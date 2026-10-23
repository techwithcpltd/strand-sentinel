"""Central constants: the mandatory disclaimer, the three outcome values,
the Escalate-cause distinction, and the (explicitly unverified) confidence
threshold placeholder.
"""

from __future__ import annotations

from enum import Enum

# Requirement 5.1 — must appear, verbatim, on every user-facing output.
DISCLAIMER: str = "Supports human triage only; not emergency, legal or medical advice."


class Outcome(str, Enum):
    """The three — and only three — router outcomes (Requirement 4.4)."""

    PROCEED = "proceed"
    GUIDE = "guide"
    ESCALATE = "escalate"


class EscalateCause(str, Enum):
    """Which of the two causes produced an Escalate outcome (Design Section 6)."""

    FAILURE = "failure"
    CONFLICTING_EVIDENCE = "conflicting_evidence"


# [VERIFY] Design Section 10: no default threshold value or calibration method
# is set by the approved design. This placeholder is NOT a calibrated
# production value — callers of routing.route() must supply an explicit
# threshold; this constant exists only because docs/tasks.md Task 2 asks for
# a flagged placeholder, and must be revisited once Task 7's real-Decider
# evaluation produces real confidence data to calibrate against.
CONFIDENCE_THRESHOLD_PLACEHOLDER: float = 0.5
