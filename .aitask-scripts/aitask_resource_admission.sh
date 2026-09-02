#!/usr/bin/env bash
# aitask_resource_admission.sh - consult the project's resource-admission hook
# before a task's implementation phase starts, and report a verdict (t1597).
#
# THE SEAM ONLY. The framework performs no resource/capacity check of its own;
# this runs the ONE command a project configures in project_config.yaml as
# `resource_admission_command` and turns its exit status into an admission
# verdict. The probe itself (memory thresholds, PSI, GPU, whatever the project
# is bound on) lives in the project, never here.
#
# NOT A GATE. Nothing is appended to any gate ledger and no task id is required
# for the decision -- `--task-id` only places the log beside a task's gate logs.
# The consumer is `.claude/skills/task-workflow/resource-admission.md`, which
# turns a non-zero exit into the approve-and-stop path (the task parks on its
# approved plan and returns to Ready). Sibling helper for the gate-shaped
# project commands: aitask_run_project_command.sh.
#
# Usage:
#   aitask_resource_admission.sh [--task-id <id>] [--plan <path>] [--log <path>]
#
#   --task-id <id> write the log under .aitask-gates/<id>/ so it sits beside the
#                  gate-path logs for the same task. Without it, a mktemp file.
#                  Also exported to the hook (see the environment table below).
#   --plan <path>  the externalized plan file; exported to the hook. Not read.
#   --log <path>   explicit log path; overrides --task-id placement. It names
#                  where a log WOULD go -- with no command configured nothing is
#                  created, not even this file.
#
# STDOUT is a pure data channel -- KEY:value lines, one per line, in this order.
# The hook's own output goes to the LOG, never here:
#
#   VERDICT:admit|refuse|error      -- ABSENT on exit 3 (see EXIT below)
#   REASON:none_configured|admitted|refused|command_malformed|command_error|not_scalar
#                                   -- not_scalar covers the two shapes that
#                                      resolve to NO scalar: a list of any
#                                      length, and an indented block. A value
#                                      that merely LOOKS structured on the key
#                                      line (`{foo: bar}`) is read as the
#                                      command it textually is; if it will not
#                                      run, that is command_malformed /
#                                      command_error -- still fail-closed, but
#                                      NOT not_scalar. Deliberate: `{ make
#                                      build; }` is a valid shell group command
#                                      and YAML parses it as a mapping, so
#                                      refusing flow mappings would reject a
#                                      working hook.
#   DETAIL:<one-line human text>    -- sanitized (see SANITIZING)
#   LOG:<path>|(none)               -- (none) = no command ran, nothing written
#   DIAG:<one-line sanitized text>  -- exit 3 ONLY, and ALWAYS on exit 3
#
# DIAG exists so the calling procedure never has to read stderr. Its prescribed
# capture form takes stdout only, and merging stderr in (`2>&1`) would corrupt
# this parse -- so an infrastructure outcome that spoke only on stderr would
# leave the agent with nothing deterministic to show the user. stderr stays
# human-facing and is never part of the contract.
#
# EXIT: 0=admit 1=refuse 2=error (the hook ran but could not decide)
#       3=usage/infrastructure -- NO VERDICT: line, which is how a caller tells
#         "could not evaluate at all" apart from any verdict. 2 and 3 are kept
#         distinct even though the workflow parks on both: a broken hook and a
#         broken invocation must not be indistinguishable.
#   1 and 2 are ORDINARY outcomes, not failures of this script. A caller under
#   `set -e` must not write `out="$(...)"; rc=$?` -- errexit fires on the
#   assignment and the shell dies before rc is captured. Use:
#       if out="$(./.aitask-scripts/aitask_resource_admission.sh --task-id 42)"; then
#         rc=0
#       else
#         rc=$?
#       fi
#
# THE HOOK'S OWN EXIT VOCABULARY -- a separate namespace from this script's:
#
#     hook exit | meaning
#     ----------+-------------------------------------------------------
#         0     | admit    -> proceed to implementation
#         2     | refuse   -> defer this task (RESOURCE_ADMISSION_REFUSE_EXIT)
#      anything | error    -> the hook could not decide
#        else   |
#
#   Unlike the gate command keys there is no per-key opt-in for exit 2: this key
#   is new and purpose-written, so its vocabulary is defined here rather than
#   inherited from tools that use 2 for their own failures.
#
#   A command that will not PARSE never ran, so `bash -n -c` runs first and a
#   parse failure is `command_malformed` (error) -- never a refusal. Same
#   reasoning as run_project_command_key's malformed handling.
#
# ENVIRONMENT HANDED TO THE HOOK -- the whole contract, nothing else:
#
#     AIT_RESOURCE_ADMISSION_TASK_ID     the --task-id value ("" when absent)
#     AIT_RESOURCE_ADMISSION_PLAN_FILE   the --plan value ("" when absent)
#
# SANITIZING. DETAIL prefers the LAST `ADMISSION_REASON: <text>` line in the
# hook's output (namespaced so it cannot collide with this script's own REASON:
# key), falls back to the last non-empty line, and otherwise reads "no reason
# given". DIAG is written by the same sanitizer. Both are author-controlled text
# landing in a line the caller parses, so they are stripped of control
# characters, collapsed to one line, and truncated.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/yaml_utils.sh
source "$SCRIPT_DIR/lib/yaml_utils.sh"
# shellcheck source=lib/gate_verifier_lib.sh
source "$SCRIPT_DIR/lib/gate_verifier_lib.sh"   # project_config_values()

# The project_config.yaml key. One key, one command.
RESOURCE_ADMISSION_KEY="resource_admission_command"

# The one hook exit code that means "refuse -- defer this task".
RESOURCE_ADMISSION_REFUSE_EXIT=2

# Ceiling for a sanitized one-line field (DETAIL / DIAG).
RESOURCE_ADMISSION_DETAIL_MAX=200

CONFIG_FILE="aitasks/metadata/project_config.yaml"

# sanitize_line <text>
# Collapse author-controlled text to ONE printable line: control characters
# (including CR/LF and ANSI escapes' ESC) dropped, whitespace runs collapsed,
# ends trimmed, truncated to RESOURCE_ADMISSION_DETAIL_MAX with an ellipsis.
# Every value this script prints for DETAIL: and DIAG: goes through here.
sanitize_line() {
    printf '%s' "$1" \
        | LC_ALL=C tr -d '\000-\037\177' \
        | LC_ALL=C sed 's/[[:space:]][[:space:]]*/ /g; s/^ //; s/ $//' \
        | LC_ALL=C awk -v max="$RESOURCE_ADMISSION_DETAIL_MAX" \
            '{ if (length($0) > max) printf "%s...", substr($0, 1, max); else printf "%s", $0 }'
}

# diag_exit <message>
# The exit-3 path: one sanitized DIAG: line on stdout (the caller's only
# deterministic diagnostic), the human message on stderr, NO VERDICT:.
# LOG: reports (none) until a log has actually been created and proven
# writable -- naming a path the caller cannot read anything from would send
# them to diagnostics that do not exist.
# yaml_key_has_block_child <file> <key>
# True when <key> is a TOP-LEVEL key whose inline value is empty and whose next
# content line is INDENTED -- i.e. its value is a nested block, not a scalar.
#
# read_yaml_list witnesses a block LIST but not a MAPPING: `k:` followed by an
# indented `sh -c "..."` resolves to nothing at all, and "nothing" is
# indistinguishable from "key absent" -- which turned a configured-but-mis-saved
# hook into a silent admit (t1672). An empty `key:` with NO indented body is not
# a block: that is the documented way to disable the hook and must keep reading
# as "not configured".
yaml_key_has_block_child() {
    local file="$1" key="$2" answer
    [[ -f "$file" ]] || return 1
    answer="$(LC_ALL=C awk -v key="$key" '
        seen == 0 {
            if (index($0, key ":") == 1 &&
                substr($0, length(key) + 2) ~ /^[[:space:]]*$/) seen = 1
            next
        }
        /^[[:space:]]*$/ { next }
        /^[[:space:]]*#/ { next }
        /^[[:space:]]/   { print "block"; exit }
        { exit }
    ' "$file")"
    [[ "$answer" == "block" ]]
}

diag_exit() {
    local msg="$1"
    printf 'LOG:%s\n' "$( [[ "${log_ready:-0}" == 1 ]] && printf '%s' "$log_path" || printf '(none)' )"
    printf 'DIAG:%s\n' "$(sanitize_line "$msg")"
    echo "aitask_resource_admission.sh: $msg" >&2
    exit 3
}

usage_error() {
    echo "usage: aitask_resource_admission.sh [--task-id <id>] [--plan <path>] [--log <path>]" >&2
    diag_exit "$1"
}

task_id=""
plan_file=""
log_path=""
log_ready=0   # 1 once the log exists and is proven writable (see diag_exit)

while [[ $# -gt 0 ]]; do
    case "$1" in
        --task-id)
            [[ $# -ge 2 ]] || usage_error "--task-id requires a value"
            task_id="$2"; shift 2 ;;
        --plan)
            [[ $# -ge 2 ]] || usage_error "--plan requires a value"
            plan_file="$2"; shift 2 ;;
        --log)
            [[ $# -ge 2 ]] || usage_error "--log requires a value"
            log_path="$2"; shift 2 ;;
        -h|--help)
            usage_error "help requested" ;;
        *)
            usage_error "unknown argument: $1" ;;
    esac
done

# The task id lands in a filesystem path, so keep it to the shape task ids
# actually take (`16`, `16_2`) instead of trusting the caller.
if [[ -n "$task_id" ]] && ! [[ "$task_id" =~ ^[0-9]+(_[0-9]+)*$ ]]; then
    usage_error "invalid --task-id '$task_id' (expected e.g. 16 or 16_2)"
fi

# --- resolve the hook BEFORE allocating anything ---------------------------
#
# Deliberately the INVERSE of aitask_run_project_command.sh's ordering, which
# allocates the log first and then writes "(no X configured)" into it. That is
# right for a gate the project opted into and wrong for a hook on the ordinary
# path: this script runs at EVERY Step 7, so an unconfigured project would
# collect a fresh .aitask-gates/<id>/ directory and a timestamped,
# audit-looking artifact for a feature it never enabled. Unset must mean
# UNTOUCHED -- no directory, no file, not even under an explicit --log.
#
# THE KEY IS SCALAR-ONLY, AND THAT IS CHECKED ON THE YAML SHAPE, NOT ON A COUNT.
# project_config_values() is shape-agnostic by design -- its other callers accept
# both forms, so it flattens `k: cmd` and `k: [cmd]` to the same one value. A
# count-based check would therefore admit a one-element list while rejecting a
# two-element one: a contract the user only discovers by tripping over the
# boundary. read_yaml_list() is the shape witness -- empty for EVERY scalar form
# (including `"pytest -k 'a,b'"`, whose comma must not read as a list), non-empty
# for every list form whatever its length -- so ask it first and refuse the list
# form outright. The scalar then goes through project_config_values() for its
# quote-stripping and null/empty handling; no third parser is introduced.
declare -a as_list=()
mapfile -t as_list < <(read_yaml_list "$CONFIG_FILE" "$RESOURCE_ADMISSION_KEY" 2>/dev/null || true)
if [[ ${#as_list[@]} -gt 0 ]]; then
    printf 'REASON:not_scalar\n'
    diag_exit "$RESOURCE_ADMISSION_KEY must be a single command, not a YAML list (got a ${#as_list[@]}-item list in $CONFIG_FILE) -- point it at one wrapper script instead"
fi

# A NESTED BLOCK IS NOT A SCALAR EITHER, and unlike a list it is INVISIBLE to
# both readers above: it resolves to zero values, which is exactly what "key
# absent" resolves to. Collapsing the two would report `none_configured` and
# exit 0 for a project that HAS configured a hook -- a silent admit, inverting
# this feature's fail-closed posture (t1672). Checked after the list refusal, so
# a block LIST keeps its own message.
if yaml_key_has_block_child "$CONFIG_FILE" "$RESOURCE_ADMISSION_KEY"; then
    printf 'REASON:not_scalar\n'
    diag_exit "$RESOURCE_ADMISSION_KEY must be a single command string, but its value in $CONFIG_FILE is an indented block, not a scalar -- put the command on the key line (quote it if it contains a colon)"
fi

declare -a cmds=()
mapfile -t cmds < <(project_config_values "$CONFIG_FILE" "$RESOURCE_ADMISSION_KEY")

if [[ ${#cmds[@]} -eq 0 ]]; then
    printf 'VERDICT:admit\n'
    printf 'REASON:none_configured\n'
    printf 'DETAIL:no %s configured\n' "$RESOURCE_ADMISSION_KEY"
    printf 'LOG:(none)\n'
    exit 0
fi

# Belt and braces: the shape check above already refused every list form, so
# reaching here with more than one value would mean the resolver disagreed with
# read_yaml_list about what a list is. Refuse rather than silently running the
# first of them.
if [[ ${#cmds[@]} -gt 1 ]]; then
    printf 'REASON:not_scalar\n'
    diag_exit "$RESOURCE_ADMISSION_KEY resolved to ${#cmds[@]} values in $CONFIG_FILE despite not being a list -- refusing to guess which one to run"
fi
command_str="${cmds[0]}"

# --- allocate the log (a command exists, so its output has somewhere to go) --
if [[ -z "$log_path" ]]; then
    if [[ -n "$task_id" ]]; then
        logdir=".aitask-gates/${task_id}"
        mkdir -p "$logdir" || diag_exit "could not create log directory: $logdir"
        log_path="${logdir}/resource_admission_$(date -u +%Y%m%dT%H%M%SZ)_$$.log"
    else
        log_path="$(mktemp "${TMPDIR:-/tmp}/aitask_resource_admission_XXXXXX.log")" \
            || diag_exit "could not create a temporary log file"
    fi
else
    log_parent="$(dirname "$log_path")"
    mkdir -p "$log_parent" || diag_exit "could not create log directory: $log_parent"
fi

# Prove the log is WRITABLE before running anything: `bash -n -c "$c" 2>>"$log"`
# below fails on the REDIRECTION when the log cannot be written, which would
# report a perfectly valid command as malformed. A log this script cannot write
# is an infrastructure error (exit 3, no verdict), never a verdict.
: > "$log_path" || diag_exit "log file is not writable: $log_path"
log_ready=1

emit() { # emit <verdict> <reason> <detail> <exit-code>
    printf 'VERDICT:%s\n' "$1"
    printf 'REASON:%s\n'  "$2"
    printf 'DETAIL:%s\n'  "$(sanitize_line "$3")"
    printf 'LOG:%s\n'     "$log_path"
    exit "$4"
}

printf '$ %s\n' "$command_str" >> "$log_path"

if ! bash -n -c "$command_str" 2>>"$log_path"; then
    emit error command_malformed \
        "malformed $RESOURCE_ADMISSION_KEY (cannot parse): $command_str" 2
fi

rc=0
AIT_RESOURCE_ADMISSION_TASK_ID="$task_id" \
AIT_RESOURCE_ADMISSION_PLAN_FILE="$plan_file" \
    bash -c "$command_str" >> "$log_path" 2>&1 || rc=$?

# The hook's human-readable reason: its own namespaced line if it gave one,
# else its last word on the matter, else empty.
#
# `tail -n +2` skips the `$ <command>` banner this script wrote at the top of
# the log. Without it a silent hook's "reason" would be the banner -- i.e. this
# script quoting the project's own configuration back at the user as if the hook
# had said it.
hook_reason="$(tail -n +2 "$log_path" \
    | sed -n 's/^[[:space:]]*ADMISSION_REASON:[[:space:]]*//p' | tail -n1)"
if [[ -z "$hook_reason" ]]; then
    hook_reason="$(tail -n +2 "$log_path" | grep -v '^[[:space:]]*$' | tail -n1 || true)"
fi

# The default differs by verdict, deliberately. "no reason given" is the honest
# thing to say about a refusal or an error -- a stop the user cannot act on is a
# stop they learn to route around -- but it reads as a complaint about an admit,
# which needs no reason at all.
if [[ $rc -eq 0 ]]; then
    emit admit admitted "${hook_reason:-admitted}" 0
fi

if [[ $rc -eq $RESOURCE_ADMISSION_REFUSE_EXIT ]]; then
    emit refuse refused "${hook_reason:-no reason given}" 1
fi

emit error command_error \
    "$RESOURCE_ADMISSION_KEY could not decide (exit $rc): ${hook_reason:-no reason given}" 2
