#!/usr/bin/env bash
# The advisory-only contract for the workflow-phase signal (t1420).
#
# This is the discriminating test for the whole feature. A happy-path check
# ("the right phase picks the right default") would pass just as well if the
# phase had become a GATE — which is exactly the shape
# aidocs/framework/shadow_agent.md forbids, and exactly the defect t1311 had to
# remove once already.
#
# So this proves the opposite property: that EVERY phase value — including
# UNKNOWN and a deliberately WRONG one — still reaches every shadow capability.
#
# Three layers:
#   1. Behaviour  — `--phase` is total: every stamp (valid, wrong, corrupt,
#      absent) yields one parseable line and exit 0, and never disturbs capture.
#   2. Structure  — every rendered shadow closure keeps its full capability list
#      and carries no phase-conditioned refusal.
#   3. Positive control — layer 2 is run against a fixture with an injected
#      phase-gate and MUST fail. Without this, a green sweep proves nothing.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR" || exit 1

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

check() {
    local name="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1)); echo "  PASS: $name"
    else
        FAIL=$((FAIL + 1)); echo "  FAIL: $name (expected '$expected', got '$actual')"
    fi
}

CAPTURE=".aitask-scripts/aitask_shadow_capture.sh"
GATE=".aitask-scripts/aitask_gate.sh"

# --- Layer 1: --phase is total -------------------------------------------

echo "=== Layer 1: --phase never refuses, whatever it reads ==="

# Runs outside a shadow pane (no @aitask_shadow_phase binding); that is itself
# one of the cases under test — an unstamped reader must still answer.
for arg in "" "1420" "99999" "not_a_task_id"; do
    label="${arg:-<no task id>}"
    if [[ -z "$arg" ]]; then
        out="$("$CAPTURE" --phase 2>/dev/null)"; rc=$?
    else
        out="$("$CAPTURE" --phase "$arg" 2>/dev/null)"; rc=$?
    fi
    check "--phase $label exits 0" "0" "$rc"
    # `$( )` strips the trailing newline, so re-add one before counting: exactly
    # one line ⇒ exactly one newline. (Counting the stripped form gives 0 and
    # cannot distinguish "one line" from "empty".)
    check "--phase $label prints exactly one line" "1" \
        "$(printf '%s\n' "$out" | wc -l | tr -d ' ')"
    case "$out" in
        PHASE:*\|WAITING:*\|SOURCE:*) parsed=1 ;;
        *) parsed=0 ;;
    esac
    check "--phase $label emits a parseable signal" "1" "$parsed"
done

# Every phase value reaches the reader intact, including a WRONG one: the reader
# must not "correct" or reject a value that disagrees with the ledger.
if [[ -n "${TMUX_PANE:-}" ]]; then
    echo
    echo "=== Layer 1b: a wrong / corrupt stamp is still served, never refused ==="
    # shellcheck source=lib/tmux_exec.sh
    source .aitask-scripts/lib/tmux_exec.sh
    for phase in PLAN IMPLEMENT POSTIMPL UNKNOWN; do
        # t1420 is recorded IMPLEMENT, so PLAN/POSTIMPL/UNKNOWN are all "wrong".
        line="PHASE:$phase|WAITING:WAITING|SOURCE:workflow-prompt|CONSULTED:ledger,screen|RECORDING:on|DETAIL:injected"
        ait_tmux set-option -p -t "$TMUX_PANE" @aitask_shadow_phase "$line" 2>/dev/null
        out="$("$CAPTURE" --phase 1420 2>/dev/null)"; rc=$?
        check "wrong phase $phase: exit 0" "0" "$rc"
        check "wrong phase $phase: served verbatim" "1" \
            "$(case "$out" in "PHASE:$phase|"*) echo 1 ;; *) echo 0 ;; esac)"
    done
    # A corrupt stamp must degrade to the ledger, not error out.
    ait_tmux set-option -p -t "$TMUX_PANE" @aitask_shadow_phase 'total garbage' 2>/dev/null
    out="$("$CAPTURE" --phase 1420 2>/dev/null)"; rc=$?
    check "corrupt stamp: exit 0" "0" "$rc"
    check "corrupt stamp: falls back to the ledger CLI" "1" \
        "$(case "$out" in *"VIA:ledger-cli") echo 1 ;; *) echo 0 ;; esac)"
    # ...and capture itself still works with a garbage phase stamp present.
    "$CAPTURE" --phase >/dev/null 2>&1
    check "capture path unaffected by a garbage phase stamp" "0" "$?"
    ait_tmux set-option -pu -t "$TMUX_PANE" @aitask_shadow_phase 2>/dev/null
else
    echo "  SKIP layer 1b: not running inside a tmux pane"
fi

# The plain ledger verb must never exit nonzero either — a shadow that cannot
# get a phase must lose the hint, not the run.
out="$("$GATE" workflow-phase 1420 2>/dev/null)"; rc=$?
check "gate workflow-phase exits 0" "0" "$rc"
check "gate workflow-phase emits a signal" "1" \
    "$(case "$out" in PHASE:*) echo 1 ;; *) echo 0 ;; esac)"

# --- Layer 2: no phase-conditioned refusal in any rendered closure --------

echo
echo "=== Layer 2: every rendered shadow closure stays ungated ==="

# The capability list Step 3 dispatches to. If the phase had become a gate, one
# of these would have been made conditional on it.
CAPABILITIES=(
    "plan-explain.md"
    "plan-challenge.md"
    "impl-challenge.md"
    "plan-socratic.md"
    "plan-assumptions.md"
    "plan-diagnose-errors.md"
    "spawn-learn-skill.md"
)

# Refusal wording within a few lines of a phase mention. Deliberately narrow:
# the point is a REFUSAL conditioned on phase, not any co-occurrence.
sweep_file() {
    # $1 = file. Prints the number of phase-conditioned refusals found.
    "$PY" - "$1" <<'PYEOF'
import re, sys
text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
lines = text.splitlines()
refusal = re.compile(r"\b(refuse|refuses|refusing|do not run|don't run|cannot run|"
                     r"must not run|is unavailable|not available|too early|"
                     r"abort the run|stop the run|only if the phase|"
                     r"unless the phase|requires the phase)\b", re.I)
phase = re.compile(r"\bphase\b", re.I)
hits = 0
for i, line in enumerate(lines):
    if not phase.search(line):
        continue
    window = lines[max(0, i - 2): i + 3]
    if any(refusal.search(w) for w in window):
        hits += 1
print(hits)
PYEOF
}

PY="$( . .aitask-scripts/lib/python_resolve.sh 2>/dev/null; resolve_python 2>/dev/null || true)"
if [[ -z "$PY" ]]; then
    echo "  SKIP layer 2: no python interpreter resolved"
else
    shopt -s nullglob
    closures=(.claude/skills/aitask-shadow-*-/SKILL.md
              .agents/skills/aitask-shadow-*-/SKILL.md
              .opencode/skills/aitask-shadow-*-/SKILL.md)
    shopt -u nullglob
    check "rendered closures were found" "1" \
        "$([[ ${#closures[@]} -ge 1 ]] && echo 1 || echo 0)"

    for closure in "${closures[@]}"; do
        dir="$(dirname "$closure")"
        short="${dir#./}"
        # Every capability still reachable from the dispatch list.
        missing=0
        for cap in "${CAPABILITIES[@]}"; do
            grep -qF -- "$cap" "$closure" || missing=$((missing + 1))
        done
        check "$short: all ${#CAPABILITIES[@]} capabilities still dispatched" "0" "$missing"
        # The explicit non-gating clause survives rendering.
        check "$short: carries the never-removes-a-capability clause" "1" \
            "$(grep -qF "never removes a capability" "$closure" && echo 1 || echo 0)"
        # No phase-conditioned refusal anywhere in the closure.
        total_hits=0
        for f in "$dir"/*.md; do
            h="$(sweep_file "$f")"
            total_hits=$((total_hits + h))
        done
        check "$short: no phase-conditioned refusal" "0" "$total_hits"
    done

    # --- Layer 3: positive control ---------------------------------------
    echo
    echo "=== Layer 3: the sweep detects an injected phase-gate ==="
    tmp="$(mktemp -d)"
    CLEANUP_DIRS+=("$tmp")
    cat > "$tmp/injected.md" <<'EOF'
## Step 3 — Serve the request

Before running any analysis, check the detected phase.

- **Adversarially challenge the implementation** — if the phase is not
  IMPLEMENT or POSTIMPL, refuse the review and tell the user it is too early.
EOF
    injected_hits="$(sweep_file "$tmp/injected.md")"
    check "sweep FAILS on an injected phase-gate (>0 hits)" "1" \
        "$([[ "$injected_hits" -gt 0 ]] && echo 1 || echo 0)"
    # ...and does not fire on ungated prose that merely mentions the phase.
    cat > "$tmp/clean.md" <<'EOF'
The phase is advisory. Every capability is available at every phase, including
one you believe is wrong. Cite the phase when you offer a default.
EOF
    clean_hits="$(sweep_file "$tmp/clean.md")"
    check "sweep is quiet on ungated phase prose" "0" "$clean_hits"
fi

for d in "${CLEANUP_DIRS[@]}"; do rm -rf "$d"; done

echo
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] && echo "All tests PASSED" || echo "SOME TESTS FAILED"
exit $(( FAIL > 0 ? 1 : 0 ))
