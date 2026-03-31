# Futuro

A warm, memory-driven job search companion you own and run yourself.

Futuro is a personal AI side project — a locally-hosted web application that knows your full professional story, tracks every company you're pursuing, coaches your interview prep, and gives honest strategic feedback. It's not a SaaS tool. You build it, you own the code, and your data never leaves your machine unless you choose otherwise.

---

## What it does

- **Persistent memory** — your background, skills, target companies, and STAR stories persist across every session without re-explaining
- **Content ingestion** — paste a URL, upload a file, or transcribe a course and Futuro distills the key insights into your search strategy
- **Story bank** — STAR stories indexed by behavioral theme, semantically searchable, ready for any BQ question
- **Resume versioning** — tailored resume variants per company, diff-tracked over time
- **BQ coaching** — semantic match between question and your best story, structured feedback, simulated follow-up
- **Interview debrief** — structured post-interview capture, pattern detection across companies
- **Company pipeline** — visual tracker from research to offer, with timeline and activity log
- **Weekly strategy review** — checks your campaign against your stated goals and surfaces what to change

---

## Tech stack

| Layer | Choice |
|---|---|
| Backend | FastAPI (Python 3.12) |
| Frontend | Next.js 14 (TypeScript) |
| LLM | Anthropic Claude API (streaming) |
| Structured storage | SQLite via SQLAlchemy |
| Memory files | Markdown (git-tracked) |
| Vector search | ChromaDB (local) |
| Auth | Single-user JWT |
| Container | Docker + docker-compose |

---

## Project structure

```
futuro/
├── README.md
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
│   │   ├── api/
│   │   │   ├── chat.py
│   │   │   ├── memory.py
│   │   │   ├── campaign.py
│   │   │   ├── stories.py
│   │   │   ├── intake.py
│   │   │   ├── resume.py
│   │   │   └── interviews.py
│   │   ├── agents/
│   │   │   ├── core.py
│   │   │   ├── intake_agent.py
│   │   │   ├── story_crafter.py
│   │   │   ├── resume_editor.py
│   │   │   ├── bq_coach.py
│   │   │   ├── debrief_agent.py
│   │   │   └── strategy_agent.py
│   │   ├── memory/
│   │   │   ├── manager.py
│   │   │   ├── vector_store.py
│   │   │   └── markdown_io.py
│   │   └── models/
│   │       ├── campaign.py
│   │       └── interview.py
│   ├── data/
│   │   ├── memory/           # Markdown memory files (git-tracked)
│   │   ├── uploads/          # Ingested files (gitignored)
│   │   └── chroma/           # ChromaDB local store (gitignored)
│   ├── tests/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── alembic/              # DB migrations
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   └── lib/
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── docker-compose.prod.yml
├── .env.example
├── .gitignore
└── Makefile
```

---

## Quick start

```bash
git clone https://github.com/your-username/futuro.git
cd futuro
cp .env.example .env           # Add your ANTHROPIC_API_KEY
make dev                        # Starts backend + frontend
```

Open http://localhost:3000. Run onboarding. Start your search.

See `docs/DEV_SETUP.md` for full setup instructions.

---

## Design principles

1. **You own it** — code, data, and memory live on your machine
2. **Human-readable state** — all memory is markdown. You can edit it directly, git blame it, and carry it to any future system
3. **Warm by design** — encouragement and emotional intelligence are not bolt-ons; they're in the agent architecture
4. **Goal-oriented, not task-oriented** — every action connects back to your target role
5. **Incrementally deployable** — works offline with SQLite and local ChromaDB; cloud deployment is optional

---

## License

MIT
