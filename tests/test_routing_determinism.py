"""Task 5: explicit proof that routing.route is deterministic — the same
GateOutcome and threshold always produce the same RoutingResult, called
repeatedly, not just "happened to match" in Task 2's single-call tests.
"""

from __future__ import annotations

from strand_sentinel.constants import CONFIDENCE_THRESHOLD_PLACEHOLDER
from strand_sentinel.models import GateOutcome, GroundednessAnswer
from strand_sentinel.routing import route

THRESHOLD = CONFIDENCE_THRESHOLD_PLACEHOLDER


def test_route_is_deterministic_across_repeated_calls():
    gate_outcome = GateOutcome(
        overall_answer=GroundednessAnswer(question_id="overall", value="grounded", confidence=0.9),
        per_argument_answers=(
            GroundednessAnswer(question_id="a", value="yes", confidence=0.9),
            GroundednessAnswer(question_id="b", value="yes", confidence=0.9),
            GroundednessAnswer(question_id="c", value="yes", confidence=0.9),
            GroundednessAnswer(question_id="d", value="yes", confidence=0.9),
        ),
        ungrounded_arguments=(),
        lowest_confidence=0.9,
    )

    results = [route(gate_outcome, THRESHOLD) for _ in range(50)]

    assert all(result == results[0] for result in results)
