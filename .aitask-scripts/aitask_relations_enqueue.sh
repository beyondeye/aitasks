#!/usr/bin/env bash
# aitask_relations_enqueue.sh <op> <trigger> <task_id>
#
# The one trigger helper of the task-relations layer
# (aidocs/framework/task_relations.md D4, "Worker API"). Callers: the creation,
# fold and approval hooks of t1981_4.
#
# CONTRACT: always exits 0 and NEVER writes to stdout, so `--silent` callers
# keep their single-line output contract. Every check and every write (the
# relations.enabled / per-trigger / AIT_RELATIONS=0 switches, the coalescing
# spool write, for `relations plan_approved` the approval stamp, and the
# worker start) happens in the DETACHED part, lib/relations_worker.py
# `enqueue`, which starts its own session and logs to
# <git-common-dir>/aitask-relations/spool/enqueue.log. Nothing here blocks the
# caller, and no failure here can change the caller's exit status.
set -uo pipefail
# Deliberately not `set -e`: a failed probe must fall through to `exit 0`.

exec 1>/dev/null
trap 'exit 0' EXIT

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)" || exit 0

op="${1:-}"
trigger="${2:-}"
task_id="${3:-}"

root="$(git rev-parse --show-toplevel 2>/dev/null)" || root=""
[[ -n "$root" ]] || exit 0
gcd="$(git -C "$root" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" || gcd=""
[[ -n "$gcd" ]] || exit 0

log="$gcd/aitask-relations/spool/enqueue.log"
if mkdir -p "$gcd/aitask-relations/spool" 2>/dev/null && : >>"$log" 2>/dev/null; then
    exec 2>>"$log"
else
    log=/dev/null
    exec 2>/dev/null
fi

if [[ -z "$op" || -z "$trigger" || -z "$task_id" ]]; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [$$] ENQUEUE_USAGE: <op> <trigger> <task_id> (got '$op' '$trigger' '$task_id')" >&2
    exit 0
fi

# shellcheck source=lib/python_resolve.sh disable=SC1091
source "$SCRIPT_DIR/lib/python_resolve.sh" 2>/dev/null || exit 0
PY="$(resolve_python 2>/dev/null)" || PY=""
if [[ -z "$PY" ]]; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [$$] ENQUEUE_ERROR: no python interpreter" >&2
    exit 0
fi

nohup "$PY" "$SCRIPT_DIR/lib/relations_worker.py" enqueue "$root" "$op" "$trigger" "$task_id" \
    </dev/null >>"$log" 2>&1 &
disown 2>/dev/null || true
exit 0
