# Memory System

The memory system is what makes Futuro different from a stateless AI assistant. This document covers the design, implementation, and operational details.

---

## Design goals

1. **Trustworthy** — the user should be able to rely on Futuro remembering things correctly. A memory system that makes things up or forgets is worse than no memory.
2. **Transparent** — the user should be able to see exactly what Futuro "knows" about them, edit it, and correct it.
3. **Portable** — memory should survive Futuro's deprecation, code rewrites, or the user switching tools.
4. **Incremental** — the system should work with minimal initial setup and get richer over time.
5. **Git-tracked** — every change is versioned, reversible, and attributable.

---

## The three storage layers

```
┌─────────────────────────────────────────────────────┐
│                 Markdown files                       │
│              (backend/data/memory/)                 │
│  Human-readable · Git-tracked · Always the source   │
│  of truth · Portable to any system                  │
│                                                     │
│  L0_identity.md  L2_knowledge.md  stories_bank.md  │
│  resume_versions.md  interview_log.md               │
└──────────────────────┬──────────────────────────────┘
                       │ derived from
┌──────────────────────▼──────────────────────────────┐
│                  ChromaDB                           │
│              (backend/data/chroma/)                 │
│  Semantic search acceleration layer                 │
│  Indexes stories_bank + L2 knowledge entries        │
│  Rebuilt on demand — never the source of truth      │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                   SQLite                            │
│              (backend/data/futuro.db)               │
│  Structured relational data                         │
│  Campaign pipeline · Interview events · Outreach    │
│  Sessions · Activity logs                           │
└─────────────────────────────────────────────────────┘
```

**Rule:** Markdown is always the source of truth for everything in it. ChromaDB is always derived. If there's a conflict, markdown wins.

---

## Memory tiers

### L0 · Core Identity
**File:** `L0_identity.md`  
**Size target:** 400–600 words  
**Change frequency:** Rarely (once a month or less)  
**Always loaded:** Yes — every agent reads L0 on every request

L0 is the stable foundation. It contains who the person is, what they're targeting, and what they need from Futuro. It's small enough to fit in context without cost concerns.

**Update triggers:**
- User explicitly requests a change ("update my target location")
- A fundamental career shift (new degree, major role change, new target)
- After onboarding, when initial profile is refined

**What NOT to put in L0:** Anything that changes weekly (that belongs in L1) or anything that could grow unboundedly (that belongs in L2).

### L1 · Campaign State
**File:** `L1_campaign.md`  
**Size target:** 200–400 words  
**Change frequency:** Every session  
**Always loaded:** Yes — every agent reads L1 on every request

L1 is the live dashboard of the search — where things stand, what the focus is, and how the person is doing emotionally. Note that company-level data lives in SQLite; L1 is the narrative layer that explains the shape and direction of the search.

**Update triggers:**
- End of every session (strategy updates, mindset update)
- When campaign status shifts significantly
- After strategy review sessions

**L1 must not grow** — it should be updated in place, not appended to. When a week is over, its focus section is replaced, not accumulated.

### L2 · Knowledge Base
**File:** `L2_knowledge.md`  
**Size target:** Grows unboundedly (this is intentional)  
**Change frequency:** When new content is ingested or strategy shifts  
**Loading:** Loaded on demand by agents that need it (Intake, Strategy); selectively loaded by others

L2 is the accumulation of everything the user has learned about job searching. Unlike L0/L1, it grows continuously and is never pruned — it's a learning history.

**Loading strategy for L2:** Because L2 can grow large, agents don't load the whole file. They request specific sections:
- StrategyReviewAgent: loads "Current strategy" + "Strategy iteration log"
- IntakeAgent: loads "Insights from content" + "Market intelligence"
- BQCoachAgent: loads "Interview prep learnings"

```python
class MemoryManager:
    async def load_l2_section(self, section: str) -> str:
        """Load a specific section from L2 by header name."""
        ...
```

---

## MemoryManager implementation

```python
class MemoryManager:
    def __init__(self, memory_dir: Path, db: AsyncSession, repo: git.Repo):
        self.memory_dir = memory_dir
        self.db = db
        self.repo = repo

    async def load_context(self, agent_type: str) -> AgentContext:
        """
        Build the full context for an agent.
        Each agent declares its memory_reads in its class definition.
        """
        context = AgentContext()

        # Always load L0 and L1
        context.identity = await self.read_markdown("L0_identity.md")
        context.campaign = await self.read_markdown("L1_campaign.md")

        # Load SQLite data based on agent type
        if agent_type in ("BQ", "DEBRIEF", "STRATEGY"):
            context.campaign_stats = await self._load_campaign_stats()
            context.recent_interviews = await self._load_recent_interviews(n=3)

        # Load agent-specific markdown
        if agent_type in ("BQ", "STORY", "DEBRIEF"):
            context.stories = await self.read_markdown("stories_bank.md")
        if agent_type in ("RESUME",):
            context.resume = await self.read_markdown("resume_versions.md")
        if agent_type in ("STRATEGY", "INTAKE"):
            context.knowledge = await self.load_l2_section("Current strategy")

        return context

    async def read_markdown(self, filename: str) -> str:
        path = self.memory_dir / filename
        return path.read_text(encoding="utf-8")

    async def write_section(
        self,
        filename: str,
        section_header: str,
        new_content: str,
        action: Literal["append", "replace", "create"],
        commit_message: str
    ) -> None:
        path = self.memory_dir / filename
        content = path.read_text(encoding="utf-8")

        if action == "append":
            # Find the section and append after its last line
            content = self._append_to_section(content, section_header, new_content)
        elif action == "replace":
            # Replace the entire section
            content = self._replace_section(content, section_header, new_content)
        elif action == "create":
            # Append a new top-level section
            content = content.rstrip() + "\n\n---\n\n" + new_content

        path.write_text(content, encoding="utf-8")
        self._git_commit(filename, commit_message)

    def _git_commit(self, filename: str, message: str) -> None:
        self.repo.index.add([str(self.memory_dir / filename)])
        self.repo.index.commit(f"[futuro] {message}")
```

---

## Memory update approval flow

Agents never write to memory autonomously. They propose updates; the user approves.

```
Agent.post_process(response) → list[MemoryUpdate]
        │
        ▼
POST /api/chat response includes "proposed_updates" field
        │
        ▼
Frontend renders MemoryUpdateCard for each:
┌─────────────────────────────────────────────┐
│ 📝 Update: stories_bank.md                 │
│ Adding: STORY-004 — Data migration story   │
│ ─────────────────────────────────────────── │
│ ## STORY-004 · Platform Migration Lead     │
│ Themes: leadership, technical, ambiguity   │
│ ...                                        │
│                                            │
│ [Accept]  [Edit]  [Skip]                   │
└─────────────────────────────────────────────┘
        │
        ├── Accept → POST /api/memory/{file}/apply-update
        │               → MemoryManager.write_section()
        │               → git commit
        │               → (if story) ChromaDB.add_story()
        │
        ├── Edit → Opens modal with editable text → Accept
        │
        └── Skip → Discard
```

**Rationale for manual approval:** Memory mistakes are worse than memory gaps. A wrong "fact" that gets written and repeatedly fed back in context will compound. Requiring a human in the loop keeps the memory trustworthy.

---

## Vector store design

### When to index
- When a new story is accepted (real-time)
- When a story is edited (real-time update)
- On demand via `POST /api/stories/rebuild-index` (full rebuild)
- On startup, if the index is empty (auto-rebuild)

### Document structure

Each story gets one ChromaDB document. The text content is optimized for semantic matching against behavioral interview questions.

```python
def story_to_chroma_doc(story: Story) -> ChromaDoc:
    # Combine elements that reflect what a BQ question would be asking
    # Focus on: the challenge faced, the action taken, the result
    text = f"""
    {story.one_liner}
    
    Challenge: {story.situation} {story.task}
    Action: {story.action}
    Result: {story.result}
    Themes: {", ".join(story.themes)}
    """
    return ChromaDoc(
        id=story.story_id,
        document=text.strip(),
        metadata={
            "story_id": story.story_id,
            "title": story.title,
            "themes": story.themes,  # Stored as list
            "has_numbers": bool(re.search(r'\d+%|\$\d+|x\d+', story.result)),
            "archived": story.archived,
        }
    )
```

### Embedding model

Default: `text-embedding-3-small` (OpenAI, 1536 dimensions)  
Fallback: ChromaDB's default local embedding function (no API call needed, lower quality)

The embedding model is configurable via `EMBEDDING_MODEL` env var. The index must be rebuilt when changing models.

---

## Git integration

The memory directory is both a data store and a git repo. The git history IS the audit trail.

```bash
# On first setup:
git init backend/data/memory
git add .
git commit -m "initial memory setup"

# Every memory update:
git add L1_campaign.md
git commit -m "[futuro] update L1: moved Anthropic to TECHNICAL stage"
```

Commit message convention: `[futuro] {action}: {brief description}`
Examples:
- `[futuro] update L1: Schwab moved to final round`
- `[futuro] add story: STORY-004 platform migration`
- `[futuro] update L2: added insight from IGotAnOffer course`
- `[futuro] manual edit: L0 target location updated`

**Remote backup (optional):**
```bash
git remote add backup git@github.com:your-username/futuro-memory-private.git
# Push after each session:
git push backup main
```

The memory repo must be private. It contains your full professional history.

---

## Context window budget

At `claude-sonnet-4-5`, the context window is 200K tokens. Memory consumption per request:

| Component | Estimated tokens |
|---|---|
| System prompt (base persona + agent) | ~800 |
| L0 identity | ~600 |
| L1 campaign | ~400 |
| Stories bank (full, if loaded) | ~2,000–6,000 |
| Resume versions (full, if loaded) | ~1,000–2,000 |
| Interview log (recent section) | ~500–1,000 |
| L2 section (selective) | ~500–1,500 |
| Conversation history | ~500–3,000 |
| **Total** | ~6,000–15,000 |

Well within limits. The main cost lever is conversation history length — long chat sessions will accumulate tokens. The frontend should implement a "summarize and continue" option for sessions exceeding ~40 turns.

---

## Onboarding flow

Two paths, both produce the same initial memory state.

### Path A: File-based (faster for people who can write)

1. User clones the repo and fills in `onboarding/my_profile.md`
2. Runs `make onboard` → script reads the file and populates L0, seeds L1
3. Optionally: user uploads their current resume → ResumeEditorAgent structures it into `resume_versions.md`

### Path B: Conversation-based (better for people who prefer dialogue)

1. User opens Futuro for the first time
2. Futuro detects empty L0 (`L0_identity.md` exists but has no content past headers)
3. CoreAgent switches to onboarding mode: asks questions in small batches over 3–4 turns
4. At the end: "Here's what I've put together for your profile — does this look right?"
5. User approves → `make onboard-save` writes the memory files

Both paths end with:
- A populated `L0_identity.md`
- A seeded `L1_campaign.md` (current status, first priorities)
- An initialized `stories_bank.md` (empty index, ready for first story)
- An initialized `resume_versions.md` (current bullets if resume was provided)
