import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router';
import { readToken } from '../../api/client';
import type { UserRole } from '../../api/types';
import { homeFor, ROUTES } from '../routes';
import { useMe } from './useMe';

/**
 * Пускает на экран только вошедшего пользователя нужной роли.
 * Без токена — на вход с возвратом сюда же; чужая роль — в свой кабинет.
 * Истёкший токен ловит общий обработчик 401 в App.tsx.
 */
export function RequireAuth({ roles, children }: { roles: UserRole[]; children: ReactNode }) {
  const location = useLocation();
  const { data: me } = useMe();

  if (readToken() === null) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`${ROUTES.login}?next=${next}`} replace />;
  }
  if (me && !roles.includes(me.role)) return <Navigate to={homeFor(me.role)} replace />;
  return children;
}
