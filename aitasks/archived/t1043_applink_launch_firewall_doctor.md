---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [applink]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-21 17:21
updated_at: 2026-06-22 11:36
completed_at: 2026-06-22 11:36
---

On AppLink server launch, detect when the host firewall is blocking the
bound listen port and offer to open it for the user — so users never have
to craft firewall commands by hand.

## Motivation

During live mobile pairing tests, the phone could not connect: the server
bound `0.0.0.0:8765` correctly, but the host's `ufw` firewall silently
dropped inbound TCP on that port (ICMP passed, TCP SYN timed out). The
mobile app surfaced only a generic "NETWORK, try again". The user had to
manually run `sudo ufw allow from <lan>/24 to any port 8765 proto tcp`.
This is a poor first-run experience and hard to diagnose.

## Chosen approach (decided with user): launch-time firewall doctor

On startup (and/or on the pairing screen), the server should:

1. **Detect the active firewall backend** (unprivileged): `ufw`,
   `firewalld`, or `nftables` via `systemctl is-active` (the repo host uses
   ufw-over-iptables-nft). This is timeout-bound and failure-silent, so a
   non-systemd box / container / WSL degrades to "no backend" rather than
   hanging. *(This replaces the originally-proposed self-connect probe — see
   "Why not a self-connect probe" below.)*
2. **Surface a clear, conditional advisory** in the TUI when a backend is
   active ("Firewall (ufw) active — if your phone can't connect, press 'f'
   to open port N for <lan>/<prefix>."). The advisory never claims the port
   is *blocked* (the host can't cheaply prove that without root), so it
   produces no false positives.
3. **Offer to open it** with explicit user consent (the `f` keypress + a
   modal) — scoped to the LAN subnet (the real network/prefix from `ip`,
   fallback `/24`), never `0.0.0.0/0`.
4. On consent, **run the privileged command** via `pkexec` (preferred for a
   GUI/agent context; its polkit dialog doesn't fight the TUI). The server
   runs unprivileged, so escalation is requested only at this step, only for
   this one rule, and reported back (success/failure). **Scope (decided with
   user):** auto-run for `ufw`/`firewalld` (natively idempotent);
   `nftables`/`iptables` are **show-command-only** (no clean idempotent
   one-liner). A **"show me the command, I'll run it myself"** affordance is
   available for *every* backend (the command is always visible in the
   modal), and an always-reachable generic show-command help covers undetected
   / raw setups.

## Why not a self-connect probe

The original step 1 proposed probing reachability by self-connecting to
`<lan-ip>:<port>` from the host. **This cannot detect a firewall drop and was
dropped (confirmed with the user).** On Linux a connection from the host to
*its own* LAN IP is routed through the loopback device (`lo`), which
ufw/iptables/nftables accept unconditionally via the standard `-i lo -j ACCEPT`
before-rule. So the self-connect *succeeds* even when the firewall blocks
external inbound — it would report "reachable ✓" in exactly the scenario this
doctor exists to catch. **Do not reintroduce it.** The honest, achievable signal
is active-backend detection (above); definitive proof of reachability can only
come from the phone (out of scope for a launch-time host-side check).

## Requirements / acceptance

- No manual command-crafting by the user; at most a single yes/no consent.
- Backend-agnostic: ufw and firewalld are auto-opened; nftables/iptables and
  any undetected/raw setup are covered by the always-reachable generic
  show-command help ("here is the exact command") — so every backend has a UI
  route to the fix.
- Idempotent: re-running when the rule already exists is a no-op (reported as
  "already open", not a failure — backend-aware result classification).
- LAN-scoped rule, never world-open.
- Privilege escalation only on explicit consent; never silent.
- Clear failure path if escalation is denied or unavailable (fall back to
  showing the exact command).
- No false positives: the advisory is conditional and never claims the port is
  blocked; auto-detection is honestly scoped to cheaply-detectable managed
  backends (it does not block on undetected raw setups — the generic help is
  the fallback there).

## Related

- Mobile-side root-cause fix (separate repo `aitasks_mobile`, task t18):
  the app was dialing `ws://` instead of `wss://`, which masked the
  firewall symptom behind a generic transport error. That is fixed; this
  task addresses the server/host-side firewall UX.
- Server code: `.aitask-scripts/applink/` (`applink_app.py`, `server.py`,
  `pairing.py` `detect_lan_ip()`, `tls.py`).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-22T08:24:04Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-22T08:24:05Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-22T08:35:10Z status=pass attempt=1 type=human
