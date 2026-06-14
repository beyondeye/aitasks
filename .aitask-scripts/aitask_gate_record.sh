#!/usr/bin/env bash
# aitask_gate_record.sh - Record a workflow checkpoint into the gate ledger
# AND persist it so the gate state is visible from every PC (t635_2, Phase 1).
#
# Thin best-effort wrapper used by task-workflow's checkpoint recording (gated
# behind the `record_gates` execution-profile key). It:
#   1. appends a gate-run block via aitask_gate.sh (the substrate from t635_1), then
#   2. commits the single task file path-scoped via `task_git` and best-effort
#      pushes via `task_push` (task_utils.sh) so other machines/sessions see it.
#
# DESIGN: this is purely additive bookkeeping for the attended-mode D2 seed.
# It is best-effort end-to-end and ALWAYS exits 0 — a recording or git failure
# must never block the workflow the user is driving. Concurrency is bounded by
# the per-task lock the workflow already holds (only the lock-holder records a
# task's gates) plus aitask_gate.sh's own append lock; the commit stages only
# the one task file ("stage specific paths only", per the shared aitask-data
# branch reconciliation rules).
#
# Usage:
#   aitask_gate_record.sh <task-id> <gate> <status> [k=v ...]
#
# <status>: pass | fail | pending | running | skip | error
# Keys are forwarded verbatim to `aitask_gate.sh append` (run/attempt/duration/
# type on the marker line; verifier/result/log/note in the body).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

TASK_DIR="${TASK_DIR:-aitasks}"

show_help() {
    cat <<'EOF'
Usage: aitask_gate_record.sh <task-id> <gate> <status> [k=v ...]

Record a workflow checkpoint into the task's gate ledger and persist it so the
gate state is visible from every PC. Best-effort: always exits 0.

Steps:
  1. aitask_gate.sh append <task-id> <gate> <status> [k=v ...]
  2. commit the task file (path-scoped) and best-effort push to the data branch.

<status>: pass | fail | pending | running | skip | error
Keys: run, attempt, duration, type (marker line);
      verifier, result, log, note (body lines).

Example:
  aitask_gate_record.sh 42 plan_approved pass type=human
EOF
}

main() {
    case "${1:-}" in
        --help | -h | help | "") show_help; return 0 ;;
    esac

    local task_id="${1:-}" gate="${2:-}" status="${3:-}"
    if [[ -z "$task_id" || -z "$gate" || -z "$status" ]]; then
        die "Usage: aitask_gate_record.sh <task-id> <gate> <status> [k=v ...] (try --help)"
    fi

    # 1. Append the gate-run block (best-effort — never block the workflow).
    if ! "$SCRIPT_DIR/aitask_gate.sh" append "$@"; then
        warn "gate-record: append failed for t${task_id} gate '${gate}' — skipping persist"
        return 0
    fi

    # 2. Persist: commit the single task file path-scoped, then best-effort push.
    #    resolve_task_file returns the repo-relative aitasks/... path, which
    #    task_git resolves inside the data worktree (symlink-safe).
    local file
    if ! file="$(resolve_task_file "$task_id" 2>/dev/null)"; then
        warn "gate-record: could not resolve task file for t${task_id} — block appended but not committed"
        return 0
    fi

    task_git add -- "$file" 2>/dev/null || true
    task_git commit -m "ait: Record ${gate} gate for t${task_id}" -- "$file" 2>/dev/null || true
    task_push 2>/dev/null || true

    return 0
}

main "$@"
