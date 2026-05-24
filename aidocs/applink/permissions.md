# AppLink Permission Profiles

How the `ait applink` server decides which mobile-issued command verbs are allowed for a paired session.

## Overview

Every paired mobile session runs under exactly one **permission profile** that names the set of verbs the session is allowed to invoke. Profiles are selected by the PC user from the `ait applink` TUI before showing the QR code; the chosen profile is embedded in the `pair` response (see [protocol.md §Pairing flow](protocol.md#pairing-flow)) and pinned for the lifetime of the bearer.

This document defines:

- The three **default profiles** shipped with v1.
- The **verb gating table** mapping each `monitor`-derived command verb to a profile.
- How profiles are **stored and selected** on disk and in the TUI.
- How to **add a new profile** without changing the protocol.

Wire-protocol and pairing details live in [protocol.md](protocol.md). The canonical verb inventory (payload schemas, modal handshakes, push frames) is authored by sibling task t822_3 in [monitor_port_design.md](monitor_port_design.md); this document seeds the verb table with the v1 baseline.

## Default profiles

Three profiles ship with v1, ordered by escalating capability:

| Profile | Intended use | Snapshots | Key forwarding | Pane lifecycle |
|---------|--------------|-----------|----------------|----------------|
| `read_only` | "Just let me watch from the couch." Read-only mirror of `ait monitor`. | ✓ | ✗ | ✗ |
| `monitor_control` | "Talk to a running agent from my phone." Send keystrokes and switch panes; cannot kill anything. | ✓ | ✓ | ✗ |
| `full` | "Treat my phone as a full terminal companion." Includes destructive verbs. | ✓ | ✓ | ✓ |

Profile choice is per-pairing; revoking and re-pairing under a different profile is the standard escalation path. There is no in-session profile upgrade.

## Verb gating table

The v1 verb set is derived from the existing `ait monitor` command surface in `.aitask-scripts/monitor/tmux_monitor.py:585-720` and `.aitask-scripts/monitor/monitor_app.py:1489` (`cycle_compare_mode`). Each verb maps to exactly one profile-tier; profiles include all verbs at their tier and below.

| Verb | Existing call site | `read_only` | `monitor_control` | `full` |
|------|--------------------|:-----------:|:-----------------:|:------:|
| `snapshot` (server push) | `tmux_monitor.py:capture_all` | ✓ | ✓ | ✓ |
| `send_enter` | `tmux_monitor.py:585` | ✗ | ✓ | ✓ |
| `send_keys` | `tmux_monitor.py:589` | ✗ | ✓ | ✓ |
| `switch_to_pane` | `tmux_monitor.py:602` | ✗ | ✓ | ✓ |
| `cycle_compare_mode` | `monitor_app.py:1489` (calls `tmux_monitor.py:480`) | ✗ | ✓ | ✓ |
| `kill_pane` | `tmux_monitor.py:656` | ✗ | ✗ | ✓ |
| `kill_window` | `tmux_monitor.py:666` | ✗ | ✗ | ✓ |
| `spawn_tui` | `tmux_monitor.py:718` | ✗ | ✗ | ✓ |

`snapshot` is a server-initiated `push` frame (not a client `req`) — gating still applies on the client → server side because a `read_only` session has no verbs at all that the server will execute, but the server pushes snapshots regardless of profile.

Notes:

- **`forward_key`** is intentionally absent from the v1 table. The Textual-to-tmux key map at `.aitask-scripts/monitor/monitor_app.py:84-111` (`_TEXTUAL_TO_TMUX`) will be folded into a single `forward_key` verb when t822_3 produces the canonical inventory; until then, mobile clients send individual `send_keys` frames with literal escape sequences.
- **Modal-prompted operations** (kill-confirm dialogs, session rename) require a server → client `push` of type `modal_request` and a client `res`. The gating tier applies to the underlying destructive verb, not the modal handshake.
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
description: "Snapshots plus key forwarding; no destructive verbs."
allowed_verbs:
  - snapshot
  - send_enter
  - send_keys
  - switch_to_pane
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
