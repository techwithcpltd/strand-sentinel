"""Real Strands Decider 2B adapter (Task 7).

Wraps the installed `strands-decider` Python API behind the existing
DeciderClient contract (strand_sentinel.adapters.decider_client). This
module does NOT import `strands_decider` at module load time -- every
import of the package happens lazily, inside methods -- so merely importing
this file never requires the optional Decider/MLX dependency group to be
installed. Only calling `evaluate()` does. This keeps the default
test/install path free of the ~1.2GB Decider/MLX stack (see pyproject.toml's
`decider` optional dependency group).

Response-shape facts below are confirmed two ways: by direct inspection of
the installed `strands_decider.schema` module's pydantic field definitions,
and by the one approved local CLI verification call recorded in
docs/design.md Section 10 and
patterns/evidence_groundedness_gate/INTEGRATION.md. Neither is guessed.

Confirmed real API shape (strands_decider.schema):
  - NoulAnswer.noul: float                        -- a bare scalar, no "yes"/"no" label.
  - ChoiceAnswer.choice: str                       -- the selected label.
  - ChoiceAnswer.probabilities: dict[str, float]   -- full distribution over options.
  - ChoiceAnswer.confidence: float                 -- NOT equal to probabilities[choice].
        It is `derive_confidence()`: a normalised max-probability concentration
        score, (N * p_max - 1) / (N - 1), comparable across different option
        counts (uniform -> 0.0, one-hot -> 1.0). This is why this adapter keeps
        `model_confidence` (this value) and `selected_probability`
        (probabilities[choice]) as two distinct, separately preserved numbers
        -- never substitute one for the other.

Routing-compatibility mapping (documented here, not implicit): the existing
`GroundednessAnswer.confidence` field (used by strand_sentinel.routing.route,
Task 2, unmodified) is set to:
  - per-argument (noul) questions: the probability mass behind whichever
    label was actually selected -- `yes_probability` if value == "yes",
    else `1 - yes_probability` if value == "no". Symmetric with the choice
    case below.
  - overall (choice) questions: `selected_probability`
    (`probabilities[choice]`) -- NOT the API's separate `model_confidence`.
Both raw numbers are always preserved, unreduced, in `raw_decider_output`.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from strand_sentinel.models import (
    FailureRecord,
    FailureStage,
    GroundednessAnswer,
    GroundednessQuestion,
    QuestionKind,
)

# Configuration: read from environment/constructor args, never hard-coded
# operational behaviour.
_MODEL_ID_ENV = "STRAND_SENTINEL_DECIDER_MODEL_ID"
_DEVICE_ENV = "STRAND_SENTINEL_DECIDER_DEVICE"
_DEFAULT_MODEL_ID = "StrandsAgents/strands-decider-2B-hobson-v19"
_DEFAULT_DEVICE = "mlx"


class RealDeciderClient:
    """Real Strands Decider 2B adapter.

    Loads the model once, lazily, on the first call to `evaluate()`, and
    reuses that loaded engine for every subsequent call on the same
    instance -- never once per question (requirement 1).

    Every failure mode -- optional-dependency import failure, model-load
    failure, inference failure, or a response shape that doesn't match what
    is documented above -- is converted into a
    `FailureRecord(stage=FailureStage.DECIDER, ...)` rather than raised or
    guessed at, matching the existing DeciderClient contract exactly
    (requirements 4-6).
    """

    def __init__(
        self,
        model_id: str | None = None,
        device: str | None = None,
        hf_home: str | None = None,
        yes_threshold: float = 0.5,
    ) -> None:
        self._model_id = model_id or os.environ.get(_MODEL_ID_ENV, _DEFAULT_MODEL_ID)
        self._device = device or os.environ.get(_DEVICE_ENV, _DEFAULT_DEVICE)
        self._hf_home = hf_home
        self._yes_threshold = yes_threshold
        self._engine = None  # loaded lazily; at most once per instance

    def evaluate(self, question: GroundednessQuestion) -> GroundednessAnswer | FailureRecord:
        try:
            engine = self._ensure_engine()
        except Exception as exc:  # optional-dependency import or model-load failure
            return self._failure("model-load-failed", exc)

        try:
            sdk_question = self._build_sdk_question(question)
        except Exception as exc:
            return self._failure("unsupported-question-kind", exc)

        try:
            response = engine.ask(question.state, {question.question_id: sdk_question})
        except Exception as exc:  # inference failure
            return self._failure("inference-failed", exc)

        try:
            return self._parse_answer(question, response)
        except Exception as exc:  # malformed or ambiguous response -- never guessed
            return self._failure("malformed-response", exc)

    def _ensure_engine(self):
        if self._engine is not None:
            return self._engine

        if self._hf_home:
            os.environ["HF_HOME"] = self._hf_home

        from strands_decider.infer import load_engine  # lazy: optional dependency

        self._engine = load_engine(self._model_id, device=self._device)
        return self._engine

    def _build_sdk_question(self, question: GroundednessQuestion):
        from strands_decider.schema import ChoiceQuestion, NoulQuestion  # lazy

        if question.kind is QuestionKind.PER_ARGUMENT:
            return NoulQuestion(instructions=question.text)
        if question.kind is QuestionKind.OVERALL:
            # Matches the official CLI's own construction exactly (strands_decider.cli
            # ask_cmd): empty-string per-option descriptions, not invented here.
            return ChoiceQuestion(
                instructions=question.text,
                criteria={option: "" for option in question.options},
            )
        raise ValueError(f"unsupported GroundednessQuestion.kind: {question.kind!r}")

    def _parse_answer(self, question: GroundednessQuestion, response) -> GroundednessAnswer:
        from strands_decider.schema import ChoiceAnswer, NoulAnswer  # lazy

        answer = response.answers[question.question_id]  # KeyError -> malformed-response

        # The answer's type must match the *expected* kind for this question
        # (not just be "some" recognised type) -- a kind mismatch is exactly
        # the ambiguity requirement 6 says must never be silently accepted.
        if question.kind is QuestionKind.PER_ARGUMENT:
            if not isinstance(answer, NoulAnswer):
                raise TypeError(
                    f"expected NoulAnswer for per-argument question "
                    f"{question.question_id!r}, got {type(answer)!r}"
                )
            yes_probability = answer.noul
            value = "yes" if yes_probability >= self._yes_threshold else "no"
            confidence = yes_probability if value == "yes" else 1.0 - yes_probability
            raw_decider_output = {
                "api_type": "noul",
                "yes_probability": yes_probability,
            }
            return GroundednessAnswer(
                question_id=question.question_id,
                value=value,
                confidence=confidence,
                raw_decider_output=raw_decider_output,
            )

        if question.kind is QuestionKind.OVERALL:
            if not isinstance(answer, ChoiceAnswer):
                raise TypeError(
                    f"expected ChoiceAnswer for overall question "
                    f"{question.question_id!r}, got {type(answer)!r}"
                )
            selected_probability = answer.probabilities[answer.choice]  # KeyError -> malformed
            raw_decider_output = {
                "api_type": "choice",
                "selected_probability": selected_probability,
                "model_confidence": answer.confidence,
                "probabilities": dict(answer.probabilities),
            }
            return GroundednessAnswer(
                question_id=question.question_id,
                value=answer.choice,
                confidence=selected_probability,
                raw_decider_output=raw_decider_output,
            )

        raise ValueError(f"unsupported GroundednessQuestion.kind: {question.kind!r}")

    def _failure(self, error_type: str, exc: Exception) -> FailureRecord:
        return FailureRecord(
            stage=FailureStage.DECIDER,
            error_type=error_type,
            error_message=str(exc),
            occurred_at=datetime.now(timezone.utc),
        )
