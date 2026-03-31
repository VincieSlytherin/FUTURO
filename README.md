<div align="center">
  <img src="futuro.png" alt="Futuro" width="120" />
  <h1>Futuro</h1>
  <p>A warm, memory-driven job search companion you own and run yourself.</p>
</div>

---

Futuro is a locally-hosted web application that knows your full professional story, tracks every company you're pursuing, coaches your interview prep, and gives honest strategic feedback. It's not a SaaS tool. You build it, you own the code, and your data never leaves your machine unless you choose otherwise.

---

## Features

- **Persistent memory** — your background, skills, target companies, and STAR stories persist across every session without re-explaining. Memory lives in plain Markdown files, git-tracked and always editable.
- **AI-powered chat** — streaming conversation with intent classification that automatically routes to the right specialist agent (intake, story builder, resume editor, BQ coach, debrief, strategy review, job scout).
- **Job scout** — automated job listing search via LinkedIn, Indeed, and Glassdoor (powered by python-jobspy), with Claude scoring each listing for fit. Runs on a schedule or on demand.
- **Company pipeline** — visual Kanban tracker from RESEARCHING → APPLIED → SCREENING → TECHNICAL → ONSITE → OFFER, with activity log and response-rate metrics.
- **Story bank** — STAR stories indexed by behavioral theme in ChromaDB, semantically searchable, ready for any behavioral question.
- **Interview log** — log every round, run post-interview debriefs with the AI, and surface patterns across companies.
- **Resume versioning** — tailored resume variants per company, version-tracked in memory.
- **Memory editor** — edit your six core memory files directly in the browser, with a full git commit log.
- **Provider flexibility** — use Anthropic Claude or run fully offline with local Ollama (Qwen 2.5, nomic-embed-text).

---

## Tech stack

| Layer | Choice |
|---|---|
| Backend | FastAPI (Python 3.12) |
| Frontend | Next.js 14 (TypeScript) |
| LLM | Anthropic Claude API (default) or Ollama (local) |
| Database | SQLite via SQLAlchemy 2.0 + Alembic migrations |
| Memory files | Markdown (git-tracked via GitPython) |
| Vector search | ChromaDB (local) |
| Job scraping | python-jobspy (LinkedIn, Indeed, Glassdoor) |
| Scheduling | APScheduler (background scout runs) |
| Auth | Single-user JWT (bcrypt password hash) |
| Container | Docker + docker-compose |

---

## Project structure

```
futuro/
├── README.md
├── Makefile
├── docker-compose.yml
├── .env.example
├── docs/
│   ├── TELOS.md              # Vision and philosophy
│   ├── ARCHITECTURE.md       # System architecture
│   ├── TECH_STACK.md         # Stack decisions and rationale
│   ├── DATA_MODEL.md         # Database schema and memory structures
│   ├── API_SPEC.md           # REST API reference
│   ├── AGENT_DESIGN.md       # Agent architecture and prompts
│   ├── MEMORY_SYSTEM.md      # Memory layer design
│   ├── FRONTEND_SPEC.md      # UI specification
│   ├── DEV_SETUP.md          # Local development guide
│   ├── DEPLOYMENT.md         # Deployment options
│   └── ROADMAP.md            # Phased development plan
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/              # auth, chat, campaign, scout, interviews,
│   │   │                     # memory, stories, intake, providers
│   │   ├── agents/           # CoreAgent, IntakeAgent, StoryBuilderAgent,
│   │   │                     # ResumeEditorAgent, BQCoachAgent, DebriefAgent,
│   │   │                     # StrategyReviewAgent, JobScoutAgent
│   │   ├── providers/        # claude_provider, ollama_provider, router
│   │   ├── memory/           # manager, vector_store, markdown_io
│   │   └── models/           # SQLAlchemy ORM (Company, Interview, Session)
│   ├── data/
│   │   ├── memory/           # Markdown memory files (git-tracked)
│   │   ├── uploads/          # Ingested files (gitignored)
│   │   └── chroma/           # ChromaDB local store (gitignored)
│   ├── tests/
│   ├── alembic/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/              # /chat, /campaign, /jobs, /interviews,
│   │   │                     # /stories, /memory, /resume, /settings
│   │   ├── components/       # MessageBubble, MemoryUpdateCard, ProviderStatus
│   │   └── lib/              # api clients, Zustand store, TypeScript types
│   ├── package.json
│   └── Dockerfile
```

---

## Quick start

```bash
git clone https://github.com/your-username/futuro.git
cd futuro
make setup        # Creates .env, hashes password, runs migrations, inits memory repo
make dev          # Starts backend (port 8000) + frontend (port 3000)
```

Open [http://localhost:3000](http://localhost:3000), log in, and run onboarding.

See [docs/DEV_SETUP.md](docs/DEV_SETUP.md) for full setup instructions.

### Key `make` targets

| Command | What it does |
|---|---|
| `make setup` | First-time setup (env, deps, DB, memory git repo) |
| `make dev` | Run backend + frontend in development mode |
| `make test` | Run all tests |
| `make migrate` | Run pending DB migrations |
| `make rebuild-index` | Rebuild ChromaDB vector index from stories_bank.md |
| `make backup` | Archive data directory to a tarball |
| `make docker-dev` | Run everything in Docker |
| `make ollama-setup` | Pull qwen2.5:7b and nomic-embed-text for offline use |

### Environment variables (`.env.example`)

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes* | Claude API key (*not required if using Ollama only) |
| `JWT_SECRET` | Yes | Generated by `make setup` |
| `USER_PASSWORD_HASH` | Yes | Bcrypt hash of your login password |
| `LLM_PROVIDER` | No | `claude` (default), `ollama`, or `auto` |
| `SCOUT_DEFAULT_LOCATION` | No | e.g. `San Francisco, CA` |
| `OLLAMA_BASE_URL` | No | `http://localhost:11434` |

---

## Memory system

All persistent state lives in six Markdown files under `backend/data/memory/`, auto-committed to a local git repo on every change:

| File | Purpose |
|---|---|
| `L0_identity.md` | Who you are — background, skills, target roles |
| `L1_campaign.md` | Active job search state and goals |
| `L2_knowledge.md` | Distilled insights from ingested content |
| `stories_bank.md` | STAR stories indexed by behavioral theme |
| `resume_versions.md` | Resume variants per target role |
| `interview_log.md` | Post-interview debriefs and patterns |

You can edit any of these directly in the browser (`/memory`), via the chat, or with any text editor. Every change is versioned — you own the history.

---

## Agent system

Futuro classifies each chat message by intent and routes it to the appropriate agent:

| Intent | Agent | What it does |
|---|---|---|
| GENERAL | CoreAgent | Greetings, check-ins, open-ended support |
| INTAKE | IntakeAgent | Process URLs, PDFs, DOCX, or pasted text into memory |
| STORY | StoryBuilderAgent | Build and refine STAR stories |
| RESUME | ResumeEditorAgent | Tailor resume to a specific role |
| BQ | BQCoachAgent | Behavioral question practice with follow-up |
| DEBRIEF | DebriefAgent | Post-interview reflection and coaching |
| STRATEGY | StrategyReviewAgent | Review and adjust overall search strategy |
| SCOUT | JobScoutAgent | Analyze job listings and recommend targets |

Every agent loads your full memory context before responding and can propose atomic memory updates inline.

---

## Design principles

1. **You own it** — code, data, and memory live on your machine
2. **Human-readable state** — all memory is Markdown; edit it directly, git blame it, carry it to any future system
3. **Warm by design** — encouragement and emotional intelligence are not bolt-ons; they're in the agent architecture
4. **Goal-oriented, not task-oriented** — every action connects back to your target role
5. **Incrementally deployable** — works fully offline with SQLite + ChromaDB + Ollama; cloud deployment is optional

---

## License

**Futuro Personal Use License v1.0** — Copyright (c) 2026 Ran. All rights reserved.

You may use, study, and modify this software for **personal, non-commercial purposes**. You may share the unmodified source with attribution and this license included.

**You may NOT**, without prior written permission:
- Use this software commercially (SaaS, consulting, revenue-generating products)
- Sell, sublicense, or transfer rights to this software or any derivative
- Build a competing product that replicates Futuro's functionality and offers it to third parties
- Remove or alter this license, the copyright notice, or attribution in any distributed copy

Running this software on your own machine for your personal job search, or sharing the source on GitHub for others to study, is explicitly permitted.

See [LICENSE](LICENSE) for the full license text, including third-party component notices and disclaimer.

---

*For commercial licensing inquiries, contact the copyright holder directly.*
