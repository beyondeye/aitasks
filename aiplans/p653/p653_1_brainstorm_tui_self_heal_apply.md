---
Task: t653_1_brainstorm_tui_self_heal_apply.md
Parent Task: aitasks/t653_brainstorm_import_proposal_hangs.md
Sibling Tasks: aitasks/t653/t653_2_*.md, aitasks/t653/t653_3_*.md, aitasks/t653/t653_4_*.md
Archived Sibling Plans: (none yet)
Worktree: (current branch — no worktree)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-26 16:39
---

# Plan: t653_1 — Brainstorm TUI self-heal on session open + persistent retry banner

## Context

Bug at Layer B in the t653 chain (parent: `aitasks/t653_brainstorm_import_proposal_hangs.md`).

The TUI's `_poll_initializer()` at `brainstorm_app.py:3172` is one-shot: it sets `_initializer_done = True` on **both** the `Completed` (line 3187) and `Error`/`Aborted` (line 3201) branches and stops the 2 s polling timer. On `Error` it surfaces a transient toast and never polls again. There is no detection on TUI reopen of "output file present + n000_init still placeholder" — `_load_existing_session()` (line 1778) re-loads the whole session via `load_session()` but never re-attempts apply. Verified against session 635: `initializer_bootstrap_output.md` has been valid 794 lines on disk for hours, and the dashboard still shows the placeholder.

Goal: make the TUI self-healing — on every session load (including re-open), if there is an output file and the node is still a placeholder, retry `apply_initializer_output()`. On Error, keep polling at a longer interval for the output to appear. Surface apply failures via a **persistent banner widget** (not a fading toast) pointing the user at `ait brainstorm apply-initializer <session>` (the retry CLI is added by sibling t653_2; the message is informative even before t653_2 lands).

## Approach

Three changes, plus a manual-retry binding and a persistent banner widget:

1. New helper `n000_needs_apply(task_num)` in `brainstorm_session.py` that detects the recoverable state.
2. New method `_try_apply_initializer_if_needed()` on `BrainstormApp`, hooked into `_load_existing_session()` and `_start_initializer_wait()`.
3. Soften `_poll_initializer()`'s Error/Aborted branch from "stop forever" to "poll slower (30 s), watch for `_output.md`".
4. `ctrl+r` retry binding (verified unused).
5. Persistent `Static` banner widget at the top of the dashboard, hidden by default.

## Verified codebase facts (all confirmed by Phase 1 exploration)

- `_poll_initializer()` — `brainstorm_app.py:3172`. Completed branch: lines 3187–3199; Error/Aborted branch: lines 3200–3209. Timer attribute is `self._initializer_timer`.
- `_start_initializer_wait()` — `brainstorm_app.py:3162–3170`. Installs `set_interval(2, self._poll_initializer)` on line 3170.
- `_load_existing_session()` — `brainstorm_app.py:1778`. Reloads via `load_session()`, refreshes title/DAG/nodes; safe to call new helper at end.
- `apply_initializer_output(task_num: int | str) -> None` — `brainstorm_session.py:264`. Raises `FileNotFoundError`/`ValueError` (no custom exceptions).
- `crew_worktree` (`brainstorm_session.py:35`), `NODES_DIR` (line 23), `read_yaml` (line 19) — all already in scope of `brainstorm_session.py`.
- Placeholder string `"Imported proposal (awaiting reformat): "` — produced at `brainstorm_session.py:120`. Output filename `initializer_bootstrap_output.md` — `brainstorm_session.py:278`.
- `BrainstormApp.compose()` — `brainstorm_app.py:1328`. First widget is `Header()` (line 1329). No existing top-level banner.
- Inline CSS — `brainstorm_app.py:904` (`CSS = """..."""`). No external `.tcss` file.
- `BINDINGS` — `brainstorm_app.py:1276`. `Binding` already imported (line 16). `ctrl+r` not used anywhere.
- `__init__` — `brainstorm_app.py:1286`. Already initializes `_initializer_agent`, `_initializer_done`, `_initializer_timer` (lines 1305–1307); safe place for new state.
- `Static` already imported from `textual.widgets` (line 28).

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

No `__all__` change needed — the module has no `__all__`.

### S2. New state + method on `BrainstormApp`

In `__init__` (`brainstorm_app.py:1286`), alongside existing `_initializer_*` state at lines 1305–1307:

```python
self._initializer_apply_error: str | None = None
self._applying_initializer = False
```

Method (place near `_poll_initializer`):

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

Re-entrancy: `_try_apply_initializer_if_needed` calls `_load_existing_session()` on success, which the next step hooks back into `_try_apply_initializer_if_needed`. The `_applying_initializer` guard prevents recursion.

### S3. Hook the auto-apply

- In `_start_initializer_wait()` (around line 3170, just before `set_interval`), call `self._try_apply_initializer_if_needed()` once.
- In `_load_existing_session()` (around line 1788, after `_actions_show_step1()`), call `self._try_apply_initializer_if_needed()` at the end.

### S4. Soften `_poll_initializer()` Error/Aborted branch

Replace the `elif status in ("Error", "Aborted"):` block (currently lines 3200–3209) with:

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
    self._try_apply_initializer_if_needed()
```

Critically: do **NOT** set `self._initializer_done = True`. The Completed branch (line 3187) keeps setting it — that distinction is the whole point of the softening. Once `_try_apply_initializer_if_needed()` succeeds, `n000_needs_apply()` returns False and subsequent 30 s ticks are cheap no-ops.

### S5. Persistent banner widget

In `BrainstormApp.compose()` (`brainstorm_app.py:1328`), insert immediately after `yield Header()` (line 1329):

```python
yield Static("", id="initializer_apply_banner", classes="initializer-banner")
```

Add CSS to the inline `CSS = """..."""` block at `brainstorm_app.py:904`:

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
        pass  # banner not mounted yet (early load); caller's exception still surfaces via notify

def _clear_apply_banner(self) -> None:
    try:
        widget = self.query_one("#initializer_apply_banner", Static)
        widget.update("")
        widget.remove_class("visible")
    except Exception:
        pass
```

### S6. Key-binding `ctrl+r` for manual retry

Add to `BINDINGS` (`brainstorm_app.py:1276`):

```python
Binding("ctrl+r", "retry_initializer_apply", "Retry initializer apply"),
```

Action handler (anywhere in `BrainstormApp`):

```python
def action_retry_initializer_apply(self) -> None:
    self._try_apply_initializer_if_needed(force=True)
```

`force=True` skips the `n000_needs_apply()` short-circuit so the user can re-run apply even after partial success.

## Files touched

- `.aitask-scripts/brainstorm/brainstorm_session.py` — `+n000_needs_apply()` (~12 lines)
- `.aitask-scripts/brainstorm/brainstorm_app.py` — `__init__` state, `_try_apply_initializer_if_needed`, banner setter/clearer, `_poll_initializer` softening, `compose()` addition, CSS, `BINDINGS` entry, action handler, two call-site hooks (~80 lines net)

## Verification

1. **Static check.**
   ```bash
   grep -n "_initializer_done = True" .aitask-scripts/brainstorm/brainstorm_app.py
   ```
   Should show only the `Completed` branch (line ~3187) — the Error/Aborted branch no longer flips the flag.

2. **Synthetic Completed-but-unapplied test.** Build `.aitask-crews/crew-brainstorm-9999/` mirroring session 635:
   - `br_nodes/n000_init.yaml` with `description: 'Imported proposal (awaiting reformat): demo.md'`
   - `br_proposals/n000_init.md` placeholder
   - valid `initializer_bootstrap_output.md` with `--- NODE_YAML_START ---` / `--- PROPOSAL_START ---`
   - `initializer_bootstrap_status.yaml` with `status: Completed`

   Run `ait brainstorm 9999`. Dashboard auto-applies on load; n000_init shows real description; banner stays hidden. Cleanup: `rm -rf .aitask-crews/crew-brainstorm-9999/`.

3. **Synthetic Error → late-recovery test.** Same fixture but with `status: Error`, `error_message: "..."`, and **no `_output.md`**. Open TUI; observe the banner. While TUI is open, drop a valid `_output.md` into the session dir. Within 30 s the slow watcher fires, apply succeeds, banner clears, dashboard refreshes.

4. **Banner persistence test.** Same fixture but with malformed `_output.md`. Banner appears and stays through clicks/scrolls. (Without sibling t653_2's tolerant apply, em-dash failures will recur — that's expected; the banner is the right outcome.)

5. **Manual retry.** With the banner showing, press `ctrl+r`. `_try_apply_initializer_if_needed(force=True)` fires; banner state updates accordingly.

6. **No regression in happy-path.** Run a fresh `ait brainstorm` import on a clean proposal (no em-dashes). The agent completes, the 2 s timer sees `Completed`, apply runs once, dashboard updates, banner stays hidden.

## Out of scope (intentionally)

- No changes to `apply_initializer_output()` itself (Layer C — owned by t653_2).
- No new CLI helper (Layer C — owned by t653_2).
- No agent-crew status / transition changes (Layer D — owned by t653_3).
- No heartbeat fixes (Layer A — owned by parent t650).
- No polling-activity indicator widget — split into new sibling **t653_5**. That task adds a reusable indicator (off / dim-cycle when polling / bright flash on poll-fire), mounted *contextually* next to each polling site (e.g., next to the initializer banner here), and wires it to every `set_interval`/`set_timer` in the brainstorm TUI. The 30 s slow watcher introduced by S4 above is one of its consumers, but the wiring is owned by t653_5.

## Step 9 — Post-Implementation

Standard task-workflow archival. No build verification configured (`verify_build` not set in `project_config.yaml`). After commit:
- Append "Final Implementation Notes" to this plan covering: actual files touched, any deviations (especially around CSS placement or the `_load_existing_session` call site), and notes for sibling t653_2 / t653_3 (e.g., banner-message text they may want to update once the retry CLI lands).
- Run `aitask_archive.sh 653_1`. Push.

## Final Implementation Notes

(Filled in at archival time per task-workflow Step 9.)
