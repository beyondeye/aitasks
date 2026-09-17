#!/usr/bin/env bash
# test_brainstorm_discuss_skill_contract.sh — Contract guard for
# /aitask-brainstorm-discuss (t1823_2, risk mitigation skill_contract_test).
#
# The skill's defining behaviours are prose: advisory-only authority over the
# brainstorm session, a fast start that analyses nothing up front, a menu derived
# from the Capabilities section rather than hardcoded, and a closure that stays
# free of the shadow companion's concern-fenced procedures. This test renders the
# `default` variant with walk-write into a temp repo root and checks those
# properties on the RENDERED tree (what an agent actually reads).
#
# The temp root carries a copy of the shadow skill as well, so a reference to a
# shadow procedure would really resolve and drag it into the closure — without
# that copy the closure check could never fire. Two mutants, each in its own temp
# root (the real skill files are never edited), prove the checks are live:
#   M1 — discuss-audience.md names a shadow procedure path  -> closure violations
#   M2 — the guardrail stops naming node YAML               -> guardrail violation
# Run: bash tests/test_brainstorm_discuss_skill_contract.sh

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
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/ait_discuss_contract.XXXXXX")"
trap 'rm -rf "$TMP_ROOT"' EXIT

# make_root <name> — a minimal repo root holding copies of the discuss skill,
# the shadow skill and the default profile. Prints the root path.
make_root() {
    local root="$TMP_ROOT/$1"
    mkdir -p "$root/.claude/skills" "$root/aitasks/metadata/profiles"
    cp -R "$PROJECT_DIR/.claude/skills/$SKILL" "$root/.claude/skills/$SKILL"
    cp -R "$PROJECT_DIR/.claude/skills/aitask-shadow" "$root/.claude/skills/aitask-shadow"
    cp "$PROJECT_DIR/aitasks/metadata/profiles/default.yaml" "$root/aitasks/metadata/profiles/default.yaml"
    printf '%s\n' "$root"
}

# render_root <root> — walk-write the default/claude closure into <root>.
render_root() {
    local root="$1"
    "$PYTHON" "$PROJECT_DIR/.aitask-scripts/lib/skill_template.py" walk-write \
        "$root/.claude/skills/$SKILL/SKILL.md.j2" \
        "$root/aitasks/metadata/profiles/default.yaml" claude "$root" --force
}

# section <file> <heading-prefix> — the lines from the first "## <prefix>" heading
# up to (not including) the next "## " heading.
section() {
    awk -v h="## $2" '
        index($0, h) == 1 { on = 1; print; next }
        on && /^## / { exit }
        on { print }
    ' "$1"
}

# contract_violations <root> — print one label per violated contract property
# (nothing when the rendered skill honours every one). Pure: never exits.
contract_violations() {
    local root="$1"
    local rdir="$root/.claude/skills/$SKILL-default-"
    local sk="$rdir/SKILL.md"
    if [[ ! -f "$sk" ]]; then
        echo "render:missing"
        return 0
    fi

    local guard step0
    guard="$(section "$sk" "Guardrail — advisory only (load-bearing)")"
    step0="$(section "$sk" "Step 0")"

    # Guardrail names every protected surface.
    [[ -n "$guard" ]] || echo "guardrail:missing"
    grep -q "proposal file" <<<"$guard" || echo "guardrail:proposal-files"
    grep -q "node YAML" <<<"$guard" || echo "guardrail:node-yaml"
    grep -q "session state" <<<"$guard" || echo "guardrail:session-state"
    grep -q "mutating" <<<"$guard" || echo "guardrail:mutating-commands"

    # Step 0: resolves through the helper and forbids up-front analysis.
    grep -q "aitask_brainstorm_context.sh" <<<"$step0" || echo "step0:helper"
    grep -q "does not process or analyse the proposals up front" <<<"$step0" \
        || echo "step0:no-upfront-analysis"
    grep -q "This is a skim, not an analysis" <<<"$step0" || echo "step0:skim-only"

    # Menu is derived, never hardcoded: the maintainer note is present and Step 0
    # holds no capability shortcode (only the >? reprint rule is allowed there).
    grep -q "MAINTAINER: Do NOT hardcode the capability list" <<<"$step0" \
        || echo "menu:maintainer-comment"
    grep -q "by reading the \*\*Capabilities\*\* section" <<<"$step0" \
        || echo "menu:derived"
    local code
    for code in '`>c`' '`>cd`' '`>e`' '`>q`' '`>f`' '`>h`'; do
        grep -qF "$code" <<<"$step0" && echo "menu:hardcoded-$code"
    done

    # Every rendered procedure opens with the Advisory-only header.
    local f
    for f in "$rdir"/*.md; do
        [[ "$(basename "$f")" == "SKILL.md" ]] && continue
        head -n 5 "$f" | grep -q '^\*\*Advisory-only:\*\*' \
            || echo "procedure:advisory-header:$(basename "$f")"
    done

    # Closure hygiene over the WHOLE rendered tree, not just the skill dir.
    if grep -rqF "===AITASK-CONCERNS===" "$root/.claude/skills" --include='*.md' \
        --exclude-dir=aitask-shadow 2>/dev/null; then
        echo "closure:concern-fence"
    fi
    local d
    for d in "$root/.claude/skills"/aitask-shadow-*; do
        [[ -e "$d" ]] && echo "closure:shadow-rendered:$(basename "$d")"
    done
    return 0
}

# === Test 1: the real skill honours the contract ===

echo "=== Test 1: rendered default variant honours every contract property ==="
real_root="$(make_root real)"
render_root "$real_root"
assert_eq "real skill: rendered SKILL.md exists" "yes" \
    "$([[ -f "$real_root/.claude/skills/$SKILL-default-/SKILL.md" ]] && echo yes || echo no)"
assert_eq "real skill: no contract violations" "" "$(contract_violations "$real_root")"

# === Test 2 (negative control M1): a shadow procedure path drags its closure in ===

echo "=== Test 2: mutant naming a shadow procedure fails the closure checks ==="
m1_root="$(make_root mutant_shadow_ref)"
printf '\nSee also aitask-shadow/round-preamble.md for the original rules.\n' \
    >>"$m1_root/.claude/skills/$SKILL/discuss-audience.md"
render_root "$m1_root"
m1="$(contract_violations "$m1_root")"
# Liveness first: the mutant ref must really have resolved, or the checks below
# would be failing for some other reason (or passing vacuously).
assert_eq "M1 control is live: the shadow skill was rendered into the closure" "yes" \
    "$([[ -d "$m1_root/.claude/skills/aitask-shadow-default-" ]] && echo yes || echo no)"
assert_contains "M1: shadow render is reported" "closure:shadow-rendered:aitask-shadow-default-" "$m1"
assert_contains "M1: concern fence is reported" "closure:concern-fence" "$m1"
assert_not_contains "M1: guardrail checks unaffected (guard-specific signal)" "guardrail:" "$m1"

# === Test 3 (negative control M2): dropping a protected surface from the guardrail ===

echo "=== Test 3: mutant guardrail without node YAML fails the guardrail check ==="
m2_root="$(make_root mutant_guardrail)"
"$PYTHON" - "$m2_root/.claude/skills/$SKILL/SKILL.md.j2" <<'PY'
import sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
head, sep, guard = s.partition("## Guardrail — advisory only (load-bearing)")
assert sep, "guardrail heading not found"
new_guard = guard.replace("node YAML", "node metadata")
assert new_guard != guard, "mutation did not apply"
open(p, "w", encoding="utf-8").write(head + sep + new_guard)
PY
render_root "$m2_root"
m2="$(contract_violations "$m2_root")"
assert_eq "M2: exactly the node-yaml guardrail violation" "guardrail:node-yaml" "$m2"

# === Summary ===

echo ""
echo "Tests: $TOTAL, Passed: $PASS, Failed: $FAIL"
[[ "$FAIL" -eq 0 ]] || exit 1
