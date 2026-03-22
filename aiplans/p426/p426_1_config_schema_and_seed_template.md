---
Task: t426_1_config_schema_and_seed_template.md
Parent Task: aitasks/t426_default_execution_profiles.md
Sibling Tasks: aitasks/t426/t426_2_*.md, aitasks/t426/t426_3_*.md, aitasks/t426/t426_4_*.md, aitasks/t426/t426_5_*.md, aitasks/t426/t426_6_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t426_1 — Config Schema and Seed Template

## Context

This is the foundation child task. It defines the `default_profiles` configuration key that all other child tasks depend on. The key maps skill names to default profile names, enabling automatic profile selection without interactive prompts.

## Steps

### 1. Add `default_profiles` to `seed/project_config.yaml`

**File:** `seed/project_config.yaml`

Add a new commented block after the `verify_build` section, following the same documentation style (separator line, key name, description, examples):

```yaml
# ──────────────────────────────────────────────────────────────────────
# default_profiles — Default execution profile for each skill.
#
# Maps skill names to profile names (without .yaml extension). When a
# skill starts, it checks this setting before prompting for a profile.
# Users can override per-skill in userconfig.yaml (gitignored, personal).
# The --profile argument on any skill overrides both.
#
# Valid skill names: pick, fold, review, pr-import, revert, explore,
#                    pickrem, pickweb
#
# Resolution order:
#   1. --profile <name> argument (highest priority)
#   2. userconfig.yaml default_profiles.<skill> (personal)
#   3. project_config.yaml default_profiles.<skill> (team)
#   4. Interactive selection / auto-select (fallback)
#
# Examples:
#
#   # Team-wide: use 'fast' for pick, 'default' for review
#   default_profiles:
#     pick: fast
#     review: default
#
#   # Set all interactive skills to 'fast'
#   default_profiles:
#     pick: fast
#     fold: fast
#     review: fast
#     pr-import: fast
#     revert: fast
#     explore: fast
#
#   # Remote skills: use 'remote' profile
#   default_profiles:
#     pickrem: remote
#     pickweb: remote
# ──────────────────────────────────────────────────────────────────────

default_profiles:
```

### 2. Add `default_profiles` to `PROJECT_CONFIG_SCHEMA` in `settings_app.py`

**File:** `.aitask-scripts/settings/settings_app.py` (around line 302-319)

Add a new entry to the `PROJECT_CONFIG_SCHEMA` dict:

```python
"default_profiles": {
    "summary": "Default execution profile for each skill",
    "detail": (
        "Maps skill names to profile names (without .yaml). "
        "Valid skills: pick, fold, review, pr-import, revert, explore, pickrem, pickweb. "
        "Users can override in userconfig.yaml. The --profile argument overrides both."
    ),
},
```

### 3. Verify

- `python3 -c "import yaml; yaml.safe_load(open('seed/project_config.yaml'))"` — seed parses OK
- `./ait settings` — verify default_profiles appears in Project Config tab with summary/detail hint

## Files to Modify

- `seed/project_config.yaml` — add commented default_profiles block
- `.aitask-scripts/settings/settings_app.py` — add to PROJECT_CONFIG_SCHEMA

## Reference Files

- `seed/project_config.yaml` (existing style: lines 9-71 for codeagent_coauthor_domain and verify_build)
- `.aitask-scripts/settings/settings_app.py:302-319` (existing PROJECT_CONFIG_SCHEMA entries)
