---
Task: t923_3_migrate_case_insensitive_files.md
Parent Task: aitasks/t923_consolidate_test_assert_helpers_shared_lib.md
Sibling Tasks: aitasks/t923/t923_1_*.md, aitasks/t923/t923_2_*.md, aitasks/t923/t923_4_*.md, aitasks/t923/t923_5_*.md
Archived Sibling Plans: aiplans/archived/p923/p923_1_*.md, aiplans/archived/p923/p923_2_*.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-03 13:55
---

# Plan: Migrate case-insensitive (`grep -qi`) files (t923_3)

Depends on 923_1/923_2 (both landed). **Read 923_1's plan for the API/recipe and
923_2's notes for batch refinements.** This plan reuses 923_1's proven
block-removal/source-insertion recipe and `assert_migration_verify.sh` harness
verbatim.

These files' inline matching is case-insensitive, so call sites map to the
shared **`assert_contains_ci` / `assert_not_contains_ci`** variants — **unless**
a needle audit shows otherwise (see the two-dimensional audit below).

## Verify-pass findings (2026-06-03 — re-checked against the current codebase)

- **Foundation present.** `tests/lib/asserts.sh` defines `assert_contains_ci`
  (line 85) and `assert_not_contains_ci` (line 96), both `grep -qiF` (fixed +
  case-insensitive, with the t920 `--` guard). `tests/lib/assert_migration_verify.sh`
  exists and is executable. Reuse both verbatim.
- **CI bucket = 30 files** (regenerated mechanically with 923_1's bucketing
  command). Reconciles exactly with 923_1's measured 33 minus the 3 ci files
  migrated in the pilot (`test_claim_id.sh`, `test_task_git.sh`,
  `test_agent_string.sh`). The 30: `test_brainstorm_cli.sh`, `test_codeagent.sh`,
  `test_crew_groups.sh`, `test_crew_init.sh`, `test_crew_report.sh`,
  `test_crew_runner.sh`, `test_crew_status.sh`, `test_crew_template_includes.sh`,
  `test_data_branch_migration.sh`, `test_data_branch_setup.sh`,
  `test_draft_finalize.sh`, `test_find_files.sh`, `test_global_shim.sh`,
  `test_lock_diag.sh`, `test_lock_force.sh`, `test_migrate_archives.sh`,
  `test_pr_contributor_metadata.sh`, `test_repo_fetch.sh`, `test_setup_git.sh`,
  `test_setup_git_tui.sh`, `test_skill_render.sh`, `test_skillrun_codex_planmode.sh`,
  `test_skill_template.sh`, `test_skill_verify.sh`, `test_t167_integration.sh`,
  `test_t644_branch_mode_upgrade.sh`, `test_task_lock.sh`, `test_version_checks.sh`,
  `test_web_merge.sh`, `test_zip_old.sh`. (Regenerate in Step 1 — don't trust a
  hardcoded list.)
- **FINDING C — the bucket is `grep -qi` (REGEX), not `grep -qiF` (fixed).**
  This is the key correction to the original plan's "casing-only" needle audit.
  **29 of the 30 files use plain `grep -qi`** (case-insensitive *regex*); only
  `test_migrate_archives.sh` uses `grep -Fqi` (case-insensitive *fixed*). But the
  lib's `_ci` variant is `grep -qiF` (**fixed**). So mapping a `grep -qi` file to
  `_ci` silently changes **regex → fixed-string**, which matters whenever a needle
  contains a BRE metacharacter (`.`, `*`, `[`, `^`, `$`, `\`). The needle audit
  must therefore be **two-dimensional** (casing × fixed/regex), not casing-only.
  See Step 2.
- **FINDING D — `assert_not_contains` regex downgrades are NOT harness-caught.**
  The before/after harness gates on FAIL-count + exit status. A regex→fixed
  downgrade on an `assert_not_contains` call **passes vacuously**: a literal
  needle that never appears in the output satisfies "not contains" regardless of
  whether the original anchored/regex form would have matched. So the count does
  not change and the harness stays green — while the assertion has silently lost
  its guarding power. `assert_not_contains` calls with regex needles MUST be
  mapped by **manual audit** to `_re` (or escaped), never validated by the
  harness alone. Concrete instance: `test_pr_contributor_metadata.sh:145`
  `assert_not_contains "No contributor field" "^contributor:" "$content_3"` — the
  `^` anchor means "no line *starting with* contributor:"; collapsing it to literal
  `^contributor:` would pass even if the frontmatter did contain a `contributor:`
  line, defeating the test.
- **FINDING E — two files have genuine regex needles; both map cleanly to `_re`.**
  A call-site scan for metacharacters found exactly two affected files, and in
  both, the needle's casing already matches the asserted output, so `-qi` was
  *not* load-bearing for casing — only the regex was. They map to the
  case-sensitive-regex variant `_re` (`grep -qE`), which preserves the
  metacharacter:
  - `test_lock_diag.sh` — 4 `assert_contains` calls (lines ~111–113, ~128) with
    `.*` wildcards: `"PASS.*Git available"`, `"PASS.*Origin remote"`,
    `"PASS.*Lock branch"`, `"FAIL.*Lock branch"`. The script emits `PASS:`/`FAIL:`
    and the labels "Git available"/"Origin remote"/"Lock branch" verbatim →
    casing matches → **`assert_contains_re`** (preserves `.*`).
  - `test_pr_contributor_metadata.sh:145` — `assert_not_contains "^contributor:"`;
    frontmatter keys are lowercase → casing matches → **`assert_not_contains_re`**
    (preserves the `^` anchor). (Per FINDING D, this one *must* be remapped by
    audit — the harness would not catch leaving it as literal.)
- **FINDING F — no `_ci`+regex ("both load-bearing") cases found, and no
  ci+regex lib variant exists.** The lib offers `_ci` (fixed, ci) and `_re`
  (regex, case-sensitive) but **no case-insensitive-regex** variant. In this
  bucket every regex-needle call's casing happens to already match its output, so
  `_re` suffices and no needle needs both. **Keep a guard anyway:** if a call
  surfaces during migration whose needle needs *both* case-insensitivity *and* a
  regex metacharacter, do NOT force it onto `_ci`/`_re` — either escape the
  metacharacter so `_ci` is exact, or leave that single call inline and flag it
  for 923_5 (synonyms/stragglers/final gates). Record any such case under
  "Upstream defects identified" / "Notes for sibling tasks".
- **FINDING G — bucket is structurally clean (no 923_2-style stragglers).** For
  all 30 files, `PROJECT_DIR` is defined *before* the inline `assert_contains`
  definition, and none combine `set -u` with a missing `TOTAL` initializer. So
  the `test_opencode_setup.sh` straggler hazard 923_2 hit (helpers defined before
  the dir var / `set -u` with no `TOTAL`) does **not** affect this bucket — the
  mechanical source-insertion recipe is safe for all 30.

## Step 1 — Regenerate the file lists

Use 923_1's bucketing command, CI branch (`echo` on the `-*i` match). Confirm the
count is 30 and matches the list above. Also regenerate the **regex-needle
sublist** (the files that need per-call `_re` handling) with a metacharacter
scan over `assert_contains`/`assert_not_contains` call sites (`.* [ ^ $ \`),
expecting `test_lock_diag.sh` and `test_pr_contributor_metadata.sh`. There are no
trimming-`assert_eq` files in this bucket to remap (verify with 923_2's trim
probe; expected empty).

## Step 2 — Migrate in verified batches (~10 files/batch → ~3 batches)

For each batch:

1. `tests/lib/assert_migration_verify.sh snapshot <baseline> <files...>`.
2. Per file (block-removal/insertion with the editor, **never `sed -i`**):
   - Insert `. "$PROJECT_DIR/tests/lib/asserts.sh"` anchored on the `PROJECT_DIR`
     line (right after the `test_scaffold.sh` source when present, else right
     after the inline `PROJECT_DIR=…`). FINDING G confirms this is safe for all 30.
   - Delete the inline defs the lib now provides (`assert_eq`, `assert_contains`,
     `assert_not_contains`, and any `assert_exit_*` / `assert_file_*` /
     `assert_dir_*` the file defines). **Keep** file-local `PASS=0/FAIL=0/TOTAL=0`,
     single-use/domain helpers, and synonym-named exit helpers (923_5's job).
   - **Two-dimensional call-site remap (FINDING C/D/E):** for each
     `assert_contains` / `assert_not_contains` call, decide on **two axes**:
     - **Casing load-bearing?** (could the needle match output of different case)
       and **regex metacharacter present?** (`.` `*` `[` `^` `$` `\`).
     - casing matters, no metachar → **`_ci`** (`grep -qiF`).
     - metachar matters, casing already matches output → **`_re`** (`grep -qE`).
     - neither matters → default `assert_contains` (`grep -qF`).
     - **both matter** → no variant (FINDING F): escape the metachar for `_ci`,
       or keep that call inline and flag for 923_5.
     - **When casing is in doubt and the needle is literal, prefer `_ci`** (it
       preserves the original `-qi` behavior). **When the needle has a metachar,
       you MUST decide regex-vs-fixed explicitly — do not default to `_ci`**, or a
       wildcard/anchor will be silently neutralized.
   - **`assert_not_contains` + regex needle (FINDING D): map by hand, not by
     harness.** Known: `test_pr_contributor_metadata.sh:145` → `assert_not_contains_re`.
   - Known `_re` remaps (FINDING E): `test_lock_diag.sh` 4 `assert_contains`
     `.*` calls → `assert_contains_re`.
3. `tests/lib/assert_migration_verify.sh check <baseline> <files...>` — FAIL count
   + exit status MUST be identical for every file. Investigate ANY delta before
   committing (a delta means a casing/regex behavior actually mattered → fix that
   call's variant). **Remember the harness blind spot (FINDING D):** a green check
   does NOT by itself prove an `assert_not_contains` regex needle was handled —
   confirm those by reading the remapped calls.
4. `shellcheck` a sample of the batch clean (modulo pre-existing info notes).
5. Commit the batch with plain `git`:
   `refactor: Consolidate case-insensitive assert helpers, batch N (t923_3)`.

## Step 3 — Verify

- Standalone FAIL-count + exit identical before vs after for every migrated file
  (the harness is the gate).
- Migrated files no longer define the consolidated helpers inline:
  `grep -rlE '^assert_contains\(\)' tests/` lists none of the 30 (only
  `tests/lib/asserts.sh`).
- No remaining inline `grep -qi` assert defs in migrated files.
- The regex-needle call sites resolved correctly: `test_lock_diag.sh` uses
  `assert_contains_re` for its `.*` calls; `test_pr_contributor_metadata.sh:145`
  uses `assert_not_contains_re`. Confirm by reading the diff, not just the harness.
- `shellcheck` clean on a sample.

## Risk

### Code-health risk: low
- Wide-ish blast radius (30 files), but each change is a pure, mechanical
  consolidation individually gated by the before/after harness (FAIL-count + exit
  must match). FINDING G confirms no structural stragglers in this bucket.
  · severity: low · → mitigation: in-task verify harness (923_1 deliverable), per batch.

### Goal-achievement risk: low
- **Regex→fixed semantic drift (FINDINGS C/D/E).** Mapping `grep -qi` (regex)
  call sites to `_ci` (`grep -qiF`, fixed) silently neutralizes regex
  metacharacters, and for `assert_not_contains` the harness does **not** catch the
  drift (vacuous pass). · severity: low (after mitigation) · → mitigation: the
  two-dimensional needle audit in Step 2 (casing × fixed/regex) with the `_re`
  escape hatch, the explicit by-hand audit of `assert_not_contains` regex needles,
  and the two concrete files pre-identified (FINDING E). The count harness backstops
  the `assert_contains` direction.
- **No ci+regex lib variant (FINDING F).** A call needing both case-insensitivity
  and a regex metacharacter has no exact target. · severity: low · → mitigation:
  none found in this bucket; Step 2 keeps an explicit guard (escape, or defer the
  single call to 923_5) should one appear.

_No before/after mitigation tasks: the principal risk (regex/casing semantic drift
across the bucket) is mitigated in-task by the two-dimensional audit + 923_1's
verification harness, re-run on every migrated file. Mirrors 923_1/923_2's framing._

## Final Implementation Notes (fill in)

Record: which files genuinely needed `_ci` vs were flavor-agnostic (default) vs
needed `_re`; the resolution of the `test_lock_diag.sh` / `test_pr_contributor_metadata.sh`
regex calls; any latent casing/regex bug surfaced; any ci+regex "both matter" call
deferred to 923_5.

## Step 9 (Post-Implementation)

Standard cleanup/archival/merge per `task-workflow` Step 9.
