---
priority: medium
effort: high
depends: [t2073_1]
issue_type: feature
status: Ready
labels: [scratchpad]
gates: [risk_evaluated]
anchor: 2073
created_at: 2026-10-20 10:31
updated_at: 2026-10-20 10:32
---

## Context

Child of t2073 (minimonitor scratchpad pane). This child builds the `ait scratchpad`
Textual app: a basic notes editor that runs in a pane bound to a code agent (the
minimonitor key that spawns it is t2073_4). Persistence goes through the store helper
from t2073_1 (`aitask_scratchpad_store.sh`). Full design:
`aiplans/p2073_minimonitor_scratchpad_pane.md` ("One writer per store", "Autosave with
a deadline", "Store lifecycle"). Touches no file another in-flight task is editing.

The pane is killed by the companion-cleanup hook when its agent dies, so the app
cannot count on a clean exit. That is why autosave has a maximum dirty age and why the
loss window is stated and tested.

## Key Files to Modify

- NEW `.aitask-scripts/scratchpad/__init__.py`, `.aitask-scripts/scratchpad/scratchpad_app.py`
- NEW `.aitask-scripts/aitask_scratchpad.sh` (clone of `aitask_frozenagent.sh`)
- `./ait` — help line in the TUI block (~:34), case entry (~:218), update-check skip
  list next to `frozenagent` (~:197-200)
- `.aitask-scripts/lib/tui_registry.py` — `("scratchpad", None, None, False)`
- `.aitask-scripts/lib/shortcut_scopes.py` — `KNOWN_BINDING_SOURCES` entry
  `("scratchpad_app", "scratchpad/scratchpad_app.py", ("scratchpad",))`
- `tests/test_no_lib_to_tui_import.sh` — `TUI_PACKAGES` (~:46-49)
- `tests/test_shortcuts_registry_coverage.sh` — `TUIS` list
- NEW `tests/test_scratchpad_app.py`, NEW `tests/test_scratchpad_autosave_live.sh`

## Reference Files for Patterns

- `.aitask-scripts/frozenagent/frozenagent_app.py` — sys.path setup (:46-50), imports,
  `ShortcutsMixin`, `main(argv)`.
- `.aitask-scripts/monitor/monitor_shared.py` `ConcernPayloadEditModal` (~:4684) —
  TextArea usage; `ctrl+s`/`escape` bubble because they are absent from
  `TextArea.BINDINGS` (textual 8.2.7: TextArea owns ctrl+c copy, ctrl+v paste,
  ctrl+x cut, ctrl+z/ctrl+y undo/redo, f7 select-all).
- `monitor_shared._run_rejected_cmd` (~:1593) — asyncio subprocess seam with a timeout
  that never raises.
- `monitor_app._schedule_delayed_refresh` (~:1395) — set_timer cancel/re-arm.
- `lib/tui_clipboard.py` `copy_to_system_clipboard(app, text)`; the
  `tests/test_tui_clipboard_seam.sh` rule bans direct `.copy_to_clipboard(` calls.
- `tests/lib/tmux_isolation.sh` for the live test.

## Implementation Plan

1. App:
   - `ScratchpadApp(ShortcutsMixin, App)` with `_shortcuts_scope = "scratchpad"`.
   - CLI: `--task <id>` | `--unsaved`, plus an optional `--target <pane>` shown in the
     header.
   - One-line header state: saved / saving… / unsaved changes / NOT SAVED (no task) /
     read-only: open elsewhere / not saved — task archived.
   - A TextArea subclass whose `action_copy` sends the selection (or the whole buffer
     when nothing is selected) through `copy_to_system_clipboard`.
   - Bindings use modifier keys only: `ctrl+s` saves now, `ctrl+q` flushes and quits.
2. Startup order (ownership before content):
   1. store `open`;
   2. `os.open(<store>/.holder.lock, O_RDWR)` with no O_CREAT; a missing file → not
      saved, task archived;
   3. `fcntl.flock(LOCK_EX|LOCK_NB)`;
   4. only then read notes.md.

   On a busy lock, take a read-only path: `read_only=True`, never save, never promote
   itself later.
3. Autosave:
   - `TextArea.Changed` records `last_change`, and records `first_unsaved_change` when
     the buffer was clean.
   - One `set_timer` is re-armed at `min(last+1.0, first+3.0)`.
   - Saves pipe the text to the store `save` with `pass_fds=(holder_fd,)`, so an
     orphaned in-flight save keeps the lock until it lands.
   - Saves are serialized with a dirty flag.
   - Flush on ctrl+q, on unmount and on SIGHUP (best-effort).
   - `ARCHIVED`/`ABSENT` → header "not saved — task archived", autosave stops.
   - Unsaved mode never calls the helper and takes no lock.
   - **Stated loss window: at most the last 3 s of edits plus one in-flight save.**
4. Launcher, dispatcher, registries and test lists as listed above.

## Verification Steps

- `bash tests/run_all_python_tests.sh --test-dir tests` and read the last line.
  `tests/test_scratchpad_app.py` must cover:
  - existing notes are loaded;
  - a debounced save happens;
  - continuous typing every 0.2 s for 5 s saves within 3 s of the first edit (a
    control with the deadline disabled shows no save);
  - saves are serialized;
  - unsaved mode writes nothing;
  - a busy lock gives read-only mode with no saves;
  - ownership before read: a patched flock writes newer content just before it
    returns, and the editor shows that content (negative control: read-before-lock);
  - the save subprocess receives the holder fd;
  - ARCHIVED → the header says so;
  - copy goes through a patched `copy_to_system_clipboard`.
- `bash tests/test_scratchpad_autosave_live.sh` (isolated tmux):
  - text typed, debounce waited out, then `kill-pane` → the text is on disk;
  - continuous typing for 6 s, then an immediate `kill-pane` → every token older than
    3 s plus save latency is on disk;
  - control: a kill before the first deadline leaves the old content.
- `bash tests/test_tui_clipboard_seam.sh`, `bash tests/test_no_lib_to_tui_import.sh`,
  `bash tests/test_shortcuts_registry_coverage.sh`, `tests/test_shortcut_scopes.py`,
  `shellcheck .aitask-scripts/aitask_scratchpad.sh`.
- Manual: `ait scratchpad --unsaved` opens and accepts typing and paste.
