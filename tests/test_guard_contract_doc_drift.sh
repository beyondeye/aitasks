#!/usr/bin/env bash
# test_guard_contract_doc_drift.sh — the `.gc` guard's published contract must
# not outlive the implementation (t1598).
#
# Before t1598 the guard was fail-closed and never auto-broken, and that was
# stated as fact in the lock libs, in aidocs, in `merge-broker.md` and in its
# NINE rendered mirrors plus a golden. Protocol G changed it: the guard now
# carries a holder record, a dead-record guard is reclaimed everywhere, and a
# recordless one is reclaimed where the caller opts in. A doc sweep that is
# merely *performed* drifts the next time any of those ten copies is touched;
# one that is *asserted* does not.
#
# SCOPE — this bans only the superseded UNIVERSAL claims, i.e. sentences that
# are now false for every guard. It deliberately does NOT ban:
#
#   * "never `rm -rf`" — still true and still load-bearing. `rmdir` is
#     structurally incapable of destroying a lock's contents, which is exactly
#     why it is the prescribed cure.
#   * scoped manual-recovery language. Two residuals genuinely still need a
#     human — a recycled holder pid reads as alive, and a hung holder is never
#     displaced — and that must stay documented and truthful. The discriminator
#     is UNIVERSALITY, not the word "manual".
#
# Where a mechanical pattern cannot separate the two, this guard prefers to let
# the phrase through: a false negative costs a stale sentence, a false positive
# pressures a future editor into deleting a true limitation.
#
# Run: bash tests/test_guard_contract_doc_drift.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

cd "$PROJECT_DIR" || exit 1

# Pinned root set. Asserted below to be non-empty and present, so a renamed or
# mistyped root cannot make this guard silently scan nothing.
ROOTS=(
    ".aitask-scripts"
    ".claude/skills"
    ".agents/skills"
    ".opencode/skills"
    "aidocs"
    "tests/golden"
)

# Superseded UNIVERSAL claims. Each is a fixed string, matched with `grep -F`.
BANNED=(
    "never automatically stolen"
    "never auto-broken"
    "guard dirs are always empty"
    "nothing ever writes into them"
    "No age/PID heuristics on the guard"
    "emptiness is the proof that no reclaim is running"
)

echo "=== Test 1: the pinned roots exist ==="
missing=0
for r in "${ROOTS[@]}"; do
    [[ -d "$r" ]] || { echo "  missing root: $r"; missing=1; }
done
assert_eq "every pinned scan root is present" "0" "$missing"

scan() {   # scan <needle> — echo matching "path:line" records, one per line
    grep -rInF -- "$1" "${ROOTS[@]}" 2>/dev/null || true
}

echo
echo "=== Test 2: no superseded universal claim survives ==="
for needle in "${BANNED[@]}"; do
    hits="$(scan "$needle")"
    n="$(printf '%s' "$hits" | grep -c . || true)"
    # The HIT COUNT is asserted, not a clean exit: `grep … || echo OK` exits 0
    # both on "no match" and on a mistyped path, so an exit-status-only check
    # would pass while checking nothing.
    assert_eq "no surviving claim: '$needle'" "0" "$n"
    [[ "$n" -eq 0 ]] || printf '%s\n' "$hits" | sed 's/^/      /'
done

echo
echo "=== Test 3: a prescribed .gc cure names the holder record ==="
# A guard carrying a record is not empty, so a bare `rmdir <dir>.gc` returns
# ENOTEMPTY. Any line that PRESCRIBES the cure must use the two-argument form.
# Lines that merely explain the ENOTEMPTY behaviour are exempt by construction —
# they say so.
# PARAGRAPH-folded, not line-matched: the explanatory sentence wraps, so
# `ENOTEMPTY` lands on the NEXT line and a per-line `grep -v` cannot see it.
# Measured — the line-oriented version flagged all 11 copies of a correct
# sentence.
cure_scan() {
    python3 - "$@" <<'PYEOF'
import re, sys, pathlib
roots = sys.argv[1:]
pat = re.compile(r"rmdir '[^']*\.gc'")
for root in roots:
    for path in pathlib.Path(root).rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for para in re.split(r"\n\s*\n", text):
            flat = " ".join(para.split())
            for m in pat.finditer(flat):
                # Exempt the two legitimate shapes: the two-argument cure
                # itself, and prose explaining why a bare rmdir fails.
                window = flat[max(0, m.start() - 200):m.end() + 200]
                if "h.*" in window or "ENOTEMPTY" in window:
                    continue
                print(f"{path}: ...{flat[max(0, m.start()-60):m.end()+60]}...")
PYEOF
}
cure_hits="$(cure_scan "${ROOTS[@]}")"
cure_n="$(printf '%s' "$cure_hits" | grep -c . || true)"
assert_eq "every prescribed .gc cure includes the h.* record" "0" "$cure_n"
[[ "$cure_n" -eq 0 ]] || printf '%s\n' "$cure_hits" | sed 's/^/      /'

echo
echo "=== Test 4: POSITIVE CONTROL — the matcher actually fires ==="
# Without this, a mistyped pattern or a broken root set reads exactly like a
# clean tree. Plant each banned claim in a scanned root and require a hit.
CTL_DIR="aidocs/.t1598_doc_drift_control"
mkdir -p "$CTL_DIR"
cleanup_ctl() { rm -rf "$CTL_DIR"; }
trap cleanup_ctl EXIT

for needle in "${BANNED[@]}"; do
    printf 'fixture: %s\n' "$needle" > "$CTL_DIR/fixture.md"
    n="$(scan "$needle" | grep -c . || true)"
    assert_eq "control: the matcher finds a planted '$needle'" "1" "$n"
done

printf "Remove it with \`rmdir '<dir>.gc'\`.\n" > "$CTL_DIR/fixture.md"
n="$(cure_scan "${ROOTS[@]}" | grep -c "$CTL_DIR" || true)"
assert_eq "control: the matcher finds a planted bare-rmdir cure" "1" "$n"

cleanup_ctl
trap - EXIT

echo
echo "=== Test 5: NEGATIVE CONTROL — true residual language is allowed ==="
# These must NOT be flagged: the first is still true, the second and third are
# correctly scoped to the two residuals that genuinely need a human.
mkdir -p "$CTL_DIR"
trap cleanup_ctl EXIT
cat > "$CTL_DIR/fixture.md" <<'FIX'
Never `rm -rf` the guard.
When the holder's pid was recycled, the cure is manual.
A hung holder is never displaced; recover it by hand.
Remove it with `rmdir '<dir>.gc'/h.* '<dir>.gc'`.
FIX
allowed_hits=0
for needle in "${BANNED[@]}"; do
    n="$(scan "$needle" | grep -c "$CTL_DIR" || true)"
    allowed_hits=$(( allowed_hits + n ))
done
n="$(cure_scan "${ROOTS[@]}" | grep -c "$CTL_DIR" || true)"
allowed_hits=$(( allowed_hits + n ))
assert_eq "scoped residual + 'never rm -rf' + the real cure are NOT flagged" \
    "0" "$allowed_hits"
cleanup_ctl
trap - EXIT

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -gt 0 ]] && exit 1
echo "All tests PASSED"
