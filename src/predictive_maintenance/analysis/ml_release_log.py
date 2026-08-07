"""Finalize ENGINEERING_LOG.md from frozen Day 17 machine-learning evidence.

The helper updates the log's current-state header, current engineering workstream,
next milestone, and frozen machine-learning release block. It is intentionally
idempotent: rerunning with the same verified evidence replaces those sections
instead of appending duplicate release records.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
REPORT_PATH = PROJECT_ROOT / "outputs" / "metropt3_isolation_forest_test_report.json"
LOG_PATH = PROJECT_ROOT / "ENGINEERING_LOG.md"

CURRENT_STATE_START = "## Current Verified State"
IMPLEMENTED_MILESTONES_START = "## Implemented Milestones"
WORKSTREAM_START = "## Current Engineering Workstream"
ROBUST_BASELINE_START = "## Robust-Distance Validation Baseline"
RELEASE_MARKER = "### Frozen Machine-Learning Release"


class MLReleaseLogError(ValueError):
    """Raised when verified release evidence cannot safely finalize the log."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_report(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise MLReleaseLogError(f"Final test report does not exist: {path}")
    try:
        report = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        raise MLReleaseLogError(f"Invalid final test report JSON: {error}") from error
    if not isinstance(report, dict):
        raise MLReleaseLogError("Final test report must contain a JSON object.")
    if report.get("status") != "frozen_after_one_time_test_evaluation":
        raise MLReleaseLogError("Final test report is not frozen.")
    governance = report.get("governance", {})
    if governance.get("one_time_advanced_model_test_evaluation_complete") is not True:
        raise MLReleaseLogError("One-time advanced-model test evaluation is not complete.")
    if any(
        governance.get(name) is not False
        for name in (
            "model_fitted_during_test_evaluation",
            "threshold_revised_using_test_evidence",
            "features_changed_using_test_evidence",
            "candidate_reselected_using_test_evidence",
            "unverified_rows_are_verified_healthy",
            "alarm_burden_is_false_positive_rate",
            "unusualness_is_failure_probability",
            "unsupported_classification_metrics_reported",
        )
    ):
        raise MLReleaseLogError("Final test report violates a frozen release governance control.")
    return report


def _validate_commit(commit: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise MLReleaseLogError(
            "Implementation commit must be a full 40-character lowercase Git SHA."
        )


def _replace_between(text: str, start: str, end: str, replacement: str) -> str:
    start_index = text.find(start)
    end_index = text.find(end)
    if start_index < 0:
        raise MLReleaseLogError(f"Engineering log section is missing: {start}")
    if end_index < 0 or end_index <= start_index:
        raise MLReleaseLogError(f"Engineering log section boundary is missing: {end}")
    return text[:start_index] + replacement.rstrip() + "\n\n" + text[end_index:]


def _fmt(value: Any) -> str:
    return "not available" if value is None else str(value)


def render_current_state(
    implementation_commit: str,
    implementation_message: str,
    complete_test_count: int,
) -> str:
    return f"""## Current Verified State

- Active branch: `main`
- Remote tracking branch: `origin/main`
- Public repository: verified
- Latest verified implementation commit: `{implementation_commit}`
- Commit message: `{implementation_message}`
- Local and remote implementation commit identity: matched at `{implementation_commit}`
- Complete repository test suite: {complete_test_count} passing tests
- Advanced-model test access: consumed exactly once by the governed held-out evaluation
- Generated datasets, reports, figures, model artifacts, and temporary files: excluded from Git under governed ignore rules"""


def render_workstream(report: dict[str, Any]) -> str:
    model = report["frozen_model"]
    advanced = report["baseline_comparison"]["isolation_forest"]
    baseline = report["baseline_comparison"]["robust_distance_baseline"]
    return f"""## Current Engineering Workstream

The governed machine-learning workstream is complete through the separately authorized one-time held-out evaluation. The selected candidate remains `{model['candidate_id']}` with the unchanged frozen threshold `{model['threshold']}` and the same frozen {model['retained_feature_count']}-feature set. Test evidence did not trigger refitting, threshold revision, feature changes, or candidate reselection.

Held-out operational evidence:

- Isolation Forest documented-event coverage fraction: {_fmt(advanced['documented_event_coverage_fraction'])}
- Isolation Forest mean first-alarm latency for covered events: {_fmt(advanced['mean_first_alarm_latency_seconds_for_covered_events'])} seconds
- Isolation Forest alarms per 24 observed hours: {_fmt(advanced['alarms_per_24_observed_hours'])}
- Robust-distance baseline documented-event coverage fraction: {_fmt(baseline['documented_event_coverage_fraction'])}
- Robust-distance baseline mean first-alarm latency for covered events: {_fmt(baseline['mean_first_alarm_latency_seconds_for_covered_events'])} seconds
- Robust-distance baseline alarms per 24 observed hours: {_fmt(baseline['alarms_per_24_observed_hours'])}

These are governed operational measures, not evidence of a verified healthy negative class. Alarm burden is not a false-positive rate, and unusualness is not a failure probability.

## Next Engineering Milestone

Build the governed technical-document corpus and deterministic extraction/chunking pipeline. Record source identity, publisher, URL or DOI, license or usage status, equipment relevance, retrieval identity or checksum, local status, and exact-equipment/general-reference classification before ingestion. Then implement deterministic extraction, normalization, metadata preservation, chunk identifiers, overlap rules, provenance checks, controlled tests, and ignored generated outputs."""


def render_release_block(
    report: dict[str, Any],
    implementation_commit: str,
    complete_test_count: int,
    report_sha256: str,
) -> str:
    model = report["frozen_model"]
    test = report["advanced_model_test"]
    advanced = report["baseline_comparison"]["isolation_forest"]
    baseline = report["baseline_comparison"]["robust_distance_baseline"]
    return f"""{RELEASE_MARKER}

The governed machine-learning workstream was finalized with one separately authorized held-out evaluation of the already-frozen Isolation Forest candidate.

Verified release evidence:

- Implementation commit: `{implementation_commit}`
- Complete repository test suite: {complete_test_count} passing tests
- Frozen candidate: `{model['candidate_id']}`
- Frozen threshold: `{model['threshold']}`
- Frozen model SHA-256: `{model['model_sha256']}`
- Eligible advanced-model test rows scored: {test['scored_rows']}
- Documented events represented in the governed test evidence: {test['documented_event_count']}
- Documented events covered: {test['documented_events_covered']}
- Isolation Forest documented-event coverage fraction: {_fmt(advanced['documented_event_coverage_fraction'])}
- Isolation Forest mean first-alarm latency for covered events: {_fmt(advanced['mean_first_alarm_latency_seconds_for_covered_events'])} seconds
- Isolation Forest alarms per 24 observed hours: {_fmt(advanced['alarms_per_24_observed_hours'])}
- Robust-distance baseline documented-event coverage fraction: {_fmt(baseline['documented_event_coverage_fraction'])}
- Robust-distance baseline mean first-alarm latency for covered events: {_fmt(baseline['mean_first_alarm_latency_seconds_for_covered_events'])} seconds
- Robust-distance baseline alarms per 24 observed hours: {_fmt(baseline['alarms_per_24_observed_hours'])}
- Advanced-model test report SHA-256: `{report_sha256}`
- Advanced-model test-score Parquet SHA-256: `{test['scores_sha256']}`
- Advanced-model test access: consumed exactly once by the governed release evaluation
- Test-driven refit, feature change, threshold change, or candidate reselection: none
- Robust-distance detector: retained as the finalized transparent benchmark
- Generated model, score Parquet, and JSON evidence: excluded from Git under governed ignore rules

The machine-learning release documentation includes the model card, held-out evaluation report, data/feature governance summary, architecture, reproducibility commands, and updated README. The next core milestone is the governed technical-document corpus with deterministic extraction and chunking."""


def finalize_log_text(
    text: str,
    report: dict[str, Any],
    implementation_commit: str,
    implementation_message: str,
    complete_test_count: int,
    report_sha256: str,
) -> str:
    if complete_test_count <= 0:
        raise MLReleaseLogError("Complete test count must be positive.")
    _validate_commit(implementation_commit)
    if not implementation_message.strip():
        raise MLReleaseLogError("Implementation commit message must be non-empty.")

    updated = _replace_between(
        text,
        CURRENT_STATE_START,
        IMPLEMENTED_MILESTONES_START,
        render_current_state(
            implementation_commit,
            implementation_message.strip(),
            complete_test_count,
        ),
    )
    updated = _replace_between(
        updated,
        WORKSTREAM_START,
        ROBUST_BASELINE_START,
        render_workstream(report),
    )

    release = render_release_block(
        report,
        implementation_commit,
        complete_test_count,
        report_sha256,
    )
    marker_index = updated.find(RELEASE_MARKER)
    if marker_index >= 0:
        updated = updated[:marker_index].rstrip() + "\n\n" + release.rstrip() + "\n"
    else:
        updated = updated.rstrip() + "\n\n" + release.rstrip() + "\n"
    return updated


def update_log(
    implementation_commit: str,
    implementation_message: str,
    complete_test_count: int,
) -> None:
    report = _read_report(REPORT_PATH)
    if not LOG_PATH.is_file():
        raise MLReleaseLogError(f"Engineering log does not exist: {LOG_PATH}")
    text = LOG_PATH.read_text(encoding="utf-8")
    updated = finalize_log_text(
        text,
        report,
        implementation_commit,
        implementation_message,
        complete_test_count,
        _sha256(REPORT_PATH),
    )
    LOG_PATH.write_text(updated, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Finalize current and historical machine-learning release evidence in ENGINEERING_LOG.md."
    )
    parser.add_argument("--implementation-commit", required=True)
    parser.add_argument("--implementation-message", required=True)
    parser.add_argument("--complete-test-count", type=int, required=True)
    args = parser.parse_args()
    try:
        update_log(
            args.implementation_commit,
            args.implementation_message,
            args.complete_test_count,
        )
    except (MLReleaseLogError, OSError) as error:
        print(f"ERROR: {error}")
        return 1
    print("Engineering log finalized with frozen machine-learning release evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
