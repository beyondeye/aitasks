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

# --- t1626 helpers ----------------------------------------------------------

# Rebuild the fixture's COPY with an add_email_to_file that appends but NEVER
# COMMITS, and whose membership check is a plain `return 0`. This is the pre-fix
# body for defect 2: aitask_create.sh named EMAILS_FILE in no `task_git add`, and
# since t1599_1 scoped every claim commit to its own paths nothing swept it
# either — so the address stayed dirty indefinitely.
install_prefix_add_email_to_file_nocommit() {
    local script=".aitask-scripts/aitask_create.sh"
    local tmp="$script.new"
    grep -v '^main "\$@"$' "$script" > "$tmp"
    cat >> "$tmp" <<'LEGACY'
add_email_to_file() {
    local email="$1"
    [[ -n "$email" ]] || return 0
    ensure_emails_file
    grep -qFx -- "$email" "$EMAILS_FILE" 2>/dev/null && return 0
    local lockdir token rc=0
    lockdir="$(ait_lock_dir emails)" || return 0
    if ! stale_lock_acquire "$lockdir" "$EMAILS_LOCK_ATTEMPTS" "$EMAILS_LOCK_SLEEP" \
            "contributor list" "$_STALE_LOCK_GC_WINDOW_DEFAULT"; then
        warn "contributor list busy — email not recorded$(stale_lock_describe "$lockdir")"
        return 0
    fi
    token="$STALE_LOCK_TOKEN"
    {
        if ! grep -qFx -- "$email" "$EMAILS_FILE" 2>/dev/null; then
            printf '%s\n' "$email" >> "$EMAILS_FILE" &&
                sort -u "$EMAILS_FILE" -o "$EMAILS_FILE"
        fi
    } || rc=$?
    stale_lock_release "$lockdir" "$token" \
        || warn "add_email_to_file: contributor-list lock not fully released"
    [[ $rc -eq 0 ]] || warn "add_email_to_file: failed to record ${email} (rc=$rc)"
    return 0
}
LEGACY
    printf 'main "$@"\n' >> "$tmp"
    mv "$tmp" "$script"
    chmod +x "$script"
}

# Rebuild the fixture's COPY with the PRE-LOCK HEAD consult present but the
# UNDER-LOCK one absent. This is the control for the re-check test specifically:
# without it that test could pass on the pre-lock fix alone and would prove
# nothing about the `else` branch it exists to guard.
install_prefix_add_email_to_file_norecheck() {
    local script=".aitask-scripts/aitask_create.sh"
    local tmp="$script.new"
    grep -v '^main "\$@"$' "$script" > "$tmp"
    cat >> "$tmp" <<'LEGACY'
add_email_to_file() {
    local email="$1"
    [[ -n "$email" ]] || return 0
    ensure_emails_file
    local needs_email_commit=false
    if grep -qFx -- "$email" "$EMAILS_FILE" 2>/dev/null; then
        ait_email_is_committed "$email" || needs_email_commit=true
    else
        local lockdir token rc=0
        lockdir="$(ait_lock_dir emails)" || return 0
        if ! stale_lock_acquire "$lockdir" "$EMAILS_LOCK_ATTEMPTS" "$EMAILS_LOCK_SLEEP" \
                "contributor list" "$_STALE_LOCK_GC_WINDOW_DEFAULT"; then
            warn "contributor list busy — email not recorded$(stale_lock_describe "$lockdir")"
            return 0
        fi
        token="$STALE_LOCK_TOKEN"
        {
            if ! grep -qFx -- "$email" "$EMAILS_FILE" 2>/dev/null; then
                printf '%s\n' "$email" >> "$EMAILS_FILE" &&
                    needs_email_commit=true &&
                    sort -u "$EMAILS_FILE" -o "$EMAILS_FILE"
            fi
        } || rc=$?
        stale_lock_release "$lockdir" "$token" \
            || warn "add_email_to_file: contributor-list lock not fully released"
        [[ $rc -eq 0 ]] || warn "add_email_to_file: failed to record ${email} (rc=$rc)"
    fi
    if [[ "$needs_email_commit" == true ]]; then
        local crc=0
        task_git_commit_scoped "ait: Record contributor email" "$EMAILS_FILE" || crc=$?
        [[ $crc -eq 1 ]] && warn "could not commit ${EMAILS_FILE}"
    fi
    return 0
}
LEGACY
    printf 'main "$@"\n' >> "$tmp"
    mv "$tmp" "$script"
    chmod +x "$script"
}

# Force stale_lock_release to report failure WITHOUT actually abandoning the
# lock, so the release-failure policy can be driven on its own. The real release
# still runs first: a shim that skipped it would strand the lock dir and make
# every later assertion in the run meaningless.
install_failing_release() {
    local script=".aitask-scripts/aitask_create.sh"
    local tmp="$script.new"
    grep -v '^main "\$@"$' "$script" > "$tmp"
    cat >> "$tmp" <<'INJECT'
eval "_orig_stale_lock_release() $(declare -f stale_lock_release | tail -n +2)"
stale_lock_release() {
    _orig_stale_lock_release "$@" || true
    return 1
}
INJECT
    printf 'main "$@"\n' >> "$tmp"
    mv "$tmp" "$script"
    chmod +x "$script"
}

# Patch the FIXTURE'S COPY of lib/stale_lock.sh so stale_lock_acquire pauses at
# a controllable barrier before it contends for the mutex — the seam between
# add_email_to_file's PRE-LOCK membership check and its mutex acquisition.
#
# Blocking there is the only way to pin the interleaving deterministically: the
# creating process's pre-lock check must observe the address ABSENT, and the
# other writer's append must land before its UNDER-LOCK re-check. Waiting on
# wall-clock instead would let a scenario that never reproduced report success
# by running slow.
#
# Opt-in per run (AIT_TEST_ACQ_SIGNAL / AIT_TEST_ACQ_GO), so the patched copy
# behaves exactly like the real library everywhere else — and holder.sh, which
# sources the PROJECT's library, is unaffected.
install_acquire_barrier() {
    local lib=".aitask-scripts/lib/stale_lock.sh"
    local tmp="$lib.new"
    awk '
        /^stale_lock_acquire\(\) \{$/ {
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

# --- t1626 shared assertions -------------------------------------------------

# assert_contributor_commit_shape <label> <address>
# The FOUR properties every create-side contributor test asserts. Cleanliness
# alone is not enough: it would also hold if a TASK commit had swept emails.txt,
# which is exactly the path-scoping violation t1599_1 removed and this must not
# reintroduce. Run from inside the project dir.
assert_contributor_commit_shape() {
    local label="$1" addr="$2"
    assert_eq "$label: emails.txt is clean" \
        "" "$(git status --porcelain "$EMAILS_PATH")"
    assert_contains "$label: the address is committed at HEAD" \
        "$addr" "$(git show "HEAD:$EMAILS_PATH")"
    local c files
    c=$(git log --format=%H --grep='^ait: Record contributor email' | head -1)
    assert_non_empty_c "$label: a contributor-email commit exists" "$c"
    files=$(git show --name-only --pretty=format: "$c" | grep -v '^$')
    assert_eq "$label: that commit touches ONLY emails.txt" "$EMAILS_PATH" "$files"
    assert_contains "$label: HEAD is still the task commit" \
        "ait: Add task t" "$(git log -1 --pretty=%s)"
}

# The shared helpers have no non-empty form, and assert_not_contains "" can
# never pass (every string contains "").
assert_non_empty_c() {
    local desc="$1" value="$2"
    if [[ -n "$value" ]]; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: $desc (expected a non-empty value, got '')"
    fi
}

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

    # holder_nocommit.sh <lock_dir> <emails_file> <address>
    #
    # The OTHER writer in its simplest form (t1626): take the mutex through
    # registry_lock.sh — the adapter store_email itself takes — append, release,
    # and EXIT WITHOUT COMMITTING. That last part is the whole point: it is
    # exactly the "appended, released, then died before its own commit" end
    # state the under-lock re-check has to recover from.
    #
    # It sources the PROJECT's library, not the fixture's barrier-patched copy,
    # so install_acquire_barrier never applies to it.
    cat > "$HELPER_DIR/holder_nocommit.sh" <<EOF
#!/usr/bin/env bash
set -u
LIB="$PROJECT_DIR/.aitask-scripts/lib"
EOF
    cat >> "$HELPER_DIR/holder_nocommit.sh" <<'NOCOMMIT'
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
NOCOMMIT
    chmod +x "$HELPER_DIR/holder_nocommit.sh"
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
# Nothing was written under the mutex, so nothing is owed a commit either. This
# is the direct pin for "the contributor commit never runs on the skip path"
# (t1626) — without it the skip could still produce a spurious commit.
assert_eq "Test 2: no contributor-email commit was made" \
    "" "$(git log --format=%H --grep='^ait: Record contributor email')"

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
    # Git state has to be sampled HERE — teardown pops out of the project dir,
    # so a caller cannot inspect it afterwards (t1626).
    LAST_SCENARIO_STATUS="$(git status --porcelain "$EMAILS_PATH")"
    LAST_SCENARIO_HEAD_EMAILS="$(git show "HEAD:$EMAILS_PATH" 2>/dev/null)"
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

# --- Tests 8-13: every append is followed by a guaranteed commit (t1626) -----
#
# aitask_create.sh never named EMAILS_FILE in a task_git add, and since t1599_1
# scoped every claim commit to its own paths nothing swept it either — so an
# address recorded by `ait create --assigned-to <new>` stayed on disk,
# uncommitted, indefinitely. The membership short-circuits are what made that
# permanent: they return before the "owes a commit" flag can be set, so no later
# call ever committed it. There are TWO of them (pre-lock and under-lock) and
# each gets its own test plus its own positive negative-control.

# --- Test 8: a new address is committed, in its OWN path-scoped commit -------
echo "--- Test 8: ait create --assigned-to leaves emails.txt clean ---"

setup_project

AITASKS_LOCK_DIR="$LOCKBASE" ./.aitask-scripts/aitask_create.sh --batch --commit --silent \
    --name "new_contributor" --desc "New address" --assigned-to "carol@test.com" \
    >/dev/null 2>&1
rc8=$?
assert_eq "Test 8: creation succeeded (exit 0)" "0" "$rc8"
assert_contributor_commit_shape "Test 8" "carol@test.com"

teardown

# --- Test 9: PRE-LOCK fast-path recovery ------------------------------------
# An address on disk but not at HEAD — the end state of any write whose commit
# was lost. The membership fast-path used to return before the flag could be
# set, making that permanent; it now consults HEAD.
echo "--- Test 9: a membership hit on an UNCOMMITTED address is recovered ---"

setup_project

printf 'dave@test.com\n' >> "$EMAILS_PATH"
assert_contains "Test 9: precondition — the address is on disk and dirty" \
    " M $EMAILS_PATH" "$(git status --porcelain "$EMAILS_PATH")"

AITASKS_LOCK_DIR="$LOCKBASE" ./.aitask-scripts/aitask_create.sh --batch --commit --silent \
    --name "recover_contributor" --desc "Stranded address" --assigned-to "dave@test.com" \
    >/dev/null 2>&1
assert_contributor_commit_shape "Test 9" "dave@test.com"

teardown

# --- Test 10: NEGATIVE CONTROL — the pre-fix body commits nothing ------------
# Asserts the defect POSITIVELY in BOTH shapes, so a control whose injection
# silently failed cannot pass.
echo "--- Test 10: NEGATIVE CONTROL — pre-fix add_email_to_file never commits ---"

setup_project
install_prefix_add_email_to_file_nocommit

AITASKS_LOCK_DIR="$LOCKBASE" ./.aitask-scripts/aitask_create.sh --batch --commit --silent \
    --name "prefix_fresh" --desc "Fresh address, pre-fix" --assigned-to "heidi@test.com" \
    >/dev/null 2>&1
assert_contains "Test 10a: pre-fix DOES leave a fresh address dirty" \
    " M $EMAILS_PATH" "$(git status --porcelain "$EMAILS_PATH")"
assert_eq "Test 10a: pre-fix makes NO contributor-email commit" \
    "" "$(git log --format=%H --grep='^ait: Record contributor email')"

# ...and the already-on-disk shape: a later create with the SAME address hits
# the membership short-circuit and cannot rescue it either.
AITASKS_LOCK_DIR="$LOCKBASE" ./.aitask-scripts/aitask_create.sh --batch --commit --silent \
    --name "prefix_again" --desc "Same address, pre-fix" --assigned-to "heidi@test.com" \
    >/dev/null 2>&1
assert_contains "Test 10b: pre-fix leaves it STILL dirty on the same-address retry" \
    " M $EMAILS_PATH" "$(git status --porcelain "$EMAILS_PATH")"
assert_eq "Test 10b: pre-fix still makes NO contributor-email commit" \
    "" "$(git log --format=%H --grep='^ait: Record contributor email')"

teardown

# --- Test 11: a retained mutex must not silently swallow the address ---------
# stale_lock_release reports failure exactly when OUR OWN lock dir is still in
# place, so the commit that follows is MORE serialized then, not less — gating
# it on that status would skip it precisely when it is safest. The policy is
# therefore warn-and-commit, and this pins it.
echo "--- Test 11: a failed lock release still commits the address ---"

setup_project
install_failing_release

err11_file="$(mktemp)"
AITASKS_LOCK_DIR="$LOCKBASE" ./.aitask-scripts/aitask_create.sh --batch --commit --silent \
    --name "release_failure" --desc "Forced release failure" --assigned-to "ivan@test.com" \
    >/dev/null 2>"$err11_file"
rc11=$?
err11=$(cat "$err11_file"); rm -f "$err11_file"

# (a) The injection took effect — proven, not assumed.
assert_contains "Test 11: the retained mutex is reported" \
    "contributor-list lock not fully released" "$err11"
# (b) The warning names the recovery, so a retained lock is not a dead end.
assert_contains "Test 11: ...and names the reclaim that clears it" \
    "dead-record reclaim" "$err11"
# (c) Best-effort contract, and the address is still committed.
assert_eq "Test 11: creation still succeeds (exit 0)" "0" "$rc11"
assert_contributor_commit_shape "Test 11" "ivan@test.com"

teardown

# --- Test 12: a concurrent writer's line is never lost -----------------------
# The commit runs OUTSIDE the mutex (matching store_email / commit_and_push),
# so it can capture a snapshot that lags a concurrent append. `sort -o` renames
# a temp over the target and a single short append is not torn, so nothing is
# corrupted — and the lagged line's own writer owes it a commit. This pins that
# no address is lost across the real interleaving.
echo "--- Test 12: neither address is lost when the commit runs outside the mutex ---"

run_lost_update_scenario fixed "Test 12"
# Test 3 already pins that neither address is lost ON DISK. What only this test
# can see is what the commit did with them: create appends bob AFTER the
# holder's write-back, so the commit it makes outside the mutex must carry the
# holder's line too, and must leave nothing behind.
assert_eq "Test 12: emails.txt is clean — nothing stranded by the interleaving" \
    "" "$LAST_SCENARIO_STATUS"
assert_contains "Test 12: the holder's address reached HEAD" \
    "alice@test.com" "$LAST_SCENARIO_HEAD_EMAILS"
assert_contains "Test 12: ait create's address reached HEAD" \
    "bob@test.com" "$LAST_SCENARIO_HEAD_EMAILS"

# --- Test 13: UNDER-LOCK recheck recovery ------------------------------------
# The concurrent hole the pre-lock fix alone does not close:
#
#   holder (registry_lock)         ait create (stale_lock, under test)
#   ----------------------------   ------------------------------------------
#                                  PRE-LOCK check runs — address ABSENT
#                                  ... parked at the mutex barrier
#   acquire; append addr; release
#   (never commits)
#                                  acquires; RE-CHECK finds it ⇒ must consult
#                                  HEAD and commit it
echo "--- Test 13: a holder's uncommitted append is recovered at the re-check ---"

run_create_recheck_scenario() {   # <mode: fixed|prefix> <label>
    local mode="$1" label="$2"
    setup_project
    [[ "$mode" == "prefix" ]] && install_prefix_add_email_to_file_norecheck
    install_acquire_barrier

    local sig="$PWD/.at_acquire" go="$PWD/.acquire_go"
    rm -f "$sig" "$go"

    # 1. Start the creation. It runs add_email_to_file's PRE-LOCK check now —
    #    erin is absent, nothing has written it — then parks at the barrier.
    AITASKS_LOCK_DIR="$LOCKBASE" AIT_TEST_ACQ_SIGNAL="$sig" AIT_TEST_ACQ_GO="$go" \
        ./.aitask-scripts/aitask_create.sh --batch --commit --silent \
        --name "recheck_recovery" --desc "Under-lock recheck" \
        --assigned-to "erin@test.com" >/dev/null 2>&1 &
    local create_pid=$!

    if ! wait_for_file "$sig" 30; then
        assert_record_fail
        echo "FAIL: $label: create never reached the mutex barrier"
        kill "$create_pid" 2>/dev/null; wait "$create_pid" 2>/dev/null
        teardown
        return 1
    fi

    # The barrier proves the ordering rather than assuming it.
    assert_not_contains "$label: precondition — erin was ABSENT at the pre-lock check" \
        "erin@test.com" "$(cat "$EMAILS_PATH")"

    # 2. The other writer appends erin under the mutex and exits WITHOUT
    #    committing. Synchronous: nothing is contending yet.
    AITASKS_LOCK_DIR="$LOCKBASE" bash "$HELPER_DIR/holder_nocommit.sh" \
        "$LOCKBASE/emails" "$PWD/$EMAILS_PATH" "erin@test.com" >/dev/null 2>&1

    assert_contains "$label: precondition — the holder's address is on disk" \
        "erin@test.com" "$(cat "$EMAILS_PATH")"
    assert_contains "$label: precondition — and uncommitted" \
        " M $EMAILS_PATH" "$(git status --porcelain "$EMAILS_PATH")"

    # 3. Release create. Its UNDER-LOCK re-check is the only thing left that can
    #    notice the address, and it is the branch under test.
    : > "$go"
    wait "$create_pid" 2>/dev/null
}

run_create_recheck_scenario fixed "Test 13"
assert_contributor_commit_shape "Test 13" "erin@test.com"
teardown

echo "--- Test 13b: NEGATIVE CONTROL — pre-lock consult alone does not recover ---"
run_create_recheck_scenario prefix "Test 13b"
assert_contains "Test 13b: pre-fix DOES leave the holder's address dirty" \
    " M $EMAILS_PATH" "$(git status --porcelain "$EMAILS_PATH")"
assert_eq "Test 13b: pre-fix makes NO contributor-email commit" \
    "" "$(git log --format=%H --grep='^ait: Record contributor email')"
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
