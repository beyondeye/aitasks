#!/usr/bin/env bash
# aitask_review_detect_env.sh - Auto-detect project environment and rank review guides
# Uses modular independent tests to score environments, then maps scores to review guides.
#
# Usage:
#   aitask_review_detect_env.sh [--files-stdin | --files FILE...] [--reviewguides-dir DIR]
#
# Options:
#   --files-stdin        Read file list from stdin (one per line)
#   --files FILE...      List of files as positional arguments (terminated by next flag or end)
#   --reviewguides-dir D  Path to reviewguides directory (default: aireviewguides)
#
# Output format (two sections separated by ---):
#   ENV_SCORES
#   <env>|<score>     (one per line, descending by score, only scores > 0)
#   ---
#   REVIEW_GUIDES
#   <relative_path>|<name>|<description>|<score_or_universal>
#   (relative_path is relative to reviewguides dir, e.g. "general/security.md")
#
# Called by:
#   .claude/skills/aitask-review/SKILL.md (Step 1b - Review Guide Selection)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

# --- Defaults ---
REVIEWGUIDES_DIR="aireviewguides"
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
        --reviewguides-dir)
            REVIEWGUIDES_DIR="${2:?--reviewguides-dir requires a path}"
            shift 2
            ;;
        --help|-h)
            echo "Usage: aitask_review_detect_env.sh [--files-stdin | --files FILE...] [--reviewguides-dir DIR]"
            echo ""
            echo "Auto-detect project environments and rank review guides by relevance."
            echo ""
            echo "Options:"
            echo "  --files-stdin        Read file list from stdin (one per line)"
            echo "  --files FILE...      List of files as arguments"
            echo "  --reviewguides-dir D  Review guides directory (default: aireviewguides)"
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

    # C#
    if compgen -G "*.csproj" >/dev/null 2>&1 || compgen -G "*.sln" >/dev/null 2>&1; then
        add_score "c-sharp" "$weight"
    fi

    # Dart / Flutter
    if [[ -f "pubspec.yaml" ]]; then
        add_score "dart" "$weight"
        if grep -q 'flutter:' "pubspec.yaml" 2>/dev/null || grep -q 'flutter_' "pubspec.yaml" 2>/dev/null; then
            add_score "flutter" "$weight"
        fi
    fi

    # Swift / iOS
    if compgen -G "*.xcodeproj" >/dev/null 2>&1 || compgen -G "*.xcworkspace" >/dev/null 2>&1; then
        add_score "ios" "$weight"
        add_score "swift" "$weight"
    fi
    if [[ -f "Package.swift" ]]; then
        add_score "swift" "$weight"
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
            cs)                add_score "c-sharp" "$weight" ;;
            dart)              add_score "dart" "$weight" ;;
            swift)
                add_score "swift" "$weight"
                if compgen -G "*.xcodeproj" >/dev/null 2>&1 || compgen -G "*.xcworkspace" >/dev/null 2>&1; then
                    add_score "ios" "$weight"
                fi
                ;;
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
    local found_ios_dir=false
    local found_flutter_lib=false
    local found_csharp_dir=false

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

        # iOS directories (xcodeproj contents, ios/ folder, Pods/)
        if [[ "$f" == *.xcodeproj/* || "$f" == ios/* || "$f" == Pods/* ]] && [[ "$found_ios_dir" == false ]]; then
            add_score "ios" "$weight"
            add_score "swift" "$weight"
            found_ios_dir=true
        fi

        # Flutter (lib/*.dart files suggest Flutter project structure)
        if [[ "$f" == lib/*.dart || "$f" == lib/**/*.dart ]] && [[ "$found_flutter_lib" == false ]]; then
            add_score "flutter" "$weight"
            add_score "dart" "$weight"
            found_flutter_lib=true
        fi

        # C# (.NET project directories)
        if [[ "$f" == Properties/* || "$f" == obj/* ]] && [[ "$found_csharp_dir" == false ]]; then
            add_score "c-sharp" "$weight"
            found_csharp_dir=true
        fi
    done
}

# =========================================================================
# Review guide parsing
# =========================================================================

# Parse YAML frontmatter from a review guide .md file
# Output: <relative_path>|<name>|<description>|<env1,env2,...>
# relative_path is relative to $REVIEWGUIDES_DIR (e.g. "general/security.md")
# The environment field is empty for universal modes
parse_reviewguide() {
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

    local rel_path="${file#$REVIEWGUIDES_DIR/}"
    echo "${rel_path}|${name}|${description}|${environment}"
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
echo "REVIEW_GUIDES"

# Discover all review guide files recursively
declare -a all_mode_files=()
while IFS= read -r -d '' file; do
    all_mode_files+=("$file")
done < <(find "$REVIEWGUIDES_DIR" -name "*.md" -type f -print0 2>/dev/null)

# Apply .reviewguidesignore filter if present
declare -a mode_files=()
if [[ -f "$REVIEWGUIDES_DIR/.reviewguidesignore" ]]; then
    # Build relative paths for git check-ignore
    local_rel_paths=""
    for file in "${all_mode_files[@]}"; do
        local_rel_paths+="${file#$REVIEWGUIDES_DIR/}"$'\n'
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
        rel_path="${file#$REVIEWGUIDES_DIR/}"
        [[ -z "${ignored_set[$rel_path]:-}" ]] && mode_files+=("$file")
    done
else
    mode_files=("${all_mode_files[@]}")
fi

# Parse filtered review guide files
declare -a env_specific_modes=()
declare -a universal_modes=()

for mode_file in "${mode_files[@]}"; do
    mode_info=$(parse_reviewguide "$mode_file")

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
if [[ ${#env_specific_modes[@]} -gt 0 ]]; then
    printf '%s\n' "${env_specific_modes[@]}" | sort -t'|' -k1 -rn | while IFS='|' read -r score rel_path name description env; do
        echo "${rel_path}|${name}|${description}|${score}"
    done
fi

# Output universal modes (alphabetically by name)
if [[ ${#universal_modes[@]} -gt 0 ]]; then
    printf '%s\n' "${universal_modes[@]}" | sort -t'|' -k2 | while IFS='|' read -r rel_path name description env; do
        echo "${rel_path}|${name}|${description}|universal"
    done
fi
