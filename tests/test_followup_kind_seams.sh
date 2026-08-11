#!/usr/bin/env bash
# test_followup_kind_seams.sh - every auto-spawned-follow-up creation seam sets
# `--followup-kind` (t1468_2).
#
# The rendering sweep proves nothing on its own: a seam that silently omits the
# flag still renders consistently and keeps aitask_skill_verify.sh green. This
# suite is the thing that fails when a seam is missed.
#
# Structure: three hand-authored disposition tables (one per creation surface),
# each diffed against a set DERIVED FROM THE TREE at run time. The tables are
# constants and the derived sets are not, so the diff can genuinely fail in both
# directions -- a new seam nobody dispositioned, or a table row whose file went
# away.
#
# Discovery is EXECUTION-ONLY, not mention-based. A generic mention of "Batch
# Task Creation Procedure" / aitask_create.sh also occurs in the procedure's own
# definition, in cross-references and in CLI flag documentation; scanning for
# mentions both fires on legitimate documentation and hides real seams behind a
# fuzzy "it's just a doc reference" disposition. The narrow dispatch-shaped
# predicates below drop all six mention-only files by themselves.
#
# Run: bash tests/test_followup_kind_seams.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

. "$PROJECT_DIR/tests/lib/asserts.sh"

cd "$PROJECT_DIR"

# --- discovery predicates ---------------------------------------------------
#
# Rendered per-profile variants live in directories whose NAME ends in '-'
# (task-workflow-fast-, aitask-review-remote-codex-, ...). Excluding a path
# component that ends in '-' drops all of them without a hand-maintained list.

skill_sources() {
    find .claude/skills -type f \( -name '*.md' -o -name '*.md.j2' \) 2>/dev/null \
        | grep -v -E '/[^/]+-/' \
        | LC_ALL=C sort
}

# P1 - a skill file that DISPATCHES the shared procedure.
P1_RE='(Execute|execute|via) the \*\*Batch Task Creation Procedure\*\*'
derive_p1() {
    skill_sources | while read -r f; do
        if grep -qE "$P1_RE" "$f"; then echo "${f#.claude/skills/}"; fi
    done
}

# P2 - a skill file carrying a real inline `aitask_create.sh ... --batch`
# COMMAND LINE (leading path, not a prose mention of the script name).
P2_RE='^[[:space:]]*\./\.aitask-scripts/aitask_create\.sh .*--batch'
derive_p2() {
    skill_sources | while read -r f; do
        if grep -qE "$P2_RE" "$f"; then echo "${f#.claude/skills/}"; fi
    done
}

# P3 - a framework script that INVOKES aitask_create.sh on a non-comment line.
# (Comment-only mentions in aitask_claim_id.sh / aitask_gate.sh / aitask_labels.sh
# / aitask_project_resolve.sh / aitask_update.sh are correctly excluded.)
# Single awk predicate rather than `grep -v … | grep -q …`: grep -q exits at its
# first match and closes the pipe, so the upstream grep dies on SIGPIPE and
# prints "grep: write error: Broken pipe" to stderr. The pipeline still returns
# success, so the noise would ride along invisibly under a green result.
derive_p3() {
    for f in .aitask-scripts/*.sh; do
        if awk '
            /^[[:space:]]*#/ { next }
            /aitask_create\.sh["[:space:]]/ { found = 1; exit }
            END { exit !found }
        ' "$f"; then
            echo "${f#.aitask-scripts/}"
        fi
    done | LC_ALL=C sort
}

# --- disposition tables -----------------------------------------------------
#
# Columns: <key>|<expectation>|<kind_count>|<followup_of_count>
#
#   expectation   a followup kind, or a marker:
#                   NONE     - genuine new work; MUST carry no followup_kind
#                   TEMPLATE - the shared contract; carries the emission placeholder
#                   FLAGDOC  - the CLI flag reference surface; documents, never emits
#                   SINK     - aitask_create.sh itself
#   kind_count    exact expected occurrences of the kind literal ('-' = unchecked)
#   followup_of_count
#                 exact expected occurrences of 'followup_of:' ('-' = unchecked)
#
# followup_of is pinned alongside the kind because the anchor parameter is just
# as load-bearing: an edit that adds the kind to upstream-followup.md but drops
# the anchor leaves upstream-defect follow-ups as topic roots, invisible in the
# board's By-Topic view -- and a kind-only table would pass.

P1_TABLE='task-workflow/risk-mitigation-followup.md|risk_mitigation|2|2
task-workflow/upstream-followup.md|upstream_defect|1|1
aitask-qa/follow-up-task-creation.md|qa_test_gap|2|1
aitask-review/SKILL.md.j2|review_finding|3|1
task-workflow/planning.md|NONE|0|-
aitask-explore/SKILL.md.j2|NONE|0|-
aitask-wrap/SKILL.md.j2|NONE|0|-
aitask-pr-import/SKILL.md.j2|NONE|0|-
aitask-revert/SKILL.md.j2|NONE|0|-'

# aitask-qa's followup_of count is 1, not 2: the CHILD branch must not pass it
# (mutually exclusive with --parent), only the standalone parent branch does.
# aitask-review's single occurrence is the conditional guidance line ("Only pass
# followup_of: <reviewed_task_id> when the review clearly stems from one task"),
# not a dispatch parameter -- reviews are topic roots by design.

P2_TABLE='aitask-docs-gap/SKILL.md|docs_gap|1|-
task-workflow/task-creation-batch.md|TEMPLATE|-|-
aitask-create/SKILL.md|FLAGDOC|-|-
task-workflow/cross-repo-child-assignment.md|NONE|0|-'

P3_TABLE='aitask_archive.sh|carry_over|1|-
aitask_create_manual_verification.sh|manual_verification|1|-
aitask_verification_followup.sh|verification_failure|1|-
aitask_create.sh|SINK|-|-
aitask_issue_import.sh|NONE|0|-
aitask_pr_import.sh|NONE|0|-'

table_keys() { printf '%s\n' "$1" | cut -d'|' -f1 | LC_ALL=C sort; }

# Backticks are stripped before matching. The seam files disagree about markdown
# convention -- upstream-followup.md backticks its parameter KEYS
# (`followup_kind`: `upstream_defect`), aitask-qa and aitask-review backtick only
# the values (followup_kind: `qa_test_gap`), risk-mitigation-followup.md wraps
# the whole pair (`followup_of: <task_id>`). Normalising here keeps the assertion
# about the parameter being passed rather than about each file's house style,
# which is what actually matters to the renderer and the reader.
count_fixed() { # count_fixed <file> <fixed-string, backtick-free>
    tr -d '`' < "$1" 2>/dev/null | grep -c -F -- "$2" || true
}

# Domain-local: asserts against a FILE rather than a captured string. The shared
# assert_contains echoes its haystack on failure, which for a whole skill file
# buries the one line that matters under several hundred lines of skill prose.
assert_file_contains() { # assert_file_contains <desc> <file> <needle, backtick-free>
    TOTAL=$((TOTAL + 1))
    if [[ ! -f "$2" ]]; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $1 (missing file: $2)"
    elif tr -d '`' < "$2" | grep -qF -- "$3"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $1 ($2 does not contain '$3')"
    fi
}

# === Test 1: exhaustiveness — derived call-site sets == table key sets =======
#
# This is the assertion that makes the tables a guard rather than a checklist.

echo "=== Test 1: discovery predicates match the disposition tables ==="

for spec in "P1:$(derive_p1 | LC_ALL=C sort):$(table_keys "$P1_TABLE"):9" \
            "P2:$(derive_p2 | LC_ALL=C sort):$(table_keys "$P2_TABLE"):4" \
            "P3:$(derive_p3):$(table_keys "$P3_TABLE"):6"; do
    name="${spec%%:*}"
    rest="${spec#*:}"
    derived="${rest%%:*}"; rest="${rest#*:}"
    expected="${rest%:*}"
    pinned="${rest##*:}"

    assert_eq "$name derived call-site set == table keys" "$expected" "$derived"

    # Cardinality pin: a predicate that silently stops matching (a reworded
    # dispatch sentence, a moved script) would otherwise produce two empty sets
    # that compare equal -- a vacuously satisfied diff.
    actual_n=$(printf '%s\n' "$derived" | grep -c . || true)
    assert_eq "$name derived set size is the pinned $pinned" "$pinned" "$actual_n"
done

# === Test 2: per-seam kind and anchor expectations ===========================

echo "=== Test 2: per-seam followup_kind / followup_of expectations ==="

# Fed by process substitution, never a pipeline: a `printf | while` loop runs in
# a subshell, so every PASS/FAIL/TOTAL increment inside it would be discarded and
# the suite would report 0 assertions while looking healthy.
check_rows() { # check_rows <table> <path-prefix> <kind-literal-prefix>
    local table="$1" prefix="$2" kindpfx="$3"
    local key exp kn fn file n
    while IFS='|' read -r key exp kn fn; do
        [[ -z "$key" ]] && continue
        file="${prefix}${key}"

        if [[ ! -f "$file" ]]; then
            FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
            echo "FAIL: table row names a missing file: $file"
            continue
        fi

        case "$exp" in
            NONE)
                n=$(count_fixed "$file" "followup_kind")
                assert_eq "$key creates genuine new work — no followup_kind" "0" "$n"
                ;;
            TEMPLATE)
                assert_file_contains "$key carries the emission placeholder" \
                    "$file" '--followup-kind "<followup_kind>"'
                ;;
            FLAGDOC|SINK)
                : # in the table for exhaustiveness only
                ;;
            *)
                n=$(count_fixed "$file" "${kindpfx}${exp}")
                assert_eq "$key emits ${kindpfx}${exp} exactly $kn time(s)" "$kn" "$n"
                ;;
        esac

        if [[ "$fn" != "-" ]]; then
            n=$(count_fixed "$file" "followup_of:")
            assert_eq "$key references followup_of: exactly $fn time(s)" "$fn" "$n"
        fi
    done < <(printf '%s\n' "$table")
}

check_rows "$P1_TABLE" ".claude/skills/" "followup_kind: "
check_rows "$P2_TABLE" ".claude/skills/" "--followup-kind "
check_rows "$P3_TABLE" ".aitask-scripts/" "--followup-kind "

# === Test 3: vocabulary coverage — every kind has an emitter ================
#
# Reads the vocabulary through the sanctioned shell bridge rather than
# re-parsing followup_kinds.py, so the two cannot drift.

echo "=== Test 3: every followup kind has at least one emitting seam ==="

# shellcheck source=.aitask-scripts/lib/followup_kinds_sh.sh
. "$PROJECT_DIR/.aitask-scripts/lib/followup_kinds_sh.sh"
ALL_KINDS="$(followup_kinds_pipe | tr '|' '\n')"
ALL_EXPECTATIONS="$(printf '%s\n%s\n%s\n' "$P1_TABLE" "$P2_TABLE" "$P3_TABLE" | cut -d'|' -f2)"

if [[ -z "$ALL_KINDS" ]]; then
    FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
    echo "FAIL: could not resolve the followup-kind vocabulary (bridge failed closed)"
else
    for kind in $ALL_KINDS; do
        assert_contains "vocabulary kind '$kind' is emitted by some seam" \
            "$kind" "$ALL_EXPECTATIONS"
    done
fi

# === Test 4: rendered output, targeted per git-tracking status ==============
#
# Only .../task-workflow-remote-/ is un-ignored in .gitignore (lines 66-68), so
# it is the one rendered tree guaranteed to exist in a fresh clone. Those get
# unconditional assertions. aitask-review's rendered variants are untracked, but
# its GOLDENS are tracked and are themselves rendered output -- so the review
# seam is still asserted unconditionally, just through the golden.
#
# The remaining (untracked, may-not-exist) variants are [[ -f ]]-guarded. A
# guarded assertion that silently skips proves nothing, so the number that
# actually executed is counted and a zero count fails when the trees do exist.

echo "=== Test 4: rendered output carries the kind ==="

REMOTE_TREES=".claude/skills/task-workflow-remote-
.agents/skills/task-workflow-remote-codex-
.opencode/skills/task-workflow-remote-"

while read -r tree; do
    [[ -z "$tree" ]] && continue
    if [[ ! -d "$tree" ]]; then
        FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
        echo "FAIL: tracked prerender tree missing: $tree (run aitask_skill_rerender.sh remote)"
        continue
    fi
    assert_file_contains "$tree risk-mitigation-followup renders the kind" \
        "$tree/risk-mitigation-followup.md" "followup_kind: risk_mitigation"
    assert_file_contains "$tree upstream-followup renders the kind" \
        "$tree/upstream-followup.md" "followup_kind: upstream_defect"
    assert_file_contains "$tree upstream-followup renders the anchor" \
        "$tree/upstream-followup.md" "followup_of:"
    assert_file_contains "$tree task-creation-batch renders the emission" \
        "$tree/task-creation-batch.md" '--followup-kind "<followup_kind>"'
done < <(printf '%s\n' "$REMOTE_TREES")

for profile in default fast remote; do
    golden="tests/golden/skills/aitask-review/SKILL-${profile}-claude.md"
    if [[ ! -f "$golden" ]]; then
        FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
        echo "FAIL: tracked golden missing: $golden"
        continue
    fi
    n=$(count_fixed "$golden" "followup_kind: review_finding")
    assert_eq "aitask-review golden ($profile) carries the kind at all 3 sites" "3" "$n"
done

# Guarded, untracked variants — with the non-vacuity counter.
GUARDED_RUN=0
GUARDED_AVAILABLE=0

guarded_assert() { # guarded_assert <file> <needle> <desc>
    if [[ -e "$(dirname "$1")" ]]; then
        GUARDED_AVAILABLE=$((GUARDED_AVAILABLE + 1))
    fi
    if [[ -f "$1" ]]; then
        GUARDED_RUN=$((GUARDED_RUN + 1))
        assert_file_contains "$3" "$1" "$2"
    fi
}

guarded_assert ".claude/skills/task-workflow-fast-/task-creation-batch.md" \
    '--followup-kind "<followup_kind>"' "fast variant renders the emission"
guarded_assert ".claude/skills/task-workflow-fast-/upstream-followup.md" \
    "followup_kind: upstream_defect" "fast variant renders the upstream kind"
guarded_assert ".claude/skills/aitask-qa-fast-/follow-up-task-creation.md" \
    "followup_kind: qa_test_gap" "qa fast variant renders the kind"
guarded_assert ".claude/skills/aitask-review-fast-/SKILL.md" \
    "followup_kind: review_finding" "review fast variant renders the kind"

if [[ "$GUARDED_AVAILABLE" -gt 0 ]]; then
    TOTAL=$((TOTAL + 1))
    if [[ "$GUARDED_RUN" -gt 0 ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $GUARDED_AVAILABLE rendered tree(s) exist but 0 guarded assertions ran — the suite would have reported green having asserted nothing"
    fi
else
    echo "  (no untracked rendered variants present — guarded assertions skipped)"
fi

# --- summary ---------------------------------------------------------------

echo
echo "Results: $PASS passed, $FAIL failed (of $TOTAL)"
if [[ "$FAIL" -eq 0 ]]; then
    echo "PASS: test_followup_kind_seams.sh"
    exit 0
else
    echo "FAIL: test_followup_kind_seams.sh"
    exit 1
fi
