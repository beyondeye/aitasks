#!/usr/bin/env bash
# test_session_hook_live.sh - the A8 OBSERVING test (t1705_3).
#
# tests/test_agent_sessions_stamp.sh pins ait_stamp_record's argv contract with
# no server; its header assigns the other half here: "is the option really set
# on a real pane after a real hook fire". This module answers that against a
# REAL tmux pane and the REAL store -- only the code agent is absent (the hook
# is invoked directly with a fixture payload, which is exactly what an agent
# does with it).
#
# ISOLATION POLICY: require_isolated_tmux ONLY -- deliberately not
# require_clean_ait_server. Every tmux call the hook makes is gateway-routed
# (display-message -p, set-option -p on its own pane) and it arms no
# `pane-died` / `remain-on-exit` hook, so it is in the "isolate, NEVER refuse"
# class documented at tests/lib/tmux_isolation.sh:26-36. This suite therefore
# runs from inside tmux and alongside live agents, unlike the t1705_1 spike.
#
# Run: bash tests/test_session_hook_live.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=lib/tmux_isolation.sh
. "$SCRIPT_DIR/lib/tmux_isolation.sh"

PASS=0
FAIL=0
TOTAL=0

if ! command -v tmux >/dev/null 2>&1; then
    echo "SKIP: tmux not installed"
    exit 0
fi

require_isolated_tmux

TMP="$(mktemp -d "${TMPDIR:-/tmp}/ait_hook_live_XXXXXX")"

# The socket dir must be SHORT and must not live under $TMPDIR. A unix socket
# path is capped at ~104 bytes on macOS, and tmux builds it as
# $TMUX_TMPDIR/tmux-<uid>/<socket>; macOS $TMPDIR is /var/folders/<long>/T/,
# so a mktemp dir there overflows the cap and every tmux call fails with
# "File name too long". /tmp keeps it well inside the limit.
TMUX_TMPDIR="$(mktemp -d "/tmp/aithl.XXXXXX")"
export TMUX_TMPDIR
SOCK="hl$$"

cleanup() {
    tmux -L "$SOCK" kill-server 2>/dev/null || true
    rm -rf "$TMP" "$TMUX_TMPDIR"
}
trap cleanup EXIT

# The gateway follows this: a named socket both the fixture and the hook agree on.
export AITASKS_TMUX_SOCKET="$SOCK"

# --- a real project root ---------------------------------------------------
ROOT="$(cd "$TMP" && pwd -P)/proj"
mkdir -p "$ROOT/aitasks/metadata" "$ROOT/.aitask-scripts/lib"
: >"$ROOT/aitasks/metadata/project_config.yaml"
# The whole lib/, not an enumerated subset: these helpers source each other
# transitively (registry_lock.sh -> stale_lock.sh, ...), and chasing one missing
# file per run is how a live suite ends up quietly skipping instead of failing.
cp "$PROJECT_DIR/.aitask-scripts/lib/"* "$ROOT/.aitask-scripts/lib/" 2>/dev/null
cp "$PROJECT_DIR/.aitask-scripts/aitask_agent_sessions.sh" "$ROOT/.aitask-scripts/"

# The REAL store, in a scratch file.
export AITASKS_AGENT_SESSIONS_FILE="$TMP/agent_sessions.json"

HOOK="$PROJECT_DIR/.aitask-scripts/aitask_session_hook.sh"
FIXTURE="$PROJECT_DIR/tests/data/session_hooks/claude_sessionstart.json"

# --- a real pane -----------------------------------------------------------
tmux -L "$SOCK" new-session -d -s hooktest -n "agent-pick-4242" "sleep 300" 2>/dev/null
if ! tmux -L "$SOCK" has-session -t hooktest 2>/dev/null; then
    echo "SKIP: could not start an isolated tmux server on $TMUX_TMPDIR" >&2
    tmux -L "$SOCK" new-session -d -s probe "sleep 1" 2>&1 | head -2 >&2
    exit 0
fi
PANE="$(tmux -L "$SOCK" list-panes -t hooktest -F '#{pane_id}' | head -1)"
[ -n "$PANE" ] || { echo "SKIP: no pane"; exit 0; }

SID="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['session_id'])" "$FIXTURE")"
payload_for_root() {
    python3 -c "
import json,sys
d=json.load(open(sys.argv[1])); d['cwd']=sys.argv[2]
print(json.dumps(d))" "$FIXTURE" "$1"
}

fire_hook() {
    payload_for_root "$ROOT" | env TMUX_PANE="$PANE" TMUX= \
        AITASK_AGENT_STRING="claudecode/opus5" bash "$HOOK" 2>"$TMP/err"
}

pane_opt() {
    tmux -L "$SOCK" display-message -p -t "$PANE" "#{$1}" 2>/dev/null
}

echo "=== A8 observing test: a real pane, a real store (t1705_3) ==="

# ---------------------------------------------------------------------------
echo "--- first fire ---"
out="$(fire_hook)"; rc=$?
assert_eq "hook exits 0" "0" "$rc"
assert_eq "hook writes nothing to stdout" "" "$out"

listing="$("$ROOT/.aitask-scripts/aitask_agent_sessions.sh" list 2>&1)"
stored_id="$(printf '%s\n' "$listing" | sed -n 's/^SESSION:\([^|]*\)|.*/\1/p' | head -1)"
assert_contains "a record was created" "SESSION:" "$listing"

# GUARD against a pass by absence: every assertion below compares against
# $stored_id, so an empty one would make them all pass vacuously.
if [ -z "$stored_id" ]; then
    echo "FATAL: no record id — the assertions below would pass vacuously." >&2
    echo "store said: $listing" >&2
    echo "hook stderr: $(cat "$TMP/err" 2>/dev/null)" >&2
    exit 1
fi

# THE assertion this module exists for.
assert_eq "A8: @aitask_record is really set on the pane" "$stored_id" "$(pane_opt @aitask_record)"
assert_eq "A8: the stamp is a canonical 8-hex record id" "yes" \
    "$(printf '%s' "$(pane_opt @aitask_record)" | grep -Eq '^[0-9a-f]{8}$' && echo yes || echo no)"
assert_eq "@aitask_agent_session carries the payload session id" "$SID" "$(pane_opt @aitask_agent_session)"

echo "--- the record carries what the payload and pane said ---"
show="$("$ROOT/.aitask-scripts/aitask_agent_sessions.sh" show "$stored_id" 2>/dev/null)"
assert_contains "record stores the codeagent session id" "codeagent_session_id:$SID" "$show"
assert_contains "record stores the window name" "window:agent-pick-4242" "$show"
assert_contains "record stores the task id from the window name" "task_id:4242" "$show"
assert_contains "record stores the operation" "operation:pick" "$show"
assert_contains "record stores the pane id" "pane_id:$PANE" "$show"

# ---------------------------------------------------------------------------
echo "--- second fire in the same pane REUSES the record ---"
# This is the duplicate-record regression A8 warns about: a stored record whose
# pane was never stamped arrives at the next upsert with no --id, and the freeze
# engine's fallback then creates a SECOND record for an already-recorded agent.
out2="$(fire_hook)"; rc2=$?
assert_eq "second fire exits 0" "0" "$rc2"
count="$("$ROOT/.aitask-scripts/aitask_agent_sessions.sh" list 2>/dev/null | grep -c '^SESSION:')"
assert_eq "still exactly ONE record after a second fire" "1" "$count"
assert_eq "the pane still points at the same record" "$stored_id" "$(pane_opt @aitask_record)"

# ---------------------------------------------------------------------------
echo "--- a blank session id leaves the stored id intact (C3, live) ---"
python3 -c "
import json,sys
d=json.load(open(sys.argv[1])); d['cwd']=sys.argv[2]; d['session_id']=''
print(json.dumps(d))" "$FIXTURE" "$ROOT" \
    | env TMUX_PANE="$PANE" TMUX= bash "$HOOK" 2>/dev/null
show2="$("$ROOT/.aitask-scripts/aitask_agent_sessions.sh" show "$stored_id" 2>/dev/null)"
assert_contains "C3 live: stored session id was NOT blanked" "codeagent_session_id:$SID" "$show2"
assert_eq "C3 live: pane option was NOT blanked" "$SID" "$(pane_opt @aitask_agent_session)"

echo ""
echo "========================================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
echo "========================================="
[[ "$FAIL" -eq 0 ]] || exit 1
echo "ALL TESTS PASSED"
