#!/usr/bin/env bash
# test_skill_render_aitask_pick.sh - Regression tests for t777_6 pilot:
#   - .claude/skills/aitask-pick/SKILL.md.j2 (entry-point template)
#   - 3 per-agent stubs (claude/codex/opencode)
#   - 3 golden files under tests/golden/skills/aitask-pick/ (3 profiles, claude canonical)
# Coverage:
#   1.  Per-profile golden diff for the entry-point template (claude render).
#   1b. Agent-dimension invariance: codex/opencode renders are
#       byte-identical to the claude render (no {% if agent %} in the
#       template). Per-agent reference rewrites are a walk-write property
#       covered by Test 4, not the basic stdout render.
#   2. Profile-conditional sanity: fast/remote renders contain the
#      auto-confirm branch; default render preserves AskUserQuestion text.
#   3. No Jinja markers leak into any rendered entry-point.
#   4. Stub markers present on all 3 stub files (canonical body fingerprint
#      from aidocs/framework/stub-skill-pattern.md §3b/§3c/§3d).
# Run: bash tests/test_skill_render_aitask_pick.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

PASS=0
FAIL=0
TOTAL=0

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"

cd "$PROJECT_DIR" || exit 1

# shellcheck source=.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
PYTHON="$(require_ait_python)"
if ! "$PYTHON" -c 'import minijinja' 2>/dev/null; then
    echo "SKIP: minijinja not installed in framework venv ($PYTHON). Run 'ait setup' first."
    exit 0
fi

RENDER="$PYTHON $PROJECT_DIR/.aitask-scripts/lib/skill_template.py"
TEMPLATE=".claude/skills/aitask-pick/SKILL.md.j2"
GOLDEN_DIR="tests/golden/skills/aitask-pick"
PROFILES_DIR="aitasks/metadata/profiles"

PROFILES=(default fast remote)
AGENTS=(claude codex opencode)

# === Test 1: per-profile golden diffs (claude render is canonical) ===

echo "=== Test 1: golden diffs for entry-point × 3 profiles ==="
for profile in "${PROFILES[@]}"; do
    rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    golden_content="$(cat "$GOLDEN_DIR/SKILL-${profile}-claude.md")"
    assert_eq "golden SKILL × $profile" "$golden_content" "$rendered"
done

# === Test 1b: agent dimension invariance ===
#
# The entry-point template has no {% if agent %} gate, so the basic
# stdout render is byte-identical across all 4 agents. This single
# assertion replaces the 9 deleted per-agent goldens; if a future
# template introduces agent gating it fails LOUDLY — re-add per-agent
# goldens for that skill then (see aidocs/framework/stub-skill-pattern.md).
echo "=== Test 1b: agent renders are byte-identical (no {% if agent %} in template) ==="
for profile in "${PROFILES[@]}"; do
    base="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    for agent in codex opencode; do
        cmp="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" "$agent" 2>&1)"
        assert_eq "agent invariance $profile/$agent" "$base" "$cmp"
    done
done

# === Test 2: profile-conditional sanity ===

echo "=== Test 2: profile branches fire correctly ==="
FAST_CLAUDE="$($RENDER "$TEMPLATE" "$PROFILES_DIR/fast.yaml" claude 2>&1)"
assert_contains "fast/claude: auto-confirm branch fires (parent task)" \
    "Profile 'fast': auto-confirming task selection" "$FAST_CLAUDE"

REMOTE_CLAUDE="$($RENDER "$TEMPLATE" "$PROFILES_DIR/remote.yaml" claude 2>&1)"
assert_contains "remote/claude: auto-confirm branch fires" \
    "Profile 'remote': auto-confirming task selection" "$REMOTE_CLAUDE"

DEFAULT_CLAUDE="$($RENDER "$TEMPLATE" "$PROFILES_DIR/default.yaml" claude 2>&1)"
assert_contains "default/claude: AskUserQuestion branch fires (parent task)" \
    'Is this the correct task? Brief summary' "$DEFAULT_CLAUDE"
assert_not_contains "default/claude: no auto-confirm branch" \
    "auto-confirming task selection" "$DEFAULT_CLAUDE"

# === Test 3: no Jinja markers leak ===

echo "=== Test 3: rendered output has no Jinja markers ==="
for profile in "${PROFILES[@]}"; do
    for agent in "${AGENTS[@]}"; do
        rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" "$agent" 2>&1)"
        assert_not_contains "no Jinja {% leak $profile × $agent" "{%" "$rendered"
        assert_not_contains "no Jinja {{ leak $profile × $agent" "{{" "$rendered"
    done
done

# === Test 3b: rendered body must NOT re-resolve profile at runtime (t777_26) ===

echo "=== Test 3b: rendered body has no runtime profile-resolution tokens ==="
FORBIDDEN_TOKENS=(
    "aitask_scan_profiles.sh"
    "Execute the Execution Profile Selection Procedure"
    "Select Execution Profile"
    "refresh execution profile"
)
for profile in "${PROFILES[@]}"; do
    for agent in "${AGENTS[@]}"; do
        rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" "$agent" 2>&1)"
        for token in "${FORBIDDEN_TOKENS[@]}"; do
            assert_not_contains "rendered $profile × $agent has no '$token'" \
                "$token" "$rendered"
        done
    done
done

# === Test 4: cross-agent reference rewrites (via walk-write on-disk output) ===

echo "=== Test 4: per-agent reference rewrites via walk-write ==="
# Reference rewriting is a walk-write/walk-check property, not a single-file
# render property. Drive the full closure walk via aitask_skill_render.sh
# to write the on-disk per-profile tree, then assert on the entry point
# file under each agent root.
for agent in "${AGENTS[@]}"; do
    ./.aitask-scripts/aitask_skill_render.sh aitask-pick --profile fast --agent "$agent" --force >/dev/null 2>&1
done

assert_contains "claude/fast: task-workflow ref rewritten under .claude/skills" \
    ".claude/skills/task-workflow-fast-/SKILL.md" "$(cat .claude/skills/aitask-pick-fast-/SKILL.md)"
assert_contains "codex/fast: task-workflow ref rewritten under .agents/skills" \
    ".agents/skills/task-workflow-fast-codex-/SKILL.md" "$(cat .agents/skills/aitask-pick-fast-codex-/SKILL.md)"
assert_contains "opencode/fast: task-workflow ref rewritten under .opencode/skills" \
    ".opencode/skills/task-workflow-fast-/SKILL.md" "$(cat .opencode/skills/aitask-pick-fast-/SKILL.md)"

# === Test 5: stub-marker checks ===

echo "=== Test 5: 3 stub files contain canonical markers ==="
CLAUDE_STUB=".claude/skills/aitask-pick/SKILL.md"
CODEX_STUB=".agents/skills/aitask-pick/SKILL.md"
OPENCODE_STUB=".opencode/commands/aitask-pick.md"

for stub in "$CLAUDE_STUB" "$CODEX_STUB" "$OPENCODE_STUB"; do
    body="$(cat "$stub")"
    assert_contains "$stub: resolve_profile uses short name 'pick' (t777_26)" \
        "aitask_skill_resolve_profile.sh pick" "$body"
    assert_not_contains "$stub: resolve_profile does NOT use full slug 'aitask-pick'" \
        "aitask_skill_resolve_profile.sh aitask-pick" "$body"
    assert_contains "$stub: skill render invocation present" \
        "aitask_skill_render.sh aitask-pick" "$body"
    assert_contains "$stub: Read-and-follow marker present" \
        "Dispatch via Read-and-follow" "$body"
done

# Per-agent agent_literal substitution checks
assert_contains "claude stub: --agent claude" "--agent claude" "$(cat "$CLAUDE_STUB")"
assert_contains "codex stub: --agent codex" "--agent codex" "$(cat "$CODEX_STUB")"
assert_contains "opencode stub: --agent opencode" "--agent opencode" "$(cat "$OPENCODE_STUB")"

# Per-agent rendered-variant Read target checks
assert_contains "claude stub: reads from .claude/skills/aitask-pick-<profile>-" \
    ".claude/skills/aitask-pick-<profile>-/SKILL.md" "$(cat "$CLAUDE_STUB")"
assert_contains "codex stub: reads from .agents/skills/aitask-pick-<profile>-" \
    ".agents/skills/aitask-pick-<profile>-codex-/SKILL.md" "$(cat "$CODEX_STUB")"
assert_contains "opencode stub: reads from .opencode/skills/aitask-pick-<profile>-" \
    ".opencode/skills/aitask-pick-<profile>-/SKILL.md" "$(cat "$OPENCODE_STUB")"

# === Test 6: in-flight resume section (profile-invariant, t635_7) ===
#
# The gate-aware in-flight pick section is profile-invariant prose (no
# {% if profile %} gate), so it must render identically into all 3 profiles.
echo "=== Test 6: in-flight resume section renders in all profiles ==="
for profile in "${PROFILES[@]}"; do
    rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    assert_contains "in-flight heading present ($profile)" \
        "2.0: In-Flight Tasks (resume candidates)" "$rendered"
    assert_contains "in-flight enumerator call present ($profile)" \
        "aitask_query_files.sh inflight" "$rendered"
    assert_contains "in-flight 'pick a new task' option present ($profile)" \
        "Pick a new (Ready) task instead" "$rendered"
done

# === Test 7: opt-in pre-claim parallel assessment (t1688_2) ===
#
# `parallel_assessment` is OPT-IN: "off" (and an absent key) must render the
# hook away entirely -- no procedure reference, no checker invocation, no cost
# on a normal pick. Every shipped profile ships "off", so the enabled bodies
# have no committed render at all and the scratch profiles below are their only
# executable coverage (same situation as Test 4e's `parallel_admission: warn`
# in tests/test_skill_render_task_workflow.sh).
#
# The headless assertions are the load-bearing ones: the procedure promises no
# prompt under `headless: true` in BOTH modes, and a regression in the `ask`
# branch would leave an unattended pick waiting for an answer nobody can give.
# Each headless assertion is paired with a non-headless control of the SAME
# mode that DOES prompt, so "no AskUserQuestion" can never pass vacuously.

echo "=== Test 7: parallel_assessment opt-in (disabled / enabled / headless) ==="

PA_TMPDIR="$(mktemp -d "${TMPDIR:-/tmp}/test_pick_pa_XXXXXX")"
trap 'rm -rf "$PA_TMPDIR"' EXIT

cat > "$PA_TMPDIR/absent.yaml" <<'YAML'
name: pa_absent
description: "Synthetic profile for t1688_2 (parallel_assessment key absent)"
YAML
cat > "$PA_TMPDIR/show.yaml" <<'YAML'
name: pa_show
description: "Synthetic profile for t1688_2 (parallel_assessment: show)"
parallel_assessment: "show"
parallel_admission: "off"
YAML
cat > "$PA_TMPDIR/ask.yaml" <<'YAML'
name: pa_ask
description: "Synthetic profile for t1688_2 (parallel_assessment: ask)"
parallel_assessment: "ask"
parallel_admission: "off"
YAML
cat > "$PA_TMPDIR/show_headless.yaml" <<'YAML'
name: pa_show_headless
description: "Synthetic profile for t1688_2 (headless + parallel_assessment: show)"
headless: true
parallel_assessment: "show"
parallel_admission: "off"
YAML
cat > "$PA_TMPDIR/ask_headless.yaml" <<'YAML'
name: pa_ask_headless
description: "Synthetic profile for t1688_2 (headless + parallel_assessment: ask)"
headless: true
parallel_assessment: "ask"
parallel_admission: "off"
YAML

PROC="$PROJECT_DIR/.claude/skills/task-workflow/parallel-assessment.md"
CHECKER="$PROJECT_DIR/.claude/skills/task-workflow/parallel-admission-checker.md"

# --- disabled: the three shipped profiles AND a key-absent profile ----------
for profile in "${PROFILES[@]}"; do
    rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    assert_not_contains "pick/$profile: no assessment procedure reference" \
        "task-workflow/parallel-assessment.md" "$rendered"
    assert_not_contains "pick/$profile: no checker invocation" \
        "aitask_parallel_admission.sh" "$rendered"
done
rendered_absent="$($RENDER "$TEMPLATE" "$PA_TMPDIR/absent.yaml" claude 2>&1)"
assert_not_contains "pick/key-absent: absent key means off" \
    "task-workflow/parallel-assessment.md" "$rendered_absent"
assert_not_contains "pick/key-absent: no checker invocation" \
    "aitask_parallel_admission.sh" "$rendered_absent"

# --- enabled: the hook renders, and it renders BEFORE the Step 3 hand-off ---
#
# Order is the contract, not mere presence: the assessment exists to run before
# the task is claimed, and a line that renders after the hand-off would run
# after Step 4 took the lock. Line-order pattern: tests/test_inbox_surfacing_render.sh.
for mode in show ask; do
    rendered="$($RENDER "$TEMPLATE" "$PA_TMPDIR/$mode.yaml" claude 2>&1)"
    assert_contains "pick/$mode: assessment procedure referenced by full path" \
        ".claude/skills/task-workflow/parallel-assessment.md" "$rendered"
    assert_contains "pick/$mode: the profile's mode is named in the render" \
        "parallel_assessment: $mode" "$rendered"
    n_assess="$(printf '%s\n' "$rendered" | grep -n 'parallel-assessment.md' | head -n1 | cut -d: -f1)"
    n_handoff="$(printf '%s\n' "$rendered" | grep -n 'read and follow .*task-workflow/SKILL.md' | head -n1 | cut -d: -f1)"
    TOTAL=$(( TOTAL + 1 ))
    if [[ -n "$n_assess" && -n "$n_handoff" && "$n_assess" -lt "$n_handoff" ]]; then
        PASS=$(( PASS + 1 ))
        echo "PASS: pick/$mode: assessment precedes the Step 3 hand-off ($n_assess < $n_handoff)"
    else
        FAIL=$(( FAIL + 1 ))
        echo "FAIL: pick/$mode: assessment does not precede the hand-off (assess=$n_assess handoff=$n_handoff)"
    fi
done

# --- the procedure itself: disabled body, enabled bodies, headless bodies ---
proc_render() { $RENDER "$PROC" "$1" claude 2>&1; }

proc_off="$(proc_render "$PROFILES_DIR/fast.yaml")"
assert_contains "proc/off: says it is a no-op" 'is a **no-op**' "$proc_off"
assert_not_contains "proc/off: no checker invocation" \
    'parallel-admission-checker.md' "$proc_off"
assert_not_contains "proc/off: no prompt" 'AskUserQuestion' "$proc_off"
assert_not_contains "proc/off: no grading vocabulary" 'not assessed' "$proc_off"

proc_show="$(proc_render "$PA_TMPDIR/show.yaml")"
proc_ask="$(proc_render "$PA_TMPDIR/ask.yaml")"
proc_show_hl="$(proc_render "$PA_TMPDIR/show_headless.yaml")"
proc_ask_hl="$(proc_render "$PA_TMPDIR/ask_headless.yaml")"

for pair in "show:$proc_show" "ask:$proc_ask" "show_headless:$proc_show_hl" "ask_headless:$proc_ask_hl"; do
    name="${pair%%:*}"; body="${pair#*:}"
    assert_contains "proc/$name: defers the invocation to the checker contract" \
        'parallel-admission-checker.md' "$body"
    assert_contains "proc/$name: runs the checker WITHOUT --plan" \
        '**without**' "$body"
    assert_contains "proc/$name: keeps the not-assessed grade" 'not assessed' "$body"
    assert_contains "proc/$name: skips an already-claimed task" 'Implementing' "$body"
    assert_contains "proc/$name: never claims parallel safety" \
        'Never write "safe to run in parallel"' "$body"
    # The two incompleteness sources are reported SEPARATELY: a well-formed
    # UNCHECKABLE (or a partial in-flight enumeration) is the checker answering
    # with gaps; "checker unavailable" is the checker not answering at all.
    assert_contains "proc/$name: well-formed UNCHECKABLE is an incompleteness gap" \
        'VERDICT:UNCHECKABLE' "$body"
    assert_contains "proc/$name: a partial enumeration is named as such" \
        'enumeration incomplete' "$body"
    assert_contains "proc/$name: checker-unavailable is its own, separate clause" \
        'separately, "checker unavailable"' "$body"
done

# `ask` prompts unconditionally; `show` prompts only on an overlap / unusable
# checker. Both, attended, must still CARRY the prompt.
assert_contains "proc/ask: prompts unconditionally" 'always prompt' "$proc_ask"
assert_contains "proc/ask: attended ask has the prompt" 'AskUserQuestion' "$proc_ask"
assert_contains "proc/show: prompt is conditional on an overlap or unusable checker" \
    'prompt **only** when some row is `overlaps` or the checker was' "$proc_show"
assert_contains "proc/show: attended show has the prompt" 'AskUserQuestion' "$proc_show"

# The headless pair -- the assertions the attended controls above make non-vacuous.
assert_not_contains "proc/show_headless: headless show never prompts" \
    'AskUserQuestion' "$proc_show_hl"
assert_not_contains "proc/ask_headless: headless ask never prompts either" \
    'AskUserQuestion' "$proc_ask_hl"
assert_contains "proc/ask_headless: says so explicitly" \
    'never prompt' "$proc_ask_hl"

# --- closure level: the enabled assessment pulls the checker contract in ----
#
# The independent-toggle seam. Every scratch profile above sets
# `parallel_admission: "off"` EXPLICITLY (an absent key would mean `warn`), so
# the preflight renders its steps -- and its checker reference -- away, and the
# assessment's own reference is the edge under test.
#
# `walk-check`'s exit status proves nothing here: `discover_refs` silently skips
# a reference whose target does not exist, so a mistyped path walks "cleanly".
# Instead walk the closure in-process (write=False, nothing touches disk) and
# assert on the actual plan: which files are in it, what their rendered
# references were rewritten to, and what the rendered contract says.
closure_dump() {
    "$PYTHON" - "$PROJECT_DIR" "$TEMPLATE" "$1" "$2" <<'PY'
import sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / ".aitask-scripts" / "lib"))
import skill_template as st
entry, prof_yaml, out = (root / sys.argv[2]).resolve(), Path(sys.argv[3]).resolve(), Path(sys.argv[4])
profile = st._load_profile(prof_yaml)
plan = st.walk_closure(entry, profile, "claude", st._profile_name(profile, prof_yaml),
                       prof_yaml, root, write=False, force=False,
                       profile_filename=st._profile_filename(prof_yaml))
out.mkdir(parents=True, exist_ok=True)
with (out / "MEMBERS").open("w") as f:
    for _src, target, content in plan:
        rel = target.relative_to(root)
        f.write(str(rel) + "\n")
        dest = out / "files" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
PY
}

for variant in show ask show_headless ask_headless; do
    prof_name="$(sed -n 's/^name: //p' "$PA_TMPDIR/$variant.yaml")"
    dump="$PA_TMPDIR/closure_$variant"
    if ! closure_dump "$PA_TMPDIR/$variant.yaml" "$dump" 2>"$dump.err"; then
        assert_record_fail; echo "FAIL: closure/$variant: walk failed: $(cat "$dump.err")"
        continue
    fi
    wf=".claude/skills/task-workflow-${prof_name}-"
    members="$(cat "$dump/MEMBERS")"
    assert_contains "closure/$variant: the assessment procedure is a member" \
        "$wf/parallel-assessment.md" "$members"
    assert_contains "closure/$variant: the checker contract is a member" \
        "$wf/parallel-admission-checker.md" "$members"

    pick_body="$(cat "$dump/files/.claude/skills/aitask-pick-${prof_name}-/SKILL.md")"
    assess_body="$(cat "$dump/files/$wf/parallel-assessment.md")"
    checker_body="$(cat "$dump/files/$wf/parallel-admission-checker.md")"
    preflight_body="$(cat "$dump/files/$wf/parallel-admission.md")"

    # The references were REWRITTEN to this profile's rendered tree -- the edge
    # the agent will actually follow, not the source path.
    assert_contains "closure/$variant: pick references the rendered assessment" \
        "$wf/parallel-assessment.md" "$pick_body"
    assert_contains "closure/$variant: the assessment references the rendered checker" \
        "$wf/parallel-admission-checker.md" "$assess_body"
    assert_not_contains "closure/$variant: no source-tree path survives in the assessment" \
        ".claude/skills/task-workflow/parallel-admission-checker.md" "$assess_body"

    # Admission is off, so the preflight is a no-op that references nothing:
    # the checker contract's presence is owed to the assessment, not to it.
    assert_contains "closure/$variant: the preflight is off in this profile" \
        'is a **no-op**' "$preflight_body"
    # Only the Procedure section: the Notes render in every profile and name the
    # contract as documentation, which is not an instruction to run it.
    assert_not_contains "closure/$variant: the off preflight's procedure does not run the checker" \
        'parallel-admission-checker.md' "${preflight_body%%## Notes*}"

    # …and what arrives is the real contract.
    assert_contains "closure/$variant: checker carries the capture form" \
        'aitask_parallel_admission.sh check' "$checker_body"
    assert_contains "closure/$variant: checker keeps require-fresh" \
        '--lock-freshness require-fresh' "$checker_body"
    assert_contains "closure/$variant: checker carries the checker-unusable table" \
        '| more than one `VERDICT:` line | checker unusable' "$checker_body"
    assert_contains "closure/$variant: checker validates causes against the vocabulary" \
        'UNCHECKABLE_REASONS' "$checker_body"

    case "$variant" in
        *_headless)
            assert_not_contains "closure/$variant: rendered assessment never prompts" \
                'AskUserQuestion' "$assess_body" ;;
        *)
            assert_contains "closure/$variant: rendered attended assessment carries the prompt" \
                'AskUserQuestion' "$assess_body" ;;
    esac
done

# The checker contract is ungated: it must render identically whatever the
# profile says, because both callers -- including one whose own knob is off --
# read the same file.
checker_base="$($RENDER "$CHECKER" "$PROFILES_DIR/default.yaml" claude 2>&1)"
for profile in "${PROFILES[@]}"; do
    rendered="$($RENDER "$CHECKER" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    assert_eq "checker contract is profile-invariant ($profile)" "$checker_base" "$rendered"
done
assert_contains "checker: carries the capture form" \
    'aitask_parallel_admission.sh check' "$checker_base"
assert_contains "checker: require-fresh is mandatory" \
    '--lock-freshness require-fresh' "$checker_base"
assert_contains "checker: carries the checker-unusable classification" \
    'checker unusable' "$checker_base"
assert_contains "checker: --plan is documented as optional" \
    'only** optional part' "$checker_base"

# === Summary ===

echo ""
echo "Tests: $TOTAL, Passed: $PASS, Failed: $FAIL"
[[ "$FAIL" -eq 0 ]] || exit 1
