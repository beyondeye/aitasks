#!/usr/bin/env bash
set -euo pipefail

# Test OpenCode setup pipeline: packaging, staging, assembly, idempotency, JSON merge

PASS=0
FAIL=0
assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    if [[ "$expected" == "$actual" ]]; then
        echo "PASS: $desc"; PASS=$((PASS + 1))
    else
        echo "FAIL: $desc (expected: '$expected', got: '$actual')"; FAIL=$((FAIL + 1))
    fi
}
assert_contains() {
    local desc="$1" needle="$2" haystack="$3"
    if echo "$haystack" | grep -qF "$needle"; then
        echo "PASS: $desc"; PASS=$((PASS + 1))
    else
        echo "FAIL: $desc — '$needle' not found"; FAIL=$((FAIL + 1))
    fi
}
assert_not_contains() {
    local desc="$1" needle="$2" haystack="$3"
    if ! echo "$haystack" | grep -qF "$needle"; then
        echo "PASS: $desc"; PASS=$((PASS + 1))
    else
        echo "FAIL: $desc — '$needle' found but shouldn't be"; FAIL=$((FAIL + 1))
    fi
}

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEST_DIR="$(mktemp -d)"
trap 'rm -rf "$TEST_DIR"' EXIT

echo "=== Test 1: OpenCode skills packaging (release workflow sim) ==="
mkdir -p "$TEST_DIR/opencode_skills"
mkdir -p "$TEST_DIR/opencode_commands"
for skill_dir in "$REPO_DIR/.opencode/skills"/aitask-*/; do
    [ -d "$skill_dir" ] || continue
    cp -r "$skill_dir" "$TEST_DIR/opencode_skills/$(basename "$skill_dir")"
done
[ -f "$REPO_DIR/.opencode/skills/opencode_tool_mapping.md" ] && \
    cp "$REPO_DIR/.opencode/skills/opencode_tool_mapping.md" "$TEST_DIR/opencode_skills/"
[ -f "$REPO_DIR/.opencode/skills/opencode_planmode_prereqs.md" ] && \
    cp "$REPO_DIR/.opencode/skills/opencode_planmode_prereqs.md" "$TEST_DIR/opencode_skills/"
[ -d "$REPO_DIR/.opencode/commands" ] && \
    cp -r "$REPO_DIR/.opencode/commands/." "$TEST_DIR/opencode_commands/"

skill_count=$(find "$TEST_DIR/opencode_skills" -name "SKILL.md" -type f | wc -l | tr -d ' ')
command_count=$(find "$TEST_DIR/opencode_commands" -type f -name "*.md" | wc -l | tr -d ' ')
assert_eq "Packaged 18 skill wrappers" "18" "$skill_count"
assert_eq "Tool mapping packaged" "true" "$([ -f "$TEST_DIR/opencode_skills/opencode_tool_mapping.md" ] && echo true || echo false)"
assert_eq "Planmode prereqs packaged" "true" "$([ -f "$TEST_DIR/opencode_skills/opencode_planmode_prereqs.md" ] && echo true || echo false)"
assert_eq "Packaged 18 command wrappers" "18" "$command_count"

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
assert_eq "Staged 18 wrappers to metadata" "18" "$staged_count"
assert_eq "Tool mapping staged" "true" "$([ -f "$INSTALL_DIR/aitasks/metadata/opencode_skills/opencode_tool_mapping.md" ] && echo true || echo false)"
assert_eq "Planmode prereqs staged" "true" "$([ -f "$INSTALL_DIR/aitasks/metadata/opencode_skills/opencode_planmode_prereqs.md" ] && echo true || echo false)"
assert_eq "Staged 18 command wrappers" "18" "$staged_command_count"
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
