import { useQuery } from '@tanstack/react-query';
import { useEffect, useMemo } from 'react';
import { documentUrl, readToken } from '../../api/client';

/** Что браузер умеет показать сам: PDF — встроенным просмотрщиком, картинки — как есть. */
const VIEWABLE = ['application/pdf', 'image/jpeg', 'image/png'];

export const isViewable = (mime: string) => VIEWABLE.includes(mime);

/**
 * Файл заявки. Обычная ссылка не передаст токен, поэтому берём файл запросом с заголовком
 * Authorization. Тип задаём сами из белого списка, а не из ответа: файл загрузил клиент,
 * и под видом PDF в нашем origin не должен открыться HTML со скриптами.
 */
async function fetchDocument(documentId: string, mime: string, signal?: AbortSignal): Promise<Blob> {
  const token = readToken();
  const res = await fetch(documentUrl(documentId), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    signal,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return new Blob([await res.blob()], { type: isViewable(mime) ? mime : 'application/octet-stream' });
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Скачать файл заявки. */
export async function downloadDocument(documentId: string, filename: string): Promise<void> {
  saveBlob(await fetchDocument(documentId, 'application/octet-stream'), filename);
}

export interface DocumentRef {
  id: string;
  filename: string;
  mime: string;
}

// Ссылку на файл держим ещё минуту после закрытия: её могли открыть в новой вкладке.
const KEEP_URL_MS = 60_000;

/** Открытый для просмотра файл: blob-ссылка, пока документ открыт; doc = null — ничего не открыто. */
export function useDocumentFile(doc: DocumentRef | null) {
  const file = useQuery({
    queryKey: ['document-file', doc?.id],
    queryFn: ({ signal }) => fetchDocument(doc!.id, doc!.mime, signal),
    enabled: Boolean(doc),
    staleTime: Infinity,
    gcTime: 0,
  });
  const blob = doc ? file.data : undefined;
  const url = useMemo(() => (blob ? URL.createObjectURL(blob) : null), [blob]);
  useEffect(() => () => void (url && setTimeout(() => URL.revokeObjectURL(url), KEEP_URL_MS)), [url]);

  return {
    url,
    error: doc && file.isError ? file.error.message : null,
    loading: Boolean(doc) && file.isPending,
    download: () => blob && doc && saveBlob(blob, doc.filename),
  };
}
