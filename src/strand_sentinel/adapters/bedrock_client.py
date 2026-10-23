"""Bedrock adapter boundary (Design Section 3).

BedrockClient is the interface the orchestrator depends on. StubBedrockClient
is a deterministic, hand-authored implementation for tests: it holds fixed
tables and performs no network, AWS, model, or file I/O.

Three capabilities, matching the pipeline's three Bedrock call sites:
- propose_tool_call: analyse a report and propose create_action_brief args.
- draft_follow_up_questions: Guide path — scoped to ungrounded arguments.
- draft_conflict_summary: Escalate path, conflicting-evidence case only —
  never called for a failure-triggered Escalate (see escalation.py).
"""

from __future__ import annotations

from typing import Protocol

from strand_sentinel.models import (
    FailureRecord,
    GateOutcome,
    ProposedToolCall,
    SyntheticReport,
)


class BedrockClient(Protocol):
    """[VERIFY] Design Section 10: the real implementation depends on the
    confirmed Bedrock model ID and structured-output/tool-use API, and is
    built in Task 8. This Protocol defines only the shape the rest of the
    system depends on.
    """

    def propose_tool_call(self, report: SyntheticReport) -> ProposedToolCall | FailureRecord:
        """Propose create_action_brief arguments for a report, or return a
        FailureRecord on failure."""
        ...

    def draft_follow_up_questions(
        self,
        report: SyntheticReport,
        proposal: ProposedToolCall,
        target_arguments: tuple[str, ...],
    ) -> tuple[str, ...] | FailureRecord:
        """Draft follow-up questions scoped to target_arguments only, or
        return a FailureRecord on failure."""
        ...

    def draft_conflict_summary(
        self,
        report: SyntheticReport,
        proposal: ProposedToolCall,
        gate_outcome: GateOutcome,
    ) -> str | FailureRecord:
        """Draft a neutral human-review summary of conflicting evidence, or
        return a FailureRecord on failure."""
        ...


class StubBedrockClient:
    """Deterministic stub for all three BedrockClient methods. Each method
    checks its own failure table first (report_id -> FailureRecord); if the
    report_id isn't registered as a failure, it returns the scripted value
    from the matching table. An unregistered report_id raises KeyError,
    which is intentional: it means a test asked for a scenario it never
    scripted, and should fail loudly rather than silently.
    """

    def __init__(
        self,
        proposals: dict[str, ProposedToolCall],
        follow_up_questions: dict[str, tuple[str, ...]] | None = None,
        conflict_summaries: dict[str, str] | None = None,
        propose_failures: dict[str, FailureRecord] | None = None,
        follow_up_failures: dict[str, FailureRecord] | None = None,
        conflict_summary_failures: dict[str, FailureRecord] | None = None,
    ) -> None:
        self._proposals = dict(proposals)
        self._follow_up_questions = dict(follow_up_questions or {})
        self._conflict_summaries = dict(conflict_summaries or {})
        self._propose_failures = dict(propose_failures or {})
        self._follow_up_failures = dict(follow_up_failures or {})
        self._conflict_summary_failures = dict(conflict_summary_failures or {})

    def propose_tool_call(self, report: SyntheticReport) -> ProposedToolCall | FailureRecord:
        if report.report_id in self._propose_failures:
            return self._propose_failures[report.report_id]
        return self._proposals[report.report_id]

    def draft_follow_up_questions(
        self,
        report: SyntheticReport,
        proposal: ProposedToolCall,
        target_arguments: tuple[str, ...],
    ) -> tuple[str, ...] | FailureRecord:
        if report.report_id in self._follow_up_failures:
            return self._follow_up_failures[report.report_id]
        return self._follow_up_questions[report.report_id]

    def draft_conflict_summary(
        self,
        report: SyntheticReport,
        proposal: ProposedToolCall,
        gate_outcome: GateOutcome,
    ) -> str | FailureRecord:
        if report.report_id in self._conflict_summary_failures:
            return self._conflict_summary_failures[report.report_id]
        return self._conflict_summaries[report.report_id]
