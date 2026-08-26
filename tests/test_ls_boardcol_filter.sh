#!/usr/bin/env bash
# test_ls_boardcol_filter.sh - `ait ls --boardcol` (t1630).
#
# Covers the filter's two load-bearing decisions and the seam-reuse claim
# underneath them:
#
#   D2  `--boardcol unordered` selects the Unsorted / Inbox LANE, which is TWO
#       on-disk states -- no `boardcol:` field at all, and an explicit
#       `boardcol: unordered` (which is what `ait board` and
#       `ait update --boardcol unordered` actually write). Matching only the
#       first would split one board lane in half.
#   D3  an unknown column id is REFUSED, naming the configured ids. The
#       alternative -- zero rows -- is indistinguishable from "that column is
#       empty", which is exactly what a typo or a renamed column produces.
#
# The seam claim is asserted against INDEPENDENT GROUND TRUTH: every hit is
# cross-checked with `aitask_board_column.sh current-column`, the board's own
# answer, rather than against a hand-written expectation. The YAML-typing case
# (`boardcol: no` under a column literally named `no`) is the one a bash-local
# re-read of the field gets wrong, and it is reachable in production --
# `generate_col_id("No")` really does mint that id.
#
# SCAFFOLDED rather than run against the real tree, and that is load-bearing
# for the laziness guard: aitask_ls.sh reaches the seam through the ABSOLUTE
# "$SCRIPT_DIR/aitask_board_column.sh", so only replacing that exact path can
# observe the call. A PATH shim would never fire. See
# test_hot_path_stays_lazy.
#
# Every invocation CAPTURES output instead of discarding it, and exit codes go
# through assert_exit_zero_rc_out, so a scaffold missing a Python module lands
# in a named FAIL with its error text rather than aborting the file silently
# under `set -e` (t1488). test_scaffold_column_probe_works is the guard for
# that class.
#
# Run: bash tests/test_ls_boardcol_filter.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=lib/proc_fixtures.sh
# run_bounded: portable `timeout`. `timeout` is GNU coreutils and macOS --
# a supported platform -- ships it only as `gtimeout` via Homebrew, so a
# bare `timeout` would exit 127 there and this suite would never reach the
# guard it means to test.
. "$PROJECT_DIR/tests/lib/proc_fixtures.sh"

# Test bodies run as plain functions in the main shell, so the in-process
# PASS/FAIL counters are correct without the file-backed opt-in.

count_lines() {
    # Empty input must count as 0, not 1 -- `printf '%s\n' ""` would yield one
    # blank line and make every "returns exactly N" assertion off by one on the
    # empty case, which is precisely the case a broken filter produces.
    [[ -z "$1" ]] && { echo 0; return; }
    printf '%s\n' "$1" | wc -l
}

# --- Fixture -----------------------------------------------------------------

# board_config.json variants. Fixture A keeps the stock ids; fixture B RENAMES
# them wholesale, which is the case that catches anything hardcoding
# DEFAULT_ORDER. Fixture C additionally configures a column literally named
# `no`, to reach the YAML-typing case.
write_columns() {
    case "$1" in
        stock)
            cat > aitasks/metadata/board_config.json <<'JSON'
{
  "columns": [
    {"id": "now", "title": "Now", "color": "#FF5555"},
    {"id": "next", "title": "Next", "color": "#50FA7B"},
    {"id": "backlog", "title": "Backlog", "color": "#BD93F9"}
  ],
  "column_order": ["now", "next", "backlog"]
}
JSON
            ;;
        renamed)
            cat > aitasks/metadata/board_config.json <<'JSON'
{
  "columns": [
    {"id": "triage", "title": "Triage", "color": "#FF5555"},
    {"id": "doing", "title": "Doing", "color": "#50FA7B"},
    {"id": "parked", "title": "Parked", "color": "#BD93F9"}
  ],
  "column_order": ["triage", "doing", "parked"]
}
JSON
            ;;
        yamltyped)
            # `no` is a real id generate_col_id() emits for the title "No", and
            # PyYAML 1.1 parses the scalar `no` as the boolean False.
            cat > aitasks/metadata/board_config.json <<'JSON'
{
  "columns": [
    {"id": "no", "title": "No", "color": "#FF5555"},
    {"id": "yes", "title": "Yes", "color": "#50FA7B"}
  ],
  "column_order": ["no", "yes"]
}
JSON
            ;;
    esac
}

seed_task() {
    local path="$1"; shift
    mkdir -p "$(dirname "$path")"
    {
        printf '%s\n' "---"
        printf '%s\n' "priority: medium"
        printf '%s\n' "effort: low"
        printf '%s\n' "status: Ready"
        for extra in "$@"; do printf '%s\n' "$extra"; done
        printf '%s\n' "created_at: 2026-01-01 10:00"
        printf '%s\n' "updated_at: 2026-01-01 10:00"
        printf '%s\n' "---"
        printf '\nBody\n'
    } > "$path"
}

setup_project() {   # [column-variant]
    local variant="${1:-stock}"
    local tmpdir
    tmpdir="$(mktemp -d)"
    CLEANUP_DIRS+=("$tmpdir")

    local local_dir="$tmpdir/local"
    mkdir -p "$local_dir"
    pushd "$local_dir" > /dev/null
    git init --quiet .
    git config user.email "test@test.com"
    git config user.name "Test"

    mkdir -p aitasks/metadata
    setup_fake_aitask_repo "$PWD"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_ls.sh"           .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_board_column.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh"       .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_query_files.sh"  .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"      .aitask-scripts/lib/
    # task_utils.sh sources these at load time; without them it aborts before
    # any flag is parsed. Same set test_boardcol_update.sh copies.
    for opt in archive_utils archive_scan agentcrew_utils; do
        cp "$PROJECT_DIR/.aitask-scripts/lib/$opt.sh" .aitask-scripts/lib/ 2>/dev/null || true
    done
    # DERIVED, never a hand-maintained list -- a drifted list is what made every
    # --boardcol call fail silently in t1488.
    copy_lib_py_closure "$PWD" board_columns
    chmod +x .aitask-scripts/*.sh

    # aitask_gate.sh is deliberately NOT copied: aitask_ls.sh's dependency scan
    # then degrades to `dep_scan_state=failed` with a stderr warning and the
    # listing still runs. No fixture task declares `depends:`, so nothing here
    # depends on that verdict. stderr is redirected at every call site below so
    # the warning does not pollute a captured listing.
    printf 'bug\nchore\nfeature\n' > aitasks/metadata/task_types.txt
    : > aitasks/metadata/labels.txt
    write_columns "$variant"

    git add -A
    git commit -m "Initial setup" --quiet
}

teardown() {
    popd > /dev/null 2>&1 || true
}

# Listing helper: stderr dropped (the absent-gate warning), stdout returned.
run_ls() {
    ./.aitask-scripts/aitask_ls.sh "$@" 2>/dev/null
}

# Same, but keeps the exit status AND stderr -- for the refusal cases, where
# the message IS the assertion.
run_ls_rc() {
    LS_RC=0
    LS_OUT="$(./.aitask-scripts/aitask_ls.sh "$@" 2>&1)" || LS_RC=$?
}

# Seeds the standard fixture tree used by most tests below.
#   t1  no boardcol key at all      -> unordered
#   t2  boardcol: unordered         -> unordered  (the OTHER unordered state)
#   t3  boardcol: <colA>
#   t4  boardcol: <colA>, label ui, issue_type bug
#   t5  boardcol: <colB>
#   t6/t6_1  parent in <colA> with a child in <colB>
seed_standard_tree() {   # <colA> <colB>
    local a="$1" b="$2"
    seed_task "aitasks/t1_no_key.md"
    seed_task "aitasks/t2_explicit_unordered.md" "boardcol: unordered"
    seed_task "aitasks/t3_in_a.md"     "boardcol: $a"
    seed_task "aitasks/t4_in_a_bug.md" "boardcol: $a" "labels: [ui]" "issue_type: bug"
    seed_task "aitasks/t5_in_b.md"     "boardcol: $b"
    seed_task "aitasks/t6_parent.md"   "boardcol: $a"
    seed_task "aitasks/t6/t6_1_child.md" "boardcol: $b"
}

# --- Test 0: the scaffold itself ---------------------------------------------

test_scaffold_column_probe_works() {
    echo "=== Test: the scaffold's board-column probe is healthy ==="
    setup_project stock

    local out rc=0
    out="$(./.aitask-scripts/aitask_board_column.sh list-columns \
             --root . --task-dir aitasks --include-unordered 2>&1)" || rc=$?
    assert_exit_zero_rc_out "scaffold column probe exits zero" "$rc" "$out"
    assert_contains "probe lists the configured columns" "COLUMN:now|" "$out"

    # The new verb has to be healthy too -- the filter is inert without it, and
    # a missing SCAN_OK is a silent fail-open in every consumer.
    rc=0
    out="$(./.aitask-scripts/aitask_board_column.sh columns-of \
             --root . --task-dir aitasks 2>&1)" || rc=$?
    assert_exit_zero_rc_out "columns-of exits zero" "$rc" "$out"
    assert_eq "columns-of terminates with SCAN_OK as the exact final line" \
        "SCAN_OK" "$(printf '%s' "$out" | tail -n1)"

    teardown
}

# --- Test 1: the filter matches the board, checked against the board ---------

test_matches_the_board_exactly() {
    echo "=== Test: --boardcol <col> agrees with the board, per task ==="
    setup_project stock
    seed_standard_tree now next

    local out
    out="$(run_ls --boardcol now -s all 99)"
    assert_eq_trim "--boardcol now returns exactly 3 parents" "3" "$(count_lines "$out")"
    assert_contains "--boardcol now includes t3" "t3_in_a.md" "$out"
    assert_contains "--boardcol now includes t4" "t4_in_a_bug.md" "$out"
    assert_contains "--boardcol now includes t6" "t6_parent.md" "$out"
    assert_not_contains "--boardcol now excludes the 'next' task" "t5_in_b.md" "$out"

    # Independent ground truth: ask the BOARD about each hit, rather than
    # comparing against the expectation written just above.
    local f n cur mismatches=""
    while IFS= read -r f; do
        [[ -n "$f" ]] || continue
        n="$(printf '%s' "$f" | grep -oE '^t[0-9]+' | sed 's/t//')"
        cur="$(./.aitask-scripts/aitask_board_column.sh current-column \
                 --root . --task "$n" 2>&1)"
        [[ "$cur" == "CURRENT:$n|now" ]] || mismatches="$mismatches $n=>$cur"
    done <<< "$out"
    assert_eq "every --boardcol now hit is in 'now' per the board seam" \
        "" "$mismatches"

    teardown
}

# --- Test 2: D2 -- the unordered lane is TWO states ---------------------------

test_unordered_matches_both_states() {
    echo "=== Test: --boardcol unordered covers absent AND explicit (D2) ==="
    setup_project stock
    seed_standard_tree now next

    local out
    out="$(run_ls --boardcol unordered -s all 99)"
    assert_eq_trim "--boardcol unordered returns exactly 2 parents" \
        "2" "$(count_lines "$out")"
    assert_contains "unordered includes the task with NO boardcol key" \
        "t1_no_key.md" "$out"
    assert_contains "unordered includes the task with an EXPLICIT unordered" \
        "t2_explicit_unordered.md" "$out"
    assert_not_contains "unordered excludes a columned task" "t3_in_a.md" "$out"

    # Negative control -- without it the two assertions above could both hold
    # for a filter that simply returns everything it cannot classify. Move the
    # explicit-unordered task into a real column through the board's own writer
    # and it must DROP OUT.
    local mv rc=0
    mv="$(./.aitask-scripts/aitask_board_column.sh move \
            --root . --task 2 --column now 2>&1)" || rc=$?
    assert_exit_zero_rc_out "seam move succeeds" "$rc" "$mv"
    out="$(run_ls --boardcol unordered -s all 99)"
    assert_eq_trim "after the move, unordered returns exactly 1" \
        "1" "$(count_lines "$out")"
    assert_not_contains "the moved task left the unordered lane" \
        "t2_explicit_unordered.md" "$out"

    # ...and it must have ARRIVED. A drop-out alone is also what a broken
    # filter produces.
    out="$(run_ls --boardcol now -s all 99)"
    assert_contains "the moved task arrived in 'now'" \
        "t2_explicit_unordered.md" "$out"

    teardown
}

# --- Test 3: D3 -- an unknown id is refused, not silently empty ---------------

test_unknown_column_is_refused() {
    echo "=== Test: an unknown column id is refused (D3) ==="
    setup_project stock
    seed_standard_tree now next

    run_ls_rc --boardcol nosuchcol -s all 99
    assert_exit_nonzero_rc "unknown column exits non-zero" "$LS_RC"
    assert_contains "message names the offending id" "nosuchcol" "$LS_OUT"
    assert_contains "message names a configured id" "now" "$LS_OUT"
    assert_contains "message offers unordered too" "unordered" "$LS_OUT"

    teardown
}

# --- Test 4: renamed columns --------------------------------------------------

test_renamed_columns() {
    echo "=== Test: a project with RENAMED columns filters correctly ==="
    setup_project renamed
    seed_standard_tree doing parked

    local out
    out="$(run_ls --boardcol doing -s all 99)"
    assert_eq_trim "--boardcol doing returns exactly 3 parents" \
        "3" "$(count_lines "$out")"
    assert_contains "--boardcol doing includes t3" "t3_in_a.md" "$out"

    out="$(run_ls --boardcol parked -s all 99)"
    assert_eq_trim "--boardcol parked returns exactly 1 parent" \
        "1" "$(count_lines "$out")"
    assert_contains "--boardcol parked includes t5" "t5_in_b.md" "$out"

    # The stock id must NOT be silently accepted here -- this is the assertion
    # that fails if anything hardcodes DEFAULT_ORDER.
    run_ls_rc --boardcol now -s all 99
    assert_exit_nonzero_rc "'now' is refused in a renamed-columns project" "$LS_RC"
    assert_contains "refusal names the renamed ids" "doing" "$LS_OUT"

    teardown
}

# --- Test 5: non-string boardcol matches nothing ------------------------------

test_non_string_boardcol_matches_nothing() {
    echo "=== Test: a non-string boardcol matches no column ==="
    setup_project stock
    seed_task "aitasks/t1_no_key.md"
    seed_task "aitasks/t7_typed.md" "boardcol: 42"
    seed_task "aitasks/t3_in_a.md" "boardcol: now"

    # `42` is not a configured id, so asking for it is refused outright.
    run_ls_rc --boardcol 42 -s all 99
    assert_exit_nonzero_rc "--boardcol 42 is refused (not a configured id)" "$LS_RC"

    # And the task itself appears in NO lane -- specifically not `unordered`,
    # which is the tempting wrong answer.
    local out
    out="$(run_ls --boardcol now -s all 99)"
    assert_not_contains "typed task is not in 'now'" "t7_typed.md" "$out"
    out="$(run_ls --boardcol unordered -s all 99)"
    assert_not_contains "typed task is NOT in 'unordered' either" \
        "t7_typed.md" "$out"
    assert_contains "the genuinely-unordered task is still listed" \
        "t1_no_key.md" "$out"

    teardown
}

test_yaml_boolean_boardcol_matches_nothing() {
    echo "=== Test: 'boardcol: no' against a column named 'no' ==="
    # The case a bash-local read of the field gets wrong: bash sees the string
    # "no" and would match; YAML 1.1 parses it as the boolean False, so the
    # board renders the task nowhere. `no` is a genuine id -- it is what
    # generate_col_id() emits for the title "No".
    setup_project yamltyped
    seed_task "aitasks/t1_no_key.md"
    seed_task "aitasks/t8_bool.md"  "boardcol: no"
    seed_task "aitasks/t9_quoted.md" "boardcol: \"no\""

    local out
    out="$(run_ls --boardcol no -s all 99)"
    assert_not_contains "unquoted 'no' does NOT match the column 'no'" \
        "t8_bool.md" "$out"
    assert_contains "quoted \"no\" DOES match the column 'no'" \
        "t9_quoted.md" "$out"
    assert_eq_trim "--boardcol no returns exactly the quoted task" \
        "1" "$(count_lines "$out")"

    out="$(run_ls --boardcol unordered -s all 99)"
    assert_not_contains "the boolean task is not in 'unordered' either" \
        "t8_bool.md" "$out"

    teardown
}

# --- Test 6: composition with the existing filters -----------------------------

test_composes_with_other_filters() {
    echo "=== Test: --boardcol composes with --status / -l / --type ==="
    setup_project stock
    seed_standard_tree now next
    # t4 is the only 'now' task that is both label:ui and type:bug.

    local out
    out="$(run_ls --boardcol now -s all -l ui 99)"
    assert_eq_trim "--boardcol now -l ui returns exactly 1" "1" "$(count_lines "$out")"
    assert_contains "--boardcol now -l ui returns t4" "t4_in_a_bug.md" "$out"

    out="$(run_ls --boardcol now -s all --type bug 99)"
    assert_eq_trim "--boardcol now --type bug returns exactly 1" \
        "1" "$(count_lines "$out")"
    assert_contains "--boardcol now --type bug returns t4" "t4_in_a_bug.md" "$out"

    out="$(run_ls --boardcol next -s all --type bug 99)"
    assert_eq_trim "--boardcol next --type bug returns 0" "0" "$(count_lines "$out")"

    # Status narrows within the column, and the column narrows within status.
    ./.aitask-scripts/aitask_update.sh --batch 3 --status Postponed >/dev/null 2>&1
    out="$(run_ls --boardcol now 99)"          # default status filter = Ready
    assert_eq_trim "--boardcol now (Ready only) returns exactly 2" \
        "2" "$(count_lines "$out")"
    assert_not_contains "the Postponed task is filtered out" "t3_in_a.md" "$out"

    teardown
}

# --- Test 7 / mitigation `mode-matrix-key-agreement` --------------------------

test_mode_matrix_key_agreement() {
    echo "=== Test: --boardcol across all four listing modes ==="
    # The map is keyed by task-file PATH, and those keys must agree exactly with
    # parse_task_metadata's squeezed `current_task_file`. Mode 3 in particular
    # yields `aitasks//t6/t6_1_child.md` from its trailing-slash glob. A key
    # mismatch is fatal by design, so it surfaces here as a non-zero exit rather
    # than as a listing that merely looks short.
    setup_project stock
    seed_standard_tree now next

    local mode
    for mode in "default" "--all-levels" "--tree" "--children 6"; do
        local args=()
        [[ "$mode" == "default" ]] || read -r -a args <<< "$mode"
        run_ls_rc --boardcol next -s all "${args[@]}" 99
        assert_exit_zero_rc_out "mode '$mode' exits zero under --boardcol" \
            "$LS_RC" "$LS_OUT"
    done

    # Children carry their own boardcol and must be reachable through the modes
    # that list them -- otherwise "exits zero" is satisfied by listing nothing.
    local out
    out="$(run_ls --boardcol next -s all --all-levels 99)"
    assert_contains "--all-levels reaches the child in 'next'" \
        "t6_1_child.md" "$out"
    out="$(run_ls --boardcol next -s all --children 6 99)"
    assert_eq_trim "--children 6 returns exactly the one child in 'next'" \
        "1" "$(count_lines "$out")"
    assert_contains "--children 6 returns the child" "t6_1_child.md" "$out"
    out="$(run_ls --boardcol next -s all --children 6 99)"
    assert_not_contains "--children 6 does not leak the parent" \
        "t6_parent.md" "$out"

    teardown
}

test_map_miss_is_fatal() {
    echo "=== Test: a truncated column map is FATAL, not a short listing ==="
    # The negative control for the assertion above: without it, "exits zero in
    # every mode" would also hold for a build_boardcol_map that never detects a
    # miss. Stub the seam so it emits a well-formed scan -- SCAN_OK and all --
    # with ONE row omitted.
    setup_project stock
    seed_standard_tree now next

    local real=".aitask-scripts/aitask_board_column_real.sh"
    mv .aitask-scripts/aitask_board_column.sh "$real"
    cat > .aitask-scripts/aitask_board_column.sh <<'STUB'
#!/usr/bin/env bash
# Passes everything through EXCEPT `columns-of`, whose output loses one row.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${1:-}" == "columns-of" ]]; then
    "$here/aitask_board_column_real.sh" "$@" | grep -v 't3_in_a\.md$'
    exit 0
fi
exec "$here/aitask_board_column_real.sh" "$@"
STUB
    chmod +x .aitask-scripts/aitask_board_column.sh

    # A private TMPDIR makes the scratch-file leak below measurable without
    # counting files in a shared /tmp that other processes are also using.
    local tmp_probe
    tmp_probe="$(mktemp -d)"
    CLEANUP_DIRS+=("$tmp_probe")

    TMPDIR="$tmp_probe" run_ls_rc --boardcol now -s all 99
    assert_exit_nonzero_rc "a missing map row aborts the listing" "$LS_RC"
    assert_contains "the error names the unresolved path" "t3_in_a.md" "$LS_OUT"

    # aitask_ls.sh mktemps two scratch files and used to remove them only by
    # falling off the bottom of the script -- fine while every `die` fired during
    # argument validation, i.e. before either file existed. --boardcol added
    # three deaths that can fire AFTER, so each error exit leaked one or two
    # files per invocation. The EXIT trap is what closes that; this is its guard.
    assert_eq_trim "a fatal exit leaves no scratch files behind" \
        "0" "$(find "$tmp_probe" -maxdepth 1 -type f | wc -l)"

    # Positive control: the same probe over a SUCCESSFUL run, so "0 files" is
    # not merely proof that the temp files were written somewhere else.
    TMPDIR="$tmp_probe" run_ls --boardcol unordered -s all 99 >/dev/null 2>&1 || true
    assert_eq_trim "a successful exit leaves no scratch files behind either" \
        "0" "$(find "$tmp_probe" -maxdepth 1 -type f | wc -l)"

    teardown
}

test_trap_never_removes_an_inherited_path() {
    echo "=== Test: the cleanup trap never deletes a caller's file ==="
    # The trap must be installed with the FIRST mktemp -- one installed later
    # would not cover the deaths in between -- so it necessarily names
    # `output_file` before that variable is assigned. Bash imports exported
    # environment variables, so a caller running
    #     output_file=/some/path ait ls --boardcol now
    # would have `rm -f` delete THAT path on any death in the window. The
    # `output_file=""` initialiser ahead of the trap is what closes it; a
    # `${output_file:-}` default cannot, because an inherited value IS set and
    # the default never applies.
    #
    # The window is exactly: trap installed -> `output_file` assigned. The only
    # death reachable inside it is build_boardcol_map's scan failure (the
    # missing-executable death just above it is shadowed by
    # normalize_board_column, which runs earlier and dies first), so the stub
    # below must fail `columns-of` while letting `list-columns` succeed.
    setup_project stock
    seed_standard_tree now next

    local sentinel="$PWD/CALLER_OWNED.txt"
    printf 'precious caller data\n' > "$sentinel"

    local real=".aitask-scripts/aitask_board_column_real.sh"
    mv .aitask-scripts/aitask_board_column.sh "$real"
    cat > .aitask-scripts/aitask_board_column.sh <<'STUB'
#!/usr/bin/env bash
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ "${1:-}" == "columns-of" ]] && exit 3
exec "$here/aitask_board_column_real.sh" "$@"
STUB
    chmod +x .aitask-scripts/aitask_board_column.sh

    local rc=0 out
    out="$(output_file="$sentinel" ./.aitask-scripts/aitask_ls.sh \
             --boardcol now -s all 99 2>&1)" || rc=$?

    # Positive control FIRST: if this death is not actually reached, the
    # survival assertion below is vacuous -- the file would survive simply
    # because the trap never ran.
    assert_exit_nonzero_rc "the in-window death is actually reached" "$rc"
    assert_contains "...and it is the scan failure, inside the window" \
        "board column scan failed" "$out"

    assert_file_exists "an inherited output_file is NOT deleted" "$sentinel"
    assert_eq "...and its contents are untouched" \
        "precious caller data" "$(cat "$sentinel" 2>/dev/null)"

    teardown
}

# --- Argument guard -----------------------------------------------------------

test_value_taking_flags_require_a_value() {
    echo "=== Test: every value-taking flag rejects a missing/empty value ==="
    # Two silent failures, found while reviewing --boardcol and shared by all six
    # value-taking flags (--boardcol merely added the sixth `shift 2`):
    #
    #   `ait ls --type`    -> with one argument left, `shift 2` FAILS and shifts
    #                         nothing, so the same argv is parsed forever. There
    #                         is no `set -e` here to stop it: the command spins.
    #   `ait ls --type ''` -> an empty value is skipped by every filter block, so
    #                         the ORDINARY listing comes back looking filtered.
    #
    # The sibling flags are covered here rather than in
    # test_ls_display_and_filters.sh because they share ONE guard
    # (`require_flag_value`); splitting the cases would let a partial revert pass.
    #
    # Every invocation goes through `run_bounded` (tests/lib/proc_fixtures.sh):
    # a regression of the first bug HANGS, and an un-bounded assertion would
    # wedge the whole suite instead of failing it. It is `run_bounded` and not a
    # bare `timeout` because macOS is supported and ships that binary only as
    # `gtimeout`.
    setup_project stock
    seed_standard_tree now next

    local flag out rc bound_out
    bound_out="$(mktemp)"
    for flag in --boardcol --type -s -l --followup-kind -c; do
        rc=0
        run_bounded 10 "$bound_out" ./.aitask-scripts/aitask_ls.sh "$flag" || rc=$?
        out="$(cat "$bound_out")"
        assert_eq "'$flag' with no value does not loop (exit 124 = hung)" \
            "1" "$rc"
        assert_contains "'$flag' with no value names the flag" "$flag" "$out"
        assert_contains "'$flag' with no value says a value is required" \
            "requires a value" "$out"

        rc=0
        run_bounded 10 "$bound_out" ./.aitask-scripts/aitask_ls.sh "$flag" "" 99 || rc=$?
        out="$(cat "$bound_out")"
        assert_eq "'$flag' with an EMPTY value is refused, not ignored" "1" "$rc"
        assert_contains "'$flag' empty-value message says non-empty" \
            "requires a non-empty value" "$out"
    done

    # Positive control: the guard must not have broken the ordinary form, and a
    # valueless FLAG that legitimately takes none must still work.
    rc=0
    run_bounded 10 "$bound_out" ./.aitask-scripts/aitask_ls.sh --boardcol now -s all 99 || rc=$?
    out="$(cat "$bound_out")"
    assert_exit_zero_rc_out "a supplied value still works" "$rc" "$out"
    assert_contains "...and still filters" "t3_in_a.md" "$out"
    rc=0
    run_bounded 10 "$bound_out" ./.aitask-scripts/aitask_ls.sh --no-followup-kind 99 || rc=$?
    out="$(cat "$bound_out")"
    assert_exit_zero_rc_out "a genuinely valueless flag is unaffected" "$rc" "$out"

    rm -f "$bound_out"
    teardown
}

# --- Mitigation `hot-path-laziness-guard` -------------------------------------

test_hot_path_stays_lazy() {
    echo "=== Test: ait ls without --boardcol never touches the column seam ==="
    # `ait ls` runs on every /aitask-pick and already costs seconds; the Python
    # subprocess is only free because it is lazy. Exact-path tripwire: the call
    # site is "$SCRIPT_DIR/aitask_board_column.sh", so a PATH shim would never
    # observe it.
    setup_project stock
    seed_standard_tree now next

    local sentinel="$PWD/.colseam-calls"
    local real=".aitask-scripts/aitask_board_column_real.sh"
    mv .aitask-scripts/aitask_board_column.sh "$real"
    cat > .aitask-scripts/aitask_board_column.sh <<'STUB'
#!/usr/bin/env bash
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
printf '%s\n' "$1" >> "$AIT_TEST_COLSEAM_SENTINEL"
exec "$here/aitask_board_column_real.sh" "$@"
STUB
    chmod +x .aitask-scripts/aitask_board_column.sh
    export AIT_TEST_COLSEAM_SENTINEL="$sentinel"

    local out
    out="$(run_ls -v -s all 99)"
    assert_file_not_exists "no --boardcol => the column seam is never invoked" \
        "$sentinel"
    assert_contains "...and the listing still works" "t3_in_a.md" "$out"

    # POSITIVE CONTROL. Without it the assertion above is vacuous -- it would
    # also pass for a tripwire wired to a path nothing calls. Two calls are
    # expected: list-columns (the value validation) then columns-of (the scan).
    out="$(run_ls --boardcol now -s all 99)"
    assert_file_exists "with --boardcol => the seam IS invoked" "$sentinel"
    assert_eq_trim "exactly two seam calls: validate, then scan" \
        "2" "$(wc -l < "$sentinel")"
    assert_eq_trim "first call validates the column id" \
        "list-columns" "$(sed -n 1p "$sentinel")"
    assert_eq_trim "second call is the whole-tree scan" \
        "columns-of" "$(sed -n 2p "$sentinel")"
    assert_contains "and the filter still returns the right task" \
        "t3_in_a.md" "$out"

    unset AIT_TEST_COLSEAM_SENTINEL
    teardown
}

# --- Run ---------------------------------------------------------------------

test_scaffold_column_probe_works
test_matches_the_board_exactly
test_unordered_matches_both_states
test_unknown_column_is_refused
test_renamed_columns
test_non_string_boardcol_matches_nothing
test_yaml_boolean_boardcol_matches_nothing
test_composes_with_other_filters
test_mode_matrix_key_agreement
test_map_miss_is_fatal
test_trap_never_removes_an_inherited_path
test_value_taking_flags_require_a_value
test_hot_path_stays_lazy

for d in "${CLEANUP_DIRS[@]}"; do rm -rf "$d"; done

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
