import { HEADER } from '../../i18n/ru';
import { useSurface, type Surface } from '../../theme/surface';
import { AppHeader, SegmentedControl } from '../../ui';
import { ROUTES } from '../routes';
import { useLogout } from './useLogout';
import { useMe } from './useMe';

const SURFACE_OPTIONS: { value: Surface; label: string; swatch: string }[] = [
  {
    value: 'pearl',
    label: HEADER.surface.pearl,
    swatch: 'linear-gradient(145deg, #f6f2ed, #efe6ea 60%, #e6e8ee)',
  },
  {
    value: 'graphite',
    label: HEADER.surface.graphite,
    swatch: 'linear-gradient(145deg, #2a2426, #141011)',
  },
];

/** Шапка клиента: от чьего имени работаем, оформление, кто вошёл, выход. */
export function ClientHeader() {
  const { data: me } = useMe();
  const logout = useLogout();
  const [surface, setSurface] = useSurface();
  return (
    <AppHeader
      productName={HEADER.product}
      homeHref={ROUTES.home}
      company={
        me?.company ? { name: me.company.name, innLabel: `${HEADER.inn} ${me.company.inn}` } : null
      }
      userName={me?.full_name ?? null}
      logoutLabel={HEADER.logout}
      onLogout={logout}
      tools={
        <SegmentedControl
          label={HEADER.surface.label}
          options={SURFACE_OPTIONS}
          value={surface}
          onChange={setSurface}
        />
      }
    />
  );
}
