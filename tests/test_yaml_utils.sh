#!/usr/bin/env bash
# test_yaml_utils.sh - Tests for the shared YAML reader lib (t815).
#
# read_yaml_field was once defined independently in BOTH task_utils.sh and
# agentcrew_utils.sh; whichever lib was sourced last silently won. t815
# extracted the canonical readers (join_yaml_flow_lists, read_yaml_field,
# read_yaml_list) into lib/yaml_utils.sh, sourced by both libs behind a
# double-source guard.
#
# These tests cover the canonical read_yaml_field on both file shapes it must
# support — markdown frontmatter files and plain YAML files with no
# frontmatter (crew *_status.yaml) — read_yaml_list, and a regression guard
# against a second copy of read_yaml_field being re-introduced.
#
# Run: bash tests/test_yaml_utils.sh

set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"
LIB_DIR="$PROJECT_DIR/.aitask-scripts/lib"

# Source both libs, in the same order aitask_archive.sh does. Both source
# yaml_utils.sh; the double-source guard must make the second a no-op.
# shellcheck source=../.aitask-scripts/lib/task_utils.sh
source "$LIB_DIR/task_utils.sh"
# shellcheck source=../.aitask-scripts/lib/agentcrew_utils.sh
source "$LIB_DIR/agentcrew_utils.sh"

PASS=0
FAIL=0
TOTAL=0

# Count comma-separated entries after stripping brackets/spaces.
count_entries() {
    local csv
    csv=$(parse_yaml_list "$1")
    [[ -z "$csv" ]] && { echo 0; return; }
    echo "$csv" | tr ',' '\n' | grep -c .
}

TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_t815_XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

# --- Test 1: read_yaml_field on a markdown frontmatter file ----------------

cat > "$TMP/task.md" <<'EOF'
---
priority: high
issue_type: bug
status: Ready
labels: [ui, backend]
---

## Body

status: this-body-line-must-not-match
EOF

assert_eq "read_yaml_field: scalar frontmatter field" \
    "high" "$(read_yaml_field "$TMP/task.md" "priority")"
assert_eq "read_yaml_field: issue_type field" \
    "bug" "$(read_yaml_field "$TMP/task.md" "issue_type")"
assert_eq "read_yaml_field: missing field yields empty string" \
    "" "$(read_yaml_field "$TMP/task.md" "no_such_field")"

# Frontmatter restriction: a body line that looks like a field must NOT win.
assert_eq "read_yaml_field: body line is not matched (frontmatter wins)" \
    "Ready" "$(read_yaml_field "$TMP/task.md" "status")"

# --- Test 2: read_yaml_field on a wrapped multi-line flow list -------------

cat > "$TMP/verifies.md" <<'EOF'
---
issue_type: manual_verification
verifies: [t900_1, t900_2, t900_3, t900_4, t900_5, t900_6, t900_7, t900_8,
  t900_9, t900_10]
status: Ready
---
EOF
rf_value=$(read_yaml_field "$TMP/verifies.md" "verifies")
assert_eq "read_yaml_field: wrapped flow list returns all 10 entries" \
    "10" "$(count_entries "$rf_value")"
assert_contains "read_yaml_field: continuation-line entry present" \
    "t900_10" "$rf_value"

# --- Test 3: read_yaml_field on a plain YAML file (no frontmatter) ----------
# Crew *_status.yaml files are plain YAML with no `---` delimiters. The
# canonical reader must scan the whole file for these — the behaviour the
# agentcrew_utils.sh copy used to provide.

cat > "$TMP/crew_status.yaml" <<'EOF'
status: Running
progress: 42
agent_name: planner
started_at: '2026-03-24 09:38:55'
EOF

assert_eq "read_yaml_field: plain YAML (no frontmatter) scalar field" \
    "Running" "$(read_yaml_field "$TMP/crew_status.yaml" "status")"
assert_eq "read_yaml_field: plain YAML numeric field" \
    "42" "$(read_yaml_field "$TMP/crew_status.yaml" "progress")"
assert_eq "read_yaml_field: plain YAML agent_name field" \
    "planner" "$(read_yaml_field "$TMP/crew_status.yaml" "agent_name")"
assert_eq "read_yaml_field: plain YAML missing field yields empty string" \
    "" "$(read_yaml_field "$TMP/crew_status.yaml" "no_such_field")"

# --- Test 4: read_yaml_list on inline / wrapped / block lists --------------

cat > "$TMP/inline_list.md" <<'EOF'
---
depends: [1, 2, 3]
status: Ready
---
EOF
assert_eq "read_yaml_list: inline list yields 3 entries" \
    "3" "$(read_yaml_list "$TMP/inline_list.md" "depends" | grep -c .)"

cat > "$TMP/wrapped_list.md" <<'EOF'
---
children_to_implement: [t900_1, t900_2, t900_3, t900_4, t900_5, t900_6,
  t900_7, t900_8, t900_9, t900_10]
status: Ready
---
EOF
assert_eq "read_yaml_list: wrapped inline list yields all 10 entries" \
    "10" "$(read_yaml_list "$TMP/wrapped_list.md" "children_to_implement" | grep -c .)"
assert_eq "read_yaml_list: wrapped continuation entry parsed" \
    "t900_10" "$(read_yaml_list "$TMP/wrapped_list.md" "children_to_implement" | tail -1)"

cat > "$TMP/block_list.md" <<'EOF'
---
labels:
  - ui
  - backend
status: Ready
---
EOF
assert_eq "read_yaml_list: block-style list yields 2 entries" \
    "2" "$(read_yaml_list "$TMP/block_list.md" "labels" | grep -c .)"

# --- Test 5: join_yaml_flow_lists is reachable via both libs ---------------

joined=$(printf '%s\n' \
    'children_to_implement: [t1, t2,' \
    '  t3]' | join_yaml_flow_lists)
assert_eq "join_yaml_flow_lists: wrapped list collapses to one line" \
    "children_to_implement: [t1, t2,   t3]" "$joined"

# --- Test 6: collision regression guard ------------------------------------
# read_yaml_field must be defined exactly once, in yaml_utils.sh — never again
# in task_utils.sh or agentcrew_utils.sh (the t815 footgun).

count_def() { grep -cE "^${2}\(\)" "$1" || true; }

assert_eq "no read_yaml_field definition in task_utils.sh" \
    "0" "$(count_def "$LIB_DIR/task_utils.sh" read_yaml_field)"
assert_eq "no read_yaml_field definition in agentcrew_utils.sh" \
    "0" "$(count_def "$LIB_DIR/agentcrew_utils.sh" read_yaml_field)"
assert_eq "read_yaml_field defined exactly once in yaml_utils.sh" \
    "1" "$(count_def "$LIB_DIR/yaml_utils.sh" read_yaml_field)"
assert_eq "no read_yaml_list definition in agentcrew_utils.sh" \
    "0" "$(count_def "$LIB_DIR/agentcrew_utils.sh" read_yaml_list)"
assert_eq "read_yaml_list defined exactly once in yaml_utils.sh" \
    "1" "$(count_def "$LIB_DIR/yaml_utils.sh" read_yaml_list)"
assert_eq "no join_yaml_flow_lists definition in task_utils.sh" \
    "0" "$(count_def "$LIB_DIR/task_utils.sh" join_yaml_flow_lists)"
assert_eq "join_yaml_flow_lists defined exactly once in yaml_utils.sh" \
    "1" "$(count_def "$LIB_DIR/yaml_utils.sh" join_yaml_flow_lists)"

# --- Test 7: double-source guard -------------------------------------------

assert_eq "yaml_utils.sh double-source guard variable is set" \
    "1" "${_AIT_YAML_UTILS_LOADED:-unset}"
# Re-sourcing must short-circuit (return 0) without redefining.
source "$LIB_DIR/yaml_utils.sh"
assert_eq "re-sourcing yaml_utils.sh is a no-op (exit 0)" "0" "$?"

# --- read_yaml_mappings: artifacts: block (t1076_2) ------------------------
# The mapping reader serves both attachments: (t1030 §3) and artifacts:
# (unified artifact design §4). handle/kind must be emitted, handle/kind
# FIRST, records blank-line separated, quoted names round-tripped, and
# field-scoping must hold when both blocks coexist on one task.

cat > "$TMP/artifacts.md" <<'EOF'
---
priority: low
artifacts:
  - handle: art:t774-htmlplan
    kind: html_plan
    name: "Login flow mockups"
  - handle: art:t774-report
    kind: report
attachments:
  - hash: sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08
    name: shot.png
---
EOF

art_out="$(read_yaml_mappings "$TMP/artifacts.md" artifacts)"
expected_art="$(printf 'handle=art:t774-htmlplan\nkind=html_plan\nname=Login flow mockups\n\nhandle=art:t774-report\nkind=report')"
assert_eq "artifacts records emit handle/kind/name in schema order, blank-line separated" \
    "$expected_art" "$art_out"

attach_out="$(read_yaml_mappings "$TMP/artifacts.md" attachments)"
expected_attach="$(printf 'hash=sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08\nname=shot.png')"
assert_eq "field-scoping: reading attachments from a mixed task yields only attachment records" \
    "$expected_attach" "$attach_out"

art_scoped="$(read_yaml_mappings "$TMP/artifacts.md" artifacts | grep -c '^hash=' || true)"
assert_eq "field-scoping: artifacts records carry no attachment keys" "0" "$art_scoped"

# --- Syntax checks for the touched libraries -------------------------------

for f in lib/yaml_utils.sh lib/task_utils.sh lib/agentcrew_utils.sh aitask_archive.sh; do
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
