"""Task 5: explicit proof that the mandatory disclaimer (Requirement 5.1)
is present, verbatim, on every user-facing result and its audit record,
across all four outcome categories.
"""

from __future__ import annotations

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

EXPECTED_DISCLAIMER = "Supports human triage only; not emergency, legal or medical advice."


def _assert_disclaimer(result) -> None:
    assert result.disclaimer == DISCLAIMER == EXPECTED_DISCLAIMER
    assert result.audit_record.disclaimer == DISCLAIMER == EXPECTED_DISCLAIMER


def test_disclaimer_present_on_proceed(tmp_path):
    bedrock = StubBedrockClient(proposals={PROCEED_FIXTURE_ID: PROCEED_PROPOSAL})
    decider = StubDeciderClient(answers=PROCEED_ANSWERS)
    result = pipeline.run(
        PROCEED_REPORT, bedrock, decider, THRESHOLD, fixture_id=PROCEED_FIXTURE_ID, audit_dir=tmp_path
    )
    _assert_disclaimer(result)


def test_disclaimer_present_on_guide(tmp_path):
    bedrock = StubBedrockClient(
        proposals={GUIDE_FIXTURE_ID: GUIDE_PROPOSAL},
        follow_up_questions={GUIDE_FIXTURE_ID: GUIDE_FOLLOW_UP_QUESTIONS},
    )
    decider = StubDeciderClient(answers=GUIDE_ANSWERS)
    result = pipeline.run(
        GUIDE_REPORT, bedrock, decider, THRESHOLD, fixture_id=GUIDE_FIXTURE_ID, audit_dir=tmp_path
    )
    _assert_disclaimer(result)


def test_disclaimer_present_on_escalate_conflicting_evidence(tmp_path):
    bedrock = StubBedrockClient(
        proposals={ESCALATE_FIXTURE_ID: ESCALATE_PROPOSAL},
        conflict_summaries={ESCALATE_FIXTURE_ID: ESCALATE_CONFLICT_SUMMARY},
    )
    decider = StubDeciderClient(answers=ESCALATE_ANSWERS)
    result = pipeline.run(
        ESCALATE_REPORT, bedrock, decider, THRESHOLD, fixture_id=ESCALATE_FIXTURE_ID, audit_dir=tmp_path
    )
    _assert_disclaimer(result)


def test_disclaimer_present_on_escalate_failure(tmp_path):
    report = SyntheticReport(
        report_id="disclaimer-failure-demo",
        text="SYNTHETIC DEMO REPORT for disclaimer-on-failure test only.",
    )
    proposal = ProposedToolCall(
        tool_name="create_action_brief", issue_category="a", location="b",
        onset_or_duration="c", urgency="d",
    )
    failure = FailureRecord(
        stage=FailureStage.DECIDER,
        error_type="timeout",
        error_message="Decider did not respond in time.",
        occurred_at=datetime.now(timezone.utc),
    )
    bedrock = StubBedrockClient(proposals={"disclaimer-failure-demo": proposal})
    decider = StubDeciderClient(
        answers={}, failures={"disclaimer-failure-demo:overall": failure}
    )
    result = pipeline.run(report, bedrock, decider, THRESHOLD, audit_dir=tmp_path)
    _assert_disclaimer(result)
