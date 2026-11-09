---
priority: high
effort: medium
depends: []
issue_type: documentation
status: Ready
labels: [applink, applink_control, shadow]
gates: [risk_evaluated]
anchor: 1118
created_at: 2026-07-03 11:28
updated_at: 2026-07-03 11:28
---

## Context

First child of t1118 (mobile shadow-agent driving over applink; paired with
`aitasks_mobile#32`). Authors the protocol/design doc that is the single wire
contract both repos build against. Parent plan:
`aiplans/p1118_mobile_shadow_agent_driving_over_applink.md` (sections D1-D5 are
the content source).

## Work

Author **`aidocs/applink/shadow_driving.md`** covering:

- **Roster exposure decision (D1):** shadow panes enter the applink roster via a
  `TmuxMonitor(include_shadow_panes=True)` opt-in flag consumed in
  `_parse_list_panes`; desktop discovery-drop stays the default. New
  `PaneCategory.SHADOW`, `TmuxPaneInfo.shadow_target`.
- **Visibility model:** metadata for all profiles; shadow-pane CONTENT streaming
  gated at `monitor_control` (subscribe `content_panes` filter — D2b).
- **Verb payload schemas (D2):** `spawn_shadow` `{pane_id}` (FOLLOWED pane,
  `full` band; errors: `shadow_exists` detail) and `shadow_concerns` `{pane_id}`
  (SHADOW pane, `monitor_control` band; errors: `not_shadow_pane`; response
  `{concerns:[{priority,region,body}], followed_pane, analyzed_at?, stale}`).
- **Capability flags:** `pair`/`resume` response additive fields
  `allowed_verbs: [...]` + `caps: {shadow_content: bool}` — the server-owned
  truth mobile gates UI off (never profile-name ordering).
- **`pane_status` extensions (D3)** incl. the **field-level profile split**:
  binding/staleness fields (`shadow_target`, `shadow_pane`, `shadow_stale`,
  `shadow_analyzed_at`) = content-free metadata for all profiles;
  `shadow_has_concerns` = content-derived, suppressed below `monitor_control`.
- **D2-inv non-stamping invariant:** passive server inspection must NEVER write
  `@aitask_shadow_analyzed_at`; applink capture paths use raw gateway
  `capture-pane -J`, never `aitask_shadow_capture.sh`.
- **D3-cost contract:** change-gated re-parse (existing per-pane change
  tracking), depth cap 200 lines, shared per-pane verdict cache across
  connections.
- **`send_keys` `paste: bool` mode (D4):** bracketed paste via
  `load-buffer` + `paste-buffer -p -d`; stage-only forwarding semantics.
- **Advisory-only invariant** (shadow never inputs into the followed pane;
  forwarding is user-initiated) and staleness semantics (t1104 model).

Also update in the same change:
- `aidocs/applink/monitor_port_design.md` — add canonical verb-table rows for
  `spawn_shadow` / `shadow_concerns` (+ `send_keys` payload gains `paste?:bool`),
  marked "implementation pending".
- `aidocs/applink/permissions.md` — gating rows (`spawn_shadow`→full,
  `shadow_concerns`→monitor_control), marked "implementation pending" (yaml
  profile updates land with the implementing children A3/A4).
- `aidocs/applink/protocol.md` — cross-reference to the new doc.

## Reference files

- `aiplans/p1118_mobile_shadow_agent_driving_over_applink.md` (authoritative)
- `aidocs/framework/shadow_agent.md`, `aidocs/framework/shadow_concern_format.md`
- t822_12 archived plan for the docs+profiles sync pattern

## Verification

- Docs-only change: internal cross-links resolve; the verb table, permissions
  table, and shadow_driving.md agree with the parent plan's D-sections verbatim
  where they overlap.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1118** id=2026-11-09T08:33:29Z.01155b6800b7184b75909cd1 from=t1118 at=2026-11-09T08:33:29Z base=87b720e7ce727f7a18ece35fa8a70c070fc81f9a base_branch=main dirty=yes host=omg16
>
> | Advisory from the user-requested architecture review of t1118 and its existing plans; this is context, not an implementation approval. Source code inspected at aitasks HEAD 87b720e7ce727f7a18ece35fa8a70c070fc81f9a.
> | 
> | The parent plan's instruction to transcribe D1-D5 verbatim would now document obsolete implementation and freshness contracts:
> | 
> | 1. D1: monitor_core.TmuxPaneInfo already has shadow_target. _parse_list_panes returns separate agent-facing and shadow lists; shadows deliberately remain category AGENT for coding-agent classification and stay OUT of _pane_cache. shadow_snapshots()/get_shadow_snapshot() already expose them, keyed by FOLLOWED pane id. status_protocol and MonitorClient already transport this separate shadow map with include_shadows. Adding a producer-wide include_shadow_panes flag / SHADOW category as written would change established desktop and wire invariants. The missing piece is an applink-facing view, not discovery from scratch. See monitor_core.py:_parse_list_panes, commit_snapshots; status_client.py:shadow_snapshots, get_pane; status_protocol.py:filter_message.
> | 
> | 2. D2.1: the shared, Textual-free monitor_core.spawn_shadow already exists and both desktop TUIs use it. It now preserves launch identity, refuses unverifiable duplicate checks, removes panes whose binding stamp fails, and uses attach_companion_cleanup_hook. The proposed extraction / launch_in_tmux-then-pid-lookup recipe predates these fixes.
> | 
> | 3. D3 freshness: compute_shadow_staleness now returns a tri-state and reads get_pane_option as (ok, value); malformed/unverifiable is UNKNOWN, not fresh. Current desktop feedback also joins read recency with compute_block_age_staleness + combine_staleness: a prose-only refetch can refresh analyzed_at while the old Round block remains stale. The planned RPC stale:Boolean and the old 'malformed => false' behavior need contract reconciliation before mobile implementation. Metadata-only status must still respect the promised content/permission boundary; block age is derived from concern content, unlike read-recency metadata.
> | 
> | 4. D3-cost's mandatory 200-line ceiling predates t1187: capture_shadow_text uses the deep window (400 by default), and explicit desktop concern reads retry at _SHADOW_DEEP_RETRY_LINES=1500 when the block head was clipped. Current parser input is ANSI-free AND wrap-joined. Neither ordinary status snapshots nor MonitorClient.capture satisfy that shape (producer capture uses -p -e without -J). The non-stamping invariant remains valid; blindly calling capture_shadow_text from this shadow-hosted session is not a safe replacement for the planned passive gateway path. The format source is .claude/skills/aitask-shadow/concern-format.md; aidocs/framework/shadow_concern_format.md no longer exists.
> | 
> | As of this audit, applink/server.py still owns TmuxMonitor; t2037_4 is in flight and its plan lookup returned NOT_FOUND. The shared-server migration is a coordination dependency to recheck, not a completed change. Decisions discussed in its UI are not landed architecture.
> | 
> | Paired mobile tasks aitasks_mobile#32_1/#32_2 repeat the boolean freshness model and old format reference. Their existing scope includes the affected wire/UI work. As of this audit that repository has no .aitask-scripts/aitask_note.sh, so it cannot receive cross-repository notes through the supported writer; the server contract review needs this cross-repo context available.
