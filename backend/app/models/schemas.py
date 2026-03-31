from datetime import datetime
from typing import Literal, Any
from pydantic import BaseModel, Field


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Chat ──────────────────────────────────────────────────────────────────────

class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class ChatRequest(BaseModel):
    message: str
    history: list[Message] = []
    session_id: str | None = None

class MemoryUpdate(BaseModel):
    file: str
    section: str
    action: Literal["append", "replace", "create"]
    content: str
    reason: str


# ── Memory ────────────────────────────────────────────────────────────────────

class MemoryFileResponse(BaseModel):
    filename: str
    content: str
    last_modified: datetime | None
    last_commit: str | None

class MemoryWriteRequest(BaseModel):
    content: str

class ApplyUpdateRequest(BaseModel):
    section: str
    action: Literal["append", "replace", "create"]
    content: str
    reason: str


# ── Campaign ──────────────────────────────────────────────────────────────────

VALID_STAGES = [
    "RESEARCHING", "APPLIED", "SCREENING",
    "TECHNICAL", "ONSITE", "OFFER",
    "CLOSED_WON", "CLOSED_LOST", "WITHDREW"
]

class CompanyCreate(BaseModel):
    name: str
    role_title: str
    url: str | None = None
    priority: Literal["HIGH", "MEDIUM", "LOW"] = "MEDIUM"
    notes: str | None = None
    sponsorship_confirmed: bool = False
    salary_range: str | None = None
    source: str | None = None

class CompanyUpdate(BaseModel):
    stage: str | None = None
    priority: str | None = None
    notes: str | None = None
    salary_range: str | None = None
    sponsorship_confirmed: bool | None = None

class StageUpdateRequest(BaseModel):
    stage: str
    description: str | None = None

class CompanyEventResponse(BaseModel):
    id: int
    event_type: str
    description: str | None
    stage_from: str | None
    stage_to: str | None
    happened_at: datetime

    model_config = {"from_attributes": True}

class CompanyResponse(BaseModel):
    id: int
    name: str
    role_title: str
    url: str | None
    stage: str
    priority: str
    notes: str | None
    sponsorship_confirmed: bool
    salary_range: str | None
    source: str | None
    created_at: datetime
    updated_at: datetime
    applied_at: datetime | None
    events: list[CompanyEventResponse] = []

    model_config = {"from_attributes": True}

class CampaignStats(BaseModel):
    total_active: int
    by_stage: dict[str, int]
    response_rate: float
    avg_days_to_response: float | None
    offers: int


# ── Stories ───────────────────────────────────────────────────────────────────

class StorySearchRequest(BaseModel):
    query: str
    n_results: int = Field(default=3, ge=1, le=10)

class StorySearchResult(BaseModel):
    story_id: str
    title: str
    one_liner: str
    themes: list[str]
    distance: float
    result_metric: str | None


# ── Interviews ────────────────────────────────────────────────────────────────

class InterviewCreate(BaseModel):
    company_id: int
    round_name: str
    format: str | None = None
    interviewer: str | None = None
    scheduled_at: datetime | None = None

class DebriefRequest(BaseModel):
    questions_asked: list[str] = []
    strong_moments: str | None = None
    weak_moments: str | None = None
    gut_feeling: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = None

class InterviewResponse(BaseModel):
    id: int
    company_id: int
    round_name: str
    format: str | None
    interviewer: str | None
    gut_feeling: int | None
    scheduled_at: datetime | None
    happened_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
