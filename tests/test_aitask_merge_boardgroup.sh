#!/usr/bin/env bash
# test_aitask_merge_boardgroup.sh - base-aware `boardgroup` merge (t1243_8).
#
# Run: bash tests/test_aitask_merge_boardgroup.sh
#
# Scope split: this file covers the base-aware MERGE SEMANTICS through the real
# rebase path in legacy mode. The branch-mode plumbing that carries them (the
# `task_git show :1:` extraction and conflict staging inside a wedged rebase)
# is covered by tests/test_sync_branch_mode_automerge.sh.
#
# Why the fixture is shaped the way it is
# ---------------------------------------
# Git merges textually, per hunk. If the two sides' edits land in
# non-overlapping hunks the rebase succeeds cleanly, `aitask_merge.py` is never
# invoked, and an assertion on the final file content STILL PASSES — a test that
# proves nothing. So Test 1 asserts an unmerged path actually materialised
# before asserting the outcome, and Test 5 proves that control discriminates.

set -uo pipefail

TEST_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

. "$PROJECT_DIR/tests/lib/asserts.sh"

# Report a file's `boardgroup` as "<type>:<repr>" using the REAL loader, so an
# assertion pins presence AND type. A bare `boardgroup:` parses to None, which
# no string match on the file text would distinguish from the "" tombstone.
# Parameterised over the key (t1468_1) so `followup_kind`, which shares the
# base-aware resolver, can be pinned the same way. `parsed_boardgroup` stays as
# the boardgroup-specific wrapper so every existing call site is unchanged.
parsed_field() {
    PYTHONPATH="$PROJECT_DIR/.aitask-scripts/lib" python3 -c "
import sys, task_yaml as ty
parsed = ty.parse_frontmatter(open(sys.argv[1]).read())
if not parsed:
    print('UNPARSEABLE'); raise SystemExit
md = parsed[0]
key = sys.argv[2]
if key not in md:
    print('ABSENT'); raise SystemExit
v = md[key]
print(f'{type(v).__name__}:{v!r}')
" "$1" "$2"
}

parsed_boardgroup() { parsed_field "$1" boardgroup; }

# `labels` and `boardgroup` are ADJACENT so the two sides' single-line edits
# necessarily collide in one hunk.
#
# The unrelated edit is `labels` (union-merged), deliberately NOT `status`:
# divergent non-Implementing statuses are unresolvable by a PRE-EXISTING rule,
# so a status-based fixture reports PARTIAL for a reason that has nothing to do
# with this task and proves nothing about `boardgroup`.
write_task() {
    local path="$1" labels="$2" group_line="$3"
    {
        echo "---"
        echo "priority: high"
        echo "status: Ready"
        echo "labels: $labels"
        echo "$group_line"
        echo "updated_at: $4"
        echo "---"
        echo "Body stays the same"
    } > "$path"
}

# bare remote + local + pc2, all carrying `boardgroup: perf_work` at the base.
setup_repos() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    git init -q --bare "$tmpdir/remote.git"
    git clone -q "$tmpdir/remote.git" "$tmpdir/local" 2>/dev/null
    (
        cd "$tmpdir/local"
        git config user.email test@test.com
        git config user.name Test
        git config commit.gpgsign false
        mkdir -p aitasks aiplans
        write_task aitasks/t1_sample.md "[ui]" "boardgroup: perf_work" "2026-01-01 09:00"
        git add -A
        git commit -q -m "base: grouped"
        git push -q 2>/dev/null
        cp "$PROJECT_DIR/ait" ./ait
        chmod +x ./ait
        cp -r "$PROJECT_DIR/.aitask-scripts" ./.aitask-scripts
        git add -A
        git commit -q -m "framework"
        git push -q 2>/dev/null
    ) >/dev/null 2>&1
    git clone -q "$tmpdir/remote.git" "$tmpdir/pc2" 2>/dev/null
    (
        cd "$tmpdir/pc2"
        git config user.email test2@test.com
        git config user.name Test2
        git config commit.gpgsign false
    ) >/dev/null 2>&1
    echo "$tmpdir"
}

echo "=== boardgroup base-aware merge Tests ==="
echo ""

# --- Test 1: the cleared side wins over an unrelated labels-only edit ---
echo "--- Test 1: cleared boardgroup beats an unrelated labels-only edit ---"

TMP1="$(setup_repos)"

# pc2 CLEARS the group (writes the tombstone) and pushes.
(
    cd "$TMP1/pc2"
    write_task aitasks/t1_sample.md "[ui]" 'boardgroup: ""' "2026-01-01 10:00"
    git add -A; git commit -q -m "pc2: ungroup"; git push -q 2>/dev/null
) >/dev/null 2>&1

# local changes ONLY labels, still carrying the old group, with a NEWER stamp.
# Under newer-wins this side would win a field it never touched.
(
    cd "$TMP1/local"
    write_task aitasks/t1_sample.md "[api, ui]" "boardgroup: perf_work" "2026-01-01 12:00"
    git add -A; git commit -q -m "local: labels only"
) >/dev/null 2>&1

# POSITIVE CONTROL: the rebase must genuinely conflict. Without this the test
# could pass on a clean textual auto-merge that never invoked the driver.
(cd "$TMP1/local" && git fetch -q origin 2>/dev/null
 git rebase origin/main >/dev/null 2>&1 || git rebase origin/master >/dev/null 2>&1 || true)
unmerged=$(cd "$TMP1/local" && git diff --name-only --diff-filter=U 2>/dev/null)
assert_contains "Fixture produces a real unmerged path (control)" \
    "aitasks/t1_sample.md" "$unmerged"
(cd "$TMP1/local" && git rebase --abort >/dev/null 2>&1 || true)

output=$(cd "$TMP1/local" && ./ait sync --batch 2>/dev/null)
assert_eq_trim "Conflict auto-resolves" "AUTOMERGED" "$output"

merged=$(cat "$TMP1/local/aitasks/t1_sample.md")
assert_eq "Cleared side wins - tombstone survives as an empty STRING" \
    "str:''" "$(parsed_boardgroup "$TMP1/local/aitasks/t1_sample.md")"
assert_contains "Local labels edit is preserved" "api" "$merged"

rm -rf "$TMP1"

# --- Test 2: the withheld-base NEGATIVE CONTROL ---
echo "--- Test 2: negative control - without the base the same case is PARTIAL ---"

TMP2="$(mktemp -d)"
mkdir -p "$TMP2/aitasks"
# A conflicted file exactly as git would leave it (2-way markers, the style the
# repo actually produces — merge.conflictStyle is configured nowhere).
cat > "$TMP2/aitasks/t1_sample.md" <<'EOF'
---
priority: high
status: Ready
<<<<<<< HEAD
labels: [ui]
boardgroup: ""
=======
labels: [api, ui]
boardgroup: perf_work
>>>>>>> local
updated_at: 2026-01-01 12:00
---
Body stays the same
EOF
cp "$TMP2/aitasks/t1_sample.md" "$TMP2/with_base.md"
write_task "$TMP2/base.md" "[ui]" "boardgroup: perf_work" "2026-01-01 09:00"

# WITHOUT --base-file: nothing can say which side changed it -> fail closed.
out_nobase=$(cd "$PROJECT_DIR/.aitask-scripts/board" && \
    PYTHONDONTWRITEBYTECODE=1 python3 aitask_merge.py "$TMP2/aitasks/t1_sample.md" \
    --batch --rebase 2>/dev/null); rc_nobase=$?
assert_eq "Without a base the divergence is PARTIAL (exit 2)" "2" "$rc_nobase"
assert_contains "PARTIAL names boardgroup" "boardgroup" "$out_nobase"

# WITH --base-file: the same input resolves. This is what proves the base — and
# not some incidental difference in the fixture — is what decided it.
out_base=$(cd "$PROJECT_DIR/.aitask-scripts/board" && \
    PYTHONDONTWRITEBYTECODE=1 python3 aitask_merge.py "$TMP2/with_base.md" \
    --batch --rebase --base-file "$TMP2/base.md" 2>/dev/null); rc_base=$?
assert_eq "With a base the same input resolves (exit 0)" "0" "$rc_base"
assert_contains "Driver reports RESOLVED when the base decided it" \
    "RESOLVED" "$out_base"
assert_eq "Resolved file keeps the tombstone as an empty STRING" \
    "str:''" "$(parsed_boardgroup "$TMP2/with_base.md")"

rm -rf "$TMP2"

# --- Test 3: guard - every driver invocation site passes --base-file ---
echo "--- Test 3: guard - all aitask_sync.sh driver invocations pass a base ---"

SYNC="$PROJECT_DIR/.aitask-scripts/aitask_sync.sh"
invocations=$(grep -c '"\$_MERGE_PYTHON" "\$_MERGE_SCRIPT"' "$SYNC")
with_base=$(grep '"\$_MERGE_PYTHON" "\$_MERGE_SCRIPT"' "$SYNC" | grep -c 'base_args')
assert_eq "At least one driver invocation exists (guard is not vacuous)" \
    "1" "$([[ $invocations -ge 1 ]] && echo 1 || echo 0)"
assert_eq "Every driver invocation passes --base-file" \
    "$invocations" "$with_base"

# --- Test 4: an add/add conflict has no stage 1 and must not crash ---
echo "--- Test 4: missing/unreadable base degrades, never crashes ---"

TMP4="$(mktemp -d)"
cat > "$TMP4/conflicted.md" <<'EOF'
---
priority: high
<<<<<<< HEAD
boardgroup: alpha
=======
boardgroup: beta
>>>>>>> local
updated_at: 2026-01-01 12:00
---
Body
EOF
out4=$(cd "$PROJECT_DIR/.aitask-scripts/board" && \
    PYTHONDONTWRITEBYTECODE=1 python3 aitask_merge.py "$TMP4/conflicted.md" \
    --batch --rebase --base-file "$TMP4/does_not_exist.md" 2>/dev/null); rc4=$?
assert_eq "Unreadable base behaves like no base (PARTIAL, not a crash)" "2" "$rc4"
assert_contains "PARTIAL still names boardgroup" "boardgroup" "$out4"

rm -rf "$TMP4"

# --- Test 5: negative control on the CONTROL - far-apart edits merge cleanly ---
echo "--- Test 5: control discriminates - non-adjacent edits never conflict ---"

TMP5="$(setup_repos)"
# Same two semantic edits, but with filler between them so the hunks do not
# overlap. If this produced an unmerged path too, Test 1's positive control
# would be trivially true and would prove nothing.
far_task() {
    local path="$1" labels="$2" group_line="$3"
    {
        echo "---"
        echo "labels: $labels"
        echo "priority: high"
        echo "effort: low"
        echo "issue_type: bug"
        echo "status: Ready"
        echo "assigned_to: a@b.c"
        echo "created_at: 2026-01-01 08:00"
        echo "$group_line"
        echo "---"
        echo "Body stays the same"
    } > "$path"
}
(
    cd "$TMP5/local"
    far_task aitasks/t1_sample.md "[ui]" "boardgroup: perf_work"
    git add -A; git commit -q -m "base far"; git push -q 2>/dev/null
) >/dev/null 2>&1
(
    cd "$TMP5/pc2"
    git pull -q 2>/dev/null
    far_task aitasks/t1_sample.md "[ui]" 'boardgroup: ""'
    git add -A; git commit -q -m "pc2: ungroup far"; git push -q 2>/dev/null
) >/dev/null 2>&1
(
    cd "$TMP5/local"
    far_task aitasks/t1_sample.md "[api, ui]" "boardgroup: perf_work"
    git add -A; git commit -q -m "local: status far"
    git fetch -q origin 2>/dev/null
    git rebase origin/main >/dev/null 2>&1 || git rebase origin/master >/dev/null 2>&1 || true
) >/dev/null 2>&1
far_unmerged=$(cd "$TMP5/local" && git diff --name-only --diff-filter=U 2>/dev/null)
assert_eq "Non-adjacent edits produce NO unmerged path" "" "$far_unmerged"

rm -rf "$TMP5"

# --- Test 6: followup_kind shares the resolver but DELETES, not tombstones ---
echo "--- Test 6: followup_kind clear removes the key end-to-end (t1468_1) ---"
# boardgroup persists "" to mean "deliberately ungrouped", so its resolved file
# keeps `boardgroup: ''` (Test 2). followup_kind has NO tombstone: a clear must
# leave no line at all. Same driver, same --base-file mechanism -- the contrast
# with Test 2's `str:''` is the point.
TMP6="$(mktemp -d)"
mkdir -p "$TMP6/aitasks"
cat > "$TMP6/aitasks/t1_sample.md" <<'EOF'
---
priority: high
effort: medium
depends: []
issue_type: feature
status: Ready
<<<<<<< remote
labels: [ui, backend]
followup_kind: risk_mitigation
=======
labels: [ui, perf]
>>>>>>> local
updated_at: 2026-01-01 12:00
---
Body stays the same
EOF
cp "$TMP6/aitasks/t1_sample.md" "$TMP6/with_base.md"
cat > "$TMP6/base.md" <<'EOF'
---
priority: high
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [ui]
followup_kind: risk_mitigation
updated_at: 2026-01-01 09:00
---
Body stays the same
EOF

out6=$(cd "$PROJECT_DIR/.aitask-scripts/board" && \
    PYTHONDONTWRITEBYTECODE=1 python3 aitask_merge.py "$TMP6/with_base.md" \
    --batch --rebase --base-file "$TMP6/base.md" 2>/dev/null); rc6=$?
assert_eq "Local clear of followup_kind resolves against the base (exit 0)" "0" "$rc6"
assert_contains "Driver reports RESOLVED for the cleared kind" "RESOLVED" "$out6"
assert_eq "Cleared followup_kind is ABSENT, not a null or empty string" \
    "ABSENT" "$(parsed_field "$TMP6/with_base.md" followup_kind)"
assert_not_contains "Resolved file carries no followup_kind line at all" \
    "followup_kind" "$(cat "$TMP6/with_base.md")"

rm -rf "$TMP6"

# --- Summary ---
echo ""
echo "=== Results: $PASS passed, $FAIL failed (of $TOTAL) ==="
[[ $FAIL -eq 0 ]] || exit 1
exit 0
