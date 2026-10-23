# Integration — wiring the gate into an agent's tool-call path

## Current boundary: real local Decider 2B (Task 7); Bedrock mock-verified, one live attempt denied (Task 8)

As implemented in this repository today, the gate runs entirely through `strand_sentinel.pipeline.run()`,
which calls two adapter interfaces:

- `strand_sentinel.adapters.bedrock_client.BedrockClient` — `StubBedrockClient` remains the default for all
  deterministic unit tests. As of Task 8, a second implementation also exists:
  `strand_sentinel.adapters.real_bedrock_client.RealBedrockClient`, built against the official Bedrock
  Converse API shape and validated with **mocked** boto3 clients (`tests/test_real_bedrock_client.py`).
  **Bedrock is mock-verified locally only.** One approved live Converse attempt (synthetic report text,
  single request, no retries, returned tool never executed) was denied with `AccessDeniedException`
  because the AWS account lacks the required model agreement; no live Bedrock response has been received.
  See the dedicated section below for the full status of Task 8 gates D, E, and F.
- `strand_sentinel.adapters.decider_client.DeciderClient` — `StubDeciderClient` still exists and remains the
  default for all deterministic unit tests (Tasks 1–6 unchanged). As of Task 7, a second, real
  implementation also exists: `strand_sentinel.adapters.real_decider_client.RealDeciderClient`, which calls
  the installed `strands-decider` package's Python API directly. **This is a genuine local integration, not
  a stub** — confirmed by one approved local CLI verification call (model
  `StrandsAgents/strands-decider-2B-hobson-v19`, `device="mlx"` on an Apple M3) and by direct inspection of
  the installed package's `strands_decider.schema` module. Still entirely local: no AWS, no Bedrock, no
  network call other than the one-time Hugging Face model download into this repository's project-local
  `.hf_cache/` (never the global HF cache).

This dual-adapter setup is intentional: `StubDeciderClient` keeps the deterministic unit-test suite fast,
offline, and independent of a ~1.2GB optional dependency group; `RealDeciderClient` is used only by the
separate real-model evaluation script (`strand_sentinel.eval.decider_eval`) and by an explicit opt-in
pipeline mode, never by default.

### Confirmed real Decider 2B response shape (Task 7)

Directly confirmed — not assumed — by inspecting the installed `strands_decider.schema` module's pydantic
field definitions, and corroborated by the one approved CLI verification call:

- **Binary ("noul") answers are a bare scalar float**, e.g. `NoulAnswer.noul = 0.815` — there is no
  `"yes"`/`"no"` string anywhere in the real response. A caller must choose its own threshold; this
  project's adapter uses `>= 0.5 -> "yes"`, `< 0.5 -> "no"`.
- **Choice answers carry three separate pieces of information**, not one "value + confidence" pair:
  - `choice: str` — the selected label (e.g. `"grounded"`)
  - `probabilities: dict[str, float]` — the full distribution over every option (e.g.
    `{"grounded": 0.447, "missing_evidence": 0.333, "conflicting_evidence": 0.220}`)
  - `confidence: float` — a **separate** scalar (e.g. `0.171`), confirmed (via the installed package's own
    `derive_confidence()` source) to be a *normalised max-probability concentration score* —
    `(N * p_max - 1) / (N - 1)` — not the selected option's own probability. For the example above:
    `(3 * 0.447 - 1) / 2 ≈ 0.171`, which exactly matches the real CLI output observed in the approved
    verification call.

**These semantics are adapter-normalized and must not be confused with each other.** This project's
`RealDeciderClient` (`src/strand_sentinel/adapters/real_decider_client.py`) keeps all of these values —
`yes_probability`, `selected_probability`, `model_confidence`, and the full `probabilities` distribution —
preserved, unreduced, in `GroundednessAnswer.raw_decider_output`. The existing `GroundednessAnswer.confidence`
field (the one `strand_sentinel.routing.route()` actually uses) is set via an explicitly documented
compatibility mapping, not by guessing which real number "is" the confidence:
- per-argument (noul): the probability mass behind whichever label was actually chosen (`yes_probability` if
  `"yes"`, else `1 - yes_probability`)
- overall (choice): `selected_probability` (`probabilities[choice]`) — **not** `model_confidence`

### Verified model/backend/cache details

| | |
|---|---|
| Model ID | `StrandsAgents/strands-decider-2B-hobson-v19` |
| Backend | `device="mlx"` — confirmed working on Apple M3 / macOS arm64 |
| Python API entry point | `strands_decider.infer.load_engine(checkpoint, device=...)` returning a `SystemOneEngine`, whose `.ask(state, questions)` method is what `RealDeciderClient` calls |
| Cache location | Project-local `.hf_cache/` via the standard `HF_HOME` environment variable — confirmed the global `~/.cache/huggingface/` was never created or touched |
| Download size | ~4.3 GB (base model + adapter/head), confirmed via one approved download |
| License | Apache-2.0 |

### What remains pending verification

The Python API's `engine.ask(...)` call itself (as opposed to the CLI, which wraps it) has **not** been
separately exercised with a live model in this repository — the one approved verification call went through
the CLI (`strands-decider ask`), which internally uses this same API per the package's own source, but a
standalone live Python-API call has not been separately requested or run. `RealDeciderClient`'s unit tests
(`tests/test_real_decider_client.py`) mock this boundary entirely and do not substitute for that live check.
Mark this pending until a live Python-API call is separately approved and run.

### Amazon Bedrock (Task 8 — mock-verified; one live attempt denied)

`strand_sentinel.adapters.real_bedrock_client.RealBedrockClient` implements the same `BedrockClient`
contract (`propose_tool_call`, `draft_follow_up_questions`, `draft_conflict_summary`) using the official
Bedrock Converse API shape. **Status: mock-verified locally only.** One approved live Converse attempt was
denied with `AccessDeniedException` because the AWS account lacks the required model agreement, and no
live Bedrock response has been received. Every test in `tests/test_real_bedrock_client.py` runs against an
injected, fully mocked boto3 client, with `boto3.Session` itself monkeypatched to raise if ever
constructed, proving the default credential-discovery path is never touched.

Confirmed facts this adapter is built against (official AWS documentation, read-only research — no AWS
account was contacted to obtain these):
- **Converse requires the `bedrock:InvokeModel` IAM permission** — denying `InvokeModel` also blocks
  `Converse` automatically; there is no separate permission for `Converse` itself.
- **Bedrock tool use produces a request, never an execution.** A forced tool-use Converse call returns
  `stopReason == "tool_use"` and a `toolUse` content block naming the tool and its proposed `input` — the
  adapter only parses this into a `ProposedToolCall`. It never calls
  `strand_sentinel.tool.create_action_brief` or any other execution path; execution remains exclusively in
  the application pipeline, gated on Strands Decider's routing decision (confirmed by
  `tests/test_real_bedrock_client.py::test_adapter_never_calls_tool_execution_function`).
- Many Claude models on Bedrock are invoked on demand through a **cross-region inference profile ID**
  (e.g. `us.anthropic.claude-sonnet-5`) rather than the bare foundation-model ID, depending on model and
  region — per an official model-card page's regional-availability table. This is not universal:
  read-only Bedrock metadata showed `anthropic.claude-sonnet-5` supports direct `ON_DEMAND` invocation in
  `eu-west-2` as well as inference profiles, so check `inferenceTypesSupported` for the specific model and
  region.
- Anthropic models on Bedrock are **Marketplace-billed third-party models**, requiring a one-time model-access
  grant and Marketplace subscription per account/region before any call can succeed — separate from IAM
  permissions.
- Structured-output support (`outputConfig.textFormat`) was seen only in the abstract CLI parameter
  reference, not in a complete boto3 code example, so `draft_follow_up_questions` and `draft_conflict_summary`
  deliberately use plain-text Converse calls with strict, self-validated line/text parsing instead of that
  less-confirmed structured-output shape — the more conservative choice, not an assumption.

**Live-use status (Task 8 gates D, E, F):**
- **Gate D (credentials) — approved and used once.** No AWS credentials are configured in this
  repository; a named credential profile was selected outside the repository for the single approved live
  attempt only.
- **Gate E (live call) — approved and used once.** One live Converse attempt was made (synthetic report
  text, single request, no retries, returned tool never executed) and was denied with
  `AccessDeniedException`. No live Bedrock response has been received, so every behavior above remains
  verified against official documentation and mocked tests only.
- **Gate F (account setup).** No AWS resources, IAM policies, roles, or users have been created or changed
  by this project. Anthropic's model-access use-case form has been submitted for the account, but the model
  agreement still reported `NOT_AVAILABLE` at the last read-only check.
- Any further live use requires, at minimum: an explicit AWS profile (never boto3's default credential
  chain, per `RealBedrockClient`'s constructor contract), an explicit region, an explicit approved model or
  inference-profile ID, the model agreement reporting as available, and fresh, separate approval for each
  live call.

## Future wiring: Strands `InterventionHandler`

Per the official Strands Agents documentation (confirmed research, recorded in `docs/design.md` Section 10):
a handler subclasses `InterventionHandler` and overrides `before_tool_call(event: BeforeToolCallEvent)`,
returning one of five typed actions: `Proceed`, `Deny`, `Guide`, `Confirm`, `Transform`.

This pattern's **Proceed** and **Guide** outcomes map directly onto the SDK's own `Proceed`/`Guide` actions.
Its **Escalate** outcome has **no SDK equivalent** — it must be implemented at the application layer, most
likely by returning `Deny` (to block the tool call) while the actual escalation handling — the neutral
summary, the audit record, surfacing it to a human reviewer — happens entirely in application code, not
inside the SDK's intervention mechanism.

### Illustrative wiring sketch (pseudocode — does not import any uninstalled package)

```python
# ILLUSTRATIVE ONLY. The Strands SDK is not installed in this repository yet
# (Task 7/8 gate real package installation). Do not run this as-is.
#
# from strands.interventions import InterventionHandler              # [VERIFY]
# from strands.interventions.actions import Proceed, Deny, Guide      # [VERIFY]

from strand_sentinel.constants import Outcome
from strand_sentinel.pipeline import run as run_groundedness_gate


class EvidenceGroundednessInterventionHandler:  # (InterventionHandler):  # [VERIFY base class]
    """Sketch of how this pattern would plug into a real Strands agent's
    tool-call path. The gate call itself (`run_groundedness_gate`) is real,
    already-tested code from this repository; only the surrounding
    InterventionHandler scaffolding is illustrative.
    """

    def __init__(self, bedrock_client, decider_client, threshold):
        self._bedrock = bedrock_client
        self._decider = decider_client
        self._threshold = threshold

    def before_tool_call(self, event):  # event: BeforeToolCallEvent  # [VERIFY]
        result = run_groundedness_gate(
            report=event.report,  # [VERIFY] real event field name
            bedrock=self._bedrock,
            decider=self._decider,
            threshold=self._threshold,
        )

        if result.outcome is Outcome.PROCEED:
            return "Proceed()"  # real: Proceed(reason=...)  # [VERIFY]

        if result.outcome is Outcome.GUIDE:
            feedback = "; ".join(result.follow_up_questions)
            return f"Guide(feedback={feedback!r})"  # real: Guide(feedback=feedback)  # [VERIFY]

        # Outcome.ESCALATE: no SDK action exists for this. Block the tool via
        # Deny, and handle the actual escalation (summary, audit, human
        # notification) entirely in application code — not shown here.
        return f"Deny(reason={result.escalation_summary!r})"  # real: Deny(reason=...)  # [VERIFY]
```

The return values above are written as strings rather than real `Proceed(...)`/`Guide(...)`/`Deny(...)`
constructor calls specifically so this file never imports or calls an uninstalled package — swap them for
the real constructors once the Strands SDK is installed and its exact signatures are confirmed (Task 7/8).

## Safe integration boundary, summarized

| Layer | What it is allowed to do |
|---|---|
| Groundedness gate (`routing.route`, `pipeline.run`) | Decide Proceed / Guide / Escalate. Never calls a real tool, never does real-world routing/notification. |
| Intervention handler (future, real Strands) | Translate Proceed/Guide into the matching SDK action. Translate Escalate into `Deny` (or equivalent block), with no SDK-native "escalate" semantics. |
| Application code around the handler | Owns everything Escalate actually *means* for a human reviewer — the summary, the audit trail, any downstream review workflow. The SDK has no opinion about this, by design (per the official docs: *"Strands has no opinion about what goes inside"* an intervention handler). |
