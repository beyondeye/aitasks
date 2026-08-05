#!/usr/bin/env bash
# test_shadow_rejected.sh - Tests for the shadow concern-rejection store helper
# (t1427_1).
#
# The store is the substrate the concern picker (t1427_2) and the shadow's
# concern producers (t1427_3) both build on: rejections must survive the modal,
# the TUI process, and a TUI restart, and their entry ids must be stable enough
# that a second TUI session's stale `remove` cannot un-reject the wrong concern.
#
# Modelled on tests/test_agent_marks_concurrency.sh: background writers + `wait`,
# a live-pid lock holder for the LOCK_BUSY path, and per-contender stderr dumped
# on an anomaly so a rare race is diagnosable rather than an anonymous flake.
#
# Everything is scoped to a temp store via AITASK_SHADOW_DIR, from which the
# helper also derives its lock dir — so this suite never touches the repo's real
# .aitask-shadow/ and needs no `cd`.
#
# Run: bash tests/test_shadow_rejected.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

H="$PROJECT_DIR/.aitask-scripts/aitask_shadow_rejected.sh"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/ait_shadow_rej_XXXXXX")"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

export AITASK_SHADOW_DIR="$TMP/shadow"

# --- helpers ----------------------------------------------------------------

store_of()  { printf '%s/%s/rejected.md' "$AITASK_SHADOW_DIR" "$1"; }
lockd_of()  { printf '%s.lockd' "$(store_of "$1")"; }

entry_ids() { sed -n 's/^### r\([0-9][0-9]*\) |.*/r\1/p' "$(store_of "$1")" 2>/dev/null; }
entry_count() { entry_ids "$1" | grep -c . 2>/dev/null || true; }
header_next() {
    sed -n 's/^<!-- next_id: \([0-9][0-9]*\) -->$/\1/p' "$(store_of "$1")" 2>/dev/null | head -n1
}

reset_store() { rm -rf "$AITASK_SHADOW_DIR"; }

# Hold a task's lock with a LIVE pid so registry_lock.sh refuses to steal it
# (it steals only a provably-dead holder, never by age). Sets HOLDER_PID.
hold_lock() {
    local lockd; lockd="$(lockd_of "$1")"
    mkdir -p "$lockd"
    sleep 30 &
    HOLDER_PID=$!
    echo "$HOLDER_PID" > "$lockd/pid"
    echo "held-by-test" > "$lockd/owner"
}
release_held_lock() {
    kill "$HOLDER_PID" 2>/dev/null || true
    wait "$HOLDER_PID" 2>/dev/null || true
    rm -rf "$(lockd_of "$1")"
}

echo "=== Test 1: add/list round-trip ==="
reset_store
printf '%s\n' \
    '- [high | Step 7 guard] The guard double-commits when the lock was held.' \
    '- [medium | parser module] Multi-block accumulation is undefined.' \
    | "$H" add 1427 --producer plan-challenge > "$TMP/t1.out" 2>&1
assert_eq "add of two markers reports ADDED:2" "ADDED:2" "$(cat "$TMP/t1.out")"
assert_eq "ids assigned in order" "r1
r2" "$(entry_ids 1427)"
assert_eq "header advanced to next free id" "3" "$(header_next 1427)"

listed="$("$H" list 1427)"
assert_contains "list prints the first marker verbatim" \
    '- [high | Step 7 guard] The guard double-commits when the lock was held.' "$listed"
assert_not_contains "list strips the machine header" "next_id" "$listed"
assert_contains "list keeps the entry headers (shadow prompt context)" \
    "### r2 " "$listed"

echo
echo "=== Test 2: --machine protocol survives |-laden bodies ==="
reset_store
printf '%s\n' '- [medium | parser] Multi-block accum | undefined | really.' \
    | "$H" add 77 --producer impl-challenge >/dev/null
mout="$("$H" list 77 --machine)"
assert_eq "one REJECTED line per entry" "1" "$(printf '%s\n' "$mout" | grep -c '^REJECTED:')"
# The marker line is LAST precisely because it contains `|`; consumers split
# into exactly 4 fields and keep the remainder whole.
id_f="$(printf '%s' "$mout" | sed 's/^REJECTED://' | cut -d'|' -f1)"
ts_f="$(printf '%s' "$mout" | sed 's/^REJECTED://' | cut -d'|' -f2)"
pr_f="$(printf '%s' "$mout" | sed 's/^REJECTED://' | cut -d'|' -f3)"
mk_f="$(printf '%s' "$mout" | sed 's/^REJECTED://' | cut -d'|' -f4-)"
assert_eq "field 1 is the entry id" "r1" "$id_f"
assert_contains "field 2 is an ISO-8601 UTC stamp" "T" "$ts_f"
assert_eq "field 3 is the producer" "impl-challenge" "$pr_f"
assert_eq "remainder is the marker line, |-chars intact" \
    '- [medium | parser] Multi-block accum | undefined | really.' "$mk_f"

echo
echo "=== Test 3: NO_REJECTIONS sentinel ==="
reset_store
assert_eq "missing store -> sentinel" "NO_REJECTIONS" "$("$H" list 404)"
assert_eq "missing store -> exit 0" "0" "$("$H" list 404 >/dev/null 2>&1; echo $?)"
assert_eq "missing store -> sentinel in --machine too" "NO_REJECTIONS" "$("$H" list 404 --machine)"

echo
echo "=== Test 4: remove reports found and not-found ==="
reset_store
printf '%s\n' '- [low | a] one.' '- [low | b] two.' | "$H" add 88 >/dev/null
rout="$("$H" remove 88 r1 r99)"
assert_contains "found id reported" "REMOVED:r1" "$rout"
assert_contains "missing id reported" "NOT_FOUND:r99" "$rout"
assert_eq "only the named entry was dropped" "r2" "$(entry_ids 88)"
# Bare and r-prefixed ids are both accepted.
assert_contains "bare id accepted" "REMOVED:r2" "$("$H" remove 88 2)"

echo
echo "=== Test 5: add input validation refuses BEFORE taking the lock ==="
reset_store
printf '%s\n' '- [low | seed] seed.' | "$H" add 99 >/dev/null
cp "$(store_of 99)" "$TMP/t5_before.md"

for label in empty whitespace; do
    case "$label" in
        empty)      input="" ;;
        whitespace) input="$(printf '   \n\t\n')" ;;
    esac
    out="$(printf '%s' "$input" | "$H" add 99 2>&1)"; rc=$?
    assert_eq "$label stdin -> exit 2" "2" "$rc"
    assert_not_contains "$label stdin -> no ADDED result" "ADDED:" "$out"
    assert_eq "$label stdin -> store byte-identical" "0" \
        "$(cmp -s "$TMP/t5_before.md" "$(store_of 99)"; echo $?)"
    assert_dir_not_exists "$label stdin -> lock never acquired" "$(lockd_of 99)"
done

out="$(echo 'not a marker line' | "$H" add 99 2>&1)"; rc=$?
assert_eq "non-marker line -> exit 2" "2" "$rc"
assert_eq "non-marker line -> store byte-identical" "0" \
    "$(cmp -s "$TMP/t5_before.md" "$(store_of 99)"; echo $?)"
assert_dir_not_exists "non-marker line -> lock never acquired" "$(lockd_of 99)"

echo
echo "=== Test 6: malformed task ids are the one hard error ==="
reset_store
for bad in abc 1_2_3 12_ _3 ""; do
    rc="$(echo '- [low | x] y' | "$H" add "$bad" >/dev/null 2>&1; echo $?)"
    assert_eq "malformed id '$bad' -> exit 2" "2" "$rc"
done
assert_eq "leading t is stripped, not rejected" "ADDED:1" \
    "$(echo '- [low | x] y' | "$H" add t1427_9)"
assert_eq "t-prefixed id writes to the bare-id store" "r1" "$(entry_ids 1427_9)"

echo
echo "=== Test 7: a held lock reports LOCK_BUSY and writes NOTHING ==="
reset_store
printf '%s\n' '- [low | seed] seed.' | "$H" add 3131 >/dev/null
cp "$(store_of 3131)" "$TMP/t7_before.md"
hold_lock 3131

out="$(echo '- [high | y] z' | "$H" add 3131 2>&1)"; rc=$?
assert_eq "held lock -> LOCK_BUSY on stdout" "LOCK_BUSY" "$out"
assert_eq "held lock -> exit 3" "3" "$rc"
assert_eq "held lock -> store byte-identical (never wrote unlocked)" "0" \
    "$(cmp -s "$TMP/t7_before.md" "$(store_of 3131)"; echo $?)"

rout="$("$H" remove 3131 r1 2>&1)"; rrc=$?
assert_eq "held lock -> remove also refuses" "LOCK_BUSY" "$rout"
assert_eq "held lock -> remove exits 3" "3" "$rrc"

release_held_lock 3131
assert_eq "lock released -> add succeeds again" "ADDED:1" \
    "$(echo '- [low | y] z' | "$H" add 3131)"
assert_dir_not_exists "lock dir released after normal exit" "$(lockd_of 3131)"

echo
echo "=== Test 8: prune happy path and absent cases ==="
reset_store
printf '%s\n' '- [low | x] y' | "$H" add 4242 >/dev/null
assert_eq "prune of a populated store" "PRUNED:4242" "$("$H" prune 4242)"
assert_dir_not_exists "store dir removed" "$AITASK_SHADOW_DIR/4242"
assert_eq "prune of a missing task dir" "PRUNED:absent" "$("$H" prune 4242)"
assert_eq "prune of a missing task dir -> exit 0" "0" \
    "$("$H" prune 4242 >/dev/null 2>&1; echo $?)"

# The first archive in a repo that never created the store root. Canonicalizing
# `<root>/<id>` fails when BOTH components are missing, so an own-root check
# placed before this absence check aborts under `set -e` instead of reporting
# absent — this is the regression pin for that ordering.
out="$(AITASK_SHADOW_DIR="$TMP/never_created" "$H" prune 7777 2>&1)"; rc=$?
assert_eq "store ROOT absent -> PRUNED:absent" "PRUNED:absent" "$out"
assert_eq "store ROOT absent -> exit 0, not an abort" "0" "$rc"

echo
echo "=== Test 9 [entry_id_no_reuse]: a removed id is never re-issued ==="
reset_store
printf '%s\n' '- [low | a] one.' '- [low | b] two.' | "$H" add 55 >/dev/null
assert_eq "seeded r1,r2" "r1
r2" "$(entry_ids 55)"

# Removing the HIGHEST entry is the case a max()+1 scheme gets wrong.
"$H" remove 55 r2 >/dev/null
printf '%s\n' '- [low | c] three.' | "$H" add 55 >/dev/null
assert_eq "next add gets r3, NOT the freed r2" "r1
r3" "$(entry_ids 55)"
assert_eq "header advanced past the removed id" "4" "$(header_next 55)"

# Draining every entry must not reset the counter either.
"$H" remove 55 r1 r3 >/dev/null
assert_eq "store fully drained" "" "$(entry_ids 55)"
assert_eq "header survives a full drain" "4" "$(header_next 55)"
printf '%s\n' '- [low | d] four.' | "$H" add 55 >/dev/null
assert_eq "add after a full drain still advances" "r4" "$(entry_ids 55)"

# remove must never lower the mark.
before_next="$(header_next 55)"
"$H" remove 55 r4 >/dev/null
assert_eq "remove leaves the header untouched" "$before_next" "$(header_next 55)"

echo
echo "=== Test 10 [empty_store_removal_guard]: removing the LAST entry ==="
reset_store
printf '%s\n' '- [low | only] the only one.' | "$H" add 66 >/dev/null
out="$("$H" remove 66 r1 2>&1)"; rc=$?
assert_eq "removing the last entry exits 0" "0" "$rc"
assert_contains "removing the last entry reports REMOVED" "REMOVED:r1" "$out"
assert_file_exists "store file survives as a header-only file" "$(store_of 66)"
# ait_atomic_render refuses a zero-byte result, so the header is what keeps the
# drained store writable at all.
assert_eq "drained store is NOT zero-byte" "0" \
    "$([ -s "$(store_of 66)" ] && echo 0 || echo 1)"
assert_eq "drained store reports the sentinel" "NO_REJECTIONS" "$("$H" list 66)"
assert_eq "drained store reports the sentinel in --machine" "NO_REJECTIONS" \
    "$("$H" list 66 --machine)"

echo
echo "=== Test 11 [own_root_guard_reachable_trigger]: prune stays under its root ==="
reset_store
mkdir -p "$AITASK_SHADOW_DIR" "$TMP/outside"
echo "precious" > "$TMP/outside/keepme.txt"
# A traversal id can never reach the realpath guard — the id regex rejects it
# first — so the guard is exercised through a symlinked store dir instead.
ln -s "$TMP/outside" "$AITASK_SHADOW_DIR/9999"
out="$("$H" prune 9999 2>&1)"; rc=$?
assert_eq "symlinked store dir -> refused with exit 4" "4" "$rc"
assert_contains "refusal names the resolved target" "outside" "$out"
assert_file_exists "the outside file was NOT deleted" "$TMP/outside/keepme.txt"
assert_eq "the outside file is untouched" "precious" "$(cat "$TMP/outside/keepme.txt")"
rm -f "$AITASK_SHADOW_DIR/9999"

# The second guard, asserted separately: the id regex, which fires earlier.
rc="$("$H" prune '../evil' >/dev/null 2>&1; echo $?)"
assert_eq "traversal id -> rejected by the id regex with exit 2" "2" "$rc"

echo
echo "=== Test 12 [archival_prune_nonblocking]: prune never stalls archival ==="
reset_store
printf '%s\n' '- [low | x] y' | "$H" add 2121 >/dev/null
cp "$(store_of 2121)" "$TMP/t12_before.md"
hold_lock 2121

t0="$(date +%s)"
out="$("$H" prune 2121 2>&1)"; rc=$?
t1="$(date +%s)"
elapsed=$(( t1 - t0 ))

assert_eq "contended prune -> LOCK_BUSY" "LOCK_BUSY" "$out"
assert_eq "contended prune -> exit 3" "3" "$rc"
assert_eq "contended prune deleted NOTHING" "0" \
    "$(cmp -s "$TMP/t12_before.md" "$(store_of 2121)"; echo $?)"
assert_dir_exists "contended prune left the store dir in place" "$AITASK_SHADOW_DIR/2121"
# PRUNE_LOCK_TIMEOUT is 2s vs the 10s mutation timeout: archival must give up
# fast rather than block behind a TUI that is mid-write.
assert_eq "contended prune returned well inside the mutation timeout" "0" \
    "$([ "$elapsed" -le 5 ] && echo 0 || echo "1 (took ${elapsed}s)")"

release_held_lock 2121
assert_eq "prune succeeds once the lock is free" "PRUNED:2121" "$("$H" prune 2121)"

echo
echo "=== Test 13 [contended_append_negative_control]: concurrent appends ==="
reset_store

# --- the real thing: the mutex must make this timing-independent -------------
"$H" add 31 --producer w1 <<<'- [high | alpha] first writer.'  >"$TMP/t13_o1.log" 2>"$TMP/t13_e1.log" &
"$H" add 31 --producer w2 <<<'- [high | beta] second writer.' >"$TMP/t13_o2.log" 2>"$TMP/t13_e2.log" &
wait

got="$(entry_count 31)"
if [ "$got" != "2" ]; then
    echo "DIAG: concurrent-append anomaly (got $got, want 2) — contender output follows:"
    for i in 1 2; do
        echo "--- writer $i stdout ---"; cat "$TMP/t13_o$i.log"
        echo "--- writer $i stderr ---"; cat "$TMP/t13_e$i.log"
    done
    echo "--- store ---"; cat "$(store_of 31)" 2>/dev/null
fi
assert_eq "two concurrent adds -> both entries land (no lost update)" "2" "$got"
assert_eq "and they get distinct, sequential ids" "r1
r2" "$(entry_ids 31)"
assert_eq "header reflects both" "3" "$(header_next 31)"
assert_contains "first writer's body survived" "first writer." "$(cat "$(store_of 31)")"
assert_contains "second writer's body survived" "second writer." "$(cat "$(store_of 31)")"
assert_dir_not_exists "lock dir released after contention" "$(lockd_of 31)"

# --- the negative control ----------------------------------------------------
# Proves the assertion above discriminates. The lock bypass lives ENTIRELY in
# this fixture: the shipped helper must never carry a runtime switch that can
# skip its mutex (registry_lock.sh: "Never proceed unlocked … do NOT relax").
# So we build a throwaway tree holding the helper UNMODIFIED and substitute the
# two libs that jointly express one condition — "unsynchronized concurrent
# read-modify-write". The helper resolves libs via "$SCRIPT_DIR/lib/…", so it
# picks them up with zero edits and nothing under .aitask-scripts/ is touched.
NEG="$TMP/negctrl"
mkdir -p "$NEG/lib"
cp "$H" "$NEG/aitask_shadow_rejected.sh"
cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" "$NEG/lib/"
chmod +x "$NEG/aitask_shadow_rejected.sh"

cat > "$NEG/lib/registry_lock.sh" <<'STUB'
#!/usr/bin/env bash
# NEGATIVE-CONTROL STUB — fixture-only. Removes serialization so the suite can
# demonstrate the lost update its real counterpart prevents.
[[ -n "${_AIT_REGISTRY_LOCK_LOADED:-}" ]] && return 0
_AIT_REGISTRY_LOCK_LOADED=1
registry_lock_acquire() { return 0; }   # no mutex at all
registry_lock_release() { return 0; }
STUB

# The barrier goes AFTER the render and BEFORE the commit. That is the seam
# where both writers have produced their content from their own snapshot and
# neither has renamed: the second rename then provably discards the first.
# (At the TOP of ait_atomic_render it would NOT be deterministic — the renderer
# re-reads the store, so a writer released early could read the other's
# already-committed file.)
cat > "$NEG/lib/atomic_write.sh" <<STUB
#!/usr/bin/env bash
# NEGATIVE-CONTROL STAND-IN — fixture-only. Sources the real library, then
# redefines ONLY ait_atomic_render to rendezvous before committing.
source "$PROJECT_DIR/.aitask-scripts/lib/atomic_write.sh"

_negctrl_barrier_wait() {
    local d="\${NEGCTRL_BARRIER_DIR:?}" deadline
    mkdir -p "\$d"
    : > "\$d/\$\$.ready"
    deadline=\$(( \$(date +%s) + 10 ))
    while [ "\$(find "\$d" -maxdepth 1 -name '*.ready' | wc -l)" -lt 2 ]; do
        [ "\$(date +%s)" -ge "\$deadline" ] && return 0   # fail open, never hang
        sleep 0.02
    done
}

ait_atomic_render() {
    local dest tmp
    dest="\$(ait_atomic_resolve "\$1")" || return 1
    shift
    tmp="\$(ait_atomic_tmp "\$dest")" || return 1
    if ! "\$@" > "\$tmp"; then
        ait_atomic_discard "\$tmp"
        return 1
    fi
    _negctrl_barrier_wait
    ait_atomic_commit "\$tmp" "\$dest"
}
STUB

export NEGCTRL_BARRIER_DIR="$TMP/barrier"
rm -rf "$NEGCTRL_BARRIER_DIR"
reset_store

"$NEG/aitask_shadow_rejected.sh" add 31 --producer w1 <<<'- [high | alpha] first writer.'  >/dev/null 2>&1 &
"$NEG/aitask_shadow_rejected.sh" add 31 --producer w2 <<<'- [high | beta] second writer.' >/dev/null 2>&1 &
wait

# Assert the EXACT forced outcome, not merely "something failed": a crash, a
# missing lib or an unwritable temp would also produce a non-zero exit.
assert_eq "negative control: the barrier actually engaged (both writers arrived)" \
    "2" "$(find "$NEGCTRL_BARRIER_DIR" -maxdepth 1 -name '*.ready' 2>/dev/null | wc -l | tr -d ' ')"
assert_eq "negative control: unlocked contention LOSES one entry" "1" "$(entry_count 31)"
assert_eq "negative control: the survivor kept the reused id r1" "r1" "$(entry_ids 31)"
assert_eq "negative control: header shows only one id was ever issued" "2" "$(header_next 31)"

unset NEGCTRL_BARRIER_DIR

echo
echo "=== Test 14: an unusable store path is a write error, not contention ==="
# registry_lock_acquire retries `mkdir` until its timeout and then returns 1.
# If the store dir cannot be created at all, letting it get that far spends the
# entire timeout and then blames a competing writer for an unusable path — so
# the failure must be diagnosed before the lock is ever attempted.
reset_store
mkdir -p "$TMP/rootasfile_parent"
printf 'i am a regular file, not a directory\n' > "$TMP/rootasfile_parent/root"

t0="$(date +%s)"
out="$(echo '- [low | x] y' | AITASK_SHADOW_DIR="$TMP/rootasfile_parent/root" "$H" add 42 2>&1)"
rc=$?
t1="$(date +%s)"
elapsed=$(( t1 - t0 ))
assert_eq "file-backed store root -> exit 4 (write error)" "4" "$rc"
assert_not_contains "file-backed store root -> NOT reported as contention" "LOCK_BUSY" "$out"
assert_contains "file-backed store root -> names the real problem" "store directory" "$out"
assert_eq "file-backed store root -> fails fast, not after the lock timeout" "0" \
    "$([ "$elapsed" -le 2 ] && echo 0 || echo "1 (took ${elapsed}s)")"

# Same class of failure, reached differently: the dir exists but cannot be
# written, so `mkdir -p` succeeds and only the lock `mkdir` would fail.
reset_store
mkdir -p "$AITASK_SHADOW_DIR/43"
chmod 555 "$AITASK_SHADOW_DIR/43"
if [[ -w "$AITASK_SHADOW_DIR/43" ]]; then
    echo "SKIP: running as root — a read-only dir is still writable"
else
    t0="$(date +%s)"
    out="$(echo '- [low | x] y' | "$H" add 43 2>&1)"; rc=$?
    t1="$(date +%s)"
    assert_eq "read-only store dir -> exit 4" "4" "$rc"
    assert_not_contains "read-only store dir -> NOT reported as contention" "LOCK_BUSY" "$out"
    assert_eq "read-only store dir -> fails fast" "0" \
        "$([ $(( t1 - t0 )) -le 2 ] && echo 0 || echo 1)"
fi
chmod 755 "$AITASK_SHADOW_DIR/43" 2>/dev/null || true

echo
echo "=== Test 14b: a corrupted lock artifact is a write error, not contention ==="
# registry_lock_acquire serializes by racing `mkdir "$LOCK_DIR"`. If that path
# is occupied by something that is NOT a directory, the mkdir can never win, so
# acquire spins out its whole timeout and reports LOCK_BUSY though no writer
# exists. An existing *directory* is the real held-lock case and must still be
# left to acquire (Test 7 covers it).
# symlink-to-directory is the subtle one: `-d` FOLLOWS symlinks, so a `! -d`
# test waves it through — but `mkdir` still fails with EEXIST on the link
# itself, so acquire stalls exactly as it does for a regular file.
mkdir -p "$TMP/lock_symlink_target"
for kind in regular-file dangling-symlink symlink-to-directory; do
    reset_store
    mkdir -p "$AITASK_SHADOW_DIR/44"
    case "$kind" in
        regular-file)        printf 'corrupt lock artifact\n' > "$(lockd_of 44)" ;;
        dangling-symlink)    ln -s "$TMP/no_such_target" "$(lockd_of 44)" ;;
        symlink-to-directory) ln -s "$TMP/lock_symlink_target" "$(lockd_of 44)" ;;
    esac

    t0="$(date +%s)"
    out="$(echo '- [low | x] y' | "$H" add 44 2>&1)"; rc=$?
    t1="$(date +%s)"
    assert_eq "$kind lock path -> exit 4" "4" "$rc"
    assert_not_contains "$kind lock path -> NOT reported as contention" "LOCK_BUSY" "$out"
    assert_contains "$kind lock path -> names the lock path" "lock path" "$out"
    assert_eq "$kind lock path -> fails fast, not after the lock timeout" "0" \
        "$([ $(( t1 - t0 )) -le 2 ] && echo 0 || echo "1 (took $(( t1 - t0 ))s)")"
done

# The distinction that matters: a real lock DIRECTORY must still reach
# registry_lock_acquire and be reported as contention, not as a write error.
reset_store
printf '%s\n' '- [low | seed] seed.' | "$H" add 45 >/dev/null
hold_lock 45
out="$(echo '- [low | x] y' | "$H" add 45 2>&1)"; rc=$?
assert_eq "a genuine held lock is still LOCK_BUSY, not exit 4" "3" "$rc"
assert_eq "a genuine held lock still reports contention" "LOCK_BUSY" "$out"
release_held_lock 45

echo
echo "=== Test 15: a corrupt next_id header self-heals, never crashes ==="
# `0` would issue an r0 outside the documented monotonic-from-1 scheme, and a
# leading-zero value is read as OCTAL by bash arithmetic — `08` aborts with
# "value too great for base", an undocumented exit that loses the append.
for bad in 0 08 007 00; do
    reset_store
    mkdir -p "$AITASK_SHADOW_DIR/50"
    printf '<!-- next_id: %s -->\n\n' "$bad" > "$(store_of 50)"
    out="$(echo '- [low | x] y' | "$H" add 50 2>&1)"; rc=$?
    assert_eq "header '$bad' -> add still succeeds" "0" "$rc"
    assert_eq "header '$bad' -> reports ADDED:1" "ADDED:1" "$out"
    assert_eq "header '$bad' -> falls back to r1, never r0" "r1" "$(entry_ids 50)"
    assert_eq "header '$bad' -> header rewritten canonically" "2" "$(header_next 50)"
done

# The self-heal must respect entries that already exist, including a
# leading-zero entry id that plain arithmetic would choke on.
reset_store
mkdir -p "$AITASK_SHADOW_DIR/51"
printf '### r08 | 2026-01-01T00:00:00Z | producer: x\n- [low | a] existing.\n\n' \
    > "$(store_of 51)"
out="$(echo '- [low | b] fresh.' | "$H" add 51 2>&1)"; rc=$?
assert_eq "leading-zero ENTRY id -> no arithmetic crash" "0" "$rc"
assert_eq "leading-zero entry id -> forced base 10, next is r9" "ADDED:1" "$out"
assert_contains "the new entry landed as r9" "### r9 " "$(cat "$(store_of 51)")"

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -gt 0 ]] && exit 1
echo "All tests PASSED"
