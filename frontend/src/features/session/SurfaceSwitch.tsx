import { HEADER } from '../../i18n/ru';
import { useSurface, type Surface } from '../../theme/surface';
import { SegmentedControl } from '../../ui';

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

/** Переключатель оформления рабочих поверхностей: жемчуг / графит. */
export function SurfaceSwitch() {
  const [surface, setSurface] = useSurface();
  return (
    <SegmentedControl label={HEADER.surface.label} options={SURFACE_OPTIONS} value={surface} onChange={setSurface} />
  );
}
