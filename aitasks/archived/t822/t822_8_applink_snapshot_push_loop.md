---
priority: high
risk_code_health: medium
risk_goal_achievement: medium
effort: high
depends: [t822_7]
issue_type: feature
status: Done
labels: [ait_bridge]
risk_mitigation_tasks: [1007]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-11 10:41
updated_at: 2026-06-16 10:54
completed_at: 2026-06-16 10:54
---

Implement Stage 1 of the applink data plane: the snapshot push loop that parses `tmux capture-pane -e` output into the row/span schema and emits `keyframe`/`cursor`/`dim` MessagePack frames, driven by `subscribe`/`focus` cadences.

## Context

Third §"Deferred follow-up tasks" bullet of `aidocs/applink/monitor_port_design.md`. The wire format is **fixed** by `aidocs/applink/content_transport.md` (consume, do not redefine). Depends on t822_7 (listener carries the control verbs and the WS connection).

## Key Files to Modify

- `monitor_core` (from t822_6) — add the ANSI/SGR → styled-span parser and the snapshot-to-frame encoder.
- The applink listener (from t822_7) — add the per-pane push scheduler (cadence_idle_ms / cadence_focused_ms), `subscribe`, `focus`, `request_keyframe` control verbs, and the `pane_status` JSON push.

## Design decisions already made (design doc §Wiring PaneSnapshot to the content transport)

- **Parser:** ad-hoc SGR state machine tuned for `capture-pane -e` output — NOT `pyte`. The input is pre-rendered (no cursor movement / scroll regions / alt-screen); only SGR runs and OSC8 remain. Track `(fg, bg, attrs)` across `ESC[...m`, split lines into spans on attribute change, compute span `width` with tmux-compatible width tables.
- **Cadence mapping:** desktop 3 s refresh → `cadence_idle_ms: 3000`; 0.3 s fast preview → `cadence_focused_ms: 300`; server clamps client requests to its policy floor.
- **Focus:** single focused pane raises cadence; `focus` also performs desktop `switch_to_pane` at `monitor_control`+, cadence-only under `read_only`.
- **Scroll anchor:** render-side only — do NOT put anchor state on the wire; mobile rebuilds from `frame_id` continuity.
- **Non-content snapshot fields** (`idle_seconds`, `is_idle`, `awaiting_input`, `awaiting_input_kind`, window/category/session identity, task id/title/status) ride a JSON `push` frame `verb:"pane_status"` at idle cadence — NOT the binary plane.

## Reference Files

- `aidocs/applink/content_transport.md` — span/row schema, `keyframe`/`cursor`/`dim` layouts, subscribe/focus/back-pressure, compression (permessage-deflate mandatory)
- `aidocs/applink/monitor_port_design.md` — §Wiring PaneSnapshot to the content transport
- `monitor_core` capture pipeline (`capture_all_async`, `PaneSnapshot.content`)

## Implementation Plan

1. Write the SGR span parser + unit tests (sample `capture-pane -e` fixtures: colors, truecolor, attrs, OSC8, wide chars).
2. Implement frame encoders (MessagePack, 1-byte type tag) for `keyframe`, `cursor`, `dim`.
3. Implement the push scheduler on the listener's event loop, keyed by subscription; back-pressure rules from content_transport.md (coalesce → drop cursor → skip tick).
4. Wire `subscribe` (responds with initial keyframes), `focus`, `request_keyframe`, and the `pane_status` push.

## Verification Steps

- Unit tests for the SGR parser (no ANSI escapes survive into span text; widths match).
- A scripted WS client subscribes and decodes a valid `keyframe` for a live pane; receives `dim` + fresh keyframe after a resize.
- Focused pane updates at ~0.3 s; idle pane costs zero bytes between changes.
- `request_keyframe` returns a fresh keyframe within one tick.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-16T07:35:19Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-16T07:35:21Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-16T07:53:20Z status=pass attempt=1 type=human
