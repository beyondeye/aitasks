---
Task: t1957_trail_cross_repo_blockers_and_linked_trails.md
Base branch: main
Output branch: main
---

### Pre-phase (risk mitigations)
1. [pin_bytrail_no_probe_in_compose] (carried into t1957_1's plan as its first step) Before touching any trail card, add a characterization test in `tests/test_board_bytrail_view.py` that boots By-Trail on a fixture with an `xdeprepo`/`xdeps` member and a `proj#id` ghost, then runs `_rerender_trail` and the card `compose` with `subprocess.run` and `TaskManager.get_xdep_status` patched to raise; assert the render completes. It must pass on the pre-change code and keep passing after t1957_1.

# t1957 — Cross-repo blockers on trail cards + jump to linked trails

## Context

Implementation trails (board By-Trail view and stand-alone `ait trails`) cannot
show that a member is blocked by a task in another registered repo
(`xdeprepo` + `xdeps`), and there is no way to move from a trail in repo X to the
related trail in repo Y. The status machinery already exists
(`TaskManager.cross_repo_dep_display()` / `get_xdep_status()`,
`board_task_manager.py:936,1079`) but `TrailTaskCard` overrides `compose` and
never shows it; cross-repo `proj#id` members render as `cross_repo` ghosts that
are always `landed=False`.

Decisions taken in planning (user-confirmed):
- **Split into children** (below).
- **Live display only.** `xdeps` does NOT enter the trail document (gatherer
  records, digest, schema, skill wave ordering). No digest migration; the 11
  stored trails keep their digests. Finding §2 of the task is closed as
  "not needed for the stated aim".
- **Bootstrap** the target project's tmux session when it is not running
  (same `lib/tmux_bootstrap.sh` the TUI switcher uses).
- No in-flight task overlaps (scan of `Implementing`/`Editing` tasks: no trail work).

## Decomposition (children of t1957)

| child | name | depends |
|---|---|---|
| t1957_1 | trail_card_xdep_blocker_indicator | – |
| t1957_2 | trails_launch_focus_handle | – |
| t1957_3 | cross_repo_linked_trail_discovery | – |
| t1957_4 | jump_to_linked_trail_action | 1957_2, 1957_3 |
| t1957_5 | docs_trail_cross_repo | 1957_1, 1957_4 |

(Children auto-depend on earlier siblings; 1–3 are independent in substance.)
A manual-verification aggregate sibling is offered after creation (TUI flows,
cross-session jump).

Post-approval actions in this session (plan mode is read-only):
1. Create the 5 children via the Batch Task Creation Procedure with the
   context below; write `aiplans/p1957/p1957_<n>_*.md` per child and commit.
2. Create the separate **bug task** for the side finding (`cmd_snapshot`
   makes a foreign single scope id the owner → skill writes the trail to the
   wrong local task): issue_type bug, labels `[trails, cross_repo]`, body =
   the task's "Side finding" section with the two candidate fixes.
3. Revert parent to Ready + unlock (per planning.md child flow).

---

### t1957_1 — Cross-repo blocker indicator + live status for cross-repo ghosts

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

### t1957_2 — `ait trails --trail <handle>` + running-instance focus mailbox

Files: `.aitask-scripts/board/trails_app.py`, `.aitask-scripts/board/board_trail_screen.py`,
`.aitask-scripts/lib/agent_launch_utils.py`, `tests/test_trails_app.py`.

1. `main()`: `--trail <handle>` (validated with
   `artifact_manifest.HANDLE_RE`; invalid → `parser.error`). Passed to
   `TrailsApp(initial_trail=...)`.
2. `on_mount`: with `initial_trail`, run discovery (`_trail_discovery_worker`)
   with a continuation that calls `_activate_trail(handle)` when the handle is
   in `_trail_infos`; otherwise notify "Trail <h> not found in this project"
   and fall back to `_open_trail_select_from_cache`. Add a small
   `_open_trail_by_handle(handle, rescan: bool)` in the mixin used by both the
   cold path and the pane mailbox (handle already known → `_activate_trail`;
   unknown → rescan once, then activate or notify).
3. **Pane-addressed mailbox — exactly one receiver per request.** A
   session-wide env var (the codebrowser pattern) is NOT used: every
   `TrailsApp` in a session would poll it, and `owned_lookup_session` proves
   project ownership, not which window should receive the request. Instead the
   request lives in a tmux **pane user option** on the destination pane only
   (precedent: `MONITOR_KIND_OPTION` / shadow stamps via `set-option -p`):
   - **Request format.** `@aitask_trails_focus` holds `<request_id> <handle>`;
     `request_id` = `uuid.uuid4().hex`, generated by the writer per request.
     Writers only ever **overwrite** it; **nobody ever unsets it** (a pane's
     options die with the pane). Semantics: **latest request wins** — if A and
     B are written between two polls, only B is applied.
   - **Receiver registration.** On mount, when `$TMUX_PANE` is set, a thread
     worker (gateway) first reads the pane's current `@aitask_trails_focus`
     and records its id as the **baseline** `_seen_request_id` (so a request
     left by an earlier instance in the same pane is never replayed), **then**
     stamps its own pane `@aitask_trails_app <os.getpid()>`. Order matters:
     writers target only stamped panes, so any request written after the stamp
     is newer than the baseline. `on_unmount` unsets the `@aitask_trails_app`
     stamp only, best-effort.
   - **Consumption.** Only after registration has recorded the baseline
     (the registration worker's completion callback starts the interval — a
     poll before the baseline exists would replay a leftover request), a 1s
     `set_interval` starts a thread worker (exclusive
     group `trails_focus`) that runs
     `show-options -p -v -t <own $TMUX_PANE> @aitask_trails_focus`. A value
     whose id differs from `_seen_request_id` → set `_seen_request_id = id`
     and post `_open_trail_by_handle(handle)` to the UI thread; same id →
     nothing. **Read-only**: consumption never writes the option, so it cannot
     erase a newer request (read A → writer posts B → next poll sees B's new
     id and applies it). Malformed value / handle failing `HANDLE_RE`
     (untrusted input) → record the id as seen and ignore it. An instance
     never reads another pane's option, so a second `ait trails` in the same
     session cannot take the request. Not in tmux → no registration, no poll.
   Board does not register or poll (the jump always targets `ait trails`).
4. Writer: `launch_or_focus_trails(session, project_root, handle) -> (ok, err)`
   in `agent_launch_utils.py` next to `launch_or_focus_codebrowser`:
   `list-panes -s -t =<session>: -F '#{pane_id} #{window_id} #{@aitask_trails_app}'`
   → receivers = panes whose stamp is a pid that is alive (`os.kill(pid, 0)`;
   same host — a crashed instance launched from a shell leaves its stamp on a
   still-living pane, and must not be chosen). **One** destination is chosen
   deterministically (first receiver in window/pane order); the writer sets
   `@aitask_trails_focus "<uuid4 hex> <handle>"` on that pane id, then `select-window` +
   `select-pane` on it. No receiver → `new-window -t =<session>: -c <root>
   -n trails ./ait trails --trail <handle>` in **argv form** (no shell
   string; handle already HANDLE_RE-validated) — the cold path carries the
   handle in argv, no mailbox involved. All tmux via the `_TMUX` gateway.
   Does not switch-client (caller does).
5. Tests: argparse validation; cold `--trail` activates the trail (fixture
   project, Pilot); unknown handle → selector + notice; registration reads the baseline
   **before** stamping and a pre-existing request is not replayed; consume →
   activate, option left in place, same id not re-applied on the next poll;
   **interleaving**: poll reads A (applies A) → writer posts B → next poll
   applies B (B never erased); A and B both written between polls → only B
   applied; malformed / bad-handle value ignored and not retried;
   **two instances** (two `TrailsApp`s with distinct stubbed `$TMUX_PANE` and a
   fake per-pane option store): writer targets pane B → only B applies it, A's
   poll sees nothing;
   a stamp naming a dead pid is not chosen as a receiver;
   `launch_or_focus_trails` for receiver-present (one and two receivers →
   deterministic single target) and no-receiver branches (stubbed `_TMUX`,
   asserting argv).

### t1957_3 — Cross-repo linked-trail discovery helper

Files: new `.aitask-scripts/lib/trail_links.py`, `tests/test_trail_links.py`
(+ whitelist/extension-point entries per
`aidocs/framework/aitasks_extension_points.md` if a new helper script needs
registering — it is a Python lib with a `__main__`, check the doc).

**Linked-trail relation** (both directions, `proj#id` members count):
trail B (repo Y) is linked to trail A (repo X) when any of
- (fwd-xdeps) a member of A has `xdeprepo: Y` and an `xdeps` id that is a member of B;
- (fwd-member) A has a cross-repo member `Y#id` that is a member of B;
- (rev-xdeps) a member of B has `xdeprepo: X` and an `xdeps` id that is a member of A;
- (rev-member) B has a cross-repo member `X#id` that is a member of A.
Identity is compared as `(realpath(project root), task_id)` — project names
are resolved through `trail_gather.ProjectRoots` (registry resolver), never by
string equality of names (registry name may differ from `project.name`).

1. `python3 trail_links.py export` — run with `cwd=<repo root>`,
   `TASK_DIR=aitasks`: `discover_trails()` there and print one JSON object
   `{local_project, trails:[{handle, name, owner_id, load_error,
   members:[ref...], member_xdeps:{ref:{xdeprepo, xdeps:[...]}}}]}`
   (member xdeps read from that repo's task files, active + archived).
   Uses **this checkout's** Python with the other repo's artifact CLI
   (cwd-relative), so the export works against a repo on an older framework.
2. `find_linked_trails(local_doc, local_member_meta, local_root, exports) ->
   list[LinkedTrail(project, root, handle, name, reasons[str])]` — pure, takes
   exported data, unit-testable.
   `scan_linked_trails(local_doc, ...) -> LinkScan(links, errors, complete)`
   (thread use only). **Candidate projects** = registry entries
   (`aitask_project_resolve.sh list`, self excluded by realpath) ∪ every
   `xdeprepo` named by a local member ∪ the project of every cross-repo member
   ref — so a project the trail directly points at is searched (or reported)
   even when it is missing from the registry. **Nothing is skipped silently:**
   each candidate that cannot be searched becomes a
   `ProjectScanError(project, kind, detail)` with `kind` ∈ `stale` (registered
   path moved/missing), `not_found` (name does not resolve), `export_failed`,
   `timeout`. `complete = not errors`. Export per project via
   `subprocess.run([sys.executable, __file__, "export"], cwd=root, timeout=30)`.
3. Tests: pure relation over synthetic exports for all four directions;
   name≠project.name resolution; unparseable refs ignored; self excluded;
   **a local member with `xdeprepo` naming a STALE registered project →
   `complete=False`, one `stale` error, no links** (and the same for a
   `not_found` xdeprepo); successful empty scan → `complete=True`, no errors;
   export against a fixture repo (tmp git repo with a stored trail) — reuse the
   trail fixtures from `tests/test_trail_discovery.py`.

### t1957_4 — Jump action: pick a linked trail and switch to it

Files: `.aitask-scripts/board/board_trail_screen.py`,
`.aitask-scripts/board/board_trail_view.py` (modal),
`.aitask-scripts/board/trails_app.py`, `.aitask-scripts/board/aitask_board.py`,
`.aitask-scripts/lib/agent_launch_utils.py`, `.aitask-scripts/lib/tui_switcher.py`,
tests `tests/test_board_bytrail_view.py`, `tests/test_trails_app.py`,
`tests/test_trail_screen_host_protocol.py`.

1. Binding `Binding("L", "trail_linked", "Linked Trails")` added to
   `TRAIL_BINDINGS` (`L` is unbound on both App classes today — the board's
   `l`/`L` lock keys live on the detail *screen*; re-check at implementation). Declared on **both** hosts (same object): trails via
   `*TRAIL_BINDINGS`; board placed with `TRAIL_BINDING["trail_linked"]` among
   its rows. Implemented in the mixin, so supported on both — no capability
   entry needed. Footer only in By-Trail with an active trail (`check_action`).
2. `action_trail_linked`: captures the **origin** (`handle` of the active
   trail) and a fresh request stamp `self._trail_link_gen =
   self._bump_trail_gen()`, then starts `@work(thread=True)
   _trail_link_worker(gen, handle)` running `scan_linked_trails` (notice
   "Searching linked trails in N projects…"). Its UI-thread callback
   `_on_trail_links(gen, handle, scan)` **drops the result** unless all hold:
   `gen == self._trail_link_gen` (a newer search or a supersede bumped it),
   `self.base_filter == "bytrail"`, `self._trail_active` is not None and its
   `handle == origin`, and the origin session is still open. Invalidation
   points: a new `L` press (new gen), `_supersede_trail_workers` (leaving or
   re-entering By-Trail) resets `_trail_link_gen`, and `_switch_trail_session`
   / `_close_trail_session` / `_activate_trail` bump it (a search belongs to
   the trail it started from). A dropped result shows nothing.
   On a valid result push `LinkedTrailsScreen`: rows
   `project · handle · name · reasons`; each `ProjectScanError` as a disabled
   row (`<project>: could not search (stale path / not registered / export
   failed / timed out)`). Messages: links empty + `complete` → "No linked
   trails in other projects"; links empty + not `complete` → "No linked trails
   found — N project(s) could not be searched" with the error rows shown (never
   the definitive message).
3. On select → thread worker (guard at execution boundary): re-resolve root;
   `owned_lookup_session(root)`; if None → `bootstrap_project_session(root)`
   (new helper in `agent_launch_utils.py` holding the subprocess call now in
   `TuiSwitcherOverlay._ensure_session_live`, which is changed to call it and
   keeps its own result/STALE handling) then re-lookup; version-skew check
   (target `board/trails_app.py` lacks `--trail` → notify "<Y> runs an older
   aitasks; run `ait upgrade` there", still switch session);
   `launch_or_focus_trails(session, root, handle)`; then
   `switch-client -t =<session>` via gateway. Not in tmux →
   notify with the manual command `ait projects exec <Y> -- ait trails --trail <h>`.
4. Tests: binding identity on both hosts; modal rendering incl. incomplete-
   scan rows and both empty messages; **scan supersession**: search on A then
   switch to B / close A / leave By-Trail before the result lands → no modal;
   two searches completing out of order → only the newest opens; jump worker with
   stubbed resolver/gateway: live session, bootstrap path, bootstrap failure,
   not-in-tmux, version-skew; switcher `_ensure_session_live` regression
   (existing tests keep passing).

### t1957_5 — Docs

`website/content/docs/workflows/cross_project_dependencies.md` (trail
indicator, ghost live status, linked-trail definition, jump) and
`website/content/docs/tuis/trails/` pages (+ board By-Trail mention and the
new `L` key in the keybinding table). Current-state prose only. Run
`cd website && python3 check_links.py --build`.

### Post-phase (risk mitigations)
1. [measure_linked_scan_latency] (carried into t1957_3's plan as its last step) Time `scan_linked_trails` against the real registry on this host (`aitasks_mobile` is registered) and record per-project export timings in t1957_3's Final Implementation Notes. If a single scan exceeds ~2s, add a per-project progress callback and a session-lifetime cache of exports (invalidated by an explicit rescan) before closing the child.

## Verification (parent)

Each child carries its own tests; the parent is done when all children are
archived. Per child: the named test files via
`bash tests/run_all_python_tests.sh --test-dir <dir>` or direct unittest,
`shellcheck` for touched shell, `check_links.py --build` for docs, and a
manual run of `ait trails` against `aitasks_mobile` (registered here) covered
by the manual-verification sibling.

## Step 9 reference

Children are archived individually via their own Step 9; the parent archives
automatically when its last child is archived.

## Risk

### Code-health risk: medium
- The shared `TrailScreenMixin` gains a second per-session worker family (xdep) beside drift; a generation/supersession slip would show stale blocker state on a tab or re-render a closed session · severity: low (residual — addressed by inline pre-phase pin_bytrail_no_probe_in_compose plus the gen-supersession tests in t1957_1) · → mitigation: inline pre-phase pin_bytrail_no_probe_in_compose
- Extracting the bootstrap subprocess out of `TuiSwitcherOverlay._ensure_session_live` touches tested switcher code · severity: low · → mitigation: none (existing switcher tests + new regression in t1957_4)
- The pane-option mailbox is a new cross-process contract (stamp, id-tagged request option never cleared, baseline-at-registration, liveness check) · severity: low · → mitigation: none (interleaving, no-replay, two-instance and stale-stamp tests in t1957_2)
- New `L` binding must be declared on both hosts under the shared `"board"` scope · severity: low · → mitigation: none (host-protocol test in t1957_4)

### Goal-achievement risk: medium
- Linked-trail detection relies on project names resolving (registry) to the same roots on both sides; a project not registered on this host is invisible to the scan · severity: medium · → mitigation: none (accepted: the registry is the framework's only cross-repo addressing; projects the trail points at directly are always searched or reported as `stale`/`not_found` error rows, and an incomplete scan never shows the definitive "no linked trails" message)
- Scanning every registered project on each `L` press (one export subprocess per project, each doing artifact reads per trail) may be slow enough to feel broken · severity: low (residual — addressed by inline post-phase measure_linked_scan_latency) · → mitigation: inline post-phase measure_linked_scan_latency
- A target repo on an older framework has no `--trail`/mailbox, so the jump lands on its trail selector · severity: low · → mitigation: none (detected and notified in t1957_4)

### Planned mitigations
- timing: pre-phase | name: pin_bytrail_no_probe_in_compose | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — xdep worker supersession / probing in compose | desc: characterization test that By-Trail render + _rerender_trail spawn no subprocess (in t1957_1)
- timing: post-phase | name: measure_linked_scan_latency | type: performance | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — linked-trail scan latency | desc: measure scan_linked_trails on the real registry; add progress + export cache if >2s (in t1957_3)
