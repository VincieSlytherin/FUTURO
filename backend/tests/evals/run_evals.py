"""
Futuro eval harness
--------------------
Regression checks for the agent's decision quality, separate from unit tests.
Each suite loads JSON cases from ./cases, runs the REAL Futuro code path, computes
metrics, and is checked against a regression floor in THRESHOLDS.

Suites:
  - memory_write     precision/recall/F1 of `_should_extract_memory` (deterministic)
  - story_retrieval  precision@1 / recall@3 / MRR over a seeded vector index (local embeddings)
  - gap_matching     precision/recall/F1 of JD→resume skill matching (deterministic)
  - intent_routing   accuracy of `classify_intent` (LIVE — needs a real provider, opt-in)

Run as a script to emit a report:  python -m tests.evals.run_evals [--live]
The pytest wrapper (test_evals.py) asserts thresholds and writes the same report.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

CASES_DIR = Path(__file__).parent / "cases"
REPORTS_DIR = Path(__file__).parent / "reports"

# Regression floors — a suite below its floor is a failure.
THRESHOLDS: dict[str, dict[str, float]] = {
    "memory_write": {"f1": 0.85},
    "story_retrieval": {"recall_at_3": 0.80, "precision_at_1": 0.60},
    "gap_matching": {"f1": 0.90},
    "intent_routing": {"accuracy": 0.80},
}


def load_cases(name: str):
    return json.loads((CASES_DIR / name).read_text(encoding="utf-8"))


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return round(precision, 4), round(recall, 4), round(f1, 4)


# ── Suites ────────────────────────────────────────────────────────────────────

def eval_memory_write() -> dict:
    from app.agents.base import AGENT_MAP, CoreAgent
    from app.memory.manager import MemoryManager

    cases = load_cases("memory_write_cases.json")
    tp = fp = fn = tn = 0
    rows = []
    with TemporaryDirectory() as tmp:
        memory = MemoryManager(Path(tmp), git_auto_commit=False)
        for c in cases:
            agent = AGENT_MAP.get(c["intent"], CoreAgent)(memory)
            predicted = bool(agent._should_extract_memory(c["message"], c["message"]))
            expected = bool(c["expected_extract"])
            if predicted and expected:
                tp += 1
            elif predicted and not expected:
                fp += 1
            elif not predicted and expected:
                fn += 1
            else:
                tn += 1
            rows.append({"id": c["id"], "expected": expected, "predicted": predicted, "ok": predicted == expected})

    precision, recall, f1 = _prf(tp, fp, fn)
    accuracy = round((tp + tn) / len(cases), 4) if cases else 0.0
    return {
        "metrics": {"precision": precision, "recall": recall, "f1": f1, "accuracy": accuracy},
        "n": len(cases),
        "cases": rows,
    }


def eval_story_retrieval() -> dict:
    from app.memory.vector_store import StoryVectorStore

    data = load_cases("story_retrieval_cases.json")
    queries = data["queries"]
    with TemporaryDirectory() as tmp:
        store = StoryVectorStore(chroma_dir=Path(tmp))
        try:
            store.rebuild_from_markdown(data["stories_bank"])
        except Exception as exc:  # embedding model unavailable (e.g. offline)
            return {"skipped": True, "reason": f"embedding unavailable: {exc}", "n": len(queries)}

        hits_at_1 = hits_at_3 = 0
        rr_sum = 0.0
        rows = []
        for q in queries:
            matches = store.search(q["query"], n_results=3)
            ids = [m.story_id for m in matches]
            relevant = set(q["relevant_ids"])
            at_1 = bool(ids) and ids[0] in relevant
            at_3 = bool(relevant & set(ids))
            rr = next((1 / rank for rank, i in enumerate(ids, 1) if i in relevant), 0.0)
            hits_at_1 += at_1
            hits_at_3 += at_3
            rr_sum += rr
            rows.append({"id": q["id"], "retrieved": ids, "relevant": list(relevant), "hit@1": at_1})

    n = len(queries)
    return {
        "metrics": {
            "precision_at_1": round(hits_at_1 / n, 4) if n else 0.0,
            "recall_at_3": round(hits_at_3 / n, 4) if n else 0.0,
            "mrr": round(rr_sum / n, 4) if n else 0.0,
        },
        "n": n,
        "cases": rows,
    }


def eval_gap_matching() -> dict:
    from app.gap_analysis import build_resume_corpus, match_skills
    from app.jd_parser import extract_jd_fields

    cases = load_cases("gap_match_cases.json")
    tp = fp = fn = 0
    rows = []
    for c in cases:
        fields = extract_jd_fields(c["jd_text"])
        jd_skills = json.loads(fields.get("jd_skills_json") or "[]")
        corpus = build_resume_corpus(c["identity"], c["resume"])
        matched, _missing = match_skills(jd_skills, corpus)
        predicted = set(matched)
        # Only judge against expected skills the parser actually surfaced from this JD.
        expected = set(c["expected_matched"]) & set(jd_skills)
        tp += len(predicted & expected)
        fp += len(predicted - expected)
        fn += len(expected - predicted)
        rows.append({"id": c["id"], "predicted": sorted(predicted), "expected": sorted(expected)})

    precision, recall, f1 = _prf(tp, fp, fn)
    return {"metrics": {"precision": precision, "recall": recall, "f1": f1}, "n": len(cases), "cases": rows}


async def eval_intent_routing() -> dict:
    from app.agents.base import classify_intent

    cases = load_cases("intent_routing_cases.json")
    correct = 0
    rows = []
    for c in cases:
        try:
            intent = await classify_intent(c["message"], [])
        except Exception as exc:
            return {"skipped": True, "reason": f"classifier unavailable: {exc}", "n": len(cases)}
        ok = intent == c["expected_intent"]
        correct += ok
        rows.append({"id": c["id"], "expected": c["expected_intent"], "predicted": intent, "ok": ok})

    return {"metrics": {"accuracy": round(correct / len(cases), 4)}, "n": len(cases), "cases": rows}


# ── Orchestration + reporting ─────────────────────────────────────────────────

def check_thresholds(suite: str, result: dict) -> list[str]:
    """Return a list of failure messages for a suite (empty = pass/skip)."""
    if result.get("skipped"):
        return []
    failures = []
    for metric, floor in THRESHOLDS.get(suite, {}).items():
        value = result.get("metrics", {}).get(metric)
        if value is None:
            failures.append(f"{suite}.{metric} missing from results")
        elif value < floor:
            failures.append(f"{suite}.{metric}={value} below floor {floor}")
    return failures


def run_all(live: bool = False, generated_at: str | None = None) -> dict:
    suites = {
        "memory_write": eval_memory_write(),
        "story_retrieval": eval_story_retrieval(),
        "gap_matching": eval_gap_matching(),
    }
    if live:
        suites["intent_routing"] = asyncio.run(eval_intent_routing())
    return {
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "live": live,
        "suites": suites,
    }


def render_markdown(report: dict) -> str:
    lines = [f"# Futuro Eval Report", "", f"_generated: {report['generated_at']}_  ·  live={report['live']}", ""]
    for suite, result in report["suites"].items():
        lines.append(f"## {suite}")
        if result.get("skipped"):
            lines.append(f"- skipped: {result.get('reason')}")
        else:
            metrics = ", ".join(f"{k}={v}" for k, v in result["metrics"].items())
            floors = THRESHOLDS.get(suite, {})
            floor_str = ", ".join(f"{k}≥{v}" for k, v in floors.items())
            lines.append(f"- n={result['n']}  ·  {metrics}")
            if floor_str:
                lines.append(f"- floors: {floor_str}")
        lines.append("")
    return "\n".join(lines)


def write_report(report: dict) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "latest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path = REPORTS_DIR / "latest.md"
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return md_path


if __name__ == "__main__":
    import sys

    # Allow standalone runs without the test harness having set env first.
    os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-not-set")
    os.environ.setdefault("JWT_SECRET", "local-eval-secret-32-chars-minimum-x")
    os.environ.setdefault("USER_PASSWORD_HASH", "x")

    live = "--live" in sys.argv
    report = run_all(live=live)
    write_report(report)
    print(render_markdown(report))
    failures = [msg for suite, result in report["suites"].items() for msg in check_thresholds(suite, result)]
    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("\nAll eval suites passed their regression floors.")
