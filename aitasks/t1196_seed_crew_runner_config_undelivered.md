---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [codeagent]
gates: [risk_evaluated]
anchor: 1171
created_at: 2026-07-21 11:03
updated_at: 2026-07-21 11:03
---

## Origin

Spawned from t1194 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_setup.sh:1340-1352 — seed/crew_runner_config.yaml is
  delivered by neither install.sh nor the setup path, yet
  aidocs/agentcrew/agentcrew_architecture.md:245 states "ait setup seeds this
  file from seed/crew_runner_config.yaml" and
  .aitask-scripts/agentcrew/agentcrew_runner.py:68 reads
  aitasks/metadata/crew_runner_config.yaml.`

## Diagnostic context

t1194 built a drift guard asserting that the two delivery paths for
`aitasks/metadata/` agree:

1. `install.sh`'s `install_seed_*()` family (the tarball flow — it runs
   `rm -rf "$INSTALL_DIR/seed"` afterwards, so `seed/` is gone at runtime).
2. The source-tree flow: `populate_data_branch_seed_metadata()` +
   `ensure_agent_config_seeds()` in `aitask_setup.sh`.

While enumerating `seed/` for that guard, `crew_runner_config.yaml` turned out
to be referenced by neither side. The guard **cannot** flag it: it compares the
two manifests against each other, and a file absent from both produces no
drift. So this needs its own fix — it is invisible to the new regression guard
by construction.

Consequence: `agentcrew_runner.py` never finds a seeded
`aitasks/metadata/crew_runner_config.yaml` on a fresh install or a clean
clone, and the architecture doc's claim that `ait setup` seeds it is untrue.

## Suggested fix

Decide which is correct and make source and docs agree:

- If the file **should** be seeded: add it to BOTH delivery paths — an
  `install_seed_crew_runner_config()` in `install.sh` (wired into `main()`
  before the `seed/` cleanup) and a `cp` line in
  `populate_data_branch_seed_metadata()`. `tests/test_seed_manifest_drift.sh`
  then keeps the two in sync automatically.
- If it should **not** be seeded (the runner has a working built-in default):
  correct `aidocs/agentcrew/agentcrew_architecture.md:245` and consider
  removing `seed/crew_runner_config.yaml`.

Verify the runner's behavior when the file is absent before choosing.
