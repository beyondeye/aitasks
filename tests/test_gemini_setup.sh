#!/usr/bin/env bash
set -euo pipefail

# Test Gemini CLI setup pipeline: packaging, staging, assembly, idempotency

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

# Derive expected activate_skill count from the seed policy file (source of
# truth) so the tests stay self-maintaining as the policy is extended.
expected_activate_skill_count=$(grep -c '^toolName = "activate_skill"$' "$REPO_DIR/seed/geminicli_policies/aitasks-whitelist.toml" | tr -d ' ')

echo "=== Test 1: Gemini CLI packaging (release workflow sim) ==="
mkdir -p "$TEST_DIR/gemini_skills"
mkdir -p "$TEST_DIR/gemini_commands"
mkdir -p "$TEST_DIR/gemini_policies"
# Gemini skills dir now contains only helper docs (skill wrappers are unified in .agents/skills/)
for doc in geminicli_tool_mapping.md geminicli_planmode_prereqs.md; do
    [ -f "$REPO_DIR/.gemini/skills/$doc" ] && \
        cp "$REPO_DIR/.gemini/skills/$doc" "$TEST_DIR/gemini_skills/"
done
[ -d "$REPO_DIR/.gemini/commands" ] && \
    cp -r "$REPO_DIR/.gemini/commands/." "$TEST_DIR/gemini_commands/"
[ -d "$REPO_DIR/.gemini/policies" ] && \
    cp -r "$REPO_DIR/.gemini/policies/." "$TEST_DIR/gemini_policies/"
[ -f "$REPO_DIR/.gemini/settings.json" ] && \
    cp "$REPO_DIR/.gemini/settings.json" "$TEST_DIR/gemini_settings.json"

expected_command_count=$(find "$REPO_DIR/.gemini/commands" -type f -name "*.toml" | wc -l | tr -d ' ')

# No skill wrappers should be in gemini_skills (consolidated to .agents/skills/)
skill_count=$(find "$TEST_DIR/gemini_skills" -name "SKILL.md" -type f | wc -l | tr -d ' ')
command_count=$(find "$TEST_DIR/gemini_commands" -type f -name "*.toml" | wc -l | tr -d ' ')
policy_count=$(find "$TEST_DIR/gemini_policies" -type f -name "*.toml" | wc -l | tr -d ' ')
assert_eq "No skill wrappers in gemini_skills" "0" "$skill_count"
assert_eq "Tool mapping packaged" "true" "$([ -f "$TEST_DIR/gemini_skills/geminicli_tool_mapping.md" ] && echo true || echo false)"
assert_eq "Planmode prereqs packaged" "true" "$([ -f "$TEST_DIR/gemini_skills/geminicli_planmode_prereqs.md" ] && echo true || echo false)"
assert_eq "Packaged command wrappers (toml)" "$expected_command_count" "$command_count"
assert_eq "Packaged policy file" "1" "$policy_count"
assert_eq "Packaged settings.json" "true" "$([ -f "$TEST_DIR/gemini_settings.json" ] && echo true || echo false)"

echo ""
echo "=== Test 2: Gemini CLI staging (install.sh sim) ==="
INSTALL_DIR="$TEST_DIR/install_sim"
mkdir -p "$INSTALL_DIR/aitasks/metadata"
cp -r "$TEST_DIR/gemini_skills" "$INSTALL_DIR/gemini_skills"
cp -r "$TEST_DIR/gemini_commands" "$INSTALL_DIR/gemini_commands"
cp -r "$TEST_DIR/gemini_policies" "$INSTALL_DIR/gemini_policies"
[ -f "$TEST_DIR/gemini_settings.json" ] && \
    cp "$TEST_DIR/gemini_settings.json" "$INSTALL_DIR/gemini_settings.json"

# Inline staging logic (mirrors install_gemini_staging — helper docs only)
mkdir -p "$INSTALL_DIR/aitasks/metadata/geminicli_skills"
for doc in geminicli_tool_mapping.md geminicli_planmode_prereqs.md; do
    [ -f "$INSTALL_DIR/gemini_skills/$doc" ] && \
        cp "$INSTALL_DIR/gemini_skills/$doc" "$INSTALL_DIR/aitasks/metadata/geminicli_skills/"
done
rm -rf "$INSTALL_DIR/gemini_skills"

mkdir -p "$INSTALL_DIR/aitasks/metadata/geminicli_commands"
cp -r "$INSTALL_DIR/gemini_commands/." "$INSTALL_DIR/aitasks/metadata/geminicli_commands/"
rm -rf "$INSTALL_DIR/gemini_commands"

# Stage policies and settings
mkdir -p "$INSTALL_DIR/aitasks/metadata/geminicli_policies"
cp -r "$INSTALL_DIR/gemini_policies/." "$INSTALL_DIR/aitasks/metadata/geminicli_policies/"
rm -rf "$INSTALL_DIR/gemini_policies"

if [ -f "$INSTALL_DIR/gemini_settings.json" ]; then
    cp "$INSTALL_DIR/gemini_settings.json" "$INSTALL_DIR/aitasks/metadata/geminicli_settings.seed.json"
    rm -f "$INSTALL_DIR/gemini_settings.json"
fi

# No skill wrappers staged (consolidated in codex_skills)
staged_skill_count=$(find "$INSTALL_DIR/aitasks/metadata/geminicli_skills" -name "SKILL.md" -type f | wc -l | tr -d ' ')
staged_command_count=$(find "$INSTALL_DIR/aitasks/metadata/geminicli_commands" -type f -name "*.toml" | wc -l | tr -d ' ')
staged_policy_count=$(find "$INSTALL_DIR/aitasks/metadata/geminicli_policies" -type f -name "*.toml" | wc -l | tr -d ' ')
assert_eq "No skill wrappers staged" "0" "$staged_skill_count"
assert_eq "Tool mapping staged" "true" "$([ -f "$INSTALL_DIR/aitasks/metadata/geminicli_skills/geminicli_tool_mapping.md" ] && echo true || echo false)"
assert_eq "Planmode prereqs staged" "true" "$([ -f "$INSTALL_DIR/aitasks/metadata/geminicli_skills/geminicli_planmode_prereqs.md" ] && echo true || echo false)"
assert_eq "Staged command wrappers (toml)" "$expected_command_count" "$staged_command_count"
assert_eq "Staged policy file" "1" "$staged_policy_count"
assert_eq "Staged settings seed" "true" "$([ -f "$INSTALL_DIR/aitasks/metadata/geminicli_settings.seed.json" ] && echo true || echo false)"
assert_eq "Skills source cleaned up" "false" "$([ -d "$INSTALL_DIR/gemini_skills" ] && echo true || echo false)"
assert_eq "Commands source cleaned up" "false" "$([ -d "$INSTALL_DIR/gemini_commands" ] && echo true || echo false)"
assert_eq "Policies source cleaned up" "false" "$([ -d "$INSTALL_DIR/gemini_policies" ] && echo true || echo false)"
assert_eq "Settings source cleaned up" "false" "$([ -f "$INSTALL_DIR/gemini_settings.json" ] && echo true || echo false)"

echo ""
echo "=== Test 3: Instruction assembly (Layer 1 + Layer 2) ==="
PROJECT_DIR="$TEST_DIR/test_project"
mkdir -p "$PROJECT_DIR/aitasks/metadata" "$PROJECT_DIR/.aitask-scripts"
cp "$REPO_DIR/seed/aitasks_agent_instructions.seed.md" "$PROJECT_DIR/aitasks/metadata/"
cp "$REPO_DIR/seed/geminicli_instructions.seed.md" "$PROJECT_DIR/aitasks/metadata/"

# Extract functions from setup script
SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"
extract_fn() {
    local file="$1" fn="$2"
    awk "/^${fn}\(\)/,/^}/" "$file"
}
eval "$(extract_fn "$REPO_DIR/.aitask-scripts/aitask_setup.sh" "assemble_aitasks_instructions")"
eval "$(extract_fn "$REPO_DIR/.aitask-scripts/aitask_setup.sh" "insert_aitasks_instructions")"
warn() { echo "WARN: $*"; }
info() { echo "info: $*"; }
success() { echo "ok: $*"; }

content="$(assemble_aitasks_instructions "$PROJECT_DIR" "geminicli")" || true
assert_eq "Assembly produced content" "true" "$([ -n "$content" ] && echo true || echo false)"
assert_contains "Layer 1 present" "Task File Format" "$content"
assert_contains "Layer 2 geminicli present" "Agent Identification" "$content"

echo ""
echo "=== Test 4: Marker insertion (new file) ==="
DEST_FILE="$TEST_DIR/test_gemini.md"
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
USER_FILE="$TEST_DIR/user_gemini.md"
cat > "$USER_FILE" <<'EOF'
# My Project

Custom Gemini instructions here.

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
echo "=== Test 7: Policy merge (deduplicate rules) ==="
eval "$(extract_fn "$REPO_DIR/.aitask-scripts/aitask_setup.sh" "merge_gemini_policies")"
VENV_DIR="/nonexistent"  # force fallback to system python3

MERGE_DIR="$TEST_DIR/merge_test"
mkdir -p "$MERGE_DIR"
cat > "$MERGE_DIR/existing.toml" <<'TOML'
[[rule]]
toolName = "run_shell_command"
commandPrefix = "ls"
decision = "allow"
priority = 100

[[rule]]
toolName = "run_shell_command"
commandPrefix = "git add"
decision = "allow"
priority = 100

[[rule]]
toolName = "run_shell_command"
commandPrefix = "custom_cmd"
decision = "allow"
priority = 100
TOML

cat > "$MERGE_DIR/seed.toml" <<'TOML'
[[rule]]
toolName = "run_shell_command"
commandPrefix = "ls"
decision = "allow"
priority = 100

[[rule]]
toolName = "run_shell_command"
commandPrefix = "git add"
decision = "allow"
priority = 100

[[rule]]
toolName = "run_shell_command"
commandPrefix = "cat"
decision = "allow"
priority = 100
TOML

merge_gemini_policies "$MERGE_DIR/seed.toml" "$MERGE_DIR/existing.toml"
merged_content="$(cat "$MERGE_DIR/existing.toml")"
merged_rule_count=$(grep -c '^\[\[rule\]\]' "$MERGE_DIR/existing.toml")
assert_eq "Merged to 4 rules (3 existing + 1 new)" "4" "$merged_rule_count"
assert_contains "Kept custom_cmd" "custom_cmd" "$merged_content"
assert_contains "Added cat from seed" "cat" "$merged_content"

echo ""
echo "=== Test 8: Global Gemini policy install helper ==="
eval "$(extract_fn "$REPO_DIR/.aitask-scripts/aitask_setup.sh" "install_gemini_global_policy")"

GLOBAL_HOME="$TEST_DIR/global_home"
mkdir -p "$GLOBAL_HOME"
HOME="$GLOBAL_HOME"

install_gemini_global_policy "$REPO_DIR/seed/geminicli_policies/aitasks-whitelist.toml"
global_policy_file="$HOME/.gemini/policies/aitasks-whitelist.toml"
assert_eq "Created global policy file" "true" "$([ -f "$global_policy_file" ] && echo true || echo false)"
global_policy_content="$(cat "$global_policy_file")"
assert_contains "Global policy contains aitask rules" "./.aitask-scripts/aitask_pick_own.sh" "$global_policy_content"

cat > "$global_policy_file" <<'TOML'
[[rule]]
toolName = "run_shell_command"
commandPrefix = "custom_global_rule"
decision = "allow"
priority = 100
TOML

install_gemini_global_policy "$REPO_DIR/seed/geminicli_policies/aitasks-whitelist.toml"
merged_global_content="$(cat "$global_policy_file")"
merged_global_rule_count=$(grep -c '^\[\[rule\]\]' "$global_policy_file")
seed_rule_count=$(grep -c '^\[\[rule\]\]' "$REPO_DIR/seed/geminicli_policies/aitasks-whitelist.toml")
expected_global_rule_count=$((seed_rule_count + 1))
assert_contains "Global merge keeps custom rule" "custom_global_rule" "$merged_global_content"
assert_contains "Global merge adds aitask rules" "./.aitask-scripts/aitask_pick_own.sh" "$merged_global_content"
assert_contains "Global policy includes stderr redirection" "2>/dev/null" "$merged_global_content"
assert_not_contains "Global policy avoids unsupported inline regex flags" "(?i)aitask-review" "$merged_global_content"
global_activate_skill_count=$(printf '%s' "$merged_global_content" | grep -c '^toolName = "activate_skill"$' | tr -d ' ')
assert_eq "Global policy has explicit aitask skill entries" "$expected_activate_skill_count" "$global_activate_skill_count"
assert_contains "Global policy includes aitask-pick skill" "argsPattern = \"aitask-pick\"" "$merged_global_content"
assert_contains "Global policy includes aitask-review skill" "argsPattern = \"aitask-review\"" "$merged_global_content"
assert_not_contains "Global policy avoids broad aitask skill regex" "[Aa][Ii][Tt][Aa][Ss][Kk]-[A-Za-z0-9_-]+" "$merged_global_content"
assert_eq "Global merge adds seed rules without duplicates" "$expected_global_rule_count" "$merged_global_rule_count"

echo ""
echo "=== Test 9: Settings merge (policyPaths union) ==="
eval "$(extract_fn "$REPO_DIR/.aitask-scripts/aitask_setup.sh" "merge_gemini_settings")"

cat > "$MERGE_DIR/existing_settings.json" <<'JSON'
{
  "general": {
    "defaultApprovalMode": "default"
  },
  "policyPaths": [
    ".gemini/custom_policies/"
  ]
}
JSON

cat > "$MERGE_DIR/seed_settings.json" <<'JSON'
{
  "general": {
    "defaultApprovalMode": "default"
  },
  "policyPaths": [
    ".gemini/policies/"
  ]
}
JSON

merge_gemini_settings "$MERGE_DIR/seed_settings.json" "$MERGE_DIR/existing_settings.json"
settings_content="$(cat "$MERGE_DIR/existing_settings.json")"
assert_contains "Kept custom policies path" "custom_policies" "$settings_content"
assert_contains "Added aitask policies path" ".gemini/policies/" "$settings_content"

echo ""
echo "=== Test 10: Seed files exist ==="
assert_eq "Seed policies dir exists" "true" "$([ -d "$REPO_DIR/seed/geminicli_policies" ] && echo true || echo false)"
assert_eq "Seed policy file exists" "true" "$([ -f "$REPO_DIR/seed/geminicli_policies/aitasks-whitelist.toml" ] && echo true || echo false)"
assert_eq "Seed settings file exists" "true" "$([ -f "$REPO_DIR/seed/geminicli_settings.seed.json" ] && echo true || echo false)"
assert_contains "Seed policy includes stderr redirection" "2>/dev/null" "$(cat "$REPO_DIR/seed/geminicli_policies/aitasks-whitelist.toml")"
assert_not_contains "Seed policy avoids unsupported inline regex flags" "(?i)aitask-review" "$(cat "$REPO_DIR/seed/geminicli_policies/aitasks-whitelist.toml")"
seed_policy_content="$(cat "$REPO_DIR/seed/geminicli_policies/aitasks-whitelist.toml")"
seed_activate_skill_count=$(printf '%s' "$seed_policy_content" | grep -c '^toolName = "activate_skill"$' | tr -d ' ')
assert_eq "Seed policy has explicit aitask skill entries" "$expected_activate_skill_count" "$seed_activate_skill_count"
assert_contains "Seed policy includes aitask-pick skill" "argsPattern = \"aitask-pick\"" "$seed_policy_content"
assert_contains "Seed policy includes aitask-review skill" "argsPattern = \"aitask-review\"" "$seed_policy_content"
assert_not_contains "Seed policy avoids broad aitask skill regex" "[Aa][Ii][Tt][Aa][Ss][Kk]-[A-Za-z0-9_-]+" "$seed_policy_content"

echo ""
echo "========================================="
echo "Results: $PASS passed, $FAIL failed"
echo "========================================="
[[ $FAIL -eq 0 ]]
