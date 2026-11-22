#!/usr/bin/env bash
# aitask_path.sh — Prepend ~/.aitask/bin to PATH for aitasks subprocesses.
#
# Sourced (not executed) by the `ait` dispatcher and by individual
# `.aitask-scripts/aitask_*.sh` scripts. The export is scoped to the
# current bash process and its descendants; the user's interactive
# shell rc is intentionally left untouched.
#
# Idempotent: sourcing this multiple times does not duplicate the entry.

if [[ -n "${_AIT_PATH_LOADED:-}" ]]; then
    return 0
fi
_AIT_PATH_LOADED=1

# With HOME unset or empty there is no per-user bin dir to prepend: skip,
# rather than abort a `set -u` caller or put a root-level `/.aitask/bin` on
# PATH (t2347).
if [[ -n "${HOME:-}" ]]; then
    case ":$PATH:" in
        *":$HOME/.aitask/bin:"*) ;;
        *) export PATH="$HOME/.aitask/bin:$PATH" ;;
    esac
fi
