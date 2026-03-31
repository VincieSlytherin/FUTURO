"""
Providers API
/api/providers/status   — which provider is active per task
/api/providers/health   — live health check on each provider
/api/providers/models   — list available Ollama models
/api/providers/pull     — pull an Ollama model (SSE progress)
"""
from __future__ import annotations

import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.deps import AuthDep
from app.providers.router import provider_status, provider_health
from app.config import settings

router = APIRouter(prefix="/api/providers", tags=["providers"])


@router.get("/status")
async def get_status(_: AuthDep):
    """Return routing table: which provider handles which task."""
    return {
        "routing": provider_status(),
        "config": {
            "llm_provider":     settings.llm_provider,
            "chat_provider":    settings.chat_provider,
            "classify_provider": settings.classify_provider,
            "score_provider":   settings.score_provider,
            "embed_provider":   settings.embed_provider,
        },
        "ollama": {
            "enabled":     settings.ollama_enabled,
            "base_url":    settings.ollama_base_url,
            "chat_model":  settings.ollama_chat_model,
            "embed_model": settings.ollama_embed_model,
        } if settings.ollama_enabled else None,
    }


@router.get("/health")
async def get_health(_: AuthDep):
    """Live health probe on all configured providers."""
    return await provider_health()


@router.get("/models")
async def list_models(_: AuthDep):
    """List locally available Ollama models with size info."""
    if not settings.ollama_enabled:
        return {"models": [], "error": "Ollama not enabled"}
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


@router.post("/pull")
async def pull_model(body: PullRequest, _: AuthDep):
    """
    Pull an Ollama model. Streams SSE progress events.
    Example: POST /api/providers/pull  body: {"model": "qwen2.5:14b"}
    """
    if not settings.ollama_enabled:
        raise HTTPException(400, "Ollama not enabled")

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
