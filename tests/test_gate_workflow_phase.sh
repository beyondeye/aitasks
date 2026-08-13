#!/usr/bin/env bash
# `aitask_gate.sh workflow-phase` — the shell surface of the advisory phase
# signal (t1420). Follows test_gate_reentry.sh's conventions: fixtures under a
# temp TASK_DIR, every bash verb asserted against its python twin on the SAME
# fixture, and the degrade path pinned by a static source grep.
#
# The properties that matter here are not "the phase is right" (that is
# tests/test_workflow_phase.py's job) but that the SHELL surface is total:
# it resolves task ids the way every other verb does, it never exits nonzero,
# and its default suppresses the screen tiers so a caller that cannot observe
# the pane never overrides the ledger.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR" || exit 1

# shellcheck source=lib/asserts.sh
source "$SCRIPT_DIR/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

GATE="$PROJECT_DIR/.aitask-scripts/aitask_gate.sh"
PHASE_PY="$PROJECT_DIR/.aitask-scripts/lib/workflow_phase.py"
PY="$( . "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" 2>/dev/null; \
       resolve_python 2>/dev/null || true)"

check() {
    local name="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1)); echo "  PASS: $name"
    else
        FAIL=$((FAIL + 1)); echo "  FAIL: $name (expected '$expected', got '$actual')"
    fi
}

field() { echo "$1" | tr '|' '\n' | grep "^$2:" | cut -d: -f2-; }

make_task() {
    # make_task <num> [<gate-run-lines>]
    local num="$1" runs="${2:-}"
    mkdir -p "$TASK_DIR"
    {
        printf -- '---\npriority: medium\neffort: low\nstatus: Implementing\n'
        printf 'issue_type: feature\n---\n\n# Demo t%s\n\n' "$num"
        [[ -n "$runs" ]] && printf '## Gate Runs\n\n%s\n' "$runs"
    } > "$TASK_DIR/t${num}_demo.md"
}

make_child() {
    local parent="$1" child="$2" runs="${3:-}"
    mkdir -p "$TASK_DIR/t${parent}"
    {
        printf -- '---\npriority: medium\neffort: low\nstatus: Implementing\n'
        printf 'issue_type: feature\n---\n\n# Demo child\n\n'
        [[ -n "$runs" ]] && printf '## Gate Runs\n\n%s\n' "$runs"
    } > "$TASK_DIR/t${parent}/t${parent}_${child}_demo.md"
}

PLAN_RUN='> **✅ gate:plan_approved** run=2026-01-01T00:00:00Z status=pass attempt=1 type=human'
REVIEW_RUN='> **✅ gate:review_approved** run=2026-01-01T00:01:00Z status=pass attempt=1 type=human'

tmp="$(mktemp -d)"
CLEANUP_DIRS+=("$tmp")
export TASK_DIR="$tmp/aitasks"

echo "=== Ledger states through the shell verb ==="
make_task 500
make_task 501 "$PLAN_RUN"
make_task 502 "$PLAN_RUN
$REVIEW_RUN"

# No ledger ⇒ UNKNOWN, NOT PLAN. This is the distinction the whole signal turns
# on, asserted at the outermost surface a caller actually uses.
check "empty ledger -> UNKNOWN" "UNKNOWN" "$(field "$("$GATE" workflow-phase 500)" PHASE)"
check "plan_approved -> IMPLEMENT" "IMPLEMENT" "$(field "$("$GATE" workflow-phase 501)" PHASE)"
check "review_approved -> POSTIMPL" "POSTIMPL" "$(field "$("$GATE" workflow-phase 502)" PHASE)"

echo
echo "=== Child task ids resolve like every other verb ==="
make_child 503 1 "$PLAN_RUN
$REVIEW_RUN"
check "child id -> POSTIMPL" "POSTIMPL" "$(field "$("$GATE" workflow-phase 503_1)" PHASE)"

echo
echo "=== The verb is total: never a nonzero exit ==="
"$GATE" workflow-phase 500 >/dev/null 2>&1
check "known task exits 0" "0" "$?"
make_task 504 '> **✅ gate:plan_approved** utterly malformed nonsense here'
"$GATE" workflow-phase 504 >/dev/null 2>&1
check "malformed ledger exits 0" "0" "$?"
out="$("$GATE" workflow-phase 504 2>/dev/null)"
check "malformed ledger still emits a signal" "1" \
    "$(case "$out" in PHASE:*) echo 1 ;; *) echo 0 ;; esac)"

echo
echo "=== Default suppresses the screen tiers ==="
# A caller that cannot observe the pane must not override the ledger, however
# convincing the screen text looks.
screen="$tmp/screen.txt"
printf 'Plan saved to `aiplans/p1.md`. How would you like to proceed?\n' > "$screen"
check "screen ignored without --awaiting-input" "IMPLEMENT" \
    "$(field "$("$GATE" workflow-phase 501 --screen "$screen")" PHASE)"
check "source stays ledger" "ledger" \
    "$(field "$("$GATE" workflow-phase 501 --screen "$screen")" SOURCE)"
check "explicit --awaiting-input no also suppresses" "IMPLEMENT" \
    "$(field "$("$GATE" workflow-phase 501 --screen "$screen" --awaiting-input no)" PHASE)"

echo
echo "=== Per-agent CLI surface (t1467) ==="
# Codex and OpenCode gained live-tier markers, so `--agent` now resolves for
# them. Naming an agent must NOT by itself license a screen override: the caller
# still has to assert currency, or a shell caller that cannot observe the pane
# would be able to override the ledger with stale scrollback.
for agent in claude codex opencode; do
    check "--agent $agent alone still reports the ledger" "IMPLEMENT" \
        "$(field "$("$GATE" workflow-phase 501 --screen "$screen" --agent "$agent")" PHASE)"
    check "--agent $agent alone keeps source=ledger" "ledger" \
        "$(field "$("$GATE" workflow-phase 501 --screen "$screen" --agent "$agent")" SOURCE)"
    check "--agent $agent resolves" "scoped" \
        "$(field "$("$GATE" workflow-phase 501 --agent "$agent")" RESOLUTION)"
done

# The measured wrapper shape: a pane command that maps to no agent must report
# itself as unresolved rather than as a caller that supplied nothing.
check "--pane-command node is unresolved" "unresolved" \
    "$(field "$("$GATE" workflow-phase 501 --pane-command node)" RESOLUTION)"
check "no agent at all is 'absent'" "absent" \
    "$(field "$("$GATE" workflow-phase 501)" RESOLUTION)"
check "--pane-command claude resolves at rung 1" "scoped" \
    "$(field "$("$GATE" workflow-phase 501 --pane-command /usr/bin/claude)" RESOLUTION)"

echo
echo "=== bash <-> python parity on the same fixtures ==="
if [[ -z "$PY" ]]; then
    echo "  (skipping python-parity asserts: no interpreter resolved)"
else
    for num in 500 501 502; do
        b="$("$GATE" workflow-phase "$num")"
        p="$("$PY" "$PHASE_PY" signal "$TASK_DIR/t${num}_demo.md" \
             --profiles-dir "$TASK_DIR/metadata/profiles")"
        check "py parity t$num PHASE" "$(field "$b" PHASE)" "$(field "$p" PHASE)"
        check "py parity t$num SOURCE" "$(field "$b" SOURCE)" "$(field "$p" SOURCE)"
    done
fi

echo
echo "=== Degrade path is pinned in source ==="
# Mirrors test_gate_reentry.sh: assert the no-python fallback literally, rather
# than trying to run without an interpreter.
hits=$(grep -c 'delegate_python_phase signal "$file"' "$GATE")
check "verb delegates to the phase module" "1" "$hits"
hits=$(grep -c 'PHASE:UNKNOWN|WAITING:UNKNOWN|SOURCE:none' "$GATE")
check "degrades to an all-UNKNOWN line" "1" "$hits"

# The shell literal necessarily duplicates `workflow_phase.UNKNOWN_LINE` (it is
# the fallback for "python did not run", so it cannot ask python for it). Pin
# them EQUAL rather than merely both-present: adding a wire field bumped the
# module's line and silently left the shell's behind exactly once already
# (t1467 added RESOLUTION). parse_signal is total, so the drift is invisible at
# runtime — which is why it needs a guard rather than a comment.
if [[ -n "$PY" ]]; then
    shell_line=$(sed -n 's/.*|| echo "\(PHASE:UNKNOWN[^"]*\)".*/\1/p' "$GATE" | head -n1)
    module_line=$("$PY" -c "
import sys; sys.path.insert(0, '.aitask-scripts/lib')
import workflow_phase as wp
print(wp.UNKNOWN_LINE)")
    check "shell degrade line matches workflow_phase.UNKNOWN_LINE" \
        "$module_line" "$shell_line"
fi

echo
echo "=== Registered in every place a verb lives ==="
for site in 'workflow-phase <task-id>' 'workflow-phase) shift; cmd_workflow_phase'; do
    hits=$(grep -cF -- "$site" "$GATE")
    check "registered: ${site:0:34}" "1" "$([[ "$hits" -ge 1 ]] && echo 1 || echo 0)"
done

for d in "${CLEANUP_DIRS[@]}"; do rm -rf "$d"; done

echo
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] && echo "All tests PASSED" || echo "SOME TESTS FAILED"
exit $(( FAIL > 0 ? 1 : 0 ))
