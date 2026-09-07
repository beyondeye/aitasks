#!/usr/bin/env bash
# test_agent_sessions_stamp.sh - The pane->record stamp helper (t1705_2 A8).
#
# `ait_stamp_record` is the ONE sanctioned way to establish the pane->record
# join. The store itself never touches tmux, so the stamp is the caller's
# obligation — the SessionStart hook (t1705_3) on the normal path, the freeze
# engine (t1705_4) on its fallback path — and this helper is what they call so
# the obligation is a function rather than prose in a plan.
#
# NO LIVE TMUX SERVER. The gateway (`lib/tmux_exec.sh::ait_tmux`) resolves to
# `command tmux …`, so the argv is observable by putting a recording stub named
# `tmux` first on PATH. That keeps this suite runnable anywhere, which matters:
# the OBSERVING test — is the option really set on a real pane after a real hook
# fire — belongs to t1705_3's hook suite and to t1705_8's acceptance run, both
# of which already own a live server. This module owns the argv contract and the
# id guard.
#
# Run: bash tests/test_agent_sessions_stamp.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

TMP="$(mktemp -d "${TMPDIR:-/tmp}/ait_sessions_stamp_XXXXXX")"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

# A recording stub in place of the real tmux binary. It writes its full argv,
# one argument per line, so an assertion can see exactly what the gateway built.
mkdir -p "$TMP/bin"
cat >"$TMP/bin/tmux" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$@" >>"$TMUX_STUB_LOG"
exit 0
STUB
chmod +x "$TMP/bin/tmux"

export TMUX_STUB_LOG="$TMP/tmux.log"
export PATH="$TMP/bin:$PATH"
# Pin the socket so the gateway's flag is deterministic across machines.
export AITASKS_TMUX_SOCKET="ait-test"

# shellcheck source=../.aitask-scripts/lib/agent_sessions.sh
. "$PROJECT_DIR/.aitask-scripts/lib/agent_sessions.sh"

reset_log() { : >"$TMUX_STUB_LOG"; }
log_contents() { cat "$TMUX_STUB_LOG" 2>/dev/null; }

echo "=== Test 1: constants carry the documented option spellings ==="
assert_eq "record option spelling" "@aitask_record" "$AIT_RECORD_OPTION"
assert_eq "frozen option spelling" "@aitask_frozen" "$AIT_FROZEN_OPTION"
assert_eq "standin-ready option spelling" "@aitask_standin_ready" "$AIT_STANDIN_READY_OPTION"
assert_eq "agent-session option spelling" "@aitask_agent_session" "$AIT_AGENT_SESSION_OPTION"

echo "=== Test 2: a well-formed stamp emits exactly one set-option call ==="
reset_log
ait_stamp_record "%9" "7f3a2c1d"
rc=$?
assert_eq "stamp of a canonical id succeeds" "0" "$rc"
got="$(log_contents | tr '\n' ' ')"
assert_contains "argv carries set-option -p with the pane, option and id" \
    "set-option -p -t %9 @aitask_record 7f3a2c1d" "$got"
assert_contains "argv routes through the gateway's socket flag" "-L ait-test" "$got"

echo "=== Test 3: a non-canonical id is refused and emits NO tmux call ==="
# The id reaches a pane option that later feeds capture_dir() -- whose drop
# DELETES the tree -- and the stand-in command string handed to respawn-pane.
# Refusing before the call is what keeps a hostile value out of both.
for bad in "../../etc" "a'; rm -rf /; echo '" "7F3A2C1D" "7f3a2c1" "" ; do
    reset_log
    ait_stamp_record "%9" "$bad" 2>/dev/null
    rc=$?
    assert_eq "refuses non-canonical id '$bad'" "2" "$rc"
    assert_eq "no tmux call emitted for '$bad'" "" "$(log_contents)"
done

echo "=== Test 4: a missing pane is refused too ==="
reset_log
ait_stamp_record "" "7f3a2c1d" 2>/dev/null
rc=$?
assert_eq "refuses an empty pane" "2" "$rc"
assert_eq "no tmux call emitted for an empty pane" "" "$(log_contents)"

echo "=== Test 5: ait_frozen_dir resolves root and per-record paths ==="
AITASKS_FROZEN_DIR="$TMP/frozen" ; export AITASKS_FROZEN_DIR
assert_eq "frozen root follows the env override" "$TMP/frozen" "$(ait_frozen_dir)"
assert_eq "per-record capture dir" "$TMP/frozen/7f3a2c1d" "$(ait_frozen_dir 7f3a2c1d)"

echo "=== Test 6: shell and Python agree on every option spelling ==="
# The Python copies now live in monitor/monitor_core.py beside
# SHADOW_TARGET_OPTION (t1705_4), which is where the readers are: the
# list-panes format, kill_agent_pane_smart and the freeze engine all take their
# spellings from there. Two spellings of one option would silently break the
# join — the stamper writes one name, the reader looks for another, and every
# affected agent simply looks unrecorded — so the two sources are compared
# rather than trusted to stay in step by review.
#
# monitor_core imports `yaml`, which a bare system python3 need not have, so
# resolve the framework interpreter the same way tests/run_all_python_tests.sh
# does. The check SKIPS rather than fails if the import still cannot happen:
# this file's own contract is the argv and the id guard, and it must stay
# runnable on a machine without the venv.
# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
. "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
PYTHON_BIN="$(require_ait_python 2>/dev/null || echo python3)"

py_options="$("$PYTHON_BIN" -c "
import sys
sys.path.insert(0, '$PROJECT_DIR/.aitask-scripts')
sys.path.insert(0, '$PROJECT_DIR/.aitask-scripts/lib')
from monitor.monitor_core import (
    RECORD_OPTION, FROZEN_OPTION, STANDIN_READY_OPTION, AGENT_SESSION_OPTION,
)
print(RECORD_OPTION)
print(FROZEN_OPTION)
print(STANDIN_READY_OPTION)
print(AGENT_SESSION_OPTION)
" 2>/dev/null)"

if [ -z "$py_options" ]; then
    echo "SKIP: monitor_core is not importable with $PYTHON_BIN (missing deps)"
else
    { read -r py_record; read -r py_frozen; read -r py_ready; read -r py_session; } <<EOF
$py_options
EOF
    assert_eq "record option agrees with monitor_core"       "$AIT_RECORD_OPTION"         "$py_record"
    assert_eq "frozen option agrees with monitor_core"       "$AIT_FROZEN_OPTION"         "$py_frozen"
    assert_eq "standin-ready option agrees with monitor_core" "$AIT_STANDIN_READY_OPTION" "$py_ready"
    assert_eq "agent-session option agrees with monitor_core" "$AIT_AGENT_SESSION_OPTION" "$py_session"
fi

py_frozen_dir="$(python3 -c "
import sys; sys.path.insert(0, '$PROJECT_DIR/.aitask-scripts/lib')
import agent_sessions
print(agent_sessions.DEFAULT_FROZEN_DIR)
")"
assert_eq "python default frozen dir matches the shell default" "~/.config/aitasks/frozen" "$py_frozen_dir"

echo ""
echo "=== Summary ==="
echo "Passed: $PASS / $TOTAL"
[[ "$FAIL" -eq 0 ]] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED ($FAIL)"
[[ "$FAIL" -eq 0 ]]
