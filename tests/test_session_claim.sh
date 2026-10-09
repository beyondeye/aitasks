#!/usr/bin/env bash
# test_session_claim.sh - session ownership claim (t1922), on a real tmux server.
#
# `ait ide` / the ensure-mode bootstrap claim a tmux session for a project by
# stamping the session option @aitask_project_root, which discovery treats as
# authoritative. The claim must never take over a session another project
# owns — including one that PREDATES the stamp, whose owner only discovery's
# evidence (its panes, the legacy AITASKS_PROJECT_<s> global) can name — and
# must stop the startup on any failed ownership read or stamp write, before a
# window is added or the session attached.
#
#   Part U  the upgrade path: an existing, UNSTAMPED session owned by A, met by
#           B's claim, ensure-mode bootstrap, and full `ait ide`.
#   Part O  a project keeps its own sessions (stamped or not, wandering pane).
#   Part R  a genuinely recreated session is claimable again.
#   Part F  injected command failures: a tmux shim on PATH fails one subcommand
#           and delegates everything else to the real binary.
#
# ISOLATION. `require_isolated_tmux` + our own TMUX_TMPDIR: every server here is
# private to the run (both gateways follow the no-flag socket it pins). The
# per-user index, systemd and `ait` itself are redirected as in
# test_restore_session_bootstrap_live.sh.
#
# Run: bash tests/test_session_claim.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

command -v tmux >/dev/null 2>&1 || { echo "SKIP: tmux not available"; exit 0; }

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# Cases run inside ( … ) subshells: file-backed counters (CLAUDE.md, t1207).
assert_counters_init

# shellcheck source=lib/tmux_isolation.sh
. "$PROJECT_DIR/tests/lib/tmux_isolation.sh"
require_isolated_tmux

REAL_TMUX="$(command -v tmux)"
# shellcheck disable=SC2034  # read by frozen_fixtures.sh cleanup()
REAL_PATH="$PATH"
# `pwd -P`: the claim compares physical paths, and $TMPDIR may be a symlink.
FIXTURE_DIR="$(cd "$(mktemp -d "${TMPDIR:-/tmp}/ait_claim_XXXXXX")" && pwd -P)"
export TMUX_TMPDIR="$FIXTURE_DIR"

# shellcheck source=lib/frozen_fixtures.sh
. "$PROJECT_DIR/tests/lib/frozen_fixtures.sh"
trap cleanup EXIT

BOOT="$PROJECT_DIR/.aitask-scripts/lib/tmux_bootstrap.sh"
IDE="$PROJECT_DIR/.aitask-scripts/aitask_ide.sh"
NAME="ait_claim_$$"         # the session name A and B BOTH configure
PROJ_A="$FIXTURE_DIR/proj_a"
PROJ_B="$FIXTURE_DIR/proj_b"
OUTSIDE="$FIXTURE_DIR/outside"
SHIM="$FIXTURE_DIR/shim"

export AITASKS_PROJECTS_INDEX="$FIXTURE_DIR/projects.yaml"
# The claim mutex lives under XDG_RUNTIME_DIR: keep it inside the fixture.
export XDG_RUNTIME_DIR="$FIXTURE_DIR/run"
export AIT_NO_SYSTEMD_RUN=1

mkdir -p "$PROJ_A/aitasks/metadata" "$PROJ_B/aitasks/metadata" "$OUTSIDE" \
    "$FIXTURE_DIR/bin" "$SHIM"
printf 'tmux:\n  default_session: %s\n' "$NAME" \
    > "$PROJ_A/aitasks/metadata/project_config.yaml"
# B's syncer autostart makes a takeover visible as an extra `syncer` window.
printf 'tmux:\n  default_session: %s\n  syncer:\n    autostart: true\n' "$NAME" \
    > "$PROJ_B/aitasks/metadata/project_config.yaml"

cat > "$FIXTURE_DIR/bin/ait" <<'STUB'
#!/usr/bin/env bash
case "${1:-}" in monitor|syncer) exec sleep 1000 ;; esac
echo "stub ait: unexpected: $*" >&2
exit 1
STUB
chmod +x "$FIXTURE_DIR/bin/ait"

# The failure shim: FAIL_CMD names the subcommand to fail; FAKE_SET_OPTION=1
# makes set-option report success while writing nothing. Every call is logged.
cat > "$SHIM/tmux" <<STUB
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "$FIXTURE_DIR/shim.log"
if [ -n "\${FAIL_CMD:-}" ] && [ "\$1" = "\$FAIL_CMD" ]; then
    echo "shim: injected failure of \$1" >&2
    exit 1
fi
if [ "\${FAKE_SET_OPTION:-}" = 1 ] && [ "\$1" = set-option ]; then
    exit 0
fi
exec "$REAL_TMUX" "\$@"
STUB
chmod +x "$SHIM/tmux"
export PATH="$FIXTURE_DIR/bin:$PATH"

# --- helpers -----------------------------------------------------------------

server_with() {   # server_with <cwd>...: a fresh server holding $NAME, one window per cwd
    tm kill-server 2>/dev/null || true
    sleep 0.3
    tm new-session -d -s "$NAME" -n base -c "$1" "sleep 1000"
    shift
    local i=1 d
    for d in "$@"; do
        tm new-window -t "=$NAME:" -n "w$i" -c "$d" "sleep 1000"
        i=$((i + 1))
    done
    sleep 0.3
    rm -f "$AITASKS_PROJECTS_INDEX" "$FIXTURE_DIR/shim.log"
}

stamp()    { tm list-sessions -F "#{session_name}	#{@aitask_project_root}" 2>/dev/null | sed -n "s|^$NAME	||p"; }
registry() { tm show-environment -g "AITASKS_PROJECT_$NAME" 2>/dev/null | sed -n "s|^AITASKS_PROJECT_$NAME=||p"; }
windows()  { tm list-windows -t "=$NAME" -F '#{window_name}' 2>/dev/null | paste -sd ' ' -; }
snapshot() {
    tm list-panes -s -t "=$NAME:" -F '#{window_name}|#{pane_id}|#{pane_current_path}' 2>/dev/null
    echo "registry=$(registry)"
    echo "stamp=$(stamp)"
}

claim() {   # claim <root> [--created] -> RC / ERR
    ERR="$(bash -c 'source "$1"; shift; _tmux_bootstrap_set_project_registry "$@"' \
        _ "$BOOT" "$1" "$NAME" "${@:2}" 2>&1 >/dev/null)"
    RC=$?
}

boot() {    # boot <root> -> RC / ERR (ensure mode)
    ERR="$(bash "$BOOT" "$1" 2>&1 >/dev/null)"
    RC=$?
}

ide() {     # ide <project dir> -> RC / ERR (full `ait ide`, no terminal)
    ERR="$(cd "$1" && bash "$IDE" --no-frozen-check </dev/null 2>&1 >/dev/null)"
    RC=$?
}

# ===========================================================================
section "Part U — an existing UNSTAMPED session owned by A"
# ===========================================================================

section "U1 — legacy registry names A, pane outside any project"
(
    server_with "$OUTSIDE"
    tm set-environment -g "AITASKS_PROJECT_$NAME" "$PROJ_A"
    before="$(snapshot)"

    claim "$PROJ_B"
    assert_eq "U1: B's claim is refused with 45" "45" "$RC"
    assert_contains "U1: the sentinel names A" \
        "BOOTSTRAP_FAILED:session_owned:$NAME:$PROJ_A" "$ERR"
    assert_eq "U1: nothing changed (no stamp, registry still A)" "$before" "$(snapshot)"

    boot "$PROJ_B"
    assert_eq "U1: the ensure bootstrap refuses with 45" "45" "$RC"
    assert_eq "U1: and changes nothing (no syncer window)" "$before" "$(snapshot)"

    ide "$PROJ_B"
    assert_eq "U1: full ait ide from B exits 1" "1" "$RC"
    assert_contains "U1: ait ide names the owner" "belongs to project $PROJ_A" "$ERR"
    assert_eq "U1: ait ide added no monitor/syncer window" "base" "$(windows)"
    assert_eq "U1: and changed nothing else" "$before" "$(snapshot)"
    assert_eq "U1: the per-user index was not written" "no" \
        "$([ -f "$AITASKS_PROJECTS_INDEX" ] && echo yes || echo no)"
)

section "U2 — only A's panes name the owner (no legacy registry)"
(
    server_with "$PROJ_A" "$PROJ_A"
    before="$(snapshot)"

    boot "$PROJ_B"
    assert_eq "U2: the ensure bootstrap refuses with 45" "45" "$RC"
    ide "$PROJ_B"
    assert_eq "U2: full ait ide from B exits 1" "1" "$RC"
    assert_contains "U2: ait ide names the owner" "belongs to project $PROJ_A" "$ERR"
    assert_eq "U2: nothing changed" "$before" "$(snapshot)"
)

section "U2b — the refusal names the owner for a session name holding '/'"
(
    slash="work/m_$$"
    tm kill-server 2>/dev/null || true
    sleep 0.3
    tm new-session -d -s "$slash" -n base -c "$PROJ_A" "sleep 1000"
    tm set-option -t "=$slash:" @aitask_project_root "$PROJ_A"
    sleep 0.3
    ERR="$(cd "$PROJ_B" && bash "$IDE" --no-frozen-check --session "$slash" </dev/null 2>&1 >/dev/null)"
    RC=$?
    assert_eq "U2b: ait ide exits 1" "1" "$RC"
    assert_contains "U2b: and names the owning project" "belongs to project $PROJ_A" "$ERR"
    assert_not_contains "U2b: no sed failure leaks out" "unknown option" "$ERR"
)

section "U3 — a session nobody owns is claimable"
(
    server_with "$OUTSIDE"
    claim "$PROJ_B"
    assert_eq "U3: B claims an unowned session" "0" "$RC"
    assert_eq "U3: the stamp names B" "$PROJ_B" "$(stamp)"
    assert_eq "U3: the legacy registry follows the verified stamp" "$PROJ_B" "$(registry)"
)

# ===========================================================================
section "Part O — a project keeps its own sessions"
# ===========================================================================

section "O1 — A claims its own unstamped session, even with a pane in B"
(
    server_with "$PROJ_A" "$PROJ_B" "$PROJ_A"
    claim "$PROJ_A"
    assert_eq "O1: A's claim succeeds (A holds the pane majority)" "0" "$RC"
    assert_eq "O1: the stamp names A" "$PROJ_A" "$(stamp)"

    claim "$PROJ_A"
    assert_eq "O1: re-claiming is idempotent" "0" "$RC"
    claim "$PROJ_B"
    assert_eq "O1: B's claim on the stamped session is refused" "45" "$RC"
    assert_contains "O1: naming A" "session_owned:$NAME:$PROJ_A" "$ERR"
    assert_eq "O1: the stamp still names A" "$PROJ_A" "$(stamp)"
)

section "O2 — a stamp naming no project is no ownership; evidence decides"
(
    server_with "$PROJ_A"
    tm set-option -t "=$NAME:" @aitask_project_root "$OUTSIDE"
    claim "$PROJ_B"
    assert_eq "O2: B is refused — A's panes still own it" "45" "$RC"

    server_with "$OUTSIDE"
    tm set-option -t "=$NAME:" @aitask_project_root "$OUTSIDE"
    claim "$PROJ_B"
    assert_eq "O2: with no evidence either, B claims" "0" "$RC"
    assert_eq "O2: the stamp names B" "$PROJ_B" "$(stamp)"
)

section "O3 — a stamp is compared EXACTLY (a trailing space is part of the path)"
(
    ws="$FIXTURE_DIR/proj_ws "
    mkdir -p "$ws/aitasks/metadata"
    printf 'x: 1\n' > "$ws/aitasks/metadata/project_config.yaml"
    server_with "$PROJ_B"
    tm set-option -t "=$NAME:" @aitask_project_root "$ws"
    claim "$PROJ_B"
    assert_eq "O3: B is refused — the session belongs to 'proj_ws '" "45" "$RC"
    assert_contains "O3: the owner keeps its trailing space" \
        "session_owned:$NAME:$ws" "$ERR"
)

# ===========================================================================
section "Part C — concurrent claims are serialized"
# ===========================================================================

# Two claims race for an UNOWNED session. The evidence step is slowed so both
# would read "no owner" before either writes; only the claim mutex keeps the
# read-evidence-write sequence atomic. <mode> "nolock" disables the mutex
# through its seams — the negative control proving the race is real.
race_claim() {   # race_claim <root> <rc-file> [nolock]
    bash -c '
        source "$1"
        _tmux_bootstrap_session_evidence() { sleep 1; echo NONE; }
        if [ "$4" = nolock ]; then
            _tmux_bootstrap_claim_lock_acquire() { return 0; }
            _tmux_bootstrap_claim_lock_release() { :; }
        fi
        _tmux_bootstrap_set_project_registry "$2" "$3"' \
        _ "$BOOT" "$1" "$NAME" "${3:-}" >/dev/null 2>&1
    echo $? > "$2"
}

section "C1 — with the mutex exactly one project wins"
(
    server_with "$OUTSIDE"
    race_claim "$PROJ_A" "$FIXTURE_DIR/rc_a" & pa=$!
    race_claim "$PROJ_B" "$FIXTURE_DIR/rc_b" & pb=$!
    wait "$pa" "$pb"
    rcs="$(cat "$FIXTURE_DIR/rc_a" "$FIXTURE_DIR/rc_b" | sort | paste -sd ' ' -)"
    assert_eq "C1: one claim succeeds, the other is refused as owned" "0 45" "$rcs"
    if [ "$(cat "$FIXTURE_DIR/rc_a")" = 0 ]; then winner="$PROJ_A"; else winner="$PROJ_B"; fi
    assert_eq "C1: the stamp names the winner" "$winner" "$(stamp)"
)

section "C2 — CONTROL: without the mutex both claims 'win'"
(
    server_with "$OUTSIDE"
    race_claim "$PROJ_A" "$FIXTURE_DIR/rc_a" nolock & pa=$!
    race_claim "$PROJ_B" "$FIXTURE_DIR/rc_b" nolock & pb=$!
    wait "$pa" "$pb"
    # Both read "no owner" and both write, so neither is ever refused as owned.
    # Which one then fails its verify (47) — or whether both "verify" (0 0)
    # because one re-read lands before the other's write — is timing.
    rcs="$(cat "$FIXTURE_DIR/rc_a" "$FIXTURE_DIR/rc_b" | sort | paste -sd ' ' -)"
    assert_not_contains "C2: unserialized, neither claim is refused as owned" "45" "$rcs"
    assert_contains "C2: and at least one claim reports success" "0" "$rcs"
)

# ===========================================================================
section "Part R — genuine recreation"
# ===========================================================================

section "R1 — a killed-and-recreated session belongs to its creator"
(
    server_with "$OUTSIDE"
    tm new-session -d -s keepalive -c "$OUTSIDE" "sleep 1000"
    tm set-environment -g "AITASKS_PROJECT_$NAME" "$PROJ_A"
    tm set-option -t "=$NAME:" @aitask_project_root "$PROJ_A"
    tm kill-session -t "=$NAME"
    sleep 0.3

    boot "$PROJ_B"
    assert_eq "R1: the bootstrap creates and claims the session" "0" "$RC"
    assert_eq "R1: the new session's stamp names B, not the dead session's A" \
        "$PROJ_B" "$(stamp)"
    assert_eq "R1: the stale legacy registry entry is repaired" "$PROJ_B" "$(registry)"
    assert_contains "R1: B's own syncer window was added" "syncer" "$(windows)"
)

# ===========================================================================
section "Part F — injected command failures stop the startup"
# ===========================================================================

shim_log() { cat "$FIXTURE_DIR/shim.log" 2>/dev/null; }

section "F1 — the stamp read fails: 46, nothing written"
(
    server_with "$PROJ_A"
    before="$(snapshot)"
    PATH="$SHIM:$PATH" FAIL_CMD=list-sessions claim "$PROJ_A"
    assert_eq "F1: claim exits 46" "46" "$RC"
    assert_contains "F1: claim_unverified sentinel" "BOOTSTRAP_FAILED:claim_unverified:$NAME" "$ERR"
    assert_not_contains "F1: no set-option was attempted" "set-option" "$(shim_log)"

    PATH="$SHIM:$PATH" FAIL_CMD=list-sessions ide "$PROJ_A"
    assert_eq "F1: ait ide exits 1" "1" "$RC"
    assert_contains "F1: ait ide says it could not verify" "Could not verify" "$ERR"
    assert_not_contains "F1: no window was created" "new-window" "$(shim_log)"
    assert_not_contains "F1: nothing attached" "attach" "$(shim_log)"
    assert_eq "F1: nothing changed" "$before" "$(snapshot)"

    PATH="$SHIM:$PATH" FAIL_CMD=list-sessions boot "$PROJ_A"
    assert_eq "F1: the ensure bootstrap exits 46" "46" "$RC"
)

section "F2 — set-option fails: 47, nothing else written"
(
    server_with "$PROJ_A"
    before="$(snapshot)"
    PATH="$SHIM:$PATH" FAIL_CMD=set-option ide "$PROJ_A"
    assert_eq "F2: ait ide exits 1" "1" "$RC"
    assert_contains "F2: ait ide says it could not register" "Could not register" "$ERR"
    assert_not_contains "F2: no window was created" "new-window" "$(shim_log)"
    assert_not_contains "F2: the legacy registry was not written" "set-environment" "$(shim_log)"
    assert_not_contains "F2: nothing attached" "attach" "$(shim_log)"
    assert_eq "F2: nothing changed" "$before" "$(snapshot)"
    assert_eq "F2: the per-user index was not written" "no" \
        "$([ -f "$AITASKS_PROJECTS_INDEX" ] && echo yes || echo no)"
)

section "F3 — set-option 'succeeds' but the re-read disagrees: 47"
(
    server_with "$PROJ_A"
    PATH="$SHIM:$PATH" FAKE_SET_OPTION=1 claim "$PROJ_A"
    assert_eq "F3: claim exits 47" "47" "$RC"
    assert_contains "F3: claim_write_failed sentinel" \
        "BOOTSTRAP_FAILED:claim_write_failed:$NAME" "$ERR"
    assert_not_contains "F3: the legacy registry was not written" "set-environment" "$(shim_log)"

    PATH="$SHIM:$PATH" FAKE_SET_OPTION=1 boot "$PROJ_A"
    assert_eq "F3: the ensure bootstrap exits 47" "47" "$RC"
    assert_eq "F3: and added no syncer/monitor window" "base" "$(windows)"
)

section "F4 — the ownership evidence is incomplete: 46"
(
    # list-panes fails inside discovery's Python evidence query.
    server_with "$PROJ_A"
    before="$(snapshot)"
    PATH="$SHIM:$PATH" FAIL_CMD=list-panes ide "$PROJ_A"
    assert_eq "F4: ait ide exits 1" "1" "$RC"
    assert_contains "F4: ait ide says it could not verify" "Could not verify" "$ERR"
    assert_contains "F4: the evidence query really ran (and failed)" "list-panes" "$(shim_log)"
    assert_not_contains "F4: no set-option was attempted" "set-option" "$(shim_log)"
    assert_eq "F4: nothing changed" "$before" "$(snapshot)"
)

assert_counters_load
echo
echo "=== Summary ==="
echo "Passed: $PASS / $TOTAL"
if [[ "$FAIL" -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "FAILED: $FAIL"
    exit 1
fi
