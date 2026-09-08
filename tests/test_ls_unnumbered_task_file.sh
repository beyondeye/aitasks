#!/usr/bin/env bash
# test_ls_unnumbered_task_file.sh - Cover aitask_ls.sh's guard against task files
# whose filename carries no task number (t1721).
#
# A file like `aitasks/t_some_name.md` matches the parent glob `t*_*.md`, so
# before the guard it listed like any other task — but no consumer can derive an
# id from it, and an empty id passed onward asks about a task that cannot exist.
# The guard drops the row from stdout and warns on stderr; a SILENT skip would
# hide a Ready task instead of surfacing the data defect, so both halves are
# asserted, in every view mode.
#
# Strategy: build a real fixture repo under mktemp -d and run the REAL
# $PROJECT_DIR/.aitask-scripts/aitask_ls.sh against it, exactly as
# tests/test_ls_display_and_filters.sh does. No scaffold copy is needed:
# SCRIPT_DIR resolves back to the real lib/. Test bodies stay in the main shell,
# so the in-process PASS/FAIL counters are correct without the file-backed
# opt-in.
#
# Run: bash tests/test_ls_unnumbered_task_file.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LS="$PROJECT_DIR/.aitask-scripts/aitask_ls.sh"

PASS=0
FAIL=0
TOTAL=0

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"

# --- Setup --------------------------------------------------------------

TMPROOT=$(mktemp -d)
trap 'rm -rf "$TMPROOT"' EXIT

# Two fixture repos: one carrying the defect, one clean. The clean one is the
# negative control — without it, a guard that warned unconditionally would pass
# every stderr assertion below.
REPO="$TMPROOT/repo"
CLEAN="$TMPROOT/clean"

write_task() {   # $1 = path, $2 = body line
    mkdir -p "$(dirname "$1")"
    cat > "$1" <<EOF
---
priority: medium
effort: low
status: Ready
issue_type: chore
---
$2
EOF
}

for root in "$REPO" "$CLEAN"; do
    mkdir -p "$root/aitasks/metadata"
    touch "$root/aitasks/metadata/project_config.yaml"
    printf '%s\n' bug chore documentation enhancement feature manual_verification \
        performance refactor style test \
        > "$root/aitasks/metadata/task_types.txt"
done

# Defective fixture: one well-formed parent + child, one unnumbered parent, one
# unnumbered child. `t_no_number_here.md` matches the parent glob `t*_*.md`, and
# `t10_x_not_a_number.md` matches the child glob `t*_*_*.md` — both are reachable
# without the guard, which is what makes them worth asserting.
write_task "$REPO/aitasks/t10_numbered.md"            "well-formed parent"
write_task "$REPO/aitasks/t10/t10_1_child.md"         "well-formed child"
write_task "$REPO/aitasks/t_no_number_here.md"        "parent with no id"
write_task "$REPO/aitasks/t10/t10_x_not_a_number.md"  "child with no id"

# Outside the discovery glob entirely: `t*_*.md` requires an underscore, so
# `tbroken.md` is never visited and therefore never warned about. That limit is
# deliberate — widening ls's glob to hunt for files it does not otherwise list
# would be runtime work for a case tests/test_task_filename_invariant.sh already
# catches by scanning the data. Present here so the shape is exercised rather
# than merely described.
write_task "$REPO/aitasks/tbroken.md"                 "no underscore at all"

# Clean fixture: the same shape, every filename conforming.
write_task "$CLEAN/aitasks/t10_numbered.md"           "well-formed parent"
write_task "$CLEAN/aitasks/t10/t10_1_child.md"        "well-formed child"

# Run aitask_ls.sh from a fixture repo, capturing stdout and stderr SEPARATELY —
# the whole contract is "absent from stdout, named on stderr", which a merged
# 2>&1 capture cannot tell apart.
OUT=""
ERR=""
run_ls() {   # $1 = repo root, rest = ls args
    local root="$1"; shift
    local errfile="$TMPROOT/stderr.$$"
    set +e
    OUT=$( cd "$root" && "$LS" "$@" 2>"$errfile" )
    set -e
    ERR=$(cat "$errfile")
    rm -f "$errfile"
}

# Count non-empty lines.
count_lines() {
    printf '%s' "$1" | grep -c . || true
}

echo "=== test_ls_unnumbered_task_file.sh ==="
echo

# --- Test 1: default (parents-only) mode --------------------------------

echo "--- Test 1: default mode ---"
run_ls "$REPO" 99

# Positive hit count first: a fixture that listed NOTHING would satisfy every
# "does not contain" assertion below and read as a clean pass.
assert_eq_trim "default mode lists exactly 1 parent (the numbered one)" \
    "1" "$(count_lines "$OUT")"
assert_contains "default mode lists the numbered parent" \
    "t10_numbered.md" "$OUT"
assert_not_contains "default mode drops the unnumbered parent" \
    "t_no_number_here.md" "$OUT"
assert_contains "default mode warns about the unnumbered parent" \
    "task file without a task number" "$ERR"
assert_contains "the warning names the offending path" \
    "t_no_number_here.md" "$ERR"
# A name with no underscore is outside the `t*_*.md` discovery glob, so it is
# absent from stdout for a different reason than the guard: nothing visits it.
# This assertion pins "never appears as a listing row", which is what callers
# depend on — it deliberately does NOT pin the reason. Widening ls's glob would
# route the same file through the guard and still keep it off stdout, so this
# stays green either way; the boundary itself is covered by
# tests/test_task_filename_invariant.sh, whose scan sees the file that ls cannot.
assert_not_contains "a name outside the discovery glob is not listed either" \
    "tbroken.md" "$OUT"

# --- Test 2: --all-levels (children reachable) --------------------------

echo "--- Test 2: --all-levels ---"
run_ls "$REPO" --all-levels 99

assert_eq_trim "--all-levels lists exactly 2 rows (numbered parent + child)" \
    "2" "$(count_lines "$OUT")"
assert_contains "--all-levels lists the numbered child" \
    "t10_1_child.md" "$OUT"
assert_not_contains "--all-levels drops the unnumbered child" \
    "t10_x_not_a_number.md" "$OUT"
assert_not_contains "--all-levels drops the unnumbered parent" \
    "t_no_number_here.md" "$OUT"
# The child branch of the guard's pattern is only reachable here: the
# parents-only mode never visits a child file.
assert_contains "--all-levels warns about the unnumbered child" \
    "t10_x_not_a_number.md" "$ERR"

# --- Test 3: --tree -----------------------------------------------------

# Tree mode is NOT redundant with default mode: its loop derives task_num from
# the filename itself (grep -oE '^t[0-9]+') BEFORE calling process_task_file, so
# an unnumbered parent yields an empty task_num and a "$TASK_DIR/t" child lookup.
# The shared guard suppresses the row today, but nothing else pins that, and a
# future change to the tree path could reintroduce the malformed row unseen by
# the other two modes.
echo "--- Test 3: --tree ---"
run_ls "$REPO" --tree 99

assert_eq_trim "--tree lists exactly 2 rows (numbered parent + indented child)" \
    "2" "$(count_lines "$OUT")"
assert_contains "--tree lists the numbered parent" "t10_numbered.md" "$OUT"
assert_contains "--tree still indents the numbered child under its parent" \
    "└─ t10_1_child.md" "$OUT"
assert_not_contains "--tree drops the unnumbered parent" \
    "t_no_number_here.md" "$OUT"
assert_not_contains "--tree drops the unnumbered child" \
    "t10_x_not_a_number.md" "$OUT"
assert_contains "--tree warns about the unnumbered parent" \
    "t_no_number_here.md" "$ERR"

# --- Test 4: --children -------------------------------------------------

echo "--- Test 4: --children ---"
run_ls "$REPO" --children 10 99

assert_eq_trim "--children lists exactly 1 child" "1" "$(count_lines "$OUT")"
assert_contains "--children lists the numbered child" "t10_1_child.md" "$OUT"
assert_not_contains "--children drops the unnumbered child" \
    "t10_x_not_a_number.md" "$OUT"
# Absence from stdout is only half the contract. Assert the warning here too:
# every mode routes through the same shared function today, but a mode-specific
# early return or an output redirection in this direct child-listing path could
# suppress the warning while the absence assertion above still passed — turning
# a reported data defect back into a silent one.
assert_contains "--children warns about the unnumbered child" \
    "t10_x_not_a_number.md" "$ERR"

# --- Test 5: negative control — a clean repo warns about nothing ---------

# Without this, a guard that warned on EVERY file would pass every stderr
# assertion above.
echo "--- Test 5: negative control (clean repo) ---"
for mode in "" "--all-levels" "--tree"; do
    label="${mode:-default}"
    # shellcheck disable=SC2086  # deliberate word-splitting of the mode flag
    run_ls "$CLEAN" $mode 99
    assert_not_contains "clean repo emits no unnumbered warning in $label mode" \
        "task file without a task number" "$ERR"
    assert_contains "clean repo still lists its numbered parent in $label mode" \
        "t10_numbered.md" "$OUT"
done

# --- Summary ------------------------------------------------------------

echo
echo "===================="
echo "Passed: $PASS / $TOTAL"
[[ "$FAIL" -gt 0 ]] && echo "Failed: $FAIL"
echo "===================="
[[ "$FAIL" -eq 0 ]]
