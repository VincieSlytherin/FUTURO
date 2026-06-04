"""
Scout recommendations
----------------------
Turns an already-scored JobListing into a prioritized application action. This is the
"what should I do about this job" layer on top of the LLM fit-score: deterministic,
explainable, and built only from fields already persisted on the listing (score,
sponsorship_likely, pros/cons, salary) — so it needs no extra LLM call or DB column.
"""
from __future__ import annotations

import json
from typing import Any

PRIORITY_RANK = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}


def _as_list(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if isinstance(raw, str) and raw.strip():
        try:
            data = json.loads(raw)
            return [str(x) for x in data] if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []
    return []


def recommend(job: dict) -> dict:
    """
    Return {priority, priority_rank, recommended_action, reasons} for a scored job dict.
    `job` is the serialized listing (score, sponsorship_likely, score_pros/cons, salary_*).
    """
    score = job.get("score") or 0
    sponsorship = job.get("sponsorship_likely")
    pros = _as_list(job.get("score_pros"))
    cons = _as_list(job.get("score_cons"))

    if score >= 85:
        priority, verb = "HIGH", "Apply now"
    elif score >= 70:
        priority = "HIGH" if sponsorship else "MEDIUM"
        verb = "Apply"
    elif score >= 55:
        priority, verb = "MEDIUM", "Consider applying"
    else:
        priority, verb = "LOW", "Skip unless it's a stretch goal"

    reasons: list[str] = []
    if pros:
        reasons.append("Strong match: " + ", ".join(pros[:3]))
    if cons:
        reasons.append("Watch: " + ", ".join(cons[:2]))
    if sponsorship is True:
        reasons.append("Sponsorship looks likely.")
    elif sponsorship is None and priority in ("HIGH", "MEDIUM"):
        reasons.append("Verify visa sponsorship before investing time.")

    action_parts = [f"{verb} with your strongest tailored resume."]
    if priority == "HIGH":
        action_parts.append("Ask for a referral first — this is a top-priority fit.")
    if sponsorship is None and priority in ("HIGH", "MEDIUM"):
        action_parts.append("Confirm sponsorship.")

    return {
        "priority": priority,
        "priority_rank": PRIORITY_RANK[priority],
        "recommended_action": " ".join(action_parts),
        "reasons": reasons,
    }
