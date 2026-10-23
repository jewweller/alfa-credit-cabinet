// Кредитное решение в моках — правила плана (раздел 7), упрощённо:
// скоринг не считаем, а берём готовый грейд тестового клиента, остальное — как в плане.
// Порядок правил: R1 → R4 → R5 → R9/R10, срабатывает первое.
import type { ApplicationDetail, Product, RejectReason } from '../api/types';
import { monthlyPayment } from '../features/loanMath';
import { products, users } from './data';

type Grade = 'A' | 'B';

/** Что вернули бы реестры, ФНС и БКИ по тестовому клиенту (план, раздел 8) — только то, что нужно решению. */
interface Profile {
  grade: Grade;
  /** R1: в ЕГРЮЛ/ЕГРИП компания не «действующая». */
  inactive?: boolean;
  /** Выручка за год по данным ФНС — для R4 и для расчёта нагрузки специалистом. */
  fnsRevenue?: string;
}

const PROFILES: Record<string, Profile> = {
  '7701000019': { grade: 'A' }, // ООО «Пекарня Север»: всё чисто
  '500100001072': { grade: 'B' }, // ИП Ковалёв: просрочка до 30 дней
  '500100002020': { grade: 'B', fnsRevenue: '7000000.00' }, // ИП Мельникова: выручка по ФНС 7 млн
  '7701000026': { grade: 'B', inactive: true }, // ООО «СтройРесурс»: ЕГРЮЛ — LIQUIDATED
};
const DEFAULT_PROFILE: Profile = { grade: 'B' };

/** Надбавка к базовой ставке по грейду (R9). */
const RATE_DELTA: Record<Grade, number> = { A: 0, B: 2 };
const SAFE_LOAD = 0.35;
/** R4: расхождение выручки в анкете и у ФНС. */
const REVENUE_MISMATCH = 0.3;
/** R5: крупные суммы — только через специалиста. */
const MANUAL_AMOUNT = 10_000_000;
/** R10: шаг удлинения срока. */
const TERM_STEP = 6;

export interface OfferTerms {
  productId: string;
  amount: string;
  term: number;
  rate: string;
}

export type Verdict =
  | { kind: 'approved' | 'counter_offer'; offer: OfferTerms }
  | { kind: 'rejected'; reason: RejectReason }
  | { kind: 'info_requested' }
  | { kind: 'manual_review' };

const innByCompany = new Map(users.flatMap((u) => (u.company ? [[u.company.id, u.company.inn] as const] : [])));

function profileOf(app: ApplicationDetail): Profile {
  return PROFILES[innByCompany.get(app.company_id) ?? ''] ?? DEFAULT_PROFILE;
}

/** Нагрузка = (текущие платежи + платёж по новому кредиту) / среднемесячная выручка. */
function debtLoad(amount: number, rate: string, term: number, payments: number, revenue12m: number): number {
  return (payments + Number(monthlyPayment(amount.toFixed(2), rate, term))) / (revenue12m / 12);
}

/** Максимальная сумма (до рубля вниз), при которой нагрузка не выше 35%. */
function maxAmount(rate: string, term: number, payments: number, revenue12m: number): number {
  const budget = (revenue12m / 12) * SAFE_LOAD - payments;
  if (budget <= 0) return 0;
  const r = Number(rate) / 100 / 12;
  return Math.floor(r === 0 ? budget * term : (budget * (1 - Math.pow(1 + r, -term))) / r);
}

/**
 * R9/R10: укладываемся в нагрузку 35% — одобряем как просили; иначе сначала удлиняем срок
 * (шаг 6 мес, до максимума продукта), потом уменьшаем сумму. Другой продукт в моках не подбираем.
 */
function byLoad(app: ApplicationDetail, product: Product, grade: Grade, revenue12m: number): Verdict {
  const rate = (Number(product.base_rate) + RATE_DELTA[grade]).toFixed(2);
  const amount = Number(app.amount);
  const term = app.term_months!;
  const payments = Number(app.existing_payments_monthly ?? 0);
  const terms = (a: number, t: number): OfferTerms => ({ productId: product.id, amount: a.toFixed(2), term: t, rate });

  if (debtLoad(amount, rate, term, payments, revenue12m) <= SAFE_LOAD) {
    return { kind: 'approved', offer: terms(amount, term) };
  }
  for (let t = term + TERM_STEP; t <= product.max_term; t += TERM_STEP) {
    if (debtLoad(amount, rate, t, payments, revenue12m) <= SAFE_LOAD) return { kind: 'counter_offer', offer: terms(amount, t) };
  }
  const reduced = maxAmount(rate, product.max_term, payments, revenue12m);
  if (reduced >= Number(product.min_amount)) {
    return { kind: 'counter_offer', offer: terms(Math.min(reduced, amount), product.max_term) };
  }
  return { kind: 'rejected', reason: 'no_suitable_terms' };
}

/** Автоматическое решение после скоринга. */
export function decide(app: ApplicationDetail): Verdict {
  const profile = profileOf(app);
  const product = products.find((p) => p.id === app.product_id)!;
  const revenue = Number(app.revenue_12m);

  if (profile.inactive) return { kind: 'rejected', reason: 'company_inactive' }; // R1
  // R4: документ уже загружен (повторная отправка) — решает человек; не загружен — просим.
  if (app.info_request?.status === 'answered') return { kind: 'manual_review' };
  if (profile.fnsRevenue) {
    const fns = Number(profile.fnsRevenue);
    if (Math.abs(revenue - fns) / fns > REVENUE_MISMATCH) return { kind: 'info_requested' };
  }
  if (Number(app.amount) > MANUAL_AMOUNT) return { kind: 'manual_review' }; // R5
  return byLoad(app, product, profile.grade, revenue); // R9/R10
}

/**
 * Решение специалиста на ручном рассмотрении. Пока кабинета банка (B4) нет, моки принимают
 * его сами: те же R9/R10, но нагрузку специалист считает по выручке ФНС, если она известна.
 */
export function underwriterDecide(app: ApplicationDetail): Verdict {
  const profile = profileOf(app);
  const product = products.find((p) => p.id === app.product_id)!;
  const revenue = Number(profile.fnsRevenue ?? app.revenue_12m);
  const verdict = byLoad(app, product, profile.grade, revenue);
  return verdict.kind === 'rejected' ? { kind: 'rejected', reason: 'underwriter_decision' } : verdict;
}

/** Запрос банка при R4 — какие документы нужны и почему. */
export const REVENUE_INFO_REQUEST = {
  items: [
    { kind: 'tax_return' as const, title: 'Налоговая декларация за 2025 год', required: true },
    { kind: 'bank_statement' as const, title: 'Выписка по расчётному счёту за 6 месяцев', required: false },
  ],
  message: 'Выручка в заявке отличается от данных ФНС больше чем на 30%. Подтвердите её декларацией — так мы быстрее примем решение.',
};
