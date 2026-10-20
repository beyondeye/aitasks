#!/usr/bin/env bash
# test_archive_rearm_exit_trap.sh - EXIT-trap re-arm sites keep the archive
# sweep (t2032).
#
# lib/archive_utils.sh sweeps this shell's `ait-archive.<owner>.*` extraction
# dirs from the EXIT trap. A later `trap X EXIT` / `trap - EXIT` replaces that
# trap, so every bundled `$( resolve … )` made in the process leaked a dir.
# ait_archive_rearm_exit_trap, called right after such a `trap`, puts the sweep
# back. tests/test_archive_rearm_tripwire.py enforces that every site calls it;
# this file proves what the call does:
#
#   1-3   plain handler / cleared trap: swept, handler runs, status kept;
#         case 2 is the no-re-arm control that leaks
#   4-6   the ledger lock's three spellings: the bare and explicit-status forms
#         keep their status, the misuse form still trips the first-command
#         detector -- with a real lock dir, released in every case
#   7     idempotence
#   8a-d  a `( )` child that re-arms its own trap never deletes the parent's
#         live extraction (8a/8d: the inherited _AIT_ARCHIVE_TMPDIR case,
#         incl. the bash 3.2 path), but still cleans up its own (8c)
#   9-10  lib/registry_lock.sh: acquire/release with the archive lib loaded,
#         and the guard when it is not
#   R1-R2 real entry points -- `aitask_gate.sh append` and `aitask_note.sh`:
#         a task that exists only inside an archive bundle is refused (its
#         extraction is swept at exit) and leaves nothing behind; a loose
#         archived task stays writable and the write survives the exit
#
# Each case is a child script run under its own probe TMPDIR; what matters is
# what the child's EXIT leaves behind. Assertions stay in this shell.
#
# Run: bash tests/test_archive_rearm_exit_trap.sh
#      SHELL_UNDER_TEST=/bin/bash bash tests/test_archive_rearm_exit_trap.sh

# SC2016: the single-quoted case bodies are child-script source, expanded there.
# SC2010: probe dirs hold only mktemp names, as in test_resolve_tar_zst.sh.
# shellcheck disable=SC2016,SC2010
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

LIB="$PROJECT_DIR/.aitask-scripts/lib"
SHELL_UNDER_TEST="${SHELL_UNDER_TEST:-${BASH:-bash}}"
WARN="ran behind another command"

FIX="$(mktemp -d "${TMPDIR:-/tmp}/test_archive_rearm_XXXXXX")"
trap 'rm -rf "$FIX"' EXIT
export AITASKS_LOCK_DIR="$FIX/locks"
mkdir -p "$AITASKS_LOCK_DIR"

# A one-file bundle every case extracts from.
mkdir -p "$FIX/st"
echo "bundled content" > "$FIX/st/t91_j.md"
ARCHIVE="$FIX/old0.tar.zst"
tar -cf - -C "$FIX/st" t91_j.md | zstd -q -o "$ARCHIVE"

# run_case <body> [pre] [libs] -> RC, OUT, LEFT (ait-archive.* dirs left in the
# probe after the child exited), MARK (a file the body may append to).
# <pre> runs before any lib is sourced; <libs>=noarchive leaves archive_utils
# out (and makes no extraction).
run_case() {
    local body="$1" pre="${2:-}" libs="${3:-}"
    PROBE="$(mktemp -d "$FIX/probe.XXXXXX")"
    MARK="$PROBE.mark"
    : > "$MARK"
    {
        echo '#!/usr/bin/env bash'
        echo 'set -uo pipefail'
        printf '%s\n' "$pre"
        echo "export SCRIPT_DIR='$PROJECT_DIR/.aitask-scripts'"
        echo "A='$ARCHIVE' MARK='$MARK'"
        echo ". '$LIB/terminal_compat.sh'"
        echo ". '$LIB/stale_lock.sh'"
        echo ". '$LIB/ledger_block.sh'"
        echo ". '$LIB/registry_lock.sh'"
        if [[ "$libs" != noarchive ]]; then
            echo ". '$LIB/archive_utils.sh'"
            # A bundled extraction inside $( ): its dir outlives the
            # subshell, and only the owning shell's EXIT sweep removes it.
            cat <<'EOF'
xt() { _extract_from_archive "$A" t91_j.md && echo "$_AIT_EXTRACT_RESULT"; }
f="$(xt)"; [[ -s "$f" ]] || { echo "NO_EXTRACTION"; exit 99; }
EOF
        fi
        printf '%s\n' "$body"
    } > "$PROBE.sh"
    RC=0
    OUT="$(TMPDIR="$PROBE" "$SHELL_UNDER_TEST" "$PROBE.sh" 2>&1)" || RC=$?
    LEFT="$(ls -A "$PROBE" 2>/dev/null | grep -c '^ait-archive\.' || true)"
}

echo "=== test_archive_rearm_exit_trap.sh (bash $("$SHELL_UNDER_TEST" -c 'printf %s "$BASH_VERSION"')) ==="

# --- 1-3: plain handlers -------------------------------------------------------
echo "--- 1-3: plain handler and cleared trap ---"
run_case '
trap '\''echo ran >> "$MARK"'\'' EXIT
ait_archive_rearm_exit_trap
echo "TRAP:$(trap -p EXIT)"
exit 7'
assert_eq "1: the status survives the chain" "7" "$RC"
assert_eq "1: the bundled extraction was swept" "0" "$LEFT"
assert_eq "1: the script's handler ran once" "ran" "$(cat "$MARK")"
assert_contains "1: the re-armed trap is the chain" \
    "TRAP:trap -- '_ait_archive_exit_chain' EXIT" "$OUT"

run_case '
trap '\''echo ran >> "$MARK"'\'' EXIT
exit 7'
assert_eq "2 (control): without the re-arm the extraction leaks" "1" "$LEFT"
assert_eq "2 (control): the handler still ran" "ran" "$(cat "$MARK")"

run_case '
trap '\''echo ran >> "$MARK"'\'' EXIT
trap - EXIT
ait_archive_rearm_exit_trap
echo "TRAP:$(trap -p EXIT)"
exit 3'
assert_eq "3: status kept after a cleared trap" "3" "$RC"
assert_eq "3: swept after a cleared trap" "0" "$LEFT"
assert_eq "3: the cleared handler did not run" "" "$(cat "$MARK")"
assert_contains "3: a cleared trap re-arms the bare cleanup" \
    "TRAP:trap -- '_ait_archive_cleanup' EXIT" "$OUT"

# --- 4-6: the ledger lock's spellings, with a real lock dir --------------------
echo "--- 4-6: ledger lock first-command contract ---"
ledger_case() {  # <key> <trap text> <rearm:yes|no>
    local rearm=""
    [[ "$3" == yes ]] && rearm="ait_archive_rearm_exit_trap"
    run_case "
c() { :; }
ait_ledger_lock_acquire t2032 '$1' 'test lock' 'test lock'
echo \"LOCK:\$_AIT_LEDGER_LOCK_DIR\"
trap '$2' EXIT
$rearm
exit 42"
    LOCKDIR="$(sed -n 's/^LOCK://p' <<<"$OUT" | head -n1)"
}

ledger_case k4 'ait_ledger_lock_exit_trap' yes
assert_contains "4: the lock was really held" "LOCK:$AITASKS_LOCK_DIR/" "$OUT"
assert_eq "4: bare spelling keeps exit 42 through the chain" "42" "$RC"
assert_not_contains "4: no first-command warning for the bare spelling" "$WARN" "$OUT"
assert_dir_not_exists "4: the lock was released" "$LOCKDIR"
assert_eq "4: swept" "0" "$LEFT"

ledger_case k5 'c; ait_ledger_lock_exit_trap' yes
assert_eq "5: the misuse spelling still reports failure" "1" "$RC"
assert_contains "5: the first-command detector still fires" "$WARN" "$OUT"
assert_dir_not_exists "5: the lock was released" "$LOCKDIR"
assert_eq "5: swept" "0" "$LEFT"

ledger_case k5c 'c; ait_ledger_lock_exit_trap' no
assert_eq "5 (control): same verdict without the chain" "1" "$RC"
assert_contains "5 (control): same warning without the chain" "$WARN" "$OUT"
assert_eq "5 (control): and the extraction leaks" "1" "$LEFT"

ledger_case k6 'rc=$?; c; ait_ledger_lock_exit_trap "$rc"' yes
assert_eq "6: the explicit-status spelling keeps exit 42" "42" "$RC"
assert_not_contains "6: no warning for the explicit-status spelling" "$WARN" "$OUT"
assert_dir_not_exists "6: the lock was released" "$LOCKDIR"
assert_eq "6: swept" "0" "$LEFT"

# --- 7: idempotence -------------------------------------------------------------
echo "--- 7: idempotence ---"
run_case '
trap '\''echo ran >> "$MARK"'\'' EXIT
ait_archive_rearm_exit_trap
ait_archive_rearm_exit_trap
echo "TRAP:$(trap -p EXIT)"'
assert_eq "7: a second re-arm does not run the handler twice" "ran" "$(cat "$MARK")"
assert_contains "7: still one chain" "TRAP:trap -- '_ait_archive_exit_chain' EXIT" "$OUT"
assert_eq "7: swept" "0" "$LEFT"

# --- 8: a ( ) child that re-arms its own trap -----------------------------------
echo "--- 8: subshell re-arm and directory ownership ---"
CASE8A='
_extract_from_archive "$A" t91_j.md; pf="$_AIT_EXTRACT_RESULT"
[[ -s "$pf" ]] || exit 98
( trap '\''echo sub >> "$MARK"'\'' EXIT; ait_archive_rearm_exit_trap )
[[ -f "$pf" ]] && echo PARENT_KEPT || echo PARENT_DELETED'
run_case "$CASE8A"
assert_contains "8a: the child's re-armed trap ran" "sub" "$(cat "$MARK")"
assert_contains "8a: a direct parent extraction survives the child's exit" "PARENT_KEPT" "$OUT"
assert_eq "8a: and is removed when the parent exits" "0" "$LEFT"

run_case '
( trap : EXIT; ait_archive_rearm_exit_trap )
[[ -f "$f" ]] && echo PARENT_KEPT || echo PARENT_DELETED'
assert_contains "8b: a \$( ) parent extraction survives the child's exit" "PARENT_KEPT" "$OUT"
assert_eq "8b: and is swept when the parent exits" "0" "$LEFT"

run_case '
( _extract_from_archive "$A" t91_j.md; echo "$_AIT_EXTRACT_RESULT" > "$MARK"
  trap : EXIT; ait_archive_rearm_exit_trap )
cf="$(cat "$MARK")"
[[ -n "$cf" ]] || exit 97
[[ -e "$(dirname "$cf")" ]] && echo CHILD_KEPT || echo CHILD_GONE'
assert_contains "8c: the child's own direct extraction is removed at child exit" "CHILD_GONE" "$OUT"
assert_eq "8c: nothing left after the parent" "0" "$LEFT"

run_case "echo \"BASHPID=[\${BASHPID:-}]\"
$CASE8A" 'unset BASHPID'
assert_contains "8d: BASHPID really is unset (the bash 3.2 path)" "BASHPID=[]" "$OUT"
assert_contains "8d: bash 3.2 path keeps the parent's direct extraction" "PARENT_KEPT" "$OUT"
assert_eq "8d: and the parent still cleans it up" "0" "$LEFT"

# --- 9-10: lib/registry_lock.sh ------------------------------------------------
echo "--- 9-10: registry lock ---"
run_case "
registry_lock_acquire '$AITASKS_LOCK_DIR/reg9' 2 || exit 98
echo \"TRAP:\$(trap -p EXIT)\"
exit 5"
assert_contains "9: acquire re-arms through the chain" \
    "TRAP:trap -- '_ait_archive_exit_chain' EXIT" "$OUT"
assert_eq "9: dying while held keeps the status" "5" "$RC"
assert_dir_not_exists "9: dying while held still releases the lock" "$AITASKS_LOCK_DIR/reg9"
assert_eq "9: dying while held still sweeps" "0" "$LEFT"

run_case "
registry_lock_acquire '$AITASKS_LOCK_DIR/reg9b' 2 || exit 98
registry_lock_release '$AITASKS_LOCK_DIR/reg9b'
echo \"TRAP:\$(trap -p EXIT)\""
assert_eq "9b: acquire + release exits 0" "0" "$RC"
assert_contains "9b: release re-arms the bare cleanup" \
    "TRAP:trap -- '_ait_archive_cleanup' EXIT" "$OUT"
assert_dir_not_exists "9b: the lock was released" "$AITASKS_LOCK_DIR/reg9b"
assert_eq "9b: swept" "0" "$LEFT"

run_case "
set -e
registry_lock_acquire '$AITASKS_LOCK_DIR/reg10' 2
registry_lock_release '$AITASKS_LOCK_DIR/reg10'
echo DONE" "" noarchive
assert_eq "10: registry_lock without archive_utils runs clean under set -e" "0" "$RC"
assert_contains "10: and reaches the end" "DONE" "$OUT"

# --- R: real entry points ------------------------------------------------------
# t5 exists ONLY inside a bundle, so resolving it extracts to a temp dir; t7 is
# a loose archived file (a real repo path). Writes to a bundled task are refused
# before the lock (t2032): the extraction is swept at exit, so any write there
# would be reported and then vanish. The refusal paths still resolved through
# the archive tier, so they also prove the process's sweep survived its traps.
echo "--- R: real entry points ---"
PROJ="$FIX/proj"
mkdir -p "$PROJ/aitasks/metadata" "$PROJ/aitasks/archived/_b0" "$PROJ/aiplans/archived" "$FIX/st5"
cat > "$PROJ/aitasks/metadata/gates.yaml" <<'EOF'
gates:
  tests_pass:
    type: machine
    description: "x"
EOF
printf -- '---\nstatus: Done\ngates: [tests_pass]\n---\nBundled body.\n' > "$FIX/st5/t5_bundled.md"
tar -cf - -C "$FIX/st5" . | zstd -q -o "$PROJ/aitasks/archived/_b0/old0.tar.zst"
printf -- '---\nstatus: Done\ngates: [tests_pass]\n---\nLoose body.\n' > "$PROJ/aitasks/archived/t7_loose.md"
printf -- '---\nstatus: Implementing\n---\nActive.\n' > "$PROJ/aitasks/t300_active.md"
( cd "$PROJ" && git init -q && git add -A \
    && git -c user.email=t@t -c user.name=t commit -qm init )
BUNDLE_SUM="$(cksum < "$PROJ/aitasks/archived/_b0/old0.tar.zst")"

run_real() {  # <script> <args...> -> RC, OUT, LEFT
    local script="$1"; shift
    PROBE="$(mktemp -d "$FIX/probe.XXXXXX")"
    RC=0
    OUT="$(cd "$PROJ" && TMPDIR="$PROBE" TASK_DIR=aitasks \
        GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t \
        "$SHELL_UNDER_TEST" "$PROJECT_DIR/.aitask-scripts/$script" "$@" 2>&1)" || RC=$?
    LEFT="$(ls -A "$PROBE" 2>/dev/null | grep -c '^ait-archive\.' || true)"
}

# R1: gate append on the bundled task is refused, naming the bundle.
run_real aitask_gate.sh append 5 tests_pass pass
assert_exit_nonzero_rc "R1: gate append on a bundled task is refused" "$RC"
assert_contains "R1: the refusal names the bundle" "packed into an archive bundle" "$OUT"
assert_not_contains "R1: no block is reported written" "gate:tests_pass" "$OUT"
assert_eq "R1: the bundle is untouched" "$BUNDLE_SUM" "$(cksum < "$PROJ/aitasks/archived/_b0/old0.tar.zst")"
assert_eq "R1: the extraction made by the resolve was swept" "0" "$LEFT"

# R1b (control): a loose archived task stays writable, and the block is still
# in the file after the process exited.
run_real aitask_gate.sh append 7 tests_pass pass
assert_eq "R1b: gate append on a loose archived task succeeds" "0" "$RC"
assert_contains "R1b: the block persisted in the loose file" "gate:tests_pass" \
    "$(cat "$PROJ/aitasks/archived/t7_loose.md")"

# R2: note on the bundled task -- refused with the id-less error, nothing
# written. note.sh arms `trap note_cleanup EXIT` at top level, which used to drop
# the sweep for every run (pre-fix: 1 leaked dir here).
run_real aitask_note.sh 5 --from 300 --text bundled-probe
assert_eq "R2: note to a bundled task exits 1" "1" "$RC"
assert_contains "R2: refused with NOTE_ERROR:target-bundled" "NOTE_ERROR:target-bundled" "$OUT"
assert_not_contains "R2: no id-bearing outcome is reported" "NOTE_APPENDED" "$OUT"
assert_eq "R2: the bundle is untouched" "$BUNDLE_SUM" "$(cksum < "$PROJ/aitasks/archived/_b0/old0.tar.zst")"
assert_eq "R2: note's top-level trap keeps the sweep" "0" "$LEFT"

run_real aitask_note.sh read 5 --by t5 --ids x --mode explicit
assert_contains "R2b: a receipt on a bundled task is refused too" "READ_ERROR:target-bundled" "$OUT"
assert_eq "R2b: swept" "0" "$LEFT"

# R2c (control): a note to a loose archived task lands, and the file the
# outcome names still holds it after the process exited.
run_real aitask_note.sh 7 --from 300 --text loose-probe
assert_contains "R2c: note to a loose archived task is appended" "NOTE_APPENDED" "$OUT"
R2C_PATH="$(sed -n 's/^NOTE_APPENDED[A-Z_]*:[^|]*|\([^|]*\).*/\1/p' <<<"$OUT" | head -n1)"
assert_eq "R2c: the reported path is the loose file" "aitasks/archived/t7_loose.md" "$R2C_PATH"
assert_contains "R2c: the reported file still holds the note after exit" "loose-probe" \
    "$(cat "$PROJ/$R2C_PATH" 2>/dev/null)"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]] || exit 1
echo "ALL TESTS PASSED"
