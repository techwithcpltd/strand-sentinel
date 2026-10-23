"""Real-Decider evaluation script (Design Section 7.3, Task 7).

Runs the REAL Strands Decider 2B (not a stub) against this project's three
required fixtures and records actual outputs, mapped answers, all available
probabilities, model confidence, selected probability, and per-call latency
to a local JSON report. Does NOT assert that the real model must reproduce
each fixture's scripted stub label -- disagreement is recorded for human
inspection, never treated as a test failure.

Only runs when explicitly invoked:

    .venv/bin/python -m strand_sentinel.eval.decider_eval [--output PATH] [--hf-home PATH]

Requires the optional `decider` dependency group (`pip install -e ".[decider]"`)
and triggers a real local model load/download on first use. This module is
never imported by the default `pytest` run and has no effect by merely
being imported (see `main()` / the `__main__` guard below).
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strand_sentinel.adapters.real_decider_client import RealDeciderClient
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
)
from strand_sentinel.models import FailureRecord, GroundednessAnswer, ProposedToolCall, SyntheticReport

# Deliberate same-package dependency on pipeline's private question-builder:
# importing it here (rather than duplicating its logic) guarantees this
# evaluation always asks the real Decider the exact same questions the
# production pipeline would send, so results can't silently drift apart.
from strand_sentinel.pipeline import _build_questions

# Caller-selected output path; defaults to the already-`.gitignore`d `audit/`
# directory, so a default run never risks committing generated data.
DEFAULT_OUTPUT_PATH = Path("audit") / "decider_eval_report.json"

_FIXTURES: tuple[tuple[str, SyntheticReport, ProposedToolCall, dict[str, GroundednessAnswer]], ...] = (
    (PROCEED_FIXTURE_ID, PROCEED_REPORT, PROCEED_PROPOSAL, PROCEED_ANSWERS),
    (GUIDE_FIXTURE_ID, GUIDE_REPORT, GUIDE_PROPOSAL, GUIDE_ANSWERS),
    (ESCALATE_FIXTURE_ID, ESCALATE_REPORT, ESCALATE_PROPOSAL, ESCALATE_ANSWERS),
)


def _result_to_dict(answer_or_failure: GroundednessAnswer | FailureRecord) -> dict[str, Any]:
    if isinstance(answer_or_failure, FailureRecord):
        return {
            "kind": "failure",
            "stage": answer_or_failure.stage.value,
            "error_type": answer_or_failure.error_type,
            "error_message": answer_or_failure.error_message,
        }
    return {
        "kind": "answer",
        "value": answer_or_failure.value,
        "confidence": answer_or_failure.confidence,
        "raw_decider_output": answer_or_failure.raw_decider_output,
    }


def run_evaluation(client: RealDeciderClient) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for fixture_id, report, proposal, scripted_answers in _FIXTURES:
        questions = _build_questions(report, proposal)
        for question in questions:
            start = time.perf_counter()
            answer_or_failure = client.evaluate(question)
            latency_ms = (time.perf_counter() - start) * 1000

            scripted = scripted_answers.get(question.question_id)
            disagreement = None
            if not isinstance(answer_or_failure, FailureRecord) and scripted is not None:
                disagreement = answer_or_failure.value != scripted.value

            results.append(
                {
                    "fixture_id": fixture_id,
                    "question_id": question.question_id,
                    "kind": question.kind.value,
                    "argument_name": question.argument_name,
                    "latency_ms": latency_ms,
                    "real_result": _result_to_dict(answer_or_failure),
                    "scripted_stub_value": scripted.value if scripted else None,
                    "disagrees_with_scripted_stub": disagreement,
                }
            )
    return results


def main(output_path: str | Path = DEFAULT_OUTPUT_PATH, hf_home: str | None = None) -> Path:
    client = RealDeciderClient(hf_home=hf_home)
    results = run_evaluation(client)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Observational only. Disagreement with a fixture's scripted stub "
            "value is NOT a failure -- it reflects the real model's actual "
            "behaviour and is recorded here for human inspection."
        ),
        "results": results,
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--hf-home", default=None)
    args = parser.parse_args()
    written_path = main(output_path=args.output, hf_home=args.hf_home)
    print(f"Report written to {written_path}")
