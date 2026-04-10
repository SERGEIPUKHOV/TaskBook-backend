# MODULE CONTRACT: Models

## Назначение
SQLAlchemy ORM слой TaskBook.
Модуль описывает таблицы, relationships и общие declarative primitives для persistence-модели приложения.

## Ответственность
- Объявлять ORM-модели для `users`, `weeks`, `tasks`, `task_day_statuses`, `month_plans`, `habits`, `habit_logs`, `daily_states`, `key_events`, `gratitudes`, `calendar_connections`, `calendar_events`, `calendar_provider_accounts`, `planner_links`.
- Держать общие declarative primitives в `base.py`: `Base`, `TimestampMixin`, `UUIDPrimaryKeyMixin`.
- Определять relationships и foreign key связи между сущностями.
- Экспортировать основной набор моделей через `__init__.py` для удобного импорта и metadata discovery.

## Граница (что НЕ делает этот модуль)
- Не содержит HTTP routes и FastAPI dependencies.
- Не выполняет бизнес-операции и bundle orchestration.
- Не должен делать запросы к БД через `AsyncSession` или raw SQL.
- Не описывает API response/request contracts; это зона `schemas/`.

## Структура
| Файл | Роль |
|---|---|
| `base.py` | Declarative base и общие mixins для UUID/timestamps |
| `user.py` | Пользователь, auth-related persistence state и token для task ICS feeds |
| `week.py` | Неделя, её границы и weekly reflection поля |
| `task.py` | Задачи, export flags/bucket и статусы задач по дням |
| `month_plan.py` | План месяца |
| `habit.py` | Привычки и их логи |
| `daily_state.py` | Метрики состояния по дням |
| `day_entry.py` | Key events и gratitudes |
| `calendar_connection.py` | Подключение внешнего календаря и account metadata |
| `calendar_event.py` | Нормализованное внешнее событие календаря |
| `calendar_provider_account.py` | Provider-level account/token snapshot |
| `planner_link.py` | Link layer между внешним событием и planner entity |
| `__init__.py` | Re-export ORM моделей |

## Зависимости
- `sqlalchemy.orm` и типизированные ORM primitives
- `app.models.base.Base` как корневая metadata точка
- `app.core.database` и Alembic используют metadata этих моделей для persistence/bootstrap сценариев

## Инварианты
- Каждая модель соответствует persistence-сущности, а не UI/view model.
- Общие поля `id`, `created_at`, `updated_at` переиспользуются через mixins там, где это уместно.
- Relationships и foreign keys описываются здесь, а не размазываются по service layer.
- Любое изменение ORM shape требует синхронной проверки Alembic/migrations и связанных schema contracts.
- Link tables, provider-state модели и feed-token поля остаются user-scoped и не должны превращаться в source of truth для planner UI.
