"""
Scout API
/api/scout/configs   — manage search configs
/api/scout/jobs      — browse / action scored listings
/api/scout/run       — manually trigger a scan
/api/scout/stats     — dashboard numbers
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc

from app.deps import AuthDep, DbDep, MemoryDep
from app.models.db import ScoutConfig, ScoutRun, JobListing
from app.workers.job_monitor import register_config, unregister_config

router = APIRouter(prefix="/api/scout", tags=["scout"])


# ── Pydantic models ────────────────────────────────────────────────────────────

class ScoutConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    search_term: str = Field(..., min_length=1, max_length=200)
    location: str = "San Francisco, CA"
    distance_miles: int = Field(default=50, ge=5, le=200)
    sites: str = "linkedin,indeed,glassdoor"          # CSV
    results_wanted: int = Field(default=25, ge=5, le=100)
    hours_old: int = Field(default=72, ge=6, le=720)
    is_remote: bool | None = None
    min_score: int = Field(default=60, ge=0, le=100)
    schedule_hours: int = Field(default=12, ge=1, le=168)


class ScoutConfigUpdate(BaseModel):
    name: str | None = None
    search_term: str | None = None
    location: str | None = None
    distance_miles: int | None = None
    sites: str | None = None
    results_wanted: int | None = None
    hours_old: int | None = None
    is_remote: bool | None = None
    min_score: int | None = None
    schedule_hours: int | None = None
    is_active: bool | None = None


class JobActionRequest(BaseModel):
    status: Literal["SAVED", "PIPELINE", "DISMISSED", "APPLIED"]
    note: str | None = None


# ── Config endpoints ───────────────────────────────────────────────────────────

@router.get("/configs")
async def list_configs(_: AuthDep, db: DbDep):
    result = await db.execute(select(ScoutConfig).order_by(ScoutConfig.created_at))
    configs = result.scalars().all()
    return [_config_to_dict(c) for c in configs]


@router.post("/configs", status_code=201)
async def create_config(body: ScoutConfigCreate, _: AuthDep, db: DbDep):
    config = ScoutConfig(**body.model_dump())
    db.add(config)
    await db.commit()
    await db.refresh(config)
    # Register with scheduler
    if config.is_active:
        await register_config(config.id, config.schedule_hours)
    return _config_to_dict(config)


@router.patch("/configs/{config_id}")
async def update_config(config_id: int, body: ScoutConfigUpdate, _: AuthDep, db: DbDep):
    config = await db.get(ScoutConfig, config_id)
    if not config:
        raise HTTPException(404, "Config not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(config, field, value)
    await db.commit()
    await db.refresh(config)
    # Re-register / unregister
    if config.is_active:
        await register_config(config.id, config.schedule_hours)
    else:
        await unregister_config(config.id)
    return _config_to_dict(config)


@router.delete("/configs/{config_id}", status_code=204)
async def delete_config(config_id: int, _: AuthDep, db: DbDep):
    config = await db.get(ScoutConfig, config_id)
    if not config:
        raise HTTPException(404, "Config not found")
    await unregister_config(config_id)
    await db.delete(config)
    await db.commit()


# ── Manual run ─────────────────────────────────────────────────────────────────

@router.post("/configs/{config_id}/run")
async def manual_run(
    config_id: int,
    background_tasks: BackgroundTasks,
    _: AuthDep,
    db: DbDep,
    memory: MemoryDep,
):
    config = await db.get(ScoutConfig, config_id)
    if not config:
        raise HTTPException(404, "Config not found")

    # Check no run already in progress
    running = await db.execute(
        select(ScoutRun).where(ScoutRun.config_id == config_id, ScoutRun.status == "RUNNING")
    )
    if running.scalar_one_or_none():
        raise HTTPException(409, "A scan is already running for this config")

    async def _bg():
        from app.agents.job_scout import run_scout
        sites = [s.strip() for s in config.sites.split(",") if s.strip()]
        await run_scout(
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
            db_session=None,
        )

    background_tasks.add_task(_bg)
    return {"queued": True, "config_id": config_id, "message": "Scan started in background"}


@router.get("/configs/{config_id}/runs")
async def list_runs(config_id: int, _: AuthDep, db: DbDep):
    result = await db.execute(
        select(ScoutRun)
        .where(ScoutRun.config_id == config_id)
        .order_by(desc(ScoutRun.started_at))
        .limit(20)
    )
    runs = result.scalars().all()
    return [_run_to_dict(r) for r in runs]


# ── Job listing endpoints ──────────────────────────────────────────────────────

@router.get("/jobs")
async def list_jobs(
    _: AuthDep,
    db: DbDep,
    status: str = "NEW",          # NEW|SAVED|PIPELINE|DISMISSED|APPLIED|ALL
    min_score: int = 0,
    config_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
):
    q = select(JobListing).order_by(desc(JobListing.score), desc(JobListing.discovered_at))
    if status != "ALL":
        q = q.where(JobListing.status == status.upper())
    if min_score:
        q = q.where(JobListing.score >= min_score)
    if config_id:
        q = q.where(JobListing.config_id == config_id)
    q = q.offset(offset).limit(limit)

    result = await db.execute(q)
    jobs = result.scalars().all()

    # Total count for pagination
    count_q = select(func.count()).select_from(JobListing)
    if status != "ALL":
        count_q = count_q.where(JobListing.status == status.upper())
    if min_score:
        count_q = count_q.where(JobListing.score >= min_score)
    total = (await db.execute(count_q)).scalar_one()

    return {
        "jobs": [_job_to_dict(j) for j in jobs],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.patch("/jobs/{job_id}/action")
async def action_job(job_id: int, body: JobActionRequest, _: AuthDep, db: DbDep):
    job = await db.get(JobListing, job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    job.status = body.status
    job.user_note = body.note
    job.actioned_at = datetime.now(timezone.utc)
    await db.commit()

    return {"id": job_id, "status": job.status}


@router.post("/jobs/{job_id}/to-pipeline")
async def add_to_pipeline(job_id: int, _: AuthDep, db: DbDep):
    """Convenience: add this job's company directly to the campaign pipeline."""
    from app.models.db import Company, CompanyEvent

    job = await db.get(JobListing, job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    # Create company if not already in pipeline
    existing = await db.execute(
        select(Company).where(
            func.lower(Company.name) == job.company.lower()
        )
    )
    company = existing.scalar_one_or_none()
    if not company:
        company = Company(
            name=job.company,
            role_title=job.title,
            url=job.job_url,
            source=f"scout:{job.site}",
            notes=f"Score {job.score}/100 — {job.score_summary}",
        )
        db.add(company)
        await db.flush()
        db.add(CompanyEvent(
            company_id=company.id,
            event_type="ADDED",
            description=f"Added from Job Scout (score {job.score})",
            stage_to="RESEARCHING",
        ))

    job.status = "PIPELINE"
    job.actioned_at = datetime.now(timezone.utc)
    await db.commit()

    return {"company_id": company.id, "company_name": company.name, "job_id": job_id}


@router.get("/jobs/{job_id}")
async def get_job(job_id: int, _: AuthDep, db: DbDep):
    job = await db.get(JobListing, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    # Mark as seen
    if not job.seen_at:
        job.seen_at = datetime.now(timezone.utc)
        await db.commit()
    return _job_to_dict(job, full_description=True)


# ── Stats ──────────────────────────────────────────────────────────────────────

@router.get("/stats")
async def scout_stats(_: AuthDep, db: DbDep):
    total = (await db.execute(select(func.count()).select_from(JobListing))).scalar_one()
    new = (await db.execute(
        select(func.count()).select_from(JobListing).where(JobListing.status == "NEW")
    )).scalar_one()
    high_score = (await db.execute(
        select(func.count()).select_from(JobListing).where(JobListing.score >= 70)
    )).scalar_one()
    pipeline = (await db.execute(
        select(func.count()).select_from(JobListing).where(JobListing.status == "PIPELINE")
    )).scalar_one()
    avg_score_row = (await db.execute(
        select(func.avg(JobListing.score)).where(JobListing.score.isnot(None))
    )).scalar_one()
    configs = (await db.execute(
        select(func.count()).select_from(ScoutConfig).where(ScoutConfig.is_active == True)
    )).scalar_one()

    return {
        "total_found": total,
        "new_unseen": new,
        "high_score": high_score,
        "added_to_pipeline": pipeline,
        "avg_score": round(float(avg_score_row), 1) if avg_score_row else None,
        "active_configs": configs,
    }


# ── Serialisers ────────────────────────────────────────────────────────────────

def _config_to_dict(c: ScoutConfig) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "search_term": c.search_term,
        "location": c.location,
        "distance_miles": c.distance_miles,
        "sites": c.sites,
        "results_wanted": c.results_wanted,
        "hours_old": c.hours_old,
        "is_remote": c.is_remote,
        "min_score": c.min_score,
        "schedule_hours": c.schedule_hours,
        "is_active": c.is_active,
        "last_run_at": c.last_run_at.isoformat() if c.last_run_at else None,
        "created_at": c.created_at.isoformat(),
    }


def _run_to_dict(r: ScoutRun) -> dict:
    return {
        "id": r.id,
        "config_id": r.config_id,
        "status": r.status,
        "started_at": r.started_at.isoformat(),
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        "jobs_found": r.jobs_found,
        "jobs_new": r.jobs_new,
        "jobs_scored": r.jobs_scored,
        "error_msg": r.error_msg,
    }


def _job_to_dict(j: JobListing, full_description: bool = False) -> dict:
    return {
        "id": j.id,
        "title": j.title,
        "company": j.company,
        "location": j.location,
        "is_remote": j.is_remote,
        "salary_min": j.salary_min,
        "salary_max": j.salary_max,
        "salary_currency": j.salary_currency,
        "description": j.description if full_description else j.description_snippet,
        "site": j.site,
        "date_posted": j.date_posted,
        "job_type": j.job_type,
        "job_url": j.job_url,
        "score": j.score,
        "score_summary": j.score_summary,
        "score_pros": json.loads(j.score_pros) if j.score_pros else [],
        "score_cons": json.loads(j.score_cons) if j.score_cons else [],
        "sponsorship_likely": j.sponsorship_likely,
        "status": j.status,
        "user_note": j.user_note,
        "discovered_at": j.discovered_at.isoformat(),
        "seen_at": j.seen_at.isoformat() if j.seen_at else None,
    }
