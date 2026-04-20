---
priority: medium
effort: low
depends: [t597_4]
issue_type: chore
status: Implementing
labels: [statistics, aitask_monitor]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-19 17:52
updated_at: 2026-04-20 11:00
---

## Context

Fifth child of t597. Cleans up the now-redundant `--plot` flag from `aitask_stats.py` (the new TUI replaces it) and updates user-facing docs to describe the TUI as the interactive view.

User-confirmed decision: REMOVE `--plot` entirely. No alias, no redirect to the TUI. Users invoke the TUI via `ait stats-tui` or via the tmux switcher (`j` from any other TUI).

## Key Files to Modify

- `.aitask-scripts/aitask_stats.py` — remove `--plot` argparse entry, handler, `show_chart()`, `run_plot_summary()`, `_import_plotext()`, and any plotext-only helpers.
- `README.md` — describe `ait stats-tui` as the interactive view (replace any mention of `ait stats --plot`).
- Any `website/content/**/stats*.md` (or sibling pages) — same forward-only edit.

## Reference Files for Patterns

- Sibling `aiplans/p597/p597_1_*.md` (stats data extraction was already moved to `stats/stats_data.py` in t597_1 — only chart rendering remains in `aitask_stats.py` to delete).
- Memory `feedback_doc_forward_only`: docs describe current state only — no "previously --plot did X" wording. Only mention `ait stats-tui` and the switcher.

## Implementation Plan

1. **Audit imports/callers** of `show_chart`, `run_plot_summary`, `_import_plotext`:
   ```bash
   grep -rn "show_chart\|run_plot_summary\|_import_plotext" .aitask-scripts/ tests/
   ```
   Confirm only `aitask_stats.py` itself uses them.
2. **Remove from `aitask_stats.py`**:
   - The `--plot` argument in argparse
   - The `args.plot` branch in `main()`
   - `show_chart()`, `run_plot_summary()`, `_import_plotext()` and any helper used only by them
3. **plotext dependency mention**: if `aitask_stats.py` had a header/usage comment mentioning plotext as optional, update to point users to `ait stats-tui` for chart views. The TUI panes (t597_3) keep `plotext` as a runtime dep — do not remove it from any setup/install script.
4. **README**: locate any "Statistics" section. Replace `ait stats --plot` references with `ait stats-tui`. If no section exists, leave README alone.
5. **website/content**: locate `stats*.md` if any (search via `grep -rl "ait stats" website/content/`). Update interactive-view references the same way.
6. **Run tests**:
   ```bash
   bash tests/test_stats_data.sh
   ./.aitask-scripts/aitask_stats.sh                 # text report works
   ./.aitask-scripts/aitask_stats.sh --csv /tmp/x.csv # csv works
   ./.aitask-scripts/aitask_stats.sh --plot 2>&1 | grep -q "unrecognized arguments\|invalid choice\|usage"  # confirms removal
   ```

## Verification Steps

```bash
ait stats                                  # works
ait stats --csv /tmp/out.csv               # works
ait stats --plot                           # argparse error (flag removed)
ait stats-tui                              # TUI launches
shellcheck .aitask-scripts/aitask_stats.sh
```

## Out of Scope

- Manual end-to-end TUI walkthrough (t597_6).
