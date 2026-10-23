"""Deterministic routing — docs/design.md Section 6.

Pure function, no I/O, no model calls, no hidden state: the same
(GateOutcome | FailureRecord, threshold) pair always produces the same
RoutingResult.
"""

from __future__ import annotations

from dataclasses import dataclass

from strand_sentinel.constants import EscalateCause, Outcome
from strand_sentinel.models import FailureRecord, GateOutcome


@dataclass(frozen=True)
class RoutingResult:
    outcome: Outcome
    escalate_cause: EscalateCause | None = None


def route(result: GateOutcome | FailureRecord, threshold: float) -> RoutingResult:
    """Apply the fixed routing table in docs/design.md Section 6."""

    # Requirement 7.1 / 7.2: a FailureRecord from either adapter always escalates.
    if isinstance(result, FailureRecord):
        return RoutingResult(outcome=Outcome.ESCALATE, escalate_cause=EscalateCause.FAILURE)

    gate_outcome = result

    # Requirement 4.3 / 4.6: conflicting evidence always escalates, checked
    # before the low-confidence fallback so a low-confidence conflicting
    # answer still escalates rather than falling through to Guide.
    if gate_outcome.overall_answer.value == "conflicting_evidence":
        return RoutingResult(
            outcome=Outcome.ESCALATE, escalate_cause=EscalateCause.CONFLICTING_EVIDENCE
        )

    all_yes = all(answer.value == "yes" for answer in gate_outcome.per_argument_answers)

    # Requirement 4.1: Proceed only if fully grounded, nothing ungrounded,
    # and confidence meets the threshold.
    if (
        gate_outcome.overall_answer.value == "grounded"
        and all_yes
        and not gate_outcome.ungrounded_arguments
        and gate_outcome.lowest_confidence >= threshold
    ):
        return RoutingResult(outcome=Outcome.PROCEED)

    # Requirement 4.7: low confidence defaults to Guide (the conflicting
    # case was already handled above).
    if gate_outcome.lowest_confidence < threshold:
        return RoutingResult(outcome=Outcome.GUIDE)

    # Requirement 4.2: missing/unsupported evidence, no conflict.
    return RoutingResult(outcome=Outcome.GUIDE)
