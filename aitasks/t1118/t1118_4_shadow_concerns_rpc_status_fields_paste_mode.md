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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1118** id=2026-11-09T08:33:51Z.87c7005201689f4ebb1222c8 from=t1118 at=2026-11-09T08:33:50Z base=87b720e7ce727f7a18ece35fa8a70c070fc81f9a base_branch=main dirty=yes host=omg16
>
> | Advisory from the user-requested review of t1118; not an implementation approval. Source inspected at aitasks HEAD 87b720e7ce727f7a18ece35fa8a70c070fc81f9a.
> | 
> | Significant drift in the current child plan:
> | 
> | 1. Freshness is no longer the old synchronous stamp-to-last_change boolean. monitor_core.compute_shadow_staleness is shared and async; get_pane_option returns (ok, value). Unreadable/malformed stamps or unobserved followed panes yield UNKNOWN, preserving a standing warning; a verified empty stamp is distinct. Desktop concern UI also computes compute_block_age_staleness from THIS captured block's Round timestamp and joins with combine_staleness. A shadow can reread and answer only in prose, refreshing analyzed_at but leaving old concerns stale. The plan's stale:bool/malformed=>false wire model needs reconciliation with t1118_1 and paired mobile#32_1/#32_2, not silent coercion of unknown to fresh. Read-recency metadata and content-derived block age have different permission implications.
> | 
> | 2. Caching the complete verdict solely on shadow content changes is insufficient: the followed pane can advance, or analyzed_at can change, while the concern block is unchanged. Parsing may remain content-change-gated; freshness needs the current relevant stamp/followed change and block identity. Current desktop separates these signals explicitly (aidocs/framework/shadow_agent.md 'Block age vs read recency'). RPC freshness should describe its actual capture, not a cached earlier round.
> | 
> | 3. The hard 200-line cap predates t1187. Desktop capture_shadow_text uses the deep 400-line default and the explicit picker retries at 1500 if block_head_truncated detects a clipped opening fence. Newest-block-wins, certified metadata-only clean rounds, malformed/unrecovered markers, and ANSI-free + wrap-joined input are current parser contracts. The planned 200-line-only RPC can falsely return no concerns. See monitor_core.py:capture_shadow_text/_SHADOW_DEEP_RETRY_LINES and minimonitor_app.py:action_pick_concerns; tests/test_minimonitor_concern_action.py and test_concern_parser.py. The current format source is .claude/skills/aitask-shadow/concern-format.md, not the missing aidocs/framework/shadow_concern_format.md. Non-stamping remains essential: capture_shadow_text shells out to the helper and is not a drop-in passive read from a shadow-hosted caller.
> | 
> | 4. Producer shadows already occupy a separate shadow_snapshots map keyed by FOLLOWED id and stay out of _pane_cache/get_pane/discover_panes/capture_all_async. The binding map cannot be derived only from the old agent roster. MonitorClient transports shadow snapshots and get_last_change_wall for both record types, but does not expose producer internals in SERVER mode. The shared verdict cache can be applink-server-owned; it need not be attached to an assumed local producer. MonitorClient.capture/server capture returns the ordinary ANSI-bearing non-joined capture, so it does not satisfy concern-parser input by itself. An explicit -J + cleaning gateway path remains necessary unless a suitable server capture contract is deliberately added.
> | 
> | 5. A new monitor.paste_text call is not automatically delegated by MonitorClient: SERVER mode delegates only GATEWAY_NAMES, and tests/test_monitor_client_surface.py guards that contract. Either a local gateway seam or an explicitly supported client gateway method is needed. As of this audit applink/server.py still owns TmuxMonitor and t2037_4 is in flight, so the eventual landed client/lifecycle/deferred-reply design must be rechecked. Any awaited server round trip belongs outside a serialized phone request-dispatch path; the current router is synchronous.
