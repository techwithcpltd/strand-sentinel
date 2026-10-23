"""Standalone proof of the #guardrails routing policy, independent of the
rest of this repository's test suite layout.

This intentionally duplicates (in spirit, not verbatim) the coverage in
../../../tests/test_routing.py: the point of this file is that someone who
has only copied the `patterns/evidence_groundedness_gate/` directory out of
this repository can still run `pytest` here and see the policy proven,
without needing the rest of the project's tests.

Uses the real `strand_sentinel.routing.route` — the reusable policy's
reference implementation — not a reimplementation.
"""

from __future__ import annotations

from datetime import datetime, timezone

from strand_sentinel.constants import EscalateCause, Outcome
from strand_sentinel.models import FailureRecord, FailureStage, GateOutcome, GroundednessAnswer
from strand_sentinel.routing import route

THRESHOLD = 0.5  # illustrative threshold for this standalone proof only


def _answer(question_id: str, value: str, confidence: float) -> GroundednessAnswer:
    return GroundednessAnswer(question_id=question_id, value=value, confidence=confidence)


def test_proceed_when_grounded_and_confident():
    gate_outcome = GateOutcome(
        overall_answer=_answer("overall", "grounded", 0.9),
        per_argument_answers=(
            _answer("issue_category", "yes", 0.9),
            _answer("location", "yes", 0.9),
            _answer("onset_or_duration", "yes", 0.9),
            _answer("urgency", "yes", 0.9),
        ),
        ungrounded_arguments=(),
        lowest_confidence=0.9,
    )

    result = route(gate_outcome, THRESHOLD)

    assert result.outcome is Outcome.PROCEED
    assert result.escalate_cause is None


def test_guide_when_missing_evidence():
    gate_outcome = GateOutcome(
        overall_answer=_answer("overall", "missing_evidence", 0.9),
        per_argument_answers=(
            _answer("issue_category", "yes", 0.9),
            _answer("location", "no", 0.85),
            _answer("onset_or_duration", "yes", 0.9),
            _answer("urgency", "yes", 0.9),
        ),
        ungrounded_arguments=("location",),
        lowest_confidence=0.85,
    )

    result = route(gate_outcome, THRESHOLD)

    assert result.outcome is Outcome.GUIDE
    assert result.escalate_cause is None


def test_escalate_when_conflicting_evidence():
    gate_outcome = GateOutcome(
        overall_answer=_answer("overall", "conflicting_evidence", 0.9),
        per_argument_answers=(
            _answer("issue_category", "yes", 0.9),
            _answer("location", "no", 0.3),
            _answer("onset_or_duration", "yes", 0.9),
            _answer("urgency", "yes", 0.9),
        ),
        ungrounded_arguments=("location",),
        lowest_confidence=0.3,
    )

    result = route(gate_outcome, THRESHOLD)

    assert result.outcome is Outcome.ESCALATE
    assert result.escalate_cause is EscalateCause.CONFLICTING_EVIDENCE


def test_escalate_on_adapter_failure():
    failure = FailureRecord(
        stage=FailureStage.DECIDER,
        error_type="timeout",
        error_message="The decision model did not respond in time.",
        occurred_at=datetime.now(timezone.utc),
    )

    result = route(failure, THRESHOLD)

    assert result.outcome is Outcome.ESCALATE
    assert result.escalate_cause is EscalateCause.FAILURE
