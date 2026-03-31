# Job Scout Agent

The Job Scout is Futuro's automated job discovery system. It continuously scrapes listings from multiple job boards, scores each one against your profile using Claude, and surfaces the best matches — so you're always working from a ranked, current list rather than manually searching each platform.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              APScheduler (background)                   │
│  Every N hours per active config:                       │
│  ScoutConfig → run_scout() → scrape → score → persist  │
└────────────────────┬────────────────────────────────────┘
                     │
          ┌──────────▼──────────┐
          │    python-jobspy    │
          │  LinkedIn  Indeed   │
          │  Glassdoor ZipRecr. │
          └──────────┬──────────┘
                     │ raw listings (pandas DataFrame)
          ┌──────────▼──────────┐
          │   Deduplication     │
          │  SHA-256 url_hash   │
          │  skip seen URLs     │
          └──────────┬──────────┘
                     │ new listings only
          ┌──────────▼──────────┐
          │   Claude Scoring    │
          │  L0 identity +      │
          │  job description    │
          │  → score 0-100      │
          │  → pros / cons      │
          │  → H-1B flag        │
          └──────────┬──────────┘
                     │
          ┌──────────▼──────────┐
          │  SQLite (jobs DB)   │
          │  job_listings table │
          │  status: NEW        │
          └─────────────────────┘
```

---

## Data sources

`python-jobspy` scrapes four platforms in a single call, no authentication required:

| Platform    | Data quality | Notes |
|-------------|-------------|-------|
| LinkedIn    | High        | Description often requires `linkedin_fetch_description=True` (slower) |
| Indeed      | High        | Best salary data |
| Glassdoor   | Medium      | Good for company info overlay |
| ZipRecruiter| Medium      | High volume, tech-heavy |

**Why not direct LinkedIn scraping?** LinkedIn aggressively blocks scrapers and bans accounts. `python-jobspy` uses rotating strategies that are significantly more robust. For production-scale use, consider pairing with a proxy service.

---

## Scout configs

Each `ScoutConfig` defines one search. You can have multiple configs for different searches running simultaneously.

| Field | Description | Default |
|---|---|---|
| `name` | Human label | required |
| `search_term` | Job title / keywords | required |
| `location` | City, state | `San Francisco, CA` |
| `distance_miles` | Radius | 50 |
| `sites` | CSV of platforms | `linkedin,indeed,glassdoor` |
| `results_wanted` | Max listings per run | 25 |
| `hours_old` | Only jobs posted in last N hours | 72 |
| `is_remote` | `true` / `false` / `null` (any) | null |
| `min_score` | Only surface jobs ≥ this score | 60 |
| `schedule_hours` | Re-scan every N hours | 12 |
| `is_active` | Whether the scheduler runs this | true |

**Recommended config set for a typical AI engineer search:**

```
Config 1: "Bay Area AI — core"
  search_term: AI Engineer
  location: San Francisco, CA
  min_score: 65
  hours_old: 72
  schedule_hours: 12

Config 2: "Remote ML roles"
  search_term: Machine Learning Engineer
  is_remote: true
  min_score: 70
  schedule_hours: 24

Config 3: "Seattle / NYC fallback"
  search_term: AI Engineer
  location: Seattle, WA
  min_score: 65
  schedule_hours: 24
```

---

## Scoring system

Claude scores each new job 0–100 using your `L0_identity.md` as the benchmark. The prompt is deterministic and structured to produce calibrated scores:

**Score bands:**
- **90–100** Exceptional fit — apply today, prioritise prep
- **70–89** Strong match — worth applying, solid candidate
- **50–69** Partial match — gaps exist, evaluate carefully
- **30–49** Weak match — significant misalignment
- **0–29** Poor match — wrong level, domain, or clearly unsuitable

**What Claude evaluates:**
- Skill overlap (tech stack, frameworks, specific tools)
- Level match (not over- or under-qualified)
- Company type fit (matches your target company profile)
- H-1B / sponsorship signals (keyword detection in description)
- Location / remote alignment
- Salary range vs. your targets (if listed)

**Important calibration note:** A score of 70 is a genuinely good signal. Most jobs should land 40–75. If you're seeing nearly everything at 85+, your L0 identity may be too generic — add more specific skills and constraints.

---

## Deduplication

Every job URL is hashed (SHA-256) before insertion. The `url_hash` field has a unique constraint in SQLite. This means:

- The same job listing will never be scored twice, even across multiple runs
- Runs are idempotent: running the same config twice in quick succession costs one API call (first run), then produces `jobs_new: 0` (second run)
- Dismissed jobs stay dismissed — they won't resurface in a later scan

---

## Job status lifecycle

```
NEW → SAVED → (apply manually) → APPLIED
    → PIPELINE  (added to campaign board)
    → DISMISSED
    → APPLIED   (direct)
```

- **NEW**: Just discovered, unseen
- **SAVED**: Interesting, review later
- **PIPELINE**: Added to campaign Kanban (also creates Company record)
- **DISMISSED**: Not interested, won't resurface
- **APPLIED**: Application submitted

The `PIPELINE` action is the key integration point — it calls `POST /api/scout/jobs/{id}/to-pipeline`, which creates (or finds) the Company record and logs an event. From that point, the job lives in the campaign tracker with full event history.

---

## API reference

### Configs

```
GET    /api/scout/configs              → list all configs
POST   /api/scout/configs              → create config
PATCH  /api/scout/configs/{id}         → update config
DELETE /api/scout/configs/{id}         → delete config
POST   /api/scout/configs/{id}/run     → trigger manual scan (background)
GET    /api/scout/configs/{id}/runs    → run history (last 20)
```

### Listings

```
GET    /api/scout/jobs                 → paginated listings
  ?status=NEW|SAVED|PIPELINE|DISMISSED|APPLIED|ALL
  ?min_score=65
  ?config_id=1
  ?limit=30&offset=0

GET    /api/scout/jobs/{id}            → full listing (marks as seen)
PATCH  /api/scout/jobs/{id}/action     → update status
  body: { "status": "SAVED", "note": "Optional note" }
POST   /api/scout/jobs/{id}/to-pipeline → add to campaign board
```

### Stats

```
GET    /api/scout/stats                → dashboard numbers
```

---

## Background scheduler

The scheduler (`APScheduler AsyncIOScheduler`) starts at FastAPI lifespan and loads all active configs. Jobs are fired using `IntervalTrigger` per config's `schedule_hours`.

**Startup behaviour:**
- All active configs are registered at boot with `next_run_time = now + 10s` (first run happens almost immediately)
- Subsequent runs fire at `schedule_hours` intervals

**Dynamic registration:**
- Creating a new config → `register_config()` is called immediately
- Updating `schedule_hours` or `is_active` → config is re-registered or unregistered
- Deleting a config → `unregister_config()` removes the scheduler job

**To disable the scheduler** (e.g. for development or testing):
```bash
SCOUT_ENABLED=false
```

---

## Chat integration

When the user asks about jobs in chat, the intent classifier routes to `JobScoutAgent` (SCOUT intent). This agent:

- Summarises what the latest scan found
- Surfaces the top 2–3 listings worth paying attention to
- Analyses specific companies or titles on request
- Spots patterns across high-scoring listings (e.g. "fine-tuning keeps appearing — worth adding to your profile")
- Helps plan outreach strategy for strong matches

**Example triggers:**
- "What did the job scanner find this week?"
- "Any good AI engineer roles come up?"
- "Tell me about the Anthropic listing"
- "Should I apply to the Cohere role or reach out first?"

---

## Performance and cost

**Per run cost (approximate):**
- Scraping: free (python-jobspy, no API)
- Scoring: ~400 tokens per job × N new jobs
- At claude-sonnet-4-5 pricing: ~$0.002 per new job scored
- A typical run finding 5 new jobs: ~$0.01

**Reducing cost:**
- Increase `hours_old` (fewer results returned)
- Decrease `results_wanted`
- Increase `schedule_hours` (fewer runs)
- Set `min_score` on the scrape side — but note: scoring happens after scraping, so `min_score` only affects what surfaces in the UI, not what gets scored

**Reducing API calls in dev:**
- Set `SCOUT_ENABLED=false` in `.env` to disable background runs
- Use `make test` — test suite mocks Claude calls entirely

---

## Extending to new sources

`python-jobspy` supports additional sources that can be added to the `sites` CSV:

```python
# Currently supported by jobspy:
sites = ["linkedin", "indeed", "glassdoor", "zip_recruiter", "google"]
```

For sources not covered by jobspy (e.g. Greenhouse, Lever, company career pages), implement a custom scraper that returns the same normalised dict structure as `_scrape_jobs()` and add it as a fallback in `job_scout.py`.

---

## Security and privacy

- **No credentials stored**: `python-jobspy` scrapes public listings — no LinkedIn login required
- **Job descriptions stored locally**: Full descriptions are saved in your SQLite DB at `backend/data/futuro.db` — they never leave your machine except when sent to Claude for scoring
- **Claude receives**: Job title, company, location, description snippet (~3000 chars), and your L0 identity (~2000 chars) — no other personal data
- **Rate limiting**: `python-jobspy` has built-in delays between requests. For heavy use, configure a proxy in jobspy's settings to avoid IP rate limits

---

## Troubleshooting

**No jobs appearing after a scan:**
- Check `GET /api/scout/configs/{id}/runs` for `error_msg`
- python-jobspy occasionally gets rate-limited by LinkedIn — try `indeed` or `glassdoor` only
- Verify `ANTHROPIC_API_KEY` is set correctly

**All jobs scoring very low:**
- Your `L0_identity.md` may be sparse — fill in technical skills, target role, and target companies
- Lower `min_score` in the config to see all results regardless of score

**Scheduler not running:**
- Check `SCOUT_ENABLED=true` in `.env`
- Check logs for `[monitor] scheduler started`
- Trigger a manual run via the UI to verify the pipeline works

**Rebuilding from scratch:**
- Delete `backend/data/futuro.db` and restart — all tables are recreated
- Job listings and configs are lost; memory markdown files are unaffected
