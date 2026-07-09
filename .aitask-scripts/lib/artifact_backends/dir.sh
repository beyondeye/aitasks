#!/usr/bin/env bash
# artifact_backends/dir.sh - filesystem-directory backend for the shared
# artifact storage substrate (t1076_3): a configured directory root — NAS
# mount, network share, USB drive — shared by every checkout that mounts it.
# First config-registered backend and the reference implementation for the
# remote adapters (s3: t1089, gdrive: t1090).
#
# Blobs are content-addressed at <root>/<2hex>/<62hex> (same sharding as the
# local backend; the root IS the store — no blobs/ intermediate). The root
# comes from ARTIFACT_DIR_ROOT, exported by artifact_registry_activate from
# artifacts.backends.dir.path in aitasks/metadata/project_config.yaml. The
# git-tracked path is one absolute path for the whole team: every
# participating machine must mount the share there.
#
# The configured root must ALREADY EXIST — it is never created here. Silently
# `mkdir -p`-ing a missing NAS mountpoint would write blobs into the empty
# mountpoint dir (the unmounted-share data-loss trap); only shard subdirs are
# created. Sourced by artifact_backend.sh; never executed directly. Requires
# artifact_utils.sh (artifact_shard_path, artifact_sha256) sourced first.

[[ -n "${_AIT_ARTIFACT_BACKEND_DIRFS_LOADED:-}" ]] && return 0
_AIT_ARTIFACT_BACKEND_DIRFS_LOADED=1

# _artifact_dir_root -> echo the configured store root; die when unset or not
# mounted (fail-closed — never invent the root).
_artifact_dir_root() {
    [[ -n "${ARTIFACT_DIR_ROOT:-}" ]] \
        || die "artifact_dir: ARTIFACT_DIR_ROOT not set — activate via artifact_registry_activate dir"
    [[ -d "$ARTIFACT_DIR_ROOT" ]] \
        || die "artifact_dir: backend root not found: $ARTIFACT_DIR_ROOT (is the share mounted?)"
    printf '%s' "$ARTIFACT_DIR_ROOT"
}

# _artifact_dir_blob_path <hash> -> the blob's path inside the store.
_artifact_dir_blob_path() {
    printf '%s/%s' "$(_artifact_dir_root)" "$(artifact_shard_path "$1")"
}

# artifact_dir_head <hash> -- exit 0 iff the blob is present.
artifact_dir_head() {
    [[ -f "$(_artifact_dir_blob_path "$1")" ]]
}

# artifact_dir_put <hash> <file> -- idempotent atomic copy into the shard,
# CONTENT-VERIFYING a pre-existing dest (deliberate deviation from local.sh's
# bare existence check): a content-addressed entry whose bytes don't hash to
# its own address is by definition corruption (atomic mv means no half-writes
# sit at a final name), and the source bytes we hold DO hash to the address,
# so overwriting is a strict repair — mirroring the cache's self-heal. The
# local backend instead dies on canonical corruption because its blobs are
# git-tracked (repair = data-branch surgery); the dir store has no history.
artifact_dir_put() {
    local hash="$1" src="$2" dest tmp
    [[ -f "$src" ]] || die "artifact_dir_put: not a file: $src"
    dest="$(_artifact_dir_blob_path "$hash")"
    if [[ -f "$dest" ]]; then
        [[ "$(artifact_sha256 "$dest")" == "$hash" ]] && return 0  # idempotent
        warn "artifact_dir_put: corrupt store entry for $hash at $dest — repairing with verified bytes"
    fi
    mkdir -p "$(dirname "$dest")"
    tmp="$(mktemp "$(dirname "$dest")/.put.XXXXXX")" \
        || die "artifact_dir_put: mktemp failed in $(dirname "$dest")"
    # Atomic in the strong sense: this runs in errexit-suppressed transaction
    # trees, where an unchecked failed/partial cp would still let mv install
    # truncated bytes at the content-addressed name and return success. Abort
    # on cp failure and hash-verify the STAGED bytes before they ever reach
    # the canonical path (catches disk-full / dropped-mount partial copies).
    if ! cp "$src" "$tmp"; then
        rm -f "$tmp"
        die "artifact_dir_put: copy failed for $hash (partial copy removed)"
    fi
    if [[ "$(artifact_sha256 "$tmp")" != "$hash" ]]; then
        rm -f "$tmp"
        die "artifact_dir_put: staged bytes for $hash failed verification — nothing installed"
    fi
    mv -f "$tmp" "$dest" \
        || { rm -f "$tmp"; die "artifact_dir_put: could not install $hash into the store"; }
}

# artifact_dir_get <hash> <dest> -- copy the blob to <dest> ("-" = stdout).
artifact_dir_get() {
    local hash="$1" dest="$2" src
    src="$(_artifact_dir_blob_path "$hash")"
    [[ -f "$src" ]] || die "artifact_dir_get: blob not present: $hash"
    if [[ "$dest" == "-" ]]; then cat "$src"; else cp "$src" "$dest"; fi
}

# artifact_dir_delete <hash> -- remove the blob (no-op if absent).
artifact_dir_delete() {
    rm -f "$(_artifact_dir_blob_path "$1")"
}

# artifact_dir_list -- print every stored hash (sha256:<hex>), one per line.
artifact_dir_list() {
    local root; root="$(_artifact_dir_root)"
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
