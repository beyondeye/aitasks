#!/usr/bin/env bash
set -euo pipefail

# Test OpenCode setup pipeline: packaging, staging, assembly, idempotency, JSON merge

PASS=0
FAIL=0
# shellcheck disable=SC2034  # TOTAL is mutated by the sourced asserts.sh helpers.
TOTAL=0

# Shared assertion helpers (see tests/lib/asserts.sh). Resolve tests/lib via
# the script dir up-front (later code reassigns PROJECT_DIR to a fake repo).
# shellcheck source=lib/asserts.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/asserts.sh"

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEST_DIR="$(mktemp -d)"
trap 'rm -rf "$TEST_DIR"' EXIT

AUDIT="$REPO_DIR/.aitask-scripts/aitask_audit_wrappers.sh"

# Counts for Tests 1-2 are read from the very dirs those tests package, so they
# guard ONE thing: packaging/staging drift — did the pipeline preserve everything
# it was handed? They cannot detect a wrapper missing from the source tree, since
# a missing file lowers both sides of the comparison (t1325). Source-wrapper
# completeness is Test 0's job; keep the two concerns separate.
#
# `expected_packaged_count` is deliberately not "the number of skill wrappers":
# the glob also matches the committed rendered variants (aitask-pickrem-remote-,
# aitask-pickweb-remote-), and it should — the release workflow
# (.github/workflows/release.yml:72) copies every .opencode/skills/*/ dir, so the
# packaged set is what this must mirror.
expected_packaged_count=$(git -C "$REPO_DIR" ls-files '.opencode/skills/aitask-*/SKILL.md' | wc -l | tr -d ' ')
expected_command_count=$(find "$REPO_DIR/.opencode/commands" -type f -name "*.md" | wc -l | tr -d ' ')

echo "=== Test 0: wrapper-set parity across the ported agent trees ==="

# Independent ground truth for "which skills must have an OpenCode wrapper".
# The three ported trees (.agents/skills, .opencode/skills, .opencode/commands)
# are authored independently, so requiring identical membership does not derive
# the expectation from the tree under test. This is the check that catches the
# real omission: t1210_3 gave aitask-trail a Codex stub and an OpenCode command
# wrapper but no OpenCode skill-dir stub, and it stayed missing until t1317.
parity_rc=0
parity_out="$("$AUDIT" parity 2>&1)" || parity_rc=$?
assert_exit_zero_rc "Test 0: parity check ran" "$parity_rc"
assert_eq "Test 0: wrapper trees agree (no PARITY_GAP / ORPHAN)" "" "$parity_out"

echo ""
echo "=== Test 0b: parity negative controls (every branch is load-bearing) ==="

# A green Test 0 proves nothing unless a broken tree actually fails it. Each
# control mutates a SYNTHETIC fixture under $TEST_DIR — never the real repo — so
# the restore is a rebuild of the fixture, explicitly not `git checkout`, which
# would also discard unrelated in-flight work.
FIXTURE="$TEST_DIR/parity_fixture"

build_parity_fixture() {
    local n
    rm -rf "$FIXTURE"
    mkdir -p "$FIXTURE/.opencode/commands"
    for n in aitask-alpha aitask-beta; do
        mkdir -p "$FIXTURE/.claude/skills/$n" \
                 "$FIXTURE/.agents/skills/$n" \
                 "$FIXTURE/.opencode/skills/$n"
        echo "stub" > "$FIXTURE/.claude/skills/$n/SKILL.md"
        echo "stub" > "$FIXTURE/.agents/skills/$n/SKILL.md"
        echo "stub" > "$FIXTURE/.opencode/skills/$n/SKILL.md"
        echo "stub" > "$FIXTURE/.opencode/commands/$n.md"
    done
    # Decoys: rendered per-profile variants (trailing hyphen) are generated
    # artifacts and must be invisible to parity in every tree. Counting them is
    # exactly what makes a naive `git ls-files` glob report 30 wrappers, not 28.
    mkdir -p "$FIXTURE/.claude/skills/aitask-alpha-fast-" \
             "$FIXTURE/.opencode/skills/aitask-alpha-fast-"
    echo "rendered" > "$FIXTURE/.claude/skills/aitask-alpha-fast-/SKILL.md"
    echo "rendered" > "$FIXTURE/.opencode/skills/aitask-alpha-fast-/SKILL.md"
}

# Sets NC_OUT (stdout+stderr of the reporting form) and NC_RC (exit status of the
# --strict form: 2 == findings, distinct from die()'s 1).
run_parity_fixture() {
    NC_RC=0
    NC_OUT="$("$AUDIT" parity "$FIXTURE" 2>&1)" || NC_RC=$?
    assert_exit_zero_rc "  (reporting form always exits 0)" "$NC_RC"
    NC_RC=0
    "$AUDIT" parity --strict "$FIXTURE" >/dev/null 2>&1 || NC_RC=$?
}

# --- NC-0: positive control — a correct fixture is clean --------------------
build_parity_fixture
run_parity_fixture
assert_eq "NC-0: correct fixture emits nothing" "" "$NC_OUT"
assert_eq "NC-0: --strict exits 0 on a clean tree" "0" "$NC_RC"
assert_not_contains "NC-0: rendered variants are ignored" "aitask-alpha-fast-" "$NC_OUT"

# Each control removes exactly ONE file, so the COMPLETE expected output is a
# single line. Assert full-output equality, not substring containment: a
# regression that emitted the expected line *plus* spurious gaps for the other
# trees would satisfy a `assert_contains` while producing exactly the misleading
# pre-commit diagnostics these controls exist to prevent.

# --- NC-1: wrapper missing from the Codex tree ------------------------------
rm -f "$FIXTURE/.agents/skills/aitask-beta/SKILL.md"
run_parity_fixture
assert_eq "NC-1: agents-tree omission IS caught, and nothing else is" \
    "PARITY_GAP:agents:aitask-beta" "$NC_OUT"
assert_eq "NC-1: --strict exits 2 on findings" "2" "$NC_RC"

# --- NC-2: wrapper missing from the OpenCode skill-dir tree (the t1317 shape) ---
build_parity_fixture
rm -f "$FIXTURE/.opencode/skills/aitask-beta/SKILL.md"
run_parity_fixture
assert_eq "NC-2: opencode-skill omission IS caught, and nothing else is" \
    "PARITY_GAP:opencode-skill:aitask-beta" "$NC_OUT"
assert_eq "NC-2: --strict exits 2 on findings" "2" "$NC_RC"

# --- NC-3: wrapper missing from the OpenCode command tree -------------------
build_parity_fixture
rm -f "$FIXTURE/.opencode/commands/aitask-beta.md"
run_parity_fixture
assert_eq "NC-3: opencode-command omission IS caught, and nothing else is" \
    "PARITY_GAP:opencode-command:aitask-beta" "$NC_OUT"
assert_eq "NC-3: --strict exits 2 on findings" "2" "$NC_RC"

# --- NC-4: ORPHAN is a DISTINCT branch --------------------------------------
# All three wrappers still present, but the source-of-truth skill is gone: this
# must report ORPHAN and nothing else — in particular no parity gap.
build_parity_fixture
rm -f "$FIXTURE/.claude/skills/aitask-beta/SKILL.md"
run_parity_fixture
assert_eq "NC-4: orphan wrapper IS caught, with no parity gap alongside it" \
    "ORPHAN:aitask-beta" "$NC_OUT"
assert_eq "NC-4: --strict exits 2 on findings" "2" "$NC_RC"

# --- NC-5: an absent tree root means "agent not installed", not "all missing" ---
# Without this rule the verifier would report every skill as a gap in a
# Claude-only consumer project, so the rule is load-bearing, not cosmetic.
build_parity_fixture
rm -rf "$FIXTURE/.agents/skills"
run_parity_fixture
assert_eq "NC-5: absent tree root is skipped, not reported" "" "$NC_OUT"
assert_eq "NC-5: --strict exits 0 when a tree is simply not installed" "0" "$NC_RC"

# --- NC-5b: with fewer than two trees, ORPHAN still runs ---------------------
build_parity_fixture
rm -rf "$FIXTURE/.agents/skills" "$FIXTURE/.opencode/commands"
rm -f "$FIXTURE/.claude/skills/aitask-beta/SKILL.md"
run_parity_fixture
assert_eq "NC-5b: ORPHAN still detected with a single tree present, and no gap is claimed" \
    "ORPHAN:aitask-beta" "$NC_OUT"

# --- NC-6: full restore returns the fixture to clean -------------------------
build_parity_fixture
run_parity_fixture
assert_eq "NC-6: rebuilt fixture is clean again" "" "$NC_OUT"
assert_eq "NC-6: --strict exits 0 again" "0" "$NC_RC"

echo ""

echo "=== Test 1: OpenCode skills packaging (release workflow sim) ==="
mkdir -p "$TEST_DIR/opencode_skills"
mkdir -p "$TEST_DIR/opencode_commands"
while IFS= read -r skill_md; do
    skill_dir="$REPO_DIR/$(dirname "$skill_md")"
    [ -d "$skill_dir" ] || continue
    cp -r "$skill_dir" "$TEST_DIR/opencode_skills/$(basename "$skill_dir")"
done < <(git -C "$REPO_DIR" ls-files '.opencode/skills/aitask-*/SKILL.md')
[ -f "$REPO_DIR/.opencode/skills/opencode_tool_mapping.md" ] && \
    cp "$REPO_DIR/.opencode/skills/opencode_tool_mapping.md" "$TEST_DIR/opencode_skills/"
[ -f "$REPO_DIR/.opencode/skills/opencode_planmode_prereqs.md" ] && \
    cp "$REPO_DIR/.opencode/skills/opencode_planmode_prereqs.md" "$TEST_DIR/opencode_skills/"
[ -d "$REPO_DIR/.opencode/commands" ] && \
    cp -r "$REPO_DIR/.opencode/commands/." "$TEST_DIR/opencode_commands/"

skill_count=$(find "$TEST_DIR/opencode_skills" -name "SKILL.md" -type f | wc -l | tr -d ' ')
command_count=$(find "$TEST_DIR/opencode_commands" -type f -name "*.md" | wc -l | tr -d ' ')
assert_eq "Packaged $expected_packaged_count skill dirs" "$expected_packaged_count" "$skill_count"
assert_eq "Tool mapping packaged" "true" "$([ -f "$TEST_DIR/opencode_skills/opencode_tool_mapping.md" ] && echo true || echo false)"
assert_eq "Planmode prereqs packaged" "true" "$([ -f "$TEST_DIR/opencode_skills/opencode_planmode_prereqs.md" ] && echo true || echo false)"
assert_eq "Packaged $expected_command_count command wrappers" "$expected_command_count" "$command_count"

echo ""
echo "=== Test 2: OpenCode staging (install.sh sim) ==="
INSTALL_DIR="$TEST_DIR/install_sim"
mkdir -p "$INSTALL_DIR/aitasks/metadata"
cp -r "$TEST_DIR/opencode_skills" "$INSTALL_DIR/opencode_skills"
cp -r "$TEST_DIR/opencode_commands" "$INSTALL_DIR/opencode_commands"

# Inline staging logic (mirrors install_opencode_staging)
mkdir -p "$INSTALL_DIR/aitasks/metadata/opencode_skills"
for skill_dir in "$INSTALL_DIR/opencode_skills"/aitask-*/; do
    [[ -d "$skill_dir" ]] || continue
    skill_name="$(basename "$skill_dir")"
    mkdir -p "$INSTALL_DIR/aitasks/metadata/opencode_skills/$skill_name"
    cp "$skill_dir/SKILL.md" "$INSTALL_DIR/aitasks/metadata/opencode_skills/$skill_name/SKILL.md"
done
[ -f "$INSTALL_DIR/opencode_skills/opencode_tool_mapping.md" ] && \
    cp "$INSTALL_DIR/opencode_skills/opencode_tool_mapping.md" "$INSTALL_DIR/aitasks/metadata/opencode_skills/"
[ -f "$INSTALL_DIR/opencode_skills/opencode_planmode_prereqs.md" ] && \
    cp "$INSTALL_DIR/opencode_skills/opencode_planmode_prereqs.md" "$INSTALL_DIR/aitasks/metadata/opencode_skills/"
rm -rf "$INSTALL_DIR/opencode_skills"

mkdir -p "$INSTALL_DIR/aitasks/metadata/opencode_commands"
cp -r "$INSTALL_DIR/opencode_commands/." "$INSTALL_DIR/aitasks/metadata/opencode_commands/"
rm -rf "$INSTALL_DIR/opencode_commands"

staged_count=$(find "$INSTALL_DIR/aitasks/metadata/opencode_skills" -name "SKILL.md" -type f | wc -l | tr -d ' ')
staged_command_count=$(find "$INSTALL_DIR/aitasks/metadata/opencode_commands" -type f -name "*.md" | wc -l | tr -d ' ')
assert_eq "Staged $expected_packaged_count skill dirs to metadata" "$expected_packaged_count" "$staged_count"
assert_eq "Tool mapping staged" "true" "$([ -f "$INSTALL_DIR/aitasks/metadata/opencode_skills/opencode_tool_mapping.md" ] && echo true || echo false)"
assert_eq "Planmode prereqs staged" "true" "$([ -f "$INSTALL_DIR/aitasks/metadata/opencode_skills/opencode_planmode_prereqs.md" ] && echo true || echo false)"
assert_eq "Staged $expected_command_count command wrappers" "$expected_command_count" "$staged_command_count"
assert_eq "Skills source cleaned up" "false" "$([ -d "$INSTALL_DIR/opencode_skills" ] && echo true || echo false)"
assert_eq "Commands source cleaned up" "false" "$([ -d "$INSTALL_DIR/opencode_commands" ] && echo true || echo false)"

echo ""
echo "=== Test 3: Instruction assembly (Layer 1 + Layer 2) ==="
PROJECT_DIR="$TEST_DIR/test_project"
mkdir -p "$PROJECT_DIR/aitasks/metadata" "$PROJECT_DIR/.aitask-scripts"
cp "$REPO_DIR/seed/aitasks_agent_instructions.seed.md" "$PROJECT_DIR/aitasks/metadata/"
cp "$REPO_DIR/seed/opencode_instructions.seed.md" "$PROJECT_DIR/aitasks/metadata/"

# Extract functions from setup script
SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"
extract_fn() {
    local file="$1" fn="$2"
    awk "/^${fn}\(\)/,/^}/" "$file"
}
eval "$(extract_fn "$REPO_DIR/.aitask-scripts/aitask_setup.sh" "assemble_aitasks_instructions")"
eval "$(extract_fn "$REPO_DIR/.aitask-scripts/aitask_setup.sh" "insert_aitasks_instructions")"
warn() { echo "WARN: $*"; }

content="$(assemble_aitasks_instructions "$PROJECT_DIR" "opencode")" || true
assert_eq "Assembly produced content" "true" "$([ -n "$content" ] && echo true || echo false)"
assert_contains "Layer 1 present" "Task File Format" "$content"
assert_contains "Layer 2 opencode present" "Agent Identification" "$content"

echo ""
echo "=== Test 4: Marker insertion (new file) ==="
DEST_FILE="$TEST_DIR/test_instructions.md"
insert_aitasks_instructions "$DEST_FILE" "$content"
file_content="$(cat "$DEST_FILE")"
assert_contains "Start marker" ">>>aitasks" "$file_content"
assert_contains "End marker" "<<<aitasks" "$file_content"
assert_contains "Content present" "Task File Format" "$file_content"
marker_count=$(grep -c '>>>aitasks' "$DEST_FILE")
assert_eq "One start marker" "1" "$marker_count"

echo ""
echo "=== Test 5: Idempotency (re-insert same content) ==="
insert_aitasks_instructions "$DEST_FILE" "$content"
file_content2="$(cat "$DEST_FILE")"
assert_eq "Content unchanged" "$file_content" "$file_content2"
marker_count2=$(grep -c '>>>aitasks' "$DEST_FILE")
assert_eq "Still one start marker" "1" "$marker_count2"

echo ""
echo "=== Test 6: Existing user content preserved ==="
USER_FILE="$TEST_DIR/user_instructions.md"
cat > "$USER_FILE" <<'EOF'
# My Project

Custom instructions here.

## Custom Section
User content.
EOF

insert_aitasks_instructions "$USER_FILE" "$content"
uf="$(cat "$USER_FILE")"
assert_contains "User header preserved" "My Project" "$uf"
assert_contains "User section preserved" "Custom Section" "$uf"
assert_contains "Aitasks inserted" ">>>aitasks" "$uf"

# Update (idempotency with user content)
insert_aitasks_instructions "$USER_FILE" "UPDATED CONTENT"
uf2="$(cat "$USER_FILE")"
assert_contains "User content still preserved" "My Project" "$uf2"
assert_contains "Updated content" "UPDATED CONTENT" "$uf2"
assert_not_contains "Old aitasks content replaced" "Task File Format" "$uf2"
mc3=$(grep -c '>>>aitasks' "$USER_FILE")
assert_eq "Still one marker after update" "1" "$mc3"

echo ""
echo "=== Test 7: JSON deep merge ==="
if ! command -v python3 &>/dev/null; then
    echo "SKIP: python3 not available"
else
    SEED_JSON="$TEST_DIR/seed.json"
    DEST_JSON="$TEST_DIR/dest.json"

    cat > "$SEED_JSON" <<'EOF'
{"permission":{"bash":{"git add *":"allow","./ait git *":"allow"}},"newkey":"newvalue"}
EOF
    cat > "$DEST_JSON" <<'EOF'
{"permission":{"bash":{"custom *":"allow","git add *":"allow"}},"existing":"preserved"}
EOF

    python3 -c "
import json, sys
with open(sys.argv[1]) as f: existing = json.load(f)
with open(sys.argv[2]) as f: seed = json.load(f)
def deep_merge(base, overlay):
    result = dict(base)
    for key, value in overlay.items():
        if key not in result:
            result[key] = value
        elif isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        elif isinstance(result[key], list) and isinstance(value, list):
            existing_items = [str(item) for item in result[key]]
            for item in value:
                if str(item) not in existing_items:
                    result[key].append(item)
    return result
merged = deep_merge(existing, seed)
print(json.dumps(merged, indent=2))
" "$DEST_JSON" "$SEED_JSON" > "$TEST_DIR/merged.json"
    cp "$TEST_DIR/merged.json" "$DEST_JSON"

    merged="$(cat "$DEST_JSON")"
    assert_contains "Existing key preserved" '"existing": "preserved"' "$merged"
    assert_contains "New key added" '"newkey": "newvalue"' "$merged"
    assert_contains "Existing bash perm preserved" '"custom *": "allow"' "$merged"
    assert_contains "Seed bash perm merged" '"./ait git *": "allow"' "$merged"
    git_add_count=$(echo "$merged" | grep -c '"git add')
    assert_eq "No duplicate git add" "1" "$git_add_count"
fi

echo ""
echo "========================================="
echo "Results: $PASS passed, $FAIL failed"
echo "========================================="
[[ $FAIL -eq 0 ]]
