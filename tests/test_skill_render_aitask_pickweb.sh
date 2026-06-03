#!/usr/bin/env bash
# test_skill_render_aitask_pickweb.sh - Regression tests for t777_15:
#   - .claude/skills/aitask-pickweb/SKILL.md.j2 (entry-point template, headless-only)
#   - 5 stubs: 3 canonical (claude/codex/opencode) + 1 OpenCode skill-registry
#   - 1 golden file under tests/golden/skills/aitask-pickweb/ (remote × claude canonical)
#   - 4 pre-rendered committed remote variants under <root>/aitask-pickweb-remote-/
# Coverage:
#   1.  Golden diff for the entry-point template (remote × claude render).
#   1b. Agent-dimension invariance: claude/codex/opencode renders are
#       byte-identical (no {% if agent %} in the template).
#   2.  Pickweb-specific branches fire (plan_preference use_current default,
#       .aitask-data-updated/ web layout, no ownership/archive calls).
#   3.  No Jinja markers leak into the rendered output (remote × 4 agents).
#   3b. Rendered body has no runtime profile-resolution tokens (t777_26 forbidden tokens).
#   4.  Per-agent reference rewrites: task-workflow-remote- closure is rewritten
#       to each agent's root.
#   5.  Stub markers present on all 5 stub files (canonical body + conditional-Read).
#   6.  Committed remote-variant freshness: rendering matches what's in git.
#   7.  Zero `Use AskUserQuestion` invocations in the remote-profile rendered output
#       across all 4 agents (the headless design goal).
#   8.  Committed remote-variant file existence (regression guard).
#   9.  OpenCode skill-registry leftover fix: .opencode/skills/aitask-pickweb/SKILL.md
#       is the §3d-style stub, NOT the legacy "Source of Truth" pointer.
# Run: bash tests/test_skill_render_aitask_pickweb.sh

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
TEMPLATE=".claude/skills/aitask-pickweb/SKILL.md.j2"
GOLDEN_DIR="tests/golden/skills/aitask-pickweb"
PROFILES_DIR="aitasks/metadata/profiles"

AGENTS=(claude codex opencode)

# pickweb is a headless-only skill — only the remote profile is meaningful.
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

# === Test 2: pickweb-specific branches fire ===

echo "=== Test 2: pickweb-specific branches fire correctly ==="
rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$PROFILE.yaml" claude 2>&1)"
# plan_preference: use_current (default in remote.yaml) → use_current branch fires
assert_contains "remote/claude: plan_preference use_current branch fires" \
    "Profile: using existing plan" "$rendered"
# Web layout: .aitask-data-updated/ path present
assert_contains "remote/claude: .aitask-data-updated/ web layout present" \
    ".aitask-data-updated/" "$rendered"
# Completion marker JSON in Step 8
assert_contains "remote/claude: completion marker present" \
    "completed_t<task_id>.json" "$rendered"
# NO ownership claim (pickweb skips this)
assert_not_contains "remote/claude: no aitask_pick_own.sh ownership-claim invocation" \
    "./.aitask-scripts/aitask_pick_own.sh <task_num> --email" "$rendered"
# NO archive call (pickweb defers to aitask-web-merge)
assert_not_contains "remote/claude: no aitask_archive.sh invocation" \
    "./.aitask-scripts/aitask_archive.sh" "$rendered"
# Read-only lock check IS present
assert_contains "remote/claude: read-only lock check present" \
    "aitask_lock.sh --check" "$rendered"
# Uses regular git, not ./ait git
assert_contains "remote/claude: regular git add -A in Step 7" \
    "git add -A" "$rendered"
# NO ./ait git command invocations (descriptive prose mentions in parens
# / "no ... needed" sentences are allowed; what we forbid is an actual
# bash invocation line like `./ait git add` or `./ait git commit`).
assert_not_contains "remote/claude: no ./ait git add invocation" \
    "./ait git add" "$rendered"
assert_not_contains "remote/claude: no ./ait git commit invocation" \
    "./ait git commit" "$rendered"
assert_not_contains "remote/claude: no ./ait git push invocation" \
    "./ait git push" "$rendered"

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
    ./.aitask-scripts/aitask_skill_render.sh aitask-pickweb --profile "$PROFILE" --agent "$agent" --force >/dev/null 2>&1
done

assert_contains "claude/remote: task-workflow ref rewritten under .claude/skills" \
    ".claude/skills/task-workflow-remote-/agent-attribution.md" "$(cat .claude/skills/aitask-pickweb-remote-/SKILL.md)"
assert_contains "codex/remote: task-workflow ref rewritten under .agents/skills" \
    ".agents/skills/task-workflow-remote-codex-/agent-attribution.md" "$(cat .agents/skills/aitask-pickweb-remote-codex-/SKILL.md)"
assert_contains "opencode/remote: task-workflow ref rewritten under .opencode/skills" \
    ".opencode/skills/task-workflow-remote-/agent-attribution.md" "$(cat .opencode/skills/aitask-pickweb-remote-/SKILL.md)"

# === Test 5: stub-marker checks ===

echo "=== Test 5: 4 canonical stub files + 1 OpenCode skill-registry contain canonical conditional-Read markers ==="
CLAUDE_STUB=".claude/skills/aitask-pickweb/SKILL.md"
CODEX_STUB=".agents/skills/aitask-pickweb/SKILL.md"
OPENCODE_STUB=".opencode/commands/aitask-pickweb.md"
OPENCODE_SKILL_STUB=".opencode/skills/aitask-pickweb/SKILL.md"

for stub in "$CLAUDE_STUB" "$CODEX_STUB" "$OPENCODE_STUB" "$OPENCODE_SKILL_STUB"; do
    body="$(cat "$stub")"
    assert_contains "$stub: resolve_profile uses short name 'pickweb' (t777_26)" \
        "aitask_skill_resolve_profile.sh pickweb" "$body"
    assert_not_contains "$stub: resolve_profile does NOT use full slug 'aitask-pickweb'" \
        "aitask_skill_resolve_profile.sh aitask-pickweb" "$body"
    assert_contains "$stub: skill render invocation present (fallback branch)" \
        "aitask_skill_render.sh aitask-pickweb" "$body"
    assert_contains "$stub: Read-and-follow marker present" \
        "Dispatch via Read-and-follow" "$body"
    # Conditional-Read marker
    assert_contains "$stub: conditional-Read marker present (Render only if needed)" \
        "Render only if needed" "$body"
done

# Per-agent agent_literal substitution checks
assert_contains "claude stub: --agent claude" "--agent claude" "$(cat "$CLAUDE_STUB")"
assert_contains "codex stub: --agent codex" "--agent codex" "$(cat "$CODEX_STUB")"
assert_contains "opencode stub: --agent opencode" "--agent opencode" "$(cat "$OPENCODE_STUB")"
assert_contains "opencode skill-stub: --agent opencode" "--agent opencode" "$(cat "$OPENCODE_SKILL_STUB")"

# Per-agent rendered-variant Read target checks
assert_contains "claude stub: reads from .claude/skills/aitask-pickweb-<profile>-" \
    ".claude/skills/aitask-pickweb-<profile>-/SKILL.md" "$(cat "$CLAUDE_STUB")"
assert_contains "codex stub: reads from .agents/skills/aitask-pickweb-<profile>-" \
    ".agents/skills/aitask-pickweb-<profile>-codex-/SKILL.md" "$(cat "$CODEX_STUB")"
assert_contains "opencode stub: reads from .opencode/skills/aitask-pickweb-<profile>-" \
    ".opencode/skills/aitask-pickweb-<profile>-/SKILL.md" "$(cat "$OPENCODE_STUB")"
assert_contains "opencode skill-stub: reads from .opencode/skills/aitask-pickweb-<profile>-" \
    ".opencode/skills/aitask-pickweb-<profile>-/SKILL.md" "$(cat "$OPENCODE_SKILL_STUB")"

# === Test 6: committed remote-variant freshness ===

echo "=== Test 6: committed remote-variant matches fresh render ==="
# shellcheck source=.aitask-scripts/lib/agent_skills_paths.sh
source "$PROJECT_DIR/.aitask-scripts/lib/agent_skills_paths.sh"
for agent in "${AGENTS[@]}"; do
    # Shared-root agents (codex, +agy in t814) carry the -<agent>- segment (t834).
    committed_path="$(agent_skill_dir "$agent" aitask-pickweb remote)/SKILL.md"
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

echo "=== Test 7: remote-profile rendering has zero AskUserQuestion invocations ==="
for agent in "${AGENTS[@]}"; do
    rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$PROFILE.yaml" "$agent" 2>&1)"
    assert_not_contains "no 'Use \`AskUserQuestion\`' in $PROFILE × $agent" \
        "Use \`AskUserQuestion\`" "$rendered"
done

# === Test 8: committed remote-variant file existence ===

echo "=== Test 8: committed remote-variant files exist on disk ==="
for agent in "${AGENTS[@]}"; do
    # Shared-root agents (codex, +agy in t814) carry the -<agent>- segment (t834).
    path="$(agent_skill_dir "$agent" aitask-pickweb remote)/SKILL.md"
    TOTAL=$((TOTAL + 1))
    if [[ -f "$path" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: committed remote variant missing: $path"
    fi
done

# === Test 9: OpenCode skill-registry leftover fix ===
#
# .opencode/skills/aitask-pickweb/SKILL.md must NOT be the pre-templating-era
# "Source of Truth" pointer that points to .claude/skills/aitask-pickweb/SKILL.md.
# It should be a §3d-style stub that dispatches through the renderer.

echo "=== Test 9: OpenCode skill-registry leftover fixed (no legacy pointer) ==="
assert_not_contains "OpenCode skill-stub has no legacy 'Source of Truth' phrase" \
    "Source of Truth" "$(cat "$OPENCODE_SKILL_STUB")"
assert_not_contains "OpenCode skill-stub does not redirect to .claude/skills/aitask-pickweb/SKILL.md" \
    ".claude/skills/aitask-pickweb/SKILL.md" "$(cat "$OPENCODE_SKILL_STUB")"

# === Summary ===

echo ""
echo "Tests: $TOTAL, Passed: $PASS, Failed: $FAIL"
[[ "$FAIL" -eq 0 ]] || exit 1
