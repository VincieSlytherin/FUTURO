# Developer Log

## 2026-04-02

### Added

- Added a new `Planner` feature for job-search execution tracking.
- Added a dedicated `planner.md` memory file with two checklist-backed sections:
  - `Daily tasks`
  - `Learning backlog`
- Added a new `PLANNER` chat intent and planner-specific agent prompt.
- Added a new Planner UI page for adding, editing, checking off, and deleting checklist items.
- Added planner context to weekly digest emails.

### Behavior

- Planner items are stored in memory as markdown checkboxes, not in a new database table.
- Chat can use planner items automatically because `planner.md` is injected into agent context.
- Weekly digest now includes:
  - weekly focus
  - daily tasks
  - learning backlog

### Git / local data note

- No `.gitignore` change was needed for the planner feature itself.
- The planner uses the existing memory system under `backend/data/memory/`.
- That memory directory is already ignored by the main project repo and managed locally by the memory git repo.
