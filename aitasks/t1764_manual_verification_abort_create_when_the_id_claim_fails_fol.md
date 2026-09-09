---
priority: medium
effort: medium
depends: [1755]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [1755]
assigned_to: dario-e@beyond-eye.com
anchor: 1755
followup_kind: manual_verification
created_at: 2026-09-09 13:39
updated_at: 2026-09-09 15:07
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1755

## Verification Checklist

- [ ] Interactive `ait create` (fzf flow) runs end-to-end and creates a normally numbered task — the automated rows only drive --batch.
- [ ] Interactive draft finalize ("Finalize now" from the fzf post-draft menu) with a FAILING counter: aborts non-zero, the draft file survives, and the message names it ("Draft left at <path>"). Row 4 of tests/test_create_id_claim_abort.sh covers only `--batch --finalize`, a different entry point.
- [ ] Interactive local-scan fallback: with a broken counter on a TTY, `ait create` prompts "Use local scan anyway? (y/N)". Answering y creates a normally numbered task; answering N aborts with no aitasks/t_*.md, no commit, and `aitask_claim_id.sh --peek` unchanged. This branch needs `-t 0` and is unreachable from any automated row, yet t1755 edited exactly this function.
- [ ] With TMPDIR pointing at a non-existent directory, interactive `ait create` shows "Cannot allocate a temp file for the ID-claim diagnostic" and NOT the pre-fix shell noise ("aitask_create.sh: line NNN: :", "cat: ''").
