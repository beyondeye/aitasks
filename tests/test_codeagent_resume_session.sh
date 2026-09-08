#!/usr/bin/env bash
# test_codeagent_resume_session.sh — `aitask_codeagent.sh --resume-session <sid>`
# (t1705_5): the argv seam the frozen-agent restore coordinator uses to relaunch
# a captured session in place of its stand-in.
#
# Everything here is `--dry-run`: no agent is launched and no binary needs to be
# installed. `--agent-string` is passed explicitly on every call so the shape
# under test never depends on this checkout's configured default.
#
# What is pinned, and why each one matters:
#
#   * ORDERING per agent. claude wants `--model <id> --resume <sid>` — the flag
#     AFTER the model flag and BEFORE any positional (the same ordering hazard
#     `explore-relay` documents). codex wants `resume <sid>` as the LEADING
#     positional, so its argv has to be REBUILT rather than appended to, because
#     build_invoke_command pre-seeds (binary, model_flag, cli_id). A silent
#     regression either way produces an argv the agent rejects at respawn time —
#     inside a pane the user is watching, after their agent has already been
#     killed.
#   * `raw`-ONLY. Every other operation appends a slash command or composer
#     prompt; resuming into one would hand the restored agent fresh instructions
#     instead of returning it to where it was.
#   * opencode REFUSES with exit 2, distinct from `die`'s 1: the coordinator
#     branches on it to fail the restore before writing anything to the store.
#   * Session-id validation, because the value reaches an argv that tmux
#     respawns.
#
# Codex note (t1705_1 PINNED): codex's SessionStart hook never fires in the
# interactive TUI, which is the framework's launch path, so a codex record's
# session id is empty in practice and `codex = re-pick only` stands. The codex
# branch is an argv-completeness surface pinned by dry-run only — there is
# deliberately no live codex resume case here or in the live suite.
#
# Run: bash tests/test_codeagent_resume_session.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

CODEAGENT="$PROJECT_DIR/.aitask-scripts/aitask_codeagent.sh"

# Run the wrapper, capturing stdout+stderr and the exit status without tripping
# `set -e`. Sets RC and OUT.
run_ca() {
    RC=0
    OUT="$("$CODEAGENT" "$@" 2>&1)" || RC=$?
}

echo "=== --resume-session: claudecode argv ordering ==="

run_ca --agent-string claudecode/opus5 --resume-session abc-123 --dry-run invoke raw
assert_eq "claudecode resume: exits 0" "0" "$RC"
assert_contains "claudecode resume: --resume carries the session id" \
    "--resume abc-123" "$OUT"
# The ordering assertion, stated as one exact string rather than two
# 'contains' checks: `--resume` BEFORE the model flag would satisfy both of
# those and still be wrong.
assert_contains "claudecode resume: --resume comes AFTER the model flag" \
    "claude --model claude-opus-5 --resume abc-123" "$OUT"

run_ca --agent-string claudecode/opus5 --dry-run invoke raw
assert_eq "claudecode raw without --resume-session: exits 0" "0" "$RC"
assert_not_contains "claudecode raw without --resume-session: no --resume leaks in" \
    "--resume" "$OUT"

echo ""
echo "=== --resume-session: codex argv ordering ==="

run_ca --agent-string codex/gpt5_4 --resume-session sess_9 --dry-run invoke raw
assert_eq "codex resume: exits 0" "0" "$RC"
# `resume` must be the LEADING positional, immediately after the binary — this
# is the assertion that fails if the codex branch ever appends instead of
# rebuilding.
assert_contains "codex resume: 'resume <sid>' leads, before the model flag" \
    "codex resume sess_9" "$OUT"

run_ca --agent-string codex/gpt5_4 --dry-run invoke raw
assert_eq "codex raw without --resume-session: exits 0" "0" "$RC"
assert_not_contains "codex raw without --resume-session: no bare 'resume' leaks in" \
    "codex resume" "$OUT"

echo ""
echo "=== --resume-session: opencode is refused with exit 2 ==="

run_ca --agent-string opencode/openai_gpt_5_2 --resume-session x1 --dry-run invoke raw
assert_eq "opencode resume: exit 2 (usage), NOT die's 1" "2" "$RC"
assert_contains "opencode resume: machine-readable refusal token" \
    "RESUME_UNSUPPORTED:opencode" "$OUT"

run_ca --agent-string opencode/openai_gpt_5_2 --dry-run invoke raw
assert_eq "opencode raw without --resume-session: still works" "0" "$RC"

echo ""
echo "=== --resume-session is legal ONLY with 'invoke raw' ==="

for op in pick explain qa; do
    run_ca --agent-string claudecode/opus5 --resume-session abc --dry-run invoke "$op" 1705_5
    assert_eq "--resume-session refused for 'invoke $op'" "1" "$RC"
    assert_contains "--resume-session refusal for '$op' names the requirement" \
        "requires 'invoke raw'" "$OUT"
done

echo ""
echo "=== session-id validation (the value reaches a respawned argv) ==="

# Shell metacharacters, whitespace and an empty value must all be refused.
for bad in 'bad id' 'a;rm -rf /' 'x$(id)' '`id`' 'a|b' 'a&b' "a'b" 'a"b'; do
    run_ca --agent-string claudecode/opus5 --resume-session "$bad" --dry-run invoke raw
    assert_eq "invalid session id refused: '$bad'" "1" "$RC"
done

run_ca --agent-string claudecode/opus5 --resume-session "" --dry-run invoke raw
assert_eq "empty session id refused" "1" "$RC"

# The accepted shape: the characters real agent session ids actually use.
for good in 'abc-123' 'a_b.c-9' '01234567-89ab-cdef-0123-456789abcdef'; do
    run_ca --agent-string claudecode/opus5 --resume-session "$good" --dry-run invoke raw
    assert_eq "valid session id accepted: '$good'" "0" "$RC"
    assert_contains "valid session id reaches the argv: '$good'" \
        "--resume $good" "$OUT"
done

run_ca --agent-string claudecode/opus5 --resume-session
assert_eq "--resume-session with no value is a usage error" "1" "$RC"
assert_contains "--resume-session with no value says so" \
    "requires a value" "$OUT"

echo ""
echo "=== --resume-session is documented in --help ==="

run_ca --help
assert_contains "help documents --resume-session" "--resume-session" "$OUT"
assert_contains "help states the raw-only restriction" "invoke raw" "$OUT"

# --- Summary ---

echo ""
echo "=== Results ==="
echo "PASS: $PASS / $TOTAL"
if [[ $FAIL -gt 0 ]]; then
    echo "FAIL: $FAIL"
    exit 1
else
    echo "All tests passed."
    exit 0
fi
