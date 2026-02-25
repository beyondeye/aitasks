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

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PROFILES_DIR="${PROFILES_DIR:-$REPO_ROOT/aitasks/metadata/profiles}"
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

# Collect profile YAML files
shopt -s nullglob
profile_files=("$PROFILES_DIR"/*.yaml)
shopt -u nullglob

if [[ ${#profile_files[@]} -eq 0 ]]; then
    echo "NO_PROFILES"
    exit 0
fi

# Parse each profile: extract name and description
# Arrays indexed in parallel
declare -a filenames=()
declare -a names=()
declare -a descriptions=()
declare -a invalid=()

for f in "${profile_files[@]}"; do
    fname="$(basename "$f")"
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

    echo "AUTO_SELECTED|${filenames[$selected_idx]}|${names[$selected_idx]}|${descriptions[$selected_idx]}"
else
    # List all profiles (sorted alphabetically by filename — already sorted by glob)
    for i in "${!filenames[@]}"; do
        echo "PROFILE|${filenames[$i]}|${names[$i]}|${descriptions[$i]}"
    done
fi
