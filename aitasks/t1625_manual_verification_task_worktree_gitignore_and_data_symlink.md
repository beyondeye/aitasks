---
priority: medium
effort: medium
depends: [1616]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1616]
anchor: 1159
followup_kind: manual_verification
created_at: 2026-08-26 14:39
updated_at: 2026-08-26 14:39
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1616

## Verification Checklist

- [ ] Pick a task under a `create_worktree: true` profile and confirm Step 7 runs `./.aitask-scripts/aitask_init_data.sh --link-worktree "$worktree_path"` AFTER the fork and BEFORE work starts in the worktree, and that the agent branches correctly on each stdout token (LINKED / ALREADY_LINKED / LEGACY_MODE / NOT_INITIALIZED). The Step 7 prose is agent-executed, so only the golden diff covers it — never a live run.
- [ ] Confirm the same call fires on the REUSE path: re-pick a task whose worktree already exists (classifier returns `USABLE`), and check the agent passes the classifier's `$wt_path`, not the conventional `aiwork/<task_name>` path.
- [ ] Confirm a refusal is surfaced verbatim and STOPS the workflow rather than being worked around: pre-create `aitasks/` as a real directory inside the worktree, re-pick, and verify the agent reports the message and does not delete the directory.
- [ ] From inside a real linked task worktree, launch `ait board` and `ait monitor` and confirm both read task data correctly — TUI surfaces the python suite cannot cover.
- [ ] Confirm `./ait git add aitasks/<file>` from inside a linked worktree commits to the aitask-data branch (branch mode) rather than degrading to legacy mode.
