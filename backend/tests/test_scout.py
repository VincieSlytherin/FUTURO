"""
Tests for Job Scout: scraping mock, scoring, API endpoints, dedup logic.
"""
import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
import os

os.environ.update({
    "ANTHROPIC_API_KEY": "sk-ant-test",
    "JWT_SECRET": "test-secret-32-chars-long-enough-x",
    "USER_PASSWORD_HASH": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TiGM4e1sAnBZaOEf5RQD8vFv6Bmy",  # "testpass"
    "DATA_DIR": "/tmp/futuro-scout-test/data",
    "MEMORY_DIR": "/tmp/futuro-scout-test/data/memory",
    "CHROMA_DIR": "/tmp/futuro-scout-test/data/chroma",
    "DB_PATH": "/tmp/futuro-scout-test/data/futuro.db",
    "GIT_AUTO_COMMIT": "false",
    "DEBUG": "true",
    "SCOUT_ENABLED": "false",   # Don't start scheduler in tests
    "ALLOWED_ORIGINS": "http://localhost:3000",
})

from app.main import app  # noqa: E402


@pytest_asyncio.fixture
async def auth_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/api/auth/login", json={"password": "testpass"})
        c.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"
        yield c


# ── Unit: mock job scraping ───────────────────────────────────────────────────

def test_mock_jobs_returns_data():
    from app.agents.job_scout import _mock_jobs
    jobs = _mock_jobs("AI Engineer", "San Francisco, CA")
    assert len(jobs) >= 2
    for j in jobs:
        assert j["title"]
        assert j["company"]
        assert j["job_url"]
        assert j["url_hash"]
        assert len(j["url_hash"]) == 64   # sha256 hex


def test_mock_jobs_dedup_hash():
    from app.agents.job_scout import _mock_jobs
    import hashlib
    jobs = _mock_jobs("ML Engineer", "NYC")
    for j in jobs:
        expected = hashlib.sha256(j["job_url"].encode()).hexdigest()
        assert j["url_hash"] == expected


def test_safe_float():
    from app.agents.job_scout import _safe_float
    assert _safe_float(150000) == 150000.0
    assert _safe_float(None) is None
    assert _safe_float("nan") is None
    assert _safe_float("") is None
    assert _safe_float("200000") == 200000.0


def test_salary_str():
    from app.agents.job_scout import _salary_str
    assert "150" in _salary_str({"salary_min": 150000, "salary_max": 200000, "salary_currency": "USD"})
    assert "+" in _salary_str({"salary_min": 150000, "salary_max": None, "salary_currency": "USD"})
    assert "Not listed" in _salary_str({"salary_min": None, "salary_max": None, "salary_currency": None})


# ── Unit: Claude scoring ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_score_job_parses_valid_json():
    from app.agents.job_scout import score_job

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps({
        "score": 78,
        "summary": "Strong match — RAG and LLM experience aligns well.",
        "pros": ["Production RAG experience", "Python stack match"],
        "cons": ["No fine-tuning background mentioned"],
        "sponsorship_likely": True,
    }))]

    with patch("app.agents.job_scout._anthropic") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        result = await score_job(
            job={
                "title": "AI Engineer", "company": "Anthropic",
                "location": "SF", "is_remote": True,
                "salary_min": 180000, "salary_max": 250000, "salary_currency": "USD",
                "description": "We need someone with RAG and LLM experience.",
            },
            identity="I am an AI engineer with RAG and Python experience.",
        )

    assert result["score"] == 78
    assert result["sponsorship_likely"] is True
    assert "RAG" in result["score_summary"]
    assert isinstance(json.loads(result["score_pros"]), list)


@pytest.mark.asyncio
async def test_score_job_handles_malformed_json():
    from app.agents.job_scout import score_job

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Sorry I can't score that.")]

    with patch("app.agents.job_scout._anthropic") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        result = await score_job(
            job={"title": "X", "company": "Y", "location": "Z",
                 "is_remote": False, "description": ""},
            identity="test",
        )

    # Should fall back gracefully
    assert result["score"] == 50
    assert "unavailable" in result["score_summary"].lower()


@pytest.mark.asyncio
async def test_score_job_strips_markdown_fences():
    from app.agents.job_scout import score_job

    fenced = '```json\n{"score": 65, "summary": "OK", "pros": [], "cons": [], "sponsorship_likely": null}\n```'
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=fenced)]

    with patch("app.agents.job_scout._anthropic") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        result = await score_job(
            job={"title": "X", "company": "Y", "location": "Z", "is_remote": False, "description": ""},
            identity="test",
        )

    assert result["score"] == 65


# ── API: config CRUD ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_and_list_configs(auth_client):
    resp = await auth_client.post("/api/scout/configs", json={
        "name": "Test search",
        "search_term": "AI Engineer",
        "location": "San Francisco, CA",
        "min_score": 65,
        "schedule_hours": 24,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test search"
    assert data["min_score"] == 65
    config_id = data["id"]

    resp = await auth_client.get("/api/scout/configs")
    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()]
    assert "Test search" in names

    # Cleanup
    await auth_client.delete(f"/api/scout/configs/{config_id}")


@pytest.mark.asyncio
async def test_update_config(auth_client):
    resp = await auth_client.post("/api/scout/configs", json={
        "name": "Temp config", "search_term": "ML Engineer",
    })
    config_id = resp.json()["id"]

    resp = await auth_client.patch(f"/api/scout/configs/{config_id}", json={
        "min_score": 75, "is_active": False,
    })
    assert resp.status_code == 200
    assert resp.json()["min_score"] == 75
    assert resp.json()["is_active"] is False

    await auth_client.delete(f"/api/scout/configs/{config_id}")


@pytest.mark.asyncio
async def test_delete_config(auth_client):
    resp = await auth_client.post("/api/scout/configs", json={
        "name": "To delete", "search_term": "Data Scientist",
    })
    config_id = resp.json()["id"]
    resp = await auth_client.delete(f"/api/scout/configs/{config_id}")
    assert resp.status_code == 204

    resp = await auth_client.get("/api/scout/configs")
    assert not any(c["id"] == config_id for c in resp.json())


# ── API: manual run + listings ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_manual_run_queues_and_produces_listings(auth_client):
    # Create config
    resp = await auth_client.post("/api/scout/configs", json={
        "name": "Run test", "search_term": "AI Engineer",
        "location": "San Francisco, CA", "min_score": 0,
    })
    config_id = resp.json()["id"]

    # Mock jobspy and Claude scoring so test is fast + offline
    mock_score = {
        "score": 82, "score_summary": "Strong match.",
        "score_pros": '["Good fit"]', "score_cons": '[]',
        "sponsorship_likely": True,
    }
    with patch("app.agents.job_scout.score_job", AsyncMock(return_value=mock_score)):
        resp = await auth_client.post(f"/api/scout/configs/{config_id}/run")
        assert resp.status_code == 200
        assert resp.json()["queued"] is True

    # Wait a moment for background task
    import asyncio
    await asyncio.sleep(3)

    # Check listings appeared
    resp = await auth_client.get("/api/scout/jobs?status=NEW&limit=50")
    assert resp.status_code == 200
    jobs = resp.json()["jobs"]
    companies = [j["company"] for j in jobs]
    # Mock data includes Anthropic, Cohere, Databricks
    assert any(c in companies for c in ["Anthropic", "Cohere", "Databricks"])

    # Cleanup
    await auth_client.delete(f"/api/scout/configs/{config_id}")


@pytest.mark.asyncio
async def test_deduplication_prevents_double_insert(auth_client):
    resp = await auth_client.post("/api/scout/configs", json={
        "name": "Dedup test", "search_term": "AI Engineer",
        "location": "NYC", "min_score": 0,
    })
    config_id = resp.json()["id"]

    mock_score = {
        "score": 70, "score_summary": "Good.",
        "score_pros": "[]", "score_cons": "[]",
        "sponsorship_likely": None,
    }
    with patch("app.agents.job_scout.score_job", AsyncMock(return_value=mock_score)):
        # Run twice
        await auth_client.post(f"/api/scout/configs/{config_id}/run")
        import asyncio; await asyncio.sleep(2)
        await auth_client.post(f"/api/scout/configs/{config_id}/run")
        await asyncio.sleep(2)

    # Runs should show 0 new jobs on second run
    resp = await auth_client.get(f"/api/scout/configs/{config_id}/runs")
    runs = resp.json()
    if len(runs) >= 2:
        second_run = runs[0]  # most recent first
        # Second run should have found jobs_new=0 (all duplicates)
        assert second_run["jobs_new"] == 0

    await auth_client.delete(f"/api/scout/configs/{config_id}")


# ── API: job actions ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_job_action_save_and_dismiss(auth_client):
    resp = await auth_client.get("/api/scout/jobs?status=NEW&limit=10")
    jobs = resp.json()["jobs"]
    if not jobs:
        pytest.skip("No jobs in DB for action test")

    job_id = jobs[0]["id"]

    resp = await auth_client.patch(f"/api/scout/jobs/{job_id}/action", json={"status": "SAVED"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "SAVED"

    resp = await auth_client.patch(f"/api/scout/jobs/{job_id}/action", json={"status": "DISMISSED"})
    assert resp.json()["status"] == "DISMISSED"

    # Should no longer appear in NEW tab
    resp = await auth_client.get("/api/scout/jobs?status=NEW&limit=50")
    ids = [j["id"] for j in resp.json()["jobs"]]
    assert job_id not in ids


@pytest.mark.asyncio
async def test_add_job_to_pipeline(auth_client):
    resp = await auth_client.get("/api/scout/jobs?status=ALL&limit=10")
    jobs = resp.json()["jobs"]
    if not jobs:
        pytest.skip("No jobs in DB for pipeline test")

    job_id = jobs[0]["id"]
    resp = await auth_client.post(f"/api/scout/jobs/{job_id}/to-pipeline")
    assert resp.status_code == 200
    assert "company_id" in resp.json()
    assert "company_name" in resp.json()

    # Company should now be in campaign
    company_id = resp.json()["company_id"]
    resp = await auth_client.get(f"/api/campaign/companies/{company_id}")
    assert resp.status_code == 200


# ── API: stats ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scout_stats(auth_client):
    resp = await auth_client.get("/api/scout/stats")
    assert resp.status_code == 200
    data = resp.json()
    for key in ["total_found", "new_unseen", "high_score", "added_to_pipeline", "active_configs"]:
        assert key in data
    assert data["total_found"] >= 0


# ── API: pagination + filtering ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_jobs_min_score_filter(auth_client):
    resp = await auth_client.get("/api/scout/jobs?status=ALL&min_score=80&limit=50")
    assert resp.status_code == 200
    for job in resp.json()["jobs"]:
        assert job["score"] is None or job["score"] >= 80


@pytest.mark.asyncio
async def test_jobs_pagination(auth_client):
    page1 = await auth_client.get("/api/scout/jobs?status=ALL&limit=2&offset=0")
    page2 = await auth_client.get("/api/scout/jobs?status=ALL&limit=2&offset=2")
    p1_ids = {j["id"] for j in page1.json()["jobs"]}
    p2_ids = {j["id"] for j in page2.json()["jobs"]}
    # Pages should not overlap
    assert p1_ids.isdisjoint(p2_ids)
