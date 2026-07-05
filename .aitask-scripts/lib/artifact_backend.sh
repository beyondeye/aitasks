#!/usr/bin/env bash
# artifact_backend.sh - Backend adapter seam for the shared artifact storage
# substrate (generalized from attachment_backend.sh in t1076_1; serves both
# attachments and artifacts).
#
# Defines the storage-backend CONTRACT and dispatches it to a per-backend module
# based on $ARTIFACT_BACKEND (default: local). This is the platform-extensible
# dispatcher pattern (mirrors aidocs/gitremoteproviderintegration.md): a new
# backend drops a file in artifact_backends/ and adds a `case` arm + source
# line at the BACKEND-EXTENSION-POINT markers below.
#
# The contract is about BLOBS ONLY — the metadata ledgers (attachment_meta.py's
# per-blob refcounts, artifact_manifest.py's per-artifact manifests) are
# separate, backend-independent concerns.
#
#   artifact_backend_put    <hash> <file>   upload (idempotent)
#   artifact_backend_get    <hash> <dest>   download to dest
#   artifact_backend_head   <hash>          exit 0 iff present
#   artifact_backend_delete <hash>          remove from backend
#   artifact_backend_list                   enumerate stored hashes
#
# Source this file; do not execute directly. Sourced by aitask_attach.sh.
# Design: aidocs/task_attachments_design.md §4 (storage layout), §5 (adapter);
# aidocs/unified_artifact_design.md §5 (storage sink).

[[ -n "${_AIT_ARTIFACT_BACKEND_LOADED:-}" ]] && return 0
_AIT_ARTIFACT_BACKEND_LOADED=1

_AIT_ARTIFACT_BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Per-backend implementations. Each module defines artifact_<backend>_<op>.
# shellcheck source=lib/artifact_backends/local.sh
source "$_AIT_ARTIFACT_BACKEND_DIR/artifact_backends/local.sh"
# BACKEND-EXTENSION-POINT (source): source new artifact_backends/<name>.sh here.

# _artifact_backend_call <op> [args...]
# Route <op> to the active backend's `artifact_<backend>_<op>` function.
_artifact_backend_call() {
    local op="$1"; shift
    local backend="${ARTIFACT_BACKEND:-local}"
    case "$backend" in
        local) "artifact_local_${op}" "$@" ;;
        # BACKEND-EXTENSION-POINT (dispatch): add `name) artifact_name_${op} "$@" ;;`
        *) die "artifact_backend: unknown backend '$backend' (known: local)" ;;
    esac
}

artifact_backend_put()    { _artifact_backend_call put "$@"; }
artifact_backend_get()    { _artifact_backend_call get "$@"; }
artifact_backend_head()   { _artifact_backend_call head "$@"; }
artifact_backend_delete() { _artifact_backend_call delete "$@"; }
artifact_backend_list()   { _artifact_backend_call list "$@"; }
