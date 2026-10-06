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
#
# build / test / cross need the Go source, which ships only in the aitasks
# framework repository. prune works in any project.
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
    echo "USAGE:ait engine build | test [go test args] | cross [build.sh args] | prune [--dry-run] [--force]" >&2
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

verb="${1:-}"
[[ $# -gt 0 ]] && shift
case "$verb" in
    build) cmd_build "$@" ;;
    test)  cmd_test "$@" ;;
    cross) cmd_cross "$@" ;;
    prune) cmd_prune "$@" ;;
    # home [--migrate] — M1.6 (t1852_6) adds this arm (a named extension).
    -h|--help)
        sed -n '4,18p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
        ;;
    "")
        usage_line
        exit 64 ;;
    *)
        echo "UNKNOWN_VERB:$verb" >&2
        usage_line
        exit 64 ;;
esac
