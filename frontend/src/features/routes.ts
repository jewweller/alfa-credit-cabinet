import type { UserRole } from '../api/types';
import type { Screen } from '../i18n/ru';

// Адреса экранов из плана (раздел 11).
export const ROUTES = {
  home: '/',
  login: '/login',
  products: '/products',
  feed: '/feed',
  /** Кабинет банка: очередь (B2) и карточка заявки с решением (B3–B4). */
  bank: '/bank',
  bankApplication: (id: string) => `/bank/applications/${id}`,
  /** Администратор: сброс демо и журнал действий. */
  admin: '/admin',
  application: (id: string) => `/applications/${id}`,
  applicationEdit: (id: string) => `/applications/${id}/edit`,
  signing: (id: string) => `/applications/${id}/signing`,
  result: (id: string) => `/applications/${id}/result`,
};

export function screenPath(screen: Screen, applicationId: string): string {
  switch (screen) {
    case 'C4':
      return ROUTES.applicationEdit(applicationId);
    case 'C5':
      return ROUTES.application(applicationId);
    case 'C6':
      return ROUTES.signing(applicationId);
    case 'C7':
      return ROUTES.result(applicationId);
  }
}

/** Куда вести после входа: клиента — на главную, специалиста — в очередь, администратора — к себе. */
export function homeFor(role: UserRole): string {
  return role === 'client' ? ROUTES.home : role === 'admin' ? ROUTES.admin : ROUTES.bank;
}
