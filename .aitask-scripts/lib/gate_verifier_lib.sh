#!/usr/bin/env bash
# gate_verifier_lib.sh - shared core for project-command machine-gate verifiers
# (build_verified, tests_pass, lint).  Sourced by the thin aitask_gate_<name>.sh
# wrappers; do not execute directly (the SCRIPT_DIR guard below dies if you try).
#
# CONTRACT: the sourcing wrapper MUST set SCRIPT_DIR (the .aitask-scripts dir)
# before sourcing this file -- run_command_gate invokes "$SCRIPT_DIR/aitask_gate.sh".
# The guard below makes a direct/standalone source fail loudly instead of silently
# mis-resolving the append helper.
: "${SCRIPT_DIR:?gate_verifier_lib.sh requires SCRIPT_DIR (set by the sourcing wrapper) before sourcing}"

# run_command_gate <gate> <config_key> <verifier_name> <task-id> <attempt> <run-id>
#
# Reads project_config.yaml <config_key> (scalar OR list), runs the command(s)
# sequentially (stop on first failure), tees output to the sidecar log, appends
# the terminal gate-run block via aitask_gate.sh, and RETURNS the verifier
# contract exit code:
#   0 = pass   all command(s) succeeded
#   1 = fail   a command exited non-zero (a code fix is needed)
#   2 = skip   no command configured for <config_key> ("evaluated, not applicable")
#   3 = error  (reserved; this lib does not itself produce it)
#
# Paths are repo-root-relative: the orchestrator (and `ait`) run verifiers from
# the repo root, so aitasks/metadata/... and .aitask-gates/... resolve correctly.
run_command_gate() {
    local gate="$1" config_key="$2" verifier_name="$3"
    local task_id="$4" attempt="$5" run_id="$6"

    local config="aitasks/metadata/project_config.yaml"
    local logdir=".aitask-gates/${task_id}"
    mkdir -p "$logdir"
    local log="${logdir}/${gate}_${run_id}.log"

    # Resolve command(s). Try the list form first (read_yaml_list handles inline
    # [a, b] and block "- " lists); fall back to a scalar via read_yaml_field,
    # stripping surrounding quotes it leaves intact. Drop empties / literal "null".
    local -a cmds=() raw=()
    if [[ -f "$config" ]]; then
        mapfile -t raw < <(read_yaml_list "$config" "$config_key" 2>/dev/null || true)
        if [[ ${#raw[@]} -eq 0 ]]; then
            local scalar
            scalar="$(read_yaml_field "$config" "$config_key" 2>/dev/null || true)"
            # strip one layer of surrounding single/double quotes
            if [[ "$scalar" == \"*\" || "$scalar" == \'*\' ]]; then
                scalar="${scalar:1:${#scalar}-2}"
            fi
            [[ -n "$scalar" ]] && raw=("$scalar")
        fi
        local v
        for v in "${raw[@]}"; do
            [[ -n "$v" && "$v" != "null" ]] && cmds+=("$v")
        done
    fi

    local status code result
    if [[ ${#cmds[@]} -eq 0 ]]; then
        status=skip; code=2; result="no ${config_key} configured"
        printf '(no %s configured in %s; gate not applicable)\n' "$config_key" "$config" > "$log"
    else
        status=pass; code=0; result="all ${config_key} command(s) passed"
        : > "$log"
        local c
        for c in "${cmds[@]}"; do
            printf '$ %s\n' "$c" >> "$log"
            if ! bash -c "$c" >> "$log" 2>&1; then
                status=fail; code=1; result="command failed: ${c}"
                break
            fi
        done
    fi

    "$SCRIPT_DIR/aitask_gate.sh" append "$task_id" "$gate" "$status" \
        run="$run_id" attempt="$attempt" type=machine \
        verifier="$verifier_name" result="$result" log="$log" >/dev/null

    return "$code"
}
