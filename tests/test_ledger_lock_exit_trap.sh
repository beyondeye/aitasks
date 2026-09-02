#!/usr/bin/env bash
# test_ledger_lock_exit_trap.sh - The EXIT-trap contract of the marker-block
# ledger seam, lib/ledger_block.sh (t1681).
#
# ait_ledger_lock_exit_trap() opens with `local rc=$?` because its whole job is
# to preserve the status of whatever killed the guarded section. `$?` reflects
# the command that ran IMMEDIATELY BEFORE it, so the natural-looking
#
#     trap 'my_cleanup; ait_ledger_lock_exit_trap' EXIT
#
# silently destroys that status: my_cleanup succeeds, $? becomes 0, the trap
# exits 0 for a section that died. Measured in t1657_2 as `ait note` reporting
# NOTE_APPENDED (success) for an append whose lock was wedged.
#
# Coverage map:
#
#   group 0   the `trap -p EXIT` rendering the guard parses      (inline
#             pre-phase mitigation pin_trap_p_rendering_matrix — pins the
#             assumption so a shell that renders differently fails HERE rather
#             than silently losing the guard)
#   1, 2, 2b  naive chain: detected, never reported as success
#   3         explicit-arg chain: EXACT status preservation
#   4, 5, 6   negative controls (bare trap, explicit-arg success)
#   7         a failed release still beats a successful section
#   8, 9, 10  the 0-255 status domain, leading zeros, malformed arguments
#   11        validation is silent (no bash arithmetic diagnostics)
#
# Cases 1, 2, 2b and 3 FAIL against the pre-t1681 library (all exit 0) — they
# are the discriminating cases, not a post-hoc restatement of the fix.
#
# Drivers are written into a mktemp fixture and run with `bash`; every assertion
# stays in THIS shell, so the file-backed counters (CLAUDE.md / t1207) are not
# needed.
#
# Run: bash tests/test_ledger_lock_exit_trap.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

LIB="$PROJECT_DIR/.aitask-scripts/lib"
FIX="$(mktemp -d "${TMPDIR:-/tmp}/test_ledger_trap_XXXXXX")"
trap 'rm -rf "$FIX"' EXIT

# --- driver scaffolding -----------------------------------------------------
#
# Every driver sources the REAL library trio. stale_lock.sh is sourced because
# ledger_block.sh depends on it; the lock itself is never acquired here — this
# file is about the trap's status arithmetic, and ait_ledger_lock_release is
# stubbed so a driver never touches a real lock directory.

driver_prelude() {
    cat <<EOF
#!/usr/bin/env bash
set -uo pipefail
. "$LIB/terminal_compat.sh"
. "$LIB/stale_lock.sh"
. "$LIB/ledger_block.sh"
EOF
}

# run_driver <file> [args...] -> sets RC, OUT_ERR (stderr only; stdout dropped)
RC=0
OUT_ERR=""
run_driver() {
    local f="$1"; shift
    OUT_ERR="$(bash "$f" "$@" 2>&1 >/dev/null)"
    RC=$?
}

# =====================================================================
# Group 0 — the `trap -p EXIT` rendering the guard parses
#           (inline pre-phase: pin_trap_p_rendering_matrix)
#
# The guard decides "am I the first command of the EXIT trap?" by reading
# `trap -p EXIT` from inside the firing trap and matching the `trap -- '…' EXIT`
# rendering. Two facts have to hold for that to work at all, and neither is
# guaranteed by anything this repo controls:
#
#   * `trap -p` inside a command substitution reports the PARENT's trap (the
#     POSIX `saved=$(trap)` idiom), not the subshell's reset one;
#   * bash renders the handler single-quoted, verbatim, whatever shape it was
#     installed in.
#
# Pin both, for every handler shape a consumer can plausibly write. A shell
# that renders differently fails here — loudly — instead of silently degrading
# the guard to a no-op in group 1.
# =====================================================================

cat > "$FIX/render.sh" <<EOF
$(driver_prelude)
show() { printf 'SPEC=[%s]\n' "\$(trap -p EXIT)"; }
c() { :; }
case "\$1" in
    bare)      trap show EXIT ;;
    quoted)    trap 'show' EXIT ;;
    chained)   trap 'c; show' EXIT ;;
    multiline) trap \$'show\nc' EXIT ;;
esac
exit 0
EOF

render_of() { bash "$FIX/render.sh" "$1" 2>/dev/null; }

assert_eq "0a. bare word handler renders single-quoted" \
    "SPEC=[trap -- 'show' EXIT]" "$(render_of bare)"
assert_eq "0b. quoted single-command handler renders identically" \
    "SPEC=[trap -- 'show' EXIT]" "$(render_of quoted)"
assert_eq "0c. chained handler keeps the leading command visible" \
    "SPEC=[trap -- 'c; show' EXIT]" "$(render_of chained)"
assert_eq "0d. multi-line handler keeps its newline" \
    "$(printf 'SPEC=[trap -- %s\nc%s EXIT]' "'show" "'")" "$(render_of multiline)"

# =====================================================================
# The contract drivers.
#
# `section` is the guarded body: `exit $2` simulates a die inside it, and the
# EXIT trap is what the fix is about. `cleanup` returns $CLEAN_RC so case 2b can
# drive a FAILING cleanup — the only input that separates an unconditional
# rc=1 from `[[ $rc -ne 0 ]] || rc=1`.
# =====================================================================

cat > "$FIX/trap.sh" <<EOF
$(driver_prelude)
# Never touch a real lock: this file tests the status arithmetic, not the mutex.
ait_ledger_lock_release() { return "\${RELEASE_RC:-0}"; }
cleanup() { return "\${CLEAN_RC:-0}"; }

spelling="\$1"; section_rc="\$2"; arg="\${3-}"
case "\$spelling" in
    bare)        trap 'ait_ledger_lock_exit_trap' EXIT ;;
    naive)       trap 'cleanup; ait_ledger_lock_exit_trap' EXIT ;;
    explicit)    trap 'r=\$?; cleanup; ait_ledger_lock_exit_trap "\$r"' EXIT ;;
    # Argument under test, passed verbatim from the parent — the status-domain
    # matrix. Written through a variable so no value is ever re-expanded.
    explicit_arg) ARG="\$arg"; trap 'cleanup; ait_ledger_lock_exit_trap "\$ARG"' EXIT ;;
esac
(exit "\$section_rc")
EOF

# --- 1 / 2 / 2b. Naive chain: detected, never a success ---------------------

run_driver "$FIX/trap.sh" naive 7
assert_eq "1. naive chain + death exits exactly 1 (pre-fix: 0)" "1" "$RC"
assert_contains "2. and the guard says so, naming the function" \
    "ait_ledger_lock_exit_trap" "$OUT_ERR"
assert_contains "2a. the warning spells out the explicit-status remedy" \
    'ait_ledger_lock_exit_trap "$rc"' "$OUT_ERR"

CLEAN_RC=42 run_driver "$FIX/trap.sh" naive 7
assert_eq "2b. naive chain + FAILING cleanup + death still exits exactly 1" "1" "$RC"
assert_contains "2b-i. and still warns" "ait_ledger_lock_exit_trap" "$OUT_ERR"

CLEAN_RC=42 run_driver "$FIX/trap.sh" naive 0
assert_eq "2c. naive chain + FAILING cleanup + SUCCESS exits exactly 1, not 42" "1" "$RC"

# --- 3. Explicit-arg chain: EXACT preservation ------------------------------
#
# This is the task's "chained trap, forced death, status preserved" case, using
# the correct spelling the fix introduces.

run_driver "$FIX/trap.sh" explicit 7
assert_eq "3. explicit-arg chain + death preserves 7 exactly (pre-fix: 0)" "7" "$RC"
assert_eq "3a. and is silent" "" "$OUT_ERR"

run_driver "$FIX/trap.sh" explicit 255
assert_eq "3b. explicit-arg chain preserves the top of the domain (255)" "255" "$RC"

# --- 4 / 5 / 6. Negative controls -------------------------------------------
#
# The sanctioned spellings must be byte-for-byte unaffected. These pass BEFORE
# and after the fix; a guard that fired here would be worse than no guard.

run_driver "$FIX/trap.sh" bare 7
assert_eq "4. bare trap + death preserves 7" "7" "$RC"
assert_eq "4a. bare trap does not warn" "" "$OUT_ERR"

run_driver "$FIX/trap.sh" bare 0
assert_eq "5. bare trap + success exits 0" "0" "$RC"
assert_eq "5a. and does not warn" "" "$OUT_ERR"

run_driver "$FIX/trap.sh" explicit 0
assert_eq "6. explicit-arg chain + success exits 0" "0" "$RC"
assert_eq "6a. and does not warn" "" "$OUT_ERR"

# --- 7. A failed release still beats a successful section -------------------

RELEASE_RC=1 run_driver "$FIX/trap.sh" bare 0
assert_eq "7. bare trap + successful section + failed release exits 1" "1" "$RC"

RELEASE_RC=1 run_driver "$FIX/trap.sh" bare 7
assert_eq "7a. a failed release does not overwrite a real dying status" "7" "$RC"

# --- 8. The 0-255 status domain ---------------------------------------------
#
# `exit` truncates modulo 256, so a digit-only validator would let 256 and 512
# exit 0 — re-opening the exact false success this task closes, through the new
# parameter. Measured: exit 256 -> 0, exit 512 -> 0, exit 300 -> 44.

for v in 0 7 9 10 99 100 199 200 249 250 255; do
    run_driver "$FIX/trap.sh" explicit_arg 7 "$v"
    assert_eq "8. explicit status '$v' is accepted verbatim" "$v" "$RC"
    assert_eq "8-i. and is silent for '$v'" "" "$OUT_ERR"
done

for v in 256 260 300 512; do
    run_driver "$FIX/trap.sh" explicit_arg 7 "$v"
    assert_eq "8b. out-of-domain status '$v' is rejected, exits 1" "1" "$RC"
    assert_contains "8b-i. and warns for '$v'" "$v" "$OUT_ERR"
done

# --- 9. Leading zeros -------------------------------------------------------
#
# `[[ 010 -le 255 ]]` ACCEPTS 010 as octal 8 — the trap would exit 8 for a
# caller who wrote decimal ten. `08` / `099` are invalid octal and make bash
# print `value too great for base`. Both are why the check is pattern-only.

for v in 007 08 010 099; do
    run_driver "$FIX/trap.sh" explicit_arg 7 "$v"
    assert_eq "9. leading-zero status '$v' is rejected, exits 1" "1" "$RC"
done

# --- 10. Malformed arguments ------------------------------------------------

run_driver "$FIX/trap.sh" explicit_arg 7 ""
assert_eq "10. empty status is rejected, exits 1" "1" "$RC"
for v in x -1 1e2 " 7" "7 " 99999999999999999999; do
    run_driver "$FIX/trap.sh" explicit_arg 7 "$v"
    assert_eq "10a. malformed status '$v' is rejected, exits 1" "1" "$RC"
done

# --- 11. Validation is silent ----------------------------------------------
#
# Exactly one stderr line — the warn. No `value too great for base` (which 08 /
# 099 produce under an arithmetic range check) and no `integer expected` (which
# the 20-digit value produces). Asserted on the whole stderr, not a substring,
# so a stray diagnostic cannot hide behind a passing containment check.

for v in 08 099 010 99999999999999999999 1e2; do
    run_driver "$FIX/trap.sh" explicit_arg 7 "$v"
    assert_eq "11. rejecting '$v' emits exactly one stderr line" "1" \
        "$(printf '%s\n' "$OUT_ERR" | grep -c .)"
    assert_not_contains "11a. no bash arithmetic diagnostic for '$v'" \
        "value too great for base" "$OUT_ERR"
    assert_not_contains "11b. no 'integer expected' diagnostic for '$v'" \
        "integer expected" "$OUT_ERR"
done

# --- summary ---------------------------------------------------------------
echo
echo "Results: $PASS passed, $FAIL failed (of $TOTAL)"
[[ "$FAIL" -eq 0 ]]
