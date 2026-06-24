---
priority: medium
effort: medium
depends: [1043]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [1043]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-22 11:36
updated_at: 2026-06-24 18:28
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1043

## Verification Checklist

- [ ] With ufw active and port 8765 closed, launch `ait applink` — the firewall advisory appears on the pairing screen.
- [ ] Press 'f' — the FirewallFixModal opens; "Open it for me" runs pkexec and the polkit dialog appears under Hyprland/Wayland.
- [ ] Approve the polkit dialog — the LAN-scoped ufw rule is added and the phone then pairs (real blocked-port → pairing round trip).
- [ ] Re-press 'f' (or relaunch) — the doctor reports "already open" (idempotent no-op), not a failure.
- [ ] Headless: `ait monitor --headless-for-applink` prints the advisory block + the exact sudo command after the listener binds.
- [ ] Generic fallback: on a host with no managed firewall (or undetected), 'f' shows the backend-agnostic multi-backend commands with the real LAN CIDR.
