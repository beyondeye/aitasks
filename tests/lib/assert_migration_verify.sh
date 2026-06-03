#!/usr/bin/env bash
# tests/lib/assert_migration_verify.sh — before/after verification harness for
# the t923 assert-helper consolidation.
#
# The safety net every migration child reuses: it captures each test file's
# pass/fail signature BEFORE migration, then re-runs AFTER migration and fails
# loudly on any change. As long as a migration only swaps an inline helper
# block for `. asserts.sh` (preserving each assertion's match logic), counts
# are identical and `check` passes.
#
# Usage:
#     assert_migration_verify.sh snapshot <baseline_file> <test_file>...
#     assert_migration_verify.sh check    <baseline_file> <test_file>...
#
#   snapshot  Run each <test_file> standalone and record its signature to
#             <baseline_file> (one `relpath|PASS|FAIL|TOTAL|EXIT` line per file).
#   check     Re-run each <test_file> and diff against <baseline_file>. Prints a
#             `CHANGED: …` line for every divergence and exits non-zero if any.
#
# Files are run INDIVIDUALLY (never batched) to avoid the ~6 known batch
# cross-contamination failures noted in t920 — standalone runs give an
# apples-to-apples comparison.
#
# Signal model (see t923_1 plan FINDING 2): test files emit wildly varying
# summary lines (only ~49/168 use the canonical "Results: N passed, N failed,
# N total"). So the PRIMARY, authoritative signal is the count of `^FAIL:`
# lines plus the process exit status — both of which are uniform across the
# suite. PASS/TOTAL are parsed from a summary line when one is recognisable and
# recorded for human context only; `check` does NOT fail on a PASS/TOTAL
# change, only on a FAIL-count or exit-status change.
#
# BSD-safe: no GNU-only grep/sed, no mapfile/readarray, mktemp template form,
# `grep -c` guarded against set -e abort on zero matches.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

usage() {
    echo "usage: $(basename "$0") snapshot|check <baseline_file> <test_file>..." >&2
    exit 2
}

# Run one test file standalone; echo "PASS|FAIL|TOTAL|EXIT" for it.
# FAIL = count of '^FAIL:' lines (authoritative). EXIT = process exit status.
# PASS/TOTAL parsed best-effort from a summary line; '-' when unavailable.
run_one() {
    local file="$1" out exit_code fail pass total
    set +e
    out="$(cd "$PROJECT_DIR" && bash "$file" 2>&1)"
    exit_code=$?
    set -e

    # Authoritative: count FAIL: report lines. `grep -c` exits 1 on zero
    # matches, which would abort under set -e — guard with `|| true`.
    fail="$(printf '%s\n' "$out" | grep -c '^FAIL:' || true)"
    fail="$(printf '%s' "$fail" | tr -d '[:space:]')"   # strip BSD wc/grep padding

    # Best-effort PASS/TOTAL from a recognisable summary line. Multiple formats
    # exist; try the common "<N> passed" / "<N> total" shapes. Never fatal.
    pass="$(printf '%s\n' "$out" | grep -oiE '[0-9]+ passed' | head -1 | grep -oE '[0-9]+' || true)"
    total="$(printf '%s\n' "$out" | grep -oiE '[0-9]+ total' | head -1 | grep -oE '[0-9]+' || true)"
    [[ -z "$pass" ]] && pass="-"
    [[ -z "$total" ]] && total="-"

    echo "${pass}|${fail}|${total}|${exit_code}"
}

# Resolve a test-file argument to a path relative to PROJECT_DIR for stable
# baseline keys (so snapshot/check match regardless of how the arg was passed).
relpath() {
    local p="$1"
    case "$p" in
        "$PROJECT_DIR"/*) printf '%s' "${p#"$PROJECT_DIR"/}" ;;
        /*) printf '%s' "$p" ;;
        *) printf '%s' "$p" ;;
    esac
}

cmd_snapshot() {
    local baseline="$1"; shift
    : > "$baseline"
    local file rel sig
    for file in "$@"; do
        rel="$(relpath "$file")"
        sig="$(run_one "$file")"
        echo "${rel}|${sig}" >> "$baseline"
        echo "snapshot: ${rel} -> ${sig}"
    done
    echo "Wrote baseline for $# file(s) to ${baseline}"
}

cmd_check() {
    local baseline="$1"; shift
    [[ -f "$baseline" ]] || { echo "baseline not found: $baseline" >&2; exit 2; }

    local changed=0 file rel now before
    for file in "$@"; do
        rel="$(relpath "$file")"
        # Look up the baseline line for this file (fixed-string, anchored field).
        before="$(grep -F -- "${rel}|" "$baseline" | head -1 || true)"
        if [[ -z "$before" ]]; then
            echo "CHANGED: ${rel} (no baseline entry — was it in the snapshot?)"
            changed=1
            continue
        fi
        before="${before#"${rel}|"}"          # strip "relpath|" prefix
        now="$(run_one "$file")"

        # Compare the authoritative fields: FAIL count (field 2) and EXIT (field 4).
        local b_fail b_exit n_fail n_exit
        b_fail="$(printf '%s' "$before" | cut -d'|' -f2)"
        b_exit="$(printf '%s' "$before" | cut -d'|' -f4)"
        n_fail="$(printf '%s' "$now" | cut -d'|' -f2)"
        n_exit="$(printf '%s' "$now" | cut -d'|' -f4)"

        if [[ "$b_fail" != "$n_fail" || "$b_exit" != "$n_exit" ]]; then
            echo "CHANGED: ${rel} (before FAIL=${b_fail} EXIT=${b_exit} | after FAIL=${n_fail} EXIT=${n_exit})"
            changed=1
        else
            echo "OK: ${rel} (FAIL=${n_fail} EXIT=${n_exit})"
        fi
    done

    if [[ "$changed" -ne 0 ]]; then
        echo "VERIFY FAILED: at least one file's FAIL count or exit status changed."
        exit 1
    fi
    echo "VERIFY OK: all $# file(s) unchanged."
}

main() {
    [[ $# -ge 2 ]] || usage
    local mode="$1"; shift
    case "$mode" in
        snapshot) cmd_snapshot "$@" ;;
        check)    cmd_check "$@" ;;
        *)        usage ;;
    esac
}

main "$@"
