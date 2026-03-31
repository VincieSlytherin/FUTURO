from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.providers.router import init_providers
from app.api import auth, chat, memory, campaign, stories, interviews, intake, scout
from app.api import providers as providers_api
from app.workers.job_monitor import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.memory_dir.mkdir(parents=True, exist_ok=True)
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    await init_db()
    await init_providers(settings)
    if settings.scout_enabled:
        await start_scheduler()
    yield
    # Shutdown
    await stop_scheduler()


app = FastAPI(
    title="Futuro API",
    version="0.4.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(memory.router)
app.include_router(campaign.router)
app.include_router(stories.router)
app.include_router(interviews.router)
app.include_router(intake.router)
app.include_router(scout.router)
app.include_router(providers_api.router)


@app.get("/api/health")
async def health():
    from app.providers.router import provider_status
    return {
        "status": "ok",
        "version": "0.4.0",
        "providers": provider_status(),
    }
