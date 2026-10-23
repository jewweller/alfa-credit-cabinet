import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import { apiGet, apiPost, saveToken } from '../../api/client';
import type { LoginRequest, Me, TokenResponse } from '../../api/types';
import { homeFor } from '../routes';

/** Адрес возврата после входа: только свой, относительный путь. */
function safeNext(next: string | null): string | null {
  return next && next.startsWith('/') && !next.startsWith('//') ? next : null;
}

/** Вход: токен → профиль → в свой кабинет (клиента — туда, откуда его отправили на вход). */
export function useLogin(next: string | null) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  return useMutation({
    mutationFn: async (body: LoginRequest) => {
      const { access_token } = await apiPost<TokenResponse>('/auth/login', { body });
      saveToken(access_token);
      queryClient.clear();
      return apiGet<Me>('/auth/me');
    },
    onSuccess: (me) => {
      queryClient.setQueryData(['me'], me);
      const target = me.role === 'client' ? (safeNext(next) ?? homeFor(me.role)) : homeFor(me.role);
      navigate(target, { replace: true });
    },
  });
}
