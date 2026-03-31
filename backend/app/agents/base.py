"""
Agent base — provider-agnostic
-------------------------------
All agents talk to LLMProvider, never to SDK clients directly.
"""
from __future__ import annotations

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
        return []


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
        if "follow-up" in response.lower() and "STORY-" in response:
            return [MemoryUpdate(file="stories_bank.md", section="", action="append",
                content=f"\n<!-- BQ practice note: {message[:80]}... -->\n",
                reason="BQ session follow-up notes")]
        return []

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
    intent = text.strip().upper().split()[0] if text.strip() else "GENERAL"
    return intent if intent in AGENT_MAP else "GENERAL"


def get_agent(intent: str, memory: MemoryManager) -> BaseAgent:
    return AGENT_MAP.get(intent, CoreAgent)(memory)
