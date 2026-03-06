---
priority: medium
effort: medium
depends: [t319_4]
issue_type: feature
status: Done
labels: [opencode, codeagent]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-06 11:09
updated_at: 2026-03-06 12:04
completed_at: 2026-03-06 12:04
---

Add framework-wide support for the 'status' field in model JSON files (models_*.json).

## Context

The OpenCode model discovery script (t319_4) introduced a 'status' field ('active' or 'unavailable') to track models that are no longer available from connected providers. This field needs to be supported across the framework.

## Changes Required

### 1. aiscripts/aitask_codeagent.sh
- In get_cli_model_id(): check the 'status' field before returning cli_id
- If status is 'unavailable', fail with clear error: "Model <name> is unavailable (no longer provided by connected providers). Run 'ait opencode-models' to refresh."
- In cmd_list_models(): display status alongside each model (e.g., [UNAVAILABLE] tag)

### 2. aiscripts/board/aitask_board.py (TUI board)
- In model selection widgets: dim or strikethrough unavailable models
- Show status indicator in model list views

### 3. aiscripts/aitask_settings.sh (settings TUI)
- Handle status field in model configuration views
- Allow viewing unavailable models but prevent selecting them as defaults

### 4. ait codeagent list-models
- Show [ACTIVE]/[UNAVAILABLE] status next to each model
- Optionally filter by status (--active-only flag)

## Verification
- ait codeagent resolve with an unavailable model fails with clear error
- ait codeagent list-models shows status indicators
- TUI board dims unavailable models
- Settings TUI handles status field
