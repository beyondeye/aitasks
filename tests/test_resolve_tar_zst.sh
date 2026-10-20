#!/usr/bin/env bash
# test_resolve_tar_zst.sh - Automated tests for archive fallback in resolve functions
# Run: bash tests/test_resolve_tar_zst.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

# --- Setup helpers ---

# Create a standard test environment with task/plan directory structure
# Returns: path to the temp root directory
setup_test_env() {
    local tmpdir
    tmpdir=$(mktemp -d)

    mkdir -p "$tmpdir/aitasks/archived"
    mkdir -p "$tmpdir/aiplans/archived"

    echo "$tmpdir"
}

# Create a tar.zst archive mimicking aitask_zip_old.sh format (./prefix paths)
# Args: $1=archive_path, $2=source_dir (files to archive, relative structure preserved)
create_test_archive() {
    local archive_path="$1"
    local source_dir="$2"
    tar -cf - -C "$source_dir" . | zstd -q -o "$archive_path"
}

# Create a tar.gz archive for backward compatibility tests
create_test_archive_gz() {
    local archive_path="$1"
    local source_dir="$2"
    tar -czf "$archive_path" -C "$source_dir" .
}

# Source task_utils.sh with overridden directories pointing to test env
# Args: $1=tmpdir
# Must be called in the same shell (not subshell) where resolve functions will be used
source_task_utils() {
    local tmpdir="$1"
    export TASK_DIR="$tmpdir/aitasks"
    export ARCHIVED_DIR="$tmpdir/aitasks/archived"
    export PLAN_DIR="$tmpdir/aiplans"
    export ARCHIVED_PLAN_DIR="$tmpdir/aiplans/archived"
    export SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"

    # Reset the guard so we can re-source with new directories
    unset _AIT_TASK_UTILS_LOADED
    # Reset temp dir from previous test
    if [[ -n "$_AIT_TASK_UTILS_TMPDIR" && -d "$_AIT_TASK_UTILS_TMPDIR" ]]; then
        rm -rf "$_AIT_TASK_UTILS_TMPDIR"
    fi
    _AIT_TASK_UTILS_TMPDIR=""

    source "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"
}

# --- Tests ---

echo "=== test_resolve_tar_zst.sh ==="
echo ""

# --- Test 1: Resolve parent task from active dir ---
echo "--- Test 1: Resolve parent task from active dir ---"
TMPDIR_1=$(setup_test_env)
echo "task 50 content" > "$TMPDIR_1/aitasks/t50_test_feature.md"
source_task_utils "$TMPDIR_1"
result=$(resolve_task_file "50")
assert_eq "Parent task resolved from active dir" "$TMPDIR_1/aitasks/t50_test_feature.md" "$result"
rm -rf "$TMPDIR_1"

# --- Test 2: Resolve parent task from archived dir ---
echo "--- Test 2: Resolve parent task from archived dir ---"
TMPDIR_2=$(setup_test_env)
echo "archived task 50 content" > "$TMPDIR_2/aitasks/archived/t50_test_feature.md"
source_task_utils "$TMPDIR_2"
result=$(resolve_task_file "50")
assert_eq "Parent task resolved from archived dir" "$TMPDIR_2/aitasks/archived/t50_test_feature.md" "$result"
rm -rf "$TMPDIR_2"

# --- Test 3: Resolve parent task from tar.zst ---
echo "--- Test 3: Resolve parent task from tar.zst ---"
TMPDIR_3=$(setup_test_env)
# Create tar.zst with a task file inside
staging=$(mktemp -d)
echo "tar task 50 content" > "$staging/t50_test_feature.md"
create_test_archive "$TMPDIR_3/aitasks/archived/old.tar.zst" "$staging"
rm -rf "$staging"
source_task_utils "$TMPDIR_3"
result=$(resolve_task_file "50")
actual_content=$(cat "$result")
assert_eq "Parent task from tar.zst has correct content" "tar task 50 content" "$actual_content"
rm -rf "$TMPDIR_3"

# --- Test 4: Resolve child task from active dir ---
echo "--- Test 4: Resolve child task from active dir ---"
TMPDIR_4=$(setup_test_env)
mkdir -p "$TMPDIR_4/aitasks/t10"
echo "child 10_2 content" > "$TMPDIR_4/aitasks/t10/t10_2_add_login.md"
source_task_utils "$TMPDIR_4"
result=$(resolve_task_file "10_2")
assert_eq "Child task resolved from active dir" "$TMPDIR_4/aitasks/t10/t10_2_add_login.md" "$result"
rm -rf "$TMPDIR_4"

# --- Test 5: Resolve child task from archived dir ---
echo "--- Test 5: Resolve child task from archived dir ---"
TMPDIR_5=$(setup_test_env)
mkdir -p "$TMPDIR_5/aitasks/archived/t10"
echo "archived child 10_2 content" > "$TMPDIR_5/aitasks/archived/t10/t10_2_add_login.md"
source_task_utils "$TMPDIR_5"
result=$(resolve_task_file "10_2")
assert_eq "Child task resolved from archived dir" "$TMPDIR_5/aitasks/archived/t10/t10_2_add_login.md" "$result"
rm -rf "$TMPDIR_5"

# --- Test 6: Resolve child task from tar.zst ---
echo "--- Test 6: Resolve child task from tar.zst ---"
TMPDIR_6=$(setup_test_env)
staging=$(mktemp -d)
mkdir -p "$staging/t10"
echo "tar child 10_2 content" > "$staging/t10/t10_2_add_login.md"
create_test_archive "$TMPDIR_6/aitasks/archived/old.tar.zst" "$staging"
rm -rf "$staging"
source_task_utils "$TMPDIR_6"
result=$(resolve_task_file "10_2")
actual_content=$(cat "$result")
assert_eq "Child task from tar.zst has correct content" "tar child 10_2 content" "$actual_content"
rm -rf "$TMPDIR_6"

# --- Test 7: Resolve parent plan from tar.zst ---
echo "--- Test 7: Resolve parent plan from tar.zst ---"
TMPDIR_7=$(setup_test_env)
staging=$(mktemp -d)
echo "tar plan 50 content" > "$staging/p50_test_feature.md"
create_test_archive "$TMPDIR_7/aiplans/archived/old.tar.zst" "$staging"
rm -rf "$staging"
source_task_utils "$TMPDIR_7"
result=$(resolve_plan_file "50")
actual_content=$(cat "$result")
assert_eq "Parent plan from tar.zst has correct content" "tar plan 50 content" "$actual_content"
rm -rf "$TMPDIR_7"

# --- Test 8: Resolve child plan from tar.zst ---
echo "--- Test 8: Resolve child plan from tar.zst ---"
TMPDIR_8=$(setup_test_env)
staging=$(mktemp -d)
mkdir -p "$staging/p10"
echo "tar child plan 10_2 content" > "$staging/p10/p10_2_add_login.md"
create_test_archive "$TMPDIR_8/aiplans/archived/old.tar.zst" "$staging"
rm -rf "$staging"
source_task_utils "$TMPDIR_8"
result=$(resolve_plan_file "10_2")
actual_content=$(cat "$result")
assert_eq "Child plan from tar.zst has correct content" "tar child plan 10_2 content" "$actual_content"
rm -rf "$TMPDIR_8"

# --- Test 9: Priority - active dir wins over tar.zst ---
echo "--- Test 9: Priority - active dir wins over tar.zst ---"
TMPDIR_9=$(setup_test_env)
echo "active task 50" > "$TMPDIR_9/aitasks/t50_test_feature.md"
staging=$(mktemp -d)
echo "tar task 50" > "$staging/t50_test_feature.md"
create_test_archive "$TMPDIR_9/aitasks/archived/old.tar.zst" "$staging"
rm -rf "$staging"
source_task_utils "$TMPDIR_9"
result=$(resolve_task_file "50")
assert_eq "Active dir wins over tar.zst" "$TMPDIR_9/aitasks/t50_test_feature.md" "$result"
rm -rf "$TMPDIR_9"

# --- Test 10: Priority - archived dir wins over tar.zst ---
echo "--- Test 10: Priority - archived dir wins over tar.zst ---"
TMPDIR_10=$(setup_test_env)
echo "archived task 50" > "$TMPDIR_10/aitasks/archived/t50_test_feature.md"
staging=$(mktemp -d)
echo "tar task 50" > "$staging/t50_test_feature.md"
create_test_archive "$TMPDIR_10/aitasks/archived/old.tar.zst" "$staging"
rm -rf "$staging"
source_task_utils "$TMPDIR_10"
result=$(resolve_task_file "50")
assert_eq "Archived dir wins over tar.zst" "$TMPDIR_10/aitasks/archived/t50_test_feature.md" "$result"
rm -rf "$TMPDIR_10"

# --- Test 11: Not found anywhere - parent task dies ---
echo "--- Test 11: Not found anywhere - parent task dies ---"
TMPDIR_11=$(setup_test_env)
source_task_utils "$TMPDIR_11"
assert_exit_nonzero "Parent task not found exits non-zero" bash -c "
    export TASK_DIR='$TMPDIR_11/aitasks'
    export ARCHIVED_DIR='$TMPDIR_11/aitasks/archived'
    export SCRIPT_DIR='$PROJECT_DIR/.aitask-scripts'
    source '$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh'
    resolve_task_file '999'
"
rm -rf "$TMPDIR_11"

# --- Test 12: Not found anywhere - plan returns empty string ---
echo "--- Test 12: Not found anywhere - plan returns empty string ---"
TMPDIR_12=$(setup_test_env)
source_task_utils "$TMPDIR_12"
result=$(resolve_plan_file "999")
assert_eq "Plan not found returns empty string" "" "$result"
rm -rf "$TMPDIR_12"

# --- Test 13: Temp file cleanup after shell exits ---
echo "--- Test 13: Temp file cleanup after shell exits ---"
TMPDIR_13=$(setup_test_env)
staging=$(mktemp -d)
echo "tar task 77 content" > "$staging/t77_cleanup_test.md"
create_test_archive "$TMPDIR_13/aitasks/archived/old.tar.zst" "$staging"
rm -rf "$staging"
# Run in a subshell that will exit, triggering the EXIT trap.
# The subshell writes _AIT_ARCHIVE_TMPDIR to a file so the parent can check it.
marker_file=$(mktemp)
bash -c "
    export TASK_DIR='$TMPDIR_13/aitasks'
    export ARCHIVED_DIR='$TMPDIR_13/aitasks/archived'
    export SCRIPT_DIR='$PROJECT_DIR/.aitask-scripts'
    source '$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh'
    resolve_task_file '77' >/dev/null
    echo \"\$_AIT_ARCHIVE_TMPDIR\" > '$marker_file'
"
tmpdir_path=$(cat "$marker_file")
rm -f "$marker_file"
TOTAL=$((TOTAL + 1))
if [[ -n "$tmpdir_path" && ! -d "$tmpdir_path" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Temp dir should be cleaned up after shell exit (dir: '$tmpdir_path', exists: $(test -d "$tmpdir_path" && echo yes || echo no))"
fi
rm -rf "$TMPDIR_13"

# --- Tests 13b-13g: extraction dirs are found and swept by their owner (t2023) ---
# Real callers always run resolve_task_file / resolve_plan_file inside `$( )`,
# where the extraction dir's name never reaches the parent shell. Each case runs
# a separate child bash against its own probe TMPDIR and checks what is left
# behind after the child exits, so the counters stay in this shell.

# make_bundled_env -- a test env whose t77 task and p77 plan exist ONLY inside
# the numbered bundles (aitasks/archived/_b0/old0.tar.zst and its plan twin).
make_bundled_env() {
    local env staging
    env=$(setup_test_env)
    mkdir -p "$env/aitasks/archived/_b0" "$env/aiplans/archived/_b0"
    staging=$(mktemp -d)
    echo "bundled task 77" > "$staging/t77_leak_probe.md"
    create_test_archive "$env/aitasks/archived/_b0/old0.tar.zst" "$staging"
    rm -f "$staging/t77_leak_probe.md"
    echo "bundled plan 77" > "$staging/p77_leak_probe.md"
    create_test_archive "$env/aiplans/archived/_b0/old0.tar.zst" "$staging"
    rm -rf "$staging"
    echo "$env"
}

# child_preamble <env> <tmpdir> -- the environment lines every child starts with.
child_preamble() {
    cat <<EOF
export TASK_DIR='$1/aitasks' ARCHIVED_DIR='$1/aitasks/archived'
export PLAN_DIR='$1/aiplans' ARCHIVED_PLAN_DIR='$1/aiplans/archived'
export SCRIPT_DIR='$PROJECT_DIR/.aitask-scripts' TMPDIR='$2'
unset _AIT_TASK_UTILS_LOADED _AIT_ARCHIVE_UTILS_LOADED
EOF
}

# run_child <script> -- run it in a fresh bash; sets CHILD_OUT and CHILD_RC.
run_child() {
    CHILD_RC=0
    CHILD_OUT="$(bash "$1" 2>&1)" || CHILD_RC=$?
}

# leftovers <dir> -- the extraction-shaped entries still in <dir>, one per line.
leftovers() {
    ls -A "$1" 2>/dev/null | grep -E '^(ait-archive\.|tmp\.)' || true
}

ENV_X=$(make_bundled_env)

# 13b: a `$( )` resolve leaves nothing behind -- and the file outlives the `$( )`.
echo "--- Test 13b: \$( ) resolves leave no extraction dir behind ---"
PROBE=$(mktemp -d)
{ child_preamble "$ENV_X" "$PROBE"; cat <<'EOF'
source "$SCRIPT_DIR/lib/task_utils.sh"
f=$(resolve_task_file 77); echo "TASK:$(cat "$f")"
p=$(resolve_plan_file 77); echo "PLAN:$(cat "$p")"
echo "LIVE:$(ls -A "$TMPDIR" | grep -c '^ait-archive\.' || true)"
EOF
} > "$ENV_X/child_13b.sh"
run_child "$ENV_X/child_13b.sh"
assert_eq "13b: child exits 0" "0" "$CHILD_RC"
assert_contains "13b: the task is readable after its \$( ) returned" "TASK:bundled task 77" "$CHILD_OUT"
assert_contains "13b: the plan is readable after its \$( ) returned" "PLAN:bundled plan 77" "$CHILD_OUT"
assert_contains "13b: both extraction dirs exist while the shell runs" "LIVE:2" "$CHILD_OUT"
assert_eq "13b: nothing is left in TMPDIR after exit" "" "$(leftovers "$PROBE")"
rm -rf "$PROBE"

# 13c: an EXIT trap armed BEFORE sourcing still runs (sourcing used to replace it).
echo "--- Test 13c: an earlier EXIT trap survives sourcing ---"
PROBE=$(mktemp -d); MARK="$ENV_X/mark_13c"
{ child_preamble "$ENV_X" "$PROBE"; cat <<EOF
trap 'touch "$MARK"' EXIT
EOF
cat <<'EOF'
source "$SCRIPT_DIR/lib/task_utils.sh"
f=$(resolve_task_file 77); cat "$f" >/dev/null
EOF
} > "$ENV_X/child_13c.sh"
run_child "$ENV_X/child_13c.sh"
assert_eq "13c: child exits 0" "0" "$CHILD_RC"
assert_file_exists "13c: the caller's EXIT handler ran" "$MARK"
assert_eq "13c: nothing is left in TMPDIR after exit" "" "$(leftovers "$PROBE")"
rm -rf "$PROBE"

# 13d: a caller handler that itself calls `exit`, on a nonzero exit. Anything
# appended after such a handler never runs, so the cleanup must come first --
# while the caller still sees the dying status and its own exit still decides.
echo "--- Test 13d: a terminating caller handler with a nonzero exit ---"
PROBE=$(mktemp -d); RCFILE="$ENV_X/rc_13d"
{ child_preamble "$ENV_X" "$PROBE"; cat <<EOF
set -e
trap 'echo "rc=\$?" > "$RCFILE"; exit 7' EXIT
EOF
cat <<'EOF'
source "$SCRIPT_DIR/lib/task_utils.sh"
f=$(resolve_task_file 77); cat "$f" >/dev/null
exit 3
EOF
} > "$ENV_X/child_13d.sh"
run_child "$ENV_X/child_13d.sh"
assert_eq "13d: the caller's own exit decides the status" "7" "$CHILD_RC"
assert_eq "13d: the caller saw the dying status" "rc=3" "$(cat "$RCFILE" 2>/dev/null)"
assert_eq "13d: the cleanup ran although the caller's handler exits" "" "$(leftovers "$PROBE")"
rm -rf "$PROBE"

# 13d2: the REAL ledger handler, differentially. For each of its three
# spellings and each later composer (none / the real txn_chain_exit_trap), the
# wrapped child (task_utils.sh sourced between the spelling and the composer)
# must end exactly like the unwrapped one -- same status, same first-command
# warning -- plus clean up. Restoring only the caller's text after a txn
# prepend once turned the bare spelling's exit 42 into a silent 0. The txn
# prepend restores the dying status (t2071), so the explicit spelling ends 42
# behind it; the bare one is no longer first and still reports 1 + warning.
echo "--- Test 13d2: real ledger trap, wrapped vs unwrapped ---"
WARN_13D2="ran behind another command"
cat > "$ENV_X/child_13d2.sh" <<'EOF'
set -euo pipefail
source "$SCRIPT_DIR/lib/terminal_compat.sh"
source "$SCRIPT_DIR/lib/ledger_block.sh"
source "$SCRIPT_DIR/lib/txn_snapshot.sh"
my_cleanup() { :; }
case "$SPELLING" in
    bare)     trap 'ait_ledger_lock_exit_trap' EXIT ;;
    misuse)   trap 'my_cleanup; ait_ledger_lock_exit_trap' EXIT ;;
    explicit) trap 'rc=$?; my_cleanup; ait_ledger_lock_exit_trap "$rc"' EXIT ;;
esac
if [[ "$WRAP" == 1 ]]; then
    source "$SCRIPT_DIR/lib/task_utils.sh"
    f=$(resolve_task_file 77); [[ -s "$f" ]] || exit 99
else
    # The unwrapped arm must really be unwrapped: none of the libs above may
    # pull in archive_utils.sh.
    if declare -F _ait_archive_exit_chain >/dev/null; then exit 98; fi
fi
if [[ "$COMPOSER" == txn ]]; then txn_chain_exit_trap _txn_exit_trap; fi
exit 42
EOF
# expected "<status> <warn:0|1>" per cell, as measured on the unwrapped trap
declare -A EXPECT_13D2=(
    [bare.none]="42 0"     [bare.txn]="1 1"
    [misuse.none]="1 1"    [misuse.txn]="1 1"
    [explicit.none]="42 0" [explicit.txn]="42 0"
)
for sp in bare misuse explicit; do
    for comp in none txn; do
        cell="$sp.$comp"
        PROBE=$(mktemp -d)
        { child_preamble "$ENV_X" "$PROBE"; echo "export SPELLING=$sp COMPOSER=$comp WRAP=0"; cat "$ENV_X/child_13d2.sh"; } > "$ENV_X/c.sh"
        run_child "$ENV_X/c.sh"; u_rc=$CHILD_RC; u_warn=0
        if [[ "$CHILD_OUT" == *"$WARN_13D2"* ]]; then u_warn=1; fi
        { child_preamble "$ENV_X" "$PROBE"; echo "export SPELLING=$sp COMPOSER=$comp WRAP=1"; cat "$ENV_X/child_13d2.sh"; } > "$ENV_X/c.sh"
        run_child "$ENV_X/c.sh"; w_rc=$CHILD_RC; w_warn=0
        if [[ "$CHILD_OUT" == *"$WARN_13D2"* ]]; then w_warn=1; fi
        assert_eq "13d2 $cell: unwrapped baseline is the measured one" "${EXPECT_13D2[$cell]}" "$u_rc $u_warn"
        assert_eq "13d2 $cell: wrapped status equals unwrapped" "$u_rc" "$w_rc"
        assert_eq "13d2 $cell: wrapped warning presence equals unwrapped" "$u_warn" "$w_warn"
        assert_eq "13d2 $cell: wrapped child cleaned up" "" "$(leftovers "$PROBE")"
        if [[ "$cell" == bare.txn ]]; then BARE_TXN_RC=$w_rc; fi
        if [[ "$cell" == explicit.txn ]]; then EXPLICIT_TXN_RC=$w_rc; fi
        rm -rf "$PROBE"
    done
done
TOTAL=$((TOTAL + 1))
if [[ "${BARE_TXN_RC:-0}" != 0 ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: 13d2: bare ledger trap + txn prepend reported success for exit 42 (status ${BARE_TXN_RC:-unset})"
fi
assert_eq "13d2: explicit ledger trap + txn prepend ends with the dying status" "42" "${EXPLICIT_TXN_RC:-unset}"

# 13e: the sweep removes only this shell's tagged real directories. The tag is
# `<pid>.<nonce>`: a dir carrying the SAME pid with another nonce is what a
# concurrent command in a separate PID namespace sharing this TMPDIR creates,
# and it must survive (13h reproduces that collision for real).
echo "--- Test 13e: the sweep is scoped to the owner's tag ---"
PROBE=$(mktemp -d); OUTSIDE=$(mktemp -d)
{ child_preamble "$ENV_X" "$PROBE"; echo "OUTSIDE='$OUTSIDE'"; cat <<'EOF'
source "$SCRIPT_DIR/lib/task_utils.sh"
f=$(resolve_task_file 77); cat "$f" >/dev/null
echo "OWN_LIVE:$(ls -A "$TMPDIR" | grep -cF "ait-archive.$_AIT_ARCHIVE_OWNER." || true)"
mkdir "$TMPDIR/ait-archive.999999999.1.keep" "$TMPDIR/tmp.keep" "$OUTSIDE/target"
mkdir "$TMPDIR/ait-archive.$$.1.samepid" "$TMPDIR/ait-archive.$$.keep"
ln -s "$OUTSIDE/target" "$TMPDIR/ait-archive.$_AIT_ARCHIVE_OWNER.lnk"
echo "OWNER:$_AIT_ARCHIVE_OWNER"
echo "PID:$$"
EOF
} > "$ENV_X/child_13e.sh"
run_child "$ENV_X/child_13e.sh"
child_owner=$(sed -n 's/^OWNER://p' <<<"$CHILD_OUT")
child_pid=$(sed -n 's/^PID://p' <<<"$CHILD_OUT")
assert_eq "13e: child exits 0" "0" "$CHILD_RC"
assert_contains "13e: the owner tag is <pid>.<nonce>" "OWNER:$child_pid." "$CHILD_OUT"
assert_contains "13e: the extraction dir carried the owner's tag" "OWN_LIVE:1" "$CHILD_OUT"
assert_dir_exists "13e: another pid's tagged dir is kept" "$PROBE/ait-archive.999999999.1.keep"
assert_dir_exists "13e: the same pid with another nonce is kept" "$PROBE/ait-archive.$child_pid.1.samepid"
assert_dir_exists "13e: a bare same-pid tag (no nonce) is kept" "$PROBE/ait-archive.$child_pid.keep"
assert_dir_exists "13e: an untagged tmp.* dir is kept" "$PROBE/tmp.keep"
TOTAL=$((TOTAL + 1))
if [[ -L "$PROBE/ait-archive.$child_owner.lnk" ]]; then PASS=$((PASS + 1)); else
    FAIL=$((FAIL + 1)); echo "FAIL: 13e: a symlink carrying the owner's tag was removed"; fi
assert_dir_exists "13e: the symlink's target is untouched" "$OUTSIDE/target"
assert_eq "13e: the owner's real extraction dir was swept" "ait-archive.$child_owner.lnk" \
    "$(ls -A "$PROBE" | grep -F "ait-archive.$child_owner." || true)"
rm -rf "$PROBE" "$OUTSIDE"

# 13f: TMPDIR changed after sourcing. The base is pinned at source time, so a
# scoped override and an export-and-restore both land in it; the fallback
# (pinned base deleted) lands in the then-current TMPDIR, swept at exit.
echo "--- Test 13f: TMPDIR changes after sourcing ---"
BASE=$(mktemp -d); OTHER=$(mktemp -d); OTHER2=$(mktemp -d); OTHER3=$(mktemp -d)
{ child_preamble "$ENV_X" "$BASE"
  echo "OTHER='$OTHER' OTHER2='$OTHER2' OTHER3='$OTHER3' BASE='$BASE'"; cat <<'EOF'
source "$SCRIPT_DIR/lib/task_utils.sh"
f=$(TMPDIR="$OTHER" resolve_task_file 77); echo "I:$(cat "$f")"
export TMPDIR="$OTHER2"; f=$(resolve_task_file 77); echo "II:$(cat "$f")"; export TMPDIR="$BASE"
echo "IN_BASE:$(ls -A "$BASE" | grep -c '^ait-archive\.' || true)"
rm -rf "$BASE"; export TMPDIR="$OTHER3"
f=$(resolve_task_file 77); echo "III:$(cat "$f")"
echo "IN_OTHER3:$(ls -A "$OTHER3" | grep -c '^ait-archive\.' || true)"
EOF
} > "$ENV_X/child_13f.sh"
run_child "$ENV_X/child_13f.sh"
assert_eq "13f: child exits 0" "0" "$CHILD_RC"
assert_contains "13f: scoped override resolves" "I:bundled task 77" "$CHILD_OUT"
assert_contains "13f: export-and-restore resolves" "II:bundled task 77" "$CHILD_OUT"
assert_contains "13f: fallback resolves" "III:bundled task 77" "$CHILD_OUT"
assert_contains "13f: both overrides landed in the pinned base" "IN_BASE:2" "$CHILD_OUT"
assert_contains "13f: the fallback landed in the then-current TMPDIR" "IN_OTHER3:1" "$CHILD_OUT"
assert_eq "13f: nothing left in the scoped override's TMPDIR" "" "$(leftovers "$OTHER")"
assert_eq "13f: nothing left in the exported-then-restored TMPDIR" "" "$(leftovers "$OTHER2")"
assert_eq "13f: the fallback dir was swept at exit" "" "$(leftovers "$OTHER3")"
rm -rf "$BASE" "$OTHER" "$OTHER2" "$OTHER3"

# 13g: a FIRST source inside `( )` must not compose with the parent's handler,
# which `trap -p` displays there but which is not active in the subshell.
echo "--- Test 13g: first source inside ( ) leaves the parent's handler alone ---"
PROBE=$(mktemp -d); PMARK="$ENV_X/pmark_13g"
{ child_preamble "$ENV_X" "$PROBE"; echo "PMARK='$PMARK'"; cat <<'EOF'
trap 'touch "$PMARK"' EXIT
( source "$SCRIPT_DIR/lib/task_utils.sh"; f=$(resolve_task_file 77); [[ -s "$f" ]] && echo SUB_OK )
echo "AFTER_SUB_MARK:$([[ -e "$PMARK" ]] && echo yes || echo no)"
echo "AFTER_SUB_LEFT:$(ls -A "$TMPDIR" | grep -cE '^(ait-archive|tmp)\.' || true)"
EOF
} > "$ENV_X/child_13g.sh"
run_child "$ENV_X/child_13g.sh"
assert_contains "13g: the subshell resolved the bundled task" "SUB_OK" "$CHILD_OUT"
assert_contains "13g: the parent's handler did not run at subshell exit" "AFTER_SUB_MARK:no" "$CHILD_OUT"
assert_contains "13g: the subshell swept its own extraction dir" "AFTER_SUB_LEFT:0" "$CHILD_OUT"
assert_file_exists "13g: the parent's handler ran at the parent's exit" "$PMARK"
rm -rf "$PROBE"

# 13h: two LIVE commands in separate PID namespaces, sharing one TMPDIR and one
# uid, both get the same namespace-local pid. B's exit sweep must not delete A's
# still-held extraction. Needs unprivileged user+pid namespaces (`unshare
# -Urpf`); reported as SKIP, never as a pass, where they are unavailable or the
# pids did not actually collide.
echo "--- Test 13h: colliding pids across PID namespaces ---"
if command -v unshare >/dev/null 2>&1 && unshare -Urpf true >/dev/null 2>&1; then
    PROBE=$(mktemp -d); SYNC=$(mktemp -d)
    { child_preamble "$ENV_X" "$PROBE"; echo "SYNC='$SYNC'"; cat <<'EOF'
source "$SCRIPT_DIR/lib/task_utils.sh"
f=$(resolve_task_file 77)
echo "PID:$$"
if [[ "$1" == A ]]; then
    # Hold the extraction until B has EXITED, proven by b_done, which the
    # parent writes only after B returns. A timeout is a failed overlap, never
    # a pass: A that gave up early could exit before B ran and prove nothing.
    touch "$SYNC/a_ready"
    synced=0
    for _ in $(seq 600); do [[ -e "$SYNC/b_done" ]] && { synced=1; break; }; sleep 0.05; done
    if [[ $synced == 1 ]]; then echo "A_SYNC:ok"; else echo "A_SYNC:timeout"; exit 3; fi
    if [[ -s "$f" ]]; then echo "A_FILE:kept"; else echo "A_FILE:deleted"; fi
fi
EOF
    } > "$ENV_X/child_13h.sh"
    unshare -Urpf bash "$ENV_X/child_13h.sh" A > "$SYNC/a.out" 2>&1 &
    a_job=$!
    a_ready=0
    for _ in $(seq 600); do [[ -e "$SYNC/a_ready" ]] && { a_ready=1; break; }; sleep 0.05; done
    b_rc=0
    if [[ $a_ready == 1 ]]; then
        unshare -Urpf bash "$ENV_X/child_13h.sh" B > "$SYNC/b.out" 2>&1 || b_rc=$?
    fi
    touch "$SYNC/b_done"
    a_rc=0; wait "$a_job" || a_rc=$?
    a_pid=$(sed -n 's/^PID://p' "$SYNC/a.out"); b_pid=$(sed -n 's/^PID://p' "$SYNC/b.out" 2>/dev/null)
    assert_eq "13h: A extracted and signalled readiness before B started" "1" "$a_ready"
    assert_eq "13h: B exited cleanly" "0" "$b_rc"
    assert_eq "13h: A exited cleanly" "0" "$a_rc"
    assert_contains "13h: A was still alive when B had exited" "A_SYNC:ok" "$(cat "$SYNC/a.out")"
    if [[ -n "$a_pid" && "$a_pid" == "$b_pid" ]]; then
        assert_contains "13h: B's exit kept A's live extraction (both pid $a_pid)" "A_FILE:kept" "$(cat "$SYNC/a.out")"
        assert_eq "13h: both extraction dirs were swept once both exited" "" "$(leftovers "$PROBE")"
    else
        echo "SKIP: 13h: pids did not collide (A='$a_pid' B='$b_pid')"
    fi
    rm -rf "$PROBE" "$SYNC"
else
    echo "SKIP: 13h: unprivileged user+pid namespaces unavailable (unshare -Urpf)"
fi
rm -rf "$ENV_X"

# --- Test 14: extract_final_implementation_notes works on tar.zst-extracted file ---
echo "--- Test 14: extract_final_implementation_notes works on tar.zst-extracted file ---"
TMPDIR_14=$(setup_test_env)
staging=$(mktemp -d)
cat > "$staging/p30_some_plan.md" << 'PLANEOF'
---
Task: t30_some_plan.md
---

## Implementation Steps

Step 1: Do something

## Final Implementation Notes

- **Actual work done:** Completed all steps
- **Issues encountered:** None
PLANEOF
create_test_archive "$TMPDIR_14/aiplans/archived/old.tar.zst" "$staging"
rm -rf "$staging"
source_task_utils "$TMPDIR_14"
plan_path=$(resolve_plan_file "30")
notes=$(extract_final_implementation_notes "$plan_path")
assert_contains "extract_final_implementation_notes finds content from tar.zst file" "Completed all steps" "$notes"
rm -rf "$TMPDIR_14"

# --- Test 15: Backward compat - resolve parent task from tar.gz (legacy) ---
echo "--- Test 15: Backward compat - resolve parent task from tar.gz (legacy) ---"
TMPDIR_15=$(setup_test_env)
staging=$(mktemp -d)
echo "legacy gz task 50 content" > "$staging/t50_test_feature.md"
create_test_archive_gz "$TMPDIR_15/aitasks/archived/old.tar.gz" "$staging"
rm -rf "$staging"
source_task_utils "$TMPDIR_15"
result=$(resolve_task_file "50")
actual_content=$(cat "$result")
assert_eq "Parent task from legacy tar.gz has correct content" "legacy gz task 50 content" "$actual_content"
rm -rf "$TMPDIR_15"

# --- Results ---

echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
