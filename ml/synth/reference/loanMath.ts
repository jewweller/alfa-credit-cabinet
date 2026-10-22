// Аннуитет и график платежей — так же, как будет считать бэк (domain/loan_math.py).
// Считаем в копейках; платёж и проценты округляем до копейки, последний платёж
// закрывает остаток целиком (описание PaymentSchedule в контракте).
// В плане примеры округлены до рубля: 275 040 ₽ — здесь будет 275 039,98 ₽.
import type { PaymentSchedule } from '../api/types';

const toKop = (money: string) => Math.round(Number(money) * 100);
const toMoney = (kop: number) => (kop / 100).toFixed(2);

export function annuityPaymentKop(amountKop: number, ratePercent: number, months: number): number {
  const r = ratePercent / 100 / 12;
  if (r === 0) return Math.round(amountKop / months);
  return Math.round((amountKop * r) / (1 - Math.pow(1 + r, -months)));
}

export function monthlyPayment(amount: string, rate: string, months: number): string {
  return toMoney(annuityPaymentKop(toKop(amount), Number(rate), months));
}

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
