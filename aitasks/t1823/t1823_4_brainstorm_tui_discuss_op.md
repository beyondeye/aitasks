---
priority: medium
effort: medium
depends: [t1823_3]
issue_type: feature
status: Implementing
labels: [ait_brainstorm, tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1823
implemented_with: claudecode/opus5
created_at: 2026-09-17 09:51
updated_at: 2026-09-18 12:12
---

## Context

Parent t1823: add a node operation to the `ait brainstorm` TUI that launches an
interactive, **advisory-only** code agent over the proposal file(s) of the cursor
node or the space-marked set. Siblings already landed: t1823_1 (context helper),
t1823_2 (skill `aitask-brainstorm-discuss`), t1823_3 (codeagent operation
`discuss`, argv `<task_num> <node_id>...`). This child is the TUI surface: a row
in the Operations dialog (`A`) and the launch path.

Settled: **dialog row only, no new app-level key binding**; the op never enters
the wizard and **never registers a crew agent**; launch UX is agent dialog first
(`AgentCommandScreen`: agent/model + window-vs-split), then tmux, with a terminal
fallback when tmux is unavailable.

Parent plan: `aiplans/p1823_brainstorm_discuss_proposals_interactive_agent.md`.
**Read first:** `aidocs/framework/tui_conventions.md`, `aidocs/framework/tmux_gateway.md`,
`aidocs/framework/testing_conventions.md` (App.run_test + `@work` workers).

## Sequencing

t1816 (guard modal dismiss against stale screen) was `Implementing` at planning
time and converts brainstorm's ~46 dismiss sites in `modals.py`, including
`NodeActionSelectModal`. Check its state first; build on whatever it landed and
use its dismiss guard in any new dismiss/callback code. This child's `modals.py`
edit is two additive lines, so a textual conflict is unlikely — a semantic one
(new code bypassing the guard) is the thing to avoid.

## Key files to modify (`.aitask-scripts/brainstorm/`; line numbers as of planning)

- `constants.py`: new cardinality class `_ANY_NODE_OPS = ("discuss",)` beside
  `_SINGLE_NODE_OPS`/`_MODULE_OPS`/`_MULTI_NODE_OPS` (~:404-410);
  `_OPERATION_HELP["discuss"]` (title/summary/use_cases — see `module_sync` entry
  ~:235 for the shape); add `"discuss"` to the confirm-step exclusion tuple
  `c.get("op") not in ("", "delete")` (~:386) defensively. Do **NOT** add it to
  `_DESIGN_OPS` — that list is the wizard Step-1 row source.
- `utils.py` `op_states_for_selection` (~:406-462):
  `for op in _ANY_NODE_OPS: states[op] = (False, "")` — enabled at any cardinality
  ≥1, including the root node. (The modal already defaults unknown keys to
  enabled, but that is implicit and untested; the explicit class is the contract.)
- `modals.py` `NodeActionSelectModal` (~:1272-1287): append `"discuss"` at the
  **END** of `_OPS` (after `delete`) and add `_LOCAL_LABELS["discuss"]`
  (e.g. `("Discuss", "Talk the selected proposal(s) over with an advisory agent — read-only")`).
  Appending last is deliberate: several tests assume the first enabled row is
  `explore` and that one `down` lands on `compare`.
- `brainstorm_app.py`:
  - `_on_node_action_result` (~:2941-2977): after the node-exists check and beside
    the `delete` branch, `if op_key == "discuss": self._launch_discuss(node_id); return`
    — BEFORE the `ActionsWizardScreen` push.
  - new `_launch_discuss(node_id)`:
    `targets = sorted(self._selection.effective()) or [node_id]`, filtered to ids
    still in `list_nodes(self.session_path)` (the DAG can mutate while the modal
    is open; notify and return if none remain).
    Pre-flight the agent binary as codebrowser does (`resolve_agent_binary`,
    `shutil.which`). `args = [str(self.task_num), *targets]`;
    `full_cmd = resolve_dry_run_command(root, "discuss", *args)`;
    `AgentCommandScreen(title, full_cmd, "/aitask-brainstorm-discuss " + " ".join(args),
    default_window_name=f"agent-discuss-{self.task_num}", project_root=root,
    operation="discuss", operation_args=args,
    default_agent_string=resolve_agent_string(root, "discuss"),
    skill_name="brainstorm-discuss",
    default_profile=resolve_skill_profile("brainstorm-discuss", root))`.
    Window name MUST start with `agent-`: `maybe_spawn_minimonitor` returns `None`
    for names starting with `brainstorm-`.
  - imports from `agent_launch_utils` (today only `is_tmux_available`):
    `find_terminal, spawn_in_terminal, resolve_dry_run_command, resolve_agent_string,
    TmuxLaunchConfig, launch_in_tmux, maybe_spawn_minimonitor`; from
    `agent_command_screen`: `AgentCommandScreen, resolve_skill_profile`.

## Launch-result contract (load-bearing — a plan-review finding)

`AgentCommandScreen` dismisses with `None` (cancel) | `"run"` | a `TmuxLaunchConfig`.
The dialog's agent/model picker, temporary profile override and manual command
edits all land in **`screen.full_command`** (`run_terminal` calls
`_store_command()` and then dismisses the bare string `"run"`;
`agent_command_screen.py:773-776, 871, 1051, 1083, 1185`).

**Every dialog result must dispatch the finalized `screen.full_command` verbatim.**
- `TmuxLaunchConfig` → `launch_in_tmux(screen.full_command, cfg)`; on error notify;
  on `cfg.new_window` → `maybe_spawn_minimonitor(cfg.session, cfg.window)`. Pass
  the BARE command (the pane pid must be the agent pid). No raw tmux anywhere.
- `"run"` → copy the board's `run_dialog_command`
  (`.aitask-scripts/board/aitask_board.py:11113`, the t1225 fix):
  `args = ["sh", "-c", screen.full_command]` → `find_terminal()` +
  `spawn_in_terminal(terminal, args, cwd=root)`, else
  `with self.suspend(): subprocess.call(args)`.
- **Do NOT copy codebrowser's `_run_agent_command("explain", arg)`**
  (`codebrowser_app.py:1509-1531`): it rebuilds the default wrapper argv, so a
  user who picked another model/profile and pressed "Run in terminal" launches a
  different configuration from the one shown.
- Default reconstruction `[wrapper, "invoke", "discuss", str(task_num), *targets]`
  is reserved for the single path where no dialog was available
  (`resolve_dry_run_command` returned `None`).

## Tests

- `tests/test_brainstorm_node_action_modal.py`: update the pinned `_OPS` order in
  `test_all_ops_listed_and_enabled_without_op_states` (~:99); fix the stale
  comment at ~:238 claiming `fast_track` is the only op without `_OPERATION_HELP`.
- `tests/test_brainstorm_node_action_relevance.py`: `discuss` enabled at
  cardinality 1, at ≥2, and on the root node; add `_ANY` to the local class tuples.
- NEW `tests/test_brainstorm_discuss_launch.py` (stub `resolve_dry_run_command`,
  `launch_in_tmux`, `spawn_in_terminal`, `subprocess.call`):
  - picking `discuss` pushes `AgentCommandScreen`, never `ActionsWizardScreen`, and
    registers no crew agent;
  - argv = task_num + sorted marked set; cursor-only when nothing is marked;
  - vanished node → notify, no launch;
  - **finalized-command regression:** set `screen.full_command` to a string with a
    DIFFERENT model and a temporary profile (e.g.
    `… --model <other> '/aitask-brainstorm-discuss --profile default 42 n001'`),
    deliver result `"run"` → dispatched argv is exactly
    `["sh", "-c", <that string>]`, containing neither the default model nor a
    rebuilt wrapper argv; same assertion for a `TmuxLaunchConfig` result;
  - wrapper-argv reconstruction fires ONLY when `resolve_dry_run_command` returns `None`.
- `bash tests/test_no_raw_tmux.sh`; `tests/test_brainstorm_binding_scope.py` and
  `tests/test_brainstorm_node_action_integration.py` still pass (no new binding).

## Verification

- `bash tests/run_all_python_tests.sh` — read only the last `PYTHON SUITE:` line.
- Live (also covered by the manual-verification sibling): `ait brainstorm <N>` →
  mark 2 nodes → `A` → Discuss → dialog → tmux window; repeat with split, and with
  tmux unavailable.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1826** id=2026-09-17T19:48:33Z.47550a369973786c0784d333 from=t1826 from_verified=yes at=2026-09-17T19:48:33Z base=025ba5e9576de4c0064df0ca2b620b8381e64a70 base_branch=main dirty=yes host=omg16
>
> | New rule for any bash test this task adds (025ba5e95, t1826): every cd/pushd in tests/ must be exit-guarded (`cd "$X" || exit 1`) or a (`(`/`$(`)-confined && chain — `|| return`, `|| true`, `if cd`, `! cd` and `{ cd X && …; }` are rejected, targets must be quoted, and `# cd-guard: <reason>` is the reviewed escape hatch. A cwd-changing test also sources tests/lib/scratch_cwd.sh and calls enter_scratch_cwd right after PROJECT_DIR is derived, before any $(pwd) capture or dirname "$BASH_SOURCE" derivation. tests/test_cd_guard_lint.sh enforces it; see aidocs/framework/testing_conventions.md. Advisory only.

> **✉ note:t1823_3** id=2026-09-18T04:50:29Z.4e7cb84424ac27ba4b7adbc5 from=t1823_3 from_verified=yes at=2026-09-18T04:50:29Z base=7f7981bdd7bbbb97c2f91e17d221b584e9c14403 base_branch=main dirty=yes host=omg16
>
> | The `discuss` codeagent operation landed (t1823_3, commit 7f7981bdd). Two points
> | that affect your launch path:
> | 
> | 1. `_FRESH_WINDOW_OPERATIONS` in `.aitask-scripts/lib/agent_command_screen.py`
> |    does NOT list `discuss`. `trail` added itself to that frozenset in its own op
> |    commit; `shadow` is absent. Whether the Discuss dialog should default to a
> |    fresh window or a split is a launch-UX decision I deliberately left to you —
> |    t1823_3 changed nothing there.
> | 
> | 2. Argv shape is enforced fail-closed: every `discuss` argument must be
> |    non-empty and contain no whitespace, and the refusal fires under `--dry-run`
> |    too. So `resolve_dry_run_command(root, "discuss", task_num, *node_ids)` is a
> |    real pre-flight, not just a formatting call — a bad node id surfaces there.
> | 
> | 3. Defaults resolve to the `shadow` model: `codex/gpt5_6_terra` in
> |    `aitasks/metadata/codeagent_config.json`, `claudecode/opus5` in the seed.
> | 
> | A new cross-op guard (`tests/test_codeagent_op_wiring.sh`) now fails if any
> | skill-backed operation is wired only into `SUPPORTED_OPERATIONS`, for claudecode
> | and opencode.

> **👁 note:read** id=2026-09-18T05:06:04Z.48ea787b0092fc44233daf5a by=t1823_4 at=2026-09-18T05:06:04Z mode=explicit ids=2026-09-17T19:48:33Z.47550a369973786c0784d333,2026-09-18T04:50:29Z.4e7cb84424ac27ba4b7adbc5

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-18T09:12:23Z status=pass attempt=1 type=human
