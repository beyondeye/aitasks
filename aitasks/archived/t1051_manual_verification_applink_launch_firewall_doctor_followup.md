---
priority: medium
effort: medium
depends: [1043]
issue_type: manual_verification
status: Done
labels: [verification, manual]
verifies: [1043]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-22 11:36
updated_at: 2026-06-24 18:44
completed_at: 2026-06-24 18:44
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1043

## Verification Checklist

- [x] With ufw active and port 8765 closed, launch `ait applink` — PASS 2026-06-24 18:42 manual: user confirmed visible default-port ait applink Pairing screen showed the firewall advisory with ufw active
- [x] Press 'f' — PASS 2026-06-24 18:42 manual: user confirmed pressing f opened FirewallFixModal and Open it for me invoked pkexec/polkit under Hyprland/Wayland
- [x] Approve the polkit dialog — PASS 2026-06-24 18:42 manual: user confirmed approving polkit added the LAN-scoped ufw rule and the physical phone completed pairing
- [x] Re-press 'f' (or relaunch) — PASS 2026-06-24 18:42 manual: user confirmed rerunning the firewall flow reported already open rather than failure
- [x] Headless: `ait monitor --headless-for-applink` prints the advisory block + the exact sudo command after the listener binds. — PASS 2026-06-24 18:44 auto: exact default-port headless run printed pairing block and ufw advisory with command sudo ufw allow from 10.0.0.0/24 to any port 8765 proto tcp after listener bind
- [x] Generic fallback: on a host with no managed firewall (or undetected), 'f' shows the backend-agnostic multi-backend commands with the real LAN CIDR. — PASS 2026-06-24 18:30 auto: firewall_doctor.generic_help listed ufw/firewalld/nftables/iptables commands for real CIDR 10.0.0.0/24 and port 8765
