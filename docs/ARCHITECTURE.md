# System Architecture

---

## High-level overview

```
┌─────────────────────────────────────────────────────────┐
│                      Browser                            │
│                  Next.js 14 (TypeScript)                │
│         Chat UI · Campaign board · Story bank           │
└───────────────────────┬─────────────────────────────────┘
                        │ HTTPS / SSE streaming
┌───────────────────────▼─────────────────────────────────┐
│                  FastAPI Backend                        │
│                                                         │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │  API Layer  │  │ Agent Router │  │ Memory Manager│  │
│  └──────┬──────┘  └──────┬───────┘  └───────┬───────┘  │
│         │                │                   │          │
│  ┌──────▼──────────────────────────────────▼──────────┐ │
│  │                   Agent Core                       │ │
│  │  Intake · StoryBuilder · ResumeEditor · BQCoach   │ │
│  │  InterviewDebrief · StrategyReview                │ │
│  └──────────────────────┬────────────────────────────┘ │
│                         │ Anthropic SDK                 │
└─────────────────────────┼───────────────────────────────┘
                          │
              ┌───────────▼────────────┐
              │   Anthropic Claude API │
              │  claude-sonnet-4-5     │
              └────────────────────────┘

  Local storage (on-disk)
  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │   SQLite     │  │  Markdown    │  │  ChromaDB    │
  │  futuro.db   │  │  memory/     │  │  chroma/     │
  │              │  │  (git-track) │  │  (derived)   │
  │ Campaign     │  │ L0 identity  │  │ Story        │
  │ Companies    │  │ L2 knowledge │  │ embeddings   │
  │ Interviews   │  │ Stories bank │  │              │
  │ Activity     │  │ Resumes      │  │              │
  └──────────────┘  └──────────────┘  └──────────────┘
```

---

## Request lifecycle — chat message

```
User types message → POST /api/chat
        │
        ▼
   IntentClassifier.classify(message)
        │
        ├─ INTAKE    → IntakeAgent
        ├─ STORY     → StoryBuilderAgent
        ├─ RESUME    → ResumeEditorAgent
        ├─ BQ        → BQCoachAgent
        ├─ DEBRIEF   → DebriefAgent
        ├─ STRATEGY  → StrategyReviewAgent
        └─ GENERAL   → CoreAgent (Futuro's base persona)
        │
        ▼
   Agent.run(message, context)
        │
        ├── MemoryManager.load_context()
        │       ├── read L0_identity.md     (always)
        │       ├── read L1_campaign.md     (always)
        │       ├── fetch recent SQLite rows (campaign, interviews)
        │       └── read agent-specific memory (stories, resume, etc.)
        │
        ├── anthropic.messages.stream(
        │       model=config.model,
        │       system=agent.system_prompt,
        │       messages=[...context, user_message]
        │   )
        │
        └── SSE stream → frontend
                  │
                  ▼
           StreamHandler.on_complete()
                  │
                  └── MemoryManager.extract_and_stage_updates(response)
                          └── proposes changes, awaits user approval
```

---

## Component breakdown

### API Layer (`backend/app/api/`)

Each module is a FastAPI router mounted at its prefix.

| Module | Prefix | Responsibility |
|---|---|---|
| `chat.py` | `/api/chat` | Streaming chat endpoint, intent routing |
| `memory.py` | `/api/memory` | CRUD for markdown memory files |
| `campaign.py` | `/api/campaign` | Company pipeline, status updates |
| `stories.py` | `/api/stories` | Story CRUD, semantic search, index rebuild |
| `intake.py` | `/api/intake` | URL fetch, file processing, content distillation |
| `resume.py` | `/api/resume` | Resume version management, diff view |
| `interviews.py` | `/api/interviews` | Interview log, debrief capture |
| `auth.py` | `/api/auth` | Login, token refresh |

### Agent Router (`backend/app/agents/core.py`)

The router classifies intent from the user message and conversation history, then instantiates the appropriate agent.

```python
class IntentClassifier:
    INTENTS = ["INTAKE", "STORY", "RESUME", "BQ", "DEBRIEF", "STRATEGY", "GENERAL"]

    async def classify(self, message: str, history: list[Message]) -> str:
        # Uses a lightweight Claude call with a structured prompt
        # Returns one of the INTENTS above
        ...

class AgentRouter:
    AGENT_MAP = {
        "INTAKE": IntakeAgent,
        "STORY": StoryBuilderAgent,
        "RESUME": ResumeEditorAgent,
        "BQ": BQCoachAgent,
        "DEBRIEF": DebriefAgent,
        "STRATEGY": StrategyReviewAgent,
        "GENERAL": CoreAgent,
    }

    async def route(self, intent: str, context: AgentContext) -> BaseAgent:
        return self.AGENT_MAP[intent](context)
```

### Agent Base Class

```python
class BaseAgent:
    system_prompt: str          # Loaded from agents/prompts/{agent_name}.md
    memory_reads: list[str]     # Which memory files this agent needs
    memory_writes: list[str]    # Which memory files this agent may update

    async def run(
        self,
        message: str,
        context: AgentContext,
        history: list[Message]
    ) -> AsyncIterator[str]:    # SSE token stream
        ...

    async def post_process(
        self,
        response: str,
        context: AgentContext
    ) -> list[MemoryUpdate]:    # Proposed memory changes
        ...
```

### Memory Manager (`backend/app/memory/manager.py`)

Central interface for all memory reads and writes. Abstracts over markdown files, SQLite, and ChromaDB.

```python
class MemoryManager:
    async def load_context(self, agent_type: str) -> AgentContext:
        """Build the full context object for an agent."""
        ...

    async def read_markdown(self, filename: str) -> str:
        """Read a memory markdown file."""
        ...

    async def write_markdown(
        self,
        filename: str,
        section: str,
        content: str,
        commit_message: str
    ) -> None:
        """Update a section in a memory file and git commit."""
        ...

    async def propose_updates(
        self,
        updates: list[MemoryUpdate]
    ) -> list[MemoryUpdate]:
        """Return proposed updates for user review. Does not write yet."""
        ...

    async def apply_update(self, update: MemoryUpdate) -> None:
        """Apply an approved memory update and commit."""
        ...
```

### Vector Store (`backend/app/memory/vector_store.py`)

```python
class StoryVectorStore:
    collection_name = "futuro_stories"

    async def search(
        self,
        query: str,
        n_results: int = 3
    ) -> list[StoryMatch]:
        """Semantic search over story bank."""
        ...

    async def rebuild_index(self) -> None:
        """Parse stories_bank.md and rebuild the full ChromaDB collection."""
        ...

    async def add_story(self, story: Story) -> None:
        """Add a single story to the index."""
        ...
```

---

## Data flow — memory update cycle

```
Session conversation
        │
        ▼
Agent produces response
        │
        ▼
post_process() extracts proposed updates
  Example: "Schwab moved to final round" → L1_campaign.md update
           "New story about leading migration" → stories_bank.md entry
        │
        ▼
Frontend shows update cards: [Accept] [Edit] [Skip]
        │
        ├── Accept → MemoryManager.apply_update()
        │               ├── write markdown file
        │               ├── git add + commit
        │               └── (if story) ChromaDB.add_story()
        │
        ├── Edit → user edits in modal → Accept
        │
        └── Skip → discard
```

---

## Frontend component map

```
app/
├── (auth)/
│   └── login/page.tsx          # Single-user login
├── (app)/
│   ├── layout.tsx              # Sidebar nav + auth guard
│   ├── chat/page.tsx           # Main chat interface
│   ├── campaign/page.tsx       # Company pipeline board
│   ├── stories/page.tsx        # Story bank browser + search
│   ├── resume/page.tsx         # Resume versions + diff
│   ├── interviews/page.tsx     # Interview log + debrief entry
│   └── memory/page.tsx         # Raw memory file editor

components/
├── chat/
│   ├── ChatWindow.tsx          # SSE streaming message display
│   ├── MessageBubble.tsx       # User / Futuro message variants
│   ├── MemoryUpdateCard.tsx    # Proposed update: Accept/Edit/Skip
│   └── IntentBadge.tsx        # Shows active agent (BQ Coach, etc.)
├── campaign/
│   ├── PipelineBoard.tsx       # Kanban-style company tracker
│   ├── CompanyCard.tsx         # Card with status, last action, next step
│   └── ActivityTimeline.tsx    # Per-company event history
├── stories/
│   ├── StoryBrowser.tsx        # Filterable list + semantic search
│   ├── StoryCard.tsx           # Story with theme tags
│   └── StoryEditor.tsx         # STAR format editor
└── shared/
    ├── MarkdownRenderer.tsx    # Renders agent responses
    └── StreamingText.tsx       # Animates SSE token stream
```

---

## Security model

**Threat model:** Personal tool deployed to a small cloud server or run locally. Primary risk: unauthorized access to the server exposes the user's memory and conversations.

**Controls:**
- JWT authentication on all API endpoints (see ADR-007)
- HTTPS enforced in production (Nginx TLS termination)
- API key stored only in `.env`, never in code or git history
- Memory files in a private git repo
- Optional: IP allowlist at the reverse proxy layer
- Optional: WireGuard VPN for access without exposing the port at all

**What Anthropic receives:** Only conversation text sent via API calls. No memory files, no database contents, no file uploads — only the portions of memory included in the system prompt / context window for a given request.

---

## Environment variables

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...
JWT_SECRET=<256-bit random string>
USER_PASSWORD_HASH=<bcrypt hash of your password>

# Optional overrides
CLAUDE_MODEL=claude-sonnet-4-5
MAX_TOKENS=8192
DATA_DIR=./data                    # Default: backend/data
MEMORY_DIR=${DATA_DIR}/memory      # Git-tracked markdown
CHROMA_DIR=${DATA_DIR}/chroma      # ChromaDB index (gitignored)
DB_PATH=${DATA_DIR}/futuro.db      # SQLite database
GIT_AUTO_COMMIT=true               # Auto-commit memory updates

# Production only
ALLOWED_ORIGINS=https://your-domain.com
```
