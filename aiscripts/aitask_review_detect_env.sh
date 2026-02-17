#!/usr/bin/env bash
# aitask_review_detect_env.sh - Auto-detect project environment and rank review modes
# Uses modular independent tests to score environments, then maps scores to review modes.
#
# Usage:
#   aitask_review_detect_env.sh [--files-stdin | --files FILE...] [--reviewmodes-dir DIR]
#
# Options:
#   --files-stdin        Read file list from stdin (one per line)
#   --files FILE...      List of files as positional arguments (terminated by next flag or end)
#   --reviewmodes-dir D  Path to reviewmodes directory (default: aitasks/metadata/reviewmodes)
#
# Output format (two sections separated by ---):
#   ENV_SCORES
#   <env>|<score>     (one per line, descending by score, only scores > 0)
#   ---
#   REVIEW_MODES
#   <filename>|<name>|<description>|<score_or_universal>
#
# Called by:
#   .claude/skills/aitask-review/SKILL.md (Step 1b - Review Mode Selection)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

# --- Defaults ---
REVIEWMODES_DIR="aitasks/metadata/reviewmodes"
FILES=()
READ_STDIN=false

# --- Argument parsing ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --files-stdin)
            READ_STDIN=true
            shift
            ;;
        --files)
            shift
            while [[ $# -gt 0 && ! "$1" =~ ^-- ]]; do
                FILES+=("$1")
                shift
            done
            ;;
        --reviewmodes-dir)
            REVIEWMODES_DIR="${2:?--reviewmodes-dir requires a path}"
            shift 2
            ;;
        --help|-h)
            echo "Usage: aitask_review_detect_env.sh [--files-stdin | --files FILE...] [--reviewmodes-dir DIR]"
            echo ""
            echo "Auto-detect project environments and rank review modes by relevance."
            echo ""
            echo "Options:"
            echo "  --files-stdin        Read file list from stdin (one per line)"
            echo "  --files FILE...      List of files as arguments"
            echo "  --reviewmodes-dir D  Review modes directory (default: aitasks/metadata/reviewmodes)"
            exit 0
            ;;
        *)
            die "Unknown argument: $1"
            ;;
    esac
done

# Read files from stdin if requested
if [[ "$READ_STDIN" == true ]]; then
    while IFS= read -r line; do
        [[ -n "$line" ]] && FILES+=("$line")
    done
fi

# =========================================================================
# Environment scoring system
# =========================================================================

# Associative array for scores. Bash 4+ required.
declare -A ENV_SCORES

# Helper: add score to an environment
add_score() {
    local env="$1"
    local score="$2"
    ENV_SCORES["$env"]=$(( ${ENV_SCORES["$env"]:-0} + score ))
}

# =========================================================================
# Test functions — each test is independent and updates ENV_SCORES
#
# To add a new test:
#   1. Write a function named test_<name>()
#   2. Add it to ALL_TESTS array below
#   3. Use add_score "env_name" <weight> to contribute scores
# =========================================================================

ALL_TESTS=(
    test_project_root_files
    test_file_extensions
    test_shebang_lines
    test_directory_patterns
)

# --- Test 1: Project root marker files (weight: 3 per match) ---
# Checks for well-known build/config files in the project root.
test_project_root_files() {
    local weight=3

    # Python
    if [[ -f "pyproject.toml" || -f "setup.py" || -f "requirements.txt" ]]; then
        add_score "python" "$weight"
    fi

    # Android / Kotlin
    if [[ -f "build.gradle" || -f "build.gradle.kts" ]]; then
        add_score "android" "$weight"
        add_score "kotlin" "$weight"
    fi

    # C++ / CMake
    if [[ -f "CMakeLists.txt" ]]; then
        add_score "cpp" "$weight"
        add_score "cmake" "$weight"
    fi

    # JavaScript / TypeScript
    if [[ -f "package.json" ]]; then
        add_score "javascript" "$weight"
        add_score "typescript" "$weight"
    fi

    # Rust
    if [[ -f "Cargo.toml" ]]; then
        add_score "rust" "$weight"
    fi

    # Go
    if [[ -f "go.mod" ]]; then
        add_score "go" "$weight"
    fi
}

# --- Test 2: File extensions in the provided file list (weight: 1 per file) ---
test_file_extensions() {
    local weight=1
    local has_gradle=false
    [[ -f "build.gradle" || -f "build.gradle.kts" ]] && has_gradle=true

    for f in "${FILES[@]}"; do
        case "${f##*.}" in
            py)                 add_score "python" "$weight" ;;
            sh)                 add_score "bash" "$weight"; add_score "shell" "$weight" ;;
            kt|kts)            add_score "kotlin" "$weight"; add_score "android" "$weight" ;;
            java)
                if [[ "$has_gradle" == true ]]; then
                    add_score "android" "$weight"
                else
                    add_score "java" "$weight"
                fi
                ;;
            js|jsx|mjs)        add_score "javascript" "$weight" ;;
            ts|tsx|mts)        add_score "typescript" "$weight" ;;
            cpp|cc|cxx|c|h|hpp) add_score "cpp" "$weight" ;;
            cmake)             add_score "cmake" "$weight" ;;
            rs)                add_score "rust" "$weight" ;;
            go)                add_score "go" "$weight" ;;
        esac
    done
}

# --- Test 3: Shebang lines in existing files (weight: 2 per match) ---
# Only checks the first 20 files that exist on disk.
test_shebang_lines() {
    local weight=2
    local checked=0

    for f in "${FILES[@]}"; do
        [[ $checked -ge 20 ]] && break
        [[ -f "$f" ]] || continue

        local first_line
        first_line=$(head -n 1 "$f" 2>/dev/null) || continue
        checked=$((checked + 1))

        if [[ "$first_line" =~ ^#! ]]; then
            if [[ "$first_line" =~ bash ]] || [[ "$first_line" =~ /sh ]]; then
                add_score "bash" "$weight"
                add_score "shell" "$weight"
            elif [[ "$first_line" =~ python ]]; then
                add_score "python" "$weight"
            fi
        fi
    done
}

# --- Test 4: Directory patterns in the file list (weight: 2 per match) ---
# Checks if files are under known directories that indicate specific environments.
test_directory_patterns() {
    local weight=2
    local found_aiscripts=false
    local found_android_src=false
    local found_root_sh=false

    for f in "${FILES[@]}"; do
        # aiscripts/ directory or .sh files at project root
        if [[ "$f" == aiscripts/* ]] && [[ "$found_aiscripts" == false ]]; then
            add_score "bash" "$weight"
            add_score "shell" "$weight"
            found_aiscripts=true
        fi
        if [[ "$f" == *.sh ]] && [[ "$f" != */* ]] && [[ "$found_root_sh" == false ]]; then
            add_score "bash" "$weight"
            add_score "shell" "$weight"
            found_root_sh=true
        fi

        # Android/Kotlin source directories
        if [[ "$f" == src/main/kotlin/* || "$f" == src/main/java/* || "$f" == app/src/* ]] && [[ "$found_android_src" == false ]]; then
            add_score "android" "$weight"
            add_score "kotlin" "$weight"
            found_android_src=true
        fi
    done
}

# =========================================================================
# Review mode parsing
# =========================================================================

# Parse YAML frontmatter from a review mode .md file
# Output: <filename>|<name>|<description>|<env1,env2,...>
# The environment field is empty for universal modes
parse_reviewmode() {
    local file="$1"
    local in_yaml=false
    local name="" description="" environment=""

    while IFS= read -r line; do
        if [[ "$line" == "---" ]]; then
            if [[ "$in_yaml" == true ]]; then break; fi
            in_yaml=true
            continue
        fi
        if [[ "$in_yaml" == true ]]; then
            if [[ "$line" =~ ^name:[[:space:]]*(.*) ]]; then
                name="${BASH_REMATCH[1]}"
            elif [[ "$line" =~ ^description:[[:space:]]*(.*) ]]; then
                description="${BASH_REMATCH[1]}"
            elif [[ "$line" =~ ^environment:[[:space:]]*\[(.*)\] ]]; then
                # Remove spaces from environment list: "bash, shell" -> "bash,shell"
                environment="${BASH_REMATCH[1]}"
                environment="${environment// /}"
            fi
        fi
    done < "$file"

    echo "$(basename "$file")|${name}|${description}|${environment}"
}

# =========================================================================
# Main
# =========================================================================

# Run all environment tests
for test_fn in "${ALL_TESTS[@]}"; do
    "$test_fn"
done

# --- Output Section 1: ENV_SCORES ---
echo "ENV_SCORES"

# Sort scores descending and output
{
    for env in "${!ENV_SCORES[@]}"; do
        echo "${ENV_SCORES[$env]}|${env}"
    done
} | sort -t'|' -k1 -rn | while IFS='|' read -r score env; do
    [[ "$score" -gt 0 ]] && echo "${env}|${score}"
done

echo "---"

# --- Output Section 2: REVIEW_MODES ---
echo "REVIEW_MODES"

# Parse all review mode files
declare -a env_specific_modes=()
declare -a universal_modes=()

for mode_file in "$REVIEWMODES_DIR"/*.md; do
    [[ -f "$mode_file" ]] || continue
    mode_info=$(parse_reviewmode "$mode_file")

    # Extract environment field (4th pipe-delimited field)
    mode_env="${mode_info##*|}"

    if [[ -z "$mode_env" ]]; then
        universal_modes+=("$mode_info")
    else
        # Calculate max score from the mode's environment list
        max_score=0
        IFS=',' read -ra envs <<< "$mode_env"
        for e in "${envs[@]}"; do
            s="${ENV_SCORES[$e]:-0}"
            [[ "$s" -gt "$max_score" ]] && max_score="$s"
        done
        env_specific_modes+=("${max_score}|${mode_info}")
    fi
done

# Output env-specific modes sorted by score (descending)
printf '%s\n' "${env_specific_modes[@]}" 2>/dev/null | sort -t'|' -k1 -rn | while IFS='|' read -r score filename name description env; do
    echo "${filename}|${name}|${description}|${score}"
done

# Output universal modes (alphabetically by name)
printf '%s\n' "${universal_modes[@]}" 2>/dev/null | sort -t'|' -k2 | while IFS='|' read -r filename name description env; do
    echo "${filename}|${name}|${description}|universal"
done
