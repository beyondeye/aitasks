---
Task: t848_3_sweep_remaining_tuis.md
Parent Task: aitasks/t848_customizable_shortcuts.md
Sibling Tasks: aitasks/t848/t848_4_in_tui_shortcut_editor_modal.md, aitasks/t848/t848_5_settings_tui_shortcuts_tab.md, aitasks/t848/t848_6_documentation_for_customizable_shortcuts.md, aitasks/t848/t848_7_manual_verification_customizable_shortcuts.md
Archived Sibling Plans: aiplans/archived/p848/p848_1_shortcut_registry_and_overrides.md, aiplans/archived/p848/p848_2_label_renderer_and_board_pilot.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-30 21:30
---

# p848_3 — Migrate every remaining TUI to ShortcutsMixin

## Context

t848_1 added `lib/keybinding_registry.py` (scope/action_id → key map + user
overrides). t848_2 added `lib/shortcuts_mixin.py` (the `ShortcutsMixin` and
the standalone `get_label` helper), proved the pattern on `KanbanApp` +
`TaskDetailScreen`, and added the `(X)`-style label renderer
(`lib/shortcut_labels.py`).

This task applies that pattern to every remaining TUI under
`.aitask-scripts/` so that (a) `?` opens the editor stub in every TUI
(t848_4 will replace the stub), (b) hand-coded `(X)`-style labels become
registry-driven, and (c) the t848_4 editor has a complete scope tree to
enumerate. Pure repetitive migration — no new design decisions; minor
adjustments where the plan's original line numbers / file paths drifted
since 2026-05-27.

## Plan-verification deltas vs the original plan

The original plan called out a handful of file paths and line numbers that
have moved or were inaccurate. Resolved by inspection on 2026-05-30:

- `agent_command_screen.py` lives at `lib/agent_command_screen.py`
  (not `.aitask-scripts/agent_command_screen.py`). Same for
  `lib/stale_entry_modal.py`.
- `codebrowser_app.py`: `Copy (R)el` / `Copy (A)bs` buttons are at
  lines 128 / 131 (not 180-181). App BINDINGS at line 370.
- `brainstorm_app.py`: top-level `Binding("question_mark", "op_help", …)`
  is at line 2754 (not 2742). The `OperationHelpModal` at line 1401 has
  its own `BINDINGS` (lines 1410-1413) including `Binding("escape", "close")`
  and `Binding("question_mark", "close")`. The "[dim]Esc / ? close[/]"
  footer is at line 1428. Also: `Button("(C)ompare", …)` at line 1504.
- `settings_app.py`: hand-composed footers live at lines 1734, 1864-1865,
  and 1965 — three call sites, not one.
- `stats_app.py`: hand-composed Session footer is at line 218 (not 255).
- `KanbanApp` already splices `*ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS`
  alongside `*TuiSwitcherMixin.SWITCHER_BINDINGS` at line 3327. The
  pattern is established; apply it to every other App.

## Pattern (apply to every App-level class)

```python
from shortcuts_mixin import ShortcutsMixin
...
class FooApp(TuiSwitcherMixin, ShortcutsMixin, App):
    _shortcuts_scope = "foo"

    BINDINGS = [
        *TuiSwitcherMixin.SWITCHER_BINDINGS,
        *ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS,
        ...existing bindings unchanged...
    ]
```

MRO note: `TuiSwitcherMixin` first, then `ShortcutsMixin`, then `App`.
`ShortcutsMixin.__init__` calls `super().__init__()` and mutates
`self.BINDINGS` to apply user overrides — both mixins are cooperative.

For Modal/Screen classes that own their own BINDINGS and have user-visible
labels (footer strings, buttons, descriptions surfaced in `Footer`),
mix in `ShortcutsMixin` with a sub-scope `"<app>.<modal>"` and DO NOT
splice `SHORTCUTS_MIXIN_BINDINGS` — the `?` binding lives only at App
level.

For pure escape-to-cancel modals (no labels, single `escape` binding),
skip the mixin — they have nothing to customize.

For hand-coded `(X)`-style labels in `Button(…)` / `Static(…)` / `Label(…)`
literals, replace with `self.app.label(action_id, "Text")` (mixin
present on the App) or `get_label("<scope>", action_id, "Text")` (no
mixin instance reachable). Add a matching `Binding(key, action_id, …)`
where the literal isn't already covered by an existing binding.

## TUI-by-TUI sweep

Order (easy → hard):

1. **codebrowser** — `.aitask-scripts/codebrowser/codebrowser_app.py`,
   scope `"codebrowser"`. Mixin on `CodebrowserApp` (the App class
   that owns the line-370 BINDINGS block). Two buttons at 128/131:
   `Copy (R)el` → `self.app.label("copy_relative", "Copy Rel")` and
   `Copy (A)bs` → `self.app.label("copy_absolute", "Copy Abs")`.
   Those buttons sit inside `CopyPathScreen` (ModalScreen owning
   BINDINGS at 112) — add `ShortcutsMixin` with sub-scope
   `"codebrowser.copypath"` so the labels resolve.

2. **monitor / minimonitor** —
   `.aitask-scripts/monitor/monitor_app.py` (`MonitorApp`, scope
   `"monitor"`, BINDINGS at 577),
   `.aitask-scripts/monitor/minimonitor_app.py` (`MiniMonitorApp`, scope
   `"minimonitor"`, BINDINGS at 108). Pure mixin attach; no `(X)`
   literals. The 3 confirmation dialogs at lines 253/377/445 have only
   `escape` — skip them. `monitor_shared.py` widgets at lines 421/492
   are widgets, not Apps; they don't need their own mixin. If they
   inherit App scope via `self.app.label(...)` callsites, that's
   covered by the host App's scope.

3. **settings** — `.aitask-scripts/settings/settings_app.py`,
   scope `"settings"`, App BINDINGS at line 1121. Three hand-composed
   footers at lines 1734, 1864-1865, 1965 must become registry-derived.
   Strategy: introduce a small helper `_compose_settings_footer(self,
   *segments: tuple[str, str])` that takes
   `(action_id, label)` tuples and joins them with `"  |  "`, calling
   `self.app.label(action_id, label, style="leading")` for each. Where
   no Binding exists today (e.g. `↑↓ navigate`), add hidden bindings:

   ```python
   Binding("up", "nav_up", "Nav up", show=False),
   Binding("down", "nav_down", "Nav down", show=False),
   ```

   so the registry has a default to render. The literal `a/b/c/m/p/t:
   switch tabs` segment is already covered by per-tab bindings; render
   each via `self.app.label("switch_tab_<x>", "<x>")` joined by `/`.
   This is the largest single edit in the sweep; budget extra time
   here. Modal BINDINGS at 490/554/715/804/865/903/960/993 are all
   escape-cancel — skip.

4. **stats** — `.aitask-scripts/stats/stats_app.py`, scope `"stats"`,
   App BINDINGS at line 141. Line 218
   `"Session  [dim]← / → to cycle[/]"` becomes registry-driven via a
   `cycle_session` action_id (add hidden `Binding("left",
   "prev_session", "Prev session", show=False)` /
   `Binding("right", "next_session", "Next session", show=False)`).

5. **diffviewer / syncer / applink** — Pure mixin attach.
   - `.aitask-scripts/diffviewer/diffviewer_app.py`, scope
     `"diffviewer"`, BINDINGS at 261.
   - `.aitask-scripts/syncer/syncer_app.py`, scope `"syncer"`, App
     BINDINGS at 91.
   - `.aitask-scripts/applink/applink_app.py`, scope `"applink"`, App
     BINDINGS at 152. Two ModalScreens at 52/122 with their own
     BINDINGS — if they only carry escape-cancel, skip; otherwise sub-
     scope `"applink.<modal>"`.

6. **brainstorm** — `.aitask-scripts/brainstorm/brainstorm_app.py`,
   scope `"brainstorm"`. Two pieces of work:
   - **`?` → `H` for `op_help`**: change line 2754
     `Binding("question_mark", "op_help", "Op help", key_display="?")`
     to `Binding("H", "op_help", "Op help")` so the shared `?` editor
     (provided by `ShortcutsMixin`) takes over the `?` keyboard. Update
     the `OperationHelpModal` footer label at line 1428 from
     `"[dim]Esc / ? close[/]"` to `"[dim]Esc / H close[/]"` (literal —
     simpler than registry-render for a single label, and the close
     binding inside the modal still owns `escape`). Inside the modal
     BINDINGS at lines 1410-1413, remove the now-dead
     `Binding("question_mark", "close", "Close", show=False)` — `?`
     can no longer reach this modal because nothing opens it now.
     Keep `Binding("escape", "close", …)`.
   - `Button("(C)ompare", …)` at line 1504 → `self.app.label("compare",
     "Compare")` plus a matching `Binding("c", "compare", "Compare")`
     if one isn't already in the host class.
   - **`brainstorm_dag_display.py`** at line 447 has 11 BINDINGS with
     Unicode arrow / labels (`"↑ Layer"` etc). It's a ModalScreen with
     its own BINDINGS — mix in `ShortcutsMixin` with sub-scope
     `"brainstorm.dag"` so the editor enumerates them. Labels stay as
     literals; only registration changes.

7. **agent_command_screen** —
   `.aitask-scripts/lib/agent_command_screen.py`, scope
   `"board.agent_cmd"` (it's pushed by the board's command flow).
   App-screen BINDINGS at 252. Migrate 3 button literals at lines
   377 / 380 / 381 (`Copy (P)rompt`, `(C)opy cmd`, `(R)un in terminal`)
   to `self.app.label("copy_prompt", "Copy Prompt")`,
   `self.app.label("copy_command", "Copy cmd")`,
   `self.app.label("run_terminal", "Run in terminal")`. Line 467
   `(R)un in tmux` → `self.app.label("run_tmux", "Run in tmux")`.
   Add bindings where missing (binding rows around 252 already cover
   `copy_prompt`; the others need bindings).

8. **stale_entry_modal** — `.aitask-scripts/lib/stale_entry_modal.py`,
   scope `"syncer.stale_entry"` (it's pushed by the syncer). BINDINGS
   at line 96. Migrate line 147 `Button("(P)rune", …)` → `self.app.label
   ("prune", "Prune")`.

9. **tui_switcher** — `.aitask-scripts/lib/tui_switcher.py`. At import
   time call `register_app_bindings("shared", SWITCHER_BINDINGS)` so
   the `j` → `tui_switcher` action surfaces under a synthetic
   `"shared"` scope visible from every TUI's editor. The current
   `SWITCHER_BINDINGS` (line 1030) is just a one-liner; this is
   purely a registry-side change.

10. **Optional registry extension (only if needed):** Add a
    `customizable=False` flag to `register_app_bindings` so the
    editor can hide bindings like `escape` from the override UI.
    Plan defers this unless a TUI surface case demands it during the
    sweep — t848_4 owns the editor and can add the flag then. Skip
    unless we hit a concrete reason mid-implementation.

## New test — `tests/test_shortcuts_registry_coverage.sh`

For every App scope above, the test:

1. Sets `PYTHONPATH` to include `.aitask-scripts/lib`.
2. Imports each App module, instantiates the App in `headless=True`
   mode (or just reads `cls.BINDINGS` if instantiation is heavyweight),
   then asserts every Binding's `action` has been registered in
   `keybinding_registry._DEFAULTS` under the expected scope.
3. Calls `coherence_lint()` and prints (does NOT fail on) advisory
   warnings. Fails the test only if a `SHARED_ACTION_IDS` action
   (`quit`, `tui_switcher`, `refresh`, `shortcuts_editor`) is bound
   to genuinely conflicting keys across scopes.
4. Adds shellcheck-clean structure: `set -euo pipefail`,
   `assert_eq` / `assert_contains` helpers per repo convention,
   PASS/FAIL final summary.

The test is intentionally tolerant on advisory mismatches — flagging
them, not failing — so the sweep can land without forcing simultaneous
coherence-cleanup work (that's a t848_4/t848_5 concern).

## Step-by-step

1. Add the mixin + scope to the easiest TUI (`syncer`); confirm the
   pattern compiles by launching `ait syncer` for 2 seconds and
   killing it.
2. Apply to `diffviewer`, `applink` (also pure attach).
3. `codebrowser` (mixin attach + 2 button labels +
   `codebrowser.copypath` sub-scope).
4. `monitor` + `minimonitor` (mixin attach only).
5. `stats` (mixin attach + Session footer migration).
6. `settings` (mixin attach + 3 hand-composed footers — biggest single
   step).
7. `lib/agent_command_screen.py` + `lib/stale_entry_modal.py` (button
   literals + sub-scopes).
8. `brainstorm` last (`?` → `H` migration, modal sub-scope on
   `brainstorm.dag`, one button literal).
9. `tui_switcher.py` — register `"shared"` scope at import time.
10. Write `tests/test_shortcuts_registry_coverage.sh`, iterate until
    green.
11. Run the verification sequence below.

Commit cadence: optional per-TUI micro-commits are fine but not
required; one combined commit at the end is also acceptable. The
Step 8 review prompt is unchanged.

## Verification

```bash
# Per-test
bash tests/test_shortcuts_registry_coverage.sh
bash tests/test_keybinding_registry.sh
bash tests/test_shortcut_labels.sh

# Smoke launches (each TUI must boot without traceback)
for tui in board monitor minimonitor codebrowser brainstorm settings stats syncer applink diffviewer; do
  echo "Launching $tui — kill after 3s"
  ait "$tui" &
  pid=$!
  sleep 3
  kill "$pid" 2>/dev/null || true
  wait "$pid" 2>/dev/null || true
done

# Lint
shellcheck tests/test_shortcuts_registry_coverage.sh
```

## Verification (manual — for the t848_7 manual-verification sibling)

- `ait brainstorm` — pressing `?` no longer opens op-help; pressing
  `H` opens it; the help-modal footer reads `Esc / H close`. The
  shortcuts-editor stub toast appears on `?`.
- Every TUI launches cleanly; `?` in each toasts "Shortcuts editor not
  yet available — coming in t848_4" (the t848_2 stub behavior).
- Settings tab-switcher footer reflects the current bindings; if I
  edit `aitasks/metadata/userconfig.yaml` to add
  `shortcuts: {settings: {switch_tab_p: P}}`, relaunch `ait settings`,
  the footer reflects the override.

## Notes for sibling tasks

- The `customizable=False` extension is deferred to t848_4 (editor
  modal). The current registry already records everything; t848_4 just
  needs to filter by an optional flag when populating the editor.
- Consistent shared action_ids established here: `quit`, `refresh`,
  `tui_switcher` are already in `SHARED_ACTION_IDS`; if any TUI binds
  `q` to something other than `quit`, document it as a noted exception
  in this plan's Final Implementation Notes so t848_5's Settings tab
  doesn't try to render them as shared.
- Sub-scope convention follows t848_2: `<app>.<modal>` for
  ModalScreen/Screen with own BINDINGS. The editor in t848_4 can split
  on `.` to render hierarchy.

## Step 9 — Post-implementation

Standard archival; no special cleanup.
