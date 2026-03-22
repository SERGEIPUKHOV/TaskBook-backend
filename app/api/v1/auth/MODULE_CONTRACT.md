# MODULE CONTRACT: api/v1/auth/

## Назначение
HTTP boundary для аутентификации и browser-cookie session flows в TaskBook.
Модуль отвечает за регистрацию, логин/logout, refresh, impersonation exchange и password/account flows.

## Экспортируемый интерфейс
- `router` - единый `APIRouter` для всех `/api/v1/auth/*` маршрутов
- `get_current_user` - dependency для защищённых endpoints
- `get_optional_user` - optional dependency для сценариев с необязательной аутентификацией

## Файлы модуля
| Файл | Отвечает за |
|---|---|
| `__init__.py` | Сборка auth router package и совместимый export deps |
| `deps.py` | Access token extraction, JWT validation, current/optional user resolution |
| `register.py` | `POST /register` |
| `sessions.py` | `POST /login`, `POST /refresh`, `POST /logout`, `POST /exchange-impersonate` |
| `password.py` | `POST /forgot-password`, `GET /reset-password/validate`, `POST /reset-password`, `POST /change-password`, `DELETE /account` |

## Зависимости
- `app.core.auth_cookies` - browser auth cookie lifecycle
- `app.core.config` - auth cookie names
- `app.core.database` - `AsyncSession`, `get_db`
- `app.core.redis` - impersonation code lookup
- `app.core.security` - access token decode
- `app.services.auth_service` - register/login/refresh/logout/password/account business logic
- `app.schemas.auth` - auth request/response contracts

## Инварианты
- URL, response models и поведение `/api/v1/auth/*` не меняются при внутренней декомпозиции.
- Access token может приходить из Bearer header или access cookie.
- Refresh token разрешается из JSON payload или refresh cookie.
- Register/login/refresh/exchange-impersonate обязаны выставлять auth cookies через `set_auth_cookies`.
- Logout обязан очищать auth cookies даже если refresh token отсутствует.
- Password/account handlers не содержат inline бизнес-логики и делегируют её в `auth_service`.
