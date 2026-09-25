#!/usr/bin/env bash
# claude_hook_status.sh - Is the Claude Code session hook installed, and can it work? (t1849)
#
# `ait upgrade` stages the SessionStart hook seed but never merges it into
# .claude/settings.json -- only `ait setup` does, behind its own consent prompt.
# A project set up before the hook shipped and only upgraded since therefore has
# no hook, and every Claude Code agent in it freezes into a record with no
# session id, which restore refuses (`agent_restore.py::resume_blocker` ->
# no_session). This lib is how the installer, `ait setup --hooks-only` and
# `ait ide` notice that and say what to do. It never installs anything.
#
#   claude_session_hook_status <project_dir>
#       NO_SEED | INSTALLED | MISSING | INVALID | UNKNOWN
#   claude_session_hook_runtime
#       OK | NO_PYTHON3 | PYTHON3_BROKEN:<path> | NO_PYTHON | TOO_OLD:<path>
#       | OVERRIDE_TOO_OLD:<path>
#   claude_session_hook_runtime_ok          rc 0 iff the runtime is OK
#   claude_session_hook_repair              the one repair instruction
#   claude_session_hook_hint                the MISSING hint (embeds the repair)
#   claude_session_hook_invalid_hint        the INVALID hint
#   claude_session_hook_seed_repair <dir>   how to restore a missing seed
#
# Every function prints one line and returns 0 (except `_runtime_ok`, which is a
# predicate), so callers under `set -e` are safe.
#
# Sourced lazily, from inside the functions that need it: it is not part of any
# script's source-on-startup chain (aidocs/framework/shell_conventions.md).

[[ -n "${_AIT_CLAUDE_HOOK_STATUS_LOADED:-}" ]] && return 0
_AIT_CLAUDE_HOOK_STATUS_LOADED=1

_AIT_CLAUDE_HOOK_STATUS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=python_resolve.sh
source "$_AIT_CLAUDE_HOOK_STATUS_DIR/python_resolve.sh"

# _claude_hook_selected_python — the interpreter the session-store writer
# (`aitask_agent_sessions.sh` -> `require_ait_python`) would pick in a fresh
# process. The memo is bypassed so a value resolved earlier in THIS shell (or
# before AIT_PYTHON changed) cannot stand in for the writer's own resolution.
_claude_hook_selected_python() {
    _AIT_RESOLVED_PYTHON="" resolve_python
}

# _claude_hook_python_meets_min <python> — `require_modern_python`'s predicate,
# minus the `die`: resolve_python only LOCATES an executable, the version gate
# is separate, and a probe must not exit the caller.
_claude_hook_python_meets_min() {
    local p="$1" min="$AIT_VENV_PYTHON_MIN" major minor
    major="${min%%.*}"
    minor="${min##*.}"
    [[ -n "$p" ]] || return 1
    "$p" -c "import sys; sys.exit(0 if sys.version_info >= ($major, $minor) else 1)" 2>/dev/null
}

claude_session_hook_runtime() {
    # 1. The hook parses its payload with a bare `python3` (aitask_session_hook.sh),
    #    so that exact command must RUN -- being on PATH is not enough (a broken
    #    install, or the framework wrapper with its venv gone).
    local py3
    py3="$(command -v python3 2>/dev/null || true)"
    if [[ -z "$py3" ]]; then
        echo "NO_PYTHON3"
        return 0
    fi
    if ! python3 -c 'import json, sys' >/dev/null 2>&1; then
        echo "PYTHON3_BROKEN:$py3"
        return 0
    fi
    # 2. The store writer needs Python >= AIT_VENV_PYTHON_MIN.
    local p
    p="$(_claude_hook_selected_python)"
    if [[ -z "$p" ]]; then
        echo "NO_PYTHON"
        return 0
    fi
    if _claude_hook_python_meets_min "$p"; then
        echo "OK"
    elif [[ -n "${AIT_PYTHON:-}" && -x "${AIT_PYTHON:-}" && "$p" == "$AIT_PYTHON" ]]; then
        # resolve_python's FIRST candidate. A full `ait setup` would not help:
        # it installs a modern venv, but the explicit override still wins.
        echo "OVERRIDE_TOO_OLD:$p"
    else
        echo "TOO_OLD:$p"
    fi
    return 0
}

claude_session_hook_runtime_ok() {
    [[ "$(claude_session_hook_runtime)" == "OK" ]]
}

claude_session_hook_status() {
    local project_dir="$1"
    local seed="$project_dir/aitasks/metadata/claude_settings.hooks.json"
    local dest="$project_dir/.claude/settings.json"

    if [[ ! -f "$seed" ]]; then
        echo "NO_SEED"
        return 0
    fi
    # Absence proves it, with no parsing -- the common upgraded-only case, and
    # install.sh may be running on a machine with no usable Python.
    if [[ ! -f "$dest" ]]; then
        echo "MISSING"
        return 0
    fi

    local p rc=0
    p="$(_claude_hook_selected_python)"
    if _claude_hook_python_meets_min "$p"; then
        "$p" "$_AIT_CLAUDE_HOOK_STATUS_DIR/claude_hooks_merge.py" check "$dest" "$seed" \
            >/dev/null 2>&1 || rc=$?
        case "$rc" in
            0) echo "INSTALLED" ;;
            1) echo "MISSING" ;;
            *) echo "INVALID" ;;
        esac
        return 0
    fi

    # No usable Python: a file that never names the hook script cannot contain
    # the hook. Anything else cannot be decided here.
    if ! grep -qF "aitask_session_hook.sh" "$dest" 2>/dev/null; then
        echo "MISSING"
    else
        echo "UNKNOWN"
    fi
    return 0
}

claude_session_hook_repair() {
    local runtime
    runtime="$(claude_session_hook_runtime)"
    case "$runtime" in
        OK)
            echo "run 'ait setup --hooks-only'"
            ;;
        PYTHON3_BROKEN:*)
            local py3="${runtime#PYTHON3_BROKEN:}"
            if [[ "$py3" == "$HOME/.aitask/bin/python3" ]]; then
                # The framework's own wrapper: it execs the venv, which setup rebuilds.
                echo "the framework's python3 wrapper ($py3) does not run — run the full 'ait setup', which repairs it and then offers the hook"
            else
                echo "python3 on your PATH ($py3) does not run, and the hook calls it directly — repair or replace it, then run 'ait setup --hooks-only'"
            fi
            ;;
        OVERRIDE_TOO_OLD:*)
            echo "AIT_PYTHON=${runtime#OVERRIDE_TOO_OLD:} is older than Python $AIT_VENV_PYTHON_MIN and overrides every other interpreter, so the session store would keep using it — unset AIT_PYTHON or point it at Python >=$AIT_VENV_PYTHON_MIN, then run 'ait setup --hooks-only'"
            ;;
        *)
            echo "run the full 'ait setup', which installs the Python runtime the hook needs and then offers the hook"
            ;;
    esac
    return 0
}

claude_session_hook_hint() {
    echo "The Claude Code session hook is not installed in .claude/settings.json, so Claude Code agents started in this project record no session id and cannot be restored after a freeze. To install it, $(claude_session_hook_repair). It only helps Claude Code agents started afterwards: agents already frozen without a session id stay view-only (re-pick them if they have a task), and running ones need a restart."
    return 0
}

# claude_session_hook_seed_repair <project_dir> — how to get the hook seed back.
# A source checkout carries seed/, which `ait setup` copies into metadata
# (ensure_agent_config_seeds). An installed project does not: install.sh stages
# the seed and then deletes seed/, so only the installer can supply it again.
claude_session_hook_seed_repair() {
    local project_dir="$1" root
    if [[ -f "$project_dir/seed/claude_settings.hooks.json" ]]; then
        echo "run 'ait setup' to restore it"
        return 0
    fi
    # --dir with the resolved root: `ait` may have been run from a subdirectory,
    # and install.sh defaults to "." -- a copied command would target the
    # caller's cwd instead of the project.
    root="$(cd "$project_dir" 2>/dev/null && pwd -P)" || root="$project_dir"
    echo "the installer stages it: 'ait upgrade' does so when a newer release is available; on the latest version, reinstall it with: curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash -s -- --force --dir $(printf '%q' "$root")"
    return 0
}

claude_session_hook_invalid_hint() {
    echo "The Claude Code session hook cannot be checked: .claude/settings.json is not valid JSON (or its hooks section is malformed). Fix the file, then run 'ait setup --hooks-only'."
    return 0
}
