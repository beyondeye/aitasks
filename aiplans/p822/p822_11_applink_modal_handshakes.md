---
Task: t822_11_applink_modal_handshakes.md
Parent Task: aitasks/t822_new_ait_bridge_tui.md
Sibling Tasks: aitasks/t822/t822_12_applink_permissions_doc_sync.md, aitasks/t822/t822_13_applink_headless_monitor_flag.md, aitasks/t822/t822_14_applink_push_scheduler_resilience.md
Archived Sibling Plans: aiplans/archived/p822/p822_7_applink_websocket_listener.md, aiplans/archived/p822/p822_3_monitor_port_design.md
Worktree: (none — profile fast, current branch)
Branch: main
Base branch: main
---

# Plan: t822_11 — applink modal-dialog handshakes

## Context

Parent **t822** builds `ait applink`, the bridge that lets a mobile companion
drive an `ait` workspace over a paired LAN WebSocket. t822_7 shipped the JSON
control plane (`router.FrameRouter` — a pure, socket/tmux-free dispatcher) with
the **kill** confirm round-trip working but `pick_next_sibling`/`restart_task`
left as `UNKNOWN_VERB(deferred)` stubs. This task completes the
**§Modal-dialog handshakes** table from `aidocs/applink/monitor_port_design.md`:
the pull-model confirm/suggest/choose round-trips that replace the desktop
Textual modals for mobile-issued verbs.

**Pull model (already decided):** the client re-sends the gated verb with
`confirmed:true` / a chosen `sibling_id` after the server's first response; the
server never blocks on a dialog reply, so destructive actions stay
client-initiated and idempotent. Correlation is by envelope `id`; gating applies
to the underlying verb tier.

**Execution is intentionally deferred** (design doc §Command-verb mapping): the
kill-old-pane + relaunch-agent orchestration lives in desktop Textual screens
(`AgentCommandScreen` + `launch_in_tmux` + `maybe_spawn_minimonitor`) with no
mobile/server-side launch policy yet. So this task ships the **handshakes + idle
gate**; the confirmed-execution leg returns a deferred signal. A follow-up task
(recorded as an `after` mitigation below) owns building the launch policy and
revisiting that signal.

## Approach

All work centers on the pure `FrameRouter` (`.aitask-scripts/applink/router.py`)
so it stays unit-testable against a stub monitor — the established t822_7 seam.
One small read-only accessor is added to `monitor_core` for pane metadata.

### 1. `router.py` — verb registry + error code

- Move `pick_next_sibling`, `restart_task` **out of** `DEFERRED_VERBS` **into**
  `IMPLEMENTED_COMMAND_VERBS` (so they are gated, not blanket-`UNKNOWN_VERB`).
  `snapshot` stays in `DEFERRED_VERBS`. `KNOWN_VERBS` is unchanged (union).
- Add `restart_task` to `CONFIRM_VERBS` (documentation/grouping; the two-phase
  helper drives behaviour).
- Add error constant `ERR_NOT_IMPLEMENTED = "NOT_IMPLEMENTED"` for the deferred
  execution leg (additive new code — protocol.md §Versioning permits this).

### 2. `router.py` — shared two-phase confirm helper

Add `_two_phase(msg_id, verb, payload, *, build_details, execute)`:

1. `details = build_details()` — `build_details` returns either a `dict` of
   detail fields **or** an `err` frame to short-circuit (e.g. `not_idle`,
   `not_found`). If it's an `err` frame, return it (applies to **both** phases).
2. If `not payload.get("confirmed")` → return
   `res {confirm_required: true, **details}`.
3. Else → return `execute()`.

Refactor `kill_pane` / `kill_window` onto it (behaviour preserved — current test
assertions still hold), and **enrich `kill_pane`'s target** to
`{pane_id, window_name?, task?}` per the design table (degrades to just
`pane_id` when the pane isn't in cache). `kill_window` keeps `{window_id}`
(a `window_id`→pane resolution has no clean seam today — noted as out of scope).

### 3. `router.py` — pane→task resolver helper (session-aware)

Add `_resolve_pane_task(pane_id) -> (pane, task_id, session_name)`:
- `pane = self._monitor.get_pane(pane_id)` (cached `TmuxPaneInfo`, no subprocess).
- `session_name = getattr(pane, "session_name", "")` — **threaded through every
  subsequent task-cache call** (`get_task_info`, `invalidate`, `find_next_sibling`,
  `find_ready_siblings` all accept it; desktop passes `snap.pane.session_name`).
  Omitting it would resolve the wrong task family when applink controls panes
  from a different project/session.
- `task_id = self._tasks.get_task_id_for_pane(pane)` when both are available.
Used by kill-target enrichment and `pick_next_sibling`. `restart_task` derives
the same `session_name` from `snap.pane.session_name`.

### 4. `router.py` — `restart_task` (gate: `full`, idle-gated, two-phase)

Payload `{pane_id, confirmed?}`. `build_details`:
- `snap = self._monitor.capture_pane(pane_id)` — live capture for idle state.
  `None` → `err BAD_PAYLOAD detail:{reason:"not_found"}`.
- `if not snap.is_idle` → `err BAD_PAYLOAD detail:{reason:"not_idle"}`
  (rejected on **both** phases, matching the desktop pre-dialog idle check at
  `monitor_app.py:1716`).
- `session_name = snap.pane.session_name`; resolve `task_id` from `snap.pane`
  (`get_task_id_for_pane`).
- **No resolvable task id** (window name carries none) → `err BAD_PAYLOAD
  detail:{reason:"no_task"}` **before** building confirm details (distinct from
  the `not_found` missing-pane case; matches desktop's "No task ID in window
  name" guard at `monitor_app.py:1723`).
- `invalidate(task_id, session_name)` + `get_task_info(task_id, session_name)`
  for `title`/`status` (tolerate `None` → archived/Done, like desktop
  `action_restart_task`).
- details = `{task_id, title, status, idle_seconds}`.
`execute` (confirmed) → `err NOT_IMPLEMENTED detail:{reason:"deferred", task_id}`.

### 5. `router.py` — `pick_next_sibling` (gate: `full`, suggest/choose)

Payload `{pane_id, sibling_id?}`.
- Resolve `task_id` + `session_name` via `_resolve_pane_task`; missing pane →
  `BAD_PAYLOAD detail:{reason:"not_found"}`, no task id → `BAD_PAYLOAD
  detail:{reason:"no_task"}` (same distinction as `restart_task`).
- **No `sibling_id`** (suggest phase): `invalidate(task_id, session_name)` +
  `get_task_info(task_id, session_name)` for current title/status (tolerate
  `None`); `suggested = find_next_sibling(task_id, session_name)`;
  `ready = find_ready_siblings(task_id, session_name)`;
  `parent_id = get_parent_id(task_id) or task_id`. Reply `res`:
  ```json
  {"suggested": {"id","title"}|null,
   "current": {"id","title","status"},
   "parent_id": "<p>",
   "ready_siblings": [{"id","title","blocked_by":[...]}, ...]}
  ```
  (uses the existing `TaskInfoCache.find_next_sibling` / `find_ready_siblings`,
  `monitor_core.py:1574,1634` — no new task logic).
- **With `sibling_id`** (choose phase): execution deferred →
  `err NOT_IMPLEMENTED detail:{reason:"deferred", sibling_id}`.

### 6. `monitor_core.py` — `TmuxMonitor.get_pane`

Add the lightweight accessor (no subprocess):
```python
def get_pane(self, pane_id: str) -> TmuxPaneInfo | None:
    return self._pane_cache.get(pane_id)
```
(`_pane_cache` already backs `capture_pane`, `monitor_core.py:1172`.)

### 7a. `aitasks/metadata/applink_profiles/full.yaml`

Append `pick_next_sibling` and `restart_task` to `allowed_verbs` (so the `full`
tier can actually reach the handshakes; otherwise always `PERMISSION_DENIED`).
Validated by `aitask_applink_validate_profile.sh` (both are in `KNOWN_VERBS`).
Commit via `./ait git` (shared config on the data branch).

### 7b. `.aitask-scripts/applink/profiles.py` — built-in fallback defaults

`ProfileGate.load` falls back to `DEFAULT_ALLOWED` (`profiles.py:20`) when the
YAML dir is **missing/unreadable**. Append `pick_next_sibling`, `restart_task`
to `DEFAULT_ALLOWED["full"]` (`profiles.py:26`) so the new verbs are reachable
under the built-in defaults too — otherwise a fresh/cloned checkout without the
shipped YAMLs would `PERMISSION_DENIED` them. (The YAML list and `DEFAULT_ALLOWED`
are two intentionally-separate surfaces — shipped config vs no-config fallback —
so both must be updated; they are kept in sync by hand today.)

### 8. `aidocs/applink/protocol.md`

Add `NOT_IMPLEMENTED` to the error-frame `code` enum line (additive). One-line
edit; the verb-gating table sync stays t822_12's job.

### 9. `tests/test_applink_router.sh`

Extend the inline Python harness:
- `StubMonitor`: add `get_pane(pane_id)` → fake `TmuxPaneInfo`-like object with
  `.window_name` **and `.session_name`**; `capture_pane(pane_id)` → fake snapshot
  with `.pane` (incl. `.session_name`), `.is_idle`, `.idle_seconds`
  (parameterizable to drive the idle/not-idle paths).
- Add a `StubTasks` resolver (`get_task_id_for_pane`, `get_task_info`,
  `find_next_sibling`, `find_ready_siblings`, `get_parent_id`, `invalidate`) that
  **records the `session_name` it receives**; build the router with
  `task_resolver=StubTasks()`.
- New/updated checks:
  - kill_pane confirm target now carries `window_name` + `task` (existing
    confirm/execute checks still pass).
  - `restart_task` (idle pane): unconfirmed → `confirm_required` + detail
    `{task_id,title,status,idle_seconds}`, no execution; confirmed →
    `NOT_IMPLEMENTED(deferred)`.
  - `restart_task` (busy pane) → `BAD_PAYLOAD detail.reason == "not_idle"`.
  - `restart_task` (idle pane whose window name resolves to **no task id**) →
    `BAD_PAYLOAD detail.reason == "no_task"`, no confirm details built.
  - `pick_next_sibling` no `sibling_id` → `res` with `suggested`/`current`/
    `parent_id`/`ready_siblings`; **replaces** the old `UNKNOWN_VERB(deferred)`
    assertion (behaviour intentionally changed — see AC update).
  - `pick_next_sibling` with `sibling_id` → `NOT_IMPLEMENTED(deferred)`.
  - permission denial: `monitor_control` bearer calling `restart_task` →
    `PERMISSION_DENIED` (`required_profile == "full"`).
  - **session threading (concern 2):** a fake pane with a non-empty
    `session_name` drives a `pick_next_sibling`/`restart_task` call; assert
    `StubTasks` recorded that exact `session_name` on its
    `find_next_sibling`/`get_task_info` calls (guards cross-project resolution).
  - **fallback defaults (concern 3):** `ProfileGate.load(<missing_dir>)` →
    `is_allowed("full", "pick_next_sibling")` and `... "restart_task")` are both
    `True` (built-in `DEFAULT_ALLOWED` path).

### 10. Coordination & out-of-scope

- **t822_12 reverse pointer:** add a note to
  `aitasks/t822/t822_12_applink_permissions_doc_sync.md` that `full.yaml` already
  carries `pick_next_sibling`/`restart_task` (t822_11) — t822_12 only syncs
  `permissions.md`. Commit via `./ait git` (bidirectional coordination link).
- **`rename_session`:** desktop-only in v1 per the design doc; **out of scope**.
  Not added to `KNOWN_VERBS` → stays plain `UNKNOWN_VERB`. Recorded here so the
  decision is explicit (no silent AC deviation).
- **`kill_window` target enrichment:** out of scope (no clean `window_id`→pane
  seam); keeps `{window_id}`.

## Files

- `.aitask-scripts/applink/router.py` — verb registry, `NOT_IMPLEMENTED`,
  `_two_phase`, `_resolve_pane_task`, `restart_task`, `pick_next_sibling`,
  kill-target enrichment.
- `.aitask-scripts/monitor/monitor_core.py` — `TmuxMonitor.get_pane`.
- `.aitask-scripts/applink/profiles.py` — `DEFAULT_ALLOWED["full"]` +2 verbs.
- `aitasks/metadata/applink_profiles/full.yaml` — +2 verbs (`./ait git`).
- `aidocs/applink/protocol.md` — `NOT_IMPLEMENTED` in error enum.
- `tests/test_applink_router.sh` — handshake coverage.
- `aitasks/t822/t822_12_*.md` — reverse coordination note (`./ait git`).

## Verification

1. `bash tests/test_applink_router.sh` → PASS (all new checks + unchanged ones).
2. `./.aitask-scripts/aitask_applink_validate_profile.sh aitasks/metadata/applink_profiles/full.yaml`
   → OK (new verbs are in `KNOWN_VERBS`).
3. `bash tests/test_applink_smoke.sh` → still PASS (TUI boots; server wiring
   unchanged — router gains methods only).
4. Quick import/parse sanity: `ait`-python imports `router` and `monitor_core`
   without error.
5. (Manual, no mobile client here) the suggest/choose + idle-gate behaviour is
   exercised by the scripted router test, which is the authoritative driver per
   t822_7's testing approach.

## Risk

### Code-health risk: medium
- Refactoring `kill_pane`/`kill_window` onto the shared `_two_phase` helper
  touches the **already-tested confirm path** (load-bearing destructive action).
  · severity: medium · → mitigation: behaviour-preserving refactor, existing
  confirm/execute assertions retained + extended; no new external surface.
- A new `NOT_IMPLEMENTED` protocol error code is fresh wire surface.
  · severity: low · → mitigation: additive per protocol.md §Versioning; clients
  ignore unknown codes; documented in the enum.

### Goal-achievement risk: medium
- Confirmed-execution of `restart_task`/`pick_next_sibling` is **intentionally
  deferred** — partial surface by design, not a gap. The handshakes + idle gate
  are complete; only the relaunch leg is stubbed. · severity: medium
  · → mitigation: applink_workflow_launch_policy (after)
- The `restart_task` idle gate relies on `capture_pane` finding the pane in the
  monitor's `_pane_cache`, which is populated by the push loop; a client acting
  without an active subscription could see `not_found`. · severity: low
  · → mitigation: documented edge; clients interact with panes they are
  subscribed to in normal flow.

### Planned mitigations
- timing: after | name: applink_workflow_launch_policy | type: feature | priority: medium | effort: medium | addresses: goal-achievement "confirmed-execution deferred" | desc: Design and implement the applink workflow launch policy (server-side/mobile) to execute restart_task and pick_next_sibling after the deferred handshake, and reevaluate the NOT_IMPLEMENTED execution leg.

## Step 9 (Post-Implementation)

Standard task-workflow Step 9 (profile `fast`, current branch, no worktree):
code via `git`; `full.yaml` + the t822_12 note + plan via `./ait git`; push via
`./ait git push`; archive via `./.aitask-scripts/aitask_archive.sh 822_11`.
Parent t822 keeps t822_12..t822_14 pending. The `applink_workflow_launch_policy`
"after" mitigation is created at Step 8d.
