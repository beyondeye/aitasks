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

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="

[[ "$FAIL" -eq 0 ]] || exit 1
