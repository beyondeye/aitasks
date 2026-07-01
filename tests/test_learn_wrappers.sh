#!/usr/bin/env bash
# test_learn_wrappers.sh - Tests for aitask_learn_wrappers.sh (t1100).
# Run: bash tests/test_learn_wrappers.sh
#
# Covers the generic cross-agent wrapper emitter used by aitask-learn-skill:
#   Case A - both agent trees present: render content (incl. negative assertion
#            that it is NOT the framework stub), emit WROTE, idempotent EXISTS.
#   Case B - Claude-only repo: emit SKIPs every tree and creates NOTHING
#            (negative control for the "only emit for present trees" rule).
#   Case C - unreadable source skill: emit fails fast (nonzero) and writes nothing.
#
# Runs entirely inside throwaway temp git repos so the real repo is never touched.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

HELPER="$PROJECT_DIR/.aitask-scripts/aitask_learn_wrappers.sh"

TMPDIRS=()
cleanup() {
    local d
    for d in "${TMPDIRS[@]}"; do
        [[ -n "$d" && -d "$d" ]] && rm -rf "$d"
    done
}
trap cleanup EXIT

# make_repo <with_trees:yes|no> <with_source:yes|no> -> echoes a fresh temp repo path.
make_repo() {
    local with_trees="$1" with_source="$2" d
    d="$(mktemp -d)"
    TMPDIRS+=("$d")
    (
        cd "$d"
        git init -q
        if [[ "$with_source" == "yes" ]]; then
            mkdir -p .claude/skills/zz
            printf -- '---\nname: zz\ndescription: Do a thing — really.\nuser-invocable: true\n---\n\nBody.\n' \
                > .claude/skills/zz/SKILL.md
        fi
        if [[ "$with_trees" == "yes" ]]; then
            mkdir -p .agents/skills .opencode
        fi
    )
    printf '%s\n' "$d"
}

# ============================================================
# Case A - both agent trees present
# ============================================================
echo "--- Case A: both trees present ---"
repo="$(make_repo yes yes)"

out=$(cd "$repo" && "$HELPER" render agents zz 2>&1)
assert_contains "render agents carries name"        "name: zz"                     "$out"
assert_contains "render agents carries description"  "Do a thing — really."         "$out"
assert_contains "render agents points at Claude file" ".claude/skills/zz/SKILL.md"  "$out"
# Negative: it must be the GENERIC stub, not the framework one.
assert_not_contains "render agents has no framework Source-of-Truth" "Source of Truth" "$out"
assert_not_contains "render agents has no codex tool mapping"        "codex_tool_mapping"    "$out"
assert_not_contains "render agents has no opencode tool mapping"     "opencode_tool_mapping" "$out"

out=$(cd "$repo" && "$HELPER" render opencode-command zz 2>&1)
assert_contains "opencode command @-includes Claude file" "@.claude/skills/zz/SKILL.md" "$out"
assert_contains "opencode command keeps \$ARGUMENTS literal" '$ARGUMENTS' "$out"
assert_not_contains "opencode command has no tool mapping include" "opencode_tool_mapping" "$out"

out=$(cd "$repo" && "$HELPER" emit zz 2>&1)
assert_contains "emit writes agents wrapper"           "WROTE:.agents/skills/zz/SKILL.md"   "$out"
assert_contains "emit writes opencode skill wrapper"   "WROTE:.opencode/skills/zz/SKILL.md" "$out"
assert_contains "emit writes opencode command wrapper" "WROTE:.opencode/commands/zz.md"     "$out"
assert_file_exists "agents wrapper file exists"           "$repo/.agents/skills/zz/SKILL.md"
assert_file_exists "opencode skill wrapper file exists"   "$repo/.opencode/skills/zz/SKILL.md"
assert_file_exists "opencode command wrapper file exists" "$repo/.opencode/commands/zz.md"

# Idempotent re-run: never clobbers.
out=$(cd "$repo" && "$HELPER" emit zz 2>&1)
assert_contains "re-emit reports agents EXISTS"           "EXISTS:.agents/skills/zz/SKILL.md"   "$out"
assert_contains "re-emit reports opencode skill EXISTS"   "EXISTS:.opencode/skills/zz/SKILL.md" "$out"
assert_contains "re-emit reports opencode command EXISTS" "EXISTS:.opencode/commands/zz.md"     "$out"

# ============================================================
# Case B - Claude-only repo (negative control for tree-gating)
# ============================================================
echo "--- Case B: Claude-only repo ---"
repo="$(make_repo no yes)"

rc=0
out=$(cd "$repo" && "$HELPER" emit zz 2>&1) || rc=$?
assert_exit_zero_rc "emit succeeds in Claude-only repo" "$rc"
assert_contains "agents tree skipped as absent"           "SKIP:agents:tree-absent"           "$out"
assert_contains "opencode skill tree skipped as absent"   "SKIP:opencode-skill:tree-absent"   "$out"
assert_contains "opencode command tree skipped as absent" "SKIP:opencode-command:tree-absent" "$out"
# The load-bearing assertion the both-trees case cannot make:
assert_dir_not_exists "no .agents dir created in Claude-only repo"   "$repo/.agents"
assert_dir_not_exists "no .opencode dir created in Claude-only repo" "$repo/.opencode"

# ============================================================
# Case C - unreadable source skill (fail-fast)
# ============================================================
echo "--- Case C: unreadable source ---"
repo="$(make_repo yes no)"

rc=0
out=$(cd "$repo" && "$HELPER" emit zz 2>&1) || rc=$?
assert_exit_nonzero_rc "emit fails fast on missing source" "$rc"
assert_contains "emit reports ERROR:source-unreadable" "ERROR:source-unreadable:zz" "$out"
assert_file_not_exists "no agents wrapper written on bad source"   "$repo/.agents/skills/zz/SKILL.md"
assert_file_not_exists "no opencode wrapper written on bad source" "$repo/.opencode/skills/zz/SKILL.md"

# ============================================================
# Summary
# ============================================================
echo ""
echo "=============================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=============================="

if [[ "$FAIL" -gt 0 ]]; then
    exit 1
fi
