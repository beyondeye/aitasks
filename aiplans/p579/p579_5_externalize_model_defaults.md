---
Task: t579_5_externalize_model_defaults.md
Parent Task: aitasks/t579_support_for_opus_4_7.md
Sibling Tasks: aitasks/t579/t579_2_implement_aitask_add_model_skill.md, aitasks/t579/t579_3_add_opus_4_7_as_new_default_using_add_model_skill.md, aitasks/t579/t579_4_update_tests_and_docs_for_opus_4_7.md
Archived Sibling Plans: aiplans/archived/p579/p579_1_audit_refresh_code_models_and_design_add_model_skill.md
Base branch: main
plan_verified:
  - claudecode/opus4_6 @ 2026-04-17 00:49
---

# Plan: t579_5 — Externalize brainstorm agent defaults

## Context

Brainstorm agent model defaults (`agent_string`) are duplicated in three places
beyond the config file: the Python dict, the YAML template, and the bash init
script fallbacks. This refactor makes `codeagent_config.json` the sole source
of truth, simplifying future model promotion (t579_2's `aitask-add-model` skill
will only need to patch the config file for brainstorm ops).

## Scope — verified against current codebase

### 1. `brainstorm_crew.py` (lines 44-50, 52-88)

**Dict** — remove `agent_string` from all 5 entries in `BRAINSTORM_AGENT_TYPES`:
```python
BRAINSTORM_AGENT_TYPES = {
    "explorer": {"max_parallel": 2, "launch_mode": "headless"},
    "comparator": {"max_parallel": 1, "launch_mode": "headless"},
    "synthesizer": {"max_parallel": 1, "launch_mode": "headless"},
    "detailer": {"max_parallel": 1, "launch_mode": "interactive"},
    "patcher": {"max_parallel": 1, "launch_mode": "headless"},
}
```

**`get_agent_types()`** — rewrite to require config for `agent_string`:
- Load config via `load_layered_config` (unchanged)
- For each agent type, look up `brainstorm-<type>` in `config["defaults"]`
- If key is missing, raise `RuntimeError` with clear message
- `launch_mode` logic is unchanged (hardcoded default, overridable by config)
- Wrap config-load failure in RuntimeError too (no silent `pass` for missing config)
- Update docstring to reflect the new contract

### 2. `crew_meta_template.yaml` — DELETE

Confirmed not consumed at runtime. `TEMPLATE_DIR` references only the per-type
`.md` templates (explorer.md, comparator.md, etc.), not the YAML. Only
references are in `aidocs/model_reference_locations.md` (informational).

- Delete `.aitask-scripts/brainstorm/templates/crew_meta_template.yaml`
- Update `aidocs/model_reference_locations.md` to note deletion

### 3. `aitask_brainstorm_init.sh` (lines 88-107, 126-130)

**`_get_brainstorm_agent_string`** — make the second argument (fallback)
optional; if both config lookup and fallback are empty, die:
```bash
_get_brainstorm_agent_string() {
    local agent_type="$1"
    local default_val="${2:-}"
    ...
    # If Python prints empty and default_val is empty, error
}
```

**Lines 126-130** — drop the hardcoded fallback arguments:
```bash
--add-type "explorer:$(_get_brainstorm_agent_string explorer):..."
--add-type "comparator:$(_get_brainstorm_agent_string comparator):..."
--add-type "synthesizer:$(_get_brainstorm_agent_string synthesizer):..."
--add-type "detailer:$(_get_brainstorm_agent_string detailer):..."
--add-type "patcher:$(_get_brainstorm_agent_string patcher):..."
```

### 4. `tests/test_brainstorm_crew.py`

Update `TestGetAgentTypes` class:

- **`test_defaults_when_no_config`** (line 362): Currently asserts fallback
  `agent_string` from dict. After refactor, `get_agent_types()` without config
  should raise `RuntimeError`. Change to `assertRaises(RuntimeError)`.

- **`test_reads_project_config`** (line 369): Line 376 asserts `comparator`
  still has hardcoded default — change to also provide comparator in config
  fixture, or assert RuntimeError for missing keys. Best approach: provide a
  full config fixture with all 5 types.

- **`test_local_overrides_project`** (line 378): Same — needs full config
  fixture for non-tested types.

- **`test_partial_config_only_overrides_present_keys`** (line 387): This test's
  premise changes — partial config now raises RuntimeError for missing types.
  Replace with a test that verifies partial config raises.

- **`test_non_brainstorm_keys_ignored`** (line 403): Needs full config fixture.

- **`test_launch_mode_does_not_clobber_agent_string`** (line 453): Needs full
  config fixture for agent_string to come from.

- **Add new test**: `test_missing_config_raises_runtime_error` — no config file
  → `RuntimeError`.

- **Add new test**: `test_partial_config_raises_for_missing_type` — config with
  only some types → `RuntimeError`.

- **Helper**: Add a `_write_full_config(self, overrides=None)` method to write a
  complete config fixture with all 5 brainstorm types.

## Implementation Order

1. Edit `brainstorm_crew.py` — dict + `get_agent_types()`
2. Delete `crew_meta_template.yaml` + update `model_reference_locations.md`
3. Edit `aitask_brainstorm_init.sh` — helper function + call sites
4. Update `tests/test_brainstorm_crew.py` — all assertion sites + new tests
5. Run verification

## Verification

1. `python tests/test_brainstorm_crew.py` — all tests pass
2. `shellcheck .aitask-scripts/aitask_brainstorm_init.sh` — exits 0
3. `grep -rn 'claudecode/opus4_6\|claudecode/sonnet4_6' .aitask-scripts/brainstorm/ .aitask-scripts/aitask_brainstorm_init.sh` — no code matches (comments ok)
4. `grep -n 'DEFAULT_AGENT_STRING' .aitask-scripts/aitask_codeagent.sh` — still present (retained)
5. `./ait crew init --help` — same interface

## Step 9

Archive via `./.aitask-scripts/aitask_archive.sh 579_5`.
