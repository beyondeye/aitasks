#!/usr/bin/env bash
# test_anchor_create.sh - Tests for the scalar `anchor:` topic group key in
# aitask_create.sh (t1016_1): the --anchor / --followup-of flags, the
# resolve_anchor precedence/guards, id normalization to bare form, the legacy
# parent-aware fallback, and draft --finalize carry-through.
#
# Covers:
#   - root (no flags)            -> no `anchor:` line
#   - --anchor 42                -> anchor: 42 (bare, validated)
#   - --anchor t42               -> anchor: 42 (leading t stripped; identical)
#   - --anchor xyz / --anchor t  -> non-zero, no file (bad id shape)
#   - --anchor 999999            -> non-zero, no file (not found)
#   - --anchor <archived id>     -> succeeds (archived-inclusive validation)
#   - --followup-of <root>       -> anchor: <root>
#   - --followup-of <followup R> -> anchor: R (flattened; never chains)
#   - --followup-of <legacy anchorless child P_c> -> anchor: P (parent fallback)
#   - child --parent P (no anchor)  -> anchor: P (auto-inherit)
#   - child --parent P (anchor=R)   -> anchor: R (auto-inherit root)
#   - --parent + --anchor / + --followup-of -> non-zero, no file (child rule)
#   - --anchor + --followup-of   -> non-zero, no file (mutually exclusive)
#   - draft created with --anchor then --finalize -> anchor preserved
#
# Run: bash tests/test_anchor_create.sh

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

assert_nonzero() {
    local desc="$1" rc="$2"
    TOTAL=$((TOTAL + 1))
    if [[ "$rc" -ne 0 ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected non-zero exit, got $rc)"
    fi
}

assert_no_field() {
    local desc="$1" file="$2" field="$3"
    TOTAL=$((TOTAL + 1))
    if [[ -f "$file" ]] && grep -qE "^${field}:" "$file"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc ('${field}:' unexpectedly present in $file)"
    else
        PASS=$((PASS + 1))
    fi
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

# Run a draft-creating aitask_create.sh; echo the draft path on success (exit 0),
# echo nothing on failure. Always returns 0 so callers can capture rc separately.
make_draft() {
    bash .aitask-scripts/aitask_create.sh --batch --silent "$@" 2>/dev/null || true
}

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
    : > aitasks/metadata/labels.txt
    echo "aitasks/new/" > .gitignore

    git add -A
    git commit -m "Initial setup" --quiet
    git push --quiet 2>/dev/null || true

    ./.aitask-scripts/aitask_claim_id.sh --init >/dev/null 2>&1 || true
}

teardown() {
    popd > /dev/null 2>&1 || true
}

# Seed a task file with arbitrary extra frontmatter lines (e.g. "anchor: 42").
seed_task() {
    local path="$1"; shift
    mkdir -p "$(dirname "$path")"
    {
        printf '%s\n' "---"
        printf '%s\n' "priority: medium"
        printf '%s\n' "effort: low"
        printf '%s\n' "depends: []"
        printf '%s\n' "issue_type: chore"
        printf '%s\n' "status: Ready"
        printf '%s\n' "labels: []"
        for extra in "$@"; do printf '%s\n' "$extra"; done
        printf '%s\n' "created_at: 2026-01-01 10:00"
        printf '%s\n' "updated_at: 2026-01-01 10:00"
        printf '%s\n' "---"
        printf '\nBody\n'
    } > "$path"
}

test_explicit_anchor() {
    echo "=== Test: --anchor explicit + normalization + validation ==="
    setup_project
    seed_task aitasks/t42_root.md
    seed_task aitasks/archived/t70_done.md "status: Done"
    git add -A; git commit -m "seed" --quiet

    # root: no flags -> no anchor line
    local f
    f=$(make_draft --name root_task --desc x)
    assert_no_field "root draft has no anchor line" "$f" anchor

    # --anchor 42 -> anchor: 42
    f=$(make_draft --name a_bare --desc x --anchor 42)
    assert_eq "--anchor 42 -> 42" "42" "$(read_frontmatter_field "$f" anchor)"

    # --anchor t42 -> anchor: 42 (bare)
    f=$(make_draft --name a_tpref --desc x --anchor t42)
    assert_eq "--anchor t42 -> 42 (bare)" "42" "$(read_frontmatter_field "$f" anchor)"

    # --anchor <archived id> -> succeeds (archived-inclusive)
    f=$(make_draft --name a_arch --desc x --anchor 70)
    assert_eq "--anchor 70 (archived) -> 70" "70" "$(read_frontmatter_field "$f" anchor)"

    # bad id shapes -> non-zero, no file
    local rc
    set +e
    bash .aitask-scripts/aitask_create.sh --batch --silent --name a_bad --desc x --anchor xyz >/dev/null 2>&1; rc=$?
    set -e
    assert_nonzero "--anchor xyz rejected" "$rc"
    set +e
    bash .aitask-scripts/aitask_create.sh --batch --silent --name a_bad2 --desc x --anchor t >/dev/null 2>&1; rc=$?
    set -e
    assert_nonzero "--anchor t (empty after strip) rejected" "$rc"

    # nonexistent -> non-zero
    set +e
    bash .aitask-scripts/aitask_create.sh --batch --silent --name a_missing --desc x --anchor 999999 >/dev/null 2>&1; rc=$?
    set -e
    assert_nonzero "--anchor 999999 (missing) rejected" "$rc"

    teardown
}

test_followup_flatten() {
    echo "=== Test: --followup-of flattening + legacy parent fallback ==="
    setup_project
    seed_task aitasks/t42_root.md
    seed_task aitasks/t50_followup.md "anchor: 42"
    seed_task aitasks/t60_legacy_parent.md
    seed_task aitasks/t60/t60_1_legacy_child.md
    git add -A; git commit -m "seed" --quiet

    local f
    # follow-up of a root -> the root id
    f=$(make_draft --name fu_root --desc x --followup-of 42)
    assert_eq "--followup-of 42 (root) -> 42" "42" "$(read_frontmatter_field "$f" anchor)"

    # follow-up of a follow-up (anchor=42) -> 42 (flattened; never chains)
    f=$(make_draft --name fu_fu --desc x --followup-of 50)
    assert_eq "--followup-of 50 (followup of 42) -> 42 (flatten)" "42" "$(read_frontmatter_field "$f" anchor)"

    # follow-up of a legacy anchorless child -> its parent (topic root)
    f=$(make_draft --name fu_legacy --desc x --followup-of 60_1)
    assert_eq "--followup-of 60_1 (legacy child) -> 60 (parent fallback)" "60" "$(read_frontmatter_field "$f" anchor)"

    # follow-up of nonexistent -> non-zero
    local rc
    set +e
    bash .aitask-scripts/aitask_create.sh --batch --silent --name fu_missing --desc x --followup-of 999999 >/dev/null 2>&1; rc=$?
    set -e
    assert_nonzero "--followup-of 999999 rejected" "$rc"

    teardown
}

test_child_inherit() {
    echo "=== Test: child auto-inherits parent's anchor-or-id (--commit) ==="
    setup_project
    seed_task aitasks/t60_plain_parent.md
    seed_task aitasks/t61_anchored_parent.md "anchor: 42"
    git add -A; git commit -m "seed" --quiet

    # child of anchorless parent -> parent id
    bash .aitask-scripts/aitask_create.sh --batch --silent --parent 60 \
        --name kid_a --desc x --commit >/dev/null 2>&1 || true
    local child
    child=$(ls aitasks/t60/t60_1_*.md 2>/dev/null | head -1)
    TOTAL=$((TOTAL + 1))
    if [[ -n "$child" ]]; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); echo "FAIL: child of t60 not created"; fi
    [[ -n "$child" ]] && assert_eq "child of anchorless parent 60 -> 60" "60" "$(read_frontmatter_field "$child" anchor)"

    # child of anchored parent (anchor=42) -> 42 (inherits root)
    bash .aitask-scripts/aitask_create.sh --batch --silent --parent 61 \
        --name kid_b --desc x --commit >/dev/null 2>&1 || true
    child=$(ls aitasks/t61/t61_1_*.md 2>/dev/null | head -1)
    [[ -n "$child" ]] && assert_eq "child of anchored parent 61 (anchor=42) -> 42" "42" "$(read_frontmatter_field "$child" anchor)"

    teardown
}

test_guards() {
    echo "=== Test: mutual-exclusion + child-rule guards ==="
    setup_project
    seed_task aitasks/t42_root.md
    seed_task aitasks/t60_parent.md
    git add -A; git commit -m "seed" --quiet

    local rc
    set +e
    bash .aitask-scripts/aitask_create.sh --batch --silent --name g1 --desc x --anchor 42 --followup-of 42 >/dev/null 2>&1; rc=$?
    set -e
    assert_nonzero "--anchor + --followup-of rejected" "$rc"

    set +e
    bash .aitask-scripts/aitask_create.sh --batch --silent --parent 60 --name g2 --desc x --anchor 42 --commit >/dev/null 2>&1; rc=$?
    set -e
    assert_nonzero "--parent + --anchor rejected" "$rc"

    set +e
    bash .aitask-scripts/aitask_create.sh --batch --silent --parent 60 --name g3 --desc x --followup-of 42 --commit >/dev/null 2>&1; rc=$?
    set -e
    assert_nonzero "--parent + --followup-of rejected" "$rc"

    teardown
}

test_finalize_preserves_anchor() {
    echo "=== Test: draft --finalize carries the anchor through ==="
    setup_project
    seed_task aitasks/t42_root.md
    git add -A; git commit -m "seed" --quiet

    local draft
    draft=$(make_draft --name fin_anchor --desc x --anchor 42)
    assert_eq "draft has anchor: 42" "42" "$(read_frontmatter_field "$draft" anchor)"

    # Finalize the draft (claims a real id, moves into aitasks/) and confirm the
    # anchor survives the draft-strip sed.
    local draft_base
    draft_base=$(basename "$draft")
    bash .aitask-scripts/aitask_create.sh --batch --finalize "$draft_base" >/dev/null 2>&1 || true
    local finalized
    finalized=$(ls aitasks/t*_fin_anchor.md 2>/dev/null | head -1)
    TOTAL=$((TOTAL + 1))
    if [[ -n "$finalized" ]]; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); echo "FAIL: finalized file not found"; fi
    [[ -n "$finalized" ]] && assert_eq "finalized task preserves anchor: 42" "42" "$(read_frontmatter_field "$finalized" anchor)"

    teardown
}

teardown_all() {
    local d
    for d in "${CLEANUP_DIRS[@]}"; do
        [[ -d "$d" ]] && rm -rf "$d"
    done
}
trap teardown_all EXIT

test_explicit_anchor
test_followup_flatten
test_child_inherit
test_guards
test_finalize_preserves_anchor

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
