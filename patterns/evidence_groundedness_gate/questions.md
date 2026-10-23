# Typed questions and option sets

The gate asks exactly **five** typed questions per run: one overall choice question, and one yes/no question
per proposed tool-call argument.

## As implemented in this repository

Tool call: `create_action_brief(issue_category, location, onset_or_duration, urgency)`. Source document: a
synthetic housing-condition report.

### 1. Overall question

| Field | Value |
|---|---|
| Kind | `overall` |
| Text | *"Given the report and the proposed arguments, is the evidence grounded, missing, or conflicting?"* |
| Options | `grounded`, `missing_evidence`, `conflicting_evidence` |
| State | the full report text + the full proposed argument set |

### 2–5. Per-argument questions (one per argument)

| Field | Value |
|---|---|
| Kind | `per_argument` |
| Text template | *"Is the proposed `{argument_name}` value '`{value}`' explicitly supported by the report text?"* |
| Options | `yes`, `no` |
| State | same as the overall question — the full report text + the full proposed argument set |
| Arguments asked | `issue_category`, `location`, `onset_or_duration`, `urgency` |

Every answer — overall or per-argument — carries a **calibrated confidence value** alongside its choice.
The gate's routing policy ([`routing_policy.md`](routing_policy.md)) uses the *lowest* confidence across all
five answers as a single pass/fail signal.

Reference implementation: `strand_sentinel.models.GroundednessQuestion` /
`strand_sentinel.models.GroundednessAnswer`, built in `strand_sentinel.pipeline._build_questions`.

## Adapting this to a different tool call

To reuse this question shape for a different tool with a different argument list:

- Keep the overall question's three options exactly as-is (`grounded` / `missing_evidence` /
  `conflicting_evidence`) — they map directly onto the three possible outcomes.
- Keep the per-argument question's two options exactly as-is (`yes` / `no`).
- Replace the four argument names with your own tool's argument names (any count — the policy doesn't
  assume exactly four, see [`routing_policy.md`](routing_policy.md)).
- Replace "the report text" in both templates with whatever your evidence source actually is.

## [VERIFY] — real Decider 2B call shape

This document describes the *typed question/option set* — a model-agnostic decision contract. It does
**not** describe the real Strands Decider 2B request/response JSON shape, which is still `[VERIFY]` per
`docs/design.md` Section 10 until Task 7 confirms it against the installed package. Do not assume the field
names above (`text`, `options`, `state`) are the literal Decider 2B API's parameter names — they are this
project's own `GroundednessQuestion` model fields.
