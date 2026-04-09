#!/usr/bin/env bash
# test_setup_git_tui.sh - Tests for setup_git_tui and helpers
# Run: bash tests/test_setup_git_tui.sh

THIS_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$THIS_SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    expected="$(echo "$expected" | xargs)"
    actual="$(echo "$actual" | xargs)"
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected '$expected', got '$actual')"
    fi
}

assert_contains() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qi "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected')"
    fi
}

# Create a fake project dir with proper SCRIPT_DIR structure
# setup_git_tui uses $SCRIPT_DIR/.. as project root
setup_fake_project() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    mkdir -p "$tmpdir/.aitask-scripts"
    mkdir -p "$tmpdir/aitasks/metadata"
    echo "$tmpdir"
}

# Build a restricted bin dir with only essential external tools,
# excluding lazygit/gitui/tig. Optionally add mock TUI executables.
# Usage: make_restricted_bin [tool1 tool2 ...]
make_restricted_bin() {
    local rbin
    rbin=$(mktemp -d)
    # Symlink essential external commands needed by setup_git_tui
    local cmd src
    for cmd in grep sed cat mktemp mv rm; do
        src=$(command -v "$cmd" 2>/dev/null) || true
        if [[ -n "$src" && -f "$src" ]]; then
            ln -sf "$src" "$rbin/$cmd"
        fi
    done
    # Add requested mock TUI tools
    for tool in "$@"; do
        printf '#!/bin/sh\necho mock\n' > "$rbin/$tool"
        chmod +x "$rbin/$tool"
    done
    echo "$rbin"
}

# Source setup script for function access
source "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" --source-only
set +euo pipefail

echo "=== setup_git_tui Tests ==="
echo ""

# --- Test 1: _set_git_tui_config updates existing git_tui line ---
echo "--- Test 1: _set_git_tui_config updates existing line ---"

tmpf=$(mktemp)
cat > "$tmpf" <<'YAML'
tmux:
  default_session: aitasks
  git_tui:
  monitor:
    refresh_seconds: 3
YAML

_set_git_tui_config "$tmpf" "lazygit"

result=$(grep 'git_tui:' "$tmpf")
assert_eq "git_tui line updated" "git_tui: lazygit" "$result"

assert_contains "default_session preserved" "default_session: aitasks" "$(cat "$tmpf")"
assert_contains "monitor preserved" "refresh_seconds: 3" "$(cat "$tmpf")"
rm -f "$tmpf"

# --- Test 2: _set_git_tui_config appends tmux section when missing ---
echo "--- Test 2: _set_git_tui_config appends when missing ---"

tmpf=$(mktemp)
cat > "$tmpf" <<'YAML'
codeagent_coauthor_domain: aitasks.io
verify_build:
YAML

_set_git_tui_config "$tmpf" "gitui"

assert_contains "tmux section appended" "tmux:" "$(cat "$tmpf")"
assert_contains "git_tui set" "git_tui: gitui" "$(cat "$tmpf")"
assert_contains "original content preserved" "codeagent_coauthor_domain: aitasks.io" "$(cat "$tmpf")"
rm -f "$tmpf"

# --- Test 3: _set_git_tui_config preserves indentation ---
echo "--- Test 3: _set_git_tui_config preserves indentation ---"

tmpf=$(mktemp)
cat > "$tmpf" <<'YAML'
tmux:
  git_tui:
YAML

_set_git_tui_config "$tmpf" "tig"

result=$(grep 'git_tui:' "$tmpf")
assert_eq "Indentation preserved" "  git_tui: tig" "$result"
rm -f "$tmpf"

# --- Test 4: setup_git_tui skips when already configured ---
echo "--- Test 4: setup_git_tui skips when already configured ---"

tmpdir=$(setup_fake_project)
cat > "$tmpdir/aitasks/metadata/project_config.yaml" <<'YAML'
tmux:
  git_tui: lazygit
YAML

SCRIPT_DIR="$tmpdir/.aitask-scripts"
output=$(setup_git_tui 2>&1 </dev/null)
assert_contains "Reports already configured" "already configured" "$output"

result=$(grep 'git_tui:' "$tmpdir/aitasks/metadata/project_config.yaml")
assert_eq "Config unchanged" "git_tui: lazygit" "$result"
rm -rf "$tmpdir"

# --- Test 5: setup_git_tui skips when no config file ---
echo "--- Test 5: setup_git_tui skips when no config file ---"

tmpdir=$(setup_fake_project)
rm -f "$tmpdir/aitasks/metadata/project_config.yaml"

SCRIPT_DIR="$tmpdir/.aitask-scripts"
output=$(setup_git_tui 2>&1 </dev/null)
assert_contains "Reports skipping" "skipping" "$output"
rm -rf "$tmpdir"

# --- Test 6: setup_git_tui auto-detects single TUI (non-interactive) ---
echo "--- Test 6: Auto-detect single TUI ---"

tmpdir=$(setup_fake_project)
cat > "$tmpdir/aitasks/metadata/project_config.yaml" <<'YAML'
tmux:
  git_tui:
YAML

rbin=$(make_restricted_bin lazygit)

SCRIPT_DIR="$tmpdir/.aitask-scripts"
output=$(PATH="$rbin" setup_git_tui 2>&1 </dev/null)

result=$(grep 'git_tui:' "$tmpdir/aitasks/metadata/project_config.yaml")
assert_eq "Config set to lazygit" "  git_tui: lazygit" "$result"
assert_contains "Reports detected" "Detected git TUI" "$output"
rm -rf "$tmpdir" "$rbin"

# --- Test 7: setup_git_tui selects first with multiple (non-interactive) ---
echo "--- Test 7: Multiple TUIs non-interactive ---"

tmpdir=$(setup_fake_project)
cat > "$tmpdir/aitasks/metadata/project_config.yaml" <<'YAML'
tmux:
  git_tui:
YAML

rbin=$(make_restricted_bin lazygit gitui)

SCRIPT_DIR="$tmpdir/.aitask-scripts"
output=$(PATH="$rbin" setup_git_tui 2>&1 </dev/null)

result=$(grep 'git_tui:' "$tmpdir/aitasks/metadata/project_config.yaml")
assert_eq "Selects lazygit (first)" "  git_tui: lazygit" "$result"
assert_contains "Reports auto-selecting" "auto-selecting" "$output"
rm -rf "$tmpdir" "$rbin"

# --- Test 8: setup_git_tui skips install (non-interactive, no TUIs) ---
echo "--- Test 8: No TUIs non-interactive ---"

tmpdir=$(setup_fake_project)
cat > "$tmpdir/aitasks/metadata/project_config.yaml" <<'YAML'
tmux:
  git_tui:
YAML

rbin=$(make_restricted_bin)  # no TUI tools

SCRIPT_DIR="$tmpdir/.aitask-scripts"
output=$(PATH="$rbin" setup_git_tui 2>&1 </dev/null)

assert_contains "Reports skipping" "skipping" "$output"

result=$(grep 'git_tui:' "$tmpdir/aitasks/metadata/project_config.yaml" | sed 's/.*git_tui:[[:space:]]*//')
assert_eq "Config still empty" "" "$result"
rm -rf "$tmpdir" "$rbin"

# Restore SCRIPT_DIR
source "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" --source-only
set +euo pipefail
SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"

# --- Summary ---
echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
