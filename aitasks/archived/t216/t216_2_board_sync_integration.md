---
priority: high
effort: medium
depends: [t216_1, t216_1]
issue_type: feature
status: Done
labels: [aitask_board]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-23 15:51
updated_at: 2026-02-23 22:40
completed_at: 2026-02-23 22:40
---

## Context

Parent task t216 requires integrating the new `ait sync` command (built in t216_1) into the `ait board` Python TUI. The board currently auto-refreshes from local disk only (timer-based, default 5 min). This task adds remote sync capability: periodic background sync, manual sync via keyboard/command palette, conflict detection with dialog, and a settings toggle.

Depends on t216_1 which creates `aiscripts/aitask_sync.sh` with `--batch` mode that returns structured output (SYNCED, PUSHED, PULLED, NOTHING, CONFLICT:<files>, NO_NETWORK, NO_REMOTE, ERROR:<msg>).

## Key Files to Modify

- **Modify:** `aiscripts/board/aitask_board.py` — all board changes (modal, sync methods, bindings, settings, command palette)

## Reference Files for Patterns

- `aiscripts/board/aitask_board.py`:
  - `DeleteConfirmScreen` (line 979) — pattern for the new `SyncConflictScreen` modal
  - `run_aitask_pick()` (line 2190) — pattern for `@work(exclusive=True)` + terminal launch
  - `_find_terminal()` (line 2179) — reuse for launching interactive sync in terminal
  - `_auto_refresh_tick()` (line 1977) — modify to conditionally run sync
  - `KanbanCommandProvider` (line 1713) — add "Sync with Remote" command
  - `SettingsScreen` (line 1618) — add `sync_on_refresh` toggle
  - `_handle_settings_result()` (line 2403) — already handles `settings.update(result)`, no change needed
  - `_update_subtitle()` (line 1983) — modify to show sync status
  - `BINDINGS` (line 1886) — add `s` key binding
  - `DATA_WORKTREE` constant (line 29) — check for data-branch mode

## Implementation Plan

### 1. Add `SyncConflictScreen` modal (~line 1660, near other modals)

```python
class SyncConflictScreen(ModalScreen):
    """Modal dialog shown when ait sync detects merge conflicts."""
    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, conflicted_files: list[str]):
        super().__init__()
        self.conflicted_files = conflicted_files

    def compose(self):
        file_list = "\n".join(f"  - {f}" for f in self.conflicted_files)
        with Container(id="dep_picker_dialog"):
            yield Label("Sync Conflict Detected", id="dep_picker_title")
            yield Label(
                f"Conflicts between local and remote task data:\n\n{file_list}\n\n"
                f"Open interactive terminal to resolve?",
                id="commit_files"
            )
            with Horizontal(id="detail_buttons"):
                yield Button("Resolve Interactively", variant="warning", id="btn_sync_resolve")
                yield Button("Dismiss", variant="default", id="btn_sync_dismiss")

    @on(Button.Pressed, "#btn_sync_resolve")
    def resolve(self): self.dismiss(True)

    @on(Button.Pressed, "#btn_sync_dismiss")
    def dismiss_dialog(self): self.dismiss(False)

    def action_cancel(self): self.dismiss(False)
```

Reuse existing CSS IDs (`dep_picker_dialog`, `dep_picker_title`, `detail_buttons`) for consistent styling.

### 2. Add sync methods to `KanbanApp`

**`_run_sync(show_notification=True)`** — `@work(exclusive=True)`:
- Calls `subprocess.run(["./aiscripts/aitask_sync.sh", "--batch"], capture_output=True, text=True, timeout=30)`
- Parses stdout line:
  - `CONFLICT:<files>` → call `self.app.call_from_thread(self._show_conflict_dialog, files.split(","))` then return (don't refresh yet)
  - `NO_NETWORK` → `notify("Sync: No network", severity="warning")` if show_notification
  - `NO_REMOTE` → `notify("Sync: No remote configured", severity="warning")` if show_notification
  - `NOTHING` → `notify("Already up to date", severity="information")` if show_notification
  - `PUSHED/PULLED/SYNCED` → `notify("Sync: <status>", severity="information")` if show_notification
  - `ERROR:<msg>` → `notify("Sync error: <msg>", severity="error")`
- On `subprocess.TimeoutExpired`: notify warning
- On `FileNotFoundError`: notify error (script not found)
- After all non-CONFLICT cases: `self.manager.load_tasks(); self.refresh_board()`

**`_show_conflict_dialog(files)`** — runs on main thread:
```python
def _show_conflict_dialog(self, files):
    def on_result(resolve):
        if resolve:
            self._run_interactive_sync()
        else:
            self.manager.load_tasks()
            self.refresh_board()
    self.push_screen(SyncConflictScreen(files), on_result)
```

**`_run_interactive_sync()`** — `@work(exclusive=True)`:
- Same pattern as `run_aitask_pick`: find terminal, launch `./ait sync`, refresh board after
```python
terminal = self._find_terminal()
if terminal:
    subprocess.Popen([terminal, "--", "./ait", "sync"])
else:
    with self.suspend():
        subprocess.call(["./ait", "sync"])
    self.manager.load_tasks()
    self.refresh_board()
```

### 3. Add `action_sync_remote()` and keyboard binding

```python
def action_sync_remote(self):
    if self._modal_is_active():
        return
    self._run_sync(show_notification=True)
```

Add to `BINDINGS` (line 1913):
```python
Binding("s", "sync_remote", "Sync"),
```

### 4. Modify `_auto_refresh_tick()` (line 1977)

```python
def _auto_refresh_tick(self):
    if self._modal_is_active():
        return
    if self.manager.settings.get("sync_on_refresh", False) and DATA_WORKTREE.exists():
        self._run_sync(show_notification=False)
    else:
        self.action_refresh_board()
```

### 5. Add to command palette (line 1716 and 1742)

In `discover()`:
```python
yield DiscoveryHit(display="Sync with Remote", command=app.action_sync_remote, help="Push local changes and pull remote changes")
```

In `search()` commands list:
```python
("Sync with Remote", app.action_sync_remote, "Push local changes and pull remote changes"),
```

### 6. Add settings toggle (line 1629-1651)

In `SettingsScreen.compose()` after the auto-refresh field:
```python
current_sync = "yes" if self.manager.settings.get("sync_on_refresh", False) else "no"
yield CycleField("Sync on refresh", ["no", "yes"], current_sync, "sync_on_refresh", id="cf_sync_on_refresh")
yield Label("  [dim]Push/pull task data on each auto-refresh[/dim]", classes="settings-hint")
```

In `save_settings()`:
```python
sync_field = self.query_one("#cf_sync_on_refresh", CycleField)
new_sync = sync_field.current_value == "yes"
self.dismiss({"auto_refresh_minutes": new_minutes, "sync_on_refresh": new_sync})
```

### 7. Update subtitle (line 1983)

```python
def _update_subtitle(self):
    minutes = self.manager.auto_refresh_minutes
    sync = self.manager.settings.get("sync_on_refresh", False)
    if minutes > 0:
        suffix = " + sync" if sync else ""
        self.sub_title = f"Auto-refresh: {minutes}min{suffix}"
    else:
        self.sub_title = "Auto-refresh: off"
```

## Verification Steps

1. `./ait board` → press `s` → verify sync notification appears
2. Open command palette (Ctrl+\`) → type "sync" → verify "Sync with Remote" appears
3. Settings (S) → verify "Sync on refresh" toggle → save → check subtitle shows "+ sync"
4. Test with auto-refresh enabled + sync: wait for timer tick, verify sync runs silently
5. Test conflict scenario: modify task from another clone, create local conflict, press `s` → verify conflict dialog appears
