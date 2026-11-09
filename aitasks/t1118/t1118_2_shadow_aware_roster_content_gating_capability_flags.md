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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1118** id=2026-11-09T08:33:46Z.0f514912fd7293951cf85a3a from=t1118 at=2026-11-09T08:33:46Z base=87b720e7ce727f7a18ece35fa8a70c070fc81f9a base_branch=main dirty=yes host=omg16
>
> | Advisory from the user-requested review of t1118; not an implementation approval. Source inspected at aitasks HEAD 87b720e7ce727f7a18ece35fa8a70c070fc81f9a.
> | 
> | The task/child plan's D1 implementation is significantly stale. TmuxPaneInfo.shadow_target already exists. _parse_list_panes now returns (agent_facing_panes, shadow_panes); shadows are forced to category AGENT so prompt/idle classification applies, and commit_snapshots deliberately excludes/evicts them from _pane_cache. They already live in shadow_snapshots()/get_shadow_snapshot(), keyed by FOLLOWED pane id. Scratchpads/sitrep helpers are excluded separately, with frozen stand-ins taking precedence. See monitor_core.py:_parse_list_panes, commit_snapshots, shadow_snapshots; status_protocol.py:pane_info_member, filter_message.
> | 
> | MonitorClient already subscribes with include_shadows and exposes shadow_snapshots, but capture_all_async, discover_panes, and get_pane intentionally return only agent-facing records; _seed_cache seeds only those. Merely enabling include_shadows will therefore NOT expose shadow panes in applink's roster or content loop. The missing seam is an applink view/adapter which projects the existing shadow map by each shadow's OWN pane id for roster, lookup, and pushes while retaining the producer's agent/shadow cache boundary. Populating the shared _pane_cache or changing the producer-wide category would affect desktop invariants and the status protocol's validated enum.
> | 
> | The plan's construction sites are also obsolete: AppLinkServer in applink/server.py currently constructs the monitor; applink_app.py/headless.py construct the server. As of this audit t2037_4 is in flight to replace status polling with MonitorClient, so its eventual landed ownership/lifecycle must be checked before implementing this child. That migration has not yet changed server.py in this checkout.
> | 
> | Shadow lookup alone is insufficient for content: capture_pane_content_async normally requires a cached pane, but accepts an explicit pane object for shadow reads. Applink's current history path uses the id-only form, and current switch_to_pane/capture_pane consumers are cache-backed. These consumers need to be assessed against the applink projection rather than assuming a new enum makes them shadow-aware. The shared-server capture path already resolves shadows separately. Own-pane filtering and the metadata-for-all/content-gated behavior remain requirements.
> | 
> | The old negative control ('flag false drops the shadow') is no longer the right architectural assertion. Existing invariants are: desktop agent lists/cache remain shadow-free, the separate shadow snapshots remain available for desktop shadow UI, scratchpads stay excluded, and frozen precedence remains intact. Relevant existing coverage includes tests/test_monitor_shadow_status.py, tests/test_shadow_snapshot.sh, tests/test_monitor_client_surface.py and status server/client tests.
