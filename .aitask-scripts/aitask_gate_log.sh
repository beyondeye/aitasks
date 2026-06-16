#!/usr/bin/env bash
# aitask_gate_log.sh - Print the sidecar log for a gate's most recent run.
#
# Usage: aitask_gate_log.sh <task-id> <gate>
#
# Backs `ait gate log <task-id> <gate>` (t635_11). Resolves the gate's current
# run from the ledger, reads its `Log:` body field, and prints that sidecar
# file. Prints a friendly note (exit 0) when no log is recorded.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

cmd_main() {
    local task_id="${1:-}" gate="${2:-}"
    [[ -z "$task_id" || -z "$gate" ]] && die "Usage: aitask_gate_log.sh <task-id> <gate>"

    local file
    file="$(resolve_task_file "$task_id")"

    # Find the Log: body field of the LAST run block for this gate.
    local log
    log="$(awk -v g="$gate" '
        /^>[[:space:]]*\*\*/ && /gate:/ {
            cur = (match($0, /gate:[A-Za-z0-9_]+/) && \
                   substr($0, RSTART + 5, RLENGTH - 5) == g) ? 1 : 0
            next
        }
        cur && /^>[[:space:]]*Log:/ {
            v = $0
            sub(/^>[[:space:]]*Log:[[:space:]]*/, "", v)
            gsub(/`/, "", v)
            last = v
        }
        END { print last }
    ' "$file" 2>/dev/null)"

    if [[ -z "$log" ]]; then
        echo "(no sidecar log recorded for gate '$gate' on t$task_id)"
        return 0
    fi
    if [[ ! -f "$log" ]]; then
        echo "(sidecar log path recorded but file is missing: $log)"
        return 0
    fi
    cat "$log"
}

cmd_main "$@"
