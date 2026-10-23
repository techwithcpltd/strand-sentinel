# StrandSentinel — Offline Demo Guide

This demo runs entirely locally and offline with respect to AWS. It is the basis for the hackathon demo
video and for anyone trying the project out.

**What's real and what's not, exactly:**
- **Strands Decider 2B is real** when you pass `--real-decider` — this calls the actual, installed
  `strands-decider` package on local Apple Silicon MLX hardware. One live local verification call has
  already been made and recorded (see `patterns/evidence_groundedness_gate/INTEGRATION.md`). It is never
  contacted over the network to any AWS or third-party service — only Hugging Face, once, to download model
  weights into the project-local `.hf_cache/`.
- **Amazon Bedrock is always the deterministic `StubBedrockClient`** in this demo. There is no way to invoke
  the real Bedrock adapter from this CLI. `RealBedrockClient` exists in the codebase with full unit-test
  coverage against a mocked boto3 client, and is **mock-verified locally only**: one approved live Converse
  attempt (made outside this CLI) was denied with `AccessDeniedException` because the AWS account lacks the
  required model agreement, and **no live Bedrock response has been received.**
- Every report is synthetic, fabricated demo content. No real-world action of any kind is taken.

## Setup

```bash
pip install -e ".[dev]"
```

To use the real local Decider (optional, not required for the default demo):
```bash
pip install -e ".[decider]"          # installs strands-decider[mlx], ~1.2GB, one-time
```

## Running the demo

```bash
python -m strand_sentinel.cli proceed
python -m strand_sentinel.cli guide
python -m strand_sentinel.cli escalate
```

Each command runs the one matching required fixture end-to-end through the real, already-tested pipeline
and prints:
- the synthetic report input
- the proposed `create_action_brief` tool arguments
- each Decider groundedness result (value + confidence)
- the overall decision and final route
- whether the simulated tool actually executed
- the follow-up questions (Guide) or escalation summary (Escalate), where applicable
- the path to the generated JSON audit record (written under `audit/`, already `.gitignore`d)
- the mandatory disclaimer, verbatim

To use the real local Decider 2B instead of the deterministic stub for any scenario:
```bash
python -m strand_sentinel.cli proceed --real-decider
```
This triggers a local model load/download on first use (see Setup above) and runs entirely on-device — it
does not contact AWS or Bedrock.

## What to show, in order (for the demo video)

1. **Proceed** — `python -m strand_sentinel.cli proceed`. Decider finds every argument explicitly grounded
   → the simulated tool executes, producing an action brief.
2. **Guide** — `python -m strand_sentinel.cli guide`. Decider flags two ungrounded arguments (onset,
   urgency) → the tool is blocked, and focused follow-up questions are shown instead.
3. **Escalate** — `python -m strand_sentinel.cli escalate`. Decider detects conflicting evidence (two
   contradictory accounts of the same heating outage) → the tool is blocked, and a neutral human-review
   summary is produced.
4. **Audit trail** — open the JSON file printed at the end of any run and point out the full decision
   record: proposed arguments, per-question Decider results, final outcome, and disclaimer.
5. *(Optional, if time allows)* re-run one scenario with `--real-decider` to show the real, locally-verified
   Strands Decider 2B producing a result, explicitly noting this is still entirely local — not Bedrock.

## Custom audit output location

```bash
python -m strand_sentinel.cli proceed --audit-dir /tmp/my-demo-audit
```
The default (`audit/`) is already excluded from version control via `.gitignore`.
