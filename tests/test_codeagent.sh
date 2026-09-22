#!/usr/bin/env bash
# test_codeagent.sh - Tests for aitask_codeagent.sh
#
# Default-resolution expectations are DERIVED from seed/codeagent_config.json —
# the file the fixture installs as the project config — and checked against an
# injected sentinel DEFAULT_AGENT_STRING (the t1318 idiom, adopted here by
# t1865). They are never pinned to a literal model name, which is what would
# leave this file red after every promotion of the shipped defaults.
#
# Negative control — prove the derived assertions are not vacuous:
#     AIT_CODEAGENT_FIXTURE_OMIT_OPS=pick bash tests/test_codeagent.sh   # MUST fail
#
# Run: bash tests/test_codeagent.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

# Shared assertion helpers (see tests/lib/asserts.sh)
. "$PROJECT_DIR/tests/lib/asserts.sh"
# Derived-default helpers (see tests/lib/codeagent_defaults.sh) — MUST be
# sourced after asserts.sh.
. "$PROJECT_DIR/tests/lib/codeagent_defaults.sh"





# --- Test environment setup ---

setup_test_env() {
    local tmpdir
    tmpdir="$(mktemp -d)"

    # Create minimal project structure
    mkdir -p "$tmpdir/aitasks/metadata"
    setup_fake_aitask_repo "$tmpdir"

    # Copy required scripts
    cp "$PROJECT_DIR/.aitask-scripts/aitask_codeagent.sh" "$tmpdir/.aitask-scripts/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" "$tmpdir/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" "$tmpdir/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/agent_string.sh" "$tmpdir/.aitask-scripts/lib/"
    chmod +x "$tmpdir/.aitask-scripts/aitask_codeagent.sh"

    # Metadata fixture via the shared helper. It copies every models_*.json plus
    # project_config.yaml from the live metadata dir and installs the SEED
    # config as codeagent_config.json — the identical file set this used to copy
    # by hand. Going through the helper additionally brings the
    # AIT_CODEAGENT_FIXTURE_OMIT_OPS seam, which is the negative control for the
    # derived default assertions (see the header).
    codeagent_fixture_metadata "$tmpdir/aitasks/metadata" \
        "$PROJECT_DIR/seed/codeagent_config.json"

    # Initialize git repo (task_utils.sh needs it)
    (cd "$tmpdir" && git init --quiet && git config user.email "test@test.com" && git config user.name "Test")

    echo "$tmpdir"
}

cleanup_test_env() {
    [[ -n "${1:-}" && -d "$1" ]] && rm -rf "$1"
}

# --- Check prerequisites ---

if ! command -v jq &>/dev/null; then
    echo "SKIP: jq is required for these tests"
    exit 0
fi

# --- Tests ---

echo "=== test_codeagent.sh ==="
echo ""

# Test 1: Syntax check
echo "--- Test 1: Syntax check ---"
assert_exit_zero "bash -n syntax check" bash -n "$PROJECT_DIR/.aitask-scripts/aitask_codeagent.sh"

# Setup test environment
TMPDIR_TEST="$(setup_test_env)"
CODEAGENT="$TMPDIR_TEST/.aitask-scripts/aitask_codeagent.sh"

# Test 2: list-agents outputs all 3 agents
echo "--- Test 2: list-agents ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" list-agents 2>&1)
assert_contains_ci "list-agents shows claudecode" "AGENT:claudecode" "$output"
assert_contains_ci "list-agents shows codex" "AGENT:codex" "$output"
assert_contains_ci "list-agents shows opencode" "AGENT:opencode" "$output"

# Test 3: list-models claudecode shows expected models
echo "--- Test 3: list-models claudecode ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" list-models claudecode 2>&1)
assert_contains_ci "list-models shows opus4_6" "MODEL:opus4_6" "$output"
assert_contains_ci "list-models shows sonnet4_6" "MODEL:sonnet4_6" "$output"
assert_contains_ci "list-models shows haiku4_5" "MODEL:haiku4_5" "$output"
assert_contains_ci "list-models shows opus4_7" "MODEL:opus4_7" "$output"
assert_contains_ci "list-models shows opus4_7_1m" "MODEL:opus4_7_1m" "$output"
assert_contains_ci "list-models shows cli_id" "CLI_ID:claude-opus-4-6" "$output"
assert_contains_ci "list-models shows notes" "NOTES:" "$output"
assert_contains_ci "list-models shows verified" "VERIFIED:" "$output"

# Test 3b: list-models codex shows GPT-5.6 models
echo "--- Test 3b: list-models codex GPT-5.6 ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" list-models codex 2>&1)
assert_contains_ci "list-models codex shows gpt5_6_sol" "MODEL:gpt5_6_sol" "$output"
assert_contains_ci "list-models codex shows gpt-5.6-sol cli_id" "CLI_ID:gpt-5.6-sol" "$output"

# Test 4: list-models with invalid agent
echo "--- Test 4: list-models invalid agent ---"
assert_exit_nonzero "list-models with invalid agent" bash -c "cd '$TMPDIR_TEST' && bash '$CODEAGENT' list-models notanagent"

# Test 5: resolve pick returns the SEEDED default — derived, never pinned.
# The fixture installs seed/codeagent_config.json as the project config, so that
# file is what these resolutions read.
echo "--- Test 5: resolve pick ---"
seed_cfg="$PROJECT_DIR/seed/codeagent_config.json"
seeded_pick=$(codeagent_config_default pick "$seed_cfg")
assert_exit_zero "seed config declares a pick default" test -n "$seeded_pick"
# Registered but not the seeded value: injecting it as DEFAULT_AGENT_STRING is
# what distinguishes "read the config" from "fell through to the hardcoded
# default", which are otherwise indistinguishable whenever the two agree.
sentinel=$(codeagent_sentinel_excluding "$TMPDIR_TEST/aitasks/metadata" "$seeded_pick")
assert_exit_zero "a sentinel agent string is available" test -n "$sentinel"

output=$(cd "$TMPDIR_TEST" && DEFAULT_AGENT_STRING="$sentinel" bash "$CODEAGENT" resolve pick 2>&1)
# assert_eq on an exactly-extracted field, never assert_contains_ci: substring
# matching lets a prefix (opus5) match a longer registered name (opus5_1m,
# opus5_5), which is precisely the confusion this suite must not have.
assert_eq "resolve pick matches the seeded default" \
    "$seeded_pick" "$(codeagent_resolve_field AGENT_STRING "$output")"
assert_eq "resolve pick reports the agent" \
    "${seeded_pick%%/*}" "$(codeagent_resolve_field AGENT "$output")"
assert_eq "resolve pick reports the model" \
    "${seeded_pick#*/}" "$(codeagent_resolve_field MODEL "$output")"
# Reused by Tests 11 / 11a below, so the composed command line is cross-checked
# against the resolver rather than against a literal cli_id.
seeded_cli_id=$(codeagent_resolve_field CLI_ID "$output")
assert_exit_zero "resolve pick reports a cli_id" test -n "$seeded_cli_id"

# Test 6: resolve with --agent-string override
echo "--- Test 6: resolve with --agent-string override ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --agent-string codex/gpt5_4 resolve pick 2>&1)
assert_contains_ci "override agent string" "AGENT_STRING:codex/gpt5_4" "$output"
assert_contains_ci "override resolves codex" "AGENT:codex" "$output"

# Test 7: resolve with local config overrides project config
echo "--- Test 7: resolve with local config ---"
cat > "$TMPDIR_TEST/aitasks/metadata/codeagent_config.local.json" << 'LOCALEOF'
{
  "defaults": {
    "pick": "codex/gpt5_4"
  }
}
LOCALEOF
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" resolve pick 2>&1)
assert_contains_ci "local config overrides project config" "AGENT_STRING:codex/gpt5_4" "$output"
# Clean up local config
rm "$TMPDIR_TEST/aitasks/metadata/codeagent_config.local.json"

# Test 8: check valid agent string (claude should be in PATH on dev machines)
echo "--- Test 8: check valid agent string ---"
if command -v claude &>/dev/null; then
    output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" check "claudecode/sonnet4_6" 2>&1)
    assert_contains_ci "check shows OK" "OK" "$output"
else
    # claude not in PATH - check should fail with binary-not-found, not format error
    output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" check "claudecode/sonnet4_6" 2>&1) || true
    assert_contains_ci "check reports binary not found" "not found" "$output"
    TOTAL=$((TOTAL + 1))
    PASS=$((PASS + 1))  # This is expected behavior
fi

# Test 9: check with invalid format
echo "--- Test 9: check invalid format ---"
assert_exit_nonzero "check rejects invalid format" bash -c "cd '$TMPDIR_TEST' && bash '$CODEAGENT' check 'not-valid-format'"
assert_exit_nonzero "check rejects dots in model" bash -c "cd '$TMPDIR_TEST' && bash '$CODEAGENT' check 'claudecode/sonnet4.6'"

# Test 10: check with unknown model
echo "--- Test 10: check unknown model ---"
assert_exit_nonzero "check rejects unknown model" bash -c "cd '$TMPDIR_TEST' && bash '$CODEAGENT' check 'claudecode/nonexistent_model'"

# Test 11: --dry-run invoke
echo "--- Test 11: --dry-run invoke ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --dry-run invoke pick 42 2>&1)
assert_contains_ci "dry-run starts with DRY_RUN:" "DRY_RUN:" "$output"
assert_contains_ci "dry-run contains claude" "claude" "$output"
assert_contains "dry-run uses the resolved default model" "$seeded_cli_id" "$output"
assert_contains_ci "dry-run contains aitask-pick" "aitask-pick" "$output"
assert_contains_ci "dry-run contains task number" "42" "$output"
assert_not_contains_ci "plain dry-run carries no agent env" "AITASK_AGENT_STRING" "$output"

# Test 11a: --with-agent-env prefixes the export a real invoke performs (t1850)
echo "--- Test 11a: --with-agent-env dry-run ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --with-agent-env --dry-run invoke pick 42 2>&1)
assert_contains "agent-env dry-run prefixes env export" \
    "DRY_RUN: env AITASK_AGENT_STRING=$seeded_pick claude --model $seeded_cli_id" "$output"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --with-agent-env --agent-string codex/gpt5_4 --dry-run invoke pick 42 2>&1)
assert_contains "agent-env dry-run honors --agent-string" "DRY_RUN: env AITASK_AGENT_STRING=codex/gpt5_4 codex" "$output"

# Test 11a-2: the exported agent string is the one the command was BUILT from.
# A jq shim makes the per-user config answer opus5 on the first read and
# sonnet5 on every later one, i.e. the config "changes" mid-invocation. A second
# resolution for the env prefix would then pair `AITASK_AGENT_STRING=…sonnet5`
# with `claude --model claude-opus-5`, and the hook would record the wrong model.
echo "--- Test 11a-2: agent-env value cannot drift from the built command ---"
shim_dir="$TMPDIR_TEST/.jq_shim"
mkdir -p "$shim_dir"
real_jq="$(command -v jq)"
cat > "$shim_dir/jq" <<EOF
#!/usr/bin/env bash
for a in "\$@"; do
    if [[ "\$a" == *codeagent_config.local.json ]]; then
        n=\$(cat "$shim_dir/count" 2>/dev/null || echo 0)
        echo \$((n + 1)) > "$shim_dir/count"
        if [[ "\$n" -eq 0 ]]; then echo claudecode/opus5; else echo claudecode/sonnet5; fi
        exit 0
    fi
done
exec "$real_jq" "\$@"
EOF
chmod +x "$shim_dir/jq"
echo '{"defaults":{"pick":"claudecode/opus5"}}' > "$TMPDIR_TEST/aitasks/metadata/codeagent_config.local.json"
output=$(cd "$TMPDIR_TEST" && PATH="$shim_dir:$PATH" bash "$CODEAGENT" --with-agent-env --dry-run invoke pick 42 2>&1)
# Control: the shim really does answer differently on a later read, so the
# assertions below would catch a second resolution.
control=$(cd "$TMPDIR_TEST" && PATH="$shim_dir:$PATH" bash "$CODEAGENT" resolve pick 2>&1)
rm -f "$TMPDIR_TEST/aitasks/metadata/codeagent_config.local.json"
assert_contains "shim switches its answer on a later read (control)" "AGENT_STRING:claudecode/sonnet5" "$control"
assert_contains "env value matches the launched model" "DRY_RUN: env AITASK_AGENT_STRING=claudecode/opus5 claude --model claude-opus-5" "$output"
assert_not_contains "no second resolution leaks into the env" "sonnet5" "$output"

# Test 11b: Codex pick launches directly in Codex default mode
echo "--- Test 11b: Codex pick dry-run stays direct ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --agent-string codex/gpt5_4 --dry-run invoke pick 42 2>&1)
assert_not_contains_ci "codex pick bypasses plan helper" "aitask_codex_plan_invoke" "$output"
assert_contains_ci "codex pick dry-run contains aitask-pick" "aitask-pick" "$output"
assert_contains_ci "codex pick dry-run contains task number" "42" "$output"
assert_contains_ci "codex pick dry-run contains codex binary" "codex" "$output"
assert_contains_ci "codex pick dry-run contains codex model" "gpt-5.4" "$output"

# Test 11c: Codex explore also launches directly in Codex default mode
echo "--- Test 11c: Codex explore dry-run stays direct ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --agent-string codex/gpt5_4 --dry-run invoke explore 2>&1)
assert_not_contains_ci "codex explore bypasses plan helper" "aitask_codex_plan_invoke" "$output"
assert_contains_ci "codex explore dry-run contains aitask-explore" "aitask-explore" "$output"

# Test 11c2: Codex analysis skills (qa, explain) launch directly in default mode
echo "--- Test 11c2: Codex qa/explain dry-runs stay direct ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --agent-string codex/gpt5_4 --dry-run invoke explain src/main.py 2>&1)
assert_not_contains_ci "codex explain bypasses plan helper" "aitask_codex_plan_invoke" "$output"
assert_contains_ci "codex explain dry-run contains aitask-explain" "aitask-explain" "$output"
assert_contains_ci "codex explain dry-run contains path" "src/main.py" "$output"
assert_contains_ci "codex explain dry-run contains codex binary" "codex" "$output"

output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --agent-string codex/gpt5_4 --dry-run invoke qa 42 2>&1)
assert_not_contains_ci "codex qa bypasses plan helper" "aitask_codex_plan_invoke" "$output"
assert_contains_ci "codex qa dry-run contains aitask-qa" "aitask-qa" "$output"
assert_contains_ci "codex qa dry-run contains task number" "42" "$output"
assert_contains_ci "codex qa dry-run contains codex binary" "codex" "$output"

# Test 11d: Codex passthrough operations stay direct
echo "--- Test 11d: Codex passthrough dry-runs stay direct ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --agent-string codex/gpt5_4 --dry-run invoke raw hello 2>&1)
assert_not_contains_ci "codex raw bypasses plan helper" "aitask_codex_plan_invoke" "$output"
assert_contains_ci "codex raw stays direct" "codex" "$output"
assert_contains_ci "codex raw keeps raw argument" "hello" "$output"

output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --agent-string codex/gpt5_4 --dry-run invoke batch-review review-me 2>&1)
assert_not_contains_ci "codex batch-review bypasses plan helper" "aitask_codex_plan_invoke" "$output"
assert_contains_ci "codex batch-review stays direct" "codex" "$output"
assert_contains_ci "codex batch-review keeps argument" "review-me" "$output"

# Test 11d2: text-composed skill launches reject argv elements that cannot be
# represented after flattening. Passthrough operations continue to preserve
# whitespace-bearing and empty argv elements.
echo "--- Test 11d2: skill composer argument validation ---"
skill_operations=(pick explain qa shadow learn work-report trail discuss)
for operation in "${skill_operations[@]}"; do
    assert_exit_nonzero "$operation rejects whitespace-bearing argv" \
        bash -c "cd '$TMPDIR_TEST' && bash '$CODEAGENT' --dry-run invoke '$operation' 'two words'"
    output=$(cd "$TMPDIR_TEST" || exit 1 && bash "$CODEAGENT" --dry-run invoke "$operation" "two words" 2>&1 || true)
    assert_contains_ci "$operation whitespace refusal names cause" "argument contains whitespace" "$output"
    assert_not_contains_ci "$operation whitespace refusal emits no dry-run" "DRY_RUN:" "$output"

    assert_exit_nonzero "$operation rejects empty argv" \
        bash -c "cd '$TMPDIR_TEST' && bash '$CODEAGENT' --dry-run invoke '$operation' ''"
    output=$(cd "$TMPDIR_TEST" || exit 1 && bash "$CODEAGENT" --dry-run invoke "$operation" "" 2>&1 || true)
    assert_contains_ci "$operation empty refusal names cause" "argument is empty" "$output"
    assert_not_contains_ci "$operation empty refusal emits no dry-run" "DRY_RUN:" "$output"
done

assert_exit_zero "whitespace-free skill argv still composes" \
    bash -c "cd '$TMPDIR_TEST' && bash '$CODEAGENT' --dry-run invoke pick 42"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --agent-string codex/gpt5_4 --dry-run invoke raw "two words" "" 2>&1)
assert_contains_ci "raw preserves whitespace-bearing argv" 'two\ words' "$output"
assert_contains_ci "raw preserves empty argv" "''" "$output"

# Test 11d3: every existing Codex skill-composer arm emits its expected prompt.
echo "--- Test 11d3: Codex skill composer matrix ---"
codex_operations=(pick explain qa shadow learn work-report trail discuss)
codex_skills=(aitask-pick aitask-explain aitask-qa aitask-shadow aitask-learn-skill aitask-work-report aitask-trail aitask-brainstorm-discuss)
for index in "${!codex_operations[@]}"; do
    operation="${codex_operations[$index]}"
    expected_skill="${codex_skills[$index]}"
    output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --agent-string codex/gpt5_4 --dry-run invoke "$operation" probe 2>&1)
    assert_contains_ci "codex $operation emits expected skill prompt" "\$$expected_skill" "$output"
    assert_contains_ci "codex $operation keeps representative argv" "probe" "$output"
done

# Test 11e: every Codex launch carries the TUI animation override (t1797) —
# skill composers, explore, and the batch-review/raw passthroughs — placed
# right after the binary, with the composer prompt still the LAST argv element.
# Negative control: the other agents never receive it.
echo "--- Test 11e: Codex launches carry -c tui.animations=false ---"
dry_run_last_arg() {
    printf '%s\n' "$1" | python3 -c "
import shlex, sys
for line in sys.stdin:
    if line.startswith('DRY_RUN:'):
        print(shlex.split(line[len('DRY_RUN:'):])[-1])"
}
for operation in pick explain qa shadow learn work-report trail discuss explore batch-review raw; do
    if [[ "$operation" == "explore" ]]; then
        output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --agent-string codex/gpt5_4 --dry-run invoke "$operation" 2>&1)
    else
        output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --agent-string codex/gpt5_4 --dry-run invoke "$operation" probe 2>&1)
    fi
    assert_contains "codex $operation carries the override before the model flag" \
        "codex -c tui.animations=false -m gpt-5.4" "$output"
    last_arg="$(dry_run_last_arg "$output")"
    case "$operation" in
        batch-review|raw)
            assert_eq "codex $operation keeps its passthrough argv last" "probe" "$last_arg" ;;
        *)
            assert_contains "codex $operation keeps the composer prompt last" "\$aitask-" "$last_arg" ;;
    esac
done
for agent_string in claudecode/opus5 opencode/openai_gpt_5_2; do
    output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --agent-string "$agent_string" --dry-run invoke pick 42 2>&1)
    assert_contains "$agent_string pick still dry-runs" "DRY_RUN:" "$output"
    assert_not_contains "$agent_string pick carries no Codex TUI override" "tui.animations" "$output"
done

# Test 11d4: a supported operation missing from the nested Codex composer case
# fails closed. Mutate only a separately copied fixture, validate that the
# symbol-anchored transform matched exactly once, then remove the probe copy.
echo "--- Test 11d4: Codex unwired operation fails closed ---"
CODEAGENT_UNWIRED="$TMPDIR_TEST/.aitask-scripts/aitask_codeagent_unwired.sh"
awk '
    /^SUPPORTED_OPERATIONS=\(/ {
        sub(/\(/, "(codex-unwired-probe ")
        matches++
    }
    { print }
    END { if (matches != 1) exit 1 }
' "$CODEAGENT" > "$CODEAGENT_UNWIRED"
chmod +x "$CODEAGENT_UNWIRED"
assert_exit_nonzero "codex refuses supported but unwired operation" \
    bash -c "cd '$TMPDIR_TEST' && bash '$CODEAGENT_UNWIRED' --agent-string codex/gpt5_4 --dry-run invoke codex-unwired-probe"
output=$(cd "$TMPDIR_TEST" || exit 1 && bash "$CODEAGENT_UNWIRED" --agent-string codex/gpt5_4 --dry-run invoke codex-unwired-probe 2>&1 || true)
assert_contains_ci "codex unwired refusal names operation" \
    "operation not wired into the codex composer: codex-unwired-probe" "$output"
assert_not_contains_ci "codex unwired refusal emits no dry-run" "DRY_RUN:" "$output"
rm -f "$CODEAGENT_UNWIRED"

# Test 11e: claudecode batch-review is interactive by default; --headless opts
# into headless --print (Claude Code bills print mode at a higher rate).
echo "--- Test 11e: claudecode batch-review --headless gating ---"
# Needles use the literal "--print" flag; the assert helpers guard grep with
# `--`, so a dash-prefixed needle is matched correctly (regression test for t920).
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --agent-string claudecode/opus4_8 --dry-run invoke batch-review review-me 2>&1)
assert_not_contains_ci "claudecode batch-review interactive by default (no --print)" "--print" "$output"
assert_contains_ci "claudecode batch-review keeps argument" "review-me" "$output"

output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --agent-string claudecode/opus4_8 --headless --dry-run invoke batch-review review-me 2>&1)
assert_contains_ci "claudecode --headless batch-review adds --print" "--print review-me" "$output"

# Test 12: coauthor-domain reads configured domain
echo "--- Test 12: coauthor-domain configured ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor-domain 2>&1)
assert_contains_ci "coauthor-domain returns configured domain" "COAUTHOR_DOMAIN:aitasks.io" "$output"

# Test 13: coauthor-domain falls back when field is missing
echo "--- Test 13: coauthor-domain fallback on missing field ---"
cat > "$TMPDIR_TEST/aitasks/metadata/project_config.yaml" << 'YAMLEOF'
verify_build:
YAMLEOF
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor-domain 2>&1)
assert_contains_ci "coauthor-domain falls back to default" "COAUTHOR_DOMAIN:aitasks.io" "$output"

# Test 14: coauthor-domain falls back on empty field
echo "--- Test 14: coauthor-domain fallback on empty field ---"
cat > "$TMPDIR_TEST/aitasks/metadata/project_config.yaml" << 'YAMLEOF'
codeagent_coauthor_domain:
verify_build:
YAMLEOF
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor-domain 2>&1)
assert_contains_ci "coauthor-domain empty field falls back" "COAUTHOR_DOMAIN:aitasks.io" "$output"

# Restore project config for remaining tests
cp "$PROJECT_DIR/aitasks/metadata/project_config.yaml" "$TMPDIR_TEST/aitasks/metadata/project_config.yaml"

# Test 15: coauthor returns Codex metadata
echo "--- Test 15: coauthor Codex metadata ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor codex/gpt5_4 2>&1)
assert_contains_ci "coauthor returns agent string" "AGENT_STRING:codex/gpt5_4" "$output"
assert_contains_ci "coauthor returns name" "AGENT_COAUTHOR_NAME:Codex/GPT5.4" "$output"
assert_contains_ci "coauthor returns email" "AGENT_COAUTHOR_EMAIL:codex@aitasks.io" "$output"
assert_contains_ci "coauthor returns trailer" "AGENT_COAUTHOR_TRAILER:Co-Authored-By: Codex/GPT5.4 <codex@aitasks.io>" "$output"

# Test 15b: coauthor returns Codex GPT-5.6 metadata
echo "--- Test 15b: coauthor Codex GPT-5.6 metadata ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor codex/gpt5_6_sol 2>&1)
assert_contains_ci "coauthor returns GPT-5.6 Sol name" "AGENT_COAUTHOR_NAME:Codex/GPT5.6-Sol" "$output"

# Test 16: coauthor uses configured custom domain
echo "--- Test 16: coauthor custom domain ---"
cat > "$TMPDIR_TEST/aitasks/metadata/project_config.yaml" << 'YAMLEOF'
codeagent_coauthor_domain: codex.example
verify_build:
YAMLEOF
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor codex/gpt5_3codex 2>&1)
assert_contains_ci "coauthor uses custom domain for email" "AGENT_COAUTHOR_EMAIL:codex@codex.example" "$output"
assert_contains_ci "coauthor uses model-aware trailer" "AGENT_COAUTHOR_TRAILER:Co-Authored-By: Codex/GPT5.3-Codex <codex@codex.example>" "$output"

# Test 17: coauthor falls back to raw model token when model is unknown
echo "--- Test 17: coauthor unknown model fallback ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor codex/custom_model 2>&1)
assert_contains_ci "coauthor falls back to raw model token" "AGENT_COAUTHOR_NAME:Codex/custom_model" "$output"

# Restore project config before Claude coauthor tests
cp "$PROJECT_DIR/aitasks/metadata/project_config.yaml" "$TMPDIR_TEST/aitasks/metadata/project_config.yaml"

# Test 18: coauthor returns Claude Code metadata
echo "--- Test 18: coauthor Claude Code metadata ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor claudecode/opus4_6 2>&1)
assert_contains_ci "coauthor returns agent string" "AGENT_STRING:claudecode/opus4_6" "$output"
assert_contains_ci "coauthor returns name" "AGENT_COAUTHOR_NAME:Claude Code/Opus 4.6" "$output"
assert_contains_ci "coauthor returns email" "AGENT_COAUTHOR_EMAIL:claudecode@aitasks.io" "$output"
assert_contains_ci "coauthor returns trailer" "AGENT_COAUTHOR_TRAILER:Co-Authored-By: Claude Code/Opus 4.6 <claudecode@aitasks.io>" "$output"

# Test 19: coauthor Claude Code uses configured custom domain
echo "--- Test 19: coauthor Claude Code custom domain ---"
cat > "$TMPDIR_TEST/aitasks/metadata/project_config.yaml" << 'YAMLEOF'
codeagent_coauthor_domain: claude.example
verify_build:
YAMLEOF
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor claudecode/sonnet4_6 2>&1)
assert_contains_ci "coauthor uses custom domain for email" "AGENT_COAUTHOR_EMAIL:claudecode@claude.example" "$output"
assert_contains_ci "coauthor uses model-aware trailer" "AGENT_COAUTHOR_TRAILER:Co-Authored-By: Claude Code/Sonnet 4.6 <claudecode@claude.example>" "$output"

# Test 20: coauthor Claude Code falls back to raw model token when unknown
echo "--- Test 20: coauthor Claude Code unknown model fallback ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor claudecode/unknown_model 2>&1)
assert_contains_ci "coauthor falls back to raw model token" "AGENT_COAUTHOR_NAME:Claude Code/unknown_model" "$output"

# Test 21: coauthor Claude Code handles haiku model with date suffix in cli_id
echo "--- Test 21: coauthor Claude Code haiku model ---"
cp "$PROJECT_DIR/aitasks/metadata/project_config.yaml" "$TMPDIR_TEST/aitasks/metadata/project_config.yaml"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor claudecode/haiku4_5 2>&1)
assert_contains_ci "coauthor strips date suffix from haiku" "AGENT_COAUTHOR_NAME:Claude Code/Haiku 4.5" "$output"

# Test 22: coauthor returns OpenCode metadata (Claude model via opencode)
echo "--- Test 22: coauthor OpenCode metadata ---"
cp "$PROJECT_DIR/aitasks/metadata/project_config.yaml" "$TMPDIR_TEST/aitasks/metadata/project_config.yaml"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor opencode/opencode_claude_opus_4_6 2>&1)
assert_contains_ci "coauthor returns agent string" "AGENT_STRING:opencode/opencode_claude_opus_4_6" "$output"
assert_contains_ci "coauthor returns name" "AGENT_COAUTHOR_NAME:OpenCode/Claude Opus 4.6" "$output"
assert_contains_ci "coauthor returns email" "AGENT_COAUTHOR_EMAIL:opencode@aitasks.io" "$output"
assert_contains_ci "coauthor returns trailer" "AGENT_COAUTHOR_TRAILER:Co-Authored-By: OpenCode/Claude Opus 4.6 <opencode@aitasks.io>" "$output"

# Test 23: coauthor OpenCode uses configured custom domain
echo "--- Test 23: coauthor OpenCode custom domain ---"
cat > "$TMPDIR_TEST/aitasks/metadata/project_config.yaml" << 'YAMLEOF'
codeagent_coauthor_domain: opencode.example
verify_build:
YAMLEOF
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor opencode/opencode_gpt_5_4 2>&1)
assert_contains_ci "coauthor uses custom domain for email" "AGENT_COAUTHOR_EMAIL:opencode@opencode.example" "$output"
assert_contains_ci "coauthor uses model-aware trailer" "AGENT_COAUTHOR_TRAILER:Co-Authored-By: OpenCode/GPT 5.4 <opencode@opencode.example>" "$output"

# Test 24: coauthor OpenCode falls back to raw model token when unknown
echo "--- Test 24: coauthor OpenCode unknown model fallback ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor opencode/custom_model 2>&1)
assert_contains_ci "coauthor falls back to raw model token" "AGENT_COAUTHOR_NAME:OpenCode/custom_model" "$output"

# Test 25: coauthor OpenCode with GPT-style model (openai provider prefix)
echo "--- Test 25: coauthor OpenCode GPT model ---"
cp "$PROJECT_DIR/aitasks/metadata/project_config.yaml" "$TMPDIR_TEST/aitasks/metadata/project_config.yaml"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor opencode/openai_gpt_5_1_codex 2>&1)
assert_contains_ci "coauthor returns GPT name" "AGENT_COAUTHOR_NAME:OpenCode/GPT 5.1 Codex" "$output"

# Test 25b: coauthor OpenCode with GPT 5.4 openai provider entry
echo "--- Test 25b: coauthor OpenCode GPT 5.4 openai provider ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor opencode/openai_gpt_5_4 2>&1)
assert_contains_ci "coauthor returns GPT 5.4 name" "AGENT_COAUTHOR_NAME:OpenCode/GPT 5.4" "$output"

# Test 25c: coauthor OpenCode with GPT 5.6 openai provider
echo "--- Test 25c: coauthor OpenCode GPT 5.6 openai provider ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor opencode/openai_gpt_5_6_sol 2>&1)
assert_contains_ci "coauthor returns GPT 5.6 Sol name" "AGENT_COAUTHOR_NAME:OpenCode/GPT 5.6 Sol" "$output"

# Restore project config before help and remaining tests
cp "$PROJECT_DIR/aitasks/metadata/project_config.yaml" "$TMPDIR_TEST/aitasks/metadata/project_config.yaml"

# Test 27: --help shows usage
echo "--- Test 27: --help ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --help 2>&1)
assert_contains_ci "help shows Usage" "Usage:" "$output"
assert_contains_ci "help shows list-agents" "list-agents" "$output"
assert_contains_ci "help shows list-models" "list-models" "$output"
assert_contains_ci "help shows coauthor" "coauthor <agent-string>" "$output"
assert_contains_ci "help shows coauthor-domain" "coauthor-domain" "$output"
assert_contains_ci "help shows resolution chain" "Resolution chain" "$output"

# Test 28: resolve explain uses sonnet
echo "--- Test 28: resolve explain uses sonnet ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" resolve explain 2>&1)
assert_contains_ci "resolve explain returns sonnet5" "AGENT_STRING:claudecode/sonnet5" "$output"

# Test 29: resolve with unknown operation
echo "--- Test 29: resolve unknown operation ---"
assert_exit_nonzero "resolve rejects unknown operation" bash -c "cd '$TMPDIR_TEST' && bash '$CODEAGENT' resolve unknown-op"

# Test 30: no command shows help
echo "--- Test 30: no command shows help ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" 2>&1)
assert_contains_ci "no command shows usage" "Usage:" "$output"

# Test 31: unknown command fails
echo "--- Test 31: unknown command ---"
assert_exit_nonzero "unknown command fails" bash -c "cd '$TMPDIR_TEST' && bash '$CODEAGENT' nonexistent-command"

# --- Cleanup ---

set +e
cleanup_test_env "$TMPDIR_TEST"

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
