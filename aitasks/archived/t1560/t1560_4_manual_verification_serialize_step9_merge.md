---
priority: medium
effort: medium
depends: [t1560_1, t1560_2, t1560_3]
issue_type: manual_verification
status: Done
labels: [verification, manual]
verifies: [t1560_1, t1560_2, t1560_3]
assigned_to: dario-e@beyond-eye.com
anchor: 1560
followup_kind: manual_verification
created_at: 2026-08-18 12:26
updated_at: 2026-08-25 09:47
completed_at: 2026-08-25 09:47
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [skip] [t1560_1] Drive two REAL agent sessions to Step 9 under a worktree profile (create_worktree: true) on the same checkout; confirm the second is held out and its merge prompt names the holding task id. — SKIP 2026-08-25 09:46 Covered by the automated suite: tests/test_merge_lock_concurrency.sh pins the hold-out (case1n asserts B refused by the mutex with BUSY:tA: naming the holder), the N=51 concurrent case and the red proof -- 30/30 green on 2026-08-25. The same hold-out and holder-naming were also driven live here in items 2/3/4 with real tmux panes and real session anchors.
- [x] [t1560_1] Confirm the WAITING progress is visible on stderr in a live terminal while queued — a long queue must look queued, not hung. — PASS 2026-08-24 23:26 auto: live tmux pane, holder tA alive; queued pane showed WAITING:tA:0/3/5/7/9 accumulating ~2s apart then BUSY:tA:12 -- queued, not hung
- [x] [t1560_1] Drive a real conflict-parked merge: leave session A at the conflict, confirm session B cannot enter, then abort in A and confirm B proceeds. — PASS 2026-08-24 23:26 auto: live panes; A parked on real MERGE_CONFLICT:shared.txt (lock RETAINED), B got WAITING:tC2/BUSY:tC2:5 and A's conflict was untouched; A abort -> ABORTED, tree clean; B then MERGE_OK
- [x] [t1560_1] Kill an agent pane mid-critical-section and confirm exactly one waiter reclaims, and that a still-running pane is never displaced. — PASS 2026-08-24 23:26 auto: killed the holding pane with 5 waiters queued -- exactly one (W4) got MERGE_OK, other four BUSY:W4:26, zero git errors; while alive the holder was never displaced (all WAITING:tD, force-release REFUSED_LIVE_HOLDER:tD:1750576)
- [x] [t1560_1] Run the wedge path by hand: no tmux and no AIT_AGENT_PID, confirm NO_SESSION_ANCHOR is refused with both remedies readable, then confirm status + force-release recover a planted wedged lock. — PASS 2026-08-24 23:26 auto: env -u TMUX -u AIT_AGENT_PID -> NO_SESSION_ANCHOR exit 0, nothing reserved; both remedies named in rendered merge-broker.md; planted wedge -> status HELD:tA|pid|dead, dry-run printed target+blast radius+armed token, wrong --expect HOLDER_CHANGED (still held), correct token FORCE_RELEASED -> FREE
- [skip] [t1560_1] Confirm the helper whitelist works: invoke aitask_merge_task.sh from a skill in Claude Code and confirm no permission prompt appears. — SKIP 2026-08-25 09:46 Permission mode makes it unobservable: this session's permission mode cannot be determined from inside it, so 'no prompt appeared' is not independent evidence. The allow entry Bash(./.aitask-scripts/aitask_merge_task.sh:*) is present in .claude/settings.local.json and in the Claude/Codex/OpenCode seed configs, its prefix matches the invocation form the rendered Step 9 uses, and the broker ran cleanly from this Claude Code session.
- [x] [t1560_2] Read the rendered merge-approval question in a REAL terminal at a realistic pane width — confirm the queued-behind clause is readable and does not wrap the pinned prefix off-screen. — PASS 2026-08-25 07:49 auto: real tmux panes at 163/120/100/80 cols -- one full line at 100-163 with 'Queued behind t1560.' readable; pinned prefix leads the string so no wrap can push it off-screen. Confirmed against a REAL live Claude Code AskUserQuestion widget captured from this agent's own pane: a 200-char question rendered on ONE line at 224 cols, so the 91-char merge question is comfortably single-line
- [x] [t1560_2] Walk the rendered SKILL-default.md Step 9 by eye and confirm every broker verdict has a branch and no in-flight exit reaches cleanup. — PASS 2026-08-24 23:26 auto: walked rendered Step 9 + merge-broker-default.md; every begin/finish/abort/cleanup/status verdict has a table row (force-release deliberately excluded as a human verb); verification-outcomes table gives cleanup:no to every stop-in-flight/re-run row; test_merge_broker_rendered_verdicts.sh 25/25
- [x] [t1560_2] Confirm ait monitor / minimonitor still classify the merge-approval prompt as POSTIMPL/WAITING against a live agent showing it. — PASS 2026-08-25 07:49 auto: phase_from_screen on live tmux captures at 163/120/100/80 all -> ('POSTIMPL','WAITING', merge_approval anchor); negative controls (reworded anchor, chip removed) both -> None. Confirmed against a REAL live widget captured from this agent's pane: current_question_block matched its ' ☐ Verify' chip, and the real widget frame carrying the merge question classified POSTIMPL/WAITING. test_workflow_phase_prompt_drift.sh 17/17
- [x] [t1560_2] Resume a task at POSTIMPL after an error/blocked verification exit and confirm aitask/<task_name> and its worktree are still present and the merge re-reserves. — PASS 2026-08-24 23:26 auto: in-flight exit -- cleanup without --task-complete refused (CLEANUP_REQUIRES_COMPLETION), finish alone RELEASED, aitask/tW branch + aiwork/tW worktree both survived; resume from a different pane re-ran begin -> MERGE_OK same sha (no new commit), lock re-HELD; positive control: cleanup --task-complete -> CLEANED, both removed
- [skip] [t1560_3] Build the website and read the two changed pages in a browser: the locks table, the anchor precondition, and the force-release ladder must each be findable without prior knowledge. — SKIP 2026-08-25 09:46 No browser available in this session: the Chrome extension is not connected. hugo build --gc --minify succeeded (237 pages, rc=0) and both changed pages were read as served -- the locks page carries 'The merge mutex' / 'What the merge mutex excludes' (table), 'Before a merge can start: the session anchor' and 'Recovering a stuck merge mutex', all three in the sidebar TOC, and parallel-development's 'Serialized Merge-Back' cross-links to both.
- [x] [t1560_3] Confirm no page names a real repository or lists diffviewer among the TUIs. — PASS 2026-08-24 23:26 auto: neither changed page mentions diffviewer, lists TUIs, or names any real repository/external URL
