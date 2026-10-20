# StrandSentinel

Built for the **AWS Agent Experience Hackathon: Strands Decider** (Oct 16–23, 2026).

StrandSentinel analyses a synthetic housing-condition report with Amazon Bedrock. Bedrock proposes a
structured, simulated tool call — `create_action_brief(issue_category, location, onset_or_duration, urgency)`
— and before that tool is allowed to run, **Strands Decider 2B** checks whether each proposed argument is
explicitly grounded in the source report. Decider's outcome changes what happens next:

| Outcome | Meaning |
|---|---|
| **Proceed** | All arguments are grounded. The tool may run. |
| **Guide** | At least one argument is ungrounded. The tool is blocked and Bedrock asks focused follow-up questions. |
| **Escalate** | Evidence conflicts. The tool is blocked and a human-review summary is produced. |

Declared decision pattern: **`#guardrails`** — verifying that proposed tool-call arguments are grounded in
what the source document actually said, before the tool is allowed to execute.

## Status

This repository currently contains the **planning and specification layer only**: steering docs, a Kiro
spec (requirements / design / tasks), and an architecture decision record. No application code, tests, or
AWS deployment exist yet. See [`.kiro/specs/strand-sentinel-decision-core/`](.kiro/specs/strand-sentinel-decision-core/)
and [`docs/decisions/ADR-001-evidence-groundedness-gate.md`](docs/decisions/ADR-001-evidence-groundedness-gate.md).

## Scope boundaries (hard constraints)

This is a hackathon prototype for demonstrating a decision pattern. It must **not**:

- Perform real-world routing or dispatch of any kind
- Send real notifications to anyone
- Provide emergency response of any kind
- Give legal advice
- Give medical advice
- Process real personal data (all reports used are synthetic)

Every user-facing output carries this disclaimer:

> Supports human triage only; not emergency, legal or medical advice.

## Repository structure

```
reference/                                   non-authoritative background material (e.g. hackathon brief)
docs/                                         project documentation
docs/decisions/                               architecture decision records (ADRs)
docs/demo/                                    demo video / script assets
docs/submission/                               hackathon submission write-up assets
.kiro/steering/                               Kiro steering context (hackathon + product)
.kiro/specs/strand-sentinel-decision-core/    requirements, design, tasks for the decision core
patterns/evidence_groundedness_gate/          the reusable Decider 2B decision pattern (#guardrails)
src/                                          application source (not yet implemented)
tests/                                        automated tests (not yet implemented)
audit/                                        generated decision/audit logs (not yet implemented)
```

## Tags

`#strands-decider-2b` `#guardrails`

## Verification status

Details of the Strands Decider 2B SDK, the Strands SDK, the Bedrock model ID, and deployment mechanics
have not yet been verified against official documentation. Everywhere such a detail is referenced in this
repository's specs, it is marked **VERIFY** rather than assumed.
