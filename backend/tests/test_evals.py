"""
Pytest wrapper around the eval harness (tests/evals/run_evals.py).

Deterministic suites (memory_write, story_retrieval, gap_matching) run in CI without API keys
and assert each metric stays above its regression floor. The live intent-routing suite needs a
real provider and only runs when FUTURO_EVAL_LIVE=1. Every run writes a report to evals/reports/.
"""
import os

import bcrypt
import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")
os.environ.setdefault("JWT_SECRET", "test-secret-32-chars-long-enough-x")
os.environ.setdefault("USER_PASSWORD_HASH", bcrypt.hashpw(b"testpass", bcrypt.gensalt()).decode())
os.environ.setdefault("DATA_DIR", "/tmp/futuro-test/data")
os.environ.setdefault("MEMORY_DIR", "/tmp/futuro-test/data/memory")
os.environ.setdefault("CHROMA_DIR", "/tmp/futuro-test/data/chroma")
os.environ.setdefault("DB_PATH", "/tmp/futuro-test/data/futuro.db")
os.environ.setdefault("GIT_AUTO_COMMIT", "false")

from tests.evals import run_evals  # noqa: E402

LIVE = os.environ.get("FUTURO_EVAL_LIVE") == "1"


@pytest.fixture(scope="module")
def report():
    rep = run_evals.run_all(live=LIVE)
    run_evals.write_report(rep)
    return rep


def test_memory_write_meets_floor(report):
    result = report["suites"]["memory_write"]
    failures = run_evals.check_thresholds("memory_write", result)
    assert not failures, failures
    assert result["metrics"]["f1"] >= run_evals.THRESHOLDS["memory_write"]["f1"]


def test_story_retrieval_meets_floor(report):
    result = report["suites"]["story_retrieval"]
    if result.get("skipped"):
        pytest.skip(result.get("reason", "story retrieval skipped"))
    failures = run_evals.check_thresholds("story_retrieval", result)
    assert not failures, failures


def test_gap_matching_meets_floor(report):
    result = report["suites"]["gap_matching"]
    failures = run_evals.check_thresholds("gap_matching", result)
    assert not failures, failures
    assert result["metrics"]["f1"] >= run_evals.THRESHOLDS["gap_matching"]["f1"]


def test_report_is_written(report):
    path = run_evals.REPORTS_DIR / "latest.json"
    assert path.exists()


@pytest.mark.skipif(not LIVE, reason="intent routing eval needs a live provider (set FUTURO_EVAL_LIVE=1)")
def test_intent_routing_meets_floor(report):
    result = report["suites"]["intent_routing"]
    if result.get("skipped"):
        pytest.skip(result.get("reason", "intent routing skipped"))
    failures = run_evals.check_thresholds("intent_routing", result)
    assert not failures, failures
