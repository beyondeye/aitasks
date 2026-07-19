#!/usr/bin/env bash
# test_tui_clipboard_seam.sh — guard for the canonical TUI clipboard seam.
#
# All Textual TUI copy actions must route through
# `lib/tui_clipboard.copy_to_system_clipboard` — never call Textual's
# `copy_to_clipboard` directly. A direct call emits only a bare OSC 52 escape,
# which tmux forwards to the outer terminal ONLY for panes in the client's
# visible window; from a background window (or a session with no attached
# terminal client) the text lands in a tmux paste buffer and the system
# clipboard is silently left untouched. The seam helper adds the
# `load-buffer -w` gateway forward that works regardless of pane visibility.
#
# Detection scope: a `.copy_to_clipboard(` attribute call in any `*.py` under
# `.aitask-scripts/` outside the seam module itself (which owns the one
# sanctioned direct call). Prose/docstring mentions without the call parens do
# not match. Also runs the seam's python unit tests.
#
# Run: bash tests/test_tui_clipboard_seam.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

SEAM_MODULE=".aitask-scripts/lib/tui_clipboard.py"
PATTERN='\.copy_to_clipboard\('

# scan_dir ROOT — emit "<relpath>:<line>:<text>" for each direct
# copy_to_clipboard call in a non-seam .py file under ROOT/.aitask-scripts.
scan_dir() {
  local root="$1" f rel
  while IFS= read -r -d '' f; do
    rel="${f#"$root"/}"
    [[ "$rel" == "$SEAM_MODULE" ]] && continue
    grep -nE "$PATTERN" "$f" 2>/dev/null | sed "s|^|$rel:|"
  done < <(find "$root/.aitask-scripts" -type f -name '*.py' -print0)
}

# --- Test 1: the real tree is clean ----------------------------------------
violations="$(scan_dir "$PROJECT_DIR")"
TOTAL=$((TOTAL + 1))
if [[ -z "$violations" ]]; then
  PASS=$((PASS + 1))
else
  FAIL=$((FAIL + 1))
  echo "FAIL: direct copy_to_clipboard call(s) outside the clipboard seam:"
  printf '  DIRECT COPY: %s\n' "$violations"
  echo "  -> route through lib/tui_clipboard.copy_to_system_clipboard(app, text)"
fi

# --- Negative tests: the guard actually catches a regression ---------------
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/.aitask-scripts/lib"

# (2) a direct call in a NON-seam file is flagged; a docstring mention is not.
cat >"$TMP/.aitask-scripts/rogue_tui.py" <<'PY'
"""Docstring mentioning app.copy_to_clipboard without calling it."""
def handler(self):
    self.app.copy_to_clipboard("oops")
PY
neg="$(scan_dir "$TMP")"
assert_contains "negative: rogue direct call is flagged" "rogue_tui.py" "$neg"
rogue_hits="$(printf '%s\n' "$neg" | grep -c 'rogue_tui.py')"
assert_eq "only the call line is flagged, not the docstring (1 hit)" "1" "$rogue_hits"

# (3) the seam module's own direct call is NOT flagged.
cat >"$TMP/$SEAM_MODULE" <<'PY'
def copy_to_system_clipboard(app, text):
    app.copy_to_clipboard(text)
PY
neg_seam="$(scan_dir "$TMP")"
assert_not_contains "seam module's sanctioned call is not flagged" "tui_clipboard.py" "$neg_seam"

# --- Test 4: the seam's python unit tests pass ------------------------------
TOTAL=$((TOTAL + 1))
PYTHON_BIN="${AIT_PYTHON:-python3}"
if "$PYTHON_BIN" "$PROJECT_DIR/tests/test_tui_clipboard.py" >/dev/null 2>&1; then
  PASS=$((PASS + 1))
else
  FAIL=$((FAIL + 1))
  echo "FAIL: python unit tests for tui_clipboard (rerun: $PYTHON_BIN tests/test_tui_clipboard.py)"
fi

# --- Summary ---------------------------------------------------------------
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
  echo "ALL TESTS PASSED"
else
  echo "SOME TESTS FAILED"
  exit 1
fi
