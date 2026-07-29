#!/usr/bin/env bash
# test_characterize_batch_label_frontmatter.sh - CHARACTERIZATION test (t1321).
#
# Pins the CURRENT (pre-t1312) `labels:` frontmatter emitted by
# `aitask_create.sh --batch --labels ...` across all three creation paths, plus
# the two side-effect facts t1312 changes. Today `format_yaml_list`
# (lib/task_utils.sh:414) is a pure `s/,/, /g` + bracket wrap: no split, no
# trim, no case-fold, no sanitize, no dedupe.
#
# Paths covered:
#   parent - create_task_file       (aitask_create.sh:1791, batch site :2066)
#   child  - create_child_task_file (:462,  batch site :2035)
#   draft  - create_draft_file      (:580,  batch site :2093, gitignored)
#
# >>> THIS TEST IS EXPECTED TO CHANGE WHEN t1312 LANDS. <<<
# t1312 normalizes the --labels CSV (trim, lowercase, sanitize, dedupe) before
# it reaches format_yaml_list, and starts writing new labels into
# aitasks/metadata/labels.txt. When it lands, the expectations for the
# NON-CANONICAL cases (2, 3, 5, 6) are updated IN THE SAME COMMIT as the
# normalization change - the diff to this file IS the reviewable record of
# exactly what changed. Case 1 (`ui,backend`) is canonical and must NOT move.
# Two side-effect facts flip at the same time:
#   - labels.txt stops being byte-identical across a create
#   - the creation commit starts containing labels.txt
# EXPECTED_ASSERTIONS must be re-derived in that commit too.
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
    "labels: [ui,  backend]"
    "labels: [UI Stuff, foo-bar!]"
    "labels: []"
    "labels: [foo, FOO, foo]"
    "labels: [!!!]"
)
CASE_WHY=(
    "canonical"
    "double space preserved (no trim)"
    "verbatim (no case-fold, no sanitize)"
    "empty input"
    "no dedupe (exact-dup + case-fold-dup)"
    "no sanitize (token reduces to empty under t1312)"
)

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

    local base_cksum
    base_cksum=$(labels_cksum)

    local i f
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
        assert_eq "parent case $i commit holds only the task file" \
            "$f " "$(head_files)"
        assert_eq "parent case $i leaves labels.txt byte-identical" \
            "$base_cksum" "$(labels_cksum)"
    done

    teardown
}

test_child_path() {
    echo "=== Test: child path (--batch --commit --parent N) ==="
    setup_project
    assert_clean_baseline

    local base_cksum parent_file parent_num
    base_cksum=$(labels_cksum)

    parent_file=$(bash .aitask-scripts/aitask_create.sh --batch --commit --silent \
                      --name par --desc x 2>/dev/null || true)
    assert_file_exists "child fixture: parent task created" "$parent_file"
    parent_num=$(parent_id_of "$parent_file"); parent_num="${parent_num#t}"

    local i f
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
        assert_eq "child case $i commit holds child + parent, not labels.txt" \
            "$(printf '%s\n%s\n' "$f" "$parent_file" | sort | tr '\n' ' ')" \
            "$(head_files)"
        assert_eq "child case $i leaves labels.txt byte-identical" \
            "$base_cksum" "$(labels_cksum)"
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
        assert_eq "draft case $i leaves labels.txt byte-identical" \
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
