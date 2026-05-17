---
priority: high
effort: medium
depends: []
issue_type: chore
status: Implementing
labels: [aitask_pick]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-17 11:56
updated_at: 2026-05-17 12:20
---

## Context

This is the foundation child of t777 (templated execution-profile redesign). Establishes the templating engine + the shared helpers every later child depends on:

1. `minijinja-py` Python dependency
2. `skill_template.py` renderer module
3. `agent_skills_paths.sh` per-agent path helper (single source of truth for per-agent skill discovery paths)
4. `aitask_skill_resolve_profile.sh` (resolves the active profile name for a given skill from the existing userconfig/project_config precedence)
5. Tests for all of the above

Why these grouped together: they're tight foundational deps with no value individually — they exist purely to be called by t777_2+.

## Key Files to Modify

- `.aitask-scripts/aitask_setup.sh` — add `'minijinja>=2.0,<3'` to BOTH pip install lines:
  - CPython venv ~line 655 (search for `'textual>=8.1.1,<9'`)
  - PyPy venv ~line 574 (same dep set, separate venv)
- `.aitask-scripts/lib/skill_template.py` (new) — renderer module
- `.aitask-scripts/lib/agent_skills_paths.sh` (new) — path helper
- `.aitask-scripts/aitask_skill_resolve_profile.sh` (new) — active-profile resolver CLI
- `tests/test_skill_template.sh` (new) — tests

## Reference Files for Patterns

- `.aitask-scripts/lib/python_resolve.sh` — pattern for sourceable lib + zero-arg entry-point functions
- `.aitask-scripts/aitask_scan_profiles.sh` — pattern for profile YAML loading + local/* overrides
- `.aitask-scripts/lib/config_utils.py` — `load_yaml_config()` for YAML loading
- `.claude/skills/task-workflow/execution-profile-selection.md` — canonical active-profile precedence (userconfig → project_config → default)
- `tests/test_claim_id.sh` — pattern for bash tests with `assert_eq`/`assert_contains` helpers

## Implementation Plan

### 1. Add minijinja to setup
Edit `.aitask-scripts/aitask_setup.sh`:
- Locate the CPython venv pip install (~line 655) and add `'minijinja>=2.0,<3'` to the dep list
- Locate the PyPy venv pip install (~line 574) and add the same dep
- Run `bash .aitask-scripts/aitask_setup.sh` against a scratch HOME to confirm

### 2. skill_template.py renderer

```python
# .aitask-scripts/lib/skill_template.py
"""skill_template - Render skill .j2 templates via minijinja.

NOTE: minijinja is NOT 100% Jinja2-compatible. Stick to:
  {{ var }}, {% if %}/{% else %}/{% endif %}, {% include %},
  {% raw %}/{% endraw %}.
No {% extends %} with arbitrary Python, smaller filter set, no `do` extension.
"""
from __future__ import annotations
import sys
from pathlib import Path
from typing import Any

def render_skill(template_path: Path, profile: dict[str, Any], agent_name: str) -> str:
    import minijinja
    env = minijinja.Environment(
        loader=minijinja.loaders.FileSystemLoader(str(template_path.parent)),
        keep_trailing_newline=True,
        undefined_behavior="strict",
    )
    template_source = template_path.read_text(encoding="utf-8")
    try:
        return env.render_str(template_source, profile=profile, agent=agent_name)
    except minijinja.UndefinedError as e:
        raise RuntimeError(
            f"Template '{template_path}' references missing key in profile: {e}. "
            f"Check the profile YAML for required keys."
        ) from e

if __name__ == "__main__":
    # CLI entry: python skill_template.py <template> <profile.yaml> <agent>
    import yaml
    template, profile_yaml, agent = sys.argv[1], sys.argv[2], sys.argv[3]
    with open(profile_yaml, encoding="utf-8") as f:
        profile = yaml.safe_load(f) or {}
    sys.stdout.write(render_skill(Path(template), profile, agent))
```

### 3. agent_skills_paths.sh

```bash
#!/usr/bin/env bash
# agent_skills_paths.sh - Single source of truth for per-agent skill discovery paths.
# Sourceable helper; do not execute directly.
[[ -n "${_AIT_AGENT_SKILLS_PATHS_LOADED:-}" ]] && return 0
_AIT_AGENT_SKILLS_PATHS_LOADED=1

# Path table (verify .gemini at impl time):
#   claude   .claude/skills
#   codex    .agents/skills
#   gemini   .gemini/skills  (or .agents/skills if Gemini consolidates)
#   opencode .opencode/skills

agent_skill_root() {
    case "$1" in
        claude)   echo ".claude/skills" ;;
        codex)    echo ".agents/skills" ;;
        gemini)   echo ".gemini/skills" ;;   # verify
        opencode) echo ".opencode/skills" ;;
        *)        echo "Unknown agent: $1" >&2; return 1 ;;
    esac
}

agent_skill_dir() {
    local agent="$1" skill="$2" profile="${3:-}"
    local root; root="$(agent_skill_root "$agent")" || return 1
    if [[ -n "$profile" && "$profile" != "default" ]]; then
        echo "$root/${skill}-${profile}"
    else
        echo "$root/${skill}"
    fi
}

agent_authoring_template() {
    local skill="$1"
    echo ".claude/skills/${skill}/SKILL.md.j2"
}
```

### 4. aitask_skill_resolve_profile.sh

```bash
#!/usr/bin/env bash
# Resolves the active profile name for a skill from precedence:
# 1. userconfig.yaml -> default_profiles.<skill>
# 2. project_config.yaml -> default_profiles.<skill>
# 3. "default"
set -euo pipefail
# ... implementation reading the two YAMLs and emitting one line to stdout
```

Reference the resolution chain in `task-workflow/execution-profile-selection.md` (the runtime SKILL.md branch).

### 5. tests/test_skill_template.sh

Cover:
- Renderer happy path (template with `{{ profile.x }}` and `{% if profile.y %}` produces expected output)
- Strict-undefined raises the wrapped error with the offending key + filename
- Agent branching: `{% if agent == "claude" %}A{% else %}B{% endif %}` renders A for agent=claude, B for agent=codex
- resolve-profile precedence: userconfig wins over project_config

## Verification Steps

1. `bash .aitask-scripts/aitask_setup.sh` succeeds (against scratch HOME if testing).
2. `~/.aitask/venv/bin/python -c "import minijinja; print(minijinja.__version__)"` works.
3. `~/.aitask/venv/bin/python .aitask-scripts/lib/skill_template.py <tmpfile.j2> <tmpprofile.yaml> claude` renders expected output.
4. `source .aitask-scripts/lib/agent_skills_paths.sh; agent_skill_dir claude aitask-pick fast` echoes `.claude/skills/aitask-pick-fast`.
5. `./.aitask-scripts/aitask_skill_resolve_profile.sh pick` echoes the resolved profile name.
6. `bash tests/test_skill_template.sh` — all PASS.
7. `shellcheck .aitask-scripts/lib/agent_skills_paths.sh .aitask-scripts/aitask_skill_resolve_profile.sh` clean.
