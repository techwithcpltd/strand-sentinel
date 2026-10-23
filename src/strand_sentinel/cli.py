"""Minimal local CLI demo runner (Task 9).

Runs one of the three required fixtures (Proceed, Guide, Escalate) through
the real, already-tested pipeline and prints a human-readable report. This
is a demonstration layer only: it calls `strand_sentinel.pipeline.run`
exactly as the test suite does, never reimplements routing, and never
changes outcomes.

Uses the deterministic `StubBedrockClient` always -- there is no way to
invoke the real Bedrock adapter from this CLI at all, by design (no AWS, no
boto3, no credentials, no network, ever). The Decider side defaults to the
deterministic `StubDeciderClient` so the demo is repeatable; the real,
locally-verified Strands Decider 2B (`RealDeciderClient`, Task 7 -- local
MLX inference only, never AWS/Bedrock) is available only via the explicit
`--real-decider` opt-in flag.

Usage:
    python -m strand_sentinel.cli proceed
    python -m strand_sentinel.cli guide
    python -m strand_sentinel.cli escalate
    python -m strand_sentinel.cli proceed --real-decider
    python -m strand_sentinel.cli proceed --audit-dir /tmp/my-audit
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from strand_sentinel.adapters.bedrock_client import StubBedrockClient
from strand_sentinel.adapters.decider_client import DeciderClient, StubDeciderClient
from strand_sentinel.constants import CONFIDENCE_THRESHOLD_PLACEHOLDER, DISCLAIMER
from strand_sentinel.fixtures import (
    ESCALATE_ANSWERS,
    ESCALATE_CONFLICT_SUMMARY,
    ESCALATE_FIXTURE_ID,
    ESCALATE_PROPOSAL,
    ESCALATE_REPORT,
    GUIDE_ANSWERS,
    GUIDE_FIXTURE_ID,
    GUIDE_FOLLOW_UP_QUESTIONS,
    GUIDE_PROPOSAL,
    GUIDE_REPORT,
    PROCEED_ANSWERS,
    PROCEED_FIXTURE_ID,
    PROCEED_PROPOSAL,
    PROCEED_REPORT,
)
from strand_sentinel.pipeline import PipelineResult
from strand_sentinel.pipeline import run as run_pipeline

_SCENARIOS = {
    "proceed": (PROCEED_FIXTURE_ID, PROCEED_REPORT, PROCEED_PROPOSAL),
    "guide": (GUIDE_FIXTURE_ID, GUIDE_REPORT, GUIDE_PROPOSAL),
    "escalate": (ESCALATE_FIXTURE_ID, ESCALATE_REPORT, ESCALATE_PROPOSAL),
}


def _build_bedrock_stub(scenario: str) -> StubBedrockClient:
    fixture_id, _report, proposal = _SCENARIOS[scenario]
    if scenario == "proceed":
        return StubBedrockClient(proposals={fixture_id: proposal})
    if scenario == "guide":
        return StubBedrockClient(
            proposals={fixture_id: proposal},
            follow_up_questions={fixture_id: GUIDE_FOLLOW_UP_QUESTIONS},
        )
    return StubBedrockClient(
        proposals={fixture_id: proposal},
        conflict_summaries={fixture_id: ESCALATE_CONFLICT_SUMMARY},
    )


def _build_decider_stub(scenario: str) -> StubDeciderClient:
    answers = {"proceed": PROCEED_ANSWERS, "guide": GUIDE_ANSWERS, "escalate": ESCALATE_ANSWERS}[scenario]
    return StubDeciderClient(answers=answers)


def _build_real_decider() -> DeciderClient:
    # Lazy import: the optional `decider` dependency group (and a one-time
    # local model load) is only touched if --real-decider is explicitly
    # passed. Local MLX inference only -- never AWS, never Bedrock.
    from strand_sentinel.adapters.real_decider_client import RealDeciderClient

    return RealDeciderClient()


def _print_report(scenario: str, result: PipelineResult) -> None:
    _fixture_id, report, proposal = _SCENARIOS[scenario]
    record = result.audit_record

    print("=" * 72)
    print(f"StrandSentinel offline demo — scenario: {scenario}")
    print("=" * 72)
    print()
    print("Report input (synthetic, fabricated — no real personal data):")
    print(f"  report_id: {report.report_id}")
    first_line = report.text.strip().splitlines()[0] if report.text.strip() else ""
    print(f"  text (first line): {first_line}")
    print()
    print("Proposed tool arguments (create_action_brief):")
    for field in ("issue_category", "location", "onset_or_duration", "urgency"):
        print(f"  {field}: {getattr(proposal, field)!r}")
    print()
    print("Decider groundedness results:")
    for answer in record.decider_results:
        print(f"  {answer['question_id']}: value={answer['value']!r} confidence={answer['confidence']:.3f}")
    print()
    print(f"Overall decision: {record.final_outcome}")
    print(f"Final route: {result.outcome.value}")
    print(f"Simulated tool executed: {result.action_brief is not None}")
    if result.action_brief is not None:
        print(f"  action_brief: {result.action_brief}")
    if result.follow_up_questions is not None:
        print("Follow-up questions:")
        for question in result.follow_up_questions:
            print(f"  - {question}")
    if result.escalation_summary is not None:
        print(f"Escalation summary:\n  {result.escalation_summary}")
    print()
    print(f"Audit record written to: {result.audit_path}")
    print()
    print(f"DISCLAIMER: {result.disclaimer}")
    print("=" * 72)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="strand-sentinel-demo",
        description=(
            "StrandSentinel offline demo runner. Bedrock is always the deterministic "
            "stub (no AWS, ever). Decider is the deterministic stub by default; pass "
            "--real-decider for the real, locally-verified Strands Decider 2B "
            "(local MLX inference only, never AWS/Bedrock)."
        ),
    )
    parser.add_argument("scenario", choices=sorted(_SCENARIOS), help="Which required fixture to run.")
    parser.add_argument(
        "--real-decider",
        action="store_true",
        help=(
            "Use the real, locally-verified Strands Decider 2B (local-only MLX "
            "inference; never AWS, never Bedrock) instead of the deterministic "
            "stub. Requires the optional 'decider' dependency group and triggers "
            "a local model load on first use."
        ),
    )
    parser.add_argument(
        "--audit-dir",
        default="audit",
        help="Where to write the JSON audit record (default: 'audit/', already .gitignore'd).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=CONFIDENCE_THRESHOLD_PLACEHOLDER,
        help=(
            "Confidence threshold passed to the router (default: the explicitly "
            "non-calibrated placeholder from strand_sentinel.constants)."
        ),
    )
    args = parser.parse_args(argv)

    fixture_id, report, _proposal = _SCENARIOS[args.scenario]
    bedrock = _build_bedrock_stub(args.scenario)
    decider = _build_real_decider() if args.real_decider else _build_decider_stub(args.scenario)

    result = run_pipeline(
        report,
        bedrock,
        decider,
        args.threshold,
        fixture_id=fixture_id,
        audit_dir=Path(args.audit_dir),
    )
    _print_report(args.scenario, result)
    assert result.disclaimer == DISCLAIMER
    return 0


if __name__ == "__main__":
    sys.exit(main())
