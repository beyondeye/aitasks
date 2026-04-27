---
Task: t657_remove_m_shortcut_for_multi_on_of.md
Base branch: main
plan_verified: []
---

# Plan: Hide `M` (toggle multi-session) shortcut from monitor/minimonitor footers

## Context

`ait monitor` and `ait minimonitor` both expose an `M` shortcut that toggles
display of code-agent panes from *other* tmux sessions on/off (the
"multi-session view"). The shortcut is currently advertised in the footer/hint
area of both TUIs. The user wants the shortcut to keep working but to no
longer appear in the on-screen footer hints — it's a niche power-user toggle
that clutters the footer for the more common day-to-day shortcuts.

Note: even though the task title says "m shortcut", the actual binding for
multi-session toggle is uppercase **`M`**. Lowercase `m` in minimonitor is a
different binding (`switch_to_monitor` / "Full Monitor") and stays visible.

## Files to change

### 1. `.aitask-scripts/monitor/monitor_app.py`

Two display paths advertise `M`:

- **Auto-rendered Textual `Footer()` widget** — driven by the `BINDINGS`
  list at line 440. The `Binding("M", "toggle_multi_session", "Multi")` at
  line 456 has no `show=` kwarg, so it renders in the footer by default.
  - **Fix:** add `show=False` so Textual's footer hides it.
  - New line: `Binding("M", "toggle_multi_session", "Multi", show=False),`

- **Manually-rendered session bar** — `_rebuild_session_bar()` writes a
  `[dim]Tab: switch panel · M: toggle multi[/]` suffix on lines 871 and 878.
  - **Fix:** drop the ` · M: toggle multi` portion on both lines, leaving
    `[dim]Tab: switch panel[/]`.

### 2. `.aitask-scripts/monitor/minimonitor_app.py`

The minimonitor does **not** use Textual's `Footer()` widget — its hint area
is a plain `Static` widget composed at line 145. The `M` binding (line 112)
already has `show=False`, so only the manual hint string needs editing.

- **Manually-rendered key-hints `Static`** — line 148 currently reads:
  `"m:full monitor  M:multi"`.
  - **Fix:** remove `M:multi` and the preceding two spaces, leaving:
    `"m:full monitor"`.

The action handler `action_toggle_multi_session` on both classes is left
intact, so `M` continues to work — only the on-screen advertisement is
removed.

## Out of scope

- The `M` action implementation, `_monitor.multi_session` state, related
  config, and its on-disk persistence are untouched.
- The lowercase `m` binding in minimonitor (`switch_to_monitor` →
  "Full Monitor") stays both bound and advertised.
- The `Tab: switch panel` portion of the monitor session-bar suffix stays;
  only the `M` portion is removed.

## Verification

1. Read each modified file to confirm the three textual edits are correct
   and no unrelated changes leaked in.
2. Grep to confirm zero remaining footer-string matches:
   ```bash
   grep -rn -E "(M:multi|M: toggle multi)" .aitask-scripts/
   ```
   Expected: no output.
3. Run the existing monitor/minimonitor multi-session tests (they exercise
   the `M` action handler and binding, and don't assert on footer strings,
   so they should keep passing):
   ```bash
   bash tests/test_multi_session_monitor.sh
   bash tests/test_multi_session_minimonitor.sh
   ```
4. Manual smoke test (after merge): open `ait monitor` and `ait minimonitor`,
   confirm:
   - `M` is absent from the footer / hint area in both TUIs.
   - Pressing `M` still toggles the multi-session view (state flips, session
     dividers appear/disappear, status bar updates as before).
   - In monitor, the session bar still shows `Tab: switch panel` (without
     the `· M: toggle multi` suffix).
   - In minimonitor, the hint area still shows `m:full monitor` (without
     the trailing `M:multi`).

## Step 9 (Post-Implementation)

Standard archive flow per `.claude/skills/task-workflow/SKILL.md` — no
worktree was created, so no merge step. Commit the code changes with
message `bug: Hide M (multi-session) shortcut from monitor/minimonitor footers (t657)`,
then run the archive script.
