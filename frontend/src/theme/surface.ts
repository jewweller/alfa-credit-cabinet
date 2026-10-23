import { useCallback, useState } from 'react';

// Оформление рабочих поверхностей: «жемчуг» (по умолчанию) или «графит».
// Выбор хранится в браузере и ставится атрибутом data-surface на <html>.
export const SURFACES = ['pearl', 'graphite'] as const;
export type Surface = (typeof SURFACES)[number];

const KEY = 'surface';
const DEFAULT_SURFACE: Surface = 'pearl';

function isSurface(value: string | null): value is Surface {
  return SURFACES.includes(value as Surface);
}

export function readSurface(): Surface {
  try {
    const saved = localStorage.getItem(KEY);
    if (isSurface(saved)) return saved;
  } catch {
    // хранилище недоступно — берём вариант по умолчанию
  }
  return DEFAULT_SURFACE;
}

/** Вызывается до первого рендера, чтобы не мигала тема по умолчанию. */
export function applySurface(surface: Surface = readSurface()): void {
  document.documentElement.dataset.surface = surface;
}

type DocumentWithTransitions = Document & {
  startViewTransition?: (update: () => void) => unknown;
};

export function useSurface(): [Surface, (next: Surface) => void] {
  const [surface, setSurface] = useState<Surface>(readSurface);

  const change = useCallback((next: Surface) => {
    try {
      localStorage.setItem(KEY, next);
    } catch {
      // не запомнится между визитами — не страшно
    }
    const update = () => {
      applySurface(next);
      setSurface(next);
    };
    const doc = document as DocumentWithTransitions;
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    // Плавное перетекание темы, где браузер умеет View Transitions.
    if (doc.startViewTransition && !reduceMotion) doc.startViewTransition(update);
    else update();
  }, []);

  return [surface, change];
}
