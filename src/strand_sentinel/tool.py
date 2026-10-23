"""The simulated create_action_brief tool (Design Section 3).

Pure, no I/O, no real-world effect. The pipeline is solely responsible for
only ever calling this on a Proceed outcome (Requirement 2.2, 4.4) — this
function itself has no notion of "outcome".
"""

from __future__ import annotations

from strand_sentinel.models import ProposedToolCall


def create_action_brief(proposal: ProposedToolCall) -> dict[str, str]:
    """Assemble a simulated action brief from a grounded ProposedToolCall.
    Never performs any real-world routing, dispatch, or notification.
    """

    return {
        "tool_name": proposal.tool_name,
        "issue_category": proposal.issue_category,
        "location": proposal.location,
        "onset_or_duration": proposal.onset_or_duration,
        "urgency": proposal.urgency,
    }
