"""Decider adapter boundary (Design Section 3, Section 7.1).

DeciderClient is the interface the groundedness gate will depend on once
built (Task 4). StubDeciderClient is a deterministic, hand-authored
implementation for tests: it holds a fixed answers table and performs no
network, AWS, model, or file I/O.
"""

from __future__ import annotations

from typing import Protocol

from strand_sentinel.models import FailureRecord, GroundednessAnswer, GroundednessQuestion


class DeciderClient(Protocol):
    """[VERIFY] Design Section 10: the real implementation depends on the
    confirmed Strands Decider 2B package (`strands-decider`) and is built in
    Task 7. This Protocol defines only the shape the rest of the system
    depends on.
    """

    def evaluate(self, question: GroundednessQuestion) -> GroundednessAnswer | FailureRecord:
        """Answer one typed question, or return a FailureRecord on failure."""
        ...


class StubDeciderClient:
    """Deterministic stub: returns fixed, hand-authored answers keyed by
    question_id. A question_id present in `failures` always returns that
    FailureRecord instead, regardless of `answers` — this preserves failure
    injection for later orchestration tests without implementing the
    orchestration pipeline itself.
    """

    def __init__(
        self,
        answers: dict[str, GroundednessAnswer],
        failures: dict[str, FailureRecord] | None = None,
    ) -> None:
        self._answers = dict(answers)
        self._failures = dict(failures or {})

    def evaluate(self, question: GroundednessQuestion) -> GroundednessAnswer | FailureRecord:
        if question.question_id in self._failures:
            return self._failures[question.question_id]
        return self._answers[question.question_id]
