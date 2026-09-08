#!/usr/bin/env bash
# test_issue_import_amend_guard.sh — guard + fallback for aitask_issue_import.sh's
# frontmatter commit (t1599_4).
#
# Before t1599_4 the import ended with a bare `task_git commit --amend --no-edit`:
# it rewrote WHATEVER HEAD happened to be, with no check that HEAD was its own
# create commit, and committed the whole index while doing it. This suite pins the
# replacement, `_import_commit_frontmatter`, in BOTH directions:
#
#   * permit  — an expected HEAD is still amended normally (A1). Without this the
#               refuse side would be satisfied by a guard that refuses everything.
#   * refuse  — a HEAD carrying a foreign path (A2) or an already-published HEAD
#               (A3) is NOT rewritten, and the frontmatter is NOT lost: it lands
#               in a fresh, path-scoped commit instead.
#
# Why the function is driven directly rather than through `ait issue-import`: the
# batch import flow needs the `gh` CLI (see tests/test_issue_import_contributor.sh,
# "We can't call the full import flow"), which is exactly why this code path had no
# coverage at all before this task. The functions are extracted from the real
# script — not reimplemented — so a change to the script reaches this test.
#
# Run: bash tests/test_issue_import_amend_guard.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

CLEANUP_DIRS=()
teardown_all() {
    local d
    for d in ${CLEANUP_DIRS[@]+"${CLEANUP_DIRS[@]}"}; do
        [[ -n "$d" && -d "$d" ]] && rm -rf "$d"
    done
}
trap teardown_all EXIT

# --- Extract the functions under test from the real script -------------------
# From the `_import_amend_refusal` declaration up to (but excluding) the line
# that starts merge_issues(). Fails loudly if the anchors ever move, so this can
# never silently degrade into testing an empty file.
extract_funcs() {
    local dest="$1"
    awk '/^_import_amend_refusal=""$/,/^merge_issues\(\) \{$/' \
        "$PROJECT_DIR/.aitask-scripts/aitask_issue_import.sh" | sed '$d' > "$dest"
    if ! grep -q '^_import_commit_frontmatter()' "$dest"; then
        echo "FATAL: could not extract _import_commit_frontmatter from aitask_issue_import.sh" >&2
        echo "       (the awk anchors in this test have gone stale)" >&2
        exit 1
    fi
}

# --- Fixture ------------------------------------------------------------------
setup_repo() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    CLEANUP_DIRS+=("$tmpdir")

    git init --bare --quiet "$tmpdir/remote.git"
    git clone --quiet "$tmpdir/remote.git" "$tmpdir/local" 2>/dev/null

    pushd "$tmpdir/local" >/dev/null || return 1
    git config user.email "t@t"
    git config user.name "t"
    mkdir -p aitasks/metadata aitasks/t900 aiplans
    setup_fake_aitask_repo "$PWD"
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    # task_utils.sh sources these at load time; without them it emits "No such
    # file or directory" on stderr, which the output assertions below also read.
    for _lib in archive_utils archive_scan agentcrew_utils; do
        cp "$PROJECT_DIR/.aitask-scripts/lib/$_lib.sh" .aitask-scripts/lib/ 2>/dev/null || true
    done
    printf 'preexisting_label\n' > aitasks/metadata/labels.txt
    extract_funcs "$PWD/_import_funcs.sh"

    # The driver: source the real libs + the extracted functions, then call the
    # function under test. A separate process so a die() cannot kill the suite.
    cat > drive.sh <<'DRIVEEOF'
set -uo pipefail
SCRIPT_DIR="$PWD/.aitask-scripts"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/task_utils.sh"
TASK_DIR="aitasks"
# shellcheck disable=SC1091
source "./${AIT_FUNCS_FILE:-_import_funcs.sh}"
_import_commit_frontmatter "$1"
DRIVEEOF

    git add -A >/dev/null 2>&1
    git commit -qm "fixture base" >/dev/null 2>&1
    git push -q origin HEAD >/dev/null 2>&1
    popd >/dev/null || return 1
    echo "$tmpdir/local"
}

head_files() { git show --name-only --pretty=format: HEAD | grep -v '^$' | sort | tr '\n' ' '; }
count_commits() { git rev-list --count HEAD; }

# Build a create-commit-shaped HEAD carrying $1... and return the task file path.
seed_task_commit() {
    local taskfile="aitasks/t901_imported.md"
    printf -- '---\nstatus: Ready\n---\n\nbody\n' > "$taskfile"
    git add -- "$taskfile" "$@" >/dev/null 2>&1
    git commit -qm "ait: Add task t901: imported" >/dev/null 2>&1
    echo "$taskfile"
}

inject_frontmatter() {   # simulate inject_merge_frontmatter
    printf -- '---\nstatus: Ready\nrelated_issues: [1, 2]\n---\n\nbody\n' > "$1"
}

# =============================================================================
# A1 — an EXPECTED HEAD is amended normally (the permit direction)
# =============================================================================
test_a1_expected_head_amends() {
    echo "=== A1: expected HEAD is amended, not forked ==="
    local repo; repo="$(setup_repo)"
    pushd "$repo" >/dev/null || return

    local tf; tf="$(seed_task_commit)"
    local sha_before n_before
    sha_before=$(git rev-parse HEAD); n_before=$(count_commits)

    inject_frontmatter "$tf"
    local out rc=0
    out=$(bash drive.sh "$tf" 2>&1) || rc=$?

    assert_eq_trim "A1: driver succeeded" "0" "$rc"
    assert_eq_trim "A1: commit count unchanged (amended, not a new commit)" \
        "$n_before" "$(count_commits)"
    assert_not_contains "A1: HEAD sha changed" "$sha_before" "$(git rev-parse HEAD)"
    assert_contains "A1: injected frontmatter is in HEAD" \
        "related_issues" "$(git show "HEAD:$tf")"
    assert_eq_trim "A1: commit contains only the task file" \
        "$tf" "$(head_files)"
    assert_eq_trim "A1: task file is clean afterwards" "" "$(git status --porcelain -- "$tf")"
    assert_not_contains "A1: no refusal warning" "not amending" "$out"

    popd >/dev/null || return
}

# A1b — the other two accepted shapes: labels.txt and a child's parent file.
test_a1b_accepted_cochanges_amend() {
    echo "=== A1b: labels.txt and a child's parent file are accepted co-changes ==="
    local repo; repo="$(setup_repo)"
    pushd "$repo" >/dev/null || return

    # A child creation commit: child file + parent file + labels.txt
    local child="aitasks/t900/t900_2_child.md"
    local parent="aitasks/t900_parent.md"
    printf -- '---\nstatus: Ready\n---\n\nbody\n' > "$child"
    printf -- '---\nchildren_to_implement: [t900_2]\n---\n\nparent\n' > "$parent"
    printf 'preexisting_label\nnewlabel\n' > aitasks/metadata/labels.txt
    git add -- "$child" "$parent" aitasks/metadata/labels.txt >/dev/null 2>&1
    git commit -qm "ait: Add child task t900_2: child" >/dev/null 2>&1
    local n_before; n_before=$(count_commits)

    inject_frontmatter "$child"
    local out rc=0
    out=$(bash drive.sh "$child" 2>&1) || rc=$?

    assert_eq_trim "A1b: driver succeeded" "0" "$rc"
    assert_eq_trim "A1b: amended (commit count unchanged)" "$n_before" "$(count_commits)"
    assert_not_contains "A1b: no refusal warning" "not amending" "$out"
    assert_contains "A1b: parent file still in HEAD" "$parent" "$(head_files)"
    assert_contains "A1b: labels.txt still in HEAD" "labels.txt" "$(head_files)"

    popd >/dev/null || return
}

# =============================================================================
# A2 — a FOREIGN path in HEAD refuses, and the frontmatter is NOT lost
# =============================================================================
test_a2_foreign_head_refuses_without_loss() {
    echo "=== A2: foreign path in HEAD => no rewrite, fresh commit instead ==="
    local repo; repo="$(setup_repo)"
    pushd "$repo" >/dev/null || return

    local foreign="aiplans/p999_unrelated.md"
    printf 'someone elses work\n' > "$foreign"
    local tf; tf="$(seed_task_commit "$foreign")"

    local sha_before n_before
    sha_before=$(git rev-parse HEAD); n_before=$(count_commits)

    inject_frontmatter "$tf"
    local out rc=0
    out=$(bash drive.sh "$tf" 2>&1) || rc=$?

    assert_eq_trim "A2: driver succeeded (fallback, not a hard failure)" "0" "$rc"
    assert_eq_trim "A2: contaminated commit was NOT rewritten" \
        "$sha_before" "$(git rev-parse "HEAD~1")"
    assert_contains "A2: foreign path is still in the old commit" \
        "$foreign" "$(git show --name-only --pretty=format: "HEAD~1")"
    # Nothing lost: a NEW commit carries the frontmatter, scoped to the task file.
    assert_eq_trim "A2: exactly one new commit was made" \
        "$((n_before + 1))" "$(count_commits)"
    assert_eq_trim "A2: the new commit contains ONLY the task file" "$tf" "$(head_files)"
    assert_contains "A2: injected frontmatter is in the new commit" \
        "related_issues" "$(git show "HEAD:$tf")"
    assert_eq_trim "A2: task file clean afterwards" "" "$(git status --porcelain -- "$tf")"

    popd >/dev/null || return
}

# A4 — the refusal is LOUD and names the offending path.
test_a4_refusal_is_reported() {
    echo "=== A4: the refusal warning names the offending path ==="
    local repo; repo="$(setup_repo)"
    pushd "$repo" >/dev/null || return

    local foreign="aiplans/p999_unrelated.md"
    printf 'someone elses work\n' > "$foreign"
    local tf; tf="$(seed_task_commit "$foreign")"
    inject_frontmatter "$tf"

    local out; out=$(bash drive.sh "$tf" 2>&1)
    assert_contains "A4: warning says it is not amending" "not amending" "$out"
    assert_contains "A4: warning names the offending path" "$foreign" "$out"
    assert_contains "A4: warning says a separate commit was made" "separate commit" "$out"

    popd >/dev/null || return
}

# =============================================================================
# A5 — an AMBIGUOUS parent refuses: a second same-prefix file is not "the parent"
# =============================================================================
# The child-parent accept branch resolves `aitasks/tP_*.md`. If that glob matches
# more than one file — a malformed tree, or a concurrent session adding another —
# none of them is provably the parent this creation co-committed, and accepting
# the whole glob would let a foreign same-prefix file ride into a
# history-rewriting amend. Ambiguity must accept NOTHING.
test_a5_ambiguous_parent_refuses() {
    echo "=== A5: two same-prefix parent candidates => refuse, do not rewrite ==="
    local repo; repo="$(setup_repo)"
    pushd "$repo" >/dev/null || return

    local child="aitasks/t900/t900_2_child.md"
    local parent="aitasks/t900_parent.md"
    local foreign_parent="aitasks/t900_foreign.md"   # same prefix, NOT this parent
    printf -- '---\nstatus: Ready\n---\n\nbody\n' > "$child"
    printf -- '---\nchildren_to_implement: [t900_2]\n---\n\nparent\n' > "$parent"
    printf -- '---\nstatus: Ready\n---\n\nsomeone elses work\n' > "$foreign_parent"
    git add -- "$child" "$parent" "$foreign_parent" >/dev/null 2>&1
    git commit -qm "ait: Add child task t900_2: child" >/dev/null 2>&1

    local sha_before n_before
    sha_before=$(git rev-parse HEAD); n_before=$(count_commits)

    inject_frontmatter "$child"
    local out rc=0
    out=$(bash drive.sh "$child" 2>&1) || rc=$?

    assert_eq_trim "A5: driver succeeded (fallback)" "0" "$rc"
    assert_contains "A5: the ambiguity is reported" "ambiguous parent" "$out"
    assert_contains "A5: it refuses rather than amending" "not amending" "$out"
    assert_eq_trim "A5: the commit carrying the foreign file was NOT rewritten" \
        "$sha_before" "$(git rev-parse "HEAD~1")"
    assert_contains "A5: foreign same-prefix file still in the untouched commit" \
        "$foreign_parent" "$(git show --name-only --pretty=format: "HEAD~1")"
    assert_eq_trim "A5: exactly one new commit" "$((n_before + 1))" "$(count_commits)"
    assert_eq_trim "A5: the new commit contains ONLY the child file" "$child" "$(head_files)"
    assert_contains "A5: frontmatter still landed" "related_issues" "$(git show "HEAD:$child")"

    popd >/dev/null || return
}

# =============================================================================
# A6 — the HEAD probe FAILS CLOSED, both ways
# =============================================================================
# `git show --name-only` prints nothing both when it fails and when HEAD is a
# merge commit. Either way the path list is unverified, and treating it as
# "nothing foreign" would permit a rewrite of a commit whose contents were never
# read — a fail-OPEN guard, which is worse than none.
test_a6_unreadable_head_fails_closed() {
    echo "=== A6a: an unreadable HEAD refuses instead of permitting ==="
    local repo; repo="$(setup_repo)"
    pushd "$repo" >/dev/null || return

    # A fresh orphan branch has no commits, so `git show HEAD` fails outright.
    git checkout -q --orphan unborn 2>/dev/null
    git rm -q -rf --cached . >/dev/null 2>&1 || true
    local tf="aitasks/t901_imported.md"
    mkdir -p aitasks
    inject_frontmatter "$tf"

    local out rc=0
    out=$(bash drive.sh "$tf" 2>&1) || rc=$?
    assert_contains "A6a: refuses because HEAD could not be read" \
        "unverified" "$out"
    assert_not_contains "A6a: it did NOT silently permit an amend" \
        "amend of the import commit failed" "$out"

    popd >/dev/null || return
}

test_a6b_merge_head_fails_closed() {
    echo "=== A6b: a MERGE HEAD (empty path list) refuses ==="
    local repo; repo="$(setup_repo)"
    pushd "$repo" >/dev/null || return

    local tf; tf="$(seed_task_commit)"
    # Build a merge whose --name-only output is empty.
    git checkout -q -b side HEAD~1 2>/dev/null
    printf 'side\n' > side.txt; git add -- side.txt >/dev/null 2>&1
    git commit -qm "side" >/dev/null 2>&1
    git checkout -q - 2>/dev/null
    git merge -q --no-ff -m "merge side" side >/dev/null 2>&1

    local sha_before; sha_before=$(git rev-parse HEAD)
    inject_frontmatter "$tf"
    local out rc=0
    out=$(bash drive.sh "$tf" 2>&1) || rc=$?

    assert_contains "A6b: refuses on an empty/merge path list" \
        "no paths" "$out"
    assert_eq_trim "A6b: the merge commit was NOT rewritten" \
        "$sha_before" "$(git rev-parse "HEAD~1")"
    assert_contains "A6b: frontmatter still landed in a fresh commit" \
        "related_issues" "$(git show "HEAD:$tf")"

    popd >/dev/null || return
}

# =============================================================================
# A3 — a PUBLISHED HEAD refuses the same way (a branch A2 never reaches)
# =============================================================================
test_a3_published_head_refuses() {
    echo "=== A3: published HEAD => no rewrite of pushed history ==="
    local repo; repo="$(setup_repo)"
    pushd "$repo" >/dev/null || return

    local tf; tf="$(seed_task_commit)"
    git push -q -u origin HEAD >/dev/null 2>&1      # HEAD is now an ancestor of @{u}

    local sha_before n_before
    sha_before=$(git rev-parse HEAD); n_before=$(count_commits)

    inject_frontmatter "$tf"
    local out rc=0
    out=$(bash drive.sh "$tf" 2>&1) || rc=$?

    assert_eq_trim "A3: driver succeeded" "0" "$rc"
    assert_contains "A3: refusal cites published history" "already published" "$out"
    assert_eq_trim "A3: pushed commit was NOT rewritten" \
        "$sha_before" "$(git rev-parse "HEAD~1")"
    assert_eq_trim "A3: one new commit instead" "$((n_before + 1))" "$(count_commits)"
    assert_contains "A3: frontmatter landed" "related_issues" "$(git show "HEAD:$tf")"

    popd >/dev/null || return
}

# =============================================================================
# NEGATIVE CONTROLS — prove each direction can actually fail
# =============================================================================

# Build a variant of the extracted functions whose guard always returns $1.
install_guard_stub() {   # <always_rc> <dest>
    local rc="$1" dest="$2"
    sed "s/^_import_amend_guard() {/_import_amend_guard() { _import_amend_refusal='stubbed'; return $rc; :/" \
        _import_funcs.sh > "$dest"
}

# Control 1: with the guard stripped (always permits), A2's core assertions FAIL —
# the contaminated HEAD gets amended and no fresh commit appears.
test_neg_guard_stripped_reintroduces_the_defect() {
    echo "=== NEG 1: guard stripped => contaminated HEAD is rewritten (defect returns) ==="
    local repo; repo="$(setup_repo)"
    pushd "$repo" >/dev/null || return

    local foreign="aiplans/p999_unrelated.md"
    printf 'someone elses work\n' > "$foreign"
    local tf; tf="$(seed_task_commit "$foreign")"
    local sha_before n_before
    sha_before=$(git rev-parse HEAD); n_before=$(count_commits)

    install_guard_stub 0 _stub_permit.sh
    inject_frontmatter "$tf"
    AIT_FUNCS_FILE=_stub_permit.sh bash drive.sh "$tf" >/dev/null 2>&1

    # These are the inverse of A2 — if they do not hold, A2 was vacuous.
    assert_eq_trim "NEG1: no new commit (it amended)" "$n_before" "$(count_commits)"
    assert_not_contains "NEG1: HEAD was rewritten" "$sha_before" "$(git rev-parse HEAD)"
    assert_contains "NEG1: the foreign path rode into the rewritten commit" \
        "$foreign" "$(head_files)"

    popd >/dev/null || return
}

# Control 2: with a guard that always refuses, A1's permit assertions FAIL —
# an ordinary import would fork a needless second commit.
test_neg_always_refuse_breaks_the_permit_path() {
    echo "=== NEG 2: always-refusing guard => the normal amend path is lost ==="
    local repo; repo="$(setup_repo)"
    pushd "$repo" >/dev/null || return

    local tf; tf="$(seed_task_commit)"
    local n_before; n_before=$(count_commits)

    install_guard_stub 1 _stub_refuse.sh
    inject_frontmatter "$tf"
    AIT_FUNCS_FILE=_stub_refuse.sh bash drive.sh "$tf" >/dev/null 2>&1

    assert_eq_trim "NEG2: a second commit appeared where A1 expects an amend" \
        "$((n_before + 1))" "$(count_commits)"

    popd >/dev/null || return
}

# --- Run ----------------------------------------------------------------------
test_a1_expected_head_amends
test_a1b_accepted_cochanges_amend
test_a2_foreign_head_refuses_without_loss
test_a4_refusal_is_reported
test_a5_ambiguous_parent_refuses
test_a6_unreadable_head_fails_closed
test_a6b_merge_head_fails_closed
test_a3_published_head_refuses
test_neg_guard_stripped_reintroduces_the_defect
test_neg_always_refuse_breaks_the_permit_path

echo
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
