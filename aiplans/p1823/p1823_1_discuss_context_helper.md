---
Task: t1823_1_discuss_context_helper.md
Parent Task: aitasks/t1823_brainstorm_discuss_proposals_interactive_agent.md
Sibling Tasks: aitasks/t1823/t1823_2_*.md, aitasks/t1823/t1823_3_*.md, aitasks/t1823/t1823_4_*.md, aitasks/t1823/t1823_5_*.md
Archived Sibling Plans: aiplans/archived/p1823/p1823_*_*.md
Base branch: main
Output branch: main
---

# t1823_1 — Discuss context helper (read-only id → path resolver)

## Context

The `aitask-brainstorm-discuss` skill (t1823_2) receives only ids on argv
(`<task_num> <node_id>...`) and must self-fetch paths. No existing CLI emits a
brainstorm session path or node proposal paths (`ait brainstorm status` prints
counts only; `init` creates a session). This child adds the read-only resolver,
in the mould of `aitask_shadow_context.sh`: `KEY:value` lines, **exit 0 on every
resolution outcome**, malformed id is the one hard error.

Parent plan: `aiplans/p1823_brainstorm_discuss_proposals_interactive_agent.md`.

## Steps

1. **`brainstorm_dag.py` — `get_node_ancestors(session_path, node_id) -> list[tuple[str, int]]`.**
   Do NOT reuse `get_node_lineage` (first-parent walk, confined to one module,
   default `_umbrella`: a synthesis node loses all but its first branch; a module
   node stops at its subgraph root). New pure function:
   - BFS from `node_id` over **all** `get_parents` edges, crossing module boundaries;
   - `visited = {node_id}`; a node is queued only if unseen → diamond ancestors
     emitted once at shortest depth, cycles (incl. back to the start) terminate;
   - a parent whose YAML is missing is still returned (guard `read_node` /
     `get_parents` with a try/except → treat as no parents);
   - sort result by `(depth, node_id)`; exclude the start node.
   `get_node_lineage` and its callers stay untouched.
2. **`brainstorm_cli.py` — `paths` subcommand**: `--task-num N`, `--lineage`,
   positional `node_id*`.
   - Validate `N` and every node id with `^[A-Za-z0-9_.-]+$`, reject `.` / `..`
     → stderr message, **exit 2** (also blocks path traversal).
   - `session = crew_worktree(N)`; not a dir → print `SESSION_PATH:NOT_FOUND`, exit 0.
   - `TASK_FILE:` from `load_session(N)["task_file"]` if the file exists, else `NOT_FOUND`.
   - node ids empty → all of `list_nodes(session)`.
   - per node: `NODE:<id>|PROPOSAL:<p|NOT_FOUND>|META:<p|NOT_FOUND>|PARENTS:<csv>`,
     paths via `file_for_ref(session, OpDataRef("node_proposal"|"node_metadata", id))`
     and an `is_file()` check.
   - `--lineage`: per requested node, per `get_node_ancestors` entry:
     `ANCESTOR:<node>|<ancestor>|DEPTH:<n>|MODULE:<label>|PARENTS:<csv>|PROPOSAL:<p|NOT_FOUND>`
     (`MODULE` from the node YAML `module_label`, `_umbrella` when absent).
   - Never write; never call `save_session` / `create_node`.
3. **`.aitask-scripts/aitask_brainstorm_context.sh`** — `#!/usr/bin/env bash`,
   `set -euo pipefail`; usage `[--lineage] <task_num> [<node_id>...]`; resolve
   python through `lib/python_resolve.sh`; exec
   `brainstorm_cli.py paths --task-num "$1" [--lineage] "${@:2}"`. Follow
   `aidocs/framework/shell_conventions.md`. No `ait` dispatcher entry.
4. **Permission touchpoints (5)**:
   `./.aitask-scripts/aitask_audit_wrappers.sh apply-helper-whitelist aitask_brainstorm_context.sh`
   then `audit-helper-whitelist aitask_brainstorm_context.sh` → 5/5. Mirror the
   entry into `aitasks/metadata/opencode_config.seed.json` (commit that one via
   `aitask_task_commit.sh`, by path, separately from code).
5. **Tests**
   - `tests/test_brainstorm_node_ancestors.py`: multi-parent synthesis (both branches
     present; `get_node_lineage` on the same fixture omits branch `b` — control);
     module-boundary ancestry (umbrella ancestors present, `MODULE` differs);
     diamond de-dup; hand-written cycle terminates; missing-parent YAML tolerated.
   - `tests/test_brainstorm_context_helper.sh`: found / unknown node / missing
     session (all exit 0) / `--lineage` / malformed id and `../x` (exit 2) /
     read-only proof (fixture tree hash unchanged). Trace any fixture helper before
     reuse; opt into `assert_counters_init`/`assert_counters_load` if bodies run in
     subshells.

## Verification

- `bash tests/test_brainstorm_context_helper.sh` passes
- `bash tests/run_all_python_tests.sh --test-dir tests` — last line `PYTHON SUITE: PASSED`
- `shellcheck .aitask-scripts/aitask_brainstorm_context.sh` clean
- `bash tests/test_touchpoint_count_contract.sh` passes; `audit-helper-whitelist` reports 5/5
- On a real session: `./.aitask-scripts/aitask_brainstorm_context.sh --lineage <N> <synth_node>` lists ancestors from every parent branch, and `git -C .aitask-crews/crew-brainstorm-<N> status` stays clean

## Post-implementation

Step 9 of the task workflow (review, commit, archive). In Final Implementation
Notes record the **final output grammar** — t1823_2's skill parses it.
