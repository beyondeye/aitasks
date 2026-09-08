#!/usr/bin/env bash
# test_verification_followup.sh - Tests for aitask_verification_followup.sh (t583_6)
#
# Covers the follow-up bug-task creation flow delivered by t583_3:
#   1. Happy path: single `verifies:` entry auto-resolves origin, produces
#      FOLLOWUP_CREATED on stdout, writes a bug task with the failing item
#      text + commit/file context.
#   2. Ambiguous origin: 2+ `verifies:` entries without --origin -> exit 2
#      and ORIGIN_AMBIGUOUS:<csv> on stdout (no mutation).
#   3. Explicit --origin resolves ambiguity.
#   4. Back-reference appended to an existing `## Final Implementation Notes`
#      section in the origin's archived plan.
#   5. Back-reference creates the section when the archived plan lacks it.
#
# Run: bash tests/test_verification_followup.sh

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

# setup_project creates a bare-remote + local-clone pair, copies the minimal
# script set needed by aitask_verification_followup.sh (and its transitive
# deps), initializes the atomic id counter, and leaves CWD inside the local
# clone via pushd.
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

    # Minimum script set: followup helper + parser + create/update chain
    # (create.sh --commit calls claim_id + fold_mark transitively).
    cp "$PROJECT_DIR/.aitask-scripts/aitask_verification_followup.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_verification_parse.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_verification_parse.py" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_create.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_fold_mark.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/
    chmod +x .aitask-scripts/*.sh

    # Stub `./ait git` as a pass-through to plain git. Without it the wrapper's
    # Step-10 back-reference commit is silently a no-op (both lines end in
    # `|| true`), so the commit path had NO coverage at all — the shape t1728's
    # controls exist to exercise (same stub as
    # tests/test_create_manual_verification.sh).
    cat > ./ait <<'AITEOF'
#!/usr/bin/env bash
if [[ "${1:-}" == "git" ]]; then
    shift
    exec git "$@"
fi
exit 0
AITEOF
    chmod +x ./ait

    printf 'bug\nchore\ndocumentation\nenhancement\nfeature\nperformance\nrefactor\nstyle\ntest\nmanual_verification\n' \
        > aitasks/metadata/task_types.txt
    : > aitasks/metadata/labels.txt

    git add -A
    git commit -m "Initial setup" --quiet
    git push --quiet 2>/dev/null || true

    # Initialize the atomic id counter branch so aitask_create.sh --commit works.
    ./.aitask-scripts/aitask_claim_id.sh --init > /dev/null 2>&1
}

teardown() {
    popd > /dev/null 2>&1 || true
}

# seed_origin_commit <origin_id> creates a feature task, commits a dummy source
# file with the conventional "(tN)" suffix, and pushes. Returns via stdout the
# short commit hash.
seed_origin_commit() {
    local origin="$1"
    mkdir -p src
    printf 'placeholder for t%s\n' "$origin" > "src/origin_${origin}.py"
    git add "src/origin_${origin}.py" > /dev/null
    git commit -m "feature: seed origin (t${origin})" --quiet > /dev/null
    git rev-parse --short HEAD
}

# write_mv_task <path> <verifies_list_literal> [item_line] writes a
# manual-verification task file with one checklist item. item_line defaults to
# a plain unchecked item; pass it to exercise annotated / em-dash prose.
write_mv_task() {
    local path="$1" verifies_literal="$2"
    local item_line="${3:-- [ ] Button opens the modal cleanly}"
    mkdir -p "$(dirname "$path")"
    {
        printf '%s\n' "---"
        printf '%s\n' "priority: medium"
        printf '%s\n' "effort: low"
        printf '%s\n' "depends: []"
        printf '%s\n' "issue_type: manual_verification"
        printf '%s\n' "status: Ready"
        printf '%s\n' "labels: []"
        printf '%s\n' "verifies: ${verifies_literal}"
        printf '%s\n' "created_at: 2026-01-01 10:00"
        printf '%s\n' "updated_at: 2026-01-01 10:00"
        printf '%s\n' "---"
        printf '\n## Verification Checklist\n\n'
        printf '%s\n' "$item_line"
    } > "$path"
}

# Locate the bug task filepath emitted on the FOLLOWUP_CREATED line.
followup_path_from_output() {
    echo "$1" | sed -n 's/^FOLLOWUP_CREATED:[^:]*:\(.*\)$/\1/p' | tail -1
}

followup_id_from_output() {
    echo "$1" | sed -n 's/^FOLLOWUP_CREATED:\([^:]*\):.*$/\1/p' | tail -1
}

test_happy_path_single_verifies() {
    echo "=== Test: happy path — single verifies auto-resolves origin ==="
    setup_project

    local hash
    hash=$(seed_origin_commit 42)
    write_mv_task aitasks/t99_manual.md "[42]"
    git add -A && git commit -m "seed mv task" --quiet

    local out rc
    out=$(bash .aitask-scripts/aitask_verification_followup.sh --from 99 --item 1 2>&1) && rc=0 || rc=$?
    assert_eq "happy path exit 0" "0" "$rc"
    assert_contains "FOLLOWUP_CREATED emitted" "FOLLOWUP_CREATED:" "$out"

    local new_path
    new_path=$(followup_path_from_output "$out")
    if [[ -z "$new_path" || ! -f "$new_path" ]]; then
        FAIL=$((FAIL + 1))
        TOTAL=$((TOTAL + 1))
        echo "FAIL: bug task path not resolvable or file missing"
        echo "  out: $out"
    else
        TOTAL=$((TOTAL + 1)); PASS=$((PASS + 1))
        local body
        body=$(cat "$new_path")
        assert_contains "bug task includes failing item text" "Button opens the modal cleanly" "$body"
        assert_contains "bug task references origin commit" "$hash" "$body"
        assert_contains "bug task references touched file" "src/origin_42.py" "$body"
        assert_contains "bug task depends on origin" "depends: [42]" "$body"
        assert_contains "bug task type is bug" "issue_type: bug" "$body"
    fi

    teardown
}

test_em_dash_item_text_preserved() {
    echo "=== Test: item prose with an em-dash survives into the bug task (t1208) ==="
    setup_project

    seed_origin_commit 42 > /dev/null
    # Prose em-dash + a prior FAIL annotation: the description must keep the
    # whole sentence and drop only the annotation.
    write_mv_task aitasks/t99_manual.md "[42]" \
        '- [fail] Advanced is the recommended tier — a user must never infer it from the output. — FAIL 2026-01-01 10:00 auto: regressed'
    git add -A && git commit -m "seed mv task" --quiet

    local out rc
    out=$(bash .aitask-scripts/aitask_verification_followup.sh --from 99 --item 1 2>&1) && rc=0 || rc=$?
    assert_eq "em-dash case exit 0" "0" "$rc"

    local new_path
    new_path=$(followup_path_from_output "$out")
    if [[ -z "$new_path" || ! -f "$new_path" ]]; then
        FAIL=$((FAIL + 1))
        TOTAL=$((TOTAL + 1))
        echo "FAIL: bug task path not resolvable or file missing"
        echo "  out: $out"
    else
        local body
        body=$(cat "$new_path")
        assert_contains "prose before the em-dash kept" \
            "Advanced is the recommended tier" "$body"
        assert_contains "prose AFTER the em-dash kept" \
            "a user must never infer it from the output." "$body"
        TOTAL=$((TOTAL + 1))
        if grep -q 'FAIL 2026-01-01 10:00' "$new_path"; then
            FAIL=$((FAIL + 1))
            echo "FAIL: annotation leaked into the bug task description"
        else
            PASS=$((PASS + 1))
        fi
    fi

    teardown
}

test_ambiguous_origin() {
    echo "=== Test: ambiguous origin — 2+ verifies without --origin ==="
    setup_project

    seed_origin_commit 42 > /dev/null
    seed_origin_commit 43 > /dev/null
    write_mv_task aitasks/t99_manual.md "[42, 43]"
    git add -A && git commit -m "seed mv task" --quiet

    local out rc
    out=$(bash .aitask-scripts/aitask_verification_followup.sh --from 99 --item 1 2>&1) && rc=0 || rc=$?
    assert_eq "ambiguous origin exits 2" "2" "$rc"
    assert_contains "ORIGIN_AMBIGUOUS emitted" "ORIGIN_AMBIGUOUS:" "$out"
    assert_contains "csv contains 42" "42" "$out"
    assert_contains "csv contains 43" "43" "$out"
    assert_not_contains "no FOLLOWUP_CREATED on ambiguous" "FOLLOWUP_CREATED:" "$out"

    teardown
}

test_explicit_origin_resolves_ambiguity() {
    echo "=== Test: explicit --origin resolves ambiguity ==="
    setup_project

    local hash
    hash=$(seed_origin_commit 42)
    seed_origin_commit 43 > /dev/null
    write_mv_task aitasks/t99_manual.md "[42, 43]"
    git add -A && git commit -m "seed mv task" --quiet

    local out rc
    out=$(bash .aitask-scripts/aitask_verification_followup.sh --from 99 --item 1 --origin 42 2>&1) && rc=0 || rc=$?
    assert_eq "explicit origin exits 0" "0" "$rc"
    assert_contains "FOLLOWUP_CREATED emitted with --origin" "FOLLOWUP_CREATED:" "$out"

    local new_path
    new_path=$(followup_path_from_output "$out")
    if [[ -n "$new_path" && -f "$new_path" ]]; then
        local body
        body=$(cat "$new_path")
        assert_contains "bug task depends on chosen origin (42)" "depends: [42]" "$body"
        assert_not_contains "bug task does not reference other origin (43)" "depends: [43]" "$body"
        assert_contains "chosen origin commit included" "$hash" "$body"
    else
        TOTAL=$((TOTAL + 1)); FAIL=$((FAIL + 1))
        echo "FAIL: bug task path not resolvable for explicit-origin case"
    fi

    teardown
}

test_backref_appended_to_existing_notes() {
    echo "=== Test: back-reference appended to existing Final Implementation Notes ==="
    setup_project

    seed_origin_commit 42 > /dev/null
    write_mv_task aitasks/t99_manual.md "[42]"

    # Archived plan with an existing Final Implementation Notes section.
    mkdir -p aiplans/archived
    cat > aiplans/archived/p42_origin.md <<'EOF'
---
Task: t42_origin.md
---

# Plan: origin

## Final Implementation Notes

- **Actual work done:** initial implementation
EOF
    git add -A && git commit -m "seed mv task + archived plan" --quiet

    local out rc
    out=$(bash .aitask-scripts/aitask_verification_followup.sh --from 99 --item 1 2>&1) && rc=0 || rc=$?
    assert_eq "backref path exit 0" "0" "$rc"

    local new_id
    new_id=$(followup_id_from_output "$out")
    local plan_content
    plan_content=$(cat aiplans/archived/p42_origin.md)
    assert_contains "plan mentions Manual-verification failure" "Manual-verification failure" "$plan_content"
    assert_contains "plan references new follow-up task id" "t${new_id}" "$plan_content"
    assert_contains "existing notes line preserved" "initial implementation" "$plan_content"

    # Exactly one "## Final Implementation Notes" heading — the helper should
    # have appended under the existing section, not duplicated it.
    local heading_count
    heading_count=$(grep -c '^## Final Implementation Notes' aiplans/archived/p42_origin.md || true)
    assert_eq "single Final Implementation Notes section" "1" "$heading_count"

    teardown
}

test_backref_creates_section_when_missing() {
    echo "=== Test: back-reference creates section when archived plan lacks it ==="
    setup_project

    seed_origin_commit 42 > /dev/null
    write_mv_task aitasks/t99_manual.md "[42]"

    # Archived plan WITHOUT a Final Implementation Notes section.
    mkdir -p aiplans/archived
    cat > aiplans/archived/p42_origin.md <<'EOF'
---
Task: t42_origin.md
---

# Plan: origin

## Overview

Something else.
EOF
    git add -A && git commit -m "seed mv task + archived plan (no notes)" --quiet

    local out rc
    out=$(bash .aitask-scripts/aitask_verification_followup.sh --from 99 --item 1 2>&1) && rc=0 || rc=$?
    assert_eq "create-section path exit 0" "0" "$rc"

    local new_id
    new_id=$(followup_id_from_output "$out")
    local plan_content
    plan_content=$(cat aiplans/archived/p42_origin.md)
    assert_contains "Final Implementation Notes section created" "## Final Implementation Notes" "$plan_content"
    assert_contains "plan references new follow-up task id" "t${new_id}" "$plan_content"
    assert_contains "pre-existing section preserved" "## Overview" "$plan_content"

    teardown
}

test_syntax_check() {
    echo "=== Test: syntax check touched script ==="
    TOTAL=$((TOTAL + 1))
    if bash -n "$PROJECT_DIR/.aitask-scripts/aitask_verification_followup.sh"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: syntax check"
    fi
}

# The Step-10 back-reference commit used to be `./ait git add <plan>` followed
# by a bare `./ait git commit`, which commits the WHOLE index. The origin plan
# lives on the shared task-data branch, so both halves of the hazard are
# reachable here and each gets its own control (t1728).
test_backref_commit_is_scoped() {
    echo "=== Test: the back-reference commit does not swallow concurrent work (t1728) ==="
    setup_project

    seed_origin_commit 42 > /dev/null
    write_mv_task aitasks/t99_manual.md "[42]"
    mkdir -p aiplans/archived
    cat > aiplans/archived/p42_origin.md <<'EOF'
---
Task: t42_origin.md
---

# Plan: origin

## Final Implementation Notes

- **Actual work done:** initial implementation
EOF
    git add -A && git commit -m "seed mv task + archived plan" --quiet

    # A concurrent session's work, staged and not yet committed.
    printf 'concurrent session work\n' > foreign.txt
    git add foreign.txt

    local out rc
    out=$(bash .aitask-scripts/aitask_verification_followup.sh --from 99 --item 1 2>&1) && rc=0 || rc=$?
    assert_eq "wrapper still exits 0" "0" "$rc"

    local committed still_staged
    committed=$(git show --name-only --format= HEAD | tr '\n' ' ')
    still_staged=$(git diff --cached --name-only | tr '\n' ' ')

    assert_contains "the origin plan IS committed" "aiplans/archived/p42_origin.md" "$committed"
    assert_not_contains "the foreign staged file is NOT swallowed" "foreign.txt" "$committed"
    assert_contains "the foreign file is still staged afterwards" "foreign.txt" "$still_staged"

    teardown
}

# The staging half. Unlike the freshly-created task file in
# tests/test_create_manual_verification.sh, the origin plan is a PRE-EXISTING
# shared file, so another session genuinely can hold a staged version of the
# very path this site commits. Verified against real git: `add` + a failing
# `commit -o` leaves the index at the worktree content, while `commit -o` alone
# leaves it untouched — that difference is the whole control.
test_backref_commit_preserves_staged_target() {
    echo "=== Test: the back-reference commit does not clobber a staged version of the origin plan (t1728) ==="
    setup_project

    seed_origin_commit 42 > /dev/null
    write_mv_task aitasks/t99_manual.md "[42]"
    mkdir -p aiplans/archived
    cat > aiplans/archived/p42_origin.md <<'EOF'
---
Task: t42_origin.md
---

# Plan: origin

## Final Implementation Notes

- **Actual work done:** initial implementation
EOF
    git add -A && git commit -m "seed mv task + archived plan" --quiet

    # A concurrent session staged version A of the SAME path. The two versions
    # REPLACE each other rather than accumulating: with an append chain the
    # index would contain both markers whatever happened, and the "survives"
    # assertion could not discriminate.
    cat > aiplans/archived/p42_origin.md <<'EOF'
---
Task: t42_origin.md
---

# Plan: origin

## Final Implementation Notes

- STAGED_BY_OTHER_SESSION
EOF
    git add aiplans/archived/p42_origin.md
    # ...and the worktree has since moved on to version B.
    cat > aiplans/archived/p42_origin.md <<'EOF'
---
Task: t42_origin.md
---

# Plan: origin

## Final Implementation Notes

- OUR_WORKTREE_VERSION
EOF

    # Force ONLY the back-reference commit to fail, through a documented git
    # seam. A blanket `pre-commit` hook is too blunt: it also fails
    # aitask_create.sh's own commit, so the script dies before Step 10 ever runs
    # and this control passes vacuously (observed). `commit-msg` receives the
    # message file, so it can single out the one commit under test.
    mkdir -p .git/hooks
    cat > .git/hooks/commit-msg <<'HOOKEOF'
#!/bin/sh
grep -q "Back-reference manual-verification failure" "$1" && exit 1
exit 0
HOOKEOF
    chmod +x .git/hooks/commit-msg

    bash .aitask-scripts/aitask_verification_followup.sh --from 99 --item 1 >/dev/null 2>&1 || true
    rm -f .git/hooks/commit-msg

    local staged_now
    staged_now=$(git show :aiplans/archived/p42_origin.md 2>/dev/null || echo "<unreadable>")

    assert_contains "the other session's STAGED version of the origin plan survives" \
        "STAGED_BY_OTHER_SESSION" "$staged_now"
    assert_not_contains "our worktree version did not replace it in the index" \
        "OUR_WORKTREE_VERSION" "$staged_now"

    teardown
}

# The absorb, and the composed EXIT trap (t1728 post-phase control).
#
# Two things this script must keep doing once the commit goes through the seam,
# which returns a non-zero status for outcomes the old `|| true` swallowed
# wholesale. This script runs under `set -euo pipefail`, so an unabsorbed status
# would kill it AFTER the plan file was already appended to:
#   1. the statements after the commit still run — witnessed by the stdout
#      contract (FOLLOWUP_CREATED:), which is emitted further down;
#   2. the EXIT trap still removes the temp file it owned. The seam's cleanup
#      has to be COMPOSED into that trap, and a naive `trap ... EXIT` would
#      replace it — leaking `followup_*.md` on every run.
# The commit is forced to FAIL here, which is the status most likely to escape.
test_backref_commit_failure_is_absorbed() {
    echo "=== Test: a failed back-reference commit neither aborts the script nor leaks its temp file (t1728) ==="
    setup_project

    seed_origin_commit 42 > /dev/null
    write_mv_task aitasks/t99_manual.md "[42]"
    mkdir -p aiplans/archived
    cat > aiplans/archived/p42_origin.md <<'EOF'
---
Task: t42_origin.md
---

# Plan: origin

## Final Implementation Notes

- **Actual work done:** initial implementation
EOF
    git add -A && git commit -m "seed mv task + archived plan" --quiet

    # Scoped to the back-reference commit alone — see the note in
    # test_backref_commit_preserves_staged_target.
    mkdir -p .git/hooks
    cat > .git/hooks/commit-msg <<'HOOKEOF'
#!/bin/sh
grep -q "Back-reference manual-verification failure" "$1" && exit 1
exit 0
HOOKEOF
    chmod +x .git/hooks/commit-msg

    # A private TMPDIR makes the leak check exact rather than a scan of /tmp.
    local privtmp
    privtmp="$(mktemp -d)"
    CLEANUP_DIRS+=("$privtmp")

    local out rc
    out=$(TMPDIR="$privtmp" bash .aitask-scripts/aitask_verification_followup.sh \
            --from 99 --item 1 2>&1) && rc=0 || rc=$?
    rm -f .git/hooks/commit-msg

    assert_eq "a failed back-reference commit does not abort the script" "0" "$rc"
    assert_contains "the statements after the commit still run" "FOLLOWUP_CREATED:" "$out"

    # The append itself must still have landed — the commit is best-effort, the
    # edit is not.
    assert_contains "the back-reference is still written to the plan" \
        "Manual-verification failure" "$(cat aiplans/archived/p42_origin.md)"

    local leaked
    leaked=$(find "$privtmp" -maxdepth 1 -name 'followup_*.md' | wc -l | tr -d ' ')
    assert_eq "the composed EXIT trap still removes the temp file" "0" "$leaked"

    teardown
}

teardown_all() {
    local d
    for d in "${CLEANUP_DIRS[@]}"; do
        [[ -d "$d" ]] && rm -rf "$d"
    done
}
trap teardown_all EXIT

test_happy_path_single_verifies
test_em_dash_item_text_preserved
test_ambiguous_origin
test_explicit_origin_resolves_ambiguity
test_backref_appended_to_existing_notes
test_backref_creates_section_when_missing
test_backref_commit_is_scoped
test_backref_commit_preserves_staged_target
test_backref_commit_failure_is_absorbed
test_syntax_check

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
