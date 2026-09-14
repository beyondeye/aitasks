#!/usr/bin/env bash
# test_codex_config_tui_seed.sh - the Codex `[tui] animations = false` seed (t1797).
#
# codex-cli 0.154.0 animates a Braille "starfield" around the idle composer,
# which keeps `ait monitor` / `ait minimonitor` from ever reading an idle Codex
# pane as idle. Framework launches carry `-c tui.animations=false`
# (tests/test_codeagent.sh Test 11e); this file pins the per-project layer:
# the seed carries the key, and merge_codex_settings ADDS it when absent but
# never overrides an explicit project value — the precedence the docs state.
#
# Drives the REAL merge via `aitask_setup.sh --source-only`, like Group D of
# tests/test_session_hook_install.sh. Assertions run in THIS shell (no `( … )`
# groups), so the in-process PASS/FAIL counters stay authoritative.
#
# Run: bash tests/test_codex_config_tui_seed.sh

set -uo pipefail

PASS=0
FAIL=0
# shellcheck disable=SC2034  # TOTAL is mutated by the sourced asserts.sh helpers.
TOTAL=0

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

SEED="$PROJECT_DIR/seed/codex_config.seed.toml"
TESTROOT="$(mktemp -d)"
trap 'rm -rf "$TESTROOT"' EXIT

# tui_get <file> <key> — repr of [tui].<key>, or ABSENT / NO_TUI / INVALID:<why>.
tui_get() {
    python3 - "$1" "$2" <<'PY'
import sys, tomllib
try:
    d = tomllib.load(open(sys.argv[1], "rb"))
except Exception as e:
    print("INVALID: %s" % e)
    raise SystemExit(0)
tui = d.get("tui")
if not isinstance(tui, dict):
    print("NO_TUI")
    raise SystemExit(0)
print(repr(tui[sys.argv[2]]) if sys.argv[2] in tui else "ABSENT")
PY
}

# toml_get <file> <dotted.key> — repr of a top-level/nested value.
toml_get() {
    python3 - "$1" "$2" <<'PY'
import sys, tomllib
d = tomllib.load(open(sys.argv[1], "rb"))
for part in sys.argv[2].split("."):
    d = d[part]
print(repr(d))
PY
}

# merge_fixture <name> <existing config content> — prints the merged file path.
merge_fixture() {
    local dir="$TESTROOT/$1"
    mkdir -p "$dir/.aitask-scripts" "$dir/.codex"
    printf '%s' "$2" >"$dir/.codex/config.toml"
    merge_codex_settings "$SEED" "$dir/.codex/config.toml" >/dev/null 2>&1
    echo "$dir/.codex/config.toml"
}

echo "=== Codex [tui] animations seed (t1797) ==="

echo ""
echo "--- Group 0: the seed and this repo's own config carry the key ---"
assert_eq "0: the seed sets [tui] animations = false" "False" "$(tui_get "$SEED" animations)"
assert_eq "0: this repo's .codex/config.toml sets it too" "False" \
    "$(tui_get "$PROJECT_DIR/.codex/config.toml" animations)"

# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" --source-only
# Sourcing turns errexit/nounset ON in this shell; relax them as the sibling
# setup tests do, so a failing probe reports instead of aborting the suite.
set +eu

echo ""
echo "--- Group 1: an existing [tui] table gains the key, keeping its own ---"
CFG1="$(merge_fixture g1_pet '[tui]
pet = "disabled"
')"
assert_eq "1: animations is added to the user's [tui]" "False" "$(tui_get "$CFG1" animations)"
assert_eq "1: the user's [tui] pet survives" "'disabled'" "$(tui_get "$CFG1" pet)"

echo ""
echo "--- Group 2: an explicit project value WINS (default only when absent) ---"
CFG2="$(merge_fixture g2_explicit '[tui]
animations = true
')"
assert_eq "2: an explicit animations = true is kept" "True" "$(tui_get "$CFG2" animations)"

echo ""
echo "--- Group 3: a config with no [tui] gets the table ---"
CFG3="$(merge_fixture g3_absent 'model = "gpt-5.6"
')"
assert_eq "3: [tui] animations = false is added" "False" "$(tui_get "$CFG3" animations)"
assert_eq "3: the user's top-level key survives" "'gpt-5.6'" "$(toml_get "$CFG3" model)"

echo ""
echo "--- Group 4: repeated merges are idempotent ---"
merge_codex_settings "$SEED" "$CFG3" >/dev/null 2>&1
merge_codex_settings "$SEED" "$CFG3" >/dev/null 2>&1
assert_eq "4: still valid TOML with animations = false" "False" "$(tui_get "$CFG3" animations)"
assert_eq "4: exactly one [tui] table header" "1" "$(grep -c '^\[tui\]$' "$CFG3")"

echo ""
echo "========================================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
echo "========================================="
[[ "$FAIL" -eq 0 ]] || exit 1
echo "ALL TESTS PASSED"
