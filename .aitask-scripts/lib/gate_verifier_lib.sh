#!/usr/bin/env bash
# gate_verifier_lib.sh - shared core for running a project_config.yaml command
# key under the gate exit contract.  Sourced, never executed directly (the
# SCRIPT_DIR guard below dies if you try).  Two consumers, deliberately:
#
#   * the thin aitask_gate_<name>.sh wrappers -- the machine-gate verifiers
#     (build_verified, tests_pass, lint), via run_command_gate();
#   * aitask_run_project_command.sh -- the legacy build-verification helper the
#     Step-9 / pickrem / pickweb / aitask-qa agent prose calls, via
#     run_project_command_key() (t1610).
#
# The file name says "gate verifier" for history; the contract it owns is the
# project-command one, and run_project_command_key()'s docblock is its single
# canonical statement.  Do not restate that table in a consumer.
#
# CONTRACT: the sourcing script MUST set SCRIPT_DIR (the .aitask-scripts dir)
# before sourcing this file -- run_command_gate invokes "$SCRIPT_DIR/aitask_gate.sh".
# The guard below makes a direct/standalone source fail loudly instead of silently
# mis-resolving the append helper.  run_project_command_key() itself needs no
# ledger and no task id, but the guard is file-scoped, so a consumer that only
# wants that function still sets SCRIPT_DIR.
#
# A caller that RUNS commands must also have sourced lib/yaml_utils.sh
# (read_yaml_list / read_yaml_field); run_project_command_key checks that and
# returns 3, because a missing reader would otherwise resolve every command key
# to nothing and report a silent, wrong "skip". The check is inside the function
# rather than at file scope so that sourcing this lib purely to read
# GATE_COMMAND_KEYS stays legal.
: "${SCRIPT_DIR:?gate_verifier_lib.sh requires SCRIPT_DIR (set by the sourcing wrapper) before sourcing}"

# --- constants -------------------------------------------------------------
# Plain globals, deliberately NOT readonly: this file is sourced, and a second
# source in the same shell must not die on a re-assignment.

# The project_config.yaml key a project uses to declare which of its command
# keys speak the gate exit contract (see run_project_command_key's docblock).
GATE_COMMAND_EXIT_CONTRACT_KEY="gate_command_exit_contract"

# The one command exit code that means "I did not run".
GATE_COMMAND_SKIP_EXIT=2

# Every project_config.yaml command key this lib can be invoked for -- one entry
# per aitask_gate_*.sh wrapper's <config_key> argument, and the only keys
# aitask_run_project_command.sh accepts. Canonical set: a
# gate_command_exit_contract entry outside it is a typo, not an opt-in, and is
# reported rather than silently ignored. tests/test_gate_verifiers.sh derives the
# same set from the wrappers and fails if the two drift.
GATE_COMMAND_KEYS="verify_build test_command lint_command"

# project_config_values <config-file> <key>
# Resolve a project_config.yaml key to zero or more values, one per line.
# Try the list form first (read_yaml_list handles inline [a, b] and block "- "
# lists); fall back to a scalar via read_yaml_field, stripping surrounding
# quotes it leaves intact. Drop empties / literal "null". A missing config file
# yields nothing.
#
# Extracted verbatim from run_command_gate's former inline resolution so the
# command path is unchanged; the gate_command_exit_contract opt-in list below
# reads through the same function rather than growing a second parser.
#
# PUBLIC (t1597): it was `_gate_config_values` while both callers lived in this
# file. aitask_resource_admission.sh is a third caller from OUTSIDE it -- its key
# is not a gate command key and must NOT join GATE_COMMAND_KEYS (tests/
# test_gate_verifiers.sh Test 10 derives that constant from the aitask_gate_*.sh
# wrappers), but the "scalar or list, one value per line" resolution is exactly
# the same and must not be re-implemented.
project_config_values() {
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

# run_project_command_key <config_key> <log_path>
#
# THE canonical implementation of the project-command exit contract. Resolves
# project_config.yaml <config_key> (scalar OR list), runs the command(s)
# sequentially, tees their combined output to <log_path>, and reports a verdict
# through globals. It appends NOTHING to any ledger and prints nothing to
# stdout -- that is what lets both consumers share it:
#
#   1. run_command_gate() below   -- the machine-gate verifiers, which turn the
#                                    verdict into an appended gate-run block.
#   2. aitask_run_project_command.sh -- the legacy build-verification helper the
#                                    Step-9 / pickrem / pickweb agent prose calls
#                                    (t1610). No ledger, no task id required.
#
# Adding a third consumer is fine; restating the table below in one is not.
#
# RETURNS 0 on every verdict (the verdict is in the globals, not the status) and
# 3 when it could not evaluate at all -- today only a missing yaml_utils.sh.
# A caller MUST branch on the return before reading the globals: on 3 they are
# not set, and treating that as a verdict is the "empty parse is not a result"
# mistake this contract exists to prevent.
#
# OUTPUT (globals, all five set whenever it returns 0; none are printed):
#   PROJECT_CMD_STATUS  pass | fail | skip
#   PROJECT_CMD_CODE    0=pass 1=fail 2=skip  (the VERIFIER contract's codes,
#                       NOT the project command's own exit status)
#   PROJECT_CMD_REASON  none_configured | all_passed | command_failed |
#                       command_malformed | command_skipped -- machine-readable,
#                       and the ONLY thing that separates the two kinds of skip.
#                       command_malformed is a fail (t1609): a command that will
#                       not parse never ran, so it must never reach a skip.
#   PROJECT_CMD_RESULT  one-line human text (the gate-run block's `result=`)
#   PROJECT_CMD_NOTE    unrecognized-opt-in-key note, "" when there is none
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
#   verdict) but reported on stderr and in PROJECT_CMD_NOTE -- otherwise a
#   misspelled key looks exactly like "not opted in", which is the hardest
#   state to diagnose.
#
# AGGREGATION over a command list:
#   A fail short-circuits (later commands do NOT run). A skip does NOT: it is
#   remembered and the list continues, so a fail after a skip still wins.
#   any fail -> fail; else any skip -> skip; else pass.
#
# Paths are repo-root-relative: every caller runs from the repo root, so
# aitasks/metadata/... resolves correctly.
#
# shellcheck disable=SC2034  # PROJECT_CMD_REASON is read by the OTHER consumer
# (aitask_run_project_command.sh, which turns it into the REASON: output line);
# run_command_gate below has no use for it, so shellcheck cannot see a reader
# in this file. Removing the assignments would silently blank that line.
run_project_command_key() {
    local config_key="$1" log="$2"

    local config="aitasks/metadata/project_config.yaml"

    # Fail loudly on a missing YAML reader rather than silently resolving the
    # key to zero commands -- which looks exactly like "nothing configured" and
    # would report a wrong `skip` for a project that has a real build. Checked
    # here, not at file scope: sourcing this lib only to read GATE_COMMAND_KEYS
    # is legitimate (tests/test_gate_verifiers.sh Test 10 does exactly that),
    # and a file-scope `exit` would kill the sourcing shell outright.
    if ! declare -F read_yaml_list >/dev/null || ! declare -F read_yaml_field >/dev/null; then
        echo "run_project_command_key: lib/yaml_utils.sh must be sourced first" >&2
        return 3
    fi

    PROJECT_CMD_STATUS=""
    PROJECT_CMD_CODE=""
    PROJECT_CMD_REASON=""
    PROJECT_CMD_RESULT=""
    PROJECT_CMD_NOTE=""

    # Resolve command(s) through the shared reader (list form first, scalar
    # fallback, empties / literal "null" dropped).
    local -a cmds=()
    mapfile -t cmds < <(project_config_values "$config" "$config_key")

    # Resolve the per-key exit-contract opt-in, and collect unrecognized entries.
    # The WHOLE list is validated against GATE_COMMAND_KEYS -- not just this
    # call's own key -- so any consumer reports a typo.
    local exit_contract=0 k unknown_keys=""
    while IFS= read -r k; do
        # No re-stripping here: read_yaml_list unquotes both list forms itself
        # since t1609 (_yaml_norm_list_item), and the scalar fallback in
        # project_config_values above unquotes its own value. Test (j) in
        # tests/test_gate_verifiers.sh drives the quoted BLOCK form and is what
        # keeps that true.
        if [[ " $GATE_COMMAND_KEYS " != *" $k "* ]]; then
            unknown_keys="${unknown_keys:+$unknown_keys,}$k"
            continue
        fi
        [[ "$k" == "$config_key" ]] && exit_contract=1
    done < <(project_config_values "$config" "$GATE_COMMAND_EXIT_CONTRACT_KEY")

    if [[ -n "$unknown_keys" ]]; then
        PROJECT_CMD_NOTE="${GATE_COMMAND_EXIT_CONTRACT_KEY}: unrecognized key(s): ${unknown_keys} (expected one of: ${GATE_COMMAND_KEYS// /, })"
        printf '%s\n' "$PROJECT_CMD_NOTE" >&2
    fi

    if [[ ${#cmds[@]} -eq 0 ]]; then
        PROJECT_CMD_STATUS=skip
        PROJECT_CMD_CODE=2
        PROJECT_CMD_REASON=none_configured
        PROJECT_CMD_RESULT="no ${config_key} configured"
        printf '(no %s configured in %s; gate not applicable)\n' "$config_key" "$config" > "$log"
    else
        PROJECT_CMD_STATUS=pass
        PROJECT_CMD_CODE=0
        PROJECT_CMD_REASON=all_passed
        PROJECT_CMD_RESULT="all ${config_key} command(s) passed"
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
                PROJECT_CMD_STATUS=fail
                PROJECT_CMD_CODE=1
                PROJECT_CMD_REASON=command_malformed
                PROJECT_CMD_RESULT="malformed ${config_key} command (cannot parse): ${c}"
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
            PROJECT_CMD_STATUS=fail
            PROJECT_CMD_CODE=1
            PROJECT_CMD_REASON=command_failed
            PROJECT_CMD_RESULT="command failed (exit ${rc}): ${c}"
            break
        done
        if [[ "$PROJECT_CMD_STATUS" == pass && -n "$skipped_cmd" ]]; then
            PROJECT_CMD_STATUS=skip
            PROJECT_CMD_CODE=2
            PROJECT_CMD_REASON=command_skipped
            PROJECT_CMD_RESULT="command reported skip (exit ${GATE_COMMAND_SKIP_EXIT}): ${skipped_cmd}"
        fi
    fi

    # A bad opt-in entry never changes the verdict -- it only explains why an
    # expected skip did not happen. Record it in the run's own log too.
    [[ -z "$PROJECT_CMD_NOTE" ]] || printf '%s\n' "$PROJECT_CMD_NOTE" >> "$log"

    return 0
}

# run_command_gate <gate> <config_key> <verifier_name> <task-id> <attempt> <run-id>
#
# The machine-gate wrapper around run_project_command_key: allocates the sidecar
# log, delegates the whole exit contract to that function (see its docblock --
# the command-exit table and the aggregation rule live there and nowhere else),
# appends the terminal gate-run block via aitask_gate.sh, and RETURNS the
# verifier contract exit code.
#
# THIS FUNCTION'S OWN EXIT CODES -- what the orchestrator reads. NOT a claim
# about what the project command returned; the two are separate contracts and
# conflating them is what this function used to get wrong:
#   0 = pass   every command exited 0
#   1 = fail   a command failed
#   2 = skip   "evaluated, not applicable". EITHER no command is configured for
#              <config_key>, OR a command declared it did not run. The two are
#              distinguished in the appended `result=` line, never by the code.
#   3 = error  the runner could not evaluate at all (missing yaml_utils.sh);
#              nothing is appended -- an infrastructure failure, not a result
run_command_gate() {
    local gate="$1" config_key="$2" verifier_name="$3"
    local task_id="$4" attempt="$5" run_id="$6"

    local logdir=".aitask-gates/${task_id}"
    mkdir -p "$logdir"
    local log="${logdir}/${gate}_${run_id}.log"

    # Return 3 (could not evaluate) is the verifier contract's `error`, not a
    # gate result: append nothing rather than a block with an empty status.
    if ! run_project_command_key "$config_key" "$log"; then
        return 3
    fi

    # Surface a bad opt-in entry where it is durable (the ledger block) as well
    # as in the run's own log.
    local -a note_arg=()
    if [[ -n "$PROJECT_CMD_NOTE" ]]; then
        note_arg=(note="$PROJECT_CMD_NOTE")
    fi

    "$SCRIPT_DIR/aitask_gate.sh" append "$task_id" "$gate" "$PROJECT_CMD_STATUS" \
        run="$run_id" attempt="$attempt" type=machine \
        verifier="$verifier_name" result="$PROJECT_CMD_RESULT" log="$log" \
        ${note_arg[@]+"${note_arg[@]}"} >/dev/null

    return "$PROJECT_CMD_CODE"
}
