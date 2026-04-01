"""
Providers API
/api/providers/status   — which provider is active per task
/api/providers/health   — live health check on each provider
/api/providers/models   — list available Ollama models
/api/providers/pull     — pull an Ollama model (SSE progress)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from dotenv import set_key, unset_key
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.deps import AuthDep
from app.providers.router import provider_status, provider_health, init_providers
from app.config import PROJECT_ROOT, settings

router = APIRouter(prefix="/api/providers", tags=["providers"])
ENV_PATH = PROJECT_ROOT / ".env"


def _status_payload() -> dict:
    return {
        "routing": provider_status(),
        "config": {
            "llm_provider": settings.llm_provider,
            "chat_provider": settings.chat_provider,
            "classify_provider": settings.classify_provider,
            "score_provider": settings.score_provider,
            "embed_provider": settings.embed_provider,
        },
        "ollama": {
            "enabled": settings.ollama_enabled,
            "base_url": settings.ollama_base_url,
            "chat_model": settings.ollama_chat_model,
            "embed_model": settings.ollama_embed_model,
        },
    }


def _set_env(key: str, value: str) -> None:
    set_key(str(ENV_PATH), key, value, quote_mode="never")


def _set_optional_env(key: str, value: str | None) -> None:
    if value is None:
        if f"{key}=" in ENV_PATH.read_text(encoding="utf-8"):
            unset_key(str(ENV_PATH), key)
    else:
        _set_env(key, value)


def _set_runtime_attr(key: str, value) -> None:
    setattr(settings, key, value)


@router.get("/status")
async def get_status(_: AuthDep):
    """Return routing table: which provider handles which task."""
    return _status_payload()


@router.get("/health")
async def get_health(_: AuthDep):
    """Live health probe on all configured providers."""
    return await provider_health()


@router.get("/models")
async def list_models(_: AuthDep):
    """List locally available Ollama models with size info."""
    try:
        from app.providers.ollama_provider import OllamaProvider
        p = OllamaProvider(
            base_url=settings.ollama_base_url,
            chat_model=settings.ollama_chat_model,
            embed_model=settings.ollama_embed_model,
        )
        models = await p.list_models()
        await p.close()
        return {"models": models}
    except Exception as exc:
        return {"models": [], "error": str(exc)}


class PullRequest(BaseModel):
    model: str


class ProviderConfigRequest(BaseModel):
    llm_provider: Literal["auto", "ollama", "claude"]
    chat_provider: Literal["ollama", "claude"] | None = None
    classify_provider: Literal["ollama", "claude"] | None = None
    score_provider: Literal["ollama", "claude"] | None = None
    embed_provider: Literal["ollama", "claude"] | None = None
    ollama_enabled: bool
    ollama_chat_model: str
    ollama_embed_model: str


@router.put("/config")
async def update_config(body: ProviderConfigRequest, _: AuthDep):
    """
    Persist provider preferences to .env and apply them immediately in-memory.
    This lets the UI switch between Claude / Ollama without a manual file edit.
    """
    if not Path(ENV_PATH).exists():
        raise HTTPException(500, ".env file not found")

    _set_env("LLM_PROVIDER", body.llm_provider)
    _set_optional_env("CHAT_PROVIDER", body.chat_provider)
    _set_optional_env("CLASSIFY_PROVIDER", body.classify_provider)
    _set_optional_env("SCORE_PROVIDER", body.score_provider)
    _set_optional_env("EMBED_PROVIDER", body.embed_provider)
    _set_env("OLLAMA_ENABLED", "true" if body.ollama_enabled else "false")
    _set_env("OLLAMA_CHAT_MODEL", body.ollama_chat_model)
    _set_env("OLLAMA_EMBED_MODEL", body.ollama_embed_model)

    _set_runtime_attr("llm_provider", body.llm_provider)
    _set_runtime_attr("chat_provider", body.chat_provider)
    _set_runtime_attr("classify_provider", body.classify_provider)
    _set_runtime_attr("score_provider", body.score_provider)
    _set_runtime_attr("embed_provider", body.embed_provider)
    _set_runtime_attr("ollama_enabled", body.ollama_enabled)
    _set_runtime_attr("ollama_chat_model", body.ollama_chat_model)
    _set_runtime_attr("ollama_embed_model", body.ollama_embed_model)

    await init_providers(settings)

    return {
        "saved": True,
        **_status_payload(),
        "health": await provider_health(),
    }


@router.post("/pull")
async def pull_model(body: PullRequest, _: AuthDep):
    """
    Pull an Ollama model. Streams SSE progress events.
    Example: POST /api/providers/pull  body: {"model": "qwen2.5:14b"}
    """
    from app.providers.ollama_provider import OllamaProvider

    async def _stream():
        p = OllamaProvider(
            base_url=settings.ollama_base_url,
            chat_model=body.model,
            embed_model=settings.ollama_embed_model,
            timeout=3600.0,  # pulls can take a long time
        )
        try:
            async for chunk in p.pull_model(body.model):
                yield f"data: {json.dumps(chunk)}\n\n"
            yield f"data: {json.dumps({'status': 'success', 'model': body.model})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'status': 'error', 'error': str(exc)})}\n\n"
        finally:
            await p.close()

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
