#!/usr/bin/env bash
# test_work_report_gather.sh - Tests for aitask_work_report_gather.sh (t1162_1).
#
# The gatherer is the deterministic report-input layer for /aitask-work-report
# and the board `w` flow. It emits board columns, the parent tasks they contain
# in board order, a per-bucket throughput estimate and a completion projection:
#     COLUMN:<col_id>|<title>
#     TASK:<col_id>|<task_id>|<boardidx>|<status>|<priority>|<effort>|<pending_children>|<remaining_items>|<path>
#     VELOCITY_MODEL:<model_id>|<window_days>|<start>|<end>|<model_label>
#     VELOCITY:<bucket_id>|<observed_units>|<completed_count>|<avg_per_unit>|<bucket_label>
#     PROJECTION:<remaining_total>|<projected_date>|<days_ahead>|<basis>|<caveat>
#     ERROR:<kind>:<id>  |  NO_TASKS
#
# Coverage:
#   - ordering, boardidx ascending, filename tie-break, Unsorted dynamics
#   - --tasks subsets, t-prefix normalization, dedup, significant order
#   - fail-closed staging: unknown column / unknown task / moved / reordered
#   - --list-columns enumeration incl. an orphan column_order id
#   - delimiter safety for every fixed-field class + free-text round-trip
#   - children_to_implement type policy (None / str / mapping)
#   - remaining-work semantics, phantom-stub exclusion
#   - velocity buckets, the worked projection example, bound + zero history
#   - projection is opt-in and floored at 10 completions
#   - board-parity edges: malformed frontmatter, empty board config,
#     quoted/mixed boardidx, history bound to TASK_DIR
#   - the velocity-model seam (dow vs flat) and board equivalence
#
# Run: bash tests/test_work_report_gather.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
. "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

GATHER="$PROJECT_DIR/.aitask-scripts/aitask_work_report_gather.sh"
EQUIV="$PROJECT_DIR/tests/lib/work_report_equiv.py"
PYTHON="$(require_ait_python)"

DEFAULT_BOARD='{"columns":[{"id":"now","title":"Now"},{"id":"next","title":"Next"}],"column_order":["now","next"]}'

# --- fixture helpers -------------------------------------------------------

setup_tree() {  # [tree_subdir]
    local tmp sub="${1:-}"
    tmp="$(mktemp -d "${TMPDIR:-/tmp}/test_workrep_XXXXXX")"
    CLEANUP_DIRS+=("$tmp")
    if [[ -n "$sub" ]]; then
        mkdir -p "$tmp/$sub"
        export TASK_DIR="$tmp/$sub/aitasks"
    else
        export TASK_DIR="$tmp/aitasks"
    fi
    mkdir -p "$TASK_DIR/metadata" "$TASK_DIR/archived"
    board_config "$DEFAULT_BOARD"
}

board_config() {  # <json>
    printf '%s\n' "$1" > "$TASK_DIR/metadata/board_config.json"
}

make_named() {  # <filename> <boardcol|-> <boardidx|-> [extra frontmatter lines...]
    local name="$1" col="$2" idx="$3"
    shift 3
    {
        echo "---"
        echo "priority: high"
        echo "effort: medium"
        echo "status: Ready"
        [[ "$col" != "-" ]] && echo "boardcol: $col"
        [[ "$idx" != "-" ]] && echo "boardidx: $idx"
        local line
        for line in "$@"; do echo "$line"; done
        echo "---"
        echo
        echo "Body."
    } > "$TASK_DIR/$name"
}

make_task() {  # <id> <boardcol|-> <boardidx|-> [extra frontmatter lines...]
    local id="$1"
    shift
    make_named "t${id}_demo.md" "$@"
}

make_archived() {  # <id> <completed_at YYYY-MM-DD>
    {
        echo "---"
        echo "status: Done"
        echo "issue_type: feature"
        echo "completed_at: $2 12:00"
        echo "---"
        echo
        echo "done"
    } > "$TASK_DIR/archived/t${1}_arch.md"
}

# --- output helpers --------------------------------------------------------

task_ids() {  # <output>  -> space-separated task ids in emitted order
    printf '%s\n' "$1" | grep '^TASK:' | cut -d'|' -f2 | tr '\n' ' ' | sed 's/ $//'
}

task_field() {  # <output> <task_id> <field_no>
    printf '%s\n' "$1" | grep "^TASK:[^|]*|$2|" | cut -d'|' -f"$3"
}

# --- Test: ordering, tie-break, Unsorted ------------------------------------

test_ordering() {
    echo "=== ordering: columns left-to-right, boardidx ascending ==="
    setup_tree
    make_task 100 now 20
    make_task 101 now 10
    make_task 102 next 5

    local out
    out="$("$GATHER" --columns now,next)"
    assert_eq_trim "grouped by column, ascending boardidx" "101 100 102" "$(task_ids "$out")"
    assert_contains "COLUMN:now emitted" "COLUMN:now|Now" "$out"
    assert_contains "COLUMN:next emitted" "COLUMN:next|Next" "$out"

    # Column selection order must not override board order.
    out="$("$GATHER" --columns next,now)"
    assert_eq_trim "board order wins over argument order" "101 100 102" "$(task_ids "$out")"
}

test_tie_break() {
    echo "=== tie-break: equal boardidx ordered by filename ==="
    setup_tree
    # Six tasks on the same boardidx. Filename order deliberately contradicts
    # numeric id order (t10 < t9 lexicographically), so the expected sequence
    # can only come from the filename key. Six of them also makes it implausible
    # that a regression to directory-enumeration order would coincidentally
    # reproduce this exact permutation.
    make_named "t9_aaa.md" now 10
    make_named "t10_bbb.md" now 10
    make_named "t7_ccc.md" now 10
    make_named "t120_ddd.md" now 10
    make_named "t31_eee.md" now 10
    make_named "t8_fff.md" now 10

    local out
    out="$("$GATHER" --columns now)"
    assert_eq_trim "equal boardidx -> filename order" \
        "10 120 31 7 8 9" "$(task_ids "$out")"
}

test_unordered() {
    echo "=== Unsorted column: default boardcol, explicit request, enumeration ==="
    setup_tree
    make_task 200 - -        # no boardcol/boardidx -> unordered, idx 0
    make_task 201 now 5

    local out
    out="$("$GATHER" --columns unordered,now)"
    assert_eq_trim "unordered emitted first" "200 201" "$(task_ids "$out")"
    assert_contains "unordered title" "COLUMN:unordered|Unsorted / Inbox" "$out"

    out="$("$GATHER" --list-columns)"
    assert_eq_trim "list-columns includes unordered when populated" \
        "COLUMN:unordered|Unsorted / Inbox COLUMN:now|Now COLUMN:next|Next" "$out"

    # Same tree without an unordered task: the dynamic column disappears.
    rm "$TASK_DIR/t200_demo.md"
    out="$("$GATHER" --list-columns)"
    assert_not_contains "list-columns drops empty unordered" "COLUMN:unordered" "$out"

    # A column_order id with no `columns` entry is not a reportable column
    # (the board's renderer skips it too).
    board_config '{"columns":[{"id":"now","title":"Now"}],"column_order":["now","ghost"]}'
    out="$("$GATHER" --list-columns)"
    assert_not_contains "orphan column_order id dropped" "ghost" "$out"
    out="$("$GATHER" --columns ghost)"
    assert_eq_trim "orphan id is unknown when requested" "ERROR:unknown_column:ghost" "$out"
}

# --- Test: --tasks selection ------------------------------------------------

test_task_selection() {
    echo "=== --tasks: subset, t-prefix, dedup, significant order ==="
    setup_tree
    make_task 300 now 10
    make_task 301 now 20
    make_task 302 now 30

    local out
    out="$("$GATHER" --columns now --tasks 300,302)"
    assert_eq_trim "subset honored" "300 302" "$(task_ids "$out")"

    out="$("$GATHER" --columns now --tasks t300,t302)"
    assert_eq_trim "t prefix normalized" "300 302" "$(task_ids "$out")"

    out="$("$GATHER" --columns now --tasks 300,300,302)"
    assert_eq_trim "duplicates deduped" "300 302" "$(task_ids "$out")"

    out="$("$GATHER" --columns now --tasks 302,300)"
    assert_eq_trim "reordered selection rejected" \
        "ERROR:task_order_changed:300,302" "$out"
    assert_not_contains "order error is fail-closed" "TASK:" "$out"
}

test_fail_closed() {
    echo "=== fail-closed staging: unknown column / task / moved task ==="
    setup_tree
    make_task 400 now 10
    make_task 401 next 10

    local out
    out="$("$GATHER" --columns nope,now)"
    assert_eq_trim "unknown column reported alone" "ERROR:unknown_column:nope" "$out"
    assert_not_contains "no columns emitted on error" "COLUMN:" "$out"
    assert_not_contains "no velocity emitted on error" "VELOCITY" "$out"
    assert_not_contains "no projection emitted on error" "PROJECTION" "$out"

    out="$("$GATHER" --columns now --tasks 400,999)"
    assert_eq_trim "unknown task" "ERROR:unknown_task:999" "$out"

    out="$("$GATHER" --columns now --tasks 400,401)"
    assert_eq_trim "task outside selected columns" \
        "ERROR:task_not_in_selected_columns:401" "$out"

    # All errors within the failing stage are listed together.
    out="$("$GATHER" --columns now --tasks 999,401)"
    assert_contains "both membership errors listed (unknown)" "ERROR:unknown_task:999" "$out"
    assert_contains "both membership errors listed (moved)" \
        "ERROR:task_not_in_selected_columns:401" "$out"
}

# --- Test: delimiter safety (one block per fixed-field class) ---------------

test_delimiter_argv() {
    echo "=== delimiter safety: pipe in argv -> usage error ==="
    setup_tree
    make_task 500 now 10
    assert_exit_nonzero "pipe in --columns rejected" "$GATHER" --columns 'now|x'
    assert_exit_nonzero "pipe in --tasks rejected" "$GATHER" --columns now --tasks '500|x'
}

test_delimiter_col_id() {
    echo "=== delimiter safety: pipe in a col_id -> infrastructure error ==="
    setup_tree
    board_config '{"columns":[{"id":"a|b","title":"Bad"}],"column_order":["a|b"]}'
    make_task 510 now 10
    assert_exit_nonzero "unrepresentable column id rejected" "$GATHER" --list-columns

    local err
    err="$("$GATHER" --list-columns 2>&1 >/dev/null)"
    assert_contains "diagnostic names the offending id" "a|b" "$err"
}

test_delimiter_enums() {
    echo "=== delimiter safety: pipe in status/priority/effort -> 'invalid' ==="
    setup_tree
    make_named "t520_demo.md" now 10 'status: "Ready|X"'
    make_named "t521_demo.md" now 20 'priority: "high|X"'
    make_named "t522_demo.md" now 30 'effort: "low|X"'

    local out
    out="$("$GATHER" --columns now)"
    assert_eq_trim "unsafe status coerced" "invalid" "$(task_field "$out" 520 4)"
    assert_eq_trim "unsafe priority coerced" "invalid" "$(task_field "$out" 521 5)"
    assert_eq_trim "unsafe effort coerced" "invalid" "$(task_field "$out" 522 6)"
    assert_eq_trim "one line per task despite unsafe values" "520 521 522" "$(task_ids "$out")"
}

test_delimiter_free_text() {
    echo "=== delimiter safety: free-text last field round-trips a pipe ==="
    # A pipe in the tree path AND in the column title, parsed back with the
    # documented maxsplit rule.
    setup_tree 'pi|pe'
    board_config '{"columns":[{"id":"now","title":"Now | Later"}],"column_order":["now"]}'
    make_task 530 now 10

    local out title path
    out="$("$GATHER" --columns now)"
    title="$(printf '%s\n' "$out" | grep '^COLUMN:' | cut -d'|' -f2-)"
    path="$(printf '%s\n' "$out" | grep '^TASK:' | cut -d'|' -f9-)"
    assert_eq_trim "title with a pipe survives maxsplit" "Now | Later" "$title"
    assert_eq_trim "path with a pipe survives maxsplit" "$TASK_DIR/t530_demo.md" "$path"
}

test_delimiter_newline() {
    echo "=== delimiter safety: CR/LF in free text collapses to a space ==="
    setup_tree
    board_config '{"columns":[{"id":"now","title":"Now\nLater"}],"column_order":["now"]}'
    make_task 540 now 10

    local out count
    out="$("$GATHER" --columns now)"
    count="$(printf '%s\n' "$out" | grep -c '^COLUMN:')"
    assert_eq_trim "newline in a title does not split the record" "1" "$count"
    assert_contains "newline replaced with a space" "COLUMN:now|Now Later" "$out"
}

# --- Test: children_to_implement type policy --------------------------------

test_children_types() {
    echo "=== children_to_implement type policy ==="
    setup_tree
    make_task 600 now 10 'children_to_implement: [t600_1, t600_2, t600_3]'
    make_task 601 now 20 'children_to_implement: []'
    make_task 602 now 30 'children_to_implement:'
    make_task 603 now 40 'children_to_implement: oops'
    make_task 604 now 50 'children_to_implement: {a: 1}'

    local out err
    out="$("$GATHER" --columns now 2>/dev/null)"
    err="$("$GATHER" --columns now 2>&1 >/dev/null)"

    assert_eq_trim "list -> pending count" "3" "$(task_field "$out" 600 7)"
    assert_eq_trim "list -> remaining count" "3" "$(task_field "$out" 600 8)"
    assert_eq_trim "empty list -> 0 pending" "0" "$(task_field "$out" 601 7)"
    assert_eq_trim "empty list -> 0 remaining" "0" "$(task_field "$out" 601 8)"
    assert_eq_trim "None -> 0 pending" "0" "$(task_field "$out" 602 7)"
    assert_eq_trim "None -> 0 remaining" "0" "$(task_field "$out" 602 8)"
    # A scalar must NOT be counted as len("oops"): fall back to the leaf rule.
    assert_eq_trim "scalar -> leaf pending" "0" "$(task_field "$out" 603 7)"
    assert_eq_trim "scalar -> leaf remaining" "1" "$(task_field "$out" 603 8)"
    assert_eq_trim "mapping -> leaf pending" "0" "$(task_field "$out" 604 7)"
    assert_eq_trim "mapping -> leaf remaining" "1" "$(task_field "$out" 604 8)"
    assert_contains "scalar warned on stderr" "t603_demo.md" "$err"
    assert_contains "mapping warned on stderr" "t604_demo.md" "$err"
    assert_not_contains "warnings stay off stdout" "expected a list" "$out"
}

test_remaining_and_phantom() {
    echo "=== remaining-work semantics + phantom-stub exclusion ==="
    setup_tree
    make_task 700 now 10 'status: Done'
    make_task 701 now 20              # active leaf
    printf -- '---\nboardcol: now\nboardidx: 30\n---\n\nstub\n' \
        > "$TASK_DIR/t702_demo.md"    # phantom stub: only board layout keys
    printf -- '---\n---\n\nempty\n' > "$TASK_DIR/t703_demo.md"

    local out
    out="$("$GATHER" --columns now)"
    assert_eq_trim "Done leaf -> 0 remaining" "0" "$(task_field "$out" 700 8)"
    assert_eq_trim "active leaf -> 1 remaining" "1" "$(task_field "$out" 701 8)"
    assert_eq_trim "phantom stubs excluded" "700 701" "$(task_ids "$out")"
}

test_no_tasks() {
    echo "=== empty selection -> NO_TASKS (velocity block still emitted) ==="
    setup_tree
    make_task 800 next 10

    local out
    out="$("$GATHER" --columns now --now 2026-07-19)"
    assert_contains "NO_TASKS sentinel" "NO_TASKS" "$out"
    assert_not_contains "no empty COLUMN headings" "COLUMN:" "$out"
    assert_contains "velocity block still present" "VELOCITY_MODEL:dow|" "$out"
    assert_not_contains "no projection without --project" "PROJECTION" "$out"

    out="$("$GATHER" --columns now --now 2026-07-19 --project)"
    assert_contains "projection of nothing is today" \
        "PROJECTION:0|2026-07-19|0|0|unweighted_task_counts" "$out"
}

# --- Test: velocity + projection --------------------------------------------

test_velocity_buckets() {
    echo "=== dow velocity: seven buckets, zero days stay in the denominator ==="
    setup_tree
    make_task 900 now 10
    # Window = 7 days ending Sunday 2026-07-19, so each weekday is observed once.
    make_archived 901 2026-07-13   # Monday
    make_archived 902 2026-07-13   # Monday

    local out count
    out="$("$GATHER" --columns now --now 2026-07-19 --velocity-window 7)"
    count="$(printf '%s\n' "$out" | grep -c '^VELOCITY:')"
    assert_eq_trim "exactly seven weekday buckets" "7" "$count"
    assert_contains "window echoed with its date range" \
        "VELOCITY_MODEL:dow|7|2026-07-13|2026-07-19|" "$out"
    assert_contains "Monday: 2 completions over 1 observed Monday" \
        "VELOCITY:1|1|2|2|Mon" "$out"
    # A weekday with no completions is still observed — that is what keeps the
    # average honest rather than undefined.
    assert_contains "quiet Sunday still counted as observed" \
        "VELOCITY:7|1|0|0|Sun" "$out"
    assert_contains "quiet Tuesday still counted as observed" \
        "VELOCITY:2|1|0|0|Tue" "$out"
}

test_projection_worked_example() {
    echo "=== projection: the pinned worked example (Sun 10 / Mon 20, 25 left) ==="
    setup_tree
    local i children=""
    for i in $(seq 1 25); do children="${children}t900_${i}, "; done
    make_task 910 now 10 "children_to_implement: [${children%, }]"

    for i in $(seq 1 20); do make_archived "92$i" 2026-07-13; done   # Monday
    for i in $(seq 1 10); do make_archived "93$i" 2026-07-19; done   # Sunday

    local out
    out="$("$GATHER" --columns now --now 2026-07-19 --velocity-window 7 --project)"
    assert_contains "Sunday average is 10" "VELOCITY:7|1|10|10|Sun" "$out"
    assert_contains "Monday average is 20" "VELOCITY:1|1|20|20|Mon" "$out"
    # 25 left on a Sunday: Sunday burns 10 (15 left), Monday burns 20 -> done.
    assert_contains "projected to the following Monday" \
        "PROJECTION:25|2026-07-20|1|30|unweighted_task_counts" "$out"
}

test_projection_edges() {
    echo "=== projection: zero history, window boundary, walk bound ==="
    setup_tree
    make_task 940 now 10

    local out i
    out="$("$GATHER" --columns now --now 2026-07-19 --velocity-window 7 --project)"
    assert_contains "no history -> insufficient_data" \
        "PROJECTION:1|none|insufficient_data|0|unweighted_task_counts" "$out"

    # A completion just outside the window must not count at all.
    make_archived 941 2026-07-12    # window starts 2026-07-13
    out="$("$GATHER" --columns now --now 2026-07-19 --velocity-window 7 --project)"
    assert_contains "completion outside the window is ignored" \
        "PROJECTION:1|none|insufficient_data|0|unweighted_task_counts" "$out"

    # Same completion, one day later: inside the window, so it does produce a
    # rate — but one data point must NOT be enough to forecast a date.
    make_archived 941 2026-07-13
    out="$("$GATHER" --columns now --now 2026-07-19 --velocity-window 7 --project)"
    assert_contains "in-window completion produces a rate" "VELOCITY:1|1|1|1|Mon" "$out"
    assert_contains "one data point is below the confidence floor" \
        "PROJECTION:1|none|insufficient_data|1|unweighted_task_counts" "$out"

    # Widening the window widens the denominator.
    out="$("$GATHER" --columns now --now 2026-07-19 --velocity-window 14)"
    assert_contains "wider window observes each weekday twice" \
        "VELOCITY:1|2|1|0.5|Mon" "$out"
}

test_projection_floor() {
    echo "=== projection: confidence floor is exactly 10 completions ==="
    setup_tree
    make_task 945 now 10
    local i out
    for i in $(seq 1 9); do make_archived "94$i" 2026-07-13; done

    out="$("$GATHER" --columns now --now 2026-07-19 --velocity-window 7 --project)"
    assert_contains "9 completions -> still refused" \
        "PROJECTION:1|none|insufficient_data|9|unweighted_task_counts" "$out"

    make_archived 9410 2026-07-13   # 10th completion
    out="$("$GATHER" --columns now --now 2026-07-19 --velocity-window 7 --project)"
    assert_contains "10 completions -> projection allowed" \
        "PROJECTION:1|2026-07-20|1|10|unweighted_task_counts" "$out"
    assert_contains "basis count is reported for confidence" "|10|" "$out"
}

test_projection_optin() {
    echo "=== projection is opt-in, never a default output ==="
    setup_tree
    make_task 946 now 10
    local i out
    for i in $(seq 1 12); do make_archived "95$i" 2026-07-13; done

    out="$("$GATHER" --columns now --now 2026-07-19 --velocity-window 7)"
    assert_contains "velocity is a default output" "VELOCITY:1|1|12|12|Mon" "$out"
    assert_not_contains "projection is withheld by default" "PROJECTION" "$out"

    out="$("$GATHER" --columns now --now 2026-07-19 --velocity-window 7 --project)"
    assert_contains "projection appears only when requested" "PROJECTION:1|" "$out"
    assert_contains "and always names its limitation" "unweighted_task_counts" "$out"
}

test_projection_bound() {
    echo "=== projection: the walk is bounded, not unbounded ==="
    setup_tree
    # flat model over 3650 days with 12 completions (above the floor): total
    # throughput across the whole bound is 12 items. One item finishes deep
    # inside the bound; twenty cannot finish within it at all.
    local i
    for i in $(seq 1 12); do make_archived "96$i" 2026-07-13; done

    make_task 970 now 10
    local out
    out="$("$GATHER" --columns now --now 2026-07-19 --velocity-window 3650 --velocity-model flat --project)"
    assert_not_contains "1 item finishes inside the bound" "insufficient_data" "$out"
    assert_contains "…and is projected far out" "PROJECTION:1|" "$out"

    local children=""
    for i in $(seq 1 20); do children="${children}t970_${i}, "; done
    make_task 971 now 20 "children_to_implement: [${children%, }]"
    out="$("$GATHER" --columns now --now 2026-07-19 --velocity-window 3650 --velocity-model flat --project)"
    assert_contains "21 items exceed the bound -> insufficient_data" \
        "PROJECTION:21|none|insufficient_data|12|unweighted_task_counts" "$out"
}

# --- Test: board-parity edges that a naive re-derivation gets wrong ---------

test_malformed_frontmatter() {
    echo "=== malformed YAML: hidden like the board hides it, never fatal ==="
    setup_tree
    printf -- '---\nstatus: Ready\nboardcol: now\nboardidx: 10\nbad: [unclosed\n---\n\nb\n' \
        > "$TASK_DIR/t400_bad.md"
    make_task 401 now 20

    local out rc
    out="$("$GATHER" --columns now 2>/dev/null)"; rc=$?
    assert_exit_zero_rc "unparseable task does not abort the run" "$rc"
    assert_eq_trim "unparseable task is dropped, healthy one kept" "401" "$(task_ids "$out")"
    assert_contains "protocol output still produced" "COLUMN:now|" "$out"
}

test_empty_board_config() {
    echo "=== a deliberately empty board stays empty (no invented defaults) ==="
    setup_tree
    board_config '{"columns":[],"column_order":[]}'
    make_task 410 now 10

    local out
    out="$("$GATHER" --list-columns)"
    assert_eq_trim "no columns invented for an empty board" "" "$out"
    assert_not_contains "stock Now column not resurrected" "COLUMN:now" "$out"
    assert_not_contains "stock Backlog column not resurrected" "COLUMN:backlog" "$out"

    out="$("$GATHER" --columns now)"
    assert_eq_trim "and its ids are not selectable" "ERROR:unknown_column:now" "$out"
}

test_quoted_boardidx() {
    echo "=== quoted boardidx sorts numerically, and mixes without crashing ==="
    setup_tree
    make_named "t420_ten.md" now '"10"'
    make_named "t421_two.md" now '"2"'

    local out
    out="$("$GATHER" --columns now)"
    # Sorting the raw YAML would order "10" before "2" lexically.
    assert_eq_trim "quoted indexes ordered numerically" "421 420" "$(task_ids "$out")"

    # Mixing a quoted value with a plain int used to raise TypeError in the board.
    make_named "t422_five.md" now 5
    out="$("$GATHER" --columns now)"
    assert_eq_trim "quoted and int indexes sort together" "421 422 420" "$(task_ids "$out")"

    out="$("$PYTHON" "$EQUIV" "$PROJECT_DIR" 2>&1)"
    assert_eq_trim "board agrees on quoted/mixed indexes" "EQUIV_OK" "$out"
}

test_history_follows_task_dir() {
    echo "=== completion history comes from the same tree as membership ==="
    # A foreign ./aitasks archive next to a non-'aitasks' task tree must not be
    # mistaken for this project's history.
    local tmp
    tmp="$(mktemp -d "${TMPDIR:-/tmp}/test_workrep_XXXXXX")"
    CLEANUP_DIRS+=("$tmp")
    mkdir -p "$tmp/mytasks/metadata" "$tmp/mytasks/archived" "$tmp/aitasks/archived"
    export TASK_DIR="$tmp/mytasks"
    board_config "$DEFAULT_BOARD"
    make_task 430 now 10

    local i
    for i in $(seq 1 5); do
        printf -- '---\nstatus: Done\ncompleted_at: 2026-07-13 12:00\n---\n\nx\n' \
            > "$tmp/aitasks/archived/t44${i}_foreign.md"
    done

    local out
    out="$(cd "$tmp" && "$GATHER" --columns now --now 2026-07-19 --velocity-window 7)"
    assert_contains "foreign archive contributes nothing" "VELOCITY:1|1|0|0|Mon" "$out"

    # The real tree's own archive is what counts.
    for i in $(seq 1 3); do
        printf -- '---\nstatus: Done\ncompleted_at: 2026-07-13 12:00\n---\n\nx\n' \
            > "$TASK_DIR/archived/t45${i}_mine.md"
    done
    out="$(cd "$tmp" && "$GATHER" --columns now --now 2026-07-19 --velocity-window 7)"
    assert_contains "own archive is counted" "VELOCITY:1|1|3|3|Mon" "$out"
}

# --- Test: the velocity-model seam ------------------------------------------

test_model_seam() {
    echo "=== velocity model seam: swapping the model changes nothing else ==="
    setup_tree
    make_task 970 now 10
    make_task 971 next 20
    make_archived 972 2026-07-13

    local dow flat dow_rows flat_rows
    dow="$("$GATHER" --columns now,next --now 2026-07-19 --velocity-window 7)"
    flat="$("$GATHER" --columns now,next --now 2026-07-19 --velocity-window 7 --velocity-model flat)"

    dow_rows="$(printf '%s\n' "$dow" | grep -E '^(COLUMN|TASK):')"
    flat_rows="$(printf '%s\n' "$flat" | grep -E '^(COLUMN|TASK):')"
    assert_eq "column/task output is model-independent" "$dow_rows" "$flat_rows"

    assert_eq_trim "flat model emits a single bucket" "1" \
        "$(printf '%s\n' "$flat" | grep -c '^VELOCITY:')"
    assert_contains "flat bucket is generic, not weekday-shaped" \
        "VELOCITY:all|7|1|0.14|All days" "$flat"
    assert_contains "model id echoed (dow)" "VELOCITY_MODEL:dow|" "$dow"
    assert_contains "model id echoed (flat)" "VELOCITY_MODEL:flat|" "$flat"

    assert_exit_nonzero "unknown model rejected" \
        "$GATHER" --columns now --velocity-model nope
    local err
    err="$("$GATHER" --columns now --velocity-model nope 2>&1 >/dev/null)"
    assert_contains "unknown model lists the registered ids" "dow, flat" "$err"

    assert_exit_nonzero "non-positive window rejected" \
        "$GATHER" --columns now --velocity-window 0
    assert_exit_nonzero "non-date --now rejected" \
        "$GATHER" --columns now --now "2026-07-19 10:45"
}

# --- Test: board equivalence (independent ground truth) ---------------------

test_board_equivalence() {
    echo "=== board equivalence: TaskManager.get_column_tasks is the oracle ==="
    setup_tree
    board_config '{"columns":[{"id":"now","title":"Now"},{"id":"next","title":"Next"}],"column_order":["next","now"]}'

    make_task 980 now 20
    make_task 981 now 10
    # Tie group: filename order (t10 < t31 < t9) contradicts numeric id order,
    # so agreement here means the board applies the same key, not that both
    # happened to read the directory the same way.
    make_named "t9_tie.md" now 30
    make_named "t10_tie.md" now 30
    make_named "t31_tie.md" now 30
    make_task 982 next 5
    make_task 983 - -                        # -> unordered
    make_task 984 now 40 'status: Done'      # no status filter
    printf -- '---\nboardcol: now\nboardidx: 50\n---\n\nstub\n' \
        > "$TASK_DIR/t985_demo.md"           # phantom stub
    mkdir -p "$TASK_DIR/t980"
    make_named "t980/t980_1_child.md" now 1  # children are not board cards
    make_archived 986 2026-07-13             # archived is not a board card

    local out
    out="$("$PYTHON" "$EQUIV" "$PROJECT_DIR" 2>&1)"
    assert_eq_trim "gatherer matches the board exactly" "EQUIV_OK" "$out"

    # EQUIV_OK alone only proves the two agree. Pinning the gatherer against the
    # specified order as well means the board is pinned to it transitively.
    out="$("$GATHER" --columns unordered,next,now)"
    assert_eq_trim "agreed order is the specified one" \
        "983 982 981 980 10 31 9 984" "$(task_ids "$out")"
}

# --- Run -------------------------------------------------------------------

test_ordering
test_tie_break
test_unordered
test_task_selection
test_fail_closed
test_delimiter_argv
test_delimiter_col_id
test_delimiter_enums
test_delimiter_free_text
test_delimiter_newline
test_children_types
test_remaining_and_phantom
test_no_tasks
test_velocity_buckets
test_projection_worked_example
test_projection_edges
test_projection_floor
test_projection_optin
test_projection_bound
test_malformed_frontmatter
test_empty_board_config
test_quoted_boardidx
test_history_follows_task_dir
test_model_seam
test_board_equivalence

for dir in "${CLEANUP_DIRS[@]}"; do
    rm -rf "$dir"
done

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
if [[ "$FAIL" -gt 0 ]]; then
    exit 1
else
    echo "All tests PASSED"
fi
