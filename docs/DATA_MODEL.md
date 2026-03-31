# Data Model

Two storage backends: **SQLite** (structured, relational) and **Markdown files** (unstructured, human-readable). Together they cover all of Futuro's memory.

---

## SQLite schema

### `companies` table

The core of the campaign tracker. One row per company the user is tracking.

```sql
CREATE TABLE companies (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    role_title      TEXT NOT NULL,
    url             TEXT,                     -- Job posting URL
    stage           TEXT NOT NULL DEFAULT 'RESEARCHING',
                    -- RESEARCHING | APPLIED | SCREENING | TECHNICAL
                    -- ONSITE | OFFER | CLOSED_WON | CLOSED_LOST | WITHDREW
    priority        TEXT NOT NULL DEFAULT 'MEDIUM',
                    -- HIGH | MEDIUM | LOW
    notes           TEXT,                     -- Freeform notes
    sponsorship_confirmed BOOLEAN DEFAULT FALSE,
    salary_range    TEXT,                     -- "180k-220k + equity"
    source          TEXT,                     -- Where I found it
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    applied_at      DATETIME,
    closed_at       DATETIME
);
```

### `company_events` table

Timeline of everything that has happened with a company. Enables the activity timeline view.

```sql
CREATE TABLE company_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id      INTEGER NOT NULL REFERENCES companies(id),
    event_type      TEXT NOT NULL,
                    -- APPLIED | EMAIL_SENT | EMAIL_RECEIVED | SCREEN_SCHEDULED
                    -- SCREEN_DONE | TECHNICAL_SCHEDULED | TECHNICAL_DONE
                    -- ONSITE_SCHEDULED | ONSITE_DONE | OFFER_RECEIVED
                    -- REJECTED | WITHDREW | NOTE
    description     TEXT,
    stage_from      TEXT,
    stage_to        TEXT,
    happened_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### `interviews` table

Detailed record for each interview session. Linked to a company event.

```sql
CREATE TABLE interviews (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id      INTEGER NOT NULL REFERENCES companies(id),
    event_id        INTEGER REFERENCES company_events(id),
    round_name      TEXT NOT NULL,             -- "Phone screen", "System design", "Onsite Day 1"
    interviewer     TEXT,
    format          TEXT,                      -- "Technical" | "Behavioral" | "Case" | "Mixed"
    duration_min    INTEGER,
    questions_asked TEXT,                      -- JSON array of question strings
    my_answers      TEXT,                      -- Freeform notes on how I answered
    strong_moments  TEXT,                      -- What landed well
    weak_moments    TEXT,                      -- What to improve
    gut_feeling     INTEGER,                   -- 1–5 subjective rating
    next_steps      TEXT,
    scheduled_at    DATETIME,
    happened_at     DATETIME,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### `outreach` table

Track networking outreach separately from applications.

```sql
CREATE TABLE outreach (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    person_name     TEXT NOT NULL,
    company         TEXT,
    connection_type TEXT,                      -- "1st" | "Alumni" | "Cold" | "Referral"
    platform        TEXT,                      -- "LinkedIn" | "Email" | "Twitter" | "Event"
    message_sent    TEXT,
    response        TEXT,                      -- NULL = no response yet
    status          TEXT DEFAULT 'SENT',       -- SENT | RESPONDED | MEETING_SET | STALLED | CLOSED
    notes           TEXT,
    sent_at         DATETIME,
    responded_at    DATETIME,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### `sessions` table

Log of Futuro sessions — used for streak tracking and strategy review.

```sql
CREATE TABLE sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    intent          TEXT NOT NULL,             -- Agent type used
    summary         TEXT,                      -- 1–2 sentence summary of what was done
    memory_updates  TEXT,                      -- JSON list of files updated
    mood_score      INTEGER,                   -- 1–5, user's reported state
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## Alembic migration convention

```
backend/alembic/
├── env.py
├── script.py.mako
└── versions/
    ├── 001_initial_schema.py
    ├── 002_add_outreach_table.py
    └── ...
```

Each migration is numbered sequentially. Naming convention: `{NNN}_{description}.py`.

---

## Markdown memory files

Located in `backend/data/memory/`. All files are plain markdown tracked in a private git repo. The schema here describes the *logical structure* that agents expect — actual formatting is markdown.

### `L0_identity.md`

Updated rarely. Contains the stable facts about who the user is.

```
Sections:
- ## Who I am        (name, location, personality)
- ## Career narrative (3–4 sentence pitch)
- ## Target role     (title, locations, company type, constraints, timeline)
- ## Technical skills (core stack, supporting, familiar)
- ## Signature projects (2–3 key projects with impact)
- ## Strengths I own
- ## Areas developing
- ## What I need from Futuro
```

**Size target:** 400–600 words. If longer, it has drifted — prune.

### `L1_campaign.md`

Updated every session. A narrative + structured summary of the current search state.

```
Sections:
- ## Status snapshot   (table: metric → value)
- ## Weekly focus      (top 3 priorities, blockers, what's working)
- ## Mindset check     (optional: energy level, what's weighing on me, proud of)
- ## Strategy notes    (running log of observations and decisions)
```

Note: Company-level detail lives in SQLite (`companies`, `company_events`). L1 is the narrative layer — the "why things are the way they are" — not the data layer.

### `L2_knowledge.md`

Grows over time as content is ingested and strategy is refined.

```
Sections:
- ## Job search strategy (current operating model and thesis)
- ## Sourcing channels   (what's worked / hasn't)
- ## Market intelligence (role market, company notes, comp intel)
- ## Interview prep learnings (patterns across companies)
- ## Insights from content (per-source summaries with dates)
- ## Strategy iteration log (table: date, experiment, result, keep/change)
- ## Reference frameworks (STAR, resume bullet formula, negotiation)
```

**Growth pattern:** New entries are always appended to the relevant section with `[DATE]` tags. Old entries are never deleted — they're part of the history.

### `stories_bank.md`

The central asset of interview prep. Indexed by ChromaDB for semantic search.

```
Header section:
- ## Quick-reference index  (theme → story IDs)

Per story:
- ## STORY-{NNN} · {Title}
- **Themes:** comma-separated list
- **The one-liner:** single sentence
- **STAR:** Situation / Task / Action / Result
- **Short version (30 seconds):** for quick delivery
- **Common follow-ups + answers:** 2–3 anticipated follow-ups
```

**Story ID convention:** `STORY-001`, `STORY-002`, ... Sequential, never reused. When a story is retired, it's marked `[ARCHIVED]` not deleted.

**Theme taxonomy (standard set):**
- Impact / measurable results
- Ambiguity / working without clear direction
- Technical problem-solving
- Innovation / doing something new
- Leadership / influencing without authority
- Cross-functional collaboration
- Conflict / disagreement
- Failure / learning from mistakes
- Prioritization / tradeoffs
- Working under constraints
- Fast learning / picking up new skills

### `resume_versions.md`

```
Header:
- ## Current version: vX.X
- Current bullets (for fast reference and editing)

Per version:
- ## Version vX.X — {DATE}
- Tailored for: ...
- Key changes: ...
- Emphasis: ...
- Applied to: ...
- Result: ...

Footer:
- ## Tailoring strategy (notes by company type)
- ## ATS keywords
```

### `interview_log.md`

Complements the SQLite `interviews` table. The SQLite record has structured fields; the markdown file has narrative notes per company.

```
Per company section:
- ## {Company} — {Role}
- Stage, last updated
- Round table (structured)
- Key things I noticed
- What I would do differently
- One thing I did well

Footer:
- ## Cross-company patterns
- Questions that keep coming up
- What interviewers care about
- My blind spots (updated as I discover them)
```

---

## ChromaDB document schema

Each story in `stories_bank.md` is indexed as a ChromaDB document.

```python
{
    "id": "STORY-001",
    "document": "{one_liner}\n\n{situation}\n\n{action}\n\n{result}",
    "metadata": {
        "story_id": "STORY-001",
        "title": "Multimodal RAG Pipeline",
        "themes": ["impact", "technical-problem-solving", "ambiguity"],
        "has_numbers": True,
        "result_metric": "70% reduction in manual review",
        "archived": False
    }
}
```

**Query response:**
```python
{
    "story_id": "STORY-001",
    "title": "Multimodal RAG Pipeline",
    "distance": 0.23,          # Lower = more similar
    "themes": [...],
    "one_liner": "...",
    "result_metric": "..."
}
```

---

## Pydantic models (key request/response types)

```python
# Campaign
class CompanyCreate(BaseModel):
    name: str
    role_title: str
    url: str | None
    priority: Literal["HIGH", "MEDIUM", "LOW"] = "MEDIUM"
    notes: str | None

class CompanyUpdate(BaseModel):
    stage: str | None
    notes: str | None
    salary_range: str | None

class CompanyResponse(BaseModel):
    id: int
    name: str
    role_title: str
    stage: str
    priority: str
    events: list[CompanyEventResponse]
    updated_at: datetime

# Chat
class ChatRequest(BaseModel):
    message: str
    history: list[Message]
    session_id: str | None

class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str

# Memory update
class MemoryUpdate(BaseModel):
    file: str                  # e.g. "L1_campaign.md"
    section: str               # Section header to update
    action: Literal["append", "replace", "create"]
    content: str
    reason: str                # Why this update is being proposed

# Story search
class StorySearchRequest(BaseModel):
    query: str                 # BQ question or theme
    n_results: int = 3

class StorySearchResult(BaseModel):
    story_id: str
    title: str
    one_liner: str
    themes: list[str]
    distance: float
    result_metric: str | None
```
