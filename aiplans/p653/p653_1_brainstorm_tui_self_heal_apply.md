---
Task: t653_1_brainstorm_tui_self_heal_apply.md
Parent Task: aitasks/t653_brainstorm_import_proposal_hangs.md
Sibling Tasks: aitasks/t653/t653_2_*.md, aitasks/t653/t653_3_*.md
Archived Sibling Plans: (none yet)
Worktree: (current branch — no worktree)
Branch: main
Base branch: main
---

# Plan: t653_1 — Brainstorm TUI self-heal on session open + persistent retry banner

## Context (recap)

The TUI's `_poll_initializer()` at `brainstorm_app.py:3172` is one-shot. When it sees `Completed`, it stops the timer and calls `apply_initializer_output()` exactly once (the call that swallowed the YAML error in session 635). When it sees `Error`/`Aborted`, it stops the timer permanently — even if the agent later writes valid output. The TUI on reopen never re-detects "n000_init still placeholder + output file present" so the user is stuck.

Goal: make the apply attempt re-fire on every session load and on output-file appearance, and surface failures via a **persistent banner widget**, not a fading toast.

## Approach

Three changes:

1. New helper `n000_needs_apply(task_num)` in `brainstorm_session.py` that detects the recoverable state.
2. New method `_try_apply_initializer_if_needed()` on `BrainstormApp`, hooked into `_load_existing_session()` and `_start_initializer_wait()`.
3. Soften `_poll_initializer()`'s Error/Aborted branch from "stop forever" to "poll slower, watch for `_output.md`".

Plus a `ctrl+r` retry binding and a persistent banner widget for surfacing apply failures.

## Step-by-step

### S1. Helper in `brainstorm_session.py`

Add near `apply_initializer_output()`:

```python
def n000_needs_apply(task_num: int | str) -> bool:
    """Return True if n000_init is still a placeholder AND an output file
    exists for the initializer agent — i.e., apply is a no-op-or-fix.
    """
    wt = crew_worktree(task_num)
    node_path = wt / NODES_DIR / "n000_init.yaml"
    out_path = wt / "initializer_bootstrap_output.md"
    if not node_path.is_file() or not out_path.is_file():
        return False
    try:
        data = read_yaml(str(node_path))
    except Exception:
        return False
    desc = (data or {}).get("description", "")
    return desc.startswith("Imported proposal (awaiting reformat):")
```

Export from the module's public-ish surface (no `__all__` change needed if there is none).

### S2. New method `_try_apply_initializer_if_needed` on `BrainstormApp`

Add `__init__` state:

```python
self._initializer_apply_error: str | None = None
self._applying_initializer = False
```

Method (place near the existing `_poll_initializer`):

```python
def _try_apply_initializer_if_needed(self, force: bool = False) -> None:
    if self._applying_initializer:
        return
    from brainstorm.brainstorm_session import (
        n000_needs_apply, apply_initializer_output,
    )
    if not force and not n000_needs_apply(self.task_num):
        return
    self._applying_initializer = True
    try:
        apply_initializer_output(self.task_num)
    except Exception as exc:
        self._initializer_apply_error = str(exc)
        self._set_apply_banner(
            f"Initializer apply failed: {exc} — "
            f'run `ait brainstorm apply-initializer {self.task_num}` to retry'
        )
    else:
        self._initializer_apply_error = None
        self._clear_apply_banner()
        self.notify("Initial proposal imported.")
        self._load_existing_session()
    finally:
        self._applying_initializer = False
```

### S3. Hook the auto-apply

In `_start_initializer_wait()` (line ~3162), call `self._try_apply_initializer_if_needed()` once before installing the polling timer.

In `_load_existing_session()` (find via `grep -n "_load_existing_session" brainstorm_app.py`), call it at the very end so a TUI reopen with stale placeholder + present output triggers apply automatically.

Re-entrancy: `_load_existing_session()` is called from inside the success branch of `_try_apply_initializer_if_needed`, but the `_applying_initializer` guard prevents recursive apply calls.

### S4. Soften `_poll_initializer()` Error/Aborted branch

Replace the `elif status in ("Error", "Aborted"):` block (line 3200) with:

```python
elif status in ("Error", "Aborted"):
    # Don't permanently stop — the agent may still write _output.md later.
    # Stop the fast 2 s timer; install a slower 30 s watcher.
    if self._initializer_timer is not None:
        self._initializer_timer.stop()
    self._initializer_timer = self.set_interval(30, self._poll_initializer)
    self.notify(
        f"Initializer agent {status.lower()}. "
        f'Watching for output; run `ait brainstorm apply-initializer '
        f'{self.task_num}` to retry manually.',
        severity="error",
    )
    self._load_existing_session()
    # If output already on disk, attempt apply now.
    self._try_apply_initializer_if_needed()
```

Note: do NOT set `self._initializer_done = True`. The watcher continues; once `apply_initializer_output()` succeeds in `_try_apply_initializer_if_needed()`, the dashboard refreshes and the placeholder is gone — `n000_needs_apply()` returns False and subsequent ticks become cheap no-ops.

### S5. Persistent banner widget

Compose-time addition (find the dashboard's `compose()` method and add at the very top, above the DAG widget):

```python
yield Static("", id="initializer_apply_banner", classes="initializer-banner")
```

CSS (in the app's existing CSS string or `.tcss` file — find via `grep -rn "CSS = " brainstorm_app.py`):

```css
.initializer-banner {
    display: none;
    background: $error;
    color: $text;
    padding: 0 1;
    height: 1;
}
.initializer-banner.visible {
    display: block;
}
```

Setter / clearer (place near `_try_apply_initializer_if_needed`):

```python
def _set_apply_banner(self, msg: str) -> None:
    try:
        widget = self.query_one("#initializer_apply_banner", Static)
        widget.update(msg)
        widget.add_class("visible")
    except Exception:
        pass  # banner not mounted yet (early load) — caller's exception still surfaces via notify

def _clear_apply_banner(self) -> None:
    try:
        widget = self.query_one("#initializer_apply_banner", Static)
        widget.update("")
        widget.remove_class("visible")
    except Exception:
        pass
```

### S6. Key-binding `ctrl+r` for manual retry

Verify availability: `grep -n "ctrl+r" brainstorm_app.py` — should be empty.

Add to the dashboard screen's `BINDINGS` (find via `grep -n "BINDINGS" brainstorm_app.py`):

```python
Binding("ctrl+r", "retry_initializer_apply", "Retry initializer apply"),
```

Action handler:

```python
def action_retry_initializer_apply(self) -> None:
    self._try_apply_initializer_if_needed(force=True)
```

`force=True` skips the `n000_needs_apply()` short-circuit so the user can re-run apply even after partial success. The internal try/except keeps the banner state coherent.

## Files touched

- `.aitask-scripts/brainstorm/brainstorm_session.py` — +`n000_needs_apply()` (~12 lines)
- `.aitask-scripts/brainstorm/brainstorm_app.py` — `__init__` state, `_try_apply_initializer_if_needed`, banner setter/clearer, `_poll_initializer` softening, `compose()` addition, CSS, BINDINGS entry, action handler (~80 lines net)

## Verification

1. **Synthetic session test.** Build `.aitask-crews/crew-brainstorm-9999/` mirroring session 635 (placeholder n000_init + valid `initializer_bootstrap_output.md` + `status: Completed`). Run `ait brainstorm 9999`. Expect: dashboard auto-applies on load, n000_init shows real description, banner stays hidden. Clean up afterwards (`rm -rf .aitask-crews/crew-brainstorm-9999/`).

2. **Synthetic Error→late-recovery test.** Same fixture but with `status: Error`, `error_message: "..."` and **no `_output.md`**. Open TUI; observe banner with retry hint. While TUI is open, copy a valid `_output.md` into the session dir. Within 30 s the slow watcher fires `_try_apply_initializer_if_needed()`, the apply succeeds, banner clears, dashboard refreshes.

3. **Banner persistence test.** Same fixture but with malformed `_output.md` that `apply_initializer_output()` will reject. Banner appears and stays through clicks/scrolls. (Without sibling t653_2, `apply_initializer_output()` cannot recover from em-dashes — that's expected; the banner is the right outcome.)

4. **Static check.**
   ```bash
   grep -n "_initializer_done = True" .aitask-scripts/brainstorm/brainstorm_app.py
   ```
   Only the `Completed` branch should remain.

5. **No regression in normal happy-path.** Run a fresh `ait brainstorm` import on a small clean proposal (no em-dashes); the agent completes, the 2 s timer sees `Completed`, applies, dashboard updates, banner stays hidden.

## Final Implementation Notes

(Filled in at archival time per task-workflow Step 9.)
