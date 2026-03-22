---
Task: t428_4_add_test_lint_commands_to_settings.md
Parent Task: aitasks/t428_new_skill_aitask_qa.md
Sibling Tasks: aitasks/t428/t428_1_*.md, aitasks/t428/t428_5_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Add test_command/lint_command to ait settings

## Overview

Add `test_command` and `lint_command` as configurable project settings, similar to `verify_build`. These are consumed by the aitask-qa skill for running project-specific tests and linting.

## Steps

### 1. Update `seed/project_config.yaml`

Add after the `verify_build:` section (after line 71), following the same documentation style with comment blocks and examples per project type.

### 2. Update `aitasks/metadata/project_config.yaml`

Add empty keys after `verify_build:`:
```yaml
test_command:
lint_command:
```

### 3. Update `.aitask-scripts/settings/settings_app.py`

**3a. Add to `PROJECT_CONFIG_SCHEMA` dict (~line 318, after `verify_build`):**

```python
"test_command": {
    "summary": "Test command(s) for QA analysis (used by /aitask-qa)",
    "detail": (
        "Shell command(s) used by /aitask-qa to run project tests. "
        "Accepts a single string or YAML list. Leave blank for auto-detection."
    ),
},
"lint_command": {
    "summary": "Lint command(s) for QA analysis (used by /aitask-qa)",
    "detail": (
        "Shell command(s) used by /aitask-qa to lint changed files. "
        "Accepts a single string or YAML list. Leave blank to skip."
    ),
},
```

**3b. Generalize preset loading (~line 350):**

Replace `_load_verify_build_presets()` with a generic function:
```python
def _load_command_presets(key: str) -> list[dict]:
    """Load presets for a command-type config key."""
    presets_file = Path(__file__).resolve().parent / f"{key}_presets.yaml"
    if not presets_file.is_file():
        return []
    try:
        with open(presets_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []
```

Update `_load_verify_build_presets` to call `_load_command_presets("verify_build")` for backward compatibility.

**3c. Extend edit handler (~line 1907):**

Change the `if focused.row_key == "verify_build":` check to:
```python
if focused.row_key in ("verify_build", "test_command", "lint_command"):
    presets = _load_command_presets(focused.row_key)
    ...
```

**3d. Extend display logic (~lines 2348-2370):**

Change `if key == "verify_build"` checks to `if key in ("verify_build", "test_command", "lint_command")`.

### 4. Create preset files

**`.aitask-scripts/settings/test_command_presets.yaml`** — Common test runners per language/framework.

**`.aitask-scripts/settings/lint_command_presets.yaml`** — Common linters per language/framework.

### 5. Update `task-workflow/SKILL.md` Project Configuration table

Add rows at ~line 520:
```
| `test_command` | string or list | (none — auto-detect) | Shell command(s) for running project tests | aitask-qa Step 4 |
| `lint_command` | string or list | (none — skip) | Shell command(s) for linting project code | aitask-qa Step 4 |
```

## Verification

1. Run `ait settings` → Project tab → verify new keys appear
2. Click edit → verify multi-line editor opens with presets
3. Select a preset → verify it populates
4. Save → verify project_config.yaml updates
5. `python3 -c "import yaml; print(yaml.safe_load(open('seed/project_config.yaml')))"` — verify YAML validity

## Post-Implementation

Step 9 of task-workflow for archival.
