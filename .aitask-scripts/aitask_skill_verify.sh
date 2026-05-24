#!/usr/bin/env bash
# aitask_skill_verify.sh — Verify all .j2 authoring templates render cleanly
# across the 4 supported agents (default profile) and that each stub surface
# follows the canonical pattern documented in aidocs/stub-skill-pattern.md.
#
# Usage:
#   aitask_skill_verify.sh
#
# Exit codes:
#   0  - all checks pass (or no .j2 templates found yet)
#   1  - one or more failures (render error, empty output, missing/bad stub,
#        broken transitive reference, or render error in any closure leaf)
#
# Render check uses lib/skill_template.py directly (writes to stdout) instead
# of aitask_skill_render.sh — verification is purely functional, no disk
# side effects. The closure-walk check (t777_22) is performed via walk-check
# mode (in-memory, no disk writes).

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
    echo "aitask_skill_verify.sh: no .j2 templates found — nothing to verify."
    exit 0
fi

# --- Resolve default profile + Python interpreter ---

DEFAULT_PROFILE_YAML="aitasks/metadata/profiles/default.yaml"
if [[ ! -f "$DEFAULT_PROFILE_YAML" ]]; then
    echo "aitask_skill_verify.sh: default profile not found at $DEFAULT_PROFILE_YAML" >&2
    exit 1
fi

PYTHON="$(require_ait_python)"
SKILL_TEMPLATE_PY="$SCRIPT_DIR/lib/skill_template.py"

# --- Per-skill stub-surface map (mirrors aidocs/stub-skill-pattern.md §3g) ---

_stub_path_for() {
    local agent="$1" skill="$2"
    case "$agent" in
        claude)   echo ".claude/skills/$skill/SKILL.md" ;;
        codex)    echo ".agents/skills/$skill/SKILL.md" ;;
        gemini)   echo ".gemini/commands/$skill.toml" ;;
        opencode) echo ".opencode/commands/$skill.md" ;;
    esac
}

# Map a skill slug to its task-workflow short name (resolver key). See
# aidocs/stub-skill-pattern.md §3f. Stub authoring uses the short name in
# the resolver call so it matches the body's userconfig lookup.
_resolver_key_for() {
    local skill="$1"
    case "$skill" in
        aitask-pick) echo "pick" ;;
        aitask-explore)           echo "explore" ;;
        aitask-qa)                echo "qa" ;;
        aitask-fold)              echo "fold" ;;
        aitask-review)            echo "review" ;;
        aitask-pr-import)         echo "pr-import" ;;
        aitask-revert)            echo "revert" ;;
        aitask-pickrem)           echo "pickrem" ;;  # TODO(t777_29): generalize via prerender marker
        *)                        echo "$skill" ;;  # fallback: identity
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

    # --- Closure walk-check (t777_22): every transitive .md ref must resolve
    # and render cleanly. In-memory only — no disk writes.
    for agent in "${agents[@]}"; do
        if ! out="$("$PYTHON" "$SKILL_TEMPLATE_PY" walk-check "$tpl" "$DEFAULT_PROFILE_YAML" "$agent" "$REPO_ROOT" 2>&1)"; then
            printf 'VERIFY_FAIL: %s agent=%s closure walk error:\n%s\n' "$skill" "$agent" "$out" >&2
            failures=$((failures + 1))
        fi
    done

    # --- Stub-pattern check: 4 surfaces per skill ---
    # Canonical markers from aidocs/stub-skill-pattern.md §3b-§3d:
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
        resolver_key="$(_resolver_key_for "$skill")"
        if ! grep -q "aitask_skill_resolve_profile\.sh ${resolver_key}" "$stub_path"; then
            printf 'STUB_FAIL: %s: missing resolver call ("aitask_skill_resolve_profile.sh %s")\n' \
                "$stub_path" "$resolver_key" >&2
            failures=$((failures + 1))
        fi
        if ! grep -q "aitask_skill_render.sh ${skill}" "$stub_path"; then
            printf 'STUB_FAIL: %s: missing render call ("aitask_skill_render.sh %s")\n' \
                "$stub_path" "$skill" >&2
            failures=$((failures + 1))
        fi
        if ! grep -q "${skill}-<profile>-/SKILL\.md" "$stub_path"; then
            printf 'STUB_FAIL: %s: missing trailing-hyphen Read path ("%s-<profile>-/SKILL.md")\n' \
                "$stub_path" "$skill" >&2
            failures=$((failures + 1))
        fi
    done

    # --- Headless prerender check (pickrem only for now) ---
    # TODO(t777_29): generalize — read `prerender_for_headless` marker from j2
    # frontmatter and the `headless: true` flag from profile YAML; this hardcode
    # exists only until the marker mechanism lands.
    if [[ "$skill" == "aitask-pickrem" ]]; then
        for agent in "${agents[@]}"; do
            case "$agent" in
                claude)   root=".claude/skills" ;;
                codex)    root=".agents/skills" ;;
                gemini)   root=".gemini/skills" ;;
                opencode) root=".opencode/skills" ;;
            esac
            committed="$root/$skill-remote-/SKILL.md"
            if [[ ! -f "$committed" ]]; then
                printf 'PRERENDER_FAIL: %s: missing committed remote variant (run aitask_skill_render.sh aitask-pickrem --profile remote --agent %s and commit)\n' \
                    "$committed" "$agent" >&2
                failures=$((failures + 1))
            fi
        done
    fi
done

if (( failures > 0 )); then
    echo "aitask_skill_verify.sh: $failures failure(s)" >&2
    exit 1
fi

echo "aitask_skill_verify.sh: OK (${#templates[@]} template(s) verified across ${#agents[@]} agents)"
