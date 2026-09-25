#!/usr/bin/env bash
# tests/test_frozen_reopen_live.sh — the reopen coordinator (`agent_reopen.py`,
# t1847) against a real tmux server and the real store.
#
# `tests/test_agent_reopen.py` owns the branching with a fake tmux. This file
# owns what only a real server answers: that the `if-shell -F` guards really
# fire (and really decline), that the attempt name is really visible from the
# first instant, that discovery really attributes two sessions to one project,
# and that a recreated viewer really is back in the state machine (`drop` works
# from its new pane).
#
# ISOLATED, NOT REFUSING. Every tmux call the code under test makes goes through
# the gateway, and the synthetic project sets `tmux.minimonitor.auto_spawn:
# false`, so no companion — and no pane-died hook that would run raw `tmux`
# outside the gateway — is ever armed. `require_isolated_tmux` is therefore a
# sufficient guarantee and this suite runs alongside a live user server.
#
# Records are seeded through the SHIPPED store verbs (`upsert`, `freeze-begin`,
# `freeze-commit` with the gone-pane pair), exactly the state a record is left
# in after a tmux server dies under a frozen viewer.
#
# Cases
#   a   happy path: fresh window under the recorded name, stamped, recorded
#   b   `drop` works from the recreated pane
#   c   two same-root sessions: `--session B` lands in B; a foreign session fails closed
#   c2  from a client in A that holds a window named like another project's
#       session C, `--session C` still fails closed (reopen and restore)
#   c3  from a client in A that holds a window named B (this project's own
#       second session), `restore --session B` and `reopen` still succeed in B
#   d   stamp failure: nothing survives, the record is untouched, no lease held
#   e   lost `-P` output: identified by name; with a stamp failure, nothing survives
#   f   store failure: nothing survives; with a failed cleanup, a stamped survivor
#       under the FINAL name, which the next run adopts without a suffix
#   f2  a suffixed name stays stable across that adoption
#   g   a stranded viewer in another session is moved into the selected one
#   h   uncertain launch, retry BEFORE the viewer self-stamps: adopted by name
#   i   rename failure: a fresh window is removed; an adopted one is kept and
#       fixed on the next run
#   j   an option-like session name (`-n`) is targeted verbatim
#   k   a gone-pane RESTORE with `--session B` lands in B, not in A
#   h2  `ait ide`'s R over gone, stranded, view-only and failed-adoption records:
#       the agents come back inside their viewers; the untracked one is skipped
#   m1  a gone-pane restore's session mismatch rolls the stand-in back INTO the
#       new window, and the record tracks it (t1875)
#   m2  lost `-P` output, and m3 an uncertain rc: identified by the attempt name
#   m4  a stamp that does not take: the window is removed
#   m5  an unanswerable launch names its attempt; a retry, reopen and `gone`
#       refuse to duplicate or adopt the survivor; closing it unblocks the retry
#   m6  the crash end state (stamped, marked, renamed, record on a gone pane):
#       reopen does not adopt it; restore, `ait ide` R and drop refuse it
#   m7  the same survivor at the record's OWN pane id: never respawned as the
#       stand-in, never `pane_present`, never killed by drop
#
# REAL RESTORES (k, h2). The synthetic project symlinks the shipped
# `.aitask-scripts` and copies the model metadata, so the restore coordinator
# resolves a real `claude --resume` argv; a fake `claude` on PATH execs
# `tests/lib/fake_agent.sh`, which drives the SHIPPED SessionStart hook — the
# acknowledgement path is real. Companion auto-spawn stays off, so these cases
# stay in the isolated class too.
#
# Run: bash tests/test_frozen_reopen_live.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

command -v tmux >/dev/null 2>&1 || { echo "SKIP: tmux not available"; exit 0; }

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
assert_counters_init

# shellcheck source=lib/tmux_isolation.sh
. "$PROJECT_DIR/tests/lib/tmux_isolation.sh"
require_isolated_tmux

REAL_PATH="$PATH"
REAL_TMUX="$(command -v tmux)"
FIXTURE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/ait_reopen_live_XXXXXX")"
FIXTURE_DIR="$(cd "$FIXTURE_DIR" && pwd -P)"
export TMUX_TMPDIR="$FIXTURE_DIR"
export AITASKS_AGENT_SESSIONS_FILE="$FIXTURE_DIR/agent_sessions.json"
export AITASKS_FROZEN_DIR="$FIXTURE_DIR/frozen"
export AITASKS_FROZEN_STANDIN_CMD="$PROJECT_DIR/tests/lib/fake_standin.sh"
export AITASKS_TEST_MODE=1
unset AITASKS_REOPEN_FAIL_AT

SESSIONS_SH="$PROJECT_DIR/.aitask-scripts/aitask_agent_sessions.sh"
FROZEN_SH="$PROJECT_DIR/.aitask-scripts/aitask_frozen.sh"
FAKE_AGENT="$PROJECT_DIR/tests/lib/fake_agent.sh"
chmod +x "$AITASKS_FROZEN_STANDIN_CMD" 2>/dev/null || true

# shellcheck source=lib/frozen_fixtures.sh
. "$PROJECT_DIR/tests/lib/frozen_fixtures.sh"
trap cleanup EXIT

make_project() {
    mkdir -p "$1/aitasks/metadata"
    printf 'tmux:\n  default_session: %s\n  minimonitor:\n    auto_spawn: false\n' "$2" \
        > "$1/aitasks/metadata/project_config.yaml"
}
PROJ="$FIXTURE_DIR/proj"
OTHER="$FIXTURE_DIR/other"
make_project "$PROJ" A
make_project "$OTHER" C
ln -s "$PROJECT_DIR/.aitask-scripts" "$PROJ/.aitask-scripts"
cp "$PROJECT_DIR/aitasks/metadata/codeagent_config.json" \
    "$PROJECT_DIR"/aitasks/metadata/models_*.json "$PROJ/aitasks/metadata/"

# A fake `claude`, on PATH BEFORE the server starts: `respawn-pane` / the new
# window run their command in the SERVER's environment, captured at start.
mkdir -p "$FIXTURE_DIR/bin"
printf '#!/usr/bin/env bash\nexec "%s" "$@"\n' "$FAKE_AGENT" > "$FIXTURE_DIR/bin/claude"
chmod +x "$FIXTURE_DIR/bin/claude" "$FAKE_AGENT" 2>/dev/null || true
export PATH="$FIXTURE_DIR/bin:$PATH"
export AITASKS_FAKE_AGENT_HOOK="$PROJECT_DIR/.aitask-scripts/aitask_session_hook.sh"
export FAKE_AGENT_HOOK_LOG="$FIXTURE_DIR/hook.log"
export AITASKS_RESTORE_ACK_GRACE=3

tm new-session -d -s A -c "$PROJ" -n home
tm new-session -d -s B -c "$PROJ" -n home
tm new-session -d -s C -c "$OTHER" -n home
tm new-session -d -s -n -c "$PROJ" -n home

# seed <window> [nosession] — a `frozen` record of $PROJ whose pane is gone.
# Prints its id. `nosession` seeds no codeagent session id (cannot resume).
seed() {
    local window="$1" out id nonce
    local -a sess=(--session-id "sess-$window")
    [ "${2:-}" = nosession ] && sess=()
    store upsert --root "$PROJ" --window "$window" --pane "%99999" \
        --pane-pid 999999 "${sess[@]}" --task-id 12 >/dev/null
    id="$(store list --root "$PROJ" | grep "|$window|" | tail -1 | cut -d: -f2 | cut -d'|' -f1)"
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

forget() { store drop "$1" >/dev/null 2>&1 || true; }

reopen() { "$FROZEN_SH" reopen "$@" 2>&1; }

with_seam() { AITASKS_REOPEN_FAIL_AT="$1" "${@:2}"; }

# windows_named <name> — "<session>:<window>" of every window with that name.
windows_named() {
    tm list-windows -a -F '#{session_name}:#{window_name}' | grep -x -- ".*:$1" || true
}
attempt_windows() {
    tm list-windows -a -F '#{window_name}' | grep -c '^aitask-reopen-' || true
}
lease_free() {
    local out
    out="$(store lease-take "$1" --owner-pid $$ 2>&1)" || return 1
    store lease-release "$1" --nonce "${out##*|}" >/dev/null 2>&1
}

# --- a ------------------------------------------------------------------------
section "a: happy path"
id="$(seed agent-a)"
out="$(reopen --root "$PROJ" --session A)"
assert_contains "a: reopened fresh under the recorded name in A" \
    "REOPENED:$id|fresh|A:agent-a|" "$out"
pane="$(record_field "$id" pane_id)"
assert_eq "a: the new pane carries the stamp" "$id" "$(pane_fmt "$pane" '#{@aitask_frozen}')"
assert_eq "a: its window is exactly the recorded name" "agent-a" "$(pane_fmt "$pane" '#{window_name}')"
assert_eq "a: it lives in A" "A" "$(pane_fmt "$pane" '#{session_name}')"
assert_eq "a: the record's pid is the pane's" "$(pane_fmt "$pane" '#{pane_pid}')" \
    "$(record_field "$id" pane_pid)"
assert_eq "a: still frozen" "frozen" "$(record_field "$id" state)"
assert_eq "a: no lease left" "" "$(record_field "$id" op_nonce)"
assert_eq "a: no attempt-named window remains" "0" "$(attempt_windows)"
out="$(reopen --root "$PROJ" --session A)"
assert_contains "a: a second run has nothing to do" "REOPEN_ALL:0/0" "$out"
assert_contains "a: gone lists nothing" "GONE_COUNT:0" "$("$FROZEN_SH" gone --root "$PROJ")"

# --- b ------------------------------------------------------------------------
section "b: drop from the recreated pane"
out="$("$FROZEN_SH" drop "$id" 2>&1)"
assert_contains "b: drop succeeds" "DROPPED:$id" "$out"
assert_eq "b: the stand-in is gone" "no" "$(pane_exists "$pane" && echo yes || echo no)"

# --- c ------------------------------------------------------------------------
section "c: two sessions of one project"
id="$(seed agent-c)"
out="$(reopen "$id" --session B)"
assert_contains "c: lands in B" "REOPENED:$id|fresh|B:agent-c|" "$out"
assert_eq "c: exactly one agent-c window, in B" "B:agent-c" "$(windows_named agent-c)"
forget "$id"
id="$(seed agent-c2)"
before="$(tm list-windows -a | wc -l)"
out="$(reopen "$id" --session C)"
assert_contains "c: a session of another project fails closed" \
    "REOPEN_FAILED:$id|session_not_for_root:C" "$out"
assert_eq "c: no window was created anywhere" "$before" "$(tm list-windows -a | wc -l)"
assert_eq "c: the lease was released" "0" "$(lease_free "$id"; echo $?)"
forget "$id"

# --- c2 -----------------------------------------------------------------------
section "c2: a same-named window cannot authorize another project's session"
# A (this project) holds a window named like C, the OTHER project's session.
tm new-window -d -t "=A:" -n C
sock="$(tm display-message -p -t "=A:home" '#{socket_path}')"
spid="$(tm display-message -p -t "=A:home" '#{pid}')"
apane="$(tm display-message -p -t "=A:home" '#{pane_id}')"
# Run as a client whose CURRENT session is A — where `ait ide` runs its offer.
in_a() { TMUX="$sock,$spid,0" TMUX_PANE="$apane" "$@"; }
seen="$(in_a "$REAL_TMUX" list-panes -s -t "=C" -F '#{session_name}' | sort -u)"
assert_eq "c2: precondition — from A, a bare =C lists A's panes (the t1874 shape)" "A" "$seen"
seen="$(in_a "$REAL_TMUX" list-panes -s -t "=C:" -F '#{session_name}' | sort -u)"
assert_eq "c2: from A, the scoped =C: lists C's panes" "C" "$seen"
id="$(seed agent-c3)"
before="$(tm list-windows -a | wc -l)"
out="$(in_a "$FROZEN_SH" reopen "$id" --session C 2>&1)"
assert_contains "c2: reopen into the foreign session fails closed" \
    "REOPEN_FAILED:$id|session_not_for_root:C" "$out"
out="$(in_a "$FROZEN_SH" restore "$id" --session C 2>&1)"
assert_contains "c2: restore into the foreign session fails closed" \
    "session_not_for_root:C" "$out"
assert_eq "c2: no window was created anywhere" "$before" "$(tm list-windows -a | wc -l)"
assert_eq "c2: still frozen" "frozen" "$(record_field "$id" state)"
forget "$id"
tm kill-window -t "=A:C"

# --- c3 -----------------------------------------------------------------------
section "c3: a same-named window does not break a VALID same-root restore"
# A holds a window named B; B is this project's own second session. From a
# client in A, a bare =B reads A — the launch lands in B, and the pane lookup
# by pid must still find it there.
tm new-window -d -t "=A:" -n B
seen="$(in_a "$REAL_TMUX" list-panes -s -t "=B" -F '#{session_name}' | sort -u)"
assert_eq "c3: precondition — from A, a bare =B lists A's panes" "A" "$seen"
seen="$(in_a "$REAL_TMUX" list-panes -s -t "=B:" -F '#{session_name}' | sort -u)"
assert_eq "c3: from A, the scoped =B: lists B's panes" "B" "$seen"
id="$(seed agent-c4)"
out="$(in_a "$FROZEN_SH" restore "$id" --session B 2>&1)"
assert_contains "c3: the restore succeeds" "RESTORED:$id|" "$out"
assert_not_contains "c3: the launched pane was found" "launched_pane_unresolvable" "$out"
assert_eq "c3: the agent's window is in B" "B:agent-c4" "$(windows_named agent-c4)"
assert_eq "c3: the record is live" "live" "$(record_field "$id" state)"
assert_eq "c3: the record names the launched pane" \
    "$(tm list-panes -t "=B:agent-c4" -F '#{pane_id}' | head -1)" "$(record_field "$id" pane_id)"
forget "$id"
id="$(seed agent-c5)"
out="$(in_a "$FROZEN_SH" reopen "$id" --session B 2>&1)"
assert_contains "c3: reopen into B from A succeeds too" "REOPENED:$id|fresh|B:agent-c5|" "$out"
forget "$id"
tm kill-window -t "=A:B"

# --- d ------------------------------------------------------------------------
section "d: stamp failure"
id="$(seed agent-d)"
out="$(with_seam stamp reopen "$id" --session A)"
assert_eq "d: reported" "REOPEN_FAILED:$id|stamp" "$out"
assert_eq "d: no attempt window survives" "0" "$(attempt_windows)"
assert_eq "d: record untouched (pane)" "" "$(record_field "$id" pane_id)"
assert_eq "d: record untouched (state)" "frozen" "$(record_field "$id" state)"
assert_eq "d: no lease held" "0" "$(lease_free "$id"; echo $?)"
forget "$id"

# --- e ------------------------------------------------------------------------
section "e: lost -P output"
id="$(seed agent-e)"
out="$(with_seam identify reopen "$id" --session A)"
assert_contains "e: identified by name" "REOPENED:$id|fresh|A:agent-e|" "$out"
forget "$id"
id="$(seed agent-e2)"
out="$(with_seam identify,stamp reopen "$id" --session A)"
assert_eq "e: with a stamp failure, reported" "REOPEN_FAILED:$id|stamp" "$out"
assert_eq "e: and nothing survives" "0" "$(attempt_windows)"
forget "$id"

# --- f ------------------------------------------------------------------------
section "f: store failure"
id="$(seed agent-f)"
out="$(with_seam store reopen "$id" --session A)"
assert_contains "f: reported" "REOPEN_FAILED:$id|store:" "$out"
assert_eq "f: nothing survives" "" "$(windows_named agent-f)"
assert_eq "f: record untouched" "" "$(record_field "$id" pane_id)"
out="$(with_seam store,cleanup reopen "$id" --session A)"
assert_contains "f: a failed cleanup is reported" "|cleanup:present:seam|pane:" "$out"
survivor="${out##*|pane:}"
assert_contains_re "f: the survivor pane is named in the line" '^%[0-9]+$' "$survivor"
assert_eq "f: the survivor keeps its stamp" "$id" "$(pane_fmt "$survivor" '#{@aitask_frozen}')"
assert_eq "f: and already carries the final name" "agent-f" "$(pane_fmt "$survivor" '#{window_name}')"
assert_contains "f: gone lists it as stranded" "GONE:$id|stranded|" \
    "$("$FROZEN_SH" gone --root "$PROJ")"
out="$(reopen "$id" --session A)"
assert_eq "f: the next run adopts it" "REOPENED:$id|adopted|A:agent-f|$survivor" "$out"
assert_eq "f: one window, no suffix" "A:agent-f" "$(windows_named agent-f)"
assert_eq "f: the record tracks it" "$survivor" "$(record_field "$id" pane_id)"
forget "$id"

# --- f2 -----------------------------------------------------------------------
section "f2: a suffix is stable across adoption"
tm new-window -d -t "=A:" -n agent-g
id="$(seed agent-g)"
out="$(with_seam store,cleanup reopen "$id" --session A)"
survivor="${out##*|pane:}"
assert_eq "f2: the survivor took -2" "agent-g-2" "$(pane_fmt "$survivor" '#{window_name}')"
out="$(reopen "$id" --session A)"
assert_contains "f2: adopted under -2" "|adopted|A:agent-g-2|" "$out"
assert_eq "f2: no -3 appeared" "" "$(windows_named agent-g-3)"
forget "$id"

# --- g ------------------------------------------------------------------------
section "g: a stranded viewer in another session moves to the selected one"
id="$(seed agent-h1)"
out="$(with_seam store,cleanup reopen "$id" --session A)"
survivor="${out##*|pane:}"
assert_eq "g: the survivor starts in A" "A" "$(pane_fmt "$survivor" '#{session_name}')"
out="$(reopen "$id" --session B)"
assert_contains "g: adopted into B" "REOPENED:$id|adopted|B:agent-h1|$survivor" "$out"
assert_eq "g: the pane now lives in B" "B" "$(pane_fmt "$survivor" '#{session_name}')"
forget "$id"

# --- h ------------------------------------------------------------------------
section "h: uncertain launch, retry before the viewer self-stamps"
id="$(seed agent-i)"
out="$(AITASKS_FROZEN_STANDIN_CMD='sleep 600' with_seam launch_uncertain reopen "$id" --session A)"
assert_contains "h: an uncertain rc with the window present continues" \
    "REOPENED:$id|fresh|A:agent-i|" "$out"
forget "$id"
id="$(seed agent-j)"
out="$(AITASKS_FROZEN_STANDIN_CMD='sleep 600' with_seam launch_uncertain,lookup \
    reopen "$id" --session A)"
assert_eq "h: an unresolvable launch is reported uncertain" \
    "REOPEN_FAILED:$id|launch:uncertain" "$out"
assert_eq "h: the lease was released" "0" "$(lease_free "$id"; echo $?)"
orphan="$(tm list-panes -a -F '#{window_name} #{pane_id}' | awk -v n="aitask-reopen-$id-" 'index($1, n) == 1 {print $2}')"
assert_contains_re "h: the orphan window exists" '^%[0-9]+$' "$orphan"
assert_eq "h: the orphan is claimed only by its name" "" \
    "$(pane_fmt "$orphan" '#{@aitask_frozen}#{@aitask_standin_ready}')"
assert_contains "h: gone lists it as stranded" "GONE:$id|stranded|" \
    "$("$FROZEN_SH" gone --root "$PROJ")"
out="$(reopen "$id" --session A)"
assert_eq "h: the retry adopts it" "REOPENED:$id|adopted|A:agent-j|$orphan" "$out"
assert_eq "h: exactly one window for the record" "A:agent-j" "$(windows_named agent-j)"
assert_eq "h: now stamped" "$id" "$(pane_fmt "$orphan" '#{@aitask_frozen}')"
assert_eq "h: and no attempt window remains" "0" "$(attempt_windows)"
forget "$id"

# --- i ------------------------------------------------------------------------
section "i: rename failure"
id="$(seed agent-k)"
out="$(with_seam rename reopen "$id" --session A)"
assert_eq "i: a fresh window is reported" "REOPEN_FAILED:$id|rename" "$out"
assert_eq "i: and removed" "0" "$(attempt_windows)"
out="$(AITASKS_FROZEN_STANDIN_CMD='sleep 600' with_seam launch_uncertain,lookup \
    reopen "$id" --session A)"
orphan="$(tm list-panes -a -F '#{window_name} #{pane_id}' | awk -v n="aitask-reopen-$id-" 'index($1, n) == 1 {print $2}')"
assert_contains_re "i: the adoption candidate exists" '^%[0-9]+$' "$orphan"
out="$(with_seam rename reopen "$id" --session A)"
assert_eq "i: an adoption rename failure is reported" \
    "REOPEN_FAILED:$id|adopt:rename|pane:$orphan" "$out"
assert_eq "i: the adopted window is kept" "yes" "$(pane_exists "$orphan" && echo yes || echo no)"
assert_eq "i: the record is not committed" "" "$(record_field "$id" pane_id)"
out="$(reopen "$id" --session A)"
assert_eq "i: the next run finishes it" "REOPENED:$id|adopted|A:agent-k|$orphan" "$out"
forget "$id"

# --- j ------------------------------------------------------------------------
section "j: an option-like session"
id="$(seed agent-l)"
out="$(reopen "$id" --session -n)"
assert_contains "j: lands in the session named -n" "REOPENED:$id|fresh|-n:agent-l|" "$out"
assert_eq "j: exactly there" "-n:agent-l" "$(windows_named agent-l)"
forget "$id"

# --- k ------------------------------------------------------------------------
section "k: a gone-pane restore lands in the selected session"
id="$(seed agent-m)"
out="$("$FROZEN_SH" restore "$id" --session B 2>&1)"
assert_contains "k: restored" "RESTORED:$id|" "$out"
assert_eq "k: the agent's window is in B only" "B:agent-m" "$(windows_named agent-m)"
assert_eq "k: the record is live" "live" "$(record_field "$id" state)"
forget "$id"
id="$(seed agent-m2)"
out="$("$FROZEN_SH" restore "$id" --session C 2>&1)"
assert_contains "k: a session of another project fails closed" "session_not_for_root:C" "$out"
assert_eq "k: no window for it anywhere" "" "$(windows_named agent-m2)"
assert_eq "k: still frozen" "frozen" "$(record_field "$id" state)"
forget "$id"

# --- h2 -----------------------------------------------------------------------
section "h2: ait ide's Restore-all over gone and stranded records"
r1="$(seed agent-r1)"                                     # gone, resumable
r2="$(seed agent-r2)"                                     # stranded in A
out="$(with_seam store,cleanup reopen "$r2" --session A)"
s2="${out##*|pane:}"
r3="$(seed agent-r3 nosession)"                           # cannot resume
r4="$(seed agent-r4)"                                     # stranded in B, move fails
out="$(with_seam store,cleanup reopen "$r4" --session B)"
s4="${out##*|pane:}"
assert_contains_re "h2: the A survivor exists" '^%[0-9]+$' "$s2"
assert_contains_re "h2: the B survivor exists" '^%[0-9]+$' "$s4"
. "$PROJECT_DIR/.aitask-scripts/lib/ide_frozen_offer.sh"
out="$(printf 'R\n' | AIT_IDE_FROZEN_ASSUME_TTY=1 AITASKS_REOPEN_FAIL_AT=move \
    ide_offer_frozen_agents "$PROJ" A "$FROZEN_SH" 2>&1)"
assert_eq "h2: r1 was restored" "live" "$(record_field "$r1" state)"
assert_eq "h2: r1's agent runs in its recreated viewer window, in A" "A:agent-r1" \
    "$(windows_named agent-r1)"
assert_eq "h2: r2 was restored" "live" "$(record_field "$r2" state)"
assert_eq "h2: r2's agent runs in the adopted survivor pane" "$s2" "$(record_field "$r2" pane_id)"
assert_eq "h2: r3 stays frozen" "frozen" "$(record_field "$r3" state)"
p3="$(record_field "$r3" pane_id)"
assert_eq "h2: r3 is a tracked viewer" "$r3" "$(pane_fmt "$p3" '#{@aitask_frozen}')"
assert_contains "h2: r4 is reported, not restored" "agent-r4: viewer open but not tracked" "$out"
assert_eq "h2: r4 stays frozen" "frozen" "$(record_field "$r4" state)"
assert_eq "h2: r4 still names no pane" "" "$(record_field "$r4" pane_id)"
assert_eq "h2: r4's viewer is untouched, in B" "B" "$(pane_fmt "$s4" '#{session_name}')"
assert_eq "h2: no agent window appeared for r4 in A" "" \
    "$(tm list-windows -t "=A:" -F '#{window_name}' | grep -x agent-r4 || true)"
assert_contains "h2: the summary" "Restored 2, viewers 1, failed 0, skipped 1." "$out"
for r in "$r1" "$r2" "$r3" "$r4"; do forget "$r"; done

# --- m ------------------------------------------------------------------------
# A gone-pane restore never leaves its agent untracked (t1875). The fake agent
# reads its knobs from the SERVER's global environment, which is what a new
# window inherits: `set-environment -g` scopes each case, and `-gu` undoes it.
restore_() { "$FROZEN_SH" restore "$@" 2>&1; }
rseam() { AITASKS_RESTORE_FAIL_AT="$1" "${@:2}"; }
restore_attempts() {
    tm list-windows -a -F '#{window_name}' | grep -c "^aitask-restore-$1-" || true
}
all_windows() { tm list-windows -a | wc -l; }
agent_env_g() { tm set-environment -g "$1" "$2"; }
agent_env_gu() { tm set-environment -gu "$1" 2>/dev/null || true; }
kill_pane_window() { tm kill-window -t "$1" 2>/dev/null || true; }

section "m1: a session mismatch rolls the stand-in back INTO the new window"
id="$(seed agent-m1)"
agent_env_g FAKE_AGENT_SESSION sess-wrong
out="$(restore_ "$id" --session A)"
agent_env_gu FAKE_AGENT_SESSION
assert_contains "m1: reported as a mismatch" "RESTORE_FAILED:$id|" "$out"
assert_eq "m1: the record is frozen" "frozen" "$(record_field "$id" state)"
pane="$(record_field "$id" pane_id)"
assert_contains_re "m1: the record tracks a pane (not the gone-pane pair)" '^%[0-9]+$' "$pane"
assert_eq "m1: ...the new window's" "A:agent-m1" "$(windows_named agent-m1)"
assert_eq "m1: that pane is the record's stand-in" "$id" "$(pane_fmt "$pane" '#{@aitask_frozen}')"
wait_for_ready "$pane" "$id" || true
assert_eq "m1: the stand-in mounted in it" "$id" "$(pane_fmt "$pane" '#{@aitask_standin_ready}')"
assert_eq "m1: the attempt mark is retired" "" "$(pane_fmt "$pane" '#{@aitask_restore_attempt}')"
assert_eq "m1: no agent window is left behind" "0" "$(restore_attempts "$id")"
forget "$id"; kill_pane_window "$pane"

section "m2: lost -P output — identified by the attempt name and recorded"
id="$(seed agent-m2)"
out="$(rseam identify restore_ "$id" --session A)"
assert_contains "m2: restored" "RESTORED:$id|" "$out"
assert_eq "m2: live" "live" "$(record_field "$id" state)"
pane="$(record_field "$id" pane_id)"
assert_eq "m2: one window, under its final name" "A:agent-m2" "$(windows_named agent-m2)"
assert_eq "m2: the mark is retired on success" "" "$(pane_fmt "$pane" '#{@aitask_restore_attempt}')"
assert_eq "m2: and the stamp" "" "$(pane_fmt "$pane" '#{@aitask_frozen}')"
forget "$id"; kill_pane_window "$pane"

section "m3: an uncertain rc after the server acted — recorded, not duplicated"
id="$(seed agent-m3)"
out="$(rseam launch_uncertain restore_ "$id" --session A)"
assert_contains "m3: restored" "RESTORED:$id|" "$out"
assert_eq "m3: exactly one window" "A:agent-m3" "$(windows_named agent-m3)"
pane="$(record_field "$id" pane_id)"
forget "$id"; kill_pane_window "$pane"

# From here the agent never acks: a hook that won the race would settle the
# record `live` and hide exactly the untracked-survivor states under test.
agent_env_g FAKE_AGENT_NO_HOOK 1

section "m4: a stamp that does not take — the window is removed"
id="$(seed agent-m4)"
before="$(all_windows)"
out="$(rseam identify,stamp restore_ "$id" --session A)"
assert_contains "m4: reported" "RESTORE_FAILED:$id|respawn:stamp" "$out"
assert_eq "m4: no window survives" "$before" "$(all_windows)"
assert_eq "m4: the record is frozen" "frozen" "$(record_field "$id" state)"
forget "$id"

section "m5: an unanswerable launch names its attempt; a retry refuses to duplicate"
id="$(seed agent-m5)"
out="$(rseam identify,lookup restore_ "$id" --session A)"
assert_contains "m5: the failure names the attempt window" \
    "launch_uncertain:aitask-restore-$id-" "$out"
assert_eq "m5: the record is frozen" "frozen" "$(record_field "$id" state)"
assert_eq "m5: the survivor is identifiable by its name" "1" "$(restore_attempts "$id")"
surv="$(tm list-panes -a -F '#{window_name} #{pane_id}' | awk -v n="aitask-restore-$id-" 'index($1, n) == 1 {print $2}')"
spid="$(pane_fmt "$surv" '#{pane_pid}')"
before="$(all_windows)"
out="$(restore_ "$id" --session A)"
assert_contains "m5: the retry is refused" "RESTORE_FAILED:$id|restore_survivor:A:aitask-restore-$id-" "$out"
assert_contains "m5: naming the pane" "|pane:$surv" "$out"
assert_eq "m5: no second agent" "$before" "$(all_windows)"
assert_contains "m5: gone lists it as a survivor" "GONE:$id|survivor|" \
    "$("$FROZEN_SH" gone --root "$PROJ")"
out="$(reopen "$id" --session A)"
assert_contains "m5: reopen refuses it" "REOPEN_FAILED:$id|restore_survivor:" "$out"
assert_eq "m5: and creates no viewer beside it" "$before" "$(all_windows)"
assert_eq "m5: the survivor is untouched" "$spid" "$(pane_fmt "$surv" '#{pane_pid}')"
kill_pane_window "$surv"
agent_env_gu FAKE_AGENT_NO_HOOK
out="$(restore_ "$id" --session A)"
assert_contains "m5: once it is closed, the retry restores" "RESTORED:$id|" "$out"
pane="$(record_field "$id" pane_id)"
forget "$id"; kill_pane_window "$pane"
agent_env_g FAKE_AGENT_NO_HOOK 1

section "m6: the crash end state — a stamped, marked, renamed survivor"
id="$(seed agent-m6)"
out="$(rseam abandon restore_ "$id" --session A)"
assert_contains "m6: the attempt was abandoned" "RESTORE_FAILED:$id|respawn:abandon" "$out"
assert_eq "m6: the record is frozen on a gone pane" "" "$(record_field "$id" pane_id)"
surv="$(tm list-panes -t "=A:agent-m6" -F '#{pane_id}' | head -1)"
spid="$(pane_fmt "$surv" '#{pane_pid}')"
assert_eq "m6: the survivor carries the stamp" "$id" "$(pane_fmt "$surv" '#{@aitask_frozen}')"
assert_contains "m6: ...and the attempt mark" "$id:" "$(pane_fmt "$surv" '#{@aitask_restore_attempt}')"
out="$(reopen "$id" --session A)"
assert_contains "m6: reopen does NOT adopt it as a viewer" "REOPEN_FAILED:$id|restore_survivor:A:agent-m6|pane:$surv" "$out"
assert_eq "m6: the record still names no pane" "" "$(record_field "$id" pane_id)"
assert_eq "m6: the agent still runs" "$spid" "$(pane_fmt "$surv" '#{pane_pid}')"
out="$(restore_ "$id" --session A)"
assert_contains "m6: restore refuses it" "restore_survivor:A:agent-m6" "$out"
out="$(printf 'R\n' | AIT_IDE_FROZEN_ASSUME_TTY=1 ide_offer_frozen_agents "$PROJ" A "$FROZEN_SH" 2>&1)"
assert_contains "m6: ait ide marks it" "an earlier restore's agent is still running, untracked" "$out"
assert_contains "m6: and R skips it" "agent-m6: an earlier restore's agent is still running" "$out"
assert_eq "m6: still frozen" "frozen" "$(record_field "$id" state)"
out="$("$FROZEN_SH" drop "$id" 2>&1)"
assert_contains "m6: drop refuses it" "DROP_REFUSED:$id|restore_survivor:A:agent-m6|pane:$surv" "$out"
assert_eq "m6: the record survives" "frozen" "$(record_field "$id" state)"
assert_eq "m6: and its capture" "yes" "$([ -d "$AITASKS_FROZEN_DIR/$id" ] && echo yes || echo no)"
assert_eq "m6: the agent was not killed" "$spid" "$(pane_fmt "$surv" '#{pane_pid}')"

section "m7: a survivor holding the record's own pane id"
# The state a pane-id reuse after a server restart produces: the record names
# exactly the survivor's `%N`, which is stamped like the stand-in.
lease="$(store lease-take "$id" --owner-pid $$)"
store standin-respawned "$id" --nonce "${lease##*|}" --pane "$surv" --pane-pid "$spid" >/dev/null
assert_eq "m7: precondition — the record names the survivor" "$surv" "$(record_field "$id" pane_id)"
out="$(restore_ "$id" --session A)"
assert_contains "m7: restore refuses it" "RESTORE_FAILED:$id|restore_survivor:A:agent-m6|pane:$surv" "$out"
assert_eq "m7: it was NOT respawned as a stand-in" "$spid" "$(pane_fmt "$surv" '#{pane_pid}')"
out="$(reopen "$id" --session A)"
assert_contains "m7: reopen refuses it" "REOPEN_FAILED:$id|restore_survivor:" "$out"
assert_not_contains "m7: never read as the tracked viewer" "pane_present" "$out"
out="$("$FROZEN_SH" drop "$id" 2>&1)"
assert_contains "m7: drop refuses it" "DROP_REFUSED:$id|restore_survivor:" "$out"
assert_eq "m7: the agent was not killed" "$spid" "$(pane_fmt "$surv" '#{pane_pid}')"
assert_eq "m7: the record survives" "frozen" "$(record_field "$id" state)"
kill_pane_window "$surv"
out="$("$FROZEN_SH" drop "$id" 2>&1)"
assert_contains "m7: once it is closed, drop works" "DROPPED:$id" "$out"
agent_env_gu FAKE_AGENT_NO_HOOK

assert_counters_load
echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]] || exit 1
echo "ALL TESTS PASSED"
