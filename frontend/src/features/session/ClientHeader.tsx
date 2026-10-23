import { HEADER } from '../../i18n/ru';
import { AppHeader } from '../../ui';
import { homeFor, ROUTES } from '../routes';
import { SurfaceSwitch } from './SurfaceSwitch';
import { useLogout } from './useLogout';
import { useMe } from './useMe';

/** Шапка кабинета: от чьего имени работаем, оформление, кто вошёл, выход. Общая для клиента и банка. */
export function ClientHeader() {
  const { data: me } = useMe();
  const logout = useLogout();
  return (
    <AppHeader
      productName={HEADER.product}
      homeHref={me ? homeFor(me.role) : ROUTES.home}
      company={
        me?.company
          ? { name: me.company.name, innLabel: `${HEADER.inn} ${me.company.inn}` }
          : me
            ? { name: HEADER.bank, innLabel: HEADER.role[me.role] }
            : null
      }
      userName={me?.full_name ?? null}
      logoutLabel={HEADER.logout}
      onLogout={logout}
      tools={<SurfaceSwitch />}
    />
  );
}
