---
Task: t738_task_description_get_lost.md
Base branch: main
plan_verified: []
---

# t738 — Persist task info in monitor/minimonitor after archival

## Context

In `ait monitor` and `ait minimonitor`, each pane running a code agent is
linked to its task by the window name (`agent-pick-<id>` /
`agent-qa-<id>`). On every refresh, the TUI calls
`TaskInfoCache.get_task_info(task_id, session_name)` to display the task
title (and, in the full monitor, the kill-confirm dialog and detail dialog).

`TaskInfoCache._resolve()` (`.aitask-scripts/monitor/monitor_shared.py:217`)
only globs the **active** locations:

- Parent task: `aitasks/t<id>_*.md`
- Child task: `aitasks/t<parent>/t<parent>_<child>_*.md`
- Parent plan: `aiplans/p<id>_*.md`
- Child plan: `aiplans/p<parent>/p<parent>_<child>_*.md`

The moment a task is archived (Step 9 of the workflow moves the file under
`aitasks/archived/…`), `_resolve()` returns `None`. There are two failure
windows:

1. The pane outlives the task — agent is finished but its tmux pane is still
   open (common while reviewing the result). The cache may have already
   stored the resolved `TaskInfo` from before archival, but if
   `update_session_mapping()` clears the cache because a session was
   added/removed, the next refresh re-resolves and returns `None` —
   the task title disappears from the agent card.
2. Cold start — the user opens the monitor *after* archival but the
   pane is still alive. `_resolve()` fails on the first lookup and
   the title is never shown.

The codebase already half-anticipates this (see fallback
`f"(archived t{task_id})"` in `monitor_app.py:1621,1723`), but the
*display* of the agent card in both monitor and minimonitor relies on
`info.title` being non-None.

### Fix strategy

Extend `_resolve()` to fall back to the archived locations when the active
glob has no match. Same fallback applies to plan resolution.

Out of scope: extracting from `aitasks/archived/_b0/old<N>.tar.zst` bundles.
Bundled tasks are old enough that no live agent should reference them; if
the lookup fails, the agent card simply omits the title (current behavior
preserved).

## Files to modify

### `.aitask-scripts/monitor/monitor_shared.py`

**Function `_resolve()` (lines 217–296).**

Replace the single-glob lookup for both task and plan files with a tuple
of `(active_dir, archived_dir)` candidates, returning the first match.

#### Task file lookup

Current shape:

```python
if "_" in task_id:
    parent, child = task_id.split("_", 1)
    pattern = f"t{parent}_{child}_*.md"
    search_dir = tasks_dir / f"t{parent}"
else:
    pattern = f"t{task_id}_*.md"
    search_dir = tasks_dir

if not search_dir.is_dir():
    return None
matches = list(search_dir.glob(pattern))
if not matches:
    return None
task_path = matches[0]
```

Replace with a small helper-style loop over candidate dirs:

```python
archived_dir = tasks_dir / "archived"
if "_" in task_id:
    parent, child = task_id.split("_", 1)
    pattern = f"t{parent}_{child}_*.md"
    search_dirs = (tasks_dir / f"t{parent}", archived_dir / f"t{parent}")
else:
    pattern = f"t{task_id}_*.md"
    search_dirs = (tasks_dir, archived_dir)

task_path = None
for d in search_dirs:
    if not d.is_dir():
        continue
    matches = list(d.glob(pattern))
    if matches:
        task_path = matches[0]
        break
if task_path is None:
    return None
```

#### Plan file lookup

Mirror the same change for plans (lines ~261–283):

```python
archived_plan_dir = plans_dir / "archived"
if "_" in task_id:
    parent, child = task_id.split("_", 1)
    plan_pattern = f"p{parent}_{child}_*.md"
    plan_dirs = (plans_dir / f"p{parent}", archived_plan_dir / f"p{parent}")
else:
    plan_pattern = f"p{task_id}_*.md"
    plan_dirs = (plans_dir, archived_plan_dir)

plan_content = None
for pd in plan_dirs:
    if not pd.is_dir():
        continue
    plan_matches = list(pd.glob(plan_pattern))
    if plan_matches:
        try:
            plan_raw = plan_matches[0].read_text(encoding="utf-8")
            if plan_raw.startswith("---"):
                fm_parts = plan_raw.split("---", 2)
                if len(fm_parts) >= 3:
                    plan_content = fm_parts[2].strip()
                else:
                    plan_content = plan_raw
            else:
                plan_content = plan_raw
        except OSError:
            pass
        break
```

Active dirs win when both contain a file (race during archive itself —
shouldn't happen but be deterministic).

The `task_file` field returned in `TaskInfo` will resolve to a path under
`aitasks/archived/…` for archived tasks. That's correct — `kill-confirm`
and detail dialogs only display the title/body and don't try to write
back to it.

### `.aitask-scripts/monitor/monitor_shared.py` — `find_next_sibling()`

No change needed. The function is intentionally scoped to active siblings
(`Ready` status under `aitasks/t<parent>/`) — extending it to archived
would surface already-completed siblings as candidates.

## Tests

Add `tests/test_task_info_cache_archived.py` (new file). Patterned on
`tests/test_diff_engine.py` (`unittest`, `tempfile`, `sys.path` insertion
of `.aitask-scripts/`).

Test cases:

1. **Active parent task resolves** — write `aitasks/t100_foo.md`, assert
   `_resolve("100")` returns `TaskInfo` with the right title.
2. **Archived parent task resolves** — write only
   `aitasks/archived/t100_foo.md` (no active file), assert
   `_resolve("100")` returns the archived file's `TaskInfo` and that
   `task_file` points under `archived/`.
3. **Archived child task resolves** — write
   `aitasks/archived/t50/t50_2_bar.md`, assert `_resolve("50_2")`
   returns its `TaskInfo`.
4. **Active wins over archived** — write both files; assert the active
   one wins.
5. **Archived plan resolves alongside archived task** — write
   `aitasks/archived/t100_foo.md` and
   `aiplans/archived/p100_foo.md`; assert `plan_content` is populated.
6. **Missing in both → None** — assert `_resolve("999")` returns `None`.

Each test creates a `tempfile.TemporaryDirectory()`, builds the expected
on-disk layout, instantiates `TaskInfoCache(project_root=Path(tmpdir))`,
and calls `_resolve` directly (it's the simplest unit boundary; `get_task_info`
is just a memoization wrapper).

## Verification

1. **Run the new unit test:**
   ```bash
   python tests/test_task_info_cache_archived.py
   ```
   Expect all six cases to pass.

2. **Manual smoke test (minimonitor):**
   - Start an agent on any task: `/aitask-pick <id>` from a tmux session.
   - Open `ait minimonitor` in a side pane.
   - Confirm the task title shows under the agent card.
   - Let the agent finish, then archive the task (Step 9 of the workflow,
     or `./.aitask-scripts/aitask_archive.sh <id>`).
   - The agent's tmux pane will still be alive — minimonitor's next
     refresh should keep showing the task title (sourced from the
     archived file).

3. **Manual smoke test (full monitor) — `i` (task info dialog):**
   - In the full monitor, focus an agent pane whose task has been
     archived; press `i`. The detail dialog should populate with the
     archived task body. Press `p` to flip to the plan — should also
     load from `aiplans/archived/`.

4. **Regression check:**
   ```bash
   bash tests/test_multi_session_minimonitor.sh
   bash tests/test_multi_session_monitor.sh
   ```
   These don't directly exercise archive resolution but cover the
   per-session task-cache routing — must remain green.

## Step 9 (Post-Implementation)

Standard archival: this task becomes a Done bug fix, archive via
`/aitask-pick` Step 9 with `aitask_archive.sh 738`.
