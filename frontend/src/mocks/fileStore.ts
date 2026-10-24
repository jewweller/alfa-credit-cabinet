// Файлы, загруженные в моках, — в IndexedDB: в памяти страницы они пропадали при любой
// перезагрузке (F5, автообновление Vite), и документ в списке было уже не открыть.
// Недоступна IndexedDB (приватный режим) — файлы живут только до перезагрузки, как раньше.

const DB_NAME = 'mock-files';
const STORE = 'files';

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function run<T>(mode: IDBTransactionMode, action: (store: IDBObjectStore) => IDBRequest<T>): Promise<T | undefined> {
  try {
    const db = await open();
    return await new Promise<T>((resolve, reject) => {
      const request = action(db.transaction(STORE, mode).objectStore(STORE));
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    }).finally(() => db.close());
  } catch {
    return undefined;
  }
}

export const putFile = (id: string, blob: Blob) => run('readwrite', (store) => store.put(blob, id));
export const getFile = (id: string) => run<Blob | undefined>('readonly', (store) => store.get(id));
export const clearFiles = () => run('readwrite', (store) => store.clear());
