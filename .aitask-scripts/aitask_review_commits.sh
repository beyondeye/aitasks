#!/usr/bin/env bash
# aitask_review_commits.sh - Paginated commit fetching with ait: prefix filtering
# Returns a pipe-delimited list of relevant commits with diff stats.
#
# Usage:
#   aitask_review_commits.sh [--batch-size N] [--offset N]
#
# Options:
#   --batch-size N   Number of relevant commits to return per batch (default: 10)
#   --offset N       Number of already-displayed relevant commits to skip (default: 0)
#
# Output format (one line per commit, pipe-delimited):
#   <display_number>|<hash>|<message>|<insertions>|<deletions>
#
# Final line is one of:
#   HAS_MORE|<next_offset>    - More commits available
#   NO_MORE_COMMITS           - No more commits in history
#
# Called by:
#   .claude/skills/aitask-review/SKILL.md (Step 1a - Recent changes)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

# --- Defaults ---
BATCH_SIZE=10
OFFSET=0
GIT_CHUNK=50  # Raw commits to fetch per git log call (to efficiently scan past ait: commits)

# --- Argument parsing ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --batch-size)
            BATCH_SIZE="${2:?--batch-size requires a number}"
            shift 2
            ;;
        --offset)
            OFFSET="${2:?--offset requires a number}"
            shift 2
            ;;
        --help|-h)
            echo "Usage: aitask_review_commits.sh [--batch-size N] [--offset N]"
            echo ""
            echo "Fetch relevant commits (filtering out ait: administrative commits)"
            echo "in paginated batches with diff stats."
            echo ""
            echo "Options:"
            echo "  --batch-size N   Commits per batch (default: 10)"
            echo "  --offset N       Already-displayed commits to skip (default: 0)"
            exit 0
            ;;
        *)
            die "Unknown argument: $1"
            ;;
    esac
done

# --- Validate we're in a git repo ---
if ! git rev-parse --is-inside-work-tree &>/dev/null; then
    die "Not a git repository"
fi

# --- Parse shortstat line into insertions and deletions ---
# Input: "3 files changed, 45 insertions(+), 12 deletions(-)" or variants
# Sets: _INS and _DEL variables
parse_shortstat() {
    local stat_line="$1"
    _INS=0
    _DEL=0

    if [[ "$stat_line" =~ ([0-9]+)\ insertion ]]; then
        _INS="${BASH_REMATCH[1]}"
    fi
    if [[ "$stat_line" =~ ([0-9]+)\ deletion ]]; then
        _DEL="${BASH_REMATCH[1]}"
    fi
}

# --- Main loop: fetch and filter commits ---
collected=0
skipped=0
git_skip=0
display_num=$((OFFSET + 1))
exhausted=false

while [[ $collected -lt $BATCH_SIZE ]]; do
    # Fetch a chunk of raw commits
    raw_output=""
    raw_output=$(git log --oneline --shortstat --skip="$git_skip" -n "$GIT_CHUNK" 2>/dev/null) || true

    if [[ -z "$raw_output" ]]; then
        exhausted=true
        break
    fi

    # Track how many raw commits we got in this chunk
    chunk_count=0

    # Process commits: each commit produces 2-3 lines:
    # Line 1: <hash> <message>  (oneline)
    # Line 2: (empty line)
    # Line 3: <shortstat>
    current_hash=""
    current_msg=""
    while IFS= read -r line; do
        # Skip empty lines
        if [[ -z "$line" ]]; then
            continue
        fi

        # Check if this is a shortstat line (starts with space + digit)
        if [[ "$line" =~ ^[[:space:]]+[0-9]+\ file ]]; then
            # This is the stat line for the current commit
            if [[ -n "$current_hash" ]]; then
                chunk_count=$((chunk_count + 1))

                # Filter: skip ait: prefix commits (case-insensitive)
                if [[ "$current_msg" =~ ^[aA][iI][tT]:[[:space:]] ]]; then
                    current_hash=""
                    current_msg=""
                    continue
                fi

                # Count as relevant
                if [[ $skipped -lt $OFFSET ]]; then
                    skipped=$((skipped + 1))
                else
                    parse_shortstat "$line"
                    echo "${display_num}|${current_hash}|${current_msg}|${_INS}|${_DEL}"
                    display_num=$((display_num + 1))
                    collected=$((collected + 1))

                    if [[ $collected -ge $BATCH_SIZE ]]; then
                        current_hash=""
                        current_msg=""
                        break
                    fi
                fi
            fi
            current_hash=""
            current_msg=""
        else
            # This is a commit oneline: <hash> <message>
            current_hash="${line%% *}"
            current_msg="${line#* }"
        fi
    done <<< "$raw_output"

    # If we got fewer raw commits than requested, we've reached the end
    if [[ $chunk_count -lt $GIT_CHUNK ]]; then
        # But we might have a pending commit without stats (last commit edge case)
        if [[ -n "$current_hash" ]] && [[ $collected -lt $BATCH_SIZE ]]; then
            if ! [[ "$current_msg" =~ ^[aA][iI][tT]:[[:space:]] ]]; then
                if [[ $skipped -ge $OFFSET ]]; then
                    echo "${display_num}|${current_hash}|${current_msg}|0|0"
                    collected=$((collected + 1))
                fi
            fi
        fi
        exhausted=true
        break
    fi

    git_skip=$((git_skip + GIT_CHUNK))
done

# --- Output final marker ---
if [[ "$exhausted" == true ]]; then
    echo "NO_MORE_COMMITS"
else
    echo "HAS_MORE|$((OFFSET + collected))"
fi
