---
Task: t1823_3_codeagent_discuss_operation.md
Parent Task: aitasks/t1823_brainstorm_discuss_proposals_interactive_agent.md
Sibling Tasks: aitasks/t1823/t1823_1_*.md, aitasks/t1823/t1823_2_*.md, aitasks/t1823/t1823_4_*.md, aitasks/t1823/t1823_5_*.md
Archived Sibling Plans: aiplans/archived/p1823/p1823_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-17 22:55
---

# t1823_3 — Codeagent operation `discuss`

## Context

TUIs launch agents via `aitask_codeagent.sh invoke <op> <args>`. The brainstorm
Discuss op (t1823_4) needs an operation that maps to the
`aitask-brainstorm-discuss` skill (landed in t1823_2) with argv
`<task_num> <node_id>...`. Op name is `discuss`, not `brainstorm-discuss`:
`tests/test_settings_brainstorm_descriptions.py` treats every `brainstorm-*`
config key as a crew agent type from `BRAINSTORM_AGENT_TYPES` and rejects
orphans (confirmed during verification). Template diff: the `trail` op commit
`3386e1f43e743`.

Parent plan: `aiplans/p1823_brainstorm_discuss_proposals_interactive_agent.md`.

### Verification notes (2026-09-17)

All sites re-located and still match: `SUPPORTED_OPERATIONS` `:26`, validation
alternation `:443`, claudecode arms `:481-496`, codex composer `:571-579`
(fail-closed default), opencode arms `:599-610`, help prose `:699-700`.
`settings_app.py` `OPERATION_DESCRIPTIONS` `:132-155`. Live config `shadow` =
`codex/gpt5_6_terra`, seed `shadow` = `claudecode/opus5`.

**Concurrent in-flight work — t1826** (Implementing) has uncommitted hunks in
`tests/test_codeagent.sh` and `tests/test_codeagent_trail.sh` (sources the
*untracked* `tests/lib/scratch_cwd.sh`, adds `|| exit 1` to `cd`s). Therefore:
- `tests/test_codeagent.sh` is committed by **staging only this task's hunks**
  (whitelist, via a filtered patch into the index — never `git add` the file),
  then verified in a detached worktree of the commit against a parent control.
- New test files do **not** source `scratch_cwd.sh` (it is not in the tree);
  they write `cd … || exit 1` so t1826 has nothing to retrofit.

## Steps

1. `.aitask-scripts/aitask_codeagent.sh`:
   - `SUPPORTED_OPERATIONS` += `discuss` (append; keep ONE line).
   - validation alternation: `pick|explain|qa|shadow|learn|work-report|trail|discuss)`.
   - claudecode arm, after `trail`:
     `discuss)` / `# claude --model <id> "/aitask-brainstorm-discuss <task_num> <node_id>..."` / `CMD+=("/aitask-brainstorm-discuss ${args[*]}")`.
   - codex composer: `discuss) prompt=$(build_skill_prompt "\$aitask-brainstorm-discuss" "${args[@]}") ;;`
   - opencode arm: `discuss) CMD+=("--prompt" "/aitask-brainstorm-discuss ${args[*]}") ;;`
   - `--help`: `shadow, learn, work-report, trail, discuss`.
2. Defaults / descriptions:
   - `seed/codeagent_config.json`: `"discuss": "claudecode/opus5"` (= seed shadow).
   - `aitasks/metadata/codeagent_config.json`: `"discuss": "codex/gpt5_6_terra"`
     (= live shadow) — committed separately via `aitask_task_commit.sh`, by path.
   - `settings_app.py` `OPERATION_DESCRIPTIONS["discuss"]`: "Model used for the
     brainstorm discuss agent (launched from the brainstorm TUI to compare,
     explain, question and risk-check proposals — advisory only)".
3. `tests/test_codeagent.sh`: `discuss` into `skill_operations` (11d2),
   `codex_operations` + `aitask-brainstorm-discuss` in `codex_skills` (11d3,
   parallel), and the 11e Codex override loop.
4. NEW `tests/test_codeagent_discuss.sh` (fixture shape from
   `test_codeagent_trail.sh`, seeded config):
   - claudecode / codex / opencode `--dry-run invoke discuss 42 n001 n002` →
     `DRY_RUN:` + binary + `/aitask-brainstorm-discuss\ 42\ n001\ n002`
     (codex: `$aitask-brainstorm-discuss\ 42\ n001\ n002`, no `--sandbox`/plan).
   - single-node form `discuss 42 n001`.
   - empty and whitespace arg refused under `--dry-run`, no `DRY_RUN:` line, for
     claudecode and codex.
   - `resolve discuss` == seeded `shadow` default (sentinel
     `DEFAULT_AGENT_STRING` via `tests/lib/codeagent_defaults.sh`, as trail Test 4),
     and `claudecode` dry-run carries the resolved `CLI_ID`.
5. `website/content/docs/commands/codeagent.md` Operations table, after
   `shadow`: `| \`discuss\` | Advisory discussion of brainstorm proposals | \`codex/gpt5_6_terra\` |`.

### Post-phase (risk mitigations)
1. [unwired_op_guard] NEW `tests/test_codeagent_op_wiring.sh`. A function
   `op_wiring_failures <script>` returns the number of wiring defects (no
   PASS/FAIL side effects) so it can be run against the real script and mutants:
   - parse `SUPPORTED_OPERATIONS` with the same sed as
     `test_website_doc_lists.sh`; tripwire that it is non-empty and contains `pick`.
   - explicit passthrough/special exemption list `batch-review raw explore-relay`
     (with a comment why), itself asserted ⊆ the parsed ops so it cannot rot.
   - for every other op, for `claudecode/opus5` and `opencode/openai_gpt_5_4`:
     `--dry-run invoke <op> probe` must exit 0 and its last argv (python
     `shlex`, as 11e's `dry_run_last_arg`) must match `^/aitask-[a-z-]+`.
   - validation coverage, behavioural rather than regex-parsing the `:443`
     alternation: for every op whose claudecode prompt carries the `probe` arg
     (i.e. its arm consumes args — `explore` does not), `--dry-run invoke <op> ''`
     must exit non-zero with `argument is empty`.
   - **Negative controls — one per guard, each on its own mutated copy** in the
     fixture's `.aitask-scripts/`, never the real file. Each mutation asserts its
     transform matched exactly once (awk/sed match count), so a silently
     non-matching mutant cannot make a control vacuous:
     - (a) **prompt-wiring guard:** awk-add `unwired-probe` to
       `SUPPORTED_OPERATIONS` only, leaving every arm unwired →
       `op_wiring_failures` > 0, and the failure text names `unwired-probe`.
       Control (b) must NOT fire on this mutant (the fake op takes no args, so
       only the prompt check may report it).
     - (b) **validation-coverage guard, independent of (a):** take the unmutated
       script and delete `|discuss` from the `:443` alternation only — prompt
       wiring stays fully intact, so (a)'s check passes and **only** the
       empty-arg check can fail → `op_wiring_failures` > 0, and the failure text
       names `discuss`. This is the regression the general guard would otherwise
       never be shown to catch: an op whose prompt is wired but whose
       empty/whitespace-argument protection was dropped.
     - Real script → failures == 0.
   - If the guard exposes an existing unwired op, record it under "Upstream
     defects identified" — do not widen this task.

## Verification

- `bash tests/test_codeagent.sh`, `bash tests/test_codeagent_discuss.sh`,
  `bash tests/test_codeagent_op_wiring.sh`, `bash tests/test_codeagent_trail.sh`
- `bash tests/test_website_doc_lists.sh`
- `bash tests/run_all_python_tests.sh --test-dir tests` — last line only
  (`test_settings_brainstorm_descriptions.py`, settings tests)
- `shellcheck .aitask-scripts/aitask_codeagent.sh tests/test_codeagent_discuss.sh tests/test_codeagent_op_wiring.sh`
  must exit **0**, plain and with `-x`. A source line that shellcheck cannot
  follow is SC1091 *info*, which still exits 1, so each `.` of a `tests/lib/`
  helper in the new files carries `# shellcheck source=<rel> disable=SC1091`
  (precedent: `tests/test_brainstorm_context_helper.sh:16`). An unrelated file
  sharing the baseline is not a reason to leave the declared command red.
- `cd website && python3 check_links.py --build`
- `./.aitask-scripts/aitask_codeagent.sh --dry-run invoke discuss 42 n001 n002`
- Selective-staging check: detached worktree at the code commit, run the three
  codeagent test files there, with the parent commit as control.

## Follow-up awareness

`lib/agent_command_screen.py` `_FRESH_WINDOW_OPERATIONS` (trail was added there
in its op commit) decides the dialog's default window placement; whether
`discuss` belongs there is a launch-UX call for t1823_4 — send it an `ait note`,
do not change it here.

## Post-implementation

Step 9 of the task workflow.

## Risk

### Code-health risk: low
- The op list is duplicated across ~8 heterogeneous sites and claudecode/opencode fail open for an op added only to line 26 · severity: low (residual) · → mitigation: inline post-phase unwired_op_guard
- t1826's uncommitted hunks share `tests/test_codeagent.sh`; a whole-file commit would ship them with a reference to an untracked lib · severity: low · → mitigation: none (whitelisted hunk staging + detached-worktree check, in Verification)

### Goal-achievement risk: low
None identified.

### Planned mitigations
- timing: post-phase | name: unwired_op_guard | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: codeagent op list duplicated across ~8 sites, fail-open on claudecode/opencode | desc: guard test that every skill-backed SUPPORTED_OPERATIONS op is wired and validated for claudecode and opencode, with mutant negative controls

## Final Implementation Notes

- **Actual work done:** `discuss` wired into `aitask_codeagent.sh` at all six
  sites (`SUPPORTED_OPERATIONS`, the argument-validation alternation, the
  claudecode / codex-composer / opencode arms, `--help`), mapping to
  `/aitask-brainstorm-discuss <task_num> <node_id>...`. Defaults added to
  `seed/codeagent_config.json` (`claudecode/opus5`) and
  `aitasks/metadata/codeagent_config.json` (`codex/gpt5_6_terra`) — each the
  file's own `shadow` value. `OPERATION_DESCRIPTIONS["discuss"]` added to
  `settings_app.py`; Operations-table row added to
  `website/content/docs/commands/codeagent.md`. `tests/test_codeagent.sh` lists
  extended (11d2 `skill_operations`, 11d3 `codex_operations`/`codex_skills`,
  11e override loop). New `tests/test_codeagent_discuss.sh` (34 assertions) and
  the post-phase guard `tests/test_codeagent_op_wiring.sh` (19 assertions).
- **Deviations from plan:**
  - The op-wiring guard checks validation coverage **behaviourally** (an
    arg-bearing op must refuse an empty argument) instead of regex-parsing the
    `:443` alternation. The property that matters is the refusal, and this form
    exempts `explore` (which ignores argv) with no list to maintain.
  - The guard lives in its own `tests/test_codeagent_op_wiring.sh` rather than
    inside the discuss test — the plan allowed either; it is cross-op, not
    discuss-specific.
  - Review round 1 (lint): the plan's `shellcheck` command exited 1 on SC1091
    *info* for the new files' `tests/lib/` source lines. Each now carries
    `# shellcheck source=<rel> disable=SC1091` (precedent
    `tests/test_brainstorm_context_helper.sh:16`), so the declared command
    exits 0 plain and with `-x`.
- **Issues encountered:**
  - The first draft's "transform matched exactly once" mutant assertions were
    vacuous (`test -s <file>` on awk output, which is non-empty even when awk
    exits 1). Replaced with the captured awk exit status plus a `cmp` proving
    the mutant actually differs from the shipped script.
  - `tests/test_codeagent.sh` also holds **t1826's** uncommitted hunks (it
    sources the still-untracked `tests/lib/scratch_cwd.sh`). Only this task's
    four list-line hunks were committed, by swapping in a HEAD+mine blob for
    the commit and restoring the full working file immediately after
    (backup-and-`cmp`-verified); `git commit -- <path>` takes worktree content,
    so index-only staging would not have worked. For the same reason the two
    new test files deliberately do **not** source `scratch_cwd.sh`.
- **Key decisions:**
  - Op name `discuss`, not `brainstorm-discuss`: confirmed at implementation
    time that `tests/test_settings_brainstorm_descriptions.py` treats every
    `brainstorm-*` config key as a `BRAINSTORM_AGENT_TYPES` crew agent type and
    rejects orphans.
  - The guard's exemption list (`batch-review`, `raw`, `explore-relay`) is
    explicit and asserted to be a subset of the parsed operations, so a renamed
    op cannot turn it into a blanket exemption.
  - Codex arm left in default mode (no plan mode, no sandbox), matching the
    advisory read-only nature of the skill and the `trail` precedent.
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - t1823_4 (brainstorm TUI op): launch with
    `resolve_dry_run_command(root, "discuss", <task_num>, *<node_ids>)`; argv
    must be whitespace-free and non-empty — the wrapper refuses otherwise, and
    it refuses under `--dry-run` too, so a pre-flight dry-run surfaces it.
    `lib/agent_command_screen.py` `_FRESH_WINDOW_OPERATIONS` does **not** list
    `discuss` (trail added itself there); whether the discuss dialog should
    default to a fresh window is a launch-UX call owned by t1823_4.
  - Any future operation added to `SUPPORTED_OPERATIONS` is now automatically
    covered by `tests/test_codeagent_op_wiring.sh` — a new op that is wired
    only at line 26 fails that suite for claudecode and opencode.
