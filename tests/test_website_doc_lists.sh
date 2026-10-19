#!/usr/bin/env bash
# test_website_doc_lists.sh - Drift guard for hand-maintained documentation
# lists (t1162_5).
#
# Three user-facing lists on the website duplicate information whose source of
# truth lives in code or on disk. The first two had silently drifted before this
# guard existed (4 of 10 code-agent operations and one skill page were
# missing); the third shipped with no documentation at all (t1231_3):
#
#   1. website/content/docs/commands/codeagent.md `### Operations` table
#      vs SUPPORTED_OPERATIONS in .aitask-scripts/aitask_codeagent.sh
#   2. website/content/docs/skills/_index.md links
#      vs the aitask-* pages present in website/content/docs/skills/
#   3. website/content/docs/concepts/artifacts.md backend table
#      vs the dispatch arms of .aitask-scripts/lib/artifact_backend.sh
#
# The lists are prose tables that cannot be generated at build time, so the
# guard asserts containment instead: every canonical entry must be documented.
# Extra documentation rows are allowed (e.g. Verified Scores, which is a
# concept page rather than a skill).
#
# Run: bash tests/test_website_doc_lists.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# Shared assertion helpers (see tests/lib/asserts.sh)
# shellcheck source-path=SCRIPTDIR
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

CODEAGENT_SH="$PROJECT_DIR/.aitask-scripts/aitask_codeagent.sh"
CODEAGENT_DOC="$PROJECT_DIR/website/content/docs/commands/codeagent.md"
SKILLS_DIR="$PROJECT_DIR/website/content/docs/skills"
SKILLS_INDEX="$SKILLS_DIR/_index.md"
ARTIFACT_BACKEND_SH="$PROJECT_DIR/.aitask-scripts/lib/artifact_backend.sh"
ARTIFACT_BACKENDS_DIR="$PROJECT_DIR/.aitask-scripts/lib/artifact_backends"
ARTIFACTS_DOC="$PROJECT_DIR/website/content/docs/concepts/artifacts.md"

echo "=== Doc-list drift guard ==="

# --- Preconditions ---------------------------------------------------------
# Without these the containment loops below would vacuously pass.

assert_file_exists "aitask_codeagent.sh present" "$CODEAGENT_SH"
assert_file_exists "codeagent.md present" "$CODEAGENT_DOC"
assert_file_exists "skills/_index.md present" "$SKILLS_INDEX"
assert_file_exists "artifact_backend.sh present" "$ARTIFACT_BACKEND_SH"
assert_file_exists "concepts/artifacts.md present" "$ARTIFACTS_DOC"

# --- Test 1: every supported code-agent operation is documented ------------
#
# Source of truth: SUPPORTED_OPERATIONS=(pick explain ... work-report) on a
# single line in aitask_codeagent.sh. Extract the parenthesised body.

operations="$(sed -n 's/^SUPPORTED_OPERATIONS=(\(.*\))[[:space:]]*$/\1/p' "$CODEAGENT_SH")"

# Tripwire: if the array is ever reformatted (multi-line, quoted), the sed
# above silently yields nothing and every containment check below would pass
# without testing anything.
assert_contains_re "SUPPORTED_OPERATIONS parsed from aitask_codeagent.sh" \
    "[a-z]" "$operations"

doc_body="$(cat "$CODEAGENT_DOC")"

for op in $operations; do
    # Match the operation as a backticked id in the table's first cell.
    assert_contains "codeagent.md documents operation '$op'" \
        "| \`$op\` |" "$doc_body"
done

# --- Test 2: every skill page is linked from the skills index --------------
#
# Pages are either `aitask-<name>.md` files or `aitask-<name>/` page bundles.
# The index must link the slug as `](aitask-<name>/)` — the relative-link form
# used by both the categorized tables and the intro prose.

index_body="$(cat "$SKILLS_INDEX")"
page_count=0

for path in "$SKILLS_DIR"/aitask-*; do
    [[ -e "$path" ]] || continue
    base="$(basename "$path")"
    if [[ -d "$path" ]]; then
        slug="$base"
    else
        # Strip the .md extension; skip anything that is not markdown.
        case "$base" in
            *.md) slug="${base%.md}" ;;
            *) continue ;;
        esac
    fi
    page_count=$((page_count + 1))
    assert_contains "skills/_index.md links '$slug'" \
        "]($slug/)" "$index_body"
done

# Tripwire: the glob must actually have matched skill pages.
assert_exit_zero_rc "skill pages discovered in skills/ ($page_count found)" \
    "$([[ $page_count -gt 0 ]] && echo 0 || echo 1)"

# --- Test 3: every artifact backend is documented --------------------------
#
# Source of truth: the `case "$backend"` arms of _artifact_backend_call in
# artifact_backend.sh. Accept both arm forms — the quoted one in use today
# (`dir)   "artifact_dir_${op}" "$@" ;;`) and the unquoted one the file's own
# BACKEND-EXTENSION-POINT comment tells contributors to write
# (`name) artifact_name_${op} "$@" ;;`). The comment line (leading `#`) and the
# `*)` catch-all both fail the leading [a-z] anchor.

arm_re='^[[:space:]]*([a-z][a-z0-9_]*)\)[[:space:]]+"?artifact_[a-z0-9_]+_\$\{op\}'
backends=""
while IFS= read -r line; do
    [[ "$line" =~ $arm_re ]] && backends+="${BASH_REMATCH[1]}"$'\n'
done < "$ARTIFACT_BACKEND_SH"
backends="$(printf '%s' "$backends" | sort)"
backend_count="$(printf '%s' "$backends" | grep -c . || true)"

# Tripwires: a non-empty parse is not enough — an arm in a shape the regex
# cannot read would simply be missing. Every backend is a module file in
# artifact_backends/ plus a dispatch arm, so the two lists must agree exactly.
assert_contains_re "backend arms parsed from artifact_backend.sh" \
    "[a-z]" "$backends"
assert_exit_zero_rc "backend arms discovered ($backend_count found)" \
    "$([[ $backend_count -gt 0 ]] && echo 0 || echo 1)"
modules=""
for path in "$ARTIFACT_BACKENDS_DIR"/*.sh; do
    [[ -e "$path" ]] || continue
    base="$(basename "$path")"
    modules+="${base%.sh}"$'\n'
done
modules="$(printf '%s' "$modules" | sort)"
assert_eq "dispatch arms match the artifact_backends/ modules" \
    "$modules" "$backends"

doc_body="$(cat "$ARTIFACTS_DOC")"

for backend in $backends; do
    # Match the backend as a backticked id in the table's first cell.
    assert_contains "concepts/artifacts.md documents backend '$backend'" \
        "| \`$backend\` |" "$doc_body"
done

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
