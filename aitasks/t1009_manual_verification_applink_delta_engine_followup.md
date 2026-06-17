---
priority: medium
effort: medium
depends: [t822_9]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: ['822_9']
created_at: 2026-06-16 12:16
updated_at: 2026-06-16 12:16
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

- [ ] Start `./ait applink` and pair a scripted `python websockets` client (pin the cert fingerprint); `subscribe` to a live tmux pane and decode a valid `keyframe` (first byte 0x01, msgpack array round-trips).
- [ ] Type one line into the subscribed pane; confirm the next data frame is a `delta` (first byte 0x02) carrying only the changed row(s), and its byte size is well under the full keyframe (target <100 B for a single-row change).
- [ ] Apply the delta over the prior keyframe client-side, then send `request_keyframe`; the delta-applied buffer must match the freshly requested keyframe byte-for-byte (row content equality).
- [ ] Drop a delta client-side (skip applying it) and send `request_keyframe`; a recovery keyframe must arrive within one refresh tick and restore correct state (only recovery path — no replay buffer).
- [ ] Verify the `prev_frame_id` chain on the wire: each `delta`'s `prev_frame_id` equals the frame_id of the previously received data frame; on a deliberate mismatch the client requests a keyframe.
- [ ] Resize the desktop terminal hosting the pane; confirm a `dim` (0x05) frame is followed by a fresh `keyframe` (0x01).
- [ ] Produce a changed row containing an OSC8 hyperlink; confirm the `delta`'s `osc8` sidecar offsets are row-major over the delta's OWN rows array (subset-relative), and the decoder allows int map keys.
- [ ] Shrink pane content within fixed dimensions (drop a non-blank trailing line); confirm the `delta` carries `[row_id, []]` for the removed row and the client clears it (converges to a fresh keyframe).
- [ ] Sanity: an idle (unchanged) subscribed pane sends zero binary frames between changes; a focused pane updates at the fast cadence while idle panes stay quiet.
