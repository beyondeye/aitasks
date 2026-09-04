---
priority: medium
effort: medium
depends: [1704]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1704]
anchor: 1599
followup_kind: manual_verification
created_at: 2026-09-04 16:55
updated_at: 2026-09-04 16:55
boardcol: now
boardidx: 28742
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1704

## Verification Checklist

- [ ] Push a config into a clean sibling repo via `ait syncer` -> Settings tab -> `p`; the results screen names the commit, and `ait git log -1` in that repo shows `ait: Update codeagent_config.json` touching only that path with a clean data worktree
- [ ] Push into a sibling whose codeagent_config.json is dirty; the result line says it was not applied, and that repo's bytes are unchanged
- [ ] Push into a sibling wedged mid-merge; the result line names the state (e.g. MERGE_HEAD) so it is clear which `--abort` to run there
- [ ] Push into a sibling that has not been upgraded past t1677; the result line says its framework copy cannot commit metadata and points at the Versions tab, with no raw Python error text
- [ ] Push to the local layer; the result line says it is gitignored there and nothing was committed, rather than reading as a failure
- [ ] Run a Clear + project push whose commit fails in the destination; confirm the local override is KEPT, the result line offers a retry, and that repo's effective value is unchanged
- [ ] Confirm the results screen footer no longer claims "Nothing was committed"
- [ ] Read the results screen at a realistic terminal width - confirm the per-destination lines are legible and not truncated mid-sentence
- [ ] TODO: verify .aitask-scripts/syncer/syncer_app.py end-to-end in tmux
- [ ] TODO: verify .aitask-scripts/syncer/settings_screens.py end-to-end in tmux
