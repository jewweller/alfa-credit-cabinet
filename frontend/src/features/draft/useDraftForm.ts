import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, apiGet, apiPatch } from '../../api/client';
import type { ApplicationDetail, ApplicationUpdate } from '../../api/types';
import { applicationKey } from '../application/queries';
import { DRAFT_FIELDS, pickDraft, type DraftValues } from './validation';

export type SaveState = 'idle' | 'saving' | 'saved' | 'error' | 'conflict';

/** Пауза после последнего изменения, после которой черновик уходит на сервер. */
const AUTOSAVE_DELAY_MS = 700;

function diff(next: DraftValues, saved: DraftValues): Partial<DraftValues> | null {
  const changes: Partial<Record<keyof DraftValues, unknown>> = {};
  for (const field of DRAFT_FIELDS) {
    if (next[field] !== saved[field]) changes[field] = next[field];
  }
  return Object.keys(changes).length > 0 ? (changes as Partial<DraftValues>) : null;
}

/**
 * Форма черновика с автосохранением (план, раздел 4: «сохраняется при каждом шаге»).
 * Изменения копятся и уходят одним PATCH через паузу или при смене шага. Запросы идут
 * по одному: каждый несёт version из ответа предыдущего. Если заявку изменили
 * в другой вкладке (409 version_conflict), берём свежую версию с сервера.
 */
export function useDraftForm(app: ApplicationDetail) {
  const queryClient = useQueryClient();
  const id = app.id;
  const [values, setValues] = useState<DraftValues>(() => pickDraft(app));
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [savedAt, setSavedAt] = useState<string | null>(null);

  const current = useRef(values);
  const saved = useRef(pickDraft(app));
  const version = useRef(app.version);
  const inFlight = useRef<Promise<boolean> | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const reload = useCallback(async () => {
    const fresh = await apiGet<ApplicationDetail>(`/applications/${id}`);
    queryClient.setQueryData(applicationKey(id), fresh);
    version.current = fresh.version;
    saved.current = pickDraft(fresh);
    current.current = pickDraft(fresh);
    setValues(pickDraft(fresh));
  }, [id, queryClient]);

  /** Отправить накопленные изменения. true — на сервере то же, что на экране. */
  const flush = useCallback(async (): Promise<boolean> => {
    clearTimeout(timer.current);
    while (inFlight.current) await inFlight.current;
    const changes = diff(current.current, saved.current);
    if (!changes) return true;

    setSaveState('saving');
    const body: ApplicationUpdate = { version: version.current, ...changes };
    const request = apiPatch<ApplicationDetail>(`/applications/${id}`, body)
      .then((detail) => {
        version.current = detail.version;
        saved.current = { ...saved.current, ...changes };
        queryClient.setQueryData(applicationKey(id), detail);
        setSaveState('saved');
        setSavedAt(new Date().toISOString());
        return true;
      })
      .catch(async (error: unknown) => {
        if (error instanceof ApiError && error.body?.code === 'version_conflict') {
          setSaveState('conflict');
          await reload().catch(() => setSaveState('error'));
        } else if (error instanceof ApiError && error.status === 409) {
          // Заявку уже отправили — страница по свежему статусу уведёт в карточку.
          void queryClient.invalidateQueries({ queryKey: applicationKey(id) });
        } else {
          setSaveState('error');
        }
        return false;
      })
      .finally(() => {
        inFlight.current = null;
      });
    inFlight.current = request;
    return request;
  }, [id, queryClient, reload]);

  const change = useCallback(
    (patch: Partial<DraftValues>) => {
      current.current = { ...current.current, ...patch };
      setValues(current.current);
      clearTimeout(timer.current);
      timer.current = setTimeout(() => void flush(), AUTOSAVE_DELAY_MS);
    },
    [flush],
  );

  // Уходим со страницы — сохраняем то, что не успело уйти.
  useEffect(
    () => () => {
      clearTimeout(timer.current);
      void flush();
    },
    [flush],
  );

  return { values, change, flush, saveState, savedAt };
}
