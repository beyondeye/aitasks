#!/usr/bin/env bash
# aitask_gate_fail.sh - Append a manual `fail` marker for a gate.
#
# Usage: aitask_gate_fail.sh <task-id> <gate> [--reason "..."]
#
# Backs `ait gate fail <task-id> <gate>` (t635_11) — a thin wrapper over
# `aitask_gate.sh append <id> <gate> fail [note=<reason>]`, useful for a human
# manually failing a gate (e.g. rejecting a review). Delegates the append (and
# its per-task lock + atomic write) to aitask_gate.sh.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

cmd_main() {
    local task_id="${1:-}" gate="${2:-}"
    [[ -z "$task_id" || -z "$gate" ]] && \
        die "Usage: aitask_gate_fail.sh <task-id> <gate> [--reason \"...\"]"
    shift 2 || true

    local reason=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --reason) reason="${2:-}"; shift 2 ;;
            --reason=*) reason="${1#--reason=}"; shift ;;
            *) die "Unknown argument: $1" ;;
        esac
    done

    local -a args=("$task_id" "$gate" fail)
    [[ -n "$reason" ]] && args+=("note=$reason")
    exec "$SCRIPT_DIR/aitask_gate.sh" append "${args[@]}"
}

cmd_main "$@"
