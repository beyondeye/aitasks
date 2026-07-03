---
priority: high
effort: high
depends: [1118_2]
issue_type: feature
status: Ready
labels: [applink, applink_control, shadow]
gates: [risk_evaluated]
anchor: 1118
created_at: 2026-07-03 11:29
updated_at: 2026-07-03 11:29
---

## Context

Fourth child of t1118 (paired with `aitasks_mobile#32`); parallel to t1118_3
(depends only on t1118_2). Adds the `shadow_concerns` RPC, the shadow
staleness/binding fields on `pane_status`, and the `send_keys` paste mode.
Parent plan: `aiplans/p1118_mobile_shadow_agent_driving_over_applink.md`
(D2.2, D2-inv, D3, D3-cost, D4, D5).

## Key files to modify

- `.aitask-scripts/applink/router.py` — `shadow_concerns` verb
  (`monitor_control` band): validate pane-id format + roster membership +
  `shadow_target` non-empty (else `BAD_PAYLOAD detail:{reason:"not_shadow_pane"}`);
  response `{concerns:[{priority,region,body}], followed_pane,
  analyzed_at: epoch|null, stale: bool}`. Also `send_keys` gains optional
  `paste: bool` (default false → dispatch byte-for-byte unchanged).
- `.aitask-scripts/monitor/monitor_core.py` — server-side wrap-joined capture
  for concern reads (`capture-pane -J`, depth-capped 200 lines) reusing
  `monitor/concern_parser.parse_concerns` (forgiving variant for the RPC) and
  `has_concern_block` (strict, for status detection); staleness verdict = same
  compare as minimonitor `_update_shadow_freshness`
  (`get_pane_option(shadow, SHADOW_ANALYZED_AT_OPTION)` vs
  `get_last_change_wall(followed)` + refresh-tick epsilon). New
  `paste_text(pane_id, text)` beside `send_keys`: tmux `load-buffer` (stdin, no
  shell interpolation) + `paste-buffer -p -d -t <pane>` (bracketed paste,
  buffer deleted), gateway-routed.
- `.aitask-scripts/applink/pusher.py` — `_send_pane_status`: on FOLLOWED panes
  with a bound shadow add `shadow_pane`, `shadow_stale`, `shadow_analyzed_at`,
  and `shadow_has_concerns`. **Field-level profile split:** `shadow_has_concerns`
  is content-derived → suppressed for `read_only` connections (PushScheduler is
  per-connection and knows the profile); binding/staleness fields go to all.
- Shared `ShadowStatusCache` keyed by `pane_id` on/next to the shared monitor
  instance: `(last_change_marker, has_concerns, analyzed_at, payload_hash)`.
- Profile yamls: `shadow_concerns` in `monitor_control.yaml` + `full.yaml` +
  `DEFAULT_ALLOWED` (same commit) + flip `permissions.md` row.

## NON-NEGOTIABLE invariants (from parent plan)

- **D2-inv (non-stamping):** passive inspection NEVER writes
  `@aitask_shadow_analyzed_at`. Use raw gateway `capture-pane -J` directly —
  NEVER shell out to `aitask_shadow_capture.sh` (it stamps when run inside a
  shadow pane). Negative-control test required: status tick + `shadow_concerns`
  call leave the stamp byte-identical.
- **D3-cost:** change-gated (re-capture/re-parse only when the shadow pane's
  content changed per existing `_last_change_time` tracking; unchanged ⇒ cached
  verdict, zero capture/parse); depth cap 200; ONE capture+parse per content
  change shared across N connections.

## Verification

- Router tests: happy path, `not_shadow_pane` rejection, `monitor_control`
  gating, paste-flag routing, **no-paste byte-for-byte send_keys regression**
  (StubMonitor records unchanged `send_keys(pane_id, keys, literal)`, no buffer
  commands).
- Staleness compare cases (fresh / stale / absent stamp / malformed stamp).
- **Non-stamping negative control** (see above).
- Cost spies: two ticks unchanged content ⇒ exactly one parse; change ⇒ one
  re-parse; two connections share one parse; capture call carries the depth cap.
- Field-split test: read_only conn lacks `shadow_has_concerns`, monitor_control
  conn has it, same tick.
- `paste_text` gateway spy: load-buffer stdin + `-p` flag; multi-line payload
  arrives without submitting.
