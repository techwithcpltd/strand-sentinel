# Demo Video Checklist — StrandSentinel

Target: under 3 minutes total (hackathon rule: judges aren't required to watch beyond 3:00).

Recording basis: `docs/demo/OFFLINE_DEMO.md`. Everything shown must be reproducible with:
```bash
python -m strand_sentinel.cli proceed
python -m strand_sentinel.cli guide
python -m strand_sentinel.cli escalate
```

## Suggested timing

- [ ] **0:00–0:15** — one-sentence hook: what StrandSentinel is and the decision handed to Decider 2B
- [ ] **0:15–0:45** — **Proceed** path, narrated: grounded report → tool runs
- [ ] **0:45–1:15** — **Guide** path, narrated: missing evidence → tool blocked, follow-up questions shown
- [ ] **1:15–1:50** — **Escalate** path, narrated: conflicting evidence → tool blocked, human-review summary shown
- [ ] **1:50–2:15** — show the generated audit JSON for one run; point out the per-argument Decider results
- [ ] **2:15–2:40** — one sentence on the `#guardrails` pattern + point at `patterns/evidence_groundedness_gate/`
- [ ] **2:40–2:55** — disclaimer visible on screen at least once; state plainly this supports human triage only
- [ ] Under 3:00 total

## Content accuracy checklist (do not overclaim)

- [ ] Narration does **not** claim a live Amazon Bedrock call is happening — Bedrock is the deterministic
      stub in this demo; say so explicitly if Bedrock is mentioned at all
- [ ] If `--real-decider` is shown, narration makes clear this is **local** MLX inference, not a cloud call
- [ ] The mandatory disclaimer text is shown on screen, verbatim, at least once:
      "Supports human triage only; not emergency, legal or medical advice."
- [ ] No claim that the tool performs real-world routing, notification, or dispatch — it's explicitly simulated

## Publishing checklist (hackathon rules)

- [ ] Uploaded to YouTube, Vimeo, Facebook Video, or Youku
- [ ] Set to publicly visible
- [ ] Link included in the Builder Center submission
- [ ] No third-party trademarks included
- [ ] No copyrighted music or other material without permission
