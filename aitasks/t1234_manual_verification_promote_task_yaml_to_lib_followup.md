---
priority: medium
effort: medium
depends: [1217]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1217]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-24 15:17
updated_at: 2026-07-28 13:02
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1217

## Verification Checklist

- [x] Launch `ait board` — board paints, cards render, opening a task detail works (exercises parse_frontmatter/serialize_frontmatter via lib/, under the PyPy fast-path interpreter) — PASS 2026-07-28 13:02 auto: board rendered cards and opened t1216 task detail in tmux
- [x] Launch `ait codebrowser` — the completed-task history list loads (history_data.py, whose board/ sys.path insert was dropped) — PASS 2026-07-28 13:02 auto: codebrowser history displayed 1,528 completed tasks in tmux
- [x] Launch `ait monitor` — agent panes are listed with their task info (monitor_core.TaskInfoCache -> parse_frontmatter) — PASS 2026-07-28 13:02 auto: monitor rendered 7 sessions and 23 panes in tmux
- [x] Launch `ait minimonitor` — same TaskInfoCache path in the split-pane case — PASS 2026-07-28 13:02 auto: minimonitor rendered agent panes with task info in tmux
- [defer] Launch `ait diffviewer` on a plan file — plan content renders (plan_loader.py, the only importer whose insert was swapped board->lib rather than dropped) — DEFER 2026-07-28 13:02 auto: diffviewer launched but selecting and visually confirming plan content requires interactive TUI navigation
- [defer] In `ait board`, edit and save a task — serialize_frontmatter round-trip is intact and boardcol/boardidx remain ordered last in the frontmatter — DEFER 2026-07-28 13:02 auto: editing and save ordering requires interactive board mutation; not performed against user task data
- [defer] Run `ait sync` against a task file with a conflict — exercises board/aitask_merge.py under aitask_sync.sh's real PYTHONPATH=board argv (no test covers that argv) — DEFER 2026-07-28 13:02 auto: real sync-conflict exercise blocked by remote fetch failure and requires a safe conflict fixture
