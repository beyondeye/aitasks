---
Task: t1061_2_phase2_tunnel_howto_doc.md
Parent Task: aitasks/t1061_applink_outside_network_connectivity_roadmap.md
Sibling Tasks: aitasks/t1061/t1061_1_*.md, aitasks/t1061/t1061_3_*.md, aitasks/t1061/t1061_4_*.md, aitasks/t1061/t1061_5_*.md
Archived Sibling Plans: aiplans/archived/p1061/p1061_*_*.md
Worktree: aiwork/t1061_2_phase2_tunnel_howto_doc
Branch: aitask/t1061_2_phase2_tunnel_howto_doc
Base branch: main
---

# Plan: A2 — Phase-2 tunnel how-to + roadmap status update

Depends on A1 (`t1061_1`). Authoritative design: parent plan
`aiplans/p1061_applink_outside_network_connectivity_roadmap.md`. The task
body carries the full brief.

## Steps

1. Read the **as-landed** A1 implementation (config keys, CLI flags, alt/trust
   grammar) — document current source, not this plan's expectations.
2. Write `aidocs/applink/tunnel_howto.md`:
   - Mesh VPN lead (Tailscale / ZeroTier / WireGuard): `advertised_host` =
     mesh IP, pin unchanged, step-by-step.
   - `ssh -L` port-forward recipe.
   - Manual reverse-tunnel recipe (cloudflared/ngrok + `advertised_trust: ca`)
     — gated on `aitasks_mobile#31_3` (M3); state the pre-M3 failure mode
     (pin mismatch on the tunnel's CA cert). Link `t1061_3` (A3).
3. Update `aidocs/applink/protocol.md` §Roadmap Phase-2 status
   (current-state-only prose per
   `aidocs/framework/documentation_conventions.md`).
4. Cross-link from `aidocs/applink/wish_ssh_evaluation.md` (Phase-2 escape
   hatch framing).

## Verification

- Every command / config key / flag named in the how-to exists in the A1
  implementation (grep against source).
- Internal doc links resolve.

## Step 9 (Post-Implementation)

Standard cleanup/merge/archival per task-workflow Step 9.
