---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [ait_brainstorm, skills]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1823
created_at: 2026-09-17 09:49
updated_at: 2026-09-17 10:45
---

## Context

Parent t1823 adds a brainstorm-TUI node operation that launches an interactive,
**advisory-only (read-only)** code agent over the proposal files of the selected
node(s). The agent's skill (`aitask-brainstorm-discuss`, sibling t1823_2) receives
only ids on argv — `<task_num> <node_id>...` — because the codeagent wrapper
refuses empty/whitespace skill args and bulk context must be self-fetched (the
shadow-agent rule: "argv carries ids only"). This child builds the read-only
resolver the skill calls to turn those ids into paths.

No existing CLI does this: `ait brainstorm status` prints counts but no paths or
node ids, `brainstorm_cli.py exists` is not wired into `ait`, and the only
path-emitting command (`init`) *creates* a session. The resolution logic exists
only as a Python API.

Parent plan: `aiplans/p1823_brainstorm_discuss_proposals_interactive_agent.md`.

## Key files to modify

- `.aitask-scripts/brainstorm/brainstorm_dag.py` — add pure
  `get_node_ancestors(session_path, node_id) -> list[tuple[str, int]]`.
- `.aitask-scripts/brainstorm/brainstorm_cli.py` — add subcommand
  `paths --task-num N [--lineage] [node_id...]`.
- `.aitask-scripts/aitask_brainstorm_context.sh` — NEW thin bash wrapper.
- 5 permission touchpoints for the new helper (it IS invoked from a skill):
  `.claude/settings.local.json`, `.codex/rules/default.rules`,
  `seed/claude_settings.local.json`, `seed/codex_rules.default.rules`,
  `seed/opencode_config.seed.json` — plus keep
  `aitasks/metadata/opencode_config.seed.json` in sync (shadow's helpers are
  listed there too, though it is not an audited touchpoint).
- NEW tests: `tests/test_brainstorm_context_helper.sh`,
  `tests/test_brainstorm_node_ancestors.py`.

## Reference files for patterns

- `.aitask-scripts/aitask_shadow_context.sh` — THE mould: thin orchestrator,
  `KEY:value` lines, **every resolution outcome exits 0 (parse lines, not the exit
  code)**, a malformed id is the one hard error.
- `.aitask-scripts/brainstorm/brainstorm_session.py:54-56` `crew_worktree(task_num)`
  → `.aitask-crews/crew-brainstorm-<task_num>/`; `load_session` (:201);
  `br_session.yaml` carries `task_id`, `task_file`.
- `.aitask-scripts/brainstorm/brainstorm_op_refs.py:33-57` `OpDataRef` +
  `file_for_ref` (`node_proposal` → `br_proposals/<id>.md`, `node_metadata` →
  `br_nodes/<id>.yaml`).
- `brainstorm_dag.py`: `get_parents` (:208), `list_nodes` (:102), `read_node` (:88),
  `_node_module`, `get_node_lineage` (:435).
- `aidocs/framework/shell_conventions.md` (shebang, `set -euo pipefail`, python
  resolution via `lib/python_resolve.sh`, source-on-startup ↔ test-scaffold rule),
  `aidocs/framework/aitasks_extension_points.md` "Adding a new helper script".

## Implementation plan

1. **`get_node_ancestors`** in `brainstorm_dag.py`. **Do NOT use
   `get_node_lineage`** — it is a first-parent walk confined to one module
   (default `_umbrella`): a synthesized/merged node loses every contributing branch
   but the first, and a module node stops at its subgraph root. That is
   insufficient for explaining how a proposal evolved. The new function:
   - BFS over **all** `get_parents` edges, **crossing module boundaries**;
   - visited set for de-duplication (a diamond ancestor is emitted once, at its
     shortest depth) and cycle protection (an already-visited node — including
     the start node — is never re-queued);
   - tolerant of a parent id whose YAML is missing (still returned; the CLI
     prints `PROPOSAL:NOT_FOUND` for it — never a crash);
   - deterministic order: by depth, then node id. Returns `(ancestor_id, depth)`,
     excluding the start node.
   Leave `get_node_lineage` and all its callers untouched.
2. **`brainstorm_cli.py paths`**. Output, one line each:
   ```
   SESSION_PATH:<path>|NOT_FOUND
   TASK_FILE:<path>|NOT_FOUND
   NODE:<id>|PROPOSAL:<path or NOT_FOUND>|META:<path or NOT_FOUND>|PARENTS:<csv>
   ANCESTOR:<node>|<ancestor_id>|DEPTH:<n>|MODULE:<label>|PARENTS:<csv>|PROPOSAL:<path or NOT_FOUND>   # --lineage only
   ```
   `PARENTS:` on each ancestor line lets the skill reconstruct real edges (which
   branch a synthesis drew from); `MODULE:` makes a boundary crossing visible.
   Exit 0 on every resolution outcome (missing session → `SESSION_PATH:NOT_FOUND`
   and stop). Validate task num and every node id against `^[A-Za-z0-9_.-]+$`
   and reject `.`/`..` — malformed input is the one hard error (exit 2); this
   also blocks path traversal. With no node ids, emit `NODE:` lines for every
   node in `list_nodes()`. Resolve paths only through `crew_worktree` +
   `file_for_ref` — do not re-derive the layout.
3. **`aitask_brainstorm_context.sh`** — thin wrapper: usage
   `aitask_brainstorm_context.sh [--lineage] <task_num> [<node_id>...]`; resolves
   python, execs the CLI subcommand. No `ait` dispatcher entry (not user-facing).
4. **Whitelist**: `./.aitask-scripts/aitask_audit_wrappers.sh apply-helper-whitelist
   aitask_brainstorm_context.sh`, then `audit-helper-whitelist` to confirm 5/5.
   Entries are inserted alphabetically; do not hand-reorder others.
5. Tests (see Verification).

## Verification

- `tests/test_brainstorm_node_ancestors.py` (fixture session built with
  `create_node`, `AGENTCREW_DIR` monkeypatched as existing brainstorm tests do):
  - **multi-parent synthesis**: node with parents `[a, b]` on divergent branches →
    ancestors of both branches present; and assert `get_node_lineage` on the SAME
    fixture omits branch `b` — the control proving the distinction;
  - **module-boundary ancestry**: module-subgraph node whose root's parent lives in
    `_umbrella` → umbrella ancestors present;
  - diamond de-dup (shared ancestor once, shortest depth); a hand-written parent
    cycle terminates; missing-parent YAML tolerated.
- `tests/test_brainstorm_context_helper.sh`: found node, unknown node
  (`PROPOSAL:NOT_FOUND`, exit 0), missing session (exit 0), `--lineage`, malformed id
  and `../x` refusal (exit 2), and a **read-only proof** (hash of the fixture tree
  unchanged after every invocation). Trace any fixture helper before reusing it;
  if test bodies run in `( … )` subshells, opt into `assert_counters_init` /
  `assert_counters_load` (see CLAUDE.md Testing).
- `shellcheck .aitask-scripts/aitask_brainstorm_context.sh`;
  `bash tests/test_touchpoint_count_contract.sh`;
  `bash tests/run_all_python_tests.sh --test-dir tests` — read only the last
  `PYTHON SUITE:` line.

## Notes for sibling tasks

The output grammar above is the contract t1823_2's skill parses. If it changes
during implementation, record the final grammar in this task's plan
"Final Implementation Notes".
