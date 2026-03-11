#!/usr/bin/env bash
# test_merge_issues.sh - Tests for --merge-issues functionality in aitask_issue_import.sh
# Run: bash tests/test_merge_issues.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

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
    if echo "$actual" | grep -qF -- "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected')"
    fi
}

assert_not_contains() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qF -- "$expected"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (output should NOT contain '$expected')"
    else
        PASS=$((PASS + 1))
    fi
}

# --- Setup: source helper functions from the script ---

setup_functions() {
    local tmpdir
    tmpdir="$(mktemp -d)"

    cat > "$tmpdir/source_funcs.sh" << FUNCEOF
SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"
source "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"
source "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"

# Source helper functions from import script without running main
# We extract the functions we need
count_diff_lines() {
    local body="\$1"
    local count
    count=\$(echo "\$body" | grep -cE '^\+[^+]|^-[^-]' || true)
    echo "\${count:-0}"
}

inject_merge_frontmatter() {
    local filepath="\$1"
    local related_issues_yaml="\$2"
    local contributors_yaml="\$3"

    local anchor_pattern=""
    if grep -q '^contributor_email:' "\$filepath"; then
        anchor_pattern='^contributor_email:'
    elif grep -q '^contributor:' "\$filepath"; then
        anchor_pattern='^contributor:'
    elif grep -q '^issue:' "\$filepath"; then
        anchor_pattern='^issue:'
    else
        anchor_pattern='^status:'
    fi

    local insert_text="related_issues: \$related_issues_yaml"
    if [[ -n "\$contributors_yaml" ]]; then
        insert_text="\${insert_text}"\$'\n'"\$contributors_yaml"
    fi

    local tmpfile
    tmpfile=\$(mktemp "\${TMPDIR:-/tmp}/ait_merge_XXXXXX.md")
    local injected=false
    while IFS= read -r line; do
        printf '%s\n' "\$line" >> "\$tmpfile"
        if [[ "\$injected" == false ]] && echo "\$line" | grep -qE "\$anchor_pattern"; then
            printf '%s\n' "\$insert_text" >> "\$tmpfile"
            injected=true
        fi
    done < "\$filepath"
    mv "\$tmpfile" "\$filepath"
}
FUNCEOF
    echo "$tmpdir"
}

# Disable strict mode for test error handling
set +e

echo "=== Merge Issues Tests ==="
echo ""

# ============================================================
# Unit Tests: count_diff_lines
# ============================================================

echo "--- Test 1: count_diff_lines with diff block ---"
FUNC_DIR="$(setup_functions)"
source "$FUNC_DIR/source_funcs.sh"

body_1='Some text

```diff
--- a/file.sh
+++ b/file.sh
+added line 1
+added line 2
-removed line 1
 context line
+added line 3
```'

result_1=$(count_diff_lines "$body_1")
assert_eq "count diff lines with additions and removals" "4" "$result_1"
rm -rf "$FUNC_DIR"

echo "--- Test 2: count_diff_lines with no diffs ---"
FUNC_DIR="$(setup_functions)"
source "$FUNC_DIR/source_funcs.sh"

body_2="Just a regular issue body.

No diffs here."

result_2=$(count_diff_lines "$body_2")
assert_eq "count diff lines with no diffs" "0" "$result_2"
rm -rf "$FUNC_DIR"

echo "--- Test 3: count_diff_lines excludes --- and +++ headers ---"
FUNC_DIR="$(setup_functions)"
source "$FUNC_DIR/source_funcs.sh"

body_3='--- a/old_file.sh
+++ b/new_file.sh
+real addition
-real removal
--- another/file.txt
+++ another/file.txt'

result_3=$(count_diff_lines "$body_3")
assert_eq "count diff lines excluding headers" "2" "$result_3"
rm -rf "$FUNC_DIR"

# ============================================================
# Unit Tests: inject_merge_frontmatter
# ============================================================

echo "--- Test 4: inject_merge_frontmatter after contributor_email ---"
FUNC_DIR="$(setup_functions)"
source "$FUNC_DIR/source_funcs.sh"

tmpfile_4=$(mktemp "${TMPDIR:-/tmp}/ait_test_XXXXXX.md")
cat > "$tmpfile_4" << 'EOF'
---
priority: medium
effort: medium
issue_type: feature
status: Ready
issue: https://github.com/owner/repo/issues/42
contributor: alice
contributor_email: alice@example.com
created_at: 2026-03-10 10:00
---

Description here.
EOF

inject_merge_frontmatter "$tmpfile_4" '["https://github.com/owner/repo/issues/42", "https://github.com/owner/repo/issues/38"]' ""
content_4=$(cat "$tmpfile_4")
assert_contains "related_issues after contributor_email" "related_issues:" "$content_4"
# Verify related_issues is after contributor_email and before created_at
line_ce=$(grep -n '^contributor_email:' "$tmpfile_4" | head -1 | cut -d: -f1)
line_ri=$(grep -n '^related_issues:' "$tmpfile_4" | head -1 | cut -d: -f1)
line_ca=$(grep -n '^created_at:' "$tmpfile_4" | head -1 | cut -d: -f1)
if [[ "$line_ri" -gt "$line_ce" && "$line_ri" -lt "$line_ca" ]]; then
    TOTAL=$((TOTAL + 1)); PASS=$((PASS + 1))
else
    TOTAL=$((TOTAL + 1)); FAIL=$((FAIL + 1))
    echo "FAIL: related_issues not between contributor_email and created_at (ce=$line_ce ri=$line_ri ca=$line_ca)"
fi
rm -f "$tmpfile_4"
rm -rf "$FUNC_DIR"

echo "--- Test 5: inject_merge_frontmatter after issue (no contributor) ---"
FUNC_DIR="$(setup_functions)"
source "$FUNC_DIR/source_funcs.sh"

tmpfile_5=$(mktemp "${TMPDIR:-/tmp}/ait_test_XXXXXX.md")
cat > "$tmpfile_5" << 'EOF'
---
priority: medium
effort: medium
issue_type: feature
status: Ready
issue: https://github.com/owner/repo/issues/42
created_at: 2026-03-10 10:00
---

Description here.
EOF

inject_merge_frontmatter "$tmpfile_5" '["url1", "url2"]' ""
content_5=$(cat "$tmpfile_5")
assert_contains "related_issues after issue line" "related_issues:" "$content_5"
line_issue=$(grep -n '^issue:' "$tmpfile_5" | head -1 | cut -d: -f1)
line_ri5=$(grep -n '^related_issues:' "$tmpfile_5" | head -1 | cut -d: -f1)
assert_eq "related_issues right after issue" "$((line_issue + 1))" "$line_ri5"
rm -f "$tmpfile_5"
rm -rf "$FUNC_DIR"

echo "--- Test 6: inject_merge_frontmatter YAML list format ---"
FUNC_DIR="$(setup_functions)"
source "$FUNC_DIR/source_funcs.sh"

tmpfile_6=$(mktemp "${TMPDIR:-/tmp}/ait_test_XXXXXX.md")
cat > "$tmpfile_6" << 'EOF'
---
status: Ready
issue: https://example.com/1
---
EOF

inject_merge_frontmatter "$tmpfile_6" '["https://example.com/1", "https://example.com/2"]' ""
content_6=$(cat "$tmpfile_6")
assert_contains "related_issues list format" '["https://example.com/1", "https://example.com/2"]' "$content_6"
rm -f "$tmpfile_6"
rm -rf "$FUNC_DIR"

echo "--- Test 7: inject_merge_frontmatter with contributors YAML block ---"
FUNC_DIR="$(setup_functions)"
source "$FUNC_DIR/source_funcs.sh"

tmpfile_7=$(mktemp "${TMPDIR:-/tmp}/ait_test_XXXXXX.md")
cat > "$tmpfile_7" << 'EOF'
---
status: Ready
issue: https://example.com/1
contributor: alice
contributor_email: alice@example.com
---
EOF

contributors_yaml_7="contributors:"$'\n'"  - name: bob"$'\n'"    email: bob@example.com"$'\n'"    issue: https://example.com/2"
inject_merge_frontmatter "$tmpfile_7" '["url1", "url2"]' "$contributors_yaml_7"
content_7=$(cat "$tmpfile_7")
assert_contains "contributors block present" "contributors:" "$content_7"
assert_contains "contributor name" "  - name: bob" "$content_7"
assert_contains "contributor email" "    email: bob@example.com" "$content_7"
assert_contains "contributor issue" "    issue: https://example.com/2" "$content_7"
rm -f "$tmpfile_7"
rm -rf "$FUNC_DIR"

# ============================================================
# Argument Validation Tests
# ============================================================

echo "--- Test 8: --merge-issues with 1 issue errors ---"
result_8=$(./.aitask-scripts/aitask_issue_import.sh --batch --merge-issues 42 --source github 2>&1) || true
assert_contains "merge-issues requires 2+" "requires at least 2" "$result_8"

echo "--- Test 9: --merge-issues + --issue errors ---"
result_9=$(./.aitask-scripts/aitask_issue_import.sh --batch --merge-issues 42,43 --issue 42 --source github 2>&1) || true
assert_contains "merge-issues conflicts with --issue" "cannot be combined with --issue" "$result_9"

# ============================================================
# Script Validation Tests
# ============================================================

echo "--- Test 10: syntax check ---"
result_10=$(bash -n .aitask-scripts/aitask_issue_import.sh 2>&1)
TOTAL=$((TOTAL + 1))
if [[ $? -eq 0 || -z "$result_10" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: syntax check failed: $result_10"
fi

echo "--- Test 11: help output includes merge-issues ---"
result_11=$(./.aitask-scripts/aitask_issue_import.sh --help 2>&1)
assert_contains "help shows --merge-issues" "--merge-issues" "$result_11"
assert_contains "help shows merge example" "merge-issues 38,39,42" "$result_11"

# ============================================================
# Integration Test: Simulate merged task file and verify full result
# ============================================================

echo "--- Test 12: Full merge simulation - primary contributor selection ---"
FUNC_DIR="$(setup_functions)"
source "$FUNC_DIR/source_funcs.sh"

# Simulate what merge_issues produces: a task file created by aitask_create.sh
# with primary contributor, then inject_merge_frontmatter adds merge-specific fields
tmpfile_12=$(mktemp "${TMPDIR:-/tmp}/ait_test_XXXXXX.md")
cat > "$tmpfile_12" << 'EOF'
---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [enhancement]
issue: https://github.com/owner/repo/issues/42
contributor: alice
contributor_email: alice@example.com
created_at: 2026-03-10 10:00
updated_at: 2026-03-10 10:00
---

## Merged Contribution Issues

Source issues: #42, #38

---

### Issue #42: Add dark mode support

Some diff content here.

---

### Issue #38: Theme color updates

Another diff here.
EOF

# Simulate: alice is primary (issue 42, more diff lines), bob is secondary (issue 38)
related_yaml='["https://github.com/owner/repo/issues/42", "https://github.com/owner/repo/issues/38"]'
contrib_yaml="contributors:"$'\n'"  - name: bob"$'\n'"    email: bob@example.com"$'\n'"    issue: https://github.com/owner/repo/issues/38"

inject_merge_frontmatter "$tmpfile_12" "$related_yaml" "$contrib_yaml"
content_12=$(cat "$tmpfile_12")

# Primary should be alice (set by aitask_create.sh, reflected in contributor/contributor_email fields)
assert_contains "primary contributor is alice" "contributor: alice" "$content_12"
assert_contains "primary email" "contributor_email: alice@example.com" "$content_12"
assert_contains "primary issue URL" "issue: https://github.com/owner/repo/issues/42" "$content_12"

# related_issues should have both URLs
assert_contains "related_issues present" "related_issues:" "$content_12"
assert_contains "related_issues has issue 42" "issues/42" "$content_12"
assert_contains "related_issues has issue 38" "issues/38" "$content_12"

# Secondary contributor (bob) in contributors block
assert_contains "contributors block has bob" "- name: bob" "$content_12"
assert_contains "contributors bob email" "email: bob@example.com" "$content_12"
assert_contains "contributors bob issue" "issue: https://github.com/owner/repo/issues/38" "$content_12"

# Description has both issues
assert_contains "description has issue 42 section" "Issue #42:" "$content_12"
assert_contains "description has issue 38 section" "Issue #38:" "$content_12"
assert_contains "description has merged header" "Merged Contribution Issues" "$content_12"

# Verify ordering: related_issues and contributors are after contributor_email, before created_at
line_ce12=$(grep -n '^contributor_email:' "$tmpfile_12" | head -1 | cut -d: -f1)
line_ri12=$(grep -n '^related_issues:' "$tmpfile_12" | head -1 | cut -d: -f1)
line_ct12=$(grep -n '^contributors:' "$tmpfile_12" | head -1 | cut -d: -f1)
line_ca12=$(grep -n '^created_at:' "$tmpfile_12" | head -1 | cut -d: -f1)
if [[ "$line_ri12" -gt "$line_ce12" && "$line_ct12" -gt "$line_ri12" && "$line_ca12" -gt "$line_ct12" ]]; then
    TOTAL=$((TOTAL + 1)); PASS=$((PASS + 1))
else
    TOTAL=$((TOTAL + 1)); FAIL=$((FAIL + 1))
    echo "FAIL: field ordering wrong (ce=$line_ce12 ri=$line_ri12 ct=$line_ct12 ca=$line_ca12)"
fi

rm -f "$tmpfile_12"
rm -rf "$FUNC_DIR"

echo "--- Test 13: Primary contributor selection by diff count ---"
FUNC_DIR="$(setup_functions)"
source "$FUNC_DIR/source_funcs.sh"

# Issue with more diff lines should be primary
body_13a='+line1
+line2
+line3
+line4
-removed1
-removed2'

body_13b='+singleline'

count_a=$(count_diff_lines "$body_13a")
count_b=$(count_diff_lines "$body_13b")

assert_eq "issue A has 6 diff lines" "6" "$count_a"
assert_eq "issue B has 1 diff line" "1" "$count_b"

# Verify A would be selected as primary (larger count)
TOTAL=$((TOTAL + 1))
if [[ "$count_a" -gt "$count_b" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: primary selection - A ($count_a) should be > B ($count_b)"
fi
rm -rf "$FUNC_DIR"

# ============================================================
# Summary
# ============================================================

echo ""
echo "=== Results ==="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
echo "TOTAL: $TOTAL"

if [[ "$FAIL" -gt 0 ]]; then
    echo "STATUS: FAILED"
    exit 1
else
    echo "STATUS: PASSED"
    exit 0
fi
