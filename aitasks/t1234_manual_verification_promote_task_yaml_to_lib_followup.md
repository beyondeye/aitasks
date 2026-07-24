---
priority: medium
effort: medium
depends: [1217]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1217]
created_at: 2026-07-24 15:17
updated_at: 2026-07-24 15:17
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1217

## Verification Checklist

- [ ] Launch `ait board` — board paints, cards render, opening a task detail works (exercises parse_frontmatter/serialize_frontmatter via lib/, under the PyPy fast-path interpreter)
- [ ] Launch `ait codebrowser` — the completed-task history list loads (history_data.py, whose board/ sys.path insert was dropped)
- [ ] Launch `ait monitor` — agent panes are listed with their task info (monitor_core.TaskInfoCache -> parse_frontmatter)
- [ ] Launch `ait minimonitor` — same TaskInfoCache path in the split-pane case
- [ ] Launch `ait diffviewer` on a plan file — plan content renders (plan_loader.py, the only importer whose insert was swapped board->lib rather than dropped)
- [ ] In `ait board`, edit and save a task — serialize_frontmatter round-trip is intact and boardcol/boardidx remain ordered last in the frontmatter
- [ ] Run `ait sync` against a task file with a conflict — exercises board/aitask_merge.py under aitask_sync.sh's real PYTHONPATH=board argv (no test covers that argv)
