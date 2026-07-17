#!/usr/bin/env bash
# test_create_manual_verification_gates.sh - Regression tests for the
# manual_verification gate allowlist (t1156).
#
# A manual_verification task skips task-workflow Steps 6-8 (plan / risk /
# review), so gates recorded there (risk_evaluated, plan_approved,
# review_approved, docs_updated) are unreachable and would block archival
# forever (GATE_PENDING with max_retries: 0). aitask_create.sh keeps, for
# --type manual_verification, only the Step-9 gates the flow can reach
# (MANUAL_VERIFICATION_REACHABLE_GATES in lib/task_utils.sh) and strips the
# rest — at the run_batch_mode() sink AND at finalize_draft() (via
# enforce_manual_verification_gate_invariant).
#
# Covers:
#   1. Unit: filter_gates_for_issue_type (strip / keep / mixed / other-type
#      negative control / empty input / future planning gates).
#   2. Allowlist ⊆ registry guard: every allowlisted gate exists in the
#      canonical gate registry (rename/typo tripwire).
#   3. Injection-equivalence pin: the profile→template injection path emits
#      the exact `--gates "risk_evaluated"` CLI shape the integration tests
#      feed the sink (authoring template Jinja line + seed fast profile; the
#      locally-rendered fast variant is asserted too when present).
#   4. Integration: real aitask_create.sh --batch --commit in an isolated
#      repo (strip end-to-end, mixed keep, other-type negative control,
#      archive-ready → NO_GATES).
#   5. Finalize path: a hand-written manual_verification draft carrying
#      gates: [risk_evaluated] finalizes without the gate.
#
# Run: bash tests/test_create_manual_verification_gates.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"

# --- Unit-test helper -------------------------------------------------------
# Runs filter_gates_for_issue_type in a subshell, capturing stdout and stderr
# separately into FILTER_OUT / FILTER_ERR.
run_filter() {
    local issue_type="$1" csv="$2"
    local errfile
    errfile="$(mktemp)"
    FILTER_OUT=$(bash -c "
        source '$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh'
        filter_gates_for_issue_type '$issue_type' '$csv'
    " 2>"$errfile")
    FILTER_ERR=$(cat "$errfile")
    rm -f "$errfile"
}

test_unit_filter() {
    echo "=== Test: unit — filter_gates_for_issue_type ==="

    run_filter manual_verification "risk_evaluated"
    assert_eq "mv+risk_evaluated: stdout empty" "" "$FILTER_OUT"
    assert_eq "mv+risk_evaluated: stripped notice" "STRIPPED:risk_evaluated" "$FILTER_ERR"

    run_filter manual_verification "risk_evaluated,build_verified"
    assert_eq "mv mixed: reachable kept" "build_verified" "$FILTER_OUT"
    assert_eq "mv mixed: unreachable stripped" "STRIPPED:risk_evaluated" "$FILTER_ERR"

    run_filter manual_verification "build_verified"
    assert_eq "mv reachable-only: kept" "build_verified" "$FILTER_OUT"
    assert_eq "mv reachable-only: no stderr" "" "$FILTER_ERR"

    run_filter manual_verification "tests_pass,lint"
    assert_eq "mv step9 set: kept verbatim" "tests_pass,lint" "$FILTER_OUT"
    assert_eq "mv step9 set: no stderr" "" "$FILTER_ERR"

    # Allowlist semantics: planning/review gates (and any unknown/future gate)
    # are stripped — a new planning gate can never sneak through.
    run_filter manual_verification "review_approved,docs_updated,plan_approved,some_future_gate"
    assert_eq "mv planning gates: stdout empty" "" "$FILTER_OUT"
    assert_eq "mv planning gates: all stripped" \
        "STRIPPED:review_approved,docs_updated,plan_approved,some_future_gate" "$FILTER_ERR"

    # Negative control: every other issue_type passes through unchanged.
    run_filter bug "risk_evaluated"
    assert_eq "bug: gates untouched" "risk_evaluated" "$FILTER_OUT"
    assert_eq "bug: no stderr" "" "$FILTER_ERR"

    run_filter feature "risk_evaluated,plan_approved"
    assert_eq "feature: gates untouched" "risk_evaluated,plan_approved" "$FILTER_OUT"
    assert_eq "feature: no stderr" "" "$FILTER_ERR"

    run_filter manual_verification ""
    assert_eq "mv empty input: empty output" "" "$FILTER_OUT"
    assert_eq "mv empty input: no stderr" "" "$FILTER_ERR"
}

# --- Allowlist ⊆ registry guard ---------------------------------------------
# Every gate in MANUAL_VERIFICATION_REACHABLE_GATES must exist as a key in the
# canonical gate registry (.aitask-scripts/gates_reference.yaml — the shipped
# source of truth, field-identical to aitasks/metadata/gates.yaml per
# test_gates_reference_drift.sh). A registry rename not mirrored in the
# allowlist would silently strip a reachable gate; fail loudly instead.
test_allowlist_subset_of_registry() {
    echo "=== Test: allowlist ⊆ gate registry ==="

    local registry="$PROJECT_DIR/.aitask-scripts/gates_reference.yaml"
    TOTAL=$((TOTAL + 1))
    if [[ ! -f "$registry" ]]; then
        FAIL=$((FAIL + 1))
        echo "FAIL: canonical registry not found: $registry"
        return
    fi
    PASS=$((PASS + 1))

    local allowlist
    allowlist=$(bash -c "
        source '$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh'
        printf '%s' \"\$MANUAL_VERIFICATION_REACHABLE_GATES\"
    ")

    TOTAL=$((TOTAL + 1))
    if [[ -z "$allowlist" ]]; then
        FAIL=$((FAIL + 1))
        echo "FAIL: MANUAL_VERIFICATION_REACHABLE_GATES is empty/undefined"
        return
    fi
    PASS=$((PASS + 1))

    local g
    for g in $allowlist; do
        TOTAL=$((TOTAL + 1))
        # Registry gate keys are 2-space-indented `  <name>:` lines.
        if grep -qE "^  ${g}:" "$registry"; then
            PASS=$((PASS + 1))
        else
            FAIL=$((FAIL + 1))
            echo "FAIL: allowlisted gate '$g' not found in registry $registry"
        fi
    done
}

# --- Injection-equivalence pin ----------------------------------------------
# The profile-driven injection path is: seed fast profile default_gates →
# task-creation-batch.md Jinja `--gates "{{ profile.default_gates | join(',') }}"`
# → rendered command `--gates "risk_evaluated"` → aitask_create.sh sink. The
# integration tests below feed the sink that exact CLI shape; these asserts
# pin the equivalence so a template/profile shape change flags a re-check.
test_injection_equivalence_pin() {
    echo "=== Test: injection-equivalence pin (profile → template → sink) ==="

    local template="$PROJECT_DIR/.claude/skills/task-workflow/task-creation-batch.md"
    local template_body
    template_body=$(cat "$template")
    assert_contains "authoring template injects --gates from default_gates" \
        '--gates "{{ profile.default_gates | join('"','"') }}"' "$template_body"

    local seed_profile
    seed_profile=$(cat "$PROJECT_DIR/seed/profiles/fast.yaml")
    assert_contains "seed fast profile declares risk_evaluated default gate" \
        "default_gates: [risk_evaluated]" "$seed_profile"

    # When the fast variant has been rendered locally, assert the final shape.
    local rendered="$PROJECT_DIR/.claude/skills/task-workflow-fast-/task-creation-batch.md"
    if [[ -f "$rendered" ]]; then
        local rendered_body
        rendered_body=$(cat "$rendered")
        assert_contains "rendered fast template emits the sink CLI shape" \
            '--gates "risk_evaluated"' "$rendered_body"
    else
        echo "  (rendered fast variant absent — skipping rendered-shape assert)"
    fi
}

# --- Integration fixture ------------------------------------------------------
# Bare-remote + local-clone pair with the minimal script set aitask_create.sh
# (and aitask_gate.sh for archive-ready) needs. Leaves CWD inside the clone.
setup_project() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    CLEANUP_DIRS+=("$tmpdir")

    local remote_dir="$tmpdir/remote.git"
    git init --bare --quiet "$remote_dir"

    local local_dir="$tmpdir/local"
    git clone --quiet "$remote_dir" "$local_dir" 2>/dev/null

    pushd "$local_dir" > /dev/null
    git config user.email "test@test.com"
    git config user.name "Test"

    mkdir -p aitasks/metadata aiplans/archived
    setup_fake_aitask_repo "$PWD"

    cp "$PROJECT_DIR/.aitask-scripts/aitask_create.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_gate.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/gate_ledger.py" .aitask-scripts/lib/
    chmod +x .aitask-scripts/*.sh

    # Registry for aitask_gate.sh archive-ready.
    cp "$PROJECT_DIR/.aitask-scripts/gates_reference.yaml" aitasks/metadata/gates.yaml

    # Stub `./ait git` as a pass-through to plain git.
    cat > ./ait <<'EOF'
#!/usr/bin/env bash
if [[ "${1:-}" == "git" ]]; then
    shift
    exec git "$@"
fi
exit 0
EOF
    chmod +x ./ait

    printf 'bug\nchore\ndocumentation\nenhancement\nfeature\nperformance\nrefactor\nstyle\ntest\nmanual_verification\n' \
        > aitasks/metadata/task_types.txt
    : > aitasks/metadata/labels.txt

    git add -A
    git commit -m "Initial setup" --quiet
    git push --quiet 2>/dev/null || true

    ./.aitask-scripts/aitask_claim_id.sh --init > /dev/null 2>&1
}

teardown() {
    popd > /dev/null 2>&1 || true
}

# Locate the created task file path from `Created: <path>` output.
created_path_from_output() {
    echo "$1" | sed -n 's/^Created: \(.*\)$/\1/p' | tail -1
}

# Read the frontmatter `gates:` line (empty when absent).
gates_line_of() {
    awk '/^---$/{n++; next} n==1 && /^gates:/' "$1"
}

test_integration_mv_strip() {
    echo "=== Test: integration — mv task strips risk_evaluated end-to-end ==="
    setup_project

    local out rc
    out=$(bash .aitask-scripts/aitask_create.sh --batch --commit \
            --name "mv_gate_strip" \
            --priority medium --effort low \
            --type manual_verification \
            --labels "" \
            --gates "risk_evaluated" \
            --desc "MV task that must not carry risk_evaluated" 2>&1) && rc=0 || rc=$?

    assert_eq "create exits 0" "0" "$rc"
    assert_contains "strip notice emitted" "dropped unreachable gate(s): risk_evaluated" "$out"

    local new_path
    new_path=$(created_path_from_output "$out")
    TOTAL=$((TOTAL + 1))
    if [[ -z "$new_path" || ! -f "$new_path" ]]; then
        FAIL=$((FAIL + 1))
        echo "FAIL: created task path not resolvable"
        echo "  out: $out"
        teardown
        return
    fi
    PASS=$((PASS + 1))

    assert_eq "no gates line in created file" "" "$(gates_line_of "$new_path")"

    # The whole point: the task is archivable — no declared gates.
    local task_id
    task_id=$(basename "$new_path" | grep -oE '^t[0-9]+' | sed 's/t//')
    local ready
    ready=$(./.aitask-scripts/aitask_gate.sh archive-ready "$task_id" 2>/dev/null)
    assert_eq "archive-ready reports NO_GATES" "NO_GATES" "$ready"

    teardown
}

test_integration_mv_mixed_keep() {
    echo "=== Test: integration — mv task keeps reachable gate from mixed set ==="
    setup_project

    local out rc
    out=$(bash .aitask-scripts/aitask_create.sh --batch --commit \
            --name "mv_gate_mixed" \
            --priority medium --effort low \
            --type manual_verification \
            --labels "" \
            --gates "risk_evaluated,build_verified" \
            --desc "MV task keeping only reachable gates" 2>&1) && rc=0 || rc=$?

    assert_eq "create exits 0" "0" "$rc"

    local new_path
    new_path=$(created_path_from_output "$out")
    TOTAL=$((TOTAL + 1))
    if [[ -z "$new_path" || ! -f "$new_path" ]]; then
        FAIL=$((FAIL + 1))
        echo "FAIL: created task path not resolvable"
        teardown
        return
    fi
    PASS=$((PASS + 1))

    assert_eq "only build_verified declared" "gates: [build_verified]" "$(gates_line_of "$new_path")"

    teardown
}

test_integration_other_type_negative_control() {
    echo "=== Test: integration — bug task keeps risk_evaluated (negative control) ==="
    setup_project

    local out rc
    out=$(bash .aitask-scripts/aitask_create.sh --batch --commit \
            --name "bug_gate_kept" \
            --priority medium --effort low \
            --type bug \
            --labels "" \
            --gates "risk_evaluated" \
            --desc "Non-mv task must keep its declared gates" 2>&1) && rc=0 || rc=$?

    assert_eq "create exits 0" "0" "$rc"
    assert_not_contains "no strip notice for bug type" "dropped unreachable gate" "$out"

    local new_path
    new_path=$(created_path_from_output "$out")
    TOTAL=$((TOTAL + 1))
    if [[ -z "$new_path" || ! -f "$new_path" ]]; then
        FAIL=$((FAIL + 1))
        echo "FAIL: created task path not resolvable"
        teardown
        return
    fi
    PASS=$((PASS + 1))

    assert_eq "risk_evaluated declared on bug task" "gates: [risk_evaluated]" "$(gates_line_of "$new_path")"

    teardown
}

test_finalize_draft_strips_gates() {
    echo "=== Test: finalize — hand-written mv draft loses risk_evaluated ==="
    setup_project

    # Hand-write a draft (as a pre-fix or hand-edited draft would look):
    # run_batch_mode's sink filter never saw it, so finalize must enforce.
    mkdir -p aitasks/new
    local draft="aitasks/new/draft_20260101_0000_mv_stale_draft.md"
    cat > "$draft" <<'EOF'
---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: []
gates: [risk_evaluated, build_verified]
draft: true
created_at: 2026-01-01 00:00
updated_at: 2026-01-01 00:00
---

Stale draft carrying an unreachable planning gate.
EOF

    local out rc
    out=$(bash .aitask-scripts/aitask_create.sh --batch --finalize "$draft" 2>&1) && rc=0 || rc=$?

    assert_eq "finalize exits 0" "0" "$rc"
    assert_contains "finalize strip notice emitted" \
        "dropped unreachable gate(s) from finalized draft: risk_evaluated" "$out"

    local new_path
    new_path=$(ls aitasks/t*_mv_stale_draft.md 2>/dev/null | head -1)
    TOTAL=$((TOTAL + 1))
    if [[ -z "$new_path" || ! -f "$new_path" ]]; then
        FAIL=$((FAIL + 1))
        echo "FAIL: finalized task file not found"
        echo "  out: $out"
        teardown
        return
    fi
    PASS=$((PASS + 1))

    assert_eq "finalized file keeps only build_verified" \
        "gates: [build_verified]" "$(gates_line_of "$new_path")"

    teardown
}

test_syntax_check() {
    echo "=== Test: syntax check touched scripts ==="
    local f
    for f in "$PROJECT_DIR/.aitask-scripts/aitask_create.sh" \
             "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"; do
        TOTAL=$((TOTAL + 1))
        if bash -n "$f"; then
            PASS=$((PASS + 1))
        else
            FAIL=$((FAIL + 1))
            echo "FAIL: syntax check $f"
        fi
    done
}

teardown_all() {
    local d
    for d in "${CLEANUP_DIRS[@]}"; do
        [[ -d "$d" ]] && rm -rf "$d"
    done
}
trap teardown_all EXIT

test_unit_filter
test_allowlist_subset_of_registry
test_injection_equivalence_pin
test_integration_mv_strip
test_integration_mv_mixed_keep
test_integration_other_type_negative_control
test_finalize_draft_strips_gates
test_syntax_check

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
