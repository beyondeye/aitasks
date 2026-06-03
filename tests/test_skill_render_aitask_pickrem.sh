#!/usr/bin/env bash
# test_skill_render_aitask_pickrem.sh - Regression tests for t777_14:
#   - .claude/skills/aitask-pickrem/SKILL.md.j2 (entry-point template, headless-only)
#   - 3 per-agent stubs (claude/codex/opencode) — conditional-Read pattern
#   - 1 golden file under tests/golden/skills/aitask-pickrem/ (remote × claude canonical)
#   - 4 pre-rendered committed remote variants under <root>/aitask-pickrem-remote-/
# Coverage:
#   1.  Golden diff for the entry-point template (remote × claude render).
#   1b. Agent-dimension invariance: claude/codex/opencode renders are
#       byte-identical (no {% if agent %} in the template).
#   2.  Remote-profile-specific branches fire (force_unlock_stale enabled,
#       done_task_action default fires, etc.).
#   3.  No Jinja markers leak into the rendered output (remote × 4 agents).
#   3b. Rendered body has no runtime profile-resolution tokens (t777_26 forbidden tokens).
#   4.  Per-agent reference rewrites: task-workflow-remote- closure is rewritten
#       to each agent's root.
#   5.  Stub markers present on all 3 stub files (canonical body + conditional-Read).
#   6.  Committed remote-variant freshness: rendering matches what's in git.
#   7.  Zero `Use AskUserQuestion` invocations in the remote-profile rendered output
#       across all 4 agents (the headless design goal).
#   8.  Committed remote-variant file existence (regression guard).
# Run: bash tests/test_skill_render_aitask_pickrem.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"

cd "$PROJECT_DIR"

# shellcheck source=.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
PYTHON="$(require_ait_python)"
if ! "$PYTHON" -c 'import minijinja' 2>/dev/null; then
    echo "SKIP: minijinja not installed in framework venv ($PYTHON). Run 'ait setup' first."
    exit 0
fi

RENDER="$PYTHON $PROJECT_DIR/.aitask-scripts/lib/skill_template.py"
TEMPLATE=".claude/skills/aitask-pickrem/SKILL.md.j2"
GOLDEN_DIR="tests/golden/skills/aitask-pickrem"
PROFILES_DIR="aitasks/metadata/profiles"

AGENTS=(claude codex opencode)

# pickrem is a headless-only skill — only the remote profile is meaningful.
PROFILE="remote"

# === Test 1: golden diff (remote × claude is canonical) ===

echo "=== Test 1: golden diff for entry-point × remote profile ==="
rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$PROFILE.yaml" claude 2>&1)"
golden_content="$(cat "$GOLDEN_DIR/SKILL-${PROFILE}-claude.md")"
assert_eq "golden SKILL × $PROFILE" "$golden_content" "$rendered"

# === Test 1b: agent dimension invariance ===

echo "=== Test 1b: agent renders are byte-identical (no {% if agent %} in template) ==="
base="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$PROFILE.yaml" claude 2>&1)"
for agent in codex opencode; do
    cmp="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$PROFILE.yaml" "$agent" 2>&1)"
    assert_eq "agent invariance $PROFILE/$agent" "$base" "$cmp"
done

# === Test 2: remote-profile branches fire ===

echo "=== Test 2: remote-profile branches fire correctly ==="
rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$PROFILE.yaml" claude 2>&1)"
# force_unlock_stale: true → force-unlock branch fires
assert_contains "remote/claude: force_unlock branch fires" \
    "force-unlocking stale lock" "$rendered"
# done_task_action: archive (default) → auto-archive branch fires
assert_contains "remote/claude: auto-archive Done task branch fires" \
    "auto-archiving Done task" "$rendered"
# issue_action: close_with_notes (default) → close branch fires
assert_contains "remote/claude: issue close-with-notes branch fires" \
    "aitask_issue_update.sh --close <task_num>" "$rendered"
# abort_revert_status: Ready (default) → "Ready" interpolated
assert_contains "remote/claude: abort_revert_status interpolated" \
    "--status Ready" "$rendered"

# === Test 3: no Jinja markers leak ===

echo "=== Test 3: rendered output has no Jinja markers ==="
for agent in "${AGENTS[@]}"; do
    rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$PROFILE.yaml" "$agent" 2>&1)"
    assert_not_contains "no Jinja {% leak $PROFILE × $agent" "{%" "$rendered"
    assert_not_contains "no Jinja {{ leak $PROFILE × $agent" "{{" "$rendered"
done

# === Test 3b: rendered body must NOT re-resolve profile at runtime (t777_26) ===

echo "=== Test 3b: rendered body has no runtime profile-resolution tokens ==="
FORBIDDEN_TOKENS=(
    "aitask_scan_profiles.sh"
    "Execute the Execution Profile Selection Procedure"
    "Select Execution Profile"
    "refresh execution profile"
)
for agent in "${AGENTS[@]}"; do
    rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$PROFILE.yaml" "$agent" 2>&1)"
    for token in "${FORBIDDEN_TOKENS[@]}"; do
        assert_not_contains "rendered $PROFILE × $agent has no '$token'" \
            "$token" "$rendered"
    done
done

# === Test 4: cross-agent reference rewrites (via walk-write on-disk output) ===

echo "=== Test 4: per-agent reference rewrites via walk-write ==="
for agent in "${AGENTS[@]}"; do
    ./.aitask-scripts/aitask_skill_render.sh aitask-pickrem --profile "$PROFILE" --agent "$agent" --force >/dev/null 2>&1
done

assert_contains "claude/remote: task-workflow ref rewritten under .claude/skills" \
    ".claude/skills/task-workflow-remote-/agent-attribution.md" "$(cat .claude/skills/aitask-pickrem-remote-/SKILL.md)"
assert_contains "codex/remote: task-workflow ref rewritten under .agents/skills" \
    ".agents/skills/task-workflow-remote-codex-/agent-attribution.md" "$(cat .agents/skills/aitask-pickrem-remote-codex-/SKILL.md)"
assert_contains "opencode/remote: task-workflow ref rewritten under .opencode/skills" \
    ".opencode/skills/task-workflow-remote-/agent-attribution.md" "$(cat .opencode/skills/aitask-pickrem-remote-/SKILL.md)"

# === Test 5: stub-marker checks ===

echo "=== Test 5: 3 stub files contain canonical conditional-Read markers ==="
CLAUDE_STUB=".claude/skills/aitask-pickrem/SKILL.md"
CODEX_STUB=".agents/skills/aitask-pickrem/SKILL.md"
OPENCODE_STUB=".opencode/commands/aitask-pickrem.md"

for stub in "$CLAUDE_STUB" "$CODEX_STUB" "$OPENCODE_STUB"; do
    body="$(cat "$stub")"
    assert_contains "$stub: resolve_profile uses short name 'pickrem' (t777_26)" \
        "aitask_skill_resolve_profile.sh pickrem" "$body"
    assert_not_contains "$stub: resolve_profile does NOT use full slug 'aitask-pickrem'" \
        "aitask_skill_resolve_profile.sh aitask-pickrem" "$body"
    assert_contains "$stub: skill render invocation present (fallback branch)" \
        "aitask_skill_render.sh aitask-pickrem" "$body"
    assert_contains "$stub: Read-and-follow marker present" \
        "Dispatch via Read-and-follow" "$body"
    # Conditional-Read marker — pickrem-specific divergence from canonical §3b
    assert_contains "$stub: conditional-Read marker present (Render only if needed)" \
        "Render only if needed" "$body"
done

# Per-agent agent_literal substitution checks
assert_contains "claude stub: --agent claude" "--agent claude" "$(cat "$CLAUDE_STUB")"
assert_contains "codex stub: --agent codex" "--agent codex" "$(cat "$CODEX_STUB")"
assert_contains "opencode stub: --agent opencode" "--agent opencode" "$(cat "$OPENCODE_STUB")"

# Per-agent rendered-variant Read target checks
assert_contains "claude stub: reads from .claude/skills/aitask-pickrem-<profile>-" \
    ".claude/skills/aitask-pickrem-<profile>-/SKILL.md" "$(cat "$CLAUDE_STUB")"
assert_contains "codex stub: reads from .agents/skills/aitask-pickrem-<profile>-" \
    ".agents/skills/aitask-pickrem-<profile>-codex-/SKILL.md" "$(cat "$CODEX_STUB")"
assert_contains "opencode stub: reads from .opencode/skills/aitask-pickrem-<profile>-" \
    ".opencode/skills/aitask-pickrem-<profile>-/SKILL.md" "$(cat "$OPENCODE_STUB")"

# === Test 6: committed remote-variant freshness ===
#
# Re-render to a tempdir-equivalent (via --force) and diff against the
# workspace state. The test runs AFTER Test 4's --force render, so the
# workspace IS the freshly-rendered state. We compare against `git show HEAD:`
# to catch the "edited .j2 but forgot to re-commit renders" case.

echo "=== Test 6: committed remote-variant matches fresh render ==="
# shellcheck source=.aitask-scripts/lib/agent_skills_paths.sh
source "$PROJECT_DIR/.aitask-scripts/lib/agent_skills_paths.sh"
for agent in "${AGENTS[@]}"; do
    # Shared-root agents (codex, +agy in t814) carry the -<agent>- segment (t834).
    committed_path="$(agent_skill_dir "$agent" aitask-pickrem remote)/SKILL.md"
    # File is not yet tracked or not yet in HEAD (first run pre-commit, e.g.,
    # right after a t834-style rename) — skip the freshness diff; Test 8
    # catches missing files separately.
    if ! git ls-files --error-unmatch "$committed_path" >/dev/null 2>&1; then
        continue
    fi
    if ! git cat-file -e "HEAD:$committed_path" 2>/dev/null; then
        continue
    fi
    fresh="$(cat "$committed_path")"
    head_content="$(git show "HEAD:$committed_path" 2>/dev/null || true)"
    assert_eq "freshness $agent: fresh render matches HEAD" "$head_content" "$fresh"
done

# === Test 7: zero `Use AskUserQuestion` invocations in remote rendering ===
#
# Descriptive prose mentioning AskUserQuestion (e.g. "no AskUserQuestion
# calls", "AskUserQuestion does not work") is allowed. What we forbid is the
# canonical invocation pattern that triggers a real prompt.

echo "=== Test 7: remote-profile rendering has zero AskUserQuestion invocations ==="
for agent in "${AGENTS[@]}"; do
    rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$PROFILE.yaml" "$agent" 2>&1)"
    assert_not_contains "no 'Use \`AskUserQuestion\`' in $PROFILE × $agent" \
        "Use \`AskUserQuestion\`" "$rendered"
done

# === Test 8: committed remote-variant file existence ===

echo "=== Test 8: committed remote-variant files exist on disk ==="
# shellcheck source=.aitask-scripts/lib/agent_skills_paths.sh
source "$PROJECT_DIR/.aitask-scripts/lib/agent_skills_paths.sh"
for agent in "${AGENTS[@]}"; do
    # Shared-root agents (codex, +agy in t814) carry the -<agent>- segment (t834).
    path="$(agent_skill_dir "$agent" aitask-pickrem remote)/SKILL.md"
    TOTAL=$((TOTAL + 1))
    if [[ -f "$path" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: committed remote variant missing: $path"
    fi
done

# === Summary ===

echo ""
echo "Tests: $TOTAL, Passed: $PASS, Failed: $FAIL"
[[ "$FAIL" -eq 0 ]] || exit 1
