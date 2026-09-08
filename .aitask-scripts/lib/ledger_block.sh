#!/usr/bin/env bash
# ledger_block.sh — generic marker-block ledger substrate, bash half (t1657_1).
#
# The shell twin of lib/ledger_block.py. An append-only marker-block ledger is a
# '##' section of a task file holding blockquote records of the form:
#
#     > **<icon> <namespace>:<name>** key=value key=value
#     >
#     > <body line>
#
# '## Gate Runs' (namespace 'gate') was the first; '## Inbox' (namespace 'note',
# t1657_2) is the second. This file owns what is common to both: the per-task
# append mutex, marker-line assembly, and section ensure-and-append.
#
# What deliberately stays with each consumer: the key vocabulary, the
# status->icon mapping, attempt arithmetic, body-line rendering (the gate ledger
# uses '> Label: value'; the note ledger uses a '> | ' sentinel as its injection
# defence), and any backend delegation.
#
# Depends on lib/stale_lock.sh (already generic) and lib/terminal_compat.sh for
# die/warn. The caller sources both before this file.

if [[ -z "${_AIT_LEDGER_BLOCK_LOADED:-}" ]]; then
    _AIT_LEDGER_BLOCK_LOADED=1

# --- Per-task append mutex --------------------------------------------------
#
# Serializes concurrent appends to the same task file, namespaced so two ledgers
# on one task do not share a key. Built on lib/stale_lock.sh, whose stale reclaim
# is single-winner (guarded observation+destruction) and never displaces a live
# holder — see that file for the invariants.

_AIT_LEDGER_LOCK_DIR=""
_AIT_LEDGER_LOCK_TOKEN=""

# ait_ledger_lock_acquire <namespace> <key> <reclaim_label> <fail_label> \
#                         [retries] [sleep]
#
# TWO labels, deliberately — the gate ledger uses different wording in the two
# places, and tests/test_gate_lock_characterization.sh pins BOTH:
#
#   <reclaim_label>  reaches stale_lock_acquire, which renders
#                    "Removing stale <reclaim_label> for <key> (age: …)".
#                    Gate passes "gate lock".
#   <fail_label>     the exhaustion die: "Failed to acquire <fail_label> for
#                    <key> after <n> attempts". Gate passes "gate append lock"
#                    (Test 2a pins that exact prefix).
#
# Collapsing these into one parameter reads as a simplification and silently
# rewrites the reclaim warning — which is how it was caught here.
ait_ledger_lock_acquire() {
    local ns="$1" key="$2" reclaim_label="$3" fail_label="$4"
    local retries="${5:-20}" nap="${6:-0.3}"
    local lock_dir
    lock_dir="$(ait_lock_dir "${ns}_${key}")" || \
        die "Failed to resolve ${reclaim_label} base for $key"
    # Opts in to markerless guard reclaim (t1598): a ledger append is a fixed
    # handful of file ops under the guard in every shipped version.
    if ! stale_lock_acquire "$lock_dir" "$retries" "$nap" "${reclaim_label} for $key" \
            "$_STALE_LOCK_GC_WINDOW_DEFAULT"; then
        # The prefix is pinned by tests/test_gate_lock_characterization.sh
        # (Test 2a); the describe suffix is the recovery hint (t1496).
        die "Failed to acquire ${fail_label} for ${key} after ${retries} attempts$(stale_lock_describe "$lock_dir")"
    fi
    _AIT_LEDGER_LOCK_DIR="$lock_dir"
    _AIT_LEDGER_LOCK_TOKEN="$STALE_LOCK_TOKEN"
}

ait_ledger_lock_release() {
    local rc=0
    if [[ -n "$_AIT_LEDGER_LOCK_DIR" ]]; then
        stale_lock_release "$_AIT_LEDGER_LOCK_DIR" "$_AIT_LEDGER_LOCK_TOKEN" || rc=1
    fi
    _AIT_LEDGER_LOCK_DIR=""
    _AIT_LEDGER_LOCK_TOKEN=""
    return "$rc"
}

# Explicit-release form: a genuinely retained lock (leaked guard, undeletable
# dir) must surface as a command failure, never as silent success with the key
# wedged (t1496 invariant 6).
ait_ledger_lock_release_checked() {
    if ! ait_ledger_lock_release; then
        die "ledger lock not released — the key stays wedged (see warning above)"
    fi
}

# Is this function the FIRST command of the installed EXIT trap? (t1681)
#
# The check exists because the whole contract below rests on `$?` still holding
# the guarded section's status, and only the first command in a trap string sees
# it. `trap -p` inside a command substitution reports the PARENT's trap (the
# POSIX `saved=$(trap)` idiom) and bash renders it as `trap -- 'HANDLER' EXIT`;
# tests/test_ledger_lock_exit_trap.sh group 0 pins both facts.
#
# Fails SAFE in every direction it cannot judge — no EXIT trap, someone else's
# handler, or a rendering this cannot parse all return 0 (= "no complaint"), so
# an unexpected shell degrades to the pre-t1681 behaviour instead of inventing a
# failure. That degradation is only invisible if nobody looks, which is why the
# test file asserts the guard actually FIRES rather than merely that the exit
# status is nonzero.
_ait_ledger_exit_trap_is_first() {
    local spec handler rest
    spec="$(trap -p EXIT 2>/dev/null)" || return 0
    case "$spec" in *ait_ledger_lock_exit_trap*) ;; *) return 0 ;; esac
    handler="${spec#trap -- \'}"
    [[ "$handler" != "$spec" ]] || return 0
    handler="${handler#"${handler%%[![:space:]]*}"}"
    rest="${handler#ait_ledger_lock_exit_trap}"
    if [[ "$rest" != "$handler" ]]; then
        # Matched at the start — make sure it is a whole word and not a prefix
        # of some longer name. The trailing "'" is the close of the rendering.
        case "$rest" in ""|[[:space:]]*|";"*|"'"*|"&"*|"|"*|")"*) return 0 ;; esac
    fi
    return 1
}

# EXIT-trap form: capture the incoming status, release errexit-safely, preserve
# a meaningful nonzero status, and flip 0 -> 1 only when the release itself
# failed (a bare release here could turn a die's status into a generic 1 or a
# success into a spurious failure under set -e).
#
# TWO SANCTIONED SPELLINGS, and no third (t1681):
#
#     trap 'ait_ledger_lock_exit_trap' EXIT                     # first command
#     trap 'rc=$?; my_cleanup; ait_ledger_lock_exit_trap "$rc"' EXIT
#
# `$?` reflects the command that ran immediately before this one, so a consumer
# that needs its own cleanup and writes the natural-looking
# `trap 'my_cleanup; ait_ledger_lock_exit_trap' EXIT` DESTROYS the status:
# my_cleanup succeeds, `$?` becomes 0, and the trap exits 0 for a section that
# died. Measured, not theorised — in t1657_2 that chain made a `die` from
# ait_ledger_lock_release_checked exit 0 and `ait note` report NOTE_APPENDED
# for an append whose lock was wedged. A failure reported as success is strictly
# worse than a wrong error code, so the misuse is DETECTED here rather than
# merely documented: the no-arg form checks its own position in the trap string
# and refuses to report success when it is not first.
#
# The optional argument is what makes a chained consumer correct rather than
# merely forbidden. It is the status to exit with, and it is validated against
# the real shell-status domain 0-255: `exit` truncates modulo 256, so an
# unvalidated 256 or 512 would exit 0 — re-opening, through this very parameter,
# the false success the guard above exists to close.
ait_ledger_lock_exit_trap() {
    local rc=$? ok=0                  # `local rc=$?` MUST stay the first command
    if [[ $# -gt 0 ]]; then
        rc="$1"
        # Pattern-only, deliberately: bash arithmetic reads a leading zero as
        # OCTAL, so `[[ 010 -le 255 ]]` accepts 010 and would exit 8 for a
        # caller who wrote decimal ten, while `08` / `099` are invalid octal and
        # make bash print "value too great for base" from inside an exit path.
        case "$rc" in
            [0-9]|[1-9][0-9]|1[0-9][0-9]|2[0-4][0-9]|25[0-5]) ok=1 ;;
            *)                                                ok=0 ;;
        esac
        if [[ $ok -eq 0 ]]; then
            warn "ait_ledger_lock_exit_trap: status '$1' is not a decimal 0-255 — treating as failure"
            rc=1
        fi
    elif ! _ait_ledger_exit_trap_is_first; then
        warn "ait_ledger_lock_exit_trap ran behind another command in the EXIT trap, so the dying status was lost. Install it first — trap 'ait_ledger_lock_exit_trap' EXIT — or pass the status explicitly: trap 'rc=\$?; my_cleanup; ait_ledger_lock_exit_trap \"\$rc\"' EXIT. Reporting a generic failure because the real status cannot be recovered here."
        # UNCONDITIONAL. `rc` currently holds the status of whatever ran in
        # front of us, which is NOT the section's status and must not be
        # published as if it were: a cleanup returning 42 would exit 42, a
        # number that looks meaningful and is not.
        rc=1
    fi
    if ! ait_ledger_lock_release; then
        if [[ $rc -eq 0 ]]; then rc=1; fi
    fi
    exit "$rc"
}

# --- Block rendering --------------------------------------------------------

# ait_ledger_marker <namespace> <name> <icon> [key=value ...]
#
# Echo one marker line. Resolves nothing — pairs are emitted in the order given,
# so key ORDER is the caller's contract, not this function's.
ait_ledger_marker() {
    local ns="$1" name="$2" icon="$3"
    shift 3
    local marker="> **${icon} ${ns}:${name}**" kv
    for kv in "$@"; do
        marker="${marker} ${kv}"
    done
    printf '%s' "$marker"
}

# --- Section ensure-and-append ----------------------------------------------

# _ait_ledger_swap_tmp <producer_status> <tmp> <file>
#
# The ONLY sanctioned tempfile->target swap in this file. Every write path in
# ait_ledger_append_section routes through it, because the three that did their
# own `mv` unconditionally DESTROYED the target whenever the producer failed
# (t1741): BSD awk rejects a newline inside a `-v` assignment, exits 2 with EMPTY
# output, and the following `mv` published that emptiness over an 11KB task file
# while the function still returned 0 and `ait note` printed NOTE_APPENDED.
#
# Fails closed in every direction: on a producer failure, an empty result, or a
# failed rename, the target is left BYTE-FOR-BYTE untouched, the tempfile is
# removed, and the status is non-zero so the caller can report a real failure.
_ait_ledger_swap_tmp() {
    local st="$1" tmp="$2" file="$3" why=""

    # Test-only fault injection through a documented seam. The three callers of
    # the seam are separate PROCESSES, so their failure contracts cannot be
    # driven by shadowing a command in a test shell; this is how
    # tests/test_ledger_block_append_integrity.sh reaches them. Placed here
    # rather than at the top of the function so the real guard below still runs
    # — the forced failure exercises the cleanup and the untouched target, not
    # just the return status. Never set in normal operation; mirrors
    # AIT_NOTE_FAIL_AFTER_APPEND in aitask_note.sh.
    [[ -z "${AIT_LEDGER_FAIL_APPEND:-}" ]] || st=99

    if [[ "$st" -ne 0 ]]; then
        why="block producer exited $st"
    elif [[ ! -s "$tmp" ]]; then
        # Unreachable on success: every path reprints the whole input plus at
        # least a marker line, so an empty result IS a producer that failed
        # without saying so — the BSD-awk shape, which exits non-zero AND
        # empties the file, but which a future producer might reach silently.
        why="block producer wrote an empty file"
    fi

    if [[ -n "$why" ]]; then
        rm -f "$tmp"
        warn "ait_ledger_append_section: $why — '$file' left unchanged"
        return 1
    fi

    if ! mv "$tmp" "$file"; then
        rm -f "$tmp"
        warn "ait_ledger_append_section: could not replace '$file' — left unchanged"
        return 1
    fi
    return 0
}

# ait_ledger_append_section <file> <header> <comment> <marker> <body> \
#                           [create_before] [append_at]
#
# Append one block (marker + optional body) to <header>'s section in <file>,
# creating the section when absent. Writes via an adjacent tempfile + mv.
#
#   <body>          pre-rendered body lines (newline-separated), or "" for none.
#   [create_before] header text before which a NEWLY CREATED section is inserted;
#                   "" (default) creates it at EOF. This is what lets '## Inbox'
#                   land above '## Gate Runs'.
#   [append_at]     "eof" (default) appends at end of file — the gate ledger's
#                   historical behaviour, correct because it is the terminal
#                   section, and preserved exactly so this extraction changes no
#                   bytes. "section_end" appends at the end of the section
#                   itself, which a non-terminal ledger requires.
#
# RETURNS 0 when the block was written, non-zero when it was NOT — and in the
# non-zero case <file> is byte-for-byte unchanged (t1741). Callers must branch
# on it: reporting success for a failed append is what let a truncation be
# committed. NOTHING from the caller reaches awk through `-v`, which runs escape
# processing (`C:\temp` -> `C:<TAB>emp` even on GNU awk) and rejects a literal
# newline; values are passed through ENVIRON, which is POSIX and does neither.
ait_ledger_append_section() {
    local file="$1" header="$2" comment="$3" marker="$4" body="$5"
    local create_before="${6:-}" append_at="${7:-eof}"

    case "$append_at" in
        eof|section_end) ;;
        *) die "ait_ledger_append_section: append_at must be 'eof' or 'section_end', got '$append_at'" ;;
    esac

    local header_re="^##[[:space:]]+${header#\#\# }[[:space:]]*$"
    local have_section=0
    grep -qE "$header_re" "$file" && have_section=1

    local tmp
    tmp="$(dirname "$file")/.aitask_ledger.$$.tmp"

    if [[ $have_section -eq 0 && -n "$create_before" ]]; then
        # Create the section immediately BEFORE the anchor header.
        local anchor_re="^##[[:space:]]+${create_before#\#\# }[[:space:]]*$"
        if grep -qE "$anchor_re" "$file"; then
            local st=0
            AIT_LB_ANCHOR="$anchor_re" AIT_LB_HDR="$header" AIT_LB_CMT="$comment" \
            AIT_LB_MK="$marker" AIT_LB_BODY="$body" \
            awk '
                BEGIN {
                    anchor = ENVIRON["AIT_LB_ANCHOR"]; hdr = ENVIRON["AIT_LB_HDR"]
                    cmt    = ENVIRON["AIT_LB_CMT"];    mk  = ENVIRON["AIT_LB_MK"]
                    body   = ENVIRON["AIT_LB_BODY"]
                }
                $0 ~ anchor && !done {
                    print hdr; print cmt; print "";
                    print mk;
                    if (body != "") { print ">"; print body }
                    print "";
                    done = 1
                }
                { print }
            ' "$file" > "$tmp" || st=$?
            _ait_ledger_swap_tmp "$st" "$tmp" "$file" || return 1
            return 0
        fi
        # Anchor absent: fall through to EOF creation.
    fi

    if [[ $have_section -eq 1 && "$append_at" == "section_end" ]]; then
        # Insert before the next '##' header after ours; EOF when it is last.
        local st=0
        AIT_LB_HDRRE="$header_re" AIT_LB_MK="$marker" AIT_LB_BODY="$body" \
        awk '
            BEGIN {
                inside = 0; done = 0
                hdr  = ENVIRON["AIT_LB_HDRRE"]; mk = ENVIRON["AIT_LB_MK"]
                body = ENVIRON["AIT_LB_BODY"]
            }
            !done && inside && /^##[[:space:]]/ {
                print mk;
                if (body != "") { print ">"; print body }
                print "";
                inside = 0; done = 1
            }
            $0 ~ hdr { inside = 1 }
            { print }
            END {
                if (!done) {
                    print "";
                    print mk;
                    if (body != "") { print ">"; print body }
                }
            }
        ' "$file" > "$tmp" || st=$?
        _ait_ledger_swap_tmp "$st" "$tmp" "$file" || return 1
        return 0
    fi

    # Build the appended tail FIRST, so the producer below is two guarded
    # commands rather than six unguarded ones. Byte-for-byte the same output.
    local suffix="" last_byte="" st_tail=0
    # Ensure a trailing newline before appending. A `tail` that FAILS is
    # indistinguishable from a file that already ends in one — both yield an
    # empty capture — so treat it as a producer failure rather than guessing and
    # renaming that guess over the target. Captured declare-first: `local x=$(…)`
    # returns `local`'s status, not the command's.
    last_byte="$(tail -c1 "$file" 2>/dev/null)" || st_tail=$?
    if [[ "$st_tail" -ne 0 ]]; then
        warn "ait_ledger_append_section: could not read the final byte of '$file' — left unchanged"
        return 1
    fi
    if [[ -n "$last_byte" ]]; then suffix=$'\n'; fi
    if [[ $have_section -eq 0 ]]; then
        suffix="${suffix}"$'\n'"${header}"$'\n'"${comment}"$'\n'
    fi
    suffix="${suffix}"$'\n'"${marker}"$'\n'
    if [[ -n "$body" ]]; then
        suffix="${suffix}>"$'\n'"${body}"$'\n'
    fi

    local st=0
    (
        # NO `set -e` here: bash suppresses errexit for a compound command on the
        # left of `||`, and setting it inside the subshell does NOT restore it
        # (measured) — a failing `cat` would sail past it. A brace group is worse
        # still: it reports only its LAST command's status, so a failed `cat`
        # used to be masked by the echoes that followed and the file's whole
        # content was replaced by a lone marker block. Guard each producer.
        cat "$file"           || exit 90
        printf '%s' "$suffix" || exit 91
    ) > "$tmp" || st=$?
    _ait_ledger_swap_tmp "$st" "$tmp" "$file" || return 1
    return 0
}

fi
