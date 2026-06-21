---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [applink]
created_at: 2026-06-21 17:21
updated_at: 2026-06-21 17:21
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

1. **Probe reachability** of the bound listen port on the routable LAN IP
   (the same IP embedded in the pairing QR via `detect_lan_ip()`) — e.g.
   attempt a self-connect to `<lan-ip>:<port>` from the host, distinct
   from the loopback bind, to detect a firewall drop.
2. **If blocked, detect the firewall backend** present and active:
   `ufw`, `firewalld`, or raw `nftables`/`iptables` (the repo host uses
   ufw-over-iptables-nft).
3. **Surface a clear, actionable message** in the TUI explaining the port
   is blocked, and **offer to open it** with explicit user consent
   (a confirmation keypress / prompt) — scoped to the LAN subnet, not
   `0.0.0.0/0`.
4. On consent, **run the appropriate privileged command** via `pkexec`
   (preferred for a GUI/agent context) or `sudo`, e.g.
   `ufw allow from <lan>/24 to any port <port> proto tcp`. The server runs
   unprivileged, so privilege escalation must be requested only at this
   step, only for this one rule, and reported back (success/failure).

## Requirements / acceptance

- No manual command-crafting by the user; at most a single yes/no consent.
- Backend-agnostic: ufw, firewalld, and nftables/iptables all handled (or
  a clean "couldn't auto-detect, here is the exact command" fallback).
- Idempotent: re-running when the rule already exists is a no-op.
- LAN-scoped rule, never world-open.
- Privilege escalation only on explicit consent; never silent.
- Clear failure path if escalation is denied or unavailable (fall back to
  showing the exact command).
- Probe must not produce false positives when the port is genuinely open.

## Related

- Mobile-side root-cause fix (separate repo `aitasks_mobile`, task t18):
  the app was dialing `ws://` instead of `wss://`, which masked the
  firewall symptom behind a generic transport error. That is fixed; this
  task addresses the server/host-side firewall UX.
- Server code: `.aitask-scripts/applink/` (`applink_app.py`, `server.py`,
  `pairing.py` `detect_lan_ip()`, `tls.py`).
