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

## Final Implementation Notes

- **Actual work done:** Three one-line patches, no production-code changes.
  1. `tests/test_init_data.sh` — `create_data_branch_setup()` now copies `lib/python_resolve.sh` alongside `lib/terminal_compat.sh` so sourcing `aitask_setup.sh --source-only` succeeds (previously failed at `aitask_setup.sh:15`).
  2. `tests/test_t644_branch_mode_upgrade.sh` — `tar czf` argument list now includes `packaging/` so `install_global_shim` (called from `install.sh:1059`) can find `packaging/shim/ait` instead of `die`-ing and aborting `install.sh` before `commit_installed_files` runs.
  3. `tests/test_t167_integration.sh` — same `packaging/` addition to its `tar czf` argument list.

  All 3 target tests now pass at full counts: `test_init_data` 30/30 (was 7/30), `test_t644_branch_mode_upgrade` 16/16 (was 8/16), `test_t167_integration` 17/17 (was 14/17). Adjacent regression sweep (test_init_data, test_t644_*, test_t167_*, test_task_push, test_brainstorm_cli, test_explain_context, test_migrate_archives) all green.

- **Deviations from plan:** None. The verify-mode plan rewrite anticipated all three patches and the precise insertion sites; implementation matched it line-for-line.

- **Issues encountered:** None blocking. The original task description's hypothesis that `install.sh` / `aitask_setup.sh` had lost the `committed to git` / `Update aitasks framework` strings was misleading — those strings are still present (`install.sh:826`, `856`, `862`; the version-tagged `Update aitasks framework to v${version}` at `install.sh:856`); they simply never executed because `install.sh` exited at `install_global_shim` `die`. Verify-mode caught this by tracing under `bash -x` against a reproduction repo before committing to a code patch.

- **Key decisions:**
  1. **Strategy 1 (fix tests only)** over Strategy 2 (touch production code). The t732_5 precedent is explicit: when production has correctly evolved (here: t623_1 shim extraction + t695_2/_4 python_resolve refactor) and tests have not caught up, fixing the tests is the in-scope minimum. Touching `install.sh` / `aitask_setup.sh` would have introduced unnecessary churn for behavior already correct in real-world (release-tarball) installs.
  2. **No helper extraction** — same rationale as t732_2/_5: two/three callers is below the bar. The eventual t734 (`test_scaffold_helper_for_fake_aitask_repo`) is the right home for the convergence; this task adds one more inline `cp` and one more `tar czf` arg.
  3. **Did not edit `install_script()` in `test_init_data.sh:110`** — that helper only copies `aitask_init_data.sh`, which sources only `terminal_compat.sh`. Adding `python_resolve.sh` there would be dead code. Restricted the patch to `create_data_branch_setup()`, the one helper that actually sources `aitask_setup.sh`.

- **Upstream defects identified:** None.

  The pre-existing `tar rzf "$TARBALL" .claude/skills/` and `tar rzf "$TARBALL" seed/` calls in both `test_t644_branch_mode_upgrade.sh:82-86` and `test_t167_integration.sh:90-94` silently fail (`tar: Cannot update compressed archives`) because `tar -r` doesn't support `.tar.gz`. The errors are swallowed by `2>/dev/null || true`, so `.claude/skills/` and `seed/` never make it into the test tarballs. **This is intentional**: the test scenarios assert "no skills/" and "no seed/" warnings (e.g., `[ait] No seed/profiles/ — skipping profile installation`), so the broken-`tar -r` failure is the test's de-facto way of building a "minimal" tarball. Not a defect, just an obscure idiom. Worth a comment in any future helper extraction (t734).

- **Notes for sibling tasks:**
  - **Pattern verified for both fronts:** ANY new test that scaffolds a fake `.aitask-scripts/lib/` and sources framework helpers MUST copy both `terminal_compat.sh` AND `python_resolve.sh` (and `aitask_path.sh` per t732_5). ANY new test that builds a synthetic upgrade tarball MUST include `packaging/`. Both rules collapse to "match what `release.yml` actually ships" — if a future test diverges from that list, expect a fresh time-bomb on the next refactor.
  - **For Cluster D (t732_4 — `test_codex_model_detect`, `test_gemini_setup`):** if either test scaffolds a fake `.aitask-scripts/lib/` or builds an upgrade-style tarball, re-check both rules above before debugging any other symptom.
  - **For t732_7 (full-suite verification):** when the full test suite is re-run for the parent's verification, the 3 tests fixed here should appear in the green list. If any regresses, the most likely cause is a new lib being sourced from `aitask_setup.sh` (rule 1) or a new path required by `install.sh` (rule 2).
