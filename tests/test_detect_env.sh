#!/bin/bash
# test_detect_env.sh - Automated tests for aitask_review_detect_env.sh
# Run: bash tests/test_detect_env.sh
#
# Creates temporary directories with project structures and verifies that
# the environment detection script correctly identifies each environment.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DETECT_SCRIPT="$PROJECT_DIR/aiscripts/aitask_review_detect_env.sh"
GUIDES_DIR="$PROJECT_DIR/aireviewguides"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

TMPDIR_BASE=""

setup_tmpdir() {
    TMPDIR_BASE=$(mktemp -d)
}

teardown_tmpdir() {
    [[ -n "$TMPDIR_BASE" && -d "$TMPDIR_BASE" ]] && rm -rf "$TMPDIR_BASE"
    TMPDIR_BASE=""
}

# Run detection in a temp directory with given root files and file list.
# Usage: run_detect <file_list_string> [root_files_to_create...]
# Prints ENV_SCORES section only (env|score lines).
run_detect() {
    local file_list="$1"
    shift
    local workdir="$TMPDIR_BASE/workdir"
    rm -rf "$workdir"
    mkdir -p "$workdir"

    # Create root files (touch or write content)
    for spec in "$@"; do
        local target="$workdir/$spec"
        mkdir -p "$(dirname "$target")"
        touch "$target"
    done

    # Run detection from the workdir
    (cd "$workdir" && printf '%s' "$file_list" | "$DETECT_SCRIPT" --files-stdin --reviewguides-dir "$GUIDES_DIR" 2>/dev/null) || true
}

# Extract just the env scores from output (lines between ENV_SCORES and ---)
extract_scores() {
    local output="$1"
    echo "$output" | sed -n '/^ENV_SCORES$/,/^---$/p' | grep -v '^ENV_SCORES$' | grep -v '^---$' || true
}

# Assert that a specific environment appears in the scores with score > 0
assert_env_detected() {
    local desc="$1"
    local env="$2"
    local scores="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$scores" | grep -q "^${env}|"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected '$env' in scores)"
        echo "  Got: $(echo "$scores" | tr '\n' ' ')"
    fi
}

# Assert that a specific environment does NOT appear in the scores
assert_env_not_detected() {
    local desc="$1"
    local env="$2"
    local scores="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$scores" | grep -q "^${env}|"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (unexpected '$env' in scores)"
        echo "  Got: $(echo "$scores" | tr '\n' ' ')"
    else
        PASS=$((PASS + 1))
    fi
}

# Assert that env score is >= minimum
assert_env_min_score() {
    local desc="$1"
    local env="$2"
    local min_score="$3"
    local scores="$4"
    TOTAL=$((TOTAL + 1))
    local actual
    actual=$(echo "$scores" | grep "^${env}|" | cut -d'|' -f2)
    if [[ -z "$actual" ]]; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (env '$env' not found, expected score >= $min_score)"
        return
    fi
    if [[ "$actual" -ge "$min_score" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (env '$env' score=$actual, expected >= $min_score)"
    fi
}

# Assert no environments detected
assert_no_envs() {
    local desc="$1"
    local scores="$2"
    TOTAL=$((TOTAL + 1))
    if [[ -z "$scores" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected no envs, got: $(echo "$scores" | tr '\n' ' '))"
    fi
}

echo "=== Environment Detection Tests ==="
echo ""

# --- Syntax check ---
echo "--- Syntax check ---"
TOTAL=$((TOTAL + 1))
if bash -n "$DETECT_SCRIPT" 2>/dev/null; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: bash -n aitask_review_detect_env.sh (syntax error)"
fi

setup_tmpdir

# =========================================================================
# PYTHON
# =========================================================================
echo "--- Python ---"

# pyproject.toml root file
output=$(run_detect "" "pyproject.toml")
scores=$(extract_scores "$output")
assert_env_detected "Python: pyproject.toml root file" "python" "$scores"

# setup.py root file
output=$(run_detect "" "setup.py")
scores=$(extract_scores "$output")
assert_env_detected "Python: setup.py root file" "python" "$scores"

# requirements.txt root file
output=$(run_detect "" "requirements.txt")
scores=$(extract_scores "$output")
assert_env_detected "Python: requirements.txt root file" "python" "$scores"

# .py file extension
output=$(run_detect $'app.py\nutils.py\n')
scores=$(extract_scores "$output")
assert_env_detected "Python: .py file extensions" "python" "$scores"

# Combined root + extensions = higher score
output=$(run_detect $'app.py\nutils.py\n' "pyproject.toml")
scores=$(extract_scores "$output")
assert_env_min_score "Python: root + extensions combined" "python" 5 "$scores"

# =========================================================================
# BASH / SHELL
# =========================================================================
echo "--- Bash / Shell ---"

# .sh file extension
output=$(run_detect $'deploy.sh\ninstall.sh\n')
scores=$(extract_scores "$output")
assert_env_detected "Bash: .sh file extensions" "bash" "$scores"
assert_env_detected "Shell: .sh file extensions" "shell" "$scores"

# aiscripts/ directory pattern
output=$(run_detect $'aiscripts/build.sh\n')
scores=$(extract_scores "$output")
assert_env_detected "Bash: aiscripts/ directory" "bash" "$scores"
assert_env_detected "Shell: aiscripts/ directory" "shell" "$scores"

# Root .sh file triggers directory pattern
output=$(run_detect $'deploy.sh\n')
scores=$(extract_scores "$output")
assert_env_detected "Bash: root .sh file" "bash" "$scores"

# =========================================================================
# KOTLIN / ANDROID
# =========================================================================
echo "--- Kotlin / Android ---"

# build.gradle root file
output=$(run_detect "" "build.gradle")
scores=$(extract_scores "$output")
assert_env_detected "Android: build.gradle root file" "android" "$scores"
assert_env_detected "Kotlin: build.gradle root file" "kotlin" "$scores"

# build.gradle.kts root file
output=$(run_detect "" "build.gradle.kts")
scores=$(extract_scores "$output")
assert_env_detected "Android: build.gradle.kts root file" "android" "$scores"
assert_env_detected "Kotlin: build.gradle.kts root file" "kotlin" "$scores"

# .kt file extension
output=$(run_detect $'src/Main.kt\n')
scores=$(extract_scores "$output")
assert_env_detected "Kotlin: .kt file extension" "kotlin" "$scores"
assert_env_detected "Android: .kt file extension" "android" "$scores"

# Android source directories
output=$(run_detect $'app/src/main/kotlin/App.kt\n')
scores=$(extract_scores "$output")
assert_env_detected "Android: app/src/ directory pattern" "android" "$scores"

# src/main/kotlin pattern
output=$(run_detect $'src/main/kotlin/Main.kt\n')
scores=$(extract_scores "$output")
assert_env_detected "Android: src/main/kotlin/ directory pattern" "android" "$scores"

# =========================================================================
# JAVA
# =========================================================================
echo "--- Java ---"

# .java without gradle → java (not android)
output=$(run_detect $'src/Main.java\n')
scores=$(extract_scores "$output")
assert_env_detected "Java: .java without gradle" "java" "$scores"
assert_env_not_detected "Java: no android without gradle" "android" "$scores"

# .java WITH gradle → android (not standalone java)
output=$(run_detect $'src/Main.java\n' "build.gradle")
scores=$(extract_scores "$output")
assert_env_detected "Java+gradle: android detected" "android" "$scores"

# =========================================================================
# JAVASCRIPT
# =========================================================================
echo "--- JavaScript ---"

# package.json root file
output=$(run_detect "" "package.json")
scores=$(extract_scores "$output")
assert_env_detected "JavaScript: package.json root file" "javascript" "$scores"

# .js file extension
output=$(run_detect $'src/app.js\n')
scores=$(extract_scores "$output")
assert_env_detected "JavaScript: .js file extension" "javascript" "$scores"

# .jsx file extension
output=$(run_detect $'components/App.jsx\n')
scores=$(extract_scores "$output")
assert_env_detected "JavaScript: .jsx file extension" "javascript" "$scores"

# .mjs file extension
output=$(run_detect $'utils.mjs\n')
scores=$(extract_scores "$output")
assert_env_detected "JavaScript: .mjs file extension" "javascript" "$scores"

# =========================================================================
# TYPESCRIPT
# =========================================================================
echo "--- TypeScript ---"

# package.json also scores typescript
output=$(run_detect "" "package.json")
scores=$(extract_scores "$output")
assert_env_detected "TypeScript: package.json root file" "typescript" "$scores"

# .ts file extension
output=$(run_detect $'src/app.ts\n')
scores=$(extract_scores "$output")
assert_env_detected "TypeScript: .ts file extension" "typescript" "$scores"

# .tsx file extension
output=$(run_detect $'components/App.tsx\n')
scores=$(extract_scores "$output")
assert_env_detected "TypeScript: .tsx file extension" "typescript" "$scores"

# .mts file extension
output=$(run_detect $'utils.mts\n')
scores=$(extract_scores "$output")
assert_env_detected "TypeScript: .mts file extension" "typescript" "$scores"

# =========================================================================
# C++ / CMAKE
# =========================================================================
echo "--- C++ / CMake ---"

# CMakeLists.txt root file
output=$(run_detect "" "CMakeLists.txt")
scores=$(extract_scores "$output")
assert_env_detected "C++: CMakeLists.txt root file" "cpp" "$scores"
assert_env_detected "CMake: CMakeLists.txt root file" "cmake" "$scores"

# .cpp file extension
output=$(run_detect $'src/main.cpp\n')
scores=$(extract_scores "$output")
assert_env_detected "C++: .cpp file extension" "cpp" "$scores"

# .cc file extension
output=$(run_detect $'src/main.cc\n')
scores=$(extract_scores "$output")
assert_env_detected "C++: .cc file extension" "cpp" "$scores"

# .hpp file extension
output=$(run_detect $'include/header.hpp\n')
scores=$(extract_scores "$output")
assert_env_detected "C++: .hpp file extension" "cpp" "$scores"

# .h file extension
output=$(run_detect $'include/header.h\n')
scores=$(extract_scores "$output")
assert_env_detected "C++: .h file extension" "cpp" "$scores"

# .cmake file extension
output=$(run_detect $'cmake/FindFoo.cmake\n')
scores=$(extract_scores "$output")
assert_env_detected "CMake: .cmake file extension" "cmake" "$scores"

# =========================================================================
# RUST
# =========================================================================
echo "--- Rust ---"

# Cargo.toml root file
output=$(run_detect "" "Cargo.toml")
scores=$(extract_scores "$output")
assert_env_detected "Rust: Cargo.toml root file" "rust" "$scores"

# .rs file extension
output=$(run_detect $'src/main.rs\nlib.rs\n')
scores=$(extract_scores "$output")
assert_env_detected "Rust: .rs file extensions" "rust" "$scores"

# Combined root + extensions
output=$(run_detect $'src/main.rs\n' "Cargo.toml")
scores=$(extract_scores "$output")
assert_env_min_score "Rust: root + extension combined" "rust" 4 "$scores"

# =========================================================================
# GO
# =========================================================================
echo "--- Go ---"

# go.mod root file
output=$(run_detect "" "go.mod")
scores=$(extract_scores "$output")
assert_env_detected "Go: go.mod root file" "go" "$scores"

# .go file extension
output=$(run_detect $'main.go\npkg/handler.go\n')
scores=$(extract_scores "$output")
assert_env_detected "Go: .go file extensions" "go" "$scores"

# Combined root + extensions
output=$(run_detect $'main.go\npkg/handler.go\n' "go.mod")
scores=$(extract_scores "$output")
assert_env_min_score "Go: root + extensions combined" "go" 5 "$scores"

# =========================================================================
# C# (NEW)
# =========================================================================
echo "--- C# ---"

# .csproj root file
output=$(run_detect "" "MyApp.csproj")
scores=$(extract_scores "$output")
assert_env_detected "C#: .csproj root file" "c-sharp" "$scores"

# .sln root file
output=$(run_detect "" "MyApp.sln")
scores=$(extract_scores "$output")
assert_env_detected "C#: .sln root file" "c-sharp" "$scores"

# .cs file extension
output=$(run_detect $'Program.cs\nModels/User.cs\n')
scores=$(extract_scores "$output")
assert_env_detected "C#: .cs file extensions" "c-sharp" "$scores"

# Properties/ directory pattern
output=$(run_detect $'Properties/AssemblyInfo.cs\n')
scores=$(extract_scores "$output")
assert_env_detected "C#: Properties/ directory pattern" "c-sharp" "$scores"

# obj/ directory pattern
output=$(run_detect $'obj/Debug/net6.0/app.dll\n')
scores=$(extract_scores "$output")
assert_env_detected "C#: obj/ directory pattern" "c-sharp" "$scores"

# Combined root + extensions + directory
output=$(run_detect $'Program.cs\nProperties/launchSettings.json\n' "MyApp.csproj")
scores=$(extract_scores "$output")
assert_env_min_score "C#: root + extension + dir combined" "c-sharp" 5 "$scores"

# C# should not trigger other languages
output=$(run_detect $'Program.cs\n' "MyApp.csproj")
scores=$(extract_scores "$output")
assert_env_not_detected "C#: no python" "python" "$scores"
assert_env_not_detected "C#: no java" "java" "$scores"

# =========================================================================
# DART (NEW)
# =========================================================================
echo "--- Dart ---"

# pubspec.yaml root file (without flutter)
workdir="$TMPDIR_BASE/workdir"
rm -rf "$workdir" && mkdir -p "$workdir"
echo "name: my_dart_app" > "$workdir/pubspec.yaml"
output=$(cd "$workdir" && printf 'bin/main.dart\n' | "$DETECT_SCRIPT" --files-stdin --reviewguides-dir "$GUIDES_DIR" 2>/dev/null) || true
scores=$(extract_scores "$output")
assert_env_detected "Dart: pubspec.yaml root file" "dart" "$scores"
assert_env_not_detected "Dart: no flutter without flutter dep" "flutter" "$scores"

# .dart file extension
output=$(run_detect $'bin/main.dart\nlib/utils.dart\n')
scores=$(extract_scores "$output")
assert_env_detected "Dart: .dart file extensions" "dart" "$scores"

# lib/*.dart triggers flutter directory pattern
output=$(run_detect $'lib/main.dart\nlib/widgets/button.dart\n')
scores=$(extract_scores "$output")
assert_env_detected "Dart: lib/*.dart directory pattern" "dart" "$scores"

# =========================================================================
# FLUTTER (NEW)
# =========================================================================
echo "--- Flutter ---"

# pubspec.yaml with flutter dependency
workdir="$TMPDIR_BASE/workdir"
rm -rf "$workdir" && mkdir -p "$workdir"
cat > "$workdir/pubspec.yaml" <<'YAML'
name: my_flutter_app
dependencies:
  flutter:
    sdk: flutter
YAML
output=$(cd "$workdir" && printf 'lib/main.dart\n' | "$DETECT_SCRIPT" --files-stdin --reviewguides-dir "$GUIDES_DIR" 2>/dev/null) || true
scores=$(extract_scores "$output")
assert_env_detected "Flutter: pubspec.yaml with flutter dep" "flutter" "$scores"
assert_env_detected "Flutter: also detects dart" "dart" "$scores"

# pubspec.yaml with flutter_ package reference
workdir="$TMPDIR_BASE/workdir"
rm -rf "$workdir" && mkdir -p "$workdir"
cat > "$workdir/pubspec.yaml" <<'YAML'
name: my_app
dependencies:
  flutter_bloc: ^8.0.0
YAML
output=$(cd "$workdir" && printf 'lib/main.dart\n' | "$DETECT_SCRIPT" --files-stdin --reviewguides-dir "$GUIDES_DIR" 2>/dev/null) || true
scores=$(extract_scores "$output")
assert_env_detected "Flutter: pubspec.yaml with flutter_ package" "flutter" "$scores"

# lib/*.dart directory pattern boosts flutter
output=$(run_detect $'lib/main.dart\nlib/screens/home.dart\n')
scores=$(extract_scores "$output")
assert_env_detected "Flutter: lib/*.dart directory pattern" "flutter" "$scores"

# Full flutter project (high combined score)
workdir="$TMPDIR_BASE/workdir"
rm -rf "$workdir" && mkdir -p "$workdir"
cat > "$workdir/pubspec.yaml" <<'YAML'
name: my_flutter_app
dependencies:
  flutter:
    sdk: flutter
YAML
output=$(cd "$workdir" && printf 'lib/main.dart\nlib/screens/home.dart\nlib/widgets/button.dart\n' | "$DETECT_SCRIPT" --files-stdin --reviewguides-dir "$GUIDES_DIR" 2>/dev/null) || true
scores=$(extract_scores "$output")
assert_env_min_score "Flutter: full project high score" "flutter" 5 "$scores"
assert_env_min_score "Flutter: dart also high" "dart" 5 "$scores"

# =========================================================================
# SWIFT (NEW)
# =========================================================================
echo "--- Swift ---"

# Package.swift root file
output=$(run_detect "" "Package.swift")
scores=$(extract_scores "$output")
assert_env_detected "Swift: Package.swift root file" "swift" "$scores"

# .swift file extension
output=$(run_detect $'Sources/App.swift\nSources/Utils.swift\n')
scores=$(extract_scores "$output")
assert_env_detected "Swift: .swift file extensions" "swift" "$scores"

# Package.swift should NOT trigger iOS (server-side Swift)
output=$(run_detect $'Sources/App.swift\n' "Package.swift")
scores=$(extract_scores "$output")
assert_env_detected "Swift: Package.swift detects swift" "swift" "$scores"
assert_env_not_detected "Swift: Package.swift alone is not iOS" "ios" "$scores"

# =========================================================================
# iOS (NEW)
# =========================================================================
echo "--- iOS ---"

# .xcodeproj root directory
output=$(run_detect "" "MyApp.xcodeproj/project.pbxproj")
scores=$(extract_scores "$output")
assert_env_detected "iOS: .xcodeproj root" "ios" "$scores"
assert_env_detected "iOS: .xcodeproj also detects swift" "swift" "$scores"

# .xcworkspace root directory
output=$(run_detect "" "MyApp.xcworkspace/contents.xcworkspacedata")
scores=$(extract_scores "$output")
assert_env_detected "iOS: .xcworkspace root" "ios" "$scores"

# ios/ directory pattern
output=$(run_detect $'ios/Runner/AppDelegate.swift\n')
scores=$(extract_scores "$output")
assert_env_detected "iOS: ios/ directory pattern" "ios" "$scores"

# Pods/ directory pattern
output=$(run_detect $'Pods/Alamofire/Source.swift\n')
scores=$(extract_scores "$output")
assert_env_detected "iOS: Pods/ directory pattern" "ios" "$scores"

# xcodeproj file in file list
output=$(run_detect $'MyApp.xcodeproj/project.pbxproj\nSources/App.swift\n')
scores=$(extract_scores "$output")
assert_env_detected "iOS: xcodeproj in file list" "ios" "$scores"

# .swift + xcodeproj = iOS (not just swift)
output=$(run_detect $'ViewController.swift\n' "MyApp.xcodeproj/project.pbxproj")
scores=$(extract_scores "$output")
assert_env_detected "iOS: swift + xcodeproj" "ios" "$scores"
assert_env_detected "iOS: swift also detected" "swift" "$scores"

# Full iOS project (high combined score)
output=$(run_detect $'MyApp.xcodeproj/project.pbxproj\nSources/App.swift\nSources/ViewController.swift\nPods/Alamofire/Source.swift\n' "MyApp.xcodeproj/project.pbxproj")
scores=$(extract_scores "$output")
assert_env_min_score "iOS: full project high score" "ios" 5 "$scores"

# =========================================================================
# CROSS-ENVIRONMENT / ISOLATION TESTS
# =========================================================================
echo "--- Cross-environment / Isolation ---"

# Empty input = no environments
output=$(run_detect "")
scores=$(extract_scores "$output")
assert_no_envs "Empty input: no environments detected" "$scores"

# Unrecognized extensions produce no scores
output=$(run_detect $'readme.md\nLICENSE\ndata.json\nconfig.yaml\n')
scores=$(extract_scores "$output")
assert_no_envs "Non-code files: no environments detected" "$scores"

# Mixed project detects multiple environments correctly
output=$(run_detect $'app.py\nsrc/main.ts\naiscripts/build.sh\n' "pyproject.toml" "package.json")
scores=$(extract_scores "$output")
assert_env_detected "Mixed: python detected" "python" "$scores"
assert_env_detected "Mixed: typescript detected" "typescript" "$scores"
assert_env_detected "Mixed: bash detected" "bash" "$scores"
assert_env_not_detected "Mixed: no rust" "rust" "$scores"
assert_env_not_detected "Mixed: no go" "go" "$scores"

# Flutter project should NOT detect android/kotlin
workdir="$TMPDIR_BASE/workdir"
rm -rf "$workdir" && mkdir -p "$workdir"
cat > "$workdir/pubspec.yaml" <<'YAML'
name: flutter_app
dependencies:
  flutter:
    sdk: flutter
YAML
output=$(cd "$workdir" && printf 'lib/main.dart\n' | "$DETECT_SCRIPT" --files-stdin --reviewguides-dir "$GUIDES_DIR" 2>/dev/null) || true
scores=$(extract_scores "$output")
assert_env_not_detected "Flutter project: no android" "android" "$scores"
assert_env_not_detected "Flutter project: no kotlin" "kotlin" "$scores"

# Pure Dart project (no flutter) should NOT detect flutter
workdir="$TMPDIR_BASE/workdir"
rm -rf "$workdir" && mkdir -p "$workdir"
echo "name: dart_cli" > "$workdir/pubspec.yaml"
output=$(cd "$workdir" && printf 'bin/main.dart\n' | "$DETECT_SCRIPT" --files-stdin --reviewguides-dir "$GUIDES_DIR" 2>/dev/null) || true
scores=$(extract_scores "$output")
assert_env_detected "Pure Dart: dart detected" "dart" "$scores"
assert_env_not_detected "Pure Dart: no flutter" "flutter" "$scores"

# =========================================================================
# SCORE ORDERING
# =========================================================================
echo "--- Score ordering ---"

# Verify scores are output in descending order
output=$(run_detect $'app.py\napp.py\napp.py\ninstall.sh\n' "pyproject.toml")
scores=$(extract_scores "$output")
TOTAL=$((TOTAL + 1))
prev_score=999999
ordered=true
while IFS='|' read -r env score; do
    [[ -z "$env" ]] && continue
    if [[ "$score" -gt "$prev_score" ]]; then
        ordered=false
        break
    fi
    prev_score="$score"
done <<< "$scores"
if [[ "$ordered" == true ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Scores not in descending order"
    echo "  Got: $(echo "$scores" | tr '\n' ' ')"
fi

# =========================================================================
# OUTPUT FORMAT
# =========================================================================
echo "--- Output format ---"

output=$(run_detect $'src/main.rs\n' "Cargo.toml")

# Has ENV_SCORES header
TOTAL=$((TOTAL + 1))
if echo "$output" | grep -q "^ENV_SCORES$"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Missing ENV_SCORES header"
fi

# Has --- separator
TOTAL=$((TOTAL + 1))
if echo "$output" | grep -q "^---$"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Missing --- separator"
fi

# Has REVIEW_GUIDES header
TOTAL=$((TOTAL + 1))
if echo "$output" | grep -q "^REVIEW_GUIDES$"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Missing REVIEW_GUIDES header"
fi

# Score lines match format: env|number
TOTAL=$((TOTAL + 1))
bad_format=false
while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    if ! [[ "$line" =~ ^[a-z_-]+\|[0-9]+$ ]]; then
        bad_format=true
        echo "FAIL: Bad score format: '$line'"
        break
    fi
done <<< "$scores"
if [[ "$bad_format" == false ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
fi

# --- Cleanup ---
teardown_tmpdir

# --- Summary ---
echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
