#!/usr/bin/env bash
# lock_record.sh - Single reader for a task lock's RECORD (t1657_4).
# Idempotent: safe to source multiple times.
#
# `aitask_lock.sh --check <bare-id>` has a strict stdout contract: stdout IS the
# lock record — the raw lock-file YAML — and nothing else, with absence signalled
# by exit status 1 and empty stdout (see the STDOUT CONTRACT comment at
# aitask_lock.sh:402). Two callers need the same four fields out of it:
#
#   * aitask_note.sh::note_sender_is_self  — "is that anchor MY session?"
#   * aitask_live_endpoint.sh              — "is that anchor alive, and where?"
#
# They ask different questions of the same parse, so the PARSE is what belongs
# here — not the verdict. Keeping one copy means a future field addition or a
# change in the record's shape has exactly one reader to update, instead of two
# that can silently disagree about what a lock says.
#
# Sourced by:
#   .aitask-scripts/aitask_note.sh
#   .aitask-scripts/aitask_live_endpoint.sh

[[ -n "${_AIT_LOCK_RECORD_LOADED:-}" ]] && return 0
_AIT_LOCK_RECORD_LOADED=1

_LOCK_RECORD_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Populated by lock_record_read. Always all four, always reset on every call —
# a partial record must never leave a previous call's value visible.
LOCK_REC_HOST=""
LOCK_REC_PID=""
LOCK_REC_TOKEN=""
LOCK_REC_KIND=""

# lock_record_read <bare-task-id>
#
# Run `aitask_lock.sh --check` once and split the record into the four fields
# above. Returns 0 when a record was read, 1 when the task is not locked (or the
# check could not produce a record).
#
# THE ID MUST BE BARE. Measured: `aitask_lock.sh --check t1669` prints NOTHING
# while `--check 1669` works, so a 't'-prefixed id here reads as "not locked" —
# a silent wrong answer, not an error. Callers canonicalise before calling.
#
# A field the record does not carry comes back EMPTY, never defaulted. That
# matters most for `pid`: locks written before the PID anchor existed (t1465)
# have no `pid:` line at all, and inventing a value for them would turn "this
# lock cannot say who holds it" into a claim about a process. Consumers pass the
# empty value straight to lock_holder_liveness, which answers `unknown` — the
# fail-safe direction.
lock_record_read() {
    local bare="${1:-}" out
    LOCK_REC_HOST=""; LOCK_REC_PID=""; LOCK_REC_TOKEN=""; LOCK_REC_KIND=""
    [[ -n "$bare" ]] || return 1

    out="$("$_LOCK_RECORD_LIB_DIR/../aitask_lock.sh" --check "$bare" 2>/dev/null || true)"
    [[ -n "$out" ]] || return 1

    # The four LOCK_REC_* are this function's return value — read by
    # aitask_note.sh and aitask_live_endpoint.sh after the call, not here.
    # shellcheck disable=SC2034
    {
    LOCK_REC_HOST="$(printf '%s\n' "$out" | sed -n 's/^hostname: //p' | head -n1)"
    LOCK_REC_PID="$(printf '%s\n' "$out" | sed -n 's/^pid: //p' | head -n1)"
    LOCK_REC_TOKEN="$(printf '%s\n' "$out" | sed -n 's/^pid_starttime: //p' | head -n1)"
    LOCK_REC_KIND="$(printf '%s\n' "$out" | sed -n 's/^pid_starttime_kind: //p' | head -n1)"
    }
    return 0
}
