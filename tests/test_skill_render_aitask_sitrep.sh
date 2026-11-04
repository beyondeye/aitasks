#!/usr/bin/env bash
# test_skill_render_aitask_sitrep.sh - Render regression tests for t2175_4:
#   - .claude/skills/aitask-sitrep/SKILL.md.j2 (the single authoring file)
#   - 4 per-agent stubs (claude / codex / opencode command + opencode skill)
#   - 3 entry-point goldens under tests/golden/skills/aitask-sitrep/
# Coverage:
#   0.  The skill dir holds no procedure files (the closure is the entry point).
#   0c. The walked closure is EXACTLY SKILL.md.j2 — no other skill is dragged in.
#   1.  Per-profile golden diff (claude render).
#   1b. Agent-dimension invariance (no {% if agent %}).
#   2s. Shortcodes and shortcode rules present in every render.
#   3.  No Jinja markers leak.
#   3b. Rendered output must NOT re-resolve the profile (t777_26 tokens).
#   4.  aitask_skill_render.sh --force writes the entry point for every agent.
#   5.  Stub markers on all 4 stub surfaces (resolver key `sitrep`).
# Behaviour (the documented commands against the real helpers) is
# tests/test_sitrep_skill_contract.sh.
# Run: bash tests/test_skill_render_aitask_sitrep.sh

# shellcheck disable=SC2016  # backticks in single quotes are literal markdown, not command substitution
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

PASS=0
FAIL=0
TOTAL=0

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

SKILL="aitask-sitrep"
RENDER="$PYTHON $PROJECT_DIR/.aitask-scripts/lib/skill_template.py"
SKILL_DIR=".claude/skills/$SKILL"
TEMPLATE="$SKILL_DIR/SKILL.md.j2"
SKILL_GOLDEN_DIR="tests/golden/skills/$SKILL"
PROFILES_DIR="aitasks/metadata/profiles"

PROFILES=(default fast remote)
AGENTS=(claude codex opencode)

# === Test 0: no procedure files ===

echo "=== Test 0: the skill dir holds only the stub and the template ==="
on_disk="$(find "$SKILL_DIR" -maxdepth 1 -type f -exec basename {} \; | sort)"
assert_eq "skill dir = SKILL.md + SKILL.md.j2" \
    "$(printf '%s\n' SKILL.md SKILL.md.j2)" "$on_disk"

# === Test 0c: the walked closure is exactly the template ===

echo "=== Test 0c: closure source set is exactly SKILL.md.j2 ==="
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
assert_eq "closure sources == SKILL.md.j2" "$TEMPLATE" "$closure"

# === Test 1: per-profile golden diffs ===

echo "=== Test 1: golden diffs × 3 profiles ==="
for profile in "${PROFILES[@]}"; do
    rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    golden_content="$(cat "$SKILL_GOLDEN_DIR/SKILL-${profile}-claude.md")"
    assert_eq "golden SKILL × $profile" "$golden_content" "$rendered"
done

# === Test 1b: agent dimension invariance ===

echo "=== Test 1b: agent renders are byte-identical ==="
for profile in "${PROFILES[@]}"; do
    base="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    for agent in codex opencode; do
        cmp="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" "$agent" 2>&1)"
        assert_eq "agent invariance $profile/$agent" "$base" "$cmp"
    done
done

# === Test 2s: the shortcode surface survives every render ===
#
# Step 0 derives the menu from the Capabilities section at runtime, so a render
# test can only pin that every code and rule is present to be derived from.

echo "=== Test 2s: shortcodes and shortcode rules present ==="
SHORTCODES=('### `>s`' '### `>t`' '### `>w`' '### `>q`' '### `>tr`' '### `>p`'
            '### `>x' '### `>r`' '### `>?`')
SHORTCODE_RULES=(
    'nothing else is a code, and the `>` is'
    'carries no authority the same request in words would not have'
    'gets an'
    'answer in words'
)
for profile in "${PROFILES[@]}"; do
    sk="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    for code in "${SHORTCODES[@]}"; do
        assert_contains "$profile: shortcode heading $code" "$code" "$sk"
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
        assert_not_contains "no Jinja {% leak × $profile × $agent" "{%" "$rendered"
        assert_not_contains "no Jinja {{ leak × $profile × $agent" "{{" "$rendered"
    done
done

# === Test 3b: no runtime profile resolution (t777_26) ===

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
done

# === Test 4: every agent's rendered dir receives the entry point ===

echo "=== Test 4: aitask_skill_render.sh --force per agent ==="
declare -A RENDER_DIR=(
    [claude]=".claude/skills/$SKILL-fast-"
    [codex]=".agents/skills/$SKILL-fast-codex-"
    [opencode]=".opencode/skills/$SKILL-fast-"
)
for agent in "${AGENTS[@]}"; do
    ./.aitask-scripts/aitask_skill_render.sh "$SKILL" --profile fast --agent "$agent" --force >/dev/null 2>&1
    assert_eq "$agent/fast: SKILL.md rendered" "yes" \
        "$([[ -f "${RENDER_DIR[$agent]}/SKILL.md" ]] && echo yes || echo no)"
    assert_eq "$agent/fast: render equals the fast golden" \
        "$(cat "$SKILL_GOLDEN_DIR/SKILL-fast-claude.md")" "$(cat "${RENDER_DIR[$agent]}/SKILL.md")"
done

# === Test 5: stub markers (4 surfaces) ===

echo "=== Test 5: 4 stub files contain canonical markers ==="
CLAUDE_STUB=".claude/skills/$SKILL/SKILL.md"
CODEX_STUB=".agents/skills/$SKILL/SKILL.md"
OPENCODE_CMD_STUB=".opencode/commands/$SKILL.md"
OPENCODE_SKILL_STUB=".opencode/skills/$SKILL/SKILL.md"

for stub in "$CLAUDE_STUB" "$CODEX_STUB" "$OPENCODE_CMD_STUB" "$OPENCODE_SKILL_STUB"; do
    body="$(cat "$stub")"
    assert_contains "$stub: resolve_profile uses short name 'sitrep'" \
        "aitask_skill_resolve_profile.sh sitrep" "$body"
    assert_not_contains "$stub: resolve_profile does NOT use the full slug" \
        "aitask_skill_resolve_profile.sh $SKILL" "$body"
    assert_contains "$stub: skill render invocation present" \
        "aitask_skill_render.sh $SKILL" "$body"
    assert_contains "$stub: Read-and-follow marker present" \
        "Dispatch via Read-and-follow" "$body"
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
echo "=== Results: $PASS passed, $FAIL failed, $TOTAL total ==="
[[ "$FAIL" -eq 0 ]]
