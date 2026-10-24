import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiGet, apiPost } from '../../api/client';
import type { FeedItemKind, FeedResponse } from '../../api/types';

export const HOME_FEED_LIMIT = 5;
// События появляются, пока заявку обрабатывает конвейер, — ленту подтягиваем сами.
const FEED_POLL_MS = 15_000;

/** Лента клиента. Порядок задаёт сервер: сверху события (свежие первыми), ниже новости по весу. */
export function useFeed({ kind = null, newsLimit }: { kind?: FeedItemKind | null; newsLimit?: number } = {}) {
  const params = new URLSearchParams();
  if (kind) params.set('kind', kind);
  if (newsLimit) params.set('news_limit', String(newsLimit));
  const query = params.size ? `?${params}` : '';
  return useQuery({
    queryKey: ['feed', kind ?? 'all', newsLimit ?? null],
    queryFn: ({ signal }) => apiGet<FeedResponse>(`/feed${query}`, signal),
    refetchInterval: FEED_POLL_MS,
  });
}

/** Отметить событие прочитанным: точка «новое» гаснет сразу, не дожидаясь ответа. */
export function useMarkFeedRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (eventId: string) => apiPost<void>(`/feed/events/${eventId}/read`),
    onMutate: (eventId) => {
      queryClient.setQueriesData<FeedResponse>({ queryKey: ['feed'] }, (feed) =>
        feed && { ...feed, items: feed.items.map((item) => (item.id === eventId ? { ...item, read: true } : item)) },
      );
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['feed'] }),
  });
}
