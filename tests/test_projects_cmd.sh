#!/usr/bin/env bash
# test_projects_cmd.sh - Smoke round-trip for `ait projects` verbs
# (list / add / resolve / exec) using an isolated per-user index.
#
# Run: bash tests/test_projects_cmd.sh

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

# Build a fake aitasks project with a named project block.
ALPHA_ROOT="$TMPROOT/projects/alpha"
mkdir -p "$ALPHA_ROOT/aitasks/metadata"
cat > "$ALPHA_ROOT/aitasks/metadata/project_config.yaml" <<EOF
project:
  name: alpha
  git_remote: https://example.test/alpha.git
EOF

# Second project without a `project:` block — name should default to dir basename.
BETA_ROOT="$TMPROOT/projects/beta"
mkdir -p "$BETA_ROOT/aitasks/metadata"
touch "$BETA_ROOT/aitasks/metadata/project_config.yaml"

PROJECTS_SH="$PROJECT_DIR/.aitask-scripts/aitask_projects.sh"

# --- Tests --------------------------------------------------------------

# 1. list on empty index — emits an info-line, registry file untouched
out=$("$PROJECTS_SH" list 2>&1)
assert_contains "list on empty index reports no projects" "No registered projects" "$out"
TOTAL=$((TOTAL + 1))
if [[ ! -f "$REGISTRY_FILE" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: list on empty must not create the registry file"
fi

# 2. add alpha (with project_config block → name=alpha, remote captured)
"$PROJECTS_SH" add "$ALPHA_ROOT" >/dev/null 2>&1
[[ -f "$REGISTRY_FILE" ]] && PASS=$((PASS + 1)) || { FAIL=$((FAIL + 1)); echo "FAIL: registry file created"; }
TOTAL=$((TOTAL + 1))
body=$(cat "$REGISTRY_FILE")
assert_contains "add alpha: name in registry" "name: alpha" "$body"
assert_contains "add alpha: path in registry" "path: $ALPHA_ROOT" "$body"
assert_contains "add alpha: git_remote captured from project_config" \
    "git_remote: https://example.test/alpha.git" "$body"

# 3. add beta (no project_config block → name defaults to basename)
"$PROJECTS_SH" add "$BETA_ROOT" >/dev/null 2>&1
body=$(cat "$REGISTRY_FILE")
assert_contains "add beta: name defaults to basename" "name: beta" "$body"
assert_contains "add beta: path recorded" "path: $BETA_ROOT" "$body"

# 4. add alpha again → idempotent (still only one alpha entry)
"$PROJECTS_SH" add "$ALPHA_ROOT" >/dev/null 2>&1
count=$(grep -c '^  - name: alpha$' "$REGISTRY_FILE")
assert_eq "add is idempotent: exactly one alpha entry" "1" "$count"

# 5. list shows both entries (regardless of status)
out=$("$PROJECTS_SH" list 2>&1)
assert_contains "list shows alpha" "alpha" "$out"
assert_contains "list shows beta" "beta" "$out"

# 6. resolve round-trip
out=$("$PROJECTS_SH" resolve alpha)
assert_eq "resolve alpha" "RESOLVED:$ALPHA_ROOT" "$out"
out=$("$PROJECTS_SH" resolve beta)
assert_eq "resolve beta" "RESOLVED:$BETA_ROOT" "$out"
out=$("$PROJECTS_SH" resolve missing)
assert_eq "resolve NOT_FOUND" "NOT_FOUND:missing" "$out"

# 7. exec runs the command in the resolved root
out=$("$PROJECTS_SH" exec alpha -- pwd)
assert_eq "exec runs in resolved root" "$ALPHA_ROOT" "$out"

# 8. exec on NOT_FOUND fails non-zero
set +e
"$PROJECTS_SH" exec missing -- pwd >/dev/null 2>&1
rc=$?
set -e
TOTAL=$((TOTAL + 1))
if [[ "$rc" -ne 0 ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1)); echo "FAIL: exec on NOT_FOUND must exit non-zero"
fi

# --- 9. project-group (t1025_1) ----------------------------------------

# 9a. add gamma with a config project_group → bootstrapped into the registry.
GAMMA_ROOT="$TMPROOT/projects/gamma"
mkdir -p "$GAMMA_ROOT/aitasks/metadata"
cat > "$GAMMA_ROOT/aitasks/metadata/project_config.yaml" <<EOF
project:
  name: gamma
  project_group: suite_g
EOF
"$PROJECTS_SH" add "$GAMMA_ROOT" >/dev/null 2>&1
body=$(cat "$REGISTRY_FILE")
assert_contains "add gamma: project_group bootstrapped from config" \
    "project_group: suite_g" "$body"

# 9b. group list buckets members under their group + an (ungrouped) bucket.
out=$("$PROJECTS_SH" group list 2>&1)
assert_contains "group list: suite_g header" "suite_g:" "$out"
assert_contains "group list: gamma under a group" "gamma" "$out"
assert_contains "group list: (ungrouped) bucket for alpha/beta" "(ungrouped):" "$out"

# 9c. group set assigns alpha to a group.
"$PROJECTS_SH" group set alpha team_a >/dev/null 2>&1
assert_contains "group set alpha team_a" "project_group: team_a" "$(cat "$REGISTRY_FILE")"

# 9d. group set rejects an invalid slug (non-zero; registry unchanged).
set +e
out=$("$PROJECTS_SH" group set alpha "Bad Slug" 2>&1); rc=$?
set -e
assert_exit_nonzero_rc "group set rejects invalid slug" "$rc"
assert_contains "group set invalid-slug message" "Invalid project-group" "$out"
assert_contains "group set reject leaves alpha group unchanged" \
    "project_group: team_a" "$(cat "$REGISTRY_FILE")"

# 9e. group unset writes the explicit sentinel (so config can't re-inherit).
"$PROJECTS_SH" group unset gamma >/dev/null 2>&1
assert_contains "group unset writes sentinel" "project_group: -" "$(cat "$REGISTRY_FILE")"

# 9f. re-add gamma → registry sentinel WINS over the config's suite_g (D1).
"$PROJECTS_SH" add "$GAMMA_ROOT" >/dev/null 2>&1
gamma_block=$(awk '/^  - name: gamma$/{f=1} f&&/project_group:/{print; exit}' "$REGISTRY_FILE")
assert_eq "re-add preserves the unset sentinel (registry wins)" \
    "    project_group: -" "$gamma_block"

# 9g. update repoints alpha's path → its group must survive the rewrite.
ALPHA2_ROOT="$TMPROOT/projects/alpha2"
mkdir -p "$ALPHA2_ROOT/aitasks/metadata"
touch "$ALPHA2_ROOT/aitasks/metadata/project_config.yaml"
"$PROJECTS_SH" update alpha "$ALPHA2_ROOT" >/dev/null 2>&1
assert_contains "update preserves alpha's project_group" \
    "project_group: team_a" "$(cat "$REGISTRY_FILE")"

# 9h. remove an unrelated entry → surviving groups untouched.
"$PROJECTS_SH" remove beta --force >/dev/null 2>&1
body=$(cat "$REGISTRY_FILE")
assert_contains "remove preserves alpha's group" "project_group: team_a" "$body"
assert_contains "remove preserves gamma's sentinel" "project_group: -" "$body"

# 9i. group sync backfills an absent registry group from a repo config.
DELTA_ROOT="$TMPROOT/projects/delta"
mkdir -p "$DELTA_ROOT/aitasks/metadata"
touch "$DELTA_ROOT/aitasks/metadata/project_config.yaml"   # no group yet
"$PROJECTS_SH" add "$DELTA_ROOT" >/dev/null 2>&1
cat > "$DELTA_ROOT/aitasks/metadata/project_config.yaml" <<EOF
project:
  name: delta
  project_group: suite_d
EOF
"$PROJECTS_SH" group sync >/dev/null 2>&1
assert_contains "group sync backfills delta from config" \
    "project_group: suite_d" "$(cat "$REGISTRY_FILE")"

# 9j. add rejects an invalid config project_group (D4).
EPS_ROOT="$TMPROOT/projects/epsilon"
mkdir -p "$EPS_ROOT/aitasks/metadata"
cat > "$EPS_ROOT/aitasks/metadata/project_config.yaml" <<EOF
project:
  name: epsilon
  project_group: Bad Slug
EOF
set +e
out=$("$PROJECTS_SH" add "$EPS_ROOT" 2>&1); rc=$?
set -e
assert_exit_nonzero_rc "add rejects invalid config project_group" "$rc"
assert_contains "add invalid-config-group message names the value" "Bad Slug" "$out"

# 9k. group rename rewrites every member of a group in one pass (t1025_3).
"$PROJECTS_SH" group set alpha grp_x >/dev/null 2>&1
"$PROJECTS_SH" group set delta grp_x >/dev/null 2>&1
"$PROJECTS_SH" group rename grp_x grp_y >/dev/null 2>&1
body=$(cat "$REGISTRY_FILE")
assert_eq "rename moves both members to grp_y" \
    "2" "$(grep -c 'project_group: grp_y' "$REGISTRY_FILE")"
assert_not_contains "rename leaves no grp_x rows behind" "project_group: grp_x" "$body"

# 9l. rename into an EXISTING slug merges the two groups.
"$PROJECTS_SH" group set gamma grp_z >/dev/null 2>&1
"$PROJECTS_SH" group rename grp_z grp_y >/dev/null 2>&1
body=$(cat "$REGISTRY_FILE")
assert_eq "rename-into-existing merges (3 members now in grp_y)" \
    "3" "$(grep -c 'project_group: grp_y' "$REGISTRY_FILE")"
assert_not_contains "merge consumes the source group grp_z" "project_group: grp_z" "$body"

# 9m. rename rejects an invalid new slug (non-zero; registry unchanged).
set +e
out=$("$PROJECTS_SH" group rename grp_y "Bad Slug" 2>&1); rc=$?
set -e
assert_exit_nonzero_rc "group rename rejects invalid new slug" "$rc"
assert_contains "rename invalid-slug message" "Invalid project-group" "$out"
assert_eq "rename reject leaves grp_y intact" \
    "3" "$(grep -c 'project_group: grp_y' "$REGISTRY_FILE")"

# 9n. renaming a non-existent group errors (nothing rewritten).
set +e
out=$("$PROJECTS_SH" group rename no_such_group grp_q 2>&1); rc=$?
set -e
assert_exit_nonzero_rc "group rename of a missing group exits non-zero" "$rc"
assert_contains "rename missing-group message" "No registered project has group" "$out"

# 9o. rename preserves every other field of a rewritten row (only field 5 changes).
assert_contains "rename preserves alpha's repointed path" "path: $ALPHA2_ROOT" \
    "$(cat "$REGISTRY_FILE")"

# --- Summary ------------------------------------------------------------

echo
echo "===================="
echo "Passed: $PASS / $TOTAL"
[[ "$FAIL" -gt 0 ]] && echo "Failed: $FAIL"
echo "===================="
[[ "$FAIL" -eq 0 ]]
