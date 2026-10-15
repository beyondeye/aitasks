#!/usr/bin/env bash
# test_archive_utils.sh - Tests for archive_utils.sh numbered archive library
# Run: bash tests/test_archive_utils.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

# --- Setup helpers ---

setup_test_env() {
    local tmpdir
    tmpdir=$(mktemp -d)
    mkdir -p "$tmpdir/aitasks/archived"
    mkdir -p "$tmpdir/aiplans/archived"
    echo "$tmpdir"
}

# Create a tar.zst archive from a staging directory.
# Automatically creates parent dirs for the archive path.
# Args: $1=archive_path, $2=source_dir
create_test_archive() {
    local archive_path="$1"
    local source_dir="$2"
    mkdir -p "$(dirname "$archive_path")"
    tar -cf - -C "$source_dir" . | zstd -q -o "$archive_path"
}

# Create a tar.gz archive (for backward compatibility tests).
# Args: $1=archive_path, $2=source_dir
create_test_archive_gz() {
    local archive_path="$1"
    local source_dir="$2"
    mkdir -p "$(dirname "$archive_path")"
    tar -czf "$archive_path" -C "$source_dir" .
}

# Source archive_utils.sh, resetting guard to allow re-sourcing.
source_archive_utils() {
    export SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"
    unset _AIT_ARCHIVE_UTILS_LOADED
    if [[ -n "${_AIT_ARCHIVE_TMPDIR:-}" && -d "$_AIT_ARCHIVE_TMPDIR" ]]; then
        rm -rf "$_AIT_ARCHIVE_TMPDIR"
    fi
    _AIT_ARCHIVE_TMPDIR=""
    source "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh"
}

# --- Tests ---

echo "=== test_archive_utils.sh ==="
echo ""

# --- Group A: archive_bundle() boundary cases ---
echo "--- Group A: archive_bundle() ---"
source_archive_utils

assert_eq "bundle(0)=0"     "0"  "$(archive_bundle 0)"
assert_eq "bundle(99)=0"    "0"  "$(archive_bundle 99)"
assert_eq "bundle(100)=1"   "1"  "$(archive_bundle 100)"
assert_eq "bundle(199)=1"   "1"  "$(archive_bundle 199)"
assert_eq "bundle(999)=9"   "9"  "$(archive_bundle 999)"
assert_eq "bundle(1000)=10" "10" "$(archive_bundle 1000)"
assert_eq "bundle(1099)=10" "10" "$(archive_bundle 1099)"
assert_eq "bundle(9999)=99" "99" "$(archive_bundle 9999)"

# --- Group B: archive_dir() boundary cases ---
echo "--- Group B: archive_dir() ---"
assert_eq "dir(0)=0"     "0"  "$(archive_dir 0)"
assert_eq "dir(9)=0"     "0"  "$(archive_dir 9)"
assert_eq "dir(10)=1"    "1"  "$(archive_dir 10)"
assert_eq "dir(19)=1"    "1"  "$(archive_dir 19)"
assert_eq "dir(99)=9"    "9"  "$(archive_dir 99)"
assert_eq "dir(100)=10"  "10" "$(archive_dir 100)"

# --- Group C: archive_path_for_id() full paths ---
echo "--- Group C: archive_path_for_id() ---"
assert_eq "path(0)"    "archived/_b0/old0.tar.zst"           "$(archive_path_for_id 0 "archived")"
assert_eq "path(99)"   "archived/_b0/old0.tar.zst"           "$(archive_path_for_id 99 "archived")"
assert_eq "path(100)"  "archived/_b0/old1.tar.zst"           "$(archive_path_for_id 100 "archived")"
assert_eq "path(999)"  "archived/_b0/old9.tar.zst"           "$(archive_path_for_id 999 "archived")"
assert_eq "path(1000)" "archived/_b1/old10.tar.zst"          "$(archive_path_for_id 1000 "archived")"
assert_eq "path(5432)" "aitasks/archived/_b5/old54.tar.zst"  "$(archive_path_for_id 5432 "aitasks/archived")"
assert_eq "path(non-numeric) -> empty (no arithmetic crash under set -u)" \
    "" "$(archive_path_for_id t1183 "archived")"

# --- Group D: _search_archive() ---
echo "--- Group D: _search_archive() ---"
TMPDIR_D=$(setup_test_env)
staging=$(mktemp -d)
echo "task 50 content" > "$staging/t50_test_feature.md"
create_test_archive "$TMPDIR_D/aitasks/archived/_b0/old0.tar.zst" "$staging"
rm -rf "$staging"
source_archive_utils

result=$(_search_archive "$TMPDIR_D/aitasks/archived/_b0/old0.tar.zst" "t50_.*\.md$")
assert_contains "search finds t50 in old0" "t50_test_feature.md" "$result"

result=$(_search_archive "$TMPDIR_D/aitasks/archived/_b0/old0.tar.zst" "t999_.*\.md$")
assert_eq "search for non-existent returns empty" "" "$result"

result=$(_search_archive "$TMPDIR_D/aitasks/archived/nonexistent.tar.zst" "t50_.*\.md$")
assert_eq "search on missing archive returns empty" "" "$result"
rm -rf "$TMPDIR_D"

# --- Group E: _extract_from_archive() ---
echo "--- Group E: _extract_from_archive() ---"
TMPDIR_E=$(setup_test_env)
staging=$(mktemp -d)
echo "extracted content here" > "$staging/t75_some_task.md"
create_test_archive "$TMPDIR_E/aitasks/archived/_b0/old0.tar.zst" "$staging"
rm -rf "$staging"
source_archive_utils

filename=$(_search_archive "$TMPDIR_E/aitasks/archived/_b0/old0.tar.zst" "t75_.*\.md$")
_extract_from_archive "$TMPDIR_E/aitasks/archived/_b0/old0.tar.zst" "$filename"
actual_content=$(cat "$_AIT_EXTRACT_RESULT")
assert_eq "extract content matches" "extracted content here" "$actual_content"
assert_contains "extract result path set" "t75_some_task.md" "$_AIT_EXTRACT_RESULT"
rm -rf "$TMPDIR_E"

# --- Group F: _find_archive_for_task() ---
echo "--- Group F: _find_archive_for_task() ---"
TMPDIR_F=$(setup_test_env)
staging=$(mktemp -d)
echo "task 150" > "$staging/t150_feature.md"
create_test_archive "$TMPDIR_F/aitasks/archived/_b0/old1.tar.zst" "$staging"
rm -rf "$staging"
source_archive_utils

result=$(_find_archive_for_task 150 "$TMPDIR_F/aitasks/archived")
assert_eq "find archive for task 150" "$TMPDIR_F/aitasks/archived/_b0/old1.tar.zst" "$result"

result=$(_find_archive_for_task 9999 "$TMPDIR_F/aitasks/archived")
assert_eq "find archive for nonexistent returns empty" "" "$result"

result=$(_find_archive_for_task t1183 "$TMPDIR_F/aitasks/archived")
assert_eq "find archive for non-numeric id returns empty" "" "$result"
rm -rf "$TMPDIR_F"

# --- Group G: _search_all_archives() ---
echo "--- Group G: _search_all_archives() ---"
TMPDIR_G=$(setup_test_env)

# Create two archives in different bundles
staging1=$(mktemp -d)
echo "task 50" > "$staging1/t50_alpha.md"
create_test_archive "$TMPDIR_G/aitasks/archived/_b0/old0.tar.zst" "$staging1"
rm -rf "$staging1"

staging2=$(mktemp -d)
echo "task 150" > "$staging2/t150_beta.md"
create_test_archive "$TMPDIR_G/aitasks/archived/_b0/old1.tar.zst" "$staging2"
rm -rf "$staging2"

source_archive_utils

# Search pattern that matches one archive
result=$(_search_all_archives "$TMPDIR_G/aitasks/archived" "t50_.*\.md$")
assert_contains "search_all finds t50" "t50_alpha.md" "$result"

# Search pattern that matches the other archive
result=$(_search_all_archives "$TMPDIR_G/aitasks/archived" "t150_.*\.md$")
assert_contains "search_all finds t150" "t150_beta.md" "$result"

# Search pattern that matches nothing
result=$(_search_all_archives "$TMPDIR_G/aitasks/archived" "t999_.*\.md$")
assert_eq "search_all no match returns empty" "" "$result"

# No archives at all
TMPDIR_G2=$(setup_test_env)
source_archive_utils
result=$(_search_all_archives "$TMPDIR_G2/aitasks/archived" "t50_.*\.md$")
assert_eq "search_all empty dir returns empty" "" "$result"
rm -rf "$TMPDIR_G" "$TMPDIR_G2"

# --- Group H: _search_numbered_then_legacy() ---
echo "--- Group H: _search_numbered_then_legacy() ---"

# H1: Only numbered .tar.zst archive exists
TMPDIR_H1=$(setup_test_env)
staging=$(mktemp -d)
echo "numbered task 200" > "$staging/t200_numonly.md"
create_test_archive "$TMPDIR_H1/aitasks/archived/_b0/old2.tar.zst" "$staging"
rm -rf "$staging"
source_archive_utils
result=$(_search_numbered_then_legacy 200 "$TMPDIR_H1/aitasks/archived" "t200_.*\.md$")
assert_contains "numbered: finds via numbered" "t200_numonly.md" "$result"
assert_contains "zst-only: correct archive path" "old2.tar.zst" "$result"
rm -rf "$TMPDIR_H1"

# H2: Only legacy old.tar.gz exists (backward compat)
TMPDIR_H2=$(setup_test_env)
staging=$(mktemp -d)
echo "legacy task 200" > "$staging/t200_legacy.md"
create_test_archive_gz "$TMPDIR_H2/aitasks/archived/old.tar.gz" "$staging"
rm -rf "$staging"
source_archive_utils
result=$(_search_numbered_then_legacy 200 "$TMPDIR_H2/aitasks/archived" "t200_.*\.md$")
assert_contains "legacy-only: finds via fallback" "t200_legacy.md" "$result"
assert_contains "legacy-only: legacy archive path" "old.tar.gz" "$result"
rm -rf "$TMPDIR_H2"

# H3: Both .tar.zst and legacy -- .tar.zst wins
TMPDIR_H3=$(setup_test_env)
staging_num=$(mktemp -d)
echo "numbered task 200" > "$staging_num/t200_num.md"
create_test_archive "$TMPDIR_H3/aitasks/archived/_b0/old2.tar.zst" "$staging_num"
rm -rf "$staging_num"
staging_leg=$(mktemp -d)
echo "legacy task 200" > "$staging_leg/t200_legacy.md"
create_test_archive_gz "$TMPDIR_H3/aitasks/archived/old.tar.gz" "$staging_leg"
rm -rf "$staging_leg"
source_archive_utils
result=$(_search_numbered_then_legacy 200 "$TMPDIR_H3/aitasks/archived" "t200_.*\.md$")
assert_contains "both: zst takes priority" "old2.tar.zst" "$result"
rm -rf "$TMPDIR_H3"

# H4: Neither exists
TMPDIR_H4=$(setup_test_env)
source_archive_utils
result=$(_search_numbered_then_legacy 200 "$TMPDIR_H4/aitasks/archived" "t200_.*\.md$")
assert_eq "neither: returns empty" "" "$result"
rm -rf "$TMPDIR_H4"

# --- Group I: Child task resolution through archive ---
echo "--- Group I: Child task resolution ---"
TMPDIR_I=$(setup_test_env)
staging=$(mktemp -d)
mkdir -p "$staging/t130"
echo "child 130_2 content" > "$staging/t130/t130_2_add_login.md"
# Task 130 -> bundle 1 -> dir 0 -> _b0/old1.tar.zst
create_test_archive "$TMPDIR_I/aitasks/archived/_b0/old1.tar.zst" "$staging"
rm -rf "$staging"
source_archive_utils

# Verify path computation for child's parent
assert_eq "child parent 130 bundle" "1" "$(archive_bundle 130)"
assert_eq "child parent 130 path" "$TMPDIR_I/aitasks/archived/_b0/old1.tar.zst" \
    "$(archive_path_for_id 130 "$TMPDIR_I/aitasks/archived")"

# Search for child pattern in correct archive
archive_path=$(archive_path_for_id 130 "$TMPDIR_I/aitasks/archived")
result=$(_search_archive "$archive_path" "(^|/)t130/t130_2_.*\.md$")
assert_contains "child search finds t130_2" "t130_2_add_login.md" "$result"

# Extract and verify content
_extract_from_archive "$archive_path" "$result"
actual_content=$(cat "$_AIT_EXTRACT_RESULT")
assert_eq "child extract content" "child 130_2 content" "$actual_content"
rm -rf "$TMPDIR_I"

# --- Group J: Temp dir cleanup ---
echo "--- Group J: Temp dir cleanup ---"
TMPDIR_J=$(setup_test_env)
staging=$(mktemp -d)
echo "cleanup test" > "$staging/t88_cleanup.md"
create_test_archive "$TMPDIR_J/aitasks/archived/_b0/old0.tar.zst" "$staging"
rm -rf "$staging"

marker_file=$(mktemp)
bash -c "
    export SCRIPT_DIR='$PROJECT_DIR/.aitask-scripts'
    source '$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh'
    filename=\$(_search_archive '$TMPDIR_J/aitasks/archived/_b0/old0.tar.zst' 't88_.*\.md$')
    _extract_from_archive '$TMPDIR_J/aitasks/archived/_b0/old0.tar.zst' \"\$filename\"
    echo \"\$_AIT_ARCHIVE_TMPDIR\" > '$marker_file'
"
tmpdir_path=$(cat "$marker_file")
rm -f "$marker_file"
TOTAL=$((TOTAL + 1))
if [[ -n "$tmpdir_path" && ! -d "$tmpdir_path" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: v2 temp dir should be cleaned up after shell exit (dir: '$tmpdir_path', exists: $(test -d "$tmpdir_path" && echo yes || echo no))"
fi
rm -rf "$TMPDIR_J"

# --- Group K: Backward compat — .tar.gz reading ---
echo "--- Group K: Backward compat (.tar.gz) ---"
TMPDIR_K=$(setup_test_env)
staging=$(mktemp -d)
echo "gz compat content" > "$staging/t60_gz_compat.md"
create_test_archive_gz "$TMPDIR_K/aitasks/archived/_b0/old0.tar.gz" "$staging"
rm -rf "$staging"
source_archive_utils

# _search_archive reads .tar.gz
result=$(_search_archive "$TMPDIR_K/aitasks/archived/_b0/old0.tar.gz" "t60_.*\.md$")
assert_contains "gz compat: search finds t60" "t60_gz_compat.md" "$result"

# _extract_from_archive reads .tar.gz
_extract_from_archive "$TMPDIR_K/aitasks/archived/_b0/old0.tar.gz" "$result"
actual_content=$(cat "$_AIT_EXTRACT_RESULT")
assert_eq "gz compat: extract content" "gz compat content" "$actual_content"

# _find_archive_for_task falls back to .tar.gz when no .tar.zst
result=$(_find_archive_for_task 60 "$TMPDIR_K/aitasks/archived")
assert_eq "gz compat: find falls back to gz" "$TMPDIR_K/aitasks/archived/_b0/old0.tar.gz" "$result"

# _find_archive_for_task prefers .tar.zst when both exist
staging2=$(mktemp -d)
echo "zst content" > "$staging2/t60_zst.md"
create_test_archive "$TMPDIR_K/aitasks/archived/_b0/old0.tar.zst" "$staging2"
rm -rf "$staging2"
source_archive_utils
result=$(_find_archive_for_task 60 "$TMPDIR_K/aitasks/archived")
assert_eq "gz compat: find prefers zst" "$TMPDIR_K/aitasks/archived/_b0/old0.tar.zst" "$result"
rm -rf "$TMPDIR_K"

# --- Group J2: EXIT-trap composition survives a re-source (t2023) ---
# The tests here reset the double-source guard and re-source, so the per-shell
# state (owner tag, pinned base, the stored caller handler) must survive a
# re-source in the same shell. Each case is a child bash with its own probe
# TMPDIR; what matters is what the child's EXIT leaves behind.
echo "--- Group J2: re-source keeps the composed EXIT trap ---"
TMPDIR_J2=$(setup_test_env)
staging=$(mktemp -d)
echo "j2 content" > "$staging/t91_j2.md"
create_test_archive "$TMPDIR_J2/aitasks/archived/_b0/old0.tar.zst" "$staging"
rm -rf "$staging"
J2_WARN="ran behind another command"

# j2_child <probe> <body-file> -- run a child that defines src (guard-reset
# source) and xt (one extraction, printing the extracted path); sets J2_OUT/J2_RC.
j2_child() {
    local probe="$1" body="$2"
    {
        echo "export SCRIPT_DIR='$PROJECT_DIR/.aitask-scripts' TMPDIR='$probe'"
        echo "A='$TMPDIR_J2/aitasks/archived/_b0/old0.tar.zst'"
        cat <<'EOF'
src() { unset _AIT_ARCHIVE_UTILS_LOADED; source "$SCRIPT_DIR/lib/archive_utils.sh"; }
xt() { _extract_from_archive "$A" "$(_search_archive "$A" 't91_.*\.md$')" && echo "$_AIT_EXTRACT_RESULT"; }
EOF
        cat "$body"
    } > "$TMPDIR_J2/child.sh"
    J2_RC=0
    J2_OUT="$(bash "$TMPDIR_J2/child.sh" 2>&1)" || J2_RC=$?
}
j2_left() { ls -A "$1" 2>/dev/null | grep -E '^(ait-archive\.|tmp\.)' || true; }

# J2a: one source vs two -- the caller's handler must still RUN after the second.
for n in 1 2; do
    probe=$(mktemp -d); mark="$TMPDIR_J2/mark_j2a_$n"
    cat > "$TMPDIR_J2/body.sh" <<EOF
trap 'touch "$mark"' EXIT
src
f=\$(xt); [[ -s "\$f" ]] && echo "X_OK"
if [[ $n == 2 ]]; then src; fi
echo "TRAP:\$(trap -p EXIT)"
echo "STORED:\$_AIT_ARCHIVE_CALLER_EXIT_TRAP"
EOF
    j2_child "$probe" "$TMPDIR_J2/body.sh"
    assert_eq "J2a ($n source(s)): child exits 0" "0" "$J2_RC"
    assert_contains "J2a ($n source(s)): extraction made" "X_OK" "$J2_OUT"
    assert_file_exists "J2a ($n source(s)): the caller's EXIT handler ran" "$mark"
    assert_contains "J2a ($n source(s)): the trap is the chain, once" \
        "TRAP:trap -- '_ait_archive_exit_chain' EXIT" "$J2_OUT"
    assert_contains "J2a ($n source(s)): the stored caller handler is intact" \
        "STORED:touch \"$mark\"" "$J2_OUT"
    assert_eq "J2a ($n source(s)): the extraction made before the re-source was swept" "" "$(j2_left "$probe")"
    rm -rf "$probe"
done

# J2b: a later prepend (the real txn_chain_exit_trap), then a re-source -- each
# handler runs exactly once (no recursion through the stored text, no dup).
probe=$(mktemp -d); count="$TMPDIR_J2/count_j2b"
cat > "$TMPDIR_J2/body.sh" <<EOF
source "\$SCRIPT_DIR/lib/terminal_compat.sh"
source "\$SCRIPT_DIR/lib/txn_snapshot.sh"
trap 'echo caller >> "$count"' EXIT
src
txn_h() { echo txn >> "$count"; }
txn_chain_exit_trap txn_h
src
f=\$(xt); [[ -s "\$f" ]] && echo "X_OK"
EOF
j2_child "$probe" "$TMPDIR_J2/body.sh"
assert_eq "J2b: child exits 0" "0" "$J2_RC"
assert_contains "J2b: extraction made" "X_OK" "$J2_OUT"
assert_eq "J2b: prepended and caller handlers each ran exactly once" "$(printf 'txn\ncaller')" "$(cat "$count" 2>/dev/null)"
assert_eq "J2b: nothing left in TMPDIR" "" "$(j2_left "$probe")"
rm -rf "$probe"

# J2b (ledger): the bare ledger trap + a real txn prepend + a re-source must
# NEVER report success for an exit 42 -- it ends 1 with the first-command
# warning, exactly as the unwrapped composition does.
probe=$(mktemp -d)
cat > "$TMPDIR_J2/body.sh" <<'EOF'
set -euo pipefail
source "$SCRIPT_DIR/lib/terminal_compat.sh"
source "$SCRIPT_DIR/lib/ledger_block.sh"
source "$SCRIPT_DIR/lib/txn_snapshot.sh"
trap 'ait_ledger_lock_exit_trap' EXIT
src
f=$(xt); [[ -s "$f" ]] || exit 99
txn_chain_exit_trap _txn_exit_trap
src
exit 42
EOF
j2_child "$probe" "$TMPDIR_J2/body.sh"
assert_eq "J2b ledger: a lost status is reported as failure, never success" "1" "$J2_RC"
assert_contains "J2b ledger: the first-command detector still fires" "$J2_WARN" "$J2_OUT"
assert_eq "J2b ledger: the archive cleanup ran" "" "$(j2_left "$probe")"
rm -rf "$probe"

# J2c: no prior trap -- a re-source leaves exactly the bare cleanup, once.
probe=$(mktemp -d)
cat > "$TMPDIR_J2/body.sh" <<'EOF'
src
f=$(xt); [[ -s "$f" ]] && echo "X_OK"
src
echo "TRAP:$(trap -p EXIT)"
EOF
j2_child "$probe" "$TMPDIR_J2/body.sh"
assert_contains "J2c: extraction made" "X_OK" "$J2_OUT"
assert_contains "J2c: the trap is the bare cleanup, once" "TRAP:trap -- '_ait_archive_cleanup' EXIT" "$J2_OUT"
assert_eq "J2c: nothing left in TMPDIR" "" "$(j2_left "$probe")"
rm -rf "$probe"

# J2d: the bash 3.2 path (`unset BASHPID` drops its special meaning). A
# guard-reset re-source inside ( ) carries the PROCESS pid as its tag there, so
# its exit must not sweep the parent's still-held extraction.
probe=$(mktemp -d); mark="$TMPDIR_J2/mark_j2d"
cat > "$TMPDIR_J2/body.sh" <<EOF
unset BASHPID
echo "BASHPID=[\${BASHPID:-}]"
trap 'touch "$mark"' EXIT
src
pf=\$(xt)
( src; sf=\$(xt); [[ -s "\$sf" ]] && echo "SUB_OK" )
if [[ -s "\$pf" ]]; then echo "PARENT_FILE_KEPT"; else echo "PARENT_FILE_GONE"; fi
EOF
j2_child "$probe" "$TMPDIR_J2/body.sh"
assert_contains "J2d: BASHPID really is unset in the child" "BASHPID=[]" "$J2_OUT"
assert_contains "J2d: the subshell extracted" "SUB_OK" "$J2_OUT"
assert_contains "J2d: the subshell's exit kept the parent's extraction" "PARENT_FILE_KEPT" "$J2_OUT"
assert_file_exists "J2d: the caller's EXIT handler ran" "$mark"
assert_eq "J2d: both extraction dirs were swept at the parent's exit" "" "$(j2_left "$probe")"
rm -rf "$probe" "$TMPDIR_J2"

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
