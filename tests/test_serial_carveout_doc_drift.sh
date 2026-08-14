#!/usr/bin/env bash
set -euo pipefail

# Serial carve-out doc drift guard (t1510).
#
# The Python runner splits the suite into a parallel pool and a SERIAL CARVE-OUT
# of modules that must not run inside the worker pool (they boot a real TUI in a
# tmux pane under a hard wall-clock boot budget). That list lives in exactly one
# executable place -- `SERIAL_CARVE_OUT` in tests/run_all_python_tests.sh, the
# same array `is_carved()` matches against -- and is DOCUMENTED in CLAUDE.md.
#
# The two drifted once already: the list grew from one module to three when the
# `*_startup_focus_live.py` modules were added and CLAUDE.md was never updated.
# That is not cosmetic -- carve-out membership decides whether a live tmux test
# runs against a loaded box, which is exactly the variable t1500's flake turned
# on -- so this guard asserts the two agree.
#
# BOTH SIDES ARE DERIVED FROM LIVE SOURCE. Nothing here hardcodes the expected
# module list: a hardcoded list would just become a third manifest to drift.
#
# TWO REPRESENTATIONS, ONE CANONICAL FORM. `SERIAL_CARVE_OUT` holds bare
# basenames (is_carved() compares "${1##*/}"), while the doc block shows
# reader-openable `tests/`-prefixed paths. `canon()` maps both onto
# `tests/<basename>` so a literal comparison cannot report drift on agreeing
# manifests. Membership and path-form are checked SEPARATELY -- they are
# different defects and deserve different failure messages.
#
# SCOPING. The doc side reads ONLY the `serial-carve-out:begin`/`:end` marker
# block, never the whole `### Testing` section: an unrelated Python-test example
# mentioned in that section must not be able to trip the runner manifest guard.

PASS=0
FAIL=0
# shellcheck disable=SC2034  # TOTAL is mutated by the sourced asserts.sh helpers.
TOTAL=0

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

RUNNER="$PROJECT_DIR/tests/run_all_python_tests.sh"
REAL_DOC="$PROJECT_DIR/CLAUDE.md"

TESTROOT="$(mktemp -d)"
trap 'rm -rf "$TESTROOT"' EXIT

# The comparison helpers return non-zero BY DESIGN (that is the guard's verdict)
# and the negative controls invoke them expecting failure -- errexit would abort
# the run on the first intentional drift.
set +eu

# ---------------------------------------------------------------------------
# Derivation
# ---------------------------------------------------------------------------

# canon <name> — the single canonical comparison form, applied to BOTH sides.
# Strips an optional leading `tests/`, then re-prefixes it. Idempotent.
canon() {
    printf 'tests/%s\n' "${1##*/}"
}

# join_names <newline-list> — one-line rendering for diagnostics.
join_names() {
    printf '%s' "$1" | tr '\n' ' ' | sed 's/ *$//'
}

canon_all() {
    local n
    while IFS= read -r n; do
        [[ -n "$n" ]] && canon "$n"
    done | LC_ALL=C sort -u
}

# source_set — the SERIAL_CARVE_OUT array literal, canonicalized. Bounded awk
# over the single declaration; no sourcing (the runner has no --source-only
# guard and would execute the suite).
source_set() {
    awk '
        /^SERIAL_CARVE_OUT=\(/ { inside = 1 }
        inside {
            line = $0
            sub(/^SERIAL_CARVE_OUT=\(/, "", line)
            sub(/\).*$/, "", line)
            n = split(line, parts, /[[:space:]]+/)
            for (i = 1; i <= n; i++)
                if (parts[i] ~ /\.py$/) print parts[i]
            if ($0 ~ /\)/) exit
        }
    ' "$RUNNER" | canon_all
}

# doc_set <doc> — backticked test module tokens from BETWEEN the markers only,
# canonicalized. The extraction accepts the unprefixed form deliberately, so a
# bare-basename entry is visible to doc_form_violations() below instead of
# silently vanishing into a membership mismatch.
doc_block() {
    awk '
        /serial-carve-out:begin/ { inside = 1; next }
        /serial-carve-out:end/   { inside = 0 }
        inside
    ' "$1"
}

doc_set() {
    # shellcheck disable=SC2016  # backticks here are literal markdown, not substitution
    doc_block "$1" \
        | grep -oE '`(tests/)?test_[A-Za-z0-9_]+\.py`' \
        | tr -d '`' \
        | canon_all
}

# doc_form_violations <doc> — entries not written in the `tests/<name>.py` form.
doc_form_violations() {
    # shellcheck disable=SC2016  # backticks here are literal markdown, not substitution
    doc_block "$1" \
        | grep -oE '`(tests/)?test_[A-Za-z0-9_]+\.py`' \
        | tr -d '`' \
        | grep -v '^tests/'
}

has_markers() {
    grep -q 'serial-carve-out:begin' "$1" && grep -q 'serial-carve-out:end' "$1"
}

# ---------------------------------------------------------------------------
# The guard itself — a function over a doc path, so the fixtures exercise the
# real code path rather than a replica.
# ---------------------------------------------------------------------------

# check_doc <doc> — prints OK, or one diagnostic line per defect. Non-zero on
# any defect.
check_doc() {
    local doc="$1" rc=0 src docs missing extra bad

    if ! has_markers "$doc"; then
        echo "MARKERS_MISSING: $doc has no serial-carve-out:begin/:end block"
        return 1
    fi

    src="$(source_set)"
    docs="$(doc_set "$doc")"

    # Non-empty on both sides: two empty sets would compare equal and pass
    # vacuously, turning a broken parser into a green guard.
    if [[ -z "$src" ]]; then
        echo "SOURCE_EMPTY: could not parse SERIAL_CARVE_OUT from $RUNNER"
        return 1
    fi
    if [[ -z "$docs" ]]; then
        echo "DOC_EMPTY: the marker block in $doc lists no test modules"
        return 1
    fi

    missing="$(comm -23 <(printf '%s\n' "$src") <(printf '%s\n' "$docs"))"
    extra="$(comm -13 <(printf '%s\n' "$src") <(printf '%s\n' "$docs"))"
    if [[ -n "$missing" ]]; then
        echo "DOC_MISSING: carved but undocumented: $(join_names "$missing")"
        rc=1
    fi
    if [[ -n "$extra" ]]; then
        echo "DOC_EXTRA: documented but not carved: $(join_names "$extra")"
        rc=1
    fi

    bad="$(doc_form_violations "$doc")"
    if [[ -n "$bad" ]]; then
        echo "DOC_FORM: entries must be written as tests/<name>.py: $(join_names "$bad")"
        rc=1
    fi

    [[ $rc -eq 0 ]] && echo "OK"
    return $rc
}

# shellcheck disable=SC2016  # the sed programs below carry literal markdown backticks
# fixture <name> <sed-program> — a copy of the real doc with one mutation.
fixture() {
    local path="$TESTROOT/$1.md"
    sed "$2" "$REAL_DOC" > "$path"
    printf '%s' "$path"
}

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

echo "=== Serial carve-out doc drift guard ==="

# --- Derivation sanity: the parse finds something, in canonical form ---
src="$(source_set)"
assert_contains "T0a: source set is non-empty" "tests/test_" "$src"
assert_eq "T0a: source set has 3 entries" "3" "$(printf '%s\n' "$src" | wc -l | tr -d ' ')"
assert_contains "T0b: source entries are canonicalized to tests/<name>.py" \
    "tests/test_board_header_row_live.py" "$src"

doc="$(doc_set "$REAL_DOC")"
assert_eq "T0c: doc set has 3 entries" "3" "$(printf '%s\n' "$doc" | wc -l | tr -d ' ')"

# --- POSITIVE CONTROL: the real doc and the real runner agree ---
# This is what proves canon() is neither over- nor under-normalizing on live
# inputs; without it an over-strict canon() would surface only as a red suite.
out="$(check_doc "$REAL_DOC" 2>&1)"
rc=$?
assert_eq "T1: real CLAUDE.md agrees with SERIAL_CARVE_OUT" "OK" "$out"
assert_eq "T1: ...and exits zero" "0" "$rc"

# --- NEGATIVE CONTROL 1: an entry removed from the doc block ---
f="$(fixture drift_missing '/tests\/test_codebrowser_startup_focus_live\.py/d')"
out="$(check_doc "$f" 2>&1)"
rc=$?
assert_exit_nonzero_rc "T2: dropped doc entry is detected" "$rc"
assert_contains "T2: ...reported as DOC_MISSING" "DOC_MISSING" "$out"
assert_contains "T2: ...naming the module" \
    "tests/test_codebrowser_startup_focus_live.py" "$out"

# --- NEGATIVE CONTROL 2: an extra entry added to the doc block ---
# shellcheck disable=SC2016  # literal markdown backticks in the sed program
f="$(fixture drift_extra \
    's|^- `tests/test_board_header_row_live\.py`$|- `tests/test_board_header_row_live.py`\n- `tests/test_not_actually_carved.py`|')"
out="$(check_doc "$f" 2>&1)"
rc=$?
assert_exit_nonzero_rc "T3: extra doc entry is detected" "$rc"
assert_contains "T3: ...reported as DOC_EXTRA" "DOC_EXTRA" "$out"
assert_contains "T3: ...naming the module" "tests/test_not_actually_carved.py" "$out"

# --- NEGATIVE CONTROL 3: the marker block deleted ---
# Must be a hard error, NOT a vacuous pass against an empty doc set.
f="$(fixture drift_no_markers '/serial-carve-out:/d')"
out="$(check_doc "$f" 2>&1)"
rc=$?
assert_exit_nonzero_rc "T4: deleted markers are detected" "$rc"
assert_contains "T4: ...reported as MARKERS_MISSING" "MARKERS_MISSING" "$out"

# --- NEGATIVE CONTROL 4: the normalization's own control ---
# A bare-basename entry must trip the FORM check while MEMBERSHIP still compares
# equal. That is what pins canon() to both sides: if it ran on only one, this
# fixture would report DOC_MISSING/DOC_EXTRA instead, and controls 1-2 above
# would be proving path-shape artifacts rather than real membership drift.
# shellcheck disable=SC2016  # literal markdown backticks in the sed program
f="$(fixture drift_form \
    's|^- `tests/test_board_startup_focus_live\.py`$|- `test_board_startup_focus_live.py`|')"
out="$(check_doc "$f" 2>&1)"
rc=$?
assert_exit_nonzero_rc "T5: bare-basename entry is detected" "$rc"
assert_contains "T5: ...reported as DOC_FORM" "DOC_FORM" "$out"
assert_not_contains "T5: ...and membership still agrees (canon runs on both sides)" \
    "DOC_MISSING" "$out"
assert_not_contains "T5: ...no spurious DOC_EXTRA either" "DOC_EXTRA" "$out"

echo ""
echo "========================================="
echo "Results: $PASS passed, $FAIL failed"
echo "========================================="
[[ $FAIL -eq 0 ]]
