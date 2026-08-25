#!/usr/bin/env bash
# aitask_run_project_command.sh - run one project_config.yaml command key under
# the gate exit contract and report a verdict, WITHOUT touching any gate ledger.
#
# This is the legacy build-verification path's counterpart to the three
# aitask_gate_*.sh verifiers: same rule, same code, no ledger and no task id
# required. It exists so the Step-9 / pickrem / pickweb / aitask-qa agent prose
# stops re-implementing the exit contract in English and disagreeing with the
# gate path (t1610). The contract itself is documented in exactly one place --
# run_project_command_key()'s docblock in lib/gate_verifier_lib.sh. Do not
# restate the command-exit table here or in any calling SKILL.md.
#
# Usage:
#   aitask_run_project_command.sh <config_key> [--task-id <id>] [--log <path>]
#
#   <config_key>   one of verify_build | test_command | lint_command
#                  (validated against GATE_COMMAND_KEYS -- anything else exits 3)
#   --task-id <id> write the log under .aitask-gates/<id>/ so it sits beside the
#                  gate-path logs for the same task. Without it, a mktemp file.
#   --log <path>   explicit log path; overrides --task-id placement.
#
# STDOUT is a pure data channel -- KEY:value lines, one per line, in this order.
# The command's own output goes to the LOG, never here:
#
#   VERDICT:pass|fail|skip
#   REASON:none_configured|all_passed|command_failed|command_malformed|command_skipped
#   DETAIL:<one-line human text>
#   LOG:<path>
#   NOTE:<text>     -- only when an unrecognized gate_command_exit_contract entry
#                      was seen; the machine-readable copy of the stderr warning
#
# STDERR carries human-facing warnings only. Callers must NOT merge it into
# stdout (`2>&1`), which would corrupt the KEY:value parse.
#
# EXIT: 0=pass 1=fail 2=skip 3=usage/infrastructure error (bad argument, or a log
#       that cannot be created or written -- the LOG: path is part of the
#       contract, so a log this script cannot write is never a verdict).
#   1 and 2 are ORDINARY outcomes, not failures of this script. A caller under
#   `set -e` must not write `out="$(...)"; rc=$?` -- errexit fires on the
#   assignment and the shell dies before rc is captured. Use:
#       if out="$(./.aitask-scripts/aitask_run_project_command.sh verify_build)"; then
#         rc=0
#       else
#         rc=$?
#       fi
#   On exit 3 NO VERDICT: line is printed, which is how a caller tells "could
#   not evaluate" apart from any verdict.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/yaml_utils.sh
source "$SCRIPT_DIR/lib/yaml_utils.sh"
# shellcheck source=lib/gate_verifier_lib.sh
source "$SCRIPT_DIR/lib/gate_verifier_lib.sh"

usage_error() {
    echo "aitask_run_project_command.sh: $1" >&2
    echo "usage: aitask_run_project_command.sh <config_key> [--task-id <id>] [--log <path>]" >&2
    echo "       <config_key> is one of: ${GATE_COMMAND_KEYS// /, }" >&2
    exit 3
}

# An environment failure, as opposed to a caller mistake: same exit 3 (the
# caller's only question is "did I get a verdict?", and the answer is no either
# way), but no usage banner -- the invocation was fine, the environment was not.
infra_error() {
    echo "aitask_run_project_command.sh: $1" >&2
    exit 3
}

config_key=""
task_id=""
log_path=""
log_parent=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --task-id)
            [[ $# -ge 2 ]] || usage_error "--task-id requires a value"
            task_id="$2"; shift 2 ;;
        --log)
            [[ $# -ge 2 ]] || usage_error "--log requires a value"
            log_path="$2"; shift 2 ;;
        -h|--help)
            usage_error "help requested" ;;
        -*)
            usage_error "unknown option: $1" ;;
        *)
            [[ -z "$config_key" ]] || usage_error "unexpected extra argument: $1"
            config_key="$1"; shift ;;
    esac
done

[[ -n "$config_key" ]] || usage_error "missing <config_key>"

# Reject an unknown key rather than reporting "nothing configured" for it: a
# typo'd key resolves to zero commands, and a silent skip is the hardest
# possible failure to notice.
if [[ " $GATE_COMMAND_KEYS " != *" $config_key "* ]]; then
    usage_error "unknown config key '$config_key' (expected one of: ${GATE_COMMAND_KEYS// /, })"
fi

# The task id lands in a filesystem path, so keep it to the shape task ids
# actually take (`16`, `16_2`) instead of trusting the caller.
if [[ -n "$task_id" ]] && ! [[ "$task_id" =~ ^[0-9]+(_[0-9]+)*$ ]]; then
    usage_error "invalid --task-id '$task_id' (expected e.g. 16 or 16_2)"
fi

if [[ -z "$log_path" ]]; then
    if [[ -n "$task_id" ]]; then
        logdir=".aitask-gates/${task_id}"
        mkdir -p "$logdir" || infra_error "could not create log directory: $logdir"
        log_path="${logdir}/${config_key}_legacy_$(date -u +%Y%m%dT%H%M%SZ)_$$.log"
    else
        log_path="$(mktemp "${TMPDIR:-/tmp}/aitask_${config_key}_XXXXXX.log")" \
            || infra_error "could not create a temporary log file"
    fi
else
    log_parent="$(dirname "$log_path")"
    mkdir -p "$log_parent" \
        || infra_error "could not create log directory: $log_parent"
fi

# Prove the log is WRITABLE before running anything. Every branch above funnels
# through here, so the LOG: path this script reports is always one the caller can
# actually read the command's output from.
#
# This is not belt-and-braces. run_project_command_key writes the command's
# output with `>> "$log"`, and its `bash -n -c "$c" 2>>"$log"` parse check
# redirects to the same file -- so an unwritable log makes bash fail on the
# REDIRECTION before it ever parses the command, and a perfectly valid command
# comes back as `command_malformed`. A log-setup failure must therefore be an
# infrastructure error (exit 3, no verdict), never a verdict: reporting a fail,
# or a skip with a LOG: path that holds nothing, would send the caller to
# diagnostics that do not exist.
: > "$log_path" || infra_error "log file is not writable: $log_path"

if ! run_project_command_key "$config_key" "$log_path"; then
    echo "aitask_run_project_command.sh: could not evaluate '$config_key'" >&2
    exit 3
fi

# The PROJECT_CMD_* globals are assigned by run_project_command_key in the
# sourced lib, which shellcheck does not follow (SC1091) -- hence the SC2153
# suppression on the exit below rather than a local re-assignment here.
printf 'VERDICT:%s\n' "$PROJECT_CMD_STATUS"
printf 'REASON:%s\n'  "$PROJECT_CMD_REASON"
printf 'DETAIL:%s\n'  "$PROJECT_CMD_RESULT"
printf 'LOG:%s\n'     "$log_path"
[[ -z "$PROJECT_CMD_NOTE" ]] || printf 'NOTE:%s\n' "$PROJECT_CMD_NOTE"

# shellcheck disable=SC2153  # assigned by run_project_command_key (sourced lib)
exit "$PROJECT_CMD_CODE"
