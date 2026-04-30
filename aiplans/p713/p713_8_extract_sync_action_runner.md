---
Task: t713_8_extract_sync_action_runner.md
Parent Task: aitasks/t713_ait_syncer_tui_for_remote_desync_tracking.md
Sibling Tasks: aitasks/t713/t713_3_sync_actions_failure_handling.md, aitasks/t713/t713_4_tmux_switcher_monitor_integration.md, aitasks/t713/t713_5_permissions_and_config.md, aitasks/t713/t713_6_website_syncer_docs.md, aitasks/t713/t713_7_manual_verification_syncer_tui.md
Archived Sibling Plans: aiplans/archived/p713/p713_1_desync_state_helper.md, aiplans/archived/p713/p713_2_syncer_entrypoint_and_tui.md
Worktree: (none — working on current branch per profile 'fast')
Branch: main
Base branch: main
---

## Context

Parent **t713** is shipping a new `ait syncer` TUI that surfaces remote desync state and (in t713_3) lets the user trigger sync/pull/push actions. The board TUI (`.aitask-scripts/board/aitask_board.py`) already has a working implementation of those actions: it shells out to `.aitask-scripts/aitask_sync.sh --batch`, parses the structured first-line output, displays a conflict-resolution modal, and offers an interactive `./ait sync` fallback when conflicts arise.

If t713_3 lands as currently planned, ~80 lines of parsing/dispatch glue (worker, status branching, conflict modal, interactive fallback) get duplicated verbatim into `syncer_app.py`. CLAUDE.md ("Refactor duplicates before adding to them") plus t713_1's own precedent (extracting `lib/desync_state.py` as the second-caller refactor of `aitask_changelog.sh:check_data_desync`) require the glue to be extracted to a shared helper **before t713_3 adds the second caller**.

This task is the second-caller-extraction sibling. It must land between t713_2 (TUI shell) and t713_3 (sync actions); t713_3 will be updated to depend on this task.

## Module location: `.aitask-scripts/lib/sync_action_runner.py`

Decision: place the new module in `lib/`, not `board/`. Precedent (all shared TUI helpers in this repo live in `lib/`):

- `lib/desync_state.py` — non-Textual data helper (the t713_1 extraction).
- `lib/agent_command_screen.py`, `lib/agent_model_picker.py`, `lib/section_viewer.py`, `lib/tui_switcher.py` — Textual `ModalScreen` / mixin classes already shipping `DEFAULT_CSS`.
- `lib/agent_launch_utils.py` — provides `find_terminal()` which the new module needs to import.

`board/` only contains board-specific files (`aitask_board.py`, `aitask_merge.py`, `task_yaml.py`). Both consumers (`aitask_board.py:13`, `syncer_app.py:19`) already do `sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))`, so the import is `from sync_action_runner import …` from either side. No circular-import risk: `agent_launch_utils.find_terminal` has no Textual dependency.

## New module API — `.aitask-scripts/lib/sync_action_runner.py`

Wire-protocol status constants (must match `aitask_sync.sh --batch` exactly), plus two synthetic statuses owned by the runner:

```python
STATUS_SYNCED      = "SYNCED"
STATUS_PUSHED      = "PUSHED"
STATUS_PULLED      = "PULLED"
STATUS_NOTHING     = "NOTHING"
STATUS_AUTOMERGED  = "AUTOMERGED"
STATUS_CONFLICT    = "CONFLICT"
STATUS_NO_NETWORK  = "NO_NETWORK"
STATUS_NO_REMOTE   = "NO_REMOTE"
STATUS_ERROR       = "ERROR"
STATUS_TIMEOUT     = "TIMEOUT"      # synthetic (subprocess.TimeoutExpired)
STATUS_NOT_FOUND   = "NOT_FOUND"    # synthetic (FileNotFoundError on script)

DEFAULT_SYNC_TIMEOUT_SECONDS = 30   # wall-clock cap; aitask_sync.sh has its own 10s NETWORK_TIMEOUT per fetch/push.

@dataclass
class SyncResult:
    status: str
    conflicted_files: list[str] = field(default_factory=list)
    error_message: str | None = None
    raw_output: str = ""

def parse_sync_output(stdout: str) -> SyncResult: ...
def run_sync_batch(timeout: float = DEFAULT_SYNC_TIMEOUT_SECONDS) -> SyncResult: ...

class SyncConflictScreen(ModalScreen): ...
def run_interactive_sync(app, on_done: Callable[[], None] | None = None) -> None: ...
```

**Parser semantics** — `parse_sync_output(stdout)`:

- Strip + take first non-empty line (mirrors current board: `result.stdout.strip().splitlines()[0]`).
- `SYNCED` / `PUSHED` / `PULLED` / `NOTHING` / `AUTOMERGED` / `NO_NETWORK` / `NO_REMOTE` → status set, no extra fields.
- `CONFLICT:a.md,b.md` → `status=STATUS_CONFLICT`, `conflicted_files=["a.md","b.md"]`. Bare `CONFLICT:` → `conflicted_files=[""]` (preserve current board behavior verbatim — `"".split(",")` returns `[""]`, not `[]`; pure extraction, zero behavior drift).
- `ERROR:<msg>` → `status=STATUS_ERROR`, `error_message="<msg>"`.
- Empty stdout / unknown status string → `status=STATUS_ERROR` with descriptive `error_message` ("empty output from sync script" / "unknown status: <line>"). No separate `STATUS_UNKNOWN` — every caller would treat it as an error anyway.
- `raw_output` stores the original stdout for diagnostics.

**Worker semantics** — `run_sync_batch(timeout)`:

- Blocking `subprocess.run(["./.aitask-scripts/aitask_sync.sh", "--batch"], capture_output=True, text=True, timeout=timeout)`.
- `subprocess.TimeoutExpired` → `SyncResult(status=STATUS_TIMEOUT, error_message="sync timed out after Ns")`.
- `FileNotFoundError` → `SyncResult(status=STATUS_NOT_FOUND, error_message="sync script not found")`.
- Otherwise hand `result.stdout` to `parse_sync_output()`.
- Designed to be called from inside the caller's `@work(thread=True)` worker. The module never imports `textual` for this function — keeps the parser+runner unit-testable without Textual.

**Conflict modal** — `SyncConflictScreen(ModalScreen)`:

- Verbatim move of lines 2943-2974 from `aitask_board.py` with two changes:
  - Internal CSS ids renamed `dep_picker_dialog` → `sync_conflict_dialog`, `dep_picker_title` → `sync_conflict_title`, `commit_files` → `sync_conflict_files`, `detail_buttons` → `sync_conflict_buttons`. Required because the existing ids are reused by other board screens (DepPicker at lines 1393/1428, etc.) — leaving them would create accidental cross-screen styling coupling and break the modal in the syncer (whose CSS doesn't define them).
  - Ship a `DEFAULT_CSS` class attribute matching the renamed ids, with the same dimensions/styling currently in `BoardApp.CSS` lines 3176-3213. Pattern matches `lib/agent_command_screen.py:90`, `lib/agent_model_picker.py:288`, `lib/section_viewer.py:94`, `lib/tui_switcher.py:219`.

**Interactive fallback** — `run_interactive_sync(app, on_done=None)`:

- Plain sync function (not `async`). Current board version is `@work(exclusive=True)` async but only because of `app.suspend()` — there is no `await` inside, so `app.suspend()` works fine in sync context. Keeping it plain-sync lets each caller wrap it in their own `@work` if needed and keeps the module Textual-light.
- Body mirrors current `_run_interactive_sync` (board lines 4158-4168):
  - `terminal = find_terminal()` (imported from `agent_launch_utils`).
  - If terminal: `subprocess.Popen([terminal, "--", "./ait", "sync"])` (fire-and-forget, no `on_done` invoked because the caller can't observe the spawned terminal's exit anyway — matches existing board behavior).
  - Else: `with app.suspend(): subprocess.call(["./ait", "sync"])`, then call `on_done()` if provided.
- Docstring notes: "Must be called from a worker context when `find_terminal()` returns None, because `app.suspend()` blocks; safe from any context when a terminal is available."

## Refactor of `.aitask-scripts/board/aitask_board.py`

1. **Delete** the inline `SyncConflictScreen` class (lines 2943-2974).

2. **Delete** the inline `_run_interactive_sync` method (lines 4158-4168).

3. **Add import** near the existing `agent_launch_utils` import (line 16):

   ```python
   from sync_action_runner import (
       SyncConflictScreen,
       run_sync_batch,
       run_interactive_sync,
       STATUS_AUTOMERGED, STATUS_CONFLICT, STATUS_ERROR,
       STATUS_NOTHING, STATUS_NO_NETWORK, STATUS_NO_REMOTE,
       STATUS_NOT_FOUND, STATUS_PULLED, STATUS_PUSHED,
       STATUS_SYNCED, STATUS_TIMEOUT,
   )
   ```

4. **Rewrite `_run_sync`** (lines 4097-4146) — keep it as a board instance-method wrapper so the three callsites (3444 timer, 4095 manual, 5155 post-rename) stay DRY and the `show_notification`/`show_overlay` flags + the post-hooks (`manager.load_tasks` + `refresh_board(refresh_locks=True)`) stay co-located with the board:

   ```python
   @work(exclusive=True, thread=True)
   def _run_sync(self, show_notification: bool = True, show_overlay: bool = False):
       result = run_sync_batch()

       if show_overlay:
           self.app.call_from_thread(self.pop_screen)

       status = result.status
       if status == STATUS_CONFLICT:
           self.app.call_from_thread(self._show_conflict_dialog, result.conflicted_files)
           return
       if status == STATUS_TIMEOUT:
           if show_notification:
               self.app.call_from_thread(self.notify, "Sync timed out", severity="warning")
           return
       if status == STATUS_NOT_FOUND:
           self.app.call_from_thread(self.notify, "Sync script not found", severity="error")
           return
       if status == STATUS_NO_NETWORK and show_notification:
           self.app.call_from_thread(self.notify, "Sync: No network", severity="warning")
       elif status == STATUS_NO_REMOTE and show_notification:
           self.app.call_from_thread(self.notify, "Sync: No remote configured", severity="warning")
       elif status == STATUS_NOTHING and show_notification:
           self.app.call_from_thread(self.notify, "Already up to date", severity="information")
       elif status == STATUS_AUTOMERGED and show_notification:
           self.app.call_from_thread(self.notify, "Sync: Auto-merged conflicts", severity="information")
       elif status in (STATUS_PUSHED, STATUS_PULLED, STATUS_SYNCED) and show_notification:
           self.app.call_from_thread(self.notify, f"Sync: {status.capitalize()}", severity="information")
       elif status == STATUS_ERROR:
           self.app.call_from_thread(self.notify, f"Sync error: {result.error_message}", severity="error")

       self.app.call_from_thread(self.manager.load_tasks)
       self.app.call_from_thread(self.refresh_board, refresh_locks=True)
   ```

   **Critical: LoadingOverlay ordering.** The original code pops the overlay BEFORE dispatching `_show_conflict_dialog` so the conflict modal doesn't stack on top of the overlay (lines 4119-4124). Preserve that ordering — `pop_screen` runs first, then status dispatch.

5. **Simplify `_show_conflict_dialog`** (lines 4148-4156) — replace the old `_run_interactive_sync` call with the shared helper, capturing the post-resolve hooks via `on_done`:

   ```python
   def _show_conflict_dialog(self, files: list[str]):
       def on_result(resolve):
           if resolve:
               # run_interactive_sync uses app.suspend() in the no-terminal path,
               # so wrap in @work to stay off the main thread when needed.
               self._run_interactive_sync_shared()
           else:
               self.manager.load_tasks()
               self.refresh_board()
       self.push_screen(SyncConflictScreen(files), on_result)

   @work(exclusive=True)
   async def _run_interactive_sync_shared(self):
       def reload():
           self.manager.load_tasks()
           self.refresh_board(refresh_locks=True)
       run_interactive_sync(self.app, on_done=reload)
   ```

   The thin `_run_interactive_sync_shared` wrapper preserves the current `@work(exclusive=True)` async decoration so `app.suspend()` is safe to call. Naming differs from the deleted `_run_interactive_sync` only to avoid grep collision with old comments.

6. **Verify CSS rules** at `BoardApp.CSS` lines 3126-3213 are still needed by other board screens (`#dep_picker_dialog`, `#dep_picker_title`, `#detail_buttons`, `#commit_files`) — they ARE (DepPicker, commit dialog, detail panes, etc.) — so leave them in place. The modal-internal id rename means board CSS no longer styles this particular modal, but it continues to style the other consumers.

## Tests — `tests/test_sync_action_runner.py`

Pattern: `unittest.TestCase` per existing `tests/test_desync_state.py`.

Pure tests for `parse_sync_output()` (no subprocess, no Textual import — just `from sync_action_runner import parse_sync_output, STATUS_*`):

- `"SYNCED"` → `status==STATUS_SYNCED`
- `"PUSHED"`, `"PULLED"`, `"NOTHING"`, `"AUTOMERGED"`, `"NO_NETWORK"`, `"NO_REMOTE"` — each maps to its constant
- `"CONFLICT:a.md,b.md"` → `status==STATUS_CONFLICT`, `conflicted_files==["a.md","b.md"]`
- `"CONFLICT:single.md"` → `conflicted_files==["single.md"]`
- `"CONFLICT:"` → `conflicted_files==[""]` (preserve current `"".split(",")` semantics)
- `"ERROR:something bad happened"` → `status==STATUS_ERROR`, `error_message=="something bad happened"`
- `""` → `status==STATUS_ERROR`, `error_message` mentions empty output
- `"UNKNOWN_STATUS\n"` → `status==STATUS_ERROR`, `error_message` includes the unknown line
- `"PUSHED\nextra debug noise\n"` → `status==STATUS_PUSHED` (only first line consulted)
- `"\n\nPUSHED\n"` → `status==STATUS_PUSHED` (leading blank lines stripped)
- `"  PUSHED  "` → `status==STATUS_PUSHED` (whitespace trim)

`run_sync_batch()` is NOT tested via subprocess in this file — that would need a fixture script and crosses the unit boundary. The parser carries the meaningful coverage.

Header path setup (mirroring `tests/test_desync_state.py:13-16`):

```python
PROJECT_DIR = Path(__file__).resolve().parents[1]
LIB_SRC = PROJECT_DIR / ".aitask-scripts" / "lib"
sys.path.insert(0, str(LIB_SRC))
from sync_action_runner import parse_sync_output, ...
```

## Verification (Step 8 review checklist)

- `python3 -m py_compile .aitask-scripts/lib/sync_action_runner.py`
- `python3 -m py_compile .aitask-scripts/board/aitask_board.py`
- `python3 tests/test_sync_action_runner.py` — all 11+ parser cases pass
- `git diff --stat .aitask-scripts/board/aitask_board.py` confirms ~70-90 lines net removed (the import block adds a few lines back)
- Manual `./ait board` in tmux:
  1. Press the manual sync key (or trigger `action_sync_remote`) — `LoadingOverlay` appears, then notification fires (`Sync: Pushed` / `Sync: Pulled` / `Already up to date` / etc.).
  2. Force a CONFLICT (e.g., dirty `.aitask-data` with remote ahead of local on a conflicting file): `LoadingOverlay` pops cleanly, then `SyncConflictScreen` opens with the conflicted files listed.
  3. Click "Resolve Interactively" → terminal spawns running `./ait sync` (or app suspends + interactive sync runs in-place if no terminal). After exit, board reloads.
  4. Click "Dismiss" → modal closes, board reloads without invoking interactive sync.
  5. Trigger sync via timer auto-refresh path (set `sync_on_refresh: true`) — silent path runs without notification, no overlay.
  6. Trigger sync via post-rename path (line 5155) — sync runs, no overlay (rename overlay was already popped at 5152), notification fires.

## Out of scope

- Adding the syncer caller (that is **t713_3** — it will land after this task and consume the shared module).
- Changing `aitask_sync.sh` itself.
- Any UX changes to the board's sync flow beyond the import-path swap and the `_run_interactive_sync_shared` rename.
- Updating other helpers (`agent_launch_utils.find_terminal`, etc.).

## Notes for sibling tasks

After this task lands, **t713_3** must:

- Update `depends:` from `[t713_2]` to `[t713_8]` (already done — current frontmatter shows `depends: [t713_8]`).
- Import the shared runner instead of re-implementing parsing/dialog/fallback:
  ```python
  from sync_action_runner import (
      SyncConflictScreen, run_sync_batch, run_interactive_sync, STATUS_*,
  )
  ```
- Limit its own scope to: action handlers in `syncer_app.py`, the agent escape hatch (genuinely new), and the `main` ref pull/push (also new — `aitask_sync.sh` only handles `aitask-data`).

## Reference: Step 9 (Post-Implementation)

After Step 8 commits land, the workflow proceeds to Step 9 (Post-Implementation):

- No worktree to clean up (working on current branch per `create_worktree: false`).
- `verify_build` (if configured in `aitasks/metadata/project_config.yaml`) runs.
- `./.aitask-scripts/aitask_archive.sh 713_8` archives the task and plan, releases the lock, removes from parent's `children_to_implement`, commits.
- `./ait git push` after archival.
