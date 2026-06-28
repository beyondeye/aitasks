---
Task: t1007_applink_dataplane_limits_hardening.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
---

# t1007 — applink data-plane resource-limit hardening

## Context

`ait applink` streams tmux pane content to a paired mobile app over a per-connection
WebSocket. The binary data plane (snapshot push loop, t822_8) landed flagging two
residual risks: the new per-connection asyncio push scheduler is fresh concurrency on
the server event loop, and — with no real mobile client — malformed-input / DoS
handling can only be exercised against a synthetic client.

This is the **data-plane-specific slice** of applink hardening; the control-plane
input-validation + admission-control slice already landed in **t985** (`_MAX_PANES`,
`_MAX_STR`, pane-id regex, connection caps, inbound frame-size cap, pre-auth budget).
Since then **t1057 (history RPC / scrollback)** also landed — the push loop now drains
queued `history` pulls (`pusher._drain_history`, `content.request_history` /
`history_rows`), which this plan accounts for. Goal: a malicious or buggy client must
not exhaust server resources or crash the push loop.

The design was adversarially validated; that pass caught a real correctness bug (the
keyframe-drop → append-on-phantom-buffer hole) and a stale-context issue (the t1057
history surface), both reflected here.

Audit of the **current** state (HEAD `9e14f15`, read 2026-06-28):
- **Max panes** — enforced at the router for an *explicit* list (`subscribe` rejects,
  not truncates, > `_MAX_PANES=256`, `router.py:343`). **But** the empty/absent
  `subscribe` path expands to `_discover_pane_ids()` (`router.py:355`) which is **not**
  capped before `apply_subscribe` — so `content.Subscription` (which the push loop
  iterates every tick) is the *only* bound on the roster-subscribe path, and it has no
  cap today.
- **Cadences** — `content.clamp_cadences` (content.py:498) floors idle/focused and
  floors `keyframe_interval_ms` at `MIN_KEYFRAME_INTERVAL_MS=1000`, but has **no upper
  bound** (the doc says the server picks *min* of client value and policy) and **drops
  the connection** on a non-numeric / `inf` / `nan` value (`int("abc")` raises, escapes
  `apply_subscribe`→`handle`→`_route_raw` (which only catches `json` errors)→`_handle`'s
  bare drop).
- **Malformed envelope** — *already* guarded: `FrameRouter.handle` returns BAD_PAYLOAD
  for a non-dict envelope (`router.py:179`), so decoded `[]` / `123` / `"x"` do **not**
  AttributeError. The gap is only the missing regression test (added below). The
  remaining decode risk is `_route_raw` catching only `(ValueError, TypeError)`, so a
  deeply-nested-JSON `RecursionError` within the 64 KB cap escapes to a bare connection
  drop. (Confirmed: **no inbound MessagePack path** — `unpackb` is test-only; inbound is
  JSON, MessagePack is outbound-only.)
- **Frame size** — inbound JSON is byte-capped at 64 KB (`server.py` `max_size`);
  **outbound** binary frames (live keyframe/delta/append/dim **and** t1057 history
  keyframes) have **no** size bound (pathological pane content / a dense max-`count`
  history pull → multi-MB MessagePack frame → mobile decode-bomb + server write-buffer
  blowup).
- **Resilience** — `_run_once` does `await self._push_pane(pane)` per pane (and then
  `await self._drain_history(...)`) with **no** guard; `_loop` catches only
  `asyncio.CancelledError`. A single pane's encode/capture error — or a top-level
  `capture_all_async()` error — propagates out of `_loop` and **kills the whole
  connection's push loop** (unretrieved task exception).

## Approach

Surgical hardening across the four data-plane files + their tests. Principle: enforce
each invariant at its **single sink**, one source of truth per bound, structural fix
over fragile invariant.

### 1. content.py — pane-count + cadence bounds (model-level)

- Add two constants beside the existing cadence floors (~line 55):
  ```python
  MAX_KEYFRAME_INTERVAL_MS = 300000   # 5 min: forced-keyframe resync ceiling
  MAX_SUBSCRIBED_PANES = 256          # canonical pane-count bound (router imports this)
  ```
- `clamp_cadences`: type-safe coercion + keyframe **upper** bound. Add a local
  `_coerce_int(value, default)` catching `(TypeError, ValueError, OverflowError)`
  (covers non-numeric / `null` / list / `inf` / `nan`; `bool`→int is harmless), falling
  back to the `DEFAULT_*_MS` rate (normal/slower, not the fastest floor):
  ```python
  idle = max(_coerce_int(idle_ms, DEFAULT_IDLE_MS), FLOOR_IDLE_MS)
  focused = max(_coerce_int(focused_ms, DEFAULT_FOCUSED_MS), FLOOR_FOCUSED_MS)
  kf = min(max(_coerce_int(keyframe_interval_ms, DEFAULT_KEYFRAME_INTERVAL_MS),
               MIN_KEYFRAME_INTERVAL_MS), MAX_KEYFRAME_INTERVAL_MS)
  ```
  A hostile `cadence_idle_ms:"abc"` now clamps to a safe rate instead of dropping the
  connection. (idle/focused get no *upper* bound by design — a slower cadence only
  self-throttles that client; only the keyframe interval, the anti-divergence anchor,
  needs a ceiling.)
- `Subscription.apply_subscribe`: enforce the model cap **immediately after**
  `self.panes = {...}` (content.py:554) and **before** `self.force |= set(self.panes)`
  (line 563) — so force-seeding *and* the t1057 history-pruning (lines 570-573) both
  see the capped set — unconditionally (covers the absent/non-list path too):
  ```python
  if len(self.panes) > MAX_SUBSCRIBED_PANES:
      self.panes = set(sorted(self.panes)[:MAX_SUBSCRIBED_PANES])
  ```
  This is the *only* bound on the roster-subscribe path (see Context), so it is
  load-bearing, not just belt-and-suspenders; the truncated set is echoed to the client
  via the router's `{"panes": sorted(accepted)}` reply.

### 2. router.py — single source of truth for the pane bound

- `from content import Subscription` → `from content import Subscription, MAX_SUBSCRIBED_PANES`,
  then `_MAX_PANES = MAX_SUBSCRIBED_PANES` (replacing the literal `256`, line 42). Keep
  the router's **reject-not-truncate** client-facing behavior. `R._MAX_PANES` stays a
  plain int at import time (router test `range(R._MAX_PANES + 1)` unaffected). No import
  cycle (`content` imports no project module).

### 3. server.py — inbound decode-bomb guard + thread audit into pusher

- `_route_raw`: broaden the catch to `(ValueError, TypeError, RecursionError)` → return
  BAD_PAYLOAD instead of dropping the connection on nested-JSON `RecursionError`.
  (Inbound > 64 KB already rejected upstream by `max_size`; the only residual inbound
  decode risk is `json.loads` recursion, fully covered — the parsed structure is never
  walked recursively downstream. The non-dict envelope is already handled in `handle`.)
- `_ensure_pusher`: construct `PushScheduler(conn, ws, self._monitor, audit=self._audit)`
  so the scheduler can audit dropped/oversize frames and per-pane faults.

### 4. pusher.py — outbound frame cap + loop resilience

- `import logging`; add `MAX_PUSH_FRAME_BYTES = 2 * 1024 * 1024` (2 MiB — a generous
  hard ceiling: a legit dense full-screen keyframe is low-hundreds-of-KB, and
  `HIGH_WATER_BYTES=256 KB` already coalesces well below this; 2 MiB only trips on
  genuinely pathological/adversarial content, with headroom for ultrawide geometries and
  a max-`count` history pull).
- `__init__(..., audit=None)` → default `logging.getLogger("applink.audit")`
  (backward-compatible: existing tests construct without `audit`; a no-handler logger is
  silent).
- **(C3) Early dead-socket bail in `_push_pane`:** the `pane_status` (line 172) and
  `dim` (line 178) sends precede the content frame. Add `if self._stopped: return`
  immediately **before** `cursor = await self._monitor.capture_cursor_async(...)`
  (line 187) so a dead socket detected on either pre-content send exits at once — no
  wasted cursor capture / parse / encode / doomed re-send, and `force`/state untouched
  (consistent with the existing tail hardening).
- **Outbound size cap at the single sink — `_send` now returns `bool`:**
  ```python
  async def _send(self, data) -> bool:
      if isinstance(data, (bytes, bytearray)) and len(data) > MAX_PUSH_FRAME_BYTES:
          self._audit.warning("PUSH_FRAME_OVERSIZE bytes=%d cap=%d",
                              len(data), MAX_PUSH_FRAME_BYTES)
          return False                  # dropped; NOT a dead socket — do not set _stopped
      try:
          await self._ws.send(data)
      except Exception:
          self._stopped = True
          return False
      return True
  ```
  Binary-only cap (`pane_status` JSON is bounded by construction).
- **(C2) `_push_pane` tail — re-anchor on an oversize drop (fixes the append-on-phantom
  bug), with explicit recovery timing:** capture the content-frame result
  (`delivered = await self._send(frame)`) in the append / delta / keyframe branch. At
  the tail, ordered:
  1. `if self._stopped: return` — dead socket; keep `force`, don't advance (unchanged).
  2. `if not delivered:` — oversize drop. Set `st.row_sigs = None` (next emit is forced
     through the self-contained **keyframe** path — never an append/delta against a
     baseline the client never received) and advance `st.last_hash`, `st.last_dims`,
     `st.last_cursor`, `st.last_keyframe_t`, `st.last_send_t`; `sub.force.discard(pane_id)`.
     Then `return`. **Exact resulting timing (asserted in tests):**
     - *static* oversize content → the next tick emits **nothing** (the
       `changed/forced/interval` gate is all-false: `last_hash` matches, `force` cleared,
       `last_keyframe_t` just reset) — no per-tick re-encode spin; a re-attempt fires at
       most once per `keyframe_interval` (≤ 5 min).
     - content *changes* (e.g. shrinks below the cap) → the next due tick emits a fresh
       **keyframe** (because `row_sigs is None`) that reconstructs full state.
  3. else — normal advance (unchanged).
- **(C4) History keyframes share the cap — clean drop:** `_drain_history` (line 158)
  sends via `_send`, so an oversize history keyframe (a dense max-`count` pull) is
  dropped + audited. This needs **no** re-anchor: history reads `frame_id` without
  advancing the live chain (line 156) and is explicitly best-effort (its token acks
  acceptance, not delivery — content_transport.md §Scrollback), so a drop corrupts no
  live state. Covered by a doc note + a light test.
- **(item 4) Per-unit fault isolation + loop guard:**
  - In `_run_once`, wrap `await self._push_pane(...)` (line 123) in `try/except` —
    `except asyncio.CancelledError: raise` then `except Exception:` audit-warn + `continue`.
    Apply the **same** wrap to the per-pane body of `_drain_history`'s loop (line 147+) so
    one history pane's encode error can't abort the others. The existing top-of-loop
    `if self._stopped: return` still short-circuits a dead socket (no `_stopped` re-check
    needed after the wrap).
  - In `_loop`, wrap `await self._run_once()` (line 96) the same way so a top-level
    `capture_all_async()` error doesn't kill the loop (recovers next tick). Both wraps
    are needed — they guard different sites (one pane vs. the whole pass).

### 5. Tests (synthetic-client behavioral coverage — the stated verification path)

- `tests/test_applink_content.sh`: keyframe interval clamps DOWN to
  `MAX_KEYFRAME_INTERVAL_MS`; a non-numeric / `inf` cadence coerces to default (no
  raise); `apply_subscribe` truncates a > MAX pane set to exactly `MAX_SUBSCRIBED_PANES`.
- `tests/test_applink_pusher.sh`:
  - (a) **oversize-drop + re-anchor (C2 regression for the fixed bug)** — a forced
    keyframe over the cap is dropped + audited, socket stays live, loop not stopped, and
    `row_sigs is None` post-drop; the immediate next tick on **static** content emits
    nothing (no spin); after the content shrinks below the cap the next emit is a fresh
    **keyframe** (not an append) that reconstructs full state.
  - (b) **fault isolation (item 4)** — a monitor whose `capture_cursor_async` raises for
    one pane still lets the other pane emit its keyframe, the loop survives, and the
    suite's existing `loop_excs == []` assertion holds.
  - (c) a `_loop`-level `capture_all_async` error is swallowed and the loop recovers on
    the next tick (no leaked task).
  - (d) **(C4)** a queued history pull whose encoded keyframe exceeds the cap is dropped +
    audited, leaves the pane's live `frame_id`/state unchanged, and does not stop the loop.
- `tests/test_applink_router.sh`: **(C1)** `handle([])` / `handle(123)` / `handle("x")` →
  BAD_PAYLOAD (locks the existing non-dict guard); existing over-long-list test still
  passes after the `_MAX_PANES` indirection (verify).
- `tests/test_applink_server_limits.sh`: a deeply-nested-JSON payload → BAD_PAYLOAD (not
  connection-drop) via `_route_raw`.
- `bash tests/test_applink_smoke.sh` for import-health.

### 6. Docs

Refresh `aidocs/applink/security.md` §DoS-limits (outbound frame cap incl. history,
keyframe upper bound, pane-roster model cap, scheduler fault-isolation, malformed-input
robustness) and `content_transport.md` §Back-pressure / §Scrollback (outbound
`MAX_PUSH_FRAME_BYTES`, re-anchor-on-drop behavior, oversize-history best-effort drop).
Current state only, per doc conventions.

## Risk

### Code-health risk: medium
- The changes touch the **live per-connection push loop** (`_send`, the `_push_pane`
  state-advance tail + early bail, `_run_once`/`_drain_history` per-unit guards, `_loop`)
  — a load-bearing concurrency path — and change `_send`'s contract to return `bool`.
  The re-anchor-on-drop branch, the `_stopped`-vs-`not-delivered` ordering, and the
  early-bail placement must be exactly right or a pane could diverge, spin, or do wasted
  work on a dead socket. · severity: medium · → mitigation: covered in-task by the new
  pusher regression tests (oversize-drop re-anchor timing, fault isolation, loop
  recovery, history-drop)
- Blast radius is 4 source files + 4 test files + 2 docs, all confined to the applink
  data plane; the happy path (normal keyframe/delta/append/history emit) is unchanged.
  · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- All four scope items are covered, the design was adversarially validated (keyframe-drop
  hole closed) and re-verified against the post-t1057 code. · severity: low · →
  mitigation: none needed
- The only residual is the pre-existing **"no real mobile client"** constraint: limits
  are exercised against the synthetic FakeWS/FakeMonitor unit path, not a live `wss://`
  socket or the real aitasks_mobile app. Inherited from t822_8, not introduced here.
  · severity: low · → mitigation: applink_dataplane_live_socket_e2e

### Planned mitigations
- timing: after | name: applink_dataplane_live_socket_e2e | type: test | priority: low | effort: medium | addresses: goal-achievement "no real mobile client / synthetic-only verification" | desc: Exercise the oversize-drop / pane-cap / cadence-clamp / per-pane-fault / oversize-history paths end-to-end through a real wss:// AppLinkServer socket with a scripted synthetic client, vs the current in-process FakeWS/FakeMonitor unit path.

## Files
- `.aitask-scripts/applink/content.py` — constants, `clamp_cadences`, `apply_subscribe`
- `.aitask-scripts/applink/router.py` — `_MAX_PANES` sourced from `content.MAX_SUBSCRIBED_PANES`
- `.aitask-scripts/applink/server.py` — `_route_raw` catch, `_ensure_pusher` audit wiring
- `.aitask-scripts/applink/pusher.py` — `MAX_PUSH_FRAME_BYTES`, `_send` (bool + cap),
  `_push_pane` early bail + re-anchor tail, `_run_once`/`_drain_history`/`_loop` guards,
  ctor `audit`, `import logging`
- `tests/test_applink_{content,pusher,router,server_limits}.sh`
- `aidocs/applink/security.md`, `aidocs/applink/content_transport.md`

## Verification
```bash
bash tests/test_applink_content.sh
bash tests/test_applink_pusher.sh
bash tests/test_applink_router.sh
bash tests/test_applink_server_limits.sh
bash tests/test_applink_smoke.sh
```
Each limit is exercised against the synthetic FakeWS/FakeMonitor client (no tmux, no
sockets), matching the existing data-plane test idiom. See Step 9 (Post-Implementation)
of the task-workflow for cleanup, gate verification, and archival.

## Final Implementation Notes

- **Actual work done:** All four scope items landed as planned, across `content.py`
  (`MAX_KEYFRAME_INTERVAL_MS` / `MAX_SUBSCRIBED_PANES`, `_coerce_int` + keyframe upper
  bound in `clamp_cadences`, the `apply_subscribe` pane cap), `router.py` (`_MAX_PANES`
  imported from `content.MAX_SUBSCRIBED_PANES`), `server.py` (`_route_raw` catch +
  pusher audit wiring), and `pusher.py` (`MAX_PUSH_FRAME_BYTES`, `_send` → `bool` with
  the oversize cap, the `_push_pane` early dead-socket bail + re-anchor-on-drop tail,
  per-pane / per-history / `_loop` fault isolation, ctor `audit`). Docs updated:
  `security.md` §DoS-limits, `content_transport.md` §Back-pressure + §Scrollback.
  Tests: +5 content, +19 pusher, +4 router, +1 server_limits (395 checks total, all
  green; `py_compile` clean; shellcheck only pre-existing SC1091 infos).
- **Deviations from plan:**
  - **`_route_raw` `RecursionError` catch is defense-in-depth, not a reachable
    in-pipeline fix.** Verified empirically: `json.loads` only recurses deep enough to
    raise `RecursionError` at array depth ~100000 (≈200 KB), which the transport
    `max_size` (64 KB) already rejects; a shallower nested-but-decoded value is caught
    by `FrameRouter.handle`'s `isinstance(env, dict)` guard. The catch was kept (cheap,
    upgrades the worst case from a connection-drop to BAD_PAYLOAD) and the code comment
    corrected to say so. The server_limits test exercises it at the unit level (depth
    200000, bypassing the cap). The plan's earlier "within the 64 KB cap" wording was
    inaccurate.
  - `MAX_PUSH_FRAME_BYTES` set to **2 MiB** (not 1 MiB) for headroom on ultrawide /
    dense full-screen + max-`count` history frames; `HIGH_WATER_BYTES` (256 KB) still
    coalesces far below it.
  - The non-object-envelope guard (C1) already existed in `handle` — no code change
    there, only a regression test was added to lock it.
- **Issues encountered:** Mid-session the working tree advanced (main moved past t1055
  to t635_13; **t1057 history RPC landed**), changing `pusher.py`/`content.py`/
  `router.py` and their tests under me after my first reads. Re-read all affected files
  and folded the history surface (`_drain_history`) into the design (the oversize cap
  and fault isolation now cover history keyframes; C4). Also excluded two unrelated
  concurrently-modified files (`aitask_claim_id.sh`, `test_claim_id.sh`) from the commit.
- **Key decisions:** re-anchor on oversize drop sets `st.row_sigs = None` so the next
  emit is a self-contained keyframe (closes the adversarially-found keyframe-drop →
  append-on-phantom-buffer hole) while advancing `last_hash`/`last_keyframe_t` to avoid
  a re-encode spin; `_send` returns `bool` so `_push_pane` distinguishes an oversize
  drop (re-anchor) from a dead socket (`_stopped`, keep `force`); the pane bound is a
  single constant in `content.py` enforced at both the router (reject) and the model
  (truncate, the only bound on the roster path); resilience uses one `try/except` per
  unit (per-pane, per-history-pane) plus a `_loop`-level guard, all re-raising
  `CancelledError`.
- **Upstream defects identified:** None.
