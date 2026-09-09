#!/usr/bin/env bash
# aitask_agent_sessions.sh - Locked writer for the framework session store (t1705_2).
#
# The store lives at `~/.config/aitasks/agent_sessions.json` (override with
# `AITASKS_AGENT_SESSIONS_FILE`). It records one entry per code agent across
# every aitasks tmux session and project on this machine, keyed by
# `(realpath(project_root), tmux_window_name, window_slot)`, plus the freeze /
# restore lifecycle state for each.
#
# This script is the ONLY writer. It holds the `registry_lock.sh` mutex around a
# read-modify-write and delegates all parsing/policy to the lock-free primitive
# `lib/agent_sessions.py`. Readers (the TUIs) read the JSON directly with no
# lock: every write lands via `os.replace`, so a reader always observes one
# whole generation. `list` and `show` therefore take NO lock (same rule as
# aitask_agent_marks.sh's `list`, t1598).
#
# Callers are Python TUIs, sibling scripts and the SessionStart hook — never a
# SKILL.md — so per `aidocs/framework/aitasks_extension_points.md` this script
# needs no code-agent allow-list entries and no `ait` dispatcher case.
#
# ---------------------------------------------------------------------------
# CALLER OBLIGATION: stamp the pane, and only after a success (t1705_2 A8)
#
# This store NEVER touches tmux. After `upsert` prints `UPSERTED:<id>|…`, the
# CALLER must stamp its own pane with `@aitask_record=<id>` — use
# `ait_stamp_record` from `lib/agent_sessions.sh`, which routes through the
# sanctioned tmux gateway. Do it ONLY on a success line: a stamp without a
# stored record is a dangling join, and a stored record without a stamp breaks
# the identity handoff every later restart/restore path depends on.
#   * the SessionStart hook (t1705_3) stamps on the normal path;
#   * the freeze engine (t1705_4) stamps on its fallback path.
# ---------------------------------------------------------------------------
#
# Verbs (mutating verbs take the lock; `list` / `show` do not):
#   upsert  --root <r> --window <w> --pane <id> --pane-pid <pid>
#           [--id <rid>] [--session <name>] [--session-id <sid>]
#           [--transcript <p>] [--agent-string <s>] [--operation <op>]
#           [--task-id <t>] [--restore-of <rid> --nonce <n>]
#   freeze-begin      <id> --owner-pid <pid> --capture-ansi <p>
#                          --capture-txt <p> --lines <n> [--phase <t>]
#   freeze-commit     <id> --nonce <n> --pane <pane_id|""> --pane-pid <pid|0>
#   freeze-abort      <id> --nonce <n>
#   restore-begin     <id> --owner-pid <pid> --mode resume|repick
#   restore-launched  <id> --nonce <n> --pane <id> --pane-pid <pid>
#   restore-confirm   <id> --nonce <n> --pane <id> --pane-pid <pid>
#   restore-abort     <id> --nonce <n> [--error <reason>]
#   standin-respawned <id> --nonce <n> --pane <id> --pane-pid <pid>
#   lease-take        <id> --owner-pid <pid>
#   lease-release     <id> --nonce <n>
#   drop              <id> [--nonce <n>]
#   list  [--state <s>] [--root <r>]
#   show  <id>
#   purge --observed <file>
#
# `--owner-pid` is REQUIRED on exactly the three lease-minting verbs and is the
# pid of the COORDINATOR — the detached `aitask_frozen.sh` process that outlives
# the respawn — never this wrapper's `$$`. There is deliberately NO fallback:
# a default here is indistinguishable from a correct call at the wire and
# silently degrades the lease's staleness test to a bare 60s timer, letting
# reconcile seize a live coordinator's operation (t1705_2 A7).
#
# Record ids and nonces are validated as canonical 8-hex here, BEFORE they reach
# Python: both flow into the capture directory (which `drop` deletes) and into
# the stand-in command string handed to `respawn-pane` (t1705_2 A9).
#
# Exit codes:
#   0  success
#   2  usage error
#   3  LOCK_BUSY                  - another process holds the mutex; NOTHING written.
#                                   Unreachable for `list` / `show`, which take no lock.
#   4  ERROR                      - the store is corrupt/unreadable; NOTHING written
#   5  TRANSITION_REFUSED         - illegal (state, verb); NOTHING written
#   6  NONCE_MISMATCH             - lost the race to reconcile; NOTHING written
#   7  RESTORE_SESSION_MISMATCH   - resumed a different session (last_error IS persisted)
#   8  LEASE_HELD                 - a live coordinator owns this record

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"
# shellcheck source=lib/registry_lock.sh
source "$SCRIPT_DIR/lib/registry_lock.sh"

SESSIONS_FILE="${AITASKS_AGENT_SESSIONS_FILE:-$HOME/.config/aitasks/agent_sessions.json}"
# Mutex dir for serializing the read-modify-write. Derived from SESSIONS_FILE so
# it follows AITASKS_AGENT_SESSIONS_FILE overrides (tests included) — a lock
# keyed to the default path while the data went elsewhere would serialize
# nothing.
SESSIONS_LOCK_DIR="${SESSIONS_FILE}.lockd"

# Keypress-path timeout: long enough to ride out a concurrent write, short
# enough that a jammed lock reports back rather than freezing a TUI.
WRITE_LOCK_TIMEOUT=2
# Background maintenance can afford to wait for a contended lock.
PURGE_LOCK_TIMEOUT=10

SESSIONS_PY="$SCRIPT_DIR/lib/agent_sessions.py"

usage() {
    cat >&2 <<'EOF'
Usage: aitask_agent_sessions.sh upsert --root <r> --window <w> --pane <id> --pane-pid <pid> [...]
       aitask_agent_sessions.sh freeze-begin <id> --owner-pid <pid> --capture-ansi <p> --capture-txt <p> --lines <n> [--phase <t>]
       aitask_agent_sessions.sh freeze-commit <id> --nonce <n> --pane <p> --pane-pid <pid>
       aitask_agent_sessions.sh freeze-abort <id> --nonce <n>
       aitask_agent_sessions.sh restore-begin <id> --owner-pid <pid> --mode resume|repick
       aitask_agent_sessions.sh restore-launched|restore-confirm|standin-respawned <id> --nonce <n> --pane <p> --pane-pid <pid>
       aitask_agent_sessions.sh restore-abort <id> --nonce <n> [--error <reason>]
       aitask_agent_sessions.sh lease-take <id> --owner-pid <pid>
       aitask_agent_sessions.sh lease-release <id> --nonce <n>
       aitask_agent_sessions.sh drop <id> [--nonce <n>]
       aitask_agent_sessions.sh list [--state <s>] [--root <r>]
       aitask_agent_sessions.sh show <id>
       aitask_agent_sessions.sh purge --observed <file>
EOF
    exit 2
}

die_usage() {
    echo "ERROR:$1" >&2
    exit 2
}

# Canonical 8-hex, checked before the value reaches Python (t1705_2 A9).
require_hex_id() {
    local value="${1:-}" label="$2"
    [[ "$value" =~ ^[0-9a-f]{8}$ ]] || die_usage "$label must be 8 lowercase hex: '$value'"
}

# A positive integer. Used for --owner-pid, which must never default (A7).
require_positive_int() {
    local value="${1:-}" label="$2"
    [[ "$value" =~ ^[1-9][0-9]*$ ]] || die_usage "$label must be a positive integer: '$value'"
}

# Scan a flat argument list for `--name` and echo its value ("" when absent).
arg_value() {
    local want="$1"; shift
    while [ $# -gt 0 ]; do
        if [ "$1" = "$want" ]; then
            printf '%s' "${2:-}"
            return 0
        fi
        shift
    done
    printf ''
}

# Is `--name` present at all? (distinguishes "absent" from "present but empty")
has_arg() {
    local want="$1"; shift
    while [ $# -gt 0 ]; do
        [ "$1" = "$want" ] && return 0
        shift
    done
    return 1
}

# Acquire the mutex or report LOCK_BUSY and exit 3. NEVER proceed unlocked:
# registry_lock_acquire returns 1 rather than stealing a live holder, and a
# write without the lock is exactly the lost-update this mutex exists to stop.
sessions_lock_or_busy() {
    local timeout="$1"
    # The lock dir lives beside the store; its parent may not exist on a
    # first-ever write (the Python writer would otherwise create it), so
    # `mkdir "$lockdir"` needs it present first.
    mkdir -p "$(dirname "$SESSIONS_LOCK_DIR")" 2>/dev/null || true
    if ! registry_lock_acquire "$SESSIONS_LOCK_DIR" "$timeout"; then
        echo "LOCK_BUSY"
        exit 3
    fi
}

# Run the lock-free primitive under the held lock. Its stderr carries the
# refusal lines (TRANSITION_REFUSED, NONCE_MISMATCH, …); surface them on stdout
# so a caller parsing one stream still sees the failure, and map the exit code
# through unchanged.
run_sessions_py() {
    local out rc=0
    out="$("$(require_ait_python)" "$SESSIONS_PY" --file "$SESSIONS_FILE" "$@" 2>&1)" || rc=$?
    printf '%s\n' "$out"
    return "$rc"
}

# --pane and --pane-pid are a PAIR, in two senses — both must be PRESENT, and
# their values must be COHERENT. Exactly two shapes are legal:
#
#   --pane %N  --pane-pid <positive>   a real pane
#   --pane ""  --pane-pid 0            the gone-pane commit reconcile uses
#
# A mixed pair is a usage error, not a tolerable oddity. `--pane "" --pane-pid 123`
# persists a record claiming a live process at no pane at all, and both
# `standin_pid` and `pane_pid` are then written from it — after which reconcile
# can never match the stored location against a real pane, so the record is
# stranded in `frozen` forever with no way back.
require_pane_pair() {
    if has_arg --pane "$@" && ! has_arg --pane-pid "$@"; then
        die_usage "--pane requires --pane-pid"
    fi
    if has_arg --pane-pid "$@" && ! has_arg --pane "$@"; then
        die_usage "--pane-pid requires --pane"
    fi
    has_arg --pane "$@" || return 0
    local pane pid
    pane="$(arg_value --pane "$@")"
    pid="$(arg_value --pane-pid "$@")"
    [[ "$pid" =~ ^(0|[1-9][0-9]*)$ ]] \
        || die_usage "--pane-pid must be a non-negative integer: '$pid'"
    if [ -z "$pane" ] && [ "$pid" != "0" ]; then
        die_usage "--pane '' requires --pane-pid 0 (the gone-pane pair); got '$pid'"
    fi
    if [ -n "$pane" ] && [ "$pid" = "0" ]; then
        die_usage "--pane-pid 0 requires --pane '' (the gone-pane pair); got '$pane'"
    fi
}

cmd_upsert() {
    require_pane_pair "$@"
    has_arg --root "$@"     || die_usage "missing --root"
    has_arg --window "$@"   || die_usage "missing --window"
    has_arg --pane "$@"     || die_usage "missing --pane"
    has_arg --pane-pid "$@" || die_usage "missing --pane-pid"
    has_arg --id "$@"         && require_hex_id "$(arg_value --id "$@")" "--id"
    has_arg --nonce "$@"      && require_hex_id "$(arg_value --nonce "$@")" "--nonce"
    has_arg --restore-of "$@" && require_hex_id "$(arg_value --restore-of "$@")" "--restore-of"
    sessions_lock_or_busy "$WRITE_LOCK_TIMEOUT"
    run_sessions_py upsert "$@"
}

# A leased verb: <id> plus --nonce, and (for the location-writing ones) a pane pair.
cmd_leased() {
    local verb="$1" id="${2:-}"; shift 2 || usage
    require_hex_id "$id" "id"
    has_arg --nonce "$@" || die_usage "missing --nonce"
    require_hex_id "$(arg_value --nonce "$@")" "--nonce"
    require_pane_pair "$@"
    sessions_lock_or_busy "$WRITE_LOCK_TIMEOUT"
    run_sessions_py "$verb" "$id" "$@"
}

# A lease-MINTING verb: <id> plus the coordinator's --owner-pid (A7).
cmd_minting() {
    local verb="$1" id="${2:-}"; shift 2 || usage
    require_hex_id "$id" "id"
    has_arg --owner-pid "$@" || die_usage "$verb requires --owner-pid (the coordinator's pid, never this wrapper's)"
    require_positive_int "$(arg_value --owner-pid "$@")" "--owner-pid"
    sessions_lock_or_busy "$WRITE_LOCK_TIMEOUT"
    run_sessions_py "$verb" "$id" "$@"
}

# `drop` has two forms and the difference is the concurrency guarantee (t1705_6):
# bare `drop <id>` is unconditional (any state, no nonce -- the
# `kill_agent_pane_smart` contract), while `drop <id> --nonce <n>` is the LEASED
# form a coordinator must use. The nonce is checked inside the write lock, so a
# restore that begins between the coordinator's read and this delete is refused
# with NONCE_MISMATCH instead of silently destroying the record and the only
# copy of its capture. Extra arguments are FORWARDED -- this function used to
# drop them, which would have made `--nonce` a silent no-op.
cmd_drop() {
    local id="${1:-}"; shift || true
    require_hex_id "$id" "id"
    if has_arg --nonce "$@"; then
        require_hex_id "$(arg_value --nonce "$@")" "--nonce"
    fi
    sessions_lock_or_busy "$WRITE_LOCK_TIMEOUT"
    run_sessions_py drop "$id" "$@"
}

# `lease-release` is leased-but-paneless: nonce required, no pane pair.
cmd_lease_release() {
    local id="${1:-}"; shift || true
    require_hex_id "$id" "id"
    has_arg --nonce "$@" || die_usage "missing --nonce"
    require_hex_id "$(arg_value --nonce "$@")" "--nonce"
    sessions_lock_or_busy "$WRITE_LOCK_TIMEOUT"
    run_sessions_py lease-release "$id" "$@"
}

cmd_purge() {
    has_arg --observed "$@" || die_usage "missing --observed"
    sessions_lock_or_busy "$PURGE_LOCK_TIMEOUT"
    run_sessions_py purge "$@"
}

# NO LOCK for the two read verbs (t1598): they are pure reads — load() + print,
# with no read-modify-write to serialize — and every write lands via
# `os.replace`, so a reader always observes one whole generation. Taking the
# write lock here would make a read stall on, and then fail against, a wedged
# mutex. A read must never be the thing a leaked guard wedges.
cmd_list() { run_sessions_py list "$@"; }

cmd_show() {
    local id="${1:-}"
    require_hex_id "$id" "id"
    run_sessions_py show "$id"
}

main() {
    local verb="${1:-}"
    [ -n "$verb" ] || usage
    shift
    case "$verb" in
        upsert)            cmd_upsert "$@" ;;
        freeze-begin)      cmd_minting freeze-begin "$@" ;;
        restore-begin)     cmd_minting restore-begin "$@" ;;
        lease-take)        cmd_minting lease-take "$@" ;;
        freeze-commit)     cmd_leased freeze-commit "$@" ;;
        freeze-abort)      cmd_leased freeze-abort "$@" ;;
        restore-launched)  cmd_leased restore-launched "$@" ;;
        restore-confirm)   cmd_leased restore-confirm "$@" ;;
        restore-abort)     cmd_leased restore-abort "$@" ;;
        standin-respawned) cmd_leased standin-respawned "$@" ;;
        lease-release)     cmd_lease_release "$@" ;;
        drop)              cmd_drop "$@" ;;
        purge)             cmd_purge "$@" ;;
        list)              cmd_list "$@" ;;
        show)              cmd_show "$@" ;;
        *)                 usage ;;
    esac
}

main "$@"
