#!/usr/bin/env bash
# test_fold_mark.sh - Tests for aitask_fold_mark.sh
#
# Covers:
#   - --commit-mode fresh: primary folded_tasks updated, folded tasks marked
#     Folded+folded_into, child folded task removed from parent
#     children_to_implement, commit created with expected subject
#   - --commit-mode none: no new commit created
#   - Transitive: folding A (which has folded_tasks: [X, Y]) updates X and Y's
#     folded_into to point at the primary
#   - t1599_2: the commit is path-scoped to the fold's own file set (both
#     swallow mechanisms: the broad `add aitasks/` AND the pathspec-less
#     commit), and --commit-mode amend refuses to rewrite a HEAD that is not
#     this fold's to rewrite (foreign task file, unknown metadata, or already
#     published) -- rolling the fold back rather than leaving it dirty.
#   - t1661: the four per-mutation records (PRIMARY_UPDATED / FOLDED /
#     CHILD_REMOVED / TRANSITIVE) are buffered and reach stdout only when Step 6
#     reaches a TERMINAL SUCCESS -- which includes NO_COMMIT (--commit-mode none
#     and the verified no-op), so a record means "survived Step 6", not
#     "committed". All four flush points (crc=0, crc=2, amend, none) print the
#     full set in emission order ahead of the terminal record; all three Step 6
#     failure exits (guard refusal, fresh-commit failure, amend-commit failure)
#     roll back and print nothing. An abort BEFORE Step 6 also prints nothing.
#   - t1668: the WHOLE RUN is one transaction. The fold's file set is
#     snapshotted before the first mutation and an EXIT trap rolls back on any
#     abort through Step 6 -- so an empty record set now means nothing landed
#     (this file previously PINNED the opposite as a documented residual). The
#     restore is of PRE-FOLD state, not HEAD: working-tree bytes and index
#     entry, every stage, so a caller's dirty/staged primary and an unmerged
#     path both survive an aborted fold. Coverage spans the abort windows --
#     Step 4, inside the Step 5b attach transaction (both a die and a bare
#     non-zero return through with_attach_lock), and Step 6 -- plus
#     argument-parse-time --commit-mode validation.
#   - t1733: the amend guard's HEAD probe FAILS CLOSED. `git show --name-only`
#     prints nothing both when it fails and when HEAD is a merge commit; the
#     pre-fix `|| true` absorbed both into "nothing foreign" and permitted the
#     rewrite (a merge HEAD was measurably rewritten). Three fixtures — merge
#     HEAD, unborn HEAD, and a PATH-shimmed probe failure over an otherwise
#     permitted HEAD — each assert their PRECONDITION before invoking the fold,
#     since "printed nothing" is the symptom the guard keys on and several
#     unrelated fixture accidents produce it.
#
# Partial-commit semantics inherited from t1599_1: `commit -o -- <paths>`
# commits those paths' WORKTREE content and ignores their index entry, and
# leaves every other staged path staged. Verified empirically for --amend too.
#
# Run: bash tests/test_fold_mark.sh

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

# shellcheck source=../.aitask-scripts/lib/terminal_compat.sh
source "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"

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

    mkdir -p aitasks/metadata
    setup_fake_aitask_repo "$PWD"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_fold_mark.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
    chmod +x .aitask-scripts/*.sh

    printf 'bug\nchore\ndocumentation\nenhancement\nfeature\nperformance\nrefactor\nstyle\ntest\n' > aitasks/metadata/task_types.txt
    : > aitasks/metadata/labels.txt

    git add -A
    git commit -m "Initial setup" --quiet
    git push --quiet 2>/dev/null || true

    PROJECT_UNDER_TEST="$local_dir"
}

teardown() {
    popd > /dev/null 2>&1 || true
}

write_task() {
    local path="$1"
    shift
    mkdir -p "$(dirname "$path")"
    {
        printf '%s\n' "---"
        printf '%s\n' "priority: medium"
        printf '%s\n' "effort: low"
        printf '%s\n' "depends: []"
        printf '%s\n' "issue_type: chore"
        printf '%s\n' "status: Ready"
        printf '%s\n' "labels: []"
        for extra in "$@"; do
            printf '%s\n' "$extra"
        done
        printf '%s\n' "created_at: 2026-01-01 10:00"
        printf '%s\n' "updated_at: 2026-01-01 10:00"
        printf '%s\n' "---"
        printf '\nBody\n'
    } > "$path"
}

read_frontmatter_field() {
    local file="$1" field="$2"
    awk -v f="$field" '
        BEGIN { in_fm = 0 }
        $0 == "---" { in_fm = !in_fm; next }
        in_fm && $0 ~ "^" f ":" {
            sub("^" f ":[[:space:]]*", "")
            print
            exit
        }
    ' "$file"
}

test_fresh_mode_full_flow() {
    echo "=== Test: --commit-mode fresh, parent + child folded ==="
    setup_project

    # Primary task
    write_task aitasks/t10_primary.md

    # Two simple parent tasks to fold
    write_task aitasks/t20_a.md
    write_task aitasks/t21_b.md

    # Child task with its own parent (t30), to test child cleanup
    write_task aitasks/t30_orig_parent.md "children_to_implement: [t30_1]"
    write_task aitasks/t30/t30_1_child.md

    git add -A
    git commit -m "Setup test" --quiet

    local output
    output=$(bash .aitask-scripts/aitask_fold_mark.sh \
        --commit-mode fresh 10 20 21 30_1 2>&1)

    assert_contains "primary updated" "PRIMARY_UPDATED:10" "$output"
    assert_contains "t20 folded" "FOLDED:20" "$output"
    assert_contains "t21 folded" "FOLDED:21" "$output"
    assert_contains "t30_1 folded" "FOLDED:30_1" "$output"
    assert_contains "child removed from original parent" "CHILD_REMOVED:30:1" "$output"
    assert_contains "committed" "COMMITTED:" "$output"

    # Primary's folded_tasks contains all three new IDs
    local folded
    folded=$(read_frontmatter_field aitasks/t10_primary.md folded_tasks)
    assert_contains "folded_tasks contains 20" "20" "$folded"
    assert_contains "folded_tasks contains 21" "21" "$folded"
    assert_contains "folded_tasks contains 30_1" "30_1" "$folded"

    # Each folded task has status Folded and folded_into=10
    assert_eq "t20 status=Folded" "Folded" "$(read_frontmatter_field aitasks/t20_a.md status)"
    assert_eq "t20 folded_into=10" "10" "$(read_frontmatter_field aitasks/t20_a.md folded_into)"
    assert_eq "t21 status=Folded" "Folded" "$(read_frontmatter_field aitasks/t21_b.md status)"
    assert_eq "t30_1 status=Folded" "Folded" "$(read_frontmatter_field aitasks/t30/t30_1_child.md status)"

    # t30's children_to_implement no longer references t30_1
    local t30_children
    t30_children=$(read_frontmatter_field aitasks/t30_orig_parent.md children_to_implement)
    if echo "$t30_children" | grep -qF "t30_1"; then
        TOTAL=$((TOTAL + 1))
        FAIL=$((FAIL + 1))
        echo "FAIL: t30_1 should have been removed from parent's children_to_implement (got: $t30_children)"
    else
        TOTAL=$((TOTAL + 1))
        PASS=$((PASS + 1))
    fi

    # A new commit was created with the expected subject
    local subject
    subject=$(git log -1 --pretty=%s)
    assert_contains "commit subject" "ait: Fold tasks into t10" "$subject"
    assert_contains "commit lists merged ids" "merge t20, t21, t30_1" "$subject"

    teardown
}

test_none_mode_no_commit() {
    echo "=== Test: --commit-mode none creates no commit ==="
    setup_project

    write_task aitasks/t10_primary.md
    write_task aitasks/t20_a.md

    git add -A
    git commit -m "Setup test none" --quiet

    local before_hash
    before_hash=$(git rev-parse HEAD)

    local output
    output=$(bash .aitask-scripts/aitask_fold_mark.sh --commit-mode none 10 20 2>&1)
    assert_contains "output says NO_COMMIT" "NO_COMMIT" "$output"

    # t1661: `none` is a terminal SUCCESS — the caller commits the mutations
    # itself — so the buffered records are flushed here too, ahead of NO_COMMIT.
    assert_eq "records flushed ahead of NO_COMMIT" \
        $'PRIMARY_UPDATED:10\nFOLDED:20\nNO_COMMIT' "$output"

    local after_hash
    after_hash=$(git rev-parse HEAD)
    assert_eq "HEAD unchanged" "$before_hash" "$after_hash"

    teardown
}

test_transitive() {
    echo "=== Test: transitive folded tasks ==="
    setup_project

    write_task aitasks/t50_primary.md
    # Task A has folded_tasks: [X, Y]
    write_task aitasks/t60_a.md "folded_tasks: [70, 71]"
    # X and Y already folded into A
    write_task aitasks/t70_x.md "folded_into: 60" "status: Folded"
    write_task aitasks/t71_y.md "folded_into: 60" "status: Folded"

    # Note: write_task sets status: Ready first, then the extras append. The
    # duplicate "status: Folded" later in the file is harmless for YAML parsing
    # as long as the first-seen wins; but to be safe, rewrite X/Y status to
    # Folded directly:
    sed_inplace 's/^status: Ready$/status: Folded/' aitasks/t70_x.md aitasks/t71_y.md

    git add -A
    git commit -m "Setup transitive" --quiet

    local output
    output=$(bash .aitask-scripts/aitask_fold_mark.sh --commit-mode none 50 60 2>&1)

    assert_contains "A folded into primary" "FOLDED:60" "$output"
    assert_contains "transitive 70" "TRANSITIVE:70" "$output"
    assert_contains "transitive 71" "TRANSITIVE:71" "$output"

    # X and Y now point at the new primary
    assert_eq "t70 folded_into=50" "50" "$(read_frontmatter_field aitasks/t70_x.md folded_into)"
    assert_eq "t71 folded_into=50" "50" "$(read_frontmatter_field aitasks/t71_y.md folded_into)"

    # Primary's folded_tasks contains 60, 70, 71
    local folded
    folded=$(read_frontmatter_field aitasks/t50_primary.md folded_tasks)
    assert_contains "primary folded_tasks contains 60" "60" "$folded"
    assert_contains "primary folded_tasks contains 70" "70" "$folded"
    assert_contains "primary folded_tasks contains 71" "71" "$folded"

    teardown
}

# --- t1599_2 helpers ---------------------------------------------------------

# assert_not_in_head <desc> <path>   — path absent from HEAD's file list.
assert_not_in_head() {
    local desc="$1" path="$2" files
    files=$(git show --name-only --pretty=format: HEAD | grep -v '^$' || true)
    TOTAL=$((TOTAL + 1))
    if echo "$files" | grep -qxF -- "$path"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc — '$path' IS in HEAD (files: $(echo "$files" | tr '\n' ' '))"
    else
        PASS=$((PASS + 1))
    fi
}

# assert_in_head <desc> <path>
assert_in_head() {
    local desc="$1" path="$2" files
    files=$(git show --name-only --pretty=format: HEAD | grep -v '^$' || true)
    TOTAL=$((TOTAL + 1))
    if echo "$files" | grep -qxF -- "$path"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc — '$path' NOT in HEAD (files: $(echo "$files" | tr '\n' ' '))"
    fi
}

# assert_status_code <desc> <expected two-char porcelain code> <path>
assert_status_code() {
    local desc="$1" want="$2" path="$3" got
    got=$(git status --porcelain -- "$path" | head -1 | cut -c1-2)
    assert_eq "$desc" "$want" "$got"
}

# The fold set touched by `fold_mark <primary> <folded...>` in these fixtures.
# Used by the three-way no-residue check.
FOLD_PATHS=()

# assert_no_fold_residue <desc-prefix> <before_head>
# A refusal must UNDO the fold, not merely decline to commit it:
#   1. HEAD unchanged, 2. index clean, 3. worktree clean — AND the frontmatter
# values actually restored. (3) alone is vacuous: it would also hold if the
# guard had refused before any mutation, and the mutations demonstrably run
# first, so assert the restored VALUES, not just the absence of a diff.
assert_no_fold_residue() {
    local desc="$1" before="$2" p
    assert_eq "$desc: HEAD unchanged" "$before" "$(git rev-parse HEAD)"
    for p in "${FOLD_PATHS[@]}"; do
        assert_eq "$desc: no residue on $p" "" "$(git status --porcelain -- "$p")"
    done
}

# --- t1661 helpers -----------------------------------------------------------

# _run_fold_split <args...> — run fold_mark capturing stdout and stderr
# SEPARATELY into FOLD_OUT / FOLD_ERR, with the exit status in FOLD_RC.
#
# The t1599_2 refusal tests above use `2>&1`, which is fine for asserting that
# a message appeared but useless here: a merged stream cannot tell a leaked
# progress record from the refusal text that is supposed to be the only output.
# Every silence assertion below needs the split.
FOLD_OUT=""; FOLD_ERR=""; FOLD_RC=0
_run_fold_split() {
    local errfile
    errfile="$(mktemp)"
    FOLD_RC=0
    FOLD_OUT="$(bash .aitask-scripts/aitask_fold_mark.sh "$@" 2>"$errfile")" || FOLD_RC=$?
    FOLD_ERR="$(cat "$errfile")"
    rm -f "$errfile"
}

# _install_failing_pre_commit_hook — make `git commit` (and `--amend`) fail.
#
# This is the only way to reach the two POST-staging failure exits: the amend
# guard refuses before staging, so it exercises a different path. Neither
# commit site passes --no-verify (task_utils.sh's task_git_commit_scoped, and
# the amend in aitask_fold_mark.sh), the scaffold sets no core.hooksPath, and
# task_git is plain `git` in $PWD in these fixtures — so a failing pre-commit
# hook fails the commit itself. Git releases the index lock on hook failure, so
# _fold_rollback still works and the restoration half stays assertable.
_install_failing_pre_commit_hook() {
    local hook=".git/hooks/pre-commit"
    mkdir -p "$(dirname "$hook")"
    printf '#!/bin/sh\nexit 1\n' > "$hook"
    chmod +x "$hook"
}

# assert_no_records <desc> <output> — none of the four per-mutation records
# leaked. Named individually rather than as one regex so a failure says which.
assert_no_records() {
    local desc="$1" out="$2" r
    for r in "PRIMARY_UPDATED:" "FOLDED:" "CHILD_REMOVED:" "TRANSITIVE:"; do
        assert_not_contains "$desc: no $r record" "$r" "$out"
    done
}

test_fresh_dirty_bystander_not_swept() {
    echo "=== Test: fresh — dirty bystander under aitasks/ not swept ==="
    setup_project

    write_task aitasks/t10_primary.md
    write_task aitasks/t20_a.md
    write_task aitasks/t99_bystander.md
    git add -A
    git commit -m "Setup" --quiet

    # Another session mid-edit: dirty, unstaged, under aitasks/.
    printf '\nconcurrent edit\n' >> aitasks/t99_bystander.md

    local output
    output=$(bash .aitask-scripts/aitask_fold_mark.sh --commit-mode fresh 10 20 2>&1)
    assert_contains "committed" "COMMITTED:" "$output"

    assert_in_head "primary in commit" "aitasks/t10_primary.md"
    assert_in_head "folded task in commit" "aitasks/t20_a.md"
    assert_not_in_head "bystander NOT swept" "aitasks/t99_bystander.md"
    assert_status_code "bystander still dirty+unstaged" " M" aitasks/t99_bystander.md

    teardown
}

test_fresh_prestaged_foreign_not_swept() {
    echo "=== Test: fresh — pre-STAGED path outside aitasks/ not swept ==="
    setup_project

    write_task aitasks/t10_primary.md
    write_task aitasks/t20_a.md
    git add -A
    git commit -m "Setup" --quiet

    # Outside aitasks/, so `add aitasks/` cannot be what carries it — only the
    # pathspec-less commit can. This is the SECOND swallow mechanism.
    mkdir -p aiplans
    printf 'unrelated plan\n' > aiplans/p999_unrelated.md
    git add aiplans/p999_unrelated.md

    local output
    output=$(bash .aitask-scripts/aitask_fold_mark.sh --commit-mode fresh 10 20 2>&1)
    assert_contains "committed" "COMMITTED:" "$output"

    assert_not_in_head "pre-staged foreign plan NOT swept" "aiplans/p999_unrelated.md"
    assert_status_code "pre-staged foreign plan still staged" "A " aiplans/p999_unrelated.md

    teardown
}

# Build a HEAD shaped like an `ait create` commit, then fold into it with
# --commit-mode amend. `extra_paths` are co-committed into that HEAD.
_setup_amend_fixture() {
    setup_project

    write_task aitasks/t10_primary.md
    write_task aitasks/t20_a.md
    git add -A
    git commit -m "Setup" --quiet

    FOLD_PATHS=( aitasks/t10_primary.md aitasks/t20_a.md )

    # The "task creation" commit that --commit-mode amend is meant to amend.
    printf '\ncreated\n' >> aitasks/t10_primary.md
    git add aitasks/t10_primary.md
    local p
    for p in "$@"; do
        git add "$p"
    done
    git commit -m "ait: Add task t10: primary" --quiet
}

test_amend_dirty_bystander_not_swept() {
    echo "=== Test: amend — dirty bystander not swept ==="
    _setup_amend_fixture

    write_task aitasks/t99_bystander.md
    git add aitasks/t99_bystander.md
    git commit -m "add bystander" --quiet
    printf '\nconcurrent edit\n' >> aitasks/t99_bystander.md

    # HEAD is now the bystander commit, which carries a foreign task file — so
    # rebuild a clean amend target on top of it.
    printf '\nmore\n' >> aitasks/t10_primary.md
    git add aitasks/t10_primary.md
    git commit -m "ait: Add task t10: primary" --quiet

    local output
    output=$(bash .aitask-scripts/aitask_fold_mark.sh --commit-mode amend 10 20 2>&1)
    assert_contains "amended" "AMENDED" "$output"

    assert_not_in_head "bystander NOT swept" "aitasks/t99_bystander.md"
    assert_status_code "bystander still dirty+unstaged" " M" aitasks/t99_bystander.md

    teardown
}

test_amend_prestaged_foreign_not_swept() {
    echo "=== Test: amend — pre-STAGED path outside aitasks/ not swept ==="
    _setup_amend_fixture

    mkdir -p aiplans
    printf 'unrelated plan\n' > aiplans/p999_unrelated.md
    git add aiplans/p999_unrelated.md

    local output
    output=$(bash .aitask-scripts/aitask_fold_mark.sh --commit-mode amend 10 20 2>&1)
    assert_contains "amended" "AMENDED" "$output"

    assert_not_in_head "pre-staged foreign plan NOT swept" "aiplans/p999_unrelated.md"
    assert_status_code "pre-staged foreign plan still staged" "A " aiplans/p999_unrelated.md

    teardown
}

test_amend_refuses_foreign_task_in_head() {
    echo "=== Test: amend REFUSES a foreign task file in HEAD ==="
    _setup_amend_fixture

    # HEAD acquires a foreign task file — the 8664a6a76 shape.
    write_task aitasks/t77_foreign.md
    git add aitasks/t77_foreign.md
    git commit --amend --no-edit --quiet

    local before rc=0 output
    before=$(git rev-parse HEAD)
    output=$(bash .aitask-scripts/aitask_fold_mark.sh --commit-mode amend 10 20 2>&1) || rc=$?

    assert_eq "exits non-zero" "1" "$rc"
    assert_contains "error names the offending path" "aitasks/t77_foreign.md" "$output"
    assert_contains "error points at fresh mode" "--commit-mode fresh" "$output"
    assert_no_fold_residue "foreign-HEAD refusal" "$before"
    # The load-bearing half: the fold's mutations were actually rolled back.
    assert_eq "folded task reverted to Ready" "Ready" \
        "$(read_frontmatter_field aitasks/t20_a.md status)"
    assert_eq "folded task has no folded_into" "" \
        "$(read_frontmatter_field aitasks/t20_a.md folded_into)"
    assert_eq "primary has no folded_tasks" "" \
        "$(read_frontmatter_field aitasks/t10_primary.md folded_tasks)"

    teardown
}

test_amend_refuses_unknown_metadata_in_head() {
    echo "=== Test: amend REFUSES unknown metadata in HEAD ==="
    _setup_amend_fixture

    # The 21219b0b4 shape: a foreign metadata file, not a task file.
    printf 'gates: []\n' > aitasks/metadata/gates.yaml
    git add aitasks/metadata/gates.yaml
    git commit --amend --no-edit --quiet

    local before rc=0 output
    before=$(git rev-parse HEAD)
    output=$(bash .aitask-scripts/aitask_fold_mark.sh --commit-mode amend 10 20 2>&1) || rc=$?

    assert_eq "exits non-zero" "1" "$rc"
    assert_contains "error names the offending path" "aitasks/metadata/gates.yaml" "$output"
    assert_no_fold_residue "metadata-HEAD refusal" "$before"
    assert_eq "folded task reverted to Ready" "Ready" \
        "$(read_frontmatter_field aitasks/t20_a.md status)"

    teardown
}

test_amend_refuses_task_like_metadata_filename() {
    echo "=== Test: amend REFUSES a task-LIKE filename outside a canonical location ==="
    _setup_amend_fixture

    # Basename parses as "task 10" -- the very id being folded into -- but it
    # lives under metadata/, not at a canonical task location. A basename-only
    # classifier accepted this; default-deny must refuse it.
    printf 'not a task\n' > aitasks/metadata/t10_unrelated.md
    git add aitasks/metadata/t10_unrelated.md
    git commit --amend --no-edit --quiet

    local before rc=0 output
    before=$(git rev-parse HEAD)
    output=$(bash .aitask-scripts/aitask_fold_mark.sh --commit-mode amend 10 20 2>&1) || rc=$?

    assert_eq "exits non-zero" "1" "$rc"
    assert_contains "error names the offending path" "aitasks/metadata/t10_unrelated.md" "$output"
    assert_no_fold_residue "task-like-metadata refusal" "$before"
    assert_eq "folded task reverted to Ready" "Ready" \
        "$(read_frontmatter_field aitasks/t20_a.md status)"

    teardown
}

test_amend_refuses_archived_and_misfiled_lookalikes() {
    echo "=== Test: amend REFUSES archived / directory-mismatched lookalikes ==="
    _setup_amend_fixture

    # aitasks/archived/t10_old.md parses as "10" by basename; aitasks/t99/…
    # holds a file whose filename id (10_2) disagrees with its t99 directory.
    mkdir -p aitasks/archived aitasks/t99
    printf 'archived\n' > aitasks/archived/t10_old.md
    printf 'misfiled\n' > aitasks/t99/t10_2_misfiled.md
    git add aitasks/archived/t10_old.md aitasks/t99/t10_2_misfiled.md
    git commit --amend --no-edit --quiet

    local before rc=0 output
    before=$(git rev-parse HEAD)
    output=$(bash .aitask-scripts/aitask_fold_mark.sh --commit-mode amend 10 20 2>&1) || rc=$?

    assert_eq "exits non-zero" "1" "$rc"
    assert_contains "error names the archived lookalike" "aitasks/archived/t10_old.md" "$output"
    assert_contains "error names the misfiled child" "aitasks/t99/t10_2_misfiled.md" "$output"
    assert_no_fold_residue "lookalike refusal" "$before"

    teardown
}

test_amend_permits_labels_file_in_head() {
    echo "=== Test: amend PERMITS labels.txt in HEAD (accept-branch 3) ==="
    setup_project

    write_task aitasks/t10_primary.md
    write_task aitasks/t20_a.md
    git add -A
    git commit -m "Setup" --quiet

    # Exactly what aitask_create.sh stages: the task file + the label vocabulary.
    printf '\ncreated\n' >> aitasks/t10_primary.md
    printf 'newlabel\n' >> aitasks/metadata/labels.txt
    git add aitasks/t10_primary.md aitasks/metadata/labels.txt
    git commit -m "ait: Add task t10: primary" --quiet

    local output rc=0
    output=$(bash .aitask-scripts/aitask_fold_mark.sh --commit-mode amend 10 20 2>&1) || rc=$?

    assert_eq "exits zero" "0" "$rc"
    assert_contains "amended" "AMENDED" "$output"
    assert_in_head "labels.txt retained" "aitasks/metadata/labels.txt"

    teardown
}

test_amend_permits_child_primary_parent_file() {
    echo "=== Test: amend PERMITS a child primary's own parent file (branch 2) ==="
    setup_project

    # Primary is a CHILD; HEAD is a child-creation commit carrying the child,
    # its parent, and labels.txt — exactly aitask_create.sh:859-866.
    write_task aitasks/t30_orig_parent.md "children_to_implement: [t30_1]"
    write_task aitasks/t30/t30_1_child.md
    write_task aitasks/t20_a.md
    git add -A
    git commit -m "Setup" --quiet

    printf '\ncreated\n' >> aitasks/t30/t30_1_child.md
    printf '\ntouched\n' >> aitasks/t30_orig_parent.md
    printf 'newlabel\n' >> aitasks/metadata/labels.txt
    git add aitasks/t30/t30_1_child.md aitasks/t30_orig_parent.md aitasks/metadata/labels.txt
    git commit -m "ait: Add child task t30_1: child" --quiet

    local output rc=0
    output=$(bash .aitask-scripts/aitask_fold_mark.sh --commit-mode amend 30_1 20 2>&1) || rc=$?

    assert_eq "exits zero" "0" "$rc"
    assert_contains "amended" "AMENDED" "$output"
    assert_in_head "child primary's own parent retained" "aitasks/t30_orig_parent.md"

    teardown
}

test_amend_refuses_published_head() {
    echo "=== Test: amend REFUSES an already-published HEAD ==="
    _setup_amend_fixture

    # Publish HEAD, so amending it would rewrite pushed history.
    git push -u origin HEAD --quiet 2>/dev/null

    local before rc=0 output
    before=$(git rev-parse HEAD)
    output=$(bash .aitask-scripts/aitask_fold_mark.sh --commit-mode amend 10 20 2>&1) || rc=$?

    assert_eq "exits non-zero" "1" "$rc"
    assert_contains "error says published" "already published" "$output"
    assert_no_fold_residue "published-HEAD refusal" "$before"
    assert_eq "folded task reverted to Ready" "Ready" \
        "$(read_frontmatter_field aitasks/t20_a.md status)"

    teardown
}

test_child_fold_commits_parent_file() {
    echo "=== Test: fresh — child fold still commits the parent file ==="
    setup_project

    write_task aitasks/t10_primary.md
    write_task aitasks/t30_orig_parent.md "children_to_implement: [t30_1]"
    write_task aitasks/t30/t30_1_child.md
    git add -A
    git commit -m "Setup" --quiet

    local output
    output=$(bash .aitask-scripts/aitask_fold_mark.sh --commit-mode fresh 10 30_1 2>&1)
    assert_contains "committed" "COMMITTED:" "$output"
    assert_contains "child removed from parent" "CHILD_REMOVED:30:1" "$output"

    # A legitimate co-change: the --remove-child edit. Scoping must NOT drop it.
    assert_in_head "folded child's parent IS committed" "aitasks/t30_orig_parent.md"
    assert_in_head "folded child IS committed" "aitasks/t30/t30_1_child.md"

    teardown
}

# --- t1661: records describe surviving state only ----------------------------
#
# Three tests for the three Step 6 failure exits (guard refusal before staging,
# fresh-commit failure, amend-commit failure): stdout must be silent, and the
# rollback must still have happened. Three more for the four flush points
# (crc=0, crc=2, amend, none — the last extends test_none_mode_no_commit above):
# the full record set must survive, in order, ahead of the terminal record.
# Plus the pre-Step-6 abort, where the contract deliberately stops short.

test_refused_amend_emits_no_records() {
    echo "=== Test: t1661 — a refused amend emits no records ==="
    _setup_amend_fixture

    # HEAD acquires a foreign task file, so the guard refuses BEFORE staging.
    write_task aitasks/t77_foreign.md
    git add aitasks/t77_foreign.md
    git commit --amend --no-edit --quiet

    local before
    before=$(git rev-parse HEAD)
    _run_fold_split --commit-mode amend 10 20

    assert_eq "exits non-zero" "1" "$FOLD_RC"
    assert_eq "stdout is empty" "" "$FOLD_OUT"
    assert_no_records "guard refusal" "$FOLD_OUT"
    assert_contains "refusal went to stderr" "refusing --commit-mode amend" "$FOLD_ERR"
    # The silence is only honest if the transaction really was undone.
    assert_no_fold_residue "guard refusal" "$before"
    assert_eq "folded task reverted to Ready" "Ready" \
        "$(read_frontmatter_field aitasks/t20_a.md status)"
    assert_eq "folded task has no folded_into" "" \
        "$(read_frontmatter_field aitasks/t20_a.md folded_into)"
    assert_eq "primary has no folded_tasks" "" \
        "$(read_frontmatter_field aitasks/t10_primary.md folded_tasks)"

    teardown
}

test_fresh_commit_failure_emits_no_records() {
    echo "=== Test: t1661 — a failed fresh commit emits no records ==="
    setup_project

    write_task aitasks/t10_primary.md
    write_task aitasks/t20_a.md
    git add -A
    git commit -m "Setup" --quiet
    FOLD_PATHS=( aitasks/t10_primary.md aitasks/t20_a.md )

    local before
    before=$(git rev-parse HEAD)
    _install_failing_pre_commit_hook

    _run_fold_split --commit-mode fresh 10 20

    assert_eq "exits non-zero" "1" "$FOLD_RC"
    assert_eq "stdout is empty" "" "$FOLD_OUT"
    assert_no_records "fresh commit failure" "$FOLD_OUT"
    assert_contains "failure went to stderr" "fold commit failed" "$FOLD_ERR"
    assert_no_fold_residue "fresh commit failure" "$before"
    assert_eq "folded task reverted to Ready" "Ready" \
        "$(read_frontmatter_field aitasks/t20_a.md status)"
    assert_eq "primary has no folded_tasks" "" \
        "$(read_frontmatter_field aitasks/t10_primary.md folded_tasks)"

    teardown
}

test_amend_commit_failure_emits_no_records() {
    echo "=== Test: t1661 — a failed amend commit emits no records ==="
    # Clean HEAD, so the guard PERMITS the amend and the commit itself is what
    # fails — a different exit from test_refused_amend_emits_no_records above.
    _setup_amend_fixture

    local before
    before=$(git rev-parse HEAD)
    _install_failing_pre_commit_hook

    _run_fold_split --commit-mode amend 10 20

    assert_eq "exits non-zero" "1" "$FOLD_RC"
    assert_eq "stdout is empty" "" "$FOLD_OUT"
    assert_no_records "amend commit failure" "$FOLD_OUT"
    assert_contains "failure went to stderr" "fold amend-commit failed" "$FOLD_ERR"
    assert_no_fold_residue "amend commit failure" "$before"
    assert_eq "folded task reverted to Ready" "Ready" \
        "$(read_frontmatter_field aitasks/t20_a.md status)"

    teardown
}

# _seed_all_record_types — a fold whose run produces every record type:
# PRIMARY_UPDATED (10), FOLDED (20 and the child 30_1), CHILD_REMOVED (30:1)
# and TRANSITIVE (70, 71, carried by t20's own folded_tasks).
_seed_all_record_types() {
    write_task aitasks/t10_primary.md
    write_task aitasks/t20_a.md "folded_tasks: [70, 71]"
    write_task aitasks/t70_x.md
    write_task aitasks/t71_y.md
    write_task aitasks/t30_orig_parent.md "children_to_implement: [t30_1]"
    write_task aitasks/t30/t30_1_child.md
}

# The emission order Steps 3-5 produce, which buffering must not disturb.
ALL_RECORDS=$'PRIMARY_UPDATED:10\nFOLDED:20\nFOLDED:30_1\nCHILD_REMOVED:30:1\nTRANSITIVE:70\nTRANSITIVE:71'

# assert_records_then <desc> <terminal-record-prefix>
# The buffered records must appear in ALL_RECORDS order, with the terminal
# record last and nothing else in between.
assert_records_then() {
    local desc="$1" terminal="$2"
    assert_eq "$desc: 6 records + terminal" "7" "$(printf '%s\n' "$FOLD_OUT" | wc -l)"
    assert_eq "$desc: records in emission order" "$ALL_RECORDS" \
        "$(printf '%s\n' "$FOLD_OUT" | head -n 6)"
    assert_contains "$desc: terminal record last" "$terminal" \
        "$(printf '%s\n' "$FOLD_OUT" | tail -n 1)"
}

test_fresh_flush_order_preserved() {
    echo "=== Test: t1661 — fresh flushes the full record set, in order ==="
    setup_project

    _seed_all_record_types
    git add -A
    git commit -m "Setup" --quiet

    _run_fold_split --commit-mode fresh 10 20 30_1

    assert_eq "exits zero" "0" "$FOLD_RC"
    assert_records_then "fresh" "COMMITTED:"

    teardown
}

test_amend_flush_order_preserved() {
    echo "=== Test: t1661 — a permitted amend flushes the full record set ==="
    setup_project

    _seed_all_record_types
    git add -A
    git commit -m "Setup" --quiet

    # HEAD the amend targets carries only the primary, so the guard permits it.
    printf '\ncreated\n' >> aitasks/t10_primary.md
    git add aitasks/t10_primary.md
    git commit -m "ait: Add task t10: primary" --quiet

    _run_fold_split --commit-mode amend 10 20 30_1

    assert_eq "exits zero" "0" "$FOLD_RC"
    assert_records_then "amend" "AMENDED"

    teardown
}

test_fresh_verified_noop_flushes_records() {
    echo "=== Test: t1661 — a verified no-op fresh commit still flushes ==="
    setup_project

    write_task aitasks/t10_primary.md
    write_task aitasks/t20_a.md
    git add -A
    git commit -m "Setup" --quiet

    local before
    before=$(git rev-parse HEAD)

    # task_git_commit_scoped returns 2 when `git status --porcelain -- <paths>`
    # is empty with rc 0. In production that is the idempotent re-fold, whose
    # rewrite is byte-identical — but only within the same minute, since
    # aitask_update.sh stamps updated_at to the current one. The index bit is
    # the deterministic stand-in: git reports these paths clean however the
    # fold rewrites them on disk. `NO_COMMIT` from a FRESH invocation can only
    # come from that arm (crc=0 prints COMMITTED:), so the assertion below
    # cannot pass without actually reaching it.
    git update-index --assume-unchanged aitasks/t10_primary.md aitasks/t20_a.md

    _run_fold_split --commit-mode fresh 10 20

    assert_eq "exits zero" "0" "$FOLD_RC"
    assert_eq "records flushed ahead of NO_COMMIT" \
        $'PRIMARY_UPDATED:10\nFOLDED:20\nNO_COMMIT' "$FOLD_OUT"
    assert_eq "no commit was created" "$before" "$(git rev-parse HEAD)"
    # The records are only honest if the mutations really did survive.
    assert_eq "folded task IS Folded on disk" "Folded" \
        "$(read_frontmatter_field aitasks/t20_a.md status)"

    git update-index --no-assume-unchanged aitasks/t10_primary.md aitasks/t20_a.md
    teardown
}

# --- t1668: the rollback restores PRE-FOLD state, not HEAD ------------------

test_step6_rollback_preserves_dirty_entry() {
    echo "=== Test: t1668 — a Step 6 rollback keeps the primary's pre-fold edit ==="
    setup_project

    write_task aitasks/t10_primary.md
    write_task aitasks/t20_a.md
    git add -A
    git commit -m "Setup" --quiet

    # The primary is DIRTY on entry -- exactly what the ad-hoc fold flow hands
    # this script: `aitask_fold_content.sh | aitask_update.sh --desc-file -`
    # merges the folded descriptions into the primary immediately beforehand,
    # and does not commit. A HEAD-restoring rollback throws that merge away.
    printf '\nPRE-FOLD EDIT\n' >> aitasks/t10_primary.md

    _install_failing_pre_commit_hook
    _run_fold_split --commit-mode fresh 10 20

    assert_eq "exits non-zero" "1" "$FOLD_RC"
    # The fold itself must be undone...
    assert_eq "fold undone: primary has no folded_tasks" "" \
        "$(read_frontmatter_field aitasks/t10_primary.md folded_tasks)"
    assert_eq "fold undone: folded task back to Ready" "Ready" \
        "$(read_frontmatter_field aitasks/t20_a.md status)"
    # ...but the caller's uncommitted edit must NOT be.
    assert_contains "pre-fold edit survives the rollback" "PRE-FOLD EDIT" \
        "$(cat aitasks/t10_primary.md)"

    teardown
}

test_abort_mid_mutation_rolls_back() {
    echo "=== Test: t1668 — an abort before Step 6 rolls back and emits no records ==="
    setup_project

    write_task aitasks/t10_primary.md
    git add -A
    git commit -m "Setup" --quiet

    local before
    before=$(git rev-parse HEAD)

    # A folded id with no task file: Step 3 updates the primary, then Step 4's
    # aitask_update.sh for the missing id exits non-zero and `set -e` kills the
    # script BEFORE Step 6. The buffer is never flushed, so stdout stays empty.
    _run_fold_split --commit-mode fresh 10 9999

    assert_eq "exits non-zero" "1" "$FOLD_RC"
    assert_eq "stdout is empty" "" "$FOLD_OUT"
    assert_no_records "pre-Step-6 abort" "$FOLD_OUT"
    assert_contains "stderr names the missing task" "9999" "$FOLD_ERR"
    assert_contains "stderr names the rollback" "rolled back every mutation" "$FOLD_ERR"

    # t1668: the silence is now honest. Before this task the Step 3 mutation
    # stayed on disk (folded_tasks: [9999], worktree ` M`) because the rollback
    # set was not assembled until after Step 5b; the exit status was the only
    # signal. The whole run is one transaction now, so an empty record set means
    # what it looks like.
    assert_eq "the Step 3 mutation was rolled back" "" \
        "$(read_frontmatter_field aitasks/t10_primary.md folded_tasks)"
    assert_eq "primary clean in the worktree" "" \
        "$(git status --porcelain -- aitasks/t10_primary.md)"
    assert_eq "HEAD unchanged" "$before" "$(git rev-parse HEAD)"

    teardown
}

# --- t1668: attachment-window fixture helpers --------------------------------
#
# Step 5b is lazily sourced, so setup_project's minimal lib set does not carry
# the attachment ledger. registry_lock.sh / stale_lock.sh / python_resolve.sh /
# yaml_utils.sh already come from the shared scaffold; these are the rest.
_copy_attachment_libs() {
    cp "$PROJECT_DIR/.aitask-scripts/lib/attachment_lock.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/attachment_meta.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/artifact_utils.sh"  .aitask-scripts/lib/
    copy_py_closure_from "$PROJECT_DIR/.aitask-scripts/lib" \
        "$PWD/.aitask-scripts/lib" attachment_meta frontmatter_patch
}

# _seed_attachment <task_stem_path> <owner_id> <content> — write a task file
# carrying one `attachments:` entry plus its per-blob meta file, so the fold
# takes the Step 5b path. Sets ATTACH_HEX / ATTACH_META for the caller.
ATTACH_HEX=""; ATTACH_META=""
_seed_attachment() {
    local path="$1" owner="$2" content="$3"
    ATTACH_HEX="$(printf '%s' "$content" | sha256sum | cut -d' ' -f1)"
    write_task "$path" "attachments:" \
        "  - hash: sha256:${ATTACH_HEX}" \
        "    name: rb.bin"
    ATTACH_META="attachments/meta/${ATTACH_HEX:0:2}/${ATTACH_HEX:2}.json"
    mkdir -p "$(dirname "$ATTACH_META")"
    printf '{"hash": "sha256:%s", "refs": ["%s"]}\n' "$ATTACH_HEX" "$owner" > "$ATTACH_META"
}

# _install_failing_frontmatter_patch — make the attachment/artifact frontmatter
# merge fail. This is the documented mutating seam INSIDE the attach
# transaction, reached only after the rebind has already rewritten meta files.
# It is invoked THROUGH python (`"$(require_python)" .../frontmatter_patch.py`),
# so the stub must be valid Python. If an executable `.fm_side_effect` exists in
# the repo root it is run at the INSTANT the stub fails (t1698): a
# restore-failure case needs a path to become unwritable BETWEEN the fold's own
# writes and the rollback's `cp` back, and chmod'ing it any earlier would break
# Steps 4-5, which legitimately write the primary.
_install_failing_frontmatter_patch() {
    cat > .aitask-scripts/lib/frontmatter_patch.py <<'STUB'
import os, subprocess, sys
if os.access(".fm_side_effect", os.X_OK):
    subprocess.run(["./.fm_side_effect"])
sys.stderr.write("stub: append refused\n")
sys.exit(7)
STUB
    chmod +x .aitask-scripts/lib/frontmatter_patch.py
}

# _install_failing_ls_files — a PATH shim whose `git` refuses `ls-files` and
# forwards everything else to the real binary. task_git calls bare `git`, so
# this is the CLI boundary, not a source patch: it exercises the real
# index-read failure (an unreadable/locked index) without touching the script.
_install_failing_ls_files() {
    local realgit; realgit="$(command -v git)"
    mkdir -p .shim
    {
        printf '#!/usr/bin/env bash\n'
        printf 'for a in "$@"; do [[ "$a" == "ls-files" ]] && { echo "shim: index read refused" >&2; exit 1; }; done\n'
        printf 'exec %q "$@"\n' "$realgit"
    } > .shim/git
    chmod +x .shim/git
}

test_index_read_failure_aborts_before_mutating() {
    echo "=== Test: t1668 — an unreadable index aborts BEFORE the transaction ==="
    setup_project

    write_task aitasks/t10_primary.md
    git add -A
    git commit -m "Setup" --quiet

    # A pre-existing STAGED edit: the thing a fail-open snapshot destroys.
    printf '\nPRE-FOLD EDIT\n' >> aitasks/t10_primary.md
    git add aitasks/t10_primary.md
    local staged_before
    staged_before="$(git ls-files --stage -- aitasks/t10_primary.md)"

    _install_failing_ls_files
    local oldpath="$PATH"
    PATH="$PWD/.shim:$PATH"
    _run_fold_split --commit-mode fresh 10 9999
    PATH="$oldpath"

    assert_eq "exits non-zero" "1" "$FOLD_RC"
    assert_contains "stderr names the index-read failure" \
        "could not read the index entry" "$FOLD_ERR"
    # `ls-files` exits 0 with EMPTY output for a path that is merely absent from
    # the index, so a non-zero exit can only mean the read failed. Recording it
    # as "absent" (a `|| :`-truncated snapshot) would make a later rollback's
    # --force-remove DELETE this entry instead of restoring it.
    assert_eq "the caller's staged index entry is untouched" "$staged_before" \
        "$(git ls-files --stage -- aitasks/t10_primary.md)"
    assert_status_code "still staged" "M " aitasks/t10_primary.md
    assert_eq "nothing was mutated" "" \
        "$(read_frontmatter_field aitasks/t10_primary.md folded_tasks)"

    teardown
}

test_abort_preserves_pre_existing_dirty_primary() {
    echo "=== Test: t1668 — a pre-Step-6 abort keeps the primary's dirty edit ==="
    setup_project

    write_task aitasks/t10_primary.md
    git add -A
    git commit -m "Setup" --quiet

    printf '\nPRE-FOLD EDIT\n' >> aitasks/t10_primary.md

    _run_fold_split --commit-mode fresh 10 9999

    assert_eq "exits non-zero" "1" "$FOLD_RC"
    assert_eq "fold undone" "" \
        "$(read_frontmatter_field aitasks/t10_primary.md folded_tasks)"
    assert_contains "pre-fold edit survives the rollback" "PRE-FOLD EDIT" \
        "$(cat aitasks/t10_primary.md)"

    teardown
}

test_abort_preserves_pre_existing_staged_primary() {
    echo "=== Test: t1668 — a pre-Step-6 abort keeps the primary's STAGED edit ==="
    setup_project

    write_task aitasks/t10_primary.md
    git add -A
    git commit -m "Setup" --quiet

    # Staged, not merely dirty. A rollback that opens with a blanket
    # `git reset -- <paths>` unstages this; the fold stages nothing before
    # Step 6, so that reset could only ever discard the CALLER's work.
    printf '\nPRE-FOLD EDIT\n' >> aitasks/t10_primary.md
    git add aitasks/t10_primary.md

    _run_fold_split --commit-mode fresh 10 9999

    assert_eq "exits non-zero" "1" "$FOLD_RC"
    assert_eq "fold undone" "" \
        "$(read_frontmatter_field aitasks/t10_primary.md folded_tasks)"
    assert_status_code "still staged, not unstaged" "M " aitasks/t10_primary.md
    assert_contains "the staged content is the pre-fold one" "PRE-FOLD EDIT" \
        "$(git diff --cached -- aitasks/t10_primary.md)"
    assert_not_contains "the staged content carries no fold mutation" \
        "folded_tasks" "$(git diff --cached -- aitasks/t10_primary.md)"

    teardown
}

test_abort_preserves_unmerged_index_stages() {
    echo "=== Test: t1668 — a pre-Step-6 abort preserves unmerged index stages ==="
    setup_project

    write_task aitasks/t10_primary.md
    git add -A
    git commit -m "Setup" --quiet

    # Synthesise the conflicted-index shape without a real merge. `ait syncer`
    # rebases task data, so an unmerged aitasks/ path is reachable in the wild;
    # a restore that parses ONE mode/sha out of `ls-files --stage` and writes a
    # stage-0 entry would silently resolve it.
    local sha before
    sha=$(git hash-object -w aitasks/t10_primary.md)
    git update-index --force-remove -- aitasks/t10_primary.md
    printf '100644 %s 1\taitasks/t10_primary.md\n100644 %s 2\taitasks/t10_primary.md\n100644 %s 3\taitasks/t10_primary.md\n' \
        "$sha" "$sha" "$sha" | git update-index --index-info
    before="$(git ls-files --stage -- aitasks/t10_primary.md)"
    assert_eq "fixture really is unmerged (3 stages)" "3" \
        "$(printf '%s\n' "$before" | wc -l)"

    _run_fold_split --commit-mode fresh 10 9999

    assert_eq "exits non-zero" "1" "$FOLD_RC"
    assert_eq "all index stages round-trip byte-exactly" "$before" \
        "$(git ls-files --stage -- aitasks/t10_primary.md)"

    teardown
}

test_abort_rolls_back_child_and_parent() {
    echo "=== Test: t1668 — a pre-Step-6 abort rolls back every mutated file ==="
    setup_project

    write_task aitasks/t10_primary.md
    write_task aitasks/t30_orig_parent.md "children_to_implement: [t30_1]"
    write_task aitasks/t30/t30_1_child.md
    git add -A
    git commit -m "Setup" --quiet

    local before
    before=$(git rev-parse HEAD)

    # Step 4 marks 30_1 Folded and strips it from t30's children_to_implement,
    # THEN dies on the unresolvable 9999 — so three files are already mutated
    # when the abort lands.
    _run_fold_split --commit-mode fresh 10 30_1 9999

    assert_eq "exits non-zero" "1" "$FOLD_RC"
    assert_eq "stdout is empty" "" "$FOLD_OUT"
    assert_eq "primary rolled back" "" \
        "$(read_frontmatter_field aitasks/t10_primary.md folded_tasks)"
    assert_eq "child back to Ready" "Ready" \
        "$(read_frontmatter_field aitasks/t30/t30_1_child.md status)"
    assert_eq "child has no folded_into" "" \
        "$(read_frontmatter_field aitasks/t30/t30_1_child.md folded_into)"
    assert_contains "child restored to its original parent" "t30_1" \
        "$(read_frontmatter_field aitasks/t30_orig_parent.md children_to_implement)"
    assert_eq "worktree clean" "" "$(git status --porcelain -- aitasks/)"
    assert_eq "HEAD unchanged" "$before" "$(git rev-parse HEAD)"

    teardown
}

test_invalid_commit_mode_rejected() {
    echo "=== Test: t1668 — an invalid --commit-mode mutates nothing ==="
    setup_project

    write_task aitasks/t10_primary.md
    write_task aitasks/t20_a.md
    git add -A
    git commit -m "Setup" --quiet

    _run_fold_split --commit-mode bogus 10 20

    assert_eq "exits non-zero" "1" "$FOLD_RC"
    assert_eq "stdout is empty" "" "$FOLD_OUT"
    assert_contains "stderr names the mode" "invalid --commit-mode: 'bogus'" "$FOLD_ERR"
    assert_eq "primary untouched" "" \
        "$(read_frontmatter_field aitasks/t10_primary.md folded_tasks)"
    assert_eq "folded task untouched" "Ready" \
        "$(read_frontmatter_field aitasks/t20_a.md status)"
    assert_eq "worktree clean" "" "$(git status --porcelain -- aitasks/)"

    teardown
}

test_invalid_commit_mode_precedes_resolution() {
    echo "=== Test: t1668 — --commit-mode is validated before task resolution ==="
    setup_project

    write_task aitasks/t10_primary.md
    git add -A
    git commit -m "Setup" --quiet

    # Neither id resolves. Which error comes out says WHERE the mode is checked:
    # validated up front it is the commit-mode one; validated in Step 6 (as
    # before t1668) the run would die on the unresolvable primary long first.
    _run_fold_split --commit-mode bogus 9999 8888

    assert_eq "exits non-zero" "1" "$FOLD_RC"
    assert_contains "stderr names the commit mode" "invalid --commit-mode" "$FOLD_ERR"
    assert_not_contains "and NOT the unresolvable primary" \
        "primary task file not found" "$FOLD_ERR"

    teardown
}

test_attach_merge_failure_aborts_the_fold() {
    echo "=== Test: t1668 — a failed attachment merge aborts the fold ==="
    setup_project
    _copy_attachment_libs

    write_task aitasks/t10_primary.md
    _seed_attachment aitasks/t20_a.md 20 "rollback blob"
    git add -A
    git commit -m "Setup" --quiet

    # Precondition for the rollback assertions in the test below: prove the
    # injected failure actually REACHES the abort. errexit is off inside the
    # attach callback and _fold_merge_one assigns to seen_* right after the
    # append, so before t1668 this failure was overwritten by a successful
    # assignment and the fold committed partial attachment state.
    _install_failing_frontmatter_patch
    _run_fold_split --commit-mode fresh 10 20

    assert_eq "exits non-zero" "1" "$FOLD_RC"
    assert_eq "stdout is empty" "" "$FOLD_OUT"
    assert_contains "stderr names the merge failure" "attachment merge failed" "$FOLD_ERR"

    teardown
}

test_attach_txn_nonzero_return_rolls_back() {
    echo "=== Test: t1668 — a non-zero RETURN from the attach txn rolls back ==="
    setup_project
    _copy_attachment_libs

    write_task aitasks/t10_primary.md
    _seed_attachment aitasks/t20_a.md 20 "nonzero return blob"
    git add -A
    git commit -m "Setup" --quiet

    local before
    before=$(git rev-parse HEAD)

    install_attach_txn_returns_nonzero || { teardown; return; }
    _run_fold_split --commit-mode fresh 10 20

    # with_attach_lock ends with `return "$rc"`, and registry_lock_release has
    # already done `trap - EXIT` by then -- so a BARE `with_attach_lock
    # _fold_attach_txn` call site would trip errexit one line before the
    # re-arm and roll back nothing. This is the path a `die`-based injection
    # cannot reach.
    assert_eq "exits non-zero" "1" "$FOLD_RC"
    assert_contains "stderr names the wrapper failure" \
        "attachment transfer failed (exit 3)" "$FOLD_ERR"
    assert_eq "primary rolled back" "" \
        "$(read_frontmatter_field aitasks/t10_primary.md folded_tasks)"
    assert_eq "folded task back to Ready" "Ready" \
        "$(read_frontmatter_field aitasks/t20_a.md status)"
    assert_eq "worktree clean" "" "$(git status --porcelain -- aitasks/)"
    assert_eq "HEAD unchanged" "$before" "$(git rev-parse HEAD)"
    assert_dir_not_exists "attach lock released" "attachments/.attach.lock"

    teardown
}

test_negative_control_attach_rearm_removed() {
    echo "=== Negative control: t1707 — WITHOUT the re-arm, nothing rolls back ==="
    setup_project
    _copy_attachment_libs

    write_task aitasks/t10_primary.md
    _seed_attachment aitasks/t20_a.md 20 "rearm control blob"
    git add -A
    git commit -m "Setup" --quiet

    # The paired control for test_attach_txn_nonzero_return_rolls_back above.
    # t1698's Step 8b review reported that fold has no EXIT trap after Step 5b
    # returns; it does (aitask_fold_mark.sh:820, shipped by t1668 itself). This
    # control settles that empirically: delete the re-arm and the SAME scenario
    # stops rolling back. Without it, the positive test proves nothing — it
    # would pass against a build where the re-arm was never needed.
    #
    # Injector order is load-bearing: the re-arm removal runs FIRST, because
    # install_attach_txn_returns_nonzero deletes _fold_snapshot_meta_tree and
    # rewrites the function this one's call-site guard reads around.
    install_attach_rearm_removed || { teardown; return; }
    install_attach_txn_returns_nonzero || { teardown; return; }

    _run_fold_split --commit-mode fresh 10 20

    # The die at :822 is unaffected — only the rollback behind it disappears.
    assert_eq "exits non-zero" "1" "$FOLD_RC"
    assert_contains "stderr still names the wrapper failure" \
        "attachment transfer failed (exit 3)" "$FOLD_ERR"

    assert_defect_present "pre-fix: primary was NOT rolled back" \
        test "[20]" = "$(read_frontmatter_field aitasks/t10_primary.md folded_tasks)"
    assert_defect_present "pre-fix: folded task left at Folded" \
        test "Folded" = "$(read_frontmatter_field aitasks/t20_a.md status)"
    assert_defect_present "pre-fix: no rollback was reported" \
        test -z "$(printf '%s' "$FOLD_ERR" | grep -F 'rolled back every mutation' || true)"

    teardown
}

test_abort_inside_attach_txn_rolls_back() {
    echo "=== Test: t1668 — an abort INSIDE the attach transaction rolls back ==="
    setup_project
    _copy_attachment_libs

    write_task aitasks/t10_primary.md
    _seed_attachment aitasks/t20_a.md 20 "attach window blob"
    git add -A
    git commit -m "Setup" --quiet

    # A pre-fold uncommitted edit to the META file. The rebind rewrites this
    # file before the merge fails, so restoring it from HEAD (the only option
    # for a path discovered after its own mutation) would discard this line --
    # which is why the meta tree is snapshotted before the rebind runs.
    printf '{"hash": "sha256:%s", "refs": ["20"], "mime": "text/plain"}\n' \
        "$ATTACH_HEX" > "$ATTACH_META"
    local meta_before
    meta_before="$(cat "$ATTACH_META")"

    local before
    before=$(git rev-parse HEAD)

    _install_failing_frontmatter_patch
    _run_fold_split --commit-mode fresh 10 20

    # 1. The injected failure reached the abort (test_attach_merge_failure_*).
    assert_eq "exits non-zero" "1" "$FOLD_RC"
    assert_contains "the injected failure reached the abort" \
        "attachment merge failed" "$FOLD_ERR"
    # 2. The fold rolled back -- so the EXIT-trap chain installed inside the
    #    attach transaction really ran (registry_lock_acquire had replaced the
    #    fold's handler with its own).
    assert_eq "primary rolled back" "" \
        "$(read_frontmatter_field aitasks/t10_primary.md folded_tasks)"
    assert_eq "folded task back to Ready" "Ready" \
        "$(read_frontmatter_field aitasks/t20_a.md status)"
    assert_eq "worktree clean under aitasks/" "" "$(git status --porcelain -- aitasks/)"
    assert_eq "HEAD unchanged" "$before" "$(git rev-parse HEAD)"
    # 3. The meta file came back as it was PRE-FOLD, not as HEAD has it.
    assert_eq "meta file restored to its pre-fold bytes" "$meta_before" \
        "$(cat "$ATTACH_META")"
    # 4. ...and the lock handler the chain was prepended to still ran.
    assert_dir_not_exists "attach lock released" "attachments/.attach.lock"

    teardown
}

# t1698: the fold wrappers must carry the RESTORE VERDICT, not just run the
# restore. _fold_rollback used to return _fold_prune_unsnapshotted_meta's status
# (discarding the restore's) and all four call sites printed an unconditional
# "rolled back every mutation" — so a partial rollback was announced as a
# complete one. Two cases, because the two halves fail independently.
test_fold_partial_restore_is_reported() {
    echo "=== Test: t1698 — a fold whose RESTORE fails says so ==="
    if [[ "$(id -u)" -eq 0 ]]; then
        echo "SKIP: needs an unwritable file to force a restore failure; running"
        echo "      as root, where the write bit is ignored and the forcing would"
        echo "      silently do nothing (the case would pass vacuously)."
        return 0
    fi
    setup_project
    _copy_attachment_libs
    write_task aitasks/t10_primary.md
    _seed_attachment aitasks/t20_a.md 20 "restore window blob"
    git add -A
    git commit -m "Setup" --quiet

    # Make the primary unrestorable at the MOMENT the transaction aborts —
    # after Steps 4-5 have legitimately written it, before the rollback's `cp`
    # back. The FILE's own write bit, not its parent's: cp over an existing file
    # opens and truncates, so a read-only directory would let the copy through
    # and the case would pass vacuously.
    printf '#!/usr/bin/env bash\nchmod a-w aitasks/t10_primary.md\n' > .fm_side_effect
    chmod +x .fm_side_effect

    _install_failing_frontmatter_patch
    _run_fold_split --commit-mode fresh 10 20
    chmod u+w aitasks/t10_primary.md 2>/dev/null || true
    rm -f .fm_side_effect

    assert_exit_nonzero_rc "the fold still fails" "$FOLD_RC"
    assert_contains "the report says the rollback did not fully restore" \
        "did NOT fully restore" "$FOLD_ERR"
    assert_contains "it names the un-restored path" "t10_primary.md" "$FOLD_ERR"
    assert_contains "it names the retained recovery directory" "ait_txn_snap" "$FOLD_ERR"
    assert_not_contains "and NEVER claims a full rollback" \
        "rolled back every mutation" "$FOLD_ERR"

    teardown
}

test_fold_partial_prune_is_reported() {
    echo "=== Test: t1698 — a fold whose PRUNE fails says so ==="
    if [[ "$(id -u)" -eq 0 ]]; then
        echo "SKIP: needs an unwritable directory to force a prune failure (root"
        echo "      ignores the write bit, so the case would pass vacuously)."
        return 0
    fi
    setup_project
    _copy_attachment_libs
    write_task aitasks/t10_primary.md
    _seed_attachment aitasks/t20_a.md 20 "prune window blob"
    git add -A
    git commit -m "Setup" --quiet

    # _fold_prune_unsnapshotted_meta deletes meta files the transaction CREATED,
    # and nothing in the shipped ledger creates one during a fold — the function
    # is defensive (its own comment says so). So this path is not reachable
    # without help: inject a transaction-created meta file plus an unwritable
    # shard directory, and the REAL prune code then runs and its REAL `rm -f`
    # fails. This is an injected scenario, not a production one.
    python3 - "$PWD/.aitask-scripts/aitask_fold_mark.sh" <<'PYEOF'
import sys
p = sys.argv[1]
s = open(p).read()
old = '    _fold_snapshot_meta_tree\n'
assert old in s, "meta-tree call not found"
inject = old + '    mkdir -p attachments/meta/zz\n' \
             + '    printf "{}\\n" > attachments/meta/zz/injected.json\n' \
             + '    chmod a-w attachments/meta/zz   # TEST INJECTION: break the prune\n'
open(p, 'w').write(s.replace(old, inject, 1))
PYEOF
    grep -q 'TEST INJECTION: break the prune' .aitask-scripts/aitask_fold_mark.sh \
        || { echo "FAIL: prune-break injection did not land"; FAIL=$((FAIL+1)); TOTAL=$((TOTAL+1)); teardown; return 1; }

    _install_failing_frontmatter_patch
    _run_fold_split --commit-mode fresh 10 20
    chmod u+w attachments/meta/zz 2>/dev/null || true

    assert_exit_nonzero_rc "the fold still fails" "$FOLD_RC"
    # The verdict must come from the RECORDED set: txn_rollback_failed returns 0
    # and sits in the prune loop's tail, so `_fold_prune_unsnapshotted_meta ||
    # rc=1` would be a no-op and this would read as a complete rollback.
    assert_contains "a prune-only failure still reports a partial rollback" \
        "did NOT fully restore" "$FOLD_ERR"
    assert_contains "it names the meta file that could not be deleted" \
        "attachments/meta/zz/injected.json" "$FOLD_ERR"
    assert_not_contains "and NEVER claims a full rollback" \
        "rolled back every mutation" "$FOLD_ERR"

    teardown
}

test_fold_clean_rollback_still_claims_full() {
    echo "=== Test: t1698 — control: a CLEAN fold rollback does claim full ==="
    setup_project
    _copy_attachment_libs
    write_task aitasks/t10_primary.md
    _seed_attachment aitasks/t20_a.md 20 "clean control blob"
    git add -A
    git commit -m "Setup" --quiet

    _install_failing_frontmatter_patch
    _run_fold_split --commit-mode fresh 10 20

    # Without this control the two cases above would pass against a build that
    # never prints the full-rollback message at all.
    assert_contains "a complete rollback claims every mutation was rolled back" \
        "rolled back every mutation" "$FOLD_ERR"
    assert_not_contains "and prints no partial report" \
        "did NOT fully restore" "$FOLD_ERR"
    assert_eq "the primary really came back" "" \
        "$(read_frontmatter_field aitasks/t10_primary.md folded_tasks)"

    teardown
}

# --- Negative controls -------------------------------------------------------
#
# Rebuild the fixture's copy of aitask_fold_mark.sh with the PRE-FIX Step 6
# block, then re-run the discriminating assertions and require them to FAIL.
# The pre-fix code has TWO independent swallow mechanisms and each control
# targets one:
#   `task_git add aitasks/`        — sweeps DIRTY files under aitasks/
#   pathspec-less `task_git commit`— sweeps anything already STAGED, anywhere
#
# install_prefix_commit_block asserts the substitution actually landed. A
# control that silently patched nothing would "pass" while proving nothing.
install_prefix_commit_block() {
    python3 - "$PWD/.aitask-scripts/aitask_fold_mark.sh" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
# Start at the guard helpers, not just the case block: a faithful pre-fix
# build has none of this code, and leaving the guard defined would make the
# "did the injection land" check below unable to tell the two apart.
start = s.index('# _fold_task_id_of_path -- task/plan id owning a repo path')
# Anchor on the block, not on a message inside it: the old anchor was the
# `--commit-mode` die string, which t1668 moved to argument-parse time. The
# nested `case "$crc"` ends with an INDENTED esac, so only the top-level one
# matches at column 0.
end = s.index('\nesac\n', s.index('# Step 6: commit')) + len('\nesac\n')
pre = '''# Step 6: commit
case "$commit_mode" in
    fresh)
        task_git add aitasks/ >/dev/null 2>&1 || true
        joined=""
        for fid in "${folded_ids[@]}"; do
            fid="${fid#t}"
            if [[ -n "$joined" ]]; then joined="${joined}, t${fid}"; else joined="t${fid}"; fi
        done
        if task_git commit -m "ait: Fold tasks into t${primary_id}: merge ${joined}" --quiet >/dev/null 2>&1; then
            hash=$(task_git rev-parse --short HEAD 2>/dev/null || echo "")
            _fold_flush_records
            echo "COMMITTED:${hash}"
        else
            _fold_flush_records
            echo "NO_COMMIT"
        fi
        ;;
    amend)
        task_git add aitasks/ >/dev/null 2>&1 || true
        if task_git commit --amend --no-edit --quiet >/dev/null 2>&1; then
            _fold_flush_records
            echo "AMENDED"
        else
            die "fold amend-commit failed"
        fi
        ;;
    none)
        _fold_flush_records
        echo "NO_COMMIT"
        ;;
    *)
        die "invalid --commit-mode: $commit_mode"
        ;;
esac
'''
open(p, 'w').write(s[:start] + pre + s[end:])
PY
    # Prove the injection landed — both mechanisms must be back.
    grep -q 'task_git add aitasks/' .aitask-scripts/aitask_fold_mark.sh \
        || { echo "FAIL: negative control did not install pre-fix broad add"; FAIL=$((FAIL+1)); TOTAL=$((TOTAL+1)); return 1; }
    grep -qE 'task_git commit -m "ait: Fold tasks into .*" --quiet' .aitask-scripts/aitask_fold_mark.sh \
        || { echo "FAIL: negative control did not install pathspec-less commit"; FAIL=$((FAIL+1)); TOTAL=$((TOTAL+1)); return 1; }
    # The DEFINITION, not a mention: the fold-transaction block above the
    # excision refers to _fold_amend_guard in a comment, and a bare name grep
    # would read that as "the guard survived".
    grep -q '^_fold_amend_guard() {' .aitask-scripts/aitask_fold_mark.sh \
        && { echo "FAIL: negative control left the amend guard in place"; FAIL=$((FAIL+1)); TOTAL=$((TOTAL+1)); return 1; }
    # t1668 (pin_control_excision_span): pin the excised SPAN's boundaries, not
    # just its content. The anchor is a `\nesac\n` search from `# Step 6:
    # commit`; if it ever matched a wider span it would swallow the fold
    # transaction block that sits above the guard helpers, and all three
    # t1599_2 controls below would keep "passing" while proving nothing.
    local marker
    # `_fold_snap_add` was the top-of-block marker until t1698 promoted the
    # snapshot primitive to lib/txn_snapshot.sh. `_fold_prune_unsnapshotted_meta`
    # replaces it: it is now the FIRST function in the transaction block, so a
    # span that widened upward loses it first — and it exists both in the real
    # block and in install_prefix_no_abort_rollback's stubbed one, so the guard
    # keeps working when the two injectors compose.
    for marker in '^_fold_abort_cleanup() {' '^_fold_prune_unsnapshotted_meta() {' '^_fold_emit() '; do
        grep -q "$marker" .aitask-scripts/aitask_fold_mark.sh \
            || { echo "FAIL: negative control excised too much — '$marker' is gone"; FAIL=$((FAIL+1)); TOTAL=$((TOTAL+1)); return 1; }
    done
    TOTAL=$((TOTAL + 1)); PASS=$((PASS + 1))
    return 0
}

# assert_defect_present <desc> <condition-cmd...> — the control INVERTS: the
# defect must be observable against the pre-fix build.
assert_defect_present() {
    local desc="$1"; shift
    TOTAL=$((TOTAL + 1))
    if "$@"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: negative control — $desc (pre-fix build did NOT exhibit the defect; the test above proves nothing)"
    fi
}

_head_contains() { git show --name-only --pretty=format: HEAD | grep -qxF -- "$1"; }

# _out_contains <needle> — predicate over the last _run_fold_split's stdout.
_out_contains() { case "$FOLD_OUT" in *"$1"*) return 0 ;; *) return 1 ;; esac; }

# t1661 control: rebuild the fixture's copy with the PRE-FIX record emission —
# each record printed the moment its mutation happens, nothing buffered. The
# silence tests above would pass just as happily against a build that never
# emits anything at all; this is what tells the two apart.
#
# It patches only the delimited helper block, which lives ABOVE Step 6, so it
# composes with install_prefix_commit_block rather than fighting it.
install_unbuffered_record_emission() {
    python3 - "$PWD/.aitask-scripts/aitask_fold_mark.sh" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
start = s.index('# --- Structured-record buffer (t1661)')
end = s.index('\n', s.index('# --- end structured-record buffer')) + 1
pre = """# --- Structured-record buffer (t1661) --- PRE-FIX BUILD: unbuffered
_fold_emit() { printf '%s\\n' "$1"; }
_fold_flush_records() { :; }
# --- end structured-record buffer ---
"""
open(p, 'w').write(s[:start] + pre + s[end:])
PY
    # Prove the injection landed — emission is direct AND the buffer is gone.
    grep -q "_fold_emit() { printf" .aitask-scripts/aitask_fold_mark.sh \
        || { echo "FAIL: negative control did not install unbuffered emission"; FAIL=$((FAIL+1)); TOTAL=$((TOTAL+1)); return 1; }
    grep -q '_fold_records+=' .aitask-scripts/aitask_fold_mark.sh \
        && { echo "FAIL: negative control left the record buffer in place"; FAIL=$((FAIL+1)); TOTAL=$((TOTAL+1)); return 1; }
    TOTAL=$((TOTAL + 1)); PASS=$((PASS + 1))
    return 0
}

# t1668 control A: rebuild the fixture's copy with the PRE-FIX transaction
# block -- the names still exist, but nothing is snapshotted and no EXIT trap is
# installed. The rollback tests above would pass just as happily against a build
# that never mutates anything; this is what tells the two apart.
#
# It patches only the delimited block, which lives ABOVE Step 6, so it composes
# with install_prefix_commit_block rather than fighting it.
install_prefix_no_abort_rollback() {
    python3 - "$PWD/.aitask-scripts/aitask_fold_mark.sh" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
start = s.index('# --- fold transaction (t1668)')
end = s.index('\n', s.index('# --- end fold transaction')) + 1
# The snapshot primitive moved to lib/txn_snapshot.sh (t1698), so the stubs
# below SHADOW the lib names rather than this file's old private ones. The block
# sits well below the `source` line, so redefining them here wins.
pre = """# --- fold transaction (t1668) --- PRE-FIX BUILD: no snapshot, no trap
_fold_txn_active=false
_fold_meta_root=""
_fold_meta_pre=()
txn_snap_init() { :; }
txn_snap_add() { :; }
txn_snap_restore() { :; }
txn_snap_cleanup() { :; }
_fold_snapshot_meta_tree() { :; }
_fold_prune_unsnapshotted_meta() { :; }
_fold_rollback_report() { :; }
_fold_abort_cleanup() { :; }
_FOLD_ROLLBACK_OK=1
_fold_rollback() {
    task_git reset -q -- "${fold_paths[@]}" >/dev/null 2>&1 || true
    task_git checkout -- "${fold_paths[@]}" >/dev/null 2>&1 || true
}
# --- end fold transaction ---
"""
open(p, 'w').write(s[:start] + pre + s[end:])
PY
    # Prove the injection landed -- no arming, no snapshotting.
    grep -q "PRE-FIX BUILD: no snapshot, no trap" .aitask-scripts/aitask_fold_mark.sh \
        || { echo "FAIL: negative control did not install the pre-fix transaction block"; FAIL=$((FAIL+1)); TOTAL=$((TOTAL+1)); return 1; }
    # Check the ARMING site, not the trap string: the post-attach-lock re-arm
    # lives outside this block (registry_lock_release clears EXIT) and would
    # match a bare `trap '_fold_abort_cleanup' EXIT` grep even after a correct
    # excision.
    grep -q '^_fold_txn_active=true$' .aitask-scripts/aitask_fold_mark.sh \
        && { echo "FAIL: negative control left the transaction armed"; FAIL=$((FAIL+1)); TOTAL=$((TOTAL+1)); return 1; }
    grep -q 'txn_snap_add "\$_p"' .aitask-scripts/aitask_fold_mark.sh \
        && { echo "FAIL: negative control left the snapshot loop in place"; FAIL=$((FAIL+1)); TOTAL=$((TOTAL+1)); return 1; }
    TOTAL=$((TOTAL + 1)); PASS=$((PASS + 1))
    return 0
}

# t1668: replace _fold_attach_txn's body with a bare non-zero RETURN, so the
# attach callback fails WITHOUT calling die. That is the only way to exercise
# with_attach_lock's `return "$rc"` path, which the die-based fault injection
# (_install_failing_frontmatter_patch) can never reach.
install_attach_txn_returns_nonzero() {
    python3 - "$PWD/.aitask-scripts/aitask_fold_mark.sh" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
start = s.index('_fold_attach_txn() {')
end = s.index('\n}\n', start) + len('\n}\n')
open(p, 'w').write(s[:start] + '_fold_attach_txn() {\n    return 3\n}\n' + s[end:])
PY
    grep -q '^    return 3$' .aitask-scripts/aitask_fold_mark.sh \
        || { echo "FAIL: injector did not stub _fold_attach_txn"; FAIL=$((FAIL+1)); TOTAL=$((TOTAL+1)); return 1; }
    grep -q '    _fold_snapshot_meta_tree$' .aitask-scripts/aitask_fold_mark.sh \
        && { echo "FAIL: injector left the attach transaction body in place"; FAIL=$((FAIL+1)); TOTAL=$((TOTAL+1)); return 1; }
    TOTAL=$((TOTAL + 1)); PASS=$((PASS + 1))
    return 0
}

# t1707: delete the post-attach-lock re-arm (aitask_fold_mark.sh:820), leaving an
# armed transaction with no EXIT handler between Step 5b and Step 6. This is the
# build t1698's Step 8b review believed was shipped; the control below proves it
# is not, and that removing the re-arm is observable. INJECTED — no shipped path
# reaches this state, which is exactly why the claim needed a mutant to settle.
#
# The anchor is the FULL line including its trailing comment. The bare trap text
# `trap '_fold_abort_cleanup' EXIT` ALSO matches the top-level arm at :518, so a
# loose anchor would silently mutate the wrong trap and the control would pass
# while proving nothing. The guards below pin exactly that: one re-arm line goes,
# the distinct column-0 top-level arm stays.
_FOLD_REARM_LINE="    trap '_fold_abort_cleanup' EXIT   # registry_lock_release did \`trap - EXIT\`"

install_attach_rearm_removed() {
    # Precondition: exactly ONE re-arm line, and the top-level arm is distinct.
    local n_rearm n_toplevel
    n_rearm=$(grep -cxF "$_FOLD_REARM_LINE" .aitask-scripts/aitask_fold_mark.sh || true)
    n_toplevel=$(grep -cxF "trap '_fold_abort_cleanup' EXIT" .aitask-scripts/aitask_fold_mark.sh || true)
    [[ "$n_rearm" == 1 ]] \
        || { echo "FAIL: expected exactly 1 post-attach-lock re-arm line, found $n_rearm"; FAIL=$((FAIL+1)); TOTAL=$((TOTAL+1)); return 1; }
    [[ "$n_toplevel" == 1 ]] \
        || { echo "FAIL: expected exactly 1 top-level trap arm, found $n_toplevel"; FAIL=$((FAIL+1)); TOTAL=$((TOTAL+1)); return 1; }

    python3 - "$PWD/.aitask-scripts/aitask_fold_mark.sh" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
old = "    trap '_fold_abort_cleanup' EXIT   # registry_lock_release did `trap - EXIT`\n"
if s.count(old) != 1:
    sys.stderr.write("anchor: post-attach-lock re-arm not found exactly once\n"); sys.exit(1)
open(p, 'w').write(s.replace(old, '', 1))
PY
    grep -qxF "$_FOLD_REARM_LINE" .aitask-scripts/aitask_fold_mark.sh \
        && { echo "FAIL: injector did not remove the post-attach-lock re-arm"; FAIL=$((FAIL+1)); TOTAL=$((TOTAL+1)); return 1; }
    # Excised the right line and only that line: the top-level arm and the call
    # site itself must both survive.
    grep -qxF "trap '_fold_abort_cleanup' EXIT" .aitask-scripts/aitask_fold_mark.sh \
        || { echo "FAIL: injector clobbered the top-level trap arm"; FAIL=$((FAIL+1)); TOTAL=$((TOTAL+1)); return 1; }
    grep -qF 'with_attach_lock _fold_attach_txn || _fold_attach_rc=$?' .aitask-scripts/aitask_fold_mark.sh \
        || { echo "FAIL: injector removed the with_attach_lock call site"; FAIL=$((FAIL+1)); TOTAL=$((TOTAL+1)); return 1; }
    TOTAL=$((TOTAL + 1)); PASS=$((PASS + 1))
    return 0
}

test_negative_control_no_abort_rollback() {
    echo "=== Negative control: pre-fix build DOES leave the abort residue ==="
    setup_project

    write_task aitasks/t10_primary.md
    git add -A
    git commit -m "Setup" --quiet

    install_prefix_no_abort_rollback || { teardown; return; }

    _run_fold_split --commit-mode fresh 10 9999

    assert_defect_present "pre-fix: the Step 3 mutation is still on disk" \
        test "[9999]" = "$(read_frontmatter_field aitasks/t10_primary.md folded_tasks)"
    assert_defect_present "pre-fix: the primary is left dirty" \
        test " M aitasks/t10_primary.md" = "$(git status --porcelain -- aitasks/t10_primary.md)"

    teardown
}

test_negative_control_unbuffered_on_refusal() {
    echo "=== Negative control: pre-fix emission DOES leak on a refused amend ==="
    _setup_amend_fixture

    write_task aitasks/t77_foreign.md
    git add aitasks/t77_foreign.md
    git commit --amend --no-edit --quiet

    install_unbuffered_record_emission || { teardown; return; }

    _run_fold_split --commit-mode amend 10 20

    assert_defect_present "pre-fix: a refused amend still prints PRIMARY_UPDATED" \
        _out_contains "PRIMARY_UPDATED:10"
    assert_defect_present "pre-fix: a refused amend still prints FOLDED" \
        _out_contains "FOLDED:20"

    teardown
}

test_negative_control_unbuffered_on_commit_failure() {
    echo "=== Negative control: pre-fix emission DOES leak on a failed commit ==="
    setup_project

    write_task aitasks/t10_primary.md
    write_task aitasks/t20_a.md
    git add -A
    git commit -m "Setup" --quiet

    install_unbuffered_record_emission || { teardown; return; }
    _install_failing_pre_commit_hook

    _run_fold_split --commit-mode fresh 10 20

    assert_defect_present "pre-fix: a failed fresh commit still prints PRIMARY_UPDATED" \
        _out_contains "PRIMARY_UPDATED:10"

    teardown
}

test_negative_control_fresh() {
    echo "=== Negative control: pre-fix fresh mode DOES swallow (both mechanisms) ==="
    setup_project

    write_task aitasks/t10_primary.md
    write_task aitasks/t20_a.md
    write_task aitasks/t99_bystander.md
    git add -A
    git commit -m "Setup" --quiet

    install_prefix_commit_block || { teardown; return; }

    printf '\nconcurrent edit\n' >> aitasks/t99_bystander.md      # dirty, under aitasks/
    mkdir -p aiplans
    printf 'unrelated plan\n' > aiplans/p999_unrelated.md
    git add aiplans/p999_unrelated.md                              # staged, outside aitasks/

    bash .aitask-scripts/aitask_fold_mark.sh --commit-mode fresh 10 20 >/dev/null 2>&1 || true

    assert_defect_present "broad add sweeps the dirty bystander" \
        _head_contains aitasks/t99_bystander.md
    assert_defect_present "pathspec-less commit sweeps the pre-staged plan" \
        _head_contains aiplans/p999_unrelated.md

    teardown
}

test_negative_control_amend_sweeps() {
    echo "=== Negative control: pre-fix amend DOES swallow (both mechanisms) ==="
    setup_project

    write_task aitasks/t10_primary.md
    write_task aitasks/t20_a.md
    write_task aitasks/t99_bystander.md
    git add -A
    git commit -m "Setup" --quiet

    # A clean amend target: HEAD carries only the primary, so the FIXED build
    # would permit the amend. Any sweeping here is the pre-fix defect alone.
    printf '\ncreated\n' >> aitasks/t10_primary.md
    git add aitasks/t10_primary.md
    git commit -m "ait: Add task t10: primary" --quiet

    install_prefix_commit_block || { teardown; return; }

    printf '\nconcurrent edit\n' >> aitasks/t99_bystander.md      # dirty, under aitasks/
    mkdir -p aiplans
    printf 'unrelated plan\n' > aiplans/p999_unrelated.md
    git add aiplans/p999_unrelated.md                              # staged, outside aitasks/

    bash .aitask-scripts/aitask_fold_mark.sh --commit-mode amend 10 20 >/dev/null 2>&1 || true

    assert_defect_present "pre-fix amend: broad add sweeps the dirty bystander" \
        _head_contains aitasks/t99_bystander.md
    assert_defect_present "pre-fix amend: pathspec-less amend takes the pre-staged plan" \
        _head_contains aiplans/p999_unrelated.md

    teardown
}

test_negative_control_amend() {
    echo "=== Negative control: pre-fix amend DOES rewrite a foreign HEAD ==="
    setup_project

    write_task aitasks/t10_primary.md
    write_task aitasks/t20_a.md
    write_task aitasks/t77_foreign.md
    git add -A
    git commit -m "Setup" --quiet

    printf '\ncreated\n' >> aitasks/t10_primary.md
    printf '\nforeign edit\n' >> aitasks/t77_foreign.md
    git add aitasks/t10_primary.md aitasks/t77_foreign.md
    git commit -m "ait: Add task t10: primary" --quiet

    install_prefix_commit_block || { teardown; return; }

    local before
    before=$(git rev-parse HEAD)
    bash .aitask-scripts/aitask_fold_mark.sh --commit-mode amend 10 20 >/dev/null 2>&1 || true

    assert_defect_present "bare amend rewrites HEAD despite the foreign file" \
        test "$before" != "$(git rev-parse HEAD)"
    assert_defect_present "foreign file is silently retained in the rewritten commit" \
        _head_contains aitasks/t77_foreign.md

    teardown
}

# =============================================================================
# t1733 — the HEAD probe FAILS CLOSED, both ways
# =============================================================================
# `git show --name-only` prints nothing both when it FAILS and when HEAD is a
# MERGE commit. The pre-fix probe absorbed both with `|| true`, so `foreign`
# stayed empty and _fold_amend_guard returned 0 — authorising a rewrite of a
# commit whose contents were never read. Measured before the fix: a merge HEAD
# was actually rewritten.
#
# Fixture preconditions are ASSERTED, not assumed. "git show printed nothing" is
# the symptom the guard keys on, and several unrelated fixture accidents produce
# it — a test that only asserts the refusal could be passing through a different
# empty-or-unreadable condition, proving nothing about merge commits, and its
# control could "observe the defect" with no merge commit involved at all.

# Number of parents of HEAD (2 == a merge commit); -1 if HEAD does not resolve.
_head_parent_count() {
    local line
    line="$(git rev-list --parents -n1 HEAD 2>/dev/null)" || { echo "-1"; return 0; }
    local -a parts=()
    read -r -a parts <<< "$line" || true
    echo $(( ${#parts[@]} - 1 ))
}

# The non-empty path lines `git show --name-only` prints for HEAD ("" for a merge).
_head_name_only_paths() { git show --name-only --format='' HEAD 2>/dev/null | sed '/^$/d'; }

_head_show_succeeds() { git show --name-only --format='' HEAD >/dev/null 2>&1; }

# Subshell body so the PATH override cannot leak into the caller.
_head_show_succeeds_shimmed() ( PATH="$FAKE_GIT_BIN:$PATH"; _head_show_succeeds; )

# Render a predicate's outcome as a comparable value for assert_eq.
_yn() { if "$@"; then echo yes; else echo no; fi; }

_contains_needle() { printf '%s' "$2" | grep -qF -- "$1"; }
_lacks_needle()    { ! _contains_needle "$1" "$2"; }

# The documented merge-output shape: HEAD really is a merge AND it really does
# print no path list. Both halves matter — the guard refuses on the empty list,
# so without the parent count the test would not be about merges at all.
assert_merge_head_fixture() {
    local desc="$1"
    assert_eq "$desc: HEAD is a merge (two parents)" "2" "$(_head_parent_count)"
    assert_eq "$desc: merge HEAD prints no paths" "" "$(_head_name_only_paths)"
}

assert_unreadable_head_fixture() {
    local desc="$1"
    assert_eq "$desc: git show HEAD fails" "no" "$(_yn _head_show_succeeds)"
    assert_eq "$desc: HEAD does not resolve" "-1" "$(_head_parent_count)"
}

# A `git` on PATH that fails ONLY the guard's HEAD path-list probe and hands
# everything else to the real binary. This is the one case where the amend WOULD
# have succeeded, so it is the only fixture that proves a failed probe does not
# authorise a rewrite — on an unborn branch the amend cannot succeed anyway.
# Lives outside the fixture repo so it cannot show up as a stray untracked path.
FAKE_GIT_BIN=""
install_failing_show_shim() {
    local real_git
    real_git="$(command -v git)"
    FAKE_GIT_BIN="$(dirname "$PWD")/fakebin"
    mkdir -p "$FAKE_GIT_BIN"
    cat > "$FAKE_GIT_BIN/git" <<EOF
#!/usr/bin/env bash
# Only \`git show … --name-only\` fails; the guard's probe is the sole call site
# combining those two, so nothing else in the fold is affected.
_has_show=0; _has_nameonly=0
for _a in "\$@"; do
    [[ "\$_a" == "show" ]] && _has_show=1
    [[ "\$_a" == "--name-only" ]] && _has_nameonly=1
done
if (( _has_show == 1 && _has_nameonly == 1 )); then
    echo "fatal: simulated object read failure" >&2
    exit 128
fi
exec "$real_git" "\$@"
EOF
    chmod +x "$FAKE_GIT_BIN/git"
}

# Rebuild the fixture's copy with the PRE-FIX probe: the status capture and both
# refusals removed, the loop fed from the `|| true` process substitution again.
# install_prefix_commit_block is unusable here — it excises the guard entirely,
# so it cannot tell the fail-open probe apart from having no guard at all.
install_prefix_amend_probe() {
    python3 - "$PWD/.aitask-scripts/aitask_fold_mark.sh" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()

start = '    local head_paths="" show_rc=0\n'
stop  = '    while IFS= read -r p; do\n'
fixed_loop_end  = '    done <<< "$head_paths"\n'
prefix_loop_end = "    done < <(task_git show --name-only --format='' HEAD 2>/dev/null || true)\n"

for anchor in (start, stop, fixed_loop_end):
    if anchor not in s:
        sys.stderr.write("FATAL: anchor has gone stale: %r\n" % anchor)
        sys.exit(1)

i = s.index(start)
j = s.index(stop, i)
s = s[:i] + s[j:]
s = s.replace(fixed_loop_end, prefix_loop_end, 1)
open(p, 'w').write(s)
PY
    # Prove the mutation landed. Without this the controls below could pass
    # vacuously against an unmutated build.
    local script=".aitask-scripts/aitask_fold_mark.sh"
    grep -q 'show_rc' "$script" \
        && { echo "FAIL: negative control left the status capture in place"; FAIL=$((FAIL+1)); TOTAL=$((TOTAL+1)); return 1; }
    grep -q 'head_paths' "$script" \
        && { echo "FAIL: negative control left the captured path list in place"; FAIL=$((FAIL+1)); TOTAL=$((TOTAL+1)); return 1; }
    grep -qF "done < <(task_git show --name-only --format='' HEAD 2>/dev/null || true)" "$script" \
        || { echo "FAIL: negative control did not install the fail-open probe"; FAIL=$((FAIL+1)); TOTAL=$((TOTAL+1)); return 1; }
    # Only the PROBE regresses — the rest of the guard must survive, or these
    # controls would be observing "no guard" rather than "fail-open guard".
    grep -q '^_fold_amend_guard() {' "$script" \
        || { echo "FAIL: negative control excised the amend guard itself"; FAIL=$((FAIL+1)); TOTAL=$((TOTAL+1)); return 1; }
    grep -qF 'carries paths outside this fold' "$script" \
        || { echo "FAIL: negative control excised the foreign-path refusal"; FAIL=$((FAIL+1)); TOTAL=$((TOTAL+1)); return 1; }
    TOTAL=$((TOTAL + 1)); PASS=$((PASS + 1))
    return 0
}

# HEAD is a real merge commit sitting on top of a normal amend target.
_setup_merge_head_fixture() {
    _setup_amend_fixture

    local orig_branch
    orig_branch="$(git rev-parse --abbrev-ref HEAD)"
    git checkout -q -b side HEAD~1
    printf 'side\n' > side.txt
    git add side.txt
    git commit -m "side" --quiet
    git checkout -q "$orig_branch"
    git merge -q --no-ff -m "merge side" side
}

# HEAD does not resolve at all: a fresh orphan branch has no commits.
_setup_unborn_head_fixture() {
    setup_project

    write_task aitasks/t10_primary.md
    write_task aitasks/t20_a.md
    git add -A
    git commit -m "Setup" --quiet

    FOLD_PATHS=( aitasks/t10_primary.md aitasks/t20_a.md )
    git checkout -q --orphan unborn
}

test_amend_refuses_merge_head() {
    echo "=== Test: amend REFUSES a MERGE HEAD (empty path list) ==="
    _setup_merge_head_fixture
    assert_merge_head_fixture "merge fixture"

    local before rc=0 output
    before=$(git rev-parse HEAD)
    output=$(bash .aitask-scripts/aitask_fold_mark.sh --commit-mode amend 10 20 2>&1) || rc=$?

    assert_eq "exits non-zero" "1" "$rc"
    assert_contains "error says HEAD reports no paths" "reports no paths" "$output"
    assert_contains "error points at fresh mode" "--commit-mode fresh" "$output"
    # The load-bearing half: the merge commit's history is intact.
    assert_eq "the merge commit was NOT rewritten" "$before" "$(git rev-parse HEAD)"
    assert_no_fold_residue "merge-HEAD refusal" "$before"
    assert_eq "folded task reverted to Ready" "Ready" \
        "$(read_frontmatter_field aitasks/t20_a.md status)"
    assert_eq "primary has no folded_tasks" "" \
        "$(read_frontmatter_field aitasks/t10_primary.md folded_tasks)"

    teardown
}

test_amend_refuses_unreadable_head() {
    echo "=== Test: amend REFUSES an unreadable HEAD (unborn branch) ==="
    _setup_unborn_head_fixture
    assert_unreadable_head_fixture "unborn fixture"

    local rc=0 output
    output=$(bash .aitask-scripts/aitask_fold_mark.sh --commit-mode amend 10 20 2>&1) || rc=$?

    assert_eq "exits non-zero" "1" "$rc"
    assert_contains "error says the HEAD contents are unverified" "unverified" "$output"
    assert_contains "error points at fresh mode" "--commit-mode fresh" "$output"
    # The discriminator. Pre-fix the guard PERMITTED and the run died later, on
    # the amend itself — same exit status, same rollback, wrong reason. Here the
    # refusal must come from the guard, before anything is staged.
    assert_not_contains "it did NOT fall through to the amend" \
        "amend-commit failed" "$output"
    assert_eq "folded task reverted to Ready" "Ready" \
        "$(read_frontmatter_field aitasks/t20_a.md status)"

    teardown
}

test_amend_refuses_failed_head_probe() {
    echo "=== Test: amend REFUSES a FAILED HEAD probe (would otherwise permit) ==="
    _setup_amend_fixture
    install_failing_show_shim

    # Precondition A: without the shim this is a HEAD the guard PERMITS — a
    # single-parent commit carrying only the fold's own primary.
    assert_eq "fixture: HEAD is a single-parent commit" "1" "$(_head_parent_count)"
    assert_eq "fixture: HEAD lists only the fold's own primary" \
        "aitasks/t10_primary.md" "$(_head_name_only_paths)"
    # Precondition B: under the shim the probe genuinely fails. With A, the only
    # difference from a permitted amend is the failed probe.
    assert_eq "fixture: the probe fails under the shim" "no" \
        "$(_yn _head_show_succeeds_shimmed)"

    local before rc=0 output
    before=$(git rev-parse HEAD)
    output=$(PATH="$FAKE_GIT_BIN:$PATH" bash .aitask-scripts/aitask_fold_mark.sh \
        --commit-mode amend 10 20 2>&1) || rc=$?

    assert_eq "exits non-zero" "1" "$rc"
    assert_contains "error says the HEAD contents are unverified" "unverified" "$output"
    assert_eq "HEAD was NOT rewritten" "$before" "$(git rev-parse HEAD)"
    assert_no_fold_residue "failed-probe refusal" "$before"
    assert_eq "folded task reverted to Ready" "Ready" \
        "$(read_frontmatter_field aitasks/t20_a.md status)"

    teardown
}

test_negative_control_merge_head_rewritten() {
    echo "=== Negative control: pre-fix amend DOES rewrite a merge HEAD ==="
    _setup_merge_head_fixture
    assert_merge_head_fixture "pre-fix merge fixture"
    install_prefix_amend_probe || { teardown; return; }

    local before
    before=$(git rev-parse HEAD)
    bash .aitask-scripts/aitask_fold_mark.sh --commit-mode amend 10 20 >/dev/null 2>&1 || true

    assert_defect_present "pre-fix: the merge commit IS rewritten" \
        test "$before" != "$(git rev-parse HEAD)"

    teardown
}

test_negative_control_failed_probe_amends() {
    echo "=== Negative control: pre-fix amend DOES proceed on a failed HEAD probe ==="
    _setup_amend_fixture
    install_failing_show_shim
    assert_eq "fixture: HEAD lists only the fold's own primary" \
        "aitasks/t10_primary.md" "$(_head_name_only_paths)"
    assert_eq "fixture: the probe fails under the shim" "no" \
        "$(_yn _head_show_succeeds_shimmed)"
    install_prefix_amend_probe || { teardown; return; }

    local before out
    before=$(git rev-parse HEAD)
    out=$(PATH="$FAKE_GIT_BIN:$PATH" bash .aitask-scripts/aitask_fold_mark.sh \
        --commit-mode amend 10 20 2>&1) || true

    assert_defect_present "pre-fix: the amend proceeds despite the unread HEAD" \
        _contains_needle "AMENDED" "$out"
    assert_defect_present "pre-fix: HEAD IS rewritten" \
        test "$before" != "$(git rev-parse HEAD)"

    teardown
}

test_negative_control_unborn_head_wrong_reason() {
    echo "=== Negative control: pre-fix gives the WRONG reason on an unreadable HEAD ==="
    _setup_unborn_head_fixture
    assert_unreadable_head_fixture "pre-fix unborn fixture"
    install_prefix_amend_probe || { teardown; return; }

    local out
    out=$(bash .aitask-scripts/aitask_fold_mark.sh --commit-mode amend 10 20 2>&1) || true

    # Pre-fix the guard permits, so the failure surfaces from the amend instead.
    assert_defect_present "pre-fix: the guard PERMITS and the amend fails instead" \
        _contains_needle "amend-commit failed" "$out"
    assert_defect_present "pre-fix: no 'unverified' guard refusal is emitted" \
        _lacks_needle "unverified" "$out"

    teardown
}

teardown_all() {
    local d
    for d in "${CLEANUP_DIRS[@]}"; do
        [[ -d "$d" ]] && rm -rf "$d"
    done
}
trap teardown_all EXIT

test_fresh_mode_full_flow
test_none_mode_no_commit
test_transitive

# t1599_2 — path-scoped commit + amend guard
test_fresh_dirty_bystander_not_swept
test_fresh_prestaged_foreign_not_swept
test_amend_dirty_bystander_not_swept
test_amend_prestaged_foreign_not_swept
test_amend_refuses_foreign_task_in_head
test_amend_refuses_unknown_metadata_in_head
test_amend_refuses_task_like_metadata_filename
test_amend_refuses_archived_and_misfiled_lookalikes
test_amend_permits_labels_file_in_head
test_amend_permits_child_primary_parent_file
test_amend_refuses_published_head
test_child_fold_commits_parent_file

# t1661 — records reach stdout only on a Step 6 terminal success
test_refused_amend_emits_no_records
test_fresh_commit_failure_emits_no_records
test_amend_commit_failure_emits_no_records
test_fresh_flush_order_preserved
test_amend_flush_order_preserved
test_fresh_verified_noop_flushes_records
test_abort_mid_mutation_rolls_back

# t1668 — the whole run is one transaction: every abort restores the exact
# pre-fold state (index + worktree), and the mode is validated before any of it
test_step6_rollback_preserves_dirty_entry
test_abort_preserves_pre_existing_dirty_primary
test_abort_preserves_pre_existing_staged_primary
test_abort_preserves_unmerged_index_stages
test_index_read_failure_aborts_before_mutating
test_abort_rolls_back_child_and_parent
test_invalid_commit_mode_rejected
test_invalid_commit_mode_precedes_resolution
test_attach_merge_failure_aborts_the_fold
test_attach_txn_nonzero_return_rolls_back
test_abort_inside_attach_txn_rolls_back

# Negative controls (must observe the defect against the pre-fix build)
test_fold_partial_restore_is_reported
test_fold_partial_prune_is_reported
test_fold_clean_rollback_still_claims_full
test_negative_control_no_abort_rollback
test_negative_control_fresh
test_negative_control_amend_sweeps
test_negative_control_amend
test_negative_control_unbuffered_on_refusal
test_negative_control_unbuffered_on_commit_failure
# t1707 — pairs test_attach_txn_nonzero_return_rolls_back: without the
# post-attach-lock re-arm (aitask_fold_mark.sh:820) the same scenario rolls
# back nothing, which is what makes that test's assertions mean something.
test_negative_control_attach_rearm_removed

# t1733 — the HEAD probe fails closed: an unreadable HEAD and a merge commit's
# empty path list both refuse instead of authorising a history rewrite
test_amend_refuses_merge_head
test_amend_refuses_unreadable_head
test_amend_refuses_failed_head_probe
test_negative_control_merge_head_rewritten
test_negative_control_failed_probe_amends
test_negative_control_unborn_head_wrong_reason

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
