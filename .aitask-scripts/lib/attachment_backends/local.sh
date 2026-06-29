#!/usr/bin/env bash
# attachment_backends/local.sh - local filesystem backend for task attachments
# (t1030_2). Blobs are content-addressed and live in the .aitask-data worktree at
# attachments/blobs/<2>/<62> (design §4). Sourced by attachment_backend.sh; never
# executed directly. Requires attachment_utils.sh (attachment_shard_path) and
# task_utils.sh (_ait_detect_data_worktree) to be sourced first.

[[ -n "${_AIT_ATTACHMENT_BACKEND_LOCAL_LOADED:-}" ]] && return 0
_AIT_ATTACHMENT_BACKEND_LOCAL_LOADED=1

# _attachment_local_root -> echo the attachments dir inside the data worktree.
_attachment_local_root() {
    _ait_detect_data_worktree
    printf '%s/attachments' "$_AIT_DATA_WORKTREE"
}

# attachment_local_blob_relpath <hash> -> data-worktree-root-relative blob path
# (attachments/blobs/<2>/<62>), for `task_git add` staging.
attachment_local_blob_relpath() {
    printf 'attachments/blobs/%s' "$(attachment_shard_path "$1")"
}

# attachment_local_blob_path <hash> -> the blob's on-disk (working) path.
attachment_local_blob_path() {
    printf '%s/blobs/%s' "$(_attachment_local_root)" "$(attachment_shard_path "$1")"
}

# attachment_local_head <hash> -- exit 0 iff the blob is present.
attachment_local_head() {
    [[ -f "$(attachment_local_blob_path "$1")" ]]
}

# attachment_local_put <hash> <file> -- idempotent atomic copy into the shard.
# Writes to a temp file in the shard dir then renames, so a half-written blob
# never appears under its final content-addressed name.
attachment_local_put() {
    local hash="$1" src="$2" dest tmp
    [[ -f "$src" ]] || die "attachment_local_put: not a file: $src"
    dest="$(attachment_local_blob_path "$hash")"
    [[ -f "$dest" ]] && return 0          # idempotent: already stored
    mkdir -p "$(dirname "$dest")"
    tmp="$(mktemp "$(dirname "$dest")/.put.XXXXXX")"
    cp "$src" "$tmp"
    mv -f "$tmp" "$dest"
}

# attachment_local_get <hash> <dest> -- copy the blob to <dest> ("-" = stdout).
attachment_local_get() {
    local hash="$1" dest="$2" src
    src="$(attachment_local_blob_path "$hash")"
    [[ -f "$src" ]] || die "attachment_local_get: blob not present: $hash"
    if [[ "$dest" == "-" ]]; then cat "$src"; else cp "$src" "$dest"; fi
}

# attachment_local_delete <hash> -- remove the blob (no-op if absent).
attachment_local_delete() {
    rm -f "$(attachment_local_blob_path "$1")"
}

# attachment_local_list -- print every stored hash (sha256:<hex>), one per line.
attachment_local_list() {
    local root; root="$(_attachment_local_root)/blobs"
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
