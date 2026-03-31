"""
Provider router
---------------
Central registry that maps task types to providers.
Instantiated once at startup from settings; all agents import `get_provider()`.

Config-driven routing examples:

  # Full local (all tasks use Ollama)
  LLM_PROVIDER=ollama

  # Full cloud (all tasks use Claude)
  LLM_PROVIDER=claude

  # Hybrid (default): chat + classify local, score + embed flexible
  LLM_PROVIDER=auto
  CHAT_PROVIDER=ollama
  SCORE_PROVIDER=claude     # more accurate structured JSON
  EMBED_PROVIDER=ollama     # local embeddings, no API cost

  # Auto: probe Ollama at startup; fall back to Claude if unavailable
  LLM_PROVIDER=auto
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.providers.base import LLMProvider, TaskType

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)

# Module-level registry: populated by init_providers() at startup
_registry: dict[TaskType, LLMProvider] = {}


async def init_providers(settings: "Settings") -> None:
    """Build providers from settings. Call once at FastAPI lifespan startup."""
    from app.providers.claude_provider import ClaudeProvider
    from app.providers.ollama_provider import OllamaProvider

    # Build candidate providers
    claude: ClaudeProvider | None = None
    ollama: OllamaProvider | None = None

    if settings.anthropic_api_key and settings.anthropic_api_key != "sk-ant-not-set":
        claude = ClaudeProvider(
            api_key=settings.anthropic_api_key,
            model=settings.claude_model,
            max_tokens=settings.max_tokens,
        )

    if settings.ollama_enabled:
        ollama = OllamaProvider(
            base_url=settings.ollama_base_url,
            chat_model=settings.ollama_chat_model,
            embed_model=settings.ollama_embed_model,
            timeout=settings.ollama_timeout,
            keep_alive=settings.ollama_keep_alive,
        )

    # Probe availability
    ollama_ok = False
    if ollama:
        health = await ollama.health()
        ollama_ok = health["ok"]
        if ollama_ok:
            logger.info(f"[providers] Ollama ready — chat={settings.ollama_chat_model} embed={settings.ollama_embed_model}")
        else:
            logger.warning(f"[providers] Ollama unavailable: {health['detail']}")

    claude_ok = claude is not None

    def _resolve(explicit: str | None, task: TaskType) -> LLMProvider:
        """Pick a provider for a task, respecting explicit overrides."""
        want = explicit or settings.llm_provider

        if want == "ollama":
            if ollama_ok:
                return ollama  # type: ignore
            if claude_ok:
                logger.warning(f"[providers] ollama requested for {task} but unavailable — falling back to claude")
                return claude  # type: ignore
            raise RuntimeError(f"No provider available for task {task}")

        if want == "claude":
            if claude_ok:
                return claude  # type: ignore
            if ollama_ok:
                logger.warning(f"[providers] claude requested for {task} but not configured — falling back to ollama")
                return ollama  # type: ignore
            raise RuntimeError(f"No provider available for task {task}")

        # "auto" — prefer ollama if up, else claude
        if ollama_ok:
            return ollama  # type: ignore
        if claude_ok:
            return claude  # type: ignore
        raise RuntimeError(f"No provider available for task {task} (both claude and ollama unavailable)")

    _registry[TaskType.CHAT]     = _resolve(settings.chat_provider,     TaskType.CHAT)
    _registry[TaskType.CLASSIFY] = _resolve(settings.classify_provider,  TaskType.CLASSIFY)
    _registry[TaskType.SCORE]    = _resolve(settings.score_provider,     TaskType.SCORE)
    _registry[TaskType.EMBED]    = _resolve(settings.embed_provider,     TaskType.EMBED)

    for task, provider in _registry.items():
        logger.info(f"[providers] {task.value:10} → {provider.name} ({_model_label(provider)})")


def get_provider(task: TaskType = TaskType.CHAT) -> LLMProvider:
    """Return the provider assigned to a task type."""
    if not _registry:
        raise RuntimeError("Providers not initialised — call init_providers() first")
    return _registry[task]


def provider_status() -> dict:
    """Return a summary dict for the /api/providers/status endpoint."""
    return {
        task.value: {
            "provider": p.name,
            "model": _model_label(p),
        }
        for task, p in _registry.items()
    }


async def provider_health() -> dict:
    """Run health checks on all unique providers."""
    seen: set[str] = set()
    results = {}
    for task, provider in _registry.items():
        if provider.name not in seen:
            results[provider.name] = await provider.health()
            seen.add(provider.name)
    return results


def _model_label(provider: LLMProvider) -> str:
    from app.providers.claude_provider import ClaudeProvider
    from app.providers.ollama_provider import OllamaProvider
    if isinstance(provider, ClaudeProvider):
        return provider.model
    if isinstance(provider, OllamaProvider):
        return provider.chat_model
    return "unknown"
