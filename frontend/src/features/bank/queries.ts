import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiGet, apiPost, newIdempotencyKey } from '../../api/client';
import type {
  ApplicationStatus,
  BankApplicationDetail,
  BankApplicationSummary,
  Grade,
  UnderwriterDecisionRequest,
} from '../../api/types';
import { POLL_INTERVAL_MS } from '../applications/useApplications';

export interface QueueFilter {
  statuses: ApplicationStatus[];
  grade: Grade | null;
  productId: string | null;
}

const bankApplicationKey = (id: string) => ['bank-application', id] as const;

/** Очередь банка. Опрашивается: конвейер двигает заявки сам, клиенты присылают новые. */
export function useBankQueue(filter: QueueFilter) {
  const params = new URLSearchParams();
  for (const status of filter.statuses) params.append('status', status);
  if (filter.grade) params.set('grade', filter.grade);
  if (filter.productId) params.set('product_id', filter.productId);
  const query = params.toString();
  return useQuery({
    queryKey: ['bank-queue', query],
    queryFn: ({ signal }) => apiGet<BankApplicationSummary[]>(`/bank/applications${query ? `?${query}` : ''}`, signal),
    refetchInterval: POLL_INTERVAL_MS,
    placeholderData: (previous) => previous,
  });
}

/** Пока заявка в конвейере или у клиента, карточка обновляется сама. */
const SETTLED: ApplicationStatus[] = ['MANUAL_REVIEW', 'REJECTED', 'ISSUED', 'DECLINED_BY_CLIENT', 'CANCELLED'];

export function useBankApplication(id: string) {
  return useQuery({
    queryKey: bankApplicationKey(id),
    queryFn: ({ signal }) => apiGet<BankApplicationDetail>(`/bank/applications/${id}`, signal),
    refetchInterval: (query) => {
      const status = query.state.data?.application.status;
      return status && !SETTLED.includes(status) ? POLL_INTERVAL_MS : false;
    },
    retry: (count, error) => !('status' in error && error.status === 404) && count < 1,
  });
}

/** Взять в работу и решение: ответ — свежая карточка; очередь и историю просим перечитать. */
export function useBankActions(id: string) {
  const queryClient = useQueryClient();
  const refresh = (detail: BankApplicationDetail) => {
    queryClient.setQueryData(bankApplicationKey(id), detail);
    void queryClient.invalidateQueries({ queryKey: ['bank-queue'] });
    void queryClient.invalidateQueries({ queryKey: ['application-history', id] });
    void queryClient.invalidateQueries({ queryKey: ['audit'] });
  };

  const assign = useMutation({
    mutationFn: () => apiPost<BankApplicationDetail>(`/bank/applications/${id}/assign`),
    onSuccess: refresh,
  });

  const decide = useMutation({
    mutationFn: (body: UnderwriterDecisionRequest) =>
      apiPost<BankApplicationDetail>(`/bank/applications/${id}/decision`, { body, idempotencyKey: newIdempotencyKey() }),
    onSuccess: refresh,
  });

  return { assign, decide };
}

/** «Взять в работу» прямо из очереди. */
export function useAssignFromQueue() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiPost<BankApplicationDetail>(`/bank/applications/${id}/assign`),
    onSuccess: (detail) => {
      queryClient.setQueryData(bankApplicationKey(detail.application.id), detail);
      void queryClient.invalidateQueries({ queryKey: ['bank-queue'] });
    },
  });
}
