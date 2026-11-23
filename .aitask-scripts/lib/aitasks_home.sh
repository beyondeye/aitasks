#!/usr/bin/env bash
# shellcheck disable=SC2034  # AITASKS_HOME_REFUSAL is read by the sourcers
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
# Idempotent: sourcing this multiple times is a no-op after the first
# SUCCESSFUL source.
#
# Refusal (t2348): when no usable root can be established, sourcing prints one
# `Error:` line, sets AITASKS_HOME_REFUSAL (plain, not exported) and returns 1.
# It exports nothing new and defines nothing, and the loaded flag stays unset,
# so a later source re-checks. AITASKS_HOME_REFUSAL is one of:
#   home-unset       AITASKS_HOME unset/empty AND HOME unset/empty: no root to
#                    derive. "/.aitasks" would make every engine path root-level.
#                    An explicit AITASKS_HOME needs no HOME.
#   root-unsettable  the root could not be assigned (AITASKS_HOME readonly and
#                    empty, or AITASKS_HOME_LOCK readonly with another value).
#                    Checked up front because a conditional `source` under
#                    errexit would otherwise run on past the failed assignment.
# Every sourcer must propagate the refusal EXPLICITLY (`source … || exit 1`,
# `|| return 1`, or a structured status): a sourced `return 1` is silently
# swallowed when the caller runs with errexit off (install.sh calls the engine
# installer as `… || true`).

if [[ -n "${_AITASKS_HOME_LOADED:-}" ]]; then
    return 0
fi
AITASKS_HOME_REFUSAL=""

# Validate CANDIDATE values first and publish nothing until both are known to
# be settable. A refusal must not leave a derived root behind for a later
# retry to reuse. Each refusal unsets these two temporaries.
_aitasks_home_root="${AITASKS_HOME:-}"
if [[ -z "$_aitasks_home_root" ]]; then
    if [[ -z "${HOME:-}" ]]; then
        unset _aitasks_home_root
        AITASKS_HOME_REFUSAL=home-unset
        echo "Error: AITASKS_HOME is unset and HOME is unset or empty, so the per-user framework root (\$HOME/.aitasks) cannot be derived; set AITASKS_HOME (or HOME)." >&2
        return 1
    fi
    if [[ "$(declare -p AITASKS_HOME 2>/dev/null)" =~ ^declare\ -[A-Za-z]*r ]]; then
        unset _aitasks_home_root
        AITASKS_HOME_REFUSAL=root-unsettable
        echo "Error: AITASKS_HOME is readonly and empty, so the per-user framework root cannot be set; unset it, or give it a value before marking it readonly." >&2
        return 1
    fi
    _aitasks_home_root="$HOME/.aitasks"
fi
# A stale_lock mutex taken by `ait engine home --migrate` for the whole move,
# so a second migration refuses (`HOME_SKIPPED:busy`) instead of racing it.
_aitasks_home_lock="$_aitasks_home_root/.home.lock"
if [[ "${AITASKS_HOME_LOCK:-}" != "$_aitasks_home_lock" &&
      "$(declare -p AITASKS_HOME_LOCK 2>/dev/null)" =~ ^declare\ -[A-Za-z]*r ]]; then
    unset _aitasks_home_root _aitasks_home_lock
    AITASKS_HOME_REFUSAL=root-unsettable
    echo "Error: AITASKS_HOME_LOCK is readonly with a value other than <root>/.home.lock, so the per-user framework root cannot be set up; unset it." >&2
    return 1
fi

# Publish. A value that is already correct is exported WITHOUT reassignment,
# so a readonly variable that already holds it never triggers a readonly error.
[[ "${AITASKS_HOME:-}" == "$_aitasks_home_root" ]] || AITASKS_HOME="$_aitasks_home_root"
export AITASKS_HOME
[[ "${AITASKS_HOME_LOCK:-}" == "$_aitasks_home_lock" ]] || AITASKS_HOME_LOCK="$_aitasks_home_lock"
export AITASKS_HOME_LOCK
# Backstop for any other failed assignment: never continue on a root that did
# not take.
if [[ "${AITASKS_HOME:-}" != "$_aitasks_home_root" || "${AITASKS_HOME_LOCK:-}" != "$_aitasks_home_lock" ]]; then
    unset _aitasks_home_root _aitasks_home_lock
    AITASKS_HOME_REFUSAL=root-unsettable
    echo "Error: AITASKS_HOME / AITASKS_HOME_LOCK could not be set, so the per-user framework root is unusable." >&2
    return 1
fi
unset _aitasks_home_root _aitasks_home_lock

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

# Set last: only a fully initialised root counts as loaded.
_AITASKS_HOME_LOADED=1
