import bcrypt
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Patch settings before importing app
import os
os.environ.update({
    "ANTHROPIC_API_KEY": "sk-ant-test",
    "JWT_SECRET": "test-secret-32-chars-long-enough-x",
    "USER_PASSWORD_HASH": bcrypt.hashpw(b"testpass", bcrypt.gensalt()).decode(),
    "DATA_DIR": "/tmp/futuro-test/data",
    "MEMORY_DIR": "/tmp/futuro-test/data/memory",
    "CHROMA_DIR": "/tmp/futuro-test/data/chroma",
    "DB_PATH": "/tmp/futuro-test/data/futuro.db",
    "GIT_AUTO_COMMIT": "false",
    "DEBUG": "true",
    "ALLOWED_ORIGINS": "http://localhost:3000",
})

from app.main import app  # noqa: E402


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def auth_client(client):
    resp = await client.post("/api/auth/login", json={"password": "testpass"})
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_login_success(client):
    resp = await client.post("/api/auth/login", json={"password": "testpass"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    resp = await client.post("/api/auth/login", json={"password": "wrong"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_requires_auth(client):
    resp = await client.get("/api/memory/files")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_memory_files(auth_client):
    resp = await auth_client.get("/api/memory/files")
    assert resp.status_code == 200
    files = resp.json()["files"]
    filenames = [f["filename"] for f in files]
    assert "L0_identity.md" in filenames
    assert "stories_bank.md" in filenames


@pytest.mark.asyncio
async def test_get_memory_file(auth_client):
    resp = await auth_client.get("/api/memory/L0_identity.md")
    assert resp.status_code == 200
    data = resp.json()
    assert "content" in data
    assert "L0" in data["content"]


@pytest.mark.asyncio
async def test_write_memory_file(auth_client):
    new_content = "# L0 · Core Identity\n\nTest content.\n"
    resp = await auth_client.put(
        "/api/memory/L0_identity.md",
        json={"content": new_content},
    )
    assert resp.status_code == 200

    read_back = await auth_client.get("/api/memory/L0_identity.md")
    assert "Test content" in read_back.json()["content"]


@pytest.mark.asyncio
async def test_campaign_create_and_list(auth_client):
    resp = await auth_client.post("/api/campaign/companies", json={
        "name": "Anthropic",
        "role_title": "AI Engineer",
        "priority": "HIGH",
    })
    assert resp.status_code == 201
    company_id = resp.json()["id"]

    resp = await auth_client.get("/api/campaign/companies")
    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()]
    assert "Anthropic" in names

    await auth_client.delete(f"/api/campaign/companies/{company_id}")


@pytest.mark.asyncio
async def test_campaign_stage_update(auth_client):
    resp = await auth_client.post("/api/campaign/companies", json={
        "name": "TestCo",
        "role_title": "ML Engineer",
    })
    company_id = resp.json()["id"]

    resp = await auth_client.patch(
        f"/api/campaign/companies/{company_id}/stage",
        json={"stage": "APPLIED", "description": "Submitted application"},
    )
    assert resp.status_code == 200
    assert resp.json()["stage"] == "APPLIED"

    await auth_client.delete(f"/api/campaign/companies/{company_id}")


@pytest.mark.asyncio
async def test_campaign_stats(auth_client):
    resp = await auth_client.get("/api/campaign/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_active" in data
    assert "response_rate" in data


@pytest.mark.asyncio
async def test_story_search_empty(auth_client):
    resp = await auth_client.post("/api/stories/search", json={"query": "ambiguity", "n_results": 3})
    assert resp.status_code == 200
    assert "results" in resp.json()


@pytest.mark.asyncio
async def test_story_rebuild_index(auth_client):
    resp = await auth_client.post("/api/stories/rebuild-index")
    assert resp.status_code == 200
    assert "stories_indexed" in resp.json()
