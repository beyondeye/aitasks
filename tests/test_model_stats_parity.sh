#!/usr/bin/env bash
# test_model_stats_parity.sh - the Python counter ports in
# lib/model_stats_store.py (bump_usage / record_verified) reproduce the jq
# renderers of aitask_usage_update.sh / aitask_verified_update.sh exactly
# (t1912_1). The real writers run on a local-only scratch repo with --date;
# after every step the Python port is fed the writer's PRE-state and must
# produce the writer's POST-state bucket (jq -S) and its printed value.
# t1912_4 deletes the jq renderers, so this is the proof they were ported.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0

. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/metadata_update_fixture.sh"

set +e

PY="$(command -v python3)"
MODELS=aitasks/metadata/models_claudecode.json

# port_step <stats_key> <skill> <date> [score_100] < pre_stats_json
# Prints "<value>\t<jq -S -c bucket>" from the Python port.
port_step() {
    local key="$1" skill="$2" day="$3" score="${4:-}"
    "$PY" -c '
import json, sys
from datetime import date
sys.path.insert(0, sys.argv[1])
import model_stats_store as mss
key, skill, day, score = sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
pre = json.load(sys.stdin)
blob = {"schema": 1, "models": {"opus4_6": pre}}
if key == "usagestats":
    out, value = mss.bump_usage(blob, "opus4_6", skill, date.fromisoformat(day))
else:
    out, value = mss.record_verified(blob, "opus4_6", skill, int(score), date.fromisoformat(day))
print(f"{value}\t" + json.dumps(out["models"]["opus4_6"][key][skill], sort_keys=True, separators=(",", ":")))
' "$PROJECT_DIR/.aitask-scripts/lib" "$key" "$skill" "$day" "$score"
}

pre_stats() {  # the row's stats keys only, as the port's model entry
    jq -c '.models[0] | with_entries(select(.key == "usagestats" or .key == "verifiedstats"))' \
        "$1/$MODELS"
}

writer_bucket() {
    jq -S -c --arg k "$2" --arg s "$3" '.models[0][$k][$s]' "$1/$MODELS"
}

# check <label> <repo> <script> <stats_key> <skill> <date> [raw_score]
check() {
    local label="$1" repo="$2" script="$3" key="$4" skill="$5" day="$6" raw="${7:-}"
    local pre out value port_out port_value port_bucket args=()
    pre="$(pre_stats "$repo")"
    args=(--agent-string claudecode/opus4_6 --skill "$skill" --date "$day" --silent)
    [[ -n "$raw" ]] && args+=(--score "$raw")
    out="$(cd "$repo" && "./.aitask-scripts/$script" "${args[@]}" 2>/dev/null)"
    value="${out##*:}"
    port_out="$(port_step "$key" "$skill" "$day" "${raw:+$((raw * 20))}" <<<"$pre")"
    port_value="${port_out%%$'\t'*}"
    port_bucket="${port_out#*$'\t'}"
    assert_eq "$label: writer ran" "UPDATED:claudecode/opus4_6:$skill:$value" "$out"
    assert_eq "$label: bucket" "$(writer_bucket "$repo" "$key" "$skill")" "$port_bucket"
    assert_eq "$label: printed value" "$value" "$port_value"
}

seed() {  # seed <repo> <jq filter>
    local tmp
    tmp="$(mktemp)"
    jq "$2" "$1/$MODELS" > "$tmp" && mv "$tmp" "$1/$MODELS"
    (cd "$1" && git add -A && git commit -q -m seed)
}

DATES=(2026-03-11 2026-03-12 2026-03-17 2026-04-02 2026-07-01 2026-12-31 2027-01-01 2027-01-04)
SCORES=(5 4 3 5 1 2 4 3)

echo "=== model_stats_store jq parity ==="

echo "--- usage: fresh skill across week / month / gap / year boundaries ---"
U="$(setup_local_metadata_repo aitask_usage_update.sh)"
for d in "${DATES[@]}"; do
    check "usage pick $d" "$U" aitask_usage_update.sh usagestats pick "$d"
done

echo "--- usage: seeded entry with null prev_month and missing week ---"
seed "$U" '.models[0].usagestats.explain = {"all_time": {"runs": 9}, "prev_month": null, "month": {"period": "2027-01", "runs": 2}}'
check "usage explain seeded" "$U" aitask_usage_update.sh usagestats explain 2027-01-05
check "usage explain next month" "$U" aitask_usage_update.sh usagestats explain 2027-02-01
rm -rf "$U"

echo "--- verified: fresh skill with scores, across the same boundaries ---"
V="$(setup_local_metadata_repo aitask_verified_update.sh)"
for i in "${!DATES[@]}"; do
    check "verified pick ${DATES[$i]}" "$V" aitask_verified_update.sh verifiedstats pick "${DATES[$i]}" "${SCORES[$i]}"
done

echo "--- verified: legacy flat entries (with and without score_sum) ---"
seed "$V" '.models[0].verifiedstats.explain = {"runs": 3, "score_sum": 240}
           | .models[0].verifiedstats.qa = {"runs": 2}'
check "verified explain flat" "$V" aitask_verified_update.sh verifiedstats explain 2026-11-12 5
check "verified explain after migration" "$V" aitask_verified_update.sh verifiedstats explain 2026-11-13 2
check "verified qa flat without score_sum" "$V" aitask_verified_update.sh verifiedstats qa 2026-11-12 4

echo "--- verified: a .5 average (half away from zero) ---"
seed "$V" '.models[0].verifiedstats.wrap = {"all_time": {"runs": 7, "score_sum": 0},
           "prev_month": {"period": "", "runs": 0, "score_sum": 0},
           "month": {"period": "2026-11", "runs": 7, "score_sum": 0},
           "week": {"period": "2026-W46", "runs": 7, "score_sum": 0}}'
check "verified wrap 20/8" "$V" aitask_verified_update.sh verifiedstats wrap 2026-11-12 1
assert_eq "the .5 case really is 2.5 -> 3" "3" "$(jq -r '.models[0].verified.wrap' "$V/$MODELS")"
rm -rf "$V"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
