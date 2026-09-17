---
Task: t1823_3_codeagent_discuss_operation.md
Parent Task: aitasks/t1823_brainstorm_discuss_proposals_interactive_agent.md
Sibling Tasks: aitasks/t1823/t1823_1_*.md, aitasks/t1823/t1823_2_*.md, aitasks/t1823/t1823_4_*.md, aitasks/t1823/t1823_5_*.md
Archived Sibling Plans: aiplans/archived/p1823/p1823_*_*.md
Base branch: main
Output branch: main
---

# t1823_3 — Codeagent operation `discuss`

## Context

TUIs launch agents via `aitask_codeagent.sh invoke <op> <args>`. The brainstorm
Discuss op (t1823_4) needs an operation that maps to the
`aitask-brainstorm-discuss` skill (t1823_2) with argv `<task_num> <node_id>...`.
Op name is `discuss` (not `brainstorm-discuss`: `brainstorm-*` config keys are
crew agent types, orphan-checked by `tests/test_settings_brainstorm_descriptions.py`
— confirm on start). Template diff: the `trail` op commit `3386e1f43e743`.

Parent plan: `aiplans/p1823_brainstorm_discuss_proposals_interactive_agent.md`.

## Steps

1. `.aitask-scripts/aitask_codeagent.sh` (re-locate line numbers):
   - `SUPPORTED_OPERATIONS` (~:26) += `discuss` — keep ONE line (sed-parsed by
     `tests/test_website_doc_lists.sh`);
   - skill-arg validation alternation (~:443) += `discuss`;
   - claudecode arm: `discuss) CMD+=("/aitask-brainstorm-discuss ${args[*]}") ;;`
   - codex composer: `discuss) prompt=$(build_skill_prompt "\$aitask-brainstorm-discuss" "${args[@]}") ;;`
   - opencode arm: `discuss) CMD+=("--prompt" "/aitask-brainstorm-discuss ${args[*]}") ;;`
   - `--help` operations prose.
2. Defaults: `seed/codeagent_config.json` and `aitasks/metadata/codeagent_config.json`
   `.defaults.discuss` = the `shadow` value (the metadata file is committed
   separately via `aitask_task_commit.sh`, by path). `settings_app.py`
   `OPERATION_DESCRIPTIONS["discuss"]`.
3. `tests/test_codeagent.sh`: extend `skill_operations`, `codex_operations` +
   `codex_skills` (`aitask-brainstorm-discuss`, keep the arrays parallel), and the
   Codex TUI-override loop.
4. NEW `tests/test_codeagent_discuss.sh` (model `test_codeagent_trail.sh`): per agent
   `--dry-run invoke discuss 42 n001 n002` → prompt carries all args in order;
   single-node form; empty and whitespace arg refused (under `--dry-run` too).
5. `website/content/docs/commands/codeagent.md` Operations table row for `discuss`
   (current-state prose, generic agent wording).

### Post-phase (risk mitigations)
1. [unwired_op_guard] Guard test (in `test_codeagent_discuss.sh` or new
   `tests/test_codeagent_op_wiring.sh`): parse `SUPPORTED_OPERATIONS` and the
   validation alternation from the script; for every skill-backed op assert
   `--dry-run invoke <op> x` yields a `DRY_RUN:` line with a non-empty `/aitask-…`
   prompt for `claudecode` and `opencode`; assert every op with a slash-command
   arm is in the alternation. Negative control: a sed-mutated temp copy of the
   script (fake op in line 26 only, in the scratch dir) makes the guard fail.
   If the guard exposes an existing unwired op, record it under "Upstream defects
   identified" — do not widen this task.

## Verification

- `bash tests/test_codeagent.sh`, `bash tests/test_codeagent_discuss.sh`, guard test pass
- `bash tests/test_website_doc_lists.sh` passes
- `bash tests/run_all_python_tests.sh --test-dir tests` — last line `PYTHON SUITE: PASSED`
- `shellcheck .aitask-scripts/aitask_codeagent.sh` clean
- `cd website && python3 check_links.py --build` passes
- `./.aitask-scripts/aitask_codeagent.sh --dry-run invoke discuss 42 n001 n002` prints the expected claude command

## Post-implementation

Step 9 of the task workflow.
