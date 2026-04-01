import os
import sqlite3

os.environ.update({
    "ANTHROPIC_API_KEY": "sk-ant-test",
    "JWT_SECRET": "test-secret-32-chars-long-enough-x",
    "USER_PASSWORD_HASH": "$2b$12$2w9iWu05oig3NbS1uYPjtu9LQyqW5kYJho25k0Ri49myuM8X/4Qx2",
    "DATA_DIR": "/tmp/futuro-migrate-test/data",
    "MEMORY_DIR": "/tmp/futuro-migrate-test/data/memory",
    "CHROMA_DIR": "/tmp/futuro-migrate-test/data/chroma",
    "DB_PATH": "/tmp/futuro-migrate-test/data/futuro.db",
    "GIT_AUTO_COMMIT": "false",
    "DEBUG": "true",
    "ALLOWED_ORIGINS": '["http://localhost:3000"]',
})

from sqlalchemy import create_engine

from app.database import _run_migrations, _sqlite_tables, _sync_db_url
from app.models.db import Base


def test_fresh_database_runs_baseline_migration(tmp_path):
    db_path = tmp_path / "fresh.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"

    _run_migrations(db_url=db_url, db_path=db_path)

    tables = _sqlite_tables(db_path)
    assert "alembic_version" in tables
    assert "companies" in tables
    assert "job_listings" in tables
    assert "scout_configs" in tables


def test_legacy_database_is_stamped_without_dropping_tables(tmp_path):
    db_path = tmp_path / "legacy.db"
    sync_engine = create_engine(
        _sync_db_url(f"sqlite+aiosqlite:///{db_path}"),
        connect_args={"check_same_thread": False},
    )
    try:
        Base.metadata.create_all(sync_engine)
    finally:
        sync_engine.dispose()

    assert "alembic_version" not in _sqlite_tables(db_path)

    _run_migrations(db_url=f"sqlite+aiosqlite:///{db_path}", db_path=db_path)

    tables = _sqlite_tables(db_path)
    assert "alembic_version" in tables
    assert "companies" in tables
    assert "job_listings" in tables


def test_empty_alembic_version_table_is_treated_as_legacy(tmp_path):
    db_path = tmp_path / "half_bootstrapped.db"
    sync_engine = create_engine(
        _sync_db_url(f"sqlite+aiosqlite:///{db_path}"),
        connect_args={"check_same_thread": False},
    )
    try:
        Base.metadata.create_all(sync_engine)
        with sync_engine.begin() as conn:
            conn.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
    finally:
        sync_engine.dispose()

    _run_migrations(db_url=f"sqlite+aiosqlite:///{db_path}", db_path=db_path)

    tables = _sqlite_tables(db_path)
    assert "alembic_version" in tables


def test_latest_head_includes_company_jd_columns(tmp_path):
    db_path = tmp_path / "latest.db"
    _run_migrations(db_url=f"sqlite+aiosqlite:///{db_path}", db_path=db_path)

    with sqlite3.connect(db_path) as conn:
        cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(companies)").fetchall()
        }

    assert "job_description_text" in cols
    assert "jd_summary" in cols
    assert "jd_requirements_json" in cols
    assert "jd_responsibilities_json" in cols
    assert "jd_skills_json" in cols
    assert "work_mode" in cols
