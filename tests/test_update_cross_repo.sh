#!/usr/bin/env bash
# test_update_cross_repo.sh — Cover aitask_update.sh --project's
# argument-validation, the cross-repo re-exec dispatch, the
# status-transition allowlist, and the --name refusal. Mirrors
# tests/test_create_project_flag.sh.
#
# Run: bash tests/test_update_cross_repo.sh

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

# Build a fake sibling project named `sister` with a stub
# aitask_update.sh that dumps its argv + cwd + AIT_CROSS_REPO_REEXEC env
# into a sentinel file.
SISTER_ROOT="$TMPROOT/sister"
mkdir -p "$SISTER_ROOT/.aitask-scripts"
mkdir -p "$SISTER_ROOT/aitasks/metadata"
touch "$SISTER_ROOT/aitasks/metadata/project_config.yaml"

SENTINEL="$TMPROOT/sister-invocation.log"
cat > "$SISTER_ROOT/.aitask-scripts/aitask_update.sh" <<EOF
#!/usr/bin/env bash
echo "CWD=\$(pwd)"                              >> "$SENTINEL"
echo "REEXEC=\${AIT_CROSS_REPO_REEXEC:-unset}"  >> "$SENTINEL"
echo "ARGC=\$#"                                 >> "$SENTINEL"
printf 'ARG=%s\n' "\$@"                          >> "$SENTINEL"
exit 0
EOF
chmod +x "$SISTER_ROOT/.aitask-scripts/aitask_update.sh"

cat > "$REGISTRY_FILE" <<EOF
projects:
  - name: sister
    path: $SISTER_ROOT
EOF

UPDATE="$PROJECT_DIR/.aitask-scripts/aitask_update.sh"

run_update() {
    set +e
    OUT=$("$UPDATE" "$@" 2>&1)
    RC=$?
    set -e
}

# --- Tests --------------------------------------------------------------

# 1. --project requires --batch
run_update --project sister 1 --priority high
assert_contains "rejects --project without --batch" "--project requires --batch" "$OUT"
TOTAL=$((TOTAL + 1))
[[ "$RC" -ne 0 ]] && PASS=$((PASS + 1)) || { FAIL=$((FAIL + 1)); echo "FAIL: rejection must exit non-zero"; }

# 2. --project cannot be combined with --name
run_update --batch --project sister 1 --name renamed_task
assert_contains "rejects --project + --name" "--project cannot be combined with --name" "$OUT"
TOTAL=$((TOTAL + 1))
[[ "$RC" -ne 0 ]] && PASS=$((PASS + 1)) || { FAIL=$((FAIL + 1)); echo "FAIL: --name rejection must exit non-zero"; }

# 3. --project with --status Implementing → refused with pick hint
run_update --batch --project sister 1 --status Implementing
assert_contains "refuses cross-repo Implementing transition" "must go through 'sister's own /aitask-pick" "$OUT"
TOTAL=$((TOTAL + 1))
[[ "$RC" -ne 0 ]] && PASS=$((PASS + 1)) || { FAIL=$((FAIL + 1)); echo "FAIL: Implementing rejection must exit non-zero"; }

# 4. --project with --status Done → refused with pick hint
run_update --batch --project sister 1 --status Done
assert_contains "refuses cross-repo Done transition" "must go through 'sister's own /aitask-pick" "$OUT"
TOTAL=$((TOTAL + 1))
[[ "$RC" -ne 0 ]] && PASS=$((PASS + 1)) || { FAIL=$((FAIL + 1)); echo "FAIL: Done rejection must exit non-zero"; }

# 5. --project with --status Folded → refused (fold not supported cross-repo)
run_update --batch --project sister 1 --status Folded
assert_contains "refuses cross-repo Folded transition" "folding requires reading both task bodies and is not supported cross-repo" "$OUT"
TOTAL=$((TOTAL + 1))
[[ "$RC" -ne 0 ]] && PASS=$((PASS + 1)) || { FAIL=$((FAIL + 1)); echo "FAIL: Folded rejection must exit non-zero"; }

# 6. --project with unregistered name → NOT_FOUND
run_update --batch --project notreal 1 --priority high
assert_contains "NOT_FOUND surfaces in error message" "is not registered" "$OUT"
TOTAL=$((TOTAL + 1))
[[ "$RC" -ne 0 ]] && PASS=$((PASS + 1)) || { FAIL=$((FAIL + 1)); echo "FAIL: NOT_FOUND must exit non-zero"; }

# 7-13. End-to-end redirects: each allowed flag combination should
# re-exec the sister stub with --project/<name> stripped and
# AIT_CROSS_REPO_REEXEC=1 set.
run_redirect() {
    local desc="$1"; shift
    > "$SENTINEL"
    "$UPDATE" "$@" >/dev/null 2>&1
    invocation=$(cat "$SENTINEL")
    assert_contains "$desc: cd'd into sister root" "CWD=$SISTER_ROOT" "$invocation"
    assert_contains "$desc: AIT_CROSS_REPO_REEXEC=1" "REEXEC=1" "$invocation"
    assert_not_contains "$desc: --project stripped" "ARG=--project" "$invocation"
    assert_not_contains "$desc: project name stripped" "ARG=sister" "$invocation"
}

run_redirect "--priority"           --batch --project sister 1 --priority high
run_redirect "--xdeps + --xdeprepo" --batch --project sister 1 --xdeps "1,2" --xdeprepo a
run_redirect "--status Postponed"   --batch --project sister 1 --status Postponed
run_redirect "--status Ready"       --batch --project sister 1 --status Ready
run_redirect "--status Editing"     --batch --project sister 1 --status Editing
run_redirect "--add-label"          --batch --project sister 1 --add-label foo
run_redirect "--boardcol/--boardidx" --batch --project sister 1 --boardcol now --boardidx 50

# 14. Verify --batch IS forwarded (we want the cross-repo aitask_update.sh
# to actually run in batch mode, not interactive)
> "$SENTINEL"
"$UPDATE" --batch --project sister 1 --priority high >/dev/null 2>&1
assert_contains "forwards --batch to sister" "ARG=--batch" "$(cat "$SENTINEL")"

# --- Summary ------------------------------------------------------------

echo
echo "===================="
echo "Passed: $PASS / $TOTAL"
[[ "$FAIL" -gt 0 ]] && echo "Failed: $FAIL"
echo "===================="
[[ "$FAIL" -eq 0 ]]
