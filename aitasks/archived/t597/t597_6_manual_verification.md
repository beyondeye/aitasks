---
priority: medium
effort: low
depends: [t597_5]
issue_type: manual_verification
status: Done
labels: [statistics, aitask_monitor]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-19 17:53
updated_at: 2026-04-21 08:01
completed_at: 2026-04-21 08:01
---

## Context

Sixth and final child of t597. Aggregate manual-verification task per memory `feedback_manual_verification_aggregate` (parent has 4 TUI-touching siblings). Runs after t597_5 lands; verifies the full feature end-to-end in a real terminal/tmux session.

> **Note:** This task should have `issue_type: manual_verification` once that's a supported value. Created here as `chore` if `manual_verification` is not yet in `aitasks/metadata/task_types.txt` — verify and update via `aitask_update.sh --batch t597_6 --type manual_verification` if available.

## Verification Checklist

Launch in a fresh tmux session (or current one):

- [x] `ait stats-tui` launches without exception; sidebar visible on the left, content area on the right. — PASS 2026-04-20 16:20
- [x] Sidebar shows the panes from the active preset (default: Overview). — PASS 2026-04-20 16:21
- [x] `↑` / `↓` selects panes; right-side content swaps to the corresponding chart/table. — PASS 2026-04-20 16:21
- [x] `r` refreshes (modify a task and archive it via `ait board` in another window, return, press `r` — PASS 2026-04-20 16:21
- [x] `c` opens config modal: — PASS 2026-04-20 16:21
  - [x] All four presets are listed and selectable — PASS 2026-04-20 16:22
  - [defer] Switching preset updates the sidebar immediately — DEFER 2026-04-21 07:42
  - [skip] "+ New custom" → name input → multi-select → save → custom appears in the list and in the sidebar — SKIP 2026-04-21 07:43 Cannot verify right now
  - [defer] Quitting and relaunching `ait stats-tui` restores the active layout (persistence works) — DEFER 2026-04-21 07:43
- [x] `j` opens TUI switcher overlay; switching to `board`, `monitor`, `codebrowser` and back to `stats` works. — PASS 2026-04-21 07:43
- [x] `q` quits cleanly. — PASS 2026-04-21 07:43
- [x] All 4 preset categories render without exceptions on the current dataset: — PASS 2026-04-21 07:43
  - [x] Overview (summary, daily, weekday) — PASS 2026-04-21 07:44
  - [x] Labels & Issue Types (top, issue types, heatmap) — PASS 2026-04-21 07:46
  - [fail] Agents & Models (per-agent, per-model, verified rankings) — FAIL 2026-04-21 07:48 follow-up t603
  - [x] Velocity (daily, rolling, parent vs child) — PASS 2026-04-21 07:49
- [defer] CLI parity: — DEFER 2026-04-21 07:50
  - [x] `ait stats` text report unchanged — PASS 2026-04-21 07:50
  - [x] `ait stats --csv /tmp/out.csv` produces the same CSV as before — PASS 2026-04-21 07:50
  - [x] `ait stats --plot` returns argparse error (flag removed) — PASS 2026-04-21 07:51
- [skip] Persistence file hygiene: — SKIP 2026-04-21 07:53 Section header. Follow-up: see t604 — skip section headers in manual verification
  - [x] `aitasks/metadata/stats_config.json` is git-tracked, contains 4 presets — PASS 2026-04-21 07:54
  - [x] `aitasks/metadata/stats_config.local.json` is git-ignored (`git status` doesn't list it after editing) — PASS 2026-04-21 07:54
- [x] tmux switcher entry: `ait stats-tui` appears in the switcher list with shortcut letter (if assigned in t597_2). — PASS 2026-04-21 07:56

## Reference Files

- `aiplans/p597_ait_stats_tui.md` (parent plan) for the design intent.
- Sibling plan files in `aiplans/p597/` for per-task implementation details.

## Failure Mode

If any item fails, file a follow-up child task (e.g., `t597_7_*`) describing the failure and wire dependencies appropriately. Do NOT modify previous archived tasks.
