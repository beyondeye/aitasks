---
Task: t1057_applink_history_rpc_scrollback.md
Base branch: main
plan_verified: []
---

# Plan — t1057: AppLink `history` RPC (Stage 5, server-side)

## Context

AppLink streams tmux pane content to a paired mobile companion over a binary
data plane. Live frames cover **only the current viewport** (t1054 made
keyframes viewport-only). The wire spec (`aidocs/applink/content_transport.md`
§Scrollback / §Staged rollout Stage 5) defines a `history` RPC for pulling past
rows on demand, but **no `history` verb exists in `applink/router.py`** — Stage 5
is unimplemented server-side. Without it, scrollback is unreachable: the capture
buffer already retains ~200 scrollback lines (`capture-pane -S -200`,
`monitor_core.py`), but nothing exposes them to the client.

This task implements the server half (the mobile half is the paired
`aitasks_mobile` t14_13). Per the spec: client sends `history {pane_id,
before_line, count}` on the control plane; the server replies on the control
plane with a **token**, then pushes a **single binary `keyframe` (0x01)** on the
data plane whose rows carry **negative `row_id`s** (`-1` = line immediately above
`before_line`, `-2` two above, …). It reuses the existing keyframe frame shape —
no sixth frame type.

> **Revised after review.** The first draft claimed history works without a live
> subscription and drained before the back-pressure guard. Both were unsafe.
> The sections below incorporate fixes for pane-cache population, frame
> anchoring, back-pressure ordering, per-pane request correlation, and
> positive-`before_line` edge cases.

## Key existing code reused (no reinvention)

- `content.parse_sgr_line()` / `content.build_osc8()` — SGR→span parser + OSC8
  sidecar builder. The new history-row builder reuses both; only the line-range
  selection is new.
- `content.parse_snapshot(content, viewport_height)` — establishes the geometry
  convention the history math mirrors: the **viewport is the trailing
  `viewport_height` lines**, `row_id 0` == top of viewport (t1054).
- `content.encode_keyframe(...)` — the wire encoder; used verbatim.
- `Subscription` (`content.py`) — already carries the per-connection `force` set
  consumed by the pusher; the history queue is modeled the same way.
- `PushScheduler._run_once` (`pusher.py`) — already calls
  `monitor.capture_all_async()` (which runs discovery → populates `_pane_cache`)
  and is woken by the server after each routed frame. History drains **inside
  the same pass**, reusing that capture.

## Design decisions (surfaced for review)

1. **History requires the pane to be in the active subscription; the token acks
   acceptance, not delivery.** History is "scrollback for a pane I'm streaming".
   The router rejects (`BAD_PAYLOAD`, `reason: not_subscribed`) any `history`
   whose `pane_id` is not in `conn.subscription.panes` — a never-subscribed pane
   is rejected synchronously. Requiring subscription resolves the **pane-cache**
   problem for *real* panes: `TmuxMonitor.capture_pane_async()` returns `None`
   for any pane not in `_pane_cache` (`monitor_core.py:1205`), but a real pane is
   discovered + cached by the pusher's `capture_all_async()`, so its history
   capture succeeds. **However, explicit `subscribe` accepts any well-formed
   `%N` without proving the pane exists** (`router.py` validates only
   `_PANE_ID_RE`), so the subscription set can contain a stale/nonexistent id.
   For such a pane — and for a real pane that vanished between subscribe and
   drain — `_drain_history` finds `snaps.get(pane_id) is None`, consumes the
   request, and sends **no** keyframe. The `res` token therefore acknowledges
   that the request was **accepted and queued, not that a keyframe will be
   delivered**: delivery is **best-effort**, contingent on the pane being
   present in the drain-time capture. The client correlates by the keyframe's
   arrival (by `pane_id`) and learns a pane is gone from the roster via
   `pane_status` / its absence. This is documented in `content_transport.md`
   §Scrollback and pinned by a test (subscribe-to-nonexistent → token, no
   keyframe, request drained).

2. **`before_line` coordinate space + best-effort anchoring.** `before_line` is a
   **viewport-relative row id** in the same space as live frames (`0` = viewport
   top; positive = into the viewport; negative = already-fetched scrollback).
   The response is **always numbered `-1..-count` relative to `before_line`**;
   the client translates response `row_id -j` back to its own absolute
   `before_line - j`. Server math: history `row_id -j` ⇒ capture line index
   `(L − H) + before_line − j` (`L` = captured line count, `H` = pane height).
   The history is anchored to the **capture taken at drain time** — the *same*
   `capture_all_async()` snapshot this pusher tick uses for the pane's live
   frame, so the history keyframe and the concurrent live frame are mutually
   consistent. It is **NOT** anchored to the exact frame the client had rendered
   when it scrolled: if the pane emits output between the client's rendered
   frame and the server's drain capture, the viewport boundary shifts and the
   returned rows can overlap/shift by the scroll delta. This is **best-effort by
   design** — the server keeps no per-frame replay buffer (explicitly out of
   scope, `content_transport.md` §Out of scope: "Replay buffer / time-travel").
   It is **exact for idle/static panes**, which is the dominant scrollback case
   (scrolling back over a finished/idle agent). Documented in
   `content_transport.md` §Scrollback and pinned by a targeted test
   (intervening-scroll). The `1234` example value in the spec is illustrative
   (the server retains only ~200 lines). This coordinate + anchoring contract is
   the **explicit coordination point with mobile t14_13**.

3. **History keyframe `frame_id` does NOT advance the live monotonic chain.**
   Negative `row_id`s are the *sole* signal distinguishing a history keyframe
   from a live one (both type `0x01`). The server reads the pane's current
   `frame_id` without bumping it (read *after* the live loop, so on tick 1 it
   carries the same `frame_id` as the live keyframe it follows — never `0`; the
   negative row ids disambiguate), so a subsequent live `delta`'s
   `prev_frame_id` still matches and the live chain is never desynced.

4. **Token is an ack; ≤1 outstanding history per pane (coalesced).** The keyframe
   wire shape has no token/`before_line` field, so correlation is by `pane_id`.
   To remove same-pane ambiguity, `request_history` keeps **at most one pending
   request per pane** — a newer request for a pane **supersedes** any un-drained
   older one (last-write-wins, matching the pusher's coalescing model). Across
   panes, frames carry distinct `pane_id`s, so there is never ambiguity.
   Ordering is **res-before-keyframe**: the server sends the control-plane `res`
   inline in `_handle` *before* the pusher (woken via an event) sends the binary
   keyframe on the next loop turn. The `res` token is a deterministic,
   counter-based handle (`h1`, `h2`, … per subscription) acknowledging
   *acceptance* of the latest request for that pane — not delivery (see decision
   #1: a keyframe follows only if the pane is in the drain-time capture).

5. **Bounded, read-gated, back-pressure-respecting.** `count` is validated
   `1 ≤ count ≤ _MAX_HISTORY_ROWS` (1000) and `before_line` must be an int
   (bools rejected); else `BAD_PAYLOAD`. `history` is gated at `read_only` and up
   (same band as `snapshot`/`subscribe`/`request_keyframe`). The drain runs
   **after** the pusher's `_over_high_water()` guard — a congested socket skips
   the whole tick (history included); the pending request stays queued and
   drains a later tick (no loss), so a large history response never bypasses
   back-pressure coalescing.

6. **Single cohesive task (no child split).** Complexity is high but the change
   is one RPC whose units (content helper, subscription queue, router verb,
   pusher drain) are tightly coupled and each already has a per-module unit test
   home.

## Implementation

### A. `content.py` — history-row builder + subscription queue

1. **`history_rows(content, viewport_height, before_line, count)` → `(rows, osc8)`**
   (near `snapshot_to_rows`). Split into lines, dropping the single trailing
   empty cell exactly as `parse_snapshot` does. `L = len(lines)`;
   `base = L - viewport_height`. Loop `j` from `1..count`; `idx = base +
   before_line - j`; **`break` on `idx < 0 or idx >= L`** (not `continue`).
   Because `idx` decreases monotonically with `j`, `break` guarantees a
   **contiguous** run `-1..-m` (`m ≤ count`): a far-positive `before_line` whose
   first `idx (j=1)` is `≥ L` yields an **empty** history keyframe (never the
   sparse `-977`-without-`-1..-976` response the naive `continue` would emit);
   running off the buffer top (`idx < 0`) stops cleanly. For each in-range `idx`,
   `parse_sgr_line(lines[idx])` and append `(-j, spans, urls)`. Return
   `rows = [[rid, spans], …]` and `osc8 = build_osc8(parsed)` (row-major over the
   emitted history rows). Docstring states the geometry, the contiguity/empty
   guarantee, and that osc8 offsets are over the history rows.

2. **`Subscription` history queue** (additive):
   - `__init__`: `self._pending_history: list = []`, `self._history_seq = 0`.
   - `request_history(self, pane_id, before_line, count) -> str`: **drop any
     existing pending entry for `pane_id`** (coalesce), bump `_history_seq`,
     build `token = f"h{self._history_seq}"`, append
     `(pane_id, before_line, count, token)`, return `token`.
   - `has_pending_history(self) -> bool`.
   - `take_pending_history(self) -> list`: return the list and reset to `[]`.
   - In `apply_subscribe`: after recomputing `self.panes`, **prune
     `_pending_history` of entries whose pane is no longer subscribed** (one
     comprehension) — mirrors the existing per-pane-state pruning so a
     re-subscribe cannot strand a stale history request.

### B. `router.py` — the `history` verb

1. Add `"history"` to `IMPLEMENTED_COMMAND_VERBS` (auto-flows into `KNOWN_VERBS`).
2. Add `_MAX_HISTORY_ROWS = 1000` near the other input-validation bounds.
3. Add `_req_int(payload, key) -> int | None` helper (rejects bools:
   `isinstance(v, int) and not isinstance(v, bool)`).
4. Dispatch branch in `_dispatch`:
   ```python
   if verb == "history":
       pane_id = self._req_pane_id(payload)
       before_line = self._req_int(payload, "before_line")
       count = self._req_int(payload, "count")
       if (pane_id is None or before_line is None
               or count is None or count < 1 or count > _MAX_HISTORY_ROWS):
           return self._bad_field(msg_id, verb, "pane_id/before_line/count")
       # History serves scrollback for a pane the client is actively streaming.
       # Requiring a live subscription guarantees the pane was discovered +
       # cached (capture_pane_async needs _pane_cache), so the token is never
       # returned for a pane that cannot be served.
       if conn.subscription is None or pane_id not in conn.subscription.panes:
           return self._err(msg_id, verb, ERR_BAD_PAYLOAD,
                            f"pane '{pane_id}' is not subscribed",
                            detail={"reason": "not_subscribed"})
       token = conn.subscription.request_history(pane_id, before_line, count)
       return self._res(msg_id, verb, {"ok": True, "token": token})
   ```

### C. `pusher.py` — drain history → binary keyframe (after the live loop)

Restructure `_run_once` so the existing guards and capture come first, then the
**unchanged live loop**, then the history drain (reusing this tick's `snaps`):
```python
sub = self._conn.subscription
if sub is None or not sub.panes:
    return                              # unchanged live-path guard
if self._over_high_water():
    return                              # back-pressure: skip tick incl. history
snaps = await self._monitor.capture_all_async()
now = self._clock()
for pane_id in list(sub.panes):
    ...                                 # existing live loop, unchanged
if self._stopped:
    return                              # a live send failed: don't touch a dead socket
if sub.has_pending_history():
    await self._drain_history(sub, snaps)
```
**History drains *after* the live loop (fixes the first-frame race).** Because
`apply_subscribe` seeds `force |= panes`, tick 1 always emits a forced live
keyframe for each subscribed pane *first* (establishing `row_sigs` and bumping
`frame_id` to `1`); only then does history drain. So a client that sends
`subscribe` then immediately `history` can never receive a `frame_id=0`
history keyframe with negative rows *before* its first live keyframe — the live
viewport baseline always precedes the scrollback fill within the same pass. The
`_stopped` guard mirrors the live loop's own dead-socket check.

New `_drain_history(self, sub, snaps)`:
```python
for pane_id, before_line, count, _token in sub.take_pending_history():
    snap = snaps.get(pane_id)
    if snap is None:
        continue                        # pane vanished this tick; client retries
    pane = snap.pane
    cols, rows_h = pane.width, pane.height
    rows, osc8 = content.history_rows(snap.content, rows_h, before_line, count)
    frame_id = sub.state_for(pane_id).frame_id   # read; do NOT advance live chain
    cursor = [0, 0, False, 0]                     # history has no cursor (hidden)
    await self._send(content.encode_keyframe(
        pane_id, frame_id, cols, rows_h, cursor, rows, osc8 or None))
```
Reuses `snaps` (so history is anchored to the same capture as this tick's live
frame — decision #2) and the existing `_send` dead-socket handling. **No
`server.py` change is needed** (dropped from the first draft): a subscribed pane
means `sub.panes` is non-empty, so the existing
`if conn.subscription is not None and conn.subscription.panes:` wake in
`server._handle` already fires.

### D. `profiles.py` — gate `history` at read_only+

Add `"history"` to `DEFAULT_ALLOWED["read_only"]`, `["monitor_control"]`, and
`["full"]` (cumulative fallback). Keep aligned with the shipped YAMLs (E).

### E. Shipped permission profiles (data branch — `./ait git`)

Add `- history` to each of
`aitasks/metadata/applink_profiles/{read_only,monitor_control,full}.yaml` (the
loaded source-of-truth; without them the verb is `PERMISSION_DENIED` here). Stage
**only these three paths**, commit separately via `./ait git` (concurrent
aitask-data branch — stage specific paths, leave reconciliation to the syncer).

### F. Docs (`aidocs/` — regular git)

- `content_transport.md` §Scrollback: clarify `before_line` coordinate space
  (viewport-relative; response `-1..-count` relative to it; example value
  illustrative); the **best-effort anchoring** contract (anchored to the
  drain-time capture; exact for idle panes, may overlap for actively-scrolling
  panes; no replay buffer); ≤1 outstanding request per pane (coalesced),
  correlation by pane_id; the no-token-on-wire note; **the token = acceptance
  ack, not a delivery guarantee** (no keyframe is sent if the subscribed pane is
  absent from the drain-time capture — stale/nonexistent/vanished pane); and
  that the history keyframe `frame_id` does not advance the live chain.
- `monitor_port_design.md` verb table: add a `history` row
  (`{pane_id, before_line, count}`, gate `read_only`, modal `N`).
- `permissions.md`: add `history` to the §Verb gating table (✓/✓/✓) and the
  `read_only` YAML example block.

## Tests

- **`tests/test_applink_content.sh`** — `history_rows`:
  - Synthetic `content` whose each line text == its absolute capture index;
    assert history `row_id -j` text == `lines[base + before_line - j]`
    (**independent ground truth** from the line list, not the function) for
    `before_line` = 0, negative, and a small positive in-viewport value.
  - **Contiguity / empty (concern 5):** a far-positive `before_line` (beyond the
    viewport) → **empty** rows; an in-window `before_line` with `count` larger
    than retained scrollback → contiguous `-1..-m` (no gaps), `m` < `count`.
  - osc8 sidecar for a hyperlinked scrollback line, offset over the history rows.
- **`tests/test_applink_router.sh`** — `history`:
  - With the pane subscribed: `res` carries a non-empty `token`; the request is
    queued (`has_pending_history()` true; entry matches).
  - **not_subscribed (concern 1):** `history` for a pane not in the subscription
    (and for a connection with no subscription) → `BAD_PAYLOAD`,
    `detail.reason == "not_subscribed"`, and **no token / nothing queued**.
  - Validation: missing/invalid `pane_id`, non-int `before_line`, `count` < 1 / >
    max / non-int → `BAD_PAYLOAD`.
  - **Coalescing (concern 4):** two `history` calls for the same subscribed pane
    → exactly one pending entry (the latest before_line/count), latest token.
  - `read_only` profile allows `history` (not `PERMISSION_DENIED`); `history` no
    longer `UNKNOWN_VERB`; `KNOWN_VERBS` includes it.
- **`tests/test_applink_pusher.sh`** (FakeMonitor already has
  `capture_all_async`; no new fake method needed):
  - Subscribe + queue a pending history, run `_run_once`: msgpack-decode the
    history `0x01` frame — `pane_id` matches, all `row_id`s negative and map to
    the expected lines, cursor hidden; assert `_drain_history` did not bump
    `frame_id` beyond the live keyframe's value.
  - **First-frame race (drain-after-live):** on a fresh subscription, queue
    history and run `_run_once` once; assert the binary frames are ordered
    **live keyframe first** (non-negative `row_id`s, `frame_id == 1`) **then**
    the history keyframe (negative `row_id`s, `frame_id == 1`) — never a
    `frame_id=0` history keyframe before the first live keyframe.
  - **Anchoring (concern 2):** change `FakeMonitor` content between queueing and
    draining; assert the history keyframe reflects the **drain-time** capture
    (documents/pins the best-effort contract).
  - **Back-pressure (concern 3):** with `_over_high_water()` true (FakeTransport
    size > HIGH_WATER_BYTES), `_run_once` emits **no** binary frame and the
    history request **stays pending**; once clear, the next pass drains it.
  - **Best-effort delivery (subscribed-but-missing pane):** subscribe to a
    regex-valid pane id that is **not** in the FakeMonitor's `capture_all_async`
    result, queue history, run `_run_once`: **no** history keyframe is emitted
    and the request is **drained** (not re-queued) — proving the token does not
    guarantee delivery and a stale/nonexistent pane does not loop.
  - A `paused` conn does not drain history (request stays pending until resume).
- **`tests/test_applink_headless_live.sh`** — extend the live wss round-trip:
  after the subscribe keyframe, send a `history` frame for the subscribed pane;
  assert the control-plane `res` carries a `token` (definitive); best-effort
  assert a binary `0x01` whose rows include negative ids (skip if the throwaway
  pane has no scrollback). Skip-capable like the rest of the file.

Run: `bash tests/test_applink_content.sh`, `tests/test_applink_router.sh`,
`tests/test_applink_pusher.sh`, `tests/test_applink_headless_live.sh`; sanity
`python -m pyflakes` on the four edited modules if available.

## Step 9 (post-implementation)

Standard: review (Step 8), commit code (regular git) + plan + profile YAMLs +
docs (`./ait git` for the data-branch YAMLs), then merge approval and archival.
The confirmed `after` mitigation (`applink_history_coordinate_verify`) is created
at Step 8d. Suggest a paired follow-up note on `aitasks_mobile` t14_13 (mobile
renders negative row ids + the `before_line` translation + the best-effort
anchoring contract); a cross-agent skill port is **not** needed (no skill
surface changes).

## Risk

### Code-health risk: medium
- The history drain is a new branch in `pusher._run_once`, placed **after** the
  `not sub.panes` guard, the `_over_high_water()` back-pressure guard, the
  `capture_all_async()` call, **and the live loop** — so the live-frame path is
  byte-for-byte unchanged when no history is pending, history inherits
  back-pressure + discovery for free, and the live keyframe always precedes the
  history keyframe (no first-frame race). No `server.py` change. · severity:
  low · → mitigation: covered by the pusher (incl. first-frame-ordering) +
  headless-live tests
- Additive surface across content, router, profiles + 3 data-branch YAMLs;
  every edit is localized. · severity: low · → mitigation: none needed

### Goal-achievement risk: medium
- `before_line`'s coordinate space + the best-effort anchoring contract must
  match `aitasks_mobile` t14_13, or end-to-end scrollback renders at the wrong
  offset on the phone even though the server is internally correct · severity:
  medium · → mitigation: t1088
- Anchoring to the drain-time capture means an actively-scrolling pane can return
  overlapping rows; this is documented best-effort (no replay buffer) and pinned
  by the intervening-scroll test, exact for the dominant idle-pane case ·
  severity: low · → mitigation: t1088
- Explicit `subscribe` accepts unverified `%N` ids, so a stale/nonexistent (or
  vanished) subscribed pane yields a token but no keyframe; the token is
  documented as an acceptance ack (not delivery), correlation is by keyframe
  arrival, and the case is tested (no keyframe, request drained, no loop) ·
  severity: low · → mitigation: none needed

### Planned mitigations
- timing: after | name: applink_history_coordinate_verify | created: t1088 | type: test | priority: medium | effort: low | addresses: goal-achievement before_line coordinate-space + anchoring agreement with aitasks_mobile t14_13 | desc: once mobile t14_13 lands, verify end-to-end that the server's negative-id before_line mapping renders scrollback at the correct offset on the phone, including behavior over an actively-scrolling pane

## Final Implementation Notes

- **Actual work done:** Implemented the Stage-5 `history` RPC server-side exactly per the approved plan. `content.history_rows()` builds the negative-row-id scrollback keyframe (contiguous `-1..-m` via `break`, empty for an out-of-window anchor); `Subscription` gained a coalesced (≤1/pane) history queue with re-subscribe pruning; `router.py` added the read-only-gated `history` verb (validates `pane_id`/`before_line`/`count`, requires the pane be subscribed → `not_subscribed`, returns an acceptance token) plus a bool-rejecting `_req_int` helper and `_MAX_HISTORY_ROWS=1000`; `pusher._drain_history()` serves the keyframe after the live loop, reusing the tick's capture, without advancing the live `frame_id`. Gated `history` at `read_only`+ in `profiles.py` (in-code fallback) and the three shipped `applink_profiles/*.yaml`. Docs updated: `content_transport.md` §Scrollback "Server semantics (v1)", verb-table rows in `monitor_port_design.md` + `permissions.md`.
- **Deviations from plan:** None. The plan was followed as approved. The `server.py` wake-condition change anticipated in the first draft was (correctly) dropped during review — a subscribed pane already triggers the existing wake.
- **Issues encountered:** None blocking. The four review rounds (pane-cache, anchoring, back-pressure ordering, token/FIFO correlation, sparse `before_line`) and the first-frame-race round were all resolved in the plan before implementation; the code matched the agreed contract and the tests passed on the first full run.
- **Key decisions:** History drains *after* the live loop so a `subscribe`+immediate-`history` never delivers a `frame_id=0` negative-row keyframe before the first live keyframe; the token acks acceptance not delivery (correlation by `pane_id`, best-effort if the pane is absent from the drain-time capture); `frame_id` is read, never advanced, so the live delta chain is never desynced.
- **Upstream defects identified:** None.
- **Test results:** `test_applink_content.sh` (98), `test_applink_router.sh` (168), `test_applink_pusher.sh` (85), and the live `test_applink_headless_live.sh` e2e all pass; `smoke`/`server_limits`/`headless` unaffected; pyflakes clean on the four edited modules. The e2e confirms the control-plane history token end-to-end; the negative-id keyframe is correctly SKIP'd there because a fresh throwaway pane has no scrollback (the documented best-effort path).
