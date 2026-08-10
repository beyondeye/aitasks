#!/usr/bin/env bash
# Parity guard for the bash ANSI stripper in aitask_shadow_capture.sh (t1474).
#
# `shadow_strip_ansi` is a sed mirror of monitor/ansi_utils.py written in a
# different language. Before this file nothing automated covered it, so the two
# could diverge silently: the Python suite would stay green while pasted
# captures came back with OSC markup still in them, or worse, with visible text
# eaten. The mirror only stays a mirror if something checks.
#
# Driven through the DOCUMENTED entry point — `aitask_shadow_capture.sh -`, the
# stdin seam — not by sourcing the function. That path short-circuits before any
# tmux access (no pane to resolve, no binding to check), so this test is
# hermetic and needs no tmux server.
#
# Two assertion families per case, because either alone is insufficient:
#   * PARITY against the live Python strip_ansi. The expectation is computed by
#     running the real module, never a copied string, so drift cannot pass.
#   * ABSOLUTE properties on the real fixture. Parity alone would be satisfied
#     if BOTH implementations broke the same way, so this is the independent
#     ground truth.
#
# Run: bash tests/test_shadow_strip_ansi.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR" || exit 1

# shellcheck source=lib/asserts.sh
source "$SCRIPT_DIR/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

CAPTURE_SH="$PROJECT_DIR/.aitask-scripts/aitask_shadow_capture.sh"
FIXTURE="$PROJECT_DIR/tests/fixtures/osc8_capture_pane.txt"
ESC=$(printf '\033')
BEL=$(printf '\007')

# --- the two implementations under comparison --------------------------------

# The bash side, via its real CLI seam.
sh_strip() { "$CAPTURE_SH" -; }

# The Python side. ansi_utils is an import-only module with no CLI or stdin
# behaviour, so we supply the adapter. Three details are load-bearing:
#   * `-c`, not a `<<'EOF'` heredoc — a heredoc would occupy stdin, the very
#     channel the test data needs.
#   * the module directory passed as argv[1] rather than interpolated into the
#     code string.
#   * a surrogateescape byte round-trip, so a capture that is not valid UTF-8
#     cannot corrupt the comparison.
PY_STRIP='import sys
sys.path.insert(0, sys.argv[1])
from ansi_utils import strip_ansi
d = sys.stdin.buffer.read().decode("utf-8", "surrogateescape")
sys.stdout.buffer.write(strip_ansi(d).encode("utf-8", "surrogateescape"))'

py_strip() { "$PY" -c "$PY_STRIP" "$PROJECT_DIR/.aitask-scripts/monitor"; }

# --- preconditions -----------------------------------------------------------
#
# Both are hard failures, never skips: this file's entire purpose is the
# cross-language comparison, so an unusable oracle means "unknown", and
# reporting unknown as PASS is exactly how a guard rots into decoration.

echo "=== Preconditions ==="

if [[ ! -f "$FIXTURE" ]]; then
    echo "FAIL: missing fixture $FIXTURE"
    exit 1
fi
echo "  OK: fixture present"

PY="$( . "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" 2>/dev/null; \
       resolve_python 2>/dev/null || true )"
if [[ -z "$PY" ]]; then
    echo "FAIL: no python interpreter resolved — the parity oracle is unavailable."
    echo "      This test cannot degrade to a skip: without the oracle there is"
    echo "      nothing to compare the sed mirror against."
    exit 1
fi
echo "  OK: python resolved ($PY)"

# Oracle self-check. Without this, an adapter that cannot import the module
# would emit an empty string and every parity assertion would compare the shell
# output against "" — passing only when the shell side was ALSO broken.
probe_in="A${ESC}]8;;u${ESC}\\B"
probe_out="$(printf '%s' "$probe_in" | py_strip 2>/dev/null)"
probe_rc=$?
if [[ "$probe_rc" -ne 0 || "$probe_out" != "AB" ]]; then
    echo "FAIL: python strip_ansi adapter unusable (rc=$probe_rc, got '$probe_out',"
    echo "      expected 'AB') — aborting rather than comparing against a blank."
    exit 1
fi
echo "  OK: oracle self-check (adapter strips a known OSC to 'AB')"

# --- parity cases ------------------------------------------------------------

echo
echo "=== Parity: sed mirror vs live Python strip_ansi ==="

check_parity() {
    local desc="$1" input="$2"
    local want got want_rc got_rc
    want="$(printf '%s' "$input" | py_strip)"; want_rc=$?
    got="$(printf '%s' "$input" | sh_strip)"; got_rc=$?
    TOTAL=$((TOTAL + 1))
    if [[ "$want_rc" -ne 0 || "$got_rc" -ne 0 ]]; then
        FAIL=$((FAIL + 1))
        echo "  FAIL: $desc (python rc=$want_rc, shell rc=$got_rc) — a crashed"
        echo "        side must never read as agreement"
    elif [[ "$want" == "$got" ]]; then
        PASS=$((PASS + 1))
        echo "  PASS: $desc"
    else
        FAIL=$((FAIL + 1))
        echo "  FAIL: $desc"
        echo "        python: $(printf '%s' "$want" | od -c | head -3)"
        echo "        shell : $(printf '%s' "$got" | od -c | head -3)"
    fi
}

# The real capture, read from the shared fixture (same artifact the Python test
# asserts against).
FIXTURE_BYTES="$(cat "$FIXTURE")"

check_parity "real tmux OSC 8 capture (fixture)" "$FIXTURE_BYTES"
check_parity "OSC with BEL terminator" "${ESC}]0;window title${BEL}after"
check_parity "unterminated OSC (fail-safe: must not eat trailing text)" \
    "${ESC}]8;;http://truncated VISIBLE text"
check_parity "CSI colour run (regression)" \
    "${ESC}[31mRED${ESC}[0m plain ${ESC}[1;32mGREEN${ESC}[m"
check_parity "OSC immediately followed by CSI" \
    "${ESC}]8;;http://x${ESC}\\LINK${ESC}]8;;${ESC}\\ ${ESC}[31mRED${ESC}[0m"

# --- absolute properties on the real fixture ---------------------------------
#
# Independent of the Python side: if both implementations regressed identically,
# parity above would still pass and only these would catch it.

echo
echo "=== Absolute: the fixture's visible text survives, its markup does not ==="

fixture_out="$(printf '%s' "$FIXTURE_BYTES" | sh_strip)"
# Argument order is (desc, needle, haystack) — see tests/lib/asserts.sh. Passing
# them the other way round makes the assertion vacuous rather than wrong, so it
# passes forever and silently; that mistake was caught here only because the
# parity test was run against a deliberately broken mirror.
assert_eq "fixture strips to exactly its visible text" "LINKTEXT" "$fixture_out"
assert_not_contains "no ESC byte survives" "$ESC" "$fixture_out"
assert_not_contains "no hyperlink URL survives" "example.com" "$fixture_out"

# Positive control: the untouched bytes must NOT already equal the expected
# output, or the assertions above would pass on a no-op implementation.
TOTAL=$((TOTAL + 1))
if [[ "$FIXTURE_BYTES" != "$fixture_out" ]]; then
    PASS=$((PASS + 1))
    echo "  PASS: positive control (raw fixture differs from stripped output)"
else
    FAIL=$((FAIL + 1))
    echo "  FAIL: positive control — raw fixture already equals the stripped"
    echo "        output, so this file would pass without stripping anything"
fi

# Note: comparison is on a fixture with no trailing whitespace and no trailing
# blank lines, because `shadow_clean` (the pipeline `-` runs) additionally
# right-trims lines and drops trailing blanks. tmux does not pad captured lines,
# so a real capture satisfies that naturally.

echo
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
if [[ "$FAIL" -eq 0 ]]; then echo "All tests PASSED"; else echo "SOME TESTS FAILED"; fi
exit $(( FAIL > 0 ? 1 : 0 ))
