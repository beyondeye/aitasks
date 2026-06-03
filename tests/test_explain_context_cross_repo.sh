#!/usr/bin/env bash
# test_explain_context_cross_repo.sh - Cross-repo --project support and
# aitasks#path notation on aitask_explain_context.sh (t832_2).
#
# Strategy: build two fake aitasks projects with pre-populated caches under
# their own .aitask-explain/codebrowser/ trees, register both in a temp
# AITASKS_PROJECTS_INDEX, then invoke the real orchestrator script and
# assert it produces ONE unified markdown blob spanning both projects and
# does NOT touch the caller's CWD for cache writes.
#
# The pre-populated cache approach mirrors test_explain_context.sh Test 7
# (setup_cache) — it avoids depending on the full extract pipeline being
# runnable inside the test harness.
#
# Run: bash tests/test_explain_context_cross_repo.sh

set -e

SCRIPT_DIR_T="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR_T/.." && pwd)"
SCRIPT="$PROJECT_DIR/.aitask-scripts/aitask_explain_context.sh"

PASS=0
FAIL=0
TOTAL=0

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"

assert_exists() {
    local desc="$1" pattern="$2"
    TOTAL=$((TOTAL + 1))
    # shellcheck disable=SC2086
    if ls -d $pattern >/dev/null 2>&1; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (no match for: $pattern)"
    fi
}

assert_not_exists() {
    local desc="$1" pattern="$2"
    TOTAL=$((TOTAL + 1))
    # shellcheck disable=SC2086
    if ls -d $pattern >/dev/null 2>&1; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (unexpected match for: $pattern)"
    else
        PASS=$((PASS + 1))
    fi
}

# --- Setup --------------------------------------------------------------

TMPROOT=$(mktemp -d "${TMPDIR:-/tmp}/explain_cross_XXXXXX")
trap 'rm -rf "$TMPROOT"' EXIT

# Two fake aitasks projects. Each gets the project_config.yaml marker
# (resolver validates by checking that file exists) and a pre-populated
# codebrowser cache with a unique plan we can grep for in the output.
build_project() {
    local root="$1" pname="$2" dir_key="$3" rel_path="$4" task_id="$5" plan_title="$6"
    mkdir -p "$root/aitasks/metadata"
    cat > "$root/aitasks/metadata/project_config.yaml" <<EOF
project:
  name: $pname
EOF

    local run_dir="$root/.aitask-explain/codebrowser/${dir_key}__20990101_120000"
    mkdir -p "$run_dir/plans"
    cat > "$run_dir/reference.yaml" <<EOF
files:
  - path: $rel_path
    line_ranges:
      - start: 1
        end: 50
        commits: [1]
        tasks: ["$task_id"]

tasks:
  - id: "$task_id"
    task_file: "tasks/t${task_id}.md"
    plan_file: "plans/p${task_id}.md"
EOF
    cat > "$run_dir/plans/p${task_id}.md" <<EOF
---
Task: t${task_id}_${pname}.md
---

# ${plan_title}

Marker line for project ${pname} (task ${task_id}).
EOF
}

PROJ_A="$TMPROOT/proj_a"
PROJ_B="$TMPROOT/proj_b"
build_project "$PROJ_A" "alpha" "src" "src/foo.py" "1001" "Alpha plan"
build_project "$PROJ_B" "beta"  "lib" "lib/bar.py" "2002" "Beta plan"

# Stale project — registered but the marker file is missing.
STALE_ROOT="$TMPROOT/stale"
mkdir -p "$STALE_ROOT"  # no aitasks/metadata/project_config.yaml

REGISTRY_FILE="$TMPROOT/projects.yaml"
cat > "$REGISTRY_FILE" <<EOF
projects:
  - name: alpha
    path: $PROJ_A
  - name: beta
    path: $PROJ_B
  - name: stale_one
    path: $STALE_ROOT
EOF
export AITASKS_PROJECTS_INDEX="$REGISTRY_FILE"

# Caller directory — proves the orchestrator stays put and per-project work
# does NOT pollute the caller's CWD with cache dirs.
CALLER="$TMPROOT/caller"
mkdir -p "$CALLER"

# --- Tests --------------------------------------------------------------

# 1. --project name:file form, two projects, unified output.
output=$(cd "$CALLER" && "$SCRIPT" --max-plans 1 \
    --project alpha:src/foo.py \
    --project beta:lib/bar.py 2>&1)
assert_contains "explicit pair: header present"   "## Historical Architectural Context" "$output"
assert_contains "explicit pair: alpha plan in output" "Alpha plan" "$output"
assert_contains "explicit pair: beta plan in output"  "Beta plan"  "$output"
assert_contains "explicit pair: alpha task id"   "1001" "$output"
assert_contains "explicit pair: beta task id"    "2002" "$output"

# 2. Caches stay inside each project tree; caller cwd is untouched.
assert_exists      "alpha cache lives in proj_a"  "$PROJ_A/.aitask-explain/codebrowser/src__"*
assert_exists      "beta cache lives in proj_b"   "$PROJ_B/.aitask-explain/codebrowser/lib__"*
assert_not_exists  "caller cwd has no cache dir"  "$CALLER/.aitask-explain"

# 3. aitasks#path notation produces equivalent output.
output2=$(cd "$CALLER" && "$SCRIPT" --max-plans 1 \
    alpha#src/foo.py \
    beta#lib/bar.py 2>&1)
assert_contains "hash notation: header present" "## Historical Architectural Context" "$output2"
assert_contains "hash notation: alpha plan"     "Alpha plan" "$output2"
assert_contains "hash notation: beta plan"      "Beta plan"  "$output2"

# 4. Mixed forms (one --project, one hash) work in the same call.
output3=$(cd "$CALLER" && "$SCRIPT" --max-plans 1 \
    --project alpha:src/foo.py \
    beta#lib/bar.py 2>&1)
assert_contains "mixed: alpha via --project" "Alpha plan" "$output3"
assert_contains "mixed: beta via #-notation" "Beta plan"  "$output3"

# 5. NOT_FOUND — unregistered project name surfaces hint and exits non-zero.
NF_OUT=$(cd "$CALLER" && "$SCRIPT" --max-plans 1 --project notreal_xxx:foo.py 2>&1 || true)
assert_contains "NOT_FOUND: hint surfaces" "is not registered" "$NF_OUT"
assert_exit_nonzero "NOT_FOUND: non-zero exit" \
    bash -c "cd '$CALLER' && AITASKS_PROJECTS_INDEX='$REGISTRY_FILE' '$SCRIPT' --max-plans 1 --project notreal_xxx:foo.py"

# 6. STALE — registered path missing the marker file surfaces hint.
ST_OUT=$(cd "$CALLER" && "$SCRIPT" --max-plans 1 --project stale_one:foo.py 2>&1 || true)
assert_contains "STALE: hint surfaces" "is stale" "$ST_OUT"
assert_exit_nonzero "STALE: non-zero exit" \
    bash -c "cd '$CALLER' && AITASKS_PROJECTS_INDEX='$REGISTRY_FILE' '$SCRIPT' --max-plans 1 --project stale_one:foo.py"

# 7. --project missing value.
NV_OUT=$(cd "$CALLER" && "$SCRIPT" --max-plans 1 --project 2>&1 || true)
assert_contains "missing --project value" "requires a value" "$NV_OUT"

# 8. --project without colon separator.
NC_OUT=$(cd "$CALLER" && "$SCRIPT" --max-plans 1 --project alphafoo 2>&1 || true)
assert_contains "--project without colon rejected" "requires <name>:<file>" "$NC_OUT"

# 9. --project with empty name or empty file.
EE_OUT=$(cd "$CALLER" && "$SCRIPT" --max-plans 1 --project :foo.py 2>&1 || true)
assert_contains "--project with empty name rejected" "non-empty name and file" "$EE_OUT"

# 10. Help text mentions new surfaces.
HELP=$("$SCRIPT" --help 2>&1)
assert_contains "help mentions --project"      "--project" "$HELP"
assert_contains "help mentions # notation"     "<name>#<path>" "$HELP"

# --- Summary ------------------------------------------------------------

echo
echo "===================="
echo "Passed: $PASS / $TOTAL"
[[ "$FAIL" -gt 0 ]] && echo "Failed: $FAIL"
echo "===================="
[[ "$FAIL" -eq 0 ]]
