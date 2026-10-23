# Routing policy

Pure, deterministic logic — no model call, no hidden state. The same `(answers, threshold)` pair always
produces the same outcome. Reference implementation: `strand_sentinel.routing.route()`.

## The routing contract

| Outcome | Condition | Who can take this action |
|---|---|---|
| **Proceed** | Overall = `grounded`, every per-argument answer = `yes`, no ungrounded arguments, confidence ≥ threshold | A real Strands SDK action (`Proceed`) |
| **Guide** | Overall = `missing_evidence` with no conflict, **or** confidence < threshold with no conflict | A real Strands SDK action (`Guide`) |
| **Escalate** | Overall = `conflicting_evidence`, **or** the Bedrock/Decider call itself failed | **Not** a Strands SDK action — this is an **application-level** result, implemented by blocking the tool call (most likely via the SDK's `Deny` action) and generating a human-review summary entirely in application code |

This asymmetry is deliberate and confirmed against the official Strands Agents documentation (see
`docs/design.md` Section 10): the SDK's `before_tool_call` intervention actions are `Proceed`, `Deny`,
`Guide`, `Confirm`, `Transform` — there is no `Escalate`. Anyone reusing this pattern should not expect an
SDK-native "escalate" action to exist; the pattern's `Escalate` outcome must be translated into whatever
block/deny primitive the host SDK actually offers.

## Precedence order (checked in this exact order)

```
1. If either adapter call failed           -> ESCALATE (cause: failure)
2. Else if overall answer == conflicting    -> ESCALATE (cause: conflicting_evidence)
3. Else if overall == grounded AND all per-argument answers == yes
      AND no ungrounded arguments AND lowest_confidence >= threshold
                                             -> PROCEED
4. Else if lowest_confidence < threshold    -> GUIDE (low-confidence fallback)
5. Else (missing evidence, or some "no", no conflict, confidence adequate)
                                             -> GUIDE
```

Step 2 is checked **before** step 4 so that a low-confidence *conflicting* answer still escalates, rather
than being swallowed by the low-confidence Guide fallback.

## Why Escalate always wins over everything else when caused by failure

A failed Bedrock or Decider call is treated identically to conflicting evidence in terms of precedence — it
always escalates, regardless of what (if anything) was learned before the failure. This is a deliberate
fail-safe choice: an agent should never let a tool run, or present a "Guide" follow-up, built on a decision
process that didn't actually complete.

## Threshold

The routing policy takes a single scalar confidence threshold, compared against the *minimum* confidence
across all five answers. No default value is prescribed by this pattern — pick one appropriate to your own
risk tolerance and calibrate it against your own decision model's real confidence outputs. (This project's
own placeholder value, `0.5`, is explicitly marked non-calibrated — see `strand_sentinel.constants`.)
