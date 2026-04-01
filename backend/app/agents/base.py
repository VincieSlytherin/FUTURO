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

MEMORY_EXTRACTION_SYSTEM = """You extract durable user memory from a single Futuro chat turn.

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
- When the user pastes resume content, prefer storing it in "resume_versions.md" under "Bullets".
- When the user shares personal background, role target, skills, or signature projects, store it in "L0_identity.md".
- When the user shares ongoing search status or priorities, store it in "L1_campaign.md".
- When the user shares reusable strategy or market learnings, store it in "L2_knowledge.md".
- Avoid duplicating facts already present in memory.
- Use only these files and sections:
  - L0_identity.md: Who I am, Career narrative, Target role, Technical skills, Signature projects
  - L1_campaign.md: Status snapshot, Weekly focus, Mindset check, Strategy notes
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

    def _build_system(self, ctx: AgentContext) -> str:
        parts = [BASE_PERSONA, "\n\n---\n\n", self._agent_prompt]
        if ctx.identity:
            parts.append(f"\n\n## Your memory — who this person is\n\n{ctx.identity}")
        if ctx.campaign:
            parts.append(f"\n\n## Their current search state\n\n{ctx.campaign}")
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
        self, response: str, message: str, ctx: AgentContext
    ) -> list[MemoryUpdate]:
        if self._looks_like_resume_payload(message):
            resume_updates = self._extract_resume_memory_updates(message)
            if resume_updates:
                return resume_updates
        return await self._extract_memory_updates(response, message, ctx)

    async def _extract_memory_updates(
        self,
        response: str,
        message: str,
        ctx: AgentContext,
    ) -> list[MemoryUpdate]:
        if not self._should_extract_memory(message):
            return []

        try:
            provider = get_provider(TaskType.CHAT)
        except RuntimeError:
            return self._fallback_memory_updates(message)

        existing_memory = "\n\n".join(filter(None, [
            f"[L0_identity.md]\n{ctx.identity[:1600]}",
            f"[L1_campaign.md]\n{ctx.campaign[:1200]}",
            f"[resume_versions.md]\n{ctx.resume[:1600]}",
            f"[stories_bank.md]\n{ctx.stories[:1200]}",
            f"[interview_log.md]\n{ctx.interview_log[:1200]}",
            f"[L2_knowledge.md]\n{ctx.knowledge_section[:1200]}",
        ]))
        user_turn = (
            f"Intent: {self.intent}\n\n"
            f"User message:\n{message.strip()}\n\n"
            f"Assistant response:\n{response.strip()}\n\n"
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
        if update.section and update.section not in allowed_sections:
            return False
        if not update.content.strip():
            return False
        if update.action == "replace" and not update.section:
            return False
        return True

    def _should_extract_memory(self, message: str) -> bool:
        cleaned = message.strip()
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

    async def post_process(self, response, message, ctx):
        updates = await super().post_process(response, message, ctx)
        if "follow-up" in response.lower() and "STORY-" in response:
            updates.append(
                MemoryUpdate(
                    file="stories_bank.md",
                    section="Quick-reference index",
                    action="append",
                    content=f"- BQ follow-up note: {message[:80].strip()}...",
                    reason="BQ session follow-up notes",
                )
            )
        return updates

class DebriefAgent(BaseAgent):
    intent = "DEBRIEF"; prompt_name = "debrief_agent"

class StrategyReviewAgent(BaseAgent):
    intent = "STRATEGY"; prompt_name = "strategy_agent"

class JobScoutAgent(BaseAgent):
    intent = "SCOUT"; prompt_name = "job_scout"


AGENT_MAP: dict[str, type[BaseAgent]] = {
    "GENERAL": CoreAgent, "INTAKE": IntakeAgent, "STORY": StoryBuilderAgent,
    "RESUME": ResumeEditorAgent, "BQ": BQCoachAgent, "DEBRIEF": DebriefAgent,
    "STRATEGY": StrategyReviewAgent, "SCOUT": JobScoutAgent,
}

INTENT_SYSTEM = """You are a routing classifier for Futuro, a job search assistant.
Classify the user message into exactly one intent:
- INTAKE: user shares a URL, file, article, or course to process
- STORY: user wants to build, refine, or document a STAR story
- RESUME: user wants to edit, tailor, or review their resume
- BQ: user wants behavioral interview question practice or coaching
- DEBRIEF: user has just finished an interview and wants to debrief
- STRATEGY: user wants to review or update their overall job search strategy
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
