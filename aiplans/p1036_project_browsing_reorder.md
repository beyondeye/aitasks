---
Task: t1036_project_browsing_reorder.md
Base branch: main
plan_verified: []
---

# t1036 — Cross-group project browsing in the TUI switcher (+ stats)

## Context

The TUI switcher (`ait`'s `j` overlay) and the stats TUI support two-axis
project-group browsing (added in t1025_2): `[` / `]` cycle which **project
group** is selected, and `←` / `→` cycle the **session ring** derived for that
group. Today the ring is "this group's members **plus** any live out-of-group
session" (`group_sessions(...).ring`), so `←` / `→` can land on repos outside
the selected group, and the switcher's `Session:` row lists *every* session.

The user wants a cleaner two-level model:

- When a group is selected, **show only that group's projects**.
- `←` / `→` now **cross group boundaries**: pressing `→` on the **last** project
  of a group moves to the **first** project of the **next** group (and switches
  the selected group to match); pressing `←` on the **first** project moves to
  the **last** project of the **previous** group.

Confirmed decisions (via clarifying questions):
1. **Global wrap** — `→` on the last project of the last group wraps to the
   first project of the first group (and symmetrically for `←`). One continuous
   ring across all groups.
2. **Per-group display** — the switcher `Session:` row lists only the selected
   group's projects; it re-renders to the next group's projects when a boundary
   is crossed. (The `▶` attached marker is hidden while browsing another group —
   that repo is still reachable by crossing.)
3. **Apply to both** the switcher and the stats TUI, preserving the stats
   aggregate (`__all__`) reachability.

## Design

Both TUIs already consume pure, unit-tested helpers in
`.aitask-scripts/lib/agent_launch_utils.py` (`group_sessions`,
`advance_selected_group`, `default_selected_group`, `_session_in_group`,
`PROJECT_GROUP_UNGROUPED_LABEL`). Add the new traversal as **pure helpers there**
(testable in isolation, no duplication in the TUIs):

### 1. New pure helpers — `agent_launch_utils.py`

- `group_members(sessions, selected_group) -> list[AitasksSession]` — the
  selected group's members only (input order), via the existing
  `_session_in_group`. Unlike `group_sessions(...).ring`, **no** out-of-group
  live append. Used for the switcher row + both `[`/`]` re-point checks.
- `@dataclass(frozen=True) class CrossGroupRingEntry: session: str; group: str | None`
- `cross_group_ring(sessions) -> list[CrossGroupRingEntry]` — flat `←`/`→`
  traversal order across **all** groups: for each group in
  `group_sessions(sessions, None).groups` order (sorted real groups, then the
  synthetic ungrouped bucket), append its members (incl. in-group stale ones,
  matching `group_sessions`), each tagged with its group (ungrouped label
  normalized to `None`). Every project appears exactly once.
- `cross_group_step(entries, current_session, step) -> CrossGroupRingEntry | None`
  — index-wrap a `±1` step over `entries`, matching `.session == current_session`
  (start at 0 if absent); `None` when empty. `entries` may carry caller-appended
  extras (the stats aggregate).

Docstrings reference t1036 and the t1025_2 contract; naming is scope-honest
(`cross_group_*`, `group_members`).

### 2. Switcher — `.aitask-scripts/lib/tui_switcher.py`

- `_cycle_session(step)`: build `cross_group_ring(self._all_sessions)`; guard
  `not self._multi_mode or len(entries) < 2` → `SkipAction` (preserves existing
  single-session/no-widget skip paths). Step via `cross_group_step`, then set
  `self._session = target.session` **and** `self._selected_group = target.group`,
  then `_refresh_after_cycle()`.
- `_cycle_group(step)` (`[`/`]`): after `advance_selected_group`, re-point using
  `group_members(self._all_sessions, self._selected_group)` (replaces the old
  `_ring_names()` reach) — land on the new group's first member when the current
  selection isn't one of its members.
- Replace `_ring_names()` (members + out-of-group live) with the
  `group_members`-based reach; update its now-stale docstring.
- `_render_session_row()`: iterate `group_members(self._all_sessions,
  self._selected_group)` instead of `self._all_sessions`, so the row lists only
  the selected group's projects. Keep the `[group]` prefix and stale/attached
  styling logic unchanged.
- `_render_hint()`: unchanged (still keys off `group_sessions(...).groups`).

### 3. Stats TUI — `.aitask-scripts/stats/stats_app.py`

- `_session_ring()`: return `[e.session for e in cross_group_ring(self.sessions)]
  + [ALL_SESSIONS_KEY]` (aggregate stays a fixed final ring member).
- `_cycle_session(delta)`: append a virtual aggregate entry
  (`CrossGroupRingEntry(ALL_SESSIONS_KEY, self._selected_group)`) to
  `cross_group_ring(...)`, step via `cross_group_step`, and update
  `self._selected_group = target.group` **only when the target is a real
  session** (aggregate is group-agnostic — keep the current group). Then
  `_apply_session_selection(target.session)`.
- `_cycle_group(delta)` (`[`/`]`): re-point check now uses
  `group_members(self.sessions, self._selected_group)` (not the full
  cross-group ring, which would always contain the selection and never
  re-point). Land on the group's first member when the selection falls out;
  fall back to `ALL_SESSIONS_KEY` only if the group is somehow empty.
- The stats `#session_list` sidebar stays a full static list (it is not a
  single-line row; not group-filtered) — only the `←`/`→` / `[`/`]` navigation
  semantics change.

## Tests

- **`tests/test_project_groups.py`** — add a `CrossGroupTests` class covering:
  `group_members` (members only, stale-in-group kept, out-of-group excluded,
  ungrouped bucket); `cross_group_ring` ordering (group-cycle order, ungrouped
  last, every project once, group tags); `cross_group_step` forward/back/global
  wrap and absent-current fallback. Existing `GroupSessionsTests` etc. stay green
  (`group_sessions` is unchanged).
- **`tests/test_tui_group_nav.py`** — update `SwitcherRingTests`,
  `SwitcherPilotTests`, and `StatsRingTests` to the new model: `←`/`→` cross
  boundaries and update `_selected_group`; the row/ring lists only the selected
  group; stats aggregate is the global-final ring member; `[`/`]` re-points onto
  a member of the target group. Add a switcher assertion that `→` on a group's
  last member lands on the next group's first member (and `←` symmetrically).
- **`tests/test_tui_switcher_multi_session.sh`** — verify green unchanged: its
  fixtures are ungrouped (single `(ungrouped)` bucket), so `cross_group_ring`
  reduces to the old single-bucket ring and the forward/back/wrap/SkipAction
  assertions still hold.

## Risk

### Code-health risk: low
- New behavior is added as pure, independently-tested helpers reusing existing
  grouping primitives (`_session_in_group`, `group_sessions`); the TUIs gain no
  duplicated logic. Blast radius is 3 source + 3 test files, all already covered
  by tests. `group_sessions` is left untouched, so its other contracts are
  unaffected. · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- Requirements were ambiguous on three points but are now confirmed via
  clarifying questions; the approach implements each directly. The one edge case
  (stats aggregate position under global wrap) is explicitly handled and tested.
  None identified beyond that. · severity: low · → mitigation: TBD

## Verification

- `python3 -m pytest tests/test_project_groups.py tests/test_tui_group_nav.py -v`
- `bash tests/test_tui_switcher_multi_session.sh`
- `shellcheck` is N/A (Python changes); run the repo's Python test runner if
  present: `bash tests/run_all_python_tests.sh`.
- Manual: in a multi-group tmux setup, open the switcher (`j`), confirm the
  `Session:` row shows only the selected group, `←`/`→` crosses into the
  adjacent group at the ends (wrapping globally), and `[`/`]` still jumps groups.
  Repeat in `ait stats`, confirming `←`/`→` reaches `All sessions (aggregate)`
  and crosses groups, and `[`/`]` lands on a member of the target group.

## Post-implementation

Follow Step 9: this runs on the current branch (profile `fast`), so review the
diff (Step 8), commit code as `enhancement: ... (t1036)` and the plan via
`./ait git`, then archive with `./.aitask-scripts/aitask_archive.sh 1036`.
