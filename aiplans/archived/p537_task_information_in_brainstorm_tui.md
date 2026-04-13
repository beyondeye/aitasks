---
Task: t537_task_information_in_brainstorm_tui.md
Base branch: main
---

# t537 — Task information in brainstorm TUI

## Context

The brainstorm Textual TUI (`ait brainstorm <task_num>`) currently shows only the static app name in its header ("ait brainstorm"). There is no visible indication of **which task** the user is currently brainstorming. Task detail is technically reachable by selecting the `n000_init` node in the Dashboard tab and pressing Enter, but this is not easily discoverable.

The fix is small and targeted: surface the task identifier and full name in the Textual `Header` bar so users instantly know which task context they are in. Per the task description, at a minimum the full task name must be shown in the title bar.

## Approach

Textual's `App` exposes two reactive attributes that the built-in `Header` widget renders:

- `self.title` — currently driven by `TITLE = "ait brainstorm"` class attribute
- `self.sub_title` — currently unset

Keeping `title` as the app identity and using `sub_title` for the task info gives the cleanest visual hierarchy in the header ("ait brainstorm — t537: task information in brainstorm tui") without touching any CSS or layout.

Task filename resolution priority:
1. If `session_data["task_file"]` is populated (after `_load_existing_session()`), use it — this is the authoritative path stored when the session was initialized.
2. Otherwise, glob `aitasks/t<task_num>_*.md` (single file expected). This handles the pre-init case where the `InitSessionModal` is about to be shown.
3. Fall back to `f"t{task_num}"` with no name if nothing is found.

The display name is the filename stem with the `t<num>_` prefix stripped, underscores left as-is (matches the existing task file naming convention used elsewhere in the TUI).

## Files to modify

- `.aitask-scripts/brainstorm/brainstorm_app.py` — only file touched.

## Implementation steps

### 1. Add a helper to resolve the task file and compute the display name

Add two small private methods to `BrainstormApp` (near `__init__`, around line 950):

```python
def _resolve_task_file_path(self) -> Path | None:
    """Return the task file path for self.task_num, or None if not found.

    Prefers session_data["task_file"] when available, otherwise globs aitasks/.
    """
    tf = self.session_data.get("task_file") if self.session_data else None
    if tf:
        p = Path(tf)
        if p.exists():
            return p
    matches = sorted(Path("aitasks").glob(f"t{self.task_num}_*.md"))
    return matches[0] if matches else None

def _update_title_from_task(self) -> None:
    """Set sub_title to include task id and full name."""
    path = self._resolve_task_file_path()
    if path is not None:
        stem = path.stem  # e.g. "t537_task_information_in_brainstorm_tui"
        prefix = f"t{self.task_num}_"
        name_part = stem[len(prefix):] if stem.startswith(prefix) else stem
        self.sub_title = f"t{self.task_num} — {name_part}"
    else:
        self.sub_title = f"t{self.task_num}"
```

`Path` is already imported at the top of the file (line 10: `from pathlib import Path`).

### 2. Call the helper in `__init__`

At the end of `BrainstormApp.__init__` (after line 949, after existing field initializations):

```python
self._update_title_from_task()
```

This sets a reasonable `sub_title` even before the session is loaded (covers the `InitSessionModal` path where `_load_existing_session()` is never called until after init).

### 3. Refresh the title after session loads

In `_load_existing_session()` (line 1340), after `self.session_data = load_session(self.task_num)` (line 1342), add:

```python
self._update_title_from_task()
```

This ensures the authoritative `task_file` path from the session YAML is used once available (handles the edge case where a task file has been renamed after the session was created).

## Why not touch `TITLE`

`TITLE = "ait brainstorm"` is a class-level constant and represents the app identity — leaving it alone means the header always reads "ait brainstorm" as the primary title, with `sub_title` showing task-specific context. This matches Textual conventions and avoids having to juggle the class attribute vs instance attribute.

## Verification

1. **Smoke test with an existing session**: run `ait brainstorm 427` (crew-brainstorm-427 exists in `.aitask-crews/`) — verify the header shows `ait brainstorm — t427 — <name>` after the dashboard loads.
2. **Smoke test without a session**: run `ait brainstorm 537` (no crew yet) — the `InitSessionModal` should appear, and behind/around it the header should still read `ait brainstorm — t537 — task_information_in_brainstorm_tui` (resolved via glob).
3. **Edge case**: run `ait brainstorm 9999` (nonexistent task) — header should degrade gracefully to `ait brainstorm — t9999` (no dash, no name).
4. **No regressions**: run `bash tests/test_plan_externalize.sh` and any brainstorm-related tests (none found targeting `brainstorm_app.py` specifically, as it is a TUI).

The crew-copied copy at `.aitask-crews/crew-brainstorm-427/.aitask-scripts/brainstorm/brainstorm_app.py` is a frozen per-crew snapshot and does **not** need to be updated — it will pick up changes the next time a fresh crew worktree is created.

## Step 9 reference

After approval and implementation, proceed to Step 9 (Post-Implementation): user review, commit (`feature: Add task info to brainstorm TUI title bar (t537)`), plan commit via `./ait git`, then archive with `./.aitask-scripts/aitask_archive.sh 537` and `./ait git push`.

## Final Implementation Notes

- **Actual work done:** Added two private methods to `BrainstormApp` in `.aitask-scripts/brainstorm/brainstorm_app.py`: `_resolve_task_file_path()` (prefers `session_data["task_file"]`, falls back to globbing `aitasks/t<num>_*.md`) and `_update_title_from_task()` (sets `self.sub_title` to `f"t{num} — {name_part}"` or just `f"t{num}"` as fallback). Called the helper at the end of `__init__` and again in `_load_existing_session()` after session data is loaded. Total: +23 lines.
- **Deviations from plan:** None. Implementation matched the plan exactly.
- **Issues encountered:** `tests/test_brainstorm_cli.sh` was already failing on clean `main` (pre-existing issue, unrelated to this change) — verified by stashing changes and re-running. Python syntax check (`py_compile`) and headless `BrainstormApp` instantiation both confirm correctness for existing task (`t537 — task_information_in_brainstorm_tui`) and missing task (`t9999` fallback).
- **Key decisions:** Used `self.sub_title` rather than touching the class-level `TITLE` constant so the app identity ("ait brainstorm") stays intact and task context lives in the subtitle. Resolution order (session_data → glob → fallback) handles both existing and pre-init sessions uniformly. The frozen per-crew copy at `.aitask-crews/crew-brainstorm-427/.aitask-scripts/brainstorm/brainstorm_app.py` was intentionally not touched — it's a point-in-time snapshot that will pick up the change on the next crew spawn.
