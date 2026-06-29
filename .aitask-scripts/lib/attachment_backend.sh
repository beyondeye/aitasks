#!/usr/bin/env bash
# attachment_backend.sh - Backend adapter seam for task attachments (t1030_2).
#
# Defines the storage-backend CONTRACT and dispatches it to a per-backend module
# based on $ATTACHMENT_BACKEND (default: local). This is the platform-extensible
# dispatcher pattern (mirrors aidocs/gitremoteproviderintegration.md): a new
# backend drops a file in attachment_backends/ and adds a `case` arm + source
# line at the BACKEND-EXTENSION-POINT markers below.
#
# The contract is about BLOBS ONLY — the metadata/refcount ledger
# (attachment_meta.py) is a separate, backend-independent concern. Names/shape
# follow design §5 so t1076_1 can widen `attachment_backend_*` → `artifact_backend_*`
# by rename, not re-plumb.
#
#   attachment_backend_put    <hash> <file>   upload (idempotent)
#   attachment_backend_get    <hash> <dest>   download to dest
#   attachment_backend_head   <hash>          exit 0 iff present
#   attachment_backend_delete <hash>          remove from backend
#   attachment_backend_list                   enumerate stored hashes
#
# Source this file; do not execute directly. Sourced by aitask_attach.sh.
# Design: aidocs/task_attachments_design.md §4 (storage layout), §5 (adapter).

[[ -n "${_AIT_ATTACHMENT_BACKEND_LOADED:-}" ]] && return 0
_AIT_ATTACHMENT_BACKEND_LOADED=1

_AIT_ATTACHMENT_BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Per-backend implementations. Each module defines attachment_<backend>_<op>.
# shellcheck source=lib/attachment_backends/local.sh
source "$_AIT_ATTACHMENT_BACKEND_DIR/attachment_backends/local.sh"
# BACKEND-EXTENSION-POINT (source): source new attachment_backends/<name>.sh here.

# _attachment_backend_call <op> [args...]
# Route <op> to the active backend's `attachment_<backend>_<op>` function.
_attachment_backend_call() {
    local op="$1"; shift
    local backend="${ATTACHMENT_BACKEND:-local}"
    case "$backend" in
        local) "attachment_local_${op}" "$@" ;;
        # BACKEND-EXTENSION-POINT (dispatch): add `name) attachment_name_${op} "$@" ;;`
        *) die "attachment_backend: unknown backend '$backend' (known: local)" ;;
    esac
}

attachment_backend_put()    { _attachment_backend_call put "$@"; }
attachment_backend_get()    { _attachment_backend_call get "$@"; }
attachment_backend_head()   { _attachment_backend_call head "$@"; }
attachment_backend_delete() { _attachment_backend_call delete "$@"; }
attachment_backend_list()   { _attachment_backend_call list "$@"; }
