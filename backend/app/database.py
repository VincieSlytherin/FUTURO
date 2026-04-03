from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config import PROJECT_ROOT, settings
from app.models.db import Base

engine = create_async_engine(
    settings.db_url,
    echo=settings.debug,
    connect_args={"check_same_thread": False, "timeout": 30},
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@event.listens_for(engine.sync_engine, "connect")
def _configure_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA synchronous=NORMAL")
    finally:
        cursor.close()


def _sync_db_url(async_db_url: str) -> str:
    if async_db_url.startswith("sqlite+aiosqlite:///"):
        return async_db_url.replace("sqlite+aiosqlite:///", "sqlite:///", 1)
    return async_db_url


def _sqlite_tables(db_path: Path) -> set[str]:
    if not db_path.exists():
        return set()

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    return {row[0] for row in rows}


def _sqlite_current_revision(db_path: Path) -> str | None:
    if not db_path.exists():
        return None

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        if "alembic_version" not in tables:
            return None

        row = conn.execute("SELECT version_num FROM alembic_version LIMIT 1").fetchone()
    return row[0] if row and row[0] else None


def _alembic_config(db_url: str) -> Config:
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", _sync_db_url(db_url))
    return cfg


def _run_migrations(db_url: str | None = None, db_path: Path | None = None) -> None:
    target_db_url = db_url or settings.db_url
    target_db_path = db_path or settings.db_path

    tables = _sqlite_tables(target_db_path)
    current_revision = _sqlite_current_revision(target_db_path)
    alembic_cfg = _alembic_config(target_db_url)

    # Existing local databases created before Alembic should not be blown away.
    # If we detect a legacy schema without alembic_version, ensure any current
    # tables exist and then stamp the current baseline as applied.
    if tables and current_revision is None:
        sync_engine = create_engine(
            _sync_db_url(target_db_url),
            connect_args={"check_same_thread": False, "timeout": 30},
        )
        try:
            Base.metadata.create_all(sync_engine, checkfirst=True)
        finally:
            sync_engine.dispose()
        command.stamp(alembic_cfg, "head")
        return

    command.upgrade(alembic_cfg, "head")


def run_migrations() -> None:
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    _run_migrations()


async def init_db() -> None:
    await asyncio.to_thread(run_migrations)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
