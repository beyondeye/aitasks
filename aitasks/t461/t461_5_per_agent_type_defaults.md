---
priority: medium
effort: low
depends: [t461_4]
issue_type: feature
status: Implementing
labels: [agentcrew, brainstorming]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-13 11:45
updated_at: 2026-04-14 10:12
---

## Context

Parent task t461 adds interactive launch mode for agentcrew code agents
(see t461_1 for the core runner + schema). Setting the mode per-agent
every time is tedious when a whole class of agents (e.g., brainstorm's
`detailer`) benefits from being interactive by default. This task adds
**per-agent-type defaults** for `launch_mode`, resolved with per-agent
overrides taking precedence.

## Key Files to Modify

- `.aitask-scripts/agentcrew/agentcrew_runner.py` — the effective-mode
  resolution in `launch_agent()` already reads
  `type_config.get("launch_mode")` if t461_1 landed as planned. Confirm
  and, if needed, finish that wiring.
- `.aitask-scripts/aitask_crew_init.sh` — where `_crew_meta.yaml` is
  first written. Allow an optional `launch_mode` key on each agent-type
  entry emitted under `agent_types:`. Missing key = `headless` (current
  behavior).
- `.aitask-scripts/brainstorm/brainstorm_crew.py` —
  `BRAINSTORM_AGENT_TYPES` (around lines 39-45). Each entry gets a new
  `launch_mode` key.
- `.aitask-scripts/brainstorm/brainstorm_crew.py` — `_run_addwork()`
  (lines 86-119). Only emit `--launch-mode <mode>` when the wizard
  override differs from the per-type default, to keep the command line
  minimal and avoid redundant overrides in `_status.yaml`.

## Reference Files for Patterns

- `_crew_meta.yaml` format (see any existing crew, e.g.
  `.aitask-crews/crew-brainstorm-427/_crew_meta.yaml`) for the
  `agent_types:` block structure.
- `load_tmux_defaults()` in
  `.aitask-scripts/lib/agent_launch_utils.py` — showcases the
  "framework default → config override" pattern the resolution should
  follow.

## Implementation Plan

1. **Schema extension**: `_crew_meta.yaml` already stores
   `agent_types.<name>.agent_string` and `.max_parallel`. Add an optional
   `launch_mode: headless|interactive` alongside. Missing key → default
   `headless`.

2. **Update `aitask_crew_init.sh`** to accept and write this field when
   it builds the initial meta block. Look for the section that emits
   `agent_types:` and make the emitter parameterizable. If the script
   currently writes a fixed block, add a hook so brainstorm can override
   entries.

3. **Update `BRAINSTORM_AGENT_TYPES`** in `brainstorm_crew.py`:
   ```python
   BRAINSTORM_AGENT_TYPES = {
       "explorer":   {"agent_string": "claudecode/opus4_6",  "max_parallel": 2, "launch_mode": "headless"},
       "comparator": {"agent_string": "claudecode/sonnet4_6","max_parallel": 1, "launch_mode": "headless"},
       "synthesizer":{"agent_string": "claudecode/opus4_6",  "max_parallel": 1, "launch_mode": "headless"},
       "detailer":   {"agent_string": "claudecode/opus4_6",  "max_parallel": 1, "launch_mode": "interactive"},
       "patcher":    {"agent_string": "claudecode/sonnet4_6","max_parallel": 1, "launch_mode": "headless"},
   }
   ```
   Rationale for `detailer` being interactive by default: it produces a
   long plan and users benefit from watching live. All others default
   headless because they often run in parallel and fill tmux with noise.

4. **Runner resolution** (confirm / complete):
   ```python
   launch_mode = (
       agent_data.get("launch_mode")            # per-agent override
       or type_config.get("launch_mode")        # per-type default
       or "headless"                             # framework default
   )
   ```
   `type_config` is already loaded in `launch_agent()` for the
   `agent_string` lookup; reuse it.

5. **`_run_addwork()` should not pass `--launch-mode` when the wizard
   value matches the per-type default**. This keeps the command line
   minimal and ensures the per-agent status yaml stays clean (no stored
   override when the type default already matches the user's choice).
   Helper:
   ```python
   type_default = BRAINSTORM_AGENT_TYPES.get(agent_type, {}).get("launch_mode", "headless")
   if launch_mode != type_default:
       cmd.extend(["--launch-mode", launch_mode])
   ```

6. **Wizard initial value** (cooperates with t461_3): the wizard toggle
   shows the effective default for the selected op when the panel is
   first rendered, so users see what they would launch with if they
   leave it alone.

## Verification Steps

1. Create a new brainstorm crew via `ait brainstorm <task>` (first-run
   of a brainstorm session). Confirm the resulting
   `_crew_meta.yaml` contains `launch_mode: interactive` under
   `agent_types.detailer` and `launch_mode: headless` under
   `agent_types.explorer`.
2. Run a `detail` op in brainstorm without touching the wizard toggle.
   Confirm the detailer agent launches in a tmux window
   `agent-detailer_NNN`, not headless.
3. Run an `explore` op without touching the toggle. Confirm explorers
   launch headless (logs only), no tmux window.
4. Toggle the wizard OFF for a `detail` op and launch. Confirm the
   agent launches headless (per-agent override wins over per-type
   default).
5. Toggle the wizard ON for an `explore` op and launch. Confirm the
   agent launches interactively.
6. Existing brainstorm tests still pass; `shellcheck
   .aitask-scripts/aitask_crew_init.sh` must pass.

## Dependencies

- Depends on t461_1 for the runner's resolution line and the
  `launch_mode` field schema.
- Cooperates with t461_3 for the wizard-toggle initial value.
