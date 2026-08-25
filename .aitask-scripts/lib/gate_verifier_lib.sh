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

# --- constants -------------------------------------------------------------
# Plain globals, deliberately NOT readonly: this file is sourced, and a second
# source in the same shell must not die on a re-assignment.

# The project_config.yaml key a project uses to declare which of its command
# keys speak the gate exit contract (see run_command_gate's docblock).
GATE_COMMAND_EXIT_CONTRACT_KEY="gate_command_exit_contract"

# The one command exit code that means "I did not run".
GATE_COMMAND_SKIP_EXIT=2

# Every project_config.yaml command key this lib can be invoked for -- one entry
# per aitask_gate_*.sh wrapper's <config_key> argument. Canonical set: a
# gate_command_exit_contract entry outside it is a typo, not an opt-in, and is
# reported rather than silently ignored. tests/test_gate_verifiers.sh derives the
# same set from the wrappers and fails if the two drift.
GATE_COMMAND_KEYS="verify_build test_command lint_command"

# _gate_config_values <config-file> <key>
# Resolve a project_config.yaml key to zero or more values, one per line.
# Try the list form first (read_yaml_list handles inline [a, b] and block "- "
# lists); fall back to a scalar via read_yaml_field, stripping surrounding
# quotes it leaves intact. Drop empties / literal "null". A missing config file
# yields nothing.
#
# Extracted verbatim from run_command_gate's former inline resolution so the
# command path is unchanged; the gate_command_exit_contract opt-in list below
# reads through the same function rather than growing a second parser.
_gate_config_values() {
    local config="$1" key="$2"
    [[ -f "$config" ]] || return 0
    local -a raw=()
    mapfile -t raw < <(read_yaml_list "$config" "$key" 2>/dev/null || true)
    if [[ ${#raw[@]} -eq 0 ]]; then
        local scalar
        scalar="$(read_yaml_field "$config" "$key" 2>/dev/null || true)"
        # Strip one layer of surrounding single/double quotes. This is NOT the
        # dead twin of the list-side strip t1609 removed below: read_yaml_field
        # only trims whitespace, it never unquotes, so the scalar path still
        # needs its own. A cleanup pass must not delete both.
        if [[ "$scalar" == \"*\" || "$scalar" == \'*\' ]]; then
            scalar="${scalar:1:${#scalar}-2}"
        fi
        [[ -n "$scalar" ]] && raw=("$scalar")
    fi
    local v
    for v in "${raw[@]}"; do
        [[ -n "$v" && "$v" != "null" ]] && printf '%s\n' "$v"
    done
    return 0
}

# run_command_gate <gate> <config_key> <verifier_name> <task-id> <attempt> <run-id>
#
# Reads project_config.yaml <config_key> (scalar OR list), runs the command(s)
# sequentially, tees output to the sidecar log, appends the terminal gate-run
# block via aitask_gate.sh, and RETURNS the verifier contract exit code.
#
# THIS FUNCTION'S OWN EXIT CODES -- what the orchestrator reads. NOT a claim
# about what the project command returned; the two are separate contracts and
# conflating them is what this function used to get wrong:
#   0 = pass   every command exited 0
#   1 = fail   a command failed (see the command-exit table below)
#   2 = skip   "evaluated, not applicable". EITHER no command is configured for
#              <config_key>, OR a command declared it did not run. The two are
#              distinguished in the appended `result=` line, never by the code.
#   3 = error  (reserved; this lib does not itself produce it)
#
# HOW A PROJECT COMMAND'S OWN EXIT CODE IS READ -- opt-in, per config key:
#   By default EVERY non-zero exit is a fail, 2 included. A command's 2 means
#   "I did not run" only when <config_key> is listed in project_config.yaml's
#   `gate_command_exit_contract`. Reserving 2 universally would be unsafe: GNU
#   make exits 2 on a build error and pytest exits 2 on interrupt, so a real
#   failure would silently satisfy a blocks_dependents gate.
#
#     command exit | key opted in       | key not opted in
#     -------------+--------------------+------------------
#          0       | pass               | pass
#          1       | fail               | fail
#          2       | skip (did not run) | fail
#      anything    | fail               | fail
#      else
#
#   Only the documented skip code is a skip; any other non-zero is a failure, so
#   an unexpected status can never be laundered into a skip.
#
#   `gate_command_exit_contract` accepts only the keys in GATE_COMMAND_KEYS.
#   Anything else is a typo: it is IGNORED (never fatal, never changes a
#   verdict) but reported on stderr, in the sidecar log, and as a `note=` field
#   on the appended gate-run block -- otherwise a misspelled key looks exactly
#   like "not opted in", which is the hardest state to diagnose.
#
# AGGREGATION over a command list:
#   A fail short-circuits (later commands do NOT run). A skip does NOT: it is
#   remembered and the list continues, so a fail after a skip still wins.
#   any fail -> fail; else any skip -> skip; else pass.
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

    # Resolve command(s) through the shared reader (same semantics as before:
    # list form first, scalar fallback, empties / literal "null" dropped).
    local -a cmds=()
    mapfile -t cmds < <(_gate_config_values "$config" "$config_key")

    # Resolve the per-key exit-contract opt-in, and collect unrecognized entries.
    # The WHOLE list is validated against GATE_COMMAND_KEYS -- not just this
    # verifier's own key -- so any of the three verifiers reports a typo.
    local exit_contract=0 k unknown_keys=""
    while IFS= read -r k; do
        # No re-stripping here: read_yaml_list unquotes both list forms itself
        # since t1609 (_yaml_norm_list_item), and the scalar fallback in
        # _gate_config_values above unquotes its own value. Test (j) in
        # tests/test_gate_verifiers.sh drives the quoted BLOCK form and is what
        # keeps that true.
        if [[ " $GATE_COMMAND_KEYS " != *" $k "* ]]; then
            unknown_keys="${unknown_keys:+$unknown_keys,}$k"
            continue
        fi
        [[ "$k" == "$config_key" ]] && exit_contract=1
    done < <(_gate_config_values "$config" "$GATE_COMMAND_EXIT_CONTRACT_KEY")

    local unknown_note=""
    if [[ -n "$unknown_keys" ]]; then
        unknown_note="${GATE_COMMAND_EXIT_CONTRACT_KEY}: unrecognized key(s): ${unknown_keys} (expected one of: ${GATE_COMMAND_KEYS// /, })"
        printf '%s\n' "$unknown_note" >&2
    fi

    local status code result
    if [[ ${#cmds[@]} -eq 0 ]]; then
        status=skip; code=2; result="no ${config_key} configured"
        printf '(no %s configured in %s; gate not applicable)\n' "$config_key" "$config" > "$log"
    else
        status=pass; code=0; result="all ${config_key} command(s) passed"
        : > "$log"
        local c rc skipped_cmd=""
        for c in "${cmds[@]}"; do
            printf '$ %s\n' "$c" >> "$log"
            # A command that cannot be PARSED never ran, so it must never be
            # able to satisfy this gate (t1609). bash exits 2 on a syntax
            # error, and 2 is GATE_COMMAND_SKIP_EXIT -- so under an opted-in
            # gate_command_exit_contract an unparseable command used to be
            # recorded as a skip, which can release a blocks_dependents edge
            # for work that never happened. `bash -n` separates the two: it
            # rejects `echo "a` and `for x in`, and accepts everything that
            # merely fails at runtime (`pytest -k` -> 127, `[ -f x ] && make`
            # -> 1), which stay ordinary fails.
            #
            # SKIP_EXIT keeps its real meaning here: "the command ran and
            # reported it did not do the work", never "it would not parse".
            if ! bash -n -c "$c" 2>>"$log"; then
                status=fail; code=1
                result="malformed ${config_key} command (cannot parse): ${c}"
                break
            fi
            rc=0
            bash -c "$c" >> "$log" 2>&1 || rc=$?
            if [[ $rc -eq 0 ]]; then
                continue
            fi
            if [[ $exit_contract -eq 1 && $rc -eq $GATE_COMMAND_SKIP_EXIT ]]; then
                # Declared "I did not run". Not a failure -- and NOT a
                # short-circuit: a later command may still fail, and a fail
                # beside a skip must stay a fail.
                printf '(exit %s: command reported skip - did not run)\n' "$rc" >> "$log"
                [[ -n "$skipped_cmd" ]] || skipped_cmd="$c"
                continue
            fi
            status=fail; code=1; result="command failed (exit ${rc}): ${c}"
            break
        done
        if [[ "$status" == pass && -n "$skipped_cmd" ]]; then
            status=skip; code=2
            result="command reported skip (exit ${GATE_COMMAND_SKIP_EXIT}): ${skipped_cmd}"
        fi
    fi

    # A bad opt-in entry never changes the verdict -- it only explains why an
    # expected skip did not happen. Surface it where it is durable (the ledger
    # block) as well as in the run's own log.
    local -a note_arg=()
    if [[ -n "$unknown_note" ]]; then
        printf '%s\n' "$unknown_note" >> "$log"
        note_arg=(note="$unknown_note")
    fi

    "$SCRIPT_DIR/aitask_gate.sh" append "$task_id" "$gate" "$status" \
        run="$run_id" attempt="$attempt" type=machine \
        verifier="$verifier_name" result="$result" log="$log" \
        ${note_arg[@]+"${note_arg[@]}"} >/dev/null

    return "$code"
}
