from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Text, Float, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    role_title: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    stage: Mapped[str] = mapped_column(String(50), default="RESEARCHING")
    priority: Mapped[str] = mapped_column(String(20), default="MEDIUM")
    notes: Mapped[str | None] = mapped_column(Text)
    sponsorship_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    salary_range: Mapped[str | None] = mapped_column(String(100))
    source: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    applied_at: Mapped[datetime | None] = mapped_column(DateTime)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)

    events: Mapped[list["CompanyEvent"]] = relationship(back_populates="company", order_by="CompanyEvent.happened_at.desc()")
    interviews: Mapped[list["Interview"]] = relationship(back_populates="company")


class CompanyEvent(Base):
    __tablename__ = "company_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    stage_from: Mapped[str | None] = mapped_column(String(50))
    stage_to: Mapped[str | None] = mapped_column(String(50))
    happened_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    company: Mapped["Company"] = relationship(back_populates="events")


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("company_events.id"))
    round_name: Mapped[str] = mapped_column(String(100), nullable=False)
    interviewer: Mapped[str | None] = mapped_column(String(200))
    format: Mapped[str | None] = mapped_column(String(50))
    duration_min: Mapped[int | None] = mapped_column(Integer)
    questions_asked: Mapped[str | None] = mapped_column(Text)  # JSON array
    my_answers: Mapped[str | None] = mapped_column(Text)
    strong_moments: Mapped[str | None] = mapped_column(Text)
    weak_moments: Mapped[str | None] = mapped_column(Text)
    gut_feeling: Mapped[int | None] = mapped_column(Integer)
    next_steps: Mapped[str | None] = mapped_column(Text)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime)
    happened_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    company: Mapped["Company"] = relationship(back_populates="interviews")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    intent: Mapped[str] = mapped_column(String(50), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    memory_updates: Mapped[str | None] = mapped_column(Text)  # JSON
    mood_score: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ── Job Scout ─────────────────────────────────────────────────────────────────

class ScoutConfig(Base):
    """One row = one saved search config (user can have multiple)."""
    __tablename__ = "scout_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)      # "Bay Area AI roles"
    search_term: Mapped[str] = mapped_column(String(200), nullable=False) # "AI Engineer"
    location: Mapped[str] = mapped_column(String(200), default="San Francisco, CA")
    distance_miles: Mapped[int] = mapped_column(Integer, default=50)
    sites: Mapped[str] = mapped_column(String(200), default="linkedin,indeed,glassdoor")  # CSV
    results_wanted: Mapped[int] = mapped_column(Integer, default=25)
    hours_old: Mapped[int] = mapped_column(Integer, default=72)          # only jobs posted in last N hours
    is_remote: Mapped[bool | None] = mapped_column(Boolean, default=None) # None = any
    min_score: Mapped[int] = mapped_column(Integer, default=60)          # only surface jobs ≥ this score
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    schedule_hours: Mapped[int] = mapped_column(Integer, default=12)     # re-scan every N hours
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    runs: Mapped[list["ScoutRun"]] = relationship(back_populates="config", order_by="ScoutRun.started_at.desc()")


class ScoutRun(Base):
    """Log of each scrape run — how many found, how many new, errors."""
    __tablename__ = "scout_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    config_id: Mapped[int] = mapped_column(ForeignKey("scout_configs.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="RUNNING")   # RUNNING|DONE|ERROR
    jobs_found: Mapped[int] = mapped_column(Integer, default=0)
    jobs_new: Mapped[int] = mapped_column(Integer, default=0)
    jobs_scored: Mapped[int] = mapped_column(Integer, default=0)
    error_msg: Mapped[str | None] = mapped_column(Text)

    config: Mapped["ScoutConfig"] = relationship(back_populates="runs")


class JobListing(Base):
    """A scraped + scored job listing."""
    __tablename__ = "job_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)  # sha256 of job_url
    job_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    company: Mapped[str] = mapped_column(String(200), nullable=False)
    location: Mapped[str | None] = mapped_column(String(200))
    is_remote: Mapped[bool] = mapped_column(Boolean, default=False)
    salary_min: Mapped[float | None] = mapped_column(Float)
    salary_max: Mapped[float | None] = mapped_column(Float)
    salary_currency: Mapped[str | None] = mapped_column(String(10))
    description: Mapped[str | None] = mapped_column(Text)               # truncated for storage
    description_snippet: Mapped[str | None] = mapped_column(Text)       # 300 chars for display
    site: Mapped[str] = mapped_column(String(50))                       # linkedin / indeed / etc
    date_posted: Mapped[str | None] = mapped_column(String(50))
    job_type: Mapped[str | None] = mapped_column(String(100))           # full-time / contract
    # Scout metadata
    config_id: Mapped[int | None] = mapped_column(ForeignKey("scout_configs.id"))
    run_id: Mapped[int | None] = mapped_column(ForeignKey("scout_runs.id"))
    # Claude scoring
    score: Mapped[int | None] = mapped_column(Integer)                  # 0-100
    score_summary: Mapped[str | None] = mapped_column(Text)             # 1-2 sentence reason
    score_pros: Mapped[str | None] = mapped_column(Text)                # JSON list
    score_cons: Mapped[str | None] = mapped_column(Text)                # JSON list
    sponsorship_likely: Mapped[bool | None] = mapped_column(Boolean)
    # User actions
    status: Mapped[str] = mapped_column(String(30), default="NEW")
    # NEW | SAVED | PIPELINE | DISMISSED | APPLIED
    user_note: Mapped[str | None] = mapped_column(Text)
    seen_at: Mapped[datetime | None] = mapped_column(DateTime)
    actioned_at: Mapped[datetime | None] = mapped_column(DateTime)
    discovered_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
