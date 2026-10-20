# CLAUDE.md

Persistent instructions for Claude Code working in this repository.

## Project

StrandSentinel — a submission to AWS Builder Center's **Agent Experience Hackathon: Strands Decider**
(Oct 16–23, 2026, 23:59 PDT deadline). See [`reference/PROJECT_BRIEF.md`](reference/PROJECT_BRIEF.md) for
full source notes on both the hackathon listing and the product definition below.

## Product definition

A synthetic housing-condition report is analysed by Amazon Bedrock. Bedrock proposes a structured,
simulated tool call:

```
create_action_brief(issue_category, location, onset_or_duration, urgency)
```

Before that tool call is allowed to run, **Strands Decider 2B** checks whether each proposed argument is
explicitly grounded in the report text. Decider's outcome changes what happens next:

| Outcome | Meaning |
|---|---|
| **Proceed** | All arguments grounded. The tool call runs and an action brief is produced. |
| **Guide** | At least one argument is ungrounded. The tool is blocked; Bedrock asks focused follow-up questions targeting the ungrounded argument(s). |
| **Escalate** | Evidence conflicts (not merely missing). The tool is blocked; a human-review summary is produced. |

The result is shown to a human triage reviewer, with the mandatory disclaimer attached (below).

## Decision pattern — `#guardrails`

This is the entire point of the product, not an add-on: verify that proposed tool-call arguments are
grounded in what the source document actually said, before the tool is allowed to execute. Every
implementation choice should serve this pattern directly.

## Hackathon requirements (qualification checklist)

- [ ] An agent using Strands Decider 2B for at least one meaningful decision, paired with Amazon Bedrock
- [ ] A written article on Builder Center describing the agent, what it does, and the decision handed to Decider 2B
- [ ] A public repository link with source code AND at least one reusable Decider 2B decision pattern
      (lives in `patterns/evidence_groundedness_gate/`: the typed question/option set, the wiring that
      places the check in the agent's execution path, and a short usage note)
- [ ] A public demo video, under 3 minutes, showing the agent and the Decider 2B decision working
- [ ] Required tags applied: `#strands-decider-2b` and `#guardrails`
- [ ] Confirmation the agent is original / not previously published

Judging weighs: Creativity (30%), Effective use of Decider 2B (30%), Communication quality (25%),
Originality (15%). Prefer the smallest implementation that satisfies the checklist over an ambitious but
unfinished build.

## Bedrock and Strands Decider 2B constraints

- Decider 2B does not generate text — it reads a state and a typed question and returns a choice, a
  yes/no, or a score, each with a calibrated confidence number. Use it only for the groundedness-check
  decision, not as a general-purpose model.
- Bedrock handles all generative steps (reading the report, proposing the tool call, drafting follow-up
  questions, drafting the escalation summary).
- Do not substitute a different decision pattern without explicit approval.

## Synthetic-data and human-triage limitations

- All report inputs are synthetic/fabricated for the demo. Never process real personal data.
- This prototype must **not**: perform real-world routing or dispatch, send real notifications, provide
  emergency response, give legal advice, or give medical advice.
- Every user-facing output must include, verbatim:
  > Supports human triage only; not emergency, legal or medical advice.

## VERIFY rule

Details of the Strands Decider 2B SDK, the Strands SDK (including whether an `InterventionHandler`-style
mechanism is the correct integration point), the Bedrock model ID(s) used, and deployment mechanics have
not been verified against official documentation. Mark any such unverified detail as **VERIFY** rather than
assuming or inventing an API. Do not invent APIs.

## Working agreement

- Work one task at a time. Stop and wait for explicit approval before starting the next task.
- Do not create AWS resources, provision infrastructure, or take any action that could incur charges
  without explicit approval first.
