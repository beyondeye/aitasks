#!/usr/bin/env bash
# test_docs_vocabulary_coverage.sh - Drift guard for the two hand-maintained
# vocabularies that document the task frontmatter (t1666).
#
# Drives tests/lib/docs_vocabulary_scan.py, which enforces:
#
#   A  seed/task_types.txt is in sync with aitasks/metadata/task_types.txt
#   B  every site that enumerates issue_type carries exactly its declared set
#      (FULL / NO_MV / DETECTED) -- extracted from the enumeration itself, so a
#      NO_MV site is free to explain in prose why manual_verification is absent
#   C  every site anchor matches exactly one line, and every extraction yields
#      a non-empty set (the tripwire: a renamed heading must fail loudly rather
#      than silently reduce a site to checking nothing)
#   D  the writer-derived frontmatter field set and the website's Frontmatter
#      Fields table are equal, in both directions
#   E  supplemental: no task file carries a frontmatter key no known writer
#      emits
#
# Test 1 runs the scan against the real repository. Tests 2+ are mostly negative
# controls: each mutates one thing in a throwaway fixture and asserts the
# corresponding check flips to FAIL. Without them the scan could be green
# because it checks nothing. Test 12b is the one control in the other direction
# — it asserts the scan still PASSES on a registered key, which is what a fix
# that silenced check E wholesale would break.
#
# The fixture is built from the scanner's own `--list-inputs`, so a site added
# to SITES joins the fixture automatically and cannot silently fall out of the
# negative controls.
#
# Run: bash tests/test_docs_vocabulary_coverage.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

SCAN="$PROJECT_DIR/tests/lib/docs_vocabulary_scan.py"

cleanup() {
    local d
    for d in "${CLEANUP_DIRS[@]}"; do
        [[ -n "$d" && -d "$d" ]] && rm -rf "$d"
    done
}
trap cleanup EXIT

# Run the scanner; echo its output, return its exit status.
run_scan() {
    python3 "$SCAN" --root "$1" 2>&1 || true
}
scan_rc() {
    python3 "$SCAN" --root "$1" >/dev/null 2>&1
}

# Build a throwaway fixture root holding exactly the files the scanner reads,
# plus a two-file task corpus for check E.
make_fixture() {
    local dir rel
    dir="$(mktemp -d)"
    CLEANUP_DIRS+=("$dir")
    while IFS= read -r rel; do
        [[ -n "$rel" ]] || continue
        mkdir -p "$dir/$(dirname "$rel")"
        cp "$PROJECT_DIR/$rel" "$dir/$rel"
    done < <(python3 "$SCAN" --root "$PROJECT_DIR" --list-inputs)
    mkdir -p "$dir/aitasks"
    cat > "$dir/aitasks/t1_sample.md" <<'EOF'
---
priority: medium
effort: low
issue_type: feature
status: Ready
labels: [docs]
created_at: 2026-01-01 00:00
updated_at: 2026-01-01 00:00
---

Sample task.
EOF
    printf '%s\n' "$dir"
}

# --------------------------------------------------------------------------
# Test 1 - the real repository is clean
# --------------------------------------------------------------------------
test_live_repo_is_clean() {
    echo "=== Test 1: live repository passes every check ==="
    local out
    out="$(run_scan "$PROJECT_DIR")"
    if scan_rc "$PROJECT_DIR"; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: live repo failed the vocabulary scan:"
        echo "$out"
    fi
    assert_contains "live scan reports both dimensions" "issue_type sites" "$out"
}

# --------------------------------------------------------------------------
# Test 2 - the fixture reproduces the clean result
#
# A negative control is only meaningful against a baseline that passes: if the
# fixture were already failing, every mutation below would "fail" for free.
# --------------------------------------------------------------------------
FIXTURE=""
test_fixture_baseline_is_clean() {
    echo "=== Test 2: unmutated fixture passes (negative-control baseline) ==="
    FIXTURE="$(make_fixture)"
    local out
    out="$(run_scan "$FIXTURE")"
    if scan_rc "$FIXTURE"; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: unmutated fixture did not pass — controls below are void:"
        echo "$out"
    fi
}

# Mutate a fresh fixture, assert the scan fails and names the expected check.
# Each control gets its own fixture, so a mutation can never leak into the next.
assert_control() {
    local desc="$1" expect_tag="$2" mutate_fn="$3"
    local dir out
    dir="$(make_fixture)"
    "$mutate_fn" "$dir"
    out="$(run_scan "$dir")"
    if scan_rc "$dir"; then
        assert_record_fail
        echo "FAIL: $desc — scan still passed after the mutation (check is vacuous)"
    else
        assert_record_pass
    fi
    assert_contains "$desc names $expect_tag" "$expect_tag" "$out"
}

# The mirror of assert_control: mutate a fresh fixture and assert the scan still
# PASSES. A negative control proves a check can fail; this proves it does not
# fire on input it is supposed to accept -- the direction that catches a fix
# which silences the diagnostic wholesale.
assert_positive_control() {
    local desc="$1" mutate_fn="$2"
    local dir out
    dir="$(make_fixture)"
    "$mutate_fn" "$dir"
    out="$(run_scan "$dir")"
    if scan_rc "$dir"; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: $desc — scan failed on input it should accept:"
        echo "$out"
    fi
}

# --------------------------------------------------------------------------
# Test 3 - check A: seed vocabulary drifts from the live one
# --------------------------------------------------------------------------
mutate_seed_vocabulary() {
    grep -v '^manual_verification$' "$1/seed/task_types.txt" > "$1/seed/task_types.txt.tmp"
    mv "$1/seed/task_types.txt.tmp" "$1/seed/task_types.txt"
}
test_control_vocabulary_sync() {
    echo "=== Test 3: control — seed/task_types.txt drift is caught ==="
    assert_control "seed drift" "A/vocabulary-sync" mutate_seed_vocabulary
}

# --------------------------------------------------------------------------
# Test 4 - check B: a site drops a value
# --------------------------------------------------------------------------
mutate_drop_value_from_site() {
    local f="$1/website/content/docs/development/task-format.md"
    sed -i.bak 's/^| `issue_type` | `bug`, `chore`, `documentation`, `enhancement`, `feature`, `manual_verification`,/| `issue_type` | `bug`, `chore`, `documentation`, `enhancement`, `feature`,/' "$f"
    rm -f "$f.bak"
}
test_control_site_missing_value() {
    echo "=== Test 4: control — a site dropping a value is caught ==="
    assert_control "dropped issue_type value" "B/site" mutate_drop_value_from_site
}

# --------------------------------------------------------------------------
# Test 5 - check B, other direction: a NO_MV site enumerates the excluded value
#
# This is the control that proves the extraction is doing real work. The
# rationale sentence at every NO_MV site already contains the word
# manual_verification; only adding it to the *enumeration* may fail.
# --------------------------------------------------------------------------
mutate_no_mv_site_gains_value() {
    local f="$1/CLAUDE.md"
    sed -i.bak 's/`style`, `test`\. Also `ait` for/`style`, `test`, `manual_verification`. Also `ait` for/' "$f"
    rm -f "$f.bak"
}
test_control_no_mv_site_gains_value() {
    echo "=== Test 5: control — a NO_MV site enumerating manual_verification is caught ==="
    assert_control "NO_MV site gained the excluded value" "B/site" mutate_no_mv_site_gains_value
}

# --------------------------------------------------------------------------
# Test 6 - check B is NOT fooled by the rationale prose
#
# The positive half of Test 5: the live CLAUDE.md already says the word
# "manual_verification" in the sentence right under its commit-type list, and
# that must not count as enumerating it.
# --------------------------------------------------------------------------
test_rationale_prose_does_not_count() {
    echo "=== Test 6: rationale prose naming the excluded value does not fail the site ==="
    local body
    body="$(cat "$PROJECT_DIR/CLAUDE.md")"
    assert_contains "CLAUDE.md explains the exclusion in prose" \
        "there is no" "$body"
    assert_contains "CLAUDE.md names manual_verification in that prose" \
        '`manual_verification:` commit type' "$body"
    # Test 1 already asserted the whole scan passes with that prose present.
}

# --------------------------------------------------------------------------
# Test 7 - check C: a renamed anchor
# --------------------------------------------------------------------------
mutate_rename_anchor() {
    local f="$1/website/content/docs/development/task-format.md"
    sed -i.bak 's/^## Customizing Task Types$/## Customising Task Types/' "$f"
    rm -f "$f.bak"
}
test_control_anchor_tripwire() {
    echo "=== Test 7: control — a renamed anchor fails loudly ==="
    assert_control "renamed anchor" "C/anchor" mutate_rename_anchor
}

# --------------------------------------------------------------------------
# Test 8 - check C: a reworded list whose extraction yields nothing
# --------------------------------------------------------------------------
mutate_reword_list_away() {
    local f="$1/.claude/skills/aitask-docs-gap/SKILL.md"
    sed -i.bak 's/^  - `ISSUE_TYPE:` — task type (.*)$/  - `ISSUE_TYPE:` — task type, see task_types.txt/' "$f"
    rm -f "$f.bak"
}
test_control_extraction_tripwire() {
    echo "=== Test 8: control — a reworded list that extracts nothing fails ==="
    assert_control "reworded away" "C/extract" mutate_reword_list_away
}

# --------------------------------------------------------------------------
# Test 9 - check D: a writable field with no table row
#
# The zero-instance case the corpus can never see: the field is added to a
# writer and to no task file at all.
# --------------------------------------------------------------------------
mutate_add_undocumented_writer_field() {
    local f="$1/.aitask-scripts/aitask_update.sh"
    printf '\n# fixture-only writer emission\n_fixture() { echo "brand_new_field: x"; }\n' >> "$f"
}
test_control_zero_instance_field() {
    echo "=== Test 9: control — a zero-instance writable field with no row is caught ==="
    assert_control "undocumented zero-instance field" "D/field-coverage" \
        mutate_add_undocumented_writer_field
}

# --------------------------------------------------------------------------
# Test 10 - check D, other direction: a documented field loses its writer
#
# Deletes the `attachments` row — the field that has zero on-disk instances and
# is therefore invisible to any corpus-derived check. This is the control that
# distinguishes the writer-derived source from a corpus scan.
# --------------------------------------------------------------------------
mutate_delete_zero_instance_row() {
    local f="$1/website/content/docs/development/task-format.md"
    grep -v '^| `attachments` |' "$f" > "$f.tmp"
    mv "$f.tmp" "$f"
}
test_control_zero_instance_row_removal() {
    echo "=== Test 10: control — deleting the row of a zero-instance field is caught ==="
    assert_control "deleted attachments row" "D/field-coverage" \
        mutate_delete_zero_instance_row
}

# --------------------------------------------------------------------------
# Test 11 - check D: a new frontmatter_patch.py caller
# --------------------------------------------------------------------------
mutate_add_patch_caller() {
    mkdir -p "$1/.aitask-scripts"
    cat > "$1/.aitask-scripts/aitask_fixture_writer.sh" <<'EOF'
#!/usr/bin/env bash
python3 lib/frontmatter_patch.py append "$task_file" widgets "k=v"
EOF
}
test_control_new_patch_caller() {
    echo "=== Test 11: control — a new nested-field writer is caught ==="
    assert_control "new frontmatter_patch caller" "D/patch-callers" mutate_add_patch_caller
}

# --------------------------------------------------------------------------
# Test 12 - check E: a task file carrying an unknown key
# --------------------------------------------------------------------------
mutate_corpus_unknown_key() {
    local f="$1/aitasks/t1_sample.md"
    sed -i.bak 's/^status: Ready$/status: Ready\nmystery_key: 1/' "$f"
    rm -f "$f.bak"
}
test_control_corpus_unknown_key() {
    echo "=== Test 12: control — an unknown key on disk is reported ==="
    assert_control "unknown corpus key" "E/corpus" mutate_corpus_unknown_key
}

# --------------------------------------------------------------------------
# Test 12b - check E, positive control: a REGISTERED key on disk is accepted
#
# The mirror of Test 12 on the same axis. `archived_reason` is written by
# `ait archive --superseded` and registered in OTHER_WRITERS (t1732); it must
# not be reported as an unknown key. Doing this in the fixture rather than
# leaning on the live corpus matters: the live repo currently proves it via a
# single archived file, and that file will eventually be folded into an
# `old.tar.zst` bundle, taking the coverage with it. Also the only fixture that
# reaches the `aitasks/archived/` arm of the check_corpus_supplemental walk.
# --------------------------------------------------------------------------
mutate_corpus_archived_reason() {
    mkdir -p "$1/aitasks/archived"
    cat > "$1/aitasks/archived/t2_superseded.md" <<'EOF'
---
priority: low
effort: low
issue_type: chore
status: Done
archived_reason: superseded
created_at: 2026-01-01 00:00
updated_at: 2026-01-01 00:00
completed_at: 2026-01-01 00:00
---

Superseded sample task.
EOF
}
test_positive_control_corpus_archived_reason() {
    echo "=== Test 12b: positive control — a registered archived_reason is accepted ==="
    assert_positive_control "registered archived_reason key" \
        mutate_corpus_archived_reason
}

# --------------------------------------------------------------------------
# Test 12c - check D: the archived_reason writer loses its write
#
# What makes the OTHER_WRITERS needle a real guard rather than an assertion
# about itself. The mutation deletes the awk insertion but LEAVES the
# `--superseded` help line, which also contains the string `archived_reason` --
# so this fails only because the registry pins the write expression. A registry
# keyed on the bare field name would stay green here.
# --------------------------------------------------------------------------
mutate_archive_writer_dropped() {
    local f="$1/.aitask-scripts/aitask_archive.sh"
    grep -v 'print "archived_reason: ' "$f" > "$f.tmp"
    mv "$f.tmp" "$f"
    # Two recorded assertions, not a bare `|| echo`: `echo` exits 0, so a
    # warning would let the run continue and the control would still "pass"
    # for the wrong reason. Both are preconditions of what 12c claims to
    # prove, and both must be able to fail the suite.
    #
    # (a) the mutation landed — otherwise D/writers firing would mean
    #     something else entirely;
    assert_not_contains "12c precondition: the awk write is gone" \
        "archived_reason" "$(grep -F 'print "archived_reason: ' "$f" || true)"
    # (b) the *intended* non-write occurrence survived. Checked explicitly on
    #     the `--superseded` help line rather than as "any occurrence
    #     anywhere": that line is what a bare field-name needle would match,
    #     and it is the sole reason this control discriminates. If a later
    #     archive-script refactor drops it, 12c degrades to "the field
    #     vanished entirely" — which any needle catches — and must fail loudly
    #     rather than keep claiming to pin the needle.
    assert_contains "12c precondition: the --superseded help line survives" \
        "archived_reason" "$(grep -- '--superseded' "$f" || true)"
}
test_control_archive_writer_dropped() {
    echo "=== Test 12c: control — dropping the archived_reason write is caught ==="
    assert_control "dropped archived_reason writer" "D/writers" \
        mutate_archive_writer_dropped
}

# --------------------------------------------------------------------------
# Test 13 - the scanner itself parses
# --------------------------------------------------------------------------
test_syntax_check() {
    echo "=== Test 13: scanner compiles, test file parses ==="
    if python3 -m py_compile "$SCAN" 2>/dev/null; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: $SCAN does not compile"
    fi
    if bash -n "$SCRIPT_DIR/test_docs_vocabulary_coverage.sh" 2>/dev/null; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: test file has a syntax error"
    fi
}

test_live_repo_is_clean
test_fixture_baseline_is_clean
test_control_vocabulary_sync
test_control_site_missing_value
test_control_no_mv_site_gains_value
test_rationale_prose_does_not_count
test_control_anchor_tripwire
test_control_extraction_tripwire
test_control_zero_instance_field
test_control_zero_instance_row_removal
test_control_new_patch_caller
test_control_corpus_unknown_key
test_positive_control_corpus_archived_reason
test_control_archive_writer_dropped
test_syntax_check

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
