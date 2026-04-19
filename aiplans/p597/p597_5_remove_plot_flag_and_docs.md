---
Task: t597_5_remove_plot_flag_and_docs.md
Parent Task: aitasks/t597_ait_stats_tui.md
Sibling Tasks: aitasks/t597/t597_1_*.md, aitasks/t597/t597_2_*.md, aitasks/t597/t597_3_*.md, aitasks/t597/t597_4_*.md, aitasks/t597/t597_6_*.md
Archived Sibling Plans: aiplans/archived/p597/p597_*_*.md
Worktree: (no worktree — current branch)
Branch: main
Base branch: main
---

# Plan: t597_5 — Remove `ait stats --plot` + docs update

## Context

User-confirmed cleanup: the new TUI is the only interactive view. The `--plot` flag and its plotext rendering code are removed entirely from `aitask_stats.py` (no alias, no redirect). User-facing docs are updated to point at `ait stats-tui`.

The data extraction was already moved to `stats/stats_data.py` in t597_1; only chart-rendering code remains in `aitask_stats.py` to delete.

## Implementation Plan

### 1. Audit callers

```bash
grep -rn "show_chart\|run_plot_summary\|_import_plotext\|--plot" .aitask-scripts/ tests/ website/ README.md
```

Confirm:
- `show_chart`, `run_plot_summary`, `_import_plotext` are referenced **only** within `aitask_stats.py`.
- `--plot` is referenced in `aitask_stats.py` argparse + maybe README/website.

If any test or external script depends on `--plot`, surface it as a follow-up child task before deleting.

### 2. Delete from `aitask_stats.py`

- The `--plot` argparse argument
- The `if args.plot:` branch in `main()`
- Function defs: `show_chart()`, `run_plot_summary()`, `_import_plotext()`
- Any helper that becomes unused after the above (e.g., chart-title/axis builders **only** used by plot rendering — be careful, some are reused by tests or moved to `stats_data.py` already; verify with grep before deleting)
- Any `import plotext` at module level (unlikely — should be lazy)

### 3. Update header / docstring / usage

If `aitask_stats.py` has a top-of-file usage comment or `--help` epilog mentioning `--plot`, replace with a note that interactive charts are available via `ait stats-tui`.

### 4. README

```bash
grep -n "ait stats\|--plot" README.md
```

For any line mentioning `ait stats --plot`, replace with `ait stats-tui`. Per memory `feedback_doc_forward_only`, write present-tense only — do NOT add "previously this was --plot" wording.

### 5. Website docs

```bash
grep -rln "ait stats\|--plot" website/content/
```

Update each match the same way. If a page has a screenshot of the old plot output, replace with a TUI screenshot or remove the image (defer screenshot capture to t597_6 if needed).

### 6. plotext dependency mention

If any setup script (`seed/`, install docs) lists `plotext` as a dep for `--plot`, update the rationale to "required by `ait stats-tui` for chart rendering". Don't remove the dep — TUI panes (t597_3) need it.

## Verification

```bash
./.aitask-scripts/aitask_stats.sh                 # text report works
./.aitask-scripts/aitask_stats.sh --csv /tmp/x.csv && head /tmp/x.csv
./.aitask-scripts/aitask_stats.sh --plot 2>&1 | tail -3   # argparse error: "unrecognized arguments: --plot"
ait stats-tui                                     # TUI launches
shellcheck .aitask-scripts/aitask_stats.sh
bash tests/test_stats_data.sh                     # still PASS

# Regression: no orphan symbol references
grep -rn "show_chart\|run_plot_summary\|_import_plotext" .aitask-scripts/ tests/   # empty
grep -rn "stats --plot\|ait stats --plot" .                                         # empty (or only git-history files)
```

## Out of Scope

- Manual end-to-end TUI walkthrough (t597_6).
