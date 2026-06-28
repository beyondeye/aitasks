#!/usr/bin/env bash
# test_attach_scaffold.sh - Tests for the task-attachments scaffold (t1030_1):
# the pure helpers in lib/attachment_utils.sh, the read_yaml_mappings reader in
# lib/yaml_utils.sh, and the read-only `ait attach ls` surface.
#
# Run: bash tests/test_attach_scaffold.sh

set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"
LIB_DIR="$PROJECT_DIR/.aitask-scripts/lib"

# die() lives in terminal_compat.sh; attachment_utils.sh calls it. Source the
# helpers directly (these libs are not in ./ait's startup chain).
# shellcheck source=../.aitask-scripts/lib/terminal_compat.sh
source "$LIB_DIR/terminal_compat.sh"
# shellcheck source=../.aitask-scripts/lib/yaml_utils.sh
source "$LIB_DIR/yaml_utils.sh"
# shellcheck source=../.aitask-scripts/lib/attachment_utils.sh
source "$LIB_DIR/attachment_utils.sh"

PASS=0
FAIL=0
TOTAL=0

TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_attach_XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

ATTACH="$PROJECT_DIR/.aitask-scripts/aitask_attach.sh"
GOOD_HASH="sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"

# --- Test 1: attachment_sha256 known vector (empty input) ------------------
: > "$TMP/empty"
assert_eq "sha256 of empty file matches the known vector" \
    "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" \
    "$(attachment_sha256 "$TMP/empty")"

printf 'hello\n' > "$TMP/hello"
hello_hash="$(attachment_sha256 "$TMP/hello")"
assert_eq "sha256 output is a well-formed sha256:<64hex>" \
    "0" "$( [[ "$hello_hash" =~ ^sha256:[0-9a-f]{64}$ ]]; echo $? )"

# --- Test 2: attachment_validate_hash accept / reject ----------------------
assert_exit_zero    "validate_hash accepts a canonical hash" attachment_validate_hash "$GOOD_HASH"
assert_exit_nonzero "validate_hash rejects missing sha256: prefix" \
    attachment_validate_hash "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
assert_exit_nonzero "validate_hash rejects a too-short hash" attachment_validate_hash "sha256:abcd"
assert_exit_nonzero "validate_hash rejects uppercase hex" \
    attachment_validate_hash "sha256:9F86D081884C7D659A2FEAA0C55AD015A3BF4F1B2B0B822CD15D6C15B0F00A08"
assert_exit_nonzero "validate_hash rejects empty input" attachment_validate_hash ""

# --- Test 3: attachment_shard_path -----------------------------------------
assert_eq "shard_path splits into <2>/<62>" \
    "9f/86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08" \
    "$(attachment_shard_path "$GOOD_HASH")"
# Bad hash must die (run in a subshell so its exit does not kill the test).
( attachment_shard_path "not-a-hash" ) >/dev/null 2>&1; shard_rc=$?
assert_exit_nonzero_rc "shard_path dies on an invalid hash" "$shard_rc"

# --- Test 4: attachment_cache_path honors XDG_CACHE_HOME --------------------
assert_eq "cache_path uses XDG_CACHE_HOME override" \
    "/xdg/cache/ait/attachments/$GOOD_HASH" \
    "$(XDG_CACHE_HOME=/xdg/cache attachment_cache_path "$GOOD_HASH")"
assert_eq "cache_path falls back to \$HOME/.cache" \
    "/home/fixture/.cache/ait/attachments/$GOOD_HASH" \
    "$(HOME=/home/fixture XDG_CACHE_HOME="" attachment_cache_path "$GOOD_HASH")"

# --- Test 5: read_yaml_mappings on 0 / 1 / 2 attachments -------------------

# 0 attachments: no field at all.
cat > "$TMP/none.md" <<EOF
---
priority: medium
status: Ready
---
body
EOF
assert_eq "read_yaml_mappings: missing field emits nothing" \
    "" "$(read_yaml_mappings "$TMP/none.md" attachments)"

# 0 attachments: empty inline list.
cat > "$TMP/empty_list.md" <<EOF
---
attachments: []
status: Ready
---
EOF
assert_eq "read_yaml_mappings: empty inline list emits nothing" \
    "" "$(read_yaml_mappings "$TMP/empty_list.md" attachments)"

# 1 attachment: the EXACT design §3 block (inline comment + full-line comment +
# url: null). Proves the contract against the canonical shape.
cat > "$TMP/one.md" <<EOF
---
priority: medium
attachments:
  - hash: $GOOD_HASH
    name: login-screen-bug.png
    mime: image/png
    size: 184320
    added_at: 2026-06-18T12:34:56Z
    backend: local         # one of: local | s3 | gcs | gh-release | gdrive
    # backend-specific resolution hints (optional, advisory only):
    url: null
status: Ready
---
EOF
one_out="$(read_yaml_mappings "$TMP/one.md" attachments)"
assert_eq "read_yaml_mappings: one attachment yields exactly one record" \
    "1" "$(printf '%s\n' "$one_out" | grep -c '^hash=')"
assert_contains "read_yaml_mappings: hash field" "hash=$GOOD_HASH" "$one_out"
assert_contains "read_yaml_mappings: name field" "name=login-screen-bug.png" "$one_out"
# Inline-comment strip (concern #2): backend is 'local', NOT the commented string.
assert_contains "read_yaml_mappings: inline comment stripped from backend" \
    "backend=local" "$one_out"
assert_not_contains "read_yaml_mappings: comment text not leaked into value" \
    "one of" "$one_out"
# Full-line comment did not break record accumulation; url: null preserved.
assert_contains "read_yaml_mappings: url: null preserved verbatim" "url=null" "$one_out"
# Schema order: hash precedes url in the emitted record.
assert_eq "read_yaml_mappings: fields emitted in schema order (hash before url)" \
    "0" "$(printf '%s\n' "$one_out" | grep -nE '^(hash|url)=' | head -1 | grep -qF 'hash=' && echo 0 || echo 1)"

# 2 attachments, second with adversarial values (concern #1):
#   - a quoted name containing ';', '=' and spaces (would break a k=v;k=v format)
#   - an unquoted name with a literal '#' (must NOT be treated as a comment)
cat > "$TMP/two.md" <<EOF
---
attachments:
  - hash: $GOOD_HASH
    name: "report; v=2.png"
    backend: s3
  - hash: $GOOD_HASH
    name: bug#3.png
    backend: local
status: Ready
---
EOF
two_out="$(read_yaml_mappings "$TMP/two.md" attachments)"
assert_eq "read_yaml_mappings: two attachments yield two records" \
    "2" "$(printf '%s\n' "$two_out" | grep -c '^hash=')"
assert_eq "read_yaml_mappings: two records separated by a blank line" \
    "1" "$(printf '%s\n' "$two_out" | grep -c '^$')"
# Concern #1: ';'/'='/space-bearing value round-trips intact (split on first '=').
assert_contains "read_yaml_mappings: quoted value with ;/=/space is intact" \
    "name=report; v=2.png" "$two_out"
# Concern #2 inverse: literal '#' (not whitespace-preceded) survives.
assert_contains "read_yaml_mappings: literal '#' in name preserved" \
    "name=bug#3.png" "$two_out"

# --- Test 6: `ait attach ls` end-to-end ------------------------------------
mkdir -p "$TMP/aitasks" "$TMP/aitasks/archived"
cp "$TMP/one.md" "$TMP/aitasks/t9001_fixture.md"

run_attach() { TASK_DIR="$TMP/aitasks" ARCHIVED_DIR="$TMP/aitasks/archived" "$ATTACH" "$@"; }

ls_out="$(run_attach ls 9001 2>&1)"; ls_rc=$?
assert_exit_zero_rc "attach ls exits 0 on a valid fixture" "$ls_rc"
assert_contains "attach ls shows the attachment name" "login-screen-bug.png" "$ls_out"
assert_contains "attach ls shows the short hash (first 12 hex)" "9f86d081884c" "$ls_out"
assert_contains "attach ls shows the backend" "local" "$ls_out"
# Accepts the `t`-prefixed id too.
t_out="$(run_attach ls t9001 2>&1)"
assert_contains "attach ls accepts a t-prefixed id" "login-screen-bug.png" "$t_out"

# Empty case.
cp "$TMP/none.md" "$TMP/aitasks/t9002_empty.md"
empty_out="$(run_attach ls 9002 2>&1)"
assert_eq "attach ls prints 'No attachments.' when there are none" \
    "No attachments." "$empty_out"

# Malformed hash (concern #3): loud failure, no row printed.
cat > "$TMP/aitasks/t9003_bad.md" <<EOF
---
attachments:
  - hash: sha256:nope
    name: broken.png
    backend: local
status: Ready
---
EOF
bad_out="$(run_attach ls 9003 2>&1)"; bad_rc=$?
assert_exit_nonzero_rc "attach ls fails loudly on a malformed hash" "$bad_rc"
assert_contains "attach ls names the invalid-hash error" "invalid or missing hash" "$bad_out"

# --- Test 7: stub verbs are not-yet-implemented ----------------------------
for verb in add get rm move gc; do
    stub_out="$(run_attach "$verb" 9001 2>&1)"; stub_rc=$?
    assert_exit_nonzero_rc "attach $verb stub exits non-zero" "$stub_rc"
    assert_contains "attach $verb stub explains it is not yet available" \
        "not yet available" "$stub_out"
done

# help lists the full surface.
help_out="$(run_attach help 2>&1)"
assert_contains "attach help lists ls" "ls" "$help_out"
assert_contains "attach help marks unimplemented verbs" "not yet implemented" "$help_out"

# --- Test 8: syntax checks for the touched/new files -----------------------
for f in lib/attachment_utils.sh lib/yaml_utils.sh aitask_attach.sh; do
    TOTAL=$((TOTAL + 1))
    if bash -n "$PROJECT_DIR/.aitask-scripts/$f"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: syntax check $f"
    fi
done

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
