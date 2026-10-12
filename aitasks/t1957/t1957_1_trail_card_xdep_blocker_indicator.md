---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [trails, board, cross_repo]
gates: [risk_evaluated]
anchor: 1957
created_at: 2026-10-12 21:31
updated_at: 2026-10-12 21:31
---

## Context

Part of t1957 (cross-repo blockers on trail cards + jump to linked trails; parent
plan: `aiplans/p1957_trail_cross_repo_blockers_and_linked_trails.md`).

A trail member blocked by a task in another registered repo (`xdeprepo` +
`xdeps` frontmatter) looks unblocked in the board's By-Trail view and in
`ait trails`: `TrailTaskCard` (`.aitask-scripts/board/board_trail_view.py`
~line 345) overrides `TaskCard.compose` completely and shows no deps. Cross-repo
members (`proj#id` entries) render as `TrailGhostCard` with
`ghost_kind="cross_repo"` and `landed=False` always (`build_trail_lanes`,
~line 179-221), even when Done in their own repo.

The status logic exists in `.aitask-scripts/board/board_task_manager.py`:
`cross_repo_dep_display()` (~936) and `get_xdep_status()` (~1079). It probes
**synchronously** with a subprocess
(`aitask_query_files.sh --project <repo> task-status <id>`, 10s timeout) and
caches in `xdep_status_cache`, which only the board's `refresh_board()` clears.
The board's normal `TaskCard` (`board_widgets.py` ~396-448) calls it inside
`compose` on the UI thread.

`_rerender_trail` (`board_trail_screen.py` ~669) has a t1268 PRECONDITION:
trail cards read none of `modified_files` / `lock_map` / `xdep_status_cache`.
This child must keep that true — status is **per-trail-session state filled by a
background worker**, never probed in compose.

Decided in parent planning: live display only — `xdeps` does NOT enter the
trail document/digest/skill.

## Key Files to Modify

- `.aitask-scripts/board/board_task_manager.py` — extract pure
  `classify_xdep_refs(xdeprepo, xdeps, status_of) -> (display, blocked)` and
  cache-free `probe_xdep_status(repo, task_id) -> str`; existing methods delegate.
- `.aitask-scripts/board/board_trail_screen.py` — `TrailSession.xdep` /
  `xdep_gen`; `_start_session_xdep`, `_trail_xdep_worker`, `_on_trail_xdep`;
  started with drift; supersession.
- `.aitask-scripts/board/board_trail_view.py` — `TrailEntryView` new fields;
  `build_trail_lanes(..., xdep_status=None)`; card compose lines.
- `tests/test_board_bytrail_view.py`, `tests/test_trails_app.py`.

## Reference Files for Patterns

- Drift worker trio: `_start_session_drift` (~1116), `_trail_drift_worker`
  (~1125), `_on_trail_drift` (~1131) in `board_trail_screen.py` — gen stamps via
  `_bump_trail_gen()`, `call_from_thread`, background-tab `updated=True`.
- `_supersede_trail_workers` (~327).
- `TaskCard.compose` glyphs/strings in `board_widgets.py` ~400-448
  (`🌐 blocked (cross-repo)`, `↗ refs`).
- Card render tests: `CardApp` pattern in `tests/test_board_bytrail_view.py`
  (`TrailCardRenderTests` ~316-450); detail-screen xdep test
  `tests/test_board_detail_collapsible.py:227-290` pins the display strings.
- `cross_repo_notation.parse_ref` / `canonical_trail_ref` / `trail_ref_to_local_id`.

## Implementation Plan

0. **Pre-phase [pin_bytrail_no_probe_in_compose]** (risk mitigation, do FIRST):
   characterization test that boots By-Trail on a fixture with an
   `xdeprepo`/`xdeps` member and a `proj#id` ghost, runs `_rerender_trail` and
   card `compose` with `subprocess.run` and `TaskManager.get_xdep_status`
   patched to raise; render completes. Must pass before and after this change.
1. Extract `classify_xdep_refs` + `probe_xdep_status` (behaviour-preserving;
   strings `ref`, `ref [Status]`, `ref (UNREACHABLE)`; fail closed: anything
   but `Done` blocks, `""`/`NOT_FOUND` = UNREACHABLE).
2. Session state + worker: refs = live local members' `xdeprepo#xdep` pairs ∪
   `cross_repo` ghost refs; empty → `session.xdep = {}`, no worker. Worker probes
   with `probe_xdep_status`; callback drops stale gen / closed session / not
   bytrail; active tab → `_rerender_trail(focused)`; background tab →
   `updated=True` + tab refresh. Start alongside every `_start_session_drift`
   call site (activation, `R`, `d`); `r` re-renders from cached state only;
   `_supersede_trail_workers` retires `xdep_gen`.
3. `build_trail_lanes(..., xdep_status=None)`: `TrailEntryView` gains
   `xdeps: list[str]`, `xdep_blocked: bool`, `xdep_pending: bool`,
   `remote_status: str`. Local member: `None` → pending; else classify with
   `xdep_status.get(ref, "")` (missing ⇒ blocked/UNREACHABLE). Cross-repo ghost:
   `remote_status` from map; `landed = remote_status == "Done"`.
4. Cards: `TrailTaskCard` yields `🌐 blocked (cross-repo)` + `↗ refs` (or
   `↗ refs (checking…)` while pending, no chip), `markup=False`.
   `TrailGhostCard` (cross_repo) yields a status badge
   (`_status_badge_text(remote_status, "")`, `(UNREACHABLE)`, or
   `(checking…)`).
5. Tests: classification strings; pending vs resolved; missing ref fails
   closed; ghost landed only on Done; worker gen supersession incl. tab A→B→A
   and close-while-in-flight; compose never probes.

## Verification

- `python3 -m pytest tests/test_board_bytrail_view.py tests/test_trails_app.py tests/test_board_detail_collapsible.py tests/test_trail_screen_host_protocol.py -q`
  (or `bash tests/run_all_python_tests.sh --test-dir tests` with
  `AIT_TEST_PARALLEL=0` if pytest is absent); read only the final verdict line.
- Manual (covered by the manual-verification sibling): `ait trails` on a trail
  with a member carrying `xdeprepo: aitasks_mobile` shows `↗`/`🌐` lines after a
  moment, without UI freeze.
