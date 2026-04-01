from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

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
    data_dir: Path = BACKEND_ROOT / "data"
    memory_dir: Path = BACKEND_ROOT / "data/memory"
    chroma_dir: Path = BACKEND_ROOT / "data/chroma"
    db_path: Path = BACKEND_ROOT / "data/futuro.db"
    custom_instructions_path: Path = BACKEND_ROOT / "data/custom_instructions.json"

    # Memory
    git_auto_commit: bool = True

    # Notifications
    notify_email: str = ""
    gmail_app_password: str = ""

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

    def model_post_init(self, __context) -> None:
        self.data_dir = self._resolve_path(self.data_dir)
        self.memory_dir = self._resolve_path(self.memory_dir)
        self.chroma_dir = self._resolve_path(self.chroma_dir)
        self.db_path = self._resolve_path(self.db_path)
        self.custom_instructions_path = self._resolve_path(self.custom_instructions_path)

    @property
    def db_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.db_path}"

    @staticmethod
    def _resolve_path(path: Path) -> Path:
        return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


settings = Settings()
