---
Task: t1852_testmap_m1_engine_foundation_and_distribution.md
Base branch: main
Output branch: main
plan_verified: []
---

# Plan: t1852 — Testmap M1: Engine foundation and distribution (coarse planning pass)

## Context

The test map feature (`aidocs/testing_engine/n014_explorer_006_proposal.md`,
committed at `cac8a6448`) is cut into ten modules, one parent task each
(t1852–t1861). This task is **M1 — Engine foundation and distribution**: the
`ait-testmap` Go engine as a buildable, installable, resolvable binary with
nothing project-specific in it yet.

The task body binds the planning protocol: this session performs only the
**coarse planning pass** for M1 — decompose the parent into **one child per
submodule row** (M1.1–M1.6), write a coarse plan per child that records what the
proposal fixes (scope, owned files, provided/consumed interfaces, acceptance
test lists, wave) plus the **mandatory Reality-check step**, and **stop** at the
child checkpoint. No code is written. The other nine parents get the same pass
before any child of any parent is implemented.

The Complexity Assessment answer is prescribed by the task body ("choose *Yes,
create child tasks*" and "at the child-task checkpoint choose *Stop here*");
this plan treats both as decided.

**Sequencing rule (clarified at this pass).** The user's stated preference
(2026-09-22, aborting an early t1853 pass) is that M1's children are
**implemented** before M2 (t1853) is planned. That preference is granular at
the **submodule**, not the parent: the task bodies record that module-level
dependencies form a cycle (M6.5 → M8.2/M8.4, M8.3 → M7.1/M7.2, M7.1 → M6.2)
and the graph is acyclic only at submodule granularity, so "wait for whole
provider parents to land" would deadlock M6, M7 and M8. The rule is therefore:
a parent's coarse pass starts once the **specific provider submodules its
wave-earliest children consume** have landed in the tree (M2 waits for M1.2;
M3.1 for M1.2 + M2.1; M6.1 for M1.5, M2.1, M2.5, M3.1, M5.2; …), and each
child is implemented in proposal wave order against landed providers. The
task bodies' "plan all ten before implementing any child" is read as an upper
bound on how far planning may run ahead, never as a requirement to plan
against providers that do not exist. Post-approval step 5 sends this
clarification to t1853–t1861 as a note (their bodies still carry the
all-ten-first wording), and the cross-linking pass task (step 5b) guards
itself with a completeness precondition that accepts archived records, since
by the time the last pass runs M1's children will have been archived.

## Repository reality anchors (verified 2026-09-22, main @ b0d8fa530)

These are the facts every child's reality check starts from; a later child
re-verifies them against its own merge target.

| fact | state now |
|---|---|
| `goengines/` Go module | does not exist; no `go.mod` outside `website/` (Hugo). **The proposal names this directory `engine/`; the user renamed it at this planning pass — see Deviation 6** |
| Go toolchain in CI | `release.yml` has no Go step; the only `actions/setup-go` is `hugo.yml` (`website/go.mod`) |
| Go on this dev host | go1.27.0 via mise (proposal pins Go 1.26 — M1.2 picks the toolchain line) |
| `.aitask-scripts/VERSION` | `0.35.1` |
| release tarball | `release.yml` tars an explicit path list (`ait`, `CHANGELOG.md`, `.aitask-scripts/`, `packaging/`, `skills/`, `seed/`, …) — `goengines/` is excluded by construction, nothing to add |
| `release.yml` jobs | `plan` → `release` (`needs: plan`, two `softprops/action-gh-release@v3` steps, VERSION-matches-tag guard) → `packaging` (`needs: [plan, release]`, `release-packaging.yml`) |
| legacy per-user root `~/.aitask/` | referenced in 8 framework files, 35 references (`aitask_setup.sh` venv/bin/python/uv/dev_tier, `lib/python_resolve.sh`, `lib/aitask_path.sh`, `aitask_upgrade.sh`, `aitask_codemap.sh`, `lib/launch_modes_sh.sh`, `lib/followup_kinds_sh.sh`, `lib/plan_paths_sh.sh`) — matches the proposal's count |
| `~/.aitasks/` | does not exist on any host yet; no script names it |
| `ait` dispatcher | `case "$1"` arms at `ait:197–357`; unknown command → `*)` arm exits 1. `ait setup` → `aitask_setup.sh`; `ait upgrade` → `aitask_upgrade.sh` |
| `ait upgrade` → `install.sh` | `aitask_upgrade.sh:152` runs the downloaded `install.sh --force --dir "$AIT_DIR"`; `install.sh:1487` sources `aitask_setup.sh --source-only`; both files carry a `--source-only` guard for tests (`install.sh:1518`, `aitask_setup.sh` tail) |
| `aitask_setup.sh` | 4528 lines; `main()` at 4364; summary block prints `Python venv: $VENV_DIR` — the `AITASKS_HOME:` line goes beside it; gitignore helper pattern `setup_gate_logs_gitignore()` (2345–2383); flags `--with-pypy/--with-chat/--with-dev` parsed in `main()` |
| `.gitignore` | no `.aitask-testmap/` rule yet |
| test conventions | `tests/lib/scratch_cwd.sh` + `test_scaffold.sh` + `asserts.sh`; bash tests run individually (`bash tests/test_x.sh`); grep-guard pattern in `tests/test_no_raw_tmux.sh`; ten tests already source `install.sh --source-only` (e.g. `tests/test_global_shim.sh`, `tests/test_agent_instructions.sh`) |
| source-on-startup rule | any lib added to `./ait`'s or a helper's startup `source` chain must be added to `tests/lib/test_scaffold.sh::setup_fake_aitask_repo()` in the same change (`aidocs/framework/shell_conventions.md:135`) |
| permission touchpoints | whitelist only helpers a skill invokes (`aidocs/framework/aitasks_extension_points.md` "Adding a new helper script"); `.claude/settings.local.json` allows `./ait` per-subcommand (`./ait git:*`, `./ait ls *`, …), not `./ait *` |
| docs | `aidocs/framework/go_engine.md` does not exist; `aidocs/packaging/packaging_strategy.md` exists; `CLAUDE.md` has no Engine block |
| sibling parents | t1853–t1861 all `Ready`, none decomposed yet; none depends on M1 by task data yet (they fill `depends:` at their own coarse pass) |

## Decomposition — six children, one per submodule row

Create all six with `--no-sibling-dep`, then set `depends:` exactly as the
table says (the auto sibling chain would over-constrain M1.2, which is
independent of M1.1). Ids are assigned in row order, so `t1852_<n>` = `M1.<n>`.

| child | name | scope (from the proposal's M1 row) | owns | depends | wave | effort |
|---|---|---|---|---|---|---|
| t1852_1 | `m1_1_per_user_root` | `AITASKS_HOME=${AITASKS_HOME:-$HOME/.aitasks}`, `aitasks_engine_dir <version\|dev>`, `$AITASKS_HOME/.home.lock`; `ait setup` creates `$AITASKS_HOME/engine/` (0755) and prints `AITASKS_HOME:<path>` beside the venv line; never falls back to `~/.aitask/` | `.aitask-scripts/lib/aitasks_home.sh`; `tests/test_aitasks_home.sh` (default, env override, the no-`~/.aitask/` grep over this feature's scripts); the `AITASKS_HOME:` line + `mkdir` in `aitask_setup.sh` (named extension of setup — see Ownership notes); the `test_scaffold.sh` copy-list entry | — | A | low |
| t1852_2 | `m1_2_engine_skeleton` | `goengines/` Go module (`go.mod` at `goengines/`, module path `github.com/beyondeye/aitasks/goengines`, pinned toolchain, deps `gopkg.in/yaml.v3`, `bmatcuk/doublestar/v4`, `golang.org/x/sync` only), `goengines/cmd/ait-testmap`, stdlib-`flag` verb table with `version` live and every other verb (`test select schedule run scan check stale annotate verify explain axes areas classify costs score attribute readiness brief onboard{…} runner`) registered as a stub exiting 64; line-protocol + `--json` + per-verb exit-contract helpers as the **shared** package `goengines/internal/lineproto`; `-X version/commit/contract` ldflags vars; `version --json` printing `ENGINE:<path>`; `CONTRACT_MISMATCH` helper; pool cap 8; **shared** `goengines/internal/platform`; **shared** `goengines/internal/gitx` (git exec, blob digests, `merge-base --is-ancestor`, `ls-tree`); the testmap-specific package root `goengines/internal/testmap/` (empty placeholder plus the fixture harness); `t.TempDir()` fixture harness with synthetic `(t<id>)` histories; `go test -bench` harness with the 2× regression rule | `goengines/**` except later packages; `goengines/go.mod` | — | A | high |
| t1852_3 | `m1_3_build_ci_release` | `goengines/build.sh` (single build + matrix `linux,darwin × amd64,arm64` over every `cmd/*`, `CGO_ENABLED=0`, `-trimpath -buildvcs=false -ldflags "-s -w -X …"`, `build.sh all`); `.github/workflows/goengines-check.yml` (gofmt, vet, test, 2× bench on push/PR touching `goengines/**`); the `goengines` job in `release.yml` (`actions/setup-go` with `go-version-file: goengines/go.mod`, vet, test, `build.sh all`) producing `ait-testmap_<V>_{linux,darwin}_{amd64,arm64}` + `ait-testmap_<V>_SHA256SUMS.txt`, attached by **both** `action-gh-release` steps, `release needs: [plan, goengines]`; VERSION guard unchanged; `release-packaging.yml` and nfpm `arch: all` untouched | `goengines/build.sh`; the two workflow edits; `aidocs/framework/go_engine.md` (build half) | M1.2 | B | medium |
| t1852_4 | `m1_4_shim_and_handshake` | `.aitask-scripts/aitask_testmap.sh` — strict handshake `AIT_TESTMAP_BIN` (override notice) > `AIT_ENGINE=dev` slot at `$AITASKS_HOME/engine/dev/` requiring `<V>-dev+<sha>` > `$AITASKS_HOME/engine/v<V>/` requiring `== VERSION` > `ENGINE_MISSING:<path>` exit 3 with the repair hint; never downloads. `lib/platform_detect.sh` mapping `uname`. The `ait testmap` dispatcher arm | `aitask_testmap.sh`; `lib/platform_detect.sh`; the `testmap)` arm in `ait`; `tests/test_testmap_shim.sh` (with an `AITASKS_HOME` host); `tests/test_platform_detect.sh` | M1.1, M1.2 | B | medium |
| t1852_5 | `m1_5_install_upgrade_dev_verbs` | `install_engine_binary()` in `aitask_setup.sh` (source order `--local-engine` > exact-version release asset > `--engine-from-source` > `ENGINE_MISSING` warning; `sha256sum -c` / `shasum -a 256` with `.sha256` sidecar short-circuit; atomic install to `$AITASKS_HOME/engine/v<V>/`; `version --json` must echo `<V>`; `.dev`-marked binaries never overwritten without `--force-engine`; `--no-testmap` / `AIT_TESTMAP_FETCH=0` → `TESTMAP_BINARY:skipped`; `.aitask-testmap/` gitignored by setup); reached by `ait setup` and by `ait upgrade` through `install.sh` — which requires **the engine flags in both argument parsers** (`--local-engine <path>`, `--engine-from-source`, `--no-testmap`, `--force-engine` in `install.sh`'s `while` parser, which today dies on any unknown option, and in `aitask_setup.sh::main()`'s `case`, which today knows only `--with-*`) **and the `install_engine_binary` call after `install_global_shim` in `install.sh`** (today the only function called there); `aitask_engine.sh` with `build\|test\|cross\|prune` (`prune` walks only `$AITASKS_HOME/engine/v*/` against the project registry); `report_testmap_state()` with `TESTMAP:engine-missing` / `TESTMAP:absent` (+ `run /aitask-testmap-onboard`) / `TESTMAP:onboarded` — setup reports, never onboards; the `engine)` dispatcher arm | the two functions in `aitask_setup.sh` **plus the four engine flags in `main()`'s parser and the calls that reach them**; **the four engine flags, their pass-through and the `install_engine_binary` call in `install.sh`** (named extension of the installer — see Deviation 8); `aitask_engine.sh` (except the `home` arm); the `engine)` arm in `ait`; `tests/test_install_engine_binary.sh`; the `packaging_strategy.md` paragraph naming `~/.aitasks/engine/`; the `CLAUDE.md` Engine block | M1.1, M1.3, M1.4 | C | high |
| t1852_6 | `m1_6_framework_home_migration` | `ait engine home` printing `HOME_ROOT:` / `HOME_LEGACY:<path>\|<tenants>` / `HOME_SYMLINK:none\|<target>` / `HOME_NEXT:`; `ait engine home --migrate` under `flock $AITASKS_HOME/.home.lock`, with a **preflight before any move** that refuses `no-legacy-root` / `already-migrated` / `foreign-symlink:<target>` / `cross-device` / `unknown-entry:<name>` / **`destination-exists:<name>`** (any present legacy entry whose `$AITASKS_HOME/<name>` already exists — `engine/` will, because setup creates it), so a refusal happens with **zero entries moved and both trees intact**; then moving the known set `{venv, pypy_venv, python, bin, uv, dev_tier, update_check, engine}` with same-device `mv`, `rmdir` of the emptied legacy root, `ln -s $AITASKS_HOME ~/.aitask`, `HOME_MIGRATED:<n>` / `HOME_SKIPPED:<reason>`; the `HOME_LEGACY:` hint in setup (setup only hints in this release) | the `home` arm of `aitask_engine.sh`; the `HOME_LEGACY:` hint in setup; the migration cases in `tests/test_aitasks_home.sh` (named extension of M1.1's file), including a `destination-exists` case asserting both trees unchanged after the refusal | M1.1, M1.5 | H | medium |

Labels per child: `testmap` on all; plus `install,ait_setup` (M1.1, M1.5, M1.6),
`go_engine` (M1.2, M1.3), `release_scripts` (M1.3), `ait_dispatcher` (M1.4,
M1.5), `testing,test_infrastructure` (M1.2), `bash_scripts` (M1.4, M1.5,
M1.6). Priority `medium` (parent's). Type `feature`. Gates: the profile
injects `--gates risk_evaluated`.

## Cross-module seams (recorded in every child body)

**Provides:** M1.1 → the one `AITASKS_HOME` resolver every bash piece sources
(shim, installer, `aitask_engine.sh`, later the verifiers and `aitask_test.sh`).
M1.2 → the binary every engine submodule of M2–M8 adds a package to; the
fixture and bench harnesses. M1.3 → release assets + sums M1.5 installs. M1.4 →
`ait testmap <verb>` for every later bash caller (M5.1, M6.5, M7.4, M7.5, M8.2,
M8.3, M9.3). M1.5 → an installed engine on every host that ran `ait setup`;
`TESTMAP:<state>`. M1.6 → the migration verb.

**Consumes:** nothing from other modules. M1.1 and M1.2 are the roots of the
graph, so no child of this parent carries a cross-parent `depends:`; the
reverse edges (M2.1, M2.3, M3.1 → `t1852_2`; M6.1 → `t1852_5`; M5.1 → `t1852_4`;
…) are written by those parents' coarse passes and checked in the cross-linking
pass after all ten are planned.

**Named extensions into M1-owned files** (a file has one owner):
- `report_testmap_state()` (M1.5) ships three states; **M6.1** adds
  `bootstrapping|<next>` — M1.5 leaves the state switch shaped for it and
  says so in a comment.
- The verb table (M1.2) registers every later verb as an exit-64 stub; each
  later engine submodule replaces only its own stub.
- `aitask_engine.sh` is M1.5's; M1.6 adds the `home` arm.
- `tests/test_aitasks_home.sh` is M1.1's; M1.6 adds the migration cases.
- `aidocs/framework/go_engine.md`: build half M1.3, engine half **M9.4**.
- `aitask_setup.sh`: M1.5 owns `install_engine_binary()` and
  `report_testmap_state()`; M1.1's `AITASKS_HOME:` line / `mkdir` and M1.6's
  `HOME_LEGACY:` hint land as small named extensions (setup is a pre-existing
  shared file, not an M1-created one).
- Invariant 5 binds every engine package (never writes `aitasks/`, `aiplans/`,
  `.aitask-data/`, a gate ledger, `project_config.yaml`, `gates.yaml`, a
  profile or `CLAUDE.md`; never invokes `aitask_*.sh`; never commits).
- Named follow-up (not v1): flipping `ait engine home --migrate` to the setup
  default (reserving `--no-home-migration` / `AIT_HOME_MIGRATE=0`).

## Deviations from the proposal

None requires a proposal edit. Recorded so the children do not re-derive them:

1. **Doc-file ownership — Module Map wins.** The *Binary distribution
   (M1.3, M1.4)* component text lists `CLAUDE.md` Engine block,
   `packaging_strategy.md` paragraph and `test_aitasks_home.sh` under its
   "Docs/Tests", but the Module Map's *owns* column assigns the first two to
   M1.5 and the test to M1.1. The Module Map is the cut ("the files it
   owns"); the component sentence describes the feature's docs, not
   ownership. Children follow the owns column.
2. **Permission touchpoints are the first skill consumer's, not M1's.**
   `aitask_testmap.sh` / `aitask_engine.sh` are invoked by no skill in M1, and
   `aitasks_extension_points.md` forbids dead-weight whitelist entries. The
   five-touchpoint checklist is owed by the first skill that calls
   `ait testmap` / `./.aitask-scripts/aitask_testmap.sh` (M6.5 / M8.3 / M9.3 —
   the proposal already assigns M5.1 its own "five permission touchpoints").
   Post-approval: send a note to t1857, t1859 and t1860 stating this.
3. **Go toolchain line.** The proposal says "Go 1.26 with a pinned
   toolchain"; the dev host has go1.27.0. M1.2 decides the `go` / `toolchain`
   directives at its reality check (≥ 1.26, ideally the current stable) — a
   value in a plan, not a proposal change.
4. **Setup is a shared pre-existing file with three M1 writers.** Not a cut
   error (M1.5 is the named owner of the two new functions); M1.1 and M1.6
   land one-line extensions. Stated above so no child claims the whole file.
5. **Trail caveat is stale.** The trail `art:trail-testmap-feature` says the
   proposal is untracked; it was committed in `cac8a6448`. No action for M1;
   the trail refresh (`/aitask-trail --refresh trail-testmap-feature --deep`)
   after all coarse passes picks it up.
6. **Go source directory renamed `engine/` → `goengines/` (proposal fix,
   user decision at this pass).** "engine" is ambiguous and more distributable
   Go executables are expected. Chosen layout: **one Go module** at
   `goengines/` (module path `github.com/beyondeye/aitasks/goengines`), one
   executable per `goengines/cmd/<name>/` (`cmd/ait-testmap` now), the
   cross-executable packages `gitx`, `platform` and the line-protocol / exit
   helpers (`lineproto`) at `goengines/internal/`, and every testmap-specific
   package under `goengines/internal/testmap/<pkg>` (`registry`, `annot`,
   `deps`, `axes`, `changesurface`, `selectr`, `sched`, `runner`, `cost`,
   `feedback`, `stale`, `seed`, `onboard`, `brief`). Wherever the proposal
   writes `internal/<pkg>` for a testmap package it now means
   `goengines/internal/testmap/<pkg>`. Renamed with it: the CI workflow
   (`goengines-check.yml`, trigger `goengines/**`), the release job
   (`goengines`, `release needs: [plan, goengines]`), `go-version-file:
   goengines/go.mod`, the tarball-exclusion sentence, `build.sh` builds every
   `cmd/*`. **Unchanged:** the binary name `ait-testmap`, the per-user install
   dir `$AITASKS_HOME/engine/v<V>/`, the `ait engine` verb family,
   `aidocs/framework/go_engine.md`, and every line protocol. This is a cut
   change, so it is **fixed in the proposal** (post-approval step 0 below) —
   the ten source-dir references at proposal lines 680, 681, 1929, 1982–1988,
   2288, 3147, 3175, 3619 plus one path-convention paragraph in the *Go engine
   and CLI (M1.2)* component — and noted to t1853–t1860, whose owns cells name
   `internal/<pkg>` packages.
7. **M1.6 migration has no destination-collision rule (proposal contract
   gap, fixed in the proposal).** *Framework home report and migration verb
   (M1.6)* moves every present legacy entry into `$AITASKS_HOME` but defines
   no behaviour when `$AITASKS_HOME/<name>` already exists. It always will
   for `engine/` (M1.1's setup creates it), and a `mv` onto an existing
   directory **nests** the source inside it — possibly after earlier entries
   already moved. Fix carried into the proposal and the M1.6 child plan: a
   **preflight over every present legacy entry runs before any move**; if
   any destination exists the verb refuses with
   `HOME_SKIPPED:destination-exists:<name>` and moves nothing; the refusal
   list gains `destination-exists:<name>`; `tests/test_aitasks_home.sh`
   gains a case asserting both trees are byte-identical after the refusal.
   Chosen over merge/overwrite semantics because a refusal that names the
   entry is the simplest safe option and the user resolves the collision by
   hand once.
8. **M1.5 must own its installer integration (proposal owns-cell gap, fixed
   in the proposal).** M1.5's acceptance test drives a real
   `install.sh --dir <scratch> --local-engine <bin>`, but `install.sh`'s
   parser dies on any unknown option and, after sourcing setup with
   `--source-only`, calls only `install_global_shim`; `aitask_setup.sh::main()`
   parses only `--with-pypy/--with-chat/--with-dev`. Neither surface is in
   M1.5's owns cell, so the child would fail its own ownership check. Fix:
   the M1.5 owns cell gains "the `--local-engine` / `--engine-from-source` /
   `--no-testmap` / `--force-engine` flags in `install.sh` and in
   `aitask_setup.sh::main()`, and the `install_engine_binary` call after
   `install_global_shim` in `install.sh`" as a named extension of the
   installer; the *Engine install, upgrade and state report (M1.5)*
   component states the same.

## Child plan template (each `aiplans/p1852/p1852_<n>_<name>.md`)

Header per `planning.md` (child form: `Task:`, `Parent Task:`,
`Sibling Tasks:`, `Archived Sibling Plans:`, `Base branch: main`,
`Output branch: main`, no `Worktree:` — current-branch profile), then:

1. **Context** — the parent goal, this submodule's row, the wave, and the
   sentence: *"This coarse plan records what the proposal fixes for M1.<n>. It
   does not design internals against providers that do not exist yet; the
   Reality check below does that when this child is picked."*
2. **Proposal reading list** — the exact sections: Module Map `#### M1` row,
   the component subsection(s) tagged `(M1.<n>)`, *Architecture → The process
   boundary / Process map / Where state lives*, *Assumptions → Engine,
   distribution and install (M1)*, *Tradeoffs → Engine and distribution (M1)*,
   *The per-user root (M1)*, plus the framework rules
   (`aitasks_extension_points.md`, `shell_conventions.md`, `sed_macos_issues.md`
   for the bash children; `testing_conventions.md` for M1.2's bench harness).
3. **Owned files / provides / consumes** — from the table above, verbatim.
4. **Step 0 — Reality check (MANDATORY, before any code; outcome recorded in
   this plan file)** — the six numbered sub-steps from the parent task body §2:
   re-read the proposal rows; inspect the actual state of every provider on the
   merge target and name the task + commit that landed each; tabulate
   *proposal says / coarse plan says / repository has*; decide per difference
   (adapt / revise this plan / revise the proposal); send `/aitask-note` to
   every downstream child a difference breaks; re-confirm every file touched
   is owned here or lands as the owner's named extension. For M1.1 and M1.2
   (no providers) the check still runs against the *Repository reality
   anchors* table above — those anchors are claims, not facts, by the time
   the child is picked.
5. **Implementation steps (coarse)** — the scope cell expanded into ordered
   steps naming files; no internal design beyond what the proposal fixes.
6. **Verification / acceptance** — the component test list for this
   submodule:
   - M1.1: `tests/test_aitasks_home.sh` pins the default, the env override, and
     that no framework script of this feature names `~/.aitask/`; scaffold
     copy-list entry; `ait setup` prints `AITASKS_HOME:`.
   - M1.2: `go vet` + `go test ./...` green; `ait-testmap version` prints
     version/commit/contract; `version --json` prints `ENGINE:<path>`; every
     stub verb exits 64; `CONTRACT_MISMATCH` helper covered; fixture harness
     builds a synthetic `(t<id>)` history in `t.TempDir()`; bench harness
     fails on a 2× regression against a committed baseline.
   - M1.3: `goengines-check.yml` runs gofmt/vet/test/bench for `goengines/**`;
     `build.sh all` yields the four binaries + `SHA256SUMS.txt`; `release.yml`
     `goengines` job attaches them in both release steps with
     `release needs: [plan, goengines]`; VERSION guard, `release-packaging.yml`,
     nfpm untouched; `aidocs/framework/go_engine.md` build half written.
   - M1.4: `tests/test_testmap_shim.sh` covers every handshake tier including
     `ENGINE_MISSING` exit 3 and the dev-slot `<V>-dev+<sha>` rule with an
     `AITASKS_HOME` host; `tests/test_platform_detect.sh` covers the `uname`
     map; `ait testmap version` resolves through the shim.
   - M1.5: `tests/test_install_engine_binary.sh` drives a real
     `install.sh --dir <scratch> --local-engine <bin>` (so the installer's
     parser accepts the flag and its post-shim call reaches
     `install_engine_binary`) and asserts the `$AITASKS_HOME/engine/v<V>/`
     path, checksum refusal, `.dev` protection, `--force-engine`,
     `TESTMAP_BINARY:skipped` via both `--no-testmap` and
     `AIT_TESTMAP_FETCH=0`, and each `TESTMAP:` state; `ait setup
     --local-engine <bin>` accepted by `main()`; `.aitask-testmap/`
     gitignored; `ait engine build|test|cross|prune` smoke.
   - M1.6: migration cases in `tests/test_aitasks_home.sh` — every refusal
     reason **including `destination-exists:<name>` with a pre-created
     `$AITASKS_HOME/engine/`, asserting both trees byte-identical after the
     refusal and nothing moved**, the known-set move incl. `pypy_venv`, the
     trailing symlink, `HOME_MIGRATED:<n>` / `HOME_SKIPPED:<reason>`,
     idempotent re-run, and `ait engine home` report lines; setup prints
     `HOME_LEGACY:` when tenants exist and never migrates.
7. **Step 9 reference** — the shared post-implementation procedure
   (`task-workflow` Step 9) handles archival; current-branch profile, no merge.

## Post-approval sequence (this session, after `ExitPlanMode`)

0. Fix the proposal for Deviations 6, 7 and 8 in one edit of
   `aidocs/testing_engine/n014_explorer_006_proposal.md`: the ten source-dir
   references plus the path-convention paragraph in *Go engine and CLI
   (M1.2)* (6); the `destination-exists:<name>` refusal and the
   preflight-before-any-move sentence in *Framework home report and migration
   verb (M1.6)* and the M1.6 Module Map row (7); the installer flags and call
   in the M1.5 Module Map owns cell and the *Engine install, upgrade and state
   report (M1.5)* component (8). Commit path-scoped with
   `git commit -m "documentation: Rename the Go source dir to goengines/ and close two M1 contract gaps in the testmap proposal (t1852)" -- aidocs/testing_engine/n014_explorer_006_proposal.md`
   (the file is on `main`, not the task-data branch).
1. Externalize this plan: `aitask_plan_externalize.sh 1852 --force
   --profile aitasks/metadata/profiles/fast.yaml --no-worktree`; commit via
   `aitask_task_commit.sh -m "ait: Add plan for t1852" aiplans/p1852_….md`.
2. Create the six children (`aitask_create.sh --batch --commit --parent 1852
   --no-sibling-dep …`, heredoc descriptions carrying the Child Task
   Documentation Requirements sections), then set `depends:` per the table
   with `aitask_update.sh --batch 1852_<n> --deps "t1852_<m>,…"`.
3. Revert the parent: `aitask_update.sh --batch 1852 --status Ready
   --assigned-to "" --plan-approved-at ""`; `aitask_lock.sh --unlock 1852`.
4. Write the six child plans to `aiplans/p1852/` from the template; commit
   them together, naming every file.
5. Send notes: the touchpoint note (Deviation 2) to t1857, t1859, t1860; the
   `goengines/` path-convention note (Deviation 6) to t1853–t1860, citing the
   proposal commit from step 0; the **sequencing clarification** (Context:
   submodule-granular waiting, M1 implemented before M2 planned, all-ten-first
   is an upper bound) to t1853–t1861. Also correct the session memory
   `feedback_testmap_parents_in_strict_wave_order` (it over-generalizes to
   whole parents) — a memory write, outside plan mode.
5b. **Create the cross-linking pass task now** (the `after` mitigation
   `testmap_cross_linking_pass` would otherwise only be created at Step 8d,
   which this session never reaches because it stops at the child
   checkpoint): Batch Task Creation with `mode: parent`, name
   `testmap_cross_linking_pass`, type `chore`, priority `medium`, effort
   `low`, labels `testmap,task-planning,dependencies`, `followup_of: 1852`,
   `followup_kind: risk_mitigation`, description carrying the Part 3
   `## Origin` / `## Risk addressed` / `## Goal` shape and the two rules
   below verbatim.

   **Step 0 — completeness precondition (all-or-nothing, before any
   write).** `has-children` proves nothing here: it succeeds on any positive
   local file count, and `children_to_implement` grows incrementally during
   creation, so an interrupted or in-progress pass looks "decomposed". The
   task instead validates every prescribed submodule of every parent:
   - For each parent t1852–t1861 — resolved from **active or archived**
     records (`aitask_query_files.sh resolve <id>`, else `archived-task
     <id>`; `aitask_archive.sh` moves a finished parent and its children to
     `aitasks/archived/t<parent>/` and `aiplans/archived/p<parent>/`, and by
     the time this runs M1's are there) — parse its `## Submodules` table
     for the `**M<n>.<m>**` rows. For every row that is **not** marked
     `(cross-repo)`, require a child file whose stem carries `m<n>_<m>_` in
     `aitasks/t<parent>/` **or** `aitasks/archived/t<parent>/` (exactly one
     across both) **and** its plan file — `aitask_query_files.sh plan-file
     <parent>_<k>` (active) else `aiplans/archived/p<parent>/p<parent>_<k>_*.md`
     — containing the `Step 0 — Reality check` heading. An **archived** child
     with its archived plan is complete evidence (a landed provider), never
     `INCOMPLETE`.
   - For every row marked `(cross-repo)` (today M10.2–M10.5 in t1861),
     require the parent's plan file to carry the cross-repo decomposition
     record (`planning-cross-repo.md` Step 6: the `label | side | nominal
     parent | in-repo deps | cross-repo deps` table) with one entry naming
     that row and its target project as registered in `ait projects list`.
   - Any missing item → print `INCOMPLETE:t<parent>:M<n>.<m>:<reason>` for
     each, then stop with **no** dependency writes; re-pick when the
     remaining passes have landed.

   **Step 1 — graph check and repair, pending local rows only.** For every
   local row whose child is **pending** (active and not `Done`), check each
   "depends on" cell against a real `depends:` entry in the `t<parent>_<m>`
   form on that child and fill only the missing ones with
   `aitask_update.sh --batch <child> --deps "<current + missing>"`
   (`--deps` replaces the list — read it first). Archived or `Done`
   children are **never** updated: a landed provider's edges are history,
   and a dependency *on* an archived child is already satisfied, so it is
   neither added nor required. **M10.2–M10.5 are never
   repaired with local ids:** they live in their target repositories, are
   referenced with `<project>#<id>` notation, and depend on the framework
   release carrying M1–M9 reaching each target rather than on this
   repository's task ids (t1861 body, `cross_repo_references.md`). For them
   the task only checks that the cross-repo record names each row and that
   any already-created cross-repo task carries the project-qualified
   reference (`xdeps` + `xdeprepo`, both-or-neither) — mismatches are
   reported, never rewritten from here. Then check the module → task map in
   every parent body against the real parent ids, and refresh the trail
   (`/aitask-trail --refresh trail-testmap-feature --deep`). `depends: []`
   (a `depends:` on the parents would block it until they are *Done*, which
   is far too late; the precondition above is the real gate). Then
   write `| created: t<id>` on the plan's `testmap_cross_linking_pass` line,
   back-fill its `→ mitigation:` link, and commit the plan
   (`aitask_task_commit.sh -m "ait: Record mitigation witness t<id> for t1852" aiplans/p1852_….md`),
   so a later Step 8d run sees the witness and creates nothing.
6. Manual-verification sibling prompt; then the child checkpoint → **Stop
   here** (prescribed by the task body). Satisfaction feedback; end.

### Post-phase (risk mitigations)

1. [verify_child_plans_carry_reality_check] After step 4 writes the six child
   plans and before they are committed, run
   `grep -L 'Step 0 — Reality check' aiplans/p1852/p1852_*_*.md` and
   `grep -L 'does not design internals against providers that do not exist yet' aiplans/p1852/p1852_*_*.md`.
   Both must print nothing. A named file means that child plan is not
   implementing the parent as specified: fix it before the commit, never after.
2. [verify_child_dependency_graph] After step 2 sets `depends:`, run
   `./.aitask-scripts/aitask_ls.sh -v --children 1852 99` and read each
   child's `depends:` line back with `grep '^depends:' aiplans/../aitasks/t1852/t1852_*_*.md`.
   Expected exactly: `_1 []`, `_2 []`, `_3 [t1852_2]`, `_4 [t1852_1, t1852_2]`,
   `_5 [t1852_1, t1852_3, t1852_4]`, `_6 [t1852_1, t1852_5]`. Any other value
   is corrected with `aitask_update.sh --batch 1852_<n> --deps …` before the
   parent is reverted to `Ready`.

## Verification (of this planning pass)

- `./.aitask-scripts/aitask_ls.sh -v --children 1852 99` lists six children
  `Ready`, M1.1 and M1.2 unblocked, the rest blocked exactly per the table.
- Each `aiplans/p1852/p1852_<n>_*.md` contains a `Step 0 — Reality check`
  heading and the "does not design internals against providers that do not
  exist yet" sentence (a `grep -L` over the six files returns nothing).
- The parent is `Ready`, unassigned, unlocked, with
  `children_to_implement: [1852_1 … 1852_6]`.
- `ait ls -v 15` shows t1852 as "Has children".
- `ait ls --followup-kind risk_mitigation` lists `t<id>_testmap_cross_linking_pass`
  (`Ready`, `depends: []`), and the plan's `testmap_cross_linking_pass` line
  carries `created: t<id>`.
- The proposal commit from step 0 exists on `main` and
  `grep -c 'goengines/' aidocs/testing_engine/n014_explorer_006_proposal.md`
  is ≥ 10 while `grep -n '\`engine/' …` returns only per-user-root paths.

## Risk

### Code-health risk: low
- The pass writes only task/plan data on the task-data branch; no source file
  changes. Residual: a wrong `depends:` cell would mis-block a child ·
  severity: low (residual — addressed by inline post-phase
  verify_child_dependency_graph) · → mitigation: inline post-phase verify_child_dependency_graph

### Goal-achievement risk: medium
- The coarse plans are hypotheses written before any provider exists; a child
  implemented without executing its Reality check would build against the
  proposal's description instead of the tree · severity: low (residual — the
  heading and sentence are grep-verified by inline post-phase
  verify_child_plans_carry_reality_check; executing the step remains the
  child's obligation) · → mitigation: inline post-phase verify_child_plans_carry_reality_check
- Cross-parent edges (M2.1 / M2.3 / M3.1 / M5.1 / M6.1 → M1 children) are
  written by other parents' passes; if a later pass names a child by the
  wrong number, the graph silently unblocks work early · severity: medium ·
  → mitigation: testmap_cross_linking_pass

### Planned mitigations
- timing: post-phase | name: verify_child_plans_carry_reality_check | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — child plan lacking the mandatory Reality check | desc: grep every child plan for the Step 0 heading and the no-internals sentence before committing them
- timing: post-phase | name: verify_child_dependency_graph | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — a wrong depends cell mis-blocking a child | desc: read the six depends lines back and compare with the decomposition table before reverting the parent
- timing: after | name: testmap_cross_linking_pass | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: medium | addresses: goal-achievement — cross-parent edges named by the wrong child number | desc: after all ten parents are decomposed, check every "depends on" cell against a real depends entry and the module → task map against real ids, then refresh trail-testmap-feature with --deep (created in this session at post-approval step 5b, not at Step 8d, because this pass stops at the child checkpoint; the witness is written there)
