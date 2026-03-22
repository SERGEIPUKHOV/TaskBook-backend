# MODULE CONTRACT: Core Infrastructure

## Назначение
Инфраструктурный слой backend.
Конфигурация, async DB доступ, JWT/cookie security, Redis client, rate limiting, logging и observability.

## Ответственность
- Загружать настройки из env через единый объект `settings`.
- Создавать async engine и `AsyncSessionLocal`.
- Выдавать и проверять JWT, хешировать пароли.
- Управлять auth cookies для browser flows.
- Давать Redis client и простые cache invalidation helpers.
- Подключать logging, Sentry и rate-limit primitives.

## Граница (что НЕ делает этот модуль)
- Не должен хранить предметную бизнес-логику продукта.
- Не должен знать о конкретных страницах frontend/admin.
- Не должен определять API routes.
- Не должен выполнять domain-specific ORM запросы вместо service layer.

## Структура
| Файл | Роль |
|---|---|
| `config.py` | `Settings`, env parsing, derived flags |
| `database.py` | `engine`, `AsyncSessionLocal`, `get_db`, `init_models` |
| `security.py` | JWT helpers и password hashing |
| `auth_cookies.py` | Set/clear browser auth cookies |
| `redis.py` | Redis client creation и in-memory fallback |
| `rate_limit.py` | IP extraction и rate-limit middleware support |
| `logging.py` | Logging setup |
| `observability.py` | Sentry initialization |

## Зависимости
- `pydantic-settings`
- `sqlalchemy[asyncio]`
- `redis.asyncio`
- `python-jose`
- `passlib`
- `fastapi`
- `sentry-sdk`

## Инварианты
- `settings` - единая точка чтения runtime configuration.
- DB access строится на `AsyncSession`; sync session paths не являются supported pattern.
- JWT types `access`, `refresh`, `reset` создаются и декодируются только через helpers этого слоя.
- Cookie names и cookie security flags берутся из `settings`, а не хардкодятся в route handlers.
- При отсутствии рабочего `REDIS_URL` допускается `InMemoryRedis` fallback для локального режима.

## Экспортируемый интерфейс
- `settings`
- `engine`, `AsyncSessionLocal`, `get_db`, `init_models`
- `hash_password`, `verify_password`, `create_access_token`, `create_refresh_token`, `create_reset_token`, `decode_token`
- `set_auth_cookies`, `clear_auth_cookies`
- `redis_client`, `invalidate_keys`

## Критичные точки изменения
- Любые изменения в `config.py`, `security.py`, `database.py` и `auth_cookies.py` могут затронуть весь backend.
- Изменение значений cookie/JWT контрактов требует синхронной проверки frontend middleware и auth flows.
