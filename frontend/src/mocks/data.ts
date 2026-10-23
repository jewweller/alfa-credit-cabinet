// Исходные данные моков по контракту (docs/api/openapi.json, ветка contract/c5).
// Клиент — ООО «Пекарня Север». По заявке на каждый сценарий карточки (C5).
import type {
  ApplicationDetail,
  CompanyLookup,
  Employee,
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

/** Пароль у всех демо-учёток — как в плане (раздел 14). */
export const DEMO_PASSWORD = 'Demo2026!';

const company = (id: string, inn: string, name: string, kind: 'LLC' | 'IE', okved: string, segment: 'micro' | 'small') => ({
  id: `5a0e7d6c-0000-4000-8000-0000000${id}`,
  inn,
  name,
  kind,
  okved_main: okved,
  segment,
});

/** Демо-учётки из плана. Заявки в исходных данных есть только у Пекарни, остальные начинают с нуля. */
export const users: Me[] = [
  me,
  {
    id: '5a0e7d6c-0000-4000-8000-0000000000a2',
    email: 'kovalev@demo.local',
    full_name: 'Андрей Ковалёв',
    role: 'client',
    company: company('000c2', '500100001072', 'ИП Ковалёв А.С.', 'IE', '47.11', 'micro'),
  },
  {
    id: '5a0e7d6c-0000-4000-8000-0000000000a3',
    email: 'stroy@demo.local',
    full_name: 'Олег Белов',
    role: 'client',
    company: company('000c3', '7701000026', 'ООО «СтройРесурс»', 'LLC', '41.20', 'small'),
  },
  {
    id: '5a0e7d6c-0000-4000-8000-0000000000a4',
    email: 'melnikova@demo.local',
    full_name: 'Елена Мельникова',
    role: 'client',
    company: company('000c4', '500100002020', 'ИП Мельникова Е.В.', 'IE', '96.02', 'micro'),
  },
  // Клиенты только для очереди банка (B2): своих учёток для демо у них нет, заявки — в исходных данных.
  {
    id: '5a0e7d6c-0000-4000-8000-0000000000a5',
    email: 'vektor@demo.local',
    full_name: 'Павел Гришин',
    role: 'client',
    company: company('000c5', '7701000033', 'ООО «Вектор»', 'LLC', '46.90', 'small'),
  },
  {
    id: '5a0e7d6c-0000-4000-8000-0000000000a6',
    email: 'mirage@demo.local',
    full_name: 'Анна Зайцева',
    role: 'client',
    company: company('000c6', '7701000058', 'ООО «Мираж»', 'LLC', '56.10', 'small'),
  },
  {
    id: '5a0e7d6c-0000-4000-8000-0000000000a7',
    email: 'sboy@demo.local',
    full_name: 'Игорь Сбоев',
    role: 'client',
    company: company('000c7', '7701000065', 'ООО «Сбой-Тест»', 'LLC', '62.01', 'small'),
  },
  {
    id: '5a0e7d6c-0000-4000-8000-0000000000b1',
    email: 'underwriter@demo.local',
    full_name: 'Дмитрий Орлов',
    role: 'underwriter',
    company: null,
  },
  {
    id: '5a0e7d6c-0000-4000-8000-0000000000b2',
    email: 'admin@demo.local',
    full_name: 'Администратор стенда',
    role: 'admin',
    company: null,
  },
];

/** Ответы ЕГРЮЛ/ЕГРИП по тестовым ИНН (план, раздел 8). 7701000072 в реестре нет. */
export const registry: CompanyLookup[] = [
  {
    inn: '7701000019',
    kind: 'LLC',
    ogrn: '1187746000019',
    name: 'ООО «Пекарня Север»',
    status: 'ACTIVE',
    registered_at: '2018-09-14',
    okved_main: '10.71',
    okved_extra: ['10.72', '47.24'],
    region: 'Москва',
    address: 'г. Москва, ул. Северная, д. 12',
    director_fio: 'Соколова Ирина Павловна',
  },
  {
    inn: '500100001072',
    kind: 'IE',
    ogrn: '321500100001072',
    name: 'Ковалёв Андрей Сергеевич',
    status: 'ACTIVE',
    registered_at: '2022-06-01',
    okved_main: '47.11',
    okved_extra: [],
    region: 'Московская область',
    address: null,
    director_fio: null,
  },
  {
    inn: '500100002020',
    kind: 'IE',
    ogrn: '324500100002020',
    name: 'Мельникова Елена Викторовна',
    status: 'ACTIVE',
    registered_at: '2025-04-23',
    okved_main: '96.02',
    okved_extra: [],
    region: 'Московская область',
    address: null,
    director_fio: null,
  },
  {
    inn: '7701000026',
    kind: 'LLC',
    ogrn: '1157746000026',
    name: 'ООО «СтройРесурс»',
    status: 'LIQUIDATED',
    registered_at: '2015-03-02',
    okved_main: '41.20',
    okved_extra: ['43.99'],
    region: 'Москва',
    address: 'г. Москва, Промышленный пр., д. 4',
    director_fio: 'Белов Олег Игоревич',
  },
  {
    inn: '7701000033',
    kind: 'LLC',
    ogrn: '1197746000033',
    name: 'ООО «Вектор»',
    status: 'ACTIVE',
    registered_at: '2019-11-20',
    okved_main: '46.90',
    okved_extra: [],
    region: 'Москва',
    address: 'г. Москва, ул. Лесная, д. 7',
    director_fio: 'Гришин Павел Олегович',
  },
  {
    inn: '7701000058',
    kind: 'LLC',
    ogrn: '1207746000058',
    name: 'ООО «Мираж»',
    status: 'ACTIVE',
    registered_at: '2020-02-17',
    okved_main: '56.10',
    okved_extra: [],
    region: 'Москва',
    address: 'г. Москва, ул. Садовая, д. 1',
    director_fio: 'Зайцева Анна Петровна',
  },
  {
    inn: '7701000065',
    kind: 'LLC',
    ogrn: '1217746000065',
    name: 'ООО «Сбой-Тест»',
    status: 'ACTIVE',
    registered_at: '2021-05-05',
    okved_main: '62.01',
    okved_extra: [],
    region: 'Москва',
    address: 'г. Москва, ул. Тестовая, д. 5',
    director_fio: 'Сбоев Игорь Иванович',
  },
];

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

/** Внутренняя запись мока: карточка + история + все офферы + то, что видит только банк. */
export interface MockApplication {
  detail: ApplicationDetail;
  history: StatusHistoryEntry[];
  offers: Offer[];
  /** Кто из специалистов взял заявку в работу. */
  assignee?: Employee | null;
  /** Последнее решение специалиста: кто и с каким внутренним комментарием. */
  review?: { underwriter: Employee; comment: string | null } | null;
}

/** Специалист из демо-учёток — им подписаны решения в исходных данных. */
export const UNDERWRITER: Employee = { id: '5a0e7d6c-0000-4000-8000-0000000000b1', full_name: 'Дмитрий Орлов' };

/** Клиент из списка учёток — для заявок других компаний в исходных данных. */
function applicantOf(email: string) {
  const user = users.find((u) => u.email === email)!;
  return { company_id: user.company!.id, applicant_id: user.id };
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
  const counter = makeOffer('0ffe7000-0000-4000-8000-000000001055', PRODUCT_IDS.EXPRESS_WC, '2000000.00', 18, '18.00');
  const issued = makeOffer('0ffe7000-0000-4000-8000-000000000987', PRODUCT_IDS.EXPRESS_WC, '1500000.00', 12, '18.00', 'accepted');

  return [
    {
      // Нужны документы: загрузка → повторная отправка → специалист → решение.
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
          items: [{ kind: 'tax_return', title: 'Декларация или выписка за прошлый год', required: true }],
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
      // Другие условия: при текущих платежах 550 тыс. нагрузка на 12 мес — 36,7%, на 18 мес — 33,9% (R10).
      detail: {
        ...base,
        id: 'a-1055',
        number: '1055',
        product_id: PRODUCT_IDS.EXPRESS_WC,
        amount: '2000000.00',
        term_months: 12,
        purpose: 'working_capital',
        existing_payments_monthly: '550000.00',
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
      // Отказ специалиста: 25 млн — R5, ручное рассмотрение; нагрузка на 60 мес — 37,9%.
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
          decided_by: 'underwriter',
          reason_code: 'no_suitable_terms',
          decided_at: minutesAgo(90 * DAY),
        },
      },
      history: [
        ...pipeline(91 * DAY, 90 * DAY + 30),
        h('SCORING', 'MANUAL_REVIEW', 'system', 90 * DAY + 28),
        h('MANUAL_REVIEW', 'REJECTED', 'underwriter', 90 * DAY),
      ],
      offers: [],
      assignee: UNDERWRITER,
      review: {
        underwriter: UNDERWRITER,
        comment: 'Нагрузка 37,9% даже на максимальном сроке. Меньшая сумма не покрывает покупку линии — клиенту это не нужно.',
      },
    },
    {
      // ООО «Вектор»: текущая просрочка 120 дней — автоматический отказ (R2).
      detail: {
        ...base,
        ...applicantOf('vektor@demo.local'),
        id: 'a-1060',
        number: '1060',
        product_id: PRODUCT_IDS.EXPRESS_WC,
        amount: '4000000.00',
        term_months: 18,
        purpose: 'working_capital',
        revenue_12m: '16000000.00',
        existing_payments_monthly: '95000.00',
        status: 'REJECTED',
        status_changed_at: minutesAgo(2 * DAY),
        submitted_at: minutesAgo(2 * DAY + 4),
        decision: { outcome: 'rejected', decided_by: 'system', reason_code: 'bankruptcy_or_overdue', decided_at: minutesAgo(2 * DAY) },
      },
      history: [...pipeline(2 * DAY + 30, 2 * DAY + 4), h('SCORING', 'REJECTED', 'system', 2 * DAY)],
      offers: [],
    },
    {
      // ООО «Мираж»: грейд D (37 баллов) — ждёт специалиста (R7).
      detail: {
        ...base,
        ...applicantOf('mirage@demo.local'),
        id: 'a-1063',
        number: '1063',
        product_id: PRODUCT_IDS.EXPRESS_WC,
        amount: '3000000.00',
        term_months: 24,
        purpose: 'working_capital',
        revenue_12m: '9500000.00',
        existing_payments_monthly: '120000.00',
        status: 'MANUAL_REVIEW',
        status_changed_at: minutesAgo(50 * MIN),
        submitted_at: minutesAgo(54 * MIN),
      },
      history: [...pipeline(3 * HOUR, 54 * MIN), h('SCORING', 'MANUAL_REVIEW', 'system', 50 * MIN)],
      offers: [],
    },
    {
      // ООО «Сбой-Тест»: БКИ не ответило после 2 повторов — ждёт специалиста (R3).
      detail: {
        ...base,
        ...applicantOf('sboy@demo.local'),
        id: 'a-1066',
        number: '1066',
        product_id: PRODUCT_IDS.OVERDRAFT,
        amount: '1200000.00',
        term_months: 12,
        purpose: 'cash_gap',
        revenue_12m: '18000000.00',
        existing_payments_monthly: '0.00',
        status: 'MANUAL_REVIEW',
        status_changed_at: minutesAgo(25 * MIN),
        submitted_at: minutesAgo(29 * MIN),
      },
      history: [...pipeline(1 * HOUR, 29 * MIN), h('SCORING', 'MANUAL_REVIEW', 'system', 25 * MIN)],
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
