# Tasks: StrandSentinel — Evidence Groundedness Gate

Status: draft, not yet approved for implementation. This plan sequences the implementation of the frozen
baseline in [`docs/requirements.md`](requirements.md) and [`docs/design.md`](design.md), under the
constraints in [`CLAUDE.md`](../CLAUDE.md). Each task is independently reviewable and ends with a hard stop
for human approval — no task may begin until the previous one is approved.

**Tasks 1–6 require no AWS account, credentials, paid service, model-weight download, or external API
call.** Everywhere a model's behaviour would otherwise be needed, a deterministic stub is used instead, per
[`docs/design.md` Section 7](design.md#7-testability). Real model/AWS integration is deliberately isolated
to Tasks 7 and 8, each gated on your explicit, separate approval.

---

## Task 0 — GitHub repository checkpoint

Not a requirement-implementing task. This is the one-time checkpoint, inserted per your instruction, between
this task plan's approval and any code being written.

**Implements requirements:** none (process/infrastructure only).

**Files created/modified:** none in the working tree beyond what already exists. Actions, each requiring
separate explicit approval before being run: stage the currently-approved planning files
(`CLAUDE.md`, `README.md`, `.gitignore`, `reference/`, `docs/`) with `git add`; create the first commit;
create a **private** GitHub repository (`gh repo create ... --private`); add it as a remote; push.

**Open decision for you:** the two hackathon-brief PDFs at the repo root are not part of the application and
are not in the file list above — confirm whether they should be `.gitignore`d, left untracked, or moved out
of the repo entirely before the first push, since this repo must later go public for submission.

**Stubbed vs real:** N/A — this task takes real, externally-visible actions (git history, a real GitHub
repository). Nothing here is simulated.

**Tests / evidence of completion:** `git log` shows exactly one initial commit containing only the agreed
files; `git remote -v` shows the new repository; the repository's visibility is confirmed **private** in
GitHub's own settings (not just assumed from the create command).

**Approval checkpoint:** Stop here. Three separate go-aheads are required before this task is considered
done: (1) approval to commit, (2) approval to create the GitHub repo, (3) approval to push. Do not start
Task 1 until all three have happened and you've confirmed the result.

---

## Task 1 — Python project skeleton and test tooling only

**Implements requirements:** none directly — this is the scaffold Requirements 1–9 will be built on top of
in later tasks. No business logic is written here.

**Files created/modified:**
- `pyproject.toml` (project metadata; the only dependency is `pytest`, a local dev/test tool)
- `src/strand_sentinel/__init__.py` (empty package marker)
- `tests/__init__.py`, `tests/conftest.py` (empty/minimal)

**Stubbed vs real:** Neither applies — there is no logic yet, so nothing is stubbed and nothing is real.

**Tests / evidence of completion:** `pytest --collect-only` runs cleanly (collects zero tests, proving the
tooling works); `python -c "import strand_sentinel"` succeeds from the project root.

**Approval checkpoint:** Stop here. Do not start Task 2 until you approve this task.

---

## Task 2 — Dependency-free domain models, constants, disclaimer, and deterministic routing logic

**Implements requirements:** 1 (`SyntheticReport` shape), 2.3 (`ProposedToolCall` shape, data only — no
Bedrock call yet), 4 (all of 4.1–4.7, the full routing table), 5.1 (disclaimer text as a constant).

**Files created/modified:**
- `src/strand_sentinel/models.py` — `SyntheticReport`, `ProposedToolCall`, `GroundednessQuestion`,
  `GroundednessAnswer`, `GateOutcome`, `FailureRecord` (Design §4)
- `src/strand_sentinel/constants.py` — the disclaimer text (verbatim, Requirement 5.1), the three outcome
  values, a placeholder confidence-threshold constant (flagged, not calibrated — Design §10)
- `src/strand_sentinel/routing.py` — the deterministic router, translating Design §6's pseudocode into real
  Python
- `tests/test_routing.py`

**Stubbed vs real:** Entirely real. Pure Python, standard library only — no model, no network, no AWS. This
is what "dependency-free" means for this task.

**Tests / evidence of completion:** `pytest tests/test_routing.py -v` passes, with one test per routing
branch in Design §6: Proceed; Guide (missing evidence); Guide (low confidence, non-conflicting); Escalate
(conflicting evidence); Escalate (`FailureRecord` input, from either stage).

**Approval checkpoint:** Stop here. Do not start Task 3 until you approve this task.

---

## Task 3 — Three synthetic fixtures and stubbed Decider/Bedrock adapters

**Implements requirements:** 8.1–8.4, 8.6 (the three required fixtures), 2 (shape of what a Bedrock adapter
interface produces), 3 (shape of what a Decider adapter interface produces), groundwork for 7.1/7.2 (failure
injection via stub).

**Files created/modified:**
- `src/strand_sentinel/fixtures/` — `proceed.txt`, `guide.txt`, `escalate.txt` (fabricated report text, no
  real personal data, per Requirement 1.2/8.6) plus `fixtures.py` exposing each as a `SyntheticReport`
- `src/strand_sentinel/adapters/decider_client.py` — `DeciderClient` interface (Design §7.1) and a
  `StubDeciderClient` returning scripted `GroundednessAnswer`s per fixture, plus a failure-injection mode
- `src/strand_sentinel/adapters/bedrock_client.py` — `BedrockClient` interface and a `StubBedrockClient`
  returning a scripted `ProposedToolCall` per fixture, plus a failure-injection mode
- `tests/test_fixtures.py`

**Stubbed vs real:** Entirely stubbed. Zero network calls, zero AWS, zero Decider installation. These stubs
are kept permanently for unit testing — they are not deleted once Tasks 7–8 add real clients.

**Tests / evidence of completion:** `pytest tests/test_fixtures.py -v` passes, proving each fixture, fed
through the stub adapters, produces the exact `GateOutcome`/`ProposedToolCall` that Task 2's router (already
tested) is known to route to its intended outcome — i.e. the fixtures are proven correct against the router
before the full pipeline exists.

**Approval checkpoint:** Stop here. Do not start Task 4 until you approve this task.

---

## Task 4 — Orchestration pipeline, simulated tool, deterministic failure summary, JSON audit writer

**Implements requirements:** 2 (orchestrator calls the Bedrock adapter), 3.1–3.3 (orchestrator calls the
Decider adapter via the gate), 4 (router wired into the pipeline), 5.1–5.2 (disclaimer attached to every
output), 6.1–6.5 (audit record written every run), 7.1–7.4 (failure → Escalate, end to end, with the
deterministic local fallback summary).

**Files created/modified:**
- `src/strand_sentinel/pipeline.py` — orchestrator wiring Bedrock adapter → groundedness gate → Decider
  adapter → router → output generator
- `src/strand_sentinel/tool.py` — the simulated `create_action_brief`, runnable on Proceed only
  (Requirement 2.2, 4.4)
- `src/strand_sentinel/followup.py` — Guide-path follow-up questions (via the **stub** Bedrock adapter at
  this stage; real Bedrock comes in Task 8)
- `src/strand_sentinel/escalation.py` — Escalate-path summaries: a real, deterministic local fallback
  summary built only from `FailureRecord` fields for failure-triggered Escalate (no model call, by design);
  a conflicting-evidence summary via the **stub** Bedrock adapter at this stage
- `src/strand_sentinel/audit.py` — JSON `AuditRecord` writer (Design §8), writing to `audit/` (already
  `.gitignore`d)
- `tests/test_pipeline.py`

**Stubbed vs real:** Pipeline wiring and the deterministic failure-summary logic are real. Both model calls
still go through Task 3's stub adapters — no real Bedrock or Decider call happens in this task.

**Tests / evidence of completion:** `pytest tests/test_pipeline.py -v` passes for all three fixtures run
end-to-end through the orchestrator: correct `final_outcome`; tool invoked only on Proceed; disclaimer
present on all three; one audit JSON file written per run with every Section 8 field populated; a fourth
test injects adapter failure and proves Escalate with `summary_source == "deterministic_failure_summary"`
and no stub-Bedrock call made for the summary.

**Approval checkpoint:** Stop here. Do not start Task 5 until you approve this task.

---

## Task 5 — Comprehensive unit tests

**Implements requirements:** a coverage/hardening pass proving 4.1–4.7, 5.1–5.2, 6.1–6.5, 7.1–7.4, and
8.1–8.6 are each actually exercised by a test — no new production logic unless a genuine gap is found.

**Files created/modified:** expanded `tests/` coverage (exact filenames illustrative, may be consolidated):
`tests/test_outcomes_proceed.py`, `tests/test_outcomes_guide.py`, `tests/test_outcomes_escalate.py`,
`tests/test_low_confidence.py`, `tests/test_failures.py`, `tests/test_tool_blocking.py`,
`tests/test_disclaimer.py`, `tests/test_audit_schema.py`. No `src/` changes expected; if a testability gap
forces one, it will be called out explicitly and treated as its own review point, not folded in silently.

**Stubbed vs real:** 100% stub-based (Task 3's `StubDeciderClient`/`StubBedrockClient`, extended with
additional scripted low-confidence and malformed-output scenarios). No real model or AWS call.

**Tests / evidence of completion:** full `pytest` run green; a coverage report (`pytest --cov=strand_sentinel`)
and a short written mapping from each Requirement 4/5/6/7/8 acceptance criterion to the specific test(s)
proving it.

**Approval checkpoint:** Stop here. Do not start Task 6 until you approve this task.

---

## Task 6 — Package the reusable `#guardrails` artifact

**Implements requirements:** 9.1–9.5.

**Files created/modified:**
- `patterns/evidence_groundedness_gate/README.md`
- `patterns/evidence_groundedness_gate/questions.md` (the typed question/option set, Design §5)
- `patterns/evidence_groundedness_gate/routing_policy.md` (the routing logic, Design §6)
- `patterns/evidence_groundedness_gate/INTEGRATION.md` (wiring notes — carries Section 10's `[VERIFY]`
  markers for the real Strands wiring until Task 7 resolves them)
- `patterns/evidence_groundedness_gate/tests/` (standalone copy/re-export of the relevant stub-based routing
  tests, proving the pattern works independent of the rest of the repo)

**Open decision for you:** where the OSI license file (Requirement 9.5) lives — a single project-root
`LICENSE`, or one local to the pattern folder too. Proposed default: project-root only; raised again at
Task 10.

**Stubbed vs real:** Documentation plus reused, already-stub-tested code references — no new runtime logic
beyond Tasks 2–4.

**Tests / evidence of completion:** `pytest patterns/evidence_groundedness_gate/tests/` passes standalone;
README reviewed against Requirement 9.2's three required elements (typed question/option set, wiring notes,
usage note).

**Approval checkpoint:** Stop here. Do not start Task 7 until you approve this task.

---

## Task 7 — Verify and integrate the real local Strands Decider 2B

**Package installation, model-weight download, and running any command that executes the real model all
require your explicit approval, step by step, before they happen.** Before any integration code is written,
the following must be confirmed by actually running the tool locally (not assumed from the Section 10
research): exact Mac hardware compatibility (MLX vs. MPS vs. CPU on this specific machine), runtime behaviour,
license, installed package version, CLI/server behaviour, and the real `/v1/systemone` request/response
field names.

**Implements requirements:** resolves the `[VERIFY]` items in Design §10 under "Decider package/API and
output schema" and "Decider deployment/runtime approach"; Requirement 9.4 (reusable artifact uses only
confirmed API calls).

**Files created/modified (only after each approval below):**
- `pyproject.toml` — adds `strands-decider` as a dependency
- `src/strand_sentinel/adapters/real_decider_client.py` — real `DeciderClient` implementation
- `src/strand_sentinel/eval/decider_eval.py` (or similar) — the separate real-model evaluation script
- `patterns/evidence_groundedness_gate/INTEGRATION.md` — VERIFY markers replaced with confirmed specifics

**Explicit sub-approvals required, each separately:**
1. Approval to `pip install strands-decider` into a project-local virtual environment.
2. Approval to download model weights from Hugging Face (`StrandsAgents/...`) — flag expected size/disk use
   before downloading.
3. Confirmation of which local backend (MLX / MPS / CPU) this specific Mac will actually use.
4. Re-confirmation of the Apache-2.0 license at the moment of install (not just from earlier research).
5. Running `strands-decider --help` / a trivial local call to confirm exact CLI/server behavior and response
   schema before any adapter code is written against assumed field names.

**Stubbed vs real:** This is where "real" first appears. `StubDeciderClient` is not removed — it remains the
default for Tasks 2/3/5's unit tests. The real client is used only by the separate evaluation script and by
an explicit opt-in pipeline mode.

**Tests / evidence of completion:** a real-Decider evaluation report (JSON or markdown) recording actual
outputs, confidence values, and per-call latency for the three fixtures, per Design §7.3 — not asserting a
fixed expected outcome per fixture, but flagging any disagreement with the fixture's intended outcome. The
existing stub-based test suite remains green and unmodified in its assertions.

**Approval checkpoint:** Stop here. Do not start Task 8 until you approve this task.

---

## Task 8 — Verify and integrate Amazon Bedrock

**No Bedrock call, AWS login, IAM change, AWS resource creation, or billing action can happen without your
explicit approval.** This task does not start until you have separately approved: AWS credentials to use,
the specific Bedrock model ID, the AWS region, and acknowledged the possible cost.

**Implements requirements:** resolves the `[VERIFY]` items in Design §10 under "Bedrock model ID and
structured-output/tool-use API."

**Files created/modified (only after each approval below):**
- `pyproject.toml` — adds the AWS SDK dependency (name/version to be confirmed, not assumed)
- `src/strand_sentinel/adapters/real_bedrock_client.py` — real `BedrockClient` implementation
- `.env.example` or `src/strand_sentinel/config.py` — model ID/region read from configuration, never
  hard-coded (Design §8's `model_identifiers` note)
- Updates to `followup.py` / `escalation.py` to use the real client behind the existing adapter interface

**Explicit sub-approvals required, each separately:** (1) which AWS account/credentials to use, (2) the
Bedrock model ID, (3) the AWS region, (4) acknowledgment of possible cost, (5) approval immediately before
any `boto3`/`aws` command that could create a resource or incur a charge.

**Stubbed vs real:** `StubBedrockClient` remains the default for all unit tests from Tasks 2–5. The real
client is used only in an explicit opt-in "live" mode.

**Tests / evidence of completion:** a small number of manually-approved live runs against the three fixtures,
logged to the audit JSON with real `model_identifiers` and `latency_ms`, reviewed by you before being
considered done.

**Approval checkpoint:** Stop here. Do not start Task 9 until you approve this task.

---

## Task 9 — Minimal local demo runner

Cannot start until Task 5's full test suite is green. No web UI (Flask/FastAPI/HTML/etc.) is created unless
you separately and explicitly approve one.

**Implements requirements:** none new — supports the hackathon's demo-video requirement
(`reference/PROJECT_BRIEF.md`) using the already-tested pipeline from Tasks 1–8.

**Files created/modified:**
- `src/strand_sentinel/cli.py` — a minimal local script/CLI that runs one of the three fixtures (or a
  supplied report) through the pipeline and prints the outcome, disclaimer, and audit-record path

**Stubbed vs real:** Defaults to the safe, no-cost stub adapters. Real adapters are used only if Tasks 7/8
were approved and are explicitly enabled via a flag/environment variable — never by default.

**Tests / evidence of completion:** a terminal transcript (demo-video-ready) showing all three fixtures run
through the CLI, each producing its intended outcome and the disclaimer.

**Approval checkpoint:** Stop here. Do not start Task 10 until you approve this task.

---

## Task 10 — Explicitly approved minimal local web UI (demonstration layer only)

Cannot start until Task 5 (core deterministic tests passing), Task 7 (real Strands Decider 2B integration
complete), and Task 8 (real Bedrock integration complete) are all done and approved. This task is not in
scope automatically just because those are done — it requires its own separate, explicit approval before
any UI code is written. This supersedes Task 9's default "no web UI unless separately approved" — this task
*is* that separate approval, scoped exactly as follows.

**The UI is a demonstration layer only:**
- It must call the same already-tested pipeline from Tasks 1–8 (the same entry point Task 9's CLI uses) —
  it is a thin presentation layer, nothing more.
- It must **not** reimplement routing or decision logic (Design §6 stays the single source of truth).
- It must **not** change outcomes — whatever the pipeline returns is what the UI shows.
- It must not be built until the core test suite (Task 5) is passing.

**Implements requirements:** none new — supports the hackathon's demo-video/article requirement
(`reference/PROJECT_BRIEF.md`) by presenting the existing, already-tested pipeline visually.

**Files created/modified (only after approval):**
- A minimal web app under `src/strand_sentinel/webui/` (e.g. `app.py` plus one HTML template/static asset
  set for the single page). Exact minimal framework (e.g. a small built-in HTTP server, Flask, or
  equivalent) is proposed and approved at task start, since it adds a new dependency.
- `pyproject.toml` — adds the one chosen minimal web framework dependency (name/version confirmed at
  approval time, not assumed here).

**Scope — must include, and nothing beyond:**
1. A synthetic-report input textarea, plus three preloaded sample buttons — Proceed, Guide, Escalate —
   reusing Task 3's existing fixtures (no new fixtures).
2. A single "Analyse report" action.
3. A visible Bedrock proposal section showing the four proposed arguments.
4. A visible Decider gate section showing per-argument results, the overall result, confidence, and whether
   the tool was permitted or blocked.
5. A visible final outcome panel: Proceed, Guide, or Escalate.
6. A visible JSON audit record viewer or download link (the same `AuditRecord` from Task 4/Design §8).
7. The mandatory disclaimer (Requirement 5.1), always visible, verbatim.
8. Explicitly excluded: login, accounts, database, real personal data, maps, notifications, real routing,
   deployment, or any additional AWS infrastructure.
9. Standard accessible dashboard design: semantic labels, keyboard-operable controls, high contrast, clear
   outcome status conveyed in text/icons (not colour alone).

**Stubbed vs real:** The UI itself contains zero decision logic — it only renders whatever the pipeline
returns. Whether a given run uses stub or real adapters is controlled entirely by Tasks 7/8's existing
opt-in mechanism (same as Task 9's CLI); the UI does not introduce a new adapter path.

**Tests / evidence of completion:** the existing `pytest` suite remains green and untouched (no new
routing/decision tests are needed, since the UI adds no decision logic). A manual walkthrough (or screen
recording) shows all three sample buttons producing their correct outcome end-to-end through the same tested pipeline, using
the real Decider 2B and Bedrock adapters for the final submission demonstration; deterministic stub adapters
may be used only for local development and regression testing, with the disclaimer, audit viewer, and the accessibility checklist in point 9 all verified by
hand (including keyboard-only operation and no colour-only status indication).

**Approval checkpoint (before starting):** Stop here. Do not write any UI code until you explicitly approve:
the one-page scope above exactly as listed, the minimal framework/dependency choice, and confirmation that
Tasks 5, 7, and 8 are all complete and approved.

**Approval checkpoint (after completion):** Stop here. Do not start Task 11 until you approve this task.

---

## Task 11 — GitHub-safe documentation, README, article outline, demo-video script, compliance checklist

**Implements requirements:** the hackathon's non-code submission requirements (written article, repo README,
tags, OSI license, demo video — `reference/PROJECT_BRIEF.md`), plus a final sweep against every "must not"
in `CLAUDE.md` and every acceptance criterion in `docs/requirements.md`.

**Files created/modified:**
- `README.md` (root) — final usage instructions; this is the only task permitted to touch it, and only with
  your explicit approval at that point
- `docs/submission/article_outline.md`
- `docs/submission/demo_video_script.md`
- `docs/submission/compliance_checklist.md`
- `LICENSE` (resolving Task 6's open license-location decision)

**Stubbed vs real:** N/A — documentation only, no code changes.

**Tests / evidence of completion:** a completed compliance checklist confirming every `CLAUDE.md` "must not"
item is absent from the shipped repo, every hackathon qualification item is either satisfied in-repo or
explicitly flagged as a human action you still need to take (actually publishing the article/video is yours
to do, not something this plan automates), and the mandatory disclaimer appears verbatim in both `README.md`
and the CLI's output.

**Approval checkpoint:** Stop here. This is the last task in the plan — confirm completion with you before
considering the submission ready.
