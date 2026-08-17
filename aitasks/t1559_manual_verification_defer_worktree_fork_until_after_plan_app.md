---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: []
verifies: [1536]
anchor: 1536
followup_kind: carry_over
created_at: 2026-08-17 23:09
updated_at: 2026-08-17 23:09
---

Carry-over of deferred manual-verification items from t1546. Re-pick this task to continue the remaining checklist.

## Verification Checklist

- [ ] Run a real /aitask-pick under a create_worktree:true profile (no shipped profile sets it, so the scripted acceptance run in t1536 never exercised the live pick path). — DEFER 2026-08-17 18:58 auto: not automatable -- requires a real interactive /aitask-pick session (worktree mode is reachable under the default profile by answering Yes; no shipped profile sets create_worktree: true, only fast.yaml sets it false). Driving one would mean implementing a real task end to end and cutting real branches. Human run needed.
- [ ] Fork timing: the worktree appears only after the plan is approved AND the Remote Drift Check returns "Continue anyway" — not before. — DEFER 2026-08-17 18:58 auto: blocked on item 1 -- fork TIMING relative to plan approval + the drift check's 'Continue anyway' can only be observed inside a live pick. Source ordering was verified (item 13); the live observation is the missing evidence.
- [ ] Drift stop leaves nothing: choose "Stop and re-verify plan" and confirm no worktree or aitask/ branch was created, then re-pick and confirm it cuts cleanly from the pulled base. — DEFER 2026-08-17 18:58 auto: blocked on item 1 -- the 'Stop and re-verify plan' exit and the subsequent re-pick are multi-turn interactive stop paths.
- [ ] Approve-and-stop leaves nothing: choose "Approve and stop here" and confirm the same, then re-pick without a "branch already exists" failure (the t1392 collision). — DEFER 2026-08-17 18:58 auto: blocked on item 1 -- 'Approve and stop here' + clean re-pick (the t1392 branch-already-exists collision) needs a live plan-approval checkpoint.
- [ ] Decomposed parent: let planning create child tasks and stop — confirm the parent stranded no worktree. — DEFER 2026-08-17 18:58 auto: blocked on item 1 -- requires live planning that decomposes a parent into children and then stops.
- [ ] Risk-mitigation "before" stop: confirm the worktree DOES exist on that path and that a re-pick reuses it rather than failing. — DEFER 2026-08-17 18:59 auto: blocked on item 1 -- needs a live risk-gated plan with a 'before' mitigation line so the Step 7 session-stop branch fires; the reuse-on-re-pick half is covered mechanically by item 11.
- [ ] Re-entry under a DIFFERENT profile: resume a worktree-mode task under fast and confirm the fork still runs (header-driven), then resume a current-branch task under a worktree profile and confirm no worktree appears. — DEFER 2026-08-17 18:59 auto: partially verified, live half owed. Verified: Re-entry Routing resolves worktree intent from the plan header's Worktree: field with an explicit prohibition on profile.create_worktree, and the block is byte-identical across default/fast/remote and claude/codex/opencode; the header-parse snippets were executed (present / empty / unsafe cases all behave). Not verified: an actual cross-profile resume.
- [ ] Step 9 merge: complete a worktree-mode task end to end and confirm the merge and worktree cleanup still work. — DEFER 2026-08-17 18:59 auto: blocked on item 1 -- an end-to-end worktree-mode task through Step 9 merge + worktree cleanup requires a full live implementation cycle.
