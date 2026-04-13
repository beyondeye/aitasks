---
Task: t461_3_brainstorm_wizard_toggle.md
Parent Task: aitasks/t461_interactive_override_in_agencrew.md
Sibling Tasks: aitasks/t461/t461_1_*.md, aitasks/t461/t461_2_*.md, aitasks/t461/t461_4_*.md, aitasks/t461/t461_5_*.md, aitasks/t461/t461_6_*.md
Archived Sibling Plans: aiplans/archived/p461/p461_1_*.md, aiplans/archived/p461/p461_2_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# p461_3 — Brainstorm wizard "force interactive" toggle

## Goal

Expose interactive-launch mode in the brainstorm TUI wizard's config
step so users can create an agent in interactive mode directly from
the wizard flow. The toggle's initial value comes from the per-type
default (after t461_5).

## Files

### Modified

1. `.aitask-scripts/brainstorm/brainstorm_app.py`
   - `_config_explore_no_node()` (~1935)
   - `_config_compare()` (~1944)
   - `_config_hybridize()` (~1962)
   - `_config_patch_no_node()` (~1974)
   - `_actions_show_confirm()` — inline toggle for the `detail` op
   - `_actions_collect_config()` (~2015-2056)
   - `_run_design_op()` (~2240)
2. `.aitask-scripts/brainstorm/brainstorm_crew.py`
   - `register_explorer`, `register_comparator`, `register_synthesizer`,
     `register_detailer`, `register_patcher`
   - `_run_addwork()` (~86-119)

## Implementation steps

### 1. Add `Switch` widget to each per-op config mounter

Example for explore:
```python
from textual.widgets import Switch, Label

def _config_explore_no_node(self) -> None:
    # ... existing mandate TextArea + parallel CycleField ...
    type_default = _brainstorm_type_default("explorer")  # from t461_5
    yield Label("Force interactive mode:")
    yield Switch(value=(type_default == "interactive"),
                 id="force-interactive-explore")
```

Repeat for compare / hybridize / patch / detail (on confirm screen).
Use a consistent id prefix like `force-interactive-<op>` so
`_actions_collect_config` can find the widget reliably.

Above the switch, show a small `Static` help label:
```
Launch in a tmux window so `ait monitor` can see it.
```

### 2. Tmux availability guard

At the top of each config screen, import
`is_tmux_available` from `agent_launch_utils` and if it returns False,
still show the switch but append a note:
```
(tmux not found — will fall back to a standalone terminal)
```

### 3. Collect into `_wizard_config`

In each `_actions_collect_config_<op>()` branch:
```python
switch = self.query_one(f"#force-interactive-{op}", Switch)
self._wizard_config["launch_mode"] = (
    "interactive" if switch.value else "headless"
)
```

### 4. Thread through `_run_design_op()`

```python
launch_mode = self._wizard_config.get("launch_mode", "headless")

if self._wizard_op == "explore":
    agent_name = register_explorer(
        session_dir, crew_id,
        mandate=..., base_node_id=..., group_name=...,
        launch_mode=launch_mode,
    )
# ... similar for other ops ...
```

### 5. Extend `register_*` signatures

```python
def register_explorer(session_dir, crew_id, mandate, base_node_id,
                      group_name, agent_suffix="",
                      launch_mode: str = "headless") -> str:
    # ... existing body ...
    return _run_addwork(
        crew_id=crew_id,
        agent_name=agent_name,
        agent_type="explorer",
        group_name=group_name,
        work2do_path=work2do_path,
        launch_mode=launch_mode,
    )
```

Do the same for `register_comparator`, `register_synthesizer`,
`register_detailer`, `register_patcher`.

### 6. `_run_addwork()` — conditional `--launch-mode`

```python
def _run_addwork(crew_id, agent_name, agent_type, group_name,
                 work2do_path, launch_mode: str = "headless") -> str:
    cmd = [
        "./ait", "crew", "addwork",
        "--crew", crew_id,
        "--name", agent_name,
        "--work2do", str(work2do_path),
        "--type", agent_type,
        "--group", group_name,
        "--batch",
    ]
    type_default = BRAINSTORM_AGENT_TYPES.get(agent_type, {}).get("launch_mode", "headless")
    if launch_mode != type_default:
        cmd.extend(["--launch-mode", launch_mode])
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(_repo_root))
    if result.returncode != 0:
        raise RuntimeError(f"addwork failed: {result.stderr}")
    return agent_name
```

### 7. Helper `_brainstorm_type_default()`

Add a tiny helper used by the wizard to query per-type defaults:
```python
def _brainstorm_type_default(agent_type: str) -> str:
    from .brainstorm_crew import BRAINSTORM_AGENT_TYPES
    return BRAINSTORM_AGENT_TYPES.get(agent_type, {}).get("launch_mode", "headless")
```

## Verification

1. Launch `ait brainstorm <task>`. For each of explore, compare,
   hybridize, detail, patch:
   - Confirm the "Force interactive mode" toggle appears in the
     config step (or on the confirm screen for detail).
   - Confirm the default matches the per-type default (after t461_5
     lands): detail defaults to interactive, others headless.
   - Flip the toggle, proceed, and verify the registered agent's
     `_status.yaml` contains the chosen `launch_mode` value.
2. After running the crew runner, confirm interactive-marked agents
   launch in a tmux window (if tmux is available), headless-marked
   ones launch via Popen.
3. With tmux unavailable, confirm the toggle still works and the
   fallback hint is visible.
4. Existing brainstorm tests (if any) still pass.

## Dependencies

- t461_1: consumes `--launch-mode` flag on `ait crew addwork`.
- t461_5: reads `BRAINSTORM_AGENT_TYPES[type]["launch_mode"]` for
  default; gracefully degrades to `"headless"` if the key is missing.

## Notes for sibling tasks

- The helper `_run_addwork()` now filters out redundant
  `--launch-mode` arguments (when the wizard value matches the type
  default). **t461_4** should NOT use that optimization — it always
  passes the explicit mode via `ait crew setmode`, to make the user's
  intent explicit in the commit history.
