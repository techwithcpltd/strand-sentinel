"""Task 5: explicit proof that the simulated create_action_brief tool is
called exactly once on Proceed and never called on Guide or Escalate, plus
a proof that the pipeline has no real-world side effect outside the caller-
configured audit directory.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from strand_sentinel import pipeline
from strand_sentinel.adapters.bedrock_client import StubBedrockClient
from strand_sentinel.adapters.decider_client import StubDeciderClient
from strand_sentinel.constants import CONFIDENCE_THRESHOLD_PLACEHOLDER, Outcome
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


def _spy(original):
    calls: list[tuple] = []

    def wrapper(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    return wrapper, calls


def test_tool_called_exactly_once_on_proceed(monkeypatch, tmp_path):
    from strand_sentinel import tool as tool_module

    wrapper, calls = _spy(tool_module.create_action_brief)
    monkeypatch.setattr(pipeline, "create_action_brief", wrapper)

    bedrock = StubBedrockClient(proposals={PROCEED_FIXTURE_ID: PROCEED_PROPOSAL})
    decider = StubDeciderClient(answers=PROCEED_ANSWERS)

    result = pipeline.run(
        PROCEED_REPORT, bedrock, decider, THRESHOLD, fixture_id=PROCEED_FIXTURE_ID, audit_dir=tmp_path
    )

    assert result.outcome is Outcome.PROCEED
    assert len(calls) == 1
    assert set(result.action_brief.keys()) == {
        "tool_name",
        "issue_category",
        "location",
        "onset_or_duration",
        "urgency",
    }


def test_tool_never_called_on_guide(monkeypatch, tmp_path):
    from strand_sentinel import tool as tool_module

    wrapper, calls = _spy(tool_module.create_action_brief)
    monkeypatch.setattr(pipeline, "create_action_brief", wrapper)

    bedrock = StubBedrockClient(
        proposals={GUIDE_FIXTURE_ID: GUIDE_PROPOSAL},
        follow_up_questions={GUIDE_FIXTURE_ID: GUIDE_FOLLOW_UP_QUESTIONS},
    )
    decider = StubDeciderClient(answers=GUIDE_ANSWERS)

    result = pipeline.run(
        GUIDE_REPORT, bedrock, decider, THRESHOLD, fixture_id=GUIDE_FIXTURE_ID, audit_dir=tmp_path
    )

    assert result.outcome is Outcome.GUIDE
    assert len(calls) == 0


def test_tool_never_called_on_escalate_conflicting_evidence(monkeypatch, tmp_path):
    from strand_sentinel import tool as tool_module

    wrapper, calls = _spy(tool_module.create_action_brief)
    monkeypatch.setattr(pipeline, "create_action_brief", wrapper)

    bedrock = StubBedrockClient(
        proposals={ESCALATE_FIXTURE_ID: ESCALATE_PROPOSAL},
        conflict_summaries={ESCALATE_FIXTURE_ID: ESCALATE_CONFLICT_SUMMARY},
    )
    decider = StubDeciderClient(answers=ESCALATE_ANSWERS)

    result = pipeline.run(
        ESCALATE_REPORT, bedrock, decider, THRESHOLD, fixture_id=ESCALATE_FIXTURE_ID, audit_dir=tmp_path
    )

    assert result.outcome is Outcome.ESCALATE
    assert len(calls) == 0


def test_tool_never_called_on_escalate_failure(monkeypatch, tmp_path):
    from strand_sentinel import tool as tool_module

    wrapper, calls = _spy(tool_module.create_action_brief)
    monkeypatch.setattr(pipeline, "create_action_brief", wrapper)

    report = SyntheticReport(
        report_id="tool-blocking-failure-demo",
        text="SYNTHETIC DEMO REPORT for tool-blocking failure test only.",
    )
    failure = FailureRecord(
        stage=FailureStage.BEDROCK,
        error_type="unavailable",
        error_message="Bedrock did not respond.",
        occurred_at=datetime.now(timezone.utc),
    )
    bedrock = StubBedrockClient(
        proposals={}, propose_failures={"tool-blocking-failure-demo": failure}
    )
    decider = StubDeciderClient(answers={})

    result = pipeline.run(report, bedrock, decider, THRESHOLD, audit_dir=tmp_path)

    assert result.outcome is Outcome.ESCALATE
    assert len(calls) == 0


def test_no_real_world_side_effects_outside_configured_audit_dir(tmp_path):
    real_audit_dir = Path(__file__).resolve().parents[1] / "audit"
    before = set(real_audit_dir.iterdir()) if real_audit_dir.exists() else set()

    bedrock = StubBedrockClient(proposals={PROCEED_FIXTURE_ID: PROCEED_PROPOSAL})
    decider = StubDeciderClient(answers=PROCEED_ANSWERS)
    result = pipeline.run(
        PROCEED_REPORT, bedrock, decider, THRESHOLD, fixture_id=PROCEED_FIXTURE_ID, audit_dir=tmp_path
    )

    after = set(real_audit_dir.iterdir()) if real_audit_dir.exists() else set()
    assert before == after, "pipeline.run wrote outside the caller-configured audit_dir"

    # And confirm the audit record really did land in the directory we asked for.
    assert result.audit_path.parent == tmp_path
    assert list(tmp_path.iterdir()) == [result.audit_path]
