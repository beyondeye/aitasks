#!/usr/bin/env bash
# test_release_post_date.sh - a release blog post is never dated after its
# release (website/new_release_post.sh).
#
# Hugo reads a bare `date: YYYY-MM-DD` as UTC midnight and leaves future-dated
# content out of the build. new_release_post.sh used to write the tag's LOCAL
# calendar day, so a release tagged between local midnight and UTC midnight
# (east of UTC) produced a post Hugo considered future. The build dropped it,
# and check_links.py failed the landing page's link to it (seen on v0.38.0,
# tagged 2026-10-16 01:49 +03:00 = 2026-10-15 22:49 UTC). The script now
# writes an exact RFC 3339 timestamp with its offset.
#
# Each cell runs the real script in a fixture repo and checks the property that
# matters: the post's instant is not after the release instant. Cell 1's tag
# sits inside that window, where the old bare day was three hours in the future.
#
# Run: bash tests/test_release_post_date.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

. "$PROJECT_DIR/tests/lib/git_config_isolation.sh"
sync_isolate_git_config
assert_git_config_isolated

ROOT="$(mktemp -d "${TMPDIR:-/tmp}/ait_release_post_XXXXXX")"
trap 'rm -rf "$ROOT"' EXIT

REPO="$ROOT/repo"
mkdir -p "$REPO/website/content/blog"
cp "$PROJECT_DIR/website/new_release_post.sh" "$REPO/website/"
cat > "$REPO/website/content/_index.md" <<'EOF'
## Latest Releases

- **[v9.8.0: Older](blog/v980/)** -- Oct 1, 2026
EOF
cat > "$REPO/CHANGELOG.md" <<'EOF'
# Changelog

## v9.9.0

### Features

- **Window probe**: a release cut just after local midnight.

## v9.8.0

- older
EOF
git -C "$REPO" init --quiet
git -C "$REPO" config user.email t@t
git -C "$REPO" config user.name t
git -C "$REPO" add -A
git -C "$REPO" commit --quiet -m init
# Tagged inside the window: local 2026-10-16 01:49 at +03:00 is 22:49 UTC on
# the 15th, so the old bare `2026-10-16` read as a time three hours later.
GIT_COMMITTER_DATE="2026-10-16T01:49:12+03:00" git -C "$REPO" tag -a v9.9.0 -m "v9.9.0"

# post_date <file> — the front-matter date value.
post_date() { sed -n 's/^date: //p' "$1" | head -1; }

# not_after <date> <iso-instant> — prints "yes" when <date>, read the way Hugo
# reads front matter (a bare day is UTC midnight), is not after <iso-instant>.
not_after() {
    python3 - "$1" "$2" <<'PY'
import sys
from datetime import datetime, timezone
def read(value):
    if len(value) == 10:  # bare YYYY-MM-DD: Hugo reads it as UTC midnight
        return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
print("yes" if read(sys.argv[1]) <= read(sys.argv[2]) else "no")
PY
}

echo "=== a release post is never dated after its release ==="

echo "--- Test 1: --auto, tagged between local and UTC midnight ---"
out="$(cd "$REPO" && bash website/new_release_post.sh --auto 9.9.0 2>&1)"; rc=$?
assert_eq "1: the script succeeds" "0" "$rc"
post="$(ls "$REPO"/website/content/blog/v990*.md 2>/dev/null | head -1)"
assert_eq "1: the post was written" "yes" "$([[ -n "$post" ]] && echo yes || echo no)"
date_value="$(post_date "$post")"
assert_eq "1: the date is the tag's exact instant with its offset" \
    "2026-10-16T01:49:12+03:00" "$date_value"
assert_eq "1: the post is not dated after the release (Hugo would drop it)" "yes" \
    "$(not_after "$date_value" "2026-10-15T22:49:12+00:00")"
assert_eq "1: control: the old bare local day WAS after the release" "no" \
    "$(not_after "2026-10-16" "2026-10-15T22:49:12+00:00")"
assert_contains "1: the landing page shows the local release day" \
    "(blog/$(basename "$post" .md)/)** -- Oct 16, 2026" "$(cat "$REPO/website/content/_index.md")"

echo "--- Test 2: no tag yet: the fallback is 'now' with an offset ---"
cat >> "$REPO/CHANGELOG.md" <<'EOF'

## v9.10.0

- untagged
EOF
before="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
out="$(cd "$REPO" && bash website/new_release_post.sh 9.10.0 2>&1)"; rc=$?
after="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
assert_eq "2: the scaffold succeeds" "0" "$rc"
post2="$(ls "$REPO"/website/content/blog/v9100*.md 2>/dev/null | head -1)"
date2="$(post_date "$post2")"
assert_eq "2: the date is an RFC 3339 timestamp with an offset" "yes" \
    "$([[ "$date2" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}[+-][0-9]{2}:[0-9]{2}$ ]] && echo yes || echo "no: $date2")"
assert_eq "2: and not after the moment it was written" "yes" "$(not_after "$date2" "$after")"
assert_eq "2: nor before the run started" "no" "$(not_after "$date2" "$(python3 -c '
import sys
from datetime import datetime, timedelta
print((datetime.fromisoformat(sys.argv[1].replace("Z", "+00:00")) - timedelta(seconds=1)).isoformat())
' "$before")")"

echo ""
echo "=== Results ==="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
echo "TOTAL: $TOTAL"

[[ "$FAIL" -eq 0 ]] || { echo "SOME TESTS FAILED"; exit 1; }
echo "ALL TESTS PASSED"
