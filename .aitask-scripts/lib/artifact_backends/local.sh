#!/usr/bin/env bash
# artifact_backends/local.sh - local filesystem backend for the shared artifact
# storage substrate (generalized from attachment_backends/local.sh in t1076_1;
# serves both attachments and artifacts). Blobs are content-addressed and live
# in the .aitask-data worktree at attachments/blobs/<2>/<62> (design §4) — the
# on-disk path keeps its historical name; no data migration (t1076_1 decision).
# Sourced by artifact_backend.sh; never executed directly. Requires
# artifact_utils.sh (artifact_shard_path) and task_utils.sh
# (_ait_detect_data_worktree) to be sourced first.

[[ -n "${_AIT_ARTIFACT_BACKEND_LOCAL_LOADED:-}" ]] && return 0
_AIT_ARTIFACT_BACKEND_LOCAL_LOADED=1

# _artifact_local_root -> echo the shared blob-store dir inside the data
# worktree (historical name: attachments/).
_artifact_local_root() {
    _ait_detect_data_worktree
    printf '%s/attachments' "$_AIT_DATA_WORKTREE"
}

# artifact_local_blob_relpath <hash> -> data-worktree-root-relative blob path
# (attachments/blobs/<2>/<62>), for `task_git add` staging.
artifact_local_blob_relpath() {
    printf 'attachments/blobs/%s' "$(artifact_shard_path "$1")"
}

# artifact_local_blob_path <hash> -> the blob's on-disk (working) path.
artifact_local_blob_path() {
    printf '%s/blobs/%s' "$(_artifact_local_root)" "$(artifact_shard_path "$1")"
}

# artifact_local_head <hash> -- exit 0 iff the blob is present.
artifact_local_head() {
    [[ -f "$(artifact_local_blob_path "$1")" ]]
}

# artifact_local_put <hash> <file> -- idempotent atomic copy into the shard.
# Writes to a temp file in the shard dir then renames, so a half-written blob
# never appears under its final content-addressed name.
artifact_local_put() {
    local hash="$1" src="$2" dest tmp
    [[ -f "$src" ]] || die "artifact_local_put: not a file: $src"
    dest="$(artifact_local_blob_path "$hash")"
    [[ -f "$dest" ]] && return 0          # idempotent: already stored
    mkdir -p "$(dirname "$dest")"
    tmp="$(mktemp "$(dirname "$dest")/.put.XXXXXX")"
    cp "$src" "$tmp"
    mv -f "$tmp" "$dest"
}

# artifact_local_get <hash> <dest> -- copy the blob to <dest> ("-" = stdout).
artifact_local_get() {
    local hash="$1" dest="$2" src
    src="$(artifact_local_blob_path "$hash")"
    [[ -f "$src" ]] || die "artifact_local_get: blob not present: $hash"
    if [[ "$dest" == "-" ]]; then cat "$src"; else cp "$src" "$dest"; fi
}

# artifact_local_delete <hash> -- remove the blob (no-op if absent).
artifact_local_delete() {
    rm -f "$(artifact_local_blob_path "$1")"
}

# artifact_local_list -- print every stored hash (sha256:<hex>), one per line.
artifact_local_list() {
    local root; root="$(_artifact_local_root)/blobs"
    [[ -d "$root" ]] || return 0
    local shard prefix f
    for shard in "$root"/*/; do
        [[ -d "$shard" ]] || continue
        prefix="$(basename "$shard")"
        for f in "$shard"*; do
            [[ -f "$f" ]] || continue
            printf 'sha256:%s%s\n' "$prefix" "$(basename "$f")"
        done
    done
}
