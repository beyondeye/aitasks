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
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"
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

# 2. --project can be combined with --parent and forwards the parent target
> "$SENTINEL"
"$CREATE" --batch --project sister --parent 1 --name foo --desc "child" >/dev/null 2>&1
invocation=$(cat "$SENTINEL")
assert_contains "forwards --parent" "ARG=--parent" "$invocation"
assert_contains "forwards parent value" "ARG=1" "$invocation"

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

# 7. Real cross-repo child creation: --project + --parent runs in the target
#    repo, --silent returns an absolute target path, and --commit leaves the
#    target task data clean.
setup_real_project() {
    local root="$1"
    local name="$2"
    local with_parent="${3:-false}"
    local with_dep="${4:-false}"

    mkdir -p "$root/aitasks/metadata"
    git -C "$root" init --quiet
    git -C "$root" config user.email "test@test.com"
    git -C "$root" config user.name "Test"

    setup_fake_aitask_repo "$root"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_create.sh" "$root/.aitask-scripts/"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" "$root/.aitask-scripts/"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_query_files.sh" "$root/.aitask-scripts/"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_project_resolve.sh" "$root/.aitask-scripts/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" "$root/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" "$root/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" "$root/.aitask-scripts/lib/"
    chmod +x "$root/.aitask-scripts"/*.sh

    cat > "$root/aitasks/metadata/project_config.yaml" <<EOF
project:
  name: $name
EOF
    printf 'bug\nchore\ndocumentation\nenhancement\nfeature\nperformance\nrefactor\nstyle\ntest\n' \
        > "$root/aitasks/metadata/task_types.txt"
    printf 'cross\nbackend\n' > "$root/aitasks/metadata/labels.txt"

    if [[ "$with_parent" == true ]]; then
        cat > "$root/aitasks/t100_parent.md" <<'TASK'
---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: []
created_at: 2026-07-03 10:00
updated_at: 2026-07-03 10:00
---

Parent task.
TASK
    fi

    if [[ "$with_dep" == true ]]; then
        cat > "$root/aitasks/t7_local_dependency.md" <<'TASK'
---
priority: medium
effort: low
depends: []
issue_type: feature
status: Ready
labels: []
created_at: 2026-07-03 10:00
updated_at: 2026-07-03 10:00
---

Local dependency.
TASK
    fi

    git -C "$root" add -A
    git -C "$root" commit -m "Initial $name setup" --quiet
}

REAL_SISTER_ROOT="$TMPROOT/real_sister"
REAL_LOCAL_ROOT="$TMPROOT/real_local"
CALLER_ROOT="$TMPROOT/caller"
mkdir -p "$REAL_SISTER_ROOT" "$REAL_LOCAL_ROOT" "$CALLER_ROOT"
setup_real_project "$REAL_SISTER_ROOT" sister true false
setup_real_project "$REAL_LOCAL_ROOT" local false true

git -C "$CALLER_ROOT" init --quiet
git -C "$CALLER_ROOT" config user.email "test@test.com"
git -C "$CALLER_ROOT" config user.name "Test"
echo "caller" > "$CALLER_ROOT/README.md"
git -C "$CALLER_ROOT" add README.md
git -C "$CALLER_ROOT" commit -m "Initial caller setup" --quiet

cat > "$REGISTRY_FILE" <<EOF
projects:
  - name: sister
    path: $REAL_SISTER_ROOT
  - name: local
    path: $REAL_LOCAL_ROOT
EOF

set +e
created_path=$(cd "$CALLER_ROOT" && "$CREATE" --batch --project sister --parent 100 \
    --name real_child --type bug --priority medium --effort low \
    --desc "Real child" --commit --silent 2>/dev/null)
create_rc=$?
set -e
assert_exit_zero_rc "real --project --parent create succeeds" "$create_rc"

lines=$(printf '%s' "$created_path" | grep -c '' | tr -d ' ')
assert_eq "silent create stdout is one line" "1" "$lines"
assert_contains "silent create returns target absolute path" "$REAL_SISTER_ROOT/aitasks/t100/t100_1_real_child.md" "$created_path"
assert_file_exists "real child file exists in sister" "$REAL_SISTER_ROOT/aitasks/t100/t100_1_real_child.md"
assert_file_not_exists "caller did not receive target-relative child" "$CALLER_ROOT/aitasks/t100/t100_1_real_child.md"

parent_body=$(cat "$REAL_SISTER_ROOT/aitasks/t100_parent.md")
assert_contains "sister parent tracks child" "children_to_implement: [t100_1]" "$parent_body"

sister_log=$(git -C "$REAL_SISTER_ROOT" log --format='%s')
assert_contains "sister logged child commit" "ait: Add child task t100_1: real child" "$sister_log"
sister_status=$(git -C "$REAL_SISTER_ROOT" status --porcelain)
assert_eq "sister clean after child create" "" "$sister_status"
caller_status=$(git -C "$CALLER_ROOT" status --porcelain)
assert_eq "caller clean after project-routed create" "" "$caller_status"

UPDATE="$PROJECT_DIR/.aitask-scripts/aitask_update.sh"
set +e
update_path=$(cd "$CALLER_ROOT" && "$UPDATE" --batch --project sister 100_1 \
    --xdeps 7 --xdeprepo local --commit --silent 2>/dev/null)
update_rc=$?
set -e
assert_exit_zero_rc "real --project child update back-fill succeeds" "$update_rc"
assert_contains "update returns target child path" "aitasks/t100/t100_1_real_child.md" "$update_path"

child_body=$(cat "$REAL_SISTER_ROOT/aitasks/t100/t100_1_real_child.md")
assert_contains "child has xdeps after back-fill" "xdeps: [7]" "$child_body"
assert_contains "child has xdeprepo after back-fill" "xdeprepo: local" "$child_body"
sister_log=$(git -C "$REAL_SISTER_ROOT" log --format='%s')
assert_contains "sister logged child update commit" "ait: Update task t100_1: real child" "$sister_log"
sister_status=$(git -C "$REAL_SISTER_ROOT" status --porcelain)
assert_eq "sister clean after child update" "" "$sister_status"

set +e
created_xdep_path=$(cd "$CALLER_ROOT" && "$CREATE" --batch --project sister --parent 100 \
    --name real_cross_dep_child --type bug --priority medium --effort low \
    --desc "Real cross dep child" --xdeps 7 --xdeprepo local \
    --commit --silent 2>/dev/null)
create_xdep_rc=$?
set -e
assert_exit_zero_rc "real --project child create with xdeps succeeds" "$create_xdep_rc"
assert_contains "xdep child returns target absolute path" "$REAL_SISTER_ROOT/aitasks/t100/t100_2_real_cross_dep_child.md" "$created_xdep_path"
assert_file_exists "xdep child file exists in sister" "$REAL_SISTER_ROOT/aitasks/t100/t100_2_real_cross_dep_child.md"
xdep_child_body=$(cat "$REAL_SISTER_ROOT/aitasks/t100/t100_2_real_cross_dep_child.md")
assert_contains "xdep child has xdeps" "xdeps: [7]" "$xdep_child_body"
assert_contains "xdep child has xdeprepo" "xdeprepo: local" "$xdep_child_body"
sister_status=$(git -C "$REAL_SISTER_ROOT" status --porcelain)
assert_eq "sister clean after xdep child create" "" "$sister_status"

# --- Summary ------------------------------------------------------------

echo
echo "===================="
echo "Passed: $PASS / $TOTAL"
[[ "$FAIL" -gt 0 ]] && echo "Failed: $FAIL"
echo "===================="
[[ "$FAIL" -eq 0 ]]
