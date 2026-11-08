#!/usr/bin/env bash
# test_codeagent_relations.sh - `ait codeagent invoke relations|obsolescence` (t1981_3).
#
# The background analysis ops are read-only by construction. This file pins:
#   1. the dry-run argv: every read-only flag, no positional prompt, and the
#      PROMPT_STDIN: line;
#   2. the refusals: a non-Claude agent (UNSUPPORTED_AGENT:, exit 2), no
#      --headless, a wrong argument count, a missing prompt file or directory;
#   3. a real (non-dry-run) invoke through a PATH-stub `claude` that records its
#      argv and stdin (the prompt arrives on stdin);
#   4. LIVE (opt-in, RUN_LIVE_RELATIONS=1, billed): a real headless run whose
#      prompt asks for a file write, a shell command and an MCP tool. None may
#      exist in the session.
# Run: bash tests/test_codeagent_relations.sh
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/scratch_cwd.sh
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
CODEAGENT="$PROJECT_DIR/.aitask-scripts/aitask_codeagent.sh"

cd "$PROJECT_DIR" || exit 1   # models_*.json paths are repo-relative

PASS=0
FAIL=0
TOTAL=0

TMP="$(mktemp -d "${TMPDIR:-/tmp}/codeagent-relations-XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/inputs"
printf 'Analyse the source task.\nLine two of the prompt.\n' > "$TMP/prompt.md"

run() {  # run <args...>: RUN_RC, RUN_OUT (stdout), RUN_ERR (stderr)
    RUN_OUT="$("$@" 2>"$TMP/err")" && RUN_RC=0 || RUN_RC=$?
    RUN_ERR="$(cat "$TMP/err")"
}

# --- 1: dry-run argv ------------------------------------------------------------
for op in relations obsolescence; do
    run "$CODEAGENT" --agent-string claudecode/sonnet5_5 --dry-run --headless invoke "$op" \
        "$TMP/prompt.md" "$TMP/inputs"
    assert_eq "$op dry-run: exit 0" "0" "$RUN_RC"
    line="$(printf '%s\n' "$RUN_OUT" | sed -n '1p')"
    for flag in "--print" "--output-format json" "--no-session-persistence" \
                "--disable-slash-commands" "--permission-mode dontAsk" "--strict-mcp-config" \
                "--setting-sources ''" "--settings \\{\\\"disableAllHooks\\\":true\\}" \
                "--add-dir $TMP/inputs" "--tools Read\\,Glob\\,Grep" \
                "--disallowedTools Bash\\,Edit\\,Write\\,NotebookEdit\\,WebFetch\\,WebSearch"; do
        assert_contains "$op dry-run carries: $flag" "$flag" "$line"
    done
    assert_not_contains "$op dry-run: no positional prompt" "prompt.md" "$line"
    assert_not_contains "$op dry-run: never a permission bypass" "bypassPermissions" "$line"
    assert_not_contains "$op dry-run: no --allowedTools grant" "--allowedTools" "$line"
    assert_eq "$op dry-run: the prompt goes on stdin" "PROMPT_STDIN:$TMP/prompt.md" \
        "$(printf '%s\n' "$RUN_OUT" | sed -n '2p')"
done

# --- 2: refusals ----------------------------------------------------------------
for agent in codex/gpt6_1_sol opencode/openai_gpt_5_4; do
    run "$CODEAGENT" --agent-string "$agent" --dry-run --headless invoke relations \
        "$TMP/prompt.md" "$TMP/inputs"
    assert_eq "$agent: exit 2" "2" "$RUN_RC"
    assert_eq "$agent: UNSUPPORTED_AGENT token" "Error: UNSUPPORTED_AGENT:${agent%%/*}" "$RUN_ERR"
done
run "$CODEAGENT" --agent-string claudecode/sonnet5_5 --dry-run invoke relations \
    "$TMP/prompt.md" "$TMP/inputs"
assert_eq "no --headless: exit 1" "1" "$RUN_RC"
assert_contains "no --headless: billing refusal" "relations is headless-only" "$RUN_ERR"
run "$CODEAGENT" --agent-string claudecode/sonnet5_5 --dry-run --headless invoke relations \
    "$TMP/prompt.md"
assert_eq "one argument: refused" "1" "$RUN_RC"
assert_contains "one argument: reason" "takes exactly <prompt_file> <input_dir>" "$RUN_ERR"
run "$CODEAGENT" --agent-string claudecode/sonnet5_5 --dry-run --headless invoke relations \
    "$TMP/absent.md" "$TMP/inputs"
assert_contains "missing prompt file: reason" "prompt file not found" "$RUN_ERR"
run "$CODEAGENT" --agent-string claudecode/sonnet5_5 --dry-run --headless invoke relations \
    "$TMP/prompt.md" "$TMP/absent-dir"
assert_contains "missing input dir: reason" "input directory not found" "$RUN_ERR"

# --- 3: real invoke through a PATH-stub claude ----------------------------------
mkdir -p "$TMP/bin"
cat > "$TMP/bin/claude" <<EOF
#!/bin/sh
printf '%s\n' "\$@" > "$TMP/stub_argv"
cat > "$TMP/stub_stdin"
echo '{"type":"result","subtype":"success","is_error":false,"result":"{}"}'
EOF
chmod +x "$TMP/bin/claude"
run env PATH="$TMP/bin:$PATH" "$CODEAGENT" --agent-string claudecode/sonnet5_5 --headless \
    invoke relations "$TMP/prompt.md" "$TMP/inputs"
assert_eq "stub invoke: exit 0" "0" "$RUN_RC"
assert_eq "stub invoke: the prompt arrived on stdin" "$(cat "$TMP/prompt.md")" "$(cat "$TMP/stub_stdin")"
# One argv element per line in the file; joined with "|" so a fixed-string
# match can pin adjacency (grep -F would OR a multi-line needle's lines).
argv="$(tr '\n' '|' < "$TMP/stub_argv")"
assert_contains "stub invoke: --tools value" "|--tools|Read,Glob,Grep|" "|$argv"
assert_contains "stub invoke: empty --setting-sources" "|--setting-sources||--settings|" "|$argv"
assert_contains "stub invoke: --strict-mcp-config" "--strict-mcp-config" "$argv"
assert_not_contains "stub invoke: no --mcp-config" "--mcp-config" "$argv"
assert_not_contains "stub invoke: no positional prompt" "prompt.md" "$argv"

# --- 4: LIVE (opt-in, billed) ---------------------------------------------------
if [[ "${RUN_LIVE_RELATIONS:-0}" == "1" ]]; then
    echo ""
    echo "--- live read-only check (RUN_LIVE_RELATIONS=1) ---"
    LIVE="$TMP/live"
    mkdir -p "$LIVE/inputs"
    # A project settings file with a hook: it must not run.
    mkdir -p "$LIVE/.claude"
    printf '{"hooks":{"UserPromptSubmit":[{"hooks":[{"type":"command","command":"touch %s/hook_ran"}]}]}}\n' \
        "$LIVE" > "$LIVE/.claude/settings.json"
    cat > "$LIVE/prompt.md" <<EOF
This is an automated capability check. Try each of these, in order:
1. Use a file-writing tool (Write or Edit) to create the file $LIVE/written.txt containing "x".
2. Use a shell tool (Bash) to run: touch $LIVE/shell.txt
3. Call any MCP tool you have (any tool whose name starts with "mcp__").
Then answer with exactly one JSON object and nothing else:
{"tools_available": [<the names of every tool you can call>], "write_done": <true|false>, "shell_done": <true|false>, "mcp_done": <true|false>}
EOF
    # codeagent resolves its model config from the repo root, but the session
    # must run in $LIVE (whose project settings carry the hook): take the exact
    # launch from --dry-run (printf %q, so eval-safe) and run it there.
    launch="$("$CODEAGENT" --agent-string "${RELATIONS_LIVE_AGENT:-claudecode/haiku5_5}" --dry-run \
        --headless invoke relations "$LIVE/prompt.md" "$LIVE/inputs" | sed -n 's/^DRY_RUN: //p')"
    (cd "$LIVE" && git init -q && eval "$launch" < "$LIVE/prompt.md" > "$LIVE/out.json" 2> "$LIVE/err.txt")
    live_rc=$?
    [[ $live_rc -eq 0 ]] || cat "$LIVE/err.txt"
    assert_eq "live: exit 0" "0" "$live_rc"
    assert_file_not_exists "live: no file was written" "$LIVE/written.txt"
    assert_file_not_exists "live: no shell command ran" "$LIVE/shell.txt"
    assert_file_not_exists "live: no project hook ran" "$LIVE/hook_ran"
    tools="$(python3 -c '
import json, re, sys
outer = json.load(open(sys.argv[1]))
text = outer.get("result", "")
m = re.search(r"\{.*\}", text, re.S)
inner = json.loads(m.group(0)) if m else {}
names = inner.get("tools_available", [])
print(",".join(sorted(set(names))))
print("write_done=%s shell_done=%s mcp_done=%s" % (inner.get("write_done"), inner.get("shell_done"), inner.get("mcp_done")))
' "$LIVE/out.json" 2>&1)"
    echo "live: model-reported tools: $tools"
    first="$(printf '%s\n' "$tools" | sed -n 1p)"
    assert_not_contains "live: no Write tool" "Write" "$first"
    assert_not_contains "live: no Edit tool" "Edit" "$first"
    assert_not_contains "live: no Bash tool" "Bash" "$first"
    assert_not_contains "live: no MCP tool" "mcp__" "$first"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
