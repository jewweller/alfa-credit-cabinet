import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import { ApiError, apiGet, apiPost } from '../../api/client';
import type { ApplicationCreate, ApplicationDetail, CompanyLookup } from '../../api/types';
import { applicationKey } from '../application/queries';
import { ROUTES } from '../routes';

/** Создать черновик и сразу открыть мастер заявки. */
export function useCreateDraft() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  return useMutation({
    mutationFn: (body: ApplicationCreate) => apiPost<ApplicationDetail>('/applications', { body }),
    onSuccess: (detail) => {
      queryClient.setQueryData(applicationKey(detail.id), detail);
      void queryClient.invalidateQueries({ queryKey: ['applications'] });
      navigate(ROUTES.applicationEdit(detail.id));
    },
  });
}

/** Данные компании из ЕГРЮЛ/ЕГРИП. «Не найдена» не повторяем — ответ не изменится. */
export function useCompanyLookup(inn: string | undefined) {
  return useQuery({
    queryKey: ['company-lookup', inn],
    queryFn: ({ signal }) => apiGet<CompanyLookup>(`/companies/lookup?inn=${inn}`, signal),
    enabled: Boolean(inn),
    staleTime: 10 * 60_000,
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 1,
  });
}
