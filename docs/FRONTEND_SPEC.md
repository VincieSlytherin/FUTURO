# Frontend Specification

---

## Stack

- **Framework:** Next.js 14 (App Router)
- **Language:** TypeScript
- **Styling:** Tailwind CSS + shadcn/ui
- **State:** Zustand (lightweight, no Redux overhead)
- **Data fetching:** TanStack Query (React Query v5)
- **Streaming:** native EventSource / SSE
- **Icons:** Lucide React

---

## Application layout

```
┌────────────────────────────────────────────────────┐
│ Sidebar (collapsible, 240px)    │  Main content     │
│                                 │                   │
│  ● Futuro                       │                   │
│  ────────                       │                   │
│  💬 Chat           ← active     │                   │
│  📋 Campaign                    │                   │
│  📚 Stories                     │                   │
│  📄 Resume                      │                   │
│  🗓  Interviews                  │                   │
│  🧠 Memory                      │                   │
│  ────────                       │                   │
│  ⚙  Settings                   │                   │
└────────────────────────────────────────────────────┘
```

Sidebar nav items correspond to the main feature areas. Active item is highlighted. On mobile: sidebar collapses to a bottom tab bar (Chat, Campaign, Stories, More).

---

## Page specifications

### `/chat` — Chat interface

The primary surface. Used for 80% of interactions.

```
┌─────────────────────────────────────────────────────┐
│  💬 Futuro                    [BQ Coach]  ← intent  │
│─────────────────────────────────────────────────────│
│                                                     │
│  ┌─────────────────────────────────────────┐        │
│  │ Hey, how are you holding up today?      │        │
│  │ And what would be most useful to        │        │
│  │ work on?                  ← Futuro msg  │        │
│  └─────────────────────────────────────────┘        │
│                                                     │
│         ┌──────────────────────────────────┐        │
│         │ Let's practice BQ. I have a      │        │
│         │ technical screen Thursday.       │        │
│         │                     ← user msg   │        │
│         └──────────────────────────────────┘        │
│                                                     │
│  ┌─────────────────────────────────────────┐        │
│  │ Thursday — okay, let's make sure        │        │
│  │ you're ready. For behavioral questions, │        │
│  │ ▋ ← streaming cursor                   │        │
│  └─────────────────────────────────────────┘        │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │ 📝 Update: stories_bank.md                  │   │
│  │ Adding follow-up Q&A to STORY-001            │   │
│  │                         [Accept] [Skip]      │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│─────────────────────────────────────────────────────│
│  [  Message Futuro...                        ↑ ]    │
└─────────────────────────────────────────────────────┘
```

**Component: `ChatWindow`**
- Messages rendered as `MessageBubble` (user right-aligned, Futuro left-aligned)
- Futuro messages: support full markdown rendering
- Streaming: tokens appear in real-time via SSE; cursor animates at the end of the stream
- Intent badge: small pill showing active agent ("BQ Coach", "Intake", etc.) — appears when classified
- Memory update cards: appear at the bottom of Futuro's message when proposed updates exist

**Component: `MemoryUpdateCard`**
```
┌───────────────────────────────────────────┐
│ 📝  stories_bank.md                       │
│     Adding: STORY-004 — Migration story   │
│  ─────────────────────────────────────── │
│  ## STORY-004 · Platform Migration Lead  │
│  **Themes:** leadership, technical        │
│  **One liner:** ...                       │
│                              [+3 lines]   │
│                                           │
│          [Accept]  [Edit]  [Skip]         │
└───────────────────────────────────────────┘
```
- Collapsed by default (shows first 4 lines)
- Expand button to read full proposed content
- Edit opens a modal with a simple text editor
- Accept → `POST /api/memory/{file}/apply-update` → success toast

**Component: `MessageInput`**
- Multiline textarea, auto-expanding
- Submit on Enter (Shift+Enter for newline)
- Disable during streaming (show spinner)
- Keyboard shortcut: `Cmd+K` to focus from anywhere

---

### `/campaign` — Company pipeline board

```
┌─────────────────────────────────────────────────────┐
│  Campaign                          [+ Add Company]   │
│  8 active · 62% response rate · 0 offers            │
│─────────────────────────────────────────────────────│
│                                                     │
│  Researching  Applied   Screening  Technical  Onsite│
│  ──────────   ───────   ─────────  ─────────  ──────│
│  ┌────────┐  ┌───────┐  ┌───────┐  ┌───────┐        │
│  │Databricks│ │Schwab │  │ Scale │  │Cohere │        │
│  │AI Eng. │  │Sr. AI │  │ AI    │  │ ML    │        │
│  │◉ HIGH  │  │◉ HIGH │  │● MED  │  │◉ HIGH │        │
│  │12d     │  │ 3d    │  │ 8d    │  │  1d   │        │
│  └────────┘  └───────┘  └───────┘  └───────┘        │
│                                                     │
│  ┌────────┐  ┌───────┐                              │
│  │ Arize  │  │Applied│                              │
│  │ML Eng. │  │ Matls │                              │
│  │● MED   │  │● MED  │                              │
│  └────────┘  └───────┘                              │
└─────────────────────────────────────────────────────┘
```

**Component: `PipelineBoard`**
- Columns: Researching → Applied → Screening → Technical → Onsite → (Closed section at bottom)
- Each column scrolls independently if many cards
- Drag-to-drop stage update (triggers `PATCH /api/campaign/companies/{id}/stage`)
- Stage update triggers an event log entry automatically

**Component: `CompanyCard`**
```
┌────────────────────────────────┐
│  Cohere                ◉ HIGH  │
│  ML Engineer                   │
│  ─────────────────────────────│
│  Technical · 1d ago            │
│  Next: System design prep      │
│                   [→ Details]  │
└────────────────────────────────┘
```
- Priority dot: ◉ HIGH (coral) / ● MEDIUM (amber) / ○ LOW (gray)
- Stage duration: days since last stage change
- Quick action: click "Details" → drawer opens with full company view

**Drawer: `CompanyDetailDrawer`**
- Full company info: role, URL, notes, salary range
- Activity timeline: all events in reverse chronological order
- Quick actions: Log event / Update stage / Prep with Futuro (links to chat with prefilled context)
- Interview list: any logged interviews for this company

**Stats bar:**
```
8 active · 62% response rate · 3 in interview stages · 0 offers
```
Pulled from `GET /api/campaign/stats`.

---

### `/stories` — Story bank

```
┌─────────────────────────────────────────────────────┐
│  Stories                            [+ New Story]   │
│                                                     │
│  🔍 [Search by question or theme...              ]  │
│     Themes: [Impact×] [Technical×]  [+ Filter]     │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │ STORY-001 · Multimodal RAG Pipeline           │  │
│  │ Impact · Ambiguity · Technical                │  │
│  │ "Built a production RAG system that cut       │  │
│  │  manual review by ~70%..."                    │  │
│  │                            [Practice] [Edit]  │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │ STORY-002 · EDA Copilot Agent                 │  │
│  │ Impact · Innovation · Technical               │  │
│  │ "Agentic EDA tool generating ~$180K in        │  │
│  │  estimated annual savings..."                 │  │
│  │                            [Practice] [Edit]  │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

**Semantic search:** as the user types in the search box, `POST /api/stories/search` is called with debounce (300ms). Results reorder by semantic relevance.

**[Practice] button:** opens chat with a prefilled message: "Let's practice answering behavioral questions using STORY-001."

**[Edit] button:** opens `StoryEditor` — a structured form with STAR fields, themes selector, and one-liner.

---

### `/resume` — Resume versions

```
┌─────────────────────────────────────────────────────┐
│  Resume                        [+ New Version]      │
│                                                     │
│  Current: v2.1 — Tailored for Cohere                │
│  Based on v1.0 · Created 2 days ago                 │
│                                                     │
│  [Tailor for new JD]   [View diff v2.1 → v1.0]     │
│                                                     │
│  ── Bullets (current version) ──────────────────── │
│                                                     │
│  RGA — Data Scientist / AI Engineer                 │
│  • Built a multimodal RAG pipeline for insurance    │
│    document analysis... [~70% manual review ↓]     │
│  • Developed EDA Copilot agent... [$180K savings]   │
│  • [+3 more bullets]                               │
│                                                     │
│  ── Version history ───────────────────────────── │
│  v2.1  Cohere ML Engineer       2d ago  [View]      │
│  v2.0  Anthropic AI Engineer    5d ago  [View]      │
│  v1.0  General baseline         14d ago [View]      │
└─────────────────────────────────────────────────────┘
```

**[Tailor for new JD]:** opens a modal → user pastes JD text → triggers `POST /api/resume/tailor` → streams suggestions in chat-like UI.

**[View diff]:** side-by-side diff view showing exactly what changed between versions. Uses a simple text diff (additions in green, removals in red).

---

### `/interviews` — Interview log

Two tabs: **Scheduled** (upcoming) and **Log** (past).

**Scheduled tab:** upcoming interviews with prep links.
```
Thu Apr 3 · Cohere · Technical Screen · 2:00 PM PT
[Prep with Futuro] [View company] [Add to calendar]
```

**Log tab:** past interviews in reverse chronological order, each expandable to show debrief notes.

**[Add Debrief] button:** opens a structured form that feeds into `POST /api/interviews/{id}/debrief`. The form pre-fills with the interview metadata; user fills in questions asked, strong/weak moments, gut feeling.

---

### `/memory` — Memory editor

Power-user view. Not the primary surface, but important for trust and transparency.

```
┌─────────────────────────────────────────────────────┐
│  Memory                                             │
│                                                     │
│  [ L0 Identity ] [ L1 Campaign ] [ L2 Knowledge ]  │
│  [ Stories ]     [ Resume ]      [ Interviews ]    │
│                                                     │
│  ─── L0 Identity ───────────────── Last edit: 2d ──│
│                                                     │
│  [markdown editor — raw file content editable]      │
│                                                     │
│  [Save + commit]                                    │
│                                                     │
│  ─── Git history ──────────────────────────────────│
│  3h ago  update L1: Cohere moved to screening       │
│  2d ago  add story: STORY-003                       │
│  5d ago  update L0: added new project               │
└─────────────────────────────────────────────────────┘
```

**Editor:** Simple textarea or CodeMirror for markdown syntax highlighting. Save triggers `PUT /api/memory/{filename}` and commits to git.

**Git history:** Shows recent commits to the memory repo, with the commit message and timestamp. Click a commit to see the diff.

---

## Streaming UX

SSE streaming is the core of the chat experience. Implementation details:

```typescript
// components/chat/ChatWindow.tsx

const streamMessage = async (message: string) => {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
    body: JSON.stringify({ message, history }),
  });

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let streaming = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop()!;

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));

        if (data.type === 'token') {
          streaming += data.text;
          updateStreamingMessage(streaming);
        }
        if (data.type === 'intent') {
          setActiveIntent(data.intent);
        }
        if (data.type === 'complete') {
          finalizeMessage(data.full_response);
          setProposedUpdates(data.proposed_updates);
        }
      }
    }
  }
};
```

---

## Design tokens

Follow Tailwind defaults with these custom extensions:

```js
// tailwind.config.js
{
  extend: {
    colors: {
      futuro: {
        50:  '#f0f4ff',  // Background tints
        500: '#6366f1',  // Primary (indigo-ish)
        600: '#4f46e5',  // Primary hover
      }
    },
    fontFamily: {
      sans: ['Inter', 'system-ui', 'sans-serif'],
      mono: ['JetBrains Mono', 'monospace'],
    }
  }
}
```

**Color semantics:**
- Priority HIGH: coral / rose-500
- Priority MEDIUM: amber-500
- Stage progress: indigo-500 (primary)
- Futuro messages: neutral surface
- User messages: primary tint
- Memory update cards: amber-50 border amber-200

---

## Responsive breakpoints

| Breakpoint | Layout |
|---|---|
| < 768px (mobile) | Sidebar hidden, bottom tab bar (Chat / Campaign / More) |
| 768–1024px (tablet) | Sidebar icon-only (collapsed), hover to expand |
| > 1024px (desktop) | Full sidebar always visible |

Chat is the primary mobile surface. Campaign board and memory editor are desktop-optimized.
