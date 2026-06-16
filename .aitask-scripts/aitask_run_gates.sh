#!/usr/bin/env bash
# aitask_run_gates.sh - Headless gate orchestrator entry (t635_11, Phase 4).
#
# The bash wrapper around lib/gate_orchestrator.py — the engine that runs a
# task's declared gates (compute unlocked set, dispatch machine-gate verifiers
# within their retry budgets, observe human gates without self-signalling, stop).
# This is what `ait gates run` / `ait gates unlocked`, the `aitask-run-gates`
# skill, `aitask-resume`, and the autonomous lane (aitask-pickrem) call.
#
# Subcommands:
#   run      <task-id> [--gate <name>] [--dry-run]   Run the orchestrator
#   unlocked <task-id>                               Print the unlocked gate set
#
# `max_parallel_gates` is read from the active execution profile (default 2),
# capped by core count inside the engine. The engine appends through
# aitask_gate.sh (reusing its per-task lock); it never writes the task file.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"
# shellcheck source=lib/yaml_utils.sh
source "$SCRIPT_DIR/lib/yaml_utils.sh"

TASK_DIR="${TASK_DIR:-aitasks}"
ORCH_PY="$SCRIPT_DIR/lib/gate_orchestrator.py"
REGISTRY="${TASK_DIR}/metadata/gates.yaml"
PROFILES_DIR="${PROFILES_DIR:-$REPO_ROOT/aitasks/metadata/profiles}"

# Resolve max_parallel_gates from the active profile (default 2). A user-local
# profile (profiles/local/<name>.yaml) takes precedence over the shared one.
resolve_max_parallel() {
    local name file val
    name="$("$SCRIPT_DIR/aitask_skill_resolve_profile.sh" run-gates 2>/dev/null || echo default)"
    file=""
    if [[ -f "$PROFILES_DIR/local/${name}.yaml" ]]; then
        file="$PROFILES_DIR/local/${name}.yaml"
    elif [[ -f "$PROFILES_DIR/${name}.yaml" ]]; then
        file="$PROFILES_DIR/${name}.yaml"
    fi
    val=""
    [[ -n "$file" ]] && val="$(read_yaml_field "$file" max_parallel_gates)"
    [[ "$val" =~ ^[0-9]+$ ]] || val=2
    echo "$val"
}

main() {
    local subcmd="${1:-}"
    case "$subcmd" in
        run|unlocked) shift ;;
        --help|-h|"") cat <<'EOF'
Usage: aitask_run_gates.sh <run|unlocked> <task-id> [options]

  run      <task-id> [--gate <name>] [--dry-run]
        Run the gate orchestrator: dispatch unlocked machine-gate verifiers
        within their retry budgets, observe human gates, stop.
  unlocked <task-id>
        Print the gates runnable right now, one per line.
EOF
            return 0 ;;
        *) die "Unknown subcommand '$subcmd' (try: run | unlocked)" ;;
    esac

    local task_id="${1:-}"
    [[ -z "$task_id" ]] && die "Usage: aitask_run_gates.sh $subcmd <task-id> [options]"
    shift

    local file py
    file="$(resolve_task_file "$task_id")"
    py="$(resolve_python)" || die "python3 is required for the gate orchestrator"

    if [[ "$subcmd" == "unlocked" ]]; then
        exec "$py" "$ORCH_PY" unlocked "$file" --registry "$REGISTRY"
    fi

    local max_parallel
    max_parallel="$(resolve_max_parallel)"
    exec "$py" "$ORCH_PY" run "$file" --task-id "$task_id" \
        --max-parallel "$max_parallel" --registry "$REGISTRY" "$@"
}

main "$@"
