#!/usr/bin/env bash
# test_create_email_lock.sh - aitask_create.sh's add_email_to_file() must hold
# the SAME contributor-list mutex store_email() holds (t1608).
# Run: bash tests/test_create_email_lock.sh
#
# aitasks/metadata/emails.txt has exactly two writers. t1599_1 put
# aitask_pick_own.sh's store_email() behind `ait_lock_dir emails`; this file's
# subject is the other one. Before the fix, add_email_to_file() did an unlocked
# `echo >> ; sort -u -o`, and `sort -o` renames a SNAPSHOT over the target — so
# whichever writer finished second erased the address the other had appended. A
# mutex excludes only writers that honour it, so the t1599_1 serialization bought
# nothing against a concurrent `ait create`.
#
# --- What each test pins ----------------------------------------------------
#
#   1  The two ADAPTERS exclude each other on one lock dir, both directions.
#      registry_lock.sh (store_email's adapter) delegates to stale_lock.sh
#      (add_email_to_file's) on the caller's dir, so they contend on one mkdir
#      mutex. This is the interop the fix depends on — asserted, not assumed.
#   2  `ait create` honours the mutex: a busy list skips the write, not the
#      creation. Both sides of the boundary (Test 8 shape in
#      tests/test_pick_own_scoped_commit.sh).
#   3  No address is lost when the two writers contend.
#   4  NEGATIVE CONTROL for Test 3: the pre-fix body DOES lose one.
#   5  The failure path releases the mutex — a failed mutation must not strand
#      the lock for every later caller.
#   6  A failed APPEND is reported, not swallowed by the sort that follows it.
#   7  Syntax.
#
# --- Synchronization --------------------------------------------------------
# stale_lock_acquire emits NOTHING while it waits (lib/stale_lock.sh), so
# emails.txt content is the only real observable. Every wait below is therefore a
# bounded poll on a CONDITION whose timeout is a hard FAIL, never a sleep chosen
# to be "long enough" — a scenario that did not actually reproduce cannot report
# success by running slow.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

EMAILS_PATH="aitasks/metadata/emails.txt"

# --- Bounded condition waits -----------------------------------------------
# Each returns 1 on timeout so the caller can FAIL with a specific message.

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

wait_for_glob() {      # <glob> <timeout_s>
    local pattern="$1" ticks=$(( ${2} * 10 )) i=0
    while (( i < ticks )); do
        if compgen -G "$pattern" >/dev/null; then return 0; fi
        sleep 0.1
        i=$((i + 1))
    done
    return 1
}

stayed_absent_for() {  # <file> <needle> <seconds> — 1 if it showed up
    local file="$1" needle="$2" ticks=$(( ${3} * 10 )) i=0
    while (( i < ticks )); do
        grep -qF -- "$needle" "$file" 2>/dev/null && return 1
        sleep 0.1
        i=$((i + 1))
    done
    return 0
}

# --- Fixture ----------------------------------------------------------------
# Mirrors tests/test_create_silent_stdout.sh: bare remote + clone, the real
# aitask_create.sh, and a seeded contributor list. setup_fake_aitask_repo already
# copies BOTH stale_lock.sh and registry_lock.sh, which Test 1 needs.
#
# Sets LOCKBASE and HELPER_DIR, and leaves the shell inside the project
# (teardown pops).
setup_project() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    CLEANUP_DIRS+=("$tmpdir")

    local remote_dir="$tmpdir/remote.git"
    git init --bare --quiet "$remote_dir"

    local local_dir="$tmpdir/local"
    git clone --quiet "$remote_dir" "$local_dir"

    pushd "$local_dir" > /dev/null
    git config user.email "test@test.com"
    git config user.name "Test"

    mkdir -p aitasks/archived aitasks/metadata aitasks/new aiplans
    setup_fake_aitask_repo "$PWD"

    cp "$PROJECT_DIR/.aitask-scripts/aitask_create.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_ls.sh" .aitask-scripts/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true
    chmod +x .aitask-scripts/*.sh 2>/dev/null || true

    printf 'bug\nchore\ndocumentation\nenhancement\nfeature\nperformance\nrefactor\nstyle\ntest\n' \
        > aitasks/metadata/task_types.txt
    echo "seed@test.com" > "$EMAILS_PATH"
    echo "aitasks/new/" > .gitignore

    git add -A
    git commit -m "Initial setup" --quiet
    git push --quiet 2>/dev/null

    ./.aitask-scripts/aitask_claim_id.sh --init >/dev/null 2>&1

    LOCKBASE="$local_dir/locks"
    mkdir -p "$LOCKBASE"
    HELPER_DIR="$local_dir/testhelpers"
    mkdir -p "$HELPER_DIR"
    write_helpers
}

teardown() {
    popd > /dev/null 2>&1 || true
}

# lockprobe.sh <mode> <lock_dir> — drives the two mutex adapters against one dir
# from a THROWAWAY process. Deliberately not sourced into the test shell:
# registry_lock_acquire installs an EXIT trap, and registry_lock_release clears
# it, which would silently disarm anything this suite relied on.
#
# stale_lock_acquire is never called inside a command substitution (its token
# would be stranded in the subshell — see lib/stale_lock.sh's limitations).
write_helpers() {
    cat > "$HELPER_DIR/lockprobe.sh" <<EOF
#!/usr/bin/env bash
set -u
LIB="$PROJECT_DIR/.aitask-scripts/lib"
EOF
    cat >> "$HELPER_DIR/lockprobe.sh" <<'PROBE'
# shellcheck source=/dev/null
source "$LIB/terminal_compat.sh"
# registry_lock.sh sources stale_lock.sh from its own directory.
# shellcheck source=/dev/null
source "$LIB/registry_lock.sh"

mode="$1"
dir="$2"

case "$mode" in
    reg-then-stale)
        if registry_lock_acquire "$dir" 2 probe; then echo "REG_ACQUIRED"; else echo "REG_BUSY"; fi
        if stale_lock_acquire "$dir" 2 0.05 probe; then echo "STALE_ACQUIRED"; else echo "STALE_BUSY"; fi
        registry_lock_release "$dir"
        if stale_lock_acquire "$dir" 2 0.05 probe; then
            echo "STALE_ACQUIRED_AFTER"
            stale_lock_release "$dir" "$STALE_LOCK_TOKEN" >/dev/null 2>&1 || true
        else
            echo "STALE_BUSY_AFTER"
        fi
        ;;
    stale-then-reg)
        if stale_lock_acquire "$dir" 2 0.05 probe; then echo "STALE_ACQUIRED"; else echo "STALE_BUSY"; fi
        tok="$STALE_LOCK_TOKEN"
        if registry_lock_acquire "$dir" 2 probe; then echo "REG_ACQUIRED"; else echo "REG_BUSY"; fi
        stale_lock_release "$dir" "$tok" >/dev/null 2>&1 || true
        if registry_lock_acquire "$dir" 2 probe; then
            echo "REG_ACQUIRED_AFTER"
            registry_lock_release "$dir"
        else
            echo "REG_BUSY_AFTER"
        fi
        ;;
    stale-acquire)
        if stale_lock_acquire "$dir" 2 0.05 probe; then
            echo "ACQUIRED"
            stale_lock_release "$dir" "$STALE_LOCK_TOKEN" >/dev/null 2>&1 || true
        else
            echo "BUSY"
        fi
        ;;
esac
PROBE
    chmod +x "$HELPER_DIR/lockprobe.sh"

    # holder.sh <lock_dir> <emails_file> <ready_file> <go_file> <address>
    #
    # Plays the OTHER writer, using registry_lock.sh — the adapter store_email
    # actually takes — and reproducing its read-modify-write shape: capture a
    # snapshot, and later rename a sorted copy of that snapshot over the target.
    # That rename is the mechanism that erases a concurrent append.
    cat > "$HELPER_DIR/holder.sh" <<EOF
#!/usr/bin/env bash
set -u
LIB="$PROJECT_DIR/.aitask-scripts/lib"
EOF
    cat >> "$HELPER_DIR/holder.sh" <<'HOLDER'
# shellcheck source=/dev/null
source "$LIB/terminal_compat.sh"
# shellcheck source=/dev/null
source "$LIB/registry_lock.sh"

lockdir="$1"; emails="$2"; ready="$3"; go="$4"; addr="$5"

if ! registry_lock_acquire "$lockdir" 30 holder; then
    echo "HOLDER_BUSY"
    exit 1
fi

snapshot="$(cat "$emails" 2>/dev/null || true)"
: > "$ready"

# Wait for the test to finish its observation before the destructive write-back.
while [[ ! -f "$go" ]]; do sleep 0.05; done

printf '%s\n%s\n' "$snapshot" "$addr" | grep -v '^$' | sort -u > "$emails.holder"
mv "$emails.holder" "$emails"

registry_lock_release "$lockdir"
echo "HOLDER_DONE"
HOLDER
    chmod +x "$HELPER_DIR/holder.sh"
}

# Rebuild the fixture's COPY of aitask_create.sh with the PRE-FIX
# add_email_to_file. The script's last line is a single `main "$@"`, so appending
# the legacy definition ahead of it makes bash use it — the real function is not
# edited and nothing outside this throwaway repo is touched. Same technique as
# install_prefix_commit_and_push in tests/test_pick_own_scoped_commit.sh, so the
# control stays executable on every run instead of expiring once the fix landed.
install_prefix_add_email_to_file() {
    local script=".aitask-scripts/aitask_create.sh"
    local tmp="$script.new"
    grep -v '^main "\$@"$' "$script" > "$tmp"    # portable; no sed -i
    cat >> "$tmp" <<'LEGACY'
add_email_to_file() {
    local email="$1"
    ensure_emails_file
    if [[ -n "$email" ]] && ! grep -qFx "$email" "$EMAILS_FILE" 2>/dev/null; then
        echo "$email" >> "$EMAILS_FILE"
        sort -u "$EMAILS_FILE" -o "$EMAILS_FILE"
    fi
}
LEGACY
    printf 'main "$@"\n' >> "$tmp"
    mv "$tmp" "$script"
    chmod +x "$script"
}

# Make the emails APPEND — and nothing else — fail, by shadowing the printf
# builtin with a function for the duration of the fixture's script copy. A PATH
# shim cannot reach a builtin, and permissions cannot discriminate: a mode that
# blocks the append blocks `sort -o` on the same file too, so both would fail and
# the branch under test would never be isolated.
#
# `${FUNCNAME[1]}` is what makes it exact — only the call inside
# add_email_to_file fails, every other printf in the script is untouched.
install_failing_append() {
    local script=".aitask-scripts/aitask_create.sh"
    local tmp="$script.new"
    grep -v '^main "\$@"$' "$script" > "$tmp"
    cat >> "$tmp" <<'INJECT'
printf() {
    if [[ "${FUNCNAME[1]:-}" == "add_email_to_file" ]]; then
        return 1
    fi
    builtin printf "$@"
}
INJECT
    printf 'main "$@"\n' >> "$tmp"
    mv "$tmp" "$script"
    chmod +x "$script"
}

set +e

echo "=== add_email_to_file holds the contributor-list mutex (t1608) ==="
echo ""

# --- Test 1: the two adapters exclude each other on one lock dir -------------
echo "--- Test 1: registry_lock and stale_lock contend on one dir, both directions ---"

setup_project

probe_dir="$LOCKBASE/interop"
out1a=$(AITASKS_LOCK_DIR="$LOCKBASE" bash "$HELPER_DIR/lockprobe.sh" reg-then-stale "$probe_dir" 2>/dev/null)

assert_contains "Test 1a: registry_lock took the dir" "REG_ACQUIRED" "$out1a"
assert_contains "Test 1a: stale_lock is EXCLUDED while registry_lock holds it" \
    "STALE_BUSY" "$out1a"
assert_contains "Test 1a: stale_lock succeeds once registry_lock releases" \
    "STALE_ACQUIRED_AFTER" "$out1a"

rm -rf "$probe_dir" "$probe_dir.gc"
out1b=$(AITASKS_LOCK_DIR="$LOCKBASE" bash "$HELPER_DIR/lockprobe.sh" stale-then-reg "$probe_dir" 2>/dev/null)

assert_contains "Test 1b: stale_lock took the dir" "STALE_ACQUIRED" "$out1b"
assert_contains "Test 1b: registry_lock is EXCLUDED while stale_lock holds it" \
    "REG_BUSY" "$out1b"
assert_contains "Test 1b: registry_lock succeeds once stale_lock releases" \
    "REG_ACQUIRED_AFTER" "$out1b"

teardown

# --- Test 2: a busy mutex skips the write, not the creation ------------------
echo "--- Test 2: ait create honours a held contributor-list mutex ---"

setup_project

mkdir -p "$LOCKBASE/emails"
sleep 120 &
HOLDER2=$!
echo "$HOLDER2" > "$LOCKBASE/emails/pid"

before2=$(cat "$EMAILS_PATH")
err2_file="$(mktemp)"
stdout2=$(AITASKS_LOCK_DIR="$LOCKBASE" EMAILS_LOCK_ATTEMPTS=2 EMAILS_LOCK_SLEEP=0.05 \
    ./.aitask-scripts/aitask_create.sh --batch --commit --silent \
    --name "busy_probe" --desc "Busy mutex probe" --assigned-to "bob@test.com" 2>"$err2_file")
rc2=$?
err2=$(cat "$err2_file"); rm -f "$err2_file"

assert_eq "Test 2: creation still succeeds (exit 0)" "0" "$rc2"
assert_file_exists "Test 2: the task file was created" "$stdout2"
assert_contains "Test 2: the skip is reported" "contributor list busy" "$err2"

after2=$(cat "$EMAILS_PATH")
assert_eq "Test 2: emails.txt unchanged — never written unlocked" "$before2" "$after2"

# Other side of the boundary: release the mutex and the address now lands.
kill "$HOLDER2" 2>/dev/null
wait "$HOLDER2" 2>/dev/null
rm -rf "$LOCKBASE/emails" "$LOCKBASE/emails.gc"

AITASKS_LOCK_DIR="$LOCKBASE" EMAILS_LOCK_ATTEMPTS=2 EMAILS_LOCK_SLEEP=0.05 \
    ./.aitask-scripts/aitask_create.sh --batch --commit --silent \
    --name "free_probe" --desc "Free mutex probe" --assigned-to "carol@test.com" \
    >/dev/null 2>&1
rc2b=$?

assert_eq "Test 2b: creation succeeds with the mutex free" "0" "$rc2b"
assert_contains "Test 2b: the address lands once the mutex is free" \
    "carol@test.com" "$(cat "$EMAILS_PATH")"

teardown

# --- Tests 3 and 4: the lost update, and its negative control ----------------
# One scenario driver, run against the fixed script and against the injected
# pre-fix body. Both branches synchronize on OBSERVED FILE STATE.
#
#   holder (registry_lock)          create (stale_lock, under test)
#   -------------------------       --------------------------------
#   acquire; snapshot; ready
#                                   start; write task file
#     [branch-specific observation]  ... appends bob, or blocks on the mutex
#   write back snapshot+alice
#   release
#                                   (fixed only) acquires, re-checks, appends bob
#
# The pre-fix body appends while the mutex is held, so the write-back erases it.
run_lost_update_scenario() {
    local mode="$1"          # fixed | prefix
    local label="$2"

    setup_project
    [[ "$mode" == "prefix" ]] && install_prefix_add_email_to_file

    local lockdir="$LOCKBASE/emails"
    local ready="$PWD/.holder_ready" go="$PWD/.holder_go"
    rm -f "$ready" "$go"

    AITASKS_LOCK_DIR="$LOCKBASE" bash "$HELPER_DIR/holder.sh" \
        "$lockdir" "$PWD/$EMAILS_PATH" "$ready" "$go" "alice@test.com" \
        > "$PWD/.holder_out" 2>/dev/null &
    local holder_pid=$!

    if ! wait_for_file "$ready" 20; then
        assert_record_fail
        echo "FAIL: $label: the holder never acquired the mutex (no ready signal)"
        kill "$holder_pid" 2>/dev/null; wait "$holder_pid" 2>/dev/null
        teardown
        return 1
    fi

    # Budget generously outlasts the holder section: 600 x 0.05s = ~30s.
    AITASKS_LOCK_DIR="$LOCKBASE" EMAILS_LOCK_ATTEMPTS=600 EMAILS_LOCK_SLEEP=0.05 \
        ./.aitask-scripts/aitask_create.sh --batch --commit --silent \
        --name "lost_update" --desc "Concurrent writer" --assigned-to "bob@test.com" \
        > "$PWD/.create_out" 2>"$PWD/.create_err" &
    local create_pid=$!

    local create_reaped=""
    if [[ "$mode" == "prefix" ]]; then
        # NEGATIVE CONTROL: assert the defect POSITIVELY — the unlocked writer
        # must be OBSERVED writing while the mutex is held. Waiting for create to
        # finish COMPLETELY (it never blocks in this mode; if the injection
        # failed it blocks, warns and still exits) removes every timing window:
        # its whole `echo >> ; sort -u -o` is done before the holder writes back,
        # so a surviving address could only mean the write was serialized.
        wait "$create_pid" 2>/dev/null
        create_reaped=1
        if grep -qF -- "bob@test.com" "$EMAILS_PATH" 2>/dev/null; then
            assert_record_pass
        else
            assert_record_fail
            echo "FAIL: $label: pre-fix body did NOT write while the mutex was held — control did not reproduce"
        fi
    else
        # The task file is written immediately before add_email_to_file, so its
        # appearance proves create actually reached the email step.
        if wait_for_glob "aitasks/t*_lost_update.md" 25; then
            assert_record_pass
        else
            assert_record_fail
            echo "FAIL: $label: create never got as far as writing the task file"
        fi
        # Mirror of the control's observation: the write must stay excluded.
        if stayed_absent_for "$EMAILS_PATH" "bob@test.com" 3; then
            assert_record_pass
        else
            assert_record_fail
            echo "FAIL: $label: the address was written while the mutex was held"
        fi
    fi

    : > "$go"
    wait "$holder_pid" 2>/dev/null
    [[ -n "$create_reaped" ]] || wait "$create_pid" 2>/dev/null

    LAST_SCENARIO_EMAILS="$(cat "$EMAILS_PATH")"
    LAST_SCENARIO_HOLDER_OUT="$(cat "$PWD/.holder_out" 2>/dev/null)"
    teardown
}

echo "--- Test 3: neither writer's address is lost (fixed) ---"
run_lost_update_scenario fixed "Test 3"
assert_contains "Test 3: the holder's write-back ran" "HOLDER_DONE" "$LAST_SCENARIO_HOLDER_OUT"
assert_contains "Test 3: the holder's address survives" \
    "alice@test.com" "$LAST_SCENARIO_EMAILS"
assert_contains "Test 3: ait create's address survives" \
    "bob@test.com" "$LAST_SCENARIO_EMAILS"

echo "--- Test 4: NEGATIVE CONTROL — the pre-fix body loses the update ---"
run_lost_update_scenario prefix "Test 4"
assert_contains "Test 4: the holder's write-back ran" "HOLDER_DONE" "$LAST_SCENARIO_HOLDER_OUT"
assert_contains "Test 4: pre-fix keeps the holder's address" \
    "alice@test.com" "$LAST_SCENARIO_EMAILS"
assert_not_contains "Test 4: pre-fix LOSES ait create's address" \
    "bob@test.com" "$LAST_SCENARIO_EMAILS"

# --- Test 5: a failed mutation still releases the mutex ----------------------
# The `{ … } || rc=$?` catch exists so a failed append/sort reaches
# stale_lock_release. Nothing else here exercises it, so without this test a
# change could strand the lock while every success and busy assertion stayed
# green. The failure is injected through a narrow PATH shim rather than
# permissions, so it works under any uid.
echo "--- Test 5: a failed write releases the lock, and the path still works ---"

setup_project

REAL_SORT="$(command -v sort)"
mkdir -p "$PWD/shim"
cat > "$PWD/shim/sort" <<EOF
#!/usr/bin/env bash
# Fail ONLY the emails.txt rewrite; pass everything else through to the real
# binary, resolved before the PATH prepend so this cannot recurse.
want_o=""; want_emails=""
for a in "\$@"; do
    case "\$a" in
        -o) want_o=1 ;;
        *${EMAILS_PATH##*/}) want_emails=1 ;;
    esac
done
if [[ -n "\$want_o" && -n "\$want_emails" ]]; then exit 1; fi
exec "$REAL_SORT" "\$@"
EOF
chmod +x "$PWD/shim/sort"

err5_file="$(mktemp)"
stdout5=$(PATH="$PWD/shim:$PATH" AITASKS_LOCK_DIR="$LOCKBASE" \
    ./.aitask-scripts/aitask_create.sh --batch --commit --silent \
    --name "sort_failure" --desc "Forced mutation failure" \
    --assigned-to "erin@test.com" 2>"$err5_file")
rc5=$?
err5=$(cat "$err5_file"); rm -f "$err5_file"

# (a) The injection actually took effect — proven, not assumed.
assert_contains "Test 5: the failed write is reported" \
    "add_email_to_file: failed to record" "$err5"
# (b) Best-effort contract holds on the failure path too.
assert_eq "Test 5: creation still succeeds (exit 0)" "0" "$rc5"
assert_file_exists "Test 5: the task file was created" "$stdout5"
# (c) + (d) The lock is gone AND genuinely reacquirable on the same path.
assert_dir_not_exists "Test 5: the lock dir was removed" "$LOCKBASE/emails"
probe5=$(AITASKS_LOCK_DIR="$LOCKBASE" bash "$HELPER_DIR/lockprobe.sh" \
    stale-acquire "$LOCKBASE/emails" 2>/dev/null)
assert_eq "Test 5: the lock is reacquirable after the failure" "ACQUIRED" "$probe5"

rm -f "$PWD/shim/sort"
AITASKS_LOCK_DIR="$LOCKBASE" ./.aitask-scripts/aitask_create.sh --batch --commit --silent \
    --name "after_failure" --desc "Path still works" --assigned-to "frank@test.com" \
    >/dev/null 2>&1
assert_contains "Test 5b: the path still records addresses after a failure" \
    "frank@test.com" "$(cat "$EMAILS_PATH")"

teardown

# --- Test 6: a failed APPEND is reported, not masked by the following sort ----
# errexit is suppressed inside the `{ … } || rc=$?` group, so as two separate
# statements a failed `printf >>` followed by a SUCCEEDING `sort -u -o` leaves
# the group's status at 0: the function would report success for an address it
# never wrote. Test 5 cannot see this branch — it fails sort, not the append.
# The `&&` chain in add_email_to_file is what this pins.
echo "--- Test 6: a failed append surfaces (not swallowed by the sort) ---"

setup_project

install_failing_append

before6=$(cat "$EMAILS_PATH")
err6_file="$(mktemp)"
stdout6=$(AITASKS_LOCK_DIR="$LOCKBASE" \
    ./.aitask-scripts/aitask_create.sh --batch --commit --silent \
    --name "append_failure" --desc "Forced append failure" \
    --assigned-to "gina@test.com" 2>"$err6_file")
rc6=$?
err6=$(cat "$err6_file"); rm -f "$err6_file"

# The discriminating assertion: without the `&&` chain the sort succeeds, the
# group returns 0, and this warning is never emitted.
assert_contains "Test 6: the failed append is reported" \
    "add_email_to_file: failed to record" "$err6"
assert_eq "Test 6: emails.txt is unchanged — nothing was appended" \
    "$before6" "$(cat "$EMAILS_PATH")"
assert_not_contains "Test 6: the address is NOT recorded" \
    "gina@test.com" "$(cat "$EMAILS_PATH")"
# Best-effort contract and lock hygiene hold on this failure path too.
assert_eq "Test 6: creation still succeeds (exit 0)" "0" "$rc6"
assert_file_exists "Test 6: the task file was created" "$stdout6"
assert_dir_not_exists "Test 6: the lock dir was removed" "$LOCKBASE/emails"
probe6=$(AITASKS_LOCK_DIR="$LOCKBASE" bash "$HELPER_DIR/lockprobe.sh" \
    stale-acquire "$LOCKBASE/emails" 2>/dev/null)
assert_eq "Test 6: the lock is reacquirable after a failed append" "ACQUIRED" "$probe6"

teardown

# --- Test 7: syntax ----------------------------------------------------------
echo "--- Test 7: syntax check ---"
if bash -n "$PROJECT_DIR/.aitask-scripts/aitask_create.sh" 2>/dev/null; then
    assert_record_pass
else
    assert_record_fail
    echo "FAIL: aitask_create.sh syntax check"
fi

# --- Cleanup ---
for d in "${CLEANUP_DIRS[@]}"; do
    rm -rf "$d"
done

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
