# MODULE CONTRACT: Services Layer

## Назначение
Предметная логика TaskBook.
Слой orchestrates операции с моделями, валидацию периода, агрегации bundle, auth/session сценарии и calendar integration flows.

## Ответственность
- Выполнять user-scoped CRUD и domain операции поверх `AsyncSession`.
- Собирать week/month/day bundles из нескольких сущностей.
- Инкапсулировать auth logic: регистрация, логин, refresh, logout, reset password, seed users.
- Централизовать расчёты периода и ISO week helpers.
- Синхронизировать внешние календарные события, управлять импортом события в planner через backend-owned link layer, публиковать opt-in задачи в ICS feeds и делать best-effort write-back имени и weekly RRULE в Google Calendar.

## Граница (что НЕ делает этот модуль)
- Не объявляет HTTP routes и не работает с FastAPI `Request`/`Response`.
- Не хранит infra-конфигурацию, cookie политику и startup wiring.
- Не рендерит UI и не знает о React/Next/Vite.
- Не должен обходить `core.database` прямыми sync-коннектами.

## Структура
| Файл | Роль |
|---|---|
| `auth_service.py` | Auth flows, refresh token state, seed users |
| `task_service.py` | CRUD задач, статусы по дням, reorder |
| `week_service.py` | Get/create week, update week, carry-over tasks |
| `month_service.py` | Month plan CRUD |
| `habit_service.py` | Привычки и habit logs |
| `daily_state_service.py` | Метрики состояния по дням |
| `day_entry_service.py` | Key events и gratitudes |
| `day_service.py` | Day bundle aggregation |
| `bundle_service.py` | Month/week bundle aggregation |
| `dashboard_service.py` | Dashboard summary |
| `periods.py` | Month/week key helpers и validators |
| `cache_service.py` | Cache key helpers |
| `calendar_service.py` | Calendar connections, event range read, import orchestration facade |
| `calendar_bridge_service.py` | Calendar -> planner import rules, link resolution и idempotency |
| `calendar_task_export_service.py` | Tokenized task-feed links и ICS export по buckets |
| `calendar_write_service.py` | Best-effort Google Calendar write-back для imported task/habit summary и habit RRULE/BYDAY |
| `calendar_sync_service.py` | Normalized event upsert/sync helpers |
| `calendar_google_service.py` | Google Calendar OAuth/token and provider sync logic |
| `calendar_ics_service.py` | Apple ICS fetch/parse/sync logic |
| `__init__.py` | Текущий re-export `ensure_seed_users` |

## Зависимости
- `app.models.*`
- `app.schemas.*`
- `app.core.database.AsyncSession`
- `app.core.security`
- `app.core.redis`
- `app.services.periods`
- внешние calendar providers через adapter-style service helpers (`google`, `ics`)

## Инварианты
- Все функции, затрагивающие БД или Redis, должны работать в async стиле.
- Сервисные функции принимают явные входы (`db`, `user_id`, typed payload), без скрытого request context.
- User-facing данные должны быть отфильтрованы по пользователю; кросс-пользовательский доступ допустим только в явно admin/auth сценариях.
- `periods.py` остаётся источником правил по месяцу, дню и ISO week validation.
- Bundle services собирают данные из более узких сервисов, а не наоборот.
- Calendar import idempotency и task feed token provisioning принадлежат backend service layer, а не frontend state.

## Экспортируемый интерфейс
- Основной публичный API модуля - набор функций по файлам.
- Через `__init__.py` сейчас экспортируется `ensure_seed_users`.

## Ключевые риски
- Изменения в `auth_service.py`, `week_service.py` и `task_service.py` сразу затрагивают ключевые пользовательские сценарии.
- Изменения сигнатур сервисов требуют синхронной правки route handlers.
