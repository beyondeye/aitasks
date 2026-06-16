---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: [t822_8]
issue_type: feature
status: Implementing
labels: [ait_bridge]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-11 10:41
updated_at: 2026-06-16 11:31
---

Implement Stage 2 of the applink data plane: server-side delta encoding — per-row hashing + changed-row collection — emitting `delta` frames against `prev_frame_id`, with the `request_keyframe` recovery path.

## Context

Fourth §"Deferred follow-up tasks" bullet of `aidocs/applink/monitor_port_design.md`. Stage 1 (t822_8) ships keyframes only; this stage makes bandwidth viable for cellular/relay (<100 B/update for most workloads per content_transport.md). Wire format is fixed — `delta` frame layout is already specified.

## Key Files to Modify

- `applink/content.py` — the deltifier: pure `deltify` / `row_signature` / `build_osc8` helpers + the `encode_delta` (0x02) encoder. Per-row hash state is kept **per-connection** on `Subscription.PaneState.row_sigs`, NOT in `monitor_core` and NOT in `monitor_app.py`'s render loop. **Deviation from the original design-doc wording** (which named `monitor_core` with "a single hash cache regardless of attached clients"): a delta is computed against the specific frame each client last received, so the diff baseline is irreducibly per-client; the capture pipeline that needs sharing is already shared via `monitor_core.capture_all_async` (t822_8); a cross-client hash cache would couple the shared TUI core to applink's subscription lifecycle for no real benefit. Extends t822_8's boundary (its Final Notes hand off "t822_9's deltifier will extend content.py"). `monitor_port_design.md` §Deltification + §Append fast-path updated to match.
- `applink/pusher.py` — the push scheduler (t822_8): choose `delta` vs `keyframe` per tick in `_push_pane`: forced keyframe on `keyframe_interval_ms`, on subscribe/resume, when delta cost ≥ keyframe cost, or on `request_keyframe`.

## Constraints

- The existing whole-pane change tracking (`_last_content`/`_last_change_time`) stays separate — it feeds idle detection; the deltifier hashes per-row. Merging them is a non-goal (design doc).
- `prev_frame_id` chain is linear (most recent keyframe OR delta); on client mismatch the client requests a keyframe — there is no replay buffer.

## Reference Files

- `aidocs/applink/content_transport.md` — §delta, §Frame integrity and recovery, §Staged rollout (Stage 2)
- `aidocs/applink/monitor_port_design.md` — §Deltification responsibility

## Implementation Plan

1. Per-connection per-row hash state (`Subscription.PaneState.row_sigs`, in `content.py`) with invalidation on `dim`/resize (forced keyframe) and (re)subscribe (force-seeded keyframe).
2. Diff pass producing changed-row list; cost comparison vs full keyframe.
3. Emit `delta` with correct `frame_id`/`prev_frame_id`; bump chain on every data frame.
4. Tests: synthetic frame sequences (change 1 row of 40 → delta with 1 row; resize → dim + keyframe; simulated gap → client-side mismatch triggers keyframe request).

## Verification Steps

- Scripted WS client: applies deltas over a keyframe and matches a freshly requested keyframe byte-for-byte (row content equality).
- A single-row change produces a frame well under the full-keyframe size.
- Dropping a delta client-side and sending `request_keyframe` recovers within one tick.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-16T08:31:22Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-16T08:31:24Z status=pass attempt=1 type=machine
