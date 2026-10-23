// Подбор продукта (POST /products/recommend) — как описано в контракте:
// продукты с нужной целью, сумма и срок приведены к лимитам, сначала подходящие
// без изменений, потом с меньшим платежом.
import type { ProductRecommendation, ProductRecommendRequest, RecommendationAdjustment } from '../api/types';
import { monthlyPayment } from '../features/loanMath';
import { products } from './data';
import { MockHttpError } from './db';

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

export function recommend(body: Partial<ProductRecommendRequest>): ProductRecommendation[] {
  if (!body.purpose) throw new MockHttpError(422, 'validation_error', 'Выберите цель', 'purpose');
  if (!body.amount || !/^\d+\.\d{2}$/.test(body.amount) || Number(body.amount) <= 0) {
    throw new MockHttpError(422, 'validation_error', 'Укажите сумму', 'amount');
  }
  if (!body.term_months || body.term_months < 1) {
    throw new MockHttpError(422, 'validation_error', 'Укажите срок', 'term_months');
  }
  const { purpose, term_months: term } = body;
  const requested = Number(body.amount);

  return products
    .filter((product) => product.purpose_tags.includes(purpose))
    .map((product) => {
      const amount = clamp(requested, Number(product.min_amount), Number(product.max_amount));
      const months = clamp(term, product.min_term, product.max_term);
      const adjusted: RecommendationAdjustment[] = [];
      if (amount !== requested) adjusted.push('amount');
      if (months !== term) adjusted.push('term_months');
      const money = amount.toFixed(2);
      return {
        product,
        amount: money,
        term_months: months,
        rate: product.base_rate,
        monthly_payment: monthlyPayment(money, product.base_rate, months),
        adjusted,
      };
    })
    .sort(
      (a, b) =>
        a.adjusted.length - b.adjusted.length || Number(a.monthly_payment) - Number(b.monthly_payment),
    )
    .slice(0, 3);
}
