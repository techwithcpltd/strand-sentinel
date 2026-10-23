# Builder Center Article Outline — StrandSentinel

Draft outline only. Not the final article text.

## 1. Hook
"What happens when an agent is about to act on a claim the source document never actually said?"

## 2. The problem
LLM-proposed tool calls can smuggle in unsupported or conflicting claims. Manual review of every proposal
doesn't scale, but blind trust in the proposal is worse.

## 3. The decision handed to Strands Decider 2B
Before letting a simulated `create_action_brief(issue_category, location, onset_or_duration, urgency)` tool
call run, Strands Decider 2B checks whether each proposed argument is explicitly grounded in the source
report — one overall 3-way choice question (`grounded` / `missing_evidence` / `conflicting_evidence`) plus
one yes/no question per argument. This is the `#guardrails` decision pattern.

## 4. How the outcome changes behaviour
- **Proceed** — all grounded, confidence met → the tool runs.
- **Guide** — missing evidence or low confidence, no conflict → the tool is blocked, focused follow-up
  questions are shown instead.
- **Escalate** — conflicting evidence (or the decision pipeline itself failed) → the tool is blocked, a
  neutral human-review summary is produced. Note for the write-up: **Escalate is not a Strands SDK action**
  — confirmed from official docs that `before_tool_call` only offers `Proceed`/`Deny`/`Guide`/`Confirm`/
  `Transform`. Escalate is implemented entirely at the application layer, most likely via `Deny`.

## 5. What's real vs. simulated — be explicit, this is the honest core of the write-up
- Strands Decider 2B: **genuinely integrated and locally verified** — real local inference via
  `strands-decider` on Apple Silicon MLX, one live verification call made and recorded.
- The `create_action_brief` tool: **simulated** — it only ever assembles a dict, never performs any
  real-world routing, dispatch, or notification, by design (Requirement 2.2 of the project's own spec).
- Amazon Bedrock: **implemented and unit-tested against a mocked AWS client, but not live-verified** — no
  AWS account, credentials, model access, or live Bedrock call were used for this submission. The published
  demo uses a deterministic stub standing in for Bedrock's generative steps.

## 6. The reusable pattern
Point to `patterns/evidence_groundedness_gate/` — the typed question/option set, the deterministic routing
policy, the integration notes (including the confirmed real Decider 2B response shape and the official
Strands `InterventionHandler` action set), and a standalone test suite.

## 7. What I learned (candidates — pick 2–3 for the final article)
- Strands Decider 2B's `confidence` for a choice answer is *not* the selected option's own probability — it's
  a separate, normalised concentration score (`derive_confidence`), confirmed by reading the installed
  package's own source and matching it exactly against a real CLI output.
- There is no SDK-native "Escalate" action in Strands Agents' intervention system — only
  Proceed/Deny/Guide/Confirm/Transform — which shaped how the whole pattern had to be designed.
- Getting `strands-decider[mlx]` installed on a brand-new Python version (3.14) required verifying wheel
  availability before installing anything, rather than assuming it would work.

## 8. Links and tags
- Public repository link (pending — repo is currently private, must be made public before submission)
- Demo video link (pending)
- Tags: `#strands-decider-2b` `#guardrails`
