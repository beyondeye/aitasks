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
# KILLED RUNS (t2301). SIGKILL of the guarding shell runs no handler: its
# directory stays, and its phase's process group may outlive it and keep writing
# there. tmpdir_guard_begin finds such directories (same label, other pid) and
# reclaims one ONLY on positive evidence that nothing can still use it; any
# directory it cannot prove unused is kept and reported with a reason.
#
#   Run metadata. Each run records itself in a private control directory BESIDE
#   its guard directory, <base>/.<dirname>.ait_guard_meta/ (mode 0700, made by
#   mkdir, which is exclusive and never follows a symlink), in the file `meta`.
#   Beside, not inside: a phase neither sees it in its TMPDIR nor can delete its
#   own run's evidence. Format:
#       ait_tmpdir_guard_meta 1
#       owner <pid> <kind> <token>     get_pid_identity of the guarding shell
#       phase_start <seq>              appended BEFORE each phase is forked
#       phase <seq> <pgid>             appended right after the fork
#   The two phase lines make a phase whose pgid never got recorded (owner killed
#   between fork and append) detectable instead of silently missing. A phase is
#   launched inside the guard only when its intent line is recorded, or the
#   record is CONFIRMED unusable: a failed append INVALIDATES the metadata
#   (removes it, else makes it unreadable — chmod needs neither space nor write
#   permission), so a killed run of that kind is kept. When neither can be
#   confirmed, the record may still parse as complete with that group missing,
#   so this and every later phase runs OUTSIDE the guard (original TMPDIR; the
#   run then counts as not inspected) — nothing then uses the guard dir that its
#   record does not account for.
#
#   Evidence ladder, first verdict wins:
#     1. metadata: missing (a pre-metadata dir, or invalidated) or not provably
#        this run's own (control dir or file not a real, owned, readable and
#        writable entry; bad header, line, or token shape for its kind; owner
#        pid other than the name's; an unterminated last line) -> kept, unless
#        the pid in the name answers kill -0 (a concurrent run: silent);
#     2. owner: lock_holder_liveness (.aitask-scripts/lib/pid_anchor.sh) on
#        pid + start-time token. alive -> a concurrent run, silent; unknown ->
#        kept. A recycled pid fails the token match and reads dead;
#     3. phases: a phase_start without its phase line -> kept; every recorded
#        pgid must answer kill -0 with "No such process" (a surviving writer of
#        a dead wrapper keeps the dir);
#     4. holders: no process may have its cwd (any thread), an fd, its environ
#        or its cmdline under the dir (Linux /proc). The scan counts only when the process LIST is complete:
#        a proc mount with hidepid=invisible/ptraceable (or one whose options
#        cannot be read) hides processes from enumeration, so every candidate is
#        kept (proc-view-incomplete). Every file is read
#        with cat, so a read that fails after the open is a failure, never a
#        shorter record. Off Linux: `lsof +w +D` (warnings forced on), believed
#        only as root and only when it exits 1 with no output at all;
#     5. mounts: nothing may be mounted at or below the dir (bind mounts
#        included — matched by path in the mount table, not by device), since
#        the recursive chmod and rm would walk into it. The whole table is
#        read: a mount found anywhere wins; otherwise any unreadable row (or an
#        unreadable table) keeps the dir. On Linux the table is the kernel's
#        (<proc-root>/mounts, else /proc/self/mounts), never `mount`'s stdout;
#        on Darwin/BSD it is `mount`; elsewhere coverage cannot be established
#        and the dir is kept. Off Linux, `mount` rows are printed
#        unescaped, so a row whose " on " split is ambiguous is tried at EVERY
#        split, and any reading below the dir counts as a mount there.
#        tmpdir_guard_end applies the same rule to the run's own dir: it
#        removes it only when the table was read and shows nothing below it,
#        and reports the outcome it observed. Control dirs are never removed
#        recursively: their one `meta` file, then rmdir — and only on that same
#        evidence. Discovery is NUL-delimited, so a base path may hold a newline;
#     6. sockets: no socket file may exist anywhere inside the dir (find -type
#        s over the candidate's own tree, after the mount check and before
#        anything recursive). A bound unix socket under the dir is such a file,
#        so no host-wide socket table is read. A socket found, or a walk that
#        fails, keeps the dir: a stale socket file is left for manual cleanup,
#        and whether it still has a listener is not checked.
#   A record is treated as invalidated only on POSITIVE evidence (a find that
#   ran and showed it gone or without its owner-read bit); a failed probe, or rm
#   and chmod reporting success, proves nothing.
#        A process that cannot be inspected (another uid, non-dumpable, a read
#        that fails while it still exists) is a holder of UNKNOWN state, and any
#        such process keeps every candidate: unknown is never rounded up to dead,
#        and a process's start time does not rule out later access or a passed
#        descriptor. Consequence: on a non-root Linux host under systemd,
#        `sd-pam` and other users' processes are always uninspectable, so there a
#        reclaim effectively happens only for a root run (CI containers) or on a
#        host where every process is inspectable. Elsewhere the dir is
#        reported. Unix sockets bound ELSEWHERE on the host (abstract, relative,
#        or under another path) never affect a reclaim: sockets are judged only
#        by the candidate's own tree (step 6), and a stale socket file found
#        there keeps that dir for manual cleanup.
#
#   Residual gaps (not covered): the window between the scan and the removal;
#   threads with an unshared fd table (only <pid>/fd is read; cwd is read per
#   thread); processes in another mount or PID namespace (a container sharing
#   the base); a process that later re-derives the path from nothing it
#   currently holds; a mount made between the mount check and the removal.
#
#   _TG_PROC_ROOT (default /proc), _TG_EUID (default $EUID), _TG_OSTYPE
#   (default $OSTYPE) and _TG_SELF_MOUNTS (default /proc/self/mounts) are shell
#   variables — set them AFTER sourcing — and the test seams for steps 4 and 5.
#   They are deliberately not environment variables, so they never leak into
#   nested runs.
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
# Leftover count from the last tmpdir_guard_end, set ONLY when the inspection
# really ran (the listing succeeded, or the path is truly absent — no entry and
# no symlink: nothing left; a path replaced by a file or link is NOT absent). Empty means "not inspected" — a guard that never started, or a listing
# that failed — and strict callers must treat that as a failure, never as 0.
_TG_LEFTOVER_COUNT=""
_TG_META=""           # the active run's metadata file; "" when not recorded
_TG_META_DIR=""       # its private control directory (beside _TG_DIR)
_TG_META_SUFFIX=".ait_guard_meta"
_TG_PHASE_SEQ=0       # phases started by this run
_TG_PROC_ROOT="/proc" # holder-scan root (test seam — see KILLED RUNS)
_TG_EUID="${EUID:-}"  # effective uid the lsof rule trusts (test seam)
_TG_OSTYPE="${OSTYPE:-}"                # platform for the mount-table source (test seam)
_TG_SELF_MOUNTS="/proc/self/mounts"     # Linux mount table fallback (test seam)

# Owner identity and liveness come from the framework's PID-anchor library
# (idempotent, side-effect free). Without it the owner is recorded as `none`,
# which the reader can only call dead on a confirmed-absent pid.
_TG_PID_ANCHOR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../../.aitask-scripts/lib/pid_anchor.sh"
if [[ -r "$_TG_PID_ANCHOR" ]]; then
    # shellcheck source=../../.aitask-scripts/lib/pid_anchor.sh disable=SC1091
    . "$_TG_PID_ANCHOR" 2>/dev/null || true
fi

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

# --- Killed-run reclaim (t2301; see KILLED RUNS in the header) --------------
#
# Nothing below forks per process except one readlink and one cat, and nothing
# writes a temp file: the scan runs inside begin, before TMPDIR points at the
# new dir. Every file is read through _tg_slurp: `read` returns non-zero for EOF
# and for a read error alike, so a record cut short by an I/O error would parse
# as a shorter, valid one.

_TG_META_STATE=none   # ok | invalid (record unusable: kept if killed) |
                      # broken (record may look valid but is incomplete) | none
_TG_RAN_OUTSIDE=0     # a phase had to run outside the guard (see tmpdir_guard_run)

# _tg_slurp <var> <file...> — the files' bytes into <var>, via cat, so a read
# error after the open is reported. NUL bytes are dropped (entries run
# together, which can only add a match, never hide one). Non-zero on any open
# or read failure.
_tg_slurp() {
    local __tg_v="$1" __tg_o; shift
    { __tg_o="$(LC_ALL=C cat -- "$@" 2>/dev/null && printf x)"; } 2>/dev/null || return 1
    [[ "$__tg_o" == *x ]] || return 1
    printf -v "$__tg_v" '%s' "${__tg_o%x}"
}

# _tg_lines <text> — split <text> into the array _tg_l, one element per line,
# in one pass. Peeling lines off a string copies the rest each time (quadratic:
# 1.4s on a 1000-row net/unix); a here-string would write a temp file.
_tg_lines() {
    _tg_l=()
    [[ -n "$1" ]] || return 0
    mapfile -t _tg_l < <(printf '%s' "$1")
}

# _tg_mount_escape <path> — <path> spelled as the mount table spells mount
# points (octal escapes for space, tab, newline and backslash).
_tg_mount_escape() {
    local s="$1"
    s="${s//\\/\\134}"; s="${s// /\\040}"; s="${s//$'\t'/\\011}"; s="${s//$'\n'/\\012}"
    _tg_esc="$s"
}

# _tg_mounts_under <dir> — is anything mounted at or below <dir>? A recursive
# chmod or rm would walk into it and change or delete the mounted data, and a
# same-filesystem bind mount is invisible to --one-file-system. Reads the WHOLE
# table: a mount found anywhere wins over a row that could not be read. Returns
# 0 (a mount found, or possibly found; _tg_mount_hit names it), 1 (none — every
# row read and none below <dir>), 2 (no mount found, but the table or a row of
# it could not be read).
#
# Source, by platform ($_TG_OSTYPE): <proc-root>/mounts when present, else on
# Linux the kernel's own table, $_TG_SELF_MOUNTS (/proc/self/mounts) — never
# `mount`'s stdout there, whose util-linux format (`… on <target> type <fs>
# (…)`) is not the BSD one parsed below. On Darwin and the BSDs, `mount`
# stdout. Anywhere else the format is unknown: 2.
_tg_mounts_under() {
    local d="$1" phys tab line mp f rest body unknown=0 src=""
    local -a forms=()
    _tg_mount_hit=""
    phys="$(cd "$d" 2>/dev/null && pwd -P)" || phys=""
    if [[ -e "$_TG_PROC_ROOT/mounts" ]]; then
        src="$_TG_PROC_ROOT/mounts"
    elif [[ "$_TG_OSTYPE" == linux* ]]; then
        src="$_TG_SELF_MOUNTS"
    fi
    if [[ -n "$src" ]]; then
        _tg_mount_escape "${d%/}"; forms+=("$_tg_esc")
        [[ -n "$phys" ]] && { _tg_mount_escape "$phys"; forms+=("$_tg_esc"); }
        _tg_slurp tab "$src" || return 2
        _tg_lines "$tab"
        for line in ${_tg_l[@]+"${_tg_l[@]}"}; do
            if [[ ! "$line" =~ ^[^\ ]+\ ([^\ ]+)\  ]]; then
                unknown=1; continue                                 # a row we cannot read
            fi
            mp="${BASH_REMATCH[1]}"
            for f in "${forms[@]}"; do
                if [[ "$mp" == "$f" || "$mp" == "$f/"* ]]; then _tg_mount_hit="$mp"; return 0; fi
            done
        done
        (( unknown )) && return 2
        return 1
    fi
    case "$_TG_OSTYPE" in
        darwin*|freebsd*|netbsd*|openbsd*|dragonfly*) ;;
        *) return 2 ;;                                  # a `mount` format we do not know
    esac
    tab="$(LC_ALL=C mount 2>/dev/null)" || return 2
    [[ -n "$tab" ]] || return 2
    forms=("${d%/}"); [[ -n "$phys" ]] && forms+=("$phys")
    _tg_lines "$tab"
    # `<source> on <target> (<options>)`, printed unescaped. A source or target
    # that itself contains " on " (an NFS export path, say) makes the split
    # ambiguous, so EVERY split is tried: any reading that puts the target at
    # or below <dir> counts as a mount there. A row not of that shape (a path
    # with a newline breaks it in two) cannot be read at all.
    for line in ${_tg_l[@]+"${_tg_l[@]}"}; do
        if [[ "$line" != *" on "*" ("*")" ]]; then
            unknown=1; continue
        fi
        body="${line% (*}"
        rest="$body"
        while [[ "$rest" == *" on "* ]]; do
            rest="${rest#* on }"
            for f in "${forms[@]}"; do
                # "<dir> …" too: the remainder may be the dir plus a suffix the
                # format added (` type <fs>`), and a sibling named "<dir> x"
                # read as a mount only keeps a dir — the safe direction.
                if [[ "$rest" == "$f" || "$rest" == "$f/"* || "$rest" == "$f "* ]]; then
                    _tg_mount_hit="$rest"; return 0
                fi
            done
        done
    done
    (( unknown )) && return 2
    return 1
}

# _tg_remove_ctl <control-dir> — remove a run's control dir with nothing
# recursive: its one expected entry (`meta`), then rmdir, which refuses a
# non-empty dir and a mount point alike. Nothing is touched unless the mount
# table was read and shows nothing at or below it. Non-zero when the dir remains.
_tg_remove_ctl() {
    local c="$1" mrc=0
    [[ -d "$c" && ! -L "$c" ]] || return 1
    _tg_mounts_under "$c" || mrc=$?
    (( mrc == 1 )) || return 1
    rm -f -- "$c/meta" 2>/dev/null || true
    rmdir -- "$c" 2>/dev/null
}

# _tg_meta_path_of <guard-dir> — set _tg_meta_dir (the run's private control
# directory, beside the guard dir) and _tg_meta_path (its `meta` file).
_tg_meta_path_of() {
    local d="${1%/}"
    _tg_meta_dir="${d%/*}/.${d##*/}${_TG_META_SUFFIX}"
    _tg_meta_path="$_tg_meta_dir/meta"
}

# _tg_token_ok <kind> <token> — the token has the shape its kind's source
# writes (pid_anchor.sh). A token of the wrong shape would make a live owner
# compare unequal and read as recycled, i.e. dead.
_tg_token_ok() {
    case "$1" in
        proc)    [[ "$2" =~ ^[0-9]+$ ]] ;;
        bsdinfo) [[ "$2" =~ ^[0-9]+\.[0-9]{6}$ ]] ;;
        ps)      [[ "$2" =~ ^[A-Za-z0-9_:]+$ ]] ;;
        none)    [[ "$2" == - ]] ;;
        *)       return 1 ;;
    esac
}

# _tg_meta_create <guard-dir> — create the run's control directory and write
# its header and owner identity. mkdir is exclusive and never follows a
# symlink, so nothing planted at that path is written through; the file is then
# created inside a 0700 directory only this user can enter. Sets _TG_META_DIR /
# _TG_META on success; non-zero (both "") on any failure.
_tg_meta_create() {
    local ident="none -" kind tok
    _TG_META_DIR=""; _TG_META=""; _TG_META_STATE=none
    _tg_meta_path_of "$1"
    mkdir -m 700 -- "$_tg_meta_dir" 2>/dev/null || return 1
    if [[ -L "$_tg_meta_dir" || ! -d "$_tg_meta_dir" || ! -O "$_tg_meta_dir" ]]; then
        return 1
    fi
    if declare -F get_pid_identity >/dev/null 2>&1; then
        ident="$(get_pid_identity "$$" 2>/dev/null)" || ident="none -"
    fi
    kind="${ident%% *}"; tok="${ident#* }"
    _tg_token_ok "$kind" "$tok" || ident="none -"
    _TG_META_DIR="$_tg_meta_dir"
    _TG_META="$_tg_meta_path"
    if ! printf 'ait_tmpdir_guard_meta 1\nowner %s %s\n' "$$" "$ident" 2>/dev/null >"$_tg_meta_path"; then
        # The write may have landed whole although it reported failure: make
        # sure no usable record survives (or that phases avoid the guard).
        _tg_meta_invalidate "could not write the run metadata"
        return 1
    fi
    _TG_META_STATE=ok
}

# _tg_meta_confirmed_unusable <metafile> — true only when find, run on the
# control dir and succeeding, positively shows the record gone or the record
# without its owner-read bit (the reader refuses both).
_tg_meta_confirmed_unusable() {
    local f="$1" out
    out="$(find "${f%/*}" -mindepth 1 -maxdepth 1 -name "${f##*/}" -print 2>/dev/null)" || return 1
    [[ -z "$out" ]] && return 0                                   # listed, and absent
    [[ "$out" == "$f" ]] || return 1
    out="$(find "$f" -prune ! -perm -u=r -print 2>/dev/null)" || return 1
    [[ "$out" == "$f" ]]                                          # present, no owner read
}

# _tg_meta_invalidate <why> — the run can no longer keep its record complete,
# so make the record unusable: remove it, else make it unreadable (chmod needs
# neither space nor write permission). A killed run is then kept as having no
# usable metadata, never judged on a record missing a process group. Sets
# _TG_META_STATE to `invalid` when either step is CONFIRMED, else `broken` —
# a record that may still parse as complete, so tmpdir_guard_run then runs every
# later phase outside the guard. Warns either way; stops recording.
_tg_meta_invalidate() {
    local f="$_TG_META"
    _TG_META=""
    [[ -n "$f" ]] || { _TG_META_STATE=invalid; return 0; }
    rm -f -- "$f" 2>/dev/null || true
    if [[ -e "$f" || -L "$f" ]]; then
        chmod 000 -- "$f" 2>/dev/null || true
    fi
    # Confirmed only on POSITIVE evidence — a probe that ran and said so. A
    # probe that fails proves nothing, and neither do rm's or chmod's own exit
    # statuses (rm -f succeeds on a path it did not remove).
    if _tg_meta_confirmed_unusable "$f"; then
        _TG_META_STATE=invalid
        echo "TMPDIR GUARD: $1 — run metadata invalidated; if this run is killed its dir will be kept" >&2
    else
        _TG_META_STATE=broken
        echo "TMPDIR GUARD: $1, and the run metadata could not be removed or made unreadable — later phases run outside the guard" >&2
    fi
}

# _tg_meta_parse <guard-dir> <name_pid> — strict reader. Sets _tg_m_owner_pid,
# _tg_m_kind, _tg_m_token, _tg_m_pgids (array) and _tg_m_unrecorded (a
# phase_start seq with no phase line, or ""). Returns 0 when well formed, 1 when
# there is no metadata (no control dir, or an invalidated record), 2 for
# anything else: a control dir or file that is not a real entry owned by this
# user, a file without owner read+write permission (invalidated by chmod), a
# bad header or version, an unknown or malformed line, a token of the wrong
# shape for its kind, a duplicate, an unterminated last line (an append cut
# short), or an owner pid other than the one in the directory's name.
_tg_meta_parse() {
    local name_pid="$2" f line="" n=0 seq content
    local -A started=() recorded=()
    _tg_m_owner_pid=""; _tg_m_kind=""; _tg_m_token=""; _tg_m_pgids=(); _tg_m_unrecorded=""
    _tg_meta_path_of "$1"
    f="$_tg_meta_path"
    [[ -e "$_tg_meta_dir" || -L "$_tg_meta_dir" ]] || return 1
    [[ -d "$_tg_meta_dir" && ! -L "$_tg_meta_dir" && -O "$_tg_meta_dir" ]] || return 2
    [[ -e "$f" || -L "$f" ]] || return 1
    [[ -f "$f" && ! -L "$f" && -O "$f" ]] || return 2
    # Mode bits, not access(2): root reads a mode-000 file, and that mode is how
    # an invalidated record is marked when it could not be removed.
    find "$f" -prune -perm -u=rw 2>/dev/null | grep -q . || return 2
    _tg_slurp content "$f" || return 2           # a read error is not a short record
    [[ "$content" == *$'\n' ]] || return 2       # empty, or an append cut short
    _tg_lines "$content"
    for line in ${_tg_l[@]+"${_tg_l[@]}"}; do
        n=$((n + 1))
        if (( n == 1 )); then
            [[ "$line" == "ait_tmpdir_guard_meta 1" ]] || return 2
        elif (( n == 2 )); then
            [[ "$line" =~ ^owner\ ([1-9][0-9]*)\ (proc|bsdinfo|ps|none)\ ([[:graph:]]+)$ ]] || return 2
            _tg_m_owner_pid="${BASH_REMATCH[1]}"
            _tg_m_kind="${BASH_REMATCH[2]}"
            _tg_m_token="${BASH_REMATCH[3]}"
            [[ "$_tg_m_owner_pid" == "$name_pid" ]] || return 2
            _tg_token_ok "$_tg_m_kind" "$_tg_m_token" || return 2
        elif [[ "$line" =~ ^phase_start\ ([1-9][0-9]*)$ ]]; then
            seq="${BASH_REMATCH[1]}"
            [[ -z "${started[$seq]:-}" ]] || return 2
            started[$seq]=1
        elif [[ "$line" =~ ^phase\ ([1-9][0-9]*)\ ([1-9][0-9]*)$ ]]; then
            seq="${BASH_REMATCH[1]}"
            [[ -z "${recorded[$seq]:-}" ]] || return 2
            recorded[$seq]="${BASH_REMATCH[2]}"
            _tg_m_pgids+=("${BASH_REMATCH[2]}")
        else
            return 2
        fi
    done
    (( n >= 2 )) || return 2
    if (( ${#started[@]} > 0 )); then
        for seq in "${!started[@]}"; do
            [[ -n "${recorded[$seq]:-}" ]] || { _tg_m_unrecorded="$seq"; break; }
        done
    fi
    return 0
}

# _tg_pgid_state <pgid> — set _tg_pg_state: empty (kill says "No such
# process"), live (a member answers, or EPERM proves one exists), or unknown.
_tg_pgid_state() {
    local err
    if err="$(LC_ALL=C kill -0 -- "-$1" 2>&1)"; then _tg_pg_state=live; return 0; fi
    case "$err" in
        *"No such process"*) _tg_pg_state=empty ;;
        *"not permitted"*)   _tg_pg_state=live ;;
        *)                   _tg_pg_state=unknown ;;
    esac
}

# _tg_owner_state <pid> <token> <kind> — set _tg_owner: alive | dead | unknown.
# Without the PID-anchor library only a confirmed-absent pid reads dead.
_tg_owner_state() {
    local err
    if declare -F lock_holder_liveness >/dev/null 2>&1; then
        _tg_owner="$(lock_holder_liveness "$1" "$2" "$3")"
        return 0
    fi
    _tg_owner=unknown
    if ! err="$(LC_ALL=C kill -0 "$1" 2>&1)"; then
        [[ "$err" == *"No such process"* ]] && _tg_owner=dead
    fi
    return 0
}

# _tg_stale_verdict <dir> <name_pid> — steps 1-3 of the ladder. Sets
# _tg_verdict to live (a concurrent run: silent), keep:<reason>, or candidate
# (passed on to the holder scan, step 4).
_tg_stale_verdict() {
    local d="$1" name_pid="$2" rc=0 pg
    _tg_meta_parse "$d" "$name_pid" || rc=$?
    if (( rc != 0 )); then
        if kill -0 "$name_pid" 2>/dev/null; then _tg_verdict=live; return 0; fi
        if (( rc == 1 )); then _tg_verdict="keep:no-metadata"; else _tg_verdict="keep:metadata-unreadable"; fi
        return 0
    fi
    _tg_owner_state "$_tg_m_owner_pid" "$_tg_m_token" "$_tg_m_kind"
    case "$_tg_owner" in
        alive) _tg_verdict=live; return 0 ;;
        dead)  ;;
        *)     _tg_verdict="keep:owner-unverified"; return 0 ;;
    esac
    if [[ -n "$_tg_m_unrecorded" ]]; then
        _tg_verdict="keep:phase-unrecorded"; return 0
    fi
    if (( ${#_tg_m_pgids[@]} > 0 )); then
        for pg in "${_tg_m_pgids[@]}"; do
            _tg_pgid_state "$pg"
            case "$_tg_pg_state" in
                empty) ;;
                live)  _tg_verdict="keep:pgid-live:$pg"; return 0 ;;
                *)     _tg_verdict="keep:pgid-unverified:$pg"; return 0 ;;
            esac
        done
    fi
    _tg_verdict=candidate
}

# _tg_only_vanished <readlink output> — true when readlink failed ONLY because
# entries disappeared between the glob and the read (an fd closed, a thread
# exited): such an entry no longer holds anything. Any other error is not.
_tg_only_vanished() {
    local line seen=0
    _tg_lines "$1"
    for line in ${_tg_l[@]+"${_tg_l[@]}"}; do
        [[ "$line" == "readlink: "* ]] || continue
        [[ "$line" == *": No such file or directory" ]] || return 1
        seen=1
    done
    (( seen ))
}

# _tg_proc_links <procdir> — set _tg_cwds (every thread's cwd link) and
# _tg_links (those plus every fd link) under nullglob.
_tg_proc_links() {
    local ng=0
    shopt -q nullglob && ng=1
    shopt -s nullglob
    _tg_tasks=("$1"/task/*)
    _tg_cwds=("$1"/task/*/cwd)
    _tg_links=("${_tg_cwds[@]}" "$1"/fd/*)
    (( ng )) || shopt -u nullglob
}

# _tg_proc_view_complete — true only when the proc mount at $_TG_PROC_ROOT is
# known to list every process: its entry in <root>/mounts is found and carries
# no hidepid that hides processes (invisible / ptraceable — 2 / 4). hidepid=1
# (noaccess) still lists them, and the scan counts them uninspectable. A mount
# whose options cannot be read is NOT complete.
_tg_proc_view_complete() {
    local root phys line opts="" found=0 o tab
    root="$_TG_PROC_ROOT"
    phys="$(cd "$root" 2>/dev/null && pwd -P)" || return 1
    [[ -n "$phys" ]] || return 1
    _tg_mount_escape "$phys"; phys="$_tg_esc"
    _tg_slurp tab "$root/mounts" || return 1
    _tg_lines "$tab"
    for line in ${_tg_l[@]+"${_tg_l[@]}"}; do
        # <source> <mountpoint> <fstype> <options> <dump> <pass>
        if [[ "$line" =~ ^[^\ ]+\ ([^\ ]+)\ proc\ ([^\ ]+)\  && "${BASH_REMATCH[1]}" == "$phys" ]]; then
            found=1; opts="${BASH_REMATCH[2]}"        # the last mount there wins
        fi
    done
    (( found )) || return 1
    local IFS=,
    for o in $opts; do
        case "$o" in
            hidepid=0|hidepid=off|hidepid=1|hidepid=noaccess) ;;
            hidepid=*) return 1 ;;
        esac
    done
    return 0
}

# _tg_socket_under <dir> — step 6: is a socket FILE anywhere inside <dir>? A
# bound unix socket under the dir is a socket file in it, so this replaces
# reading the host-wide net/unix table (whose relative and "@" rows cannot be
# placed). A socket found keeps the dir — stale ones are left for manual
# cleanup; whether one still has a listener is not checked. Returns 0 (found;
# _tg_socket_hit names it), 1 (the whole tree was walked, none), 2 (the walk
# failed: some part of the tree could not be read).
_tg_socket_under() {
    local out rc=0
    _tg_socket_hit=""
    out="$(find "$1" -type s -print -quit 2>/dev/null)" || rc=$?
    if [[ -n "$out" ]]; then _tg_socket_hit="$out"; return 0; fi
    (( rc == 0 )) || return 2
    return 1
}

# _tg_scan_holders <dir...> — step 4 on Linux, over $_TG_PROC_ROOT. Sets
# _tg_held[i] to held:<pid> for the i-th candidate (or "" when no holder was
# seen) and _tg_uninspectable to how many processes could not be inspected.
# (Sockets are step 6, a scan of each candidate's own tree.) Returns 1 when the root holds no process entries — not a /proc;
# the caller falls back to lsof — and 2 when the process list cannot be shown
# complete (_tg_proc_view_complete): nothing is scanned, every candidate kept.
_tg_scan_holders() {
    local root="$_TG_PROC_ROOT" p pid stat st out try ok i ng=0
    local -a procs forms_l=("$@") forms_p=()
    shopt -q nullglob && ng=1
    shopt -s nullglob
    procs=("$root"/[0-9]*)
    (( ng )) || shopt -u nullglob
    (( ${#procs[@]} > 0 )) || return 1
    _tg_proc_view_complete || return 2
    _tg_held=(); _tg_uninspectable=0
    # Match both the path as found and its physical form: link targets read
    # from /proc are canonical, environ and cmdline hold whatever was written.
    for i in "${!forms_l[@]}"; do
        _tg_held[i]=""
        forms_p[i]="$(cd "${forms_l[i]}" 2>/dev/null && pwd -P)" || forms_p[i]=""
        [[ -n "${forms_p[i]}" ]] || forms_p[i]="${forms_l[i]}"
    done
    for p in "${procs[@]}"; do
        pid="${p##*/}"
        [[ "$pid" =~ ^[0-9]+$ ]] || continue
        stat=""
        if ! { IFS= read -r stat || [[ -n "$stat" ]]; } 2>/dev/null < "$p/stat"; then
            [[ -e "$p" ]] && _tg_uninspectable=$((_tg_uninspectable + 1))
            continue                              # gone mid-scan, or unreadable
        fi
        st="${stat##*) }"; st="${st%% *}"
        _tg_proc_links "$p"
        # A zombie holds no cwd and no fd — unless other threads of its group
        # are still running (a leader that exited first), so only a lone one.
        [[ "$st" == Z ]] && (( ${#_tg_tasks[@]} <= 1 )) && continue
        if [[ ! -r "$p/fd" || ! -x "$p/fd" ]] || (( ${#_tg_cwds[@]} == 0 )); then
            [[ -e "$p" ]] && _tg_uninspectable=$((_tg_uninspectable + 1))
            continue
        fi
        ok=0
        for try in 1 2; do
            if out="$(LC_ALL=C readlink -v -- "${_tg_links[@]}" 2>&1)"; then ok=1; break; fi
            _tg_only_vanished "$out" && { ok=1; break; }
            [[ -e "$p" ]] || break
            (( try == 1 )) && _tg_proc_links "$p"   # one retry on a transient failure
        done
        [[ -e "$p" ]] || continue
        _tg_buf=""
        if ! (( ok )) || ! _tg_slurp _tg_buf "$p/environ" "$p/cmdline"; then
            [[ -e "$p" ]] && _tg_uninspectable=$((_tg_uninspectable + 1))
            continue
        fi
        for i in "${!forms_l[@]}"; do
            [[ -z "${_tg_held[i]}" ]] || continue
            if [[ "$out" == *"${forms_l[i]}"* || "$out" == *"${forms_p[i]}"* \
               || "$_tg_buf" == *"${forms_l[i]}"* || "$_tg_buf" == *"${forms_p[i]}"* ]]; then
                _tg_held[i]="held:$pid"
            fi
        done
    done
    _tg_buf=""
    return 0
}

# _tg_lsof_holder <dir> — step 4 off Linux. Sets _tg_lsof to none, held:<pid>,
# or holder-unverified:<why> / no-holder-scan. A non-root lsof cannot see other
# users' processes, so its negative is never accepted. Warnings are enabled
# EXPLICITLY (+w — the default is a build-time choice, and some builds suppress
# them): they are how lsof says its coverage is incomplete (a file system it
# could not stat, a process it could not read), so ANY output other than a
# holder line keeps the dir.
_tg_lsof_holder() {
    local out rc=0
    if ! command -v lsof >/dev/null 2>&1; then _tg_lsof="no-holder-scan"; return 0; fi
    if [[ "$_TG_EUID" != 0 ]]; then _tg_lsof="holder-unverified:lsof-not-root"; return 0; fi
    out="$(LC_ALL=C lsof +w -F p +D "$1" 2>&1)" || rc=$?
    if [[ "$out" =~ (^|$'\n')p([0-9]+) ]]; then
        _tg_lsof="held:${BASH_REMATCH[2]}"
    elif (( rc == 1 )) && [[ -z "$out" ]]; then
        _tg_lsof=none
    else
        _tg_lsof="holder-unverified:lsof-failed"
    fi
    return 0
}

# _tg_report_names <list...> — print at most 5 names, then "… and K more".
_tg_report_names() {
    printf '%s ' "${@:1:5}"
    (( $# > 5 )) && printf '… and %d more' $(( $# - 5 ))
    printf '\n'
}

# _tg_reclaim_stale <base> <label> — find guard dirs of earlier runs with this
# label under <base>, reclaim the provably unused ones, report the rest. Also
# drops metadata files whose directory is gone (removed by hand). Never fails.
_tg_reclaim_stale() {
    local base="$1" label="$2" f base_name pid v i
    local -a kept=() reclaimed=() cands=() verdicts=()
    # NUL-delimited end to end: a base path may legally contain a newline.
    while IFS= read -r -d '' f; do
        [[ "$f" == "$_TG_DIR" ]] && continue
        base_name="${f##*/}"
        pid="${base_name#ait_"${label}"_}"; pid="${pid%%_*}"
        [[ "$pid" =~ ^[0-9]+$ ]] || continue
        _tg_stale_verdict "$f" "$pid"
        case "$_tg_verdict" in
            live)      ;;
            candidate) cands+=("$f") ;;
            *)         kept+=("$base_name(${_tg_verdict#keep:})") ;;
        esac
    done < <(find "$base" -mindepth 1 -maxdepth 1 -type d -name "ait_${label}_*_*" -print0 2>/dev/null | LC_ALL=C sort -z)

    if (( ${#cands[@]} > 0 )); then
        local scan_rc=0
        _tg_scan_holders "${cands[@]}" || scan_rc=$?
        if (( scan_rc == 2 )); then
            for i in "${!cands[@]}"; do verdicts[i]="keep:proc-view-incomplete"; done
        elif (( scan_rc == 0 )); then
            for i in "${!cands[@]}"; do
                if [[ -n "${_tg_held[i]}" ]]; then verdicts[i]="keep:${_tg_held[i]}"
                elif (( _tg_uninspectable > 0 )); then verdicts[i]="keep:holder-unverified:$_tg_uninspectable"
                else verdicts[i]=reclaim
                fi
            done
        else
            for i in "${!cands[@]}"; do
                _tg_lsof_holder "${cands[i]}"
                if [[ "$_tg_lsof" == none ]]; then verdicts[i]=reclaim; else verdicts[i]="keep:$_tg_lsof"; fi
            done
        fi
        for i in "${!cands[@]}"; do
            f="${cands[i]}"; v="${verdicts[i]}"; base_name="${f##*/}"
            # Last check before anything recursive: a killed test can leave a
            # mount (or a same-filesystem bind mount) inside its dir.
            if [[ "$v" == reclaim ]]; then
                local mrc=0
                _tg_mounts_under "$f" || mrc=$?
                case $mrc in
                    0) v="keep:mounted:$_tg_mount_hit" ;;
                    2) v="keep:mounts-unverified" ;;
                esac
            fi
            if [[ "$v" == reclaim ]]; then
                local src=0
                _tg_socket_under "$f" || src=$?
                case $src in
                    0) v="keep:socket:$_tg_socket_hit" ;;
                    2) v="keep:socket-scan-failed" ;;
                esac
            fi
            if [[ "$v" == reclaim ]]; then
                chmod -R u+w "$f" 2>/dev/null || true
                rm -rf -- "$f" 2>/dev/null || true
                if [[ -e "$f" || -L "$f" ]]; then
                    kept+=("$base_name(remove-failed)")       # metadata kept for a retry
                else
                    _tg_meta_path_of "$f"
                    _tg_remove_ctl "$_tg_meta_dir" || true   # else: the orphan sweep retries
                    reclaimed+=("$base_name")
                fi
            else
                kept+=("$base_name(${v#keep:})")
            fi
        done
    fi

    # A control directory whose guard dir is gone protects nothing. A run
    # creates its control dir only after its guard dir exists, so this never
    # races a begin. Only this user's own, real directories are touched.
    while IFS= read -r -d '' f; do
        base_name="${f##*/}"; base_name="${base_name#.}"; base_name="${base_name%"$_TG_META_SUFFIX"}"
        [[ -e "$base/$base_name" || -L "$base/$base_name" ]] && continue
        [[ -d "$f" && ! -L "$f" && -O "$f" ]] || continue
        _tg_remove_ctl "$f" || true
    done < <(find "$base" -mindepth 1 -maxdepth 1 -type d -name ".ait_${label}_*_*${_TG_META_SUFFIX}" -print0 2>/dev/null)

    if (( ${#reclaimed[@]} > 0 )); then
        {
            printf 'TMPDIR GUARD: reclaimed %d guard dir(s) left by killed runs under %s (owner, recorded process groups and every process verified gone): ' "${#reclaimed[@]}" "$base"
            _tg_report_names "${reclaimed[@]}"
        } >&2
    fi
    if (( ${#kept[@]} > 0 )); then
        {
            printf 'TMPDIR GUARD: %d guard dir(s) from earlier runs remain under %s (kept — not provably unused; remove by hand once no process uses them): ' "${#kept[@]}" "$base"
            _tg_report_names "${kept[@]}"
        } >&2
    fi
    return 0
}

tmpdir_guard_begin() {
    local label="${1:-}" base
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

    # Record this run before anything else, so a SIGKILL from here on leaves a
    # directory the next run can judge (KILLED RUNS above).
    _TG_PHASE_SEQ=0
    if ! _tg_meta_create "$_TG_DIR"; then
        echo "TMPDIR GUARD: run metadata not recorded — if this run is killed its dir will be kept" >&2
    fi

    # Directories left by a guarding shell that died without its handler
    # (SIGKILL): reclaimed only when provably unused, otherwise reported.
    _tg_reclaim_stale "$base" "$label"

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
    local rc had_m=0 seq="" outside=0 saved_tmpdir=""
    # Guarded mode records the phase's pgid: the intent BEFORE the fork, the
    # pgid right after, so a gap between the two is visible (KILLED RUNS).
    # A phase is launched INSIDE the guard only when its intent is recorded or
    # the record is confirmed unusable (invalid). When neither holds (broken:
    # the intent append failed and so did removing and chmodding the record,
    # which may still parse as complete with no group in it), the phase runs
    # OUTSIDE the guard, under the original TMPDIR — so nothing uses the guard
    # dir that its record does not account for.
    if [[ -n "$_TG_DIR" && "$_TG_DONE" != 1 ]]; then
        if [[ "$_TG_META_STATE" == ok && -n "$_TG_META" ]]; then
            _TG_PHASE_SEQ=$((_TG_PHASE_SEQ + 1))
            seq="$_TG_PHASE_SEQ"
            if ! printf 'phase_start %s\n' "$seq" 2>/dev/null >>"$_TG_META"; then
                _tg_meta_invalidate "could not record phase $seq before launching it"
                seq=""
            fi
        fi
        [[ "$_TG_META_STATE" == broken ]] && outside=1
    fi
    if (( outside )); then
        _TG_RAN_OUTSIDE=1
        echo "TMPDIR GUARD: this phase runs OUTSIDE the guard (original TMPDIR) — its leftovers are not inspected" >&2
        saved_tmpdir="$TMPDIR"
        if (( _TG_ORIG_SET )); then export TMPDIR="$_TG_ORIG"; else unset TMPDIR; fi
    fi
    [[ "$-" == *m* ]] && had_m=1
    set -m
    "$@" </dev/null &
    _TG_CHILD=$!
    (( had_m )) || set +m
    (( outside )) && export TMPDIR="$saved_tmpdir"
    # A missing pgid line already keeps the dir (phase-unrecorded); the record
    # is invalidated too, so the failure is announced and recording stops.
    if [[ -n "$seq" ]] && ! printf 'phase %s %s\n' "$seq" "$_TG_CHILD" 2>/dev/null >>"$_TG_META"; then
        _tg_meta_invalidate "could not record the process group of phase $seq"
    fi
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
    _TG_LEFTOVER_COUNT=""
    if [[ -L "$_TG_DIR" || ( -e "$_TG_DIR" && ! -d "$_TG_DIR" ) ]]; then
        # The phase replaced the guard directory with a symlink (dangling or
        # not) or a non-directory. Nothing was inspected, so the count stays
        # empty: a strict caller must not read this as "nothing left". Remove
        # the entry itself; rm -f never follows a symlink to its target.
        echo "TMPDIR LEFTOVERS: the per-run TMPDIR ($_TG_DIR) was replaced by a symlink or non-directory — not inspected; removing that entry" >&2
        rm -f -- "$_TG_DIR" 2>/dev/null || true
        if [[ -e "$_TG_DIR" || -L "$_TG_DIR" ]]; then
            echo "TMPDIR GUARD: could not remove $_TG_DIR" >&2
        fi
    elif [[ -d "$_TG_DIR" ]]; then
        local listing listed=0
        if listing="$(find "$_TG_DIR" -mindepth 1 -maxdepth 1 2>/dev/null)"; then
            listed=1
        fi
        while IFS= read -r f; do
            [[ -n "$f" ]] || continue
            f="${f##*/}"
            _tg_expected_entry "$f" && continue
            left+=("$f")
        done < <(printf '%s\n' "$listing" | LC_ALL=C sort)
        n=${#left[@]}
        (( listed )) && (( ! _TG_RAN_OUTSIDE )) && _TG_LEFTOVER_COUNT="$n"
        if (( n > 0 )); then
            shown=$(( n < _TG_REPORT_CAP ? n : _TG_REPORT_CAP ))
            {
                printf 'TMPDIR LEFTOVERS (%d): ' "$n"
                printf '%s ' "${left[@]:0:shown}"
                (( n > shown )) && printf '… and %d more' $(( n - shown ))
                printf '\n'
            } >&2
        fi
        # A mount the phase left inside the dir must not be walked into: the
        # recursive chmod and rm would change and delete the mounted data. So
        # the removal runs only when the mount table was read and shows nothing
        # at or below the dir; otherwise the dir is left (and reported) for a
        # later run, which keeps it on the same evidence.
        local mrc=0 outcome="removed"
        _tg_mounts_under "$_TG_DIR" || mrc=$?
        if (( mrc == 0 )); then
            _TG_LEFTOVER_COUNT=""; outcome="NOT removed: a mount at or below it ($_tg_mount_hit)"
            echo "TMPDIR GUARD: $_TG_DIR has a mount at or below it ($_tg_mount_hit) — not removed; unmount it, then remove the dir by hand" >&2
        elif (( mrc == 2 )); then
            _TG_LEFTOVER_COUNT=""; outcome="NOT removed: the mount table could not be read"
            echo "TMPDIR GUARD: could not verify that nothing is mounted below $_TG_DIR — not removed; remove it by hand once you have checked" >&2
        else
            chmod -R u+w "$_TG_DIR" 2>/dev/null || true
            rm -rf -- "$_TG_DIR" 2>/dev/null || true
            if [[ -e "$_TG_DIR" ]]; then
                outcome="NOT fully removed"
                echo "TMPDIR GUARD: could not fully remove $_TG_DIR" >&2
            fi
        fi
        # Report the OBSERVED outcome, after the attempt — never "removed" for
        # a dir that is still there.
        if (( n > 0 )); then
            if [[ "$outcome" == removed ]]; then
                printf 'TMPDIR LEFTOVERS: these were left in the per-run TMPDIR (%s) and are now removed; attribute each by its name prefix\n' "$_TG_DIR" >&2
            else
                printf 'TMPDIR LEFTOVERS: these were left in the per-run TMPDIR (%s) and were %s; attribute each by its name prefix\n' "$_TG_DIR" "$outcome" >&2
            fi
        fi
    else
        (( _TG_RAN_OUTSIDE )) || _TG_LEFTOVER_COUNT=0   # truly absent: nothing left
    fi
    # The run's metadata goes with its directory. If the directory could not be
    # removed, keep it: the next run can then still judge (and retry) it.
    if [[ -n "$_TG_META_DIR" && ! -e "$_TG_DIR" && ! -L "$_TG_DIR" ]]; then
        if ! _tg_remove_ctl "$_TG_META_DIR" && [[ -e "$_TG_META_DIR" ]]; then
            echo "TMPDIR GUARD: could not remove the run's control dir $_TG_META_DIR (not empty, a mount below it, or the mount table unreadable)" >&2
        fi
    fi
    if (( _TG_ORIG_SET )); then export TMPDIR="$_TG_ORIG"; else unset TMPDIR; fi
    return 0
}
