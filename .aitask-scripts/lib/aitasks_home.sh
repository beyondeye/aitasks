#!/usr/bin/env bash
# aitasks_home.sh — the per-user framework root ($AITASKS_HOME).
#
# Sourced (not executed) by every bash piece of the test-map feature: the
# `ait testmap` shim, install_engine_binary() / aitask_engine.sh, the gate
# verifiers and aitask_test.sh. It is the ONE owner of the path: nothing
# else composes "$HOME/.aitasks", and it never falls back to the legacy
# per-user root (venv, bin, python, uv, …), which coexists with this one
# until `ait engine home --migrate` runs.
#
# Exports: AITASKS_HOME, AITASKS_HOME_LOCK. Function: aitasks_engine_dir.
# Idempotent: sourcing this multiple times is a no-op after the first.

if [[ -n "${_AITASKS_HOME_LOADED:-}" ]]; then
    return 0
fi
_AITASKS_HOME_LOADED=1

export AITASKS_HOME="${AITASKS_HOME:-$HOME/.aitasks}"
# Taken (flock) by `ait engine home --migrate` and refused-against by any
# `ait` that would otherwise touch the root mid-move.
export AITASKS_HOME_LOCK="$AITASKS_HOME/.home.lock"

# aitasks_engine_dir <version|dev> — print the engine slot for one version:
#   dev        → $AITASKS_HOME/engine/dev
#   <version>  → $AITASKS_HOME/engine/v<version>   (bare version, no `v`)
# No trailing slash; callers append "/ait-testmap". Empty arg → usage, 2.
aitasks_engine_dir() {
    local version="${1:-}"
    if [[ -z "$version" ]]; then
        echo "usage: aitasks_engine_dir <version|dev>" >&2
        return 2
    fi
    if [[ "$version" == "dev" ]]; then
        printf '%s\n' "$AITASKS_HOME/engine/dev"
    else
        printf '%s\n' "$AITASKS_HOME/engine/v$version"
    fi
}
