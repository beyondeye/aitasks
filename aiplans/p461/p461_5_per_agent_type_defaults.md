---
Task: t461_5_per_agent_type_defaults.md
Parent Task: aitasks/t461_interactive_override_in_agencrew.md
Sibling Tasks: aitasks/t461/t461_1_*.md, aitasks/t461/t461_2_*.md, aitasks/t461/t461_3_*.md, aitasks/t461/t461_4_*.md, aitasks/t461/t461_6_*.md
Archived Sibling Plans: aiplans/archived/p461/p461_1_*.md, aiplans/archived/p461/p461_2_*.md, aiplans/archived/p461/p461_3_*.md, aiplans/archived/p461/p461_4_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# p461_5 — Per-agent-type launch_mode defaults

## Goal

Let each agent type (e.g., brainstorm's `explorer`, `detailer`) declare
its own `launch_mode` default in `_crew_meta.yaml`. The runner's
resolution (added in t461_1) already reads this path; this task fills
it with sensible defaults for brainstorm agents and teaches
`aitask_crew_init.sh` to emit the field.

## Files

### Modified

1. `.aitask-scripts/agentcrew/agentcrew_runner.py` — confirm the
   resolution line is present (added in t461_1):
   ```python
   launch_mode = (
       agent_data.get("launch_mode")
       or type_config.get("launch_mode")
       or "headless"
   )
   ```
2. `.aitask-scripts/aitask_crew_init.sh` — writes `_crew_meta.yaml`.
   Allow a `launch_mode` key on agent-type entries.
3. `.aitask-scripts/brainstorm/brainstorm_crew.py` —
   `BRAINSTORM_AGENT_TYPES` (lines 39-45) and its emitter into
   `_crew_meta.yaml` (if brainstorm customizes the init).
4. `.aitask-scripts/brainstorm/brainstorm_crew.py` — `_run_addwork()`
   already reads this via the filter from t461_3, so this task just
   populates the source.

## Implementation steps

### 1. Decide the defaults

```python
BRAINSTORM_AGENT_TYPES = {
    "explorer":    {"agent_string": "claudecode/opus4_6",   "max_parallel": 2, "launch_mode": "headless"},
    "comparator":  {"agent_string": "claudecode/sonnet4_6", "max_parallel": 1, "launch_mode": "headless"},
    "synthesizer": {"agent_string": "claudecode/opus4_6",   "max_parallel": 1, "launch_mode": "headless"},
    "detailer":    {"agent_string": "claudecode/opus4_6",   "max_parallel": 1, "launch_mode": "interactive"},
    "patcher":     {"agent_string": "claudecode/sonnet4_6", "max_parallel": 1, "launch_mode": "headless"},
}
```

Rationale: detailer produces long plans the user wants to watch live
(it's the "inner loop" of brainstorm). Others often run in parallel
and would clutter tmux with windows.

### 2. `aitask_crew_init.sh` emitter

Find the block that writes `agent_types:` in `_crew_meta.yaml`. It
probably looks like:
```bash
cat > "$META_FILE" <<EOF
...
agent_types:
  explorer:
    agent_string: claudecode/opus4_6
    max_parallel: 0
...
EOF
```

Refactor to support an optional `launch_mode` line per type. Options:
- Pass agent type definitions as a structured arg to the script (hard).
- Make the brainstorm crew init path write `_crew_meta.yaml` directly
  from Python using `BRAINSTORM_AGENT_TYPES` (cleaner).

Prefer option 2: `brainstorm_crew.py` already calls `_run_init()`; have
it pass the dict through and write the yaml in Python via
`yaml.safe_dump`. If that is too invasive, add a minimal
`--agent-types-file <yaml>` flag to `aitask_crew_init.sh` so callers
supply the whole block verbatim.

### 3. Runner resolution — verify

Check that t461_1's change is correctly resolving from `type_config`.
Write a small Python test or manual verification:
- Load a `_crew_meta.yaml` with `launch_mode: interactive` on
  `detailer`.
- Call `launch_agent()` (or the internal resolution helper) with a
  detailer agent whose status yaml has no `launch_mode` key.
- Assert the effective mode is `interactive`.

### 4. `_run_addwork()` redundancy filter (already added in t461_3)

Confirm the filter is active:
```python
type_default = BRAINSTORM_AGENT_TYPES.get(agent_type, {}).get("launch_mode", "headless")
if launch_mode != type_default:
    cmd.extend(["--launch-mode", launch_mode])
```
This keeps the per-agent status yaml clean of redundant overrides.

### 5. Brainstorm wizard initial value (already added in t461_3)

`_brainstorm_type_default()` helper reads from
`BRAINSTORM_AGENT_TYPES`. After this task, `detailer` will report
`interactive` as its default.

## Verification

1. Create a fresh brainstorm crew. `cat _crew_meta.yaml` — confirm
   `launch_mode: interactive` on `detailer` and `launch_mode: headless`
   on `explorer`.
2. Run a `detail` op without touching the wizard toggle. Confirm the
   detailer agent launches in a tmux window `agent-detailer_NNN`.
3. Run an `explore` op without touching the toggle. Confirm explorers
   launch headless (logs only, no tmux window).
4. Toggle the wizard OFF for a `detail` op. Confirm per-agent override
   wins — detailer launches headless. Verify `_status.yaml` has
   `launch_mode: headless` (because the filter recognizes the user
   override differs from the type default, so it is written).
5. Toggle the wizard ON for an `explore` op. Confirm explorer launches
   interactively. Verify `_status.yaml` has `launch_mode: interactive`.
6. `shellcheck .aitask-scripts/aitask_crew_init.sh` passes.

## Dependencies

- t461_1: runner resolution line.
- t461_3: wizard filter that consults `BRAINSTORM_AGENT_TYPES` for
  the redundancy check and initial value.

## Notes for sibling tasks

- **Adding a new brainstorm agent type later**: remember to add
  `launch_mode` to its `BRAINSTORM_AGENT_TYPES` entry. Missing keys
  fall back to `headless`.
- **t461_6 (log viewer)**: no interaction with this task.
