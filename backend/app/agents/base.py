"""
Agent base — provider-agnostic
-------------------------------
All agents talk to LLMProvider, never to SDK clients directly.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import AsyncIterator

from app.config import settings
from app.custom_instructions import CustomInstructionManager
from app.memory.manager import AgentContext, MemoryManager
from app.models.schemas import MemoryUpdate
from app.providers.base import TaskType
from app.providers.router import get_provider

PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(name: str) -> str:
    path = PROMPTS_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


BASE_PERSONA = _load_prompt("base_persona")

MEMORY_TARGETS: dict[str, list[str]] = {
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

MEMORY_EXTRACTION_SYSTEM = """You extract durable user memory from a Futuro chat session.

Return only strict JSON. No markdown fences. No commentary.

Output format:
[
  {
    "file": "resume_versions.md",
    "section": "Bullets",
    "action": "append",
    "content": "- concise bullet to add",
    "reason": "why this should be stored"
  }
]

Rules:
- Only store durable facts the user explicitly shared about themselves, their resume, their goals, their job search state, their interview patterns, or reusable stories.
- Do not store generic chit-chat, temporary pleasantries, or assistant-authored suggestions unless the user clearly adopted them.
- Prefer concise markdown snippets.
- Preserve concrete resume facts: role names, skills, stacks, quantified achievements, and target roles.
- Prefer saving newly stated user preferences, constraints, and priorities so L1 needs little manual upkeep.
- Capture new company or pipeline changes when the user mentions applying, interviewing, waiting, rejecting, or prioritizing a company.
- Capture interview outcomes, patterns, and lessons when the user debriefs an interview.
- Capture newly claimed technical skills, tools, or domains when the user says they have them or used them.
- Capture concrete daily tasks and learning goals when the user is planning their week or saying what they want to study next.
- Prefer using planner.md for living checklists that can be updated, forgotten, edited, or reordered over time.
- When the user pastes resume content, prefer storing it in "resume_versions.md" under "Bullets".
- When the user shares personal background, role target, skills, or signature projects, store it in "L0_identity.md".
- When the user shares ongoing search status or priorities, store it in "L1_campaign.md".
- When the user shares company-specific next steps, blockers, or search preferences, prefer "L1_campaign.md".
- When the user shares a concrete action item for today or this week, prefer "planner.md" under "Daily tasks".
- When the user shares something they want to learn, practice, or review, prefer "planner.md" under "Learning backlog".
- When the user shares reusable strategy or market learnings, store it in "L2_knowledge.md".
- When the user shares interview outcomes, recurring question patterns, or weak spots, prefer "interview_log.md".
- Avoid duplicating facts already present in memory.
- Use only these files and sections:
  - L0_identity.md: Who I am, Career narrative, Target role, Technical skills, Signature projects
  - L1_campaign.md: Status snapshot, Weekly focus, Mindset check, Strategy notes
  - planner.md: Daily tasks, Learning backlog
  - L2_knowledge.md: Job search strategy, Sourcing channels, Market intelligence, Interview prep learnings, Insights from content, Strategy iteration log
  - stories_bank.md: Quick-reference index
  - resume_versions.md: Current version: v1.0, Bullets
  - interview_log.md: Active interviews, Cross-company patterns, Questions that keep coming up, My blind spots
- Use action "append" unless replace is clearly required.
- Return [] when nothing should be saved.
"""


class BaseAgent:
    intent: str = "GENERAL"
    prompt_name: str = "core_agent"

    def __init__(self, memory: MemoryManager):
        self.memory = memory
        self._agent_prompt = _load_prompt(self.prompt_name)
        self._custom_instructions = CustomInstructionManager(settings.custom_instructions_path)

    def _build_system(self, ctx: AgentContext) -> str:
        parts = [BASE_PERSONA, "\n\n---\n\n", self._agent_prompt]
        custom = self._custom_instructions.load()
        if custom.get("global"):
            parts.append(
                f"\n\n## User custom instructions for all functions\n\n{custom['global']}"
            )
        if custom.get(self.intent):
            parts.append(
                f"\n\n## User custom instructions for {self.intent}\n\n{custom[self.intent]}"
            )
        if ctx.identity:
            parts.append(f"\n\n## Your memory — who this person is\n\n{ctx.identity}")
        if ctx.campaign:
            parts.append(f"\n\n## Their current search state\n\n{ctx.campaign}")
        if ctx.planner:
            parts.append(f"\n\n## Their living planner\n\n{ctx.planner}")
        if ctx.stories:
            parts.append(f"\n\n## Their story bank\n\n{ctx.stories}")
        if ctx.resume:
            parts.append(f"\n\n## Their resume versions\n\n{ctx.resume}")
        if ctx.interview_log:
            parts.append(f"\n\n## Their interview log\n\n{ctx.interview_log}")
        if ctx.knowledge_section:
            parts.append(f"\n\n## Their current search strategy\n\n{ctx.knowledge_section}")
        return "".join(parts)

    async def stream(
        self,
        message: str,
        history: list[dict],
        ctx: AgentContext,
    ) -> AsyncIterator[str]:
        provider = get_provider(TaskType.CHAT)
        messages = [{"role": m["role"], "content": m["content"]} for m in history]
        messages.append({"role": "user", "content": message})
        async for token in provider.stream(system=self._build_system(ctx), messages=messages):
            yield token

    async def post_process(
        self,
        response: str,
        message: str,
        ctx: AgentContext,
        history: list[dict] | None = None,
    ) -> list[MemoryUpdate]:
        if self._looks_like_resume_payload(message):
            resume_updates = self._extract_resume_memory_updates(message)
            if resume_updates:
                return resume_updates
        story_updates = self._extract_story_bank_updates(message, response, ctx)
        memory_updates = await self._extract_memory_updates(response, message, ctx, history=history)
        return self._merge_updates(story_updates + memory_updates)

    async def _extract_memory_updates(
        self,
        response: str,
        message: str,
        ctx: AgentContext,
        history: list[dict] | None = None,
    ) -> list[MemoryUpdate]:
        session_transcript = self._build_session_transcript(history or [], message, response)
        if not self._should_extract_memory(session_transcript):
            return []

        try:
            provider = get_provider(TaskType.CHAT)
        except RuntimeError:
            return self._fallback_memory_updates(message)

        existing_memory = "\n\n".join(filter(None, [
            f"[L0_identity.md]\n{ctx.identity[:1600]}",
            f"[L1_campaign.md]\n{ctx.campaign[:1200]}",
            f"[planner.md]\n{ctx.planner[:1200]}",
            f"[resume_versions.md]\n{ctx.resume[:1600]}",
            f"[stories_bank.md]\n{ctx.stories[:1200]}",
            f"[interview_log.md]\n{ctx.interview_log[:1200]}",
            f"[L2_knowledge.md]\n{ctx.knowledge_section[:1200]}",
        ]))
        user_turn = (
            f"Intent: {self.intent}\n\n"
            f"Session transcript:\n{session_transcript}\n\n"
            f"Existing memory snapshot:\n{existing_memory or '[empty]'}"
        )

        try:
            raw = await provider.complete(
                system=MEMORY_EXTRACTION_SYSTEM,
                messages=[{"role": "user", "content": user_turn}],
                max_tokens=900,
            )
        except Exception:
            return self._fallback_memory_updates(message)

        parsed = self._parse_memory_updates(raw)
        return parsed or self._fallback_memory_updates(message)

    def _build_session_transcript(
        self,
        history: list[dict],
        message: str,
        response: str,
    ) -> str:
        trimmed_history = list(history[-8:])
        if (
            trimmed_history
            and trimmed_history[-1].get("role") == "user"
            and trimmed_history[-1].get("content", "").strip() == message.strip()
        ):
            trimmed_history = trimmed_history[:-1]

        lines: list[str] = []
        for turn in trimmed_history:
            role = str(turn.get("role", "user")).strip().upper() or "USER"
            content = str(turn.get("content", "")).strip()
            if content:
                lines.append(f"{role}: {content}")
        if message.strip():
            lines.append(f"USER: {message.strip()}")
        if response.strip():
            lines.append(f"ASSISTANT: {response.strip()}")
        return "\n\n".join(lines)

    def _parse_memory_updates(self, raw: str) -> list[MemoryUpdate]:
        raw = raw.strip()
        if not raw:
            return []

        candidates = None
        try:
            candidates = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"(\[\s*{.*}\s*\]|\[\s*\])", raw, re.DOTALL)
            if match:
                try:
                    candidates = json.loads(match.group(1))
                except json.JSONDecodeError:
                    return []
            else:
                return []

        if isinstance(candidates, dict):
            candidates = [candidates]
        if not isinstance(candidates, list):
            return []

        updates: list[MemoryUpdate] = []
        for item in candidates:
            if not isinstance(item, dict):
                continue
            try:
                update = MemoryUpdate(**item)
            except Exception:
                continue
            if not self._is_allowed_update(update):
                continue
            target_text = self.memory.read(update.file)
            if update.content.strip() and update.content.strip() in target_text:
                continue
            updates.append(update)
        return updates

    def _is_allowed_update(self, update: MemoryUpdate) -> bool:
        allowed_sections = MEMORY_TARGETS.get(update.file)
        if allowed_sections is None:
            return False
        if update.file == "stories_bank.md" and update.section.startswith("STORY-"):
            return bool(update.content.strip())
        if update.section and update.section not in allowed_sections:
            return False
        if not update.content.strip():
            return False
        if update.action == "replace" and not update.section:
            return False
        return True

    def _should_extract_memory(self, transcript: str) -> bool:
        cleaned = transcript.strip()
        if len(cleaned) >= 80:
            return True
        lowered = cleaned.lower()
        keywords = [
            "resume",
            "cv",
            "experience",
            "worked at",
            "i am",
            "my background",
            "skills",
            "target role",
            "interview",
            "job search",
            "remember this",
            "task",
            "todo",
            "to-do",
            "today",
            "this week",
            "checklist",
            "learn",
            "study",
            "applied",
            "screen",
            "onsite",
            "offer",
            "prefer",
            "looking for",
            "avoid",
            "learned",
        ]
        return any(keyword in lowered for keyword in keywords)

    def _fallback_memory_updates(self, message: str) -> list[MemoryUpdate]:
        if not self._looks_like_resume_payload(message):
            return []
        return self._extract_resume_memory_updates(message)

    def _looks_like_resume_payload(self, message: str) -> bool:
        lowered = message.lower()
        signals = [
            "resume",
            "cv",
            "experience",
            "skills",
            "worked at",
            "engineer",
            "intern",
            "project",
        ]
        bullet_like_lines = sum(
            1
            for line in message.splitlines()
            if line.strip().startswith(("-", "*", "•"))
        )
        return (
            len(message.strip()) >= 200 and
            (bullet_like_lines >= 2 or sum(token in lowered for token in signals) >= 3)
        )

    def _extract_resume_memory_updates(self, message: str) -> list[MemoryUpdate]:
        text = self._resume_source_text(message)
        if not text:
            return []

        summary = self._extract_resume_section(text, "Summary", "Professional Experience")
        experience = self._extract_resume_section(text, "Professional Experience", "AI Projects")
        projects = self._extract_resume_section(text, "AI Projects", "Education")
        education = self._extract_resume_section(text, "Education", "Skills")
        skills = self._extract_resume_section(text, "Skills", None)

        experience_bullets = self._extract_resume_bullets(experience, limit=8)
        project_bullets = self._extract_resume_bullets(projects, limit=4)
        education_lines = self._extract_resume_education(education, limit=3)
        skill_lines = self._extract_resume_skills(skills, limit=6)
        summary_lines = self._extract_resume_summary(summary, limit=3)

        resume_parts: list[str] = []
        if summary_lines:
            resume_parts.append("#### Imported summary")
            resume_parts.extend(summary_lines)
        if experience_bullets:
            resume_parts.append("\n#### Professional experience highlights")
            resume_parts.extend(experience_bullets)
        if project_bullets:
            resume_parts.append("\n#### Project highlights")
            resume_parts.extend(project_bullets)
        if education_lines:
            resume_parts.append("\n#### Education")
            resume_parts.extend(education_lines)
        if skill_lines:
            resume_parts.append("\n#### Skills")
            resume_parts.extend(skill_lines)

        who_i_am_lines: list[str] = []
        target_role = self._infer_target_role(summary_lines, experience_bullets)
        location = self._extract_resume_location(text)
        if target_role or location:
            who_i_am = "- " + " ".join(
                part for part in [
                    "Ran Ju" if "ran ju" in text.lower() else "",
                    f"is {target_role}" if target_role else "",
                    f"based in {location}." if location else "",
                ]
                if part
            ).strip()
            if who_i_am != "-":
                who_i_am_lines.append(who_i_am)

        updates: list[MemoryUpdate] = []
        if resume_parts:
            updates.append(
                MemoryUpdate(
                    file="resume_versions.md",
                    section="Bullets",
                    action="replace",
                    content="\n".join(resume_parts).strip(),
                    reason="Imported current resume snapshot from chat",
                )
            )
        if who_i_am_lines:
            updates.append(
                MemoryUpdate(
                    file="L0_identity.md",
                    section="Who I am",
                    action="replace",
                    content="\n".join(who_i_am_lines).strip(),
                    reason="Updated identity snapshot from imported resume",
                )
            )
        if skill_lines:
            updates.append(
                MemoryUpdate(
                    file="L0_identity.md",
                    section="Technical skills",
                    action="replace",
                    content="\n".join(skill_lines).strip(),
                    reason="Updated identity snapshot from imported resume",
                )
            )
        return updates

    def _resume_source_text(self, message: str) -> str:
        text = message.replace("\\@", "@").replace("\\ ", " ")
        text = re.sub(r"^This is my resume:\s*", "", text, flags=re.IGNORECASE)
        start = re.search(r"=\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+", text)
        if start:
            text = text[start.start():]

        text = re.sub(r"#link\(\"[^\"]+\"\)\[([^\]]+)\]", r"\1", text)
        text = re.sub(r"#h\([^)]+\)", " ", text)
        text = re.sub(r"#chiline\(\)", " ", text)
        text = re.sub(r"#(?:show|set|let)\b.*?(?=(?:\s+=\s+[A-Z])|(?:\s+==\s+[A-Z])|$)", " ", text, flags=re.DOTALL)
        text = re.sub(r"//\s*-\s.*?(?=(?:\s+-\s+)|(?:\s+==\s+[A-Z])|$)", " ", text, flags=re.DOTALL)
        text = text.replace("//", " ")
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _extract_resume_section(self, text: str, start: str, end: str | None) -> str:
        if end:
            pattern = rf"==\s*{re.escape(start)}\s+(.*?)\s+==\s*{re.escape(end)}"
        else:
            pattern = rf"==\s*{re.escape(start)}\s+(.*)$"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def _extract_resume_bullets(self, text: str, limit: int) -> list[str]:
        if not text:
            return []
        raw_bullets = re.findall(r"(?:^|\s)-\s+(.*?)(?=\s+-\s+|$)", text, re.DOTALL)
        cleaned = [self._clean_resume_fragment(bullet) for bullet in raw_bullets]
        deduped: list[str] = []
        seen: set[str] = set()
        for bullet in cleaned:
            if len(bullet) < 20:
                continue
            key = re.sub(r"[^a-z0-9]+", "", bullet.lower())
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(f"- {bullet}")
            if len(deduped) >= limit:
                break
        return deduped

    def _extract_resume_summary(self, text: str, limit: int) -> list[str]:
        cleaned = self._clean_resume_fragment(text)
        if not cleaned:
            return []
        sentences = re.split(r"(?<=[.!?])\s+", cleaned)
        result: list[str] = []
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 30:
                continue
            result.append(f"- {sentence}")
            if len(result) >= limit:
                break
        return result

    def _extract_resume_education(self, text: str, limit: int) -> list[str]:
        entries = re.findall(r"\*([^*]+)\*\s+#h\(1fr\)\s+([^\\]+)\\\s+([^#]+?)#h\(1fr\)\s+_([^_]+)_", text)
        result = []
        for school, location, degree, dates in entries[:limit]:
            line = self._clean_resume_fragment(f"{school} — {degree} — {location.strip()} — {dates.strip()}")
            if line:
                result.append(f"- {line}")
        if result:
            return result
        cleaned = self._clean_resume_fragment(text)
        return [f"- {cleaned}"] if cleaned else []

    def _extract_resume_skills(self, text: str, limit: int) -> list[str]:
        if not text:
            return []
        raw_bullets = re.findall(r"(?:^|\s)-\s+(.*?)(?=\s+-\s+|$)", text, re.DOTALL)
        result: list[str] = []
        seen: set[str] = set()
        for bullet in raw_bullets:
            cleaned = self._clean_resume_fragment(bullet)
            if len(cleaned) < 12:
                continue
            key = re.sub(r"[^a-z0-9]+", "", cleaned.lower())
            if key in seen:
                continue
            seen.add(key)
            result.append(f"- {cleaned}")
            if len(result) >= limit:
                break
        return result

    def _infer_target_role(self, summary_lines: list[str], experience_bullets: list[str]) -> str | None:
        corpus = " ".join(summary_lines + experience_bullets)
        candidates = [
            "an Applied AI Engineer",
            "an AI Systems Engineer",
            "a GenAI Systems Engineer",
            "a Machine Learning Engineer",
        ]
        lowered = corpus.lower()
        for candidate in candidates:
            role = candidate.replace("an ", "").replace("a ", "").lower()
            if role in lowered:
                return candidate
        return None

    def _extract_resume_location(self, text: str) -> str | None:
        match = re.search(r"=\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\s+([A-Z][a-z]+,\s+[A-Z]{2})\s+\|", text)
        return match.group(1).strip() if match else None

    def _clean_resume_fragment(self, text: str) -> str:
        cleaned = re.sub(r"#link\(\"[^\"]+\"\)\[([^\]]+)\]", r"\1", text)
        cleaned = re.sub(r"#h\([^)]+\)", " ", cleaned)
        cleaned = cleaned.replace("*", "").replace("_", "")
        cleaned = cleaned.replace("`", "").replace("\\", "")
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip(" -;,.")

    def _extract_story_bank_updates(
        self,
        message: str,
        response: str,
        ctx: AgentContext,
    ) -> list[MemoryUpdate]:
        structured_stories = self._parse_structured_story_blocks(response) or self._parse_structured_story_blocks(message)
        core_stories = self._parse_story_inventory(response) or self._parse_story_inventory(message)
        coverage_gaps = self._parse_coverage_gaps(response) or self._parse_coverage_gaps(message)

        if not structured_stories and not core_stories and not coverage_gaps:
            return []

        existing_entries = self._parse_existing_story_entries(ctx.stories)
        existing_titles = {entry["title"].lower() for entry in existing_entries}
        next_story_number = self._next_story_number(existing_entries)

        new_entries: list[dict[str, str]] = []
        replacement_updates: list[MemoryUpdate] = []

        for story in structured_stories:
            title = story["title"].strip()
            if not title:
                continue

            existing = next((entry for entry in existing_entries if entry["title"].lower() == title.lower()), None)
            story_id = existing["story_id"] if existing else f"STORY-{next_story_number:03d}"
            if not existing:
                next_story_number += 1

            entry = {
                "story_id": story_id,
                "title": title,
                "one_liner": story["one_liner"].strip(),
            }

            if existing:
                existing["one_liner"] = entry["one_liner"] or existing.get("one_liner", "")
                replacement_updates.append(
                    MemoryUpdate(
                        file="stories_bank.md",
                        section=f'{story_id} · {title}',
                        action="replace",
                        content=self._build_story_block_body(story),
                        reason="Updated detailed story bank entry from chat",
                    )
                )
            else:
                new_entries.append(entry)
                replacement_updates.append(
                    MemoryUpdate(
                        file="stories_bank.md",
                        section="",
                        action="append",
                        content=self._build_story_block(story_id, story),
                        reason="Added detailed story bank entry from chat",
                    )
                )
                existing_titles.add(title.lower())

        for story in core_stories:
            title = story["title"].strip()
            if not title or title.lower() in existing_titles:
                continue
            story_id = f"STORY-{next_story_number:03d}"
            next_story_number += 1
            new_entries.append({
                "story_id": story_id,
                "title": title,
                "one_liner": story["one_liner"].strip(),
            })
            existing_titles.add(title.lower())

        if not replacement_updates and not new_entries and not coverage_gaps:
            return []

        combined_entries = existing_entries + new_entries
        for story in structured_stories:
            title = story["title"].strip()
            if not title:
                continue
            for entry in combined_entries:
                if entry["title"].lower() == title.lower():
                    entry["one_liner"] = story["one_liner"].strip() or entry.get("one_liner", "")
                    break
        updates: list[MemoryUpdate] = []

        if combined_entries:
            index_lines = ["| Theme | Stories |", "|---|---|"]
            for entry in combined_entries:
                story_ref = f'{entry["story_id"]} · {entry["one_liner"]}' if entry["one_liner"] else entry["story_id"]
                index_lines.append(f'| {entry["title"]} | {story_ref} |')
            updates.append(
                MemoryUpdate(
                    file="stories_bank.md",
                    section="Quick-reference index",
                    action="replace",
                    content="\n".join(index_lines),
                    reason="Saved story bank index from chat",
                )
            )

        if coverage_gaps:
            updates.append(
                MemoryUpdate(
                    file="stories_bank.md",
                    section="Coverage gaps",
                    action="replace",
                    content="\n".join(f"- {gap}" for gap in coverage_gaps),
                    reason="Saved missing behavioral story coverage from chat",
                )
            )

        if new_entries:
            story_blocks = []
            for entry in new_entries:
                story_blocks.append(
                    self._build_story_block(
                        entry["story_id"],
                        {
                            "title": entry["title"],
                            "themes": [entry["title"]],
                            "one_liner": entry["one_liner"] or "Imported from BQ session",
                            "situation": "Imported from a BQ/story-bank conversation. Flesh this out in Story Builder mode.",
                            "task": "Clarify the challenge, stakes, and your ownership.",
                            "action": "Add the specific actions you personally drove.",
                            "result": "Add the outcome, ideally with a concrete metric.",
                            "raw_notes": "",
                        },
                    )
                )
            replacement_updates.append(
                MemoryUpdate(
                    file="stories_bank.md",
                    section="",
                    action="append",
                    content="\n\n".join(story_blocks),
                    reason="Added structured story entries from BQ chat",
                )
            )

        return updates + replacement_updates

    def _parse_story_inventory(self, text: str) -> list[dict[str, str]]:
        section_match = re.search(
            r"Core stories locked in:\s*(.+?)(?:\n\s*Still missing|\n\s*When you're ready|\Z)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        block = section_match.group(1) if section_match else text

        stories: list[dict[str, str]] = []
        seen: set[str] = set()
        for raw_line in block.splitlines():
            line = self._clean_story_line(raw_line)
            if not line:
                continue
            if ":" in line and not re.search(r"\s[—–-]\s", line):
                continue
            if len(line) > 160:
                continue
            title, one_liner = self._split_story_line(line)
            if not title or title.lower() in seen:
                continue
            if len(title.split()) > 10 and not one_liner:
                continue
            seen.add(title.lower())
            stories.append({"title": title, "one_liner": one_liner})
        return stories

    def _parse_coverage_gaps(self, text: str) -> list[str]:
        match = re.search(
            r"Still missing(?:\s*\(.*?\))?:\s*(.+?)(?:\n\s*When you're ready|\Z)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return []

        gaps: list[str] = []
        for raw_line in match.group(1).splitlines():
            line = self._clean_story_line(raw_line)
            if not line or line.lower() == "none yet.":
                continue
            gaps.append(line)
        return gaps

    def _clean_story_line(self, line: str) -> str:
        cleaned = line.strip()
        cleaned = re.sub(r"^[\-\*\u2022]+\s*", "", cleaned)
        cleaned = re.sub(r"^\d+\.\s*", "", cleaned)
        cleaned = cleaned.strip()
        if not cleaned:
            return ""
        lower = cleaned.lower()
        if lower.startswith(("core stories locked in", "still missing", "you now have", "when you're ready")):
            return ""
        return cleaned

    def _split_story_line(self, line: str) -> tuple[str, str]:
        for separator in (" — ", " – ", " - "):
            if separator in line:
                title, one_liner = line.split(separator, 1)
                return title.strip(" -"), one_liner.strip()
        return line.strip(" -"), ""

    def _parse_structured_story_blocks(self, text: str) -> list[dict[str, str | list[str]]]:
        if "**Situation:**" not in text or "**Action:**" not in text or "**Result:**" not in text:
            return []

        chunks = re.split(r"(?=^## )", text, flags=re.MULTILINE)
        if len(chunks) == 1:
            chunks = [text]

        stories: list[dict[str, str | list[str]]] = []
        for chunk in chunks:
            if "**Situation:**" not in chunk or "**Action:**" not in chunk or "**Result:**" not in chunk:
                continue
            title = self._extract_story_title(chunk)
            if not title:
                continue
            one_liner = self._extract_story_label(chunk, "The one-liner")
            themes_raw = self._extract_story_label(chunk, "Themes")
            raw_notes = self._extract_story_label(chunk, "Raw notes")
            situation = self._extract_story_label(chunk, "Situation")
            task = self._extract_story_label(chunk, "Task")
            action = self._extract_story_label(chunk, "Action")
            result = self._extract_story_label(chunk, "Result")
            if not action or not result:
                continue
            themes = [t.strip() for t in themes_raw.split(",") if t.strip()] if themes_raw else [title]
            stories.append({
                "title": title,
                "themes": themes,
                "one_liner": one_liner or self._derive_story_one_liner(title, situation, result),
                "situation": situation,
                "task": task,
                "action": action,
                "result": result,
                "raw_notes": raw_notes,
            })
        return stories

    def _extract_story_title(self, chunk: str) -> str:
        heading_match = re.search(r"^##\s+(?:STORY-\d+\s+·\s+)?(.+)$", chunk, re.MULTILINE)
        if heading_match:
            return heading_match.group(1).strip()
        title_match = re.search(r"\*\*Title:\*\*\s*(.+)", chunk)
        if title_match:
            return title_match.group(1).strip()
        one_liner = self._extract_story_label(chunk, "The one-liner")
        if one_liner:
            return one_liner.split("—")[0].split(" - ")[0].strip()[:80]
        return ""

    def _extract_story_label(self, chunk: str, label: str) -> str:
        match = re.search(
            rf"\*\*{re.escape(label)}:\*\*\s*(.+?)(?=\n\*\*[^*]+:\*\*|\n## |\n---|\Z)",
            chunk,
            re.DOTALL,
        )
        return match.group(1).strip() if match else ""

    def _derive_story_one_liner(self, title: str, situation: str, result: str) -> str:
        for candidate in [result, situation]:
            sentence = re.split(r"(?<=[.!?])\s+", candidate.strip())[0].strip()
            if sentence:
                return sentence[:180]
        return title

    def _build_story_block(self, story_id: str, story: dict[str, str | list[str]]) -> str:
        return "\n".join([
            f'## {story_id} · {story["title"]}',
            "",
            self._build_story_block_body(story),
            "",
            "---",
        ])

    def _build_story_block_body(self, story: dict[str, str | list[str]]) -> str:
        themes = story.get("themes", [])
        theme_text = ", ".join(themes) if isinstance(themes, list) else str(themes)
        lines = [
            f"**Themes:** {theme_text}",
            f'**The one-liner:** {story.get("one_liner", "")}'.rstrip(),
            f'**Situation:** {story.get("situation", "")}'.rstrip(),
        ]
        if story.get("task", ""):
            lines.append(f'**Task:** {story.get("task", "")}'.rstrip())
        lines.extend([
            f'**Action:** {story.get("action", "")}'.rstrip(),
            f'**Result:** {story.get("result", "")}'.rstrip(),
        ])
        if story.get("raw_notes", ""):
            lines.append(f'**Raw notes:** {story.get("raw_notes", "")}'.rstrip())
        return "\n".join(lines)

    def _parse_existing_story_entries(self, stories_md: str) -> list[dict[str, str]]:
        entries: list[dict[str, str]] = []
        for match in re.finditer(
            r"^## (STORY-\d+)\s+·\s+(.+?)\n(.*?)(?=^## STORY-|\Z)",
            stories_md,
            re.MULTILINE | re.DOTALL,
        ):
            body = match.group(3)
            one_liner_match = re.search(r"\*\*The one-liner:\*\*\s*(.+)", body)
            entries.append({
                "story_id": match.group(1).strip(),
                "title": match.group(2).strip(),
                "one_liner": one_liner_match.group(1).strip() if one_liner_match else "",
            })
        return entries

    def _next_story_number(self, entries: list[dict[str, str]]) -> int:
        existing_numbers = []
        for entry in entries:
            match = re.search(r"STORY-(\d+)", entry["story_id"])
            if match:
                existing_numbers.append(int(match.group(1)))
        return max(existing_numbers, default=0) + 1

    def _merge_updates(self, updates: list[MemoryUpdate]) -> list[MemoryUpdate]:
        merged: list[MemoryUpdate] = []
        seen: set[tuple[str, str, str, str]] = set()
        for update in updates:
            key = (update.file, update.section, update.action, update.content.strip())
            if key in seen:
                continue
            seen.add(key)
            merged.append(update)
        return merged


class CoreAgent(BaseAgent):
    intent = "GENERAL"; prompt_name = "core_agent"

class IntakeAgent(BaseAgent):
    intent = "INTAKE"; prompt_name = "intake_agent"

class StoryBuilderAgent(BaseAgent):
    intent = "STORY"; prompt_name = "story_crafter"

class ResumeEditorAgent(BaseAgent):
    intent = "RESUME"; prompt_name = "resume_editor"

class BQCoachAgent(BaseAgent):
    intent = "BQ"; prompt_name = "bq_coach"

    async def post_process(self, response, message, ctx, history=None):
        return await super().post_process(response, message, ctx, history=history)

class DebriefAgent(BaseAgent):
    intent = "DEBRIEF"; prompt_name = "debrief_agent"

class StrategyReviewAgent(BaseAgent):
    intent = "STRATEGY"; prompt_name = "strategy_agent"

class PlannerAgent(BaseAgent):
    intent = "PLANNER"; prompt_name = "planner_agent"

class JobScoutAgent(BaseAgent):
    intent = "SCOUT"; prompt_name = "job_scout"


AGENT_MAP: dict[str, type[BaseAgent]] = {
    "GENERAL": CoreAgent, "INTAKE": IntakeAgent, "STORY": StoryBuilderAgent,
    "RESUME": ResumeEditorAgent, "BQ": BQCoachAgent, "DEBRIEF": DebriefAgent,
    "STRATEGY": StrategyReviewAgent, "PLANNER": PlannerAgent, "SCOUT": JobScoutAgent,
}

INTENT_SYSTEM = """You are a routing classifier for Futuro, a job search assistant.
Classify the user message into exactly one intent:
- INTAKE: user shares a URL, file, article, or course to process
- STORY: user wants to build, refine, or document a STAR story
- RESUME: user wants to edit, tailor, or review their resume
- BQ: user wants behavioral interview question practice or coaching
- DEBRIEF: user has just finished an interview and wants to debrief
- STRATEGY: user wants to review or update their overall job search strategy
- PLANNER: user wants to plan their week, manage tasks, organize a checklist, or track what to learn next
- SCOUT: user asks about job listings, the job scanner, new openings, or wants to find jobs
- GENERAL: greetings, check-ins, questions, emotional support, anything else
Reply with exactly one word from the list above. Nothing else."""


async def classify_intent(message: str, history: list[dict]) -> str:
    provider = get_provider(TaskType.CLASSIFY)
    msgs = [{"role": m["role"], "content": m["content"]} for m in history[-4:]]
    msgs.append({"role": "user", "content": message})
    text = await provider.complete(system=INTENT_SYSTEM, messages=msgs, max_tokens=10)
    token = text.strip().upper().split()[0] if text.strip() else "GENERAL"
    intent = re.sub(r"[^A-Z_]", "", token)
    return intent if intent in AGENT_MAP else "GENERAL"


def get_agent(intent: str, memory: MemoryManager) -> BaseAgent:
    return AGENT_MAP.get(intent, CoreAgent)(memory)
