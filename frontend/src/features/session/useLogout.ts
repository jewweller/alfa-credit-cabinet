import { useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import { clearToken } from '../../api/client';
import { ROUTES } from '../routes';

export function useLogout() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  return () => {
    clearToken();
    queryClient.clear();
    navigate(ROUTES.login);
  };
}
