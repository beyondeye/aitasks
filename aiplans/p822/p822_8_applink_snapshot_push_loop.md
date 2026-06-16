---
Task: t822_8_applink_snapshot_push_loop.md
Parent Task: aitasks/t822_new_ait_bridge_tui.md
Sibling Tasks: aitasks/t822/t822_9_applink_delta_engine.md, aitasks/t822/t822_10_applink_append_fastpath.md, aitasks/t822/t822_11_applink_modal_handshakes.md, aitasks/t822/t822_12_applink_permissions_doc_sync.md, aitasks/t822/t822_13_applink_headless_monitor_flag.md
Archived Sibling Plans: aiplans/archived/p822/p822_6_extract_monitor_core.md, aiplans/archived/p822/p822_7_applink_websocket_listener.md
Worktree: (none — profile fast, current branch)
Branch: main
Base branch: main
---

# Plan: t822_8 — applink snapshot push loop (data plane Stage 1)

## Context

Parent **t822** builds `ait applink`, the bridge that lets a mobile companion
drive an `ait` workspace over a paired LAN WebSocket. The **control plane** (JSON
verbs: pairing, auth, profile gating, key forwarding, kill/focus) landed in
**t822_7**. This task adds **Stage 1 of the binary data plane**: streaming tmux
pane *content* to mobile as MessagePack frames.

Concretely: parse `tmux capture-pane -e` output once on the server into the
**styled-span row schema** fixed by `aidocs/applink/content_transport.md`, encode
`keyframe`/`cursor`/`dim` frames (1-byte type tag + MessagePack), and push them on
a per-pane cadence driven by the mobile `subscribe`/`focus` control verbs. The
wire format is **fixed — consumed, not redefined**. Stage 2 `delta` (t822_9) and
Stage 3 `append` (t822_10) are explicitly **out of scope** here; their encoders
arrive with those siblings.

t822_7's Final Implementation Notes hand off precisely: the server already owns a
`TmuxMonitor` + `capture_all_async` substrate and a pure `FrameRouter`;
`subscribe`/`request_keyframe` currently return `UNKNOWN_VERB(deferred)` and just
need promoting; dispatch is extended by adding verbs to `router.py`.

## Key decisions (confirmed with user)

1. **Encoder home = new applink module, not `monitor_core`.** The SGR parser +
   MessagePack encoders live in `.aitask-scripts/applink/content.py`, NOT in
   `monitor_core.py`. This keeps the new `msgpack` dependency out of the
   board/monitor TUI import path (those import `monitor_core`). The *shared
   capture pipeline* (`capture_all_async`) stays in `monitor_core` exactly as the
   design doc intends; only the applink-specific **wire encoding** moves out.
   Minor wording deviation from `monitor_port_design.md` §Deltification ("in
   monitor_core") — t822_9's deltifier will extend `content.py`.

2. **`focus` stays `monitor_control+`; read_only fast-watch via `subscribe`
   cadence.** The design doc's "read_only focus = cadence-only" is *not*
   implemented. Reasoning (answer to user's question): a read_only client that
   wants to live-tail one pane simply subscribes to that single pane with a fast
   `cadence_idle_ms` (clamped by the server policy floor) — no `focus` verb
   needed. So `focus` remains purely a *control* verb (switch + raise cadence for
   `monitor_control+`); cadence is purely a *subscribe* concern. Avoids changing
   an existing verb's gating and a tier-conditional branch in the pure router.
   The one sentence in `monitor_port_design.md` §Focus-state forwarding is
   corrected to match.

3. **`msgpack` confined + lazily imported.** `content.py` imports `msgpack` only
   inside the `encode_*` functions, so importing `Subscription`/parser helpers
   (e.g. from the router unit test) needs no msgpack. Tests skip gracefully when
   msgpack is absent (mirrors the existing pyyaml skip in `test_applink_router.sh`).

## Architecture

```
server.AppLinkServer (asyncio transport — existing)
  _handle(ws): text frames → router.FrameRouter.handle(env, conn)   [pure]
      router mutates conn.subscription (pure Subscription state)
  after each handle: if conn.subscription has panes → ensure a per-conn
      pusher.PushScheduler task is running; wake it (immediate push of force set)
  on close: cancel the conn's PushScheduler

pusher.PushScheduler (NEW, asyncio, one per connection)
  loop: sleep(min cadence) → monitor.capture_all_async() (shared) →
        per subscribed pane: emit dim (on resize) + keyframe (on change /
        interval / forced) as binary; emit pane_status JSON at idle cadence
  back-pressure: skip a tick's sends when ws write buffer > high-water

content.py (NEW, pure + lazy-msgpack)
  parse_sgr_line / snapshot_to_rows  (SGR state machine → styled spans)
  char_width / span width (tmux-compatible best-effort)
  encode_keyframe / encode_cursor / encode_dim  (1-byte tag + msgpack)
  Subscription (pure dataclass: panes, cadences, focus, per-pane frame state)
  cadence floor constants + clamp helper

monitor_core.TmuxMonitor
  + capture_cursor_async(pane_id) -> (row, col, visible, style) | None
```

## Implementation

### 1. `.aitask-scripts/applink/content.py` (NEW — pure, unit-testable)

- **Span/row schema** (`content_transport.md` §Row encoding): span =
  `[text, fg, bg, attrs, width]`; row = `[row_id, [span,...]]`.
- **`parse_sgr_line(line) -> (spans, osc8_urls)`** — ad-hoc SGR state machine
  (NOT pyte — input is pre-rendered by tmux: only SGR runs + OSC8 remain). Track
  `(fg, bg, attrs)` across `ESC[…m`; split into spans on style change; strip all
  escapes from `text`. fg/bg per spec: `null`=default, `0-255`=palette,
  truecolor packed negative. attrs bitfield (bold/italic/underline/reverse/
  strike/blink/dim/hyperlink). OSC8 (`ESC]8;;URI ST … ESC]8;; ST`) sets attr bit 7
  and collects the URL into the frame-level `osc8` sidecar (flat row-major span
  offset → url).
- **`char_width(ch)` / span width** — combining/zero-width → 0; East Asian
  Wide/Fullwidth (`unicodedata.east_asian_width`) → 2; else 1. Best-effort tmux
  parity (server is authoritative per design goal 5; mobile uses verbatim).
  Documented approximation.
- **`snapshot_to_rows(content) -> (rows, osc8)`** — split `PaneSnapshot.content`
  into lines, parse each, assign `row_id` from 0 (top of viewport).
- **Frame encoders** (lazy `import msgpack`): each returns `bytes` =
  `bytes([TYPE]) + msgpack.packb(remainder_array)` where the 1-byte type tag is a
  **raw leading byte** and the MessagePack array holds the *remaining* fields
  (per content_transport.md's "1-byte type tag … remainder is MessagePack" prose).
  - `encode_keyframe(pane_id, frame_id, cols, rows, cursor, row_list, osc8=None)`
    → `\x01` + packb(`[pane_id, frame_id, cols, rows, cursor, row_list]` + `[osc8]`
    only when non-empty).
  - `encode_cursor(pane_id, frame_id, cursor)` → `\x04` + packb(`[pane_id, frame_id, cursor]`).
  - `encode_dim(pane_id, cols, rows, palette_hash=0)` → `\x05` + packb(`[pane_id, cols, rows, palette_hash]`).
  `cursor = [row, col, visible, style]`. (Stage 1 `palette_hash`=0 constant;
  `delta`/`append` encoders are t822_9/t822_10.)
- **`Subscription` dataclass** (pure, no msgpack at import): `panes: set[str]`,
  `cadence_idle_ms`, `cadence_focused_ms`, `keyframe_interval_ms`,
  `focused_pane: str|None`, `viewport_hint` (stored, ignored Stage 1), and
  per-pane state `_pane: dict[pane_id -> {frame_id, last_hash, last_dims,
  last_keyframe_t, last_send_t}]`, plus `force: set[str]`. Methods:
  `apply_subscribe(payload, floor)`, `request_keyframe(pane)`, `set_focus(pane)`,
  `cadence_for(pane)`, `next_tick_ms()`, `next_frame_id(pane)`.
- **Cadence floor constants + `clamp_cadences(...)`** — e.g.
  `FLOOR_FOCUSED_MS = 200`, `FLOOR_IDLE_MS = 500`, keyframe-interval bounds.
  Server clamps client requests up to its policy floor.

### 2. `.aitask-scripts/applink/router.py` (MODIFY — pure dispatch)

- Move `subscribe`, `request_keyframe` from `DEFERRED_VERBS` →
  `IMPLEMENTED_COMMAND_VERBS`. **Keep `snapshot` in `DEFERRED_VERBS`** (it's the
  read-capability profile token / push direction, never a pulled verb).
  `KNOWN_VERBS` is unchanged (already unions all three sets) so the profile
  validator still accepts every token.
- Thread `conn` into `_dispatch` (`_dispatch(self, msg_id, verb, payload, conn)`)
  and update the single call site in `handle()`.
- New handlers in `_dispatch`:
  - `subscribe`: validate `panes` (list[str]); build/refresh `conn.subscription`
    via `Subscription.apply_subscribe(payload, floor)`; add all panes to the
    force set (initial keyframes); return `res {ok, panes}`.
  - `request_keyframe`: `conn.subscription.request_keyframe(pane_id)`; return
    `res {ok}`. (No-op-safe if no subscription yet.)
- Extend `focus` handler: also `conn.subscription.set_focus(pane_id)` (raise
  cadence) **in addition to** the existing `switch_to_pane`. Gating unchanged
  (`monitor_control+`).
- `ConnState.__init__`: add `self.subscription = None`.

### 3. `.aitask-scripts/applink/pusher.py` (NEW — asyncio, per-connection)

- `class PushScheduler` constructed with `(conn, ws, monitor)` — all
  **dependency-injected and duck-typed** for testability: `ws` only needs an
  async `send(data)`; `monitor` only needs `capture_all_async()` +
  `capture_cursor_async(pane_id)` + `discover`-cached `_pane_cache` access (or the
  pane dims carried on each snapshot's `.pane`); `conn.subscription` is the pure
  `Subscription`. No real tmux/socket required to drive it.
- Owns an `asyncio.Event` `_wake`, a `_stopped` flag, and a `_task`.
  `start()` schedules `_loop()`; `wake()` sets the event (called by the server
  after a subscribe/request_keyframe so the force set flushes immediately);
  `async stop()` sets `_stopped`, sets `_wake`, cancels `_task`, and **awaits it**
  (with `contextlib.suppress(CancelledError)`) so teardown is deterministic.
- **`async def _run_once(self)` is the single testable emit pass** (one
  capture→encode→send cycle). `_loop()` is the thin driver:
  `while not self._stopped: await wait_for(self._wake.wait(),
  timeout=sub.next_tick_ms()/1000) (suppress TimeoutError); self._wake.clear();
  await self._run_once()`. Splitting `_run_once` out lets the unit test assert one
  deterministic pass without racing timers.
- In `_run_once`: `snaps = await monitor.capture_all_async()`.
  For each `pane_id in sub.panes`:
  - snap missing → pane gone, skip.
  - dims `(pane.width, pane.height)`; if changed vs `last_dims` → `encode_dim`,
    send, force a keyframe.
  - send keyframe when: content hash changed **or** pane in `force` **or**
    `keyframe_interval` elapsed, **and** pane's own cadence interval elapsed
    (`now - last_send >= sub.cadence_for(pane)`). Build via `snapshot_to_rows`
    + `capture_cursor_async`; `frame_id = sub.next_frame_id(pane)`; `encode_keyframe`;
    `await ws.send(frame_bytes)`. Update per-pane state; discard from `force`.
  - **Idle panes cost zero bytes** (no change, not forced, interval not elapsed →
    nothing sent; no cursor fetch).
- **`pane_status` JSON push** at idle cadence: `await ws.send(json.dumps({"v":1,
  "kind":"push","verb":"pane_status","payload":{pane_id, idle_seconds, is_idle,
  awaiting_input, awaiting_input_kind, window_name, category, session_name,
  task_id}}))`. `task_id` via `monitor_core.task_id_from_window_name` (cheap,
  pure). Task title/status stay behind the existing `task_detail` verb (pulled on
  tap) — documented Stage-1 scope.
- **Back-pressure** (`content_transport.md` §Back-pressure): before sends, if
  `getattr(ws.transport, "get_write_buffer_size", lambda: 0)()` exceeds a
  high-water (256 KB), skip this tick's sends (coalesce; cursor frames are not
  emitted standalone anyway). Wrap sends in try/except → on send failure, stop.
- **Standalone `cursor` (0x04) emission is deferred** (encoder implemented +
  tested, but the scheduler folds cursor into keyframes so idle panes stay at
  zero bytes — detecting cursor-only motion would require a per-tick cursor fetch
  per pane). Documented Stage-1 limitation.

### 4. `.aitask-scripts/applink/server.py` (MODIFY — lifecycle wiring)

- Add `self._pushers: dict[ConnState, PushScheduler] = {}`.
- In `_handle`, after `reply = self._route_raw(raw, conn)` and the `touch`:
  if `conn.subscription is not None and conn.subscription.panes`: lazily create
  + `start()` a `PushScheduler(conn, ws, self._monitor)` (store in `_pushers`),
  then `pusher.wake()`.
- In the `finally`: `pusher = self._pushers.pop(conn, None)`; if present,
  `await pusher.stop()`.

### 5. `.aitask-scripts/monitor/monitor_core.py` (MODIFY — one small helper)

- Add `async def capture_cursor_async(self, pane_id) -> tuple[int,int,bool,int]|None`:
  `display-message -p -t <pane> -F "#{cursor_y} #{cursor_x} #{cursor_flag}"` via
  `self._tmux_async`; parse → `(row, col, visible, style=0)`; `None` on error.
  (Block-cursor style only in Stage 1.) Justified in the shared core as a tmux
  primitive alongside `capture_pane_async`.

### 6. Profiles + dependency + validator (MODIFY)

- `aitasks/metadata/applink_profiles/{read_only,monitor_control,full}.yaml` — add
  `subscribe` and `request_keyframe` to each `allowed_verbs` (gated like
  `snapshot`, present in all three). `focus` left as-is (monitor_control+ only).
- `.aitask-scripts/applink/profiles.py` — mirror the same additions in
  `DEFAULT_ALLOWED` (built-in fallback, all three tiers).
- `.aitask-scripts/aitask_setup.sh` — add `'msgpack>=1,<2'` to
  `AIT_PIP_SPECS_CPYTHON_EXTRA` and `msgpack` to `AIT_IMPORTS_CPYTHON_EXTRA`
  (CPython-only; applink never runs under the PyPy board fast-path).
- `.aitask-scripts/aitask_applink.sh` — add `msgpack` to the `missing=()` import
  probe alongside `textual`/`segno`/`websockets`.
- permessage-deflate is mandatory and **already on by default** in
  `websockets.serve`; leave default negotiation, note it in code.

### 7. Doc correction (MODIFY)

- `aidocs/applink/monitor_port_design.md` §Focus-state forwarding — replace the
  "under read_only the cadence change applies…" sentence with the implemented
  behavior: `focus` is `monitor_control+` (switch + raise cadence); read_only
  raises a pane's cadence by subscribing to it with a fast `cadence_idle_ms`.
  (Current-source-accurate per doc conventions.)

### 8. Tests

- **`tests/test_applink_content.sh` (NEW)** — skip if `msgpack` absent (mirror
  the pyyaml skip). Pure assertions:
  - plain line → one span, `fg/bg=null`, `attrs=0`, `width=len`; **no `\x1b`
    survives in any `text`**.
  - 256-color + truecolor fg/bg encode correctly; bold/underline/reverse → right
    attr bits; style change splits spans.
  - OSC8 → attr bit 7 set + URL in the `osc8` sidecar at the right offset.
  - wide char → width 2; combining mark → width 0.
  - `encode_keyframe/cursor/dim`: leading type byte == `0x01/0x04/0x05`;
    `msgpack.unpackb(rest)` round-trips the field array; `osc8` only present when
    hyperlinks exist.
  - `Subscription`: `apply_subscribe` clamps cadences to the floor; `subscribe`
    seeds the force set; `request_keyframe` adds to force; `cadence_for(focused)`
    == focused cadence.
- **`tests/test_applink_router.sh` (EXTEND)** — against the stub monitor:
  - `subscribe` (monitor_control bearer) → `res`, `conn.subscription.panes` set,
    force set seeded; `subscribe`/`request_keyframe` no longer return
    `UNKNOWN_VERB` and are in `KNOWN_VERBS`.
  - `request_keyframe` adds the pane to the force set.
  - `focus` → stub `switch_to_pane` recorded **and** `conn.subscription.focused_pane`
    set.
  - read_only `subscribe` allowed (in profile); read_only `focus` still
    `PERMISSION_DENIED` (unchanged).
- **`tests/test_applink_pusher.sh` (NEW)** — async unit tests for the riskiest
  new piece (the scheduler), via `asyncio.run`, with a **fake WS** (async `send`
  recording every frame) and a **fake monitor** (`capture_all_async` returns a
  canned `PaneSnapshot` for one pane; `capture_cursor_async` returns a fixed
  cursor). Skip if `msgpack` absent. Cases:
  - **emit:** build a `Subscription` with one pane forced; `await
    sched._run_once()`; assert the fake WS received a **binary keyframe** (first
    byte `0x01`, `msgpack.unpackb(rest)` decodes to the field array) **and** a
    `pane_status` JSON text frame.
  - **idle = zero bytes:** second `_run_once()` with unchanged content and no
    force / interval elapsed → no new binary frame sent.
  - **resize → dim:** change the fake pane's dims between passes → a `0x05` dim
    frame precedes the fresh keyframe.
  - **lifecycle teardown:** `sched.start(); sched.wake()`; let one pass run; then
    `await sched.stop()` and assert `sched._task` is done/cancelled (no leaked
    task, no exception) and a post-stop `wake()` triggers no further sends.
- Existing `test_applink_smoke.sh` / `test_applink_devices.sh` must still pass.

## Verification

1. `bash tests/test_applink_content.sh` → PASS (parser, encoders, Subscription).
2. `bash tests/test_applink_router.sh` → PASS (subscribe/request_keyframe/focus
   cadence + gating; existing cases green).
3. `bash tests/test_applink_pusher.sh` → PASS (scheduler emit/idle/resize/teardown).
4. `bash tests/test_applink_smoke.sh` && `bash tests/test_applink_devices.sh` → PASS.
5. `shellcheck .aitask-scripts/aitask_applink.sh` → clean.
6. `./.aitask-scripts/aitask_applink_validate_profile.sh aitasks/metadata/applink_profiles/full.yaml`
   → OK (new verbs validate against `KNOWN_VERBS`).
7. Python import sanity: `python -c "import applink.content, applink.pusher"`
   (with venv) — no import errors; msgpack lazily loaded.
8. **Live end-to-end (manual — real mobile client is cross-repo / unavailable):**
   `./ait applink`, pair a scripted `python websockets` client pinning the cert
   fingerprint, `subscribe` to a live pane → decode a valid `keyframe`; resize the
   desktop terminal → receive `dim` + fresh keyframe; focused pane updates at
   ~0.3 s while an idle pane sends zero bytes; `request_keyframe` returns a fresh
   keyframe within one tick; observe `pane_status` JSON pushes. → covered by a
   **manual-verification follow-up task** (offered at workflow Step 8c).

## Step 9 (Post-Implementation)

Profile `fast`, current branch (no worktree). Code via `git`; profile YAMLs + the
plan via `./ait git`. Push via `./ait git push`. Archive this child via
`./.aitask-scripts/aitask_archive.sh 822_8` — parent t822 keeps t822_9..t822_13
pending. Sibling note (in Final Implementation Notes) for **t822_9** (delta) and
**t822_10** (append): extend `content.py` (parser + `next_frame_id`/per-pane state
already in `Subscription`); the scheduler's keyframe-on-change branch is where
delta/append slot in. **Mobile (cross-repo `aitasks_mobile`)** note: the wire
framing is `1 raw type byte + msgpack array of the remaining fields` (NOT the type
as msgpack array[0]); `pane_status` is a `kind:"push"` JSON text frame.

## Risk

### Code-health risk: medium
- New per-connection **asyncio push scheduler** (cadence timers, wake-event,
  back-pressure, lifecycle tied to connection close) is fresh concurrency on the
  server's event loop — a leak or uncancelled task could outlive its socket.
  · severity: medium · → mitigation: per-conn task tracked in `_pushers` and
  cancelled in `_handle`'s `finally`; scheduler split into a dependency-injected
  `_run_once` driven by `_loop`, with **direct async tests** (emit + lifecycle
  teardown) in `test_applink_pusher.sh`; router stays pure.
  → mitigation: applink_dataplane_limits_hardening
- New `msgpack` dependency in the install/probe flow. · severity: low ·
  → mitigation: lazy import + graceful test skips + `aitask_setup.sh`/launcher
  probe, mirroring the t822_7 `websockets` addition. → mitigation: TBD
- Blast radius is contained: two new applink-package modules + one small
  `monitor_core` helper + additive router/profile edits; no change to the
  desktop monitor/board render path. · severity: low

### Goal-achievement risk: medium
- **No real mobile client here** — end-to-end keyframe decode, resize→dim,
  focused cadence, and `request_keyframe` recovery can only be exercised against a
  synthetic scripted WS client; payload-schema drift from what mobile expects is
  possible. · severity: medium · → mitigation: strict adherence to
  `content_transport.md`; explicit framing note for the mobile sibling; a
  manual-verification follow-up for the live path. → mitigation: applink_dataplane_limits_hardening
- **tmux/wcwidth parity** for span widths and cursor style is best-effort
  (stdlib `east_asian_width`, no utf8proc; block-cursor only). Wide-char rendering
  could be off by a cell in rare cases. · severity: low · → mitigation: server is
  the authoritative width source (mobile uses verbatim), so it stays
  self-consistent; documented. → mitigation: TBD

### Planned mitigations
- timing: after | name: applink_dataplane_limits_hardening | type: chore | priority: medium | effort: low | addresses: code-health "asyncio push scheduler" + goal-achievement "no real mobile client / schema-drift & DoS" | desc: Enforce/verify applink data-plane resource limits — max subscribed panes per connection, cadence-floor clamping, msgpack frame-size cap, and decode-bomb guards — coordinated with t985 (applink security hardening) to avoid duplication.
