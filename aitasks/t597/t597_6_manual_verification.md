---
priority: medium
effort: low
depends: [t597_5]
issue_type: manual_verification
status: Implementing
labels: [statistics, aitask_monitor]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-19 17:53
updated_at: 2026-04-20 14:49
---

## Context

Sixth and final child of t597. Aggregate manual-verification task per memory `feedback_manual_verification_aggregate` (parent has 4 TUI-touching siblings). Runs after t597_5 lands; verifies the full feature end-to-end in a real terminal/tmux session.

> **Note:** This task should have `issue_type: manual_verification` once that's a supported value. Created here as `chore` if `manual_verification` is not yet in `aitasks/metadata/task_types.txt` — verify and update via `aitask_update.sh --batch t597_6 --type manual_verification` if available.

## Verification Checklist

Launch in a fresh tmux session (or current one):

- [ ] `ait stats-tui` launches without exception; sidebar visible on the left, content area on the right.
- [ ] Sidebar shows the panes from the active preset (default: Overview).
- [ ] `↑` / `↓` selects panes; right-side content swaps to the corresponding chart/table.
- [ ] `r` refreshes (modify a task and archive it via `ait board` in another window, return, press `r` — counts update).
- [ ] `c` opens config modal:
  - [ ] All four presets are listed and selectable
  - [ ] Switching preset updates the sidebar immediately
  - [ ] "+ New custom" → name input → multi-select → save → custom appears in the list and in the sidebar
  - [ ] Quitting and relaunching `ait stats-tui` restores the active layout (persistence works)
- [ ] `j` opens TUI switcher overlay; switching to `board`, `monitor`, `codebrowser` and back to `stats` works.
- [ ] `q` quits cleanly.
- [ ] All 4 preset categories render without exceptions on the current dataset:
  - [ ] Overview (summary, daily, weekday)
  - [ ] Labels & Issue Types (top, issue types, heatmap)
  - [ ] Agents & Models (per-agent, per-model, verified rankings)
  - [ ] Velocity (daily, rolling, parent vs child)
- [ ] CLI parity:
  - [ ] `ait stats` text report unchanged
  - [ ] `ait stats --csv /tmp/out.csv` produces the same CSV as before
  - [ ] `ait stats --plot` returns argparse error (flag removed)
- [ ] Persistence file hygiene:
  - [ ] `aitasks/metadata/stats_config.json` is git-tracked, contains 4 presets
  - [ ] `aitasks/metadata/stats_config.local.json` is git-ignored (`git status` doesn't list it after editing)
- [ ] tmux switcher entry: `ait stats-tui` appears in the switcher list with shortcut letter (if assigned in t597_2).

## Reference Files

- `aiplans/p597_ait_stats_tui.md` (parent plan) for the design intent.
- Sibling plan files in `aiplans/p597/` for per-task implementation details.

## Failure Mode

If any item fails, file a follow-up child task (e.g., `t597_7_*`) describing the failure and wire dependencies appropriately. Do NOT modify previous archived tasks.
