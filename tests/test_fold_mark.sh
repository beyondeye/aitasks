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
#     roll back and print nothing. An abort BEFORE Step 6 also prints nothing --
#     and its RESIDUAL is pinned too: that path rolls back nothing, so the
#     mutations stay on disk uncommitted and the non-zero EXIT STATUS, not the
#     empty record set, is what says so.
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

test_abort_mid_mutation_emits_no_records() {
    echo "=== Test: t1661 — an abort before Step 6 emits no records ==="
    setup_project

    write_task aitasks/t10_primary.md
    git add -A
    git commit -m "Setup" --quiet

    # A folded id with no task file: Step 3 updates the primary, then Step 4's
    # aitask_update.sh for the missing id exits non-zero and `set -e` kills the
    # script BEFORE Step 6. The buffer is never flushed, so stdout stays empty.
    _run_fold_split --commit-mode fresh 10 9999

    assert_eq "exits non-zero" "1" "$FOLD_RC"
    assert_eq "stdout is empty" "" "$FOLD_OUT"
    assert_no_records "pre-Step-6 abort" "$FOLD_OUT"
    assert_contains "stderr names the missing task" "9999" "$FOLD_ERR"

    # ...and the documented RESIDUAL, pinned so nobody mistakes silence for
    # "nothing happened": this path rolls back nothing, so the Step 3 mutation
    # is still on disk, uncommitted. The non-zero exit status is what tells the
    # caller to reconcile. Making this transactional is out of scope for the
    # output contract — it needs rollback_paths assembled before Step 3.
    assert_eq "residual: the Step 3 mutation is still on disk" "[9999]" \
        "$(read_frontmatter_field aitasks/t10_primary.md folded_tasks)"
    assert_status_code "residual: dirty in the worktree, never committed" \
        " M" aitasks/t10_primary.md

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
end = s.index('esac\n', s.index('die "invalid --commit-mode: $commit_mode"')) + len('esac\n')
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
    grep -q '_fold_amend_guard' .aitask-scripts/aitask_fold_mark.sh \
        && { echo "FAIL: negative control left the amend guard in place"; FAIL=$((FAIL+1)); TOTAL=$((TOTAL+1)); return 1; }
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
test_abort_mid_mutation_emits_no_records

# Negative controls (must observe the defect against the pre-fix build)
test_negative_control_fresh
test_negative_control_amend_sweeps
test_negative_control_amend
test_negative_control_unbuffered_on_refusal
test_negative_control_unbuffered_on_commit_failure

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
