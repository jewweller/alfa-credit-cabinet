import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiGet, apiPost } from '../../api/client';
import type { AuditAction, AuditEntry, DemoResetResult } from '../../api/types';
import { POLL_INTERVAL_MS } from '../applications/useApplications';

export const AUDIT_PAGE = 50;

export interface AuditFilter {
  applicationId?: string;
  actions?: AuditAction[];
}

/** Журнал действий, свежие сверху; следующая страница — записи раньше последней загруженной. */
export function useAudit(filter: AuditFilter = {}) {
  const params = new URLSearchParams({ limit: String(AUDIT_PAGE) });
  if (filter.applicationId) params.set('application_id', filter.applicationId);
  for (const action of filter.actions ?? []) params.append('action', action);
  const query = params.toString();
  return useInfiniteQuery({
    queryKey: ['audit', query],
    queryFn: ({ pageParam, signal }) =>
      apiGet<AuditEntry[]>(`/bank/audit?${query}${pageParam ? `&before=${encodeURIComponent(pageParam)}` : ''}`, signal),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => (last.length < AUDIT_PAGE ? undefined : last[last.length - 1].created_at),
    select: (data) => data.pages.flat(),
    refetchInterval: POLL_INTERVAL_MS * 2,
    placeholderData: (previous) => previous,
  });
}

/** Сброс демо: после него всё, кроме профиля, устарело — перечитываем. */
export function useDemoReset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiPost<DemoResetResult>('/admin/demo/reset'),
    onSuccess: () => queryClient.invalidateQueries({ predicate: (q) => q.queryKey[0] !== 'me' }),
  });
}
