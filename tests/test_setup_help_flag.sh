#!/usr/bin/env bash
# test_setup_help_flag.sh - `ait setup --help` prints usage and runs NO setup step.
# Run: bash tests/test_setup_help_flag.sh
#
# Covers both in-project entry paths (t1435):
#   1. the script directly:   .aitask-scripts/aitask_setup.sh --help
#   2. the public interface:  ./ait setup --help
#
# Everything runs against an ISOLATED framework copy with a temp $HOME. Before
# the fix, --help fell through main()'s `*)` catch-all and ran the full guided
# install (package installs, git init, venv creation, framework commits) — so a
# regression here must not be able to reach the real repo or the real $HOME.

THIS_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$THIS_SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

. "$PROJECT_DIR/tests/lib/test_scaffold.sh"
. "$PROJECT_DIR/tests/lib/asserts.sh"

# main()'s first line of body — printed only once a setup step has begun.
SETUP_BANNER="aitask framework setup"

# --- Bounded run -----------------------------------------------------------
# run_bounded <secs> <outfile> <cmd...>  → command's status, or 124 on timeout.
#
# `timeout` is GNU coreutils; macOS ships it only as `gtimeout` via Homebrew
# coreutils, so a bare `timeout` here would fail the test on macOS before it
# exercised either help path. Same guard the framework uses at
# aitask_sync.sh:97 and aitask_remote_drift_check.sh:152.
run_bounded() {
    local secs="$1" out="$2"; shift 2
    local runner=""
    command -v timeout >/dev/null 2>&1 && runner=timeout
    [ -z "$runner" ] && command -v gtimeout >/dev/null 2>&1 && runner=gtimeout
    if [ -n "$runner" ]; then
        "$runner" "$secs" "$@" >"$out" 2>&1 </dev/null
        return $?
    fi
    # macOS fallback. `set -m` puts the child in its own process group so the
    # watchdog can kill the whole tree — a regression here spawns pip/git
    # children that a bare `kill $pid` would orphan.
    set -m
    "$@" >"$out" 2>&1 </dev/null &
    local pid=$!
    set +m
    local i=0
    while kill -0 "$pid" 2>/dev/null && [ "$i" -lt "$secs" ]; do
        sleep 1
        i=$((i + 1))
    done
    if kill -0 "$pid" 2>/dev/null; then
        kill -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
        return 124
    fi
    wait "$pid"
    return $?
}

# --- Isolated framework fixture --------------------------------------------
# ensure_git_repo() and friends resolve the project root as $SCRIPT_DIR/.. , so
# the copied script sees $FIXTURE as its project — never the real repo.
FIXTURE="$(mktemp -d)"
FIXTURE_HOME="$FIXTURE/home"
mkdir -p "$FIXTURE_HOME"
setup_fake_aitask_repo "$FIXTURE"
cp "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh"      "$FIXTURE/.aitask-scripts/"
# github_release.sh + python_resolve.sh (scaffolded) are the two libs
# aitask_setup.sh sources at startup.
cp "$PROJECT_DIR/.aitask-scripts/lib/github_release.sh" "$FIXTURE/.aitask-scripts/lib/"
cp "$PROJECT_DIR/ait"                                   "$FIXTURE/"
chmod +x "$FIXTURE/.aitask-scripts/aitask_setup.sh" "$FIXTURE/ait"

SETUP_SH="$FIXTURE/.aitask-scripts/aitask_setup.sh"
OUT="$FIXTURE/out.txt"

echo "=== ait setup --help Tests ==="
echo ""

# --- Test 1: --help prints usage, exits 0, runs nothing --------------------
echo "--- Test 1: --help prints usage and runs no setup step ---"

HOME="$FIXTURE_HOME" run_bounded 30 "$OUT" bash "$SETUP_SH" --help
rc=$?
help_output="$(cat "$OUT")"

assert_eq "--help exits 0" "0" "$rc"
assert_contains "Prints the usage banner" "Usage: ait setup" "$help_output"
assert_contains "Documents -h, --help" "-h, --help" "$help_output"
assert_not_contains "No setup step ran" "$SETUP_BANNER" "$help_output"
assert_dir_not_exists "No \$HOME/.aitask side effects" "$FIXTURE_HOME/.aitask"

# --- Test 2: -h is equivalent ----------------------------------------------
echo "--- Test 2: -h behaves like --help ---"

HOME="$FIXTURE_HOME" run_bounded 30 "$OUT" bash "$SETUP_SH" -h
rc=$?
short_output="$(cat "$OUT")"

assert_eq "-h exits 0" "0" "$rc"
assert_contains "-h prints the usage banner" "Usage: ait setup" "$short_output"
assert_not_contains "-h runs no setup step" "$SETUP_BANNER" "$short_output"
assert_dir_not_exists "-h leaves \$HOME/.aitask absent" "$FIXTURE_HOME/.aitask"

# --- Test 3: --help wins mid-loop, after another flag ----------------------
echo "--- Test 3: --with-dev --help still prints help ---"

HOME="$FIXTURE_HOME" run_bounded 30 "$OUT" bash "$SETUP_SH" --with-dev --help
rc=$?
mixed_output="$(cat "$OUT")"

assert_eq "--with-dev --help exits 0" "0" "$rc"
assert_contains "Prints usage after another flag" "Usage: ait setup" "$mixed_output"
assert_not_contains "Runs no setup step" "$SETUP_BANNER" "$mixed_output"

# --- Test 4: the public interface, ./ait setup --help ----------------------
# What users actually type. `setup` is in the dispatcher's check_for_updates
# skip list, so this touches no network.
echo "--- Test 4: ./ait setup --help (dispatcher path) ---"

for flag in --help -h; do
    ( cd "$FIXTURE" && HOME="$FIXTURE_HOME" run_bounded 30 "$OUT" ./ait setup "$flag" )
    rc=$?
    disp_output="$(cat "$OUT")"

    assert_eq "ait setup $flag exits 0" "0" "$rc"
    assert_contains "ait setup $flag prints usage" "Usage: ait setup" "$disp_output"
    assert_not_contains "ait setup $flag runs no setup step" "$SETUP_BANNER" "$disp_output"
done
assert_dir_not_exists "Dispatcher path leaves \$HOME/.aitask absent" "$FIXTURE_HOME/.aitask"

# --- Test 5: usage() documents every opt-in tier flag (drift guard) ---------
# Derive the tier flags from main()'s case loop instead of hardcoding them, so
# a future tier added to the loop but not to usage() fails here.
# POSIX class, not \s: \s is a GNU grep extension that silently fails to match
# on BSD/macOS grep (aidocs/framework/sed_macos_issues.md), which would make
# the loop below vacuous instead of failing loudly.
echo "--- Test 5: usage() documents every --with-* tier flag ---"

# `tr -d '[:space:])'` would eat the newlines too and fuse every match into one
# token — strip per line with sed instead.
tier_flags=$(grep -oE '^[[:space:]]+--with-[a-z]+\)' \
                  "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" \
             | sed 's/^[[:space:]]*//; s/)$//')
# shellcheck disable=SC2086  # deliberate word-splitting: one flag per line
tier_count=$(printf '%s\n' $tier_flags | grep -c . || true)
assert_eq_trim "Tier-flag extractor found all 3 arms" "3" "$tier_count"
# Match the flag as an entry of the Options block (`  --with-x  <text>`), not
# as a bare substring: every tier flag also appears in the Examples block, so a
# plain containment check still passes when an Options line is dropped — the
# guard would not discriminate on the thing it exists to protect.
# shellcheck disable=SC2086
for f in $tier_flags; do
    assert_contains_re "usage() lists $f under Options" \
        "^  ${f}[[:space:]]+[A-Za-z]" "$help_output"
done

rm -rf "$FIXTURE"

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
