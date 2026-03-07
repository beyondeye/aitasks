#!/usr/bin/env bash
# aitask_scan_profiles.sh - Scan execution profiles and output metadata
# Usage:
#   aitask_scan_profiles.sh          # List all profiles
#   aitask_scan_profiles.sh --auto   # Auto-select (remote > single > first alphabetical)
#
# Output format:
#   PROFILE|<filename>|<name>|<description>   (one per valid profile)
#   AUTO_SELECTED|<filename>|<name>|<description>  (--auto mode)
#   NO_PROFILES                                (no .yaml files found)
#   INVALID|<filename>                         (missing name field, skipped)
#
# For user-local profiles (in profiles/local/), the filename field includes
# the local/ prefix (e.g., "local/fast.yaml") so callers can resolve the
# path with: cat aitasks/metadata/profiles/<filename>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PROFILES_DIR="${PROFILES_DIR:-$REPO_ROOT/aitasks/metadata/profiles}"
LOCAL_PROFILES_DIR="${LOCAL_PROFILES_DIR:-$PROFILES_DIR/local}"
AUTO_MODE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --auto) AUTO_MODE=true; shift ;;
        --help|-h)
            echo "Usage: aitask_scan_profiles.sh [--auto]"
            echo "  --auto  Auto-select profile (remote > single > first alphabetical)"
            exit 0
            ;;
        *) echo "Error: Unknown option: $1" >&2; exit 1 ;;
    esac
done

# Collect profile YAML files from both directories
shopt -s nullglob
project_files=("$PROFILES_DIR"/*.yaml)
local_files=("$LOCAL_PROFILES_DIR"/*.yaml)
shopt -u nullglob

if [[ ${#project_files[@]} -eq 0 && ${#local_files[@]} -eq 0 ]]; then
    echo "NO_PROFILES"
    exit 0
fi

# Merge: local overrides project for same filename
declare -A profile_paths
declare -A profile_layer_map

for f in "${project_files[@]}"; do
    fname="$(basename "$f")"
    profile_paths["$fname"]="$f"
    profile_layer_map["$fname"]="project"
done

for f in "${local_files[@]}"; do
    fname="$(basename "$f")"
    profile_paths["$fname"]="$f"
    profile_layer_map["$fname"]="user"
done

# Build the output filename (include local/ prefix for user profiles)
_output_fname() {
    local fname="$1"
    if [[ "${profile_layer_map[$fname]}" == "user" ]]; then
        echo "local/$fname"
    else
        echo "$fname"
    fi
}

# Parse each profile: extract name and description
# Arrays indexed in parallel
declare -a filenames=()
declare -a names=()
declare -a descriptions=()
declare -a invalid=()

for fname in $(printf '%s\n' "${!profile_paths[@]}" | sort); do
    f="${profile_paths[$fname]}"
    # Extract name: first line matching "name: <value>"
    pname="$(grep -m1 '^name:' "$f" 2>/dev/null | sed 's/^name:[[:space:]]*//' | sed 's/[[:space:]]*$//')" || true
    if [[ -z "$pname" ]]; then
        invalid+=("$fname")
        continue
    fi
    # Extract description: first line matching "description: <value>"
    pdesc="$(grep -m1 '^description:' "$f" 2>/dev/null | sed 's/^description:[[:space:]]*//' | sed 's/[[:space:]]*$//')" || true

    filenames+=("$fname")
    names+=("$pname")
    descriptions+=("$pdesc")
done

# Report invalid profiles (to stderr for --auto, to stdout for list mode)
for inv in "${invalid[@]}"; do
    if [[ "$AUTO_MODE" == true ]]; then
        echo "INVALID|$inv" >&2
    else
        echo "INVALID|$inv"
    fi
done

if [[ ${#filenames[@]} -eq 0 ]]; then
    echo "NO_PROFILES"
    exit 0
fi

if [[ "$AUTO_MODE" == true ]]; then
    # Auto-select: remote > single > first alphabetical
    selected_idx=""

    # Priority 1: profile named "remote"
    for i in "${!names[@]}"; do
        if [[ "${names[$i]}" == "remote" ]]; then
            selected_idx=$i
            break
        fi
    done

    # Priority 2: single profile
    if [[ -z "$selected_idx" && ${#filenames[@]} -eq 1 ]]; then
        selected_idx=0
    fi

    # Priority 3: first alphabetically by filename
    if [[ -z "$selected_idx" ]]; then
        selected_idx=0
    fi

    echo "AUTO_SELECTED|$(_output_fname "${filenames[$selected_idx]}")|${names[$selected_idx]}|${descriptions[$selected_idx]}"
else
    # List all profiles (sorted alphabetically by filename)
    for i in "${!filenames[@]}"; do
        echo "PROFILE|$(_output_fname "${filenames[$i]}")|${names[$i]}|${descriptions[$i]}"
    done
fi
