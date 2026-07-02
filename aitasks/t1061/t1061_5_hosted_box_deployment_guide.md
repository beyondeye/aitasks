---
priority: low
effort: medium
depends: []
issue_type: documentation
status: Ready
labels: [applink, applink_connectivity]
gates: [risk_evaluated]
anchor: 1061
created_at: 2026-07-02 23:46
updated_at: 2026-07-02 23:46
---

**A5 of the t1061 paired decomposition** (see
`aiplans/p1061_applink_outside_network_connectivity_roadmap.md`). Hosted-box
deployment guide — Alternative B per
`aidocs/applink/wish_ssh_evaluation.md`: run the applink server on an
always-on public VM (PC can be off; phone connects directly). Low priority;
independent of the other children. No new protocol work.

## Deliverable

A deployment guide (extend `aidocs/applink/` — e.g.
`hosted_deployment_guide.md`) covering:

- Dedicated tmux socket for the hosted topology (`AITASKS_TMUX_SOCKET` env
  var — see the aside in `wish_ssh_evaluation.md`; t953 background).
- systemd unit for the applink server (headless mode).
- TLS story: real CA cert + FQDN vs the pinning model — and what each means
  for the mobile client (per-endpoint `trust=ca` from
  `aitasks_mobile#31_3` / M3 once it lands).
- Firewall posture for a world-reachable endpoint (the LAN-CIDR-scoped
  firewall doctor guidance does not apply).
- **Hardening checklist referencing the Tier-2 tasks as prerequisites for
  sustained public exposure:** t1066 (cert rotation), t1067 (bearer
  rotation), t1068 (request rate-limit). Reference, do not duplicate.

## Verification

- Dry-run the guide on a scratch VM (or verify every referenced command, env
  var, and config key against the current source).
- Confirm cross-references (wish_ssh_evaluation.md, security.md residuals,
  Tier-2 task IDs) are accurate.
