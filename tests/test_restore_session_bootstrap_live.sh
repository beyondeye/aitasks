#!/usr/bin/env bash
# tests/test_restore_session_bootstrap_live.sh — the REAL-tmux contract for
# restoring a frozen agent whose project has NO tmux session (t1784).
#
# WHAT IS UNDER TEST. `agent_restore._launch_into_new_window` used to fail
# `no_session_for_root` whenever no tmux session was attributed to the record's
# project — the ordinary state after a tmux server restart. It now creates the
# project's OWN session through `lib/tmux_bootstrap.sh --create-only`, the same
# bootstrap `ait ide` and the TUI switcher use.
#
# THE HAZARD THIS FILE EXISTS FOR. The bootstrap's DEFAULT mode is "ensure", not
# "create": when the configured session name already exists it leaves the
# session alone but still writes `AITASKS_PROJECT_<session>` and a syncer window
# into it. `discover_aitasks_sessions()` falls back to that registry entry when
# no pane cwd names a project, so restoring project B into a name held by
# project A would re-point A's session at B and then launch B's agent inside it.
# `--create-only` must therefore either CREATE the session or change NOTHING.
#
#   Part A  the `--create-only` contract, driving tmux_bootstrap.sh directly.
#           A0 is a CONTROL: it proves the "nothing changed" detectors of A2-A4
#           can actually see a clobber, so they cannot pass vacuously.
#   Part B  `_launch_into_new_window` end to end: created, refused, no server.
#
# ISOLATION. `require_isolated_tmux` only: it unsets $TMUX/$TMUX_PANE, repoints
# TMUX_TMPDIR, and pins AITASKS_TMUX_SOCKET="" so the gateway (Python AND
# lib/tmux_exec.sh) stays on this run's own socket. Every `kill-server` here is
# scoped to it, so the suite is safe to run from inside tmux. Three more exports
# keep the bootstrap's side effects inside the fixture: the per-user project
# registry (AITASKS_PROJECTS_INDEX), systemd (AIT_NO_SYSTEMD_RUN — a server the
# bootstrap creates must not hop into a user unit, which would not inherit
# TMUX_TMPDIR), and `ait` itself (a stub, so the seeded `monitor` / `syncer`
# windows stay up without booting TUIs).
#
# Run: bash tests/test_restore_session_bootstrap_live.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

command -v tmux >/dev/null 2>&1 || { echo "SKIP: tmux not available"; exit 0; }

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# Cases run inside ( … ) subshells; without the file-backed counters their
# PASS/FAIL increments die at subshell exit and this file exits 0 whatever
# happened (CLAUDE.md, t1207).
assert_counters_init

# shellcheck source=lib/tmux_isolation.sh
. "$PROJECT_DIR/tests/lib/tmux_isolation.sh"
require_isolated_tmux

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
. "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
PYTHON_BIN="$(require_ait_python)"

REAL_TMUX="$(command -v tmux)"
REAL_PATH="$PATH"
# `pwd -P`: discovery realpaths every root, and $TMPDIR is a symlink on macOS.
FIXTURE_DIR="$(cd "$(mktemp -d "${TMPDIR:-/tmp}/ait_boot_live_XXXXXX")" && pwd -P)"
# Our OWN socket dir, so every `kill-server` below is scoped to this run.
export TMUX_TMPDIR="$FIXTURE_DIR"

# shellcheck source=lib/frozen_fixtures.sh
. "$PROJECT_DIR/tests/lib/frozen_fixtures.sh"
# `cleanup` (frozen_fixtures.sh) kills the isolated server and removes the tree.
trap cleanup EXIT

BOOT="$PROJECT_DIR/.aitask-scripts/lib/tmux_bootstrap.sh"
NAME="ait_boot_$$"          # the session name A and B BOTH configure
OTHER="other_$$"            # an unrelated session in a non-project dir
PROJ_A="$FIXTURE_DIR/proj_a"
PROJ_B="$FIXTURE_DIR/proj_b"
OUTSIDE="$FIXTURE_DIR/outside"
MARK="sleep 4242"           # B's "agent", findable anywhere on the server

export AITASKS_PROJECTS_INDEX="$FIXTURE_DIR/projects.yaml"
export AIT_NO_SYSTEMD_RUN=1

mkdir -p "$PROJ_A/aitasks/metadata" "$PROJ_B/aitasks/metadata" "$OUTSIDE" "$FIXTURE_DIR/bin"
printf 'tmux:\n  default_session: %s\n' "$NAME" \
    > "$PROJ_A/aitasks/metadata/project_config.yaml"
# B turns syncer autostart ON, so a clobber of A's session is visible as an
# extra `syncer` window — not only as a changed registry entry.
printf 'tmux:\n  default_session: %s\n  syncer:\n    autostart: true\n' "$NAME" \
    > "$PROJ_B/aitasks/metadata/project_config.yaml"

cat > "$FIXTURE_DIR/bin/ait" <<'STUB'
#!/usr/bin/env bash
# The bootstrap seeds `ait monitor` and, with autostart, `ait syncer`. Booting
# the real TUIs would be slow and would act on state, and a window that dies at
# once would take a one-window session with it. Sleeping keeps both observable.
case "${1:-}" in monitor|syncer) exec sleep 1000 ;; esac
echo "stub ait: unexpected: $*" >&2
exit 1
STUB
chmod +x "$FIXTURE_DIR/bin/ait"
# Exported BEFORE any server starts: a server's global environment is captured
# at start, and the seeded windows run in it.
export PATH="$FIXTURE_DIR/bin:$PATH"

# --- helpers -----------------------------------------------------------------

fresh_server_with() {   # fresh_server_with <session> <cwd>: a server holding ONLY that session
    tm kill-server 2>/dev/null || true
    sleep 0.3
    tm new-session -d -s "$1" -n base -c "$2" "sleep 1000"
    sleep 0.3
}

no_server() { tm kill-server 2>/dev/null || true; sleep 0.3; }

# Session $NAME held by project A, in the two shapes discovery attributes
# differently:
#   outside — its pane sits in a NON-project dir and ONLY the global registry
#             entry names A. The dangerous shape: a clobbered entry re-points it.
#   inside  — its pane sits in project A, and there is no registry entry.
collision_fixture() {
    if [ "$1" = outside ]; then
        fresh_server_with "$NAME" "$OUTSIDE"
        tm set-environment -g "AITASKS_PROJECT_$NAME" "$PROJ_A"
    else
        fresh_server_with "$NAME" "$PROJ_A"
    fi
    rm -f "$AITASKS_PROJECTS_INDEX"
}

registry() { tm show-environment -g "AITASKS_PROJECT_$1" 2>/dev/null | sed -n "s|^AITASKS_PROJECT_$1=||p"; }
windows()  { tm list-windows -t "=$1" -F '#{window_name}' 2>/dev/null | paste -sd ' ' -; }
index_written() { [ -f "$AITASKS_PROJECTS_INDEX" ] && echo yes || echo no; }

# Everything a clobber could change, as one comparable string.
snapshot() {
    tm list-panes -s -t "=$1" -F '#{window_name}|#{pane_id}|#{pane_current_path}' 2>/dev/null
    echo "registry=$(registry "$1")"
}

boot() {   # boot [--create-only] <root>  ->  BOOT_RC / BOOT_OUT / BOOT_ERR
    BOOT_OUT="$(bash "$BOOT" "$@" 2>"$FIXTURE_DIR/boot.err")"
    BOOT_RC=$?
    BOOT_ERR="$(cat "$FIXTURE_DIR/boot.err")"
}

marked_panes() { tm list-panes -a -F '#{pane_start_command}' 2>/dev/null | grep -c "4242" || true; }

# The Part B driver: one `_launch_into_new_window` call, printing
# `pane|pid|error`. `error` may itself contain `|`; `read` gives the LAST
# variable the rest of the line, so it survives intact.
DRIVER="$FIXTURE_DIR/driver.py"
cat > "$DRIVER" <<'PYEOF'
import sys
sys.path.insert(0, sys.argv[1] + "/.aitask-scripts")
sys.path.insert(0, sys.argv[1] + "/.aitask-scripts/lib")
import agent_restore

root, window, command = sys.argv[2], sys.argv[3], sys.argv[4]
pane, pid, err = agent_restore._launch_into_new_window(
    {"root": root, "window": window}, command,
    {"AITASK_RESTORE_RECORD": "bootlive1"})
print(f"{pane}|{pid}|{err}")
PYEOF

bdrive() { "$PYTHON_BIN" "$DRIVER" "$PROJECT_DIR" "$@"; }

# ===========================================================================
section "Part A — the --create-only contract (tmux_bootstrap.sh)"
# ===========================================================================

# ---------------------------------------------------------------------------
section "A1 — no session: create-only creates it and says so"
# ---------------------------------------------------------------------------
(
    fresh_server_with "$OTHER" "$OUTSIDE"
    rm -f "$AITASKS_PROJECTS_INDEX"
    boot --create-only "$PROJ_B"

    assert_eq "A1: exit 0" "0" "$BOOT_RC"
    assert_contains "A1: it reports the session it created" \
        "BOOTSTRAP_CREATED:$NAME" "$BOOT_OUT"
    assert_contains "A1: the new session is seeded with a monitor window" \
        "monitor" "$(windows "$NAME")"
    assert_eq "A1: and registered to the project it was created for" \
        "$PROJ_B" "$(registry "$NAME")"
    assert_contains "A1: B's syncer autostart applies to its OWN new session" \
        "syncer" "$(windows "$NAME")"
    assert_contains "A1: the per-user index was written (redirected)" \
        "$PROJ_B" "$(cat "$AITASKS_PROJECTS_INDEX" 2>/dev/null)"
    assert_eq "A1: the unrelated session was not touched" "base" "$(windows "$OTHER")"
)

# ---------------------------------------------------------------------------
section "A0 — CONTROL: the default mode DOES clobber a foreign session"
# ---------------------------------------------------------------------------
# Why this case is permanent. A2-A4 assert "nothing changed", and a detector
# that cannot see a change passes them vacuously. This drives the SAME fixture
# through the default ("ensure") mode — which `ait ide` keeps on purpose — and
# requires the clobber to be visible. That proves the detectors work, and shows
# that the flag, not the fixture, is what prevents the clobber.
(
    collision_fixture outside
    boot "$PROJ_B"

    assert_eq "A0: the default mode exits 0 on an existing session" "0" "$BOOT_RC"
    assert_eq "A0: it RE-POINTS the foreign session's registry entry at B" \
        "$PROJ_B" "$(registry "$NAME")"
    assert_contains "A0: and adds B's syncer window to A's session" \
        "syncer" "$(windows "$NAME")"
)

# ---------------------------------------------------------------------------
section "A2 — collision, panes OUTSIDE project dirs: left untouched"
# ---------------------------------------------------------------------------
(
    collision_fixture outside
    before="$(snapshot "$NAME")"
    boot --create-only "$PROJ_B"

    assert_eq "A2: exit 43" "43" "$BOOT_RC"
    assert_contains "A2: the structured refusal names the session" \
        "BOOTSTRAP_FAILED:session_exists:$NAME" "$BOOT_ERR"
    assert_not_contains "A2: nothing claims a creation" "BOOTSTRAP_CREATED" "$BOOT_OUT"
    assert_eq "A2: the registry entry still names A" "$PROJ_A" "$(registry "$NAME")"
    assert_eq "A2: windows, panes and registry are identical" \
        "$before" "$(snapshot "$NAME")"
    assert_not_contains "A2: no syncer window was added" "syncer" "$(windows "$NAME")"
    assert_eq "A2: the per-user index was not written" "no" "$(index_written)"
)

# ---------------------------------------------------------------------------
section "A3 — collision, panes INSIDE project A: left untouched"
# ---------------------------------------------------------------------------
(
    collision_fixture inside
    before="$(snapshot "$NAME")"
    boot --create-only "$PROJ_B"

    assert_eq "A3: exit 43" "43" "$BOOT_RC"
    assert_contains "A3: the structured refusal names the session" \
        "BOOTSTRAP_FAILED:session_exists:$NAME" "$BOOT_ERR"
    assert_eq "A3: no registry entry was created" "" "$(registry "$NAME")"
    assert_eq "A3: windows, panes and registry are identical" \
        "$before" "$(snapshot "$NAME")"
    assert_not_contains "A3: no syncer window was added" "syncer" "$(windows "$NAME")"
    assert_eq "A3: the per-user index was not written" "no" "$(index_written)"
)

# ---------------------------------------------------------------------------
section "A4 — a session created CONCURRENTLY is left untouched too"
# ---------------------------------------------------------------------------
# `has-session` says absent; by the time the bootstrap's own `new-session` runs,
# a racer holds the name. A PATH shim plays the racer: on the bootstrap's
# new-session it creates $NAME for project A and registers it, then lets the
# real call through — which fails as a duplicate.
(
    fresh_server_with "$OTHER" "$OUTSIDE"
    rm -f "$AITASKS_PROJECTS_INDEX"
    mkdir -p "$FIXTURE_DIR/race_bin"
    cat > "$FIXTURE_DIR/race_bin/tmux" <<SHIM
#!/usr/bin/env bash
for a in "\$@"; do
    if [ "\$a" = new-session ]; then
        "$REAL_TMUX" new-session -d -s "$NAME" -n base -c "$OUTSIDE" "sleep 1000"
        "$REAL_TMUX" set-environment -g "AITASKS_PROJECT_$NAME" "$PROJ_A"
        break
    fi
done
exec "$REAL_TMUX" "\$@"
SHIM
    chmod +x "$FIXTURE_DIR/race_bin/tmux"
    export PATH="$FIXTURE_DIR/race_bin:$PATH"     # this subshell only
    boot --create-only "$PROJ_B"

    assert_eq "A4: the racer really took the name (the shim fired)" \
        "base" "$(windows "$NAME")"
    assert_eq "A4: exit 43 — the name was taken by the time new-session ran" \
        "43" "$BOOT_RC"
    assert_contains "A4: reported as session_exists" \
        "BOOTSTRAP_FAILED:session_exists:$NAME" "$BOOT_ERR"
    assert_eq "A4: the racer's registry entry was not overwritten" \
        "$PROJ_A" "$(registry "$NAME")"
    assert_eq "A4: the per-user index was not written" "no" "$(index_written)"
)

# ===========================================================================
section "Part B — _launch_into_new_window, end to end"
# ===========================================================================

# ---------------------------------------------------------------------------
section "B1 — no session for the project: the restore creates it and lands there"
# ---------------------------------------------------------------------------
(
    fresh_server_with "$OTHER" "$OUTSIDE"
    rm -f "$AITASKS_PROJECTS_INDEX"
    IFS='|' read -r pane pid err <<<"$(bdrive "$PROJ_B" agent-pick-b1 "$MARK")"
    sleep 0.3

    assert_eq "B1: no error" "" "$err"
    assert_eq "B1: the pane is real" "yes" \
        "$([ -n "$pane" ] && pane_exists "$pane" && echo yes || echo no)"
    assert_eq "B1: it sits in the project's own, newly created session" \
        "$NAME" "$(pane_fmt "$pane" '#{session_name}')"
    assert_eq "B1: in a window with the record's name" \
        "agent-pick-b1" "$(pane_fmt "$pane" '#{window_name}')"
    assert_eq "B1: and the pid is the launched process" \
        "$pid" "$(pane_fmt "$pane" '#{pane_pid}')"
    assert_eq "B1: the new session is registered to B" "$PROJ_B" "$(registry "$NAME")"
    assert_eq "B1: the unrelated session was not used" "base" "$(windows "$OTHER")"
)

# ---------------------------------------------------------------------------
section "B2 — the name is held by another project: refused, and nothing changes"
# ---------------------------------------------------------------------------
(
    collision_fixture outside
    before="$(snapshot "$NAME")"
    IFS='|' read -r pane pid err <<<"$(bdrive "$PROJ_B" agent-pick-b2 "$MARK")"
    sleep 0.3

    assert_eq "B2: the refusal names the root and the taken session" \
        "no_session_for_root:$PROJ_B|bootstrap:session_name_taken:$NAME" "$err"
    assert_eq "B2: no pane is handed back" "" "$pane"
    assert_eq "B2: A's session is exactly as it was (windows, panes, registry)" \
        "$before" "$(snapshot "$NAME")"
    assert_eq "B2: B's agent was launched NOWHERE" "0" "$(marked_panes)"
)

# ---------------------------------------------------------------------------
section "B3 — no tmux server at all: the bootstrap creates it"
# ---------------------------------------------------------------------------
# The reboot case: `ait frozen restore --all` from a plain terminal. A missing
# server must read as "nothing attributed", and the bootstrap must create the
# server as well as the session.
(
    no_server
    assert_eq "B3: premise — there is no server" "no" \
        "$(tm list-sessions >/dev/null 2>&1 && echo yes || echo no)"
    IFS='|' read -r pane pid err <<<"$(bdrive "$PROJ_B" agent-pick-b3 "$MARK")"
    sleep 0.3

    assert_eq "B3: no error" "" "$err"
    assert_eq "B3: the pane is real" "yes" \
        "$([ -n "$pane" ] && pane_exists "$pane" && echo yes || echo no)"
    assert_eq "B3: in the project's session" "$NAME" "$(pane_fmt "$pane" '#{session_name}')"
    assert_eq "B3: in the record's window" "agent-pick-b3" "$(pane_fmt "$pane" '#{window_name}')"
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
