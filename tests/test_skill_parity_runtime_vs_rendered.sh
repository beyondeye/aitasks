#!/usr/bin/env bash
# test_skill_parity_runtime_vs_rendered.sh - Parity test for t777_27.
#
# Asserts that for every profile-conditional branch in the pre-rewrite
# source (tests/fixtures/skills/), the current .j2-rendered output
# preserves the original behaviour for each branch of each profile key,
# including the implicit "ASK / fallback" case when a profile key is
# undefined (the `default` profile).
#
# Coverage:
#   - aitask-pick SKILL.md.j2 × {default,fast,remote}: skip_task_confirmation
#   - task-workflow SKILL.md × {default,fast,remote}: default_email,
#     create_worktree
#   - task-workflow planning.md × {default,fast,remote}: plan_preference,
#     post_plan_action
#   - task-workflow satisfaction-feedback.md × {default,fast,remote}:
#     enableFeedbackQuestions
#   - task-workflow manual-verification-followup.md × {default,fast,remote}:
#     manual_verification_followup_mode
#
# Coverage decisions (out of scope for individual rows but verified by
# the cross-check pass):
#   - base_branch: no profile sets it; all 3 renders keep the runtime
#     "Profile check" wrapper. Not differentiable per-profile.
#   - plan_verification_required, plan_verification_stale_after_hours,
#     post_plan_action_for_child, plan_preference_child: behaviour is
#     subsumed by plan_preference / post_plan_action rows (template
#     resolves both parent and child branches together).
#   - remote_drift_check: the remote-drift-check.md render is byte-
#     identical across all 3 profiles (profile check is runtime, not
#     template-conditional). No differentiable row.
#
# Render pattern matches tests/test_skill_render_task_workflow.sh: use
# skill_template.py directly (stdout render), not aitask_skill_render.sh
# (which only writes to .claude/skills/<skill>-<profile>-/ on disk and
# does not support --output-dir).
#
# Run: bash tests/test_skill_parity_runtime_vs_rendered.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

assert_contains() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if printf '%s' "$actual" | grep -qF -- "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc"
        echo "  expected (substring): $expected"
        echo "  rendered head (60 lines):"
        printf '%s\n' "$actual" | head -60 | sed 's/^/    /'
    fi
}

assert_not_contains() {
    local desc="$1" forbidden="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if printf '%s' "$actual" | grep -qF -- "$forbidden"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc"
        echo "  forbidden (substring): $forbidden"
    else
        PASS=$((PASS + 1))
    fi
}

cd "$PROJECT_DIR"

# shellcheck source=.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
PYTHON="$(require_ait_python)"
if ! "$PYTHON" -c 'import minijinja' 2>/dev/null; then
    echo "SKIP: minijinja not installed in framework venv ($PYTHON). Run 'ait setup' first."
    exit 0
fi

RENDER="$PYTHON $PROJECT_DIR/.aitask-scripts/lib/skill_template.py"

PICK_SKILL="$PROJECT_DIR/.claude/skills/aitask-pick/SKILL.md.j2"
WORKFLOW_DIR="$PROJECT_DIR/.claude/skills/task-workflow"
PROFILES_DIR="$PROJECT_DIR/aitasks/metadata/profiles"
FIXTURE_DIR="$PROJECT_DIR/tests/fixtures/skills"

# Verify fixtures are present (Phase 1 must have landed first)
if [[ ! -f "$FIXTURE_DIR/aitask-pick/SKILL.md.pre-rewrite" ]]; then
    echo "FAIL: missing fixture $FIXTURE_DIR/aitask-pick/SKILL.md.pre-rewrite"
    echo "      Run Phase 1 of t777_27 to land pre-rewrite fixtures."
    exit 1
fi
fixture_count=$(find "$FIXTURE_DIR/task-workflow" -name '*.pre-rewrite' | wc -l)
if [[ "$fixture_count" -ne 25 ]]; then
    echo "FAIL: expected 25 task-workflow fixtures, found $fixture_count"
    exit 1
fi

# render_file <abs-template-path> <profile-name>
render_file() {
    $RENDER "$1" "$PROFILES_DIR/$2.yaml" claude 2>&1
}

# Resolve template absolute path from row's SKILL+FILE columns.
template_path() {
    local skill="$1" file="$2"
    if [[ "$skill" == "aitask-pick" ]]; then
        echo "$PICK_SKILL"
    else
        echo "$WORKFLOW_DIR/$file"
    fi
}

# === Assertion table ===
#
# Row format: SKILL|FILE|PROFILE|FIXTURE_LINE|KEY|PRESENT|ABSENT|NOTE
#
# PRESENT and ABSENT are substring sentinels. ABSENT is the *complementary*
# sentinel (typically another profile's Display sentence) — not the fallback
# AskUserQuestion text, which can legitimately survive in the rendered
# output as an "if both are empty" fallback.

ROWS=(
    # --- aitask-pick / skip_task_confirmation (parent confirm site) ---
    "aitask-pick|SKILL.md.j2|fast|SKILL.md.j2:23|skip_task_confirmation|Profile 'fast': auto-confirming task selection|Is this the correct task"
    "aitask-pick|SKILL.md.j2|remote|SKILL.md.j2:23|skip_task_confirmation|Profile 'remote': auto-confirming task selection|Is this the correct task"
    "aitask-pick|SKILL.md.j2|default|SKILL.md.j2:23|skip_task_confirmation|Is this the correct task|Profile 'fast': auto-confirming task selection"

    # --- aitask-pick / skip_task_confirmation (child confirm site) ---
    "aitask-pick|SKILL.md.j2|fast|SKILL.md.j2:51|skip_task_confirmation|Profile 'fast': auto-confirming task selection|Brief summary: <1-2 sentence summary of the child task"
    "aitask-pick|SKILL.md.j2|remote|SKILL.md.j2:51|skip_task_confirmation|Profile 'remote': auto-confirming task selection|Brief summary: <1-2 sentence summary of the child task"

    # --- task-workflow SKILL.md / default_email ---
    "task-workflow|SKILL.md|fast|SKILL.md:96|default_email|Profile 'fast': using email|Profile 'remote': using email"
    "task-workflow|SKILL.md|remote|SKILL.md:96|default_email|Profile 'remote': using email|Profile 'fast': using email"
    "task-workflow|SKILL.md|default|SKILL.md:96|default_email|Enter your email to track who is working on this task|Profile 'fast': using email"

    # --- task-workflow SKILL.md / create_worktree ---
    # fast sets create_worktree:false → rendered to concrete branch
    # remote/default do not set create_worktree → render keeps runtime wrapper
    "task-workflow|SKILL.md|fast|SKILL.md:181|create_worktree|Profile 'fast': working on current branch|If the active profile has \`create_worktree\` set"
    "task-workflow|SKILL.md|remote|SKILL.md:181|create_worktree|If the active profile has \`create_worktree\` set|Profile 'fast': working on current branch"
    "task-workflow|SKILL.md|default|SKILL.md:181|create_worktree|If the active profile has \`create_worktree\` set|Profile 'fast': working on current branch"

    # --- task-workflow planning.md / plan_preference ---
    "task-workflow|planning.md|fast|planning.md:29|plan_preference|Profile 'fast': using existing plan|How would you like to proceed with the plan"
    "task-workflow|planning.md|remote|planning.md:29|plan_preference|Profile 'remote': using existing plan|How would you like to proceed with the plan"
    "task-workflow|planning.md|default|planning.md:29|plan_preference|An existing implementation plan was found at|Profile 'fast': using existing plan"

    # --- task-workflow planning.md / post_plan_action ---
    "task-workflow|planning.md|fast|planning.md:294|post_plan_action|Profile 'fast' configures the post-plan action|"
    "task-workflow|planning.md|remote|planning.md:294|post_plan_action|Profile 'remote': proceeding to implementation|Profile 'fast' configures the post-plan action"
    "task-workflow|planning.md|default|planning.md:294|post_plan_action|If the effective action is|Profile 'fast' configures the post-plan action"

    # --- task-workflow satisfaction-feedback.md / enableFeedbackQuestions ---
    "task-workflow|satisfaction-feedback.md|fast|sf.md:34|enableFeedbackQuestions|Profile 'fast' sets \`enableFeedbackQuestions: true\`. Continue with step 2 (no skip)|Profile 'remote': feedback questions disabled"
    "task-workflow|satisfaction-feedback.md|remote|sf.md:34|enableFeedbackQuestions|Profile 'remote' sets \`enableFeedbackQuestions: false\`|Profile 'fast' sets \`enableFeedbackQuestions: true\`"
    "task-workflow|satisfaction-feedback.md|default|sf.md:34|enableFeedbackQuestions|Profile check:|Profile 'fast' sets \`enableFeedbackQuestions: true\`"

    # --- task-workflow manual-verification-followup.md / manual_verification_followup_mode ---
    "task-workflow|manual-verification-followup.md|fast|mvf.md:34|manual_verification_followup_mode|Profile 'fast' sets \`manual_verification_followup_mode: ask\`. Continue with step 2 (no skip)|Profile 'remote' sets \`manual_verification_followup_mode: never\`"
    "task-workflow|manual-verification-followup.md|remote|mvf.md:34|manual_verification_followup_mode|Profile 'remote' sets \`manual_verification_followup_mode: never\`|Profile 'fast' sets \`manual_verification_followup_mode: ask\`"
    "task-workflow|manual-verification-followup.md|default|mvf.md:34|manual_verification_followup_mode|If the active profile has \`manual_verification_followup_mode\` set to|Profile 'default' sets \`manual_verification_followup_mode: never\`"
)

echo "=== Per-row parity assertions ==="
for ROW in "${ROWS[@]}"; do
    IFS='|' read -r SKILL FILE PROFILE FIXTURE_LINE KEY PRESENT ABSENT _NOTE <<<"$ROW"
    TEMPLATE="$(template_path "$SKILL" "$FILE")"
    RENDERED="$(render_file "$TEMPLATE" "$PROFILE")"
    DESC="$SKILL/$FILE/$PROFILE key=$KEY (fixture:$FIXTURE_LINE)"

    [[ -n "$PRESENT" ]] && assert_contains "$DESC present"  "$PRESENT" "$RENDERED"
    [[ -n "$ABSENT"  ]] && assert_not_contains "$DESC absent" "$ABSENT"  "$RENDERED"
done

# === Cross-check pass: every pre-rewrite conditional has at least one
# render arm in some profile. ===
#
# For each pre-rewrite fixture file under a row's SKILL+FILE, scan for
# guard sentences ("If the active profile…", "Profile check:",
# "If the effective action is…"). For each match, build the union of
# PRESENT sentinels covering that fixture file across all rows, and
# require that at least one of them appears in some profile's render.
#
# This catches the failure mode where a template author deletes both
# arms of a conditional by accident.

echo "=== Cross-check: each fixture guard has a render arm ==="
declare -A PRESENT_BY_FILE
for ROW in "${ROWS[@]}"; do
    IFS='|' read -r SKILL FILE _PROFILE _FL _K PRESENT _A _N <<<"$ROW"
    [[ -z "$PRESENT" ]] && continue
    key="$SKILL/$FILE"
    PRESENT_BY_FILE["$key"]+="${PRESENT}"$'\n'
done

# Determine each fixture file's path on disk
fixture_path() {
    local skill="$1" file="$2"
    if [[ "$skill" == "aitask-pick" ]]; then
        echo "$FIXTURE_DIR/aitask-pick/SKILL.md.pre-rewrite"
    else
        echo "$FIXTURE_DIR/task-workflow/${file}.pre-rewrite"
    fi
}

# Each unique SKILL/FILE pair in the ROWS table
declare -A SEEN_FILES
for ROW in "${ROWS[@]}"; do
    IFS='|' read -r SKILL FILE _REST <<<"$ROW"
    key="$SKILL/$FILE"
    [[ -n "${SEEN_FILES[$key]:-}" ]] && continue
    SEEN_FILES["$key"]=1

    FX="$(fixture_path "$SKILL" "$FILE")"
    if [[ ! -f "$FX" ]]; then
        TOTAL=$((TOTAL + 1)); FAIL=$((FAIL + 1))
        echo "FAIL: cross-check fixture missing: $FX"
        continue
    fi

    # Count guard sentences in the fixture
    guard_count=$(grep -cE 'If the active profile|Profile check[.:]|If the effective action is' "$FX" || true)
    if [[ "$guard_count" -eq 0 ]]; then
        # No guards in this fixture; nothing to cross-check.
        continue
    fi

    # Render in all 3 profiles and look for any of this file's PRESENT sentinels
    union_present="${PRESENT_BY_FILE[$key]:-}"
    if [[ -z "$union_present" ]]; then
        TOTAL=$((TOTAL + 1)); FAIL=$((FAIL + 1))
        echo "FAIL: cross-check has no PRESENT sentinels for $key (guards=$guard_count)"
        continue
    fi

    TEMPLATE="$(template_path "$SKILL" "$FILE")"
    found_any=0
    for prof in default fast remote; do
        rendered="$(render_file "$TEMPLATE" "$prof")"
        while IFS= read -r sent; do
            [[ -z "$sent" ]] && continue
            if printf '%s' "$rendered" | grep -qF -- "$sent"; then
                found_any=1; break
            fi
        done <<<"$union_present"
        [[ "$found_any" -eq 1 ]] && break
    done

    TOTAL=$((TOTAL + 1))
    if [[ "$found_any" -eq 1 ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: cross-check $key has $guard_count guard(s) in fixture but no row sentinel matched any profile render"
    fi
done

# === No-leak assertion (replicated invariant) ===

echo "=== No Jinja markers leak into any rendered output ==="
LEAK_FILES=(
    "$PICK_SKILL"
    "$WORKFLOW_DIR/SKILL.md"
    "$WORKFLOW_DIR/planning.md"
    "$WORKFLOW_DIR/satisfaction-feedback.md"
    "$WORKFLOW_DIR/manual-verification-followup.md"
    "$WORKFLOW_DIR/remote-drift-check.md"
)
for tmpl in "${LEAK_FILES[@]}"; do
    for prof in default fast remote; do
        out="$(render_file "$tmpl" "$prof")"
        rel="${tmpl#"$PROJECT_DIR"/}"
        assert_not_contains "$rel × $prof: no {% leak" "{%" "$out"
        assert_not_contains "$rel × $prof: no {{ leak" "{{" "$out"
    done
done

echo ""
echo "=========================================="
echo "Total: $TOTAL  Pass: $PASS  Fail: $FAIL"
echo "=========================================="
[[ "$FAIL" -eq 0 ]]
