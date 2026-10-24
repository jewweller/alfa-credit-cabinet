// Заглушки API для MSW по контракту (docs/api/openapi.json).
// Вход — демо-учётками из плана (раздел 14), пароль у всех Demo2026!.
// Сценарий выбирается параметром в адресе страницы:
//   ?scenario=full           — все заявки (по умолчанию)
//   ?scenario=empty          — у клиента нет заявок
//   ?scenario=error          — заявки отвечают 500 (проверка плашек ошибки)
//   ?scenario=registry_down  — реестр ЕГРЮЛ/ЕГРИП не отвечает (503)
// Состояние живёт в db.ts: действия меняют заявки, «конвейер» двигает статусы сам.

import { delay, http, HttpResponse } from 'msw';
import type {
  ApplicationCreate,
  ApplicationUpdate,
  DocumentKind,
  LoginRequest,
  Me,
  ProductRecommendRequest,
  UnderwriterDecisionRequest,
} from '../api/types';
import { DEMO_PASSWORD, products, registry, users } from './data';
import { buildSchedule } from './loanMath';
import { db, MockHttpError } from './db';
import { apiMode } from './mode';
import { recommend } from './recommend';

const API = '/api/v1';
const TOKEN_PREFIX = 'mock-token.';

function scenario(): string {
  return new URLSearchParams(window.location.search).get('scenario') ?? 'full';
}

function errorJson(status: number, code: string, message: string, field?: string) {
  return HttpResponse.json(field ? { code, message, field } : { code, message }, { status });
}

/**
 * В смешанном режиме вход настоящий и токен — JWT бэкенда. Подпись проверяет бэкенд;
 * мок только берёт id пользователя (`sub`): id демо-учёток совпадают с seed/users.json.
 */
function userFromJwt(token: string): Me | null {
  const payload = token.split('.')[1];
  if (!payload) return null;
  try {
    const claims = JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/'))) as { sub?: string };
    return users.find((u) => u.id === claims.sub) ?? null;
  } catch {
    return null;
  }
}

/** Токен мока — «mock-token.<email>», по нему находим демо-учётку; иначе пробуем JWT. */
function currentUser(request: Request): Me | null {
  const header = request.headers.get('Authorization') ?? '';
  const prefix = `Bearer ${TOKEN_PREFIX}`;
  if (header.startsWith(prefix)) {
    const email = header.slice(prefix.length);
    return users.find((u) => u.email === email) ?? null;
  }
  return header.startsWith('Bearer ') ? userFromJwt(header.slice('Bearer '.length)) : null;
}

/** Клиент с компанией; сотрудникам банка клиентские операции недоступны. */
function clientOf(user: Me): Me & { company: NonNullable<Me['company']> } {
  if (user.role !== 'client' || !user.company) {
    throw new MockHttpError(403, 'forbidden', 'Операция доступна только клиенту');
  }
  return user as Me & { company: NonNullable<Me['company']> };
}

/**
 * Выполняет операцию мока от имени вошедшего пользователя и превращает
 * MockHttpError в ответ формата {code, message, field?}.
 */
async function respond<T>(request: Request, run: (user: Me) => T, { status = 200, wait = 300 } = {}) {
  await delay(wait);
  const user = currentUser(request);
  if (!user) return errorJson(401, 'unauthorized', 'Войдите заново');
  try {
    return HttpResponse.json(run(user) as object, { status });
  } catch (error) {
    if (error instanceof MockHttpError) return errorJson(error.status, error.code, error.message, error.field);
    throw error;
  }
}

/** Операция над заявкой своей компании. */
function own<T>(request: Request, id: unknown, run: (id: string, user: Me) => T, options?: { status?: number; wait?: number }) {
  return respond(
    request,
    (user) => {
      const appId = String(id);
      db.assertOwner(appId, clientOf(user).company.id);
      return run(appId, user);
    },
    options,
  );
}

/** Сотрудник банка (underwriter, admin); клиенту кабинет банка недоступен. */
function bankOnly(user: Me) {
  if (user.role === 'client') {
    throw new MockHttpError(403, 'forbidden', 'Операция доступна только сотрудникам банка');
  }
}

/** Взять в работу и решить может только кредитный специалист: решение админа история записала бы как underwriter. */
function underwriterOnly(user: Me) {
  if (user.role !== 'underwriter') {
    throw new MockHttpError(403, 'forbidden', 'Операция доступна только кредитному специалисту');
  }
}

function adminOnly(user: Me) {
  if (user.role !== 'admin') throw new MockHttpError(403, 'forbidden', 'Операция доступна только администратору');
}

/** Операция кабинета банка над любой заявкой. */
function bank<T>(request: Request, run: (user: Me) => T, options?: { status?: number; wait?: number }) {
  return respond(
    request,
    (user) => {
      bankOnly(user);
      return run(user);
    },
    options,
  );
}

const key = (request: Request) => request.headers.get('Idempotency-Key');

export const handlers = [
  http.post(`${API}/auth/login`, async ({ request }) => {
    await delay(500);
    const body = (await request.json()) as Partial<LoginRequest>;
    const email = body.email?.trim().toLowerCase() ?? '';
    const user = users.find((u) => u.email === email);
    if (!user || body.password !== DEMO_PASSWORD) {
      db.logLogin(null, email);
      return errorJson(401, 'unauthorized', 'Неверный email или пароль');
    }
    db.logLogin(user, email);
    return HttpResponse.json({ access_token: TOKEN_PREFIX + user.email, token_type: 'bearer' });
  }),

  http.get(`${API}/auth/me`, ({ request }) => respond(request, (user) => user, { wait: 200 })),

  http.get(`${API}/products`, ({ request }) => respond(request, () => products, { wait: 200 })),

  http.post(`${API}/products/recommend`, async ({ request }) => {
    const body = (await request.json()) as Partial<ProductRecommendRequest>;
    return respond(request, () => recommend(body), { wait: 350 });
  }),

  http.get(`${API}/companies/lookup`, ({ request }) =>
    respond(
      request,
      () => {
        if (scenario() === 'registry_down') {
          throw new MockHttpError(503, 'upstream_unavailable', 'Реестр ФНС сейчас не отвечает');
        }
        const inn = new URL(request.url).searchParams.get('inn') ?? '';
        if (!/^(\d{10}|\d{12})$/.test(inn)) {
          throw new MockHttpError(422, 'validation_error', 'ИНН — 10 или 12 цифр', 'inn');
        }
        const company = registry.find((c) => c.inn === inn);
        if (!company) throw new MockHttpError(404, 'company_not_found', 'Компания не найдена в реестре');
        return company;
      },
      { wait: 700 },
    ),
  ),

  http.get(`${API}/applications`, ({ request }) =>
    respond(
      request,
      (user) => {
        if (scenario() === 'error') throw new MockHttpError(500, 'internal_error', 'Сервис временно недоступен');
        return scenario() === 'empty' ? [] : db.list(clientOf(user).company.id);
      },
      { wait: 400 },
    ),
  ),

  http.post(`${API}/applications`, async ({ request }) => {
    const body = (await request.json()) as ApplicationCreate;
    return respond(request, (user) => db.create(clientOf(user), body), { status: 201, wait: 400 });
  }),

  http.get(`${API}/applications/:id`, ({ request, params }) => own(request, params.id, (id) => db.get(id))),

  http.patch(`${API}/applications/:id`, async ({ request, params }) => {
    const body = (await request.json()) as ApplicationUpdate;
    return own(request, params.id, (id) => db.update(id, body), { wait: 250 });
  }),

  http.post(`${API}/applications/:id/submit`, ({ request, params }) =>
    own(request, params.id, (id) => db.submit(id, key(request)), { wait: 600 }),
  ),

  // Историю видит и клиент (своя заявка), и сотрудник банка (план, раздел 10).
  http.get(`${API}/applications/:id/history`, ({ request, params }) =>
    respond(
      request,
      (user) => {
        if (user.role === 'client') db.assertOwner(String(params.id), clientOf(user).company.id);
        return db.history(String(params.id));
      },
      { wait: 250 },
    ),
  ),

  http.get(`${API}/applications/:id/schedule`, ({ request, params }) =>
    own(request, params.id, (id) => {
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

  http.post(`${API}/applications/:id/offers/:offerId/accept`, ({ request, params }) =>
    own(request, params.id, (id) => db.accept(id, String(params.offerId), key(request)), { wait: 500 }),
  ),

  http.post(`${API}/applications/:id/offers/:offerId/decline`, ({ request, params }) =>
    own(request, params.id, (id) => db.decline(id, String(params.offerId), key(request)), { wait: 500 }),
  ),

  http.post(`${API}/applications/:id/signing/code`, ({ request, params }) =>
    own(request, params.id, (id) => db.signingCode(id), { wait: 400 }),
  ),

  http.post(`${API}/applications/:id/signing/confirm`, async ({ request, params }) => {
    const body = (await request.json()) as { code?: string };
    return own(request, params.id, (id) => db.confirmSigning(id, String(body.code ?? ''), key(request)), { wait: 500 });
  }),

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
    return own(
      request,
      params.id,
      (id) =>
        db.upload(
          id,
          file,
          String(kind) as DocumentKind,
          typeof infoRequestId === 'string' && infoRequestId ? infoRequestId : null,
        ),
      { status: 201, wait },
    );
  }),

  http.get(`${API}/documents/:id`, async ({ params, request }) => {
    await delay(200);
    const user = currentUser(request);
    if (!user) return errorJson(401, 'unauthorized', 'Войдите заново');
    try {
      const { blob, doc } = db.file(String(params.id), user);
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

  http.post(`${API}/applications/:id/resubmit`, ({ request, params }) =>
    own(request, params.id, (id) => db.resubmit(id, key(request)), { wait: 500 }),
  ),

  http.post(`${API}/applications/:id/cancel`, ({ request, params }) =>
    own(request, params.id, (id) => db.cancel(id, key(request)), { wait: 400 }),
  ),

  // ── Кабинет банка (B2–B4) ──

  http.get(`${API}/bank/applications`, ({ request }) =>
    bank(request, () => {
      const params = new URL(request.url).searchParams;
      return db.bankList({ status: params.getAll('status'), grade: params.get('grade'), productId: params.get('product_id') });
    }),
  ),

  http.get(`${API}/bank/applications/:id`, ({ request, params }) => bank(request, () => db.bankDetail(String(params.id)))),

  http.post(`${API}/bank/applications/:id/assign`, ({ request, params }) =>
    bank(
      request,
      (user) => {
        underwriterOnly(user);
        return db.assign(String(params.id), user);
      },
      { wait: 400 },
    ),
  ),

  http.post(`${API}/bank/applications/:id/decision`, async ({ request, params }) => {
    const body = (await request.json()) as UnderwriterDecisionRequest;
    return bank(
      request,
      (user) => {
        underwriterOnly(user);
        return db.bankDecide(String(params.id), user, body, key(request));
      },
      { wait: 600 },
    );
  }),

  // ── Журнал и сброс демо ──

  http.get(`${API}/bank/audit`, ({ request }) =>
    bank(request, () => {
      const params = new URL(request.url).searchParams;
      return db.audit({
        applicationId: params.get('application_id'),
        actions: params.getAll('action'),
        actorRole: params.get('actor_role'),
        before: params.get('before'),
        limit: Math.min(500, Number(params.get('limit') ?? 100) || 100),
      });
    }),
  ),

  http.post(`${API}/admin/demo/reset`, ({ request }) =>
    respond(
      request,
      (user) => {
        adminOnly(user);
        return db.demoReset(user);
      },
      { wait: 700 },
    ),
  ),

  http.get(`${API}/feed`, ({ request }) =>
    respond(
      request,
      (user) => {
        const items = db.feed(clientOf(user).company.id);
        // В mixed заявки настоящие, а события моков — про выдуманные: оставляем только новости.
        const newsOnly = scenario() === 'empty' || apiMode() === 'mixed';
        return newsOnly ? items.filter((f) => f.kind === 'news') : items;
      },
      { wait: 300 },
    ),
  ),

  http.post(`${API}/feed/events/:id/read`, () => new HttpResponse(null, { status: 204 })),
];
