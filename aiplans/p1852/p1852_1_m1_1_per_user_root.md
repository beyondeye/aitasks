---
Task: t1852_1_m1_1_per_user_root.md
Parent Task: aitasks/t1852_testmap_m1_engine_foundation_and_distribution.md
Sibling Tasks: aitasks/t1852/t1852_2_*.md, aitasks/t1852/t1852_3_*.md, aitasks/t1852/t1852_4_*.md, aitasks/t1852/t1852_5_*.md, aitasks/t1852/t1852_6_*.md
Archived Sibling Plans: aiplans/archived/p1852/p1852_*_*.md
Base branch: main
Output branch: main
---

# Coarse plan: t1852_1 — M1.1 Per-user root

## Context

Parent goal: M1 — Engine foundation and distribution (`ait-testmap` as a
buildable, installable, resolvable binary). This submodule is **M1.1 Per-user
root**, wave **A**, no providers — one of the two roots of the feature's
dependency graph. It delivers the one `AITASKS_HOME` path resolver every bash
piece of the feature sources, and the setup lines that make the per-user root
visible.

This coarse plan records what the proposal fixes for M1.1. It does not design internals against providers that do not exist yet;
the Reality check below does that when this child is picked.

## Proposal reading list

`aidocs/testing_engine/n014_explorer_006_proposal.md`:
- *Module Map* → `#### M1` row **M1.1**; *How to read it*; *Cross-module
  interfaces*; *Suggested implementation order* (wave A).
- *Components* → *Per-user root (M1.1)*.
- *Architecture* → *Process map* (the `lib/aitasks_home.sh` line), *Where
  state lives*.
- *Assumptions* → *Engine, distribution and install (M1)*:
  `assumption_legacy_user_root_coexists`, `assumption_home_symlink_compatibility`.
- *Tradeoffs* → *The per-user root (M1)*.
- Framework rules: `aidocs/framework/shell_conventions.md` (incl. the
  source-on-startup ↔ `test_scaffold.sh` rule), `aidocs/framework/sed_macos_issues.md`,
  `aidocs/framework/aitasks_extension_points.md` ("No global PATH override",
  "Adding a new helper script").
- Parent plan: `aiplans/p1852_testmap_m1_engine_foundation_and_distribution.md`
  (reality anchors, deviations 4 and 6).

## Owned files / provides / consumes

- **Owns:** `.aitask-scripts/lib/aitasks_home.sh`; `tests/test_aitasks_home.sh`
  (the default, the env override, the no-`~/.aitask/` grep); the
  `mkdir -p "$AITASKS_HOME/engine"` (0755) and the `AITASKS_HOME:<path>`
  summary line in `aitask_setup.sh` (a named extension of setup); the
  `test_scaffold.sh` copy-list entry when the startup-chain rule applies.
- **Provides:** `AITASKS_HOME=${AITASKS_HOME:-$HOME/.aitasks}`,
  `aitasks_engine_dir <version|dev>`, `$AITASKS_HOME/.home.lock` — sourced by
  the shim (M1.4), `install_engine_binary()` / `aitask_engine.sh` (M1.5), the
  migration verb (M1.6), later the verifiers (M8) and `aitask_test.sh` (M5.1).
- **Consumes:** nothing.
- **Named extensions into this child's files:** M1.6 adds the migration
  cases to `tests/test_aitasks_home.sh`.

## Step 0 — Reality check (MANDATORY, before any code; record the outcome here)

1. Re-read the proposal rows above and the parent plan's *Repository reality
   anchors* table. Those anchors are claims, not facts, by the time this
   child is picked.
2. Inspect the actual current state on the merge target: does
   `lib/aitasks_home.sh` or any `~/.aitasks` reference already exist (name
   the task and commit if so); the current `~/.aitask/` reference set
   (`grep -rn 'HOME/\.aitask\b\|~/\.aitask\b' .aitask-scripts/`); the setup
   summary block shape; the current `test_scaffold.sh` copy list.
3. Tabulate every difference: *proposal says / coarse plan says / repository has*.
4. Decide per difference: adapt this child; revise this plan; or revise the
   proposal (cut errors go to the proposal). Record the decision and reason.
5. Send `/aitask-note` to every downstream child a difference breaks
   (t1852_4, t1852_5, t1852_6 consume the resolver API).
6. Re-confirm every file touched is owned here or lands as the owner's named
   extension (setup: only the `mkdir` + summary line).

**Outcome:** _(to be recorded when executed)_

## Implementation steps (coarse)

1. Write `.aitask-scripts/lib/aitasks_home.sh`: double-source guard (pattern
   `lib/aitask_path.sh`), `export AITASKS_HOME="${AITASKS_HOME:-$HOME/.aitasks}"`,
   `aitasks_engine_dir()` returning `$AITASKS_HOME/engine/v<version>/` or
   `$AITASKS_HOME/engine/dev/`, `AITASKS_HOME_LOCK="$AITASKS_HOME/.home.lock"`.
   No `~/.aitask/` anywhere in it.
2. `aitask_setup.sh`: source the lib, `mkdir -p` the engine dir with mode
   0755, print `AITASKS_HOME:<path>` beside `Python venv:` in the summary.
3. `tests/test_aitasks_home.sh`: default resolves to `$HOME/.aitasks`; env
   override honoured; grep guard over this feature's scripts for `~/.aitask/`
   (documented scope like `tests/test_no_raw_tmux.sh`; the legacy tenants in
   `aitask_setup.sh` / `python_resolve.sh` / `aitask_path.sh` are *not* this
   feature's and are excluded by an explicit allowlist).
4. If any startup `source` chain now includes the lib, add it to
   `tests/lib/test_scaffold.sh::setup_fake_aitask_repo()` in the same change.

## Verification / acceptance

- `bash tests/test_aitasks_home.sh` passes; `shellcheck .aitask-scripts/lib/aitasks_home.sh` clean.
- `AITASKS_HOME=<tmp> ./ait setup` prints `AITASKS_HOME:<tmp>` and creates
  `<tmp>/engine/` (0755); without the override the default is `$HOME/.aitasks`.
- No framework script of this feature names `~/.aitask/`.

## Step 9 reference

Archival and cleanup follow the shared `task-workflow` Step 9
(post-implementation). Current-branch profile: no worktree, no merge.
