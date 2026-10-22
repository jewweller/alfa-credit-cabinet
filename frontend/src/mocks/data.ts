// Исходные данные моков по контракту (docs/api/openapi.json, ветка contract/c5).
// Клиент — ООО «Пекарня Север». По заявке на каждый сценарий карточки (C5).
import type {
  ApplicationDetail,
  FeedItem,
  Me,
  Offer,
  Product,
  StatusHistoryEntry,
} from '../api/types';
import { monthlyPayment } from './loanMath';

const now = Date.now();
export const minutesAgo = (m: number) => new Date(now - m * 60_000).toISOString();
const MIN = 1;
const HOUR = 60;
const DAY = 24 * HOUR;

export const PRODUCT_IDS = {
  EXPRESS_WC: '7f1c2b0a-0000-4000-8000-000000000001',
  EQUIPMENT: '7f1c2b0a-0000-4000-8000-000000000002',
  OVERDRAFT: '7f1c2b0a-0000-4000-8000-000000000003',
} as const;

export const products: Product[] = [
  {
    id: PRODUCT_IDS.EXPRESS_WC,
    code: 'EXPRESS_WC',
    name: 'Экспресс-оборот',
    purpose_tags: ['working_capital', 'cash_gap'],
    min_amount: '300000.00',
    max_amount: '5000000.00',
    min_term: 3,
    max_term: 24,
    base_rate: '18.00',
  },
  {
    id: PRODUCT_IDS.EQUIPMENT,
    code: 'EQUIPMENT',
    name: 'Инвест-оборудование',
    purpose_tags: ['equipment'],
    min_amount: '1000000.00',
    max_amount: '30000000.00',
    min_term: 12,
    max_term: 60,
    base_rate: '16.00',
  },
  {
    id: PRODUCT_IDS.OVERDRAFT,
    code: 'OVERDRAFT',
    name: 'Овердрафт для бизнеса',
    purpose_tags: ['cash_gap'],
    min_amount: '100000.00',
    max_amount: '3000000.00',
    min_term: 12,
    max_term: 12,
    base_rate: '20.00',
  },
];

export const me: Me = {
  id: '5a0e7d6c-0000-4000-8000-0000000000aa',
  email: 'bakery@demo.local',
  full_name: 'Ирина Соколова',
  role: 'client',
  company: {
    id: '5a0e7d6c-0000-4000-8000-0000000000cc',
    inn: '7701000019',
    name: 'ООО «Пекарня Север»',
    kind: 'LLC',
    okved_main: '10.71',
    segment: 'small',
  },
};

/** Оффер с платежом, посчитанным по аннуитету. */
export function makeOffer(
  id: string,
  productId: string,
  amount: string,
  term: number,
  rate: string,
  status: Offer['status'] = 'active',
): Offer {
  return {
    id,
    product_id: productId,
    amount,
    term_months: term,
    rate,
    monthly_payment: monthlyPayment(amount, rate, term),
    status,
  };
}

/** Внутренняя запись мока: карточка + история + все офферы. */
export interface MockApplication {
  detail: ApplicationDetail;
  history: StatusHistoryEntry[];
  offers: Offer[];
}

const base = {
  company_id: me.company!.id,
  applicant_id: me.id,
  revenue_12m: '24000000.00',
  existing_payments_monthly: '150000.00',
  bki_consent: true,
  version: 1,
  documents: [],
  info_request: null,
  decision: null,
  active_offer: null,
};

function h(
  from: StatusHistoryEntry['from_status'],
  to: StatusHistoryEntry['to_status'],
  actor: StatusHistoryEntry['actor_type'],
  at: number,
): StatusHistoryEntry {
  return { from_status: from, to_status: to, actor_type: actor, created_at: minutesAgo(at) };
}

/** Путь от черновика до решения: создание, отправка, проверка, оценка. */
function pipeline(createdAt: number, submittedAt: number): StatusHistoryEntry[] {
  return [
    h(null, 'DRAFT', 'client', createdAt),
    h('DRAFT', 'SUBMITTED', 'client', submittedAt),
    h('SUBMITTED', 'ENRICHMENT', 'system', submittedAt - 1),
    h('ENRICHMENT', 'SCORING', 'system', submittedAt - 2),
  ];
}

export function seedApplications(): MockApplication[] {
  const counter = makeOffer('0ffe7000-0000-4000-8000-000000001055', PRODUCT_IDS.EXPRESS_WC, '2000000.00', 24, '20.00');
  const issued = makeOffer('0ffe7000-0000-4000-8000-000000000987', PRODUCT_IDS.EXPRESS_WC, '1500000.00', 12, '18.00', 'accepted');

  return [
    {
      // Нужны документы: загрузка → повторная отправка → конвейер → одобрение.
      detail: {
        ...base,
        id: 'a-1042',
        number: '1042',
        product_id: PRODUCT_IDS.EXPRESS_WC,
        amount: '3000000.00',
        term_months: 12,
        purpose: 'working_capital',
        revenue_12m: '12000000.00',
        existing_payments_monthly: '0.00',
        status: 'INFO_REQUESTED',
        status_changed_at: minutesAgo(10 * MIN),
        submitted_at: minutesAgo(40 * MIN),
        decision: { outcome: 'info_requested', decided_by: 'system', reason_code: null, decided_at: minutesAgo(10 * MIN) },
        info_request: {
          id: '1fe00000-0000-4000-8000-000000001042',
          status: 'open',
          items: [
            { kind: 'tax_return', title: 'Налоговая декларация за 2025 год', required: true },
            { kind: 'bank_statement', title: 'Выписка по расчётному счёту за 6 месяцев', required: false },
          ],
          message:
            'Выручка в заявке отличается от данных ФНС. Подтвердите её декларацией — так мы быстрее примем решение.',
          created_at: minutesAgo(10 * MIN),
        },
      },
      history: [...pipeline(2 * DAY, 40 * MIN), h('SCORING', 'INFO_REQUESTED', 'system', 10 * MIN)],
      offers: [],
    },
    {
      // Черновик: карточка ведёт в мастер заявки (C4).
      detail: {
        ...base,
        id: 'a-1048',
        number: '1048',
        product_id: PRODUCT_IDS.OVERDRAFT,
        amount: '500000.00',
        term_months: 12,
        purpose: 'cash_gap',
        revenue_12m: null,
        existing_payments_monthly: null,
        bki_consent: false,
        status: 'DRAFT',
        status_changed_at: minutesAgo(26 * HOUR),
        submitted_at: null,
      },
      history: [h(null, 'DRAFT', 'client', 26 * HOUR)],
      offers: [],
    },
    {
      // Оценивается сейчас; через ~10 секунд банк одобрит (см. db.ts).
      detail: {
        ...base,
        id: 'a-1051',
        number: '1051',
        product_id: PRODUCT_IDS.EQUIPMENT,
        amount: '8000000.00',
        term_months: 36,
        purpose: 'equipment',
        status: 'SCORING',
        status_changed_at: minutesAgo(1 * MIN),
        submitted_at: minutesAgo(3 * MIN),
      },
      history: pipeline(3 * HOUR, 3 * MIN),
      offers: [],
    },
    {
      // Другие условия: просили 2 млн на 12 мес, предлагаем на 24 мес (R10, план, раздел 7).
      detail: {
        ...base,
        id: 'a-1055',
        number: '1055',
        product_id: PRODUCT_IDS.EXPRESS_WC,
        amount: '2000000.00',
        term_months: 12,
        purpose: 'working_capital',
        status: 'COUNTER_OFFER',
        status_changed_at: minutesAgo(1 * HOUR),
        submitted_at: minutesAgo(1 * HOUR + 5),
        decision: { outcome: 'counter_offer', decided_by: 'system', reason_code: null, decided_at: minutesAgo(1 * HOUR) },
        active_offer: counter,
      },
      history: [...pipeline(5 * HOUR, 1 * HOUR + 5), h('SCORING', 'COUNTER_OFFER', 'system', 1 * HOUR)],
      offers: [counter],
    },
    {
      // Выдан: всё зелёное, кнопка ведёт к графику (C7).
      detail: {
        ...base,
        id: 'a-0987',
        number: '0987',
        product_id: PRODUCT_IDS.EXPRESS_WC,
        amount: '1500000.00',
        term_months: 12,
        purpose: 'working_capital',
        status: 'ISSUED',
        status_changed_at: minutesAgo(40 * DAY),
        submitted_at: minutesAgo(41 * DAY),
        decision: { outcome: 'approved', decided_by: 'system', reason_code: null, decided_at: minutesAgo(41 * DAY - 10) },
        active_offer: issued,
        version: 6,
      },
      history: [
        ...pipeline(42 * DAY, 41 * DAY),
        h('SCORING', 'APPROVED', 'system', 41 * DAY - 10),
        h('APPROVED', 'SIGNING', 'client', 40 * DAY + 60),
        h('SIGNING', 'SIGNED', 'client', 40 * DAY + 50),
        h('SIGNED', 'ISSUED', 'system', 40 * DAY),
      ],
      offers: [issued],
    },
    {
      // Отказ: причина R10 — нагрузка, ничего не подошло.
      detail: {
        ...base,
        id: 'a-0950',
        number: '0950',
        product_id: PRODUCT_IDS.EQUIPMENT,
        amount: '25000000.00',
        term_months: 60,
        purpose: 'equipment',
        status: 'REJECTED',
        status_changed_at: minutesAgo(90 * DAY),
        submitted_at: minutesAgo(90 * DAY + 30),
        decision: {
          outcome: 'rejected',
          decided_by: 'system',
          reason_code: 'no_suitable_terms',
          decided_at: minutesAgo(90 * DAY),
        },
      },
      history: [...pipeline(91 * DAY, 90 * DAY + 30), h('SCORING', 'REJECTED', 'system', 90 * DAY)],
      offers: [],
    },
  ];
}

export function seedFeed(): FeedItem[] {
  return [
    {
      id: 'e-1',
      kind: 'event',
      title: 'Нужны документы по заявке №1042',
      body: 'Загрузите налоговую декларацию за 2025 год, чтобы мы продолжили рассмотрение.',
      created_at: minutesAgo(10),
      application_id: 'a-1042',
      read: false,
    },
    {
      id: 'e-2',
      kind: 'event',
      title: 'Заявка №1051 отправлена',
      body: 'Проверяем данные о компании. Ничего делать не нужно.',
      created_at: minutesAgo(3),
      application_id: 'a-1051',
      read: true,
    },
    {
      id: 'n-1',
      kind: 'news',
      title: 'Как подготовить декларацию для банка',
      body: 'Какие страницы нужны, в каком формате загружать и что делать, если декларация уточнённая.',
      created_at: minutesAgo(60 * 5),
      reason: 'Ваша заявка ждёт документы',
      read: false,
    },
    {
      id: 'n-2',
      kind: 'news',
      title: 'Цены на муку: чего ждать пекарням осенью',
      body: 'Короткий обзор для производителей хлеба и выпечки.',
      created_at: minutesAgo(60 * 20),
      reason: 'Ваш ОКВЭД 10.71 — производство хлеба',
      read: false,
    },
    {
      id: 'n-3',
      kind: 'news',
      title: 'Лизинг или кредит на оборудование',
      body: 'Сравниваем два способа купить печь или линию упаковки.',
      created_at: minutesAgo(60 * 48),
      reason: 'У вас заявка на «Инвест-оборудование»',
      read: true,
    },
  ];
}
