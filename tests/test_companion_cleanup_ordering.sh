#!/usr/bin/env bash
# test_companion_cleanup_ordering.sh — `aitask_companion_cleanup.sh` must clean
# up every companion regardless of which one armed the hook first (t1451).
#
# THE DEFECT. One `pane-died` hook carries exactly one `companion_pane`, and
# `attach_companion_cleanup_hook` deliberately never overwrites — so the
# argument names whichever companion armed the hook FIRST. `spawn_shadow`
# passes `companion_pane or shadow_pane`, and from the full monitor
# `companion_pane` is None, so a shadow-first ordering leaves the hook naming
# the SHADOW pane. Job 2 then counted a minimonitor that is not `$companion` as
# a real AGENT sibling (it carries no `@aitask_shadow_target`), so `others`
# never reached 0 and the named companion was spared too.
#
# The fix discovers companions from `@aitask_monitor_kind`, exactly as job 1
# already discovers shadows from `@aitask_shadow_target`.
#
# The script is invoked DIRECTLY rather than through a real `pane-died` event:
# it is the unit that decides, and driving real hook firings is slower and
# flakier without testing anything more. Its raw, un-flagged `tmux` calls are
# contained by the fixture $TMUX_TMPDIR.
#
# Case 2 is the negative control — it fails against the pre-fix script.
#
# Run: bash tests/test_companion_cleanup_ordering.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=lib/tmux_isolation.sh
. "$PROJECT_DIR/tests/lib/tmux_isolation.sh"
require_isolated_tmux

PASS=0
FAIL=0
TOTAL=0

CLEANUP="$PROJECT_DIR/.aitask-scripts/aitask_companion_cleanup.sh"

command -v tmux >/dev/null 2>&1 || { echo "SKIP: tmux not installed"; exit 0; }

FIXTURE_DIR="$(mktemp -d)"
export TMUX_TMPDIR="$FIXTURE_DIR/tmux"
mkdir -p "$TMUX_TMPDIR"
SESSION="t1451clean"

cleanup() {
    tmux kill-server 2>/dev/null || true
    rm -rf "$FIXTURE_DIR"
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Fixture. An `anchor` window keeps the session alive after the test window's
# panes are all killed, so the survivor query still has a server to talk to.
# ---------------------------------------------------------------------------
new_window() {
    tmux kill-session -t "=$SESSION" 2>/dev/null || true
    tmux new-session -d -s "$SESSION" -n anchor "sleep 600"
    tmux new-window -t "=$SESSION" -n work "sleep 600"
}

add_pane() { tmux split-window -P -F '#{pane_id}' -t "=$SESSION:work" "sleep 600"; }
first_pane() { tmux list-panes -t "=$SESSION:work" -F '#{pane_id}' | head -n1; }

mark_monitor() { tmux set-option -p -t "$1" @aitask_monitor_kind "minimonitor:$$"; }
mark_shadow()  { tmux set-option -p -t "$1" @aitask_shadow_target "$2"; }

# Sorted, space-joined survivor list for the work window ("" when it is gone).
survivors() {
    tmux list-panes -t "=$SESSION:work" -F '#{pane_id}' 2>/dev/null \
        | sort | tr '\n' ' ' | sed 's/ $//'
}
sorted() { printf '%s\n' "$@" | sort | tr '\n' ' ' | sed 's/ $//'; }

run_cleanup() { bash "$CLEANUP" "$1" "$2" >/dev/null 2>&1 || true; }

# ============================================================
echo "--- 1. companion-first ordering: hook names the minimonitor ---"
new_window
PRIMARY="$(first_pane)"
MINI="$(add_pane)"
SHADOW="$(add_pane)"
mark_monitor "$MINI"
mark_shadow "$SHADOW" "$PRIMARY"
# Positive control: all three really are in the window before we start.
assert_eq "fixture built" "$(sorted "$PRIMARY" "$MINI" "$SHADOW")" "$(survivors)"
run_cleanup "$PRIMARY" "$MINI"
assert_eq "no pane survives a last-agent exit" "" "$(survivors)"

# ============================================================
echo "--- 2. shadow-first ordering: hook names the SHADOW (negative control) ---"
# Reproduces a hook armed by spawn_shadow from the full monitor, where
# companion_pane is None so the argument is the shadow's own pane. Pre-fix, the
# minimonitor counted as a real agent sibling and NOTHING but the shadow died.
new_window
PRIMARY="$(first_pane)"
MINI="$(add_pane)"
SHADOW="$(add_pane)"
mark_monitor "$MINI"
mark_shadow "$SHADOW" "$PRIMARY"
assert_eq "fixture built" "$(sorted "$PRIMARY" "$MINI" "$SHADOW")" "$(survivors)"
run_cleanup "$PRIMARY" "$SHADOW"
assert_eq "companion discovered by marker, not by argument" "" "$(survivors)"

# ============================================================
echo "--- 3. a real sibling keeps the companion alive ---"
new_window
PRIMARY="$(first_pane)"
MINI="$(add_pane)"
SHADOW="$(add_pane)"
EXTRA="$(add_pane)"        # a plain user shell — a real agent sibling
mark_monitor "$MINI"
mark_shadow "$SHADOW" "$PRIMARY"
run_cleanup "$PRIMARY" "$MINI"
# Job 1 kills the bound shadow unconditionally; the primary always dies; the
# companion and the unrelated pane must both survive.
assert_eq "companion and sibling survive" \
    "$(sorted "$MINI" "$EXTRA")" "$(survivors)"

# ============================================================
echo "--- 4. an unmarked legacy companion is still honoured ---"
# A companion pane predating the marker is named only by the argument.
new_window
PRIMARY="$(first_pane)"
LEGACY="$(add_pane)"
run_cleanup "$PRIMARY" "$LEGACY"
assert_eq "argument still names a companion" "" "$(survivors)"

# ============================================================
echo "--- 5. a shadow in another window is still reached ---"
# Job 1 is session-scoped; the format change must not have narrowed it.
new_window
PRIMARY="$(first_pane)"
MINI="$(add_pane)"
mark_monitor "$MINI"
tmux new-window -t "=$SESSION" -n elsewhere "sleep 600"
FAR_SHADOW="$(tmux list-panes -t "=$SESSION:elsewhere" -F '#{pane_id}' | head -n1)"
mark_shadow "$FAR_SHADOW" "$PRIMARY"
run_cleanup "$PRIMARY" "$MINI"
assert_eq "work window fully cleaned" "" "$(survivors)"
assert_eq "cross-window shadow killed" "" \
    "$(tmux list-panes -t "=$SESSION:elsewhere" -F '#{pane_id}' 2>/dev/null | tr -d '\n')"

# ============================================================
echo ""
echo "============================================"
echo "Results: $PASS passed, $FAIL failed (of $TOTAL)"
echo "============================================"
[ "$FAIL" -eq 0 ] || exit 1
