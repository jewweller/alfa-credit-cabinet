import type { ApiErrorBody } from './types';

const BASE_URL = '/api/v1';
const TOKEN_KEY = 'access_token';

export class ApiError extends Error {
  readonly status: number;
  readonly body: ApiErrorBody | null;

  constructor(status: number, body: ApiErrorBody | null) {
    super(body?.message ?? `HTTP ${status}`);
    this.status = status;
    this.body = body;
  }
}

export function readToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    // хранилище недоступно — токена там и нет
  }
}

function authHeaders(): Record<string, string> {
  const token = readToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let body: ApiErrorBody | null = null;
    try {
      body = (await res.json()) as ApiErrorBody;
    } catch {
      // тело не JSON — оставляем null
    }
    throw new ApiError(res.status, body);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(BASE_URL + path, {
    headers: { Accept: 'application/json', ...authHeaders() },
    signal,
  });
  return parse<T>(res);
}

/**
 * POST, меняющий состояние. Idempotency-Key защищает от двойного клика (план, раздел 9):
 * один ключ на одно намерение пользователя, повтор с тем же ключом не создаёт дубль.
 */
export async function apiPost<T>(
  path: string,
  options: { body?: unknown; idempotencyKey?: string } = {},
): Promise<T> {
  const res = await fetch(BASE_URL + path, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      ...(options.body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(options.idempotencyKey ? { 'Idempotency-Key': options.idempotencyKey } : {}),
      ...authHeaders(),
    },
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });
  return parse<T>(res);
}

/** multipart/form-data — Content-Type с границей браузер ставит сам. */
export async function apiUpload<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(BASE_URL + path, {
    method: 'POST',
    headers: { Accept: 'application/json', ...authHeaders() },
    body: form,
  });
  return parse<T>(res);
}

export function newIdempotencyKey(): string {
  return crypto.randomUUID();
}

export function documentUrl(documentId: string): string {
  return `${BASE_URL}/documents/${documentId}`;
}
