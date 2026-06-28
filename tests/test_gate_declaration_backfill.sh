#!/usr/bin/env bash
# test_gate_declaration_backfill.sh - Tests the Step-7 gate-declaration backfill
# primitive (t635_14): a picked task with NO `gates:` field adopts the active
# profile's `default_gates`, while an explicit `gates: []` opt-out and an
# already-declaring task are left untouched, and a profile with no `default_gates`
# is a no-op.
#
# Exercises the exact helper sequence the task-workflow Step-7 backfill runs:
#   has-gates-field (presence oracle) -> effective-gates --profile -> update --gates
# The presence oracle (not `list`) is what protects an explicit `gates: []`.
#
# Run: bash tests/test_gate_declaration_backfill.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

# --- fixture helpers -------------------------------------------------------

new_fixture() {
    local tmp
    tmp="$(mktemp -d "${TMPDIR:-/tmp}/test_gatebackfill_XXXXXX")"
    CLEANUP_DIRS+=("$tmp")
    mkdir -p "$tmp/aitasks/metadata/profiles" "$tmp/aiplans"
    printf 'name: fast\ndefault_gates: [risk_evaluated]\n' \
        > "$tmp/aitasks/metadata/profiles/fast.yaml"
    printf 'name: default\n' > "$tmp/aitasks/metadata/profiles/default.yaml"
    echo "$tmp"
}

# write_task <dir> <id> <gates-literal | __absent__>
write_task() {
    local dir="$1" id="$2" gates="$3"
    local path="$dir/aitasks/t${id}_x.md"
    {
        echo "---"
        echo "status: Implementing"
        [[ "$gates" != "__absent__" ]] && echo "gates: ${gates}"
        echo "---"
        echo "Body."
    } > "$path"
}

# backfill <dir> <id> <profile_file_rel_or_empty> : run the EXACT Step-7 sequence.
# cwd is the fixture (so TASK_DIR=aitasks resolves the task file there); the
# scripts are invoked by absolute path (the fixture is not the real repo root).
backfill() {
    local dir="$1" id="$2" prof="$3"
    local gate="$PROJECT_DIR/.aitask-scripts/aitask_gate.sh"
    local update="$PROJECT_DIR/.aitask-scripts/aitask_update.sh"
    ( cd "$dir" && TASK_DIR=aitasks bash -c '
        set -e
        gate="$1"; update="$2"; id="$3"; prof="$4"
        if ! "$gate" has-gates-field "$id" >/dev/null 2>&1; then
            if [ -n "$prof" ]; then
                eff="$("$gate" effective-gates "$id" --profile "$prof" | paste -sd, -)"
            else
                eff="$("$gate" effective-gates "$id" | paste -sd, -)"
            fi
            if [ -n "$eff" ]; then
                "$update" --batch "$id" --gates "$eff" >/dev/null
            fi
        fi
    ' _ "$gate" "$update" "$id" "$prof" )
}

# gates_line <dir> <id> : the rendered `gates:` frontmatter line (or empty)
gates_line() {
    local dir="$1" id="$2"
    grep -E '^gates:' "$dir/aitasks/t${id}_x.md" 2>/dev/null || true
}

# --- tests -----------------------------------------------------------------

test_backfill_absent() {
    local d; d="$(new_fixture)"
    write_task "$d" 1 "__absent__"
    backfill "$d" 1 "aitasks/metadata/profiles/fast.yaml"
    assert_contains "absent field -> backfilled from profile default_gates" \
        "risk_evaluated" "$(gates_line "$d" 1)"
}

test_optout_preserved() {
    local d; d="$(new_fixture)"
    write_task "$d" 2 "[]"
    backfill "$d" 2 "aitasks/metadata/profiles/fast.yaml"
    # has-gates-field exits 0 for `gates: []`, so the backfill must NOT run.
    assert_not_contains "explicit gates:[] opt-out NOT overwritten" \
        "risk_evaluated" "$(gates_line "$d" 2)"
}

test_already_declaring_unchanged() {
    local d; d="$(new_fixture)"
    write_task "$d" 3 "[build_verified]"
    backfill "$d" 3 "aitasks/metadata/profiles/fast.yaml"
    local line; line="$(gates_line "$d" 3)"
    assert_contains "already-declaring task keeps its gates" "build_verified" "$line"
    assert_not_contains "already-declaring task not overwritten with profile default" \
        "risk_evaluated" "$line"
}

test_no_default_gates_noop() {
    local d; d="$(new_fixture)"
    write_task "$d" 4 "__absent__"
    backfill "$d" 4 "aitasks/metadata/profiles/default.yaml"
    assert_eq "profile with no default_gates -> field stays absent" \
        "" "$(gates_line "$d" 4)"
}

# --- Run ---
test_backfill_absent
test_optout_preserved
test_already_declaring_unchanged
test_no_default_gates_noop

for dir in "${CLEANUP_DIRS[@]}"; do rm -rf "$dir"; done

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -gt 0 ]] && exit 1
echo "All tests PASSED"
