import bcrypt
import os

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")
os.environ.setdefault("JWT_SECRET", "test-secret-32-chars-long-enough-x")
os.environ.setdefault("USER_PASSWORD_HASH", bcrypt.hashpw(b"testpass", bcrypt.gensalt()).decode())
os.environ.setdefault("DATA_DIR", "/tmp/futuro-test/data")
os.environ.setdefault("MEMORY_DIR", "/tmp/futuro-test/data/memory")
os.environ.setdefault("CHROMA_DIR", "/tmp/futuro-test/data/chroma")
os.environ.setdefault("DB_PATH", "/tmp/futuro-test/data/futuro.db")
os.environ.setdefault("GIT_AUTO_COMMIT", "false")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("ALLOWED_ORIGINS", '["http://localhost:3000"]')

from app.gap_analysis import (  # noqa: E402
    analyze_gap,
    build_resume_corpus,
    match_skills,
    requirement_coverage,
    skill_present,
)


JD_TEXT = """
Applied AI Engineer

Responsibilities
- Build production RAG pipelines and agent workflows
- Ship FastAPI services backed by Python

Requirements
- Strong Python and FastAPI experience
- Experience deploying with Kubernetes and Terraform
- Familiarity with LangChain and vector databases
"""

RESUME = """
### Bullets
- Built a production RAG platform on AWS with Python and FastAPI, reducing review time 90%.
- Architected a LangChain agent pipeline with semantic retrieval over ChromaDB.
"""

IDENTITY = "## Technical skills\n- Python, FastAPI, RAG, LangChain, AWS"


# ── Deterministic core ────────────────────────────────────────────────────────

def test_skill_present_uses_token_boundaries():
    corpus = "built rag pipelines with python and fastapi on aws"
    assert skill_present("Python", corpus)
    assert skill_present("FastAPI", corpus)
    assert not skill_present("SQL", corpus)
    # substring must not false-match
    assert not skill_present("Spark", "worked on sparkling features")


def test_match_skills_splits_matched_and_missing():
    corpus = build_resume_corpus(IDENTITY, RESUME)
    jd_skills = ["Python", "FastAPI", "LangChain", "Kubernetes", "Terraform"]
    matched, missing = match_skills(jd_skills, corpus)
    assert set(matched) == {"Python", "FastAPI", "LangChain"}
    assert set(missing) == {"Kubernetes", "Terraform"}


def test_requirement_coverage_retrieves_closest_story():
    class FakeMatch:
        def __init__(self, story_id, title, distance):
            self.story_id = story_id
            self.title = title
            self.distance = distance
            self.one_liner = ""
            self.themes = []
            self.result_metric = None

    class FakeStore:
        def search(self, query, n_results=1):
            return [FakeMatch("STORY-001", "RAG platform build", 0.42)]

    coverage = requirement_coverage(["Build production RAG pipelines"], FakeStore())
    assert coverage[0]["matched_story_id"] == "STORY-001"
    assert coverage[0]["matched_story"] == "RAG platform build"
    assert coverage[0]["covered"] is True


def test_requirement_coverage_without_store_marks_uncovered():
    coverage = requirement_coverage(["Deploy with Kubernetes"], None)
    assert coverage[0]["matched_story"] is None
    assert coverage[0]["covered"] is False


# ── Orchestrator (LLM mocked away → fallback path) ────────────────────────────

@pytest.mark.asyncio
async def test_analyze_gap_fallback_returns_usable_report():
    result = await analyze_gap(
        jd_text=JD_TEXT,
        identity=IDENTITY,
        resume=RESUME,
        store=None,
        use_llm=False,
    )
    assert "Python" in result["matched_skills"]
    assert "FastAPI" in result["matched_skills"]
    assert "Kubernetes" in result["missing_skills"]
    assert 0 <= result["overall_match_score"] <= 100
    # fallback builds a checklist from missing skills + uncovered requirements
    assert result["resume_edit_checklist"]
    assert any("Kubernetes" in item for item in result["resume_edit_checklist"])


@pytest.mark.asyncio
async def test_analyze_gap_uses_llm_enrichment_when_available():
    fake = {
        "overall_match_score": 78,
        "match_summary": "Strong fit with two infra gaps.",
        "weak_signals": ["Terraform mentioned but no metric"],
        "resume_edit_checklist": ["Add a bullet quantifying RAG latency wins"],
    }
    with patch("app.gap_analysis._llm_enrich", AsyncMock(return_value=fake)):
        result = await analyze_gap(jd_text=JD_TEXT, identity=IDENTITY, resume=RESUME, store=None)
    assert result["overall_match_score"] == 78
    assert result["match_summary"] == "Strong fit with two infra gaps."
    assert result["weak_signals"] == ["Terraform mentioned but no metric"]


@pytest.mark.asyncio
async def test_analyze_gap_requires_some_jd_input():
    with pytest.raises(ValueError):
        await analyze_gap(jd_text="", jd_url=None, identity=IDENTITY, resume=RESUME, use_llm=False)


# ── API ───────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def auth_client():
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/api/auth/login", json={"password": "testpass"})
        c.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"
        yield c


@pytest.mark.asyncio
async def test_gap_analyze_endpoint(auth_client):
    fake = {
        "overall_match_score": 70,
        "match_summary": "Good fit.",
        "weak_signals": [],
        "resume_edit_checklist": ["Add Kubernetes evidence"],
    }
    with patch("app.gap_analysis._llm_enrich", AsyncMock(return_value=fake)):
        resp = await auth_client.post("/api/gap/analyze", json={"jd_text": JD_TEXT})
    assert resp.status_code == 200
    data = resp.json()
    assert "Python" in data["jd_skills"]
    assert isinstance(data["matched_skills"], list)
    assert data["overall_match_score"] == 70
    assert data["resume_edit_checklist"] == ["Add Kubernetes evidence"]


@pytest.mark.asyncio
async def test_gap_analyze_requires_input(auth_client):
    resp = await auth_client.post("/api/gap/analyze", json={})
    assert resp.status_code == 422
