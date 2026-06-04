"""
Tests for the #2 memory-governance and #4 scout-recommendation enhancements.
"""
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import bcrypt
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")
os.environ.setdefault("JWT_SECRET", "test-secret-32-chars-long-enough-x")
os.environ.setdefault("USER_PASSWORD_HASH", bcrypt.hashpw(b"testpass", bcrypt.gensalt()).decode())
os.environ.setdefault("DATA_DIR", "/tmp/futuro-test/data")
os.environ.setdefault("MEMORY_DIR", "/tmp/futuro-test/data/memory")
os.environ.setdefault("CHROMA_DIR", "/tmp/futuro-test/data/chroma")
os.environ.setdefault("DB_PATH", "/tmp/futuro-test/data/futuro.db")
os.environ.setdefault("GIT_AUTO_COMMIT", "false")


# ── #2 Memory schema validation ───────────────────────────────────────────────

def test_validate_update_accepts_known_section():
    from app.memory.schema import validate_update
    ok, err = validate_update("resume_versions.md", "Bullets", "append", "- did a thing")
    assert ok and err is None


def test_validate_update_rejects_unknown_file():
    from app.memory.schema import validate_update
    ok, err = validate_update("secrets.md", "Bullets", "append", "x")
    assert not ok and "Unknown memory file" in err


def test_validate_update_rejects_unknown_section():
    from app.memory.schema import validate_update
    ok, err = validate_update("L0_identity.md", "Bank account", "replace", "x")
    assert not ok and "not allowed" in err


def test_validate_update_rejects_bad_action_and_empty_content():
    from app.memory.schema import validate_update
    ok, err = validate_update("planner.md", "Daily tasks", "delete", "x")
    assert not ok and "Invalid action" in err
    ok2, err2 = validate_update("planner.md", "Daily tasks", "append", "   ")
    assert not ok2 and "empty" in err2


def test_validate_update_allows_dynamic_story_blocks():
    from app.memory.schema import validate_update
    ok, _ = validate_update("stories_bank.md", "STORY-007 · A new story", "replace", "**Result:** x")
    assert ok
    ok2, _ = validate_update("stories_bank.md", "", "append", "## STORY-008 · Block")
    assert ok2


def test_validate_update_matches_agent_allowed_update():
    """Schema validator must agree with BaseAgent._is_allowed_update on representative cases."""
    from app.memory.schema import validate_update
    from app.memory.manager import MemoryManager
    from app.agents.base import CoreAgent
    from app.models.schemas import MemoryUpdate

    with TemporaryDirectory() as tmp:
        agent = CoreAgent(MemoryManager(Path(tmp), git_auto_commit=False))
        cases = [
            ("resume_versions.md", "Bullets", "append", "- shipped X"),
            ("L0_identity.md", "Bank account", "replace", "x"),
            ("planner.md", "Daily tasks", "append", "- todo"),
            ("stories_bank.md", "STORY-001 · t", "replace", "**Result:** y"),
        ]
        for file, section, action, content in cases:
            schema_ok, _ = validate_update(file, section, action, content)
            agent_ok = agent._is_allowed_update(
                MemoryUpdate(file=file, section=section, action=action, content=content, reason="t")
            )
            assert schema_ok == agent_ok, (file, section, action)


# ── #2 Preview / diff ─────────────────────────────────────────────────────────

def test_preview_update_returns_diff_without_writing():
    from app.memory.manager import MemoryManager

    with TemporaryDirectory() as tmp:
        memory = MemoryManager(Path(tmp), git_auto_commit=False)
        before_file = memory.read("planner.md")
        preview = memory.preview_update("planner.md", "Daily tasks", "append", "- [ ] Tailor the Stripe resume")

        assert preview["changed"] is True
        assert "- [ ] Tailor the Stripe resume" in preview["after"]
        assert "Tailor the Stripe resume" not in preview["before"]
        assert preview["diff"].startswith("--- a/planner.md")
        assert "+- [ ] Tailor the Stripe resume" in preview["diff"]
        # Nothing was written to disk.
        assert memory.read("planner.md") == before_file


# ── #2 API ────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def auth_client():
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/api/auth/login", json={"password": "testpass"})
        c.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"
        yield c


@pytest.mark.asyncio
async def test_apply_update_rejects_invalid_section(auth_client):
    resp = await auth_client.post(
        "/api/memory/L0_identity.md/apply-update",
        json={"section": "Bank account", "action": "replace", "content": "x", "reason": "test"},
    )
    assert resp.status_code == 422
    assert "not allowed" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_preview_update_endpoint(auth_client):
    resp = await auth_client.post(
        "/api/memory/planner.md/preview-update",
        json={"section": "Daily tasks", "action": "append", "content": "- [ ] Follow up with Anthropic", "reason": "t"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["changed"] is True
    assert "+- [ ] Follow up with Anthropic" in data["diff"]
    # Preview must not persist.
    read_back = await auth_client.get("/api/memory/planner.md")
    assert "Follow up with Anthropic" not in read_back.json()["content"]


# ── #4 Scout recommendations ──────────────────────────────────────────────────

def test_recommend_high_score_says_apply_and_referral():
    from app.scout_recommend import recommend
    rec = recommend({"score": 90, "sponsorship_likely": True, "score_pros": ["RAG", "FastAPI"], "score_cons": []})
    assert rec["priority"] == "HIGH"
    assert rec["priority_rank"] == 3
    assert "Apply now" in rec["recommended_action"]
    assert "referral" in rec["recommended_action"].lower()


def test_recommend_mid_score_without_sponsorship_flags_verification():
    from app.scout_recommend import recommend
    rec = recommend({"score": 72, "sponsorship_likely": None, "score_pros": [], "score_cons": ["No metrics"]})
    assert rec["priority"] == "MEDIUM"
    assert any("sponsorship" in r.lower() for r in rec["reasons"])


def test_recommend_low_score_says_skip():
    from app.scout_recommend import recommend
    rec = recommend({"score": 40, "sponsorship_likely": False, "score_pros": [], "score_cons": []})
    assert rec["priority"] == "LOW"
    assert rec["priority_rank"] == 1


def test_recommend_parses_json_string_pros():
    from app.scout_recommend import recommend
    rec = recommend({"score": 88, "sponsorship_likely": True, "score_pros": '["LLM eval", "Python"]', "score_cons": "[]"})
    assert "LLM eval" in rec["reasons"][0]


@pytest.mark.asyncio
async def test_recommendations_endpoint_ranks_by_priority(auth_client):
    from uuid import uuid4
    from app.database import AsyncSessionLocal, init_db
    from app.models.db import JobListing
    from app.config import settings

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    await init_db()

    created_ids: list[int] = []
    async with AsyncSessionLocal() as db:
        for score, sponsor in [(92, True), (60, None), (78, True)]:
            listing = JobListing(
                url_hash=uuid4().hex,
                job_url=f"https://example.com/rec/{uuid4().hex}",
                title="Applied AI Engineer",
                company="RecCo",
                location="Remote",
                is_remote=True,
                site="linkedin",
                status="NEW",
                score=score,
                score_summary="ok",
                score_pros='["RAG"]',
                score_cons="[]",
                sponsorship_likely=sponsor,
            )
            db.add(listing)
            await db.flush()
            created_ids.append(listing.id)
        await db.commit()

    try:
        resp = await auth_client.get("/api/scout/recommendations?min_score=55")
        assert resp.status_code == 200
        recs = resp.json()["recommendations"]
        assert len(recs) >= 3
        # Every result carries an action, and results are ranked by priority (non-increasing).
        assert recs[0]["recommendation"]["recommended_action"]
        ranks = [r["recommendation"]["priority_rank"] for r in recs]
        assert ranks == sorted(ranks, reverse=True)
    finally:
        async with AsyncSessionLocal() as db:
            for jid in created_ids:
                obj = await db.get(JobListing, jid)
                if obj:
                    await db.delete(obj)
            await db.commit()
