#!/usr/bin/env bash
set -euo pipefail

# aitask_explain_cleanup.sh - Remove stale aiexplain run directories
# Keeps only the newest run per source directory key.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

AIEXPLAINS_DIR="aiexplains"
CODEBROWSER_SUBDIR="codebrowser"
TARGET_DIR=""
MODE="target"  # target | all
DRY_RUN=false
QUIET=false

# --- Functions ---

# Extract key and timestamp from directory name
# Returns "key|timestamp" or returns 1 if unrecognized
extract_key_and_timestamp() {
    local name="$1"

    # Pattern: <key>__<YYYYMMDD_HHMMSS>
    if [[ "$name" =~ ^(.+)__([0-9]{8}_[0-9]{6})$ ]]; then
        echo "${BASH_REMATCH[1]}|${BASH_REMATCH[2]}"
        return 0
    fi

    # Bare timestamp: <YYYYMMDD_HHMMSS> (15 chars)
    if [[ "$name" =~ ^([0-9]{8}_[0-9]{6})$ ]]; then
        echo "_bare_timestamp_|${BASH_REMATCH[1]}"
        return 0
    fi

    return 1
}

# Clean up stale directories in a given target directory
# Sets _cleanup_result with the number of directories removed
cleanup_directory() {
    local target="$1"
    _cleanup_result=0

    if [[ ! -d "$target" ]]; then
        [[ "$QUIET" == false ]] && info "Directory not found: $target"
        return
    fi

    local base
    base=$(realpath "$AIEXPLAINS_DIR" 2>/dev/null || echo "$AIEXPLAINS_DIR")

    # Associative arrays: key -> newest timestamp, key -> newest dir path
    declare -A newest_ts
    declare -A newest_dir
    # key -> list of older dirs (newline-separated)
    declare -A older_dirs

    local skipped=0

    for entry in "$target"/*/; do
        [[ -d "$entry" ]] || continue
        local dirname
        dirname=$(basename "$entry")

        local parsed
        if ! parsed=$(extract_key_and_timestamp "$dirname"); then
            [[ "$QUIET" == false ]] && warn "Skipping unrecognized directory: $dirname"
            skipped=$((skipped + 1))
            continue
        fi

        local key ts
        key="${parsed%%|*}"
        ts="${parsed##*|}"

        # Safety: verify directory is under aiexplains/
        local canonical
        canonical=$(realpath "$entry" 2>/dev/null || echo "$entry")
        if [[ "$canonical" != "$base"/* ]]; then
            warn "Refusing to process directory outside ${AIEXPLAINS_DIR}/: $entry"
            continue
        fi

        # Safety: verify presence of files.txt or raw_data.txt
        if [[ ! -f "${entry}files.txt" && ! -f "${entry}raw_data.txt" ]]; then
            [[ "$QUIET" == false ]] && warn "Skipping $dirname (no files.txt or raw_data.txt)"
            skipped=$((skipped + 1))
            continue
        fi

        if [[ -z "${newest_ts[$key]+x}" ]] || [[ "$ts" > "${newest_ts[$key]}" ]]; then
            # Current entry is newer — demote the previous newest
            if [[ -n "${newest_ts[$key]+x}" ]]; then
                if [[ -n "${older_dirs[$key]+x}" ]]; then
                    older_dirs[$key]="${older_dirs[$key]}"$'\n'"${newest_dir[$key]}"
                else
                    older_dirs[$key]="${newest_dir[$key]}"
                fi
            fi
            newest_ts[$key]="$ts"
            newest_dir[$key]="$entry"
        else
            # Current entry is older
            if [[ -n "${older_dirs[$key]+x}" ]]; then
                older_dirs[$key]="${older_dirs[$key]}"$'\n'"$entry"
            else
                older_dirs[$key]="$entry"
            fi
        fi
    done

    local cleaned=0

    for key in "${!older_dirs[@]}"; do
        while IFS= read -r dir_to_remove; do
            [[ -z "$dir_to_remove" ]] && continue
            if [[ "$DRY_RUN" == true ]]; then
                echo "Would remove: $dir_to_remove (key: $key)"
            else
                rm -rf "$dir_to_remove"
                [[ "$QUIET" == false ]] && info "Removed: $dir_to_remove (key: $key, kept: $(basename "${newest_dir[$key]}"))"
            fi
            cleaned=$((cleaned + 1))
        done <<< "${older_dirs[$key]}"
    done

    [[ "$QUIET" == false && $skipped -gt 0 ]] && info "Skipped $skipped unrecognized/invalid directories in $target"

    _cleanup_result=$cleaned
}

# --- Argument Parsing ---

show_help() {
    cat << 'EOF'
Usage: aitask_explain_cleanup.sh [OPTIONS]

Remove stale aiexplain run directories, keeping only the newest per source directory key.

Options:
  --target DIR    Clean a specific directory (default: aiexplains/)
  --all           Clean both aiexplains/ (non-codebrowser) and aiexplains/codebrowser/
  --dry-run       Show what would be removed without deleting
  --quiet         Suppress informational output
  --help, -h      Show help

Examples:
  # Dry run on all directories
  ./aiscripts/aitask_explain_cleanup.sh --dry-run --all

  # Clean only codebrowser runs
  ./aiscripts/aitask_explain_cleanup.sh --target aiexplains/codebrowser

  # Clean everything (both top-level and codebrowser)
  ./aiscripts/aitask_explain_cleanup.sh --all

  # Quiet mode for automation
  ./aiscripts/aitask_explain_cleanup.sh --all --quiet
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --target)
                MODE="target"
                [[ $# -ge 2 ]] || die "--target requires a directory argument"
                TARGET_DIR="$2"
                shift 2
                ;;
            --all)
                MODE="all"
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --quiet)
                QUIET=true
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                die "Unknown option: $1. Use --help for usage."
                ;;
        esac
    done

    # Default target
    if [[ "$MODE" == "target" && -z "$TARGET_DIR" ]]; then
        TARGET_DIR="$AIEXPLAINS_DIR"
    fi
}

main() {
    parse_args "$@"

    local total_cleaned=0

    if [[ "$MODE" == "all" ]]; then
        [[ "$QUIET" == false ]] && info "Cleaning ${AIEXPLAINS_DIR}/ (excluding ${CODEBROWSER_SUBDIR}/)..."

        # For top-level: create a temporary view excluding codebrowser/
        # We process aiexplains/ but skip the codebrowser subdirectory
        if [[ -d "$AIEXPLAINS_DIR" ]]; then
            local base
            base=$(realpath "$AIEXPLAINS_DIR" 2>/dev/null || echo "$AIEXPLAINS_DIR")

            declare -A newest_ts_top
            declare -A newest_dir_top
            declare -A older_dirs_top
            local skipped_top=0

            for entry in "$AIEXPLAINS_DIR"/*/; do
                [[ -d "$entry" ]] || continue
                local dirname
                dirname=$(basename "$entry")

                # Skip codebrowser subdirectory
                [[ "$dirname" == "$CODEBROWSER_SUBDIR" ]] && continue

                local parsed
                if ! parsed=$(extract_key_and_timestamp "$dirname"); then
                    [[ "$QUIET" == false ]] && warn "Skipping unrecognized directory: $dirname"
                    skipped_top=$((skipped_top + 1))
                    continue
                fi

                local key ts
                key="${parsed%%|*}"
                ts="${parsed##*|}"

                local canonical
                canonical=$(realpath "$entry" 2>/dev/null || echo "$entry")
                if [[ "$canonical" != "$base"/* ]]; then
                    warn "Refusing to process directory outside ${AIEXPLAINS_DIR}/: $entry"
                    continue
                fi

                if [[ ! -f "${entry}files.txt" && ! -f "${entry}raw_data.txt" ]]; then
                    [[ "$QUIET" == false ]] && warn "Skipping $dirname (no files.txt or raw_data.txt)"
                    skipped_top=$((skipped_top + 1))
                    continue
                fi

                if [[ -z "${newest_ts_top[$key]+x}" ]] || [[ "$ts" > "${newest_ts_top[$key]}" ]]; then
                    if [[ -n "${newest_ts_top[$key]+x}" ]]; then
                        if [[ -n "${older_dirs_top[$key]+x}" ]]; then
                            older_dirs_top[$key]="${older_dirs_top[$key]}"$'\n'"${newest_dir_top[$key]}"
                        else
                            older_dirs_top[$key]="${newest_dir_top[$key]}"
                        fi
                    fi
                    newest_ts_top[$key]="$ts"
                    newest_dir_top[$key]="$entry"
                else
                    if [[ -n "${older_dirs_top[$key]+x}" ]]; then
                        older_dirs_top[$key]="${older_dirs_top[$key]}"$'\n'"$entry"
                    else
                        older_dirs_top[$key]="$entry"
                    fi
                fi
            done

            for key in "${!older_dirs_top[@]}"; do
                while IFS= read -r dir_to_remove; do
                    [[ -z "$dir_to_remove" ]] && continue
                    if [[ "$DRY_RUN" == true ]]; then
                        echo "Would remove: $dir_to_remove (key: $key)"
                    else
                        rm -rf "$dir_to_remove"
                        [[ "$QUIET" == false ]] && info "Removed: $dir_to_remove (key: $key, kept: $(basename "${newest_dir_top[$key]}"))"
                    fi
                    total_cleaned=$((total_cleaned + 1))
                done <<< "${older_dirs_top[$key]}"
            done

            [[ "$QUIET" == false && $skipped_top -gt 0 ]] && info "Skipped $skipped_top unrecognized/invalid directories in $AIEXPLAINS_DIR/"
        fi

        [[ "$QUIET" == false ]] && info "Cleaning ${AIEXPLAINS_DIR}/${CODEBROWSER_SUBDIR}/..."
        cleanup_directory "${AIEXPLAINS_DIR}/${CODEBROWSER_SUBDIR}"
        total_cleaned=$((total_cleaned + _cleanup_result))
    else
        cleanup_directory "$TARGET_DIR"
        total_cleaned=$((total_cleaned + _cleanup_result))
    fi

    if [[ "$DRY_RUN" == true ]]; then
        [[ "$QUIET" == false ]] && info "Dry run complete. $total_cleaned stale directory(ies) would be removed."
    else
        [[ "$QUIET" == false ]] && info "Cleanup complete. Removed $total_cleaned stale directory(ies)."
    fi

    echo "CLEANED: $total_cleaned"
}

main "$@"
