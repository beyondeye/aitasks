#!/usr/bin/env bash
# attachment_cache.sh - universal local-cache resolver for task attachments
# (t1030_2). design §5: every machine keeps a cache at ~/.cache/ait/attachments/
# <hash>; the canonical copy lives in the backend. Sourced by aitask_attach.sh;
# requires attachment_utils.sh + attachment_backend.sh sourced first.

[[ -n "${_AIT_ATTACHMENT_CACHE_LOADED:-}" ]] && return 0
_AIT_ATTACHMENT_CACHE_LOADED=1

# attachment_resolve <hash> -- ensure the blob is available in the universal local
# cache and print the cache path. Resolution order (design §5):
#   1. cache hit                      -> print path
#   2. backend head + get into cache  -> print path
#   3. miss in both                   -> loud error (never a silent placeholder)
# For the `local` backend the cache entry is a symlink to the worktree blob.
attachment_resolve() {
    local hash="$1" cache
    cache="$(attachment_cache_path "$hash")"
    if [[ -e "$cache" ]]; then
        printf '%s\n' "$cache"
        return 0
    fi
    mkdir -p "$(dirname "$cache")"

    if [[ "${ATTACHMENT_BACKEND:-local}" == "local" ]]; then
        local blob abs
        blob="$(attachment_local_blob_path "$hash")"
        if [[ -f "$blob" ]]; then
            # Symlink to an ABSOLUTE path so the link resolves from the cache dir.
            abs="$(cd "$(dirname "$blob")" && pwd -P)/$(basename "$blob")"
            ln -sf "$abs" "$cache"
            printf '%s\n' "$cache"
            return 0
        fi
        die "attachment_resolve: blob not found for $hash (local backend; not in cache or store)"
    fi

    if attachment_backend_head "$hash"; then
        attachment_backend_get "$hash" "$cache"
        printf '%s\n' "$cache"
        return 0
    fi
    die "attachment_resolve: blob not found for $hash (cache miss and backend miss)"
}
