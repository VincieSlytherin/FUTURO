"""
Ollama provider
---------------
Talks to a local Ollama server (default http://localhost:11434).

Supports:
  - Streaming chat via POST /api/chat  (NDJSON)
  - Non-streaming completion via same endpoint with stream=false
  - Embeddings via POST /api/embed
  - Model pull check via GET /api/tags

Recommended Qwen 2.5 models:
  Chat:
    qwen2.5:7b    — fast, good for general Q&A and coaching (4 GB RAM)
    qwen2.5:14b   — better reasoning, longer context (9 GB RAM)
    qwen2.5:32b   — near-Claude quality for complex tasks (20 GB RAM)
  Embeddings:
    qwen2.5:7b           — works but generic
    nomic-embed-text     — specialized, 137M params, excellent quality (270 MB)
    mxbai-embed-large    — strong retrieval, 335M params (670 MB)

Pull a model before use:
  ollama pull qwen2.5:7b
  ollama pull nomic-embed-text
"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator

import httpx

from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)

# Ollama NDJSON response shape for /api/chat
# {"model":"qwen2.5:7b","created_at":"...","message":{"role":"assistant","content":"Hi"},"done":false}


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(
        self,
        base_url: str,
        chat_model: str,
        embed_model: str,
        timeout: float = 120.0,
        keep_alive: str = "10m",
    ):
        self.base_url    = base_url.rstrip("/")
        self.chat_model  = chat_model
        self.embed_model = embed_model
        self.keep_alive  = keep_alive
        self._client     = httpx.AsyncClient(timeout=timeout)

    # ── Streaming ─────────────────────────────────────────────────────────────

    async def stream(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """
        Stream tokens from /api/chat.
        Ollama uses NDJSON: each line is a JSON object with message.content.
        """
        ollama_messages = self._build_messages(system, messages)
        payload = {
            "model":      self.chat_model,
            "messages":   ollama_messages,
            "stream":     True,
            "keep_alive": self.keep_alive,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.7,
            },
        }

        async with self._client.stream(
            "POST",
            f"{self.base_url}/api/chat",
            json=payload,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    token = data.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if data.get("done"):
                        break
                except json.JSONDecodeError:
                    continue

    # ── Non-streaming ─────────────────────────────────────────────────────────

    async def complete(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 512,
    ) -> str:
        ollama_messages = self._build_messages(system, messages)
        payload = {
            "model":      self.chat_model,
            "messages":   ollama_messages,
            "stream":     False,
            "keep_alive": self.keep_alive,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.1,   # lower temp for structured outputs
            },
        }
        resp = await self._client.post(
            f"{self.base_url}/api/chat",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "")

    # ── Embeddings ────────────────────────────────────────────────────────────

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """
        Call /api/embed (Ollama >= 0.3) which accepts a list of inputs.
        Falls back to /api/embeddings (legacy, single string) if needed.
        """
        if not texts:
            return []
        try:
            return await self._embed_batch(texts)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                # Older Ollama — fall back to sequential single-string calls
                return await self._embed_legacy(texts)
            raise

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """POST /api/embed  (Ollama >= 0.3.0) — batched."""
        resp = await self._client.post(
            f"{self.base_url}/api/embed",
            json={"model": self.embed_model, "input": texts},
        )
        resp.raise_for_status()
        data = resp.json()
        # Response: {"embeddings": [[...], [...]]}
        return data["embeddings"]

    async def _embed_legacy(self, texts: list[str]) -> list[list[float]]:
        """POST /api/embeddings  (Ollama < 0.3.0) — one at a time."""
        results = []
        for text in texts:
            resp = await self._client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.embed_model, "prompt": text},
            )
            resp.raise_for_status()
            results.append(resp.json()["embedding"])
        return results

    # ── Health ────────────────────────────────────────────────────────────────

    async def health(self) -> dict:
        """Check Ollama is running and the configured models are available."""
        try:
            resp = await self._client.get(f"{self.base_url}/api/tags", timeout=5.0)
            resp.raise_for_status()
            models = {m["name"] for m in resp.json().get("models", [])}

            missing = []
            # Normalize: "qwen2.5:7b" matches "qwen2.5:7b" in the list
            if not any(self.chat_model in m for m in models):
                missing.append(f"chat model '{self.chat_model}' not pulled")
            if self.embed_model and not any(self.embed_model in m for m in models):
                missing.append(f"embed model '{self.embed_model}' not pulled")

            if missing:
                return {
                    "ok": False,
                    "model": self.chat_model,
                    "embed_model": self.embed_model,
                    "available_models": sorted(models),
                    "detail": "Missing: " + "; ".join(missing)
                              + f". Run: ollama pull {self.chat_model}",
                }
            return {
                "ok": True,
                "model": self.chat_model,
                "embed_model": self.embed_model,
                "available_models": sorted(models),
                "detail": "Ollama ready",
            }
        except httpx.ConnectError:
            return {
                "ok": False,
                "model": self.chat_model,
                "detail": f"Cannot reach Ollama at {self.base_url}. Is it running? Run: ollama serve",
            }
        except Exception as exc:
            return {"ok": False, "model": self.chat_model, "detail": str(exc)}

    async def list_models(self) -> list[dict]:
        """Return all locally available models with size info."""
        try:
            resp = await self._client.get(f"{self.base_url}/api/tags", timeout=5.0)
            resp.raise_for_status()
            return resp.json().get("models", [])
        except Exception:
            return []

    async def pull_model(self, model: str):
        """
        Stream the pull progress for a model.
        Yields dicts: {"status": "...", "completed": N, "total": N}
        """
        async with self._client.stream(
            "POST",
            f"{self.base_url}/api/pull",
            json={"name": model, "stream": True},
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.strip():
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue

    async def close(self):
        await self._client.aclose()

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _build_messages(system: str, messages: list[dict]) -> list[dict]:
        """
        Ollama expects messages in OpenAI format.
        Prepend the system prompt as a system message if provided.
        """
        result = []
        if system:
            result.append({"role": "system", "content": system})
        for m in messages:
            result.append({"role": m["role"], "content": m["content"]})
        return result
