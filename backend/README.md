# Backend

API «Умного кредитного кабинета»: FastAPI, SQLAlchemy 2, PostgreSQL 16, Alembic. Python 3.12,
зависимости зафиксированы в `uv.lock`.

Подробнее: [архитектура](../docs/architecture.md) · [модель данных](../docs/data-model.md) ·
[руководство по API](../docs/api/README.md) · [контракт OpenAPI](../docs/api/openapi.json) ·
[решения, принятые без аналитика](../docs/analyst-questions.md).

## Запуск

Основной способ — Docker Compose из корня репозитория (поднимает `db`, `api`, `frontend`):

```bash
cp .env.example .env          # затем задайте свои JWT_SECRET и POSTGRES_PASSWORD
docker compose up --build
```

- Фронт — `http://localhost:8080`, API — `http://127.0.0.1:8000`, Swagger — `/api/docs`.
- При старте контейнера `api`: `alembic upgrade head` → `python -m app.seed` → uvicorn.
- Готовность: `GET /ready` (его же проверяет healthcheck контейнера).
- Демо-учётки (пароль у всех `Demo2026!`): клиенты `bakery@`, `kovalev@`, `stroy@`, `melnikova@`,
  `vektor@`, `mirage@`, `sboy@demo.local`; `underwriter@demo.local`; `admin@demo.local`.
- Сброс демо перед показом: `POST /api/v1/admin/demo/reset` от имени `admin` (нужен `DEMO_MODE=true`).

## Переменные окружения

Секреты задаются только в окружении (`.env` не коммитится). Значения по умолчанию в таблице — из
кода (`app/config.py`); где `docker-compose.yml` задаёт другое, указано отдельно.

| Переменная | По умолчанию | Назначение |
| --- | --- | --- |
| `DATABASE_URL` | — | `postgresql+psycopg://user:password@host:5432/db`; без неё работает только `/health` |
| `JWT_SECRET` | — | подпись токенов, не короче 32 символов; **обязательна** (compose не стартует без неё) |
| `JWT_TTL_MINUTES` | `480` | срок жизни токена |
| `BCRYPT_ROUNDS` | `12` | стоимость bcrypt (в тестах снижена до 4) |
| `APP_ENV` | `local` | `local` / `test` / `demo` / `prod` |
| `LOG_LEVEL` | `INFO` | уровень логов |
| `SEED_DEMO_DATA` | `false` (в compose — `true`) | загружать учётки, компании и продукты из `seed/` |
| `SEED_DIR` | `seed/` | каталог демо-данных и `news.json` (в compose — `/seed`) |
| `FIXTURES_DIR` | `mocks/fixtures/` | ответы ЕГРЮЛ, ЕГРИП, ФНС, БКИ (в compose — `/fixtures`) |
| `UPLOADS_DIR` | `<tmp>/alfa-credit-uploads` | файлы клиентов (в compose — том `uploads`, `/uploads`) |
| `DEMO_MODE` | `false` (в compose — `true`) | разрешает `POST /admin/demo/reset`; на общем стенде — `false` |
| `ML_RANKING_ENABLED` | `false` (в compose — `true`) | порядок новостей ленты задаёт модель из `ml/`; при сбое — правила |
| `ML_TIMEOUT_SEC` | `1.0` | таймаут вызова модели, секунды |

Переменные только для compose: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `API_PORT`
(по умолчанию 8000), `WEB_PORT` (8080), `VITE_API_MODE`, `VITE_USE_MOCKS`, `VITE_DEMO_MODE`
(см. `.env.example`).

## Разработка

Нужны [uv](https://docs.astral.sh/uv/) и Python 3.12. Команды — из каталога `backend/`:

```bash
uv sync --frozen                                # зависимости строго по uv.lock
uv run --frozen pytest -q                       # тесты: SQLite в памяти, PostgreSQL не нужен
uv run --frozen ruff check . ../ml              # линтер (backend и модель ленты)
uv run --frozen ruff format --check . ../ml     # формат
uv run --frozen python -m app.openapi --check   # docs/api/openapi.json соответствует коду
uv run --frozen python -m app.openapi           # перегенерировать контракт
```

Те же проверки запускает CI (`.github/workflows/backend.yml`); вторым заданием он прогоняет
`alembic upgrade → downgrade base → upgrade` на PostgreSQL 16.4.

Миграции (нужна `DATABASE_URL`):

```bash
uv run --frozen alembic upgrade head            # применить все
uv run --frozen alembic downgrade -1            # откатить последнюю
uv run --frozen alembic history                 # цепочка 0001 → 0007
uv run --frozen python -m app.seed              # демо-данные (при SEED_DEMO_DATA=true)
```

## Структура

| Каталог | Что внутри |
| --- | --- |
| `app/api/` | маршруты (`v1/router.py`), роли и зависимости (`deps.py`), формат ошибок |
| `app/services/` | сценарии: заявки, конвейер, офферы, документы, подпись, банк, лента, журнал |
| `app/domain/` | машина состояний, аннуитет, ИНН, формула и тексты ленты |
| `app/scoring/`, `app/decision/` | скоринг F1–F6 и правила R1–R10; пороги — `scoring/config.yaml` |
| `app/integrations/` | источники данных (`SourceClient`); сейчас — фикстуры `mocks/fixtures/` |
| `app/schemas/` | схемы запросов и ответов, из них строится контракт |
| `app/db/`, `alembic/` | модели SQLAlchemy и миграции |
| `tests/` | `unit/`, `api/`, `contract/` |

Модель ранжирования ленты лежит вне `backend/`, в [`ml/`](../ml/README.md); в образ `api` она
копируется через `additional_contexts` в `docker-compose.yml`, поэтому `backend/Dockerfile`
собирается через `docker compose`. Отдельная команда `docker build ./backend` падает (Docker
ищет образ `ml` в реестре); с явным контекстом работает:

```bash
docker build --build-context ml=./ml ./backend    # из корня репозитория
```
