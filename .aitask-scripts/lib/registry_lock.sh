#!/usr/bin/env bash
# registry_lock.sh - the persistent-registry mutex, an ADAPTER over the shared
# stale_lock.sh core (t1507). Source this file from aitask scripts; do not
# execute directly.
#
# The project registry (~/.config/aitasks/projects.yaml) is mutated by a
# whole-file read-modify-write in aitask_projects.sh. Those mutations fire
# concurrently — `ait projects add` runs silently on every tmux session bootstrap
# (lib/tmux_bootstrap.sh), so a restart burst launches many writers at once.
# Without serialization the last writer clobbers the others with its stale
# snapshot, silently dropping project_group / last_opened fields (t1073). The
# same mutex also guards agent marks, shadow rejections, attach/artifact-manifest
# transactions (lib/attachment_lock.sh) and `ait gates sync-registry`.
#
# This file used to carry its OWN mkdir mutex, whose stale reclaim observed the
# holder pid and only THEN `mv`'d whatever was at the path — the observation and
# the destructive act were not serialized, so a contender could displace a
# freshly re-published live lock (two holders in the critical section). That is
# the exact race t1496 fixed for the gate/child locks by building
# lib/stale_lock.sh; t1507 converts this lib onto it, leaving ONE mutex protocol
# in the tree. All the protocol invariants (`.gc`-guarded single-winner reclaim,
# live PIDs never displaced, owner-token release, verified removals) now live
# there and are documented in that file — do not restate or fork them here.
#
# Provides:
#   registry_lock_acquire <lock_dir> [timeout_secs=10] [label]  -> 0 held / 1 busy
#   registry_lock_release <lock_dir>                            -> always 0
#   registry_lock_describe <lock_dir>                           -> recovery hint
#
# Lock paths are CALLER-CHOSEN and stay at fixed shared locations (the per-user
# config dir, the data worktree, /tmp). They are deliberately NOT routed through
# stale_lock's ait_lock_dir per-repo scoping: these ledgers are shared across
# repositories by design. Only the mutex protocol converges.
#
# Requires warn() from terminal_compat.sh — every caller sources it first.
#
# --- Deliberate boundary deltas (the adapter's whole surface) ---------------
#
#   1. TIMEOUT vs RETRY BUDGET. This API budgets SECONDS; stale_lock budgets
#      ATTEMPTS. The deadline loop below converts, re-arming from the REMAINING
#      time on each pass. Note the contract is coarser than it looks and is
#      preserved INCLUDING its coarseness: the deadline is quantized to whole
#      seconds by `date +%s`, so the guarantee is "never reports busy before the
#      integer clock reaches start_second + timeout" — NOT "waits at least
#      timeout seconds of real time". A call entered late in a second can
#      legitimately return almost immediately. Keeping `date +%s` is deliberate:
#      it is the existing behavior and it is portable.
#   2. RELEASE ALWAYS RETURNS 0. stale_lock_release returns 1 on a retained lock
#      or guard, but every caller is `set -euo pipefail` and calls this bare,
#      AFTER the protected mutation has already committed — propagating there
#      would abort the script mid-flow. Retention is surfaced as a warn instead.
#   4. MARKERLESS GUARD RECLAIM is opted in here, and that is a decision about
#      the LOCK DIR, not this adapter: none of this adapter's callers can reach
#      stale_lock_guarded_section, so no shipped version holds one of these
#      guards across an unbounded operation. `ait_lock_dir emails` is reached
#      both through here and through a direct stale_lock_acquire call in
#      aitask_create.sh, and the two MUST pass the same window — otherwise
#      whether a wedged guard self-heals would depend on which writer arrived
#      first. merge_lock.sh deliberately opts out.
#   5. AUTO-RELEASE ON EXIT, CHAINED (t2322). stale_lock installs no trap; this
#      adapter does — see "Caller EXIT traps" below.
#   3. TOKENLESS-AGE RECLAIM is newly reachable (stale_lock's 120s window). This
#      lib's own locks always carry a pid file, and publication happens under the
#      `.gc` guard, so a tokenless dir can only be a legacy/foreign lock — never
#      a holder mid-acquire. Strictly safer than the old code, which read a
#      tokenless dir as live and waited out the whole timeout.
#
# --- Recovery ---------------------------------------------------------------
#
# Since t1598 the `.gc` guard carries a holder record, so a process killed
# inside its few-file-op section leaves a guard naming a dead pid — and the next
# acquire frees it automatically. This adapter also passes a markerless-guard
# window (see delta 4), so a guard left by pre-t1598 code self-heals once it is
# older than that window.
#
# Two cases still need a human, and both are fail-safe rather than fail-open:
# a recycled holder pid reads as alive, and a genuinely hung holder is never
# displaced. For those, registry_lock_describe names the lock, the guard, and
# the holder pid when there is one; a caller whose failure is otherwise silent
# (`ait projects add` runs as `… >/dev/null 2>&1 || true` on every tmux
# bootstrap) should surface it.
#
# --- Caller EXIT traps (t2322) ----------------------------------------------
#
# A held lock is released by an EXIT trap, so a script that dies mid-section
# does not strand it. That trap no longer costs the caller its own:
#
#   * In the top-level shell the acquire CHAINS: it saves the caller's EXIT
#     trap text and installs _registry_lock_exit_chain, which at exit releases
#     the lock FIRST and then runs the caller's handler with the dying `$?`
#     and the script's positional parameters.
#     The release RESTORES the saved trap. Before t2322 the acquire replaced
#     the caller's trap and the release ran `trap - EXIT`, so a caller's
#     cleanup was dead during the hold and gone afterwards.
#   * A trap the caller installs DURING the hold still ends at the release,
#     which restores the pre-acquire trap. Work that must run under the lock
#     on an abort is prepended inside the hold with txn_chain_exit_trap
#     (lib/txn_snapshot.sh) and runs before the release.
#   * Inside a subshell (`( )`, `$( )`, a pipeline stage) nothing is composed.
#     There `trap -p` shows the PARENT's handler, which is not armed in the
#     subshell; composing it would run the parent's cleanup when the subshell
#     exits. A subshell acquire replaces and its release clears, exactly as
#     before t2322. A subshell's own pre-acquire trap is therefore still lost.
#     That is a known boundary: an inherited trap cannot be told apart from
#     one the subshell set.
#   * The trap state is per-shell and the variables are not: a child inherits
#     them but not the armed trap. Every "is it armed?" check compares the
#     recorded arming shell ("${BASHPID:-$$}:${BASH_SUBSHELL}") with the
#     current one.
#   * lib/archive_utils.sh's sweep stays the OUTERMOST layer. Its own wrapping
#     is peeled off before the caller's text is saved, and the re-arm puts it
#     back (see _registry_lock_save_caller_exit_trap).

[[ -n "${_AIT_REGISTRY_LOCK_LOADED:-}" ]] && return 0
_AIT_REGISTRY_LOCK_LOADED=1

_AIT_REGISTRY_LOCK_SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/stale_lock.sh
source "$_AIT_REGISTRY_LOCK_SELF/stale_lock.sh"

# One value pair, defined together because they are one value: the poll interval
# and its reciprocal. They are what converts this API's seconds into the core's
# attempt budget — changing either alone silently rescales every timeout.
_REGISTRY_LOCK_SLEEP=0.05
_REGISTRY_LOCK_ATTEMPTS_PER_SEC=20

# One active lock per process. Set on acquire, cleared on release.
_registry_lock_dir=""
_registry_lock_token=""

# EXIT-trap state (t2322) -- see "Caller EXIT traps" in the header. `:=`, not a
# plain assignment: the tests reset the double-source guard, and a same-shell
# re-source must not erase a caller trap saved by an acquire that is still held.
#   _registry_lock_trap_mode   ""      not armed
#                              chain   top-level shell: release, then the saved caller trap
#                              replace subshell: release only (the pre-t2322 behaviour)
#   _registry_lock_trap_shell  the shell that armed it, "${BASHPID:-$$}:${BASH_SUBSHELL}"
#   _registry_lock_saved_trap  the caller's EXIT trap text, archive sweep unwrapped
: "${_registry_lock_trap_mode:=}"
: "${_registry_lock_trap_shell:=}"
: "${_registry_lock_saved_trap:=}"

# registry_lock_acquire <lock_dir> [timeout_secs] [label]
# Returns 0 with the lock held, or 1 if a live holder kept it past the deadline.
# Emits nothing on the busy path: aitask_shadow_rejected.sh and
# aitask_agent_marks.sh both pin an exact `LOCK_BUSY` on 2>&1-captured output.
registry_lock_acquire() {
    local dir="$1"
    local timeout="${2:-10}"
    local label="${3:-lock $1}"
    local deadline remaining retries
    deadline=$(( $(date +%s) + timeout ))

    while :; do
        remaining=$(( deadline - $(date +%s) ))
        if (( remaining < 0 )); then
            remaining=0
        fi
        retries=$(( remaining * _REGISTRY_LOCK_ATTEMPTS_PER_SEC ))
        # Floor of 3: a reclaim consumes an attempt without acquiring, so a zero
        # or sub-second timeout must still get the follow-up mkdir that the old
        # `continue`-after-steal loop gave it -- and since t1598 there can be TWO
        # such reclaims before the acquiring mkdir (the guard, then the lock dir).
        if (( retries < 3 )); then
            retries=3
        fi
        # This adapter MAY opt in to markerless guard reclaim: none of its
        # callers can reach stale_lock_guarded_section, so no shipped version
        # holds one of its guards across an unbounded operation. See delta 4.
        if stale_lock_acquire "$dir" "$retries" "$_REGISTRY_LOCK_SLEEP" "$label" \
                "${_REGISTRY_LOCK_GC_WINDOW:-$_STALE_LOCK_GC_WINDOW_DEFAULT}"; then
            _registry_lock_dir="$dir"
            _registry_lock_token="$STALE_LOCK_TOKEN"
            _registry_lock_arm_exit_trap "$dir"
            return 0
        fi
        # Re-arm until the deadline actually passes. stale_lock's budget is a
        # retry count and a burst of dead-holder reclaims spends it WITHOUT
        # sleeping, so returning on the first exhaustion would report busy early
        # -- the one thing this API's timeout promises not to do.
        if (( $(date +%s) >= deadline )); then
            return 1   # live holder, timed out → FAIL SAFELY (never write unlocked)
        fi
    done
}

# registry_lock_release <lock_dir>
# Removes the lock dir ONLY if this process still owns it (token match), then
# gives the caller back the EXIT trap it had before the acquire.
# Always returns 0 -- see delta 2 in the header.
registry_lock_release() {
    local dir="$1"
    [[ -n "$_registry_lock_dir" && "$dir" == "$_registry_lock_dir" ]] || return 0
    _registry_lock_drop "$dir"
    _registry_lock_restore_exit_trap
    return 0
}

# registry_lock_describe <lock_dir> -- human recovery hint for an exhausted
# acquire: the resolved dir, the recorded holder pid, and the `.gc` guard when
# one is present. Callers append it to their own busy message.
registry_lock_describe() {
    stale_lock_describe "$1"
}

# --- EXIT-trap plumbing (t2322) ----------------------------------------------

# _registry_lock_drop <lock_dir> -- the token release and the state clear, with
# no trap operation (shared by the explicit release and the EXIT chain).
_registry_lock_drop() {
    local dir="$1"
    stale_lock_release "$dir" "$_registry_lock_token" \
        || warn "registry_lock: '$dir' not fully released"
    _registry_lock_dir=""
    _registry_lock_token=""
    return 0
}

# _registry_lock_arm_exit_trap <lock_dir> -- install the auto-release.
#
# The shell identity is computed INLINE, never through $( ): a command
# substitution is itself a subshell and would report its own BASHPID and level.
_registry_lock_arm_exit_trap() {
    local dir="$1" here="${BASHPID:-$$}:${BASH_SUBSHELL:-0}"
    # Same-shell nested acquire: our chain is already the trap and already
    # holds the caller's text -- saving again would save OURSELVES and recurse.
    # (One active lock per process stays the contract; the chain releases
    # whichever lock _registry_lock_dir names at exit.) The test is scoped to
    # the arming shell because a ( ) child inherits these variables but NOT
    # the armed trap: an unscoped "already armed" would leave the child's own
    # lock with no release at all.
    if [[ "$_registry_lock_trap_mode" == chain && "$_registry_lock_trap_shell" == "$here" ]]; then
        return 0
    fi
    _registry_lock_trap_shell="$here"
    _registry_lock_saved_trap=""
    if (( ${BASH_SUBSHELL:-0} > 0 )); then
        # Inside ( ) / $( ), `trap -p` shows the PARENT's handler, which is not
        # armed here: composing it would run the parent's cleanup when this
        # subshell exits. Replace, exactly as before t2322.
        _registry_lock_trap_mode=replace
        # shellcheck disable=SC2064  # expand $dir now, on purpose
        trap "registry_lock_release '$dir'" EXIT
        # Keep the archive sweep when lib/archive_utils.sh is loaded (t2032).
        if declare -F ait_archive_rearm_exit_trap >/dev/null; then ait_archive_rearm_exit_trap; fi
        return 0
    fi
    _registry_lock_trap_mode=chain
    _registry_lock_save_caller_exit_trap
    # Installed FROM the constant the chain recognises itself by, so the two
    # cannot drift (see _REGISTRY_LOCK_CHAIN_CMD for why it carries "$@").
    # shellcheck disable=SC2064  # the constant IS the trap text; its "$@" stays literal
    trap "$_REGISTRY_LOCK_CHAIN_CMD" EXIT
    # The archive sweep wraps the chain as the OUTERMOST layer (t2032); the
    # caller text was saved with that layer peeled off, so it is not doubled.
    if declare -F ait_archive_rearm_exit_trap >/dev/null; then ait_archive_rearm_exit_trap; fi
    return 0
}

# The chain's trap text: the one value both installed (arm, above) and
# recognised (_registry_lock_owned_tail). `"$@"` is expanded at EXIT time, in
# the exit context, and handed to the chain, so the caller's handler -- eval'd
# inside a function -- still sees the script's positional parameters
# ($1, $#, "$@").
_REGISTRY_LOCK_CHAIN_CMD='_registry_lock_exit_chain "$@"'

# _registry_lock_owned_tail <text> <cmd> -- 0 when the wrapper command <cmd> is
# a COMMAND of <text> in one of the two positions a wrapper can occupy:
#   * the whole text (a wrapper installed alone), or
#   * the LAST command, after an unescaped "; " ending the text -- what every
#     status-preserving prepend produces, whoever wrote it (txn_chain_exit_trap
#     in txn_snapshot.sh, _tg_prepend_exit_trap in tests/lib/tmpdir_guard.sh,
#     a hand-written `x; <cmd>`): a prepend keeps the earlier trap as its tail.
# Sets _RL_HEAD to whatever precedes <cmd> ("" for a whole-text match).
#
# Never a substring match: quoted caller data such as
# `rmdir "$d/_ait_archive_cleanup"` only MENTIONS the name. Text that ends
# inside or after a quote ends in the quote, never in the bare command word, so
# it cannot match. An ESCAPED `\;` before the word makes it an argument
# (`-exec … \; x`) and is refused. Escaping is decided by the parity of the
# run of backslashes before the `;`: `\;` is a literal backslash followed by
# an active `;`, so an even run still recognises the command.
_registry_lock_owned_tail() {
    local text="$1" cmd="$2" head run n=0
    _RL_HEAD=""
    if [[ "$text" == "$cmd" ]]; then
        return 0
    fi
    case "$text" in
        *"; $cmd")
            head="${text%"; $cmd"}"
            run="$head"
            while [[ "$run" == *\\ ]]; do
                run="${run%\\}"
                n=$(( n + 1 ))
            done
            if (( n % 2 == 1 )); then
                return 1          # odd run: the `;` itself is escaped
            fi
            _RL_HEAD="$head"
            return 0 ;;
    esac
    return 1
}

# _registry_lock_join <head> <tail> -- "<head>; <tail>", dropping an empty side,
# into _RL_JOINED.
_registry_lock_join() {
    if [[ -z "$1" ]]; then
        _RL_JOINED="$2"
    elif [[ -z "$2" ]]; then
        _RL_JOINED="$1"
    else
        _RL_JOINED="$1; $2"
    fi
}

# _registry_lock_save_caller_exit_trap -- store the current EXIT trap text in
# _registry_lock_saved_trap, with lib/archive_utils.sh's own layer peeled off.
#
# The peel is what keeps the two wrappers from eating each other. Saving
# `_ait_archive_exit_chain` verbatim and then re-arming the sweep would let the
# sweep overwrite its stored caller (_AIT_ARCHIVE_CALLER_EXIT_TRAP) with OUR
# command, and exit would recurse sweep -> us -> sweep -> us. So the sweep's
# chain command is replaced by the text it runs at exit, and its bare cleanup
# command is dropped. The re-arm then puts the sweep back outside us, and
# release puts it back outside the caller -- the pre-acquire state.
# _AIT_ARCHIVE_CALLER_EXIT_TRAP is only READ here.
_registry_lock_save_caller_exit_trap() {
    local cur
    cur="$(trap -p EXIT)"
    if [[ -z "$cur" ]]; then
        _registry_lock_saved_trap=""
        return 0
    fi
    cur="${cur#trap -- }"; cur="${cur% EXIT}"
    eval "cur=$cur"                       # unquote bash's own rendering
    if declare -F ait_archive_rearm_exit_trap >/dev/null; then
        if _registry_lock_owned_tail "$cur" _ait_archive_cleanup; then
            cur="$_RL_HEAD"
        elif _registry_lock_owned_tail "$cur" _ait_archive_exit_chain; then
            _registry_lock_join "$_RL_HEAD" "${_AIT_ARCHIVE_CALLER_EXIT_TRAP-}"
            cur="$_RL_JOINED"
        fi
    fi
    # Our own command can only be here if the state above was lost; never save
    # it (it would eval itself at exit).
    if _registry_lock_owned_tail "$cur" "$_REGISTRY_LOCK_CHAIN_CMD"; then
        cur="$_RL_HEAD"
    fi
    _registry_lock_saved_trap="$cur"
}

# _registry_lock_restore_exit_trap -- give the caller back its EXIT trap.
#
# Only the shell that armed the chain restores. Anywhere else -- replace mode, or
# a subshell releasing a lock its parent armed -- clear, as before t2322:
# restoring the parent's text there would arm the parent's cleanup in the child.
_registry_lock_restore_exit_trap() {
    local here="${BASHPID:-$$}:${BASH_SUBSHELL:-0}"
    local saved="$_registry_lock_saved_trap" mine=0
    if [[ "$_registry_lock_trap_mode" == chain && "$_registry_lock_trap_shell" == "$here" ]]; then
        mine=1
    fi
    _registry_lock_trap_mode=""
    _registry_lock_trap_shell=""
    _registry_lock_saved_trap=""
    if (( mine == 1 )) && [[ -n "$saved" ]]; then
        trap -- "$saved" EXIT
        # Keep the archive sweep when lib/archive_utils.sh is loaded (t2032).
        if declare -F ait_archive_rearm_exit_trap >/dev/null; then ait_archive_rearm_exit_trap; fi
    else
        trap - EXIT
        # Keep the archive sweep when lib/archive_utils.sh is loaded (t2032).
        if declare -F ait_archive_rearm_exit_trap >/dev/null; then ait_archive_rearm_exit_trap; fi
    fi
    return 0
}

# _registry_lock_exit_chain -- the EXIT handler in chain mode: release, THEN the
# caller's handler, exactly as the caller's unwrapped trap would run it (the
# shape of lib/archive_utils.sh's _ait_archive_exit_chain):
#   * release first, because an APPENDED command never runs after a handler that
#     calls `exit` (ait_ledger_lock_exit_trap ends in one) -- release-last would
#     leak the lock. Work that must run UNDER the lock (a transaction rollback)
#     is prepended inside the hold with txn_chain_exit_trap and so runs first;
#   * `$?` is restored to the dying status before the caller's text runs;
#   * `trap -p EXIT` is rewritten with our command replaced by the caller's
#     text, so a first-command detector (lib/ledger_block.sh) reads its real
#     position;
#   * the caller's text is eval'd with the positional parameters the trap
#     passed in ("$@" at exit), so a handler reading $1 / "$@" still works.
# Re-arming EXIT inside the running handler does not re-run it. The two `trap`
# lines below are deliberately NOT followed by the sweep re-arm: the sweep wraps
# this chain from outside and has already run.
_registry_lock_exit_chain() {
    local __rl_rc=$? __rl_saved __rl_cur __rl_now   # `__rl_rc=$?` MUST stay first
    __rl_saved="$_registry_lock_saved_trap"
    if [[ -n "$_registry_lock_dir" ]]; then
        _registry_lock_drop "$_registry_lock_dir"
    fi
    _registry_lock_trap_mode=""
    _registry_lock_trap_shell=""
    _registry_lock_saved_trap=""
    __rl_cur="$(trap -p EXIT)"
    __rl_cur="${__rl_cur#trap -- }"; __rl_cur="${__rl_cur% EXIT}"
    __rl_now=""
    if [[ -n "$__rl_cur" ]]; then
        eval "__rl_now=$__rl_cur"         # unquote bash's own rendering
    fi
    if _registry_lock_owned_tail "$__rl_now" "$_REGISTRY_LOCK_CHAIN_CMD"; then
        _registry_lock_join "$_RL_HEAD" "$__rl_saved"
        __rl_now="$_RL_JOINED"
    else
        __rl_now="$__rl_saved"
    fi
    if [[ -n "$__rl_now" ]]; then
        trap -- "$__rl_now" EXIT   # archive-sweep: exit-handler
    else
        trap - EXIT   # archive-sweep: exit-handler
    fi
    (exit "$__rl_rc") && :
    eval "$__rl_saved"
}
