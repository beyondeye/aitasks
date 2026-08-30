#!/usr/bin/env bash
# test_plan_approved_marker_contract.sh - The `plan_approved_at` (t1595)
# lifecycle contract, asserted against the RENDERED procedure surfaces.
#
# The marker's meaning -- "plan approved, implementation deliberately deferred,
# not since invalidated" -- is only true if every site that ends that state
# clears it. Those sites are skill PROSE spread across five procedure files
# (planning.md carries two of them: the §6.0 replan branches and the §6.1
# decomposition cleanup), so
# a later edit can silently drop one and leave a marker that actively lies about
# a task. This test is the executable guard for that (the post-phase mitigation
# recorded in aiplans/p1595_*.md).
#
# It pins the boundary in BOTH directions. A presence-only test would pass on a
# build that clears the marker everywhere -- including the risk-mitigation
# "before" stop, where the plan is approved and still awaiting implementation
# and the marker MUST survive. That is the specific mistake the consumption
# boundary exists to prevent, so its absence is asserted too.
#
# Rendered, not template, surfaces: the rendered file is what an agent actually
# reads, and it is what a stale re-render would break.
#
# Run: bash tests/test_plan_approved_marker_contract.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

# The profile-invariant sites are checked against the `default` render; the
# risk-mitigation stop only exists under a profile whose active gate set carries
# risk_evaluated, so its absence check uses the `fast` render (checking it in a
# render where the block does not exist at all would be vacuous).
DEFAULT_DIR="$PROJECT_DIR/.claude/skills/task-workflow-default-"
FAST_DIR="$PROJECT_DIR/.claude/skills/task-workflow-fast-"

# hits <file> <fixed-string> -- count of matching lines.
hits() { grep -cF -- "$2" "$1" || true; }

assert_hits() { # assert_hits <label> <expected> <file> <needle>
    assert_eq_trim "$1" "$2" "$(hits "$3" "$4")"
}

echo "--- Preconditions: the rendered surfaces exist ---"
for f in "$DEFAULT_DIR/plan-approved-stop.md" "$DEFAULT_DIR/SKILL.md" \
         "$DEFAULT_DIR/planning.md" "$DEFAULT_DIR/task-abort.md" \
         "$DEFAULT_DIR/cross-repo-child-assignment.md" "$FAST_DIR/SKILL.md"; do
    TOTAL=$((TOTAL + 1))
    if [[ -f "$f" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: missing rendered surface $f (run aitask_skill_rerender.sh)"
    fi
done

echo "--- The single writer: deferred sets, drift clears ---"

STOP="$DEFAULT_DIR/plan-approved-stop.md"
assert_hits "plan-approved-stop.md stamps the marker on the deferred stop" \
    "1" "$STOP" '--status Ready --assigned-to "" --plan-approved-at now'
assert_hits "plan-approved-stop.md CLEARS the marker on the drift stop" \
    "1" "$STOP" '--status Ready --assigned-to "" --plan-approved-at ""'
# The drift branch must not re-stamp: refreshing a marker on the path that just
# established the plan needs re-verification is the failure this pins.
assert_eq_trim "the drift stop never stamps 'now' a second time" \
    "1" "$(hits "$STOP" '--plan-approved-at now')"

# --- each stop_reason SELECTS only its matching command ------------------
#
# Rendering both commands is not enough: without an explicit conditional an
# agent on the drift path can run the `now` command and refresh a marker on the
# very path that established the plan needs re-verification. The selection is
# asserted POSITIONALLY -- each reason's conditional header must be followed by
# its own command before the other reason's header appears.
deferred_hdr="$(grep -n 'If `stop_reason` is `deferred`' "$STOP" | head -n1 | cut -d: -f1)"
drift_hdr="$(grep -n 'If `stop_reason` is `drift`' "$STOP" | head -n1 | cut -d: -f1)"
now_cmd="$(grep -nF -- '--plan-approved-at now' "$STOP" | head -n1 | cut -d: -f1)"
clear_cmd="$(grep -nF -- '--assigned-to "" --plan-approved-at ""' "$STOP" | head -n1 | cut -d: -f1)"

assert_hits "plan-approved-stop.md has an explicit 'deferred' conditional" \
    "1" "$STOP" 'If `stop_reason` is `deferred`'
assert_hits "plan-approved-stop.md has an explicit 'drift' conditional" \
    "1" "$STOP" 'If `stop_reason` is `drift`'

TOTAL=$((TOTAL + 1))
if [[ -n "$deferred_hdr" && -n "$drift_hdr" && -n "$now_cmd" && -n "$clear_cmd" \
   && "$deferred_hdr" -lt "$now_cmd" && "$now_cmd" -lt "$drift_hdr" \
   && "$drift_hdr" -lt "$clear_cmd" ]]; then
    PASS=$((PASS + 1))
    echo "PASS: each stop_reason conditional selects only its own command (deferred@$deferred_hdr -> now@$now_cmd, drift@$drift_hdr -> clear@$clear_cmd)"
else
    FAIL=$((FAIL + 1))
    echo "FAIL: the stop_reason branches do not strictly interleave with their commands (deferred@$deferred_hdr now@$now_cmd drift@$drift_hdr clear@$clear_cmd) -- a drift stop could execute the deferred command"
fi

echo "--- The clear sites ---"

assert_hits "SKILL.md consumes the marker when implementation starts" \
    "1" "$DEFAULT_DIR/SKILL.md" '--plan-approved-at "" --silent'
assert_hits "planning.md clears the marker on replan" \
    "1" "$DEFAULT_DIR/planning.md" '--plan-approved-at "" --silent'
# planning.md carries TWO clear sites: §6.0's replan branches (above, matched on
# the --silent form) and §6.1's decomposition cleanup (below, matched on
# <parent_num>). The decomposition assertion is the direct counterpart to the
# mitigation-stop ABSENCE check further down -- decomposition replaces the
# single-task plan with children, so the marker must go; the mitigation stop
# merely blocks an intact plan, so it must stay. Asserting only one of the pair
# passes on a build that gets the other backwards (t1640).
# ...in EVERY profile render, not just the interactive one. The replan branches
# exist under a profile-driven `create_new` too, and the clearing block must not
# live inside the interactive-only Jinja branch -- there it would render as a
# dangling "see Clearing on replan" reference with no command behind it.
for prof_dir in "$DEFAULT_DIR" "$FAST_DIR" "$PROJECT_DIR/.claude/skills/task-workflow-remote-"; do
    assert_hits "planning.md ($(basename "$prof_dir")) renders the replan clear command" \
        "1" "$prof_dir/planning.md" '--plan-approved-at "" --silent'
done
for prof_dir in "$DEFAULT_DIR" "$FAST_DIR" "$PROJECT_DIR/.claude/skills/task-workflow-remote-"; do
    assert_hits "planning.md ($(basename "$prof_dir")) clears the marker on decomposition" \
        "1" "$prof_dir/planning.md" \
        '--batch <parent_num> --status Ready --assigned-to "" --plan-approved-at ""'
done
assert_hits "task-abort.md clears the marker on abort" \
    "1" "$DEFAULT_DIR/task-abort.md" '--assigned-to "" --plan-approved-at ""'
assert_hits "cross-repo-child-assignment.md clears the marker on demotion" \
    "1" "$DEFAULT_DIR/cross-repo-child-assignment.md" \
    '--status Ready --assigned-to "" --plan-approved-at ""'

echo "--- The prompt: exact conditional option labels ---"

# The marker's user-visible payoff is the recommendation in the existing-plan
# prompt. Prose saying "mark it as recommended" is not enough -- the literal
# label an agent emits has to be spelled out, or it emits the plain label and
# the distinction is invisible.
PLAN_MD="$DEFAULT_DIR/planning.md"
assert_hits "the marker variant names the exact 'Use current plan (Recommended)' label" \
    "1" "$PLAN_MD" '"Use current plan (Recommended)"'
assert_hits "the force-verify variant names the exact 'Verify plan (Recommended)' label" \
    "1" "$PLAN_MD" '"Verify plan (Recommended)"'
# Only one option may ever carry the suffix, and force_verify must outrank the
# marker -- both are stated as rules an agent can follow, not left implicit.
assert_contains "the prompt forbids more than one recommended option" \
    'Never suffix `(Recommended)` on more than one option' "$(cat "$PLAN_MD")"
assert_contains "force_verify outranks the marker in the prompt" \
    'never recommend "Use current plan" when `force_verify` is set' "$(cat "$PLAN_MD")"

echo "--- The boundary: the mitigation stop must NOT clear it ---"

# Under `fast` the risk-mitigation "before" stop block renders. Its revert must
# stay a plain revert: that task's plan is approved and awaiting implementation,
# merely blocked -- which is exactly what the marker means.
FAST_SKILL="$FAST_DIR/SKILL.md"
assert_contains "the risk-mitigation 'before' stop block renders under fast" \
    "risk_before_blocking: true" "$(cat "$FAST_SKILL")"
mitig_revert_line="$(grep -nF -- 'aitask_update.sh --batch <task_num> --status Ready --assigned-to ""' "$FAST_SKILL" | head -n1)"
TOTAL=$((TOTAL + 1))
if [[ -n "$mitig_revert_line" ]]; then
    PASS=$((PASS + 1))
    echo "PASS: the mitigation stop reverts with a plain --status Ready (no marker clear)"
else
    FAIL=$((FAIL + 1))
    echo "FAIL: the mitigation stop's plain revert line is gone -- if it now clears the marker, a blocked-but-approved plan stops being visible"
fi
# ...and the deliberate-omission note is present, so the next reader does not
# "fix" it by mirroring the clear from the implementation body.
assert_contains "the omission is documented as deliberate at that site" \
    'Deliberately no `--plan-approved-at ""` here' "$(cat "$FAST_SKILL")"

# Under fast, SKILL.md must still carry exactly ONE marker-clearing COMMAND (the
# consumption at the implementation body) -- not two. Counted on the full command
# rather than the flag alone, which also appears in the prose note above.
assert_hits "fast SKILL.md carries exactly one marker-clearing command" \
    "1" "$FAST_SKILL" 'aitask_update.sh --batch <task_num> --plan-approved-at "" --silent'

echo ""
echo "===================="
echo "Passed: $PASS / $TOTAL"
if [[ "$FAIL" -ne 0 ]]; then
    echo "Failed: $FAIL"
    echo "===================="
    exit 1
fi
echo "===================="
