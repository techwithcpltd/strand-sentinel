"""Task 7: unit tests for RealDeciderClient with the Python API boundary
fully mocked -- no real model load, no network, no weight access. Proves
the response-normalization rules documented in real_decider_client.py:
binary scalar -> yes/no + routing-compatible confidence; choice answer ->
selected label + separately-preserved selected_probability/model_confidence;
and that every failure mode converts to a FailureRecord rather than raising
or silently guessing.
"""

from __future__ import annotations

import pytest

strands_decider = pytest.importorskip("strands_decider")

from strands_decider.schema import ChoiceAnswer, NoulAnswer, SystemOneResponse, Usage  # noqa: E402

from strand_sentinel.adapters.real_decider_client import RealDeciderClient  # noqa: E402
from strand_sentinel.models import FailureRecord, FailureStage, GroundednessQuestion, QuestionKind  # noqa: E402


def _noul_question(question_id: str = "q:issue_category") -> GroundednessQuestion:
    return GroundednessQuestion(
        question_id=question_id,
        kind=QuestionKind.PER_ARGUMENT,
        argument_name="issue_category",
        text="Is the proposed issue_category value 'water leak' explicitly supported by the report text?",
        options=("yes", "no"),
        state={"report": "synthetic test report", "proposed_arguments": {}},
    )


def _choice_question(question_id: str = "q:overall") -> GroundednessQuestion:
    return GroundednessQuestion(
        question_id=question_id,
        kind=QuestionKind.OVERALL,
        argument_name=None,
        text="Given the report and the proposed arguments, is the evidence grounded, missing, or conflicting?",
        options=("grounded", "missing_evidence", "conflicting_evidence"),
        state={"report": "synthetic test report", "proposed_arguments": {}},
    )


class _FakeEngine:
    """Stands in for strands_decider.infer.SystemOneEngine. Returns a fixed
    response (or raises a fixed exception) and counts calls."""

    def __init__(self, response_or_exc):
        self._response_or_exc = response_or_exc
        self.ask_calls = 0

    def ask(self, state, questions):
        self.ask_calls += 1
        if isinstance(self._response_or_exc, Exception):
            raise self._response_or_exc
        return self._response_or_exc


def _patch_load_engine(monkeypatch, engine_or_exc):
    load_calls = {"count": 0}

    def fake_load_engine(checkpoint, *, device="cuda", **kwargs):
        load_calls["count"] += 1
        if isinstance(engine_or_exc, Exception):
            raise engine_or_exc
        return engine_or_exc

    monkeypatch.setattr("strands_decider.infer.load_engine", fake_load_engine)
    return load_calls


# --- Binary (noul) threshold mapping: below, exactly at, above 0.5 ---


def test_binary_below_threshold_maps_to_no(monkeypatch):
    response = SystemOneResponse(
        model="test", answers={"q:issue_category": NoulAnswer(noul=0.3)}, usage=Usage()
    )
    _patch_load_engine(monkeypatch, _FakeEngine(response))
    client = RealDeciderClient()

    answer = client.evaluate(_noul_question())

    assert answer.value == "no"
    assert answer.confidence == pytest.approx(0.7)  # 1 - 0.3: confidence in the "no" that was chosen
    assert answer.raw_decider_output == {"api_type": "noul", "yes_probability": 0.3}


def test_binary_exactly_at_threshold_maps_to_yes(monkeypatch):
    response = SystemOneResponse(
        model="test", answers={"q:issue_category": NoulAnswer(noul=0.5)}, usage=Usage()
    )
    _patch_load_engine(monkeypatch, _FakeEngine(response))
    client = RealDeciderClient()

    answer = client.evaluate(_noul_question())

    assert answer.value == "yes"  # >= 0.5 maps to yes, per spec
    assert answer.confidence == pytest.approx(0.5)


def test_binary_above_threshold_maps_to_yes(monkeypatch):
    response = SystemOneResponse(
        model="test", answers={"q:issue_category": NoulAnswer(noul=0.815)}, usage=Usage()
    )
    _patch_load_engine(monkeypatch, _FakeEngine(response))
    client = RealDeciderClient()

    answer = client.evaluate(_noul_question())

    assert answer.value == "yes"
    assert answer.confidence == pytest.approx(0.815)
    assert answer.raw_decider_output["yes_probability"] == pytest.approx(0.815)


# --- Choice: selected_probability vs. model_confidence are kept distinct ---


def test_choice_preserves_selected_probability_and_model_confidence_distinctly(monkeypatch):
    # Real values observed in the one approved local CLI verification call.
    probabilities = {"grounded": 0.447, "missing_evidence": 0.333, "conflicting_evidence": 0.220}
    response = SystemOneResponse(
        model="test",
        answers={"q:overall": ChoiceAnswer(choice="grounded", probabilities=probabilities, confidence=0.171)},
        usage=Usage(),
    )
    _patch_load_engine(monkeypatch, _FakeEngine(response))
    client = RealDeciderClient()

    answer = client.evaluate(_choice_question())

    assert answer.value == "grounded"
    # Routing-compatibility mapping: confidence == selected_probability, NOT model_confidence.
    assert answer.confidence == pytest.approx(0.447)
    assert answer.raw_decider_output["selected_probability"] == pytest.approx(0.447)
    assert answer.raw_decider_output["model_confidence"] == pytest.approx(0.171)
    # The two are genuinely different numbers -- this is the point being tested.
    assert answer.raw_decider_output["selected_probability"] != answer.raw_decider_output["model_confidence"]
    assert answer.raw_decider_output["probabilities"] == probabilities


# --- Failure modes: model-load, inference, malformed response ---


def test_model_load_failure_returns_failure_record(monkeypatch):
    _patch_load_engine(monkeypatch, RuntimeError("could not load checkpoint"))
    client = RealDeciderClient()

    result = client.evaluate(_noul_question())

    assert isinstance(result, FailureRecord)
    assert result.stage is FailureStage.DECIDER
    assert result.error_type == "model-load-failed"
    assert "could not load checkpoint" in result.error_message


def test_inference_exception_returns_failure_record(monkeypatch):
    _patch_load_engine(monkeypatch, _FakeEngine(RuntimeError("inference blew up")))
    client = RealDeciderClient()

    result = client.evaluate(_noul_question())

    assert isinstance(result, FailureRecord)
    assert result.stage is FailureStage.DECIDER
    assert result.error_type == "inference-failed"


def test_missing_answer_key_returns_malformed_response_failure(monkeypatch):
    response = SystemOneResponse(model="test", answers={}, usage=Usage())  # question_id absent
    _patch_load_engine(monkeypatch, _FakeEngine(response))
    client = RealDeciderClient()

    result = client.evaluate(_noul_question())

    assert isinstance(result, FailureRecord)
    assert result.error_type == "malformed-response"


def test_unexpected_answer_type_returns_malformed_response_failure(monkeypatch):
    # A ChoiceAnswer returned for what should be a noul (per-argument) question.
    response = SystemOneResponse(
        model="test",
        answers={"q:issue_category": ChoiceAnswer(choice="x", probabilities={"x": 1.0}, confidence=1.0)},
        usage=Usage(),
    )
    _patch_load_engine(monkeypatch, _FakeEngine(response))
    client = RealDeciderClient()

    result = client.evaluate(_noul_question())

    assert isinstance(result, FailureRecord)
    assert result.error_type == "malformed-response"


def test_missing_selected_probability_key_returns_malformed_response_failure(monkeypatch):
    # choice names a label that isn't in its own probabilities dict.
    response = SystemOneResponse(
        model="test",
        answers={"q:overall": ChoiceAnswer(choice="grounded", probabilities={"missing_evidence": 1.0}, confidence=1.0)},
        usage=Usage(),
    )
    _patch_load_engine(monkeypatch, _FakeEngine(response))
    client = RealDeciderClient()

    result = client.evaluate(_choice_question())

    assert isinstance(result, FailureRecord)
    assert result.error_type == "malformed-response"


# --- Load-once-per-instance ---


def test_engine_loaded_once_per_instance_across_multiple_evaluate_calls(monkeypatch):
    response = SystemOneResponse(
        model="test", answers={"q:issue_category": NoulAnswer(noul=0.9)}, usage=Usage()
    )
    engine = _FakeEngine(response)
    load_calls = _patch_load_engine(monkeypatch, engine)
    client = RealDeciderClient()

    client.evaluate(_noul_question("q:issue_category"))
    client.evaluate(_noul_question("q:issue_category"))
    client.evaluate(_noul_question("q:issue_category"))

    assert load_calls["count"] == 1  # loaded once, not once per question
    assert engine.ask_calls == 3  # but ask() is called per question, as expected
