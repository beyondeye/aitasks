#!/usr/bin/env bash
# test_create_id_claim_abort.sh - a failed task-ID claim ABORTS the create (t1755).
#
# Run: bash tests/test_create_id_claim_abort.sh
#
# Before this, `ait create` could write aitasks/t_<name>.md -- a task file
# carrying NO id at all -- COMMIT it, and exit 0. Two independent defects:
#
#   (1) claim_parent_id_once() allocated its stderr capture with an unchecked
#       `mktemp`. With TMPDIR missing/full/read-only, $claim_stderr stayed empty
#       and `2>"$claim_stderr"` was an ambiguous redirect, so the claim could not
#       run; the user saw shell noise plus a misleading "unknown error".
#
#   (2) The failure status never reached the caller. MEASURED root cause: bash
#       DROPS errexit inside every command-substitution subshell --
#
#         $ set -e; echo "$SHELLOPTS"; echo "$(echo "$SHELLOPTS")"
#         braceexpand:errexit:hashall:interactive-comments
#         braceexpand:hashall:interactive-comments      # <- no errexit
#
#       -- so inside `claimed_id=$(claim_unique_parent_id …)` the inner
#       `$(claim_parent_id_once …)` failing did not abort. die() exited only its
#       own subshell, the retry loop fell through to active_parent_task_exists ""
#       (false, no t_*.md exists), and the function echoed an EMPTY id and
#       returned 0. That is why the error printed once, not five times.
#
# A third defect was found while fixing these: add_label_to_file() writes
# labels.txt to disk, and in run_batch_mode it ran BEFORE the claim -- so an
# aborted `--labels` create left a task-less entry in the shared vocabulary,
# violating the "nothing is written" guarantee. Fixed by hoisting the claim above
# the registration (NOT by rolling the file back: a wholesale restore would
# clobber a concurrent session's append, the t1662 hazard).
#
# --- What each row discriminates (MEASURED by mutation, not reasoned) ---------
# Note the task's own text claims "fixing (1) alone would close this
# reproduction". That is FALSE under the abort route taken here: with only (1)
# fixed, the new die() is still invisible to the caller, so the id-less file
# still appears. Row 1's exit/artifact assertions therefore do NOT discriminate
# the (1) half at all -- only its stderr-MESSAGE assertions do. Hence:
#
# Every row below was MEASURED by applying the mutation and re-running this file
# (29 assertions total); none is reasoned. Correct the TABLE if a future run
# disagrees -- never the claim.
#
#   mutation                                   | failing assertions
#   -------------------------------------------|--------------------------------
#   revert only the mktemp check (fix 1)        |  3 — row 1's three MESSAGE
#                                              |     assertions, and nothing else
#   revert only the status propagation (fix 2)  | 14 — rows 1, 3, 4
#   revert only the claim hoist (fix 3)         |  5 — rows 1 and 3, labels.txt
#                                              |     and "worktree unchanged"
#   revert all three                            | 17 — rows 1, 3, 4
#
# Two things that table makes visible and prose would not:
#
#  * fix 1 is pinned by THREE assertions and no others. Reverting it leaves every
#    exit/artifact assertion green, because fix 2 still converts the (now
#    misleading) die into a real abort. Deleting those three message assertions
#    as "cosmetic" would leave fix 1 completely uncovered.
#  * fix 2's blast radius is a superset of fix 3's: with no abort at all the
#    create runs to completion, so the labels.txt assertions fail there too. That
#    is why fix 3 needs its own mutation to be shown as independently pinned.
#
# --- Negative control ---------------------------------------------------------
# Row 2 runs the same create with a usable TMPDIR and a working counter, and
# asserts it SUCCEEDS. It controls two things: that the forced failures in rows
# 1/3/4 are the injection and not a broken fixture, and -- via its POSITIVE
# labels.txt assertion -- that row 1's and row 3's negative labels.txt assertions
# are discriminating rather than vacuously true because the label path never ran.
#
# Every forced-failure row snapshots `git rev-parse HEAD` AND
# `git status --porcelain` around the create. The no-commit guarantee is per CALL
# SITE, and finalize_draft() and run_batch_mode() are two distinct
# task_git_commit_scoped() sites -- a row checking only the artifact would let a
# regression at the other site commit silently.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

cleanup_all() {
    local d
    for d in "${CLEANUP_DIRS[@]}"; do
        [[ -n "$d" && -d "$d" ]] && rm -rf "$d"
    done
    return 0
}
trap cleanup_all EXIT

assert_true() {
    local desc="$1" cond_rc="$2"
    TOTAL=$((TOTAL + 1))
    if [[ "$cond_rc" == "0" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc"
    fi
}

# assert_no_idless_task <desc> — no aitasks/t_*.md anywhere. The glob is the
# whole point of the task, so it gets its own helper rather than being inlined.
assert_no_idless_task() {
    local desc="$1"
    TOTAL=$((TOTAL + 1))
    local found
    found=$(find aitasks -maxdepth 2 -name 't_*.md' 2>/dev/null | head -5)
    if [[ -z "$found" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc — found id-less task file(s): $found"
    fi
}

# --- Project setup (mirrors tests/test_create_silent_stdout.sh:setup_project) ---
setup_project() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    CLEANUP_DIRS+=("$tmpdir")

    local remote_dir="$tmpdir/remote.git"
    git init --bare --quiet "$remote_dir"

    local local_dir="$tmpdir/local"
    git clone --quiet "$remote_dir" "$local_dir"

    pushd "$local_dir" > /dev/null
    git config user.email "test@test.com"
    git config user.name "Test"
    git config commit.gpgsign false

    mkdir -p aitasks/archived aitasks/metadata aitasks/new
    setup_fake_aitask_repo "$PWD"

    cp "$PROJECT_DIR/.aitask-scripts/aitask_create.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_ls.sh" .aitask-scripts/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true
    chmod +x .aitask-scripts/*.sh 2>/dev/null || true

    printf 'bug\nchore\ndocumentation\nenhancement\nfeature\nperformance\nrefactor\nstyle\ntest\n' \
        > aitasks/metadata/task_types.txt
    printf 'existing_label\n' > aitasks/metadata/labels.txt

    echo "aitasks/new/" > .gitignore

    git add -A
    git commit -m "Initial setup" --quiet
    git push --quiet 2>/dev/null

    ./.aitask-scripts/aitask_claim_id.sh --init >/dev/null 2>&1
}

# Replace the counter with a stub that FAILS the claim but still answers --peek.
# This is the documented seam (tests/test_create_silent_stdout.sh uses the same
# file for its sequence stub) and it is the forced failure that is NOT mktemp --
# the row that pins the status-propagation half on its own.
install_failing_claim_stub() {
    cat > .aitask-scripts/aitask_claim_id.sh <<'EOF'
#!/usr/bin/env bash
if [[ "${1:-}" == "--peek" ]]; then echo 1; exit 0; fi
echo "stub: counter unavailable" >&2
exit 3
EOF
    chmod +x .aitask-scripts/aitask_claim_id.sh
}

teardown() {
    popd > /dev/null 2>&1 || true
}

peek_counter() {
    ./.aitask-scripts/aitask_claim_id.sh --peek 2>/dev/null | tail -1
}

# --- Test 1: forced failure — unusable TMPDIR ------------------------------
test_mktemp_failure_aborts() {
    echo "=== Test 1: unusable TMPDIR aborts the create ==="
    setup_project

    local head_before status_before peek_before labels_before
    head_before="$(git rev-parse HEAD)"
    status_before="$(git status --porcelain)"
    peek_before="$(peek_counter)"
    labels_before="$(cat aitasks/metadata/labels.txt)"

    local out rc=0
    out=$(TMPDIR="$PWD/nope" ./.aitask-scripts/aitask_create.sh --batch --commit \
        --name "tdf" --desc "d" --labels "a_fresh_label" 2>&1) || rc=$?

    assert_exit_nonzero_rc "1: create exits non-zero" "$rc"
    assert_no_idless_task "1: no id-less task file"
    assert_eq "1: HEAD unchanged (no commit)" "$head_before" "$(git rev-parse HEAD)"
    assert_eq "1: worktree unchanged" "$status_before" "$(git status --porcelain)"
    assert_eq "1: id counter did not move" "$peek_before" "$(peek_counter)"

    # The label vocabulary is shared, committed state: an aborted create must not
    # leave a token behind for a task that does not exist.
    assert_eq "1: labels.txt byte-identical" "$labels_before" "$(cat aitasks/metadata/labels.txt)"
    assert_not_contains "1: labels.txt free of the new label" "a_fresh_label" \
        "$(cat aitasks/metadata/labels.txt)"

    # The guard's MESSAGE is part of the guard: these are the only assertions in
    # this row that discriminate the mktemp half (see the header table).
    assert_contains "1: names the real cause" \
        "Cannot allocate a temp file for the ID-claim diagnostic" "$out"
    assert_not_contains "1: no ambiguous-redirect noise" "cat: ''" "$out"
    assert_not_contains "1: no bare shell line error" "aitask_create.sh: line" "$out"

    teardown
}

# --- Test 2: negative control — the same create succeeds -------------------
test_negative_control_succeeds() {
    echo ""
    echo "=== Test 2: negative control — usable TMPDIR, working counter ==="
    setup_project

    local peek_before
    peek_before="$(peek_counter)"

    local out rc=0
    out=$(./.aitask-scripts/aitask_create.sh --batch --commit \
        --name "tdf" --desc "d" --labels "a_fresh_label" 2>&1) || rc=$?

    assert_exit_zero_rc "2: create succeeds" "$rc"
    assert_contains "2: reports the created path" "aitasks/t1_tdf.md" "$out"
    assert_file_exists "2: numbered task file exists" "aitasks/t1_tdf.md"
    assert_no_idless_task "2: no id-less task file"

    TOTAL=$((TOTAL + 1))
    if [[ "$(peek_counter)" != "$peek_before" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: 2: id counter should have advanced (still '$peek_before')"
    fi

    # POSITIVE control for the labels.txt assertions in rows 1 and 3: it proves the
    # label path actually runs on this input, so their negative form is
    # discriminating rather than vacuously true.
    assert_contains "2: label IS registered on success" "a_fresh_label" \
        "$(cat aitasks/metadata/labels.txt)"

    teardown
}

# --- Test 3: forced failure that is NOT mktemp -----------------------------
# The row that stays red if only the mktemp is fixed — it pins defect (2) alone.
test_counter_failure_aborts() {
    echo ""
    echo "=== Test 3: a failing counter (not mktemp) aborts the create ==="
    setup_project
    install_failing_claim_stub

    local head_before status_before labels_before
    head_before="$(git rev-parse HEAD)"
    status_before="$(git status --porcelain)"
    labels_before="$(cat aitasks/metadata/labels.txt)"

    local out rc=0
    out=$(./.aitask-scripts/aitask_create.sh --batch --commit \
        --name "stubfail" --desc "d" --labels "a_fresh_label" 2>&1) || rc=$?

    assert_exit_nonzero_rc "3: create exits non-zero" "$rc"
    assert_no_idless_task "3: no id-less task file"
    assert_eq "3: HEAD unchanged (no commit)" "$head_before" "$(git rev-parse HEAD)"
    assert_eq "3: worktree unchanged" "$status_before" "$(git status --porcelain)"
    assert_eq "3: labels.txt byte-identical" "$labels_before" "$(cat aitasks/metadata/labels.txt)"
    assert_contains "3: reports the counter failure" "Atomic ID counter failed" "$out"

    teardown
}

# --- Test 4: the draft/finalize call site ----------------------------------
# finalize_draft() has its OWN task_git_commit_scoped() call, distinct from
# run_batch_mode()'s — so it needs its own no-commit assertions.
test_finalize_draft_failure_aborts() {
    echo ""
    echo "=== Test 4: a failing counter aborts --finalize, preserving the draft ==="
    setup_project

    # Draft first, with a working counter (drafts claim no id).
    ./.aitask-scripts/aitask_create.sh --batch --name "draftfail" --desc "d" >/dev/null 2>&1

    local draft_path
    draft_path=$(find aitasks/new -name 'draft_*draftfail*.md' | head -1)
    assert_true "4: fixture produced a draft" "$([[ -n "$draft_path" ]] && echo 0 || echo 1)"

    install_failing_claim_stub

    local head_before status_before
    head_before="$(git rev-parse HEAD)"
    status_before="$(git status --porcelain)"

    local out rc=0
    out=$(./.aitask-scripts/aitask_create.sh --batch --finalize "$(basename "$draft_path")" 2>&1) || rc=$?

    assert_exit_nonzero_rc "4: finalize exits non-zero" "$rc"
    assert_no_idless_task "4: no id-less task file"
    assert_eq "4: HEAD unchanged (no commit)" "$head_before" "$(git rev-parse HEAD)"
    assert_eq "4: worktree unchanged" "$status_before" "$(git status --porcelain)"
    assert_file_exists "4: the draft survives the abort" "$draft_path"
    assert_contains "4: names the surviving draft" "Draft left at" "$out"

    teardown
}

test_mktemp_failure_aborts
test_negative_control_succeeds
test_counter_failure_aborts
test_finalize_draft_failure_aborts

echo ""
echo "========================================="
echo "Results: $PASS passed, $FAIL failed (of $TOTAL)"
echo "========================================="
[[ "$FAIL" -eq 0 ]]
