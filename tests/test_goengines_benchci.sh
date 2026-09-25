#!/usr/bin/env bash
# test_goengines_benchci.sh - goengines/ci/benchci.sh: the seeded-regression
# baseline and the per-benchmark scaled-ratio summary the CI bench job writes
# for t1878's promotion decision (t1852_3).
# Run: bash tests/test_goengines_benchci.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

PASS=0
FAIL=0
TOTAL=0
. "$PROJECT_DIR/tests/lib/asserts.sh"

BENCHCI="$PROJECT_DIR/goengines/ci/benchci.sh"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

cat > "$TMP/baseline.txt" <<'EOF'
# fixture baseline
internal/benchgate.BenchmarkCalibrate 1000000
internal/benchgate.BenchmarkCalibrateSpawn 500000
internal/benchgate.BenchmarkCalibrateHash 30000
pkg.BenchmarkOk 1000
pkg.BenchmarkBoundary 1000
pkg.BenchmarkBudget 2000 budget=500ns
pkg.BenchmarkSpawnReg 400000 cal=spawn
pkg.BenchmarkHash 10000 cal=sha1
pkg.BenchmarkGone 500
EOF

# cpu: the true scale is 250400/1000000 = 0.2504; the gate prints it as 0.250.
# BenchmarkBoundary: 325.2696 / (1000 x 0.2504) = 1.299 exactly, but 1.301 with
# the rounded scale — the two sit on either side of t1878's 1.3 limit.
cat > "$TMP/gate.out" <<'EOF'
BENCH_MODE:full
BENCH_SCALE:cpu|0.250|250400|1000000
BENCH_SCALE:spawn|1.000|500000|500000
BENCH_SCALE_IMPLAUSIBLE:sha1|5.000|150000|30000
ok  	github.com/beyondeye/aitasks/goengines/internal/gitx	1.234s
BENCH_OK:pkg.BenchmarkOk|313|1000
BENCH_OK:pkg.BenchmarkBoundary|325.2696|1000
BENCH_OVER_BUDGET:pkg.BenchmarkBudget|600.96|500ns
BENCH_REGRESSION:pkg.BenchmarkSpawnReg|880000|400000|2.20
BENCH_OK:pkg.BenchmarkHash|10000|10000
BENCH_MISSING:pkg.BenchmarkGone
BENCH_NEW:pkg.BenchmarkFresh|42
EOF

# column <summary> <benchmark> <n>: field n of that benchmark's table row
# (2 name, 3 class, 4 current, 5 baseline, 6 scale, 7 ratio, 8 verdict).
column() {
    printf '%s\n' "$1" | awk -F'|' -v b="$2" -v n="$3" '
        { name = $2; gsub(/ /, "", name) }
        name == b { v = $n; gsub(/ /, "", v); print v }'
}

# --- 1. seed -------------------------------------------------------------------
"$BENCHCI" seed "$TMP/baseline.txt" "$TMP/seeded.txt"
seeded="$(cat "$TMP/seeded.txt")"
assert_contains "seed keeps comments" "# fixture baseline" "$seeded"
assert_contains "seed leaves the cpu calibration" "internal/benchgate.BenchmarkCalibrate 1000000" "$seeded"
assert_contains "seed leaves the spawn calibration" "internal/benchgate.BenchmarkCalibrateSpawn 500000" "$seeded"
assert_contains "seed divides by 2.1" "pkg.BenchmarkOk 476.190476" "$seeded"
assert_contains "seed keeps budget=" "pkg.BenchmarkBudget 952.380952 budget=500ns" "$seeded"
assert_contains "seed keeps cal=" "pkg.BenchmarkSpawnReg 190476.190476 cal=spawn" "$seeded"
assert_eq "seed keeps the line count" "$(wc -l < "$TMP/baseline.txt")" "$(wc -l < "$TMP/seeded.txt")"

# --- 2-7. summary ---------------------------------------------------------------
sum="$("$BENCHCI" summary "$TMP/baseline.txt" "$TMP/gate.out")"
assert_eq "BENCH_OK row: exact scaled ratio" "1.250000" "$(column "$sum" pkg.BenchmarkOk 7)"
assert_eq "BENCH_OK row: scale recomputed from the unrounded fields" "0.250400" "$(column "$sum" pkg.BenchmarkOk 6)"
assert_eq "over-budget-only row: baseline taken from the baseline file" "2000" "$(column "$sum" pkg.BenchmarkBudget 5)"
assert_eq "over-budget-only row: ratio" "1.200000" "$(column "$sum" pkg.BenchmarkBudget 7)"
assert_eq "over-budget-only row: verdict" "over-budget" "$(column "$sum" pkg.BenchmarkBudget 8)"
reg="$(column "$sum" pkg.BenchmarkSpawnReg 7)"
assert_eq "regression row agrees with the gate's printed ratio at 2 dp" "2.20" "$(printf '%.2f' "$reg")"
assert_eq "regression row: class from cal=" "spawn" "$(column "$sum" pkg.BenchmarkSpawnReg 3)"
assert_eq "boundary: true ratio 1.299, not the rounded-scale 1.301" "1.299000" "$(column "$sum" pkg.BenchmarkBoundary 7)"
assert_eq "implausible scale: ratio n/a" "n/a" "$(column "$sum" pkg.BenchmarkHash 7)"
assert_eq "implausible scale: scale n/a" "n/a" "$(column "$sum" pkg.BenchmarkHash 6)"
assert_eq "missing: ratio n/a" "n/a" "$(column "$sum" pkg.BenchmarkGone 7)"
assert_eq "missing: verdict" "missing" "$(column "$sum" pkg.BenchmarkGone 8)"
assert_eq "new: ratio n/a" "n/a" "$(column "$sum" pkg.BenchmarkFresh 7)"
assert_eq "new: verdict" "new" "$(column "$sum" pkg.BenchmarkFresh 8)"
assert_not_contains "calibrations are not tabulated" "| internal/benchgate.BenchmarkCalibrate " "$sum"
assert_contains "scale lines are echoed" "BENCH_SCALE_IMPLAUSIBLE:sha1|5.000|150000|30000" "$sum"

# Negative control for the boundary assertion: a scratch copy that uses the
# rounded field 2 must land on the other side of 1.3.
sed 's/scale\[f\[1\]\] = f\[3\] \/ f\[4\]/scale[f[1]] = f[2]/' "$BENCHCI" > "$TMP/rounded.sh"
assert_eq "control copy was actually patched" "1" "$(grep -c 'scale\[f\[1\]\] = f\[2\]' "$TMP/rounded.sh")"
ctl="$(bash "$TMP/rounded.sh" summary "$TMP/baseline.txt" "$TMP/gate.out")"
assert_eq "control: the rounded scale gives 1.301078" "1.301078" "$(column "$ctl" pkg.BenchmarkBoundary 7)"

# --- unreadable input and usage -------------------------------------------------
rc=0
note="$("$BENCHCI" summary "$TMP/nope.txt" "$TMP/gate.out")" || rc=$?
assert_eq "unreadable input exits 0" "0" "$rc"
assert_contains "unreadable input prints a note" "bench summary unavailable" "$note"
rc=0
"$BENCHCI" frobnicate >/dev/null 2>&1 || rc=$?
assert_eq "unknown subcommand exits 2" "2" "$rc"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]] || exit 1
