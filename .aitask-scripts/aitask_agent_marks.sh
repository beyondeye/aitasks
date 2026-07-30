#!/usr/bin/env bash
# aitask_agent_marks.sh - Locked writer for the cross-repo prioritized-agent
# marks store (t1326).
#
# The store lives at `~/.config/aitasks/agent_marks.json` (override with
# `AITASKS_AGENT_MARKS_FILE`). It records `{root, window, marked_at}` entries
# keyed by `(realpath(project_root), tmux_window_name)`, so a mark set from one
# repo's monitor is visible from every other repo's monitor.
#
# This script is the ONLY writer. It holds the `registry_lock.sh` mutex around a
# read-modify-write and delegates the actual parsing/policy to the lock-free
# primitive `lib/agent_marks.py`. Readers (the monitor TUIs) read the JSON
# directly with no lock: every write lands via `os.replace`, so a reader always
# observes one whole generation.
#
# Callers are the Python TUIs only (never a SKILL.md), so per
# `aidocs/framework/aitasks_extension_points.md` this script needs no code-agent
# allow-list entries and no `ait` dispatcher case.
#
# Verbs:
#   toggle <project_root> <window_name>
#                          - Flip the mark. Prints MARKED:<root>|<window> or
#                            UNMARKED:<root>|<window>.
#   purge [--observed <file>]
#                          - Apply age expiry and, when --observed is given, the
#                            fail-closed liveness sweep. Prints a
#                            DROPPED:<root>|<window>|<reason> line per removed
#                            entry, then PURGED:<n>.
#   list                   - Print MARK:<root>|<window>|<marked_at> per entry.
#
# Exit codes:
#   0  success
#   2  usage error
#   3  LOCK_BUSY   - another process holds the mutex; NOTHING was written
#   4  ERROR       - the store is corrupt or unreadable; NOTHING was written

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"
# shellcheck source=lib/registry_lock.sh
source "$SCRIPT_DIR/lib/registry_lock.sh"

MARKS_FILE="${AITASKS_AGENT_MARKS_FILE:-$HOME/.config/aitasks/agent_marks.json}"
# Mutex dir for serializing the read-modify-write. Derived from MARKS_FILE so it
# follows AITASKS_AGENT_MARKS_FILE overrides (tests included) — a lock keyed to
# the default path while the data went elsewhere would serialize nothing.
MARKS_LOCK_DIR="${MARKS_FILE}.lockd"

# Keypress-path timeout. The 10s default is far too long to stall a TUI on a
# single `space`; 2s is long enough to ride out a concurrent toggle and short
# enough that a jammed lock reports back rather than freezing the UI.
TOGGLE_LOCK_TIMEOUT=2
# Background maintenance can afford to wait for a contended lock.
PURGE_LOCK_TIMEOUT=10

MARKS_PY="$SCRIPT_DIR/lib/agent_marks.py"

usage() {
    cat >&2 <<'EOF'
Usage: aitask_agent_marks.sh toggle <project_root> <window_name>
       aitask_agent_marks.sh purge [--observed <file>]
       aitask_agent_marks.sh list
EOF
    exit 2
}

# Acquire the mutex or report LOCK_BUSY and exit 3. NEVER proceed unlocked:
# registry_lock_acquire returns 1 rather than stealing a live holder, and a
# write without the lock is exactly the lost-update this mutex exists to stop.
marks_lock_or_busy() {
    local timeout="$1"
    # The lock dir lives beside the store; its parent may not exist on a
    # first-ever write (the Python writer would otherwise create it), so
    # `mkdir "$lockdir"` needs it present first.
    mkdir -p "$(dirname "$MARKS_LOCK_DIR")" 2>/dev/null || true
    if ! registry_lock_acquire "$MARKS_LOCK_DIR" "$timeout"; then
        echo "LOCK_BUSY"
        exit 3
    fi
}

# Run the lock-free primitive under the held lock. Its stderr carries ERROR:
# lines for a corrupt store; surface them on stdout so a TUI parsing one stream
# still sees the failure, and map its exit 4 through unchanged.
run_marks_py() {
    local out rc=0
    out="$("$(require_ait_python)" "$MARKS_PY" --file "$MARKS_FILE" "$@" 2>&1)" || rc=$?
    printf '%s\n' "$out"
    return "$rc"
}

cmd_toggle() {
    local root="${1:-}" window="${2:-}"
    [ -n "$root" ] && [ -n "$window" ] || usage
    marks_lock_or_busy "$TOGGLE_LOCK_TIMEOUT"
    run_marks_py toggle "$root" "$window"
}

cmd_purge() {
    local observed=""
    while [ $# -gt 0 ]; do
        case "$1" in
            --observed) observed="${2:-}"; shift 2 ;;
            *) usage ;;
        esac
    done
    marks_lock_or_busy "$PURGE_LOCK_TIMEOUT"
    if [ -n "$observed" ]; then
        run_marks_py purge --observed "$observed"
    else
        run_marks_py purge
    fi
}

cmd_list() {
    marks_lock_or_busy "$PURGE_LOCK_TIMEOUT"
    run_marks_py list
}

main() {
    local verb="${1:-}"
    [ -n "$verb" ] || usage
    shift
    case "$verb" in
        toggle) cmd_toggle "$@" ;;
        purge)  cmd_purge "$@" ;;
        list)   cmd_list "$@" ;;
        *)      usage ;;
    esac
}

main "$@"
