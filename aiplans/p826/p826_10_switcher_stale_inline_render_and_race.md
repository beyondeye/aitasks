---
Task: t826_10_switcher_stale_inline_render_and_race.md
Parent Task: aitasks/t826_brainstorm_cross_repo_project_references.md
Sibling Tasks: aitasks/t826/t826_3_*.md, aitasks/t826/t826_4_*.md
Archived Sibling Plans: aiplans/archived/p826/p826_1_*.md, p826_2_*.md, p826_5_*.md, p826_6_*.md, p826_7_*.md, p826_8_*.md, p826_9_*.md
Base branch: main
---

# Plan: TUI switcher inline render + race handling for STALE registry entries (t826_10)

## Context

This is the user-facing payoff of the t826_5 brainstorm. The previous
siblings already shipped:

- `_read_registry_index()` and `discover_aitasks_sessions(include_registered=True)`
  surface STALE registry entries as `AitasksSession(is_live=False, is_stale=True)`
  rows (t826_6).
- `ait projects remove`/`update` atomic verbs the modal can shell out to (t826_7).
- `cmd_prune` and `cmd_doctor` CLI flows (parallel — not consumed here, t826_8/9).
- `spawn_session_detached <project_root>` already exits non-zero with a
  human-readable stderr line when the marker file is missing (t826_2,
  `tmux_bootstrap.sh:137-139`).

Currently the switcher renders STALE entries with the same styling as
LIVE/OK entries because `_render_session_row` ignores `is_stale`, and
clicking one bottoms out in `_ensure_session_live → spawn_session_detached`
with a generic "Failed to bootstrap session" notification — no path to
fix the registry from the TUI.

This task wires STALE awareness into:

1. The Session: row rendering (dimmed, `(stale)` suffix).
2. A new `StaleEntryModal` that offers Prune / Repoint / Cancel and
   refreshes the cached session list after a successful mutation.
3. Pre-spawn selection guard so picking a STALE entry pushes the modal
   *before* the bootstrap subprocess runs.
4. Structured-stderr detection in `_ensure_session_live` so the same
   modal pops up for entries that turn STALE between switcher mount and
   user action (race-condition path).

The bootstrap helper already exits non-zero on a missing marker; we add
a structured `BOOTSTRAP_FAILED:stale_path` sentinel on the helper side
so the switcher can recognise the race-condition failure mode and route
it to the modal instead of a flat error notification.

## Key Files to Modify

- `.aitask-scripts/lib/tui_switcher.py` — `_render_session_row` (~line
  544), pre-spawn guard inserted at the top of `_switch_to`,
  `action_shortcut_explore`, `action_shortcut_create`; structured
  failure detection in `_ensure_session_live`.
- `.aitask-scripts/lib/stale_entry_modal.py` — **new** modal file.
- `.aitask-scripts/lib/tmux_bootstrap.sh` — replace the generic
  "not an aitasks project" stderr line in `spawn_session_detached`
  with `BOOTSTRAP_FAILED:stale_path` followed by a human-readable
  detail line; bump the exit code to `42` so the switcher can also
  detect it positionally if it ever needs to.

## Implementation Plan

### Step 1 — Emit structured failure marker in `tmux_bootstrap.sh`

`.aitask-scripts/lib/tmux_bootstrap.sh:137-139` currently does:

```bash
if [[ ! -f "$root/aitasks/metadata/project_config.yaml" ]]; then
    echo "spawn_session_detached: not an aitasks project: $root" >&2
    return 2
fi
```

Replace with a marker line *plus* the existing human-readable detail
so casual users running the standalone CLI still see what went wrong:

```bash
if [[ ! -f "$root/aitasks/metadata/project_config.yaml" ]]; then
    echo "BOOTSTRAP_FAILED:stale_path" >&2
    echo "spawn_session_detached: not an aitasks project: $root" >&2
    return 42
fi
```

`42` is a distinct non-zero so a positional check (if needed) is
unambiguous, but the switcher reads stderr — exit code is informational.
Leave the `not a directory` branch (`return 2`) and missing-root branch
(`return 2`) untouched: they are pre-existing argument-validation
failures, not stale-path drift.

### Step 2 — `StaleEntryModal` (`lib/stale_entry_modal.py`)

New file. Self-contained `DEFAULT_CSS` (per memory
`feedback_modal_self_contained_css`: modals in `lib/` are pushed by
multiple Apps and cannot rely on App-level CSS).

```python
"""stale_entry_modal - Modal for prune/repoint of a STALE registry entry.

Pushed by tui_switcher when the user activates a registry entry whose
project root no longer holds the aitasks/metadata/project_config.yaml
marker — either selected directly from the switcher's Session: row or
detected after a `spawn_session_detached` BOOTSTRAP_FAILED:stale_path
race signal.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class RegistryRefresh(Message):
    """Posted by StaleEntryModal after a successful prune/repoint so the
    parent overlay can re-run discover_aitasks_sessions() and rebuild
    the Session: row."""


class _RepointInputScreen(ModalScreen):
    """Tiny text-input modal pushed by StaleEntryModal on Repoint."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    DEFAULT_CSS = """
    #repoint_dialog {
        width: 70;
        height: 9;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #repoint_title { text-align: center; padding: 0 0 1 0; }
    #repoint_buttons { height: 3; align: center middle; }
    #repoint_buttons Button { margin: 0 1; }
    """

    def __init__(self, name: str, current_path: str) -> None:
        super().__init__()
        self._name = name
        self._current_path = current_path

    def compose(self) -> ComposeResult:
        with Container(id="repoint_dialog"):
            yield Label(
                f"Repoint [bold]{self._name}[/]\n[dim]{self._current_path}[/]",
                id="repoint_title",
            )
            yield Input(placeholder="New project path", id="repoint_input")
            with Horizontal(id="repoint_buttons"):
                yield Button("OK", variant="success", id="btn_repoint_ok")
                yield Button("Cancel", variant="default", id="btn_repoint_cancel")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    @on(Button.Pressed, "#btn_repoint_ok")
    def _submit(self) -> None:
        val = self.query_one("#repoint_input", Input).value.strip()
        self.dismiss(val or None)

    @on(Button.Pressed, "#btn_repoint_cancel")
    def _cancel(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class StaleEntryModal(ModalScreen):
    """Prune / Repoint / Cancel modal for a STALE registry entry."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("p", "prune", "Prune", show=False),
        Binding("r", "repoint", "Repoint", show=False),
        Binding("c", "cancel", "Cancel", show=False),
    ]

    DEFAULT_CSS = """
    StaleEntryModal { align: center middle; }
    #stale_dialog {
        width: 60;
        height: 13;
        background: $surface;
        border: thick $warning;
        padding: 1 2;
    }
    #stale_title {
        text-align: center;
        text-style: bold;
        padding: 0 0 1 0;
    }
    #stale_path {
        text-align: center;
        color: $text-muted;
        padding: 0 0 1 0;
    }
    #stale_actions {
        height: 3;
        align: center middle;
        padding: 1 0 0 0;
    }
    #stale_actions Button { margin: 0 1; }
    """

    # Module-level helper to locate aitask_projects.sh — resolved once so
    # tests that monkeypatch the path can override.
    PROJECTS_SH: str = str(
        Path(__file__).resolve().parent.parent / "aitask_projects.sh"
    )

    def __init__(self, name: str, project_root: Path) -> None:
        super().__init__()
        self._name = name
        self._project_root = project_root

    def compose(self) -> ComposeResult:
        with Container(id="stale_dialog"):
            yield Label(
                f"Stale registry entry: [bold]{self._name}[/]",
                id="stale_title",
            )
            yield Label(str(self._project_root), id="stale_path")
            with Horizontal(id="stale_actions"):
                yield Button("(P)rune", variant="error", id="btn_stale_prune")
                yield Button("(R)epoint", variant="primary", id="btn_stale_repoint")
                yield Button("(C)ancel", variant="default", id="btn_stale_cancel")

    # --- Actions --------------------------------------------------------

    def action_prune(self) -> None:
        self._do_prune()

    def action_repoint(self) -> None:
        self._do_repoint()

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#btn_stale_prune")
    def _on_prune(self) -> None:
        self._do_prune()

    @on(Button.Pressed, "#btn_stale_repoint")
    def _on_repoint(self) -> None:
        self._do_repoint()

    @on(Button.Pressed, "#btn_stale_cancel")
    def _on_cancel(self) -> None:
        self.dismiss(None)

    # --- Subprocess helpers --------------------------------------------

    def _do_prune(self) -> None:
        result = subprocess.run(
            [self.PROJECTS_SH, "remove", self._name, "--force"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            self.app.notify(
                f"Prune failed: {(result.stderr or '').strip() or 'unknown error'}",
                severity="error",
            )
            self.dismiss(None)
            return
        self.app.notify(f"Removed {self._name} from registry")
        self.post_message(RegistryRefresh())
        self.dismiss("pruned")

    def _do_repoint(self) -> None:
        self.app.push_screen(
            _RepointInputScreen(self._name, str(self._project_root)),
            callback=self._apply_repoint,
        )

    def _apply_repoint(self, new_path: str | None) -> None:
        if not new_path:
            return
        result = subprocess.run(
            [self.PROJECTS_SH, "update", self._name, new_path],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            self.app.notify(
                f"Repoint failed: {(result.stderr or '').strip() or 'unknown error'}",
                severity="error",
            )
            return
        self.app.notify(f"Repointed {self._name} → {new_path}")
        self.post_message(RegistryRefresh())
        self.dismiss("repointed")
```

**Design notes:**

- `RegistryRefresh` is a Textual `Message` posted *before* `dismiss()`
  so the parent overlay's handler fires after dismiss (Textual delivers
  messages on the next frame). The switcher's handler re-runs
  `discover_aitasks_sessions(include_registered=True)`, replaces
  `self._all_sessions`, then re-renders.
- `_RepointInputScreen` is intentionally minimal: a single Input + OK /
  Cancel. Submitting Enter on the Input triggers OK; Escape cancels.
  The text-input modal returns the typed path to the StaleEntryModal,
  which validates it via `aitask_projects.sh update` (`cmd_update`
  rejects missing-marker paths with a `die()` — the modal surfaces
  stderr verbatim).
- `PROJECTS_SH` is a class attribute (not a static path constant) so
  tests can monkeypatch it to a stub script. Resolved once at class-load
  via `Path(__file__).resolve().parent.parent / "aitask_projects.sh"`.
- The post-success state (`"pruned"` / `"repointed"`) is returned via
  `dismiss()` so the *caller* (switcher overlay) can branch on whether
  to retry the original spawn — pruned entries can't be retried, but
  repointed entries can.

### Step 3 — `tui_switcher.py` integration

#### 3a. Render STALE rows dimmed with `(stale)` suffix

`_render_session_row` (currently lines 536-560). Today the loop is:

```python
for s in self._all_sessions:
    name = s.session
    attached = name == self._attached_session
    selected = name == self._session
    prefix = "▶ " if attached else "  "
    if selected:
        parts.append(f"[reverse]{prefix}{name}[/]")
    else:
        parts.append(f"[dim]{prefix}{name}[/]")
```

Update to include the `(stale)` suffix on STALE entries, dimmed
regardless of selection (the `[reverse]` selection highlight still
fires but on the dimmed text — visually clear but not flashy):

```python
for s in self._all_sessions:
    name = s.session
    attached = name == self._attached_session
    selected = name == self._session
    prefix = "▶ " if attached else "  "
    suffix = " (stale)" if s.is_stale else ""
    label = f"{prefix}{name}{suffix}"
    if s.is_stale:
        # STALE rows render dimmed regardless of selection so the
        # status is unambiguous; selection still shows via reverse.
        if selected:
            parts.append(f"[reverse][dim]{label}[/][/]")
        else:
            parts.append(f"[dim]{label}[/]")
    elif selected:
        parts.append(f"[reverse]{label}[/]")
    else:
        parts.append(f"[dim]{label}[/]")
```

Brainstorm verification step 5 ("breakpoint when implementing — start
with a simple 'always show `(stale)` suffix, accept truncation'") is
respected: no width-constrained `✗` fallback, just truncation if the
row overflows the 44-column dialog.

#### 3b. Pre-spawn STALE guard

Add helper `_handle_stale_selection` to `TuiSwitcherOverlay`. It
returns `True` if the modal was pushed (caller short-circuits) and
`False` if the selected entry is not STALE:

```python
def _handle_stale_selection(self) -> bool:
    """If the SELECTED session is a STALE registry entry, push the
    StaleEntryModal and return True. Caller must NOT proceed with
    bootstrap/spawn when True.
    """
    idx = next(
        (i for i, s in enumerate(self._all_sessions)
         if s.session == self._session),
        None,
    )
    if idx is None:
        return False
    entry = self._all_sessions[idx]
    if not entry.is_stale:
        return False
    self._push_stale_modal(entry.project_name, entry.project_root)
    return True

def _push_stale_modal(self, name: str, project_root: Path) -> None:
    from stale_entry_modal import StaleEntryModal
    self.app.push_screen(StaleEntryModal(name, project_root))
```

Wire `_handle_stale_selection()` at the top of every spawn entry
point. Today `_ensure_session_live` is called at the top of
`_switch_to`, `action_shortcut_explore`, and `action_shortcut_create`;
the stale guard must run *before* it so we don't waste a subprocess
spawn just to discover the path is missing. Pattern:

```python
def _switch_to(self, name: str, running: bool,
               window_index: str | None = None) -> None:
    if self._handle_stale_selection():
        return
    if not self._ensure_session_live():
        return
    # ... existing body ...
```

Same insertion at the top of `action_shortcut_explore` and
`action_shortcut_create` (both already start with
`if not self._ensure_session_live(): return`).

#### 3c. Structured-failure detection in `_ensure_session_live`

Today the helper notifies on any non-zero exit. Extend it to recognise
the `BOOTSTRAP_FAILED:stale_path` marker and route to the same modal:

```python
if result.returncode != 0:
    stderr_text = (result.stderr or "").strip()
    if "BOOTSTRAP_FAILED:stale_path" in stderr_text:
        # Race: entry was OK at switcher mount but went STALE before
        # bootstrap. Push the modal for the user to prune/repoint
        # inline, same as the pre-spawn guard path.
        self._push_stale_modal(entry.project_name, entry.project_root)
        return False
    err = stderr_text.splitlines()[-1:] or ["unknown error"]
    self.app.notify(
        f"Failed to bootstrap session for {entry.project_name}: {err[0]}",
        severity="error",
    )
    return False
```

#### 3d. Registry refresh after prune/repoint

The modal posts a `RegistryRefresh` message before dismissing. Add a
message handler on the overlay:

```python
from stale_entry_modal import RegistryRefresh  # at top with other imports

def on_registry_refresh(self, event: RegistryRefresh) -> None:
    """Re-run session discovery and rebuild the Session: row after
    the modal mutates the registry."""
    event.stop()
    self._all_sessions = discover_aitasks_sessions(include_registered=True)
    # Selected session may have been removed (prune); fall back to attached.
    if not any(s.session == self._session for s in self._all_sessions):
        self._session = self._attached_session
    self._render_session_row()
    self._populate_list_for(self._session)
```

The import is gated to avoid a hard dependency cycle if
`stale_entry_modal.py` ever needs to import from `tui_switcher` (it
won't today, but the lazy-import inside `_push_stale_modal` already
covers it — the top-of-file `from stale_entry_modal import
RegistryRefresh` is fine because the modal file has no reverse
import).

### Step 4 — Tests

#### 4a. `tests/test_stale_entry_modal.py` (new)

Modeled on `tests/test_discover_include_registered.py`. Uses
`unittest.mock` to stub `subprocess.run` and validate the modal's
behavior without a Textual App.

Test cases:

1. **CSS self-containment** — instantiate `StaleEntryModal(name, root)`
   and assert `DEFAULT_CSS` contains `#stale_dialog`, `#stale_actions`,
   `Button`. Smoke-style test guarding the memory invariant
   (`feedback_modal_self_contained_css`).
2. **Prune action calls `aitask_projects.sh remove --force`** — stub
   `subprocess.run` to return `returncode=0`; call `modal._do_prune()`
   inside a Textual `App` test pump (or mock `self.app.notify` /
   `self.post_message` / `self.dismiss` directly). Assert the
   subprocess call's argv matches
   `[..., "remove", "<name>", "--force"]`.
3. **Repoint action calls `aitask_projects.sh update`** — same stub,
   call `modal._apply_repoint("/new/path")`. Assert argv matches
   `[..., "update", "<name>", "/new/path"]`.
4. **Cancel dismisses cleanly** — call `modal._on_cancel()`; assert
   `self.dismiss(None)` was called and no subprocess fired.
5. **Prune failure surfaces the stderr line** — stub `subprocess.run`
   to return `returncode=1, stderr="boom\n"`; call `_do_prune()`; assert
   `self.app.notify` was called with `"Prune failed: boom"` and severity
   `"error"`, and no `RegistryRefresh` was posted.
6. **Empty repoint input is a no-op** — call
   `modal._apply_repoint(None)`; assert no subprocess fired.

To exercise the message + dismiss flow without spinning up a full
Textual App, the test creates a `Mock(spec=StaleEntryModal)`-style
harness that monkeypatches `app`, `dismiss`, `post_message` on the
instance — Textual modals tolerate this pattern (seen in other lib
tests).

#### 4b. `tests/test_discover_include_registered.py` extension

Add a single assertion: when a registry entry with `project_name` X is
STALE AND a live entry with `project_name` X exists, the live entry
wins (already covered by
`test_live_entry_dedupes_registered_with_same_project_name` for OK
entries — add a parallel STALE variant to lock the same behavior so a
future regression in `discover_aitasks_sessions` doesn't surface STALE
ghosts beside a live entry).

#### 4c. Lint

`shellcheck .aitask-scripts/lib/tmux_bootstrap.sh` must remain clean
after the structured-marker edit.

### Step 5 — Manual verification

(Aggregate sibling t826_4 already exists for the t826 family; this
task's manual checklist items can be appended there or executed
ad-hoc against the live `aitasks` tmux session.)

1. **Render**: Add a fake registry entry pointing at `/tmp/nope`. Open
   `ait ide`, press `j`. Verify the Session: row shows the entry
   dimmed with `(stale)` suffix, no `▶` marker.
2. **Prune branch**: Cycle (Left/Right) onto the STALE entry, press
   any TUI shortcut (e.g. `b`). The `StaleEntryModal` opens. Press `p`
   (or click `(P)rune`). Verify the entry is removed from the
   registry (`ait projects list`), the modal dismisses, and the
   switcher's Session: row no longer contains it.
3. **Repoint branch**: Re-add a STALE entry (a registered name
   pointing at a missing path). Open the modal as above, press `r`,
   enter a real project path, submit. Verify the entry is repointed
   in the registry and the Session: row now shows it as a normal
   OK/inactive entry (no `(stale)` suffix).
4. **Race condition**: Open the switcher with an OK registered
   project visible. In another terminal, `rm` the project's
   `aitasks/metadata/project_config.yaml` (without closing the
   switcher). Without rebuilding the Session: row, press the entry's
   shortcut. Bootstrap subprocess fails with
   `BOOTSTRAP_FAILED:stale_path` and the same `StaleEntryModal` opens
   — confirming structured-stderr detection routes the race path to
   the same UX as the up-front guard.
5. **Cancel**: From any of the above paths, pressing Escape (or `c`
   / the Cancel button) closes the modal with no registry mutation.

## Out of Scope

- **`prune` / `doctor` CLI flows** — t826_8 / t826_9, archived.
- **Visual indicators for OK-but-inactive entries** — shipped in t826_2
  (no marker; activity implied by switch-vs-spawn).
- **Auto-clone integration in the modal** — clone stays a `doctor
  --clone` flow per brainstorm decision #3.
- **Width-constrained `(stale)` → `✗` glyph fallback** — accepted as
  truncation in the brainstorm verification note. Revisit only if a
  user reports overflow in a narrow pane.

## Verification

```bash
# New tests
python3 tests/test_stale_entry_modal.py
python3 tests/test_discover_include_registered.py

# Regression
python3 tests/test_discover_default_unchanged.py

# Lint
shellcheck .aitask-scripts/lib/tmux_bootstrap.sh

# Manual (Step 5 above)
```

## Step 9 reference

Follow shared workflow Step 9 after Step 8 approval. Profile `fast`
works on the current branch — no worktree to clean. Archival closes
t826_10 and leaves t826_3 / t826_4 as the remaining children of t826.

## Final Implementation Notes

- **Actual work done:** All 4 plan steps landed as designed.
  - **Step 1** — `spawn_session_detached` in `.aitask-scripts/lib/tmux_bootstrap.sh` now emits `BOOTSTRAP_FAILED:stale_path` on stderr (plus the existing human-readable detail) and exits 42 when the marker file is missing.
  - **Step 2** — New `.aitask-scripts/lib/stale_entry_modal.py` ships `StaleEntryModal` (Prune / Repoint / Cancel), `_RepointInputScreen` (text-input modal for the new path), and `RegistryRefresh` (Textual `Message`). All CSS is self-contained per the `feedback_modal_self_contained_css` memory. `PROJECTS_SH` is a class attribute so tests can override the path; both subprocess wrappers also catch `TimeoutExpired` / `FileNotFoundError` / `OSError` and surface them as notify-error messages.
  - **Step 3a** — `_render_session_row` in `tui_switcher.py` now dims STALE rows and appends ` (stale)`; selection still shows via `[reverse]` on the dimmed text.
  - **Step 3b** — `_handle_stale_selection` and `_push_stale_modal` helpers added; wired at the top of `_switch_to`, `action_shortcut_explore`, and `action_shortcut_create` so STALE selections short-circuit before any bootstrap subprocess runs.
  - **Step 3c** — `_ensure_session_live` now greps stderr for `BOOTSTRAP_FAILED:stale_path` and routes to the same modal (race-condition path).
  - **Step 3d** — `on_registry_refresh` re-runs `discover_aitasks_sessions(include_registered=True)`, falls back to the attached session if the selected entry got pruned, and re-renders both the Session row and the desync line + window list.
  - **Step 4a** — `tests/test_stale_entry_modal.py` (7 tests covering CSS self-containment, prune happy path, repoint happy path, cancel, prune failure, repoint failure keeps modal open, empty input no-op).
  - **Step 4b** — `tests/test_discover_include_registered.py` gained a STALE-by-name dedup regression next to the existing OK dedup test.

- **Deviations from plan:**
  - **Repoint failure does NOT dismiss the modal.** The plan's snippet returned without dismissing on subprocess failure (no explicit dismiss). The implementation explicitly leaves the modal open so the user can retry with a different path. Added as `test_repoint_failure_keeps_modal_open` to lock that behavior; the plan's test list (cases 1-6) becomes 7 with this addition.
  - **The pre-spawn guard pushes the modal without retry-after-repoint coordination.** The plan mused that the caller "can branch on whether to retry the original spawn — pruned entries can't be retried, but repointed entries can." Not implemented — after the modal returns, the overlay just refreshes the session list via `on_registry_refresh` and the user re-issues the action. Simpler and matches what the manual verification flow actually does.
  - **`mock.patch.object(StaleEntryModal, 'app', mock.Mock())` pattern in tests.** The plan said "monkeypatch app / dismiss / post_message on the instance"; `app` is a read-only property on Textual's `MessagePump`, so the test fixture patches it at the class level for the duration of each test instead. `dismiss` and `post_message` are regular methods and can be stubbed per-instance, which is what the harness does.

- **Issues encountered:**
  - First test pass failed on `modal.app = mock.Mock()` because `Screen.app` is a read-only property. Fixed by switching the fixture to `mock.patch.object(StaleEntryModal, 'app', ...)` in `setUp` / `tearDown`.
  - First STALE-dedup test asserted `len(result) == 1` but actually saw 2 entries — the live and registry side had different basenames (`shared` vs `shared_live_root`), so the dedup-by-`project_name` did not fire. Fixed by aligning the live project's directory basename to the registry name.

- **Key decisions:**
  - **Exit code 42 for the structured failure.** Distinct non-zero so a positional check is unambiguous if ever needed, but the switcher consumes the stderr sentinel — the exit code is informational. Pre-existing argument-validation failures (`return 2`) are untouched.
  - **Single sentinel for both the up-front guard and the race path.** The stale guard runs before the bootstrap subprocess; the structured-stderr detection only fires when the up-front guard missed (registry entry was OK at switcher mount but went STALE between mount and selection). Both paths converge on the same `_push_stale_modal` call, so the UX is uniform regardless of *when* the staleness was detected.
  - **No retry-after-repoint plumbing.** After a successful prune or repoint, `on_registry_refresh` rebuilds `_all_sessions`, the modal dismisses, and the user picks up where they left off — re-issuing the shortcut for the (now live) repointed entry. Simpler than a callback-driven auto-retry and matches the way the rest of the switcher handles state mutations.
  - **`_RepointInputScreen` lives in the same module as `StaleEntryModal`.** It is only used from there and has no reuse value, so the indirection of a separate file is unwarranted.

- **Upstream defects identified:** None.

- **Notes for sibling tasks:**
  - **t826_3 (website docs):** When documenting STALE registry recovery, mention that the TUI switcher now dims STALE entries with a `(stale)` suffix and offers an inline Prune / Repoint modal. The CLI `ait projects prune` / `doctor` flows remain available for batch operations; the TUI modal is for the "I clicked a stale entry by accident, fix it now" path.
  - **t826_4 (manual verification aggregate):** Add checklist items covering (a) STALE row rendering, (b) Prune branch, (c) Repoint branch, (d) the race-condition path (delete marker mid-switcher-session, then activate). The race-condition test is the one that proves `BOOTSTRAP_FAILED:stale_path` actually routes correctly — easy to forget without an explicit checklist line.
  - **Future modals invoked from `lib/`:** The `mock.patch.object(<ModalClass>, 'app', mock.Mock())` test fixture is the right pattern for unit-testing modals outside a running App. Re-use rather than fighting the read-only property.

- **Build verification:** N/A (`verify_build` is unset in this project).
