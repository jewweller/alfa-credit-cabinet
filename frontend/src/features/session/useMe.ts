import { useQuery } from '@tanstack/react-query';
import { ApiError, apiGet, readToken } from '../../api/client';
import type { Me } from '../../api/types';

export function useMe() {
  return useQuery({
    queryKey: ['me'],
    queryFn: ({ signal }) => apiGet<Me>('/auth/me', signal),
    enabled: readToken() !== null,
    staleTime: 5 * 60_000,
    retry: (count, error) => !(error instanceof ApiError && error.status === 401) && count < 1,
  });
}

/** Имя для приветствия: первое слово из full_name («Ирина Соколова» → «Ирина»). */
export function firstName(fullName: string | undefined): string {
  return fullName?.trim().split(/\s+/)[0] ?? '';
}
