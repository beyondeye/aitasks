#!/usr/bin/env bash
# test_update_landing.sh - Tests for landing page "Latest Releases" auto-update (t243)
# Run: bash tests/test_update_landing.sh

set -e

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0
TMPDIR_TEST=""

# --- Test helpers ---

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc"
        echo "  expected: $(echo "$expected" | head -5)"
        echo "  actual:   $(echo "$actual" | head -5)"
    fi
}

assert_contains() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qF "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected to contain '$expected')"
        echo "  actual: $(echo "$actual" | head -5)"
    fi
}

assert_not_contains() {
    local desc="$1" unexpected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -qF "$unexpected"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (should NOT contain '$unexpected')"
        echo "  actual: $(echo "$actual" | head -5)"
    else
        PASS=$((PASS + 1))
    fi
}

assert_line_count() {
    local desc="$1" expected="$2" pattern="$3" content="$4"
    TOTAL=$((TOTAL + 1))
    local count
    count=$(echo "$content" | grep -c "$pattern" || true)
    if [[ "$count" -eq "$expected" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected $expected lines matching '$pattern', got $count)"
    fi
}

setup_tmpdir() {
    TMPDIR_TEST=$(mktemp -d)
}

cleanup_tmpdir() {
    if [[ -n "$TMPDIR_TEST" && -d "$TMPDIR_TEST" ]]; then
        rm -rf "$TMPDIR_TEST"
    fi
}

trap cleanup_tmpdir EXIT

# --- The awk command under test (extracted from new_release_post.sh) ---
run_awk_update() {
    local new_entry="$1"
    local index_file="$2"
    awk -v new_entry="$new_entry" '
    BEGIN { entry_count = 0; inserted = 0 }
    /^- \*\*\[v/ {
        if (!inserted) {
            print new_entry
            inserted = 1
            entry_count = 1
        }
        entry_count++
        if (entry_count <= 3) { print }
        next
    }
    { print }
    ' "$index_file"
}

# --- Sample _index.md content ---
SAMPLE_INDEX='---
title: "aitasks"
linkTitle: "aitasks"
---

{{< blocks/cover title="" image_anchor="top" height="med" color="primary" >}}
<div class="mx-auto">
  <p class="lead mt-2">AI-powered task management</p>
</div>
{{< /blocks/cover >}}

{{% blocks/section color="dark" %}}
## Latest Releases

<div class="row justify-content-center">
<div class="col-lg-8">

- **[v0.6.0: Feature A](blog/v060-feature-a/)** -- Feb 22, 2026
- **[v0.5.0: Feature B](blog/v050-feature-b/)** -- Feb 20, 2026
- **[v0.4.0: Feature C](blog/v040-feature-c/)** -- Feb 17, 2026

[All releases &rarr;](blog/)

</div>
</div>

{{% /blocks/section %}}

{{% blocks/section color="light" %}}
## Quick Install
```bash
curl -fsSL https://example.com/install.sh | bash
```
{{% /blocks/section %}}'

echo "=== Landing Page Update Tests (t243) ==="
echo ""

# ============================================================
# Test 1: Normal case - 3 existing entries, insert new, drop oldest
# ============================================================
echo "--- Test 1: Normal case (3 entries -> insert new, drop oldest) ---"

setup_tmpdir
echo "$SAMPLE_INDEX" > "$TMPDIR_TEST/index.md"

NEW_ENTRY='- **[v0.7.0: Feature D](blog/v070-feature-d/)** -- Feb 25, 2026'
result=$(run_awk_update "$NEW_ENTRY" "$TMPDIR_TEST/index.md")

assert_contains "new entry present" "v0.7.0: Feature D" "$result"
assert_contains "v0.6.0 kept" "v0.6.0: Feature A" "$result"
assert_contains "v0.5.0 kept" "v0.5.0: Feature B" "$result"
assert_not_contains "v0.4.0 removed" "v0.4.0: Feature C" "$result"
assert_line_count "exactly 3 release entries" 3 '^- \*\*\[v' "$result"

# Check that new entry comes before v0.6.0
new_line=$(echo "$result" | grep -n 'v0.7.0' | head -1 | cut -d: -f1)
old_line=$(echo "$result" | grep -n 'v0.6.0' | head -1 | cut -d: -f1)
TOTAL=$((TOTAL + 1))
if [[ "$new_line" -lt "$old_line" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: new entry should appear before v0.6.0 (line $new_line vs $old_line)"
fi

cleanup_tmpdir

# ============================================================
# Test 2: Fewer than 3 entries - insert new, keep all
# ============================================================
echo "--- Test 2: Fewer than 3 entries (2 existing -> 3 total) ---"

SAMPLE_TWO_ENTRIES='{{% blocks/section color="dark" %}}
## Latest Releases

<div class="row justify-content-center">
<div class="col-lg-8">

- **[v0.5.0: Feature B](blog/v050-feature-b/)** -- Feb 20, 2026
- **[v0.4.0: Feature C](blog/v040-feature-c/)** -- Feb 17, 2026

[All releases &rarr;](blog/)

</div>
</div>

{{% /blocks/section %}}'

setup_tmpdir
echo "$SAMPLE_TWO_ENTRIES" > "$TMPDIR_TEST/index.md"

result=$(run_awk_update "$NEW_ENTRY" "$TMPDIR_TEST/index.md")

assert_contains "new entry present" "v0.7.0: Feature D" "$result"
assert_contains "v0.5.0 kept" "v0.5.0: Feature B" "$result"
assert_contains "v0.4.0 kept" "v0.4.0: Feature C" "$result"
assert_line_count "exactly 3 release entries" 3 '^- \*\*\[v' "$result"

cleanup_tmpdir

# ============================================================
# Test 3: Only 1 existing entry -> 2 total
# ============================================================
echo "--- Test 3: Only 1 existing entry (1 -> 2 total) ---"

SAMPLE_ONE_ENTRY='{{% blocks/section color="dark" %}}
## Latest Releases

<div class="row justify-content-center">
<div class="col-lg-8">

- **[v0.4.0: Feature C](blog/v040-feature-c/)** -- Feb 17, 2026

[All releases &rarr;](blog/)

</div>
</div>

{{% /blocks/section %}}'

setup_tmpdir
echo "$SAMPLE_ONE_ENTRY" > "$TMPDIR_TEST/index.md"

result=$(run_awk_update "$NEW_ENTRY" "$TMPDIR_TEST/index.md")

assert_contains "new entry present" "v0.7.0: Feature D" "$result"
assert_contains "v0.4.0 kept" "v0.4.0: Feature C" "$result"
assert_line_count "exactly 2 release entries" 2 '^- \*\*\[v' "$result"

cleanup_tmpdir

# ============================================================
# Test 4: 4 existing entries -> insert new, keep only 3
# ============================================================
echo "--- Test 4: 4 existing entries (insert new, drop 2 oldest) ---"

SAMPLE_FOUR_ENTRIES='{{% blocks/section color="dark" %}}
## Latest Releases

<div class="row justify-content-center">
<div class="col-lg-8">

- **[v0.6.0: Feature A](blog/v060-feature-a/)** -- Feb 22, 2026
- **[v0.5.0: Feature B](blog/v050-feature-b/)** -- Feb 20, 2026
- **[v0.4.0: Feature C](blog/v040-feature-c/)** -- Feb 17, 2026
- **[v0.3.0: Feature D](blog/v030-feature-d/)** -- Feb 14, 2026

[All releases &rarr;](blog/)

</div>
</div>

{{% /blocks/section %}}'

setup_tmpdir
echo "$SAMPLE_FOUR_ENTRIES" > "$TMPDIR_TEST/index.md"

result=$(run_awk_update "$NEW_ENTRY" "$TMPDIR_TEST/index.md")

assert_contains "new entry present" "v0.7.0: Feature D" "$result"
assert_contains "v0.6.0 kept" "v0.6.0: Feature A" "$result"
assert_contains "v0.5.0 kept" "v0.5.0: Feature B" "$result"
assert_not_contains "v0.4.0 removed" "v0.4.0: Feature C" "$result"
assert_not_contains "v0.3.0 removed" "v0.3.0: Feature D" "$result"
assert_line_count "exactly 3 release entries" 3 '^- \*\*\[v' "$result"

cleanup_tmpdir

# ============================================================
# Test 5: Format preservation - Hugo shortcodes and HTML intact
# ============================================================
echo "--- Test 5: Format preservation (Hugo shortcodes + HTML intact) ---"

setup_tmpdir
echo "$SAMPLE_INDEX" > "$TMPDIR_TEST/index.md"

result=$(run_awk_update "$NEW_ENTRY" "$TMPDIR_TEST/index.md")

assert_contains "Hugo cover block preserved" 'blocks/cover title=""' "$result"
assert_contains "Hugo section dark preserved" 'blocks/section color="dark"' "$result"
assert_contains "Hugo section light preserved" 'blocks/section color="light"' "$result"
assert_contains "All releases link preserved" '[All releases &rarr;](blog/)' "$result"
assert_contains "Quick Install section preserved" '## Quick Install' "$result"
assert_contains "div wrapper preserved" '<div class="col-lg-8">' "$result"

cleanup_tmpdir

# ============================================================
# Test 6: Duplicate detection via grep (simulated)
# ============================================================
echo "--- Test 6: Duplicate detection (slug already in file) ---"

setup_tmpdir
# Create file that already has v0.7.0
SAMPLE_WITH_070='{{% blocks/section color="dark" %}}
## Latest Releases

<div class="row justify-content-center">
<div class="col-lg-8">

- **[v0.7.0: Feature D](blog/v070-feature-d/)** -- Feb 25, 2026
- **[v0.6.0: Feature A](blog/v060-feature-a/)** -- Feb 22, 2026
- **[v0.5.0: Feature B](blog/v050-feature-b/)** -- Feb 20, 2026

[All releases &rarr;](blog/)

</div>
</div>

{{% /blocks/section %}}'

echo "$SAMPLE_WITH_070" > "$TMPDIR_TEST/index.md"

# Simulate the grep check that update_landing_page() does
slug="v070-feature-d"
TOTAL=$((TOTAL + 1))
if grep -qF "blog/${slug}/" "$TMPDIR_TEST/index.md"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: duplicate detection should find existing slug"
fi

cleanup_tmpdir

# ============================================================
# Test 7: format_display_date function (Linux only)
# ============================================================
echo "--- Test 7: format_display_date (Linux) ---"

if [[ "$(uname -s)" != "Darwin" ]]; then
    result=$(date -d "2026-02-25" "+%b %-d, %Y" 2>/dev/null || echo "UNSUPPORTED")
    assert_eq "Feb 25, 2026 formatting" "Feb 25, 2026" "$result"

    result=$(date -d "2026-03-05" "+%b %-d, %Y" 2>/dev/null || echo "UNSUPPORTED")
    assert_eq "Mar 5, 2026 no zero-pad" "Mar 5, 2026" "$result"

    result=$(date -d "2026-12-31" "+%b %-d, %Y" 2>/dev/null || echo "UNSUPPORTED")
    assert_eq "Dec 31, 2026 formatting" "Dec 31, 2026" "$result"
else
    echo "  (skipping Linux date tests on macOS)"
fi

# ============================================================
# Summary
# ============================================================
echo ""
echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="

if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
