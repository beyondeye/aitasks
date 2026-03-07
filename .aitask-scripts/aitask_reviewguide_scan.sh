#!/usr/bin/env bash
# aitask_reviewguide_scan.sh - Scan reviewguide files for metadata and similarity
# Scans reviewguide files for metadata completeness and finds similar files.
# Used by the classify skill and merge skill, also useful standalone.
#
# Usage:
#   aitask_reviewguide_scan.sh [OPTIONS]
#
# Options:
#   --missing-meta         Only show files missing reviewlabels, reviewtype, or environment (non-general)
#   --environment ENV      Filter to files matching this environment (or "general" for universal)
#   --reviewguides-dir DIR  Path to reviewguides directory (default: aireviewguides)
#   --find-similar         For each file, find the most similar other file by reviewlabel overlap
#   --compare FILE         Compare one file against all others, output similarity scores
#
# Default output format (pipe-delimited, one per line):
#   <relative_path>|<name>|<reviewtype_or_MISSING>|<reviewlabels_csv_or_MISSING>|<environment_csv_or_universal>
#
# --find-similar output (appends a 6th field):
#   <relative_path>|<name>|<reviewtype>|<reviewlabels_csv>|<env>|<most_similar_path>:<overlap_count>
#
# --compare FILE output:
#   <relative_path>|<name>|<similarity_score>|<shared_labels_csv>|<type_match:yes/no>|<env_overlap:yes/no>
#   Score = (shared_labels_count * 2) + (type_match ? 3 : 0) + (env_overlap ? 2 : 0)
#   Sorted descending by score. Only files with score > 0.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

# --- Defaults ---
REVIEWGUIDES_DIR="aireviewguides"
MODE="default"
ENVIRONMENT_FILTER=""
COMPARE_FILE=""

# --- Argument parsing ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --missing-meta)
            MODE="missing-meta"
            shift
            ;;
        --environment)
            ENVIRONMENT_FILTER="${2:?--environment requires a value}"
            shift 2
            ;;
        --reviewguides-dir)
            REVIEWGUIDES_DIR="${2:?--reviewguides-dir requires a path}"
            shift 2
            ;;
        --find-similar)
            MODE="find-similar"
            shift
            ;;
        --compare)
            MODE="compare"
            COMPARE_FILE="${2:?--compare requires a file path}"
            shift 2
            ;;
        --help|-h)
            echo "Usage: aitask_reviewguide_scan.sh [--missing-meta] [--environment ENV] [--reviewguides-dir DIR] [--find-similar] [--compare FILE]"
            echo ""
            echo "Scan reviewguide files for metadata completeness and find similar files."
            echo ""
            echo "Options:"
            echo "  --missing-meta         Only show files missing reviewlabels, reviewtype, or environment (non-general)"
            echo "  --environment ENV      Filter to files matching environment (or 'general' for universal)"
            echo "  --reviewguides-dir DIR  Review guides directory (default: aireviewguides)"
            echo "  --find-similar         For each file, find the most similar other file"
            echo "  --compare FILE         Compare one file against all others (relative path)"
            exit 0
            ;;
        *)
            die "Unknown argument: $1"
            ;;
    esac
done

# Validate reviewguides directory exists
[[ -d "$REVIEWGUIDES_DIR" ]] || die "Reviewguides directory not found: $REVIEWGUIDES_DIR"

# Validate --compare file exists
if [[ "$MODE" == "compare" ]]; then
    [[ -f "$REVIEWGUIDES_DIR/$COMPARE_FILE" ]] || die "Compare file not found: $REVIEWGUIDES_DIR/$COMPARE_FILE"
fi

# =========================================================================
# File discovery + .reviewguidesignore filter# =========================================================================

declare -a all_mode_files=()
while IFS= read -r -d '' file; do
    all_mode_files+=("$file")
done < <(find "$REVIEWGUIDES_DIR" -name "*.md" -type f -print0 2>/dev/null)

declare -a mode_files=()
if [[ -f "$REVIEWGUIDES_DIR/.reviewguidesignore" ]]; then
    # Build relative paths for git check-ignore
    local_rel_paths=""
    for file in "${all_mode_files[@]}"; do
        local_rel_paths+="${file#"$REVIEWGUIDES_DIR"/}"$'\n'
    done
    local_rel_paths="${local_rel_paths%$'\n'}"

    # Get ignored paths using gitignore-style matching
    ignored_output="$(printf '%s' "$local_rel_paths" | \
        git -c "core.excludesFile=$REVIEWGUIDES_DIR/.reviewguidesignore" \
            check-ignore --no-index --stdin 2>/dev/null)" || true

    # Build set of ignored paths for O(1) lookup
    declare -A ignored_set
    while IFS= read -r ignored; do
        [[ -n "$ignored" ]] && ignored_set["$ignored"]=1
    done <<< "$ignored_output"

    # Filter out ignored files
    for file in "${all_mode_files[@]}"; do
        rel_path="${file#"$REVIEWGUIDES_DIR"/}"
        [[ -z "${ignored_set[$rel_path]:-}" ]] && mode_files+=("$file")
    done
else
    mode_files=("${all_mode_files[@]}")
fi

if [[ ${#mode_files[@]} -eq 0 ]]; then
    warn "No reviewguide files found in $REVIEWGUIDES_DIR"
    exit 0
fi

# =========================================================================
# Frontmatter parsing
# =========================================================================

# Parse YAML frontmatter from a review guide .md file
# Output: <relative_path>|<name>|<reviewtype_or_MISSING>|<reviewlabels_csv_or_MISSING>|<environment_csv_or_universal>
parse_reviewguide() {
    local file="$1"
    local in_yaml=false
    local name="" environment="" reviewtype="" reviewlabels=""

    while IFS= read -r line; do
        if [[ "$line" == "---" ]]; then
            if [[ "$in_yaml" == true ]]; then break; fi
            in_yaml=true
            continue
        fi
        if [[ "$in_yaml" == true ]]; then
            if [[ "$line" =~ ^name:[[:space:]]*(.*) ]]; then
                name="${BASH_REMATCH[1]}"
            elif [[ "$line" =~ ^environment:[[:space:]]*\[(.*)\] ]]; then
                environment="${BASH_REMATCH[1]}"
                environment="${environment// /}"
            elif [[ "$line" =~ ^reviewtype:[[:space:]]*(.*) ]]; then
                reviewtype="${BASH_REMATCH[1]}"
            elif [[ "$line" =~ ^reviewlabels:[[:space:]]*\[(.*)\] ]]; then
                reviewlabels="${BASH_REMATCH[1]}"
                reviewlabels="${reviewlabels// /}"
            fi
        fi
    done < "$file"

    local rel_path="${file#"$REVIEWGUIDES_DIR"/}"
    echo "${rel_path}|${name}|${reviewtype:-MISSING}|${reviewlabels:-MISSING}|${environment:-universal}"
}

# =========================================================================
# Parse all files
# =========================================================================

declare -a parsed_lines=()
for file in "${mode_files[@]}"; do
    parsed_lines+=("$(parse_reviewguide "$file")")
done

# =========================================================================
# Environment filter
# =========================================================================

if [[ -n "$ENVIRONMENT_FILTER" ]]; then
    declare -a filtered_lines=()
    for line in "${parsed_lines[@]}"; do
        env_field="${line##*|}"
        if [[ "$ENVIRONMENT_FILTER" == "general" ]]; then
            # Show only universal modes (no environment set)
            [[ "$env_field" == "universal" ]] && filtered_lines+=("$line")
        else
            # Show only modes matching the specific environment
            [[ ",$env_field," == *",$ENVIRONMENT_FILTER,"* ]] && filtered_lines+=("$line")
        fi
    done
    parsed_lines=("${filtered_lines[@]+"${filtered_lines[@]}"}")
fi

# =========================================================================
# Label set helpers
# =========================================================================

# Split comma-separated string into array (stored in global SPLIT_RESULT)
declare -a SPLIT_RESULT=()
split_csv() {
    SPLIT_RESULT=()
    local csv="$1"
    if [[ -z "$csv" || "$csv" == "MISSING" ]]; then
        return
    fi
    IFS=',' read -ra SPLIT_RESULT <<< "$csv"
}

# Compute intersection of two comma-separated label strings
# Sets SHARED_LABELS (csv) and SHARED_COUNT
SHARED_LABELS=""
SHARED_COUNT=0
compute_label_overlap() {
    local labels_a="$1"
    local labels_b="$2"
    SHARED_LABELS=""
    SHARED_COUNT=0

    if [[ "$labels_a" == "MISSING" || "$labels_b" == "MISSING" ]]; then
        return
    fi

    # Build set from labels_a
    declare -A set_a
    split_csv "$labels_a"
    for label in "${SPLIT_RESULT[@]}"; do
        set_a["$label"]=1
    done

    # Find intersection with labels_b
    local shared=()
    split_csv "$labels_b"
    for label in "${SPLIT_RESULT[@]}"; do
        if [[ -n "${set_a[$label]:-}" ]]; then
            shared+=("$label")
        fi
    done

    SHARED_COUNT=${#shared[@]}
    if [[ $SHARED_COUNT -gt 0 ]]; then
        SHARED_LABELS="$(IFS=','; echo "${shared[*]}")"
    fi
}

# Check if two environment fields overlap
# Returns 0 (true) if overlap, 1 (false) if not
check_env_overlap() {
    local env_a="$1"
    local env_b="$2"

    # Both universal → overlap
    if [[ "$env_a" == "universal" && "$env_b" == "universal" ]]; then
        return 0
    fi
    # One universal, one specific → no overlap (different scope)
    if [[ "$env_a" == "universal" || "$env_b" == "universal" ]]; then
        return 1
    fi
    # Both specific → check for shared environment
    declare -A env_set
    split_csv "$env_a"
    for e in "${SPLIT_RESULT[@]}"; do
        env_set["$e"]=1
    done
    split_csv "$env_b"
    for e in "${SPLIT_RESULT[@]}"; do
        if [[ -n "${env_set[$e]:-}" ]]; then
            return 0
        fi
    done
    return 1
}

# =========================================================================
# Mode-specific output
# =========================================================================

case "$MODE" in
    default)
        for line in "${parsed_lines[@]}"; do
            echo "$line"
        done
        ;;

    missing-meta)
        for line in "${parsed_lines[@]}"; do
            IFS='|' read -r _path _name rtype rlabels _env <<< "$line"
            if [[ "$rtype" == "MISSING" || "$rlabels" == "MISSING" || ( "$_env" == "universal" && "$_path" != general/* ) ]]; then
                echo "$line"
            fi
        done
        ;;

    find-similar)
        # For each file, find the best-matching other file by label overlap
        for i in "${!parsed_lines[@]}"; do
            IFS='|' read -r _path_i _name_i _type_i labels_i _env_i <<< "${parsed_lines[$i]}"
            best_path=""
            best_count=0

            for j in "${!parsed_lines[@]}"; do
                [[ "$i" -eq "$j" ]] && continue
                IFS='|' read -r path_j _name_j _type_j labels_j _env_j <<< "${parsed_lines[$j]}"

                # Skip pairs where both have MISSING labels
                [[ "$labels_i" == "MISSING" && "$labels_j" == "MISSING" ]] && continue

                compute_label_overlap "$labels_i" "$labels_j"
                if [[ $SHARED_COUNT -gt $best_count ]]; then
                    best_count=$SHARED_COUNT
                    best_path="$path_j"
                fi
            done

            if [[ -n "$best_path" && $best_count -gt 0 ]]; then
                echo "${parsed_lines[$i]}|${best_path}:${best_count}"
            else
                echo "${parsed_lines[$i]}|none:0"
            fi
        done
        ;;

    compare)
        # Parse the target file
        target_line=""
        for line in "${parsed_lines[@]}"; do
            IFS='|' read -r path _name _type _labels _env <<< "$line"
            if [[ "$path" == "$COMPARE_FILE" ]]; then
                target_line="$line"
                break
            fi
        done

        if [[ -z "$target_line" ]]; then
            die "Compare file not found in parsed results: $COMPARE_FILE"
        fi

        IFS='|' read -r _tpath _tname target_type target_labels target_env <<< "$target_line"

        # Compare against all other files, collect scored results
        declare -a scored_results=()
        for line in "${parsed_lines[@]}"; do
            IFS='|' read -r c_path c_name c_type c_labels c_env <<< "$line"
            [[ "$c_path" == "$COMPARE_FILE" ]] && continue

            # Compute shared labels
            compute_label_overlap "$target_labels" "$c_labels"
            local_shared_count=$SHARED_COUNT
            local_shared_labels="$SHARED_LABELS"

            # Type match
            type_match="no"
            if [[ "$target_type" != "MISSING" && "$c_type" != "MISSING" && "$target_type" == "$c_type" ]]; then
                type_match="yes"
            fi

            # Env overlap
            env_overlap="no"
            if check_env_overlap "$target_env" "$c_env"; then
                env_overlap="yes"
            fi

            # Score
            score=$(( local_shared_count * 2 ))
            [[ "$type_match" == "yes" ]] && score=$(( score + 3 ))
            [[ "$env_overlap" == "yes" ]] && score=$(( score + 2 ))

            if [[ $score -gt 0 ]]; then
                scored_results+=("${c_path}|${c_name}|${score}|${local_shared_labels:-none}|${type_match}|${env_overlap}")
            fi
        done

        # Sort descending by score (field 3)
        if [[ ${#scored_results[@]} -gt 0 ]]; then
            printf '%s\n' "${scored_results[@]}" | sort -t'|' -k3 -rn
        fi
        ;;
esac
