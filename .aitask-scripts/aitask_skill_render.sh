#!/usr/bin/env bash
# aitask_skill_render.sh - Render a (skill, profile, agent) into per-profile dir.
#
# Usage:
#   aitask_skill_render.sh <skill> --profile <name> --agent <name> [--force]
#
# Renders the authoring template at .claude/skills/<skill>/SKILL.md.j2 using
# the active profile YAML and agent name, atomically writing the result to
# the per-profile skill dir (.<agent_root>/<skill>[-<profile>]/SKILL.md).
#
# Behavior:
#   - Skip-if-fresh: if the target file exists and is newer than both the
#     template and the profile YAML, exit 0 silently. --force bypasses.
#   - Cross-skill includes: scans the template source for `{% include "...j2" %}`
#     directives that resolve OUTSIDE the parent skill dir; recursively renders
#     each as its own per-profile skill (within-skill includes are inlined
#     natively by minijinja).
#   - Atomic mv: render to a tempfile, then mv into place — live agent
#     sessions re-read SKILL.md, so partial writes are unacceptable.

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
  --agent <name>     Agent name: claude | codex | gemini | opencode.
  --force            Re-render even if target is fresh.
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

# --- Portable mtime helper (Linux: stat -c %Y, BSD/macOS: stat -f %m) ---

_get_mtime() {
    stat -c %Y "$1" 2>/dev/null || stat -f %m "$1"
}

# --- Resolve profile YAML via aitask_scan_profiles.sh (handles local/* overrides) ---

_scan_output="$("$SCRIPT_DIR/aitask_scan_profiles.sh")"
profile_filename="$(echo "$_scan_output" \
    | awk -F'|' -v n="$profile_name" '$1=="PROFILE" && $3==n {print $2; exit}')"
if [[ -z "$profile_filename" ]]; then
    echo "skill_render: profile '$profile_name' not found" >&2
    exit 1
fi
profile_yaml="$REPO_ROOT/aitasks/metadata/profiles/$profile_filename"

# --- Resolve authoring template and target path via t777_1 helpers ---

template_rel="$(agent_authoring_template "$skill")"
template_path="$REPO_ROOT/$template_rel"
if [[ ! -f "$template_path" ]]; then
    echo "skill_render: template not found: $template_path" >&2
    exit 1
fi

target_rel="$(agent_skill_dir "$agent" "$skill" "$profile_name")"
target_dir="$REPO_ROOT/$target_rel"
target_file="$target_dir/SKILL.md"

# --- Skip-if-fresh ---

if [[ "$force" == false && -f "$target_file" ]]; then
    target_mtime=$(_get_mtime "$target_file")
    tpl_mtime=$(_get_mtime "$template_path")
    yaml_mtime=$(_get_mtime "$profile_yaml")
    if (( target_mtime >= tpl_mtime && target_mtime >= yaml_mtime )); then
        exit 0
    fi
fi

# --- Render atomically ---

PYTHON="$(require_ait_python)"
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT
tmpfile="$tmpdir/SKILL.md.tmp"

"$PYTHON" "$SCRIPT_DIR/lib/skill_template.py" \
    "$template_path" "$profile_yaml" "$agent" > "$tmpfile"

mkdir -p "$target_dir"
mv "$tmpfile" "$target_file"

# --- Cross-skill recursive include scan ---
#
# Within-skill .j2 includes are inlined natively by minijinja (loader scoped
# to template's parent dir). Cross-skill .j2 includes (those resolving to a
# DIFFERENT skill directory under the same agent root) must be rendered as
# their own per-profile skills.

parent_dir="$(dirname "$template_path")"
template_skill_root="$(dirname "$parent_dir")"

include_regex='\{%-?[[:space:]]*include[[:space:]]+["'\'']([^"'\'']+\.j2)["'\'']'

# Extract the include filename via grep+sed (no PCRE per CLAUDE.md grep portability).
mapfile -t include_rels < <(
    grep -oE "$include_regex" "$template_path" 2>/dev/null \
        | sed -E "s|.*[\"']([^\"']+\\.j2)[\"'].*|\\1|" \
        | sort -u
)

for inc_rel in "${include_rels[@]}"; do
    [[ -z "$inc_rel" ]] && continue
    # Resolution mirrors skill_template.py's loader order:
    #   1) template's parent dir  → within-skill include (skip recursion).
    #   2) template's grandparent (agent skill root) → cross-skill include
    #      written as "<other_skill>/SKILL.md.j2".
    # Plain realpath (no -m: GNU-only). Existence required.
    inc_abs=""
    if [[ -e "$parent_dir/$inc_rel" ]]; then
        inc_abs="$(realpath "$parent_dir/$inc_rel" 2>/dev/null || true)"
    elif [[ -e "$template_skill_root/$inc_rel" ]]; then
        inc_abs="$(realpath "$template_skill_root/$inc_rel" 2>/dev/null || true)"
    fi
    [[ -z "$inc_abs" || ! -f "$inc_abs" ]] && continue
    # Skip if include lives inside the same skill dir — minijinja inlines natively.
    case "$inc_abs" in
        "$parent_dir"/*) continue ;;
    esac
    # Derive other_skill: first path component under template_skill_root.
    rel_to_root="${inc_abs#"$template_skill_root"/}"
    other_skill="${rel_to_root%%/*}"
    if [[ -z "$other_skill" || "$other_skill" == "$rel_to_root" ]]; then
        # Path didn't share the agent skill root — skip (out-of-tree include).
        continue
    fi
    rec_args=("$other_skill" --profile "$profile_name" --agent "$agent")
    [[ "$force" == true ]] && rec_args+=(--force)
    "$0" "${rec_args[@]}"
done
