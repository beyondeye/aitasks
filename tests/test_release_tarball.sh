#!/usr/bin/env bash
# test_release_tarball.sh - Smoke test for release tarball skill staging.
#
# Emulates the release.yml "Build skills directory" step and the install.sh
# install_skills() copy step against the current working tree, then asserts
# that helper skills (ait-git, task-workflow, user-file-select) and sub-docs
# (task-workflow/planning.md, aitask-qa/change-analysis.md, ...) survive both
# phases. Regression guard for the silent exclusion caused by an
# `aitask-*/` glob or a single-file `cp "$dir/SKILL.md" ...`.
#
# Run: bash tests/test_release_tarball.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

PASS=0
FAIL=0
TOTAL=0

assert_exists() {
    local desc="$1" path="$2"
    TOTAL=$((TOTAL + 1))
    if [[ -e "$path" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc"
        echo "  missing: $path"
    fi
}

TMP="$(mktemp -d -t aitasks_tarball_test_XXXXXX)"
trap "rm -rf '$TMP'" EXIT

# --- Phase 1: emulate release.yml "Build skills directory from .claude/skills" ---

mkdir -p "$TMP/skills"
for skill_dir in .claude/skills/*/; do
    skill_name="$(basename "$skill_dir")"
    cp -r "$skill_dir" "$TMP/skills/$skill_name"
done

# Helper skills (previously excluded by `aitask-*/` glob).
assert_exists "tarball: ait-git/SKILL.md"          "$TMP/skills/ait-git/SKILL.md"
assert_exists "tarball: task-workflow/SKILL.md"    "$TMP/skills/task-workflow/SKILL.md"
assert_exists "tarball: user-file-select/SKILL.md" "$TMP/skills/user-file-select/SKILL.md"

# Sub-docs of task-workflow must travel with the directory copy.
assert_exists "tarball: task-workflow/planning.md"                    "$TMP/skills/task-workflow/planning.md"
assert_exists "tarball: task-workflow/task-creation-batch.md"         "$TMP/skills/task-workflow/task-creation-batch.md"
assert_exists "tarball: task-workflow/execution-profile-selection.md" "$TMP/skills/task-workflow/execution-profile-selection.md"
assert_exists "tarball: task-workflow/satisfaction-feedback.md"       "$TMP/skills/task-workflow/satisfaction-feedback.md"

# Sub-docs of aitask-qa (regression that existed even before the task-workflow fix).
assert_exists "tarball: aitask-qa/SKILL.md"            "$TMP/skills/aitask-qa/SKILL.md"
assert_exists "tarball: aitask-qa/change-analysis.md"  "$TMP/skills/aitask-qa/change-analysis.md"
assert_exists "tarball: aitask-qa/test-execution.md"   "$TMP/skills/aitask-qa/test-execution.md"

# Plain aitask-* skill still ships (no regression in the happy path).
assert_exists "tarball: aitask-pick/SKILL.md" "$TMP/skills/aitask-pick/SKILL.md"

# --- Phase 2: emulate install.sh install_skills() ---

mkdir -p "$TMP/target/.claude/skills"
for skill_dir in "$TMP/skills"/*/; do
    [[ -d "$skill_dir" ]] || continue
    skill_name="$(basename "$skill_dir")"
    mkdir -p "$TMP/target/.claude/skills/$skill_name"
    cp -r "$skill_dir". "$TMP/target/.claude/skills/$skill_name/"
done

# Same assertions at install target.
assert_exists "install: ait-git/SKILL.md"                              "$TMP/target/.claude/skills/ait-git/SKILL.md"
assert_exists "install: task-workflow/SKILL.md"                        "$TMP/target/.claude/skills/task-workflow/SKILL.md"
assert_exists "install: task-workflow/planning.md"                     "$TMP/target/.claude/skills/task-workflow/planning.md"
assert_exists "install: task-workflow/task-creation-batch.md"          "$TMP/target/.claude/skills/task-workflow/task-creation-batch.md"
assert_exists "install: task-workflow/execution-profile-selection.md"  "$TMP/target/.claude/skills/task-workflow/execution-profile-selection.md"
assert_exists "install: user-file-select/SKILL.md"                     "$TMP/target/.claude/skills/user-file-select/SKILL.md"
assert_exists "install: aitask-qa/change-analysis.md"                  "$TMP/target/.claude/skills/aitask-qa/change-analysis.md"
assert_exists "install: aitask-qa/test-execution.md"                   "$TMP/target/.claude/skills/aitask-qa/test-execution.md"
assert_exists "install: aitask-pick/SKILL.md"                          "$TMP/target/.claude/skills/aitask-pick/SKILL.md"

echo ""
echo "==================================================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
