---
priority: high
effort: medium
depends: [t1118_1]
issue_type: feature
status: Ready
labels: [applink, applink_control, shadow]
gates: [risk_evaluated]
anchor: 1118
created_at: 2026-07-03 11:29
updated_at: 2026-07-03 11:29
---

## Context

Second child of t1118 (paired with `aitasks_mobile#32`). Exposes shadow panes to
the applink roster without changing desktop semantics, gates their content per
profile, and adds the capability flags mobile gates UI off. Parent plan:
`aiplans/p1118_mobile_shadow_agent_driving_over_applink.md` (D1, D2b, D3 shadow_target).

## Key files to modify

- `.aitask-scripts/monitor/monitor_core.py` — `TmuxPaneInfo` gains
  `shadow_target: str = ""` (~line 234); new `PaneCategory.SHADOW`;
  `TmuxMonitor.__init__` gains `include_shadow_panes: bool = False`;
  `_parse_list_panes` (~1017): flag False → current drop unchanged
  (`is_shadow_target(parts[8]) → continue`); True → keep pane with
  `shadow_target=parts[8]`, `category=PaneCategory.SHADOW`.
- `.aitask-scripts/applink/applink_app.py` + `.aitask-scripts/applink/headless.py`
  — construct the monitor with `include_shadow_panes=True`.
- `.aitask-scripts/applink/pusher.py` — `_send_pane_status` (~388) additively
  emits `shadow_target` on SHADOW panes.
- `.aitask-scripts/applink/router.py` — D2b content gating: in `subscribe`,
  for a `read_only` session (`conn.session.profile`), filter shadow panes out of
  the effective `content_panes` set (roster/status subscription untouched).
  `request_keyframe`/`history` already reject via `streams_content` /
  `not_subscribed` once the filter is in place. Also: `pair`/`resume` response
  payloads gain additive `allowed_verbs: [...]` (from the profile gate) and
  `caps: {shadow_content: bool}` (true for monitor_control+). Pair response is
  built in `_do_pair` (~258); resume path likewise.

## Constraints (from parent plan)

- Desktop TUIs behaviorally unchanged — the flag defaults False everywhere else.
- Audit downstream applink consumers for the new SHADOW category:
  `_discover_pane_ids` (subscribe-all now includes shadows — intended),
  `kill_agent_pane_smart` real-agent count (keys off the marker — verify
  unchanged), snapshot capture path.
- All wire changes additive; no protocol `v` bump.

## Reference patterns

- t1045 roster-vs-content split (`Subscription.streams_content`,
  `content_panes` handling in router `subscribe`, `not_content_pane` rejection).
- `tests/test_applink_router.sh` StubMonitor harness;
  `tests/test_applink_pusher.sh` for pane_status fields.

## Verification

- Tests: `_parse_list_panes` with flag on/off (**negative control: flag off ⇒
  stamped shadow pane still dropped**); pusher emits `shadow_target` on shadow
  panes and omits it elsewhere; subscribe-all includes shadows in roster;
  read_only content filter excludes shadows from `content_panes` +
  `request_keyframe` on a shadow rejected for read_only but accepted for
  monitor_control; pair-response `allowed_verbs`/`caps` per profile.
- `bash tests/test_applink_router.sh`, `bash tests/test_applink_pusher.sh`,
  existing monitor tests unchanged.
