---
Task: t1957_1_trail_card_xdep_blocker_indicator.md
Parent Task: aitasks/t1957_trail_cross_repo_blockers_and_linked_trails.md
Sibling Tasks: aitasks/t1957/t1957_2_*.md, aitasks/t1957/t1957_3_*.md, aitasks/t1957/t1957_4_*.md, aitasks/t1957/t1957_5_*.md
Archived Sibling Plans: aiplans/archived/p1957/p1957_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-12 22:06
---

# t1957_1 — Cross-repo blocker indicator + live status for cross-repo ghosts

## Context

A trail member blocked by a task in another registered repo (`xdeprepo` +
`xdeps`) looks unblocked in By-Trail / `ait trails`: `TrailTaskCard.compose`
(`board_trail_view.py:358`) fully overrides `TaskCard.compose` and shows no deps.
Cross-repo members (`proj#id`) render as `TrailGhostCard` with
`ghost_kind="cross_repo"` and `landed=False` always (`build_trail_lanes`,
`board_trail_view.py:179-221`), even when Done in their own repo.

The status logic exists in `TaskManager.cross_repo_dep_display()`
(`board_task_manager.py:936`) / `get_xdep_status()` (`:1079`), but it probes
**synchronously** (10s subprocess) and caches in `xdep_status_cache`, which
`_rerender_trail` (`board_trail_screen.py:680`) deliberately never touches
(t1268 precondition: trail cards read no `modified_files`/`lock_map`/
`xdep_status_cache`). So status here is **per-trail-session state filled by a
background worker**, never probed in `compose`. Live display only — `xdeps` does
not enter the trail document / digest / skill (decided in parent planning; parent
plan `aiplans/p1957_trail_cross_repo_blockers_and_linked_trails.md`).

## Verification notes (verify pass, 2026-10-12)

All anchors in the original plan still hold. Refinements found while verifying,
plus a review round on cache reconciliation:

- **One start funnel.** Every drift start goes through `_start_session_drift`
  (`board_trail_screen.py:1127`): activation (`:1115`), board view entry
  (`aitask_board.py:3752`), sync completion (`aitask_board.py:5212`), `d`/reload
  and background content changes (`_apply_trail_content`, `:384-418`, reached
  from `_on_trail_reload` with `restart_drift=True`). `_start_session_xdep` is
  called from inside it, so every site is covered. `r`
  (`action_trail_refresh_local`, `:728`) and tab switches
  (`_show_trail_session`) never call it — they stay zero-subprocess.
- **Per-ref coverage, not a whole-map "pending/resolved" flag** (review
  finding, blocking). The original design had `session.xdep is None` ⇒ pending,
  else a missing key ⇒ fail-closed UNREACHABLE. That reports a *failure for a
  ref nobody probed*: after `r` reloads metadata with a new `xdeps` entry (or
  another tab reloads the shared task metadata), the new ref is absent from a
  populated map and rendered UNREACHABLE until some other action re-probes.
  New model — each ref is in exactly one of three states, decided at render
  from session state only:
  - **resolved**: key present in `session.xdep` (completed probe results only;
    `""`/`NOT_FOUND` there = a completed failed probe ⇒ UNREACHABLE, blocked);
  - **checking**: key absent, but in `session.xdep_inflight` (the ref set of the
    current-generation worker);
  - **unchecked**: key absent and not in flight ⇒ rendered `(not checked)`,
    never blocked, never UNREACHABLE.
  The worker's result contains only keys it actually probed, and the callback
  *replaces* the map, so no result — current or superseded — can ever turn an
  unprobed ref into a failure. Superseded results are dropped by `xdep_gen`.
- **Start before render** (review finding). `_apply_trail_content` (active
  branch, `:407-410`) renders and *then* starts drift; `_activate_trail`
  (`:1113-1115`) and the sync worker (`aitask_board.py:5208-5212`) do the same.
  With the coverage model, a render that runs before the start shows new refs
  as `(not checked)` and nothing redraws them until the result lands. Fix by
  ordering: in all three, start drift/xdep first, then render (the worker
  callback is posted via `call_from_thread`, so it always lands after the
  render). Board view entry (`aitask_board.py:3752` → `refresh_board` at
  `:3760`) is already in that order. No extra remounts are added.
- **Supersession clears in-flight coverage.** `_supersede_trail_workers` retires
  `xdep_gen` *and* clears `xdep_inflight`, so a retired worker never leaves a ref
  stuck at `(checking…)`; it shows `(not checked)` until the next start.
- **Patch seam.** `InertPatchGuardTests` (`tests/test_trail_screen_host_protocol.py:708`)
  requires trail-only names to be stubbed on `ab.board_trail_screen`, so
  `board_trail_screen` imports `probe_xdep_status` by name and tests patch
  `ab.board_trail_screen.probe_xdep_status`.
- **Existing negative controls stay green by construction.** `_enter_synthetic_bytrail`
  (`tests/test_board_bytrail_view.py:168`) stubs `_start_trail_drift`, which
  now also gates the xdep worker; the `git`-only spy test (`~:2830`) and
  `LocalRefreshTests` still see no `task-status` probe. Tabbed
  `test_trails_app.py` fixtures use local refs only → empty ref set → no worker.
- **One normalization / one set of strings.** `xdep_ref_pairs()` normalizes ids
  (`str(xd).lstrip('t')`) for both the ref collector and the cards, and
  `classify_xdep_status()` is the single source of the `ref` / `ref [S]` /
  `ref (UNREACHABLE)` strings for both `TaskCard` and the trail cards.

## Pre-phase (risk mitigations)

1. **[pin_bytrail_no_probe_in_compose]** Before touching any trail card, add a
   characterization test in `tests/test_board_bytrail_view.py`: boot By-Trail
   (`_enter_synthetic_bytrail`) on a doc with a live member carrying
   `xdeprepo`/`xdeps` (fixture task with metadata patched in) and a `proj#id`
   ghost; then, with `subprocess.run` and `TaskManager.get_xdep_status` patched
   to raise, call `_rerender_trail()` and `await pilot.pause()`; assert cards
   mounted and nothing raised. Must pass on the pre-change code and after.

## Implementation steps

### 1. `board_task_manager.py` — pure helpers (behaviour-preserving)

Module-level:

```python
def xdep_ref_pairs(xdeprepo, xdeps) -> list[tuple[str, str]]:
    """(repo, id) pairs of a task's cross-repo deps; [] unless both present."""
    if not xdeprepo or not xdeps:
        return []
    return [(str(xdeprepo), str(xd).lstrip('t')) for xd in xdeps]

def classify_xdep_status(ref: str, status: str) -> tuple[str, bool]:
    """Display + blocked for ONE completed probe (fail closed):
    Done → (ref, False); ""/NOT_FOUND → (f"{ref} (UNREACHABLE)", True);
    else → (f"{ref} [{status}]", True)."""

def probe_xdep_status(repo: str, task_id: str) -> str:
    # the subprocess body of get_xdep_status, cache-free (cwd-relative script
    # path, 10s timeout, STATUS: parse, "" on any failure)
```

`cross_repo_dep_display` loops `xdep_ref_pairs` → `classify_xdep_status(ref,
self.get_xdep_status(repo, xid))`; `get_xdep_status` keeps its cache and delegates
the probe to `probe_xdep_status`. Existing detail-screen tests
(`tests/test_board_detail_collapsible.py:227-290`) pin the strings unchanged.

### 2. `board_trail_view.py` — model + cards

- `TrailEntryView` gains defaulted fields (appended, so positional test
  constructors keep working): `xdeps: list = []` (per-ref display strings),
  `xdep_blocked: bool = False`, `remote_state: str = ""`
  (`""` | `resolved` | `checking` | `unchecked`, cross-repo ghosts only),
  `remote_status: str = ""`.
- New pure `trail_xdep_refs(doc, tasks_by_id, local_project) -> dict[str, tuple[str, str]]`
  (`repo#id` → `(repo, id)`): (a) every live local member's `xdep_ref_pairs(...)`;
  (b) every non-local entry ref that `parse_cross_repo_ref` accepts (key via
  `canonical_trail_ref`). Deduped by key.
- New pure `xdep_ref_state(key, status_map, inflight) -> str` returning
  `resolved` / `checking` / `unchecked` (the one coverage rule; cards and tests
  share it).
- `build_trail_lanes(..., drift_by_ref=None, xdep_status=None, xdep_inflight=())`
  (`None` ⇒ `{}`):
  - live local task: for each `(repo, xid)` with key `repo#xid`: resolved →
    `classify_xdep_status(key, map[key])` (accumulate `blocked`); checking →
    `f"{key} (checking…)"`; unchecked → `f"{key} (not checked)"`. Only resolved
    refs can set `xdep_blocked`.
  - `cross_repo` ghost: key = `canonical_trail_ref(ref)`; `remote_state` from
    `xdep_ref_state`; when resolved, `remote_status = map[key]` and
    `landed = remote_status == "Done"` (task file of the other repo is the
    source of truth; snapshot never trusted).
- `TrailTaskCard.compose`: after the status badge, when `xdep_blocked` yield
  `Label("🌐 blocked (cross-repo)", classes="task-info trail-xdep-blocked", markup=False)`;
  when `xdeps` yield `Label(f"↗ {', '.join(xdeps)}", classes="task-info trail-xdeps",
  markup=False)`. Same glyphs/strings as `TaskCard` (`board_widgets.py:427-448`).
- `TrailGhostCard.compose` (only `ghost_kind == "cross_repo"`): after the kind
  line, a `task-info trail-remote-status` label (markup=False): checking →
  `🌐 (checking…)`; unchecked → `🌐 (not checked)`; resolved with `""`/`NOT_FOUND`
  → `🌐 (UNREACHABLE)`; else `_status_badge_text(remote_status, "")`.

### 3. `board_trail_screen.py` — session state + worker

- `TrailSession`: `xdep: dict = field(default_factory=dict)` (completed results
  only), `xdep_inflight: frozenset = frozenset()`, `xdep_gen: int = 0`; add
  `_trail_xdep` / `_trail_xdep_inflight` via `_session_field`.
- `_supersede_trail_workers`: also `session.xdep_gen = gen` and
  `session.xdep_inflight = frozenset()`.
- `_start_session_drift(session)`: after kicking the drift worker, call
  `self._start_session_xdep(session)`.
- New trio mirroring drift:
  ```python
  def _start_session_xdep(self, session):
      """Probe every xdep/cross-repo ref of `session` off-thread. Callers MUST
      start before they render: the render reads `xdep_inflight` to tell a
      ref being checked from one nobody probed."""
      if session.doc is None or session.error:
          return
      refs = trail_xdep_refs(session.doc, self._live_tasks_by_id(),
                             self._get_local_project())
      session.xdep_gen = self._bump_trail_gen()
      session.xdep_inflight = frozenset(refs)
      if refs:
          self._trail_xdep_worker(session.xdep_gen, session.handle, refs)

  @work(thread=True)
  def _trail_xdep_worker(self, gen, handle, refs):
      result = {}
      try:
          for key, (repo, tid) in refs.items():
              result[key] = probe_xdep_status(repo, tid)
      finally:   # partial results still land; unprobed keys stay absent
          self.app.call_from_thread(self._on_trail_xdep, gen, handle, result)

  def _on_trail_xdep(self, gen, handle, result):
      session = self._trail_session(handle)
      if session is None or gen != session.xdep_gen or self.base_filter != "bytrail":
          return
      session.xdep = dict(result)          # replace: only probed keys
      session.xdep_inflight = frozenset()
      if session is not self._trail_active:
          session.updated = True
          self._refresh_trail_tabs()
          return
      focused = self._focused_card()
      self._rerender_trail(focused.task_data.filename if focused else "")
  ```
- **Start-before-render ordering** in the three funnels that render first today:
  - `_apply_trail_content` active branch: `_start_trail_drift()` (when doc ok)
    *before* `_rerender_trail()`.
  - `_activate_trail`: `_start_trail_drift()` (when doc ok) *before*
    `refresh_board()`.
  - `aitask_board.py` sync worker: post `_start_trail_drift` (bytrail only)
    *before* `refresh_board` (after `load_tasks`, which the ref collector needs).
- `_build_active_trail_lanes` passes `xdep_status=self._trail_xdep,
  xdep_inflight=self._trail_xdep_inflight`. (`_resolve_trail_members` keeps the
  defaults — it only warms the archive cache.)
- Update the `_rerender_trail` docstring: cards still read no
  `xdep_status_cache`; xdep state comes from `session.xdep` /
  `session.xdep_inflight`, filled off-thread.
- Import `probe_xdep_status` (from `board_task_manager`) and `trail_xdep_refs`
  (from `board_trail_view`) by name.

### 4. Tests

`tests/test_board_bytrail_view.py`:
- `classify_xdep_status` strings: Done / `[Implementing]` / `""` and `NOT_FOUND`
  → `(UNREACHABLE)`; blocked flag. `xdep_ref_pairs` normalizes `t`-prefixed ids.
- `trail_xdep_refs`: local member pairs + cross-repo ghost refs, dedup, local
  and unparseable refs excluded.
- `xdep_ref_state` + `build_trail_lanes`: resolved / checking / unchecked per
  ref; a mixed member (one resolved-Done ref, one unchecked) is **not** blocked
  and shows `(not checked)`; a completed `""` probe **is** UNREACHABLE+blocked;
  ghost `landed` only on resolved `Done`.
- Card render (`CardApp` pattern, `TrailCardRenderTests`): blocked chip + `↗`
  line; checking/unchecked suffixes and no chip; ghost badge for
  Done / UNREACHABLE / checking / not checked; no xdep labels without xdeps.
- **Dependency introduced after cache population** (Pilot,
  `_enter_synthetic_bytrail`): session map `{A: "Done"}`; add a new xdep `X` to
  the live member's metadata on disk/in manager; run `action_trail_refresh_local`
  with `subprocess.run` recording → zero subprocesses; card shows `A` resolved
  and `X (not checked)`, no `🌐 blocked`, no `UNREACHABLE`.
- Pre-phase test (above).

`tests/test_trails_app.py` (`TabbedSessionTests`, counting-fake style;
`ab.board_trail_screen.probe_xdep_status` patched; for "first render" tests
`app._trail_xdep_worker` replaced by a recorder so the result never lands):
- **First render after artifact content changes**: active tab has a populated
  map; `_on_trail_reload` delivers a doc adding a `proj#9` ghost → the very
  first render shows `🌐 (checking…)` for it, never UNREACHABLE / not checked.
- Activation of a trail with an xdep member: first render shows `(checking…)`.
- **Older in-flight result**: start gen N for `{A}`, then gen N+1 for `{A, X}`;
  deliver gen N's result `{A: ""}` → dropped (A keeps its cached value, X stays
  `checking`); deliver a current-gen result lacking `X` → `X (not checked)`,
  never UNREACHABLE.
- Real worker (patched probe) result reaches the active tab's cards.
- Close-while-in-flight dropped; background result → `updated` + `•`, active
  tab not re-rendered; A→B→A: a result for A landing while B is active marks A
  only, and switching back renders it with no new probe.
- Supersession clears `xdep_inflight` (no stuck `(checking…)`).
- `r` and tab switch: zero probe calls.

### 5. Verification

```bash
python3 -m pytest tests/test_board_bytrail_view.py tests/test_trails_app.py \
  tests/test_board_detail_collapsible.py tests/test_trail_screen_host_protocol.py -q
bash tests/run_all_python_tests.sh   # full suite; read only the final verdict line
```
Manual check (manual-verification sibling): `ait trails` on a trail whose member
carries `xdeprepo: aitasks_mobile` shows the `↗`/`🌐` lines after a moment,
without UI freeze.

## Step 9 reference

After implementation and review, follow task-workflow Step 9 (archive this child;
the parent t1957 archives automatically when its last child is archived).

## Risk

### Code-health risk: medium
- The shared `TrailScreenMixin` gains a second per-session worker family (xdep) beside drift; a generation/supersession slip would show stale blocker state on a tab or re-render a closed session · severity: low (residual — gen/close/A→B→A/older-result tests in step 4) · → mitigation: inline pre-phase pin_bytrail_no_probe_in_compose
- Start-before-render is an ordering invariant across funnels; a future funnel that renders before starting would show `(not checked)` until the result lands · severity: low (cosmetic and truthful-direction: never a false failure) · → mitigation: none (docstring on `_start_session_xdep` + first-render tests for apply-content and activation)
- Hooking the xdep start into `_start_session_drift` means every drift start also spawns `task-status` probes; a test relying on "drift start spawns only the drift verb" could break · severity: low · → mitigation: none (existing negative controls stub `_start_trail_drift`; full python suite in Verification)

### Goal-achievement risk: low
- Probes run sequentially (10s timeout each), so a trail with several unreachable cross-repo refs shows `(checking…)` for a while · severity: low · → mitigation: none (accepted; non-blocking, and the state is truthful)
- An unprobed ref is shown `(not checked)` without the blocked chip, so a dependency added via `r` is not flagged as blocking until `d`/sync re-probes · severity: low · → mitigation: none (deliberate: `r` stays zero-subprocess, and the ref is visibly marked unchecked rather than silently clear)

### Planned mitigations
- timing: pre-phase | name: pin_bytrail_no_probe_in_compose | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — xdep worker supersession / probing in compose | desc: characterization test that By-Trail render + _rerender_trail spawn no subprocess (in t1957_1)
