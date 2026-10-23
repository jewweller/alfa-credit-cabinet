// Кредитное решение в моках — правила плана (раздел 7). Скоринг (scoring.ts) даёт грейд,
// правила R1–R10 идут по порядку, срабатывает первое. Каждая проверка записывается с пояснением —
// андеррайтер видит её в карточке (B3). Другой продукт в R10 моки не подбирают (упрощение).
import type { ApplicationDetail, Grade, InfoRequestItem, Product, RejectReason, RuleCheck, ScoringResult } from '../api/types';
import { formatMoney, formatPercent } from '../features/format';
import { products, users } from './data';
import { debtLoad, score } from './scoring';
import { sourcesFor, type Sources } from './sources';

/** Надбавка к базовой ставке по грейду: R9 (A, B) и R8 (C), п.п. */
const RATE_DELTA: Partial<Record<Grade, number>> = { A: 0, B: 2, C: 4 };
const SAFE_LOAD = 0.35;
/** R4: расхождение выручки в анкете и у ФНС. */
const REVENUE_MISMATCH = 0.3;
/** R5: крупные суммы — только через специалиста. */
const MANUAL_AMOUNT = 10_000_000;
/** R10: шаг удлинения срока. */
const TERM_STEP = 6;
/** R2: просрочка, после которой — отказ. */
const HARD_OVERDUE_DAYS = 90;

export interface OfferTerms {
  productId: string;
  amount: string;
  term: number;
  rate: string;
}

export type Verdict =
  | { kind: 'approved' | 'counter_offer'; offer: OfferTerms }
  | { kind: 'rejected'; reason: RejectReason }
  /** request — что просит специалист; без него — запрос по R4 (REVENUE_INFO_REQUEST). */
  | { kind: 'info_requested'; request?: { items: InfoRequestItem[]; message: string } }
  | { kind: 'manual_review' };

export interface Evaluation {
  scoring: ScoringResult;
  rules: RuleCheck[];
  verdict: Verdict;
}

const innByCompany = new Map(users.flatMap((u) => (u.company ? [[u.company.id, u.company.inn] as const] : [])));

export function sourcesOf(app: ApplicationDetail): Sources {
  return sourcesFor(innByCompany.get(app.company_id) ?? '');
}

/** Ставка для грейда: база продукта + надбавка. */
export function gradeRate(product: Product, grade: Grade): string {
  return (Number(product.base_rate) + (RATE_DELTA[grade] ?? 0)).toFixed(2);
}

const ratePct = (rate: string) => formatPercent(Number(rate) / 100);

/** Максимальная сумма (до рубля вниз), при которой нагрузка не выше 35%. */
function maxAmount(rate: string, term: number, payments: number, revenue12m: number): number {
  const budget = (revenue12m / 12) * SAFE_LOAD - payments;
  if (budget <= 0) return 0;
  const r = Number(rate) / 100 / 12;
  return Math.floor(r === 0 ? budget * term : (budget * (1 - Math.pow(1 + r, -term))) / r);
}

/** Решение по нагрузке для грейдов A/B (R9/R10): срок длиннее, потом сумма меньше. */
function byLoad(app: ApplicationDetail, product: Product, grade: Grade, revenue12m: number) {
  const rate = gradeRate(product, grade);
  const amount = Number(app.amount);
  const term = app.term_months!;
  const payments = Number(app.existing_payments_monthly ?? 0);
  const terms = (a: number, t: number): OfferTerms => ({ productId: product.id, amount: a.toFixed(2), term: t, rate });
  const load = debtLoad(amount, rate, term, payments, revenue12m);
  const result = (verdict: Verdict, note = '') => ({ load, verdict, note });

  if (load <= SAFE_LOAD) return result({ kind: 'approved', offer: terms(amount, term) });
  for (let t = term + TERM_STEP; t <= product.max_term; t += TERM_STEP) {
    const longer = debtLoad(amount, rate, t, payments, revenue12m);
    if (longer <= SAFE_LOAD) {
      return result({ kind: 'counter_offer', offer: terms(amount, t) }, `срок ${t} мес → нагрузка ${formatPercent(longer)}`);
    }
  }
  const reduced = maxAmount(rate, product.max_term, payments, revenue12m);
  if (reduced >= Number(product.min_amount)) {
    const a = Math.min(reduced, amount);
    return result({ kind: 'counter_offer', offer: terms(a, product.max_term) }, `срок ${product.max_term} мес и сумма ${formatMoney(a)}`);
  }
  return result({ kind: 'rejected', reason: 'no_suitable_terms' }, 'ни срок, ни сумма не помогают');
}

/** Скоринг и проверка правил по порядку до первого сработавшего. */
export function evaluate(app: ApplicationDetail): Evaluation {
  const src = sourcesOf(app);
  const scoring = score(app, src);
  const product = products.find((p) => p.id === app.product_id)!;
  const amount = Number(app.amount);
  const revenue = Number(app.revenue_12m);
  const payments = Number(app.existing_payments_monthly ?? 0);
  const rules: RuleCheck[] = [];
  const done = (verdict: Verdict): Evaluation => ({ scoring, rules, verdict });
  const check = (code: string, title: string, fired: boolean, detail: string) => {
    rules.push({ code, title, fired, detail });
    return fired;
  };

  const status = src.registry?.status ?? 'нет в реестре';
  if (check('R1', 'Компания не действующая в ЕГРЮЛ/ЕГРИП', status !== 'ACTIVE', `Статус: ${status}`)) {
    return done({ kind: 'rejected', reason: 'company_inactive' });
  }

  const overdue = Math.max(0, ...(src.bki?.loans.map((l) => l.current_overdue_days) ?? []));
  const bankrupt = src.bki?.bankruptcy ?? false;
  const r2 = !src.bki
    ? 'БКИ не ответило'
    : bankrupt
      ? 'Банкротство'
      : overdue > 0
        ? `Текущая просрочка ${overdue} дн.`
        : 'Текущих просрочек нет';
  if (check('R2', 'Банкротство или текущая просрочка больше 90 дней (БКИ)', bankrupt || overdue > HARD_OVERDUE_DAYS, r2)) {
    return done({ kind: 'rejected', reason: 'bankruptcy_or_overdue' });
  }

  const r3 = src.bki ? 'Все источники ответили' : 'БКИ: 503 после 3 попыток';
  if (check('R3', 'Источник не ответил после 2 повторов', !src.bki, r3)) return done({ kind: 'manual_review' });

  const fns = src.fns.revenue['2025'] ?? null;
  const answered = app.info_request?.status === 'answered';
  const mismatch = fns ? Math.abs(revenue - fns) / fns : 0;
  const r4 = answered
    ? 'Документы по запросу загружены — решает специалист'
    : fns
      ? `Анкета ${formatMoney(revenue)}, ФНС ${formatMoney(fns)}: расхождение ${formatPercent(mismatch)}`
      : 'Нет данных ФНС о выручке';
  if (check('R4', 'Выручка в анкете расходится с ФНС больше чем на 30%', answered || mismatch > REVENUE_MISMATCH, r4)) {
    return done(answered ? { kind: 'manual_review' } : { kind: 'info_requested' });
  }

  if (check('R5', 'Сумма больше 10 млн ₽', amount > MANUAL_AMOUNT, `Сумма ${formatMoney(amount)}`)) {
    return done({ kind: 'manual_review' });
  }

  const { grade, total_score } = scoring;
  const gradeNote = `Грейд ${grade}, ${total_score} баллов`;
  if (check('R6', 'Грейд E', grade === 'E', gradeNote)) return done({ kind: 'rejected', reason: 'low_score' });
  if (check('R7', 'Грейд D', grade === 'D', gradeNote)) return done({ kind: 'manual_review' });

  if (grade === 'C') {
    // R8: меньшее из половины запрошенного и максимума при нагрузке ≤ 35%; ставка база + 4 п.п.
    const rate = gradeRate(product, 'C');
    const offered = Math.floor(Math.min(amount * 0.5, maxAmount(rate, app.term_months!, payments, revenue)));
    const enough = offered >= Number(product.min_amount);
    const note = enough ? `${gradeNote}: сумма ${formatMoney(offered)}, ставка ${ratePct(rate)}` : `${gradeNote}: допустимая сумма ниже минимума продукта`;
    check('R8', 'Грейд C', true, note);
    return done(
      enough
        ? { kind: 'counter_offer', offer: { productId: product.id, amount: offered.toFixed(2), term: app.term_months!, rate } }
        : { kind: 'rejected', reason: 'no_suitable_terms' },
    );
  }
  check('R8', 'Грейд C', false, gradeNote);

  const { load, verdict, note } = byLoad(app, product, grade, revenue);
  const loadNote = `Нагрузка ${formatPercent(load)} при ставке ${ratePct(gradeRate(product, grade))}`;
  if (check('R9', 'Грейд A/B и нагрузка не выше 35%', load <= SAFE_LOAD, loadNote)) return done(verdict);
  check('R10', 'Грейд A/B и нагрузка выше 35%', true, `${loadNote}; ${note}`);
  return done(verdict);
}

/** Автоматическое решение после скоринга. */
export function decide(app: ApplicationDetail): Verdict {
  return evaluate(app).verdict;
}

/** Запрос банка при R4 — какие документы нужны и почему. */
export const REVENUE_INFO_REQUEST = {
  // Как на бэке (config.yaml, R4): один пункт, закрывается декларацией или выпиской.
  items: [{ kind: 'tax_return' as const, title: 'Декларация или выписка за прошлый год', required: true }],
  message: 'Выручка в заявке отличается от данных ФНС больше чем на 30%. Подтвердите её декларацией — так мы быстрее примем решение.',
};
