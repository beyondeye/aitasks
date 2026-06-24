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
updated_at: 2026-06-24 18:30
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1043

## Verification Checklist

- [defer] With ufw active and port 8765 closed, launch `ait applink` — DEFER 2026-06-24 18:30 auto: blocked pending live TUI inspection; ufw is active, but port 8765 is already bound by an existing listener so a fresh default-port applink launch could not be verified safely
- [defer] Press 'f' — DEFER 2026-06-24 18:30 auto: requires interactive Hyprland/Wayland polkit observation after pressing f in the live TUI; not verifiable from this non-GUI run
- [defer] Approve the polkit dialog — DEFER 2026-06-24 18:30 auto: requires explicit polkit approval and a real phone pairing round trip after opening the LAN-scoped ufw rule
- [defer] Re-press 'f' (or relaunch) — DEFER 2026-06-24 18:30 auto: depends on completing the live firewall-open flow first, then rerunning f/relaunch to observe the already-open no-op
- [defer] Headless: `ait monitor --headless-for-applink` prints the advisory block + the exact sudo command after the listener binds. — DEFER 2026-06-24 18:30 auto: headless advisory path passed on port 18765 with ufw active and command sudo ufw allow from 10.0.0.0/24 to any port 18765 proto tcp; exact default-port 8765 run is blocked because 8765 is already bound by an existing listener
- [x] Generic fallback: on a host with no managed firewall (or undetected), 'f' shows the backend-agnostic multi-backend commands with the real LAN CIDR. — PASS 2026-06-24 18:30 auto: firewall_doctor.generic_help listed ufw/firewalld/nftables/iptables commands for real CIDR 10.0.0.0/24 and port 8765
