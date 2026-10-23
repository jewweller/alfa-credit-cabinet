import { documentUrl, readToken } from '../../api/client';

/**
 * Скачать файл заявки. Обычная ссылка не передаст токен, поэтому берём файл
 * запросом с заголовком Authorization и отдаём браузеру как загрузку.
 */
export async function downloadDocument(documentId: string, filename: string): Promise<void> {
  const token = readToken();
  const res = await fetch(documentUrl(documentId), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const url = URL.createObjectURL(await res.blob());
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
