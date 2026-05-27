---
Task: t832_3_xdeps_parser_and_validation.md
Parent Task: aitasks/t832_brainstorm_cross_repo_skills_retrieval_xdeps_parallel_planni.md
Sibling Tasks: aitasks/t832/t832_*_*.md
Archived Sibling Plans: aiplans/archived/p832/p832_*_*.md (none yet)
Worktree: aiwork/t832_3_xdeps_parser_and_validation
Branch: aitask/t832_3_xdeps_parser_and_validation
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-27 17:11
---

# Plan: xdeps / xdeprepo parser + create/fold validation

See parent plan §t832_3 for the design.

## Goal

Introduce the `xdeps` (list) and `xdeprepo` (scalar) frontmatter fields
+ create/fold validation. Foundational for t832_4, t832_5, t832_8.

## Schema

```yaml
xdeps: [N, N_M, ...]   # task IDs in the cross-repo project's local format
xdeprepo: <name>       # scalar project name (must resolve via registry)
```

Both-or-neither. `Done`-only satisfaction semantics (enforced in t832_4).

## Implementation steps

1. **`aitask_ls.sh:222-251`** (`parse_yaml_frontmatter` case):
   ```bash
   xdeprepo)
       xdeprepo_text="$value"
       ;;
   xdeps)
       xdeps_text=$(parse_yaml_list "$value")
       xdeps_text=$(normalize_task_ids "$xdeps_text")
       ;;
   ```
   Add `xdeps_text=""` and `xdeprepo_text=""` to the reset block at
   lines 287-298 (`parse_task_metadata`).

2. **`lib/task_utils.sh`** — thin readers:
   ```bash
   read_xdeps() {
       local file="$1"
       local raw
       raw=$(read_yaml_field "$file" "xdeps")
       parse_yaml_list "$raw"
   }
   read_xdeprepo() {
       local file="$1"
       read_yaml_field "$file" "xdeprepo"
   }
   ```

3. **`aitask_create.sh`** — add `--xdeps "<csv>"` and `--xdeprepo <name>`
   batch flags. Mirror the existing `--deps` handling.

4. **`aitask_create.sh` validation:**
   - Both-or-neither: fail with clear error if only one is set.
   - `xdeprepo` resolves: `aitask_project_resolve.sh "$xdeprepo"`;
     die-with-hint on STALE / NOT_FOUND.
   - Each `xdeps` ID exists cross-repo: for each id,
     `aitask_query_files.sh task-file --project "$xdeprepo" "$id"`
     (from t832_1) — if `NOT_FOUND`, fail with the offending ID.

5. **`aitask_create.sh` frontmatter emission** (near lines 399 / 486 / 1444
   where `depends:` is written): emit `xdeps:` and `xdeprepo:` lines.
   Use `format_yaml_list` for `xdeps`. Omit both if `xdeps` is empty.

6. **`aitask_fold_validate.sh`** — when validating a fold, read folded
   task's `xdeps` / `xdeprepo`. If the primary task does not already
   carry the same `xdeprepo` and a superset of the folded `xdeps`, warn
   (do not block). Folding loses cross-repo deps silently otherwise.

## Tests

`tests/test_xdeps_parser.sh`:
- Synthesize a task file with `xdeps: [1, 2_3]` `xdeprepo: foo`.
- Run `aitask_ls.sh -v` and verify the depends column shows the local
  deps; verify `read_xdeps` / `read_xdeprepo` from task_utils.sh return
  the right values.
- Round-trip: read via parser, write back via aitask_update.sh (after
  any field changes), re-read and confirm `xdeps` / `xdeprepo` are
  preserved.

`tests/test_xdeps_validation.sh`:
- `aitask_create.sh --batch --xdeps "1,2" --xdeprepo a` (registered) → succeeds.
- `aitask_create.sh --batch --xdeps "1,2"` (no xdeprepo) → fails with both-or-neither.
- `aitask_create.sh --batch --xdeprepo a` (no xdeps) → fails with both-or-neither.
- `aitask_create.sh --batch --xdeps "1,999" --xdeprepo a` (999 does not exist) → fails with hint.
- `aitask_create.sh --batch --xdeps "1" --xdeprepo not_registered` → die-with-hint.

`tests/test_xdeps_fold_warn.sh`:
- Folded task carries xdeps that primary doesn't → fold validator warns.

## Verification

- `bash tests/test_xdeps_parser.sh` / `test_xdeps_validation.sh` /
  `test_xdeps_fold_warn.sh` all pass.
- `shellcheck` clean on touched scripts.
- TUI round-trip: create a task with `xdeps` / `xdeprepo`, open in `ait
  board`, change priority, save, confirm `xdeps` / `xdeprepo` are still
  present in the file (the audit confirmed `task_yaml.py` preserves
  unknown keys, but verify in practice).

## Notes for sibling tasks

- Variable names (`xdeps_text`, `xdeprepo_text` in `aitask_ls.sh`,
  `--xdeps` / `--xdeprepo` flags in `aitask_create.sh`) are load-bearing
  for t832_4 (blocking), t832_5 (parallel-planning emits these via
  create), t832_7 (cross-repo update of these fields), and t832_8
  (board display).

## Out of scope

- Blocking logic (t832_4).
- TUI display (t832_8).
- Cross-repo dep maintenance / repair (defer; surfaces in t832_6).

## Final Implementation Notes

- **Actual work done:**
  - `aitask_ls.sh`: added `xdeps)` / `xdeprepo)` case arms in
    `parse_yaml_frontmatter` (before closing `esac`) and `xdeps_text=""` /
    `xdeprepo_text=""` to the `parse_task_metadata` reset block.
  - `lib/task_utils.sh`: added `read_xdeps()` (returns normalized csv via
    `parse_yaml_list` + `normalize_task_ids`) and `read_xdeprepo()`
    (returns the scalar via `read_yaml_field`), placed next to
    `read_task_status()`.
  - `aitask_create.sh`: new globals `BATCH_XDEPS` / `BATCH_XDEPREPO`; new
    `--xdeps` / `--xdeprepo` flags in `parse_args()` and `show_help`; new
    `validate_xdeps_pair()` invoked right after the status validation;
    emission added at all 3 frontmatter heredoc sites (child, draft,
    parent) — fields emitted only when `BATCH_XDEPS` is non-empty.
  - `aitask_fold_validate.sh`: after `VALID:<id>:<file>` emission, when
    `--exclude-self` is provided, compares the foldee's `xdeps`/`xdeprepo`
    against the primary's and emits a non-blocking
    `WARNING:<id>:xdeps_loss:<repo>:<deps>` line if folding would drop
    cross-repo deps. Backward compatible — existing callers ignore
    unknown line types.
  - New tests: `test_xdeps_parser.sh` (5 assertions),
    `test_xdeps_validation.sh` (14 assertions),
    `test_xdeps_fold_warn.sh` (9 assertions). All pass.
  - Regression-verified: `test_fold_validate.sh`, `test_fold_content.sh`,
    `test_fold_mark.sh`, `test_create_project_flag.sh`,
    `test_create_silent_stdout.sh`, `test_create_manual_verification.sh`,
    `test_query_files_cross_repo.sh` all pass unchanged.
  - TUI round-trip verified end-to-end: PyYAML re-quotes the child IDs
    (`'2_3'`), but bash's `parse_yaml_list` strips quotes and
    `normalize_task_ids` re-attaches the `t` prefix, so `read_xdeps`
    returns the canonical `1,t2_3` after a board edit.
- **Deviations from plan:**
  - Plan step 4 said to validate xdeps existence via
    `aitask_query_files.sh task-file --project <name> <N>`. Switched
    to `task-status` (also added in t832_1) because `task-file` only
    accepts parent IDs (`<N>`) while `xdeps` may legitimately contain
    child IDs (`<N>_<M>`). `task-status` accepts both and emits a
    canonical `STATUS:NOT_FOUND` for missing ids; the validator
    accepts any `STATUS:<value>` (Ready, Implementing, Done, etc.) as
    existence proof.
  - Did NOT thread `BATCH_XDEPS` / `BATCH_XDEPREPO` through the 16-arg
    function signatures of `create_child_task_file`,
    `create_draft_file`, and `create_task_file`. Instead, the
    emission heredocs read the globals directly. Justification: the
    new fields are batch-only for v1 (interactive mode does not yet
    surface them per the plan's silent scope cut), and adding two
    more positional args to each signature plus all callers would
    have meant ~12 mechanical edits with high "wrong-slot" risk. The
    existing `BATCH_AUTO_MERGE` reads-via-global precedent justifies
    keeping the heredocs simple.
  - The fold-validator warning uses the existing `--exclude-self <id>`
    flag as the primary indicator (it is the only signal currently
    passed by all callers — `aitask_create.sh auto_merge` and the
    planning skill's ad-hoc fold), so the warning fires correctly
    without introducing a new flag. Callers that don't pass
    `--exclude-self` keep the strict VALID/INVALID-only contract.
- **Issues encountered:**
  - First `test_xdeps_parser.sh` run errored because sourcing
    `lib/task_utils.sh` from a test outside `.aitask-scripts/` made
    its `SCRIPT_DIR` self-default to `tests/`, which doesn't contain
    `lib/terminal_compat.sh`. Fixed by pinning `SCRIPT_DIR=
    $PROJECT_DIR/.aitask-scripts` in the test before sourcing.
  - The plan cited line numbers 222-251 (case block) and 287-298
    (reset block) in `aitask_ls.sh`. Pre-verification (in this
    session's verify pass) confirmed they had shifted to 224-268 and
    303-315 respectively. Anchors (`depends)` case and the
    `contributor_text=""` reset line) were used as insertion targets
    rather than the stale line numbers.
- **Key decisions:**
  - **`task-status` over `task-file` for existence check** — see
    deviations note above.
  - **`WARNING:` as new line type** in `aitask_fold_validate.sh`
    rather than promoting an `INVALID:xdeps_loss` (which would block
    fold). Spec says "warn, do not block"; existing callers only
    pattern-match `VALID:` / `INVALID:`, so unknown lines silently
    drop — backward compatible.
  - **Skipped scaffold update.** `lib/task_utils.sh` is not in
    `./ait`'s source-on-startup chain, so per CLAUDE.md the
    `tests/lib/test_scaffold.sh::setup_fake_aitask_repo` baseline
    does not need a copy of it. (The new tests source the lib from
    the real `.aitask-scripts/` via absolute path.)
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - **`BATCH_XDEPS` / `BATCH_XDEPREPO` are the canonical batch
    globals.** t832_5 (parallel-planning procedure) emits via
    `aitask_create.sh --batch --project <name> --xdeps ... --xdeprepo ...`
    and the flag spellings are now load-bearing. The validator at
    creation time refuses silently-broken plans, so the procedure
    can call create directly without separate validation.
  - **`xdeps_text` / `xdeprepo_text` in `aitask_ls.sh`** are the
    stable parser-output names. t832_4 will read them in
    `calculate_blocked_status()` to compute the cross-repo blocked
    flag. The reset block ordering matters only insofar as both
    must be reset for every task before parse — current placement
    after `contributor_text=""` satisfies that.
  - **t832_7 (`aitask_update.sh --project`) inherits the `WARNING:`
    line type.** If t832_7 ever wraps `aitask_fold_validate` behind
    a different caller (e.g. cross-repo fold), the same parsing
    contract — VALID / INVALID / optional WARNING — applies.
  - **t832_7 also owns the local-only `aitask_update.sh --xdeps` /
    `--xdeprepo` flag work** (administrative-edit subset). t832_3
    deliberately did not pre-add those flags so they can land in
    one PR alongside the `--project` cross-repo update + lock-check
    + status-allowlist orchestration that gives them their
    guardrails. There is no half-implemented local-only variant to
    rip out later.
  - **TUI round-trip preserves quoting.** `task_yaml.py` emits child
    IDs in xdeps as `'N_M'` (PyYAML's default for tokens with `_`),
    but every reader strips quotes, so the consumer-side
    normalization stays identical to local `depends:`. t832_8 should
    not need an xdeps-specific `_normalize_task_ids` call unless the
    goal is to canonicalize the on-disk representation to
    `t<N>_<M>` — currently quoted-raw is fine because every reader
    normalizes.
