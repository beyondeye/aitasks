---
priority: medium
effort: medium
depends: [t1823_2]
issue_type: feature
status: Implementing
labels: [codeagent, skills]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1823
created_at: 2026-09-17 09:50
updated_at: 2026-09-17 15:39
---

## Context

Parent t1823 adds a brainstorm-TUI node operation that launches an interactive,
advisory-only code agent running the `aitask-brainstorm-discuss` skill (sibling
t1823_2) with argv `<task_num> <node_id>...`. TUIs launch agents through
`aitask_codeagent.sh invoke <operation> <args>`; this child wires the new
operation **`discuss`** into that wrapper for all supported agents.

**Why the op is `discuss`, not `brainstorm-discuss`:**
`tests/test_settings_brainstorm_descriptions.py` treats `brainstorm-*` keys in
`aitasks/metadata/codeagent_config.json` as crew agent types
(`brainstorm_crew.BRAINSTORM_AGENT_TYPES`) and rejects orphans. Confirm that rule
when you start; keep `discuss` regardless. Op and skill names need not match
(`learn` → `aitask-learn-skill` is the precedent).

Parent plan: `aiplans/p1823_brainstorm_discuss_proposals_interactive_agent.md`.

## Key files to modify

`.aitask-scripts/aitask_codeagent.sh` (line numbers as of planning — re-locate):
- `:26` `SUPPORTED_OPERATIONS=(...)` — add `discuss`. **Keep it a single line**:
  `tests/test_website_doc_lists.sh` parses it with `sed`.
- `:443` skill-arg validation alternation
  `pick|explain|qa|shadow|learn|work-report|trail)` — add `discuss` (every arg must
  be non-empty and whitespace-free).
- claudecode arm (model: `shadow` at `:481-484`):
  `CMD+=("/aitask-brainstorm-discuss ${args[*]}")`
- codex composer arm (model `:571`):
  `discuss) prompt=$(build_skill_prompt "\$aitask-brainstorm-discuss" "${args[@]}") ;;`
  — the default there is fail-closed (`die "operation not wired into the codex composer"`).
- opencode arm (model `:599-601`): `CMD+=("--prompt" "/aitask-brainstorm-discuss ${args[*]}")`
- `--help` operations prose (`:698-706`).
Defaults / descriptions:
- `aitasks/metadata/codeagent_config.json` and `seed/codeagent_config.json`
  `.defaults.discuss` — same agent string as `shadow`. (Commit the
  `aitasks/metadata/` file via `./ait git` / `aitask_task_commit.sh`, by path —
  never in the same commit as code.) Note `tests/test_add_model.sh:170-174` pins
  that the seed gains no `brainstorm-*` keys — `discuss` is fine.
- `.aitask-scripts/settings/settings_app.py` `OPERATION_DESCRIPTIONS["discuss"]` (~:132-154).
Docs pinned by test:
- `website/content/docs/commands/codeagent.md` `### Operations` table — add a
  `| \`discuss\` | … |` row (`tests/test_website_doc_lists.sh` Test 1). Current-state
  prose only; generic agent wording (see `aidocs/framework/documentation_conventions.md`).
Tests:
- `tests/test_codeagent.sh`: `skill_operations` (~:213), `codex_operations` +
  parallel `codex_skills` (~:236-237, add `aitask-brainstorm-discuss`), Codex
  TUI-override loop (~:258).
- NEW `tests/test_codeagent_discuss.sh` (model: `tests/test_codeagent_trail.sh`):
  `--dry-run invoke discuss 42 n001 n002` per agent → `DRY_RUN:` line carrying the
  skill prompt with all args in order; single-node form; empty-arg and
  whitespace-arg refusal (they fire under `--dry-run` too, by design).

## Reference files for patterns

- The `trail` op landing commit `3386e1f43e743` ("feature: Add aitask-trail skill
  (t1210_3)") — `git show --stat` it; its `aitask_codeagent.sh` hunk is the
  template for this diff.
- `--dry-run` must precede `invoke`; Python callers use
  `resolve_dry_run_command(project_root, "discuss", *args)`
  (`.aitask-scripts/lib/agent_launch_utils.py:255`).
- `aidocs/framework/shell_conventions.md`.

## Implementation plan

1. Wrapper edits (6 sites above), then config defaults + settings description.
2. `test_codeagent.sh` list extensions + `test_codeagent_discuss.sh`.
3. codeagent.md table row.
4. Post-phase risk mitigation **[unwired_op_guard]** (from the parent plan's
   `### Planned mitigations`). The op list lives in ~8 heterogeneous sites; codex
   fails closed for an unwired op (Test 11d4) but **claudecode and opencode fail
   open** — an op added only to line 26 yields an empty prompt and unvalidated
   args. Add a guard (in `tests/test_codeagent_discuss.sh` or a new
   `tests/test_codeagent_op_wiring.sh`) that parses `SUPPORTED_OPERATIONS` and the
   `:443` alternation from the script and, for every skill-backed op, asserts
   `--dry-run invoke <op> x` prints a `DRY_RUN:` line containing a non-empty
   `/aitask-…` prompt for `claudecode` and `opencode`; and that every op with a
   slash-command arm is in the validation alternation. **Negative control:** a
   sed-mutated temp copy of the script with a fake op added to line 26 only must
   make the guard fail (mutate a copy in the scratch dir — never the real file).

## Verification

- `bash tests/test_codeagent.sh`, `bash tests/test_codeagent_discuss.sh`,
  the guard test, `bash tests/test_website_doc_lists.sh`
- `bash tests/run_all_python_tests.sh --test-dir tests` for
  `test_settings_brainstorm_descriptions.py` / settings tests — read only the last
  `PYTHON SUITE:` line
- `shellcheck .aitask-scripts/aitask_codeagent.sh`
- `cd website && python3 check_links.py --build`

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1826** id=2026-09-17T19:48:15Z.5b7d358ef4b550fd23a3a9e1 from=t1826 from_verified=yes at=2026-09-17T19:48:15Z base=025ba5e9576de4c0064df0ca2b620b8381e64a70 base_branch=main dirty=yes host=omg16
>
> | New rule for any bash test this task adds (landed in 025ba5e95, t1826).
> | 
> | Every `cd`/`pushd` in `tests/*.sh` and `tests/lib/*.sh` must be exit-guarded
> | (`cd "$X" || exit 1`, or `|| { …; exit 1; }`) or be an `&&` chain confined to a
> | `(`/`$(` subshell. `|| return`, `|| true`, `if cd …`, `! cd …` and
> | `{ cd X && …; }` are rejected, the target must be quoted, and a reviewed
> | `# cd-guard: <reason>` comment is the escape hatch. A test that changes its cwd
> | also sources `tests/lib/scratch_cwd.sh` and calls `enter_scratch_cwd` right
> | after `PROJECT_DIR` is derived — before any `ORIG_DIR="$(pwd)"` capture and
> | before any `dirname "$BASH_SOURCE"`-relative path derivation, both of which
> | break if they run after the cwd moves.
> | 
> | `tests/test_cd_guard_lint.sh` fails the build on a violation;
> | `python3 tests/lib/cd_guard_scan.py --check tests/*.sh` and `--helper-order
> | tests/*.sh` report them by file:line. Rationale and accepted forms:
> | aidocs/framework/testing_conventions.md ("Every `cd` in a bash test is
> | `exit`-guarded").
> | 
> | t1823_2's two test files were adopted into this rule in the same commit; their
> | guarded `cd "$PROJECT_DIR" || exit 1` was left as-is. Advisory only — nothing
> | here asks you to change your task's scope.
