# Tech Stack — Decision Records

Each decision is documented as a lightweight ADR (Architecture Decision Record): context, decision, rationale, tradeoffs.

---

## ADR-001: Python for backend

**Decision:** FastAPI (Python 3.12)

**Context:** The developer's primary language is Python, with production experience in LangChain, LangGraph, AWS Bedrock, and Streamlit. This is a solo side project.

**Rationale:**
- FastAPI is the fastest Python web framework for building async APIs; native support for streaming responses (critical for LLM output)
- Python has the best LLM ecosystem: Anthropic SDK, LangChain, ChromaDB all have first-class Python clients
- No context-switching cost; every hour of work goes into the product, not learning a new language
- Pydantic v2 (built into FastAPI) gives strong data validation with minimal boilerplate

**Tradeoffs:**
- Not as performant as Go or Rust for raw throughput — acceptable for a single-user personal tool
- Python's async story is messier than Node.js's — mitigated by FastAPI's design

**Rejected alternatives:**
- Node.js/Express: worse LLM ecosystem, added language switch
- Django: too much overhead for an API-first app

---

## ADR-002: Next.js 14 for frontend

**Decision:** Next.js 14 with TypeScript, App Router

**Context:** This is a real side project meant to be used daily and potentially shown in a portfolio. It should look and feel like real software, not a Streamlit prototype.

**Rationale:**
- App Router + React Server Components gives a clean mental model for data fetching
- TypeScript gives type safety across the entire frontend, catching bugs during development
- Next.js supports streaming UI natively — critical for displaying LLM output as it streams
- Tailwind CSS for styling; shadcn/ui for component primitives — minimal setup, professional output
- Strong portfolio signal: full-stack Python + TypeScript is a valuable combination to demonstrate

**Tradeoffs:**
- Higher initial complexity than Streamlit
- Build tooling overhead (webpack/turbo)

**Migration path from Streamlit:** If rapid prototyping is needed first, an optional `streamlit/` folder can serve as a Phase 0 interface while Next.js is built.

**Rejected alternatives:**
- Streamlit: faster to build, but limited layout control, poor mobile, limited streaming UX — acceptable as Phase 0 only
- SvelteKit: smaller ecosystem, less relevant for portfolio
- Raw React (CRA): no SSR, no built-in routing

---

## ADR-003: Anthropic Claude API (direct)

**Decision:** Use the Anthropic Python SDK against `api.anthropic.com` directly, not via AWS Bedrock

**Context:** Developer uses AWS Bedrock at work. For a personal side project, the tradeoffs are different.

**Rationale:**
- Direct API is simpler: one credential (API key in `.env`), no AWS IAM setup, no Bedrock provisioned throughput configuration
- Anthropic releases new models to the direct API first — personal project benefits from latest capabilities
- `claude-sonnet-4-5` via direct API has lower latency than Bedrock for interactive use
- Cost: direct API pricing is equivalent to Bedrock; no additional overhead for personal volumes

**Streaming:** All chat endpoints use `anthropic.messages.stream()` with Server-Sent Events (SSE) to the frontend. Token-by-token streaming is non-negotiable for interactive feel.

**Model selection:**
- Default: `claude-sonnet-4-5` — best balance of quality and speed for interactive sessions
- Long-form tasks (full resume rewrite, deep strategy review): allow override to `claude-opus-4-5`
- Stored in config, never hardcoded in agent files

**Rejected alternatives:**
- AWS Bedrock: works but adds IAM complexity; keep for work, use direct API for personal
- OpenAI: no strong reason to switch when the developer already works daily with Claude
- Local models (Ollama): quality gap too large for the nuanced judgment these agents require

---

## ADR-004: SQLite for structured storage

**Decision:** SQLite via SQLAlchemy ORM, with Alembic for migrations

**Context:** Structured data (company applications, interview events, activity logs) needs reliable querying and relationship integrity. The app is single-user, local-first.

**Rationale:**
- SQLite requires zero infrastructure — the database is a single file
- For one user, SQLite's write throughput is more than sufficient
- SQLAlchemy ORM means the schema is version-controlled code, not a manual database setup
- Alembic migrations mean schema changes are safe and reversible
- The database file lives in `backend/data/futuro.db` — it can be backed up with `cp`

**Rejected alternatives:**
- PostgreSQL: unnecessary complexity for single-user; requires running a separate process
- MongoDB: structured data (campaign pipeline, interview events) benefits from relational model
- Raw SQL: SQLAlchemy adds minimal overhead and makes models readable

---

## ADR-005: Markdown files for unstructured memory

**Decision:** Memory layers L0 (identity), L2 (knowledge), stories bank, and resume versions are stored as markdown files in `backend/data/memory/`, tracked by git

**Context:** The memory system is the most important part of Futuro. It needs to be trustworthy, transparent, and portable.

**Rationale:**
- Human-readable: the user can open any memory file and read or edit it directly
- Git-tracked: every update is a commit; full history, full rollback
- Portable: if Futuro is ever replaced, the memory migrates to any other system
- Transparent: the user knows exactly what the AI "knows" about them
- No vendor lock-in: no proprietary format, no third-party service dependency

**Update flow:** Agents propose memory updates at the end of sessions. The `MemoryManager` class writes the markdown, stages the change, and commits with a descriptive message (`git commit -m "update L1: Schwab moved to final round"`).

**Rejected alternatives:**
- Database storage for all memory: loses human readability and portability
- mem0/Supermemory: third-party service dependency; privacy risk; lock-in
- JSON files: harder to read and edit than markdown; no native rendering

---

## ADR-006: ChromaDB for vector search

**Decision:** ChromaDB running locally (persistent mode, not in-memory)

**Context:** The stories bank will grow to 10–50+ stories. Matching a BQ question to the right story semantically is much more reliable than keyword search or reading the full file.

**Rationale:**
- ChromaDB runs locally with zero infrastructure (embedded Python library)
- Persistent mode stores the index on disk (`backend/data/chroma/`) — survives restarts
- Simple Python API; integrates cleanly with the existing FastAPI backend
- The vector index is derived from markdown files — always rebuildable from source

**Index strategy:**
- Each story in `stories_bank.md` gets its own ChromaDB document
- Embedding: `text-embedding-3-small` (OpenAI) or Anthropic's embedding model when available
- At query time (BQ coaching): embed the question → retrieve top-3 story matches → agent selects best
- Rebuild index: `POST /api/stories/rebuild-index` (or `make rebuild-index`)

**What's NOT in the vector store:**
- L0 identity (always fully read — small and stable)
- L1 campaign (always fully read — structured data is in SQLite)
- The vector store is an acceleration layer, not the source of truth

**Rejected alternatives:**
- Pinecone/Weaviate: cloud services; privacy concern; unnecessary for local use
- pgvector: would require PostgreSQL
- FAISS: lower-level; ChromaDB provides a better developer experience with minimal overhead

---

## ADR-007: Single-user JWT auth

**Decision:** Single-user authentication via a setup-time password, stored as a bcrypt hash, issuing a JWT on login

**Context:** Futuro is a personal tool. It doesn't need multi-user accounts. It does need to be safe to deploy to a cloud server without being open to the internet.

**Rationale:**
- Simple: one password set at `make setup`, one JWT secret in `.env`
- Stateless: JWT means no session store needed
- Sufficient: the threat model is "someone stumbles onto my Fly.io URL" — a password gate is enough

**Implementation:**
- `POST /api/auth/login` — validates password, returns JWT (7-day expiry)
- All other endpoints: `Authorization: Bearer <token>` required
- Frontend stores JWT in an httpOnly cookie (not localStorage)
- JWT secret: 256-bit random string generated at `make setup`

**Rejected alternatives:**
- OAuth/SSO: massive overkill for a single-user personal tool
- API key header only: fine for CLI usage, less natural for a web app
- No auth: acceptable for fully local use; required if deploying to cloud

---

## ADR-008: Docker for packaging

**Decision:** Docker + docker-compose for development and deployment

**Context:** The project has two services (backend, frontend) and needs to work consistently across environments.

**Rationale:**
- `docker-compose up` starts everything with one command
- Consistent environment between developer's machine and cloud deployment
- Separate `docker-compose.prod.yml` for production (no hot-reload, environment-specific settings)
- Each service has its own Dockerfile; the backend mounts `data/` as a volume so state persists

**Development vs production:**
- Dev: hot reload enabled, `data/` mounted directly, no TLS
- Prod: multi-stage builds, `data/` on a persistent volume, Nginx reverse proxy with TLS termination

---

## ADR-009: Makefile for developer UX

**Decision:** A root-level `Makefile` with common commands

**Context:** The project has multiple services, setup steps, and operational commands. These should be one command, not documented multi-step procedures.

**Targets:**
```makefile
make setup          # First-time setup: create .env, generate secrets, run migrations
make dev            # Start backend + frontend in development mode
make test           # Run backend tests
make migrate        # Run Alembic migrations
make rebuild-index  # Rebuild ChromaDB vector index from markdown files
make backup         # Backup data/ directory with timestamp
make deploy         # Deploy to Fly.io (requires fly CLI)
make logs           # Tail logs from all services
```
