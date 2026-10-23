// График платежей — так же, как будет считать бэк (domain/loan_math.py). Аннуитет — в
// features/loanMath.ts; проценты округляем до копейки, последний платёж закрывает
// остаток целиком (описание PaymentSchedule в контракте).
// В плане примеры округлены до рубля: 275 040 ₽ — здесь будет 275 039,98 ₽.
import type { PaymentSchedule } from '../api/types';
import { annuityPaymentKop, monthlyPayment, toKop, toMoney } from '../features/loanMath';

export { monthlyPayment };

function addMonths(date: Date, months: number): Date {
  const d = new Date(date);
  d.setMonth(d.getMonth() + months);
  return d;
}

export function buildSchedule(
  offer: { id: string; amount: string; term_months: number; rate: string },
  startDate: Date,
): PaymentSchedule {
  const amountKop = toKop(offer.amount);
  const r = Number(offer.rate) / 100 / 12;
  const paymentKop = annuityPaymentKop(amountKop, Number(offer.rate), offer.term_months);

  let balance = amountKop;
  let total = 0;
  const items: PaymentSchedule['items'] = [];
  for (let n = 1; n <= offer.term_months; n += 1) {
    const interest = Math.round(balance * r);
    const isLast = n === offer.term_months;
    const principal = isLast ? balance : paymentKop - interest;
    const payment = principal + interest;
    balance -= principal;
    total += payment;
    items.push({
      number: n,
      due_date: addMonths(startDate, n).toISOString().slice(0, 10),
      payment: toMoney(payment),
      principal: toMoney(principal),
      interest: toMoney(interest),
      balance: toMoney(balance),
    });
  }

  return {
    offer_id: offer.id,
    amount: offer.amount,
    term_months: offer.term_months,
    rate: offer.rate,
    monthly_payment: toMoney(paymentKop),
    total_payment: toMoney(total),
    overpayment: toMoney(total - amountKop),
    items,
  };
}
