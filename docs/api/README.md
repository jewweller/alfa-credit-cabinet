# Руководство по API

Описывает работающий API на 25.10.2026. **Источник истины — контракт** [openapi.json](openapi.json):
он генерируется из кода (`python -m app.openapi` в `backend/`), его актуальность проверяют тесты и
CI (`python -m app.openapi --check`). Здесь — как этим пользоваться; схемы полей смотрите в
контракте или в Swagger. Архитектура — [../architecture.md](../architecture.md), БД — [../data-model.md](../data-model.md).

| Что | Где |
| --- | --- |
| Swagger UI | `http://localhost:8000/api/docs` (в Docker также `http://localhost:8080/api/docs`) |
| Схема OpenAPI | `/api/openapi.json` (рабочая схема запущенного приложения) и файл `docs/api/openapi.json` (контракт: то же плюс пометки `x-implementation-status` и вводное описание) |
| Префикс | `/api/v1` (служебные `GET /health` и `GET /ready` есть и без префикса) |
| Операций | 32: 30 под `/api/v1` и 2 служебных без префикса (`/health`, `/ready`); у всех `x-implementation-status: implemented` |

## 1. Общие правила

- **Формат.** JSON, кодировка UTF-8; загрузка файла — `multipart/form-data`.
- **Деньги и ставки — строки** с двумя знаками после точки: `"3000000.00"`. Ставка — в процентах
  годовых: `"18.00"` = 18 %. Шаблон `^\d+\.\d{2}$`.
- **Идентификаторы** — UUID, **время** — ISO 8601 с часовым поясом.
- **Версия заявки.** `PATCH /applications/{id}` требует `version`, полученный последним `GET`.
  Если заявку уже изменили — 409 `version_conflict`.
- **Идемпотентность.** Заголовок `Idempotency-Key` принимают `submit`, `resubmit`, `cancel`,
  `accept`, `decline`, `signing/confirm` и `bank/.../decision`. **Ключ не хранится:** повтор
  действия получает 409 (статус уже сменился), дубля не создаётся, но и прежний ответ не
  повторяется.

## 2. Авторизация и роли

`POST /auth/login` выдаёт JWT; дальше он передаётся заголовком `Authorization: Bearer <токен>`.
Роль берётся из БД по пользователю из токена. Токен живёт 8 часов (`JWT_TTL_MINUTES`).

| Роль | Что может |
| --- | --- |
| `client` | своя компания: заявки, офферы, документы, подпись, график, лента, подбор продукта |
| `underwriter` | кабинет банка: очередь, карточка, **взять в работу и решение**, журнал, файлы и история любых заявок |
| `admin` | кабинет банка **только для просмотра** (очередь, карточка, журнал, история, файлы); `POST /admin/demo/reset`. «Взять в работу» и решение — 403 |

Клиент не видит чужих заявок: запрос чужой заявки отвечает **404**, как будто её нет. Чужой файл
(`GET /documents/{id}`) — **403**. Операции клиента (`createApplication`, `getFeed` и др.) для
сотрудника банка — 403.

```bash
TOKEN=$(curl -s -H 'Content-Type: application/json' \
  -d '{"email":"bakery@demo.local","password":"Demo2026!"}' \
  http://localhost:8000/api/v1/auth/login | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
```

```json
{"access_token": "eyJhbGciOiJIUzI1NiIs…", "token_type": "bearer"}
```

Учётки демо (пароль у всех `Demo2026!`): `bakery@`, `kovalev@`, `stroy@`, `melnikova@`,
`vektor@`, `mirage@`, `sboy@demo.local` — клиенты; `underwriter@demo.local`; `admin@demo.local`.

## 3. Ошибки

Любая ошибка — одного формата. Поле `field` есть, если ошибка относится к полю запроса.

```json
{"code": "validation_error", "message": "Выберите продукт", "field": "product_id"}
```

| HTTP | `code` | Когда |
| --- | --- | --- |
| 401 | `unauthorized` | нет токена, он недействителен или истёк, неверный пароль |
| 403 | `forbidden` | роль не подходит; чужой файл |
| 404 | `not_found` | нет такой заявки, оффера, файла, события — или она чужая |
| 404 | `company_not_found` | ИНН не найден в реестре |
| 405 | `method_not_allowed` | метод не поддерживается путём |
| 409 | `invalid_transition` | из текущего статуса действие не разрешено, в том числе повтор |
| 409 | `version_conflict` | заявку изменили, пока вы её редактировали |
| 409 | `conflict` | `PATCH` не в `DRAFT`; загрузка файла не в `INFO_REQUESTED` |
| 409 | `offer_not_active` | оффер уже принят, отклонён или заменён |
| 409 | `assigned_to_other` | заявку ведёт другой специалист |
| 409 | `demo_mode_disabled` | сброс демо при `DEMO_MODE=false` |
| 413 | `file_too_large` | файл больше 10 МБ |
| 415 | `unsupported_media_type` | не PDF, JPG или PNG, либо содержимое не совпадает с типом |
| 422 | `validation_error` | тело, параметры или проверка полноты; `field` указывает на поле |
| 422 | `documents_required` | `resubmit` без обязательных документов |
| 422 | `invalid_code` | код подписи неверный, истёк или попытки закончились |
| 503 | `upstream_unavailable` | реестр недоступен (`/companies/lookup`) или API не готов (`/ready`) |
| любой | `http_error` | прочие ошибки HTTP |

## 4. Операции

«Вход» — нужен ли токен; `Ключ` — принимает `Idempotency-Key`.

### Служебные и вход

| Метод и путь | Операция | Роль | Ключ |
| --- | --- | --- | --- |
| `GET /health`, `GET /api/v1/health` | `health` | без входа | |
| `GET /ready`, `GET /api/v1/ready` | `ready` | без входа | |
| `POST /api/v1/auth/login` | `login` | без входа | |
| `GET /api/v1/auth/me` | `getMe` | любая | |

### Каталог и подбор

| Метод и путь | Операция | Роль | Ключ |
| --- | --- | --- | --- |
| `GET /api/v1/products` | `listProducts` | любая | |
| `POST /api/v1/products/recommend` | `recommendProducts` | любая | |
| `GET /api/v1/companies/lookup?inn=` | `lookupCompany` | любая | |

### Заявка клиента

| Метод и путь | Операция | Роль | Ключ |
| --- | --- | --- | --- |
| `GET /api/v1/applications` | `listApplications` | client | |
| `POST /api/v1/applications` | `createApplication` | client | |
| `GET /api/v1/applications/{id}` | `getApplication` | client | |
| `PATCH /api/v1/applications/{id}` | `updateApplication` | client | |
| `POST /api/v1/applications/{id}/submit` | `submitApplication` | client | да |
| `POST /api/v1/applications/{id}/cancel` | `cancelApplication` | client | да |
| `POST /api/v1/applications/{id}/resubmit` | `resubmitApplication` | client | да |
| `GET /api/v1/applications/{id}/history` | `getApplicationHistory` | client (своя), банк (любая) | |
| `POST /api/v1/applications/{id}/documents` | `uploadDocument` | client | |
| `GET /api/v1/documents/{id}` | `downloadDocument` | client (свой), банк (любой) | |

### Оффер, подпись, график

| Метод и путь | Операция | Роль | Ключ |
| --- | --- | --- | --- |
| `POST /api/v1/applications/{id}/offers/{offer_id}/accept` | `acceptOffer` | client | да |
| `POST /api/v1/applications/{id}/offers/{offer_id}/decline` | `declineOffer` | client | да |
| `POST /api/v1/applications/{id}/signing/code` | `createSigningCode` | client | |
| `POST /api/v1/applications/{id}/signing/confirm` | `confirmSigning` | client | да |
| `GET /api/v1/applications/{id}/schedule` | `getPaymentSchedule` | client | |

### Лента

| Метод и путь | Операция | Роль | Ключ |
| --- | --- | --- | --- |
| `GET /api/v1/feed` | `getFeed` | client | |
| `POST /api/v1/feed/events/{id}/read` | `markFeedEventRead` | client | |

### Банк и администратор

| Метод и путь | Операция | Роль | Ключ |
| --- | --- | --- | --- |
| `GET /api/v1/bank/applications` | `listBankApplications` | underwriter, admin | |
| `GET /api/v1/bank/applications/{id}` | `getBankApplication` | underwriter, admin | |
| `POST /api/v1/bank/applications/{id}/assign` | `assignBankApplication` | **underwriter** | |
| `POST /api/v1/bank/applications/{id}/decision` | `decideBankApplication` | **underwriter** | да |
| `GET /api/v1/bank/audit` | `listAuditEntries` | underwriter, admin | |
| `POST /api/v1/admin/demo/reset` | `resetDemo` | **admin** | |

## 5. Путь заявки

### Подбор продукта

```bash
curl -s -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"purpose":"working_capital","amount":"3000000.00","term_months":12}' \
  http://localhost:8000/api/v1/products/recommend
```

Цели: `working_capital`, `equipment`, `cash_gap`. Ответ — до трёх продуктов; сумма и срок
приведены к лимитам продукта, что изменено — в `adjusted`; сначала подходящие без изменений, затем
с меньшим платежом.

```json
[{"product": {"code": "EXPRESS_WC", "name": "Экспресс-оборот", "base_rate": "18.00", "…": "…"},
  "amount": "3000000.00", "term_months": 12, "rate": "18.00",
  "monthly_payment": "275039.98", "adjusted": []}]
```

### Черновик, правка, отправка

1. `POST /applications` с телом `{}` создаёт черновик (`status: DRAFT`, `number: "0001"`). Компания —
   компания текущего пользователя; ИНН в запросе нет.
2. `PATCH /applications/{id}` — автосохранение. Тело: `version` (обязательно) и изменяемые поля:
   `product_id`, `amount`, `term_months`, `purpose`, `revenue_12m`, `existing_payments_monthly`,
   `bki_consent`. Изменять можно только черновик.
3. `POST /applications/{id}/submit` проверяет полноту (422 с `field` у неполного поля) и сразу
   проводит заявку через обогащение, скоринг и решение. **Ответ уже содержит итоговый статус**,
   фонового ожидания нет.

```json
{"status": "APPROVED",
 "decision": {"outcome": "approved", "decided_by": "system", "reason_code": null,
              "decided_at": "2026-10-25T08:33:52.162643Z"},
 "active_offer": {"id": "b217…", "amount": "3000000.00", "term_months": 12, "rate": "18.00",
                  "monthly_payment": "275039.98", "status": "active", "…": "…"}}
```

Исходы: `APPROVED`, `COUNTER_OFFER`, `REJECTED`, `INFO_REQUESTED` (нужны документы),
`MANUAL_REVIEW` (ждёт специалиста). `decision.reason_code` — причина отказа
(`company_inactive`, `bankruptcy_or_overdue`, `low_score`, `no_suitable_terms`,
`underwriter_decision`); баллы и сработавшие правила клиенту не показываются.
`active_offer` — последний оффер: после `accept` он остаётся в ответе со `status: accepted`.
Ошибки: повторный `submit` — 409 `invalid_transition`; неполная анкета —
`{"code": "validation_error", "message": "Выберите продукт", "field": "product_id"}`.

`GET /applications/{id}/history` возвращает таймлайн
`[{from_status, to_status, actor_type, created_at}]`: переход `SUBMITTED → ENRICHMENT → SCORING →
исход` пишет `actor_type: system`.

### Запрос документов

В статусе `INFO_REQUESTED` заявка содержит `info_request` со списком пунктов. Клиент загружает
файлы и вызывает `POST /applications/{id}/resubmit`: если обязательные пункты закрыты — конвейер
идёт заново (обычно итог `MANUAL_REVIEW`), иначе 422 `documents_required`. Заявку в этом
статусе можно отозвать (`cancel`).

### Оффер, подпись, график

- `POST …/offers/{offer_id}/accept` → `SIGNING`; `…/decline` → `DECLINED_BY_CLIENT`. Ответить можно
  один раз: повтор — 409 `offer_not_active`.
- `POST …/signing/code` → `{"code": "482915", "expires_at": "…"}` (симуляция ПЭП: код показывается
  в интерфейсе). Код 6 цифр, действует 5 минут, новый запрос заменяет прежний.
- `POST …/signing/confirm` с телом `{"code": "482915"}` → **сразу `ISSUED`**: подпись и выдача
  проходят в одном запросе (в истории `SIGNING → SIGNED → ISSUED`). Неверный код — 422
  `invalid_code`; на один код 5 попыток.
- `GET …/schedule[?offer_id=]` — аннуитетный график. Суммы до копейки, последний платёж закрывает
  остаток; после выдачи даты считаются от даты выдачи, до неё — от текущей.

```json
{"offer_id": "b217…", "amount": "3000000.00", "term_months": 12, "rate": "18.00",
 "monthly_payment": "275039.98", "total_payment": "3300479.74", "overpayment": "300479.74",
 "items": [{"number": 1, "due_date": "2026-11-25", "payment": "275039.98",
            "principal": "230039.98", "interest": "45000.00", "balance": "2769960.02"}, "…"]}
```

## 6. Документы

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  -F kind=tax_return -F 'file=@declaration.pdf;type=application/pdf' \
  http://localhost:8000/api/v1/applications/$ID/documents
```

- Поля формы: `kind` (`tax_return`, `bank_statement`, `financial_statements`, `contract`,
  `other`), `file`, необязательный `info_request_id`.
- Загрузка разрешена **только в статусе `INFO_REQUESTED`**, иначе 409 `conflict`.
- PDF, JPG или PNG до 10 МБ; проверяются тип и начало файла. 413 `file_too_large`, 415
  `unsupported_media_type`, пустой файл — 422.
- Пункт запроса R4 «Декларация или выписка» закрывается файлом вида `tax_return` **или**
  `bank_statement`.
- `GET /documents/{id}` отдаёт файл с исходным именем в `Content-Disposition`. Клиент скачивает
  свои файлы, сотрудники банка — любые; чужой файл — 403.

## 7. Лента

`GET /feed[?kind=event|news][&news_limit=1..30]` (по умолчанию 10 новостей). Сверху все события
по заявкам клиента, свежие первыми; ниже новости по убыванию `score`.

```json
{"items": [
   {"kind": "event", "title": "Заявка №0001 одобрена", "status": "APPROVED", "read": false,
    "reasons": [], "score": null, "…": "…"},
   {"kind": "news", "title": "Что проверить перед подписанием договора", "read": true,
    "reasons": [{"code": "status", "text": "Подсказка к текущему этапу вашей заявки"}],
    "score": 0.7096, "…": "…"}],
 "ranking": {"method": "ml", "model_version": "feed-logreg-1.0.0"}}
```

- **`ranking.method`**: `ml` — порядок задала модель, `model_version` — её версия
  (`feed-logreg-1.0.0`); `rules` — порядок по формуле плана (`feed-rules-1.0`). Метод `rules`
  означает либо `ML_RANKING_ENABLED=false`, либо **откат**: модель недоступна, не успела за 1 с или
  вернула некорректный ответ. Клиент в этом случае получает ту же ленту.
- **`reasons`** — «Почему вы это видите»: у новости одна-две причины (`okved`, `status`, `product`,
  `segment`, `general`), текст до 120 символов; у событий пусто. Причину модели бэкенд принимает,
  только если её код совпал с реальным совпадением новости с профилем; иначе показывает причины правил.
- **`score`** — вес в выбранном методе: у `rules` сумма весов формулы (может быть больше 1), у
  `ml` — сигмоида оценки модели (между 0 и 1); сравнивать числа разных методов нельзя.
- События создаются при смене статуса заявки. `POST /feed/events/{id}/read` → 204, повтор
  безвреден, чужое событие — 404.

## 8. Кабинет банка

- **Очередь** `GET /bank/applications[?status=…&status=…][&grade=A][&product_id=…]`: без
  черновиков, сначала `MANUAL_REVIEW` (дольше ждущие выше), затем остальные, свежие сверху.
- **Карточка** `GET /bank/applications/{id}`: заявка, компания, данные реестра, **последний ответ
  каждого источника** (`status: ok | not_found | error`, `attempts`), скоринг F1–F6 с
  понятными значениями, трасса правил R1–R10 и последнее решение с исполнителем и комментарием.
- **Взять в работу** `POST …/assign`: только в `MANUAL_REVIEW`; повтор тем же специалистом ничего
  не меняет; заявку другого — 409 `assigned_to_other`.
- **Решение** `POST …/decision` — только в `MANUAL_REVIEW`; какие поля нужны, зависит от `outcome`:

| `outcome` | Обязательные поля | Результат |
| --- | --- | --- |
| `approved` | `rate` (> 0) | `APPROVED`, оффер на сумму и срок из заявки |
| `counter_offer` | `product_id`, `amount`, `term_months`, `rate` | `COUNTER_OFFER`; сумма и срок — в лимитах продукта, иначе 422 с `field` |
| `info_requested` | `info_items` (≥ 1), `comment` | `INFO_REQUESTED`; `comment` — сообщение клиенту |
| `rejected` | `reason_code` | `REJECTED` |

  Необязательный `comment` (до 1000 символов) у остальных исходов — внутренний, клиент его не видит.
  Решить можно и без «взять в работу»: заявка закрепляется за тем, кто решил.
- **Журнал** `GET /bank/audit[?application_id=][&action=…][&actor_role=][&before=][&limit=]`:
  свежие сверху, `limit` от 1 до 500 (по умолчанию 100), следующая страница — `before` равный
  `created_at` последней записи. Журнал только дописывается.

```json
[{"id": "9e9e…", "created_at": "2026-10-25T08:33:52.158602Z", "action": "application.submitted",
  "actor_role": "client", "actor_name": "Ирина Соколова", "application_number": "0001",
  "summary": "DRAFT → SUBMITTED", "details": {"from_status": "DRAFT", "to_status": "SUBMITTED"},
  "ip": "172.19.0.1", "…": "…"}]
```

- **Сброс демо** `POST /admin/demo/reset` (только `admin`) → `{"reset_at": …,
  "applications_deleted": N}`. Удаляет все заявки со связанными строками и файлами; учётки,
  компании, продукты и журнал остаются, в журнал дописывается `demo.reset`. Без `DEMO_MODE=true`
  — 409 `demo_mode_disabled`. Повторный вызов безопасен.

## 9. Готовность

`GET /ready` → `{"status": "ready", "checks": {"database": "ok", "migrations": "ok",
"fixtures": "ok", "news": "ok"}}`. Если что-то не прошло — 503 `upstream_unavailable`, в
`message` перечислено, что именно (`API не готов: migrations`). Это же проверяет healthcheck
контейнера `api`.

## 10. Контракт и его проверка

```bash
cd backend
uv run python -m app.openapi            # перегенерировать docs/api/openapi.json
uv run python -m app.openapi --check    # проверить, что файл соответствует коду
```

Правила, которых нет в плане, решены командой backend и аналитиком не подтверждены: решения и
их статус — [../analyst-questions.md](../analyst-questions.md). Пометки `TBD` из описаний контракта
убраны: они заменены фактическим поведением с отсылкой к номеру решения (A1–A9, B4, K4, M6).
