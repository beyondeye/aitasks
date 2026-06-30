#!/usr/bin/env bash
# test_shadow_spawn_learner.sh - Tests for the t1071_5 shadow learner-spawn glue.
# Run: bash tests/test_shadow_spawn_learner.sh
#
# Covers:
#   1. The `learn` codeagent operation resolves through the agent-string chain
#      and emits `/aitask-learn-skill <pane>` per agent (claudecode / opencode /
#      codex). No live tmux — pure --dry-run.
#   2. `resolve learn` returns the explicit configured default, not a silent
#      DEFAULT_AGENT_STRING fallback.
#   3. `learn` is a supported operation (and an unknown op still errors); the
#      codex plan policy treats `learn` as a relaxed (default-mode) skill.
#   4. aitask_shadow_spawn_learner.py --dry-run resolves the learn command WITHOUT
#      live tmux (works even when the followed pane does not exist), separating
#      command resolution from live session targeting.
#   5. unique_window_name() gives distinct, monitor-legible names (pure, no tmux).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

CODEAGENT="$PROJECT_DIR/.aitask-scripts/aitask_codeagent.sh"
SPAWN="$PROJECT_DIR/.aitask-scripts/aitask_shadow_spawn_learner.py"

# ============================================================
# Tests: dry-run resolution of the learn operation
# ============================================================
echo "--- codeagent dry-run resolution ---"

# Default agent (codeagent_config.json defaults.learn → claudecode/opus4_8).
out=$("$CODEAGENT" --dry-run invoke learn %5 1071_5 2>&1)
assert_contains "default learn resolves to claude" "claude" "$out"
assert_contains "default learn emits /aitask-learn-skill" "/aitask-learn-skill" "$out"
assert_contains "default learn passes pane id" "%5" "$out"

# Explicit claudecode (pane only).
out=$("$CODEAGENT" --agent-string claudecode/opus4_8 --dry-run invoke learn %7 2>&1)
assert_contains "claudecode learn emits /aitask-learn-skill" "/aitask-learn-skill" "$out"
assert_contains "claudecode learn pane id" "%7" "$out"

# OpenCode uses --prompt with the slash command.
out=$("$CODEAGENT" --agent-string opencode/opencode_claude_sonnet_4_6 \
    --dry-run invoke learn %7 2>&1)
assert_contains "opencode learn uses --prompt" "--prompt" "$out"
assert_contains "opencode learn emits /aitask-learn-skill" "/aitask-learn-skill" "$out"

# Codex is interactive-but-not-planning (default mode), NOT routed through the
# /plan PTY helper.
out=$("$CODEAGENT" --agent-string codex/gpt5_5 --dry-run invoke learn %7 2>&1)
assert_contains "codex learn builds composer prompt" "aitask-learn-skill" "$out"
assert_not_contains "codex learn does NOT force plan mode" "aitask_codex_plan_invoke" "$out"

# ============================================================
# Tests: explicit default (no silent DEFAULT_AGENT_STRING fallback)
# ============================================================
echo "--- explicit learn default ---"

out=$("$CODEAGENT" resolve learn 2>&1)
assert_contains "resolve learn returns the configured default" \
    "AGENT_STRING:claudecode/opus4_8" "$out"

# ============================================================
# Tests: operation support + codex plan policy
# ============================================================
echo "--- operation support ---"

assert_exit_zero "learn is a supported operation" \
    "$CODEAGENT" --dry-run invoke learn %1
assert_exit_nonzero "an unknown operation is still rejected" \
    "$CODEAGENT" --dry-run invoke bogus-op %1

# shellcheck source=/dev/null
. "$PROJECT_DIR/.aitask-scripts/lib/codex_plan_policy.sh"
rc=0; codex_skill_forces_plan_mode learn || rc=$?
assert_exit_nonzero_rc "codex_skill_forces_plan_mode learn is relaxed (returns 1)" "$rc"
rc=0; codex_skill_forces_plan_mode pick || rc=$?
assert_exit_zero_rc "codex_skill_forces_plan_mode pick still forces plan mode" "$rc"

# ============================================================
# Tests: launcher --dry-run (no live tmux required)
# ============================================================
echo "--- aitask_shadow_spawn_learner.py --dry-run ---"

# %999999 almost certainly does not exist; --dry-run must still succeed because
# it resolves the command only and never touches tmux.
out=$(python3 "$SPAWN" --dry-run %999999 1071_5 2>&1)
assert_contains "dry-run emits DRY_RUN_SPAWN" "DRY_RUN_SPAWN:" "$out"
assert_contains "dry-run resolves the learn command" "/aitask-learn-skill" "$out"
assert_contains "dry-run passes the followed pane id" "%999999" "$out"
assert_contains "dry-run labels window with task id" "window=agent-learn-1071_5" "$out"

# No task id → base window name (distinct from the task-labelled base).
out=$(python3 "$SPAWN" --dry-run %999999 2>&1)
assert_contains "dry-run no-task window base" "window=agent-learn cmd" "$out"

# ============================================================
# Tests: unique_window_name (pure helper)
# ============================================================
echo "--- unique_window_name ---"

PYOUT=$(cd "$PROJECT_DIR" && python3 - <<'PY'
import sys
sys.path.insert(0, ".aitask-scripts/lib")
import agent_launch_utils as a

assert a.unique_window_name(set(), "agent-learn") == "agent-learn", "free base"
seen = {"agent-learn"}
assert a.unique_window_name(seen, "agent-learn") == "agent-learn-2", "first dup -> -2"
seen.add("agent-learn-2")
assert a.unique_window_name(seen, "agent-learn") == "agent-learn-3", "second dup -> -3"
# A task-labelled base is independent of the no-task base.
assert a.unique_window_name(seen, "agent-learn-1071_5") == "agent-learn-1071_5", \
    "task-labelled base unaffected by agent-learn duplicates"
print("PYOK")
PY
)
assert_contains "unique_window_name unit assertions pass" "PYOK" "$PYOUT"

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
