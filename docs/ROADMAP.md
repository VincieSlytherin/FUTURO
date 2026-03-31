# Roadmap

Phased development plan. Each phase produces something usable. Never a long pause before value.

---

## Phase 0 — Foundation (Week 1–2)
**Goal:** The project exists, runs, and has a working skeleton.

**Backend:**
- [ ] FastAPI project initialized with `app/main.py`, config, and deps
- [ ] Auth endpoint (`POST /api/auth/login`)
- [ ] Database: SQLAlchemy models for `companies`, `company_events`, `interviews`
- [ ] Alembic migration: initial schema
- [ ] Memory: `MemoryManager` with `read_markdown`, `write_section`, `git_commit`
- [ ] `GET /api/memory/{filename}` and `PUT /api/memory/{filename}`
- [ ] Health check endpoint: `GET /api/health`

**Frontend:**
- [ ] Next.js app scaffolded with Tailwind + shadcn/ui
- [ ] Login page
- [ ] Sidebar navigation shell (empty pages for each section)
- [ ] Memory editor page (raw markdown view + edit)

**Infra:**
- [ ] `docker-compose.yml` for local dev (backend + frontend)
- [ ] `Makefile` with `setup`, `dev`, `test`, `migrate`
- [ ] `.env.example` with all variables documented
- [ ] `make setup` script working end-to-end
- [ ] Git repo initialized with `.gitignore` and initial commit

**Milestone:** `make setup && make dev` works. You can log in, view and edit memory files. The data directory structure is correct.

---

## Phase 1 — Core Chat (Week 3–4)
**Goal:** Futuro talks to you with memory. This is the heart of the project.

**Backend:**
- [ ] `BaseAgent` class with context loading and streaming
- [ ] `CoreAgent` — Futuro's base persona (GENERAL intent)
- [ ] `IntentClassifier` — lightweight routing call
- [ ] `AgentRouter`
- [ ] `POST /api/chat` — SSE streaming endpoint
- [ ] Memory context loading: L0 + L1 always, agent-specific on demand
- [ ] `MemoryUpdate` proposal extraction from agent `post_process()`
- [ ] `POST /api/memory/{file}/apply-update`

**Frontend:**
- [ ] Chat page with `ChatWindow` component
- [ ] SSE streaming: tokens appear in real-time
- [ ] `MessageBubble` — user vs Futuro visual distinction
- [ ] `MemoryUpdateCard` — Accept / Skip for proposed updates
- [ ] Intent badge (which agent is active)
- [ ] Message input with keyboard shortcuts

**Milestone:** Full conversation with Futuro. It reads L0 and L1, responds with warmth and context, and proposes memory updates. The core loop works.

---

## Phase 2 — Stories + BQ (Week 5–6)
**Goal:** Your STAR stories are in the system and you can practice with them.

**Backend:**
- [ ] `StoryBuilderAgent` (STORY intent)
- [ ] `BQCoachAgent` (BQ intent)
- [ ] `ChromaDB` integration: `StoryVectorStore` class
- [ ] Story indexing: index on `apply-update` when file is `stories_bank.md`
- [ ] `POST /api/stories/search` (semantic search)
- [ ] `GET /api/stories`, `POST /api/stories`
- [ ] `POST /api/stories/rebuild-index`
- [ ] `make rebuild-index` Makefile target

**Frontend:**
- [ ] Stories page: filterable list with theme chips
- [ ] Semantic search with debounce
- [ ] `StoryEditor` — structured STAR form
- [ ] [Practice] button → chat with story context prefilled
- [ ] `StoryCard` with quick-view and theme tags

**Milestone:** All three signature projects are in the story bank. You can ask "give me a question about ambiguity" and Futuro surfaces STORY-001, coaches your delivery, and asks follow-up questions.

---

## Phase 3 — Campaign Tracker (Week 7–8)
**Goal:** Your company pipeline lives in the app. No more spreadsheet.

**Backend:**
- [ ] Full CRUD for `companies` and `company_events`
- [ ] `PATCH /api/campaign/companies/{id}/stage` — auto-creates event
- [ ] `GET /api/campaign/stats`
- [ ] `AgentRouter`: integrate campaign data into `StrategyReviewAgent` context

**Frontend:**
- [ ] Campaign page: kanban board
- [ ] `PipelineBoard` with drag-to-drop stage updates
- [ ] `CompanyCard` with priority, stage duration, next step
- [ ] `CompanyDetailDrawer` — full company view + activity timeline
- [ ] Stats bar (response rate, stage distribution)
- [ ] [+ Add Company] modal

**Milestone:** Every company you're tracking is in the board. You drag Schwab from TECHNICAL to ONSITE and it logs the event automatically.

---

## Phase 4 — Intake + Resume (Week 9–10)
**Goal:** Content goes in, intelligence comes out. Resume is versioned.

**Backend:**
- [ ] `IntakeAgent` (INTAKE intent)
- [ ] `POST /api/intake/url` — fetch + distill
- [ ] `POST /api/intake/file` — PDF/DOCX extraction (PyPDF2 + python-docx)
- [ ] `POST /api/intake/text`
- [ ] `ResumeEditorAgent` (RESUME intent)
- [ ] `GET /api/resume/versions`, `POST /api/resume/versions`
- [ ] `GET /api/resume/versions/{version}/diff`
- [ ] `POST /api/resume/tailor`

**Frontend:**
- [ ] Resume page: version list + current bullets display
- [ ] Version diff view (side-by-side)
- [ ] [Tailor for new JD] modal → streaming suggestions

**Milestone:** Paste a job description URL → Intake agent distills it into L2 → Resume agent tailors your bullets for the role → new version saved with diff.

---

## Phase 5 — Interviews + Gmail (Week 11–12)
**Goal:** Every interview is logged. Gmail keeps the tracker updated.

**Backend:**
- [ ] `DebriefAgent` (DEBRIEF intent)
- [ ] `POST /api/interviews`, `POST /api/interviews/{id}/debrief`
- [ ] `GET /api/interviews/patterns`
- [ ] Gmail OAuth2 integration (read-only)
  - Scan for emails matching tracked company names
  - Auto-propose L1 + campaign status updates
  - Weekly digest: "You have 3 open applications with no response in 14+ days"
- [ ] Google Calendar integration
  - Detect interview-related events
  - Auto-create interview records

**Frontend:**
- [ ] Interviews page: Scheduled + Log tabs
- [ ] Debrief form (structured, linked to existing interview)
- [ ] Pattern summary view

**Milestone:** Come home from an interview, open Futuro, tap [Add Debrief], fill in 5 fields. Futuro gives you a genuine analysis, updates the tracker, and tells you what to prep for next time.

---

## Phase 6 — Strategy + Polish (Week 13–14)
**Goal:** The weekly review is a real ritual. The app feels finished.

**Backend:**
- [ ] `StrategyReviewAgent` (STRATEGY intent) — full implementation
- [ ] Session logging (`sessions` SQLite table)
- [ ] Streak tracking: days with at least one Futuro session

**Frontend:**
- [ ] Strategy review trigger: "Weekly review" shortcut in sidebar
- [ ] Memory git log view on `/memory` page
- [ ] Onboarding flow: detect empty L0, trigger conversation-based setup
- [ ] Mobile layout: bottom tab bar
- [ ] Error states: connection lost, API error, streaming failure
- [ ] Settings page: change password, API key status, model selection

**Milestone:** The app is production-quality. Onboarding works end-to-end. Every page handles errors gracefully. Weekly review is a one-click ritual.

---

## Backlog (post-v1)

- **Voice mode:** record a debrief by speaking rather than typing
- **Multi-device sync:** encrypted sync of memory repo to a private remote
- **Company research:** auto-pull Glassdoor sentiment, recent news for tracked companies
- **Offer comparison:** structured tool for comparing multiple offers
- **Export:** generate a clean PDF summary of your search (applications, interviews, learnings)
- **Notifications:** email or push digest ("You have an interview in 2 days — let's prep")
- **Prompt versioning:** track prompt changes in git alongside memory files
- **Multiple users:** if ever shared with a partner, friend, or turned into a small product

---

## Definition of done (per feature)

A feature is done when:
1. Backend: endpoint works, returns correct data, handles errors
2. Frontend: page/component is interactive, responsive, handles loading and error states
3. Tests: critical paths have coverage (not 100%, but the happy path and main error case)
4. Docs: if the feature changes the API or data model, the relevant doc is updated
5. Used: it's been used at least once in a real job search session

---

## Phase 7 — Job Scout (complete, delivered in v3)

The automated job discovery system. Merged into the project as a complete, tested feature.

**Backend:**
- [x] `ScoutConfig`, `ScoutRun`, `JobListing` SQLAlchemy models
- [x] `app/agents/job_scout.py` — scraping (python-jobspy) + Claude scoring engine
- [x] `app/workers/job_monitor.py` — APScheduler background monitor
- [x] `app/api/scout.py` — full REST API (configs, runs, listings, actions, stats)
- [x] `app/agents/prompts/job_scout.md` — agent prompt for chat integration
- [x] SCOUT intent wired into `AgentRouter`
- [x] `backend/tests/test_scout.py` — 15 tests (unit + integration)

**Frontend:**
- [x] `/jobs` page — scored listing feed, tabs, score filter, pagination
- [x] Scout config panel — create/pause/delete/run configs
- [x] Job cards — score badge, pros/cons, H-1B pill, salary, expand/collapse
- [x] Actions — Save, Dismiss, Add to Pipeline, Mark Applied
- [x] One-click pipeline integration (creates Company in campaign Kanban)
- [x] Jobs added to sidebar nav

**Docs:**
- [x] `docs/SCOUT_AGENT.md` — architecture, scoring rubric, API ref, troubleshooting

**Backlog (post-v3):**
- [ ] Email notifications when high-score jobs arrive
- [ ] Company research overlay (Glassdoor rating, recent news) on job cards
- [ ] Outreach template generator from a job listing + company info
- [ ] "Apply for me" draft — generates tailored cover letter and resume from listing
- [ ] Chrome extension: save any job listing from any site to Futuro with one click
