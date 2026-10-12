---
Task: t1957_1_trail_card_xdep_blocker_indicator.md
Parent Task: aitasks/t1957_trail_cross_repo_blockers_and_linked_trails.md
Sibling Tasks: aitasks/t1957/t1957_2_*.md, aitasks/t1957/t1957_3_*.md, aitasks/t1957/t1957_4_*.md, aitasks/t1957/t1957_5_*.md
Archived Sibling Plans: aiplans/archived/p1957/p1957_*_*.md
Base branch: main
Output branch: main
---

Parent plan (decisions, linked-trail definition, risk record):
`aiplans/p1957_trail_cross_repo_blockers_and_linked_trails.md`.
The task file `aitasks/t1957/t1957_1_trail_card_xdep_blocker_indicator.md` carries the full context,
reference files and line anchors.


### Pre-phase (risk mitigations)
1. [pin_bytrail_no_probe_in_compose] Before touching any trail card, add a characterization test in `tests/test_board_bytrail_view.py` that boots By-Trail on a fixture with an `xdeprepo`/`xdeps` member and a `proj#id` ghost, then runs `_rerender_trail` and the card `compose` with `subprocess.run` and `TaskManager.get_xdep_status` patched to raise; assert the render completes. It must pass on the pre-change code and keep passing after t1957_1.


## t1957_1 — Cross-repo blocker indicator + live status for cross-repo ghosts

Files: `.aitask-scripts/board/board_trail_view.py`,
`.aitask-scripts/board/board_trail_screen.py`, `.aitask-scripts/board/board_task_manager.py`,
tests `tests/test_board_bytrail_view.py` (+ `tests/test_trails_app.py` for the
host path).

Design — status is **per-trail-session state filled by a worker**, never probed
in `compose` (keeps `_rerender_trail`'s t1268 precondition true: cards still
read no `xdep_status_cache`/`lock_map`/`modified_files`):
1. `board_task_manager.py`: factor the classification out of
   `cross_repo_dep_display` into a pure module function
   `classify_xdep_refs(xdeprepo, xdeps, status_of) -> (display: list[str], blocked: bool)`
   (same strings: `ref`, `ref [Status]`, `ref (UNREACHABLE)`; fail closed).
   `cross_repo_dep_display` calls it with `self.get_xdep_status` — behaviour
   unchanged (existing detail-screen/inflight tests pin it).
   Extract `probe_xdep_status(repo, task_id) -> str`, a cache-free module
   function holding the subprocess body of `get_xdep_status` (which now
   delegates to it and keeps its cache). Script path stays cwd-relative as
   today (all TUIs run from the repo root) — extraction only, no behaviour
   change.
2. `TrailSession` gains `xdep: dict | None = None` (ref → status) and
   `xdep_gen: int = 0`. New mixin methods mirroring drift
   (`_start_session_drift` / `_trail_drift_worker` / `_on_trail_drift`):
   `_start_session_xdep(session)` collects refs = (a) every live local member's
   `xdeprepo#xdep` pairs (from `self.manager` task metadata) and (b) every
   `cross_repo` ghost ref of the doc (parsed with `parse_cross_repo_ref`);
   empty set → `session.xdep = {}` and no worker. Otherwise
   `@work(thread=True) _trail_xdep_worker(gen, handle, refs)` probes each with
   `probe_xdep_status` and posts `_on_trail_xdep(gen, handle, result)` via
   `call_from_thread`; the callback drops stale gens (`gen != session.xdep_gen`,
   session closed, not bytrail), stores, and for the active tab calls
   `_rerender_trail(focused filename)`; background tab → `updated=True` +
   `_refresh_trail_tabs` (same shape as `_on_trail_drift`).
   Started wherever `_start_session_drift` is started (activation, reload `R`,
   drift `d`); `r` (zero-subprocess local refresh) re-renders from the cached
   `session.xdep`. `_supersede_trail_workers` retires `xdep_gen` too.
3. `build_trail_lanes(..., drift_by_ref=None, xdep_status=None)`:
   `TrailEntryView` gains `xdeps: list[str]`, `xdep_blocked: bool`,
   `xdep_pending: bool`, and `remote_status: str` (cross-repo ghosts).
   - live local task with `xdeprepo`+`xdeps`: if `xdep_status is None` →
     `xdep_pending=True`, refs listed without status; else
     `classify_xdep_refs(..., status_of=lambda r,i: xdep_status.get(f"{r}#{i}", ""))`.
     Missing key ⇒ `""` ⇒ UNREACHABLE/blocked (fail closed).
   - `cross_repo` ghost: `remote_status = xdep_status.get(canonical ref)`;
     `landed = remote_status == "Done"` (task file of the other repo is the
     source of truth, consistent with the existing "never trust the snapshot"
     rule).
4. `TrailTaskCard.compose`: after the status badge, yield
   `🌐 blocked (cross-repo)` (when blocked) and `↗ <refs joined>` lines,
   `markup=False`; pending → `↗ <refs> (checking…)` with no blocked chip.
   Same glyphs/strings as `TaskCard` (`board_widgets.py:~410-448`).
   `TrailGhostCard.compose` for `cross_repo`: add the live status badge via
   `_status_badge_text(remote_status, "")`, or `(UNREACHABLE)` when the probe
   returned `""`/`NOT_FOUND`, `(checking…)` while pending.
5. Tests (pure + card render, existing `CardApp` pattern in
   `test_board_bytrail_view.py`): classification strings; pending vs
   resolved; missing ref fails closed; ghost landed only on `Done`;
   worker gen supersession incl. tab A→B→A and close-while-in-flight;
   `compose` never calls `get_xdep_status`/`subprocess` (patched to raise).

## Step 9 reference

After implementation and review, follow task-workflow Step 9 (merge if
applicable, archive this child; the parent t1957 archives automatically when its
last child is archived).
