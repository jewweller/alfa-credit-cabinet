// Аннуитет — так же, как будет считать бэк (domain/loan_math.py). Считаем в копейках,
// платёж округляем до копейки. Нужен для примерного платежа в мастере заявки.

export const toKop = (money: string) => Math.round(Number(money) * 100);
export const toMoney = (kop: number) => (kop / 100).toFixed(2);

export function annuityPaymentKop(amountKop: number, ratePercent: number, months: number): number {
  const r = ratePercent / 100 / 12;
  if (r === 0) return Math.round(amountKop / months);
  return Math.round((amountKop * r) / (1 - Math.pow(1 + r, -months)));
}

export function monthlyPayment(amount: string, rate: string, months: number): string {
  return toMoney(annuityPaymentKop(toKop(amount), Number(rate), months));
}
