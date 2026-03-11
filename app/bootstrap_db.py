from __future__ import annotations

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.core.database import engine
from app.models.base import Base


def _get_alembic_config() -> Config:
    return Config("alembic.ini")


async def _get_existing_tables() -> set[str]:
    async with engine.begin() as connection:
        return await connection.run_sync(lambda sync_connection: set(inspect(sync_connection).get_table_names()))


async def _detect_bootstrap_mode() -> str:
    existing_tables = await _get_existing_tables()
    expected_tables = set(Base.metadata.tables.keys())

    if "alembic_version" in existing_tables:
        return "upgrade"

    initialized_tables = existing_tables & expected_tables
    if not initialized_tables:
        return "upgrade"

    if initialized_tables == expected_tables:
        return "stamp"

    raise RuntimeError(
        "Database contains a partially initialized schema without alembic metadata. "
        "Bring it to a clean state or reconcile it manually before startup."
    )


def bootstrap_database() -> None:
    import asyncio

    mode = asyncio.run(_detect_bootstrap_mode())
    config = _get_alembic_config()

    if mode == "stamp":
        command.stamp(config, "head")
        return

    command.upgrade(config, "head")


if __name__ == "__main__":
    bootstrap_database()
