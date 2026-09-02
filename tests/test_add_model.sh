#!/usr/bin/env bash
# test_add_model.sh - Unit tests for aitask_add_model.sh
# Run: bash tests/test_add_model.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"
HELPER="$PROJECT_DIR/.aitask-scripts/aitask_add_model.sh"

PASS=0
FAIL=0
TOTAL=0

# --- Fixture helpers ---

setup_fixture() {
    # Creates a temp repo layout and exports AITASK_REPO_ROOT.
    FIXTURE_DIR=$(mktemp -d "${TMPDIR:-/tmp}/test_add_model_XXXXXX")
    export AITASK_REPO_ROOT="$FIXTURE_DIR"
    mkdir -p "$FIXTURE_DIR/aitasks/metadata" "$FIXTURE_DIR/seed" \
        "$FIXTURE_DIR/.aitask-scripts" "$FIXTURE_DIR/.aitask-scripts/lib"

    # Minimal models_claudecode.json with one existing entry carrying verified scores
    cat > "$FIXTURE_DIR/aitasks/metadata/models_claudecode.json" <<'EOF'
{
  "models": [
    {
      "name": "opus4_6",
      "cli_id": "claude-opus-4-6",
      "notes": "existing",
      "verified": { "pick": 98 },
      "verifiedstats": { "pick": { "all_time": { "runs": 10, "score_sum": 980 } } }
    }
  ]
}
EOF
    cat > "$FIXTURE_DIR/seed/models_claudecode.json" <<'EOF'
{
  "models": [
    {
      "name": "opus4_6",
      "cli_id": "claude-opus-4-6",
      "notes": "existing",
      "verified": {},
      "verifiedstats": {}
    }
  ]
}
EOF

    cat > "$FIXTURE_DIR/aitasks/metadata/codeagent_config.json" <<'EOF'
{
  "defaults": {
    "pick": "claudecode/opus4_6",
    "explain": "claudecode/sonnet4_6",
    "explore": "claudecode/opus4_6",
    "brainstorm-explorer": "claudecode/opus4_6",
    "brainstorm-synthesizer": "claudecode/opus4_6"
  }
}
EOF
    cat > "$FIXTURE_DIR/seed/codeagent_config.json" <<'EOF'
{
  "defaults": {
    "pick": "claudecode/opus4_6",
    "explain": "claudecode/sonnet4_6",
    "explore": "claudecode/opus4_6"
  }
}
EOF

    # Stub lib/agent_string.sh with the DEFAULT_AGENT_STRING anchor the helper
    # patches. Keep the parameter-expansion shape byte-exact with the real file
    # so the caller-override capability is exercised.
    cat > "$FIXTURE_DIR/.aitask-scripts/lib/agent_string.sh" <<'EOF'
#!/usr/bin/env bash
# stub for tests

DEFAULT_AGENT_STRING="${DEFAULT_AGENT_STRING:-claudecode/opus4_6}"
METADATA_DIR="aitasks/metadata"
EOF
    chmod +x "$FIXTURE_DIR/.aitask-scripts/lib/agent_string.sh"

    # Stub aitask_codeagent.sh with the resolution-chain note the helper patches.
    # Keep the anchor byte-exact with the real file.
    cat > "$FIXTURE_DIR/.aitask-scripts/aitask_codeagent.sh" <<'EOF'
#!/usr/bin/env bash
# stub for tests

METADATA_DIR="aitasks/metadata"
DEFAULT_COAUTHOR_DOMAIN="aitasks.io"

# ...help text...
# Resolution chain (highest priority first):
#   1. --agent-string flag
#   2. aitasks/metadata/codeagent_config.local.json (per-user, gitignored)
#   3. aitasks/metadata/codeagent_config.json (per-project, git-tracked)
  4. Hardcoded default: claudecode/opus4_6
EOF
    chmod +x "$FIXTURE_DIR/.aitask-scripts/aitask_codeagent.sh"
}

teardown_fixture() {
    [[ -n "${FIXTURE_DIR:-}" && -d "$FIXTURE_DIR" ]] && rm -rf "$FIXTURE_DIR"
    unset AITASK_REPO_ROOT FIXTURE_DIR
}

# Octal mode of a file. `stat -c` is GNU, `stat -f` is BSD — the same fallback
# chain lib/atomic_write.sh::ait_file_mode uses.
file_mode() {
    stat -c '%a' "$1" 2>/dev/null || stat -f '%Lp' "$1" 2>/dev/null || true
}

# Fail if any dot-prefixed staging temp was left behind in <dir>. The atomic
# writer stages `.<basename>.XXXXXX` beside its destination, so a leaked temp
# lands inside the repo tree rather than in $TMPDIR.
assert_no_staged_temp() {
    local label="$1" dir="$2" leaked
    leaked=$(find "$dir" -maxdepth 1 -name '.*.??????' -type f 2>/dev/null | tr '\n' ' ')
    if [[ -z "$leaked" ]]; then
        echo "  PASS: $label"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $label — leaked: $leaked"
        FAIL=$((FAIL + 1))
    fi
    TOTAL=$((TOTAL + 1))
}

# --- Tests ---

echo "=== Test 1: add-json appends entry and preserves existing verified/verifiedstats ==="
setup_fixture
bash "$HELPER" add-json --agent claudecode --name opus4_7 --cli-id claude-opus-4-7 --notes "new flagship" >/dev/null
count=$(jq '.models | length' "$FIXTURE_DIR/aitasks/metadata/models_claudecode.json")
assert_eq "metadata has 2 models" "2" "$count"
new_name=$(jq -r '.models[1].name' "$FIXTURE_DIR/aitasks/metadata/models_claudecode.json")
assert_eq "new model is opus4_7" "opus4_7" "$new_name"
preserved_score=$(jq -r '.models[0].verified.pick' "$FIXTURE_DIR/aitasks/metadata/models_claudecode.json")
assert_eq "existing verified.pick preserved" "98" "$preserved_score"
preserved_runs=$(jq -r '.models[0].verifiedstats.pick.all_time.runs' "$FIXTURE_DIR/aitasks/metadata/models_claudecode.json")
assert_eq "existing verifiedstats preserved" "10" "$preserved_runs"
seed_count=$(jq '.models | length' "$FIXTURE_DIR/seed/models_claudecode.json")
assert_eq "seed also synced (2 models)" "2" "$seed_count"
teardown_fixture

echo "=== Test 2: add-json second run errors clearly (idempotent-with-error) ==="
setup_fixture
bash "$HELPER" add-json --agent claudecode --name opus4_7 --cli-id claude-opus-4-7 --notes "n" >/dev/null
result=$(bash "$HELPER" add-json --agent claudecode --name opus4_7 --cli-id claude-opus-4-7 --notes "n" 2>&1 || true)
assert_contains "second run errors with 'already exists'" "already exists" "$result"
teardown_fixture

echo "=== Test 3: promote-config updates only listed ops, including brainstorm-* ==="
setup_fixture
bash "$HELPER" promote-config --agent claudecode --name opus4_7 \
    --ops pick,brainstorm-explorer >/dev/null
pick_val=$(jq -r '.defaults.pick' "$FIXTURE_DIR/aitasks/metadata/codeagent_config.json")
explain_val=$(jq -r '.defaults.explain' "$FIXTURE_DIR/aitasks/metadata/codeagent_config.json")
explore_val=$(jq -r '.defaults.explore' "$FIXTURE_DIR/aitasks/metadata/codeagent_config.json")
brainstorm_ex=$(jq -r '.defaults["brainstorm-explorer"]' "$FIXTURE_DIR/aitasks/metadata/codeagent_config.json")
brainstorm_syn=$(jq -r '.defaults["brainstorm-synthesizer"]' "$FIXTURE_DIR/aitasks/metadata/codeagent_config.json")
assert_eq "pick updated" "claudecode/opus4_7" "$pick_val"
assert_eq "brainstorm-explorer updated" "claudecode/opus4_7" "$brainstorm_ex"
assert_eq "brainstorm-synthesizer untouched" "claudecode/opus4_6" "$brainstorm_syn"
assert_eq "explain untouched" "claudecode/sonnet4_6" "$explain_val"
assert_eq "explore untouched" "claudecode/opus4_6" "$explore_val"
# Seed: pick exists (should update), brainstorm-explorer does NOT (should skip silently)
seed_pick=$(jq -r '.defaults.pick' "$FIXTURE_DIR/seed/codeagent_config.json")
seed_has_brainstorm=$(jq 'has("defaults") and (.defaults | has("brainstorm-explorer"))' "$FIXTURE_DIR/seed/codeagent_config.json")
assert_eq "seed pick updated" "claudecode/opus4_7" "$seed_pick"
assert_eq "seed does not gain brainstorm-explorer" "false" "$seed_has_brainstorm"
teardown_fixture

echo "=== Test 4: promote-default-agent-string rejects non-claudecode + patches lib/agent_string.sh and the codeagent note ==="
setup_fixture
# Rejection path
result=$(bash "$HELPER" promote-default-agent-string --agent codex --name gpt5_4 2>&1 || true)
assert_contains "rejects non-claudecode" "only supports agent 'claudecode'" "$result"
# Apply path
bash "$HELPER" promote-default-agent-string --agent claudecode --name opus4_7 >/dev/null
lib="$FIXTURE_DIR/.aitask-scripts/lib/agent_string.sh"
note_src="$FIXTURE_DIR/.aitask-scripts/aitask_codeagent.sh"
default_line=$(grep '^DEFAULT_AGENT_STRING=' "$lib")
assert_eq "DEFAULT_AGENT_STRING updated (param-expansion shape preserved)" \
    'DEFAULT_AGENT_STRING="${DEFAULT_AGENT_STRING:-claudecode/opus4_7}"' "$default_line"
resolution_line=$(grep '^  4\. Hardcoded default:' "$note_src")
assert_eq "resolution-chain note updated" "  4. Hardcoded default: claudecode/opus4_7" "$resolution_line"
# Executable bit preserved on both patched files
if [[ -x "$lib" && -x "$note_src" ]]; then
    echo "  PASS: executable bit preserved on both patched files"
    PASS=$((PASS + 1))
else
    echo "  FAIL: executable bit NOT preserved on both patched files"
    FAIL=$((FAIL + 1))
fi
TOTAL=$((TOTAL + 1))
teardown_fixture

echo "=== Test 5: --dry-run emits diffs AND leaves filesystem unchanged across all subcommands ==="
setup_fixture
checksum_before=$(find "$FIXTURE_DIR" -type f -print0 | sort -z | xargs -0 cat | md5sum | awk '{print $1}')

dry1=$(bash "$HELPER" add-json --dry-run --agent claudecode --name opus4_7 \
    --cli-id claude-opus-4-7 --notes "n" 2>&1)
assert_contains "add-json dry-run emits diff (metadata)" "+++ b/aitasks/metadata/models_claudecode.json" "$dry1"
assert_contains "add-json dry-run emits diff (seed)" "+++ b/seed/models_claudecode.json" "$dry1"
assert_contains "add-json dry-run mentions new name" "opus4_7" "$dry1"

dry2=$(bash "$HELPER" promote-config --dry-run --agent claudecode --name opus4_7 \
    --ops pick,brainstorm-explorer 2>&1)
assert_contains "promote-config dry-run emits diff" "+++ b/aitasks/metadata/codeagent_config.json" "$dry2"

dry3=$(bash "$HELPER" promote-default-agent-string --dry-run --agent claudecode \
    --name opus4_7 2>&1)
assert_contains "promote-default dry-run emits lib diff" "+++ b/.aitask-scripts/lib/agent_string.sh" "$dry3"
assert_contains "promote-default dry-run emits note diff" "+++ b/.aitask-scripts/aitask_codeagent.sh" "$dry3"

checksum_after=$(find "$FIXTURE_DIR" -type f -print0 | sort -z | xargs -0 cat | md5sum | awk '{print $1}')
assert_eq "filesystem unchanged after all dry-runs" "$checksum_before" "$checksum_after"

# Produced JSON always validates (cover both real writes and dry-run internals)
bash "$HELPER" add-json --agent claudecode --name opus4_7 --cli-id claude-opus-4-7 --notes "n" >/dev/null
if jq . "$FIXTURE_DIR/aitasks/metadata/models_claudecode.json" >/dev/null 2>&1; then
    echo "  PASS: metadata JSON validates after apply"
    PASS=$((PASS + 1))
else
    echo "  FAIL: metadata JSON invalid after apply"
    FAIL=$((FAIL + 1))
fi
TOTAL=$((TOTAL + 1))
if jq . "$FIXTURE_DIR/seed/models_claudecode.json" >/dev/null 2>&1; then
    echo "  PASS: seed JSON validates after apply"
    PASS=$((PASS + 1))
else
    echo "  FAIL: seed JSON invalid after apply"
    FAIL=$((FAIL + 1))
fi
TOTAL=$((TOTAL + 1))
teardown_fixture

echo "=== Test 6: invalid inputs fail with clear errors ==="
setup_fixture
r1=$(bash "$HELPER" add-json --agent unknownagent --name x --cli-id y --notes z 2>&1 || true)
assert_contains "unknown agent rejected" "Unknown agent" "$r1"

r2=$(bash "$HELPER" add-json --agent claudecode --name BadName --cli-id y --notes z 2>&1 || true)
assert_contains "uppercase name rejected" "Invalid model name" "$r2"

r3=$(bash "$HELPER" add-json --agent claudecode --name has_space --cli-id "" --notes z 2>&1 || true)
assert_contains "empty cli-id rejected" "--cli-id is required" "$r3"

r4=$(bash "$HELPER" add-json --agent opencode --name x --cli-id y --notes z 2>&1 || true)
assert_contains "opencode rejected with pointer" "aitask-refresh-code-models" "$r4"

r5=$(bash "$HELPER" add-json --agent claudecode --name "has space" --cli-id y --notes z 2>&1 || true)
assert_contains "name with space rejected" "Invalid model name" "$r5"
teardown_fixture

echo "=== Test 7: writes preserve each destination's own mode (both directions) ==="
setup_fixture
# A deliberate 644/600 split so BOTH drift directions are discriminating: a
# `mv` from a 0600 mktemp narrows the 644 destinations, while a hardcoded
# `chmod 644` would widen the 600 ones. Only true per-file preservation passes
# both. `lib/agent_string.sh` is pinned 640 (non-executable) and
# `aitask_codeagent.sh` 755, so the read bits and the exec bit are both covered.
chmod 644 "$FIXTURE_DIR/aitasks/metadata/models_claudecode.json"
chmod 600 "$FIXTURE_DIR/seed/models_claudecode.json"
chmod 644 "$FIXTURE_DIR/aitasks/metadata/codeagent_config.json"
chmod 600 "$FIXTURE_DIR/seed/codeagent_config.json"
chmod 640 "$FIXTURE_DIR/.aitask-scripts/lib/agent_string.sh"
chmod 755 "$FIXTURE_DIR/.aitask-scripts/aitask_codeagent.sh"

mode_paths=(
    "aitasks/metadata/models_claudecode.json"
    "seed/models_claudecode.json"
    "aitasks/metadata/codeagent_config.json"
    "seed/codeagent_config.json"
    ".aitask-scripts/lib/agent_string.sh"
    ".aitask-scripts/aitask_codeagent.sh"
)
mode_before=()
for rel in "${mode_paths[@]}"; do
    mode_before+=("$(file_mode "$FIXTURE_DIR/$rel")")
done

bash "$HELPER" add-json --agent claudecode --name opus4_7 --cli-id claude-opus-4-7 --notes "new flagship" >/dev/null
bash "$HELPER" promote-config --agent claudecode --name opus4_7 --ops pick >/dev/null
bash "$HELPER" promote-default-agent-string --agent claudecode --name opus4_7 >/dev/null

# The mode assertions below only mean something if the writes actually landed —
# a subcommand that silently no-ops would satisfy them vacuously.
assert_eq "add-json actually wrote (2 models)" "2" \
    "$(jq '.models | length' "$FIXTURE_DIR/aitasks/metadata/models_claudecode.json")"
assert_eq "promote-config actually wrote (pick)" "claudecode/opus4_7" \
    "$(jq -r '.defaults.pick' "$FIXTURE_DIR/aitasks/metadata/codeagent_config.json")"
assert_eq "promote-default actually wrote (DEFAULT_AGENT_STRING)" \
    'DEFAULT_AGENT_STRING="${DEFAULT_AGENT_STRING:-claudecode/opus4_7}"' \
    "$(grep '^DEFAULT_AGENT_STRING=' "$FIXTURE_DIR/.aitask-scripts/lib/agent_string.sh")"

for i in "${!mode_paths[@]}"; do
    assert_eq "mode preserved: ${mode_paths[$i]}" \
        "${mode_before[$i]}" "$(file_mode "$FIXTURE_DIR/${mode_paths[$i]}")"
done

assert_no_staged_temp "no staged temp left in aitasks/metadata" "$FIXTURE_DIR/aitasks/metadata"
assert_no_staged_temp "no staged temp left in seed" "$FIXTURE_DIR/seed"
assert_no_staged_temp "no staged temp left in .aitask-scripts/lib" "$FIXTURE_DIR/.aitask-scripts/lib"
teardown_fixture

echo "=== Test 8: writes follow a symlinked destination instead of replacing it ==="
setup_fixture
# The three write paths did not agree on file-symlink semantics before t1684:
# `mv` REPLACED a symlinked destination (orphaning the backing file), while
# `cat > "$dest"` followed it. Both now route through lib/atomic_write.sh,
# which resolves the link and renames onto the backing file. Covered here on
# one former-`mv` path (add-json) and on the former-`cat >` path
# (promote-default-agent-string), where following the link is a no-regression
# requirement. The links are RELATIVE so ait_atomic_resolve's non-absolute
# branch is the one exercised.
mkdir -p "$FIXTURE_DIR/real"
mv "$FIXTURE_DIR/aitasks/metadata/models_claudecode.json" "$FIXTURE_DIR/real/models_claudecode.json"
ln -s "../../real/models_claudecode.json" "$FIXTURE_DIR/aitasks/metadata/models_claudecode.json"
chmod 640 "$FIXTURE_DIR/real/models_claudecode.json"
mv "$FIXTURE_DIR/.aitask-scripts/lib/agent_string.sh" "$FIXTURE_DIR/real/agent_string.sh"
ln -s "../../real/agent_string.sh" "$FIXTURE_DIR/.aitask-scripts/lib/agent_string.sh"
chmod 600 "$FIXTURE_DIR/real/agent_string.sh"

bash "$HELPER" add-json --agent claudecode --name opus4_7 --cli-id claude-opus-4-7 --notes "new flagship" >/dev/null
bash "$HELPER" promote-default-agent-string --agent claudecode --name opus4_7 >/dev/null

link_json="$FIXTURE_DIR/aitasks/metadata/models_claudecode.json"
link_lib="$FIXTURE_DIR/.aitask-scripts/lib/agent_string.sh"

if [[ -L "$link_json" && -L "$link_lib" ]]; then
    echo "  PASS: both destinations are still symlinks"
    PASS=$((PASS + 1))
else
    echo "  FAIL: a destination was replaced by a regular file"
    FAIL=$((FAIL + 1))
fi
TOTAL=$((TOTAL + 1))

assert_eq "add-json link target unchanged" "../../real/models_claudecode.json" "$(readlink "$link_json")"
assert_eq "promote-default link target unchanged" "../../real/agent_string.sh" "$(readlink "$link_lib")"

# The write must have gone THROUGH the link — the backing file is what changed.
assert_eq "backing registry updated (2 models)" "2" \
    "$(jq '.models | length' "$FIXTURE_DIR/real/models_claudecode.json")"
assert_eq "backing lib updated (DEFAULT_AGENT_STRING)" \
    'DEFAULT_AGENT_STRING="${DEFAULT_AGENT_STRING:-claudecode/opus4_7}"' \
    "$(grep '^DEFAULT_AGENT_STRING=' "$FIXTURE_DIR/real/agent_string.sh")"

# Mode preservation must read the resolved path, not the link.
assert_eq "backing registry mode preserved" "640" "$(file_mode "$FIXTURE_DIR/real/models_claudecode.json")"
assert_eq "backing lib mode preserved" "600" "$(file_mode "$FIXTURE_DIR/real/agent_string.sh")"

assert_no_staged_temp "no staged temp left beside the backing files" "$FIXTURE_DIR/real"
teardown_fixture

echo "=== Test 9: a failed second write leaves no staging temp behind ==="
setup_fixture
# commit_staged COPIES its source (ait_atomic_render reads it) where the old
# `mv` consumed it — so a handler that cleans up only the second temp strands
# the first. Forced here by making the seed/ directory unwritable, which fails
# ait_atomic_tmp's mktemp for the second destination only. TMPDIR is scoped to
# the fixture so the assertion sees this run's temps and nothing else.
fixture_tmp="$FIXTURE_DIR/tmpdir"
mkdir -p "$fixture_tmp"
chmod 500 "$FIXTURE_DIR/seed"

set +e
TMPDIR="$fixture_tmp" bash "$HELPER" add-json --agent claudecode --name opus4_7 \
    --cli-id claude-opus-4-7 --notes n >/dev/null 2>"$FIXTURE_DIR/err.txt"
add_rc=$?
set -e
chmod 755 "$FIXTURE_DIR/seed"

assert_eq "add-json fails when the seed write fails" "1" "$add_rc"
assert_contains "failure names the seed registry" "seed/models_claudecode.json" \
    "$(cat "$FIXTURE_DIR/err.txt")"

leftover=$(find "$fixture_tmp" -type f | tr '\n' ' ')
if [[ -z "$leftover" ]]; then
    echo "  PASS: no staging temp stranded in TMPDIR after the failed write"
    PASS=$((PASS + 1))
else
    echo "  FAIL: staging temp stranded in TMPDIR: $leftover"
    FAIL=$((FAIL + 1))
fi
TOTAL=$((TOTAL + 1))
teardown_fixture

# --- Summary ---
echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ "$FAIL" -gt 0 ]]; then
    exit 1
fi
