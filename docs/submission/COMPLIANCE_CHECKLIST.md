# Compliance Checklist — StrandSentinel

Snapshot as of this review. Re-check before final submission, since some items (GitHub visibility, license,
article, video) are still outstanding.

## `CLAUDE.md` "must not" list — in-repo verification

| Constraint | Status | Evidence |
|---|---|---|
| No real-world routing or dispatch | ✅ | `tool.py`'s `create_action_brief` only assembles a dict; `tests/test_tool_blocking.py` |
| No real notifications | ✅ | Nothing in the codebase sends any notification, anywhere |
| No emergency response functionality | ✅ | No such code path exists |
| No legal advice | ✅ | No such code path exists |
| No medical advice | ✅ | No such code path exists |
| All report inputs synthetic, no real personal data | ✅ | `src/strand_sentinel/fixtures/*.txt` all explicitly labelled "SYNTHETIC DEMO REPORT — fabricated" |
| Mandatory disclaimer on every user-facing output | ✅ | `tests/test_disclaimer.py` (4 tests, all outcome categories) |
| No AWS resources created without approval | ✅ | No AWS resources created and no IAM changes made by this project; Task 8 gates D and E were each approved and used once (see below) |

## Hackathon qualification checklist (from `reference/PROJECT_BRIEF.md`)

| Requirement | Status |
|---|---|
| Agent uses Strands Decider 2B for a meaningful decision, paired with Amazon Bedrock | ⚠️ **Partial** — Decider 2B is genuinely integrated and locally verified; Bedrock is mock-verified locally only (one approved live attempt was denied with `AccessDeniedException`). See the explicit note below. |
| Written article on Builder Center | ❌ Not written (outline drafted: `docs/submission/ARTICLE_OUTLINE.md`) |
| Public repository with source + reusable decision pattern | ⚠️ **Repo is currently private** — `patterns/evidence_groundedness_gate/` exists and is tested, but the repo itself must be made public before submission |
| Public demo video, under 3 minutes | ❌ Not recorded (checklist drafted: `docs/submission/VIDEO_CHECKLIST.md`) |
| Tags `#strands-decider-2b` and `#guardrails` applied | ❌ Not yet applied (applied on the Builder Center post itself, not in-repo) |
| Original agent, not previously published | ✅ |
| OSI-approved open source license | ⚠️ Pending — MIT `LICENSE` added this session with a placeholder copyright holder that must be filled in before publishing |

## Explicit statement on Bedrock status (do not overclaim in article/video)

**Amazon Bedrock has never returned a live response in this project.** One approved live Converse attempt
(synthetic report text, single request, no retries, returned tool never executed) was denied with
`AccessDeniedException` because the AWS account lacks the required model agreement.

`RealBedrockClient` (`src/strand_sentinel/adapters/real_bedrock_client.py`) is implemented against the
official Bedrock Converse API shape and is covered by 26 unit tests using an injected, fully mocked boto3
client (`tests/test_real_bedrock_client.py`) — every test explicitly monkeypatches `boto3.Session` to raise
if ever constructed, proving no default AWS credential discovery occurs.

No AWS credentials, account details, or region are configured in this repository; the single live attempt
used a named credential profile selected outside the repository. Anthropic's model-access use-case form has
since been submitted for that account, but the model agreement still reported `NOT_AVAILABLE` at the last
read-only check.

The default CLI demo (`python -m strand_sentinel.cli`) and the test suite remain offline: they always use
`StubBedrockClient`, and the CLI provides no way to invoke the real adapter at all. Any submission material
should state this plainly rather than imply a live Bedrock integration.

**Strands Decider 2B, by contrast, is a genuine local integration**, verified by one approved live local CLI
call (model `StrandsAgents/strands-decider-2B-hobson-v19`, `device="mlx"` on Apple Silicon) and available in
the demo via the explicit `--real-decider` flag.

## Outstanding items before final submission

1. Make the GitHub repository public (currently private; requires separate explicit approval).
2. Fill in the `LICENSE` copyright holder placeholder.
3. Decide whether to retry one live Bedrock call once the model agreement reports as available (requires
   fresh, separate approval), or submit with Bedrock explicitly documented as mock-verified with one denied
   live attempt, and Decider 2B as the fully-real, demonstrated integration.
4. Write and publish the Builder Center article (from the outline).
5. Record and publish the demo video (from the checklist).
6. Apply the `#strands-decider-2b` and `#guardrails` tags on the Builder Center submission.
