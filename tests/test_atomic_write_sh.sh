#!/usr/bin/env bash
# test_atomic_write_sh.sh - Contract tests for .aitask-scripts/lib/atomic_write.sh (t1379).
#
# The shell sibling of lib/atomic_write.py. Each test defends one property, and
# each has its own negative control (a mutation of the helper that must make
# exactly that test fail) — there is no single mutation that fails them all:
#
#   | test                              | mutation that must fail it              |
#   |-----------------------------------|-----------------------------------------|
#   | staged_beside_resolved_dest       | mktemp into "${TMPDIR:-/tmp}"           |
#   | existing_mode_preserved           | drop the chmod in ait_atomic_tmp        |
#   | new_file_mode_* (both umasks)     | hardcode 0644 instead of 0666 & ~umask  |
#   | symlink_followed_not_replaced     | drop ait_atomic_resolve                 |
#   | retarget_between_stage_and_commit | resolve inside tmp/commit (i.e. twice)  |
#   | directory_destination_rejected    | drop the [[ -d "$dest" ]] guards        |
#   | render_failure_*                  | drop the discard in ait_atomic_render   |
#   | commit_failure_no_residue         | drop the rm -f in ait_atomic_commit     |
#   | empty_output_rejected             | drop the [[ -s "$tmp" ]] check          |
#
# Two of these are worth spelling out, because a plausible-looking test would
# NOT discriminate them:
#
#   * The mode tests assert BOTH an existing file's mode and a missing file's
#     umask-derived default, the latter re-run under `umask 0077`. Under the
#     usual umask of 022, `0666 & ~umask` IS 0644 — so a hardcoded 0644 passes
#     the default-umask case and only the restrictive one catches it.
#   * There is deliberately NO "hardlink probe proves a same-filesystem rename"
#     test. A real cross-device mv also leaves the probe on the old bytes with
#     a new inode at the path; the property that actually rules a cross-device
#     rename out is staged_beside_resolved_dest.
#
# Run: bash tests/test_atomic_write_sh.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

# shellcheck source=../.aitask-scripts/lib/terminal_compat.sh
. "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"
# shellcheck source=../.aitask-scripts/lib/atomic_write.sh
. "$PROJECT_DIR/.aitask-scripts/lib/atomic_write.sh"

WORK="$(mktemp -d "${TMPDIR:-/tmp}/ait_atomic_sh_XXXXXX")"
WORK="$(cd "$WORK" && pwd -P)"
cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT

file_mode() { stat -c '%a' "$1" 2>/dev/null || stat -f '%Lp' "$1"; }

# Count dot-prefixed staging siblings of <name> left in <dir>.
residue_count() {
    local dir="$1" name="$2" n
    n=$(find "$dir" -maxdepth 1 -name ".${name}.*" 2>/dev/null | wc -l)
    printf '%s' "$n" | tr -d '[:space:]'
}

echo "=== lib/atomic_write.sh contract ==="

# --- staging location -------------------------------------------------------
echo "--- staged beside the resolved destination ---"
d="$WORK/stage"; mkdir -p "$d/real"
printf 'OLD\n' > "$d/real/backing.md"
ln -s real/backing.md "$d/link.md"

resolved="$(ait_atomic_resolve "$d/link.md")"
assert_eq "resolve follows the file symlink" "$d/real/backing.md" "$resolved"

tmp="$(ait_atomic_tmp "$resolved")"
assert_eq "temp is staged in the resolved destination's directory" \
    "$d/real" "$(dirname "$tmp")"
case "$(basename "$tmp")" in
    .backing.md.*) assert_eq "temp name is dot-prefixed" "yes" "yes" ;;
    *)             assert_eq "temp name is dot-prefixed" "yes" "no ($(basename "$tmp"))" ;;
esac
ait_atomic_discard "$tmp"

# --- mode -------------------------------------------------------------------
echo "--- mode ---"
printf 'x\n' > "$WORK/m640.md"; chmod 640 "$WORK/m640.md"
ait_atomic_write_text "$WORK/m640.md" "y"
assert_eq "an existing file's mode survives the rewrite" "640" "$(file_mode "$WORK/m640.md")"

# mktemp creates 0600; the redirection this helper replaces creates
# 0666 & ~umask. Without an explicit default a NEW task file would land 0600.
expected_default="$(printf '%o' $(( 0666 & ~0$(umask) )))"
ait_atomic_write_text "$WORK/fresh.md" "hi"
assert_eq "a new file gets 0666 & ~umask, not mktemp's 0600" \
    "$expected_default" "$(file_mode "$WORK/fresh.md")"

# Under the usual umask 022 the derived value IS 0644, so only a restrictive
# umask distinguishes "derived" from "hardcoded 0644".
( umask 0077; ait_atomic_write_text "$WORK/fresh_restrictive.md" "hi" )
assert_eq "the new-file default tracks a changed umask" \
    "600" "$(file_mode "$WORK/fresh_restrictive.md")"

ait_atomic_write_text "$WORK/deep/nested/new.md" "hi"
assert_eq "a missing parent directory is created" "hi" "$(cat "$WORK/deep/nested/new.md")"

# --- symlinks ---------------------------------------------------------------
echo "--- symlinks ---"
d="$WORK/sym"; mkdir -p "$d/real"
printf 'OLD\n' > "$d/real/backing.md"
ln -s real/backing.md "$d/link.md"
ait_atomic_write_text "$d/link.md" "NEW"
# `> "$link"` follows the symlink; a bare `mv` REPLACES it, orphaning the
# backing file while reads keep succeeding.
assert_eq "the symlink itself survives" "yes" "$([ -L "$d/link.md" ] && echo yes || echo no)"
assert_eq "the write reaches the backing file" "NEW" "$(cat "$d/real/backing.md")"

d="$WORK/cycle"; mkdir -p "$d"
ln -s b.md "$d/a.md"; ln -s a.md "$d/b.md"
rc=0; ait_atomic_resolve "$d/a.md" >/dev/null 2>&1 || rc=$?
assert_eq "a symlink cycle fails instead of looping" "1" "$rc"

# --- retarget race (resolve-once) -------------------------------------------
echo "--- retarget between stage and commit ---"
# Single resolution is guaranteed structurally: the entry points resolve, and
# ait_atomic_tmp / ait_atomic_commit do NOT. Assert that primitive property
# directly — a scenario test that hands both stages an already-resolved path
# passes under a resolve-twice implementation too, so it would prove nothing.
d="$WORK/race"; mkdir -p "$d/a" "$d/b"
printf 'A_OLD\n' > "$d/a/f.md"; printf 'B_OLD\n' > "$d/b/f.md"
ln -s a/f.md "$d/link.md"

# commit must replace exactly the path it is given. If it resolved, this would
# land on a/f.md and leave the symlink in place.
tmp="$(ait_atomic_tmp "$d/a/f.md")"
printf 'NEW\n' > "$tmp"
ait_atomic_commit "$tmp" "$d/link.md"
assert_eq "ait_atomic_commit does not resolve its destination" "no" \
    "$([ -L "$d/link.md" ] && echo yes || echo no)"
assert_eq "…so the backing file it pointed at is untouched" "A_OLD" "$(cat "$d/a/f.md")"

# ait_atomic_tmp must not resolve either: given a symlink it stages beside the
# LINK, not beside the backing file.
d="$WORK/race2"; mkdir -p "$d/real"
printf 'OLD\n' > "$d/real/backing.md"
ln -s real/backing.md "$d/link.md"
tmp="$(ait_atomic_tmp "$d/link.md")"
assert_eq "ait_atomic_tmp does not resolve its destination" "$d" "$(dirname "$tmp")"
ait_atomic_discard "$tmp"

# End to end through the entry point, which DOES resolve: a retarget after the
# call cannot affect where the bytes went.
ait_atomic_write_text "$d/link.md" "NEW"
ln -sfn ../elsewhere.md "$d/link.md"
assert_eq "the entry point's single resolution reached the backing file" \
    "NEW" "$(cat "$d/real/backing.md")"

# --- directory destination --------------------------------------------------
echo "--- directory destination ---"
d="$WORK/dirdest"; mkdir -p "$d/target"
_ok_body() { echo hi; }
rc=0; ait_atomic_render "$d/target" _ok_body >/dev/null 2>&1 || rc=$?
# `mv -f tmp somedir` SUCCEEDS by moving the temp INTO the directory, so without
# an explicit guard this reports success while writing nothing.
assert_eq "a directory destination is rejected" "1" "$rc"
assert_eq "nothing is left inside the directory" "0" \
    "$(find "$d/target" -mindepth 1 2>/dev/null | wc -l | tr -d '[:space:]')"

rc=0; ait_atomic_tmp "$d/target" >/dev/null 2>&1 || rc=$?
assert_eq "ait_atomic_tmp rejects a directory too" "1" "$rc"

# --- render failures --------------------------------------------------------
echo "--- render failures ---"
d="$WORK/render"; mkdir -p "$d"
printf 'ORIGINAL\n' > "$d/f.md"

# Failure-after-success: the shape a "renderer returns non-zero" test misses.
# ait_atomic_render's calling context disables errexit inside the renderer, so
# the guard has to be explicit — this is the contract every converted site owes.
_mid_fail_body() { echo line1; false || return 1; printf 'partial\n'; }
rc=0; ait_atomic_render "$d/f.md" _mid_fail_body >/dev/null 2>&1 || rc=$?
assert_eq "a mid-render failure is reported" "1" "$rc"
assert_eq "the original survives a mid-render failure" "ORIGINAL" "$(cat "$d/f.md")"
assert_eq "no residue after a mid-render failure" "0" "$(residue_count "$d" "f.md")"

_empty_body() { true; }
rc=0; ait_atomic_render "$d/f.md" _empty_body >/dev/null 2>&1 || rc=$?
assert_eq "an empty render result is rejected" "1" "$rc"
assert_eq "the original survives an empty render" "ORIGINAL" "$(cat "$d/f.md")"
assert_eq "no residue after an empty render" "0" "$(residue_count "$d" "f.md")"

AIT_ATOMIC_ALLOW_EMPTY=1 ait_atomic_render "$d/f.md" _empty_body
assert_eq "AIT_ATOMIC_ALLOW_EMPTY permits an empty result" "0" \
    "$(wc -c < "$d/f.md" | tr -d '[:space:]')"

# --- commit failure ---------------------------------------------------------
echo "--- commit failure ---"
d="$WORK/commit"; mkdir -p "$d"
printf 'ORIGINAL\n' > "$d/f.md"
tmp="$(ait_atomic_tmp "$d/f.md")"
printf 'NEW\n' > "$tmp"
# The rename itself has to fail, and it has to fail while the directory is
# still writable — otherwise the cleanup could not run either and the test
# would pass whether or not the cleanup exists. A function override is the one
# deterministic way to reach that branch (ait_atomic_commit calls `mv`
# unqualified). The directory-destination case is guarded BEFORE the rename, so
# it exercises a different discard.
mv() { return 1; }
rc=0; ait_atomic_commit "$tmp" "$d/f.md" >/dev/null 2>&1 || rc=$?
unset -f mv
assert_eq "a failing rename reports failure" "1" "$rc"
assert_eq "a failing rename removes its temp" "0" "$(residue_count "$d" "f.md")"
assert_eq "the original is untouched by a failing rename" "ORIGINAL" "$(cat "$d/f.md")"

# --- round trip -------------------------------------------------------------
echo "--- ait_atomic_write_text round trip ---"
d="$WORK/roundtrip"; mkdir -p "$d"
ait_atomic_write_text "$d/f.md" "$(printf 'one\ntwo')"
assert_eq "content round-trips" "$(printf 'one\ntwo')" "$(cat "$d/f.md")"
# "one\ntwo" is 7 bytes; exactly one trailing newline makes the file 8. Two
# would make it 9, so this discriminates the "force exactly one" behaviour.
assert_eq "exactly one trailing newline" "8" \
    "$(wc -c < "$d/f.md" | tr -d '[:space:]')"
assert_eq "no residue after a successful write" "0" "$(residue_count "$d" "f.md")"

echo
echo "=== Results ==="
echo "Total:  $TOTAL"
echo "Pass:   $PASS"
echo "Fail:   $FAIL"
if [[ $FAIL -eq 0 ]]; then
    echo "PASS"
    exit 0
fi
echo "FAIL"
exit 1
