---
Task: aitasks/t525_better_next_sibling.md
Worktree: (current branch, no worktree)
Branch: main
Base branch: main
---

# t525 — Better (n)next sibling: handle parent tasks with children

## Context

`ait monitor` TUI has a `(n) Next Sibling` keybinding that terminates the
currently focused code-agent pane and launches a new one for the next
sibling task. Today it only works when the focused agent is running a
**child** task (e.g. `t123_4`) — if the agent is a **parent** task with
children (e.g. `t123`), the handler bails out with
`"Not a child task — no siblings"` and the user must manually pick a child.

Fix: extend the command so that when a parent task is focused, it picks
the first pending child of that parent using the same ordering and
status-filter heuristic already used for sibling selection.

## Files to modify

1. `.aitask-scripts/monitor/monitor_shared.py` — generalize `find_next_sibling`
2. `.aitask-scripts/monitor/monitor_app.py` — remove parent-bail guard and fix parent_id fallback

## Current behavior (code paths)

- **Binding** (`monitor_app.py:330`): `Binding("n", "pick_next_sibling", "Next Sibling")`
- **Handler** (`monitor_app.py:920-958`): `action_pick_next_sibling`
  - Lines 935–937: early return when `"_" not in task_id` → this is where parent tasks fail.
  - Line 945: `self._task_cache.find_next_sibling(task_id)`
  - Line 950: `parent_id = self._task_cache.get_parent_id(task_id)` — returns `None` for parents.
- **Helper** (`monitor_shared.py:109-156`): `find_next_sibling(task_id)`
  - Lines 114–115: early return when `"_" not in task_id`.
  - Otherwise: scans `aitasks/t{parent}/t{parent}_*_*.md`, excludes `task_id` itself, keeps only `status == "Ready"`, sorts by numeric child number, returns the first.
- **Dialog** (`NextSiblingDialog`, `monitor_app.py:184-240`): `parent_id` drives the "Choose child" button (`dismiss(("choose", self._parent_id))`). The downstream callback (`_on_next_sibling_result`) uses `resolve_dry_run_command(..., "pick", target_id)` which already handles parent IDs (opens the child-selection dialog in aitask-pick).

## Changes

### Change 1: `monitor_shared.py` — generalize `find_next_sibling`

Refactor `find_next_sibling(task_id)` so that:
- If `task_id` contains `_` (child): behavior is unchanged. `parent = task_id.split("_", 1)[0]`, self is excluded from candidates.
- If `task_id` has no `_` (parent): treat `parent = task_id` and scan for its children. There is no "self" among the children, so nothing is excluded.

Replace lines 109–156 (the whole method body) with:

```python
    def find_next_sibling(self, task_id: str) -> tuple[str, str] | None:
        """Find the next Ready sibling/child task.

        If task_id is a child (e.g. "123_4"): returns the next Ready sibling
        under the same parent, excluding the current task.
        If task_id is a parent (e.g. "123"): returns the first Ready child
        of that parent.

        Returns (task_id, title) or None.
        """
        if "_" in task_id:
            parent, _child = task_id.split("_", 1)
            exclude_id: str | None = task_id
        else:
            parent = task_id
            exclude_id = None

        search_dir = self._project_root / "aitasks" / f"t{parent}"
        if not search_dir.is_dir():
            return None

        candidates = []
        child_re = re.compile(rf'^t{re.escape(parent)}_(\d+)_')
        for path in sorted(search_dir.glob(f"t{parent}_*_*.md")):
            m = child_re.match(path.stem)
            if not m:
                continue
            sib_child = m.group(1)
            sib_id = f"{parent}_{sib_child}"
            if exclude_id is not None and sib_id == exclude_id:
                continue
            try:
                raw = path.read_text(encoding="utf-8")
            except OSError:
                continue
            parsed = parse_frontmatter(raw)
            if parsed is None:
                continue
            metadata, body, _ = parsed
            if str(metadata.get("status", "")).strip() != "Ready":
                continue
            title = None
            for line in body.splitlines():
                ls = line.strip()
                if ls.startswith("# "):
                    title = ls[2:].strip()
                    break
            if not title:
                parts = path.stem.split("_", 2)
                title = parts[2].replace("_", " ") if len(parts) > 2 else path.stem
            candidates.append((int(sib_child), sib_id, title))

        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0])
        _, sib_id, title = candidates[0]
        return (sib_id, title)
```

The scan/parse/sort logic is identical to today — only the parent resolution and the self-exclusion are gated by whether `task_id` is a child.

### Change 2: `monitor_app.py` — remove parent bail and fix parent_id fallback

In `action_pick_next_sibling` (`monitor_app.py:920-958`):

- **Delete** lines 935–937:
  ```python
  if "_" not in task_id:
      self.notify("Not a child task — no siblings", severity="warning")
      return
  ```
- **Change** line 950 to fall back to the current task_id when it is itself a parent, so the dialog's "Choose child" button still targets the correct parent:
  ```python
  parent_id = self._task_cache.get_parent_id(task_id) or task_id
  ```

Everything else in the handler (invalidate, get_task_info, find_next_sibling, dialog, callback) works unchanged — `NextSiblingDialog` and `_on_next_sibling_result` already handle parent target IDs via `resolve_dry_run_command`.

Also update the warning message on line 947 from `"No ready siblings found"` to `"No ready siblings or children found"` so parent-task users get a clearer message when all children are in progress / done.

## Verification

1. **Syntax/import check**:
   ```bash
   python3 -c "import ast; ast.parse(open('.aitask-scripts/monitor/monitor_shared.py').read())"
   python3 -c "import ast; ast.parse(open('.aitask-scripts/monitor/monitor_app.py').read())"
   ```

2. **Manual test (child task — regression)**:
   - Open `ait monitor` with an agent window named `agent-pick-<parent>_<child>` where sibling children exist in `Ready` status.
   - Press `n`. The dialog should suggest the lowest-numbered *other* Ready sibling (unchanged from today).

3. **Manual test (parent task — new behavior)**:
   - Open `ait monitor` with an agent window named `agent-pick-<parent>` where the parent has pending Ready children.
   - Press `n`. The dialog should now appear and suggest the lowest-numbered Ready child, instead of showing the `"Not a child task — no siblings"` warning.
   - Confirm "Pick" launches a new agent for that child.
   - Confirm "Choose child" falls through to the normal child picker for the parent.

4. **Manual test (parent with no Ready children)**:
   - Open `ait monitor` with an agent window for a parent whose children are all Done/Implementing.
   - Press `n`. Should now show `"No ready siblings or children found"` warning (clean failure).

## Post-Implementation (Step 9)

Follow the standard task-workflow Step 9: user review → commit → archive via
`./.aitask-scripts/aitask_archive.sh 525` → `./ait git push`.

## Final Implementation Notes

- **Actual work done:**
  - `monitor_shared.py`: generalized `find_next_sibling(task_id)` to accept
    both child IDs (existing behavior) and parent IDs (new: returns the first
    `Ready` child of the parent). Same scan/sort/status-filter logic.
  - `monitor_app.py` — `action_pick_next_sibling`: removed the
    `"_" not in task_id` early-return that bailed out for parent tasks,
    updated the warning from "No ready siblings found" to "No ready siblings
    or children found", and changed `parent_id` fallback to the current task
    id so the dialog's "Choose child" button still targets the correct
    parent.
  - `monitor_app.py` — `NextSiblingDialog.compose`: `will_kill` now also
    activates when the current task has no `_` (parent with children), with
    a tailored warning line "Parent agent pane will be killed (parent is
    split into children)".
  - `monitor_app.py` — `_on_next_sibling_result`: the pane is now killed when
    `is_parent_with_children` is true (in addition to Done/archived), because
    a parent task that was split into children no longer has implementation
    work of its own — the pick session for it can be closed.
- **Deviations from plan:** Added the parent-pane kill behavior after the
  user pointed out that when a parent is split into children, the parent's
  agent pane becomes redundant (case observed with task 521 in the current
  tmux session). This was not in the original plan but fits the spirit of
  the "automate transitioning away from a finished agent session" goal.
- **Issues encountered:** None. Smoke-tested against live repo parent tasks
  (t259, t369, t376, t386, t399, t401, t417, t423, t447, t468) —
  `find_next_sibling` returned the expected first-Ready child in each case.
  Child regression tested against `259_1` → `259_2`, `369_4` → `369_5`,
  `417_11` → `None` (no other Ready siblings).
- **Key decisions:**
  - Single generalized `find_next_sibling` instead of a separate
    `find_first_pending_child` helper — the scan/filter/sort bodies were
    identical and the parent/child difference reduces to the self-exclusion.
  - Kill condition uses `"_" not in task_id` rather than a status check on
    the parent — this matches the workflow invariant that parents with
    `children_to_implement` live in `Ready` (or blocked) state, and avoids
    a race where the status cache may be stale.
