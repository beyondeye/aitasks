# AppLink Pane Content Transport

The wire format for streaming tmux pane contents to a mobile companion app paired via `ait applink`.

## Overview

[protocol.md](protocol.md) defines the **control plane** (envelope, pairing, lifecycle, verbs, permissions). This document defines the **data plane** — how tmux pane content is encoded, framed, deltified, and pushed to the mobile client.

The data plane is separated from the control plane because:

- The control plane is JSON over WebSocket text frames; the data plane is **binary** (MessagePack) over WebSocket binary frames. Different transport modes, different schemas.
- Pane content dominates bandwidth by 2-3 orders of magnitude over control verbs. The data-plane format directly determines whether the protocol is viable over cellular (Phase 3 relay, see [protocol.md §Roadmap to cross-network](protocol.md#roadmap-to-cross-network)).
- The format is **final from day 1**; feature coverage (delta encoding, append fast-path, history) is staged, but every stage uses the same on-wire schema. Mobile decoders are written once against the full spec.

[monitor_port_design.md](monitor_port_design.md) (authored by t822_3) wires the existing `monitor` module onto this format — it does not re-litigate the format itself.

## Design goals

In priority order:

1. **Frame-independent decoding.** Any keyframe must render correctly without prior state. No cross-frame parser state that can drift after a missed delta or reconnect.
2. **Mobile renderer triviality.** Rendering a frame must be O(visible-cells) using only primitives every mobile UI toolkit ships (textured glyph or styled-text-run). No VT/xterm parser on the phone.
3. **Bandwidth efficiency on cellular.** Idle panes cost zero bytes; an unfocused pane updating once every 3 s costs < 100 B/update; a busy focused pane costs < 1 KB at 4 Hz.
4. **Server CPU stays modest.** ANSI parsing happens **once** in the server's existing tmux output pipeline; the wire format mirrors that internal state directly.
5. **Wide-char and Unicode safety.** Server determines cell width using the same width tables tmux uses; mobile does not re-decide width per glyph.
6. **No version bumps for feature stages.** All stages (keyframe-only, +delta, +append, +viewport-hint, +history) plug in additively per the [protocol.md §Versioning](protocol.md#versioning) rules.

## Wire encoding

- **Container:** MessagePack arrays/maps. Compact, schema-less, fast decoders available for every target platform.
- **Transport:** WebSocket **binary** frames (opcode `0x2`). The JSON envelope from [protocol.md §Message envelope](protocol.md#message-envelope) is used only for **text** frames (opcode `0x1`) carrying control verbs. Binary frames bypass the envelope to save bytes; correlation back to control flow uses pane IDs and frame IDs, not envelope `id`s.
- **Per-frame type tag:** every binary frame starts with a 1-byte type ID (see [Frame types](#frame-types)). The remainder is MessagePack-encoded.
- **Compression:** WebSocket `permessage-deflate` extension is **mandatory** for the data plane. Brotli is enabled by the Phase 3 relay broker for cross-network paths (see [protocol.md §Roadmap to cross-network](protocol.md#roadmap-to-cross-network)).

## Row encoding (the core decision)

Rows are sequences of **styled spans**. The server parses ANSI/SGR escape sequences from `tmux capture-pane -e` exactly once and emits a structured row; the phone never sees raw escape sequences.

### Span schema

A span is a fixed-arity MessagePack array:

```
[text, fg, bg, attrs, width]
```

| Field | Type | Notes |
|-------|------|-------|
| `text` | str | UTF-8 string. May contain combining marks; **no** ANSI escapes, **no** zero-width control chars (except explicit `\t` if surface, but tmux strips these). |
| `fg` | int or null | Foreground color. `null` means default. `0-255` = xterm 256-palette index. Negative = truecolor packed: `-((0xFF<<24) | (r<<16) | (g<<8) | b)` (alpha 0xFF reserved as a sentinel; high bit clears flag truecolor). |
| `bg` | int or null | Background color, same encoding as `fg`. |
| `attrs` | int | Bitfield (see below). |
| `width` | int | Total cell width occupied by the span. Server-computed using tmux's width tables; mobile **uses this value verbatim** rather than re-running East Asian Width. |

### Attrs bitfield (1 byte)

| Bit | Meaning |
|-----|---------|
| 0 | bold |
| 1 | italic |
| 2 | underline |
| 3 | reverse video |
| 4 | strikethrough |
| 5 | blink (slow) |
| 6 | dim |
| 7 | hyperlink (OSC8) — `text` field is the visible label; URL travels in a sidecar map (see below) |

### Row schema

```
[row_id, [span, span, ...]]
```

`row_id` is the absolute row index within the pane's current viewport — `0` is the top row of the visible area. Scrollback rows use negative IDs (history RPC only; see [Scrollback](#scrollback)).

### Hyperlink sidecar

When any span in a frame has bit 7 of `attrs` set, the frame includes an `osc8` map at the frame level: `{span_offset → url}`. `span_offset` is a flat counter (frame-global, row-major). Keeps the per-span shape fixed; only frames with hyperlinks pay for the sidecar.

## Frame types

All five data-plane frame types are part of the spec from day 1. Stages 1-5 in [Staged rollout](#staged-rollout) describe which the server and client implement at each milestone — the schema is fixed.

| Type ID | Name | Purpose |
|---------|------|---------|
| `0x01` | `keyframe` | Full grid: every row, cursor, scroll position, frame_id |
| `0x02` | `delta` | Changed rows only + cursor + `prev_frame_id` |
| `0x03` | `append` | New rows appended at bottom (log-streaming fast path) |
| `0x04` | `cursor` | Cursor-only update (REPL echo, mouse hover) |
| `0x05` | `dim` | Pane resize / palette change / dimensions update |

### `keyframe`

```
[0x01, pane_id, frame_id, cols, rows, cursor, [row, row, ...], osc8?]
```

- `frame_id`: monotonic u32 per (pane_id, session_bearer). Resets on resume.
- `cols`/`rows`: terminal dimensions at capture time.
- `cursor`: `[row, col, visible, style]` — `style` ∈ `{0=block, 1=underline, 2=bar}`.
- `rows`: array of row-arrays. Rows not in the array are blank.
- `osc8`: optional sidecar map (see above).

Sent: on subscribe, on resume, every N seconds (keyframe interval), when delta encoding cost ≥ keyframe cost, or on demand via the recovery path.

### `delta`

```
[0x02, pane_id, frame_id, prev_frame_id, cursor, [row, row, ...], osc8?]
```

- Only **changed** rows are included. Unchanged rows on the client retain their previous content.
- A row whose span array is **empty** (`[row_id, []]`) **clears that row to blank** on the client. This is how a delta expresses a row that went from content to empty within unchanged dimensions (e.g. a trailing line was removed); without it the client would retain the stale content and diverge from a fresh keyframe.
- The optional `osc8` sidecar's flat span-offsets are **row-major over the delta's own `rows` array** (the changed rows only), exactly as keyframe `osc8` is row-major over its rows — *not* over the full pane grid.
- `prev_frame_id` is the frame_id this delta is computed against. If the client's last known frame_id does not match `prev_frame_id`, the client **must** request a keyframe (see [Recovery](#frame-integrity-and-recovery)).

### `append`

```
[0x03, pane_id, frame_id, [row, row, ...]]
```

Fast path for log-like growth: rows are appended at the **bottom** of the client's buffer, the topmost row is dropped to maintain `rows` from the most recent keyframe. No cursor change implied. No `prev_frame_id` chain (each `append` is independent and additive on top of the latest `keyframe`/`delta`).

Server emits `append` instead of `delta` when:
- Cursor is at the bottom row before and after the update.
- No rows above the bottom changed.
- No scroll-region shenanigans (alt-screen activations break the fast path; server falls back to `delta`).

**Detection convention (server-authoritative).** The server emits `append` only on an **exact full-viewport scroll**: the new grid equals the previous grid shifted up by *k* rows (`1 ≤ k < rows`) with *k* brand-new rows at the bottom, the cursor unchanged from the previous frame and at the bottom row. The appended rows carry their **new absolute `row_id`s** (`rows-k … rows-1`) — after the client drops *k* top rows and shifts the rest up, they land at exactly those positions (row-id is the viewport position, as for `keyframe`/`delta`). The server does **not** inspect for alt-screen explicitly (the captured snapshot exposes no such flag); exact-shift detection is the conservative substitute, since an alt-screen redraw is not a clean shift and falls back to `delta` (and even a coincidental shift converges correctly).

`append` carries **no cursor** and **no `osc8` sidecar**. The client keeps the cursor from the previous frame (the server only appends when the cursor did not change), and the server emits a `delta` instead whenever an appended row carries a hyperlink — so `append` rows never set the OSC8 attr bit. The client **adopts the append's `frame_id` as its current frame_id**, so a subsequent `delta`'s `prev_frame_id` equals that `frame_id` and the linear gap-check still works. A run of `append`s cannot self-detect a *lost* `append` (no `prev_frame_id` chain); recovery rests on the ordered, reliable WebSocket transport (a dropped frame breaks the connection → reconnect → fresh keyframe) and the periodic keyframe interval that re-syncs accumulated drift — the same recovery model deltas rely on.

### `cursor`

```
[0x04, pane_id, frame_id, cursor]
```

Cursor moved, no cells changed. Typical: REPL prompt blink, vim normal-mode motion.

### `dim`

```
[0x05, pane_id, cols, rows, palette_hash]
```

Dimensions changed (user resized the desktop terminal) or the palette changed. Triggers a follow-up `keyframe`. Mobile resizes its render buffer.

## Refresh control, focus, back-pressure

Mobile drives subscription via control-plane verbs (JSON envelope, text frames):

### `subscribe`

```json
{"v":1, "id":"s1", "kind":"req", "verb":"subscribe",
 "auth":"<bearer>",
 "payload":{
   "panes": ["<pane_id_1>", "<pane_id_2>"],
   "cadence_focused_ms": 250,
   "cadence_idle_ms": 3000,
   "keyframe_interval_ms": 30000,
   "viewport_hint": {"cols": [0, 60], "rows": null}
 }}
```

- `keyframe_interval_ms` upper-bounds the gap between forced keyframes (defends against accumulated delta drift). Server picks min of this and its own policy.
- `viewport_hint` (Stage 4) — server clips spans/rows to the requested column window before encoding. Optional.
- `panes` — the pane ids (`%N`) to follow. An **empty list `[]` (or an absent `panes` key) means "all currently-discovered panes"**: the server expands it to the full pane roster it enumerates at subscribe time. This lets a client subscribe to everything without a prior discovery handshake (the mobile app sends `panes: []`). The expansion is **point-in-time** — panes that appear later are not auto-added; the client re-subscribes (or `request_keyframe`s) to pick them up. A present-but-non-list `panes` value is a `BAD_PAYLOAD` error.

Server responds with the current state (a `keyframe` per subscribed pane) on the data plane. The `subscribe` `res` echoes the accepted pane set in `payload.panes` (the expanded roster, when an empty/absent list was sent).

**Bandwidth note (all-panes subscribe).** Subscribing to the whole roster streams full content (keyframe + deltas) for every pane. The per-pane delta engine keeps idle panes near-zero-cost after their initial keyframe, and `focus` raises only one pane's cadence, so the steady-state cost is bounded; the main cost is the one-time keyframe burst on connect. A more bandwidth-frugal contract — `pane_status` (roster badges) for all panes but binary content only for the focused/explicitly-subscribed pane — is a planned follow-up that requires coordinated server **and** mobile-app changes.

### `focus`

```json
{"v":1, "id":"f1", "kind":"req", "verb":"focus",
 "auth":"<bearer>",
 "payload":{"pane_id":"<id>"}}
```

Server raises that pane's cadence to `cadence_focused_ms`, lowers all others to `cadence_idle_ms`. Single focused pane at any time (matches `monitor_app.py`'s focus model). Acknowledged via `res` — no data-plane echo.

### Back-pressure

If the WebSocket send buffer exceeds a configurable high-water mark (default 256 KB), the server:

1. Coalesces queued deltas for the same pane into a single keyframe.
2. Drops `cursor` frames (lowest priority).
3. Skips a refresh tick rather than queueing.

Mobile MAY send a `pause` push (`verb: "pause"`) when backgrounded but not yet `Suspended` (e.g., screen off but socket alive) — server stops all pushes until `resume` push, no state lost.

## Scrollback

Live updates cover only the current viewport. History is pulled on demand:

### `history`

```json
{"v":1, "id":"h1", "kind":"req", "verb":"history",
 "auth":"<bearer>",
 "payload":{"pane_id":"<id>", "before_line": 1234, "count": 500}}
```

Server responds (control plane `res`) with a token, then sends a **single** binary `keyframe` on the data plane with `rows` populated using **negative** `row_id`s (`-1` = line immediately above `before_line`, `-2` = two above, etc.). No further updates for history rows.

Rationale: history is read-mostly and bursty. Reusing `keyframe` shape avoids a sixth frame type.

#### Server semantics (v1)

The v1 server (`applink/router.py` + `pusher._drain_history`) pins down the parts the wire shape leaves implicit:

- **`before_line` is viewport-relative.** It is a `row_id` in the same coordinate space as live frames — `0` = top of the current viewport, positive = into the viewport, negative = already-fetched scrollback. The response is **always numbered `-1..-count` relative to `before_line`** (`row_id -j` ⇒ the line at viewport-relative position `before_line - j`); the client translates each `-j` back to its own absolute `before_line - j`. The `1234` in the request example above is **illustrative** — the server only retains its capture buffer's scrollback (`capture-pane -S -<capture_lines>`, ~200 lines), so a `before_line` whose lines lie past the retained buffer yields an **empty** history keyframe. The returned run is always **contiguous** from `-1` (never sparse).
- **Best-effort, anchored to the drain-time capture.** The rows are read from the capture taken when the pusher drains the request — the *same* snapshot as that tick's live frame for the pane, so the two are mutually consistent. It is **not** anchored to the exact frame the client had rendered when it scrolled: if the pane emits output in between, the returned rows can overlap/shift by the scroll delta. This is intentional — there is no per-frame replay buffer (see [Out of scope](#out-of-scope-this-document)). It is exact for idle/static panes (the dominant scrollback case).
- **The token acks acceptance, not delivery.** The keyframe wire shape carries no token (correlation is by `pane_id` + the negative ids), so the control-plane token only confirms the request was accepted and queued. A subscribed pane that is absent from the drain-time capture (a stale/nonexistent subscribed id, or one that vanished) produces a token but **no** keyframe; the client learns the pane is gone from the roster via `pane_status`. History additionally requires the pane to be in the connection's active subscription (else `BAD_PAYLOAD` `reason: not_subscribed`).
- **≤1 outstanding request per pane.** A newer `history` for a pane supersedes any un-drained older one (last-write-wins), so two outstanding pulls can never produce ambiguous same-pane frames.
- **`frame_id` does not advance the live chain.** The history keyframe carries the pane's current `frame_id` without bumping it; the negative `row_id`s are the sole signal distinguishing it from a live keyframe, so the live `delta`/`prev_frame_id` chain is never desynced by a scrollback pull.

## Frame integrity and recovery

- `frame_id` is a monotonic u32 per (pane, session). Resets on a new `keyframe` after subscribe/resume.
- Every `delta` and `cursor` carries `prev_frame_id` referring to the frame the delta is computed against (the most recent keyframe **or** delta — the chain is linear).
- `append` does NOT carry `prev_frame_id`; it stacks on whatever the latest visible state is.
- **Gap detection:** if mobile receives a frame whose `prev_frame_id` does not match its current frame_id, it discards the frame and sends `request_keyframe`:

```json
{"v":1, "id":"k1", "kind":"req", "verb":"request_keyframe",
 "auth":"<bearer>",
 "payload":{"pane_id":"<id>"}}
```

Server replies with a fresh `keyframe` on the data plane within one refresh tick. This is the **only** recovery path — there is no replay buffer of past deltas.

## Compression

- **Default:** WebSocket `permessage-deflate` (RFC 7692), `client_max_window_bits=15`, `server_max_window_bits=15`, **no context takeover** (each frame compresses independently). Loss of cross-frame context costs ~10% ratio but eliminates a class of corruption on dropped frames and matches the frame-independent design.
- **Phase 3 relay:** broker enables Brotli compression on its egress to mobile; PC → broker side stays on deflate. Mobile decodes whichever is signalled.
- MessagePack arrays of short strings compress well; the encoded form rarely beats raw JSON until compression, but **after** compression the binary form is ~2× smaller than the equivalent gzipped JSON because of redundancy in JSON's structural tokens.

## Staged rollout

Format is fixed from Stage 1. Stages 2-5 add features, never change the wire schema.

| Stage | Server implements | Mobile implements | What's unlocked |
|-------|-------------------|-------------------|-----------------|
| **1** | `keyframe`, `cursor`, `dim`, `subscribe`, `focus`, `request_keyframe` | All 5 frame decoders (already final), keyframe-only renderer | End-to-end render works on LAN at low cadence. Validates encoding, framing, MessagePack pipeline, mobile renderer. |
| **2** | `delta` (server diff engine: row hashing + changed-row collection) | Delta application (replace listed rows in local buffer) | Bandwidth viable for relay/cellular. Most workloads (vim, htop) drop to <100 B/update. |
| **3** | `append` fast path (cursor-at-bottom detection in monitor refresh loop) | Append to bottom, scroll top out | `tail -f`, agent logs, build output stream instantly with sub-100 B/line. |
| **4** | `viewport_hint` clipping (clip spans/rows before encoding) | Send hint on layout change, request keyframe | Narrow-screen bandwidth halves for wide TUIs. |
| **5** | `history` RPC (cell buffer query for past rows) | Scrollback gesture, render negative row IDs | True scrollback. |

Mobile decoder switch statements cover all five frame types **from Stage 1** — stages 2-5 add cases to the renderer side, not the decoder. Adding a future Stage 6 frame type (e.g., `image` for Sixel/kitty graphics) is additive per [protocol.md §Versioning](protocol.md#versioning); legacy clients receive a `keyframe` substitute.

## Cross-references

- [protocol.md](protocol.md) — envelope, pairing, lifecycle, versioning, transport roadmap.
- [permissions.md](permissions.md) — the `snapshot` push is gated on every profile (it's the read-channel for all three profiles); `subscribe` / `focus` / `request_keyframe` are control verbs gated identically.
- [monitor_port_design.md](monitor_port_design.md) (authored by t822_3) — how the existing `tmux_monitor.PaneSnapshot` + `monitor_app.py` refresh loop are wired onto the frame types defined here. That doc consumes this spec; it does not redefine the wire format.

## Out of scope (this document)

- **Cell-level mouse events** — deferred. Mobile sends `send_keys` with literal escape sequences for now; a dedicated `mouse` verb may be added in a future stage.
- **Image cells (Sixel, kitty graphics)** — a future Stage 6 `image` frame type would handle this without a `v` bump.
- **Bidirectional text and complex script shaping** (Arabic, Hindi conjuncts) — server's width values are authoritative; mobile renders LTR. Bidi can be added per-span later via an `attrs` bit.
- **Audio/notification side-channels** — not part of pane content; if needed, separate verb.
- **Replay buffer / time-travel** — not provided; `history` is the only past-state RPC and is read-only.
