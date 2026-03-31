"""
Job Monitor Worker
------------------
APScheduler background tasks that run scout configs on their configured schedule.
Registered at FastAPI startup.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.db import ScoutConfig

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _run_config(config_id: int) -> None:
    """Called by APScheduler for each active config."""
    from app.agents.job_scout import run_scout
    from app.memory.manager import MemoryManager
    from app.config import settings

    async with AsyncSessionLocal() as db:
        config = await db.get(ScoutConfig, config_id)
        if not config or not config.is_active:
            return

    memory = MemoryManager(memory_dir=settings.memory_dir, git_auto_commit=False)

    try:
        sites = [s.strip() for s in config.sites.split(",") if s.strip()]
        result = await run_scout(
            config_id=config.id,
            search_term=config.search_term,
            location=config.location,
            sites=sites,
            results_wanted=config.results_wanted,
            hours_old=config.hours_old,
            distance=config.distance_miles,
            is_remote=config.is_remote,
            min_score=config.min_score,
            memory=memory,
            db_session=None,  # run_scout manages its own sessions
        )
        logger.info(f"[monitor] config {config_id} '{config.name}': {result}")
    except Exception as exc:
        logger.error(f"[monitor] config {config_id} failed: {exc}")


async def register_config(config_id: int, schedule_hours: int) -> None:
    """Add or replace a scheduled job for this config."""
    global _scheduler
    if _scheduler is None:
        return
    job_id = f"scout_{config_id}"
    if _scheduler.get_job(job_id):
        _scheduler.remove_job(job_id)
    _scheduler.add_job(
        _run_config,
        trigger=IntervalTrigger(hours=schedule_hours),
        id=job_id,
        args=[config_id],
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=10),  # first run soon
        replace_existing=True,
        misfire_grace_time=300,
    )
    logger.info(f"[monitor] registered config {config_id} every {schedule_hours}h")


async def unregister_config(config_id: int) -> None:
    global _scheduler
    if _scheduler is None:
        return
    job_id = f"scout_{config_id}"
    if _scheduler.get_job(job_id):
        _scheduler.remove_job(job_id)


async def start_scheduler() -> None:
    """Start APScheduler and load all active configs from DB."""
    global _scheduler
    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.start()

    # Register all currently active configs
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ScoutConfig).where(ScoutConfig.is_active == True)
        )
        configs = result.scalars().all()

    for config in configs:
        await register_config(config.id, config.schedule_hours)

    logger.info(f"[monitor] scheduler started, {len(configs)} active configs loaded")


async def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def get_scheduler() -> AsyncIOScheduler | None:
    return _scheduler
