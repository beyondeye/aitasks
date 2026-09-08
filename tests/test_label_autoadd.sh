#!/usr/bin/env bash
# test_label_autoadd.sh - Integration tests for label vocabulary auto-add on
# the aitask_create.sh --batch paths (t1312).
#
# Covers:
#   - a brand-new label lands in aitasks/metadata/labels.txt AND in the
#     task-creation commit, on the PARENT and the CHILD path (a parent-only fix
#     would pass the parent case and silently miss the child one)
#   - every frontmatter label is a subset of the vocabulary
#   - a pre-existing label is not duplicated, and labels.txt is absent from that
#     creation commit (no gratuitous rewrite)
#   - --labels "" is a total no-op (guards test_create_manual_verification_gates.sh)
#   - --labels "UI Stuff, Backend" -> frontmatter [ui_stuff, backend], agreeing
#     with the vocabulary
#   - --labels ",,!!!" -> exit 0, stderr warning, labels: [], vocabulary untouched
#   - a draft writes nothing; --finalize registers and commits the vocabulary
#   - --silent stdout stays exactly one line (create.sh's own caller and
#     aitask_verification_followup.sh parse it)
#   - an EMBEDDED NEWLINE in --labels neither truncates the token list nor
#     splits the YAML inline list
#
# Run: bash tests/test_label_autoadd.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

VOCAB="aitasks/metadata/labels.txt"

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

    mkdir -p aitasks/metadata aitasks/new aitasks/archived
    setup_fake_aitask_repo "$PWD"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_create.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_query_files.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true
    chmod +x .aitask-scripts/*.sh

    printf 'bug\nchore\ndocumentation\nenhancement\nfeature\nperformance\nrefactor\nstyle\ntest\n' > aitasks/metadata/task_types.txt
    # A committed pre-existing entry: the "not duplicated / not re-committed"
    # assertions are vacuous against an empty vocabulary.
    printf 'preexisting_label\n' > "$VOCAB"
    echo "aitasks/new/" > .gitignore

    git add -A
    git commit -m "Initial setup" --quiet
    git push --quiet 2>/dev/null || true

    ./.aitask-scripts/aitask_claim_id.sh --init >/dev/null 2>&1 || true
}

teardown() { popd > /dev/null 2>&1 || true; }

labels_line()  { grep -m1 '^labels:' "$1"; }
head_files()   { git show --name-only --pretty=format: HEAD | grep -v '^$' | sort | tr '\n' ' '; }
parent_id_of() { local b; b=$(basename "$1" .md); printf '%s' "${b%%_*}"; }

# Every frontmatter label must exist in the vocabulary. Echoes the offenders.
frontmatter_not_in_vocab() {
    local file="$1" raw missing=""
    raw=$(labels_line "$file" | sed 's/^labels: *//' | tr -d '[]' | tr ',' '\n')
    while IFS= read -r l; do
        l="$(printf '%s' "$l" | xargs)"
        [[ -z "$l" ]] && continue
        grep -qFx -- "$l" "$VOCAB" || missing="${missing}${l} "
    done <<< "$raw"
    printf '%s' "$missing"
}

# --- Test 1: parent path, brand-new label ----------------------------------

test_parent_new_label() {
    echo "=== Test: parent path registers and commits a new label ==="
    setup_project

    local f
    f=$(bash .aitask-scripts/aitask_create.sh --batch --commit --silent \
            --name par_new --desc x --labels "brand_new_label" 2>/dev/null)

    assert_file_exists "parent task created" "$f"
    assert_eq "frontmatter carries the label" "labels: [brand_new_label]" "$(labels_line "$f")"
    assert_eq "label registered in the vocabulary" "1" \
        "$(grep -c '^brand_new_label$' "$VOCAB")"
    assert_contains "creation commit contains labels.txt" "$VOCAB" "$(head_files)"
    assert_contains "creation commit contains the task file" "$f" "$(head_files)"
    assert_eq "frontmatter is a subset of the vocabulary" "" "$(frontmatter_not_in_vocab "$f")"
    assert_eq "worktree clean after creation" "" "$(git status --porcelain)"

    teardown
}

# --- Test 2: child path, brand-new label -----------------------------------

test_child_new_label() {
    echo "=== Test: child path registers and commits a new label ==="
    setup_project

    local parent_file parent_num f
    parent_file=$(bash .aitask-scripts/aitask_create.sh --batch --commit --silent \
                      --name par --desc x 2>/dev/null)
    parent_num=$(parent_id_of "$parent_file"); parent_num="${parent_num#t}"

    f=$(bash .aitask-scripts/aitask_create.sh --batch --commit --silent \
            --parent "$parent_num" --name kid --desc x \
            --labels "child_only_label" 2>/dev/null)

    assert_file_exists "child task created" "$f"
    assert_eq "child frontmatter carries the label" "labels: [child_only_label]" "$(labels_line "$f")"
    assert_eq "child label registered in the vocabulary" "1" \
        "$(grep -c '^child_only_label$' "$VOCAB")"
    assert_contains "child creation commit contains labels.txt" "$VOCAB" "$(head_files)"
    assert_eq "child frontmatter is a subset of the vocabulary" "" "$(frontmatter_not_in_vocab "$f")"
    assert_eq "worktree clean after child creation" "" "$(git status --porcelain)"

    teardown
}

# --- Test 3: pre-existing label is not duplicated or re-committed ----------

test_preexisting_label() {
    echo "=== Test: pre-existing label is neither duplicated nor re-committed ==="
    setup_project

    local before f
    before=$(cksum < "$VOCAB")

    f=$(bash .aitask-scripts/aitask_create.sh --batch --commit --silent \
            --name par_pre --desc x --labels "preexisting_label" 2>/dev/null)

    assert_eq "label still appears exactly once" "1" \
        "$(grep -c '^preexisting_label$' "$VOCAB")"
    assert_eq "vocabulary byte-identical" "$before" "$(cksum < "$VOCAB")"
    assert_not_contains "creation commit does NOT contain labels.txt" "$VOCAB" "$(head_files)"
    assert_contains "creation commit contains the task file" "$f" "$(head_files)"

    teardown
}

# --- Test 4: normalization agreement, empty input, all-invalid input -------

test_normalization_and_edges() {
    echo "=== Test: normalization agreement and edge inputs ==="
    setup_project

    local before f out rc err

    # 4a. "UI Stuff, Backend" -> [ui_stuff, backend], agreeing with vocabulary.
    f=$(bash .aitask-scripts/aitask_create.sh --batch --commit --silent \
            --name par_norm --desc x --labels "UI Stuff, Backend" 2>/dev/null)
    assert_eq "non-canonical input is normalized in frontmatter" \
        "labels: [ui_stuff, backend]" "$(labels_line "$f")"
    assert_eq "normalized frontmatter agrees with the vocabulary" "" \
        "$(frontmatter_not_in_vocab "$f")"

    # 4b. --labels "" is a total no-op.
    before=$(cksum < "$VOCAB")
    f=$(bash .aitask-scripts/aitask_create.sh --batch --commit --silent \
            --name par_empty --desc x --labels "" 2>/dev/null)
    assert_eq "empty --labels emits an empty list" "labels: []" "$(labels_line "$f")"
    assert_eq "empty --labels leaves the vocabulary byte-identical" \
        "$before" "$(cksum < "$VOCAB")"
    assert_not_contains "empty --labels keeps labels.txt out of the commit" \
        "$VOCAB" "$(head_files)"

    # 4bb. An embedded newline must not truncate the CSV (`read` takes one
    # line) nor split the emitted inline list across two physical lines.
    f=$(bash .aitask-scripts/aitask_create.sh --batch --commit --silent \
            --name par_nl --desc x --labels "$(printf 'a\nb,c')" 2>/dev/null)
    assert_eq "embedded newline is folded, no token dropped" \
        "labels: [a_b, c]" "$(labels_line "$f")"
    assert_eq "labels: stays a single physical line" "1" "$(grep -c '^labels:' "$f")"
    assert_eq "newline-folded frontmatter agrees with the vocabulary" "" \
        "$(frontmatter_not_in_vocab "$f")"

    # 4c. All-invalid CSV: warn + drop, still exit 0.
    before=$(cksum < "$VOCAB")
    set +e
    err=$(bash .aitask-scripts/aitask_create.sh --batch --commit --silent \
              --name par_junk --desc x --labels ",,!!!" 2>&1 >/dev/null)
    rc=$?
    out=$(bash .aitask-scripts/aitask_create.sh --batch --commit --silent \
              --name par_junk2 --desc x --labels ",,!!!" 2>/dev/null)
    set -e
    assert_exit_zero_rc "all-invalid --labels still exits 0" "$rc"
    assert_contains_ci "all-invalid --labels warns on stderr" "label" "$err"
    assert_eq "all-invalid --labels emits an empty list" "labels: []" "$(labels_line "$out")"
    assert_eq "all-invalid --labels leaves the vocabulary byte-identical" \
        "$before" "$(cksum < "$VOCAB")"

    teardown
}

# --- Test 5: draft defers the vocabulary write to --finalize ---------------

test_draft_defers_to_finalize() {
    echo "=== Test: draft writes nothing; --finalize registers and commits ==="
    setup_project

    local before draft final
    before=$(cksum < "$VOCAB")

    draft=$(bash .aitask-scripts/aitask_create.sh --batch --silent \
                --name drafted --desc x --labels "draft_only_label" 2>/dev/null)
    assert_file_exists "draft created" "$draft"
    assert_eq "draft leaves the vocabulary byte-identical" "$before" "$(cksum < "$VOCAB")"
    assert_eq "draft registers nothing" "0" "$(grep -c '^draft_only_label$' "$VOCAB" || true)"

    final=$(bash .aitask-scripts/aitask_create.sh --batch --silent \
                --finalize "$(basename "$draft")" 2>/dev/null)
    assert_file_exists "draft finalized" "$final"
    assert_eq "finalize registers the label" "1" "$(grep -c '^draft_only_label$' "$VOCAB")"
    assert_contains "finalize commit contains labels.txt" "$VOCAB" "$(head_files)"
    assert_eq "worktree clean after finalize" "" "$(git status --porcelain)"

    teardown
}

# --- Test 6: --silent stdout stays exactly one line ------------------------

test_silent_stdout_single_line() {
    echo "=== Test: --silent stdout is exactly one line ==="
    setup_project

    local out lines
    out=$(bash .aitask-scripts/aitask_create.sh --batch --commit --silent \
              --name par_silent --desc x --labels "silent_new_label" 2>/dev/null)
    lines=$(printf '%s\n' "$out" | wc -l)
    assert_eq_trim "--silent prints exactly one stdout line" "1" "$lines"
    assert_file_exists "the single line is the created path" "$out"

    teardown
}

# --- t1599_4 / t1662: labels.txt must not ride along -----------------------
#
# THE DISCRIMINATING SEED IS A DIRTY labels.txt. `git add` on an UNCHANGED file
# stages nothing, which is exactly why Test 3 above passes against the pre-fix
# code and cannot see this bug. Every case below dirties the vocabulary first, to
# stand in for a concurrent session that appended a label and has not committed.
FOREIGN_LABEL="someone_elses_pending_label"
dirty_vocab() { printf '%s\n' "$FOREIGN_LABEL" >> "$VOCAB"; }

files_in() { git show --name-only --pretty=format: "$1" | grep -v '^$' | sort | tr '\n' ' '; }

# Shared assertions for "this creation must not have swallowed the foreign edit".
assert_foreign_edit_survived() {   # <label-prefix> <commit-files>
    local tag="$1" commit_files="$2"
    assert_not_contains "$tag: commit does NOT contain labels.txt" \
        "aitasks/metadata/labels.txt" "$commit_files"
    assert_contains "$tag: foreign edit is still pending" \
        "$VOCAB" "$(git status --porcelain -- "$VOCAB")"
    assert_contains "$tag: foreign label is still on disk" \
        "$FOREIGN_LABEL" "$(cat "$VOCAB")"
}

# --- T7: batch parent, already-known label, dirty vocabulary ---------------
test_batch_parent_does_not_sweep_dirty_vocab() {
    echo "=== T7: batch parent with a known label leaves a dirty labels.txt alone ==="
    setup_project
    dirty_vocab

    local f
    f=$(bash .aitask-scripts/aitask_create.sh --batch --commit --silent \
            --name t7_parent --desc x --labels "preexisting_label" 2>/dev/null)
    assert_file_exists "T7: task file created" "$f"
    local commit_files; commit_files=$(head_files)
    assert_contains "T7: commit contains the task file" "$f" "$commit_files"
    assert_foreign_edit_survived "T7" "$commit_files"

    teardown
}

# --- T8: batch child — a parent-only fix passes T7 and misses this ---------
test_batch_child_does_not_sweep_dirty_vocab() {
    echo "=== T8: batch child with a known label leaves a dirty labels.txt alone ==="
    setup_project

    local parent
    parent=$(bash .aitask-scripts/aitask_create.sh --batch --commit --silent \
                 --name t8_parent --desc x 2>/dev/null)
    local pid; pid=$(parent_id_of "$parent"); pid="${pid#t}"

    dirty_vocab
    local child
    child=$(bash .aitask-scripts/aitask_create.sh --batch --commit --silent \
                --parent "$pid" --name t8_child --desc x --labels "preexisting_label" 2>/dev/null)
    assert_file_exists "T8: child file created" "$child"
    local commit_files; commit_files=$(head_files)
    assert_contains "T8: commit contains the child file" "$child" "$commit_files"
    assert_foreign_edit_survived "T8" "$commit_files"

    teardown
}

# --- T9: the finalize path (a different pair of commit sites) --------------
test_finalize_does_not_sweep_dirty_vocab() {
    echo "=== T9: --finalize with a known label leaves a dirty labels.txt alone ==="
    setup_project

    local draft
    draft=$(bash .aitask-scripts/aitask_create.sh --batch --silent \
                --name t9_parent --desc x --labels "preexisting_label" 2>/dev/null)
    dirty_vocab
    local f
    f=$(bash .aitask-scripts/aitask_create.sh --batch --silent --finalize "$draft" 2>/dev/null)
    assert_file_exists "T9: finalized file exists" "$f"
    assert_foreign_edit_survived "T9" "$(head_files)"

    teardown
}

# --- T10: the cross-draft stale signal (the _register_task_labels reset) ---
#
# The naive two-draft version does NOT discriminate: draft A's commit would leave
# labels.txt clean, so draft B's stale-signal add is a no-op on an unchanged file.
# A post-commit hook injects a foreign append AFTER THE FIRST COMMIT ONLY, so the
# vocabulary is dirty exactly when draft B is committed. Draft B carries no labels
# at all, so labels.txt must not appear in its commit — it only can if B read a
# stale AIT_LABELS_ADDED left behind by A.
test_finalize_all_no_stale_label_signal() {
    echo "=== T10: a later draft does not inherit an earlier draft's label signal ==="
    setup_project

    # Draft A carries a NEW label; draft B carries none. Names pin the glob order.
    bash .aitask-scripts/aitask_create.sh --batch --silent \
        --name aaa_first --desc x --labels "t10_brand_new" >/dev/null 2>&1
    bash .aitask-scripts/aitask_create.sh --batch --silent \
        --name zzz_second --desc x >/dev/null 2>&1

    # Hooks live in the COMMON git dir, which a .aitask-data worktree also shares.
    local hookdir; hookdir="$(git rev-parse --git-dir)/hooks"
    mkdir -p "$hookdir"
    cat > "$hookdir/post-commit" <<HOOKEOF
#!/bin/sh
marker="\$(git rev-parse --git-dir)/.t10_fired"
[ -e "\$marker" ] && exit 0
: > "\$marker"
printf '%s\n' "$FOREIGN_LABEL" >> "$VOCAB"
exit 0
HOOKEOF
    chmod +x "$hookdir/post-commit"

    bash .aitask-scripts/aitask_create.sh --batch --silent --finalize-all >/dev/null 2>&1
    rm -f "$hookdir/post-commit"

    # HEAD is draft B's commit (it finalized second).
    local b_files; b_files=$(head_files)
    assert_contains "T10: HEAD is the second draft's commit" "zzz_second" "$b_files"
    assert_not_contains "T10: the label-less draft did NOT commit labels.txt" \
        "aitasks/metadata/labels.txt" "$b_files"
    assert_contains "T10: the injected foreign label is still uncommitted" \
        "$FOREIGN_LABEL" "$(cat "$VOCAB")"

    teardown
}

# --- T11: a PRE-STAGED foreign edit is not absorbed either -----------------
#
# Asserted in its SAFE form only. The staging gate alone cannot fix this case
# (refraining from `git add` changes nothing once another session has staged the
# file) — it is closed by the pathspec on the commit. Both land together, so
# there is no interim state in which absorption would be correct and no
# characterization of today's behaviour is committed.
test_prestaged_foreign_edit_not_absorbed() {
    echo "=== T11: a foreign labels.txt edit that is ALREADY STAGED is not absorbed ==="
    setup_project
    dirty_vocab
    git add -- "$VOCAB"          # the other session staged it

    local f
    f=$(bash .aitask-scripts/aitask_create.sh --batch --commit --silent \
            --name t11_parent --desc x --labels "preexisting_label" 2>/dev/null)
    local commit_files; commit_files=$(head_files)
    assert_contains "T11: commit contains the task file" "$f" "$commit_files"
    assert_not_contains "T11: pre-staged labels.txt is NOT in the commit" \
        "aitasks/metadata/labels.txt" "$commit_files"
    assert_contains "T11: the foreign label is still on disk" \
        "$FOREIGN_LABEL" "$(cat "$VOCAB")"

    teardown
}

# --- T12: co-change POSITIVE controls (post-phase risk mitigation) ---------
#
# The permit direction of the scoping. These pass before and after the fix by
# construction — their job is to fail if the pathspec is drawn too tight. Tests
# 1, 2 and 5 already cover "a genuinely new label IS committed"; the child's
# parent file is the co-change a naive "only the task file" pathspec would drop.
test_cochange_positive_controls() {
    echo "=== T12: legitimate co-changes still land in the commit ==="
    setup_project

    local parent
    parent=$(bash .aitask-scripts/aitask_create.sh --batch --commit --silent \
                 --name t12_parent --desc x 2>/dev/null)
    local pid; pid=$(parent_id_of "$parent"); pid="${pid#t}"

    local child
    child=$(bash .aitask-scripts/aitask_create.sh --batch --commit --silent \
                --parent "$pid" --name t12_child --desc x --labels "t12_brand_new" 2>/dev/null)
    local commit_files; commit_files=$(head_files)

    assert_contains "T12: child creation commits the child file" "$child" "$commit_files"
    assert_contains "T12: child creation ALSO commits the parent file (children_to_implement)" \
        "$parent" "$commit_files"
    assert_contains "T12: a genuinely new label DOES commit labels.txt" \
        "aitasks/metadata/labels.txt" "$commit_files"
    assert_eq_trim "T12: nothing left dirty" "" "$(git status --porcelain)"

    teardown
}

teardown_all() {
    local d
    for d in "${CLEANUP_DIRS[@]}"; do
        [[ -d "$d" ]] && rm -rf "$d"
    done
}
trap teardown_all EXIT

test_parent_new_label
test_child_new_label
test_preexisting_label
test_normalization_and_edges
test_draft_defers_to_finalize
test_silent_stdout_single_line
test_batch_parent_does_not_sweep_dirty_vocab
test_batch_child_does_not_sweep_dirty_vocab
test_finalize_does_not_sweep_dirty_vocab
test_finalize_all_no_stale_label_signal
test_prestaged_foreign_edit_not_absorbed
test_cochange_positive_controls

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="

[[ "$FAIL" -eq 0 ]] || exit 1
