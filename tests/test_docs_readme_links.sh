#!/usr/bin/env bash
# test_docs_readme_links.sh - Link guard for docs/README.md (t1782).
#
# docs/README.md indexes the website docs but is not part of the Hugo build, so
# neither `hugo build` nor website/check_links.py ever sees it -- its links went
# dead with nothing failing. check_readme() closes that gap:
#
#   LINKS    every inline Markdown link target is extracted; zero extracted
#            links is a failure (the tripwire: bare paths or a changed link
#            syntax must not pass by checking nothing)
#   DEAD     every relative target resolves against docs/
#   MISSING  every top-level docs page (website/content/docs/*.md, minus the
#            root _index.md) and every top-level section
#            (website/content/docs/*/_index.md) is linked -- the set is derived
#            from the tree, never hard-coded
#
# What it does NOT check:
#   - only inline links, [text](target). Reference-style definitions
#     ([x]: path) and HTML <a href> are not seen -- deferred to t1788
#   - #fragment anchors are stripped, not validated
#   - subsection pages (e.g. tuis/board/*) are not required to be listed
#
# Test 1 runs the check against the real repository. Tests 2+ run it against
# throwaway fixtures whose README is generated from the fixture's own tree: a
# clean baseline, then negative controls that each break one thing and assert
# the matching finding. Without them the guard could be green because it checks
# nothing.
#
# Run: bash tests/test_docs_readme_links.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

cleanup() {
    local d
    for d in "${CLEANUP_DIRS[@]}"; do
        [[ -n "$d" && -d "$d" ]] && rm -rf "$d"
    done
}
trap cleanup EXIT

# docs_pages <docs_dir> - print the top-level pages and sections the README must
# list, relative to <docs_dir>: every *.md except the root _index.md, plus every
# */_index.md.
docs_pages() {
    local docs="$1" page rel
    for page in "$docs"/*.md "$docs"/*/_index.md; do
        [[ -e "$page" ]] || continue
        rel="${page#"$docs"/}"
        if [[ "$rel" != "_index.md" ]]; then
            echo "$rel"
        fi
    done
}

# check_readme <root> - print LINKS:<n>, then one DEAD:<target> or
# MISSING:<rel> line per finding. Returns 1 on any finding or when no link was
# extracted, 0 otherwise.
check_readme() {
    local root="$1"
    local docs="$root/website/content/docs"
    local rc=0 target rel listed t
    local -a targets=()

    while IFS= read -r target; do
        [[ "$target" =~ ^[a-zA-Z][a-zA-Z0-9+.-]*: ]] && continue
        target="${target%%#*}"
        [[ -n "$target" ]] && targets+=("$target")
    done < <(grep -oE '\]\([^)]+\)' "$root/docs/README.md" | sed -e 's/^](//' -e 's/)$//')

    echo "LINKS:${#targets[@]}"
    [[ "${#targets[@]}" -gt 0 ]] || rc=1

    for target in "${targets[@]}"; do
        if [[ ! -e "$root/docs/$target" ]]; then
            echo "DEAD:$target"
            rc=1
        fi
    done

    while IFS= read -r rel; do
        listed=0
        for t in "${targets[@]}"; do
            if [[ "$t" == "../website/content/docs/$rel" ]]; then
                listed=1
                break
            fi
        done
        if [[ "$listed" -eq 0 ]]; then
            echo "MISSING:$rel"
            rc=1
        fi
    done < <(docs_pages "$docs")

    return "$rc"
}

# run_check <root> - run check_readme, capturing CHECK_OUT and CHECK_RC.
run_check() {
    CHECK_RC=0
    CHECK_OUT="$(check_readme "$1")" || CHECK_RC=$?
}

# make_fixture - build FIXTURE: an empty file for every top-level page and
# section the real tree has, and no README yet.
make_fixture() {
    local rel
    FIXTURE="$(mktemp -d "${TMPDIR:-/tmp}/test_docs_readme_links.XXXXXX")"
    CLEANUP_DIRS+=("$FIXTURE")
    mkdir -p "$FIXTURE/docs"
    while IFS= read -r rel; do
        mkdir -p "$(dirname "$FIXTURE/website/content/docs/$rel")"
        : > "$FIXTURE/website/content/docs/$rel"
    done < <(docs_pages "$PROJECT_DIR/website/content/docs")
}

# write_readme <link|bare> - write FIXTURE's README, one table row per page of
# the fixture tree: an inline link (link) or the same target as a bare path.
write_readme() {
    local mode="$1" rel
    {
        echo "# Documentation"
        echo
        echo "| Guide | Description |"
        echo "|-------|-------------|"
        while IFS= read -r rel; do
            if [[ "$mode" == link ]]; then
                echo "| [$rel](../website/content/docs/$rel) | fixture row |"
            else
                echo "| $rel | ../website/content/docs/$rel |"
            fi
        done < <(docs_pages "$FIXTURE/website/content/docs")
    } > "$FIXTURE/docs/README.md"
}

test_live_repo_is_clean() {
    run_check "$PROJECT_DIR"
    assert_eq "live: check_readme exits 0" "0" "$CHECK_RC"
    assert_not_contains "live: no dead link" "DEAD:" "$CHECK_OUT"
    assert_not_contains "live: no missing page or section" "MISSING:" "$CHECK_OUT"
    assert_contains_re "live: links were extracted" "^LINKS:[1-9]" "$CHECK_OUT"
}

test_fixture_baseline_is_clean() {
    local expected
    make_fixture
    write_readme link
    expected="$(docs_pages "$FIXTURE/website/content/docs" | wc -l | tr -d ' ')"
    assert_eq "baseline: fixture has the concepts section" "yes" \
        "$([[ -e "$FIXTURE/website/content/docs/concepts/_index.md" ]] && echo yes || echo no)"
    run_check "$FIXTURE"
    assert_eq "baseline: check_readme exits 0" "0" "$CHECK_RC"
    assert_contains "baseline: one link per page" "LINKS:$expected" "$CHECK_OUT"
    assert_not_contains "baseline: no dead link" "DEAD:" "$CHECK_OUT"
    assert_not_contains "baseline: no missing page" "MISSING:" "$CHECK_OUT"
}

test_control_dead_link() {
    make_fixture
    write_readme link
    assert_eq "dead: fixture has the page it deletes" "yes" \
        "$([[ -e "$FIXTURE/website/content/docs/concepts/_index.md" ]] && echo yes || echo no)"
    rm "$FIXTURE/website/content/docs/concepts/_index.md"
    run_check "$FIXTURE"
    assert_eq "dead: check_readme exits 1" "1" "$CHECK_RC"
    assert_contains "dead: reports the target" \
        "DEAD:../website/content/docs/concepts/_index.md" "$CHECK_OUT"
}

test_control_missing_section() {
    make_fixture
    write_readme link
    mkdir -p "$FIXTURE/website/content/docs/newsection"
    : > "$FIXTURE/website/content/docs/newsection/_index.md"
    run_check "$FIXTURE"
    assert_eq "missing section: check_readme exits 1" "1" "$CHECK_RC"
    assert_contains "missing section: reports it" "MISSING:newsection/_index.md" "$CHECK_OUT"
}

test_control_missing_top_level_page() {
    make_fixture
    write_readme link
    : > "$FIXTURE/website/content/docs/new-page.md"
    run_check "$FIXTURE"
    assert_eq "missing page: check_readme exits 1" "1" "$CHECK_RC"
    assert_contains "missing page: reports it" "MISSING:new-page.md" "$CHECK_OUT"
}

test_control_bare_paths() {
    make_fixture
    write_readme bare
    run_check "$FIXTURE"
    assert_eq "bare paths: check_readme exits 1" "1" "$CHECK_RC"
    assert_contains "bare paths: tripwire fires" "LINKS:0" "$CHECK_OUT"
    assert_contains "bare paths: pages reported missing" "MISSING:concepts/_index.md" "$CHECK_OUT"
}

test_live_repo_is_clean
test_fixture_baseline_is_clean
test_control_dead_link
test_control_missing_section
test_control_missing_top_level_page
test_control_bare_paths

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
