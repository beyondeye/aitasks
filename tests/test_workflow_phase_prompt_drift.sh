#!/usr/bin/env bash
# Drift guards for the advisory workflow-phase tables (t1420).
#
# Two duplications exist by necessity, and each gets a guard that fails LOUDLY
# rather than degrading silently — a phase signal that stops firing looks
# identical to one that legitimately reports UNKNOWN, so nothing else would
# notice:
#
#   (a) WORKFLOW_PROMPTS mirrors question text authored in
#       .claude/skills/task-workflow/ — reword it there and Tier A goes dead.
#   (b) NATIVE_KIND_PHASE + QUESTION_WIDGET_KINDS key on PromptPattern *names*
#       in monitor/prompt_patterns.py — rename one and the row empties.
#
# t1467 inherits guard (b) when it fills in the Codex/OpenCode rows.
#
# Every check asserts a HIT COUNT. A grep that silently matches zero lines reads
# exactly like a clean result, which is how a guard rots into decoration.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR" || exit 1

# shellcheck source=lib/asserts.sh
source "$SCRIPT_DIR/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

PHASE_PY=".aitask-scripts/lib/workflow_phase.py"
PATTERNS_PY=".aitask-scripts/monitor/prompt_patterns.py"
WORKFLOW_DIR=".claude/skills/task-workflow"

check() {
    local name="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1)); echo "  PASS: $name"
    else
        FAIL=$((FAIL + 1)); echo "  FAIL: $name (expected $expected, got $actual)"
    fi
}

echo "=== Guard 0: the files under guard exist ==="
for f in "$PHASE_PY" "$PATTERNS_PY"; do
    check "$f exists" "1" "$([[ -f "$f" ]] && echo 1 || echo 0)"
done
check "$WORKFLOW_DIR exists" "1" "$([[ -d "$WORKFLOW_DIR" ]] && echo 1 || echo 0)"

echo
echo "=== Guard A: every Tier A anchor still exists in the canonical skill text ==="
# The canonical site is the skill markdown; WORKFLOW_PROMPTS only mirrors it.
# Anchors are listed here as the literal prose fragment (not the regex), because
# that is what a rewording would break.
anchors=(
    "Plan saved to"
    "Implementation complete. Please review and test the changes"
    "Proceed with merge of code changes into"
    "has all gates passing and is ready to archive"
)
for anchor in "${anchors[@]}"; do
    hits=$(grep -rF -- "$anchor" "$WORKFLOW_DIR" 2>/dev/null | wc -l)
    TOTAL=$((TOTAL + 1))
    if [[ "$hits" -ge 1 ]]; then
        PASS=$((PASS + 1)); echo "  PASS: canonical text present ($hits hit(s)): $anchor"
    else
        FAIL=$((FAIL + 1))
        echo "  FAIL: '$anchor' no longer appears in $WORKFLOW_DIR —"
        echo "        Tier A is now dead for it. Update WORKFLOW_PROMPTS in $PHASE_PY"
        echo "        to match the new wording, or drop the row."
    fi
done

echo
echo "=== Guard A-neg: the guard detects a reworded anchor ==="
# Positive control for guard A: a fabricated anchor must NOT be found, proving
# the grep discriminates rather than matching everything.
bogus=$(grep -rF -- "Plan preserved to a file somewhere" "$WORKFLOW_DIR" 2>/dev/null | wc -l)
check "fabricated anchor absent" "0" "$bogus"

echo
echo "=== Guard B: every phase-table kind exists as a PromptPattern name ==="
PY="$( . .aitask-scripts/lib/python_resolve.sh 2>/dev/null; resolve_python 2>/dev/null || true)"
if [[ -z "$PY" ]]; then
    echo "  SKIP: no python interpreter resolved"
else
    result="$("$PY" - <<'PYEOF'
import sys
sys.path.insert(0, ".aitask-scripts/lib")
sys.path.insert(0, ".aitask-scripts/monitor")
import workflow_phase as wp
from prompt_patterns import PROMPT_PATTERNS_BY_AGENT

# The COMPILED pattern must match the canonical prose. Checked here rather than
# by grepping the source: a regex may legally be split across source lines (as
# step8_review is), so a literal source grep would report drift that does not
# exist while missing a regex that no longer matches. This asserts the property
# that actually matters.
canonical = [
    "Plan saved to `aiplans/p1_demo.md`. How would you like to proceed?",
    "Implementation complete. Please review and test the changes. When ready, select an option:",
    "Proceed with merge of code changes into the `main` branch (plan header)?",
    "This task has all gates passing and is ready to archive. Would you like to archive it now?",
]
unmatched = [c for c in canonical
             if not any(p.regex.search(c) for p in wp.WORKFLOW_PROMPTS)]
print("UNMATCHED:" + (str(len(unmatched)) if unmatched else "0"))
# Positive control: a reworded question must NOT match, or the check is vacuous.
bogus_matches = [p.name for p in wp.WORKFLOW_PROMPTS
                 if p.regex.search("Blueprint preserved somewhere. Continue?")]
print("BOGUS:" + (",".join(bogus_matches) if bogus_matches else "-"))

missing = []
for agent, kinds in wp.QUESTION_WIDGET_KINDS.items():
    known = {p.name for p in PROMPT_PATTERNS_BY_AGENT.get(agent, [])}
    missing += [f"{agent}:{k}" for k in kinds if k not in known]
for agent, row in wp.NATIVE_KIND_PHASE.items():
    known = {p.name for k, v in PROMPT_PATTERNS_BY_AGENT.items() if k == agent
             for p in v}
    missing += [f"{agent}:{k}" for k in row if k not in known]
print("MISSING:" + (",".join(missing) if missing else "-"))

# A generic confirmation must never carry a phase — absence is the safety.
generic = ["claude_proceed", "claude_help_bar", "codex_yes_proceed"]
leaked = [g for agent, row in wp.NATIVE_KIND_PHASE.items() for g in generic if g in row]
print("LEAKED:" + (",".join(leaked) if leaked else "-"))

# Guard against the tables silently emptying: claude must still be wired.
print("CLAUDE_WIRED:" + ("1" if wp.live_tiers_available("claude") else "0"))
PYEOF
)"
    check "compiled patterns match the canonical questions" "UNMATCHED:0" \
        "$(echo "$result" | grep '^UNMATCHED:')"
    check "patterns reject a reworded question" "BOGUS:-" \
        "$(echo "$result" | grep '^BOGUS:')"
    check "all phase-table kinds are real pattern names" "MISSING:-" \
        "$(echo "$result" | grep '^MISSING:')"
    check "no generic confirmation carries a phase" "LEAKED:-" \
        "$(echo "$result" | grep '^LEAKED:')"
    check "claude live tiers still wired" "CLAUDE_WIRED:1" \
        "$(echo "$result" | grep '^CLAUDE_WIRED:')"
fi

echo
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] && echo "All tests PASSED" || echo "SOME TESTS FAILED"
exit $(( FAIL > 0 ? 1 : 0 ))
