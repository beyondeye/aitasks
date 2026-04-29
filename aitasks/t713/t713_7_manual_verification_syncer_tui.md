---
priority: medium
effort: medium
depends: [t713_6]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [713_1, 713_2, 713_3, 713_4, 713_5, 713_6]
created_at: 2026-04-29 15:01
updated_at: 2026-04-29 15:01
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t713_1] Run the desync helper against a repo with remote-ahead `main` and confirm the row reports behind count, commit subjects, and changed paths.
- [ ] [t713_1] Run the desync helper against branch-mode task data and confirm `aitask-data` reports stale local data without reading directly from `origin/aitask-data` as a resolver fallback.
- [ ] [t713_2] Launch `ait syncer` inside tmux and confirm the TUI renders exactly `main` and `aitask-data` rows with a usable details pane.
- [ ] [t713_3] Trigger task-data sync from the syncer and confirm it follows the same statuses and interactive fallback behavior as board `ait sync`.
- [ ] [t713_3] Trigger or simulate a failing `main` pull/push and confirm the error details and code-agent escape hatch are offered.
- [ ] [t713_4] Open the TUI switcher and confirm key `y` launches/focuses syncer while `n` remains create-task.
- [ ] [t713_4] Enable `tmux.syncer.autostart: true`, run `ait ide`, and confirm a singleton syncer window starts in the project session.
- [ ] [t713_4] Confirm monitor and minimonitor show compact desync summaries without blocking refresh.
- [ ] [t713_5] Confirm all five helper-script whitelist touchpoints include `aitask_syncer.sh` and the syncer autostart config defaults false when omitted.
- [ ] [t713_6] Build or statically validate the website and confirm the dedicated Syncer TUI page is reachable from navigation and cross-linked from affected docs.
