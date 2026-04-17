from __future__ import annotations

from collections import defaultdict
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tracker_goal import TrackerGoal
from app.models.tracker_sprint import TrackerSprint
from app.schemas.tracker import (
    TrackerDeadlineOut,
    TrackerGoalCreate,
    TrackerGoalOut,
    TrackerGoalPatch,
    TrackerSprintCreate,
    TrackerSprintOut,
    TrackerSprintPatch,
)
from app.services.periods import week_bounds

SECTION_ORDER = {
    "money": 0,
    "health": 1,
    "state": 2,
    "communications": 3,
    "relations": 4,
}


def _goal_sort_key(goal: TrackerGoal | TrackerGoalOut) -> tuple[int, int, int, str]:
    section_order = SECTION_ORDER.get(getattr(goal, "section", ""), 99)
    sort_order = getattr(goal, "sort_order", 0)
    level = getattr(goal, "level", 99)
    created_at = getattr(goal, "created_at", None)
    created_key = created_at.isoformat() if created_at is not None else ""
    return (section_order, sort_order, level, created_key)


def _build_tree(rows: list[TrackerGoal]) -> list[TrackerGoalOut]:
    goals_by_id: dict[str, TrackerGoalOut] = {}
    for row in sorted(rows, key=_goal_sort_key):
        goals_by_id[row.id] = TrackerGoalOut.model_validate(row)

    roots: list[TrackerGoalOut] = []
    for goal in goals_by_id.values():
        if goal.parent_id and goal.parent_id in goals_by_id:
            goals_by_id[goal.parent_id].children.append(goal)
        else:
            roots.append(goal)

    def sort_children(node: TrackerGoalOut) -> None:
        node.children.sort(key=_goal_sort_key)
        for child in node.children:
            sort_children(child)

    roots.sort(key=_goal_sort_key)
    for root in roots:
        sort_children(root)
    return roots


async def _get_sprint_for_user(db: AsyncSession, user_id: str, sprint_id: str) -> TrackerSprint:
    result = await db.execute(
        select(TrackerSprint).where(
            TrackerSprint.id == sprint_id,
            TrackerSprint.user_id == user_id,
        ),
    )
    sprint = result.scalar_one_or_none()
    if sprint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sprint not found")
    return sprint


async def _get_goal_for_user(db: AsyncSession, user_id: str, goal_id: str) -> TrackerGoal:
    result = await db.execute(
        select(TrackerGoal).where(
            TrackerGoal.id == goal_id,
            TrackerGoal.user_id == user_id,
        ),
    )
    goal = result.scalar_one_or_none()
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    return goal


async def _validate_parent_goal(
    db: AsyncSession,
    user_id: str,
    sprint_id: str,
    level: int,
    section: str,
    parent_id: str | None,
) -> TrackerGoal | None:
    if level == 1:
        if parent_id is not None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Level 1 goal cannot have a parent")
        return None

    if parent_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Nested goal requires a parent")

    parent = await _get_goal_for_user(db, user_id, parent_id)
    if parent.sprint_id != sprint_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Parent belongs to another sprint")
    if parent.section != section:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Parent section mismatch")
    if level == 2 and parent.level != 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Level 2 goal must belong to a level 1 parent")
    if level == 3 and parent.level != 2:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Level 3 goal must belong to a level 2 parent")
    return parent


def _normalize_goal_payload(level: int, hypothesis: str | None, deadline_date: date | None, status: str | None) -> tuple[str | None, date | None, str | None]:
    if level == 1:
        return None, None, None
    if level == 2:
        return hypothesis, None, None
    return None, deadline_date, status


async def _set_active_sprint(db: AsyncSession, user_id: str, sprint_id: str) -> None:
    await db.execute(
        update(TrackerSprint)
        .where(TrackerSprint.user_id == user_id)
        .values(is_active=False),
    )
    await db.execute(
        update(TrackerSprint)
        .where(TrackerSprint.user_id == user_id, TrackerSprint.id == sprint_id)
        .values(is_active=True),
    )


async def _ensure_valid_sprint_dates(sprint: TrackerSprint, patch: TrackerSprintPatch) -> None:
    next_start = patch.start_date if patch.start_date is not None else sprint.start_date
    next_end = patch.end_date if patch.end_date is not None else sprint.end_date
    if next_end < next_start:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Sprint end date must not be before start date")


async def list_sprints(db: AsyncSession, user_id: str) -> list[TrackerSprintOut]:
    result = await db.execute(
        select(TrackerSprint)
        .where(TrackerSprint.user_id == user_id)
        .order_by(TrackerSprint.is_active.desc(), TrackerSprint.start_date.desc(), TrackerSprint.created_at.desc()),
    )
    return [TrackerSprintOut.model_validate(item) for item in result.scalars().all()]


async def create_sprint(db: AsyncSession, user_id: str, data: TrackerSprintCreate) -> TrackerSprintOut:
    sprint = TrackerSprint(
        user_id=user_id,
        title=data.title.strip(),
        start_date=data.start_date,
        end_date=data.end_date,
        is_active=False,
    )
    db.add(sprint)
    await db.flush()
    await _set_active_sprint(db, user_id, sprint.id)
    await db.commit()
    await db.refresh(sprint)
    return TrackerSprintOut.model_validate(sprint)


async def patch_sprint(db: AsyncSession, user_id: str, sprint_id: str, data: TrackerSprintPatch) -> TrackerSprintOut:
    sprint = await _get_sprint_for_user(db, user_id, sprint_id)
    await _ensure_valid_sprint_dates(sprint, data)

    payload = data.model_dump(exclude_unset=True)
    activate = payload.pop("is_active", None)
    for field, value in payload.items():
        if field == "title" and value is not None:
            value = value.strip()
        setattr(sprint, field, value)

    if activate:
        await _set_active_sprint(db, user_id, sprint.id)
        sprint.is_active = True
    elif activate is False:
        sprint.is_active = False

    db.add(sprint)
    await db.commit()
    await db.refresh(sprint)
    return TrackerSprintOut.model_validate(sprint)


async def delete_sprint(db: AsyncSession, user_id: str, sprint_id: str) -> None:
    sprint = await _get_sprint_for_user(db, user_id, sprint_id)
    was_active = sprint.is_active

    await db.execute(
        delete(TrackerGoal).where(
            TrackerGoal.user_id == user_id,
            TrackerGoal.sprint_id == sprint.id,
        ),
    )
    await db.delete(sprint)
    await db.flush()

    if was_active:
        remaining_result = await db.execute(
            select(TrackerSprint)
            .where(TrackerSprint.user_id == user_id)
            .order_by(TrackerSprint.start_date.desc(), TrackerSprint.created_at.desc())
            .limit(1),
        )
        remaining = remaining_result.scalar_one_or_none()
        if remaining is not None:
            await _set_active_sprint(db, user_id, remaining.id)

    await db.commit()


async def list_goals(db: AsyncSession, user_id: str, sprint_id: str) -> list[TrackerGoalOut]:
    await _get_sprint_for_user(db, user_id, sprint_id)
    result = await db.execute(
        select(TrackerGoal)
        .where(TrackerGoal.user_id == user_id, TrackerGoal.sprint_id == sprint_id)
        .order_by(TrackerGoal.section.asc(), TrackerGoal.sort_order.asc(), TrackerGoal.created_at.asc()),
    )
    return _build_tree(list(result.scalars().all()))


async def create_goal(db: AsyncSession, user_id: str, sprint_id: str, data: TrackerGoalCreate) -> TrackerGoalOut:
    await _get_sprint_for_user(db, user_id, sprint_id)
    await _validate_parent_goal(db, user_id, sprint_id, data.level, data.section, data.parent_id)
    hypothesis, deadline_date, status = _normalize_goal_payload(
        data.level,
        data.hypothesis.strip() if isinstance(data.hypothesis, str) else data.hypothesis,
        data.deadline_date,
        None,
    )
    goal = TrackerGoal(
        user_id=user_id,
        sprint_id=sprint_id,
        section=data.section,
        level=data.level,
        parent_id=data.parent_id,
        title=data.title.strip(),
        hypothesis=hypothesis,
        deadline_date=deadline_date,
        status=status,
        sort_order=data.sort_order,
    )
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    return TrackerGoalOut.model_validate(goal)


async def patch_goal(db: AsyncSession, user_id: str, goal_id: str, data: TrackerGoalPatch) -> TrackerGoalOut:
    goal = await _get_goal_for_user(db, user_id, goal_id)
    payload = data.model_dump(exclude_unset=True)

    if "hypothesis" in payload and goal.level != 2:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Only level 2 goals can store a hypothesis")
    if "deadline_date" in payload and goal.level != 3:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Only level 3 goals can store a deadline")
    if "status" in payload and goal.level != 3:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Only level 3 goals can store a status")

    for field, value in payload.items():
        if field == "title" and value is not None:
            value = value.strip()
        if field == "hypothesis" and isinstance(value, str):
            value = value.strip() or None
        setattr(goal, field, value)

    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    return TrackerGoalOut.model_validate(goal)


async def delete_goal(db: AsyncSession, user_id: str, goal_id: str) -> None:
    goal = await _get_goal_for_user(db, user_id, goal_id)
    sprint_result = await db.execute(
        select(TrackerGoal.id, TrackerGoal.parent_id).where(
            TrackerGoal.user_id == user_id,
            TrackerGoal.sprint_id == goal.sprint_id,
        ),
    )
    rows = sprint_result.all()
    children_by_parent: dict[str, list[str]] = defaultdict(list)
    for child_id, parent_id in rows:
        if parent_id:
            children_by_parent[str(parent_id)].append(str(child_id))

    ids_to_delete = {goal.id}
    frontier = [goal.id]
    while frontier:
        current = frontier.pop()
        for child_id in children_by_parent.get(current, []):
            if child_id not in ids_to_delete:
                ids_to_delete.add(child_id)
                frontier.append(child_id)

    await db.execute(
        delete(TrackerGoal).where(
            TrackerGoal.user_id == user_id,
            TrackerGoal.id.in_(ids_to_delete),
        ),
    )
    await db.commit()


async def _get_active_sprint(db: AsyncSession, user_id: str) -> TrackerSprint | None:
    result = await db.execute(
        select(TrackerSprint)
        .where(TrackerSprint.user_id == user_id, TrackerSprint.is_active.is_(True))
        .order_by(TrackerSprint.updated_at.desc())
        .limit(1),
    )
    sprint = result.scalar_one_or_none()
    if sprint is not None:
        return sprint

    fallback_result = await db.execute(
        select(TrackerSprint)
        .where(TrackerSprint.user_id == user_id)
        .order_by(TrackerSprint.start_date.desc(), TrackerSprint.created_at.desc())
        .limit(1),
    )
    return fallback_result.scalar_one_or_none()


async def _get_deadlines_between(db: AsyncSession, user_id: str, start_date: date, end_date: date) -> list[TrackerDeadlineOut]:
    active_sprint = await _get_active_sprint(db, user_id)
    if active_sprint is None:
        return []

    result = await db.execute(
        select(TrackerGoal)
        .where(
            TrackerGoal.user_id == user_id,
            TrackerGoal.sprint_id == active_sprint.id,
            TrackerGoal.level == 3,
            TrackerGoal.deadline_date.is_not(None),
            TrackerGoal.deadline_date >= start_date,
            TrackerGoal.deadline_date <= end_date,
        )
        .order_by(TrackerGoal.deadline_date.asc(), TrackerGoal.sort_order.asc(), TrackerGoal.created_at.asc()),
    )
    goals = list(result.scalars().all())
    if not goals:
        return []

    tree_result = await db.execute(
        select(TrackerGoal).where(
            TrackerGoal.user_id == user_id,
            TrackerGoal.sprint_id == active_sprint.id,
        ),
    )
    goal_map = {goal.id: goal for goal in tree_result.scalars().all()}

    deadlines: list[TrackerDeadlineOut] = []
    for goal in goals:
        breadcrumb = [goal.title]
        parent = goal_map.get(goal.parent_id) if goal.parent_id else None
        while parent is not None:
            breadcrumb.append(parent.title)
            parent = goal_map.get(parent.parent_id) if parent.parent_id else None
        breadcrumb.reverse()
        deadlines.append(
            TrackerDeadlineOut(
                goal_id=goal.id,
                sprint_id=goal.sprint_id,
                section=goal.section,
                title=goal.title,
                deadline_date=goal.deadline_date,
                status=goal.status,
                breadcrumb=breadcrumb,
            ),
        )
    return deadlines


async def get_deadlines_for_week(db: AsyncSession, user_id: str, week_year: int, week_num: int) -> list[TrackerDeadlineOut]:
    start_date, end_date = week_bounds(week_year, week_num)
    return await _get_deadlines_between(db, user_id, start_date, end_date)


async def get_deadlines_for_date(db: AsyncSession, user_id: str, target_date: date) -> list[TrackerDeadlineOut]:
    return await _get_deadlines_between(db, user_id, target_date, target_date)
