#!/usr/bin/env bash
# test_pick_own_scoped_commit.sh - a task claim must commit ONLY the paths it
# owns (t1599_1). Run: bash tests/test_pick_own_scoped_commit.sh
#
# Before this, aitask_pick_own.sh did `task_git add aitasks/` then an unscoped
# `task_git commit`, so any file a concurrent session was mid-edit on landed in
# a commit whose message named a different task. Measured on this repo's data
# branch: 28% of claim commits carried a foreign task file.
#
# --- CHARACTERIZATION: partial-commit semantics -----------------------------
# (pre-phase risk mitigation `partial_commit_worktree_semantics`, run before the
# scoping edit; the other t1599 children inherit this pattern.)
#
#   `git commit -m <msg> -- <paths>` is a PARTIAL commit. VERIFIED ANSWER: it
#   commits the WORKTREE content of those paths and IGNORES their staged index
#   entry. A path staged as v2 and then modified on disk to v3 lands in the
#   commit as v3. Afterwards that path is clean, and every OTHER staged-or-dirty
#   path is left exactly as it was.
#
#   Also VERIFIED, and why _commit_scoped passes `-o` and guards an empty array:
#   `git commit -o -m msg --` with an EMPTY pathspec is fatal (exit 128, "No
#   paths with --include/--only does not make sense"), whereas `git commit -m
#   msg --` with an empty pathspec silently commits the WHOLE index — exactly
#   the bug being fixed.
#
# --- Negative control -------------------------------------------------------
# `install_prefix_commit_and_push` rebuilds the fixture's COPY of the script
# with the pre-fix body, so the control is executable on every run rather than a
# one-off instruction that expires once the fix lands. It asserts the defect is
# POSITIVELY present, so a control whose injection silently failed cannot pass.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

CLAIM_SUBJECT_RE='^ait: Start work on t'
EMAILS_PATH="aitasks/metadata/emails.txt"

# assert_non_empty <desc> <value> — the shared helpers have no non-empty form,
# and assert_not_contains "" can never pass (every string contains "").
assert_non_empty() {
    local desc="$1" value="$2"
    TOTAL=$((TOTAL + 1))
    if [[ -n "$value" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected a non-empty value, got '')"
    fi
}

# --- Fixture ---------------------------------------------------------------

# Paired bare remote + clone with full aitask_pick_own.sh support, a claimable
# t1, a committed bystander t2, and a seeded contributor list.
setup_paired_repos() {
    local tmpdir
    tmpdir="$(mktemp -d)"

    local remote_dir="$tmpdir/remote.git"
    git init --bare --quiet "$remote_dir"

    local local_dir="$tmpdir/local"
    git clone --quiet "$remote_dir" "$local_dir"
    (
        cd "$local_dir"
        git config user.email "test@test.com"
        git config user.name "Test"

        mkdir -p aitasks/archived aitasks/metadata aiplans

        cat > aitasks/t1_test_task.md <<'TASK'
---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: []
created_at: 2026-01-01 00:00
updated_at: 2026-01-01 00:00
---

Task under claim.
TASK

        cat > aitasks/t2_bystander.md <<'TASK'
---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: []
created_at: 2026-01-01 00:00
updated_at: 2026-01-01 00:00
---

Bystander owned by another session.
TASK

        echo "seed@test.com" > aitasks/metadata/emails.txt

        setup_fake_aitask_repo "$PWD"
        cp "$PROJECT_DIR/.aitask-scripts/aitask_lock.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_pick_own.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/pid_anchor.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
        # registry_lock.sh + stale_lock.sh (the contributor-list mutex) come
        # from setup_fake_aitask_repo above.
        cp "$PROJECT_DIR/ait" . 2>/dev/null || true
        chmod +x .aitask-scripts/*.sh ait 2>/dev/null || true

        git add -A
        git commit -m "Initial setup" --quiet
        git push --quiet 2>/dev/null

        ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1
    )

    echo "$tmpdir"
}

# Rebuild the fixture's COPY of aitask_pick_own.sh with the PRE-FIX
# commit_and_push. The script's last line is a single `main "$@"`, so appending
# the legacy definition ahead of it makes bash use it — no edit to the real
# function, and nothing outside this throwaway repo is touched.
install_prefix_commit_and_push() {
    local script="$1/local/.aitask-scripts/aitask_pick_own.sh"
    local tmp="$script.new"
    grep -v '^main "\$@"$' "$script" > "$tmp"    # portable; no sed -i
    cat >> "$tmp" <<'LEGACY'
commit_and_push() {
    local task_id="$1"
    task_git add aitasks/
    if task_git diff --cached --quiet; then
        info "No changes to commit"
    else
        task_git commit -m "ait: Start work on t${task_id}: set status to Implementing" --quiet
    fi
    task_push
}
LEGACY
    printf 'main "$@"\n' >> "$tmp"
    mv "$tmp" "$script"
    chmod +x "$script"
}

# Commits whose subject is a claim AND that touch <path>. Empty = the invariant
# holds. This is the property under test, and it holds under every interleaving.
claim_commits_touching() {
    git -C "$1/local" log --format=%H --grep="$CLAIM_SUBJECT_RE" -- "$2"
}

# Files touched by HEAD.
head_files() {
    git -C "$1/local" show --name-status --pretty=format: -M0 HEAD
}

set +e

echo "=== Pick-own scoped claim commit (t1599_1) ==="
echo ""

# --- Test 1: the claim commit carries only the claimed task's paths ---------
echo "--- Test 1: claim commit does not sweep a dirty bystander ---"

T1="$(setup_paired_repos)"
# A concurrent session's in-flight edit, committed-then-dirtied.
(cd "$T1/local" && printf '\nMid-edit by another session.\n' >> aitasks/t2_bystander.md)

out1=$(cd "$T1/local" && ./.aitask-scripts/aitask_pick_own.sh 1 --email "alice@test.com" 2>&1)
assert_contains "Test 1: claim succeeded" "OWNED:1" "$out1"

subject1=$(git -C "$T1/local" log -1 --pretty=%s)
assert_eq "Test 1: HEAD is the claim commit" \
    "ait: Start work on t1: set status to Implementing" "$subject1"

files1=$(head_files "$T1")
assert_contains "Test 1: claimed task file IS in the commit" "aitasks/t1_test_task.md" "$files1"
assert_not_contains "Test 1: bystander NOT in the commit" "t2_bystander" "$files1"

status1=$(git -C "$T1/local" status --porcelain aitasks/t2_bystander.md)
assert_contains "Test 1: bystander still modified-but-unstaged" \
    " M aitasks/t2_bystander.md" "$status1"

rm -rf "$T1"

# --- Test 2: characterization — partial commit takes worktree content -------
echo "--- Test 2: partial commit captures the WORKTREE version, not the index ---"

T2="$(setup_paired_repos)"
(
    cd "$T2/local"
    printf '\nSTAGED_ONLY_MARKER\n' >> aitasks/t1_test_task.md
    git add aitasks/t1_test_task.md
    # Now diverge the worktree from what was just staged.
    sed -i.bak 's/STAGED_ONLY_MARKER/WORKTREE_ONLY_MARKER/' aitasks/t1_test_task.md
    rm -f aitasks/t1_test_task.md.bak
)

out2=$(cd "$T2/local" && ./.aitask-scripts/aitask_pick_own.sh 1 --email "alice@test.com" 2>&1)
assert_contains "Test 2: claim succeeded" "OWNED:1" "$out2"

committed2=$(git -C "$T2/local" show HEAD:aitasks/t1_test_task.md)
assert_contains "Test 2: worktree version landed" "WORKTREE_ONLY_MARKER" "$committed2"
assert_not_contains "Test 2: staged-only version did NOT land" "STAGED_ONLY_MARKER" "$committed2"

rm -rf "$T2"

# --- Test 3: idempotent re-claim creates no new commit ----------------------
echo "--- Test 3: re-claiming an already-Implementing task adds no commit ---"

T3="$(setup_paired_repos)"
(cd "$T3/local" && ./.aitask-scripts/aitask_pick_own.sh 1 --email "alice@test.com" >/dev/null 2>&1)
before3=$(git -C "$T3/local" rev-list --count HEAD)
out3=$(cd "$T3/local" && ./.aitask-scripts/aitask_pick_own.sh 1 --email "alice@test.com" 2>&1)
after3=$(git -C "$T3/local" rev-list --count HEAD)

assert_contains "Test 3: re-claim still reports ownership" "OWNED:1" "$out3"
assert_eq "Test 3: no new commit on re-claim" "$before3" "$after3"

rm -rf "$T3"

# --- Test 4: a refused claim's leftover email is never swept ----------------
echo "--- Test 4: a foreign email left by a REFUSED claim is not committed ---"

T4="$(setup_paired_repos)"
# Reach the dirty state through the production path: a claim refused at the lock
# has already appended its address (store_email runs before acquire_lock).
(cd "$T4/local" && ./.aitask-scripts/aitask_lock.sh --lock 1 --email "bob@test.com" >/dev/null 2>&1)
refused4=$(cd "$T4/local" && ./.aitask-scripts/aitask_pick_own.sh 1 --email "mallory@test.com" 2>&1)
assert_contains "Test 4: the foreign claim was refused" "LOCK_FAILED" "$refused4"

pre4=$(git -C "$T4/local" status --porcelain "$EMAILS_PATH")
assert_contains "Test 4: precondition — emails.txt left dirty by the refused claim" \
    " M $EMAILS_PATH" "$pre4"

(cd "$T4/local" && ./.aitask-scripts/aitask_lock.sh --unlock 1 >/dev/null 2>&1)
# alice is NOT yet known, so this claim legitimately adds her; mallory's line
# must still not be attributed to the claim.
out4=$(cd "$T4/local" && ./.aitask-scripts/aitask_pick_own.sh 1 --email "alice@test.com" 2>&1)
assert_contains "Test 4: claim succeeded" "OWNED:1" "$out4"

offenders4=$(claim_commits_touching "$T4" "$EMAILS_PATH")
assert_eq "Test 4: no claim commit touches emails.txt" "" "$offenders4"

disk4=$(cat "$T4/local/$EMAILS_PATH")
assert_contains "Test 4: mallory's line survives on disk" "mallory@test.com" "$disk4"

rm -rf "$T4"

# --- Test 5: a claim with NO email never touches the list -------------------
echo "--- Test 5: a claim with no --email does not commit a dirty emails.txt ---"

T5="$(setup_paired_repos)"
(cd "$T5/local" && printf 'mallory@test.com\n' >> "$EMAILS_PATH")
out5=$(cd "$T5/local" && ./.aitask-scripts/aitask_pick_own.sh 1 2>&1)
assert_contains "Test 5: claim succeeded" "OWNED:1" "$out5"

offenders5=$(claim_commits_touching "$T5" "$EMAILS_PATH")
assert_eq "Test 5: no claim commit touches emails.txt" "" "$offenders5"

status5=$(git -C "$T5/local" status --porcelain "$EMAILS_PATH")
assert_contains "Test 5: emails.txt still unstaged" " M $EMAILS_PATH" "$status5"

rm -rf "$T5"

# --- Test 6: positive direction — a new address DOES get persisted ----------
# Without this, tests 4/5 would pass vacuously against a fix that simply never
# commits the contributor list.
echo "--- Test 6: a genuinely new address lands in its own commit ---"

T6="$(setup_paired_repos)"
out6=$(cd "$T6/local" && ./.aitask-scripts/aitask_pick_own.sh 1 --email "alice@test.com" 2>&1)
assert_contains "Test 6: claim succeeded" "OWNED:1" "$out6"

subject6=$(git -C "$T6/local" log -1 --pretty=%s)
assert_eq "Test 6: HEAD is still the claim commit" \
    "ait: Start work on t1: set status to Implementing" "$subject6"

claim_files6=$(head_files "$T6")
assert_not_contains "Test 6: claim commit does NOT carry emails.txt" \
    "metadata/emails.txt" "$claim_files6"

email_commit6=$(git -C "$T6/local" log --format=%H --grep='^ait: Record contributor email' | head -1)
assert_non_empty "Test 6: an email commit exists" "$email_commit6"

email_files6=$(git -C "$T6/local" show --name-only --pretty=format: "$email_commit6" | grep -v '^$')
assert_eq "Test 6: the email commit touches ONLY emails.txt" "$EMAILS_PATH" "$email_files6"

clean6=$(git -C "$T6/local" status --porcelain "$EMAILS_PATH")
assert_eq "Test 6: emails.txt is clean afterwards" "" "$clean6"

rm -rf "$T6"

# --- Test 7: interleaved two-task claim -------------------------------------
# The shape a concurrent store_email leaves behind: another session's address
# appended and uncommitted at the moment this claim commits.
echo "--- Test 7: a concurrent session's append never rides in the claim ---"

T7="$(setup_paired_repos)"
(
    cd "$T7/local"
    printf 'bob@test.com\n' >> "$EMAILS_PATH"
    sort -u "$EMAILS_PATH" -o "$EMAILS_PATH"
)
out7=$(cd "$T7/local" && ./.aitask-scripts/aitask_pick_own.sh 1 --email "alice@test.com" 2>&1)
assert_contains "Test 7: claim succeeded" "OWNED:1" "$out7"

offenders7=$(claim_commits_touching "$T7" "$EMAILS_PATH")
assert_eq "Test 7: no claim commit touches emails.txt" "" "$offenders7"

email_commit7=$(git -C "$T7/local" log --format=%H --grep='^ait: Record contributor email' | head -1)
email_body7=$(git -C "$T7/local" show "$email_commit7:$EMAILS_PATH")
assert_contains "Test 7: the email commit carries alice" "alice@test.com" "$email_body7"
assert_contains "Test 7: ...and bob — accurate, since its message names no task" \
    "bob@test.com" "$email_body7"

rm -rf "$T7"

# --- Test 8: mutex boundary -------------------------------------------------
# A busy contributor-list mutex must never write unlocked, and must never fail
# the claim. Both sides of the boundary are pinned.
echo "--- Test 8: a busy contributor-list mutex skips the write, not the claim ---"

T8="$(setup_paired_repos)"
LOCKBASE8="$T8/locks"
mkdir -p "$LOCKBASE8/emails"
sleep 60 &
HOLDER8=$!
echo "$HOLDER8" > "$LOCKBASE8/emails/pid"

before8=$(cat "$T8/local/$EMAILS_PATH")
out8=$(cd "$T8/local" && AITASKS_LOCK_DIR="$LOCKBASE8" EMAILS_LOCK_TIMEOUT=1 \
    ./.aitask-scripts/aitask_pick_own.sh 1 --email "alice@test.com" 2>&1)

assert_contains "Test 8: the claim still succeeds" "OWNED:1" "$out8"
assert_contains "Test 8: the skip is reported" "contributor list busy" "$out8"

after8=$(cat "$T8/local/$EMAILS_PATH")
assert_eq "Test 8: emails.txt unchanged — never written unlocked" "$before8" "$after8"

email8=$(git -C "$T8/local" log --format=%H --grep='^ait: Record contributor email')
assert_eq "Test 8: no contributor-email commit was made" "" "$email8"

claim8=$(head_files "$T8")
assert_contains "Test 8: the claim commit still landed" "aitasks/t1_test_task.md" "$claim8"

# Other side of the boundary: release the mutex and the address now lands.
kill "$HOLDER8" 2>/dev/null
wait "$HOLDER8" 2>/dev/null
rm -rf "$LOCKBASE8/emails"
out8b=$(cd "$T8/local" && AITASKS_LOCK_DIR="$LOCKBASE8" EMAILS_LOCK_TIMEOUT=1 \
    ./.aitask-scripts/aitask_pick_own.sh 1 --email "alice@test.com" 2>&1)
assert_contains "Test 8b: re-claim succeeded" "OWNED:1" "$out8b"

after8b=$(cat "$T8/local/$EMAILS_PATH")
assert_contains "Test 8b: the address lands once the mutex is free" \
    "alice@test.com" "$after8b"

rm -rf "$T8"

# --- Test 9: NEGATIVE CONTROL — the pre-fix code must exhibit the defect ----
# Asserts the defect POSITIVELY. If the legacy injection silently failed, these
# assertions fail rather than quietly passing.
echo "--- Test 9: NEGATIVE CONTROL — pre-fix commit_and_push sweeps bystanders ---"

T9="$(setup_paired_repos)"
install_prefix_commit_and_push "$T9"
(cd "$T9/local" && printf '\nMid-edit by another session.\n' >> aitasks/t2_bystander.md)
(cd "$T9/local" && printf 'mallory@test.com\n' >> "$EMAILS_PATH")

out9=$(cd "$T9/local" && ./.aitask-scripts/aitask_pick_own.sh 1 --email "alice@test.com" 2>&1)
assert_contains "Test 9: control ran to completion (not an early abort)" "OWNED:1" "$out9"

files9=$(head_files "$T9")
assert_contains "Test 9: pre-fix DOES sweep the bystander" "t2_bystander" "$files9"
assert_contains "Test 9: pre-fix DOES sweep emails.txt into the claim" \
    "metadata/emails.txt" "$files9"

offenders9=$(claim_commits_touching "$T9" "$EMAILS_PATH")
assert_non_empty "Test 9: pre-fix violates the claim-commit invariant" "$offenders9"

email9=$(git -C "$T9/local" log --format=%H --grep='^ait: Record contributor email')
assert_eq "Test 9: pre-fix makes no separate contributor-email commit" "" "$email9"

rm -rf "$T9"

# --- Test 10: syntax ---------------------------------------------------------
echo "--- Test 10: syntax check ---"
TOTAL=$((TOTAL + 1))
if bash -n "$PROJECT_DIR/.aitask-scripts/aitask_pick_own.sh" 2>/dev/null; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: aitask_pick_own.sh syntax check"
fi

# --- Summary ---
echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
