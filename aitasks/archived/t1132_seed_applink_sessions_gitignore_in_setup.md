---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [chat_surface, python]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1120
implemented_with: claudecode/opus4_8
created_at: 2026-07-05 18:05
updated_at: 2026-07-15 18:37
completed_at: 2026-07-15 18:37
---

## Origin

Spawned from t1120_2 during Step 8b review.

## Upstream defect

- `aitask_setup.sh:1348-1382 — no data-branch gitignore append block seeds
  aitasks/metadata/applink_sessions/ for fresh installs (the applink rule
  exists only as a manual commit on this repo's data branch, 9df76f759; a
  fresh downstream project pairing applink could commit its TLS key +
  session table).`

## Diagnostic context

While wiring the chatlink_sessions/ secrets hygiene for t1120_2, verification
showed the applink_sessions/ gitignore rule exists ONLY at
`.aitask-data/.gitignore:14` in this repo (one-off commit `9df76f759`
"ait: Gitignore applink runtime session state"). `aitask_setup.sh`'s
`setup_data_branch` appends gitignore blocks for `aitasks/new/`,
`userconfig.yaml`, `*.local.json`, `profiles/local/`, and (since t1120_2)
`aitasks/metadata/chatlink_sessions/` — but never for
`aitasks/metadata/applink_sessions/`. Any fresh downstream project that
bootstraps via `ait setup` and later pairs applink stores its TLS
cert/key + `sessions.json` (bearer sessions) in an unignored directory;
a blanket `git add .` on the data branch would commit those secrets. The
0700 dir mode does not protect against self-commits.

## Suggested fix

Add an append block in `setup_data_branch` mirroring the chatlink one added
by t1120_2 (`aitask_setup.sh` — "# chatlink runtime state" block):
guard `grep -qxF "aitasks/metadata/applink_sessions/"`, comment
`# applink runtime state (per-PC: TLS cert/key + active bearer sessions)`.
One block + a check-ignore assertion in a test.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-15T15:28:17Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-15T15:33:16Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-07-15T15:37:14Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:4bb32a6c8d4f7a99

> **✅ gate:risk_evaluated** run=2026-07-15T15:37:14Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1132/risk_evaluated_2026-07-15T15:37:14Z-risk_evaluated-a1.log`
