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

# Rebuild the fixture's COPY with the PRE-FIX store_email — three UNCHAINED
# statements and the single warning (t1614). Same technique and rationale as
# install_prefix_commit_and_push above: the control stays executable on every
# run instead of expiring once the fix landed.
install_prefix_store_email() {
    local script="$1/local/.aitask-scripts/aitask_pick_own.sh"
    local tmp="$script.new"
    grep -v '^main "\$@"$' "$script" > "$tmp"
    cat >> "$tmp" <<'LEGACY'
store_email() {
    local email="$1"
    if [[ -z "$email" ]]; then
        return 0
    fi
    local dir
    dir=$(dirname "$EMAILS_FILE")
    mkdir -p "$dir"
    touch "$EMAILS_FILE"
    grep -qxF -- "$email" "$EMAILS_FILE" 2>/dev/null && return 0
    local lockdir
    lockdir="$(ait_lock_dir emails)" || return 0
    if ! registry_lock_acquire "$lockdir" "$EMAILS_LOCK_TIMEOUT" store_email; then
        warn "contributor list busy — email not recorded$(registry_lock_describe "$lockdir")"
        return 0
    fi
    local rc=0
    {
        if ! grep -qxF -- "$email" "$EMAILS_FILE" 2>/dev/null; then
            printf '%s\n' "$email" >> "$EMAILS_FILE"
            sort -u "$EMAILS_FILE" -o "$EMAILS_FILE"
            EMAIL_STORED=true
        fi
    } || rc=$?
    registry_lock_release "$lockdir"
    [[ $rc -eq 0 ]] || warn "store_email: failed to record ${email} (rc=$rc)"
    return 0
}
LEGACY
    printf 'main "$@"\n' >> "$tmp"
    mv "$tmp" "$script"
    chmod +x "$script"
}

# Make the emails APPEND — and nothing else — fail, by shadowing the printf
# BUILTIN with a function for the duration of the fixture's script copy (t1614).
# A PATH shim cannot reach a builtin, and permissions cannot discriminate: a mode
# that blocks the append blocks `sort -o` on the same file too, so both would
# fail and the branch under test would never be isolated.
#
# `${FUNCNAME[1]}` is what makes it exact — only the call inside store_email
# fails; every other printf in the script (including the one inside warn) is
# untouched.
install_failing_append() {
    local script="$1/local/.aitask-scripts/aitask_pick_own.sh"
    local tmp="$script.new"
    grep -v '^main "\$@"$' "$script" > "$tmp"
    cat >> "$tmp" <<'INJECT'
printf() {
    if [[ "${FUNCNAME[1]:-}" == "store_email" ]]; then
        return 1
    fi
    builtin printf "$@"
}
INJECT
    printf 'main "$@"\n' >> "$tmp"
    mv "$tmp" "$script"
    chmod +x "$script"
}

# Make the emails SORT — and nothing else — fail, so the append succeeds and the
# normalization does not (t1614). The complement of install_failing_append: it is
# the only way to reach the partial-success branch, which the append-failure
# tests cannot see. Lifted from tests/test_create_email_lock.sh Test 5.
#
# Echoes the shim dir; prepend it to PATH for the run under test.
install_failing_sort() {
    local shim="$1/shim"
    local real_sort
    real_sort="$(command -v sort)"     # resolved BEFORE the prepend, so no recursion
    mkdir -p "$shim"
    cat > "$shim/sort" <<EOF
#!/usr/bin/env bash
want_o=""; want_emails=""
for a in "\$@"; do
    case "\$a" in
        -o)          want_o=1 ;;
        *emails.txt) want_emails=1 ;;
    esac
done
if [[ -n "\$want_o" && -n "\$want_emails" ]]; then exit 1; fi
exec "$real_sort" "\$@"
EOF
    chmod +x "$shim/sort"
    echo "$shim"
}

# Rebuild the fixture's COPY with the PRE-FIX ORDERING: store_email called from
# INSIDE acquire_lock, i.e. before the lock gate can refuse (t1626). Paired with
# install_prefix_store_email, which supplies the pre-fix body whose membership
# fast-path never consults HEAD — both halves are needed, because the fixed fast
# path would otherwise recover the stranded address on the retry and the control
# would not reproduce.
#
# The wrapper renames the real function via `declare -f` rather than restating
# its body, so the control cannot drift from the code it is a control for.
install_prefix_store_email_ordering() {
    local script="$1/local/.aitask-scripts/aitask_pick_own.sh"
    local tmp="$script.new"
    grep -v '^main "\$@"$' "$script" > "$tmp"
    cat >> "$tmp" <<'LEGACY'
eval "_orig_acquire_lock() $(declare -f acquire_lock | tail -n +2)"
acquire_lock() {
    [[ -n "${2:-}" ]] && store_email "$2"
    _orig_acquire_lock "$@"
}
LEGACY
    printf 'main "$@"\n' >> "$tmp"
    mv "$tmp" "$script"
    chmod +x "$script"
}

# Rebuild the fixture's COPY with a store_email that has the PRE-LOCK HEAD
# consult but NOT the under-lock one (t1626). This is the control for Test 4d
# specifically: without it, 4d could pass on the pre-lock fix alone and would
# prove nothing about the `else` branch it exists to guard.
install_prefix_store_email_norecheck() {
    local script="$1/local/.aitask-scripts/aitask_pick_own.sh"
    local tmp="$script.new"
    grep -v '^main "\$@"$' "$script" > "$tmp"
    cat >> "$tmp" <<'LEGACY'
store_email() {
    local email="$1"
    if [[ -z "$email" ]]; then
        return 0
    fi
    local dir
    dir=$(dirname "$EMAILS_FILE")
    mkdir -p "$dir"
    touch "$EMAILS_FILE"
    if grep -qxF -- "$email" "$EMAILS_FILE" 2>/dev/null; then
        ait_email_is_committed "$email" || EMAIL_STORED=true
        return 0
    fi
    local lockdir
    lockdir="$(ait_lock_dir emails)" || return 0
    if ! registry_lock_acquire "$lockdir" "$EMAILS_LOCK_TIMEOUT" store_email; then
        warn "contributor list busy — email not recorded$(registry_lock_describe "$lockdir")"
        return 0
    fi
    local rc=0
    {
        if ! grep -qxF -- "$email" "$EMAILS_FILE" 2>/dev/null; then
            printf '%s\n' "$email" >> "$EMAILS_FILE" &&
                EMAIL_STORED=true &&
                sort -u "$EMAILS_FILE" -o "$EMAILS_FILE"
        fi
    } || rc=$?
    registry_lock_release "$lockdir"
    [[ $rc -eq 0 ]] || warn "store_email: failed to record ${email} (rc=$rc)"
    return 0
}
LEGACY
    printf 'main "$@"\n' >> "$tmp"
    mv "$tmp" "$script"
    chmod +x "$script"
}

# --- Bounded condition waits (lifted from tests/test_create_email_lock.sh) ---
# Each returns 1 on timeout so the caller can FAIL with a specific message. A
# scenario that did not actually reproduce must never report success by running
# slow, so every wait below is a poll on a CONDITION, never a chosen sleep.

wait_for_file() {      # <path> <timeout_s>
    local path="$1" ticks=$(( ${2} * 10 )) i=0
    while (( i < ticks )); do
        [[ -e "$path" ]] && return 0
        sleep 0.1
        i=$((i + 1))
    done
    return 1
}

wait_for_content() {   # <file> <needle> <timeout_s>
    local file="$1" needle="$2" ticks=$(( ${3} * 10 )) i=0
    while (( i < ticks )); do
        grep -qF -- "$needle" "$file" 2>/dev/null && return 0
        sleep 0.1
        i=$((i + 1))
    done
    return 1
}

# install_acquire_barrier <tmpdir> — patch the FIXTURE'S COPY of
# lib/registry_lock.sh so registry_lock_acquire pauses at a controllable barrier
# before it contends for the mutex.
#
# That point is the seam between store_email's PRE-LOCK membership check and its
# mutex acquisition, and blocking there is the only way to pin the interleaving
# deterministically: the claim's pre-lock check must observe the address ABSENT,
# and the other writer's append must land before the claim's UNDER-LOCK re-check.
# Waiting on wall-clock instead would let a scenario that never reproduced
# report success by running slow.
#
# The barrier is opt-in per run (AIT_TEST_ACQ_SIGNAL / AIT_TEST_ACQ_GO), so the
# patched copy behaves exactly like the real library for every other test, and
# the HOLDER below is unaffected — it sources the PROJECT's unpatched library.
install_acquire_barrier() {
    local lib="$1/local/.aitask-scripts/lib/registry_lock.sh"
    local tmp="$lib.new"
    awk '
        /^registry_lock_acquire\(\) \{$/ {
            print
            print "    if [[ -n \"${AIT_TEST_ACQ_SIGNAL:-}\" ]]; then"
            print "        : > \"$AIT_TEST_ACQ_SIGNAL\""
            print "        while [[ ! -f \"${AIT_TEST_ACQ_GO:-}\" ]]; do sleep 0.05; done"
            print "    fi"
            next
        }
        { print }
    ' "$lib" > "$tmp"
    mv "$tmp" "$lib"
}

# write_holder <tmpdir> — emit a helper that plays the OTHER contributor-list
# writer: take the mutex through registry_lock.sh (the adapter store_email
# itself takes), append the address, release, and EXIT WITHOUT COMMITTING.
# That last part is the whole point — it is exactly the "appended, released,
# then died before its own commit" end state.
#
# It sources the PROJECT's library, not the fixture's patched copy, so the
# barrier above never applies to it.
#
# Echoes the helper's path.
write_holder() {
    local dir="$1/holder"
    mkdir -p "$dir"
    cat > "$dir/holder.sh" <<EOF
#!/usr/bin/env bash
set -u
LIB="$PROJECT_DIR/.aitask-scripts/lib"
EOF
    cat >> "$dir/holder.sh" <<'HOLDER'
# shellcheck source=/dev/null
source "$LIB/terminal_compat.sh"
# shellcheck source=/dev/null
source "$LIB/registry_lock.sh"

lockdir="$1"; emails="$2"; addr="$3"

if ! registry_lock_acquire "$lockdir" 30 holder; then
    echo "HOLDER_BUSY"
    exit 1
fi
printf '%s\n' "$addr" >> "$emails"
sort -u "$emails" -o "$emails"
registry_lock_release "$lockdir"
echo "HOLDER_DONE"
HOLDER
    chmod +x "$dir/holder.sh"
    echo "$dir/holder.sh"
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

# --- Test 4: a foreign email already on the list is never swept -------------
# The dirty state is seeded DIRECTLY. It used to be reached through the defect
# — a refused claim appended before the lock gate could refuse — but a refused
# claim now writes nothing at all (t1626, Test 4b), so driving it that way would
# characterize a bug that is gone instead of the invariant this test guards.
echo "--- Test 4: a foreign email on the list is not attributed to a claim ---"

T4="$(setup_paired_repos)"
(cd "$T4/local" && printf 'mallory@test.com\n' >> "$EMAILS_PATH")

pre4=$(git -C "$T4/local" status --porcelain "$EMAILS_PATH")
assert_contains "Test 4: precondition — emails.txt is dirty with a foreign address" \
    " M $EMAILS_PATH" "$pre4"

# alice is NOT yet known, so this claim legitimately adds her; mallory's line
# must still not be attributed to the claim.
out4=$(cd "$T4/local" && ./.aitask-scripts/aitask_pick_own.sh 1 --email "alice@test.com" 2>&1)
assert_contains "Test 4: claim succeeded" "OWNED:1" "$out4"

offenders4=$(claim_commits_touching "$T4" "$EMAILS_PATH")
assert_eq "Test 4: no claim commit touches emails.txt" "" "$offenders4"

disk4=$(cat "$T4/local/$EMAILS_PATH")
assert_contains "Test 4: mallory's line survives on disk" "mallory@test.com" "$disk4"

rm -rf "$T4"

# --- Test 4b: a REFUSED claim writes nothing; the same-address retry lands ---
# The gap Test 4 cannot cover. Test 4 retried with a DIFFERENT address, which
# legitimately set EMAIL_STORED and swept the stranded line along incidentally.
# With the SAME address the old membership fast-path returned before the flag
# could ever be set again, so no later claim committed it — emails.txt stayed
# dirty indefinitely (t1626 defect 1).
echo "--- Test 4b: a refused claim writes nothing, and the same-address retry commits ---"

T4B="$(setup_paired_repos)"
(cd "$T4B/local" && ./.aitask-scripts/aitask_lock.sh --lock 1 --email "bob@test.com" >/dev/null 2>&1)
refused4b=$(cd "$T4B/local" && ./.aitask-scripts/aitask_pick_own.sh 1 --email "mallory@test.com" 2>&1)
assert_contains "Test 4b: the claim was refused" "LOCK_FAILED" "$refused4b"

# The fix: store_email now runs BELOW every refusal exit, so nothing was written.
assert_eq "Test 4b: the refused claim left emails.txt CLEAN" \
    "" "$(git -C "$T4B/local" status --porcelain "$EMAILS_PATH")"
assert_not_contains "Test 4b: ...and never appended the address at all" \
    "mallory@test.com" "$(cat "$T4B/local/$EMAILS_PATH")"

(cd "$T4B/local" && ./.aitask-scripts/aitask_lock.sh --unlock 1 >/dev/null 2>&1)
out4b=$(cd "$T4B/local" && ./.aitask-scripts/aitask_pick_own.sh 1 --email "mallory@test.com" 2>&1)
assert_contains "Test 4b: the same-address retry succeeded" "OWNED:1" "$out4b"

assert_eq "Test 4b: emails.txt is clean after the retry" \
    "" "$(git -C "$T4B/local" status --porcelain "$EMAILS_PATH")"
assert_contains "Test 4b: the address is committed at HEAD" \
    "mallory@test.com" "$(git -C "$T4B/local" show "HEAD:$EMAILS_PATH")"
count4b=$(git -C "$T4B/local" log --format=%H --grep='^ait: Record contributor email' | wc -l)
assert_eq "Test 4b: exactly one contributor-email commit" "1" "$count4b"
assert_eq "Test 4b: no claim commit touches emails.txt" \
    "" "$(claim_commits_touching "$T4B" "$EMAILS_PATH")"

rm -rf "$T4B"

# --- Test 4c: PRE-LOCK fast-path recovery ------------------------------------
# An address on disk but not at HEAD — the end state of any write whose commit
# was lost. The membership fast-path used to return before EMAIL_STORED could be
# set, making that permanent; it now consults HEAD.
echo "--- Test 4c: a membership hit on an UNCOMMITTED address is recovered ---"

T4C="$(setup_paired_repos)"
(cd "$T4C/local" && printf 'mallory@test.com\n' >> "$EMAILS_PATH")

out4c=$(cd "$T4C/local" && ./.aitask-scripts/aitask_pick_own.sh 1 --email "mallory@test.com" 2>&1)
assert_contains "Test 4c: claim succeeded" "OWNED:1" "$out4c"

assert_eq "Test 4c: emails.txt is clean — the stranded address was recovered" \
    "" "$(git -C "$T4C/local" status --porcelain "$EMAILS_PATH")"
assert_contains "Test 4c: the address is committed at HEAD" \
    "mallory@test.com" "$(git -C "$T4C/local" show "HEAD:$EMAILS_PATH")"

email4c=$(git -C "$T4C/local" log --format=%H --grep='^ait: Record contributor email' | head -1)
assert_non_empty "Test 4c: a contributor-email commit was made" "$email4c"
files4c=$(git -C "$T4C/local" show --name-only --pretty=format: "$email4c" | grep -v '^$')
assert_eq "Test 4c: that commit touches ONLY emails.txt" "$EMAILS_PATH" "$files4c"
assert_eq "Test 4c: HEAD is still the claim commit" \
    "ait: Start work on t1: set status to Implementing" \
    "$(git -C "$T4C/local" log -1 --pretty=%s)"

rm -rf "$T4C"

# --- Test 4d: UNDER-LOCK recheck recovery ------------------------------------
# The concurrent hole the pre-lock fix alone does not close, and the widest
# window of the two writers: store_email runs under the mutex but its commit
# happens much later, in commit_and_push.
#
#   holder (registry_lock)        claim (store_email, under test)
#   ---------------------------   -----------------------------------------
#   acquire; ready
#                                 start; PRE-LOCK check runs — address ABSENT
#                                 ... blocks on the mutex
#   append addr; release; EXIT
#   (never commits)
#                                 acquires; RE-CHECK finds it ⇒ must consult
#                                 HEAD and commit it
echo "--- Test 4d: a holder's uncommitted append is recovered at the re-check ---"

run_recheck_scenario() {   # <mode: fixed|prefix> <label>
    local mode="$1" label="$2"
    local T; T="$(setup_paired_repos)"
    [[ "$mode" == "prefix" ]] && install_prefix_store_email_norecheck "$T"
    install_acquire_barrier "$T"

    local lockbase="$T/locks" holder
    local sig="$T/.at_acquire" go="$T/.acquire_go"
    holder="$(write_holder "$T")"
    mkdir -p "$lockbase"

    # 1. Start the claim. It runs store_email's PRE-LOCK check now — erin is
    #    absent, because nothing has written it yet — and then parks at the
    #    barrier, before contending for the mutex.
    (cd "$T/local" && AITASKS_LOCK_DIR="$lockbase" EMAILS_LOCK_TIMEOUT=30 \
        AIT_TEST_ACQ_SIGNAL="$sig" AIT_TEST_ACQ_GO="$go" \
        ./.aitask-scripts/aitask_pick_own.sh 1 --email "erin@test.com" \
        > "$T/.claim_out" 2>&1) &
    local claim_pid=$!

    if ! wait_for_file "$sig" 30; then
        assert_record_fail
        echo "FAIL: $label: the claim never reached the mutex barrier"
        kill "$claim_pid" 2>/dev/null; wait "$claim_pid" 2>/dev/null
        rm -rf "$T"; return 1
    fi

    # The barrier proves the ordering rather than assuming it: the pre-lock
    # check has run, and it ran against this state.
    assert_not_contains "$label: precondition — erin was ABSENT at the pre-lock check" \
        "erin@test.com" "$(cat "$T/local/$EMAILS_PATH")"

    # 2. The other writer appends erin under the mutex and exits WITHOUT
    #    committing. Synchronous: nothing is contending yet.
    AITASKS_LOCK_DIR="$lockbase" bash "$holder" \
        "$lockbase/emails" "$T/local/$EMAILS_PATH" "erin@test.com" >/dev/null 2>&1

    assert_contains "$label: precondition — the holder's address is on disk" \
        "erin@test.com" "$(cat "$T/local/$EMAILS_PATH")"
    assert_contains "$label: precondition — and uncommitted" \
        " M $EMAILS_PATH" "$(git -C "$T/local" status --porcelain "$EMAILS_PATH")"

    # 3. Release the claim. Its UNDER-LOCK re-check is the only thing left that
    #    can notice the address, and it is the branch under test.
    : > "$go"
    wait "$claim_pid" 2>/dev/null

    LAST_RECHECK_OUT="$(cat "$T/.claim_out" 2>/dev/null)"
    LAST_RECHECK_DIR="$T"
}

run_recheck_scenario fixed "Test 4d"
T4D="$LAST_RECHECK_DIR"
assert_contains "Test 4d: the claim succeeded" "OWNED:1" "$LAST_RECHECK_OUT"
assert_contains "Test 4d: the holder's address is on disk" \
    "erin@test.com" "$(cat "$T4D/local/$EMAILS_PATH")"
assert_eq "Test 4d: emails.txt is clean — the re-check recovered it" \
    "" "$(git -C "$T4D/local" status --porcelain "$EMAILS_PATH")"
assert_contains "Test 4d: the address is committed at HEAD" \
    "erin@test.com" "$(git -C "$T4D/local" show "HEAD:$EMAILS_PATH")"
email4d=$(git -C "$T4D/local" log --format=%H --grep='^ait: Record contributor email' | head -1)
assert_non_empty "Test 4d: a contributor-email commit was made" "$email4d"
files4d=$(git -C "$T4D/local" show --name-only --pretty=format: "$email4d" | grep -v '^$')
assert_eq "Test 4d: that commit touches ONLY emails.txt" "$EMAILS_PATH" "$files4d"
assert_eq "Test 4d: HEAD is still the claim commit" \
    "ait: Start work on t1: set status to Implementing" \
    "$(git -C "$T4D/local" log -1 --pretty=%s)"
rm -rf "$T4D"

# --- Test 4e: NEGATIVE CONTROLS ---------------------------------------------
# Each asserts its defect POSITIVELY, so a control whose injection silently
# failed cannot pass.
echo "--- Test 4e: NEGATIVE CONTROLS — pre-fix ordering and pre-fix re-check ---"

# 4e-1: store_email BEFORE the lock gate (pre-fix ordering) plus the pre-fix
# body whose fast path never consults HEAD. Both halves are needed: with the
# fixed fast path the retry would recover the address and the control would not
# reproduce.
T4E1="$(setup_paired_repos)"
install_prefix_store_email "$T4E1"
install_prefix_store_email_ordering "$T4E1"

(cd "$T4E1/local" && ./.aitask-scripts/aitask_lock.sh --lock 1 --email "bob@test.com" >/dev/null 2>&1)
refused4e=$(cd "$T4E1/local" && ./.aitask-scripts/aitask_pick_own.sh 1 --email "mallory@test.com" 2>&1)
assert_contains "Test 4e-1: the claim was refused" "LOCK_FAILED" "$refused4e"
assert_contains "Test 4e-1: pre-fix DOES leave emails.txt dirty after a refusal" \
    " M $EMAILS_PATH" "$(git -C "$T4E1/local" status --porcelain "$EMAILS_PATH")"

(cd "$T4E1/local" && ./.aitask-scripts/aitask_lock.sh --unlock 1 >/dev/null 2>&1)
out4e=$(cd "$T4E1/local" && ./.aitask-scripts/aitask_pick_own.sh 1 --email "mallory@test.com" 2>&1)
assert_contains "Test 4e-1: control ran to completion (not an early abort)" "OWNED:1" "$out4e"
assert_contains "Test 4e-1: pre-fix leaves it STILL dirty after the same-address retry" \
    " M $EMAILS_PATH" "$(git -C "$T4E1/local" status --porcelain "$EMAILS_PATH")"
assert_eq "Test 4e-1: pre-fix makes NO contributor-email commit" \
    "" "$(git -C "$T4E1/local" log --format=%H --grep='^ait: Record contributor email')"
rm -rf "$T4E1"

# 4e-2: the pre-lock consult present, the under-lock `else` absent — the exact
# control for Test 4d. Without this, 4d could pass on the pre-lock fix alone.
run_recheck_scenario prefix "Test 4e-2"
T4E2="$LAST_RECHECK_DIR"
assert_contains "Test 4e-2: control ran to completion" "OWNED:1" "$LAST_RECHECK_OUT"
assert_contains "Test 4e-2: pre-fix DOES leave the holder's address dirty" \
    " M $EMAILS_PATH" "$(git -C "$T4E2/local" status --porcelain "$EMAILS_PATH")"
assert_eq "Test 4e-2: pre-fix makes NO contributor-email commit" \
    "" "$(git -C "$T4E2/local" log --format=%H --grep='^ait: Record contributor email')"
rm -rf "$T4E2"

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

# --- Tests 10-13: store_email must not mask a failed write (t1614) -----------
#
# errexit is suppressed inside the `{ … } || rc=$?` group, so as three separate
# statements a failed `printf >>` followed by a SUCCEEDING `sort -u -o` leaves
# the group's status at 0: store_email reported success for an address it never
# wrote, AND set EMAIL_STORED, which is what tells commit_and_push the
# contributor list is this claim's to commit. The `&&` chain is what these pin.
#
# The chain's ORDER is pinned too, and separately. EMAIL_STORED sits between the
# append and the sort, because the append is the write the flag answers for:
# behind the sort as well, a normalization failure would leave the address
# appended, uncommitted and dirty forever — the next call's membership fast-path
# finds it already present and returns before the flag can be set again.
# Test 12 is the only test that can see that; 10 and 11 fail the append, not the
# sort.

# --- Test 10: a failed APPEND is reported, on a clean list -------------------
echo "--- Test 10: a failed append surfaces (not swallowed by the sort) ---"

T10="$(setup_paired_repos)"
install_failing_append "$T10"

before10=$(cat "$T10/local/$EMAILS_PATH")
out10=$(cd "$T10/local" && ./.aitask-scripts/aitask_pick_own.sh 1 --email "alice@test.com" 2>&1)

# The discriminating assertion: unchained, the sort succeeds, the group returns
# 0, and this warning is never emitted.
assert_contains "Test 10: the failed append is reported" \
    "store_email: failed to record" "$out10"
assert_eq "Test 10: emails.txt is unchanged — nothing was appended" \
    "$before10" "$(cat "$T10/local/$EMAILS_PATH")"
assert_not_contains "Test 10: the address is NOT recorded" \
    "alice@test.com" "$(cat "$T10/local/$EMAILS_PATH")"
email10=$(git -C "$T10/local" log --format=%H --grep='^ait: Record contributor email')
assert_eq "Test 10: no contributor-email commit was made" "" "$email10"
# Best-effort contract: a failed contributor-list write must not fail the claim.
assert_contains "Test 10: the claim still succeeds" "OWNED:1" "$out10"
assert_contains "Test 10: the claim commit still landed" \
    "aitasks/t1_test_task.md" "$(head_files "$T10")"

rm -rf "$T10"

# --- Test 11: a failed APPEND leaves EMAIL_STORED false, on a DIRTY list -----
# Test 10 cannot pin the flag: on a clean list _commit_scoped's empty-status
# guard suppresses the commit anyway, so "no email commit" holds there even with
# the flag wrongly true. A concurrent session's uncommitted append (the Test 7
# shape) is the state where the lie becomes observable.
echo "--- Test 11: a failed append does not mark the dirty list as ours ---"

T11="$(setup_paired_repos)"
install_failing_append "$T11"
(cd "$T11/local" && printf 'bob@test.com\n' >> "$EMAILS_PATH")

before11=$(cat "$T11/local/$EMAILS_PATH")
out11=$(cd "$T11/local" && ./.aitask-scripts/aitask_pick_own.sh 1 --email "alice@test.com" 2>&1)

assert_contains "Test 11: the claim still succeeds" "OWNED:1" "$out11"
# Byte-identical INCLUDING order: still append-order (seed, bob), not re-sorted.
# That is what proves `sort -u` was skipped rather than merely idempotent.
assert_eq "Test 11: emails.txt is byte-unchanged, order included" \
    "$before11" "$(cat "$T11/local/$EMAILS_PATH")"
email11=$(git -C "$T11/local" log --format=%H --grep='^ait: Record contributor email')
assert_eq "Test 11: EMAIL_STORED stayed false — no contributor-email commit" \
    "" "$email11"

rm -rf "$T11"

# --- Test 12: a failed SORT still records and commits the address ------------
# The partial-success path: the append landed, so the address IS recorded and
# the claim owes that file a commit. With EMAIL_STORED behind the sort instead,
# the flag stays false, nothing is committed, and the address is stranded dirty
# forever — the second claim below is what proves it is not.
echo "--- Test 12: a failed sort still persists the appended address ---"

T12="$(setup_paired_repos)"
SHIM12="$(install_failing_sort "$T12")"

out12=$(cd "$T12/local" && PATH="$SHIM12:$PATH" \
    ./.aitask-scripts/aitask_pick_own.sh 1 --email "alice@test.com" 2>&1)

assert_contains "Test 12: the claim still succeeds" "OWNED:1" "$out12"
# The injection took effect, and says what it observed — the normalization
# failed — without claiming the file is now unsorted (a failed `sort -u` does
# not establish that; an appended address may already be in lexical order).
assert_contains "Test 12: the failed normalization is reported" \
    "normalizing the contributor list failed" "$out12"
assert_not_contains "Test 12: ...and NOT as a failure to record — it was recorded" \
    "failed to record" "$out12"
assert_contains "Test 12: the address IS on disk" \
    "alice@test.com" "$(cat "$T12/local/$EMAILS_PATH")"

email12=$(git -C "$T12/local" log --format=%H --grep='^ait: Record contributor email' | head -1)
assert_non_empty "Test 12: a contributor-email commit was made" "$email12"
assert_contains "Test 12: that commit carries the address" \
    "alice@test.com" "$(git -C "$T12/local" show "$email12:$EMAILS_PATH")"
assert_eq "Test 12: emails.txt is clean afterwards — nothing stranded" \
    "" "$(git -C "$T12/local" status --porcelain "$EMAILS_PATH")"

# The stranding scenario itself: a LATER claim by the same address cannot rescue
# it, because store_email's membership fast-path returns before the flag is set.
# So the first claim had to persist it, and the tree must stay clean.
rm -f "$SHIM12/sort"
out12b=$(cd "$T12/local" && ./.aitask-scripts/aitask_pick_own.sh 2 --email "alice@test.com" 2>&1)
assert_contains "Test 12b: the second claim succeeds" "OWNED:2" "$out12b"
assert_eq "Test 12b: emails.txt is still clean — never stranded dirty" \
    "" "$(git -C "$T12/local" status --porcelain "$EMAILS_PATH")"
assert_contains "Test 12b: the address is committed at HEAD" \
    "alice@test.com" "$(git -C "$T12/local" show "HEAD:$EMAILS_PATH")"

rm -rf "$T12"

# --- Test 13: NEGATIVE CONTROL — the pre-fix store_email masks all of it -----
# Asserts the defect POSITIVELY in all three states, so a control whose
# injection silently failed cannot pass.
echo "--- Test 13: NEGATIVE CONTROL — pre-fix store_email masks the failure ---"

# 13a: failed append, clean list — the warning is simply never emitted.
T13A="$(setup_paired_repos)"
install_prefix_store_email "$T13A"
install_failing_append "$T13A"
out13a=$(cd "$T13A/local" && ./.aitask-scripts/aitask_pick_own.sh 1 --email "alice@test.com" 2>&1)
assert_contains "Test 13a: control ran to completion (not an early abort)" \
    "OWNED:1" "$out13a"
assert_not_contains "Test 13a: pre-fix does NOT report the failed append" \
    "store_email: failed to record" "$out13a"
rm -rf "$T13A"

# 13b: failed append, dirty list — the false EMAIL_STORED becomes visible as a
# contributor-email commit attributed to a write that never happened.
T13B="$(setup_paired_repos)"
install_prefix_store_email "$T13B"
install_failing_append "$T13B"
(cd "$T13B/local" && printf 'bob@test.com\n' >> "$EMAILS_PATH")
out13b=$(cd "$T13B/local" && ./.aitask-scripts/aitask_pick_own.sh 1 --email "alice@test.com" 2>&1)
assert_contains "Test 13b: control ran to completion" "OWNED:1" "$out13b"
# The sort runs even though the append failed, so the file IS rewritten.
assert_eq "Test 13b: pre-fix DOES rewrite the file (re-sorted)" \
    "bob@test.com
seed@test.com" "$(cat "$T13B/local/$EMAILS_PATH")"
email13b=$(git -C "$T13B/local" log --format=%H --grep='^ait: Record contributor email' | head -1)
assert_non_empty "Test 13b: pre-fix DOES make a contributor-email commit" "$email13b"
assert_not_contains "Test 13b: ...for a write that failed — the address is absent" \
    "alice@test.com" "$(git -C "$T13B/local" show "$email13b:$EMAILS_PATH")"
rm -rf "$T13B"

# 13c: failed sort — pre-fix was silent here too (rc stayed 0), so NEITHER
# wording appears. This is what makes Test 12's warning assertion discriminating.
T13C="$(setup_paired_repos)"
install_prefix_store_email "$T13C"
SHIM13C="$(install_failing_sort "$T13C")"
out13c=$(cd "$T13C/local" && PATH="$SHIM13C:$PATH" \
    ./.aitask-scripts/aitask_pick_own.sh 1 --email "alice@test.com" 2>&1)
assert_contains "Test 13c: control ran to completion" "OWNED:1" "$out13c"
assert_not_contains "Test 13c: pre-fix reports no failure to record" \
    "store_email: failed to record" "$out13c"
assert_not_contains "Test 13c: pre-fix reports no failed normalization either" \
    "normalizing the contributor list failed" "$out13c"
rm -rf "$T13C"

# --- Test 14: syntax ---------------------------------------------------------
echo "--- Test 14: syntax check ---"
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
