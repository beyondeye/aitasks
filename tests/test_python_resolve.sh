#!/usr/bin/env bash
# test_python_resolve.sh - Tests for lib/python_resolve.sh
# Run: bash tests/test_python_resolve.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LIB="$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

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
        echo "FAIL: $desc"
        echo "  expected: $expected"
        echo "  actual:   $actual"
    fi
}

assert_contains() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -q "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc"
        echo "  expected to contain: $expected"
        echo "  actual:              $actual"
    fi
}

# Resolve a real Python interpreter on the host for stub delegation
REAL_PY="$(command -v python3)"
[[ -z "$REAL_PY" ]] && { echo "No python3 on host; cannot run tests."; exit 2; }

SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/test_python_resolve.XXXXXX")"
trap 'rm -rf "$SCRATCH"' EXIT

mkdir -p "$SCRATCH/bin" "$SCRATCH/.aitask/bin" "$SCRATCH/.aitask/venv/bin"

# Tests run subshells with a custom PATH = $SCRATCH/bin + standard sysbin so
# stubs win for python3 lookups but coreutils / awk are still available.
SUBPATH="$SCRATCH/bin:/usr/bin:/bin"

# make_stub <name> <reported_version>
# Creates a stub script that:
#   --version   -> echoes "Python <ver>"
#   -c <code>   -> delegates to the real python3 with sys.version_info patched
#                  to <ver> via a wrapper, so version-info checks see <ver>
make_stub() {
    local name="$1" ver="$2"
    local path="$SCRATCH/bin/$name"
    cat > "$path" <<STUB
#!/usr/bin/env bash
case "\$1" in
  --version) echo "Python $ver" ;;
  -c)
    shift
    code="\$1"
    real_py='$REAL_PY'
    "\$real_py" -c "
import sys
parts = '$ver'.split('.')
major = int(parts[0])
minor = int(parts[1]) if len(parts) > 1 else 0
patch = int(parts[2]) if len(parts) > 2 else 0
class _VI(tuple):
    @property
    def major(self): return self[0]
    @property
    def minor(self): return self[1]
    @property
    def micro(self): return self[2]
sys.version_info = _VI((major, minor, patch, 'final', 0))
exec(compile('''\$code''', '<stub>', 'exec'))
"
    ;;
  *) echo "stub:$name:$ver:\$@" ;;
esac
STUB
    chmod +x "$path"
}

# === Test 1: system python3 only (PATH-resolved) ===
unset AIT_PYTHON _AIT_RESOLVED_PYTHON
make_stub python3 "3.9.0"
rm -f "$SCRATCH/.aitask/bin/python3" "$SCRATCH/.aitask/venv/bin/python"
result="$(HOME="$SCRATCH" PATH="$SUBPATH" /usr/bin/bash --noprofile --norc -c "
unset _AIT_RESOLVED_PYTHON AIT_PYTHON
source '$LIB'
resolve_python
")"
assert_eq "Test 1: system python3 fallback" "$SCRATCH/bin/python3" "$result"

# === Test 2: AIT_PYTHON override wins over system ===
make_stub aitpy "3.13.0"
result="$(HOME="$SCRATCH" AIT_PYTHON="$SCRATCH/bin/aitpy" PATH="$SUBPATH" /usr/bin/bash --noprofile --norc -c "
unset _AIT_RESOLVED_PYTHON
source '$LIB'
resolve_python
")"
assert_eq "Test 2: AIT_PYTHON override" "$SCRATCH/bin/aitpy" "$result"

# === Test 3: ~/.aitask/bin/python3 wins over system, when AIT_PYTHON unset ===
ln -sf "$SCRATCH/bin/aitpy" "$SCRATCH/.aitask/bin/python3"
result="$(HOME="$SCRATCH" PATH="$SUBPATH" /usr/bin/bash --noprofile --norc -c "
unset AIT_PYTHON _AIT_RESOLVED_PYTHON
source '$LIB'
resolve_python
")"
assert_eq "Test 3: ~/.aitask/bin/python3 precedence" "$SCRATCH/.aitask/bin/python3" "$result"

# === Test 4: cache test — second call returns the same value even if target is removed ===
# Note: we redirect resolve_python to tempfiles instead of using command
# substitution, because $(...) runs in a subshell and the cached
# _AIT_RESOLVED_PYTHON would not propagate back to the parent.
ln -sf "$SCRATCH/bin/aitpy" "$SCRATCH/.aitask/bin/python3"
result="$(HOME="$SCRATCH" PATH="$SUBPATH" /usr/bin/bash --noprofile --norc -c "
unset AIT_PYTHON _AIT_RESOLVED_PYTHON
source '$LIB'
resolve_python > '$SCRATCH/first.txt'
rm -f '$SCRATCH/.aitask/bin/python3'
resolve_python > '$SCRATCH/second.txt'
first=\$(cat '$SCRATCH/first.txt')
second=\$(cat '$SCRATCH/second.txt')
if [[ \"\$first\" == \"\$second\" ]]; then echo MATCH; else echo \"MISMATCH:\$first vs \$second\"; fi
")"
assert_eq "Test 4: cache stable across calls" "MATCH" "$result"

# === Test 5: require_modern_python rejects too-old ===
make_stub python3 "3.9.0"
rm -f "$SCRATCH/.aitask/bin/python3" "$SCRATCH/.aitask/venv/bin/python"
output="$(HOME="$SCRATCH" PATH="$SUBPATH" /usr/bin/bash --noprofile --norc -c "
unset AIT_PYTHON _AIT_RESOLVED_PYTHON
source '$LIB'
require_modern_python 3.11
" 2>&1 || true)"
assert_contains "Test 5: require_modern_python rejects 3.9" "Python >=3.11 required" "$output"

# === Test 6: require_modern_python accepts a sufficient version ===
make_stub python3 "3.13.0"
rm -f "$SCRATCH/.aitask/bin/python3" "$SCRATCH/.aitask/venv/bin/python"
result="$(HOME="$SCRATCH" PATH="$SUBPATH" /usr/bin/bash --noprofile --norc -c "
unset AIT_PYTHON _AIT_RESOLVED_PYTHON
source '$LIB'
require_modern_python 3.11
")"
assert_eq "Test 6: require_modern_python accepts 3.13" "$SCRATCH/bin/python3" "$result"

# === Test 7: require_python dies when nothing resolvable ===
rm -f "$SCRATCH/.aitask/bin/python3" "$SCRATCH/.aitask/venv/bin/python"
output="$(HOME="$SCRATCH" PATH="/usr/bin:/bin" /usr/bin/bash --noprofile --norc -c "
unset AIT_PYTHON _AIT_RESOLVED_PYTHON
# Hide /usr/bin/python3 too by switching to a totally-empty bin path that lacks python
PATH='$SCRATCH/empty:/usr/bin:/bin'
# Move python3 out of the way for this subshell
hash -r
source '$LIB'
# Override _AIT_RESOLVED_PYTHON path checks: force lookup to skip system
unset PATH
PATH=/nonexistent
require_python
" 2>&1 || true)"
assert_contains "Test 7: require_python dies when no Python" "No Python interpreter found" "$output"

# === Test 8: double-source guard ===
result="$(/usr/bin/bash --noprofile --norc -c "
source '$LIB'
source '$LIB'
declare -F resolve_python >/dev/null && echo OK || echo MISSING
")"
assert_eq "Test 8: double-source guard preserves function" "OK" "$result"

echo ""
echo "Tests: $TOTAL  Pass: $PASS  Fail: $FAIL"
if (( FAIL > 0 )); then
    exit 1
fi
