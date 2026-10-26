---
priority: low
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: enhancement
status: Done
labels: [verification, bug]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1689
followup_kind: risk_mitigation
implemented_with: claudecode/opus5_5
created_at: 2026-10-26 15:25
updated_at: 2026-10-26 17:37
completed_at: 2026-10-26 17:37
---

## Origin

Risk-mitigation ("after") follow-up for t2144, created at Step 8d after implementation landed.

## Risk addressed

Residual: `mise x` wrappers outside ~/.local/bin are no longer protected.

> **Residual:** a `mise x` wrapper in a dir other than `~/.local/bin`, placed
> ahead of mise entries, is no longer protected. t1689 hoisted mise ahead of
> every dir. All observed wrappers (23 on this host, plus the t1689 incident)
> are in `~/.local/bin`, and the Omarchy docs and the user's rc name that same
> dir. Protecting the general case would mean sniffing file contents on the
> per-call hot path, which t1689 already rejected · severity: medium

## Goal

t2144 (commit 230234839) narrowed spawn-PATH normalization
(`.aitask-scripts/lib/tmux_exec.py::normalize_spawn_path`,
`.aitask-scripts/lib/spawn_path.sh::ait_spawn_path_normalize`) to a minimal
displacement. Only `$HOME/.local/bin` is moved behind the last mise entry
(anything under `<mise_data>/`), so a healthy mise-activated shell reaches
panes unchanged.

1. Measure first. Record whether self-referential
   `mise use … && exec mise x <n> -- <n>` wrappers ever appear outside
   `~/.local/bin` on supported hosts, for example `$XDG_BIN_HOME`,
   `/usr/local/bin`, or `~/bin`. Sources: Omarchy's `omarchy-mise-install`, the
   mise docs' wrapper recipes, and user reports.
2. Only if they do, extend the hazard-dir set in both parity-pinned
   implementations, or add a targeted pre-exec guard in
   `ait codeagent invoke`, rather than reinstating the full mise-block hoist.
   The full hoist breaks legitimate tool precedence (t2144: `~/.opencode/bin`
   ahead of mise on purpose).
3. If they never appear, close with the measurement recorded.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-26T14:28:48Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-26T15:19:38Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-10-26T15:37:44Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:9f107c815ee7f866

> **✅ gate:risk_evaluated** run=2026-10-26T15:37:44Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2153/risk_evaluated_2026-10-26T15:37:44Z-risk_evaluated-a1.log`
