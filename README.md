<div align="center">
  <img src="futuro.png" alt="Futuro" width="480" />
  <h1>Futuro</h1>
  <p>A warm, memory-driven job search companion you own and run yourself.</p>
</div>

---

Futuro is a local-first web app for managing your job search. It keeps your memory in Markdown, stores structured data in SQLite, and gives you a single interface for chat, company tracking, stories, interviews, and search strategy.

This README is written as a practical setup guide. If you follow it top to bottom, you should be able to:

- install dependencies
- create a working `.env`
- start the backend
- start the frontend
- open `http://localhost:3000/login`
- sign in successfully

## What works in the current repo snapshot

- the backend creates SQLite tables automatically on startup
- the memory directory is created automatically when first used
- the app can boot in auth/data-only mode even if Claude and Ollama are both not configured yet
- chat and provider-backed features need either a real Anthropic key or a working Ollama setup
- there are no checked-in Alembic migration files in this snapshot

## Main features

- Persistent memory stored in Markdown and versioned with Git
- AI chat with intent routing for intake, stories, resume help, BQ practice, debrief, strategy, and scouting
- Company pipeline tracking
- Story bank with local vector search
- Interview log and review flow
- Local SQLite storage
- Optional Claude or Ollama provider setup

## Tech stack

| Layer | Choice |
|---|---|
| Backend | FastAPI |
| Frontend | Next.js 14 |
| Language | Python 3.12 + TypeScript |
| Database | SQLite + SQLAlchemy 2.0 |
| Auth | JWT + bcrypt |
| Vector store | ChromaDB |
| Job scraping | python-jobspy |
| Scheduling | APScheduler |

## Recommended local setup

If you already have a Conda environment named `futuro`, use that. It is the cleanest path for this project.

### 1. Activate your Python environment

If you already have the Conda env:

```bash
conda activate futuro
python --version
```

You want Python 3.12.x if possible.

If you do not already have that env, create it:

```bash
conda create -n futuro python=3.12 -y
conda activate futuro
```

### 2. Install backend dependencies

From the project root:

```bash
cd /Users/ranju1008/Desktop/futuro
pip install -r backend/requirements.txt
```

### 3. Install frontend dependencies

```bash
cd /Users/ranju1008/Desktop/futuro/frontend
npm install
cd ..
```

### 4. Create your environment file

```bash
cd /Users/ranju1008/Desktop/futuro
cp .env.example .env
```

### 5. Generate `JWT_SECRET`

```bash
openssl rand -hex 32
```

Paste that value into:

```env
JWT_SECRET=your-generated-value
```

### 6. Generate `USER_PASSWORD_HASH`

Pick the password you want to use in the login page, then generate a bcrypt hash for it:

```bash
python -c "import bcrypt; print(bcrypt.hashpw(b'your-password-here', bcrypt.gensalt()).decode())"
```

Paste the result into:

```env
USER_PASSWORD_HASH=your-generated-bcrypt-hash
```

### 7. Fill `.env`

The safest first-boot setup is to make the app start even before you configure an LLM.

Use values like this:

```env
ANTHROPIC_API_KEY=sk-ant-not-set
JWT_SECRET=your-generated-value
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
ALLOWED_ORIGINS=["http://localhost:3000"]

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
- chat will stay unavailable until you configure Claude or Ollama

## Optional provider setup

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

## Start the app

Open two terminals.

### Terminal 1: backend

```bash
cd /Users/ranju1008/Desktop/futuro
conda activate futuro
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Expected result:

- backend starts on `http://127.0.0.1:8000`
- SQLite tables are created automatically on first boot

### Terminal 2: frontend

```bash
cd /Users/ranju1008/Desktop/futuro/frontend
npx next dev -H 127.0.0.1 -p 3000
```

Expected result:

- frontend starts on `http://127.0.0.1:3000`

## Verify everything

### Check backend health

```bash
curl http://127.0.0.1:8000/api/health
```

You should see something like:

```json
{"status":"ok","version":"0.4.0","providers":{}}
```

If `providers` is empty, that is okay for first boot. It just means Claude/Ollama is not configured yet.

### Check the login page

Open:

```text
http://127.0.0.1:3000/login
```

or

```text
http://localhost:3000/login
```

### Test login from the terminal

```bash
curl -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password":"your-password-here"}'
```

If the password matches `USER_PASSWORD_HASH`, you will get back an `access_token`.

## What you can do before LLM setup

Even without Claude or Ollama configured, you can still:

- open the app
- log in
- use auth
- create the SQLite database
- access provider status
- work on memory and other local-only parts of the app

What will still need a provider:

- chat
- intent classification
- provider-backed scoring
- local/remote embedding features that rely on the configured provider path

## Common issues

### `ALLOWED_ORIGINS` parsing error

Use JSON array syntax in `.env`, not a bare string:

```env
ALLOWED_ORIGINS=["http://localhost:3000"]
```

### `.env` is not being read

The backend now resolves `.env` from the project root. Start the backend from the repo and keep your `.env` in the top-level folder.

### Login fails even though the password looks right

Make sure you generated `USER_PASSWORD_HASH` with raw `bcrypt`, for example:

```bash
python -c "import bcrypt; print(bcrypt.hashpw(b'your-password-here', bcrypt.gensalt()).decode())"
```

### `greenlet` missing error on backend startup

Install backend requirements again:

```bash
pip install -r backend/requirements.txt
```

### Frontend starts but chat says no provider is configured

That is expected if you used:

```env
ANTHROPIC_API_KEY=sk-ant-not-set
OLLAMA_ENABLED=false
```

Configure Claude or Ollama to enable chat.

## Useful files

- `backend/requirements.txt`
- `.env.example`
- `backend/app/config.py`
- `backend/app/api/auth.py`
- `backend/app/providers/router.py`
- `frontend/src/components/shared/ProviderStatus.tsx`
- `docs/DEV_SETUP.md`

## Project structure

```text
futuro/
├── backend/
│   ├── app/
│   ├── data/
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   └── package.json
├── docs/
├── .env.example
├── Makefile
└── README.md
```

## License

Futuro is shared under the repository's included license terms. See `LICENSE` for details.
