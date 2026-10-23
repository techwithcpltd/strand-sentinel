"""Task 5: failure-path coverage not already proven by Task 4's
test_pipeline.py — the initial Bedrock failure, and failures during the
second Bedrock call on each of the Guide and Escalate paths.
"""

from __future__ import annotations

from datetime import datetime, timezone

from strand_sentinel import pipeline
from strand_sentinel.adapters.bedrock_client import StubBedrockClient
from strand_sentinel.adapters.decider_client import StubDeciderClient
from strand_sentinel.constants import CONFIDENCE_THRESHOLD_PLACEHOLDER, Outcome
from strand_sentinel.models import (
    FailureRecord,
    FailureStage,
    GroundednessAnswer,
    ProposedToolCall,
    SyntheticReport,
)

THRESHOLD = CONFIDENCE_THRESHOLD_PLACEHOLDER


def test_initial_bedrock_failure_escalates_without_any_decider_call(tmp_path):
    report = SyntheticReport(
        report_id="initial-bedrock-failure",
        text="SYNTHETIC DEMO REPORT for initial Bedrock failure test only.",
    )
    failure = FailureRecord(
        stage=FailureStage.BEDROCK,
        error_type="unavailable",
        error_message="Bedrock did not respond.",
        occurred_at=datetime.now(timezone.utc),
    )
    # No `proposals` entry for this report_id: if propose_tool_call somehow
    # fell through to the normal lookup instead of returning the failure,
    # this stub would raise KeyError, failing the test loudly.
    bedrock = StubBedrockClient(proposals={}, propose_failures={"initial-bedrock-failure": failure})
    # No `answers` entries at all: if the pipeline ever called the Decider
    # after a Bedrock failure, this stub would raise KeyError.
    decider = StubDeciderClient(answers={})

    result = pipeline.run(report, bedrock, decider, THRESHOLD, audit_dir=tmp_path)

    assert result.outcome is Outcome.ESCALATE
    assert result.action_brief is None
    assert result.follow_up_questions is None
    assert result.escalation_summary is not None
    assert "bedrock" in result.escalation_summary
    assert result.audit_record.summary_source == "deterministic_failure_summary"
    assert result.audit_record.failure_reason is not None
    assert result.audit_record.failure_reason["stage"] == "bedrock"
    assert result.audit_record.bedrock_proposal is None
    assert result.audit_record.decider_questions == []
    assert result.audit_record.decider_results == []


def test_secondary_bedrock_failure_on_guide_followup_escalates(tmp_path):
    report = SyntheticReport(
        report_id="secondary-failure-guide",
        text="SYNTHETIC DEMO REPORT for secondary Bedrock failure (Guide) test only.",
    )
    proposal = ProposedToolCall(
        tool_name="create_action_brief",
        issue_category="a",
        location="b",
        onset_or_duration="c",
        urgency="d",
    )
    answers = {
        "secondary-failure-guide:overall": GroundednessAnswer(
            question_id="secondary-failure-guide:overall", value="missing_evidence", confidence=0.9
        ),
        "secondary-failure-guide:issue_category": GroundednessAnswer(
            question_id="secondary-failure-guide:issue_category", value="yes", confidence=0.9
        ),
        "secondary-failure-guide:location": GroundednessAnswer(
            question_id="secondary-failure-guide:location", value="yes", confidence=0.9
        ),
        "secondary-failure-guide:onset_or_duration": GroundednessAnswer(
            question_id="secondary-failure-guide:onset_or_duration", value="no", confidence=0.9
        ),
        "secondary-failure-guide:urgency": GroundednessAnswer(
            question_id="secondary-failure-guide:urgency", value="yes", confidence=0.9
        ),
    }
    follow_up_failure = FailureRecord(
        stage=FailureStage.BEDROCK,
        error_type="timeout",
        error_message="Bedrock did not respond while drafting follow-up questions.",
        occurred_at=datetime.now(timezone.utc),
    )
    bedrock = StubBedrockClient(
        proposals={"secondary-failure-guide": proposal},
        follow_up_failures={"secondary-failure-guide": follow_up_failure},
        # No `follow_up_questions` entry: proves the failure path is taken,
        # not a lucky fallthrough to a scripted success value.
    )
    decider = StubDeciderClient(answers=answers)

    result = pipeline.run(report, bedrock, decider, THRESHOLD, audit_dir=tmp_path)

    assert result.outcome is Outcome.ESCALATE
    assert result.action_brief is None
    assert result.follow_up_questions is None
    assert result.audit_record.summary_source == "deterministic_failure_summary"
    assert result.audit_record.failure_reason is not None
    assert result.audit_record.failure_reason["stage"] == "bedrock"
    assert result.audit_record.failure_reason["error_type"] == "timeout"


def test_secondary_bedrock_failure_on_conflict_summary_escalates(tmp_path):
    report = SyntheticReport(
        report_id="secondary-failure-escalate",
        text="SYNTHETIC DEMO REPORT for secondary Bedrock failure (Escalate) test only.",
    )
    proposal = ProposedToolCall(
        tool_name="create_action_brief",
        issue_category="a",
        location="b",
        onset_or_duration="c",
        urgency="d",
    )
    answers = {
        "secondary-failure-escalate:overall": GroundednessAnswer(
            question_id="secondary-failure-escalate:overall",
            value="conflicting_evidence",
            confidence=0.9,
        ),
        "secondary-failure-escalate:issue_category": GroundednessAnswer(
            question_id="secondary-failure-escalate:issue_category", value="yes", confidence=0.9
        ),
        "secondary-failure-escalate:location": GroundednessAnswer(
            question_id="secondary-failure-escalate:location", value="yes", confidence=0.9
        ),
        "secondary-failure-escalate:onset_or_duration": GroundednessAnswer(
            question_id="secondary-failure-escalate:onset_or_duration", value="no", confidence=0.9
        ),
        "secondary-failure-escalate:urgency": GroundednessAnswer(
            question_id="secondary-failure-escalate:urgency", value="no", confidence=0.9
        ),
    }
    summary_failure = FailureRecord(
        stage=FailureStage.BEDROCK,
        error_type="timeout",
        error_message="Bedrock did not respond while drafting the conflict summary.",
        occurred_at=datetime.now(timezone.utc),
    )
    bedrock = StubBedrockClient(
        proposals={"secondary-failure-escalate": proposal},
        conflict_summary_failures={"secondary-failure-escalate": summary_failure},
        # No `conflict_summaries` entry: proves the failure path is taken.
    )
    decider = StubDeciderClient(answers=answers)

    result = pipeline.run(report, bedrock, decider, THRESHOLD, audit_dir=tmp_path)

    assert result.outcome is Outcome.ESCALATE
    assert result.action_brief is None
    assert result.audit_record.summary_source == "deterministic_failure_summary"
    assert result.audit_record.failure_reason is not None
    assert result.audit_record.failure_reason["stage"] == "bedrock"
