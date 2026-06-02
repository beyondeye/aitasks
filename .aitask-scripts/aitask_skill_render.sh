#!/usr/bin/env bash
# aitask_skill_render.sh - Render a (skill, profile, agent) closure to disk.
#
# Usage:
#   aitask_skill_render.sh <skill> --profile <name> --agent <name> [--force]
#
# Renders the authoring template at .claude/skills/<skill>/SKILL.md.j2 and
# every reachable .md procedure (dep-walker, t777_22) through minijinja using
# the active profile YAML and agent name. Outputs are written atomically to
# the per-profile sibling trees under the requested agent root:
#
#   .claude/skills/<skill>-<profile>-/SKILL.md           (entry-point target)
#   .claude/skills/<other_skill>-<profile>-/<file>.md    (transitive procs)
#
# Skip-if-fresh is closure-aware: any stale leaf re-renders the whole chain.
# Staleness combines an mtime fast-path with an authoritative content-diff
# safety net, so a committed prerender that drifted under git-equalized mtimes
# (checkout/clone) is still repaired (t907). --force re-renders unconditionally.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=.aitask-scripts/lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"
# shellcheck source=.aitask-scripts/lib/agent_skills_paths.sh
source "$SCRIPT_DIR/lib/agent_skills_paths.sh"

usage() {
    cat <<'EOF' >&2
Usage: aitask_skill_render.sh <skill> --profile <name> --agent <name> [--force]

Arguments:
  <skill>            Skill name (e.g. aitask-pick). Resolves to
                     .claude/skills/<skill>/SKILL.md.j2.
  --profile <name>   Execution profile name (must match a file in
                     aitasks/metadata/profiles/).
  --agent <name>     Agent name: claude | codex | opencode.
  --force            Re-render every closure target unconditionally.
EOF
}

# --- Arg parse ---

skill=""
profile_name=""
agent=""
force=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --profile)
            [[ $# -lt 2 ]] && { echo "skill_render: --profile requires a value" >&2; usage; exit 2; }
            profile_name="$2"; shift 2 ;;
        --agent)
            [[ $# -lt 2 ]] && { echo "skill_render: --agent requires a value" >&2; usage; exit 2; }
            agent="$2"; shift 2 ;;
        --force)
            force=true; shift ;;
        --help|-h)
            usage; exit 0 ;;
        --*)
            echo "skill_render: unknown flag: $1" >&2; usage; exit 2 ;;
        *)
            if [[ -z "$skill" ]]; then
                skill="$1"
            else
                echo "skill_render: unexpected positional arg: $1" >&2; usage; exit 2
            fi
            shift ;;
    esac
done

[[ -z "$skill" ]] && { echo "skill_render: missing <skill>" >&2; usage; exit 2; }
[[ -z "$profile_name" ]] && { echo "skill_render: missing --profile" >&2; usage; exit 2; }
[[ -z "$agent" ]] && { echo "skill_render: missing --agent" >&2; usage; exit 2; }

# --- Resolve profile YAML via aitask_scan_profiles.sh (handles local/* overrides) ---

_scan_output="$("$SCRIPT_DIR/aitask_scan_profiles.sh")"
profile_filename="$(echo "$_scan_output" \
    | awk -F'|' -v n="$profile_name" '$1=="PROFILE" && $3==n {print $2; exit}')"
if [[ -z "$profile_filename" ]]; then
    echo "skill_render: profile '$profile_name' not found" >&2
    exit 1
fi
profile_yaml="$REPO_ROOT/aitasks/metadata/profiles/$profile_filename"

# --- Resolve authoring template path via t777_1 helpers ---

template_rel="$(agent_authoring_template "$skill")"
template_path="$REPO_ROOT/$template_rel"
if [[ ! -f "$template_path" ]]; then
    echo "skill_render: template not found: $template_path" >&2
    exit 1
fi

# --- Delegate the full closure walk to Python (t777_22 dep-walker) ---
#
# The Python walker handles skip-if-fresh (closure-aware), atomic per-file
# writes, cycle detection, and reference rewriting across all 4 agent roots.

PYTHON="$(require_ait_python)"
extra=()
[[ "$force" == true ]] && extra+=(--force)

"$PYTHON" "$SCRIPT_DIR/lib/skill_template.py" walk-write \
    "$template_path" "$profile_yaml" "$agent" "$REPO_ROOT" "${extra[@]}"
