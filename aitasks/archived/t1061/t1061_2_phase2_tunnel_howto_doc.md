---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: [t1061_1]
issue_type: documentation
status: Done
labels: [applink, applink_connectivity]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1061
implemented_with: claudecode/fable5
created_at: 2026-07-02 23:45
updated_at: 2026-07-05 18:05
completed_at: 2026-07-05 18:05
---

**A2 of the t1061 paired decomposition** (see
`aiplans/p1061_applink_outside_network_connectivity_roadmap.md`). Phase-2
tunnel how-to documentation + roadmap status update. Depends on A1
(`t1061_1`) — it documents A1's `advertised_*` knobs.

## Context

With A1 landed, mesh-VPN reach works end-to-end (existing self-signed cert +
fingerprint pin are endpoint-agnostic). This child writes the user-facing
recipe collection and updates the protocol roadmap status.

## Work

- New `aidocs/applink/tunnel_howto.md`:
  1. **Lead with mesh VPN (Tailscale / ZeroTier / WireGuard)** — existing cert
     + pin work unchanged; set `tmux.applink.advertised_host` to the mesh IP
     (or `--advertise-host`), done.
  2. `ssh -L` port-forward recipe.
  3. **Manual reverse-tunnel recipe** (user-run cloudflared/ngrok:
     `advertised_host` = public hostname + `advertised_trust: ca`) —
     explicitly marked as **gated on `aitasks_mobile#31_3` (M3, per-endpoint
     CA trust) landing client-side**; until then fingerprint pinning fails
     against the tunnel's CA cert. Link M3 and A3 (`t1061_3`).
- Update `aidocs/applink/protocol.md` §Roadmap Phase-2 status —
  current-state-only prose per `aidocs/framework/documentation_conventions.md`
  (no version history in doc bodies).
- Cross-link from `aidocs/applink/wish_ssh_evaluation.md` where it frames
  wish as the Phase-2 escape hatch.
- A user-facing website page can come later; aidocs is the source of truth
  now.

## Verification

- Follow the mesh-VPN recipe verbatim on a real Tailscale setup (or verify
  each command/config key exists and is spelled correctly against the A1
  implementation).
- `hugo build` not required (aidocs only); check internal doc links resolve.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-05T14:49:38Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-05T15:04:37Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-07-05T15:05:09Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:3d817b8423b04821

> **✅ gate:risk_evaluated** run=2026-07-05T15:05:09Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1061_2/risk_evaluated_2026-07-05T15:05:09Z-risk_evaluated-a1.log`
