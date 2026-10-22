// Заглушки API для MSW по контракту (docs/api/openapi.json).
// Сценарий выбирается параметром в адресе страницы:
//   ?scenario=full   — все заявки (по умолчанию)
//   ?scenario=empty  — у клиента нет заявок
//   ?scenario=error  — заявки отвечают 500 (проверка плашек ошибки)
// Состояние живёт в db.ts: действия меняют заявки, «конвейер» двигает статусы сам.

import { delay, http, HttpResponse } from 'msw';
import type { DocumentKind } from '../api/types';
import { me, products } from './data';
import { buildSchedule } from './loanMath';
import { db, MockHttpError } from './db';

const API = '/api/v1';

function scenario(): string {
  return new URLSearchParams(window.location.search).get('scenario') ?? 'full';
}

function errorJson(status: number, code: string, message: string, field?: string) {
  return HttpResponse.json(field ? { code, message, field } : { code, message }, { status });
}

/** Выполняет операцию мока и превращает MockHttpError в ответ формата {code, message, field?}. */
async function respond<T>(run: () => T, { status = 200, wait = 300 } = {}) {
  await delay(wait);
  if (scenario() === 'error') return errorJson(500, 'internal_error', 'Сервис временно недоступен');
  try {
    return HttpResponse.json(run() as object, { status });
  } catch (error) {
    if (error instanceof MockHttpError) return errorJson(error.status, error.code, error.message, error.field);
    throw error;
  }
}

const key = (request: Request) => request.headers.get('Idempotency-Key');

export const handlers = [
  http.get(`${API}/auth/me`, async () => {
    await delay(200);
    return HttpResponse.json(me);
  }),

  http.get(`${API}/products`, async () => {
    await delay(200);
    return HttpResponse.json(products);
  }),

  http.get(`${API}/applications`, () =>
    respond(() => (scenario() === 'empty' ? [] : db.list()), { wait: 400 }),
  ),

  http.get(`${API}/applications/:id`, ({ params }) => respond(() => db.get(String(params.id)))),

  http.get(`${API}/applications/:id/history`, ({ params }) =>
    respond(() => db.history(String(params.id)), { wait: 250 }),
  ),

  http.get(`${API}/applications/:id/schedule`, ({ params, request }) =>
    respond(() => {
      const id = String(params.id);
      const offerId = new URL(request.url).searchParams.get('offer_id');
      const offers = db.offers(id);
      const offer =
        offers.find((o) => o.id === offerId) ??
        offers.find((o) => o.status === 'active') ??
        offers.find((o) => o.status === 'accepted');
      if (!offer) throw new MockHttpError(404, 'not_found', 'По заявке нет предложения');
      return buildSchedule(offer, new Date());
    }),
  ),

  http.post(`${API}/applications/:id/offers/:offerId/accept`, ({ params, request }) =>
    respond(() => db.accept(String(params.id), String(params.offerId), key(request)), { wait: 500 }),
  ),

  http.post(`${API}/applications/:id/offers/:offerId/decline`, ({ params, request }) =>
    respond(() => db.decline(String(params.id), String(params.offerId), key(request)), { wait: 500 }),
  ),

  http.post(`${API}/applications/:id/documents`, async ({ params, request }) => {
    const form = await request.formData();
    const file = form.get('file');
    const kind = form.get('kind');
    const infoRequestId = form.get('info_request_id');
    if (!(file instanceof File)) {
      await delay(200);
      return errorJson(422, 'validation_error', 'Выберите файл', 'file');
    }
    // Чем больше файл, тем дольше «загрузка» — чтобы было видно прогресс.
    const wait = Math.min(1500, 400 + file.size / 20_000);
    return respond(
      () =>
        db.upload(
          String(params.id),
          file,
          String(kind) as DocumentKind,
          typeof infoRequestId === 'string' && infoRequestId ? infoRequestId : null,
        ),
      { status: 201, wait },
    );
  }),

  http.get(`${API}/documents/:id`, async ({ params }) => {
    await delay(200);
    try {
      const { blob, doc } = db.file(String(params.id));
      return new HttpResponse(blob, {
        headers: {
          'Content-Type': doc.mime,
          'Content-Disposition': `attachment; filename*=UTF-8''${encodeURIComponent(doc.filename)}`,
        },
      });
    } catch (error) {
      if (error instanceof MockHttpError) return errorJson(error.status, error.code, error.message);
      throw error;
    }
  }),

  http.post(`${API}/applications/:id/resubmit`, ({ params, request }) =>
    respond(() => db.resubmit(String(params.id), key(request)), { wait: 500 }),
  ),

  http.post(`${API}/applications/:id/cancel`, ({ params, request }) =>
    respond(() => db.cancel(String(params.id), key(request)), { wait: 400 }),
  ),

  http.get(`${API}/feed`, async () => {
    await delay(300);
    const items = db.feed();
    return HttpResponse.json(scenario() === 'empty' ? items.filter((f) => f.kind === 'news') : items);
  }),

  http.post(`${API}/feed/events/:id/read`, () => new HttpResponse(null, { status: 204 })),
];
