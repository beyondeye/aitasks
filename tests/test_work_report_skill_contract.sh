#!/usr/bin/env bash
# test_work_report_skill_contract.sh — Contract guard for /aitask-work-report (t1162_3).
#
# The work-report skill carries load-bearing prose contracts (fail-closed
# selection validation, opt-in projection, no report file, pinned gatherer
# record schemas). This test greps the canonical SKILL.md for each marker and
# checks the three cross-agent wrapper files point at the canonical path.
# Dropping any marker fails the test.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"

cd "$PROJECT_DIR"

CANONICAL=".claude/skills/aitask-work-report/SKILL.md"

TOTAL=$((TOTAL + 1))
if [[ -f "$CANONICAL" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: canonical skill missing at $CANONICAL"
    echo ""
    echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
    exit 1
fi

skill="$(cat "$CANONICAL")"

# --- Load-bearing markers in the canonical SKILL.md -------------------------

assert_contains "column discovery uses the gatherer --list-columns" \
    "aitask_work_report_gather.sh --list-columns" "$skill"

assert_contains "empty-discovery path (zero reportable columns)" \
    "no reportable columns" "$skill"

assert_contains "discovery run is validated in list mode before the empty check" \
    "Validate the discovery run first" "$skill"

assert_contains "paginated multi-select keeps an accumulator across pages" \
    "accumulator across pages" "$skill"

assert_contains "fallback for agents without native multi-select" \
    "Agents without native multi-select" "$skill"

assert_contains "multi-select fallback collects one comma-separated id list" \
    "comma-separated list of ids" "$skill"

assert_contains "fallback preserves column ids verbatim (no t-prefix stripping)" \
    "NO prefix" "$skill"

assert_contains "fallback strips optional t prefix on task ids only" \
    "the optional \`t\` on task ids ONLY" "$skill"

assert_contains "exclusions are membership-validated before subtraction" \
    "Validate every exclusion BEFORE subtracting" "$skill"

assert_contains "fail-closed hard stop covers ERROR:/NO_TASKS output" \
    'One or more `ERROR:` lines, or `NO_TASKS`' "$skill"

assert_contains "fail-closed hard stop covers non-zero gatherer exit" \
    "Non-zero exit status" "$skill"

assert_contains "malformed-record rule (schema-violating lines hard-stop)" \
    "malformed record" "$skill"

assert_contains "hard stop halts drafting" \
    "STOP — do not draft" "$skill"

assert_contains "membership integrity sentence" \
    "never drafts from a partial or silently-corrected selection" "$skill"

assert_contains "pinned TASK: record schema (field order)" \
    "TASK:<col_id>|<task_id>|<boardidx>|<status>|<priority>|<effort>|<pending_children>|<remaining_items>|<task_file_path>" \
    "$skill"

assert_contains "pinned VELOCITY: record schema (field order)" \
    "VELOCITY:<bucket_id>|<observed_units>|<completed_count>|<avg_per_unit>|<bucket_label>" \
    "$skill"

assert_contains "velocity args are forwarded passthrough" \
    "--velocity-model" "$skill"

assert_contains "projection is opt-in via --project" \
    "--project" "$skill"

assert_contains "insufficient-history fallback (never fabricate a rate)" \
    "insufficient completion history for a projection" "$skill"

assert_contains "horizon judgement restricted (no inferred fits/exceeds)" \
    "without any inferred fits/exceeds" "$skill"

assert_contains "no report file is written" \
    "Do NOT write a report file" "$skill"

assert_contains "satisfaction feedback uses skill_name work-report" \
    '`skill_name` = `"work-report"`' "$skill"

# --- Wrapper files point at the canonical skill ------------------------------

for wrapper in \
    ".agents/skills/aitask-work-report/SKILL.md" \
    ".opencode/skills/aitask-work-report/SKILL.md" \
    ".opencode/commands/aitask-work-report.md"; do
    TOTAL=$((TOTAL + 1))
    if [[ ! -f "$wrapper" ]]; then
        FAIL=$((FAIL + 1))
        echo "FAIL: wrapper missing at $wrapper"
        continue
    fi
    PASS=$((PASS + 1))
    assert_contains "$wrapper points at the canonical skill path" \
        "$CANONICAL" "$(cat "$wrapper")"
done

# --- Summary -----------------------------------------------------------------

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ $FAIL -eq 0 ]] || exit 1
