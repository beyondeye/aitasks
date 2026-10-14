#!/usr/bin/env bash
# tests/test_linked_trail_jump_live.sh — the linked-trail jump against REAL tmux
# (t1957_4, risk mitigation live_jump_bootstrap_path).
#
# WHAT IS UNDER TEST. `board_trail_screen.prepare_linked_trail_jump` and
# `finish_linked_trail_jump`, unmodified, on an isolated tmux server. The unit
# suite (tests/test_linked_trail_jump.py) stubs the gateway, so it cannot see the
# seams that only real tmux has:
#
#   * the session `tmux_bootstrap.sh` starts must be the one
#     `live_project_session` then finds by root (the registration stamp vs the
#     realpath compare, the configured name);
#   * the cold launch must put a `trails` window running
#     `./ait trails --trail <h>` in THAT session;
#   * a second jump must reuse the session, not start a duplicate;
#   * a target on an older framework gets no window but is still switched to;
#   * finish must refuse a session whose name now belongs to another project.
#
# Only two names are replaced, in the driver: `current_tmux_session` (the
# driver is not a pane of the server) and `switch_client_to` (headless tmux has
# no client to switch). Both record what they were asked.
#
# ISOLATION. `require_isolated_tmux`, plus our own TMUX_TMPDIR so every
# `kill-server` is scoped to this run; AITASKS_PROJECTS_INDEX keeps the
# bootstrap's registry write in the fixture; AIT_NO_SYSTEMD_RUN keeps the server
# out of a user unit; a stub `ait` keeps the seeded windows (and the launched
# `trails`) alive without booting TUIs.
#
# Run: bash tests/test_linked_trail_jump_live.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

command -v tmux >/dev/null 2>&1 || { echo "SKIP: tmux not available"; exit 0; }

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# Cases run inside ( … ) subshells; without the file-backed counters their
# PASS/FAIL increments die at subshell exit (CLAUDE.md, t1207).
assert_counters_init

# shellcheck source=lib/tmux_isolation.sh
. "$PROJECT_DIR/tests/lib/tmux_isolation.sh"
require_isolated_tmux

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
. "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
PYTHON_BIN="$(require_ait_python)"

# Both read by tests/lib/frozen_fixtures.sh (`tm`, `cleanup`).
# shellcheck disable=SC2034
REAL_TMUX="$(command -v tmux)"
# shellcheck disable=SC2034
REAL_PATH="$PATH"
# `pwd -P`: the scan and the session lookup realpath every root.
FIXTURE_DIR="$(cd "$(mktemp -d "${TMPDIR:-/tmp}/ait_jump_live_XXXXXX")" && pwd -P)"
export TMUX_TMPDIR="$FIXTURE_DIR"

# shellcheck source=lib/frozen_fixtures.sh
. "$PROJECT_DIR/tests/lib/frozen_fixtures.sh"
trap cleanup EXIT

export AITASKS_PROJECTS_INDEX="$FIXTURE_DIR/projects.yaml"
export AIT_NO_SYSTEMD_RUN=1

HANDLE="art:trail-y"
Y_SESS="ait_jump_y_$$"
OLD_SESS="ait_jump_old_$$"
OTHER="other_$$"
PROJ_X="$FIXTURE_DIR/proj_x"        # the caller: the driver's cwd
PROJ_Y="$FIXTURE_DIR/proj_y"        # target, current framework
PROJ_OLD="$FIXTURE_DIR/proj_old"    # target, older framework (no --trail)
PROJ_Z="$FIXTURE_DIR/proj_z"        # takes Y's session name in case D
OUTSIDE="$FIXTURE_DIR/outside"

make_project() {   # make_project <root> <default_session> <trails_app body>
    mkdir -p "$1/aitasks/metadata" "$1/.aitask-scripts/board"
    printf 'tmux:\n  default_session: %s\n' "$2" \
        > "$1/aitasks/metadata/project_config.yaml"
    printf '%s\n' "$3" > "$1/.aitask-scripts/board/trails_app.py"
    # The project's own `./ait`, which the cold launch runs: record the argv,
    # stay alive so the window can be inspected.
    cat > "$1/ait" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$PWD/ait_argv.log"
exec sleep 1000
STUB
    chmod +x "$1/ait"
}

mkdir -p "$PROJ_X" "$OUTSIDE" "$FIXTURE_DIR/bin"
make_project "$PROJ_Y" "$Y_SESS" 'parser.add_argument("--trail")'
make_project "$PROJ_OLD" "$OLD_SESS" 'parser.add_argument("--tasks-dir")'
make_project "$PROJ_Z" "unused_$$" 'parser.add_argument("--trail")'

# The bootstrap seeds `ait monitor` (and maybe `ait syncer`) from PATH.
cat > "$FIXTURE_DIR/bin/ait" <<'STUB'
#!/usr/bin/env bash
case "${1:-}" in monitor|syncer) exec sleep 1000 ;; esac
echo "stub ait: unexpected: $*" >&2
exit 1
STUB
chmod +x "$FIXTURE_DIR/bin/ait"
# Exported BEFORE any server starts: the seeded windows run in its environment.
export PATH="$FIXTURE_DIR/bin:$PATH"

# --- helpers -----------------------------------------------------------------

fresh_server() {   # a server holding ONLY an unrelated session
    tm kill-server 2>/dev/null || true
    sleep 0.3
    tm new-session -d -s "$OTHER" -n base -c "$OUTSIDE" "sleep 1000"
    sleep 0.3
}

stamp()   { tm list-sessions -F "#{session_name}	#{@aitask_project_root}" 2>/dev/null | sed -n "s|^$1	||p"; }
windows() { tm list-windows -t "=$1" -F '#{window_name}' 2>/dev/null | paste -sd ' ' -; }
session_count() { tm list-sessions 2>/dev/null | wc -l | tr -d ' '; }

wait_for_file() {   # wait_for_file <path>: up to 5 s
    local tries=50
    while [ "$tries" -gt 0 ]; do
        [ -s "$1" ] && return 0
        sleep 0.1
        tries=$((tries - 1))
    done
    return 1
}

# The driver: prepare, optionally run a shell command, then finish. Prints
# `key=value` lines; list values are joined with " || ".
DRIVER="$FIXTURE_DIR/driver.py"
cat > "$DRIVER" <<'PYEOF'
import subprocess
import sys
from types import SimpleNamespace

repo, root, handle, between = sys.argv[1:5]
sys.path[:0] = [repo + "/.aitask-scripts/board", repo + "/.aitask-scripts/lib"]
import board_trail_screen as ts

switched = []
ts.current_tmux_session = lambda: "caller"
ts.switch_client_to = lambda session: switched.append(session) or True

link = SimpleNamespace(project="proj", root=root, handle=handle, name="Y",
                       reasons=())
jump = ts.prepare_linked_trail_jump(link)
notices = []
if not jump.error:
    if between:
        subprocess.run(["bash", "-c", between], check=True)
    notices = [message for message, _ in ts.finish_linked_trail_jump(jump)]
print(f"error={jump.error}")
print(f"session={jump.session}")
print(f"launch={jump.launch}")
print("warnings=" + " || ".join(jump.warnings))
print("notices=" + " || ".join(notices))
print("switched=" + " || ".join(switched))
PYEOF

drive() {   # drive <root> [<shell command between prepare and finish>]
    (cd "$PROJ_X" && "$PYTHON_BIN" "$DRIVER" "$PROJECT_DIR" "$1" "$HANDLE" "${2:-}")
}
field() { sed -n "s/^$1=//p" <<<"$2"; }

# ---------------------------------------------------------------------------
section "A — no session for the target: started, found by root, launched"
# ---------------------------------------------------------------------------
(
    fresh_server
    out="$(drive "$PROJ_Y")"

    assert_eq "A: no error" "" "$(field error "$out")"
    assert_eq "A: no warnings" "" "$(field warnings "$out")"
    assert_eq "A: prepare found the session the bootstrap started" \
        "$Y_SESS" "$(field session "$out")"
    assert_eq "A: that session is stamped with the target's root" \
        "$PROJ_Y" "$(stamp "$Y_SESS")"
    assert_eq "A: finish returned no notice" "" "$(field notices "$out")"
    assert_eq "A: the client was switched to it" "$Y_SESS" "$(field switched "$out")"
    wait_for_file "$PROJ_Y/ait_argv.log"
    assert_eq "A: the target's ./ait got the trail" \
        "trails --trail $HANDLE" "$(head -n1 "$PROJ_Y/ait_argv.log" 2>/dev/null)"
    assert_contains "A: in a trails window of that session" \
        "trails" "$(windows "$Y_SESS")"
)

# ---------------------------------------------------------------------------
section "B — a second jump reuses the session"
# ---------------------------------------------------------------------------
(
    before="$(session_count)"
    out="$(drive "$PROJ_Y")"

    assert_eq "B: no error" "" "$(field error "$out")"
    assert_eq "B: the same session" "$Y_SESS" "$(field session "$out")"
    assert_eq "B: no second session was started" "$before" "$(session_count)"
    assert_eq "B: switched to the same session" "$Y_SESS" "$(field switched "$out")"
)

# ---------------------------------------------------------------------------
section "C — CONTROL: an older target gets no window, but is switched to"
# ---------------------------------------------------------------------------
# Proves A's window assertion can fail: the same path with launch disabled.
(
    out="$(drive "$PROJ_OLD")"

    assert_eq "C: no error" "" "$(field error "$out")"
    assert_eq "C: the session was started" "$OLD_SESS" "$(field session "$out")"
    assert_eq "C: launch is off" "False" "$(field launch "$out")"
    assert_contains "C: the user is told to upgrade" "ait upgrade" \
        "$(field warnings "$out")"
    assert_not_contains "C: no trails window" "trails" "$(windows "$OLD_SESS")"
    assert_file_not_exists "C: its ./ait never ran" "$PROJ_OLD/ait_argv.log"
    assert_eq "C: still switched" "$OLD_SESS" "$(field switched "$out")"
)

# ---------------------------------------------------------------------------
section "D — the session's name is taken by another project before finish"
# ---------------------------------------------------------------------------
(
    rm -f "$PROJ_Y/ait_argv.log"
    # `set-option -t` resolves a WINDOW-typed target: a bare `=<s>` is "no such
    # session", the trailing colon makes it the session (as the bootstrap does).
    between="set -e
tmux kill-session -t '=$Y_SESS'
tmux new-session -d -s '$Y_SESS' -n base -c '$PROJ_Z' 'sleep 1000'
tmux set-option -t '=$Y_SESS:' @aitask_project_root '$PROJ_Z'"
    out="$(drive "$PROJ_Y" "$between")"

    assert_eq "D: prepare saw Y's live session" "$Y_SESS" "$(field session "$out")"
    assert_eq "D: premise — the name now belongs to Z" "$PROJ_Z" "$(stamp "$Y_SESS")"
    assert_contains "D: finish refused" "changed before the jump" \
        "$(field notices "$out")"
    assert_eq "D: the client was not switched" "" "$(field switched "$out")"
    assert_not_contains "D: Z's session got no trails window" \
        "trails" "$(windows "$Y_SESS")"
    assert_file_not_exists "D: nothing was launched" "$PROJ_Y/ait_argv.log"
)

# ===========================================================================
section "Summary"
# ===========================================================================
assert_counters_load
echo "Passed: $PASS / $TOTAL"
if [ "$FAIL" -eq 0 ]; then
    echo "ALL TESTS PASSED"
    exit 0
fi
echo "FAILED: $FAIL"
exit 1
