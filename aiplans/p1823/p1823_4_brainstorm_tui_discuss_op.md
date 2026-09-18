---
Task: t1823_4_brainstorm_tui_discuss_op.md
Parent Task: aitasks/t1823_brainstorm_discuss_proposals_interactive_agent.md
Sibling Tasks: aitasks/t1823/t1823_1_*.md, aitasks/t1823/t1823_2_*.md, aitasks/t1823/t1823_3_*.md, aitasks/t1823/t1823_5_*.md
Archived Sibling Plans: aiplans/archived/p1823/p1823_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-18 12:10
---

# t1823_4: "Discuss" node operation and launch path in the brainstorm TUI

## Context

This task adds the advisory discuss agent to `ait brainstorm`. It becomes a row in the
Operations dialog (`A`) that acts on the cursor node or the space-marked set. Picking it
opens `AgentCommandScreen`, then launches `aitask_codeagent.sh invoke discuss <task_num>
<node_id>...` in tmux or in a terminal. It uses no wizard, registers no crew agent and adds
no key binding. The siblings are already in place: t1823_1 (context helper), t1823_2
(skill) and t1823_3 (codeagent op `discuss`).

## Verification findings (plan re-checked against the tree on 2026-09-18)

- **t1816 is Done.** Its guard lives in the base class (`lib/guarded_dismiss.py`), and every
  brainstorm screen already uses it. **But this task makes a new, unguarded dialog chain
  reachable from brainstorm** (a review finding, confirmed):
  - `AgentCommandScreen(ShortcutsMixin, ModalScreen)` at `lib/agent_command_screen.py:176`.
  - Its children: `AgentModelPickerScreen(ModalScreen)` (`lib/agent_model_picker.py:285`),
    `ProfileEditScreen(ModalScreen)` (`lib/profile_editor.py:796`), and the
    `EditStringScreen(ModalScreen)` that `ProfileEditScreen` pushes (`:573`).
  - A stale second `action_cancel` on a closed `AgentCommandScreen` pops the screen beneath
    it, and ends in `ScreenStackError`.
  - None of these files calls `pop_screen` or overrides `dismiss`, and no dismiss happens
    while a child is on top. The only parent-from-child dismissals run in result callbacks,
    after the child has popped, which the t1816 contract test
    `test_parent_dismiss_from_child_result_callback` already covers. So mixing in the guard
    only changes the stale-dismiss case. Step 0 fixes this.
- **The effective targets must be validated before the cursor guard** (a review finding,
  confirmed). `_on_node_action_result` returns early when the primary `node_id` is gone,
  before any branch runs. `NodeSelection` lets the cursor (C) differ from the marked set
  (A, B), so deleting C while the dialog is open would block a Discuss of A and B, which
  still exist. Step 4 routes Discuss ahead of that check.
- All anchors still hold:
  - `constants.py`: `_SINGLE_NODE_OPS`, `_MODULE_OPS`, `_MULTI_NODE_OPS` at ~:404-410; the
    confirm step `c.get("op") not in ("", "delete")` at :385; `_OPERATION_HELP["module_sync"]` at :235.
  - `utils.py` `op_states_for_selection` at :406.
  - `modals.py` `_OPS` and `_LOCAL_LABELS` at :1272-1287.
  - `brainstorm_app.py`: `_on_node_action_result` at :2942. It imports only
    `is_tmux_available` from `agent_launch_utils` (:104).
- **Window default (point 1 of t1823_3's note):** no change is needed.
  `should_default_to_new_window` already returns True for any `agent-*` window name
  (`_FRESH_WINDOW_PREFIXES`). So `agent-discuss-<N>` defaults to a new window without adding
  `discuss` to `_FRESH_WINDOW_OPERATIONS`. That set is left untouched.
- **Agent-binary pre-flight:** `resolve_agent_binary` lives in `codebrowser/agent_utils.py`.
  `codebrowser/` is a package (it has an empty `__init__.py`) and `..` is already on the
  brainstorm `sys.path`, so the import is `from codebrowser.agent_utils import resolve_agent_binary`.
- **Real dry-run check:** `aitask_codeagent.sh --dry-run invoke discuss 42 n001 n002` prints
  `DRY_RUN: codex … $aitask-brainstorm-discuss 42 n001 n002`.
- **Project root:** brainstorm has no root attribute. Use
  `Path(__file__).resolve().parent.parent.parent` (the repo root that owns this
  `.aitask-scripts/`), assigned once as the module constant `_REPO_ROOT`.
- **Existing gate unchanged (settled in the parent plan):** `_open_operations_dialog`
  refuses read-only sessions and sessions not in init/active status, so Discuss is
  unavailable there too.

## Steps

0. **Guard the newly reachable shared dialog chain** with the existing mechanism: mix in
   `GuardedDismissMixin` before the `Screen` base. Call sites keep their plain
   `self.dismiss(...)`.
   - `lib/agent_command_screen.py`:
     `class AgentCommandScreen(GuardedDismissMixin, ShortcutsMixin, ModalScreen)`.
     Add `from guarded_dismiss import GuardedDismissMixin`.
   - `lib/agent_model_picker.py`: `AgentModelPickerScreen` becomes `GuardedModalScreen`.
     `LaunchModePickerScreen`, in the same file and used by settings, gets the same change,
     so the module is uniformly guarded.
   - `lib/profile_editor.py`: `ProfileEditScreen` and `EditStringScreen` become
     `GuardedModalScreen`.
   - These dialogs are shared by board, codebrowser, monitor, minimonitor, syncer and
     settings. Behaviour changes only for a dismiss on an inactive screen: it becomes a
     logged no-op instead of popping the wrong screen.
1. **`.aitask-scripts/brainstorm/constants.py`**
   - Next to `_MULTI_NODE_OPS`, add `_ANY_NODE_OPS = ("discuss",)` with a one-line comment:
     enabled at any cardinality ≥1, including the root node.
   - Add `_OPERATION_HELP["discuss"]`, after `module_sync`, in the same shape:
     - `title`: "Discuss — Advisory Agent"
     - `summary`: an interactive, read-only code agent over the selected proposal(s) that
       compares them, explains one plainly, answers questions and checks the design for
       flaws. It creates no node and changes no file.
     - `reads_from_parent`: the proposal file(s) of the target node(s), plus ancestry
       context from the discuss context helper.
     - `produces`: nothing persisted, only a conversation in a tmux window or terminal.
     - `use_cases`: 2-3 entries.
   - Confirm step: change it to `c.get("op") not in ("", "delete", "discuss")`.
     This is defensive, because discuss never reaches the wizard.
   - Do not add it to `_DESIGN_OPS`.
2. **`.aitask-scripts/brainstorm/utils.py`**
   - Import `_ANY_NODE_OPS` into the existing `from brainstorm.constants import (...)` block.
   - Before `return states`, add `for op in _ANY_NODE_OPS: states[op] = (False, "")`.
   - Add a bullet to the docstring: any-node ops (discuss) are always enabled.
3. **`.aitask-scripts/brainstorm/modals.py` `NodeActionSelectModal`**
   - Append `"discuss"` to the end of `_OPS`, after `delete`. Update the ordering comment:
     discuss goes last because tests assume the first enabled row is explore.
   - Add `_LOCAL_LABELS["discuss"] = ("Discuss", "Talk the selected proposal(s) over with an advisory agent — read-only")`.
   - Update the class docstring's op list.
4. **`.aitask-scripts/brainstorm/brainstorm_app.py`**
   - **Imports:** extend `from agent_launch_utils import is_tmux_available` with
     `TmuxLaunchConfig, find_terminal, launch_in_tmux, maybe_spawn_minimonitor,
     resolve_agent_string, resolve_dry_run_command, spawn_in_terminal`. Also add
     `from agent_command_screen import AgentCommandScreen, resolve_skill_profile`,
     `from codebrowser.agent_utils import resolve_agent_binary`, and `import shutil`
     if it is missing. Define `_REPO_ROOT`.
   - **`_on_node_action_result`:** put
     `if op_key == "discuss": self._launch_discuss(node_id); return` immediately after
     `if not op_key: return`, before the single-cursor existence check. Discuss validates
     its own effective targets. The cursor check stays unchanged for every other op.
     Update the docstring.
   - **New `_launch_discuss(self, node_id)`:**
     - Compute `live = set(list_nodes(self.session_path))`,
       `wanted = sorted(self._selection.effective()) or [node_id]` and
       `targets = [n for n in wanted if n in live]`.
     - If `targets` is empty, notify "Selected node(s) no longer exist." as an error and return.
     - If some targets dropped out, notify a warning naming them (for example "Skipping
       vanished node(s): X"), then continue with the survivors. A vanished unmarked cursor is
       never among `wanted` when a marked set exists, so it raises no warning.
     - Run the binary pre-flight: `agent_name, binary, err = resolve_agent_binary(_REPO_ROOT, "discuss")`.
       If there is no binary, notify `err` or a generic message and return. If
       `shutil.which(binary)` fails, notify "`<agent> CLI (<binary>) not found in PATH`" and
       return. This matches `codebrowser_app.py:1475-1481`.
     - Set `args = [str(self.task_num), *targets]` and
       `full_cmd = resolve_dry_run_command(_REPO_ROOT, "discuss", *args)`.
     - If `full_cmd is None`, call `self._run_discuss_default(args)`. This is the only place
       the wrapper argv is rebuilt.
     - Otherwise push `AgentCommandScreen(f"Discuss {', '.join(targets)}", full_cmd,
       "/aitask-brainstorm-discuss " + " ".join(args),
       default_window_name=f"agent-discuss-{self.task_num}", project_root=_REPO_ROOT,
       operation="discuss", operation_args=args,
       default_agent_string=resolve_agent_string(_REPO_ROOT, "discuss"),
       skill_name="brainstorm-discuss",
       default_profile=resolve_skill_profile("brainstorm-discuss", _REPO_ROOT))`.
       The callback is `lambda result, s=screen: self._on_discuss_dialog_result(s, result)`.
   - **New `_on_discuss_dialog_result(self, screen, result)`:** always dispatch
     `screen.full_command` verbatim.
     - `isinstance(result, TmuxLaunchConfig)` → `_, err = launch_in_tmux(screen.full_command, result)`.
       On `err`, notify it as an error. Otherwise, if `result.new_window`, call
       `maybe_spawn_minimonitor(result.session, result.window)`.
     - `result == "run"` → `self._run_dialog_command(screen.full_command)`.
     - `None` or anything else → do nothing.
   - **New `_run_dialog_command(self, command)`:** the board's t1225 pattern
     (`board/board_trail_screen.py:1044`).
     - Set `argv = ["sh", "-c", command]`.
     - If `find_terminal()` returns a terminal, call
       `spawn_in_terminal(terminal, argv, cwd=str(_REPO_ROOT))`.
     - Otherwise run `with self.suspend(): subprocess.call(argv, cwd=str(_REPO_ROOT))`.
     - It is a plain synchronous method, not a `@work` worker, so no in-flight worker can
       outlive `run_test` (see testing_conventions).
     - Do not copy codebrowser's `_run_agent_command`.
   - **New `_run_discuss_default(self, args)`:** set
     `argv = [str(_REPO_ROOT / ".aitask-scripts" / "aitask_codeagent.sh"), "invoke", "discuss", *args]`,
     then use the same terminal-or-suspend dispatch. Factor the dispatch into one small
     helper, `_dispatch_argv(argv)`, that both methods share.
5. **Tests**
   - **`tests/test_brainstorm_node_action_modal.py`**
     - Append `"discuss"` to the pinned `_OPS` order (~:113).
     - Reword the stale comment at ~:238 to "fast_track has no `_OPERATION_HELP` entry".
       It currently says "the only op", which becomes wrong only if discuss lacks help, and
       discuss will have help. Keep the sentence accurate.
   - **`tests/test_brainstorm_node_action_relevance.py`**
     - Add `_ANY = ("discuss",)`.
     - Add `test_any_node_ops_enabled_at_every_cardinality`: 1 and 3 with `_FULL_CTX`, plus a
       root/umbrella ctx `{"is_root": True, "is_umbrella": True}` at 1.
   - **NEW `tests/test_brainstorm_discuss_launch.py`**
     - Harness: the temp-session setup from `test_brainstorm_node_action_integration.py`.
       Boot `BrainstormApp` under `run_test`, and patch `brainstorm_app` module attributes
       with `unittest.mock.patch`: `resolve_agent_binary`, `shutil.which`,
       `resolve_dry_run_command`, `resolve_agent_string`, `resolve_skill_profile`,
       `launch_in_tmux`, `maybe_spawn_minimonitor`, `find_terminal`, `spawn_in_terminal`,
       and `subprocess.call`.
     - Replace `app.push_screen` with a recorder that captures `(screen, callback)`.
     - Replace `app.suspend` with a `nullcontext` factory.
     - Cases:
       1. `_on_node_action_result(n, "discuss")` pushes exactly one `AgentCommandScreen`
          and no `ActionsWizardScreen`. The crew worktree's agent/status files are unchanged,
          so no crew agent was registered. The screen's `operation_args == [task_num, n]`
          (cursor-only).
       2. With 2 marked nodes, `operation_args == [task_num, *sorted(marked)]`, and the
          dry-run stub received the same args.
       3. All targets vanished (`brainstorm_app.list_nodes` is patched to miss them): an
          error notice, nothing pushed.
       3b. **Vanished unmarked cursor, surviving marked targets.** Mark A and B, set the
          cursor to C, and make `list_nodes` miss only C. Call
          `_on_node_action_result(C, "discuss")`: an `AgentCommandScreen` is pushed with
          `operation_args == [task_num, A, B]`, and no "no longer exists" error appears.
          Control case: for a non-discuss op (for example `explore`), the same state still
          hits the cursor guard and pushes nothing.
       3c. A marked set partly vanished (A survives, B is gone): launches with `[A]` and
          warns naming B.
       4. **Finalized-command regression, `"run"`:** set `screen.full_command` to
          `"codex -m other-model '/aitask-brainstorm-discuss --profile default 42 n001'"`
          and call the callback with `"run"`. `spawn_in_terminal` receives exactly
          `["sh", "-c", <that string>]`. The argv contains neither the default model nor
          `aitask_codeagent.sh`.
       5. The same regression for a `TmuxLaunchConfig(new_window=True, …)` result:
          `launch_in_tmux` receives the edited string verbatim, and `maybe_spawn_minimonitor`
          is called once.
       6. The same regression through the suspend fallback (`find_terminal` returns None):
          `subprocess.call` receives `["sh","-c",<edited>]`.
       7. A dry-run returning `None` sends no `AgentCommandScreen`, and `spawn_in_terminal`
          receives `[wrapper, "invoke", "discuss", task_num, n]`. In every other case the
          wrapper argv never appears.
       8. A missing binary (`which` returns None) notifies and launches nothing.
     - Python only; no bash test is added, so the cd-guard rule from t1826's note does not apply.
   - **`tests/test_brainstorm_guarded_dismiss.py`: extend it to the shared dialog chain.**
     The launch tests above record `push_screen`, so they bypass the real screen stack and
     cannot show stale-dismiss behaviour.
     - New `SharedLaunchDialogGuardTests`, with an inspect-based check that every `Screen`
       subclass defined in `agent_command_screen`, `agent_model_picker` and `profile_editor`
       is a `GuardedDismissMixin` subclass (at least 5 checked).
     - Mounted stale-dismiss tests, each run on `_StackHost`: push a guarded parent, then
       push the real screen, call the close action 3 times with a `pilot.pause()` between
       calls, and assert that `app.screen is parent` and `app.is_running`. The screens are:
       - a real `AgentCommandScreen("t", "echo x", "/p", project_root=REPO_ROOT)` via
         `action_cancel`;
       - `EditStringScreen("k", "v")` via its cancel action;
       - `AgentModelPickerScreen` via its cancel action, if it mounts headless with simple
         args; otherwise it is covered by the class check only.
     - Red proof: before Step 0, the `AgentCommandScreen` mounted test must fail with
       `ScreenStackError` or a popped parent. Confirm this by running it before applying
       Step 0.
     - Also run the other suites touching these dialogs: `tests/test_agent_command_screen*.py`,
       `tests/test_profile_editor*.py` and `tests/test_agent_model_picker*.py`, whichever exist.
6. **Step 9 (Post-Implementation):** cleanup, archival and merge per the task workflow.

## Verification

- `bash tests/run_all_python_tests.sh`: read only the last `PYTHON SUITE:` line. Also run
  the targeted modules directly: modal, relevance, integration, binding_scope,
  discuss_launch and guarded_dismiss.
- Live check: in the brainstorm Discuss dialog, press Esc rapidly several times. The dialog
  closes and brainstorm stays up; the old behaviour was that the Browse screen was popped
  or the TUI died.
- `bash tests/test_no_raw_tmux.sh` and `bash tests/test_codeagent_op_wiring.sh` pass.
- `shellcheck` is not applicable (no shell change).
- In `ait brainstorm <N>`, `A` on a single node shows an enabled Discuss row last in the list.
  With 2 marked nodes it is still enabled, and the dialog's prompt lists both node ids.
- In the agent dialog, change the model and choose "Run in tmux" (new window). The launched
  pane runs the changed model and a minimonitor companion appears.
- In the agent dialog, change the model and choose "Run in terminal". The terminal runs the
  changed model, not the default.
- Split placement works, and with tmux unavailable the terminal fallback launches.
- No crew agent appears in the Running tab, and Discuss creates no node.

## Risk

### Code-health risk: medium
- Step 0 changes the base class of shared dialogs used by six TUIs. It is
  behaviour-preserving for an active dismiss, and a dismiss that relied on popping from
  beneath would now silently stop closing the dialog · severity: medium · → mitigation:
  none; verified that no such site exists, and the full Python suite covers the other hosts
- A third copy of the "dispatch the dialog's `full_command` via `sh -c` in a terminal or
  under suspend" pattern (board trail screen, board, now brainstorm) · severity: low ·
  → mitigation: lift_dialog_command_dispatch
- New imports into `brainstorm_app.py` (`codebrowser.agent_utils`, `agent_command_screen`)
  widen its import surface. A failure at import time would break the whole TUI, not just
  Discuss · severity: low · → mitigation: none (existing integration tests import `brainstorm_app`)

### Goal-achievement risk: low
- The `resolve_dry_run_command → None` fallback also fires when the op's fail-closed argv
  check refuses. The rebuilt-argv terminal then shows the wrapper's refusal and may close
  before it can be read. This is accepted per the settled parent-plan design, and node ids
  are whitespace-free by construction · severity: low · → mitigation: none (settled design)

### Planned mitigations
- timing: after | name: lift_dialog_command_dispatch | type: refactor | priority: low | effort: low | inline_risk: medium | added_complexity: medium | addresses: code-health — third copy of the dialog full_command sh -c dispatch | desc: Lift the "dispatch AgentCommandScreen full_command via sh -c in a terminal or under suspend" pattern (board_trail_screen.run_dialog_command, brainstorm _run_dialog_command/_dispatch_argv) into one lib/ helper and migrate the callers
