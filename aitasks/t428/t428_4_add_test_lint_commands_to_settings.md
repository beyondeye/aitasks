---
priority: high
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [testing, qa, settings]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-22 11:23
updated_at: 2026-03-22 13:15
---

## Context

Add `test_command` and `lint_command` as configurable project settings in `project_config.yaml`, similar to the existing `verify_build` key. These keys are consumed by the new `/aitask-qa` skill (t428_1) but are useful independently for any workflow needing project test/lint configuration. The distinction from `verify_build` is: `verify_build` is a post-merge build gate, while `test_command`/`lint_command` are for focused QA analysis.

## Key Files to Modify

- **`seed/project_config.yaml`** — Add documented `test_command` and `lint_command` keys with examples per project type
- **`aitasks/metadata/project_config.yaml`** — Add empty keys for this project
- **`.aitask-scripts/settings/settings_app.py`** (~line 302) — Add to `PROJECT_CONFIG_SCHEMA` dict, reuse `EditVerifyBuildScreen` modal
- **`.claude/skills/task-workflow/SKILL.md`** (~line 519) — Update Project Configuration table with new keys
- Optionally create: `.aitask-scripts/settings/test_command_presets.yaml`
- Optionally create: `.aitask-scripts/settings/lint_command_presets.yaml`

## Implementation Steps

### 1. Update seed/project_config.yaml

Add after the `verify_build` section, following the same documentation style:

```yaml
# test_command — Shell command(s) to run project tests.
#
# Used by aitask-qa skill to execute tests and verify test coverage.
# Accepts a single command string or a YAML list of commands.
# Leave blank to let aitask-qa auto-detect tests from project structure.
#
# Examples:
#   # Python: pytest
#   # JavaScript: npm test
#   # Go: go test ./...
#   # Rust: cargo test
#   # Shell (aitasks): bash tests/test_*.sh
#   # Multi-step:
#   #   - "npm run unit"
#   #   - "npm run integration"

test_command:

# lint_command — Shell command(s) to lint/check project code.
#
# Used by aitask-qa skill to run linting on changed files.
# Accepts a single command string or a YAML list of commands.
# Leave blank to skip linting or let aitask-qa auto-detect.
#
# Examples:
#   # Python: ruff check .
#   # JavaScript: eslint .
#   # Go: golangci-lint run
#   # Rust: cargo clippy
#   # Shell: shellcheck .aitask-scripts/aitask_*.sh

lint_command:
```

### 2. Update aitasks/metadata/project_config.yaml

Add empty keys:
```yaml
test_command:
lint_command:
```

### 3. Update settings_app.py

Add to `PROJECT_CONFIG_SCHEMA` dict (after `verify_build`):

```python
"test_command": {
    "summary": "Test command(s) for QA analysis",
    "detail": (
        "Shell command(s) used by /aitask-qa to run project tests. "
        "Accepts a single string or YAML list. Leave blank for auto-detection."
    ),
},
"lint_command": {
    "summary": "Lint command(s) for QA analysis",
    "detail": (
        "Shell command(s) used by /aitask-qa to lint changed files. "
        "Accepts a single string or YAML list. Leave blank to skip."
    ),
},
```

In the project config editing handler (~line 1907), extend the `verify_build` special handling to also apply to `test_command` and `lint_command`:
```python
if focused.row_key in ("verify_build", "test_command", "lint_command"):
    presets = _load_command_presets(focused.row_key)
    self.push_screen(
        EditVerifyBuildScreen(
            focused.row_key, focused.raw_value, presets=presets,
        ),
        callback=self._handle_project_config_edit,
    )
```

Add a generic `_load_command_presets(key)` function that loads from `{key}_presets.yaml`.

### 4. Create preset files (optional but recommended)

**`.aitask-scripts/settings/test_command_presets.yaml`**:
```yaml
- name: Python (pytest)
  value: "pytest"
- name: Python (unittest)
  value: "python -m unittest discover"
- name: JavaScript (npm)
  value: "npm test"
- name: JavaScript (vitest)
  value: "npx vitest run"
- name: Go
  value: "go test ./..."
- name: Rust
  value: "cargo test"
- name: Shell (aitasks pattern)
  value: "bash tests/test_*.sh"
```

**`.aitask-scripts/settings/lint_command_presets.yaml`**:
```yaml
- name: Python (ruff)
  value: "ruff check ."
- name: Python (flake8)
  value: "flake8 ."
- name: JavaScript (eslint)
  value: "eslint ."
- name: Go (golangci-lint)
  value: "golangci-lint run"
- name: Rust (clippy)
  value: "cargo clippy"
- name: Shell (shellcheck)
  value: "shellcheck .aitask-scripts/aitask_*.sh"
```

### 5. Update task-workflow/SKILL.md Project Configuration table

Add rows to the table at ~line 519:
```
| `test_command` | string or list | (none — auto-detect) | Shell command(s) for running project tests | aitask-qa Step 4 |
| `lint_command` | string or list | (none — skip) | Shell command(s) for linting project code | aitask-qa Step 4 |
```

## Reference Files

- `seed/project_config.yaml` — Template with `verify_build` documentation pattern to follow
- `.aitask-scripts/settings/settings_app.py` — TUI settings app with `PROJECT_CONFIG_SCHEMA` and `EditVerifyBuildScreen`
- `.aitask-scripts/settings/verify_build_presets.yaml` — Preset file pattern to follow
- `.claude/skills/task-workflow/SKILL.md` lines 516-522 — Project Configuration table

## Verification Steps

1. Run `ait settings` → navigate to Project tab → verify `test_command` and `lint_command` appear
2. Click edit on `test_command` → verify multi-line editor opens with presets
3. Select a preset → verify it populates correctly
4. Save and verify `aitasks/metadata/project_config.yaml` updates
5. Run `python3 -c "import yaml; print(yaml.safe_load(open('seed/project_config.yaml')))"` to verify YAML validity
