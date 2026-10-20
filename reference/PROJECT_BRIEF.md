# Project Brief — StrandSentinel

Non-authoritative reference notes. This file exists to keep the confirmed product definition and the
confirmed hackathon rules in one place so the spec files can cite it. It is not itself a spec.

## Source material

- Hackathon listing: "Agent Experience Hackathon: Strands Decider" on AWS Builder Center
  (Oct 16, 2026 00:00 PDT – Oct 23, 2026 23:59 PDT). Local copies saved to the repo root by the user as
  reference PDFs (not part of the application).

## Confirmed hackathon rules (from the listing)

**Every submission must include:**
1. An agent that uses Strands Decider 2B for at least one meaningful decision, paired with Amazon Bedrock
2. A written article on Builder Center describing the agent, what it does, and the decision handed to Decider 2B
3. A link to a public repository with the agent's source code and at least one reusable Decider 2B decision
   pattern others can use in their own agents
4. A short, publicly available demo video, under three minutes, showing the agent and its Decider 2B
   decision working
5. One declared decision pattern from: Tool selection, **Guardrails**, Policy, Model routing, Context and memory
6. An original agent that has not been published before

**Required tags:** `#strands-decider-2b` and one pattern tag — this project uses `#guardrails`.

**Judging rubric (Gate 1 → top 100, Gate 2 → 3 winners):**
- Creativity and cool factor — 30%
- Effective use of Decider 2B — 30% (a measured latency/cost improvement counts as a bonus here)
- Communication quality — 25%
- Originality — 15%

**Reusable asset requirement:** the typed question and option set handed to Decider 2B, the wiring that
puts it in the agent's path (the listing names a Strands `InterventionHandler` as an example — **VERIFY**
this is the correct integration point), and a short usage note.

**Decider 2B, as described by the listing:** a small, open, experimental decision model from AWS. It does
not generate text — it reads a state and a typed question and returns a choice, a yes/no, or a score, each
with a calibrated confidence number, in about 115ms on hardware you already own. This description is taken
from the listing's marketing copy; exact SDK/API shape is **VERIFY**.

**Key dates:** projects due Oct 23, 2026; Gate 1 scoring week of Oct 26; Gate 2 judging week of Nov 2;
winners announced week of Nov 9.

## Confirmed product definition (StrandSentinel)

- A synthetic housing-condition report is analysed by Amazon Bedrock.
- Bedrock proposes a structured, simulated tool call:
  `create_action_brief(issue_category, location, onset_or_duration, urgency)`.
- Before that tool call is allowed to run, Strands Decider 2B checks whether each proposed argument is
  explicitly grounded in the report text.
- Decider's outcome changes system behaviour:
  - **Proceed** — all arguments grounded; the tool may run.
  - **Guide** — at least one argument is ungrounded; the tool is blocked and Bedrock asks focused
    follow-up questions.
  - **Escalate** — evidence conflicts; the tool is blocked and a human-review summary is produced. This
    path is reserved for conflicting evidence only, not for ungrounded-but-non-conflicting evidence.
- Declared decision pattern: `#guardrails`.
- Out of scope (must not happen in this prototype): real-world routing, notifications, emergency response,
  legal advice, medical advice, processing of real personal data.
- Mandatory disclaimer on every user-facing output:
  > Supports human triage only; not emergency, legal or medical advice.

## Open questions (tracked, not resolved here)

All marked **VERIFY** in the spec files:
- Strands Decider 2B SDK/package name, install method, and call signature
- Strands SDK's tool-interception mechanism (is `InterventionHandler` the real API?)
- Which Bedrock model ID is used for the generative (report-analysis, tool-proposal, follow-up-question)
  steps
- Deployment target and mechanics (local script vs. Lambda vs. something else)
- Exact confidence-score semantics and threshold Decider 2B returns
