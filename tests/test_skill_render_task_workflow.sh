#!/usr/bin/env bash
# test_skill_render_task_workflow.sh - Regression tests for the wrapped
# shared workflow under .claude/skills/task-workflow/:
#   - the wrapped .md files under it (profile-varying + profile-invariant)
#   - their goldens under tests/golden/procs/task-workflow/
#
# The inventory and the counts are NOT stated here: Test 0 derives both from
# disk and fails when they disagree with the arrays below. Prose counts went
# stale silently; an assertion cannot.
# Coverage:
#   0.  Every Jinja-bearing workflow file is listed, no file is in both arrays,
#       every listed file exists and has its goldens, and no golden is orphaned.
#   1.  Per-(file, profile) golden diff for the profile-varying wrapped
#       files × 3 profiles.
#   1b. remote-drift-check is profile-invariant — a single canonical golden
#       plus a byte-equality assertion across all 3 profile renders.
#   2. Agent byte-identity: rendering SKILL.md with profile=fast across all
#      4 agents yields byte-identical output (task-workflow uses only
#      sibling refs, which the dep-walker leaves unchanged regardless of
#      --agent).
#   3. default-profile renders contain the original AskUserQuestion blocks
#      verbatim (no key is defined → all guards fall through to {% else %}).
#   4. remote_drift_check synthetic profile demonstrates the true branch
#      fires when the key is defined (no committed profile uses it).
#   5. risk steps are profile-invariant + runtime-gated (t635_14): the planning
#      eval step + mitigation design, SKILL.md two-field write + "before"/Step-8d
#      "after" creation, and the gate-declaration backfill render in EVERY
#      profile (the old `risk_evaluation` toggle is gone — they are gated at
#      runtime via aitask_gate.sh effective-gates / has-gates-field).
# Run: bash tests/test_skill_render_task_workflow.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"

cd "$PROJECT_DIR"

# shellcheck source=.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
PYTHON="$(require_ait_python)"
if ! "$PYTHON" -c 'import minijinja' 2>/dev/null; then
    echo "SKIP: minijinja not installed in framework venv ($PYTHON). Run 'ait setup' first."
    exit 0
fi

RENDER="$PYTHON $PROJECT_DIR/.aitask-scripts/lib/skill_template.py"
WORKFLOW_DIR=".claude/skills/task-workflow"
GOLDEN_DIR="tests/golden/procs/task-workflow"
PROFILES_DIR="aitasks/metadata/profiles"

# remote-drift-check is profile-invariant (its conditional is activated only
# by a synthetic profile — see Test 4), so it keeps one canonical golden.
WRAPPED_FILES_VARYING=(
    "SKILL.md"
    "planning.md"
    "plan-approved-stop.md"
    "manual-verification.md"
    "manual-verification-followup.md"
    "auto-verification.md"
    "satisfaction-feedback.md"
    # The shared creation contract. Profile-varying via the default_gates
    # injection: `fast` renders `--gates "risk_evaluated"` into both command
    # forms, `default` and `remote` render neither. Added in t1468_2 — it had no
    # golden at all until then, so template drift in the one file every
    # task-creating seam routes through was invisible to this suite.
    "task-creation-batch.md"
    # The advisory parallel-admission preflight (t1569_4).
    #
    # All three committed profiles ship `parallel_admission: "off"` (56% of
    # in-flight tasks carry no plan, so the check is opted out until the
    # in-flight surface gains a task-body fallback), and `off` renders the whole
    # step away. The three renders are therefore the SAME no-op body differing
    # only in the interpolated profile name -- which is exactly what makes them
    # worth pinning per profile: the golden is where "this profile opted out" is
    # recorded, so silently re-enabling one shows up as a golden diff.
    #
    # The `warn` and `confirm` bodies have no committed profile at all, exactly
    # like remote-drift-check's `skip`. Test 4e drives both through synthetic
    # profiles, which is their only executable coverage.
    "parallel-admission.md"
)
WRAPPED_FILES_INVARIANT=(
    "remote-drift-check.md"
    # The Step 9 merge broker control flow (t1560_2). Profile-invariant: the
    # verdict dispositions are the same under every profile, and Step 9's only
    # profile conditionals (record_gates) stayed in SKILL.md.
    "merge-broker.md"
    "planning-cross-repo.md"
    "cross-repo-child-assignment.md"
    "risk-evaluation.md"
    "risk-mitigation-followup.md"
    "gate-recording.md"
    # The legacy (non-gate) build-verification decision flow (t1610). Shared by
    # task-workflow Step 9, aitask-pickrem and aitask-pickweb, so it carries no
    # profile conditionals of its own -- the record_gates guard stayed in
    # SKILL.md, where the recording lives.
    "build-verification.md"
    # The Step-7 resource-admission seam (t1597). Profile-invariant by design,
    # not by accident: whether a host can afford the implementation phase must
    # not vary with how chatty a profile is, so the procedure carries no profile
    # conditional and ships no knob -- an unset `resource_admission_command` is
    # the opt-out.
    "resource-admission.md"
)
PROFILES=(default fast remote)
AGENTS=(claude codex opencode)

# === Test 0: the two arrays ARE the inventory, and every file has its goldens ===
#
# The header used to state the counts in prose ("17 wrapped .md files", "33
# golden files"). Prose cannot fail, so a procedure added to the workflow dir and
# forgotten here was covered by nothing and drifted silently — which is exactly
# what this file exists to prevent. Assert the two facts instead of narrating
# them (t1569_4 pre-phase mitigation `pin_procedure_and_golden_inventory`):
#
#   1. Every Jinja-bearing file in .claude/skills/task-workflow/ is listed in one
#      of the two arrays (containment — see the note at the assertion), and every
#      listed name still exists.
#   2. Every listed file has its expected goldens on disk: 3 for a varying file
#      (one per profile), 1 canonical -default for an invariant one — and no
#      golden is orphaned.
#
# Counts are DERIVED here rather than restated, so this test never needs editing
# when a file is added — only the arrays do, which is the point.

echo "=== Test 0: wrapped-file inventory and golden coverage ==="

listed_files="$(printf '%s\n' "${WRAPPED_FILES_VARYING[@]}" "${WRAPPED_FILES_INVARIANT[@]}" | sort)"

# CONTAINMENT, not equality. The workflow dir holds ~36 .md files; most carry no
# Jinja and need no golden, and a few (auto-verification.md) vary through a
# resolved sibling ref rather than a conditional of their own. The load-bearing
# direction is one-way: a file that CONTAINS Jinja has profile-conditional
# output, so leaving it off both arrays means its branches are goldened by
# nothing. That is the drift this catches.
unlisted_jinja=""
for f in "$WORKFLOW_DIR"/*.md; do
    n="$(basename "$f")"
    grep -qE '\{%|\{\{' "$f" || continue
    printf '%s\n' "$listed_files" | grep -qxF "$n" || unlisted_jinja+="$n "
done
assert_eq "every profile-conditional (Jinja-bearing) file is listed" "" "$unlisted_jinja"

# And the inverse: an array entry whose file is gone is a stale name that would
# make every loop below read a nonexistent path.
missing_files=""
while IFS= read -r n; do
    [[ -z "$n" ]] && continue
    [[ -f "$WORKFLOW_DIR/$n" ]] || missing_files+="$n "
done <<< "$listed_files"
assert_eq "every listed file exists in the workflow dir" "" "$missing_files"

# A file in BOTH arrays would be rendered twice against contradictory
# expectations; the union above cannot see that, so check it separately.
dupes="$(printf '%s\n' "${WRAPPED_FILES_VARYING[@]}" "${WRAPPED_FILES_INVARIANT[@]}" \
    | sort | uniq -d)"
assert_eq "no file is listed as both varying and invariant" "" "$dupes"

missing_goldens=""
for file in "${WRAPPED_FILES_VARYING[@]}"; do
    stem="${file%.md}"
    for profile in "${PROFILES[@]}"; do
        [[ -f "$GOLDEN_DIR/${stem}-${profile}.md" ]] ||
            missing_goldens+="${stem}-${profile}.md "
    done
done
for file in "${WRAPPED_FILES_INVARIANT[@]}"; do
    stem="${file%.md}"
    [[ -f "$GOLDEN_DIR/${stem}-default.md" ]] || missing_goldens+="${stem}-default.md "
done
assert_eq "every listed wrapped file has its goldens on disk" "" "$missing_goldens"

# The inverse: a golden with no owning file is a leftover from a deleted
# procedure, and would sit unread forever.
expected_goldens="$( { for f in "${WRAPPED_FILES_VARYING[@]}"; do
                          for p in "${PROFILES[@]}"; do echo "${f%.md}-${p}.md"; done
                      done
                      for f in "${WRAPPED_FILES_INVARIANT[@]}"; do
                          echo "${f%.md}-default.md"
                      done; } | sort)"
actual_goldens="$(find "$GOLDEN_DIR" -maxdepth 1 -name '*.md' -printf '%f\n' | sort)"
assert_eq "no orphan goldens" "$expected_goldens" "$actual_goldens"

# === Test 1: Per-(file, profile) golden diff (profile-varying files) ===

echo "=== Test 1: golden diffs for ${#WRAPPED_FILES_VARYING[@]} profile-varying wrapped files × ${#PROFILES[@]} profiles ==="
for file in "${WRAPPED_FILES_VARYING[@]}"; do
    stem="${file%.md}"
    for profile in "${PROFILES[@]}"; do
        rendered="$($RENDER "$WORKFLOW_DIR/$file" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
        golden_path="$GOLDEN_DIR/${stem}-${profile}.md"
        golden_content="$(cat "$golden_path")"
        assert_eq "golden $stem × $profile" "$golden_content" "$rendered"
    done
done

# === Test 1b: profile-invariant wrapped files — canonical golden + invariance ===
#
# remote-drift-check's profile conditional is activated only by a synthetic
# profile (Test 4), so all 3 committed-profile renders are byte-identical.
# One canonical -default golden replaces the 2 deleted profile dupes; the
# invariance assertion fails LOUDLY if a committed profile ever diverges it.
echo "=== Test 1b: profile-invariant wrapped files — canonical golden + invariance ==="
for file in "${WRAPPED_FILES_INVARIANT[@]}"; do
    stem="${file%.md}"
    base="$($RENDER "$WORKFLOW_DIR/$file" "$PROFILES_DIR/default.yaml" claude 2>&1)"
    golden_content="$(cat "$GOLDEN_DIR/${stem}-default.md")"
    assert_eq "golden $stem (canonical)" "$golden_content" "$base"
    for profile in "${PROFILES[@]}"; do
        rendered="$($RENDER "$WORKFLOW_DIR/$file" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
        assert_eq "$stem profile-invariant ($profile==default)" "$base" "$rendered"
    done
done

# === Test 2: Agent byte-identity (task-workflow has only sibling refs) ===

echo "=== Test 2: agent byte-identity for SKILL.md @ profile=fast ==="
REF_OUT="$($RENDER "$WORKFLOW_DIR/SKILL.md" "$PROFILES_DIR/fast.yaml" claude 2>&1)"
for agent in "${AGENTS[@]}"; do
    out="$($RENDER "$WORKFLOW_DIR/SKILL.md" "$PROFILES_DIR/fast.yaml" "$agent" 2>&1)"
    if [[ "$out" == "$REF_OUT" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: SKILL.md fast render differs for agent=$agent vs claude"
    fi
    TOTAL=$((TOTAL + 1))
done

# === Test 2b: agent byte-identity for planning.md @ profile=fast (t818) ===
# The shared {% include "_plan_contract.md" %} resolves agent-agnostically
# (the include target is markdown, not a refs-bearing template), so the
# rendered planning.md is identical across all 4 agent trees.
echo "=== Test 2b: agent byte-identity for planning.md @ profile=fast ==="
REF_PLAN="$($RENDER "$WORKFLOW_DIR/planning.md" "$PROFILES_DIR/fast.yaml" claude 2>&1)"
for agent in "${AGENTS[@]}"; do
    out="$($RENDER "$WORKFLOW_DIR/planning.md" "$PROFILES_DIR/fast.yaml" "$agent" 2>&1)"
    if [[ "$out" == "$REF_PLAN" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: planning.md fast render differs for agent=$agent vs claude"
    fi
    TOTAL=$((TOTAL + 1))
done

# === Test 2c: planning.md resolves _planning_plan_contract.md (t818) ===
# Verifies the {% include "_planning_plan_contract.md" %} directive resolves
# through the extended minijinja loader path (search dir =
# .aitask-scripts/skill_templates/). The fragment is the planning-specific
# single-level "Detailed" spec. Catches regressions where the include target
# moves or the loader path config drifts.
echo "=== Test 2c: planning.md embeds resolved _planning_plan_contract.md ==="
for profile in "${PROFILES[@]}"; do
    rendered="$($RENDER "$WORKFLOW_DIR/planning.md" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    assert_contains "planning.md $profile: planning spec present" \
        'Create a detailed, step-by-step implementation plan. "Detailed" means:' "$rendered"
    assert_contains "planning.md $profile: planning spec continuation present" \
        "code snippets for non-trivial modifications" "$rendered"
    assert_not_contains "planning.md $profile: no literal include tag survives" \
        '{% include' "$rendered"
done

# === Test 3: default profile preserves all AskUserQuestion blocks ===

echo "=== Test 3: default profile keeps existing interactive prose ==="
DEFAULT_SKILL="$($RENDER "$WORKFLOW_DIR/SKILL.md" "$PROFILES_DIR/default.yaml" claude 2>&1)"
assert_contains "SKILL.md default: create_worktree AskUserQuestion present" \
    'Do you want to create a separate branch and worktree for this task?' "$DEFAULT_SKILL"
# t1558: the deferral must live INSIDE the question text. Step 5 only resolves
# the fork; Step 7 cuts it. A user who believes the worktree already exists
# misreads every later stop path (drift stop, approve-and-stop, decomposed
# parent) -- which is the misreading t1536's wording change exists to prevent.
assert_contains "SKILL.md default: create_worktree question states the deferral" \
    'Nothing is created now — the branch and worktree are cut at the start of implementation' "$DEFAULT_SKILL"
assert_not_contains "SKILL.md default: no creating-now claim" \
    "': creating worktree" "$DEFAULT_SKILL"
assert_contains "SKILL.md default: base_branch AskUserQuestion present" \
    'Which branch should the new task branch be based on?' "$DEFAULT_SKILL"
assert_contains "SKILL.md default: default_email AskUserQuestion present" \
    'Enter your email to track who is working on this task' "$DEFAULT_SKILL"
# output_branch has NO interactive question by design: unset means "merge into
# the resolved base branch", so the fallback is silent (t1233).
assert_contains "SKILL.md default: output_branch fallback prose present" \
    'the merge target is the base branch resolved above' "$DEFAULT_SKILL"
assert_not_contains "SKILL.md default: output_branch adds no AskUserQuestion" \
    'Which branch should the finished work be merged into' "$DEFAULT_SKILL"

DEFAULT_PLAN="$($RENDER "$WORKFLOW_DIR/planning.md" "$PROFILES_DIR/default.yaml" claude 2>&1)"
assert_contains "planning.md default: plan_preference AskUserQuestion present" \
    'An existing implementation plan was found at' "$DEFAULT_PLAN"
assert_contains "planning.md default: post_plan_action AskUserQuestion present" \
    'Plan saved to' "$DEFAULT_PLAN"

DEFAULT_MVF="$($RENDER "$WORKFLOW_DIR/manual-verification-followup.md" "$PROFILES_DIR/default.yaml" claude 2>&1)"
assert_contains "manual-verification-followup default: 'never' guidance present" \
    'manual_verification_followup_mode' "$DEFAULT_MVF"

DEFAULT_RDC="$($RENDER "$WORKFLOW_DIR/remote-drift-check.md" "$PROFILES_DIR/default.yaml" claude 2>&1)"
assert_contains "remote-drift-check default: 'skip' fallback prose present" \
    'remote_drift_check: skip' "$DEFAULT_RDC"

DEFAULT_SF="$($RENDER "$WORKFLOW_DIR/satisfaction-feedback.md" "$PROFILES_DIR/default.yaml" claude 2>&1)"
assert_contains "satisfaction-feedback default: enableFeedbackQuestions prose present" \
    'If `enableFeedbackQuestions` is omitted' "$DEFAULT_SF"

# === Test 3b: rendered SKILL.md must NOT include Step 3b refresh (t777_26) ===

echo "=== Test 3b: SKILL.md rendered output has no Step 3b refresh ==="
for profile in "${PROFILES[@]}"; do
    rendered="$($RENDER "$WORKFLOW_DIR/SKILL.md" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    assert_not_contains "SKILL.md $profile: no Step 3b heading" \
        "Step 3b: refresh execution profile" "$rendered"
    assert_not_contains "SKILL.md $profile: no scan-profiles call" \
        "aitask_scan_profiles.sh" "$rendered"
    assert_not_contains "SKILL.md $profile: no refresh profile prose" \
        "refresh execution profile" "$rendered"
done

# === Test 4: synthetic profile with remote_drift_check: skip fires the true branch ===

echo "=== Test 4: synthetic remote_drift_check: skip profile ==="
TMP_PROFILE="$(mktemp "${TMPDIR:-/tmp}/test_rdc_XXXXXX.yaml")"
trap 'rm -f "$TMP_PROFILE"' EXIT
cat > "$TMP_PROFILE" <<'YAML'
name: test_rdc_skip
description: "Synthetic profile for t777_7 test (remote_drift_check skip)"
remote_drift_check: skip
YAML
SYNTH_OUT="$($RENDER "$WORKFLOW_DIR/remote-drift-check.md" "$TMP_PROFILE" claude 2>&1)"
assert_contains "synthetic profile triggers true branch (return immediately)" \
    "Profile 'test_rdc_skip' sets" "$SYNTH_OUT"
assert_not_contains "synthetic profile suppresses fallback prose" \
    '**Profile check.** If the active profile has' "$SYNTH_OUT"

# === Test 4b: synthetic profile with output_branch bakes the value (t1233) ===

echo "=== Test 4b: synthetic output_branch profile ==="
TMP_OB_PROFILE="$(mktemp "${TMPDIR:-/tmp}/test_ob_XXXXXX.yaml")"
cat > "$TMP_OB_PROFILE" <<'YAML'
name: test_output_branch
description: "Synthetic profile for t1233 (output_branch)"
create_worktree: true
base_branch: main
output_branch: dev
YAML
OB_OUT="$($RENDER "$WORKFLOW_DIR/SKILL.md" "$TMP_OB_PROFILE" claude 2>&1)"
assert_contains "output_branch profile bakes the resolved value" \
    "Profile 'test_output_branch': using output branch dev" "$OB_OUT"
assert_not_contains "output_branch profile suppresses the fallback prose" \
    'the merge target is the base branch resolved above' "$OB_OUT"
# t1558: this synthetic profile also sets create_worktree: true, which is the
# ONLY way to render the baked worktree-mode branch -- no committed profile
# defines create_worktree: true, so that branch has no golden and this is its
# sole executable coverage.
assert_contains "create_worktree: true bakes the deferral into the display line" \
    "Profile 'test_output_branch': worktree mode — the branch and worktree are created after plan approval and the remote drift check, not now." "$OB_OUT"
assert_not_contains "create_worktree: true makes no creating-now claim" \
    "': creating worktree" "$OB_OUT"
# Step 9 consumes the plan header at runtime, so it must stay profile-invariant:
# no profile ever bakes a literal merge target into the checkout.
# Line-anchored: the pre-flight PROSE legitimately mentions `git checkout dev`
# when explaining the tag/detached-HEAD trap, so a substring check would collide
# with it. What must never happen is the checkout COMMAND baking a literal.
baked_checkout=$(printf '%s\n' "$OB_OUT" | grep -cE '^[[:space:]]*git checkout dev$' || true)
assert_eq "Step 9 never bakes a literal merge target into the checkout command" \
    "0" "$baked_checkout"
assert_contains "Step 9 consumes the validated shell variable, not the profile value" \
    'the bound `$output_branch`' "$OB_OUT"
rm -f "$TMP_OB_PROFILE"

# === Test 4c: the hardcoded `main` merge target is gone from every render ===

echo "=== Test 4c: no hardcoded main merge target (t1233) ==="
for profile in "${PROFILES[@]}"; do
    rendered="$($RENDER "$WORKFLOW_DIR/SKILL.md" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    assert_not_contains "SKILL.md $profile: no hardcoded merge-approval target" \
        'merge of code changes to main branch' "$rendered"
    assert_not_contains "SKILL.md $profile: no hardcoded git checkout main" \
        'git checkout main' "$rendered"
    assert_contains "SKILL.md $profile: resolves the merge target from the plan header" \
        'Resolve the merge target' "$rendered"
    # The branch name comes from a user-authored profile and git allows shell
    # metacharacters in ref names (dev;id, dev$(id) are valid), so every shell
    # sink that substitutes it must be quoted.
    # Quoting alone is NOT sufficient: "dev$(id)" executes inside double quotes
    # and git accepts such refs. Every sink must consume the shell VARIABLE that
    # Step 5/Step 9 bind and validate, never a textual placeholder.
    # t1560_2: `git checkout`, the fully-qualified `git rev-parse` pre-flight and
    # `git merge` moved OUT of Step 9 and INTO the merge broker, which performs
    # them inside the mutex. The injection-safety property did not move with
    # them -- it is re-pinned on both sides: here, that Step 9 hands the broker
    # the BOUND variable and substitutes no literal; and in
    # tests/test_merge_broker_rendered_verdicts.sh (BEGIN_CALL_NOT_BOUND /
    # BEGIN_CALL_SUBSTITUTES_LITERAL), that the rendered `begin` invocation
    # consumes that variable. Neither half may be deleted without the other
    # being in place first.
    assert_contains "SKILL.md $profile: hands the merge to the broker procedure" \
        '## Entry — acquire the reservation and merge' "$rendered"
    assert_contains "SKILL.md $profile: passes the bound variable, not a literal" \
        'the bound `$output_branch`' "$rendered"
    assert_contains "SKILL.md $profile: names the quoting rule at the call site" \
        'quoted shell variable' "$rendered"
    assert_contains "SKILL.md $profile: Step 9 validates the branch name" \
        'UNSAFE_OUTPUT_BRANCH' "$rendered"
    assert_contains "SKILL.md $profile: Step 9 binds from the plan header" \
        "output_branch=\$(sed -n 's/^Output branch: //p'" "$rendered"
    # Step 5 must not reference a shell variable no workflow command ever binds:
    # $base_branch is prose-only, so an absent-key fallback onto it would resolve
    # empty and stall every default-profile worktree run.
    unbound=$(printf '%s\n' "$rendered" | grep -cE 'output_branch="\$base_branch"' || true)
    assert_eq "SKILL.md $profile: no fallback onto an unbound \$base_branch" "0" "$unbound"
    # No command line may interpolate the placeholder -- that is the injectable form.
    placeholder_sink=$(printf '%s\n' "$rendered" \
        | grep -cE '^[[:space:]]*(git|\./\.aitask-scripts/aitask_merge_task\.sh) .*(<output_branch>|"<output_branch>")' || true)
    assert_eq "SKILL.md $profile: no git command substitutes the literal placeholder" \
        "0" "$placeholder_sink"
    # The legacy fallback must stop at main -- never rebound to Base branch, which
    # would retroactively change where an in-flight pre-t1233 plan merges.
    assert_not_contains "SKILL.md $profile: no Base branch rung in the fallback" \
        'Base branch: <branch>` — plans externalized before' "$rendered"
done

# === Test 4d: the externalize call passes a PATH, never a branch value ===
#
# Handing the helper a profile path (which it parses with a real YAML reader)
# keeps the user-authored branch name out of the agent's command line entirely.
echo "=== Test 4d: externalize call-sites pass the profile path (t1233) ==="
PE_OUT="$($RENDER "$WORKFLOW_DIR/plan-externalization.md" "$PROFILES_DIR/default.yaml" claude 2>&1)"
assert_contains "plan-externalization: passes --profile with the profile path" \
    '--profile "aitasks/metadata/profiles/<active_profile_filename>"' "$PE_OUT"
# Only actual command lines count -- the prose legitimately mentions the
# --output-branch <name> escape hatch.
# Join backslash-continued lines FIRST. Scanning only command-opening lines
# misses a value carried on the continuation, which is exactly where an
# interactively supplied branch would be substituted.
PE_JOINED=$(printf '%s\n' "$PE_OUT" | sed -e ':a' -e '/\\$/{N;s/\\\n//;ba' -e '}')
# The trailing space is what distinguishes a value-carrying flag from its -file
# form: `--base-branch-file <path>` is a PATH and must not be flagged here.
literal_flag=$(printf '%s\n' "$PE_JOINED" \
    | grep -E '^\./\.aitask-scripts/aitask_plan_externalize\.sh' \
    | grep -cE -- '--(base-branch|output-branch(-default)?) ' || true)
assert_eq "plan-externalization: no call-site substitutes a branch value" "0" "$literal_flag"
# The interactive value must travel through the file channel instead. Since t1277
# the base branch is its own flag: the interactive answer is the RECORDED
# `Base branch:` as well as the merge-target fallback, so routing it through the
# legacy --output-branch-default-file would leave the header field on the primary.
assert_contains "plan-externalization: interactive base uses the file channel" \
    '--base-branch-file' "$PE_OUT"
# The per-field splice-intent rule is the caller-visible half of BASE_INTENT: a
# call that supplies no base must not rewrite one. Prose here is load-bearing —
# it is what stops a future caller from "simplifying" onto the legacy flag.
assert_contains "plan-externalization: documents per-field splice opt-in" \
    'an invocation that supplies no base never rewrites one' "$PE_OUT"
# --profile must be conditional: active_profile_filename is null on manual/resume
# invocations, and a constructed path would make the fail-closed helper abort.
# Prose alone is not enough: an agent follows the command BLOCK. There must be a
# rendered invocation that carries no --profile at all, or a manual/resume run
# (active_profile_filename = null) would construct a missing path and the
# fail-closed helper would abort externalization.
no_profile_cmd=$(printf '%s\n' "$PE_JOINED" \
    | grep -E '^\./\.aitask-scripts/aitask_plan_externalize\.sh' \
    | grep -vc -- '--profile' || true)
assert_eq "plan-externalization: a usable no-profile command form is rendered" \
    "1" "$(test "$no_profile_cmd" -ge 1 && echo 1 || echo 0)"
# Retries must carry the resolution flags; the retry is the call that writes the
# header, so dropping them silently reverts the merge target to the primary.
assert_contains "plan-externalization: retries preserve the branch flags" \
    'preserving `--force` and the full `<branch-flags>` from the original call' "$PE_OUT"
# Current-branch mode must not be documented as an empty flag set: --no-worktree
# is what clears a stale Output branch left by an earlier run.
assert_contains "plan-externalization: current-branch mode always carries --no-worktree" \
    'Current-branch mode **always** includes `--no-worktree`' "$PE_OUT"
assert_not_contains "plan-externalization: no empty-flags advice for current-branch mode" \
    'legitimately **empty** for a no-profile, current-branch invocation' "$PE_OUT"
# The scratch value file must survive until Step 8, which reuses the same flags.
assert_contains "plan-externalization: scratch file lives until Step 8" \
    'Keep the scratch file until **Step 8** has run' "$PE_OUT"
# No example may label a current-branch invocation's flag set as empty: the
# command below such a label carries --no-worktree, and the mislabel is what
# would teach a future edit to drop it and restore the stale-header bug.
assert_not_contains "plan-externalization: no example labels branch-flags as empty" \
    '(`<branch-flags>` empty)' "$PE_OUT"

# === Test 4e: parallel-admission disposition contract, on the RENDER (t1569_4) ===
#
# The render is what the agent executes, so the verdict->disposition mapping has
# to be asserted on the GENERATED text, not inferred from the source template.
# Goldens catch any byte change but cannot say which sentence is load-bearing;
# these name them.
#
# `confirm` is set by NO committed profile, so the synthetic profile below is
# that branch's only executable coverage (same reason as Test 4b's
# create_worktree).

echo "=== Test 4e: parallel-admission disposition contract per profile ==="

PA_SRC="$WORKFLOW_DIR/parallel-admission.md"

TMP_PA_WARN="$(mktemp "${TMPDIR:-/tmp}/test_pa_warn_XXXXXX.yaml")"
TMP_PA_CONFIRM="$(mktemp "${TMPDIR:-/tmp}/test_pa_confirm_XXXXXX.yaml")"
TMP_PA_OFF="$(mktemp "${TMPDIR:-/tmp}/test_pa_off_XXXXXX.yaml")"
trap 'rm -f "$TMP_PROFILE" "$TMP_OB_PROFILE" "$TMP_PA_WARN" "$TMP_PA_CONFIRM" "$TMP_PA_OFF"' EXIT
# Every COMMITTED profile ships `off`, so the active bodies have no committed
# render at all. These two synthetic profiles are their only coverage -- the
# same situation as remote_drift_check: skip in Test 4.
cat > "$TMP_PA_WARN" <<'YAML'
name: test_pa_warn
description: "Synthetic profile for t1569_4 (parallel_admission: warn)"
parallel_admission: warn
YAML
# …and the absent-key default must render the SAME body as an explicit `warn`.
TMP_PA_ABSENT="$(mktemp "${TMPDIR:-/tmp}/test_pa_absent_XXXXXX.yaml")"
cat > "$TMP_PA_ABSENT" <<'YAML'
name: test_pa_warn
description: "Synthetic profile for t1569_4 (parallel_admission absent)"
YAML
cat > "$TMP_PA_CONFIRM" <<'YAML'
name: test_pa_confirm
description: "Synthetic profile for t1569_4 (parallel_admission: confirm)"
parallel_admission: confirm
YAML
cat > "$TMP_PA_OFF" <<'YAML'
name: test_pa_off
description: "Synthetic profile for t1569_4 (parallel_admission: off)"
parallel_admission: "off"
YAML

pa_render() { $RENDER "$PA_SRC" "$1" claude 2>&1; }

# --- the ACTIVE (warn) body: every verdict maps to its own disposition ------
for prof in warn absent; do
    case "$prof" in
        warn)   out="$(pa_render "$TMP_PA_WARN")" ;;
        absent) out="$(pa_render "$TMP_PA_ABSENT")" ;;
    esac
    assert_contains "pa/$prof: CLEAR proceeds with the honest wording" \
        'no known conflict at check time' "$out"
    assert_contains "pa/$prof: CLEAR must not claim parallel safety" \
        'never "safe to run in parallel"' "$out"
    # warn: CLEAR_CAVEATED is a NOTE, distinct from CLEAR and from confirm.
    assert_contains "pa/$prof: CLEAR_CAVEATED renders as a visible note (warn)" \
        'display a visible note naming each unverified source' "$out"
    assert_not_contains "pa/$prof: CLEAR_CAVEATED does not ask under warn" \
        "sets \`parallel_admission: confirm\`" "$out"
    assert_contains "pa/$prof: CLEAR_CAVEATED is rendered distinctly from CLEAR" \
        'Render it distinctly from `CLEAR`' "$out"
    assert_contains "pa/$prof: CONFLICT names the tasks and files, then asks" \
        'name the overlapping task(s) and file(s) from the `OVERLAP:` lines, then ask' "$out"
    assert_contains "pa/$prof: UNCHECKABLE names why and asks" \
        'name *why*, with the remedy from step 5' "$out"
    # Continue-first is the advisory posture, and it is an ORDER claim.
    # Anchor on the OPTION-LIST shape, not the bare label: the intro quotes
    # `returned "Continue anyway"` from the drift check, and a head -n1 on the
    # bare label lands there instead -- which made an earlier draft of this
    # assertion trivially true regardless of the real option order.
    cont_line="$(printf '%s\n' "$out" | grep -n -- '- "Continue anyway" (description:' | head -n1 | cut -d: -f1)"
    stop_line="$(printf '%s\n' "$out" | grep -n -- '- "Stop and re-plan" (description:' | head -n1 | cut -d: -f1)"
    TOTAL=$((TOTAL + 1))
    if [[ -n "$cont_line" && -n "$stop_line" && "$cont_line" -lt "$stop_line" ]]; then
        PASS=$((PASS + 1))
        echo "PASS: pa/$prof lists 'Continue anyway' before 'Stop and re-plan' (@$cont_line < @$stop_line)"
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: pa/$prof does not list continue first (continue@$cont_line stop@$stop_line) -- an advisory heuristic must not present a stop as the default"
    fi
    # The fail-safe clause (t1569_4 finding: invalid output is never a pass).
    assert_contains "pa/$prof: invalid checker output is UNCHECKABLE, not a pass" \
        'Accept the result only if it is well-formed' "$out"
    assert_contains "pa/$prof: a duplicate VERDICT line is never resolved by picking one" \
        'never pick one' "$out"
    assert_contains "pa/$prof: fail-safe is stated, not implied" \
        'fail-safe, not fail-open' "$out"
done

# --- the `confirm` branch (synthetic; no committed profile sets it) ---------
out_confirm="$(pa_render "$TMP_PA_CONFIRM")"
assert_contains "pa/confirm: CLEAR_CAVEATED asks instead of noting" \
    "**Profile 'test_pa_confirm' sets \`parallel_admission: confirm\`**" "$out_confirm"
assert_not_contains "pa/confirm: the warn note text is suppressed" \
    'display a visible note naming each unverified source' "$out_confirm"
assert_contains "pa/confirm: CONFLICT is unchanged by the knob" \
    'name the overlapping task(s) and file(s)' "$out_confirm"

# --- `off`: the WHOLE step is absent, not merely quiet ---------------------
for label in "synthetic:$TMP_PA_OFF" "default:$PROFILES_DIR/default.yaml" \
             "fast:$PROFILES_DIR/fast.yaml" "remote:$PROFILES_DIR/remote.yaml"; do
    name="${label%%:*}"; file="${label#*:}"
    out_off="$(pa_render "$file")"
    assert_contains "pa/off($name): says it is a no-op" 'is a **no-op**' "$out_off"
    assert_not_contains "pa/off($name): no checker invocation" \
        'aitask_parallel_admission.sh' "$out_off"
    assert_not_contains "pa/off($name): no prompt" 'AskUserQuestion' "$out_off"
    assert_not_contains "pa/off($name): no disposition table" 'CLEAR_CAVEATED' "$out_off"
done

# --- NO render, in ANY profile, may claim the step stops on its own --------
#
# The executable form of the advisory-only decision. Checked across every
# profile including `off`, because the Notes render there too.
for file in "$PROFILES_DIR"/default.yaml "$PROFILES_DIR"/fast.yaml \
            "$PROFILES_DIR"/remote.yaml "$TMP_PA_WARN" "$TMP_PA_ABSENT" \
            "$TMP_PA_CONFIRM" "$TMP_PA_OFF"; do
    out_any="$(pa_render "$file")"
    assert_contains "pa($(basename "$file")): states that no value stops the workflow" \
        'No value of `parallel_admission` stops' "$out_any"
    assert_not_contains "pa($(basename "$file")): never renders a stop-and-replan default" \
        'stop-and-replan by default' "$out_any"
    assert_not_contains "pa($(basename "$file")): never offers a \`block\` value" \
        'parallel_admission: block' "$out_any"
done

# --- every SHIPPED profile opts out, and its seed mirror agrees ------------
#
# The docs, the goldens and Test 4e's `off` loop all rest on this. Assert it
# directly rather than inferring it from a render.
for prof in default fast remote; do
    assert_contains "profile $prof ships the opt-out" \
        'parallel_admission: "off"' "$(cat "$PROFILES_DIR/$prof.yaml")"
    assert_contains "seed profile $prof mirrors it" \
        'parallel_admission: "off"' "$(cat "seed/profiles/$prof.yaml")"
    # Unquoted would parse as the boolean false. The renderer tolerates that,
    # but a shipped profile must not rely on the tolerance.
    assert_not_contains "profile $prof does not ship a bare (boolean) off" \
        'parallel_admission: off' "$(cat "$PROFILES_DIR/$prof.yaml")"
done

# --- profiles.md documents the knob, and agrees with the procedure ---------
#
# profiles.md carries NO Jinja and is in neither WRAPPED_FILES_* array, so no
# golden covers it. A contradiction between the knob's documentation and the
# procedure it documents would otherwise be invisible to this whole suite.
PROFILES_DOC="$WORKFLOW_DIR/profiles.md"
profiles_doc_text="$(cat "$PROFILES_DOC")"
assert_contains "profiles.md documents parallel_admission" \
    '`parallel_admission`' "$profiles_doc_text"
assert_contains "profiles.md names exactly the three values" \
    '`"confirm"`, `"warn"` (**the default** when omitted), or `"off"`' "$profiles_doc_text"
assert_contains "profiles.md states that no value stops the workflow" \
    '**No value of this key ever stops the workflow.**' "$profiles_doc_text"
assert_contains "profiles.md says there is deliberately no block value" \
    'There is deliberately no `block` value' "$profiles_doc_text"
assert_not_contains "profiles.md carries no promotion criterion" \
    'promot' "$profiles_doc_text"
assert_not_contains "profiles.md carries no stop-and-replan claim" \
    'stop-and-replan' "$profiles_doc_text"
assert_contains "profiles.md warns that a bare off is a YAML boolean" \
    'YAML parses a bare `off` as the boolean false' "$profiles_doc_text"

# === Test 5: risk machinery is profile-CONDITIONAL via rendered_set (t635_33) ===
#
# t635_33 re-introduced render-time omission: the risk producer machinery is
# wrapped in {% if 'risk_evaluated' in rendered_set %}, where rendered_set is
# the profile's render ceiling (rendered_gates if the key is present, else
# default_gates, else []). `fast` declares default_gates: [risk_evaluated] →
# machinery rendered; `default`/`remote` declare none → machinery OMITTED and
# Step 8c routes straight to Step 9. Correctness is preserved at runtime by the
# claim-time `materialize-active` tuple (ALWAYS rendered — never Jinja-gated),
# which replaced the former Step-7 gates: backfill.
echo "=== Test 5: risk machinery profile-conditional via rendered_set (t635_33) ==="
RISK_PROFILES=(fast)
LEAN_PROFILES=(default remote)
for profile in "${RISK_PROFILES[@]}"; do
    RP="$($RENDER "$WORKFLOW_DIR/planning.md" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    RS="$($RENDER "$WORKFLOW_DIR/SKILL.md" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    assert_contains "planning.md $profile: emits the eval step" \
        'Risk evaluation (end of planning)' "$RP"
    assert_contains "planning.md $profile: emits the mitigation design step" \
        'Risk-mitigation design (end of planning)' "$RP"
    assert_contains "planning.md $profile: risk check is the exit-code verb" \
        'aitask_gate.sh active <task_id> risk_evaluated' "$RP"
    assert_not_contains "planning.md $profile: no effective-gates text parsing" \
        'effective-gates <task_id> --profile' "$RP"
    assert_contains "SKILL.md $profile: emits the Step 7 'before' creation hook" \
        'Risk-mitigation "before" creation' "$RS"
    assert_contains "SKILL.md $profile: emits Step 8d 'after' creation" \
        'Step 8d: Risk-Mitigation' "$RS"
    assert_contains "SKILL.md $profile: Step 8c points to Step 8d" \
        'proceed to Step 8d' "$RS"
done
for profile in "${LEAN_PROFILES[@]}"; do
    RP="$($RENDER "$WORKFLOW_DIR/planning.md" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    RS="$($RENDER "$WORKFLOW_DIR/SKILL.md" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    assert_not_contains "planning.md $profile: risk eval step OMITTED" \
        'Risk evaluation (end of planning)' "$RP"
    assert_not_contains "planning.md $profile: mitigation design OMITTED" \
        'Risk-mitigation design (end of planning)' "$RP"
    assert_not_contains "planning.md $profile: risk-section guard OMITTED" \
        'Risk-section guard' "$RP"
    assert_not_contains "SKILL.md $profile: 'before' creation OMITTED" \
        'Risk-mitigation "before" creation' "$RS"
    assert_not_contains "SKILL.md $profile: Step 8d OMITTED" \
        'Step 8d: Risk-Mitigation' "$RS"
    assert_contains "SKILL.md $profile: Step 8c routes straight to Step 9" \
        'When the procedure returns, proceed to Step 9.' "$RS"
done
for profile in "${PROFILES[@]}"; do
    RP="$($RENDER "$WORKFLOW_DIR/planning.md" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    RS="$($RENDER "$WORKFLOW_DIR/SKILL.md" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    # The claim-time materialization is the correctness safety valve: ALWAYS
    # rendered, in every profile (writing `active_gates: []` is what makes a
    # declared-but-unrendered gate invisible to every enforcer).
    assert_contains "SKILL.md $profile: materialize-active always rendered" \
        'aitask_gate.sh materialize-active' "$RS"
    # The two-field risk write stays profile-invariant (runtime no-op when the
    # plan has no ## Risk section).
    assert_contains "SKILL.md $profile: emits the two-field write" \
        '--risk-code-health' "$RS"
    # The Step-7 gates: backfill is retired — no inline bash block remains.
    assert_not_contains "SKILL.md $profile: no gate-declaration backfill" \
        'Gate-declaration backfill' "$RS"
    # The retired profile key must not reappear as a render-time Jinja gate.
    assert_not_contains "planning.md $profile: no profile.risk_evaluation Jinja" \
        'profile.risk_evaluation' "$RP"
    assert_not_contains "SKILL.md $profile: no profile.risk_evaluation Jinja" \
        'profile.risk_evaluation' "$RS"
done
# Material leanness: the lean render must be strictly smaller than the risk
# render for BOTH files (the t635_14 regression this task reverses).
FAST_S_LINES="$($RENDER "$WORKFLOW_DIR/SKILL.md" "$PROFILES_DIR/fast.yaml" claude 2>&1 | wc -l)"
DEF_S_LINES="$($RENDER "$WORKFLOW_DIR/SKILL.md" "$PROFILES_DIR/default.yaml" claude 2>&1 | wc -l)"
FAST_P_LINES="$($RENDER "$WORKFLOW_DIR/planning.md" "$PROFILES_DIR/fast.yaml" claude 2>&1 | wc -l)"
DEF_P_LINES="$($RENDER "$WORKFLOW_DIR/planning.md" "$PROFILES_DIR/default.yaml" claude 2>&1 | wc -l)"
if [[ "$DEF_S_LINES" -lt "$FAST_S_LINES" && "$DEF_P_LINES" -lt "$FAST_P_LINES" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: default render not leaner (SKILL $DEF_S_LINES vs $FAST_S_LINES; planning $DEF_P_LINES vs $FAST_P_LINES)"
fi
TOTAL=$((TOTAL + 1))

# === Test 6: synthetic record_gates: true fires the gated recording sites (t635_2) ===
#
# The record_gates gate is a zero-footprint {%- if profile.record_gates
# is defined and profile.record_gates %} wrap at six dispatch sites:
# SKILL.md Step 7 (plan_approved; risk_evaluated — now guarded additionally by a
# runtime `should-self-record` check, t635_14), Step 8 (review_approved), Step 9
# (build_verified, merge_approved), the Procedures list, and planning.md's
# "Approve and stop here" branch (deferred plan_approved). fast.yaml sets
# record_gates: true, so the committed fast goldens carry these sites while
# default/remote omit them (Test 1). The risk-field write is now always rendered
# (no longer risk_evaluation-gated), so record_gates alone exercises the nested
# risk_evaluated recording.
echo "=== Test 6: synthetic record_gates: true profile ==="
TMP_REC="$(mktemp "${TMPDIR:-/tmp}/test_record_XXXXXX.yaml")"
trap 'rm -f "$TMP_PROFILE" "$TMP_RISK" "$TMP_REC"' EXIT
# default_gates makes rendered_set = [risk_evaluated], so the nested
# risk_evaluated self-record site (record_gates AND rendered-set gated since
# t635_33) is exercised alongside the plain record_gates sites.
cat > "$TMP_REC" <<'YAML'
name: test_record_gates
description: "Synthetic profile for t635_2 test (record_gates true)"
record_gates: true
default_gates: [risk_evaluated]
YAML
REC_SKILL="$($RENDER "$WORKFLOW_DIR/SKILL.md" "$TMP_REC" claude 2>&1)"
REC_PLAN="$($RENDER "$WORKFLOW_DIR/planning.md" "$TMP_REC" claude 2>&1)"
assert_contains "record_gates true: SKILL.md emits plan_approved recording" \
    'gate_name=plan_approved' "$REC_SKILL"
assert_contains "record_gates true: SKILL.md emits risk_evaluated recording (nested)" \
    'gate_name=risk_evaluated' "$REC_SKILL"
assert_contains "record_gates true: risk_evaluated record guarded by should-self-record (t635_14)" \
    'should-self-record' "$REC_SKILL"
assert_contains "record_gates true: SKILL.md emits review_approved recording" \
    'gate_name=review_approved' "$REC_SKILL"
assert_contains "record_gates true: SKILL.md emits build_verified recording" \
    'gate_name=build_verified' "$REC_SKILL"
# t1610: the recording is verdict-driven, not hardcoded to pass. A legacy
# build-verification `skip` (an opted-in command that declared it did not run)
# must reach the ledger as `skip`, exactly as the gate path records it -- so the
# status must be threaded through, and the unconfigured case must record nothing.
assert_contains "record_gates true: build_verified status is the returned verdict" \
    'status=<build_verdict>' "$REC_SKILL"
assert_contains "record_gates true: nothing is recorded when nothing is configured" \
    'When `build_verdict` is **not** `none`' "$REC_SKILL"
assert_not_contains "record_gates true: build_verified is not hardcoded to pass" \
    'gate_name=build_verified`, `status=pass' "$REC_SKILL"
assert_contains "record_gates true: SKILL.md emits merge_approved recording" \
    'gate_name=merge_approved' "$REC_SKILL"
assert_contains "record_gates true: SKILL.md lists the Gate Recording Procedure" \
    'Gate Recording Procedure' "$REC_SKILL"
# The deferred plan_approved recording moved OUT of planning.md and into the
# shared Approved-Plan Stop Sequence (t1380): planning.md and remote-drift-check.md
# now both REFERENCE it, so neither can drop a step by partial copy. The
# record_gates guard therefore lives in plan-approved-stop.md, and that is where
# the recording assertion belongs.
REC_STOP="$($RENDER "$WORKFLOW_DIR/plan-approved-stop.md" "$TMP_REC" claude 2>&1)"
assert_contains "record_gates true: plan-approved-stop.md emits the plan_approved recording" \
    'gate_name=plan_approved' "$REC_STOP"
assert_contains "record_gates true: the recording is guarded by recorded-pass (record once)" \
    'recorded-pass <task_id> plan_approved' "$REC_STOP"
assert_contains "planning.md references the shared stop sequence" \
    'plan-approved-stop.md' "$REC_PLAN"
REC_DRIFT="$($RENDER "$WORKFLOW_DIR/remote-drift-check.md" "$TMP_REC" claude 2>&1)"
assert_contains "remote-drift-check.md references the same shared stop sequence" \
    'plan-approved-stop.md' "$REC_DRIFT"
assert_not_contains "planning.md no longer inlines its own plan_approved recording" \
    'gate_name=plan_approved' "$REC_PLAN"

# Default profile (key absent) shows none — guards the zero-footprint claim.
DEFAULT_REC_SKILL="$($RENDER "$WORKFLOW_DIR/SKILL.md" "$PROFILES_DIR/default.yaml" claude 2>&1)"
DEFAULT_REC_PLAN="$($RENDER "$WORKFLOW_DIR/planning.md" "$PROFILES_DIR/default.yaml" claude 2>&1)"
DEFAULT_REC_STOP="$($RENDER "$WORKFLOW_DIR/plan-approved-stop.md" "$PROFILES_DIR/default.yaml" claude 2>&1)"
assert_not_contains "default profile: no SKILL.md gate recording references" \
    'Gate Recording Procedure' "$DEFAULT_REC_SKILL"
assert_not_contains "default profile: no SKILL.md gate-record script mention" \
    'aitask_gate_record.sh' "$DEFAULT_REC_SKILL"
assert_not_contains "default profile: no planning.md gate recording" \
    'gate_name=plan_approved' "$DEFAULT_REC_PLAN"
assert_not_contains "default profile: no plan-approved-stop.md gate recording" \
    'gate_name=plan_approved' "$DEFAULT_REC_STOP"
assert_not_contains "default profile: no plan-approved-stop.md Gate Recording Procedure" \
    'Gate Recording Procedure' "$DEFAULT_REC_STOP"
# ...but the release-and-revert body must still render: the guard removes the
# recording, not the sequence.
assert_contains "default profile: plan-approved-stop.md still reverts to Ready" \
    '--status Ready --assigned-to ""' "$DEFAULT_REC_STOP"

# === Test 7: AskUserQuestion header cap in risk-mitigation-followup (t1419) ===
#
# The AskUserQuestion contract documents a 12-char cap on the header chip.
# Scoped to risk-mitigation-followup.md, whose recovery prompts (stale
# witness, ambiguous adoption) were added under that cap; two pre-existing
# 13-char headers elsewhere ("Related tasks", "Manual verify") are out of
# scope here.

echo "=== Test 7: risk-mitigation-followup AskUserQuestion headers <= 12 chars ==="
long_headers="$(grep -hoE '[Hh]eader:? "[^"]+"' "$WORKFLOW_DIR/risk-mitigation-followup.md" \
    | awk -F'"' 'length($2) > 12 {print $2}' | sort -u | tr '\n' ',')"
assert_eq "risk-mitigation-followup headers within 12-char cap" "" "$long_headers"

# === Summary ===

echo ""
echo "Tests: $TOTAL, Passed: $PASS, Failed: $FAIL"
[[ "$FAIL" -eq 0 ]] || exit 1
