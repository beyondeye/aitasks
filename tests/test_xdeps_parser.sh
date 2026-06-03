#!/usr/bin/env bash
# test_xdeps_parser.sh - Verify xdeps / xdeprepo frontmatter parsing (t832_3).
#
# Covers:
#   - read_xdeps / read_xdeprepo helpers in lib/task_utils.sh
#   - aitask_ls.sh parses the new fields without crashing and emits them
#     in -v output (TUI round-trip is verified separately by the board test).
#
# Run: bash tests/test_xdeps_parser.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Shared assertion helpers (see tests/lib/asserts.sh).
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0


TMPROOT=$(mktemp -d)
trap 'rm -rf "$TMPROOT"' EXIT

# Fake project tree (no scaffold needed — we source the real libs).
mkdir -p "$TMPROOT/aitasks"

# Test fixture 1: task with xdeps + xdeprepo
cat > "$TMPROOT/aitasks/t42_sample.md" <<'EOF'
---
priority: medium
effort: medium
depends: []
xdeps: [1, 2_3, t99]
xdeprepo: aitasks_mobile
issue_type: feature
status: Ready
labels: []
---
body
EOF

# Test fixture 2: task without either field
cat > "$TMPROOT/aitasks/t43_plain.md" <<'EOF'
---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: []
---
body
EOF

# --- Reader helpers ---
# task_utils.sh resolves sibling libs via SCRIPT_DIR; pin it to the real tree.
SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"
# shellcheck disable=SC1091
source "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"
# shellcheck disable=SC1091
source "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"

xrepo=$(read_xdeprepo "$TMPROOT/aitasks/t42_sample.md")
assert_eq "read_xdeprepo returns the scalar" "aitasks_mobile" "$xrepo"

xdeps=$(read_xdeps "$TMPROOT/aitasks/t42_sample.md")
# normalize_task_ids prepends t to N_M but leaves bare numbers alone.
assert_eq "read_xdeps returns normalized csv" "1,t2_3,t99" "$xdeps"

xrepo_plain=$(read_xdeprepo "$TMPROOT/aitasks/t43_plain.md")
assert_eq "read_xdeprepo on plain task is empty" "" "$xrepo_plain"

xdeps_plain=$(read_xdeps "$TMPROOT/aitasks/t43_plain.md")
assert_eq "read_xdeps on plain task is empty" "" "$xdeps_plain"

# --- aitask_ls.sh round-trip: parser must not crash on the new fields ---

cd "$TMPROOT"
out=$("$PROJECT_DIR/.aitask-scripts/aitask_ls.sh" -v 2>&1 || true)
TOTAL=$((TOTAL + 1))
if grep -q 't42_sample' <<< "$out" && grep -q 't43_plain' <<< "$out"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: aitask_ls.sh -v should list both task fixtures"
    echo "  output: $out"
fi
cd - >/dev/null

# --- Summary ---

echo
echo "=========================================="
echo "Tests: $TOTAL  Passed: $PASS  Failed: $FAIL"
echo "=========================================="

[[ "$FAIL" -eq 0 ]]
