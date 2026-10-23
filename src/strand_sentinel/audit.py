"""JSON audit record — Design Section 8, Requirement 6.

AuditRecord and the write function are the single owner of the audit JSON
schema. Serialization helpers here convert our dataclasses/enums into plain,
JSON-safe dicts explicitly, rather than relying on generic introspection.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from strand_sentinel.models import (
    FailureRecord,
    GroundednessAnswer,
    GroundednessQuestion,
    ProposedToolCall,
    SyntheticReport,
)


@dataclass(frozen=True)
class AuditRecord:
    run_id: str
    timestamp: str  # ISO-8601
    fixture_id: str | None
    input_report: dict[str, Any]
    bedrock_proposal: dict[str, Any] | None
    decider_questions: list[dict[str, Any]]
    decider_results: list[dict[str, Any]]
    confidence_threshold: float
    final_outcome: str  # "proceed" | "guide" | "escalate"
    behaviour_taken: str
    failure_reason: dict[str, Any] | None
    summary_source: str | None  # "bedrock_conflict_summary" | "deterministic_failure_summary" | None
    latency_ms: dict[str, float]
    model_identifiers: dict[str, str]
    disclaimer: str


def report_to_dict(report: SyntheticReport) -> dict[str, Any]:
    return {"report_id": report.report_id, "text": report.text}


def proposal_to_dict(proposal: ProposedToolCall) -> dict[str, Any]:
    return {
        "tool_name": proposal.tool_name,
        "issue_category": proposal.issue_category,
        "location": proposal.location,
        "onset_or_duration": proposal.onset_or_duration,
        "urgency": proposal.urgency,
    }


def question_to_dict(question: GroundednessQuestion) -> dict[str, Any]:
    return {
        "question_id": question.question_id,
        "kind": question.kind.value,
        "argument_name": question.argument_name,
        "text": question.text,
        "options": list(question.options),
    }


def answer_to_dict(answer: GroundednessAnswer) -> dict[str, Any]:
    return {
        "question_id": answer.question_id,
        "value": answer.value,
        "confidence": answer.confidence,
    }


def failure_to_dict(failure: FailureRecord) -> dict[str, Any]:
    return {
        "stage": failure.stage.value,
        "error_type": failure.error_type,
        "error_message": failure.error_message,
        "occurred_at": failure.occurred_at.isoformat(),
    }


def write_audit_record(record: AuditRecord, audit_dir: str | Path = "audit") -> Path:
    """Write one JSON audit record per run. Local filesystem only — no
    network, no AWS. `audit_dir` defaults to the repo's existing, already
    `.gitignore`d `audit/` directory but is fully caller-configurable.
    """

    directory = Path(audit_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{record.run_id}.json"
    path.write_text(json.dumps(asdict(record), indent=2), encoding="utf-8")
    return path
