---
priority: low
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [tui, documentation]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8_1m
created_at: 2026-06-10 12:00
updated_at: 2026-06-10 12:06
completed_at: 2026-06-10 12:06
---

## Problem

`ait stats-tui` is a fully-fledged TUI (dispatched at `ait` line 195 →
`aitask_stats_tui.sh` → `stats/stats_app.py`, registered in
`.aitask-scripts/lib/tui_registry.py:22` as `("stats", "Statistics", "ait
stats-tui", True)` so it shows in the `j` TUI switcher), but it is **missing
from the TUI section of `ait` help text**.

The help text TUI section (`ait` lines 28-37, hardcoded in `show_usage()`)
lists `applink, board, codebrowser, diffviewer, ide, minimonitor, monitor,
settings, syncer` — but not `stats-tui`. Only the non-TUI CLI reporter `ait
stats` appears, under the **Reporting** section (line 54).

## Root cause

The help text is a hand-maintained hardcoded list with no link to the TUI
registry, so it drifted: `stats-tui` was added to `tui_registry.py` and the
dispatcher but never added to the help TUI section. (Note `ide` is listed as a
TUI in help but is really a tmux/monitor launcher — the section is loosely
curated.)

## Proposed fix

1. Add a `stats-tui` line to the TUI section of `show_usage()` in `ait`,
   e.g. `stats-tui      Launch the statistics TUI`.
2. Reconcile the help TUI section against `.aitask-scripts/lib/tui_registry.py`
   so the two don't drift again. Consider whether the help TUI list should be
   generated from (or at least audited against) `TUI_REGISTRY` /
   `switcher_tuis()` rather than maintained by hand.

## Notes / scope considerations

- Respect the project rule that `diffviewer` is transitional and intentionally
  omitted from *user-facing website docs / lists-of-TUIs* — but it currently
  IS listed in `ait` help; decide whether the help text (a CLI surface, not
  website docs) should keep it.
- `brainstorm` and `minimonitor` are registry entries with `in_switcher=False`;
  factor that into any auto-generation approach.

## Key files

- `ait` (repo root) lines 28-37 (help TUI section), 54 (Reporting), 194-195
  (dispatch)
- `.aitask-scripts/lib/tui_registry.py` lines 17-41 (TUI_REGISTRY, switcher_tuis)
- `.aitask-scripts/lib/tui_switcher.py:142` (KNOWN_TUIS = switcher_tuis())
