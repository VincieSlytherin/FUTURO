.PHONY: setup dev dev-backend dev-frontend test test-backend \
        rebuild-index backup restore deploy docker-dev docker-down deploy-secrets logs help migrate migration

BACKUP_DIR := backups
DATA_DIR   := backend/data

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Setup ─────────────────────────────────────────────────────────────────────

setup: ## First-time setup: env, secrets, deps, local data dirs, memory repo
	@echo "→ Setting up Futuro..."
	@cp -n .env.example .env || true
	@echo "\nGenerating JWT_SECRET..."
	@JWT_SECRET=$$(openssl rand -hex 32) && \
	  sed -i.bak "s/JWT_SECRET=.*/JWT_SECRET=$$JWT_SECRET/" .env && rm .env.bak
	@echo "Set your ANTHROPIC_API_KEY in .env (open it now)"
	@echo "Enter your Futuro login password (will be hashed):" && \
	  read -s PW && \
	  HASH=$$(python -c "import bcrypt; print(bcrypt.hashpw('$$PW'.encode(), bcrypt.gensalt()).decode())") && \
	  sed -i.bak "s|USER_PASSWORD_HASH=.*|USER_PASSWORD_HASH=$$HASH|" .env && rm .env.bak
	@cd backend && python -m venv .venv && .venv/bin/pip install -q -r requirements.txt
	@cd frontend && npm install --silent
	@mkdir -p $(DATA_DIR)/memory $(DATA_DIR)/chroma $(BACKUP_DIR)
	@if [ ! -d "$(DATA_DIR)/memory/.git" ]; then \
	  git -C $(DATA_DIR)/memory init && \
	  git -C $(DATA_DIR)/memory config user.email "futuro@local" && \
	  git -C $(DATA_DIR)/memory config user.name "Futuro" && \
	  git -C $(DATA_DIR)/memory commit --allow-empty -m "init memory repo"; \
	fi
	@echo "\n✓ Setup complete. Run 'make dev' to start. The SQLite schema will be migrated automatically on backend startup."

# ── Development ───────────────────────────────────────────────────────────────

dev: ## Start backend + frontend (development)
	@trap 'kill %1 %2' SIGINT; \
	  (cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000) & \
	  (cd frontend && npm run dev) & \
	  wait

dev-backend: ## Start backend only
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

dev-frontend: ## Start frontend only
	cd frontend && npm run dev

# ── Testing ───────────────────────────────────────────────────────────────────

test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend tests (pytest)
	cd backend && .venv/bin/pytest tests/ -v

test-frontend: ## Run frontend tests (jest)
	cd frontend && npm test -- --watchAll=false

# ── Database ──────────────────────────────────────────────────────────────────

migrate: ## Run Alembic migrations to head
	backend/.venv/bin/python backend/run_migrations.py

migration: ## Create a new Alembic revision with autogenerate (use MSG="description")
	@[ -n "$(MSG)" ] || (echo 'Usage: make migration MSG="add jd_summary to companies"' && exit 1)
	backend/.venv/bin/alembic -c alembic.ini revision --autogenerate -m "$(MSG)"

# ── Memory & Vector Store ─────────────────────────────────────────────────────

rebuild-index: ## Rebuild ChromaDB vector index from stories_bank.md
	cd backend && .venv/bin/python -c \
	  "from app.memory.vector_store import StoryVectorStore; import asyncio; asyncio.run(StoryVectorStore().rebuild_index())"
	@echo "✓ Index rebuilt"

# ── Data Management ───────────────────────────────────────────────────────────

backup: ## Backup memory + database with timestamp
	@mkdir -p $(BACKUP_DIR)
	@TIMESTAMP=$$(date +%Y-%m-%d-%H%M) && \
	  tar -czf $(BACKUP_DIR)/futuro-backup-$$TIMESTAMP.tar.gz \
	    $(DATA_DIR)/memory $(DATA_DIR)/futuro.db && \
	  echo "✓ Backup saved: $(BACKUP_DIR)/futuro-backup-$$TIMESTAMP.tar.gz"

restore: ## Restore from backup — BACKUP=path/to/backup.tar.gz
	@[ -n "$(BACKUP)" ] || (echo "Usage: make restore BACKUP=path/to/backup.tar.gz" && exit 1)
	tar -xzf $(BACKUP) -C .
	make migrate
	make rebuild-index
	@echo "✓ Restored from $(BACKUP)"

# ── Docker ────────────────────────────────────────────────────────────────────

docker-dev: ## Start via docker-compose (dev)
	docker-compose up --build

docker-prod: ## Start via docker-compose (prod)
	docker-compose -f docker-compose.prod.yml up --build -d

docker-down: ## Stop all containers
	docker-compose down

# ── Deployment ────────────────────────────────────────────────────────────────

deploy: ## Deploy to Fly.io
	fly deploy

deploy-secrets: ## Push all secrets to Fly.io
	@source .env && \
	  fly secrets set \
	    ANTHROPIC_API_KEY=$$ANTHROPIC_API_KEY \
	    JWT_SECRET=$$JWT_SECRET \
	    USER_PASSWORD_HASH="$$USER_PASSWORD_HASH" \
	    CLAUDE_MODEL=$$CLAUDE_MODEL

logs: ## Tail Fly.io logs
	fly logs

# ── Ollama ────────────────────────────────────────────────────────────────────

ollama-setup: ## Pull recommended Qwen 2.5 + embed models for Futuro
	@echo "\n→ Pulling Ollama models for Futuro...\n"
	ollama pull qwen2.5:7b
	ollama pull nomic-embed-text
	@echo "\n✓ Models ready. Update OLLAMA_CHAT_MODEL in .env then make dev\n"

ollama-status: ## Check Ollama health and available models
	@curl -s http://localhost:11434/api/tags | python3 -c \
	  "import json,sys; models=json.load(sys.stdin).get('models',[]); \
	   [print(f'  {m[\"name\"]:40} {round(m[\"size\"]/1e9,1)} GB') for m in models]" \
	  2>/dev/null || echo "  Ollama not running. Start with: ollama serve"
