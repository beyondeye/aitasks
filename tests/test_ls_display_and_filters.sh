#!/usr/bin/env bash
# test_ls_display_and_filters.sh - Cover aitask_ls.sh's verbose display line and
# ALL of its metadata filters: -l/--labels, --type, --followup-kind and
# --no-followup-kind (t1468_4).
#
# This is the first coverage the `-v` display line and the `-l` filter have ever
# had, so the fixture pins the whole bracket (field order included), not just a
# substring, and every positive filter is asserted by HIT COUNT — a silent
# zero-match otherwise reads as a clean pass.
#
# Strategy: build a real fixture repo under mktemp -d and run the REAL
# $PROJECT_DIR/.aitask-scripts/aitask_ls.sh against it. No scaffold copy is
# needed: SCRIPT_DIR resolves back to the real lib/, so the followup-kind bridge
# is found. Test bodies stay in the main shell, so the in-process PASS/FAIL
# counters are correct without the file-backed opt-in.
#
# Run: bash tests/test_ls_display_and_filters.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LS="$PROJECT_DIR/.aitask-scripts/aitask_ls.sh"
CREATE="$PROJECT_DIR/.aitask-scripts/aitask_create.sh"

PASS=0
FAIL=0
TOTAL=0

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"

# --- Setup --------------------------------------------------------------

TMPROOT=$(mktemp -d)
trap 'rm -rf "$TMPROOT"' EXIT

REPO="$TMPROOT/repo"
mkdir -p "$REPO/aitasks/metadata" "$REPO/aitasks/t13"
touch "$REPO/aitasks/metadata/project_config.yaml"
# --type validates against this vocabulary; without it the empty-file fallback
# (bug/feature/refactor) would reject the fixture's chore/test/enhancement tasks.
printf '%s\n' bug chore documentation enhancement feature manual_verification \
    performance refactor style test \
    > "$REPO/aitasks/metadata/task_types.txt"

# Fixture tasks.
#   t10  bug,         labels [ui],          no kind
#   t11  feature,     labels [backend],     followup_kind risk_mitigation
#   t12  test,        labels [ui, backend], followup_kind qa_test_gap
#   t13  feature parent with children_to_implement
#   t13_1 enhancement, followup_kind upstream_defect
#   t13_2 chore,       no kind
cat > "$REPO/aitasks/t10_plain_bug.md" <<'EOF'
---
priority: high
effort: low
status: Ready
issue_type: bug
labels: [ui]
---
plain bug
EOF

cat > "$REPO/aitasks/t11_mitigation.md" <<'EOF'
---
priority: medium
effort: medium
status: Ready
issue_type: feature
labels: [backend]
followup_kind: risk_mitigation
---
risk mitigation follow-up
EOF

cat > "$REPO/aitasks/t12_qa_gap.md" <<'EOF'
---
priority: low
effort: high
status: Ready
issue_type: test
labels: [ui, backend]
followup_kind: qa_test_gap
---
qa test gap follow-up
EOF

cat > "$REPO/aitasks/t13_parent.md" <<'EOF'
---
priority: medium
effort: medium
status: Ready
issue_type: feature
children_to_implement: [t13_1, t13_2]
---
parent
EOF

cat > "$REPO/aitasks/t13/t13_1_upstream.md" <<'EOF'
---
priority: high
effort: low
status: Ready
issue_type: enhancement
followup_kind: upstream_defect
---
upstream defect follow-up
EOF

cat > "$REPO/aitasks/t13/t13_2_chore.md" <<'EOF'
---
priority: low
effort: low
status: Ready
issue_type: chore
---
plain chore child
EOF

# Run aitask_ls.sh from the fixture repo. Prints stdout+stderr.
run_ls() {
    ( cd "$REPO" && "$LS" "$@" 2>&1 ) || true
}

# Run aitask_ls.sh and publish its output and exit code as LS_OUT / LS_RC.
# Deliberately NOT a stdout-returning function: calling it inside a command
# substitution would run it in a subshell, where the exit-code assignment dies
# and every rejection test would silently see rc=0.
LS_OUT=""
LS_RC=0
run_ls_rc() {
    set +e
    LS_OUT=$( cd "$REPO" && "$LS" "$@" 2>&1 )
    LS_RC=$?
    set -e
}

# Line for a given task filename stem out of a listing.
line_for() {
    printf '%s\n' "$2" | grep -F "$1" || true
}

# Count non-empty lines.
count_lines() {
    printf '%s' "$1" | grep -c . || true
}

# --- Test 1: Display line -----------------------------------------------

all_v=$(run_ls -v --all-levels 99)

t11_line=$(line_for "t11_mitigation.md" "$all_v")
assert_contains "t11 -v shows the issue type" "Type: feature" "$t11_line"
assert_contains "t11 -v shows the follow-up kind" \
    "Follow-up: risk_mitigation" "$t11_line"

t10_line=$(line_for "t10_plain_bug.md" "$all_v")
assert_contains "t10 -v shows its true issue type" "Type: bug" "$t10_line"
assert_not_contains "t10 (not a follow-up) shows no Follow-up field" \
    "Follow-up" "$t10_line"

# Pin the WHOLE bracket for one task of each shape so field order is fixed,
# not merely the presence of substrings.
assert_eq "t11 full display line (field order pinned)" \
    "t11_mitigation.md [Status: Ready, Priority: Medium, Effort: Medium, Type: feature, Follow-up: risk_mitigation]" \
    "$t11_line"
assert_eq "t10 full display line (no Follow-up segment)" \
    "t10_plain_bug.md [Status: Ready, Priority: High, Effort: Low, Type: bug]" \
    "$t10_line"

# --- Test 2: Positive filters, asserted by hit count ---------------------

out=$(run_ls -v --followup-kind risk_mitigation 99)
assert_eq_trim "--followup-kind risk_mitigation returns exactly 1 task" \
    "1" "$(count_lines "$out")"
assert_contains "--followup-kind risk_mitigation returns t11" \
    "t11_mitigation.md" "$out"

out=$(run_ls -v --type bug 99)
assert_eq_trim "--type bug returns exactly 1 task" "1" "$(count_lines "$out")"
assert_contains "--type bug returns t10" "t10_plain_bug.md" "$out"

# --- Test 3: --no-followup-kind (genuine new work) ----------------------

out=$(run_ls -v --no-followup-kind 99)
assert_eq_trim "--no-followup-kind returns exactly 2 parent tasks" \
    "2" "$(count_lines "$out")"
assert_contains "--no-followup-kind includes t10" "t10_plain_bug.md" "$out"
assert_contains "--no-followup-kind includes t13" "t13_parent.md" "$out"
assert_not_contains "--no-followup-kind excludes t11" "t11_mitigation.md" "$out"
assert_not_contains "--no-followup-kind excludes t12" "t12_qa_gap.md" "$out"

# --- Test 4: Every listing mode -----------------------------------------

for mode_args in "--children 13" "--tree" "--all-levels"; do
    # shellcheck disable=SC2086
    out=$(run_ls -v $mode_args --followup-kind upstream_defect 99)
    assert_eq_trim "--followup-kind upstream_defect in '$mode_args' returns exactly 1" \
        "1" "$(count_lines "$out")"
    assert_contains "--followup-kind upstream_defect in '$mode_args' returns t13_1" \
        "t13_1_upstream.md" "$out"

    # shellcheck disable=SC2086
    out=$(run_ls -v $mode_args --type chore 99)
    assert_eq_trim "--type chore in '$mode_args' returns exactly 1" \
        "1" "$(count_lines "$out")"
    assert_contains "--type chore in '$mode_args' returns t13_2" \
        "t13_2_chore.md" "$out"
done

# Default (parents-only) mode sees neither child.
out=$(run_ls -v --followup-kind upstream_defect 99)
assert_eq_trim "--followup-kind upstream_defect in parents-only mode returns 0" \
    "0" "$(count_lines "$out")"
out=$(run_ls -v --type chore 99)
assert_eq_trim "--type chore in parents-only mode returns 0" \
    "0" "$(count_lines "$out")"

# --- Test 5: Composition -------------------------------------------------

out=$(run_ls -v --type feature --followup-kind risk_mitigation 99)
assert_eq_trim "--type feature + --followup-kind risk_mitigation returns exactly 1" \
    "1" "$(count_lines "$out")"
assert_contains "--type feature + --followup-kind risk_mitigation returns t11" \
    "t11_mitigation.md" "$out"

out=$(run_ls -v --type test --followup-kind risk_mitigation 99)
assert_eq_trim "--type test + --followup-kind risk_mitigation returns 0" \
    "0" "$(count_lines "$out")"

out=$(run_ls -v -l ui --type bug 99)
assert_eq_trim "-l ui + --type bug returns exactly 1" "1" "$(count_lines "$out")"
assert_contains "-l ui + --type bug returns t10" "t10_plain_bug.md" "$out"

# First-ever coverage of the -l filter on its own.
out=$(run_ls -v -l ui 99)
assert_eq_trim "-l ui returns exactly 2 tasks" "2" "$(count_lines "$out")"
assert_contains "-l ui includes t10" "t10_plain_bug.md" "$out"
assert_contains "-l ui includes t12" "t12_qa_gap.md" "$out"
assert_not_contains "-l ui excludes t11 (backend only)" "t11_mitigation.md" "$out"

# --- Test 6: Rejection ---------------------------------------------------

run_ls_rc -v --followup-kind bogus 99
assert_exit_nonzero_rc "--followup-kind bogus exits non-zero" "$LS_RC"
assert_contains "--followup-kind bogus names the valid kinds" \
    "risk_mitigation" "$LS_OUT"
assert_contains "--followup-kind bogus reports an invalid VALUE" \
    "Invalid follow-up kind: bogus" "$LS_OUT"

run_ls_rc -v --type bogus 99
assert_exit_nonzero_rc "--type bogus exits non-zero" "$LS_RC"
assert_contains "--type bogus names the valid types" "feature" "$LS_OUT"
assert_contains "--type bogus reports an invalid VALUE" \
    "Invalid type: bogus" "$LS_OUT"

run_ls_rc -v --followup-kind risk_mitigation --no-followup-kind 99
assert_exit_nonzero_rc "--followup-kind + --no-followup-kind is rejected" "$LS_RC"
assert_contains "mutual-exclusion message names both flags" \
    "--no-followup-kind" "$LS_OUT"

run_ls_rc -v --nope 99
assert_exit_nonzero_rc "an unknown long flag still hard-fails" "$LS_RC"
assert_contains "unknown long flag keeps the pre-existing message" \
    "Unknown argument" "$LS_OUT"

# --- Test 7: Fail-closed vocabulary, with a positive control -------------

EMPTY_KINDS_DIR="$TMPROOT/empty_kinds"
mkdir -p "$EMPTY_KINDS_DIR"

set +e
out=$( cd "$REPO" && AIT_FOLLOWUP_KINDS_DIR="$EMPTY_KINDS_DIR" \
    "$LS" -v --followup-kind risk_mitigation 99 2>&1 )
rc=$?
set -e
assert_exit_nonzero_rc "unresolvable vocabulary → --followup-kind exits non-zero" "$rc"
assert_contains "unresolvable vocabulary reports 'cannot resolve', not 'invalid'" \
    "cannot resolve" "$out"
assert_not_contains "unresolvable vocabulary does NOT claim an invalid value" \
    "Invalid follow-up kind" "$out"

# Positive control: with the same broken vocabulary but no kind flag, plain -v
# still works and still DISPLAYS the kind — the bridge is lazy and is never
# consulted for display.
set +e
out=$( cd "$REPO" && AIT_FOLLOWUP_KINDS_DIR="$EMPTY_KINDS_DIR" \
    "$LS" -v --all-levels 99 2>&1 )
rc=$?
set -e
assert_exit_zero_rc "unresolvable vocabulary does not break plain -v" "$rc"
assert_contains "plain -v still displays the kind with a broken vocabulary" \
    "Follow-up: risk_mitigation" "$out"

# --- Test 8: --type validation through the real entry point --------------
# Pins the behaviour of aitask_create.sh's task-type validation across the
# get_valid_task_types → read_valid_task_types delegation. Driven through the
# real CLI, not the helper.

CREATE_REPO="$TMPROOT/create_repo"
mkdir -p "$CREATE_REPO/aitasks/metadata"
touch "$CREATE_REPO/aitasks/metadata/project_config.yaml"
printf '%s\n' bug feature refactor enhancement chore test documentation \
    performance style manual_verification \
    > "$CREATE_REPO/aitasks/metadata/task_types.txt"

create_in() {
    local repo="$1"; shift
    ( cd "$repo" && "$CREATE" --batch --desc "fixture" "$@" 2>&1 )
}

set +e
out=$(create_in "$CREATE_REPO" --name "bogus type task" --type bogus)
rc=$?
set -e
assert_exit_nonzero_rc "create --type bogus exits non-zero" "$rc"
assert_contains "create --type bogus reports Invalid type" "Invalid type:" "$out"

set +e
out=$(create_in "$CREATE_REPO" --name "mv task" --type manual_verification)
rc=$?
set -e
assert_exit_zero_rc "create --type manual_verification succeeds" "$rc"

# Empty task_types.txt → the bug/feature/refactor fallback, and nothing else.
EMPTY_TYPES_REPO="$TMPROOT/empty_types_repo"
mkdir -p "$EMPTY_TYPES_REPO/aitasks/metadata"
touch "$EMPTY_TYPES_REPO/aitasks/metadata/project_config.yaml"
: > "$EMPTY_TYPES_REPO/aitasks/metadata/task_types.txt"

for t in bug feature refactor; do
    set +e
    out=$(create_in "$EMPTY_TYPES_REPO" --name "fallback $t" --type "$t")
    rc=$?
    set -e
    assert_exit_zero_rc "empty task_types.txt still accepts '$t'" "$rc"
done

set +e
out=$(create_in "$EMPTY_TYPES_REPO" --name "fallback chore" --type chore)
rc=$?
set -e
assert_exit_nonzero_rc "empty task_types.txt rejects 'chore' (outside fallback)" "$rc"
assert_contains "empty task_types.txt fallback names only bug/feature/refactor" \
    "bug,feature,refactor" "$out"

# --- Summary ------------------------------------------------------------

echo
echo "===================="
echo "Passed: $PASS / $TOTAL"
[[ "$FAIL" -gt 0 ]] && echo "Failed: $FAIL"
echo "===================="
[[ "$FAIL" -eq 0 ]]
