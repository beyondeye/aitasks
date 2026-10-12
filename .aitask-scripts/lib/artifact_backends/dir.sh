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
# The configured root must ALREADY EXIST and carry the store MARKER
# (.ait-artifact-store), written once by `ait artifact init-store dir` while
# the share is mounted. Every op refuses a root without it (t1283). Neither
# the root nor the marker is ever created implicitly: `mkdir -p`-ing a missing
# mountpoint, or treating an existing EMPTY directory as the store, would
# write blobs into the local filesystem underneath an unmounted share (or into
# whatever unrelated directory the config happens to name), where every other
# checkout then fails with "blob not found". The marker is what tells "the
# share is mounted here" apart from "a directory exists here". Only shard
# subdirs are created.
#
# VALIDATION BOUNDARY: the root is validated once, at op entry. `put` then
# works on absolute paths, so a share unmounted BETWEEN that validation and
# the shard mkdir / temp file / final mv is not protected against — that needs
# the operations tied to the validated directory itself (follow-up of t1283).
#
# Sourced by artifact_backend.sh; never executed directly. Requires
# artifact_utils.sh (artifact_shard_path, artifact_sha256) sourced first.

[[ -n "${_AIT_ARTIFACT_BACKEND_DIRFS_LOADED:-}" ]] && return 0
_AIT_ARTIFACT_BACKEND_DIRFS_LOADED=1

# shellcheck source=lib/atomic_write.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/atomic_write.sh"

_ARTIFACT_DIR_MARKER=".ait-artifact-store"
_ARTIFACT_DIR_ROOT_ERROR=""

# _artifact_dir_check_root -- exit 0 iff ARTIFACT_DIR_ROOT is a usable store:
# set, an existing directory, and carrying the marker. Otherwise set
# _ARTIFACT_DIR_ROOT_ERROR and return 1. Never call it inside $( ): the error
# global would be lost with the subshell.
_artifact_dir_check_root() {
    if [[ -z "${ARTIFACT_DIR_ROOT:-}" ]]; then
        _ARTIFACT_DIR_ROOT_ERROR="artifact_dir: ARTIFACT_DIR_ROOT not set — activate via artifact_registry_activate dir"
    elif [[ ! -d "$ARTIFACT_DIR_ROOT" ]]; then
        _ARTIFACT_DIR_ROOT_ERROR="artifact_dir: backend root not found: $ARTIFACT_DIR_ROOT (is the share mounted?)"
    elif [[ ! -f "$ARTIFACT_DIR_ROOT/$_ARTIFACT_DIR_MARKER" ]]; then
        _ARTIFACT_DIR_ROOT_ERROR="artifact_dir: $ARTIFACT_DIR_ROOT is not an initialized artifact store (no $_ARTIFACT_DIR_MARKER marker) — is the share mounted there? If this directory IS the share, run: ait artifact init-store dir"
    else
        return 0
    fi
    return 1
}

# _artifact_dir_require_root -- die unless the store root is usable. Call it in
# the op's OWN shell, never inside $( ): a die in a command substitution only
# exits the subshell, and under with_attach_lock's errexit-suppressed call
# tree the caller then carries on with an empty root — which is how a blob
# path once degenerated to /<2hex>/<62hex> at the filesystem root (t1283).
_artifact_dir_require_root() {
    _artifact_dir_check_root || die "$_ARTIFACT_DIR_ROOT_ERROR"
}

# _artifact_dir_blob_path <hash> -> the blob's path inside the store. Fails
# (prints nothing) on an empty root rather than ever deriving /<2>/<62>.
_artifact_dir_blob_path() {
    [[ -n "${ARTIFACT_DIR_ROOT:-}" ]] || return 1
    printf '%s/%s' "$ARTIFACT_DIR_ROOT" "$(artifact_shard_path "$1")"
}

# artifact_dir_init -- mark the configured root as the store (idempotent).
# Run by a human with the share mounted (`ait artifact init-store dir`). The
# root must already exist — it is never created, which is why the temp comes
# from a bare mktemp rather than ait_atomic_tmp (that one mkdir -p's the
# parent). The marker is installed atomically via ait_atomic_commit, whose
# directory check matters here: `mv -f tmp <dir>` SUCCEEDS by moving the temp
# inside the directory, so a directory squatting on the marker name would
# otherwise yield INITIALIZED for a store every op still refuses. Prints
# INITIALIZED:<root> or ALREADY_INITIALIZED:<root>.
artifact_dir_init() {
    [[ -n "${ARTIFACT_DIR_ROOT:-}" ]] \
        || die "artifact_dir: ARTIFACT_DIR_ROOT not set — activate via artifact_registry_activate dir"
    [[ -d "$ARTIFACT_DIR_ROOT" ]] \
        || die "artifact_dir: backend root not found: $ARTIFACT_DIR_ROOT (is the share mounted?) — the root is never created; mount the share (or create the directory on it) first"
    local marker="$ARTIFACT_DIR_ROOT/$_ARTIFACT_DIR_MARKER"
    if [[ -f "$marker" ]]; then
        printf 'ALREADY_INITIALIZED:%s\n' "$ARTIFACT_DIR_ROOT"
        return 0
    fi
    # Refuse before staging anything, and leave whatever is there untouched.
    [[ -e "$marker" || -L "$marker" ]] \
        && die "artifact_dir_init: $marker exists but is not a regular file — it was left untouched; remove it by hand if it is not needed, then re-run"
    local tmp
    tmp="$(mktemp "$ARTIFACT_DIR_ROOT/.marker.XXXXXX")" \
        || die "artifact_dir_init: cannot write into $ARTIFACT_DIR_ROOT"
    if ! printf 'aitasks artifact store v1\n' > "$tmp"; then
        ait_atomic_discard "$tmp"
        die "artifact_dir_init: could not write the store marker in $ARTIFACT_DIR_ROOT"
    fi
    ait_atomic_commit "$tmp" "$marker" \
        || die "artifact_dir_init: could not install the store marker at $marker"
    printf 'INITIALIZED:%s\n' "$ARTIFACT_DIR_ROOT"
}

# artifact_dir_head <hash> -- exit 0 iff the blob is present. Dies (rather
# than answering "absent") when the store itself is unusable.
artifact_dir_head() {
    _artifact_dir_require_root
    local path
    path="$(_artifact_dir_blob_path "$1")" || die "artifact_dir_head: could not derive the blob path for $1"
    [[ -f "$path" ]]
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
    _artifact_dir_require_root
    [[ -f "$src" ]] || die "artifact_dir_put: not a file: $src"
    dest="$(_artifact_dir_blob_path "$hash")" || die "artifact_dir_put: could not derive the blob path for $hash"
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
    _artifact_dir_require_root
    src="$(_artifact_dir_blob_path "$hash")" || die "artifact_dir_get: could not derive the blob path for $hash"
    [[ -f "$src" ]] || die "artifact_dir_get: blob not present: $hash"
    if [[ "$dest" == "-" ]]; then cat "$src"; else cp "$src" "$dest"; fi
}

# artifact_dir_delete <hash> -- remove the blob (no-op if absent). RETURNS
# non-zero (with the cause on stderr) when the store is unusable — it NEVER
# dies. Delete is the op the rollback hooks (_artifact_rollback_create_blobs,
# _artifact_rollback_move_blobs, _attach_rollback_add_blobs) call from the
# chained EXIT trap; an exit there would cut the trap short, skipping the
# rollback report, the snapshot cleanup and the chained registry_lock_release
# — leaking the global attach lock. Every caller handles a returned failure
# (`|| txn_rollback_failed` in the hooks, `|| die` elsewhere).
artifact_dir_delete() {
    local path
    if ! _artifact_dir_check_root; then
        warn "artifact_dir_delete: $_ARTIFACT_DIR_ROOT_ERROR"
        return 1
    fi
    path="$(_artifact_dir_blob_path "$1")" || return 1
    rm -f "$path" || return 1
}

# artifact_dir_list -- print every stored hash (sha256:<hex>), one per line.
artifact_dir_list() {
    _artifact_dir_require_root
    local root="$ARTIFACT_DIR_ROOT"
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
