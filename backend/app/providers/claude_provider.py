"""
Claude provider (Anthropic API)
--------------------------------
Thin wrapper around the Anthropic async SDK.
Handles streaming, non-streaming, and a stub embed
(Claude doesn't expose embeddings — falls back to chromadb default).
"""
from __future__ import annotations

from typing import AsyncIterator

import anthropic

from app.providers.base import LLMProvider


class ClaudeProvider(LLMProvider):
    name = "claude"

    def __init__(self, api_key: str, model: str, max_tokens: int = 8192):
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model   = model
        self.max_tokens = max_tokens

    # ── Streaming ─────────────────────────────────────────────────────────────

    async def stream(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        async with self._client.messages.stream(
            model=self.model,
            max_tokens=max_tokens or self.max_tokens,
            system=system,
            messages=messages,
        ) as s:
            async for token in s.text_stream:
                yield token

    # ── Non-streaming ─────────────────────────────────────────────────────────

    async def complete(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 512,
    ) -> str:
        resp = await self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        return resp.content[0].text

    # ── Embeddings ────────────────────────────────────────────────────────────

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """
        Anthropic doesn't offer an embedding API.
        Return empty lists — the caller falls back to ChromaDB's default EF.
        """
        return [[] for _ in texts]

    # ── Health ────────────────────────────────────────────────────────────────

    async def health(self) -> dict:
        try:
            await self._client.messages.create(
                model=self.model,
                max_tokens=5,
                messages=[{"role": "user", "content": "ping"}],
            )
            return {"ok": True, "model": self.model, "detail": "Anthropic API reachable"}
        except Exception as exc:
            return {"ok": False, "model": self.model, "detail": str(exc)}
