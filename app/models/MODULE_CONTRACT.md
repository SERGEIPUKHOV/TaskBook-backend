# MODULE CONTRACT: Models

## Назначение
SQLAlchemy ORM слой TaskBook.
Модуль описывает таблицы, relationships и общие declarative primitives для persistence-модели приложения.

## Ответственность
- Объявлять ORM-модели для `users`, `weeks`, `tasks`, `task_day_statuses`, `month_plans`, `habits`, `habit_logs`, `daily_states`, `key_events`, `gratitudes`.
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
| `user.py` | Пользователь и auth-related persistence state |
| `week.py` | Неделя, её границы и weekly reflection поля |
| `task.py` | Задачи и статусы задач по дням |
| `month_plan.py` | План месяца |
| `habit.py` | Привычки и их логи |
| `daily_state.py` | Метрики состояния по дням |
| `day_entry.py` | Key events и gratitudes |
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
