#!/usr/bin/env bash
# test_create_project_flag.sh - Cover aitask_create.sh --project's
# argument-validation and the cross-repo re-exec dispatch. The forwarded
# args end up in a stub aitask_create.sh under a fake sibling project,
# which logs them to a file for inspection.
#
# Run: bash tests/test_create_project_flag.sh

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
# aitask_create.sh that just dumps its argv + cwd into a sentinel file.
SISTER_ROOT="$TMPROOT/sister"
mkdir -p "$SISTER_ROOT/.aitask-scripts"
mkdir -p "$SISTER_ROOT/aitasks/metadata"
touch "$SISTER_ROOT/aitasks/metadata/project_config.yaml"

SENTINEL="$TMPROOT/sister-invocation.log"
cat > "$SISTER_ROOT/.aitask-scripts/aitask_create.sh" <<EOF
#!/usr/bin/env bash
echo "CWD=\$(pwd)"   >> "$SENTINEL"
echo "ARGC=\$#"       >> "$SENTINEL"
printf 'ARG=%s\n' "\$@" >> "$SENTINEL"
exit 0
EOF
chmod +x "$SISTER_ROOT/.aitask-scripts/aitask_create.sh"

# Register the sister in the isolated registry.
cat > "$REGISTRY_FILE" <<EOF
projects:
  - name: sister
    path: $SISTER_ROOT
EOF

CREATE="$PROJECT_DIR/.aitask-scripts/aitask_create.sh"

# --- Tests --------------------------------------------------------------

# 1. --project requires --batch
set +e
out=$("$CREATE" --project sister --name foo 2>&1)
rc=$?
set -e
assert_contains "rejects --project without --batch" "--project requires --batch" "$out"
TOTAL=$((TOTAL + 1))
[[ "$rc" -ne 0 ]] && PASS=$((PASS + 1)) || { FAIL=$((FAIL + 1)); echo "FAIL: rejection must exit non-zero"; }

# 2. --project cannot be combined with --parent
set +e
out=$("$CREATE" --batch --project sister --parent 1 --name foo 2>&1)
rc=$?
set -e
assert_contains "rejects --project + --parent" "--project cannot be combined with --parent" "$out"
TOTAL=$((TOTAL + 1))
[[ "$rc" -ne 0 ]] && PASS=$((PASS + 1)) || { FAIL=$((FAIL + 1)); echo "FAIL: combo rejection must exit non-zero"; }

# 3. --project with a missing name fails fast (NOT_FOUND)
set +e
out=$("$CREATE" --batch --project notreal --name foo 2>&1)
rc=$?
set -e
assert_contains "NOT_FOUND surfaces in error message" "is not registered" "$out"
TOTAL=$((TOTAL + 1))
[[ "$rc" -ne 0 ]] && PASS=$((PASS + 1)) || { FAIL=$((FAIL + 1)); echo "FAIL: NOT_FOUND must exit non-zero"; }

# 4. End-to-end redirect: --project sister re-execs the sister's stub
#    in the sister's root, with --project/<name> stripped from argv.
> "$SENTINEL"
"$CREATE" --batch --project sister --name cross_repo_test --type chore \
    --priority low --effort low --desc "smoke" >/dev/null 2>&1

[[ -f "$SENTINEL" ]] || { FAIL=$((FAIL + 1)); echo "FAIL: sister stub never ran"; }
TOTAL=$((TOTAL + 1))
PASS=$((PASS + 1))  # sentinel existence covered above

invocation=$(cat "$SENTINEL")
assert_contains "redirect cd'd into sister root" "CWD=$SISTER_ROOT" "$invocation"
assert_contains "forwarded --batch" "ARG=--batch" "$invocation"
assert_contains "forwarded --name" "ARG=--name" "$invocation"
assert_contains "forwarded the name value" "ARG=cross_repo_test" "$invocation"
# Critical: --project / <name> must NOT appear in the forwarded argv,
# otherwise the redirect would loop.
TOTAL=$((TOTAL + 1))
if grep -qF "ARG=--project" "$SENTINEL"; then
    FAIL=$((FAIL + 1)); echo "FAIL: --project leaked through to sister"
else
    PASS=$((PASS + 1))
fi
TOTAL=$((TOTAL + 1))
if grep -qFx "ARG=sister" "$SENTINEL"; then
    FAIL=$((FAIL + 1)); echo "FAIL: project name leaked through to sister"
else
    PASS=$((PASS + 1))
fi

# --- Summary ------------------------------------------------------------

echo
echo "===================="
echo "Passed: $PASS / $TOTAL"
[[ "$FAIL" -gt 0 ]] && echo "Failed: $FAIL"
echo "===================="
[[ "$FAIL" -eq 0 ]]
