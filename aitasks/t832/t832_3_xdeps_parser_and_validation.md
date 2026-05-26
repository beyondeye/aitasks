---
priority: medium
effort: medium
depends: [t832_1]
issue_type: feature
status: Ready
labels: [cross_repo, xdeps]
created_at: 2026-05-26 18:27
updated_at: 2026-05-26 18:30
---

## Context

Part of t832 brainstorm decomposition. Introduces the `xdeps` (cross-repo
dependencies) and `xdeprepo` (cross-repo dependency target project)
frontmatter fields and wires create/fold validation. This is the **shared
foundation** for t832_4 (blocking logic), t832_5 (parallel-planning
procedure), and t832_8 (board TUI surfacing).

## Schema (user-confirmed)

- `xdeprepo: <name>` — scalar; the cross-repo project (must resolve via
  the registry).
- `xdeps: [N, N_M, ...]` — task numbers in the regular local format,
  interpreted **inside `xdeprepo`**.

Both fields are required together (both-present or both-absent). The
scalar `xdeprepo` keeps parsing trivial; the flat `xdeps` list mirrors
local `depends:` so the mental model is identical.

## Key Files to Modify

- `.aitask-scripts/aitask_ls.sh:222-225` — `parse_yaml_frontmatter()`
  case statement: add `xdeprepo)` and `xdeps)` arms storing into new
  variables `xdeprepo_text` and `xdeps_text`. Reuse `parse_yaml_list`
  and `normalize_task_ids` from `task_utils.sh`.
- `.aitask-scripts/lib/task_utils.sh` — add thin readers:
  `read_xdeps` (wraps `read_yaml_field` + `parse_yaml_list`) and
  `read_xdeprepo` (wraps `read_yaml_field`).
- `.aitask-scripts/aitask_create.sh` — add `--xdeps "<csv>"` and
  `--xdeprepo <name>` batch flags. At validation site:
  - Both-or-neither check (fail if only one is provided).
  - `xdeprepo` resolves via `aitask_project_resolve.sh` (die-with-hint on
    STALE/NOT_FOUND).
  - Each `xdeps` number exists cross-repo via
    `aitask_query_files.sh task-file --project <name> <N>` (from t832_1).
  - Emit `xdeps:` and `xdeprepo:` lines in the generated frontmatter
    (near where `depends:` is emitted at lines 399 / 486 / 1444).
- `.aitask-scripts/aitask_fold_validate.sh` — when folding tasks, warn
  if the folded task carries `xdeps` / `xdeprepo` that the primary task
  does not also carry. (Folding should not silently lose cross-repo deps.)

## Reference Files for Patterns

- `lib/task_utils.sh:231 parse_yaml_list` and `lib/yaml_utils.sh:58
  read_yaml_field` — already handle the proposed shapes without changes.
- `aitask_ls.sh:222-251` — the existing case-based frontmatter parser
  the new arms mirror.
- `aitask_create.sh:399, 486, 1444` — where `depends:` is currently
  emitted; `xdeps:` / `xdeprepo:` follow the same pattern.

## TUI / Python Parser Audit (already confirmed clean)

The Plan agent that validated the t832 decomposition confirmed:
- `board/task_yaml.py:81` (`yaml.safe_load`) round-trips unknown keys via
  the "any new non-board keys" loop at `serialize_frontmatter:93`. New
  fields survive board edits.
- `monitor/monitor_app.py:1867` and `agentcrew/agentcrew_utils.py:62`
  only read specific keys; unknown keys are ignored.
- `aitask_ls.sh:parse_yaml_frontmatter` is a switched-case scanner;
  unknown fields drop silently.

**No TUI spillover work is required.** This task is genuinely contained.

## Implementation Plan

1. Add the case arms in `aitask_ls.sh:parse_yaml_frontmatter` and reset
   defaults near line 283-305.
2. Add `read_xdeps` and `read_xdeprepo` to `task_utils.sh`.
3. Add `--xdeps` and `--xdeprepo` flag parsing to `aitask_create.sh`
   (matches existing `--deps` handling).
4. Validate the pair at task-creation time (both-or-neither, repo resolves,
   IDs exist cross-repo).
5. Emit `xdeps:` and `xdeprepo:` in the generated frontmatter.
6. Extend `aitask_fold_validate.sh` to warn on cross-repo dep loss.

## Verification Steps

- New test files: `tests/test_xdeps_parser.sh` and `tests/test_xdeps_validation.sh`
  - Parser test: create a task file with `xdeps: [1, 2_3]` `xdeprepo: foo`,
    run `aitask_ls.sh -v` and verify the values are read correctly.
  - Validation tests:
    - Both-or-neither: only `xdeps` set → fail; only `xdeprepo` set → fail.
    - `xdeprepo` resolves: set to a registered project → pass; unregistered → fail with hint.
    - `xdeps` IDs exist cross-repo: set to existing IDs → pass; non-existent → fail.
- `shellcheck` clean on all modified scripts.
- Round-trip test: create a task with `xdeps:` / `xdeprepo:`, open in
  `ait board`, edit unrelated fields (e.g., priority), save, and verify
  `xdeps:` / `xdeprepo:` are preserved.

## Notes for sibling tasks

- t832_4 will extend `calculate_blocked_status()` in `aitask_ls.sh:256`
  to consume `xdeps_text` / `xdeprepo_text`. Names matter — keep these
  variable names stable.
- t832_5 (parallel-planning procedure) will emit `--xdeps` / `--xdeprepo`
  flags via `aitask_create.sh --batch --project`. The flag names defined
  here are load-bearing.
- t832_8 (board TUI) consumes the round-tripped fields directly from
  parsed frontmatter — no additional Python-side parser needed.

## Out of scope

- Blocking logic in `aitask_pick_own.sh` / `aitask_ls.sh` (owned by t832_4).
- TUI display (owned by t832_8).
- Cross-repo dep maintenance/repair (defer; surfaces in t832_6 retrospective).

See parent plan §t832_3 for the full design context.
