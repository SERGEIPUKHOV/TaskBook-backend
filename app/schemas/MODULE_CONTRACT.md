# MODULE CONTRACT: Schemas

## Назначение
Typed request/response contracts для backend API.
Модуль отвечает за Pydantic v2 модели, которые валидируют входящие payloads и сериализуют ответы наружу.

## Ответственность
- Описывать request schemas для create/update/auth/admin сценариев.
- Описывать response schemas для frontend/admin клиентов.
- Держать shared envelope и pagination contracts в `common.py`.
- Отражать backend domain model в transport-safe виде без протаскивания ORM объектов наружу.

## Граница (что НЕ делает этот модуль)
- Не обращается к БД и не знает про `AsyncSession`.
- Не содержит предметную бизнес-логику и side effects.
- Не управляет FastAPI router wiring.
- Не участвует в Alembic migrations и не заменяет ORM models.

## Структура
| Файл | Роль |
|---|---|
| `auth.py` | Auth payloads, user snapshot, password flows |
| `admin.py` | Admin user/stats contracts |
| `dashboard.py` | Dashboard summary schemas |
| `user.py` | Профиль и user-facing contracts |
| `task.py` | Task CRUD и task day status contracts |
| `habit.py` | Habit CRUD и habit grid/log contracts |
| `week.py` | Week summary, patch и bundle contracts |
| `month.py` | Month plan и month state contracts |
| `day.py` | Day bundle contracts |
| `day_entry.py` | Key events и gratitude entries |
| `daily_state.py` | Метрики состояния по дням |
| `common.py` | `Response`, `PaginatedResponse`, `OperationStatus` |
| `__init__.py` | Package exports |

## Зависимости
- `pydantic` / `pydantic.ConfigDict`
- `typing` и generics для envelope contracts
- `app.models.*` только опосредованно, через `from_attributes=True` в ORM-backed output schemas

## Правила и инварианты
- Проект использует Pydantic v2 API; `@validator` из v1 не должен появляться.
- ORM-backed output schemas включают `ConfigDict(from_attributes=True)` там, где это нужно.
- Схемы отражают transport contract текущего API, а не желаемое будущее состояние.
- Любое изменение response shape требует синхронной проверки route handlers, frontend mappers и tests.
