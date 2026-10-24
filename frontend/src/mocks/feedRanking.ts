// Ранжирование новостей правилами — копия backend/app/domain/feed_ranking.py.
// вес = 3·[ОКВЭД] + 2·[сегмент] + 2·[продукт] + 3·[статус] + свежесть (1 − дней/30).
// Теги ОКВЭД и статуса — фильтры; новость с тегами без совпадений не показывается.

import type { ApplicationStatus, FeedReason, FeedReasonCode } from '../api/types';
import NEWS from './news.json';

export const MODEL_VERSION = 'feed-rules-1.0';
const FRESHNESS_DAYS = 30;

const WEIGHTS: Record<Exclude<FeedReasonCode, 'general'>, number> = { okved: 3, status: 3, product: 2, segment: 2 };

const OKVED_NAMES: Record<string, string> = {
  '10.71': 'производство хлеба и мучных изделий',
  '41.20': 'строительство зданий',
  '46.90': 'оптовая торговля',
  '47.11': 'розничная торговля продуктами',
  '56.10': 'рестораны и кафе',
  '62.01': 'разработка программ',
  '96.02': 'парикмахерские и салоны красоты',
};

const SEGMENT_TEXT = { micro: 'Подобрано для микробизнеса', small: 'Подобрано для малого бизнеса' };

const STATUS_TEXT: Partial<Record<ApplicationStatus, string>> = {
  DRAFT: 'У вас есть черновик заявки',
  SUBMITTED: 'Ваша заявка на проверке',
  ENRICHMENT: 'Ваша заявка на проверке',
  SCORING: 'Ваша заявка на проверке',
  MANUAL_REVIEW: 'Вашу заявку рассматривает специалист',
  INFO_REQUESTED: 'Ваша заявка ждёт документы',
  APPROVED: 'Ваша заявка одобрена',
  COUNTER_OFFER: 'Банк предложил вам другие условия',
  REJECTED: 'По вашей заявке отказ',
  SIGNING: 'Вы подписываете договор',
  SIGNED: 'Договор подписан',
  ISSUED: 'Кредит выдан',
  DECLINED_BY_CLIENT: 'Вы отказались от предложения',
};

const GENERAL_TEXT = 'Полезно всем клиентам';

interface News {
  id: string;
  title: string;
  body: string;
  tags: { okved?: string[]; segment?: string[]; product?: string[]; status?: string[] };
  published_at: string;
}

export interface FeedProfile {
  okvedMain: string;
  segment: 'micro' | 'small';
  /** Код продукта → название, из заявок клиента (кроме отменённых). */
  products: Record<string, string>;
  statuses: Set<ApplicationStatus>;
}

export interface RankedNews {
  news: News;
  score: number;
  reasons: FeedReason[];
}

const okvedGroup = (code: string) => code.split('.', 1)[0].slice(0, 2);

function matches(news: News, profile: FeedProfile): FeedReason[] | null {
  const { okved = [], segment = [], product = [], status = [] } = news.tags;
  const reasons: FeedReason[] = [];

  if (okved.length) {
    if (!okved.includes(okvedGroup(profile.okvedMain))) return null;
    const name = OKVED_NAMES[profile.okvedMain];
    reasons.push({ code: 'okved', text: `Ваш ОКВЭД ${profile.okvedMain}${name ? ` — ${name}` : ''}` });
  }
  if (status.length) {
    const hit = status.find((s) => profile.statuses.has(s as ApplicationStatus)) as ApplicationStatus | undefined;
    if (!hit) return null;
    reasons.push({ code: 'status', text: STATUS_TEXT[hit] ?? GENERAL_TEXT });
  }
  const productHit = product.find((p) => p in profile.products);
  if (productHit) reasons.push({ code: 'product', text: `У вас заявка на «${profile.products[productHit]}»` });
  if (segment.includes(profile.segment)) reasons.push({ code: 'segment', text: SEGMENT_TEXT[profile.segment] });

  if (!reasons.length && (product.length || segment.length)) return null;
  return reasons;
}

function freshness(publishedAt: string, now: number): number {
  const days = Math.max(0, (now - Date.parse(publishedAt)) / 86_400_000);
  return Math.max(0, 1 - days / FRESHNESS_DAYS);
}

/** Топ новостей по весу; при равном весе — свежие первыми. */
export function rankNews(profile: FeedProfile, now: number, limit: number): RankedNews[] {
  const ranked: RankedNews[] = [];
  for (const news of NEWS as News[]) {
    const reasons = matches(news, profile);
    if (!reasons) continue;
    const score = reasons.reduce((sum, r) => sum + WEIGHTS[r.code as keyof typeof WEIGHTS], 0) + freshness(news.published_at, now);
    ranked.push({
      news,
      score: Math.round(score * 100) / 100,
      reasons: reasons.length ? reasons : [{ code: 'general', text: GENERAL_TEXT }],
    });
  }
  ranked.sort((a, b) => b.score - a.score || b.news.published_at.localeCompare(a.news.published_at) || a.news.id.localeCompare(b.news.id));
  return ranked.slice(0, limit);
}
