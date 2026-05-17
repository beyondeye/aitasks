#!/usr/bin/env bash
# agent_skills_paths.sh - Single source of truth for per-agent skill discovery paths.
# Sourceable helper; do not execute directly.
#
# Provides:
#   agent_skill_root <agent>                 - echo the per-agent skill root dir
#   agent_skill_dir  <agent> <skill> [prof]  - echo the per-(skill,profile) dir
#   agent_authoring_template <skill>         - echo the authoring template path
#                                              (Claude is the source of truth)
#
# Path mapping (verified t777_1, 2026-05-17):
#   claude   .claude/skills
#   codex    .agents/skills
#   gemini   .gemini/skills   (per CLAUDE.md "Gemini CLI" section)
#   opencode .opencode/skills
#
# Rendered-dir naming convention (t777_3):
#   - With a non-empty <profile> arg (including "default"), agent_skill_dir
#     returns <root>/<skill>-<profile>- with a TRAILING HYPHEN. The trailing
#     hyphen is the recognizable "generated" marker that lets .gitignore use
#     a single `*-/` glob per agent root instead of per-profile entries.
#   - Without a profile arg, agent_skill_dir returns the no-suffix path
#     <root>/<skill>. That path is reserved exclusively for the committed
#     stub SKILL.md / command wrapper — it is NEVER overwritten by a render.
#   - REVERSES t777_1's "default profile uses no suffix" convention. Renders
#     for the default profile now go to <skill>-default-/, NOT <skill>/.
#     See .claude/skills/task-workflow/stub-skill-pattern.md for full design.

[[ -n "${_AIT_AGENT_SKILLS_PATHS_LOADED:-}" ]] && return 0
_AIT_AGENT_SKILLS_PATHS_LOADED=1

agent_skill_root() {
    case "$1" in
        claude)   echo ".claude/skills" ;;
        codex)    echo ".agents/skills" ;;
        gemini)   echo ".gemini/skills" ;;
        opencode) echo ".opencode/skills" ;;
        *)        echo "agent_skill_root: unknown agent: $1" >&2; return 1 ;;
    esac
}

agent_skill_dir() {
    local agent="$1" skill="$2" profile="${3:-}"
    local root
    root="$(agent_skill_root "$agent")" || return 1
    # Rendered dirs end with a trailing hyphen — recognizable "generated"
    # marker so gitignore is a single `*-/` glob per agent root. The
    # no-profile-arg case returns the no-suffix path, reserved for the
    # committed stub SKILL.md / command wrapper.
    if [[ -n "$profile" ]]; then
        echo "$root/${skill}-${profile}-"
    else
        echo "$root/${skill}"
    fi
}

agent_authoring_template() {
    local skill="$1"
    echo ".claude/skills/${skill}/SKILL.md.j2"
}
