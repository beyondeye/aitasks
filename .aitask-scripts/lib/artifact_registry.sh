#!/usr/bin/env bash
# artifact_registry.sh - bash front for the artifact backend registry
# (t1076_3; design: aidocs/unified_artifact_design.md par.6). Wraps
# lib/artifact_registry.py, which validates a backend name against the
# git-tracked `artifacts:` block in aitasks/metadata/project_config.yaml and
# prints the adapter's param env vars.
#
# artifact_registry_activate <name> is THE way to select a backend before any
# artifact_backend_* / artifact_resolve / artifact_store call: it exports
# ARTIFACT_BACKEND plus the adapter params (e.g. ARTIFACT_DIR_ROOT for `dir`),
# dying actionably when the name is unregistered, has no shipped adapter, or
# is misconfigured. `local` is always implicitly registered (zero-config).
#
# Source this file; do not execute. Requires terminal_compat.sh (die) to be
# sourced by the caller; sources python_resolve.sh itself (same pattern as
# artifact_manifest.sh).

[[ -n "${_AIT_ARTIFACT_REGISTRY_LOADED:-}" ]] && return 0
_AIT_ARTIFACT_REGISTRY_LOADED=1

_AIT_ARTIFACT_REGISTRY_DIR_SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/python_resolve.sh
source "$_AIT_ARTIFACT_REGISTRY_DIR_SELF/python_resolve.sh"

# cwd-relative, matching every other project_config.yaml consumer — `ait` cd's
# to the repo root before dispatching.
_AIT_ARTIFACT_REGISTRY_CONFIG="aitasks/metadata/project_config.yaml"

# BACKEND-EXTENSION-POINT (params): list EVERY adapter param env var here, so
# activation always clears the previous backend's params first (no
# cross-activation leakage — load-bearing for `move`, which activates the
# source and then the target backend in one process).
_AIT_ARTIFACT_REGISTRY_PARAM_VARS=( ARTIFACT_DIR_ROOT )

# artifact_registry_activate <name> -- validate <name> against the registry
# and export ARTIFACT_BACKEND + its adapter params. Dies on unregistered /
# adapterless / misconfigured backends (fail-closed, pre-mutation).
artifact_registry_activate() {
    local name="${1:-}"
    [[ -n "$name" ]] || die "artifact_registry_activate: backend name required"
    local v
    for v in "${_AIT_ARTIFACT_REGISTRY_PARAM_VARS[@]}"; do unset "$v"; done
    if [[ "$name" == "local" ]]; then
        export ARTIFACT_BACKEND="local"
        return 0
    fi
    # Explicit `|| die`: callers run inside with_attach_lock's
    # errexit-suppressed call tree, where a failed capture would NOT abort.
    local py out
    py="$(require_python)"
    out="$("$py" "$_AIT_ARTIFACT_REGISTRY_DIR_SELF/artifact_registry.py" \
            --config "$_AIT_ARTIFACT_REGISTRY_CONFIG" backend-env "$name")" \
        || die "artifact_registry: cannot activate backend '$name' (see error above)"
    local line k val
    while IFS= read -r line; do
        [[ -n "$line" ]] || continue
        k="${line%%=*}"; val="${line#*=}"
        # Config-driven strings must never choose arbitrary env var names.
        [[ "$k" =~ ^ARTIFACT_[A-Z0-9_]+$ ]] \
            || die "artifact_registry: unexpected param line '$line'"
        export "$k=$val"
    done <<< "$out"
    export ARTIFACT_BACKEND="$name"
}

# artifact_registry_default_backend -- print the backend `create` should use
# when --backend is absent (`local` unless artifacts.default_backend is set).
# Capture-safe printer: callers must `|| die` the capture themselves.
artifact_registry_default_backend() {
    local py
    py="$(require_python)"
    "$py" "$_AIT_ARTIFACT_REGISTRY_DIR_SELF/artifact_registry.py" \
        --config "$_AIT_ARTIFACT_REGISTRY_CONFIG" default-backend
}
