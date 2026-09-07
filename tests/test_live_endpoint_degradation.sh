#!/usr/bin/env bash
# test_live_endpoint_degradation.sh — the resolver's result-code contract (t1657_4).
#
# `aitask_live_endpoint.sh` answers "which live agent is implementing task X?".
# Its whole value is that EVERY branch is a usable answer: a sender must never
# have to fall back to inspecting tmux by hand, and a degradation must never look
# like an error. So this file pins one case per `LIVE_NONE:<reason>` in the
# documented table, each asserting the EXACT stdout line and the exit status.
#
# WHAT THIS FILE DELIBERATELY DOES NOT ASSERT: that a durable `NOTE_APPENDED:`
# survives each branch. The resolver takes a task id and returns a code — it
# never appends a note and never calls SendMessage. Asserting durable-first
# ordering needs `ait note` + the adapter in one test, and that composition is
# owned by t1657_5 as its single join point (a note was sent to t1657_5 carrying
# the two assertions). Duplicating it here would build a second, drifting copy of
# a composition this task does not own.
#
# Locks are FORGED directly onto the fixture's `aitask-locks` branch rather than
# acquired: `remote_host`, `holder_dead` and the legacy no-`pid:` record cannot
# be produced by a real claim on this machine, and the lock record is the
# resolver's documented input seam.
#
# Also covers lib/lock_record.sh directly — the shared parse both this resolver
# and aitask_note.sh::note_sender_is_self read the lock record through. The
# fixture is already here, and the seam is otherwise only exercised through one
# caller's verdict.
#
# Run: bash tests/test_live_endpoint_degradation.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=../.aitask-scripts/lib/lock_record.sh
. "$PROJECT_DIR/.aitask-scripts/lib/lock_record.sh"

PASS=0
FAIL=0
TOTAL=0

RESOLVE="$PROJECT_DIR/.aitask-scripts/aitask_live_endpoint.sh"

# Private lock base, the documented isolation seam (t1496), so concurrent runs
# cannot collide on lock paths.
AITASKS_LOCK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/test_live_ep_lockbase_XXXXXX")"
export AITASKS_LOCK_DIR

TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_live_ep_XXXXXX")"
# shellcheck disable=SC2329  # invoked indirectly, by the EXIT trap below
cleanup() { rm -rf "$TMP" "$AITASKS_LOCK_DIR"; }
trap cleanup EXIT

# --- fixture ---------------------------------------------------------------
#
# A clone of a bare remote, not a bare `git init`: aitask_lock.sh keeps locks on
# an 'aitask-locks' orphan branch and refuses to operate without an 'origin'.

REMOTE="$TMP/remote.git"
git init -q --bare -b main "$REMOTE"
DATA="$TMP/data"
git clone -q "$REMOTE" "$DATA" 2>/dev/null
mkdir -p "$DATA/aitasks"
git -C "$DATA" config user.email t@example.com
git -C "$DATA" config user.name Test

# <id> <implemented_with value, or "" for none>
make_task() {
    local id="$1" impl="${2:-}"
    {
        echo "---"
        echo "status: Implementing"
        [[ -n "$impl" ]] && echo "implemented_with: $impl"
        echo "---"
        echo "Body for t${id}."
    } > "$DATA/aitasks/t${id}_x.md"
}

make_task 800 "claudecode/opus5"   # the well-formed, deliverable case
make_task 801 ""                   # the Step 4 -> Step 7 attribution window
make_task 802 "codex/gpt-5.4"      # a family with no adapter
make_task 803 "claudecode/opus5"   # host / liveness cases
git -C "$DATA" add -A && git -C "$DATA" commit -qm "tasks"
git -C "$DATA" push -q origin main 2>/dev/null || true
( cd "$DATA" && "$PROJECT_DIR/.aitask-scripts/aitask_lock.sh" --init ) >/dev/null 2>&1 || true

# Write <yaml> as t<id>_lock.yaml on the fixture's lock branch. Plumbing-only,
# the same shape aitask_lock.sh itself uses, so nothing here depends on the
# claim path being reachable for the state under test.
forge_lock() {
    local id="$1" yaml="$2"
    (
        cd "$DATA" || exit 1
        git fetch -q origin aitask-locks 2>/dev/null || true
        local parent blob newtree commit
        parent="$(git rev-parse origin/aitask-locks 2>/dev/null || true)"
        blob="$(printf '%s' "$yaml" | git hash-object -w --stdin)"
        newtree="$(
            {
                [[ -n "$parent" ]] && git ls-tree origin/aitask-locks \
                    | grep -v "$(printf '\t')t${id}_lock.yaml\$"
                printf '100644 blob %s\tt%s_lock.yaml\n' "$blob" "$id"
            } | git mktree
        )"
        if [[ -n "$parent" ]]; then
            commit="$(echo forge | git commit-tree "$newtree" -p "$parent")"
        else
            commit="$(echo forge | git commit-tree "$newtree")"
        fi
        git push -q --force origin "$commit:refs/heads/aitask-locks"
    )
}

# Run the resolver with the fixture as cwd, so resolve_task_file reads its tasks.
run_resolve() { ( cd "$DATA" && "$RESOLVE" "$@" ); }

THIS_HOST="$(hostname)"

# A PID that is provably gone: start a process, wait for it, keep its number.
DEAD_PID="$( ( sleep 0 & echo $! ) )"
wait 2>/dev/null || true
# And a provably live one with a real identity token — this shell.
LIVE_PID=$$
# shellcheck source=../.aitask-scripts/lib/pid_anchor.sh
. "$PROJECT_DIR/.aitask-scripts/lib/pid_anchor.sh"
LIVE_TOKEN="$(get_pid_starttime "$LIVE_PID")"
LIVE_KIND="$(get_pid_starttime_kind "$LIVE_PID")"

echo "=== aitask_live_endpoint.sh: result-code contract (t1657_4) ==="

# --- 1. unlocked -----------------------------------------------------------
#
# The commonest case by far: the note that matters most is written to a task
# nobody is working on yet.

out="$(run_resolve 800 2>/dev/null)"; rc=$?
assert_eq "1a. no lock record => unlocked" "LIVE_NONE:unlocked" "$out"
assert_eq "1b. unlocked is a SUCCESSFUL resolution (exit 0)" "0" "$rc"

# --- 2. remote_host --------------------------------------------------------
#
# The lock records `hostname` precisely so a cross-machine holder degrades to the
# durable lane instead of being chased across the network.

forge_lock 803 "task_id: 803
locked_by: alice@test.com
locked_at: 2026-09-06 09:00
hostname: some-other-machine
pid: $LIVE_PID
pid_starttime: $LIVE_TOKEN
pid_starttime_kind: $LIVE_KIND
"
out="$(run_resolve 803 2>/dev/null)"; rc=$?
assert_eq "2a. lock on another host => remote_host" "LIVE_NONE:remote_host" "$out"
assert_eq "2b. exit 0" "0" "$rc"

# --- 3. holder_dead --------------------------------------------------------

forge_lock 803 "task_id: 803
locked_by: alice@test.com
locked_at: 2026-09-06 09:00
hostname: $THIS_HOST
pid: $DEAD_PID
pid_starttime: 999999999
pid_starttime_kind: proc
"
out="$(run_resolve 803 2>/dev/null)"
assert_eq "3a. provably gone holder => holder_dead" "LIVE_NONE:holder_dead" "$out"

# --- 4. holder_unknown, INCLUDING the legacy record ------------------------
#
# `unknown` must never be collapsed into `dead` — that conflation is the t1465
# defect class, and it is the difference between "nobody is there" and "I cannot
# tell", which a sender needs to distinguish.
#
# 4b is the legacy shape: locks written before the PID anchor existed carry NO
# `pid:` line at all. There is a real one in this repo (t259). The resolver must
# read it as unknown, never invent a holder for it.

forge_lock 803 "task_id: 803
locked_by: alice@test.com
locked_at: 2026-09-06 09:00
hostname: $THIS_HOST
pid: $LIVE_PID
pid_starttime: definitely-not-this-processes-token
pid_starttime_kind: unrecognised-kind
"
out="$(run_resolve 803 2>/dev/null)"
assert_eq "4a. uninspectable identity => holder_unknown" "LIVE_NONE:holder_unknown" "$out"

forge_lock 803 "task_id: 803
locked_by: alice@test.com
locked_at: 2026-02-26 17:27
hostname: $THIS_HOST
"
out="$(run_resolve 803 2>/dev/null)"
assert_eq "4b. legacy lock with no pid: line => holder_unknown" \
    "LIVE_NONE:holder_unknown" "$out"

# --- 5. agent_unknown ------------------------------------------------------
#
# `implemented_with` is written by Agent Attribution at Step 7 while the lock is
# claimed at Step 4. During planning a task is legitimately Implementing, locked,
# and blank here. That window must read as unknown, NOT as an error.

live_lock() {
    forge_lock "$1" "task_id: $1
locked_by: alice@test.com
locked_at: 2026-09-06 09:00
hostname: $THIS_HOST
pid: $LIVE_PID
pid_starttime: $LIVE_TOKEN
pid_starttime_kind: $LIVE_KIND
"
}

live_lock 801
out="$(run_resolve 801 2>/dev/null)"; rc=$?
assert_eq "5a. empty implemented_with => agent_unknown" "LIVE_NONE:agent_unknown" "$out"
assert_eq "5b. the attribution window is not an error (exit 0)" "0" "$rc"

# --- 6. agent_unsupported --------------------------------------------------

live_lock 802
out="$(run_resolve 802 2>/dev/null)"
assert_eq "6a. family with no adapter => agent_unsupported:<family>" \
    "LIVE_NONE:agent_unsupported:codex" "$out"

# --- 7. The manifest DRIVES the decision -----------------------------------
#
# Without this pair, "the resolver contains no agent literal" could be true while
# the behaviour came from somewhere else entirely. AIT_LIVE_DELIVERY_DIR is the
# documented seam; the two runs differ ONLY in what the manifest says.

live_lock 800
MANIFEST_DIR="$TMP/manifest"
mkdir -p "$MANIFEST_DIR"

run_with_manifest() { ( cd "$DATA" && AIT_LIVE_DELIVERY_DIR="$MANIFEST_DIR" "$RESOLVE" "$@" 2>/dev/null ); }

: > "$MANIFEST_DIR/agents.txt"
out="$(run_with_manifest 800)"
assert_eq "7a. family absent from the manifest => agent_unsupported" \
    "LIVE_NONE:agent_unsupported:claudecode" "$out"

# The same input, the same code, one extra manifest row naming a procedure that
# EXISTS: the branch flips.
echo "adapter body" > "$MANIFEST_DIR/adapter.md"
printf '# comment\n\nclaudecode  adapter.md\n' > "$MANIFEST_DIR/agents.txt"
out="$(run_with_manifest 800)"
assert_not_contains "7b. a manifest row with a real procedure passes the agent gate" \
    "agent_unsupported" "$out"

# A fabricated family proves the lookup is by NAME from the file, not a
# hardcoded set that happens to contain the real one.
make_task 804 "fictionalagent/v1"
git -C "$DATA" add -A && git -C "$DATA" commit -qm "task 804" >/dev/null
live_lock 804
out="$(run_with_manifest 804)"
assert_eq "7c. fabricated family, absent from the manifest => unsupported" \
    "LIVE_NONE:agent_unsupported:fictionalagent" "$out"
printf 'fictionalagent  adapter.md\n' >> "$MANIFEST_DIR/agents.txt"
out="$(run_with_manifest 804)"
assert_not_contains "7d. …and declaring it in the manifest lets it through" \
    "agent_unsupported" "$out"

# --- 7'. A NAME MATCH IS NOT ENOUGH ----------------------------------------
#
# `LIVE_PANE` is a promise the caller acts on: a live endpoint AND a procedure to
# deliver through. A row that names a family but no usable procedure would break
# that promise one layer too late — the caller has already been told the endpoint
# is live and then finds nothing to run. `agent_unsupported` is the honest
# answer, because that is exactly what a family with no usable adapter is.
#
# These cases pin the rows a truncated install or a hand-edit actually produces.

printf 'claudecode\n' > "$MANIFEST_DIR/agents.txt"
assert_eq "7e. row with no procedure column => agent_unsupported" \
    "LIVE_NONE:agent_unsupported:claudecode" "$(run_with_manifest 800)"

printf 'claudecode  not_there.md\n' > "$MANIFEST_DIR/agents.txt"
assert_eq "7f. row naming a file that does not exist => agent_unsupported" \
    "LIVE_NONE:agent_unsupported:claudecode" "$(run_with_manifest 800)"

# A DIRECTORY is a readable path but not a readable procedure. `-r` alone is
# true for it, so this is the shape that slips past a "does the path exist and
# can I read it" check while leaving the caller with nothing to read.
mkdir -p "$MANIFEST_DIR/notafile.md"
printf 'claudecode  notafile.md\n' > "$MANIFEST_DIR/agents.txt"
assert_eq "7f'. row naming a DIRECTORY => agent_unsupported" \
    "LIVE_NONE:agent_unsupported:claudecode" "$(run_with_manifest 800)"

printf 'claudecode  adapter.md\n' > "$MANIFEST_DIR/agents.txt"
chmod 000 "$MANIFEST_DIR/adapter.md"
if [[ -r "$MANIFEST_DIR/adapter.md" ]]; then
    # Running as root (or on a filesystem that ignores the mode): the unreadable
    # case cannot be produced, and asserting it here would pass vacuously.
    echo "SKIP 7g: cannot make a file unreadable in this environment"
else
    assert_eq "7g. row naming an unreadable file => agent_unsupported" \
        "LIVE_NONE:agent_unsupported:claudecode" "$(run_with_manifest 800)"
fi
chmod 644 "$MANIFEST_DIR/adapter.md"

# The procedure column is untrusted data. A row must not be able to point the
# resolver at a file outside the delivery directory.
mkdir -p "$MANIFEST_DIR/sub"
echo "elsewhere" > "$TMP/outside.md"
printf 'claudecode  ../outside.md\n' > "$MANIFEST_DIR/agents.txt"
assert_eq "7h. a traversing procedure path is refused, not followed" \
    "LIVE_NONE:agent_unsupported:claudecode" "$(run_with_manifest 800)"
printf 'claudecode  sub/adapter.md\n' > "$MANIFEST_DIR/agents.txt"
cp "$MANIFEST_DIR/adapter.md" "$MANIFEST_DIR/sub/adapter.md"
assert_eq "7i. …and so is a subdirectory path, even one that resolves" \
    "LIVE_NONE:agent_unsupported:claudecode" "$(run_with_manifest 800)"

# The SHIPPED manifest must satisfy its own rule — otherwise the live lane is
# dead in the product while every fixture-driven case above passes.
printf 'claudecode  adapter.md\n' > "$MANIFEST_DIR/agents.txt"
assert_not_contains "7j. the shipped manifest declares a usable adapter" \
    "agent_unsupported" "$(cd "$DATA" && "$RESOLVE" 800 2>/dev/null)"

# --- 8. no_pane ------------------------------------------------------------
#
# Past every earlier gate — locked, local, alive, a known agent family — but no
# pane on the gateway socket maps to the holder. Forced through the socket seam:
# pointing the gateway at a server that does not exist is the one way to make the
# pane map empty without killing anything real.

out="$( cd "$DATA" && AITASKS_TMUX_SOCKET="ait_nonexistent_$$" "$RESOLVE" 800 2>/dev/null )"; rc=$?
assert_eq "8a. holder alive but no gateway pane => no_pane" "LIVE_NONE:no_pane" "$out"
assert_eq "8b. exit 0" "0" "$rc"

# --- 9. LIVE_ERROR is disjoint from LIVE_NONE ------------------------------
#
# "There is no live endpoint" and "the resolver could not run" are different
# answers and must not be confusable: the first is a successful send, the second
# is a bug to report.

out="$(run_resolve 'not-an-id' 2>/dev/null)"; rc=$?
assert_eq "9a. a malformed id is an ERROR, not a degradation" "LIVE_ERROR:bad_task_id" "$out"
assert_eq "9b. …and exits non-zero" "2" "$rc"

live_lock 899   # a lock for a task that has no file
out="$(run_resolve 899 2>/dev/null)"; rc=$?
assert_contains "9c. a lock with no task file is an ERROR" "LIVE_ERROR:task_not_found" "$out"
assert_eq "9d. …and exits non-zero" "2" "$rc"

assert_not_contains "9e. no LIVE_NONE line ever carries an error reason" \
    "LIVE_NONE" "$out"

# --- 9'. STDOUT CARRIES EXACTLY ONE LINE, INCLUDING ON MISUSE --------------
#
# The contract is "exactly ONE line on stdout, always". A usage error that prints
# its help to stdout breaks it in the worst way: a caller reading the first line
# finds `Usage:` and parses prose as a result. So the help goes to stderr and the
# single result line stays on stdout.
#
# Asserted as a LINE COUNT, not just a prefix — `assert_contains` on
# `LIVE_ERROR:usage` would pass with pages of help text above it.

check_usage_error() {   # <label> [args...]
    local label="$1"; shift
    local out err rc
    out="$( cd "$DATA" && "$RESOLVE" "$@" 2>/dev/null )"; rc=$?
    assert_eq "9f. [$label] stdout is exactly one line" "1" "$(printf '%s\n' "$out" | grep -c .)"
    assert_eq "9g. [$label] …and it is the result line" "LIVE_ERROR:usage" "$out"
    assert_eq "9h. [$label] …exit 2" "2" "$rc"
    assert_not_contains "9i. [$label] no usage prose on stdout" "Usage:" "$out"
    # The help is not discarded — it goes where prose belongs.
    err="$( cd "$DATA" && "$RESOLVE" "$@" 2>&1 >/dev/null )"
    assert_contains "9j. [$label] …the help is on stderr" "Usage:" "$err"
}

check_usage_error "<no argument>"
check_usage_error "too many arguments" 800 extra

# `--help` is the ONE documented exception: that invocation is addressed to a
# human, so prose on stdout is correct there. Pinned so the exception stays
# deliberate rather than becoming a second leak.
out="$( cd "$DATA" && "$RESOLVE" --help 2>/dev/null )"; rc=$?
assert_contains "9k. --help prints usage on stdout" "Usage:" "$out"
assert_eq "9l. …and exits 0" "0" "$rc"

# --- 10. The id is accepted in both circulating forms ----------------------
#
# Measured (aitask_note.sh section 0): `aitask_lock.sh --check t1669` prints
# NOTHING while `--check 1669` works. A resolver that forwarded the 't' form
# unchanged would answer "unlocked" for every t-prefixed id — a silent wrong
# answer, not an error. Both must agree.

live_lock 800
bare_out="$(run_resolve 800 2>/dev/null)"
pfx_out="$(run_resolve t800 2>/dev/null)"
assert_eq "10a. t-prefixed and bare ids resolve identically" "$bare_out" "$pfx_out"
assert_not_contains "10b. …and neither reads as unlocked" "unlocked" "$pfx_out"

# --- 11. lib/lock_record.sh, directly --------------------------------------
#
# The shared parse. aitask_note.sh reads it for a self-identity verdict and the
# resolver for a liveness verdict; neither exercises the parse on its own.

live_lock 800
( cd "$DATA" && lock_record_read 800 ) >/dev/null
# The function sets shell variables, so it has to run in THIS shell to be read.
cd "$DATA" || exit 1
lock_record_read 800
assert_eq "11a. hostname parsed"          "$THIS_HOST"  "$LOCK_REC_HOST"
assert_eq "11b. pid parsed"               "$LIVE_PID"   "$LOCK_REC_PID"
assert_eq "11c. pid_starttime parsed"     "$LIVE_TOKEN" "$LOCK_REC_TOKEN"
assert_eq "11d. pid_starttime_kind parsed" "$LIVE_KIND" "$LOCK_REC_KIND"

# A legacy record: the PID must come back EMPTY, never defaulted. Inventing a
# value here would turn "this lock cannot say who holds it" into a claim about a
# process, and lock_holder_liveness would then answer about the wrong one.
forge_lock 800 "task_id: 800
locked_by: alice@test.com
locked_at: 2026-02-26 17:27
hostname: $THIS_HOST
"
lock_record_read 800
assert_eq "11e. legacy record: hostname still parsed" "$THIS_HOST" "$LOCK_REC_HOST"
assert_eq "11f. legacy record: pid is EMPTY, not defaulted" "" "$LOCK_REC_PID"
assert_eq "11g. legacy record: token is EMPTY"             "" "$LOCK_REC_TOKEN"
assert_eq "11h. an empty pid reads as unknown, never dead" \
    "unknown" "$(lock_holder_liveness "$LOCK_REC_PID" "${LOCK_REC_TOKEN:--}" "${LOCK_REC_KIND:-proc}")"

# Unlocked returns 1 AND leaves no stale field from the previous call.
if lock_record_read 897; then
    TOTAL=$((TOTAL + 1)); FAIL=$((FAIL + 1))
    echo "FAIL: 11i. lock_record_read on an unlocked task returned 0"
else
    TOTAL=$((TOTAL + 1)); PASS=$((PASS + 1))
fi
assert_eq "11j. …and clears the previous call's hostname" "" "$LOCK_REC_HOST"
assert_eq "11k. …and clears the previous call's pid"      "" "$LOCK_REC_PID"

cd "$PROJECT_DIR" || exit 1

# --- summary ---------------------------------------------------------------

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ "$FAIL" -eq 0 ]]; then
    echo "ALL TESTS PASSED"
    exit 0
fi
echo "SOME TESTS FAILED"
exit 1
