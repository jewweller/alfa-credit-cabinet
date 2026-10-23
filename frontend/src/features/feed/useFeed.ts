import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../../api/client';
import type { FeedItem } from '../../api/types';

export const HOME_FEED_LIMIT = 5;

/** Сверху события по заявкам, ниже новости; внутри групп — свежие первыми. */
export function orderFeed(items: FeedItem[]): FeedItem[] {
  const byDateDesc = (a: FeedItem, b: FeedItem) => b.created_at.localeCompare(a.created_at);
  const events = items.filter((i) => i.kind === 'event').sort(byDateDesc);
  const news = items.filter((i) => i.kind === 'news').sort(byDateDesc);
  return [...events, ...news];
}

export function useFeed(limit?: number) {
  return useQuery({
    queryKey: ['feed'],
    queryFn: ({ signal }) => apiGet<FeedItem[]>('/feed', signal),
    select: (items) => {
      const ordered = orderFeed(items);
      return limit ? ordered.slice(0, limit) : ordered;
    },
  });
}
