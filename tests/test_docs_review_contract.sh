#!/usr/bin/env bash
# test_docs_review_contract.sh - Static contract test for the docs_updated gate's
# review wiring and the aitask-docs-review procedure (t2258_2).
#
# Covers (parent plan t2258, decisions 2, 3, 5, 6):
#   - the gate drafts complete .draft/.base files (step 3), reviews them in a
#     step 3b between steps 3 and 4, re-reviews after Adjust and reconciliation;
#   - step 5 names the five destination states, runs git merge-file only in the
#     "modified" row, treats exit statuses outside 0-127 as an error that applies
#     nothing, sends created/deleted pages back to step 3, merges from a snapshot
#     and rebaselines .base from that snapshot (never a fresh read);
#   - the fresh-reader budget: 3 per gate run, written once per run id, cumulative
#     across re-reviews and step-3 re-entry, most-changed-first, extended only by
#     the user's explicit choice and never in autonomous profiles;
#   - a page already in the run keeps its .base (moved facts reuse its draft),
#     a deleted page the user recreates drops its stale .base, and a move
#     deletes the source pair only after the destination draft is saved;
#   - the step-6 log names reader= with all six values;
#   - the review skill resolves the guide via the config resolver, reads the guide
#     only through `## Reader levels`, copies none of the guide's prose-rule
#     bullets, and skips level check + fresh-reader without a level model.
#
# Controls (each check is shown to be able to fail):
#   - every gate check (G_*) fails against the gate text before this task, read
#     from a pinned commit;
#   - every skill check (S_*) fails against a missing skill, and the targeted
#     ones fail against a mutant of the real skill.
#
# Run: bash tests/test_docs_review_contract.sh
# shellcheck disable=SC2016  # needles are literal markdown (backticks, $drafts)
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/fixture_root.sh"

PASS=0; FAIL=0; TOTAL=0
CLEANUP_DIRS=()
cleanup() { local d; for d in "${CLEANUP_DIRS[@]+"${CLEANUP_DIRS[@]}"}"; do rm -rf "$d"; done; }
trap cleanup EXIT

GATE_REL=".claude/skills/aitask-gate-docs-updated/SKILL.md"
GATE="$PROJECT_DIR/$GATE_REL"
SKILL="$PROJECT_DIR/.claude/skills/aitask-docs-review/SKILL.md"
GUIDE="$PROJECT_DIR/aitasks/metadata/doc_update_guide.md"
# Last commit of the gate skill before t2258_2 wired the review in.
PRE_CHANGE_SHA="9baf1dcb491493f7a0796ed4af94f399ae8f1e82"

# sec <file> <heading-regex> — print the section that starts at the first line
# matching <heading-regex>, up to (not including) the next `## `/`### ` heading.
sec() {
    awk -v re="$2" '
        f && /^##+ / { exit }
        !f && $0 ~ re { f = 1 }
        f { print }
    ' "$1" 2>/dev/null
}

# has <text> <needle> — fixed-string containment.
has() { grep -qF -- "$2" < <(printf '%s' "$1"); }

# line_of <file> <regex> — first matching line number, or empty.
line_of() { grep -nE -- "$2" "$1" 2>/dev/null | head -n1 | cut -d: -f1; }

out_check() { if [[ "$2" == 1 ]]; then echo "CHECK:$1:ok"; else echo "CHECK:$1:fail"; fi; }

# all_of <text> <needle>... — 1 when every needle is present.
all_of() {
    local t="$1" n; shift
    for n in "$@"; do has "$t" "$n" || { echo 0; return; }; done
    echo 1
}

# --------------------------------------------------------------------------
# check_gate <gate_file> — one CHECK:G_*:ok|fail line per gate-text check.
# --------------------------------------------------------------------------
check_gate() {
    local g="$1" s3 s3b s4 s5 s6 l3 l3b l4 ok row rows_ok
    s3="$(sec "$g" '^### 3\. ')"
    s3b="$(sec "$g" '^### 3b\. ')"
    s4="$(sec "$g" '^### 4\. ')"
    s5="$(sec "$g" '^### 5\. ')"
    s6="$(sec "$g" '^### 6\. ')"

    # Review step sits between step 3 and step 4.
    l3="$(line_of "$g" '^### 3\. ')"; l3b="$(line_of "$g" '^### 3b\. ')"; l4="$(line_of "$g" '^### 4\. ')"
    ok=0
    if [[ -n "$l3" && -n "$l3b" && -n "$l4" ]] && (( l3 < l3b && l3b < l4 )); then ok=1; fi
    out_check G_review_step_between_3_and_4 "$ok"
    out_check G_review_runs_doc_review_skill "$(all_of "$s3b" '.claude/skills/aitask-docs-review/SKILL.md' '--caller gate')"

    # Step 3: complete drafts plus a .base taken first, drafted from the .base.
    out_check G_step3_writes_draft_and_base "$(all_of "$s3" 'docs_updated_<run-id>_drafts' '<page path>.draft' '<page path>.base' 'complete')"
    out_check G_step3_drafts_from_base_copy "$(all_of "$s3" '**first** copy the page' 'from the `.base` copy')"

    # Budget: written once per run id; re-entry keeps it; cumulative; ordering.
    out_check G_budget_written_once_per_run "$(all_of "$s3" '[ -f "$drafts/.reader_budget" ] || echo 3' 'only when the file does not exist yet' 'never resets it')"
    out_check G_budget_cumulative_most_changed "$(all_of "$s3b" '**3 per gate run, cumulative across every review' 'pages returned to step 3' 'most changed body lines first' 'reader=not-run(cap)')"
    out_check G_budget_extend_explicit_only "$(all_of "$s4" 'Run more fresh-reader tests' 'explicit authorization' 'never ask this and never' 'extend the budget')"

    # Step 4: reader report shown; Adjust re-reviews.
    out_check G_confirm_shows_review "$(all_of "$s4" 'reader report' 'unresolved problems' 'remaining fresh-reader budget' 'has no level model')"
    out_check G_adjust_rereviews "$(all_of "$s4" '**Adjust** — revise the drafts' 're-run step 3b on the' 'changed pages')"

    # Step 5: five states, one row each.
    out_check G_five_destination_states "$(all_of "$s5" '| unchanged |' '| unchanged (new page) |' '| modified by another session |' '| created by another session |' '| deleted by another session |')"

    # git merge-file: invoked only in step 5, named in the modified row, never in
    # the created/deleted rows.
    ok=0
    local total in5 modrow crrow delrow
    # Count invocations (`git merge-file -p`), not prose mentions such as the
    # MUST NOT list's "a `git merge-file` error".
    total="$(grep -c -- 'git merge-file -p' "$g" 2>/dev/null || true)"
    in5="$(printf '%s\n' "$s5" | grep -c -- 'git merge-file -p' || true)"
    modrow="$(printf '%s\n' "$s5" | grep -F -- '| modified by another session |')"
    crrow="$(printf '%s\n' "$s5" | grep -F -- '| created by another session |')"
    delrow="$(printf '%s\n' "$s5" | grep -F -- '| deleted by another session |')"
    if [[ "${total:-0}" -ge 1 && "$total" == "$in5" ]] \
        && has "$modrow" 'git merge-file' \
        && [[ -n "$crrow" && -n "$delrow" ]] \
        && ! has "$crrow" 'merge-file' && ! has "$delrow" 'merge-file' \
        && has "$s5" '`git merge-file` runs only in this row'; then ok=1; fi
    out_check G_merge_file_only_in_modified "$ok"

    rows_ok=1
    for row in "$crrow" "$delrow"; do
        if [[ -z "$row" ]] || ! has "$row" 'apply nothing for this page' || ! has "$row" 'back to step 3'; then rows_ok=0; fi
    done
    out_check G_created_deleted_back_to_step3 "$rows_ok"

    out_check G_merge_rc_handling "$(all_of "$s5" '`1`–`127`' 'no conflict markers' 'an **error, not a reconciliation**' 'apply nothing for this page')"
    out_check G_merge_from_snapshot_rebaseline "$(all_of "$s5" 'git merge-file -p "$drafts/<page path>.snapshot"' 'Merge **from the snapshot**' '**the snapshot becomes the new `.base`**' 'Never re-copy the live page')"
    out_check G_reconciled_rereviewed "$(all_of "$s5" 'goes back through step 3b' 'and step 4 before anything is written')"
    out_check G_existing_pair_keeps_base "$(all_of "$s3" '**A page that already has a draft in this run keeps its `.base`.**' 'never by' 're-copying the live page')"
    out_check G_deleted_choice_transitions "$(all_of "$s5" '**Recreate the page:** delete `"$drafts/<page path>.base"`' 'applies through the "unchanged (new page)"' '**Move the change to another page:** **first** put the change into the other' '**Only' 'then** delete this page' 'keep this page' 'stays pending in the' '**Drop it:** delete this page' 'budget is unchanged in every case')"
    out_check G_never_apply_over_changed "$(all_of "$s5" 'Never apply a draft over a destination that is not in an "unchanged" row')"

    # Step 6 log: reader= with all six values.
    out_check G_log_reader_six_values "$(all_of "$s6" 'reader=' 'level=' 'prose=' 'unresolved=' '`subagent`' '`self-review`' '`not-run(not-beginner)`' '`not-run(untagged)`' '`not-run(cap)`' '`not-run(no-level-model)`')"
}

# --------------------------------------------------------------------------
# check_skill <skill_file> <guide_file> — one CHECK:S_*:ok|fail line each.
# --------------------------------------------------------------------------
check_skill() {
    local sk="$1" gd="$2" body s6 ok h b prefix
    body="$(cat "$sk" 2>/dev/null)"
    s6="$(sec "$sk" '^### Step 6: ')"

    out_check S_resolves_guide_via_resolver "$(all_of "$body" 'aitask_resolve_config_path.sh doc_update.guide' 'aitasks/metadata/doc_update_guide.md')"

    # Interface: `## Reader levels` and its three labels, and no other guide heading.
    ok=0
    if [[ -n "$body" ]] && has "$body" '`## Reader levels`' && has "$body" '`Level field:`' \
        && has "$body" '`Beginner level:`' && has "$body" '`Personas:`'; then
        ok=1
        while IFS= read -r h; do
            [[ "$h" == "## Reader levels" ]] && continue
            if has "$body" "$h"; then ok=0; fi
        done < <(grep -E '^## ' "$gd")
    fi
    out_check S_reader_levels_only_interface "$ok"

    # No duplicated rules: no prose-rules bullet, whole or its first 60 chars.
    ok=0
    if [[ -n "$body" ]]; then
        ok=1
        while IFS= read -r b; do
            b="${b#- }"
            prefix="${b:0:60}"
            if has "$body" "$b" || has "$body" "$prefix"; then ok=0; fi
        done < <(sec "$gd" '^## Prose rules' | grep -E '^- ')
    fi
    out_check S_no_guide_prose_bullets "$ok"

    out_check S_reader_six_values "$(all_of "$body" '`subagent`' '`self-review`' '`not-run(not-beginner)`' '`not-run(untagged)`' '`not-run(cap)`' '`not-run(no-level-model)`')"
    out_check S_budget_rules "$(all_of "$body" 'most changed body lines first' 'never extends its own' 'Every candidate left over gets' '`reader=not-run(cap)`')"
    out_check S_moved_fact_reuses_existing_draft "$(all_of "$body" '**The owning page already has a `.draft` there:**' 'leave its `.base` exactly as it is' 'Never re-copy the live' '**It has no draft yet:**' 'within the budget, Step 4) in this same call')"
    out_check S_fresh_reader_page_text_inline "$(all_of "$body" 'the page text, inline' 'not to open files')"
    out_check S_no_level_model_skips "$(all_of "$s6" 'skip the level check and the fresh-reader test' '`level=not-run(no-level-model)`' '`reader=not-run(no-level-model)`' '`BUDGET_USED:0`')"
}

# expect_all <desc-prefix> <ok|fail> <check output> — one assertion per CHECK line.
expect_all() {
    local prefix="$1" want="$2" out="$3" line name val n=0
    while IFS= read -r line; do
        [[ "$line" == CHECK:* ]] || continue
        n=$((n + 1))
        name="${line#CHECK:}"; val="${name##*:}"; name="${name%:*}"
        assert_eq "$prefix $name" "$want" "$val"
    done < <(printf '%s\n' "$out")
    # A check function that printed nothing must not read as all-clear.
    if [[ "$n" -eq 0 ]]; then assert_eq "$prefix produced checks" "≥1" "0"; fi
}

# expect_one <desc> <check name> <ok|fail> <check output>
expect_one() {
    local got
    got="$(printf '%s\n' "$4" | grep -E "^CHECK:$2:" | head -n1)"
    assert_eq "$1" "CHECK:$2:$3" "$got"
}

# --- 0. preconditions ------------------------------------------------------
assert_file_exists "gate skill present" "$GATE"
assert_file_exists "doc-review skill present" "$SKILL"
assert_file_exists "configured guide present" "$GUIDE"
guide_txt="$(cat "$GUIDE")"
assert_contains "guide declares the level-model interface" "## Reader levels" "$guide_txt"
assert_contains "guide declares the level field" "- Level field:" "$guide_txt"
n_bullets="$(sec "$GUIDE" '^## Prose rules' | grep -cE '^- ' || true)"
assert_contains_re "guide prose-rules section has bullets to compare" '^[1-9][0-9]*$' "$n_bullets"

# --- 1. real files: every check passes -------------------------------------
gate_out="$(check_gate "$GATE")"
skill_out="$(check_skill "$SKILL" "$GUIDE")"
expect_all "gate:" ok "$gate_out"
expect_all "skill:" ok "$skill_out"

fixture_root_init

# --- 2. control: pre-change gate text fails every gate check ---------------
if git -C "$PROJECT_DIR" cat-file -e "$PRE_CHANGE_SHA:$GATE_REL" 2>/dev/null; then
    old_gate="$FIXTURE_ROOT/gate_pre_change.md"
    git -C "$PROJECT_DIR" show "$PRE_CHANGE_SHA:$GATE_REL" > "$old_gate"
    expect_all "control (pre-change gate):" fail "$(check_gate "$old_gate")"
else
    echo "SKIP: pinned pre-change gate $PRE_CHANGE_SHA not in this clone — gate control not run"
fi

# --- 3. control: a missing skill fails every skill check -------------------
expect_all "control (no skill):" fail "$(check_skill "$FIXTURE_ROOT/missing_skill.md" "$GUIDE")"

# --- 4. control: targeted mutants of the real skill ------------------------
mutant() { cp "$SKILL" "$FIXTURE_ROOT/$1.md"; echo "$FIXTURE_ROOT/$1.md"; }

m="$(mutant pasted_bullet)"
sec "$GUIDE" '^## Prose rules' | grep -E '^- ' | head -n1 >> "$m"
expect_one "mutant: a pasted prose-rule bullet is caught" S_no_guide_prose_bullets fail "$(check_skill "$m" "$GUIDE")"

m="$(mutant pasted_prefix)"
b="$(sec "$GUIDE" '^## Prose rules' | grep -E '^- ' | sed -n 2p)"; b="${b#- }"
printf '\nNote: %s\n' "${b:0:60}" >> "$m"
expect_one "mutant: a pasted 60-char bullet prefix is caught" S_no_guide_prose_bullets fail "$(check_skill "$m" "$GUIDE")"

m="$(mutant no_resolver)"
grep -v 'aitask_resolve_config_path.sh' "$SKILL" > "$m"
expect_one "mutant: resolver call removed is caught" S_resolves_guide_via_resolver fail "$(check_skill "$m" "$GUIDE")"

m="$(mutant extra_heading)"
printf '\nAlso read the guide'"'"'s ## Prose rules section by name.\n' >> "$m"
expect_one "mutant: a second guide heading read by name is caught" S_reader_levels_only_interface fail "$(check_skill "$m" "$GUIDE")"

m="$(mutant five_values)"
grep -v 'not-run(cap)' "$SKILL" > "$m"
expect_one "mutant: a missing reader= value is caught" S_reader_six_values fail "$(check_skill "$m" "$GUIDE")"

m="$(mutant moved_fact_recopy)"
grep -v -F -- 'leave its `.base` exactly as it is' "$SKILL" > "$m"
expect_one "mutant: moved fact without keeping the existing .base is caught" S_moved_fact_reuses_existing_draft fail "$(check_skill "$m" "$GUIDE")"

# --- 5. control: targeted mutants of the real gate --------------------------
gmut() { cp "$GATE" "$FIXTURE_ROOT/$1.md"; echo "$FIXTURE_ROOT/$1.md"; }

m="$(gmut merge_in_created_row)"
sed 's/^| no | exists | created by another session | apply nothing for this page;/| no | exists | created by another session | git merge-file it; apply nothing for this page;/' "$GATE" > "$m"
expect_one "gate mutant: merge-file in the created row is caught" G_merge_file_only_in_modified fail "$(check_gate "$m")"

m="$(gmut recopy_base)"
grep -v -F -- '**the snapshot becomes the new `.base`**' "$GATE" > "$m"
expect_one "gate mutant: rebaseline-from-snapshot removed is caught" G_merge_from_snapshot_rebaseline fail "$(check_gate "$m")"

m="$(gmut budget_reset)"
sed 's/^\[ -f "\$drafts\/.reader_budget" \] || echo 3 > "\$drafts\/.reader_budget"$/echo 3 > "$drafts\/.reader_budget"/' "$GATE" > "$m"
expect_one "gate mutant: unconditional budget reset is caught" G_budget_written_once_per_run fail "$(check_gate "$m")"

m="$(gmut no_recreate_transition)"
grep -v -F -- '**Recreate the page:**' "$GATE" > "$m"
expect_one "gate mutant: recreate without dropping the stale .base is caught" G_deleted_choice_transitions fail "$(check_gate "$m")"

m="$(gmut move_delete_first)"
sed 's/^- \*\*Move the change to another page:\*\* \*\*first\*\* put the change into the other$/- **Move the change to another page:** delete this page'"'"'s pair, then put the change into the other/' "$GATE" > "$m"
expect_one "gate mutant: move that deletes the source pair first is caught" G_deleted_choice_transitions fail "$(check_gate "$m")"

# --- summary ---------------------------------------------------------------
echo ""
echo "Tests: $TOTAL, Passed: $PASS, Failed: $FAIL"
[ "$FAIL" -eq 0 ]
