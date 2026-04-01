"""baseline schema

Revision ID: 0001_baseline
Revises:
Create Date: 2026-04-01 18:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("role_title", sa.String(length=200), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("stage", sa.String(length=50), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sponsorship_confirmed", sa.Boolean(), nullable=False),
        sa.Column("salary_range", sa.String(length=100), nullable=True),
        sa.Column("source", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("applied_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("intent", sa.String(length=50), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("memory_updates", sa.Text(), nullable=True),
        sa.Column("mood_score", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )

    op.create_table(
        "scout_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("search_term", sa.String(length=200), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=False),
        sa.Column("distance_miles", sa.Integer(), nullable=False),
        sa.Column("sites", sa.String(length=200), nullable=False),
        sa.Column("results_wanted", sa.Integer(), nullable=False),
        sa.Column("hours_old", sa.Integer(), nullable=False),
        sa.Column("is_remote", sa.Boolean(), nullable=True),
        sa.Column("min_score", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("schedule_hours", sa.Integer(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )

    op.create_table(
        "company_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("stage_from", sa.String(length=50), nullable=True),
        sa.Column("stage_to", sa.String(length=50), nullable=True),
        sa.Column("happened_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )

    op.create_table(
        "scout_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("config_id", sa.Integer(), sa.ForeignKey("scout_configs.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("jobs_found", sa.Integer(), nullable=False),
        sa.Column("jobs_new", sa.Integer(), nullable=False),
        sa.Column("jobs_scored", sa.Integer(), nullable=False),
        sa.Column("error_msg", sa.Text(), nullable=True),
    )

    op.create_table(
        "interviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("company_events.id"), nullable=True),
        sa.Column("round_name", sa.String(length=100), nullable=False),
        sa.Column("interviewer", sa.String(length=200), nullable=True),
        sa.Column("format", sa.String(length=50), nullable=True),
        sa.Column("duration_min", sa.Integer(), nullable=True),
        sa.Column("questions_asked", sa.Text(), nullable=True),
        sa.Column("my_answers", sa.Text(), nullable=True),
        sa.Column("strong_moments", sa.Text(), nullable=True),
        sa.Column("weak_moments", sa.Text(), nullable=True),
        sa.Column("gut_feeling", sa.Integer(), nullable=True),
        sa.Column("next_steps", sa.Text(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("happened_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )

    op.create_table(
        "job_listings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("url_hash", sa.String(length=64), nullable=False),
        sa.Column("job_url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("company", sa.String(length=200), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("is_remote", sa.Boolean(), nullable=False),
        sa.Column("salary_min", sa.Float(), nullable=True),
        sa.Column("salary_max", sa.Float(), nullable=True),
        sa.Column("salary_currency", sa.String(length=10), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("description_snippet", sa.Text(), nullable=True),
        sa.Column("site", sa.String(length=50), nullable=False),
        sa.Column("date_posted", sa.String(length=50), nullable=True),
        sa.Column("job_type", sa.String(length=100), nullable=True),
        sa.Column("config_id", sa.Integer(), sa.ForeignKey("scout_configs.id"), nullable=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("scout_runs.id"), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("score_summary", sa.Text(), nullable=True),
        sa.Column("score_pros", sa.Text(), nullable=True),
        sa.Column("score_cons", sa.Text(), nullable=True),
        sa.Column("sponsorship_likely", sa.Boolean(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("user_note", sa.Text(), nullable=True),
        sa.Column("seen_at", sa.DateTime(), nullable=True),
        sa.Column("actioned_at", sa.DateTime(), nullable=True),
        sa.Column("discovered_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("url_hash"),
    )


def downgrade() -> None:
    op.drop_table("job_listings")
    op.drop_table("interviews")
    op.drop_table("scout_runs")
    op.drop_table("company_events")
    op.drop_table("scout_configs")
    op.drop_table("sessions")
    op.drop_table("companies")
