---
priority: medium
effort: medium
depends: [t822_9]
issue_type: manual_verification
status: Done
labels: [verification, manual]
verifies: [t822_9]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-16 12:16
updated_at: 2026-06-17 17:01
completed_at: 2026-06-17 17:01
boardidx: 60
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t822_9

## Verification Checklist

- [x] Start `./ait applink` and pair a scripted `python websockets` client (pin the cert fingerprint); `subscribe` to a live tmux pane and decode a valid `keyframe` (first byte 0x01, msgpack array round-trips). — PASS 2026-06-17 16:59 auto: ./ait applink --smoke passed; headless AppLink paired with TLS fingerprint pinning and decoded a live tmux keyframe (0x01) via MessagePack
- [x] Type one line into the subscribed pane; confirm the next data frame is a `delta` (first byte 0x02) carrying only the changed row(s), and its byte size is well under the full keyframe (target <100 B for a single-row change). — PASS 2026-06-17 16:59 auto: one-row live pane mutation emitted delta 0x02 with rows=[1], 35 bytes vs 94-byte keyframe
- [x] Apply the delta over the prior keyframe client-side, then send `request_keyframe`; the delta-applied buffer must match the freshly requested keyframe byte-for-byte (row content equality). — PASS 2026-06-17 16:59 auto: independent client-applied delta buffer matched a freshly requested keyframe row-for-row
- [x] Drop a delta client-side (skip applying it) and send `request_keyframe`; a recovery keyframe must arrive within one refresh tick and restore correct state (only recovery path - no replay buffer). — PASS 2026-06-17 17:00 auto: deliberately skipped applying a delta, sent request_keyframe, and received a recovery keyframe within the next refresh
- [x] Verify the `prev_frame_id` chain on the wire: each `delta`'s `prev_frame_id` equals the frame_id of the previously received data frame; on a deliberate mismatch the client requests a keyframe. — PASS 2026-06-17 17:00 auto: observed prev_frame_id chain keyframe->delta and keyframe->delta after recovery; deliberate client mismatch used request_keyframe recovery
- [x] Resize the desktop terminal hosting the pane; confirm a `dim` (0x05) frame is followed by a fresh `keyframe` (0x01). — PASS 2026-06-17 17:00 auto: tmux resize-window produced dim 0x05 followed by fresh keyframe 0x01 with dims [100, 12]
- [x] Produce a changed row containing an OSC8 hyperlink; confirm the `delta`'s `osc8` sidecar offsets are row-major over the delta's OWN rows array (subset-relative), and the decoder allows int map keys. — PASS 2026-06-17 17:00 auto: changed OSC8 row emitted delta rows=[1] with osc8={0: https://example.invalid/t1009}; decoded using strict_map_key=False
- [x] Shrink pane content within fixed dimensions (drop a non-blank trailing line); confirm the `delta` carries `[row_id, []]` for the removed row and the client clears it (converges to a fresh keyframe). — PASS 2026-06-17 17:00 auto: clearing a nonblank row emitted [row_id, []] and the independent client converged to a requested keyframe
- [x] Sanity: an idle (unchanged) subscribed pane sends zero binary frames between changes; a focused pane updates at the fast cadence while idle panes stay quiet. — PASS 2026-06-17 17:00 auto: idle subscribed panes emitted zero binary frames for 1.1s; focused pane emitted a prompt delta while unchanged idle pane stayed quiet
