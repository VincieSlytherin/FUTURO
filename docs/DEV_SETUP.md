# Development Setup

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
- SQLite tables are created automatically on backend startup via SQLAlchemy `create_all()`
- the memory directory and its stub Markdown files are created automatically by the memory manager
- there are no checked-in Alembic migration files in this snapshot

Because of that, you do not need a migration step to get the app running locally.

## Backend requirements

The backend dependency list lives in [backend/requirements.txt](/Users/ranju1008/Desktop/futuro/backend/requirements.txt).

If you already have a Conda environment named `futuro`, activate that first and use it.

```bash
conda activate futuro
python --version
```

Otherwise, create a virtual environment and install dependencies:

```bash
cd /Users/ranju1008/Desktop/futuro
python3.12 -m venv backend/.venv
source backend/.venv/bin/activate
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
```

If `python3.12` is not available on your machine, use your installed Python 3.12 binary instead.

## Frontend requirements

```bash
cd /Users/ranju1008/Desktop/futuro/frontend
npm install
```

## Detailed local configuration

### 1. Create `.env`

```bash
cd /Users/ranju1008/Desktop/futuro
cp .env.example .env
```

### 2. Generate `JWT_SECRET`

```bash
openssl rand -hex 32
```

Paste the output into `JWT_SECRET=` in `.env`.

### 3. Generate `USER_PASSWORD_HASH`

Make sure your backend environment is active, then run:

```bash
cd /Users/ranju1008/Desktop/futuro
python -c "import bcrypt; print(bcrypt.hashpw(b'your-password-here', bcrypt.gensalt()).decode())"
```

Paste the output into `USER_PASSWORD_HASH=` in `.env`.

### 4. Fill the minimum required `.env` values

Minimal first-boot setup:

```env
ANTHROPIC_API_KEY=sk-ant-not-set
JWT_SECRET=your-generated-secret
USER_PASSWORD_HASH=your-generated-bcrypt-hash
DEBUG=true
ALLOWED_ORIGINS=["http://localhost:3000"]
SCOUT_ENABLED=false
LLM_PROVIDER=auto
OLLAMA_ENABLED=false
```

Claude-based setup:

```env
ANTHROPIC_API_KEY=sk-ant-...
JWT_SECRET=your-generated-secret
USER_PASSWORD_HASH=your-generated-bcrypt-hash
DEBUG=true
ALLOWED_ORIGINS=["http://localhost:3000"]
LLM_PROVIDER=claude
CLAUDE_MODEL=claude-sonnet-4-5
```

The default storage paths in `.env.example` already match this repo:

```env
DATA_DIR=./backend/data
MEMORY_DIR=./backend/data/memory
CHROMA_DIR=./backend/data/chroma
DB_PATH=./backend/data/futuro.db
```

### 5. Optional Ollama setup

If you want to run locally without Anthropic:

```bash
ollama serve
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

Then set:

```env
ANTHROPIC_API_KEY=sk-ant-not-set
LLM_PROVIDER=ollama
OLLAMA_ENABLED=true
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=qwen2.5:7b
OLLAMA_EMBED_MODEL=nomic-embed-text
```

If you want automatic fallback instead, use:

```env
LLM_PROVIDER=auto
```

## Running the app

### Start the backend

```bash
cd /Users/ranju1008/Desktop/futuro
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

On first startup, the backend will:
- create `backend/data/`
- create the SQLite database file
- create all tables
- create the ChromaDB directory
- initialize the memory directory as needed

### Start the frontend

Open a second terminal:

```bash
cd /Users/ranju1008/Desktop/futuro/frontend
npx next dev -H 127.0.0.1 -p 3000
```

### Open the app

- Frontend: `http://localhost:3000`
- Backend health: `http://127.0.0.1:8000/api/health`
- Backend docs: `http://127.0.0.1:8000/docs`

The docs page is only visible when `DEBUG=true`.

## Shortcut commands

After dependencies are installed, you can use:

```bash
cd /Users/ranju1008/Desktop/futuro
make setup
make dev
make dev-backend
make dev-frontend
```

The manual steps above are still the clearest path if you want full control over each config value.

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

## Running tests

### Backend

```bash
cd /Users/ranju1008/Desktop/futuro
source backend/.venv/bin/activate
cd backend
pytest tests -v
```

### Frontend

```bash
cd /Users/ranju1008/Desktop/futuro/frontend
npm test -- --watchAll=false
```

## Common issues

### `make setup` or `make migrate` mentions Alembic

The current repo snapshot does not include Alembic migration files. Database tables are created automatically on backend startup.

### Login returns `401 Invalid password`

The plaintext password you type into the login form must match the bcrypt hash stored in `USER_PASSWORD_HASH`.

### `http://localhost:8000/docs` is missing

Set `DEBUG=true` in `.env` and restart the backend.

### Ollama requests fail

Make sure Ollama is running and the configured models are installed:

```bash
ollama serve
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

## Useful commands

```bash
make test
make test-backend
make test-frontend
make rebuild-index
make backup
```
