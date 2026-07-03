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
