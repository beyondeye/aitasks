---
priority: medium
effort: low
depends: [t822_9]
issue_type: feature
status: Implementing
labels: [ait_bridge]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-11 10:42
updated_at: 2026-06-16 12:19
---

Implement Stage 3 of the applink data plane: the `append` fast path for log-streaming panes — bottom-cursor + no-upper-changes detection and `append` frame emission.

## Context

Fifth §"Deferred follow-up tasks" bullet of `aidocs/applink/monitor_port_design.md`. Makes `tail -f`-style output (agent logs, build output) stream at sub-100 B/line. Depends on t822_9 — the detection check lives next to the deltifier, which already has previous and current row sets in hand (design doc §Append fast-path detection).

## Key Files to Modify

- `monitor_core` deltifier (t822_9) — add the append detector as a cheap prefix comparison before falling back to a full delta.
- Push scheduler — emit `append` frames (`[0x03, pane_id, frame_id, [row,...]]`).

## Emission conditions (content_transport.md §append — all required)

- Cursor at the bottom row before and after the update.
- No rows above the bottom changed.
- No scroll-region/alt-screen activity (fall back to `delta`).

`append` carries no `prev_frame_id` — each is independent and additive on the latest `keyframe`/`delta`; client drops the topmost row to maintain the row count.

## Reference Files

- `aidocs/applink/content_transport.md` — §append, §Staged rollout (Stage 3)
- `aidocs/applink/monitor_port_design.md` — §Append fast-path detection

## Implementation Plan

1. Add bottom-growth detection to the deltifier (prefix comparison of row hashes).
2. Emit `append` with only the new bottom rows; keep frame_id chain semantics per spec.
3. Tests: log-append sequence → `append` frames; mid-screen edit → falls back to `delta`; alt-screen toggle → `delta`/`keyframe`.

## Verification Steps

- Streaming `seq 1 1000` in a subscribed pane produces predominantly `append` frames (assert via scripted client).
- vim-style mid-screen edits never produce `append`.
- Client-rendered buffer matches a requested keyframe after a long append run.
