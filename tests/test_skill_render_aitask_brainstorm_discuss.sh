#!/usr/bin/env bash
# test_skill_render_aitask_brainstorm_discuss.sh - Regression tests for t1823_2:
#   - .claude/skills/aitask-brainstorm-discuss/SKILL.md.j2 (entry-point template)
#   - 4 Jinja-free procedures (discuss-audience / -compare / -explain / -flaws)
#   - 4 per-agent stubs (claude / codex / opencode command + opencode skill)
#   - 3 entry-point goldens under tests/golden/skills/aitask-brainstorm-discuss/
#   - 4 procedure goldens (-default) under tests/golden/procs/aitask-brainstorm-discuss/
# Coverage:
#   0.  Procedure inventory matches the skill dir.
#   0c. Closure set: the walked closure is EXACTLY the 5 authoring files — any
#       source under another skill dir (notably aitask-shadow/) fails.
#   1.  Per-profile golden diff for the entry-point template (claude render).
#   1b. Agent-dimension invariance for the entry point (no {% if agent %}).
#   1p. Procedure -default goldens + profile x agent byte-equality.
#   2s. Shortcodes, shortcode rules and the ambiguous-operand rule present in
#       every entry-point render.
#   3.  No Jinja markers leak into entry-point or procedure renders.
#   3b. Rendered output must NOT re-resolve profile (t777_26 forbidden tokens).
#   4.  Closure completeness per agent via aitask_skill_render.sh --force.
#   5.  Stub markers present on all 4 stub surfaces.
# Run: bash tests/test_skill_render_aitask_brainstorm_discuss.sh

# shellcheck disable=SC2016  # backticks in single quotes are literal markdown, not command substitution
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
# shellcheck source=tests/lib/asserts.sh disable=SC1091
. "$PROJECT_DIR/tests/lib/asserts.sh"

cd "$PROJECT_DIR" || exit 1

# shellcheck source=.aitask-scripts/lib/python_resolve.sh disable=SC1091
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
PYTHON="$(require_ait_python)"
if ! "$PYTHON" -c 'import minijinja' 2>/dev/null; then
    echo "SKIP: minijinja not installed in framework venv ($PYTHON). Run 'ait setup' first."
    exit 0
fi

SKILL="aitask-brainstorm-discuss"
RENDER="$PYTHON $PROJECT_DIR/.aitask-scripts/lib/skill_template.py"
SKILL_DIR=".claude/skills/$SKILL"
TEMPLATE="$SKILL_DIR/SKILL.md.j2"
SKILL_GOLDEN_DIR="tests/golden/skills/$SKILL"
PROC_GOLDEN_DIR="tests/golden/procs/$SKILL"
PROFILES_DIR="aitasks/metadata/profiles"

PROFILES=(default fast remote)
AGENTS=(claude codex opencode)

# Every procedure is Jinja-free (profile- and agent-invariant): one canonical
# -default golden each, plus the byte-equality sweep in Test 1p.
PROC_FILES_INVARIANT=(
    discuss-audience
    discuss-compare
    discuss-explain
    discuss-flaws
)

# === Test 0: the array IS the procedure inventory ===

echo "=== Test 0: procedure inventory matches the skill dir ==="
on_disk="$(find "$SKILL_DIR" -maxdepth 1 -name '*.md' ! -name 'SKILL.md' -exec basename {} .md \; | sort)"
listed="$(printf '%s\n' "${PROC_FILES_INVARIANT[@]}" | sort)"
assert_eq "every procedure on disk is listed, and every listed one exists" \
    "$on_disk" "$listed"

# === Test 0c: the walked closure is exactly the 5 authoring files ===
#
# walk-check only proves the closure renders (it prints nothing), so walk the
# closure in memory through the library and list its sources. The walker
# follows every resolvable filename anywhere in a file, so a stray mention of
# another skill's procedure path would silently drag it in — this pins the set.

echo "=== Test 0c: closure source set is exactly the 5 authoring files ==="
closure="$("$PYTHON" - "$PROJECT_DIR" "$TEMPLATE" <<'PY'
import sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / ".aitask-scripts" / "lib"))
from skill_template import walk_closure, _load_profile
profile_yaml = (root / "aitasks/metadata/profiles/default.yaml").resolve()
plan = walk_closure((root / sys.argv[2]).resolve(), _load_profile(profile_yaml),
                    "claude", "default", profile_yaml, root,
                    write=False, force=False)
for src, _target, _content in plan:
    print(src.relative_to(root))
PY
)"
expected="$(printf '%s\n' "$SKILL_DIR/SKILL.md.j2" \
    "$SKILL_DIR/discuss-audience.md" "$SKILL_DIR/discuss-compare.md" \
    "$SKILL_DIR/discuss-explain.md" "$SKILL_DIR/discuss-flaws.md" | sort)"
assert_eq "closure sources == the 5 authoring files" \
    "$expected" "$(printf '%s\n' "$closure" | sort)"
assert_not_contains "no aitask-shadow source in the closure" "aitask-shadow" "$closure"

# === Test 1: per-profile entry-point golden diffs (claude render is canonical) ===

echo "=== Test 1: golden diffs for entry-point × 3 profiles ==="
for profile in "${PROFILES[@]}"; do
    rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    golden_content="$(cat "$SKILL_GOLDEN_DIR/SKILL-${profile}-claude.md")"
    assert_eq "golden SKILL × $profile" "$golden_content" "$rendered"
done

# === Test 1b: entry-point agent dimension invariance ===

echo "=== Test 1b: agent renders are byte-identical (no {% if agent %} in template) ==="
for profile in "${PROFILES[@]}"; do
    base="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    for agent in codex opencode; do
        cmp="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" "$agent" 2>&1)"
        assert_eq "agent invariance $profile/$agent" "$base" "$cmp"
    done
done

# === Test 1p: procedure -default goldens + profile x agent invariance ===
#
# Adding a conditional to any procedure fails the invariance half and says
# "give this file per-profile goldens".

echo "=== Test 1p: procedure goldens + invariance across profile × agent ==="
for f in "${PROC_FILES_INVARIANT[@]}"; do
    base="$($RENDER "$SKILL_DIR/$f.md" "$PROFILES_DIR/default.yaml" claude 2>&1)"
    golden_content="$(cat "$PROC_GOLDEN_DIR/$f-default.md")"
    assert_eq "golden proc $f × default" "$golden_content" "$base"
    for profile in "${PROFILES[@]}"; do
        for agent in "${AGENTS[@]}"; do
            cmp="$($RENDER "$SKILL_DIR/$f.md" "$PROFILES_DIR/$profile.yaml" "$agent" 2>&1)"
            assert_eq "proc $f invariance $profile/$agent" "$base" "$cmp"
        done
    done
done

# === Test 2s: the shortcode surface survives every entry-point render ===
#
# Step 0 derives the menu from the Capabilities section at runtime, so the only
# thing a render test can pin is that every code and rule is PRESENT to be
# derived from.

echo "=== Test 2s: shortcodes, rules and the ambiguous-operand rule present ==="
SHORTCODES=('`>c`' '`>cd`' '`>e`' '`>q`' '`>f`' '`>h`' '`>?`')
SHORTCODE_RULES=(
    'The `>` is required.'
    'Embedded is fine; mentioned is not.'
    'nothing else is a code'
    'It carries no authority the'
    '`discuss-compare.md`'
    '`discuss-explain.md`'
    '`discuss-flaws.md`'
    '**Ambiguous operand**'
    'do not pick either: ask'
    'which one is meant, naming both'
)
for profile in "${PROFILES[@]}"; do
    sk="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    for code in "${SHORTCODES[@]}"; do
        assert_contains "$profile: shortcode $code registered" "$code" "$sk"
    done
    for line in "${SHORTCODE_RULES[@]}"; do
        assert_contains "$profile: rule text — '$line'" "$line" "$sk"
    done
done

# === Test 3: no Jinja markers leak ===

echo "=== Test 3: rendered output has no Jinja markers ==="
for profile in "${PROFILES[@]}"; do
    for agent in "${AGENTS[@]}"; do
        rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" "$agent" 2>&1)"
        assert_not_contains "no Jinja {% leak SKILL × $profile × $agent" "{%" "$rendered"
        assert_not_contains "no Jinja {{ leak SKILL × $profile × $agent" "{{" "$rendered"
    done
    for f in "${PROC_FILES_INVARIANT[@]}"; do
        rendered="$($RENDER "$SKILL_DIR/$f.md" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
        assert_not_contains "no Jinja {% leak $f × $profile" "{%" "$rendered"
        assert_not_contains "no Jinja {{ leak $f × $profile" "{{" "$rendered"
    done
done

# === Test 3b: rendered body must NOT re-resolve profile at runtime (t777_26) ===

echo "=== Test 3b: rendered output has no runtime profile-resolution tokens ==="
FORBIDDEN_TOKENS=(
    "aitask_scan_profiles.sh"
    "Execute the Execution Profile Selection Procedure"
    "Select Execution Profile"
    "refresh execution profile"
)
for profile in "${PROFILES[@]}"; do
    rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    for token in "${FORBIDDEN_TOKENS[@]}"; do
        assert_not_contains "SKILL $profile has no '$token'" "$token" "$rendered"
    done
    for f in "${PROC_FILES_INVARIANT[@]}"; do
        rendered="$($RENDER "$SKILL_DIR/$f.md" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
        for token in "${FORBIDDEN_TOKENS[@]}"; do
            assert_not_contains "$f $profile has no '$token'" "$token" "$rendered"
        done
    done
done

# === Test 4: closure completeness per agent (walk-write on-disk output) ===
#
# The procedures are referenced from the entry point as siblings, which the
# walker leaves unrewritten; what must hold is that every procedure lands in
# each agent's rendered dir, and that no other skill's dir is rendered with it.

echo "=== Test 4: closure completeness per agent via walk-write ==="
declare -A RENDER_DIR=(
    [claude]=".claude/skills/$SKILL-fast-"
    [codex]=".agents/skills/$SKILL-fast-codex-"
    [opencode]=".opencode/skills/$SKILL-fast-"
)
for agent in "${AGENTS[@]}"; do
    ./.aitask-scripts/aitask_skill_render.sh "$SKILL" --profile fast --agent "$agent" --force >/dev/null 2>&1
    for f in "${PROC_FILES_INVARIANT[@]}" SKILL; do
        assert_eq "$agent/fast: $f.md rendered into the closure" "yes" \
            "$([[ -f "${RENDER_DIR[$agent]}/$f.md" ]] && echo yes || echo no)"
    done
done
assert_contains "claude/fast: sibling ref left relative" \
    "\`discuss-flaws.md\`" "$(cat "${RENDER_DIR[claude]}/SKILL.md")"

# === Test 5: stub-marker checks (4 surfaces) ===

echo "=== Test 5: 4 stub files contain canonical markers ==="
CLAUDE_STUB=".claude/skills/$SKILL/SKILL.md"
CODEX_STUB=".agents/skills/$SKILL/SKILL.md"
OPENCODE_CMD_STUB=".opencode/commands/$SKILL.md"
OPENCODE_SKILL_STUB=".opencode/skills/$SKILL/SKILL.md"

for stub in "$CLAUDE_STUB" "$CODEX_STUB" "$OPENCODE_CMD_STUB" "$OPENCODE_SKILL_STUB"; do
    body="$(cat "$stub")"
    assert_contains "$stub: resolve_profile uses short name 'brainstorm-discuss'" \
        "aitask_skill_resolve_profile.sh brainstorm-discuss" "$body"
    assert_not_contains "$stub: resolve_profile does NOT use the full slug" \
        "aitask_skill_resolve_profile.sh $SKILL" "$body"
    assert_contains "$stub: skill render invocation present" \
        "aitask_skill_render.sh $SKILL" "$body"
    assert_contains "$stub: Read-and-follow marker present" \
        "Dispatch via Read-and-follow" "$body"
    # The launcher's argv (<task_num> <node_id>...) must reach the rendered variant.
    assert_contains "$stub: forwards ARGUMENTS to the rendered variant" \
        "ARGUMENTS unchanged" "$body"
done

assert_contains "claude stub: --agent claude" "--agent claude" "$(cat "$CLAUDE_STUB")"
assert_contains "codex stub: --agent codex" "--agent codex" "$(cat "$CODEX_STUB")"
assert_contains "opencode cmd stub: --agent opencode" "--agent opencode" "$(cat "$OPENCODE_CMD_STUB")"
assert_contains "opencode skill stub: --agent opencode" "--agent opencode" "$(cat "$OPENCODE_SKILL_STUB")"

assert_contains "claude stub: reads from .claude/skills/$SKILL-<profile>-" \
    ".claude/skills/$SKILL-<profile>-/SKILL.md" "$(cat "$CLAUDE_STUB")"
assert_contains "codex stub: reads from .agents/skills/$SKILL-<profile>-codex-" \
    ".agents/skills/$SKILL-<profile>-codex-/SKILL.md" "$(cat "$CODEX_STUB")"
assert_contains "opencode cmd stub: reads from .opencode/skills/$SKILL-<profile>-" \
    ".opencode/skills/$SKILL-<profile>-/SKILL.md" "$(cat "$OPENCODE_CMD_STUB")"
assert_contains "opencode skill stub: reads from .opencode/skills/$SKILL-<profile>-" \
    ".opencode/skills/$SKILL-<profile>-/SKILL.md" "$(cat "$OPENCODE_SKILL_STUB")"

# === Summary ===

echo ""
echo "Tests: $TOTAL, Passed: $PASS, Failed: $FAIL"
[[ "$FAIL" -eq 0 ]] || exit 1
