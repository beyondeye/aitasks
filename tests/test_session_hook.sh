#!/usr/bin/env bash
# test_session_hook.sh - the SessionStart hook's argv and exit contracts (t1705_3).
#
# NO LIVE TMUX SERVER and no code agent. The gateway resolves to `command tmux`,
# so a recording stub named `tmux` first on PATH makes the argv observable --
# the same technique as tests/test_agent_sessions_stamp.sh. The store wrapper is
# stubbed the same way, by building a scratch project root whose
# .aitask-scripts/aitask_agent_sessions.sh records its argv.
#
# The OBSERVING half -- is the pane option really set on a real pane after a
# real hook fire -- lives in tests/test_session_hook_live.sh, which owns a live
# (isolated) server.
#
# Run: bash tests/test_session_hook.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

HOOK="$PROJECT_DIR/.aitask-scripts/aitask_session_hook.sh"
FIXTURES="$PROJECT_DIR/tests/data/session_hooks"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/ait_session_hook_XXXXXX")"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Scratch project + stubs
# ---------------------------------------------------------------------------
ROOT="$(cd "$TMP" && pwd -P)/proj"
mkdir -p "$ROOT/aitasks/metadata" "$ROOT/.aitask-scripts/lib" "$TMP/bin"
: >"$ROOT/aitasks/metadata/project_config.yaml"
# Real gateway + constants: the hook must work against the shipped helpers.
cp "$PROJECT_DIR/.aitask-scripts/lib/tmux_exec.sh" \
   "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" \
   "$PROJECT_DIR/.aitask-scripts/lib/agent_sessions.sh" "$ROOT/.aitask-scripts/lib/"

# Recording tmux stub. Answers display-message from TMUX_STUB_DISPLAY.
cat >"$TMP/bin/tmux" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$@" >>"$TMUX_STUB_LOG"
for a in "$@"; do
  if [ "$a" = "display-message" ]; then
    printf '%s\n' "${TMUX_STUB_DISPLAY:-}"
    exit 0
  fi
done
exit 0
STUB
chmod +x "$TMP/bin/tmux"

# Recording store-wrapper stub. Writes argv NUL-delimited so an argument
# containing a space is distinguishable from two arguments.
cat >"$ROOT/.aitask-scripts/aitask_agent_sessions.sh" <<'STUB'
#!/usr/bin/env bash
n=0
if [ -f "$SESSIONS_STUB_COUNT" ]; then n="$(cat "$SESSIONS_STUB_COUNT")"; fi
n=$((n + 1))
printf '%s' "$n" >"$SESSIONS_STUB_COUNT"
printf '%s\0' "$@" >>"$SESSIONS_STUB_LOG"
printf '\36' >>"$SESSIONS_STUB_LOG"   # RS: end of one invocation
if [ "$n" -eq 1 ] && [ -n "${SESSIONS_STUB_RC1:-}" ]; then
    printf '%s\n' "${SESSIONS_STUB_OUT1:-LOCK_BUSY}"
    exit "$SESSIONS_STUB_RC1"
fi
printf '%s\n' "${SESSIONS_STUB_OUT:-UPSERTED:aabbccdd|created}"
exit "${SESSIONS_STUB_RC:-0}"
STUB
chmod +x "$ROOT/.aitask-scripts/aitask_agent_sessions.sh"

export PATH="$TMP/bin:$PATH"
export TMUX_STUB_LOG="$TMP/tmux.log"
export SESSIONS_STUB_LOG="$TMP/sessions.log"
export SESSIONS_STUB_COUNT="$TMP/sessions.count"
# Pin the gateway to the no-flag escape hatch so the stub argv is stable and
# the hook's $TMUX-derived socket logic does not vary the recorded arguments.
export AITASKS_TMUX_SOCKET=""

DISPLAY_LINE=$'aitasks\tagent-pick-1705_3\t%7\t4242\t'

# run_hook <payload-json> [env assignments...]
# Resets the logs, runs the hook, captures stdout/stderr/exit separately.
HOOK_OUT=""; HOOK_ERR=""; HOOK_RC=0
run_hook() {
    local payload="$1"; shift
    : >"$TMUX_STUB_LOG"; : >"$SESSIONS_STUB_LOG"; rm -f "$SESSIONS_STUB_COUNT"
    HOOK_OUT="$(printf '%s' "$payload" | env "$@" \
        TMUX_PANE="%7" TMUX= AITASK_AGENT_STRING="claudecode/opus5" \
        bash "$HOOK" 2>"$TMP/stderr")"
    HOOK_RC=$?
    HOOK_ERR="$(cat "$TMP/stderr")"
}

# argv_of <n> — the n-th invocation's argv, one argument per line.
argv_of() {
    python3 - "$SESSIONS_STUB_LOG" "$1" <<'PY'
import sys
raw = open(sys.argv[1], 'rb').read()
calls = [c for c in raw.split(b'\x1e') if c]
i = int(sys.argv[2]) - 1
if i >= len(calls):
    raise SystemExit(0)
args = [a.decode() for a in calls[i].split(b'\x00') if a != b'']
print('\n'.join(args))
PY
}

# arg_value <n> <flag> — the value following <flag> in invocation <n>.
arg_value() {
    argv_of "$1" | awk -v f="$2" 'p{print;exit} $0==f{p=1}'
}

# tmux_option_set <option> — did a set-option actually write <option>?
# Matches the option as a WHOLE argv line: the display-message format string
# also contains "#{@aitask_record}", so a substring grep would always match.
tmux_option_set() {
    grep -qx -- "$1" "$TMUX_STUB_LOG"
}

# tmux_option_value <option> — the value set-option wrote for <option>.
tmux_option_value() {
    awk -v o="$1" 'p{print;exit} $0==o{p=1}' "$TMUX_STUB_LOG"
}

call_count() {
    python3 -c "
import sys
raw=open('$SESSIONS_STUB_LOG','rb').read()
print(len([c for c in raw.split(b'\x1e') if c]))"
}

payload() {
    python3 -c "
import json,sys
print(json.dumps(json.loads(sys.argv[1])))" "$1"
}

echo "=== SessionStart hook contracts (t1705_3) ==="

# ---------------------------------------------------------------------------
echo "--- Baseline: a plain start ---"
export TMUX_STUB_DISPLAY="$DISPLAY_LINE"
run_hook '{"session_id":"sid-1","transcript_path":"/t/a.jsonl","cwd":"'"$ROOT"'","source":"startup"}'

assert_eq "exit 0 on the happy path" "0" "$HOOK_RC"
assert_eq "stdout is empty (SessionStart injects stdout into context)" "" "$HOOK_OUT"
assert_eq "one upsert call" "1" "$(call_count)"
assert_eq "verb is upsert" "upsert" "$(argv_of 1 | head -1)"
assert_eq "--root is the resolved project root" "$ROOT" "$(arg_value 1 --root)"
assert_eq "--window from display-message" "agent-pick-1705_3" "$(arg_value 1 --window)"
assert_eq "--pane from display-message" "%7" "$(arg_value 1 --pane)"
assert_eq "--pane-pid from display-message" "4242" "$(arg_value 1 --pane-pid)"
assert_eq "--session-id from the payload" "sid-1" "$(arg_value 1 --session-id)"
assert_eq "--transcript from the payload" "/t/a.jsonl" "$(arg_value 1 --transcript)"
assert_eq "--agent-string from the environment" "claudecode/opus5" "$(arg_value 1 --agent-string)"
assert_eq "--operation parsed from the window name" "pick" "$(arg_value 1 --operation)"
assert_eq "--task-id parsed from the window name" "1705_3" "$(arg_value 1 --task-id)"

# C5: --session (A6) is captured from tmux and must be passed on.
assert_eq "C5: --session carries the tmux session name" "aitasks" "$(arg_value 1 --session)"

# No @aitask_record on the pane => no --id.
assert_eq "no --id when the pane carries no record" "" "$(argv_of 1 | grep -c '^--id$' | tr -d ' ' | sed 's/^0$//')"

# A8: the stamp fires on success, with the upserted id.
assert_eq "A8: pane is stamped with @aitask_record" "aabbccdd" "$(tmux_option_value @aitask_record)"
assert_eq "pane option @aitask_agent_session carries the session id" "sid-1" "$(tmux_option_value @aitask_agent_session)"

# ---------------------------------------------------------------------------
echo "--- C1: the stamp fires only on a success LINE ---"
# The store wrapper merges python's stdout and stderr, so a warning can precede
# the UPSERTED: line. A prefix test would miss the stamp; a line match must not.
export SESSIONS_STUB_OUT=$'warning: something chatty\nUPSERTED:12ab34cd|created'
run_hook '{"session_id":"sid-2","transcript_path":"/t/b.jsonl","cwd":"'"$ROOT"'","source":"startup"}'
assert_eq "C1: exit 0 with a noisy store" "0" "$HOOK_RC"
assert_eq "C1: stamped despite a warning line before UPSERTED:" "12ab34cd" "$(tmux_option_value @aitask_record)"

echo "--- C1: no stamp on a refusal ---"
export SESSIONS_STUB_OUT="UPSERT_REFUSED:12ab34cd|frozen"
export SESSIONS_STUB_RC=5
run_hook '{"session_id":"sid-3","transcript_path":"/t/c.jsonl","cwd":"'"$ROOT"'","source":"startup"}'
assert_eq "C1: exit 0 on a refusal" "0" "$HOOK_RC"
if tmux_option_set @aitask_record; then
    assert_eq "C1: NO @aitask_record stamp on UPSERT_REFUSED" "no stamp" "stamped"
else
    assert_eq "C1: NO @aitask_record stamp on UPSERT_REFUSED" "no stamp" "no stamp"
fi
assert_contains "C1: the refusal is reported on stderr" "UPSERT_REFUSED" "$HOOK_ERR"
unset SESSIONS_STUB_RC
export SESSIONS_STUB_OUT="UPSERTED:aabbccdd|created"

# ---------------------------------------------------------------------------
echo "--- C2: paths containing spaces ---"
SPACED="$(cd "$TMP" && pwd -P)/My Project"
mkdir -p "$SPACED/aitasks/metadata" "$SPACED/.aitask-scripts/lib"
: >"$SPACED/aitasks/metadata/project_config.yaml"
cp "$ROOT/.aitask-scripts/lib/"*.sh "$SPACED/.aitask-scripts/lib/"
cp "$ROOT/.aitask-scripts/aitask_agent_sessions.sh" "$SPACED/.aitask-scripts/"
run_hook '{"session_id":"sid-sp","transcript_path":"/t/my transcript.jsonl","cwd":"'"$SPACED"'","source":"startup"}'
assert_eq "C2: exit 0 with spaces in paths" "0" "$HOOK_RC"
assert_eq "C2: --root survives as ONE argument" "$SPACED" "$(arg_value 1 --root)"
assert_eq "C2: --transcript survives as ONE argument" "/t/my transcript.jsonl" "$(arg_value 1 --transcript)"
assert_eq "C2: --session-id is not shifted by the spaces" "sid-sp" "$(arg_value 1 --session-id)"

echo "--- C2: quotes and dollars in paths ---"
run_hook '{"session_id":"sid-q","transcript_path":"/t/a$b '"'"'c.jsonl","cwd":"'"$ROOT"'","source":"startup"}'
assert_eq "C2: exit 0 with \$ and ' in the transcript path" "0" "$HOOK_RC"
assert_eq "C2: metacharacters are not expanded" "/t/a\$b 'c.jsonl" "$(arg_value 1 --transcript)"

# ---------------------------------------------------------------------------
echo "--- C3: a blank session id records NOTHING ---"
for case_name in empty absent null; do
    case "$case_name" in
        empty)  pl='{"session_id":"","transcript_path":"/t/d.jsonl","cwd":"'"$ROOT"'","source":"startup"}' ;;
        absent) pl='{"transcript_path":"/t/d.jsonl","cwd":"'"$ROOT"'","source":"startup"}' ;;
        null)   pl='{"session_id":null,"transcript_path":"/t/d.jsonl","cwd":"'"$ROOT"'","source":"startup"}' ;;
    esac
    run_hook "$pl"
    assert_eq "C3($case_name): exit 0" "0" "$HOOK_RC"
    assert_eq "C3($case_name): NO upsert call" "0" "$(call_count)"
    assert_eq "C3($case_name): stdout stays empty" "" "$HOOK_OUT"
    if tmux_option_set @aitask_agent_session; then
        assert_eq "C3($case_name): pane option NOT written" "unset" "written"
    else
        assert_eq "C3($case_name): pane option NOT written" "unset" "unset"
    fi
    assert_contains "C3($case_name): reported on stderr" "empty session_id" "$HOOK_ERR"
done

# ---------------------------------------------------------------------------
echo "--- @aitask_record present => --id ---"
export TMUX_STUB_DISPLAY=$'aitasks\tagent-pick-1705_3\t%7\t4242\tdeadbeef'
run_hook '{"session_id":"sid-4","transcript_path":"/t/e.jsonl","cwd":"'"$ROOT"'","source":"resume"}'
assert_eq "--id forwarded from @aitask_record" "deadbeef" "$(arg_value 1 --id)"
export TMUX_STUB_DISPLAY="$DISPLAY_LINE"

# ---------------------------------------------------------------------------
echo "--- restore environment => --restore-of / --nonce ---"
run_hook '{"session_id":"sid-5","transcript_path":"/t/f.jsonl","cwd":"'"$ROOT"'","source":"resume"}' \
    AITASK_RESTORE_RECORD=1122aabb AITASK_RESTORE_NONCE=99887766 AITASK_RESTORE_MODE=resume
assert_eq "--restore-of from the environment" "1122aabb" "$(arg_value 1 --restore-of)"
assert_eq "--nonce from the environment" "99887766" "$(arg_value 1 --nonce)"

# ---------------------------------------------------------------------------
echo "--- LOCK_BUSY (rc 3) is retried exactly once ---"
export SESSIONS_STUB_RC1=3
export SESSIONS_STUB_OUT1="LOCK_BUSY"
run_hook '{"session_id":"sid-6","transcript_path":"/t/g.jsonl","cwd":"'"$ROOT"'","source":"startup"}'
assert_eq "LOCK_BUSY: exit 0" "0" "$HOOK_RC"
assert_eq "LOCK_BUSY: exactly two calls" "2" "$(call_count)"
unset SESSIONS_STUB_RC1 SESSIONS_STUB_OUT1

echo "--- a persistent LOCK_BUSY gives up after the retry ---"
export SESSIONS_STUB_RC=3
export SESSIONS_STUB_OUT="LOCK_BUSY"
run_hook '{"session_id":"sid-7","transcript_path":"/t/h.jsonl","cwd":"'"$ROOT"'","source":"startup"}'
assert_eq "persistent LOCK_BUSY: exit 0" "0" "$HOOK_RC"
assert_eq "persistent LOCK_BUSY: two calls, no more" "2" "$(call_count)"
unset SESSIONS_STUB_RC
export SESSIONS_STUB_OUT="UPSERTED:aabbccdd|created"

# ---------------------------------------------------------------------------
echo "--- degenerate inputs all exit 0 and record nothing ---"
run_hook 'not json at all'
assert_eq "malformed JSON: exit 0" "0" "$HOOK_RC"
assert_eq "malformed JSON: no upsert" "0" "$(call_count)"
assert_eq "malformed JSON: stdout empty" "" "$HOOK_OUT"

run_hook '[1,2,3]'
assert_eq "non-object payload: exit 0" "0" "$HOOK_RC"
assert_eq "non-object payload: no upsert" "0" "$(call_count)"

run_hook '{"session_id":"sid-8","cwd":"/definitely/not/an/aitasks/project","source":"startup"}'
assert_eq "cwd outside any aitasks project: exit 0" "0" "$HOOK_RC"
assert_eq "cwd outside any aitasks project: no upsert" "0" "$(call_count)"

echo "--- no \$TMUX_PANE => the hook does nothing at all ---"
: >"$TMUX_STUB_LOG"; : >"$SESSIONS_STUB_LOG"; rm -f "$SESSIONS_STUB_COUNT"
out="$(printf '%s' '{"session_id":"sid-9","cwd":"'"$ROOT"'","source":"startup"}' \
    | env -u TMUX_PANE TMUX= bash "$HOOK" 2>&1)"
rc=$?
assert_eq "no TMUX_PANE: exit 0" "0" "$rc"
assert_eq "no TMUX_PANE: no output at all" "" "$out"
assert_eq "no TMUX_PANE: no upsert" "0" "$(call_count)"
assert_eq "no TMUX_PANE: no tmux call" "" "$(cat "$TMUX_STUB_LOG")"

# ---------------------------------------------------------------------------
echo "--- the committed fixtures are consumed, branching on _fixture_status ---"
for agent in claude codex; do
    fx="$FIXTURES/${agent}_sessionstart.json"
    [ -f "$fx" ] || { echo "  SKIP: $fx missing"; continue; }
    status="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('_fixture_status',''))" "$fx")"
    # Re-root the fixture at the scratch project: its cwd is redacted.
    pl="$(python3 -c "
import json,sys
d=json.load(open(sys.argv[1])); d['cwd']=sys.argv[2]
print(json.dumps(d))" "$fx" "$ROOT")"
    run_hook "$pl"
    case "$status" in
        captured)
            assert_eq "fixture $agent (captured): exit 0" "0" "$HOOK_RC"
            assert_eq "fixture $agent (captured): one upsert" "1" "$(call_count)"
            sid="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['session_id'])" "$fx")"
            assert_eq "fixture $agent (captured): session id forwarded" "$sid" "$(arg_value 1 --session-id)"
            ;;
        provisional)
            # ADVISORY ONLY -- the codex shape is not settled for the
            # interactive path. Assert the invariant that holds regardless.
            assert_eq "fixture $agent (provisional, advisory): exit 0" "0" "$HOOK_RC"
            assert_eq "fixture $agent (provisional, advisory): stdout empty" "" "$HOOK_OUT"
            echo "  NOTE: $agent fixture is provisional — argv assertions are advisory, not pinned."
            ;;
        unsupported)
            echo "  SKIP (explicit): $agent declares no SessionStart support; no upsert expected."
            assert_eq "fixture $agent (unsupported): no upsert" "0" "$(call_count)"
            ;;
        *)
            assert_eq "fixture $agent has a known _fixture_status" "known" "unknown:$status"
            ;;
    esac
done

echo ""
echo "========================================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
echo "========================================="
[[ "$FAIL" -eq 0 ]] || exit 1
echo "ALL TESTS PASSED"
