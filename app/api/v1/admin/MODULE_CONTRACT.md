# MODULE CONTRACT: Admin API

## Назначение
Admin-only HTTP пакет под `/api/v1/admin/*`.
Модуль обслуживает moderation и platform-observability сценарии для административного интерфейса.

## Ответственность
- Собирать admin router package в `__init__.py`.
- Ограничивать доступ через `require_admin` из `deps.py`.
- Отдавать paginated user list, moderation actions, password reset и impersonation flows.
- Возвращать platform stats для admin dashboard.

## Граница (что НЕ делает этот модуль)
- Не реализует login/register/refresh/logout и не заменяет пакет `auth/`.
- Не рендерит admin UI и не хранит состояние SPA.
- Не должен обходить admin guard или публиковать эти endpoints обычным пользователям.
- Не должен превращаться в общий shared router для non-admin API surface.

## Структура
| Файл | Роль |
|---|---|
| `__init__.py` | Сборка admin router package |
| `deps.py` | `require_admin` guard поверх `get_current_user` |
| `users.py` | Поиск пользователей, block/unblock, email change, temp password, impersonation |
| `stats.py` | Сводные platform-level counts для admin dashboard |

## Зависимости
- `app.api.deps.get_current_user`
- `app.core.database.get_db`
- `app.core.redis` и `app.core.security` для impersonation/password reset сценариев
- `app.models.user`, `app.models.task`, `app.models.habit`
- `app.schemas.admin`, `app.schemas.common`

## Инварианты
- Все публичные endpoints пакета зависят от `require_admin`.
- Self-mutation и admin-to-admin mutation запрещены там, где это зашито текущим поведением.
- Ответы отдаются в `Response[...]` envelope, совместимом с текущим admin SPA.
- Текущая реализация использует `AsyncSession` и модели напрямую внутри route handlers; это нужно учитывать при рефакторинге.
