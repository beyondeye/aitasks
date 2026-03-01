---
priority: high
effort: medium
depends: [t268_3]
issue_type: refactor
status: Implementing
labels: [modelwrapper, board]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-01 09:00
updated_at: 2026-03-01 14:53
---

## Context

This is child task 4 of t268 (Code Agent Wrapper). It splits the existing `board_config.json` into per-project (git-tracked) and per-user (gitignored) layers, using the common config library from t268_3.

Currently `board_config.json` is a single file in `aitasks/metadata/` that mixes project-level settings (columns, column_order) with user preferences (auto_refresh, sync_on_refresh). This task separates them so project structure is shared via git while personal preferences stay local.

## Key Files

- **Modify:** `aiscripts/board/aitask_board.py` (`load_metadata` and `save_metadata` methods, ~lines 198-218)
- **Modify:** `aiscripts/aitask_setup.sh` (gitignore for `board_config.local.json`)

## Implementation Plan

### 1. Define key categorization

**Per-project keys** (stay in `board_config.json`, git-tracked):
- `columns` — column definitions
- `column_order` — column display order
- Any structural/display settings shared across the team

**Per-user keys** (go to `board_config.local.json`, gitignored):
- `auto_refresh` — user preference
- `sync_on_refresh` — user preference
- Future: model/agent selection for operations

### 2. Refactor `TaskManager.load_metadata()`

Replace direct JSON loading with:
```python
from aiscripts.lib.config_utils import load_layered_config

config = load_layered_config(
    "aitasks/metadata/board_config.json",
    "aitasks/metadata/board_config.local.json"
)
```

### 3. Refactor `TaskManager.save_metadata()`

Use `config_utils.save_project_config()` and `save_local_config()` to split when saving:
- Structural keys → `board_config.json`
- User preference keys → `board_config.local.json`

### 4. Update gitignore

Add `board_config.local.json` to the data branch `.gitignore` (may already be covered by `*.local.json` from t268_2).

## Verification Steps

1. Board TUI loads config correctly with both files present
2. Board TUI loads config correctly with only project file (no local overrides)
3. Saving user preferences writes to `.local.json`, not project config
4. Saving structural changes (columns) writes to project config
5. `board_config.local.json` is gitignored
6. Existing `board_config.json` content is preserved during migration
