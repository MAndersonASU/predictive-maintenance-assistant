"""Finalize the engineering log after the Day 17 implementation commit exists."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
REPORT_PATH = PROJECT_ROOT / "outputs" / "metropt3_isolation_forest_test_report.json"
LOG_PATH = PROJECT_ROOT / "ENGINEERING_LOG.md"
MARKER = "### Frozen Machine-Learning Release"


class MLReleaseLogError(ValueError):
    pass


def update_log(implementation_commit: str, complete_test_count: int) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", implementation_commit):
        raise MLReleaseLogError("Implementation commit must be a full 40-character lowercase Git SHA.")
    if complete_test_count <= 0:
        raise MLReleaseLogError("Complete test count must be positive.")
    if not REPORT_PATH.is_file():
        raise MLReleaseLogError(f"Final test report does not exist: {REPORT_PATH}")
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8-sig"))
    if report.get("status") != "frozen_after_one_time_test_evaluation":
        raise MLReleaseLogError("Final test report is not frozen.")
    if not LOG_PATH.is_file():
        raise MLReleaseLogError(f"Engineering log does not exist: {LOG_PATH}")

    text = LOG_PATH.read_text(encoding="utf-8")
    if MARKER in text:
        raise MLReleaseLogError("Frozen machine-learning release is already recorded in the engineering log.")

    model = report["frozen_model"]
    test = report["advanced_model_test"]
    block = f"""

{MARKER}

The governed machine-learning workstream was finalized with one separately authorized held-out evaluation of the already-frozen Isolation Forest candidate.

Verified release evidence:

- Implementation commit: `{implementation_commit}`
- Complete repository test suite: {complete_test_count} passing tests
- Frozen candidate: `{model['candidate_id']}`
- Frozen threshold: `{model['threshold']}`
- Frozen model SHA-256: `{model['model_sha256']}`
- Eligible advanced-model test rows scored: {test['scored_rows']}
- Documented-event coverage fraction: {test['documented_event_coverage_fraction']}
- Mean first-alarm latency for covered events: {test['mean_first_alarm_latency_seconds_for_covered_events']} seconds
- Alarms per 24 observed hours: {test['alarms_per_24_observed_hours']}
- Advanced-model test access: consumed exactly once by the governed release evaluation
- Test-driven refit, feature change, threshold change, or candidate reselection: none
- Robust-distance detector: retained as the finalized transparent benchmark
- Generated model, score Parquet, and JSON evidence: excluded from Git under governed ignore rules

The machine-learning release documentation now includes the model card, held-out evaluation report, data/feature governance summary, architecture, reproducibility commands, and updated README. The next core milestone is the governed technical-document corpus with deterministic extraction and chunking.
"""
    LOG_PATH.write_text(text.rstrip() + block.rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Record the verified frozen ML release in ENGINEERING_LOG.md.")
    parser.add_argument("--implementation-commit", required=True)
    parser.add_argument("--complete-test-count", type=int, required=True)
    args = parser.parse_args()
    try:
        update_log(args.implementation_commit, args.complete_test_count)
    except (MLReleaseLogError, OSError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}")
        return 1
    print("Engineering log updated with frozen machine-learning release evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
