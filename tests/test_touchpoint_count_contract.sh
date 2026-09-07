#!/usr/bin/env bash
# test_touchpoint_count_contract.sh - The helper-permission touchpoint set is
# enumerated in five places: the canonical map in
# .aitask-scripts/aitask_audit_wrappers.sh::touchpoint_file(), the two iteration
# loops beside it, a table plus a prose COUNT in
# aidocs/framework/aitasks_extension_points.md, an enumeration in
# aidocs/framework/adding_a_new_codeagent.md §13, and a table in
# .claude/skills/aitask-audit-wrappers/SKILL.md.
#
# The prose count silently went stale once already (t1717): it was written as
# "7-touchpoint" when gemini was live, t812_2 retired gemini's two touchpoints
# and updated the table to five rows, and the sentence kept saying 7 for four
# months. Nothing failed, because nothing checked. This is that check.
#
# Ground truth is the canonical map executing itself -- `aitask_audit_wrappers.sh
# touchpoints` derives the live set by probing touchpoint_file() -- never a
# regex over the script's source text, which would break silently the next time
# that function is reformatted.
#
# Run: bash tests/test_touchpoint_count_contract.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR" || exit 1

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

AUDIT_SH=".aitask-scripts/aitask_audit_wrappers.sh"
EXT_POINTS="aidocs/framework/aitasks_extension_points.md"
NEW_AGENT="aidocs/framework/adding_a_new_codeagent.md"
AUDIT_SKILL=".claude/skills/aitask-audit-wrappers/SKILL.md"
CLAUDE_MD="CLAUDE.md"

# ---------------------------------------------------------------------------
# Probe guard -- run FIRST, and abort rather than continue.
#
# Every assertion below compares a doc surface against the probe's output. If
# the probe returns nothing, each of those comparisons is empty-vs-empty and
# passes while checking nothing. A guard test that can only pass is worse than
# no guard, so an unusable probe is a hard stop, not a soft finding.
# ---------------------------------------------------------------------------

probe_rc=0
probe_out="$("./$AUDIT_SH" touchpoints 2>/dev/null)" || probe_rc=$?

assert_eq "touchpoints subcommand exits 0" "0" "$probe_rc"

probe_lines=0
[[ -n "$probe_out" ]] && probe_lines=$(printf '%s\n' "$probe_out" | grep -c '^TOUCHPOINT:')
if [[ "$probe_rc" -ne 0 || "$probe_lines" -eq 0 ]]; then
    echo "FATAL: touchpoints probe produced no usable output (rc=$probe_rc," \
         "lines=$probe_lines). Every assertion below would compare empty to" \
         "empty and pass vacuously, so this run is aborted instead."
    echo
    echo "PASS: $PASS, FAIL: $((FAIL + 1)), TOTAL: $((TOTAL + 1))"
    exit 1
fi

# Every emitted line must be well-formed and name a file that exists -- a
# TOUCHPOINT: line pointing at a deleted policy file is a broken map, and it
# would otherwise be compared happily against a doc that also still lists it.
malformed=""
for line in $probe_out; do
    if [[ ! "$line" =~ ^TOUCHPOINT:[0-9]+:[^[:space:]]+$ ]]; then
        malformed="$malformed $line"
        continue
    fi
    tp_file="${line#TOUCHPOINT:*:}"
    [[ -f "$tp_file" ]] || malformed="$malformed ${line}(missing-file)"
done
assert_eq "every TOUCHPOINT line is well-formed and names an existing file" \
    "" "$malformed"

# ---------------------------------------------------------------------------
# Derive the live set from the probe.
# ---------------------------------------------------------------------------

LIVE_IDS="$(printf '%s\n' "$probe_out" | sed -n 's/^TOUCHPOINT:\([0-9]*\):.*/\1/p' | tr '\n' ' ')"
LIVE_IDS="${LIVE_IDS% }"
LIVE_FILES="$(printf '%s\n' "$probe_out" | sed -n 's/^TOUCHPOINT:[0-9]*://p' | sort | tr '\n' ' ')"
LIVE_FILES="${LIVE_FILES% }"
LIVE_COUNT="$probe_lines"

# --- Test 1: the live ID set, with its deliberate vacancies ---
#
# Hard-coded on purpose. IDs 2 and 5 are retired gemini slots that must stay
# vacant, and a new agent touchpoint must be a conscious edit here -- see
# adding_a_new_codeagent.md §13, which names this test in its add/retire steps.
assert_eq "live touchpoint IDs (2 and 5 stay vacant)" "1 3 4 6 7" "$LIVE_IDS"

# --- Test 2: the extension-points table lists exactly the live files ---

assert_eq "$EXT_POINTS has exactly one touchpoint table header" \
    "1" "$(grep -c '^| Touchpoint | Entry shape |$' "$EXT_POINTS")"

table_files="$(awk '
    /^\| Touchpoint \| Entry shape \|$/ { in_table = 1; next }
    in_table && /^\|-/                  { next }
    in_table && !/^\|/                  { in_table = 0 }
    in_table {
        line = $0
        sub(/^\| *`/, "", line)
        sub(/` *\|.*$/, "", line)
        print line
    }
' "$EXT_POINTS" | sort | tr '\n' ' ')"
table_files="${table_files% }"
assert_eq "$EXT_POINTS table lists exactly the live touchpoint files" \
    "$LIVE_FILES" "$table_files"

# --- Test 3: the prose count matches the live count ---

prose_count="$(grep -oE '[0-9]+-touchpoint checklist' "$EXT_POINTS" | head -n1 | cut -d- -f1)"
assert_eq "$EXT_POINTS prose count matches the live touchpoint count" \
    "$LIVE_COUNT" "$prose_count"

# --- Test 4: §13's `Current touchpoints:` block matches ---

s13_pairs="$(awk '
    /^Current touchpoints:$/ { seen = 1; next }
    seen && /^```$/          { fence++; if (fence == 2) exit; next }
    seen && fence == 1 && /^[0-9]+ = / { print $1 " " $3 }
' "$NEW_AGENT" | sort | tr '\n' ' ')"
s13_pairs="${s13_pairs% }"

live_pairs="$(printf '%s\n' "$probe_out" | sed -n 's/^TOUCHPOINT:\([0-9]*\):\(.*\)/\1 \2/p' | sort | tr '\n' ' ')"
live_pairs="${live_pairs% }"

assert_eq "$NEW_AGENT §13 lists exactly the live id/file pairs" \
    "$live_pairs" "$s13_pairs"

# --- Test 5: the audit-wrappers skill table matches ---

# SC2016: the sed script's \1 \2 backrefs and backticks are literal - single quotes are required.
# shellcheck disable=SC2016
skill_pairs="$(sed -n 's/^| \([0-9]\+\) | `\([^`]*\)` |.*/\1 \2/p' "$AUDIT_SKILL" | sort | tr '\n' ' ')"
skill_pairs="${skill_pairs% }"
assert_eq "$AUDIT_SKILL table lists exactly the live id/file pairs" \
    "$live_pairs" "$skill_pairs"

# --- Test 6: the iteration loops cover exactly the live IDs ---
#
# A touchpoint_file() entry the audit/apply loops skip is a touchpoint nobody
# ever checks -- the map would be right and the tool silently blind to it.
loop_count=0
while IFS= read -r loop_ids; do
    loop_count=$((loop_count + 1))
    assert_eq "iteration loop #$loop_count covers exactly the live IDs" \
        "$LIVE_IDS" "$loop_ids"
done < <(grep -oE 'for touchpoint in [0-9 ]+; do' "$AUDIT_SH" \
           | sed -e 's/^for touchpoint in //' -e 's/; do$//')

assert_eq "both iteration loops were found in $AUDIT_SH" "2" "$loop_count"

# --- Test 7: the helper-script section pointer names its real owner ---
#
# The "Adding a new helper script" section moved out of CLAUDE.md into
# aidocs/framework/aitasks_extension_points.md. Both the helper's usage() text
# and the audit-wrappers skill cite it by name, and the skill's citation stayed
# pointed at CLAUDE.md for months (t1726). These assertions pin the ownership
# and both citations of it.

# Every check below compares counts rather than passing a whole file as a
# haystack: assert_contains takes (desc, NEEDLE, HAYSTACK), and a multi-line
# needle makes `grep -F` match on any single line -- including a blank one --
# so a file-as-needle assertion passes vacuously. grep -c also exits 1 on zero
# matches, and this file runs under `set -u` without `-e`, so each substitution
# ends in `|| true` to yield "0" rather than the empty string.

assert_eq "$EXT_POINTS owns the 'Adding a new helper script' section" "1" \
    "$(grep -c '^## Adding a new helper script$' "$EXT_POINTS" || true)"

assert_eq "$CLAUDE_MD no longer carries that section as a heading" "0" \
    "$(grep '^#' "$CLAUDE_MD" | grep -ci 'adding a new helper script' || true)"

skill_cites=0
grep -q 'aitasks_extension_points\.md' "$AUDIT_SKILL" && skill_cites=1
assert_eq "$AUDIT_SKILL cites $EXT_POINTS for the touchpoints" "1" "$skill_cites"

helper_cites=0
grep -q 'aitasks_extension_points\.md' "$AUDIT_SH" && helper_cites=1
assert_eq "$AUDIT_SH usage() cites $EXT_POINTS for the touchpoints" "1" "$helper_cites"

# Prose only -- the `[^|]*` keeps the skill's markdown tables out of scope.
assert_eq "$AUDIT_SKILL attributes no helper-script prose to CLAUDE.md" "0" \
    "$(grep -ci 'CLAUDE\.md[^|]*helper' "$AUDIT_SKILL" || true)"

# --- Summary ---

echo
echo "PASS: $PASS, FAIL: $FAIL, TOTAL: $TOTAL"
[[ "$FAIL" -eq 0 ]]
