"""Orchestration pipeline (Design Sections 1-3, 6).

Wires: Bedrock adapter -> groundedness gate (question build + answer
collection, implemented here) -> Decider adapter -> the pure, unmodified
router (routing.route, Task 2) -> the matching output generator (tool /
followup / escalation) -> audit writer.

Routing itself is never duplicated here — this module only calls
routing.route() and acts on its result.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from strand_sentinel.adapters.bedrock_client import BedrockClient
from strand_sentinel.adapters.decider_client import DeciderClient
from strand_sentinel.audit import (
    AuditRecord,
    answer_to_dict,
    failure_to_dict,
    proposal_to_dict,
    question_to_dict,
    report_to_dict,
    write_audit_record,
)
from strand_sentinel.constants import DISCLAIMER, EscalateCause, Outcome
from strand_sentinel.escalation import generate_escalation_summary
from strand_sentinel.followup import generate_follow_up_questions
from strand_sentinel.models import (
    ARGUMENT_NAMES,
    OVERALL_ANSWER_OPTIONS,
    PER_ARGUMENT_ANSWER_OPTIONS,
    FailureRecord,
    GateOutcome,
    GroundednessAnswer,
    GroundednessQuestion,
    ProposedToolCall,
    QuestionKind,
    SyntheticReport,
)
from strand_sentinel.routing import route
from strand_sentinel.tool import create_action_brief

# [VERIFY] Design Section 10: real model identifiers are not yet configured
# (Tasks 7/8). Never hard-code a real model ID here.
_UNCONFIGURED_MODEL_IDENTIFIERS = {
    "bedrock_model_id": "[VERIFY - not yet configured]",
    "decider_model_id": "[VERIFY - not yet configured]",
}


@dataclass(frozen=True)
class PipelineResult:
    outcome: Outcome
    disclaimer: str
    action_brief: dict[str, str] | None
    follow_up_questions: tuple[str, ...] | None
    escalation_summary: str | None
    audit_record: AuditRecord
    audit_path: Path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_questions(
    report: SyntheticReport, proposal: ProposedToolCall
) -> list[GroundednessQuestion]:
    state = {
        "report": report.text,
        "proposed_arguments": {
            "issue_category": proposal.issue_category,
            "location": proposal.location,
            "onset_or_duration": proposal.onset_or_duration,
            "urgency": proposal.urgency,
        },
    }
    questions = [
        GroundednessQuestion(
            question_id=f"{report.report_id}:overall",
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
                question_id=f"{report.report_id}:{argument_name}",
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
    questions: list[GroundednessQuestion], answers: list[GroundednessAnswer]
) -> GateOutcome:
    overall_answer = answers[0]
    per_argument_answers = tuple(answers[1:])
    ungrounded_arguments = tuple(
        question.argument_name
        for question, answer in zip(questions[1:], per_argument_answers)
        if answer.value == "no"
    )
    lowest_confidence = min(answer.confidence for answer in answers)
    return GateOutcome(
        overall_answer=overall_answer,
        per_argument_answers=per_argument_answers,
        ungrounded_arguments=ungrounded_arguments,
        lowest_confidence=lowest_confidence,
    )


def run(
    report: SyntheticReport,
    bedrock: BedrockClient,
    decider: DeciderClient,
    threshold: float,
    *,
    fixture_id: str | None = None,
    audit_dir: str | Path = "audit",
) -> PipelineResult:
    run_id = str(uuid.uuid4())
    latency_ms: dict[str, float] = {}
    decider_questions_log: list[GroundednessQuestion] = []
    decider_results_log: list[GroundednessAnswer] = []

    # --- Bedrock: propose the simulated tool call ---
    t0 = time.perf_counter()
    proposal_or_failure = bedrock.propose_tool_call(report)
    latency_ms["bedrock_propose_ms"] = (time.perf_counter() - t0) * 1000

    if isinstance(proposal_or_failure, FailureRecord):
        return _finish_escalate_on_failure(
            run_id=run_id,
            report=report,
            fixture_id=fixture_id,
            threshold=threshold,
            proposal=None,
            decider_questions_log=decider_questions_log,
            decider_results_log=decider_results_log,
            failure=proposal_or_failure,
            latency_ms=latency_ms,
            audit_dir=audit_dir,
        )

    proposal = proposal_or_failure

    # --- Decider: evaluate groundedness, short-circuit on first failure ---
    questions = _build_questions(report, proposal)
    t0 = time.perf_counter()
    first_failure: FailureRecord | None = None
    for question in questions:
        decider_questions_log.append(question)
        answer_or_failure = decider.evaluate(question)
        if isinstance(answer_or_failure, FailureRecord):
            first_failure = answer_or_failure
            break
        decider_results_log.append(answer_or_failure)
    latency_ms["decider_ms"] = (time.perf_counter() - t0) * 1000

    if first_failure is not None:
        return _finish_escalate_on_failure(
            run_id=run_id,
            report=report,
            fixture_id=fixture_id,
            threshold=threshold,
            proposal=proposal,
            decider_questions_log=decider_questions_log,
            decider_results_log=decider_results_log,
            failure=first_failure,
            latency_ms=latency_ms,
            audit_dir=audit_dir,
        )

    gate_outcome = _assemble_gate_outcome(questions, decider_results_log)
    routing_result = route(gate_outcome, threshold)

    if routing_result.outcome is Outcome.PROCEED:
        brief = create_action_brief(proposal)
        record = AuditRecord(
            run_id=run_id,
            timestamp=_now_iso(),
            fixture_id=fixture_id,
            input_report=report_to_dict(report),
            bedrock_proposal=proposal_to_dict(proposal),
            decider_questions=[question_to_dict(q) for q in decider_questions_log],
            decider_results=[answer_to_dict(a) for a in decider_results_log],
            confidence_threshold=threshold,
            final_outcome=Outcome.PROCEED.value,
            behaviour_taken="tool executed",
            failure_reason=None,
            summary_source=None,
            latency_ms=latency_ms,
            model_identifiers=dict(_UNCONFIGURED_MODEL_IDENTIFIERS),
            disclaimer=DISCLAIMER,
        )
        audit_path = write_audit_record(record, audit_dir)
        return PipelineResult(
            outcome=Outcome.PROCEED,
            disclaimer=DISCLAIMER,
            action_brief=brief,
            follow_up_questions=None,
            escalation_summary=None,
            audit_record=record,
            audit_path=audit_path,
        )

    if routing_result.outcome is Outcome.GUIDE:
        t0 = time.perf_counter()
        followup_result = generate_follow_up_questions(bedrock, report, proposal, gate_outcome)
        latency_ms["bedrock_followup_ms"] = (time.perf_counter() - t0) * 1000

        if isinstance(followup_result, FailureRecord):
            return _finish_escalate_on_failure(
                run_id=run_id,
                report=report,
                fixture_id=fixture_id,
                threshold=threshold,
                proposal=proposal,
                decider_questions_log=decider_questions_log,
                decider_results_log=decider_results_log,
                failure=followup_result,
                latency_ms=latency_ms,
                audit_dir=audit_dir,
            )

        record = AuditRecord(
            run_id=run_id,
            timestamp=_now_iso(),
            fixture_id=fixture_id,
            input_report=report_to_dict(report),
            bedrock_proposal=proposal_to_dict(proposal),
            decider_questions=[question_to_dict(q) for q in decider_questions_log],
            decider_results=[answer_to_dict(a) for a in decider_results_log],
            confidence_threshold=threshold,
            final_outcome=Outcome.GUIDE.value,
            behaviour_taken="follow-up questions generated",
            failure_reason=None,
            summary_source=None,
            latency_ms=latency_ms,
            model_identifiers=dict(_UNCONFIGURED_MODEL_IDENTIFIERS),
            disclaimer=DISCLAIMER,
        )
        audit_path = write_audit_record(record, audit_dir)
        return PipelineResult(
            outcome=Outcome.GUIDE,
            disclaimer=DISCLAIMER,
            action_brief=None,
            follow_up_questions=followup_result,
            escalation_summary=None,
            audit_record=record,
            audit_path=audit_path,
        )

    # ESCALATE via conflicting evidence (all failure cases returned above).
    t0 = time.perf_counter()
    summary_result = generate_escalation_summary(
        cause=EscalateCause.CONFLICTING_EVIDENCE,
        bedrock=bedrock,
        report=report,
        proposal=proposal,
        gate_outcome=gate_outcome,
        failure=None,
    )
    latency_ms["bedrock_conflict_summary_ms"] = (time.perf_counter() - t0) * 1000

    if isinstance(summary_result, FailureRecord):
        return _finish_escalate_on_failure(
            run_id=run_id,
            report=report,
            fixture_id=fixture_id,
            threshold=threshold,
            proposal=proposal,
            decider_questions_log=decider_questions_log,
            decider_results_log=decider_results_log,
            failure=summary_result,
            latency_ms=latency_ms,
            audit_dir=audit_dir,
        )

    record = AuditRecord(
        run_id=run_id,
        timestamp=_now_iso(),
        fixture_id=fixture_id,
        input_report=report_to_dict(report),
        bedrock_proposal=proposal_to_dict(proposal),
        decider_questions=[question_to_dict(q) for q in decider_questions_log],
        decider_results=[answer_to_dict(a) for a in decider_results_log],
        confidence_threshold=threshold,
        final_outcome=Outcome.ESCALATE.value,
        behaviour_taken="escalation summary generated",
        failure_reason=None,
        summary_source="bedrock_conflict_summary",
        latency_ms=latency_ms,
        model_identifiers=dict(_UNCONFIGURED_MODEL_IDENTIFIERS),
        disclaimer=DISCLAIMER,
    )
    audit_path = write_audit_record(record, audit_dir)
    return PipelineResult(
        outcome=Outcome.ESCALATE,
        disclaimer=DISCLAIMER,
        action_brief=None,
        follow_up_questions=None,
        escalation_summary=summary_result,
        audit_record=record,
        audit_path=audit_path,
    )


def _finish_escalate_on_failure(
    *,
    run_id: str,
    report: SyntheticReport,
    fixture_id: str | None,
    threshold: float,
    proposal: ProposedToolCall | None,
    decider_questions_log: list[GroundednessQuestion],
    decider_results_log: list[GroundednessAnswer],
    failure: FailureRecord,
    latency_ms: dict[str, float],
    audit_dir: str | Path,
) -> PipelineResult:
    # Deterministic local summary only — no Bedrock call, by design (Design
    # Section 2/6 amendment): Bedrock may itself be the unavailable
    # component, so a failure-triggered Escalate never depends on it.
    summary = generate_escalation_summary(
        cause=EscalateCause.FAILURE,
        bedrock=None,
        report=report,
        proposal=proposal,
        gate_outcome=None,
        failure=failure,
    )
    record = AuditRecord(
        run_id=run_id,
        timestamp=_now_iso(),
        fixture_id=fixture_id,
        input_report=report_to_dict(report),
        bedrock_proposal=proposal_to_dict(proposal) if proposal is not None else None,
        decider_questions=[question_to_dict(q) for q in decider_questions_log],
        decider_results=[answer_to_dict(a) for a in decider_results_log],
        confidence_threshold=threshold,
        final_outcome=Outcome.ESCALATE.value,
        behaviour_taken="escalation summary generated",
        failure_reason=failure_to_dict(failure),
        summary_source="deterministic_failure_summary",
        latency_ms=latency_ms,
        model_identifiers=dict(_UNCONFIGURED_MODEL_IDENTIFIERS),
        disclaimer=DISCLAIMER,
    )
    audit_path = write_audit_record(record, audit_dir)
    return PipelineResult(
        outcome=Outcome.ESCALATE,
        disclaimer=DISCLAIMER,
        action_brief=None,
        follow_up_questions=None,
        escalation_summary=summary,
        audit_record=record,
        audit_path=audit_path,
    )
