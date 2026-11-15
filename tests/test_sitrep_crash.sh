#!/usr/bin/env bash
# End-to-end tests for `aitask_sitrep_harvest.sh crashed` (t2299_2).
#
# Real wrapper, real store writer, real git lock refs (a scratch
# `refs/remotes/origin/aitask-locks` built with hash-object/mktree/commit-tree),
# real dead PIDs (a reaped `sleep 0`) and real live ones (`sleep 300`, their
# starttime captured through lib/pid_anchor.sh) -- under a scratch HOME.
#
#   1   classification: crashed / orphan / stale_lock stored; alive, unknown,
#       other_host (incl. no-PID foreign and `unknown` hosts) skipped, never stored
#   2   idempotence: same clock and an advanced clock inside the age bucket are
#       `unchanged` (todo.md and sources/ byte-identical); a bucket crossing applies
#   3   precedence: archived / Done under dead and no-anchor locks stay stale_lock
#       over 3 passes; release -> done (stays done); a live claim -> done;
#       a crashed task archived under its dead lock -> stale_lock, same key
#   4   strict inputs: every unreadable input warns and leaves an existing OPEN and
#       an existing UNKNOWN item byte-identical; archived (loose and bundled) bad
#       status; unreadable ref/tree -> CRASH_FAILED, nothing written; absent = no lock
#   5   episodes: dismissed orphan + metadata edit kept; dismissed crash + lock
#       removed kept; live claim untouched then reopened when it dies; a
#       self-refreshed lock keeps the key; done -> crashed again reopens
#   6   atomicity: the fault seam leaves the item unchanged; a dismissal between
#       the read and the write -> STALE, then kept_dismissed
#   7   --dry-run writes nothing; nothing in flight -> CRASH_NONE; subdirectory
#       cwd and the default --root; a held harvest mutex -> CRASH_FAILED
#
# Bodies run in the main shell (no subshell asserts), so the plain counters
# are enough.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

HV="$PROJECT_DIR/.aitask-scripts/aitask_sitrep_harvest.sh"
WR="$PROJECT_DIR/.aitask-scripts/aitask_sitrep_todo.sh"
PID_ANCHOR="$PROJECT_DIR/.aitask-scripts/lib/pid_anchor.sh"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/ait_crash_XXXXXX")"
TMP="$(cd "$TMP" && pwd -P)"
BG_PIDS=()
cleanup() {
    local p
    for p in "${BG_PIDS[@]:-}"; do
        [[ -n "$p" ]] && kill -9 "$p" 2>/dev/null
    done
    exec 7>&- 2>/dev/null
    chmod -R u+rwx "$TMP" 2>/dev/null
    rm -rf "$TMP"
}
trap cleanup EXIT

AIT_PYTHON="$(source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" && require_ait_python)"
export AIT_PYTHON
export HOME="$TMP/home"
mkdir -p "$HOME/.config/aitasks"
export AITASKS_AGENT_SESSIONS_FILE="$TMP/agent_sessions.json"
export AITASKS_PROJECTS_INDEX="$TMP/projects.yaml"
printf 'projects:\n' > "$AITASKS_PROJECTS_INDEX"
export TZ=UTC
export AITASK_SITREP_NOW="2026-11-03T10:00:00Z"
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
export GIT_CONFIG_NOSYSTEM=1
unset TMUX TMUX_PANE AITASK_SITREP_DIR AITASK_SITREP_PAUSE_FIFO AITASK_SITREP_LOCK_TIMEOUT \
      AITASK_SITREP_CRASH_FAULT AITASK_SITREP_CRASH_PAUSE_FIFO \
      AITASK_SITREP_HARVEST_PAUSE_FIFO AITASK_SITREP_HARVEST_LOCK_TIMEOUT TASK_DIR

HOST="$(hostname)"
FIFO="$TMP/pause.fifo"

# --- helpers -----------------------------------------------------------------

new_root() {   # new_root <name> -> a fresh git repo with aitasks/ and aiplans/
    local d="$TMP/$1"
    mkdir -p "$d/aitasks/metadata" "$d/aitasks/archived" "$d/aiplans" "$TMP/locks/$1"
    printf '.aitask-sitrep/\n' > "$d/.gitignore"
    printf 'a\n' > "$d/src.py"
    git -C "$d" init -q -b main
    git -C "$d" add -A
    git -C "$d" commit -q -m init
    publish "$d"
    printf '%s' "$d"
}

# task <root> <id> <status> [yaml lines...]  (active file; replaces any)
task() {
    local root="$1" id="$2" status="$3" dir="$1/aitasks" l
    shift 3
    [[ "$id" == *_* ]] && dir="$root/aitasks/t${id%%_*}"
    mkdir -p "$dir"
    { printf -- '---\n'
      [[ -n "$status" ]] && printf 'status: %s\n' "$status"
      for l in "$@"; do printf '%s\n' "$l"; done
      printf -- '---\n\nbody\n'; } > "$dir/t${id}_x.md"
}

# archive <root> <id> <status>  (moves the task to archived/, loose)
archive() {
    rm -f "$1/aitasks/t$2_x.md"
    { printf -- '---\n'
      [[ -n "$3" ]] && printf 'status: %s\n' "$3"
      printf 'completed_at: 2026-11-02 09:00\n---\n\nbody\n'; } > "$1/aitasks/archived/t$2_x.md"
}

publish() {   # publish <root>: $TMP/locks/<name>/ -> refs/remotes/origin/aitask-locks
    local root="$1" d f entries="" oid tree commit
    d="$TMP/locks/$(basename "$root")"
    mkdir -p "$d"
    for f in "$d"/*_lock.yaml; do
        [[ -e "$f" ]] || continue
        oid="$(git -C "$root" hash-object -w "$f")"
        entries+="100644 blob $oid"$'\t'"$(basename "$f")"$'\n'
    done
    tree="$(printf '%s' "$entries" | git -C "$root" mktree)"
    commit="$(git -C "$root" commit-tree "$tree" -m locks)"
    git -C "$root" update-ref refs/remotes/origin/aitask-locks "$commit"
}

# setlock <root> <id> <host> <pid|""> [start] [kind] [locked_at]
setlock() {
    local f
    f="$TMP/locks/$(basename "$1")/t$2_lock.yaml"
    { printf 'task_id: %s\nlocked_by: a@b\nlocked_at: %s\nhostname: %s\n' \
          "$2" "${7:-2026-11-03 08:00}" "$3"
      if [[ -n "$4" ]]; then
          printf 'pid: %s\npid_starttime: %s\npid_starttime_kind: %s\n' "$4" "${5:-1}" "${6:-proc}"
      fi; } > "$f"
    publish "$1"
}
rawlock() { printf '%s' "$3" > "$TMP/locks/$(basename "$1")/t$2_lock.yaml"; publish "$1"; }
unlock() { rm -f "$TMP/locks/$(basename "$1")/t$2_lock.yaml"; publish "$1"; }

dead_pid() { sleep 0 & local p=$!; wait "$p" 2>/dev/null; printf '%s' "$p"; }
live() {   # live -> sets LIVE_PID, LIVE_KIND, LIVE_START (a running sleep)
    sleep 300 &
    LIVE_PID=$!
    BG_PIDS+=("$LIVE_PID")
    read -r LIVE_KIND LIVE_START <<<"$(source "$PID_ANCHOR"; get_pid_identity "$LIVE_PID")"
}

wr() { local root="$1"; shift; AITASK_SITREP_DIR="$root/.aitask-sitrep" "$WR" "$@"; }

crashed() {   # crashed <root> [args...] -> OUT, RC
    local root="$1"; shift
    RC=0
    OUT="$("$HV" crashed --root "$root" "$@" 2>"$TMP/err")" || RC=$?
}

todo() { cat "$1/.aitask-sitrep/todo.md" 2>/dev/null; }
cid_of() { todo "$1" | sed -n "s/^- \(c[0-9]*\) | .* | ref=recover:t$2 | .*/\1/p"; }
line_of() { todo "$1" | grep "^- $2 |"; }
st_of() { line_of "$1" "$2" | sed -n 's/.* | state=\([a-z]*\) | .*/\1/p'; }
outc() { line_of "$1" "$2" | sed -n 's/.* | outcome=\([^|]*\) | .*/\1/p'; }
inc_of() { wr "$1" context "$2" | sed -n 's/.* incarnation=\([0-9a-f]*\).*/\1/p'; }
item_res() { printf '%s\n' "$OUT" | grep "^CRASH_ITEM:t$1|" | cut -d'|' -f3; }
sources_list() { ls "$1/.aitask-sitrep/sources" 2>/dev/null; }
snapshot() { { todo "$1"; sources_list "$1"; } | cksum; }
item_block() {   # the item line plus its context block, verbatim
    local c="$2"
    line_of "$1" "$c"
    todo "$1" | awk -v h="### $c" '$0 == h {p=1; print; next} p && /^### / {p=0} p'
}

# =============================================================================
echo "=== Test 1: classification ==="
R1="$(new_root r1)"
D1="$(dead_pid)"
live
task "$R1" 1 Implementing; setlock "$R1" 1 "$HOST" "$D1"
task "$R1" 2 Implementing
task "$R1" 3 Ready;        setlock "$R1" 3 "$HOST" ""
task "$R1" 4 Implementing; setlock "$R1" 4 "$HOST" "$LIVE_PID" "$LIVE_START" "$LIVE_KIND"
task "$R1" 5 Implementing; setlock "$R1" 5 elsewhere ""
task "$R1" 6 Implementing; setlock "$R1" 6 unknown abc
WEAK="$(source "$PID_ANCHOR"; _pid_starttime_ps "$LIVE_PID")"
task "$R1" 7 Implementing; setlock "$R1" 7 "$HOST" "$LIVE_PID" "$WEAK" ps
task "$R1" 8_1 Implementing; setlock "$R1" 8_1 "$HOST" "$D1"
crashed "$R1"
assert_eq "pass exits 0" "0" "$RC"
assert_eq "t1 crashed added" "added" "$(item_res 1)"
assert_contains "t1 category" "CRASH_ITEM:t1|c" "$OUT"
assert_contains "t1 is crashed" "|added|crashed" "$(printf '%s\n' "$OUT" | grep '^CRASH_ITEM:t1|')"
assert_contains "t2 orphan" "|added|orphan" "$(printf '%s\n' "$OUT" | grep '^CRASH_ITEM:t2|')"
assert_contains "t3 stale lock (no anchor)" "|added|stale_lock" "$(printf '%s\n' "$OUT" | grep '^CRASH_ITEM:t3|')"
assert_contains "t8_1 child crashed" "|added|crashed" "$(printf '%s\n' "$OUT" | grep '^CRASH_ITEM:t8_1|')"
assert_contains "t4 live -> skip" "CRASH_SKIP:t4|alive" "$OUT"
assert_contains "t5 foreign host, no pid -> other_host" "CRASH_SKIP:t5|other_host:elsewhere" "$OUT"
assert_contains "t6 unknown host, bad pid -> other_host" "CRASH_SKIP:t6|other_host:unknown" "$OUT"
assert_contains "t7 weak token -> unknown" "CRASH_SKIP:t7|unknown" "$OUT"
for t in 4 5 6 7; do
    assert_eq "t$t never stored" "" "$(cid_of "$R1" "$t")"
done
assert_contains "final counts" \
    "CRASHED:crashed=2|orphans=1|stale_locks=1|skipped=4|added=4|reopened=0|warned=0" "$OUT"
C1="$(cid_of "$R1" 1)"
assert_eq "t1 item is open" "open" "$(st_of "$R1" "$C1")"
assert_contains "t1 outcome" "crashed · holder pid $D1 is gone" "$(outc "$R1" "$C1")"
assert_contains "t1 group now/next" "group=next" "$(line_of "$R1" "$C1")"
assert_contains "t3 waits" "group=waiting" "$(line_of "$R1" "$(cid_of "$R1" 3)")"
assert_contains "t1 title" "Recover t1 x (crashed): unknown, no plan, 0 files" "$(line_of "$R1" "$C1")"
SURV="$(grep -l '^task: t1$' "$R1"/.aitask-sitrep/sources/*.txt)"
assert_contains "survey retained" "SITREP_RECOVERY_SURVEY v1" "$(cat "$SURV")"
assert_contains "survey lock age" "lock_age: 1h-1d" "$(cat "$SURV")"
assert_contains "context origin" "origin: task=t1 incarnation=" "$(wr "$R1" context "$C1")"

echo "=== Test 2: idempotence across an advancing clock ==="
before="$(snapshot "$R1")"
crashed "$R1"
assert_eq "same clock: t1 unchanged" "unchanged" "$(item_res 1)"
assert_eq "same clock: t2 unchanged" "unchanged" "$(item_res 2)"
assert_eq "same clock: store byte-identical" "$before" "$(snapshot "$R1")"
AITASK_SITREP_NOW="2026-11-03T13:00:00Z" crashed "$R1"
assert_eq "+3h (same bucket): t1 unchanged" "unchanged" "$(item_res 1)"
assert_eq "+3h: t3 unchanged" "unchanged" "$(item_res 3)"
assert_eq "+3h: store byte-identical, no new source" "$before" "$(snapshot "$R1")"
AITASK_SITREP_NOW="2026-11-05T10:00:00Z" crashed "$R1"
assert_eq "+2d (bucket crossed): t1 applied" "applied" "$(item_res 1)"
assert_eq "+2d: orphan t2 (no lock age) unchanged" "unchanged" "$(item_res 2)"
assert_contains "+2d: survey says 1d-7d" "lock_age: 1d-7d" \
    "$(grep -h -A4 '^task: t1$' "$R1"/.aitask-sitrep/sources/*.txt)"
# A state-only done item stays unchanged across an advanced clock.
unlock "$R1" 3
AITASK_SITREP_NOW="2026-11-05T10:00:00Z" crashed "$R1"
C3="$(cid_of "$R1" 3)"
assert_eq "t3 released -> done" "done" "$(st_of "$R1" "$C3")"
assert_contains "t3 done is applied" "CRASH_ITEM:t3|$C3|applied|recovered" "$OUT"
b3="$(item_block "$R1" "$C3")"
AITASK_SITREP_NOW="2026-11-09T10:00:00Z" crashed "$R1"
assert_eq "done item byte-identical later" "$b3" "$(item_block "$R1" "$C3")"
assert_eq "done item not reported" "" "$(item_res 3)"

# =============================================================================
echo "=== Test 3: precedence ==="
R3="$(new_root r3)"
D3="$(dead_pid)"
archive "$R3" 10 Done;   setlock "$R3" 10 "$HOST" "$D3"
task "$R3" 11 Done;      setlock "$R3" 11 "$HOST" ""
task "$R3" 12 Implementing; setlock "$R3" 12 "$HOST" "$D3"
crashed "$R3"
first="$(printf '%s\n' "$OUT" | grep -v '^CRASH_ITEM:t12|')"
assert_contains "archived Done + dead lock -> stale_lock" "|added|stale_lock" \
    "$(printf '%s\n' "$OUT" | grep '^CRASH_ITEM:t10|')"
assert_contains "Done + no-anchor lock -> stale_lock" "|added|stale_lock" \
    "$(printf '%s\n' "$OUT" | grep '^CRASH_ITEM:t11|')"
C10="$(cid_of "$R3" 10)"; C11="$(cid_of "$R3" 11)"; C12="$(cid_of "$R3" 12)"
K12="$(inc_of "$R3" "$C12")"
for pass in 2 3; do
    crashed "$R3"
    assert_eq "pass $pass: t10 still open" "open" "$(st_of "$R3" "$C10")"
    assert_eq "pass $pass: t11 still open" "open" "$(st_of "$R3" "$C11")"
    assert_eq "pass $pass: t10 unchanged" "unchanged" "$(item_res 10)"
    assert_eq "pass $pass: t11 unchanged" "unchanged" "$(item_res 11)"
done
unlock "$R3" 10
crashed "$R3"
assert_eq "t10 released -> done" "done" "$(st_of "$R3" "$C10")"
assert_contains "t10 recovered outcome" "recovered · recovered: archived Done" "$(outc "$R3" "$C10")"
crashed "$R3"
assert_eq "t10 stays done" "done" "$(st_of "$R3" "$C10")"
live
setlock "$R3" 11 "$HOST" "$LIVE_PID" "$LIVE_START" "$LIVE_KIND"
crashed "$R3"
assert_eq "t11 live claim -> done" "done" "$(st_of "$R3" "$C11")"
assert_contains "t11 live outcome" "alive · held by a live session" "$(outc "$R3" "$C11")"
# A crashed task archived under its dead lock: stale_lock, same episode key.
archive "$R3" 12 Done
crashed "$R3"
assert_contains "t12 archived under its dead lock -> stale_lock" "|applied|stale_lock" \
    "$(printf '%s\n' "$OUT" | grep '^CRASH_ITEM:t12|')"
assert_eq "t12 keeps its key" "$K12" "$(inc_of "$R3" "$C12")"
assert_eq "t12 still open" "open" "$(st_of "$R3" "$C12")"
[[ -n "$first" ]] || true

# =============================================================================
echo "=== Test 4: strict inputs ==="
R4="$(new_root r4)"
D4="$(dead_pid)"
task "$R4" 20 Implementing; setlock "$R4" 20 "$HOST" "$D4"
task "$R4" 21 Implementing; setlock "$R4" 21 "$HOST" "$D4"
crashed "$R4"
C20="$(cid_of "$R4" 20)"; C21="$(cid_of "$R4" 21)"
setlock "$R4" 21 elsewhere "$D4"
crashed "$R4"
assert_eq "t21 foreign host -> unknown" "unknown" "$(st_of "$R4" "$C21")"
B20="$(item_block "$R4" "$C20")"; B21="$(item_block "$R4" "$C21")"
check_untouched() {   # check_untouched <label>
    assert_eq "$1: open item byte-identical" "$B20" "$(item_block "$R4" "$C20")"
    assert_eq "$1: unknown item byte-identical" "$B21" "$(item_block "$R4" "$C21")"
}
# (a) malformed locks (no hostname / mismatched id)
rawlock "$R4" 20 $'task_id: 20\npid: 1\n'
rawlock "$R4" 21 $'task_id: 99\nhostname: elsewhere\n'
crashed "$R4"
assert_contains "malformed lock warns" "CRASH_WARN:t20|unreadable:" "$OUT"
assert_contains "mismatched lock warns" "CRASH_WARN:t21|unreadable:" "$OUT"
assert_eq "malformed: no CRASH_ITEM" "" "$(printf '%s\n' "$OUT" | grep '^CRASH_ITEM:t2[01]|')"
check_untouched "malformed lock"
# (b) an unreadable blob (its object deleted)
setlock "$R4" 20 "$HOST" "$D4"; setlock "$R4" 21 elsewhere "$D4"
oid="$(git -C "$R4" rev-parse refs/remotes/origin/aitask-locks:t20_lock.yaml)"
rm -f "$R4/.git/objects/${oid:0:2}/${oid:2}"
crashed "$R4"
assert_contains "unreadable blob warns" "CRASH_WARN:t20|unreadable:" "$OUT"
check_untouched "unreadable blob"
# (c) an unreadable active task file, (d) a missing status
setlock "$R4" 20 "$HOST" "$D4"
if [[ "$(id -u)" != 0 ]]; then
    chmod 000 "$R4/aitasks/t20_x.md"
    crashed "$R4"
    assert_contains "unreadable task file warns" "CRASH_WARN:t20|unreadable:" "$OUT"
    check_untouched "unreadable task file"
    chmod 644 "$R4/aitasks/t20_x.md"
fi
task "$R4" 21 "" "priority: high"
crashed "$R4"
assert_contains "missing status warns" "CRASH_WARN:t21|unreadable: t21_x.md: no status" "$OUT"
check_untouched "missing status"
task "$R4" 21 Implementing
# (e) archived records with a bad status, loose and bundled, under dead locks
archive "$R4" 22 ""; setlock "$R4" 22 "$HOST" "$D4"
mkdir -p "$TMP/bundle" "$R4/aitasks/archived/_b0"
printf -- '---\nstatus: Banana\n---\n\nbody\n' > "$TMP/bundle/t23_x.md"
tar -C "$TMP/bundle" --zstd -cf "$R4/aitasks/archived/_b0/old0.tar.zst" t23_x.md
setlock "$R4" 23 "$HOST" "$D4"
crashed "$R4"
assert_contains "loose archived, no status warns" "CRASH_WARN:t22|unreadable:" "$OUT"
assert_contains "bundled archived, bad status warns" "CRASH_WARN:t23|unreadable:" "$OUT"
assert_eq "no item for t22" "" "$(cid_of "$R4" 22)"
assert_eq "no item for t23" "" "$(cid_of "$R4" 23)"
check_untouched "archived bad status"
# (e2) an unreadable plan of a stored task: warn, no write
if [[ "$(id -u)" != 0 ]]; then
    printf 'plan for t20\n' > "$R4/aiplans/p20_x.md"
    chmod 000 "$R4/aiplans/p20_x.md"
    crashed "$R4"
    assert_contains "unreadable plan warns" "CRASH_WARN:t20|unreadable: plan aiplans/p20_x.md" "$OUT"
    check_untouched "unreadable plan"
    rm -f "$R4/aiplans/p20_x.md"
fi
# (f) control: a lock absent from the tree is "no lock"
task "$R4" 24 Implementing
crashed "$R4"
assert_contains "absent lock -> orphan, not an error" "|added|orphan" \
    "$(printf '%s\n' "$OUT" | grep '^CRASH_ITEM:t24|')"
# (g) an unreadable ref or tree fails the pass with no writes
snap="$(snapshot "$R4")"
tree="$(git -C "$R4" rev-parse 'refs/remotes/origin/aitask-locks^{tree}')"
rm -f "$R4/.git/objects/${tree:0:2}/${tree:2}"
crashed "$R4"
assert_eq "unreadable tree exits 1" "1" "$RC"
assert_contains "unreadable tree -> CRASH_FAILED" "CRASH_FAILED:lock_tree_unreadable" "$OUT"
assert_eq "unreadable tree: nothing written" "$snap" "$(snapshot "$R4")"
# a failed `git status` is never "nothing dirty"
publish "$R4"
mkdir -p "$TMP/shim_status"
printf '#!/usr/bin/env bash\nfor a in "$@"; do [[ "$a" == status ]] && exit 128; done\nexec %s "$@"\n' \
    "$(command -v git)" > "$TMP/shim_status/git"
chmod +x "$TMP/shim_status/git"
PATH="$TMP/shim_status:$PATH" crashed "$R4"
assert_contains "failed status -> CRASH_FAILED" "CRASH_FAILED:shared_status_unreadable" "$OUT"
assert_eq "failed status: nothing written" "$snap" "$(snapshot "$R4")"
rm -f "$R4/.git/objects/${tree:0:2}/${tree:2}"
git -C "$R4" update-ref -d refs/remotes/origin/aitask-locks
crashed "$R4"
assert_contains "no lock ref -> CRASH_FAILED" "CRASH_FAILED:no_lock_ref" "$OUT"
assert_eq "no lock ref: nothing written" "$snap" "$(snapshot "$R4")"

# =============================================================================
echo "=== Test 5: episodes ==="
R5="$(new_root r5)"
D5="$(dead_pid)"
task "$R5" 30 Implementing
task "$R5" 31 Implementing; setlock "$R5" 31 "$HOST" "$D5"
task "$R5" 32 Implementing; setlock "$R5" 32 "$HOST" "$D5"
task "$R5" 33 Implementing; setlock "$R5" 33 "$HOST" "$D5" 1 proc "2026-11-03 08:00"
task "$R5" 34 Implementing; setlock "$R5" 34 "$HOST" "$D5"
crashed "$R5"
C30="$(cid_of "$R5" 30)"; C31="$(cid_of "$R5" 31)"; C32="$(cid_of "$R5" 32)"
C33="$(cid_of "$R5" 33)"; C34="$(cid_of "$R5" 34)"
for c in "$C30" "$C31" "$C32" "$C33"; do wr "$R5" dismiss "$c" >/dev/null; done
K33="$(inc_of "$R5" "$C33")"
# metadata edit on a dismissed orphan
task "$R5" 30 Implementing "labels: [x]" "updated_at: 2026-11-04 10:00"
# dismissed crash whose lock is removed (-> orphan, same carried key)
unlock "$R5" 31
# live claim on a dismissed crash
live
setlock "$R5" 32 "$HOST" "$LIVE_PID" "$LIVE_START" "$LIVE_KIND"
B32="$(item_block "$R5" "$C32")"
# a self-refreshed lock (only locked_at changes)
setlock "$R5" 33 "$HOST" "$D5" 1 proc "2026-11-03 09:30"
crashed "$R5"
assert_contains "metadata edit: orphan kept" "CRASH_ITEM:t30|$C30|kept_dismissed|orphan" "$OUT"
assert_contains "lock removed: kept" "CRASH_ITEM:t31|$C31|kept_dismissed|orphan" "$OUT"
assert_contains "live claim: skipped" "CRASH_SKIP:t32|alive" "$OUT"
assert_eq "live claim: dismissed item untouched" "$B32" "$(item_block "$R5" "$C32")"
assert_contains "self-refreshed lock: same key, kept" "CRASH_ITEM:t33|$C33|kept_dismissed|crashed" "$OUT"
assert_eq "self-refreshed lock: key unchanged" "$K33" "$(inc_of "$R5" "$C33")"
for c in "$C30" "$C31" "$C32" "$C33"; do
    assert_eq "$c still dismissed" "dismissed" "$(st_of "$R5" "$c")"
done
# the live claim dies -> a new episode reopens the dismissed item
kill -9 "$LIVE_PID" 2>/dev/null; wait "$LIVE_PID" 2>/dev/null
crashed "$R5"
assert_contains "dead claim B reopens" "CRASH_ITEM:t32|$C32|reopened|crashed" "$OUT"
assert_eq "t32 open again" "open" "$(st_of "$R5" "$C32")"
# done -> crashed again
unlock "$R5" 34; task "$R5" 34 Ready
crashed "$R5"
assert_eq "t34 recovered -> done" "done" "$(st_of "$R5" "$C34")"
D5b="$(dead_pid)"
task "$R5" 34 Implementing; setlock "$R5" 34 "$HOST" "$D5b" 2
crashed "$R5"
assert_contains "done -> crashed again reopens" "CRASH_ITEM:t34|$C34|reopened|crashed" "$OUT"
assert_contains "final counts reopened" "reopened=1" "$OUT"

# =============================================================================
echo "=== Test 6: atomicity ==="
R6="$(new_root r6)"
D6="$(dead_pid)"
task "$R6" 40 Implementing; setlock "$R6" 40 "$HOST" "$D6"
crashed "$R6"
C40="$(cid_of "$R6" 40)"
B40="$(item_block "$R6" "$C40")"
setlock "$R6" 40 "$HOST" "$D6" 1 proc "2026-11-03 09:00"   # evidence change
RC=0; OUT="$(AITASK_SITREP_CRASH_FAULT=before_apply "$HV" crashed --root "$R6" 2>/dev/null)" || RC=$?
assert_eq "fault exits 1" "1" "$RC"
assert_contains "fault reported" "CRASH_FAILED:fault:before_apply" "$OUT"
assert_eq "fault: item unchanged" "$B40" "$(item_block "$R6" "$C40")"
task "$R6" 41 Implementing
RC=0; OUT="$(AITASK_SITREP_CRASH_FAULT=after_retain "$HV" crashed --root "$R6" 2>/dev/null)" || RC=$?
assert_eq "after_retain fault: nothing added" "" "$(cid_of "$R6" 41)"
# A dismissal between the read and the write wins.
mkfifo "$FIFO"
exec 7<>"$FIFO"
AITASK_SITREP_CRASH_PAUSE_FIFO="$FIFO" "$HV" crashed --root "$R6" >"$TMP/race.out" 2>&1 &
RACE=$!
BG_PIDS+=("$RACE")
for _ in $(seq 1 200); do [[ -s "$FIFO.reached" ]] && break; sleep 0.05; done
assert_eq "paused before apply" "before_apply" "$(cat "$FIFO.reached" 2>/dev/null)"
wr "$R6" dismiss "$C40" >/dev/null
for _ in 1 2 3; do printf 'go\n' >&7; done
wait "$RACE" 2>/dev/null
assert_contains "the racing write is STALE" "CRASH_WARN:t40|stale" "$(cat "$TMP/race.out")"
assert_eq "the dismissal survived" "dismissed" "$(st_of "$R6" "$C40")"
exec 7>&-
crashed "$R6"
assert_contains "next pass keeps it dismissed" "CRASH_ITEM:t40|$C40|kept_dismissed|crashed" "$OUT"

# =============================================================================
echo "=== Test 7: dry-run, nothing in flight, cwd, the harvest mutex ==="
R7="$(new_root r7)"
crashed "$R7"
assert_eq "nothing in flight" "CRASH_NONE:nothing_inflight" "$OUT"
assert_eq "nothing in flight: no store" "no" "$([[ -e "$R7/.aitask-sitrep" ]] && echo yes || echo no)"
D7="$(dead_pid)"
task "$R7" 50 Implementing; setlock "$R7" 50 "$HOST" "$D7"
crashed "$R7" --dry-run
assert_contains "dry-run reports" "CRASH_ITEM:t50|-|dry_run|crashed" "$OUT"
assert_eq "dry-run: no store written" "no" "$([[ -e "$R7/.aitask-sitrep" ]] && echo yes || echo no)"
mkdir -p "$R7/deep/sub"
RC=0; OUT="$(cd "$R7/deep/sub" && "$HV" crashed 2>/dev/null)" || RC=$?
assert_eq "default --root from a subdirectory" "added" "$(item_res 50)"
RC=0; OUT="$(cd "$R7/aitasks" && "$HV" crashed --root "$R7" 2>/dev/null)" || RC=$?
assert_eq "explicit --root from inside aitasks/" "unchanged" "$(item_res 50)"
# Hold the harvest mutex with a paused run; the second run must fail cleanly.
rm -f "$FIFO" "$FIFO.reached"; mkfifo "$FIFO"; exec 7<>"$FIFO"
setlock "$R7" 50 "$HOST" "$D7" 1 proc "2026-11-03 09:10"
AITASK_SITREP_HARVEST_PAUSE_FIFO="$FIFO" "$HV" crashed --root "$R7" >/dev/null 2>&1 &
HOLD=$!
BG_PIDS+=("$HOLD")
for _ in $(seq 1 200); do [[ -s "$FIFO.reached" ]] && break; sleep 0.05; done
RC=0; OUT="$(AITASK_SITREP_HARVEST_LOCK_TIMEOUT=1 "$HV" crashed --root "$R7" 2>/dev/null)" || RC=$?
assert_eq "busy mutex exits 1" "1" "$RC"
assert_contains "busy mutex -> CRASH_FAILED" "CRASH_FAILED:harvest_lock_busy" "$OUT"
for _ in 1 2 3; do printf 'go\n' >&7; done
wait "$HOLD" 2>/dev/null
exec 7>&-
RC=0; "$HV" crashed --root relative >/dev/null 2>&1 || RC=$?
assert_eq "relative --root is a usage error" "2" "$RC"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]] || exit 1
