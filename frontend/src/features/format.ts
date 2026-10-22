import { MONEY, TIME } from '../i18n/ru';

const money = new Intl.NumberFormat('ru-RU', {
  style: 'currency',
  currency: 'RUB',
  maximumFractionDigits: 0,
});

/** Деньги приходят строкой "3000000.00" (контракт) — на экран выводим «3 000 000 ₽». */
export function formatMoney(amount: string | number | null | undefined): string {
  if (amount === null || amount === undefined || amount === '') return MONEY.noAmount;
  return money.format(Number(amount));
}

const moneyKop = new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', minimumFractionDigits: 2 });

/** С копейками — для графика платежей. */
export function formatMoneyExact(amount: string | number): string {
  return moneyKop.format(Number(amount));
}

export function formatTerm(months: number | null | undefined): string {
  return months ? MONEY.term(months) : MONEY.noTerm;
}

/** Ставка "18.00" → «18% годовых». */
export function formatRate(rate: string | number): string {
  return `${Number(rate).toLocaleString('ru-RU', { maximumFractionDigits: 2 })}% годовых`;
}

const dateFmt2 = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
const dateTimeFmt = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' });

export function formatDate(iso: string): string {
  return dateFmt2.format(new Date(iso));
}

export function formatDateTime(iso: string): string {
  return dateTimeFmt.format(new Date(iso));
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} КБ`;
  return `${(bytes / 1024 / 1024).toLocaleString('ru-RU', { maximumFractionDigits: 1 })} МБ`;
}

const dateFmt = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });

export function timeAgo(iso: string, now: number = Date.now()): string {
  const diffMin = Math.max(0, Math.floor((now - new Date(iso).getTime()) / 60_000));
  if (diffMin < 1) return TIME.justNow;
  if (diffMin < 60) return TIME.minutes(diffMin);
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return TIME.hours(diffH);
  const diffD = Math.floor(diffH / 24);
  if (diffD === 1) return TIME.yesterday;
  if (diffD < 7) return TIME.days(diffD);
  return dateFmt.format(new Date(iso));
}

const todayFmt = new Intl.DateTimeFormat('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' });

/** «среда, 22 октября» — подпись над приветствием. */
export function formatToday(now: number = Date.now()): string {
  return todayFmt.format(new Date(now));
}
