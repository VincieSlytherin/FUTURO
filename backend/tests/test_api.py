import bcrypt
import pytest
import pytest_asyncio
from uuid import uuid4
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch

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
    "ALLOWED_ORIGINS": '["http://localhost:3000"]',
})

from app.main import app  # noqa: E402
from app.models.schemas import MemoryUpdate  # noqa: E402


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
    assert "planner.md" in filenames
    assert "stories_bank.md" in filenames


@pytest.mark.asyncio
async def test_get_memory_file(auth_client):
    resp = await auth_client.get("/api/memory/L0_identity.md")
    assert resp.status_code == 200
    data = resp.json()
    assert "content" in data
    assert "L0" in data["content"]


@pytest.mark.asyncio
async def test_custom_instructions_api_round_trip(auth_client, tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "custom_instructions_path", tmp_path / "custom_instructions.json")

    get_resp = await auth_client.get("/api/instructions")
    assert get_resp.status_code == 200
    assert "bq_instruction" in get_resp.json()

    put_resp = await auth_client.put("/api/instructions", json={
        "global_instruction": "Be concise.",
        "general_instruction": "",
        "bq_instruction": "Always score my answer out of 10 first.",
        "story_instruction": "",
        "resume_instruction": "",
        "debrief_instruction": "",
        "strategy_instruction": "",
        "scout_instruction": "",
        "intake_instruction": "",
    })
    assert put_resp.status_code == 200

    read_back = await auth_client.get("/api/instructions")
    assert read_back.status_code == 200
    payload = read_back.json()
    assert payload["global_instruction"] == "Be concise."
    assert payload["bq_instruction"] == "Always score my answer out of 10 first."


@pytest.mark.asyncio
async def test_notifications_api_round_trip(auth_client, tmp_path, monkeypatch):
    from app.config import settings
    from app.api import notifications as notifications_api

    monkeypatch.setattr(notifications_api, "ENV_PATH", tmp_path / ".env")
    monkeypatch.setattr(settings, "notify_email", "")
    monkeypatch.setattr(settings, "gmail_app_password", "")

    get_resp = await auth_client.get("/api/notifications")
    assert get_resp.status_code == 200
    assert get_resp.json()["notifications_enabled"] is False

    put_resp = await auth_client.put("/api/notifications", json={
        "notify_email": "user@example.com",
        "gmail_app_password": "abcd efgh ijkl mnop",
    })
    assert put_resp.status_code == 200
    payload = put_resp.json()
    assert payload["notify_email"] == "user@example.com"
    assert payload["gmail_app_password_configured"] is True
    assert payload["notifications_enabled"] is True


@pytest.mark.asyncio
async def test_notifications_test_endpoint(auth_client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "notify_email", "user@example.com")
    monkeypatch.setattr(settings, "gmail_app_password", "abcd efgh ijkl mnop")

    with patch("app.api.notifications.EmailNotificationService.build_test_scout_jobs", AsyncMock(return_value=[])), \
         patch("app.api.notifications.EmailNotificationService.send_scout_run_summary", AsyncMock(return_value=True)) as send_mock:
        resp = await auth_client.post("/api/notifications/test", json={"kind": "scout"})

    assert resp.status_code == 200
    assert resp.json()["sent"] is True
    assert send_mock.await_count == 1


@pytest.mark.asyncio
async def test_run_scout_triggers_email_notification(monkeypatch):
    from app.config import settings
    from app.database import init_db
    from app.memory.manager import MemoryManager
    from app.database import AsyncSessionLocal
    from app.models.db import ScoutConfig
    from app.agents.job_scout import run_scout

    monkeypatch.setattr(settings, "notify_email", "user@example.com")
    monkeypatch.setattr(settings, "gmail_app_password", "abcdefghijklmnop")

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.memory_dir.mkdir(parents=True, exist_ok=True)
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    await init_db()

    async with AsyncSessionLocal() as db:
        config = ScoutConfig(
            name="Notify test",
            search_term="AI Engineer",
            location="Remote",
            min_score=70,
        )
        db.add(config)
        await db.commit()
        await db.refresh(config)

    memory = MemoryManager(settings.memory_dir, git_auto_commit=False)
    mock_score = {
        "score": 82,
        "score_summary": "Strong match.",
        "score_pros": '["Good fit"]',
        "score_cons": '[]',
        "sponsorship_likely": True,
    }

    with patch("app.agents.job_scout._scrape_jobs", return_value=[
            {
                "title": "Applied AI Engineer",
                "company": "Sample AI Co",
                "job_url": "https://example.com/jobs/1",
                "url_hash": uuid4().hex,
                "location": "Remote",
                "is_remote": True,
                "salary_min": 180000,
                "salary_max": 220000,
                "salary_currency": "USD",
                "description": "Build production LLM systems.",
                "description_snippet": "Build production LLM systems.",
                "site": "linkedin",
                "date_posted": "today",
                "job_type": "full-time",
            }
        ]), \
         patch("app.agents.job_scout.score_job", AsyncMock(return_value=mock_score)), \
         patch("app.agents.job_scout.EmailNotificationService.send_scout_run_summary", AsyncMock(return_value=True)) as send_mock:
        result = await run_scout(
            config_id=config.id,
            search_term=config.search_term,
            location=config.location,
            sites=["linkedin"],
            results_wanted=10,
            hours_old=72,
            distance=50,
            is_remote=None,
            min_score=config.min_score,
            memory=memory,
            db_session=None,
        )

    assert result["jobs_new"] >= 1
    assert send_mock.await_count == 1


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
async def test_portfolio_upload_list_and_delete(auth_client, tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "portfolio_dir", tmp_path / "portfolio")

    upload = await auth_client.post(
        "/api/portfolio/upload",
        files={"files": ("resume.pdf", b"%PDF-1.4 test content", "application/pdf")},
    )
    assert upload.status_code == 201
    uploaded = upload.json()["files"]
    assert len(uploaded) == 1
    assert uploaded[0]["filename"] == "resume.pdf"

    listed = await auth_client.get("/api/portfolio/files")
    assert listed.status_code == 200
    filenames = [item["filename"] for item in listed.json()["files"]]
    assert "resume.pdf" in filenames
    assert listed.json()["files"][0]["relative_path"] == "resume.pdf"

    download = await auth_client.get("/api/portfolio/download/resume.pdf")
    assert download.status_code == 200
    assert download.content == b"%PDF-1.4 test content"

    deleted = await auth_client.delete("/api/portfolio/entry/resume.pdf")
    assert deleted.status_code == 204

    listed_after = await auth_client.get("/api/portfolio/files")
    assert listed_after.status_code == 200
    assert listed_after.json()["files"] == []
    assert listed_after.json()["folders"] == []


@pytest.mark.asyncio
async def test_portfolio_folder_upload_and_delete(auth_client, tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "portfolio_dir", tmp_path / "portfolio")

    upload = await auth_client.post(
        "/api/portfolio/upload",
        files=[
            ("paths", (None, "applications/company-a/resume.docx")),
            ("paths", (None, "applications/company-a/offer.pdf")),
            ("files", ("resume.docx", b"docx-content", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
            ("files", ("offer.pdf", b"%PDF-1.4 offer", "application/pdf")),
        ],
    )
    assert upload.status_code == 201
    payload = upload.json()
    assert {item["relative_path"] for item in payload["files"]} == {
        "applications/company-a/resume.docx",
        "applications/company-a/offer.pdf",
    }

    listed = await auth_client.get("/api/portfolio/files")
    assert listed.status_code == 200
    assert any(item["relative_path"] == "applications/company-a/resume.docx" for item in listed.json()["files"])
    assert any(folder["path"] == "applications" for folder in listed.json()["folders"])
    assert any(folder["path"] == "applications/company-a" for folder in listed.json()["folders"])

    deleted = await auth_client.delete("/api/portfolio/entry/applications/company-a")
    assert deleted.status_code == 204

    listed_after = await auth_client.get("/api/portfolio/files")
    assert listed_after.status_code == 200
    assert listed_after.json()["files"] == []


@pytest.mark.asyncio
async def test_campaign_create_extracts_jd_fields(auth_client):
    resp = await auth_client.post("/api/campaign/companies", json={
        "name": "OpenAI",
        "role_title": "Applied AI Engineer",
        "job_description_text": """
Responsibilities
- Build production RAG systems
- Work with Python and FastAPI services

Requirements
- 3+ years with Python
- Experience with LLM applications and AWS
- Hybrid work model
- Visa sponsorship available
        """,
    })
    assert resp.status_code == 201
    payload = resp.json()
    assert payload["jd_summary"]
    assert "Python" in payload["jd_skills"]
    assert any("RAG" in item or "LLM" in item for item in payload["jd_requirements"])
    assert payload["work_mode"] == "HYBRID"
    assert payload["sponsorship_confirmed"] is True

    await auth_client.delete(f"/api/campaign/companies/{payload['id']}")


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


@pytest.mark.asyncio
async def test_delete_scout_config_with_runs_and_jobs(auth_client):
    from app.database import AsyncSessionLocal
    from app.models.db import ScoutConfig, ScoutRun, JobListing

    create_resp = await auth_client.post("/api/scout/configs", json={
        "name": "Delete me",
        "search_term": "AI Engineer",
        "location": "San Francisco, CA",
        "min_score": 60,
        "schedule_hours": 24,
    })
    assert create_resp.status_code == 201
    config_id = create_resp.json()["id"]

    async with AsyncSessionLocal() as db:
        run = ScoutRun(config_id=config_id, status="DONE")
        db.add(run)
        await db.flush()
        job = JobListing(
            url_hash="delete-test-hash",
            job_url="https://example.com/job",
            title="AI Engineer",
            company="ExampleCo",
            location="Remote",
            is_remote=True,
            site="linkedin",
            config_id=config_id,
            run_id=run.id,
            status="NEW",
        )
        db.add(job)
        await db.commit()

    delete_resp = await auth_client.delete(f"/api/scout/configs/{config_id}")
    assert delete_resp.status_code == 204

    async with AsyncSessionLocal() as db:
        assert await db.get(ScoutConfig, config_id) is None
        remaining_run = await db.get(ScoutRun, run.id)
        remaining_job = await db.get(JobListing, job.id)
        assert remaining_run is None
        assert remaining_job is not None
        assert remaining_job.config_id is None
        assert remaining_job.run_id is None


def test_memory_manager_appends_to_subheading():
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from app.memory.manager import MemoryManager

    with TemporaryDirectory() as tmp:
        manager = MemoryManager(Path(tmp), git_auto_commit=False)
        manager.apply_update(
            filename="resume_versions.md",
            section="Bullets",
            action="append",
            content="- Built an LLM evaluation pipeline with Python and SQL",
            reason="test append",
        )
        content = manager.read("resume_versions.md")
        assert "### Bullets" in content
        assert "- Built an LLM evaluation pipeline with Python and SQL" in content
        assert "\n## Bullets\n" not in content


@pytest.mark.asyncio
async def test_chat_returns_memory_proposals_without_auto_applying(auth_client, tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "memory_dir", tmp_path / "memory")

    class FakeAgent:
        async def stream(self, message, history, ctx):
            yield "Thanks, I saved that."

        async def post_process(self, response, message, ctx, history=None):
            return [
                MemoryUpdate(
                    file="resume_versions.md",
                    section="Bullets",
                    action="append",
                    content="- Built production RAG pipelines and evaluation workflows",
                    reason="Saved resume details shared in chat",
                )
            ]

    with (
        patch("app.api.chat.classify_intent", AsyncMock(return_value="RESUME")),
        patch("app.api.chat.get_agent", return_value=FakeAgent()),
    ):
        resp = await auth_client.post("/api/chat", json={
            "message": "Here is my resume. I built production RAG pipelines and evaluation workflows.",
            "history": [],
        })

    assert resp.status_code == 200
    assert '"proposed_updates"' in resp.text
    assert '"applied": false' in resp.text.lower()

    resume = await auth_client.get("/api/memory/resume_versions.md")
    assert resume.status_code == 200
    assert "Built production RAG pipelines and evaluation workflows" not in resume.json()["content"]


@pytest.mark.asyncio
async def test_post_process_uses_session_transcript_for_memory_extraction():
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from unittest.mock import AsyncMock
    from app.memory.manager import MemoryManager
    from app.agents.base import StrategyReviewAgent

    captured = {}

    class FakeProvider:
        async def complete(self, system, messages, max_tokens):
            captured["system"] = system
            captured["messages"] = messages
            return "[]"

    with TemporaryDirectory() as tmp:
        memory = MemoryManager(Path(tmp), git_auto_commit=False)
        agent = StrategyReviewAgent(memory)
        ctx = memory.load_context("STRATEGY")
        history = [
            {"role": "user", "content": "I'm prioritizing applied AI roles in healthcare and fintech."},
            {"role": "assistant", "content": "Noted. What matters most in the next few weeks?"},
        ]
        with (
            patch("app.agents.base.get_provider", return_value=FakeProvider()),
            patch.object(StrategyReviewAgent, "_extract_story_bank_updates", return_value=[]),
        ):
            updates = await agent.post_process(
                "We should focus on high-signal teams next.",
                "I also want remote-friendly teams and I want to avoid ad-tech.",
                ctx,
                history=history,
            )

    assert all(update.file != "stories_bank.md" for update in updates)
    transcript = captured["messages"][0]["content"]
    assert "Session transcript:" in transcript
    assert "USER: I'm prioritizing applied AI roles in healthcare and fintech." in transcript
    assert "USER: I also want remote-friendly teams and I want to avoid ad-tech." in transcript
    assert "ASSISTANT: We should focus on high-signal teams next." in transcript


@pytest.mark.asyncio
async def test_resume_post_process_strips_formatting_and_extracts_content():
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from app.memory.manager import MemoryManager
    from app.agents.base import ResumeEditorAgent

    resume_text = """
This is my resume:#show heading: set text(font: "Linux Biolinum")
= Ran Ju St. Louis, MO | ranj@alumni.cmu.edu
== Summary
AI Systems Engineer specializing in production-scale LLM applications, RAG pipelines, and multi-agent systems.
== Professional Experience
*Reinsurance Group of America (RGA)* _Assistant Data Scientist (Applied AI / GenAI Systems)_
- Led end-to-end design and deployment of a production RAG platform on AWS Bedrock for treaty compliance analysis, supporting 60+ business units and reducing manual review time by 90%+.
- Re-architected hybrid retrieval pipeline (semantic + lexical + metadata filtering) with async execution, reducing P95 latency from 60s+ to under 10s.
== AI Projects
*AI Research Intelligence Pipeline (LLM Application System)*
- Architected bilingual content intelligence pipeline aggregating 20+ AI/ML sources with semantic deduplication.
== Education
*Carnegie Mellon University, School of Computer Science* #h(1fr) Pittsburgh, PA \ Master in Computational Data Science | GPA: 3.85/4.0 #h(1fr) _Aug 2022 - Dec 2023_
== Skills
- LLM & GenAI Systems: RAG Pipelines, Multi-Agent Systems, LangGraph, LangChain, Guardrails
- AI Infrastructure: Python, FastAPI, AWS, Databricks, Docker, Kubernetes
"""

    with TemporaryDirectory() as tmp:
        memory = MemoryManager(Path(tmp), git_auto_commit=False)
        agent = ResumeEditorAgent(memory)
        ctx = memory.load_context("RESUME")
        updates = await agent.post_process("Thanks for sharing your resume.", resume_text, ctx)

    resume_update = next(u for u in updates if u.file == "resume_versions.md")
    assert resume_update.action == "replace"
    assert "Linux Biolinum" not in resume_update.content
    assert "production RAG platform on AWS Bedrock" in resume_update.content
    assert "20+ AI/ML sources" in resume_update.content

    identity_update = next(u for u in updates if u.file == "L0_identity.md" and u.section == "Technical skills")
    assert "LangGraph" in identity_update.content
    assert "FastAPI" in identity_update.content


@pytest.mark.asyncio
async def test_bq_post_process_builds_story_bank_updates():
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from app.memory.manager import MemoryManager
    from app.agents.base import BQCoachAgent

    response = """
I've saved your full BQ story bank to memory. You now have:

Core stories locked in:
Tell me about yourself — Applied GenAI at RGA, RAG platform + copilot rebuild
Why should we hire you — Production AI depth + regulated environment experience
Greatest achievement — RAG platform (the anchor story)

Still missing (we need to build these):
Failure story — something you owned that didn't go as planned
Leadership/mentorship story — helping someone grow or driving alignment

When you're ready, let's knock out the failure story first.
"""

    with TemporaryDirectory() as tmp:
        memory = MemoryManager(Path(tmp), git_auto_commit=False)
        agent = BQCoachAgent(memory)
        ctx = memory.load_context("BQ")
        updates = await agent.post_process(response, "Here is my BQ story bank.", ctx)

        for update in updates:
            memory.apply_update(
                filename=update.file,
                section=update.section,
                action=update.action,
                content=update.content,
                reason=update.reason,
            )

        stories = memory.read("stories_bank.md")

    assert any(u.file == "stories_bank.md" and u.section == "Quick-reference index" for u in updates)
    assert any(u.file == "stories_bank.md" and u.section == "Coverage gaps" for u in updates)
    assert any(u.file == "stories_bank.md" and u.action == "append" for u in updates)
    assert "## STORY-001 · Tell me about yourself" in stories
    assert "Applied GenAI at RGA, RAG platform + copilot rebuild" in stories
    assert "## Coverage gaps" in stories
    assert "Failure story" in stories


@pytest.mark.asyncio
async def test_story_post_process_saves_full_star_details():
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from app.memory.manager import MemoryManager
    from app.agents.base import StoryBuilderAgent

    response = """
## Copilot rebuild under pressure

**Themes:** ambiguity, technical problem-solving, conflict
**The one-liner:** Rebuilt a failing analytics copilot from brittle SQL generation to reliable function-calling orchestration.
**Situation:** Our Databricks analytics copilot was failing frequently in production and users were losing trust in it.
**Task:** I needed to redesign the system quickly without breaking stakeholder workflows, while preserving analyst flexibility.
**Action:** I audited failure patterns, replaced free-form SQL generation with tool-based function calling, added retry logic, and built an observability panel so we could inspect agent traces with non-technical partners.
**Result:** Execution failure rate dropped from 31% to 5%, ad-hoc SQL workload fell by 4x, and stakeholders regained confidence in the tool.

30-second version: ...
"""

    with TemporaryDirectory() as tmp:
        memory = MemoryManager(Path(tmp), git_auto_commit=False)
        agent = StoryBuilderAgent(memory)
        ctx = memory.load_context("STORY")
        updates = await agent.post_process(response, "Help me capture my copilot rebuild story.", ctx)

        for update in updates:
            memory.apply_update(
                filename=update.file,
                section=update.section,
                action=update.action,
                content=update.content,
                reason=update.reason,
            )

        stories = memory.read("stories_bank.md")

    assert "## STORY-001 · Copilot rebuild under pressure" in stories
    assert "**Situation:** Our Databricks analytics copilot was failing frequently in production" in stories
    assert "**Task:** I needed to redesign the system quickly" in stories
    assert "**Action:** I audited failure patterns" in stories
    assert "**Result:** Execution failure rate dropped from 31% to 5%" in stories


def test_agent_build_system_includes_custom_instructions(tmp_path, monkeypatch):
    from app.config import settings
    from app.custom_instructions import CustomInstructionManager
    from app.memory.manager import MemoryManager
    from app.agents.base import BQCoachAgent

    custom_path = tmp_path / "custom_instructions.json"
    monkeypatch.setattr(settings, "custom_instructions_path", custom_path)

    manager = CustomInstructionManager(custom_path)
    manager.save({
        "global": "Keep answers direct.",
        "BQ": "Always rate the answer first, then rewrite it in STAR.",
    })

    memory = MemoryManager(tmp_path / "memory", git_auto_commit=False)
    agent = BQCoachAgent(memory)
    ctx = memory.load_context("BQ")
    system = agent._build_system(ctx)

    assert "Keep answers direct." in system
    assert "Always rate the answer first, then rewrite it in STAR." in system


def test_weekly_digest_text_includes_planner_sections():
    from app.notifications import EmailNotificationService

    service = EmailNotificationService()
    digest = {
        "generated_at": None,
        "top_jobs": [],
        "current_stage_counts": {},
        "previous_stage_counts": {},
        "applied_this_week": 2,
        "weekly_focus": "- Finish two tailored applications",
        "daily_tasks": [
            {"done": False, "text": "Tailor the Stripe resume"},
            {"done": True, "text": "Send recruiter follow-up to Anthropic"},
        ],
        "learning_backlog": [
            {"done": False, "text": "Review system design for retrieval pipelines"},
        ],
        "encouragement": "Keep going.",
    }

    text = service._build_weekly_digest_text(digest, test_mode=False)

    assert "Daily tasks:" in text
    assert "- [ ] Tailor the Stripe resume" in text
    assert "- [x] Send recruiter follow-up to Anthropic" in text
    assert "Learning backlog:" in text
    assert "- [ ] Review system design for retrieval pipelines" in text


def test_memory_manager_migrates_legacy_planner_sections(tmp_path):
    from app.memory.manager import MemoryManager

    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    (memory_dir / "L1_campaign.md").write_text(
        "# L1 · Campaign State\n\n"
        "## Weekly focus\n\n"
        "- Ship applications\n\n"
        "## Daily tasks\n\n"
        "- [ ] Tailor resume for Stripe\n\n"
        "## Learning backlog\n\n"
        "- [ ] Review retrieval evaluation\n",
        encoding="utf-8",
    )

    memory = MemoryManager(memory_dir, git_auto_commit=False)
    planner = memory.read("planner.md")

    assert "## Daily tasks" in planner
    assert "- [ ] Tailor resume for Stripe" in planner
    assert "## Learning backlog" in planner
    assert "- [ ] Review retrieval evaluation" in planner


def test_agent_build_system_includes_planner_context(tmp_path):
    from app.memory.manager import MemoryManager
    from app.agents.base import PlannerAgent

    memory = MemoryManager(tmp_path / "memory", git_auto_commit=False)
    memory.apply_update(
        filename="planner.md",
        section="Daily tasks",
        action="replace",
        content="- [ ] Finish one application",
        reason="seed planner task",
    )

    agent = PlannerAgent(memory)
    ctx = memory.load_context("PLANNER")
    system = agent._build_system(ctx)

    assert "## Their living planner" in system
    assert "Finish one application" in system
