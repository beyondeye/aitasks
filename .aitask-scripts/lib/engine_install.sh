#!/usr/bin/env bash
# engine_install.sh — stage, verify and publish an ait-testmap engine into a
# per-user engine slot: $AITASKS_HOME/engine/v<V>/ (release) or engine/dev/.
#
# Sourced (not executed) by install_engine_binary() in aitask_setup.sh — which
# install.sh also reaches — and by aitask_engine.sh. It is on no startup chain:
# setup sources it lazily, inside the function that needs it.
#
# ERREXIT-INDEPENDENT BY CONSTRUCTION. install.sh calls the installer as
# `install_engine_binary … || true`, which switches errexit off for the whole
# call tree; setup calls it plainly, with errexit on. Every command here that
# can fail is therefore checked explicitly, nothing runs after a failed step,
# and no function calls die() — each returns a status for its caller to report.
#
# Slot layout:
#   ait-testmap          the engine (mode 0755)
#   ait-testmap.sha256   sidecar, sha256sum format "<hex>  ait-testmap", written
#                        only after a VERIFIED release install; a re-run whose
#                        binary still matches it (and self-checks) skips the fetch
#   .dev                 the slot holds a non-release build (--local-engine,
#                        --engine-from-source); no installer replaces it without
#                        --force-engine. engine/dev/ never carries one.
#
# Every slot writer — the three install tiers, `ait engine build`, `ait engine
# prune` — holds the slot's publication lock ($AITASKS_HOME/engine/.locks/<slot>,
# a stale_lock mutex) around its write, and the .dev protection is re-checked
# under it: a check made before a download is only a fast path, never the guard.
#
# Interfaces (each pinned by the named tests/test_install_engine_binary.sh case)
#
# | function | contract | pinned by |
# |---|---|---|
# | engine_read_framework_version <file> | stdout the version; 1 missing/unreadable, 2 empty or outside [A-Za-z0-9._+-] (one CR stripped) | E2, E2b |
# | engine_fetch <url> <dest> | curl -fsSL / wget; 1 on any failure (partial dest removed); dest is NOT executable | R0, R5 |
# | engine_stage_exec <file> | chmod 0755, verified; run on every staged binary BEFORE its self-check | R0, R1 |
# | engine_self_check <bin> <V> | `version --json` must carry "version":"<V>"; on mismatch stdout the found version (or ?), 1 | I6 |
# | engine_sum_lookup <sums> <name> | stdout the hex of exactly one `<64 hex>  <name>` line, else 1 | R3, R4 |
# | engine_slot_lock <slot> | 0 held; 1 a holder kept it (slot-busy); 3 lock dir could not be prepared (lock-unavailable) | D5, D6 |
# | engine_publish <mode> … | under the lock: 0 published, 1 nothing changed, 2 rollback failed, 3 a destination is a directory, 4 .dev-protected, 5 slot on another (or unknown) filesystem | D4, F1-F4, P1-P7 |
# | engine_publish_locked <mode> … | lock + publish + unlock; adds 6 slot-busy, 7 lock-unavailable | D4, D5, D6 |
# | engine_publish_report <rc> <bin> <label> | the TESTMAP_BINARY: line for a publish result | I1, R1, D1-D6, F1-F4 |
#
# Test seams, set by nothing but tests/test_install_engine_binary.sh, so the
# concurrent-writer cases are deterministic:
#   AIT_ENGINE_TEST_PRE_PUBLISH_HOOK=<exe>  runs after staging, before the slot
#                                           lock is taken (D4)
#   AIT_ENGINE_TEST_POST_UNLOCK_HOOK=<exe>  runs right after a slot lock is
#                                           released, given the lock dir (E6)
#
# Requires warn() from the caller (aitask_setup.sh, install.sh and
# terminal_compat.sh all define it). Idempotent: sourcing twice is a no-op.

if [[ -n "${_ENGINE_INSTALL_LOADED:-}" ]]; then
    return 0
fi
_ENGINE_INSTALL_LOADED=1

_ENGINE_INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/aitasks_home.sh
source "$_ENGINE_INSTALL_DIR/aitasks_home.sh"
# shellcheck source=lib/stale_lock.sh
source "$_ENGINE_INSTALL_DIR/stale_lock.sh"

_ENGINE_LOCK_DIR=""
_ENGINE_LOCK_TOKEN=""

# engine_read_framework_version <file> — the ONE reader of an
# .aitask-scripts/VERSION for the engine: install, `engine build`, prune.
engine_read_framework_version() {
    local f="$1" v=""
    [[ -f "$f" && -r "$f" ]] || return 1
    { v="$(<"$f")"; } 2>/dev/null || return 1
    v="${v%$'\r'}"
    [[ -n "$v" && "$v" =~ ^[A-Za-z0-9._+-]+$ ]] || return 2
    printf '%s\n' "$v"
}

# engine_sha256 <file> — print the file's sha256 hex digest.
engine_sha256() {
    local out
    if command -v sha256sum >/dev/null 2>&1; then
        out="$(sha256sum "$1" 2>/dev/null)" || return 1
    elif command -v shasum >/dev/null 2>&1; then
        out="$(shasum -a 256 "$1" 2>/dev/null)" || return 1
    else
        return 1
    fi
    out="${out%% *}"
    [[ "$out" =~ ^[0-9a-f]{64}$ ]] || return 1
    printf '%s\n' "$out"
}

# engine_sum_lookup <sumsfile> <name> — the hex of the ONE line naming <name>.
# Compared by awk field equality, so a version's dots are never regex wildcards.
engine_sum_lookup() {
    local sums="$1" name="$2" hits
    [[ -f "$sums" ]] || return 1
    hits="$(awk -v n="$name" 'NF == 2 && $2 == n && $1 ~ /^[0-9a-f]+$/ && length($1) == 64 { print $1 }' "$sums" 2>/dev/null)" || return 1
    [[ -n "$hits" && "$hits" != *$'\n'* ]] || return 1
    printf '%s\n' "$hits"
}

# engine_file_matches <file> <hex> — the file's digest equals <hex>.
engine_file_matches() {
    local got
    got="$(engine_sha256 "$1")" || return 1
    [[ "$got" == "$2" ]]
}

# engine_fetch <url> <dest> — download with the URL family install.sh uses.
# curl's -f is load-bearing: without it a 404 page lands in <dest> with exit 0.
engine_fetch() {
    local url="$1" dest="$2" rc=0
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL --max-time 120 "$url" -o "$dest" 2>/dev/null || rc=$?
    elif command -v wget >/dev/null 2>&1; then
        wget -q --timeout=120 "$url" -O "$dest" 2>/dev/null || rc=$?
    else
        rc=127
    fi
    if [[ "$rc" -ne 0 || ! -f "$dest" ]]; then
        rm -f "$dest" 2>/dev/null
        return 1
    fi
    return 0
}

# engine_stage_exec <file> — make a staged binary executable. A download
# arrives 0644, so this MUST precede the self-check that executes it.
engine_stage_exec() {
    chmod 0755 "$1" 2>/dev/null || return 1
    [[ -f "$1" && -x "$1" ]]
}

# engine_self_check <bin> <V> — the staged binary must report exactly <V>.
engine_self_check() {
    local bin="$1" want="$2" out found
    if ! out="$("$bin" version --json </dev/null 2>/dev/null)"; then
        printf '?\n'
        return 1
    fi
    if printf '%s\n' "$out" | grep -qF "\"version\":\"$want\""; then
        return 0
    fi
    found="$(printf '%s\n' "$out" | sed -n 's/.*"version":"\([^"]*\)".*/\1/p' | head -n1)"
    [[ -n "$found" && "$found" != *'|'* ]] || found="?"
    printf '%s\n' "$found"
    return 1
}

# engine_dev_id <path> — the st_dev of what <path> RESOLVES to (GNU stat, else
# BSD stat; -L in both). Without -L a slot that is a symlink would report the
# link's own filesystem, not the one the rename would actually write to.
engine_dev_id() {
    local d
    d="$(stat -L -c %d "$1" 2>/dev/null)" || d="$(stat -L -f %d "$1" 2>/dev/null)" || return 1
    [[ "$d" =~ ^[0-9]+$ ]] || return 1
    printf '%s\n' "$d"
}

# engine_staging_dir — a fresh staging dir beside the slots (same filesystem,
# so publication is a rename). Prints its path.
engine_staging_dir() {
    if [[ ! -d "$AITASKS_HOME/engine" ]]; then
        # shellcheck disable=SC2174  # the mode is meant for engine/ alone
        mkdir -p -m 0755 "$AITASKS_HOME/engine" 2>/dev/null || return 1
    fi
    mktemp -d "$AITASKS_HOME/engine/.staging.XXXXXX" 2>/dev/null
}

# engine_slot_lock <slot name> — take the slot's publication lock.
# 0 held · 1 a holder kept it past the deadline · 3 could not be prepared.
# stale_lock's guard and lock are plain mkdirs that never create their parent,
# so .locks/ is prepared here: without it every acquire on a fresh root would
# exhaust its retries and read as a busy slot.
engine_slot_lock() {
    local locks="$AITASKS_HOME/engine/.locks" dir
    dir="$locks/$1"
    _ENGINE_LOCK_DIR=""
    _ENGINE_LOCK_TOKEN=""
    mkdir -p "$locks" 2>/dev/null || return 3
    [[ -d "$locks" ]] || return 3
    if stale_lock_acquire "$dir" "${ENGINE_SLOT_LOCK_RETRIES:-600}" 0.1 "engine slot $1"; then
        _ENGINE_LOCK_DIR="$dir"
        _ENGINE_LOCK_TOKEN="$STALE_LOCK_TOKEN"
        return 0
    fi
    [[ -e "$dir" ]] && return 1
    return 3
}

# engine_slot_unlock — release the lock engine_slot_lock took (no-op if none).
engine_slot_unlock() {
    [[ -n "$_ENGINE_LOCK_DIR" ]] || return 0
    stale_lock_release "$_ENGINE_LOCK_DIR" "$_ENGINE_LOCK_TOKEN" ||
        warn "engine slot lock $_ENGINE_LOCK_DIR was not released cleanly"
    if [[ -n "${AIT_ENGINE_TEST_POST_UNLOCK_HOOK:-}" ]]; then
        "$AIT_ENGINE_TEST_POST_UNLOCK_HOOK" "$_ENGINE_LOCK_DIR" || true
    fi
    _ENGINE_LOCK_DIR=""
    _ENGINE_LOCK_TOKEN=""
    return 0
}

# engine_publish <release|marked|devslot> <staged bin> <slot dir> <force 0|1> [<staged sidecar>]
# Call with the slot lock held. 0 published · 1 nothing changed · 2 a rollback
# step failed (inspect the slot) · 3 a destination is a directory (nothing
# changed) · 4 protected by .dev (nothing changed) · 5 the slot is not on the
# staging filesystem, or that could not be established (nothing changed).
engine_publish() {
    local mode="$1" staged="$2" slot="$3" force="${4:-0}" staged_sum="${5:-}"
    local bin="$slot/ait-testmap" dev="$slot/.dev" sum="$slot/ait-testmap.sha256"
    local had_dev=0 aside="" rb=0

    if [[ "$mode" != devslot && "$force" != 1 && -e "$dev" ]]; then return 4; fi  # under-lock .dev re-check (D4)

    mkdir -p "$slot" 2>/dev/null || return 1
    [[ -d "$slot" ]] || return 1
    # mv onto a directory (or a symlink to one) NESTS the source inside it and
    # still succeeds — the slot would claim an install that never happened.
    # Refused here, under the lock, before any metadata is touched.
    if [[ -d "$bin" || -d "$sum" ]]; then return 3; fi
    # Publication is only atomic as a same-filesystem rename. A slot linked onto
    # another filesystem would turn mv into copy-then-delete: a reader could see
    # a half-written binary, and a failed copy could lose the previous one.
    # Refused — and an unknowable device id is refused too (fail closed).
    local sdev ddev
    sdev="$(engine_dev_id "$(dirname "$staged")")" || return 5
    ddev="$(engine_dev_id "$slot")" || return 5
    [[ "$sdev" == "$ddev" ]] || return 5

    case "$mode" in
        devslot)
            mv -f "$staged" "$bin" 2>/dev/null || return 1
            return 0
            ;;
        release)
            mv -f "$staged" "$bin" 2>/dev/null || return 1
            # The binary is now the verified release. A sidecar that cannot be
            # written only costs the next run a re-fetch: its stale hash (or its
            # absence) never matches the new binary.
            if [[ -z "$staged_sum" ]] || ! mv -f "$staged_sum" "$sum" 2>/dev/null; then
                printf 'TESTMAP_BINARY:sidecar-not-written|%s\n' "$sum"
                warn "Could not write $sum — the next 'ait setup' re-downloads the engine."
            fi
            if [[ -e "$dev" ]] && ! rm -f "$dev" 2>/dev/null; then
                warn "Could not remove $dev — the slot stays marked as a custom build."
            fi
            return 0
            ;;
        marked)
            [[ -e "$dev" ]] && had_dev=1
            # The marker goes down BEFORE the binary: a crash in between leaves
            # a protected slot, never an unprotected custom binary.
            if [[ "$had_dev" == 0 ]]; then
                { : > "$dev"; } 2>/dev/null || return 1
            fi
            if [[ -e "$sum" ]]; then
                aside="$(dirname "$staged")/previous.sha256"
                if ! mv -f "$sum" "$aside" 2>/dev/null; then
                    if [[ "$had_dev" == 0 ]]; then rm -f "$dev" 2>/dev/null || return 2; fi
                    return 1
                fi
            fi
            if ! mv -f "$staged" "$bin" 2>/dev/null; then
                if [[ -n "$aside" ]]; then mv -f "$aside" "$sum" 2>/dev/null || rb=1; fi
                if [[ "$had_dev" == 0 ]]; then rm -f "$dev" 2>/dev/null || rb=1; fi
                [[ "$rb" == 0 ]] && return 1
                return 2
            fi
            return 0
            ;;
    esac
    return 1
}

# engine_publish_locked <mode> <staged bin> <slot dir> <force> [<staged sidecar>]
# engine_publish under the slot's lock (same codes 0-5). Adds 6 (slot busy) and
# 7 (lock unavailable).
engine_publish_locked() {
    local mode="$1" staged="$2" slot="$3" force="${4:-0}" staged_sum="${5:-}" rc=0 name
    name="$(basename "$slot")"
    if [[ -n "${AIT_ENGINE_TEST_PRE_PUBLISH_HOOK:-}" ]]; then
        "$AIT_ENGINE_TEST_PRE_PUBLISH_HOOK" || true
    fi
    engine_slot_lock "$name" || rc=$?
    if [[ "$rc" -eq 1 ]]; then return 6; fi
    if [[ "$rc" -ne 0 ]]; then return 7; fi
    engine_publish "$mode" "$staged" "$slot" "$force" "$staged_sum" || rc=$?
    engine_slot_unlock
    return "$rc"
}

# engine_publish_report <rc> <bin> <source label> — the TESTMAP_BINARY: line.
engine_publish_report() {
    local rc="$1" bin="$2" label="$3"
    case "$rc" in
        0) printf 'TESTMAP_BINARY:installed|%s|%s\n' "$bin" "$label" ;;
        4) printf 'TESTMAP_BINARY:kept-dev|%s\n' "$bin"
           warn "$bin is a custom engine build (.dev); pass --force-engine to replace it." ;;
        6) printf 'TESTMAP_BINARY:slot-busy|%s\n' "$bin"
           warn "Another process holds the engine slot lock; nothing was written." ;;
        7) printf 'TESTMAP_BINARY:lock-unavailable|%s\n' "$AITASKS_HOME/engine/.locks"
           warn "Could not prepare the engine slot lock under $AITASKS_HOME/engine/.locks; nothing was written." ;;
        3) printf 'TESTMAP_BINARY:slot-invalid|%s\n' "$(dirname "$bin")"
           warn "A directory sits where the engine or its sidecar belongs in $(dirname "$bin"); nothing was written — remove it by hand." ;;
        5) printf 'TESTMAP_BINARY:slot-cross-device|%s\n' "$(dirname "$bin")"
           warn "$(dirname "$bin") is not on the filesystem of $AITASKS_HOME/engine, so it cannot be replaced atomically; nothing was written." ;;
        2) printf 'TESTMAP_BINARY:install-failed|rollback|%s\n' "$bin"
           warn "Engine install failed AND its rollback failed — inspect $(dirname "$bin") by hand." ;;
        *) printf 'TESTMAP_BINARY:install-failed|%s\n' "$bin"
           warn "Engine install failed; the previous binary and its protection are unchanged." ;;
    esac
}
