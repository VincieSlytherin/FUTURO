"""add company_size to scout_configs and company_num_employees to job_listings

Revision ID: 0003_scout_company_size
Revises: 0002_company_jd
Create Date: 2026-07-07
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_scout_company_size"
down_revision = "0002_company_jd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("scout_configs") as batch_op:
        batch_op.add_column(sa.Column("company_size", sa.String(length=50), nullable=True))

    with op.batch_alter_table("job_listings") as batch_op:
        batch_op.add_column(sa.Column("company_num_employees", sa.String(length=100), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("job_listings") as batch_op:
        batch_op.drop_column("company_num_employees")

    with op.batch_alter_table("scout_configs") as batch_op:
        batch_op.drop_column("company_size")
