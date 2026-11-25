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
run "$(ctx "Second item." "- direction: alpha")" add --kind action --title "two" --group now --context-file -
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
# A changed context entry gives its item a fresh rev (t2175_3): a refresh
# verdict computed from the old entry must fail the batch's rev check. (The
# `situation` write above took rev 4: a direction block has a rev of its own.)
assert_eq "upsert-context c2 gives c2 a fresh rev" "5" "$(item_line c2 | sed -n 's/^- c2 | rev=\([0-9]*\) .*/\1/p')"
assert_eq "upsert-context c2 leaves the c1 item line byte-identical" "$c1_line" "$(item_line c1)"
run - context c1
assert_eq "upsert-context c2 leaves the c1 context byte-identical" "$c1_ctx" "$OUT"
before="$(cat "$S/todo.md")"
run - update c2 --title "two renamed"
assert_eq "an identical update reports the unchanged rev" "UPDATED:c2|5" "$OUT"
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
echo "=== Test 9b: restore --if-damaged decides under the lock (t2211_3) ==="
reset_store
run - add --kind task --title "g1"
run - add --kind task --title "g2"
run - add --kind task --title "g3 newer than the backup"
cp "$S/todo.md" "$TMP/healthy.md"
run - restore todo --if-damaged
assert_eq "healthy todo.md -> exit 0" "0" "$RC"
assert_eq "healthy todo.md -> RESTORE_NOT_NEEDED" "RESTORE_NOT_NEEDED:todo.md" "$OUT"
assert_eq "... the live generation is untouched" "$(cat "$TMP/healthy.md")" "$(cat "$S/todo.md")"
assert_dir_not_exists "... and nothing was preserved" "$S/recovered"
run "Q: x?" qa
cp "$S/qa.md" "$TMP/healthy_qa.md"
run - restore qa --if-damaged
assert_eq "healthy qa.md -> RESTORE_NOT_NEEDED" "RESTORE_NOT_NEEDED:qa.md" "$OUT"
assert_eq "... qa.md untouched" "$(cat "$TMP/healthy_qa.md")" "$(cat "$S/qa.md")"
# Pre-fix control: the unconditional verb DOES roll a healthy file back -- the
# hazard the flag exists for.
run - restore todo
assert_contains "plain restore on a healthy file still restores (CLI contract)" "RESTORED:todo.md|recovered/" "$OUT"
assert_not_contains "... and rolls the newer generation back" "g3 newer" "$(cat "$S/todo.md")"

reset_store
run - add --kind task --title "g1"
run - add --kind task --title "g2"
cp "$S/todo.md.bak" "$TMP/bak.md"
sed -i 's/kind=task/kind=bogus/' "$S/todo.md"
run - restore todo --if-damaged
assert_contains "damaged todo.md -> --if-damaged restores" "RESTORED:todo.md|recovered/todo.md." "$OUT"
assert_eq "... installing the backup" "$(cat "$TMP/bak.md")" "$(cat "$S/todo.md")"
rm "$S/todo.md"
run - restore todo --if-damaged
assert_eq "missing todo.md in an established store -> restored" "RESTORED:todo.md|no-damaged-copy" "$OUT"
printf 'not a store file\n' > "$S/todo.md"
run - restore todo --if-damaged
assert_contains "an unparsable todo.md (no header) -> restored" "RESTORED:todo.md|recovered/" "$OUT"
run - restore bogus --if-damaged
assert_eq "--if-damaged with a bad kind -> exit 2" "2" "$RC"
run - restore todo --if-damaged --wat
assert_eq "an unknown restore option -> exit 2" "2" "$RC"

sed -i 's/kind=task/kind=bogus/' "$S/todo.md"
cp "$S/todo.md" "$TMP/damaged3.md"
hold_lock
OUT="$(AITASK_SITREP_LOCK_TIMEOUT=1 "$H" restore todo --if-damaged 2>"$TMP/err" </dev/null)"; RC=$?
assert_eq "--if-damaged on a busy lock -> exit 3" "3" "$RC"
assert_eq "... LOCK_BUSY" "LOCK_BUSY" "$OUT"
assert_eq "... nothing written" "$(cat "$TMP/damaged3.md")" "$(cat "$S/todo.md")"
release_held_lock

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
sed -i '2s/format=1/format=x/' "$S/qa.md"
run "Q: refused" qa
assert_eq "corrupt qa.md -> qa exit 4" "4" "$RC"
run - add --kind task --title "todo still works"
assert_eq "corrupt qa.md -> todo verbs keep working" "0" "$RC"
run - restore qa
assert_eq "restore qa recovers from the backup" "0" "$RC"
assert_eq "restored qa.md is the previous generation" "$(cat "$TMP/qa_good.md")" "$(cat "$S/qa.md")"
run - read qa
assert_eq "read qa prints the log" "$(cat "$S/qa.md")" "$OUT"
# A qa.md of a NEWER format is not damage: restore refuses to roll it back,
# with LF and with CR LF line endings.
sed -i '2s/format=1/format=9/' "$S/qa.md"
for ending in LF CRLF; do
    [[ "$ending" == CRLF ]] && sed -i 's/$/\r/' "$S/qa.md"
    newer_qa="$(cat "$S/qa.md"; printf x)"
    for form in "restore qa" "restore qa --if-damaged"; do
        # shellcheck disable=SC2086
        run - $form
        assert_eq "$form over a newer-format qa.md ($ending) -> exit 4" "4" "$RC"
        assert_contains "... says it is not damaged" "newer than this writer supports" "$ERR"
        assert_eq "... qa.md untouched" "$newer_qa" "$(cat "$S/qa.md"; printf x)"
    done
done

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
nl_slug="$(printf 'alpha\nX')"; nl_slug="${nl_slug%X}"
run "text" situation "$nl_slug"
assert_eq "a direction with a trailing LF -> exit 2" "2" "$RC"
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
# Directions (t2335_1). Helpers first.

# The DIRECTION line of <slug>: field n (2 rev, 3 stamp, 4 rank, 5 freshness,
# 6 checked_at, 7 digest, 8 next, 9 trails, 10 pending, 11 members, 12 title).
dir_field() { "$H" directions "$1" 2>/dev/null | sed -n '1p' | cut -d'|' -f"$2"; }
dir_rev() { dir_field "$1" 2; }
dir_stamp() { dir_field "$1" 3; }
item_rev() { item_line "$1" | sed -n 's/^- c[0-9]* | rev=\([0-9]*\) .*/\1/p'; }
# The lines of <slug>'s block in todo.md (heading to the blank line).
block() { sed -n "/^#### $1 | rev=/,/^\$/p" "$S/todo.md"; }
# The block's AGENT-written lines: everything but the heading's rev and the
# three refresh fields.
agent_fields() { block "$1" | sed -e '1s/ | rev=.*//' -e '/^- freshness:/d' -e '/^- checked_at:/d' -e '/^- drift:/d'; }
# snapshot <slug> <line>...: a baseline snapshot text (lines given in order).
# Captured with $( ), it loses its final newline: retain_snapshot puts it back.
snapshot() {
    local slug="$1" l
    shift
    printf 'sitrep direction baseline v1\ndirection: %s\n' "$slug"
    for l in "$@"; do printf '%s\n' "$l"; done
}
# retain_snapshot <text>: sets DIG (the digest) and OUT / RC.
retain_snapshot() {
    run "$1"$'\n' retain-baseline
    DIG="$(printf '%s' "$OUT" | sed -n 's/^RETAINED_BASELINE:[^|]*|//p')"
}
# set_summary <slug> <digest> <text> [more direction-set args]: with the block's
# current rev.
set_summary() {
    local slug="$1" dig="$2" text="$3"
    shift 3
    run "$text" direction-set "$slug" --expect-rev "$(dir_rev "$slug")" \
        --summary-file - --digest "$dig" "$@"
}
freshness_line() {   # freshness_line <slug> <freshness> [drift]: with the current rev + stamp
    printf '%s|%s|%s|%s|now|%s\n' "$1" "$(dir_rev "$1")" "$(dir_stamp "$1")" "$2" "${3:-}"
}
# The records of a format-4 file reduced to what formats 1-3 held: headings
# without their rev, the nine header lines gone.
strip_records() { sed -e '/^#### /s/ | rev=[0-9]*$//' -e '/^#### /{n;N;N;N;N;N;N;N;N;d;}'; }

# upgrade_checks <fixture dir name> <format>: the store was just upgraded by
# `update c4 --title ...` from that fixture.
upgrade_checks() {
    local src="$FIXTURE/$1/todo.md" fmt="$2" kept
    assert_eq "$1: line 2 is now format=4" "<!-- aitask-sitrep todo format=4 -->" "$(sed -n 2p "$S/todo.md")"
    assert_eq "$1: same items, contexts and situation text, bar the touched item" \
        "$(sed -e 2d -e '/^- c4 |/d' -e 's/^- theme: /- direction: /' "$src")" \
        "$(sed -e 2d -e '/^- c4 |/d' "$S/todo.md" | strip_records)"
    assert_eq "$1: the upgraded todo.md verifies" "VERIFIED:todo" "$(python3 "$CORE" verify todo "$S/todo.md")"
    # Mixed versions: no older-format backup is left behind the format-4 file.
    assert_eq "$1: the backup is format=4 too" "<!-- aitask-sitrep todo format=4 -->" "$(sed -n 2p "$S/todo.md.bak")"
    assert_eq "$1: the backup verifies" "VERIFIED:todo" "$(python3 "$CORE" verify todo "$S/todo.md.bak")"
    assert_eq "$1: the backup is the PREVIOUS generation, same content" \
        "$(sed -e 2d -e 's/^- theme: /- direction: /' "$src")" \
        "$(sed -e 2d "$S/todo.md.bak" | strip_records)"
    kept="$(ls "$S/recovered" 2>/dev/null | grep "^todo\.md\.format$fmt\." | head -n1)"
    assert_contains "$1: the pre-upgrade bytes are kept under recovered/" "todo.md.format$fmt." "$kept"
    assert_eq "$1: ... byte-identical" "$(cat "$src")" "$(cat "$S/recovered/$kept" 2>/dev/null)"
    assert_eq "$1: an unchanged block has one rev in the file and its backup" \
        "$(grep '^#### ' "$S/todo.md")" "$(grep '^#### ' "$S/todo.md.bak")"
    assert_eq "$1: qa.md stays format=1" "<!-- aitask-sitrep qa format=1 -->" "$(sed -n 2p "$S/qa.md")"
}

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
assert_contains "the fixture is todo format 4" "format=4" "$(sed -n 2p "$S/todo.md")"
run - directions
assert_eq "directions on the fixture" "$(cat "$FIXTURE/expected_directions.txt")" "$OUT"
run - directions crashed-agents
assert_eq "directions <slug> prints that direction only" \
    "$(grep ':crashed-agents|' "$FIXTURE/expected_directions.txt")" "$OUT"
run - directions nosuch
assert_eq "directions of an unknown slug -> exit 2" "2" "$RC"
assert_eq "... NOT_FOUND on stdout" "NOT_FOUND:nosuch" "$OUT"

# =============================================================================
echo "=== Test 16b: a format=1 store is read as-is and upgraded by its first changing write ==="
reset_store
mkdir -p "$S"
cp -R "$FIXTURE/store_v1/." "$S/"
run - read
assert_eq "read returns the v1 fixture byte-identical" "$(cat "$FIXTURE/store_v1/todo.md")" "$OUT"
run - list --machine
assert_eq "list --machine on the v1 fixture" "$(cat "$FIXTURE/expected_list_v1.txt")" "$OUT"
title="$(sed -n 's/^ITEM:c2|\([^|]*|\)\{8\}//p' "$FIXTURE/expected_list_v1.txt")"
run - update c2 --title "$title"
assert_eq "a no-op update on the v1 fixture succeeds" "0" "$RC"
assert_eq "... and leaves the v1 todo.md byte-identical (still format=1)" \
    "$(cat "$FIXTURE/store_v1/todo.md")" "$(cat "$S/todo.md")"
run - update c4 --title "CI on the sitrep branch (renamed)"
assert_eq "a changing update on the v1 fixture succeeds" "0" "$RC"
upgrade_checks store_v1 1

# =============================================================================
echo "=== Test 16c: push refs ==="
reset_store
run "$(ctx "A push reminder.")" add --kind action --title "Push main" --ref push:main@ABCDEF1 --derived agent --context-file -
assert_eq "add --ref push:main@<sha> -> ADDED" "ADDED:c1" "$OUT"
assert_contains "the sha is stored lowercase" "ref=push:main@abcdef1 |" "$(item_line c1)"
run - add --kind action --title "Push main again" --ref push:main@abcdef1
assert_eq "the same push ref again -> EXISTS" "EXISTS:c1" "$OUT"
run - add --kind action --title "Push feature" --ref push:feature/x-1@0123456789abcdef0123456789abcdef01234567
assert_eq "a slash branch and a 40-hex sha -> ADDED" "ADDED:c2" "$OUT"
before="$(cat "$S/todo.md")"
for bad in "push:main" "push:@abcdef1" "push:main@abc12" "push:main@xyz1234" "push:.hidden@abcdef1" \
           "push:a..b@abcdef1" "push:a//b@abcdef1" "push:a/@abcdef1" "push:a.lock@abcdef1" \
           "push:-x@abcdef1" "push:a/.b@abcdef1" "push:ma in@abcdef1" 'push:a$(id)@abcdef1'; do
    run - add --kind action --title "bad" --ref "$bad"
    assert_eq "invalid push ref '$bad' -> exit 2" "2" "$RC"
done
assert_eq "... and nothing was written" "$before" "$(cat "$S/todo.md")"

# =============================================================================
echo "=== Test 16d: a format=2 store is read as-is and upgraded to 4 by its first changing write ==="
reset_store
mkdir -p "$S"
cp -R "$FIXTURE/store_v2/." "$S/"
run - read
assert_eq "read returns the v2 fixture byte-identical" "$(cat "$FIXTURE/store_v2/todo.md")" "$OUT"
run - list --machine
assert_eq "list --machine on the v2 fixture" "$(cat "$FIXTURE/expected_list_v2.txt")" "$OUT"
title="$(sed -n 's/^ITEM:c2|\([^|]*|\)\{8\}//p' "$FIXTURE/expected_list_v2.txt")"
run - update c2 --title "$title"
assert_eq "a no-op update on the v2 fixture succeeds" "0" "$RC"
assert_eq "... and leaves the v2 todo.md byte-identical (still format=2)" \
    "$(cat "$FIXTURE/store_v2/todo.md")" "$(cat "$S/todo.md")"
run - update c4 --title "CI on the sitrep branch (renamed)"
assert_eq "a changing update on the v2 fixture succeeds" "0" "$RC"
upgrade_checks store_v2 2
# A v2 file holding format-3 grammar is refused (exit 4), never read loosely.
reset_store
mkdir -p "$S"
cp -R "$FIXTURE/store_v2/." "$S/"
sed -i '/^- c6 |/a - c9 | rev=20 | kind=task | state=open | group=now | checked_at=never | ref=recover:t42 | derived=script | outcome= | t42 crashed' "$S/todo.md"
run - list
assert_eq "a v2 file with a recover: ref -> exit 4" "4" "$RC"
assert_contains "... naming the format it needs" "recover refs need format=3" "$ERR"
cp "$FIXTURE/store_v2/todo.md" "$S/todo.md"
sed -i 's/^- origin: agent=agent-pick-2175 date=2026-11-01$/& incarnation=0123456789ab/' "$S/todo.md"
assert_contains "(the origin line was edited)" "incarnation=0123456789ab" "$(cat "$S/todo.md")"
run - list
assert_eq "a v2 file with an incarnation origin -> exit 4" "4" "$RC"
assert_contains "... naming the format it needs" "incarnation origin key needs format=3" "$ERR"

# =============================================================================
echo "=== Test 16e: a format=3 store is read as-is and upgraded to 4 by its first changing write ==="
reset_store
mkdir -p "$S"
cp -R "$FIXTURE/store_v3/." "$S/"
run - read
assert_eq "read returns the v3 fixture byte-identical" "$(cat "$FIXTURE/store_v3/todo.md")" "$OUT"
run - list --machine
assert_eq "list --machine on the v3 fixture" "$(cat "$FIXTURE/expected_list_v3.txt")" "$OUT"
run - context c1
assert_contains "context prints the current key on an old file" "- direction: sitrep" "$OUT"
run - directions sitrep
assert_contains "directions reads an old file: no rev yet" "DIRECTION:sitrep|-|" "$OUT"
title="$(sed -n 's/^ITEM:c2|\([^|]*|\)\{8\}//p' "$FIXTURE/expected_list_v3.txt")"
run - update c2 --title "$title"
assert_eq "a no-op update on the v3 fixture succeeds" "0" "$RC"
assert_eq "... and leaves the v3 todo.md byte-identical (still format=3)" \
    "$(cat "$FIXTURE/store_v3/todo.md")" "$(cat "$S/todo.md")"
assert_file_not_exists "... and no backup was rolled" "$S/todo.md.bak"
run - update c4 --title "CI on the sitrep branch (renamed)"
assert_eq "a changing update on the v3 fixture succeeds" "0" "$RC"
upgrade_checks store_v3 3
# Newer grammar under an older format= is refused (exit 4), never read loosely.
reset_store
mkdir -p "$S"
cp -R "$FIXTURE/store_v3/." "$S/"
sed -i 's/^#### sitrep$/#### sitrep | rev=5/' "$S/todo.md"
run - list
assert_eq "a v3 file with a direction heading -> exit 4" "4" "$RC"
assert_contains "... naming the format it needs" "direction records need format=4" "$ERR"
cp "$FIXTURE/store_v3/todo.md" "$S/todo.md"
sed -i '0,/^- theme: sitrep$/s//- direction: sitrep/' "$S/todo.md"
run - list
assert_eq "a v3 file with a direction key -> exit 4" "4" "$RC"
assert_contains "... naming the format it needs" "direction context key needs format=4" "$ERR"
reset_store
mkdir -p "$S"
cp -R "$FIXTURE/store/." "$S/"
sed -i '0,/^- direction: sitrep$/s//- theme: sitrep/' "$S/todo.md"
run - list
assert_eq "a v4 file with the old key -> exit 4" "4" "$RC"
assert_contains "... as an unknown key" "unknown context key 'theme'" "$ERR"

# =============================================================================
echo "=== Test 16f: mixed versions -- a killed upgrade, and a file from a NEWER writer ==="
reset_store
mkdir -p "$S"
cp -R "$FIXTURE/store_v3/." "$S/"
printf 'Rewritten.\n' > "$TMP/sit.in"
park_and_kill write:after_backup "$TMP/sit.in" situation sitrep
assert_eq "the upgrading write parked after the backup" "write:after_backup" "$KILLED_AT"
assert_eq "killed there -> todo.md is still the format=3 generation" \
    "$(cat "$FIXTURE/store_v3/todo.md")" "$(cat "$S/todo.md")"
assert_eq "... and the backup already is format=4" "<!-- aitask-sitrep todo format=4 -->" "$(sed -n 2p "$S/todo.md.bak")"
assert_eq "... holding the same content" \
    "$(sed -e 2d -e 's/^- theme: /- direction: /' "$FIXTURE/store_v3/todo.md")" \
    "$(sed -e 2d "$S/todo.md.bak" | strip_records)"
run - list --machine
assert_eq "the next read works" "$(cat "$FIXTURE/expected_list_v3.txt")" "$OUT"
run "Rewritten." situation sitrep
assert_eq "the next write completes the upgrade" "SITUATION:sitrep|set" "$OUT"
assert_eq "... to format=4" "<!-- aitask-sitrep todo format=4 -->" "$(sed -n 2p "$S/todo.md")"
assert_eq "... and the store verifies" "VERIFIED:todo" "$(python3 "$CORE" verify todo "$S/todo.md")"
# This writer is the OLD one for the next format: it must not restore over it.
run - add --kind task --title "second generation"
sed -i '2s/format=4/format=5/' "$S/todo.md"
live="$(cat "$S/todo.md")"; bak="$(cat "$S/todo.md.bak")"
assert_eq "(the backup is a valid generation)" "VERIFIED:todo" "$(python3 "$CORE" verify todo "$S/todo.md.bak")"
for form in "restore todo" "restore todo --if-damaged"; do
    # shellcheck disable=SC2086
    run - $form
    assert_eq "$form over a newer-format file -> exit 4" "4" "$RC"
    assert_contains "... says it is not damaged" "newer than this writer supports" "$ERR"
    assert_eq "... todo.md untouched" "$live" "$(cat "$S/todo.md")"
    assert_eq "... todo.md.bak untouched" "$bak" "$(cat "$S/todo.md.bak")"
done
# The same file with CR LF line endings is still a newer file, not a damaged one.
sed -i 's/$/\r/' "$S/todo.md"
crlf="$(cat "$S/todo.md"; printf x)"
for form in "restore todo" "restore todo --if-damaged"; do
    # shellcheck disable=SC2086
    run - $form
    assert_eq "$form over a CRLF newer-format file -> exit 4" "4" "$RC"
    assert_eq "... the CRLF file is preserved byte for byte" "$crlf" "$(cat "$S/todo.md"; printf x)"
    assert_eq "... todo.md.bak untouched" "$bak" "$(cat "$S/todo.md.bak")"
done
printf '%s\n' "$live" > "$S/todo.md"
run - add --kind task --title "refused"
assert_eq "a mutation of a newer-format file -> exit 4" "4" "$RC"
assert_contains "... tells the user to update the checkout" "update this checkout" "$ERR"
assert_eq "... todo.md untouched" "$live" "$(cat "$S/todo.md")"
run - list
assert_eq "a read of a newer-format file -> exit 4" "4" "$RC"
# Negative control: a DAMAGED file (not a newer one) is still restored.
sed -i '2s/format=5/format=x/' "$S/todo.md"
run - restore todo --if-damaged
assert_contains "a damaged file is restored as before" "RESTORED:todo.md|recovered/" "$OUT"


# =============================================================================
echo "=== Test 17: recovery-apply (t2299_1) ==="
A=aaaaaaaaaaaa
B=bbbbbbbbbbbb
C=cccccccccccc
rctx() {   # rctx <task> <incarnation> [background]
    printf -- '- background: %s\n- origin: task=%s incarnation=%s\n' "${3:-crashed agent}" "$1" "$2"
}
# ra <stdin|-> <ref> <expect-rev> <incarnation> <state> <outcome> [extra args...]
ra() {
    local input="$1" ref="$2" rev="$3" inc="$4" state="$5" outcome="$6"
    shift 6
    local extra=()
    [[ "$input" == "-" ]] || extra=(--context-file -)
    run "$input" recovery-apply --ref "$ref" --expect-rev "$rev" --incarnation "$inc" \
        --state "$state" --outcome "$outcome" --checked-at now "$@" "${extra[@]}"
}
ctx_inc() {   # the recorded incarnation of item <cN>
    sed -n "/^### $1\$/,/^\$/p" "$S/todo.md" | grep -o 'incarnation=[0-9a-f]*' | cut -d= -f2
}
rev_of() { item_line "$1" | sed -n 's/^- c[0-9]* | rev=\([0-9]*\) .*/\1/p'; }

reset_store
ra "$(rctx t42 $A)" recover:t42 absent $A open "crashed · plan approved" --title "t42 crashed" --group now
assert_eq "absent + no owner -> ADDED with its rev" "ADDED:c1|1" "$OUT"
assert_contains "the item is kind=task derived=script in group now" \
    "kind=task | state=open | group=now | checked_at=2026-11-01T10:00:00Z | ref=recover:t42 | derived=script | outcome=crashed · plan approved | t42 crashed" "$(item_line c1)"
assert_eq "the context records the incarnation" "$A" "$(ctx_inc c1)"
before="$(cat "$S/todo.md")"
ra "$(rctx t42 $A)" recover:t42 absent $A open "again" --title "t42 crashed"
assert_eq "absent + an owner -> STALE with the owner's rev" "STALE:c1|1" "$OUT"
assert_eq "... and nothing was written" "$before" "$(cat "$S/todo.md")"
ra - recover:t44 absent $A open "x" --title "t44"
assert_eq "absent without a context -> exit 2" "2" "$RC"
ra "$(rctx t44 $A)" recover:t44 absent $A open "x"
assert_eq "absent without --title -> exit 2" "2" "$RC"
ra - recover:t99 5 $A open "x"
assert_eq "a rev but no owner -> ABSENT" "ABSENT:recover:t99" "$OUT"
ra - recover:t42 7 $A open "x"
assert_eq "a rev mismatch -> STALE" "STALE:c1|1" "$OUT"
assert_eq "... and nothing was written" "$before" "$(cat "$S/todo.md")"
ra - recover:t42 1 $A open "crashed · work survives"
assert_eq "open item, a changed field -> APPLIED with a fresh rev" "APPLIED:c1|2" "$OUT"
before="$(cat "$S/todo.md")"
ra - recover:t42 2 $A open "crashed · work survives"
assert_eq "nothing differs -> UNCHANGED" "UNCHANGED:c1|2" "$OUT"
assert_eq "... and nothing was written" "$before" "$(cat "$S/todo.md")"
ra "$(rctx t42 $A "crashed agent, more evidence")" recover:t42 2 $A open "crashed · work survives"
assert_eq "a context-only change -> APPLIED with one fresh rev" "APPLIED:c1|3" "$OUT"
ra - recover:t42 3 $A done "reclaimed"
assert_eq "state-only done with the recorded key -> APPLIED" "APPLIED:c1|4" "$OUT"
ra - recover:t42 4 $A open "crashed again"
assert_eq "done + --state open -> REOPENED" "REOPENED:c1|5" "$OUT"
# Dismissal is scoped to the recorded episode.
run - dismiss c1
d1="$(rev_of c1)"
before="$(cat "$S/todo.md")"
ra - recover:t42 "$d1" $B open "x"
assert_eq "dismissed, no context -> KEPT" "KEPT:c1|dismissed" "$OUT"
ra "$(rctx t42 $A)" recover:t42 "$d1" $A open "x"
assert_eq "dismissed, the same incarnation -> KEPT" "KEPT:c1|dismissed" "$OUT"
ra "$(rctx t42 $B)" recover:t42 "$d1" $B done "x"
assert_eq "dismissed, a new incarnation but not --state open -> KEPT" "KEPT:c1|dismissed" "$OUT"
assert_eq "... none of the KEPT replies wrote anything" "$before" "$(cat "$S/todo.md")"
ra "$(rctx t42 $B "crashed on a new claim")" recover:t42 "$d1" $B open "crashed · new claim"
assert_eq "dismissed, a new incarnation, --state open, its context -> REOPENED" "REOPENED:c1|$((d1 + 1))" "$OUT"
assert_contains "... the item is open again" "state=open" "$(item_line c1)"
assert_eq "... the new incarnation is recorded" "$B" "$(ctx_inc c1)"
assert_contains "... with the new evidence" "crashed on a new claim" "$(cat "$S/todo.md")"
assert_eq "... in ONE generation: .bak is the dismissed one" "$before" "$(cat "$S/todo.md.bak")"
# A dismissed recover item with no recorded incarnation (hand-made: no verb can
# produce one) is never reopened.
ra "$(rctx t43 $C)" recover:t43 absent $C open "crashed" --title "t43 crashed"
run - dismiss c2
d2="$(rev_of c2)"
sed -i "s/^- origin: task=t43 incarnation=$C\$/- origin: task=t43/" "$S/todo.md"
assert_eq "(the hand edit kept the store valid)" "VERIFIED:todo" "$(python3 "$CORE" verify todo "$S/todo.md")"
ra "$(rctx t43 $B)" recover:t43 "$d2" $B open "x"
assert_eq "dismissed, no recorded incarnation -> KEPT dismissed_no_incarnation" \
    "KEPT:c2|dismissed_no_incarnation" "$OUT"
# Request refusals: exit 2, nothing written.
before="$(cat "$S/todo.md")"
ra - t42 "$(rev_of c1)" $B open "x"
assert_eq "a non-recover ref -> exit 2" "2" "$RC"
ra - recover:T42 "$(rev_of c1)" $B open "x"
assert_eq "an upper-case recover ref -> exit 2" "2" "$RC"
ra - recover:42 "$(rev_of c1)" $B open "x"
assert_eq "a recover ref without the t -> exit 2" "2" "$RC"
ra "$(rctx t42 $C)" recover:t42 "$(rev_of c1)" $B open "x"
assert_eq "the context's incarnation differs from --incarnation -> exit 2" "2" "$RC"
ra "$(printf -- '- background: x\n- origin: task=t42\n')" recover:t42 "$(rev_of c1)" $B open "x"
assert_eq "a context without an incarnation -> exit 2" "2" "$RC"
for bad in aaaaaaaaaaa AAAAAAAAAAAA gggggggggggg aaaaaaaaaaaaa; do
    ra - recover:t42 "$(rev_of c1)" "$bad" open "x"
    assert_eq "a bad --incarnation '$bad' -> exit 2" "2" "$RC"
done
ra "$(rctx t42 ABCDEF012345)" recover:t42 "$(rev_of c1)" ABCDEF012345 open "x"
assert_eq "an upper-case incarnation in the context -> exit 2" "2" "$RC"
ra - recover:t42 "$(rev_of c1)" $B dismissed "x"
assert_eq "--state dismissed -> exit 2 (dismissal is the user's)" "2" "$RC"
ra - recover:t42 now $B open "x"
assert_eq "a bad --expect-rev -> exit 2" "2" "$RC"
ra - recover:t42 "$(rev_of c1)" $B open "a | b"
assert_eq "an outcome with '|' -> exit 2" "2" "$RC"
assert_eq "... none of the refusals wrote anything" "$before" "$(cat "$S/todo.md")"
# The kind binding: a recover ref is kind=task at parse time too.
cp "$S/todo.md" "$TMP/kind.md"
sed -i 's/^\(- c1 | rev=[0-9]* | \)kind=task/\1kind=action/' "$TMP/kind.md"
python3 "$CORE" verify todo "$TMP/kind.md" >/dev/null 2>"$TMP/err"; RC=$?
assert_eq "a recover: item with kind=action is refused at parse -> exit 4" "4" "$RC"
assert_contains "... naming the binding" "recover: ref needs kind=task" "$(cat "$TMP/err")"
# The dismissal exception never leaks to other refs.
run - add --kind task --title "plain" --ref t70
run - dismiss c3
run "c3|$(rev_of c3)|open|now|
" set-state --batch
assert_eq "a dismissed NON-recover item is still KEPT by a batch" "KEPT:c3|dismissed" "$OUT"

echo "=== Test 17b: episode handoff -- a state-only verdict keeps the recorded episode (t2299_2 contract) ==="
reset_store
ra "$(rctx t50 $A)" recover:t50 absent $A open "crashed" --title "t50 crashed"
ctx_before="$(sed -n '/^### c1$/,/^$/p' "$S/todo.md")"
r="$(rev_of c1)"
before="$(cat "$S/todo.md")"
ra - recover:t50 "$r" $B done "live claim holds it"
assert_eq "negative control: state-only with the OBSERVED key -> exit 2" "2" "$RC"
assert_eq "... and nothing was written" "$before" "$(cat "$S/todo.md")"
ra - recover:t50 "$r" $A done "live claim holds it"
assert_eq "state-only done with the RECORDED key -> APPLIED" "APPLIED:c1|$((r + 1))" "$OUT"
assert_contains "... the item is done" "state=done" "$(item_line c1)"
assert_eq "... its context is byte-identical (still episode A)" "$ctx_before" "$(sed -n '/^### c1$/,/^$/p' "$S/todo.md")"
ra "$(rctx t50 $B "claim B crashed too")" recover:t50 "$((r + 1))" $B open "crashed · claim B"
assert_eq "claim B crashes: B's context + --state open -> REOPENED" "REOPENED:c1|$((r + 2))" "$OUT"
assert_eq "... the recorded incarnation is now B" "$B" "$(ctx_inc c1)"
run - dismiss c1
ra "$(rctx t50 $B "claim B crashed too")" recover:t50 "$(rev_of c1)" $B open "crashed · claim B"
assert_eq "dismissing B, then B again -> KEPT (the dismissal is scoped to B)" "KEPT:c1|dismissed" "$OUT"

echo "=== Test 17c: only recovery-apply moves a recover item's ref or incarnation ==="
reset_store
ra "$(rctx t60 $A)" recover:t60 absent $A open "crashed" --title "t60 crashed"
run - add --kind task --title "plain" --ref t61
fingerprint() { printf '%s|%s' "$(item_line c1 | grep -o 'ref=[^ ]*')" "$(ctx_inc c1)"; }
fp0="$(fingerprint)"
# guard_case <label> <expect: refuse|keep> <stdin|-> <verb args...>
guard_case() {
    local label="$1" expect="$2" input="$3"
    shift 3
    local snap
    snap="$(cat "$S/todo.md")"
    run "$input" "$@"
    if [[ "$expect" == refuse ]]; then
        assert_eq "$label -> exit 2" "2" "$RC"
        assert_eq "... todo.md unchanged" "$snap" "$(cat "$S/todo.md")"
    else
        assert_eq "$label -> exit 0" "0" "$RC"
        assert_eq "... the recover ref and incarnation are unchanged" "$fp0" "$(fingerprint)"
    fi
}
guard_case "add --ref recover:t60" refuse - add --kind task --title "x" --ref recover:t60
guard_case "add --ref recover:t62 (a new one)" refuse - add --kind task --title "x" --ref recover:t62
guard_case "add --ref t60 (the plain task ref)" keep - add --kind task --title "x" --ref t60
guard_case "update c2 --ref recover:t61" refuse - update c2 --ref recover:t61
guard_case "update c1 --ref t60" refuse - update c1 --ref t60
guard_case "update c1 --kind watch" refuse - update c1 --kind watch
guard_case "update c1 --title" keep - update c1 --title "t60 crashed (renamed)"
guard_case "upsert-context c1 with another incarnation" refuse "$(rctx t60 $C)" upsert-context c1
guard_case "upsert-context c1 with no incarnation" refuse "$(ctx "no key")" upsert-context c1
guard_case "upsert-context c1 keeping the incarnation" keep "$(rctx t60 $A "richer map")" upsert-context c1
guard_case "set-state c1 unknown" keep - set-state c1 unknown
guard_case "situation" keep "Crash recovery pending." situation sitrep
guard_case "qa --items c1" keep "Q: resume t60?" qa --items c1
guard_case "dismiss c1" keep - dismiss c1
guard_case "set-state --batch on the dismissed c1" keep "c1|$(rev_of c1)|open|now|
" set-state --batch
assert_eq "... the batch KEPT the dismissed item" "KEPT:c1|dismissed" "$OUT"
ra "$(rctx t60 $B)" recover:t60 "$(rev_of c1)" $B open "crashed again"
assert_eq "recovery-apply (a new episode) reopens it" "REOPENED:c1|$(rev_of c1)" "$OUT"
assert_eq "... and is the one verb that moved the incarnation" "$B" "$(ctx_inc c1)"

echo "=== Test 17d: a recovery-apply killed inside the lock leaves the old generation ==="
reset_store
ra "$(rctx t80 $A)" recover:t80 absent $A open "crashed" --title "t80 crashed"
run - dismiss c1
r="$(rev_of c1)"
cp "$S/todo.md" "$TMP/gen_rec.md"
rctx t80 $B > "$TMP/rec.in"
park_and_kill write:after_backup "$TMP/rec.in" recovery-apply --ref recover:t80 --expect-rev "$r" \
    --incarnation $B --state open --outcome "crashed again" --checked-at now --context-file -
assert_eq "recovery-apply parked after the backup" "write:after_backup" "$KILLED_AT"
assert_eq "killed after the backup -> todo.md is the old generation" "$(cat "$TMP/gen_rec.md")" "$(cat "$S/todo.md")"
ra "$(rctx t80 $B)" recover:t80 "$r" $B open "crashed again"
assert_contains "the next writer reopens it" "REOPENED:c1|" "$OUT"
assert_eq "... with the new incarnation" "$B" "$(ctx_inc c1)"

# =============================================================================
echo "=== Test 18: direction-set ==="
reset_store
run "$(ctx "One." "- direction: alpha")" add --kind task --title one --ref t10 --context-file -
run "$(ctx "Two." "- direction: alpha")" add --kind task --title two --ref t11 --context-file -
run - add --kind task --title three
run - directions
assert_eq "a direction exists from its members alone" \
    "DIRECTION:alpha|-|$(dir_stamp alpha)|-|unknown|never||||2|2|
DIRECTION_MEMBER:alpha|c1|open|task|t10
DIRECTION_MEMBER:alpha|c2|open|task|t11
UNASSIGNED:1|c3" "$OUT"
run - direction-set alpha --expect-rev absent --title "Alpha work" --trails art:trail-a --next 10
A1="$(dir_rev alpha)"
assert_eq "direction-set creates the record (next is normalized)" "DIRECTION:alpha|created|$A1" "$OUT"
assert_eq "the block: heading, nine header lines, blank" "#### alpha | rev=$A1
- title: Alpha work
- rank:
- trails: art:trail-a
- next: t10
- summary:
- digest:
- freshness: unknown
- checked_at: never
- drift:" "$(block alpha)"
before="$(cat "$S/todo.md")"
run - direction-set alpha --expect-rev absent --title "Other"
assert_eq "absent on an existing record -> STALE" "STALE:alpha|$A1" "$OUT"
run - direction-set alpha --expect-rev 999 --title "Other"
assert_eq "a wrong rev -> STALE" "STALE:alpha|$A1" "$OUT"
run - direction-set beta --expect-rev 7 --title "Beta"
assert_eq "a rev for a direction with no record -> ABSENT" "ABSENT:beta" "$OUT"
run - direction-set alpha --expect-rev "$A1" --title "Alpha work" --trails art:trail-a --next t10
assert_eq "the same values -> unchanged, same rev" "DIRECTION:alpha|unchanged|$A1" "$OUT"
for bad in "--title x --next c99" "--trails trail-a" "--trails art:trail-a,art:trail-a" \
           "--next T10" "--digest 0123456789abcdef" ""; do
    # shellcheck disable=SC2086
    run - direction-set alpha --expect-rev "$A1" $bad
    assert_eq "direction-set $bad -> exit 2" "2" "$RC"
done
run - direction-set alpha --expect-rev "$A1" --next core#42
assert_contains "a cross-repo next whose project starts with c is a task ref, not an item id" "DIRECTION:alpha|updated|" "$OUT"
assert_contains "... stored as given" "- next: core#42" "$(block alpha)"
run - direction-set alpha --expect-rev "$(dir_rev alpha)" --next c1
assert_contains "an existing item id is accepted" "DIRECTION:alpha|updated|" "$OUT"
run - direction-set alpha --expect-rev "$(dir_rev alpha)" --next t10
A1="$(dir_rev alpha)"
before="$(cat "$S/todo.md")"
run - direction-set alpha --title "no guard"
assert_eq "direction-set without --expect-rev -> exit 2" "2" "$RC"
run "A summary." direction-set alpha --expect-rev "$A1" --summary-file -
assert_eq "a summary without --digest -> exit 2" "2" "$RC"
run "Two
lines." direction-set alpha --expect-rev "$A1" --summary-file - --digest 0123456789abcdef
assert_eq "a two-line summary -> exit 2" "2" "$RC"
run "A summary." direction-set alpha --expect-rev "$A1" --summary-file - --digest 0123456789abcdef
assert_eq "a digest naming no retained baseline -> exit 2" "2" "$RC"
assert_contains "... names the status" "is missing" "$ERR"
run - direction-set gamma --expect-rev absent --title ""
assert_eq "creating a direction that holds nothing -> exit 2" "2" "$RC"
assert_eq "none of the refusals wrote anything" "$before" "$(cat "$S/todo.md")"
ALPHA="$(snapshot alpha "member: c1|open|t10" "member: c2|open|t11" "task: t10|Ready" "trail: art:trail-a|v1:current" "next: t10|valid")"
retain_snapshot "$ALPHA"
assert_contains "retain-baseline -> RETAINED_BASELINE" "RETAINED_BASELINE:baselines/$DIG.txt|$DIG" "$OUT"
assert_eq "the digest is sha256[:16] of the snapshot" "$(printf '%s\n' "$ALPHA" | sha256sum | cut -c1-16)" "$DIG"
assert_eq "the snapshot is stored verbatim" "$ALPHA" "$(cat "$S/baselines/$DIG.txt")"
retain_snapshot "$ALPHA"
assert_contains "retaining it again is idempotent" "RETAINED_BASELINE:baselines/$DIG.txt|$DIG" "$OUT"
ADIG="$DIG"
set_summary alpha "$ADIG" "Alpha is moving; two tasks open."
A2="$(dir_rev alpha)"
assert_eq "a summary with its baseline -> updated" "DIRECTION:alpha|updated|$A2" "$OUT"
assert_contains "the summary is stored" "- summary: Alpha is moving; two tasks open." "$(block alpha)"
assert_contains "... with its digest" "- digest: $ADIG" "$(block alpha)"
run - directions alpha
assert_contains "directions prints the summary" "DIRECTION_SUMMARY:alpha|Alpha is moving; two tasks open." "$OUT"
run - check-sources
assert_contains "check-sources reports the baseline" "SOURCE_OK:alpha|baselines/$ADIG.txt" "$OUT"
run "$(freshness_line alpha current)" direction-freshness --batch
assert_eq "the refresh marks it current" "FRESHNESS:alpha|current|$(dir_rev alpha)" "$OUT"
run - direction-set alpha --expect-rev "$(dir_rev alpha)" --title "Alpha (renamed)"
assert_eq "a title change keeps the verdict (not a digest input)" "current" "$(dir_field alpha 5)"
run - direction-set alpha --expect-rev "$(dir_rev alpha)" --next t11
assert_eq "a next change resets the freshness" "unknown|never" "$(dir_field alpha 5)|$(dir_field alpha 6)"
run - direction-set alpha --expect-rev "$(dir_rev alpha)" --next t10
run "$(freshness_line alpha current)" direction-freshness --batch
run "" direction-set alpha --expect-rev "$(dir_rev alpha)" --summary-file -
assert_contains "an empty summary clears it" "DIRECTION:alpha|updated|" "$OUT"
assert_eq "... and the digest, and resets the freshness" "||unknown" "$(block alpha | sed -n 's/^- summary:\(.*\)/\1/p')|$(dir_field alpha 7)|$(dir_field alpha 5)"

# =============================================================================
echo "=== Test 18b: direction-assign --batch ==="
reset_store
run "$(ctx "One." "- sources:" "  - commit: abcdef1")" add --kind task --title one --ref t10 --context-file -
run - add --kind task --title two --ref t11
run - add --kind task --title three
ctx1="$("$H" context c1)"
r1="$(item_rev c1)"; r2="$(item_rev c2)"
run "c1|$r1|alpha
c2|$r2|alpha" direction-assign --batch
assert_eq "a mixed batch (with and without a context) assigns both" \
    "ASSIGNED:c1|alpha|$(item_rev c1)
ASSIGNED:c2|alpha|$(item_rev c2)" "$OUT"
assert_eq "both items got a fresh rev" "1" "$([[ "$(item_rev c1)" != "$r1" && "$(item_rev c2)" != "$r2" ]] && echo 1)"
run - context c1
assert_eq "only the direction key changed in an existing context" \
    "$(printf '%s\n' "$ctx1" | sed '/^- origin:/a - direction: alpha')" "$OUT"
run - context c2
assert_eq "the contextless item got exactly the minimal entry" "### c2
- background: No context was recorded for this item; this entry holds its direction.
- origin: date=2026-11-01
- direction: alpha" "$OUT"
before="$(cat "$S/todo.md")"
run "c3|$(item_rev c3)|-" direction-assign --batch
assert_eq "clearing an unassigned contextless item is unchanged" "ASSIGNED:c3|-|$(item_rev c3)" "$OUT"
assert_eq "... writes nothing" "$before" "$(cat "$S/todo.md")"
run - context c3
assert_eq "... and creates no context entry" "NO_CONTEXT:c3" "$OUT"
run "c1|$(item_rev c1)|alpha" direction-assign --batch
assert_eq "re-assigning the same direction is unchanged" "ASSIGNED:c1|alpha|$(item_rev c1)" "$OUT"
assert_eq "... writes nothing" "$before" "$(cat "$S/todo.md")"
run "c3|999|alpha" direction-assign --batch
assert_eq "a stale rev on a contextless item -> STALE" "STALE:c3|$(item_rev c3)" "$OUT"
assert_eq "... writes nothing" "$before" "$(cat "$S/todo.md")"
run "c1|$(item_rev c1)|beta
c3|999|beta
c9|1|beta" direction-assign --batch
assert_eq "one stale line among several: every refusal is named" "STALE:c3|$(item_rev c3)
NOT_FOUND:c9" "$OUT"
assert_eq "... and NOTHING is written (all or nothing)" "$before" "$(cat "$S/todo.md")"
for bad in "c1|1|crashed-agents" "c1|1|Not A Slug" "c1|1|alpha
c1|1|beta" "c1|x|alpha" "c1|1" ""; do
    run "$bad" direction-assign --batch
    assert_eq "direction-assign '$bad' -> exit 2" "2" "$RC"
done
assert_eq "none of them wrote anything" "$before" "$(cat "$S/todo.md")"
A=aaaaaaaaaaaa
run "$(printf -- '- background: died.\n- origin: task=t80 incarnation=%s\n- sources:\n  - task: aitasks/t80_x.md\n' "$A")" \
    recovery-apply --ref recover:t80 --expect-rev absent --incarnation "$A" --state open \
    --outcome "crashed · plan approved" --checked-at now --title "Recover t80" --context-file -
REC="$(printf '%s' "$OUT" | sed -n 's/^ADDED:\(c[0-9]*\)|.*/\1/p')"
before="$(cat "$S/todo.md")"
run "c3|$(item_rev c3)|beta
$REC|$(item_rev "$REC")|beta" direction-assign --batch
assert_eq "a recover: item is never reassigned" "KEPT:$REC|recovery" "$OUT"
assert_eq "... and the rest of that batch is not written either" "$before" "$(cat "$S/todo.md")"
run "$(ctx "Named." "- direction: crashed-agents")" upsert-context c1
assert_eq "context input naming the reserved direction -> exit 2" "2" "$RC"
assert_contains "... says why" "reserved" "$ERR"
# A membership write resets the freshness of the blocks it touches.
ALPHA="$(snapshot alpha "member: c1|open|t10" "member: c2|open|t11")"
retain_snapshot "$ALPHA"
run "Alpha." direction-set alpha --expect-rev absent --summary-file - --digest "$DIG"
run "$(freshness_line alpha current)" direction-freshness --batch
assert_eq "(alpha is current)" "current" "$(dir_field alpha 5)"
arev="$(dir_rev alpha)"
run "c3|$(item_rev c3)|alpha" direction-assign --batch
assert_eq "an assignment into a block reports its new rev" "ASSIGNED:c3|alpha|$(item_rev c3)
DIRECTION:alpha|updated|$(dir_rev alpha)" "$OUT"
assert_eq "... and resets its freshness" "unknown|never" "$(dir_field alpha 5)|$(dir_field alpha 6)"
assert_eq "... with a fresh rev" "1" "$([[ "$(dir_rev alpha)" != "$arev" ]] && echo 1)"
ALPHA3="$(snapshot alpha "member: c1|open|t10" "member: c2|open|t11" "member: c3|open|")"
retain_snapshot "$ALPHA3"
set_summary alpha "$DIG" "Alpha, three items."
run "$(freshness_line alpha current)" direction-freshness --batch
run "$(printf -- '- background: Three, moved by upsert.\n- origin: date=2026-11-01\n')" upsert-context c3 --expect-rev "$(item_rev c3)"
assert_eq "upsert-context moving an item out -> replaced" "CONTEXT:c3|replaced" "$OUT"
assert_eq "... resets that block's freshness too" "unknown" "$(dir_field alpha 5)"
before="$(cat "$S/todo.md")"
run "$(ctx "Stale guard.")" upsert-context c3 --expect-rev 999
assert_eq "upsert-context with a stale rev -> STALE" "STALE:c3|$(item_rev c3)" "$OUT"
assert_eq "... writes nothing" "$before" "$(cat "$S/todo.md")"

# =============================================================================
echo "=== Test 18c: the proposal save sequence -- a change during confirmation ==="
# rule 5: the baseline's store-side lines must match the store when it is saved.
seed_alpha() {
    reset_store
    run "$(ctx "One.")" add --kind task --title one --ref t10 --context-file -
    run "$(ctx "Two.")" add --kind task --title two --ref t11 --context-file -
    run "$(ctx "Three.")" add --kind task --title three --ref t12 --context-file -
    run "c1|$(item_rev c1)|alpha
c2|$(item_rev c2)|alpha" direction-assign --batch
    run - direction-set alpha --expect-rev absent --title "Alpha" --trails art:trail-a --next t10
    ALPHA="$(snapshot alpha "member: c1|open|t10" "member: c2|open|t11" "task: t10|Ready" "trail: art:trail-a|v1:current" "next: t10|valid")"
    retain_snapshot "$ALPHA"
    ADIG="$DIG"
}
seed_alpha
set_summary alpha "$ADIG" "Alpha."
assert_contains "control: with nothing changed the summary saves" "DIRECTION:alpha|updated|" "$OUT"
seed_alpha
run - set-state c2 done --outcome "landed"
before="$(cat "$S/todo.md")"
set_summary alpha "$ADIG" "Alpha."
assert_eq "a member closed during confirmation -> EVIDENCE_CHANGED" "EVIDENCE_CHANGED:alpha|member|c2" "$OUT"
assert_eq "... exit 0, nothing written" "0|$before" "$RC|$(cat "$S/todo.md")"
seed_alpha
run - update c1 --ref t99
before="$(cat "$S/todo.md")"
set_summary alpha "$ADIG" "Alpha."
assert_eq "a member's ref moved -> EVIDENCE_CHANGED" "EVIDENCE_CHANGED:alpha|member|c1" "$OUT"
assert_eq "... nothing written" "$before" "$(cat "$S/todo.md")"
seed_alpha
run "c3|$(item_rev c3)|alpha" direction-assign --batch
before="$(cat "$S/todo.md")"
set_summary alpha "$ADIG" "Alpha."
assert_eq "an item moved in -> EVIDENCE_CHANGED" "EVIDENCE_CHANGED:alpha|member|c3" "$OUT"
assert_eq "... nothing written" "$before" "$(cat "$S/todo.md")"
seed_alpha
run "c2|$(item_rev c2)|-" direction-assign --batch
before="$(cat "$S/todo.md")"
set_summary alpha "$ADIG" "Alpha."
assert_eq "a member moved out -> EVIDENCE_CHANGED" "EVIDENCE_CHANGED:alpha|member|c2" "$OUT"
assert_eq "... nothing written" "$before" "$(cat "$S/todo.md")"
seed_alpha
set_summary alpha "$ADIG" "Alpha." --trails art:trail-b --next t11
assert_eq "trail and next keys must be the record's after this call" \
    "EVIDENCE_CHANGED:alpha|trail|art:trail-a
EVIDENCE_CHANGED:alpha|trail|art:trail-b
EVIDENCE_CHANGED:alpha|next|t11" "$OUT"
retain_snapshot "$(snapshot beta "member: c1|open|t10")"
assert_contains "(a baseline for another direction is retained)" "RETAINED_BASELINE:" "$OUT"
set_summary alpha "$DIG" "Alpha."
assert_eq "a baseline of another direction -> exit 2" "2" "$RC"
assert_contains "... naming the status" "wrong_direction" "$ERR"

echo "=== Test 18d: a refusal after the first assignment (rule 6) ==="
seed_alpha
set_summary alpha "$ADIG" "Alpha, two items."
run "$(freshness_line alpha current)" direction-freshness --batch
assert_eq "(alpha has a saved, current record)" "current" "$(dir_field alpha 5)"
# The proposal: c3 joins alpha. Its baseline is taken for the PROPOSED members.
PROPOSED="$(snapshot alpha "member: c1|open|t10" "member: c2|open|t11" "member: c3|open|t12" "task: t10|Ready" "trail: art:trail-a|v1:current" "next: t10|valid")"
retain_snapshot "$PROPOSED"
PDIG="$DIG"
run "c3|$(item_rev c3)|alpha" direction-assign --batch
STEP_A="$(printf '%s' "$OUT" | sed -n 's/^DIRECTION:alpha|updated|//p')"
assert_eq "step a prints the rev step b needs" "$(dir_rev alpha)" "$STEP_A"
run - set-state c1 done --outcome "landed meanwhile"
before="$(cat "$S/todo.md")"
run "Alpha, three items." direction-set alpha --expect-rev "$STEP_A" --summary-file - --digest "$PDIG"
assert_eq "step b refuses: the evidence moved" "EVIDENCE_CHANGED:alpha|member|c1" "$OUT"
assert_eq "... writing nothing" "$before" "$(cat "$S/todo.md")"
run - directions alpha
assert_contains "the assignment stays" "DIRECTION_MEMBER:alpha|c3|open|task|t12" "$OUT"
assert_contains "... with the PREVIOUS summary" "DIRECTION_SUMMARY:alpha|Alpha, two items." "$OUT"
assert_eq "... and freshness unknown, never a stale 'current'" "unknown" "$(dir_field alpha 5)"
REVISED="$(snapshot alpha "member: c2|open|t11" "member: c3|open|t12" "task: t10|Done" "trail: art:trail-a|v1:current" "next: t10|valid")"
retain_snapshot "$REVISED"
run "Alpha: t10 landed, two items left." direction-set alpha --expect-rev "$STEP_A" --summary-file - --digest "$DIG"
assert_contains "the revised proposal saves with step a's rev" "DIRECTION:alpha|updated|" "$OUT"
run "alpha|$(dir_rev alpha)" direction-rank --expect-ranked -
assert_eq "step c still applies" "RANKED:alpha|1|$(dir_rev alpha)" "$OUT"

# =============================================================================
echo "=== Test 18e: baseline integrity, size and grammar ==="
seed_alpha
set_summary alpha "$ADIG" "Alpha."
BL="$S/baselines/$ADIG.txt"
integrity_case() {   # integrity_case <label> <status> <check-sources line>
    local before
    before="$(cat "$S/todo.md")"
    set_summary alpha "$ADIG" "Alpha, again."
    assert_eq "$1: direction-set -> exit 2" "2" "$RC"
    assert_contains "$1: ... naming the status" "is $2" "$ERR"
    run "$(freshness_line alpha current)" direction-freshness --batch
    assert_eq "$1: 'current' is not published" "KEPT:alpha|baseline_$2" "$OUT"
    run "$(freshness_line alpha stale "member_closed:1:c2")" direction-freshness --batch
    assert_eq "$1: 'stale' with a guessed reason is not either" "KEPT:alpha|baseline_$2" "$OUT"
    assert_eq "$1: nothing was written" "$before" "$(cat "$S/todo.md")"
    run - check-sources
    assert_contains "$1: check-sources reports it unusable" "$3" "$OUT"
}
printf '%s\n' "${ALPHA/Ready/Done}" > "$BL"
integrity_case "a different valid snapshot at the right path" hash_mismatch "SOURCE_INVALID:alpha|baselines/$ADIG.txt|hash_mismatch"
printf '%s' "${ALPHA:0:40}" > "$BL"
integrity_case "a truncated file" hash_mismatch "SOURCE_INVALID:alpha|baselines/$ADIG.txt|hash_mismatch"
rm -f "$BL"; ln -s "$TMP/elsewhere" "$BL"
integrity_case "a symlink" not_regular "SOURCE_INVALID:alpha|baselines/$ADIG.txt|not_regular"
rm -f "$BL"
integrity_case "a deleted file" missing "SOURCE_MISSING:alpha|baselines/$ADIG.txt"
run "$(freshness_line alpha unknown "baseline_unreadable:1")" direction-freshness --batch
assert_eq "an 'unknown' verdict always applies" "FRESHNESS:alpha|unknown|$(dir_rev alpha)" "$OUT"
printf 'damaged\n' > "$BL"
retain_snapshot "$ALPHA"
assert_eq "retaining the right bytes again repairs a damaged file" "$ALPHA" "$(cat "$BL")"
run "$(freshness_line alpha current)" direction-freshness --batch
assert_eq "... and the verdict applies again" "FRESHNESS:alpha|current|$(dir_rev alpha)" "$OUT"
# Size: exactly the limit is retained, one byte more is refused whole.
MAXB="$(python3 -c "import sys; sys.path.insert(0, sys.argv[1]); import sitrep_todo; print(sitrep_todo.MAX_BASELINE_BYTES)" "$PROJECT_DIR/.aitask-scripts/lib")"
gen_snapshot() {   # gen_snapshot <slug> <bytes> > file: a valid snapshot of exactly that size
    python3 - "$1" "$2" <<'PYEOF'
import sys
slug, size = sys.argv[1], int(sys.argv[2])
head = f"sitrep direction baseline v1\ndirection: {slug}\n"
tail = "next: t1|"
lines, n, total = [], 0, len(head)
while True:
    left = size - total - len(tail) - 1
    if 0 <= left <= 120:
        break
    n += 1
    line = f"member: c{n}|open|t{n}\n"
    lines.append(line)
    total += len(line)
sys.stdout.write(head + "".join(lines) + tail + "v" * left + "\n")
PYEOF
}
gen_snapshot big "$MAXB" > "$TMP/at.txt"
gen_snapshot big "$((MAXB + 1))" > "$TMP/over.txt"
assert_eq "(the generated snapshots have the intended sizes)" "$MAXB $((MAXB + 1))" "$(wc -c < "$TMP/at.txt" | tr -d ' ') $(wc -c < "$TMP/over.txt" | tr -d ' ')"
RC=0; OUT="$("$H" retain-baseline < "$TMP/at.txt" 2>"$TMP/err")" || RC=$?
assert_contains "a snapshot of exactly the limit is retained" "RETAINED_BASELINE:baselines/" "$OUT"
nfiles="$(ls "$S/baselines" | wc -l | tr -d ' ')"
before="$(cat "$S/todo.md")"
RC=0; OUT="$("$H" retain-baseline < "$TMP/over.txt" 2>"$TMP/err")" || RC=$?
assert_eq "one byte more -> exit 2" "2" "$RC"
assert_contains "... naming the size" "$((MAXB + 1)) bytes" "$(cat "$TMP/err")"
assert_contains "... and the limit" "limit $MAXB" "$(cat "$TMP/err")"
assert_eq "... no file was created" "$nfiles" "$(ls "$S/baselines" | wc -l | tr -d ' ')"
assert_eq "... and the direction's record is untouched" "$before" "$(cat "$S/todo.md")"
retain_snapshot "$ALPHA"
set_summary alpha "$DIG" "Alpha, after the split."
assert_contains "a snapshot for a smaller member set saves (the split outcome)" "DIRECTION:alpha|updated|" "$OUT"
for bad in "$(snapshot alpha "member: c2|open|t11" "member: c1|open|t10")" \
           "$(snapshot alpha "task: t10|Ready" "task: t10|Done")" \
           "$(snapshot alpha "member: c1|open|t10" "" "task: t10|Ready")" \
           "$(snapshot alpha "member: c1|done|t10")" \
           "$(printf 'not a snapshot\ndirection: alpha')"; do
    nfiles="$(ls "$S/baselines" | wc -l | tr -d ' ')"
    run "$bad"$'\n' retain-baseline
    assert_eq "a snapshot outside the grammar -> exit 2" "2" "$RC"
    assert_eq "... nothing retained" "$nfiles" "$(ls "$S/baselines" | wc -l | tr -d ' ')"
done
run "$(snapshot alpha "member: c1|open|t10")" retain-baseline
assert_eq "a snapshot with no final newline -> exit 2" "2" "$RC"
assert_contains "... says so" "final newline" "$ERR"

# =============================================================================
echo "=== Test 18f: direction-rank ==="
reset_store
for n in a b c; do run "$(ctx "Item $n." "- direction: $n")" add --kind task --title "item $n" --context-file -; done
run - direction-set a --expect-rev absent --title "A"
run - direction-set b --expect-rev absent --title "B"
before="$(cat "$S/todo.md")"
run "" direction-rank --expect-ranked -
assert_eq "empty stdin without --clear -> exit 2" "2" "$RC"
run "a|$(dir_rev a)
a|$(dir_rev a)" direction-rank --expect-ranked -
assert_eq "a duplicate direction -> exit 2" "2" "$RC"
run "a|$(dir_rev a)
zzz|absent" direction-rank --expect-ranked -
assert_eq "an unknown direction -> exit 2" "2" "$RC"
assert_contains "... says why" "unknown direction 'zzz'" "$ERR"
run "a|$(dir_rev a)" direction-rank
assert_eq "direction-rank without --expect-ranked -> exit 2" "2" "$RC"
run "a|$(dir_rev a)
b|999" direction-rank --expect-ranked -
assert_eq "a stale rev on one line -> STALE, nothing else" "STALE:b|$(dir_rev b)" "$OUT"
run "a|absent" direction-rank --expect-ranked -
assert_eq "absent for a direction that has a record -> STALE" "STALE:a|$(dir_rev a)" "$OUT"
assert_eq "none of the refusals wrote anything" "$before" "$(cat "$S/todo.md")"
run "b|$(dir_rev b)
a|$(dir_rev a)
c|absent" direction-rank --expect-ranked -
assert_eq "the whole order is set from one list; a member-only direction gets a block" \
    "RANKED:b|1|$(dir_rev b)
RANKED:a|2|$(dir_rev a)
RANKED:c|3|$(dir_rev c)" "$OUT"
assert_eq "directions lists them in rank order" "b a c" "$("$H" directions | sed -n 's/^DIRECTION:\([^|]*\)|.*/\1/p' | tr '\n' ' ' | sed 's/ $//')"
# The intervening rank addition: the user saw [a]; another session ranks [a, b].
run "" direction-rank --expect-ranked b,a,c --clear
assert_eq "--clear unranks everything (c held nothing else: its block is gone)" \
    "UNRANKED:a|$(dir_rev a)
UNRANKED:b|$(dir_rev b)
UNRANKED:c|-" "$OUT"
run "a|$(dir_rev a)" direction-rank --expect-ranked -
SEEN_A="$(dir_rev a)"
run "a|$SEEN_A
b|$(dir_rev b)" direction-rank --expect-ranked a
assert_eq "(another session ranks b second; a's rev does not move)" "$SEEN_A" "$(dir_rev a)"
before="$(cat "$S/todo.md")"
run "a|$SEEN_A" direction-rank --expect-ranked a
assert_eq "the original request, made for [a], is refused" "STALE_ORDER:a,b" "$OUT"
assert_eq "... and b keeps rank 2" "2|$before" "$(dir_field b 4)|$(cat "$S/todo.md")"
run "" direction-rank --expect-ranked a --clear
assert_eq "--clear made for [a] is refused the same way" "STALE_ORDER:a,b" "$OUT"
assert_eq "... nothing written" "$before" "$(cat "$S/todo.md")"
run "a|$SEEN_A" direction-rank --expect-ranked a,b
assert_eq "control: with the order it now sees, the same request applies" \
    "RANKED:a|1|$(dir_rev a)
UNRANKED:b|$(dir_rev b)" "$OUT"
run "a|$(dir_rev a)" direction-rank --expect-ranked a
assert_eq "an identical order writes nothing" "RANKED:a|1|$SEEN_A" "$OUT"
# direction-remove closes the gap.
run "b|$(dir_rev b)
a|$(dir_rev a)
c|absent" direction-rank --expect-ranked a
run - direction-remove b --expect-rev 999
assert_eq "direction-remove with a stale rev -> STALE" "STALE:b|$(dir_rev b)" "$OUT"
run - direction-remove zzz --expect-rev 5
assert_eq "direction-remove of nothing -> ABSENT" "ABSENT:zzz" "$OUT"
run - direction-remove b --expect-rev "$(dir_rev b)"
assert_eq "direction-remove deletes the block and closes the rank gap" \
    "DIRECTION_REMOVED:b|1
RANKED:a|1|$(dir_rev a)
RANKED:c|2|$(dir_rev c)" "$OUT"
run - directions b
assert_eq "the removed direction stays listed from its member, with no record" \
    "DIRECTION:b|-|$(dir_stamp b)|-|unknown|never||||1|1|
DIRECTION_MEMBER:b|c2|open|task|" "$OUT"
assert_eq "the store verifies" "VERIFIED:todo" "$(python3 "$CORE" verify todo "$S/todo.md")"

# =============================================================================
echo "=== Test 18g: direction-freshness --batch ==="
seed_alpha
set_summary alpha "$ADIG" "Alpha."
agent="$(agent_fields alpha)"
run "$(freshness_line alpha stale "member_closed:2:c1+c2, trail_stale:1:art:trail-a")" direction-freshness --batch
F1="$(dir_rev alpha)"
assert_eq "a stale verdict is stored" "FRESHNESS:alpha|stale|$F1" "$OUT"
assert_eq "... with its reasons" "- drift: member_closed:2:c1+c2, trail_stale:1:art:trail-a" "$(block alpha | grep '^- drift:')"
assert_eq "the agent-written fields are byte-identical" "$agent" "$(agent_fields alpha)"
run - directions alpha
assert_contains "directions prints count and sample" "DIRECTION_DRIFT:alpha|member_closed|2|c1+c2" "$OUT"
before="$(cat "$S/todo.md")"
run "$(printf 'alpha|%s|%s|stale|2026-11-01T10:00:00Z|member_closed:2:c1+c2,trail_stale:1:art:trail-a\n' "$F1" "$(dir_stamp alpha)")" direction-freshness --batch
assert_eq "an equal line keeps the rev" "FRESHNESS:alpha|stale|$F1" "$OUT"
assert_eq "... and writes nothing" "$before" "$(cat "$S/todo.md")"
run "zzz|5|0123456789abcdef|unknown|now|" direction-freshness --batch
assert_eq "a direction with no block -> NOT_FOUND" "NOT_FOUND:zzz" "$OUT"
for bad in "alpha|$F1|$(dir_stamp alpha)|current|now|x:1" "alpha|$F1|$(dir_stamp alpha)|stale|now|" \
           "alpha|$F1|nostamp|unknown|now|" "alpha|$F1|$(dir_stamp alpha)|fresh|now|" \
           "alpha|$F1|$(dir_stamp alpha)|stale|now|x:1,x:2" "alpha|$F1|$(dir_stamp alpha)|stale|now|x:1:a+b" \
           "alpha|$F1|$(dir_stamp alpha)|stale|now|x:9:a+b+c+d" "alpha|$F1|$(dir_stamp alpha)|unknown|never|"; do
    run "$bad" direction-freshness --batch
    assert_eq "freshness line '$bad' -> exit 2" "2" "$RC"
done
assert_eq "none of them wrote anything" "$before" "$(cat "$S/todo.md")"
run - direction-set beta --expect-rev absent --title "Beta"
run "$(freshness_line beta current)" direction-freshness --batch
assert_eq "'current' for a record with no baseline -> KEPT" "KEPT:beta|no_baseline" "$OUT"
run "$(freshness_line beta stale "never_summarized")" direction-freshness --batch
assert_eq "'stale' (never summarised) applies without one" "FRESHNESS:beta|stale|$(dir_rev beta)" "$OUT"
# The intervening input change: the rev does not cover membership or state.
fresh_case() {   # the verdict line was computed BEFORE the mutation the caller ran
    local line="$1" label="$2" before
    before="$(cat "$S/todo.md")"
    run "$line" direction-freshness --batch
    assert_eq "$label -> STALE with the current rev and stamp" "STALE:alpha|$(dir_rev alpha)|$(dir_stamp alpha)" "$OUT"
    assert_eq "$label: nothing written" "$before" "$(cat "$S/todo.md")"
}
seed_alpha; set_summary alpha "$ADIG" "Alpha."
LINE="$(freshness_line alpha current)"
run "$LINE" direction-freshness --batch
assert_eq "control: with no change in between the verdict applies" "FRESHNESS:alpha|current|$(dir_rev alpha)" "$OUT"
seed_alpha; set_summary alpha "$ADIG" "Alpha."
LINE="$(freshness_line alpha current)"; SEEN_REV="$(dir_rev alpha)"
run - set-state c2 done --outcome "landed"
assert_eq "(a member's state change leaves the direction rev alone)" "$SEEN_REV" "$(dir_rev alpha)"
fresh_case "$LINE" "a member's set-state between snapshot and batch"
seed_alpha; set_summary alpha "$ADIG" "Alpha."
LINE="$(freshness_line alpha current)"
run "$(ctx "Three, joining." "- direction: alpha")" upsert-context c3
fresh_case "$LINE" "an item moved in by upsert-context"
seed_alpha; set_summary alpha "$ADIG" "Alpha."
LINE="$(freshness_line alpha current)"
run "$(ctx "Two, leaving.")" upsert-context c2
fresh_case "$LINE" "a member moved out"

# =============================================================================
echo "=== Test 18h: more causes than reasons fit; a legal long trail handle; an oversized group ==="
seed_alpha; set_summary alpha "$ADIG" "Alpha."
AGG="$(python3 -c "
import sys; sys.path.insert(0, sys.argv[1]); import sitrep_todo as st
pairs = [('member_closed', 'c%d' % i) for i in range(20, 0, -1)] + [('trail_stale', 'art:trail-a'), ('task_archived', 't10')]
print(','.join(st.render_reason(r) for r in st.aggregate_drift(pairs)))" "$PROJECT_DIR/.aitask-scripts/lib")"
assert_eq "22 causes aggregate into three reasons" "member_closed:20:c1+c2+c3,trail_stale:1:art:trail-a,task_archived:1:t10" "$AGG"
run "$(freshness_line alpha stale "$AGG")" direction-freshness --batch
assert_eq "the verdict above the cause count persists as stale" "FRESHNESS:alpha|stale|$(dir_rev alpha)" "$OUT"
run - directions alpha
assert_contains "... with the count as the overflow indication" "DIRECTION_DRIFT:alpha|member_closed|20|c1+c2+c3" "$OUT"
LONG="art:trail-$(printf 'x%.0s' $(seq 1 122))"
assert_eq "(the handle is the longest legal one)" "132" "${#LONG}"
seed_alpha
run - direction-set alpha --expect-rev "$(dir_rev alpha)" --trails "$LONG"
assert_contains "direction-set takes a 132-character handle" "DIRECTION:alpha|updated|" "$OUT"
retain_snapshot "$(snapshot alpha "member: c1|open|t10" "member: c2|open|t11" "trail: $LONG|v1:unreadable" "next: t10|valid")"
assert_contains "a baseline trail line takes it" "RETAINED_BASELINE:" "$OUT"
set_summary alpha "$DIG" "Alpha, long handle."
assert_contains "... and the summary saves against it" "DIRECTION:alpha|updated|" "$OUT"
run "$(freshness_line alpha stale "trail_unreadable:1:$LONG")" direction-freshness --batch
assert_eq "it is a valid drift sample key" "FRESHNESS:alpha|stale|$(dir_rev alpha)" "$OUT"
assert_eq "... and round-trips" "- drift: trail_unreadable:1:$LONG" "$(block alpha | grep '^- drift:')"
assert_eq "the store verifies" "VERIFIED:todo" "$(python3 "$CORE" verify todo "$S/todo.md")"
before="$(cat "$S/todo.md")"
run - direction-set alpha --expect-rev "$(dir_rev alpha)" --trails "${LONG}x"
assert_eq "133 characters: direction-set -> exit 2" "2" "$RC"
run "$(snapshot alpha "trail: ${LONG}x|v1:current")"$'\n' retain-baseline
assert_eq "133 characters: retain-baseline -> exit 2" "2" "$RC"
run "$(freshness_line alpha stale "trail_unreadable:1:${LONG}x")" direction-freshness --batch
assert_eq "133 characters: a drift key -> exit 2" "2" "$RC"
assert_eq "none of them wrote anything" "$before" "$(cat "$S/todo.md")"
ONLY_LONG="$(python3 -c "
import sys; sys.path.insert(0, sys.argv[1]); import sitrep_todo as st
print(','.join(st.render_reason(r) for r in st.aggregate_drift([('trail_stale', sys.argv[2] + '=tasks_changed'), ('trail_stale', sys.argv[2] + '=wave_moved')])))" "$PROJECT_DIR/.aitask-scripts/lib" "$LONG")"
assert_eq "keys that do not fit are left out, the count stays" "trail_stale:2" "$ONLY_LONG"
run "$(freshness_line alpha stale "$ONLY_LONG")" direction-freshness --batch
assert_eq "the count-only form persists as stale" "FRESHNESS:alpha|stale|$(dir_rev alpha)" "$OUT"
# crashed-agents cannot be split: its members are derived and never reassigned.
reset_store
A=aaaaaaaaaaaa
run "$(printf -- '- background: died.\n- origin: task=t80 incarnation=%s\n- sources:\n  - task: aitasks/t80_x.md\n' "$A")" \
    recovery-apply --ref recover:t80 --expect-rev absent --incarnation "$A" --state open \
    --outcome "crashed · plan approved" --checked-at now --title "Recover t80" --context-file -
run - direction-set crashed-agents --expect-rev absent --title "Crashed agents"
run "crashed-agents|$(dir_rev crashed-agents)" direction-rank --expect-ranked -
gen_snapshot crashed-agents "$((MAXB + 1))" > "$TMP/over.txt"
RC=0; OUT="$("$H" retain-baseline < "$TMP/over.txt" 2>"$TMP/err")" || RC=$?
assert_eq "its oversized snapshot is refused like any other" "2" "$RC"
members="$("$H" directions crashed-agents | grep '^DIRECTION_MEMBER:')"
run "$(freshness_line crashed-agents unknown "baseline_too_large:1")" direction-freshness --batch
assert_eq "the supported outcome: unknown with a size reason" "FRESHNESS:crashed-agents|unknown|$(dir_rev crashed-agents)" "$OUT"
assert_eq "... the reason is stored" "- drift: baseline_too_large:1" "$(block crashed-agents | grep '^- drift:')"
assert_eq "... membership is still derived" "$members" "$("$H" directions crashed-agents | grep '^DIRECTION_MEMBER:')"
assert_eq "... the rank and title stay" "1|Crashed agents" "$(dir_field crashed-agents 4)|$(dir_field crashed-agents 12)"
run "$(freshness_line crashed-agents current)" direction-freshness --batch
assert_eq "... and it can never read current" "KEPT:crashed-agents|no_baseline" "$OUT"

# =============================================================================
echo "=== Test 18i: situation text and the record; existing verbs on a format-4 store ==="
reset_store
run "$(ctx "One." "- direction: alpha")" add --kind task --title one --ref t10 --context-file -
run "Alpha is moving." situation alpha
assert_eq "situation creates a block" "SITUATION:alpha|set" "$OUT"
S1="$(dir_rev alpha)"
run "Alpha is moving." situation alpha
assert_eq "the same text again writes nothing" "$S1" "$(dir_rev alpha)"
run "Alpha moved on." situation alpha
assert_eq "new text bumps the block's rev" "1" "$([[ "$(dir_rev alpha)" != "$S1" ]] && echo 1)"
run - direction-set alpha --expect-rev "$(dir_rev alpha)" --title "Alpha"
assert_contains "the record keeps the situation text" "Alpha moved on." "$(block alpha)"
run "" situation alpha
assert_eq "empty situation removes the text" "SITUATION:alpha|removed" "$OUT"
assert_contains "... and keeps the record" "- title: Alpha" "$(block alpha)"
assert_eq "... with no text left" "11" "$(block alpha | wc -l | tr -d ' ')"
run "" situation alpha
assert_eq "removing it again -> absent" "SITUATION:alpha|absent" "$OUT"
run - directions alpha
assert_contains "the member still names the direction" "DIRECTION_MEMBER:alpha|c1|open|task|t10" "$OUT"
run "Text only." situation beta
run "" situation beta
assert_eq "a text-only block goes with its text" "" "$(block beta)"
run "Recovery." situation crashed-agents
assert_eq "the reserved direction takes situation text" "SITUATION:crashed-agents|set" "$OUT"
run - set-state c1 done --outcome ok --expect-rev "$(item_rev c1)"
assert_contains "set-state works on a format-4 store" "STATE:c1|done|" "$OUT"
run "c1|$(item_rev c1)|open|now|" set-state --batch
assert_contains "set-state --batch works" "STATE:c1|open|" "$OUT"
run - dismiss c1 --outcome "user: no"
assert_contains "dismiss works" "STATE:c1|dismissed|" "$OUT"
run "Q: ok?" qa --items c1
assert_eq "qa works" "0" "$RC"
run - restore todo
assert_contains "restore works on a format-4 store" "RESTORED:todo.md|recovered/" "$OUT"
assert_eq "the restored store verifies" "VERIFIED:todo" "$(python3 "$CORE" verify todo "$S/todo.md")"
REV_NOW="$(cat "$S/next_rev")"
HIGH="$(grep -o 'rev=[0-9]*' "$S/todo.md" "$S/todo.md.bak" "$S"/recovered/* | sed 's/.*rev=//' | sort -n | tail -1)"
assert_eq "restore pins next_rev above every rev ever seen, direction revs included" "1" "$([[ "$REV_NOW" -gt "$HIGH" ]] && echo 1)"

echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ "$FAIL" -eq 0 ]]; then
    echo "ALL TESTS PASSED"
fi
[[ "$FAIL" -eq 0 ]]
