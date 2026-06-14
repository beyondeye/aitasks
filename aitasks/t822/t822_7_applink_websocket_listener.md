---
priority: high
risk_code_health: medium
risk_goal_achievement: medium
effort: high
depends: [t822_6]
issue_type: feature
status: Implementing
labels: [ait_bridge]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-11 10:41
updated_at: 2026-06-14 11:38
---

Wire the `ait applink` TUI to start a TLS WebSocket server on launch, accept the `pair` verb, and route subsequent control frames per the canonical verb table, enforcing permission profiles.

## Context

Second §"Deferred follow-up tasks" bullet of `aidocs/applink/monitor_port_design.md`. The TUI skeleton + QR pairing screen landed in t822_2; the protocol contract is `aidocs/applink/protocol.md` (envelope, pairing flow, state machine) and `aidocs/applink/permissions.md` (profiles). Depends on t822_6: verbs execute through `monitor_core`.

## Key Files to Modify

- `.aitask-scripts/applink/` — add the WS server module(s): TLS socket (self-signed cert per protocol.md §Pairing flow), pairing-token validation, bearer session table, frame router.
- The applink TUI app — start/stop the listener, surface connection state (Discovering → Pairing → Connected → Suspended → Disconnected), wire the `r` (revoke/new-QR) keybinding semantics from protocol.md.

## Scope

- Implement the JSON control plane only: `pair`, `resume`, `bye`, and the command verbs from the design doc's verb table that map directly onto `monitor_core` calls (`send_enter`, `send_keys`, `forward_key`, `focus`/`switch_to_pane`, `cycle_compare_mode`, `kill_pane` → `kill_agent_pane_smart`, `kill_window`, `spawn_tui`, `task_detail`).
- `forward_key` performs the `_TEXTUAL_TO_TMUX` translation server-side (map moves/copies out of `monitor_app.py` per the design doc).
- Enforce profile gating: verb above the session tier → `err` `PERMISSION_DENIED` with `detail.required_profile` (permissions.md).
- Confirmation flow for destructive verbs uses the pull model from the design doc §Modal-dialog handshakes (`confirmed:false` → `confirm_required` response) — full multi-step handshakes (sibling task) can stub.
- The binary data plane (snapshot push) is NOT in scope — next sibling.
- `pick_next_sibling` / `restart_task` mobile execution is deferred (design doc note) — return `UNKNOWN_VERB` or a `deferred` error for now.

## Reference Files

- `aidocs/applink/monitor_port_design.md` — §Command verb → applink protocol mapping (payload schemas, gates)
- `aidocs/applink/protocol.md` — envelope, pairing, state machine, error codes
- `aidocs/applink/permissions.md` — profile YAML shape, storage under `aitasks/metadata/applink_profiles/`
- `aiplans/archived/p822/p822_2_applink_tui_qr.md` — how the QR/pairing screen was built

## Implementation Plan

1. Re-read the three aidocs; re-verify monitor_core symbol names post-t822_6.
2. Implement session table (bearer, profile, device name; persisted per permissions.md §Storage) + token validation.
3. Implement the frame router: parse envelope, auth check, profile gate, dispatch to monitor_core, reply `res`/`err`.
4. Ship `aitasks/metadata/applink_profiles/{read_only,monitor_control,full}.yaml` and the profile validator hook described in permissions.md (or create a follow-up if split).
5. Integrate listener lifecycle into the applink TUI with connection-state display.

## Verification Steps

- Pair a test client (e.g. `python -m websockets` script) via the QR URI values; receive bearer + profile.
- Exercise an allowed verb and a disallowed verb (expect `PERMISSION_DENIED`).
- Revoke from the TUI; next frame gets `AUTH_FAILED`.
- `send_keys`/`send_enter` reach a live tmux pane.
