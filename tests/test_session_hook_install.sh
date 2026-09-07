#!/usr/bin/env bash
# test_session_hook_install.sh - installing the SessionStart hook (t1705_3).
#
# Covers the post-phase `fresh_install_hook_smoke` risk mitigation: the hook is
# a NEW INSTALL SURFACE, so the ways it can go wrong are (1) not installed at
# all, (2) installed while destroying something the user put in the same file,
# (3) installed three times, (4) installed without asking.
#
# KNOWN LOSS, asserted in Group D so it stays known rather than surprising:
# merge_codex_settings re-serialises the parsed TOML, so every comment in a
# user's .codex/config.toml is dropped on merge. That predates this task (it is
# how the codex merge has always worked); adding the [hooks] block just makes it
# reachable more often. Documented for users by the t1705 docs child.
#
# Drives the REAL setup functions via `aitask_setup.sh --source-only` against
# fixture project dirs -- the house pattern (see tests/test_setup_agent_config_seeds.sh).
# The consent cases additionally need a TTY, because every setup prompt is gated
# on `[[ -t 0 ]]` and a pipe silently takes the auto-accept branch; they use
# tests/lib/pty_drive.py.
#
# Run: bash tests/test_session_hook_install.sh

set -uo pipefail

PASS=0
FAIL=0
# shellcheck disable=SC2034  # TOTAL is mutated by the sourced asserts.sh helpers.
TOTAL=0

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

TESTROOT="$(mktemp -d)"
trap 'rm -rf "$TESTROOT"' EXIT

SEED_HOOKS="$PROJECT_DIR/seed/claude_settings.hooks.json"
HOOK_CMD_TAIL=".aitask-scripts/aitask_session_hook.sh"

# --- helpers ---------------------------------------------------------------

# Count aitasks SessionStart hook entries in a settings.json.
count_hook() {
    python3 - "$1" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    print(-1); raise SystemExit(0)
n = 0
for g in d.get("hooks", {}).get("SessionStart", []) or []:
    for h in (g.get("hooks") or []):
        if "aitask_session_hook.sh" in (h.get("command") or ""):
            n += 1
print(n)
PY
}

json_get() {
    python3 - "$1" "$2" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
for part in sys.argv[2].split('.'):
    if part.isdigit():
        d = d[int(part)]
    else:
        d = d[part]
print(json.dumps(d, sort_keys=True))
PY
}

# A fixture project with the hooks seed already staged in metadata.
make_fixture() {
    local dir="$TESTROOT/$1"
    mkdir -p "$dir/.aitask-scripts" "$dir/aitasks/metadata"
    cp "$SEED_HOOKS" "$dir/aitasks/metadata/claude_settings.hooks.json"
    echo "$dir"
}

echo "=== SessionStart hook install surface (t1705_3) ==="

# ---------------------------------------------------------------------------
echo ""
echo "--- Group 0: the seed and its two-sided wiring exist ---"
assert_eq "seed/claude_settings.hooks.json exists" "yes" \
    "$([ -f "$SEED_HOOKS" ] && echo yes || echo no)"
assert_eq "the seed names the hook script" "$HOOK_CMD_TAIL" \
    "$(python3 -c "
import json,sys
c=json.load(open(sys.argv[1]))['hooks']['SessionStart'][0]['hooks'][0]['command']
print(c.split('/',1)[1] if c.startswith('\$CLAUDE_PROJECT_DIR/') else c)" "$SEED_HOOKS")"
assert_eq "the seed uses \$CLAUDE_PROJECT_DIR (expanded by the agent)" "yes" \
    "$(grep -q 'CLAUDE_PROJECT_DIR' "$SEED_HOOKS" && echo yes || echo no)"
# install.sh half of the manifest (tests/test_seed_manifest_drift.sh proves the
# two halves agree; this just pins that the installer exists and is positioned).
assert_eq "install.sh defines install_seed_claude_hooks" "yes" \
    "$(grep -q '^install_seed_claude_hooks()' "$PROJECT_DIR/install.sh" && echo yes || echo no)"
wire_line="$(grep -n '^    install_seed_claude_hooks$' "$PROJECT_DIR/install.sh" | cut -d: -f1)"
# Anchor on the COMMAND (leading whitespace, start of line) -- a comment in
# install.sh mentions the same text and would make this grep ambiguous.
cleanup_line="$(grep -n '^[[:space:]]*rm -rf "\$INSTALL_DIR/seed"' "$PROJECT_DIR/install.sh" | cut -d: -f1 | head -1)"
assert_eq "install_seed_claude_hooks is wired BEFORE the seed cleanup" "yes" \
    "$([ -n "$wire_line" ] && [ -n "$cleanup_line" ] && [ "$wire_line" -lt "$cleanup_line" ] && echo yes || echo no)"
assert_eq ".claude/settings.json is in install.sh's framework paths" "yes" \
    "$(grep -q '"\.claude/settings\.json"' "$PROJECT_DIR/install.sh" && echo yes || echo no)"
assert_eq ".claude/settings.json is in _ait_framework_paths" "yes" \
    "$(grep -q '"\.claude/settings\.json"' "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" && echo yes || echo no)"

# ---------------------------------------------------------------------------
# Source the real setup for the function-level groups.
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" --source-only
# aitask_setup.sh runs `set -euo pipefail` at file scope, and sourcing it turns
# errexit ON in THIS shell. A suite whose assertions legitimately probe failing
# commands would then abort silently mid-run (observed: the consent group
# vanished with no output and a 0 status). Same relaxation, same reason, as
# tests/test_setup_agent_config_seeds.sh.
set +eu

echo ""
echo "--- Group A: fresh project gets the hook (non-interactive auto-accept) ---"
(
    DIR="$(make_fixture a_fresh)"
    SCRIPT_DIR="$DIR/.aitask-scripts"
    setup_claude_hooks </dev/null >/dev/null 2>&1
    assert_eq "A: .claude/settings.json created" "yes" \
        "$([ -f "$DIR/.claude/settings.json" ] && echo yes || echo no)"
    assert_eq "A: exactly one aitasks SessionStart hook" "1" "$(count_hook "$DIR/.claude/settings.json")"
)

echo ""
echo "--- Group B: an existing settings.json is PRESERVED ---"
(
    DIR="$(make_fixture b_preserve)"
    mkdir -p "$DIR/.claude"
    cat >"$DIR/.claude/settings.json" <<'EOF'
{
  "env": {"USER_KEY": "user-value"},
  "permissions": {"allow": ["Bash(ls:*)"]},
  "hooks": {
    "PreToolUse": [
      {"matcher": "Bash",
       "hooks": [{"type": "command", "command": "/user/guard.py", "timeout": 5}]}
    ],
    "SessionStart": [
      {"matcher": "clear",
       "hooks": [{"type": "command", "command": "/user/on-clear.sh"}]}
    ]
  }
}
EOF
    before_pretooluse="$(json_get "$DIR/.claude/settings.json" hooks.PreToolUse)"
    before_env="$(json_get "$DIR/.claude/settings.json" env)"
    before_perms="$(json_get "$DIR/.claude/settings.json" permissions)"
    before_foreign="$(json_get "$DIR/.claude/settings.json" hooks.SessionStart.0)"

    SCRIPT_DIR="$DIR/.aitask-scripts"
    setup_claude_hooks </dev/null >/dev/null 2>&1

    assert_eq "B: the aitasks hook was added" "1" "$(count_hook "$DIR/.claude/settings.json")"
    assert_eq "B: user PreToolUse hook survives byte-for-byte" \
        "$before_pretooluse" "$(json_get "$DIR/.claude/settings.json" hooks.PreToolUse)"
    assert_eq "B: unrelated top-level 'env' key survives" \
        "$before_env" "$(json_get "$DIR/.claude/settings.json" env)"
    assert_eq "B: unrelated 'permissions' key survives" \
        "$before_perms" "$(json_get "$DIR/.claude/settings.json" permissions)"
    assert_eq "B: the FOREIGN SessionStart group (matcher 'clear') survives" \
        "$before_foreign" "$(json_get "$DIR/.claude/settings.json" hooks.SessionStart.0)"
    assert_eq "B: the foreign group was not merged into — 2 groups now" "2" \
        "$(python3 -c "
import json,sys
print(len(json.load(open(sys.argv[1]))['hooks']['SessionStart']))" "$DIR/.claude/settings.json")"
)

echo ""
echo "--- Group C: idempotency across repeated \`ait setup\` ---"
(
    DIR="$(make_fixture c_idem)"
    SCRIPT_DIR="$DIR/.aitask-scripts"
    for _ in 1 2 3; do
        setup_claude_hooks </dev/null >/dev/null 2>&1
    done
    assert_eq "C: still exactly ONE aitasks hook after three runs" "1" \
        "$(count_hook "$DIR/.claude/settings.json")"
    assert_eq "C: still exactly ONE SessionStart group" "1" \
        "$(python3 -c "
import json,sys
print(len(json.load(open(sys.argv[1]))['hooks']['SessionStart']))" "$DIR/.claude/settings.json")"
)

echo ""
echo "--- Group C2: a user who hardcoded an absolute path is not duplicated ---"
(
    DIR="$(make_fixture c2_abs)"
    mkdir -p "$DIR/.claude"
    cat >"$DIR/.claude/settings.json" <<EOF
{"hooks": {"SessionStart": [
  {"matcher": "startup|resume",
   "hooks": [{"type": "command", "command": "$DIR/.aitask-scripts/aitask_session_hook.sh"}]}
]}}
EOF
    SCRIPT_DIR="$DIR/.aitask-scripts"
    setup_claude_hooks </dev/null >/dev/null 2>&1
    assert_eq "C2: the hardcoded-path hook is recognised, not duplicated" "1" \
        "$(count_hook "$DIR/.claude/settings.json")"
)

# ---------------------------------------------------------------------------
echo ""
echo "--- Group D: the codex [hooks] block round-trips through the TOML merge ---"
(
    DIR="$TESTROOT/d_codex"
    mkdir -p "$DIR/.aitask-scripts" "$DIR/.codex"
    SCRIPT_DIR="$DIR/.aitask-scripts"
    cat >"$DIR/.codex/config.toml" <<'EOF'
# a user comment
sandbox_mode = "workspace-write"

[profiles.mine]
model = "gpt-5.6"
EOF
    merge_codex_settings "$PROJECT_DIR/seed/codex_config.seed.toml" "$DIR/.codex/config.toml" >/dev/null 2>&1

    assert_eq "D: merged config is valid TOML" "yes" \
        "$(python3 -c "
import tomllib,sys
try:
    tomllib.load(open(sys.argv[1],'rb')); print('yes')
except Exception as e: print('no: %s' % e)" "$DIR/.codex/config.toml")"
    assert_eq "D: the [hooks] block survives the round trip" "$HOOK_CMD_TAIL" \
        "$(python3 -c "
import tomllib,sys
d=tomllib.load(open(sys.argv[1],'rb'))
print(d['hooks']['SessionStart'][0]['hooks'][0]['command'])" "$DIR/.codex/config.toml")"
    assert_eq "D: the user's [profiles.mine] table survives" "gpt-5.6" \
        "$(python3 -c "
import tomllib,sys
print(tomllib.load(open(sys.argv[1],'rb'))['profiles']['mine']['model'])" "$DIR/.codex/config.toml")"
    assert_eq "D: the protective prefix_rules survive" "3" \
        "$(python3 -c "
import tomllib,sys
print(len(tomllib.load(open(sys.argv[1],'rb'))['rules']['prefix_rules']))" "$DIR/.codex/config.toml")"

    # Idempotency: deep_merge dedups list entries by str(item).
    merge_codex_settings "$PROJECT_DIR/seed/codex_config.seed.toml" "$DIR/.codex/config.toml" >/dev/null 2>&1
    merge_codex_settings "$PROJECT_DIR/seed/codex_config.seed.toml" "$DIR/.codex/config.toml" >/dev/null 2>&1
    assert_eq "D: exactly ONE SessionStart group after three merges" "1" \
        "$(python3 -c "
import tomllib,sys
print(len(tomllib.load(open(sys.argv[1],'rb'))['hooks']['SessionStart']))" "$DIR/.codex/config.toml")"

    # KNOWN LOSS, asserted so it stays a known loss rather than a surprise:
    # toml_serialize re-emits the parsed structure and drops every comment.
    # Documented in the codex seed and in the docs child's "Session hooks".
    assert_eq "D: KNOWN LOSS — user comments are dropped by toml_serialize" "gone" \
        "$(grep -q 'a user comment' "$DIR/.codex/config.toml" && echo kept || echo gone)"
)

# ---------------------------------------------------------------------------
echo ""
echo "--- Group E: CONSENT (needs a real TTY — see tests/lib/pty_drive.py) ---"

# A driver the PTY can exec: sources setup and runs just the hook installer.
DRIVER="$TESTROOT/drive_hooks.sh"
cat >"$DRIVER" <<EOF
#!/usr/bin/env bash
set -uo pipefail
source "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" --source-only
SCRIPT_DIR="\$1/.aitask-scripts"
setup_claude_hooks
EOF
chmod +x "$DRIVER"

pty_run() {  # pty_run <answers-csv> <fixture-dir>
    python3 "$PROJECT_DIR/tests/lib/pty_drive.py" --answers "$1" -- bash "$DRIVER" "$2" 2>&1
}

# One bare Enter. NOT `pty_run ''`: an empty --answers means "send nothing",
# which would hang at the prompt until the harness timeout rather than testing
# the default.
pty_run_enter() {  # pty_run_enter <fixture-dir>
    python3 "$PROJECT_DIR/tests/lib/pty_drive.py" --answer '' -- bash "$DRIVER" "$1" 2>&1
}

# E0: the harness really does present a TTY (without this, every case below
# would be silently exercising the auto-accept branch and proving nothing).
E0="$(make_fixture e0_tty)"
out_e0="$(pty_run 'Y' "$E0")"
assert_eq "E0: the prompt is actually shown (a TTY was allocated)" "yes" \
    "$(printf '%s' "$out_e0" | grep -q 'Install the session hook?' && echo yes || echo no)"
assert_eq "E0: 'auto-accepting default' did NOT fire under a TTY" "no" \
    "$(printf '%s' "$out_e0" | grep -q 'auto-accepting default' && echo yes || echo no)"
assert_eq "E0: accepting installs the hook" "1" "$(count_hook "$E0/.claude/settings.json")"

# E1: declining installs nothing, and setup still completes.
E1="$(make_fixture e1_decline)"
out_e1="$(pty_run 'n' "$E1")"
assert_eq "E1: the decline is acknowledged" "yes" \
    "$(printf '%s' "$out_e1" | grep -q 'Skipped Claude Code session hook' && echo yes || echo no)"
assert_eq "E1: no .claude/settings.json was created" "no" \
    "$([ -f "$E1/.claude/settings.json" ] && echo yes || echo no)"

# E1b: declining leaves an EXISTING settings.json byte-for-byte untouched.
E1B="$(make_fixture e1b_decline_existing)"
mkdir -p "$E1B/.claude"
printf '{\n  "env": {"K": "V"}\n}\n' >"$E1B/.claude/settings.json"
before_sum="$(cksum <"$E1B/.claude/settings.json")"
pty_run 'n' "$E1B" >/dev/null
assert_eq "E1b: an existing settings.json is untouched on decline" \
    "$before_sum" "$(cksum <"$E1B/.claude/settings.json")"
assert_eq "E1b: and still carries no aitasks hook" "0" "$(count_hook "$E1B/.claude/settings.json")"

# E2: a decline is NOT remembered — the next run asks again (house convention:
# no persistence, no new config field). Pinned so that changing to "remember
# the decline" has to be a deliberate decision, not a silent drift.
E2="$(make_fixture e2_reoffer)"
pty_run 'n' "$E2" >/dev/null
out_e2b="$(pty_run 'n' "$E2")"
assert_eq "E2: the prompt is offered AGAIN after a previous decline" "yes" \
    "$(printf '%s' "$out_e2b" | grep -q 'Install the session hook?' && echo yes || echo no)"
assert_eq "E2: and still installs nothing" "no" \
    "$([ -f "$E2/.claude/settings.json" ] && echo yes || echo no)"
# ...and a later YES still works.
pty_run 'Y' "$E2" >/dev/null
assert_eq "E2: accepting after two declines installs the hook" "1" \
    "$(count_hook "$E2/.claude/settings.json")"

# E3: a bare Enter takes the default (Y).
E3="$(make_fixture e3_default)"
pty_run_enter "$E3" >/dev/null
assert_eq "E3: bare Enter accepts (default is Y)" "1" "$(count_hook "$E3/.claude/settings.json")"

# E4: THE ORDERING CASE — declining PERMISSIONS must not suppress the hook
# offer. This is the exact failure a hooks-inside-setup_claude_code shape would
# have shipped, and it is invisible to every non-interactive test above.
E4="$(make_fixture e4_perm_decline)"
cp "$PROJECT_DIR/seed/claude_settings.local.json" "$E4/aitasks/metadata/claude_settings.seed.json"
DRIVER2="$TESTROOT/drive_both.sh"
cat >"$DRIVER2" <<EOF
#!/usr/bin/env bash
set -uo pipefail
source "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" --source-only
SCRIPT_DIR="\$1/.aitask-scripts"
setup_claude_code
setup_claude_hooks
EOF
chmod +x "$DRIVER2"
out_e4="$(python3 "$PROJECT_DIR/tests/lib/pty_drive.py" --answers 'n,Y' -- bash "$DRIVER2" "$E4" 2>&1)"
assert_eq "E4: permissions were declined" "yes" \
    "$(printf '%s' "$out_e4" | grep -q 'Skipped Claude Code permission settings' && echo yes || echo no)"
assert_eq "E4: the hook was STILL offered after that decline" "yes" \
    "$(printf '%s' "$out_e4" | grep -q 'Install the session hook?' && echo yes || echo no)"
assert_eq "E4: and installing it works" "1" "$(count_hook "$E4/.claude/settings.json")"
assert_eq "E4: settings.local.json was NOT written (permissions declined)" "no" \
    "$([ -f "$E4/.claude/settings.local.json" ] && echo yes || echo no)"

echo ""
echo "========================================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
echo "========================================="
[[ "$FAIL" -eq 0 ]] || exit 1
echo "ALL TESTS PASSED"
