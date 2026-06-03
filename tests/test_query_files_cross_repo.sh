#!/usr/bin/env bash
# test_query_files_cross_repo.sh - Cover cross-repo --project re-exec and
# the new task-status subcommand on aitask_query_files.sh, plus --project
# re-exec on aitask_ls.sh and aitask_find_by_file.sh (t832_1).
#
# Sister-side dispatch is verified with stub helpers that log argv to a
# sentinel file. Local task-status behavior is verified against a real
# fake aitasks/ tree by cd'ing there and invoking the real script via
# its absolute path (the script resolves libs via SCRIPT_DIR but reads
# task data from CWD-relative aitasks/).
#
# Run: bash tests/test_query_files_cross_repo.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"

# --- Setup --------------------------------------------------------------

TMPROOT=$(mktemp -d)
trap 'rm -rf "$TMPROOT"' EXIT

REGISTRY_FILE="$TMPROOT/projects.yaml"
export AITASKS_PROJECTS_INDEX="$REGISTRY_FILE"

# Fake sibling with stub helpers that just log argv + cwd to a sentinel.
SISTER_ROOT="$TMPROOT/sister"
mkdir -p "$SISTER_ROOT/.aitask-scripts"
mkdir -p "$SISTER_ROOT/aitasks/metadata"
touch "$SISTER_ROOT/aitasks/metadata/project_config.yaml"

SENTINEL_QF="$TMPROOT/sister-qf-invocation.log"
SENTINEL_LS="$TMPROOT/sister-ls-invocation.log"
SENTINEL_FBF="$TMPROOT/sister-fbf-invocation.log"

for pair in \
    "aitask_query_files.sh:$SENTINEL_QF" \
    "aitask_ls.sh:$SENTINEL_LS" \
    "aitask_find_by_file.sh:$SENTINEL_FBF"; do
    helper="${pair%%:*}"
    sentinel="${pair##*:}"
    cat > "$SISTER_ROOT/.aitask-scripts/$helper" <<EOF
#!/usr/bin/env bash
echo "CWD=\$(pwd)"   >> "$sentinel"
echo "ARGC=\$#"       >> "$sentinel"
printf 'ARG=%s\n' "\$@" >> "$sentinel"
exit 0
EOF
    chmod +x "$SISTER_ROOT/.aitask-scripts/$helper"
done

# Stale sibling: registered name points at a path missing the marker file.
STALE_ROOT="$TMPROOT/stale"
mkdir -p "$STALE_ROOT"  # no aitasks/metadata/project_config.yaml

cat > "$REGISTRY_FILE" <<EOF
projects:
  - name: sister
    path: $SISTER_ROOT
  - name: stale_one
    path: $STALE_ROOT
EOF

QF="$PROJECT_DIR/.aitask-scripts/aitask_query_files.sh"
LS="$PROJECT_DIR/.aitask-scripts/aitask_ls.sh"
FBF="$PROJECT_DIR/.aitask-scripts/aitask_find_by_file.sh"

# --- Dispatch tests (sister stub records argv) ---------------------------

# 1. aitask_query_files.sh --project sister task-file 42
: > "$SENTINEL_QF"
"$QF" --project sister task-file 42 >/dev/null 2>&1
invocation=$(cat "$SENTINEL_QF")
assert_contains "QF: cd'd into sister"        "CWD=$SISTER_ROOT" "$invocation"
assert_contains "QF: forwarded subcommand"    "ARG=task-file"    "$invocation"
assert_contains "QF: forwarded subcommand arg" "ARG=42"          "$invocation"
assert_not_contains "QF: --project stripped"   "ARG=--project"   "$invocation"
assert_not_contains "QF: sister name stripped" "ARG=sister"      "$invocation"

# 2. aitask_ls.sh --project sister -v 10
: > "$SENTINEL_LS"
"$LS" --project sister -v 10 >/dev/null 2>&1
invocation=$(cat "$SENTINEL_LS")
assert_contains "LS: cd'd into sister"     "CWD=$SISTER_ROOT" "$invocation"
assert_contains "LS: forwarded -v"          "ARG=-v"          "$invocation"
assert_contains "LS: forwarded limit"       "ARG=10"          "$invocation"
assert_not_contains "LS: --project stripped" "ARG=--project"  "$invocation"

# 3. aitask_find_by_file.sh --project sister some/path.py
: > "$SENTINEL_FBF"
"$FBF" --project sister some/path.py >/dev/null 2>&1
invocation=$(cat "$SENTINEL_FBF")
assert_contains "FBF: cd'd into sister"      "CWD=$SISTER_ROOT" "$invocation"
assert_contains "FBF: forwarded path arg"     "ARG=some/path.py" "$invocation"
assert_not_contains "FBF: --project stripped" "ARG=--project"   "$invocation"

# --- Resolver error tests ------------------------------------------------

# NOT_FOUND — exercise each helper individually.
check_not_found() {
    local label="$1"; shift
    set +e
    local out rc
    out=$("$@" --project notreal_xxx 2>&1)
    rc=$?
    set -e
    assert_contains "$label: NOT_FOUND surfaces" "is not registered" "$out"
    TOTAL=$((TOTAL + 1))
    if [[ "$rc" -ne 0 ]]; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); echo "FAIL: $label NOT_FOUND must exit non-zero"; fi
}
check_not_found "QF"  "$QF" task-file 1
check_not_found "LS"  "$LS" 10
check_not_found "FBF" "$FBF" foo.py

# STALE
set +e
out=$("$QF" --project stale_one task-file 1 2>&1)
rc=$?
set -e
assert_contains "QF: STALE surfaces" "is stale" "$out"
TOTAL=$((TOTAL + 1))
if [[ "$rc" -ne 0 ]]; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); echo "FAIL: QF STALE must exit non-zero"; fi

# Missing --project value
set +e
out=$("$QF" --project 2>&1)
rc=$?
set -e
assert_contains "QF: --project requires value" "--project requires a value" "$out"
TOTAL=$((TOTAL + 1))
if [[ "$rc" -ne 0 ]]; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); echo "FAIL: QF --project missing value must exit non-zero"; fi

# --- Local task-status subcommand tests ----------------------------------

# Build a fake project with several statuses, including a child and an
# archived parent.
LOCAL_ROOT="$TMPROOT/local_repo"
mkdir -p "$LOCAL_ROOT/aitasks/t200"
mkdir -p "$LOCAL_ROOT/aitasks/archived"

write_task() {
    local file="$1" status="$2"
    cat > "$file" <<EOF
---
priority: medium
effort: medium
issue_type: feature
status: $status
---
body
EOF
}

write_task "$LOCAL_ROOT/aitasks/t100_ready.md"        "Ready"
write_task "$LOCAL_ROOT/aitasks/t101_implementing.md" "Implementing"
write_task "$LOCAL_ROOT/aitasks/t102_postponed.md"    "Postponed"
write_task "$LOCAL_ROOT/aitasks/t103_folded.md"       "Folded"
write_task "$LOCAL_ROOT/aitasks/t200/t200_1_ready.md" "Ready"
write_task "$LOCAL_ROOT/aitasks/t200/t200_2_editing.md" "Editing"
# Archived parent — task-status falls through to archive and returns Done.
write_task "$LOCAL_ROOT/aitasks/archived/t50_done.md" "Done"

run_status() {
    local id="$1"
    ( cd "$LOCAL_ROOT" && "$QF" task-status "$id" )
}

assert_eq "task-status t100 (Ready)"        "STATUS:Ready"        "$(run_status 100)"
assert_eq "task-status t101 (Implementing)" "STATUS:Implementing" "$(run_status 101)"
assert_eq "task-status t102 (Postponed)"    "STATUS:Postponed"    "$(run_status 102)"
assert_eq "task-status t103 (Folded)"       "STATUS:Folded"       "$(run_status 103)"
assert_eq "task-status t200_1 (child Ready)" "STATUS:Ready"       "$(run_status 200_1)"
assert_eq "task-status t200_2 (child Editing)" "STATUS:Editing"   "$(run_status 200_2)"
assert_eq "task-status t050 (archived → Done)" "STATUS:Done"      "$(run_status 50)"
assert_eq "task-status NOT_FOUND"           "STATUS:NOT_FOUND"    "$(run_status 9999)"

# Missing argument
set +e
out=$("$QF" task-status 2>&1)
rc=$?
set -e
assert_contains "task-status requires arg" "task-status requires" "$out"
TOTAL=$((TOTAL + 1))
if [[ "$rc" -ne 0 ]]; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); echo "FAIL: task-status missing arg must exit non-zero"; fi

# Invalid id
set +e
out=$("$QF" task-status not_a_number 2>&1)
rc=$?
set -e
assert_contains "task-status invalid id rejected" "Invalid task id" "$out"
TOTAL=$((TOTAL + 1))
if [[ "$rc" -ne 0 ]]; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); echo "FAIL: task-status invalid id must exit non-zero"; fi

# --- Summary ------------------------------------------------------------

echo
echo "===================="
echo "Passed: $PASS / $TOTAL"
[[ "$FAIL" -gt 0 ]] && echo "Failed: $FAIL"
echo "===================="
[[ "$FAIL" -eq 0 ]]
