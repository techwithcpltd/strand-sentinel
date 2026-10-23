# StrandSentinel

Built for the **AWS Agent Experience Hackathon: Strands Decider** (Oct 16–23, 2026).

StrandSentinel analyses a synthetic housing-condition report. An upstream model proposes a structured,
simulated tool call — `create_action_brief(issue_category, location, onset_or_duration, urgency)` — and
before that tool is allowed to run, **Strands Decider 2B** checks whether each proposed argument is
explicitly grounded in the source report. Decider's outcome changes what happens next:

| Outcome | Meaning |
|---|---|
| **Proceed** | All arguments are grounded, with confidence above threshold. The simulated tool runs. |
| **Guide** | At least one argument is ungrounded, or confidence is low. The tool is blocked and focused follow-up questions are shown instead. |
| **Escalate** | Evidence conflicts (or the decision pipeline itself failed). The tool is blocked and a neutral human-review summary is produced. |

Declared decision pattern: **`#guardrails`** — verifying that proposed tool-call arguments are grounded in
what the source document actually said, before the tool is allowed to execute. See
[`patterns/evidence_groundedness_gate/`](patterns/evidence_groundedness_gate/) for the reusable, standalone
version of this pattern.

## Status

The decision core is implemented and tested: domain models, the deterministic router, the orchestration
pipeline, the simulated tool, the JSON audit writer, and the reusable `#guardrails` pattern are all complete,
with 73 passing project tests plus 4 passing standalone pattern tests (77 total) — see [`docs/tasks.md`](docs/tasks.md) for the task-by-task
build history. Full planning baseline: [`docs/requirements.md`](docs/requirements.md),
[`docs/design.md`](docs/design.md), [`docs/tasks.md`](docs/tasks.md).

**Model integration status:**
- **Strands Decider 2B — real, local, verified.** `RealDeciderClient` calls the actual installed
  `strands-decider` package (Apple Silicon MLX backend) and has been exercised with one approved live local
  verification call. See [`patterns/evidence_groundedness_gate/INTEGRATION.md`](patterns/evidence_groundedness_gate/INTEGRATION.md).
- **Amazon Bedrock — mock-verified locally only.** `RealBedrockClient` is implemented against the official
  Bedrock Converse API shape and is covered by unit tests using an injected, fully mocked boto3 client. One
  approved live Bedrock Converse attempt (synthetic report text, single request, no retries, returned tool
  never executed) was denied with `AccessDeniedException` because the AWS account lacks the required model
  agreement; no live Bedrock response has been received. The default demo and test suite use
  `StubBedrockClient`, a deterministic, hand-scripted stand-in.

## Try it locally

```bash
pip install -e ".[dev]"
python -m strand_sentinel.cli proceed
python -m strand_sentinel.cli guide
python -m strand_sentinel.cli escalate
```

Each command runs one of the three required synthetic fixtures end-to-end through the real pipeline, using
the deterministic stub adapters by default, and prints a full human-readable report (proposed arguments,
per-argument groundedness results, final route, whether the simulated tool ran, and the audit file path).
See [`docs/demo/OFFLINE_DEMO.md`](docs/demo/OFFLINE_DEMO.md) for the full walkthrough.

### Tests

```bash
pytest                                            # project tests (73 tests), fully offline
pytest patterns/evidence_groundedness_gate/tests/ # standalone pattern tests (4 tests)
```

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
docs/                                         project documentation (requirements, design, tasks)
docs/demo/                                    offline demo guide
docs/submission/                              hackathon submission write-up assets
patterns/evidence_groundedness_gate/          the reusable Decider 2B decision pattern (#guardrails)
src/strand_sentinel/                          application source
  adapters/                                   Bedrock + Decider adapter interfaces (stub and real)
  fixtures/                                   the three required synthetic demo fixtures
  eval/                                       real-Decider evaluation script (explicit invocation only)
  cli.py                                      local demo runner
tests/                                        automated tests (fully offline)
audit/                                        generated decision/audit logs (gitignored, not committed)
```

## Tags

`#strands-decider-2b` `#guardrails`

## Verification status

Decider 2B's local Python API, Strands Agents' `InterventionHandler` tool-interception mechanism, and
Bedrock's Converse API shape have all been confirmed against official documentation and/or direct package
inspection — see `docs/design.md` Section 10 and `patterns/evidence_groundedness_gate/INTEGRATION.md` for
the full, itemized verification status, including what remains `[VERIFY]` (e.g. a successful live Bedrock call, and a
standalone live Python-API Decider call as opposed to the CLI path already verified).
