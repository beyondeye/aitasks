---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [chat_surface, python]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1120
created_at: 2026-07-05 18:05
updated_at: 2026-07-15 17:44
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
