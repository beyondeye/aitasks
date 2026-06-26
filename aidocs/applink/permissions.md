# AppLink Permission Profiles

How the `ait applink` server decides which mobile-issued command verbs are allowed for a paired session.

## Overview

Every paired mobile session runs under exactly one **permission profile** that names the set of verbs the session is allowed to invoke. Profiles are selected by the PC user from the `ait applink` TUI before showing the QR code; the chosen profile is embedded in the `pair` response (see [protocol.md §Pairing flow](protocol.md#pairing-flow)) and pinned for the lifetime of the bearer.

This document defines:

- The three **default profiles** shipped with v1.
- The **verb gating table** mapping each `monitor`-derived command verb to a profile.
- How profiles are **stored and selected** on disk and in the TUI.
- How to **add a new profile** without changing the protocol.

Wire-protocol and pairing details live in [protocol.md](protocol.md). The canonical verb inventory (payload schemas, modal handshakes, push frames) is authored in [monitor_port_design.md](monitor_port_design.md); this document gives the **profile-band assignment** for that inventory — which verbs each profile tier may invoke — and is kept in sync with it.

## Default profiles

Three profiles ship with v1, ordered by escalating capability:

| Profile | Intended use | Snapshots | Key forwarding | Pane lifecycle |
|---------|--------------|-----------|----------------|----------------|
| `read_only` | "Just let me watch from the couch." Read-only mirror of `ait monitor`. | ✓ | ✗ | ✗ |
| `monitor_control` | "Talk to a running agent from my phone." Send keystrokes and switch panes; cannot kill anything. | ✓ | ✓ | ✗ |
| `full` | "Treat my phone as a full terminal companion." Includes destructive verbs. | ✓ | ✓ | ✓ |

Profile choice is per-pairing; revoking and re-pairing under a different profile is the standard escalation path. There is no in-session profile upgrade.

## Verb gating table

The v1 verb set is the canonical inventory in [monitor_port_design.md §Command verb → applink protocol mapping](monitor_port_design.md#command-verb--applink-protocol-mapping); this table assigns each verb to a profile tier and is kept in sync with it (the canonical table carries the full payload/modal detail). The command surface those verbs invoke lives in `.aitask-scripts/monitor/monitor_core.py` (the headless monitor core), with the UI-bound action handlers in `monitor_app.py`. Each verb maps to exactly one profile-tier; profiles include all verbs at their tier and below.

| Verb | Call site (`monitor_core.py` / `monitor_app.py` symbol) | `read_only` | `monitor_control` | `full` |
|------|----------------------------------------------------------|:-----------:|:-----------------:|:------:|
| `snapshot` (server push) | `monitor_core.py` (`capture_all`) | ✓ | ✓ | ✓ |
| `subscribe` / `request_keyframe` (data-plane control) | [content_transport.md §Refresh control](content_transport.md#refresh-control-focus-back-pressure) | ✓ | ✓ | ✓ |
| `pause` (data-plane self-throttle) | `applink/router.py` (`ConnState.paused`; halts `pusher.py` `PushScheduler` until `resume`) | ✓ | ✓ | ✓ |
| `task_detail` | `monitor_core.py` (`TaskInfoCache._resolve`) | ✓ | ✓ | ✓ |
| `send_enter` | `monitor_core.py` (`send_enter`) | ✗ | ✓ | ✓ |
| `send_keys` | `monitor_core.py` (`send_keys`) | ✗ | ✓ | ✓ |
| `forward_key` | `monitor_app.py` (`_forward_key_to_tmux`; map `_TEXTUAL_TO_TMUX` in `monitor_core.py`) | ✗ | ✓ | ✓ |
| `focus` (= `switch_to_pane`) | `monitor_core.py` (`switch_to_pane`) | ✗ | ✓ | ✓ |
| `cycle_compare_mode` | `monitor_core.py` (`cycle_compare_mode`; handler `monitor_app.py` `action_cycle_compare_mode`) | ✗ | ✓ | ✓ |
| `kill_pane` | `monitor_core.py` (`kill_agent_pane_smart`) | ✗ | ✗ | ✓ |
| `kill_window` | `monitor_core.py` (`kill_window`) | ✗ | ✗ | ✓ |
| `spawn_tui` | `monitor_core.py` (`spawn_tui`) | ✗ | ✗ | ✓ |
| `pick_next_sibling` | `monitor_app.py` (`action_pick_next_sibling`) | ✗ | ✗ | ✓ |
| `restart_task` | `monitor_app.py` (`action_restart_task`) | ✗ | ✗ | ✓ |

`snapshot` is a server-initiated `push` frame (not a client `req`) — gating still applies on the client → server side because a `read_only` session has no control verbs the server will execute, but the server pushes snapshots regardless of profile. The `subscribe` / `request_keyframe` data-plane control frames (refresh cadence, keyframe recovery) sit in the same read-only band: a `read_only` client steers its own snapshot stream without invoking any control action.

Notes:

- **`forward_key`** folds the Textual-to-tmux key map (`_TEXTUAL_TO_TMUX`, `monitor_core.py`) into a single verb resolved server-side: the mobile client sends an abstract key name (`up`, `escape`, `f5`, `ctrl+c`, …) and the server translates it to the tmux `send-keys` arguments. Mobile no longer sends literal escape sequences via `send_keys` for special keys. See [monitor_port_design.md](monitor_port_design.md#command-verb--applink-protocol-mapping).
- **Modal-prompted operations** carry a confirmation/selection handshake: `kill_pane`, `kill_window`, `restart_task`, and `pick_next_sibling` round-trip a confirm (or suggest-then-choose) step before executing. The gating tier applies to the underlying verb, not the handshake frames. The round-trip wire detail (pull-model `confirmed:true` re-send, `pick_next_sibling` suggest/choose) lives in [monitor_port_design.md §Modal-dialog handshakes](monitor_port_design.md#modal-dialog-handshakes); it is not duplicated here.
- **`pick_next_sibling` and `restart_task` are gated `full` but their mobile execution is deferred** (`NOT_IMPLEMENTED` past the v1 listener) per [monitor_port_design.md](monitor_port_design.md#command-verb--applink-protocol-mapping) — they are inventoried and gated for completeness; the launch-config flow has no mobile equivalent yet.
- **`rename_session` is desktop-only in v1** and is not gated here. It is inventoried in [monitor_port_design.md §Modal-dialog handshakes](monitor_port_design.md#modal-dialog-handshakes); add a row to this table only when it gains a mobile implementation.
- A `req` for a verb above the session's tier returns `err` with `code: "PERMISSION_DENIED"` and `detail: {"required_profile": "<name>"}`.

## Storage and selection

Profile definitions live under:

```
aitasks/metadata/applink_profiles/<name>.yaml
```

This directory ships with `read_only.yaml`, `monitor_control.yaml`, and `full.yaml` checked in. User-authored profiles can be added alongside (see [Adding a new profile](#adding-a-new-profile)).

Profile YAML shape:

```yaml
name: monitor_control
description: "Snapshots plus key forwarding and pane focus; no destructive verbs."
allowed_verbs:
  - snapshot
  - subscribe
  - request_keyframe
  - task_detail
  - send_enter
  - send_keys
  - forward_key
  - focus
  - cycle_compare_mode
```

**Selection at pairing time:** before showing the QR, the TUI presents the list of available profiles and the user picks one. The chosen profile name is:

1. Embedded in the in-memory pairing context (not in the QR payload — the QR carries only the token and TLS fingerprint).
2. Returned to the phone in the `pair` response's `payload.profile` field.
3. Persisted alongside the session bearer in the server's session table.

**Per-pairing device notes:** human-readable device names from the phone's `pair` payload are persisted under `aitasks/metadata/applink_sessions/` (gitignored — device-specific, not shared). This file holds active bearers and is rewritten on every pair/revoke.

## Adding a new profile

To ship a new profile (e.g., `dashboard_only` for a kiosk-style read view with limited snapshot fields):

### 1. Author the YAML

Create `aitasks/metadata/applink_profiles/<name>.yaml` with `name`, `description`, and `allowed_verbs`. The verb names must already exist in the canonical inventory (see [monitor_port_design.md](monitor_port_design.md)) — adding a new profile does not extend the verb namespace.

### 2. Validate verb names

Run the verb-validator (introduced alongside the protocol implementation, deferred from this docs-only PR):

```bash
./.aitask-scripts/aitask_applink_validate_profile.sh aitasks/metadata/applink_profiles/<name>.yaml
```

Validation checks: every entry in `allowed_verbs` matches a verb name registered in the applink dispatcher; no duplicates; `name` matches the filename stem.

### 3. Update profile-list docs

If the profile is intended to ship for all users (not a personal/local override), add a row to the "Default profiles" table above and an entry to the verb gating table.

### 4. Update the TUI selector (no code change required for read)

The TUI enumerates `aitasks/metadata/applink_profiles/*.yaml` at startup; no registration call is needed. For ordering, prefix the filename with a numeric sort key (e.g., `00_read_only.yaml`) — the `name` field inside the YAML remains canonical for protocol messages.

### 5. Test pairing

Pair a device under the new profile, exercise an allowed verb, and exercise a disallowed verb to confirm the `PERMISSION_DENIED` error fires.

## Out of scope (this document)

- The canonical verb inventory and payload schemas — authored by t822_3.
- The validator and TUI selector implementations — deferred to the t822_2 follow-up task that wires the WebSocket listener.
- Migration of in-flight bearers when a profile's `allowed_verbs` changes mid-session — bearers are immutable; users re-pair.
- Audit logging of denied verbs — deferred to a follow-up task once the server is wired.
