from datetime import datetime, timezone

from strand_sentinel.constants import CONFIDENCE_THRESHOLD_PLACEHOLDER, EscalateCause, Outcome
from strand_sentinel.models import FailureRecord, FailureStage, GateOutcome, GroundednessAnswer
from strand_sentinel.routing import route

THRESHOLD = CONFIDENCE_THRESHOLD_PLACEHOLDER


def _answer(question_id: str, value: str, confidence: float) -> GroundednessAnswer:
    return GroundednessAnswer(question_id=question_id, value=value, confidence=confidence)


def test_proceed_when_grounded_and_confident():
    gate_outcome = GateOutcome(
        overall_answer=_answer("overall", "grounded", 0.95),
        per_argument_answers=(
            _answer("issue_category", "yes", 0.9),
            _answer("location", "yes", 0.92),
            _answer("onset_or_duration", "yes", 0.88),
            _answer("urgency", "yes", 0.91),
        ),
        ungrounded_arguments=(),
        lowest_confidence=0.88,
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


def test_guide_when_low_confidence_without_conflict():
    gate_outcome = GateOutcome(
        overall_answer=_answer("overall", "grounded", 0.4),
        per_argument_answers=(
            _answer("issue_category", "yes", 0.4),
            _answer("location", "yes", 0.6),
            _answer("onset_or_duration", "yes", 0.7),
            _answer("urgency", "yes", 0.8),
        ),
        ungrounded_arguments=(),
        lowest_confidence=0.4,
    )

    result = route(gate_outcome, THRESHOLD)

    assert result.outcome is Outcome.GUIDE
    assert result.escalate_cause is None


def test_escalate_when_conflicting_evidence():
    gate_outcome = GateOutcome(
        overall_answer=_answer("overall", "conflicting_evidence", 0.93),
        per_argument_answers=(
            _answer("issue_category", "yes", 0.9),
            # Deliberately low confidence here: conflicting evidence must still
            # escalate rather than falling through to the low-confidence Guide path.
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


def test_escalate_on_bedrock_failure():
    failure = FailureRecord(
        stage=FailureStage.BEDROCK,
        error_type="timeout",
        error_message="Bedrock did not respond in time.",
        occurred_at=datetime.now(timezone.utc),
    )

    result = route(failure, THRESHOLD)

    assert result.outcome is Outcome.ESCALATE
    assert result.escalate_cause is EscalateCause.FAILURE


def test_escalate_on_decider_failure():
    failure = FailureRecord(
        stage=FailureStage.DECIDER,
        error_type="unparseable-output",
        error_message="Decider response could not be parsed.",
        occurred_at=datetime.now(timezone.utc),
    )

    result = route(failure, THRESHOLD)

    assert result.outcome is Outcome.ESCALATE
    assert result.escalate_cause is EscalateCause.FAILURE
