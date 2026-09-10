#!/usr/bin/env bash
# test_install_changelog_preservation.sh - install.sh must not destroy a
# project's own root CHANGELOG.md or VERSION (t1772).
#
# The bug: main() extracted the release tarball straight into the project root
# — the tarball carries the FRAMEWORK's CHANGELOG.md at its root, so extraction
# overwrote the project's own — and then ran `rm -f "$INSTALL_DIR/CHANGELOG.md"`,
# deleting the result. Every install and every `ait upgrade` destroyed a file
# the framework's own `ait changelog` tooling maintains. An unconditional
# `rm -f "$INSTALL_DIR/VERSION"` did the same to a project's root VERSION.
#
# The fix stashes both files before extraction and restores them afterwards,
# removing a root VERSION only when it is provably the pre-v0.3.0 framework
# artefact. Because a preserved project VERSION would then be misread forever
# as the framework version, show_upgrade_changelog now prefers
# .aitask-scripts/VERSION over the root file.
#
#   Tests 1-5 — hermetic full `bash install.sh --force` runs (e2e).
#   Tests 6-7 — show_upgrade_changelog under live errexit (helper-level).
#
# Tests 1, 2, 4, 6 and 7 discriminate (they fail against the unfixed
# install.sh); 3 and 5 are pins that pass either way — they protect the two
# removals the fix deliberately keeps.
#
# Every e2e case first asserts the installer exited 0 AND that extraction
# reached the target. Without that, a silent installer abort (the t1414 failure
# mode, in the same function this fix edits) would leave the project's files
# untouched and make the preservation cases pass for the wrong reason.
#
# Zero network (--local-tarball); HOME and SHIM_DIR are redirected into the
# scratch dir so nothing touches the developer's ~/.local/bin or shell rc files.
#
# Run: bash tests/test_install_changelog_preservation.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# Shared assertion helpers (see tests/lib/asserts.sh)
. "$PROJECT_DIR/tests/lib/asserts.sh"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "=== install.sh project-file preservation Tests (t1772) ==="
echo ""

# ---------------------------------------------------------------------------
# Fixture: a release-layout tarball (cf. .github/workflows/release.yml) whose
# root CHANGELOG.md is deliberately DIFFERENT from any project changelog below,
# so a replacement fails the byte comparison exactly as a deletion does.
# ---------------------------------------------------------------------------
STAGE="$WORK/stage"
mkdir -p "$STAGE" "$WORK/home" "$WORK/bin"
printf '# Changelog\n\n## v99.0.0\n- FRAMEWORK changelog, not the project one\n' \
    > "$STAGE/CHANGELOG.md"

TARBALL="$WORK/release.tar.gz"
# Two -C switches keep every member name flat (no ./ prefix), matching the
# release layout; both GNU tar and bsdtar honour a -C between member lists.
tar -czf "$TARBALL" \
    -C "$PROJECT_DIR" .aitask-scripts ait packaging seed \
    -C "$STAGE" CHANGELOG.md 2>/dev/null
tar_rc=$?

if [[ $tar_rc -ne 0 || ! -s "$TARBALL" ]]; then
    # Fail loudly rather than skipping — an unbuildable fixture must not read
    # as success.
    TOTAL=$((TOTAL + 1)); FAIL=$((FAIL + 1))
    echo "FAIL: could not build the release-layout fixture tarball (tar rc=$tar_rc)"
    echo ""
    echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
    exit 1
fi

PROJECT_CHANGELOG=$'# Project Changelog\n\n## v1.2.3\n- a project-owned entry\n- trailing line with no newline'
PROJECT_VERSION=$'7.7.7-project\n'

# Runs the real installer against $1. Sets `rc` and `log`. The subshell only
# isolates the installer's cwd — every assertion stays at top level.
run_install() {
    local target="$1"
    log="$target.install.log"
    (
        cd "$PROJECT_DIR" || exit 1
        HOME="$WORK/home" SHIM_DIR="$WORK/bin" \
            bash "$PROJECT_DIR/install.sh" --force \
                 --dir "$target" \
                 --local-tarball "$TARBALL"
    ) </dev/null >"$log" 2>&1
    rc=$?
}

# Vacuity guard: the installer must have run to completion AND reached
# extraction before any preservation claim means anything.
assert_install_ran() {
    local label="$1" target="$2"
    assert_exit_zero_rc "$label: installer exits 0" "$rc"
    assert_file_exists "$label: extraction reached the target" \
        "$target/.aitask-scripts/VERSION"
    if [[ $rc -ne 0 ]]; then
        echo "  --- install.sh output (last 20 lines) ---"
        tail -n 20 "$log" | sed 's/^/  /'
    fi
}

# Byte-identity check against a pre-run copy. Reports WHICH failure it was:
# `missing` is the old rm -f, `differs` is the extraction clobbering the file.
assert_same_bytes() {
    local label="$1" expected="$2" actual="$3" verdict
    if [[ ! -f "$actual" ]]; then
        verdict="missing"
    elif cmp -s "$expected" "$actual"; then
        verdict="identical"
    else
        verdict="differs"
    fi
    assert_eq "$label" "identical" "$verdict"
}

# --- Test 1: upgrade over an install that owns a root CHANGELOG.md ---------
echo "--- Test 1: upgrade preserves the project's CHANGELOG.md ---"
T1="$WORK/t1"
mkdir -p "$T1/.aitask-scripts"
echo "0.0.1" > "$T1/.aitask-scripts/VERSION"   # existing install => upgrade path
printf '%s' "$PROJECT_CHANGELOG" > "$T1/CHANGELOG.md"
cp -p "$T1/CHANGELOG.md" "$WORK/t1.expected"
run_install "$T1"
assert_install_ran "upgrade" "$T1"
assert_same_bytes "upgrade: project CHANGELOG.md is byte-identical afterwards" \
    "$WORK/t1.expected" "$T1/CHANGELOG.md"

# --- Test 2: first-time forced install into a project with a changelog -----
# No .aitask-scripts/ at all: a different check_existing_install branch and a
# different show_upgrade_changelog exit than Test 1, so neither covers the other.
echo "--- Test 2: first-time install preserves the project's CHANGELOG.md ---"
T2="$WORK/t2"
mkdir -p "$T2"
printf '%s' "$PROJECT_CHANGELOG" > "$T2/CHANGELOG.md"
cp -p "$T2/CHANGELOG.md" "$WORK/t2.expected"
run_install "$T2"
assert_install_ran "first install" "$T2"
assert_same_bytes "first install: project CHANGELOG.md is byte-identical afterwards" \
    "$WORK/t2.expected" "$T2/CHANGELOG.md"

# --- Test 3 (pin): no project changelog => the framework's is not left behind
echo "--- Test 3: no project CHANGELOG.md => none left behind ---"
T3="$WORK/t3"
mkdir -p "$T3"
run_install "$T3"
assert_install_ran "no changelog" "$T3"
assert_file_not_exists "no changelog: the framework's CHANGELOG.md is not left in the project" \
    "$T3/CHANGELOG.md"

# --- Test 4: a project root VERSION survives an upgrade ---------------------
echo "--- Test 4: upgrade preserves a project-owned root VERSION ---"
T4="$WORK/t4"
mkdir -p "$T4/.aitask-scripts"
echo "0.0.1" > "$T4/.aitask-scripts/VERSION"   # already migrated => not legacy
printf '%s' "$PROJECT_VERSION" > "$T4/VERSION"
cp -p "$T4/VERSION" "$WORK/t4.expected"
run_install "$T4"
assert_install_ran "project VERSION" "$T4"
assert_same_bytes "project VERSION: root VERSION is byte-identical afterwards" \
    "$WORK/t4.expected" "$T4/VERSION"

# --- Test 5 (pin): the genuine pre-v0.3.0 artefact is still removed ---------
# An existing install (.aitask-scripts/ present) whose version never migrated
# to .aitask-scripts/VERSION: the root VERSION is the framework's own.
echo "--- Test 5: legacy pre-v0.3.0 root VERSION is still removed ---"
T5="$WORK/t5"
mkdir -p "$T5/.aitask-scripts"
echo "legacy" > "$T5/.aitask-scripts/legacy_marker"
echo "0.2.9" > "$T5/VERSION"
run_install "$T5"
assert_install_ran "legacy VERSION" "$T5"
assert_file_not_exists "legacy VERSION: the migrated root VERSION is removed" \
    "$T5/VERSION"

# ---------------------------------------------------------------------------
# Helper-level cases. Sourced AFTER the e2e runs: the --source-only guard
# returns before main() runs and must be the FIRST argument. Same pattern as
# tests/test_install_upgrade_changelog.sh.
# ---------------------------------------------------------------------------
# shellcheck source=../install.sh
source "$PROJECT_DIR/install.sh" --source-only
set +euo pipefail

# Runs show_upgrade_changelog under LIVE errexit, exactly as main() calls it.
# `</dev/null` keeps the [[ -t 0 ]]-guarded "Proceed with upgrade?" read from
# hanging an interactive run.
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

# --- Test 6: a conflicting project root VERSION, real version transition ----
# The primary discriminator for the precedence flip. Pre-fix the helper reads
# the project's 7.7.7 as the framework version, announces v7.7.7 -> v2.0.0,
# and — never meeting a `## v7.7.7` heading — dumps every section, including
# the installed version's.
echo "--- Test 6: helper, project root VERSION does not hijack the transition ---"
mkdir -p "$WORK/h6/.aitask-scripts" "$WORK/tb6/.aitask-scripts"
echo "7.7.7" > "$WORK/h6/VERSION"
echo "1.0.0" > "$WORK/h6/.aitask-scripts/VERSION"
echo "2.0.0" > "$WORK/tb6/.aitask-scripts/VERSION"
printf '## v2.0.0\n- new thing\n\n## v1.0.0\n- old thing\n' > "$WORK/tb6/CHANGELOG.md"
tar -czf "$WORK/h6.tar.gz" -C "$WORK/tb6" .aitask-scripts/VERSION CHANGELOG.md
run_case true "$WORK/h6.tar.gz" "$WORK/h6"
assert_exit_zero_rc "helper returns 0 with a conflicting project VERSION" "$rc"
assert_contains "caller continues past the helper" "MARKER" "$out"
assert_contains "announces the FRAMEWORK transition" "Upgrading: v1.0.0 → v2.0.0" "$out"
assert_not_contains "never reads the project's own VERSION as the framework's" \
    "7.7.7" "$out"
assert_contains "still prints the newer release's changelog section" \
    "- new thing" "$out"
assert_not_contains "still stops before the installed version's section" \
    "- old thing" "$out"

# --- Test 7: authoritative version equals the tarball => early return -------
# Pre-fix the root 1.0.0 is read instead, so a no-op upgrade is announced.
echo "--- Test 7: helper, no transition when .aitask-scripts/VERSION matches ---"
mkdir -p "$WORK/h7/.aitask-scripts" "$WORK/tb7/.aitask-scripts"
echo "1.0.0" > "$WORK/h7/VERSION"
echo "9.9.9" > "$WORK/h7/.aitask-scripts/VERSION"
echo "9.9.9" > "$WORK/tb7/.aitask-scripts/VERSION"
printf '## v9.9.9\n- current thing\n' > "$WORK/tb7/CHANGELOG.md"
tar -czf "$WORK/h7.tar.gz" -C "$WORK/tb7" .aitask-scripts/VERSION CHANGELOG.md
run_case true "$WORK/h7.tar.gz" "$WORK/h7"
assert_exit_zero_rc "helper returns 0 on the same-version early return" "$rc"
assert_contains "caller continues past the early return" "MARKER" "$out"
assert_not_contains "announces no upgrade when the framework version is unchanged" \
    "Upgrading:" "$out"

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
