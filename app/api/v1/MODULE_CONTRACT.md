# MODULE CONTRACT: API v1

## Назначение
HTTP слой TaskBook API.
Маршруты, валидация входящих данных, auth/admin gatekeeping и сборка API surface под `/api/v1/*`.

## Ответственность
- Объединять все router modules в единый `api_router`.
- Принимать HTTP request и преобразовывать его в typed inputs для service layer.
- Применять зависимости аутентификации и авторизации.
- Возвращать schema-based ответы и корректные HTTP status codes.

## Граница (что НЕ делает этот модуль)
- Не содержит основную бизнес-логику предметной области.
- Не должен выполнять длинные inline SQL сценарии вместо services.
- Не управляет состоянием frontend/admin UI.
- Не хранит infra-конфигурацию и не отвечает за lifecycle приложения.

## Структура
| Файл | Роль |
|---|---|
| `__init__.py` | Сборка `api_router` и регистрация всех route groups |
| `auth.py` | Регистрация, логин, refresh, logout, password flows |
| `users.py` | Профиль текущего пользователя |
| `months.py` | Month plan, month states, month bundle |
| `habits.py` | CRUD привычек и habit logs |
| `weeks.py` | Недели, week patch, week tasks, reorder, week bundle |
| `tasks.py` | Patch/delete task и day statuses |
| `days.py` | Day bundle, key events, gratitudes |
| `dashboard.py` | Dashboard summary |
| `admin/__init__.py` | Единый admin router package и сборка subrouters |
| `admin/users.py` | Admin users actions, password reset, impersonation |
| `admin/stats.py` | Platform stats для admin dashboard |
| `admin/deps.py` | Admin-specific dependency boundary (`require_admin`) |

Связанный shared deps module расположен уровнем выше: `backend/app/api/deps.py`.

## Зависимости
- `fastapi`, `fastapi.responses`, `fastapi.Depends`
- `app.api.deps` для `get_current_user` и `require_admin`
- `app.core.database.get_db`
- `app.core.auth_cookies` для browser auth cookie handling
- `app.schemas.*` для request/response моделей
- `app.services.*` для предметной логики

## Инварианты
- Все роуты подключаются через `api_router` из `__init__.py`.
- Глобальный prefix задаётся в `app.main` через `settings.API_V1_PREFIX`, текущее значение `/api/v1`.
- Защищённые endpoints работают через `get_current_user`, а admin endpoints через `require_admin`.
- Не-`204` ответы должны оставаться совместимыми со schema contract; `204` не возвращает body.
- Route handlers делегируют предметную работу в service layer, а не дублируют её локально.

## Экспортируемый интерфейс
- `api_router` - единая точка подключения API v1 в `app.main`

## Критичные точки изменения
- Любое изменение URL, auth behaviour или response shape потенциально ломает frontend и admin.
- Изменения в `auth.py` и `admin/` требуют повышенной осторожности из-за безопасности и прав доступа.
