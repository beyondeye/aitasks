#!/usr/bin/env bash
# test_model_stats_parity.sh - the Python counter ports in
# lib/model_stats_store.py (bump_usage / record_verified) reproduce the former
# jq renderers of aitask_usage_update.sh / aitask_verified_update.sh exactly.
#
# t1912_4 deleted the jq renderers, so their results are frozen in
# tests/golden/model_stats_parity/steps.tsv (captured from the live jq writers
# immediately before the deletion; the file's header names the capture). Each
# row is one writer step: the port is fed the row's PRE-state and must produce
# the row's POST-state bucket (jq -S -c) and printed value.
#
# Completeness is checked against the explicit case manifest below — the golden
# must hold exactly these labels, each once — so a truncated, padded or
# hand-trimmed golden fails here rather than silently testing less.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

PASS=0
FAIL=0
TOTAL=0

. "$PROJECT_DIR/tests/lib/asserts.sh"

set +e

PY="$(command -v python3)"
# PARITY_GOLDEN overrides the golden (negative controls only).
GOLDEN="${PARITY_GOLDEN:-$PROJECT_DIR/tests/golden/model_stats_parity/steps.tsv}"

# The cases the capture ran: usage 8 dates + 2 seeded; verified 8 dates +
# 3 legacy flat entries + 1 half-way rounding case.
MANIFEST=(
    "usage pick 2026-03-11" "usage pick 2026-03-12" "usage pick 2026-03-17"
    "usage pick 2026-04-02" "usage pick 2026-07-01" "usage pick 2026-12-31"
    "usage pick 2027-01-01" "usage pick 2027-01-04"
    "usage explain seeded" "usage explain next month"
    "verified pick 2026-03-11" "verified pick 2026-03-12" "verified pick 2026-03-17"
    "verified pick 2026-04-02" "verified pick 2026-07-01" "verified pick 2026-12-31"
    "verified pick 2027-01-01" "verified pick 2027-01-04"
    "verified explain flat" "verified explain after migration"
    "verified qa flat without score_sum" "verified wrap 20/8"
)

echo "=== model_stats_store parity against the frozen jq writer golden ==="

assert_eq "manifest lists the 22 captured cases" "22" "${#MANIFEST[@]}"
assert_eq "golden labels == manifest (same set, each once)" \
    "$(printf '%s\n' "${MANIFEST[@]}" | sort)" \
    "$(grep -v '^#' "$GOLDEN" | cut -f1 | sort)"

# One Python pass over every row. Fields are split in Python, not with a bash
# `read`: IFS=TAB is whitespace to bash, so the empty score column of a usage
# row would collapse and shift every later field. Each output line is
# label, want value, got value, want bucket, got bucket, joined by \x1f.
port_out="$("$PY" - "$PROJECT_DIR/.aitask-scripts/lib" "$GOLDEN" <<'PY'
import json, sys
from datetime import date
sys.path.insert(0, sys.argv[1])
import model_stats_store as mss
for line in open(sys.argv[2], encoding="utf-8"):
    if line.startswith("#") or not line.strip():
        continue
    label, key, skill, day, score, pre, want_value, want_bucket = \
        line.rstrip("\n").split("\t")
    blob = {"schema": 1, "models": {"opus4_6": json.loads(pre)}}
    if key == "usagestats":
        out, value = mss.bump_usage(blob, "opus4_6", skill, date.fromisoformat(day))
    else:
        out, value = mss.record_verified(blob, "opus4_6", skill, int(score),
                                         date.fromisoformat(day))
    bucket = json.dumps(out["models"]["opus4_6"][key][skill], sort_keys=True,
                        separators=(",", ":"))
    print("\x1f".join([label, want_value, str(value), want_bucket, bucket]))
PY
)"
assert_eq "port ran over every golden row" "22" "$(printf '%s\n' "$port_out" | grep -c .)"

while IFS=$'\x1f' read -r label want_value got_value want_bucket got_bucket; do
    assert_eq "$label: printed value" "$want_value" "$got_value"
    assert_eq "$label: bucket" "$want_bucket" "$got_bucket"
done <<<"$port_out"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
