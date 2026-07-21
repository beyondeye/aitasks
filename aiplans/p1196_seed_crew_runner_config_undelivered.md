---
Task: t1196_seed_crew_runner_config_undelivered.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

# t1196 — Seed `crew_runner_config.yaml` on both delivery paths

## Context

`seed/crew_runner_config.yaml` was added by t386_3 (the AgentCrew runner) but
never wired into **either** of the two mutually exclusive delivery paths for
`aitasks/metadata/`:

1. `install.sh`'s `install_seed_*()` family (the tarball flow, which
   `rm -rf`s `seed/` afterwards), and
2. the source-tree flow —
   `populate_data_branch_seed_metadata()` + `ensure_agent_config_seeds()` in
   `.aitask-scripts/aitask_setup.sh`.

Meanwhile `aidocs/agentcrew/agentcrew_architecture.md:245` asserts *"The `ait
setup` command seeds this file from `seed/crew_runner_config.yaml`"* — untrue on
every install and clean clone.

t1194's drift guard (`tests/test_seed_manifest_drift.sh`) **cannot** catch this:
it compares the two manifests against each other, and a file absent from *both*
produces no drift. Hence a standalone fix.

**Verified before choosing a direction:** the runner degrades cleanly when the
file is absent. `resolve_config()`
(`.aitask-scripts/agentcrew/agentcrew_runner.py:122-143`) falls back to
`DEFAULT_INTERVAL = 30` / `DEFAULT_MAX_CONCURRENT = 3` (lines 70-71) — values
**byte-identical** to what the current seed file hardcodes. So seeding the file
verbatim would silently promote the seed to the effective default and turn those
two Python constants into dead code that can drift.

**Chosen outcome:** seed the file on both paths, but ship it as a *documented
template with both keys commented out*. Confirmed empirically in a scratch
fixture: `resolve_config(None, None)` returns `(30, 3)` both with the file absent
and with the commented template in place — `read_yaml()`
(`agentcrew_utils.py:60-64`) returns `{}` for a comment-only file, so the Python
constants remain the single source of truth while users get a discoverable knob
in `aitasks/metadata/`. The architecture doc's claim becomes true, and t1194's
guard keeps the two paths in sync from here on.

## Implementation

### 1. `seed/crew_runner_config.yaml` — rewrite as a commented template

Replace the whole file. No active keys; the comments *are* the payload.

```yaml
# Runner configuration for `ait crew runner` (the AgentCrew orchestrator).
#
# Both keys are commented out on purpose: with a key unset the runner uses its
# own built-in default, so `agentcrew_runner.py` stays the single source of
# truth for those values. Uncomment a key only to override it project-wide.
#
# Resolution order: CLI args (--interval / --max-concurrent) > this file >
# built-in defaults (interval: 30, max_concurrent: 3).

# interval: 30          # Seconds between runner iterations
# max_concurrent: 3     # Maximum agents running simultaneously (across all types)
```

### 2. `install.sh` — new installer, wired before the seed cleanup

Add `install_seed_crew_runner_config()` immediately after
`install_seed_chatlink_config()` (currently ends at line 521):

```bash
# --- Install AgentCrew runner config template (t1196) ---
# Copy-if-absent rather than merge_seed: the template carries NO active keys,
# so a --force `merge_seed yaml` would safe_dump an empty mapping and rewrite
# the file to a bare `{}`, destroying the documentation that is its entire
# purpose. Same shape as install_seed_doc_update_guide().
install_seed_crew_runner_config() {
    local src="$INSTALL_DIR/seed/crew_runner_config.yaml"
    local dest="$INSTALL_DIR/aitasks/metadata/crew_runner_config.yaml"

    if [[ ! -f "$src" ]]; then
        warn "No seed/crew_runner_config.yaml in tarball — skipping crew runner config installation"
        return
    fi

    if [[ -f "$dest" ]]; then
        info "  Crew runner config exists (kept): crew_runner_config.yaml"
        return
    fi

    cp "$src" "$dest"
    info "  Installed crew runner config: crew_runner_config.yaml"
}
```

Wire it in `main()` right after the chatlink installer (~line 1221) — i.e.
**before** `rm -rf "$INSTALL_DIR/seed"` (~line 1265), which t1194's Test 6/T9
position check enforces:

```bash
    info "Installing crew runner config..."
    install_seed_crew_runner_config
```

This is also what covers **tarball-installed projects**: `ait upgrade` downloads
the target version's installer and runs `bash install.sh --force`
(`.aitask-scripts/aitask_upgrade.sh:141-152`), so every upgrading repo receives
the file here — from a tarball that still has `seed/` at that moment.

### 3. `.aitask-scripts/aitask_setup.sh` — source-tree side

**3a.** Add one line to `populate_data_branch_seed_metadata()` (after the
`chatlink_config.yaml` copy, line 1631) — this is what restores manifest parity
and is the line t1194's guard derives:

```bash
    cp "$seed_dir/crew_runner_config.yaml" "$dest_dir/" 2>/dev/null || true
```

**3b.** Add a populate-missing pass next to `ensure_chatlink_config()` (which
ends at line 1607), modelled on it. Its scope is stated honestly in the comment:
`seed/` is deleted by `install.sh`, so this helper can only ever fire where
`seed/` survives — source-tree and clean-clone repos whose data branch predates
this change. It is **not** the repair path for tarball installs; §2 is.

```bash
# --- AgentCrew runner config (populate-missing, t1196) ---
# SOURCE-TREE / CLEAN-CLONE ONLY. install.sh deletes seed/ after its installers
# run, so on a tarball-installed repo this is a no-op by construction — those
# repos get the file from install_seed_crew_runner_config() on every
# `ait upgrade` (aitask_upgrade.sh runs install.sh --force). This pass exists
# for repos whose data branch was initialized before crew_runner_config.yaml
# joined the clean-init set, where re-running `ait setup` repairs it.
#
# Silent when neither file is present, unlike ensure_chatlink_config: the
# chatlink daemon refuses to start without its config, whereas the runner has
# working built-in defaults — warning on every seedless setup run would be pure
# noise.
ensure_crew_runner_config() {
    local project_dir="$SCRIPT_DIR/.."
    local seed_config="$project_dir/seed/crew_runner_config.yaml"
    local target_config="$project_dir/aitasks/metadata/crew_runner_config.yaml"

    [[ -f "$target_config" ]] && return
    [[ -f "$seed_config" ]] || return

    mkdir -p "$(dirname "$target_config")"
    cp "$seed_config" "$target_config"
    success "Created crew_runner_config.yaml"
}
```

Call it directly after `ensure_chatlink_config` (line 3508):

```bash
    ensure_crew_runner_config
```

**Known residual (accepted, recorded — not silently claimed as covered):** a
seedless tarball repo that deletes `aitasks/metadata/crew_runner_config.yaml`
cannot restore it with `ait setup` alone; it needs an `ait upgrade`.
`chatlink_config.yaml` has the identical hole today. The escape hatch, if this
ever matters, is t1147's pattern — a canonical reference under `.aitask-scripts/`
(cf. `gates_reference.yaml` + `install_seed_gates_registry`), which survives the
`seed/` cleanup. Out of scope here: it would change
`populate_data_branch_seed_metadata()`'s signature and therefore t1194's guard
call site, for a file whose absence costs nothing at runtime. Logged as an
upstream observation in the plan's Final Implementation Notes.

### 4. `aidocs/agentcrew/agentcrew_architecture.md` — make the doc true

Rewrite the *Runner Configuration* block (lines 234-245). The replacement, with
the outer fence widened so the inner ```yaml fence is unambiguous:

````markdown
### Runner Configuration

Stored in `aitasks/metadata/crew_runner_config.yaml`:

```yaml
# interval: 30          # Seconds between runner iterations
# max_concurrent: 3     # Maximum agents running simultaneously
```

**Resolution order:** CLI args (`--interval`, `--max-concurrent`) > config file >
built-in defaults (30s, 3).

`ait setup` and `install.sh` both seed this file from
`seed/crew_runner_config.yaml` with **both keys commented out**, so
`DEFAULT_INTERVAL` / `DEFAULT_MAX_CONCURRENT` in `agentcrew_runner.py` stay the
single source of truth until a key is uncommented.
````

The inner fence closes immediately after the two commented sample keys; the
prose that follows is normal body text. The file-table row at line 433 stays
as-is — still accurate.

### 5. `tests/test_crew_runner.sh` — pin the *content* contract

Manifest parity only proves both paths deliver a file **by name**. A future edit
that uncomments `interval:` / `max_concurrent:` would keep parity while
destroying the design (the seed would become the effective default again). Add a
Test 19 following the file's existing `$PYTHON` + `assert_eq` style:

```bash
# --- Test 19: shipped runner-config template is inert (t1196) ---
```

Two assertions:

- **The template defines no active override.** Parse
  `seed/crew_runner_config.yaml` and assert neither `interval` nor
  `max_concurrent` is present. **Coalesce before subscripting:** `yaml.safe_load`
  on a comment-only document returns `None`, not `{}` (verified against the
  actual template — `repr` is `None`), so a bare `.get()` would raise
  `AttributeError` and the test would fail *while the behavior it guards is
  correct*. Use the same coalescing the framework's own reader uses
  (`agentcrew_utils.read_yaml` does `data if isinstance(data, dict) else {}`):

  ```python
  cfg = yaml.safe_load(open("seed/crew_runner_config.yaml")) or {}
  assert "interval" not in cfg and "max_concurrent" not in cfg
  ```

  Guarding the seed guards both delivered copies, since `install.sh` and
  `populate_data_branch_seed_metadata()` both `cp` it verbatim. The assertion
  stays correct if the template later gains an unrelated active key — it checks
  for these two specifically, not for emptiness.
- **The delivered file does not change runner behavior.** Copy the template into
  a test repo's `aitasks/metadata/`, then assert
  `resolve_config(None, None) == (30, 3)` — the same tuple the *absent-file* path
  produces. This exercises the runner rather than the installer, so it cannot
  pass for the same reason the drift guard does.

Both are already confirmed working against live source in a scratch fixture
(`from agentcrew.agentcrew_runner import resolve_config` imports cleanly; the
module reads `CONFIG_FILE` relative to cwd, so the test `cd`s into the fixture;
and the comment-only parse returns `None`, hence the coalescing above).

## Verification

1. **Drift guard (parity oracle):** `bash tests/test_seed_manifest_drift.sh` —
   T2 must pass with `crew_runner_config.yaml` now in *both* derived manifests,
   and T6 must confirm the new installer is wired **before** the seed cleanup.
   Both manifests derive from live source.
2. **Content + behavior contract:** `bash tests/test_crew_runner.sh` — new Test
   19 (above) plus existing Test 8, which writes its own config with real values
   and must still resolve and honor CLI overrides.
3. **Lint:** `shellcheck install.sh .aitask-scripts/aitask_setup.sh`.
4. **Spot-check the setup path:** source `aitask_setup.sh --source-only` against
   a fixture and run `populate_data_branch_seed_metadata` + the new
   `ensure_crew_runner_config`; confirm the file lands, that a second run is a
   no-op (existing file kept, not overwritten), and that
   `ensure_crew_runner_config` returns cleanly with `seed/` absent.
5. **Doc render:** re-read the edited Runner Configuration section and confirm
   the prose after the yaml block is body text, not code.

## Risk

### Code-health risk: low
- `install.sh` is the tarball installer, so a defect there breaks fresh installs
  — but the change is additive and copies the shape of two existing installers
  (`install_seed_chatlink_config` for placement, `install_seed_doc_update_guide`
  for copy-if-absent semantics), and t1194's guard checks both its existence and
  its call *position*. · severity: low · → mitigation: none needed
- The deliberate deviation from `merge_seed yaml` is a third seeding idiom in
  `install.sh`. It is justified in-comment (a keyless template cannot be merged,
  only destroyed), and the idiom already exists in the file. · severity: low ·
  → mitigation: none needed
- `ensure_crew_runner_config()` cannot fire on seedless tarball installs. Scoped
  explicitly in its comment and recorded as a known residual above rather than
  claimed as coverage. · severity: low · → mitigation: none needed

### Goal-achievement risk: low
- None identified. The goal is a precise source/doc agreement, the direction was
  confirmed with the user, and both the parity and the content/behavior contracts
  are machine-checked.

## Step 9 (Post-Implementation)

Standard: merge approval, `./ait gates run 1196` (declared gate: `risk_evaluated`),
then `./.aitask-scripts/aitask_archive.sh 1196`.

## Post-Review Changes

### Change Request 1 (2026-07-21 12:35)

- **Requested by user:** Two blocking review concerns.
  1. *(tests)* Test 19 was added to `tests/test_crew_runner.sh`, but that
     script's footer reads a file-backed `COUNTER_FILE` that the shared
     `asserts.sh` helpers never write. It prints `FAIL:` lines and still exits
     0, so the new content/behavior contract was not pinned in automation.
  2. *(install flow)* `aidocs/framework/aitasks_extension_points.md` §"Test the
     full install flow for setup helpers" requires a setup helper touching
     `aitasks/metadata/` to be exercised through the real `install.sh → ait
     setup` flow, not a hand-crafted seed fed to the helper in isolation.
     Neither the new test nor t1194's drift guard (which SOURCES installer
     functions against a fixture that still has `seed/`) covered the real
     post-cleanup state.

- **Verification of the concerns:** both CONFIRMED against source.
  1. Reproduced directly: with a deliberately broken template,
     `bash tests/test_crew_runner.sh` printed `FAIL:` and still exited **0**.
     Root cause: `assert_eq` mutates shell-global `PASS`/`FAIL`, which are lost
     across the file's `( … )` subshells — the file-based counters that existed
     to survive subshells were orphaned by the t923 migration to shared
     `asserts.sh`. Pre-existing (reproduced at HEAD, before this task's change).
  2. The extension-points doc describes this exact situation verbatim: *"A
     helper that reads from `$project_dir/seed/...` will silently fail in a
     fresh user install even if it passes when tested against a hand-copied seed
     file."* That is `ensure_crew_runner_config()` precisely. This doc is
     mandated by CLAUDE.md for any `aitask_setup.sh` / install-flow edit and was
     not read during planning — a process miss, not just a test gap.

- **Changes made:**
  - Reverted `tests/test_crew_runner.sh` to HEAD (untouched by this task). Its
    broken exit path cannot pin anything, and fixing it properly means
    reworking 18 other tests' subshell/counter structure — out of scope, logged
    as an upstream defect instead.
  - Deleted the isolated `tests/test_setup_crew_runner_config.sh`.
  - Added `tests/test_crew_runner_config_delivery.sh` — one harness with a
    working `[[ $FAIL -eq 0 ]]` exit path and every assertion at top level:
    - **T1** content contract: the template declares no active
      `interval`/`max_concurrent` (coalescing `or {}`, since a comment-only
      document parses to `None`).
    - **T2** the REAL install flow: builds a local tarball, runs
      `bash install.sh --dir <scratch> --local-tarball <tb>` (~0.1s,
      network-free), asserts the file is delivered verbatim, asserts `seed/`
      was deleted (the seedless precondition every later leg depends on), then
      resolves `resolve_config(None, None)` against the **actually installed**
      file — `(30, 3)`, identical to the absent-file result — plus a negative
      control proving an uncommented key really does win.
    - **T3** the mandated `install.sh → ait setup` handoff, run against that
      genuinely seedless post-install repo: the helper is a clean no-op, never
      clobbers, survives an errexit caller, and the documented residual (with
      `seed/` gone it *cannot* restore a deleted config) is pinned as an
      assertion instead of prose.
    - **T4** the source-tree path and the data-branch initializer.
  - Corrected the T3a comment: reintroducing the bare `return` is caught by
    **T3c**, not T3a — when the target exists, `[[ -f x ]] && return` returns
    the successful test's status (0), so the first guard's `return 0` is
    defensive rather than load-bearing.

- **Regression proof (each failure mode reintroduced, suite must exit 1):**
  - uncommented key in the template → 3 failures, exit 1
  - bare `return` in `ensure_crew_runner_config` → T3c fails, exit 1
  - `install_seed_crew_runner_config` unwired from `main()` → T2 fails, exit 1

- **Files affected:** `tests/test_crew_runner_config_delivery.sh` (new),
  `tests/test_crew_runner.sh` (reverted to HEAD),
  `tests/test_setup_crew_runner_config.sh` (deleted, never committed).
