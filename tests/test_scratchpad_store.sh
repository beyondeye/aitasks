#!/usr/bin/env bash
# test_scratchpad_store.sh - Tests for the scratchpad notes-store helper
# (t2073_1).
#
# The helper's job is lifecycle safety more than storage: an open or save racing
# archival must never resurrect a pruned store, a malformed root must be refused
# before anything is touched, and the identity key must not change when the
# store is created. The races are driven deterministically through the helper's
# test seam (AITASK_SCRATCHPAD_PAUSE_FIFO parks a verb INSIDE its lock), and the
# guards that make them safe are each shown to matter with an isolated mutant
# copy of the helper that lacks them (negative controls).
#
# Everything is scoped to a temp store via AITASK_SCRATCHPAD_DIR and a temp task
# dir via TASK_DIR, so this suite never touches the repo's real
# .aitask-scratchpad/. Background verbs write to files; every assertion runs in
# the main shell.
#
# Run: bash tests/test_scratchpad_store.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

H="$PROJECT_DIR/.aitask-scripts/aitask_scratchpad_store.sh"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/ait_scratchpad_XXXXXX")"
TMP="$(cd "$TMP" && pwd -P)"
BG_PIDS=()
cleanup() {
    local p
    for p in "${BG_PIDS[@]:-}"; do
        [[ -n "$p" ]] && kill "$p" 2>/dev/null
    done
    exec 7>&- 2>/dev/null
    rm -rf "$TMP"
}
trap cleanup EXIT

export TASK_DIR="$TMP/aitasks"
export AITASK_SCRATCHPAD_DIR="$TMP/pad"
unset AITASK_SCRATCHPAD_PAUSE_FIFO
FIFO="$TMP/pause.fifo"

# --- helpers ----------------------------------------------------------------

store_of() { printf '%s/%s' "$AITASK_SCRATCHPAD_DIR" "$1"; }
lockd_of() { printf '%s/.locks/%s.lockd' "$AITASK_SCRATCHPAD_DIR" "$1"; }

task_path_of() {   # <id> [dir]
    local id="$1" dir="${2:-$TASK_DIR}"
    if [[ "$id" == *_* ]]; then
        local p="${id%%_*}" c="${id#*_}"
        printf '%s/t%s/t%s_%s_scratch_test.md' "$dir" "$p" "$p" "$c"
    else
        printf '%s/t%s_scratch_test.md' "$dir" "$id"
    fi
}
mk_task() {
    local f; f="$(task_path_of "$1")"
    mkdir -p "$(dirname "$f")"
    printf -- '---\nstatus: Implementing\n---\n' > "$f"
}
# Archive-style move: the task file leaves the active dir, as aitask_archive.sh
# does before it prunes.
archive_task() {
    local f dest; f="$(task_path_of "$1")"
    dest="$(task_path_of "$1" "$TASK_DIR/archived")"
    mkdir -p "$(dirname "$dest")"
    mv "$f" "$dest"
}

# Fresh store, fresh task dir, fresh fifo. fd 7 holds the fifo open read-write
# so releasing a parked verb is a non-blocking write.
reset_all() {
    rm -rf "$AITASK_SCRATCHPAD_DIR" "$TASK_DIR"
    mkdir -p "$TASK_DIR/archived"
    exec 7>&- 2>/dev/null
    rm -f "$FIFO" "$FIFO.reached"
    mkfifo "$FIFO"
    exec 7<>"$FIFO"
}

# Wait (bounded, 5 s) until a seam-enabled verb reports it is parked.
wait_reached() {
    local _
    for _ in $(seq 1 100); do
        [[ -s "$FIFO.reached" ]] && return 0
        sleep 0.05
    done
    return 1
}
release_pause() { echo go >&7; }

# Wait (bounded, 10 s) for a background pid to exit; 1 if it is still running.
wait_done() {
    local pid="$1" _
    for _ in $(seq 1 200); do
        kill -0 "$pid" 2>/dev/null || { wait "$pid" 2>/dev/null; return 0; }
        sleep 0.05
    done
    return 1
}
is_running() { kill -0 "$1" 2>/dev/null; }

# Hold a task's lifecycle lock with a LIVE pid so registry_lock.sh refuses to
# steal it. Sets HOLDER_PID.
hold_lock() {
    local lockd; lockd="$(lockd_of "$1")"
    mkdir -p "$lockd"
    sleep 30 &
    HOLDER_PID=$!
    BG_PIDS+=("$HOLDER_PID")
    echo "$HOLDER_PID" > "$lockd/pid"
    echo "held-by-test" > "$lockd/owner"
}
release_held_lock() {
    kill "$HOLDER_PID" 2>/dev/null || true
    wait "$HOLDER_PID" 2>/dev/null || true
    rm -rf "$(lockd_of "$1")"
}

# Build an isolated mutant copy of the helper: inside function <func>, the line
# equal to <line> is replaced by <replacement> (awk -v expands \n). The copy gets
# a `lib` symlink so it sources the real libraries. Sets MUTANT; the caller must
# assert MUTANT_CHANGED=yes before trusting the control.
make_mutant() {   # <name> <func> <line> <replacement>
    local dir="$TMP/mutant_$1"
    mkdir -p "$dir"
    ln -sfn "$PROJECT_DIR/.aitask-scripts/lib" "$dir/lib"
    MUTANT="$dir/aitask_scratchpad_store.sh"
    awk -v fn="$2" -v target="$3" -v repl="$4" '
        $0 == fn "() {" { inside = 1 }
        inside && $0 == target { print repl; next }
        { print }
        inside && $0 == "}" { inside = 0 }
    ' "$H" > "$MUTANT"
    chmod +x "$MUTANT"
    if cmp -s "$H" "$MUTANT"; then MUTANT_CHANGED=no; else MUTANT_CHANGED=yes; fi
}

# --- Test 1: open --------------------------------------------------------------

echo "=== Test 1: open refuses an inactive task, creates the store for an active one ==="
reset_all
out="$("$H" open 42 2>&1)"; rc=$?
assert_eq "open without a task file exits 0" "0" "$rc"
assert_eq "open without a task file -> NO_TASK" "NO_TASK" "$out"
assert_dir_not_exists "NO_TASK created no store" "$(store_of 42)"

mk_task 42
out="$("$H" open 42 2>&1)"; rc=$?
assert_eq "open of an active task exits 0" "0" "$rc"
assert_eq "open prints the canonical notes path" "OPENED:$TMP/pad/42/notes.md" "$out"
assert_dir_exists "store dir created" "$(store_of 42)"
assert_file_exists ".holder.lock created" "$(store_of 42)/.holder.lock"
assert_file_not_exists "open writes no notes.md" "$(store_of 42)/notes.md"

mk_task 10_1
out="$("$H" open t10_1 2>&1)"
assert_eq "child id (t-prefixed) resolves its child task file" \
    "OPENED:$TMP/pad/10_1/notes.md" "$out"
out="$("$H" open 10_2 2>&1)"
assert_eq "a sibling child without a task file -> NO_TASK" "NO_TASK" "$out"

# --- Test 2: save round trip ------------------------------------------------------

echo "=== Test 2: save round trip and empty save ==="
reset_all
mk_task 42
"$H" open 42 >/dev/null
printf 'line one\n  indented | pipe\n\n' > "$TMP/in.txt"
out="$("$H" save 42 < "$TMP/in.txt" 2>&1)"; rc=$?
assert_eq "save exits 0" "0" "$rc"
assert_eq "SAVED:<bytes> equals the input size" "SAVED:$(wc -c < "$TMP/in.txt" | tr -d ' ')" "$out"
if cmp -s "$TMP/in.txt" "$(store_of 42)/notes.md"; then same=yes; else same=no; fi
assert_eq "notes.md is byte-identical to stdin (trailing newlines kept)" "yes" "$same"

out="$(printf '' | "$H" save 42 2>&1)"
assert_eq "empty save -> SAVED:empty" "SAVED:empty" "$out"
assert_file_not_exists "empty save removed notes.md" "$(store_of 42)/notes.md"
assert_dir_exists "empty save kept the store dir" "$(store_of 42)"

# --- Test 2b: a failed stdin read never commits ------------------------------------

echo "=== Test 2b: a failed stdin read exits 4 and leaves existing notes alone ==="
reset_all
mk_task 42
"$H" open 42 >/dev/null
echo keep | "$H" save 42 >/dev/null
# A directory as stdin: open() succeeds, cat's read fails with EISDIR.
out="$("$H" save 42 < "$TMP" 2>/dev/null)"; rc=$?
assert_eq "failed read -> save exits 4" "4" "$rc"
assert_not_contains "failed read prints no SAVED response" "SAVED" "$out"
assert_eq "failed read left the existing notes unchanged" "keep" "$(cat "$(store_of 42)/notes.md" 2>/dev/null)"

echo "=== Test 2b control: with the sentinel after ';' the failed read is masked ==="
make_mutant masked_read cmd_save '    if ! buf="$(cat && printf x)"; then' '    if ! buf="$(cat; printf x)"; then'
assert_eq "control mutant differs from the helper" "yes" "$MUTANT_CHANGED"
out="$("$MUTANT" save 42 < "$TMP" 2>/dev/null)"; rc=$?
assert_eq "control: the masked read reports success" "0:SAVED:empty" "$rc:$out"
assert_file_not_exists "control: the masked read deleted the notes" "$(store_of 42)/notes.md"

# --- Test 3: save never creates the store ------------------------------------------

echo "=== Test 3: save before open -> ABSENT ==="
reset_all
mk_task 42
out="$(echo text | "$H" save 42 2>&1)"; rc=$?
assert_eq "save without a store exits 0" "0" "$rc"
assert_eq "save without a store -> ABSENT" "ABSENT" "$out"
assert_dir_not_exists "ABSENT created no store" "$(store_of 42)"

# --- Test 4: malformed ids --------------------------------------------------------

echo "=== Test 4: malformed ids exit 2 for every verb ==="
reset_all
for verb in open save path prune; do
    for id in ../evil 1x; do
        "$H" "$verb" "$id" </dev/null >/dev/null 2>&1; rc=$?
        assert_eq "$verb '$id' exits 2" "2" "$rc"
    done
done
assert_dir_not_exists "malformed ids created no root" "$AITASK_SCRATCHPAD_DIR"

# --- Test 5: own-root guard ---------------------------------------------------------

echo "=== Test 5: prune refuses a symlinked store ==="
reset_all
mkdir -p "$AITASK_SCRATCHPAD_DIR" "$TMP/outside"
echo precious > "$TMP/outside/keep.txt"
ln -s "$TMP/outside" "$(store_of 9999)"
"$H" prune 9999 >/dev/null 2>&1; rc=$?
assert_eq "dir-symlinked store -> prune exits 4" "4" "$rc"
assert_file_exists "outside file untouched" "$TMP/outside/keep.txt"
rm -f "$(store_of 9999)"
ln -s "$TMP/outside/keep.txt" "$(store_of 9998)"
"$H" prune 9998 >/dev/null 2>&1; rc=$?
assert_eq "file-symlinked store -> prune exits 4" "4" "$rc"
assert_eq "symlink target file untouched" "precious" "$(cat "$TMP/outside/keep.txt")"
rm -f "$(store_of 9998)"

# --- Test 6: externally held lock ---------------------------------------------------

echo "=== Test 6: a held lifecycle lock -> prune LOCK_BUSY, nothing deleted ==="
reset_all
mk_task 42
"$H" open 42 >/dev/null
echo keep | "$H" save 42 >/dev/null
hold_lock 42
out="$("$H" prune 42 2>&1)"; rc=$?
assert_eq "contended prune exits 3" "3" "$rc"
assert_eq "contended prune -> LOCK_BUSY" "LOCK_BUSY" "$out"
assert_eq "contended prune deleted nothing" "keep" "$(cat "$(store_of 42)/notes.md" 2>/dev/null)"
assert_file_exists "contended prune kept .holder.lock" "$(store_of 42)/.holder.lock"
release_held_lock 42

# --- Test 7: saves are serialized ---------------------------------------------------

# Save A parks inside the lock; save B must not land until A releases it.
run_save_race() {   # <helper> -> sets RACE_B_WHILE_PARKED, RACE_FINAL
    local helper="$1" a b
    reset_all
    mk_task 42
    "$helper" open 42 >/dev/null
    echo AAA | AITASK_SCRATCHPAD_PAUSE_FIFO="$FIFO" "$helper" save 42 \
        >"$TMP/a.out" 2>"$TMP/a.err" &
    a=$!; BG_PIDS+=("$a")
    if ! wait_reached; then RACE_B_WHILE_PARKED=never-parked; RACE_FINAL=""; kill "$a"; return; fi
    echo BBB | "$helper" save 42 >"$TMP/b.out" 2>"$TMP/b.err" &
    b=$!; BG_PIDS+=("$b")
    sleep 0.5
    if is_running "$b"; then RACE_B_WHILE_PARKED=waiting; else RACE_B_WHILE_PARKED=finished; fi
    release_pause
    wait_done "$a"; wait_done "$b"
    RACE_FINAL="$(cat "$(store_of 42)/notes.md" 2>/dev/null)"
}

echo "=== Test 7: concurrent saves are serialized ==="
run_save_race "$H"
assert_eq "save B waits while save A holds the lock" "waiting" "$RACE_B_WHILE_PARKED"
assert_eq "save A landed" "SAVED:4" "$(cat "$TMP/a.out")"
assert_eq "save B landed" "SAVED:4" "$(cat "$TMP/b.out")"
assert_eq "B landed after A (final content is B)" "BBB" "$RACE_FINAL"

echo "=== Test 7 control: without save's lock, B lands while A is parked ==="
make_mutant nolock_save cmd_save "    lock_or_busy" "    :"
assert_eq "control mutant differs from the helper" "yes" "$MUTANT_CHANGED"
run_save_race "$MUTANT"
assert_eq "control: save B finished while A was parked" "finished" "$RACE_B_WHILE_PARKED"
assert_eq "control: A's late write clobbered B (lost update)" "AAA" "$RACE_FINAL"

# --- Test 8: open vs prune on an existing store -------------------------------------

echo "=== Test 8: prune waits for a parked open, then removes the store ==="
reset_all
mk_task 42
"$H" open 42 >/dev/null
echo old | "$H" save 42 >/dev/null
rm -f "$FIFO.reached"
AITASK_SCRATCHPAD_PAUSE_FIFO="$FIFO" "$H" open 42 >"$TMP/a.out" 2>"$TMP/a.err" &
a=$!; BG_PIDS+=("$a")
wait_reached; assert_eq "open parked after its task check" "open:after_task_check" "$(cat "$FIFO.reached")"
archive_task 42
"$H" prune 42 >"$TMP/p.out" 2>"$TMP/p.err" &
p=$!; BG_PIDS+=("$p")
sleep 0.5
if is_running "$p"; then st=waiting; else st=finished; fi
assert_eq "prune waits for the parked open" "waiting" "$st"
release_pause
wait_done "$a"; wait_done "$p"
assert_eq "parked open completed" "OPENED:$TMP/pad/42/notes.md" "$(cat "$TMP/a.out")"
assert_eq "prune then pruned the store" "PRUNED:42" "$(cat "$TMP/p.out")"
assert_dir_not_exists "nothing survives open-vs-prune" "$(store_of 42)"

# --- Test 9: the FIRST open vs archive --------------------------------------------

# No root at all: open parks between its task check and its mkdir, so the store
# does not exist yet when prune runs. Prune must still wait for the lock.
run_first_open_race() {   # <prune helper> -> sets FIRST_PRUNE_OUT
    local helper="$1" a p
    reset_all
    mk_task 42
    AITASK_SCRATCHPAD_PAUSE_FIFO="$FIFO" "$H" open 42 >"$TMP/a.out" 2>"$TMP/a.err" &
    a=$!; BG_PIDS+=("$a")
    wait_reached || { kill "$a"; FIRST_PRUNE_OUT=never-parked; return; }
    archive_task 42
    "$helper" prune 42 >"$TMP/p.out" 2>"$TMP/p.err" &
    p=$!; BG_PIDS+=("$p")
    sleep 0.5
    release_pause
    wait_done "$a"; wait_done "$p"
    FIRST_PRUNE_OUT="$(cat "$TMP/p.out")"
}

echo "=== Test 9: prune removes a store created by a racing first open ==="
run_first_open_race "$H"
assert_eq "first open completed" "OPENED:$TMP/pad/42/notes.md" "$(cat "$TMP/a.out")"
assert_eq "prune waited and pruned the fresh store" "PRUNED:42" "$FIRST_PRUNE_OUT"
assert_dir_not_exists "no store survives the first-open race" "$(store_of 42)"

echo "=== Test 9 control: an absence check before the lock leaves the store behind ==="
make_mutant early_absent cmd_prune "    lock_or_busy" \
    '    [[ -d "$STORE_DIR" ]] || { echo "PRUNED:absent"; return 0; }\n    lock_or_busy'
assert_eq "control mutant differs from the helper" "yes" "$MUTANT_CHANGED"
run_first_open_race "$MUTANT"
assert_eq "control: early check reports absent" "PRUNED:absent" "$FIRST_PRUNE_OUT"
assert_dir_exists "control: the archived task's store survived" "$(store_of 42)"

# --- Test 10: save vs prune ---------------------------------------------------------

echo "=== Test 10: a parked save lands, prune removes it, the next save refuses ==="
reset_all
mk_task 42
"$H" open 42 >/dev/null
echo INFLIGHT | AITASK_SCRATCHPAD_PAUSE_FIFO="$FIFO" "$H" save 42 >"$TMP/a.out" 2>"$TMP/a.err" &
a=$!; BG_PIDS+=("$a")
wait_reached; assert_eq "save parked after its existence check" "save:after_exists_check" "$(cat "$FIFO.reached")"
archive_task 42
"$H" prune 42 >"$TMP/p.out" 2>"$TMP/p.err" &
p=$!; BG_PIDS+=("$p")
sleep 0.5
if is_running "$p"; then st=waiting; else st=finished; fi
assert_eq "prune waits for the parked save" "waiting" "$st"
release_pause
wait_done "$a"; wait_done "$p"
assert_eq "parked save landed" "SAVED:9" "$(cat "$TMP/a.out")"
assert_eq "prune removed it afterwards" "PRUNED:42" "$(cat "$TMP/p.out")"
assert_dir_not_exists "store gone after save-vs-prune" "$(store_of 42)"
out="$(echo LATE | "$H" save 42 2>&1)"
assert_eq "a later save -> ARCHIVED" "ARCHIVED" "$out"
assert_dir_not_exists "the later save recreated nothing" "$(store_of 42)"

# --- Test 11: prune first, then save -------------------------------------------------

echo "=== Test 11: prune first, then a seam-enabled save -> ARCHIVED, never parks ==="
reset_all
mk_task 42
"$H" open 42 >/dev/null
archive_task 42
"$H" prune 42 >/dev/null
out="$(echo X | AITASK_SCRATCHPAD_PAUSE_FIFO="$FIFO" "$H" save 42 2>&1)"
assert_eq "save after prune -> ARCHIVED" "ARCHIVED" "$out"
assert_file_not_exists "save refused before its pause point" "$FIFO.reached"
assert_dir_not_exists "no store recreated" "$(store_of 42)"

# --- Test 12: surviving dir ---------------------------------------------------------

echo "=== Test 12: archived task with a surviving store dir -> save refuses ==="
reset_all
mk_task 42
"$H" open 42 >/dev/null
echo keep | "$H" save 42 >/dev/null
archive_task 42
out="$(echo new | "$H" save 42 2>&1)"
assert_eq "save on a surviving dir of an archived task -> ARCHIVED" "ARCHIVED" "$out"
assert_eq "notes.md unchanged" "keep" "$(cat "$(store_of 42)/notes.md")"

# --- Test 13: holder vs prune ---------------------------------------------------------

echo "=== Test 13: after prune the holder file cannot be opened without O_CREAT ==="
reset_all
mk_task 42
"$H" open 42 >/dev/null
holder="$(store_of 42)/.holder.lock"
python3 -c 'import os,sys; os.close(os.open(sys.argv[1], os.O_RDWR))' "$holder" 2>/dev/null; rc=$?
assert_eq "precondition: the holder opens O_RDWR while the store exists" "0" "$rc"
archive_task 42
"$H" prune 42 >/dev/null
err="$(python3 -c 'import os,sys; os.open(sys.argv[1], os.O_RDWR)' "$holder" 2>&1)"; rc=$?
assert_exit_nonzero_rc "O_RDWR open of the pruned holder fails" "$rc"
assert_contains "it fails as FileNotFoundError" "FileNotFoundError" "$err"
assert_dir_not_exists "the failed open recreated nothing" "$(store_of 42)"

# --- Test 14: path is stable across creation --------------------------------------------

check_path_stable() {   # <label> <root> <expected key>
    local label="$1" before after opened
    before="$(AITASK_SCRATCHPAD_DIR="$2" "$H" path 42 2>&1)"
    opened="$(AITASK_SCRATCHPAD_DIR="$2" "$H" open 42 2>&1)"
    after="$(AITASK_SCRATCHPAD_DIR="$2" "$H" path 42 2>&1)"
    assert_eq "$label: key before creation" "$3" "$before"
    assert_eq "$label: key unchanged after creation" "$before" "$after"
    assert_eq "$label: OPENED equals path + /notes.md" "OPENED:$before/notes.md" "$opened"
}

echo "=== Test 14: path is identical before and after the store exists ==="
reset_all
mk_task 42
mkdir -p "$TMP/relcase"
pushd "$TMP/relcase" >/dev/null || exit 1
check_path_stable "relative root" "rel/pad" "$TMP/relcase/rel/pad/42"
popd >/dev/null || exit 1
check_path_stable "missing absolute root" "$TMP/abs/deep/pad" "$TMP/abs/deep/pad/42"
mkdir -p "$TMP/realdir"
ln -s "$TMP/realdir" "$TMP/linkdir"
check_path_stable "symlinked ancestor" "$TMP/linkdir/pad" "$TMP/realdir/pad/42"
check_path_stable "./ and // segments" "$TMP/dots/./x//pad/" "$TMP/dots/x/pad/42"
AITASK_SCRATCHPAD_DIR="$TMP/pad/../x" "$H" path 42 >/dev/null 2>&1; rc=$?
assert_eq "a '..' segment in the root -> path exits 2" "2" "$rc"

# --- Test 15: prune on a never-created root ------------------------------------------------

echo "=== Test 15: prune of a never-created root creates nothing ==="
out="$(AITASK_SCRATCHPAD_DIR="$TMP/never_created" "$H" prune 7777 2>&1)"; rc=$?
assert_eq "prune of a missing root exits 0" "0" "$rc"
assert_eq "prune of a missing root -> PRUNED:absent" "PRUNED:absent" "$out"
assert_dir_not_exists "the root is still absent" "$TMP/never_created"

# --- Test 16: invalid root refused before any mutation -------------------------------------

snapshot_c16() {
    find "$TMP/c16" -print | LC_ALL=C sort
    find "$TMP/c16" -type f -exec cksum {} + | LC_ALL=C sort
}

echo "=== Test 16: a '..' root is refused by every verb before anything changes ==="
reset_all
mk_task 42
mkdir -p "$TMP/c16/pad" "$TMP/c16/other/42"
echo victim > "$TMP/c16/other/42/notes.md"
: > "$TMP/c16/other/42/.holder.lock"
before="$(snapshot_c16)"
pushd "$TMP/c16" >/dev/null || exit 1
for root in "$TMP/c16/pad/../other" "pad/../other"; do
    for verb in open save path prune; do
        out="$(echo text | AITASK_SCRATCHPAD_DIR="$root" "$H" "$verb" 42 2>/dev/null)"; rc=$?
        assert_eq "$verb with root '$root' exits 2" "2" "$rc"
        assert_eq "$verb with root '$root' prints nothing on stdout" "" "$out"
    done
done
popd >/dev/null || exit 1
assert_eq "the tree is byte-identical after every refused verb" "$before" "$(snapshot_c16)"
assert_dir_not_exists "no .locks created under the resolved root" "$TMP/c16/other/.locks"

# --- Test 17: canonicalization failure propagates -------------------------------------------

echo "=== Test 17: a failing canonicalization exits 4 before any mutation ==="
reset_all
mk_task 42
make_mutant nokey _canonical_key '    local abs rest seg prefix="" canon out i=0' '    return 4'
assert_eq "failure-injection mutant differs from the helper" "yes" "$MUTANT_CHANGED"
out="$("$MUTANT" open 42 2>/dev/null)"; rc=$?
assert_eq "open exits 4 when the key cannot be computed" "4" "$rc"
assert_not_contains "open prints no OPENED line" "OPENED:" "$out"
assert_dir_not_exists "open created no root (no .locks, no store)" "$AITASK_SCRATCHPAD_DIR"
out="$("$MUTANT" path 42 2>/dev/null)"; rc=$?
assert_eq "path exits 4 when the key cannot be computed" "4" "$rc"
assert_eq "path prints nothing" "" "$out"

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -gt 0 ]] && exit 1
echo "All tests PASSED"
