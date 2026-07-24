#!/usr/bin/env bash
# test_no_lib_to_tui_import.sh — layering guard for the t1217 lib/ promotion.
#
# `.aitask-scripts/lib/` is the shared BASE layer: the TUI packages (board,
# monitor, codebrowser, …) depend on it, and it must not depend on them. Before
# t1217 that direction was inverted — `lib/work_report_gather.py` and
# `lib/trail_gather.py` each put `board/` on `sys.path` purely to import the
# shared frontmatter parser, so moving or renaming `board/task_yaml.py` silently
# broke them. t1217 moved that parser to `lib/task_yaml.py`; this test FAILS if
# any `lib/` module reaches back up into a sibling TUI package.
#
# It is a FREEZE, not a migration: the one remaining sanctioned upward reach is
# allowlisted with its reason, not rewritten.
#
# Detection scope (documented on purpose — a guard that overclaims is worse than
# one with a known boundary):
#   * A `sys.path` insert/append naming a sibling package directory, in any of
#     the idioms used in this tree: a literal `"board"` / `'board'` element, a
#     `/ "board"` pathlib join, or a `"…/board"` path fragment.
#   * NOT detected: dynamic loading via importlib/`spec_from_file_location` (how
#     `lib/shortcut_scopes.py` deliberately loads TUI modules — it is
#     allowlisted anyway), a package dir reached through a variable whose value
#     is computed at runtime, or an insert built by string concatenation.
#   * Scanned: `.aitask-scripts/lib/*.py` only. `tests/` legitimately puts TUI
#     dirs on sys.path to import the TUI under test.
#
# Run: bash tests/test_no_lib_to_tui_import.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

# --- Sibling packages lib/ must not reach into -----------------------------
# Every directory under .aitask-scripts/ that is a layer ABOVE lib/. Kept
# explicit rather than derived so adding a new TUI package is a deliberate,
# reviewed edit here.
TUI_PACKAGES=(
  agentcrew applink board brainstorm chat chatlink codebrowser
  diffviewer logview monitor settings stats syncer
)

# --- Allowlist -------------------------------------------------------------
# Entries are `<lib-relative-file>:<package>` (or `:*` for every package), each
# with the reason it is sanctioned. An entry here means "known and accepted",
# NOT "invisible" — the stats holdout below is the remaining half of the t1217
# inversion, deliberately surfaced so it stays on the radar.
ALLOWLIST=(
  "shortcut_scopes.py:*"        # reflection loader: imports every TUI module by
                                # path to sweep shortcut bindings; the sys.path
                                # setup is its entire purpose, not a dependency
  "work_report_gather.py:stats" # KNOWN remaining inversion: reuses stats_data's
                                # collect_stats/DAY_NAMES. Out of scope for
                                # t1217; repaying it empties this allowlist.
)

is_allowed() {
  local file="$1" pkg="$2" entry
  for entry in "${ALLOWLIST[@]}"; do
    [[ "$entry" == "$file:$pkg" || "$entry" == "$file:*" ]] && return 0
  done
  return 1
}

# scan_dir LIBDIR — emit "<file>:<pkg>:<line>:<text>" for each non-allowlisted
# sys.path insert of a sibling TUI package under LIBDIR. Pure-comment lines are
# dropped so prose naming a package does not trip the guard.
scan_dir() {
  local libdir="$1" f base pkg pattern
  for f in "$libdir"/*.py; do
    [[ -e "$f" ]] || continue
    base="$(basename "$f")"
    for pkg in "${TUI_PACKAGES[@]}"; do
      is_allowed "$base" "$pkg" && continue
      # A sys.path line mentioning the package as a quoted element, a pathlib
      # join, or a path fragment.
      pattern="(\"${pkg}\"|'${pkg}'|/[[:space:]]*\"${pkg}\"|/[[:space:]]*'${pkg}'|/${pkg}[\"'/])"
      grep -nE "sys\.path\.(insert|append)" "$f" 2>/dev/null \
        | grep -vE '^[0-9]+:[[:space:]]*#' \
        | grep -E "$pattern" \
        | sed "s|^|$base:$pkg:|"
      # The two-step idiom: a loop/tuple of sibling dirs fed to sys.path below.
      # Matches `for _sub in (..., "board")` / `_sub_dir = os.path.join(X, pkg)`.
      grep -nE "(for[[:space:]]+_?sub|os\.path\.join|_SCRIPTS_DIR[[:space:]]*/)" "$f" 2>/dev/null \
        | grep -vE '^[0-9]+:[[:space:]]*#' \
        | grep -E "$pattern" \
        | sed "s|^|$base:$pkg:|"
    done
  done
}

# --- Test 1: the real lib/ is clean ----------------------------------------
violations="$(scan_dir "$PROJECT_DIR/.aitask-scripts/lib" | sort -u)"
TOTAL=$((TOTAL + 1))
if [[ -z "$violations" ]]; then
  PASS=$((PASS + 1))
  echo "PASS: no lib/ module reaches into a sibling TUI package"
else
  FAIL=$((FAIL + 1))
  echo "FAIL: lib/ reaches up into a TUI package (layer inversion):"
  printf '  INVERSION: %s\n' "$violations"
  echo "  -> move the shared code down into lib/ (as t1217 did for task_yaml),"
  echo "     or, if genuinely sanctioned, add '<file>:<pkg>' to ALLOWLIST with a reason."
fi

# --- Negative controls: prove the scanner can actually fail -----------------
# Without these, a scanner whose pattern never matches anything would pass
# Test 1 forever and pin nothing.
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/lib"

# (2) a fresh lib/ module inserting board/ is flagged.
cat >"$TMP/lib/bad_module.py" <<'PY'
import os
import sys

_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_SCRIPTS_DIR, "board"))
from task_yaml import parse_frontmatter  # noqa: E402
PY
neg="$(scan_dir "$TMP/lib" | sort -u)"
assert_contains "negative: rogue lib/ module inserting board/ is flagged" \
  "bad_module.py" "$neg"
assert_contains "negative: the offending package is named in the report" \
  ":board:" "$neg"

# (3) exactly one file is flagged — the scanner is not matching indiscriminately.
neg_files="$(printf '%s\n' "$neg" | cut -d: -f1 | sort -u | grep -c .)"
assert_eq "negative: exactly one file flagged" "1" "$neg_files"

# (4) an allowlisted file making the SAME reach is not flagged.
cp "$TMP/lib/bad_module.py" "$TMP/lib/shortcut_scopes.py"
neg_allow="$(scan_dir "$TMP/lib" | sort -u)"
assert_not_contains "allowlisted reflection loader is not flagged" \
  "shortcut_scopes.py" "$neg_allow"

# (5) allowlisting is per-package, not per-file: work_report_gather.py may
#     reach `stats`, but reaching `board` is still a violation.
cat >"$TMP/lib/work_report_gather.py" <<'PY'
import os
import sys

_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _sub in ("stats",):
    sys.path.insert(0, os.path.join(_SCRIPTS_DIR, _sub))
PY
neg_stats="$(scan_dir "$TMP/lib" | sort -u)"
assert_not_contains "allowlisted work_report_gather.py -> stats is not flagged" \
  "work_report_gather.py" "$neg_stats"

cat >"$TMP/lib/work_report_gather.py" <<'PY'
import os
import sys

_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_SCRIPTS_DIR, "board"))
PY
neg_board="$(scan_dir "$TMP/lib" | sort -u)"
assert_contains "allowlist is per-package: work_report_gather.py -> board IS flagged" \
  "work_report_gather.py:board" "$neg_board"

# (6) prose / comments naming a package do not trip the guard.
rm -f "$TMP/lib/bad_module.py" "$TMP/lib/work_report_gather.py" \
      "$TMP/lib/shortcut_scopes.py"
cat >"$TMP/lib/innocent.py" <<'PY'
import sys

# sys.path.insert(0, "board")  <- a comment must NOT trip the guard
TUI_NAMES = ("board", "monitor")  # a data tuple must NOT trip the guard
sys.path.insert(0, "/some/other/place")
PY
neg_prose="$(scan_dir "$TMP/lib" | sort -u)"
assert_eq "comments and data tuples do not trip the guard" "" "$neg_prose"

# --- Test 7: task_yaml lives in lib/, not board/ ---------------------------
# The concrete t1217 postcondition, asserted directly rather than inferred.
assert_file_exists "task_yaml.py lives in lib/" \
  "$PROJECT_DIR/.aitask-scripts/lib/task_yaml.py"
assert_file_not_exists "task_yaml.py no longer lives in board/" \
  "$PROJECT_DIR/.aitask-scripts/board/task_yaml.py"

# --- Summary ---------------------------------------------------------------
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
  echo "ALL TESTS PASSED"
else
  echo "SOME TESTS FAILED"
  exit 1
fi
