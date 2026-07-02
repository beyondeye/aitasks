---
Task: t1061_5_hosted_box_deployment_guide.md
Parent Task: aitasks/t1061_applink_outside_network_connectivity_roadmap.md
Sibling Tasks: aitasks/t1061/t1061_1_*.md, aitasks/t1061/t1061_2_*.md, aitasks/t1061/t1061_3_*.md, aitasks/t1061/t1061_4_*.md
Archived Sibling Plans: aiplans/archived/p1061/p1061_*_*.md
Worktree: aiwork/t1061_5_hosted_box_deployment_guide
Branch: aitask/t1061_5_hosted_box_deployment_guide
Base branch: main
---

# Plan: A5 — Hosted-box deployment guide (Alternative B, low priority)

Independent, documentation-only. The task body carries the full brief; see
`aidocs/applink/wish_ssh_evaluation.md` (Alternative B) and the parent plan.

## Steps

1. Write `aidocs/applink/hosted_deployment_guide.md`:
   - Hosted topology: applink server on an always-on public VM; dedicated
     tmux socket (`AITASKS_TMUX_SOCKET`); systemd unit for headless mode.
   - TLS: real CA cert + FQDN vs pinning; client implications
     (per-endpoint `trust=ca` from `aitasks_mobile#31_3` once landed).
   - Firewall posture for a world-reachable endpoint (LAN-CIDR doctor
     guidance does not apply).
   - Hardening checklist referencing (not duplicating) t1066 cert rotation,
     t1067 bearer rotation, t1068 request rate-limit as prerequisites for
     sustained public exposure.
2. Cross-link from `wish_ssh_evaluation.md`.

## Verification

- Dry-run on a scratch VM, or verify every referenced command/env var/config
  key against current source; cross-references accurate.

## Step 9 (Post-Implementation)

Standard cleanup/merge/archival per task-workflow Step 9.
