import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiGet, apiPost, apiUpload, newIdempotencyKey } from '../../api/client';
import type {
  ApplicationDetail,
  DocumentInfo,
  DocumentKind,
  PaymentSchedule,
  StatusHistoryEntry,
} from '../../api/types';
import { STATUS_UI } from '../../i18n/ru';
import { POLL_INTERVAL_MS } from '../applications/useApplications';

export const applicationKey = (id: string) => ['application', id] as const;

/** Карточка заявки. Опрос каждые 3 секунды, пока заявка у банка (план, раздел 5). */
export function useApplication(id: string) {
  return useQuery({
    queryKey: applicationKey(id),
    queryFn: ({ signal }) => apiGet<ApplicationDetail>(`/applications/${id}`, signal),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && STATUS_UI[status].block === 'bank' ? POLL_INTERVAL_MS : false;
    },
    retry: (count, error) => !('status' in error && error.status === 404) && count < 1,
  });
}

/** История перечитывается при каждой смене статуса. */
export function useApplicationHistory(id: string, statusChangedAt: string | undefined) {
  return useQuery({
    queryKey: ['application-history', id, statusChangedAt],
    queryFn: ({ signal }) => apiGet<StatusHistoryEntry[]>(`/applications/${id}/history`, signal),
    enabled: Boolean(statusChangedAt),
    placeholderData: (previous) => previous,
  });
}

export function usePaymentSchedule(id: string, offerId: string | undefined) {
  return useQuery({
    queryKey: ['payment-schedule', id, offerId],
    queryFn: ({ signal }) =>
      apiGet<PaymentSchedule>(`/applications/${id}/schedule?offer_id=${offerId}`, signal),
    enabled: Boolean(offerId),
    staleTime: Infinity,
  });
}

/**
 * Действия клиента по заявке. Ответ сервера — свежая карточка: кладём её в кэш сразу,
 * а список заявок, ленту и историю просим перечитать.
 */
export function useApplicationActions(id: string) {
  const queryClient = useQueryClient();

  const refresh = (detail?: ApplicationDetail) => {
    if (detail) queryClient.setQueryData(applicationKey(id), detail);
    else void queryClient.invalidateQueries({ queryKey: applicationKey(id) });
    void queryClient.invalidateQueries({ queryKey: ['applications'] });
    void queryClient.invalidateQueries({ queryKey: ['feed'] });
  };

  // Один ключ идемпотентности на одно нажатие: повтор того же запроса не создаст дубль.
  const post = (path: string) => apiPost<ApplicationDetail>(path, { idempotencyKey: newIdempotencyKey() });

  const accept = useMutation({
    mutationFn: (offerId: string) => post(`/applications/${id}/offers/${offerId}/accept`),
    onSuccess: refresh,
  });

  const decline = useMutation({
    mutationFn: (offerId: string) => post(`/applications/${id}/offers/${offerId}/decline`),
    onSuccess: refresh,
  });

  const resubmit = useMutation({
    mutationFn: () => post(`/applications/${id}/resubmit`),
    onSuccess: refresh,
  });

  const cancel = useMutation({
    mutationFn: () => post(`/applications/${id}/cancel`),
    onSuccess: refresh,
  });

  const upload = useMutation({
    mutationFn: (input: { file: File; kind: DocumentKind; infoRequestId: string | null }) => {
      const form = new FormData();
      form.append('file', input.file);
      form.append('kind', input.kind);
      if (input.infoRequestId) form.append('info_request_id', input.infoRequestId);
      return apiUpload<DocumentInfo>(`/applications/${id}/documents`, form);
    },
    onSuccess: () => refresh(),
  });

  return { accept, decline, resubmit, cancel, upload };
}
