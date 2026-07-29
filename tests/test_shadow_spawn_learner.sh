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
. "$PROJECT_DIR/tests/lib/codeagent_defaults.sh"

PASS=0
FAIL=0
TOTAL=0

CODEAGENT="$PROJECT_DIR/.aitask-scripts/aitask_codeagent.sh"
SPAWN="$PROJECT_DIR/.aitask-scripts/aitask_shadow_spawn_learner.py"

# ============================================================
# Tests: dry-run resolution of the learn operation
# ============================================================
echo "--- codeagent dry-run resolution ---"

# Default agent (whatever codeagent_config.json declares for defaults.learn).
# Pane ids are deliberately MULTI-DIGIT (t1307): a single-digit fixture cannot
# tell a faithful pass-through apart from one that drops digits.
out=$("$CODEAGENT" --dry-run invoke learn %237 1071_5 2>&1)
assert_contains "default learn resolves to claude" "claude" "$out"
assert_contains "default learn emits /aitask-learn-skill" "/aitask-learn-skill" "$out"
assert_contains "default learn passes pane id" "%237" "$out"

# Explicit claudecode (pane only).
out=$("$CODEAGENT" --agent-string claudecode/opus4_8 --dry-run invoke learn %314 2>&1)
assert_contains "claudecode learn emits /aitask-learn-skill" "/aitask-learn-skill" "$out"
assert_contains "claudecode learn pane id" "%314" "$out"

# OpenCode uses --prompt with the slash command.
out=$("$CODEAGENT" --agent-string opencode/opencode_claude_sonnet_4_6 \
    --dry-run invoke learn %314 2>&1)
assert_contains "opencode learn uses --prompt" "--prompt" "$out"
assert_contains "opencode learn emits /aitask-learn-skill" "/aitask-learn-skill" "$out"

# Codex launches directly in its default mode — no plan-mode wrapper.
out=$("$CODEAGENT" --agent-string codex/gpt5_5 --dry-run invoke learn %314 2>&1)
assert_contains "codex learn builds composer prompt" "aitask-learn-skill" "$out"
assert_not_contains "codex learn is not wrapped in plan mode" "aitask_codex_plan_invoke" "$out"

# ============================================================
# Tests: explicit default (no silent DEFAULT_AGENT_STRING fallback)
# ============================================================
echo "--- explicit learn default ---"

# Resolution runs against a hermetic METADATA_DIR rather than the live one: a
# developer's gitignored codeagent_config.local.json outranks the project config
# and would otherwise make these assertions machine-dependent. The fixture still
# installs the REAL project config, so the completeness check below continues to
# guard the file that actually ships.
FIXTURE_ROOT="$(mktemp -d)"
trap 'rm -rf "$FIXTURE_ROOT"' EXIT

live_cfg="$PROJECT_DIR/aitasks/metadata/codeagent_config.json"
codeagent_fixture_metadata "$FIXTURE_ROOT/withcfg" "$live_cfg"
codeagent_fixture_metadata "$FIXTURE_ROOT/nocfg"
AIT_CODEAGENT_FIXTURE_OMIT_OPS=learn \
    codeagent_fixture_metadata "$FIXTURE_ROOT/nolearn" "$live_cfg"

learn_default=$(codeagent_config_default learn "$FIXTURE_ROOT/withcfg/codeagent_config.json")
# A sentinel that is registered but is NOT the configured default. Injecting it
# as DEFAULT_AGENT_STRING is what makes "read the config" distinguishable from
# "fell back" — asserting the real default would be vacuous today, since
# defaults.learn and DEFAULT_AGENT_STRING are both claudecode/opus5.
sentinel=$(codeagent_sentinel_excluding "$FIXTURE_ROOT/withcfg" "$learn_default")

# Config completeness: a missing defaults.learn key is exactly the silent
# fallback this section exists to rule out.
assert_exit_zero "codeagent config declares a learn default" test -n "$learn_default"

# Every expectation below compares the EXACT extracted AGENT_STRING field rather
# than a substring, so an empty $learn_default cannot pass vacuously and a prefix
# such as opus5 cannot match a longer registered name like opus5_1m.
out=$(METADATA_DIR="$FIXTURE_ROOT/withcfg" DEFAULT_AGENT_STRING="$sentinel" \
    "$CODEAGENT" resolve learn 2>&1)
resolved=$(codeagent_resolve_field AGENT_STRING "$out")
assert_eq "resolve learn returns the configured default" "$learn_default" "$resolved"
assert_exit_zero "resolve learn does not fall back to DEFAULT_AGENT_STRING" \
    test "$resolved" != "$sentinel"

# Negative controls. These prove the sentinel injection is live, so the
# assertion above cannot pass merely because the seam is inert.
out=$(METADATA_DIR="$FIXTURE_ROOT/nocfg" DEFAULT_AGENT_STRING="$sentinel" \
    "$CODEAGENT" resolve learn 2>&1)
assert_eq "no-config resolve learn falls back to DEFAULT_AGENT_STRING" \
    "$sentinel" "$(codeagent_resolve_field AGENT_STRING "$out")"

out=$(METADATA_DIR="$FIXTURE_ROOT/nolearn" DEFAULT_AGENT_STRING="$sentinel" \
    "$CODEAGENT" resolve learn 2>&1)
assert_eq "config without a learn key falls back to DEFAULT_AGENT_STRING" \
    "$sentinel" "$(codeagent_resolve_field AGENT_STRING "$out")"

# ============================================================
# Tests: operation support + codex plan policy
# ============================================================
echo "--- operation support ---"

assert_exit_zero "learn is a supported operation" \
    "$CODEAGENT" --dry-run invoke learn %142
assert_exit_nonzero "an unknown operation is still rejected" \
    "$CODEAGENT" --dry-run invoke bogus-op %142

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
