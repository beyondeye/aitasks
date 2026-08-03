#!/usr/bin/env bash
# test_gate_plan_approval_transitions.sh - Behavioural tests for the
# plan_approval ledger transitions the t1380 procedures drive.
#
# WHY THIS EXISTS: the two procedures that own these transitions
# (plan-approved-stop.md's "Record the approval — once" and task-abort.md's
# "Re-open a recorded plan approval") are agent prose, so a structural test can
# only prove that the prose *mentions* the commands. This file executes the
# documented sequences against a real git-initialised fixture and asserts the
# resulting LEDGER STATE, then binds the executed sequence back to the prose by
# asserting the rendered procedure files carry exactly those commands.
#
# Coverage:
#   1. drift-stop on a task with no prior approval -> plan_approved pass
#      (note=drift), resume-point IMPLEMENT.
#   2. drift-stop on a task that ALREADY has the pass -> no second block
#      appended (the recorded-pass guard suppresses the duplicate).
#   3. abort on that task -> plan_approved fail (note=aborted), recorded-pass
#      now exits 1, resume-point demoted to PLAN. Runs with NO profile in
#      scope, which is exactly the "fast-recorded ledger aborted under default"
#      cross-profile case: both scripts are profile-agnostic.
#   4. abort on a task with NO ledger -> nothing appended AND no `## Gate Runs`
#      section created. This is the executable proof that behaviour under
#      `record_gates: false` is unchanged.
#   5. Prose binding: the rendered task-abort.md carries the demotion on EVERY
#      profile (no Jinja gate may remove it), and plan-approved-stop.md carries
#      the guarded recording on a recording profile only.
#
# Run: bash tests/test_gate_plan_approval_transitions.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

GATE="$PROJECT_DIR/.aitask-scripts/aitask_gate.sh"
GATE_RECORD="$PROJECT_DIR/.aitask-scripts/aitask_gate_record.sh"
WORKFLOW_DIR="$PROJECT_DIR/.claude/skills/task-workflow"
PROFILES_DIR="$PROJECT_DIR/aitasks/metadata/profiles"

# --- Fixture: a real git repo so gate-record's path-scoped commit runs for real.

REPO=""
make_repo() {
    REPO="$(mktemp -d "${TMPDIR:-/tmp}/test_plan_approval_XXXXXX")"
    CLEANUP_DIRS+=("$REPO")
    git init --quiet "$REPO"
    (
        cd "$REPO"
        git config user.email "test@example.com"
        git config user.name  "Test"
        mkdir -p aitasks/metadata
        echo "seed" > README.md
        git add README.md
        git commit --quiet -m "init"
    )
    export TASK_DIR="$REPO/aitasks"
}

make_task() {
    local id="$1"
    {
        echo "---"
        echo "priority: high"
        echo "status: Implementing"
        echo "---"
        echo
        echo "Body for t${id}."
    } > "$TASK_DIR/t${id}_demo.md"
}

task_path() { echo "$TASK_DIR/t${1}_demo.md"; }

# Count appended blocks for a gate (each block starts with a `> **… gate:<g>**`
# marker line), so a suppressed duplicate is detectable.
marker_count() {
    local id="$1" gate="$2"
    grep -c "gate:${gate}\*\*" "$(task_path "$id")" 2>/dev/null || true
}

# --- The documented sequences, transcribed from the procedure files ----------
#
# plan-approved-stop.md, "Record the approval — once":
#   recorded-pass <id> plan_approved  ->  exit 1 = record, exit 0 = skip
proc_stop_record_approval() {
    local id="$1" stop_reason="$2"
    if "$GATE" recorded-pass "$id" plan_approved >/dev/null 2>&1; then
        return 0   # already recorded — skip (no duplicate)
    fi
    ( cd "$REPO" && "$GATE_RECORD" "$id" plan_approved pass type=human "note=$stop_reason" ) >/dev/null 2>&1
}

# task-abort.md, "Re-open a recorded plan approval":
#   recorded-pass <id> plan_approved  ->  exit 0 = demote, exit 1 = skip
proc_abort_reopen_approval() {
    local id="$1"
    if ! "$GATE" recorded-pass "$id" plan_approved >/dev/null 2>&1; then
        return 0   # nothing recorded — skip
    fi
    ( cd "$REPO" && "$GATE_RECORD" "$id" plan_approved fail type=human note=aborted ) >/dev/null 2>&1
}

# --- Tests -----------------------------------------------------------------

test_drift_stop_records() {
    echo "=== 1. drift-stop records plan_approved on a task with no prior approval ==="
    make_repo
    make_task 810

    assert_eq_trim "precondition: resume-point PLAN" "PLAN" "$("$GATE" resume-point 810)"

    proc_stop_record_approval 810 drift

    assert_exit_zero "plan_approved is now recorded" "$GATE" recorded-pass 810 plan_approved
    assert_eq_trim "resume-point promoted to IMPLEMENT" "IMPLEMENT" "$("$GATE" resume-point 810)"
    assert_contains "the recorded block carries the drift note" \
        "Note: drift" "$(cat "$(task_path 810)")"
    assert_contains "the recorded block is a pass" \
        "gate:plan_approved** run=" "$(cat "$(task_path 810)")"
    assert_eq "exactly one plan_approved block" "1" "$(marker_count 810 plan_approved)"

    # The persist half really ran: the task file is committed, not just dirty.
    local tracked
    tracked="$(cd "$REPO" && git log --oneline -- aitasks/t810_demo.md | wc -l | tr -d ' ')"
    assert_eq "gate-record committed the task file" "1" "$tracked"
}

test_drift_stop_is_idempotent() {
    echo "=== 2. drift-stop on an already-approved task appends nothing ==="
    make_repo
    make_task 811
    proc_stop_record_approval 811 deferred
    assert_eq "one block after first stop" "1" "$(marker_count 811 plan_approved)"

    # A re-entered task stopping again must not re-record.
    proc_stop_record_approval 811 drift
    assert_eq "still one block after second stop" "1" "$(marker_count 811 plan_approved)"
    assert_not_contains "no drift note added on the suppressed pass" \
        "Note: drift" "$(cat "$(task_path 811)")"
    assert_eq_trim "resume-point unchanged" "IMPLEMENT" "$("$GATE" resume-point 811)"
}

test_abort_demotes() {
    echo "=== 3. abort re-opens a recorded approval (cross-profile: no profile in scope) ==="
    make_repo
    make_task 812
    # Recorded as if by a `fast` session...
    proc_stop_record_approval 812 deferred
    assert_eq_trim "precondition: IMPLEMENT" "IMPLEMENT" "$("$GATE" resume-point 812)"

    # ...and aborted with NO profile in scope at all. Both scripts are
    # profile-agnostic, so this is the `default`-profile abort path.
    proc_abort_reopen_approval 812

    assert_exit_nonzero "plan_approved no longer reads as pass" \
        "$GATE" recorded-pass 812 plan_approved
    assert_eq_trim "resume-point demoted to PLAN" "PLAN" "$("$GATE" resume-point 812)"
    assert_contains "the demotion carries the aborted note" \
        "Note: aborted" "$(cat "$(task_path 812)")"
    assert_eq "two plan_approved blocks (append-only history preserved)" \
        "2" "$(marker_count 812 plan_approved)"

    # The invariant that matters: even if Check 5's status gate were relaxed,
    # routing cannot resume into implementation on the rejected plan.
    assert_eq_trim "re-abort is a no-op" "PLAN" "$("$GATE" resume-point 812)"
    proc_abort_reopen_approval 812
    assert_eq "no third block from a repeat abort" "2" "$(marker_count 812 plan_approved)"
}

test_abort_without_ledger_is_inert() {
    echo "=== 4. abort on a ledger-less task creates nothing (record_gates:false parity) ==="
    make_repo
    make_task 813
    local before
    before="$(cat "$(task_path 813)")"

    proc_abort_reopen_approval 813

    local after
    after="$(cat "$(task_path 813)")"
    assert_eq "task file byte-identical after abort" "$before" "$after"
    assert_not_contains "no ## Gate Runs section was created" \
        "## Gate Runs" "$after"
    assert_eq "no plan_approved block" "0" "$(marker_count 813 plan_approved)"
    assert_eq_trim "resume-point still PLAN" "PLAN" "$("$GATE" resume-point 813)"
}

test_prose_binding() {
    echo "=== 5. the rendered procedures carry the sequences this test executed ==="
    local py
    py="$( . "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" 2>/dev/null; require_ait_python 2>/dev/null || true)"
    if [[ -z "$py" ]] || ! "$py" -c 'import minijinja' 2>/dev/null; then
        echo "(skipping: minijinja not installed in framework venv)"
        return
    fi
    local render="$py $PROJECT_DIR/.aitask-scripts/lib/skill_template.py"

    local p out
    for p in default fast remote; do
        # task-abort.md's demotion must survive EVERY profile: it is gated on
        # ledger content, never on record_gates. A future Jinja guard here
        # would silently reintroduce the stale-approval bug on `default`.
        out="$($render "$WORKFLOW_DIR/task-abort.md" "$PROFILES_DIR/$p.yaml" claude 2>&1)"
        assert_contains "task-abort($p): recorded-pass guard" \
            'aitask_gate.sh recorded-pass <task_id> plan_approved' "$out"
        assert_contains "task-abort($p): demotion append" \
            'aitask_gate_record.sh <task_id> plan_approved fail type=human note=aborted' "$out"
    done

    # plan-approved-stop.md's recording IS record_gates-gated: present on a
    # recording profile, absent (with zero footprint) otherwise.
    out="$($render "$WORKFLOW_DIR/plan-approved-stop.md" "$PROFILES_DIR/fast.yaml" claude 2>&1)"
    assert_contains "plan-approved-stop(fast): recorded-pass guard" \
        'aitask_gate.sh recorded-pass <task_id> plan_approved' "$out"
    assert_contains "plan-approved-stop(fast): records the gate" \
        'gate_name=plan_approved' "$out"

    for p in default remote; do
        out="$($render "$WORKFLOW_DIR/plan-approved-stop.md" "$PROFILES_DIR/$p.yaml" claude 2>&1)"
        assert_not_contains "plan-approved-stop($p): no Gate Recording Procedure" \
            'Gate Recording Procedure' "$out"
        assert_not_contains "plan-approved-stop($p): no gate_name=plan_approved" \
            'gate_name=plan_approved' "$out"
        assert_not_contains "plan-approved-stop($p): no recorded-pass call" \
            'recorded-pass' "$out"
        # The rest of the sequence must still render — the guard removes the
        # recording, not the release-and-revert.
        assert_contains "plan-approved-stop($p): still reverts to Ready" \
            '--status Ready --assigned-to ""' "$out"
    done
}

# --- Run ---
test_drift_stop_records
test_drift_stop_is_idempotent
test_abort_demotes
test_abort_without_ledger_is_inert
test_prose_binding

for dir in "${CLEANUP_DIRS[@]}"; do
    rm -rf "$dir"
done

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
if [[ "$FAIL" -gt 0 ]]; then
    exit 1
else
    echo "All tests PASSED"
fi
