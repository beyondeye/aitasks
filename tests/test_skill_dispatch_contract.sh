#!/usr/bin/env bash
# test_skill_dispatch_contract.sh — Dispatch-contract smoke for t1317.
#
# Guards the stub -> rendered-variant dispatch path for EVERY templated skill x
# EVERY agent surface. Subjects are DISCOVERED at runtime (the same
# `find .claude/skills -name SKILL.md.j2` that aitask_skill_verify.sh:35-37
# uses), never hardcoded — so a newly converted skill is covered the moment its
# template lands.
#
# Per (skill, surface) it asserts:
#   1. The stub exists.
#   2. The stub's Step-3 dispatch target — PARSED out of the stub body, never
#      reconstructed — equals the path the canonical seam
#      lib/agent_skills_paths.sh::agent_skill_dir computes for that agent. This
#      is what fails a codex stub missing the `-codex-` shared-root segment.
#   3. Rendering actually produces the path the stub names.
#   4. The rendered closure is complete: every *.md in the authoring dir has a
#      counterpart in the rendered dir (a skill whose sub-procedures never reach
#      the Codex/OpenCode trees fails loudly).
#   5. The stub's resolver key runs: exit 0 and exactly one non-empty line.
#
# Complements .aitask-scripts/aitask_skill_verify.sh rather than duplicating it.
# That script greps the Read path against its own restatement of the §3g table
# and never renders to disk, never executes the resolver, never checks
# `.opencode/skills/<skill>/SKILL.md`, and never checks closure completeness.
#
# The §3g per-agent surface table (aidocs/framework/stub-skill-pattern.md) is
# the single source of truth for rendered-path shapes; it is NOT restated here —
# the expectation comes from agent_skill_dir and from the stub itself.
#
# Run: bash tests/test_skill_dispatch_contract.sh

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

# Canonical seam for rendered-dir naming — reused, not restated.
# shellcheck source=.aitask-scripts/lib/agent_skills_paths.sh
source "$PROJECT_DIR/.aitask-scripts/lib/agent_skills_paths.sh"

RENDER="$PROJECT_DIR/.aitask-scripts/aitask_skill_render.sh"
RESOLVE="$PROJECT_DIR/.aitask-scripts/aitask_skill_resolve_profile.sh"

# One profile is enough: the stub body is profile-agnostic by contract
# (stub-skill-pattern.md §3b/§3f), so the dispatch shape is profile-invariant.
# `default` also keeps the test away from the COMMITTED `*-remote-` prerender
# dirs that .gitignore un-ignores.
PROFILE="default"

# Surfaces. Only the STUB locations appear here; every rendered path is derived
# from agent_skill_dir. OpenCode has two stubs that dispatch to one rendered dir.
SURFACES="claude codex opencode-cmd opencode-skill"

# Scratch control fixture (Test 3). Prefix makes cleanup unambiguous.
CTRL="_t1317_ctrl"

cleanup() {
    # shellcheck disable=SC2115
    rm -rf "$PROJECT_DIR"/.claude/skills/"${CTRL}"* \
           "$PROJECT_DIR"/.agents/skills/"${CTRL}"* \
           "$PROJECT_DIR"/.opencode/skills/"${CTRL}"* \
           "$PROJECT_DIR"/.opencode/commands/"${CTRL}".md
}
trap cleanup EXIT
# Pre-clean in case a prior aborted run left scratch dirs behind.
cleanup

# Memo of already-rendered "<skill>|<agent>" pairs so the two OpenCode surfaces
# do not pay for the same render twice. Mutated by check_surface, which
# therefore must run in the CURRENT shell (never inside a command substitution)
# for the main loop.
RENDERED_KEYS=" "

agent_for() {
    case "$1" in
        claude)                       echo "claude" ;;
        codex)                        echo "codex" ;;
        opencode-cmd|opencode-skill)  echo "opencode" ;;
        *) echo "agent_for: unknown surface: $1" >&2; return 1 ;;
    esac
}

stub_path_for() {
    case "$1" in
        claude)          echo ".claude/skills/$2/SKILL.md" ;;
        codex)           echo ".agents/skills/$2/SKILL.md" ;;
        opencode-cmd)    echo ".opencode/commands/$2.md" ;;
        opencode-skill)  echo ".opencode/skills/$2/SKILL.md" ;;
        *) echo "stub_path_for: unknown surface: $1" >&2; return 1 ;;
    esac
}

# check_surface <skill> <surface>
# Prints one "  - <problem>" line per problem to stdout.
# Returns 0 when the surface is clean, 1 when any problem was found.
check_surface() {
    local skill="$1" surface="$2"
    local agent stub problems=0
    agent="$(agent_for "$surface")"
    stub="$(stub_path_for "$surface" "$skill")"

    # --- 1. Stub exists ---------------------------------------------------
    if [[ ! -f "$stub" ]]; then
        echo "  - missing stub: $stub"
        return 1
    fi

    # --- 2. Step-3 dispatch target, parsed from the stub body -------------
    # Shape: a backticked path carrying the literal <profile> placeholder and
    # ending in /SKILL.md, e.g. `.agents/skills/aitask-pick-<profile>-codex-/SKILL.md`
    local parsed expected_dir expected resolved
    # shellcheck disable=SC2016  # the backticks are literal markdown in the stub, not command substitution
    parsed="$(grep -oE '`[^`]*-<profile>-[^`]*/SKILL\.md`' "$stub" | head -n1 | tr -d '`')"
    if [[ -z "$parsed" ]]; then
        echo "  - $stub: no Step-3 dispatch target found" \
             "(expected a backticked '<root>/<skill>-<profile>-[<agent>-]/SKILL.md' path)"
        return 1
    fi

    expected_dir="$(agent_skill_dir "$agent" "$skill" "$PROFILE")"
    expected="$expected_dir/SKILL.md"
    resolved="${parsed//<profile>/$PROFILE}"

    if [[ "$resolved" != "$expected" ]]; then
        echo "  - $stub: Step-3 target '$parsed' resolves to '$resolved'," \
             "but agent_skill_dir($agent) says '$expected'"
        problems=1
    fi

    # --- 3. Rendering produces the path the STUB names --------------------
    local memo_key=" ${skill}|${agent} "
    if [[ "$RENDERED_KEYS" != *"$memo_key"* ]]; then
        if "$RENDER" "$skill" --profile "$PROFILE" --agent "$agent" >/dev/null 2>&1; then
            RENDERED_KEYS="${RENDERED_KEYS}${skill}|${agent} "
        else
            echo "  - render failed: aitask_skill_render.sh $skill --profile $PROFILE --agent $agent"
            return 1
        fi
    fi
    if [[ ! -f "$resolved" ]]; then
        echo "  - $stub: rendering did not produce the stub's Step-3 target: $resolved"
        problems=1
    fi

    # --- 4. Rendered closure is complete ----------------------------------
    # Every *.md in the authoring dir must have a same-named counterpart in the
    # rendered dir. The stub SKILL.md maps 1:1 onto the .j2-rendered SKILL.md.
    local src base
    for src in ".claude/skills/$skill"/*.md; do
        [[ -e "$src" ]] || continue
        base="$(basename "$src")"
        if [[ ! -f "$expected_dir/$base" ]]; then
            echo "  - $skill [$agent]: closure incomplete —" \
                 "authoring file '$base' has no counterpart in $expected_dir/"
            problems=1
        fi
    done

    # --- 5. Resolver key resolves -----------------------------------------
    local key out rc line_count
    key="$(grep -oE 'aitask_skill_resolve_profile\.sh [A-Za-z0-9_-]+' "$stub" \
           | head -n1 | awk '{print $2}')"
    if [[ -z "$key" ]]; then
        echo "  - $stub: no resolver call found" \
             "(expected 'aitask_skill_resolve_profile.sh <key>')"
        problems=1
    else
        # `|| rc=$?` keeps this in a condition context: toggling `set -e` here
        # would clobber the caller's errexit state (probe() relies on it).
        rc=0
        out="$("$RESOLVE" "$key" 2>/dev/null)" || rc=$?
        if [[ "$rc" -ne 0 ]]; then
            echo "  - $stub: resolver key '$key' exited $rc"
            problems=1
        elif [[ -z "$out" ]]; then
            echo "  - $stub: resolver key '$key' printed nothing"
            problems=1
        else
            line_count="$(printf '%s\n' "$out" | wc -l | tr -d ' ')"
            if [[ "$line_count" != "1" ]]; then
                echo "  - $stub: resolver key '$key' printed $line_count lines, expected 1"
                problems=1
            fi
        fi
    fi

    return "$problems"
}

# ============================================================================
# Discovery — mirrors aitask_skill_verify.sh:35-37. NEVER a hardcoded list.
# ============================================================================

SKILLS=()
while IFS= read -r tpl; do
    [[ -n "$tpl" ]] || continue
    SKILLS+=("$(basename "$(dirname "$tpl")")")
done < <(find ".claude/skills" -mindepth 2 -maxdepth 3 -name 'SKILL.md.j2' -type f 2>/dev/null | sort)

echo "=== Test 1: discovery ==="
TOTAL=$((TOTAL + 1))
if [[ ${#SKILLS[@]} -gt 0 ]]; then
    PASS=$((PASS + 1))
    echo "Discovered ${#SKILLS[@]} templated skill(s): ${SKILLS[*]}"
else
    FAIL=$((FAIL + 1))
    echo "FAIL: no SKILL.md.j2 templates discovered under .claude/skills"
fi

# ============================================================================
# Test 2 — dispatch contract for every templated skill x every agent surface
# ============================================================================

echo ""
echo "=== Test 2: dispatch contract (skill x surface, profile=$PROFILE) ==="
for skill in "${SKILLS[@]}"; do
    for surface in $SURFACES; do
        TOTAL=$((TOTAL + 1))
        if check_surface "$skill" "$surface"; then
            PASS=$((PASS + 1))
        else
            FAIL=$((FAIL + 1))
            echo "FAIL: dispatch contract: $skill [$surface]"
        fi
    done
done

# ============================================================================
# Test 3 — negative controls: the assertions above are load-bearing
#
# A passing suite proves nothing unless a weakened contract actually breaks it.
# Each control mutates a SCRATCH fixture only — never a committed file — so the
# restore is `rm -rf` of the scratch dirs (trap cleanup EXIT), explicitly NOT
# `git checkout`, which would also discard unrelated in-flight work.
# ============================================================================

echo ""
echo "=== Test 3: negative controls ==="

CTRL_CLAUDE_DIR="$PROJECT_DIR/.claude/skills/$CTRL"
CTRL_CODEX_DIR="$PROJECT_DIR/.agents/skills/$CTRL"
CTRL_OC_SKILL_DIR="$PROJECT_DIR/.opencode/skills/$CTRL"
CTRL_OC_CMD="$PROJECT_DIR/.opencode/commands/$CTRL.md"

mkdir -p "$CTRL_CLAUDE_DIR" "$CTRL_CODEX_DIR" "$CTRL_OC_SKILL_DIR"

cat > "$CTRL_CLAUDE_DIR/SKILL.md.j2" <<'EOF'
---
name: _t1317_ctrl-{{ profile.name }}
description: t1317 dispatch-contract control fixture.
---

# Control fixture (agent={{ agent }}, profile={{ profile.name }})

See ctrl_proc.md for the procedure.
EOF

cat > "$CTRL_CLAUDE_DIR/ctrl_proc.md" <<'EOF'
# Control procedure

Referenced as a sibling from the control fixture's entry template.
EOF

# write_ctrl_stub <dest> <agent-literal> <target-path>
write_ctrl_stub() {
    cat > "$1" <<EOF
---
name: $CTRL
description: t1317 dispatch-contract control fixture.
---

This is a profile-aware skill stub. Execute these steps in order, then stop:

1. **Resolve active profile.** Otherwise run:
   \`./.aitask-scripts/aitask_skill_resolve_profile.sh $CTRL\`
   and use the single-line stdout as \`<profile>\`.

2. **Render per-profile variant.** Run:
   \`./.aitask-scripts/aitask_skill_render.sh $CTRL --profile <profile> --agent $2\`

3. **Dispatch via Read-and-follow.** Read the file at
   \`$3\` and execute its instructions as if they were this skill.
EOF
}

write_ctrl_stubs() {
    write_ctrl_stub "$CTRL_CLAUDE_DIR/SKILL.md"   claude   ".claude/skills/$CTRL-<profile>-/SKILL.md"
    write_ctrl_stub "$CTRL_CODEX_DIR/SKILL.md"    codex    ".agents/skills/$CTRL-<profile>-codex-/SKILL.md"
    write_ctrl_stub "$CTRL_OC_SKILL_DIR/SKILL.md" opencode ".opencode/skills/$CTRL-<profile>-/SKILL.md"
    write_ctrl_stub "$CTRL_OC_CMD"                opencode ".opencode/skills/$CTRL-<profile>-/SKILL.md"
}
write_ctrl_stubs

# probe <skill> <surface> -> echoes "clean" | "problems"
probe() {
    local rc=0
    check_surface "$1" "$2" >/dev/null 2>&1 || rc=$?
    [[ "$rc" -eq 0 ]] && echo "clean" || echo "problems"
}

# --- 3a. Positive control: a correct fixture passes all four surfaces ------
# Without this, a failing negative control could just mean the fixture is
# broken in some unrelated way.
for surface in $SURFACES; do
    assert_eq "positive control: correct fixture is clean [$surface]" \
        "clean" "$(probe "$CTRL" "$surface")"
done

# --- 3b. NC-1: stub names a dispatch target nothing produces --------------
write_ctrl_stub "$CTRL_CLAUDE_DIR/SKILL.md" claude ".claude/skills/$CTRL-WRONG-<profile>-/SKILL.md"
assert_eq "NC-1: mutation is real (stub target rewritten)" "differ" \
    "$(grep -qF "$CTRL-WRONG-<profile>-" "$CTRL_CLAUDE_DIR/SKILL.md" && echo differ || echo same)"
assert_eq "NC-1: wrong Step-3 dispatch target IS caught" \
    "problems" "$(probe "$CTRL" "claude")"
write_ctrl_stubs   # restore by rewriting the fixture — not git checkout

# --- 3c. NC-2: codex stub missing the -codex- shared-root segment ----------
# This is the exact t1311 failure mode the mitigation exists for.
write_ctrl_stub "$CTRL_CODEX_DIR/SKILL.md" codex ".agents/skills/$CTRL-<profile>-/SKILL.md"
assert_eq "NC-2: mutation is real (-codex- segment stripped)" "differ" \
    "$(grep -qF "$CTRL-<profile>-codex-" "$CTRL_CODEX_DIR/SKILL.md" && echo same || echo differ)"
assert_eq "NC-2: codex stub missing -codex- segment IS caught" \
    "problems" "$(probe "$CTRL" "codex")"
write_ctrl_stubs   # restore

# --- 3d. NC-3: an authoring-dir procedure that never reaches the closure ---
cat > "$CTRL_CLAUDE_DIR/orphan_proc.md" <<'EOF'
# Orphan procedure — referenced by nothing, so the dep-walker never renders it.
EOF
assert_eq "NC-3: mutation is real (orphan procedure present)" "yes" \
    "$([[ -f "$CTRL_CLAUDE_DIR/orphan_proc.md" ]] && echo yes || echo no)"
assert_eq "NC-3: incomplete rendered closure IS caught" \
    "problems" "$(probe "$CTRL" "claude")"
rm -f "$CTRL_CLAUDE_DIR/orphan_proc.md"   # restore

# --- 3e. Post-restore: the fixture is clean again --------------------------
assert_eq "post-restore: fixture clean again [claude]" \
    "clean" "$(probe "$CTRL" "claude")"
assert_eq "post-restore: fixture clean again [codex]" \
    "clean" "$(probe "$CTRL" "codex")"

# ============================================================================
# Summary
# ============================================================================

echo ""
echo "Tests: $TOTAL, Passed: $PASS, Failed: $FAIL"
[[ "$FAIL" -eq 0 ]] || exit 1
