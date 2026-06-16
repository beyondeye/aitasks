---
priority: medium
effort: medium
depends: [t822_8]
issue_type: feature
status: Implementing
labels: [ait_bridge]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-11 10:41
updated_at: 2026-06-16 11:00
---

Implement Stage 2 of the applink data plane: server-side delta encoding — per-row hashing + changed-row collection — emitting `delta` frames against `prev_frame_id`, with the `request_keyframe` recovery path.

## Context

Fourth §"Deferred follow-up tasks" bullet of `aidocs/applink/monitor_port_design.md`. Stage 1 (t822_8) ships keyframes only; this stage makes bandwidth viable for cellular/relay (<100 B/update for most workloads per content_transport.md). Wire format is fixed — `delta` frame layout is already specified.

## Key Files to Modify

- `monitor_core` — the deltifier: per-row hash cache per (pane, session), changed-row collection between captures. Lives in monitor_core (NOT `monitor_app.py`'s render loop) so the Textual UI and applink listener share one capture pipeline and a single hash cache regardless of attached clients (design doc §Deltification responsibility).
- The push scheduler (t822_8) — choose `delta` vs `keyframe` per tick: forced keyframe on `keyframe_interval_ms`, on subscribe/resume, when delta cost ≥ keyframe cost, or on `request_keyframe`.

## Constraints

- The existing whole-pane change tracking (`_last_content`/`_last_change_time`) stays separate — it feeds idle detection; the deltifier hashes per-row. Merging them is a non-goal (design doc).
- `prev_frame_id` chain is linear (most recent keyframe OR delta); on client mismatch the client requests a keyframe — there is no replay buffer.

## Reference Files

- `aidocs/applink/content_transport.md` — §delta, §Frame integrity and recovery, §Staged rollout (Stage 2)
- `aidocs/applink/monitor_port_design.md` — §Deltification responsibility

## Implementation Plan

1. Row hash cache keyed by (pane_id, session_bearer) with invalidation on `dim`/resize and unsubscribe.
2. Diff pass producing changed-row list; cost comparison vs full keyframe.
3. Emit `delta` with correct `frame_id`/`prev_frame_id`; bump chain on every data frame.
4. Tests: synthetic frame sequences (change 1 row of 40 → delta with 1 row; resize → dim + keyframe; simulated gap → client-side mismatch triggers keyframe request).

## Verification Steps

- Scripted WS client: applies deltas over a keyframe and matches a freshly requested keyframe byte-for-byte (row content equality).
- A single-row change produces a frame well under the full-keyframe size.
- Dropping a delta client-side and sending `request_keyframe` recovers within one tick.
