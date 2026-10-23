# Evidence Groundedness Gate — `#guardrails`

A reusable decision pattern for the AWS Agent Experience Hackathon: Strands Decider. Before an agent lets a
proposed tool call run, this pattern asks a small decision model whether each proposed argument is
explicitly grounded in a source document — and routes to **Proceed**, **Guide**, or **Escalate** based on
the answer.

> **Status note:** the adapters shipped in this repository (`StubBedrockClient`, `StubDeciderClient`) are
> **deterministic local stubs** written for Tasks 1–6 of this project's own build. They are **not** a real
> Strands Decider 2B integration. Real Decider 2B integration is planned for Task 7 of
> [`docs/tasks.md`](../../docs/tasks.md); until then, nothing in this pattern should be read as proof that it
> works against the real model — only that the *decision logic* is correct and fully tested against
> hand-scripted stand-ins.

## What the pattern does

Given a tool call with N typed arguments (here, four: `issue_category`, `location`, `onset_or_duration`,
`urgency`) proposed from a source document, the gate asks:

1. **One overall question** — is the evidence `grounded`, `missing_evidence`, or `conflicting_evidence`?
2. **One yes/no question per argument** — is this exact proposed value explicitly supported by the source
   document?

The answers deterministically route to exactly one of three outcomes:

| Outcome | Meaning | Tool call |
|---|---|---|
| **Proceed** | Everything grounded, confidence met | Runs |
| **Guide** | Missing/unsupported evidence, or low confidence (no conflict) | Blocked — ask focused follow-ups |
| **Escalate** | Conflicting evidence, or the decision/model step itself failed | Blocked — human-review summary |

See [`questions.md`](questions.md) for the exact typed questions/options, [`routing_policy.md`](routing_policy.md)
for the full routing table, and [`INTEGRATION.md`](INTEGRATION.md) for how to wire this into an agent's
tool-call path (including the current stub boundary vs. a real Strands `InterventionHandler`).

## Reuse this in 3 steps

1. **Adapt the question set.** Replace the four argument names in [`questions.md`](questions.md) with your
   own tool's argument names, and swap "the source document" for whatever evidence source your agent reads
   from (a ticket, a transcript, a form submission, etc.). The overall-question options and per-argument
   yes/no shape stay the same.
2. **Reuse the routing policy as-is.** [`routing_policy.md`](routing_policy.md) is domain-agnostic: it only
   depends on an overall answer, four-or-N per-argument answers, and a confidence threshold. The reference
   implementation is `strand_sentinel.routing.route()` — copy it, or import it directly if you're already in
   this codebase.
3. **Wire it in before your tool call.** See [`INTEGRATION.md`](INTEGRATION.md) for the current stub-based
   wiring (`strand_sentinel.pipeline.run()`) and the intended future wiring through a Strands
   `InterventionHandler.before_tool_call` — noting that `Escalate` is not an SDK action and must be handled
   at the application layer.

## What's proven here, right now

`tests/test_pattern_routing.py` in this directory re-proves the routing policy standalone — Proceed, Guide
(missing evidence), Escalate (conflicting evidence), and Escalate (adapter failure) — using the same
`strand_sentinel.routing.route()` function the rest of this repository uses, with no dependency on the rest
of the repo's test suite layout. Run it with:

```bash
pytest patterns/evidence_groundedness_gate/tests/
```

## Licensing

No license file is included in this pattern yet. An OSI-approved license for the whole repository is a
later submission task (see `docs/tasks.md` Task 11), not part of this pattern package.
