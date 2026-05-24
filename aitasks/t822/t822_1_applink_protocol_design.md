---
priority: high
effort: medium
depends: []
issue_type: documentation
status: Ready
labels: [ait_bridge]
created_at: 2026-05-24 09:31
updated_at: 2026-05-24 09:31
---

Design the wire protocol, auth/pairing model, and permission profiles for the new `ait applink` TUI that bridges a local `ait ide` tmux session to a mobile companion app (developed in sibling repo `../aitasks_mobile`, Kotlin Multiplatform). This child produces design docs only — no runtime code.

## Context

Parent task **t822** introduces `ait applink`, a new framework TUI whose job is to securely expose `ait monitor`-style activity to a phone. This task locks down the *contract* before any code is written, because child 822_2 (TUI + QR pairing) and child 822_3 (monitor port design) both depend on these decisions.

Pre-plan decisions already locked (do NOT re-prompt):
- TUI name: `applink` (Python module `.aitask-scripts/applink/`, command `ait applink`)
- Coordination with `../aitasks_mobile` is **document-only** in this PR — produce a versioned contract; the user mirrors a matching task into the mobile repo afterward.
- Transport choice is **this task's responsibility** — survey LAN WebSocket vs. relay server vs. WebRTC/holepunch, recommend one as the default, document trade-offs.

## Key Files to Create

- `aidocs/applink/protocol.md` — wire protocol design:
  - Transport choice + rationale (recommend LAN WebSocket as default; document relay and WebRTC alternatives)
  - Message envelope (JSON over WS): request/response frames, server-push frames, error frames, versioning header
  - Session lifecycle: QR pairing → token exchange → per-session bearer → revoke
  - Connection state machine (Discovering → Pairing → Connected → Suspended → Disconnected)
- `aidocs/applink/permissions.md` — permission profile model:
  - Default profiles: `read_only`, `monitor_control`, `full`
  - Per-verb gating table (which profile permits which `ait monitor` command verb from t822_3's verb list)
  - How profiles are stored (under `aitasks/metadata/applink_profiles/` or similar) and selected at pairing time
  - How to add a new profile (extension checklist, similar style to `aidocs/gitremoteproviderintegration.md`)

## Key Files to Reference (read-only)

- `aidocs/gitremoteproviderintegration.md` — canonical "architecture + extension checklist + tables" style template to mimic
- `aidocs/brainstorming/` — example of multi-doc subdirectory layout for a feature
- `aidocs/tui_conventions.md` — top-of-doc convention reference
- `.aitask-scripts/monitor/tmux_monitor.py:585-675` — the 7 command verbs this protocol will eventually carry (`send_keys`, `send_enter`, `switch_to_pane`, `kill_pane`, `kill_window`, `spawn_tui`, plus modal-prompted ops)
- `.aitask-scripts/monitor/monitor_app.py:84-111` — Textual → tmux special-key mapping (input vocabulary)

## Implementation Plan

1. Survey transport options:
   - LAN WebSocket (PC = server, QR encodes `ws://<lan-ip>:<port>?token=<pairing>`)
   - Relay server (cloud broker, QR encodes session ID)
   - WebRTC with signaling (P2P, NAT traversal)
   Document one paragraph each + a decision matrix table (latency / firewall-resilience / infra-cost / battery). Pick LAN WebSocket as default (rationale: zero infra, local-first, lowest battery).
2. Define the envelope (JSON):
   ```json
   {"v":1, "id":"<req-id>", "kind":"req|res|push|err", "verb":"<name>", "payload":{...}}
   ```
3. Define pairing flow:
   - PC generates 256-bit token T
   - QR encodes `applink://<lan-ip>:<port>/pair?t=<base64url(T)>&fp=<server-tls-fingerprint>`
   - Mobile POSTs `{"verb":"pair","payload":{"token":T,"device":{...}}}` → server returns session bearer + chosen permission profile
   - Subsequent frames carry `"auth":"<bearer>"`
4. Define the 3 default permission profiles and their verb tables. Map every verb from `.aitask-scripts/monitor/tmux_monitor.py:585-675` to read_only / monitor_control / full.
5. Add a one-line pointer in root `CLAUDE.md` under a new short "## Mobile Companion" subsection pointing to `aidocs/applink/`.
6. Style match: use `##` section headers, embed tables, keep code blocks under 20 lines, no ToC unless > 8 major sections.

## Verification Steps

- `aidocs/applink/protocol.md` and `aidocs/applink/permissions.md` exist and render cleanly in any markdown viewer (no broken refs, no orphan headers)
- `grep -R "applink" CLAUDE.md` returns the new pointer
- Sibling task t822_2 (TUI + QR) can read this doc and have a complete spec for what the QR encodes and what `pair` verb returns — no further questions
- Sibling task t822_3 (monitor port design) can read `permissions.md` and produce a verb-by-verb mapping table — no further questions

No runtime tests (doc-only task).

## Out of Scope

- Implementation of the protocol (deferred to a future task spawned after t822_2 lands the TUI skeleton)
- Mobile-side bindings (handled in `../aitasks_mobile` by a separate task the user will create manually)
- Cryptographic primitive selection details (mention TLS + bearer token at a high level; defer detailed crypto review to a follow-up)
