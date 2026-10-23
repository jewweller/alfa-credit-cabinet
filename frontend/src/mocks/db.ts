// Состояние моков: действия клиента меняют заявки, а «конвейер» банка двигает
// статусы по таймеру, как воркер на бэке (план, раздел 5).
// Хранится в sessionStorage: переживает перезагрузку вкладки, новая вкладка
// начинает с исходных данных, ?reset=1 сбрасывает текущую. Загруженные файлы
// живут только до перезагрузки (в списке остаются, скачать уже нельзя).
import type {
  ApplicationCreate,
  ApplicationDetail,
  ApplicationStatus,
  ApplicationSummary,
  DocumentInfo,
  DocumentKind,
  ApplicationUpdate,
  FeedItem,
  Me,
  Offer,
  StatusActor,
} from '../api/types';
import { formatMoney } from '../features/format';
import { makeOffer, me as bakery, products, seedApplications, seedFeed, type MockApplication } from './data';

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

const STORAGE_KEY = 'mock-db-v2';
const apps = new Map<string, MockApplication>();
const files = new Map<string, Blob>();
const idempotent = new Map<string, unknown>();
let feed: FeedItem[] = [];

function save() {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ apps: [...apps.values()], feed }));
  } catch {
    // хранилище недоступно — состояние проживёт до перезагрузки
  }
}

function load(): boolean {
  try {
    if (new URLSearchParams(window.location.search).has('reset')) sessionStorage.removeItem(STORAGE_KEY);
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return false;
    const saved = JSON.parse(raw) as { apps: MockApplication[]; feed: FeedItem[] };
    for (const app of saved.apps) apps.set(app.detail.id, app);
    feed = saved.feed;
    return true;
  } catch {
    return false;
  }
}

function reset() {
  apps.clear();
  for (const app of seedApplications()) apps.set(app.detail.id, app);
  feed = seedFeed();
  save();
}

/**
 * Чем закончится конвейер для заявки. №1051 банк одобряет сам (грейд A, ставка базовая),
 * остальные после повторной отправки — через специалиста (грейд B, база + 2 п.п.).
 */
const OUTCOME: Record<string, { rate: string; by: 'system' | 'underwriter' }> = {
  'a-1051': { rate: '16.00', by: 'system' },
};
const DEFAULT_OUTCOME = { rate: '20.00', by: 'underwriter' as const };

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
  notify(app, to);
}

const EVENT_TEXT: Partial<Record<ApplicationStatus, (n: string) => [string, string]>> = {
  SUBMITTED: (n) => [`Заявка №${n} отправлена`, 'Проверяем данные о компании. Ничего делать не нужно.'],
  MANUAL_REVIEW: (n) => [`Заявку №${n} смотрит специалист`, 'Обычно это занимает до одного рабочего дня.'],
  APPROVED: (n) => [`Заявка №${n} одобрена`, 'Посмотрите предложение и график платежей.'],
  COUNTER_OFFER: (n) => [`По заявке №${n} — другие условия`, 'Сравните их с запрошенными.'],
  REJECTED: (n) => [`По заявке №${n} — отказ`, 'Мы объясним причину и что можно сделать.'],
  SIGNING: (n) => [`Предложение по заявке №${n} принято`, 'Осталось подписать документы.'],
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
      application_id: app.detail.id,
      read: false,
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

/**
 * Двигает заявку по конвейеру с её текущего статуса: проверка → оценка →
 * (специалист) → одобрение. Вызывается после отправки и при загрузке страницы,
 * поэтому перезагрузка посреди конвейера не «замораживает» заявку.
 */
function continuePipeline(id: string, firstDelay = STEP_MS) {
  const app = apps.get(id);
  if (!app) return;
  const outcome = OUTCOME[id] ?? DEFAULT_OUTCOME;
  const decide = (current: MockApplication) => {
    const offer = makeOffer(
      crypto.randomUUID(),
      current.detail.product_id!,
      current.detail.amount!,
      current.detail.term_months!,
      outcome.rate,
    );
    approve(current, offer, outcome.by, 'APPROVED');
  };

  const next: Partial<Record<ApplicationStatus, (current: MockApplication) => void>> = {
    SUBMITTED: (current) => transition(current, 'ENRICHMENT', 'system'),
    ENRICHMENT: (current) => transition(current, 'SCORING', 'system'),
    SCORING: (current) =>
      outcome.by === 'underwriter' ? transition(current, 'MANUAL_REVIEW', 'system') : decide(current),
    MANUAL_REVIEW: decide,
  };
  const step = next[app.detail.status];
  if (!step) return;
  // Специалисту даём побольше времени — так на демо видно ручное рассмотрение.
  const delay = app.detail.status === 'MANUAL_REVIEW' ? 8000 : firstDelay;
  setTimeout(() => {
    const current = apps.get(id);
    if (!current || !next[current.detail.status]) return;
    next[current.detail.status]!(current);
    save();
    continuePipeline(id);
  }, delay);
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

if (!load()) reset();
// №1051 в исходных данных «оценивается» — через 10 секунд банк её одобрит (проверка опроса).
for (const id of apps.keys()) continuePipeline(id, id === 'a-1051' ? 10_000 : STEP_MS);

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
    return find(id).detail;
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
    return app.detail;
  },

  submit(id: string, key: string | null): ApplicationDetail {
    return withIdempotency(key, `submit:${id}`, () => {
      const app = find(id);
      if (app.detail.status !== 'DRAFT') {
        throw new MockHttpError(409, 'invalid_transition', 'Заявка уже отправлена');
      }
      checkComplete(app.detail);
      transition(app, 'SUBMITTED', 'client');
      app.detail = { ...app.detail, submitted_at: app.detail.status_changed_at };
      save();
      continuePipeline(id);
      return app.detail;
    });
  },

  accept(id: string, offerId: string, key: string | null): ApplicationDetail {
    return withIdempotency(key, `accept:${id}`, () => {
      const app = find(id);
      activeOffer(app, offerId);
      transition(app, 'SIGNING', 'client');
      setOfferStatus(app, offerId, 'accepted');
      save();
      return app.detail;
    });
  },

  decline(id: string, offerId: string, key: string | null): ApplicationDetail {
    return withIdempotency(key, `decline:${id}`, () => {
      const app = find(id);
      activeOffer(app, offerId);
      transition(app, 'DECLINED_BY_CLIENT', 'client');
      setOfferStatus(app, offerId, 'declined');
      save();
      return app.detail;
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
    app.detail = { ...app.detail, documents: [...app.detail.documents, doc], version: app.detail.version + 1 };
    save();
    return doc;
  },

  file(documentId: string): { blob: Blob; doc: DocumentInfo } {
    for (const app of apps.values()) {
      const doc = app.detail.documents.find((d) => d.id === documentId);
      const blob = files.get(documentId);
      if (doc && blob) return { blob, doc };
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
      transition(app, 'SUBMITTED', 'client');
      app.detail = {
        ...app.detail,
        info_request: request ? { ...request, status: 'answered' } : null,
        submitted_at: app.detail.status_changed_at,
      };
      save();
      continuePipeline(id);
      return app.detail;
    });
  },

  cancel(id: string, key: string | null): ApplicationDetail {
    return withIdempotency(key, `cancel:${id}`, () => {
      const app = find(id);
      transition(app, 'CANCELLED', 'client');
      app.detail = {
        ...app.detail,
        info_request: app.detail.info_request ? { ...app.detail.info_request, status: 'answered' } : null,
      };
      save();
      return app.detail;
    });
  },

  /** События — только по своим заявкам. Исходные новости подобраны под Пекарню, другим их не показываем. */
  feed(companyId: string): FeedItem[] {
    return feed.filter((item) =>
      item.kind === 'event'
        ? item.application_id !== null &&
          item.application_id !== undefined &&
          apps.get(item.application_id)?.detail.company_id === companyId
        : companyId === bakery.company!.id,
    );
  },
};
