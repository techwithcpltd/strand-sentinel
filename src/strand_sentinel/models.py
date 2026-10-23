"""Conceptual data models for StrandSentinel's Evidence Groundedness Gate.

Shapes mirror docs/design.md Section 4 exactly. Dependency-free: standard
library only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class QuestionKind(str, Enum):
    OVERALL = "overall"
    PER_ARGUMENT = "per_argument"


class FailureStage(str, Enum):
    BEDROCK = "bedrock"
    DECIDER = "decider"


# The four create_action_brief arguments (Requirement 2.1).
ARGUMENT_NAMES: tuple[str, ...] = (
    "issue_category",
    "location",
    "onset_or_duration",
    "urgency",
)

# Decider's overall-question options (Design Section 5).
OVERALL_ANSWER_OPTIONS: tuple[str, ...] = (
    "grounded",
    "missing_evidence",
    "conflicting_evidence",
)

# Decider's per-argument-question options (Design Section 5).
PER_ARGUMENT_ANSWER_OPTIONS: tuple[str, ...] = ("yes", "no")


@dataclass(frozen=True)
class SyntheticReport:
    report_id: str
    text: str


@dataclass(frozen=True)
class ProposedToolCall:
    tool_name: str
    issue_category: str
    location: str
    onset_or_duration: str
    urgency: str
    raw_model_response: object | None = None  # [VERIFY] shape — Design Section 4


@dataclass(frozen=True)
class GroundednessQuestion:
    question_id: str
    kind: QuestionKind
    argument_name: str | None
    text: str
    options: tuple[str, ...]
    state: dict


@dataclass(frozen=True)
class GroundednessAnswer:
    question_id: str
    value: str
    confidence: float
    raw_decider_output: object | None = None  # [VERIFY] shape — Design Section 4


@dataclass(frozen=True)
class GateOutcome:
    overall_answer: GroundednessAnswer
    per_argument_answers: tuple[GroundednessAnswer, ...]
    ungrounded_arguments: tuple[str, ...]
    lowest_confidence: float


@dataclass(frozen=True)
class FailureRecord:
    stage: FailureStage
    error_type: str
    error_message: str
    occurred_at: datetime
