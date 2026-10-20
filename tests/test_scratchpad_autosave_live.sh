#!/usr/bin/env bash
# test_scratchpad_autosave_live.sh - the scratchpad's autosave against real
# pane deaths (t2073_2).
#
# Run: bash tests/test_scratchpad_autosave_live.sh
#
# The app runs in a pane on a PRIVATE tmux server (`-L ait_scratch_<pid>`, inside
# require_isolated_tmux's TMUX_TMPDIR), with the REAL store helper writing into a
# throwaway fixture repo. It is launched through `exec`, so `#{pane_pid}` is the
# app itself.
#
# "Hard kill" means `kill -KILL` of the app: nothing of the app runs afterwards,
# so what is on disk is exactly what autosave already landed. `kill-pane` is the
# other death — it delivers SIGHUP, which the app answers with a detached flush —
# and is tested as its own path.
#
#   (a)  type, wait out the debounce, hard kill            -> on disk
#   (b)  a token every 0.2 s for 6 s, hard kill at once    -> every token older
#        than 3 s + 1.5 s save latency is on disk
#   (c)  CONTROL: hard kill before the first deadline      -> the old content
#        (documents the loss window: changes not in the latest saved buffer)
#   (d)  type, kill-pane at 0.3 s                          -> the SIGHUP flush lands
#   (e)  post-phase orphan_save_handoff: the helper's pause fifo parks a save of
#        a pasted >= 8 KiB buffer, then the app is hard-killed. The orphaned save
#        child still holds the inherited flock; once released it lands the
#        buffer byte-identically, the flock frees, and a fresh instance owns the
#        store and shows it.
#   (f)  (e) with kill-pane instead of kill -KILL: a graceful SIGHUP exit with a
#        save in flight must not kill that save.

set -uo pipefail

TEST_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

PASS=0
FAIL=0
TOTAL=0

if ! command -v tmux >/dev/null 2>&1; then
    echo "SKIP: tmux not available"
    exit 0
fi

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=lib/tmux_isolation.sh
. "$TEST_SCRIPT_DIR/lib/tmux_isolation.sh"
require_isolated_tmux
# shellcheck source=lib/venv_python.sh
. "$TEST_SCRIPT_DIR/lib/venv_python.sh"

# The header separator is `·`; capture-pane reads it back as `_` under a
# non-UTF-8 locale.
if [[ "$(locale charmap 2>/dev/null)" != "UTF-8" ]]; then
    export LC_ALL=C.UTF-8
fi

APP="$PROJECT_DIR/.aitask-scripts/scratchpad/scratchpad_app.py"
STORE_SH="$PROJECT_DIR/.aitask-scripts/aitask_scratchpad_store.sh"
SOCK="ait_scratch_$$"
T="$(mktemp -d "${TMPDIR:-/tmp}/ait_scratch_live.XXXXXX")"
REPO="$T/repo"
NOTES="$REPO/pad/42/notes.md"
HOLDER="$REPO/pad/42/.holder.lock"
FIFO="$T/pause"
CASE=0

# Every call names the private server; `-f /dev/null` keeps the user's config
# (base-index, hooks, default-command) out of the fixture.
tm() { tmux -L "$SOCK" -f /dev/null "$@"; }

cleanup() {
    # Never leave a parked helper behind: feed every fifo once more.
    if [[ -p "$FIFO" ]]; then
        timeout 1 bash -c "printf 'x\n' > '$FIFO'" 2>/dev/null || true
    fi
    tm kill-server 2>/dev/null || true
    rm -rf "$T"
}
trap cleanup EXIT

fixture() {
    rm -rf "$REPO" "$FIFO" "$FIFO.reached"
    mkdir -p "$REPO/aitasks"
    printf -- '---\nstatus: Implementing\n---\n' > "$REPO/aitasks/t42_x.md"
}

store() {
    TASK_DIR="$REPO/aitasks" AITASK_SCRATCHPAD_DIR="$REPO/pad" "$STORE_SH" "$@"
}

notes() { cat "$NOTES" 2>/dev/null; }

# launch [VAR=value ...] -> sets TARGET (no subshell: CASE must advance)
launch() {
    CASE=$((CASE + 1))
    local cmd
    cmd="exec env TASK_DIR=$(printf '%q' "$REPO/aitasks")"
    cmd+=" AITASK_SCRATCHPAD_DIR=$(printf '%q' "$REPO/pad")"
    local kv
    for kv in "$@"; do
        cmd+=" $(printf '%q' "$kv")"
    done
    cmd+=" $(printf '%q' "$AITASK_PYTHON") $(printf '%q' "$APP") --task 42"
    tm new-session -d -s "c$CASE" -x 100 -y 30 -c "$REPO" "$cmd"
    TARGET="=c$CASE:"
}

screen() { tm capture-pane -p -t "$1" 2>/dev/null; }

# wait_until <seconds> <command...> - bounded poll, never an assertion
wait_until() {
    local limit="$1"
    shift
    local deadline=$((SECONDS + limit))
    until "$@"; do
        (( SECONDS >= deadline )) && return 1
        sleep 0.1
    done
}

is_saved() { screen "$1" | grep -qE 't42 .{1,3} saved( |$)'; }
pane_pid() { tm display -p -t "$1" '#{pane_pid}'; }
type_text() { tm send-keys -t "$1" -l "$2"; }
holder_free() {
    "$AITASK_PYTHON" -c 'import fcntl, os, sys
fd = os.open(sys.argv[1], os.O_RDWR)
fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)' "$HOLDER" 2>/dev/null
}
reached_is() { [[ "$(cat "$FIFO.reached" 2>/dev/null)" == "$1" ]]; }
release_fifo() { timeout 5 bash -c "printf 'go\n' > '$FIFO'"; }
notes_is() { [[ "$(notes)" == "$1" ]]; }
gone() { ! kill -0 "$1" 2>/dev/null; }

start_ready() {
    launch
    if ! wait_until 15 is_saved "$TARGET"; then
        echo "FAIL: case $CASE never reached 'saved'" >&2
        screen "$TARGET" >&2
    fi
}

# --- (a) debounce, then a hard kill -------------------------------------------
fixture
start_ready
target="$TARGET"
type_text "$target" "alpha"
sleep 2.5
pid="$(pane_pid "$target")"
kill -KILL "$pid"
wait_until 5 gone "$pid"
assert_eq "(a) debounced text survives a hard kill" "alpha" "$(notes)"

# --- (b) continuous typing, then an immediate hard kill ----------------------
fixture
start_ready
target="$TARGET"
declare -a sent_at=()
start_ns="$(date +%s%N)"
i=0
while (( ( $(date +%s%N) - start_ns ) < 6000000000 )); do
    i=$((i + 1))
    sent_at[i]="$(date +%s%N)"
    type_text "$target" "k$i "
    sleep 0.2
done
pid="$(pane_pid "$target")"
kill_ns="$(date +%s%N)"
kill -KILL "$pid"
wait_until 5 gone "$pid"
on_disk="$(notes)"
missing=""
old=0
for (( j = 1; j <= i; j++ )); do
    if (( kill_ns - sent_at[j] > 4500000000 )); then
        old=$((old + 1))
        case " $on_disk" in
            *" k$j "*) ;;
            *) missing+=" k$j" ;;
        esac
    fi
done
assert_eq "(b) every token older than 3 s + 1.5 s is on disk ($old tokens)" "" "$missing"
if (( old == 0 )); then
    assert_eq "(b) the run produced tokens old enough to check" "nonzero" "0"
fi

# --- (c) CONTROL: a hard kill before the first deadline -----------------------
fixture
store open 42 >/dev/null
printf 'old' | store save 42 >/dev/null
start_ready
target="$TARGET"
type_text "$target" "new"
sleep 0.3
pid="$(pane_pid "$target")"
kill -KILL "$pid"
wait_until 5 gone "$pid"
sleep 0.5
assert_eq "(c) control: a kill before the debounce leaves the old content" "old" "$(notes)"

# --- (d) kill-pane delivers SIGHUP -> the detached flush lands ----------------
fixture
start_ready
target="$TARGET"
type_text "$target" "hup"
sleep 0.3
tm kill-pane -t "$target"
wait_until 5 notes_is "hup"
assert_eq "(d) kill-pane: the SIGHUP flush lands" "hup" "$(notes)"

# --- (e)/(f) post-phase orphan_save_handoff ----------------------------------
BIG="BEGIN-"
for (( n = 1; n <= 420; n++ )); do
    BIG+="$(printf 'line%04d-abcdefghij ' "$n")"
done
BIG+="-END"
want_sum="$(printf '%s' "$BIG" | cksum)"

orphan_case() {
    local label="$1" how="$2" target pid
    fixture
    mkfifo "$FIFO"
    launch "AITASK_SCRATCHPAD_PAUSE_FIFO=$FIFO"
    target="$TARGET"
    wait_until 15 reached_is "open:after_task_check"
    release_fifo
    if ! wait_until 15 is_saved "$target"; then
        echo "FAIL: ($label) never reached 'saved'" >&2
    fi
    rm -f "$FIFO.reached"
    # One bracketed paste = one edit, so the parked save carries the whole
    # buffer rather than whatever had been typed when the deadline fired.
    tm set-buffer -b spbig -- "$BIG"
    tm paste-buffer -p -d -b spbig -t "$target"
    wait_until 15 reached_is "save:after_exists_check"
    assert_eq "($label) the save of the pasted buffer is parked" \
        "save:after_exists_check" "$(cat "$FIFO.reached" 2>/dev/null)"
    pid="$(pane_pid "$target")"
    if [[ "$how" == "kill" ]]; then
        kill -KILL "$pid"
    else
        tm kill-pane -t "$target"
    fi
    wait_until 5 gone "$pid"
    assert_eq "($label) the app is gone" "gone" "$(gone "$pid" && echo gone)"
    if holder_free; then
        assert_eq "($label) the orphaned save still holds the inherited flock" "busy" "free"
    else
        assert_eq "($label) the orphaned save still holds the inherited flock" "busy" "busy"
    fi
    assert_not_contains "($label) nothing landed before release" "-END" "$(notes)"
    release_fifo
    wait_until 5 notes_is "$BIG"
    assert_eq "($label) the released save lands byte-identical" \
        "$want_sum" "$(notes | cksum)"
    wait_until 5 holder_free
    if holder_free; then
        assert_eq "($label) the flock frees once the save lands" "free" "free"
    else
        assert_eq "($label) the flock frees once the save lands" "free" "busy"
    fi
    rm -f "$FIFO" "$FIFO.reached"
    launch
    target="$TARGET"
    if wait_until 15 is_saved "$target"; then
        assert_eq "($label) a fresh instance owns the store" "saved" "saved"
    else
        assert_eq "($label) a fresh instance owns the store" "saved" "$(screen "$target")"
    fi
    assert_contains "($label) the fresh instance shows the landed notes" \
        "BEGIN-line0001" "$(screen "$target")"
    tm kill-pane -t "$target" 2>/dev/null || true
}

orphan_case e kill
orphan_case f kill-pane

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ "$FAIL" -eq 0 ]]; then
    echo "ALL TESTS PASSED"
    exit 0
fi
echo "SOME TESTS FAILED"
exit 1
