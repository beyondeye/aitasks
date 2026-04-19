---
Task: t597_6_manual_verification.md
Parent Task: aitasks/t597_ait_stats_tui.md
Sibling Tasks: aitasks/t597/t597_1_*.md, aitasks/t597/t597_2_*.md, aitasks/t597/t597_3_*.md, aitasks/t597/t597_4_*.md, aitasks/t597/t597_5_*.md
Archived Sibling Plans: aiplans/archived/p597/p597_*_*.md
Worktree: (no worktree — current branch)
Branch: main
Base branch: main
---

# Plan: t597_6 — Manual verification

## Context

Aggregate manual-verification task for t597 (`ait stats` TUI). Per memory `feedback_manual_verification_aggregate`, parents with 2+ TUI-touching siblings get one consolidated verification task instead of inline verification sections in each sibling.

`issue_type: manual_verification`. The `aitask-pick` workflow routes manual-verification tasks through `manual-verification.md` (Step 3 Check 3) — an interactive checklist runner.

## Verification Checklist

### Setup
- [ ] Confirm latest main has all of t597_1 through t597_5 archived
- [ ] Confirm `aitasks/metadata/stats_config.json` exists and is git-tracked
- [ ] Confirm `aitasks/metadata/stats_config.local.json` is gitignored

### Launch & layout
- [ ] `ait stats-tui` launches without exception
- [ ] Sidebar visible on the left, content area on the right
- [ ] Sidebar populated from active preset (default: Overview, 3 panes)
- [ ] First pane auto-selected on launch

### Navigation
- [ ] `↑` / `↓` selects panes; right-side content swaps to corresponding chart/table
- [ ] Selection wraps or clamps at top/bottom (whichever was implemented)
- [ ] No `n` key binding active (per user)

### Refresh
- [ ] In another tmux window: pick a Ready task, archive it
- [ ] Return to stats TUI, press `r`
- [ ] Counts in current pane update (e.g., total task count, today's count)

### Config modal
- [ ] `c` opens modal
- [ ] All four presets listed (Overview, Labels, Agents, Velocity) and selectable
- [ ] Switching preset → Apply → sidebar updates immediately
- [ ] `+ New custom` → prompts for name → multi-select pane chooser → Save
- [ ] Custom layout appears in sidebar
- [ ] Custom layout deletable (left list `d` or Delete button)
- [ ] Quitting and relaunching `ait stats-tui` restores the active layout (persistence works)

### TUI switcher
- [ ] `j` opens switcher overlay; `Statistics` listed with shortcut letter
- [ ] Switching to `board`, `monitor`, `codebrowser`, `settings` and back to `stats` works
- [ ] Reverse: from each other TUI, `j` shows `Statistics` and switches into it

### Pane category coverage
- [ ] **Overview**: summary cards, daily line chart, weekday bar chart all render
- [ ] **Labels**: top labels bar, issue type bar, label×week heatmap all render
- [ ] **Agents**: per-agent bar, per-model bar, verified rankings table all render
- [ ] **Velocity**: daily line, rolling-avg overlay, parent-vs-child stacked bar all render
- [ ] No exceptions for any of the 12 panes on the current production dataset
- [ ] Empty-state: in a sandbox repo with no archived tasks, panes show "No data" placeholders rather than crash

### CLI parity
- [ ] `ait stats` text report unchanged (compare against pre-t597 output if a snapshot exists)
- [ ] `ait stats --csv /tmp/out.csv` produces the same CSV format as before
- [ ] `ait stats --plot` returns argparse error (`unrecognized arguments: --plot`)
- [ ] `ait stats --help` no longer mentions `--plot`

### Persistence file hygiene
- [ ] `aitasks/metadata/stats_config.json` git-tracked, contains 4 presets only (no user state)
- [ ] `aitasks/metadata/stats_config.local.json` git-ignored (`git status` doesn't list it after editing in the TUI)

### Docs
- [ ] README mentions `ait stats-tui`, no longer mentions `--plot`
- [ ] Website pages (if any) reference the TUI as the interactive view

## Failure Mode

If any item fails: file a follow-up child task `t597_7_*` (or `t597_8_*` etc.) describing the failure and wire dependencies. Do NOT modify already-archived child tasks.

## Reference

- Parent plan: `aiplans/p597_ait_stats_tui.md` (or its archived counterpart by the time this runs)
- Sibling plans: `aiplans/p597/p597_*.md` (or archived `aiplans/archived/p597/`)
