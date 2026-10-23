// Скоринг в моках — 6 факторов плана (раздел 7), максимум 100 баллов. Отдельно от решения:
// считается всегда, даже если потом сработает стоп-фактор.
import type { ApplicationDetail, Grade, ScoringFactor, ScoringResult } from '../api/types';
import { formatMoney, formatPercent } from '../features/format';
import { monthlyPayment } from '../features/loanMath';
import { products } from './data';
import type { Sources } from './sources';

export const MODEL_VERSION = 'rules-2026.10';

const YEAR_MS = 365.25 * 24 * 3600 * 1000;

/** Нагрузка = (текущие платежи + платёж по новому кредиту) / среднемесячная выручка. */
export function debtLoad(amount: number, rate: string, term: number, payments: number, revenue12m: number): number {
  return (payments + Number(monthlyPayment(amount.toFixed(2), rate, term))) / (revenue12m / 12);
}

export function gradeOf(score: number): Grade {
  if (score >= 80) return 'A';
  if (score >= 65) return 'B';
  if (score >= 50) return 'C';
  if (score >= 35) return 'D';
  return 'E';
}

function years(n: number): string {
  const whole = Math.floor(n);
  if (whole < 1) return 'меньше года';
  const mod10 = whole % 10;
  const mod100 = whole % 100;
  const word = mod10 === 1 && mod100 !== 11 ? 'год' : mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14) ? 'года' : 'лет';
  return `${whole} ${word}`;
}

function f1Age(src: Sources, at: number): ScoringFactor {
  const age = src.registry ? (at - Date.parse(src.registry.registered_at)) / YEAR_MS : 0;
  const points = age < 1 ? 0 : age < 2 ? 8 : age <= 5 ? 15 : 20;
  return { code: 'F1', title: 'Возраст бизнеса', value: src.registry ? years(age) : 'нет в реестре', points, max_points: 20 };
}

function f2History(src: Sources): ScoringFactor {
  const base = { code: 'F2', title: 'Кредитная история', max_points: 25 };
  if (!src.bki) return { ...base, value: 'БКИ не ответило', points: 10 };
  if (!src.bki.has_history) return { ...base, value: 'истории нет', points: 10 };
  const overdue = Math.max(0, ...src.bki.loans.map((l) => l.max_overdue_days_24m));
  if (overdue === 0) return { ...base, value: 'без просрочек за 24 мес', points: 25 };
  if (overdue <= 30) return { ...base, value: `просрочка до 30 дней (${overdue} дн.)`, points: 15 };
  if (overdue <= 90) return { ...base, value: `просрочка 30–90 дней (${overdue} дн.)`, points: 5 };
  return { ...base, value: `просрочка больше 90 дней (${overdue} дн.)`, points: 0 };
}

function f3Load(load: number): ScoringFactor {
  const points = load <= 0.25 ? 20 : load <= 0.35 ? 12 : load <= 0.5 ? 4 : 0;
  return { code: 'F3', title: 'Долговая нагрузка', value: formatPercent(load), points, max_points: 20 };
}

function f4Revenue(src: Sources): ScoringFactor {
  const base = { code: 'F4', title: 'Динамика выручки', max_points: 15 };
  const { '2024': prev, '2025': last } = src.fns.revenue;
  if (!prev || !last) return { ...base, value: 'нет данных за прошлый год', points: 8 };
  const change = (last - prev) / prev;
  const value = `${change >= 0 ? '+' : '−'}${formatPercent(Math.abs(change))} к 2024`;
  return { ...base, value, points: change >= 0 ? 15 : change >= -0.2 ? 8 : 0 };
}

function f5TaxDebt(src: Sources): ScoringFactor {
  const debt = src.fns.tax_debt_rub;
  const points = debt === 0 ? 10 : debt <= 100_000 ? 4 : 0;
  return { code: 'F5', title: 'Налоговая задолженность', value: debt === 0 ? 'нет' : formatMoney(debt), points, max_points: 10 };
}

const FLAG_TITLES = {
  mass_address: 'массовый адрес',
  unreliable_address: 'недостоверный адрес',
  unreliable_director: 'недостоверный руководитель',
} as const;

function f6Flags(src: Sources): ScoringFactor {
  const raised = (Object.keys(FLAG_TITLES) as (keyof typeof FLAG_TITLES)[]).filter((f) => src.fns.flags[f]);
  const points = raised.length === 0 ? 10 : raised.length === 1 ? 3 : 0;
  const value = raised.length === 0 ? 'нет' : raised.map((f) => FLAG_TITLES[f]).join(', ');
  return { code: 'F6', title: 'Признаки риска (ФНС)', value, points, max_points: 10 };
}

/** Скоринг заявки: нагрузка — по базовой ставке продукта на запрошенных условиях. */
export function score(app: ApplicationDetail, src: Sources): ScoringResult {
  const product = products.find((p) => p.id === app.product_id)!;
  const load = debtLoad(
    Number(app.amount),
    product.base_rate,
    app.term_months!,
    Number(app.existing_payments_monthly ?? 0),
    Number(app.revenue_12m),
  );
  const at = Date.parse(app.submitted_at ?? new Date().toISOString());
  const factors = [f1Age(src, at), f2History(src), f3Load(load), f4Revenue(src), f5TaxDebt(src), f6Flags(src)];
  const total = factors.reduce((sum, f) => sum + f.points, 0);
  return { model_version: MODEL_VERSION, total_score: total, grade: gradeOf(total), debt_load: Math.round(load * 1000) / 1000, factors };
}
