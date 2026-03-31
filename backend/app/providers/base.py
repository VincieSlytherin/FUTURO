"""
Provider abstraction layer
--------------------------
Defines the interface that both Claude and Ollama backends implement.
All agents and tools talk to providers, never to SDK clients directly.

Task types let you route different workloads to different providers:
  CHAT     - main Futuro conversation (warmth + memory)
  CLASSIFY - intent classification (fast, cheap, low stakes)
  SCORE    - job scoring (structured JSON output, accuracy critical)
  EMBED    - vector embeddings for ChromaDB semantic search
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import AsyncIterator


class TaskType(str, Enum):
    CHAT     = "chat"
    CLASSIFY = "classify"
    SCORE    = "score"
    EMBED    = "embed"


class LLMProvider(ABC):
    """Streaming text + embedding provider interface."""

    name: str = "base"

    @abstractmethod
    async def stream(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Yield text tokens as they arrive."""
        ...

    @abstractmethod
    async def complete(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 512,
    ) -> str:
        """Return full response text (non-streaming)."""
        ...

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors for a list of texts."""
        ...

    @abstractmethod
    async def health(self) -> dict:
        """Return {'ok': bool, 'model': str, 'detail': str}."""
        ...
