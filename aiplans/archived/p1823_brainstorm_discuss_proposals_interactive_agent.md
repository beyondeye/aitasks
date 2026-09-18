---
Task: t1823_brainstorm_discuss_proposals_interactive_agent.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1823 — Brainstorm "Discuss proposals" interactive advisory agent (parent plan: decomposition)

## Context

`ait brainstorm` lets the user generate and evolve design proposals as DAG nodes, but
offers no way to *talk about* them: comparing two proposals, asking questions, getting a
plain-language explanation, or having one checked for structural flaws all require
reading raw markdown. This task adds a node operation that launches an **interactive,
strictly advisory (read-only)** code agent over the proposal file(s) of the cursor node
or the space-marked set, modelled on the shadow agent but anchored on brainstorm
proposals instead of a followed pane.

Decisions confirmed during planning (2026-09-17):
- **Split into child tasks** (this plan is the decomposition; each child gets its own plan).
- **Own procedure files** in the new skill, with **no cross-skill reference into `aitask-shadow/` at all**.
  Shadow's `plan-*.md` / `concern-format.md` are wired to pane capture, round snapshots and minimonitor
  concern-forwarding (emitting `===AITASK-CONCERNS===` fences here could be mis-forwarded).
  *Plan-review correction:* the original idea of referencing `aitask-shadow/round-preamble.md` §1-§2 is
  dropped. `skill_template.py` `discover_refs`/`walk_closure` scan whole files and follow every filename
  that resolves — section limits do not limit the closure — and `round-preamble.md` names
  `plan-challenge.md`, `plan-assumptions.md`, `impl-challenge.md`, `plan-diagnose-errors.md`,
  `concern-format.md` (all fence-bearing) and `task-summarize.md`. The small audience + plain-words
  rules are instead **adapted locally** into a dependency-free `discuss-audience.md`.
- **Operations-dialog row only** — no new app-level key binding (follow-up candidate; t1296 pending).

## Key design choices

| Choice | Value | Why |
|---|---|---|
| Skill slug | `aitask-brainstorm-discuss` | resolver key defaults to `brainstorm-discuss` (no `resolver_key.txt` sidecar — `test_opencode_skill_legacy_pointers.sh` ignores sidecars) |
| Codeagent operation | `discuss` | NOT `brainstorm-discuss`: `tests/test_settings_brainstorm_descriptions.py` treats `brainstorm-*` keys in `codeagent_config.json` as crew agent types and rejects orphans. Op→skill names need not match (`learn` → `aitask-learn-skill` precedent). Verify the orphan rule at implementation; keep `discuss` regardless. |
| argv | `<task_num> <node_id>...` | ids only, whitespace-free (codeagent skill-arg gate); skill self-fetches paths. No raw paths on argv. |
| Context helper | `aitask_brainstorm_context.sh` over a new `brainstorm_cli.py paths` subcommand | no existing CLI emits session/proposal paths; reuse pure `crew_worktree` + `file_for_ref` + `get_parents`, plus a new all-parents `get_node_ancestors` (NOT the first-parent, single-module `get_node_lineage`) — no path convention re-derived in shell. Mould: `aitask_shadow_context.sh` (exit 0 on every resolution outcome; parse lines). |
| tmux window name | `agent-discuss-<task_num>` | `maybe_spawn_minimonitor` skips `brainstorm-*` names; `agent-` prefix gets the companion |
| TUI wiring | new cardinality class `_ANY_NODE_OPS = ("discuss",)`; row appended at the END of `NodeActionSelectModal._OPS` (after `delete`) | several tests assume first row = `explore` and one `down` = `compare`; appending last keeps them valid, only the pinned-order list test is updated |
| Wizard | never entered; branch in `_on_node_action_result` before `push_screen`, like `delete`. NOT added to `_DESIGN_OPS` (that is the wizard Step-1 row source). Label via `_LOCAL_LABELS`; help via `_OPERATION_HELP["discuss"]`. No crew agent registered. |

**Duplicated op-list note (planning convention "refactor duplicates first").** The codeagent
operation list appears in ~8 sites, but they are heterogeneous (per-agent bash `case` arms with
different prompt syntax, a docs table, test matrices) rather than copies of one list, and two
drift guards already exist (`test_website_doc_lists.sh`, `test_codeagent.sh` Test 11d4 for codex).
No SSOT extraction in this task; the remaining gap (claudecode/opencode silently produce an empty
prompt for an unwired op) is closed by a small guard test in child 3 — see Risk.

## Child tasks (created post-approval — plan mode is read-only)

All in scope as siblings (auto sequential deps). Each child task file carries full context
(Context / Key files / Reference patterns / Implementation plan / Verification) per
`planning.md` "Child Task Documentation Requirements", and each gets a plan in `aiplans/p1823/`.

### t1823_1 — `discuss_context_helper` (feature, effort medium)
Read-only resolver the skill calls.
- `.aitask-scripts/brainstorm/brainstorm_cli.py`: add `paths --task-num N [--lineage] [node_id...]`.
  Output, one line each, always exit 0 on resolution outcomes:
  `SESSION_PATH:<path>|NOT_FOUND`, `TASK_FILE:<path>|NOT_FOUND` (from `br_session.yaml` `task_file`),
  `NODE:<id>|PROPOSAL:<path or NOT_FOUND>|META:<path or NOT_FOUND>|PARENTS:<csv>`; with `--lineage`,
  extra `ANCESTOR:<node>|<ancestor_id>|DEPTH:<n>|MODULE:<label>|PARENTS:<csv>|PROPOSAL:<path or NOT_FOUND>` lines.
  **Do NOT use `get_node_lineage` for this** — it is a first-parent walk confined to one module
  (default `_umbrella`, `brainstorm_dag.py:435-468`): a synthesized/merged node loses every
  contributing branch but the first, and a module node stops at its subgraph root. Add a new pure
  function `get_node_ancestors(session_path, node_id) -> list[tuple[str, int]]` in `brainstorm_dag.py`:
  BFS over **all** `get_parents` edges, crossing module boundaries, with a visited set for
  de-duplication (diamond ancestry emitted once, at its shortest depth) and cycle protection
  (a node already visited — including the start node — is never re-queued), tolerant of a parent id
  whose YAML is missing (emitted with `PROPOSAL:NOT_FOUND`, not a crash). Deterministic order:
  by depth, then node id. `PARENTS:` on each ancestor line lets the skill reconstruct the actual
  edges (which branch a synthesis drew from) rather than a flattened list; `MODULE:` makes a
  module-boundary crossing visible. `get_node_lineage` and its callers are left untouched. Malformed task num / node id
  (anything outside `[A-Za-z0-9_.-]`) is the one hard error (exit 2) — also blocks path traversal.
  Reuse `crew_worktree` (`brainstorm_session.py:54`), `file_for_ref`/`OpDataRef`
  (`brainstorm_op_refs.py:33-57`), `get_parents`/`get_node_lineage`/`list_nodes` (`brainstorm_dag.py`).
- `.aitask-scripts/aitask_brainstorm_context.sh`: thin wrapper (shell conventions doc: shebang,
  `set -euo pipefail`, python resolve via `lib/python_resolve.sh`). No `ait` dispatcher entry (not user-facing).
- **5 permission touchpoints** for the new helper via
  `./.aitask-scripts/aitask_audit_wrappers.sh apply-helper-whitelist aitask_brainstorm_context.sh`:
  `.claude/settings.local.json`, `.codex/rules/default.rules`, `seed/claude_settings.local.json`,
  `seed/codex_rules.default.rules`, `seed/opencode_config.seed.json` (+ keep
  `aitasks/metadata/opencode_config.seed.json` in sync, as shadow's helpers are).
- Tests: `tests/test_brainstorm_context_helper.sh` (fixture session dir via monkeypatched
  `AGENTCREW_DIR`/cwd; found, NOT_FOUND node, missing session, malformed-id refusal,
  read-only proof: tree hash unchanged) plus `tests/test_brainstorm_node_ancestors.py` for the new
  DAG function: **multi-parent synthesis** (node with parents `[a, b]` on divergent branches → both
  branches' ancestors present; assert `get_node_lineage` on the same fixture omits branch `b`, as the
  control proving the distinction), **module-boundary ancestry** (module subgraph node whose root's
  parent lives in `_umbrella` → umbrella ancestors present with their `MODULE:`), diamond de-dup
  (shared ancestor once), a hand-written parent cycle terminates, missing-parent YAML tolerated. Trace any reused fixture helper first; opt into
  `assert_counters_init` if bodies run in subshells. `shellcheck`.

### t1823_2 — `brainstorm_discuss_skill` (feature, effort high)
New profile-aware skill, Claude Code source of truth, **all 4 stub surfaces in the first commit**.
- `.claude/skills/aitask-brainstorm-discuss/SKILL.md` (stub, resolver key `brainstorm-discuss`),
  `SKILL.md.j2`, and procedure files: `discuss-compare.md` (simple / detailed), `discuss-explain.md`
  (adapted from shadow `plan-explain.md` steps 2-6), `discuss-flaws.md` (shadow `plan-challenge.md`
  six attack axes + `plan-assumptions.md` five buckets + impact vector, **plain prose output, no
  concern fences, no snapshots**), and `discuss-audience.md` — the audience rule (reader will not
  read the proposal: no file paths / function names / framework terms in simple-words output) and
  the "In plain words:" derivation order, adapted locally from shadow `round-preamble.md` §1-§2.
  **Closure hygiene (load-bearing):** no file in this skill may contain a filename that resolves
  under `.claude/skills/aitask-shadow/` — not as a bare sibling-looking name (a sibling ref resolves
  only in this skill's own dir, so `plan-challenge.md` would be inert, but avoid it anyway), and
  never as `aitask-shadow/<file>.md` or a full `.claude/skills/aitask-shadow/...` path. Provenance
  ("adapted from the shadow's audience rules") is stated in words without a resolvable path.
  Shadow's files are not edited, so shadow's goldens are untouched.
- **Verify the actual closure inventory**, not the intent: run
  `skill_template.py walk-check` for the template and assert the closure's resolved source set is
  exactly `{SKILL.md.j2, discuss-compare.md, discuss-explain.md, discuss-flaws.md, discuss-audience.md}`
  (the render test's Test 0 inventory + a closure-set assertion — an `aitask-shadow` path anywhere
  in the walked set is a failure).
- Template shape (mirror `aitask-shadow/SKILL.md.j2`): "What this is" with the advisory contract
  up front → Arguments (`<task_num> <node_id>...`) → **Step 0 fast start**: run the context helper
  once, skim only each proposal's title/first heading, list proposals with handles `A`,`B`,… + node id
  (skip the list ceremony for one proposal), then the capability menu **derived at runtime from the
  capability section** (maintainer comment forbidding a hardcoded copy; `>`-prefixed shortcodes,
  `>?` reprints) — no analysis up front → lazy context section (node YAML, task file, `--lineage`
  ancestors: read on demand only) → capability catalogue (`>c` compare simple, `>cd` compare detailed,
  `>e` explain, `>q` free-form Q&A inline, `>f` flaws & risks) → **"Guardrail — advisory only
  (load-bearing)"** stated in this task's terms: never edit proposal files, node YAML, session state,
  or run `ait brainstorm` mutating commands; restated in each procedure's header.
  Jinja surface: `{{ profile.name }}` only (no new profile key).
- Stubs: `.agents/skills/aitask-brainstorm-discuss/SKILL.md`, `.opencode/commands/aitask-brainstorm-discuss.md`,
  `.opencode/skills/aitask-brainstorm-discuss/SKILL.md` (generate with `aitask_audit_wrappers.sh apply-wrapper`).
  These are dispatch stubs, not the ports.
- Profile-key registration: `settings_app.py` `VALID_PROFILE_SKILLS` (+ prose copy ~:263),
  `seed/project_config.yaml` valid-name comment (~:391); check `tests/test_settings_default_profiles_unknown_keys.py`.
- Goldens `tests/golden/skills/aitask-brainstorm-discuss/SKILL-{default,fast,remote}-claude.md` +
  `tests/golden/procs/aitask-brainstorm-discuss/*-default.md` (regeneration loop from
  `skill_authoring_conventions.md:484-497`), same commit as the template.
- Tests: `tests/test_skill_render_aitask_brainstorm_discuss.sh` (model: `test_skill_render_aitask_trail.sh` /
  `_shadow.sh` incl. Test 0 procedure inventory, invariance, per-agent ref rewrites, stub markers);
  **[skill_contract_test]** `tests/test_brainstorm_discuss_skill_contract.sh` (model:
  `test_trail_skill_contract.sh`) — see Risk.
- Gate: `./.aitask-scripts/aitask_skill_verify.sh`; also `test_skill_dispatch_contract.sh`,
  `test_opencode_skill_legacy_pointers.sh`, `test_opencode_setup.sh`.
- Read first: `aidocs/framework/skill_authoring_conventions.md`, `stub-skill-pattern.md`.

### t1823_3 — `codeagent_discuss_operation` (feature, effort medium)
- `.aitask-scripts/aitask_codeagent.sh`: `SUPPORTED_OPERATIONS` (:26, keep single line), skill-arg
  validation alternation (:443), claudecode arm (`"/aitask-brainstorm-discuss ${args[*]}"`), codex
  composer arm (`build_skill_prompt "\$aitask-brainstorm-discuss"`), opencode arm, `--help` text.
- Defaults: `aitasks/metadata/codeagent_config.json` + `seed/codeagent_config.json` key `discuss`
  (same model as `shadow`); `settings_app.py` `OPERATION_DESCRIPTIONS["discuss"]`.
- Tests: extend `tests/test_codeagent.sh` lists (`skill_operations` :213, `codex_operations`/`codex_skills`
  :236-237, TUI-override loop :258); new `tests/test_codeagent_discuss.sh` (model `test_codeagent_trail.sh`:
  dry-run per agent, multi-node argv, whitespace/empty refusal);
  **[unwired_op_guard]** — see Risk.
- Docs pinned by test: `website/content/docs/commands/codeagent.md` Operations table row
  (`tests/test_website_doc_lists.sh`); run `python3 check_links.py --build`.

### t1823_4 — `brainstorm_tui_discuss_op` (feature, effort medium)
- `constants.py`: `_ANY_NODE_OPS = ("discuss",)`; `_OPERATION_HELP["discuss"]`; add `"discuss"` to the
  confirm-step exclusion tuple (:386) defensively.
- `utils.py` `op_states_for_selection`: `for op in _ANY_NODE_OPS: states[op] = (False, "")`.
- `modals.py` `NodeActionSelectModal`: append `"discuss"` to `_OPS`; `_LOCAL_LABELS["discuss"]`.
- `brainstorm_app.py`: in `_on_node_action_result`, `if op_key == "discuss": self._launch_discuss(node_id); return`
  before the wizard push. `_launch_discuss` copies `codebrowser_app.py:1469-1531`:
  targets = `sorted(self._selection.effective()) or [node_id]`, filtered to nodes still in
  `list_nodes()`; `resolve_agent_binary` pre-flight; `resolve_dry_run_command(root, "discuss", str(task_num), *targets)`;
  `AgentCommandScreen(..., operation="discuss", operation_args=[...], skill_name="brainstorm-discuss",
  default_profile=resolve_skill_profile("brainstorm-discuss", root), default_window_name=f"agent-discuss-{task_num}")`;
  on `TmuxLaunchConfig` → `launch_in_tmux(screen.full_command, cfg)` + `maybe_spawn_minimonitor`.
  **Every dialog result dispatches the finalized `screen.full_command` verbatim** — the dialog's
  agent/model picker, temporary profile override and manual edits all land there (`run_terminal`
  calls `_store_command()` then dismisses the bare string `"run"`), so rebuilding the default wrapper
  argv would launch a different configuration from the one shown. On `"run"`: copy the board's
  `run_dialog_command` (`aitask_board.py:11113`, the t1225 fix): `args = ["sh", "-c", screen.full_command]`
  → `find_terminal()` + `spawn_in_terminal(terminal, args, cwd=root)`, else `with self.suspend(): subprocess.call(args)`.
  Do NOT copy codebrowser's `_run_agent_command("explain", arg)` here — it rebuilds defaults.
  Default reconstruction (`[wrapper, "invoke", "discuss", str(task_num), *targets]`) is reserved for the
  single path where no dialog was available (`resolve_dry_run_command` returned `None`).
  No raw tmux (`tests/test_no_raw_tmux.sh`). Allowed in read-only sessions? No — `_open_operations_dialog`
  already gates the dialog; leave that gate unchanged.
- **Sequencing:** t1816 (Implementing) rewrites `modals.py` dismiss sites. This child is last in the
  chain, so rebase on whatever t1816 landed and use its dismiss guard in any new dismiss/callback code.
- Tests: update `test_brainstorm_node_action_modal.py` pinned `_OPS` order + the stale
  "fast_track is the only helpless op" comment; add relevance tests (discuss enabled at cardinality 1 and ≥2,
  on root) to `test_brainstorm_node_action_relevance.py`; new `tests/test_brainstorm_discuss_launch.py`
  (stub `resolve_dry_run_command`/`launch_in_tmux`: asserts argv = task_num + sorted marked set, no wizard
  pushed, no crew agent registered, vanished-node notify). **Regression check for finalized-command
  preservation:** drive the result callback with a screen whose `full_command` was changed to a
  different model AND a temporary profile (e.g. `... --model <other> '/aitask-brainstorm-discuss --profile default 42 n001'`),
  result `"run"`, with `spawn_in_terminal`/`subprocess.call` stubbed — assert the dispatched argv is
  `["sh","-c",<that exact string>]` and contains neither the default model nor a rebuilt wrapper argv;
  same assertion for the `TmuxLaunchConfig` result; and a separate case proving the wrapper-argv
  reconstruction fires only when `resolve_dry_run_command` returns `None`. Follow `testing_conventions.md` for `run_test` + workers.
- Read first: `aidocs/framework/tui_conventions.md`, `tmux_gateway.md`.

### t1823_5 — `discuss_op_docs` (documentation, effort low)
Per planning convention, docs for a user-visible TUI feature are a sibling, created before the
manual-verification sibling (this overrides the task body's "docs = follow-up" note).
`website/content/docs/tuis/brainstorm/reference.md` (operations table, Operations-dialog keys),
`how-to.md`, new `website/content/docs/skills/aitask-brainstorm-discuss.md` linked from `skills/_index.md`
(test-pinned). Current-state-only prose; generic agent wording; `check_links.py --build`.

### Manual-verification sibling
Offered through the standard post-child-creation prompt (live launch in tmux window / split / no-tmux
terminal; one node vs marked set; fast start; agent stays read-only).

## Upstream defect noticed during planning (hand to a follow-up bug task, not fixed here)
`.aitask-scripts/codebrowser/codebrowser_app.py:1509-1510, 1523-1531` — the Explain dialog's `"run"`
result calls `_run_agent_command("explain", arg)`, rebuilding the default wrapper argv and discarding
the dialog's agent/model/profile/edit changes (the t1225 class of bug, fixed on the board only).

## Follow-ups to suggest at the end (not children)
Codex CLI and OpenCode behavioural ports of the skill (per CLAUDE.md); direct key binding; write-back
("suggest an op") from a discussion; section-scoped discussion once t571 lands.

## Post-approval sequence (Step 6 → checkpoint)
1. Externalize this plan to `aiplans/p1823_brainstorm_discuss_proposals_interactive_agent.md`.
2. Create the 5 children via the Batch Task Creation Procedure (`mode: child`, parent 1823), write
   and commit all child plans under `aiplans/p1823/` by explicit path.
3. Revert parent to `Ready` (clear `assigned_to` / `plan_approved_at`), release parent lock.
4. Manual-verification sibling prompt → child checkpoint (start `1823_1` or stop).
Step 9 (archival/merge) applies per child; the parent archives when the last child does.

### Post-phase (risk mitigations)
This parent has no numbered implementation body (it decomposes), so each inline mitigation is
carried into the named child's task file and plan as an explicit, name-labeled step.
1. [unwired_op_guard] In t1823_3: add a test (in `tests/test_codeagent_discuss.sh` or a new
   `tests/test_codeagent_op_wiring.sh`) that parses `SUPPORTED_OPERATIONS` and, for every
   skill-backed op (the `:443` alternation set), asserts `--dry-run invoke <op> x` prints a
   `DRY_RUN:` line containing a non-empty `/aitask-…` prompt for `claudecode` and `opencode`, and
   that every op with a slash-command arm is in the validation alternation. Negative control: a
   sed-mutated copy of the script with a fake op in line 26 only must make the test fail.
2. [skill_contract_test] In t1823_2: `tests/test_brainstorm_discuss_skill_contract.sh` renders the
   `default` variant and asserts: the "Guardrail — advisory only (load-bearing)" section names
   proposal files / node YAML / session state; Step 0 runs `aitask_brainstorm_context.sh` and
   forbids up-front analysis; the menu-derivation maintainer comment is present and Step 0 contains
   no hardcoded shortcode list; every procedure file carries the `**Advisory-only:**` header; the
   string `===AITASK-CONCERNS===` appears nowhere in the **walked closure** (iterate the rendered
   per-profile tree that `walk-write` produces into a temp root — not just the authoring dir), and
   no `aitask-shadow-*` directory is rendered as a side effect. Negative control: a temp copy of the
   skill whose `discuss-audience.md` mentions `aitask-shadow/round-preamble.md` must make the test fail.

## Verification (whole feature, after the last child)
- `bash tests/test_brainstorm_context_helper.sh`, `test_codeagent.sh`, `test_codeagent_discuss.sh`,
  `test_skill_render_aitask_brainstorm_discuss.sh`, `test_brainstorm_discuss_skill_contract.sh`,
  `test_website_doc_lists.sh`, `test_no_raw_tmux.sh`, `test_touchpoint_count_contract.sh`
- `./.aitask-scripts/aitask_skill_verify.sh`; `shellcheck .aitask-scripts/aitask_*.sh`
- `bash tests/run_all_python_tests.sh` — read only the last `PYTHON SUITE:` line
- Live: `ait brainstorm <N>` → mark 2 nodes → `A` → Discuss → agent dialog → tmux window; agent lists
  `A`/`B` with titles immediately, offers the `>` menu, and `git status` in the crew worktree stays clean.

## Risk

### Code-health risk: low
- Codeagent operation list is duplicated across ~8 heterogeneous sites; an op added to line 26 but missed in a claudecode/opencode arm or the validation alternation yields a silent empty prompt / unvalidated args · severity: low (residual — addressed by inline post-phase unwired_op_guard) · → mitigation: inline post-phase unwired_op_guard
- Pinned `_OPS` order and "first row is explore" assumptions in brainstorm modal tests; concurrent t1816 edits to `modals.py` · severity: low · → mitigation: none (append-last placement + child ordered after t1816)

### Goal-achievement risk: medium
- The skill's defining behaviours (fast start with no up-front analysis, lazy context, menu derived from the capability section, advisory-only guardrail) are prose with no mechanical guard; a later edit can silently drop them · severity: low (residual — addressed by inline post-phase skill_contract_test; a contract test pins wording, not the live agent's behaviour) · → mitigation: inline post-phase skill_contract_test
- Launch path outside tmux and multi-node argv are only exercised by stubs until manual verification · severity: low · → mitigation: none (manual-verification sibling)

### Planned mitigations
- timing: post-phase | name: unwired_op_guard | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: codeagent op list duplicated across ~8 sites, fail-open on claudecode/opencode | desc: guard test that every skill-backed SUPPORTED_OPERATIONS op is wired and validated for claudecode and opencode (lands in t1823_3)
- timing: post-phase | name: skill_contract_test | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: skill's defining behaviours are prose-only | desc: contract test pinning the rendered skill's load-bearing guardrail, fast-start and menu-derivation properties (lands in t1823_2)
