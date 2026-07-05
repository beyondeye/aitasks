#!/usr/bin/env bash
# artifact_utils.sh - Pure, headless helpers for the shared artifact storage
# substrate (generalized from attachment_* in t1076_1; serves both attachments
# and artifacts). Content-addressed primitives: SHA-256 hashing, hash
# validation, and the on-disk shard / local-cache path derivation.
#
# These are the canonical hash-handling units. Reuse them everywhere — do NOT
# re-derive shard logic inline. The signatures established here are the stable
# interface consumed by the storage backend and archive/gc.
#
# Pure: no task/repo state, no git, no network. Source this file; do not execute
# directly. Sourced by aitask_attach.sh — NOT part of ./ait's source-on-startup
# chain, so it does not belong in tests/lib/test_scaffold.sh.
#
# Design: aidocs/task_attachments_design.md §2 (content-addressing), §4 (storage
# layout / sharding), §5 (universal local cache);
# aidocs/unified_artifact_design.md §5 (storage sink).

# --- Guard against double-sourcing ---
[[ -n "${_AIT_ARTIFACT_UTILS_LOADED:-}" ]] && return 0
_AIT_ARTIFACT_UTILS_LOADED=1

# artifact_sha256 <file>
# Print the content hash of <file> as `sha256:<64-lowercase-hex>`.
# Encapsulates the platform hashing-CLI choice in ONE place: prefer openssl,
# fall back to sha256sum (GNU/Linux), then shasum -a 256 (macOS/Perl). die if
# none is available or the file cannot be read.
artifact_sha256() {
    local file="$1"
    [[ -f "$file" ]] || die "artifact_sha256: not a file: $file"

    local hex=""
    if command -v openssl >/dev/null 2>&1; then
        # openssl prints "<ALGO>(<file>)= <hex>" (the exact ALGO label varies
        # across versions: SHA256 vs SHA2-256); the hex is always the last field.
        hex="$(openssl dgst -sha256 "$file" | awk '{print $NF}')"
    elif command -v sha256sum >/dev/null 2>&1; then
        hex="$(sha256sum "$file" | awk '{print $1}')"
    elif command -v shasum >/dev/null 2>&1; then
        hex="$(shasum -a 256 "$file" | awk '{print $1}')"
    else
        die "artifact_sha256: no SHA-256 tool found (need openssl, sha256sum, or shasum)"
    fi

    # Normalize to lowercase (these tools already emit lowercase, but be safe).
    hex="$(printf '%s' "$hex" | tr '[:upper:]' '[:lower:]')"
    [[ "$hex" =~ ^[0-9a-f]{64}$ ]] || die "artifact_sha256: unexpected hash output for $file: '$hex'"
    printf 'sha256:%s\n' "$hex"
}

# artifact_validate_hash <hash>
# Predicate: exit 0 iff <hash> matches `sha256:<64-lowercase-hex>`, non-zero
# otherwise. Emits nothing (it is a test, not a printer). The `sha256:` prefix
# names the digest algorithm and future-proofs algorithm migration (design §3).
artifact_validate_hash() {
    local hash="${1:-}"
    printf '%s' "$hash" | grep -qE '^sha256:[0-9a-f]{64}$'
}

# artifact_shard_path <hash>
# Print the 2-char-prefix-sharded relative blob path `<first2hex>/<remaining62hex>`
# (design §4). Strips the `sha256:` prefix first; die on a malformed hash so a
# bad value can never silently produce a wrong path.
artifact_shard_path() {
    local hash="${1:-}"
    artifact_validate_hash "$hash" || die "artifact_shard_path: invalid hash: '$hash'"
    local hex="${hash#sha256:}"
    printf '%s/%s\n' "${hex:0:2}" "${hex:2}"
}

# artifact_cache_path <hash>
# Print the absolute universal-local-cache path for <hash> (design §5). The cache
# key is the full `sha256:`-prefixed hash. Honors XDG_CACHE_HOME, defaulting to
# ~/.cache. die on a malformed hash BEFORE deriving the path (same rule as
# artifact_shard_path) — a validated hash has no '/', so the derived path can
# never traverse outside the cache dir. (Does not create or check the file.)
# t1076_1 moved the cache from ~/.cache/ait/attachments/ to ~/.cache/ait/artifacts/;
# entries under the old dir simply go stale (the cache is a pure perf layer —
# blobs are re-fetched/re-symlinked on first resolve).
artifact_cache_path() {
    local hash="${1:-}"
    artifact_validate_hash "$hash" || die "artifact_cache_path: invalid hash: '$hash'"
    printf '%s/ait/artifacts/%s\n' "${XDG_CACHE_HOME:-$HOME/.cache}" "$hash"
}
