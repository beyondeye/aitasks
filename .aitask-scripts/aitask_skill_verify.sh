#!/usr/bin/env bash
# aitask_skill_verify.sh — Verify all .j2 authoring templates render cleanly
# across the 4 supported agents (default profile) and that each stub surface
# follows the canonical pattern documented in
# .claude/skills/task-workflow/stub-skill-pattern.md.
#
# Usage:
#   aitask_skill_verify.sh
#
# Exit codes:
#   0  - all checks pass (or no .j2 templates found yet)
#   1  - one or more failures (render error, empty output, missing/bad stub)
#
# Render check uses lib/skill_template.py directly (writes to stdout) instead
# of aitask_skill_render.sh — verification is purely functional, no disk
# side effects, and skips the cross-skill recursive include scan.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=.aitask-scripts/lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"
# shellcheck source=.aitask-scripts/lib/agent_skills_paths.sh
source "$SCRIPT_DIR/lib/agent_skills_paths.sh"

cd "$REPO_ROOT"

# --- Find all authoring templates ---

mapfile -t templates < <(
    find ".claude/skills" -mindepth 2 -maxdepth 3 -name 'SKILL.md.j2' -type f 2>/dev/null | sort
)

if [[ ${#templates[@]} -eq 0 ]]; then
    echo "ait skill verify: no .j2 templates found — nothing to verify."
    exit 0
fi

# --- Resolve default profile + Python interpreter ---

DEFAULT_PROFILE_YAML="aitasks/metadata/profiles/default.yaml"
if [[ ! -f "$DEFAULT_PROFILE_YAML" ]]; then
    echo "ait skill verify: default profile not found at $DEFAULT_PROFILE_YAML" >&2
    exit 1
fi

PYTHON="$(require_ait_python)"
SKILL_TEMPLATE_PY="$SCRIPT_DIR/lib/skill_template.py"

# --- Per-skill stub-surface map (mirrors stub-skill-pattern.md §3g) ---

_stub_path_for() {
    local agent="$1" skill="$2"
    case "$agent" in
        claude)   echo ".claude/skills/$skill/SKILL.md" ;;
        codex)    echo ".agents/skills/$skill/SKILL.md" ;;
        gemini)   echo ".gemini/commands/$skill.toml" ;;
        opencode) echo ".opencode/commands/$skill.md" ;;
    esac
}

# --- Verification loop ---

failures=0
agents=(claude codex gemini opencode)

for tpl in "${templates[@]}"; do
    skill="$(basename "$(dirname "$tpl")")"

    # --- Render check: render against default.yaml for each agent ---
    for agent in "${agents[@]}"; do
        if ! out="$("$PYTHON" "$SKILL_TEMPLATE_PY" "$tpl" "$DEFAULT_PROFILE_YAML" "$agent" 2>&1)"; then
            printf 'VERIFY_FAIL: %s agent=%s render error:\n%s\n' "$skill" "$agent" "$out" >&2
            failures=$((failures + 1))
            continue
        fi
        if [[ -z "${out//[[:space:]]/}" ]]; then
            printf 'VERIFY_FAIL: %s agent=%s rendered output is empty\n' "$skill" "$agent" >&2
            failures=$((failures + 1))
        fi
    done

    # --- Stub-pattern check: 4 surfaces per skill ---
    # Canonical markers from stub-skill-pattern.md §3b-§3d:
    #   1) resolver call referencing this skill
    #   2) render call referencing this skill
    #   3) trailing-hyphen Read path with <profile>- placeholder
    for agent in "${agents[@]}"; do
        stub_path="$(_stub_path_for "$agent" "$skill")"
        if [[ ! -f "$stub_path" ]]; then
            printf 'STUB_FAIL: %s: missing stub for %s\n' "$stub_path" "$agent" >&2
            failures=$((failures + 1))
            continue
        fi
        if ! grep -q "aitask_skill_resolve_profile\.sh ${skill}" "$stub_path"; then
            printf 'STUB_FAIL: %s: missing resolver call ("aitask_skill_resolve_profile.sh %s")\n' \
                "$stub_path" "$skill" >&2
            failures=$((failures + 1))
        fi
        if ! grep -q "ait skill render ${skill}" "$stub_path"; then
            printf 'STUB_FAIL: %s: missing render call ("ait skill render %s")\n' \
                "$stub_path" "$skill" >&2
            failures=$((failures + 1))
        fi
        if ! grep -q "${skill}-<profile>-/SKILL\.md" "$stub_path"; then
            printf 'STUB_FAIL: %s: missing trailing-hyphen Read path ("%s-<profile>-/SKILL.md")\n' \
                "$stub_path" "$skill" >&2
            failures=$((failures + 1))
        fi
    done
done

if (( failures > 0 )); then
    echo "ait skill verify: $failures failure(s)" >&2
    exit 1
fi

echo "ait skill verify: OK (${#templates[@]} template(s) verified across ${#agents[@]} agents)"
