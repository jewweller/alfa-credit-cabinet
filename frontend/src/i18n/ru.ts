import type {
  ApplicationStatus,
  AuditAction,
  AuditActorRole,
  CompanyRegistryStatus,
  DocumentKind,
  EnrichmentSource,
  FeedItemKind,
  FeedRanking,
  Grade,
  InfoRequest,
  LoanPurpose,
  RecommendationAdjustment,
  RejectReason,
  StatusActor,
  UnderwriterOutcome,
  UserRole,
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
  retry: 'Повторить',
  markRead: 'Отметить прочитанным',
  page: {
    eyebrow: 'Лента',
    title: 'События и новости',
    subtitle: 'Что происходит с вашими заявками и что полезно вашему бизнесу. Уведомления приходят сюда — без писем и SMS.',
    back: 'На главную',
    filter: 'Что показать',
    filters: { all: 'Всё', event: 'Заявки', news: 'Новости' } as Record<FeedFilter, string>,
    panel: { all: 'Всё по порядку', event: 'События по заявкам', news: 'Новости по вашему профилю' } as Record<FeedFilter, string>,
    caption: { all: 'сначала заявки', event: 'свежие первыми', news: 'самые подходящие первыми' } as Record<FeedFilter, string>,
    empty: {
      all: 'Пока здесь пусто',
      event: 'Событий пока нет — они появятся, когда вы отправите заявку',
      news: 'Новостей под ваш профиль пока нет',
    } as Record<FeedFilter, string>,
    stats: { unread: 'новых событий', news: 'новостей подобрано' },
  },
  how: {
    eyebrow: 'Прозрачно',
    title: 'Как подбираются новости',
    text: 'Новости — из каталога банка. Каждую мы сверяем с профилем компании и заявками и складываем совпадения:',
    weights: [
      { label: 'Отрасль по ОКВЭД', value: '+3' },
      { label: 'Шаг, на котором сейчас заявка', value: '+3' },
      { label: 'Продукт из вашей заявки', value: '+2' },
      { label: 'Сегмент: микро или малый бизнес', value: '+2' },
      { label: 'Свежесть: за 30 дней падает до нуля', value: 'до +1' },
    ],
    filters: 'Заметки для другой отрасли и подсказки к чужому шагу мы не показываем вовсе.',
    noBki: 'Данные кредитной истории для подбора не используются.',
    ml: 'Порядок предложила модель; если она не ответит вовремя, сработают правила выше.',
    version: (method: FeedRanking['method'], v: string) => `Подбор ${method === 'ml' ? 'моделью' : 'по правилам'} · ${v}`,
  },
};

export type FeedFilter = 'all' | FeedItemKind;

export const HEADER = {
  product: 'Кредитный кабинет',
  inn: 'ИНН',
  bank: 'Альфа-Банк',
  role: {
    client: 'Клиент',
    underwriter: 'Кредитный специалист',
    admin: 'Администратор',
  } satisfies Record<UserRole, string>,
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

// ── C1: вход ────────────────────────────────────────────────────────────────

export const LOGIN = {
  eyebrow: 'Кредитный кабинет для бизнеса',
  title: 'Кредит для бизнеса — от заявки до денег в одном окне',
  subtitle: 'Подберите продукт, подайте заявку и следите за решением банка. Без звонков и визитов в офис.',
  points: ['Данные о компании по ИНН найдём в реестре сами', 'Статус заявки обновляется автоматически', 'Решение с понятным объяснением'],
  formEyebrow: 'Вход',
  formTitle: 'Войдите в кабинет',
  email: 'Email',
  password: 'Пароль',
  submit: 'Войти',
  submitting: 'Входим…',
  required: 'Заполните email и пароль',
  wrong: 'Неверный email или пароль',
  failed: 'Не получилось войти — попробуйте ещё раз',
  demo: {
    eyebrow: 'Демо-стенд',
    title: 'Тестовые учётки',
    hint: 'Нажмите на учётку — поля заполнятся сами. Пароль у всех: Demo2026!',
    password: 'Demo2026!',
    accounts: [
      { email: 'bakery@demo.local', name: 'ООО «Пекарня Север»', scenario: 'Одобрение, подписание, выдача' },
      { email: 'kovalev@demo.local', name: 'ИП Ковалёв', scenario: 'Другие условия' },
      { email: 'stroy@demo.local', name: 'ООО «СтройРесурс»', scenario: 'Отказ' },
      { email: 'melnikova@demo.local', name: 'ИП Мельникова', scenario: 'Запрос документов' },
      { email: 'underwriter@demo.local', name: 'Кредитный специалист', scenario: 'Очередь и ручное решение' },
      { email: 'admin@demo.local', name: 'Администратор', scenario: 'Сброс данных, аудит' },
    ],
  },
};

// ── C3: подбор продукта ─────────────────────────────────────────────────────

export const PICK = {
  back: 'Все заявки',
  eyebrow: 'Подбор кредита',
  title: 'На что нужны деньги?',
  subtitle: 'Расскажите о задаче — покажем подходящие продукты и примерный платёж.',
  formEyebrow: 'Ваша задача',
  purposeLabel: 'Цель',
  purposeHint: {
    working_capital: 'Закупка сырья и товаров, зарплаты, аренда',
    equipment: 'Станки, печи, транспорт, линии производства',
    cash_gap: 'Покупатели платят позже, чем нужно платить вам',
  } satisfies Record<LoanPurpose, string>,
  amount: 'Сумма',
  term: 'Срок',
  termSuffix: 'мес',
  amountRequired: 'Укажите сумму',
  termRequired: 'Укажите срок',
  resultsEyebrow: 'Подходящие продукты',
  resultsHint: 'Платёж примерный — по базовой ставке. Точные условия банк назовёт после проверки заявки.',
  choosePurpose: 'Выберите цель — и мы покажем, что подходит.',
  fillParams: 'Укажите сумму и срок — посчитаем платёж.',
  noResults: 'Под эту цель продуктов пока нет',
  noResultsText: 'Попробуйте другую цель — например, оборотные средства.',
  loading: 'Подбираем продукты',
  loadError: 'Не получилось подобрать продукты',
  bestBadge: 'Лучший вариант',
  fitsBadge: 'Подходит',
  adjustedBadge: 'Другие условия',
  perMonth: 'в месяц',
  rateFrom: (rate: string) => `от ${rate}`,
  whyTitle: 'Почему подходит',
  why: {
    purpose: (purpose: string) => `Создан для цели «${purpose.toLowerCase()}»`,
    amountFits: (min: string, max: string) => `Сумма в пределах продукта: ${min} — ${max}`,
    termFits: (min: number, max: number) =>
      min === max ? `Срок продукта — ${min} мес` : `Срок в пределах продукта: ${min}–${max} мес`,
  },
  adjusted: {
    amount: (amount: string) => `Посчитали на ${amount} — это ближайшая сумма, которую даёт продукт`,
    term_months: (term: number) => `Посчитали на ${term} мес — это ближайший срок для продукта`,
  } satisfies Record<RecommendationAdjustment, unknown>,
  apply: 'Оформить заявку',
  creating: 'Создаём черновик…',
  createError: 'Не получилось создать заявку — попробуйте ещё раз',
  next: {
    eyebrow: 'Что будет дальше',
    steps: [
      'Заполните заявку — данные о компании подтянем из реестра',
      'Банк проверит данные и оценит заявку за пару минут',
      'Решение придёт в кабинет и в ленту',
    ],
  },
};

// ── C4: мастер заявки ───────────────────────────────────────────────────────

export type WizardStep = 'company' | 'params' | 'finance' | 'review';

export const WIZARD = {
  back: 'Все заявки',
  eyebrow: (number: string) => `Заявка №${number} · черновик`,
  title: 'Заявка на кредит',
  steps: {
    company: 'Компания',
    params: 'Условия',
    finance: 'Финансы',
    review: 'Проверка',
  } satisfies Record<WizardStep, string>,
  subtitle: {
    company: 'Данные о компании берём из реестра — вводить их не нужно.',
    params: 'Сколько, на какой срок и на что нужны деньги.',
    finance: 'Две цифры о бизнесе — по ним банк оценит нагрузку.',
    review: 'Проверьте заявку и отправьте в банк.',
  } satisfies Record<WizardStep, string>,
  stepLabel: (n: number, total: number) => `Шаг ${n} из ${total}`,
  nextStep: 'Далее',
  prevStep: 'Назад',
  save: {
    saving: 'Сохраняем…',
    saved: (ago: string) => `Черновик сохранён · ${ago}`,
    error: 'Не удалось сохранить — повторим при следующем изменении',
    conflict: 'Заявку изменили в другой вкладке — показываем свежие данные',
  },
  company: {
    eyebrow: 'Данные из реестра',
    sourceLLC: 'Источник: ЕГРЮЛ · только чтение',
    sourceIE: 'Источник: ЕГРИП · только чтение',
    name: 'Наименование',
    nameIE: 'Предприниматель',
    inn: 'ИНН',
    ogrn: 'ОГРН',
    ogrnip: 'ОГРНИП',
    status: 'Статус',
    registered: 'Зарегистрирована',
    registeredIE: 'Зарегистрирован',
    okved: 'Основной ОКВЭД',
    region: 'Регион',
    address: 'Адрес',
    director: 'Руководитель',
    registryStatus: {
      ACTIVE: 'Действующая',
      LIQUIDATING: 'В процессе ликвидации',
      LIQUIDATED: 'Ликвидирована',
    } satisfies Record<CompanyRegistryStatus, string>,
    inactive:
      'По данным реестра компания не действует. Заявку отправить можно, но банк не сможет выдать кредит такой компании.',
    readOnly: 'Если данные неверны, их исправляют в налоговой — после этого они обновятся здесь сами.',
    loading: 'Запрашиваем реестр',
    notFound: 'Компания не найдена в реестре',
    notFoundText: 'Проверьте ИНН в профиле. Если он верный, реестр мог ещё не обновиться — попробуйте открыть заявку позже.',
    unavailable: 'Реестр сейчас не отвечает',
    unavailableText: 'Можно продолжить заполнение — данные подтянем, когда реестр заработает.',
  },
  params: {
    eyebrow: 'Условия кредита',
    product: 'Продукт',
    purpose: 'Цель',
    amount: 'Сумма',
    term: 'Срок',
    termSuffix: 'мес',
    limitsAmount: (min: string, max: string) => `От ${min} до ${max}`,
    limitsTerm: (min: number, max: number) => (min === max ? `Только ${min} мес` : `От ${min} до ${max} мес`),
    productRate: (rate: string) => `ставка от ${rate}`,
    payment: 'Примерный платёж',
    paymentHint: 'по базовой ставке продукта',
    purposeMismatch: 'Этот продукт обычно берут на другие цели — банк может предложить другие условия.',
  },
  finance: {
    eyebrow: 'Финансы бизнеса',
    revenue: 'Выручка за последние 12 месяцев',
    revenueHint: 'Как в налоговой декларации — банк сверит с данными ФНС.',
    payments: 'Платежи по текущим кредитам в месяц',
    paymentsHint: 'Если кредитов нет, поставьте 0.',
    loadTitle: 'Нагрузка на бизнес',
    threshold: 'порог 35%',
    loadOk: 'Столько среднемесячной выручки уйдёт на все кредиты вместе с новым. До 35% банк обычно одобряет.',
    loadHigh: 'Больше 35% выручки уйдёт на кредиты — банк может предложить срок длиннее или сумму меньше.',
  },
  review: {
    eyebrow: 'Проверка',
    company: 'Компания',
    params: 'Условия',
    finance: 'Финансы',
    edit: 'Изменить',
    consent: 'Согласен(на) на запрос кредитной истории в бюро кредитных историй',
    consentHint: 'Без согласия банк не сможет оценить заявку. Запрос не влияет на кредитный рейтинг.',
    submit: 'Отправить в банк',
    submitting: 'Отправляем…',
    submitHint: 'После отправки изменить заявку будет нельзя. Решение придёт за пару минут.',
    submitError: 'Не получилось отправить — попробуйте ещё раз',
    incomplete: 'Заявка заполнена не до конца. Исправьте отмеченные поля — кнопка «Изменить» откроет нужный шаг.',
    cancel: 'Отозвать заявку',
    cancelQuestion: 'Отозвать заявку?',
    cancelConfirm: 'Да, отозвать',
    keep: 'Нет',
  },
  validation: {
    product: 'Выберите продукт',
    purpose: 'Выберите цель',
    amount: 'Укажите сумму',
    amountRange: (min: string, max: string) => `Сумма для этого продукта — от ${min} до ${max}`,
    term: 'Укажите срок',
    termRange: (min: number, max: number) => `Срок для этого продукта — от ${min} до ${max} мес`,
    revenue: 'Укажите выручку',
    payments: 'Укажите платежи — или 0, если кредитов нет',
    consent: 'Нужно согласие на запрос кредитной истории',
    fixBefore: 'Исправьте отмеченные поля',
  },
  empty: '—',
};

// ── C6: подписание ──────────────────────────────────────────────────────────

export const SIGNING = {
  back: 'К заявке',
  eyebrow: (number: string) => `Заявка №${number} · подписание`,
  title: 'Подписание договора',
  subtitle: 'Проверьте условия и подпишите договор кодом. Это симуляция простой электронной подписи.',
  contract: {
    eyebrow: (number: string) => `Договор № ${number}-К`,
    title: 'Договор кредита',
    parties: (company: string, inn: string, person: string) =>
      `Банк (кредитор) и ${company}, ИНН ${inn} (заёмщик), заключили договор на условиях ниже. Подписант от заёмщика — ${person}.`,
    product: 'Продукт',
    amount: 'Сумма кредита',
    term: 'Срок',
    rate: 'Ставка',
    payment: 'Ежемесячный платёж',
    purpose: 'Цель',
    clauses: (t: { amount: string; term: string; purpose: string; rate: string; payment: string; account: string }) => [
      {
        title: 'Предмет договора',
        text: `Банк предоставляет заёмщику кредит ${t.amount} на срок ${t.term}. Цель — ${t.purpose.toLowerCase()}.`,
      },
      {
        title: 'Проценты',
        text: `Ставка — ${t.rate}. Проценты начисляются ежедневно на остаток долга.`,
      },
      {
        title: 'Погашение',
        text: `Ежемесячно равными платежами по ${t.payment} по графику. Первый платёж — через месяц после выдачи.`,
      },
      {
        title: 'Выдача',
        text: `После подписания деньги зачисляются на счёт заёмщика ${t.account}.`,
      },
      {
        title: 'Досрочное погашение',
        text: 'Полностью или частично, без комиссии. Заявление подаётся в кредитном кабинете.',
      },
      {
        title: 'Уведомления',
        text: 'Стороны обмениваются уведомлениями в кредитном кабинете — в ленте событий.',
      },
      {
        title: 'Подписание',
        text: 'Договор подписывается простой электронной подписью — одноразовым кодом в кабинете.',
      },
    ],
    note: 'Текст синтетический, для демонстрации. Подписывая, вы соглашаетесь с условиями договора.',
  },
  sign: {
    eyebrow: 'Симуляция ПЭП',
    title: 'Подпишите договор',
    get: 'Получить код',
    again: 'Получить новый код',
    getting: 'Готовим код…',
    codeLabel: 'Код подписи',
    codeShown: 'Код для демо показан здесь — введите его ниже:',
    expires: (time: string) => `Действует до ${time}`,
    hint: 'На реальном продукте код пришёл бы по вашему каналу подтверждения. На демо показываем его на экране.',
    input: 'Введите код',
    confirm: 'Подписать',
    confirming: 'Подписываем…',
    wrong: 'Код неверный или истёк. Получите новый и попробуйте снова.',
    error: 'Не получилось подписать — попробуйте ещё раз.',
    needCode: 'Сначала получите код.',
  },
};

// ── C7: итог выдачи ─────────────────────────────────────────────────────────

export const RESULT = {
  back: 'К заявке',
  eyebrow: (number: string) => `Заявка №${number} · выдача`,
  title: 'Деньги зачислены',
  subtitle: 'Кредит выдан. График платежей всегда под рукой.',
  waiting: {
    title: 'Перечисляем деньги на счёт',
    text: 'Договор подписан. Обычно деньги приходят в течение нескольких минут — статус обновится сам.',
  },
  issued: {
    eyebrow: 'Средства зачислены',
    account: 'Счёт зачисления',
    accountNumber: '**** 4521',
    amount: 'Сумма',
    product: 'Продукт',
    rate: 'Ставка',
    term: 'Срок',
    first: 'Первый платёж',
    done: 'Готово',
    home: 'На главную',
  },
};

// ── B2–B4: кабинет банка ───────────────────────────────────────────────────

/** Статус глазами сотрудника банка: короче и точнее, чем клиенту. */
export const BANK_STATUS: Record<ApplicationStatus, { label: string; tone: BadgeTone }> = {
  DRAFT: { label: 'Черновик', tone: 'neutral' },
  SUBMITTED: { label: 'Отправлена', tone: 'progress' },
  ENRICHMENT: { label: 'Обогащение', tone: 'progress' },
  SCORING: { label: 'Скоринг', tone: 'progress' },
  MANUAL_REVIEW: { label: 'Ждёт специалиста', tone: 'action' },
  INFO_REQUESTED: { label: 'Ждём документы', tone: 'neutral' },
  APPROVED: { label: 'Одобрена', tone: 'success' },
  COUNTER_OFFER: { label: 'Другие условия', tone: 'success' },
  REJECTED: { label: 'Отказ', tone: 'danger' },
  SIGNING: { label: 'Подписание', tone: 'progress' },
  SIGNED: { label: 'Подписана', tone: 'progress' },
  ISSUED: { label: 'Выдан', tone: 'success' },
  DECLINED_BY_CLIENT: { label: 'Клиент отказался', tone: 'neutral' },
  CANCELLED: { label: 'Отозвана', tone: 'neutral' },
};

export type QueueGroup = 'all' | 'review' | 'pipeline' | 'client' | 'closed';

export const BANK = {
  eyebrow: 'Кабинет банка',
  queue: {
    title: 'Очередь заявок',
    subtitle: 'Сверху — заявки, которые ждут решения специалиста. Остальные конвейер ведёт сам.',
    stats: { review: 'Ждут специалиста', mine: 'В работе у вас', total: 'Всего заявок' },
    filters: { group: 'Статус', grade: 'Грейд', product: 'Продукт' },
    group: {
      all: 'Все',
      review: 'Ждут решения',
      pipeline: 'В конвейере',
      client: 'У клиента',
      closed: 'Завершённые',
    } satisfies Record<QueueGroup, string>,
    groupStatuses: {
      all: [],
      review: ['MANUAL_REVIEW'],
      pipeline: ['SUBMITTED', 'ENRICHMENT', 'SCORING'],
      client: ['INFO_REQUESTED', 'APPROVED', 'COUNTER_OFFER', 'SIGNING', 'SIGNED'],
      closed: ['ISSUED', 'REJECTED', 'DECLINED_BY_CLIENT', 'CANCELLED'],
    } satisfies Record<QueueGroup, ApplicationStatus[]>,
    any: 'Все',
    columns: {
      number: '№',
      company: 'Компания',
      product: 'Продукт',
      amount: 'Сумма',
      grade: 'Грейд',
      status: 'Статус',
      waiting: 'В статусе',
      assignee: 'Ведёт',
    },
    take: 'Взять в работу',
    taking: 'Берём…',
    nobody: '—',
    you: 'Вы',
    live: 'обновляется сама',
    empty: { title: 'Под эти фильтры заявок нет', text: 'Снимите часть фильтров — заявки появятся.' },
    loadError: 'Не получилось загрузить очередь',
  },
  card: {
    back: 'Очередь',
    eyebrow: (number: string, product: string) => `Заявка №${number} · ${product}`,
    subtitle: (inn: string, applicant: string) => `ИНН ${inn} · подал(а) ${applicant}`,
    stats: { amount: 'Сумма', term: 'Срок', score: 'Скоринг' },
    scoreValue: (grade: Grade, score: number) => `${grade} · ${score}`,
    notScored: 'ещё нет',
    take: 'Взять в работу',
    taking: 'Берём…',
    assignedToOther: (name: string) => `Заявку ведёт ${name}`,
    loadError: 'Не получилось загрузить заявку',
    notFound: { title: 'Заявка не найдена', text: 'Возможно, её номер изменился. Вернитесь в очередь.' },
  },
  review: {
    eyebrow: 'Ручное рассмотрение',
    waitTitle: 'Заявка ждёт специалиста',
    waitText: 'Возьмите её в работу, чтобы принять решение. Пока заявка у вас, другой специалист её не возьмёт.',
    why: 'Почему на ручном рассмотрении',
    adminText: 'Решение принимает кредитный специалист. Администратору заявка доступна только для просмотра.',
  },
  decision: {
    eyebrow: 'Решение',
    title: 'Ваше решение',
    outcomeLabel: 'Исход',
    outcomes: {
      approved: { title: 'Одобрить', text: 'На условиях заявки, ставку задаёте вы' },
      counter_offer: { title: 'Другие условия', text: 'Сумма, срок, продукт и ставка' },
      info_requested: { title: 'Запросить документы', text: 'Клиент загрузит их в заявку' },
      rejected: { title: 'Отказать', text: 'С причиной из справочника' },
    } satisfies Record<UnderwriterOutcome, { title: string; text: string }>,
    product: 'Продукт',
    amount: 'Сумма',
    term: 'Срок',
    rate: 'Ставка',
    rateHint: (suggested: string) => `По грейду — ${suggested}`,
    termHint: (min: number, max: number) => `От ${min} до ${max} мес`,
    preview: 'Что получит клиент',
    payment: 'Платёж в месяц',
    loadByForm: 'Нагрузка по анкете',
    loadByFns: 'Нагрузка по выручке ФНС',
    safe: 'Безопасно — до 35%',
    documents: 'Какие документы нужны',
    requiredMark: 'обязательный',
    documentTitles: {
      tax_return: 'Налоговая декларация за 2025 год',
      bank_statement: 'Выписка по расчётному счёту за 6 месяцев',
      financial_statements: 'Бухгалтерская отчётность за 2025 год',
      contract: 'Договор с поставщиком или покупателем',
      other: 'Другой документ — опишите в сообщении',
    } satisfies Record<DocumentKind, string>,
    message: 'Сообщение клиенту',
    messageHint: 'Клиент увидит его в карточке заявки.',
    reason: 'Причина отказа',
    reasons: {
      company_inactive: { title: 'Компания не действующая', text: 'R1 — статус в ЕГРЮЛ/ЕГРИП не «действующая»' },
      bankruptcy_or_overdue: { title: 'Банкротство или просрочка', text: 'R2 — по БКИ банкротство или текущая просрочка больше 90 дней' },
      low_score: { title: 'Высокий риск', text: 'R6 — низкий скоринговый балл' },
      no_suitable_terms: { title: 'Не подобрать условия', text: 'R10 — нагрузка выше 35%, срок и сумма не помогают' },
      underwriter_decision: { title: 'Иное решение специалиста', text: 'Опишите причину во внутреннем комментарии' },
    } satisfies Record<RejectReason, { title: string; text: string }>,
    errors: {
      outcome: 'Выберите исход',
      rate: 'Укажите ставку больше нуля',
      product: 'Выберите продукт',
      amount: (min: string, max: string) => `Сумма — от ${min} до ${max}`,
      term: (min: number, max: number) => `Срок — от ${min} до ${max} мес`,
      documents: 'Отметьте хотя бы один документ',
      message: 'Напишите клиенту, зачем нужны документы',
      reason: 'Выберите причину',
    },
    loadHigh: 'выше 35%',
    comment: 'Внутренний комментарий',
    commentHint: 'Клиент его не видит.',
    submit: 'Принять решение',
    question: 'Отправить решение клиенту?',
    confirm: 'Да, отправить',
    cancel: 'Нет',
    error: 'Не получилось сохранить решение — попробуйте ещё раз.',
  },
  result: {
    eyebrow: 'Решение принято',
    by: (who: string, when: string) => `${who} · ${when}`,
    system: 'Автоматически, движок правил',
    offer: 'Условия',
    reason: 'Причина',
    comment: 'Комментарий',
    requested: 'Запрошено',
    outcomes: {
      approved: 'Одобрено',
      counter_offer: 'Одобрено на других условиях',
      info_requested: 'Запрошены документы',
      rejected: 'Отказ',
      manual_review: 'Передано специалисту',
    },
  },
  scoring: {
    eyebrow: 'Скоринг',
    title: (grade: Grade, score: number) => `Грейд ${grade} · ${score} из 100`,
    pending: 'Скоринг появится после проверки данных о компании.',
    load: 'Долговая нагрузка',
    loadNote: 'По базовой ставке продукта на запрошенных условиях',
    threshold: '35%',
    model: (version: string) => `Модель ${version} · правила плана, раздел 7`,
  },
  rules: {
    eyebrow: 'Движок решения',
    title: 'Правила по порядку',
    fired: 'сработало',
    passed: 'не сработало',
    note: 'Срабатывает первое подходящее правило; дальше проверка не идёт.',
  },
  sources: {
    eyebrow: 'Внешние источники',
    title: 'Что ответили источники',
    pending: 'Данные появятся после этапа обогащения.',
    names: {
      egrul: 'ЕГРЮЛ',
      egrip: 'ЕГРИП',
      fns_tb: 'ФНС «Прозрачный бизнес»',
      bki: 'Бюро кредитных историй',
    } satisfies Record<EnrichmentSource, string>,
    status: { ok: 'ответил', not_found: 'нет данных', error: 'не ответил' },
    attempts: (n: number) => `попыток: ${n}`,
    raw: 'Ответ как есть (JSON)',
    fields: {
      status: 'Статус в реестре',
      registered: 'Зарегистрирована',
      okved: 'Основной ОКВЭД',
      director: 'Руководитель',
      revenue: (year: string) => `Выручка ${year}`,
      taxDebt: 'Налоговый долг',
      employees: 'Сотрудники',
      flags: 'Флаги риска',
      history: 'Кредитная история',
      loans: 'Действующих кредитов',
      payments: 'Платежи в месяц',
      overdue: 'Макс. просрочка за 24 мес',
      inquiries: 'Запросов за 30 дней',
    },
    yes: 'есть',
    no: 'нет',
    days: (n: number) => `${n} дн.`,
  },
  facts: {
    title: 'Анкета',
    product: 'Продукт',
    amount: 'Сумма',
    term: 'Срок',
    purpose: 'Цель',
    revenue: 'Выручка за 12 мес',
    payments: 'Платежи по кредитам',
    consent: 'Согласие на БКИ',
    submitted: 'Отправлена',
    yes: 'дано',
    no: 'нет',
  },
  documents: {
    title: 'Документы',
    empty: 'Клиент пока ничего не загружал.',
    open: 'Открыть',
    download: 'Скачать',
    downloadError: 'Не получилось скачать файл',
    viewer: {
      newTab: 'В новой вкладке',
      close: 'Закрыть',
      loading: 'Загружаем файл…',
      error: (detail: string) => `Не получилось открыть файл (${detail}). Попробуйте скачать его.`,
      unsupported: 'Этот формат браузер не показывает — скачайте файл.',
      pdfError: 'Не получилось показать PDF здесь — откройте его в новой вкладке или скачайте.',
      page: (page: number, total: number) => `Страница ${page} из ${total}`,
    },
  },
};

export type AuditGroup = 'all' | 'auth' | 'client' | 'documents' | 'bank' | 'system';

export const ADMIN = {
  eyebrow: 'Администратор стенда',
  title: 'Администрирование',
  subtitle: 'Сброс демо-данных перед показом и журнал действий всех пользователей.',
  toQueue: 'Очередь заявок',
  toAdmin: 'Администрирование',
  stats: { today: 'Действий сегодня', logins: 'Входов сегодня', decisions: 'Решений специалистов' },
  reset: {
    eyebrow: 'Перед показом',
    title: 'Сброс демо-данных',
    text: 'Удалит все заявки с документами, решениями и подписями. Учётки, компании и продукты останутся. Журнал не очищается — в него запишется сам сброс.',
    button: 'Сбросить данные',
    question: 'Удалить все заявки?',
    confirm: 'Да, сбросить',
    cancel: 'Отмена',
    busy: 'Сбрасываем…',
    done: (count: number, at: string) => `Готово в ${at}: удалено заявок — ${count}. Можно начинать показ.`,
    error: 'Не получилось сбросить данные',
  },
  audit: {
    eyebrow: 'Аудит',
    title: 'Журнал действий',
    applicationTitle: 'Журнал по заявке',
    note: 'Журнал только дописывается: записи не меняются и не удаляются.',
    filter: 'Действия',
    group: {
      all: 'Все',
      auth: 'Входы',
      client: 'Клиенты',
      documents: 'Документы',
      bank: 'Решения банка',
      system: 'Система',
    } satisfies Record<AuditGroup, string>,
    groupActions: {
      all: [],
      auth: ['auth.login', 'auth.login_failed'],
      client: [
        'application.created',
        'application.submitted',
        'application.resubmitted',
        'application.cancelled',
        'offer.accepted',
        'offer.declined',
        'signing.code_issued',
        'signing.confirmed',
      ],
      documents: ['document.uploaded', 'document.downloaded'],
      bank: ['bank.assigned', 'bank.decision'],
      system: ['application.status_changed', 'loan.issued', 'demo.reset'],
    } satisfies Record<AuditGroup, AuditAction[]>,
    columns: { time: 'Когда', action: 'Действие и кто', summary: 'Что изменилось' },
    action: {
      'auth.login': 'Вход',
      'auth.login_failed': 'Неудачный вход',
      'application.created': 'Создан черновик',
      'application.submitted': 'Заявка отправлена',
      'application.resubmitted': 'Отправлена повторно',
      'application.cancelled': 'Заявка отменена',
      'application.status_changed': 'Смена статуса',
      'document.uploaded': 'Загружен файл',
      'document.downloaded': 'Открыт файл',
      'offer.accepted': 'Предложение принято',
      'offer.declined': 'Предложение отклонено',
      'signing.code_issued': 'Выдан код подписи',
      'signing.confirmed': 'Договор подписан',
      'loan.issued': 'Кредит выдан',
      'bank.assigned': 'Взята в работу',
      'bank.decision': 'Решение специалиста',
      'demo.reset': 'Сброс демо',
    } satisfies Record<AuditAction, string>,
    role: {
      client: 'клиент',
      underwriter: 'специалист',
      admin: 'администратор',
      system: 'система',
    } satisfies Record<AuditActorRole, string>,
    system: 'Система',
    unknown: 'неизвестно',
    empty: 'Записей пока нет.',
    more: 'Показать ещё',
    loadingMore: 'Загружаем…',
    loadError: 'Не получилось загрузить журнал',
  },
};

