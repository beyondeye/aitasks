#!/usr/bin/env bash
# test_install_upgrade_changelog.sh - Tests for install.sh show_upgrade_changelog()
# (t1414).
#
# The bug: the `else` branch of the version lookup used a bare `return`, which
# inherits the status of the immediately preceding failed `[[ -f ... ]]` test —
# i.e. 1. install.sh runs under `set -euo pipefail` and main() calls the helper
# unguarded right after the download and BEFORE `tar -xzf`, so a `--force`
# install into a directory with no VERSION aborted the installer silently,
# leaving the target directory completely empty.
#
# Two surfaces (the split tests/test_install_create_data_dirs.sh also uses):
#   Test 1     — hermetic full `bash install.sh --force --dir <fresh>` run,
#                asserting the target actually gets populated. This is the
#                regression test for the observable failure.
#   Tests 2-5  — helper-level cases run under live errexit, covering the three
#                `return` sites and the changelog display individually.
#
# Tests 1 and 2 discriminate (they fail against the unfixed install.sh);
# 3-5 are pins that pass either way and protect the sibling `return 0`
# hardening and the display path.
#
# Zero network: the full run uses --local-tarball, so install.sh never needs
# curl/wget. Fully hermetic: HOME and SHIM_DIR are redirected into the scratch
# dir so the global shim and the PATH line never touch the developer's
# ~/.local/bin or shell rc files.
#
# Run: bash tests/test_install_upgrade_changelog.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# Shared assertion helpers (see tests/lib/asserts.sh)
. "$PROJECT_DIR/tests/lib/asserts.sh"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "=== install.sh show_upgrade_changelog() Tests ==="
echo ""

# ---------------------------------------------------------------------------
# Test 1: hermetic full-installer run into a fresh directory (t1414 regression)
# ---------------------------------------------------------------------------
# Drives the real main(), so it proves the helper no longer aborts the caller
# AND that extraction is reached. Runs unconditionally — there is deliberately
# no skip path: a skipped case here would let the suite report green without
# ever checking the task's observable outcome.
echo "--- Test 1: full install.sh --force into an empty directory ---"

E2E_ROOT="$WORK/e2e"
mkdir -p "$E2E_ROOT/home" "$E2E_ROOT/bin" "$E2E_ROOT/target"
E2E_TARBALL="$E2E_ROOT/release.tar.gz"

# Release-layout tarball (cf. .github/workflows/release.yml). `ait` and
# .aitask-scripts/*.sh are mandatory (set_permissions chmods both); packaging/
# carries the shim source install_global_shim needs; seed/ makes the run match
# a real release.
(cd "$PROJECT_DIR" && tar czf "$E2E_TARBALL" .aitask-scripts/ ait packaging/ seed/) 2>/dev/null
tar_rc=$?

if [[ $tar_rc -ne 0 || ! -s "$E2E_TARBALL" ]]; then
    # Fail loudly rather than skipping — an unbuildable fixture must not read
    # as success.
    TOTAL=$((TOTAL + 1)); FAIL=$((FAIL + 1))
    echo "FAIL: could not build the release-layout fixture tarball (tar rc=$tar_rc)"
else
    E2E_LOG="$E2E_ROOT/install.log"
    (
        cd "$PROJECT_DIR" || exit 1
        HOME="$E2E_ROOT/home" SHIM_DIR="$E2E_ROOT/bin" \
            bash "$PROJECT_DIR/install.sh" --force \
                 --dir "$E2E_ROOT/target" \
                 --local-tarball "$E2E_TARBALL"
    ) </dev/null >"$E2E_LOG" 2>&1
    e2e_rc=$?

    assert_exit_zero_rc "--force into an empty dir exits 0 (not a silent abort)" "$e2e_rc"
    assert_file_exists "installer populated the target: ait" \
        "$E2E_ROOT/target/ait"
    assert_file_exists "installer populated the target: .aitask-scripts/VERSION" \
        "$E2E_ROOT/target/.aitask-scripts/VERSION"

    if [[ $e2e_rc -ne 0 ]]; then
        echo "  --- install.sh output (last 20 lines) ---"
        tail -n 20 "$E2E_LOG" | sed 's/^/  /'
    fi

    # Hermeticity self-check: nothing escaped into the redirected HOME/SHIM_DIR
    # substitutes for the developer's real ones.
    assert_file_exists "global shim landed in the redirected SHIM_DIR" \
        "$E2E_ROOT/bin/ait"
fi

# ---------------------------------------------------------------------------
# Helper-level cases: load install.sh's functions only. The --source-only guard
# returns before main() runs, and must be the FIRST argument (the parser breaks
# on it). See tests/test_install_tarball_download.sh for the same pattern.
# ---------------------------------------------------------------------------
# shellcheck source=../install.sh
source "$PROJECT_DIR/install.sh" --source-only
set +euo pipefail

# Runs show_upgrade_changelog under LIVE errexit in a subshell, exactly as
# main() calls it: a nonzero return kills the subshell, so `rc` is nonzero and
# the trailing MARKER never appears.
#
# `</dev/null` is load-bearing, not decoration: command substitution redirects
# stdout only, so stdin would stay the caller's terminal and the `[[ -t 0 ]]`
# guarded "Proceed with upgrade? [Y/n]" read at the end of the function would
# HANG test 5 for anyone running this suite interactively.
run_case() {
    local force="$1" tarball="$2" dir="$3"
    # FORCE is read by the sourced show_upgrade_changelog, which shellcheck
    # cannot see across the file boundary.
    # shellcheck disable=SC2034
    out="$( set -euo pipefail
            FORCE="$force"
            show_upgrade_changelog "$tarball" "$dir" </dev/null 2>&1
            echo MARKER )"
    rc=$?
}

# --- Test 2: no VERSION anywhere + --force (the defective `else`) -----------
echo "--- Test 2: helper, empty dir with no VERSION (FORCE=true) ---"
mkdir -p "$WORK/empty"
run_case true "$WORK/nonexistent.tar.gz" "$WORK/empty"
assert_exit_zero_rc "helper returns 0 when the current version is undeterminable" "$rc"
assert_contains "caller continues past the helper (not a silent abort)" "MARKER" "$out"

# --- Test 3: FORCE != true (sibling early return) ---------------------------
echo "--- Test 3: helper, FORCE=false early return ---"
run_case false "$WORK/nonexistent.tar.gz" "$WORK/empty"
assert_exit_zero_rc "helper returns 0 on the non-force early return" "$rc"
assert_contains "caller continues past the non-force early return" "MARKER" "$out"

# --- Test 4: installed version == tarball version (sibling early return) ----
echo "--- Test 4: helper, current version equals tarball version ---"
mkdir -p "$WORK/same/.aitask-scripts" "$WORK/tb_same/.aitask-scripts"
echo "9.9.9" > "$WORK/same/.aitask-scripts/VERSION"
echo "9.9.9" > "$WORK/tb_same/.aitask-scripts/VERSION"
# Flat member names (no ./ prefix), matching the release layout and the
# selective `tar -xzf ... .aitask-scripts/VERSION` extraction in the helper.
tar -czf "$WORK/same.tar.gz" -C "$WORK/tb_same" .aitask-scripts/VERSION
run_case true "$WORK/same.tar.gz" "$WORK/same"
assert_exit_zero_rc "helper returns 0 when there is no version change" "$rc"
assert_contains "caller continues past the same-version early return" "MARKER" "$out"

# --- Test 5: happy path — changelog display and version-range slicing -------
echo "--- Test 5: helper, upgrade display 1.0.0 -> 2.0.0 ---"
mkdir -p "$WORK/old/.aitask-scripts" "$WORK/tb_new/.aitask-scripts"
echo "1.0.0" > "$WORK/old/.aitask-scripts/VERSION"
echo "2.0.0" > "$WORK/tb_new/.aitask-scripts/VERSION"
printf '## v2.0.0\n- new thing\n\n## v1.0.0\n- old thing\n' > "$WORK/tb_new/CHANGELOG.md"
tar -czf "$WORK/new.tar.gz" -C "$WORK/tb_new" .aitask-scripts/VERSION CHANGELOG.md
run_case true "$WORK/new.tar.gz" "$WORK/old"
assert_exit_zero_rc "helper returns 0 on the upgrade display path" "$rc"
assert_contains "announces the version transition" "Upgrading: v1.0.0 → v2.0.0" "$out"
assert_contains "prints the newer release's changelog section" "- new thing" "$out"
assert_not_contains "stops before the currently-installed version's section" \
    "- old thing" "$out"

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
