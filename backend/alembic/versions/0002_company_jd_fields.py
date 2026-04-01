"""add company jd fields

Revision ID: 0002_company_jd
Revises: 0001_baseline
Create Date: 2026-04-01 18:45:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_company_jd"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("companies") as batch_op:
        batch_op.add_column(sa.Column("job_description_text", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("jd_summary", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("jd_requirements_json", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("jd_responsibilities_json", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("jd_skills_json", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("work_mode", sa.String(length=20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("companies") as batch_op:
        batch_op.drop_column("work_mode")
        batch_op.drop_column("jd_skills_json")
        batch_op.drop_column("jd_responsibilities_json")
        batch_op.drop_column("jd_requirements_json")
        batch_op.drop_column("jd_summary")
        batch_op.drop_column("job_description_text")
