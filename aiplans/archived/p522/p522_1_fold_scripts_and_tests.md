---
Task: t522_1_fold_scripts_and_tests.md
Parent Task: aitasks/t522_encapsulate_fold_logic_in_scripts.md
Sibling Tasks: aitasks/t522/t522_2_update_claude_code_callers.md, aitasks/t522/t522_3_mirror_caller_updates.md
Archived Sibling Plans: aiplans/archived/p522/p522_*_*.md
Worktree: (none — profile fast, create_worktree=false)
Branch: main
Base branch: main
---

# Plan: t522_1 Fold scripts and tests

## Context

First child of t522. Ships the three new bash scripts that the later children will adopt: `aitask_fold_validate.sh`, `aitask_fold_content.sh`, `aitask_fold_mark.sh`. Also refactors two helper functions out of `aitask_archive.sh` into `lib/task_utils.sh` for sharing, and adds three test files mirroring the existing fold-test scaffolding.

This child does **not** touch any SKILL.md or procedure file. Existing callers continue to run the prose procedures until t522_2. That decoupling means this child can land independently and be reverted without cascading breakage.

See parent plan `aiplans/p522_encapsulate_fold_logic_in_scripts.md` and the task description `aitasks/t522/t522_1_fold_scripts_and_tests.md` for the full context, decision log, and fully fleshed-out script skeletons.

## Implementation

### Step 1 — Move `read_yaml_field` / `read_task_status` into `lib/task_utils.sh`

1. Open `.aitask-scripts/lib/task_utils.sh` and add the two functions after `parse_yaml_list()` (~line 109). Copy verbatim from `.aitask-scripts/aitask_archive.sh:170-200`, preserving the section headers.
2. Grep to confirm no other script redefines these names: `grep -rn 'read_yaml_field\|read_task_status' .aitask-scripts/`. Only `aitask_archive.sh` should match.
3. Delete the local definitions from `.aitask-scripts/aitask_archive.sh` (lines 170-200, including the two `# --- Helper ...` headers). `task_utils.sh` is already sourced at the top of `aitask_archive.sh`, so the shared versions take over with zero caller changes.
4. Run `bash tests/test_archive_folded.sh` to confirm no regression.

### Step 2 — `aitask_fold_validate.sh`

Follows the structured-output convention used by `aitask_query_files.sh`. See the full skeleton in the task description.

Key portability points (per CLAUDE.md):
- `set -euo pipefail`
- Source `lib/terminal_compat.sh` and `lib/task_utils.sh` via `SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"`.
- Use `wc -l | tr -d ' '` when comparing counts as strings.
- Use `ls ... 2>/dev/null | head -1 || true` for file globbing.
- Always exit 0; callers parse the lines.

### Step 3 — `aitask_fold_content.sh`

Uses `awk` for frontmatter-stripping (no GNU-only sed features). Supports two input modes: positional `<primary_file>` for existing-primary callers and `--primary-stdin` for create-during callers (aitask-explore, aitask-pr-import, aitask-contribution-review).

Output format must match `task-fold-content.md` exactly (preserves the same `## Merged from t<N>: <name>` and `## Folded Tasks` sections) so callers relying on the old prose can't tell the difference.

### Step 4 — `aitask_fold_mark.sh`

Mirrors `task-fold-marking.md` step-by-step. Uses `task_git` (not raw `git`) so branch-mode task-data worktrees work. Uses `aitask_update.sh --batch ... --silent` for all frontmatter writes (not direct sed).

Transitive handling: read `folded_tasks` of each new folded task; if any, collect their IDs and also update their `folded_into` to point at the primary. Controlled by `--no-transitive` flag (default: transitive on).

Step 4b (child task parent cleanup): for each new folded ID matching `^([0-9]+)_([0-9]+)$`, call `aitask_update.sh --batch <parent_part> --remove-child t<id> --silent`.

Commit modes:
- `fresh` — stage `aitasks/`, commit with `ait: Fold tasks into t<primary>: merge t<id1>, t<id2>, ...`, emit `COMMITTED:<short_hash>`.
- `amend` — stage `aitasks/`, `commit --amend --no-edit`, emit `AMENDED`.
- `none` — emit `NO_COMMIT`.

### Step 5 — Tests

Use `tests/test_archive_folded.sh` as the scaffolding reference: bare remote + working clone setup, `assert_eq` / `assert_contains` / `assert_file_exists` helpers, `CLEANUP_DIRS` array, PASS/FAIL counters, per-test `setup_*` / `teardown` functions, final summary with exit code.

**`tests/test_fold_validate.sh`:**
- Valid parent → `VALID:<id>:<path>`
- Valid child → `VALID:<parent>_<child>:<path>`
- Missing → `INVALID:<id>:not_found`
- Status `Implementing` → `INVALID:<id>:status_Implementing`
- Parent with pending children → `INVALID:<id>:has_children`
- `--exclude-self <id>` → `INVALID:<id>:is_self`
- Batch of 4 IDs → 4 output lines in request order

**`tests/test_fold_content.sh`:**
- Positional `<primary_file>` form → correct merged body
- `--primary-stdin` form → same body when stdin matches primary's body
- Filename parsing: `t12_simple.md`, `t16_2_child.md`, `t100_multi_word_name.md`
- Frontmatter correctly stripped
- `## Folded Tasks` section references each folded task with filename

**`tests/test_fold_mark.sh`:**
- Setup: bare remote + clone + primary task + 2 folded parents + 1 folded child
- `--commit-mode fresh <primary> <p1> <p2> <child>` → assert primary `folded_tasks` contains all 3 IDs, folded tasks have `status: Folded` and `folded_into: <primary>`, child removed from its parent's `children_to_implement`, commit exists with expected subject
- `--commit-mode none` → assert no new commit
- Transitive: fold task A (where A has `folded_tasks: [X, Y]`) → assert X and Y get `folded_into: <primary>`

### Step 6 — Make executable and commit

```bash
chmod +x .aitask-scripts/aitask_fold_validate.sh .aitask-scripts/aitask_fold_content.sh .aitask-scripts/aitask_fold_mark.sh
git add .aitask-scripts/aitask_fold_validate.sh \
        .aitask-scripts/aitask_fold_content.sh \
        .aitask-scripts/aitask_fold_mark.sh \
        .aitask-scripts/lib/task_utils.sh \
        .aitask-scripts/aitask_archive.sh \
        tests/test_fold_validate.sh \
        tests/test_fold_content.sh \
        tests/test_fold_mark.sh
git commit -m "chore: Add fold helper scripts with shared read_yaml_field (t522_1)"
```

## Verification

1. `shellcheck .aitask-scripts/aitask_fold_*.sh` — lint clean.
2. `bash tests/test_fold_validate.sh` — all PASS.
3. `bash tests/test_fold_content.sh` — all PASS.
4. `bash tests/test_fold_mark.sh` — all PASS.
5. `bash tests/test_archive_folded.sh` — still passes (regression check on the `read_yaml_field` move).
6. Manual smoke: create two scratch task files in `/tmp`, run each of the three new scripts against them, verify output format matches the spec.

## Notes for sibling tasks (t522_2, t522_3)

- Script interfaces are locked once this child ships. If t522_2 discovers an interface gap, split into a t522_1_1 follow-up or bundle a script edit into t522_2 rather than silently diverging.
- `read_yaml_field` / `read_task_status` now live in `lib/task_utils.sh` — safe to use from any new script or shell code.
- `handle_folded_tasks()` in `aitask_archive.sh` was intentionally left alone; do not refactor it in t522_2 or t522_3.

## Final Implementation Notes

- **`aitask_fold_validate.sh` — child-counting under `set -euo pipefail`.** Original draft used `ls "$TASK_DIR"/t"${id}"/*.md 2>/dev/null | wc -l | tr -d ' '`. When the child directory does not exist, `ls` fails and `pipefail` propagates the failure, causing silent script exit. Replaced with `shopt -s nullglob` + bash array (`child_matches=( "$TASK_DIR"/t"${id}"/*.md )`), which is glob-native and safe under strict mode.
- **`tests/test_archive_folded.sh` pre-existing breakage.** The regression test is broken independently of this task: its `setup_project` scaffolding copies `task_utils.sh` but not `archive_utils.sh` (added in t433_7) or `agentcrew_utils.sh` (sourced by `aitask_archive.sh`). Additionally, `task_utils.sh:329` has a `local archive_path tar_match` declaration that trips `set -u` when `archive_path` is empty. Verified baseline (pre-t522_1) also fails silently. **Not fixed** — out of scope for a script-move task. Instead, verified `read_yaml_field`/`read_task_status` via direct smoke-test: sourced `lib/task_utils.sh` in a subshell, called both helpers against a scratch task file, confirmed identical output to the pre-move behavior.
- **Shellcheck.** Exit 1 without flags due to SC1091 (not following sourced libs) and SC2012 (use find instead of ls) — both info-level, both match patterns already accepted throughout `.aitask-scripts/`. Clean under `--severity=style`.
- **All three new test suites pass:** `test_fold_validate.sh` 7/7, `test_fold_content.sh` 16/16, `test_fold_mark.sh` 26/26 (49 assertions total).
