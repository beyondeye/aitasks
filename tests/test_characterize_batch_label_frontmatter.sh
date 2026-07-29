#!/usr/bin/env bash
# test_characterize_batch_label_frontmatter.sh - CHARACTERIZATION test
# (t1321, flipped by t1312).
#
# Pins the `labels:` frontmatter emitted by `aitask_create.sh --batch --labels
# ...` across all three creation paths, plus the two vocabulary side-effect
# facts. t1312 inserted a `normalize_labels_csv` pass (trim, lowercase,
# sanitize, dedupe, drop-empties) ahead of `format_yaml_list`
# (lib/task_utils.sh) and made the committed paths register new labels in
# aitasks/metadata/labels.txt.
#
# Paths covered:
#   parent - create_task_file       (batch site: run_batch_mode parent branch)
#   child  - create_child_task_file (batch site: run_batch_mode child branch)
#   draft  - create_draft_file      (no --commit, gitignored)
#
# >>> FLIP RECORD (t1321 -> t1312) <<<
# Case 1 (`ui,backend`) is canonical and did NOT move, as designed. The
# non-canonical cases each moved exactly once:
#   2 `ui, backend`       [ui,  backend]        -> [ui, backend]   (trim)
#   3 `UI Stuff,foo-bar!` [UI Stuff, foo-bar!]  -> [ui_stuff, foo-bar]
#   5 `foo,FOO,foo`       [foo, FOO, foo]       -> [foo]           (dedupe)
#   6 `!!!`               [!!!]                 -> []              (drop)
# Side-effect facts flipped for the two COMMITTED paths only:
#   - labels.txt is rewritten whenever the case contributes a label the
#     vocabulary does not already hold (CASE_VOCAB_GROWS below)
#   - the creation commit then contains labels.txt alongside the task file
# The draft path is unchanged: drafts are gitignored, so the vocabulary write
# is deferred to `--finalize` (covered by tests/test_label_autoadd.sh).
#
# Run: bash tests/test_characterize_batch_label_frontmatter.sh

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

# Assertion-count tripwire. The negative control run at implementation time
# proves the wiring discriminates ONCE; this constant makes that guarantee
# repeatable - a later refactor that deletes or short-circuits assertions would
# otherwise still print a green "0 failed".
# 6 cases x (5 parent + 5 child + 4 draft) + 3 preconditions + 1 parent-create
EXPECTED_ASSERTIONS=88

# --- The pinned matrix -----------------------------------------------------
# Parallel arrays (bash 3.2: no associative arrays). CASE_IN[i] is passed
# verbatim to --labels; CASE_OUT[i] is the exact emitted frontmatter line.
CASE_IN=(
    "ui,backend"
    "ui, backend"
    "UI Stuff,foo-bar!"
    ""
    "foo,FOO,foo"
    "!!!"
)
CASE_OUT=(
    "labels: [ui, backend]"
    "labels: [ui, backend]"
    "labels: [ui_stuff, foo-bar]"
    "labels: []"
    "labels: [foo]"
    "labels: []"
)
CASE_WHY=(
    "canonical"
    "leading space trimmed"
    "case-folded and sanitized (space -> _, ! stripped from the tail)"
    "empty input"
    "deduped (exact-dup + case-fold-dup collapse to one)"
    "all-invalid token dropped (warn + drop, still exit 0)"
)
# Does this case contribute a label the vocabulary does not already hold, given
# the cases before it in the same fixture ran first? Drives both side-effect
# assertions. Case 2 repeats case 1's labels; cases 4 and 6 contribute none.
CASE_VOCAB_GROWS=(1 0 1 0 1 0)

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
    # Discriminating sentinel: none of the labels this test passes appear here,
    # so ANY write by the batch path (append + `sort -u`) changes the file. An
    # empty labels.txt would pass the "untouched" assertion vacuously for some
    # write shapes.
    # MUST stay ABOVE the `git add -A` / `git commit` below - see
    # assert_clean_baseline().
    printf 'zzz_sentinel_preexisting\n' > aitasks/metadata/labels.txt
    echo "aitasks/new/" > .gitignore

    git add -A
    git commit -m "Initial setup" --quiet
    git push --quiet 2>/dev/null || true

    ./.aitask-scripts/aitask_claim_id.sh --init >/dev/null 2>&1 || true
}

teardown() {
    popd > /dev/null 2>&1 || true
}

# --- Helpers ---------------------------------------------------------------

labels_line()  { grep -m1 '^labels:' "$1"; }
labels_cksum() { cksum < aitasks/metadata/labels.txt; }
head_files()   { git show --name-only --pretty=format: HEAD | grep -v '^$' | sort | tr '\n' ' '; }
head_subject() { git log -1 --pretty=format:%s; }
head_sha()     { git rev-parse HEAD; }

VOCAB_PATH="aitasks/metadata/labels.txt"

# Expected `head_files` output: the given paths plus labels.txt when the case
# grew the vocabulary, sorted the same way head_files sorts.
expect_files() {
    local grows="$1"; shift
    local paths=("$@")
    [[ "$grows" == "1" ]] && paths+=("$VOCAB_PATH")
    printf '%s\n' "${paths[@]}" | sort | tr '\n' ' '
}

# Task id token from a created path: aitasks/t7_p_case1.md -> t7
parent_id_of() { local b; b=$(basename "$1" .md); printf '%s' "${b%%_*}"; }
# Child id token: aitasks/t7/t7_1_c_case1.md -> t7_1
child_id_of()  { basename "$1" .md | cut -d_ -f1,2; }

# Load-bearing precondition, not decoration. aitask_create.sh unconditionally
# runs `task_git add "$LABELS_FILE"` on the parent and child commit paths, and
# `task_git commit` commits STAGED PATHS ONLY (no -a). If the sentinel write
# above were left uncommitted (e.g. a future edit moves it below `git add -A`),
# the first `--batch --commit` would sweep labels.txt into its commit: the
# commit-content assertions would then fail on a FIXTURE ARTIFACT rather than
# on real behavior, and the child path (whose parent is created during the
# test's own setup) could absorb the stray file and hide it entirely.
assert_clean_baseline() {
    assert_eq "fixture baseline is committed and clean" "" "$(git status --porcelain)"
}

# --- Tests -----------------------------------------------------------------

test_parent_path() {
    echo "=== Test: parent path (--batch --commit) ==="
    setup_project
    assert_clean_baseline

    local prev_cksum
    prev_cksum=$(labels_cksum)

    local i f vocab_changed
    for i in "${!CASE_IN[@]}"; do
        f=$(bash .aitask-scripts/aitask_create.sh --batch --commit --silent \
                --name "p_case$i" --desc x --labels "${CASE_IN[$i]}" 2>/dev/null || true)

        assert_file_exists "parent case $i created (${CASE_WHY[$i]})" "$f"
        assert_eq "parent case $i labels line (${CASE_WHY[$i]})" \
            "${CASE_OUT[$i]}" "$(labels_line "$f")"
        # assert_contains, not assert_eq: assert_eq is exact equality and the
        # subject carries the humanized task name. The id-bearing needle pins
        # THIS creation commit without depending on the `tr '_' ' '` rule.
        assert_contains "parent case $i asserts on its own creation commit" \
            "ait: Add task $(parent_id_of "$f"):" "$(head_subject)"
        assert_eq "parent case $i commit content (${CASE_WHY[$i]})" \
            "$(expect_files "${CASE_VOCAB_GROWS[$i]}" "$f")" "$(head_files)"
        vocab_changed=no
        if [[ "$(labels_cksum)" != "$prev_cksum" ]]; then vocab_changed=yes; fi
        if [[ "${CASE_VOCAB_GROWS[$i]}" == "1" ]]; then
            assert_eq "parent case $i grew labels.txt" "yes" "$vocab_changed"
        else
            assert_eq "parent case $i left labels.txt byte-identical" "no" "$vocab_changed"
        fi
        prev_cksum=$(labels_cksum)
    done

    teardown
}

test_child_path() {
    echo "=== Test: child path (--batch --commit --parent N) ==="
    setup_project
    assert_clean_baseline

    local prev_cksum parent_file parent_num
    prev_cksum=$(labels_cksum)

    parent_file=$(bash .aitask-scripts/aitask_create.sh --batch --commit --silent \
                      --name par --desc x 2>/dev/null || true)
    assert_file_exists "child fixture: parent task created" "$parent_file"
    parent_num=$(parent_id_of "$parent_file"); parent_num="${parent_num#t}"

    local i f vocab_changed
    for i in "${!CASE_IN[@]}"; do
        f=$(bash .aitask-scripts/aitask_create.sh --batch --commit --silent \
                --parent "$parent_num" --name "c_case$i" --desc x \
                --labels "${CASE_IN[$i]}" 2>/dev/null || true)

        assert_file_exists "child case $i created (${CASE_WHY[$i]})" "$f"
        assert_eq "child case $i labels line (${CASE_WHY[$i]})" \
            "${CASE_OUT[$i]}" "$(labels_line "$f")"
        # Children commit "ait: Add child task <id>: ..." (aitask_create.sh:2052),
        # NOT "ait: Add task ..." - a shared needle would fail every child case.
        assert_contains "child case $i asserts on its own creation commit" \
            "ait: Add child task $(child_id_of "$f"):" "$(head_subject)"
        # The parent file is a legitimate co-committed artifact here:
        # update_parent_children_to_implement rewrites it and :2047 stages it.
        # labels.txt is still absent - that is the fact being pinned.
        assert_eq "child case $i commit content (${CASE_WHY[$i]})" \
            "$(expect_files "${CASE_VOCAB_GROWS[$i]}" "$f" "$parent_file")" \
            "$(head_files)"
        vocab_changed=no
        if [[ "$(labels_cksum)" != "$prev_cksum" ]]; then vocab_changed=yes; fi
        if [[ "${CASE_VOCAB_GROWS[$i]}" == "1" ]]; then
            assert_eq "child case $i grew labels.txt" "yes" "$vocab_changed"
        else
            assert_eq "child case $i left labels.txt byte-identical" "no" "$vocab_changed"
        fi
        prev_cksum=$(labels_cksum)
    done

    teardown
}

test_draft_path() {
    echo "=== Test: draft path (--batch, no --commit) ==="
    setup_project
    assert_clean_baseline

    local base_cksum base_sha
    base_cksum=$(labels_cksum)
    base_sha=$(head_sha)

    local i f
    for i in "${!CASE_IN[@]}"; do
        f=$(bash .aitask-scripts/aitask_create.sh --batch --silent \
                --name "d_case$i" --desc x --labels "${CASE_IN[$i]}" 2>/dev/null || true)

        assert_file_exists "draft case $i created (${CASE_WHY[$i]})" "$f"
        assert_eq "draft case $i labels line (${CASE_WHY[$i]})" \
            "${CASE_OUT[$i]}" "$(labels_line "$f")"
        assert_eq "draft case $i creates no commit" "$base_sha" "$(head_sha)"
        assert_eq "draft case $i leaves labels.txt byte-identical (deferred to --finalize)" \
            "$base_cksum" "$(labels_cksum)"
    done

    teardown
}

teardown_all() {
    local d
    for d in "${CLEANUP_DIRS[@]}"; do
        [[ -d "$d" ]] && rm -rf "$d"
    done
}
trap teardown_all EXIT

test_parent_path
test_child_path
test_draft_path

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="

# Deliberately outside the PASS/FAIL/TOTAL counters so it is not
# self-referential. Exit 0 alone is not evidence of coverage: a suite that ran
# zero assertions also exits 0.
if [[ "$TOTAL" -ne "$EXPECTED_ASSERTIONS" ]]; then
    echo "FAIL: assertion-count tripwire - ran $TOTAL assertions, expected $EXPECTED_ASSERTIONS"
    echo "      (assertions were added or removed; update EXPECTED_ASSERTIONS deliberately)"
    exit 1
fi

[[ "$FAIL" -eq 0 ]] || exit 1
