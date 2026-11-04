#!/usr/bin/env bash
# test_premise_stale.sh - Tests for the premise-staleness producer (t1663_1):
# aitask_premise_stale.sh over real sandbox git repos, through the real pure core
# (lib/task_premise.py) and the real `--batch-map --encode-paths` seam.
#
# Sections:
#   A. verdicts over curated scope (Tier A)
#   B. preconditions: baseline grammar, ancestry, python, CLI misuse
#   C. derived origin scope (Tier B), incl. hostile filenames and failures
#   D. fail-open engine guard (faults injected through PYTHONPATH)
#   E. glue, cwd, data-worktree, encoding and vocabulary drift guards
#
# THE INVARIANT every section probes: FRESH is a positive claim. A failed probe,
# a symbolic baseline or a filename that breaks record framing must read
# ASK_STALE or SKIP -- never FRESH.
#
# Test bodies are plain functions (never `( … )` subshells), so the in-process
# PASS/FAIL counters from tests/lib/asserts.sh are sufficient -- the file-backed
# counters (assert_counters_init) are deliberately NOT used.
#
# Run: bash tests/test_premise_stale.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/fixture_root.sh"

HELPER="$PROJECT_DIR/.aitask-scripts/aitask_premise_stale.sh"
LIB="$PROJECT_DIR/.aitask-scripts/lib"
PY="$( . "$LIB/python_resolve.sh" 2>/dev/null; resolve_python 2>/dev/null || true)"
[[ -n "$PY" ]] || PY="$(command -v python3)"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

TS="2026-01-01 10:00"

# --- Fixture factories -------------------------------------------------------

new_repo() {
    # new_repo -> echoes a fresh git repo path with an initial commit
    local d
    d="$(fixture_mktemp_d test_premstale)" || return 1
    git init --quiet "$d"
    git -C "$d" config user.email "test@test.com"
    git -C "$d" config user.name "Test"
    git -C "$d" config commit.gpgsign false
    mkdir -p "$d/lib" "$d/docs" "$d/aitasks"
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
    # :(literal) -- `git add` takes a PATHSPEC, so a glob-shaped fixture name
    # would stage its neighbours too.
    git -C "$d" add -- ":(literal)$rel"
    git -C "$d" commit -q -m "$subject"
}

remove_file() {
    # remove_file <repo> <relpath> <subject>
    local d="$1" rel="$2" subject="$3"
    git -C "$d" rm -q -- ":(literal)$rel"
    git -C "$d" commit -q -m "$subject"
}

mk_task() {
    # mk_task <path> <baseline-or-empty> <file_references-csv-or-empty> [verifies] [anchor]
    local path="$1" baseline="$2" refs="$3" verifies="${4:-}" anchor="${5:-}"
    {
        echo "---"
        echo "priority: medium"
        echo "effort: low"
        echo "depends: []"
        echo "issue_type: feature"
        echo "status: Ready"
        echo "labels: []"
        [[ -n "$refs" ]] && echo "file_references: [$refs]"
        [[ -n "$verifies" ]] && echo "verifies: [$verifies]"
        [[ -n "$anchor" ]] && echo "anchor: $anchor"
        [[ -n "$baseline" ]] && echo "premise_baseline: $baseline"
        echo "created_at: $TS"
        echo "updated_at: $TS"
        echo "---"
        echo ""
        echo "Body"
    } > "$path"
}

run_check() {
    # run_check <repo> <task_file_rel> [extra env...] -- cwd inside the sandbox
    local d="$1" t="$2"
    shift 2
    ( cd "$d" && env "$@" bash "$HELPER" check "$t" 2>/dev/null )
}

run_check_err() {
    # run_check_err <repo> <task_file_rel> <errfile> [extra env...]
    local d="$1" t="$2" err="$3"
    shift 3
    ( cd "$d" && env "$@" bash "$HELPER" check "$t" 2>"$err" )
}

decision_of() {
    printf '%s\n' "$1" | sed -n 's/^DECISION://p' | head -1
}

count_matches() {
    local n
    n=$(printf '%s\n' "$1" | grep -cE "$2" || true)
    printf '%s' "$n"
}

assert_not_fresh() {
    assert_eq "$1 (never FRESH)" "not-fresh" \
        "$( [[ "$(decision_of "$2")" == "FRESH" ]] && echo FRESH || echo not-fresh )"
}

# assert_protocol_shape <desc> <output> -- the fixed 4-line head + DISPLAY/DECISION tail
assert_protocol_shape() {
    local desc="$1" out="$2" ok=yes
    local -a lines=()
    local l
    while IFS= read -r l; do lines+=("$l"); done <<< "$out"
    local n=${#lines[@]}
    [[ $n -ge 6 ]] || ok=no
    if [[ $ok == yes ]]; then
        [[ "${lines[0]}" == BASELINE:* && "${lines[1]}" == CHECKED:* \
           && "${lines[2]}" == FINGERPRINT:* && "${lines[3]}" == FILES:* \
           && "${lines[n-2]}" == DISPLAY:* && "${lines[n-1]}" == DECISION:* ]] || ok=no
    fi
    assert_eq "$desc (protocol shape)" "yes" "$ok"
}

# =============================================================================
# Section A -- curated scope
# =============================================================================

test_clean_scope_is_fresh_and_rows_reach_the_core() {
    echo "=== A: two untouched curated files => FRESH, FILES:2 (rows reached the core) ==="
    local d base out
    d=$(new_repo)
    commit_file "$d" lib/a.sh "one" "feature: add a (t100)"
    commit_file "$d" lib/b.sh "one" "feature: add b (t100)"
    base=$(git -C "$d" rev-parse HEAD)
    commit_file "$d" lib/other.sh "x" "chore: unrelated (t555)"
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" "lib/a.sh, lib/b.sh"
    out=$(run_check "$d" aitasks/t500_x.md)
    assert_eq "clean => FRESH" "FRESH" "$(decision_of "$out")"
    # Rows reach the core: an empty-stdin glue would read SKIP/empty_scope here.
    assert_contains "clean => FILES:2 through the real check" "FILES:2" "$out"
    assert_contains "CHECKED: is the pinned HEAD" "CHECKED:$(git -C "$d" rev-parse HEAD)" "$out"
    assert_protocol_shape "clean" "$out"
}

test_changed_is_ask_stale_naming_the_culprit() {
    echo "=== A: a curated file modified since the baseline => ASK_STALE + CHANGED ==="
    local d base out
    d=$(new_repo)
    commit_file "$d" lib/a.sh "one" "feature: add a (t100)"
    base=$(git -C "$d" rev-parse HEAD)
    commit_file "$d" lib/a.sh "two" "enhancement: tweak a (t777)"
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" "lib/a.sh"
    out=$(run_check "$d" aitasks/t500_x.md)
    assert_eq "modified => ASK_STALE" "ASK_STALE" "$(decision_of "$out")"
    assert_contains "modified => CHANGED names the culprit" "CHANGED:lib/a.sh|1|777" "$out"
}

test_deleted_is_detected_by_probe_not_history() {
    echo "=== A: a curated file deleted => DELETED, never CHANGED ==="
    local d base out
    d=$(new_repo)
    commit_file "$d" lib/b.sh "one" "feature: add b (t101)"
    base=$(git -C "$d" rev-parse HEAD)
    remove_file "$d" lib/b.sh "chore: drop b (t778)"
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" "lib/b.sh"
    out=$(run_check "$d" aitasks/t500_x.md)
    assert_eq "deleted => ASK_STALE" "ASK_STALE" "$(decision_of "$out")"
    assert_contains "deleted => DELETED names the culprit" "DELETED:lib/b.sh|778|chore: drop b (t778)" "$out"
    assert_not_contains "deleted => not CHANGED" "CHANGED:lib/b.sh" "$out"
}

test_uncheckable_entries_drive_ask_stale() {
    echo "=== A: absent-at-baseline and invalid entries => UNKNOWN => ASK_STALE ==="
    local d base out
    d=$(new_repo)
    commit_file "$d" lib/a.sh "one" "feature: add a (t100)"
    base=$(git -C "$d" rev-parse HEAD)
    commit_file "$d" lib/new.sh "n" "feature: new (t779)"
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" 'lib/a.sh, lib/new.sh, ":12"'
    out=$(run_check "$d" aitasks/t500_x.md)
    assert_eq "uncheckable => ASK_STALE" "ASK_STALE" "$(decision_of "$out")"
    assert_contains "absent at baseline" "UNKNOWN:lib/new.sh|absent_at_baseline" "$out"
    assert_contains "range-only entry is invalid_reference" "UNKNOWN::12|invalid_reference" "$out"
    assert_contains "all three entries counted" "FILES:3" "$out"
}

test_failed_history_is_never_unchanged() {
    echo "=== A: a FAILED git log on a genuinely changed file => history_unavailable, never FRESH ==="
    local d base out control
    d=$(new_repo)
    commit_file "$d" lib/a.sh "one" "feature: add a (t100)"
    base=$(git -C "$d" rev-parse HEAD)
    commit_file "$d" lib/a.sh "two" "enhancement: tweak a (t777)"
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" "lib/a.sh"
    control=$(run_check "$d" aitasks/t500_x.md)
    assert_contains "control: the change is visible without the fault" "CHANGED:lib/a.sh|1|777" "$control"

    # The reviewer's probe: both cat-file -e probes still succeed, git log exits 128.
    git -C "$d" config log.date invalid-date-mode
    out=$(run_check "$d" aitasks/t500_x.md)
    git -C "$d" config --unset log.date
    assert_not_fresh "log.date=invalid-date-mode" "$out"
    assert_contains "failed history is reported as such" "UNKNOWN:lib/a.sh|history_unavailable" "$out"
    assert_eq "failed history => ASK_STALE" "ASK_STALE" "$(decision_of "$out")"
}

test_dirty_worktree_is_not_a_change() {
    echo "=== A: an uncommitted edit to a scope file flips nothing ==="
    local d base out
    d=$(new_repo)
    commit_file "$d" lib/a.sh "one" "feature: add a (t100)"
    base=$(git -C "$d" rev-parse HEAD)
    echo "dirty" >> "$d/lib/a.sh"
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" "lib/a.sh"
    out=$(run_check "$d" aitasks/t500_x.md)
    assert_eq "dirty worktree => FRESH" "FRESH" "$(decision_of "$out")"
    assert_eq "dirty worktree => no evidence" "0" "$(count_matches "$out" '^(CHANGED|DELETED|UNKNOWN):')"
}

test_encoding_and_glob_paths() {
    echo "=== A: '|' / literal %7C names round-trip; glob names absorb no neighbour ==="
    local d base out
    d=$(new_repo)
    commit_file "$d" "lib/a|b.sh" "1" "feature: pipe (t100)"
    commit_file "$d" "lib/x%7Cy.sh" "1" "feature: pct (t100)"
    commit_file "$d" "docs/a[bc].md" "1" "docs: glob (t100)"
    commit_file "$d" "docs/ab.md" "1" "docs: neighbour (t100)"
    base=$(git -C "$d" rev-parse HEAD)
    commit_file "$d" "lib/a|b.sh" "2" "fix: pipe (t801)"
    commit_file "$d" "lib/x%7Cy.sh" "2" "fix: pct (t802)"
    commit_file "$d" "docs/ab.md" "2" "docs: neighbour moves (t803)"
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" '"lib/a|b.sh", "lib/x%7Cy.sh", "docs/a[bc].md"'
    out=$(run_check "$d" aitasks/t500_x.md)
    assert_contains "'|' is encoded" "CHANGED:lib/a%7Cb.sh|1|801" "$out"
    assert_contains "literal %7C is not an encoded delimiter" "CHANGED:lib/x%257Cy.sh|1|802" "$out"
    assert_not_contains "glob name does not absorb its neighbour's change" "docs/a[bc].md|" "$out"
    assert_not_contains "no neighbour task id leaks in" "|803" "$out"
}

test_ranges_are_stripped_and_deduped() {
    echo "=== A: range suffixes stripped; duplicate ranges are one unit ==="
    local d base out
    d=$(new_repo)
    commit_file "$d" lib/a.sh "one" "feature: add a (t100)"
    base=$(git -C "$d" rev-parse HEAD)
    commit_file "$d" lib/a.sh "two" "fix: a (t777)"
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" "lib/a.sh:1-3, lib/a.sh:5-9^12-14, lib/a.sh"
    out=$(run_check "$d" aitasks/t500_x.md)
    assert_contains "ranges dedupe to FILES:1" "FILES:1" "$out"
    assert_contains "the stripped path is reported" "CHANGED:lib/a.sh|1|777" "$out"
}

test_quoted_comma_entry_is_one_path() {
    echo "=== A: file_references: [\"a,b.py\"] is ONE path, never 'a' + 'b.py' ==="
    local d base out
    d=$(new_repo)
    commit_file "$d" "a,b.py" "1" "feature: comma file (t100)"
    commit_file "$d" "a" "1" "feature: fragment a (t100)"
    commit_file "$d" "b.py" "1" "feature: fragment b (t100)"
    base=$(git -C "$d" rev-parse HEAD)
    commit_file "$d" "a,b.py" "2" "fix: only the comma file moves (t777)"
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" '"a,b.py"'
    out=$(run_check "$d" aitasks/t500_x.md)
    assert_not_fresh "quoted comma entry" "$out"
    assert_contains "the comma file is the scope" "FILES:1" "$out"
    assert_contains "and its change is reported" "CHANGED:a,b.py|1|777" "$out"
    assert_not_contains "the unchanged fragments are not the scope" "FILES:2" "$out"
}

test_invalid_yaml_frontmatter_skips() {
    echo "=== A: frontmatter that is not valid YAML => SKIP invalid_frontmatter, no comma guess ==="
    local d base out
    d=$(new_repo)
    commit_file "$d" "docs/ab.md" "1" "docs: x (t100)"
    base=$(git -C "$d" rev-parse HEAD)
    commit_file "$d" "docs/ab.md" "2" "docs: y (t777)"
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" "docs/a[bc].md"
    out=$(run_check "$d" aitasks/t500_x.md)
    assert_eq "unparseable frontmatter => SKIP" "SKIP" "$(decision_of "$out")"
    assert_contains "unparseable frontmatter => invalid_frontmatter" "invalid_frontmatter" "$out"
}

test_non_string_entries_are_uncheckable_not_dropped() {
    echo "=== A: null / on / 010 entries are invalid references -- never dropped, never coerced ==="
    local d base out err
    d=$(new_repo)
    for f in good.py True 8 on 010; do commit_file "$d" "$f" "1" "feature: $f (t100)"; done
    base=$(git -C "$d" rev-parse HEAD)
    commit_file "$d" on "2" "fix: on (t777)"
    commit_file "$d" 010 "2" "fix: 010 (t778)"
    err="$(fixture_mktemp_d test_premstale_err)/stderr"

    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" "good.py, null"
    out=$(run_check_err "$d" aitasks/t500_x.md "$err")
    assert_not_fresh "[good.py, null]" "$out"
    assert_contains "[good.py, null] keeps both entries" "FILES:2" "$out"
    assert_contains "the null entry is an invalid reference" \
        "UNKNOWN:<invalid file_references entry: None>|invalid_reference" "$out"
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" "good.py"
    out=$(run_check "$d" aitasks/t500_x.md)
    assert_eq "control: [good.py] alone is FRESH" "FRESH" "$(decision_of "$out")"

    # YAML 1.1 reads unquoted on / 010 as True / 8; files named True and 8 exist,
    # unchanged, so a coercing reader would watch them and read FRESH.
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" "on, 010"
    out=$(run_check_err "$d" aitasks/t500_x.md "$err")
    assert_not_fresh "[on, 010] unquoted" "$out"
    assert_eq "both coerced entries are invalid references" "2" \
        "$(count_matches "$out" '^UNKNOWN:<invalid file_references entry: .*>\|invalid_reference$')"
    assert_not_contains "the decoy file True is never watched" "True|" "${out//entry: True>/}"
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" '"on", "010"'
    out=$(run_check "$d" aitasks/t500_x.md)
    assert_contains "control: quoted on is checked" "CHANGED:on|1|777" "$out"
    assert_contains "control: quoted 010 is checked" "CHANGED:010|1|778" "$out"
    assert_eq "no warning reached stderr" "" "$(cat "$err")"
}

test_nul_values_never_reach_bash() {
    echo "=== A: a NUL in a reference or the baseline is rejected before bash, silently ==="
    local d base out err
    d=$(new_repo)
    commit_file "$d" a.py "1" "feature: a (t100)"
    base=$(git -C "$d" rev-parse HEAD)
    err="$(fixture_mktemp_d test_premstale_err)/stderr"
    # YAML's double-quoted "\0" escape IS a NUL; bash `$( )` would drop it and
    # read the unchanged a.py.
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" '"a\0.py"'
    out=$(run_check_err "$d" aitasks/t500_x.md "$err")
    assert_not_fresh "NUL reference" "$out"
    assert_contains "NUL reference => invalid reference" "invalid_reference" "$out"
    assert_not_contains "NUL reference is never read as a.py" "UNKNOWN:a.py|" "$out"
    assert_eq "NUL reference => no 'ignored null byte' warning" "" "$(cat "$err")"
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" '"a.py"'
    out=$(run_check "$d" aitasks/t500_x.md)
    assert_eq "control: \"a.py\" is FRESH" "FRESH" "$(decision_of "$out")"

    mk_task "$d/aitasks/t500_x.md" "\"$base\\0 @ $TS\"" "a.py"
    out=$(run_check_err "$d" aitasks/t500_x.md "$err")
    assert_eq "NUL baseline => SKIP" "SKIP" "$(decision_of "$out")"
    assert_contains "NUL baseline => invalid_baseline" "invalid_baseline" "$out"
    assert_eq "NUL baseline => no warning" "" "$(cat "$err")"
    mk_task "$d/aitasks/t500_x.md" "\"$base @ $TS\"" "a.py"
    out=$(run_check "$d" aitasks/t500_x.md)
    assert_eq "control: the quoted clean baseline is FRESH" "FRESH" "$(decision_of "$out")"
}

test_fields_reader_failures_fail_closed() {
    echo "=== A: a broken / truncated fields read => SKIP scope_error, never a shrunk scope ==="
    local d base out err shadow mode
    d=$(new_repo)
    commit_file "$d" lib/a.sh "1" "feature: a (t100)"
    commit_file "$d" lib/b.sh "1" "feature: b (t100)"
    base=$(git -C "$d" rev-parse HEAD)
    commit_file "$d" lib/b.sh "2" "fix: b (t777)"
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" "lib/a.sh, lib/b.sh"
    err="$(fixture_mktemp_d test_premstale_err)/stderr"
    shadow="$(fixture_mktemp_d test_premstale_fields)"
    # Wraps the REAL module and damages only task_fields' output.
    cat > "$shadow/task_premise.py" <<'EOF'
import importlib.util as _u, os as _os
_spec = _u.spec_from_file_location("_real_task_premise", _os.environ["PREMISE_REAL_LIB"] + "/task_premise.py")
_real = _u.module_from_spec(_spec)
_spec.loader.exec_module(_real)
check = _real.check
def task_fields(meta):
    lines = list(_real.task_fields(meta))
    mode = _os.environ.get("PREMISE_FIELDS_FAULT", "")
    if mode == "drop_end":
        return tuple(lines[:-1])
    if mode == "drop_ref":
        return tuple(l for l in lines if l != "FIELD_REF:lib/b.sh")
    return tuple(lines)
EOF
    for mode in drop_end drop_ref; do
        out=$(run_check_err "$d" aitasks/t500_x.md "$err" PYTHONPATH="$shadow"             PREMISE_REAL_LIB="$LIB" PREMISE_FIELDS_FAULT="$mode")
        assert_not_fresh "fields fault $mode" "$out"
        assert_eq "fields fault $mode => SKIP" "SKIP" "$(decision_of "$out")"
        assert_contains "fields fault $mode => scope_error" "scope_error" "$out"
        assert_eq "fields fault $mode => helper stderr empty" "" "$(cat "$err")"
    done
    out=$(run_check "$d" aitasks/t500_x.md PYTHONPATH="$shadow" PREMISE_REAL_LIB="$LIB" PREMISE_FIELDS_FAULT=none)
    assert_contains "control: the undamaged wrapper sees the change" "CHANGED:lib/b.sh|1|777" "$out"

    printf 'raise SystemExit(5)\n' > "$shadow/task_yaml.py"
    out=$(run_check_err "$d" aitasks/t500_x.md "$err" PYTHONPATH="$shadow"         PREMISE_REAL_LIB="$LIB" PREMISE_FIELDS_FAULT=none)
    assert_eq "fields reader crash => SKIP" "SKIP" "$(decision_of "$out")"
    assert_contains "fields reader crash => scope_error" "scope_error" "$out"
}

test_fingerprint_and_baseline_advance() {
    echo "=== A: FINGERPRINT stable over unrelated commits; advancing to CHECKED stops the prompt ==="
    local d base out1 out2 out3 fp1 fp2 fp3 checked out4
    d=$(new_repo)
    commit_file "$d" lib/a.sh "one" "feature: add a (t100)"
    commit_file "$d" lib/b.sh "one" "feature: add b (t100)"
    base=$(git -C "$d" rev-parse HEAD)
    commit_file "$d" lib/a.sh "two" "fix: a (t777)"
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" "lib/a.sh"
    out1=$(run_check "$d" aitasks/t500_x.md)
    commit_file "$d" lib/unrelated.sh "u" "chore: unrelated (t900)"
    out2=$(run_check "$d" aitasks/t500_x.md)
    fp1=$(printf '%s\n' "$out1" | sed -n 's/^FINGERPRINT://p')
    fp2=$(printf '%s\n' "$out2" | sed -n 's/^FINGERPRINT://p')
    assert_eq "fingerprint stable across an unrelated commit" "$fp1" "$fp2"
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" "lib/a.sh, lib/b.sh"
    out3=$(run_check "$d" aitasks/t500_x.md)
    fp3=$(printf '%s\n' "$out3" | sed -n 's/^FINGERPRINT://p')
    assert_eq "fingerprint changes when file_references: is edited" "differs" \
        "$( [[ "$fp1" != "$fp3" && -n "$fp3" ]] && echo differs || echo same )"

    checked=$(printf '%s\n' "$out3" | sed -n 's/^CHECKED://p')
    mk_task "$d/aitasks/t500_x.md" "$checked @ $TS" "lib/a.sh, lib/b.sh"
    out4=$(run_check "$d" aitasks/t500_x.md)
    assert_eq "advancing the baseline to CHECKED: stops the prompt" "FRESH" "$(decision_of "$out4")"
}

# =============================================================================
# Section B -- preconditions
# =============================================================================

test_no_baseline_and_no_scope_skip() {
    echo "=== B: no stored baseline => SKIP, FILES:0, CHECKED:NONE; empty scope => SKIP ==="
    local d base out
    d=$(new_repo)
    commit_file "$d" lib/a.sh "one" "feature: add a (t100)"
    base=$(git -C "$d" rev-parse HEAD)
    mk_task "$d/aitasks/t500_x.md" "" "lib/a.sh"
    out=$(run_check "$d" aitasks/t500_x.md)
    assert_eq "no baseline => SKIP" "SKIP" "$(decision_of "$out")"
    assert_contains "no baseline => FILES:0 (scope never resolved)" "FILES:0" "$out"
    assert_contains "no baseline => CHECKED:NONE" "CHECKED:NONE" "$out"
    assert_contains "no baseline => reason" "no_stored_baseline" "$out"

    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" ""
    out=$(run_check "$d" aitasks/t500_x.md)
    assert_eq "baseline + empty scope => SKIP" "SKIP" "$(decision_of "$out")"
    assert_contains "baseline + empty scope => empty_scope" "empty_scope" "$out"
    assert_contains "SKIP => FINGERPRINT:NONE" "FINGERPRINT:NONE" "$out"
}

test_symbolic_baselines_are_never_compared() {
    echo "=== B: HEAD / branch / abbreviation / HEAD~1 baselines => SKIP invalid_baseline, never FRESH ==="
    local d base branch out v
    d=$(new_repo)
    commit_file "$d" lib/a.sh "one" "feature: add a (t100)"
    base=$(git -C "$d" rev-parse HEAD)
    commit_file "$d" lib/a.sh "two" "fix: a (t777)"
    branch=$(git -C "$d" symbolic-ref --short HEAD)
    for v in "HEAD" "$branch" "${base:0:7}" "HEAD~1"; do
        mk_task "$d/aitasks/t500_x.md" "$v @ $TS" "lib/a.sh"
        out=$(run_check "$d" aitasks/t500_x.md)
        assert_not_fresh "baseline '$v'" "$out"
        assert_eq "baseline '$v' => SKIP" "SKIP" "$(decision_of "$out")"
        assert_contains "baseline '$v' => invalid_baseline" "invalid_baseline" "$out"
        assert_contains "baseline '$v' => BASELINE:NONE" "BASELINE:NONE" "$out"
    done
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" "lib/a.sh"
    out=$(run_check "$d" aitasks/t500_x.md)
    assert_contains "control: the full sha sees the change" "CHANGED:lib/a.sh|1|777" "$out"
    mk_task "$d/aitasks/t500_x.md" "$(printf '%s' "$base" | tr 'a-f' 'A-F') @ $TS" "lib/a.sh"
    out=$(run_check "$d" aitasks/t500_x.md)
    assert_eq "an uppercase full sha is accepted" "ASK_STALE" "$(decision_of "$out")"
    assert_contains "and normalized to lowercase" "BASELINE:$base|" "$out"
}

test_history_rewrite_skips_on_both_arms() {
    echo "=== B: baseline not an ancestor => SKIP (exit 1 and exit 128 arms) ==="
    local d base orphan out
    d=$(new_repo)
    commit_file "$d" lib/a.sh "one" "feature: add a (t100)"
    orphan=$(git -C "$d" commit-tree "$(git -C "$d" hash-object -t tree /dev/null)" -m "orphan")
    mk_task "$d/aitasks/t500_x.md" "$orphan @ $TS" "lib/a.sh"
    out=$(run_check "$d" aitasks/t500_x.md)
    assert_eq "unrelated commit (exit 1) => SKIP" "SKIP" "$(decision_of "$out")"
    assert_contains "unrelated commit => history_rewritten" "history_rewritten" "$out"
    assert_contains "the sha still shows in BASELINE:" "BASELINE:$orphan|" "$out"
    mk_task "$d/aitasks/t500_x.md" "$(printf '%040d' 0 | tr 0 e) @ $TS" "lib/a.sh"
    out=$(run_check "$d" aitasks/t500_x.md)
    assert_eq "nonexistent well-formed sha (exit 128) => SKIP" "SKIP" "$(decision_of "$out")"
    assert_contains "nonexistent sha => history_rewritten" "history_rewritten" "$out"
    base=$(git -C "$d" rev-parse HEAD)
    : "$base"
}

test_outside_a_git_repository_skips() {
    echo "=== B: not a git repository => SKIP not_a_git_repo ==="
    local d out
    d="$(fixture_mktemp_d test_premstale_nogit)"
    mkdir -p "$d/aitasks"
    mk_task "$d/aitasks/t500_x.md" "$(printf '%040d' 0 | tr 0 a) @ $TS" "lib/a.sh"
    out=$(run_check "$d" aitasks/t500_x.md GIT_CEILING_DIRECTORIES="$FIXTURE_ROOT")
    assert_eq "no repo => SKIP" "SKIP" "$(decision_of "$out")"
    assert_contains "no repo => reason" "not_a_git_repo" "$out"
}

test_python_unavailable_through_the_real_resolver() {
    echo "=== B: no python => shell-formatted SKIP python_unavailable (real resolve_python) ==="
    local d shim home out dir f name
    d=$(new_repo)
    mk_task "$d/aitasks/t500_x.md" "" "lib/a.sh"
    shim="$(fixture_mktemp_d test_premstale_shim)"
    home="$(fixture_mktemp_d test_premstale_home)"
    local IFS_SAVE="$IFS"
    IFS=':'
    for dir in $PATH; do
        IFS="$IFS_SAVE"
        [[ -d "$dir" ]] || continue
        for f in "$dir"/*; do
            name="${f##*/}"
            case "$name" in python*|pypy*) continue ;; esac
            [[ -x "$f" && ! -e "$shim/$name" ]] && ln -s "$f" "$shim/$name"
        done
        IFS=':'
    done
    IFS="$IFS_SAVE"
    out=$( cd "$d" && env -u _AIT_RESOLVED_PYTHON -u AIT_PYTHON HOME="$home" PATH="$shim" \
        bash "$HELPER" check aitasks/t500_x.md 2>/dev/null ) || true
    assert_eq "no python => SKIP" "SKIP" "$(decision_of "$out")"
    assert_contains "no python => python_unavailable" "python_unavailable" "$out"
    assert_protocol_shape "python_unavailable" "$out"
}

test_cli_misuse_dies() {
    echo "=== B: CLI misuse dies rather than printing SKIP ==="
    local rc out
    rc=0; out=$(bash "$HELPER" 2>/dev/null) || rc=$?
    assert_eq "missing verb => non-zero" "nonzero" "$( [[ $rc -ne 0 ]] && echo nonzero || echo zero )"
    rc=0; out=$(bash "$HELPER" check /nonexistent/task.md 2>/dev/null) || rc=$?
    assert_eq "missing file => non-zero" "nonzero" "$( [[ $rc -ne 0 ]] && echo nonzero || echo zero )"
    assert_not_contains "missing file => no SKIP printed" "DECISION:" "$out"
    rc=0; out=$(bash "$HELPER" check 2>/dev/null) || rc=$?
    assert_eq "check without a file => non-zero" "nonzero" "$( [[ $rc -ne 0 ]] && echo nonzero || echo zero )"
}

# =============================================================================
# Section C -- derived origin scope (Tier B)
# =============================================================================

test_tier_b_origin_scope_drops_task_data() {
    echo "=== C: exact origin => scope = its landed code paths (task data dropped) ==="
    local d base out
    d=$(new_repo)
    commit_file "$d" lib/o.sh "o" "feature: origin (t42)"
    commit_file "$d" aitasks/t42_origin.md "t" "ait: task data (t42)"
    base=$(git -C "$d" rev-parse HEAD)
    commit_file "$d" lib/o.sh "o2" "fix: o (t777)"
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" "" "42"
    out=$(run_check "$d" aitasks/t500_x.md)
    assert_eq "tier B change => ASK_STALE" "ASK_STALE" "$(decision_of "$out")"
    assert_contains "tier B => the origin's code path" "CHANGED:lib/o.sh|1|777" "$out"
    assert_contains "tier B => only code paths in scope" "FILES:1" "$out"
    assert_not_contains "tier B => task data is not scope" "aitasks/" "$out"
}

test_tier_b_topic_only_origin_skips() {
    echo "=== C: anchor-only (topic) origin => SKIP, never FRESH ==="
    local d base out
    d=$(new_repo)
    commit_file "$d" lib/o.sh "o" "feature: origin (t42)"
    base=$(git -C "$d" rev-parse HEAD)
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" "" "" "42"
    out=$(run_check "$d" aitasks/t500_x.md)
    assert_eq "topic origin => SKIP" "SKIP" "$(decision_of "$out")"
    assert_contains "topic origin => empty_scope" "empty_scope" "$out"
}

test_tier_b_newline_filename_is_not_its_prefix() {
    echo "=== C: 'lib/keep.py<LF>noise' changed => reported as itself, never as lib/keep.py ==="
    local d base out nl
    nl="$(printf 'lib/keep.py\nnoise')"
    d=$(new_repo)
    commit_file "$d" lib/keep.py "k" "feature: keep (t42)"
    commit_file "$d" "$nl" "n" "feature: noise (t42)"
    base=$(git -C "$d" rev-parse HEAD)
    commit_file "$d" "$nl" "n2" "fix: noise (t43)"
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" "" "42"
    out=$(run_check "$d" aitasks/t500_x.md)
    assert_not_fresh "newline filename" "$out"
    assert_contains "the newline file is reported, encoded" "CHANGED:lib/keep.py%0Anoise|1|43" "$out"
    assert_contains "both real paths, each once" "FILES:2" "$out"
    assert_not_contains "the unchanged prefix file is not blamed" "CHANGED:lib/keep.py|" "$out"
}

test_tier_b_forged_record_filename() {
    echo "=== C: a filename that forges a TASKFILES: record stays one encoded path ==="
    local d base out forged
    forged="$(printf 'x\nTASKFILES:42|lib/keep.py')"
    d=$(new_repo)
    commit_file "$d" lib/keep.py "k" "feature: keep (t42)"
    commit_file "$d" "$forged" "f" "feature: forged (t42)"
    base=$(git -C "$d" rev-parse HEAD)
    commit_file "$d" "$forged" "f2" "fix: forged (t44)"
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" "" "42"
    out=$(run_check "$d" aitasks/t500_x.md)
    assert_eq "forged-record name => ASK_STALE" "ASK_STALE" "$(decision_of "$out")"
    assert_contains "the forged name is reported, encoded" "CHANGED:x%0ATASKFILES:42%7Clib/keep.py|1|44" "$out"
    assert_contains "each real path counted once" "FILES:2" "$out"
}

test_tier_b_hostile_names() {
    echo "=== C: space / '|' / '*' in an origin's paths: verbatim, once, no globbing ==="
    local d base out
    d=$(new_repo)
    commit_file "$d" "lib/with space.sh" "1" "feature: a (t42)"
    commit_file "$d" "lib/p|q.sh" "1" "feature: b (t42)"
    commit_file "$d" "lib/star*.sh" "1" "feature: c (t42)"
    commit_file "$d" "lib/starX.sh" "1" "feature: neighbour (t900)"
    base=$(git -C "$d" rev-parse HEAD)
    commit_file "$d" "lib/starX.sh" "2" "fix: neighbour (t901)"
    commit_file "$d" "lib/with space.sh" "2" "fix: a (t902)"
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" "" "42"
    out=$(run_check "$d" aitasks/t500_x.md)
    assert_contains "three origin paths" "FILES:3" "$out"
    assert_contains "space path verbatim" "CHANGED:lib/with space.sh|1|902" "$out"
    assert_not_contains "'*' path absorbs no neighbour" "|901" "$out"
    assert_eq "exactly one evidence line" "1" "$(count_matches "$out" '^(CHANGED|DELETED|UNKNOWN):')"
}

test_tier_b_unknown_history_completeness() {
    echo "=== C: UNKNOWN_HISTORY origin: ASK_STALE beside a resolvable one; empty_scope alone ==="
    local d base out
    d=$(new_repo)
    commit_file "$d" lib/o.sh "o" "feature: origin (t42)"
    base=$(git -C "$d" rev-parse HEAD)
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" "" "42, 99"
    out=$(run_check "$d" aitasks/t500_x.md)
    assert_eq "resolvable + unknown origin => ASK_STALE" "ASK_STALE" "$(decision_of "$out")"
    assert_contains "the unknown origin is evidence" "UNKNOWN:99|unknown_history" "$out"
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" "" "99"
    out=$(run_check "$d" aitasks/t500_x.md)
    assert_eq "unknown origin alone => SKIP" "SKIP" "$(decision_of "$out")"
    assert_contains "unknown origin alone => empty_scope" "empty_scope" "$out"
}

# make_py_wrapper -> path of an AIT_PYTHON wrapper (run with _AIT_RESOLVED_PYTHON
# unset; the analyzer re-resolves through the same variable). It execs the real
# python except where PREMISE_FAULT says otherwise:
#   origin  followup_origin.py exits 1
#   map     task_file_sets.py exits 2 with FRAMING_ERROR:
#   badrow  task_file_sets.py prints a TASKFILES: row with no '|', exit 0
#   drop    task_file_sets.py runs for real, its output filtered through
#           `grep -vE "$PREMISE_DROP_RE"`, exit status preserved (0)
make_py_wrapper() {
    local w
    w="$(fixture_mktemp_d test_premstale_py)/python" || return 1
    cat > "$w" <<'EOF'
#!/usr/bin/env bash
for a in "$@"; do
    case "$a" in
        *followup_origin.py)
            if [[ "$PREMISE_FAULT" == origin ]]; then echo "boom: origin resolver" >&2; exit 1; fi ;;
        *task_file_sets.py)
            if [[ "$PREMISE_FAULT" == map ]]; then cat >/dev/null; echo "FRAMING_ERROR:0 boom" >&2; exit 2; fi
            if [[ "$PREMISE_FAULT" == badrow ]]; then cat >/dev/null; printf 'TASKFILES:42\nSTATUS:42|FILES\n'; exit 0; fi
            if [[ "$PREMISE_FAULT" == drop ]]; then
                "$PREMISE_REAL_PY" "$@" | grep -vE -- "$PREMISE_DROP_RE"
                exit "${PIPESTATUS[0]}"
            fi ;;
    esac
done
exec "$PREMISE_REAL_PY" "$@"
EOF
    chmod +x "$w"
    printf '%s' "$w"
}

test_tier_b_subprocess_failures_fail_closed() {
    echo "=== C: followup_origin / batch-map failures and a bad row => SKIP scope_error ==="
    local d base out err wrapper
    d=$(new_repo)
    commit_file "$d" lib/o.sh "o" "feature: origin (t42)"
    base=$(git -C "$d" rev-parse HEAD)
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" "" "42"
    wrapper=$(make_py_wrapper)
    err="$(fixture_mktemp_d test_premstale_err)/stderr"
    out=$(run_check_err "$d" aitasks/t500_x.md "$err" -u _AIT_RESOLVED_PYTHON AIT_PYTHON="$wrapper" \
        PREMISE_REAL_PY="$PY" PREMISE_FAULT=origin)
    assert_eq "origin resolver failure => SKIP" "SKIP" "$(decision_of "$out")"
    assert_contains "origin resolver failure => scope_error" "scope_error" "$out"
    assert_contains "the diagnostic is folded into DISPLAY" "boom: origin resolver" "$out"
    assert_eq "origin resolver failure => helper stderr empty" "" "$(cat "$err")"

    out=$(run_check_err "$d" aitasks/t500_x.md "$err" -u _AIT_RESOLVED_PYTHON AIT_PYTHON="$wrapper" \
        PREMISE_REAL_PY="$PY" PREMISE_FAULT=map)
    assert_eq "batch-map failure => SKIP" "SKIP" "$(decision_of "$out")"
    assert_contains "batch-map failure => scope_error" "scope_error" "$out"
    assert_eq "batch-map failure => helper stderr empty" "" "$(cat "$err")"

    out=$(run_check_err "$d" aitasks/t500_x.md "$err" -u _AIT_RESOLVED_PYTHON AIT_PYTHON="$wrapper" \
        PREMISE_REAL_PY="$PY" PREMISE_FAULT=badrow)
    assert_not_fresh "unparseable TASKFILES: row" "$out"
    assert_contains "unparseable, unattested map => scope_error" "scope_error" "$out"

    out=$(run_check_err "$d" aitasks/t500_x.md "$err" -u _AIT_RESOLVED_PYTHON AIT_PYTHON="$wrapper" \
        PREMISE_REAL_PY="$PY" PREMISE_FAULT=none)
    assert_eq "control: the wrapper passes through cleanly" "FRESH" "$(decision_of "$out")"
}

test_tier_b_dropped_map_rows_are_detected() {
    echo "=== C: a map with a dropped STATUS / TASKFILES / COUNT / END row (exit 0) => never FRESH ==="
    local d base out wrapper re
    wrapper=$(make_py_wrapper)

    # (1) The reviewer's STATUS case: two origins, nothing changed; 99 has no history.
    d=$(new_repo)
    commit_file "$d" lib/a.sh "a" "feature: origin (t42)"
    base=$(git -C "$d" rev-parse HEAD)
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" "" "42, 99"
    out=$(run_check "$d" aitasks/t500_x.md -u _AIT_RESOLVED_PYTHON AIT_PYTHON="$wrapper" \
        PREMISE_REAL_PY="$PY" PREMISE_FAULT=none)
    assert_eq "control: the unknown origin drives ASK_STALE" "ASK_STALE" "$(decision_of "$out")"
    assert_contains "control: UNKNOWN for origin 99" "UNKNOWN:99|unknown_history" "$out"
    out=$(run_check "$d" aitasks/t500_x.md -u _AIT_RESOLVED_PYTHON AIT_PYTHON="$wrapper" \
        PREMISE_REAL_PY="$PY" PREMISE_FAULT=drop PREMISE_DROP_RE='^STATUS:99\|')
    assert_not_fresh "dropped STATUS:99" "$out"
    assert_contains "dropped STATUS:99 => scope_error" "scope_error" "$out"

    # (2) The reviewer's TASKFILES case: a genuinely changed file's row dropped.
    d=$(new_repo)
    commit_file "$d" lib/a.sh "a" "feature: origin a (t42)"
    commit_file "$d" lib/b.sh "b" "feature: origin b (t42)"
    base=$(git -C "$d" rev-parse HEAD)
    commit_file "$d" lib/b.sh "b2" "fix: b (t777)"
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" "" "42"
    out=$(run_check "$d" aitasks/t500_x.md -u _AIT_RESOLVED_PYTHON AIT_PYTHON="$wrapper" \
        PREMISE_REAL_PY="$PY" PREMISE_FAULT=none)
    assert_contains "control: the change is visible" "CHANGED:lib/b.sh|1|777" "$out"
    for re in '^TASKFILES:42\|lib/b\.sh$' '^TASKFILES_COUNT:' '^END:' '^STATUS:42\|'; do
        out=$(run_check "$d" aitasks/t500_x.md -u _AIT_RESOLVED_PYTHON AIT_PYTHON="$wrapper" \
            PREMISE_REAL_PY="$PY" PREMISE_FAULT=drop PREMISE_DROP_RE="$re")
        assert_not_fresh "dropped $re" "$out"
        assert_eq "dropped $re => SKIP" "SKIP" "$(decision_of "$out")"
        assert_contains "dropped $re => scope_error" "scope_error" "$out"
    done
}

# =============================================================================
# Section D -- fail-open engine guard (pre-phase engine_error_fail_open)
# =============================================================================

test_engine_faults_fail_open() {
    echo "=== D: a broken core never yields FRESH; SKIP, exit 0, silent stderr ==="
    local d base out err rc shadow kind
    d=$(new_repo)
    commit_file "$d" lib/a.sh "one" "feature: add a (t100)"
    base=$(git -C "$d" rev-parse HEAD)
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" "lib/a.sh"
    err="$(fixture_mktemp_d test_premstale_err)/stderr"
    for kind in raise fresh_with_changed garbage_then_fresh no_display; do
        shadow="$(fixture_mktemp_d "test_premstale_shadow_$kind")"
        case "$kind" in
            raise)
                printf 'def check(rows):\n    raise RuntimeError("core exploded")\n' ;;
            fresh_with_changed)
                printf 'class R:\n    lines = ("BASELINE:%s|t", "CHECKED:%s", "FINGERPRINT:0123456789abcdef", "FILES:1", "CHANGED:lib/a.sh|1|7", "DISPLAY:x", "DECISION:FRESH")\ndef check(rows):\n    return R()\n' "$base" "$base" ;;
            garbage_then_fresh)
                printf 'class R:\n    lines = ("hello", "world", "DECISION:FRESH")\ndef check(rows):\n    return R()\n' ;;
            no_display)
                printf 'class R:\n    lines = ("BASELINE:%s|t", "CHECKED:%s", "FINGERPRINT:0123456789abcdef", "FILES:1", "DECISION:FRESH")\ndef check(rows):\n    return R()\n' "$base" "$base" ;;
        esac > "$shadow/task_premise.py"
        rc=0
        out=$(run_check_err "$d" aitasks/t500_x.md "$err" PYTHONPATH="$shadow") || rc=$?
        assert_eq "$kind => exit 0" "0" "$rc"
        assert_eq "$kind => SKIP" "SKIP" "$(decision_of "$out")"
        assert_contains "$kind => engine_error" "engine_error" "$out"
        assert_not_contains "$kind => no FRESH escapes" "DECISION:FRESH" "$out"
        assert_protocol_shape "$kind" "$out"
        assert_eq "$kind => stdout is only the protocol (6 lines)" "6" "$(printf '%s\n' "$out" | wc -l | tr -d ' ')"
        assert_eq "$kind => helper stderr empty" "" "$(cat "$err")"
    done
    out=$(run_check "$d" aitasks/t500_x.md)
    assert_eq "control: the real core reads FRESH here" "FRESH" "$(decision_of "$out")"
}

# =============================================================================
# Section E -- glue, cwd, data worktree, drift guards
# =============================================================================

extract_glue() {
    sed -n "/^_PREMISE_GLUE='/,/^'/p" "$HELPER" | sed '1d;$d'
}

test_glue_import_path_and_shadow_order() {
    echo "=== E: the glue imports from an arbitrary cwd; a PYTHONPATH shadow still wins ==="
    local glue out scratch shadow rev
    glue="$(extract_glue)"
    rev="$(printf '%040d' 0 | tr 0 c)"
    scratch="$(fixture_mktemp_d test_premstale_cwd)"
    out=$(cd "$scratch" && printf 'REV:%s\nBASE:||no_stored_baseline\nTIER:NONE|0|0\n' "$rev" \
        | "$PY" -c "$glue" "$LIB")
    assert_contains "glue answers from a scratch cwd and echoes REV:" "CHECKED:$rev" "$out"
    shadow="$(fixture_mktemp_d test_premstale_glue_shadow)"
    printf 'class R:\n    lines = ("SHADOW",)\ndef check(rows):\n    return R()\n' > "$shadow/task_premise.py"
    out=$(cd "$scratch" && printf 'x\n' | PYTHONPATH="$shadow" "$PY" -c "$glue" "$LIB")
    assert_eq "a PYTHONPATH shadow wins over the appended lib dir" "SHADOW" "$out"
}

test_cwd_portability_within_the_repo() {
    echo "=== E: identical output from the repo root and a subdirectory ==="
    local d base a b
    d=$(new_repo)
    commit_file "$d" lib/a.sh "one" "feature: add a (t100)"
    base=$(git -C "$d" rev-parse HEAD)
    commit_file "$d" lib/a.sh "two" "fix: a (t777)"
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" "lib/a.sh"
    a=$(run_check "$d" aitasks/t500_x.md)
    b=$(cd "$d/docs" && bash "$HELPER" check ../aitasks/t500_x.md 2>/dev/null)
    assert_eq "subdirectory run is identical" "$a" "$b"
}

test_data_worktree_cwd_skips() {
    echo "=== E: cwd inside a code-less data worktree => SKIP, never FRESH/ASK_STALE ==="
    local d base data_commit wt out
    d=$(new_repo)
    commit_file "$d" lib/a.sh "one" "feature: add a (t100)"
    base=$(git -C "$d" rev-parse HEAD)
    commit_file "$d" lib/a.sh "two" "fix: a (t777)"
    mk_task "$d/aitasks/t500_x.md" "$base @ $TS" "lib/a.sh"
    data_commit=$(git -C "$d" commit-tree "$(git -C "$d" hash-object -t tree /dev/null)" -m "data branch")
    git -C "$d" branch datab "$data_commit"
    wt="$(fixture_mktemp_d test_premstale_wt)/data"
    git -C "$d" worktree add -q "$wt" datab
    out=$(cd "$wt" && bash "$HELPER" check "$d/aitasks/t500_x.md" 2>/dev/null)
    assert_eq "data worktree => SKIP" "SKIP" "$(decision_of "$out")"
    assert_contains "data worktree => fails closed via ancestry" "history_rewritten" "$out"
}

test_vocabulary_and_encoding_drift_guards() {
    echo "=== E: the bash validator and the shell codec match task_premise ==="
    local sh_prefixes py_prefixes v sh_enc py_enc
    sh_prefixes=$(sed -n 's/^_PREMISE_LINE_PREFIXES=(\(.*\))$/\1/p' "$HELPER")
    py_prefixes=$("$PY" -c 'import sys; sys.path.insert(0, sys.argv[1]); import task_premise as t; print(" ".join(t.LINE_PREFIXES))' "$LIB")
    assert_eq "validator prefixes == LINE_PREFIXES" "$py_prefixes" "$sh_prefixes"

    eval "$(sed -n '/^_enc() {/,/^}/p; /^_DEC=""$/p; /^_dec() {/,/^}/p' "$HELPER")"
    local -a corpus=( "%" "%7C" "|" $'a\nb' $'c\rd' "%0A" "%0D" "a%25b" $'tail\n' "plain.py" $'x\nTASKFILES:42|keep.py' )
    for v in "${corpus[@]}"; do
        sh_enc=$(_enc "$v")
        py_enc=$("$PY" -c 'import sys; sys.path.insert(0, sys.argv[1]); import task_premise as t; sys.stdout.write(t.encode_field(sys.argv[2]))' "$LIB" "$v")
        assert_eq "shell _enc == encode_field for $(printf '%q' "$v")" "$py_enc" "$sh_enc"
        _dec "$py_enc"
        assert_eq "shell _dec inverts encode_field for $(printf '%q' "$v")" "$v" "$_DEC"
    done
}

# --- Run ---------------------------------------------------------------------

echo "=== test_premise_stale.sh ==="
echo ""

cd "$PROJECT_DIR" || exit 1

fixture_root_init
assert_fixture_registered "new_repo dirs land under the registered FIXTURE_ROOT" "$(new_repo)"

test_clean_scope_is_fresh_and_rows_reach_the_core
test_changed_is_ask_stale_naming_the_culprit
test_deleted_is_detected_by_probe_not_history
test_uncheckable_entries_drive_ask_stale
test_failed_history_is_never_unchanged
test_dirty_worktree_is_not_a_change
test_encoding_and_glob_paths
test_ranges_are_stripped_and_deduped
test_quoted_comma_entry_is_one_path
test_invalid_yaml_frontmatter_skips
test_non_string_entries_are_uncheckable_not_dropped
test_nul_values_never_reach_bash
test_fields_reader_failures_fail_closed
test_fingerprint_and_baseline_advance

test_no_baseline_and_no_scope_skip
test_symbolic_baselines_are_never_compared
test_history_rewrite_skips_on_both_arms
test_outside_a_git_repository_skips
test_python_unavailable_through_the_real_resolver
test_cli_misuse_dies

test_tier_b_origin_scope_drops_task_data
test_tier_b_topic_only_origin_skips
test_tier_b_newline_filename_is_not_its_prefix
test_tier_b_forged_record_filename
test_tier_b_hostile_names
test_tier_b_unknown_history_completeness
test_tier_b_subprocess_failures_fail_closed
test_tier_b_dropped_map_rows_are_detected

test_engine_faults_fail_open

test_glue_import_path_and_shadow_order
test_cwd_portability_within_the_repo
test_data_worktree_cwd_skips
test_vocabulary_and_encoding_drift_guards

for dir in "${CLEANUP_DIRS[@]}"; do
    rm -rf "$dir"
done

echo ""
echo "=== Results ==="
echo "Total:  $TOTAL"
echo "Pass:   $PASS"
echo "Fail:   $FAIL"

if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "SOME TESTS FAILED"
    exit 1
fi
