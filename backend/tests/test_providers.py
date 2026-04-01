"""
Tests for the provider abstraction layer.
Claude provider tests use mocks; Ollama tests exercise real logic but mock HTTP.
"""
import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import os

os.environ.update({
    "ANTHROPIC_API_KEY": "sk-ant-test",
    "JWT_SECRET": "test-secret-32-chars-long-enough-x",
    "USER_PASSWORD_HASH": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TiGM4e1sAnBZaOEf5RQD8vFv6Bmy",
    "DATA_DIR": "/tmp/futuro-provider-test/data",
    "MEMORY_DIR": "/tmp/futuro-provider-test/data/memory",
    "CHROMA_DIR": "/tmp/futuro-provider-test/data/chroma",
    "DB_PATH": "/tmp/futuro-provider-test/data/futuro.db",
    "GIT_AUTO_COMMIT": "false",
    "SCOUT_ENABLED": "false",
    "LLM_PROVIDER": "claude",   # tests default to Claude (mocked)
    "OLLAMA_ENABLED": "false",
    "DEBUG": "true",
    "ALLOWED_ORIGINS": '["http://localhost:3000"]',
})


# ── ClaudeProvider ────────────────────────────────────────────────────────────

class TestClaudeProvider:

    @pytest.mark.asyncio
    async def test_stream_yields_tokens(self):
        from app.providers.claude_provider import ClaudeProvider

        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=None)

        tokens = ["Hello", " world", "!"]
        async def _gen():
            for t in tokens:
                yield t
        mock_stream.text_stream = _gen()

        provider = ClaudeProvider(api_key="sk-ant-test", model="claude-sonnet-4-5")
        with patch.object(provider._client.messages, "stream", return_value=mock_stream):
            result = []
            async for tok in provider.stream("sys", [{"role": "user", "content": "hi"}]):
                result.append(tok)
        assert result == tokens

    @pytest.mark.asyncio
    async def test_complete_returns_text(self):
        from app.providers.claude_provider import ClaudeProvider

        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text="GENERAL")]

        provider = ClaudeProvider(api_key="sk-ant-test", model="claude-sonnet-4-5")
        with patch.object(provider._client.messages, "create", AsyncMock(return_value=mock_resp)):
            result = await provider.complete("sys", [{"role": "user", "content": "hi"}], max_tokens=10)
        assert result == "GENERAL"

    @pytest.mark.asyncio
    async def test_embed_returns_empty_lists(self):
        from app.providers.claude_provider import ClaudeProvider
        provider = ClaudeProvider(api_key="sk-ant-test", model="claude-sonnet-4-5")
        result = await provider.embed(["hello", "world"])
        assert result == [[], []]

    @pytest.mark.asyncio
    async def test_health_returns_ok_on_success(self):
        from app.providers.claude_provider import ClaudeProvider
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text="pong")]
        provider = ClaudeProvider(api_key="sk-ant-test", model="claude-sonnet-4-5")
        with patch.object(provider._client.messages, "create", AsyncMock(return_value=mock_resp)):
            h = await provider.health()
        assert h["ok"] is True

    @pytest.mark.asyncio
    async def test_health_returns_not_ok_on_error(self):
        from app.providers.claude_provider import ClaudeProvider
        provider = ClaudeProvider(api_key="sk-ant-test", model="claude-sonnet-4-5")
        with patch.object(provider._client.messages, "create", AsyncMock(side_effect=Exception("Auth error"))):
            h = await provider.health()
        assert h["ok"] is False
        assert "Auth error" in h["detail"]


# ── OllamaProvider ────────────────────────────────────────────────────────────

class TestOllamaProvider:

    def _make_provider(self):
        from app.providers.ollama_provider import OllamaProvider
        return OllamaProvider(
            base_url="http://localhost:11434",
            chat_model="qwen2.5:7b",
            embed_model="nomic-embed-text",
        )

    @pytest.mark.asyncio
    async def test_stream_parses_ndjson(self):
        from app.providers.ollama_provider import OllamaProvider
        import httpx

        ndjson_lines = [
            b'{"message":{"role":"assistant","content":"Hello"},"done":false}\n',
            b'{"message":{"role":"assistant","content":" world"},"done":false}\n',
            b'{"message":{"role":"assistant","content":""},"done":true}\n',
        ]

        async def _aiter_lines():
            for line in ndjson_lines:
                yield line.decode().strip()

        mock_resp = AsyncMock()
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)
        mock_resp.raise_for_status = MagicMock()
        mock_resp.aiter_lines = _aiter_lines

        provider = self._make_provider()
        with patch.object(provider._client, "stream", return_value=mock_resp):
            tokens = []
            async for tok in provider.stream("sys", [{"role": "user", "content": "hi"}]):
                tokens.append(tok)

        assert tokens == ["Hello", " world"]

    @pytest.mark.asyncio
    async def test_complete_non_streaming(self):
        from app.providers.ollama_provider import OllamaProvider

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "message": {"role": "assistant", "content": "BQ"},
            "done": True,
        }

        provider = self._make_provider()
        with patch.object(provider._client, "post", AsyncMock(return_value=mock_resp)):
            result = await provider.complete("sys", [{"role": "user", "content": "classify"}], max_tokens=10)
        assert result == "BQ"

    @pytest.mark.asyncio
    async def test_embed_batch_endpoint(self):
        from app.providers.ollama_provider import OllamaProvider

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "embeddings": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        }

        provider = self._make_provider()
        with patch.object(provider._client, "post", AsyncMock(return_value=mock_resp)):
            result = await provider.embed(["hello", "world"])

        assert len(result) == 2
        assert result[0] == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_embed_falls_back_to_legacy_on_404(self):
        """When /api/embed returns 404, fall back to /api/embeddings one-by-one."""
        import httpx
        from app.providers.ollama_provider import OllamaProvider

        call_count = 0

        async def mock_post(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if "api/embed" in url and call_count == 1:
                mock = MagicMock()
                mock.raise_for_status.side_effect = httpx.HTTPStatusError(
                    "404", request=MagicMock(), response=MagicMock(status_code=404)
                )
                return mock
            # Legacy fallback
            m = MagicMock()
            m.raise_for_status = MagicMock()
            m.json.return_value = {"embedding": [0.7, 0.8, 0.9]}
            return m

        provider = self._make_provider()
        with patch.object(provider._client, "post", side_effect=mock_post):
            result = await provider.embed(["single text"])

        assert result == [[0.7, 0.8, 0.9]]

    @pytest.mark.asyncio
    async def test_health_ok_when_model_available(self):
        from app.providers.ollama_provider import OllamaProvider

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "models": [
                {"name": "qwen2.5:7b"},
                {"name": "nomic-embed-text"},
            ]
        }

        provider = self._make_provider()
        with patch.object(provider._client, "get", AsyncMock(return_value=mock_resp)):
            h = await provider.health()

        assert h["ok"] is True

    @pytest.mark.asyncio
    async def test_health_fails_when_model_missing(self):
        from app.providers.ollama_provider import OllamaProvider

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "models": [{"name": "llama3.2:3b"}]  # chat model not present
        }

        provider = self._make_provider()
        with patch.object(provider._client, "get", AsyncMock(return_value=mock_resp)):
            h = await provider.health()

        assert h["ok"] is False
        assert "qwen2.5:7b" in h["detail"]
        assert "ollama pull" in h["detail"]

    @pytest.mark.asyncio
    async def test_health_fails_on_connect_error(self):
        import httpx
        from app.providers.ollama_provider import OllamaProvider

        provider = self._make_provider()
        with patch.object(provider._client, "get", AsyncMock(side_effect=httpx.ConnectError("refused"))):
            h = await provider.health()

        assert h["ok"] is False
        assert "ollama serve" in h["detail"]

    def test_build_messages_prepends_system(self):
        from app.providers.ollama_provider import OllamaProvider
        result = OllamaProvider._build_messages(
            "You are Futuro.",
            [{"role": "user", "content": "Hello"}],
        )
        assert result[0] == {"role": "system", "content": "You are Futuro."}
        assert result[1] == {"role": "user", "content": "Hello"}

    def test_build_messages_no_system(self):
        from app.providers.ollama_provider import OllamaProvider
        result = OllamaProvider._build_messages("", [{"role": "user", "content": "Hi"}])
        assert result[0]["role"] == "user"


# ── Provider router ───────────────────────────────────────────────────────────

class TestProviderRouter:

    @pytest.mark.asyncio
    async def test_init_with_claude_only(self):
        from app.providers import router as r
        r._registry.clear()

        from app.providers.claude_provider import ClaudeProvider
        mock_claude = MagicMock(spec=ClaudeProvider)
        mock_claude.name = "claude"
        mock_claude.health = AsyncMock(return_value={"ok": True, "model": "claude-sonnet-4-5", "detail": "ok"})

        with patch("app.providers.router.ClaudeProvider", return_value=mock_claude), \
             patch("app.providers.router.OllamaProvider") as mock_ollama_cls:
            mock_ollama_cls.return_value.health = AsyncMock(return_value={"ok": False, "detail": "no ollama"})
            mock_ollama_cls.return_value.name = "ollama"

            from app.config import settings
            # Force llm_provider = claude
            settings_copy = MagicMock()
            settings_copy.anthropic_api_key = "sk-ant-test"
            settings_copy.claude_model = "claude-sonnet-4-5"
            settings_copy.max_tokens = 8192
            settings_copy.ollama_enabled = True
            settings_copy.ollama_base_url = "http://localhost:11434"
            settings_copy.ollama_chat_model = "qwen2.5:7b"
            settings_copy.ollama_embed_model = "nomic-embed-text"
            settings_copy.ollama_timeout = 30.0
            settings_copy.ollama_keep_alive = "5m"
            settings_copy.llm_provider = "claude"
            settings_copy.chat_provider = None
            settings_copy.classify_provider = None
            settings_copy.score_provider = None
            settings_copy.embed_provider = None

            await r.init_providers(settings_copy)

        from app.providers.base import TaskType
        assert r.get_provider(TaskType.CHAT).name == "claude"
        r._registry.clear()

    def test_get_provider_raises_when_not_init(self):
        from app.providers import router as r
        r._registry.clear()
        from app.providers.base import TaskType
        with pytest.raises(RuntimeError, match="not initialised"):
            r.get_provider(TaskType.CHAT)
        # Restore for other tests
        r._registry.clear()

    def test_provider_status_shape(self):
        from app.providers import router as r
        from app.providers.base import TaskType
        from app.providers.claude_provider import ClaudeProvider
        mock = MagicMock(spec=ClaudeProvider)
        mock.name = "claude"
        mock.model = "claude-sonnet-4-5"
        r._registry = {t: mock for t in TaskType}
        status = r.provider_status()
        for task in ["chat", "classify", "score", "embed"]:
            assert task in status
            assert "provider" in status[task]
        r._registry.clear()


# ── Vector store with Ollama EF ───────────────────────────────────────────────

class TestVectorStoreWithOllama:

    def test_ollama_ef_callable(self):
        """OllamaEmbeddingFunction should be callable with a list of strings."""
        from app.memory.vector_store import OllamaEmbeddingFunction
        import httpx

        ef = OllamaEmbeddingFunction("http://localhost:11434", "nomic-embed-text")

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}

        with patch.object(ef._client, "post", return_value=mock_resp):
            result = ef(["text one", "text two"])

        assert len(result) == 2
        assert result[0] == [0.1, 0.2]

    def test_build_ef_uses_ollama_when_configured(self):
        """_build_ef should return OllamaEmbeddingFunction when ollama embed is set."""
        from app.memory.vector_store import _build_ef, OllamaEmbeddingFunction

        mock_settings = MagicMock()
        mock_settings.ollama_enabled = True
        mock_settings.embed_provider = "ollama"
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.ollama_embed_model = "nomic-embed-text"

        ef = _build_ef(mock_settings)
        assert isinstance(ef, OllamaEmbeddingFunction)

    def test_build_ef_fallback_to_default(self):
        """_build_ef should return default EF when ollama is disabled."""
        from app.memory.vector_store import _build_ef, OllamaEmbeddingFunction

        mock_settings = MagicMock()
        mock_settings.ollama_enabled = False

        ef = _build_ef(mock_settings)
        assert not isinstance(ef, OllamaEmbeddingFunction)


# ── Intent classification with Ollama output quirks ──────────────────────────

class TestClassifyIntentOllamaQuirks:
    """Ollama sometimes returns the intent with punctuation or extra whitespace."""

    @pytest.mark.asyncio
    async def test_classify_strips_punctuation(self):
        """classify_intent should strip trailing periods, newlines, etc."""
        from app.providers import router as r
        from app.providers.base import TaskType
        from app.providers.claude_provider import ClaudeProvider

        mock_provider = MagicMock(spec=ClaudeProvider)
        mock_provider.name = "claude"
        # Simulate Ollama returning "BQ.\n" instead of "BQ"
        mock_provider.complete = AsyncMock(return_value="BQ.\n")
        r._registry = {t: mock_provider for t in TaskType}

        from app.agents.base import classify_intent
        intent = await classify_intent("Can we practice behavioral questions?", [])
        assert intent == "BQ"
        r._registry.clear()

    @pytest.mark.asyncio
    async def test_classify_unknown_returns_general(self):
        from app.providers import router as r
        from app.providers.base import TaskType
        from app.providers.claude_provider import ClaudeProvider

        mock_provider = MagicMock(spec=ClaudeProvider)
        mock_provider.name = "claude"
        mock_provider.complete = AsyncMock(return_value="UNKNOWN_INTENT")
        r._registry = {t: mock_provider for t in TaskType}

        from app.agents.base import classify_intent
        intent = await classify_intent("something random", [])
        assert intent == "GENERAL"
        r._registry.clear()
