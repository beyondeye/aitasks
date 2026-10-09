#!/usr/bin/env bash
set -euo pipefail

# aitask_engine.sh — `ait engine <verb>`: developer and housekeeping verbs for
# the ait-testmap engine binaries (t1852_5, test map M1.5).
#
#   build              build this checkout's engine into the dev slot
#                      ($AITASKS_HOME/engine/dev/), version <VERSION>-dev+<sha>;
#                      use it with AIT_ENGINE=dev ait testmap …
#   test [args]        go vet + go test over goengines/ (args go to go test)
#   cross [args]       the release matrix: goengines/build.sh all [args]
#   prune [--dry-run] [--force]
#                      remove release slots $AITASKS_HOME/engine/v*/ that no
#                      registered project (`ait projects`) uses — never by count
#   home [--migrate]   report the legacy per-user root beside $AITASKS_HOME;
#                      --migrate moves its tenants into $AITASKS_HOME and
#                      leaves a compatibility symlink behind (t1852_6)
#
# build / test / cross need the Go source, which ships only in the aitasks
# framework repository. prune and home work in any project.
#
# Interfaces (each pinned by the named tests/test_install_engine_binary.sh case)
#
# | shape | contract | pinned by |
# |---|---|---|
# | ENGINE_BUILT:<bin>|<version> | stdout, build published into the dev slot | E4 |
# | ENGINE_SOURCE_MISSING:<dir> | stderr, exit 3; no goengines/ here | E3 |
# | ENGINE_SLOT_BUSY:<bin> / ENGINE_LOCK_UNAVAILABLE:<dir> / ENGINE_SLOT_INVALID:<bin> / ENGINE_SLOT_CROSS_DEVICE:<bin> / ENGINE_INSTALL_FAILED:<bin> | stderr, exit 1 | E4, P5 |
# | PRUNE_KEPT:<dir>|<project names csv> | a registered project's framework VERSION | E1, E2b |
# | PRUNE_KEPT:<dir>|dev-marked / PRUNE_KEPT:<dir>|busy | a .dev slot without --force / a held slot lock | E1, E5 |
# | PRUNE_WOULD:<dir> / PRUNED:<dir> | --dry-run / removed | E1, E2b |
# | PRUNE_FAILED:<dir>|<reason> | the slot survived a removal attempt; exit 1 at the end | E5 |
# | PRUNE_REFUSED:no-registry|<file> | exit 1, nothing removed | E2 |
# | PRUNE_REFUSED:registry-unreadable|<file> | exit 1, nothing removed | E2 |
# | PRUNE_REFUSED:version-unreadable|<file> / version-invalid|<file> | a kept project's .aitask-scripts/VERSION; exit 1, nothing removed | E2 |
# | UNKNOWN_VERB:<verb> then USAGE:<msg> / USAGE:<msg> | stderr, exit 64 | E3 |
#
# `home` shapes (stdout), each pinned by the named tests/test_aitasks_home.sh case
#
# | shape | contract | pinned by |
# |---|---|---|
# | HOME_ROOT:<path> / HOME_LEGACY:<path>|<csv or (empty)> / HOME_LEGACY:none / HOME_SYMLINK:none|<target> | report, read-only, exit 0 | H1, H2 |
# | HOME_NEXT:migrate|<n>|<csv> / HOME_NEXT:none|<reason> / HOME_NEXT:refuse|<reason> (one line per reason) | what --migrate would do | H1-H3, H12 |
# | HOME_SKIPPED:no-legacy-root / already-migrated | --migrate, nothing to do, nothing created, exit 0 | H4, H13 |
# | HOME_SKIPPED:<refusal> (one line per reason) | preflight refusal, nothing moved, exit 1 — foreign-symlink:<t>, legacy-not-a-directory, root-not-absolute, root-not-normalized, root-unresolvable, same-root, root-inside-legacy, legacy-inside-root, cross-device, cross-device:<n>, unknown-entry:<n> (control characters %q-escaped), relative-symlink:<path>, scan-incomplete[:<path>] (a directory find could not read, or a link target that could not be read), destination-exists:<n>, busy, lock-unavailable | H5-H10, H16, H18, H24-H26 |
# | HOME_MIGRATED:<n> | moved, legacy root is now a symlink to $AITASKS_HOME, exit 0 (128+signo when a signal arrived after ln — the completed migration is kept) | H11, H12, H21, H28 |
# | HOME_SKIPPED:<reason> then HOME_ROLLED_BACK:<n> | a step failed or a signal arrived mid-move; every moved entry restored, exit 1 (128+signo when interrupted) — destination-exists:<n>, move-failed:<n>, legacy-root-not-empty:<csv>, symlink-failed, interrupted:<SIG> | H14-H16, H19, H20 |
# | HOME_FAILED:rollback|<csv> then HOME_STRANDED:<name>|<now>|<legacy> and HOME_RESTORE:<name or .>|<command> lines, run in order (per entry: competitor aside, then restore — or the single restore when nothing occupies the legacy path; when the legacy root itself is obstructed: obstruction aside, mkdir, then each entry; when it is absent: mkdir, then each entry) | rollback blocked; competing entries and obstructions untouched, exit 2 | H22, H23, H27, H29, H30 |
# | USAGE:<msg> | home with an argument other than --migrate, exit 64 | H17 |

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GOENGINES="$SCRIPT_DIR/../goengines"

# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/aitasks_home.sh
source "$SCRIPT_DIR/lib/aitasks_home.sh"
# shellcheck source=lib/engine_install.sh
source "$SCRIPT_DIR/lib/engine_install.sh"

REGISTRY_FILE="${AITASKS_PROJECTS_INDEX:-$HOME/.config/aitasks/projects.yaml}"

usage_line() {
    echo "USAGE:ait engine build | test [go test args] | cross [build.sh args] | prune [--dry-run] [--force] | home [--migrate]" >&2
}

require_source() {
    if [[ ! -f "$GOENGINES/build.sh" ]]; then
        echo "ENGINE_SOURCE_MISSING:$GOENGINES" >&2
        echo "The Go engine source ships only in the aitasks framework repository." >&2
        exit 3
    fi
    GOENGINES="$(cd "$GOENGINES" && pwd)"
}

# The framework VERSION of this checkout, validated (exit 3 when unusable).
framework_version() {
    local v rc=0
    v="$(engine_read_framework_version "$SCRIPT_DIR/VERSION")" || rc=$?
    if [[ "$rc" -ne 0 ]]; then
        echo "VERSION_INVALID:$SCRIPT_DIR/VERSION" >&2
        exit 3
    fi
    printf '%s\n' "$v"
}

cmd_build() {
    [[ $# -eq 0 ]] || { usage_line; exit 64; }
    require_source
    local v sha version staging out built found prc=0 slot bin
    v="$(framework_version)"
    if ! sha="$(git -C "$SCRIPT_DIR/.." rev-parse HEAD 2>/dev/null)" || [[ ! "$sha" =~ ^[0-9a-f]{40,64}$ ]]; then
        echo "ENGINE_BUILD_FAILED:no git commit to stamp the dev build with" >&2
        exit 1
    fi
    version="$v-dev+$sha"
    slot="$(aitasks_engine_dir dev)"
    bin="$slot/ait-testmap"
    staging="$(engine_staging_dir)" || { echo "ENGINE_BUILD_FAILED:cannot create staging under $AITASKS_HOME/engine" >&2; exit 1; }
    if ! out="$(bash "$GOENGINES/build.sh" --version "$version" --commit "$sha" --out "$staging" host)"; then
        rm -rf -- "$staging"
        echo "ENGINE_BUILD_FAILED:goengines/build.sh" >&2
        exit 1
    fi
    built="$(printf '%s\n' "$out" | sed -n 's/^BUILT://p')"
    if [[ -z "$built" || "$built" == *$'\n'* || ! -f "$built" ]] || ! engine_stage_exec "$built"; then
        rm -rf -- "$staging"
        echo "ENGINE_BUILD_FAILED:no single BUILT: binary" >&2
        exit 1
    fi
    if ! found="$(engine_self_check "$built" "$version")"; then
        rm -rf -- "$staging"
        echo "ENGINE_BUILD_FAILED:built engine reports '$found', expected '$version'" >&2
        exit 1
    fi
    engine_publish_locked devslot "$built" "$slot" 0 || prc=$?
    rm -rf -- "$staging"
    case "$prc" in
        0) ;;
        6) echo "ENGINE_SLOT_BUSY:$bin" >&2; exit 1 ;;
        7) echo "ENGINE_LOCK_UNAVAILABLE:$AITASKS_HOME/engine/.locks" >&2; exit 1 ;;
        3) echo "ENGINE_SLOT_INVALID:$bin" >&2; exit 1 ;;
        5) echo "ENGINE_SLOT_CROSS_DEVICE:$bin" >&2; exit 1 ;;
        *) echo "ENGINE_INSTALL_FAILED:$bin" >&2; exit 1 ;;
    esac
    echo "ENGINE_BUILT:$bin|$version"
    info "Use it with: AIT_ENGINE=dev ait testmap <verb>" >&2
}

cmd_test() {
    require_source
    cd "$GOENGINES"
    go vet ./...
    go test ./... "$@"
}

cmd_cross() {
    require_source
    exec bash "$GOENGINES/build.sh" all "$@"
}

# prune_keep_add <version file> <name> — validate one framework VERSION and add
# it to the keep set; refuse the whole prune (exit 1) when it is unusable.
prune_keep_add() {
    local file="$1" name="$2" v rc=0
    v="$(engine_read_framework_version "$file")" || rc=$?
    case "$rc" in
        0) ;;
        2) echo "PRUNE_REFUSED:version-invalid|$file"; exit 1 ;;
        *) echo "PRUNE_REFUSED:version-unreadable|$file"; exit 1 ;;
    esac
    KEEP_VERSIONS+=("$v")
    KEEP_NAMES+=("$name")
}

# The project names keeping version $1, comma-separated (empty when none).
prune_keepers() {
    local i names=""
    for i in "${!KEEP_VERSIONS[@]}"; do
        if [[ "${KEEP_VERSIONS[$i]}" == "$1" ]]; then
            names="${names:+$names,}${KEEP_NAMES[$i]}"
        fi
    done
    printf '%s\n' "$names"
}

cmd_prune() {
    local dry_run=0 force=0
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run) dry_run=1; shift ;;
            --force)   force=1; shift ;;
            *) usage_line; exit 64 ;;
        esac
    done

    if [[ ! -f "$REGISTRY_FILE" ]]; then
        echo "PRUNE_REFUSED:no-registry|$REGISTRY_FILE"
        info "Register each project that uses the engine with 'ait projects add', then re-run." >&2
        exit 1
    fi
    local rows
    rows="$(AITASKS_PROJECTS_INDEX="$REGISTRY_FILE" "$SCRIPT_DIR/aitask_project_resolve.sh" list 2>/dev/null)" || rows=""
    rows="$(printf '%s\n' "$rows" | grep '^PROJECT:' || true)"
    if [[ -z "$rows" ]]; then
        echo "PRUNE_REFUSED:registry-unreadable|$REGISTRY_FILE"
        exit 1
    fi

    # The whole keep set is read and validated before anything is removed. Only
    # .aitask-scripts/VERSION is the framework version: a root VERSION belongs
    # to the consuming project.
    KEEP_VERSIONS=()
    KEEP_NAMES=()
    prune_keep_add "$SCRIPT_DIR/VERSION" "$(basename "$(cd "$SCRIPT_DIR/.." && pwd)")"
    local row rest name path status
    while IFS= read -r row; do
        rest="${row#PROJECT:}"
        name="${rest%%:*}"
        status="${rest##*:}"
        path="${rest#*:}"
        path="${path%:*}"
        [[ "$status" == RESOLVED ]] || continue
        prune_keep_add "$path/.aitask-scripts/VERSION" "$name"
    done <<<"$rows"

    local root="$AITASKS_HOME/engine" dir ver keepers failed=0 lrc
    [[ -d "$root" ]] || return 0
    for dir in "$root"/v*; do
        [[ -d "$dir" && ! -L "$dir" ]] || continue
        ver="${dir##*/v}"
        keepers="$(prune_keepers "$ver")"
        if [[ -n "$keepers" ]]; then
            echo "PRUNE_KEPT:$dir|$keepers"
            continue
        fi
        if [[ "$force" != 1 && -e "$dir/.dev" ]]; then
            echo "PRUNE_KEPT:$dir|dev-marked"
            continue
        fi
        if [[ "$dry_run" == 1 ]]; then
            echo "PRUNE_WOULD:$dir"
            continue
        fi
        lrc=0
        engine_slot_lock "v$ver" || lrc=$?
        if [[ "$lrc" -eq 1 ]]; then
            echo "PRUNE_KEPT:$dir|busy"
            continue
        elif [[ "$lrc" -ne 0 ]]; then
            echo "PRUNE_FAILED:$dir|lock-unavailable"
            failed=1
            continue
        fi
        # Re-checked under the lock: an install may have marked it meanwhile.
        if [[ "$force" != 1 && -e "$dir/.dev" ]]; then
            engine_slot_unlock
            echo "PRUNE_KEPT:$dir|dev-marked"
            continue
        fi
        # Removal is verified while the lock is still held: after release a
        # publisher may legitimately recreate the slot, which is not a failure.
        rm -rf -- "$dir" 2>/dev/null || true
        if [[ -e "$dir" ]]; then
            engine_slot_unlock
            echo "PRUNE_FAILED:$dir|not-removed"
            failed=1
        else
            engine_slot_unlock
            echo "PRUNED:$dir"
        fi
    done
    [[ "$failed" -eq 0 ]] || exit 1
}

# --- home [--migrate] (t1852_6, M1.6) -----------------------------------------
# The legacy per-user root (venv, pypy_venv, python, bin, uv, dev_tier,
# update_check) that `home --migrate` empties into $AITASKS_HOME, leaving
# `<legacy> -> $AITASKS_HOME` behind so every consumer that spells the old path
# keeps resolving. Spelled exactly once; everything below goes through it.
LEGACY_ROOT="$HOME/.aitask"  # legacy-root-ok: the one spelling of the root `home --migrate` empties
HOME_KNOWN_ENTRIES=(venv pypy_venv python bin uv dev_tier update_check engine)

HOME_STATE=""          # none | migrated | refuse | ready  (set by home_preflight)
HOME_REASONS=()
HOME_MOVE=()           # entry names to move, LC_ALL=C order
HOME_IDS=()            # "<dev>:<inode>" of HOME_MOVE[i], recorded under the lock
HOME_ROOT_PHYS=""      # the physical path $AITASKS_HOME has (or will have)
HOME_ROOT_ANCHOR=""    # its nearest existing ancestor (itself when it exists)
HOME_PHASE=""          # "" | locked | moving | removed | linked | finished
HOME_LOCK_TOKEN=""

# home_lstat_id <path> — "<dev>:<inode>" of the path itself (lstat; GNU, else BSD).
home_lstat_id() {
    local id
    id="$(stat -c '%d:%i' -- "$1" 2>/dev/null)" || id="$(stat -f '%d:%i' "$1" 2>/dev/null)" || return 1
    [[ "$id" =~ ^[0-9]+:[0-9]+$ ]] || return 1
    printf '%s\n' "$id"
}

# home_present <path> — the path exists, a dangling symlink included.
home_present() { [[ -e "$1" || -L "$1" ]]; }

# home_entries — every entry of the legacy root, dotfiles included, LC_ALL=C
# order, NUL-terminated: a name is never split, so a name holding a newline
# (`venv` + LF) stays ONE unknown entry instead of reading as a known one.
# Consumers read it with `read -r -d ''`.
home_entries() {
    local e
    for e in "$LEGACY_ROOT"/* "$LEGACY_ROOT"/.[!.]* "$LEGACY_ROOT"/..?*; do
        home_present "$e" || continue
        printf '%s\0' "${e##*/}"
    done | LC_ALL=C sort -z
}

# home_show <name> — a name as it may appear in a protocol line: verbatim
# unless it holds a control character, %q-escaped then (one line, unambiguous).
home_show() {
    if [[ "$1" == *[[:cntrl:]]* ]]; then printf '%q\n' "$1"; else printf '%s\n' "$1"; fi
}

# home_link_escapes <link path relative to the legacy root> <target> — 0 when
# the target is relative and, resolved lexically from the link's directory,
# leaves the legacy root. Such a link means something else after the move
# (the root's parent differs); a relative link that stays inside the root
# moves with its target and keeps resolving.
home_link_escapes() {
    local rel="$1" t="$2" dir s c depth=0
    [[ "$t" == /* ]] && return 1
    dir=""
    [[ "$rel" == */* ]] && dir="${rel%/*}"
    s="$dir/$t"
    while [[ -n "$s" ]]; do
        c="${s%%/*}"
        if [[ "$s" == */* ]]; then s="${s#*/}"; else s=""; fi
        case "$c" in
            ""|.) ;;
            ..)
                if [[ "$depth" -eq 0 ]]; then return 0; fi
                depth=$((depth - 1)) ;;
            *)  depth=$((depth + 1)) ;;
        esac
    done
    return 1
}

home_is_known() {
    local k
    for k in "${HOME_KNOWN_ENTRIES[@]}"; do [[ "$k" == "$1" ]] && return 0; done
    return 1
}

# home_resolve_root — set HOME_ROOT_PHYS / HOME_ROOT_ANCHOR to the physical
# path $AITASKS_HOME has, or WILL have once created: the nearest existing
# ancestor resolved through every symlink, plus the not-yet-existing rest. This
# is what makes an alias (an outside symlink pointing into the legacy tree) a
# refusal BEFORE anything is created. 2 not normalized, 3 unresolvable.
home_resolve_root() {
    local p rest="" base
    p="$AITASKS_HOME"
    while [[ "$p" == */ && "$p" != / ]]; do p="${p%/}"; done
    case "$p/" in */./*|*/../*|*//*) return 2 ;; esac
    while ! home_present "$p"; do
        rest="/${p##*/}$rest"
        p="${p%/*}"
        [[ -n "$p" ]] || p="/"
    done
    base="$(cd -P -- "$p" 2>/dev/null && pwd -P)" || return 3
    HOME_ROOT_ANCHOR="$p"
    HOME_ROOT_PHYS="${base%/}$rest"
    [[ -n "$HOME_ROOT_PHYS" ]] || HOME_ROOT_PHYS="/"
}

# home_preflight — read-only. Sets HOME_STATE, HOME_REASONS and HOME_MOVE.
# Collects every refusal, not only the first, so one pass fixes them all.
home_preflight() {
    local e legacy_phys legacy_dev root_dev d rc=0
    HOME_STATE=""
    HOME_REASONS=()
    HOME_MOVE=()

    if [[ "$AITASKS_HOME" != /* ]]; then
        HOME_STATE=refuse; HOME_REASONS=(root-not-absolute); return 0
    fi
    if [[ -L "$LEGACY_ROOT" ]]; then
        if [[ -e "$LEGACY_ROOT" && -e "$AITASKS_HOME" && "$LEGACY_ROOT" -ef "$AITASKS_HOME" ]]; then
            HOME_STATE=migrated; HOME_REASONS=(already-migrated)
        else
            HOME_STATE=refuse; HOME_REASONS=("foreign-symlink:$(readlink "$LEGACY_ROOT" 2>/dev/null || echo '?')")
        fi
        return 0
    fi
    if [[ ! -e "$LEGACY_ROOT" ]]; then
        HOME_STATE=none; HOME_REASONS=(no-legacy-root); return 0
    fi
    if [[ ! -d "$LEGACY_ROOT" ]]; then
        HOME_STATE=refuse; HOME_REASONS=(legacy-not-a-directory); return 0
    fi

    home_resolve_root || rc=$?
    case "$rc" in
        0) ;;
        2) HOME_STATE=refuse; HOME_REASONS=(root-not-normalized); return 0 ;;
        *) HOME_STATE=refuse; HOME_REASONS=(root-unresolvable); return 0 ;;
    esac
    legacy_phys="$(cd -P -- "$LEGACY_ROOT" 2>/dev/null && pwd -P)" || {
        HOME_STATE=refuse; HOME_REASONS=(legacy-not-a-directory); return 0; }
    if [[ "$HOME_ROOT_PHYS" == "$legacy_phys" ]]; then
        HOME_STATE=refuse; HOME_REASONS=(same-root); return 0
    fi
    if [[ "$HOME_ROOT_PHYS/" == "$legacy_phys/"* ]]; then
        HOME_STATE=refuse; HOME_REASONS=(root-inside-legacy); return 0
    fi
    if [[ "$legacy_phys/" == "${HOME_ROOT_PHYS%/}/"* ]]; then
        HOME_STATE=refuse; HOME_REASONS=(legacy-inside-root); return 0
    fi

    # A root on another filesystem turns every mv into copy-then-delete. An
    # unknowable device id is refused too (fail closed).
    legacy_dev="$(engine_dev_id "$LEGACY_ROOT")" || legacy_dev=""
    root_dev="$(engine_dev_id "$HOME_ROOT_ANCHOR")" || root_dev=""
    if [[ -z "$legacy_dev" || "$legacy_dev" != "$root_dev" ]]; then
        HOME_REASONS+=(cross-device)
    fi

    while IFS= read -r -d '' e; do
        [[ -n "$e" ]] || continue
        if ! home_is_known "$e"; then
            HOME_REASONS+=("unknown-entry:$(home_show "$e")")
            continue
        fi
        # mv onto an existing directory NESTS the source inside it and still
        # succeeds; engine/ always exists after `ait setup`.
        if home_present "$AITASKS_HOME/$e"; then
            HOME_REASONS+=("destination-exists:$e")
            continue
        fi
        # A mount point (or anything on another device) would be copied.
        d="$(home_lstat_id "$LEGACY_ROOT/$e")" || d=""
        if [[ -z "$legacy_dev" || "${d%%:*}" != "$legacy_dev" ]]; then
            HOME_REASONS+=("cross-device:$e")
            continue
        fi
        HOME_MOVE+=("$e")
    done < <(home_entries)

    # A relative symlink anywhere in the tree that points OUT of it would
    # silently change target once moved (`venv -> ../external`). The scan must
    # be COMPLETE to clear the tree: a directory find cannot read hides its
    # links, so find's own exit status rides along as a trailing sentinel
    # record (a real record always starts with the absolute legacy path), and
    # a link whose target cannot be read is unverified, not clean.
    local link target find_rc=""
    while IFS= read -r -d '' link; do
        if [[ "$link" == FIND_RC:* ]]; then find_rc="${link#FIND_RC:}"; continue; fi
        if ! target="$(readlink "$link" 2>/dev/null)"; then
            HOME_REASONS+=("scan-incomplete:$(home_show "${link#"$LEGACY_ROOT"/}")")
            continue
        fi
        if home_link_escapes "${link#"$LEGACY_ROOT"/}" "$target"; then
            HOME_REASONS+=("relative-symlink:$(home_show "${link#"$LEGACY_ROOT"/}")")
        fi
    done < <(find "$LEGACY_ROOT" -mindepth 1 -type l -print0 2>/dev/null; printf 'FIND_RC:%s\0' "$?")
    if [[ "$find_rc" != 0 ]]; then
        HOME_REASONS+=(scan-incomplete)
    fi

    if [[ ${#HOME_REASONS[@]} -gt 0 ]]; then
        HOME_STATE=refuse
    else
        HOME_STATE=ready
    fi
}

home_csv() { local IFS=,; printf '%s\n' "$*"; }

# home_report — `ait engine home`: lock-free, changes nothing.
home_report() {
    local entries=() e reason
    echo "HOME_ROOT:$AITASKS_HOME"
    if [[ -d "$LEGACY_ROOT" && ! -L "$LEGACY_ROOT" ]]; then
        while IFS= read -r -d '' e; do [[ -n "$e" ]] && entries+=("$(home_show "$e")"); done < <(home_entries)
        if [[ ${#entries[@]} -gt 0 ]]; then
            echo "HOME_LEGACY:$LEGACY_ROOT|$(home_csv "${entries[@]}")"
        else
            echo "HOME_LEGACY:$LEGACY_ROOT|(empty)"
        fi
    else
        echo "HOME_LEGACY:none"
    fi
    if [[ -L "$LEGACY_ROOT" ]]; then
        echo "HOME_SYMLINK:$(readlink "$LEGACY_ROOT" 2>/dev/null || echo '?')"
    else
        echo "HOME_SYMLINK:none"
    fi
    home_preflight
    case "$HOME_STATE" in
        ready)
            echo "HOME_NEXT:migrate|${#HOME_MOVE[@]}|$(home_csv ${HOME_MOVE[@]+"${HOME_MOVE[@]}"})" ;;
        none|migrated)
            echo "HOME_NEXT:none|${HOME_REASONS[0]}" ;;
        *)
            for reason in "${HOME_REASONS[@]}"; do echo "HOME_NEXT:refuse|$reason"; done ;;
    esac
}

# home_hook <point> [name] — test seam, set by nothing but tests/test_aitasks_home.sh.
home_hook() {
    [[ -n "${AIT_HOME_TEST_HOOK:-}" ]] || return 0
    "$AIT_HOME_TEST_HOOK" "$@" || true
}

home_release_lock() {
    [[ -n "$HOME_LOCK_TOKEN" ]] || return 0
    stale_lock_release "$AITASKS_HOME_LOCK" "$HOME_LOCK_TOKEN" ||
        warn "home lock $AITASKS_HOME_LOCK was not released cleanly"
    HOME_LOCK_TOKEN=""
}

# home_locate <i> — where HOME_MOVE[i] is now, matched by its recorded
# identity: legacy | root | nested (a forward mv nested it inside a raced-in
# destination directory) | legacy-nested (a rollback mv nested it inside a
# raced-in competitor at the legacy path) | lost.
home_locate() {
    local n="${HOME_MOVE[$1]}" want="${HOME_IDS[$1]}" p
    for p in "legacy:$LEGACY_ROOT/$n" "root:$AITASKS_HOME/$n" "nested:$AITASKS_HOME/$n/$n" \
             "legacy-nested:$LEGACY_ROOT/$n/$n"; do
        # Through a legacy root that is now a symlink, a path under it is
        # just another name for the entry's location elsewhere — never "back".
        if [[ "$p" == legacy* && -L "$LEGACY_ROOT" ]]; then continue; fi
        if home_present "${p#*:}" && [[ "$(home_lstat_id "${p#*:}" 2>/dev/null)" == "$want" ]]; then
            printf '%s\n' "${p%%:*}"
            return 0
        fi
    done
    echo lost
}

# home_rollback <reason> — undo every move, derived from where each entry IS
# (by identity), not from bookkeeping, so a signal landing between a mv and its
# record is still covered. A competing entry at the legacy path is never
# overwritten: that entry is reported stranded instead.
# Prints the outcome; returns 1 (fully restored) or 2 (something stranded).
home_rollback() {
    local reason="$1" i n where src restored=0 stranded=() s
    # Recovery itself must not be cut short by a further signal.
    trap '' INT TERM HUP
    if ! home_present "$LEGACY_ROOT"; then
        mkdir "$LEGACY_ROOT" 2>/dev/null || true
    fi
    for (( i = ${#HOME_MOVE[@]} - 1; i >= 0; i-- )); do
        n="${HOME_MOVE[$i]}"
        where="$(home_locate "$i")"
        case "$where" in
            legacy)        continue ;;
            root)          src="$AITASKS_HOME/$n" ;;
            nested)        src="$AITASKS_HOME/$n/$n" ;;
            legacy-nested) stranded+=("$n|$LEGACY_ROOT/$n/$n"); continue ;;
            *)             stranded+=("$n|?"); continue ;;
        esac
        if [[ -L "$LEGACY_ROOT" || ! -d "$LEGACY_ROOT" ]] || home_present "$LEGACY_ROOT/$n"; then
            stranded+=("$n|$src")
            continue
        fi
        home_hook pre-restore "$n"
        mv -n -- "$src" "$LEGACY_ROOT/$n" 2>/dev/null || true
        # Report where it actually IS now — a competitor raced in after the
        # check above makes mv nest it inside that competitor.
        case "$(home_locate "$i")" in
            legacy)        restored=$((restored + 1)) ;;
            root)          stranded+=("$n|$AITASKS_HOME/$n") ;;
            nested)        stranded+=("$n|$AITASKS_HOME/$n/$n") ;;
            legacy-nested) stranded+=("$n|$LEGACY_ROOT/$n/$n") ;;
            *)             stranded+=("$n|?") ;;
        esac
    done
    echo "HOME_SKIPPED:$reason"
    if [[ ${#stranded[@]} -eq 0 ]]; then
        echo "HOME_ROLLED_BACK:$restored"
        return 1
    fi
    local names=()
    for s in "${stranded[@]}"; do names+=("${s%%|*}"); done
    echo "HOME_FAILED:rollback|$(home_csv "${names[@]}")"
    for s in "${stranded[@]}"; do
        echo "HOME_STRANDED:${s%%|*}|${s#*|}|$LEGACY_ROOT/${s%%|*}"
    done
    # The legacy root itself may be what blocks the way back (something put a
    # file or a foreign link there): set THAT aside and recreate the directory
    # first — the per-entry steps assume a directory to move into.
    if [[ -L "$LEGACY_ROOT" || ! -d "$LEGACY_ROOT" ]]; then
        home_restore_root_steps
    else
        for s in "${stranded[@]}"; do
            home_restore_steps "${s%%|*}" "${s#*|}"
        done
    fi
    return 2
}

# home_restore_steps <name> <current path or ?> — the manual restore for one
# stranded entry, as runnable HOME_RESTORE:<name>|<command> lines. When a
# competitor occupies the legacy path, a plain `mv <current> <legacy>` would
# nest the original INSIDE it, so the competitor is set aside first (preserved,
# never deleted; the aside path does not exist when this is printed), then the
# original takes its place. When the legacy path is free — the move back itself
# failed — the restore is that one move.
home_restore_steps() {
    local n="$1" cur="$2" legacy="$LEGACY_ROOT/$1" aside
    if [[ "$cur" == "?" ]]; then
        warn "$n was moved and then could not be located by identity; inspect $AITASKS_HOME and $LEGACY_ROOT by hand."
        return 0
    fi
    if ! home_present "$legacy"; then
        # Nothing is in the way: the move back itself failed (e.g. the legacy
        # directory was not writable). One step, once that is fixed.
        printf 'HOME_RESTORE:%s|mv -- %q %q\n' "$(home_show "$n")" "$cur" "$legacy"
        warn "$n could not be moved back to $legacy (the move failed — check that $LEGACY_ROOT is writable). Once it is, run the HOME_RESTORE:$n command above."
        return 0
    fi
    aside="$(home_aside "$legacy")"
    # Setting the competitor aside moves anything nested inside it too.
    if [[ "$cur" == "$legacy/"* ]]; then cur="$aside/${cur#"$legacy"/}"; fi
    printf 'HOME_RESTORE:%s|mv -- %q %q\n' "$(home_show "$n")" "$legacy" "$aside"
    printf 'HOME_RESTORE:%s|mv -- %q %q\n' "$(home_show "$n")" "$cur" "$legacy"
    warn "$n could not be moved back: something else now occupies $legacy. Run the two HOME_RESTORE:$n commands above in order — the first sets that competing entry aside at $aside (kept, inspect it), the second restores the original."
}

# home_aside <path> — a sibling name for setting <path> aside that does not
# exist right now: <path>.competing, then <path>.competing.2, …
home_aside() {
    local aside="$1.competing" k=1
    while home_present "$aside"; do k=$((k + 1)); aside="$1.competing.$k"; done
    printf '%s\n' "$aside"
}

# home_restore_root_steps — the legacy root is not a directory. When something
# occupies it (a file, a foreign link), one step sets that obstruction aside
# (kept); when it is simply absent (the rollback's own mkdir failed) there is
# nothing to set aside. Then one step recreates the directory and each stranded
# entry moves back into it. All as HOME_RESTORE: lines, run in order; `.` names
# the legacy root itself.
home_restore_root_steps() {
    local aside="" s n cur
    if home_present "$LEGACY_ROOT"; then
        aside="$(home_aside "$LEGACY_ROOT")"
        printf 'HOME_RESTORE:.|mv -- %q %q\n' "$LEGACY_ROOT" "$aside"
    fi
    printf 'HOME_RESTORE:.|mkdir -- %q\n' "$LEGACY_ROOT"
    for s in "${stranded[@]}"; do
        n="${s%%|*}"; cur="${s#*|}"
        if [[ "$cur" == "?" ]]; then
            warn "$n was moved and then could not be located by identity; inspect $AITASKS_HOME by hand."
            continue
        fi
        printf 'HOME_RESTORE:%s|mv -- %q %q\n' "$(home_show "$n")" "$cur" "$LEGACY_ROOT/$n"
    done
    if [[ -n "$aside" ]]; then
        warn "$LEGACY_ROOT is no longer a directory (something replaced it), so the entries could not be moved back. Run the HOME_RESTORE: commands above in order — the first sets that obstruction aside at $aside (kept, inspect it), the second recreates the directory, the rest restore each entry."
    else
        warn "$LEGACY_ROOT is missing and could not be recreated (check that its parent is writable), so the entries could not be moved back. Once it is writable, run the HOME_RESTORE: commands above in order — the first recreates the directory, the rest restore each entry."
    fi
}

# home_on_signal <SIG> — a catchable interruption. Before the link is verified
# the migration is incomplete and is cancelled (rolled back); after it, the
# migration is complete and nothing is undone. SIGKILL is not catchable.
home_on_signal() {
    local sig="$1" code=1
    trap '' INT TERM HUP
    case "$sig" in INT) code=130 ;; TERM) code=143 ;; HUP) code=129 ;; esac
    # A signal landing after ln but before the phase advanced still finds a
    # completed layout: recognise it rather than "roll back" through the link.
    if [[ "$HOME_PHASE" == removed && -L "$LEGACY_ROOT" &&
          "$(readlink "$LEGACY_ROOT" 2>/dev/null)" == "$AITASKS_HOME" ]]; then
        HOME_PHASE=linked
    fi
    case "$HOME_PHASE" in
        moving|removed) home_rollback "interrupted:$sig" || true ;;
        linked)         echo "HOME_MIGRATED:${#HOME_MOVE[@]}" ;;
        finished)       ;;
        *)              echo "HOME_SKIPPED:interrupted:$sig" ;;
    esac
    exit "$code"
}

# home_skip_preflight — print the preflight verdict when it is not `ready`;
# returns the exit status to use (0 nothing to do, 1 refused).
home_skip_preflight() {
    local reason
    for reason in "${HOME_REASONS[@]}"; do echo "HOME_SKIPPED:$reason"; done
    [[ "$HOME_STATE" == refuse ]] && return 1
    return 0
}

home_migrate() {
    local i n id rc=0 left=() e link

    # Unlocked preflight: nothing to do or a refusal creates nothing at all.
    home_preflight
    if [[ "$HOME_STATE" != ready ]]; then
        home_skip_preflight || exit 1
        exit 0
    fi

    if ! mkdir -p "$AITASKS_HOME" 2>/dev/null; then
        echo "HOME_SKIPPED:lock-unavailable"
        exit 1
    fi
    trap home_release_lock EXIT
    if ! stale_lock_acquire "$AITASKS_HOME_LOCK" 3 0.1 "framework home migration"; then
        if home_present "$AITASKS_HOME_LOCK"; then
            echo "HOME_SKIPPED:busy"
            info "Another 'ait engine home --migrate' holds $AITASKS_HOME_LOCK; nothing was moved." >&2
        else
            echo "HOME_SKIPPED:lock-unavailable"
        fi
        exit 1
    fi
    HOME_LOCK_TOKEN="$STALE_LOCK_TOKEN"
    HOME_PHASE=locked
    trap 'home_on_signal INT' INT
    trap 'home_on_signal TERM' TERM
    trap 'home_on_signal HUP' HUP

    # Re-checked under the lock: the world may have moved since.
    home_preflight
    if [[ "$HOME_STATE" != ready ]]; then
        home_skip_preflight || exit 1
        exit 0
    fi
    HOME_IDS=()
    for n in ${HOME_MOVE[@]+"${HOME_MOVE[@]}"}; do
        if ! id="$(home_lstat_id "$LEGACY_ROOT/$n")"; then
            echo "HOME_SKIPPED:move-failed:$n"
            exit 1
        fi
        HOME_IDS+=("$id")
    done

    HOME_PHASE=moving
    for i in "${!HOME_MOVE[@]}"; do
        n="${HOME_MOVE[$i]}"
        if home_present "$AITASKS_HOME/$n"; then
            home_rollback "destination-exists:$n" || rc=$?
            exit "$rc"
        fi
        home_hook pre-mv "$n"
        mv -n -- "$LEGACY_ROOT/$n" "$AITASKS_HOME/$n" 2>/dev/null || true
        case "$(home_locate "$i")" in
            root)   ;;
            nested) home_rollback "destination-exists:$n" || rc=$?; exit "$rc" ;;
            *)      home_rollback "move-failed:$n" || rc=$?; exit "$rc" ;;
        esac
    done
    home_hook post-moves

    if ! rmdir "$LEGACY_ROOT" 2>/dev/null; then
        while IFS= read -r -d '' e; do [[ -n "$e" ]] && left+=("$(home_show "$e")"); done < <(home_entries)
        home_rollback "legacy-root-not-empty:$(home_csv ${left[@]+"${left[@]}"})" || rc=$?
        exit "$rc"
    fi
    HOME_PHASE=removed
    home_hook pre-link

    ln -s "$AITASKS_HOME" "$LEGACY_ROOT" 2>/dev/null || true
    home_hook post-ln
    if [[ ! -L "$LEGACY_ROOT" || "$(readlink "$LEGACY_ROOT" 2>/dev/null)" != "$AITASKS_HOME" ]]; then
        # Something recreated the legacy root meanwhile, so ln put its link
        # INSIDE that directory. Remove only that link, then cancel.
        link="$LEGACY_ROOT/${AITASKS_HOME##*/}"
        if [[ -d "$LEGACY_ROOT" && ! -L "$LEGACY_ROOT" && -L "$link" &&
              "$(readlink "$link" 2>/dev/null)" == "$AITASKS_HOME" ]]; then
            rm -f -- "$link" 2>/dev/null || true
        fi
        home_rollback symlink-failed || rc=$?
        exit "$rc"
    fi
    HOME_PHASE=linked
    home_hook post-link

    echo "HOME_MIGRATED:${#HOME_MOVE[@]}"
    HOME_PHASE=finished
    success "Moved ${#HOME_MOVE[@]} entr$([[ ${#HOME_MOVE[@]} -eq 1 ]] && echo y || echo ies) into $AITASKS_HOME; $LEGACY_ROOT now links there." >&2
    exit 0
}

cmd_home() {
    # One spelling of the root for the whole verb: trailing slashes would make
    # basename-derived names (the stray-link cleanup) empty.
    while [[ "$AITASKS_HOME" == */ && "$AITASKS_HOME" != / ]]; do AITASKS_HOME="${AITASKS_HOME%/}"; done
    case "$#:${1:-}" in
        0:)          home_report ;;
        1:--migrate) home_migrate ;;
        *)           usage_line; exit 64 ;;
    esac
}

verb="${1:-}"
[[ $# -gt 0 ]] && shift
case "$verb" in
    build) cmd_build "$@" ;;
    test)  cmd_test "$@" ;;
    cross) cmd_cross "$@" ;;
    prune) cmd_prune "$@" ;;
    home)  cmd_home "$@" ;;
    -h|--help)
        sed -n '4,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
        ;;
    "")
        usage_line
        exit 64 ;;
    *)
        echo "UNKNOWN_VERB:$verb" >&2
        usage_line
        exit 64 ;;
esac
