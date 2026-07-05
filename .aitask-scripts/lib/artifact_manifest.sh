#!/usr/bin/env bash
# artifact_manifest.sh - shared bash front for the per-artifact manifest store
# (t1076_1). Wraps lib/artifact_manifest.py (the lock-free manifest primitive)
# with the small helpers shell consumers need: manifest-dir resolution and the
# data-root-relative manifest relpath (for `task_git add` staging).
#
# Manifests are COMMITTED per-artifact JSON files at
# <data-worktree>/artifacts/manifests/<id>.json (settled t1076_1 decision,
# aidocs/unified_artifact_design.md par.4b) -- they travel with the aitask-data
# branch; updating one never touches a task file.
#
# MUTATING subcommands (create/set-current/set-backend) are lock-free here ---
# the CALLER must already hold the global attachments/.attach.lock
# (attachment_lock.sh with_attach_lock): manifests share the blob store with
# attachments and gc unions manifest references into its blocking set, so one
# lock serializes both ledgers against the sweep. Read-only subcommands
# (get/current/versions/list/referenced-hashes) are safe lock-free
# (artifact_manifest.py writes are atomic temp+os.replace).
#
# Source this file; do not execute. Requires task_utils.sh (for
# _ait_detect_data_worktree) to be sourced by the caller; sources
# python_resolve.sh itself.

[[ -n "${_AIT_ARTIFACT_MANIFEST_SH_LOADED:-}" ]] && return 0
_AIT_ARTIFACT_MANIFEST_SH_LOADED=1

_AIT_ARTIFACT_MANIFEST_DIR_SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/python_resolve.sh
source "$_AIT_ARTIFACT_MANIFEST_DIR_SELF/python_resolve.sh"

# artifact_manifest_dir -> per-artifact manifest dir in the data worktree.
artifact_manifest_dir() {
    _ait_detect_data_worktree
    printf '%s/artifacts/manifests' "$_AIT_DATA_WORKTREE"
}

# artifact_manifest <subcommand> [args...] -- run the lock-free manifest helper.
# Callers MUST already hold the global attach lock for mutating subcommands.
artifact_manifest() {
    local py; py="$(require_python)"
    "$py" "$_AIT_ARTIFACT_MANIFEST_DIR_SELF/artifact_manifest.py" \
        --manifest-dir "$(artifact_manifest_dir)" "$@"
}

# artifact_manifest_relpath <handle> -> data-root-relative manifest file path
# (artifacts/manifests/<id>.json), for `task_git add` staging. Validates the
# handle shape (mirrors artifact_manifest.py HANDLE_RE) so a bad value can
# never silently produce a wrong path.
artifact_manifest_relpath() {
    local handle="${1:-}"
    [[ "$handle" =~ ^art:[a-z0-9][a-z0-9._-]{0,127}$ ]] || \
        die "artifact_manifest_relpath: invalid handle: '$handle'"
    printf 'artifacts/manifests/%s.json' "${handle#art:}"
}
