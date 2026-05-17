---
Task: t777_1_minijinja_dep_renderer_paths_resolver.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_*_*.md
Parent Plan: aiplans/p777_modular_pick_skill.md
Base branch: main
---

# Plan: t777_1 — `minijinja` dep + renderer + paths + resolver

## Scope

Foundation child. Establishes the templating engine plus shared helpers every later child depends on. See task description (`aitasks/t777/t777_1_*.md`) for the full file-by-file plan, references, and verification steps — that document is the canonical implementation guide.

## Step Order

1. **Add minijinja dep** — Edit `.aitask-scripts/aitask_setup.sh` to add `'minijinja>=2.0,<3'` to both pip-install lines (CPython venv ~655, PyPy venv ~574). Run setup against scratch HOME to confirm install.
2. **Write `lib/skill_template.py`** — Renderer with `render_skill(template_path, profile, agent_name)`, `keep_trailing_newline=True`, strict-undefined wrapped to clear "missing key" error, UTF-8 + LF. CLI `__main__` for stdin/stdout use by other scripts.
3. **Write `lib/agent_skills_paths.sh`** — sourceable helper exposing `agent_skill_root`, `agent_skill_dir`, `agent_authoring_template`. Verify whether `.gemini/skills/` exists separately or routes through `.agents/skills/` (per the current explore-agent finding that says both exist).
4. **Write `aitask_skill_resolve_profile.sh`** — one-line CLI mirroring `task-workflow/execution-profile-selection.md` precedence (userconfig → project_config → default).
5. **Write `tests/test_skill_template.sh`** — happy path render, strict-undefined error message check, agent branching, resolve-profile precedence.

## Critical Files (for navigation)

- `.aitask-scripts/aitask_setup.sh` (modify)
- `.aitask-scripts/lib/skill_template.py` (new)
- `.aitask-scripts/lib/agent_skills_paths.sh` (new)
- `.aitask-scripts/aitask_skill_resolve_profile.sh` (new)
- `tests/test_skill_template.sh` (new)

## Pitfalls

- **minijinja ≠ Jinja2 100%** — see parent plan §Pitfalls.
- **YAML loading** — use the existing `lib/config_utils.py` `load_yaml_config()` for consistency.
- **Profile precedence** — DO NOT re-invent. Mirror the chain in `task-workflow/execution-profile-selection.md` exactly.

## Verification

See task description Verification Steps. All bash helpers must pass `shellcheck`.
