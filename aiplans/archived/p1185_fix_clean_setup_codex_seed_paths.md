---
Task: t1185_fix_clean_setup_codex_seed_paths.md
Base branch: main
plan_verified: []
---

# t1185 — Fix clean-setup agent config seed paths

## Context

t1171 removed the `/plan` PTY injection from Codex skill launches. That change is
only safe because `ait setup` enables `default_mode_request_user_input = true` in
`.codex/config.toml` — without it, Codex cannot raise interactive prompts in
default mode. That flag lives in `seed/codex_config.seed.toml:8-9`.

t1180's live verification found the flag missing after a clean `ait setup`, and
did not archive. Root cause, confirmed during planning:

- `setup_codex_cli()` reads **only** `aitasks/metadata/codex_config.seed.toml`
  (`aitask_setup.sh:2067`) and `aitasks/metadata/codex_rules.default.rules`
  (`:2081`). Both are wrapped in `if [[ -f … ]]`, so a missing seed is a **silent
  no-op** — setup reports success while leaving the load-bearing flag unset.
- The clean data-branch initializer (`setup_data_branch()`, populate step at
  `:1339-1351`) is a hand-maintained list of literal `cp` calls. It never copies
  those two files. `codex_instructions.seed.md` survives only by riding an
  incidental glob, `cp "$project_dir/seed/"*_instructions.seed.md` (`:1347`) —
  that single accidental glob is the entire asymmetry described in the task.
- The same defect class affects `opencode_config.seed.json` (read at `:2218`) and
  `claude_settings.seed.json` (read at `:1807`); neither is in the clean-init list
  either.

Two corrections to the task's stated "Suggested fix":

1. **A reader-side `seed/` fallback is not sufficient.**
   `aidocs/framework/aitasks_extension_points.md:116` warns that `install.sh`
   deletes `seed/` at the end of install (confirmed at `install.sh:1153`), so any
   helper reading `$project_dir/seed/...` silently fails in a real install.
2. **Fixing only the clean-init list does not repair existing repos.** The
   populate step runs solely on first-time initialization; re-running `ait setup`
   on an already-initialized repo skips it. This repository is itself in that
   broken state today — its `aitasks/metadata/` contains none of the four seeds.

**Scope (confirmed with user, widened beyond the literal AC):** cover all four
agent config seeds, not just the two Codex ones. Identical defect, identical fix,
one shared manifest.

**Outcome:** every `ait setup` guarantees the agent config seeds are present in
`aitasks/metadata/`, repairing existing repos and fresh clean data branches alike,
without ever overwriting a user's customized copy.

## Approach

Add one **populate-missing** helper, `ensure_agent_config_seeds()`, modelled
directly on the two existing precedents in the same file —
`ensure_project_config_defaults()` (`:1556`) and `ensure_chatlink_config()`
(`:1606`). Both encode exactly this pattern and both carry comments noting the
`seed/` fallback matters for in-tree runs where `seed/` survives.

Deliberately **not** adding `cp` lines to the clean-init block at `:1339-1351`:
the new helper runs later in the same `ait setup` and already covers that case.
Duplicating the list into two places would create a drift hazard — one manifest
stays the single source of truth.

Reader sites (`:2067`, `:2081`, `:2218`, `:1807`) are left unchanged per the
scope decision; making their silent skips fail-loud is noted as a follow-up.

## Steps

### 1. Add `ensure_agent_config_seeds()` to `.aitask-scripts/aitask_setup.sh`

Insert immediately after `ensure_chatlink_config()` (ends at `:1626`), matching
its shape, comment style, and `local project_dir="$SCRIPT_DIR/.."` convention:

```bash
# --- Agent config seeds (populate-missing, t1185) ---
# install.sh installs these into aitasks/metadata/ directly (and deletes seed/
# afterwards), so in the normal tarball flow the targets already exist. This
# populate-missing pass matters for (a) source-tree / clean-clone runs where
# seed/ survives but aitasks/metadata/ was never populated, and (b) repos whose
# data branch was initialized before these seeds joined the clean-init set —
# re-running `ait setup` repairs them. Existing files are never overwritten.
ensure_agent_config_seeds() {
    local project_dir="$SCRIPT_DIR/.."
    local seed_dir="$project_dir/seed"
    local dest_dir="$project_dir/aitasks/metadata"

    [[ -d "$seed_dir" ]] || return 0

    # "<seed filename>:<metadata filename>" — the dest name differs for the
    # Claude settings seed; install.sh:582-583 applies the same rename.
    local pairs=(
        "codex_config.seed.toml:codex_config.seed.toml"
        "codex_rules.default.rules:codex_rules.default.rules"
        "opencode_config.seed.json:opencode_config.seed.json"
        "claude_settings.local.json:claude_settings.seed.json"
    )

    mkdir -p "$dest_dir"
    local pair src_name dest_name copied=0
    for pair in "${pairs[@]}"; do
        src_name="${pair%%:*}"
        dest_name="${pair##*:}"
        [[ -f "$seed_dir/$src_name" ]] || continue
        [[ -f "$dest_dir/$dest_name" ]] && continue
        cp "$seed_dir/$src_name" "$dest_dir/$dest_name"
        info "  Populated aitasks/metadata/$dest_name from seed"
        copied=$((copied + 1))
    done
    if [[ $copied -gt 0 ]]; then
        success "Populated $copied missing agent config seed(s)"
    fi
    return 0
}
```

Note the explicit `return 0` — the file runs under `set -euo pipefail`, so the
function must not end on a false test.

### 2. Wire the call site

In the main setup sequence, add after `ensure_chatlink_config` (`:3436`):

```bash
    ensure_agent_config_seeds
    echo ""
```

This slot is load-bearing and already proven by its neighbours: it runs **after**
`setup_data_branch` (`:3415`) has created `aitasks/` as a symlink into
`.aitask-data/`, **before** `setup_codex_cli` / `setup_opencode` (`:2246`,
`:2251`) read the seeds, and **before** `commit_framework_data_files` (`:3485`).
`aitasks/metadata/` is already a committed framework-data path
(`_ait_data_framework_paths`, `:2655`) and new files there are picked up as
untracked, so the populated seeds are committed to the data branch automatically —
no new commit logic required.

### 3. Add `tests/test_setup_agent_config_seeds.sh`

Follow the sanctioned scaffold from `tests/test_data_branch_setup.sh`: source the
setup script with `source "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh"
--source-only` (`:100`), then drive the function by setting `SCRIPT_DIR` to a
temp fixture. Use the shared helpers in `tests/lib/asserts.sh`.

Cases:

1. **Populate-missing** — fixture has all four files in `seed/`, empty
   `aitasks/metadata/`. Assert all four land, and that
   `claude_settings.local.json` arrives as `claude_settings.seed.json`.
2. **No-clobber** — pre-write `aitasks/metadata/codex_config.seed.toml` with
   sentinel content; assert it is byte-identical afterwards (user edits win).
3. **Partial seed dir** — only `codex_config.seed.toml` present; assert it is
   copied, the others are absent, and the function exits 0.
4. **No `seed/` dir** — assert exit 0 and no files created (the tarball-install
   path must not error).
5. **End-to-end ground truth** — build a codex fixture whose
   `aitasks/metadata/` is **not** hand-seeded, run `ensure_agent_config_seeds`
   then `setup_codex_cli`, and assert `.codex/config.toml` contains
   `default_mode_request_user_input = true`. Model the staging fixture on
   `create_codex_staging()` in `tests/test_agent_instructions.sh:283-304` —
   `setup_codex_cli` returns early at `:2007` unless
   `aitasks/metadata/codex_skills` exists.
6. **Negative control** — same fixture as (5) but skipping the
   `ensure_agent_config_seeds` call; assert `.codex/config.toml` does **not**
   gain `[features]`. This proves the assertion in (5) is caused by the fix and
   not by incidental fixture state.

Case 5 + 6 together are the regression that t1180 needed. The existing coverage
cannot catch this bug: `test_agent_instructions.sh` hand-writes
`codex_config.seed.toml` into metadata inside its fixture (`:283-304`), and
`test_opencode_setup.sh:86` does the same for OpenCode — both mask the very gap
this task fixes.

## Verification

```bash
bash tests/test_setup_agent_config_seeds.sh     # new
bash tests/test_data_branch_setup.sh            # regression (clean-init path)
bash tests/test_agent_instructions.sh           # regression (setup_codex_cli)
bash tests/test_opencode_setup.sh               # regression
bash tests/test_codex_no_plan_injection.sh      # t1171 structural guard
shellcheck .aitask-scripts/aitask_setup.sh
```

End-to-end repair proof (this repo is currently in the broken state, so it is a
live fixture — run it in a scratch clone, not in place):

```bash
git clone . /tmp/t1185-verify && cd /tmp/t1185-verify
./ait setup
test -f aitasks/metadata/codex_config.seed.toml && echo SEED_OK
grep -A1 '\[features\]' .codex/config.toml       # expect default_mode_request_user_input = true
```

Per `aidocs/framework/aitasks_extension_points.md:120-127`, also exercise the
full install flow rather than stopping at helper-level tests:

```bash
bash install.sh --dir /tmp/t1185-install
grep -r default_mode_request_user_input /tmp/t1185-install/.codex/config.toml
```

## Risk

### Code-health risk: low
- The change is purely additive: one new self-contained function plus one call
  line. No existing code path is modified, so nothing currently working can
  regress. · severity: low · → mitigation: none (accepted; severity low)
- The new helper introduces a second place (alongside `install.sh`'s
  `install_seed_*` family) that knows the seed→metadata filename mapping,
  including the `claude_settings.local.json` → `claude_settings.seed.json`
  rename. If a future seed is added to one manifest and not the other, the two
  drift silently. · severity: low · → mitigation: t1194 (seed_manifest_drift_guard)
- The reader sites left unchanged by this task still skip silently when a seed
  is absent, which is what let this bug pass setup undetected in the first
  place. · severity: low · → mitigation: t1195 (fail_loud_agent_seed_readers)
- Writing into `aitasks/metadata/` means the populated files are auto-committed
  to the data branch by `commit_framework_data_files`. That is the intended and
  already-proven behavior for this slot, but it does make `ait setup` produce a
  commit it did not previously produce. · severity: low · → mitigation: none (accepted; severity low)

### Goal-achievement risk: low
- The root cause is confirmed by direct source reading rather than inference —
  the reader paths (`:2067`, `:2081`), the clean-init `cp` list (`:1339-1351`),
  and the incidental `*_instructions.seed.md` glob (`:1347`) that explains the
  asymmetry were each read in place, and this repository reproduces the broken
  state. · severity: low · → mitigation: none (accepted; severity low)
- Residual: the fix depends on `seed/` being present at `ait setup` time. In a
  clean clone of a data-branch repo that ships no `seed/` directory, the files
  exist nowhere and no populate-missing pass can recover them. This is out of
  scope here; the structural answer is the t1147 pattern (promote the canonical
  copy under `.aitask-scripts/`, as was done for `gates_reference.yaml` at
  `:1357`). · severity: low · → mitigation: none (accepted; severity low)
- The end-to-end assertion is protected against false confidence by an explicit
  negative control (test case 6), so a passing suite cannot be produced by
  incidental fixture state — the failure mode that let this bug survive existing
  coverage. · severity: low · → mitigation: none (accepted; severity low)

### Planned mitigations
- timing: after | task: t1194 | name: seed_manifest_drift_guard | type: test | priority: medium | effort: low | addresses: code-health — dual-manifest drift | desc: Assert the seed→metadata filename mapping in install.sh's install_seed_* family and ensure_agent_config_seeds()'s pairs list stay in sync, so a seed added to one but not the other fails loudly.
- timing: after | task: t1195 | name: fail_loud_agent_seed_readers | type: enhancement | priority: medium | effort: low | addresses: code-health — silent no-op defect class | desc: Convert the silent [[ -f ]] skips at aitask_setup.sh:2067, :2081, :2218, :1807 into visible warnings so the next instance of this bug class self-reports instead of passing setup silently.

## Follow-ups (not in this task)

- The two confirmed mitigations above are created as independent "after" tasks
  at Step 8d, once this task's code has landed.
- Promoting the agent config seeds to a canonical copy under `.aitask-scripts/`
  (the t1147 pattern) was proposed and declined — the seedless-clone residual is
  accepted at severity low.
- After this lands, t1180 (`depends: [1185]`) can re-run its clean-setup step.

## Final Implementation Notes

- **Actual work done:** Added `ensure_agent_config_seeds()` to
  `.aitask-scripts/aitask_setup.sh` (after `ensure_chatlink_config()`, +59 lines)
  and wired it into `main()` after `ensure_chatlink_config`. It copies four agent
  config seeds from `seed/` into `aitasks/metadata/` only when absent, applying
  the `claude_settings.local.json` → `claude_settings.seed.json` rename that
  `install.sh` also applies. Added `tests/test_setup_agent_config_seeds.sh`
  (22 assertions). No existing code path was modified.

- **Deviations from plan:** One. The plan specified an unconditional
  `mkdir -p "$dest_dir"`. During verification I confirmed that `mkdir -p` **fails**
  through a dangling `aitasks/` symlink (`mkdir: cannot create directory: File
  exists`), which under `set -euo pipefail` would abort the entire `ait setup`
  run. It is unreachable in the current call order — the helper runs after
  `setup_data_branch` has materialized `.aitask-data/` — but an unconditional
  `mkdir` is a latent hard-abort. Changed to create the directory only when
  genuinely absent and to degrade to a `warn` + `return 0` if creation fails.
  Test 8 pins the behavior. Two further tests were added beyond the plan's six:
  Test 7 (data-branch symlink layout) and Test 8 (dangling symlink).

- **Issues encountered:**
  - The first `install.sh --local-tarball` run failed (`mkdir: cannot create
    directory 'aitasks': File exists`) because the hand-built tarball included
    the repo's `aitasks`/`aiplans` symlinks, which a real release tarball does
    not. Rebuilt the tarball with those excluded; install then succeeded (rc=0).
    Worth noting that `install.sh` has the same dangling-symlink exposure this
    task guarded against in `ensure_agent_config_seeds`, though it is not
    reachable via a genuine release tarball.
  - In that install fixture `setup_codex_cli` initially early-returned ("No Codex
    CLI staging files found") because the hand-built tarball lacked the packaged
    `codex_skills/` staging directory that the release workflow produces. Supplied
    the staging manually to exercise the merge path. Tarball artifact, not a
    product defect.

- **Key decisions:**
  - **Scope widened beyond the literal AC, with user confirmation:** covers all
    four agent config seeds (Codex config + rules, OpenCode config, Claude
    settings), not just the two Codex ones. Same defect, same fix, one manifest.
  - **Rejected the task's own suggested "fall back to `seed/` paths":**
    `aidocs/framework/aitasks_extension_points.md:116` and `install.sh:1153`
    confirm `install.sh` deletes `seed/` after install, so a reader-side fallback
    is a no-op for real installs.
  - **Rejected extending the clean-init `cp` list at `:1339-1351`:** it only fires
    on first-time initialization, so it would not repair already-initialized
    repos (this repository included). The populate-missing helper runs on every
    `ait setup` and covers both. Deliberately kept as a single manifest rather
    than duplicating the list into the clean-init block, to avoid drift.
  - Reader sites (`:2067`, `:2081`, `:2218`, `:1807`) left unchanged per the scope
    decision; the fail-loud conversion is queued as a mitigation task.

- **Verification performed:** New test 22/22. Regressions all green:
  `test_data_branch_setup` 70/70, `test_agent_instructions` all passed,
  `test_opencode_setup` 31/31, `test_codex_no_plan_injection` 29/29, plus
  `test_install_merge`, `test_data_branch_migration`, `test_setup_git`,
  `test_setup_verify_venv_imports`, `test_skill_verify`. `shellcheck
  aitask_setup.sh` holds at the 18-finding baseline (no new findings); the new
  test file has zero warnings/errors. Two end-to-end proofs: (a) reproducing this
  repo's real broken layout, the helper populated 3 seeds — correctly not
  clobbering the pre-existing `claude_settings.seed.json` — and `.codex/config.toml`
  then gained `default_mode_request_user_input = true`, landing on the data branch
  through the symlink; (b) a full `install.sh --local-tarball` run (rc=0) where
  `seed/` is deleted and the helper is a verified no-op (15 files → 15), after
  which `setup_codex_cli` merged `[features]` into the pre-existing
  `.codex/config.toml` while preserving the user's existing rules — the exact
  path t1180 reported as broken.

- **Upstream defects identified:**
  - `install.sh:338-344 — create_data_dirs() runs unguarded mkdir -p on aitasks/ and aiplans/, which fails ("File exists") when either is a dangling symlink, aborting the install under set -e. Same defect class as the one guarded in ensure_agent_config_seeds by this task. Observed with a hand-built tarball that included the repo's aitasks/aiplans symlinks; a genuine release tarball excludes them, so this is a latent robustness gap rather than a live user-facing failure.`

