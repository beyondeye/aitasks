#!/usr/bin/env bash
# aitask_migrate_archives.sh - Convert old tar.gz archives to tar.zst
# and rebucket legacy root archives into numbered tar.zst bundles.

if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
    return 0
fi

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/archive_utils.sh"

TASK_ARCHIVED_DIR="${TASK_DIR:-aitasks}/archived"
PLAN_ARCHIVED_DIR="${PLAN_DIR:-aiplans}/archived"

DRY_RUN=false
DELETE_OLD=false
VERBOSE=false

FOUND=0
CONVERTED=0
SKIPPED=0
FAILED=0

usage() {
    cat <<'EOF'
Usage: aitask_migrate_archives.sh [OPTIONS]

Convert numbered old*.tar.gz archives to old*.tar.zst, and rebucket legacy
old.tar.gz archives into numbered tar.zst bundles.

Options:
  --dry-run       Show what would be converted without changing files
  --delete-old    Delete old .tar.gz sources after successful migration
  --verbose       Show detailed progress output
  -h, --help      Show this help message
EOF
}

verbose() {
    if $VERBOSE; then
        info "$1"
    fi
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --delete-old)
                DELETE_OLD=true
                shift
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                die "Unknown argument: $1"
                ;;
        esac
    done
}

normalize_entry_path() {
    local entry="$1"
    entry="${entry#./}"
    echo "$entry"
}

path_parent_id() {
    local path
    path=$(normalize_entry_path "$1")
    local prefix="$2"
    if [[ "$path" =~ ^${prefix}([0-9]+) ]]; then
        echo "${BASH_REMATCH[1]}"
        return 0
    fi
    return 1
}

append_sorted_matches() {
    local search_root="$1"
    local pattern="$2"
    local -n target_ref="$3"
    local path
    while IFS= read -r path; do
        [[ -n "$path" ]] || continue
        target_ref+=("$path")
    done < <(find "$search_root" -type f -path "$pattern" 2>/dev/null | sort)
}

delete_source_if_requested() {
    local source="$1"
    if $DELETE_OLD && ! $DRY_RUN && [[ -f "$source" ]]; then
        rm -f "$source"
        verbose "Deleted source archive: $source"
    fi
}

convert_numbered_archive() {
    local source="$1"
    local target="${source%.tar.gz}.tar.zst"
    local tmp_root=""

    FOUND=$((FOUND + 1))

    if [[ -f "$target" ]]; then
        SKIPPED=$((SKIPPED + 1))
        info "Skipping numbered archive (target exists): $source"
        delete_source_if_requested "$source"
        return 0
    fi

    if $DRY_RUN; then
        info "Would convert numbered archive: $source -> $target"
        return 0
    fi

    tmp_root=$(mktemp -d "${TMPDIR:-/tmp}/ait_migrate_numbered_XXXXXX")
    mkdir -p "$tmp_root/extract"

    if ! tar -xzf "$source" -C "$tmp_root/extract"; then
        warn "Failed to extract numbered archive: $source"
        FAILED=$((FAILED + 1))
        rm -rf "$tmp_root"
        return 0
    fi

    if ! tar -cf - -C "$tmp_root/extract" . | zstd -q -f -o "$tmp_root/archive.tar.zst"; then
        warn "Failed to recompress numbered archive: $source"
        FAILED=$((FAILED + 1))
        rm -rf "$tmp_root"
        return 0
    fi

    if ! zstd -dc "$tmp_root/archive.tar.zst" | tar -tf - > /dev/null; then
        warn "Verification failed for numbered archive: $source"
        FAILED=$((FAILED + 1))
        rm -rf "$tmp_root"
        return 0
    fi

    mkdir -p "$(dirname "$target")"
    mv "$tmp_root/archive.tar.zst" "$target"
    rm -rf "$tmp_root"

    CONVERTED=$((CONVERTED + 1))
    info "Converted numbered archive: $source -> $target"
    delete_source_if_requested "$source"
}

legacy_targets_from_archive() {
    local source="$1"
    local archived_dir="$2"
    local prefix="$3"
    local -A seen=()
    local entry parent_id target

    while IFS= read -r entry; do
        entry=$(normalize_entry_path "$entry")
        [[ -n "$entry" ]] || continue
        [[ "$entry" == */ ]] && continue
        [[ "$entry" == *.md ]] || continue
        if ! parent_id=$(path_parent_id "$entry" "$prefix"); then
            warn "Could not determine parent id for legacy entry: $source:$entry"
            return 1
        fi
        target=$(archive_path_for_id "$parent_id" "$archived_dir")
        seen["$target"]=1
    done < <(tar -tzf "$source" 2>/dev/null)

    if [[ ${#seen[@]} -eq 0 ]]; then
        warn "Legacy archive has no markdown files to migrate: $source"
        return 1
    fi

    printf '%s\n' "${!seen[@]}" | sort
}

copy_tree_contents() {
    local from_dir="$1"
    local to_dir="$2"
    if [[ -d "$from_dir" ]]; then
        mkdir -p "$to_dir"
        cp -R "$from_dir"/. "$to_dir"/
    fi
}

rebucket_legacy_archive() {
    local source="$1"
    local archived_dir="$2"
    local prefix="$3"
    local tmp_root=""
    local all_success=true
    local had_files=false

    FOUND=$((FOUND + 1))

    if $DRY_RUN; then
        local targets=""
        if targets=$(legacy_targets_from_archive "$source" "$archived_dir" "$prefix"); then
            info "Would rebucket legacy archive: $source"
            while IFS= read -r target; do
                [[ -n "$target" ]] || continue
                info "  -> $target"
            done <<< "$targets"
        else
            FAILED=$((FAILED + 1))
        fi
        return 0
    fi

    tmp_root=$(mktemp -d "${TMPDIR:-/tmp}/ait_migrate_legacy_XXXXXX")
    mkdir -p "$tmp_root/extract" "$tmp_root/staged"

    if ! tar -xzf "$source" -C "$tmp_root/extract"; then
        warn "Failed to extract legacy archive: $source"
        FAILED=$((FAILED + 1))
        rm -rf "$tmp_root"
        return 0
    fi

    declare -A bundle_stage_dirs=()
    declare -A bundle_targets=()
    local file rel_path parent_id bundle bundle_stage_dir target

    while IFS= read -r file; do
        [[ -f "$file" ]] || continue
        rel_path="${file#"$tmp_root/extract"/}"
        rel_path="${rel_path#/}"
        [[ "$rel_path" == *.md ]] || continue
        had_files=true
        if ! parent_id=$(path_parent_id "$rel_path" "$prefix"); then
            warn "Could not determine parent id for legacy entry: $source:$rel_path"
            all_success=false
            continue
        fi
        bundle=$(archive_bundle "$parent_id")
        target=$(archive_path_for_id "$parent_id" "$archived_dir")
        bundle_stage_dir="${bundle_stage_dirs[$bundle]:-$tmp_root/staged/$bundle}"
        bundle_stage_dirs["$bundle"]="$bundle_stage_dir"
        bundle_targets["$bundle"]="$target"
        mkdir -p "$bundle_stage_dir/$(dirname "$rel_path")"
        cp "$file" "$bundle_stage_dir/$rel_path"
    done < <(find "$tmp_root/extract" -type f | sort)

    if [[ "$had_files" == false ]]; then
        warn "Legacy archive has no markdown files to migrate: $source"
        FAILED=$((FAILED + 1))
        rm -rf "$tmp_root"
        return 0
    fi

    if [[ "$all_success" == false ]]; then
        FAILED=$((FAILED + 1))
        rm -rf "$tmp_root"
        return 0
    fi

    local bundle_key existing_zst existing_gz build_dir archive_tmp target_count=0
    while IFS= read -r bundle_key; do
        [[ -n "$bundle_key" ]] || continue
        target="${bundle_targets[$bundle_key]}"
        existing_zst="$target"
        existing_gz="${target%.tar.zst}.tar.gz"
        build_dir="$tmp_root/build_$bundle_key"
        archive_tmp="$tmp_root/archive_$bundle_key.tar.zst"
        mkdir -p "$build_dir"

        if [[ -f "$existing_zst" ]]; then
            if ! _archive_extract_all "$existing_zst" "$build_dir"; then
                warn "Failed to extract existing target bundle: $existing_zst"
                all_success=false
                continue
            fi
        elif [[ -f "$existing_gz" ]]; then
            warn "Cannot rebucket legacy archive while numbered tar.gz still exists: $existing_gz"
            all_success=false
            continue
        fi

        copy_tree_contents "${bundle_stage_dirs[$bundle_key]}" "$build_dir"

        if ! tar -cf - -C "$build_dir" . | zstd -q -f -o "$archive_tmp"; then
            warn "Failed to create rebucketed archive: $target"
            all_success=false
            continue
        fi

        if ! zstd -dc "$archive_tmp" | tar -tf - > /dev/null; then
            warn "Verification failed for rebucketed archive: $target"
            rm -f "$archive_tmp"
            all_success=false
            continue
        fi

        mkdir -p "$(dirname "$target")"
        mv "$archive_tmp" "$target"
        target_count=$((target_count + 1))
    done < <(printf '%s\n' "${!bundle_targets[@]}" | sort -n)

    if [[ "$all_success" == false ]]; then
        FAILED=$((FAILED + 1))
        rm -rf "$tmp_root"
        return 0
    fi

    CONVERTED=$((CONVERTED + 1))
    info "Rebucketed legacy archive: $source -> $target_count numbered bundle(s)"
    delete_source_if_requested "$source"
    rm -rf "$tmp_root"
}

print_summary() {
    echo ""
    info "Migration summary:"
    echo "  found: $FOUND"
    echo "  converted: $CONVERTED"
    echo "  skipped: $SKIPPED"
    echo "  failed: $FAILED"
}

main() {
    parse_args "$@"

    local -a numbered_sources=()
    append_sorted_matches "$TASK_ARCHIVED_DIR" "*/_b*/old*.tar.gz" numbered_sources
    append_sorted_matches "$PLAN_ARCHIVED_DIR" "*/_b*/old*.tar.gz" numbered_sources

    local source
    for source in "${numbered_sources[@]}"; do
        convert_numbered_archive "$source"
    done

    local -a legacy_sources=()
    [[ -f "$TASK_ARCHIVED_DIR/old.tar.gz" ]] && legacy_sources+=("$TASK_ARCHIVED_DIR/old.tar.gz|$TASK_ARCHIVED_DIR|t")
    [[ -f "$PLAN_ARCHIVED_DIR/old.tar.gz" ]] && legacy_sources+=("$PLAN_ARCHIVED_DIR/old.tar.gz|$PLAN_ARCHIVED_DIR|p")

    local legacy_spec legacy_path archived_dir prefix
    for legacy_spec in "${legacy_sources[@]}"; do
        IFS='|' read -r legacy_path archived_dir prefix <<< "$legacy_spec"
        rebucket_legacy_archive "$legacy_path" "$archived_dir" "$prefix"
    done

    if [[ ${#numbered_sources[@]} -eq 0 && ${#legacy_sources[@]} -eq 0 ]]; then
        info "No tar.gz archives found to migrate."
    fi

    print_summary

    if [[ "$FAILED" -gt 0 ]]; then
        exit 1
    fi
}

main "$@"
