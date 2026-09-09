---
priority: medium
effort: medium
depends: [1755]
issue_type: manual_verification
status: Done
labels: [verification, manual]
verifies: [1755]
assigned_to: dario-e@beyond-eye.com
anchor: 1755
followup_kind: manual_verification
created_at: 2026-09-09 13:39
updated_at: 2026-09-09 15:34
completed_at: 2026-09-09 15:34
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1755

## Verification Checklist

- [x] Interactive `ait create` (fzf flow) runs end-to-end and creates a normally numbered task — the automated rows only drive --batch. — PASS 2026-09-09 15:32 auto: interactive fzf flow end-to-end in an isolated fixture (tmux-driven) created aitasks/t1_interactive_smoke.md, counter 1->2, committed, exit 0, draft removed
- [x] Interactive draft finalize ("Finalize now" from the fzf post-draft menu) with a FAILING counter: aborts non-zero, the draft file survives, and the message names it ("Draft left at <path>"). Row 4 of tests/test_create_id_claim_abort.sh covers only `--batch --finalize`, a different entry point. — PASS 2026-09-09 15:32 auto: 'Finalize now' with a failing counter exited 1; draft survived; message 'Draft left at aitasks/new/draft_...md; nothing was created'; HEAD and worktree unchanged
- [x] Interactive local-scan fallback: with a broken counter on a TTY, `ait create` prompts "Use local scan anyway? (y/N)". Answering y creates a normally numbered task; answering N aborts with no aitasks/t_*.md, no commit, and `aitask_claim_id.sh --peek` unchanged. This branch needs `-t 0` and is unreachable from any automated row, yet t1755 edited exactly this function. — PASS 2026-09-09 15:32 auto: TTY prompt 'Use local scan anyway? (y/N)' shown; y -> aitasks/t1_local_scan_yes.md committed; N -> exit 1, no t_*.md, HEAD/worktree unchanged, --peek 4 -> 4 (delegating stub so peek reflects the real counter)
- [x] With TMPDIR pointing at a non-existent directory, interactive `ait create` shows "Cannot allocate a temp file for the ID-claim diagnostic" and NOT the pre-fix shell noise ("aitask_create.sh: line NNN: :", "cat: ''"). — PASS 2026-09-09 15:32 auto: broken TMPDIR shows 'Cannot allocate a temp file for the ID-claim diagnostic'; no 'cat: ''', no 'aitask_create.sh: line', no 'unknown error'. Pre-fix control at ec9641e79^ emitted all three plus wrote aitasks/t_tmpdir_broken.md (ID: t) at exit 0
