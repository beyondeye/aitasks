---
Task: t419_7_settings_for_brainstorming_agents.md
Parent Task: aitasks/t419_brainstorm_agent_framework.md (archived)
Sibling Tasks: aitasks/t419/t419_6_tui_scaffolding.md
Archived Sibling Plans: aiplans/archived/p419/p419_5_agentcrew_brainstorm_agent_types_and_templates.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: Brainstorm Agent Settings in ait settings TUI

## Context
The brainstorm engine (t419) defines 5 agent types (explorer, comparator, synthesizer, detailer, patcher) with hardcoded model defaults in `BRAINSTORM_AGENT_TYPES`. This task makes those defaults configurable via the Agent Defaults tab in `ait settings`, and renames the section header.

## Steps

### Step 1: Add brainstorm operation descriptions to `OPERATION_DESCRIPTIONS`

**File:** `.aitask-scripts/settings/settings_app.py` (lines 112-118)

Add 5 new entries after the existing operations:

```python
OPERATION_DESCRIPTIONS: dict[str, str] = {
    "pick": "Model used for picking and implementing tasks",
    "explain": "Model used for explaining/documenting code",
    "batch-review": "Model used for batch code review operations",
    "raw": "Model used for direct/ad-hoc code agent invocations (passthrough mode)",
    "brainstorm-explorer": "Model for exploring solution space in brainstorming sessions",
    "brainstorm-comparator": "Model for comparing and analyzing design proposals",
    "brainstorm-synthesizer": "Model for merging and synthesizing design proposals",
    "brainstorm-detailer": "Model for creating detailed implementation plans from designs",
    "brainstorm-patcher": "Model for applying targeted tweaks to brainstorm plans",
}
```

Use hyphens (`brainstorm-explorer`) to match the existing key style (`batch-review`).

### Step 2: Add brainstorm defaults to `codeagent_config.json`

**File:** `aitasks/metadata/codeagent_config.json`

```json
{
  "defaults": {
    "pick": "claudecode/opus4_6",
    "explain": "claudecode/sonnet4_6",
    "batch-review": "claudecode/sonnet4_6",
    "raw": "claudecode/sonnet4_6",
    "brainstorm-explorer": "claudecode/opus4_6",
    "brainstorm-comparator": "claudecode/sonnet4_6",
    "brainstorm-synthesizer": "claudecode/opus4_6",
    "brainstorm-detailer": "claudecode/opus4_6",
    "brainstorm-patcher": "claudecode/sonnet4_6"
  }
}
```

### Step 3: Rename section header in `_populate_agent_tab()`

**File:** `.aitask-scripts/settings/settings_app.py` (line 2072)

Change:
```python
container.mount(Label("Code Agent Default Models", classes="section-header"))
```
To:
```python
container.mount(Label("Default Code Agents for Skills", classes="section-header"))
```

### Step 4: Add visual section separator for brainstorm agents

In `_populate_agent_tab()`, after the loop iterates through all keys, the brainstorm keys will appear naturally. However, to visually separate them from the skill operations, add a sub-header before brainstorm keys.

Modify the loop in `_populate_agent_tab()` (around line 2087) to detect when we enter the brainstorm section and insert a separator label:

```python
brainstorm_header_shown = False
for key in all_keys:
    # Insert brainstorm section header before first brainstorm key
    if key.startswith("brainstorm-") and not brainstorm_header_shown:
        container.mount(Label(""))  # spacer
        container.mount(Label("Default Code Agents for Brainstorming", classes="section-header"))
        container.mount(Label(
            "[dim]Models used by brainstorm agent types during design exploration.[/dim]",
            classes="section-hint",
        ))
        brainstorm_header_shown = True
    # ... rest of loop unchanged
```

### Step 5: Update `brainstorm_crew.py` to read from codeagent config

**File:** `.aitask-scripts/brainstorm/brainstorm_crew.py`

Add a function that loads configured agent strings from `codeagent_config.json`, falling back to `BRAINSTORM_AGENT_TYPES` hardcoded defaults:

```python
def get_agent_types() -> dict[str, dict]:
    """Return brainstorm agent types with agent_string from codeagent config.

    Reads brainstorm-* keys from codeagent_config.json (layered: project <- local).
    Falls back to BRAINSTORM_AGENT_TYPES hardcoded defaults for missing keys.
    """
    import copy
    result = copy.deepcopy(BRAINSTORM_AGENT_TYPES)
    try:
        config = load_layered_config(
            str(Path(__file__).resolve().parents[1] / "aitasks" / "metadata" / "codeagent_config.json")
        )
        defaults = config.get("defaults", {})
        for agent_type, info in result.items():
            config_key = f"brainstorm-{agent_type}"
            if config_key in defaults:
                info["agent_string"] = defaults[config_key]
    except Exception:
        pass  # Fall back to hardcoded defaults
    return result
```

This requires importing `load_layered_config` from `config_utils`. The path resolution needs to go from `.aitask-scripts/brainstorm/` up to repo root, then into `aitasks/metadata/`.

### Step 6: Update `aitask_brainstorm_init.sh` to read from config

**File:** `.aitask-scripts/aitask_brainstorm_init.sh` (lines 89-96)

Currently hardcodes `--add-type explorer:claudecode/opus4_6` etc. Update to read from `codeagent_config.json` defaults, falling back to the hardcoded values.

Add a helper function that reads agent strings from config:
```bash
_get_brainstorm_agent_string() {
    local agent_type="$1"
    local default_val="$2"
    local config_key="brainstorm-${agent_type}"
    local val
    # Try project config, then local config
    val=$(python3 -c "
import json, sys
for p in ['aitasks/metadata/codeagent_config.local.json', 'aitasks/metadata/codeagent_config.json']:
    try:
        d = json.load(open(p))
        v = d.get('defaults', {}).get('$config_key')
        if v:
            print(v)
            sys.exit(0)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
print('$default_val')
" 2>/dev/null) || val="$default_val"
    echo "$val"
}
```

Then use it:
```bash
crew_output=$(bash "$SCRIPT_DIR/aitask_crew_init.sh" \
    --id "brainstorm-${TASK_NUM}" \
    --name "Brainstorm t${TASK_NUM}" \
    --add-type "explorer:$(_get_brainstorm_agent_string explorer claudecode/opus4_6)" \
    --add-type "comparator:$(_get_brainstorm_agent_string comparator claudecode/sonnet4_6)" \
    --add-type "synthesizer:$(_get_brainstorm_agent_string synthesizer claudecode/opus4_6)" \
    --add-type "detailer:$(_get_brainstorm_agent_string detailer claudecode/opus4_6)" \
    --add-type "patcher:$(_get_brainstorm_agent_string patcher claudecode/sonnet4_6)" \
    --batch 2>&1) || {
```

### Step 7: Update `crew_meta_template.yaml` comment

**File:** `.aitask-scripts/brainstorm/templates/crew_meta_template.yaml`

Update the comment to mention settings are configurable via `ait settings`:
```yaml
# Default brainstorm agent_types. Configurable via `ait settings` > Agent Defaults.
# Used by aitask_brainstorm_init.sh when creating the brainstorm crew.
```

### Step 8: Add tests for `get_agent_types()` config reading

**File:** `tests/test_brainstorm_crew.py`

Add a new test class `TestGetAgentTypes` that verifies the config reading logic:

```python
from brainstorm.brainstorm_crew import get_agent_types, BRAINSTORM_AGENT_TYPES

class TestGetAgentTypes(unittest.TestCase):
    """Test that get_agent_types reads from codeagent config correctly."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="brainstorm_config_test_")
        self.config_dir = Path(self.tmpdir) / "aitasks" / "metadata"
        self.config_dir.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_defaults_when_no_config(self):
        """Falls back to BRAINSTORM_AGENT_TYPES when config file is missing."""
        result = get_agent_types(config_root=Path(self.tmpdir))
        for agent_type, info in BRAINSTORM_AGENT_TYPES.items():
            self.assertEqual(result[agent_type]["agent_string"], info["agent_string"])
            self.assertEqual(result[agent_type]["max_parallel"], info["max_parallel"])

    def test_reads_project_config(self):
        """Reads brainstorm-* keys from project codeagent_config.json."""
        config = {"defaults": {"brainstorm-explorer": "geminicli/gemini_2_5_pro"}}
        (self.config_dir / "codeagent_config.json").write_text(json.dumps(config))
        result = get_agent_types(config_root=Path(self.tmpdir))
        self.assertEqual(result["explorer"]["agent_string"], "geminicli/gemini_2_5_pro")
        # Others unchanged
        self.assertEqual(result["comparator"]["agent_string"], "claudecode/sonnet4_6")

    def test_local_overrides_project(self):
        """Local config overrides project config for brainstorm agents."""
        proj = {"defaults": {"brainstorm-explorer": "claudecode/opus4_6"}}
        local = {"defaults": {"brainstorm-explorer": "codex/o3"}}
        (self.config_dir / "codeagent_config.json").write_text(json.dumps(proj))
        (self.config_dir / "codeagent_config.local.json").write_text(json.dumps(local))
        result = get_agent_types(config_root=Path(self.tmpdir))
        self.assertEqual(result["explorer"]["agent_string"], "codex/o3")

    def test_partial_config_only_overrides_present_keys(self):
        """Only brainstorm keys present in config are overridden."""
        config = {"defaults": {"brainstorm-patcher": "claudecode/opus4_6"}}
        (self.config_dir / "codeagent_config.json").write_text(json.dumps(config))
        result = get_agent_types(config_root=Path(self.tmpdir))
        self.assertEqual(result["patcher"]["agent_string"], "claudecode/opus4_6")
        self.assertEqual(result["explorer"]["agent_string"], "claudecode/opus4_6")  # default
        self.assertEqual(result["comparator"]["agent_string"], "claudecode/sonnet4_6")  # default

    def test_max_parallel_preserved(self):
        """Config only changes agent_string, not max_parallel."""
        config = {"defaults": {"brainstorm-explorer": "codex/o3"}}
        (self.config_dir / "codeagent_config.json").write_text(json.dumps(config))
        result = get_agent_types(config_root=Path(self.tmpdir))
        self.assertEqual(result["explorer"]["max_parallel"], 2)

    def test_non_brainstorm_keys_ignored(self):
        """Non-brainstorm keys in config don't affect agent types."""
        config = {"defaults": {"pick": "claudecode/opus4_6", "brainstorm-detailer": "codex/o3"}}
        (self.config_dir / "codeagent_config.json").write_text(json.dumps(config))
        result = get_agent_types(config_root=Path(self.tmpdir))
        self.assertEqual(result["detailer"]["agent_string"], "codex/o3")
        self.assertNotIn("pick", result)
```

This requires `get_agent_types()` to accept an optional `config_root` parameter (defaults to repo root) for testability — avoids needing to mock file paths:

```python
def get_agent_types(config_root: Path | None = None) -> dict[str, dict]:
    """Return brainstorm agent types with agent_string from codeagent config."""
    import copy
    result = copy.deepcopy(BRAINSTORM_AGENT_TYPES)
    if config_root is None:
        config_root = Path(__file__).resolve().parents[2]  # repo root
    config_path = config_root / "aitasks" / "metadata" / "codeagent_config.json"
    try:
        config = load_layered_config(str(config_path))
        defaults = config.get("defaults", {})
        for agent_type, info in result.items():
            config_key = f"brainstorm-{agent_type}"
            if config_key in defaults:
                info["agent_string"] = defaults[config_key]
    except Exception:
        pass
    return result
```

## Key Files
- `.aitask-scripts/settings/settings_app.py` — Agent Defaults tab: add brainstorm ops, rename header, add section separator
- `aitasks/metadata/codeagent_config.json` — Add brainstorm-* default entries
- `.aitask-scripts/brainstorm/brainstorm_crew.py` — Add `get_agent_types()` to read from config
- `.aitask-scripts/aitask_brainstorm_init.sh` — Read agent strings from config
- `.aitask-scripts/brainstorm/templates/crew_meta_template.yaml` — Update comment
- `tests/test_brainstorm_crew.py` — Tests for config-aware `get_agent_types()`

## Verification
- Run `python3 -m pytest tests/test_brainstorm_crew.py -v` (or `python3 -m unittest tests.test_brainstorm_crew -v`) — all tests pass including new `TestGetAgentTypes`
- Launch `ait settings` and navigate to Agent Defaults tab
- Verify section header reads "Default Code Agents for Skills"
- Verify brainstorm agents appear in a separate subsection "Default Code Agents for Brainstorming"
- Edit a brainstorm agent (e.g., brainstorm-explorer) and verify it saves to `codeagent_config.json`
- Verify user overrides work (edit user row, then clear with `d`)
- Run `shellcheck .aitask-scripts/aitask_brainstorm_init.sh`

## Final Implementation Notes
- **Actual work done:** Implemented all 8 steps as planned. Added 5 brainstorm-* operation descriptions to settings TUI, added defaults to codeagent_config.json, renamed section header from "Code Agent Default Models" to "Default Code Agents for Skills", added visual separator for brainstorm section, created `get_agent_types()` function in brainstorm_crew.py that reads from layered config, updated aitask_brainstorm_init.sh to read agent strings from config with fallback, updated crew_meta_template.yaml comment, and added 6 unit tests.
- **Deviations from plan:** (1) `get_agent_types()` uses `parents[2]` instead of `parents[1]` for repo root resolution — the file is at `.aitask-scripts/brainstorm/brainstorm_crew.py`, so parents[2] correctly reaches the repo root. (2) Added `sys.path.insert` for `lib/` directory in brainstorm_crew.py to import `config_utils`.
- **Issues encountered:** None — clean implementation. All 28 tests pass (22 existing + 6 new).
- **Key decisions:** (1) Used hyphens in config keys (`brainstorm-explorer`) to match existing convention (`batch-review`). (2) `get_agent_types()` accepts optional `config_root` param for testability. (3) Shell helper `_get_brainstorm_agent_string` uses `$PYTHON` variable already set by the script, ensuring venv Python is used consistently. (4) Local config takes priority over project config in the shell helper (checked first).
- **Notes for sibling tasks:** The `get_agent_types()` function in `brainstorm_crew.py` should be used by t419_6 (TUI) and any future brainstorm code instead of reading `BRAINSTORM_AGENT_TYPES` directly. Import: `from brainstorm.brainstorm_crew import get_agent_types`. The function respects the project/local layering from `codeagent_config.json`.

## Post-Implementation
- Step 9: archive task, push changes
