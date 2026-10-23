import type { Grade } from '../../api/types';
import type { BadgeTone } from '../../i18n/ru';

/** Сколько заявка в текущем статусе: «<1 мин», «50 мин», «3 ч», «2 дн». */
export function waitingFor(iso: string, now: number): string {
  const minutes = Math.max(0, Math.floor((now - Date.parse(iso)) / 60_000));
  if (minutes < 1) return '<1 мин';
  if (minutes < 60) return `${minutes} мин`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} ч`;
  return `${Math.floor(hours / 24)} дн`;
}

/** Цвет грейда: A/B — хорошо, C — нейтрально, D/E — риск. */
export const GRADE_TONE: Record<Grade, BadgeTone> = { A: 'success', B: 'success', C: 'neutral', D: 'danger', E: 'danger' };
