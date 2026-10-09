---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [codeagent, models]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1916
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-09 15:45
updated_at: 2026-10-09 16:00
---

## Origin

Spawned from t1928 during Step 8b review.

## Upstream defect

- `tests/test_verified_update_flags.sh:27-33 — runs aitask_verified_update.sh in PROJECT_DIR against the real registry, so every run commits and pushes junk test_414_flags verified scores to origin/aitask-data (87 runs recorded so far); it should use a scaffolded fixture repo`

## Diagnostic context

While verifying t1928 (compare-and-swap rewrite of the model registries), this
suite was run as one of the counter-writer suites. Unlike
`tests/test_verified_update.sh` / `tests/test_usage_update.sh`, which build a
throwaway repo with `setup_fake_aitask_repo` (or the remote fixtures in
`tests/lib/metadata_update_fixture.sh`), this file does
`cd "$PROJECT_DIR" && bash "$UPDATE_SCRIPT" ... --skill test_414_flags --score N`.
That records a real verified score on `claudecode/opus4_6` in
`aitasks/metadata/models_claudecode.json` and, because the real data branch has
a remote, commits and pushes it to `origin/aitask-data`. The run during t1928
pushed two such commits; the key already carried 85 earlier runs.

It also makes the test's verdict environment-dependent: with the local data
branch diverged from origin, the first call returned `UPDATED_REMOTE_ONLY`
(exit 3) and `set -e` killed the file before any assertion ran.

## Suggested fix

Rebuild the test on the scaffolded fixture used by `tests/test_verified_update.sh`
(no-remote `setup_repo`, or `setup_remote_metadata_repo` from
`tests/lib/metadata_update_fixture.sh`) so it never touches the real registry;
optionally clean the accumulated `test_414_flags` entries out of
`models_claudecode.json` in a separate, reviewed commit.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-09T13:00:48Z status=pass attempt=1 type=human
