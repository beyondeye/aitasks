---
priority: high
effort: high
depends: [t1705_5]
issue_type: feature
status: Ready
labels: [tui, textual, tui_switcher, custom_shortcuts, codeagent, session_persistence, python]
gates: [risk_evaluated]
anchor: 1705
created_at: 2026-09-04 16:05
updated_at: 2026-09-04 16:05
---

## Context

Sixth child of t1705 (frozen code agents). The new **`ait frozenagent`**
TUI: the stand-in that takes over a frozen agent's pane and renders its
persisted terminal output faithfully, with search, selection + copy, a
plain/markdown toggle, and restore / re-pick / drop actions that delegate to
the detached coordinator shipped by t1705_5 (`aitask_frozen.sh restore
<id>` via `run-shell -b` — never in-process, because the coordinator replaces
this very pane). Name and switcher key were decided with the user
(`frozenagent`, `f`). Parent plan §B/§D are **PINNED** (reproduced in
`aiplans/p1705/p1705_6_frozenagent_viewer_tui.md`); two rules from them are
this child's own responsibility: **the viewer stamps
`@aitask_standin_ready=<record-id>` on its own pane after mount and only
then** (self-stamp rule, like `mark_monitor_pane`), and the viewer never
mutates the store directly.

## Deliverables

1. **`.aitask-scripts/frozenagent/frozenagent_app.py`** —
   `class FrozenAgentApp(TuiSwitcherMixin, ShortcutsMixin, App)`,
   `_shortcuts_scope = "frozenagent"`, `current_tui_name = "frozenagent"`,
   `BINDINGS = [*TuiSwitcherMixin.SWITCHER_BINDINGS,
   *ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS, …]`. Two modes:
   - `--record <id>` **viewer**: `RichLog(highlight=False, markup=False,
     wrap=False)` fed `Text.from_ansi(capture.ansi)` (default) or plain
     `Text(capture.txt)` (`r`); `m` renders all lines — or the selected
     range — as Markdown in a modal (`lib/section_viewer.SectionAwareMarkdown`
     or Textual `Markdown`); `/` search box, `n` next, `escape` cancel over
     `capture.txt` line indices (logview precedent, plus a highlighted
     current match); keyboard range selection `shift+up/down` +
     `escape` (the `codebrowser/code_viewer.py` model: `_selection_start/_end/_active`,
     `get_selected_range()` 1-indexed) **and** Textual native
     `ALLOW_SELECT` mouse selection; `y` copies the keyboard range or the
     native selection through `lib/tui_clipboard.copy_to_system_clipboard`
     (**only** — `tests/test_tui_clipboard_seam.sh` enforces it); `g`/`G`
     top/bottom; header line: `<project> · <window> · t<task_id> <title> ·
     <agent_string> · frozen <frozen_at> · <capture_lines> lines · <state>`
     (title via `TaskInfoCache`-equivalent lookup of the task file, `""`
     when unbound). Escape any `[…]` in the header markup (t1486 lesson,
     `logview_app.py:71-79`). Startup focus goes to the log on every path,
     including the missing-capture early return.
   - bare `ait frozenagent` **list**: every `frozen` record across projects
     (`SessionsView`), one row per record (`<project> <window> t<task> <agent>
     <frozen_at> <lines>`), `enter` opens the viewer in-process, `R`/`p`/`k`
     as below, `q` quits.
   - Actions (both modes, on the current record): `R` restore, `p` re-pick
     (only when `task_id` non-empty; otherwise a notify), `k` drop (confirm
     dialog — reuse `KillConfirmDialog`'s shape). Each shells out via
     `TmuxClient.run(["run-shell", "-b", "<repo>/.aitask-scripts/aitask_frozen.sh restore <id> [--repick]"])`
     / `… drop <id>`; the viewer then shows `restoring…` and polls
     `SessionsView` every 1 s: on `live` it is about to be replaced (do
     nothing); on `frozen` again with `last_error` / a new `restore_attempts`
     it refreshes the header with the failure reason (`restore failed:
     <reason> — capture kept`); `ack=liveness` renders `restored, unverified —
     capture kept`. Use a `@work` worker or `set_interval`, never block the
     event loop (`monitor_shared._run_marks_cmd` seam shape).
   - Record resolution: `--record <id>` → `show` via the lock-free reader;
     missing capture file → header says so, `R`/`p` still offered, `k`
     offered; unknown id → exit 2 with a one-line error.
2. **`.aitask-scripts/aitask_frozenagent.sh`** — clone
   `aitask_diffviewer.sh` verbatim (`require_ait_python`, textual/yaml
   probe, `ait_warn_if_incapable_terminal`, `exec`).
3. **`ait` dispatcher** — usage `TUI:` block (`ait:27-38`) + case beside
   `diffviewer` (`ait:208`); add to the update-check bypass list (`ait:190`)
   since a stand-in must not stall on a version check.
4. **Registration (atomic 4-part + 3)** — `lib/tui_registry.py` row
   `("frozenagent","Frozen Agent","ait frozenagent",True)` positioned after
   `monitor`; `lib/tui_switcher.py` `_TUI_SHORTCUTS["frozenagent"]="f"`,
   `Binding("f","shortcut_frozenagent","Frozen Agent",show=False)` in
   `_QUICK_JUMP_BINDINGS`, `action_shortcut_frozenagent`, `_HINT_ITEMS`
   entry if the footer budget allows (`tests/test_tui_switcher_footer_fit.sh`);
   `lib/shortcut_scopes.py` `KNOWN_BINDING_SOURCES` entry
   `("frozenagent_app","frozenagent/frozenagent_app.py",("frozenagent",))`;
   `tests/test_shortcuts_registry_coverage.sh` `TUIS` list;
   `tests/test_no_lib_to_tui_import.sh` `TUI_PACKAGES`. The switcher's
   `frozenagent` entry launches the bare list mode.
5. **`standin_command()`** in `lib/agent_sessions.py` already names
   `ait frozenagent --record <id>` — verify the argv round-trips through
   `respawn-pane` (quoting) with a live smoke.

## Tests

- `tests/test_frozenagent_app.py` (`App.run_test`, headless): ANSI vs
  plain render of a fixture capture (`tests/data/frozen_capture/*.ansi`),
  search wrap + not-found, keyboard range → `y` copies exactly those lines
  (monkeypatch `copy_to_system_clipboard`, assert the text), native
  selection path, markdown modal for a range, header escaping, startup
  focus on the log (missing-file path too), `R`/`p`/`k` produce the exact
  `run-shell -b` argv (fake `TmuxClient`), `p` refused without task id,
  restore-failed header refresh from a `SessionsView` change, list mode
  rows + `enter`.
- `tests/test_frozenagent_standin_stamp.sh` (isolated tmux): launching
  `ait frozenagent --record <id>` in a pane stamps `@aitask_standin_ready=<id>`
  on **that** pane after mount and never on another pane; the stamp is the
  viewer's, not the launcher's.
- Existing guards: `test_tui_clipboard_seam.sh`, `test_shortcut_scopes.py`,
  `test_shortcuts_registry_coverage.sh`, `test_no_lib_to_tui_import.sh`,
  `test_tui_switcher_hint_text.py`, `test_tui_switcher_footer_fit.sh`,
  `test_textual_markup_structure.py` (add the header pin).

## Key files

- New: `frozenagent/frozenagent_app.py`, `frozenagent/__init__.py`,
  `aitask_frozenagent.sh`, the two test files, `tests/data/frozen_capture/`.
- Edit: `ait`, `lib/tui_registry.py`, `lib/tui_switcher.py`,
  `lib/shortcut_scopes.py`, the two test lists, `tests/test_textual_markup_structure.py`.

## Reference patterns

- `logview/logview_app.py` (whole file: `Text.from_ansi`, raw toggle,
  search, the focus trap), `codebrowser/code_viewer.py:77-106`, `:381-452`
  (selection model), `lib/numbered_source_view.py`, `lib/tui_clipboard.py`,
  `lib/section_viewer.py:357-376`, `diffviewer/diffviewer_app.py` (minimal
  registered TUI), `codebrowser/codebrowser_app.py:36,331,413,449` (full
  mixin wiring), `aidocs/framework/tui_conventions.md` §"Adding a TUI"
  (:514-533) and the `KNOWN_BINDING_SOURCES` probe rules (:789-805),
  `aidocs/framework/tmux_gateway.md`.
- Textual 8.2.7: `Widget.ALLOW_SELECT`, `text_selection`, `get_selection`
  (`site-packages/textual/widget.py:328,689,4213`) — first use in this repo.

## Verification

```bash
bash tests/run_all_python_tests.sh
bash tests/test_frozenagent_standin_stamp.sh      # isolated tmux; fine from any shell (read-only on the real server)
bash tests/test_tui_clipboard_seam.sh tests/test_shortcuts_registry_coverage.sh tests/test_no_lib_to_tui_import.sh tests/test_tui_switcher_footer_fit.sh
./ait frozenagent --record <id-from-a-test-store>   # manual look
```
Not tmux-stress (the viewer only reads and self-stamps), but run the
stand-in stamp test on an isolated server anyway.
