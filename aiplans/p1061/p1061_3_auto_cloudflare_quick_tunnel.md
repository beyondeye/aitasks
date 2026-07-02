---
Task: t1061_3_auto_cloudflare_quick_tunnel.md
Parent Task: aitasks/t1061_applink_outside_network_connectivity_roadmap.md
Sibling Tasks: aitasks/t1061/t1061_1_*.md, aitasks/t1061/t1061_2_*.md, aitasks/t1061/t1061_4_*.md, aitasks/t1061/t1061_5_*.md
Archived Sibling Plans: aiplans/archived/p1061/p1061_*_*.md
Worktree: aiwork/t1061_3_auto_cloudflare_quick_tunnel
Branch: aitask/t1061_3_auto_cloudflare_quick_tunnel
Base branch: main
---

# Plan: A3 — Auto-spawned Cloudflare Quick Tunnel (turnkey Phase 2)

Depends on A1 (`t1061_1`) and **cross-repo on `aitasks_mobile#31_3` (M3)** —
do not start until M3 has landed (client must accept per-endpoint
`trust=ca`). Authoritative design: parent plan
`aiplans/p1061_applink_outside_network_connectivity_roadmap.md`
(§"Endpoint & trust model"). The task body carries the full brief.

## Steps

1. **Origin-TLS verification FIRST (gate for the rest of the plan).**
   Empirically verify cloudflared can proxy the self-signed, no-SAN `wss://`
   origin: expected `cloudflared tunnel --url https://localhost:<port>
   --no-tls-verify` (or `originRequest: {noTLSVerify: true}`). Confirm
   WebSocket upgrade end-to-end (pair + monitor stream through the tunnel).
   Document the loopback-bounded skipped-verification trust step. If quick
   tunnels can't do it, fall back to documenting named tunnels and record the
   deviation.
2. Tunnel supervisor: detect binary, spawn, parse `*.trycloudflare.com` URL
   from output, lifecycle tied to the applink server, clean shutdown.
3. QR emission per the A1 grammar: tunnel endpoint
   (`<x>.trycloudflare.com:443;tunnel;ca`); default primary = LAN/pin with
   tunnel in `alt` (old-client compatible) unless a "remote-first QR" toggle
   is added — record the decision here.
4. Surfaces: `tmux.applink.auto_tunnel: cloudflared` config + CLI flag; TUI
   status line for tunnel state.
5. Check `MAX_PER_IP=8` (server.py) against all-loopback tunnel arrivals;
   adjust deliberately if it bites (t1007 context).
6. Tests: URL parsing from cloudflared output, supervisor spawn/shutdown, QR
   emission shape.

## Verification

- Live e2e: spawn tunnel, pair from an M2+M3-capable client; LAN and tunnel
  endpoints both work; racing prefers LAN when co-located.
- Security notes present in docs (ephemeral hostname; verbs still
  permission-gated; recommend t1068 for sustained use).

## Step 9 (Post-Implementation)

Standard cleanup/merge/archival per task-workflow Step 9.
