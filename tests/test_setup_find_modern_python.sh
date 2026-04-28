#!/usr/bin/env bash
# test_setup_find_modern_python.sh - Unit tests for find_modern_python()
# Run: bash tests/test_setup_find_modern_python.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected '$expected', got '$actual')"
    fi
}

assert_contains() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -q "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected', got '$actual')"
    fi
}

# Source setup script for function access
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" --source-only
set +euo pipefail

SCRATCH="$(mktemp -d)"
trap 'rm -rf "$SCRATCH"' EXIT
mkdir -p "$SCRATCH/bin" "$SCRATCH/home/.aitask/python/3.13/bin"

# Stub generator — fakes --version and -c "import sys; sys.exit(0 if sys.version_info >= (M, m) else 1)"
make_stub() {
    local path="$1" version="$2"
    local stub_major stub_minor
    stub_major="${version%%.*}"
    stub_minor="$(echo "$version" | cut -d. -f2)"
    cat > "$path" <<EOF
#!/usr/bin/env bash
case "\$1" in
  --version) echo "Python $version" ;;
  -c)
    shift
    if echo "\$1" | grep -qE 'sys.version_info >= \(([0-9]+), ([0-9]+)\)'; then
        req_major="\$(echo "\$1" | sed -E 's/.*>= \(([0-9]+), [0-9]+\).*/\1/')"
        req_minor="\$(echo "\$1" | sed -E 's/.*>= \([0-9]+, ([0-9]+)\).*/\1/')"
        if [[ $stub_major -gt \$req_major ]] || \
           { [[ $stub_major -eq \$req_major ]] && [[ $stub_minor -ge \$req_minor ]]; }; then
            exit 0
        else
            exit 1
        fi
    fi
    ;;
esac
EOF
    chmod +x "$path"
}

echo "=== find_modern_python tests ==="
echo ""

# Test 1: impossibly-high min version → empty (regardless of system python)
echo "--- Test 1: unsatisfiable min returns empty ---"
out="$(PATH="$SCRATCH/bin:/usr/bin:/bin" HOME="$SCRATCH/home" find_modern_python 99.0)"
assert_eq "empty when no candidate satisfies min" "" "$out"

# Test 2: python3.13 stub on PATH → returned
echo "--- Test 2: python3.13 on PATH is selected ---"
make_stub "$SCRATCH/bin/python3.13" "3.13.1"
out="$(PATH="$SCRATCH/bin:/usr/bin:/bin" HOME="$SCRATCH/home" find_modern_python 3.11)"
assert_contains "python3.13 picked up via PATH" "python3.13" "$out"

# Test 3: python3.11 stub that lies (reports 3.9) → rejected
echo "--- Test 3: spoofed version is rejected ---"
rm -f "$SCRATCH/bin/python3.13"
make_stub "$SCRATCH/bin/python3.11" "3.9.0"
# Also make a python3 stub reporting 3.9 so the trailing fallback doesn't accept it
make_stub "$SCRATCH/bin/python3" "3.9.0"
out="$(PATH="$SCRATCH/bin:/usr/bin:/bin" HOME="$SCRATCH/home" find_modern_python 3.11)"
assert_eq "spoofed python3.11 reporting 3.9 is rejected" "" "$out"

# Test 4: ~/.aitask/python/3.13/bin/python3 takes priority over PATH
echo "--- Test 4: uv-installed path preferred over PATH ---"
rm -f "$SCRATCH/bin/python3.11" "$SCRATCH/bin/python3"
make_stub "$SCRATCH/bin/python3.13" "3.13.1"
make_stub "$SCRATCH/home/.aitask/python/3.13/bin/python3" "3.13.2"
out="$(AIT_VENV_PYTHON_PREFERRED=3.13 PATH="$SCRATCH/bin:/usr/bin:/bin" HOME="$SCRATCH/home" find_modern_python 3.11)"
assert_contains "uv-installed path preferred over PATH" "$SCRATCH/home/.aitask/python/3.13/bin/python3" "$out"

# Test 5: ~/.aitask/bin/python3 (t695_3 symlink target) takes priority over uv path
echo "--- Test 5: framework bin/python3 has highest priority ---"
mkdir -p "$SCRATCH/home/.aitask/bin"
make_stub "$SCRATCH/home/.aitask/bin/python3" "3.13.5"
out="$(AIT_VENV_PYTHON_PREFERRED=3.13 PATH="$SCRATCH/bin:/usr/bin:/bin" HOME="$SCRATCH/home" find_modern_python 3.11)"
assert_contains "framework bin/python3 wins" "$SCRATCH/home/.aitask/bin/python3" "$out"

# Test 6: respects min argument (no candidates satisfy min=4.0)
echo "--- Test 6: min argument is enforced ---"
rm -rf "$SCRATCH/home/.aitask"
out="$(PATH="$SCRATCH/bin:/usr/bin:/bin" HOME="$SCRATCH/home" find_modern_python 4.0)"
assert_eq "no python satisfies min=4.0" "" "$out"

echo ""
echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
[[ $FAIL -eq 0 ]] || exit 1
