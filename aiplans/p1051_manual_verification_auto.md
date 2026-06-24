---
task_id: 1051
task_file: aitasks/t1051_manual_verification_applink_launch_firewall_doctor_followup.md
type: manual_verification_auto
created_at: 2026-06-24 18:30
---

# t1051 Manual Verification Auto-Execution Plan

## Pre-built Auto-Execution Plan

1. [defer if no live TUI/phone] With ufw active and port 8765 closed, launch `ait applink` and confirm the firewall advisory appears on the pairing screen.
   - Strategy: live TUI inspection.
   - Action: confirm `ufw` is active via `systemctl is-active ufw`; start `./ait applink` in a real terminal or tmux-backed TUI; inspect the pairing screen for the firewall advisory.
   - Pass criterion: the pairing screen shows the active-firewall advisory for port 8765 and the computed LAN CIDR.
   - Fail/defer fallback: fail if the advisory is absent with ufw active; defer if no live TUI can be inspected.

2. [defer if no polkit session] Press `f` and confirm `FirewallFixModal` opens; "Open it for me" invokes `pkexec` and the polkit dialog appears under Hyprland/Wayland.
   - Strategy: live TUI plus desktop privilege dialog.
   - Action: press `f` in `ait applink`, choose "Open it for me", and observe the polkit dialog.
   - Pass criterion: the modal opens, shows the LAN-scoped command, and `pkexec` triggers polkit without blocking the TUI.
   - Fail/defer fallback: fail if the modal or privilege path is broken; defer if no interactive desktop/polkit session is available.

3. [defer if no phone/polkit approval] Approve polkit, confirm the LAN-scoped ufw rule is added, and pair a real phone.
   - Strategy: live privileged system change plus real mobile pairing.
   - Action: approve the polkit dialog, then pair the phone using the QR/URI shown by `ait applink`.
   - Pass criterion: the rule opened is scoped to the computed LAN CIDR and port 8765, and a real phone completes the pairing round trip.
   - Fail/defer fallback: fail if approval does not add the rule or pairing still fails; defer if no phone or user approval is available.

4. [defer if no live fix run] Re-press `f` or relaunch and confirm the doctor reports "already open".
   - Strategy: live idempotency check.
   - Action: rerun the firewall-fix path after item 3 has opened the rule.
   - Pass criterion: the result is a successful "already open" no-op, not an error.
   - Fail/defer fallback: fail if the second run is reported as a command failure; defer if item 3 was not completed.

5. [pass/fail by CLI] Run `ait monitor --headless-for-applink` and confirm the advisory block plus exact sudo command prints after listener bind.
   - Strategy: CLI invocation with captured stdout.
   - Action: launch headless mode on a temporary free port if 8765 is busy; capture output until the pairing block and firewall advisory appear; terminate the process.
   - Pass criterion: output contains the headless pairing block and a firewall advisory with an exact LAN-scoped sudo command.
   - Fail/defer fallback: fail if the process starts but never prints the advisory; defer if runtime dependencies are missing.

6. [pass/fail by module harness] Exercise the no-managed-firewall path and confirm backend-agnostic commands use the real LAN CIDR.
   - Strategy: Python harness against `firewall_doctor` and `FirewallFixModal` command text without changing the real firewall.
   - Action: compute the current LAN CIDR, create a `FirewallStatus(backend=None, cidr=<cidr>, port=8765)`, and inspect `generic_help`.
   - Pass criterion: the fallback text lists ufw, firewalld, nftables, and iptables commands using the computed CIDR and port 8765.
   - Fail/defer fallback: fail if any backend command or real CIDR is missing.

## Cleanup

- Stop any `ait applink` or headless applink process started for verification.
- Remove temporary logs created under `/tmp`.
- Do not remove or alter unrelated pre-existing firewall rules.
- If a temporary rule is added solely for verification and the user wants it reverted, remove only that exact LAN-scoped port 8765 rule after the pairing/idempotency checks.

## Execution Log

### Item 1
- Item text: With ufw active and port 8765 closed, launch `ait applink` and confirm the firewall advisory appears on the pairing screen.
- Approach: live TUI inspection.
- Action run: `systemctl is-active ufw firewalld nftables`; attempted exact default-port headless launch separately for port availability.
- Output trimmed: `ufw` was active; `firewalld` and `nftables` were inactive. Default port 8765 was already bound, so a fresh default-port listener could not be launched safely.
- Verdict: defer.

### Item 2
- Item text: Press `f`; confirm `FirewallFixModal` opens and "Open it for me" runs `pkexec` under Hyprland/Wayland.
- Approach: live desktop/polkit inspection.
- Action run: not executed from this non-GUI automation session.
- Output trimmed: `pkexec` is installed, but observing the Hyprland/Wayland polkit dialog requires an interactive desktop session.
- Verdict: defer.

### Item 3
- Item text: Approve polkit; confirm the LAN-scoped ufw rule is added and a real phone pairs.
- Approach: live privileged system change plus real mobile pairing.
- Action run: not executed automatically; this requires explicit user approval in polkit and a phone on the LAN.
- Output trimmed: no privileged firewall mutation was attempted.
- Verdict: defer.

### Item 4
- Item text: Re-press `f` or relaunch and confirm the doctor reports "already open".
- Approach: live idempotency check.
- Action run: not executed because item 3 was not completed.
- Output trimmed: unit coverage in `tests/test_applink_firewall.sh` confirms the idempotent result parser maps existing ufw/firewalld rules to success, but the live no-op path still depends on the real firewall-open flow.
- Verdict: defer.

### Item 5
- Item text: Headless `ait monitor --headless-for-applink` prints the advisory block and exact sudo command after the listener binds.
- Approach: CLI invocation with captured stdout.
- Action run: `timeout 14s bash ./.aitask-scripts/aitask_monitor.sh --headless-for-applink --port 18765 --no-qr`; then `timeout 14s bash ./.aitask-scripts/aitask_monitor.sh --headless-for-applink --no-qr`.
- Output trimmed: temporary-port run printed the pairing block and firewall advisory: `sudo ufw allow from 10.0.0.0/24 to any port 18765 proto tcp`. Exact default-port run failed with `address already in use` for `0.0.0.0:8765`.
- Verdict: defer, because the checklist explicitly requires default port 8765.

### Item 6
- Item text: Generic fallback shows backend-agnostic multi-backend commands with the real LAN CIDR.
- Approach: Python harness against `firewall_doctor.generic_help`.
- Action run: computed `firewall_doctor.host_lan_cidr("10.0.0.1")`, then rendered `generic_help(8765, cidr)`.
- Output trimmed: CIDR was `10.0.0.0/24`; fallback text listed ufw, firewalld, nftables, and iptables commands for port 8765.
- Verdict: pass.

### Supporting Checks
- `bash tests/test_applink_firewall.sh`: passed all firewall doctor unit checks.
- `systemctl is-active ufw firewalld nftables`: `active`, `inactive`, `inactive`.
- `ss -ltnp 'sport = :8765'`: confirmed a listener is already bound on `0.0.0.0:8765`; process details were not visible without elevated inspection.
