"""Task 3 evidence: each required fixture, run through the stub adapters,
proves its intended outcome via the already-tested router
(strand_sentinel.routing.route, Task 2).

No orchestration pipeline exists yet (that's Task 4). The question-building
and GateOutcome assembly below are test-only — they exist so the stub
adapters and the router can be proven to agree on each fixture, not as a
reusable production "groundedness gate" component.
"""

from __future__ import annotations

from strand_sentinel.adapters.bedrock_client import StubBedrockClient
from strand_sentinel.adapters.decider_client import StubDeciderClient
from strand_sentinel.constants import CONFIDENCE_THRESHOLD_PLACEHOLDER, EscalateCause, Outcome
from strand_sentinel.fixtures import (
    ESCALATE_ANSWERS,
    ESCALATE_FIXTURE_ID,
    ESCALATE_PROPOSAL,
    ESCALATE_REPORT,
    GUIDE_ANSWERS,
    GUIDE_FIXTURE_ID,
    GUIDE_PROPOSAL,
    GUIDE_REPORT,
    PROCEED_ANSWERS,
    PROCEED_FIXTURE_ID,
    PROCEED_PROPOSAL,
    PROCEED_REPORT,
    question_id,
)
from strand_sentinel.models import (
    ARGUMENT_NAMES,
    OVERALL_ANSWER_OPTIONS,
    PER_ARGUMENT_ANSWER_OPTIONS,
    GateOutcome,
    GroundednessAnswer,
    GroundednessQuestion,
    ProposedToolCall,
    QuestionKind,
    SyntheticReport,
)
from strand_sentinel.routing import route

THRESHOLD = CONFIDENCE_THRESHOLD_PLACEHOLDER


def _build_questions(
    fixture_id: str, report: SyntheticReport, proposal: ProposedToolCall
) -> list[GroundednessQuestion]:
    state = {"report": report.text, "proposed_arguments": vars(proposal)}
    questions = [
        GroundednessQuestion(
            question_id=question_id(fixture_id, "overall"),
            kind=QuestionKind.OVERALL,
            argument_name=None,
            text="Given the report and the proposed arguments, is the evidence "
            "grounded, missing, or conflicting?",
            options=OVERALL_ANSWER_OPTIONS,
            state=state,
        )
    ]
    for argument_name in ARGUMENT_NAMES:
        value = getattr(proposal, argument_name)
        questions.append(
            GroundednessQuestion(
                question_id=question_id(fixture_id, argument_name),
                kind=QuestionKind.PER_ARGUMENT,
                argument_name=argument_name,
                text=f"Is the proposed {argument_name} value '{value}' explicitly "
                "supported by the report text?",
                options=PER_ARGUMENT_ANSWER_OPTIONS,
                state=state,
            )
        )
    return questions


def _assemble_gate_outcome(
    questions: list[GroundednessQuestion], decider: StubDeciderClient
) -> GateOutcome:
    answers: dict[str, GroundednessAnswer] = {}
    for question in questions:
        answer = decider.evaluate(question)
        assert isinstance(answer, GroundednessAnswer)
        answers[question.question_id] = answer

    overall_question = next(q for q in questions if q.kind is QuestionKind.OVERALL)
    overall_answer = answers[overall_question.question_id]

    per_argument_answers = tuple(
        answers[q.question_id] for q in questions if q.kind is QuestionKind.PER_ARGUMENT
    )
    ungrounded_arguments = tuple(
        q.argument_name
        for q in questions
        if q.kind is QuestionKind.PER_ARGUMENT and answers[q.question_id].value == "no"
    )
    lowest_confidence = min(answer.confidence for answer in answers.values())

    return GateOutcome(
        overall_answer=overall_answer,
        per_argument_answers=per_argument_answers,
        ungrounded_arguments=ungrounded_arguments,
        lowest_confidence=lowest_confidence,
    )


def test_proceed_fixture_routes_to_proceed():
    bedrock = StubBedrockClient(proposals={PROCEED_FIXTURE_ID: PROCEED_PROPOSAL})
    decider = StubDeciderClient(answers=PROCEED_ANSWERS)

    proposal = bedrock.propose_tool_call(PROCEED_REPORT)
    assert proposal == PROCEED_PROPOSAL

    questions = _build_questions(PROCEED_FIXTURE_ID, PROCEED_REPORT, proposal)
    gate_outcome = _assemble_gate_outcome(questions, decider)
    result = route(gate_outcome, THRESHOLD)

    assert result.outcome is Outcome.PROCEED
    assert result.escalate_cause is None


def test_guide_fixture_routes_to_guide():
    bedrock = StubBedrockClient(proposals={GUIDE_FIXTURE_ID: GUIDE_PROPOSAL})
    decider = StubDeciderClient(answers=GUIDE_ANSWERS)

    proposal = bedrock.propose_tool_call(GUIDE_REPORT)
    assert proposal == GUIDE_PROPOSAL

    questions = _build_questions(GUIDE_FIXTURE_ID, GUIDE_REPORT, proposal)
    gate_outcome = _assemble_gate_outcome(questions, decider)
    result = route(gate_outcome, THRESHOLD)

    assert result.outcome is Outcome.GUIDE
    assert result.escalate_cause is None


def test_escalate_fixture_routes_to_escalate():
    bedrock = StubBedrockClient(proposals={ESCALATE_FIXTURE_ID: ESCALATE_PROPOSAL})
    decider = StubDeciderClient(answers=ESCALATE_ANSWERS)

    proposal = bedrock.propose_tool_call(ESCALATE_REPORT)
    assert proposal == ESCALATE_PROPOSAL

    questions = _build_questions(ESCALATE_FIXTURE_ID, ESCALATE_REPORT, proposal)
    gate_outcome = _assemble_gate_outcome(questions, decider)
    result = route(gate_outcome, THRESHOLD)

    assert result.outcome is Outcome.ESCALATE
    assert result.escalate_cause is EscalateCause.CONFLICTING_EVIDENCE
