"""Task 5: proves Requirement 4.7 (low confidence -> Guide, non-conflicting
case) end-to-end through the full pipeline, not just the pure router
(which Task 2's test_routing.py already covers at the unit level).
"""

from __future__ import annotations

from strand_sentinel import pipeline
from strand_sentinel.adapters.bedrock_client import StubBedrockClient
from strand_sentinel.adapters.decider_client import StubDeciderClient
from strand_sentinel.constants import CONFIDENCE_THRESHOLD_PLACEHOLDER, Outcome
from strand_sentinel.models import GroundednessAnswer, ProposedToolCall, SyntheticReport

THRESHOLD = CONFIDENCE_THRESHOLD_PLACEHOLDER


def test_low_confidence_without_conflict_routes_to_guide_end_to_end(tmp_path):
    report = SyntheticReport(
        report_id="low-confidence-demo",
        text="SYNTHETIC DEMO REPORT for low-confidence routing test only.",
    )
    proposal = ProposedToolCall(
        tool_name="create_action_brief",
        issue_category="a",
        location="b",
        onset_or_duration="c",
        urgency="d",
    )
    # overall = grounded, every per-argument answer = yes, but confidence is
    # below CONFIDENCE_THRESHOLD_PLACEHOLDER everywhere -- Requirement 4.7.
    answers = {
        "low-confidence-demo:overall": GroundednessAnswer(
            question_id="low-confidence-demo:overall", value="grounded", confidence=0.30
        ),
        "low-confidence-demo:issue_category": GroundednessAnswer(
            question_id="low-confidence-demo:issue_category", value="yes", confidence=0.30
        ),
        "low-confidence-demo:location": GroundednessAnswer(
            question_id="low-confidence-demo:location", value="yes", confidence=0.40
        ),
        "low-confidence-demo:onset_or_duration": GroundednessAnswer(
            question_id="low-confidence-demo:onset_or_duration", value="yes", confidence=0.45
        ),
        "low-confidence-demo:urgency": GroundednessAnswer(
            question_id="low-confidence-demo:urgency", value="yes", confidence=0.49
        ),
    }
    bedrock = StubBedrockClient(
        proposals={"low-confidence-demo": proposal},
        follow_up_questions={
            "low-confidence-demo": ("Can you confirm these details with more certainty?",)
        },
    )
    decider = StubDeciderClient(answers=answers)

    result = pipeline.run(report, bedrock, decider, THRESHOLD, audit_dir=tmp_path)

    assert result.outcome is Outcome.GUIDE
    assert result.action_brief is None
    assert result.follow_up_questions is not None
    assert result.audit_record.final_outcome == "guide"
    assert result.audit_record.summary_source is None
    assert result.audit_record.failure_reason is None
