from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Anthropic
    anthropic_api_key: str
    claude_model: str = "claude-sonnet-4-5"
    max_tokens: int = 8192

    # Auth
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 7
    user_password_hash: str

    # Storage
    data_dir: Path = Path("./data")
    memory_dir: Path = Path("./data/memory")
    chroma_dir: Path = Path("./data/chroma")
    db_path: Path = Path("./data/futuro.db")

    # Memory
    git_auto_commit: bool = True

    # ── Provider routing ──────────────────────────────────────────────────────
    # Global fallback: "claude" | "ollama" | "auto"
    # "auto" = probe Ollama at startup; use it if available, else Claude
    llm_provider: str = "auto"

    # Per-task overrides (None = use llm_provider)
    chat_provider:     str | None = None   # main Futuro conversation
    classify_provider: str | None = None   # intent classification
    score_provider:    str | None = None   # job scout scoring
    embed_provider:    str | None = None   # ChromaDB embeddings

    # ── Ollama settings ───────────────────────────────────────────────────────
    ollama_enabled:    bool  = True
    ollama_base_url:   str   = "http://localhost:11434"
    ollama_chat_model: str   = "qwen2.5:7b"        # swap to :14b or :32b as needed
    ollama_embed_model: str  = "nomic-embed-text"   # or qwen2.5:7b, mxbai-embed-large
    ollama_timeout:    float = 120.0                # seconds; 32B needs more
    ollama_keep_alive: str   = "10m"                # keep model hot in VRAM

    # Job Scout
    scout_enabled: bool = True
    scout_default_location: str = "San Francisco, CA"
    scout_default_sites: str = "linkedin,indeed,glassdoor"

    # Server
    debug: bool = False
    log_level: str = "info"
    allowed_origins: list[str] = ["http://localhost:3000"]

    @property
    def db_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.db_path}"


settings = Settings()
