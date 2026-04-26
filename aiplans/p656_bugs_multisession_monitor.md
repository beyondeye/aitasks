---
Task: t656_bugs_multisession_monitor.md
Base branch: main
plan_verified: []
---

# Plan: Cross-project task data in monitor / minimonitor (t656)

## Context

`ait monitor` and `ait minimonitor` are Textual TUIs that, in multi-session mode (`M` binding), display codeagents running in tmux sessions belonging to **other** aitasks projects. Two related bugs surface there:

1. **Wrong task description.** For a codeagent in a foreign tmux session, the row shows missing/wrong title, priority, status, etc. — because `TaskInfoCache` is initialized with a single project root (the one where the monitor was launched) and reads `<local_root>/aitasks/t<N>...md` for every pane regardless of which session it belongs to.
2. **`n` (next-sibling) shortcut is broken cross-session.** `find_next_sibling` searches the local project's `aitasks/t<parent>/` directory; siblings in the foreign project are never found. Even if one were found, the subsequent `resolve_dry_run_command` / `resolve_agent_string` / `AgentCommandScreen` calls all use `self._project_root`, so the new pick would launch in the wrong project.

The framework already discovers per-session project roots: `discover_aitasks_sessions()` (`lib/agent_launch_utils.py:248-309`) returns a list of `AitasksSession(session, project_root, project_name)`, and `TmuxMonitor` already caches it via `_discover_sessions_cached()` (`monitor/tmux_monitor.py:153-162`). Each `PaneSnapshot` already carries `pane.session_name`. The fix is simply to thread the per-pane session through to the lookups so the right project root is used.

## Approach

Make `TaskInfoCache` cross-project aware via a session→project-root mapping, expose that mapping from `TmuxMonitor`, refresh it on every monitor tick, and update every call site in `monitor_app.py` / `minimonitor_app.py` to pass the pane's `session_name`. Local-project behaviour is preserved as the fallback when `session_name` is empty (legacy single-session paths) or unknown.

## Files to modify

### 1. `.aitask-scripts/monitor/monitor_shared.py`

Make `TaskInfoCache` aware of multiple project roots.

- `__init__(self, project_root: Path, session_to_project: dict[str, Path] | None = None)`:
  - Store `self._project_root` (local fallback) and `self._session_to_project: dict[str, Path] = session_to_project or {}`.
  - Change cache key from `task_id: str` to `key: tuple[str, str] = (session_name, task_id)` so two projects with the same task ID don't collide.
  - `_window_to_task_id` cache stays keyed by window name (pure regex extraction; same value across sessions).

- New method `update_session_mapping(self, mapping: dict[str, Path]) -> None`:
  - Replace `self._session_to_project` if the dict differs from the current one. Keep cache entries; foreign sessions can come and go without invalidating the cache.

- Internal helper `_root_for_session(self, session_name: str) -> Path`:
  - Returns `self._session_to_project.get(session_name, self._project_root)`. Empty `session_name` → local root.

- Update method signatures (default `session_name=""` to keep the legacy single-session path working):
  - `get_task_info(self, task_id: str, session_name: str = "") -> TaskInfo | None`
  - `find_next_sibling(self, task_id: str, session_name: str = "") -> tuple[str, str] | None`
  - `invalidate(self, task_id: str, session_name: str = "") -> None`
  - `_resolve(self, task_id: str, session_name: str) -> TaskInfo | None` — replace the `tasks_dir = self._project_root / "aitasks"` line with `root = self._root_for_session(session_name)` then `tasks_dir = root / "aitasks"` / `plans_dir = root / "aiplans"`. The `task_file` field on `TaskInfo` should be relative to the resolved `root`, not `self._project_root`.

- `find_next_sibling`: same treatment — compute `root = self._root_for_session(session_name)` and use `root / "aitasks" / f"t{parent}"` for the search dir.

### 2. `.aitask-scripts/monitor/tmux_monitor.py`

Expose the cached session→project mapping that `TmuxMonitor` already has internally:

- Add public method `get_session_to_project_mapping(self) -> dict[str, Path]`:
  ```python
  return {s.session: s.project_root for s in self._discover_sessions_cached()}
  ```
  This piggybacks on the existing `_sessions_cache` TTL — no extra tmux calls.

### 3. `.aitask-scripts/monitor/monitor_app.py`

Thread the pane's session through every `_task_cache` call and every `resolve_*` / `AgentCommandScreen` call.

- After `self._monitor = TmuxMonitor(...)` is constructed (and on every refresh tick), update the cache mapping:
  - In `_refresh_data`, after `self._snapshots = await self._monitor.capture_all_async()`, call `self._task_cache.update_session_mapping(self._monitor.get_session_to_project_mapping())`.
  - This catches new tmux sessions started after monitor launch.

- Add a helper:
  ```python
  def _root_for_snap(self, snap: PaneSnapshot) -> Path:
      sess = snap.pane.session_name
      if sess and self._monitor:
          mapping = self._monitor.get_session_to_project_mapping()
          if sess in mapping:
              return mapping[sess]
      return self._project_root
  ```

- Update every call site (line numbers from the current file):

  | line | current call | becomes |
  |------|--------------|---------|
  | 886  | `self._task_cache.get_task_info(task_id)` | `... get_task_info(task_id, snap.pane.session_name)` |
  | 1024 | same | same |
  | 1392-1393 | `invalidate(task_id)` + `get_task_info(task_id)` | pass `snap.pane.session_name` to both |
  | 1416-1433 | `crews_root = self._project_root / ".aitask-crews"` and `cwd=str(self._project_root)` for `ait crew logview` | use `_root_for_snap(snap)` for both |
  | 1451-1453 | `get_task_id` + `get_task_info` | pass session to `get_task_info` |
  | 1487-1497 | `invalidate` + `get_task_info` + `find_next_sibling` | pass `snap.pane.session_name` to all three |
  | 1524-1530 | `get_task_info` + `resolve_dry_run_command(self._project_root, ...)` | pass session; resolve via `_root_for_snap(snap)` |
  | 1546-1550 | `resolve_agent_string(self._project_root, ...)` and `AgentCommandScreen(project_root=self._project_root, ...)` | use `_root_for_snap(snap)` for both |
  | 1590-1591 | `invalidate` + `get_task_info` (restart task) | pass session |
  | 1612 | `resolve_dry_run_command(self._project_root, "pick", task_id)` | use `_root_for_snap(snap)` |
  | 1622-1626 | `resolve_agent_string` + `AgentCommandScreen(project_root=...)` | use `_root_for_snap(snap)` |

- The "next sibling" launch (line 1547-1554) is intentionally launched in the **target task's** project, which is the same as the focused pane's session project (since we're picking a sibling of the same parent). `_root_for_snap(snap)` produces the right value.

### 4. `.aitask-scripts/monitor/minimonitor_app.py`

Same surgery, smaller scope. minimonitor only reads task info (`i` action and the agent card render); no `n` action.

- Add `_root_for_snap(snap)` helper analogous to monitor_app's.
- Wire `update_session_mapping` into `_refresh_data` (where `self._snapshots = await self._monitor.capture_all_async()` runs).
- Update line 377 (`get_task_info` for card render) and line 564 (`invalidate` + `get_task_info` for `i` action) to pass `snap.pane.session_name`.
- Multi-session mode (`M` binding) is what activates this; in single-session mode `session_name` may match `self._session` and the helper returns the correct local root either way.

## Caching subtleties

- **Cache key**: switching from `task_id` to `(session_name, task_id)` is necessary because two projects can both have e.g. `t100`. Acceptable cache-size growth: O(panes), bounded by displayed agent count.
- **Mapping refresh**: `update_session_mapping` is idempotent and free (deferred to `_discover_sessions_cached`'s TTL). Calling it on every tick handles new/closed sessions cheaply.
- **Stale entries**: when a foreign session disappears, its cache entries become inaccessible (no pane references them). They're lightweight; explicit eviction is unnecessary.

## Tests

Extend the existing `tests/test_multi_session_monitor.sh` (already establishes the multi-session test harness) with a new tier covering `TaskInfoCache`:

- **Tier 1j: TaskInfoCache resolves task from per-session project root.** Build two temp dirs `/tmp/projA` and `/tmp/projB`, each with an `aitasks/` containing different `t42_*.md` files (different titles). Construct `TaskInfoCache(project_root=projA, session_to_project={"sessA": projA, "sessB": projB})`. Assert `get_task_info("42", "sessA").title` == projA's title and `get_task_info("42", "sessB").title` == projB's title.
- **Tier 1k: `find_next_sibling` searches the right project.** Same fixture: `/tmp/projA/aitasks/t10/t10_2_*.md` (Ready) and `/tmp/projB/aitasks/t10/t10_3_*.md` (Ready). Assert `find_next_sibling("10_1", "sessA")` returns `("10_2", ...)` and `find_next_sibling("10_1", "sessB")` returns `("10_3", ...)`.
- **Tier 1l: empty `session_name` falls back to local project_root.** Assert `get_task_info("42")` and `get_task_info("42", "")` both resolve via `self._project_root`.
- **Tier 1m: `update_session_mapping` is picked up on subsequent calls.** Construct cache with empty mapping, call `get_task_info("42", "sessA")` → None. Then call `update_session_mapping({"sessA": projA})` and a fresh `get_task_info("42", "sessA")` → resolves.
- **Tier 1n: `TmuxMonitor.get_session_to_project_mapping()` returns the cached sessions as a dict.** Mock `discover_aitasks_sessions` to return two sessions; assert the method returns a `dict[str, Path]` with both entries.

These follow the existing in-process Python test pattern (no real tmux required; the existing Tier 2 harness is left untouched).

## Verification

1. **Unit tests** — `bash tests/test_multi_session_monitor.sh` passes including the new tiers.
2. **Lint** — `shellcheck .aitask-scripts/aitask_monitor.sh .aitask-scripts/aitask_minimonitor.sh` passes (these scripts are not modified, but verifying we didn't break anything by accident).
3. **Manual smoke test** (best-effort, depends on having two aitasks projects open in tmux):
   - Open project A in tmux session `aitasks-A`, open project B in `aitasks-B`. In each, launch a `/aitask-pick` agent (or any `agent-pick-*` window).
   - From session `aitasks-A`, run `ait monitor`, press `M` to enable multi-session.
   - Confirm that the agent rows from session `aitasks-B` show their **correct** task title / priority / status (the bug currently shows them blank or with wrong project's data).
   - Focus a `aitasks-B` agent row, press `n`. Confirm the next-sibling dialog suggests a sibling from project B, and that "Pick" launches the next agent in session `aitasks-B` (not in `aitasks-A`).
   - Repeat with `i` (task info) on a foreign-session row; confirm the popup shows project B's task content.
   - Repeat the `i` test in `ait minimonitor` (after pressing `M`).
4. **Regression** — single-session mode (default, `M` off) still works exactly as before because `session_name` either matches `self._session` (mapping returns the same project_root) or is empty (falls back to `self._project_root`).

## Step 9 (Post-Implementation)

Per the standard task workflow: review changes, commit (code + plan separately via `./ait git`), push, archive via `./.aitask-scripts/aitask_archive.sh 656`. The task has no linked issue, no PR, no folded tasks — straightforward archival.
