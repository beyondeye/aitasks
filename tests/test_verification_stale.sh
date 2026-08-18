#!/usr/bin/env bash
# test_verification_stale.sh - Tests for the manual-verification staleness seam
# (t1555_1): the check helper, the `verification_baseline:` frontmatter field,
# and carry-over inheritance.
#
# Sections:
#   A. aitask_verification_stale.sh over real sandbox git repos
#   B. --verification-baseline round-trip through aitask_update.sh
#   C. carry-over inheritance through aitask_archive.sh
#   D. invocation-allowlist coverage
#
# Test bodies are plain functions (never `( … )` subshells), so the in-process
# PASS/FAIL counters from tests/lib/asserts.sh are sufficient — the file-backed
# counters (assert_counters_init) are deliberately NOT used.
#
# Run: bash tests/test_verification_stale.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

HELPER="$PROJECT_DIR/.aitask-scripts/aitask_verification_stale.sh"
UPDATE_SH="$PROJECT_DIR/.aitask-scripts/aitask_update.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

# Fixed deterministic timestamp — the baseline's `@ <ts>` half is opaque to the
# helper (only the sha is probed), so no date dependency is needed anywhere.
TS="2026-01-01 10:00"

# --- Fixture factories -------------------------------------------------------

new_repo() {
    # new_repo -> echoes a fresh git repo path with an initial commit
    local d
    d="$(mktemp -d)"
    CLEANUP_DIRS+=("$d")
    git init --quiet "$d"
    git -C "$d" config user.email "test@test.com"
    git -C "$d" config user.name "Test"
    git -C "$d" config commit.gpgsign false
    mkdir -p "$d/lib" "$d/docs"
    echo "seed" > "$d/README.md"
    git -C "$d" add -A
    git -C "$d" commit -q -m "chore: seed repo (t1)"
    printf '%s' "$d"
}

commit_file() {
    # commit_file <repo> <relpath> <content> <subject>
    local d="$1" rel="$2" content="$3" subject="$4"
    mkdir -p "$d/$(dirname "$rel")"
    printf '%s\n' "$content" > "$d/$rel"
    # :(literal) for the same reason the helper under test needs it: `git add`
    # takes a PATHSPEC, so a glob-shaped fixture filename would stage its
    # neighbours too and quietly destroy the fixture's premise.
    git -C "$d" add -- ":(literal)$rel"
    git -C "$d" commit -q -m "$subject"
}

remove_file() {
    # remove_file <repo> <relpath> <subject>
    local d="$1" rel="$2" subject="$3"
    # :(literal) as in commit_file -- `git rm -- 'docs/a[bc].md'` would also
    # delete docs/ab.md.
    git -C "$d" rm -q -- ":(literal)$rel"
    git -C "$d" commit -q -m "$subject"
}

mk_task() {
    # mk_task <path> <baseline-value-or-empty> <file_references-csv-or-empty>
    local path="$1" baseline="$2" refs="$3"
    {
        echo "---"
        echo "priority: medium"
        echo "effort: low"
        echo "depends: []"
        echo "issue_type: manual_verification"
        echo "status: Ready"
        echo "labels: []"
        if [[ -n "$refs" ]]; then
            echo "file_references: [$refs]"
        fi
        if [[ -n "$baseline" ]]; then
            echo "verification_baseline: $baseline"
        fi
        echo "created_at: $TS"
        echo "updated_at: $TS"
        echo "---"
        echo ""
        echo "Body"
        echo ""
        echo "## Verification Checklist"
        echo ""
        echo "- [ ] item"
    } > "$path"
}

run_check() {
    # run_check <repo> <task_file_rel> -- runs with cwd inside the sandbox so the
    # helper's own `git rev-parse --show-toplevel` targets the fixture repo.
    ( cd "$1" && bash "$HELPER" check "$2" )
}

decision_of() {
    printf '%s\n' "$1" | sed -n 's/^DECISION://p' | head -1
}

count_matches() {
    # count_matches <output> <ERE>
    local n
    n=$(printf '%s\n' "$1" | grep -cE "$2" || true)
    printf '%s' "$n"
}

assert_no_evidence() {
    # assert_no_evidence <desc> <output>
    local n
    n=$(count_matches "$2" '^(CHANGED|DELETED|UNKNOWN):')
    assert_eq "$1" "0" "$n"
}

# =============================================================================
# Section A — the check helper
# =============================================================================

test_modified_file_is_ask_stale() {
    echo "=== A: a curated file modified since the baseline => ASK_STALE + CHANGED ==="
    local d base out
    d=$(new_repo)
    commit_file "$d" lib/a.sh "one" "feature: add a (t100)"
    base=$(git -C "$d" rev-parse HEAD)
    commit_file "$d" lib/a.sh "two" "enhancement: tweak a (t777)"

    mk_task "$d/t.md" "$base @ $TS" "lib/a.sh"
    out=$(run_check "$d" t.md)

    assert_eq "modified => ASK_STALE" "ASK_STALE" "$(decision_of "$out")"
    assert_contains "modified => CHANGED names the culprit task" "CHANGED:lib/a.sh|1|777" "$out"
    assert_contains "modified => FILES:1" "FILES:1" "$out"
}

test_deleted_file_is_detected_by_probe_not_history() {
    echo "=== A: a curated file DELETED since the baseline => DELETED, never CHANGED ==="
    local d base out
    d=$(new_repo)
    commit_file "$d" lib/b.sh "one" "feature: add b (t101)"
    base=$(git -C "$d" rev-parse HEAD)
    remove_file "$d" lib/b.sh "chore: drop b (t778)"

    mk_task "$d/t.md" "$base @ $TS" "lib/b.sh"
    out=$(run_check "$d" t.md)

    assert_eq "deleted => ASK_STALE" "ASK_STALE" "$(decision_of "$out")"
    assert_contains "deleted => DELETED names the culprit task" "DELETED:lib/b.sh|778|" "$out"
    # THE DISCRIMINATOR. The deletion commit IS inside baseline..HEAD, so a
    # history-only implementation reports this file as CHANGED and passes the
    # modified case above. Only the `git cat-file -e HEAD:<path>` probe can tell
    # the two apart, and this assertion is what proves the probe is doing it.
    assert_not_contains "deleted => NOT reported as CHANGED (history-only would)" \
        "CHANGED:lib/b.sh" "$out"
}

test_mixed_changed_deleted_untouched() {
    echo "=== A: mixed changed + deleted + untouched => exactly two evidence lines ==="
    local d base out n
    d=$(new_repo)
    commit_file "$d" lib/a.sh "one" "feature: add a (t100)"
    commit_file "$d" lib/b.sh "one" "feature: add b (t101)"
    commit_file "$d" lib/c.sh "one" "feature: add c (t102)"
    base=$(git -C "$d" rev-parse HEAD)
    commit_file "$d" lib/a.sh "two" "enhancement: tweak a (t777)"
    remove_file "$d" lib/b.sh "chore: drop b (t778)"

    mk_task "$d/t.md" "$base @ $TS" "lib/a.sh, lib/b.sh, lib/c.sh"
    out=$(run_check "$d" t.md)

    assert_eq "mixed => ASK_STALE" "ASK_STALE" "$(decision_of "$out")"
    assert_contains "mixed => FILES:3" "FILES:3" "$out"
    n=$(count_matches "$out" '^(CHANGED|DELETED|UNKNOWN):')
    assert_eq "mixed => exactly two evidence lines" "2" "$n"
    assert_contains "mixed => a is CHANGED" "CHANGED:lib/a.sh|" "$out"
    assert_contains "mixed => b is DELETED" "DELETED:lib/b.sh|" "$out"
    assert_not_contains "mixed => untouched c has no evidence line" "lib/c.sh|" "$out"
}

test_invalid_scope_entry_is_never_fresh() {
    echo "=== A: a path absent at the baseline => UNKNOWN + ASK_STALE (never FRESH/SKIP) ==="
    local d base out decision
    d=$(new_repo)
    commit_file "$d" lib/a.sh "one" "feature: add a (t100)"
    base=$(git -C "$d" rev-parse HEAD)
    # Added AFTER the baseline: a hand-edited scope entry, or a typo.
    commit_file "$d" lib/new.sh "one" "feature: add new (t779)"

    mk_task "$d/t.md" "$base @ $TS" "lib/new.sh"
    out=$(run_check "$d" t.md)
    decision=$(decision_of "$out")

    assert_contains "invalid scope => UNKNOWN with the absent_at_baseline reason" \
        "UNKNOWN:lib/new.sh|absent_at_baseline" "$out"
    # Stated as three separate assertions on purpose: a FRESH verdict over a
    # partly-uncheckable scope list is indistinguishable, to the user, from a
    # real all-clear — the one outcome this design must never produce.
    assert_eq "invalid scope => ASK_STALE" "ASK_STALE" "$decision"
    assert_not_contains "invalid scope => NOT FRESH" "DECISION:FRESH" "$out"
    assert_not_contains "invalid scope => NOT SKIP" "DECISION:SKIP" "$out"
}

test_mixed_valid_and_invalid_scope() {
    echo "=== A: mixed valid + invalid scope => one UNKNOWN, DISPLAY separates the causes ==="
    local d base out n display
    d=$(new_repo)
    commit_file "$d" lib/a.sh "one" "feature: add a (t100)"
    base=$(git -C "$d" rev-parse HEAD)
    commit_file "$d" lib/bogus.sh "one" "feature: add bogus (t780)"

    mk_task "$d/t.md" "$base @ $TS" "lib/a.sh, lib/bogus.sh"
    out=$(run_check "$d" t.md)
    display=$(printf '%s\n' "$out" | sed -n 's/^DISPLAY://p' | head -1)

    assert_eq "mixed scope => ASK_STALE" "ASK_STALE" "$(decision_of "$out")"
    n=$(count_matches "$out" '^UNKNOWN:')
    assert_eq "mixed scope => exactly one UNKNOWN line" "1" "$n"
    # The remedies differ (repair file_references: vs amend the checklist), so
    # DISPLAY must name the uncheckable path under its own cause.
    assert_contains "DISPLAY names the uncheckable path under its own cause" \
        "not present at baseline (fix file_references:): lib/bogus.sh" "$display"
    assert_not_contains "DISPLAY does not report the untouched file as changed" \
        "changed since baseline" "$display"
}

test_negative_control_all_untouched_is_fresh() {
    echo "=== A: negative control — untouched AND all valid => FRESH ==="
    local d base out
    d=$(new_repo)
    commit_file "$d" lib/a.sh "one" "feature: add a (t100)"
    commit_file "$d" lib/c.sh "one" "feature: add c (t102)"
    base=$(git -C "$d" rev-parse HEAD)
    # Unrelated later work that touches neither curated file.
    commit_file "$d" docs/other.md "x" "documentation: unrelated (t781)"

    mk_task "$d/t.md" "$base @ $TS" "lib/a.sh, lib/c.sh"
    out=$(run_check "$d" t.md)

    # A detector that cannot say FRESH is the failure mode the whole design
    # exists to avoid. This control only holds because every path is checkable —
    # the two invalid-scope cases above are its necessary complement.
    assert_eq "untouched + valid => FRESH [test_negative_control_all_untouched_is_fresh]" \
        "FRESH" "$(decision_of "$out")"
    assert_no_evidence "FRESH => no evidence lines" "$out"
    assert_contains "FRESH => FILES:2" "FILES:2" "$out"
}

test_dirty_worktree_is_not_a_change() {
    echo "=== A: uncommitted edits are invisible (committed-tree probes) ==="
    local d base out
    d=$(new_repo)
    commit_file "$d" lib/a.sh "one" "feature: add a (t100)"
    commit_file "$d" lib/b.sh "one" "feature: add b (t101)"
    base=$(git -C "$d" rev-parse HEAD)

    # Edit one curated file and DELETE another, committing neither.
    printf 'dirty\n' > "$d/lib/a.sh"
    rm -f "$d/lib/b.sh"

    mk_task "$d/t.md" "$base @ $TS" "lib/a.sh, lib/b.sh"
    out=$(run_check "$d" t.md)

    # This is the only fixture that separates the contract ("probe the COMMITTED
    # trees, never the dirty worktree") from an implementation built on a
    # working-tree diff: every other case commits its edits, so `git diff HEAD`
    # and `git diff <baseline>` agree and a worktree-based implementation passes
    # them all.
    assert_eq "dirty worktree => FRESH" "FRESH" "$(decision_of "$out")"
    assert_no_evidence "dirty worktree => no evidence lines" "$out"
}

test_delimiter_in_path_is_encoded() {
    echo "=== A: a path containing the protocol delimiter is encoded, not ambiguous ==="
    local d base out line nf decoded
    d=$(new_repo)
    commit_file "$d" 'docs/a|b.md' "one" "documentation: add piped (t103)"
    base=$(git -C "$d" rev-parse HEAD)
    commit_file "$d" 'docs/a|b.md' "two" "documentation: edit piped (t782)"

    mk_task "$d/t.md" "$base @ $TS" 'docs/a|b.md'
    out=$(run_check "$d" t.md)

    assert_eq "piped path => ASK_STALE" "ASK_STALE" "$(decision_of "$out")"
    assert_contains "piped path => emitted percent-encoded" "CHANGED:docs/a%7Cb.md|1|782" "$out"
    assert_not_contains "piped path => raw delimiter never emitted in a record" \
        "CHANGED:docs/a|b.md" "$out"

    # The executable statement of the ambiguity: an unencoded path yields one
    # EXTRA field, so a naive left-to-right split lands on the wrong boundary.
    line=$(printf '%s\n' "$out" | grep '^CHANGED:' | head -1)
    nf=$(printf '%s\n' "$line" | awk -F'|' '{print NF}')
    assert_eq "piped path => CHANGED record still has exactly 3 fields" "3" "$nf"

    # Decode round-trip: %7C -> | then %25 -> %
    decoded=$(printf '%s' "$line" | sed 's/^CHANGED://; s/|.*$//')
    decoded="${decoded//%7C/|}"
    decoded="${decoded//%25/%}"
    assert_eq "piped path => decodes back byte-for-byte" 'docs/a|b.md' "$decoded"
}

test_percent_encoding_is_lossless() {
    echo "=== A: a literal '%7C' in a filename does not collide with the encoding ==="
    local d base out line decoded
    d=$(new_repo)
    commit_file "$d" 'docs/lit%7Cnot-a-pipe.md' "one" "documentation: add literal (t104)"
    base=$(git -C "$d" rev-parse HEAD)
    commit_file "$d" 'docs/lit%7Cnot-a-pipe.md' "two" "documentation: edit literal (t783)"

    mk_task "$d/t.md" "$base @ $TS" 'docs/lit%7Cnot-a-pipe.md'
    out=$(run_check "$d" t.md)

    # Pins the encode-'%'-first ordering — the only part of the rule that can
    # silently corrupt a name. Encoding '|' first would emit `lit%7C…`, which
    # decodes to `lit|not-a-pipe.md`: a different file.
    assert_contains "literal %7C => escaped to %257C" "CHANGED:docs/lit%257Cnot-a-pipe.md|" "$out"
    line=$(printf '%s\n' "$out" | grep '^CHANGED:' | head -1)
    decoded=$(printf '%s' "$line" | sed 's/^CHANGED://; s/|.*$//')
    decoded="${decoded//%7C/|}"
    decoded="${decoded//%25/%}"
    assert_eq "literal %7C => decodes back byte-for-byte" 'docs/lit%7Cnot-a-pipe.md' "$decoded"
}

test_glob_chars_in_path_do_not_match_neighbours() {
    echo "=== A: a glob-shaped filename does not absorb its neighbours ==="
    local d base out
    d=$(new_repo)
    commit_file "$d" 'docs/a[bc].md' "one" "documentation: add literal (t105)"
    commit_file "$d" docs/ab.md "one" "documentation: add neighbour (t106)"
    base=$(git -C "$d" rev-parse HEAD)
    # Touch ONLY the neighbour, which the pathspec glob `a[bc].md` matches.
    commit_file "$d" docs/ab.md "two" "bug: touch neighbour only (t999)"

    mk_task "$d/t.md" "$base @ $TS" 'docs/a[bc].md'
    out=$(run_check "$d" t.md)

    # `git log -- <path>` matches a PATHSPEC, and a pathspec containing *, ? or
    # [...] is fnmatch-globbed — all legal POSIX filename characters. Without
    # `:(literal)` the curated file reports the neighbour's commit and the
    # helper violates its own FRESH contract on a file nothing touched.
    assert_eq "glob-shaped path untouched => FRESH" "FRESH" "$(decision_of "$out")"
    assert_no_evidence "glob-shaped path untouched => no evidence lines" "$out"
    assert_not_contains "the neighbour's task id never leaks in" "999" "$out"
}

test_glob_chars_do_not_contaminate_real_evidence() {
    echo "=== A: a glob-shaped filename's own evidence is not inflated by neighbours ==="
    local d base out
    d=$(new_repo)
    commit_file "$d" 'docs/a[bc].md' "one" "documentation: add literal (t105)"
    commit_file "$d" docs/ab.md "one" "documentation: add neighbour (t106)"
    base=$(git -C "$d" rev-parse HEAD)
    commit_file "$d" docs/ab.md "two" "bug: touch neighbour only (t999)"
    commit_file "$d" 'docs/a[bc].md' "two" "bug: touch the literal file (t888)"

    mk_task "$d/t.md" "$base @ $TS" 'docs/a[bc].md'
    out=$(run_check "$d" t.md)

    # The genuine change IS detected either way (git matches a literal path
    # before globbing), so the discriminator is the EVIDENCE: without
    # `:(literal)` the count reads 2 and the neighbour's task id is attributed
    # to this file, sending the user to amend a checklist for the wrong change.
    assert_eq "glob-shaped path changed => ASK_STALE" "ASK_STALE" "$(decision_of "$out")"
    assert_contains "exactly its own commit is counted and attributed" \
        "CHANGED:docs/a[bc].md|1|888" "$out"
    assert_not_contains "the neighbour's task id is not attributed to it" "999" "$out"
}

test_deleted_glob_path_names_its_own_culprit() {
    echo "=== A: a deleted glob-shaped path names its own culprit, not a neighbour's ==="
    local d base out
    d=$(new_repo)
    commit_file "$d" 'docs/a[bc].md' "one" "documentation: add literal (t105)"
    commit_file "$d" docs/ab.md "one" "documentation: add neighbour (t106)"
    base=$(git -C "$d" rev-parse HEAD)
    # ORDER IS THE DISCRIMINATOR. The culprit query is `-n1`, i.e. the NEWEST
    # matching deletion — so the neighbour must be deleted LAST. Deleting it
    # first would make the two implementations agree and the fixture prove
    # nothing: with globbing the newest D-commit matching `docs/a[bc].md` is
    # then the neighbour's, which `:(literal)` excludes.
    remove_file "$d" 'docs/a[bc].md' "chore: drop the literal file (t998)"
    remove_file "$d" docs/ab.md "chore: drop neighbour (t997)"

    mk_task "$d/t.md" "$base @ $TS" 'docs/a[bc].md'
    out=$(run_check "$d" t.md)

    assert_eq "deleted glob-shaped path => ASK_STALE" "ASK_STALE" "$(decision_of "$out")"
    assert_contains "culprit is its own deletion commit" "DELETED:docs/a[bc].md|998|" "$out"
    assert_not_contains "not the neighbour's deletion commit" "997" "$out"
}

test_ranged_reference_unchanged_is_fresh() {
    echo "=== A: a ranged reference to an unchanged file => FRESH ==="
    local d base out
    d=$(new_repo)
    commit_file "$d" lib/a.sh "one" "feature: add a (t100)"
    base=$(git -C "$d" rev-parse HEAD)
    commit_file "$d" docs/other.md "x" "documentation: unrelated (t784)"

    mk_task "$d/t.md" "$base @ $TS" "lib/a.sh:3-9"
    out=$(run_check "$d" t.md)

    # The discriminator for the range strip: probing `lib/a.sh:3-9` literally
    # returns UNKNOWN|absent_at_baseline and would prompt FOREVER on a perfectly
    # valid scoped reference.
    assert_eq "ranged + unchanged => FRESH" "FRESH" "$(decision_of "$out")"
    assert_no_evidence "ranged + unchanged => no evidence lines" "$out"
}

test_ranged_reference_changed_reports_stripped_path() {
    echo "=== A: a ranged reference to a changed file reports the STRIPPED path ==="
    local d base out
    d=$(new_repo)
    commit_file "$d" lib/a.sh "one" "feature: add a (t100)"
    base=$(git -C "$d" rev-parse HEAD)
    commit_file "$d" lib/a.sh "two" "enhancement: tweak a (t785)"

    mk_task "$d/t.md" "$base @ $TS" "lib/a.sh:3-9"
    out=$(run_check "$d" t.md)

    assert_eq "ranged + changed => ASK_STALE" "ASK_STALE" "$(decision_of "$out")"
    assert_contains "ranged + changed => path is stripped in the record" \
        "CHANGED:lib/a.sh|1|785" "$out"
    assert_not_contains "ranged + changed => raw ref not emitted" "CHANGED:lib/a.sh:3-9" "$out"
}

test_multi_range_reference_is_stripped() {
    echo "=== A: the compact multi-range form is stripped too ==="
    local d base out
    d=$(new_repo)
    commit_file "$d" lib/a.sh "one" "feature: add a (t100)"
    base=$(git -C "$d" rev-parse HEAD)
    commit_file "$d" docs/other.md "x" "documentation: unrelated (t786)"

    mk_task "$d/t.md" "$base @ $TS" "lib/a.sh:3-9^20-30"
    out=$(run_check "$d" t.md)

    assert_eq "multi-range + unchanged => FRESH" "FRESH" "$(decision_of "$out")"
    assert_contains "multi-range => FILES:1" "FILES:1" "$out"
}

test_duplicate_ranges_of_one_file_dedupe() {
    echo "=== A: two ranges of one file are one path => FILES:1, one evidence line ==="
    local d base out n
    d=$(new_repo)
    commit_file "$d" lib/a.sh "one" "feature: add a (t100)"
    base=$(git -C "$d" rev-parse HEAD)
    commit_file "$d" lib/a.sh "two" "enhancement: tweak a (t787)"

    mk_task "$d/t.md" "$base @ $TS" "lib/a.sh:1-4, lib/a.sh:20-30"
    out=$(run_check "$d" t.md)

    # Pins both the dedupe and the FILES: denominator — FILES must equal the
    # number of paths actually probed, or the DISPLAY count misleads.
    assert_contains "duplicate ranges => FILES:1" "FILES:1" "$out"
    n=$(count_matches "$out" '^(CHANGED|DELETED|UNKNOWN):')
    assert_eq "duplicate ranges => exactly one evidence line" "1" "$n"
}

test_precondition_skips() {
    echo "=== A: precondition skips (fail-open, silent) ==="
    local d base out
    d=$(new_repo)
    commit_file "$d" lib/a.sh "one" "feature: add a (t100)"
    base=$(git -C "$d" rev-parse HEAD)
    commit_file "$d" lib/a.sh "two" "enhancement: tweak a (t788)"

    # (a) populated list, no baseline
    mk_task "$d/t_nobase.md" "" "lib/a.sh"
    out=$(run_check "$d" t_nobase.md)
    assert_eq "list but no baseline => SKIP" "SKIP" "$(decision_of "$out")"
    assert_contains "no baseline => BASELINE:NONE" "BASELINE:NONE" "$out"
    assert_no_evidence "no baseline => no evidence lines" "$out"

    # (b) baseline, no list
    mk_task "$d/t_norefs.md" "$base @ $TS" ""
    out=$(run_check "$d" t_norefs.md)
    assert_eq "baseline but no list => SKIP" "SKIP" "$(decision_of "$out")"
    assert_contains "no list => FILES:0" "FILES:0" "$out"
    assert_no_evidence "no list => no evidence lines" "$out"

    # (c) neither
    mk_task "$d/t_neither.md" "" ""
    out=$(run_check "$d" t_neither.md)
    assert_eq "neither field => SKIP" "SKIP" "$(decision_of "$out")"
    assert_no_evidence "neither field => no evidence lines" "$out"

    # (d) baseline not an ancestor of HEAD (history rewritten / unknown sha)
    mk_task "$d/t_orphan.md" "0000000000000000000000000000000000000000 @ $TS" "lib/a.sh"
    out=$(run_check "$d" t_orphan.md)
    assert_eq "non-ancestor baseline => SKIP" "SKIP" "$(decision_of "$out")"
    assert_no_evidence "non-ancestor baseline => no evidence lines" "$out"
    assert_contains "non-ancestor baseline => reason names history rewrite" \
        "is not an ancestor of HEAD" "$out"
}

test_outside_a_git_repository_skips() {
    echo "=== A: outside any git repository => the fixed SKIP protocol, exit 0 ==="
    local d out rc
    d="$(mktemp -d)"
    CLEANUP_DIRS+=("$d")

    # The fixture is only meaningful if the temp dir really is outside a repo —
    # a $TMPDIR that happens to sit inside a checkout would make this pass
    # vacuously. Fail loudly rather than silently proving nothing.
    TOTAL=$((TOTAL + 1))
    if git -C "$d" rev-parse --show-toplevel >/dev/null 2>&1; then
        FAIL=$((FAIL + 1))
        echo "FAIL: fixture invalid — \$TMPDIR ($d) is inside a git repository"
        return 0
    fi
    PASS=$((PASS + 1))

    # Both preconditions populated, so ONLY the not-a-repo branch can produce SKIP.
    mk_task "$d/t.md" "deadbee @ $TS" "lib/a.sh"

    rc=0
    out=$( cd "$d" && bash "$HELPER" check t.md ) || rc=$?

    # Under `set -euo pipefail` an unguarded `git rev-parse` aborts the script
    # with a non-zero exit and NO output at all; every other fixture runs inside
    # a repo, so this is the only case that proves the protocol survives.
    assert_eq "outside a repo => exit 0" "0" "$rc"
    assert_eq "outside a repo => SKIP" "SKIP" "$(decision_of "$out")"
    assert_contains "outside a repo => BASELINE:NONE" "BASELINE:NONE" "$out"
    assert_contains "outside a repo => FILES:0" "FILES:0" "$out"
    assert_contains "outside a repo => DISPLAY names the reason" \
        "DISPLAY:Staleness check skipped: not a git repository." "$out"
    assert_no_evidence "outside a repo => no evidence lines" "$out"
}

test_baseline_advance_stops_the_prompt() {
    echo "=== A: advancing the baseline to HEAD stops the prompt re-firing ==="
    local d base head out
    d=$(new_repo)
    commit_file "$d" lib/a.sh "one" "feature: add a (t100)"
    base=$(git -C "$d" rev-parse HEAD)
    commit_file "$d" lib/a.sh "two" "enhancement: tweak a (t789)"

    mk_task "$d/t.md" "$base @ $TS" "lib/a.sh"
    out=$(run_check "$d" t.md)
    assert_eq "before advance => ASK_STALE" "ASK_STALE" "$(decision_of "$out")"

    # Simulate the user answering "Proceed unchanged": the baseline advances to
    # HEAD. Advancing on dismissal is load-bearing — without it the user is
    # re-prompted on every later pick and learns to ignore the prompt.
    head=$(git -C "$d" rev-parse HEAD)
    mk_task "$d/t.md" "$head @ $TS" "lib/a.sh"
    out=$(run_check "$d" t.md)
    assert_eq "after advance => FRESH (prompt does not re-fire)" "FRESH" "$(decision_of "$out")"
    assert_no_evidence "after advance => no evidence lines" "$out"
}

# =============================================================================
# Section B — the --verification-baseline setter
# =============================================================================

setup_update_project() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    CLEANUP_DIRS+=("$tmpdir")

    local remote_dir="$tmpdir/remote.git"
    git init --bare --quiet "$remote_dir"
    local local_dir="$tmpdir/local"
    git clone --quiet "$remote_dir" "$local_dir" 2>/dev/null

    pushd "$local_dir" > /dev/null
    git config user.email "test@test.com"
    git config user.name "Test"

    mkdir -p aitasks/metadata aitasks/new
    setup_fake_aitask_repo "$PWD"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true
    chmod +x .aitask-scripts/*.sh

    printf 'bug\nchore\ndocumentation\nenhancement\nfeature\nperformance\nrefactor\nstyle\ntest\nmanual_verification\n' \
        > aitasks/metadata/task_types.txt
    : > aitasks/metadata/labels.txt
    echo "aitasks/new/" > .gitignore

    git add -A
    git commit -m "Initial setup" --quiet
    git push --quiet 2>/dev/null || true
}

teardown_update_project() {
    popd > /dev/null 2>&1 || true
}

write_update_task() {
    local path="$1"
    shift
    mkdir -p "$(dirname "$path")"
    {
        printf '%s\n' "---"
        printf '%s\n' "priority: medium"
        printf '%s\n' "effort: low"
        printf '%s\n' "depends: []"
        printf '%s\n' "issue_type: manual_verification"
        printf '%s\n' "status: Ready"
        printf '%s\n' "labels: []"
        local extra
        for extra in "$@"; do
            printf '%s\n' "$extra"
        done
        printf '%s\n' "created_at: $TS"
        printf '%s\n' "updated_at: $TS"
        printf '%s\n' "---"
        printf '\nBody\n'
    } > "$path"
}

read_fm_field() {
    local file="$1" field="$2"
    awk -v f="$field" '
        BEGIN { in_fm = 0 }
        $0 == "---" { in_fm = !in_fm; next }
        in_fm && $0 ~ "^" f ":" { sub("^" f ":[[:space:]]*", ""); print; exit }
    ' "$file"
}

assert_no_fm_field() {
    local desc="$1" file="$2" field="$3"
    TOTAL=$((TOTAL + 1))
    if grep -qE "^${field}:" "$file"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc ('${field}:' unexpectedly present in $file)"
    else
        PASS=$((PASS + 1))
    fi
}

test_setter_round_trip() {
    echo "=== B: --verification-baseline round-trip ==="
    setup_update_project

    local value="a1b2c3d4e5f6 @ 2026-08-17 19:04"
    write_update_task aitasks/t10_foo.md "file_references: [lib/a.sh]"

    bash .aitask-scripts/aitask_update.sh --batch 10 \
        --verification-baseline "$value" --silent >/dev/null
    assert_eq "setter writes the field byte-identically" \
        "$value" "$(read_fm_field aitasks/t10_foo.md verification_baseline)"

    # An unrelated update must preserve it (the shared writer rebuilds the whole
    # frontmatter from a fixed field set, so a missed positional drops it).
    bash .aitask-scripts/aitask_update.sh --batch 10 --status Done --silent >/dev/null
    assert_eq "survives an unrelated --status update" \
        "$value" "$(read_fm_field aitasks/t10_foo.md verification_baseline)"
    assert_eq "the unrelated update still applied" \
        "Done" "$(read_fm_field aitasks/t10_foo.md status)"

    # Clearing removes the key — there is no tombstone for this field.
    bash .aitask-scripts/aitask_update.sh --batch 10 \
        --verification-baseline "" --silent >/dev/null
    assert_no_fm_field "empty value clears the field (key removed)" \
        aitasks/t10_foo.md verification_baseline

    teardown_update_project
}

test_setter_does_not_materialize_absent_fields() {
    echo "=== B: an unrelated update invents neither field ==="
    setup_update_project

    write_update_task aitasks/t11_bare.md
    bash .aitask-scripts/aitask_update.sh --batch 11 --priority high --silent >/dev/null

    assert_no_fm_field "a task without a baseline does not gain an empty one" \
        aitasks/t11_bare.md verification_baseline
    # Scope guard for this slice: file_references emission must be untouched, so
    # a task with no scope list must not acquire an empty one.
    assert_no_fm_field "a task without file_references does not gain an empty list" \
        aitasks/t11_bare.md file_references

    teardown_update_project
}

# --- Post-phase risk mitigation: pin_baseline_across_all_write_paths ---------
# The field is threaded as a positional through write_task_file, which has THREE
# call sites. Missing one drops the field silently on that path, with no error.
# The batch path is covered by the round-trip above; these cover the other two.

test_baseline_survives_parent_rewrite_path() {
    echo "=== B(post-phase): the parent-rewrite write path preserves the baseline ==="
    setup_update_project

    local value="feedbeef1234 @ 2026-08-17 19:04"
    write_update_task aitasks/t20_parent.md \
        "children_to_implement: [t20_1]" \
        "verification_baseline: $value"
    write_update_task aitasks/t20/t20_1_child.md

    # Completing a CHILD is what reaches handle_child_task_completion, which
    # re-parses the PARENT and rewrites it through its own write_task_file call.
    bash .aitask-scripts/aitask_update.sh --batch 20_1 --status Done --silent >/dev/null

    assert_eq "parent baseline survives the child-completion rewrite" \
        "$value" "$(read_fm_field aitasks/t20_parent.md verification_baseline)"
    assert_eq "the parent rewrite still did its job" \
        "" "$(read_fm_field aitasks/t20_parent.md children_to_implement)"

    teardown_update_project
}

test_every_write_task_file_call_site_is_wired() {
    echo "=== B(post-phase): every write_task_file call site passes the baseline ==="
    local calls wired
    calls=$(grep -cE '^[[:space:]]*write_task_file "' "$UPDATE_SH")
    wired=$(grep -cE '^[[:space:]]*"\$(CURRENT_VERIFICATION_BASELINE|new_verification_baseline)"[[:space:]]*\\?$' "$UPDATE_SH")

    # Structural pin for the interactive call site, which needs fzf and cannot be
    # driven from a test. It also catches the general failure: a FUTURE call site
    # added without the trailing positional makes these two counts diverge.
    #
    # The pattern is anchored to a WHOLE line (mirroring the followup_kind guard
    # in test_followup_kind_roundtrip.sh Part E) so the `local
    # new_verification_baseline="$CURRENT_VERIFICATION_BASELINE"` assignment and
    # the save/restore pair are not miscounted as forwards. A trailing
    # line-continuation is tolerated so the NEXT field appended after this one
    # does not trip the guard -- what is being asserted is that the positional is
    # forwarded, not that it is last.
    assert_eq "write_task_file call sites found" "3" "$calls"
    assert_eq "every call site passes the verification_baseline positional" \
        "$calls" "$wired"
}

# =============================================================================
# Section C — carry-over inheritance
# =============================================================================

setup_archive_project() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    CLEANUP_DIRS+=("$tmpdir")

    local remote_dir="$tmpdir/remote.git"
    git init --bare --quiet "$remote_dir"
    local local_dir="$tmpdir/local"
    git clone --quiet "$remote_dir" "$local_dir" 2>/dev/null

    pushd "$local_dir" > /dev/null
    git config user.email "test@test.com"
    git config user.name "Test"

    mkdir -p aitasks/archived aitasks/metadata aiplans/archived
    setup_fake_aitask_repo "$PWD"

    cp "$PROJECT_DIR/.aitask-scripts/aitask_archive.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_create.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_query_files.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_lock.sh" .aitask-scripts/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/aitask_fold_mark.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_verification_parse.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_verification_parse.py" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/pid_anchor.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/

    chmod +x .aitask-scripts/*.sh .aitask-scripts/*.py 2>/dev/null || true

    printf 'bug\nchore\ndocumentation\nenhancement\nfeature\nperformance\nrefactor\nstyle\ntest\nmanual_verification\n' \
        > aitasks/metadata/task_types.txt
    : > aitasks/metadata/labels.txt

    git add -A
    git commit -m "Initial setup" --quiet
    git push --quiet 2>/dev/null || true

    ./.aitask-scripts/aitask_claim_id.sh --init > /dev/null 2>&1
}

test_carryover_inherits_baseline() {
    echo "=== C: a carry-over task INHERITS verification_baseline, never resets it ==="
    setup_archive_project

    local value="cafebabe9876 @ 2026-08-17 19:04"
    {
        echo "---"
        echo "priority: medium"
        echo "effort: low"
        echo "depends: []"
        echo "issue_type: manual_verification"
        echo "status: Implementing"
        echo "labels: []"
        echo "file_references: [lib/a.sh]"
        echo "verification_baseline: $value"
        echo "created_at: 2026-04-21 10:00"
        echo "updated_at: 2026-04-21 10:00"
        echo "---"
        echo
        echo "Body."
        echo
        echo "## Verification Checklist"
        echo
        echo "- [defer] deferred item preserved in carry-over"
        echo "- [x] terminal item stays behind"
    } > aitasks/t200_verify.md
    git add -A && git commit -m "setup" --quiet

    local output rc=0
    set +e
    output=$(bash .aitask-scripts/aitask_archive.sh --with-deferred-carryover 200 2>&1)
    rc=$?
    set -e

    assert_eq_trim "archive exits 0" "0" "$rc"
    assert_contains "CARRYOVER_CREATED emitted" "CARRYOVER_CREATED:" "$output"

    local carryover_file
    carryover_file="$(ls aitasks/t*_verify_carryover.md 2>/dev/null | head -1 || true)"

    TOTAL=$((TOTAL + 1))
    if [[ -z "$carryover_file" ]]; then
        FAIL=$((FAIL + 1))
        echo "FAIL: carry-over task file not created"
        echo "  out: $output"
    else
        PASS=$((PASS + 1))
        # create_carryover_task gives the new task a FRESH created_at, which is
        # exactly why the baseline is a field of its own — resetting it would
        # make the staleness check measure from the wrong commit.
        assert_eq "carry-over inherits the baseline verbatim" \
            "$value" "$(read_fm_field "$carryover_file" verification_baseline)"
    fi

    teardown_update_project
}

# =============================================================================
# Section D — post-phase risk mitigation: assert_allowlist_coverage
# =============================================================================

test_helper_is_in_every_invocation_allowlist() {
    echo "=== D(post-phase): the helper is whitelisted on every agent surface ==="
    # An unwhitelisted helper does not fail — it STALLS the consuming procedure
    # on a permission prompt, which is invisible until someone runs it.
    local f
    for f in \
        ".claude/settings.local.json" \
        "seed/claude_settings.local.json" \
        "seed/opencode_config.seed.json" \
        ".codex/rules/default.rules" \
        "seed/codex_rules.default.rules"
    do
        TOTAL=$((TOTAL + 1))
        if grep -q "aitask_verification_stale.sh" "$PROJECT_DIR/$f" 2>/dev/null; then
            PASS=$((PASS + 1))
        else
            FAIL=$((FAIL + 1))
            echo "FAIL: aitask_verification_stale.sh missing from allowlist $f"
        fi
    done
}

# --- Run ---------------------------------------------------------------------

echo "=== test_verification_stale.sh ==="
echo ""

cd "$PROJECT_DIR"

test_modified_file_is_ask_stale
test_deleted_file_is_detected_by_probe_not_history
test_mixed_changed_deleted_untouched
test_invalid_scope_entry_is_never_fresh
test_mixed_valid_and_invalid_scope
test_negative_control_all_untouched_is_fresh
test_dirty_worktree_is_not_a_change
test_delimiter_in_path_is_encoded
test_percent_encoding_is_lossless
test_glob_chars_in_path_do_not_match_neighbours
test_glob_chars_do_not_contaminate_real_evidence
test_deleted_glob_path_names_its_own_culprit
test_ranged_reference_unchanged_is_fresh
test_ranged_reference_changed_reports_stripped_path
test_multi_range_reference_is_stripped
test_duplicate_ranges_of_one_file_dedupe
test_precondition_skips
test_outside_a_git_repository_skips
test_baseline_advance_stops_the_prompt

test_setter_round_trip
test_setter_does_not_materialize_absent_fields
test_baseline_survives_parent_rewrite_path
test_every_write_task_file_call_site_is_wired

test_carryover_inherits_baseline

test_helper_is_in_every_invocation_allowlist

for dir in "${CLEANUP_DIRS[@]}"; do
    rm -rf "$dir"
done

echo ""
echo "=== Results ==="
echo "Total:  $TOTAL"
echo "Pass:   $PASS"
echo "Fail:   $FAIL"

if [[ $FAIL -eq 0 ]]; then
    echo "PASS"
    exit 0
else
    echo "FAIL"
    exit 1
fi
