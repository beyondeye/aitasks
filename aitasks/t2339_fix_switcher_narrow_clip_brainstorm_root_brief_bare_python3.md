---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [tui, screenshots]
gates: [risk_evaluated]
anchor: 2278
followup_kind: upstream_defect
created_at: 2026-11-20 01:36
updated_at: 2026-11-20 01:36
---

## Origin

Spawned from t2278_5 during Step 8b review. All three were found while driving
the real TUIs on a sample project for the docs screenshots.

## Upstream defect

- `.aitask-scripts/lib/tui_switcher.py:556 — the switcher dialog has a fixed width of 44, so in the 40-column minimonitor pane its right border and the ends of the hint rows ("(S)etting", "(G)i") are clipped`
- `.aitask-scripts/brainstorm/brainstorm_session.py:154-157 — init builds the root node's description and the session brief from the first lines of the whole task file, frontmatter included, so they read "priority: medium | effort: medium"`
- `.aitask-scripts/lib/launch_modes_sh.sh:24 — falls back to a bare python3 from PATH and ignores AIT_PYTHON, so aitask_crew_init.sh fails under any HOME without ~/.aitask/venv even when AIT_PYTHON is set`

## Diagnostic context

- **Switcher clip.** Opening the TUI switcher (`j`) from a minimonitor in its
  usual 40-column split draws a dialog wider than the pane. The switcher has a
  `narrow` mode (`_switcher_narrow()` is True for minimonitor), but the dialog
  CSS width stays 44. Visible in
  `website/static/imgs/aitasks_tui_switcher_from_minimonitor.svg` and
  reproducible with `website/screenshots.sh replay --scene
  tui_switcher_from_minimonitor --png`. Once fixed, that recipe's image should
  be regenerated (the `/aitask-docs-screenshots` repair loop does it).
- **Brainstorm root brief.** `aitask_brainstorm_init.sh` copies the whole task
  file into the spec (`cat "$TASK_FILE" > "$SPEC_FILE"`), and `init_session`
  takes the first non-empty lines that do not start with `---`. Those are YAML
  frontmatter lines. Visible in the Browse tab's root node and "Brief:" line
  (`website/static/imgs/aitasks_brainstorm_browse_tab.svg`; scene
  `brainstorm_browse_tab`, to be regenerated after the fix).
- **Bare python3.** `ait brainstorm init` under a scratch `HOME` with
  `AIT_PYTHON` set failed with "failed to load launch_modes vocabulary":
  `launch_modes_sh.sh` uses `${_AIT_RESOLVED_PYTHON:-python3}`, and `python3`
  on PATH is the `~/.aitask/bin/python3` wrapper, which execs
  `$HOME/.aitask/venv/bin/python`. The screenshot tool works around it with a
  `python3` shim in its sample projects.

## Suggested fix

- Switcher: cap the dialog width to the pane in narrow mode and wrap or
  shorten the hint rows.
- Brainstorm: skip the frontmatter block when deriving the brief (or pass
  only the task body as the spec).
- launch_modes: honour `AIT_PYTHON` (or source `python_resolve.sh`) before
  falling back to `python3`.

The three are independent; split if that suits the work better.
