---
Task: t2129_syncer_failure_modal_swallows_bracketed_git_output.md
Base branch: main
Output branch: main
---

# t2129 — SyncFailureScreen swallows bracketed git output

## Context

`SyncFailureScreen.compose` (`.aitask-scripts/syncer/sync_failure_screen.py:73-87`)
builds its body as one f-string with `[b]…[/b]` console markup and interpolates
`ctx.ref_name`, `ctx.command`, `ctx.status` and `ctx.stderr_tail` verbatim, then
hands it to a markup-enabled `Static`. Git output routinely contains square
brackets (` ! [rejected]        main -> main`), and those spans are parsed as style
tags and dropped — the user never sees `[rejected]`. The title `Label` also
interpolates `ctx.action` / `ctx.ref_name` with markup on.

The sibling `MainConflictScreen` (same file, t2126) already does it right:
`Static(Text.assemble(*parts))` with labels as `(text, "bold")` tuples and values
as plain strings, and `Label(title, markup=False)`. Follow that exact pattern.

## Implementation (current-branch mode, no worktree)

### 1. Test first — `tests/test_syncer_rows.py`

Add, next to `_MainConflictHost` / `MainConflictScreenTests` (~line 3798-3905):

- `_SyncFailureHost(App)` — minimal host pushing `SyncFailureScreen(ctx)`
  (mirrors `_MainConflictHost`).
- `SyncFailureScreenRenderTests(unittest.TestCase)` with a `_render(ctx)` helper
  (same shape as `MainConflictScreenTests._render`: `run_test(size=(120, 30))`,
  `str(query_one("#sync_failure_title").render())`,
  `str(query_one("#sync_failure_body Static").render())`), and tests:
  - `test_git_output_and_command_render_verbatim` — ctx with
    `stderr_tail=" ! [rejected]        main -> main (fetch first)"`,
    `command="git push '/x/[bold]y.git' main:main"`; assert both strings appear
    verbatim in the body, plus `Branch: main`, `Status: ERROR`, `Output (tail):`.
  - `test_empty_tail_reads_empty` — `stderr_tail=""` → body contains `(empty)`.
  - `test_title_is_literal` — `action="[b]push"`-style bracketed value appears
    verbatim in the title (pins `markup=False`).

Run it before the fix to confirm it is red (`[rejected]` missing).

### 2. Fix — `.aitask-scripts/syncer/sync_failure_screen.py`

Replace the f-string body in `SyncFailureScreen.compose` with:

```python
parts = [
    ("Branch: ", "bold"), ctx.ref_name, "\n",
    ("Command: ", "bold"), ctx.command, "\n",
    ("Status: ", "bold"), ctx.status, "\n\n",
    ("Output (tail):", "bold"), "\n", ctx.stderr_tail or "(empty)",
]
```
and `yield Static(Text.assemble(*parts))`; give the title
`Label(..., id="sync_failure_title", markup=False)`. `Text` is already imported.

### 3. Verify

- `python -m pytest tests/test_syncer_rows.py -k "SyncFailure or MainConflict or failure" -q`
  (or `python -m unittest` equivalent) — new tests green, existing failure-modal
  tests (`test_a_captured_failure_still_opens_the_failure_modal`,
  `_open_failure_agent` users) unchanged.
- Full `tests/test_syncer_rows.py` run.

## Step 9

Post-implementation: current-branch mode, no merge; archive via
`aitask_archive.sh 2129`.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
