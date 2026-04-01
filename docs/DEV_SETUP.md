# Development Setup

This guide matches the current Futuro repo behavior.

If you follow it top to bottom, you should be able to:

- install backend and frontend dependencies
- create a working `.env`
- start the backend
- start the frontend
- open `http://127.0.0.1:3000/login`
- sign in successfully
- choose providers from the Settings UI
- pull Ollama models with live progress
- upload files or folders into the Portfolio vault

## Prerequisites

| Tool | Recommended version | Notes |
|---|---|---|
| Python | 3.12 | Backend is documented and tested around Python 3.12 |
| Node.js | 20 LTS | Good fit for the Next.js 14 frontend |
| npm | 10+ | Usually bundled with Node 20 |
| Git | 2.40+ | Required for the repo and for memory history |
| Make | any recent version | Optional, but convenient |

Optional:
- Ollama, if you want to run Futuro locally without Anthropic
- Docker Desktop, if you prefer containers

## What the current codebase actually does

The current repo snapshot works like this:

- Alembic migrations are applied automatically on backend startup
- existing pre-Alembic local SQLite databases are bootstrapped and stamped safely on first upgrade
- the memory directory and its stub Markdown files are created automatically by the memory manager
- the app can boot in auth/data-only mode even when Claude and Ollama are both not configured yet
- an initial Alembic baseline migration is checked into the repo

Because of that, you usually do not need a separate migration step to get the app running locally. Backend startup will run `alembic upgrade head` for you.

## Backend requirements

The backend dependency list lives in [backend/requirements.txt](/Users/ranju1008/Desktop/futuro/backend/requirements.txt).

Recommended path: if you already have a Conda environment named `futuro`, use that.

```bash
conda activate futuro
python --version
```

Install backend dependencies from the project root:

```bash
cd futuro
pip install -r backend/requirements.txt
```

If you do not already have that Conda environment, you can create it:

```bash
conda create -n futuro python=3.12 -y
conda activate futuro
pip install -r backend/requirements.txt
```

If you prefer `venv`, that still works:

```bash
cd futuro
python3.12 -m venv backend/.venv
source backend/.venv/bin/activate
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
```

## Frontend requirements

```bash
cd futuro/frontend
npm install
cd ..
```

## Detailed local configuration

### 1. Create `.env`

```bash
cd futuro
cp .env.example .env
```

### 2. Generate `JWT_SECRET`

```bash
openssl rand -hex 32
```

Paste the output into:

```env
JWT_SECRET=your-generated-secret
```

### 3. Generate `USER_PASSWORD_HASH`

Make sure your backend environment is active, then run:

```bash
cd futuro
python -c "import bcrypt; print(bcrypt.hashpw(b'your-password-here', bcrypt.gensalt()).decode())"
```

Paste the output into:

```env
USER_PASSWORD_HASH=your-generated-bcrypt-hash
```

### 4. Fill `.env` for the safest first boot

Use values like this:

```env
ANTHROPIC_API_KEY=sk-ant-not-set
JWT_SECRET=your-generated-secret
USER_PASSWORD_HASH=your-generated-bcrypt-hash

CLAUDE_MODEL=claude-sonnet-4-5
MAX_TOKENS=8192

DATA_DIR=./backend/data
MEMORY_DIR=./backend/data/memory
CHROMA_DIR=./backend/data/chroma
DB_PATH=./backend/data/futuro.db

GIT_AUTO_COMMIT=true

DEBUG=true
LOG_LEVEL=info
ALLOWED_ORIGINS=["http://127.0.0.1:3000","http://localhost:3000"]

SCOUT_ENABLED=false
SCOUT_DEFAULT_LOCATION=San Francisco, CA
SCOUT_DEFAULT_SITES=linkedin,indeed,glassdoor

LLM_PROVIDER=auto
OLLAMA_ENABLED=false
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=qwen2.5:7b
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_TIMEOUT=120.0
OLLAMA_KEEP_ALIVE=10m
```

With that setup:

- the app will boot
- login will work
- database and memory routes will work
- chat stays unavailable until you configure Claude or Ollama

## Provider setup

Recommended default: `Auto (prefer Ollama)`.

That gives you this behavior:

- Futuro uses Ollama first when the local model is available
- if Ollama is unavailable, Futuro falls back to Claude when Claude is configured
- you can still force Claude-only or Ollama-only behavior in the Settings UI

### Option A: Use Claude

Set:

```env
ANTHROPIC_API_KEY=sk-ant-your-real-key
LLM_PROVIDER=claude
```

### Option B: Use Ollama

Install Ollama and pull models first:

```bash
ollama serve
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

Then update `.env`:

```env
ANTHROPIC_API_KEY=sk-ant-not-set
LLM_PROVIDER=ollama
OLLAMA_ENABLED=true
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=qwen2.5:7b
OLLAMA_EMBED_MODEL=nomic-embed-text
```

### Option C: Use the Settings UI

After the app is running, open:

```text
http://localhost:3000/settings
```

From there you can:

- choose `Auto (prefer Ollama)`, `Ollama only`, or `Claude only`
- set per-task overrides for `chat`, `classify`, `score`, and `embed`
- choose the active Ollama chat and embedding models
- pull Ollama models directly from the UI
- edit per-function custom instructions without touching prompt files
- apply the selection without manually editing `.env`

When you click `Apply`, Futuro will:

- save the provider settings into `.env`
- rebuild provider routing immediately
- prefer Ollama first when `Auto (prefer Ollama)` is selected

## Custom instructions in the UI

The Settings page also lets you change instructions per function.

Current sections include:

- Global
- General Chat
- BQ
- Story
- Resume
- Debrief
- Strategy
- Scout
- Intake

Important notes:

- custom instructions are stored locally in `backend/data/custom_instructions.json`
- changes apply on the next request
- you do not need to restart the backend after saving them

## Portfolio document vault

Futuro includes a `Portfolio` area for files you want to keep during the search.

Current behavior:

- upload individual files or a whole folder
- keep the uploaded folder structure
- support `.pdf`, `.doc`, and `.docx`
- open files directly from the UI
- delete a single file or a whole folder
- store everything locally under `backend/data/portfolio`

Useful examples:

- resume versions
- cover letters
- saved job descriptions
- take-home assignments
- interview prep packets
- offer letters or recruiter docs

## Pull Ollama models from the UI

In the Settings page, the Ollama section lets you:

- click `Pull` for models like `qwen2.5:7b`, `qwen2.5:14b`, `qwen2.5:32b`, and `nomic-embed-text`
- see live download progress
- see percentage, bytes downloaded, and recent status lines during the pull

Important notes:

- model downloads are allowed from the Settings page even if `.env` currently has `OLLAMA_ENABLED=false`
- after a model finishes downloading, enable Ollama in the Settings page or `.env` if you want Futuro to actively use it
- large models like `qwen2.5:32b` may take a long time and require substantial RAM and disk space

## Running the app

Open two terminals.

### Terminal 1: backend

If you use Conda:

```bash
cd futuro
conda activate futuro
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

If you use `venv`:

```bash
cd futuro
source backend/.venv/bin/activate
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

On first startup, the backend will:

- create `backend/data/`
- create the SQLite database file
- create all tables
- create the ChromaDB directory
- initialize the memory directory as needed

### Terminal 2: frontend

```bash
cd futuro/frontend
npx next dev -H 127.0.0.1 -p 3000
```

### Open the app

- Frontend: `http://127.0.0.1:3000`
- Login page: `http://127.0.0.1:3000/login`
- Backend health: `http://127.0.0.1:8000/api/health`
- Backend docs: `http://127.0.0.1:8000/docs`

The docs page is only visible when `DEBUG=true`.

## First-run verification

### Health check

```bash
curl http://127.0.0.1:8000/api/health
```

Expected result: JSON containing `"status": "ok"`.

### Login test

```bash
curl -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password":"your-password-here"}'
```

Expected result: JSON containing `access_token`.

### Provider routing check

Open:

```text
http://127.0.0.1:3000/settings
```

Verify that:

- the provider preference shows the mode you selected
- Ollama health is visible in the provider status area
- if `Auto (prefer Ollama)` is selected but the Ollama chat model is not pulled yet, Futuro temporarily falls back to Claude
- the `Portfolio` page can upload a test PDF or Word file

## Shortcut commands

After dependencies are installed, you can use:

```bash
cd futuro
make setup
make dev
make dev-backend
make dev-frontend
```

The manual steps above are still the clearest path if you want full control over each config value.

## Running tests

### Backend

If you use Conda:

```bash
cd futuro
conda activate futuro
cd backend
pytest tests -v
```

If you use `venv`:

```bash
cd futuro
source backend/.venv/bin/activate
cd backend
pytest tests -v
```

### Frontend

```bash
cd futuro/frontend
npx tsc --noEmit
```

## Common issues

### `make setup` or `make migrate` mentions Alembic

That is expected now. Futuro uses Alembic migrations, and backend startup also applies them automatically.

Useful commands:

```bash
make migrate
make migration MSG="add jd_summary to companies"
```

If you already had a local database from the old pre-Alembic snapshot, use `make migrate` or just start the backend once. That path safely stamps the existing schema before future migrations.

### Login returns `401 Invalid password`

The plaintext password you type into the login form must match the bcrypt hash stored in `USER_PASSWORD_HASH`.

### `http://127.0.0.1:8000/docs` is missing

Set `DEBUG=true` in `.env` and restart the backend.

### Portfolio upload fails

Check these first:

- you refreshed the app after restarting the backend
- the file type is `.pdf`, `.doc`, or `.docx`
- if you upload a folder, your browser supports folder selection well

Uploaded portfolio files are stored locally in `backend/data/portfolio`.

### Ollama requests fail

Make sure Ollama is running and the configured models are installed:

```bash
ollama serve
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

If you are using `Auto (prefer Ollama)` and the selected model is not pulled yet, Futuro may fall back to Claude instead of using Ollama immediately.

### The Settings page shows Ollama but chat still uses Claude

This usually means one of these is true:

- the selected Ollama chat model has not finished downloading yet
- Ollama is not running
- `Auto (prefer Ollama)` is enabled and Claude is being used as a fallback

## Useful commands

```bash
make test
make test-backend
make test-frontend
make rebuild-index
make backup
```
