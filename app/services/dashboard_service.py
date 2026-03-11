from __future__ import annotations

import json
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import redis_client
from app.schemas.dashboard import DashboardOut
from app.services.cache_service import dashboard_cache_key
from app.services.daily_state_service import get_month_states
from app.services.month_service import get_month_plan
from app.services.task_service import list_week_tasks
from app.services.week_service import get_or_create_week, serialize_week


async def get_dashboard(db: AsyncSession, user_id: str) -> DashboardOut:
    cache_key = dashboard_cache_key(user_id)
    cached = await redis_client.get(cache_key)

    if cached:
        return DashboardOut.model_validate(json.loads(cached))

    today = date.today()
    current_year, current_week, _ = today.isocalendar()
    current_week_model = await get_or_create_week(db, user_id, current_year, current_week)
    current_month_plan = await get_month_plan(db, user_id, today.year, today.month)
    month_states = await get_month_states(db, user_id, today.year, today.month)
    visible_days = {today}
    if today.day > 1:
        visible_days.add(today.fromordinal(today.toordinal() - 1))
    filtered_states = [state for state in month_states if state.date in visible_days]
    tasks = await list_week_tasks(db, user_id, current_year, current_week)

    payload = DashboardOut(
        current_week=serialize_week(current_week_model),
        tasks=tasks,
        month_states=filtered_states,
        current_month_plan=current_month_plan,
    )
    await redis_client.set(
        cache_key,
        json.dumps(payload.model_dump(mode="json")),
        ex=settings.DASHBOARD_CACHE_TTL,
    )
    return payload
