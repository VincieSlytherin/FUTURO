# API Specification

Base URL: `http://localhost:8000` (dev) / `https://your-domain.com` (prod)

All endpoints except `/api/auth/login` require:
```
Authorization: Bearer <jwt_token>
```

---

## Authentication

### `POST /api/auth/login`
```json
Request:
{ "password": "your_password" }

Response 200:
{ "access_token": "eyJ...", "token_type": "bearer" }

Response 401:
{ "detail": "Invalid password" }
```

---

## Chat

### `POST /api/chat`

Primary endpoint. Classifies intent, loads memory context, streams response via SSE.

```
Content-Type: application/json
Accept: text/event-stream
```

**Request:**
```json
{
  "message": "Help me prep for the BQ question about a time I handled ambiguity",
  "history": [
    { "role": "user", "content": "Hey Futuro" },
    { "role": "assistant", "content": "Hey! How are you holding up today?..." }
  ],
  "session_id": "uuid-optional"
}
```

**SSE stream events:**
```
event: intent
data: {"intent": "BQ", "agent": "BQ Coach"}

event: token
data: {"text": "Let"}

event: token
data: {"text": " me"}

...

event: complete
data: {
  "full_response": "...",
  "proposed_updates": [
    {
      "file": "stories_bank.md",
      "section": "STORY-002",
      "action": "append",
      "content": "...",
      "reason": "New follow-up Q&A added during BQ prep"
    }
  ]
}
```

**Intent values:** `INTAKE | STORY | RESUME | BQ | DEBRIEF | STRATEGY | GENERAL`

---

## Memory

### `GET /api/memory/{filename}`

Read a memory file.

```
filename: L0_identity | L1_campaign | L2_knowledge | stories_bank | resume_versions | interview_log

Response 200:
{
  "filename": "L0_identity.md",
  "content": "# L0 · Core Identity\n...",
  "last_modified": "2026-03-28T14:23:00Z",
  "last_commit": "update L0: added new project to signature projects"
}
```

### `PUT /api/memory/{filename}`

Full file replace. Used when user edits a memory file directly in the UI.

```json
Request:
{ "content": "# L0 · Core Identity\n..." }

Response 200:
{ "committed": true, "commit_message": "manual edit: L0_identity.md" }
```

### `POST /api/memory/{filename}/apply-update`

Apply a proposed memory update (from chat's `proposed_updates` list).

```json
Request:
{
  "section": "STORY-002",
  "action": "append",
  "content": "**New follow-up:** ...",
  "reason": "Added during BQ prep"
}

Response 200:
{ "committed": true, "commit_message": "update stories_bank: STORY-002 follow-up" }
```

### `GET /api/memory/git-log`

Recent git history for memory files.

```json
Response 200:
{
  "commits": [
    {
      "hash": "a3f9c12",
      "message": "update L1: Schwab moved to final round",
      "timestamp": "2026-03-28T14:23:00Z",
      "files_changed": ["L1_campaign.md"]
    }
  ]
}
```

---

## Campaign

### `GET /api/campaign/companies`

All tracked companies with current stage.

```
Query params:
  stage: filter by stage (optional)
  priority: filter by priority (optional)

Response 200:
{
  "companies": [
    {
      "id": 1,
      "name": "Anthropic",
      "role_title": "AI Engineer",
      "stage": "TECHNICAL",
      "priority": "HIGH",
      "sponsorship_confirmed": true,
      "updated_at": "2026-03-28T...",
      "days_since_applied": 12
    }
  ]
}
```

### `POST /api/campaign/companies`

Add a new company.

```json
Request:
{
  "name": "Anthropic",
  "role_title": "AI Engineer",
  "url": "https://anthropic.com/careers/...",
  "priority": "HIGH",
  "notes": "ML team, focus on applied systems"
}

Response 201:
{ "id": 42, ...company }
```

### `PATCH /api/campaign/companies/{id}/stage`

Update pipeline stage. Also creates a `company_events` row automatically.

```json
Request:
{
  "stage": "TECHNICAL",
  "description": "Received technical screen invite from recruiter"
}

Response 200:
{ ...updated_company, "event_created": true }
```

### `POST /api/campaign/companies/{id}/events`

Manually log an event.

```json
Request:
{
  "event_type": "EMAIL_SENT",
  "description": "Sent thank you note to hiring manager",
  "happened_at": "2026-03-28T16:00:00Z"
}
```

### `GET /api/campaign/stats`

Aggregated pipeline stats.

```json
Response 200:
{
  "total_active": 8,
  "by_stage": {
    "RESEARCHING": 2,
    "APPLIED": 3,
    "SCREENING": 1,
    "TECHNICAL": 1,
    "ONSITE": 1
  },
  "response_rate": 0.62,
  "avg_days_to_response": 11,
  "offers": 0,
  "closed_last_30d": 2
}
```

---

## Stories

### `GET /api/stories`

All stories, optionally filtered by theme.

```
Query params:
  theme: behavioral theme slug (optional)
  include_archived: bool (default false)
```

### `POST /api/stories/search`

Semantic search over story bank.

```json
Request:
{
  "query": "Tell me about a time you worked with ambiguous requirements",
  "n_results": 3
}

Response 200:
{
  "results": [
    {
      "story_id": "STORY-001",
      "title": "Multimodal RAG Pipeline",
      "one_liner": "Built a production RAG system from scratch with no clear playbook, cutting manual review by ~70%",
      "themes": ["ambiguity", "technical-problem-solving", "impact"],
      "distance": 0.18,
      "result_metric": "~70% reduction in manual review"
    }
  ]
}
```

### `POST /api/stories`

Add a new story.

```json
Request:
{
  "title": "Led Migration to New Data Platform",
  "themes": ["leadership", "technical-problem-solving"],
  "one_liner": "...",
  "situation": "...",
  "task": "...",
  "action": "...",
  "result": "...",
  "short_version": "...",
  "follow_ups": [
    { "question": "How did you handle pushback?", "answer": "..." }
  ]
}

Response 201:
{ "story_id": "STORY-004", "index_updated": true }
```

### `POST /api/stories/rebuild-index`

Rebuild the ChromaDB vector index from `stories_bank.md`. Run after bulk edits.

```json
Response 200:
{ "stories_indexed": 4, "duration_ms": 1240 }
```

---

## Intake

### `POST /api/intake/url`

Fetch and distill a URL (article, post, job description, course page).

```json
Request:
{
  "url": "https://...",
  "intent": "STRATEGY_INTEL"
  // STRATEGY_INTEL | JOB_DESCRIPTION | COURSE_NOTES | MARKET_RESEARCH
}

Response 200 (streams SSE):
event: progress
data: { "step": "fetching" }

event: progress
data: { "step": "distilling" }

event: complete
data: {
  "title": "...",
  "summary": "...",
  "key_insights": ["...", "..."],
  "proposed_update": {
    "file": "L2_knowledge.md",
    "section": "Insights from content",
    "content": "### [Title — DATE]\n..."
  }
}
```

### `POST /api/intake/file`

Upload and process a file (PDF, DOCX, TXT, MD).

```
Content-Type: multipart/form-data

Fields:
  file: (binary)
  intent: STRATEGY_INTEL | JOB_DESCRIPTION | COURSE_NOTES
```

### `POST /api/intake/text`

Process freeform text (pasted notes, transcripts).

```json
Request:
{
  "text": "Here are my notes from the course on job searching...",
  "source": "IGotAnOffer course — System Design"
}
```

---

## Resume

### `GET /api/resume/versions`

All resume versions with metadata.

### `POST /api/resume/versions`

Create a new version. Takes the current version and a set of changes.

```json
Request:
{
  "based_on": "v1.0",
  "tailored_for": "Anthropic — AI Engineer",
  "changes": "Emphasized multi-agent work, moved RAG pipeline to top bullet"
}
```

### `GET /api/resume/versions/{version}/diff`

Show diff between two versions.

```
Query params:
  compare_to: version string (default: previous)
```

### `POST /api/resume/tailor`

Generate tailoring suggestions for a specific JD. Streams.

```json
Request:
{
  "jd_text": "We're looking for an AI Engineer with experience in...",
  "current_version": "v1.0"
}
```

---

## Interviews

### `POST /api/interviews`

Create a new interview record.

```json
Request:
{
  "company_id": 1,
  "round_name": "Technical Screen",
  "format": "Technical",
  "scheduled_at": "2026-04-02T14:00:00Z"
}
```

### `POST /api/interviews/{id}/debrief`

Capture post-interview debrief. Triggers the debrief agent.

```json
Request:
{
  "questions_asked": [
    "Walk me through your RAG pipeline architecture",
    "How did you handle the metadata filtering problem?"
  ],
  "strong_moments": "The architecture explanation landed well — they asked follow-ups",
  "weak_moments": "Stumbled on the scaling question",
  "gut_feeling": 4,
  "notes": "Team seemed collaborative, 4 people on the call"
}
```

Response streams SSE with the debrief agent's analysis and proposed memory updates.

### `GET /api/interviews/patterns`

Cross-company pattern analysis.

```json
Response 200:
{
  "common_questions": [
    { "question_pattern": "Ambiguity / unclear requirements", "count": 4 },
    { "question_pattern": "System design for scale", "count": 3 }
  ],
  "gap_areas": ["Conflict resolution stories", "Leadership of other engineers"],
  "strong_areas": ["Technical depth on RAG/LLM systems", "Impact quantification"]
}
```
