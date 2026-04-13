---
priority: medium
effort: medium
depends: [t461_2]
issue_type: feature
status: Ready
labels: [brainstorming, agentcrew]
created_at: 2026-04-13 11:44
updated_at: 2026-04-13 11:44
---

## Context

Parent task t461 lets users mark a code agent to launch in interactive
mode inside a tmux window. t461_1 adds the schema + runner support and
the `--launch-mode` flag on `ait crew addwork`. This task exposes that
capability in the **brainstorm TUI wizard flow** so users can toggle
"Force interactive mode" while creating a new brainstorm operation.

## Key Files to Modify

- `.aitask-scripts/brainstorm/brainstorm_app.py` — the wizard step logic:
  - `_actions_show_config()` (around line 1906) and the per-op config
    mounters: `_config_explore_no_node` (1935), `_config_compare` (1944),
    `_config_hybridize` (1962), `_config_patch_no_node` (1974).
  - The config collectors `_actions_collect_config()` (2015-2056) that
    read user inputs into `self._wizard_config`.
  - `_run_design_op()` (around line 2240) that calls the register_*
    functions.
  - Detail operation has no separate config step — add the toggle
    inline next to its confirm button.
- `.aitask-scripts/brainstorm/brainstorm_crew.py` — register_* functions
  (`register_explorer`, `register_comparator`, `register_synthesizer`,
  `register_detailer`, `register_patcher`) and `_run_addwork()` helper
  (lines 86-119) that builds the `ait crew addwork` command.

## Reference Files for Patterns

- Existing wizard input widgets in `brainstorm_app.py` — e.g., the
  Parallel CycleField in `_config_explore_no_node()` shows how to mount
  a new input widget and wire it into `_wizard_config`.
- `.aitask-scripts/lib/agent_launch_utils.py:is_tmux_available()` — use
  to disable the toggle (show read-only hint) if tmux is NOT installed,
  so the user is not offered a mode that will fall back to a
  standalone terminal.

## Implementation Plan

1. **Add a "Force interactive mode" toggle widget** to each per-op
   config panel:
   - Use Textual's `Switch` widget (or a simple two-state `CycleField`
     matching the existing style). Label: "Force interactive mode" with
     a small help line: "Launch in a tmux window so `ait monitor` can
     see it. Useful for watching long-running operations."
   - Store the ID in a consistent way, e.g.
     `#force-interactive-{op}`.
   - For **detail**, which has no config step today, mount the toggle
     inline on the confirm screen (`_actions_show_confirm()`). Do NOT
     promote detail to a 4-step wizard — that is more churn than needed.

2. **Initial value**: read the per-agent-type default from
   `brainstorm_crew.BRAINSTORM_AGENT_TYPES` (after sibling task t461_5
   adds `launch_mode` to each entry). Pass it through to the widget as
   its starting state so users can see the default for the operation.
   If t461_5 is not yet merged, default to `headless`.

3. **Collect the value**: in `_actions_collect_config()` (each
   per-op branch), read the switch state and store it:
   ```python
   self._wizard_config["launch_mode"] = (
       "interactive" if switch.value else "headless"
   )
   ```

4. **Thread through `_run_design_op()`**: after it reads
   `self._wizard_config`, pass `launch_mode=self._wizard_config.get(
   "launch_mode", "headless")` to each `register_*` call (lines
   2254-2282).

5. **Extend `register_*` function signatures** in `brainstorm_crew.py`:
   ```python
   def register_explorer(session_dir, crew_id, mandate, base_node_id,
                         group_name, agent_suffix="",
                         launch_mode="headless") -> str:
   ```
   Do the same for `register_comparator`, `register_synthesizer`,
   `register_detailer`, `register_patcher`.

6. **Update `_run_addwork()`**: add `launch_mode` parameter (default
   `"headless"`). When the value is non-default (i.e., `"interactive"`),
   append `--launch-mode interactive` to the `./ait crew addwork`
   command line (lines 101-109). Do not pass the flag when mode is
   `headless` — keep the command shorter for the common case and avoid
   churn for existing test expectations.

7. **Tmux availability guard**: at the top of the wizard config step,
   check `agent_launch_utils.is_tmux_available()`. If `False`, grey
   out the toggle and show a hint: "Tmux is not installed — interactive
   mode will fall back to a standalone terminal (no monitor
   integration)." Still allow the user to enable it — the runner
   handles the fallback.

## Verification Steps

1. Launch `ait brainstorm <task>` in a test session.
2. Use the explore wizard; confirm the "Force interactive mode" toggle
   appears in the config step with correct default (headless or
   t461_5-supplied default).
3. Toggle it on, proceed, confirm the agent is registered with
   `launch_mode: interactive` in its `_status.yaml`.
4. Run the agent (via the runner). Confirm a tmux window
   `agent-explorer_NNN` appears in the configured session.
5. Repeat for compare, hybridize, detail, patch — each wizard path
   must honour the toggle.
6. With tmux uninstalled (or renamed out of PATH), confirm the toggle
   is still functional but shows the fallback hint.
7. Existing brainstorm tests (if any) still pass; shellcheck the
   unchanged crew wrapper scripts.

## Dependencies

- Depends on t461_1 for the `--launch-mode` flag on `ait crew addwork`.
- Cooperates with t461_5 for the per-type default value read in step 2.
  Graceful degradation: if t461_5 is not yet merged, use `"headless"`.
