"""Escalate-path summary generation (Design Section 3, corrected per the
Escalate/failure amendment: a failure-triggered Escalate never calls
Bedrock, since Bedrock may itself be the unavailable component).

- cause == CONFLICTING_EVIDENCE: ask Bedrock for a neutral summary.
- cause == FAILURE: build a deterministic local summary from FailureRecord
  fields only — no model call of any kind.
"""

from __future__ import annotations

from strand_sentinel.adapters.bedrock_client import BedrockClient
from strand_sentinel.constants import EscalateCause
from strand_sentinel.models import FailureRecord, GateOutcome, ProposedToolCall, SyntheticReport


def generate_escalation_summary(
    *,
    cause: EscalateCause,
    bedrock: BedrockClient | None,
    report: SyntheticReport,
    proposal: ProposedToolCall | None,
    gate_outcome: GateOutcome | None,
    failure: FailureRecord | None,
) -> str | FailureRecord:
    if cause is EscalateCause.FAILURE:
        assert failure is not None
        return _deterministic_failure_summary(failure)

    assert bedrock is not None
    assert proposal is not None
    assert gate_outcome is not None
    return bedrock.draft_conflict_summary(report, proposal, gate_outcome)


def _deterministic_failure_summary(failure: FailureRecord) -> str:
    return (
        f"Automated escalation: the {failure.stage.value} step failed "
        f"({failure.error_type}) at {failure.occurred_at.isoformat()}. "
        f"Detail: {failure.error_message}. This run was escalated for human "
        "review because the system could not complete its automated "
        "evidence check."
    )
