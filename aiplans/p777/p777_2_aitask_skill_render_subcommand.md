---
Task: t777_2_aitask_skill_render_subcommand.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_*_*.md
Parent Plan: aiplans/p777_modular_pick_skill.md
Base branch: main
---

# Plan: t777_2 — `ait skill render` subcommand + 5-touchpoint whitelist

## Scope

Provides the `aitask_skill_render.sh` helper + `ait skill` dispatch + 5-touchpoint whitelist. Used by the stub (t777_3 → t777_6) and the wrapper (t777_5). See task description for the full file-by-file plan.

## Step Order

1. **Write `aitask_skill_render.sh`** — args `<skill> --profile <name> --agent <name> [--force]`; source `python_resolve.sh` and `agent_skills_paths.sh`; render via `lib/skill_template.py` to tempfile; atomic mv into per-profile dir; recursive include rendering; skip-if-fresh mtime optimization.
2. **Add `ait skill` case-statement** in `./ait` with `render` sub-dispatch (mirror `crew)`/`brainstorm)` pattern at lines 199/235).
3. **5-touchpoint whitelist** for `aitask_skill_render.sh` AND `aitask_skill_resolve_profile.sh` (from t777_1, which the parent plan attributed here for whitelisting):
   - `.claude/settings.local.json`
   - `.gemini/policies/aitasks-whitelist.toml`
   - `seed/claude_settings.local.json`
   - `seed/geminicli_policies/aitasks-whitelist.toml`
   - `seed/opencode_config.seed.json`
   - (Codex exempt per CLAUDE.md.)

## Critical Files

- `.aitask-scripts/aitask_skill_render.sh` (new)
- `./ait` (modify)
- 5 whitelist files

## Pitfalls

- **Recursive include scan** — minijinja parses templates via Python; if regex-scanning the source is too brittle, expose minijinja's parser via the renderer.
- **Atomic mv** — essential per [[feedback_skills_reread_during_execution]].
- **Skip-if-fresh** — compare against both template and profile YAML mtimes.

## Verification

See task description. `ait skill render` integration is exercised by t777_6+ tests.
