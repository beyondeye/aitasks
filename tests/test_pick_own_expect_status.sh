#!/usr/bin/env bash
# test_pick_own_expect_status.sh - aitask_pick_own.sh --expect-status (t1663_4).
# Run: bash tests/test_pick_own_expect_status.sh
#
# The task-workflow premise prompt (Step 3 Check 7) decides about a task BEFORE
# it is claimed, from a status read before any lock existed. A claim made on
# that decision must therefore re-validate the status UNDER the lock, from task
# data re-synced UNDER the lock, before it writes anything: otherwise a status
# changed meanwhile by a session that has since released the lock (Postponed,
# Done) is silently overwritten with Implementing.
#
# WINDOW CONTROL, without a production hook. The interesting change lands AFTER
# the claim's initial sync_remote (which would already import it) and BEFORE the
# under-lock refresh. The fixture's .aitask-scripts/aitask_lock.sh is a wrapper
# that execs the real script (aitask_lock.real.sh) and, on `--lock` only, first
# runs a one-shot per-case action file. A fixture-only override appended to the
# copied lib/task_utils.sh makes _task_pull_rebase fail while a marker file
# exists, so only the under-lock sync can fail. Both live in the throwaway
# fixture; nothing outside it is touched.
#
# Every refusal case asserts the four things a refused claim must not change:
# the task file bytes, the contributor list bytes, the absence of a claim
# commit, and a free lock afterwards. The no-flag control shows the gate -- not
# the fixture -- is what refuses.
#
# SRC (default: this checkout's .aitask-scripts) lets a scratch mirror run the
# suite against a mutated copy (the red proofs in the t1663_4 plan).

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# One registered temp root: factories run as `$(new_fixture)`, so a
# CLEANUP_DIRS append inside them would die with the subshell (t2055).
# shellcheck source=lib/fixture_root.sh
. "$PROJECT_DIR/tests/lib/fixture_root.sh"

SRC="${SRC:-$PROJECT_DIR/.aitask-scripts}"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

cleanup() {
    local d
    for d in "${CLEANUP_DIRS[@]+"${CLEANUP_DIRS[@]}"}"; do rm -rf "$d"; done
}
trap cleanup EXIT

check() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected '$expected', got '$actual')"
    fi
}

TASK_REL="aitasks/t1_claim_me.md"
EMAILS_REL="aitasks/metadata/emails.txt"

# --- Fixture ---------------------------------------------------------------

# new_fixture -> echoes <tmp>; <tmp>/a and <tmp>/b are clones of <tmp>/remote.git.
new_fixture() {
    local tmp
    tmp="$(fixture_mktemp_d test_expect_status)" || return 1
    git init --bare --quiet "$tmp/remote.git"
    git clone --quiet "$tmp/remote.git" "$tmp/a" 2>/dev/null
    (
        cd "$tmp/a" || exit 1
        git config user.email "a@test.com"
        git config user.name "A"
        git config commit.gpgsign false
        mkdir -p aitasks/archived aitasks/metadata aiplans
        cat > "$TASK_REL" <<'TASK'
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
        echo "seed@test.com" > "$EMAILS_REL"
        setup_fake_aitask_repo "$PWD"
        cp "$SRC/aitask_lock.sh" .aitask-scripts/aitask_lock.real.sh
        cp "$SRC/aitask_pick_own.sh" "$SRC/aitask_update.sh" .aitask-scripts/
        cp "$SRC/lib/task_utils.sh" "$SRC/lib/pid_anchor.sh" "$SRC/lib/archive_utils.sh" \
            "$SRC/lib/task_yaml.py" .aitask-scripts/lib/
        cp "$PROJECT_DIR/ait" . 2>/dev/null || true

        # The window wrapper (see the header).
        cat > .aitask-scripts/aitask_lock.sh <<'WRAP'
#!/usr/bin/env bash
if [[ "${1:-}" == "--lock" && -n "${EXPECT_TEST_ACTION:-}" && -f "$EXPECT_TEST_ACTION" ]]; then
    bash "$EXPECT_TEST_ACTION" >/dev/null 2>&1 || true
    rm -f "$EXPECT_TEST_ACTION"
fi
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/aitask_lock.real.sh" "$@"
WRAP
        # The fixture-only pull failure (see the header).
        cat >> .aitask-scripts/lib/task_utils.sh <<'OVERRIDE'

# --- test fixture override (tests/test_pick_own_expect_status.sh) ---
eval "_fixture_orig_task_pull_rebase() $(declare -f _task_pull_rebase | tail -n +2)"
_task_pull_rebase() {
    if [[ -n "${EXPECT_TEST_FAIL_MARK:-}" && -f "$EXPECT_TEST_FAIL_MARK" ]]; then
        echo "error: simulated pull failure (fixture)" >&2
        return 1
    fi
    _fixture_orig_task_pull_rebase "$@"
}
OVERRIDE
        chmod +x .aitask-scripts/*.sh ait 2>/dev/null || true
        git add -A
        git commit -q -m "Initial setup"
        git push -q 2>/dev/null
        ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1
    ) || return 1
    git clone --quiet "$tmp/remote.git" "$tmp/b" 2>/dev/null
    git -C "$tmp/b" config user.email "b@test.com"
    git -C "$tmp/b" config user.name "B"
    git -C "$tmp/b" config commit.gpgsign false
    printf '%s' "$tmp"
}

# write_b_status_script <tmp> <status> <action-file> [mark-file]
# The action clone B performs: set the status, commit, push -- holding no lock.
write_b_status_script() {
    local tmp="$1" status="$2" action="$3" mark="${4:-}"
    cat > "$action" <<EOF
set -e
cd "$tmp/b"
git pull -q
awk '{ if (!done && \$0 ~ /^status: /) { print "status: $status"; done=1 } else print }' \
    "$TASK_REL" > "$TASK_REL.new"
mv "$TASK_REL.new" "$TASK_REL"
git commit -q -am "ait: set t1 to $status (another session)"
git push -q
EOF
    if [[ -n "$mark" ]]; then
        printf 'touch "%s"\n' "$mark" >> "$action"
    fi
}

status_of() { awk '/^status:/ {sub(/^status:[ \t]*/, ""); print; exit}' "$1"; }
claim_commits() { git -C "$1" log --format=%s | grep -c '^ait: Start work on t1' || true; }
lock_free() {
    # aitask_lock.sh --check: exit 0 = locked, 1 = free.
    ( cd "$1" && ./.aitask-scripts/aitask_lock.sh --check 1 >/dev/null 2>&1 ) && echo locked || echo free
}

# run_claim <tmp> <action-or-empty> <mark-or-empty> <flags...> -> sets OUT, RC.
OUT=""
RC=0
run_claim() {
    local tmp="$1" action="$2" mark="$3"
    shift 3
    RC=0
    OUT=$(cd "$tmp/a" && EXPECT_TEST_ACTION="$action" EXPECT_TEST_FAIL_MARK="$mark" \
        ./.aitask-scripts/aitask_pick_own.sh 1 --email a@test.com "$@" 2>/dev/null) || RC=$?
}

# assert_refused <label> <tmp> <emails-before> <expected-line-prefix>
assert_refused() {
    local label="$1" tmp="$2" emails_before="$3" want="$4"
    check "$label: exit 1" "1" "$RC"
    check "$label: refusal line" "1" "$(printf '%s\n' "$OUT" | grep -c "^${want}")"
    check "$label: never OWNED" "0" "$(printf '%s\n' "$OUT" | grep -c '^OWNED:')"
    check "$label: contributor list unchanged" "$emails_before" "$(cat "$tmp/a/$EMAILS_REL")"
    check "$label: no claim commit" "0" "$(claim_commits "$tmp/a")"
    check "$label: lock released" "free" "$(lock_free "$tmp/a")"
}

# --- Cases -----------------------------------------------------------------

fixture_root_init
assert_fixture_registered "new_fixture dirs land under the registered FIXTURE_ROOT" \
    "$(new_fixture)"

echo "=== 1: status changed INSIDE the window (after the initial sync) ==="
for target in Postponed Done; do
    T=$(new_fixture)
    before_emails=$(cat "$T/a/$EMAILS_REL")
    check "1/$target: A starts out Ready (stale once B acts)" "Ready" "$(status_of "$T/a/$TASK_REL")"
    write_b_status_script "$T" "$target" "$T/action"
    run_claim "$T" "$T/action" "" --expect-status Ready
    check "1/$target: the action really ran (B pushed)" "$target" \
        "$(git -C "$T/b" show "HEAD:$TASK_REL" | status_of /dev/stdin)"
    assert_refused "1/$target" "$T" "$before_emails" "STATUS_CHANGED:${target}|Ready"
    check "1/$target: A holds B's status after the under-lock pull" "$target" \
        "$(status_of "$T/a/$TASK_REL")"
    check "1/$target: A's HEAD is B's commit (nothing of A's on top)" \
        "$(git -C "$T/b" rev-parse HEAD)" "$(git -C "$T/a" rev-parse HEAD)"
done

echo "=== 2: in-window change + FAILED under-lock sync => STATUS_UNVERIFIED ==="
T=$(new_fixture)
before_emails=$(cat "$T/a/$EMAILS_REL")
before_task=$(cat "$T/a/$TASK_REL")
before_head=$(git -C "$T/a" rev-parse HEAD)
write_b_status_script "$T" Postponed "$T/action" "$T/fail.mark"
run_claim "$T" "$T/action" "$T/fail.mark" --expect-status Ready
check "2: the marker was armed by the action" "yes" "$([[ -f "$T/fail.mark" ]] && echo yes || echo no)"
check "2: the remote really holds Postponed" "Postponed" \
    "$(git -C "$T/b" show "HEAD:$TASK_REL" | status_of /dev/stdin)"
assert_refused "2" "$T" "$before_emails" "STATUS_UNVERIFIED:"
check "2: A's task file byte-identical (stale Ready, never claimed)" "$before_task" \
    "$(cat "$T/a/$TASK_REL")"
check "2: A's HEAD unchanged" "$before_head" "$(git -C "$T/a" rev-parse HEAD)"

echo "=== 3: status changed BEFORE the claim (ordinary case: the initial sync sees it) ==="
T=$(new_fixture)
before_emails=$(cat "$T/a/$EMAILS_REL")
write_b_status_script "$T" Postponed "$T/pre"
bash "$T/pre" >/dev/null 2>&1
run_claim "$T" "" "" --expect-status Ready
assert_refused "3" "$T" "$before_emails" "STATUS_CHANGED:Postponed|Ready"

echo "=== 4: controls ==="
T=$(new_fixture)
run_claim "$T" "" "" --expect-status Ready
check "4a: unchanged Ready claims (exit 0)" "0" "$RC"
check "4a: OWNED" "1" "$(printf '%s\n' "$OUT" | grep -c '^OWNED:1$')"
check "4a: status Implementing" "Implementing" "$(status_of "$T/a/$TASK_REL")"
check "4a: one claim commit" "1" "$(claim_commits "$T/a")"

T=$(new_fixture)
write_b_status_script "$T" Postponed "$T/action"
run_claim "$T" "$T/action" ""
check "4b: WITHOUT the flag the same in-window change is overwritten (exit 0)" "0" "$RC"
check "4b: OWNED" "1" "$(printf '%s\n' "$OUT" | grep -c '^OWNED:1$')"
check "4b: B's Postponed was silently replaced" "Implementing" "$(status_of "$T/a/$TASK_REL")"

echo "=== 5: CLI ==="
T=$(new_fixture)
run_claim "$T" "" "" --expect-status Bogus
check "5: an unknown status is refused" "1" "$([[ $RC -ne 0 ]] && echo 1 || echo 0)"
check "5: ...before anything is claimed" "Ready" "$(status_of "$T/a/$TASK_REL")"
check "5: ...and the lock is untouched" "free" "$(lock_free "$T/a")"

echo "=== 6: no email resolves -> no lock could be taken -> refused ==="
T=$(new_fixture)
( cd "$T/a" && ./.aitask-scripts/aitask_lock.sh --lock 1 --email other@test.com >/dev/null 2>&1 )
check "6: the other owner really holds the lock" "1" \
    "$( (cd "$T/a" && ./.aitask-scripts/aitask_lock.sh --check 1 2>/dev/null) | grep -c 'other@test.com')"
before_emails=$(cat "$T/a/$EMAILS_REL")
RC=0
OUT=$(cd "$T/a" && ./.aitask-scripts/aitask_pick_own.sh 1 --expect-status Ready 2>/dev/null) || RC=$?
check "6: exit 1" "1" "$RC"
check "6: LOCK_REQUIRED:no_email" "1" "$(printf '%s\n' "$OUT" | grep -c '^LOCK_REQUIRED:no_email$')"
check "6: never OWNED" "0" "$(printf '%s\n' "$OUT" | grep -c '^OWNED:')"
check "6: status still Ready" "Ready" "$(status_of "$T/a/$TASK_REL")"
check "6: no claim commit" "0" "$(claim_commits "$T/a")"
check "6: contributor list unchanged" "$before_emails" "$(cat "$T/a/$EMAILS_REL")"
check "6: the other owner's lock is untouched" "1" \
    "$( (cd "$T/a" && ./.aitask-scripts/aitask_lock.sh --check 1 2>/dev/null) | grep -c 'other@test.com')"

echo "=== 6b: the only recovery from LOCK_REQUIRED (email + the SAME guard) cannot claim ==="
# ...another owner's task: the refusal, then the prescribed guarded retry.
T=$(new_fixture)
( cd "$T/a" && ./.aitask-scripts/aitask_lock.sh --lock 1 --email other@test.com >/dev/null 2>&1 )
RC=0; OUT=$(cd "$T/a" && ./.aitask-scripts/aitask_pick_own.sh 1 --expect-status Ready 2>/dev/null) || RC=$?
check "6b/holder: first refused with LOCK_REQUIRED" "1" "$(printf '%s\n' "$OUT" | grep -c '^LOCK_REQUIRED:no_email$')"
run_claim "$T" "" "" --expect-status Ready
check "6b/holder: the guarded retry refuses (exit 1)" "1" "$RC"
check "6b/holder: ...as LOCK_FAILED naming the holder" "1" "$(printf '%s\n' "$OUT" | grep -c '^LOCK_FAILED:other@test.com')"
check "6b/holder: ...status still Ready" "Ready" "$(status_of "$T/a/$TASK_REL")"
check "6b/holder: ...no claim commit" "0" "$(claim_commits "$T/a")"
check "6b/holder: ...the holder's lock is untouched" "1" \
    "$( (cd "$T/a" && ./.aitask-scripts/aitask_lock.sh --check 1 2>/dev/null) | grep -c 'other@test.com')"
# ...a task postponed between the refusal and the retry.
T=$(new_fixture)
RC=0; OUT=$(cd "$T/a" && ./.aitask-scripts/aitask_pick_own.sh 1 --expect-status Ready 2>/dev/null) || RC=$?
check "6b/postponed: first refused with LOCK_REQUIRED" "1" "$(printf '%s\n' "$OUT" | grep -c '^LOCK_REQUIRED:no_email$')"
write_b_status_script "$T" Postponed "$T/action"
run_claim "$T" "$T/action" "" --expect-status Ready
check "6b/postponed: the guarded retry refuses with STATUS_CHANGED" "1" \
    "$(printf '%s\n' "$OUT" | grep -c '^STATUS_CHANGED:Postponed|Ready$')"
check "6b/postponed: ...the task stays Postponed" "Postponed" "$(status_of "$T/a/$TASK_REL")"
check "6b/postponed: ...no claim commit" "0" "$(claim_commits "$T/a")"
check "6b/postponed: ...lock released" "free" "$(lock_free "$T/a")"

# set_status_line <tmp> <raw line> -- rewrite A's status line, commit, push.
set_status_line() {
    local tmp="$1" line="$2"
    awk -v l="$line" '{ if (!done && $0 ~ /^status:/) { print l; done=1 } else print }' \
        "$tmp/a/$TASK_REL" > "$tmp/a/$TASK_REL.new"
    mv "$tmp/a/$TASK_REL.new" "$tmp/a/$TASK_REL"
    git -C "$tmp/a" commit -q -am "test: status spelling"
    git -C "$tmp/a" push -q 2>/dev/null
}

echo "=== 7: the status is read as YAML -- spelling variants of Ready claim ==="
for spelling in 'status: "Ready"' "status: 'Ready'" 'status: Ready   # waiting' 'status: Ready   '; do
    T=$(new_fixture)
    set_status_line "$T" "$spelling"
    run_claim "$T" "" "" --expect-status Ready
    check "7 [$spelling]: claims (exit 0)" "0" "$RC"
    check "7 [$spelling]: OWNED" "1" "$(printf '%s\n' "$OUT" | grep -c '^OWNED:1$')"
done

echo "=== 8: unreadable metadata is UNVERIFIED, never a state change ==="
for case in nostatus badyaml numeric; do
    T=$(new_fixture)
    case "$case" in
        nostatus)
            grep -v '^status:' "$T/a/$TASK_REL" > "$T/a/$TASK_REL.new" && mv "$T/a/$TASK_REL.new" "$T/a/$TASK_REL"
            git -C "$T/a" commit -q -am "test: drop status"; git -C "$T/a" push -q 2>/dev/null ;;
        badyaml) set_status_line "$T" 'status: [Ready' ;;
        numeric) set_status_line "$T" 'status: 7' ;;
    esac
    before_emails=$(cat "$T/a/$EMAILS_REL")
    before_task=$(cat "$T/a/$TASK_REL")
    run_claim "$T" "" "" --expect-status Ready
    assert_refused "8/$case" "$T" "$before_emails" "STATUS_UNVERIFIED:unreadable_status"
    check "8/$case: never reported as STATUS_CHANGED" "0" "$(printf '%s\n' "$OUT" | grep -c '^STATUS_CHANGED:')"
    check "8/$case: task file byte-identical" "$before_task" "$(cat "$T/a/$TASK_REL")"
done

echo ""
echo "=== Results ==="
echo "Total:  $TOTAL"
echo "Pass:   $PASS"
echo "Fail:   $FAIL"
[[ "$FAIL" -eq 0 ]] && echo "ALL TESTS PASSED"
[[ "$FAIL" -eq 0 ]]
