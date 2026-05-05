---
Task: t755_stats_tui_crashing.md
Base branch: main
plan_verified: []
---

# t755 — Stats TUI crashes immediately on launch

## Context

Launching the stats TUI (`ait stats-tui`, or `t` from the TUI switcher) crashes
with:

```
Missing Python packages: plotext. Run 'ait setup' to install all dependencies.
```

### Root cause

Commit `c3f0bb2d` (t718_2) wired `aitask_stats_tui.sh` to
`require_ait_python_fast`, which auto-routes to `~/.aitask/pypy_venv` when
PyPy is installed. The PyPy venv is set up by `setup_pypy_venv()` in
`aitask_setup.sh` with only the base TUI deps (`textual`, `pyyaml`,
`linkify-it-py`, `tomli`); `plotext` is installed only in the CPython venv
(line 663-668), gated behind a TTY prompt. So with both `--with-pypy` and a
"yes" on the plotext prompt, plotext lives in CPython but is missing from
PyPy → stats TUI dies on the line-17 dep check.

### Fix direction (per user)

Stats TUI does not need PyPy. Revert just `aitask_stats_tui.sh` to
`require_ait_python` (CPython). Stats TUI joins the existing exceptions
(`monitor`, `minimonitor`, `diffviewer`) that intentionally stay on CPython.

This is a smaller and more self-contained fix than mirroring plotext into the
PyPy venv, and avoids carrying an extra dep across two venvs for a TUI whose
runtime profile (browse, glance, exit) doesn't benefit much from PyPy warmup.

## Changes

### 1. `.aitask-scripts/aitask_stats_tui.sh` (line 12)

```bash
PYTHON="$(require_ait_python_fast)"
```
→
```bash
PYTHON="$(require_ait_python)"
```

### 2. `CLAUDE.md` (lines 168 and 170)

- Line 168 ("Monitor / minimonitor are exceptions today …"): add stats TUI to
  the exceptions list with a one-line reason ("plotext is CPython-only;
  stats TUI's interaction profile doesn't justify mirroring it into PyPy").
- Line 170 ("the six fast-path TUIs (board, codebrowser, settings,
  stats-tui, brainstorm, syncer) auto-route through ~/.aitask/pypy_venv"):
  drop `stats-tui` from the list → "five fast-path TUIs (board,
  codebrowser, settings, brainstorm, syncer)".

### 3. `aidocs/python_tui_performance.md` (line 109)

Internal reference doc. Update the TUI launchers row of the table:
- Drop `aitask_stats_tui.sh` from the `require_ait_python_fast` enumeration.
- Add `aitask_stats_tui.sh` to the "stay on CPython" enumeration alongside
  `aitask_monitor.sh`, `aitask_minimonitor.sh`, with a brief parenthetical
  reason (plotext dep + interaction profile).

### 4. `.aitask-scripts/aitask_setup.sh` (line 584)

The interactive PyPy install prompt currently advertises:
```
Optional: PyPy 3.11 for faster TUIs (board, codebrowser, settings, stats, brainstorm).
```
Drop `stats` from that list to avoid promising a speedup that no longer
applies.

### 5. User-facing website docs (current-state edits, no history)

Per the project's "user-facing docs describe the **current state only**" rule,
remove stats from the PyPy fast-path lists without any "previously" framing.

- `website/content/docs/installation/pypy.md`:
  - Line 13: drop `stats-tui` from the "settings / stats-tui / brainstorm /
    syncer TUIs feel snappier under" sentence.
  - Line 32: "Once installed, the six fast-path TUIs auto-route through
    PyPy:" → "Once installed, the five fast-path TUIs auto-route through
    PyPy:".
  - Lines 38-44 table: remove the `Stats | ait stats-tui` row.

No other website docs (e.g. `docs/tuis/stats/_index.md`,
`docs/commands/board-stats.md`, `docs/skills/aitask-stats.md`) reference the
PyPy fast-path enumeration — they only describe stats TUI behavior and the
plotext optional install, which remain unchanged.

## Out of scope (per user direction)

- Mirroring plotext into the PyPy venv (`setup_pypy_venv()`). Not needed
  once stats TUI no longer routes to PyPy.
- Centralizing the `'plotext==5.3.2'` literal. There is still only one
  install site after this fix; no extraction needed.
- Re-evaluating the PyPy speedup claim for the remaining five TUIs. Out of
  scope for this bug fix.

## Verification

1. **Code check after edit:**
   ```
   grep -n require_ait_python .aitask-scripts/aitask_stats_tui.sh
   ```
   Expect: `PYTHON="$(require_ait_python)"` (no `_fast`).

2. **Resolved interpreter:**
   ```
   bash -c 'source .aitask-scripts/lib/python_resolve.sh; require_ait_python'
   ```
   Expect: `/home/ddt/.aitask/venv/bin/python` (CPython, where plotext lives).

3. **Launch stats TUI** from a tmux pane in the aitasks session:
   ```
   ./.aitask-scripts/aitask_stats_tui.sh
   ```
   Expect: TUI renders without "Missing Python packages: plotext".

4. **TUI switcher:** press `t` from any aitasks TUI; stats TUI should launch
   cleanly.

## Step 9 (Post-Implementation)

Standard archival via `aitask_archive.sh 755`. Commit message follows
`bug: <description> (t755)`.
