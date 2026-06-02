#!/usr/bin/env bash
# aitask_skill_verify.sh — Verify all .j2 authoring templates render cleanly
# across the 4 supported agents (default profile) and that each stub surface
# follows the canonical pattern documented in aidocs/framework/stub-skill-pattern.md.
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
# shellcheck source=.aitask-scripts/lib/yaml_utils.sh
source "$SCRIPT_DIR/lib/yaml_utils.sh"  # read_yaml_field (headless / prerender markers)

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

# --- Per-skill stub-surface map (mirrors aidocs/framework/stub-skill-pattern.md §3g) ---

_stub_path_for() {
    local agent="$1" skill="$2"
    case "$agent" in
        claude)   echo ".claude/skills/$skill/SKILL.md" ;;
        codex)    echo ".agents/skills/$skill/SKILL.md" ;;
        opencode) echo ".opencode/commands/$skill.md" ;;
    esac
}

# Map a skill slug to its task-workflow short name (resolver key). See
# aidocs/framework/stub-skill-pattern.md §3f. Stub authoring uses the short name in
# the resolver call so it matches the body's userconfig lookup.
#
# Default convention: strip the `aitask-` prefix. Skills whose resolver key
# diverges from this convention can drop a single-line `resolver_key.txt`
# sidecar into their authoring dir to override.
_resolver_key_for() {
    local skill="$1"
    local sidecar=".claude/skills/${skill}/resolver_key.txt"
    if [[ -f "$sidecar" ]]; then
        head -n1 "$sidecar"
    else
        echo "${skill#aitask-}"
    fi
}

# --- Discover headless profiles (profiles flagged `headless: true`) ---
# A headless profile (currently just `remote`) is one whose skills must work
# where `ait setup` never ran (e.g. Claude Code Web), so their rendered
# closures are committed. Discovered declaratively so adding another headless
# profile needs no edit here. Top-level profiles only — `local/` profiles are
# per-user and ship no committed prerenders.
headless_profiles=()
for _pf in aitasks/metadata/profiles/*.yaml; do
    [[ -f "$_pf" ]] || continue
    if [[ "$(read_yaml_field "$_pf" headless)" == "true" ]]; then
        headless_profiles+=("$(basename "$_pf" .yaml)")
    fi
done

# --- Verification loop ---

failures=0
agents=(claude codex opencode)

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
    # Canonical markers from aidocs/framework/stub-skill-pattern.md §3b-§3d:
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
        # Shared-root agents (codex today, +agy in t814) carry an additional
        # `-<agent>-` segment in the rendered dir name; other agents keep
        # the simpler `-<profile>-` form. The stub literal must match.
        if [[ "$(agent_shared_skills_root "$agent")" == "true" ]]; then
            stub_read_literal="${skill}-<profile>-${agent}-/SKILL\\.md"
            stub_read_display="${skill}-<profile>-${agent}-/SKILL.md"
        else
            stub_read_literal="${skill}-<profile>-/SKILL\\.md"
            stub_read_display="${skill}-<profile>-/SKILL.md"
        fi
        if ! grep -q "$stub_read_literal" "$stub_path"; then
            printf 'STUB_FAIL: %s: missing trailing-hyphen Read path ("%s")\n' \
                "$stub_path" "$stub_read_display" >&2
            failures=$((failures + 1))
        fi
    done

    # --- Headless prerender freshness check (generalized, t894) ---
    # A skill that declares `prerender_for_headless: true` in its .md.j2
    # frontmatter ships committed prerenders for every headless profile so it
    # works where `ait setup` never ran (e.g. Claude Code Web). For each
    # (skill, headless-profile, agent) verify the committed entry-point exists
    # AND that the skill's whole rendered closure matches what is committed.
    # The closure comparison (walk-verify) is what catches source-vs-committed
    # drift — e.g. a `task-workflow/` edit without a `aitask_skill_rerender.sh
    # remote`, which left the committed task-workflow-remote- closure stale
    # with nothing failing (t888). task-workflow-remote- is committed only as
    # a transitive closure dependency of the headless pickrem/pickweb renders,
    # so verifying those two transitively covers every committed file in it.
    if [[ "$(read_yaml_field "$tpl" prerender_for_headless)" == "true" ]]; then
        for hprofile in "${headless_profiles[@]}"; do
            for agent in "${agents[@]}"; do
                committed="$(agent_skill_dir "$agent" "$skill" "$hprofile")/SKILL.md"
                if [[ ! -f "$committed" ]]; then
                    printf 'PRERENDER_FAIL: %s: missing committed %s prerender (run aitask_skill_render.sh %s --profile %s --agent %s and commit)\n' \
                        "$committed" "$hprofile" "$skill" "$hprofile" "$agent" >&2
                    failures=$((failures + 1))
                    continue
                fi
                if ! out="$("$PYTHON" "$SKILL_TEMPLATE_PY" walk-verify "$tpl" "aitasks/metadata/profiles/${hprofile}.yaml" "$agent" "$REPO_ROOT" 2>&1)"; then
                    printf 'PRERENDER_FAIL: %s agent=%s profile=%s committed prerender stale or unrenderable (run aitask_skill_rerender.sh %s and commit):\n%s\n' \
                        "$skill" "$agent" "$hprofile" "$hprofile" "$out" >&2
                    failures=$((failures + 1))
                fi
            done
        done
    fi
done

if (( failures > 0 )); then
    echo "aitask_skill_verify.sh: $failures failure(s)" >&2
    exit 1
fi

# --- Parity check (t777_27): runtime vs rendered, against frozen pre-rewrite
# fixtures. Skipped silently if the fixtures are not present (e.g., on a
# checkout that predates Phase 1 of t777_27).
PARITY_TEST="$REPO_ROOT/tests/test_skill_parity_runtime_vs_rendered.sh"
PARITY_FIXTURES="$REPO_ROOT/tests/fixtures/skills/aitask-pick/SKILL.md.pre-rewrite"
if [[ -f "$PARITY_TEST" && -f "$PARITY_FIXTURES" ]]; then
    if ! bash "$PARITY_TEST" >/dev/null 2>&1; then
        echo "VERIFY_FAIL: parity test failed — run: bash $PARITY_TEST" >&2
        exit 1
    fi
fi

echo "aitask_skill_verify.sh: OK (${#templates[@]} template(s) verified across ${#agents[@]} agents)"
