#!/usr/bin/env bash
# test_task_workflow_reentry_drift.sh - Structural guards for the t1380
# re-entry / stop-sequence wiring in .claude/skills/task-workflow/.
#
# These are prose contracts that no golden pins by name: goldens catch *any*
# byte change, but they cannot say which sentence is load-bearing. Each guard
# below names one.
#
# Coverage:
#   1-2. Both stop branches (planning.md "Approve and stop here",
#        remote-drift-check.md "Stop and re-verify plan") REFERENCE the shared
#        Approved-Plan Stop Sequence and no longer inline the revert — the
#        structural fix for Defect 1 (a reference cannot drop a step the way a
#        partial copy did).
#   3.   plan-approved-stop.md carries the guarded, once-only recording.
#   4.   Re-entry Routing resolves branches from the PLAN HEADER (never the
#        profile), fails closed on an unsafe ref, and dispatches the right
#        remote check per route (Defect 2).
#   5.   merge-target-sync.md is fast-forward-only and never reverts the task.
#   6.   Rendered zero-footprint: plan-approved-stop.md emits no gate-recording
#        machinery under a non-recording profile.
#
# NEGATIVE CONTROLS: every guard is proven to discriminate by mutating the real
# source file, re-running THIS script as a child (AIT_NEGCTRL_CHILD=1 so it
# runs guards only), and requiring the child to exit 1 AND to name the expected
# guard. The mutation is then reversed with its exact inverse — never
# `git checkout`, which would discard a concurrent session's edits to the same
# file. One mutation per control.
#
# Run: bash tests/test_task_workflow_reentry_drift.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

WF="$PROJECT_DIR/.claude/skills/task-workflow"
PROFILES_DIR="$PROJECT_DIR/aitasks/metadata/profiles"

PY="$( . "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" 2>/dev/null; require_ait_python 2>/dev/null || true)"
HAVE_JINJA=0
if [[ -n "$PY" ]] && "$PY" -c 'import minijinja' 2>/dev/null; then
    HAVE_JINJA=1
fi

render() {
    "$PY" "$PROJECT_DIR/.aitask-scripts/lib/skill_template.py" "$1" "$PROFILES_DIR/$2.yaml" claude 2>&1
}

# slice_between <file> <start-substring> <end-substring>
#
# Print the lines from the first line CONTAINING <start-substring> up to (not
# including) the next line containing <end-substring>. Several guards below are
# about what a SPECIFIC section must not contain — e.g. planning.md legitimately
# keeps `--status Ready --assigned-to ""` in its child-task and risk-mitigation
# branches, so a whole-file assertion would be false. Scope, don't over-claim.
#
# Matching is LITERAL (awk `index`), not regex: every useful anchor in these
# files starts with markdown bold (`- **Resolve …`), and `**` in an ERE is a
# stacked quantifier that silently matches nothing.
slice_between() {
    awk -v s="$2" -v e="$3" '
        index($0, s) { inside = 1 }
        inside && seen && index($0, e) { inside = 0 }
        inside { print; seen = 1 }
    ' "$1"
}

# ===========================================================================
# Guards
# ===========================================================================

guards_stop_sequence_shared() {
    local planning drift stop
    planning="$(cat "$WF/planning.md")"
    drift="$(cat "$WF/remote-drift-check.md")"
    stop="$(cat "$WF/plan-approved-stop.md")"

    # 1. planning.md delegates instead of inlining. Scope the "no inline
    #    revert" claim to the checkpoint branch: planning.md legitimately
    #    reverts to Ready elsewhere (child-task creation, risk-mitigation stop).
    local planning_stop
    planning_stop="$(slice_between "$WF/planning.md" 'If "Approve and stop here":' 'If "Abort"')"
    assert_contains "planning-references-stop-sequence" \
        'plan-approved-stop.md' "$planning_stop"
    assert_not_contains "planning-no-inline-revert" \
        '--status Ready --assigned-to ""' "$planning_stop"
    # The old inline copy is what dropped the recording; planning.md must no
    # longer carry its own record_gates-guarded plan_approved call either.
    assert_not_contains "planning-no-inline-gate-recording" \
        'gate_name=plan_approved' "$planning"

    # The delegating references must stay UNGUARDED: plan-approved-stop.md owns
    # the record_gates guard once, on both branches' behalf. Adding a second
    # guard at either reference is the plausible maintainer mistake here — it
    # would look harmless and would silently re-fork the two branches.
    assert_not_contains "planning-delegation-is-unguarded" \
        'record_gates' "$planning"
    assert_not_contains "drift-delegation-is-unguarded" \
        'record_gates' "$drift"
    # ...and gate-recording.md must name the real call-site files, so nobody
    # goes looking for a guard at a reference that has none.
    local recording
    recording="$(cat "$WF/gate-recording.md")"
    assert_contains "gate-recording-names-stop-sequence-callsite" \
        '`plan-approved-stop.md` — the deferred `plan_approved`' "$recording"
    assert_contains "gate-recording-says-delegators-are-unguarded" \
        'do NOT call this procedure and must' "$recording"

    # 2. remote-drift-check.md delegates to the SAME procedure.
    assert_contains "drift-references-stop-sequence" \
        'plan-approved-stop.md' "$drift"
    assert_not_contains "drift-no-inline-revert" \
        '--status Ready --assigned-to ""' "$drift"
    # It must pass a distinguishable stop_reason so the ledger records why.
    assert_contains "drift-passes-stop-reason" 'stop_reason=drift' "$drift"
    assert_contains "planning-passes-stop-reason" 'stop_reason=deferred' "$planning"

    # 3. The shared file carries the once-only recording and the revert.
    assert_contains "stop-sequence-has-recorded-pass-guard" \
        'aitask_gate.sh recorded-pass <task_id> plan_approved' "$stop"
    assert_contains "stop-sequence-records-plan-approved" \
        'gate_name=plan_approved' "$stop"
    assert_contains "stop-sequence-reverts-to-ready" \
        '--status Ready --assigned-to ""' "$stop"
    # Defect 3: the recording must NOT be described as a resume signal.
    assert_contains "stop-sequence-audit-not-routing" \
        'not a routing signal' "$stop"
    assert_not_contains "stop-sequence-no-resume-signal-claim" \
        'this is the resume signal' "$stop"
    assert_not_contains "planning-no-resume-signal-claim" \
        'this is the resume signal' "$planning"
}

guards_reentry_routing() {
    local skill
    skill="$(cat "$WF/SKILL.md")"

    # 4a. Branch resolution comes from the plan header, validated, fail-closed.
    assert_contains "reentry-parses-output-branch-header" \
        "output_branch=\$(sed -n 's/^Output branch: //p'" "$skill"
    assert_contains "reentry-parses-base-branch-header" \
        "base_branch=\$(sed -n 's/^Base branch: //p'" "$skill"
    assert_contains "reentry-validates-ref-format" \
        'git check-ref-format --branch' "$skill"
    assert_contains "reentry-fails-closed-on-unsafe-ref" \
        'UNSAFE_BRANCH' "$skill"
    # Never resolve either branch from the profile — a resumed session may run
    # under a different one (the same rule Step 9 states). Asserted positively
    # and scoped to the branch-resolution step: SKILL.md mentions
    # `profile.output_branch` legitimately in Step 5 and Step 9, so a whole-file
    # "must not contain" would be false rather than protective.
    local reentry_branches
    reentry_branches="$(slice_between "$WF/SKILL.md" \
        "- **Resolve the plan's branches:" '- **Environment setup')"
    assert_contains "reentry-forbids-profile-branch-resolution" \
        'never from `profile.base_branch` / `profile.output_branch`' "$reentry_branches"
    assert_contains "reentry-forbids-base-fallback-for-output" \
        'Never fall back to `Base branch:` for the output branch' "$reentry_branches"

    # 4b. Per-route remote checks (Defect 2).
    assert_contains "reentry-implement-runs-drift-check" \
        'Remote drift check (re-entry).' "$skill"
    assert_contains "reentry-postimpl-runs-merge-sync" \
        'Merge-Target Sync Pre-flight Procedure** (see `merge-target-sync.md`)' "$skill"
    # The loop-termination argument is the AC; it must be stated, not implied.
    assert_contains "reentry-documents-loop-termination" \
        'The loop terminates.' "$skill"
    # The POSTIMPL exemption must rest on the true reason (Step 9 never
    # fetches), not on the false "the merge surfaces it".
    assert_contains "reentry-postimpl-states-step9-never-fetches" \
        'Step 9 **never fetches**' "$skill"

    # 4c. Both new procedures are discoverable from the Procedures list.
    assert_contains "skill-lists-stop-sequence-procedure" \
        '**Approved-Plan Stop Sequence** (`plan-approved-stop.md`)' "$skill"
    assert_contains "skill-lists-merge-target-sync-procedure" \
        '**Merge-Target Sync Pre-flight Procedure** (`merge-target-sync.md`)' "$skill"
}

guards_merge_target_sync() {
    local sync
    sync="$(cat "$WF/merge-target-sync.md")"

    assert_contains "sync-uses-unsynced-flag" '--unsynced' "$sync"
    assert_contains "sync-is-fast-forward-only" 'git merge --ff-only' "$sync"
    assert_contains "sync-asserts-symbolic-ref" 'git symbolic-ref --short HEAD' "$sync"
    assert_contains "sync-refuses-on-divergence" 'Do **not** rebase, reset, force' "$sync"
    # A POSTIMPL stop must never revert reviewed, committed work to Ready.
    assert_not_contains "sync-never-reverts-task" '--status Ready' "$sync"
}

guards_rendered_zero_footprint() {
    if [[ "$HAVE_JINJA" -ne 1 ]]; then
        echo "(skipping render guards: minijinja not installed in framework venv)"
        return
    fi
    local out p
    for p in default remote; do
        out="$(render "$WF/plan-approved-stop.md" "$p")"
        assert_not_contains "stop-sequence-zero-footprint-$p-procedure" \
            'Gate Recording Procedure' "$out"
        assert_not_contains "stop-sequence-zero-footprint-$p-recorder" \
            'aitask_gate_record.sh' "$out"
        assert_not_contains "stop-sequence-zero-footprint-$p-gatename" \
            'gate_name=plan_approved' "$out"
        assert_contains "stop-sequence-still-reverts-$p" \
            '--status Ready --assigned-to ""' "$out"
    done
    out="$(render "$WF/plan-approved-stop.md" fast)"
    assert_contains "stop-sequence-records-under-fast" 'gate_name=plan_approved' "$out"
}

run_all_guards() {
    guards_stop_sequence_shared
    guards_reentry_routing
    guards_merge_target_sync
    guards_rendered_zero_footprint
}

# ===========================================================================
# Child mode: guards only (the negative-control subject)
# ===========================================================================

if [[ -n "${AIT_NEGCTRL_CHILD:-}" ]]; then
    run_all_guards
    if [[ "$FAIL" -gt 0 ]]; then exit 1; fi
    exit 0
fi

# ===========================================================================
# Parent mode: guards, then negative controls
# ===========================================================================

echo "=== Guards ==="
run_all_guards

# --- negative-control machinery --------------------------------------------

PENDING_FILE=""
PENDING_INVERSE=""

# Literal-ish substitution via sed into a temp file, then written back through
# the SAME inode (`cat >`), so file mode and any open handles survive.
_sed_swap() {
    local f="$1" expr="$2" tmp
    tmp="$(mktemp "${TMPDIR:-/tmp}/ait_negctrl_XXXXXX")"
    if sed "$expr" "$f" > "$tmp"; then
        cat "$tmp" > "$f"
    fi
    rm -f "$tmp"
}

restore_pending() {
    if [[ -n "$PENDING_FILE" ]]; then
        _sed_swap "$PENDING_FILE" "$PENDING_INVERSE"
        PENDING_FILE=""
        PENDING_INVERSE=""
    fi
}
trap restore_pending EXIT

# negctrl <expected-guard-id> <file> <break-expr> <restore-expr>
negctrl() {
    local guard_id="$1" file="$2" break_expr="$3" restore_expr="$4"
    local out rc

    PENDING_FILE="$file"
    PENDING_INVERSE="$restore_expr"
    _sed_swap "$file" "$break_expr"

    out="$(AIT_NEGCTRL_CHILD=1 bash "$0" 2>&1)"; rc=$?

    restore_pending

    TOTAL=$((TOTAL + 1))
    if [[ "$rc" -eq 0 ]]; then
        FAIL=$((FAIL + 1))
        echo "NEGCTRL FAIL: breaking '$guard_id' did not fail the suite (exit 0)"
    elif ! printf '%s' "$out" | grep -qF "FAIL: $guard_id"; then
        FAIL=$((FAIL + 1))
        echo "NEGCTRL FAIL: suite failed, but not on '$guard_id' (wrong reason)"
        printf '%s\n' "$out" | grep -E '^(FAIL|NEGCTRL FAIL):' | head -5
    else
        PASS=$((PASS + 1))
    fi
}

echo "=== Negative controls (each must fail the suite, for the right reason) ==="

negctrl "planning-references-stop-sequence" "$WF/planning.md" \
    's|plan-approved-stop\.md|plan-approved-stop-BROKEN.md|g' \
    's|plan-approved-stop-BROKEN\.md|plan-approved-stop.md|g'

negctrl "drift-references-stop-sequence" "$WF/remote-drift-check.md" \
    's|plan-approved-stop\.md|plan-approved-stop-BROKEN.md|g' \
    's|plan-approved-stop-BROKEN\.md|plan-approved-stop.md|g'

negctrl "planning-delegation-is-unguarded" "$WF/planning.md" \
    's|^If "Approve and stop here":$|If "Approve and stop here":\n{% if profile.record_gates is defined and profile.record_gates %}|' \
    '/^{% if profile.record_gates is defined and profile.record_gates %}$/d'

negctrl "gate-recording-says-delegators-are-unguarded" "$WF/gate-recording.md" \
    's|do NOT call this procedure and must|call this procedure and must|' \
    's|^\*\*`planning.md` and `remote-drift-check.md` call this procedure and must|**`planning.md` and `remote-drift-check.md` do NOT call this procedure and must|'

negctrl "stop-sequence-has-recorded-pass-guard" "$WF/plan-approved-stop.md" \
    's|aitask_gate\.sh recorded-pass|aitask_gate.sh recorded-pass-BROKEN|g' \
    's|aitask_gate\.sh recorded-pass-BROKEN|aitask_gate.sh recorded-pass|g'

negctrl "stop-sequence-audit-not-routing" "$WF/plan-approved-stop.md" \
    's|not a routing signal|not a BROKEN signal|g' \
    's|not a BROKEN signal|not a routing signal|g'

negctrl "reentry-forbids-profile-branch-resolution" "$WF/SKILL.md" \
    's|never from `profile.base_branch` / `profile.output_branch`|from the active profile|' \
    's|from the active profile|never from `profile.base_branch` / `profile.output_branch`|'

negctrl "reentry-fails-closed-on-unsafe-ref" "$WF/SKILL.md" \
    's|UNSAFE_BRANCH|SAFE_BRANCH_BROKEN|g' \
    's|SAFE_BRANCH_BROKEN|UNSAFE_BRANCH|g'

negctrl "reentry-implement-runs-drift-check" "$WF/SKILL.md" \
    's|Remote drift check (re-entry)\.|Remote drift check BROKEN.|g' \
    's|Remote drift check BROKEN\.|Remote drift check (re-entry).|g'

negctrl "reentry-postimpl-runs-merge-sync" "$WF/SKILL.md" \
    's|merge-target-sync\.md|merge-target-sync-BROKEN.md|g' \
    's|merge-target-sync-BROKEN\.md|merge-target-sync.md|g'

negctrl "reentry-postimpl-states-step9-never-fetches" "$WF/SKILL.md" \
    's|Step 9 \*\*never fetches\*\*|Step 9 **sometimes fetches**|g' \
    's|Step 9 \*\*sometimes fetches\*\*|Step 9 **never fetches**|g'

negctrl "sync-is-fast-forward-only" "$WF/merge-target-sync.md" \
    's|git merge --ff-only|git merge --BROKEN|g' \
    's|git merge --BROKEN|git merge --ff-only|g'

# Insert a single whole line and delete that same whole line — an exact
# inverse. A blank-out inverse (s|…||) would leave a stray empty line behind.
negctrl "sync-never-reverts-task" "$WF/merge-target-sync.md" \
    's|^## Notes$|BROKEN-NEGCTRL: --status Ready --assigned-to ""\n## Notes|' \
    '/^BROKEN-NEGCTRL: --status Ready/d'

if [[ "$HAVE_JINJA" -eq 1 ]]; then
    # Removing the record_gates guard would leak the recording into `default`.
    negctrl "stop-sequence-zero-footprint-default-gatename" "$WF/plan-approved-stop.md" \
        's|{% if profile.record_gates is defined and profile.record_gates %}|{% if true %}|' \
        's|{% if true %}|{% if profile.record_gates is defined and profile.record_gates %}|'
fi

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
if [[ "$FAIL" -gt 0 ]]; then
    exit 1
else
    echo "All tests PASSED"
fi
