---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: [t1852_1, t1852_5]
issue_type: feature
status: Done
labels: [testmap, install, ait_setup, bash_scripts]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1931]
assigned_to: dario-e@beyond-eye.com
anchor: 1852
implemented_with: claudecode/opus5_5
created_at: 2026-09-22 17:27
updated_at: 2026-10-09 15:29
completed_at: 2026-10-09 15:29
---

## Context

Child **M1.6 — Framework home report and migration** of t1852 (test map
feature, module M1). Wave **H**. Delivers `ait engine home [--migrate]`, the
explicit verb that moves the legacy `~/.aitask/` tenants into `$AITASKS_HOME`
and leaves a symlink behind. In this release `ait setup` only prints the
`HOME_LEGACY:` hint; flipping the default is a named follow-up (not v1).
**Providers:** M1.1 (`t1852_1`, `AITASKS_HOME` and `.home.lock`), M1.5
(`t1852_5`, `aitask_engine.sh` — this child adds its `home` arm).

Authoritative specification: `aidocs/testing_engine/n014_explorer_006_proposal.md`
— Module Map `#### M1` row M1.6 (now naming the destination-collision
preflight — parent-plan Deviation 7), component *Framework home report and
migration verb (M1.6)*, *Assumptions → Engine, distribution and install (M1)*
(`assumption_home_symlink_compatibility`, `assumption_legacy_user_root_coexists`),
*Tradeoffs → The per-user root (M1)* (`tradeoff_two_user_roots`,
`tradeoff_split_home_rejected`, `tradeoff_home_migration_window`), *Named
follow-ups (not v1)*. Parent plan:
`aiplans/p1852_testmap_m1_engine_foundation_and_distribution.md`.

**Coarse plan only.** The child plan `aiplans/p1852/p1852_6_m1_6_framework_home_migration.md`
records what the proposal fixes for M1.6 and does not design internals; its
**Step 0 — Reality check** (mandatory, before any code, recorded in the plan)
inspects the landed `aitask_engine.sh`, `lib/aitasks_home.sh`, the current set
of legacy tenants `aitask_setup.sh` creates (the known set once lacked
`pypy_venv`) and the 8 framework files / 35 references that dereference
`~/.aitask` (name the tasks and commits).

## Scope (from the proposal)

- `ait engine home` prints `HOME_ROOT:<path>`, `HOME_LEGACY:<path>|<tenants>`,
  `HOME_SYMLINK:none|<target>` and `HOME_NEXT:<what --migrate would do>`.
- `ait engine home --migrate` runs under `flock $AITASKS_HOME/.home.lock`
  and refuses while another `ait` holds the lock. It runs a **preflight over
  every present legacy entry before any move** and refuses — with nothing
  moved and both trees intact — reporting `no-legacy-root`,
  `already-migrated`, `foreign-symlink:<target>`, `cross-device`,
  `unknown-entry:<name>` or `destination-exists:<name>` (a present legacy
  entry whose `$AITASKS_HOME/<name>` already exists; `engine/` always does
  after `ait setup`, and a `mv` onto an existing directory would nest the
  source inside it). Only then it moves each present entry of the known set
  `{venv, pypy_venv, python, bin, uv, dev_tier, update_check, engine}` with a
  same-device `mv`, `rmdir`s the emptied legacy root and immediately leaves
  `ln -s $AITASKS_HOME ~/.aitask` behind; prints `HOME_MIGRATED:<n>` or
  `HOME_SKIPPED:<reason>`.
- Setup prints the `HOME_LEGACY:` hint when legacy tenants exist and never
  migrates; `--no-home-migration` / `AIT_HOME_MIGRATE=0` are reserved for the
  follow-up that flips the default.
- Migration cases in `tests/test_aitasks_home.sh` (a named extension of
  M1.1's file): every refusal reason including `destination-exists` with a
  pre-created `$AITASKS_HOME/engine/` asserting both trees byte-identical and
  nothing moved; the known-set move including `pypy_venv`; the trailing
  symlink; `HOME_MIGRATED:<n>` / `HOME_SKIPPED:<reason>`; idempotent re-run
  (`already-migrated`); a hostile pre-existing symlink; the `AITASKS_HOME`
  override; `ait engine home` report lines. Through a real `install.sh --dir`
  where the case needs a populated legacy root.

## Key files to modify

- `.aitask-scripts/aitask_engine.sh` — the `home` arm (owned arm; the rest
  is M1.5's).
- `.aitask-scripts/aitask_setup.sh` — the `HOME_LEGACY:` hint (named
  extension of setup).
- `tests/test_aitasks_home.sh` — the migration cases (named extension of
  M1.1's file).

## Reference files for patterns

- `.aitask-scripts/lib/stale_lock.sh` and `lib/registry_lock.sh` — the
  framework's flock idioms; `aidocs/framework/shell_conventions.md` on
  `sed_inplace()` and BSD/GNU portability (`sed_macos_issues.md`), since
  `mv`, `rmdir`, `ln -s` and `stat` device checks must work on macOS.
- `aitask_setup.sh` `setup_pypy_venv()`, `install_python_wrappers()` — the
  tenants being moved and the absolute paths that must keep resolving through
  the symlink (`assumption_home_symlink_compatibility`).

## Provides / consumes

- **Provides:** the migration verb; the named follow-up that flips the
  default.
- **Consumes:** M1.1 (`t1852_1`), M1.5 (`t1852_5`).

## Implementation plan (coarse)

1. Step 0 — Reality check.
2. `home` report arm.
3. `--migrate`: lock → preflight (all refusals, `destination-exists`) →
   moves → `rmdir` → symlink → report.
4. Setup `HOME_LEGACY:` hint.
5. Migration test cases including the both-trees-intact refusal assertion.

## Verification

- `bash tests/test_aitasks_home.sh` passes with the new cases.
- On a scratch `HOME` with a populated legacy root and a pre-created
  `$AITASKS_HOME/engine/`, `ait engine home --migrate` prints
  `HOME_SKIPPED:destination-exists:engine` and `diff -r` of both trees before
  and after is empty; after removing the collision, the migration completes,
  `~/.aitask` is a symlink and `~/.aitask/venv/bin/python` still runs.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1852_1** id=2026-09-23T13:21:16Z.5bef83493af94e27eee47fd6 from=t1852_1 from_verified=yes at=2026-09-23T13:21:16Z base=5e378b436a5237d795aff5d9abc498e6632a4880 base_branch=main dirty=yes host=omg16
>
> | From the t1852_1 (M1.1) reality check — two findings for the migration child. Claim, not instruction; the lib and the guard are approved but UNCOMMITTED as of this moment (main @ 63012375f + working tree), so verify against the landed files when you pick.
> | 
> | 1. Legacy reference count. The proposal's `assumption_home_symlink_compatibility` and the parent plan's anchors say "8 framework files, 35 references" to `~/.aitask`. As of main @ 63012375f the tree has 9 files / 36 references: the ninth is the `ait` dispatcher itself (`ait:127`, `$HOME/.aitask/update_check` in `check_for_updates()`). It dereferences the path, so the assumption still holds — but your symlink-compat re-check should count `ait` too, and `update_check` is already in the known-entry set.
> | 
> | 2. Grep guard shape (`tests/test_aitasks_home.sh`, which you extend with the migration cases). There is NO file allowlist. It scans `.aitask-scripts/aitask_engine.sh` whole (pre-registered feature file) line by line, dropping pure-comment lines; the only exemption is a trailing `# legacy-root-ok: <reason>` comment on the specific line. Mark every legitimate legacy-root line of the `home` arm that way — the `HOME_LEGACY:` report, the known-entry loop including the `engine` entry, the `destination-exists:engine` preflight, the `rmdir` and the `ln -s $AITASKS_HOME ~/.aitask` — and any unmarked line elsewhere in the file still fails. The `HOME_LEGACY:` hint in setup lands beside `AITASKS_HOME:<path>` (protocol form, no space) in the summary block after `Python venv:`; if that hint lives inside its own function in `aitask_setup.sh`, register it in the guard's `FEATURE_FUNCTIONS` and mark its lines.
> | 
> | Also available to you: `AITASKS_HOME_LOCK` (`$AITASKS_HOME/.home.lock`) is exported by the lib for your `flock`.

> **✉ note:t1852_5** id=2026-10-06T20:12:59Z.2dffd0f7fa5b5b2d7102c8c8 from=t1852_5 from_verified=yes at=2026-10-06T20:12:59Z base=7f412d482c3e1e67c0bae2729754b8505f95ba05 base_branch=main dirty=yes host=omg16
>
> | From t1852_5 (M1.5), tree-relative to code commit 7f412d482. These are claims for you to check against the landed files, not instructions.
> | 
> | 1. `home` arm: `.aitask-scripts/aitask_engine.sh` dispatches `build|test|cross|prune`. The comment `# home [--migrate] — M1.6 (t1852_6) adds this arm` marks where the `home` arm goes. Today `home` falls to UNKNOWN_VERB, exit 64. Test case E3 in `tests/test_install_engine_binary.sh` pins that behaviour, so update E3 when you add the arm. The script sources `lib/terminal_compat.sh`, `lib/aitasks_home.sh` and `lib/engine_install.sh` at column 0. Your migration lines in this file need the per-line `# legacy-root-ok:` marker. `aitask_engine.sh` and `lib/engine_install.sh` are both registered as FEATURE_FILES in the `tests/test_aitasks_home.sh` guard.
> | 2. Slot layout, owned by `lib/engine_install.sh`. Release slots are `$AITASKS_HOME/engine/v<V>/` and hold:
> |    - `ait-testmap`;
> |    - `ait-testmap.sha256`, the installer-side sidecar (`<hex>  ait-testmap`), written only after a verified release install;
> |    - `.dev`, a marker for a non-release build that no installer replaces without `--force-engine`.
> |    `engine/dev/` is the dev slot, with no marker. There are also transient `engine/.staging.*` dirs.
> | 3. Per-slot publication locks are stale_lock mutexes at `$AITASKS_HOME/engine/.locks/<slot>` (`v<V>` or `dev`). Every slot writer holds one: the three install tiers, `ait engine build` and `ait engine prune`. A migration that moves `engine/` while one is held could race a publish, so your preflight should treat a live slot lock as busy.
> | 4. Nobody takes `AITASKS_HOME_LOCK` yet. `install_engine_binary` and `prune` do not refuse during a migration; adding that refusal is yours.
> | 5. Publication refuses a slot whose resolved device differs from the staging dir's (`TESTMAP_BINARY:slot-cross-device`). So a migration leaving `engine/` symlinked onto another filesystem would make every later install refuse.

> **👁 note:read** id=2026-10-06T20:17:09Z.5df4d08201d8cd6dec3412b0 by=t1852_6 at=2026-10-06T20:17:09Z mode=explicit ids=2026-09-23T13:21:16Z.5bef83493af94e27eee47fd6,2026-10-06T20:12:59Z.2dffd0f7fa5b5b2d7102c8c8

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-07T19:32:40Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-09T12:28:53Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-10-09T12:29:52Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:83dda8a18cf630e5

> **✅ gate:risk_evaluated** run=2026-10-09T12:29:52Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1852_6/risk_evaluated_2026-10-09T12:29:52Z-risk_evaluated-a1.log`
