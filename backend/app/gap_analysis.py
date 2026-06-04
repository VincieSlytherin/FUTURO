"""
JD-to-Resume Gap Analysis
-------------------------
Turns a job description into a gap report by reusing existing building blocks:
  - `jd_parser.extract_jd_fields`  → JD summary, requirements, skills
  - `StoryVectorStore`             → semantic retrieval of STAR stories per requirement
  - L0 identity + resume_versions  → the resume corpus we match against

The deterministic core (skill matching + requirement coverage) runs without any LLM so it
is fully testable and works offline. An optional LLM layer (the SCORE provider) adds a
match score, weak-signal detection, and a targeted resume-edit checklist; it degrades
gracefully to a deterministic fallback when no provider is configured or the call fails,
mirroring `job_scout.score_job`.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.jd_parser import extract_jd_fields, fetch_url_text
from app.providers.base import TaskType
from app.providers.router import get_provider

logger = logging.getLogger(__name__)

# A requirement whose best story match is closer than this cosine distance counts as "covered".
COVERAGE_DISTANCE_THRESHOLD = 1.0


# ── Deterministic core ────────────────────────────────────────────────────────

def build_resume_corpus(identity: str, resume: str) -> str:
    """Lowercased text we search for skill evidence: L0 identity + resume bullets."""
    return f"{identity or ''}\n{resume or ''}".lower()


def skill_present(skill: str, corpus: str) -> bool:
    """True if `skill` appears in the corpus as a standalone token (case-insensitive)."""
    pattern = rf"(?<![a-z0-9]){re.escape(skill.lower())}(?![a-z0-9])"
    return re.search(pattern, corpus) is not None


def match_skills(jd_skills: list[str], corpus: str) -> tuple[list[str], list[str]]:
    """Split JD skills into (matched, missing) based on evidence in the resume corpus."""
    matched, missing = [], []
    for skill in jd_skills:
        (matched if skill_present(skill, corpus) else missing).append(skill)
    return matched, missing


def requirement_coverage(
    requirements: list[str],
    store: Any | None,
    threshold: float = COVERAGE_DISTANCE_THRESHOLD,
) -> list[dict[str, Any]]:
    """For each requirement, find the closest STAR story via semantic retrieval."""
    coverage: list[dict[str, Any]] = []
    for requirement in requirements:
        entry: dict[str, Any] = {
            "requirement": requirement,
            "matched_story_id": None,
            "matched_story": None,
            "distance": None,
            "covered": False,
        }
        if store is not None:
            try:
                matches = store.search(requirement, n_results=1)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(f"[gap] story retrieval failed: {exc}")
                matches = []
            if matches:
                best = matches[0]
                entry.update(
                    matched_story_id=best.story_id,
                    matched_story=best.title,
                    distance=round(best.distance, 4),
                    covered=best.distance < threshold,
                )
        coverage.append(entry)
    return coverage


# ── LLM enrichment (optional, graceful fallback) ──────────────────────────────

GAP_SYSTEM = """You are a precise resume-gap analyst. Given a job description summary, the
candidate's matched and missing skills, how their STAR stories cover each requirement, and
their current resume bullets, output ONLY valid JSON — no markdown fences, no preamble. Schema:

{
  "overall_match_score": <integer 0-100>,
  "match_summary": "<1-2 sentences: how strong this fit is and why>",
  "weak_signals": ["<requirement or skill that is only partially evidenced>", ...],
  "resume_edit_checklist": ["<specific, actionable edit to close a gap>", ...]
}

Rules:
- Base the score on skill overlap AND requirement coverage. Most real fits land 45-80.
- weak_signals: things present but thin (e.g. mentioned once, no metric) — NOT the fully missing skills.
- resume_edit_checklist: concrete edits ("Add a bullet quantifying X", "Move the Y project up",
  "Surface a story showing Z"). 3-6 items. Prioritize the highest-impact gaps first.
- Be honest and specific. No generic filler."""


def _coverage_digest(coverage: list[dict[str, Any]]) -> str:
    lines = []
    for entry in coverage:
        if entry["matched_story"]:
            status = "covered" if entry["covered"] else "weakly covered"
            lines.append(f"- {entry['requirement']} → {status} by \"{entry['matched_story']}\"")
        else:
            lines.append(f"- {entry['requirement']} → no matching story")
    return "\n".join(lines) if lines else "- (no requirements extracted)"


async def _llm_enrich(
    *,
    jd_summary: str | None,
    matched_skills: list[str],
    missing_skills: list[str],
    coverage: list[dict[str, Any]],
    resume: str,
) -> dict[str, Any] | None:
    try:
        provider = get_provider(TaskType.SCORE)
    except RuntimeError:
        return None

    prompt = f"""JOB SUMMARY:
{(jd_summary or 'Not provided')[:1200]}

MATCHED SKILLS (evidenced in resume): {', '.join(matched_skills) or 'none'}
MISSING SKILLS (no evidence found): {', '.join(missing_skills) or 'none'}

REQUIREMENT COVERAGE:
{_coverage_digest(coverage)}

CURRENT RESUME BULLETS:
{(resume or 'Not provided')[:2500]}

Produce the gap analysis JSON."""

    try:
        raw = await provider.complete(
            system=GAP_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=700,
        )
    except Exception as exc:
        logger.warning(f"[gap] LLM enrichment failed: {exc}")
        return None

    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        data = json.loads(raw.strip())
    except json.JSONDecodeError:
        return None

    return {
        "overall_match_score": max(0, min(100, int(data.get("overall_match_score", 50)))),
        "match_summary": str(data.get("match_summary", ""))[:600],
        "weak_signals": [str(s) for s in data.get("weak_signals", []) if str(s).strip()][:8],
        "resume_edit_checklist": [str(s) for s in data.get("resume_edit_checklist", []) if str(s).strip()][:8],
    }


def _fallback_enrichment(
    matched_skills: list[str],
    missing_skills: list[str],
    coverage: list[dict[str, Any]],
) -> dict[str, Any]:
    total = len(matched_skills) + len(missing_skills)
    score = round(100 * len(matched_skills) / total) if total else 50

    checklist: list[str] = []
    for skill in missing_skills[:5]:
        checklist.append(f"Add concrete evidence of {skill} to your resume (project, metric, or bullet).")
    for entry in coverage:
        if not entry["matched_story"] or not entry["covered"]:
            checklist.append(f"Surface a STAR story that covers: {entry['requirement']}")
        if len(checklist) >= 6:
            break

    summary = (
        f"Matched {len(matched_skills)} of {total} target skills"
        + (f"; {len(missing_skills)} gaps to address." if missing_skills else "; strong skill overlap.")
        if total
        else "No target skills were extracted from this JD."
    )
    return {
        "overall_match_score": score,
        "match_summary": summary,
        "weak_signals": [],
        "resume_edit_checklist": checklist,
    }


# ── Orchestrator ──────────────────────────────────────────────────────────────

async def analyze_gap(
    *,
    jd_text: str | None = None,
    jd_url: str | None = None,
    identity: str = "",
    resume: str = "",
    store: Any | None = None,
    use_llm: bool = True,
) -> dict[str, Any]:
    """
    Full gap analysis:
    1. Parse the JD (text or URL) into summary / requirements / skills.
    2. Match JD skills against the resume corpus (deterministic).
    3. Retrieve the closest STAR story for each requirement (semantic).
    4. Enrich with an LLM-generated score + weak signals + edit checklist (graceful fallback).
    """
    source_text = (jd_text or "").strip()
    if not source_text and jd_url:
        source_text = fetch_url_text(jd_url)
    if not source_text:
        raise ValueError("No job description text provided (pass jd_text or a fetchable jd_url).")

    fields = extract_jd_fields(source_text)
    jd_summary = fields.get("jd_summary")
    requirements = json.loads(fields.get("jd_requirements_json") or "[]")
    jd_skills = json.loads(fields.get("jd_skills_json") or "[]")

    corpus = build_resume_corpus(identity, resume)
    matched_skills, missing_skills = match_skills(jd_skills, corpus)
    coverage = requirement_coverage(requirements, store)

    enrichment = None
    if use_llm:
        enrichment = await _llm_enrich(
            jd_summary=jd_summary,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            coverage=coverage,
            resume=resume,
        )
    if enrichment is None:
        enrichment = _fallback_enrichment(matched_skills, missing_skills, coverage)

    return {
        "jd_summary": jd_summary,
        "jd_skills": jd_skills,
        "jd_requirements": requirements,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "requirement_coverage": coverage,
        "work_mode": fields.get("work_mode"),
        "sponsorship_detected": fields.get("sponsorship_detected", False),
        **enrichment,
    }
