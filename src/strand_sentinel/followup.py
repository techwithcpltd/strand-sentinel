"""Guide-path follow-up question generation (Design Section 3).

Scoped only to the argument(s) the groundedness gate found ungrounded —
grounded arguments are never passed to Bedrock here.
"""

from __future__ import annotations

from strand_sentinel.adapters.bedrock_client import BedrockClient
from strand_sentinel.models import FailureRecord, GateOutcome, ProposedToolCall, SyntheticReport


def generate_follow_up_questions(
    bedrock: BedrockClient,
    report: SyntheticReport,
    proposal: ProposedToolCall,
    gate_outcome: GateOutcome,
) -> tuple[str, ...] | FailureRecord:
    target_arguments = gate_outcome.ungrounded_arguments
    return bedrock.draft_follow_up_questions(report, proposal, target_arguments)
