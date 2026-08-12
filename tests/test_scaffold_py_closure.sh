#!/usr/bin/env bash
# test_scaffold_py_closure.sh - Unit tests for copy_py_closure_from (t1488).
#
# The helper lives in tests/lib/test_scaffold.sh and derives the transitive
# lib/ import closure of the Python modules a scaffolded test drives, replacing
# a hand-maintained copy list that had silently drifted.
#
# Why a dedicated file: the only production caller (test_boardcol_update.sh)
# walks board_columns.py, a plain TREE — and `sort -u` collapses its three
# repeated `atomic_write` import lines before recursion, so even the
# repeated-import path never reaches the dedup guard. The diamond, cycle,
# reset and error branches are therefore unreachable from real usage and are
# driven here against synthetic module trees.
#
# THE DEDUP CLAIM CANNOT BE MADE BY INSPECTING THE DESTINATION. Two `cp`s of
# the same file are byte-identical to one, so "copied once" is invisible there.
# Every dedup assertion below instead compares AIT_PY_CLOSURE_COPIED (bumped
# after each `cp`) against AIT_PY_CLOSURE_MODULES (appended at the seen-marking).
# The two are bumped at different points and agree only while the guard holds.
#
# Run: bash tests/test_scaffold_py_closure.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

SRC=""
DST=""

# Fresh, empty synthetic source/destination lib dirs.
new_lib() {
    local d
    d="$(mktemp -d)"
    CLEANUP_DIRS+=("$d")
    SRC="$d/src"
    DST="$d/dst"
    mkdir -p "$SRC" "$DST"
}

# mkmod <name> <line>... — write a synthetic module.
mkmod() {
    local name="$1" line
    shift
    : > "$SRC/$name.py"
    for line in "$@"; do printf '%s\n' "$line" >> "$SRC/$name.py"; done
}

# Sorted, comma-joined closure membership: an order-independent set compare
# (the walk order depends on import order, the membership does not).
closure_set() {
    # shellcheck disable=SC2086  # splitting the space-delimited list is the point
    printf '%s\n' $AIT_PY_CLOSURE_MODULES | sort | tr '\n' ','
}

test_linear_chain() {
    echo "=== Test: linear chain a -> b -> c ==="
    new_lib
    mkmod a "from b import thing"
    mkmod b "import c"
    mkmod c "value = 1"

    local rc=0
    copy_py_closure_from "$SRC" "$DST" a || rc=$?
    assert_exit_zero_rc "chain exits zero" "$rc"
    assert_eq "chain closure membership" "a,b,c," "$(closure_set)"
    assert_eq "chain copy count" "3" "$AIT_PY_CLOSURE_COPIED"
    assert_file_exists "transitive c.py copied" "$DST/c.py"
}

# The case destination inspection cannot decide: `d` is reached twice.
test_diamond_copies_shared_dep_once() {
    echo "=== Test: diamond a -> {b,c} -> d copies d once ==="
    new_lib
    mkmod a "from b import x" "from c import y"
    mkmod b "from d import z"
    mkmod c "from d import w"
    mkmod d "value = 1"

    local rc=0
    copy_py_closure_from "$SRC" "$DST" a || rc=$?
    assert_exit_zero_rc "diamond exits zero" "$rc"
    assert_eq "diamond closure membership" "a,b,c,d," "$(closure_set)"
    # A seen-check that no longer suppresses the second visit to `d` yields 5
    # here while the closure still lists 4 modules — the only observable
    # difference between one `cp` and two.
    assert_eq "diamond copies d exactly once" "4" "$AIT_PY_CLOSURE_COPIED"
}

test_import_cycle_terminates() {
    echo "=== Test: import cycle a <-> b terminates ==="
    new_lib
    mkmod a "from b import x"
    mkmod b "from a import y"

    local rc=0
    copy_py_closure_from "$SRC" "$DST" a || rc=$?
    assert_exit_zero_rc "cycle exits zero" "$rc"
    assert_eq "cycle closure membership" "a,b," "$(closure_set)"
    assert_eq "cycle copy count" "2" "$AIT_PY_CLOSURE_COPIED"
}

test_dedup_spans_multiple_roots() {
    echo "=== Test: two roots sharing a dep, one call ==="
    new_lib
    mkmod a "from shared import x"
    mkmod b "from shared import y"
    mkmod shared "value = 1"

    local rc=0
    copy_py_closure_from "$SRC" "$DST" a b || rc=$?
    assert_exit_zero_rc "multi-root exits zero" "$rc"
    assert_eq "multi-root closure membership" "a,b,shared," "$(closure_set)"
    assert_eq "shared dep copied once across roots" "3" "$AIT_PY_CLOSURE_COPIED"
}

test_outputs_reset_between_calls() {
    echo "=== Test: outputs reset per call, not accumulated ==="
    new_lib
    mkmod a "from shared import x"
    mkmod b "from shared import y"
    mkmod shared "value = 1"

    local rc=0
    copy_py_closure_from "$SRC" "$DST" a || rc=$?
    assert_exit_zero_rc "first call exits zero" "$rc"
    assert_eq "first call copy count" "2" "$AIT_PY_CLOSURE_COPIED"

    rc=0
    copy_py_closure_from "$SRC" "$DST" b || rc=$?
    assert_exit_zero_rc "second call exits zero" "$rc"
    # Without the per-call reset the seen-set would still hold `shared` and the
    # counters would read 4 / a,b,shared — the second call would also silently
    # skip re-copying into a fresh destination.
    assert_eq "second call closure membership" "b,shared," "$(closure_set)"
    assert_eq "second call copy count" "2" "$AIT_PY_CLOSURE_COPIED"
}

# Docstring prose has the same shape as an import line. atomic_write.py really
# does contain "from the same old text, and the second replace …".
test_docstring_prose_is_not_a_module() {
    echo "=== Test: docstring prose does not fabricate a module ==="
    new_lib
    mkmod a '"""Header.' \
            '' \
            'Writes render from the same old text, and the second replace wins.' \
            'Callers import this from within a function.' \
            '"""' \
            'value = 1'

    local rc=0
    copy_py_closure_from "$SRC" "$DST" a || rc=$?
    assert_exit_zero_rc "prose exits zero" "$rc"
    assert_eq "prose closure membership" "a," "$(closure_set)"
    assert_file_not_exists "no the.py fabricated" "$DST/the.py"
}

test_stdlib_and_third_party_skipped() {
    echo "=== Test: stdlib / third-party imports are skipped ==="
    new_lib
    mkmod a "import os" "import json" "import yaml" "from pathlib import Path" "value = 1"

    local rc=0
    copy_py_closure_from "$SRC" "$DST" a || rc=$?
    assert_exit_zero_rc "stdlib exits zero" "$rc"
    assert_eq "stdlib closure membership" "a," "$(closure_set)"
    assert_file_not_exists "os.py not fabricated" "$DST/os.py"
}

test_comma_and_alias_import_forms() {
    echo "=== Test: 'import x, y' and 'import z as zz' forms ==="
    new_lib
    mkmod a "import x, y" "import z as zz"
    mkmod x "value = 1"
    mkmod y "value = 1"
    mkmod z "value = 1"

    local rc=0
    copy_py_closure_from "$SRC" "$DST" a || rc=$?
    assert_exit_zero_rc "comma/alias exits zero" "$rc"
    assert_eq "comma/alias closure membership" "a,x,y,z," "$(closure_set)"
}

# Over-copying a lazily-imported module is harmless; missing one is not — so
# indented imports are scanned too.
test_function_local_import_is_followed() {
    echo "=== Test: function-local (indented) import is followed ==="
    new_lib
    mkmod a "def f():" "    from lazydep import thing" "    return thing"
    mkmod lazydep "value = 1"

    local rc=0
    copy_py_closure_from "$SRC" "$DST" a || rc=$?
    assert_exit_zero_rc "function-local exits zero" "$rc"
    assert_eq "function-local closure membership" "a,lazydep," "$(closure_set)"
}

test_missing_root_fails_loudly() {
    echo "=== Test: a missing root module fails loudly ==="
    new_lib

    local rc=0 err
    err="$(copy_py_closure_from "$SRC" "$DST" nosuch 2>&1)" || rc=$?
    assert_exit_nonzero_rc "missing root exits non-zero" "$rc"
    assert_contains "message names the missing module" "nosuch.py" "$err"
}

# A dep with no matching .py is indistinguishable from a stdlib name — that is
# the existence filter working, not an error.
test_unresolvable_dep_is_skipped() {
    echo "=== Test: an unresolvable dep is skipped, not an error ==="
    new_lib
    mkmod a "from ghost import x" "value = 1"

    local rc=0
    copy_py_closure_from "$SRC" "$DST" a || rc=$?
    assert_exit_zero_rc "unresolvable dep exits zero" "$rc"
    assert_eq "unresolvable dep closure membership" "a," "$(closure_set)"
}

# Proves the convergence fail-safe is reachable and correctly named, so a
# regressed dedup guard ends with this message instead of hanging.
test_convergence_failsafe_fires() {
    echo "=== Test: the convergence fail-safe is reachable and named ==="
    new_lib
    mkmod m1 "from m2 import x"
    mkmod m2 "from m3 import x"
    mkmod m3 "value = 1"

    local rc=0 err saved="$_AIT_PY_CLOSURE_MAX_VISITS"
    _AIT_PY_CLOSURE_MAX_VISITS=2
    err="$(copy_py_closure_from "$SRC" "$DST" m1 2>&1)" || rc=$?
    _AIT_PY_CLOSURE_MAX_VISITS="$saved"

    assert_exit_nonzero_rc "visit ceiling exits non-zero" "$rc"
    assert_contains "fail-safe message is named" "not converging" "$err"
}

# The real graph the production caller walks, as an end-to-end sanity check on
# the same helper: board_columns.py must pull in record_protocol.py, the module
# whose absence from the old hand-maintained list is what t1488 fixes.
test_real_board_columns_closure() {
    echo "=== Test: the real board_columns closure includes record_protocol ==="
    local d rc=0
    d="$(mktemp -d)"
    CLEANUP_DIRS+=("$d")

    copy_py_closure_from "$PROJECT_DIR/.aitask-scripts/lib" "$d" board_columns || rc=$?
    assert_exit_zero_rc "real closure exits zero" "$rc"
    assert_file_exists "record_protocol.py in the closure" "$d/record_protocol.py"
    assert_file_exists "atomic_write.py in the closure" "$d/atomic_write.py"
    assert_file_exists "task_yaml.py in the closure" "$d/task_yaml.py"
}

test_linear_chain
test_diamond_copies_shared_dep_once
test_import_cycle_terminates
test_dedup_spans_multiple_roots
test_outputs_reset_between_calls
test_docstring_prose_is_not_a_module
test_stdlib_and_third_party_skipped
test_comma_and_alias_import_forms
test_function_local_import_is_followed
test_missing_root_fails_loudly
test_unresolvable_dep_is_skipped
test_convergence_failsafe_fires
test_real_board_columns_closure

for d in "${CLEANUP_DIRS[@]}"; do rm -rf "$d"; done

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
