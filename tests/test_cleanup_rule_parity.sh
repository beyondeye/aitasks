#!/usr/bin/env bash
# tests/test_cleanup_rule_parity.sh — the t1705_4 post-phase risk mitigation.
#
# The "does this window still hold a real agent?" rule exists TWICE:
#
#   * `aitask_companion_cleanup.sh`  (bash, runs as a tmux `pane-died` job)
#   * `monitor_core.kill_agent_pane_smart` / `count_other_real_agents` (Python)
#
# They are not shared code and cannot easily be: the hook runs as a tmux server
# job with raw, un-flagged `tmux` calls, and the monitor runs inside a TUI
# process. So the standing risk is a frozen-aware change landing in one and not
# the other — and the failure mode is destructive: a window still holding a LIVE
# agent, or a frozen stand-in (the only route back to a suspended session), gets
# killed.
#
# This file drives ONE pane table through BOTH implementations and asserts they
# reach the same verdict on every row. Verdicts:
#
#   window   — no real agent sibling remains, so the companions go too and the
#              window collapses
#   pane     — a real sibling remains; only the dying/target pane goes
#   abstain  — (bash only) the DYING pane is a frozen stand-in being respawned,
#              so the script must kill nothing at all
#
# `abstain` has no Python counterpart by design: `kill_agent_pane_smart` is a
# user action ("kill this agent"), never a departure notification, so there is
# nothing for it to abstain from. Those rows assert the bash side alone and say
# so.
#
# WHY EVERY PARITY ROW CARRIES A COMPANION PANE. The bash script never calls
# `kill-window`; it kills the companions and then the primary, and tmux closes
# the window when the last pane goes. With no companion in the window its kill
# set is IDENTICAL whether `others` is 0 or not, so the decision is
# unobservable. A companion pane is what makes the verdict readable, which is
# why it is part of the fixture rather than an afterthought.
#
# HOW THE BASH SIDE IS OBSERVED: a logging `tmux` wrapper first on PATH.
# `aitask_companion_cleanup.sh` calls raw `tmux` BY DESIGN (it relies on the
# firing server's `$TMUX`), so the wrapper is the only way to read its kill
# decision without destroying the fixture — and it forwards every other
# subcommand to the real binary, so the script's own `list-panes` reads are real.
#
# TMUX-STRESS. Run from a shell that is NOT inside tmux, with the dedicated
# `-L ait` server stopped; `require_clean_ait_server` refuses otherwise.
#
# Run: bash tests/test_cleanup_rule_parity.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

command -v tmux >/dev/null 2>&1 || { echo "SKIP: tmux not available"; exit 0; }

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# Table rows run inside ( … ) subshells, whose in-process PASS/FAIL increments
# die at subshell exit. Without the file-backed counters this file would report
# zero failures and exit 0 no matter what failed (CLAUDE.md, t1207).
assert_counters_init

# shellcheck source=lib/tmux_isolation.sh
. "$PROJECT_DIR/tests/lib/tmux_isolation.sh"
require_clean_ait_server     # FIRST — reads $TMUX and the real `-L ait` socket
require_isolated_tmux        # SECOND

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
. "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
PYTHON_BIN="$(require_ait_python)"

REAL_PATH="$PATH"
REAL_TMUX="$(command -v tmux)"
FIXTURE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/ait_cleanup_parity_XXXXXX")"
export TMUX_TMPDIR="$FIXTURE_DIR"
SESSION="ait_parity_$$"
KILL_LOG="$FIXTURE_DIR/kills.log"

cleanup() {
    PATH="$REAL_PATH" "$REAL_TMUX" kill-server 2>/dev/null || true
    rm -rf "$FIXTURE_DIR" 2>/dev/null || true
}
trap cleanup EXIT

# --- the logging tmux wrapper ------------------------------------------------
#
# Logs `kill-pane` / `kill-window` and SWALLOWS them (the fixture must survive
# the row); forwards everything else to the real binary.
mkdir -p "$FIXTURE_DIR/bin"
cat > "$FIXTURE_DIR/bin/tmux" <<WRAPPER
#!/usr/bin/env bash
case "\$1" in
    kill-pane|kill-window)
        printf '%s\n' "\$*" >> "$KILL_LOG"
        exit 0
        ;;
esac
exec "$REAL_TMUX" "\$@"
WRAPPER
chmod +x "$FIXTURE_DIR/bin/tmux"

# --- fixture builders --------------------------------------------------------

new_window() {
    "$REAL_TMUX" new-window -d -t "=$SESSION" -n "$1" -P -F '#{pane_id}' "sleep 1000"
}
split_into() {
    "$REAL_TMUX" split-window -d -t "$1" -P -F '#{pane_id}' "sleep 1000"
}
stamp() { "$REAL_TMUX" set-option -p -t "$1" "$2" "$3"; }
window_index_of() { "$REAL_TMUX" display-message -p -t "$1" '#{window_index}'; }

# Build one window from a role list; echo the pane ids in role order. Roles:
#   agent      no markers                                  -> real agent
#   frozen     `@aitask_frozen` stamped                    -> real agent (t1705_4)
#   companion  `@aitask_monitor_kind=minimonitor:<pid>`    -> helper
#   shadow     `@aitask_shadow_target=<first pane>`        -> helper
#   dead       process exited under `remain-on-exit`
build_window() {
    local window="$1"; shift
    local roles=("$@")
    local first="" ids=() pane pid
    for role in "${roles[@]}"; do
        if [ -z "$first" ]; then
            pane="$(new_window "$window")"
            first="$pane"
        else
            pane="$(split_into "$first")"
        fi
        case "$role" in
            frozen)
                stamp "$pane" @aitask_frozen 7f3a2c1d ;;
            frozen_marked)
                # A stand-in that ALSO carries a live companion marker — the
                # residue a `respawn-pane` leaves behind, since pane options are
                # pane-scoped and survive the process swap. This is the ONLY
                # shape where the "counts as real" half of the rule is
                # load-bearing: on a bare `frozen` pane it holds incidentally
                # (no helper marker of any kind), so a row built from one cannot
                # tell a correct implementation from a missing rule.
                stamp "$pane" @aitask_frozen 7f3a2c1d
                pid="$("$REAL_TMUX" display-message -p -t "$pane" '#{pane_pid}')"
                stamp "$pane" @aitask_monitor_kind "minimonitor:$pid" ;;
            companion)
                pid="$("$REAL_TMUX" display-message -p -t "$pane" '#{pane_pid}')"
                stamp "$pane" @aitask_monitor_kind "minimonitor:$pid" ;;
            shadow)
                stamp "$pane" @aitask_shadow_target "$first" ;;
            dead)
                "$REAL_TMUX" set-option -p -t "$pane" remain-on-exit on
                "$REAL_TMUX" respawn-pane -k -t "$pane" "true"
                sleep 0.3 ;;
            agent) : ;;
        esac
        ids+=("$pane")
    done
    printf '%s\n' "${ids[@]}"
}

# --- the two implementations -------------------------------------------------

# The bash verdict for "pane $1 died; $2 is the hook's companion argument".
#
# window  <- the companion pane was killed (the `others == 0` branch)
# pane    <- only the primary (and any shadow bound to it, from job 1) was killed
# abstain <- nothing was killed at all (rule a)
bash_verdict() {
    local dying="$1" companion="$2"
    : > "$KILL_LOG"
    PATH="$FIXTURE_DIR/bin:$REAL_PATH" \
        "$PROJECT_DIR/.aitask-scripts/aitask_companion_cleanup.sh" \
        "$dying" "$companion" >/dev/null 2>&1 || true
    if [ ! -s "$KILL_LOG" ]; then
        echo "abstain"
    elif grep -qF -- "$companion" "$KILL_LOG"; then
        echo "window"
    else
        echo "pane"
    fi
}

# The Python verdict for "kill pane $1 (window index $2)". Drives the REAL
# `kill_agent_pane_smart` against the REAL window with only the kills and the
# store `drop` stubbed. Prints the verdict on line 1 and the dropped record ids
# on line 2.
python_verdict() {
    local target="$1" window_index="$2"
    PYTHONPATH="$PROJECT_DIR/.aitask-scripts:$PROJECT_DIR/.aitask-scripts/lib" \
    AIT_PARITY_SESSION="$SESSION" \
    AIT_PARITY_TARGET="$target" \
    AIT_PARITY_WINDEX="$window_index" \
    AITASKS_TMUX_SOCKET="" \
    TMUX_TMPDIR="$FIXTURE_DIR" \
    "$PYTHON_BIN" - <<'PYEOF'
import os

from monitor.monitor_core import PaneCategory, TmuxMonitor, TmuxPaneInfo

session = os.environ["AIT_PARITY_SESSION"]
target = os.environ["AIT_PARITY_TARGET"]
windex = os.environ["AIT_PARITY_WINDEX"]

mon = TmuxMonitor(session=session, multi_session=False, exclude_pane="")

# Seed the cache the way discovery would. The target's own `frozen_record` is
# what drives the drop-then-kill branch, so it is read from the real pane rather
# than assumed.
rc, out = mon.tmux_run(
    ["display-message", "-p", "-t", target, "#{pane_pid}\t#{@aitask_frozen}"]
)
pane_pid, frozen = 0, ""
if rc == 0 and out.strip():
    parts = out.splitlines()[0].split("\t")
    try:
        pane_pid = int(parts[0])
    except (ValueError, IndexError):
        pane_pid = 0
    frozen = parts[1].strip() if len(parts) > 1 else ""

mon._pane_cache[target] = TmuxPaneInfo(
    window_index=windex, window_name="parity", pane_index="0",
    pane_id=target, pane_pid=pane_pid, current_command="sleep",
    width=80, height=24, category=PaneCategory.AGENT,
    session_name=session, frozen_record=frozen,
)

verdict = []
dropped = []
mon.kill_window = lambda pid_: (verdict.append("window"), True)[1]
mon.kill_pane = lambda pid_: (verdict.append("pane"), True)[1]
# The store is not under test here; a real `drop` would need the wrapper and a
# store file. Recorded so the row can assert the call separately.
mon._drop_session_record = lambda rid: (dropped.append(rid), True)[1]

mon.kill_agent_pane_smart(target)
print(verdict[0] if verdict else "none")
print(",".join(dropped))
PYEOF
}

# --- the table ---------------------------------------------------------------

"$REAL_TMUX" new-session -d -s "$SESSION" -n scratch "sleep 1000"
sleep 0.3

ROW_N=0

# row <name> <expected verdict> <index of the dying pane> <roles...>
row() {
    local name="$1" expect="$2" dying_index="$3"; shift 3
    local roles=("$@")
    ROW_N=$((ROW_N + 1))
    (
        local window="parity_$ROW_N"
        local ids=() line
        while IFS= read -r line; do ids+=("$line"); done \
            < <(build_window "$window" "${roles[@]}")
        sleep 0.2

        local dying="${ids[$dying_index]}"

        # The hook's companion argument: the companion-role pane when the row
        # has one, else a pane id that is NOT in this window. The out-of-window
        # value is deliberate — it disables the pre-marker `$pane = $companion`
        # fallback so the classification under test is the MARKER path alone.
        local companion="%99999" i=0
        for r in "${roles[@]}"; do
            if [ "$r" = "companion" ]; then companion="${ids[$i]}"; break; fi
            i=$((i + 1))
        done

        local bash_got python_out python_got
        bash_got="$(bash_verdict "$dying" "$companion")"

        if [ "$expect" = "abstain" ]; then
            # Bash-only row: kill_agent_pane_smart has no abstain verdict.
            assert_eq "$name [bash abstains]" "abstain" "$bash_got"
            assert_eq "$name [nothing was killed]" "" "$(cat "$KILL_LOG")"
        else
            python_out="$(python_verdict "$dying" "$(window_index_of "$dying")")"
            python_got="$(printf '%s' "$python_out" | head -n1)"
            assert_eq "$name [bash]" "$expect" "$bash_got"
            assert_eq "$name [python]" "$expect" "$python_got"
            assert_eq "$name [PARITY]" "$bash_got" "$python_got"
        fi
    )
}

echo "=== parity table ==="

# A real sibling keeps the window; a lone agent takes it down.
row "agent + companion"                    window 0 agent companion
row "agent + agent + companion"            pane   0 agent agent companion
row "agent + agent + companion, last dies" pane   1 agent agent companion

# t1705_4 rule (b): a frozen stand-in IS a real sibling.
row "agent + frozen + companion"           pane   0 agent frozen companion
row "frozen + agent + companion, last agent dies" pane 1 frozen agent companion

# Helpers are not siblings.
row "agent + shadow + companion"           window 0 agent shadow companion
row "agent + companion + companion"        window 0 agent companion companion

# Two stand-ins beside a live agent: killing the agent leaves them, so the
# window survives.
row "agent + frozen + frozen + companion"  pane   0 agent frozen frozen companion

# THE load-bearing row for rule (b): the stand-in also carries a live companion
# marker. Without the frozen rung being checked FIRST, both sides would demote
# it to a helper and collapse a window that still holds a frozen session.
row "agent + frozen(marked) + companion"   pane   0 agent frozen_marked companion

# A dead pane carries no markers, so BOTH sides count it as a real sibling.
# That is what parity means here: the rule is shared, not independently guessed.
row "agent + dead + companion"             pane   0 agent dead companion

# t1705_4 rule (a): the DYING pane is the stand-in — abstain entirely.
row "frozen dies -> abstain"               abstain 0 frozen agent companion
row "frozen dies last -> abstain"          abstain 2 agent companion frozen

# --- negative control --------------------------------------------------------
#
# Prove the comparison can fail. A copy of the bash script with the
# frozen-sibling rule removed must now DISAGREE with Python on the row that
# depends on it. Without this, two identically broken sides would look green.
echo "=== negative control: the parity comparison is not vacuous ==="
(
    PATCHED="$FIXTURE_DIR/patched_cleanup.sh"
    # shellcheck disable=SC2016  # `$frozen` is matched literally in the source
    sed 's/if \[ -n "\$frozen" \]; then/if false; then/' \
        "$PROJECT_DIR/.aitask-scripts/aitask_companion_cleanup.sh" > "$PATCHED"
    chmod +x "$PATCHED"
    if ! grep -q "if false; then" "$PATCHED"; then
        assert_record_fail
        echo "FAIL: negative control could not patch out the frozen rule — the"
        echo "      source line moved; update the sed above."
    else
        ids=()
        while IFS= read -r line; do ids+=("$line"); done \
            < <(build_window "parity_neg" agent frozen_marked companion)
        sleep 0.2
        : > "$KILL_LOG"
        PATH="$FIXTURE_DIR/bin:$REAL_PATH" "$PATCHED" \
            "${ids[0]}" "${ids[2]}" >/dev/null 2>&1 || true
        patched_verdict="pane"
        grep -qF -- "${ids[2]}" "$KILL_LOG" && patched_verdict="window"

        python_out="$(python_verdict "${ids[0]}" "$(window_index_of "${ids[0]}")")"
        python_got="$(printf '%s' "$python_out" | head -n1)"

        assert_eq "patched bash loses the frozen-sibling rule" \
            "window" "$patched_verdict"
        assert_eq "python still applies it" "pane" "$python_got"
        if [ "$patched_verdict" = "$python_got" ]; then
            assert_record_fail
            echo "FAIL: negative control — the sides agreed while one was patched"
        else
            assert_record_pass
        fi
    fi
)

# --- the drop-then-kill half -------------------------------------------------
echo "=== killing a frozen pane drops its record first ==="
(
    ids=()
    while IFS= read -r line; do ids+=("$line"); done \
        < <(build_window "parity_drop" frozen agent companion)
    sleep 0.2

    python_out="$(python_verdict "${ids[0]}" "$(window_index_of "${ids[0]}")")"
    assert_eq "the target's record id reaches drop" \
        "7f3a2c1d" "$(printf '%s' "$python_out" | sed -n '2p')"

    python_out="$(python_verdict "${ids[1]}" "$(window_index_of "${ids[1]}")")"
    assert_eq "an unstamped target drops nothing" \
        "" "$(printf '%s' "$python_out" | sed -n '2p')"
)

echo ""
echo "=== Summary ==="
assert_counters_load
echo "Passed: $PASS / $TOTAL"
if [[ "$FAIL" -eq 0 ]]; then echo "ALL TESTS PASSED"; else echo "SOME TESTS FAILED ($FAIL)"; fi
[[ "$FAIL" -eq 0 ]]
