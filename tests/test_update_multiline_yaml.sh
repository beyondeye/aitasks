#!/usr/bin/env bash
# test_update_multiline_yaml.sh - Regression tests for multi-line YAML flow
# list parsing (t813).
#
# The board (task_yaml.py via PyYAML) serializes a list-valued frontmatter
# field as a flow sequence that wraps across multiple physical lines once it
# exceeds ~80 columns. The bash frontmatter parsers match line-by-line, so
# continuation lines (which start with whitespace) failed the key regex and
# were silently dropped — a subsequent --add-child/--remove-child then wrote
# back the truncated subset, permanently losing the continuation entries.
#
# These tests cover the three readers (aitask_update.sh parser, read_yaml_list,
# read_yaml_field), the shared join helper, and the board serializer.
#
# Run: bash tests/test_update_multiline_yaml.sh

set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"
UPDATE_SCRIPT="$PROJECT_DIR/.aitask-scripts/aitask_update.sh"

# shellcheck source=../.aitask-scripts/lib/task_utils.sh
source "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"
# shellcheck source=../.aitask-scripts/lib/agentcrew_utils.sh
source "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh"

PASS=0
FAIL=0
TOTAL=0

# Read a single-line frontmatter field value (bash-written output is never
# wrapped, so a plain grep is sufficient for reading the *result* files).
get_field() {
    local file="$1" field="$2"
    grep -m1 "^${field}:" "$file" | sed "s/^${field}:[[:space:]]*//"
}

# Count comma-separated entries after stripping brackets/spaces.
count_entries() {
    local csv
    csv=$(parse_yaml_list "$1")
    [[ -z "$csv" ]] && { echo 0; return; }
    echo "$csv" | tr ',' '\n' | grep -c .
}

TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_t813_XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/aitasks"

# --- Test 1: join_yaml_flow_lists helper -----------------------------------

single=$(printf '%s\n' 'priority: high' | join_yaml_flow_lists)
assert_eq "join: plain line is unchanged" "priority: high" "$single"

wrapped=$(printf '%s\n' \
    'children_to_implement: [t900_1, t900_2, t900_3,' \
    '  t900_4, t900_5,' \
    '  t900_6]' | join_yaml_flow_lists)
assert_eq "join: 3-line flow list collapses to one line" \
    "children_to_implement: [t900_1, t900_2, t900_3,   t900_4, t900_5,   t900_6]" \
    "$wrapped"

empty_list=$(printf '%s\n' 'depends: []' | join_yaml_flow_lists)
assert_eq "join: empty list untouched" "depends: []" "$empty_list"

scalar=$(printf '%s\n' 'issue: https://example.com/issues/7' | join_yaml_flow_lists)
assert_eq "join: scalar URL untouched" \
    "issue: https://example.com/issues/7" "$scalar"

# --- Helper: write a task file with a wrapped children_to_implement list ---
# Continuation lines start with whitespace, exactly as PyYAML emits them.
make_children_task() {
    local file="$1"
    cat > "$file" <<'EOF'
---
priority: high
effort: medium
depends: []
issue_type: feature
status: Ready
labels: []
children_to_implement: [t900_1, t900_2, t900_3, t900_4, t900_5, t900_6,
  t900_7, t900_8, t900_9, t900_10, t900_11, t900_12, t900_13, t900_14,
  t900_15, t900_16, t900_17, t900_18]
created_at: 2026-05-20 10:00
updated_at: 2026-05-20 10:00
---

Parent task body.
EOF
}

# --- Test 2: aitask_update.sh --remove-child on a wrapped list -------------

make_children_task "$TMP/aitasks/t900_test.md"
( cd "$TMP" && bash "$UPDATE_SCRIPT" --batch 900 --remove-child t900_1 >/dev/null 2>&1 )
children_after=$(get_field "$TMP/aitasks/t900_test.md" "children_to_implement")
assert_eq "remove-child: 17 of 18 children survive (no continuation loss)" \
    "17" "$(count_entries "$children_after")"
assert_not_contains "remove-child: removed child is gone" \
    "t900_1," "$(parse_yaml_list "$children_after"),"
assert_contains "remove-child: first continuation-line entry kept" \
    "t900_7" "$children_after"
assert_contains "remove-child: last continuation-line entry kept" \
    "t900_18" "$children_after"

# --- Test 3: aitask_update.sh --add-child on a wrapped list ----------------

make_children_task "$TMP/aitasks/t900_test.md"
( cd "$TMP" && bash "$UPDATE_SCRIPT" --batch 900 --add-child t900_99 >/dev/null 2>&1 )
children_added=$(get_field "$TMP/aitasks/t900_test.md" "children_to_implement")
assert_eq "add-child: 19 children total (18 kept + 1 added)" \
    "19" "$(count_entries "$children_added")"
assert_contains "add-child: new child present" "t900_99" "$children_added"
assert_contains "add-child: pre-existing continuation entry kept" \
    "t900_15" "$children_added"

# --- Test 4: a wrapped depends list survives an unrelated update ----------

cat > "$TMP/aitasks/t901_deps.md" <<'EOF'
---
priority: medium
effort: low
depends: [1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008, 1009, 1010,
  1011, 1012, 1013, 1014, 1015]
issue_type: feature
status: Ready
labels: []
created_at: 2026-05-20 10:00
updated_at: 2026-05-20 10:00
---

Body.
EOF
( cd "$TMP" && bash "$UPDATE_SCRIPT" --batch 901 --priority low >/dev/null 2>&1 )
deps_after=$(get_field "$TMP/aitasks/t901_deps.md" "depends")
assert_eq "depends: all 15 wrapped dependencies survive" \
    "15" "$(count_entries "$deps_after")"
assert_contains "depends: continuation-line dependency kept" "1015" "$deps_after"

# --- Test 5: read_yaml_list on wrapped / inline / block lists --------------

cat > "$TMP/wrapped_list.md" <<'EOF'
---
children_to_implement: [t900_1, t900_2, t900_3, t900_4, t900_5, t900_6,
  t900_7, t900_8, t900_9, t900_10]
status: Ready
---
EOF
rl_wrapped=$(read_yaml_list "$TMP/wrapped_list.md" "children_to_implement" | grep -c .)
assert_eq "read_yaml_list: wrapped inline list yields all 10 entries" \
    "10" "$rl_wrapped"
rl_last=$(read_yaml_list "$TMP/wrapped_list.md" "children_to_implement" | tail -1)
assert_eq "read_yaml_list: continuation entry parsed" "t900_10" "$rl_last"

cat > "$TMP/inline_list.md" <<'EOF'
---
depends: [1, 2, 3]
status: Ready
---
EOF
rl_inline=$(read_yaml_list "$TMP/inline_list.md" "depends" | grep -c .)
assert_eq "read_yaml_list: non-wrapped inline list still works" "3" "$rl_inline"

cat > "$TMP/block_list.md" <<'EOF'
---
labels:
  - ui
  - backend
status: Ready
---
EOF
rl_block=$(read_yaml_list "$TMP/block_list.md" "labels" | grep -c .)
assert_eq "read_yaml_list: block-style list still works" "2" "$rl_block"

# --- Test 6: read_yaml_field on a wrapped flow list ------------------------

cat > "$TMP/verifies.md" <<'EOF'
---
issue_type: manual_verification
verifies: [t900_1, t900_2, t900_3, t900_4, t900_5, t900_6, t900_7, t900_8,
  t900_9, t900_10]
status: Ready
---
EOF
rf_value=$(read_yaml_field "$TMP/verifies.md" "verifies")
assert_eq "read_yaml_field: wrapped verifies value count" \
    "10" "$(count_entries "$rf_value")"
assert_contains "read_yaml_field: continuation entry present" \
    "t900_10" "$rf_value"

# --- Test 7: board (task_yaml.py) serializes long lists on one line --------

if python3 -c 'import yaml' >/dev/null 2>&1; then
    board_out=$(python3 - "$PROJECT_DIR" <<'PYEOF'
import sys
sys.path.insert(0, sys.argv[1] + "/.aitask-scripts/board")
import task_yaml
ids = [f"t1_{i}" for i in range(1, 40)]
out = task_yaml.serialize_frontmatter(
    {"children_to_implement": ids}, "body\n", ["children_to_implement"])
wrapped = any(ln.startswith(" ") for ln in out.splitlines())
print("WRAPPED" if wrapped else "OK")
PYEOF
)
    assert_eq "board: long flow list stays on a single physical line" \
        "OK" "$board_out"
else
    echo "SKIP: board serializer test (python3/yaml unavailable)"
fi

# --- Syntax checks for the touched libraries -------------------------------

for f in lib/task_utils.sh lib/agentcrew_utils.sh aitask_update.sh; do
    TOTAL=$((TOTAL + 1))
    if bash -n "$PROJECT_DIR/.aitask-scripts/$f"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: syntax check $f"
    fi
done

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
