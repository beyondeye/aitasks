---
Task: t732_3_cluster_c_branch_mode_and_upgrade_commit.md
Parent Task: aitasks/t732_fix_failing_pre_existing_test_suite.md
Sibling Tasks: aitasks/t732/t732_4_cluster_d_external_tool_drift.md, aitasks/t732/t732_6_cluster_f_codemap_help_text.md, aitasks/t732/t732_7_verify_full_suite_zero_failures.md
Archived Sibling Plans: aiplans/archived/p732/p732_1_cluster_a_textual_tui_api_drift.md, aiplans/archived/p732/p732_2_cluster_b_python_resolve_version_comparison.md, aiplans/archived/p732/p732_5_cluster_z_test_scaffold_missing_aitask_path.md
Worktree: (current branch — fast profile sets create_worktree:false)
Branch: (current branch)
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-04 23:23
---

# p732_3 — Cluster C: branch-mode + upgrade-commit regressions (verified)

## Goal

Make 3 tests green: `test_init_data.sh`, `test_t644_branch_mode_upgrade.sh`, `test_t167_integration.sh`. Both sub-issues turn out to be **test-side scaffolding misses** triggered by recent production-code changes — exactly the same time-bomb pattern as t732_5/t734.

## Verified diagnosis (2026-05-04)

The original plan's hypotheses were **partially correct on origin (t623_1 + t695_2/3 area) but wrong on remediation**: the production code is fine; the tests are stale. No `aitask_setup.sh` / `install.sh` change is needed. Verification details below for each sub-issue.

### Sub-issue (a) — `test_init_data.sh` (1 root cause; 23/30 failures cascade)

`tests/test_init_data.sh:119-134` — `create_data_branch_setup()` copies `aitask_setup.sh` + `lib/terminal_compat.sh` into the scratch repo, then sources `aitask_setup.sh --source-only` to call `setup_data_branch`. Sourcing fails on `.aitask-scripts/aitask_setup.sh:15`:

```bash
source "$SCRIPT_DIR/lib/python_resolve.sh"   # added by t695_2 / t695_4
```

The scaffold never copies `python_resolve.sh`, so `setup_data_branch` is never defined, the data-branch worktree + symlinks are never created, and every subsequent assertion that depends on those symlinks (Tests 2–8) cascades to `NO_DATA_BRANCH`.

This is the canonical t732_5/t734 time-bomb pattern, surfaced by `set +euo pipefail` (line 136) suppressing the source error. Direct evidence in the failing-test output: `… aitask_setup.sh: line 15: …/lib/python_resolve.sh: No such file or directory`.

**Same scope as t732_5's lessons** (notes-for-sibling-tasks: "any new test that scaffolds a fake `.aitask-scripts/lib/` MUST include `aitask_path.sh` and `python_resolve.sh` until t734 lands").

### Sub-issue (b) — `test_t644_branch_mode_upgrade.sh` + `test_t167_integration.sh` (1 shared root cause; 11 failures across both)

The bug is one missing path in both test tarballs. After t623_1 (`d627c0f5` — extract global shim), `install.sh:1058-1059` does:

```bash
source "$INSTALL_DIR/.aitask-scripts/aitask_setup.sh" --source-only
install_global_shim
```

and `install_global_shim` now requires `packaging/shim/ait` (`aitask_setup.sh` `install_global_shim` body):

```bash
local shim_src="$SCRIPT_DIR/../packaging/shim/ait"
[[ -f "$shim_src" ]] || die "Cannot locate shim source ($shim_src)"
cp "$shim_src" "$SHIM_DIR/ait"
```

Both test tarballs (t644 lines 71-87, t167 lines 75-95) build their archive with:

```bash
tar czf "$TARBALL" .aitask-scripts/ aitasks/metadata/labels.txt … ait
# then optional .claude/skills/ + seed/ via `tar rzf` (silently fails on .gz, ignored)
```

— `packaging/` is **not in the list**, so the tarball lacks `packaging/shim/ait`. On the test's upgrade `bash install.sh --force --dir … --local-tarball …`, `install_global_shim` calls `die`, `set -euo pipefail` aborts `install.sh` with `exit 1`, and `commit_installed_files` / `commit_installed_data_files` never run. Hence:

- `t644` Scenario A (branch-mode): no master commit (`A2/A3/A4/A5/A6/A9` fail).
- `t644` Scenario C (legacy mode): no legacy commit (`C2/C3` fail).
- `t167` Scenario A: `commit_installed_files` never reaches the sentinel-skip notice (`A1` fails).
- `t167` Scenario D: `commit_installed_files` never reaches the upgrade-commit path (`D1/D2` fail).

Direct evidence (captured under `bash -x` against a reproduction repo):

```
+ install_global_shim
+ local shim_src=…/.aitask-scripts/../packaging/shim/ait
+ [[ -f …/.aitask-scripts/../packaging/shim/ait ]]
+ die 'Cannot locate shim source (…)'
+ exit 1
```

Real-world (release-tarball) installs are unaffected — `release.yml` already includes `packaging/` per t623_1's plan Step 4. **Production code is correct; test tarballs are stale.**

#### Why the original plan's "missing `committed to git` / version-tagged commit message" hypothesis was wrong

The strings still exist verbatim:
- `install.sh:856` — `git commit -m "ait: Update aitasks framework to v${version}"`
- `install.sh:862` — `success "Framework update v${version} committed to git"`
- `install.sh:826` — `success "Framework files already committed to git (v${version})"`
- `install.sh:748` — `info "  .aitask-scripts/VERSION is not git-tracked — skipping auto-commit of framework update."`

They simply never execute because `install.sh` exits before reaching them. No `aitask_setup.sh` / `install.sh` patch is required.

## Strategy

**Strategy 1 (fix tests only)** — same precedent as t732_5. Production code is correct; only the test scaffolds need to catch up. Two surgical edits:

1. `tests/test_init_data.sh` — copy `python_resolve.sh` alongside `terminal_compat.sh` in `create_data_branch_setup()`.
2. `tests/test_t644_branch_mode_upgrade.sh` + `tests/test_t167_integration.sh` — add `packaging/` to each test's `tar czf` argument list.

No production code (`install.sh`, `aitask_setup.sh`, `aitask_init_data.sh`) is modified.

## Files to modify

- `tests/test_init_data.sh` (1 hunk, ~1 line added)
- `tests/test_t644_branch_mode_upgrade.sh` (1 hunk, 1 line added)
- `tests/test_t167_integration.sh` (1 hunk, 1 line added)

## Steps

### 1. Patch `tests/test_init_data.sh`

In `create_data_branch_setup()` (around line 124), add `python_resolve.sh` to the libs copied. Current:

```bash
mkdir -p "$repo_dir/.aitask-scripts/lib"
cp "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" "$repo_dir/.aitask-scripts/"
cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" "$repo_dir/.aitask-scripts/lib/"
cp -r "$PROJECT_DIR/seed" "$repo_dir/seed" 2>/dev/null || true
```

Add a single new line right after the `terminal_compat.sh` copy:

```bash
cp "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" "$repo_dir/.aitask-scripts/lib/"
```

`install_script()` at line 110 only copies `aitask_init_data.sh` (which sources only `terminal_compat.sh`) — no change needed there.

### 2. Patch `tests/test_t644_branch_mode_upgrade.sh`

Around line 73-87, append `packaging/` to the `tar czf` argument list. Current:

```bash
tar czf "$TARBALL" \
    .aitask-scripts/ \
    aitasks/metadata/labels.txt \
    aitasks/metadata/task_types.txt \
    aitasks/metadata/claude_settings.seed.json \
    aitasks/metadata/profiles/ \
    ait \
    2>/dev/null
```

After:

```bash
tar czf "$TARBALL" \
    .aitask-scripts/ \
    aitasks/metadata/labels.txt \
    aitasks/metadata/task_types.txt \
    aitasks/metadata/claude_settings.seed.json \
    aitasks/metadata/profiles/ \
    ait \
    packaging/ \
    2>/dev/null
```

The bumped tarball at line 178-189 is built by extracting `$TARBALL` then re-tar'ing the staging dir, so `packaging/` propagates automatically.

### 3. Patch `tests/test_t167_integration.sh`

Same one-line change at lines 79-86: append `packaging/` to the `tar czf` list.

The bumped tarball at line 207-212 also re-tars the staging dir, so `packaging/` propagates.

### 4. Verify each test

Run the three failing tests in isolation, then a localized regression sweep:

```bash
bash tests/test_init_data.sh
bash tests/test_t644_branch_mode_upgrade.sh
bash tests/test_t167_integration.sh

# Adjacent regression sweep (cluster-Z neighbors that may share scaffold patterns)
for t in tests/test_init_data.sh tests/test_t644_*.sh tests/test_t167_*.sh \
         tests/test_t644_branch_mode_upgrade.sh tests/test_task_push.sh; do
  bash "$t" >/dev/null 2>&1 && echo "PASS: $t" || echo "FAIL: $t"
done
```

Expected: all 3 target tests at full counts (`test_init_data` 30/30; `test_t644_branch_mode_upgrade` 16/16; `test_t167_integration` 17/17), no regressions.

### 5. Manual sanity smoke (optional)

Not required — production `install.sh` / `aitask_setup.sh` are untouched, so `./ait setup` and a real upgrade are unchanged. Skip.

## Verification

- `bash tests/test_init_data.sh` reports `30/30 pass` (was `7/30`).
- `bash tests/test_t644_branch_mode_upgrade.sh` reports `16/16 pass` (was `8/16`).
- `bash tests/test_t167_integration.sh` reports `17/17 pass` (was `14/17`).
- Adjacent sweep prints `PASS: …` for every test listed above.
- No production-code diff (`git diff -- install.sh .aitask-scripts/` is empty).

## Step 9 (Post-Implementation)

Per `task-workflow/SKILL.md` Step 9, archive via `./.aitask-scripts/aitask_archive.sh 732_3`. The parent t732 will auto-archive once all 4 remaining children are Done.

## Notes for sibling tasks

- **Confirms the t734 time-bomb pattern extends beyond `aitask_path.sh`.** `python_resolve.sh` is now also a routinely-required lib for any test that scaffolds a fake `.aitask-scripts/lib/` and sources `aitask_setup.sh` (or anything that transitively sources it). t732_5's note "tests should `source tests/lib/test_scaffold.sh` and call `setup_fake_aitask_repo`" once t734 lands is the right fix; this task just adds one more inline `cp` in the meantime.
- **Generalizes for upgrade-flow tests:** any new test that builds a synthetic upgrade tarball MUST include `packaging/` until/unless the helper extraction work captures this in a shared seeder. Worth a one-line note in the eventual `tests/lib/test_scaffold.sh` (t734) docstring.
- **Cluster D / F children should re-grep for any `tar czf … .aitask-scripts/ … ait` patterns** in their failing tests — same time-bomb if `packaging/` is missing.
