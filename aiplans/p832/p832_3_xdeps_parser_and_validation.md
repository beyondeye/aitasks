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

(To be filled by the implementing agent during/after execution.)
