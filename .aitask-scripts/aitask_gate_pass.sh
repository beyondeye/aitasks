#!/usr/bin/env bash
# aitask_gate_pass.sh - Create a human-gate signal ("sign" a gate) (t635_15).
#
# Usage: aitask_gate_pass.sh <task-id> <gate>
#
# Backs `ait gate pass <task-id> <gate>` — the sanctioned way for a HUMAN to
# sign an async human gate (e.g. an async code review / merge approval). It:
#   1. Refuses machine gates (a machine gate is recorded by its verifier).
#   2. Refuses human gates with no file-touch `signal_target` (attended-only
#      checkpoints such as `plan_approved`).
#   3. Creates the signal witness at the gate's `signal_target`, code-bound with
#      the current `code_digest` so a signature cannot later be consumed as a
#      pass for a DIFFERENT code state (the orchestrator re-pends a stale one).
#   4. Delegates the ledger `pass` recording to `aitask_run_gates.sh` (the
#      orchestrator's read-side is the single writer of observed pass blocks) —
#      no duplicated append logic. The ledger `pass` is the durable, cross-PC
#      record (the witness file lives under gitignored `.aitask-gates/`).
#
# NON-NEGOTIABLE AUTONOMY CONTROL: this is the HUMAN's tool. Agents MUST NEVER
# invoke it to self-sign a human gate, suggest automating its creation,
# impersonate a reviewer, or bypass a gate's absent signal.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

TASK_DIR="${TASK_DIR:-aitasks}"
REGISTRY="${TASK_DIR}/metadata/gates.yaml"
ORCH_PY="$SCRIPT_DIR/lib/gate_orchestrator.py"

cmd_main() {
    local task_id="${1:-}" gate="${2:-}"
    [[ -z "$task_id" || -z "$gate" ]] && \
        die "Usage: aitask_gate_pass.sh <task-id> <gate>"

    # Validate the task id early (dies with a clear error if unresolvable); the
    # registry read + orchestrator delegation below re-resolve from the id.
    resolve_task_file "$task_id" >/dev/null
    local py
    py="$(resolve_python)" || die "python3 is required for gate pass"

    # Read the gate's type + signal_target from the registry (reuse the ONE
    # registry parser — never hand-parse YAML).
    local meta gate_type signal_target
    meta="$("$py" -c '
import sys
sys.path.insert(0, sys.argv[1])
import gate_ledger as gl
reg = gl.read_registry(sys.argv[2])
g = reg.get(sys.argv[3])
if g is None:
    print("MISSING")
else:
    print((g.get("type", "") or "") + "\t" + (g.get("signal_target", "") or ""))
' "$SCRIPT_DIR/lib" "$REGISTRY" "$gate")" || die "Failed to read gate registry"

    [[ "$meta" == "MISSING" ]] && \
        die "Gate '$gate' is not defined in $REGISTRY"
    gate_type="${meta%%$'\t'*}"
    signal_target="${meta#*$'\t'}"

    # Refuse machine gates — a machine gate is recorded by running its verifier.
    [[ "$gate_type" != "human" ]] && \
        die "gate pass refuses machine gate '$gate' (machine gates are recorded by their verifier, run 'ait gates run')"

    # Refuse human gates with no file-touch signal (attended-only checkpoint).
    [[ -z "$signal_target" ]] && \
        die "Gate '$gate' has no file-touch signal_target (attended-only checkpoint — nothing to sign)"

    # Substitute the placeholders (<task-id> -> t<id>, <gate> -> <gate>).
    local target="${signal_target//<task-id>/t${task_id}}"
    target="${target//<gate>/$gate}"

    # Code-bind the witness with the current code digest (may be empty when git
    # is unavailable — then the field is omitted and the orchestrator accepts it).
    local digest signer stamp host
    digest="$("$py" "$ORCH_PY" code-digest 2>/dev/null || true)"
    signer="$(id -un 2>/dev/null || echo "${USER:-unknown}")"
    stamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    host="$(hostname 2>/dev/null || echo unknown)"

    mkdir -p "$(dirname "$target")"
    local existed=0
    [[ -f "$target" ]] && existed=1
    {
        echo "signer=$signer"
        echo "signed_at=$stamp"
        echo "hostname=$host"
        [[ -n "$digest" ]] && echo "code_digest=$digest"
    } > "$target"

    if [[ "$existed" -eq 1 ]]; then
        echo "Re-signed gate '$gate' for t${task_id} (witness refreshed): $target"
    else
        echo "Signed gate '$gate' for t${task_id}: $target"
    fi

    # Delegate recording to the orchestrator (single writer of pass blocks). It
    # observes the fresh witness and appends the ledger `pass` when the gate's
    # predecessors are satisfied; otherwise it reports why and records nothing
    # (the witness persists for a later `ait gates run`).
    echo "Recording via orchestrator:"
    "$SCRIPT_DIR/aitask_run_gates.sh" run "$task_id" --gate "$gate"
}

cmd_main "$@"
