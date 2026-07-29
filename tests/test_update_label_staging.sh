#!/usr/bin/env bash
# test_update_label_staging.sh - Integration tests for label vocabulary
# registration and commit hygiene on aitask_update.sh --batch (t1312).
#
# Covers:
#   - --add-label with a new label: registered, in the commit, worktree clean
#   - --labels (replace-all) with a new label: same (both ways of naming a
#     label grow the vocabulary identically)
#   - --labels "UI Stuff, Foo!" : frontmatter and vocabulary agree (normalized)
#   - a pre-existing label: labels.txt absent from the commit (no gratuitous
#     rewrite, no dirty worktree)
#   - a bare --status Done on a labeled task never touches labels.txt, AND does
#     not sweep an unrelated pending labels.txt edit into its commit (this is
#     the every-gate-transition / every-board-move path: its blast radius is
#     the whole system). The sweep case is what makes the staging guard
#     testable at all - staging an UNCHANGED file is a git no-op and no commit
#     assertion can see it.
#   - --remove-label does not unregister from the vocabulary
#   - --add-label with an EMBEDDED NEWLINE cannot split the YAML inline list or
#     desynchronize frontmatter from the vocabulary
#
# Run: bash tests/test_update_label_staging.sh

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
    cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_query_files.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true
    chmod +x .aitask-scripts/*.sh

    printf 'bug\nchore\ndocumentation\nenhancement\nfeature\nperformance\nrefactor\nstyle\ntest\n' > aitasks/metadata/task_types.txt
    printf 'preexisting_label\n' > "$VOCAB"
    echo "aitasks/new/" > .gitignore

    cat > aitasks/t42_sample.md <<'EOF'
---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [preexisting_label]
created_at: 2026-01-01 10:00
updated_at: 2026-01-01 10:00
---

Sample task.
EOF

    git add -A
    git commit -m "Initial setup" --quiet
    git push --quiet 2>/dev/null || true
}

teardown() { popd > /dev/null 2>&1 || true; }

labels_line()  { grep -m1 '^labels:' aitasks/t42_sample.md; }
head_files()   { git show --name-only --pretty=format: HEAD | grep -v '^$' | sort | tr '\n' ' '; }

frontmatter_not_in_vocab() {
    local raw missing=""
    raw=$(labels_line | sed 's/^labels: *//' | tr -d '[]' | tr ',' '\n')
    while IFS= read -r l; do
        l="$(printf '%s' "$l" | xargs)"
        [[ -z "$l" ]] && continue
        grep -qFx -- "$l" "$VOCAB" || missing="${missing}${l} "
    done <<< "$raw"
    printf '%s' "$missing"
}

run_update() {
    bash .aitask-scripts/aitask_update.sh --batch 42 --commit "$@" >/dev/null 2>&1
}

# --- Test 1: --add-label with a new label ----------------------------------

test_add_label_new() {
    echo "=== Test: --add-label registers, commits, leaves the worktree clean ==="
    setup_project

    run_update --add-label "fresh_from_add"

    assert_eq "label registered" "1" "$(grep -c '^fresh_from_add$' "$VOCAB")"
    assert_contains "frontmatter carries the label" "fresh_from_add" "$(labels_line)"
    assert_contains "commit contains labels.txt" "$VOCAB" "$(head_files)"
    assert_contains "commit contains the task file" "aitasks/t42_sample.md" "$(head_files)"
    assert_eq "worktree clean (labels.txt not left dirty)" "" "$(git status --porcelain)"
    assert_eq "frontmatter is a subset of the vocabulary" "" "$(frontmatter_not_in_vocab)"

    teardown
}

# --- Test 2: --labels replace-all with a new label -------------------------

test_labels_replace_all_new() {
    echo "=== Test: --labels (replace-all) registers and commits ==="
    setup_project

    run_update --labels "fresh_from_replace,preexisting_label"

    assert_eq "new label registered" "1" "$(grep -c '^fresh_from_replace$' "$VOCAB")"
    assert_contains "commit contains labels.txt" "$VOCAB" "$(head_files)"
    assert_eq "worktree clean" "" "$(git status --porcelain)"
    assert_eq "frontmatter is a subset of the vocabulary" "" "$(frontmatter_not_in_vocab)"

    teardown
}

# --- Test 3: non-canonical --labels normalizes both sides ------------------

test_labels_normalized() {
    echo "=== Test: non-canonical --labels keeps frontmatter and vocabulary in agreement ==="
    setup_project

    run_update --labels "UI Stuff, Foo!"

    assert_eq "frontmatter is normalized" "labels: [ui_stuff, foo]" "$(labels_line)"
    assert_eq "frontmatter is a subset of the vocabulary" "" "$(frontmatter_not_in_vocab)"
    assert_eq "ui_stuff registered" "1" "$(grep -c '^ui_stuff$' "$VOCAB")"
    assert_eq "raw 'UI Stuff' NOT registered" "0" "$(grep -c '^UI Stuff$' "$VOCAB" || true)"
    assert_eq "worktree clean" "" "$(git status --porcelain)"

    teardown
}

# --- Test 4: pre-existing label leaves labels.txt out of the commit --------

test_preexisting_label_not_recommitted() {
    echo "=== Test: a pre-existing label is not re-committed ==="
    setup_project

    local before
    before=$(cksum < "$VOCAB")

    run_update --add-label "preexisting_label"

    assert_eq "vocabulary byte-identical" "$before" "$(cksum < "$VOCAB")"
    assert_not_contains "commit does NOT contain labels.txt" "$VOCAB" "$(head_files)"
    assert_eq "worktree clean" "" "$(git status --porcelain)"

    teardown
}

# --- Test 5: an unrelated update never touches labels.txt ------------------

test_unrelated_update_never_touches_vocab() {
    echo "=== Test: a bare --status update never touches labels.txt ==="
    setup_project

    local before
    before=$(cksum < "$VOCAB")

    run_update --status Done

    assert_eq "vocabulary byte-identical after a bare --status" \
        "$before" "$(cksum < "$VOCAB")"
    assert_not_contains "status commit does NOT contain labels.txt" "$VOCAB" "$(head_files)"
    assert_contains "status commit contains the task file" "aitasks/t42_sample.md" "$(head_files)"
    assert_eq "worktree clean" "" "$(git status --porcelain)"

    teardown
}

# --- Test 5b: an unrelated update does not sweep up a dirty labels.txt -----
#
# THE discriminating case for the staging guard. `git add` on an UNCHANGED file
# stages nothing, so an unguarded `task_git add "$LABELS_FILE"` is invisible
# whenever labels.txt happens to be clean. Seed a pending, unrelated edit
# first: an unguarded add then sweeps a stranger's work-in-progress into this
# task's commit.

test_unrelated_update_does_not_sweep_dirty_vocab() {
    echo "=== Test: a bare --status update does not sweep up a dirty labels.txt ==="
    setup_project

    # Out-of-band edit, as another session or a manual edit would leave it.
    printf 'someone_elses_pending_label\n' >> "$VOCAB"

    run_update --status Done

    assert_not_contains "status commit does NOT contain the dirty labels.txt" \
        "$VOCAB" "$(head_files)"
    assert_contains "the unrelated edit is still pending in the worktree" \
        "$VOCAB" "$(git status --porcelain)"
    assert_eq "the unrelated edit is still on disk" "1" \
        "$(grep -c '^someone_elses_pending_label$' "$VOCAB")"

    teardown
}

# --- Test 6: --remove-label does not unregister ---------------------------

test_remove_label_does_not_unregister() {
    echo "=== Test: --remove-label leaves the vocabulary entry in place ==="
    setup_project

    local before
    before=$(cksum < "$VOCAB")

    run_update --remove-label "preexisting_label"

    assert_not_contains "frontmatter no longer carries the label" \
        "preexisting_label" "$(labels_line)"
    assert_eq "vocabulary still holds the label" "1" \
        "$(grep -c '^preexisting_label$' "$VOCAB")"
    assert_eq "vocabulary byte-identical" "$before" "$(cksum < "$VOCAB")"
    assert_eq "worktree clean" "" "$(git status --porcelain)"

    teardown
}

# --- Test 7: an embedded newline cannot corrupt frontmatter or desync ------
#
# Regression: sed is line-oriented, so a newline inside a --add-label argument
# used to survive sanitization. The frontmatter became a two-line
# `labels: [...]` inline list (YAML folds it to the space-bearing label
# "alpha beta") while the CSV registration, reading only the first line,
# recorded just "alpha" — a silent frontmatter/vocabulary mismatch.

test_embedded_newline_label() {
    echo "=== Test: an embedded newline is folded, not propagated ==="
    setup_project

    run_update --add-label "$(printf 'alpha\nbeta')"

    local labels
    labels=$(labels_line)
    assert_eq "labels: stays a single physical line" "1" \
        "$(grep -c '^labels:' aitasks/t42_sample.md)"
    assert_contains "the newline is folded to _" "alpha_beta" "$labels"
    assert_not_contains "no space-bearing label reaches frontmatter" "alpha beta" "$labels"
    assert_eq "the folded label is registered" "1" "$(grep -c '^alpha_beta$' "$VOCAB")"
    assert_eq "no truncated half is registered" "0" "$(grep -c '^alpha$' "$VOCAB" || true)"
    assert_eq "frontmatter is a subset of the vocabulary" "" "$(frontmatter_not_in_vocab)"
    assert_eq "the vocabulary gained exactly one line" "2" "$(wc -l < "$VOCAB" | xargs)"

    # --labels must not silently drop everything after a newline either.
    run_update --labels "$(printf 'a\nb,c')"
    assert_eq "--labels keeps every token across a newline" "labels: [a_b, c]" "$(labels_line)"
    assert_eq "frontmatter is a subset of the vocabulary" "" "$(frontmatter_not_in_vocab)"

    teardown
}

teardown_all() {
    local d
    for d in "${CLEANUP_DIRS[@]}"; do
        [[ -d "$d" ]] && rm -rf "$d"
    done
}
trap teardown_all EXIT

test_add_label_new
test_labels_replace_all_new
test_labels_normalized
test_preexisting_label_not_recommitted
test_unrelated_update_never_touches_vocab
test_unrelated_update_does_not_sweep_dirty_vocab
test_remove_label_does_not_unregister
test_embedded_newline_label

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="

[[ "$FAIL" -eq 0 ]] || exit 1
