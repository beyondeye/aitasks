---
priority: medium
effort: high
depends: [985]
xdeprepo: aitasks_mobile
issue_type: feature
status: Implementing
labels: [applink, applink_connectivity]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-24 14:38
updated_at: 2026-07-02 14:54
boardidx: 190
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

- **Hard gate t985 (AppLink security review & hardening) is DONE / archived** —
  so the public-exposure phases (Alternative B, Phase 3, Phase 4) are now
  **unblocked** on their security prerequisite. The `depends: [985]` edge is
  satisfied. (Its three deferred residuals live on as the Tier-2 follow-ups
  below: t1066 cert rotation, t1067 bearer rotation, t1068 request rate-limit.)
- Phase-1 foundation (DONE): t822 tree (protocol t822_1, listener t822_7,
  monitor_core t822_6, data plane t822_8/9), t950/p950 (wish + hosted-deployment
  evaluation), t953 (dedicated tmux socket for hosted topology).

### Suggested implementation order relative to this roadmap

None of the tasks below are *strict* blockers (the only hard gate, t985, is
done), but remote/cellular links are bandwidth- and correctness-sensitive, so
the data-plane work is what makes a remote link worth having. Recommended order
(established in t1072):

- **Tier 0 — do before decomposing/starting t1061 (correct + usable remote
  link), cheap-first:**
  1. **t1054** (HIGH, bug) — viewport-only keyframe rows. Server-side root cause
     of a real mobile render bug; fixes the wire row-id scheme everything builds
     on. *Do first.*
  2. **t1055** (bug, low effort) — `pause` flow-control verb (server/phone
     currently disagree). Cheap, isolated.
  3. **t1007** (chore, low effort) — data-plane DoS / resource caps. Cheap, and
     matters before any beyond-LAN exposure.
  4. **t1045** (perf) — roster-vs-focused content split. The key cellular
     bandwidth win (stream binary content only for the focused pane).
- **Tier 1 — strongly recommended, larger:**
  5. **t1057** (feature, high) — history RPC scrollback (follows t1054: once live
     keyframes are viewport-only, scrollback is reached only via this RPC).
  6. **t1056** (feature) — `viewport_hint` clipping (more bandwidth savings;
     paired with mobile, value lands once both ship).
- **Tier 2 — pair with this roadmap's PUBLIC-EXPOSURE phases (Alternative B /
  Phase 3-4), not the cheap Phase-2 tunnel:** **t1068** (request rate-limit),
  **t1066** (cert rotation), **t1067** (bearer rotation). Phase-2 (mesh VPN /
  user-run tunnel) reuses the existing LAN trust model and needs none of these.
- **Independent of t1061 (any time):** t1011 (workflow launch policy — control
  plane), t1002 (shellcheck hygiene bug on `aitask_applink.sh`), t1058 (cursor
  frames, low priority).

## Suggested decomposition (later)

1. Phase-2 tunnel how-to + pairing change to accept user-supplied host/FQDN
   (lead with Tailscale/mesh; cross-repo: mobile pin relaxation for A2).
2. Phase-3 relay-broker **design task** (outbound dial, QR scheme, E2E key
   exchange) — design-only, gated on t985.
3. Mobile reconnection / network-change + multi-address/relay-URL support
   (`aitasks_mobile`) — currently untracked there.
4. (Optional) Hosted-box deployment guide (Alternative B) and Phase-4 WebRTC.

## Prior art / external references

Two existing implementations solve this exact problem (remote access to a live
local coding-agent session). **Borrow their *connectivity* ideas, not their
*rendering* model** — the web-terminal genre streams a raw VT/ANSI stream to a
browser terminal, which `wish_ssh_evaluation.md` already rejected for the
*native* mobile companion (needs a VT parser, loses per-verb permission gating).
The useful part is purely *how they reach the machine from outside the LAN*.

- **Anthropic Claude Code "Remote Control"** (closest architectural sibling — a
  native client into a live local session). Connectivity model:
  *outbound-HTTPS-only, never opens inbound ports*; the local process registers
  with the API and polls, and the server routes messages between the mobile/web
  client and the local session. **This is exactly Phase 3 (PC dials out to a
  broker), with Anthropic's API as the broker** — validates the architecture and
  its CGNAT/firewall immunity. Also: *multiple short-lived, purpose-scoped
  credentials expiring independently* (feeds t985 / the Phase-3 E2E story);
  auto-reconnect on sleep/network-drop with a ~10-min outage→exit policy
  (validates `Suspended → Connected` + bearer TTL); push notifications +
  presence suppression (which themselves require a broker path).
  See https://code.claude.com/docs/en/remote-control
- **`decolua/9remote`** (open-source; same "terminal in your pocket" genre as the
  @JC_builds web-terminal thread that prompted this). Two ideas not yet captured
  above: (a) *auto-spawned zero-config Cloudflare Quick Tunnel (outbound-only)* —
  the app spawns the tunnel itself and encodes the public URL in the QR, turning
  Phase 2 from "user runs a tunnel" into a near-turnkey "app runs the tunnel"
  without building our own broker; (b) *`LocalFirstAdapter` races LAN vs. tunnel
  and uses whichever is faster* — keep direct-LAN for latency AND a tunnel for
  reach, prefer LAN when co-located. Plus a permanent-machine-key + one-time
  30-min QR-key model and a *PTY daemon that survives restarts* (stronger resume
  than today's process-bound session). See https://github.com/decolua/9remote
- @JC_builds web-terminal thread (origin of this note):
  https://x.com/JC_builds/status/2069507796291498022

**Transferable refinements to fold into decomposition:**
1. Auto-spawned zero-config tunnel (Cloudflare Quick Tunnel) → makes the Phase-2
   tunnel item (decomposition #1) near-turnkey; QR carries the auto-generated
   public URL.
2. LAN-vs-tunnel racing (LocalFirstAdapter) → fills the mobile multi-address /
   failover gap (decomposition #3); one client handles co-located and remote.
3. Outbound-only dial-to-broker → confirms the Phase-3 design (decomposition #2).
4. Multiple short-lived purpose-scoped credentials → feeds t985 and the Phase-3
   end-to-end key story.
5. Persistent session daemon surviving restarts → resume robustness beyond the
   current process-bound `Suspended → Connected`.

## References

- `aidocs/applink/protocol.md` (§Roadmap to cross-network, §Pairing flow)
- `aidocs/applink/wish_ssh_evaluation.md` (hosted-deployment alternative, public-exposure hardening)
- `aidocs/applink/permissions.md`
- `xdeprepo: aitasks_mobile` — paired decomposition spans both repos; mirror a
  matching task on the mobile side when children are assigned.
