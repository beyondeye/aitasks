#!/usr/bin/env bash
# test_shadow_spawn_config.sh - Tests for the t986_5 shadow spawn glue config.
# Run: bash tests/test_shadow_spawn_config.sh
#
# Covers:
#   1. The `shadow` codeagent operation resolves through the agent-string chain
#      and emits the `/aitask-shadow <pane> [<task>]` slash command per agent
#      (claudecode / opencode / codex). No live tmux — pure --dry-run.
#   2. `shadow` is a supported operation (and an unknown op still errors).
#   3. `resolve_pane_id_by_pid()` matches a pid against faked list-panes output
#      (the helper the launcher uses to find the new shadow pane's id).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

CODEAGENT="$PROJECT_DIR/.aitask-scripts/aitask_codeagent.sh"

# ============================================================
# Tests: dry-run resolution of the shadow operation
# ============================================================
echo "--- codeagent dry-run resolution ---"

# Default agent (codeagent_config.json defaults.shadow → claudecode/opus4_8).
out=$("$CODEAGENT" --dry-run invoke shadow %5 986_5 2>&1)
assert_contains "default shadow resolves to claude" "claude" "$out"
assert_contains "default shadow emits /aitask-shadow with args" "/aitask-shadow" "$out"
assert_contains "default shadow passes pane id" "%5" "$out"
assert_contains "default shadow passes task id" "986_5" "$out"

# Explicit claudecode.
out=$("$CODEAGENT" --agent-string claudecode/opus4_8 --dry-run invoke shadow %7 2>&1)
assert_contains "claudecode shadow (pane only)" "/aitask-shadow" "$out"
assert_contains "claudecode shadow pane id" "%7" "$out"

# OpenCode uses --prompt with the slash command.
out=$("$CODEAGENT" --agent-string opencode/opencode_claude_sonnet_4_6 \
    --dry-run invoke shadow %7 100_2 2>&1)
assert_contains "opencode shadow uses --prompt" "--prompt" "$out"
assert_contains "opencode shadow emits /aitask-shadow" "/aitask-shadow" "$out"

# Codex is analysis-style (default mode), NOT routed through the /plan PTY
# helper. The dry-run command must be a direct codex invocation, not the
# aitask_codex_plan_invoke.py wrapper.
out=$("$CODEAGENT" --agent-string codex/gpt5_5 --dry-run invoke shadow %7 100_2 2>&1)
assert_contains "codex shadow builds composer prompt" "aitask-shadow" "$out"
assert_not_contains "codex shadow does NOT force plan mode" "aitask_codex_plan_invoke" "$out"

# ============================================================
# Tests: operation support
# ============================================================
echo "--- operation support ---"

assert_exit_zero "shadow is a supported operation" \
    "$CODEAGENT" --dry-run invoke shadow %1
assert_exit_nonzero "an unknown operation is still rejected" \
    "$CODEAGENT" --dry-run invoke bogus-op %1

# Codex plan policy: shadow must be a relaxed (default-mode) skill, like qa/explain.
# shellcheck source=/dev/null
. "$PROJECT_DIR/.aitask-scripts/lib/codex_plan_policy.sh"
rc=0; codex_skill_forces_plan_mode shadow || rc=$?
assert_exit_nonzero_rc "codex_skill_forces_plan_mode shadow is relaxed (returns 1)" "$rc"
rc=0; codex_skill_forces_plan_mode pick || rc=$?
assert_exit_zero_rc "codex_skill_forces_plan_mode pick still forces plan mode" "$rc"

# ============================================================
# Tests: resolve_pane_id_by_pid (faked gateway)
# ============================================================
echo "--- resolve_pane_id_by_pid ---"

PYOUT=$(cd "$PROJECT_DIR" && python3 - <<'PY'
import sys
sys.path.insert(0, ".aitask-scripts/lib")
import agent_launch_utils as a

class FakeTmux:
    def __init__(self, out, rc=0):
        self._out = out
        self._rc = rc
    def run(self, argv, **kw):
        return self._rc, self._out

panes = "%10 1001\n%11 1002\n%12 1003\n"

a._TMUX = FakeTmux(panes)
assert a.resolve_pane_id_by_pid("sess", 1002) == "%11", "match middle pid"
assert a.resolve_pane_id_by_pid("sess", 1001) == "%10", "match first pid"
assert a.resolve_pane_id_by_pid("sess", 9999) is None, "no match -> None"
assert a.resolve_pane_id_by_pid("sess", 0) is None, "falsy pid -> None"

a._TMUX = FakeTmux("", rc=1)
assert a.resolve_pane_id_by_pid("sess", 1001) is None, "tmux failure -> None"

print("PYOK")
PY
)
assert_contains "resolve_pane_id_by_pid unit assertions pass" "PYOK" "$PYOUT"

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
