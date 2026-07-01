#!/usr/bin/env bash
# test_stats_tui_dispatch.sh — Verify the `ait` dispatcher routes `stats tui`
# (space form) to the TUI launcher, while preserving the text CLI and the
# canonical hyphenated `stats-tui` route.
#
# Regression for t1083: `./ait stats tui` used to reach `aitask_stats.sh` and
# fail with argparse `unrecognized arguments: tui`. The dispatcher now forwards
# a leading `tui` arg to `aitask_stats_tui.sh`.
#
# Behavioral test of the REAL dispatcher: it copies `ait` into a temp tree with
# STUB stats scripts, so routing is exercised end-to-end without launching
# Textual. Pattern mirrors tests/test_migrate_archives.sh setup.
#
# Run: bash tests/test_stats_tui_dispatch.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

# --- Build a minimal stub tree around the real `ait` dispatcher -------------
TMPDIR_ROOT="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_ROOT"' EXIT

mkdir -p "$TMPDIR_ROOT/.aitask-scripts/lib"
cp "$PROJECT_DIR/ait" "$TMPDIR_ROOT/ait"
cp "$PROJECT_DIR/.aitask-scripts/lib/aitask_path.sh" "$TMPDIR_ROOT/.aitask-scripts/lib/"

# Stub targets: echo a distinct marker + forwarded args instead of running the
# real CLI / launching the TUI. No VERSION file is copied, so the dispatcher's
# daily update check bails immediately (no background curl) — deterministic.
cat > "$TMPDIR_ROOT/.aitask-scripts/aitask_stats.sh" <<'EOF'
#!/usr/bin/env bash
echo "STATS_CLI $*"
EOF
cat > "$TMPDIR_ROOT/.aitask-scripts/aitask_stats_tui.sh" <<'EOF'
#!/usr/bin/env bash
echo "STATS_TUI $*"
EOF
chmod +x "$TMPDIR_ROOT/ait" \
         "$TMPDIR_ROOT/.aitask-scripts/aitask_stats.sh" \
         "$TMPDIR_ROOT/.aitask-scripts/aitask_stats_tui.sh"

# Isolate HOME so the update-check cache never touches the real one.
run_ait() {
    ( cd "$TMPDIR_ROOT" && HOME="$TMPDIR_ROOT/home" bash ./ait "$@" 2>&1 )
}

# --- 1: `stats tui` routes to the TUI launcher ------------------------------
out="$(run_ait stats tui)"
assert_contains "'stats tui' routes to the TUI launcher" "STATS_TUI" "$out"
assert_not_contains "'stats tui' does NOT reach the text CLI" "STATS_CLI" "$out"

# --- 2: extra args are forwarded to the TUI; `tui` is consumed --------------
out="$(run_ait stats tui --foo bar)"
assert_contains "'stats tui --foo bar' forwards trailing args" "STATS_TUI --foo bar" "$out"

# --- 3: plain `stats` still reaches the text CLI (negative control) ---------
# A greedy/incorrect match would misroute normal stats invocations to the TUI.
out="$(run_ait stats -d 7)"
assert_contains "'stats -d 7' reaches the text CLI" "STATS_CLI -d 7" "$out"
assert_not_contains "'stats -d 7' does NOT reach the TUI" "STATS_TUI" "$out"

# --- 4: canonical hyphenated `stats-tui` route intact -----------------------
out="$(run_ait stats-tui)"
assert_contains "'stats-tui' still routes to the TUI launcher" "STATS_TUI" "$out"

# --- Summary ---------------------------------------------------------------
echo ""
echo "Passed: $PASS / $TOTAL"
if [[ "$FAIL" -gt 0 ]]; then
    echo "FAILED: $FAIL"
    exit 1
fi
echo "All tests passed."
