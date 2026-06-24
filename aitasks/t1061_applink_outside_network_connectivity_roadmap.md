---
priority: medium
effort: high
depends: [985]
xdeprepo: aitasks_mobile
issue_type: feature
status: Ready
labels: [applink]
created_at: 2026-06-24 14:38
updated_at: 2026-06-24 14:38
---

Umbrella / roadmap task: enable the `ait applink` mobile companion to connect to
the workspace server **from outside the local Wi-Fi network**. This is a
cross-repo effort (server in this repo, client in `aitasks_mobile`) and is meant
to be **decomposed into children later**, not implemented as one unit.

## Why it's LAN-only today (root cause)

The connection is a **direct inbound socket to a private IP**, end to end:

- Server (`.aitask-scripts/applink/server.py`) binds `0.0.0.0`, but pairing
  (`.aitask-scripts/applink/pairing.py` `detect_lan_ip()`) encodes **only the
  detected private LAN IP** into the QR:
  `applink://<lan-ip>:<port>/pair?t=…&fp=…`.
- Mobile (`aitasks_mobile` `KtorMonitorStreamClient.kt`) dials `wss://<host>:<port>`
  straight to that stored IP — no DNS, no relay, no failover, single attempt;
  host/port frozen in `ConnectionDBO`.
- Trust is a self-signed cert + SHA-256 **fingerprint pinned in the QR**
  (`tls.py` / mobile `HttpClientFactory.kt`); CA chain and hostname verification
  are deliberately bypassed.

So the phone must TCP-reach a private LAN address in real time → same subnet
only. No NAT traversal, no public endpoint, no relay.

## Staged roadmap (design already anticipates this)

See `aidocs/applink/protocol.md §Roadmap to cross-network` and
`aidocs/applink/wish_ssh_evaluation.md`. Four transport phases reuse the same
envelope / pairing / verbs / permissions; only connectivity changes:

- **Phase 2 — User-owned tunnel (cheapest, unblocked now).** Phone reaches the PC
  via a tunnel the user runs; QR carries the tunnel endpoint instead of a LAN IP.
  - *A1 Mesh VPN (Tailscale / ZeroTier / WireGuard):* overlay gives the PC a
    stable private IP reachable anywhere — **existing LAN code basically "just
    works"**; trust unchanged. Lowest code change of any option.
  - *A2 Reverse tunnel (cloudflared / ngrok / `ssh -L`):* public hostname fronts
    the PC, but the tunnel often terminates TLS → **breaks fingerprint pinning**;
    needs a "trust the tunnel's CA cert" path on mobile.
  - Work: a how-to doc + small pairing changes (accept user-supplied/non-RFC1918
    host or FQDN; relax pin assumption for A2). No protocol/envelope change.

- **Alternative B — Hosted / always-on box.** Run the applink server on a public
  cloud VM; phone connects directly; PC can be off. Solves cross-network "for
  free" on transport but requires public-exposure hardening (CA cert + FQDN +
  rotation, rate-limiting/lockout, shorter TTLs, audit logging — i.e. t985 and
  beyond) and shifts the workspace onto a server. Pairs with `wish`/SSH for
  terminal clients (see `wish_ssh_evaluation.md`).

- **Phase 3 — First-party relay broker (turnkey path).** PC dials **out** to a
  (self-hostable) broker; phone connects to the broker; broker stitches sessions.
  New QR scheme `applink://<broker>/r/<session-id>`, outbound-socket model, and
  **end-to-end key exchange** so the broker never sees frame contents (replaces
  direct fingerprint pinning — its own crypto spec + security review). Largest
  investment; works anywhere incl. CGNAT; ~50–150 ms relay latency. **The
  protocol doc explicitly says to create this design task after Phase 1 lands —
  which it now has.**

- **Phase 4 — P2P / WebRTC (optional, long-term).** Relay used only for
  signaling; frames flow P2P over WebRTC data channels (ICE/STUN/TURN). Lowest
  latency when hole-punching succeeds, but still needs the Phase-3 relay for
  signaling, falls back to TURN under symmetric/CGNAT, and burns battery on ICE
  keepalives.

## Concrete missing pieces

**Server (this repo):**
- No public-endpoint advertisement (QR carries private IP only).
- No relay / outbound-dial model (Phase 3/4 unbuilt).
- Self-signed cert unsuitable for public (no CA cert / rotation) — `tls.py`.
- No rate-limiting / lockout / audit logging for public exposure.
- Firewall doctor scopes LAN CIDR only.

**Mobile (`aitasks_mobile`):**
- Single frozen `host:port`; no relay field / multi-address failover
  (`ConnectionDBO`, `Connection.kt`, `ConnectionMediator.kt`).
- No network-change detection or reconnect backoff (`MonitorSessionMediator.kt`).
- Cert fingerprint immutable; relay needs a CA-trust / relay-pin path
  (`HttpClientFactory.kt`, `TlsFingerprintPinner.kt`).
- QR parser understands only the LAN-IP scheme (`QrUrl.kt`).

## Dependencies & sequencing

- **Hard gate: t985 (AppLink security review & hardening, Ready/high)** blocks ANY
  public exposure (Alternatives B, Phase 3, Phase 4). Wired as `depends`.
- **Robustness, parallel & non-blocking:** t1007 (data-plane limits) + data-plane
  tasks t1045 / t1054 / t1055 / t1056 / t1057 / t1058 make remote links *usable*
  but aren't strict blockers.
- Phase-1 foundation (DONE): t822 tree (protocol t822_1, listener t822_7,
  monitor_core t822_6, data plane t822_8/9), t950/p950 (wish + hosted-deployment
  evaluation), t953 (dedicated tmux socket for hosted topology).

## Suggested decomposition (later)

1. Phase-2 tunnel how-to + pairing change to accept user-supplied host/FQDN
   (lead with Tailscale/mesh; cross-repo: mobile pin relaxation for A2).
2. Phase-3 relay-broker **design task** (outbound dial, QR scheme, E2E key
   exchange) — design-only, gated on t985.
3. Mobile reconnection / network-change + multi-address/relay-URL support
   (`aitasks_mobile`) — currently untracked there.
4. (Optional) Hosted-box deployment guide (Alternative B) and Phase-4 WebRTC.

## References

- `aidocs/applink/protocol.md` (§Roadmap to cross-network, §Pairing flow)
- `aidocs/applink/wish_ssh_evaluation.md` (hosted-deployment alternative, public-exposure hardening)
- `aidocs/applink/permissions.md`
- `xdeprepo: aitasks_mobile` — paired decomposition spans both repos; mirror a
  matching task on the mobile side when children are assigned.
