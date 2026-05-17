---
priority: high
effort: medium
depends: [t777_1]
issue_type: feature
status: Done
labels: [aitask_pick]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-17 11:57
updated_at: 2026-05-17 14:33
completed_at: 2026-05-17 14:33
---

## Context

Depends on t777_1. Provides the `ait skill render` subcommand and its underlying script. Renders a single `(skill, profile, agent)` combination on demand into the per-profile skill directory. Used by:

- The stub SKILL.md (when `/aitask-pick` is typed inside a live agent session)
- The `ait skillrun` wrapper (t777_5)
- The `AgentCommandScreen` per-run UI (t777_17)

Includes 5-touchpoint whitelist for the new helper.

## Key Files to Modify

- `.aitask-scripts/aitask_skill_render.sh` (new) — the helper script
- `./ait` (modify) — add `skill)` case-statement with `render` subcommand sub-dispatch
- 5-touchpoint whitelist:
  - `.claude/settings.local.json`
  - `.gemini/policies/aitasks-whitelist.toml`
  - `seed/claude_settings.local.json`
  - `seed/geminicli_policies/aitasks-whitelist.toml`
  - `seed/opencode_config.seed.json`

## Reference Files for Patterns

- `.aitask-scripts/aitask_scan_profiles.sh` — pattern for profile YAML loading + local/* overrides
- `.aitask-scripts/lib/python_resolve.sh` — `require_ait_python` for one-shot CLI scripts
- `./ait` lines 199 (crew) and 235 (brainstorm) — sub-dispatch pattern for `skill)` case
- `.aitask-scripts/aitask_plan_externalize.sh` — pattern for structured output and atomic file operations

## Implementation Plan

### 1. aitask_skill_render.sh
- Args: `<skill> --profile <name> --agent <name> [--force]`.
- Source `lib/python_resolve.sh`; call `require_ait_python` (one-shot CLI).
- Source `lib/agent_skills_paths.sh` (from t777_1).
- Resolve the profile YAML path via `aitask_scan_profiles.sh` output parsing (handles `local/*` overrides).
- Resolve the authoring template: `agent_authoring_template <skill>`.
- Render via `~/.aitask/venv/bin/python .aitask-scripts/lib/skill_template.py <template> <profile.yaml> <agent>` to a tempfile in `$(mktemp -d)`.
- Compute target: `agent_skill_dir <agent> <skill> <profile>` → mkdir -p target → atomic `mv` of tempfile to `<target>/SKILL.md`.
- **Recursive includes:** scan the rendered output (or template source) for `{% include "..." %}` directives that resolve to other `.j2` templates under task-workflow/ or shared procedures. For each include, invoke `aitask_skill_render.sh` recursively with the same (profile, agent). Skip plain `.md` includes (no .j2 → already canonical).
- **Skip-if-fresh:** if `<target>/SKILL.md` exists and its mtime is newer than both the template AND the profile YAML, exit 0 silently unless `--force`.

### 2. ait dispatcher
Add near alphabetical position in `./ait` (after `settings)`, before `setup)`):

```bash
skill)
    shift
    subcmd="${1:-}"
    shift || true
    case "$subcmd" in
        render) exec "$SCRIPTS_DIR/aitask_skill_render.sh" "$@" ;;
        # verify and resolve-profile subcommands added in later children
        --help|-h|"")
            echo "Usage: ait skill <subcommand> [options]"
            echo "  render   Render a skill template into a per-profile directory"
            exit 0
            ;;
        *) echo "ait skill: unknown subcommand '$subcmd'" >&2; exit 1 ;;
    esac
    ;;
```

### 3. 5-touchpoint whitelist
Per CLAUDE.md "Adding a New Helper Script":
- `.claude/settings.local.json` → add `"Bash(./.aitask-scripts/aitask_skill_render.sh:*)"` to `permissions.allow`
- `.gemini/policies/aitasks-whitelist.toml` → add `[[rule]]` block (`commandPrefix = "./.aitask-scripts/aitask_skill_render.sh"`, `decision = "allow"`, `priority = 100`)
- `seed/claude_settings.local.json` → mirror
- `seed/geminicli_policies/aitasks-whitelist.toml` → mirror
- `seed/opencode_config.seed.json` → add `"./.aitask-scripts/aitask_skill_render.sh *": "allow"`
- **Codex exempt** (no .codex/ entry needed per CLAUDE.md exemption).

## Verification Steps

1. `ait skill render pick --profile fast --agent claude` (after t777_6 creates the template) renders `.claude/skills/aitask-pick-fast/SKILL.md` atomically.
2. Re-running with no profile or template change is a no-op (skip-if-fresh).
3. `--force` rerenders even when fresh.
4. `shellcheck .aitask-scripts/aitask_skill_render.sh` clean.
5. The 5 whitelist files contain the expected entries.
