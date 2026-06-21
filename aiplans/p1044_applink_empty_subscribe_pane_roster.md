---
Task: t1044_applink_empty_subscribe_pane_roster.md
Worktree: (none — fast profile, current branch)
Branch: current
Base branch: main
---

# t1044 — Empty `subscribe` should mean "all discovered panes"

## Context

The applink data plane never streams anything to the mobile client because the
mobile app (aitasks_mobile `MonitorSessionMediator`) sends `subscribe {panes: []}`
intending "all panes", but the server treats an empty list literally as
"subscribe to nothing". Result on the phone: a permanent "Connected / No panes /
Waiting for first pane…".

Verified by the empirical proof in the task: `subscribe {panes: []}` → 0 pushes;
`subscribe {panes: ["%2","%5"]}` → real `pane_status` + binary keyframes. The data
plane works when panes are named; the bug is purely the empty-list contract
mismatch in `router.py`'s `subscribe` handler, which short-circuits before the
pusher (`pusher._run_once` early-returns on `not sub.panes`).

**Fix:** server-side only, no mobile change. When the `subscribe` payload's
`panes` is empty or absent, expand it to all currently-discovered pane ids before
applying the subscription. The wired monitor is `TmuxMonitor` (server.py:70), which
exposes the synchronous `discover_panes() -> list[TmuxPaneInfo]`
(monitor_core.py:1019); each element's `.pane_id` is the canonical `%N` string used
across the subscription (same keys as `capture_all_async()` → pusher).

**Contract decision (confirmed with user):** empty subscribe = **full content for
all discovered panes** (Option 1). The existing per-pane delta + cadence engine
keeps idle panes near-zero-cost after the initial keyframe; `focus` still raises one
pane's cadence. The more bandwidth-efficient variant (roster `pane_status` for all
panes, binary content only for the focused pane — Option 2) needs coordinated
changes in **both** the applink server and the mobile app, so it is deferred to a
**cross-repo follow-up task** (see "Follow-up" below), not done here.

## Implementation

### 1. `router.py` — expand empty/absent `panes` in the `subscribe` handler

File: `.aitask-scripts/applink/router.py`

Current handler (~L261):
```python
if verb == "subscribe":
    panes = payload.get("panes")
    if not isinstance(panes, list):
        return self._bad_field(msg_id, verb, "panes")
    if conn.subscription is None:
        conn.subscription = Subscription()
    accepted = conn.subscription.apply_subscribe(payload)
    return self._res(msg_id, verb, {"ok": True, "panes": sorted(accepted)})
```

Change to: accept empty **or absent** `panes` as "all discovered panes"; keep
`BAD_PAYLOAD` only for a present-but-non-list value:
```python
if verb == "subscribe":
    panes = payload.get("panes")
    if panes is not None and not isinstance(panes, list):
        return self._bad_field(msg_id, verb, "panes")
    if not panes:
        # Empty or absent `panes` means "all discovered panes" (roster subscribe).
        # The mobile client (aitasks_mobile MonitorSessionMediator) sends panes:[]
        # intending "all"; without this it would subscribe to nothing. See
        # aidocs/applink/protocol.md §Subscription / content_transport.md §subscribe.
        payload = dict(payload)
        payload["panes"] = self._discover_pane_ids()
    if conn.subscription is None:
        conn.subscription = Subscription()
    accepted = conn.subscription.apply_subscribe(payload)
    return self._res(msg_id, verb, {"ok": True, "panes": sorted(accepted)})
```

Add a small helper alongside the other private helpers:
```python
def _discover_pane_ids(self):
    """Pane ids (`%N`) for every currently-discovered pane — the expansion of an
    empty/absent `subscribe`. Degrades to [] if the monitor can't enumerate (so a
    stub/limited monitor keeps the old empty-subscribe behavior rather than erroring)."""
    discover = getattr(self._monitor, "discover_panes", None)
    if not callable(discover):
        return []
    return [p.pane_id for p in discover() if getattr(p, "pane_id", None)]
```

Notes:
- `discover_panes()` does live tmux work, consistent with the handler's other
  monitor calls (`send_enter`, `capture_pane`, `kill_*`) which already do live tmux
  synchronously — the router's "no asyncio/sockets" purity is about dispatch logic,
  not the monitor I/O boundary (mocked via `StubMonitor` in tests).
- `dict(payload)` avoids mutating the caller's request envelope; `apply_subscribe`
  reads cadence/viewport keys from the same payload, so all other keys are preserved.
- This is a **point-in-time** expansion (panes discovered at subscribe time). Panes
  appearing later are not auto-added — documented as a known limitation; a dynamic
  roster push is out of scope (the `snapshot` discovery verb is still deferred).

### 2. Tests

**Unit — `tests/test_applink_router.sh`:**
- Add a `discover_panes` method to `StubMonitor` returning a couple of fake panes
  with `.pane_id` (e.g. `SimpleNamespace(pane_id="%7")`, `"%8"`), driven off a new
  `self.discoverable` list so cases can control it.
- New assertions near the existing subscribe block (~L289):
  - empty `subscribe {panes: []}` → `res ok`, `dconn.subscription.panes` == the
    discovered set, response `payload["panes"]` == sorted discovered set, force set
    seeded with the discovered panes.
  - absent panes (`subscribe {}`) → same expansion (no longer `BAD_PAYLOAD`).
  - present-but-non-list (`subscribe {panes: "x"}`) → still `BAD_PAYLOAD`.
  - explicit list (existing test) still works unchanged.
  - `discoverable = []` → empty subscribe yields empty panes (no crash).

**Live end-to-end — `tests/test_applink_headless_live.sh`:**
- The scripted wss client (~L124) currently subscribes with `{panes:[pane_id]}`.
  Add an **empty subscribe** (`{panes: []}`) against the real running server and
  assert the `res` reply's `payload["panes"]` contains the throwaway session's
  `pane_id` — directly proving "empty = all discovered" end-to-end. Keep it
  skip-capable (the test already SKIPs without tmux/openssl/websockets). Assert at
  the `res` level (deterministic) rather than depending on binary-keyframe timing.

### 3. Docs

- `aidocs/applink/protocol.md` §Pane content transport (Subscription bullet, ~L160):
  note that an empty/absent `panes` list means "all currently-discovered panes".
- `aidocs/applink/content_transport.md` §`subscribe` (~L154): document the
  empty/absent-`panes` = all-discovered-panes contract, the point-in-time nature,
  and the bandwidth consideration (idle panes stay cheap via deltas; the
  focused-only-content efficiency variant is a deferred cross-repo follow-up).

## Follow-up (post-implementation)

Per the user's decision, after the core fix lands create a **cross-repo follow-up**
to design + implement the efficient Option 2 (roster `pane_status` for all panes,
binary content only for the focused/explicitly-subscribed pane). This needs paired
changes in both repos, so file coordinated, bidirectionally-linked tasks:
- **aitasks** (this repo): server-side — split the `Subscription` "status pane set"
  from the "content pane set"; pusher streams `pane_status` for the roster but
  keyframe/delta only for content panes; update the protocol/content_transport docs.
- **aitasks_mobile** (registered in the projects registry): client-side — send the
  roster/focused distinction (or rely on the new contract) in
  `MonitorSessionMediator` / `PaneListPanel`.

Create the aitasks-side task with `aitask_create.sh --batch` and the mobile-side
task with `ait create --batch --project aitasks_mobile`, each carrying a reverse
pointer to the other (`aitasks#<id>` / `aitasks_mobile#<id>` notation per
`aidocs/framework/cross_repo_references.md`).

## Step 9 (Post-Implementation)

Standard cleanup/archival per `task-workflow` Step 9 (current branch — no worktree
merge). Archive t1044 once committed.

## Verification

- `bash tests/test_applink_router.sh` — all PASS (new empty/absent/expansion cases).
- `bash tests/test_applink_pusher.sh` — still PASS (unchanged; confirms the pusher
  streams once `sub.panes` is non-empty).
- `bash tests/test_applink_headless_live.sh` — PASS or SKIP (live empty-subscribe
  roster assertion against the real server).
- `shellcheck` is N/A (Python edits); the `.sh` test files are heredoc-wrapped Python.
- Physical-device end-to-end (paired phone shows populated pane list + focused pane
  content) remains a manual check — offered as a manual-verification follow-up at
  Step 8c; gated behind aitasks_mobile t18 (ws→wss) per the task's Acceptance.

## Risk

### Code-health risk: low
- Change is confined to one `subscribe` handler + a small private helper in
  `router.py`; no change to `Subscription`, `pusher`, or the wire format. The
  `getattr`-guarded `discover_panes` call degrades safely. · severity: low

### Goal-achievement risk: low
- AC ("empty subscribe → populated pane list + focused content, no mobile change")
  is met directly by the expansion; proven end-to-end by the live test. The known
  bandwidth-efficiency limitation is explicitly deferred to the cross-repo
  follow-up, not a silent gap. · severity: low

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned (Option 1). `router.py`
  `subscribe` handler now expands an empty/absent `panes` list to all
  currently-discovered pane ids via the new `_discover_pane_ids()` helper
  (getattr-guarded `discover_panes()` call). Present-but-non-list `panes` still
  returns `BAD_PAYLOAD`. Added unit tests (`StubMonitor.discover_panes` +
  empty/absent/non-list/nothing-discovered cases) and flipped the live headless
  test to an empty subscribe asserting the roster ack includes the throwaway pane.
  Documented the contract in protocol.md and content_transport.md.
- **Deviations from plan:** None.
- **Issues encountered:** None. All suites green on first run — router (102
  checks), pusher (62, unchanged), live headless end-to-end (roster includes the
  throwaway pane `%21` + a binary keyframe was received against the real server).
- **Key decisions:** Empty subscribe streams full content for all discovered panes
  (the existing delta+cadence engine keeps idle panes cheap). The bandwidth-frugal
  variant (roster status for all, content only for the focused pane) was explicitly
  deferred to a cross-repo follow-up (server + mobile) per the user's decision.
- **Upstream defects identified:** None.
