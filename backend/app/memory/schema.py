"""
Memory schema
-------------
Single source of truth for which sections each memory file may hold, plus a validator
shared by the agent memory-extraction path and the memory API. Keeping this here (a
dependency-light module) lets both `agents.base` and `api.memory` import it without pulling
in the provider stack.
"""
from __future__ import annotations

import re

# file → the canonical ## sections it owns.
MEMORY_SECTIONS: dict[str, list[str]] = {
    "L0_identity.md": [
        "Who I am",
        "Career narrative",
        "Target role",
        "Technical skills",
        "Signature projects",
    ],
    "L1_campaign.md": [
        "Status snapshot",
        "Weekly focus",
        "Mindset check",
        "Strategy notes",
    ],
    "planner.md": [
        "Daily tasks",
        "Learning backlog",
    ],
    "L2_knowledge.md": [
        "Job search strategy",
        "Sourcing channels",
        "Market intelligence",
        "Interview prep learnings",
        "Insights from content",
        "Strategy iteration log",
    ],
    "stories_bank.md": [
        "Quick-reference index",
        "Coverage gaps",
    ],
    "resume_versions.md": [
        "Current version: v1.0",
        "Bullets",
    ],
    "interview_log.md": [
        "Active interviews",
        "Cross-company patterns",
        "Questions that keep coming up",
        "My blind spots",
    ],
}

VALID_ACTIONS = {"append", "replace", "create"}

# stories_bank.md grows dynamic per-story blocks (## STORY-001 · Title) that aren't fixed sections.
_STORY_SECTION = re.compile(r"^STORY-\d+")


def validate_update(file: str, section: str, action: str, content: str) -> tuple[bool, str | None]:
    """
    Return (ok, error). Mirrors BaseAgent._is_allowed_update so a proposal accepted by the
    agent is also accepted by the API, and an out-of-schema manual call is rejected.
    """
    if action not in VALID_ACTIONS:
        return False, f"Invalid action '{action}'. Must be one of {sorted(VALID_ACTIONS)}."

    allowed_sections = MEMORY_SECTIONS.get(file)
    if allowed_sections is None:
        return False, f"Unknown memory file '{file}'."

    if not content.strip():
        return False, "Update content is empty."

    # Dynamic story blocks: append a new block (empty section) or replace/append an existing one.
    if file == "stories_bank.md" and (_STORY_SECTION.match(section or "") or "·" in (section or "")):
        return True, None

    if action == "replace" and not section.strip():
        return False, "A 'replace' update must target a section."

    if section and section not in allowed_sections:
        return False, f"Section '{section}' is not allowed in {file}. Allowed: {allowed_sections}."

    return True, None
