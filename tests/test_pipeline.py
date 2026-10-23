"""Task 4 evidence: all three fixtures run end-to-end through the
orchestrator (stub adapters), plus one adapter-failure injection proving
Escalate with the deterministic local summary and no second Bedrock call.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from strand_sentinel import pipeline
from strand_sentinel.adapters.bedrock_client import StubBedrockClient
from strand_sentinel.adapters.decider_client import StubDeciderClient
from strand_sentinel.constants import CONFIDENCE_THRESHOLD_PLACEHOLDER, DISCLAIMER, Outcome
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


def _assert_audit_schema_complete(audit_path) -> None:
    data = json.loads(audit_path.read_text(encoding="utf-8"))
    assert _AUDIT_RECORD_FIELDS.issubset(data.keys())
    assert data["disclaimer"] == DISCLAIMER


def test_proceed_fixture_end_to_end(tmp_path):
    bedrock = StubBedrockClient(proposals={PROCEED_FIXTURE_ID: PROCEED_PROPOSAL})
    decider = StubDeciderClient(answers=PROCEED_ANSWERS)

    result = pipeline.run(
        PROCEED_REPORT,
        bedrock,
        decider,
        THRESHOLD,
        fixture_id=PROCEED_FIXTURE_ID,
        audit_dir=tmp_path,
    )

    assert result.outcome is Outcome.PROCEED
    assert result.disclaimer == DISCLAIMER
    # Tool invoked only on Proceed: action_brief populated, others not.
    assert result.action_brief is not None
    assert result.action_brief["issue_category"] == PROCEED_PROPOSAL.issue_category
    assert result.follow_up_questions is None
    assert result.escalation_summary is None
    assert result.audit_record.final_outcome == "proceed"
    assert result.audit_record.behaviour_taken == "tool executed"
    assert result.audit_path.exists()
    _assert_audit_schema_complete(result.audit_path)


def test_guide_fixture_end_to_end(tmp_path):
    bedrock = StubBedrockClient(
        proposals={GUIDE_FIXTURE_ID: GUIDE_PROPOSAL},
        follow_up_questions={GUIDE_FIXTURE_ID: GUIDE_FOLLOW_UP_QUESTIONS},
    )
    decider = StubDeciderClient(answers=GUIDE_ANSWERS)

    result = pipeline.run(
        GUIDE_REPORT,
        bedrock,
        decider,
        THRESHOLD,
        fixture_id=GUIDE_FIXTURE_ID,
        audit_dir=tmp_path,
    )

    assert result.outcome is Outcome.GUIDE
    assert result.disclaimer == DISCLAIMER
    # Tool NOT invoked on Guide.
    assert result.action_brief is None
    assert result.follow_up_questions == GUIDE_FOLLOW_UP_QUESTIONS
    assert result.escalation_summary is None
    assert result.audit_record.final_outcome == "guide"
    assert result.audit_record.behaviour_taken == "follow-up questions generated"
    assert result.audit_path.exists()
    _assert_audit_schema_complete(result.audit_path)


def test_escalate_fixture_end_to_end(tmp_path):
    bedrock = StubBedrockClient(
        proposals={ESCALATE_FIXTURE_ID: ESCALATE_PROPOSAL},
        conflict_summaries={ESCALATE_FIXTURE_ID: ESCALATE_CONFLICT_SUMMARY},
    )
    decider = StubDeciderClient(answers=ESCALATE_ANSWERS)

    result = pipeline.run(
        ESCALATE_REPORT,
        bedrock,
        decider,
        THRESHOLD,
        fixture_id=ESCALATE_FIXTURE_ID,
        audit_dir=tmp_path,
    )

    assert result.outcome is Outcome.ESCALATE
    assert result.disclaimer == DISCLAIMER
    # Tool NOT invoked on Escalate.
    assert result.action_brief is None
    assert result.follow_up_questions is None
    assert result.escalation_summary == ESCALATE_CONFLICT_SUMMARY
    assert result.audit_record.final_outcome == "escalate"
    assert result.audit_record.summary_source == "bedrock_conflict_summary"
    assert result.audit_record.failure_reason is None
    assert result.audit_path.exists()
    _assert_audit_schema_complete(result.audit_path)


def test_decider_failure_escalates_without_a_second_bedrock_call(tmp_path):
    report = SyntheticReport(
        report_id="failure-demo",
        text="SYNTHETIC DEMO REPORT — fabricated for this test only.",
    )
    proposal = ProposedToolCall(
        tool_name="create_action_brief",
        issue_category="x",
        location="y",
        onset_or_duration="z",
        urgency="w",
    )
    # Deliberately no follow_up_questions / conflict_summaries entries: if
    # the pipeline ever called either of those after a Decider failure, this
    # stub would raise KeyError, failing the test loudly rather than
    # silently passing.
    bedrock = StubBedrockClient(proposals={"failure-demo": proposal})

    failure = FailureRecord(
        stage=FailureStage.DECIDER,
        error_type="timeout",
        error_message="Decider did not respond in time.",
        occurred_at=datetime.now(timezone.utc),
    )
    decider = StubDeciderClient(answers={}, failures={"failure-demo:overall": failure})

    result = pipeline.run(report, bedrock, decider, THRESHOLD, audit_dir=tmp_path)

    assert result.outcome is Outcome.ESCALATE
    assert result.disclaimer == DISCLAIMER
    assert result.action_brief is None
    assert result.follow_up_questions is None
    assert result.escalation_summary is not None
    assert "decider" in result.escalation_summary
    assert result.audit_record.summary_source == "deterministic_failure_summary"
    assert result.audit_record.failure_reason is not None
    assert result.audit_record.failure_reason["stage"] == "decider"
    assert result.audit_path.exists()
    _assert_audit_schema_complete(result.audit_path)
