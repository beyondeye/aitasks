#!/usr/bin/env bash
# Shared helpers for aitask_verified_update.sh and aitask_usage_update.sh.
# Caller scripts source terminal_compat.sh and task_utils.sh first (task_utils.sh
# brings python_resolve.sh, whose resolve_python this file uses).
#
# The counters live on the `aitask-stats` plumbing branch and are written by
# aitask_model_stats.py (lib/model_stats_store.py). Nothing here reads or writes
# the task-data worktree: no fetch, merge, rebase, push or index change of
# `aitask-data` (t1912_4).

[[ -n "${_AIT_VERIFIED_UPDATE_LIB_LOADED:-}" ]] && return 0
_AIT_VERIFIED_UPDATE_LIB_LOADED=1

# How to register a model that is missing from models_<agent>.json. The route
# is agent-specific: aitask_add_model.sh rejects opencode, whose models are
# CLI-discovered. A resolver fallback (unregistered_*) always lands here.
model_registration_hint() {
    case "$1" in
        opencode) echo "run /aitask-refresh-code-models (OpenCode models are CLI-discovered; /aitask-add-model does not accept opencode)" ;;
        *)        echo "register it with /aitask-add-model" ;;
    esac
}

# Out-param of model_stats_write (a global, because the caller must not run the
# function in $( ): the CLI's stderr has to reach the caller's stderr).
MODEL_STATS_LINE=""

# model_stats_write <verb> --agent A --model M --skill S [--opt value ...]
# (every argument after the verb is an `--option value` pair)
#
# Run aitask_model_stats.py <verb> against the repo root (the cwd: the caller
# anchored it with ait_cd_repo_root). Sets MODEL_STATS_LINE to the CLI's last
# stdout line, or to a synthesized STATS_ERROR:<reason>, and returns 0 only for
# an `UPDATED:<A>/<M>:<S>:<value>` line with exit 0. `UPDATED:` always means the
# write is recorded; <value> is an integer or the literal `unknown` (recorded,
# but the effective total could not be read).
#
#   STATS_DIVERGED:<l>|<r>        -> STATS_ERROR:diverged:<l>|<r>
#   no CLI / no Python            -> STATS_ERROR:cli_missing / STATS_ERROR:no_python
#   UPDATED: for another target,
#   or no recognised line         -> STATS_ERROR:unexpected_output
#
# The CLI's stderr is forwarded unconditionally, even for --silent callers: it
# is quiet on success and carries only real problems (an unavailable total, a
# local stats ref that could not be advanced after a durable push).
model_stats_write() {
    local verb="$1"; shift
    local cli="$SCRIPT_DIR/aitask_model_stats.py"
    local py out rc=0 agent="" model="" skill="" opt value

    # Every option of these verbs takes a value, and each pair is forwarded as
    # ONE `--opt=value` token. A separate value that starts with `-` (a skill
    # such as `-custom`, which the writers always accepted) would otherwise be
    # read by argparse as an option of its own. The target is recorded here for
    # the echo check below.
    local -a fwd=()
    while (( $# > 0 )); do
        opt="$1"
        if (( $# < 2 )); then
            MODEL_STATS_LINE="STATS_ERROR:usage:${opt} requires a value"
            return 2
        fi
        value="$2"
        shift 2
        case "$opt" in
            --agent) agent="$value" ;;
            --model) model="$value" ;;
            --skill) skill="$value" ;;
        esac
        fwd+=("${opt}=${value}")
    done

    MODEL_STATS_LINE=""
    if [[ ! -f "$cli" ]]; then
        MODEL_STATS_LINE="STATS_ERROR:cli_missing"
        return 1
    fi
    py="$(resolve_python 2>/dev/null || true)"
    if [[ -z "$py" ]]; then
        MODEL_STATS_LINE="STATS_ERROR:no_python"
        return 1
    fi

    out="$("$py" "$cli" "$verb" "${fwd[@]}" "--root=$PWD")" || rc=$?
    MODEL_STATS_LINE="$(printf '%s\n' "$out" | tail -n 1)"

    case "$MODEL_STATS_LINE" in
        UPDATED:*)
            local want="UPDATED:${agent}/${model}:${skill}:" value
            value="${MODEL_STATS_LINE#"$want"}"
            if (( rc == 0 )) && [[ "$MODEL_STATS_LINE" == "$want"* ]] \
                    && [[ "$value" =~ ^([0-9]+|unknown)$ ]]; then
                return 0
            fi
            MODEL_STATS_LINE="STATS_ERROR:unexpected_output"
            ;;
        STATS_DIVERGED:*)
            MODEL_STATS_LINE="STATS_ERROR:diverged:${MODEL_STATS_LINE#STATS_DIVERGED:}"
            ;;
        STATS_ERROR:*)
            ;;
        *)
            MODEL_STATS_LINE="STATS_ERROR:unexpected_output"
            ;;
    esac
    (( rc != 0 )) || rc=1
    return "$rc"
}
