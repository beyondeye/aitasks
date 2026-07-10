---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: high
depends: [t1061_1]
xdeps: [t31_3]
xdeprepo: aitasks_mobile
issue_type: feature
status: Implementing
labels: [applink, applink_connectivity]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1061
implemented_with: claudecode/fable5
created_at: 2026-07-02 23:46
updated_at: 2026-07-10 10:32
---

**A3 of the t1061 paired decomposition** (see
`aiplans/p1061_applink_outside_network_connectivity_roadmap.md` — "Endpoint &
trust model" is normative). Auto-spawned Cloudflare Quick Tunnel — turnkey
Phase 2 (9remote's model: the app runs the tunnel itself). Depends on A1
(`t1061_1`, wire grammar + emission plumbing) and cross-repo on
`aitasks_mobile#31_3` (M3 — client must accept per-endpoint `trust=ca`);
staged so the client capability lands first.

## Origin TLS is a mandatory FIRST verification step, not an assumption

The applink origin is `wss://` with a **self-signed, no-SAN cert**
(`tls.py`: fixed `CN=ait-applink`, no SANs); cloudflared validates origin
certificates by default, so a naive quick tunnel would connect but fail to
proxy. Before any UI work:

- Empirically verify and document the working invocation — expected shape:
  `cloudflared tunnel --url https://localhost:<port> --no-tls-verify`
  (or `originRequest: {noTLSVerify: true}` config).
- Confirm **WebSocket upgrade proxying end-to-end** (pair + monitor stream
  through the tunnel).
- Document the skipped origin verification as an accepted, bounded trust step
  (loopback-only: cloudflared → localhost).
- If quick tunnels turn out not to support the needed origin flags, fall back
  to documenting named tunnels (account required) and record the deviation in
  the plan.

## Work

- Spawn + supervise the `cloudflared` child process: detect binary; lifecycle
  tied to the applink server; clean shutdown; parse the generated
  `*.trycloudflare.com` URL from cloudflared output.
- **QR emission (per the A1 endpoint model):** tunnel endpoint =
  `host=<x>.trycloudflare.com, port=443, kind=tunnel, trust=ca`; LAN endpoint
  stays available (`;lan;pin`).
- **Primary-endpoint decision (record in this child's plan):** primary =
  tunnel + `trust=ca` maximizes remote turnkey-ness but **breaks old clients**
  scanning that QR (they pin-verify Cloudflare's cert and fail). Default to
  primary=LAN/pin with tunnel in `alt` (compatible; M2 clients race and reach
  the tunnel) unless the pairing UI offers an explicit "remote-first QR"
  toggle.
- TUI + headless surfaces: opt-in flag/config
  (`tmux.applink.auto_tunnel: cloudflared`), status line showing tunnel state.
- **`MAX_PER_IP` check:** tunneled connections all arrive from loopback —
  verify the per-IP admission cap (`server.py`, `MAX_PER_IP = 8`, t1007 caps
  context) doesn't bite; adjust/exempt deliberately if it does.

## Security notes (include in docs)

- Quick tunnels are ephemeral public hostnames; bearer + permission profiles
  still gate every verb.
- Recommend pairing with t1068 (request rate-limit) for sustained use.

## Verification

- Live end-to-end: spawn tunnel, scan QR with an M2+M3-capable client, confirm
  both LAN and tunnel endpoints work and racing prefers LAN when co-located.
- Unit tests for URL parsing from cloudflared output, process supervision
  (spawn/shutdown), and QR emission shape.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-10T07:32:14Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-10T13:48:39Z status=pass attempt=1 type=human
