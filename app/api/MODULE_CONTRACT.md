# MODULE CONTRACT: Shared API Dependencies

## Назначение
Верхний API-модуль над `api/v1/`.
Даёт стабильную точку импорта для общих FastAPI dependencies и совместимый boundary для auth/admin gatekeeping.

## Ответственность
- `deps.py` реэкспортирует `get_current_user` и `get_optional_user` из `app.api.v1.auth.deps`.
- `deps.py` определяет `require_admin` для admin-only route handlers.
- Сохраняет совместимый import surface через `app.api.deps` для остального backend-кода.

## Граница (что НЕ делает этот модуль)
- Не содержит route handlers и не регистрирует routers.
- Не создаёт DB session factory и не заменяет `app.core.database`.
- Не реализует auth/session business logic; она остаётся в `api/v1/auth` и service layer.
- Не должен превращаться в склад несвязанных shared helpers вне API dependency chain.

## Структура
| Файл | Роль |
|---|---|
| `deps.py` | Общий dependency boundary: `get_current_user`, `get_optional_user`, `require_admin` |

## Зависимости
- `fastapi.Depends`, `fastapi.HTTPException`, `fastapi.status`
- `app.api.v1.auth.deps`
- `app.models.user.User`

## Инварианты
- `require_admin` всегда опирается на уже разрешённого `get_current_user`.
- Не-admin пользователь получает `403 Admin access required`.
- Совместимые импорты через `app.api.deps` должны оставаться стабильными при внутренней декомпозиции auth/admin.
- Логика получения текущего пользователя не дублируется здесь, а переиспользуется из `api/v1/auth/deps.py`.
