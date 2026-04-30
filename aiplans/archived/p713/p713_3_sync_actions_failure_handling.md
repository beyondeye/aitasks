---
Task: t713_3_sync_actions_failure_handling.md
Parent Task: aitasks/t713_ait_syncer_tui_for_remote_desync_tracking.md
Sibling Tasks: aitasks/t713/t713_4_tmux_switcher_monitor_integration.md, aitasks/t713/t713_5_permissions_and_config.md, aitasks/t713/t713_6_website_syncer_docs.md, aitasks/t713/t713_7_manual_verification_syncer_tui.md
Archived Sibling Plans: aiplans/archived/p713/p713_1_desync_state_helper.md, aiplans/archived/p713/p713_2_syncer_entrypoint_and_tui.md, aiplans/archived/p713/p713_8_extract_sync_action_runner.md
Worktree: (none — current branch per profile 'fast')
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-30 14:33
---

## Context

Parent **t713** ships an `ait syncer` TUI that surfaces remote desync state for the project's `main` and `aitask-data` refs. Siblings already shipped:

- **t713_1** — `lib/desync_state.py` (data helper).
- **t713_2** — `aitask_syncer.sh` + `syncer/syncer_app.py` (entrypoint + read-only TUI shell with polling).
- **t713_8** — `lib/sync_action_runner.py` (shared `run_sync_batch`, `parse_sync_output`, `SyncConflictScreen`, `run_interactive_sync`, status constants), refactored from board.

This child wires the **sync / pull / push** actions onto the syncer rows and adds a code-agent escape hatch for failed operations. It must reuse the t713_8 module verbatim for `aitask-data` (no parsing duplication) and add a small set of new pieces:

- A separate code path for `main` (the shared `run_sync_batch` is `aitask_sync.sh`-specific and only handles `aitask-data`).
- A failure-summary modal that wraps the AgentCommandScreen launch.

The previous plan was written before t713_8 landed — this revision swaps the "shell out + parse" body for shared-module imports and pins down the `main` and escape-hatch designs.

## Verified assumptions

- `lib/sync_action_runner.py` exposes: `SyncResult`, `parse_sync_output`, `run_sync_batch(timeout=…)`, `SyncConflictScreen`, `run_interactive_sync(app, on_done=…)`, plus `STATUS_SYNCED|PUSHED|PULLED|NOTHING|AUTOMERGED|CONFLICT|NO_NETWORK|NO_REMOTE|ERROR|TIMEOUT|NOT_FOUND`. Both `lib/` and `syncer/` already prepend `…/lib` to `sys.path` (`syncer_app.py:19`).
- `lib/agent_launch_utils.py` exposes `find_terminal`, `launch_in_tmux`, `TmuxLaunchConfig`, `maybe_spawn_minimonitor`, `resolve_agent_string`, `resolve_dry_run_command`.
- `lib/agent_command_screen.py` `AgentCommandScreen` is the canonical Direct/tmux destination picker (board uses it for pick / explore at `aitask_board.py:3886, 3987, 4028, 4169`).
- `aitask_codeagent.sh` supports an `invoke raw "<prompt>"` operation (`SUPPORTED_OPERATIONS=(pick explain batch-review qa explore raw)`). `resolve_dry_run_command(Path("."), "raw", prompt)` returns the resolved CLI invocation string for AgentCommandScreen.
- `aitask_companion_cleanup.sh` cleanup pattern: pane-scoped `pane-died` hook + remain-on-exit (CLAUDE.md "Companion pane auto-despawn"). For escape-hatch flows we **defer to AgentCommandScreen + maybe_spawn_minimonitor**, which already wires this pattern for tmux launches; no direct hook setup needed in this task.
- `desync_state.snapshot(refs, fetch)` returns `{"refs": [{"name", "worktree", "ahead", "behind", "status", …}]}`. `worktree` is the absolute path to use for git subprocess `cwd` (the repo root for `main`, `.aitask-data` for the data branch).
- Existing tests: `tests/test_sync.sh`, `tests/test_sync_action_runner.py` (parser unit), `tests/test_desync_state.py`. None of these import `syncer_app.py`.

## Decisions (confirmed with user)

- **Bindings:** `s` = sync (aitask-data only), `u` = pull (main only in v1), `p` = push (main only in v1), `a` = open escape hatch on the **last action's failure context**.
- **Main row v1:** Pull + Push, never auto-commit. Refuse dirty tree (pull) with explicit error.
- **Escape hatch UX:** Modal with the captured failure summary + "Launch agent to resolve" / "Dismiss" buttons. Clicking "Launch agent" dismisses and pushes `AgentCommandScreen` pre-filled with a `aitask_codeagent.sh invoke raw "<prompt>"` command — that screen owns destination selection (Direct vs tmux session/window) and the actual spawn.

## Implementation

### 1. New module — `.aitask-scripts/syncer/sync_failure_screen.py`

A focused Textual `ModalScreen` for surfacing a single failed sync action, with two buttons.

```python
"""sync_failure_screen — Failure summary modal for the syncer TUI."""
from __future__ import annotations
from dataclasses import dataclass
from textual import on
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


@dataclass
class SyncFailureContext:
    ref_name: str          # "main" | "aitask-data"
    action: str            # "pull" | "push" | "sync"
    command: str           # human-readable command summary
    status: str            # short status keyword
    stderr_tail: str       # last ~30 lines of stderr+stdout
    raw_output: str = ""   # full captured output for diagnostics


class SyncFailureScreen(ModalScreen):
    """Shows a sync-action failure with options to launch an agent or dismiss."""

    DEFAULT_CSS = """
    #sync_failure_dialog { width: 80%; max-height: 80%; background: $surface;
        border: thick $error; padding: 1 2; }
    #sync_failure_title { text-align: center; padding: 0 0 1 0; text-style: bold; }
    #sync_failure_body { padding: 0 1; height: auto; max-height: 20; }
    #sync_failure_buttons { dock: bottom; height: 3; align: center middle; }
    """
    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, ctx: SyncFailureContext):
        super().__init__()
        self.ctx = ctx

    def compose(self):
        with Container(id="sync_failure_dialog"):
            yield Label(f"Sync action failed: {self.ctx.action} on {self.ctx.ref_name}",
                        id="sync_failure_title")
            with VerticalScroll(id="sync_failure_body"):
                yield Static(
                    f"[b]Branch:[/b] {self.ctx.ref_name}\n"
                    f"[b]Command:[/b] {self.ctx.command}\n"
                    f"[b]Status:[/b] {self.ctx.status}\n\n"
                    f"[b]Output (tail):[/b]\n{self.ctx.stderr_tail or '(empty)'}"
                )
            with Horizontal(id="sync_failure_buttons"):
                yield Button("Launch agent to resolve", variant="warning",
                             id="btn_failure_launch")
                yield Button("Dismiss", variant="default", id="btn_failure_dismiss")

    @on(Button.Pressed, "#btn_failure_launch")
    def launch(self): self.dismiss(True)

    @on(Button.Pressed, "#btn_failure_dismiss")
    def dismiss_dialog(self): self.dismiss(False)

    def action_cancel(self): self.dismiss(False)
```

### 2. `syncer/syncer_app.py` — additions

#### 2.1 New imports (after line 27)

```python
from textual.binding import Binding  # already present
from agent_launch_utils import (  # noqa: E402
    TmuxLaunchConfig, launch_in_tmux, maybe_spawn_minimonitor,
    resolve_agent_string, resolve_dry_run_command,
)
from agent_command_screen import AgentCommandScreen  # noqa: E402
from sync_action_runner import (  # noqa: E402
    SyncConflictScreen, run_sync_batch, run_interactive_sync,
    STATUS_AUTOMERGED, STATUS_CONFLICT, STATUS_ERROR,
    STATUS_NO_NETWORK, STATUS_NO_REMOTE, STATUS_NOT_FOUND,
    STATUS_NOTHING, STATUS_PULLED, STATUS_PUSHED,
    STATUS_SYNCED, STATUS_TIMEOUT,
)
from sync_failure_screen import SyncFailureScreen, SyncFailureContext  # noqa: E402
import subprocess  # noqa: E402
from pathlib import Path  # already present
```

#### 2.2 `BINDINGS` additions

Append to the existing list (preserve `j`/`r`/`f`/`q`):

```python
Binding("s", "sync_data", "Sync (aitask-data)"),
Binding("u", "pull", "Pull"),
Binding("p", "push", "Push"),
Binding("a", "agent_resolve", "Resolve with agent", show=False),
```

`show=False` on `a` keeps the footer uncluttered until a failure occurs; the user only needs it after the SyncFailureScreen surfaces it implicitly. The button in the modal is the discoverable surface.

#### 2.3 `__init__` — add failure-context cache

```python
self._last_failure: SyncFailureContext | None = None
```

#### 2.4 Action handlers — guard on selected ref then dispatch

```python
def action_sync_data(self) -> None:
    name = self._selected_ref_name()
    if name != "aitask-data":
        self.notify("Sync (s) is for aitask-data only — use u/p for main.",
                    severity="warning")
        return
    self._sync_data_worker()

def action_pull(self) -> None:
    name = self._selected_ref_name()
    if name != "main":
        self.notify("Pull (u) is wired for main only — use s to sync aitask-data.",
                    severity="warning")
        return
    self._main_pull_worker()

def action_push(self) -> None:
    name = self._selected_ref_name()
    if name != "main":
        self.notify("Push (p) is wired for main only — use s to sync aitask-data.",
                    severity="warning")
        return
    self._main_push_worker()

def action_agent_resolve(self) -> None:
    if self._last_failure is None:
        self.notify("No recent failure to resolve.", severity="information")
        return
    self._open_failure_screen(self._last_failure)
```

#### 2.5 aitask-data sync worker — wraps `run_sync_batch`

```python
@work(thread=True, exclusive=True, group="syncer-action")
def _sync_data_worker(self) -> None:
    result = run_sync_batch()
    status = result.status
    self.call_from_thread(self._on_data_sync_done, result, status)

def _on_data_sync_done(self, result, status: str) -> None:
    if status == STATUS_CONFLICT:
        self.push_screen(
            SyncConflictScreen(result.conflicted_files),
            self._on_conflict_resolved,
        )
        return
    if status == STATUS_TIMEOUT:
        self._capture_failure("aitask-data", "sync",
                              "./.aitask-scripts/aitask_sync.sh --batch",
                              status, result.error_message or "timeout",
                              result.raw_output)
        self.notify("Sync timed out", severity="warning")
        return
    if status == STATUS_NOT_FOUND:
        self.notify("Sync script not found", severity="error")
        return
    if status == STATUS_ERROR:
        self._capture_failure("aitask-data", "sync",
                              "./.aitask-scripts/aitask_sync.sh --batch",
                              status, result.error_message or "",
                              result.raw_output)
        self.notify(f"Sync error: {result.error_message}", severity="error")
        # Fall through to refresh below
    elif status == STATUS_NO_NETWORK:
        self.notify("Sync: No network", severity="warning")
    elif status == STATUS_NO_REMOTE:
        self.notify("Sync: No remote configured", severity="warning")
    elif status == STATUS_NOTHING:
        self.notify("Already up to date", severity="information")
    elif status == STATUS_AUTOMERGED:
        self.notify("Sync: Auto-merged conflicts", severity="information")
    elif status in (STATUS_PUSHED, STATUS_PULLED, STATUS_SYNCED):
        self.notify(f"Sync: {status.capitalize()}", severity="information")

    self.action_refresh()  # refresh snapshot regardless

def _on_conflict_resolved(self, resolve: bool) -> None:
    if resolve:
        self._run_interactive_sync_shared()
    self.action_refresh()

@work(exclusive=True, group="syncer-action")
async def _run_interactive_sync_shared(self) -> None:
    run_interactive_sync(self.app, on_done=lambda: self.call_from_thread(self.action_refresh))
```

Notification wording mirrors board's `_run_sync` verbatim (CLAUDE.md "preserve existing user-facing outcomes"). `_capture_failure` stores a `SyncFailureContext` on `self._last_failure` so the user can press `a` later.

#### 2.6 main pull / push workers

`main` is not handled by `aitask_sync.sh`. Drive `git` directly inside the `main` worktree.

```python
GIT_TIMEOUT = 30  # wall-clock cap, parallel to DEFAULT_SYNC_TIMEOUT_SECONDS

def _main_worktree(self) -> str | None:
    ref = self._find_ref("main")
    return ref.get("worktree") if ref else None

def _git(self, args: list[str], cwd: str) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(["git", *args], capture_output=True, text=True,
                              cwd=cwd, timeout=GIT_TIMEOUT)
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"git timed out after {GIT_TIMEOUT}s"

@work(thread=True, exclusive=True, group="syncer-action")
def _main_pull_worker(self) -> None:
    cwd = self._main_worktree()
    if not cwd:
        self.call_from_thread(self.notify, "main worktree not available", severity="error")
        return

    # Pre-checks: HEAD is main + clean working tree.
    rc, head, _ = self._git(["rev-parse", "--abbrev-ref", "HEAD"], cwd)
    if rc != 0 or head.strip() != "main":
        self.call_from_thread(self.notify,
            f"Switch to main to pull (currently on {head.strip() or '?'}).",
            severity="warning")
        return
    rc, status_out, _ = self._git(["status", "--porcelain"], cwd)
    if rc == 0 and status_out.strip():
        self.call_from_thread(self.notify,
            "Working tree dirty — stash or commit before pulling.",
            severity="warning")
        return

    rc, out, err = self._git(["pull", "--ff-only"], cwd)
    cmd = "git -C <main> pull --ff-only"
    if rc != 0:
        tail = "\n".join((err or out).splitlines()[-30:])
        self.call_from_thread(self._fail, "main", "pull", cmd, "ERROR", tail, out + err)
        return
    self.call_from_thread(self.notify, "main: Pulled.", severity="information")
    self.call_from_thread(self.action_refresh)

@work(thread=True, exclusive=True, group="syncer-action")
def _main_push_worker(self) -> None:
    cwd = self._main_worktree()
    if not cwd:
        self.call_from_thread(self.notify, "main worktree not available", severity="error")
        return
    rc, out, err = self._git(["push", "origin", "main:main"], cwd)
    cmd = "git -C <main> push origin main:main"
    if rc != 0:
        tail = "\n".join((err or out).splitlines()[-30:])
        self.call_from_thread(self._fail, "main", "push", cmd, "ERROR", tail, out + err)
        return
    self.call_from_thread(self.notify, "main: Pushed.", severity="information")
    self.call_from_thread(self.action_refresh)
```

#### 2.7 Failure capture + screen flow

```python
def _capture_failure(self, ref_name, action, command, status, stderr_tail, raw_output):
    self._last_failure = SyncFailureContext(
        ref_name=ref_name, action=action, command=command,
        status=status, stderr_tail=stderr_tail, raw_output=raw_output,
    )

def _fail(self, ref_name, action, command, status, stderr_tail, raw_output):
    """UI-thread helper: capture + push the SyncFailureScreen."""
    self._capture_failure(ref_name, action, command, status, stderr_tail, raw_output)
    self._open_failure_screen(self._last_failure)

def _open_failure_screen(self, ctx: SyncFailureContext) -> None:
    def on_choice(launch: bool) -> None:
        if launch:
            self._launch_resolution_agent(ctx)
    self.push_screen(SyncFailureScreen(ctx), on_choice)

def _launch_resolution_agent(self, ctx: SyncFailureContext) -> None:
    prompt = (
        f"A sync action failed in the ait syncer TUI. Please investigate and "
        f"resolve interactively with the user.\n\n"
        f"Branch: {ctx.ref_name}\n"
        f"Action: {ctx.action}\n"
        f"Command: {ctx.command}\n"
        f"Status: {ctx.status}\n\n"
        f"Output (tail):\n{ctx.stderr_tail or '(empty)'}\n"
    )
    full_cmd = resolve_dry_run_command(Path("."), "raw", prompt)
    if not full_cmd:
        self.notify("Could not resolve agent command — check model configuration.",
                    severity="error")
        return
    agent_string = resolve_agent_string(Path("."), "raw")
    screen = AgentCommandScreen(
        title=f"Resolve {ctx.action} failure on {ctx.ref_name}",
        full_command=full_cmd,
        prompt_str=prompt,
        default_window_name=f"agent-syncfix-{ctx.ref_name}",
        project_root=Path("."),
        operation="raw",
        operation_args=[prompt],
        default_agent_string=agent_string,
    )
    def on_launch(result):
        if isinstance(result, TmuxLaunchConfig):
            _, err = launch_in_tmux(screen.full_command, result)
            if err:
                self.notify(err, severity="error")
            elif result.new_window:
                maybe_spawn_minimonitor(result.session, result.window)
        # Direct ("run") path is handled by AgentCommandScreen itself via terminal.
        self.action_refresh()
    self.push_screen(screen, on_launch)
```

`AgentCommandScreen` already attaches the `pane-died` companion cleanup wiring through `maybe_spawn_minimonitor` for `new_window=True` launches; we do not duplicate the hook setup here (CLAUDE.md companion-pane rule).

#### 2.8 Snapshot refresh after every action

Each action handler ends in `self.action_refresh()` (already called in the workers above). The polling timer continues unchanged. No additional changes needed.

### 3. No changes required outside `syncer/`

- `aitask_sync.sh`: unchanged.
- `aitask_codeagent.sh`: unchanged — `raw` already supported.
- `lib/sync_action_runner.py`: unchanged — interface used as-is.
- `lib/desync_state.py`: unchanged.
- `ait`: unchanged.

## Files to add or modify

- **Add** `.aitask-scripts/syncer/sync_failure_screen.py` — `SyncFailureScreen` modal + `SyncFailureContext` dataclass (~80 LOC).
- **Modify** `.aitask-scripts/syncer/syncer_app.py` — imports, bindings, `__init__` field, action handlers, workers, failure flow (~180 LOC added).

## Out of scope (handled by siblings)

- `tui_registry.py` registration / switcher hotkey / monitor & minimonitor desync line / `tmux.syncer.autostart` → **t713_4**.
- 5-touchpoint helper-script whitelist + project_config defaults → **t713_5**.
- User-facing website docs → **t713_6**.
- Aggregate manual verification → **t713_7**.

## Verification

### Automated

- `python3 -m py_compile .aitask-scripts/syncer/sync_failure_screen.py`
- `python3 -m py_compile .aitask-scripts/syncer/syncer_app.py`
- `bash tests/test_sync.sh` — ensures `aitask_sync.sh --batch` semantics still hold (no changes to that script, but guards against regression).
- `python3 tests/test_sync_action_runner.py` — parser unit tests (no changes to that module either; sanity).
- `python3 tests/test_desync_state.py` — confirms snapshot contract still holds.

### Manual (TUI smoke pass; covered as the manual-verification checklist for sibling t713_7)

1. `./ait syncer` opens; both rows render.
2. Press `s` on `main` row → notification "Sync (s) is for aitask-data only…".
3. Press `s` on `aitask-data` row when up-to-date → "Already up to date" notification; row refreshes.
4. Force a non-conflicting `aitask-data` change on origin (push from a scratch clone, then back here) → press `s` → "Sync: Pulled" / row updates ahead/behind.
5. Force a `aitask-data` conflict (touch the same file in scratch clone and locally) → press `s` → `SyncConflictScreen` modal opens with the conflicted files. "Resolve Interactively" → terminal spawns running `./ait sync` (or app suspends if no terminal). After resolve, row refreshes.
6. On `main` row with a clean tree on `main` HEAD → press `u` → fast-forward pull, "main: Pulled." notification.
7. On `main` row, dirty tree → press `u` → refusal notification with stash hint; no git command run.
8. On `main` row, off-main HEAD → press `u` → refusal notification with switch hint.
9. On `main` row → press `p` → push runs, notification on success.
10. Force a non-fast-forward push (rebase main locally, don't push) → press `p` → `SyncFailureScreen` opens with `git push` stderr tail and "Launch agent to resolve" / "Dismiss" buttons.
11. Click "Launch agent to resolve" → `AgentCommandScreen` opens with the resolution prompt pre-filled. Pick a destination → agent spawns; companion minimonitor accompanies if launched in a new tmux window.
12. Click "Dismiss" instead → modal closes; press `a` later → same `SyncFailureScreen` reopens (last-failure cache).
13. Press `r` (existing refresh) anywhere → snapshot refresh works as before.

## Reference: Step 9 (Post-Implementation)

After Step 8 commits land:

- No worktree to clean up (current branch per `create_worktree: false`).
- `verify_build` (if configured in `aitasks/metadata/project_config.yaml`) runs.
- `./.aitask-scripts/aitask_archive.sh 713_3` archives the task and plan, releases the lock, removes from parent's `children_to_implement`, commits.
- `./ait git push` after archival.

## Notes for sibling tasks

- **t713_4** (switcher / monitor / autostart): `_last_failure` is a per-app field; no cross-TUI signaling is in this task. If t713_4 wants the monitor/minimonitor desync line to flag "syncer has a pending failure", a tiny helper file in `.aitask-data/` or a tmux user-event would be cleaner than coupling to the syncer process — out of scope here.
- **t713_5** (whitelist + config): no new scripts in this task, so no new whitelist touchpoints — only `aitask_syncer.sh` (added by t713_2) needs the 5-touchpoint pass that t713_5 owns.
- **t713_6** (docs): document `s/u/p/a` bindings in the syncer docs once t713_4 has finalized the registry/switcher hotkey.
- **t713_7** (manual verification): the verification list in this plan's "Manual" section is the candidate checklist content for the aggregate verification task.

## Final Implementation Notes

- **Actual work done:**
  - Added `.aitask-scripts/syncer/sync_failure_screen.py` (~90 LOC): `SyncFailureContext` dataclass and `SyncFailureScreen(ModalScreen)` with branch / command / status / output-tail body and "Launch agent to resolve" / "Dismiss" buttons. Self-contained `DEFAULT_CSS` (`#sync_failure_dialog` etc.) so the modal renders correctly under the syncer app.
  - Modified `.aitask-scripts/syncer/syncer_app.py` (+290 LOC, no removals): added imports for `agent_launch_utils`, `agent_command_screen`, `sync_action_runner` (`run_sync_batch`, `run_interactive_sync`, `SyncConflictScreen`, `SyncResult`, all `STATUS_*`), and the new `sync_failure_screen` module; appended a per-syncer-dir entry to `sys.path` so the modal import resolves; added `subprocess` to the stdlib imports and two new module-scope constants (`GIT_TIMEOUT_SECONDS=30`, `FAILURE_TAIL_LINES=30`); added four bindings (`s` sync-data, `u` pull, `p` push, `a` agent-resolve with `show=False`); added `_last_failure` field on `__init__`; added action handlers `action_sync_data`/`action_pull`/`action_push`/`action_agent_resolve` (each guards on the selected ref name and notifies on row-mismatch rather than running cross-row by accident); added `_sync_data_worker` (`@work(thread=True, exclusive=True, group="syncer-action")`) that calls `run_sync_batch()` then dispatches via `_on_data_sync_done` (notifications mirror board's `_run_sync` wording verbatim, conflict path delegates to `SyncConflictScreen` + `_on_conflict_resolved` + `_run_interactive_sync_shared`); added `_main_pull_worker` and `_main_push_worker` (direct `git -C <main_worktree>` subprocess with a 30s timeout and a `_git()` helper, pull guards on HEAD==`main` + clean tree, push uses `push origin main:main` so it works regardless of HEAD); failure capture flow `_capture_failure` / `_fail` / `_open_failure_screen` / `_launch_resolution_agent` builds a prompt for `aitask_codeagent.sh invoke raw` via `resolve_dry_run_command`, then pushes `AgentCommandScreen` with the resolved command/prompt; `on_launch` callback dispatches `launch_in_tmux` + `maybe_spawn_minimonitor` for tmux destinations.
- **Deviations from plan:**
  - Added `sys.path.insert(0, str(Path(__file__).resolve().parent))` so the new `sync_failure_screen` import resolves regardless of how the app is launched. The plan didn't explicitly call this out; without it the import fails when `syncer_app.py` runs as a script.
  - Imported `SyncResult` from `sync_action_runner` for the `_on_data_sync_done` type hint — plan didn't list it but it's part of the same module.
- **Issues encountered:**
  - The repo had pre-existing untracked files (`os`, `shutil`, `subprocess`, `time`, `unittest` — 50MB PostScript artifacts from an unrelated session) and unrelated `.sh` modifications (`require_ait_python` → `require_ait_python_fast`). All left untouched; only t713_3 files staged for commit.
- **Key decisions:**
  - `a` binding has `show=False` so it doesn't clutter the footer until the user actually has a failure to recover from. The button inside `SyncFailureScreen` is the primary discoverable path; `a` is a power-user shortcut to reopen the last-failure modal after dismissing it.
  - Notification wording for the aitask-data sync path mirrors `BoardApp._run_sync` verbatim ("Already up to date", "Sync: Pulled.", "Sync: Auto-merged conflicts", etc.) per CLAUDE.md "preserve existing user-facing outcomes". The two TUIs now report identical sync results.
  - `main` push uses `git push origin main:main` so it works without checking out main (compatible with users who keep a feature branch checked out). Pull, by contrast, modifies the working tree, so it requires HEAD==`main` + clean status — refused with explicit user-actionable error otherwise. Never auto-commits, per task acceptance.
  - The failure escape hatch is a two-modal flow: `SyncFailureScreen` (this task's new modal, summary + intent capture) → `AgentCommandScreen` (existing reusable, destination + agent picker). Clean separation of concerns: this task owns the failure summary; the destination dialog is reused as-is.
  - `sync_action_runner.STATUS_NOT_FOUND` is treated as a hard error (no failure-context capture, no agent escape hatch) — if `aitask_sync.sh` is missing the install is broken and an LLM agent can't fix that.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - **t713_4** (registry/switcher/monitor): When wiring the desync line into monitor/minimonitor, prefer reading `desync_state.snapshot()` directly rather than coupling to the syncer process. The `_last_failure` field is per-app and intentionally not surfaced cross-process.
  - **t713_5** (whitelist + config): This task added no new helper scripts — only Python modules under `.aitask-scripts/syncer/`. No new whitelist touchpoints needed for this task. `aitask_syncer.sh` (added in t713_2) remains the only syncer-domain wrapper that t713_5 must whitelist.
  - **t713_6** (docs): Document `s` (sync aitask-data), `u`/`p` (pull/push main), and the failure-modal escape hatch. The `a` key is intentionally undocumented in the footer; mention it in the docs as a "press a to reopen the last failure" shortcut after the user has seen at least one failure.
  - **t713_7** (manual verification): The "Manual" section of this plan is ready-to-use as the aggregate checklist content. The two scratch-repo scenarios (force a `aitask-data` conflict and a non-fast-forward `main` push) are the load-bearing checks; everything else is a row-guard or mode-switch sanity test.
- **Verification:**
  - `python3 -m py_compile .aitask-scripts/syncer/sync_failure_screen.py` ✅
  - `python3 -m py_compile .aitask-scripts/syncer/syncer_app.py` ✅
  - `python3 tests/test_sync_action_runner.py` — 18/18 ✅
  - `python3 tests/test_desync_state.py` — 5/5 ✅
  - `bash tests/test_sync.sh` — 34/34 ✅
  - Smoke test importing `SyncerApp` and inspecting `BINDINGS` returned the expected `[j, r, s, u, p, a, f, q]` order; constructing `SyncFailureContext` works.
  - `./ait syncer --help` still renders the original argparse help unchanged.
  - End-to-end TUI runs (real conflict / non-fast-forward) deferred to sibling t713_7 per its manual-verification scope.
