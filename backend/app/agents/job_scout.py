"""
Job Scout Agent
---------------
Scrapes job listings from multiple sources using python-jobspy,
then uses Claude to score each listing against the user's L0 profile.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone

from app.memory.manager import MemoryManager
from app.notifications import EmailNotificationService, notifications_enabled
from app.providers.base import TaskType
from app.providers.router import get_provider
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)
_active_config_runs: set[int] = set()
_scout_write_lock = asyncio.Lock()


def is_config_running(config_id: int) -> bool:
    return config_id in _active_config_runs


def _is_sqlite_locked(exc: Exception) -> bool:
    return "database is locked" in str(exc).lower()


async def _run_with_sqlite_retry(fn, *, attempts: int = 6, base_delay: float = 0.15):
    for attempt in range(attempts):
        try:
            async with _scout_write_lock:
                return await fn()
        except OperationalError as exc:
            if not _is_sqlite_locked(exc) or attempt == attempts - 1:
                raise
            await asyncio.sleep(base_delay * (attempt + 1))


async def _update_run_progress(run_id: int, **fields) -> None:
    from app.database import AsyncSessionLocal
    from app.models.db import ScoutRun

    async def _write():
        async with AsyncSessionLocal() as db:
            run = await db.get(ScoutRun, run_id)
            if not run:
                return
            for field, value in fields.items():
                setattr(run, field, value)
            await db.commit()

    await _run_with_sqlite_retry(_write)

# ── Scraping ──────────────────────────────────────────────────────────────────

def _scrape_jobs(
    search_term: str,
    location: str,
    sites: list[str],
    results_wanted: int,
    hours_old: int,
    distance: int,
    is_remote: bool | None,
) -> list[dict]:
    """
    Scrape jobs using python-jobspy.
    Returns a list of normalised dicts (title, company, url, description, ...).
    Falls back to empty list if jobspy is not installed or scraping fails.
    """
    try:
        from jobspy import scrape_jobs  # type: ignore
        import pandas as pd

        kwargs: dict = dict(
            site_name=sites,
            search_term=search_term,
            location=location,
            results_wanted=results_wanted,
            hours_old=hours_old,
            distance=distance,
            country_indeed="USA",
            linkedin_fetch_description=True,
            verbose=0,
        )
        if is_remote is not None:
            kwargs["is_remote"] = is_remote

        df: pd.DataFrame = scrape_jobs(**kwargs)
        if df is None or df.empty:
            return []

        jobs = []
        for _, row in df.iterrows():
            title = str(row.get("title", "")).strip()
            company = str(row.get("company", "")).strip()
            job_url = str(row.get("job_url", "")).strip()
            if not title or not company or not job_url:
                continue

            desc = str(row.get("description", "") or "")
            jobs.append({
                "title": title,
                "company": company,
                "job_url": job_url,
                "url_hash": hashlib.sha256(job_url.encode()).hexdigest(),
                "location": str(row.get("location", "") or ""),
                "is_remote": bool(row.get("is_remote", False)),
                "salary_min": _safe_float(row.get("min_amount")),
                "salary_max": _safe_float(row.get("max_amount")),
                "salary_currency": str(row.get("currency", "") or ""),
                "description": desc[:8000],
                "description_snippet": desc[:300],
                "site": str(row.get("site", "")),
                "date_posted": str(row.get("date_posted", "") or ""),
                "job_type": str(row.get("job_type", "") or ""),
            })
        return jobs

    except ImportError:
        logger.warning("python-jobspy not installed — returning mock data for dev")
        return _mock_jobs(search_term, location)
    except Exception as exc:
        logger.error(f"Scrape failed: {exc}")
        return []


def _safe_float(val) -> float | None:
    try:
        return float(val) if val is not None and str(val) not in ("", "nan", "None") else None
    except (ValueError, TypeError):
        return None


def _mock_jobs(search_term: str, location: str) -> list[dict]:
    """Dev fallback when jobspy isn't installed."""
    base = [
        {"title": f"Senior {search_term}", "company": "Anthropic",
         "location": location, "is_remote": True,
         "description": f"We are looking for a {search_term} to join our applied team. "
                        "Experience with LLMs, RAG pipelines, and production ML systems required. "
                        "H-1B sponsorship available.",
         "job_url": "https://anthropic.com/careers/1", "site": "linkedin"},
        {"title": f"{search_term} — Platform", "company": "Cohere",
         "location": location, "is_remote": False,
         "description": f"Join Cohere as a {search_term}. Build production ML infrastructure. "
                        "Python, LangChain, vector databases. Visa sponsorship offered.",
         "job_url": "https://cohere.com/careers/1", "site": "indeed"},
        {"title": f"Staff {search_term}", "company": "Databricks",
         "location": location, "is_remote": False,
         "description": f"Databricks is hiring a {search_term}. "
                        "Work on LLMs and data intelligence products. Strong Python required.",
         "job_url": "https://databricks.com/careers/1", "site": "glassdoor"},
    ]
    for j in base:
        j["url_hash"] = hashlib.sha256(j["job_url"].encode()).hexdigest()
        j.setdefault("salary_min", None)
        j.setdefault("salary_max", None)
        j.setdefault("salary_currency", "USD")
        j.setdefault("date_posted", "today")
        j.setdefault("job_type", "full-time")
        j["description_snippet"] = j["description"][:300]
    return base


# ── Scoring ───────────────────────────────────────────────────────────────────

SCORING_SYSTEM = """You are a precise job-fit evaluator. Given a user profile and a job listing,
output ONLY valid JSON — no markdown fences, no preamble. Schema:

{
  "score": <integer 0-100>,
  "summary": "<1-2 sentences: why this score>",
  "pros": ["<specific strength 1>", "<specific strength 2>", "<specific strength 3>"],
  "cons": ["<specific gap or concern 1>", "<specific concern 2>"],
  "sponsorship_likely": <true|false|null>
}

Scoring rubric:
90-100: Exceptional match — skills align tightly, company fits target, sponsorship likely
70-89:  Strong match — most requirements covered, worth applying
50-69:  Partial match — some gaps but worth considering
30-49:  Weak match — significant skill or culture misalignment
0-29:   Poor match — wrong level, wrong domain, or clearly unsuitable

Be honest. A 70 is a good score. Most jobs should be 40-75. Reserve 90+ for truly exceptional fits.
Sponsorship: mark true if the description mentions H-1B, visa, sponsorship, or "work authorisation provided".
Null if not mentioned."""


async def score_job(job: dict, identity: str) -> dict:
    """Call configured SCORE provider to score a single job against the user's identity."""
    provider = get_provider(TaskType.SCORE)
    prompt = f"""USER PROFILE:
{identity[:2000]}

JOB LISTING:
Title: {job['title']}
Company: {job['company']}
Location: {job['location']}
Remote: {job['is_remote']}
Salary: {_salary_str(job)}
Description:
{job.get('description', '')[:3000]}

Score this job for the user. Reply with JSON only."""

    try:
        raw = await provider.complete(
            system=SCORING_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
        )
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())
        return {
            "score": max(0, min(100, int(data.get("score", 50)))),
            "score_summary": str(data.get("summary", ""))[:500],
            "score_pros": json.dumps(data.get("pros", [])),
            "score_cons": json.dumps(data.get("cons", [])),
            "sponsorship_likely": data.get("sponsorship_likely"),
        }
    except Exception as exc:
        logger.warning(f"Scoring failed for {job.get('title')}: {exc}")
        return {"score": 50, "score_summary": "Score unavailable",
                "score_pros": "[]", "score_cons": "[]", "sponsorship_likely": None}


def _salary_str(job: dict) -> str:
    lo, hi = job.get("salary_min"), job.get("salary_max")
    cur = job.get("salary_currency", "USD")
    if lo and hi:
        return f"{cur} {int(lo):,} – {int(hi):,}"
    if lo:
        return f"{cur} {int(lo):,}+"
    return "Not listed"


# ── Orchestrator ──────────────────────────────────────────────────────────────

async def run_scout(
    config_id: int,
    search_term: str,
    location: str,
    sites: list[str],
    results_wanted: int,
    hours_old: int,
    distance: int,
    is_remote: bool | None,
    min_score: int,
    memory: MemoryManager,
    db_session,  # AsyncSession
) -> dict:
    """
    Full scout run:
    1. Scrape jobs
    2. Deduplicate against DB
    3. Score new listings with Claude
    4. Persist to DB
    Returns summary dict.
    """
    from sqlalchemy import select
    from app.models.db import JobListing, ScoutRun, ScoutConfig
    from app.database import AsyncSessionLocal

    _active_config_runs.add(config_id)
    run_id: int | None = None
    try:
        # Create run record
        # 1. Scrape
        async def _create_run():
            nonlocal run_id
            async with AsyncSessionLocal() as db:
                run = ScoutRun(config_id=config_id, status="RUNNING", started_at=datetime.now(timezone.utc))
                db.add(run)
                await db.commit()
                await db.refresh(run)
                run_id = run.id

        await _run_with_sqlite_retry(_create_run)
        await _update_run_progress(run_id, error_msg="Scraping job boards...")

        raw_jobs = _scrape_jobs(search_term, location, sites, results_wanted, hours_old, distance, is_remote)
        logger.info(f"[scout:{config_id}] scraped {len(raw_jobs)} listings")
        await _update_run_progress(
            run_id,
            jobs_found=len(raw_jobs),
            error_msg=f"Deduplicating results... {len(raw_jobs)} listings fetched",
        )

        if not raw_jobs:
            await _update_run_progress(
                run_id,
                status="DONE",
                finished_at=datetime.now(timezone.utc),
                jobs_found=0,
                jobs_new=0,
                jobs_scored=0,
                error_msg="Completed — no jobs found",
            )
            return {"jobs_found": 0, "jobs_new": 0, "jobs_scored": 0}

        # 2. Deduplicate
        hashes = [j["url_hash"] for j in raw_jobs]
        async with AsyncSessionLocal() as db:
            existing = await db.execute(
                select(JobListing.url_hash).where(JobListing.url_hash.in_(hashes))
            )
            existing_hashes = {r[0] for r in existing.fetchall()}

        new_jobs = [j for j in raw_jobs if j["url_hash"] not in existing_hashes]
        logger.info(f"[scout:{config_id}] {len(new_jobs)} new (deduplicated {len(raw_jobs) - len(new_jobs)})")
        await _update_run_progress(
            run_id,
            jobs_new=len(new_jobs),
            error_msg=f"Scoring jobs... 0/{len(new_jobs)} new listings",
        )

        if not new_jobs:
            await _update_run_progress(
                run_id,
                status="DONE",
                finished_at=datetime.now(timezone.utc),
                jobs_found=len(raw_jobs),
                jobs_new=0,
                jobs_scored=0,
                error_msg="Completed — no new jobs after deduplication",
            )
            return {"jobs_found": len(raw_jobs), "jobs_new": 0, "jobs_scored": 0}

        # 3. Score each new job with Claude
        identity = memory.read("L0_identity.md")
        scored = 0
        listings_to_insert: list[JobListing] = []

        total_to_score = len(new_jobs)
        for idx, job in enumerate(new_jobs, start=1):
            scoring = await score_job(job, identity)
            listing = JobListing(
                url_hash=job["url_hash"],
                job_url=job["job_url"],
                title=job["title"],
                company=job["company"],
                location=job["location"],
                is_remote=job["is_remote"],
                salary_min=job.get("salary_min"),
                salary_max=job.get("salary_max"),
                salary_currency=job.get("salary_currency"),
                description=job.get("description"),
                description_snippet=job.get("description_snippet"),
                site=job.get("site", ""),
                date_posted=job.get("date_posted"),
                job_type=job.get("job_type"),
                config_id=config_id,
                run_id=run_id,
                score=scoring["score"],
                score_summary=scoring["score_summary"],
                score_pros=scoring["score_pros"],
                score_cons=scoring["score_cons"],
                sponsorship_likely=scoring["sponsorship_likely"],
                status="NEW",
            )
            listings_to_insert.append(listing)
            if scoring["score"] is not None:
                scored += 1
            await _update_run_progress(
                run_id,
                jobs_scored=scored,
                error_msg=f"Scoring jobs... {idx}/{total_to_score}",
            )

        # 4. Persist
        await _update_run_progress(run_id, error_msg="Saving scored jobs...")
        config_name_for_email = search_term

        async def _persist_results():
            nonlocal config_name_for_email
            async with AsyncSessionLocal() as db:
                for listing in listings_to_insert:
                    db.add(listing)

                run = await db.get(ScoutRun, run_id)
                run.status = "DONE"
                run.finished_at = datetime.now(timezone.utc)
                run.jobs_found = len(raw_jobs)
                run.jobs_new = len(new_jobs)
                run.jobs_scored = scored

                config = await db.get(ScoutConfig, config_id)
                if config:
                    config.last_run_at = datetime.now(timezone.utc)
                    config_name_for_email = config.name

                await db.commit()

        await _run_with_sqlite_retry(_persist_results)

        high_score = [j for j in listings_to_insert if (j.score or 0) >= min_score]
        await _update_run_progress(
            run_id,
            error_msg=f"Completed — {len(new_jobs)} new, {scored} scored, {len(high_score)} above threshold",
        )

        if notifications_enabled():
            high_score_jobs = [
                {
                    "title": listing.title,
                    "company": listing.company,
                    "job_url": listing.job_url,
                    "location": listing.location,
                    "salary_min": listing.salary_min,
                    "salary_max": listing.salary_max,
                    "salary_currency": listing.salary_currency,
                    "score": listing.score,
                    "score_summary": listing.score_summary,
                    "sponsorship_likely": listing.sponsorship_likely,
                    "site": listing.site,
                }
                for listing in high_score
            ]
            try:
                await EmailNotificationService(memory=memory).send_scout_run_summary(
                    config_name=config_name_for_email,
                    search_term=search_term,
                    location=location,
                    min_score=min_score,
                    jobs_found=len(raw_jobs),
                    jobs_new=len(new_jobs),
                    jobs_scored=scored,
                    jobs=high_score_jobs,
                )
            except Exception as exc:
                logger.warning(f"[scout:{config_id}] email notification failed: {exc}")

        logger.info(f"[scout:{config_id}] done — {len(new_jobs)} new, {len(high_score)} above threshold")
        return {
            "jobs_found": len(raw_jobs),
            "jobs_new": len(new_jobs),
            "jobs_scored": scored,
            "high_score_count": len(high_score),
        }

    except Exception as exc:
        logger.error(f"[scout:{config_id}] run failed: {exc}", exc_info=True)
        if run_id is not None:
            async def _mark_error():
                async with AsyncSessionLocal() as db:
                    run = await db.get(ScoutRun, run_id)
                    if run:
                        run.status = "ERROR"
                        run.finished_at = datetime.now(timezone.utc)
                        run.error_msg = str(exc)[:500]
                        await db.commit()

            await _run_with_sqlite_retry(_mark_error)
        raise
    finally:
        _active_config_runs.discard(config_id)
