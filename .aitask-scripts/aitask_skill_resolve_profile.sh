#!/usr/bin/env bash
# aitask_skill_resolve_profile.sh - Resolve the active profile name for a skill.
#
# Usage:
#   aitask_skill_resolve_profile.sh <skill_name>
#
# Resolution precedence (mirrors task-workflow/execution-profile-selection.md):
#   1. aitasks/metadata/userconfig.yaml -> default_profiles.<skill>
#   2. aitasks/metadata/project_config.yaml -> default_profiles.<skill>
#   3. "default"
#
# Output: single line to stdout — the resolved profile name (no trailing
# newline beyond echo's). No structured "KEY:value" wrapper because every
# call site wants just the raw value.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

USERCONFIG="${USERCONFIG:-$REPO_ROOT/aitasks/metadata/userconfig.yaml}"
PROJECT_CONFIG="${PROJECT_CONFIG:-$REPO_ROOT/aitasks/metadata/project_config.yaml}"

if [[ $# -ne 1 || -z "$1" ]]; then
    echo "Usage: aitask_skill_resolve_profile.sh <skill_name>" >&2
    exit 2
fi
skill="$1"

# Extract default_profiles.<skill> from a YAML file. Looks for a top-level
# `default_profiles:` block and an indented `  <skill>:` key. Emits the value
# (whitespace-trimmed, surrounding quotes stripped). Empty stdout if absent.
_extract_default_profile() {
    local file="$1" skill_key="$2"
    [[ -f "$file" ]] || return 0
    awk -v key="$skill_key" '
        BEGIN { in_block = 0 }
        # Top-level key terminates the block.
        /^[^[:space:]#]/ {
            in_block = ($1 == "default_profiles:")
            next
        }
        in_block {
            # Match "  <skill>: <value>" (any leading whitespace).
            if (match($0, "^[[:space:]]+" key ":[[:space:]]*(.*)$", m)) {
                val = m[1]
                # Strip trailing whitespace / inline comments.
                sub(/[[:space:]]*#.*$/, "", val)
                sub(/[[:space:]]+$/, "", val)
                # Strip surrounding single or double quotes.
                if (match(val, /^"(.*)"$/, q) || match(val, /^'\''(.*)'\''$/, q)) {
                    val = q[1]
                }
                if (val != "") {
                    print val
                    exit 0
                }
            }
        }
    ' "$file"
}

value="$(_extract_default_profile "$USERCONFIG" "$skill")"
if [[ -z "$value" ]]; then
    value="$(_extract_default_profile "$PROJECT_CONFIG" "$skill")"
fi
[[ -z "$value" ]] && value="default"

echo "$value"
