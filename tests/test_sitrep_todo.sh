#!/usr/bin/env bash
# test_sitrep_todo.sh - Tests for the sitrep store writer (t2175_1).
#
# The store is a source of truth, so most of this suite is about what survives:
# concurrent writers, a writer killed inside its lock, a damaged or deleted file,
# an interrupted restore, and ids across recovery. Crash points are driven
# deterministically through the helper's test seam (AITASK_SITREP_PAUSE_FIFO
# parks a verb INSIDE its lock), then the parked writer is SIGKILLed.
#
# Everything is scoped to a temp store via AITASK_SITREP_DIR, so this suite
# never touches the repo's real .aitask-sitrep/. Background verbs write to
# files; every assertion runs in the main shell.
#
# Run: bash tests/test_sitrep_todo.sh

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

H="$PROJECT_DIR/.aitask-scripts/aitask_sitrep_todo.sh"
CORE="$PROJECT_DIR/.aitask-scripts/lib/sitrep_todo.py"
FIXTURE="$PROJECT_DIR/tests/fixtures/sitrep"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/ait_sitrep_XXXXXX")"
TMP="$(cd "$TMP" && pwd -P)"
BG_PIDS=()
cleanup() {
    local p
    for p in "${BG_PIDS[@]:-}"; do
        [[ -n "$p" ]] && kill -9 "$p" 2>/dev/null
    done
    exec 7>&- 2>/dev/null
    chmod -R u+w "$TMP" 2>/dev/null
    rm -rf "$TMP"
}
trap cleanup EXIT

export AITASK_SITREP_DIR="$TMP/store"
export AITASK_SITREP_NOW="2026-11-01T10:00:00Z"
unset AITASK_SITREP_PAUSE_FIFO AITASK_SITREP_LOCK_TIMEOUT
FIFO="$TMP/pause.fifo"
S="$AITASK_SITREP_DIR"

TODO_BANNER="$(python3 -c "import sys; sys.path.insert(0, sys.argv[1]); import sitrep_todo; print(sitrep_todo.TODO_BANNER)" "$PROJECT_DIR/.aitask-scripts/lib")"
QA_BANNER="$(python3 -c "import sys; sys.path.insert(0, sys.argv[1]); import sitrep_todo; print(sitrep_todo.QA_BANNER)" "$PROJECT_DIR/.aitask-scripts/lib")"

# --- helpers ----------------------------------------------------------------

# run <stdin-text|-> <args...>: sets OUT, ERR, RC. "-" means no stdin.
run() {
    local input="$1"
    shift
    RC=0
    if [[ "$input" == "-" ]]; then
        OUT="$("$H" "$@" </dev/null 2>"$TMP/err")" || RC=$?
    else
        OUT="$(printf '%s' "$input" | "$H" "$@" 2>"$TMP/err")" || RC=$?
    fi
    ERR="$(cat "$TMP/err")"
}

reset_store() {
    chmod -R u+w "$S" 2>/dev/null
    rm -rf "$S"
    exec 7>&- 2>/dev/null
    rm -f "$FIFO" "$FIFO.reached"
    mkfifo "$FIFO"
    exec 7<>"$FIFO"
}

# Wait (bounded, 10 s) until a seam-enabled verb reports it is parked.
wait_reached() {
    local _
    for _ in $(seq 1 200); do
        [[ -s "$FIFO.reached" ]] && return 0
        sleep 0.05
    done
    return 1
}
wait_done() {
    local pid="$1" _
    for _ in $(seq 1 200); do
        kill -0 "$pid" 2>/dev/null || { wait "$pid" 2>/dev/null; return 0; }
        sleep 0.05
    done
    return 1
}

# park_and_kill <point> <stdin-file> <args...>: start a verb that pauses at
# <point>, SIGKILL it there. Sets KILLED_AT to the point it reported.
park_and_kill() {
    local point="$1" input="$2" pid
    shift 2
    rm -f "$FIFO.reached"
    AITASK_SITREP_PAUSE_FIFO="$FIFO" PAUSE_POINT="$point" "$TMP/pause_at.sh" "$@" \
        <"$input" >"$TMP/bg.out" 2>"$TMP/bg.err" &
    pid=$!
    BG_PIDS+=("$pid")
    KILLED_AT=""
    local _
    for _ in $(seq 1 200); do
        if [[ -s "$FIFO.reached" ]] && grep -qxF "$point" "$FIFO.reached"; then
            KILLED_AT="$point"
            break
        fi
        # Release any earlier seam point this verb passes on its way.
        if [[ -s "$FIFO.reached" ]]; then
            rm -f "$FIFO.reached"
            echo go >&7
        fi
        sleep 0.05
    done
    kill -9 "$pid" 2>/dev/null
    wait "$pid" 2>/dev/null
}

# The pause wrapper execs the helper so the killed pid IS the lock holder.
cat > "$TMP/pause_at.sh" <<EOF
#!/usr/bin/env bash
exec "$H" "\$@"
EOF
chmod +x "$TMP/pause_at.sh"

ctx() {   # ctx <background> [extra lines...]
    printf -- '- background: %s\n- origin: agent=a1 date=2026-11-01\n' "$1"
    shift
    local l
    for l in "$@"; do printf '%s\n' "$l"; done
}

item_line() { grep "^- $1 |" "$S/todo.md"; }
nlines() { if [[ -z "$1" ]]; then echo 0; else printf '%s\n' "$1" | wc -l | tr -d ' '; fi; }

# Hold the store mutex with a LIVE pid so registry_lock.sh refuses to steal it.
hold_lock() {
    mkdir -p "$S/.lockd"
    sleep 30 &
    HOLDER_PID=$!
    BG_PIDS+=("$HOLDER_PID")
    echo "$HOLDER_PID" > "$S/.lockd/pid"
    echo "held-by-test" > "$S/.lockd/owner"
}
release_held_lock() {
    kill "$HOLDER_PID" 2>/dev/null || true
    wait "$HOLDER_PID" 2>/dev/null || true
    rm -rf "$S/.lockd"
}

# =============================================================================
echo "=== Test 1: first use -- every verb order initializes the store ==="
for flow in "add qa" "qa add" "retain add" "retain qa" "situation qa"; do
    reset_store
    ok=1
    for verb in $flow; do
        case "$verb" in
            add)       run - add --kind task --title "first" ;;
            qa)        run "Q: x" qa ;;
            retain)    run "passage" retain ;;
            situation) run "Some text." situation sitrep ;;
        esac
        [[ "$RC" -eq 0 ]] || { ok=0; echo "  $flow: $verb rc=$RC err=$ERR"; }
    done
    assert_eq "fresh '$flow' -> no refusal" "1" "$ok"
    for f in todo.md todo.md.bak qa.md qa.md.bak store.init; do
        assert_file_exists "fresh '$flow' -> $f exists" "$S/$f"
    done
    assert_eq "fresh '$flow' -> todo.md line 1 is the banner" "$TODO_BANNER" "$(head -n1 "$S/todo.md")"
    assert_eq "fresh '$flow' -> qa.md line 1 is the banner" "$QA_BANNER" "$(head -n1 "$S/qa.md")"
    assert_eq "fresh '$flow' -> todo.md.bak line 1 is the banner" "$TODO_BANNER" "$(head -n1 "$S/todo.md.bak")"
done

reset_store
run - list
assert_eq "list on a never-created store -> NO_ITEMS" "NO_ITEMS" "$OUT"
assert_dir_not_exists "read verbs create nothing" "$S"

echo "=== Test 2: an interrupted init is completed by the next verb ==="
reset_store
: > "$TMP/empty.in"
park_and_kill init:after_qa "$TMP/empty.in" add --kind task --title "x"
assert_eq "init parked at init:after_qa" "init:after_qa" "$KILLED_AT"
assert_file_exists "interrupted init -> qa.md written" "$S/qa.md"
assert_file_not_exists "interrupted init -> no marker" "$S/store.init"
assert_file_not_exists "interrupted init -> no todo.md yet" "$S/todo.md"
run - add --kind task --title "after crash"
assert_eq "next verb after an interrupted init succeeds" "0" "$RC"
assert_eq "... and allocates c1" "ADDED:c1" "$OUT"
assert_file_exists "... marker now written" "$S/store.init"

# =============================================================================
echo "=== Test 3: round trip -- each verb leaves other records byte-identical ==="
reset_store
run "$(ctx "First item.")" add --kind task --title "one" --ref t10 --context-file -
run "$(ctx "Second item." "- theme: alpha")" add --kind action --title "two" --group now --context-file -
c1_line="$(item_line c1)"
run - context c1; c1_ctx="$OUT"
run - update c2 --title "two renamed"
assert_eq "update c2 -> UPDATED with a fresh store-wide rev" "UPDATED:c2|3" "$OUT"
assert_eq "update c2 leaves the c1 item line byte-identical" "$c1_line" "$(item_line c1)"
run - context c1
assert_eq "update c2 leaves the c1 context byte-identical" "$c1_ctx" "$OUT"
run "Alpha is moving." situation alpha
assert_eq "situation -> set" "SITUATION:alpha|set" "$OUT"
assert_eq "situation leaves the c1 item line byte-identical" "$c1_line" "$(item_line c1)"
run "$(ctx "Second item, new background.")" upsert-context c2
assert_eq "upsert-context c2 -> replaced" "CONTEXT:c2|replaced" "$OUT"
run - context c1
assert_eq "upsert-context c2 leaves the c1 context byte-identical" "$c1_ctx" "$OUT"
before="$(cat "$S/todo.md")"
run - update c2 --title "two renamed"
assert_eq "an identical update reports the unchanged rev" "UPDATED:c2|3" "$OUT"
assert_eq "an identical update writes nothing" "$before" "$(cat "$S/todo.md")"
run - verify-is-not-a-verb
assert_eq "unknown verb -> exit 2" "2" "$RC"
run - update c99 --title x
assert_eq "unknown id -> exit 2" "2" "$RC"
assert_eq "unknown id -> NOT_FOUND on stdout" "NOT_FOUND:c99" "$OUT"
run "" situation alpha
assert_eq "empty situation removes the block" "SITUATION:alpha|removed" "$OUT"

echo "=== Test 4: a hand edit makes the file unreadable, nothing is written ==="
cp "$S/todo.md" "$TMP/good.md"
tail -n +2 "$TMP/good.md" > "$S/todo.md"
cp "$S/todo.md" "$TMP/edited.md"
cp "$S/todo.md.bak" "$TMP/bak_before.md"
run - add --kind task --title "should fail"
assert_eq "banner removed -> add exit 4" "4" "$RC"
assert_contains "banner removed -> error names the banner" "banner" "$ERR"
assert_eq "banner removed -> todo.md untouched" "$(cat "$TMP/edited.md")" "$(cat "$S/todo.md")"
assert_eq "banner removed -> backup untouched" "$(cat "$TMP/bak_before.md")" "$(cat "$S/todo.md.bak")"
run - list
assert_eq "banner removed -> list exit 4" "4" "$RC"
cp "$TMP/good.md" "$S/todo.md"
sed -i 's/^### Next$/### Next /' "$S/todo.md"
run - list
assert_eq "a trailing space on a heading -> exit 4" "4" "$RC"
assert_contains "... error names the line" "todo.md:" "$ERR"
cp "$TMP/good.md" "$S/todo.md"

# =============================================================================
echo "=== Test 5: concurrent writers ==="
reset_store
run - add --kind task --title "seed"
pids=()
for i in $(seq 1 12); do
    "$H" add --kind action --title "concurrent $i" >"$TMP/c$i.out" 2>"$TMP/c$i.err" </dev/null &
    pids+=($!)
done
for p in "${pids[@]}"; do wait "$p"; done
ids="$(cat "$TMP"/c*.out | sort -u)"
assert_eq "12 concurrent adds -> 12 distinct ids" "12" "$(nlines "$ids")"
run - list
assert_eq "all 13 items present" "13" "$(nlines "$OUT")"
assert_eq "next_id after 13 adds" "14" "$(cat "$S/next_id")"
assert_not_contains "no concurrent add reported busy" "LOCK_BUSY" "$(cat "$TMP"/c*.out)"
"$H" set-state c1 done --outcome "landed" >"$TMP/s.out" 2>&1 </dev/null &
p1=$!
ctx "Concurrent context." | "$H" upsert-context c2 >"$TMP/u.out" 2>&1 &
p2=$!
wait "$p1"; wait "$p2"
run - list
assert_contains_re "concurrent set-state survived" "ITEM:c1\|[0-9]+\|task\|done\|" "$OUT"
run - context c2
assert_contains "concurrent upsert-context survived" "Concurrent context." "$OUT"

# =============================================================================
echo "=== Test 6: same-item refresh race -- stale results are refused ==="
reset_store
run - add --kind task --title "refresh target" --ref t42
run - add --kind task --title "second" --ref t43
run - list
rev_of() { printf '%s\n' "$2" | sed -n "s/^ITEM:$1|\([0-9]*\)|.*/\1/p"; }
r1="$(rev_of c1 "$OUT")"
r2="$(rev_of c2 "$OUT")"
run - dismiss c1 --outcome "user: not needed"
d1="${OUT##*|}"
assert_contains "user dismisses c1" "STATE:c1|dismissed|" "$OUT"
assert_eq "the dismissal gives c1 a fresh rev" "1" "$(( d1 > r1 && d1 > r2 ))"
run "c1|$r1|done|now|landed
c2|$r2|done|now|landed
" set-state --batch
assert_contains "refresh computed before the dismissal -> STALE" "STALE:c1|$d1" "$OUT"
assert_contains "the fresh line in the same batch applies" "STATE:c2|done|" "$OUT"
n2="$(printf '%s\n' "$OUT" | sed -n 's/^STATE:c2|done|//p')"
assert_contains "c1 is still dismissed" "c1 | rev=$d1 | kind=task | state=dismissed" "$(cat "$S/todo.md")"
run "c1|$d1|open|now|
" set-state --batch
assert_eq "a batch with the fresh rev never touches a dismissed item" "KEPT:c1|dismissed" "$OUT"
run "c1|9|dismissed|now|
" set-state --batch
assert_eq "a batch never sets dismissed (exit 2)" "2" "$RC"
before="$(cat "$S/todo.md")"
run - set-state c2 open --expect-rev "$r2"
assert_eq "single set-state with a stale --expect-rev -> STALE" "STALE:c2|$n2" "$OUT"
assert_eq "... and writes nothing" "$before" "$(cat "$S/todo.md")"
run - update c2 --title "x" --expect-rev "$r2"
assert_eq "update with a stale --expect-rev -> STALE" "STALE:c2|$n2" "$OUT"
run "c9|1|done|now|
" set-state --batch
assert_eq "batch line for an unknown id -> NOT_FOUND line" "NOT_FOUND:c9" "$OUT"

echo "=== Test 6b: an outstanding refresh stays stale across a restore ==="
reset_store
run - add --kind task --title "moving target" --ref t1
run - update c1 --ref t2
observed="${OUT##*|}"
sed -i 's/kind=task/kind=bogus/' "$S/todo.md"
run - restore todo
run - list
assert_contains "the restore put the t1 generation back" "|t1|" "$OUT"
run - update c1 --ref t3
after="${OUT##*|}"
assert_eq "the post-restore change never reuses the observed rev" "1" "$(( after != observed ))"
run "c1|$observed|done|now|outcome computed for t2
" set-state --batch
assert_eq "the refresh computed for t2 is refused on the t3 item" "STALE:c1|$after" "$OUT"
run - list
assert_contains "c1 (t3) is still open" "|task|open|" "$OUT"
assert_not_contains "... and carries no t2 outcome" "computed for t2" "$OUT"

# =============================================================================
echo "=== Test 7: a writer killed inside the lock ==="
reset_store
run - add --kind task --title "before crash"
cp "$S/todo.md" "$TMP/gen1.md"
: > "$TMP/empty.in"
park_and_kill write:after_counter "$TMP/empty.in" add --kind task --title "killed"
assert_eq "add parked after reserving its id" "write:after_counter" "$KILLED_AT"
assert_eq "killed after the counter -> todo.md is the old generation" "$(cat "$TMP/gen1.md")" "$(cat "$S/todo.md")"
assert_eq "the killed writer's id was reserved" "3" "$(cat "$S/next_id")"
run - add --kind task --title "after crash"
assert_eq "next writer steals the dead lock" "0" "$RC"
assert_eq "the reserved id is skipped, never reused" "ADDED:c3" "$OUT"
cp "$S/todo.md" "$TMP/gen2.md"
park_and_kill write:after_backup "$TMP/empty.in" set-state c1 done
assert_eq "set-state parked after the backup" "write:after_backup" "$KILLED_AT"
assert_eq "killed after the backup -> todo.md is the old generation" "$(cat "$TMP/gen2.md")" "$(cat "$S/todo.md")"
assert_eq "killed after the backup -> .bak holds the same generation" "$(cat "$TMP/gen2.md")" "$(cat "$S/todo.md.bak")"
stray="$(find "$S" -maxdepth 1 -name '.todo.md.??????' | wc -l | tr -d ' ')"
assert_eq "the killed writer left its staging temp" "1" "$stray"
run - list
assert_eq "a stray staging temp is ignored by readers" "0" "$RC"
run - set-state c1 done
assert_contains "the next writer succeeds after the kill" "STATE:c1|done" "$OUT"
assert_eq "... and sweeps the dead writer's temp under the lock" "0" \
    "$(find "$S" -maxdepth 1 -name '.todo.md.??????' | wc -l | tr -d ' ')"

# =============================================================================
echo "=== Test 8: lock busy vs store unusable ==="
reset_store
run - add --kind task --title "x"
cp "$S/todo.md" "$TMP/held.md"
hold_lock
start=$(date +%s)
OUT="$(AITASK_SITREP_LOCK_TIMEOUT=1 "$H" add --kind task --title "blocked" 2>"$TMP/err" </dev/null)"; RC=$?
assert_eq "live holder -> exit 3" "3" "$RC"
assert_eq "live holder -> LOCK_BUSY" "LOCK_BUSY" "$OUT"
assert_eq "live holder -> nothing written" "$(cat "$TMP/held.md")" "$(cat "$S/todo.md")"
release_held_lock

reset_store
mkdir -p "$TMP/filebase"
: > "$TMP/filebase/root"
OUT="$(AITASK_SITREP_DIR="$TMP/filebase/root" AITASK_SITREP_LOCK_TIMEOUT=5 "$H" add --kind task --title x 2>&1 </dev/null)"; RC=$?
assert_eq "store root is a regular file -> exit 4" "4" "$RC"
assert_not_contains "... not reported as contention" "LOCK_BUSY" "$OUT"

reset_store
run - add --kind task --title x
rm -rf "$S/.lockd"
ln -s "$TMP" "$S/.lockd"
OUT="$(AITASK_SITREP_LOCK_TIMEOUT=5 "$H" add --kind task --title y 2>&1 </dev/null)"; RC=$?
assert_eq "lock path is a symlink -> exit 4" "4" "$RC"
assert_not_contains "... not reported as contention" "LOCK_BUSY" "$OUT"
rm -f "$S/.lockd"

chmod 555 "$S"
if [[ -w "$S" ]]; then
    echo "SKIP: read-only store dir (mode ignored for this user)"
else
    OUT="$(AITASK_SITREP_LOCK_TIMEOUT=5 "$H" add --kind task --title z 2>&1 </dev/null)"; RC=$?
    assert_eq "read-only store dir -> exit 4" "4" "$RC"
    assert_not_contains "... not reported as contention" "LOCK_BUSY" "$OUT"
fi
chmod 755 "$S"

# =============================================================================
echo "=== Test 9: backups and restore ==="
reset_store
run - add --kind task --title "g1"
cp "$S/todo.md" "$TMP/g1.md"
run - add --kind task --title "g2"
cp "$S/todo.md" "$TMP/g2.md"
assert_eq ".bak is the previous generation" "$(cat "$TMP/g1.md")" "$(cat "$S/todo.md.bak")"
sed -i 's/kind=task/kind=bogus/' "$S/todo.md"
cp "$S/todo.md" "$TMP/damaged.md"
run - add --kind task --title "refused"
assert_eq "damaged todo.md -> add exit 4" "4" "$RC"
assert_eq "damaged todo.md -> file untouched" "$(cat "$TMP/damaged.md")" "$(cat "$S/todo.md")"
assert_eq "damaged todo.md -> backup untouched" "$(cat "$TMP/g1.md")" "$(cat "$S/todo.md.bak")"
run - restore todo
assert_eq "restore todo -> exit 0" "0" "$RC"
assert_contains "restore todo -> names the preserved copy" "RESTORED:todo.md|recovered/todo.md." "$OUT"
assert_eq "restore installs the backup" "$(cat "$TMP/g1.md")" "$(cat "$S/todo.md")"
preserved="$S/${OUT#RESTORED:todo.md|}"
assert_eq "the damaged file is preserved verbatim" "$(cat "$TMP/damaged.md")" "$(cat "$preserved")"

echo "--- interrupted restore ---"
sed -i 's/kind=task/kind=bogus/' "$S/todo.md"
cp "$S/todo.md" "$TMP/damaged2.md"
park_and_kill restore:after_preserve "$TMP/empty.in" restore todo
assert_eq "restore parked after preserving" "restore:after_preserve" "$KILLED_AT"
assert_file_exists "interrupted restore -> the live file still exists" "$S/todo.md"
assert_eq "interrupted restore -> it is the damaged original" "$(cat "$TMP/damaged2.md")" "$(cat "$S/todo.md")"
run - add --kind task --title "still refused"
assert_eq "after an interrupted restore the store still refuses" "4" "$RC"
run - restore todo
assert_eq "a second restore succeeds" "0" "$RC"
run - list
assert_eq "the store reads again" "0" "$RC"

echo "--- corrupt backup ---"
sed -i 's/kind=task/kind=bogus/' "$S/todo.md.bak"
cp "$S/todo.md" "$TMP/live.md"
run - restore todo
assert_eq "corrupt backup -> restore exit 4" "4" "$RC"
assert_eq "corrupt backup -> live file untouched" "$(cat "$TMP/live.md")" "$(cat "$S/todo.md")"

echo "--- deleted established files ---"
reset_store
run - add --kind task --title "a"
run - add --kind task --title "b"
run "Q: a?" qa --items c1
rm "$S/todo.md"
run - add --kind task --title "c"
assert_eq "deleted todo.md -> add exit 4 (not an empty store)" "4" "$RC"
assert_contains "... and names restore" "restore todo" "$ERR"
run "Q: still?" qa
assert_eq "deleted todo.md -> qa keeps working" "0" "$RC"
run - restore todo
assert_eq "restore of a deleted todo.md" "RESTORED:todo.md|no-damaged-copy" "$OUT"
run - list
assert_contains "the restored generation is back" "ITEM:c1|" "$OUT"
rm "$S/qa.md"
run "Q: refused?" qa
assert_eq "deleted qa.md -> qa exit 4" "4" "$RC"
run - add --kind task --title "d"
assert_eq "deleted qa.md -> add keeps working" "0" "$RC"
run - restore qa
assert_eq "restore qa recovers" "0" "$RC"
assert_eq "restored qa.md line 1 is the banner" "$QA_BANNER" "$(head -n1 "$S/qa.md")"
rm "$S/store.init" "$S/todo.md"
run - add --kind task --title "e"
assert_eq "marker AND todo.md gone while next_id exists -> still damaged" "4" "$RC"
assert_file_not_exists "... never re-initialized over the lost data" "$S/todo.md"
run - restore todo
assert_file_exists "restore rewrites the marker once both files are back" "$S/store.init"

# =============================================================================
echo "=== Test 10: ids are never reused across recovery ==="
reset_store
for t in a b c d; do run - add --kind task --title "$t"; done
run - add --kind task --title "e"
assert_eq "c5 allocated" "ADDED:c5" "$OUT"
run "Q: about c5" qa --items c5
sed -i 's/kind=task/kind=bogus/' "$S/todo.md"
run - restore todo
run - list
assert_not_contains "the restored backup lacks c5" "ITEM:c5|" "$OUT"
run - add --kind task --title "after restore"
assert_eq "after restore the next id is c6, not c5" "ADDED:c6" "$OUT"
sed -i 's/kind=task/kind=bogus/' "$S/todo.md"
run - restore todo
rm -f "$S/next_id"
run - add --kind task --title "no counter"
assert_eq "restore + lost counter -> still above every id ever seen" "ADDED:c7" "$OUT"
run "Q: never" qa --items c99
assert_eq "qa naming an id that never existed -> exit 2" "2" "$RC"

# =============================================================================
echo "=== Test 11: the Q&A log ==="
reset_store
run "Q: one?
A: yes." qa
AITASK_SITREP_NOW="2026-11-01T11:00:00Z" run "Q: two?" qa --items -
assert_eq "qa with no items" "0" "$RC"
assert_eq "entries are appended in order" "2026-11-01T10:00:00Z
2026-11-01T11:00:00Z" "$(sed -n 's/^## \([^ ]*\) |.*/\1/p' "$S/qa.md")"
run "Q: x
## forged" qa
assert_eq "a '## ' body line -> exit 2" "2" "$RC"
cp "$S/qa.md" "$TMP/qa_good.md"
printf 'Q: three?\n' > "$TMP/qa3.in"
park_and_kill write:after_backup "$TMP/qa3.in" qa
assert_eq "qa parked after the backup" "write:after_backup" "$KILLED_AT"
assert_eq "killed qa -> qa.md holds every earlier entry" "$(cat "$TMP/qa_good.md")" "$(cat "$S/qa.md")"
run "Q: three?" qa
assert_eq "the next qa succeeds" "0" "$RC"
sed -i '2s/format=1/format=9/' "$S/qa.md"
run "Q: refused" qa
assert_eq "corrupt qa.md -> qa exit 4" "4" "$RC"
run - add --kind task --title "todo still works"
assert_eq "corrupt qa.md -> todo verbs keep working" "0" "$RC"
run - restore qa
assert_eq "restore qa recovers from the backup" "0" "$RC"
assert_eq "restored qa.md is the previous generation" "$(cat "$TMP/qa_good.md")" "$(cat "$S/qa.md")"
run - read qa
assert_eq "read qa prints the log" "$(cat "$S/qa.md")" "$OUT"

# =============================================================================
echo "=== Test 12: retained sources and durable pointers ==="
reset_store
run "alpha
beta
gamma
" retain
p1="$OUT"
run "alpha
beta
gamma
" retain
assert_eq "retain is idempotent" "$p1" "$OUT"
assert_contains "retain returns a line range" "#L1-L3" "$OUT"
assert_eq "one retained file" "1" "$(find "$S/sources" -type f | wc -l | tr -d ' ')"
ptr="${p1#RETAINED:}"
run "$(ctx "Has a capture." "- sources:" "  - capture: $ptr")" add --kind task --title "with source" --context-file -
assert_eq "a retained capture pointer is accepted" "ADDED:c1" "$OUT"
for bad in "capture: ~/.config/aitasks/frozen/x/capture.txt#L1-L2" \
           "capture: /home/u/.config/aitasks/frozen/x/capture.txt#L1-L2" \
           "file: /etc/passwd" "file: ../outside.md" "task: ~/x.md" \
           "capture: sources/0000000000000000.txt#L1-L2" \
           "capture: ${ptr%%#*}#L1-L9" "commit: not-a-sha" "url: ftp://x"; do
    run "$(ctx "Bad." "- sources:" "  - $bad")" upsert-context c1
    assert_eq "rejected source '$bad' -> exit 2" "2" "$RC"
done
run - check-sources
assert_eq "check-sources -> OK" "SOURCE_OK:c1|$ptr" "$OUT"
rm -f "$S/${ptr%%#*}"
run - check-sources
assert_eq "check-sources after the file vanished -> MISSING" "SOURCE_MISSING:c1|$ptr" "$OUT"

# =============================================================================
echo "=== Test 13: schema rejection writes nothing ==="
reset_store
for bad in "- status: open" "- count: 3" "- next: pick it" "- progress: 50%" "- colour: red"; do
    run "$(ctx "x" "$bad")" add --kind task --title "t" --context-file -
    assert_eq "context '$bad' -> exit 2" "2" "$RC"
    case "$bad" in
        *colour*) assert_contains "unknown key -> names the allowed keys" "allowed: background" "$ERR" ;;
        *) assert_contains "denied '$bad' -> map-not-status message" "map of pointers" "$ERR" ;;
    esac
done
run "- origin: agent=a" add --kind task --title "t" --context-file -
assert_eq "missing background -> exit 2" "2" "$RC"
long="$(printf 'x%.0s' $(seq 1 450))"
run "$(ctx "$long")" add --kind task --title "t" --context-file -
assert_eq "over-long background -> exit 2" "2" "$RC"
run - add --kind task --title "multi
line"
assert_eq "newline in a title -> exit 2" "2" "$RC"
run - add --kind bogus --title "t"
assert_eq "bad kind -> exit 2" "2" "$RC"
run - add --kind task --title "t" --ref "not a ref"
assert_eq "bad ref -> exit 2" "2" "$RC"
assert_dir_not_exists "rejected requests on a fresh root created nothing" "$S"
run - add --kind task --title "ok"
run - set-state c1 done --outcome "a | b"
assert_eq "'|' in an outcome -> exit 2" "2" "$RC"

# =============================================================================
echo "=== Test 14: re-adding a ref is idempotent, dismissals stick ==="
reset_store
run - add --kind task --title "follow-up" --ref t42
run - add --kind task --title "follow-up again" --ref 42
assert_eq "same ref (t42 == 42) -> EXISTS" "EXISTS:c1" "$OUT"
run - dismiss c1
run - add --kind task --title "re-harvest" --ref t42
assert_eq "a dismissed ref is not re-added" "EXISTS:c1" "$OUT"
run - add --kind task --title "cross" --ref "aitasks#t2171"
run - list
assert_contains "cross-repo refs are normalized without t" "|aitasks#2171|" "$OUT"

# =============================================================================
echo "=== Test 14b: a value with a trailing newline is refused, nothing written ==="
reset_store
run - add --kind task --title "baseline"
run - set-state c1 done
cp "$S/todo.md" "$TMP/nl_todo.md"; cp "$S/todo.md.bak" "$TMP/nl_bak.md"
nl_ts="$(printf '2026-11-01T10:00:00Z\nX')"; nl_ts="${nl_ts%X}"
run - add --kind task --title "t" --checked-at "$nl_ts"
assert_eq "add --checked-at with a trailing LF -> exit 2" "2" "$RC"
run - set-state c1 open --checked-at "$nl_ts"
assert_eq "set-state --checked-at with a trailing LF -> exit 2" "2" "$RC"
nl_theme="$(printf 'alpha\nX')"; nl_theme="${nl_theme%X}"
run "text" situation "$nl_theme"
assert_eq "a theme with a trailing LF -> exit 2" "2" "$RC"
run - add --kind task --title "t" --ref "$(printf 't5\rX' | sed 's/X$//')"
assert_eq "a ref with a CR -> exit 2" "2" "$RC"
assert_eq "refused values leave todo.md unchanged" "$(cat "$TMP/nl_todo.md")" "$(cat "$S/todo.md")"
assert_eq "refused values leave the backup unchanged" "$(cat "$TMP/nl_bak.md")" "$(cat "$S/todo.md.bak")"
run - list
assert_eq "the store still reads" "0" "$RC"

echo "=== Test 14c: an unreadable data file is unusable, never empty ==="
reset_store
run - add --kind task --title "readable"
chmod 000 "$S/todo.md"
if [[ -r "$S/todo.md" ]]; then
    echo "SKIP: unreadable todo.md (mode ignored for this user)"
else
    run - read
    assert_eq "read of an unreadable todo.md -> exit 4" "4" "$RC"
    assert_contains "... with a diagnostic" "cannot read" "$ERR"
    assert_eq "... and no data-shaped stdout" "" "$OUT"
    run - list
    assert_eq "list of an unreadable todo.md -> exit 4" "4" "$RC"
    run - add --kind task --title "refused"
    assert_eq "add over an unreadable todo.md -> exit 4" "4" "$RC"
    chmod 644 "$S/todo.md"
    chmod 000 "$S/todo.md.bak"
    run - add --kind task --title "scan refused"
    assert_eq "an unreadable backup stops id allocation (exit 4)" "4" "$RC"
fi
chmod 644 "$S/todo.md" "$S/todo.md.bak" 2>/dev/null

# =============================================================================
echo "=== Test 15: a '..' root is refused before any filesystem access ==="
rm -rf "$TMP/dd"
OUT="$(AITASK_SITREP_DIR="$TMP/dd/a/../b" "$H" add --kind task --title x 2>&1 </dev/null)"; RC=$?
assert_eq "'..' root -> exit 2" "2" "$RC"
assert_dir_not_exists "'..' root -> nothing created" "$TMP/dd"

# =============================================================================
echo "=== Test 16: the consumer-contract fixture (tests/fixtures/sitrep/) ==="
reset_store
mkdir -p "$S"
cp -R "$FIXTURE/store/." "$S/"
run - read
assert_eq "read returns the fixture byte-identical" "$(cat "$FIXTURE/store/todo.md")" "$OUT"
run - list --machine
assert_eq "list --machine on the fixture" "$(cat "$FIXTURE/expected_list.txt")" "$OUT"
run - context c1
assert_eq "context c1 on the fixture" "$(cat "$FIXTURE/expected_context_c1.txt")" "$OUT"
run - check-sources
assert_eq "check-sources on the fixture" "$(cat "$FIXTURE/expected_check_sources.txt")" "$OUT"
title="$(sed -n 's/^ITEM:c2|\([^|]*|\)\{8\}//p' "$FIXTURE/expected_list.txt")"
run - update c2 --title "$title"
assert_eq "a no-op update on the fixture succeeds" "0" "$RC"
assert_eq "... and leaves todo.md byte-identical" "$(cat "$FIXTURE/store/todo.md")" "$(cat "$S/todo.md")"
assert_eq "the fixture qa.md parses" "VERIFIED:qa" "$(python3 "$CORE" verify qa "$S/qa.md")"

echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ "$FAIL" -eq 0 ]]; then
    echo "ALL TESTS PASSED"
fi
[[ "$FAIL" -eq 0 ]]
