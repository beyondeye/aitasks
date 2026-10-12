#!/usr/bin/env bash
# test_gitignore_data_symlinks.sh - the data names stay ignored as SYMLINKS (t1711).
# Run: bash tests/test_gitignore_data_symlinks.sh
#
# In a linked task worktree, .aitask-data, aitasks and aiplans are symlinks
# (ait_link_worktree_data). A trailing-slash .gitignore pattern matches
# directories only, so `.aitask-data/` left every worktree reporting
# `?? .aitask-data`; `git worktree remove` then refused and the task could not
# archive. The primary checkout never shows it, because there .aitask-data is a
# real directory.
#
# So this asks GIT, never a hand-rolled matcher: directory-only matching is the
# exact semantic a re-implementation gets wrong. Each check builds a throwaway
# repo, creates a real symlink per data name, and asserts git does not report
# it — plus a control symlink no pattern matches, which MUST be reported, so a
# harness that stopped observing fails instead of passing vacuously.
#
# Inputs read at runtime (declare them to any test-selection tooling, or an
# edit to them will not re-run this test):
#   .gitignore                              (Case A — the repo's own file)
#   .aitask-scripts/lib/data_symlinks.sh    (the names under test)
#   .aitask-scripts/aitask_setup.sh         (the rewriter, Cases C-E)
#   .aitask-scripts/lib/atomic_write.sh     (the rewriter's file replacement)
#
# The .gitignore setup writes for NEW installs is covered in
# tests/test_data_branch_setup.sh, which owns the setup_data_branch fixture.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

# The rewriter lives in aitask_setup.sh; sourcing it also pulls in
# data_symlinks.sh (the names) and sets -euo pipefail, which a test must undo.
# shellcheck source=../.aitask-scripts/aitask_setup.sh
source "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" --source-only
set +euo pipefail

NAMES=("$AIT_DATA_DIR_NAME" "${AIT_DATA_LINKS[@]}")
CONTROL="ait_t1711_control"

WORK="$(mktemp -d "${TMPDIR:-/tmp}/t1711test.XXXXXX")"
cleanup() {
    [[ -n "${WORK:-}" && -d "$WORK" ]] || return 0
    chmod -R u+w "$WORK" 2>/dev/null
    rm -rf "$WORK"
}
trap cleanup EXIT

# The names must be derived, not empty: an empty list would make every
# "not reported" assertion below pass without checking anything. No fixed count
# and no literals: the gate follows data_symlinks.sh, so a new data link is
# covered (and must be ignored) without editing this file.
TOTAL=$((TOTAL + 1))
if [[ ${#NAMES[@]} -ge 2 && -n "$AIT_DATA_DIR_NAME" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: data_symlinks.sh yields the data dir plus at least one link (got: ${NAMES[*]})"
fi
for name in "${NAMES[@]}"; do
    assert_not_contains "derived name '$name' is a bare name" "/" "$name"
done

# porcelain_for <gitignore-file> -> `git status --porcelain` of a fresh repo
# holding that .gitignore, one real symlink per data name, and the control.
# Called inside $( ), so a fresh dir per call comes from mktemp, not a counter.
porcelain_for() {
    local src="$1" repo name
    repo="$(mktemp -d "$WORK/repo.XXXXXX")" || return 1
    git -C "$repo" init -q
    cp -- "$src" "$repo/.gitignore"
    for name in "${NAMES[@]}" "$CONTROL"; do
        ln -s target "$repo/$name"
    done
    git -C "$repo" status --porcelain --untracked-files=all
}

# check_gitignore <label> <gitignore-file>: every data name ignored as a symlink.
check_gitignore() {
    local label="$1" src="$2" out name
    out="$(porcelain_for "$src")"
    # Positive control first: the harness still sees untracked symlinks.
    assert_contains "$label: control symlink IS reported" "?? $CONTROL" "$out"
    for name in "${NAMES[@]}"; do
        assert_not_contains "$label: symlink '$name' not reported" "?? $name" "$out"
    done
}

# --- Case A: this repo's tracked .gitignore -----------------------------------
# Catches the slash coming back, the line being deleted, and a later `!`
# negation re-including the name — any of them shows up as `?? <name>`.
echo "--- Case A: repo .gitignore ignores the data names as symlinks ---"
check_gitignore "A" "$PROJECT_DIR/.gitignore"

# --- Negative control: the pre-fix block really leaves the symlink exposed ----
# Proves the check above can fail: the exact block setup used to write.
echo "--- Negative control: pre-fix .gitignore exposes .aitask-data ---"
printf '.aitask-data/\naitasks\naiplans\n' > "$WORK/prefix.gitignore"
out="$(porcelain_for "$WORK/prefix.gitignore")"
assert_contains "neg: pre-fix '.aitask-data/' leaves the symlink untracked" \
    "?? .aitask-data" "$out"
assert_contains "neg: control symlink is reported" "?? $CONTROL" "$out"

# --- Case C: the rewriter repairs legacy lines, and only those ----------------
echo "--- Case C: rewrite legacy lines to the symlink-safe form ---"
C="$WORK/c.gitignore"
# Built from NAMES, so every derived name gets a legacy line to repair.
{ echo "foo/"; for name in "${NAMES[@]}"; do echo "$name/"; done; echo "bar"; } > "$C"
rc=0; _ait_rewrite_data_gitignore_lines "$C" || rc=$?
assert_eq "C: rewrite reports a change (0)" "0" "$rc"
assert_eq "C: exact rewritten content (unrelated lines untouched)" \
    "$(echo "foo/"; printf '%s\n' "${NAMES[@]}"; echo "bar")" "$(cat "$C")"
check_gitignore "C" "$C"
rc=0; _ait_rewrite_data_gitignore_lines "$C" || rc=$?
assert_eq "C: second run reports nothing to do (1)" "1" "$rc"
rc=0; _ait_rewrite_data_gitignore_lines "$WORK/does-not-exist" || rc=$?
assert_eq "C: missing .gitignore reports nothing to do (1)" "1" "$rc"

# --- Case D: a failed repair is reported as a failure, never as "unchanged" ---
echo "--- Case D: failure is distinct from 'unchanged' ---"
LEGACY_BODY="$(printf '.aitask-data/\naitasks\naiplans')"

# setup_data_gitignore_symlink_safe reads $SCRIPT_DIR/../.gitignore.
D_PROJ="$WORK/dproj"
mkdir -p "$D_PROJ/.aitask-scripts"
SETUP_SCRIPT_DIR_SAVED="$SCRIPT_DIR"
SCRIPT_DIR="$D_PROJ/.aitask-scripts"

# run_repair -> REPAIR_RC / REPAIR_OUT from the user-facing re-run step.
run_repair() {
    REPAIR_RC=0
    REPAIR_OUT="$(setup_data_gitignore_symlink_safe 2>&1)" || REPAIR_RC=$?
}

# D1: the write itself fails. atomic_write.sh's load guard keeps the
# rewriter's lazy `source` from restoring the real ait_atomic_render.
printf '%s\n' "$LEGACY_BODY" > "$D_PROJ/.gitignore"
cp "$D_PROJ/.gitignore" "$WORK/d.before"
# shellcheck source=../.aitask-scripts/lib/atomic_write.sh
source "$PROJECT_DIR/.aitask-scripts/lib/atomic_write.sh"
eval "$(declare -f ait_atomic_render | sed '1s/ait_atomic_render/_real_ait_atomic_render/')"
ait_atomic_render() { return 1; }
rc=0; _ait_rewrite_data_gitignore_lines "$D_PROJ/.gitignore" || rc=$?
assert_eq "D1: write failure reports 2 (not 1)" "2" "$rc"
assert_exit_zero "D1: file byte-identical after failed write" \
    cmp -s "$WORK/d.before" "$D_PROJ/.gitignore"
run_repair
assert_eq "D1: repair step stays non-fatal" "0" "$REPAIR_RC"
assert_contains "D1: repair step warns it could not rewrite" "Could not rewrite" "$REPAIR_OUT"
assert_not_contains "D1: repair step does not claim already-safe" "already symlink-safe" "$REPAIR_OUT"
eval "$(declare -f _real_ait_atomic_render | sed '1s/_real_ait_atomic_render/ait_atomic_render/')"
rc=0; _ait_rewrite_data_gitignore_lines "$D_PROJ/.gitignore" || rc=$?
assert_eq "D1 control: real render succeeds (0)" "0" "$rc"

# D2: the .gitignore cannot be inspected (a directory: grep exits 2). Holds
# under root too, unlike a permission fault.
rm -f "$D_PROJ/.gitignore"
mkdir "$D_PROJ/.gitignore"
rc=0; _ait_rewrite_data_gitignore_lines "$D_PROJ/.gitignore" || rc=$?
assert_eq "D2: uninspectable .gitignore reports 2 (not 1)" "2" "$rc"
run_repair
assert_contains "D2: repair step warns it could not rewrite" "Could not rewrite" "$REPAIR_OUT"
assert_not_contains "D2: repair step does not claim already-safe" "already symlink-safe" "$REPAIR_OUT"
rmdir "$D_PROJ/.gitignore"

# D3: a read-only .gitignore is refused, not replaced.
printf '%s\n' "$LEGACY_BODY" > "$D_PROJ/.gitignore"
chmod 444 "$D_PROJ/.gitignore"
if [[ -w "$D_PROJ/.gitignore" ]]; then
    echo "NOTE: D3 skipped — running as a user that can write a mode-444 file (root)"
else
    cp "$D_PROJ/.gitignore" "$WORK/d.before"
    rc=0; _ait_rewrite_data_gitignore_lines "$D_PROJ/.gitignore" || rc=$?
    assert_eq "D3: read-only .gitignore reports 2 (not 1)" "2" "$rc"
    assert_exit_zero "D3: read-only file byte-identical" \
        cmp -s "$WORK/d.before" "$D_PROJ/.gitignore"
    run_repair
    assert_contains "D3: repair step warns it could not rewrite" "Could not rewrite" "$REPAIR_OUT"
    chmod 644 "$D_PROJ/.gitignore"
    rc=0; _ait_rewrite_data_gitignore_lines "$D_PROJ/.gitignore" || rc=$?
    assert_eq "D3 control: writable again, rewrite succeeds (0)" "0" "$rc"
fi

# Unchanged is reported as unchanged.
run_repair
assert_contains "D: clean file reports already symlink-safe" "already symlink-safe" "$REPAIR_OUT"
SCRIPT_DIR="$SETUP_SCRIPT_DIR_SAVED"

# --- Case E: the repair keeps the file's mode and writes through a symlink ----
echo "--- Case E: mode and symlinked .gitignore preserved ---"
E="$WORK/e.gitignore"
printf '%s\n' "$LEGACY_BODY" > "$E"
# 664 differs from mktemp's 0600 and from the umask-022 default 0644, so a
# replacement that drops the mode cannot pass by accident.
chmod 664 "$E"
rc=0; (umask 022; _ait_rewrite_data_gitignore_lines "$E") || rc=$?
assert_eq "E: rewrite succeeds (0)" "0" "$rc"
assert_eq "E: mode 664 preserved" "664" "$(ait_file_mode "$E")"
assert_exit_zero "E: legacy line rewritten" grep -qxF ".aitask-data" "$E"

mkdir -p "$WORK/elink"
printf '%s\n' "$LEGACY_BODY" > "$WORK/elink/shared.gitignore"
ln -s shared.gitignore "$WORK/elink/.gitignore"
rc=0; _ait_rewrite_data_gitignore_lines "$WORK/elink/.gitignore" || rc=$?
assert_eq "E: symlinked .gitignore rewrite succeeds (0)" "0" "$rc"
assert_eq "E: the .gitignore symlink survives" "link" \
    "$([[ -L "$WORK/elink/.gitignore" ]] && echo link || echo notlink)"
assert_exit_zero "E: rewrite landed in the link target" \
    grep -qxF ".aitask-data" "$WORK/elink/shared.gitignore"
assert_eq "E: no staging temp left beside the target" "" \
    "$(find "$WORK/elink" -name '.shared.gitignore.*' -print)"

# --- Case F: CRLF .gitignore (core.autocrlf=true checkouts) -------------------
# Git strips a trailing CR before matching, so CRLF `.aitask-data/` is still
# directory-only and leaves the symlink untracked — but grep -x and a plain awk
# record both see the CR, so a naive rewriter reports "nothing to do".
echo "--- Case F: CRLF legacy lines are detected and rewritten ---"
F="$WORK/f.gitignore"
legacy_crlf=""
for name in "${NAMES[@]}"; do legacy_crlf+="$name/"$'\r\n'; done
printf 'foo/\r\n%s# keep\r\n' "$legacy_crlf" > "$F"
# Precondition, asked of git: the CRLF legacy file really exposes the symlinks.
out="$(porcelain_for "$F")"
assert_contains "F: precondition: CRLF '.aitask-data/' leaves the symlink untracked" \
    "?? $AIT_DATA_DIR_NAME" "$out"

rc=0; _ait_rewrite_data_gitignore_lines "$F" || rc=$?
assert_eq "F: CRLF legacy lines detected and rewritten (0)" "0" "$rc"
expected_crlf="foo/"$'\r\n'
for name in "${NAMES[@]}"; do expected_crlf+="$name"$'\r\n'; done
expected_crlf+="# keep"$'\r\n'
printf '%s' "$expected_crlf" > "$WORK/f.expected"
assert_exit_zero "F: bytes exact — CRLF kept on every line, unrelated lines untouched" \
    cmp -s "$WORK/f.expected" "$F"
check_gitignore "F" "$F"
rc=0; _ait_rewrite_data_gitignore_lines "$F" || rc=$?
assert_eq "F: second run on CRLF is a no-op (1)" "1" "$rc"

echo
echo "=== Results ==="
echo "Total:  $TOTAL"
echo "Pass:   $PASS"
echo "Fail:   $FAIL"
[[ "$FAIL" -eq 0 ]] && { echo "PASS"; exit 0; }
echo "FAIL"
exit 1
