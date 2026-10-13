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
# HELD ROOT (t1960): every op except init runs in a subshell that enters the
# root ONCE, validates the marker THROUGH that cwd, and then uses only paths
# relative to it — nothing is re-resolved by pathname after validation, so
# the validation and every write refer to the same directory object:
#   - share gone BEFORE the cd → the cd lands on the empty mountpoint, the
#     marker check fails, the op refuses;
#   - share moved AFTER the cd → the cwd still is the store, writes land
#     there (a real umount gets EBUSY while we hold the cwd; `umount -l`
#     detaches, but writes still reach the share's filesystem);
#   - store directory dead AFTER the cd (forced unmount, ESTALE, removed) →
#     writes fail; nothing ever reaches the mountpoint underneath.
# A dead directory answers every lookup with ENOENT, exactly like a real
# absence, so NEGATIVE answers (head "absent", delete "removed", a listing)
# are qualified through the held cwd too (_artifact_dir_lookup,
# _artifact_dir_still_held). No pathname re-checks of the root, by design:
# they race the same way.
#
# init is not held: it has no marker to validate through the cwd, so holding
# the directory would not change which directory gets marked. It is a
# human-attended one-shot run with the share mounted.
#
# Sourced by artifact_backend.sh; never executed directly. Requires
# artifact_utils.sh (artifact_shard_path, artifact_sha256,
# artifact_validate_hash) sourced first.

[[ -n "${_AIT_ARTIFACT_BACKEND_DIRFS_LOADED:-}" ]] && return 0
_AIT_ARTIFACT_BACKEND_DIRFS_LOADED=1

# shellcheck source=lib/atomic_write.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/atomic_write.sh"

_ARTIFACT_DIR_MARKER=".ait-artifact-store"
_ARTIFACT_DIR_UNUSABLE=3

# _artifact_dir_held <cmd> [args...] -- run <cmd> in a SUBSHELL whose cwd IS
# the store root, after validating the marker THROUGH that cwd. <cmd> must use
# only paths relative to the root. Exit status: <cmd>'s own, or
# _ARTIFACT_DIR_UNUSABLE with the cause on stderr when the root is unset,
# cannot be entered, or the entered directory carries no marker. Everything —
# the unset check included — runs inside the subshell, so a die there exits
# only the subshell (never firing the caller's EXIT trap) and each op decides
# how to propagate: delete returns, the others exit. The unset check matters:
# a `cd ""` must never leave the subshell working in the caller's cwd.
_artifact_dir_held() {
    (
        [[ -n "${ARTIFACT_DIR_ROOT:-}" ]] \
            || die_code "$_ARTIFACT_DIR_UNUSABLE" "artifact_dir: ARTIFACT_DIR_ROOT not set — activate via artifact_registry_activate dir"
        CDPATH='' cd -P -- "$ARTIFACT_DIR_ROOT" >/dev/null 2>&1 \
            || die_code "$_ARTIFACT_DIR_UNUSABLE" "artifact_dir: backend root not found: $ARTIFACT_DIR_ROOT (is the share mounted?)"
        [[ -f "$_ARTIFACT_DIR_MARKER" ]] \
            || die_code "$_ARTIFACT_DIR_UNUSABLE" "artifact_dir: $ARTIFACT_DIR_ROOT is not an initialized artifact store (no $_ARTIFACT_DIR_MARKER marker) — is the share mounted there? If this directory IS the share, run: ait artifact init-store dir"
        "$@"
    )
}

# _artifact_dir_still_held -- exit 0 iff the directory we hold still carries
# the marker. Held subshells only. Resolved relative to the held cwd, so a
# different directory can never answer it: it is NOT a pathname re-check of
# the root, and it never authorizes a write (put relies on the held cwd
# alone). It only qualifies a NEGATIVE answer — absent / deleted / a listing
# — that a dead directory would otherwise produce.
_artifact_dir_still_held() { [[ -f "$_ARTIFACT_DIR_MARKER" ]]; }

# _artifact_dir_lookup <rel> -- held subshells only. 0 = a regular file is
# present; 1 = genuinely absent (ENOENT, and the held directory is still the
# store afterwards); exits _ARTIFACT_DIR_UNUSABLE otherwise: a lookup error
# (EACCES, EIO, ESTALE …), a non-regular file at the blob name, or a store
# that went away. METADATA ONLY — it never opens the entry: opening a FIFO
# squatting on the blob name blocks forever, stalling the transaction with
# its lock held. `ls -ld` is one POSIX command that only lstat()s, reports the
# type as the mode string's first character, and prints strerror on failure
# (pinned to LC_ALL=C: the text is locale-dependent). `[[ -f ]]` cannot tell
# ENOENT from EIO, and the GNU/BSD `stat -c || stat -f` chain mixes two
# commands' stderr.
_artifact_dir_lookup() {
    local rel="$1" out
    [[ -f "$rel" ]] && return 0
    if out="$(LC_ALL=C ls -ld -- "$rel" 2>&1)"; then
        [[ "${out:0:1}" == "-" ]] && return 0     # created between the two lookups
        die_code "$_ARTIFACT_DIR_UNUSABLE" "artifact_dir: $rel in the store at $ARTIFACT_DIR_ROOT exists but is not a regular file (type '${out:0:1}') — remove it by hand"
    fi
    [[ "$out" == *"No such file or directory" ]] \
        || die_code "$_ARTIFACT_DIR_UNUSABLE" "artifact_dir: lookup of $rel failed in the store at $ARTIFACT_DIR_ROOT (${out##*: }) — is the share healthy?"
    _artifact_dir_still_held \
        || die_code "$_ARTIFACT_DIR_UNUSABLE" "artifact_dir: the store at $ARTIFACT_DIR_ROOT went away during the operation (share unmounted?) — cannot tell whether $rel is present"
    return 1
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
# than answering "absent") when the store is unusable or the lookup fails:
# the attach/artifact transactions turn "absent" into blob_pre=false, and
# their rollback then deletes the blob — which other checkouts may share.
artifact_dir_head() {
    local rel rc=0
    rel="$(artifact_shard_path "$1")" || die "artifact_dir_head: invalid hash: $1"
    _artifact_dir_held _artifact_dir_lookup "$rel" || rc=$?
    case "$rc" in
        0|1) return "$rc" ;;
        *)   exit 1 ;;      # cause already on stderr
    esac
}

# artifact_dir_put <hash> <file> -- idempotent atomic copy into the shard,
# CONTENT-VERIFYING a pre-existing dest (deliberate deviation from local.sh's
# bare existence check): a content-addressed entry whose bytes don't hash to
# its own address is by definition corruption (atomic mv means no half-writes
# sit at a final name), and the source bytes we hold DO hash to the address,
# so overwriting is a strict repair — mirroring the cache's self-heal. The
# local backend instead dies on canonical corruption because its blobs are
# git-tracked (repair = data-branch surgery); the dir store has no history.
# Every write (shard mkdir, temp, final mv) is relative to the held root.
artifact_dir_put() {
    local hash="$1" src="$2" rel
    [[ -f "$src" ]] || die "artifact_dir_put: not a file: $src"
    # Absolute against the caller's cwd, which the held subshell leaves. Plain
    # assignment, never $( ): command substitution strips trailing newlines,
    # which are legal path bytes.
    [[ "$src" == /* ]] || src="$PWD/$src"
    rel="$(artifact_shard_path "$hash")" || die "artifact_dir_put: invalid hash: $hash"
    _artifact_dir_held _artifact_dir_put_held "$hash" "$src" "$rel" || exit 1
}

# _artifact_dir_put_held <hash> <abs-src> <rel> -- put's body; cwd = held root.
_artifact_dir_put_held() {
    local hash="$1" src="$2" rel="$3" shard="${3%/*}" tmp
    if _artifact_dir_lookup "$rel"; then
        [[ "$(artifact_sha256 "$rel")" == "$hash" ]] && return 0  # idempotent
        warn "artifact_dir_put: corrupt store entry for $hash at $ARTIFACT_DIR_ROOT/$rel — repairing with verified bytes"
    fi
    mkdir -p -- "$shard" \
        || die "artifact_dir_put: could not create shard dir $shard in the store at $ARTIFACT_DIR_ROOT — did the share go away during the operation? Nothing was installed."
    tmp="$(mktemp "$shard/.put.XXXXXX")" \
        || die "artifact_dir_put: mktemp failed in $ARTIFACT_DIR_ROOT/$shard"
    # Atomic in the strong sense: this runs in errexit-suppressed transaction
    # trees, where an unchecked failed/partial cp would still let mv install
    # truncated bytes at the content-addressed name and return success. Abort
    # on cp failure and hash-verify the STAGED bytes before they ever reach
    # the canonical path (catches disk-full / dropped-mount partial copies).
    if ! cp -- "$src" "$tmp"; then
        rm -f -- "$tmp"
        die "artifact_dir_put: copy failed for $hash (partial copy removed)"
    fi
    if [[ "$(artifact_sha256 "$tmp")" != "$hash" ]]; then
        rm -f -- "$tmp"
        die "artifact_dir_put: staged bytes for $hash failed verification — nothing installed"
    fi
    mv -f -- "$tmp" "$rel" \
        || { rm -f -- "$tmp"; die "artifact_dir_put: could not install $hash into the store"; }
}

# artifact_dir_get <hash> <dest> -- copy the blob to <dest> ("-" = stdout).
artifact_dir_get() {
    local hash="$1" dest="$2" rel
    # An empty dest would become "$PWD/" — a directory copy into the cwd.
    [[ -n "$dest" ]] || die "artifact_dir_get: empty destination for $hash"
    # Absolute by plain assignment, as in put (no $( ): trailing newlines).
    [[ "$dest" == "-" || "$dest" == /* ]] || dest="$PWD/$dest"
    rel="$(artifact_shard_path "$hash")" || die "artifact_dir_get: invalid hash: $hash"
    _artifact_dir_held _artifact_dir_get_held "$hash" "$rel" "$dest" || exit 1
}

# _artifact_dir_get_held <hash> <rel> <abs-dest|-> -- get's body; cwd = held root.
_artifact_dir_get_held() {
    local hash="$1" rel="$2" dest="$3"
    _artifact_dir_lookup "$rel" || die "artifact_dir_get: blob not present: $hash"
    if [[ "$dest" == "-" ]]; then cat -- "$rel"; else cp -- "$rel" "$dest"; fi
}

# artifact_dir_delete <hash> -- remove the blob (no-op if absent). RETURNS
# non-zero (with the cause on stderr) when the hash is invalid, the store is
# unusable, or the held store went away during the delete — it NEVER dies.
# Delete is the op the rollback hooks (_artifact_rollback_create_blobs,
# _artifact_rollback_move_blobs, _attach_rollback_add_blobs) call from the
# chained EXIT trap; an exit there would cut the trap short, skipping the
# rollback report, the snapshot cleanup and the chained registry_lock_release
# — leaking the global attach lock. Every caller handles a returned failure
# (`|| txn_rollback_failed` in the hooks, `|| die` elsewhere).
artifact_dir_delete() {
    local rel
    artifact_validate_hash "$1" || { warn "artifact_dir_delete: invalid hash: '$1'"; return 1; }
    rel="$(artifact_shard_path "$1")" || return 1
    _artifact_dir_held _artifact_dir_delete_held "$rel" || return 1
}

# _artifact_dir_delete_held <rel> -- delete's body; cwd = held root. `rm -f`
# also "succeeds" in a dead directory, so the removal only counts when the
# held directory is still the store afterwards.
_artifact_dir_delete_held() {
    rm -f -- "$1" || exit 1
    _artifact_dir_still_held \
        || die_code "$_ARTIFACT_DIR_UNUSABLE" "artifact_dir: the store at $ARTIFACT_DIR_ROOT went away during the delete — cannot confirm $1 was removed"
}

# artifact_dir_list -- print every stored hash (sha256:<hex>), one per line.
artifact_dir_list() {
    _artifact_dir_held _artifact_dir_list_held || exit 1
}

# _artifact_dir_list_held -- list's body; cwd = held root. The listing is
# printed only once the held directory is confirmed still the store: a dead
# directory globs empty, which must never read as an empty store.
_artifact_dir_list_held() {
    local shard prefix f out=""
    for shard in */; do
        [[ -d "$shard" ]] || continue
        prefix="${shard%/}"
        for f in "$shard"*; do
            [[ -f "$f" ]] || continue
            out+="sha256:${prefix}${f##*/}"$'\n'
        done
    done
    _artifact_dir_still_held \
        || die_code "$_ARTIFACT_DIR_UNUSABLE" "artifact_dir: the store at $ARTIFACT_DIR_ROOT went away during the listing (share unmounted?)"
    printf '%s' "$out"
}
