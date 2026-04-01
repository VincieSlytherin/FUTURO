from __future__ import annotations

import asyncio
import json
import re
from typing import Any


SKILL_PATTERNS = [
    "Python", "SQL", "AWS", "GCP", "Azure", "Databricks", "Spark", "PySpark",
    "Docker", "Kubernetes", "Terraform", "FastAPI", "React", "TypeScript",
    "LLM", "RAG", "LangChain", "LangGraph", "OpenAI", "Anthropic", "Ollama",
    "PyTorch", "Transformers", "MLflow", "Airflow", "Pandas", "Polars",
]

RESPONSIBILITY_HEADERS = (
    "responsibilities",
    "what you'll do",
    "what you will do",
    "what youll do",
    "in this role",
    "you will",
)

REQUIREMENT_HEADERS = (
    "requirements",
    "qualifications",
    "what we're looking for",
    "what we’re looking for",
    "what we're looking for",
    "basic qualifications",
    "preferred qualifications",
    "what you bring",
    "must have",
    "nice to have",
)


def _clean_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"\u00a0", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _bullet_lines(text: str) -> list[str]:
    items = []
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^[-*•]\s+", stripped):
            items.append(re.sub(r"^[-*•]\s+", "", stripped))
    return items


def _extract_section_bullets(text: str, headers: tuple[str, ...]) -> list[str]:
    lines = [line.rstrip() for line in text.splitlines()]
    found: list[str] = []
    collecting = False

    for raw in lines:
        line = raw.strip()
        normalized = re.sub(r"[:：]+$", "", line.lower())

        if any(header == normalized for header in headers):
            collecting = True
            continue

        if collecting and line and not re.match(r"^[-*•]\s+", line) and len(line.split()) <= 6:
            collecting = False

        if collecting:
            if re.match(r"^[-*•]\s+", line):
                found.append(re.sub(r"^[-*•]\s+", "", line))
            elif line:
                found.append(line)

    deduped: list[str] = []
    seen: set[str] = set()
    for item in found:
        normalized = item.strip().lower()
        if normalized and normalized not in seen:
            deduped.append(item.strip())
            seen.add(normalized)
    return deduped[:8]


def _extract_summary(text: str, requirements: list[str] | None = None, responsibilities: list[str] | None = None) -> str | None:
    top = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^[-*•]\s+", stripped):
            continue
        if len(stripped.split()) <= 2:
            continue
        top.append(stripped)
        if len(" ".join(top)) > 420:
            break

    joined = " ".join(top)[:600]
    sentences = re.split(r"(?<=[.!?])\s+", joined)
    summary = " ".join(sentence for sentence in sentences[:2] if sentence).strip()
    if summary:
        return summary[:500]

    req = (requirements or [])[:2]
    resp = (responsibilities or [])[:2]
    parts = []
    if resp:
        parts.append(f"Key responsibilities include {', '.join(resp)}")
    if req:
        parts.append(f"Core requirements include {', '.join(req)}")
    fallback = ". ".join(parts).strip()
    return f"{fallback}."[:500] if fallback else None


def _extract_skills(text: str) -> list[str]:
    found = []
    lowered = text.lower()
    for skill in SKILL_PATTERNS:
        pattern = skill.lower()
        if pattern in lowered:
            found.append(skill)
    return found[:12]


def _detect_work_mode(text: str) -> str | None:
    lowered = text.lower()
    if "hybrid" in lowered:
        return "HYBRID"
    if "remote" in lowered or "work from home" in lowered:
        return "REMOTE"
    if "on-site" in lowered or "onsite" in lowered or "on site" in lowered:
        return "ONSITE"
    return None


def _detect_sponsorship(text: str) -> bool:
    lowered = text.lower()
    sponsorship_terms = [
        "h-1b", "visa sponsorship", "sponsorship available", "work authorization provided",
        "will sponsor", "can sponsor", "visa transfer",
    ]
    return any(term in lowered for term in sponsorship_terms)


def _extract_salary_range(text: str) -> str | None:
    match = re.search(
        r"(\$?\d{2,3}(?:,\d{3})+)\s*(?:-|–|to)\s*(\$?\d{2,3}(?:,\d{3})+)",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return f"{match.group(1)} - {match.group(2)}"

    match = re.search(r"(\$?\d{2,3}(?:,\d{3})+\+)", text, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def extract_jd_fields(text: str) -> dict[str, Any]:
    cleaned = _clean_text(text)
    if not cleaned:
        return {}

    responsibilities = _extract_section_bullets(cleaned, RESPONSIBILITY_HEADERS)
    requirements = _extract_section_bullets(cleaned, REQUIREMENT_HEADERS)
    skills = _extract_skills(cleaned)

    if not requirements:
        requirements = [item for item in _bullet_lines(cleaned) if len(item.split()) > 3][:6]

    return {
        "job_description_text": cleaned[:12000],
        "jd_summary": _extract_summary(cleaned, requirements=requirements, responsibilities=responsibilities),
        "jd_requirements_json": json.dumps(requirements[:8]),
        "jd_responsibilities_json": json.dumps(responsibilities[:8]),
        "jd_skills_json": json.dumps(skills[:12]),
        "work_mode": _detect_work_mode(cleaned),
        "sponsorship_detected": _detect_sponsorship(cleaned),
        "salary_range_detected": _extract_salary_range(cleaned),
    }


def fetch_url_text(url: str) -> str:
    try:
        import trafilatura

        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded, include_links=False)
            if text:
                return text
    except Exception:
        pass

    try:
        import httpx

        resp = httpx.get(url, timeout=10, follow_redirects=True)
        return resp.text[:12000]
    except Exception:
        return ""


async def enrich_company_from_jd(
    *,
    url: str | None,
    job_description_text: str | None,
    salary_range: str | None,
    sponsorship_confirmed: bool,
) -> dict[str, Any]:
    source_text = (job_description_text or "").strip()
    if not source_text and url:
        source_text = await asyncio.to_thread(fetch_url_text, url)

    extracted = extract_jd_fields(source_text) if source_text else {}
    if not extracted:
        return {}

    updates: dict[str, Any] = {
        "job_description_text": extracted.get("job_description_text"),
        "jd_summary": extracted.get("jd_summary"),
        "jd_requirements_json": extracted.get("jd_requirements_json"),
        "jd_responsibilities_json": extracted.get("jd_responsibilities_json"),
        "jd_skills_json": extracted.get("jd_skills_json"),
        "work_mode": extracted.get("work_mode"),
    }

    if not sponsorship_confirmed and extracted.get("sponsorship_detected"):
        updates["sponsorship_confirmed"] = True

    detected_salary = extracted.get("salary_range_detected")
    if not salary_range and detected_salary:
        updates["salary_range"] = detected_salary

    return {key: value for key, value in updates.items() if value not in (None, "", "[]")}
