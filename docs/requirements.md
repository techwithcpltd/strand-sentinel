# Requirements: StrandSentinel — Evidence Groundedness Gate

Status: draft, not yet approved for implementation. Requirements use EARS syntax (Ubiquitous / Event-driven
/ Unwanted-behaviour / Optional-feature patterns). Any requirement that depends on an unverified SDK, API,
or model detail is marked **[VERIFY]**; implementation must not guess at the underlying call shape.

Scope note: this document defines only the nine areas below, per the product definition in
[`CLAUDE.md`](../CLAUDE.md) and [`reference/PROJECT_BRIEF.md`](../reference/PROJECT_BRIEF.md). It does not
define UI, deployment, or any feature outside those nine areas.

---

## 1. Synthetic report input

**User story:** As a demo operator, I want to supply a synthetic housing-condition report as input, so that
the system has something to analyse without touching real tenant data.

**Acceptance criteria:**
1.1. THE SYSTEM SHALL accept exactly one synthetic housing-condition report as text input per run.
1.2. THE SYSTEM SHALL treat the report as fabricated demo content and SHALL NOT accept, store, or process
     real personal data under any circumstance.
1.3. WHEN a report is accepted, THE SYSTEM SHALL pass its full text, unmodified, to the Bedrock analysis
     step (Requirement 2).
1.4. IF no report text is supplied THEN THE SYSTEM SHALL NOT invoke Bedrock or Decider 2B, and SHALL
     report an input error.

---

## 2. Bedrock proposes typed arguments for the simulated `create_action_brief` tool

**User story:** As the system, I want Bedrock to read the report and propose typed arguments for a
simulated tool call, so that a candidate action brief exists for the groundedness gate to evaluate.

**Acceptance criteria:**
2.1. WHEN a synthetic report is accepted, THE SYSTEM SHALL invoke Amazon Bedrock to analyse the report and
     propose arguments for the simulated tool call
     `create_action_brief(issue_category, location, onset_or_duration, urgency)`.
2.2. THE SYSTEM SHALL treat `create_action_brief` as a simulated tool call only — it SHALL NOT be wired to
     any real-world routing, notification, dispatch, or emergency-response system.
2.3. THE SYSTEM SHALL require Bedrock's proposal to include a value (or explicit "not stated") for each of
     the four typed arguments before the proposal is passed to the Evidence Groundedness Gate
     (Requirement 3).
2.4. **[VERIFY]** THE SYSTEM SHALL use a Bedrock model ID that has been confirmed against official AWS
     documentation; no specific model ID is assumed by this requirements document.
2.5. **[VERIFY]** THE exact mechanism by which Bedrock's proposal is captured as a structured/typed object
     (e.g. tool-use / function-calling response format) depends on the Bedrock API and SHALL be confirmed
     before implementation.

---

## 3. Decider 2B Evidence Groundedness Gate (before the tool call)

**User story:** As the system, I want Strands Decider 2B to check each proposed argument against the
report before the tool call is allowed to run, so that the tool never acts on unsupported claims.

**Acceptance criteria:**
3.1. WHEN Bedrock has proposed arguments for `create_action_brief` (Requirement 2), THE SYSTEM SHALL invoke
     Strands Decider 2B to evaluate each argument's groundedness against the report text before the tool
     call is permitted to run.
3.2. THE SYSTEM SHALL NOT permit the simulated `create_action_brief` tool call to run until the Evidence
     Groundedness Gate has returned an outcome.
3.3. THE SYSTEM SHALL evaluate each of the four arguments individually for whether it is explicitly
     supported by the report text, and SHALL also evaluate whether any arguments conflict with each other
     or with the report.
3.4. **[VERIFY]** THE exact Strands Decider 2B SDK/package, its call signature, its input schema (state +
     typed question), and its output schema (choice/yes-no/score + calibrated confidence) SHALL be
     confirmed against official documentation before implementation; none is assumed here.
3.5. **[VERIFY]** THE integration point used to intercept the tool call pending Decider's outcome (the
     hackathon listing names a Strands `InterventionHandler` as an example) SHALL be confirmed before
     implementation; no specific Strands SDK mechanism is assumed.
3.6. This gate is the system's reusable `#guardrails` decision pattern (see Requirement 9).

---

## 4. Three outcomes — Proceed / Guide / Escalate

**User story:** As a human triage reviewer, I want the gate's outcome to visibly change what the system
does next, so that I can trust the tool only ever runs on grounded evidence.

**Acceptance criteria:**
4.1. WHEN the Evidence Groundedness Gate finds every proposed argument explicitly grounded in the report
     AND finds no conflicting evidence, THE SYSTEM SHALL return outcome **Proceed** and SHALL permit the
     simulated `create_action_brief` tool call to run.
4.2. WHEN the Evidence Groundedness Gate finds at least one proposed argument missing or unsupported by
     the report, AND finds no conflicting evidence, THE SYSTEM SHALL return outcome **Guide**, SHALL block
     the tool call, and SHALL cause Bedrock to generate focused follow-up questions targeting only the
     ungrounded argument(s).
4.3. WHEN the Evidence Groundedness Gate finds conflicting evidence for one or more proposed arguments,
     THE SYSTEM SHALL return outcome **Escalate**, SHALL block the tool call, and SHALL produce a neutral,
     human-review summary describing the conflict without resolving it.
4.4. THE SYSTEM SHALL use exactly one of these three outcomes per run; it SHALL NOT permit the tool call to
     run under any outcome other than Proceed.
4.5. IF an outcome is Guide or Escalate THEN THE SYSTEM SHALL NOT produce an action brief for that run.
4.6. THE Escalate path is reserved for conflicting evidence; missing-but-non-conflicting evidence SHALL
     always route to Guide, never to Escalate.
4.7. IF Strands Decider 2B returns a result with confidence below a configurable threshold, THEN THE
     SYSTEM SHALL block the simulated tool call and return Guide, unless the result is conflicting
     evidence, in which case it SHALL return Escalate.

---

## 5. Mandatory disclaimer

**User story:** As a human triage reviewer, I want every output to carry a clear disclaimer, so that I never
mistake the system's output for emergency, legal, or medical advice.

**Acceptance criteria:**
5.1. THE SYSTEM SHALL include the following text, verbatim, on every user-facing output regardless of
     outcome (Proceed, Guide, or Escalate):
     > Supports human triage only; not emergency, legal or medical advice.
5.2. IF any user-facing output is generated without this exact disclaimer text THEN THAT output SHALL be
     considered non-compliant and SHALL NOT be shown as a final result.

---

## 6. Structured JSON audit record

**User story:** As a reviewer or demo judge, I want a structured audit record of every decision, so that the
groundedness check is inspectable and reproducible rather than opaque.

**Acceptance criteria:**
6.1. WHEN the Evidence Groundedness Gate returns an outcome (Requirement 4), THE SYSTEM SHALL write one
     structured JSON audit record for that run.
6.2. THE audit record SHALL include, at minimum: a run/report identifier, a timestamp, the full set of
     arguments Bedrock proposed, the per-argument groundedness result, the final outcome
     (Proceed/Guide/Escalate), and the disclaimer text.
6.3. **[VERIFY]** THE exact field names/shape for Decider 2B's per-argument confidence score SHALL follow
     whatever Decider 2B's real output schema turns out to be once confirmed; this document does not
     assume a specific score range or field name.
6.4. THE SYSTEM SHALL NOT include any real personal data in the audit record, consistent with Requirement
     1.2.
6.5. THE audit record SHALL be written for every run regardless of outcome, including failure cases
     (Requirement 7).

---

## 7. Failure behaviour — Bedrock or Decider unavailable or invalid output

**User story:** As a human triage reviewer, I want the system to fail safe, so that an unreachable model or
a malformed response never results in an ungrounded tool call.

**Acceptance criteria:**
7.1. IF Amazon Bedrock is unavailable, errors, times out, or returns output that cannot be parsed into the
     four typed arguments THEN THE SYSTEM SHALL block the simulated `create_action_brief` tool call and
     SHALL return outcome **Escalate**.
7.2. IF Strands Decider 2B is unavailable, errors, times out, or returns output that cannot be parsed into
     a valid groundedness result THEN THE SYSTEM SHALL block the simulated `create_action_brief` tool call
     and SHALL return outcome **Escalate**.
7.3. WHEN a failure-triggered Escalate occurs (7.1 or 7.2), THE SYSTEM SHALL record the failure reason in
     the JSON audit record (Requirement 6) and SHALL still attach the mandatory disclaimer (Requirement 5).
7.4. THE SYSTEM SHALL NOT retry silently in a way that could run the tool call without a valid Proceed
     outcome from the Evidence Groundedness Gate.

---

## 8. Synthetic demo fixtures — required baseline set

**User story:** As a demo presenter, I want a required baseline set of synthetic fixtures covering Proceed,
Guide, and Escalate, so that the demo video and article can visibly show all three behaviours while
allowing additional test fixtures later.

**Acceptance criteria:**
8.1. THE SYSTEM SHALL ship at least three required synthetic demo fixtures: one that drives outcome
     Proceed, one that drives outcome Guide, and one that drives outcome Escalate.
8.2. THE Proceed fixture SHALL be a synthetic report in which all four `create_action_brief` arguments are
     explicitly stated and non-conflicting.
8.3. THE Guide fixture SHALL be a synthetic report in which at least one argument is missing or
     unsupported, with no conflicting evidence present.
8.4. THE Escalate fixture SHALL be a synthetic report that contains two or more statements that conflict
     regarding at least one argument (e.g. conflicting urgency or conflicting location).
8.6. All three fixtures SHALL be fabricated content containing no real personal data, consistent with
     Requirement 1.2.

---

## 9. Reusable `#guardrails` pattern requirement

**User story:** As another hackathon builder, I want a reusable, clearly labeled decision pattern I can drop
into my own agent, so that I can reuse this groundedness check without reading the whole project.

**Acceptance criteria:**
9.1. THE SYSTEM SHALL package the Evidence Groundedness Gate as a reusable artifact under
     `patterns/evidence_groundedness_gate/`, clearly labeled as the `#guardrails` decision pattern.
9.2. THE reusable artifact SHALL document: the typed question and option set given to Decider 2B, the
     wiring that places the check in an agent's execution path before a tool call, and a short usage note
     — per the hackathon's reusable-asset requirement.
9.3. THE SYSTEM SHALL tag its public submission with both `#strands-decider-2b` and `#guardrails`.
9.4. **[VERIFY]** Any code sample inside the reusable artifact SHALL use only confirmed Strands/Decider 2B
     API calls; placeholder or assumed API calls SHALL be marked VERIFY rather than presented as working
     code.
9.5. THE reusable artifact SHALL be licensed under an OSI-approved open source license, consistent with the
     hackathon's public-repository requirement.

---

## Out of scope (explicit non-requirements)

Per [`CLAUDE.md`](../CLAUDE.md), the following are explicitly **not** requirements of this system and SHALL
NOT be implemented under this spec: real-world routing or dispatch, real notifications, emergency response,
legal advice, medical advice, or processing of real personal data.
