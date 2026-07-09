#!/usr/bin/env bash
# artifact_cache.sh - universal local-cache resolver for the shared artifact
# storage substrate (generalized from attachment_cache.sh in t1076_1; serves
# both attachments and artifacts). design §5: every machine keeps a cache at
# ~/.cache/ait/artifacts/<hash>; the canonical copy lives in the backend.
# Sourced by aitask_attach.sh; requires artifact_utils.sh + artifact_backend.sh
# sourced first.

[[ -n "${_AIT_ARTIFACT_CACHE_LOADED:-}" ]] && return 0
_AIT_ARTIFACT_CACHE_LOADED=1

# artifact_resolve <hash> -- ensure the blob is available in the universal local
# cache, VERIFY its content, and print the cache path. Resolution order
# (design §5):
#   1. cache hit + content verifies      -> print path
#   2. backend head + get into cache     -> verify -> print path
#   3. miss in both                      -> loud error (never a silent placeholder)
# For the `local` backend the cache entry is a symlink to the worktree blob.
#
# In-resolver content verification (t1076_1): this resolver is shared substrate
# and consumers call it directly, so integrity does NOT depend on callers
# re-hashing. Every successful resolution hash-verifies the resolved bytes:
#   - a corrupted CACHED COPY (regular file — the remote-backend fill case)
#     self-heals: the bad entry is removed and re-fetched from the backend once;
#     a second mismatch dies.
#   - a corrupted CANONICAL blob (the local-backend store, reached via symlink)
#     dies loudly naming the blob — canonical corruption is never auto-repaired.
artifact_resolve() {
    local hash="$1" cache
    # Validate FIRST: a malformed "hash" must never reach path derivation —
    # unvalidated it would traverse into arbitrary cache paths (mkdir side
    # effects; worse, the self-heal rm -f could delete a traversal target).
    artifact_validate_hash "$hash" || die "artifact_resolve: invalid hash: '$hash'"
    cache="$(artifact_cache_path "$hash")"
    if [[ -e "$cache" ]]; then
        if [[ "$(artifact_sha256 "$cache")" == "$hash" ]]; then
            printf '%s\n' "$cache"
            return 0
        fi
        if [[ -L "$cache" ]]; then
            # Symlinked cache entry: the mismatching bytes ARE the canonical
            # local-backend blob. Fail loud; never auto-repair the canon.
            die "artifact_resolve: content mismatch for $hash at canonical blob $(readlink "$cache") — canonical corruption is never auto-repaired"
        fi
        # Stale/corrupted cached copy: self-heal (drop + single re-fetch below).
        warn "artifact_resolve: corrupted cache entry for $hash — re-fetching from backend"
        rm -f "$cache"
    fi
    mkdir -p "$(dirname "$cache")"

    if [[ "${ARTIFACT_BACKEND:-local}" == "local" ]]; then
        local blob abs
        blob="$(artifact_local_blob_path "$hash")"
        if [[ -f "$blob" ]]; then
            [[ "$(artifact_sha256 "$blob")" == "$hash" ]] || \
                die "artifact_resolve: content mismatch for $hash at canonical blob $blob — canonical corruption is never auto-repaired"
            # Symlink to an ABSOLUTE path so the link resolves from the cache dir.
            abs="$(cd "$(dirname "$blob")" && pwd -P)/$(basename "$blob")"
            ln -sf "$abs" "$cache"
            printf '%s\n' "$cache"
            return 0
        fi
        die "artifact_resolve: blob not found for $hash (local backend; not in cache or store)"
    fi

    if artifact_backend_head "$hash"; then
        artifact_backend_get "$hash" "$cache"
        if [[ "$(artifact_sha256 "$cache")" != "$hash" ]]; then
            rm -f "$cache"
            die "artifact_resolve: backend returned wrong bytes for $hash (bad cache entry removed)"
        fi
        printf '%s\n' "$cache"
        return 0
    fi
    die "artifact_resolve: blob not found for $hash (cache miss and backend miss)"
}

# artifact_store <hash> <file> -- write-back (design §5, t1076_3): verify
# <file> hashes to <hash>, put it to the ACTIVE backend, VERIFY the backend
# reports it, then warm the universal cache from the verified LOCAL bytes —
# no backend get round-trip. The post-put head catches a LOST put (presence
# only — backend content correctness is owned one level down: dir-put
# content-verifies a pre-existing dest; the local branch's artifact_resolve
# call hash-verifies the canonical blob). Every step carries an explicit
# `|| die`: this helper runs inside with_attach_lock transactions where
# errexit is suppressed.
artifact_store() {
    local hash="$1" file="$2" cache
    artifact_validate_hash "$hash" || die "artifact_store: invalid hash: '$hash'"
    [[ -f "$file" ]] || die "artifact_store: not a file: $file"
    [[ "$(artifact_sha256 "$file")" == "$hash" ]] \
        || die "artifact_store: $file does not hash to $hash"
    artifact_backend_put "$hash" "$file" || die "artifact_store: backend put failed for $hash"
    artifact_backend_head "$hash" \
        || die "artifact_store: backend does not report $hash after put — write-back failed"
    if [[ "${ARTIFACT_BACKEND:-local}" == "local" ]]; then
        artifact_resolve "$hash" >/dev/null    # symlink fast path + canonical verify
        return 0
    fi
    cache="$(artifact_cache_path "$hash")"
    mkdir -p "$(dirname "$cache")" || die "artifact_store: cannot create cache dir"
    local tmp
    tmp="$(mktemp "$(dirname "$cache")/.store.XXXXXX")" || die "artifact_store: mktemp failed"
    if ! cp "$file" "$tmp" || ! mv -f "$tmp" "$cache"; then
        rm -f "$tmp"
        die "artifact_store: could not warm cache for $hash"
    fi
    [[ "$(artifact_sha256 "$cache")" == "$hash" ]] \
        || { rm -f "$cache"; die "artifact_store: cache warm verification failed for $hash"; }
}
