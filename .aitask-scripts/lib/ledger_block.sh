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

# EXIT-trap form: capture the incoming status, release errexit-safely, preserve
# a meaningful nonzero status, and flip 0 -> 1 only when the release itself
# failed (a bare release here could turn a die's status into a generic 1 or a
# success into a spurious failure under set -e).
ait_ledger_lock_exit_trap() {
    local rc=$?
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
            awk -v anchor="$anchor_re" -v hdr="$header" -v cmt="$comment" \
                -v mk="$marker" -v body="$body" '
                $0 ~ anchor && !done {
                    print hdr; print cmt; print "";
                    print mk;
                    if (body != "") { print ">"; print body }
                    print "";
                    done = 1
                }
                { print }
            ' "$file" > "$tmp"
            mv "$tmp" "$file"
            return 0
        fi
        # Anchor absent: fall through to EOF creation.
    fi

    if [[ $have_section -eq 1 && "$append_at" == "section_end" ]]; then
        # Insert before the next '##' header after ours; EOF when it is last.
        awk -v hdr="$header_re" -v mk="$marker" -v body="$body" '
            BEGIN { inside = 0; done = 0 }
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
        ' "$file" > "$tmp"
        mv "$tmp" "$file"
        return 0
    fi

    {
        cat "$file"
        # Ensure a trailing newline before appending.
        [[ -n "$(tail -c1 "$file" 2>/dev/null)" ]] && echo
        if [[ $have_section -eq 0 ]]; then
            echo
            echo "$header"
            echo "$comment"
        fi
        echo
        echo "$marker"
        if [[ -n "$body" ]]; then
            echo ">"
            printf '%s\n' "$body"
        fi
    } > "$tmp"
    mv "$tmp" "$file"
}

fi
