---
priority: low
effort: medium
depends: [t386_8, t386_5]
issue_type: feature
status: Ready
labels: [agentcrew]
created_at: 2026-03-17 09:44
updated_at: 2026-03-17 09:44
---

## AgentCrew Runner Config TUI

### Context
The AgentCrew runner reads default configuration from `aitasks/metadata/crew_runner_config.yaml` (interval, max_concurrent). This task adds the ability to edit these defaults from the `ait settings` TUI or similar configuration interface. Depends on t386_5 (TUI dashboard) for the UI framework.

### Goal
Add a configuration editing screen/section in the ait TUI that allows users to view and modify `crew_runner_config.yaml` values without manually editing YAML.

### Key Fields
- `interval` — Seconds between runner iterations (default: 30)
- `max_concurrent` — Maximum agents running simultaneously (default: 3)

### Reference Files
- `aitasks/metadata/crew_runner_config.yaml` — The config file to edit
- `.aitask-scripts/agentcrew/agentcrew_runner.py` — Runner that reads this config
- `.aitask-scripts/board/aitask_board.py` — TUI framework reference

### Verification
- Edit values via TUI, verify they persist in the YAML file
- Run `ait crew runner --crew <id> --once --dry-run` and verify it picks up the new values
