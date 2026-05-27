#!/usr/bin/env bash
# test_skill_template.sh - Automated tests for t777_1 foundation:
#   - .aitask-scripts/lib/skill_template.py    (minijinja renderer)
#   - .aitask-scripts/lib/agent_skills_paths.sh (per-agent path helper)
#   - .aitask-scripts/aitask_skill_resolve_profile.sh (active-profile resolver)
# Run: bash tests/test_skill_template.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected '$expected', got '$actual')"
    fi
}

assert_contains() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qi -- "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected', got '$actual')"
    fi
}

# --- Resolve Python interpreter (framework venv) ---

cd "$PROJECT_DIR"
# shellcheck source=.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
PYTHON="$(require_ait_python)"
if ! "$PYTHON" -c 'import minijinja' 2>/dev/null; then
    echo "SKIP: minijinja not installed in framework venv ($PYTHON). Run 'ait setup' first."
    exit 0
fi

# --- Scratch workspace ---

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

CLI="$PROJECT_DIR/.aitask-scripts/lib/skill_template.py"
RESOLVER="$PROJECT_DIR/.aitask-scripts/aitask_skill_resolve_profile.sh"
PATHS_LIB="$PROJECT_DIR/.aitask-scripts/lib/agent_skills_paths.sh"

# --- 1. agent_skills_paths.sh ---

# shellcheck source=.aitask-scripts/lib/agent_skills_paths.sh
source "$PATHS_LIB"

assert_eq "agent_skill_root claude"   ".claude/skills"   "$(agent_skill_root claude)"
assert_eq "agent_skill_root codex"    ".agents/skills"   "$(agent_skill_root codex)"
assert_eq "agent_skill_root opencode" ".opencode/skills" "$(agent_skill_root opencode)"

# Unknown agent: non-zero exit + stderr message
TOTAL=$((TOTAL + 1))
if agent_skill_root bogus >/dev/null 2>&1; then
    FAIL=$((FAIL + 1)); echo "FAIL: agent_skill_root rejects unknown agent"
else
    PASS=$((PASS + 1))
fi

assert_eq "agent_skill_dir claude pick (no profile)"  ".claude/skills/aitask-pick"               "$(agent_skill_dir claude aitask-pick)"
assert_eq "agent_skill_dir claude pick default"       ".claude/skills/aitask-pick-default-"     "$(agent_skill_dir claude aitask-pick default)"
assert_eq "agent_skill_dir claude pick fast"          ".claude/skills/aitask-pick-fast-"        "$(agent_skill_dir claude aitask-pick fast)"
# t834: codex shares its root with future agy, so renders carry an extra -codex- segment.
assert_eq "agent_skill_dir codex pick fast"           ".agents/skills/aitask-pick-fast-codex-"  "$(agent_skill_dir codex aitask-pick fast)"
assert_eq "agent_skill_dir codex pick (no profile)"   ".agents/skills/aitask-pick"              "$(agent_skill_dir codex aitask-pick)"
assert_eq "agent_skill_dir opencode pick fast"        ".opencode/skills/aitask-pick-fast-"      "$(agent_skill_dir opencode aitask-pick fast)"

# t834: agent_shared_skills_root
assert_eq "agent_shared_skills_root claude"   "false" "$(agent_shared_skills_root claude)"
assert_eq "agent_shared_skills_root codex"    "true"  "$(agent_shared_skills_root codex)"
assert_eq "agent_shared_skills_root opencode" "false" "$(agent_shared_skills_root opencode)"

assert_eq "agent_authoring_template pick" ".claude/skills/aitask-pick/SKILL.md.j2" "$(agent_authoring_template aitask-pick)"

# --- 2. skill_template.py — happy path ---

cat > "$TMP_DIR/p_happy.yaml" <<'EOF'
greeting: hello
flag: true
EOF

cat > "$TMP_DIR/t_happy.j2" <<'EOF'
{{ profile.greeting }} {% if profile.flag %}YES{% else %}NO{% endif %}
EOF

OUT="$("$PYTHON" "$CLI" "$TMP_DIR/t_happy.j2" "$TMP_DIR/p_happy.yaml" claude)"
assert_eq "renderer happy path" "hello YES" "$OUT"

# --- 3. skill_template.py — agent branching ---

cat > "$TMP_DIR/p_agent.yaml" <<'EOF'
x: 1
EOF

cat > "$TMP_DIR/t_agent.j2" <<'EOF'
{% if agent == "claude" %}A{% else %}B{% endif %}
EOF

OUT_CLAUDE="$("$PYTHON" "$CLI" "$TMP_DIR/t_agent.j2" "$TMP_DIR/p_agent.yaml" claude)"
OUT_CODEX="$("$PYTHON" "$CLI" "$TMP_DIR/t_agent.j2" "$TMP_DIR/p_agent.yaml" codex)"
assert_eq "agent branch: claude -> A" "A" "$OUT_CLAUDE"
assert_eq "agent branch: codex  -> B" "B" "$OUT_CODEX"

# --- 4. skill_template.py — strict undefined wraps with filename ---

cat > "$TMP_DIR/p_min.yaml" <<'EOF'
present: yep
EOF

cat > "$TMP_DIR/t_missing.j2" <<'EOF'
{{ profile.missing_key }}
EOF

set +e
ERR_OUTPUT="$("$PYTHON" "$CLI" "$TMP_DIR/t_missing.j2" "$TMP_DIR/p_min.yaml" claude 2>&1)"
RC=$?
set -e
TOTAL=$((TOTAL + 1))
if [[ $RC -ne 0 ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1)); echo "FAIL: strict undefined should exit non-zero (got rc=$RC, output: $ERR_OUTPUT)"
fi
assert_contains "strict-undefined error names the template file" "t_missing.j2" "$ERR_OUTPUT"

# --- 5. aitask_skill_resolve_profile.sh — precedence ---

# Build a scratch repo layout for the resolver
SCRATCH_REPO="$TMP_DIR/repo"
mkdir -p "$SCRATCH_REPO/aitasks/metadata/profiles"
# Copy the resolver into the scratch repo so SCRIPT_DIR/../aitasks resolves
mkdir -p "$SCRATCH_REPO/.aitask-scripts"
cp "$RESOLVER" "$SCRATCH_REPO/.aitask-scripts/"

cat > "$SCRATCH_REPO/aitasks/metadata/project_config.yaml" <<'EOF'
default_profiles:
  pick: default
  explore: default
EOF

cat > "$SCRATCH_REPO/aitasks/metadata/userconfig.yaml" <<'EOF'
default_profiles:
  pick: fast
EOF

OUT="$(cd "$SCRATCH_REPO" && ./.aitask-scripts/aitask_skill_resolve_profile.sh pick)"
assert_eq "resolver: userconfig wins over project_config" "fast" "$OUT"

OUT="$(cd "$SCRATCH_REPO" && ./.aitask-scripts/aitask_skill_resolve_profile.sh explore)"
assert_eq "resolver: falls through to project_config when userconfig key missing" "default" "$OUT"

OUT="$(cd "$SCRATCH_REPO" && ./.aitask-scripts/aitask_skill_resolve_profile.sh review)"
assert_eq "resolver: 'default' when both configs lack the key" "default" "$OUT"

# Resolver with no userconfig at all
rm "$SCRATCH_REPO/aitasks/metadata/userconfig.yaml"
OUT="$(cd "$SCRATCH_REPO" && ./.aitask-scripts/aitask_skill_resolve_profile.sh pick)"
assert_eq "resolver: uses project_config when no userconfig exists" "default" "$OUT"

# Resolver with no configs at all
rm "$SCRATCH_REPO/aitasks/metadata/project_config.yaml"
OUT="$(cd "$SCRATCH_REPO" && ./.aitask-scripts/aitask_skill_resolve_profile.sh pick)"
assert_eq "resolver: 'default' when no configs exist" "default" "$OUT"

# --- 6. t777_22 unit tests: discover_refs + rewrite_ref ---

# Scratch closure: A (sibling/skill-relative ref), B (target of ref). Use the
# real repo's .claude/skills/ tree under a _t777_22_test_unit_ prefix so the
# resolver can find the files.

REAL_SK_DIR="$PROJECT_DIR/.claude/skills"
UNIT_A="${REAL_SK_DIR}/_t777_22_test_unit_a"
UNIT_B="${REAL_SK_DIR}/_t777_22_test_unit_b"
mkdir -p "$UNIT_A" "$UNIT_B"
cat > "$UNIT_A/SKILL.md" <<'EOF'
# Skill A
EOF
cat > "$UNIT_B/SKILL.md" <<'EOF'
# Skill B
EOF
unit_cleanup() {
    rm -rf "${REAL_SK_DIR}"/_t777_22_test_unit_*
}
trap unit_cleanup EXIT

# Helper: invoke discover_refs and print resolved kind+rel paths.
disco_call() {
    local text="$1" current="$2"
    "$PYTHON" -c "
import sys
sys.path.insert(0, '$PROJECT_DIR/.aitask-scripts/lib')
from skill_template import discover_refs
from pathlib import Path
text = sys.stdin.read()
current = Path('$current').resolve()
repo_root = Path('$PROJECT_DIR').resolve()
for r in discover_refs(text, current, repo_root):
    rel = r['resolved_source'].relative_to(repo_root)
    print(r['kind'], r['original_str'], str(rel))
" <<< "$text"
}

# Full-path ref
OUT="$(disco_call 'see .claude/skills/_t777_22_test_unit_a/SKILL.md for details' "$UNIT_B/SKILL.md")"
assert_contains "discover_refs: full-path matched" "full" "$OUT"
assert_contains "discover_refs: full-path resolved" ".claude/skills/_t777_22_test_unit_a/SKILL.md" "$OUT"

# Cross-agent-root full-path ref (says .agents/skills/... but resolves under .claude/skills/)
OUT="$(disco_call 'see .agents/skills/_t777_22_test_unit_a/SKILL.md here' "$UNIT_B/SKILL.md")"
assert_contains "discover_refs: cross-agent-root full-path normalised to .claude/" ".claude/skills/_t777_22_test_unit_a/SKILL.md" "$OUT"

# Sibling ref (B references its own dir's SKILL.md = self)
OUT="$(disco_call 'see SKILL.md for context' "$UNIT_B/SKILL.md")"
assert_contains "discover_refs: sibling matched as sibling kind" "sibling" "$OUT"

# Skill-relative ref
OUT="$(disco_call 'see _t777_22_test_unit_a/SKILL.md' "$UNIT_B/SKILL.md")"
assert_contains "discover_refs: skill-relative matched" "skill_relative" "$OUT"

# Non-existent ref → filtered (no output)
OUT="$(disco_call 'edit the imaginary.md file please' "$UNIT_B/SKILL.md")"
TOTAL=$((TOTAL + 1))
if [[ -z "$OUT" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1)); echo "FAIL: discover_refs should filter nonexistent refs (got: $OUT)"
fi

# Placeholder ref containing <> not matched
OUT="$(disco_call '<placeholder>/SKILL.md is just a template marker' "$UNIT_B/SKILL.md")"
TOTAL=$((TOTAL + 1))
if [[ -z "$OUT" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1)); echo "FAIL: discover_refs should not match <placeholder> strings (got: $OUT)"
fi

# Helper: invoke rewrite_ref and print result.
rewrite_call() {
    local kind="$1" ref_dir="$2" ref_file="$3" agent="$4" profile_name="$5"
    "$PYTHON" -c "
import sys
sys.path.insert(0, '$PROJECT_DIR/.aitask-scripts/lib')
from skill_template import rewrite_ref
ref = {'kind': '$kind', 'ref_dir': '$ref_dir', 'ref_file': '$ref_file'}
print(rewrite_ref(ref, '$agent', '$profile_name'))
"
}

assert_eq "rewrite_ref: claude full-path" \
    ".claude/skills/task-workflow-fast-/planning.md" \
    "$(rewrite_call full task-workflow planning.md claude fast)"
# t834: codex shares its root with future agy, so refs carry an extra -codex- segment.
assert_eq "rewrite_ref: codex full-path (shared root → agent suffix)" \
    ".agents/skills/task-workflow-fast-codex-/planning.md" \
    "$(rewrite_call full task-workflow planning.md codex fast)"
assert_eq "rewrite_ref: opencode full-path" \
    ".opencode/skills/task-workflow-fast-/planning.md" \
    "$(rewrite_call full task-workflow planning.md opencode fast)"
assert_eq "rewrite_ref: sibling unchanged" \
    "planning.md" \
    "$(rewrite_call sibling task-workflow planning.md claude fast)"
assert_eq "rewrite_ref: skill_relative becomes full" \
    ".claude/skills/task-workflow-fast-/planning.md" \
    "$(rewrite_call skill_relative task-workflow planning.md claude fast)"
# t834: skill_relative ref for codex also carries the -codex- segment.
assert_eq "rewrite_ref: skill_relative codex (shared root → agent suffix)" \
    ".agents/skills/task-workflow-fast-codex-/planning.md" \
    "$(rewrite_call skill_relative task-workflow planning.md codex fast)"

# AGENT_ROOTS mapping spot-check
AR_OUT="$("$PYTHON" -c "
import sys
sys.path.insert(0, '$PROJECT_DIR/.aitask-scripts/lib')
from skill_template import AGENT_ROOTS
for k, v in AGENT_ROOTS.items():
    print(k, v)
")"
assert_contains "AGENT_ROOTS claude maps to .claude/skills" "claude .claude/skills" "$AR_OUT"
assert_contains "AGENT_ROOTS opencode maps to .opencode/skills" "opencode .opencode/skills" "$AR_OUT"

# --- Summary ---

echo
echo "PASS: $PASS, FAIL: $FAIL, TOTAL: $TOTAL"
[[ $FAIL -eq 0 ]]
