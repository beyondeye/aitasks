#!/usr/bin/env bash
# tests/test_ide_frozen_all_projects_live.sh — `ait ide`'s frozen-agent offer
# across EVERY project (t2039), against a real tmux server, the real store and
# the real session bootstrap.
#
# `tests/test_ide_frozen_offer.sh` owns the offer's branching with a stub
# `aitask_frozen.sh`. This file owns what only the real pieces answer: that a
# project with no tmux session gets ITS OWN session created by the canonical
# bootstrap (`tmux_bootstrap.sh --create-only`, t1784) when its viewers come back
# through `reopen` with no `--session`; that a project whose configured session
# name is held by another project is refused and reported while the others
# still succeed; and that a project whose directory is gone, or that is not
# registered, is listed but never touched — no session is created for it.
#
# Projects (all with `tmux.minimonitor.auto_spawn: false`, so no companion and no
# pane-died hook is armed):
#   P  the current project, session A exists          -> viewer lands in A
#   Q  registered, no session                          -> bootstrapped `qsess`
#   R  registered, default_session `heldsess` held by another project's session
#                                                      -> refused, reported
#   M  registered, directory deleted after seeding     -> listed, untouched
#   U  present, NOT registered                         -> listed, untouched
#
# ISOLATION. `require_isolated_tmux` (no $TMUX, own TMUX_TMPDIR, the gateway on
# the default socket of that dir), plus the bootstrap's side effects kept in the
# fixture exactly as `test_restore_session_bootstrap_live.sh` does: the per-user
# project registry (AITASKS_PROJECTS_INDEX), systemd (AIT_NO_SYSTEMD_RUN) and
# `ait` itself (a stub on PATH before the server starts, so the seeded
# `monitor` / `syncer` windows stay up without booting TUIs).
#
# Run: bash tests/test_ide_frozen_all_projects_live.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

command -v tmux >/dev/null 2>&1 || { echo "SKIP: tmux not available"; exit 0; }

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=lib/tmux_isolation.sh
. "$PROJECT_DIR/tests/lib/tmux_isolation.sh"
require_isolated_tmux

PASS=0
FAIL=0
TOTAL=0

REAL_PATH="$PATH"
REAL_TMUX="$(command -v tmux)"
# `pwd -P`: the store and discovery realpath every root.
FIXTURE_DIR="$(cd "$(mktemp -d "${TMPDIR:-/tmp}/ait_ide_roots_XXXXXX")" && pwd -P)"
export TMUX_TMPDIR="$FIXTURE_DIR"
export AITASKS_AGENT_SESSIONS_FILE="$FIXTURE_DIR/agent_sessions.json"
export AITASKS_FROZEN_DIR="$FIXTURE_DIR/frozen"
export AITASKS_FROZEN_STANDIN_CMD="$PROJECT_DIR/tests/lib/fake_standin.sh"
export AITASKS_PROJECTS_INDEX="$FIXTURE_DIR/projects.yaml"
export AIT_NO_SYSTEMD_RUN=1
export AITASKS_TEST_MODE=1
unset AITASKS_REOPEN_FAIL_AT
chmod +x "$AITASKS_FROZEN_STANDIN_CMD" 2>/dev/null || true

SESSIONS_SH="$PROJECT_DIR/.aitask-scripts/aitask_agent_sessions.sh"
FROZEN_SH="$PROJECT_DIR/.aitask-scripts/aitask_frozen.sh"

# shellcheck source=lib/frozen_fixtures.sh
. "$PROJECT_DIR/tests/lib/frozen_fixtures.sh"
trap cleanup EXIT

mkdir -p "$FIXTURE_DIR/bin"
cat > "$FIXTURE_DIR/bin/ait" <<'STUB'
#!/usr/bin/env bash
# The bootstrap seeds `ait monitor` (and `ait syncer` when autostart is on).
# Sleeping keeps the windows observable without booting TUIs.
case "${1:-}" in monitor|syncer) exec sleep 1000 ;; esac
exit 1
STUB
chmod +x "$FIXTURE_DIR/bin/ait"
# Exported BEFORE the server starts: its global environment is captured then.
export PATH="$FIXTURE_DIR/bin:$PATH"

make_project() {   # make_project <dir> <default_session>
    mkdir -p "$1/aitasks/metadata"
    printf 'tmux:\n  default_session: %s\n  minimonitor:\n    auto_spawn: false\n' "$2" \
        > "$1/aitasks/metadata/project_config.yaml"
}
P="$FIXTURE_DIR/pproj"; make_project "$P" A
Q="$FIXTURE_DIR/qproj"; make_project "$Q" qsess
R="$FIXTURE_DIR/rproj"; make_project "$R" heldsess
M="$FIXTURE_DIR/mproj"; make_project "$M" msess
U="$FIXTURE_DIR/uproj"; make_project "$U" usess
H="$FIXTURE_DIR/holder"; make_project "$H" heldsess    # owns `heldsess`
cat > "$AITASKS_PROJECTS_INDEX" <<EOF
projects:
  - name: pproj
    path: $P
  - name: qproj
    path: $Q
  - name: rproj
    path: $R
  - name: mproj
    path: $M
EOF

tm new-session -d -s A -c "$P" -n home "sleep 1000"
tm new-session -d -s heldsess -c "$H" -n home "sleep 1000"

# seed <root> <window> — a `frozen` record whose pane is gone; prints its id.
seed() {
    local root="$1" window="$2" out id nonce
    store upsert --root "$root" --window "$window" --pane "%99999" \
        --pane-pid 999999 --session-id "sess-$window" --task-id 12 >/dev/null
    id="$(store list --root "$root" | grep "|$window|" | tail -1 | cut -d: -f2 | cut -d'|' -f1)"
    mkdir -p "$AITASKS_FROZEN_DIR/$id"
    : > "$AITASKS_FROZEN_DIR/$id/c.ansi"
    : > "$AITASKS_FROZEN_DIR/$id/c.txt"
    out="$(store freeze-begin "$id" --owner-pid $$ \
        --capture-ansi "$AITASKS_FROZEN_DIR/$id/c.ansi" \
        --capture-txt "$AITASKS_FROZEN_DIR/$id/c.txt" --lines 0)"
    nonce="${out##*|}"
    store freeze-commit "$id" --nonce "$nonce" --pane "" --pane-pid 0 >/dev/null
    echo "$id"
}

session_exists() { tm has-session -t "=$1" 2>/dev/null && echo yes || echo no; }

p_id="$(seed "$P" agent-p)"
q_id="$(seed "$Q" agent-q)"
r_id="$(seed "$R" agent-r)"
m_id="$(seed "$M" agent-m)"
u_id="$(seed "$U" agent-u)"
rm -rf "$M"                                       # its directory is gone now

# ---------------------------------------------------------------------------
section "the listing groups every project, with its state"
# ---------------------------------------------------------------------------
listing="$("$FROZEN_SH" gone --all-roots 2>&1)"
assert_contains "P is ok"            "GONE_ROOT:ok|pproj|$P" "$listing"
assert_contains "Q is ok"            "GONE_ROOT:ok|qproj|$Q" "$listing"
assert_contains "R is ok"            "GONE_ROOT:ok|rproj|$R" "$listing"
assert_contains "M is missing"       "GONE_ROOT:missing|mproj|$M" "$listing"
assert_contains "U is unregistered"  "GONE_ROOT:unregistered|uproj|$U" "$listing"
assert_contains "a GONE line ends with its root" "|$Q" \
    "$(grep "^GONE:$q_id|" <<<"$listing")"
assert_contains "five records" "GONE_COUNT:5" "$listing"

held_before="$(tm list-windows -t "=heldsess:" -F '#{window_name}' | paste -sd ' ' -)"

# ---------------------------------------------------------------------------
section "V for P, Q and R: each lands in its own project's session"
# ---------------------------------------------------------------------------
. "$PROJECT_DIR/.aitask-scripts/lib/ide_frozen_offer.sh"
out="$(printf 'V\nV\nV\n' | AIT_IDE_FROZEN_ASSUME_TTY=1 \
    ide_offer_frozen_agents "$P" A "$FROZEN_SH" 2>&1)"
echo "$out" | sed 's/^/    | /'

assert_eq "only the three actionable projects are asked" "3" \
    "$(grep -o 'Choice for ' <<<"$out" | wc -l | tr -d ' ')"
assert_contains "P's viewer comes back in A" "REOPENED:$p_id|fresh|A:agent-p|" "$out"
assert_eq "P's record names a pane in A" "A" \
    "$(pane_fmt "$(record_field "$p_id" pane_id)" '#{session_name}')"

assert_eq "Q got its OWN session, created by the bootstrap" "yes" "$(session_exists qsess)"
assert_contains "Q's viewer comes back in qsess" "REOPENED:$q_id|fresh|qsess:agent-q|" "$out"
assert_eq "Q's record names a pane in qsess" "qsess" \
    "$(pane_fmt "$(record_field "$q_id" pane_id)" '#{session_name}')"
assert_eq "Q's viewer is NOT in the session being opened" "" \
    "$(tm list-windows -t "=A:" -F '#{window_name}' | grep -x agent-q || true)"

assert_contains "R's refused bootstrap is reported" "REOPEN_FAILED:$r_id|no_session_for_root:$R" "$out"
assert_contains "naming the taken session" "session_name_taken:heldsess" "$out"
assert_eq "R stays frozen" "frozen" "$(record_field "$r_id" state)"
assert_eq "R still names no pane" "" "$(record_field "$r_id" pane_id)"
assert_eq "the holder's session is untouched" "$held_before" \
    "$(tm list-windows -t "=heldsess:" -F '#{window_name}' | paste -sd ' ' -)"

assert_contains "M is listed with its reason" "mproj — 1 · project directory gone" "$out"
assert_eq "no session is created for M" "no" "$(session_exists msess)"
assert_eq "M's record is untouched" "" "$(record_field "$m_id" pane_id)"
assert_contains "U is listed with its reason" "uproj — 1 · not a registered project" "$out"
assert_eq "no session is created for U" "no" "$(session_exists usess)"
assert_eq "U's record is untouched" "" "$(record_field "$u_id" pane_id)"

assert_contains "the user is told where Q's agents are" \
    "Other projects' agents are in their own tmux sessions: qproj (qsess)" "$out"
assert_not_contains "R is not named as reachable" "rproj (" "$out"

# ---------------------------------------------------------------------------
section "a second run offers only what is still without a viewer"
# ---------------------------------------------------------------------------
listing="$("$FROZEN_SH" gone --all-roots 2>&1)"
assert_not_contains "P is tracked now" "GONE:$p_id|" "$listing"
assert_not_contains "Q is tracked now" "GONE:$q_id|" "$listing"
assert_contains "R is still gone" "GONE:$r_id|" "$listing"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
echo "ALL TESTS PASSED"
