import type {
  ApplicationStatus,
  DocumentKind,
  InfoRequest,
  LoanPurpose,
  RejectReason,
  StatusActor,
} from '../api/types';

// Все тексты интерфейса. Для главной (C2) здесь же словарь
// «статус → блок, этап, бейдж, что дальше, кнопка»: карточка заявки
// собирается из него без условий в разметке.

export type HomeBlock = 'action' | 'bank' | 'done';
export type Stage = 'application' | 'check' | 'decision' | 'signing' | 'issue';
export type StageState = 'active' | 'complete' | 'failed';
export type BadgeTone = 'action' | 'progress' | 'success' | 'danger' | 'neutral';
export type Screen = 'C4' | 'C5' | 'C6' | 'C7';

export interface StatusUi {
  block: HomeBlock;
  stage: Stage | null;
  stageState: StageState;
  badge: string;
  tone: BadgeTone;
  next: (app: { info_request?: InfoRequest | null }) => string;
  cta: { label: string; screen: Screen };
}

export const STAGES: Stage[] = ['application', 'check', 'decision', 'signing', 'issue'];

export const STAGE_LABELS: Record<Stage, string> = {
  application: 'Заявка',
  check: 'Проверка',
  decision: 'Решение',
  signing: 'Подписание',
  issue: 'Выдача',
};

const open = { label: 'Открыть', screen: 'C5' } as const;

export const STATUS_UI: Record<ApplicationStatus, StatusUi> = {
  DRAFT: {
    block: 'action',
    stage: 'application',
    stageState: 'active',
    badge: 'Черновик',
    tone: 'action',
    next: () => 'Заполните заявку до конца и отправьте',
    cta: { label: 'Продолжить', screen: 'C4' },
  },
  INFO_REQUESTED: {
    block: 'action',
    stage: 'decision',
    stageState: 'active',
    badge: 'Нужны документы',
    tone: 'action',
    next: (app) => {
      const items = (app.info_request?.items ?? []).filter((item) => item.required);
      return items.length > 0
        ? `Банку нужны документы: ${items.map((item) => item.title).join(', ')}`
        : 'Банку нужны документы';
    },
    cta: { label: 'Загрузить', screen: 'C5' },
  },
  APPROVED: {
    block: 'action',
    stage: 'decision',
    stageState: 'active',
    badge: 'Одобрено',
    tone: 'success',
    next: () => 'Заявка одобрена — посмотрите предложение',
    cta: { label: 'Посмотреть предложение', screen: 'C5' },
  },
  COUNTER_OFFER: {
    block: 'action',
    stage: 'decision',
    stageState: 'active',
    badge: 'Другие условия',
    tone: 'action',
    next: () => 'Одобрено на других условиях — сравните с запрошенными',
    cta: { label: 'Сравнить условия', screen: 'C5' },
  },
  SIGNING: {
    block: 'action',
    stage: 'signing',
    stageState: 'active',
    badge: 'Подписание',
    tone: 'action',
    next: () => 'Подпишите документы',
    cta: { label: 'Подписать', screen: 'C6' },
  },
  SUBMITTED: {
    block: 'bank',
    stage: 'check',
    stageState: 'active',
    badge: 'Проверка',
    tone: 'progress',
    next: () => 'Проверяем данные о компании',
    cta: open,
  },
  ENRICHMENT: {
    block: 'bank',
    stage: 'check',
    stageState: 'active',
    badge: 'Проверка',
    tone: 'progress',
    next: () => 'Проверяем данные о компании',
    cta: open,
  },
  SCORING: {
    block: 'bank',
    stage: 'check',
    stageState: 'active',
    badge: 'Оцениваем',
    tone: 'progress',
    next: () => 'Оцениваем заявку',
    cta: open,
  },
  MANUAL_REVIEW: {
    block: 'bank',
    stage: 'decision',
    stageState: 'active',
    badge: 'У специалиста',
    tone: 'progress',
    next: () => 'Заявку смотрит специалист',
    cta: open,
  },
  SIGNED: {
    block: 'bank',
    stage: 'issue',
    stageState: 'active',
    badge: 'Готовим выдачу',
    tone: 'progress',
    next: () => 'Готовим выдачу средств',
    cta: open,
  },
  ISSUED: {
    block: 'done',
    stage: 'issue',
    stageState: 'complete',
    badge: 'Выдан',
    tone: 'success',
    next: () => 'Деньги зачислены',
    cta: { label: 'График платежей', screen: 'C7' },
  },
  REJECTED: {
    block: 'done',
    stage: 'decision',
    stageState: 'failed',
    badge: 'Отказ',
    tone: 'danger',
    next: () => 'Банк отказал — мы объясним почему',
    cta: { label: 'Узнать причину', screen: 'C5' },
  },
  DECLINED_BY_CLIENT: {
    block: 'done',
    stage: null,
    stageState: 'active',
    badge: 'Вы отказались',
    tone: 'neutral',
    next: () => 'Вы отказались от предложения',
    cta: open,
  },
  CANCELLED: {
    block: 'done',
    stage: null,
    stageState: 'active',
    badge: 'Отозвана',
    tone: 'neutral',
    next: () => 'Вы отозвали заявку',
    cta: open,
  },
};

export const HOME = {
  greeting: (hour: number, name: string) => {
    const part =
      hour >= 5 && hour < 12
        ? 'Доброе утро'
        : hour >= 12 && hour < 18
          ? 'Добрый день'
          : hour >= 18 && hour < 23
            ? 'Добрый вечер'
            : 'Доброй ночи';
    return name ? `${part}, ${name}` : part;
  },
  /** Строка под приветствием: главное, что происходит с заявками. */
  summary: (action: number, bank: number) => {
    if (action > 0) {
      return `${action} ${plural(action, 'заявка ждёт', 'заявки ждут', 'заявок ждут')} вашего действия`;
    }
    if (bank > 0) return 'Банк работает над заявкой — статус обновится сам';
    return 'Подберём кредит под задачу вашего бизнеса';
  },
  stats: {
    action: 'Ждут вас',
    bank: 'В работе',
    done: 'Завершены',
  } satisfies Record<HomeBlock, string>,
  blocks: {
    action: 'Нужно ваше действие',
    bank: 'В работе у банка',
    done: 'Завершённые',
  } satisfies Record<HomeBlock, string>,
  liveLabel: 'обновляется сам',
  cardEyebrow: (number: string) => `Заявка №${number}`,
  nextLabel: 'Что дальше',
  bankHint: 'Ничего делать не нужно.',
  statusChanged: (ago: string) => `Обновлено ${ago}`,
  pickCredit: 'Подобрать кредит',
  empty: {
    eyebrow: 'Заявок пока нет',
    title: 'Подберём кредит под вашу задачу',
    text: 'Расскажите, на что нужны деньги, — покажем подходящие продукты и примерный платёж.',
  },
  loading: 'Загружаем заявки',
  loadError: 'Не удалось загрузить заявки',
  retry: 'Повторить',
};

export const FEED = {
  title: 'Лента',
  caption: 'под ваш бизнес',
  kind: { event: 'Заявка', news: 'Новость' },
  reasonLabel: 'Почему вы это видите',
  all: 'Вся лента',
  empty: 'Пока здесь пусто',
  loadError: 'Не удалось загрузить ленту',
  unread: 'Новое',
};

export const HEADER = {
  product: 'Кредитный кабинет',
  inn: 'ИНН',
  logout: 'Выйти',
  surface: {
    label: 'Оформление',
    pearl: 'Жемчуг',
    graphite: 'Графит',
  },
};

export const COMING_SOON = {
  title: (code: string) => `Экран ${code} в разработке`,
  text: 'Здесь скоро будет следующий шаг. Пока вернитесь на главную.',
  back: 'На главную',
};

export const TIME = {
  justNow: 'только что',
  minutes: (n: number) => `${n} мин назад`,
  hours: (n: number) => `${n} ч назад`,
  yesterday: 'вчера',
  days: (n: number) => `${n} ${plural(n, 'день', 'дня', 'дней')} назад`,
};

export const MONEY = {
  term: (months: number) => `${months} мес`,
  noAmount: 'Сумма не указана',
  noTerm: 'срок не указан',
  noProduct: 'Продукт не выбран',
};

export function plural(n: number, one: string, few: string, many: string): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}

// ── C5: карточка заявки ─────────────────────────────────────────────────────

export const APPLICATION = {
  back: 'Все заявки',
  eyebrow: (number: string, product: string) => `Заявка №${number} · ${product}`,
  title: {
    DRAFT: 'Черновик заявки',
    SUBMITTED: 'Заявка отправлена',
    ENRICHMENT: 'Проверяем данные',
    SCORING: 'Оцениваем заявку',
    MANUAL_REVIEW: 'Заявку смотрит специалист',
    INFO_REQUESTED: 'Нужны документы',
    APPROVED: 'Заявка одобрена',
    COUNTER_OFFER: 'Одобрено на других условиях',
    REJECTED: 'Банк отказал',
    SIGNING: 'Осталось подписать',
    SIGNED: 'Готовим выдачу',
    ISSUED: 'Деньги зачислены',
    DECLINED_BY_CLIENT: 'Вы отказались от предложения',
    CANCELLED: 'Заявка отозвана',
  } satisfies Record<ApplicationStatus, string>,
  subtitle: {
    DRAFT: 'Заполните заявку до конца и отправьте — решение придёт сюда же.',
    SUBMITTED: 'Заявка в банке. Ничего делать не нужно — статус обновится сам.',
    ENRICHMENT: 'Сверяем данные о компании с реестрами. Ничего делать не нужно.',
    SCORING: 'Оцениваем заявку по данным реестров и бюро кредитных историй. Это пара минут.',
    MANUAL_REVIEW: 'Кредитный специалист изучает заявку. Обычно это до одного рабочего дня.',
    INFO_REQUESTED: 'Загрузите документы из списка ниже — и мы продолжим рассмотрение.',
    APPROVED: 'Посмотрите условия и график платежей. Если всё подходит — примите предложение.',
    COUNTER_OFFER: 'Мы не смогли одобрить запрошенные условия, но можем предложить другие.',
    REJECTED: 'Объясняем, почему так вышло и что можно сделать.',
    SIGNING: 'Предложение принято. Подпишите документы, и мы перечислим деньги.',
    SIGNED: 'Документы подписаны. Перечисляем деньги на счёт компании.',
    ISSUED: 'Кредит выдан. График платежей всегда под рукой.',
    DECLINED_BY_CLIENT: 'Предложение больше не действует. Можно подобрать другой кредит.',
    CANCELLED: 'Заявка закрыта. Подать новую можно в любой момент.',
  } satisfies Record<ApplicationStatus, string>,
  progress: {
    eyebrow: 'Где заявка сейчас',
    live: 'обновляется сам',
  },
  details: {
    title: 'Ваша заявка',
    product: 'Продукт',
    amount: 'Сумма',
    term: 'Срок',
    purpose: 'Цель',
    revenue: 'Выручка за 12 мес',
    submitted: 'Отправлена',
  },
  purpose: {
    working_capital: 'Оборотные средства',
    equipment: 'Покупка оборудования',
    cash_gap: 'Кассовый разрыв',
  } satisfies Record<LoanPurpose, string>,
  history: {
    title: 'История',
    status: {
      DRAFT: 'Создан черновик',
      SUBMITTED: 'Заявка отправлена',
      ENRICHMENT: 'Проверяем данные о компании',
      SCORING: 'Оцениваем заявку',
      MANUAL_REVIEW: 'Передали специалисту',
      INFO_REQUESTED: 'Банк запросил документы',
      APPROVED: 'Заявка одобрена',
      COUNTER_OFFER: 'Одобрено на других условиях',
      REJECTED: 'Отказ',
      SIGNING: 'Предложение принято',
      SIGNED: 'Документы подписаны',
      ISSUED: 'Деньги зачислены',
      DECLINED_BY_CLIENT: 'Вы отказались от предложения',
      CANCELLED: 'Заявка отозвана',
    } satisfies Record<ApplicationStatus, string>,
    actor: {
      client: 'Вы',
      system: 'Автоматически',
      underwriter: 'Специалист банка',
    } satisfies Record<StatusActor, string>,
  },
  waiting: {
    eyebrow: 'Что происходит',
    steps: [
      { title: 'Сверяем данные с ЕГРЮЛ и ЕГРИП', doneAfter: 'ENRICHMENT' },
      { title: 'Проверяем налоги и кредитную историю', doneAfter: 'SCORING' },
      { title: 'Оцениваем заявку и готовим решение', doneAfter: 'DECIDED' },
    ],
    hint: 'Статус обновится сам — можно закрыть страницу, решение придёт в ленту.',
  },
  review: {
    eyebrow: 'Ручное рассмотрение',
    text: 'Заявка нестандартная, поэтому решение примет специалист. Если ему понадобятся документы, запрос появится здесь и в ленте.',
  },
  offer: {
    eyebrow: 'Предложение банка',
    approvedTitle: 'Одобрено на ваших условиях',
    counterTitle: 'Предлагаем другие условия',
    requested: 'Просили',
    offered: 'Предлагаем',
    product: 'Продукт',
    amount: 'Сумма',
    term: 'Срок',
    rate: 'Ставка',
    payment: 'Платёж в месяц',
    overpayment: 'Переплата',
    total: 'Всего выплат',
    unknown: '—',
    accept: 'Принять предложение',
    decline: 'Отказаться',
    declineQuestion: 'Отказаться от предложения?',
    declineConfirm: 'Да, отказаться',
    keep: 'Нет',
    decidedBy: (by: 'system' | 'underwriter', date: string) =>
      `${by === 'system' ? 'Решение принято автоматически' : 'Решение принял специалист'} · ${date}`,
  },
  schedule: {
    title: 'График платежей',
    columns: {
      number: '№',
      date: 'Дата',
      payment: 'Платёж',
      principal: 'Долг',
      interest: 'Проценты',
      balance: 'Остаток',
    },
    showAll: (count: number) => `Показать весь график — ${count} ${plural(count, 'платёж', 'платежа', 'платежей')}`,
    collapse: 'Свернуть',
    loadError: 'Не удалось загрузить график',
  },
  documents: {
    eyebrow: 'Запрос банка',
    title: 'Загрузите документы',
    required: 'обязательно',
    optional: 'по желанию',
    uploaded: 'загружен',
    drop: 'Перетащите файл или выберите',
    hint: 'PDF, JPG или PNG до 10 МБ',
    uploading: 'Загружаем…',
    tooLarge: 'Файл больше 10 МБ — сожмите его или загрузите по частям.',
    wrongType: 'Подходят только PDF, JPG и PNG.',
    send: 'Отправить в банк',
    sendHint: 'Загрузите обязательные документы — и кнопка станет активной.',
    cancel: 'Отозвать заявку',
    cancelQuestion: 'Отозвать заявку?',
    cancelConfirm: 'Да, отозвать',
    keep: 'Нет',
  },
  documentKind: {
    tax_return: 'Налоговая декларация',
    bank_statement: 'Выписка по счёту',
    financial_statements: 'Бухгалтерская отчётность',
    contract: 'Договор',
    other: 'Другой документ',
  } satisfies Record<DocumentKind, string>,
  rejection: {
    eyebrow: 'Решение банка',
    whatToDo: 'Что можно сделать',
    pick: 'Подобрать другой кредит',
    reasons: {
      company_inactive: {
        title: 'Компания не действует по данным реестра',
        text: 'По данным ЕГРЮЛ или ЕГРИП компания ликвидирована или ликвидируется. Такой компании банк не может выдать кредит.',
        steps: [
          'Проверьте выписку из ЕГРЮЛ на сайте ФНС',
          'Если данные устарели, обратитесь в налоговую за исправлением',
          'После исправления подайте заявку заново',
        ],
      },
      bankruptcy_or_overdue: {
        title: 'Есть банкротство или серьёзная просрочка',
        text: 'По данным бюро кредитных историй у компании идёт банкротство или есть текущая просрочка больше 90 дней.',
        steps: [
          'Погасите текущую просрочку',
          'Запросите свою кредитную историю и проверьте, что данные верны',
          'Подайте заявку снова после погашения',
        ],
      },
      low_score: {
        title: 'Сейчас мы не можем одобрить кредит',
        text: 'По совокупности данных — возраст бизнеса, кредитная история, налоги и выручка — риск оказался слишком высоким.',
        steps: [
          'Попробуйте меньшую сумму',
          'Погасите налоговую задолженность, если она есть',
          'Подайте заявку снова, когда появится новая отчётность',
        ],
      },
      no_suitable_terms: {
        title: 'Платёж слишком большой для бизнеса',
        text: 'Мы пробовали увеличить срок, уменьшить сумму и подобрать другой продукт, но платёж всё равно выше безопасной нагрузки — больше 35% от среднемесячной выручки.',
        steps: [
          'Попробуйте меньшую сумму или более длинный срок',
          'Погасите часть текущих кредитов — нагрузка снизится',
          'Подайте заявку снова, когда выручка вырастет',
        ],
      },
      underwriter_decision: {
        title: 'Специалист не смог одобрить кредит',
        text: 'Кредитный специалист изучил заявку и документы и принял решение об отказе.',
        steps: ['Подберите другой продукт или сумму', 'Подайте заявку снова, когда появится новая отчётность'],
      },
    } satisfies Record<RejectReason, { title: string; text: string; steps: string[] }>,
    fallback: {
      title: 'Банк не одобрил заявку',
      text: 'Мы не смогли одобрить кредит на этих условиях.',
      steps: ['Подберите другой продукт или сумму'],
    },
  },
  final: {
    draft: 'Продолжить заполнение',
    sign: 'Перейти к подписанию',
    schedule: 'График платежей',
    pick: 'Подобрать кредит',
    signedText: 'Обычно деньги приходят в течение нескольких минут.',
  },
  notFound: {
    title: 'Заявка не найдена',
    text: 'Возможно, ссылка устарела или заявка принадлежит другой компании.',
  },
  loadError: 'Не удалось загрузить заявку',
  actionError: 'Не получилось — попробуйте ещё раз',
};
