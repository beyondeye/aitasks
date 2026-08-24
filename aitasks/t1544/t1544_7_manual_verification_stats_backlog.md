---
priority: medium
effort: medium
depends: [t1544_6]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [t1544_1, t1544_4, t1544_5, t1544_6]
assigned_to: dario-e@beyond-eye.com
anchor: 1544
followup_kind: manual_verification
created_at: 2026-08-17 22:08
updated_at: 2026-08-24 23:06
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1544_1] **List A (no-flag).** Launch `ait monitor`, then `ait minimonitor`, and confirm each session list is **byte-identical** to the List A baseline in t1544_1's Final Implementation Notes. These use no-flag discovery, which the dedupe deliberately does not touch, so the bar is "unchanged" and *any* difference is a regression — including a duplicate live session disappearing, which must still be listed twice here.
- [ ] [t1544_1] **List B (registry-inclusive).** Press `j` in any TUI (board, monitor or minimonitor — all three render the same switcher overlay) and confirm the list matches the **predicted after-list** in t1544_1's Final Implementation Notes. A row vanishing whose key was NOT in the recorded duplicate-key set is a regression. Note `ait board` has no session list of its own; its `j` overlay is this same list, so do not check it as a separate surface.
- [ ] [t1544_1] With two live tmux sessions rooted at the same repo, confirm the stats TUI shows that repo once and its totals are NOT doubled
- [ ] [t1544_1] With two live tmux sessions rooted at the same repo, open the `j` switcher and confirm left/right cycling still reaches **every other repo** (before the dedupe the cycle ring was trapped inside the duplicated pair and no other repo was reachable)
- [ ] [t1544_4] Run `ait stats` and confirm both new sections render — backlog level and net flow — each split by the category axis
- [ ] [t1544_4] Confirm the backlog table fits in an 80-column terminal at the default horizon, and that the follow-up rows (lowercase names) read as visually distinct from the issue-type rows (Title Case)
- [ ] [t1544_4] Confirm the `-- follow-ups`, `-- genuine` and `TOTAL OPEN` rows are present, and that TOTAL OPEN carries the (parents / children) split
- [ ] [t1544_4] Confirm the `Now` column is labelled as a partial week, and that the excluded-task tally, the gross-vs-net `bug` footnote, and the two-clocks footnote all appear
- [ ] [t1544_4] Run `ait stats --backlog-weeks 26` and confirm the longer horizon renders and the numbers are consistent with the default run
- [ ] [t1544_4] Run `ait stats --csv /tmp/t.csv --csv-backlog /tmp/b.csv`; confirm the per-task CSV has 12 columns with the original 10 unmoved, and that the backlog CSV carries week_ending/category/open/arrived/departed/net
- [ ] [t1544_4] Eyeball `ait stats` against a pre-change capture and confirm every pre-existing section is unchanged apart from the `Generated:` line
- [ ] [t1544_4] In a scratch project with open tasks and an empty archive, confirm `ait stats` renders the backlog section instead of "No completed tasks found."
- [ ] [t1544_5] Launch `ait stats-tui` and confirm the app starts at all (a pane module missing from the eager import list is a ModuleNotFoundError that kills the TUI)
- [ ] [t1544_5] Select the `backlog` layout in the layout picker and confirm both panes appear in the sidebar
- [ ] [t1544_5] View `backlog.level` and confirm it renders real data rather than its empty state, is readable at a normal terminal width, and that the row cap / Other bucket engages on the real corpus
- [ ] [t1544_5] View `backlog.netflow` and confirm it visibly carries the category dimension — not just arrivals-vs-departures totals
- [ ] [t1544_5] Confirm the other five presets still list their original panes and still render
- [ ] [t1544_5] Cross-check the TUI backlog numbers against `ait stats` for the same week and confirm both surfaces show the same horizon and the same values
- [ ] [t1544_6] Build the website (`cd website && hugo build --gc --minify`) and confirm it succeeds with no broken relref links
- [ ] [t1544_6] Read the rendered stats pages and confirm the preset count, the CSV column list, and the completion-clock description all match live `ait stats` output rather than the plan
