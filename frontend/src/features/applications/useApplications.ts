import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../../api/client';
import type { ApplicationSummary } from '../../api/types';
import { STATUS_UI } from '../../i18n/ru';

export const POLL_INTERVAL_MS = 3_000;

/** Опрос нужен, только пока хотя бы одна заявка в работе у банка. */
export function needsPolling(items: ApplicationSummary[] | undefined): boolean {
  return (items ?? []).some((a) => STATUS_UI[a.status].block === 'bank');
}

export function useApplications() {
  return useQuery({
    queryKey: ['applications'],
    queryFn: ({ signal }) => apiGet<ApplicationSummary[]>('/applications', signal),
    refetchInterval: (query) => (needsPolling(query.state.data) ? POLL_INTERVAL_MS : false),
  });
}
