---
Task: t822_1_applink_protocol_design.md
Parent Task: aitasks/t822_new_ait_bridge_tui.md
Sibling Tasks: aitasks/t822/t822_2_applink_tui_qr.md, aitasks/t822/t822_3_monitor_port_design.md
Archived Sibling Plans: aiplans/archived/p822/p822_*_*.md
Worktree: (current branch — profile fast)
Branch: (current branch — profile fast)
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-24 09:46
---

# Plan: t822_1 — applink protocol & permissions design (aidocs only)

## Context

First of three children under parent t822 introducing `ait applink`. This child unblocks the other two by locking the wire-protocol contract and the permission-profile vocabulary. Docs-only PR — no Python, no shell, no website changes.

## Verification status

Re-verified 2026-05-24 under profile `fast` (`plan_preference_child: verify`, `DECISION:VERIFY`). All load-bearing assumptions confirmed sound; one minor drift noted below.

## Approach

Author two markdown files under a new `aidocs/applink/` subdirectory (matches the precedent set by `aidocs/agentcrew/` and `aidocs/brainstorming/`), plus a one-line pointer in root `CLAUDE.md`. Style match: `aidocs/gitremoteproviderintegration.md` (overview → extension checklist → tables).

## Files to create

1. **`aidocs/applink/protocol.md`** — sections:
   - `## Overview` — what applink does, link to parent task t822
   - `## Transport choice` — decision matrix table comparing LAN WebSocket / relay server / WebRTC; recommend LAN WebSocket as v1 default. Rationale: zero infra, local-first, lowest battery; document fallback story for cross-network use.
   - `## Message envelope` — JSON shape `{"v":1, "id":"<req-id>", "kind":"req|res|push|err", "verb":"<name>", "payload":{...}, "auth":"<bearer-or-null>"}`; version handshake rules; error frame schema.
   - `## Pairing flow` — sequence diagram in prose:
     1. PC generates 256-bit token T via `secrets.token_urlsafe(32)`
     2. PC computes its TLS-cert fingerprint `fp` (use self-signed cert generated at first run if none configured; document deferral)
     3. QR encodes `applink://<lan-ip>:<port>/pair?t=<base64url(T)>&fp=<fp>`
     4. Mobile sends `{"verb":"pair","payload":{"token":T,"device":{"name":"...","platform":"..."}}}` over TLS WS
     5. Server validates T, returns `{"bearer":"<session-token>","profile":"<profile-name>","expires_at":...}`
     6. Subsequent frames carry `"auth":"<bearer>"`
   - `## Connection state machine` — Discovering → Pairing → Connected → Suspended → Disconnected (with allowed transitions table)
   - `## Versioning` — `v` field semantics, what triggers a version bump
2. **`aidocs/applink/permissions.md`** — sections:
   - `## Overview` — purpose, link to `protocol.md`
   - `## Default profiles` — three named profiles:
     - `read_only` — snapshots only, no command verbs
     - `monitor_control` — snapshots + `send_keys`, `send_enter`, `switch_to_pane`, `cycle_compare_mode`
     - `full` — all of the above plus `kill_pane`, `kill_window`, `spawn_tui`
   - `## Verb gating table` — rows = the 7 verbs identified in the t822 Explore. **Verified source-of-truth range: `.aitask-scripts/monitor/tmux_monitor.py:585-720` (the original plan cited 585-675, but `spawn_tui` is actually at line 718). `cycle_compare_mode` lives elsewhere — grep before embedding.** Columns = the 3 profiles; cells = ✓/✗. (t822_3 will produce the canonical version with snapshot/modal verbs added; this doc seeds it.)
   - `## Storage and selection` — store profiles under `aitasks/metadata/applink_profiles/<name>.yaml` (gitignored if they hold device-specific data; document the decision); at pairing time the user picks a profile from the TUI before showing the QR.
   - `## Adding a new profile` — extension checklist (style match `aidocs/gitremoteproviderintegration.md` "Extension Checklist").
3. **`CLAUDE.md`** — add a short section `## Mobile Companion` with one paragraph and a pointer to `aidocs/applink/`. Place it near other "Project-Specific Notes" or as its own top-level section near the end.

## Reference files (read-only)

- `aidocs/gitremoteproviderintegration.md` — style template
- `aidocs/brainstorming/` — multi-doc subdir example
- `aidocs/tui_conventions.md` — top-of-doc tone reference
- `.aitask-scripts/monitor/tmux_monitor.py:585-720` — verb list source of truth (corrected range)
- `.aitask-scripts/monitor/monitor_app.py:84-111` — Textual → tmux key map (informs `forward_key` verb design)

## Verification

- `test -f aidocs/applink/protocol.md && test -f aidocs/applink/permissions.md`
- `grep -q "Mobile Companion" CLAUDE.md`
- Spot-read each doc to confirm it follows the gitremoteproviderintegration style (headers, tables, no orphans)
- No code touched: `git diff --stat` should show only `aidocs/applink/` files and `CLAUDE.md`
- Sibling task t822_2 author can read `protocol.md` §Pairing flow and implement `pairing.py` from it without further questions
- Sibling task t822_3 author can read `permissions.md` and build the full verb mapping table without further questions

## Out of scope

- Implementation of the protocol (will be a follow-up task created after t822_2)
- Mobile-side bindings (lives in `../aitasks_mobile`, user mirrors task manually)
- Cryptographic primitive details (mention TLS + bearer at high level; cite "Detailed crypto review deferred")

## Final Implementation Notes

- **Actual work done:** Created `aidocs/applink/protocol.md` (Overview, Transport choice with decision matrix, Message envelope with kind/error tables, Pairing flow as 8-step sequence, Connection state machine with transitions table, Versioning rules, Out of scope) and `aidocs/applink/permissions.md` (Overview, three default profiles with capability table, full verb gating table seeded from `tmux_monitor.py:585-720` + `monitor_app.py:1489`, Storage and selection with YAML schema, 5-step extension checklist for new profiles). Added an 11-line `## Mobile Companion` section to `CLAUDE.md` pointing at the new subdir.
- **Deviations from plan:** None. The plan's "verified verb source-of-truth range" note (585-720 plus the `cycle_compare_mode` lookup) was applied directly when authoring the verb gating table — `cycle_compare_mode` ended up cited at `monitor_app.py:1489` (the action handler) which calls `tmux_monitor.py:480` (the underlying method).
- **Issues encountered:** None during implementation. Verify mode caught the verb-range drift (plan cited 585-675, actual is 585-720) before any docs were written.
- **Key decisions:**
  - Cited `cycle_compare_mode` via its `monitor_app.py:1489` action handler rather than the underlying `tmux_monitor.py:480` method, because the action handler is what mobile-issued verbs will eventually replace.
  - Left `forward_key` out of the v1 verb gating table with an explicit forward-pointer note — t822_3 will fold the `_TEXTUAL_TO_TMUX` map into the canonical verb when it produces the full inventory.
  - Used `wss://` (TLS over WebSocket) and TLS-cert-fingerprint pinning in the QR as the v1 security baseline; full crypto review is explicitly deferred (matches plan's "Out of scope" line).
- **Upstream defects identified:** None. Diagnosis did not surface any pre-existing bugs in `monitor/` or elsewhere — the cited code paths are all healthy.
- **Notes for sibling tasks:**
  - **t822_2 (TUI + QR + pairing token):** `protocol.md §Pairing flow` is the canonical source for the QR URI shape (`applink://<lan-ip>:<port>/pair?t=<base64url(T)>&fp=<fp>`) and the `pair` request/response payloads. Implement `pairing.py` directly against that section; no further questions needed.
  - **t822_3 (monitor port design):** The verb gating table in `permissions.md` is **seed only**. Replace it with the canonical inventory once you've audited `monitor_app.py:1262-1799` and `tmux_monitor.py:585-720` for any verbs missed in the t822 Explore. Also: fold the `_TEXTUAL_TO_TMUX` map into a single `forward_key` verb — the current table reflects that decision is yours to make, and `permissions.md` already explains it under the "Notes" subsection.
  - **Both siblings:** `aidocs/applink/` is now an established subdirectory; add `monitor_port_design.md` there (t822_3) and the new `pairing.py` reference docs there (t822_2 if needed). The cross-reference links between protocol.md, permissions.md, and monitor_port_design.md already exist as forward refs — no extra wiring needed when t822_3 lands.
