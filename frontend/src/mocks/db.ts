// Состояние моков: действия клиента меняют заявки, а «конвейер» банка двигает
// статусы по таймеру, как воркер на бэке (план, раздел 5).
// Хранится в sessionStorage: переживает перезагрузку вкладки, новая вкладка
// начинает с исходных данных, ?reset=1 сбрасывает текущую. Загруженные файлы
// живут только до перезагрузки (в списке остаются, скачать уже нельзя).
import type {
  AuditEntry,
  DemoResetResult,
  ApplicationCreate,
  ApplicationDetail,
  ApplicationStatus,
  ApplicationSummary,
  BankApplicationDetail,
  BankApplicationSummary,
  BankDecision,
  CompanyBrief,
  EnrichmentResult,
  Grade,
  UnderwriterDecisionRequest,
  DocumentInfo,
  DocumentKind,
  ApplicationUpdate,
  FeedItem,
  FeedItemKind,
  FeedResponse,
  Me,
  Offer,
  SigningCode,
  StatusActor,
} from '../api/types';
import { formatMoney } from '../features/format';
import { entry, filterAudit, owner, seedAudit, staff, SYSTEM, type Actor, type AuditFilter } from './audit';
import { MODEL_VERSION, rankNews } from './feedRanking';
import { clearFiles, getFile, putFile } from './fileStore';
import { makeOffer, products, seedApplications, seedFeed, users, type MockApplication } from './data';
import { decide, evaluate, REVENUE_INFO_REQUEST, sourcesOf, type Verdict } from './decision';
import { rawRegistry } from './sources';

/** Как в backend/app/domain/state_machine.py. */
const TRANSITIONS: Record<ApplicationStatus, ApplicationStatus[]> = {
  DRAFT: ['SUBMITTED', 'CANCELLED'],
  SUBMITTED: ['ENRICHMENT'],
  ENRICHMENT: ['SCORING'],
  SCORING: ['APPROVED', 'COUNTER_OFFER', 'REJECTED', 'INFO_REQUESTED', 'MANUAL_REVIEW'],
  MANUAL_REVIEW: ['APPROVED', 'COUNTER_OFFER', 'REJECTED', 'INFO_REQUESTED'],
  INFO_REQUESTED: ['SUBMITTED', 'CANCELLED'],
  APPROVED: ['SIGNING', 'DECLINED_BY_CLIENT'],
  COUNTER_OFFER: ['SIGNING', 'DECLINED_BY_CLIENT'],
  SIGNING: ['SIGNED'],
  SIGNED: ['ISSUED'],
  REJECTED: [],
  ISSUED: [],
  DECLINED_BY_CLIENT: [],
  CANCELLED: [],
};

export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
export const ALLOWED_MIME = ['application/pdf', 'image/jpeg', 'image/png'];

/** Шаг конвейера, мс. Как PIPELINE_STEP_DELAY_SEC на бэке, чтобы смена статусов была видна. */
const STEP_MS = 2500;

export class MockHttpError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly field?: string,
  ) {
    super(message);
  }
}

const STORAGE_KEY = 'mock-db-v6';
const apps = new Map<string, MockApplication>();
const files = new Map<string, Blob>();
const idempotent = new Map<string, unknown>();
let feed: FeedItem[] = [];
let auditLog: AuditEntry[] = [];

function save() {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ apps: [...apps.values()], feed, auditLog }));
  } catch {
    // хранилище недоступно — состояние проживёт до перезагрузки
  }
}

function load(): boolean {
  try {
    if (new URLSearchParams(window.location.search).has('reset')) sessionStorage.removeItem(STORAGE_KEY);
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return false;
    const saved = JSON.parse(raw) as { apps: MockApplication[]; feed: FeedItem[]; auditLog?: AuditEntry[] };
    for (const app of saved.apps) apps.set(app.detail.id, app);
    feed = saved.feed;
    auditLog = saved.auditLog ?? seedAudit([...apps.values()]);
    return true;
  } catch {
    return false;
  }
}

function reset() {
  apps.clear();
  void clearFiles();
  for (const app of seedApplications()) apps.set(app.detail.id, app);
  feed = seedFeed();
  auditLog = seedAudit([...apps.values()]);
  save();
}

/** Строка в журнал действий (audit_log). */
function log(action: AuditEntry['action'], actor: Actor, app: MockApplication | null, summary: string, details: Record<string, unknown> = {}) {
  auditLog = [entry(action, actor, app, summary, details), ...auditLog];
}

const change = (from: ApplicationStatus, to: ApplicationStatus) => ({ from_status: from, to_status: to });

// ── Вспомогательное ────────────────────────────────────────────────────────

function find(id: string): MockApplication {
  const app = apps.get(id);
  if (!app) throw new MockHttpError(404, 'not_found', 'Заявка не найдена');
  return app;
}

function transition(app: MockApplication, to: ApplicationStatus, actor: StatusActor) {
  const from = app.detail.status;
  if (!TRANSITIONS[from].includes(to)) {
    throw new MockHttpError(409, 'invalid_transition', `Переход ${from} → ${to} не разрешён`);
  }
  const at = new Date().toISOString();
  app.detail = { ...app.detail, status: to, status_changed_at: at, version: app.detail.version + 1 };
  app.history = [...app.history, { from_status: from, to_status: to, actor_type: actor, created_at: at }];
  // Действия клиента и специалиста пишут в журнал сами — со своим именем; здесь только система.
  if (actor === 'system') {
    log(to === 'ISSUED' ? 'loan.issued' : 'application.status_changed', SYSTEM, app, `${from} → ${to}`, change(from, to));
  }
  notify(app, to);
}

const EVENT_TEXT: Partial<Record<ApplicationStatus, (n: string) => [string, string]>> = {
  SUBMITTED: (n) => [`Заявка №${n} отправлена`, 'Проверяем данные о компании. Ничего делать не нужно.'],
  INFO_REQUESTED: (n) => [`По заявке №${n} нужны документы`, 'Загрузите их в карточке заявки — и мы продолжим рассмотрение.'],
  MANUAL_REVIEW: (n) => [`Заявку №${n} смотрит специалист`, 'Обычно это занимает до одного рабочего дня.'],
  APPROVED: (n) => [`Заявка №${n} одобрена`, 'Посмотрите предложение и график платежей.'],
  COUNTER_OFFER: (n) => [`По заявке №${n} — другие условия`, 'Сравните их с запрошенными.'],
  REJECTED: (n) => [`По заявке №${n} — отказ`, 'Мы объясним причину и что можно сделать.'],
  SIGNING: (n) => [`Предложение по заявке №${n} принято`, 'Осталось подписать документы.'],
  ISSUED: (n) => [`По заявке №${n} деньги зачислены`, 'Средства у вас на счёте. График платежей всегда под рукой.'],
  CANCELLED: (n) => [`Заявка №${n} отозвана`, 'Её можно подать заново в любой момент.'],
};

/** Событие в ленту — «уведомления» внутри продукта вместо email/SMS (план, раздел 4). */
function notify(app: MockApplication, status: ApplicationStatus) {
  const text = EVENT_TEXT[status]?.(app.detail.number);
  if (!text) return;
  feed = [
    {
      id: crypto.randomUUID(),
      kind: 'event',
      title: text[0],
      body: text[1],
      created_at: new Date().toISOString(),
      read: false,
      application_id: app.detail.id,
      application_number: app.detail.number,
      status,
      reasons: [],
      score: null,
    },
    ...feed,
  ];
}

function approve(app: MockApplication, offer: Offer, by: 'system' | 'underwriter', status: 'APPROVED' | 'COUNTER_OFFER') {
  app.offers = [...app.offers.map((o) => (o.status === 'active' ? { ...o, status: 'declined' as const } : o)), offer];
  transition(app, status, by === 'system' ? 'system' : 'underwriter');
  app.detail = {
    ...app.detail,
    active_offer: offer,
    decision: {
      outcome: status === 'APPROVED' ? 'approved' : 'counter_offer',
      decided_by: by,
      reason_code: null,
      decided_at: app.detail.status_changed_at,
    },
  };
}

/** Применяет решение движка (или специалиста) к заявке: статус, решение, оффер или запрос документов. */
function apply(app: MockApplication, verdict: Verdict, by: 'system' | 'underwriter') {
  const actor: StatusActor = by === 'system' ? 'system' : 'underwriter';
  switch (verdict.kind) {
    case 'approved':
    case 'counter_offer': {
      const { productId, amount, term, rate } = verdict.offer;
      const offer = makeOffer(crypto.randomUUID(), productId, amount, term, rate);
      approve(app, offer, by, verdict.kind === 'approved' ? 'APPROVED' : 'COUNTER_OFFER');
      return;
    }
    case 'rejected':
      transition(app, 'REJECTED', actor);
      app.detail = {
        ...app.detail,
        decision: { outcome: 'rejected', decided_by: by, reason_code: verdict.reason, decided_at: app.detail.status_changed_at },
      };
      return;
    case 'info_requested':
      transition(app, 'INFO_REQUESTED', actor);
      app.detail = {
        ...app.detail,
        decision: { outcome: 'info_requested', decided_by: by, reason_code: null, decided_at: app.detail.status_changed_at },
        info_request: {
          id: crypto.randomUUID(),
          status: 'open',
          ...(verdict.request ?? REVENUE_INFO_REQUEST),
          created_at: app.detail.status_changed_at,
        },
      };
      return;
    case 'manual_review':
      transition(app, 'MANUAL_REVIEW', actor);
      return;
  }
}

/**
 * Двигает заявку по конвейеру с её текущего статуса: проверка → оценка → решение
 * по правилам (decision.ts). Ручное рассмотрение ждёт специалиста в кабинете банка (B4).
 * Вызывается после отправки и при загрузке страницы, поэтому перезагрузка
 * посреди конвейера не «замораживает» заявку.
 */
function continuePipeline(id: string, firstDelay = STEP_MS) {
  const app = apps.get(id);
  if (!app) return;

  const next: Partial<Record<ApplicationStatus, (current: MockApplication) => void>> = {
    SUBMITTED: (current) => transition(current, 'ENRICHMENT', 'system'),
    ENRICHMENT: (current) => transition(current, 'SCORING', 'system'),
    SCORING: (current) => apply(current, decide(current.detail), 'system'),
  };
  if (!next[app.detail.status]) return;
  setTimeout(() => {
    const current = apps.get(id);
    if (!current || !next[current.detail.status]) return;
    next[current.detail.status]!(current);
    save();
    continuePipeline(id);
  }, firstDelay);
}

function withIdempotency<T>(key: string | null, scope: string, run: () => T): T {
  if (!key) return run();
  const full = `${scope}:${key}`;
  if (idempotent.has(full)) return idempotent.get(full) as T;
  const result = run();
  idempotent.set(full, result);
  return result;
}

function activeOffer(app: MockApplication, offerId: string): Offer {
  const offer = app.offers.find((o) => o.id === offerId);
  if (!offer) throw new MockHttpError(404, 'not_found', 'Оффер не найден');
  if (offer.status !== 'active') {
    throw new MockHttpError(409, 'offer_not_active', 'Это предложение уже не действует');
  }
  return offer;
}

/** active_offer — последний оффер с его статусом; после принятия не обнуляется (контракт). */
function setOfferStatus(app: MockApplication, offerId: string, status: Offer['status']) {
  app.offers = app.offers.map((o) => (o.id === offerId ? { ...o, status } : o));
  app.detail = { ...app.detail, active_offer: app.offers.find((o) => o.id === offerId) ?? null };
}

/** Проверка полноты перед отправкой (план, раздел 4, этап 2): первая ошибка — с полем. */
function checkComplete(detail: ApplicationDetail) {
  const fail = (field: string, message: string) => {
    throw new MockHttpError(422, 'validation_error', message, field);
  };
  const product = products.find((p) => p.id === detail.product_id);
  if (!product) return fail('product_id', 'Выберите продукт');
  if (!detail.purpose) return fail('purpose', 'Укажите, на что нужны деньги');
  const amount = Number(detail.amount ?? 0);
  if (amount < Number(product.min_amount) || amount > Number(product.max_amount)) {
    return fail(
      'amount',
      `Сумма для «${product.name}» — от ${formatMoney(product.min_amount)} до ${formatMoney(product.max_amount)}`,
    );
  }
  const term = detail.term_months ?? 0;
  if (term < product.min_term || term > product.max_term) {
    return fail('term_months', `Срок для «${product.name}» — от ${product.min_term} до ${product.max_term} мес`);
  }
  if (!detail.revenue_12m || Number(detail.revenue_12m) <= 0) return fail('revenue_12m', 'Укажите выручку за 12 месяцев');
  if (detail.existing_payments_monthly === null) {
    return fail('existing_payments_monthly', 'Укажите платежи по текущим кредитам — если их нет, поставьте 0');
  }
  if (!detail.bki_consent) return fail('bki_consent', 'Нужно согласие на запрос в бюро кредитных историй');
}

const MONEY_RE = /^\d+\.\d{2}$/;

/** Выданные коды подписи по заявке: сверяем введённый код с последним. */
const signingCodes = new Map<string, SigningCode>();
/** Сколько действует код подписи. */
const SIGNING_CODE_TTL_MS = 5 * 60_000;
/** Пауза перед симуляцией выдачи — чтобы на экране было видно «Готовим выдачу». */
const ISSUE_DELAY_MS = 4000;

/** Симуляция выдачи: SIGNED → ISSUED по таймеру, как воркер на бэке. */
function scheduleIssue(id: string) {
  setTimeout(() => {
    const app = apps.get(id);
    if (!app || app.detail.status !== 'SIGNED') return;
    transition(app, 'ISSUED', 'system');
    save();
  }, ISSUE_DELAY_MS);
}

/** Таймеры конвейера и выдачи — при загрузке и после сброса демо. */
function startTimers() {
  // №1051 в исходных данных «оценивается» — через 10 секунд банк её одобрит (проверка опроса).
  for (const id of apps.keys()) {
    continuePipeline(id, id === 'a-1051' ? 10_000 : STEP_MS);
    if (apps.get(id)!.detail.status === 'SIGNED') scheduleIssue(id);
  }
}

// Запуск — после объявления констант выше: scheduleIssue читает ISSUE_DELAY_MS.
if (!load()) reset();
startTimers();

/** Карточка наружу — как на бэке: запрос документов виден только в статусе INFO_REQUESTED. */
function view(detail: ApplicationDetail): ApplicationDetail {
  return detail.status === 'INFO_REQUESTED' ? detail : { ...detail, info_request: null };
}

// ── Кабинет банка: что видит андеррайтер ─────────────────────────────────────

/** До конца обогащения ответов источников ещё нет; до решения нет скоринга и правил. */
const BEFORE_ENRICHMENT: ApplicationStatus[] = ['DRAFT', 'SUBMITTED', 'ENRICHMENT'];
const BEFORE_DECISION: ApplicationStatus[] = [...BEFORE_ENRICHMENT, 'SCORING'];
/** Раньше всех в очереди — то, что ждёт человека. */
const QUEUE_FIRST: ApplicationStatus = 'MANUAL_REVIEW';

function companyOf(app: MockApplication): CompanyBrief {
  return users.find((u) => u.company?.id === app.detail.company_id)!.company!;
}

function evaluation(app: MockApplication) {
  return BEFORE_DECISION.includes(app.detail.status) ? null : evaluate(app.detail);
}

/** Ответы источников — время берём из истории: когда заявка ушла на оценку. */
function enrichmentOf(app: MockApplication): EnrichmentResult[] {
  if (BEFORE_ENRICHMENT.includes(app.detail.status)) return [];
  const at =
    [...app.history].reverse().find((h) => h.to_status === 'SCORING')?.created_at ??
    app.detail.submitted_at ??
    app.detail.status_changed_at;
  const src = sourcesOf(app.detail);
  const registrySource = companyOf(app).kind === 'IE' ? 'egrip' : 'egrul';
  return [
    src.registry
      ? { source: registrySource, status: 'ok', attempts: 1, fetched_at: at, response: rawRegistry(src.registry) }
      : { source: registrySource, status: 'not_found', attempts: 1, fetched_at: at, response: null },
    { source: 'fns_tb', status: 'ok', attempts: 1, fetched_at: at, response: { ...src.fns } },
    src.bki
      ? { source: 'bki', status: 'ok', attempts: 1, fetched_at: at, response: { ...src.bki } }
      : { source: 'bki', status: 'error', attempts: 3, fetched_at: at, response: null },
  ];
}

function bankDecisionOf(app: MockApplication): BankDecision | null {
  const decision = app.detail.decision;
  if (!decision) return null;
  const review = decision.decided_by === 'underwriter' ? app.review : null;
  return { ...decision, underwriter: review?.underwriter ?? null, comment: review?.comment ?? null };
}

function bankDetailOf(app: MockApplication): BankApplicationDetail {
  const ev = evaluation(app);
  return {
    application: view(app.detail),
    company: companyOf(app),
    applicant_name: users.find((u) => u.id === app.detail.applicant_id)?.full_name ?? '—',
    registry: sourcesOf(app.detail).registry,
    assignee: app.assignee ?? null,
    enrichment: enrichmentOf(app),
    scoring: ev?.scoring ?? null,
    rules: ev?.rules ?? [],
    decision: bankDecisionOf(app),
  };
}

function bankSummaryOf(app: MockApplication): BankApplicationSummary {
  const { detail } = app;
  const scoring = evaluation(app)?.scoring;
  return {
    id: detail.id,
    number: detail.number,
    company: companyOf(app),
    product_id: detail.product_id,
    amount: detail.amount,
    term_months: detail.term_months,
    status: detail.status,
    status_changed_at: detail.status_changed_at,
    submitted_at: detail.submitted_at,
    score: scoring?.total_score ?? null,
    grade: scoring?.grade ?? null,
    assignee: app.assignee ?? null,
  };
}

/** Решение специалиста → вердикт для apply(); поля по исходу и лимиты продукта (контракт B4). */
function underwriterVerdict(app: MockApplication, body: UnderwriterDecisionRequest): Verdict {
  const fail = (field: string, message: string): never => {
    throw new MockHttpError(422, 'validation_error', message, field);
  };
  const rate = (value: string | null | undefined) => {
    if (!value || !(Number(value) > 0)) fail('rate', 'Укажите ставку');
    return Number(value).toFixed(2);
  };
  switch (body.outcome) {
    case 'approved': {
      const { product_id, amount, term_months } = app.detail;
      return { kind: 'approved', offer: { productId: product_id!, amount: amount!, term: term_months!, rate: rate(body.rate) } };
    }
    case 'counter_offer': {
      const product = products.find((p) => p.id === body.product_id) ?? fail('product_id', 'Выберите продукт');
      const amount = Number(body.amount ?? 0);
      if (amount < Number(product.min_amount) || amount > Number(product.max_amount)) {
        fail('amount', `Сумма для «${product.name}» — от ${formatMoney(product.min_amount)} до ${formatMoney(product.max_amount)}`);
      }
      const term = body.term_months ?? 0;
      if (term < product.min_term || term > product.max_term) {
        fail('term_months', `Срок для «${product.name}» — от ${product.min_term} до ${product.max_term} мес`);
      }
      return { kind: 'counter_offer', offer: { productId: product.id, amount: amount.toFixed(2), term, rate: rate(body.rate) } };
    }
    case 'info_requested': {
      const items = body.info_items ?? [];
      if (items.length === 0) fail('info_items', 'Отметьте хотя бы один документ');
      const message = body.comment?.trim() ?? '';
      if (!message) fail('comment', 'Напишите клиенту, зачем нужны документы');
      return { kind: 'info_requested', request: { items, message } };
    }
    case 'rejected':
      return { kind: 'rejected', reason: body.reason_code ?? fail('reason_code', 'Выберите причину отказа') };
  }
}

// ── Операции API ───────────────────────────────────────────────────────────

export const db = {
  reset,

  /** Чужая заявка — как будто её нет. */
  assertOwner(id: string, companyId: string) {
    if (find(id).detail.company_id !== companyId) throw new MockHttpError(404, 'not_found', 'Заявка не найдена');
  },

  list(companyId: string): ApplicationSummary[] {
    return [...apps.values()].filter(({ detail }) => detail.company_id === companyId).map(({ detail }) => ({
      id: detail.id,
      number: detail.number,
      status: detail.status,
      status_changed_at: detail.status_changed_at,
      product_id: detail.product_id,
      amount: detail.amount,
      term_months: detail.term_months,
      submitted_at: detail.submitted_at,
      info_request: detail.info_request?.status === 'open' ? detail.info_request : null,
    }));
  },

  get(id: string): ApplicationDetail {
    return view(find(id).detail);
  },

  history(id: string) {
    return find(id).history;
  },

  offers(id: string) {
    return find(id).offers;
  },

  create(user: Me, body: ApplicationCreate): ApplicationDetail {
    if (body.product_id && !products.some((p) => p.id === body.product_id)) {
      throw new MockHttpError(422, 'validation_error', 'Такого продукта нет', 'product_id');
    }
    const at = new Date().toISOString();
    const last = Math.max(0, ...[...apps.values()].map((a) => Number(a.detail.number) || 0));
    const detail: ApplicationDetail = {
      id: crypto.randomUUID(),
      number: String(last + 1).padStart(4, '0'),
      company_id: user.company!.id,
      applicant_id: user.id,
      product_id: body.product_id ?? null,
      amount: body.amount ?? null,
      term_months: body.term_months ?? null,
      purpose: body.purpose ?? null,
      revenue_12m: null,
      existing_payments_monthly: null,
      bki_consent: false,
      status: 'DRAFT',
      status_changed_at: at,
      version: 1,
      submitted_at: null,
      active_offer: null,
      decision: null,
      info_request: null,
      documents: [],
    };
    apps.set(detail.id, {
      detail,
      history: [{ from_status: null, to_status: 'DRAFT', actor_type: 'client', created_at: at }],
      offers: [],
    });
    log('application.created', staff(user), apps.get(detail.id)!, 'DRAFT');
    save();
    return detail;
  },

  /** Автосохранение черновика: только переданные поля, с проверкой версии (план, раздел 9). */
  update(id: string, body: ApplicationUpdate): ApplicationDetail {
    const app = find(id);
    if (app.detail.status !== 'DRAFT') {
      throw new MockHttpError(409, 'conflict', 'Заявку уже отправили — изменить её нельзя');
    }
    if (body.version !== app.detail.version) {
      throw new MockHttpError(409, 'version_conflict', 'Заявку изменили в другой вкладке');
    }
    const { version: _version, ...fields } = body;
    for (const key of ['amount', 'revenue_12m', 'existing_payments_monthly'] as const) {
      const value = fields[key];
      if (value !== undefined && value !== null && !MONEY_RE.test(value)) {
        throw new MockHttpError(422, 'validation_error', 'Сумма указана неверно', key);
      }
    }
    if (fields.product_id && !products.some((p) => p.id === fields.product_id)) {
      throw new MockHttpError(422, 'validation_error', 'Такого продукта нет', 'product_id');
    }
    if (fields.term_months !== undefined && fields.term_months !== null && fields.term_months < 1) {
      throw new MockHttpError(422, 'validation_error', 'Срок — от 1 месяца', 'term_months');
    }
    const changes = Object.fromEntries(Object.entries(fields).filter(([, v]) => v !== undefined));
    app.detail = { ...app.detail, ...changes, version: app.detail.version + 1 };
    save();
    return view(app.detail);
  },

  submit(id: string, key: string | null): ApplicationDetail {
    return withIdempotency(key, `submit:${id}`, () => {
      const app = find(id);
      if (app.detail.status !== 'DRAFT') {
        throw new MockHttpError(409, 'invalid_transition', 'Заявка уже отправлена');
      }
      checkComplete(app.detail);
      transition(app, 'SUBMITTED', 'client');
      log('application.submitted', owner(app), app, 'DRAFT → SUBMITTED', change('DRAFT', 'SUBMITTED'));
      app.detail = { ...app.detail, submitted_at: app.detail.status_changed_at };
      save();
      continuePipeline(id);
      return view(app.detail);
    });
  },

  accept(id: string, offerId: string, key: string | null): ApplicationDetail {
    return withIdempotency(key, `accept:${id}`, () => {
      const app = find(id);
      activeOffer(app, offerId);
      const from = app.detail.status;
      transition(app, 'SIGNING', 'client');
      setOfferStatus(app, offerId, 'accepted');
      log('offer.accepted', owner(app), app, `${from} → SIGNING`, { ...change(from, 'SIGNING'), offer_id: offerId });
      save();
      return view(app.detail);
    });
  },

  decline(id: string, offerId: string, key: string | null): ApplicationDetail {
    return withIdempotency(key, `decline:${id}`, () => {
      const app = find(id);
      activeOffer(app, offerId);
      const from = app.detail.status;
      transition(app, 'DECLINED_BY_CLIENT', 'client');
      setOfferStatus(app, offerId, 'declined');
      log('offer.declined', owner(app), app, `${from} → DECLINED_BY_CLIENT`, { ...change(from, 'DECLINED_BY_CLIENT'), offer_id: offerId });
      save();
      return view(app.detail);
    });
  },

  /** Код подписи (экран C6). Симуляция ПЭП: возвращаем шесть цифр, их показывает интерфейс. */
  signingCode(id: string): SigningCode {
    const app = find(id);
    if (app.detail.status !== 'SIGNING') {
      throw new MockHttpError(409, 'invalid_transition', 'Код доступен только на шаге подписания');
    }
    const code: SigningCode = {
      code: String(Math.floor(100000 + Math.random() * 900000)),
      expires_at: new Date(Date.now() + SIGNING_CODE_TTL_MS).toISOString(),
    };
    signingCodes.set(id, code);
    log('signing.code_issued', owner(app), app, `действует до ${new Date(code.expires_at).toLocaleTimeString('ru-RU')}`, { expires_at: code.expires_at });
    save();
    return code;
  },

  confirmSigning(id: string, code: string, key: string | null): ApplicationDetail {
    return withIdempotency(key, `sign:${id}`, () => {
      const app = find(id);
      if (app.detail.status !== 'SIGNING') {
        throw new MockHttpError(409, 'invalid_transition', 'Заявка не на шаге подписания');
      }
      const issued = signingCodes.get(id);
      if (!issued || issued.code !== code || Date.parse(issued.expires_at) < Date.now()) {
        throw new MockHttpError(422, 'invalid_code', 'Код неверный или истёк', 'code');
      }
      signingCodes.delete(id);
      transition(app, 'SIGNED', 'client');
      log('signing.confirmed', owner(app), app, 'SIGNING → SIGNED', change('SIGNING', 'SIGNED'));
      save();
      scheduleIssue(id);
      return view(app.detail);
    });
  },

  upload(id: string, file: File, kind: DocumentKind, infoRequestId: string | null): DocumentInfo {
    const app = find(id);
    if (app.detail.status !== 'INFO_REQUESTED') {
      throw new MockHttpError(409, 'conflict', 'Загружать документы можно, только когда банк их запросил');
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      throw new MockHttpError(413, 'file_too_large', 'Файл больше 10 МБ', 'file');
    }
    if (!ALLOWED_MIME.includes(file.type)) {
      throw new MockHttpError(415, 'unsupported_media_type', 'Подходят только PDF, JPG и PNG', 'file');
    }
    const doc: DocumentInfo = {
      id: crypto.randomUUID(),
      kind,
      filename: file.name,
      mime: file.type,
      size_bytes: file.size,
      info_request_id: infoRequestId,
      uploaded_at: new Date().toISOString(),
    };
    files.set(doc.id, file);
    void putFile(doc.id, file);
    app.detail = { ...app.detail, documents: [...app.detail.documents, doc], version: app.detail.version + 1 };
    log('document.uploaded', owner(app), app, doc.filename, { document_id: doc.id, kind, size_bytes: doc.size_bytes });
    save();
    return doc;
  },

  /** Файл заявки: клиенту — только своей компании (чужой → 403, как на бэке), банку — любой. */
  async file(documentId: string, user: Me): Promise<{ blob: Blob; doc: DocumentInfo }> {
    const companyId = user.role === 'client' ? (user.company?.id ?? null) : null;
    const blob = files.get(documentId) ?? (await getFile(documentId));
    if (blob) files.set(documentId, blob);
    for (const app of apps.values()) {
      const doc = app.detail.documents.find((d) => d.id === documentId);
      if (doc && companyId && app.detail.company_id !== companyId) {
        throw new MockHttpError(403, 'forbidden', 'Нет доступа к файлу');
      }
      if (doc && blob) {
        log('document.downloaded', staff(user), app, doc.filename, { document_id: doc.id });
        save();
        return { blob, doc };
      }
    }
    throw new MockHttpError(404, 'not_found', 'Файл не найден');
  },

  resubmit(id: string, key: string | null): ApplicationDetail {
    return withIdempotency(key, `resubmit:${id}`, () => {
      const app = find(id);
      const request = app.detail.info_request;
      if (app.detail.status === 'INFO_REQUESTED' && request) {
        const uploaded = new Set(
          app.detail.documents.filter((d) => d.info_request_id === request.id).map((d) => d.kind),
        );
        const missing = request.items.filter((item) => item.required && !uploaded.has(item.kind));
        if (missing.length > 0) {
          throw new MockHttpError(
            422,
            'documents_required',
            `Не хватает документов: ${missing.map((m) => m.title).join(', ')}`,
          );
        }
      }
      const from = app.detail.status;
      transition(app, 'SUBMITTED', 'client');
      log('application.resubmitted', owner(app), app, `${from} → SUBMITTED`, change(from, 'SUBMITTED'));
      app.detail = {
        ...app.detail,
        info_request: request ? { ...request, status: 'answered' } : null,
        submitted_at: app.detail.status_changed_at,
      };
      save();
      continuePipeline(id);
      return view(app.detail);
    });
  },

  cancel(id: string, key: string | null): ApplicationDetail {
    return withIdempotency(key, `cancel:${id}`, () => {
      const app = find(id);
      const from = app.detail.status;
      transition(app, 'CANCELLED', 'client');
      log('application.cancelled', owner(app), app, `${from} → CANCELLED`, change(from, 'CANCELLED'));
      app.detail = {
        ...app.detail,
        info_request: app.detail.info_request ? { ...app.detail.info_request, status: 'answered' } : null,
      };
      save();
      return view(app.detail);
    });
  },

  /** События — только по своим заявкам. Исходные новости подобраны под Пекарню, другим их не показываем. */
  /** Лента клиента: события по его заявкам (свежие первыми), ниже новости по весу. */
  feed(company: NonNullable<Me['company']>, kind: FeedItemKind | null, newsLimit: number): FeedResponse {
    const own = [...apps.values()].filter((a) => a.detail.company_id === company.id && a.detail.status !== 'CANCELLED');
    const events = feed
      .filter((item) => item.application_id && apps.get(item.application_id)?.detail.company_id === company.id)
      .sort((a, b) => b.created_at.localeCompare(a.created_at));
    const productNames = Object.fromEntries(
      own.flatMap((a) => {
        const product = products.find((p) => p.id === a.detail.product_id);
        return product ? [[product.code, product.name]] : [];
      }),
    );
    const news: FeedItem[] = rankNews(
      { okvedMain: company.okved_main, segment: company.segment, products: productNames, statuses: new Set(own.map((a) => a.detail.status)) },
      Date.now(),
      newsLimit,
    ).map(({ news: n, score, reasons }) => ({
      id: n.id,
      kind: 'news',
      title: n.title,
      body: n.body,
      created_at: n.published_at,
      read: true,
      application_id: null,
      application_number: null,
      status: null,
      reasons,
      score,
    }));
    const items = kind === 'event' ? events : kind === 'news' ? news : [...events, ...news];
    return { items, ranking: { method: 'rules', model_version: MODEL_VERSION } };
  },

  /** Отметить событие прочитанным; чужое или несуществующее — 404. */
  markFeedRead(eventId: string, companyId: string) {
    const item = feed.find((f) => f.id === eventId && f.kind === 'event');
    if (!item || !item.application_id || apps.get(item.application_id)?.detail.company_id !== companyId) {
      throw new MockHttpError(404, 'not_found', 'Событие не найдено');
    }
    feed = feed.map((f) => (f.id === eventId ? { ...f, read: true } : f));
    save();
  },

  // ── Кабинет банка (B2–B4) ──

  /** Очередь: без черновиков; сначала ждущие специалиста (дольше ждут — выше), потом свежие. */
  bankList(filter: { status: string[]; grade: string | null; productId: string | null }): BankApplicationSummary[] {
    const rows = [...apps.values()]
      .filter((app) => app.detail.status !== 'DRAFT')
      .map(bankSummaryOf)
      .filter(
        (row) =>
          (filter.status.length === 0 || filter.status.includes(row.status)) &&
          (!filter.grade || row.grade === (filter.grade as Grade)) &&
          (!filter.productId || row.product_id === filter.productId),
      );
    const waiting = rows.filter((r) => r.status === QUEUE_FIRST).sort((a, b) => a.status_changed_at.localeCompare(b.status_changed_at));
    const rest = rows.filter((r) => r.status !== QUEUE_FIRST).sort((a, b) => b.status_changed_at.localeCompare(a.status_changed_at));
    return [...waiting, ...rest];
  },

  bankDetail(id: string): BankApplicationDetail {
    const app = find(id);
    if (app.detail.status === 'DRAFT') throw new MockHttpError(404, 'not_found', 'Заявка не найдена');
    return bankDetailOf(app);
  },

  /** Взять в работу: только ручное рассмотрение и только если не ведёт другой специалист. */
  assign(id: string, user: Me): BankApplicationDetail {
    const app = find(id);
    if (app.detail.status !== QUEUE_FIRST) {
      throw new MockHttpError(409, 'invalid_transition', 'Взять в работу можно только заявку на ручном рассмотрении');
    }
    if (app.assignee && app.assignee.id !== user.id) {
      throw new MockHttpError(409, 'assigned_to_other', `Заявку уже ведёт ${app.assignee.full_name}`);
    }
    if (!app.assignee) log('bank.assigned', staff(user), app, user.full_name);
    app.assignee = { id: user.id, full_name: user.full_name };
    save();
    return bankDetailOf(app);
  },

  /** Решение специалиста (B4): MANUAL_REVIEW → итог; клиент видит его в карточке и в ленте. */
  bankDecide(id: string, user: Me, body: UnderwriterDecisionRequest, key: string | null): BankApplicationDetail {
    return withIdempotency(key, `decide:${id}`, () => {
      const app = find(id);
      if (app.detail.status !== QUEUE_FIRST) {
        throw new MockHttpError(409, 'invalid_transition', 'Решение принимается только на ручном рассмотрении');
      }
      if (app.assignee && app.assignee.id !== user.id) {
        throw new MockHttpError(409, 'assigned_to_other', `Заявку ведёт ${app.assignee.full_name}`);
      }
      const verdict = underwriterVerdict(app, body);
      const me = { id: user.id, full_name: user.full_name };
      apply(app, verdict, 'underwriter');
      log('bank.decision', staff(user), app, `MANUAL_REVIEW → ${app.detail.status}`, {
        ...change('MANUAL_REVIEW', app.detail.status),
        outcome: body.outcome,
      });
      app.assignee = me;
      app.review = { underwriter: me, comment: body.outcome === 'info_requested' ? null : body.comment?.trim() || null };
      save();
      return bankDetailOf(app);
    });
  },

  /** Вход и неудачная попытка — в журнал; пароль не пишем. */
  logLogin(user: Me | null, email: string) {
    if (user) log('auth.login', staff(user), null, email);
    else log('auth.login_failed', { role: 'client', id: null, name: email }, null, email);
    save();
  },

  audit(filter: AuditFilter): AuditEntry[] {
    return filterAudit(auditLog, filter);
  },

  /** Сброс демо: заявки — к исходным, файлы и коды — прочь; журнал остаётся и пополняется. */
  demoReset(user: Me): DemoResetResult {
    const deleted = apps.size;
    apps.clear();
    files.clear();
    void clearFiles();
    signingCodes.clear();
    idempotent.clear();
    // Как на бэке: после сброса заявок нет совсем, демо-заявки заново не создаются.
    // Вернуть исходные заявки моков — ?reset=1 в адресе.
    feed = [];
    log('demo.reset', staff(user), null, `удалено заявок: ${deleted}`, { applications_deleted: deleted });
    save();
    startTimers();
    return { reset_at: new Date().toISOString(), applications_deleted: deleted };
  },
};
