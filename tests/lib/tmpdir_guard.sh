#!/usr/bin/env bash
# tests/lib/tmpdir_guard.sh — run a test phase under a private, per-run TMPDIR,
# report whatever it leaves behind, then remove it (t2290).
#
# WHY
#
# /tmp here is a tmpfs with an inode cap, and tests that forget to clean up add
# a directory per run. This guard is the backstop: every `mktemp` that honours
# $TMPDIR lands in one private directory, which is listed and removed at the
# end. The report names the leftovers so their producers can be found and fixed;
# it never changes the exit status (warn-only).
#
# It sees ONLY $TMPDIR. A producer that writes to a hard-coded /tmp path, or to
# TMUX_TMPDIR (tests/lib/tmux_isolation.sh), bypasses it — an empty report is
# not evidence that a run leaked nothing.
#
# API (source this file; do not execute):
#
#   tmpdir_guard_begin <label>   create  ${TMPDIR:-/tmp}/ait_<label>_<pid>_XXXXXX,
#                                export it as TMPDIR, arm EXIT/INT/TERM/HUP.
#                                Returns non-zero (and arms nothing) on failure;
#                                callers warn and run unguarded.
#   tmpdir_guard_run <cmd...>    run one phase in its OWN process group, stdin
#                                from /dev/null; returns the phase's exit status.
#                                Works unguarded too (plain run).
#   tmpdir_guard_end             idempotent: report leftovers, remove the dir,
#                                restore TMPDIR. Call it explicitly before any
#                                final verdict line; the EXIT trap is the
#                                fallback for every other exit.
#
# SIGNALS. A trapped signal is deferred while bash waits on a FOREGROUND child,
# and a non-job-control shell starts background children with SIGINT ignored —
# so a plain foreground run could neither be interrupted promptly nor have INT
# forwarded. tmpdir_guard_run therefore starts the phase under `set -m` (own
# process group) and `wait`s for it. On INT/TERM/HUP the handler sends TERM to
# the whole group (xdist workers, nested test shells included), waits up to 10s
# for it to empty, then KILLs it — and only then does the EXIT trap remove the
# directory, so nothing is still writing into it. Exit status is 128+signal.
#
# NOT COVERED. SIGKILL of the guarding shell runs no handler: its directory
# stays, and its phase's process group may outlive it. tmpdir_guard_begin only
# REPORTS such directories (owner pid gone) and never deletes them — deleting
# safely needs liveness evidence for the orphaned workers, which is out of scope
# here.
#
# The guard directory always lives under the ORIGINAL TMPDIR (default /tmp) and
# never under a path containing `/.claude/`: tests/test_shadow_q_harness.py's
# sandbox refuses any ancestor holding `.claude`.

[[ -n "${_AIT_TMPDIR_GUARD_LOADED:-}" ]] && return 0
_AIT_TMPDIR_GUARD_LOADED=1

_TG_DIR=""            # the guarded directory; "" when no guard is active
_TG_DONE=0            # tmpdir_guard_end already ran
_TG_ORIG_SET=0        # was TMPDIR set before begin?
_TG_ORIG=""           # its value
_TG_CHILD=""          # pid (== pgid) of the running phase, "" between phases

# Report names: at most this many, then "… and K more".
_TG_REPORT_CAP=20

# Entries a phase is EXPECTED to create in TMPDIR, not leaks. They are still
# removed with the directory; they are just not reported.
#   pytest-of-*       pytest's own tmp_path base (it keeps the last 3 by design)
#   ait-test-cwd-*    tests/lib/scratch_cwd.sh's empty read-only scratch cwd,
#                     deliberately ONE reused directory per uid
_tg_expected_entry() {
    case "$1" in
        pytest-of-*|ait-test-cwd-*) return 0 ;;
    esac
    return 1
}

# _tg_prepend_exit_trap <handler> — run <handler> first on EXIT, then whatever
# EXIT trap was already installed; the dying status is restored around it (the
# txn_chain_exit_trap pattern in .aitask-scripts/lib/txn_snapshot.sh).
_tg_prepend_exit_trap() {
    local cur
    cur="$(_tg_trap_word EXIT)"
    eval "trap -- '__tg_rc=\$?; (exit \"\$__tg_rc\") && :; $1; (exit \"\$__tg_rc\") && :; '${cur:-} EXIT"
}

# _tg_trap_word <SIG> — print the action currently trapped for <SIG> as the
# SHELL-QUOTED word `trap -p` emits (e.g. 'cleanup', or 'a'\''b' for a handler
# containing a quote), or nothing when there is no handler or the signal is
# ignored (''). The word is never unquoted: callers splice it next to another
# quoted string and eval the result, so the shell itself joins the pieces and
# any quoting inside the old action survives intact.
#
# `trap -p` names the signal its OWN way — `SIGTERM` for TERM, `EXIT` for EXIT
# — so the name is dropped as the last space-separated token rather than by
# matching the caller's spelling. That is safe because the action word is
# quoted: it always ends in a quote, never in a bare space.
_tg_trap_word() {
    local cur
    cur="$(trap -p "$1")"
    [[ -n "$cur" ]] || return 0
    cur="${cur#trap -- }"
    cur="${cur% *}"
    [[ "$cur" == "''" ]] && return 0
    printf '%s' "$cur"
}

# _tg_append_signal_trap <SIG> <handler> — run any existing handler for <SIG>
# first, then ours (which exits, so it must come last). An ignored signal
# ('') has no handler to keep: ours replaces the ignore — a guarded run must be
# interruptible.
_tg_append_signal_trap() {
    local sig="$1" cur
    cur="$(_tg_trap_word "$sig")"
    if [[ -n "$cur" ]]; then
        eval "trap -- ${cur}'; $2' $sig"
    else
        eval "trap -- '$2' $sig"
    fi
}

# _tg_traps_armed — every guard trap is really installed. A composition that
# failed to eval leaves the old handler in place with no error worth trusting,
# so this checks the RESULT, not the eval's status.
#
# One exception is not a failure: a signal that was IGNORED WHEN THE SHELL
# STARTED cannot be trapped at all — `trap` is a silent no-op and `trap -p`
# keeps printing '' (a non-interactive shell starts background children with
# SIGINT ignored, so `tests/run_shell_test.sh … &` is exactly this case). Such a
# signal cannot interrupt the run either, so no handler is missing. An ignore
# set after startup is replaced by _tg_append_signal_trap, so a '' surviving
# that call can only be the entry-time kind.
_tg_traps_armed() {
    local s t
    [[ "$(trap -p EXIT)" == *tmpdir_guard_end* ]] || return 1
    for s in HUP INT TERM; do
        t="$(trap -p "$s")"
        [[ "$t" == *_tg_on_signal* ]] && continue
        [[ "$t" == "trap -- '' "* ]] && continue      # ignored at entry
        return 1                                      # absent, or not ours
    done
    return 0
}

# _tg_stop_child — TERM the running phase's whole process group, wait up to 10s
# for it to empty, then KILL it. Returns once the group is gone (or after a
# final bounded wait). Never fails.
_tg_stop_child() {
    local pg="$_TG_CHILD" i
    [[ -n "$pg" ]] || return 0
    _TG_CHILD=""
    kill -TERM -- "-$pg" 2>/dev/null || { wait "$pg" 2>/dev/null; return 0; }
    for ((i = 0; i < 100; i++)); do
        kill -0 -- "-$pg" 2>/dev/null || break
        sleep 0.1
    done
    if kill -0 -- "-$pg" 2>/dev/null; then
        kill -KILL -- "-$pg" 2>/dev/null || true
        for ((i = 0; i < 50; i++)); do
            kill -0 -- "-$pg" 2>/dev/null || break
            sleep 0.1
        done
    fi
    wait "$pg" 2>/dev/null || true
    return 0
}

_tg_on_signal() {
    local n="$1"
    _tg_stop_child
    exit $((128 + n))
}

tmpdir_guard_begin() {
    local label="${1:-}" base f base_name pid
    local -a stale=()
    if [[ ! "$label" =~ ^[A-Za-z0-9]+$ ]]; then
        echo "TMPDIR GUARD: invalid label '${label}' (want [A-Za-z0-9]+)" >&2
        return 2
    fi
    if [[ -n "$_TG_DIR" ]]; then
        echo "TMPDIR GUARD: already active ($_TG_DIR)" >&2
        return 2
    fi
    base="${TMPDIR:-/tmp}"
    base="${base%/}"
    [[ -n "$base" ]] || base="/tmp"
    case "$base/" in
        */.claude/*)
            echo "TMPDIR GUARD: refusing a guard directory under '$base' (contains /.claude/, which test sandboxes reject) — running unguarded" >&2
            return 2 ;;
    esac
    if ! _TG_DIR="$(mktemp -d "$base/ait_${label}_$$_XXXXXX" 2>/dev/null)"; then
        _TG_DIR=""
        echo "TMPDIR GUARD: could not create a guard directory under '$base' — running unguarded" >&2
        return 2
    fi

    # Directories left by a guarding shell that died without its handler
    # (SIGKILL): report, never delete — see NOT COVERED above.
    while IFS= read -r f; do
        [[ "$f" == "$_TG_DIR" ]] && continue
        base_name="${f##*/}"
        pid="${base_name#ait_"${label}"_}"; pid="${pid%%_*}"
        [[ "$pid" =~ ^[0-9]+$ ]] || continue
        kill -0 "$pid" 2>/dev/null && continue     # a concurrent, live run
        stale+=("$base_name")
    done < <(find "$base" -mindepth 1 -maxdepth 1 -type d -name "ait_${label}_*_*" 2>/dev/null | LC_ALL=C sort)
    if (( ${#stale[@]} > 0 )); then
        {
            printf 'TMPDIR GUARD: %d guard dir(s) from earlier runs remain under %s (owner gone — likely a killed run; its workers may still be running, so remove by hand once no process uses them): ' "${#stale[@]}" "$base"
            printf '%s ' "${stale[@]:0:5}"
            (( ${#stale[@]} > 5 )) && printf '… and %d more' $(( ${#stale[@]} - 5 ))
            printf '\n'
        } >&2
    fi

    if [[ -n "${TMPDIR+x}" ]]; then _TG_ORIG_SET=1; _TG_ORIG="$TMPDIR"; else _TG_ORIG_SET=0; _TG_ORIG=""; fi
    _TG_DONE=0
    export TMPDIR="$_TG_DIR"

    _tg_prepend_exit_trap 'tmpdir_guard_end'
    _tg_append_signal_trap HUP  '_tg_on_signal 1'
    _tg_append_signal_trap INT  '_tg_on_signal 2'
    _tg_append_signal_trap TERM '_tg_on_signal 15'
    if ! _tg_traps_armed; then
        # Never report a guard whose signal path is missing: an interrupt
        # would then run only the caller's old handler and carry on. Back out
        # (end removes the dir, restores TMPDIR, and makes the EXIT hook a
        # no-op) and let the caller run unguarded, as on any begin failure.
        echo "TMPDIR GUARD: could not install the guard's EXIT/HUP/INT/TERM traps — running unguarded" >&2
        tmpdir_guard_end
        return 2
    fi
    return 0
}

tmpdir_guard_run() {
    local rc had_m=0
    [[ "$-" == *m* ]] && had_m=1
    set -m
    "$@" </dev/null &
    _TG_CHILD=$!
    (( had_m )) || set +m
    if wait "$_TG_CHILD"; then rc=0; else rc=$?; fi
    # The leader is gone, but members it backgrounded may still be running in
    # its group — and writing into TMPDIR, which is about to be removed. Stop
    # them now (they are strays of the phase, not of anything else: daemons
    # such as a tmux server leave the group by calling setsid).
    if kill -0 -- "-$_TG_CHILD" 2>/dev/null; then
        echo "TMPDIR GUARD: the phase left process(es) running in its process group; stopping them" >&2
        _tg_stop_child
    fi
    _TG_CHILD=""
    return "$rc"
}

tmpdir_guard_end() {
    local f n shown
    local -a left=()
    [[ -n "$_TG_DIR" && "$_TG_DONE" != 1 ]] || return 0
    _TG_DONE=1
    # A phase can still be running here: a caller's own signal handler that
    # calls `exit` runs BEFORE ours (ours is appended, so it is unreachable),
    # and a `set -e` abort or an explicit exit from the caller mid-phase lands
    # here directly. Removing the directory under a live phase lets it keep
    # writing (or recreate it), so stop the whole group first — on every route
    # into this function, not only the guard's own signal path (t2290 review).
    if [[ -n "$_TG_CHILD" ]]; then
        echo "TMPDIR GUARD: the run is ending while a phase is still running; stopping its process group first" >&2
        _tg_stop_child
    fi
    if [[ -d "$_TG_DIR" ]]; then
        while IFS= read -r f; do
            f="${f##*/}"
            _tg_expected_entry "$f" && continue
            left+=("$f")
        done < <(find "$_TG_DIR" -mindepth 1 -maxdepth 1 2>/dev/null | LC_ALL=C sort)
        n=${#left[@]}
        if (( n > 0 )); then
            shown=$(( n < _TG_REPORT_CAP ? n : _TG_REPORT_CAP ))
            {
                printf 'TMPDIR LEFTOVERS (%d): ' "$n"
                printf '%s ' "${left[@]:0:shown}"
                (( n > shown )) && printf '… and %d more' $(( n - shown ))
                printf '\n'
                printf 'TMPDIR LEFTOVERS: these were left in the per-run TMPDIR (%s) and are now removed; attribute each by its name prefix\n' "$_TG_DIR"
            } >&2
        fi
        chmod -R u+w "$_TG_DIR" 2>/dev/null || true
        rm -rf -- "$_TG_DIR" 2>/dev/null || true
        if [[ -e "$_TG_DIR" ]]; then
            echo "TMPDIR GUARD: could not fully remove $_TG_DIR" >&2
        fi
    fi
    if (( _TG_ORIG_SET )); then export TMPDIR="$_TG_ORIG"; else unset TMPDIR; fi
    return 0
}
