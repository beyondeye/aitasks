---
Task: t597_5_remove_plot_flag_and_docs.md
Parent Task: aitasks/t597_ait_stats_tui.md
Sibling Tasks: aitasks/t597/t597_6_*.md
Archived Sibling Plans: aiplans/archived/p597/p597_1_*.md, p597_2_*.md, p597_3_*.md, p597_4_*.md
Worktree: (no worktree — current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-20 11:26
---

# Plan: t597_5 — Remove `ait stats --plot` + docs update

## Context

Siblings t597_1..t597_4 split stats data extraction into `.aitask-scripts/stats/stats_data.py` and shipped a Textual TUI launched via `ait stats-tui` (`.aitask-scripts/aitask_stats_tui.sh` → `.aitask-scripts/stats/stats_app.py`). User-confirmed cleanup: remove the `--plot` flag and its plotext rendering code entirely from `aitask_stats.py` (no alias, no redirect), and repoint user-facing docs at `ait stats-tui`. The `plotext` dependency stays — the TUI panes use it (`.aitask-scripts/stats/panes/base.py:52`).

README.md has no `ait stats` mentions (confirmed by grep) — no README edits needed.

## Ground-truth findings (from verification pass)

- All plot code is in `.aitask-scripts/aitask_stats.py` only; no callers in `.aitask-scripts/` or `tests/test_stats_data.sh`.
- **`tests/test_aitask_stats_py.py` DOES exercise `run_plot_summary` (test at line 291, invoked line 333) and `run_verified_plots` (test at line 542, invoked line 562).** These two tests must be deleted (their targets are going away).
- `tests/test_stats_data.sh:99-103` asserts `--help` still advertises `--plot` ("kept until t597_5"). Flip to assert `--plot` is absent.
- `build_chart_title` and `chart_totals` now live in `stats_data.py` and are imported by the TUI panes — must NOT be deleted.

## Implementation Plan

### 1. Delete plot code in `.aitask-scripts/aitask_stats.py`

Line numbers are from the current file (641 LOC total). Delete these ranges in order — deleting bottom-up keeps the earlier line numbers stable, so perform the deletions in reverse line order:

1. **Lines 631-634** — `if args.plot:` branch inside `main()`:
   ```python
   if args.plot:
       run_plot_summary(data, days=args.days, today=today, week_start_dow=week_start_dow)
       if vdata.operations:
           run_verified_plots(vdata)
   ```
2. **Lines 581-602** — `run_verified_plots()`
3. **Lines 501-579** — `run_plot_summary()`
4. **Lines 487-499** — `_import_plotext()`
5. **Lines 449-485** — `show_chart()`
6. **Lines 442-447** — `chart_plot_size()`
7. **Lines 147-151** — the `parser.add_argument("--plot", ...)` block in `parse_args()`

Also update the module docstring (lines 2-6) to drop the plotext mention:

Current:
```python
"""Calculate and display AI task completion statistics.

Supports text output, CSV export, and optional interactive terminal plots
(when plotext is installed). Pure data extraction lives in
`stats/stats_data.py` and is shared with the stats TUI.
"""
```

Replace with:
```python
"""Calculate and display AI task completion statistics.

Supports text output and CSV export. Pure data extraction lives in
`stats/stats_data.py` and is shared with the stats TUI (`ait stats-tui`).
"""
```

### 2. Prune now-unused imports in `aitask_stats.py`

After the deletions above, these become unused — remove them if grep confirms no remaining references:

- `import shutil` (line 15) — only used by `chart_plot_size()`
- `from datetime import date, datetime, timedelta` (line 22) — check remaining usages. `date`/`datetime` may still be used elsewhere; `timedelta` is only inside `run_plot_summary`. Narrow the import accordingly.
- `Tuple` from `typing` (line 24) — only used by `chart_plot_size` signature. Keep `List`/`Optional`/`Sequence`/`Dict` if still used; re-verify with a grep.

Re-verify with:
```bash
grep -n "shutil\.\|timedelta\|Tuple" .aitask-scripts/aitask_stats.py
```

### 3. Update `tests/test_aitask_stats_py.py`

Delete the two tests whose targets are going away:

- **Lines 291-360** — `test_run_plot_summary_uses_descriptive_titles` (and any surrounding blank-line padding within the class body).
- **Lines 542-567** — `test_verified_plots_chart_count`.

Leave the rest of the file untouched (the `_load_stats_module()` bootstrap, `TestWeekStart`, `TestArgParsing`, `TestFrontmatterParsing`, `TestCollection`, and other `TestVerifiedRankings` tests do not depend on plot code).

### 4. Update `tests/test_stats_data.sh`

Replace lines 99-103:

```bash
if ./.aitask-scripts/aitask_stats.sh --help 2>&1 | grep -q -- "--plot"; then
    assert_pass "ait stats --help still advertises --plot (kept until t597_5)"
else
    assert_fail "ait stats --help still advertises --plot (kept until t597_5)" "missing flag"
fi
```

With an inverted assertion:

```bash
if ./.aitask-scripts/aitask_stats.sh --help 2>&1 | grep -q -- "--plot"; then
    assert_fail "ait stats --help no longer advertises --plot" "flag still present"
else
    assert_pass "ait stats --help no longer advertises --plot"
fi
```

### 5. Update `.aitask-scripts/aitask_setup.sh`

Line 492-493 currently reads:
```bash
info "Optional dependency: stats graph support (plotext)"
printf "  Install plotext for 'ait stats --plot'? [y/N] "
```

Change to:
```bash
info "Optional dependency: stats TUI chart panes (plotext)"
printf "  Install plotext for 'ait stats-tui' chart panes? [y/N] "
```

(Dependency install logic stays — `plotext` is still installed when the user answers `y`.)

### 6. Update website docs (forward-only wording per memory `feedback_doc_forward_only`)

Edits are all within `website/content/docs/`. Do **not** touch `website/content/blog/v083-*.md`, `CHANGELOG.md`, or `CHANGELOG_HUMANIZED.md` — those are historical release notes.

**a) `website/content/docs/commands/board-stats.md`**

Edit the command block (lines 50-58): drop the `--plot` lines.

Before:
```
ait stats                  # Basic stats (last 7 days)
ait stats -d 14            # Extended daily view
ait stats -v               # Verbose with task IDs
ait stats --csv            # Export to CSV
ait stats --plot           # Render interactive terminal charts (requires optional plotext)
ait stats -d 30 --plot     # Charts over a longer date range
ait stats --csv out.csv --plot  # Export CSV and render charts in the same run
ait stats -w sun           # Week starts on Sunday
```

After:
```
ait stats                  # Basic stats (last 7 days)
ait stats -d 14            # Extended daily view
ait stats -v               # Verbose with task IDs
ait stats --csv            # Export to CSV
ait stats -w sun           # Week starts on Sunday
```

Edit the options table (line 67): remove the `--plot` row.

Replace the "Plot mode" section (lines 85-90):

Before:
```
**Plot mode (`--plot`):**

- Uses optional `plotext` to render interactive terminal charts.
- Adds code agent and LLM model histograms for both the last 4 weeks and this week, alongside the existing charts.
- If `plotext` is not installed, `ait stats` still runs and prints the normal text report, then shows a warning and skips chart rendering (no crash).
- Enable it via `ait setup` in the Python venv step when prompted: `Install plotext for 'ait stats --plot'? [y/N]`.
```

After:
```
**Interactive charts:**

For interactive terminal charts (daily completions, weekday averages, top labels, issue types, code agents, LLM models), use [`ait stats-tui`]({{< relref "/docs/tuis/stats" >}}). The TUI is launched directly or switched into from any other aitasks TUI (`j` in the TUI switcher). It uses the optional `plotext` package, installed via `ait setup` when prompted.
```

**b) `website/content/docs/installation/_index.md`**

Line 91 — replace:
```
- Python venv at `~/.aitask/venv/` with `textual` (>=8.1), `pyyaml`, `linkify-it-py`, `tomli` (plus optional `plotext` when enabled for `ait stats --plot`). Versions are pinned — see `ait setup` for details
```

With:
```
- Python venv at `~/.aitask/venv/` with `textual` (>=8.1), `pyyaml`, `linkify-it-py`, `tomli` (plus optional `plotext` when enabled for `ait stats-tui` chart panes). Versions are pinned — see `ait setup` for details
```

**c) `website/content/docs/commands/setup-install.md`**

Line 28 — replace `Install plotext for 'ait stats --plot'? [y/N]` with `Install plotext for 'ait stats-tui' chart panes? [y/N]`, and rewrite the explanatory sentence to reference the TUI instead of `--plot`:

Before (mid-sentence):
```
This is also where optional stats plot support is enabled: setup prompts `Install plotext for 'ait stats --plot'? [y/N]`. Choosing `y` installs `plotext`; choosing `N` keeps setup complete but leaves `ait stats --plot` in warning-only fallback mode (text stats still work).
```

After:
```
This is also where optional stats-TUI chart support is enabled: setup prompts `Install plotext for 'ait stats-tui' chart panes? [y/N]`. Choosing `y` installs `plotext`; choosing `N` keeps setup complete but leaves `ait stats-tui` running without the chart panes (text stats via `ait stats` still work).
```

Line 48 — replace:
```
To enable optional chart rendering for `ait stats --plot` later, re-run `ait setup` and answer `y` to the `plotext` prompt in the Python venv step.
```

With:
```
To enable optional chart rendering for `ait stats-tui` later, re-run `ait setup` and answer `y` to the `plotext` prompt in the Python venv step.
```

**d) `website/content/docs/skills/aitask-stats.md`**

Replace lines 32-35:

Before:
```
Supports all command-line options (`-d`, `-v`, `--csv`, `-w`, `--plot`).
`--plot` shows interactive terminal charts when optional `plotext` is installed
(can be enabled via `ait setup`), including the code agent and LLM model
histograms and verified score ranking bar charts per skill.
```

After:
```
Supports all command-line options (`-d`, `-v`, `--csv`, `-w`). For interactive
terminal charts (including code agent / LLM model histograms and verified score
ranking bar charts per skill), run `ait stats-tui` or switch into it from any
other aitasks TUI via the TUI switcher.
```

**e) `website/content/docs/skills/verified-scores.md`**

Line 57 — replace:
```
- **[`ait stats`]({{< relref "/docs/skills/aitask-stats" >}})** -- Prints verified model score rankings per skill with all-providers aggregation and time-windowed display. With `--plot`, renders bar charts per skill
```

With:
```
- **[`ait stats`]({{< relref "/docs/skills/aitask-stats" >}})** -- Prints verified model score rankings per skill with all-providers aggregation and time-windowed display
- **[`ait stats-tui`]({{< relref "/docs/tuis/stats" >}})** -- Renders verified score ranking bar charts per skill alongside the other stats panes
```

### 7. `README.md`

No action — README has no `ait stats` mentions (confirmed by grep).

### 8. New docs page: `website/content/docs/tuis/stats/_index.md`

Create a new page describing the stats TUI. Follow the same structural conventions as the neighbouring TUI index pages (minimonitor, settings): YAML frontmatter, "Launching" / "Purpose" / "Layout" / "Navigating" sections, and a `Next:` pointer.

Content outline (tuned to the actual implementation in `.aitask-scripts/stats/stats_app.py` and `stats_config.py`):

- **Frontmatter:** `title: "Stats"`, `linkTitle: "Stats"`, `weight: 35` (sits after Settings), `description: "Terminal UI for browsing archive completion statistics through configurable pane layouts"`.
- **Launching:** `ait stats-tui`; shared venv (`textual`, `pyyaml`); optional `plotext` installed via `ait setup`; note the switcher (`j`) entry point.
- **Purpose:** interactive, pane-based view of the same archived-task stats that `ait stats` prints as text, with chart panes that reuse the `stats/stats_data.py` module shared with `ait stats`.
- **Layout description** (prose mirroring the ASCII docstring in `stats_app.py`): left column is split into a pane sidebar on top and a layout picker below; right column is the currently-selected pane.
- **Built-in layouts (presets):** list the four presets from `DEFAULT_PRESETS` in `stats_config.py`:
  - `overview` — Summary, Daily completions, Weekday distribution
  - `labels` — Top labels, Issue types, Label × week
  - `agents` — Per agent (4w), Per model (4w), Verified rankings
  - `velocity` — Daily velocity, Rolling average, Parent vs child
- **Custom layouts:** `n` creates a new custom layout (name modal → pane selector), `e` edits a custom layout's pane list, `d` deletes the highlighted custom layout. Built-in presets are read-only.
- **Config persistence:** layered — project-level `aitasks/metadata/stats_config.json` is read-only at runtime (ships presets); user changes (active layout, custom layouts, days, week_start) are written to `aitasks/metadata/stats_config.local.json` (gitignored). Link to verified scores when relevant.
- **Keybindings table:**
  | Key | Action |
  |-----|--------|
  | **↑/↓** | Move highlight in the focused panel (sidebar highlights a pane, layout picker highlights a layout) |
  | **Enter** | Activate layout (on layout picker); sidebar activates on highlight, no Enter needed |
  | **Tab / Shift+Tab** | Switch focus between sidebar and layout picker |
  | **c** | Jump focus to the layout picker |
  | **n** | New custom layout (focus must be on layout picker) |
  | **e** | Edit highlighted custom layout |
  | **d** | Delete highlighted custom layout |
  | **r** | Refresh data from archive |
  | **j** | Open the TUI switcher |
  | **q** | Quit |
- **Next pointer:** link back to `../monitor/` or forward to `../settings/`, matching the weight ordering.

Do **not** add how-to / reference sub-pages — only the `_index.md`. Other TUIs (e.g. `minimonitor`) ship with just an `_index.md` + `how-to.md`; a single `_index.md` is sufficient for this task and follows the precedent.

### 9. Update `website/content/docs/tuis/_index.md`

Two edits:

**a)** Add a Stats entry to the "Available TUIs" bullet list (between Settings and Brainstorm, or immediately after Code Browser — place where weight makes sense; given `weight: 35` on the new page, insert after Settings at `weight: 30`):

```
- **[Stats](stats/)** (`ait stats-tui`) — Pane-based viewer for archived task completion statistics: summary, daily/weekly trends, label and issue-type breakdowns, code agent / LLM model histograms, and verified model score rankings. Swappable built-in layouts plus user-defined custom layouts.
```

**b)** Update the "Navigating between TUIs" paragraph (line 27) to list Stats among the core integrated TUIs in the switcher:

Before:
```
The switcher lists the core integrated TUIs (Monitor, Board, Code Browser, Settings) plus your configured git TUI, and appends any running code agent and brainstorm windows discovered in the tmux session.
```

After:
```
The switcher lists the core integrated TUIs (Monitor, Board, Code Browser, Settings, Stats) plus your configured git TUI, and appends any running code agent and brainstorm windows discovered in the tmux session.
```

Confirm via grep that Stats is registered in the switcher's `KNOWN_TUIS` (in `.aitask-scripts/lib/tui_switcher.py`) before making claim (b); if it is not registered yet, surface that as a blocker and drop claim (b) rather than making it aspirational.

## Verification

From the repo root:

```bash
# 1. Script smoke: text + csv still work; --plot is gone.
./.aitask-scripts/aitask_stats.sh >/dev/null && echo OK
CSV=$(mktemp "${TMPDIR:-/tmp}/t597_5_XXXXXX.csv"); ./.aitask-scripts/aitask_stats.sh --csv "$CSV" >/dev/null && head -1 "$CSV"; rm -f "$CSV"
./.aitask-scripts/aitask_stats.sh --plot 2>&1 | tail -3   # expect "unrecognized arguments: --plot" / usage
./.aitask-scripts/aitask_stats.sh --help | grep -v -- '--plot' >/dev/null && echo "no --plot in help"

# 2. TUI still launches.
ait stats-tui   # manual launch, Ctrl-C to exit

# 3. Tests pass.
bash tests/test_stats_data.sh
./.aitask/venv/bin/python tests/test_aitask_stats_py.py
#   — or whichever `python3` is on PATH if no venv
shellcheck .aitask-scripts/aitask_stats.sh .aitask-scripts/aitask_setup.sh

# 4. Regression: no orphan symbol references.
grep -rn "show_chart\|run_plot_summary\|_import_plotext\|run_verified_plots\|chart_plot_size" .aitask-scripts/ tests/   # empty
grep -rn "ait stats --plot\|'--plot'\|\"--plot\"" .aitask-scripts/ tests/ website/content/docs/ README.md   # empty

# 5. plotext dependency retained for TUI.
grep -n "plotext" .aitask-scripts/stats/panes/base.py .aitask-scripts/aitask_stats_tui.sh   # still there

# 6. Website builds.
cd website && hugo build --gc --minify 2>&1 | tail -20; cd -
# Expect: build completes; no broken `relref` for /docs/tuis/stats or /docs/skills/aitask-stats.
```

## Out of Scope

- Manual end-to-end TUI walkthrough — covered by sibling t597_6.
- `how-to.md` or `reference.md` sub-pages under `website/content/docs/tuis/stats/` — only `_index.md` is created; deeper guides can be added later if needed.
- Blog post `website/content/blog/v083-*.md` and `CHANGELOG*.md` — historical release notes, intentionally unchanged.
