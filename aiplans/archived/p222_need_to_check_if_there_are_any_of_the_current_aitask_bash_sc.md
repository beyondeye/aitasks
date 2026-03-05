---
Task: t222_need_to_check_if_there_are_any_of_the_current_aitask_bash_sc.md
Worktree: (none — working on current branch)
Branch: (none — working on current branch)
Base branch: main
---

# Plan: Audit Bash Scripts and Migrate `aitask_stats` to Python (t222)

## Summary

- Audit existing `aiscripts/*.sh` commands for rewrite opportunities and prioritize by measurable runtime impact.
- Migrate `aitask_stats` from Bash to Python for performance and maintainability while preserving command compatibility.
- Add optional interactive terminal plotting via `--plot` using `plotext`.
- Keep the legacy Bash implementation available as `aiscripts/aitask_stats_legacy.sh` for comparison and rollback confidence.
- Create follow-up task `t305` for board-triggered stats plotting integration.

## Implementation Changes

- Replaced monolithic Bash implementation with a Python engine:
  - `aiscripts/aitask_stats.py` (parsing, aggregation, text report, CSV export, optional plotting)
  - `aiscripts/aitask_stats.sh` converted to thin Python launcher wrapper
- Added optional plot mode:
  - New flag: `--plot`
  - Graceful fallback warning when `plotext` is unavailable
  - Fixed plotext date parsing issue by using categorical numeric x-axis for daily line chart
- Added forgiving CLI parsing for accidental trailing dot in days argument:
  - `-d 7.` accepted and normalized to `7`
- Preserved legacy script for parity checks:
  - `aiscripts/aitask_stats_legacy.sh`
- Updated setup flow to optionally install plotting dependency:
  - `aiscripts/aitask_setup.sh` now prompts whether to install `plotext` in shared `~/.aitask/venv`
- Updated docs for stats plotting and setup behavior:
  - `website/content/docs/commands/board-stats.md`
  - `website/content/docs/skills/aitask-stats.md`
  - `website/content/docs/commands/setup-install.md`
  - `website/content/docs/installation/_index.md`
- Added Python tests:
  - `tests/test_aitask_stats_py.py`

## Validation

- Functional tests:
  - `python3 -m unittest tests/test_aitask_stats_py.py -v` (passes)
  - `./aiscripts/aitask_stats.sh -d 3 --csv /tmp/ait_stats_test.csv` (text + CSV)
  - `./aiscripts/aitask_stats.sh --plot -d 7.` (plot mode + tolerant days parsing)
- Legacy parity checks:
  - Compared `aiscripts/aitask_stats_legacy.sh` vs Python output and CSV on same data set.
  - Summary totals and row counts match; minor differences remain in rounding/order/CSV quoting style.
- Performance benchmark:
  - Legacy: ~11.464s
  - Python: ~0.053s

## Final Implementation Notes

- **Actual work done:** Completed Bash-to-Python migration for stats, added optional interactive plotting and setup integration, updated docs/tests, and created follow-up board integration task (`t305`).
- **Deviations from plan:** Kept output semantically compatible rather than byte-for-byte identical; accepted minor rounding/order/quoting differences due to Python implementation.
- **Issues encountered:**
  - `plotext` treated `MM-DD` labels as dates and crashed. Resolved by plotting numeric x-values with explicit tick labels.
  - User input `-d 7.` caused argparse int parsing failure. Resolved with tolerant parser.
- **Key decisions:**
  - Keep legacy script side-by-side for temporary verification.
  - Make `plotext` optional dependency controlled via `ait setup` prompt.
- **Build verification:** No dedicated build step configured for this command-only change set.

## Post-Implementation

Follow Step 9 archival workflow for `t222` via `./aiscripts/aitask_archive.sh 222` and push task-data changes.
