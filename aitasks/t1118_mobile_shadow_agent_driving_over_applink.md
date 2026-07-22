---
priority: high
effort: high
depends: []
xdeprepo: aitasks_mobile
issue_type: feature
status: Ready
labels: [applink, applink_control, shadow]
gates: [risk_evaluated]
children_to_implement: [t1118_1, t1118_2, t1118_3, t1118_4, t1118_5]
implemented_with: claudecode/fable5
created_at: 2026-07-03 07:54
updated_at: 2026-07-03 11:38
boardidx: 320
---

## Goal

Bring shadow-agent driving — spawning an advisory shadow companion beside a followed
code agent, interacting with it, picking and forwarding its concerns, and seeing
feedback-staleness warnings — to the mobile companion app (`aitasks_mobile`) over the
applink protocol. Today this capability lives only in `ait minimonitor`
(`e` spawn key, `c` concern picker); applink and the mobile app have zero shadow
awareness.

This is a complex cross-repo feature: planning must design a paired decomposition
spanning this repo (applink server + protocol docs) and `aitasks_mobile`
(wire layer + UI).

## Exploration findings (from /aitask-explore, 2026-07-03)

### Foundational gap: shadow panes are invisible to applink

- `monitor_core.discover_panes` drops shadow panes entirely
  (`.aitask-scripts/monitor/monitor_core.py` `_parse_list_panes`, the
  `is_shadow_target(parts[8])` skip) so they never reach snapshots, the applink
  roster, `pane_status` pushes, or the binary data plane. The mobile app cannot
  currently see, stream, or type into a shadow pane at all.
- Design decision needed: expose shadow panes to applink as a distinct pane
  category carrying their `@aitask_shadow_target` binding, WITHOUT un-hiding them
  in desktop agent lists / kill / sibling logic (the discovery-drop must stay for
  desktop semantics).

### Spawn verb — precedent exists, launch policy NOT needed

- Desktop spawn path: minimonitor `action_launch_shadow`
  (`monitor/minimonitor_app.py`) → `resolve_dry_run_command(root, "shadow",
  <pane_id> [<task_id>])` (`aitask_codeagent.sh` shadow operation, defaults from
  `defaults.shadow` in `codeagent_config.json`) → `launch_in_tmux` (same-window
  split by default, `tmux.shadow_same_window` / `shadow_pane_width` config) →
  stamp `@aitask_shadow_target` on the new pane → `attach_shadow_cleanup_hook`
  (shadow dies with followed agent). One-shadow-per-followed-agent guard.
- There is NO launch-config screen even on desktop — shadow spawns with pure
  defaults. So a `spawn_shadow` applink verb does NOT depend on the deferred
  applink workflow launch policy (t1011, which blocks `pick_next_sibling` /
  `restart_task` execution). Do not couple to it.
- Server-spawn precedent: the `spawn_tui` verb (`applink/router.py`) is already
  served, allowlist-validated, `full`-gated. `spawn_shadow` follows that pattern.
- Security (t985 conventions): validate `pane_id` against the live roster; no
  shell interpolation; reuse the shared sink guards.

### Interaction — nearly free once the pane is visible

- The shadow is an ordinary pane running a coding agent; the mobile app already
  streams any roster pane (binary grid frames → `PaneGrid` renderer) and types
  into any pane (`KeyForwarderBar` → `send_keys` / `forward_key`, gated on
  `canControl`). Once shadow panes enter the roster, the existing pane viewer +
  key bar work as-is.

### Concern pick-and-forward — server-side RPC required

- Shadow emits the ASCII-fenced `===AITASK-CONCERNS===` block
  (`aidocs/framework/shadow_concern_format.md`); minimonitor parses it with pure
  helpers `parse_concerns` / `has_concern_block` (`monitor/concern_parser.py`)
  and forwards via ConcernPickerModal → clipboard → user pastes.
- Clipboard does not cross the wire. Mobile flow: a `shadow_concerns` RPC returns
  the parsed concern list; the user picks concerns in a native UI; forwarding is
  composed client-side as an ordinary `send_keys` into the FOLLOWED pane
  (user-initiated, preserving the advisory-only model — the shadow itself never
  inputs into the followed pane).
- Parsing MUST be server-side: the concern parser's capture-join contract
  requires wrap-joined capture (`tmux capture-pane -J`), while the data plane
  streams visual (wrapped) rows — client-side parsing of the streamed grid would
  corrupt long concerns.
- Consider parity with minimonitor's proactive auto-offer (`has_concern_block`
  strict trigger, de-dup on payload) — e.g. a `pane_status` field or push flag
  signalling "fresh complete concern block present".

### Staleness + binding metadata — additive pane_status fields

- Desktop staleness (t1104): `@aitask_shadow_analyzed_at` stamp (written by
  `aitask_shadow_capture.sh`) compared against the followed pane's last-change
  wall time → "shadow advice is stale" warning + stale banner in the concern
  picker.
- Mobile parity: ride the existing `pane_status` JSON push
  (`applink/pusher.py` `_send_pane_status`, which already carries `task_id`,
  `title`, `awaiting_input`...) with additive fields, e.g. on the followed
  agent's status: bound `shadow_pane` id, `shadow_stale` flag / `analyzed_at`.
  Old clients ignore unknown keys by design; NO protocol `v` bump anywhere in
  this feature (all changes are additive per `aidocs/applink/protocol.md`
  §Versioning).

### Permission gating (proposal — confirm at planning)

- `spawn_shadow` → `full` band (same as `spawn_tui`; it launches an agent).
- `shadow_concerns` → `read_only` band (pure read, same band as `task_detail`).
- Concern forwarding → no new verb; client composes `send_keys`
  (`monitor_control`).
- Kill/lifecycle: existing `kill_pane` covers manual kill; auto-cleanup via the
  existing `pane-died` hook. Sync `aidocs/applink/permissions.md` +
  `aitasks/metadata/applink_profiles/*.yaml` together (t822_12 pattern).

### Mobile side (aitasks_mobile) — greenfield, established seam

- No shadow-related Kotlin code exists. Extension seam per feature:
  `@Serializable` payloads in `domain/.../applink/wire/ControlFrames.kt`
  (snake_case `@SerialName`, error codes in `MonitorErrCodes`) → suspend verb
  wrappers on `domain/.../applink/monitor/MonitorSessionMediator.kt` (+ push
  handling in `onPush`) → surface via `shared/.../monitor/MonitorScreenModel.kt`
  → Compose UI under `shared/.../monitor/` → DI in `shared/.../di/AppKoinModule.kt`.
- Client gate today is `canControl = profile != "read_only"`; server
  `PERMISSION_DENIED` is the backstop.
- UI work: spawn-shadow action on a followed agent, shadow-pane viewer entry
  (reuses `PaneContentViewer`), concern picker sheet (parity with
  `ConcernPickerModal`, incl. stale banner), staleness badge on the pane list.

## Suggested decomposition shape (for planning)

1. Protocol/design doc: `aidocs/applink/shadow_driving.md` — roster exposure
   decision, verb inventory + payload schemas, permission gating, `pane_status`
   extensions. Update `monitor_port_design.md` / `permissions.md` cross-refs.
2. Server: shadow-aware roster + data plane (expose shadows with binding
   metadata; keep desktop discovery-drop semantics intact).
3. Server: `spawn_shadow` verb + lifecycle (one-per-agent guard, target stamping,
   cleanup hook, confirm handshake if gated as destructive-adjacent).
4. Server: `shadow_concerns` RPC (wrap-joined capture + `concern_parser` reuse) +
   staleness/binding fields on `pane_status`.
5. Mobile (xdeprepo: aitasks_mobile, paired tasks created at planning): wire +
   mediator layer; shadow UI (spawn, viewer, concern picker, stale badge).

## Related (not folded)

- t1216 (monitor shadow pane view + concern picker) — the **desktop** counterpart:
  brings shadow display, shadow interaction, and the concern picker to
  `ait monitor`. Not a fold and not a dependency in either direction, but the two
  share the same foundation: shadow panes are dropped by
  `monitor_core._parse_list_panes` and must stay dropped for desktop agent-list /
  kill / sibling semantics, while being exposed as a distinct category to their
  respective consumers. Whichever lands first should leave the shadow-exposure
  seam reusable by the other rather than solving it locally.
- t1011 (applink workflow launch policy) — adjacent server-side launching work;
  explicitly NOT a dependency (see above).
- t1017 (shadow steerability), t996 (shadow resize own pane) — shadow-skill
  concerns, out of scope here.
