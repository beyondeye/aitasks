---
Task: t1823_4_brainstorm_tui_discuss_op.md
Parent Task: aitasks/t1823_brainstorm_discuss_proposals_interactive_agent.md
Sibling Tasks: aitasks/t1823/t1823_1_*.md, aitasks/t1823/t1823_2_*.md, aitasks/t1823/t1823_3_*.md, aitasks/t1823/t1823_5_*.md
Archived Sibling Plans: aiplans/archived/p1823/p1823_*_*.md
Base branch: main
Output branch: main
---

# t1823_4 — Brainstorm TUI "Discuss" node operation + launch path

## Context

Surface the advisory discuss agent in `ait brainstorm`: a row in the Operations
dialog (`A`) acting on the cursor node or the space-marked set, opening
`AgentCommandScreen` and launching `aitask_codeagent.sh invoke discuss <task_num>
<node_id>...` in tmux (or a terminal). No wizard, no crew agent, no new key binding.

Read first: `aidocs/framework/tui_conventions.md`, `tmux_gateway.md`,
`testing_conventions.md`. Parent plan:
`aiplans/p1823_brainstorm_discuss_proposals_interactive_agent.md`.

## Sequencing — check t1816 first

t1816 converts brainstorm's dismiss sites in `modals.py` (incl.
`NodeActionSelectModal`). If it has landed, use its dismiss guard in new
callback/dismiss code; if it is still in flight, keep this child's `modals.py`
edit to the two additive lines below and send t1816 an `/aitask-note` only if a
semantic overlap appears.

## Steps

1. `constants.py`: `_ANY_NODE_OPS = ("discuss",)`; `_OPERATION_HELP["discuss"]`
   (title, summary, use_cases — shape of the `module_sync` entry); add `"discuss"`
   to the confirm-step exclusion tuple. NOT in `_DESIGN_OPS`.
2. `utils.py` `op_states_for_selection`: import the class;
   `for op in _ANY_NODE_OPS: states[op] = (False, "")`.
3. `modals.py` `NodeActionSelectModal`: append `"discuss"` at the END of `_OPS`;
   `_LOCAL_LABELS["discuss"] = ("Discuss", "<read-only advisory agent over the selected proposal(s)>")`.
4. `brainstorm_app.py`:
   - imports: `find_terminal, spawn_in_terminal, resolve_dry_run_command,
     resolve_agent_string, TmuxLaunchConfig, launch_in_tmux, maybe_spawn_minimonitor`
     (agent_launch_utils); `AgentCommandScreen, resolve_skill_profile`
     (agent_command_screen); agent-binary pre-flight as codebrowser does.
   - `_on_node_action_result`: `if op_key == "discuss": self._launch_discuss(node_id); return`
     beside the `delete` branch, before the wizard push.
   - `_launch_discuss(node_id)`: targets = `sorted(self._selection.effective()) or [node_id]`
     ∩ `list_nodes(self.session_path)` (none left → notify, return);
     `args = [str(self.task_num), *targets]`;
     `full_cmd = resolve_dry_run_command(root, "discuss", *args)`;
     `full_cmd is None` → `self._run_discuss_default(args)` (the ONLY place the
     wrapper argv `[wrapper, "invoke", "discuss", *args]` is rebuilt);
     else push `AgentCommandScreen(title, full_cmd, "/aitask-brainstorm-discuss " + " ".join(args),
     default_window_name=f"agent-discuss-{self.task_num}", project_root=root,
     operation="discuss", operation_args=args,
     default_agent_string=resolve_agent_string(root, "discuss"),
     skill_name="brainstorm-discuss",
     default_profile=resolve_skill_profile("brainstorm-discuss", root))`.
   - result callback — **dispatch `screen.full_command` verbatim for every result**:
     `TmuxLaunchConfig` → `launch_in_tmux(screen.full_command, cfg)`; error → notify;
     `cfg.new_window` → `maybe_spawn_minimonitor(cfg.session, cfg.window)`.
     `"run"` → `_run_dialog_command(screen.full_command)`: `args = ["sh","-c",cmd]`;
     `find_terminal()` → `spawn_in_terminal(terminal, args, cwd=root)` else
     `with self.suspend(): subprocess.call(args)` (the board's t1225 pattern,
     `aitask_board.py:11113`). Do NOT copy codebrowser's
     `_run_agent_command("explain", arg)` — it discards dialog changes.
5. Tests: update pinned `_OPS` order + stale "only helpless op" comment in
   `test_brainstorm_node_action_modal.py`; relevance tests for `discuss`
   (cardinality 1, ≥2, root); NEW `tests/test_brainstorm_discuss_launch.py`
   (no wizard / no crew agent; argv = task_num + sorted marked set; vanished node;
   **finalized-command regression** with a changed model AND temporary profile for
   both `"run"` and `TmuxLaunchConfig`; default reconstruction only when
   `resolve_dry_run_command` is `None`).

## Verification

- `bash tests/run_all_python_tests.sh` — last line `PYTHON SUITE: PASSED`
- `bash tests/test_no_raw_tmux.sh` passes
- In `ait brainstorm <N>`: `A` on a single node shows an enabled Discuss row last in the list; with 2 marked nodes it is still enabled and the dialog's prompt lists both node ids
- In the agent dialog, change the model, choose "Run in tmux" (new window): the launched pane runs the changed model and a minimonitor companion appears
- In the agent dialog, change the model and choose "Run in terminal": the terminal runs the changed model, not the default
- Split placement works; with tmux unavailable the terminal fallback launches
- No crew agent appears in the Running tab and no node is created by Discuss

## Post-implementation

Step 9 of the task workflow.
