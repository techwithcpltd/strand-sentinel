"""Task 5: explicit audit-record proof across all four outcome categories —
full Design Section 8 schema completeness, and that summary_source /
failure_reason correctly distinguish Proceed, Guide, conflicting-evidence
Escalate, and failure-triggered Escalate.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from strand_sentinel import pipeline
from strand_sentinel.adapters.bedrock_client import StubBedrockClient
from strand_sentinel.adapters.decider_client import StubDeciderClient
from strand_sentinel.constants import CONFIDENCE_THRESHOLD_PLACEHOLDER, DISCLAIMER
from strand_sentinel.fixtures import (
    ESCALATE_ANSWERS,
    ESCALATE_CONFLICT_SUMMARY,
    ESCALATE_FIXTURE_ID,
    ESCALATE_PROPOSAL,
    ESCALATE_REPORT,
    GUIDE_ANSWERS,
    GUIDE_FIXTURE_ID,
    GUIDE_FOLLOW_UP_QUESTIONS,
    GUIDE_PROPOSAL,
    GUIDE_REPORT,
    PROCEED_ANSWERS,
    PROCEED_FIXTURE_ID,
    PROCEED_PROPOSAL,
    PROCEED_REPORT,
)
from strand_sentinel.models import FailureRecord, FailureStage, ProposedToolCall, SyntheticReport

THRESHOLD = CONFIDENCE_THRESHOLD_PLACEHOLDER

_AUDIT_RECORD_FIELDS = {
    "run_id",
    "timestamp",
    "fixture_id",
    "input_report",
    "bedrock_proposal",
    "decider_questions",
    "decider_results",
    "confidence_threshold",
    "final_outcome",
    "behaviour_taken",
    "failure_reason",
    "summary_source",
    "latency_ms",
    "model_identifiers",
    "disclaimer",
}


def _run_all_four(tmp_path):
    results = {}

    bedrock = StubBedrockClient(proposals={PROCEED_FIXTURE_ID: PROCEED_PROPOSAL})
    decider = StubDeciderClient(answers=PROCEED_ANSWERS)
    results["proceed"] = pipeline.run(
        PROCEED_REPORT, bedrock, decider, THRESHOLD,
        fixture_id=PROCEED_FIXTURE_ID, audit_dir=tmp_path / "proceed",
    )

    bedrock = StubBedrockClient(
        proposals={GUIDE_FIXTURE_ID: GUIDE_PROPOSAL},
        follow_up_questions={GUIDE_FIXTURE_ID: GUIDE_FOLLOW_UP_QUESTIONS},
    )
    decider = StubDeciderClient(answers=GUIDE_ANSWERS)
    results["guide"] = pipeline.run(
        GUIDE_REPORT, bedrock, decider, THRESHOLD,
        fixture_id=GUIDE_FIXTURE_ID, audit_dir=tmp_path / "guide",
    )

    bedrock = StubBedrockClient(
        proposals={ESCALATE_FIXTURE_ID: ESCALATE_PROPOSAL},
        conflict_summaries={ESCALATE_FIXTURE_ID: ESCALATE_CONFLICT_SUMMARY},
    )
    decider = StubDeciderClient(answers=ESCALATE_ANSWERS)
    results["escalate_conflict"] = pipeline.run(
        ESCALATE_REPORT, bedrock, decider, THRESHOLD,
        fixture_id=ESCALATE_FIXTURE_ID, audit_dir=tmp_path / "escalate_conflict",
    )

    report = SyntheticReport(
        report_id="audit-schema-failure-demo",
        text="SYNTHETIC DEMO REPORT for audit schema test only.",
    )
    proposal = ProposedToolCall(
        tool_name="create_action_brief", issue_category="x", location="y",
        onset_or_duration="z", urgency="w",
    )
    bedrock = StubBedrockClient(proposals={"audit-schema-failure-demo": proposal})
    failure = FailureRecord(
        stage=FailureStage.DECIDER,
        error_type="timeout",
        error_message="Decider did not respond in time.",
        occurred_at=datetime.now(timezone.utc),
    )
    decider = StubDeciderClient(
        answers={}, failures={"audit-schema-failure-demo:overall": failure}
    )
    results["escalate_failure"] = pipeline.run(
        report, bedrock, decider, THRESHOLD, audit_dir=tmp_path / "escalate_failure"
    )

    return results


def test_audit_schema_complete_for_all_outcomes(tmp_path):
    results = _run_all_four(tmp_path)

    for name, result in results.items():
        data = json.loads(result.audit_path.read_text(encoding="utf-8"))
        assert _AUDIT_RECORD_FIELDS.issubset(data.keys()), f"{name}: missing fields"
        assert data["disclaimer"] == DISCLAIMER, name
        assert data["confidence_threshold"] == THRESHOLD, name


def test_summary_source_and_failure_reason_distinguish_outcomes(tmp_path):
    results = _run_all_four(tmp_path)

    assert results["proceed"].audit_record.summary_source is None
    assert results["proceed"].audit_record.failure_reason is None

    assert results["guide"].audit_record.summary_source is None
    assert results["guide"].audit_record.failure_reason is None

    assert results["escalate_conflict"].audit_record.summary_source == "bedrock_conflict_summary"
    assert results["escalate_conflict"].audit_record.failure_reason is None

    assert results["escalate_failure"].audit_record.summary_source == "deterministic_failure_summary"
    assert results["escalate_failure"].audit_record.failure_reason is not None
    assert results["escalate_failure"].audit_record.failure_reason["stage"] == "decider"
