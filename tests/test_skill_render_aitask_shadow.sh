#!/usr/bin/env bash
# test_skill_render_aitask_shadow.sh - Regression tests for t1311:
#   - .claude/skills/aitask-shadow/SKILL.md.j2 (entry-point template)
#   - impl-challenge.md, the one profile-bearing procedure file
#     (shadow_impl_review_tier gates the generic-ask tier fallback)
#   - 4 per-agent stubs (claude / codex / opencode command + opencode skill)
#   - 3 entry-point goldens under tests/golden/skills/aitask-shadow/
#   - 3 impl-challenge goldens under tests/golden/procs/aitask-shadow/
# Coverage:
#   1.  Per-profile golden diff for the entry-point template (claude render).
#   1b. Agent-dimension invariance for the entry point (no {% if agent %}).
#   1p. impl-challenge goldens per profile + agent invariance.
#   1i. The eight Jinja-free procedures render identically across every
#       (profile x agent) combination.
#   2.  Both arms of the shadow_impl_review_tier conditional.
#   2p. PRECEDENCE GUARD: the explicit-wording recognition table, the
#       no-implicit-Quick line, and the whole Angle scoping block survive in
#       EVERY render, `fast` included. Without this, gating the tier section
#       wholesale would delete the recognition table from the profile-tier
#       render and there would be no basis left for honoring "deep review".
#   2g. The "too early to review" gate is gone and the review-state
#       assessment's composite four-channel resolution is present.
#   3.  No Jinja markers leak into entry-point or procedure renders.
#   3b. Rendered output must NOT re-resolve profile (t777_26 forbidden tokens).
#   4.  Per-agent reference rewrites for the impl-challenge full-path refs.
#   5.  Stub markers present on all 4 stub surfaces.
# Run: bash tests/test_skill_render_aitask_shadow.sh

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
SKILL_DIR=".claude/skills/aitask-shadow"
TEMPLATE="$SKILL_DIR/SKILL.md.j2"
SKILL_GOLDEN_DIR="tests/golden/skills/aitask-shadow"
PROC_GOLDEN_DIR="tests/golden/procs/aitask-shadow"
PROFILES_DIR="aitasks/metadata/profiles"

PROFILES=(default fast remote)
AGENTS=(claude codex opencode)

# impl-challenge is the only procedure carrying Jinja; the other eight are
# identity transforms and are covered by the invariance sweep in Test 1i.
PROC_FILES_VARYING=(impl-challenge)
PROC_FILES_INVARIANT=(
    concern-format
    impl-review-angles
    plan-assumptions
    plan-challenge
    plan-diagnose-errors
    plan-explain
    plan-socratic
    spawn-learn-skill
)
PROC_FILES=("${PROC_FILES_VARYING[@]}" "${PROC_FILES_INVARIANT[@]}")

# === Test 1: per-profile entry-point golden diffs (claude render is canonical) ===

echo "=== Test 1: golden diffs for entry-point × 3 profiles ==="
for profile in "${PROFILES[@]}"; do
    rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    golden_content="$(cat "$SKILL_GOLDEN_DIR/SKILL-${profile}-claude.md")"
    assert_eq "golden SKILL × $profile" "$golden_content" "$rendered"
done

# === Test 1b: entry-point agent dimension invariance ===
#
# The entry-point template has no {% if agent %} gate, so the basic stdout
# render is byte-identical across agents. Fails LOUDLY if agent gating is
# ever added (which would also require per-agent goldens).
echo "=== Test 1b: agent renders are byte-identical (no {% if agent %} in template) ==="
for profile in "${PROFILES[@]}"; do
    base="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    for agent in codex opencode; do
        cmp="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" "$agent" 2>&1)"
        assert_eq "agent invariance $profile/$agent" "$base" "$cmp"
    done
done

# === Test 1p: impl-challenge golden diffs + agent invariance ===

echo "=== Test 1p: impl-challenge goldens × 3 profiles + agent invariance ==="
for f in "${PROC_FILES_VARYING[@]}"; do
    for profile in "${PROFILES[@]}"; do
        rendered="$($RENDER "$SKILL_DIR/$f.md" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
        golden_content="$(cat "$PROC_GOLDEN_DIR/$f-$profile.md")"
        assert_eq "golden proc $f × $profile" "$golden_content" "$rendered"
        for agent in codex opencode; do
            other="$($RENDER "$SKILL_DIR/$f.md" "$PROFILES_DIR/$profile.yaml" "$agent" 2>&1)"
            assert_eq "proc $f × $profile agent-invariant ($agent==claude)" "$rendered" "$other"
        done
    done
done

# === Test 1i: the Jinja-free procedures are profile- and agent-invariant ===
#
# They carry no conditionals at all, so they render as identity transforms and
# need no goldens. This assertion is what makes that claim checkable: adding a
# conditional to any of them fails here and says "give this file goldens".

echo "=== Test 1i: Jinja-free procedures invariant across profile × agent ==="
for f in "${PROC_FILES_INVARIANT[@]}"; do
    base="$($RENDER "$SKILL_DIR/$f.md" "$PROFILES_DIR/default.yaml" claude 2>&1)"
    for profile in "${PROFILES[@]}"; do
        for agent in "${AGENTS[@]}"; do
            cmp="$($RENDER "$SKILL_DIR/$f.md" "$PROFILES_DIR/$profile.yaml" "$agent" 2>&1)"
            assert_eq "proc $f invariance $profile/$agent" "$base" "$cmp"
        done
    done
done

# === Test 2: both arms of the shadow_impl_review_tier conditional ===
#
# `fast` sets shadow_impl_review_tier: advanced -> the if arm bakes the tier in
# and the prompt is gone. `default` / `remote` leave it unset -> the else arm
# keeps the 4-option AskUserQuestion and no baked announce line.

echo "=== Test 2: shadow_impl_review_tier branches fire correctly ==="
for profile in "${PROFILES[@]}"; do
    ic="$($RENDER "$SKILL_DIR/impl-challenge.md" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    if [[ "$profile" == "fast" ]]; then
        assert_contains "$profile: if arm bakes the profile tier" \
            "run **advanced** — the tier configured by profile" "$ic"
        assert_contains "$profile: if arm names the source profile" \
            "'fast' via \`shadow_impl_review_tier\`" "$ic"
        assert_contains "$profile: if arm forbids asking" "Do **NOT** ask." "$ic"
        assert_not_contains "$profile: no tier prompt in the if arm" \
            'AskUserQuestion` (Header "Review tier")' "$ic"
        assert_not_contains "$profile: no Review tier header at all" \
            "Review tier" "$ic"
    else
        assert_contains "$profile: else arm keeps the tier prompt" \
            'AskUserQuestion` (Header "Review tier")' "$ic"
        assert_contains "$profile: else arm keeps the Advanced recommendation" \
            "Advanced (Recommended)" "$ic"
        assert_not_contains "$profile: no baked profile tier" \
            "the tier configured by profile" "$ic"
    fi
    # Resolution order must read as an ordered decision in EVERY render.
    assert_contains "$profile: resolution order stated" \
        "Resolution order (apply in this order)" "$ic"
    assert_contains "$profile: user-named tier wins over the profile" \
        "always wins, including over a profile" "$ic"
done

# === Test 2p: precedence guard — the recognition table survives every render ===
#
# This is the assertion that would have caught the original design's
# disappearing recognition table. Gating the whole Tier-selection section (the
# way qa_tier gates its own) would strip these lines from the `fast` render,
# leaving the "a tier named in the user's ask still wins" promise with no
# mapping behind it. They must be UNCONDITIONAL.

echo "=== Test 2p: explicit-wording recognition table present in every render ==="
RECOGNITION_LINES=(
    '"quick" / "fast" → **Quick**'
    '"default" / "basic" / "legacy"'
    '"advanced" / "standard" / "normal" → **Advanced**'
    '"deep" / "thorough" / "max" / "exhaustive" → **Deep**'
    'Nothing routes to Quick implicitly'
    '**Angle scoping (user intent wins).**'
    'State the chosen tier (and any angle scoping)'
    '**Announce an inferred tier (required).**'
)
for profile in "${PROFILES[@]}"; do
    ic="$($RENDER "$SKILL_DIR/impl-challenge.md" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
    for line in "${RECOGNITION_LINES[@]}"; do
        assert_contains "$profile: unconditional — '$line'" "$line" "$ic"
    done
done

# === Test 2g: the gate is gone, the review-state assessment is in ===

echo "=== Test 2g: review-state assessment replaced the 'too early' gate ==="
for profile in "${PROFILES[@]}"; do
    ic="$($RENDER "$SKILL_DIR/impl-challenge.md" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"

    # The gate and its abort/proceed prompt must be gone entirely.
    assert_not_contains "$profile: no 'too early to review' gate heading" \
        "Too early to review" "$ic"
    assert_not_contains "$profile: no 'probably too early' warning" \
        "probably too early" "$ic"
    assert_not_contains "$profile: no abort/proceed-anyway prompt" \
        "proceed anyway" "$ic"

    # The assessment, and the four composite channels.
    assert_contains "$profile: assessment heading present" \
        "## Review-state assessment (required — run first, every tier)" "$ic"
    assert_contains "$profile: assessment states rather than prompts" \
        "it does not prompt" "$ic"
    assert_contains "$profile: composite, not a precedence chain" \
        "COMPOSITE, not a precedence chain" "$ic"
    assert_contains "$profile: committed channel yields paths, not just subjects" \
        "git diff-tree -r --no-commit-id --name-only -z" "$ic"
    assert_contains "$profile: staged channel" "git diff --cached --name-only -z" "$ic"
    assert_contains "$profile: unstaged channel" "git diff --name-only -z" "$ic"
    assert_contains "$profile: untracked channel" \
        "git ls-files --others --exclude-standard -z" "$ic"

    # Path safety: the truncating porcelain read is stated as a prohibition,
    # and the old command form that DID it is gone.
    # shellcheck disable=SC2016  # the backticks are literal markdown in the procedure, not command substitution
    assert_contains "$profile: porcelain enumeration prohibited by name" \
        'never from `git status --short`' "$ic"
    assert_not_contains "$profile: old porcelain command form removed" \
        "git status --short   # what changed" "$ic"
    assert_contains "$profile: NUL-safe consumption loop" \
        "while IFS= read -r -d '' path" "$ic"

    # Notes-absent is normal; only an empty composite stops the run.
    assert_contains "$profile: notes-absent is the normal case" \
        "Notes absent (the normal pre-commit case)" "$ic"
    assert_contains "$profile: notes-absent neither warns nor prompts" \
        "**no warning, no prompt.**" "$ic"
    assert_contains "$profile: empty composite is the only stop" \
        "the *only* stop" "$ic"
    # AC 2: a missing plan degrades the run distinctly — it neither blocks nor
    # is silently reviewed as if S1/S2 had simply found nothing.
    assert_contains "$profile: no-plan degrades rather than blocks" \
        "**No plan at all** — continue, code-only" "$ic"
    assert_contains "$profile: no-plan names the unavailable angles" \
        "angles S1 and S2" "$ic"
    # AC 1: the disclosure obligation lives here, once, and covers the whole run.
    assert_contains "$profile: disclosure obligation is stated once, here" \
        "carries the \"tell the user what you reviewed\" obligation" "$ic"
    assert_contains "$profile: attribution limit is stated, not prompted" \
        "possibly unrelated to this task" "$ic"
done

# The angle catalog carries the notes-absent semantics for S1/S2 (it is
# Jinja-free, so one render is representative — Test 1i proves that).
angles="$($RENDER "$SKILL_DIR/impl-review-angles.md" "$PROFILES_DIR/fast.yaml" claude 2>&1)"
assert_contains "angles: S1 notes-absent mode" "judge each plan risk's status from the **diff alone**" "$angles"
assert_contains "angles: S2 pending-narration classification" "pending narration" "$angles"
assert_contains "angles: S2 keeps merit-based deviations blocking-eligible" \
    "wrong on its own merits" "$angles"

# === Test 3: no Jinja markers leak ===

echo "=== Test 3: rendered output has no Jinja markers ==="
for profile in "${PROFILES[@]}"; do
    for agent in "${AGENTS[@]}"; do
        rendered="$($RENDER "$TEMPLATE" "$PROFILES_DIR/$profile.yaml" "$agent" 2>&1)"
        assert_not_contains "no Jinja {% leak SKILL × $profile × $agent" "{%" "$rendered"
        assert_not_contains "no Jinja {{ leak SKILL × $profile × $agent" "{{" "$rendered"
    done
    for f in "${PROC_FILES[@]}"; do
        rendered="$($RENDER "$SKILL_DIR/$f.md" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
        assert_not_contains "no Jinja {% leak $f × $profile" "{%" "$rendered"
        assert_not_contains "no Jinja {{ leak $f × $profile" "{{" "$rendered"
    done
done

# === Test 3b: rendered body must NOT re-resolve profile at runtime (t777_26) ===

echo "=== Test 3b: rendered output has no runtime profile-resolution tokens ==="
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
            assert_not_contains "SKILL $profile × $agent has no '$token'" \
                "$token" "$rendered"
        done
    done
    for f in "${PROC_FILES[@]}"; do
        rendered="$($RENDER "$SKILL_DIR/$f.md" "$PROFILES_DIR/$profile.yaml" claude 2>&1)"
        for token in "${FORBIDDEN_TOKENS[@]}"; do
            assert_not_contains "$f $profile has no '$token'" "$token" "$rendered"
        done
    done
done

# === Test 4: cross-agent reference rewrites (via walk-write on-disk output) ===
#
# impl-challenge.md carries two full-path refs into its own skill dir
# (impl-review-angles.md, concern-format.md); those must be rewritten to the
# per-agent rendered dir. The nine sub-procedures must all land in the closure
# for every agent — the first time they reach the Codex / OpenCode trees at all.

echo "=== Test 4: per-agent reference rewrites + closure completeness via walk-write ==="
for agent in "${AGENTS[@]}"; do
    ./.aitask-scripts/aitask_skill_render.sh aitask-shadow --profile fast --agent "$agent" --force >/dev/null 2>&1
done

assert_contains "claude/fast: impl-review-angles ref rewritten under .claude/skills" \
    ".claude/skills/aitask-shadow-fast-/impl-review-angles.md" \
    "$(cat .claude/skills/aitask-shadow-fast-/impl-challenge.md)"
assert_contains "codex/fast: concern-format ref rewritten under .agents/skills" \
    ".agents/skills/aitask-shadow-fast-codex-/concern-format.md" \
    "$(cat .agents/skills/aitask-shadow-fast-codex-/impl-challenge.md)"
assert_contains "opencode/fast: concern-format ref rewritten under .opencode/skills" \
    ".opencode/skills/aitask-shadow-fast-/concern-format.md" \
    "$(cat .opencode/skills/aitask-shadow-fast-/impl-challenge.md)"

for f in "${PROC_FILES[@]}" SKILL; do
    assert_eq "claude/fast: $f.md rendered into the closure" "yes" \
        "$([[ -f ".claude/skills/aitask-shadow-fast-/$f.md" ]] && echo yes || echo no)"
    assert_eq "codex/fast: $f.md rendered into the closure" "yes" \
        "$([[ -f ".agents/skills/aitask-shadow-fast-codex-/$f.md" ]] && echo yes || echo no)"
    assert_eq "opencode/fast: $f.md rendered into the closure" "yes" \
        "$([[ -f ".opencode/skills/aitask-shadow-fast-/$f.md" ]] && echo yes || echo no)"
done

# === Test 5: stub-marker checks (4 surfaces) ===

echo "=== Test 5: 4 stub files contain canonical markers ==="
CLAUDE_STUB=".claude/skills/aitask-shadow/SKILL.md"
CODEX_STUB=".agents/skills/aitask-shadow/SKILL.md"
OPENCODE_CMD_STUB=".opencode/commands/aitask-shadow.md"
OPENCODE_SKILL_STUB=".opencode/skills/aitask-shadow/SKILL.md"

for stub in "$CLAUDE_STUB" "$CODEX_STUB" "$OPENCODE_CMD_STUB" "$OPENCODE_SKILL_STUB"; do
    body="$(cat "$stub")"
    assert_contains "$stub: resolve_profile uses short name 'shadow'" \
        "aitask_skill_resolve_profile.sh shadow" "$body"
    assert_not_contains "$stub: resolve_profile does NOT use full slug 'aitask-shadow'" \
        "aitask_skill_resolve_profile.sh aitask-shadow" "$body"
    assert_contains "$stub: skill render invocation present" \
        "aitask_skill_render.sh aitask-shadow" "$body"
    assert_contains "$stub: Read-and-follow marker present" \
        "Dispatch via Read-and-follow" "$body"
    # The pre-templating redirect must be gone from every surface.
    assert_not_contains "$stub: no legacy 'Source of Truth' redirect" \
        "Source of Truth" "$body"
done

# Per-agent agent_literal substitution checks
assert_contains "claude stub: --agent claude" "--agent claude" "$(cat "$CLAUDE_STUB")"
assert_contains "codex stub: --agent codex" "--agent codex" "$(cat "$CODEX_STUB")"
assert_contains "opencode cmd stub: --agent opencode" "--agent opencode" "$(cat "$OPENCODE_CMD_STUB")"
assert_contains "opencode skill stub: --agent opencode" "--agent opencode" "$(cat "$OPENCODE_SKILL_STUB")"

# Per-agent rendered-variant Read target checks
assert_contains "claude stub: reads from .claude/skills/aitask-shadow-<profile>-" \
    ".claude/skills/aitask-shadow-<profile>-/SKILL.md" "$(cat "$CLAUDE_STUB")"
assert_contains "codex stub: reads from .agents/skills/aitask-shadow-<profile>-codex-" \
    ".agents/skills/aitask-shadow-<profile>-codex-/SKILL.md" "$(cat "$CODEX_STUB")"
assert_contains "opencode cmd stub: reads from .opencode/skills/aitask-shadow-<profile>-" \
    ".opencode/skills/aitask-shadow-<profile>-/SKILL.md" "$(cat "$OPENCODE_CMD_STUB")"
assert_contains "opencode skill stub: reads from .opencode/skills/aitask-shadow-<profile>-" \
    ".opencode/skills/aitask-shadow-<profile>-/SKILL.md" "$(cat "$OPENCODE_SKILL_STUB")"

# The launcher's positional argument contract must survive the conversion:
# minimonitor spawns `/aitask-shadow <followed_pane_id> [<source_task_id>]`, so
# the stub must forward ARGUMENTS rather than consume them.
for stub in "$CLAUDE_STUB" "$CODEX_STUB" "$OPENCODE_CMD_STUB" "$OPENCODE_SKILL_STUB"; do
    assert_contains "$stub: forwards ARGUMENTS to the rendered variant" \
        "ARGUMENTS unchanged" "$(cat "$stub")"
done

# === Summary ===

echo ""
echo "Tests: $TOTAL, Passed: $PASS, Failed: $FAIL"
[[ "$FAIL" -eq 0 ]] || exit 1
