#!/usr/bin/env bash
# aitask_followup_backfill.sh - retro-classify `followup_kind` on existing
# follow-up tasks (t1468_6).
#
# t1468_1..t1468_5 registered the field and made every creation seam emit it,
# but forward-only marking leaves the existing backlog unmarked. This script
# classifies the tasks already on disk and writes the field through the
# sanctioned CLI (`aitask_update.sh --batch --followup-kind`), never by hand.
#
# DRY-RUN BY DEFAULT. `--apply` writes.
#
# ---------------------------------------------------------------------------
# Why this is more than a for-loop
#
# ~170 independent `aitask_update.sh` writes are NOT atomic. A mid-run failure
# or a concurrent task edit leaves a partial backfill sitting uncommitted, and
# because the script skips already-marked tasks, a naive retry would silently
# report fewer writes and conceal that only part of the reviewed corpus landed.
#
# So a run is a durable object under .aitask-backfill/<run-id>/:
#
#   manifest.tsv      the reviewed decision, pinning membership AND order
#   preimages/<id>.md the pre-write bytes -- the recovery material
#   journal.tsv       two-phase: INTENT before the write, DONE after
#   state             REVIEWED -> APPLYING -> COMPLETE | FAILED | ABANDONED
#
# The journal is an intent record, NOT the source of truth. lib/atomic_write.sh
# is explicit that the framework's atomic write provides visibility, not crash
# durability (no fsync), so any append can be lost. Recovery therefore
# RECONCILES BY HASHING the files against their preimages (see reconcile_row),
# which makes the write-succeeded-but-journal-failed window a resolvable state
# instead of a stuck one.
#
# Restore is preimage-based, never `git checkout -- <path>`: checkout restores
# from the index and would discard a pre-existing uncommitted edit, and its
# correctness silently depends on the path having been clean.
#
# Usage:
#   aitask_followup_backfill.sh                       # dry run, writes a manifest
#   aitask_followup_backfill.sh --apply --run <id>    # apply the reviewed manifest
#   aitask_followup_backfill.sh --apply --run <id> --limit 3   # canary
#   aitask_followup_backfill.sh --resume --run <id>   # finish a partial run
#   aitask_followup_backfill.sh --abandon --run <id>  # undo a partial run
#   aitask_followup_backfill.sh --verify-delta --run <id>      # pre-commit assertion

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"
# shellcheck source=lib/followup_kinds_sh.sh
source "$SCRIPT_DIR/lib/followup_kinds_sh.sh"
# shellcheck source=lib/artifact_utils.sh
source "$SCRIPT_DIR/lib/artifact_utils.sh"   # artifact_sha256: the framework's
                                             # one platform-portable hash seam

TASK_DIR="${TASK_DIR:-aitasks}"
ARCHIVED_DIR="${ARCHIVED_DIR:-aitasks/archived}"
STATE_ROOT="${AIT_FOLLOWUP_BACKFILL_DIR:-.aitask-backfill}"
CLASSIFIER="$SCRIPT_DIR/lib/followup_backfill_classify.py"
UPDATE_SH="$SCRIPT_DIR/aitask_update.sh"

MODE="dry-run"
RUN_ID=""
LIMIT=""
SCOPE="active"
ALLOW_DIRTY_BASELINE=false
PLAN_FILE=""

usage() {
    sed -n '2,45p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --apply)        MODE="apply"; shift ;;
        --resume)       MODE="resume"; shift ;;
        --abandon)      MODE="abandon"; shift ;;
        --verify-delta) MODE="verify-delta"; shift ;;
        --run)          RUN_ID="$2"; shift 2 ;;
        --limit)        LIMIT="$2"; shift 2 ;;
        --scope)        SCOPE="$2"; shift 2 ;;
        --allow-dirty-baseline) ALLOW_DIRTY_BASELINE=true; shift ;;
        --plan)         PLAN_FILE="$2"; shift 2 ;;
        -h|--help)      usage ;;
        *) die "Unknown argument: $1 (see --help)" ;;
    esac
done

case "$SCOPE" in
    active|all) ;;
    *) die "Invalid --scope: $SCOPE (must be 'active' or 'all')" ;;
esac
if [[ -n "$LIMIT" && ! "$LIMIT" =~ ^[1-9][0-9]*$ ]]; then
    die "Invalid --limit: $LIMIT (must be a positive integer)"
fi

PYTHON="$(require_ait_python)"

# --- small helpers ----------------------------------------------------------

# Delegate to the framework's hashing seam rather than picking a CLI here:
# sha256sum is GNU-only and absent on macOS, where the fallback is
# `shasum -a 256`. artifact_utils.sh already encapsulates that choice.
sha() { artifact_sha256 "$1"; }

run_dir()      { printf '%s/%s' "$STATE_ROOT" "$1"; }
manifest_of()  { printf '%s/manifest.tsv' "$(run_dir "$1")"; }
journal_of()   { printf '%s/journal.tsv' "$(run_dir "$1")"; }
state_file_of(){ printf '%s/state' "$(run_dir "$1")"; }
preimage_of()  { printf '%s/preimages/%s.md' "$(run_dir "$1")" "$2"; }

read_state()  { cat "$(state_file_of "$1")" 2>/dev/null || printf 'MISSING'; }
write_state() { printf '%s\n' "$2" > "$(state_file_of "$1")"; }

require_run() {
    [[ -n "$RUN_ID" ]] || die "--run <id> is required for --$MODE. Latest: $(latest_run || echo none)"
    [[ -d "$(run_dir "$RUN_ID")" ]] || die "No such run: $RUN_ID (looked in $STATE_ROOT)"
}

latest_run() {
    # `find -printf` is GNU-only (BSD/macOS find has no such flag), so walk the
    # entries and basename them instead.
    [[ -d "$STATE_ROOT" ]] || return 1
    local d
    for d in "$STATE_ROOT"/*/; do
        [[ -d "$d" ]] || continue
        basename "$d"
    done | sort | tail -n1
}

# Enumerate the corpus. `aitasks/` is a SYMLINK into the .aitask-data worktree,
# so -L is mandatory or find returns nothing. Do not drive this off `ait ls`:
# it defaults to --status Ready and hides child tasks.
enumerate_tasks() {
    if [[ "$SCOPE" == "all" ]]; then
        find -L "$TASK_DIR" -type f -name 't*.md' -print0
    else
        find -L "$TASK_DIR" -path "$ARCHIVED_DIR" -prune -o -type f -name 't*.md' -print0
    fi
}

# Is the difference between two versions of a task file EXACTLY the backfill's
# own footprint?
#
# This is a SEMANTIC comparison, not a line diff, and that distinction is
# load-bearing. aitask_update.sh rebuilds the frontmatter block through its own
# serializer, which legitimately (a) emits keys in its canonical order rather
# than the order found on disk, and (b) canonicalises task-id lists
# (`verifies: ['635_11']` -> `[t635_11]`). Both are what ANY `ait update` does
# to these files; neither loses information. A line-level check flags them as
# corruption -- and, worse, made reconcile_row report the backfill's OWN writes
# as FOREIGN_DRIFT, which would have made --abandon refuse to restore them.
#
# What actually matters: no key lost, no unrelated value changed, body
# untouched, followup_kind added with the expected value. delta_report in
# lib/followup_backfill_classify.py owns that contract; exit 0 means OK or
# OK_NORMALIZED, exit 1 means BAD.
#
# Shared by reconcile_row (recovery) and verify_delta (pre-commit assertion),
# deliberately: one definition of "the expected delta" for both.
delta_is_expected_only() {
    local before="$1" after="$2" kind="$3"
    "$PYTHON" "$CLASSIFIER" --delta "$before" "$after" "$kind" >/dev/null 2>&1
}

# Same comparison, but echo the verdict and any normalisation notes.
delta_explain() {
    "$PYTHON" "$CLASSIFIER" --delta "$1" "$2" "$3" 2>&1 || true
}

# --- dry run ----------------------------------------------------------------

do_dry_run() {
    local run_id
    run_id="$(date +%Y%m%d-%H%M%S)"
    local dir; dir="$(run_dir "$run_id")"
    mkdir -p "$dir/preimages"

    local raw; raw="$dir/classified.tsv"
    # shellcheck disable=SC2046
    enumerate_tasks | xargs -0 "$PYTHON" "$CLASSIFIER" > "$raw"

    local total already residue conflicts unparseable
    total=$(wc -l < "$raw")
    already=$(awk -F'\t' '$2=="ALREADY"' "$raw" | wc -l)
    conflicts=$(awk -F'\t' '$2 ~ /^CONFLICT/' "$raw" | wc -l)
    unparseable=$(awk -F'\t' '$2=="UNPARSEABLE_ID" || $2=="NO_FRONTMATTER"' "$raw" | wc -l)
    residue=$(awk -F'\t' '$2=="-"' "$raw" | wc -l)

    # The manifest: rows we intend to write, in a fixed order.
    local manifest; manifest="$(manifest_of "$run_id")"
    : > "$manifest"
    local id rule kind origin path
    # shellcheck disable=SC2034  # `origin` is a positional placeholder in the TSV
    while IFS=$'\t' read -r id rule kind origin path; do
        case "$rule" in
            "-"|ALREADY|UNPARSEABLE_ID|NO_FRONTMATTER|CONFLICT*) continue ;;
        esac
        is_valid_followup_kind "$kind" \
            || die "classifier emitted an unknown kind '$kind' for t$id -- refusing to build a manifest"
        printf '%s\t%s\t%s\t%s\n' "$id" "$kind" "$path" "$(sha "$path")" >> "$manifest"
    done < "$raw"

    local writes; writes=$(wc -l < "$manifest")

    # --- report ---
    echo
    info "Follow-up kind backfill - DRY RUN (run-id: $run_id, scope: $SCOPE)"
    echo
    echo "Corpus (derived at run time -- never compared against a constant):"
    printf '  %-28s %s\n' "task files scanned"      "$total"
    printf '  %-28s %s\n' "already marked (skipped)" "$already"
    printf '  %-28s %s\n' "to write"                "$writes"
    printf '  %-28s %s\n' "residue (no rule)"       "$residue"
    printf '  %-28s %s\n' "unparseable / no frontmatter" "$unparseable"
    printf '  %-28s %s\n' "rule conflicts"          "$conflicts"
    echo
    echo "Assigned kinds:"
    awk -F'\t' '{print $2}' "$manifest" | sort | uniq -c | sort -rn | sed 's/^/  /'
    echo
    echo "  (qa_test_gap and docs_gap absent above == asserted zero, not unexamined:"
    echo "   both producers now self-mark, so only legacy instances could appear.)"
    echo

    if [[ "$conflicts" -gt 0 ]]; then
        warn "Rule CONFLICTS -- two prose-provenance rules matched one task. This is a"
        warn "rule bug, not a precedence question. Resolve before applying:"
        awk -F'\t' '$2 ~ /^CONFLICT/ {printf "    t%s  %s  %s\n", $1, $2, $5}' "$raw"
        echo
    fi

    if [[ "$unparseable" -gt 0 ]]; then
        warn "Files the backfill CANNOT write (no derivable task id for --batch):"
        awk -F'\t' '$2=="UNPARSEABLE_ID" || $2=="NO_FRONTMATTER" {printf "    %-16s %s\n", $2, $5}' "$raw"
        echo
    fi

    echo "Classification table: $raw"
    echo "Manifest:             $manifest"
    echo
    echo "Residue is listed in full in the table above (rule column '-')."
    echo "NOTE: the '## Origin' column is an ANNOTATION, not a filter. Its recall over"
    echo "known follow-ups measured 59%, so its absence is NOT evidence that a task is"
    echo "genuine new work. Review the residue as a set; do not trust the annotation."
    echo
    write_state "$run_id" "REVIEWED"
    echo "Review the table, then:  $0 --apply --run $run_id"
}

# --- reconciliation ---------------------------------------------------------
#
# Classify one manifest row by HASHING, independent of what the journal says.
# Echoes one of: NOT_STARTED STARTED_NOT_LANDED LANDED FOREIGN_DRIFT UNRECOVERABLE
reconcile_row() {
    local run_id="$1" id="$2" kind="$3" path="$4" review_sha="$5"
    local pre; pre="$(preimage_of "$run_id" "$id")"
    local cur; cur="$(sha "$path")"

    if [[ ! -f "$pre" ]]; then
        # No preimage. If the file still matches what was classified, this row
        # was simply never reached -- indistinguishable from a fresh row at
        # first apply, and the state the --limit canary leaves 165 rows in.
        # Treating "preimage missing" as unrecoverable would make the
        # canary->resume path unable to ever complete.
        if [[ "$cur" == "$review_sha" ]]; then echo "NOT_STARTED"; else echo "UNRECOVERABLE"; fi
        return 0
    fi

    local pre_sha; pre_sha="$(sha "$pre")"
    if [[ "$cur" == "$pre_sha" ]]; then echo "STARTED_NOT_LANDED"; return 0; fi
    if delta_is_expected_only "$pre" "$path" "$kind"; then echo "LANDED"; return 0; fi
    echo "FOREIGN_DRIFT"
}

# --- apply / resume ---------------------------------------------------------

# Partition the dirty task paths against the manifest. A dirty SELECTED path
# aborts in every mode: its reviewed hash no longer describes the bytes that
# were classified, and a preimage taken from it would bake a foreign edit into
# this run's own restore material. --allow-dirty-baseline covers only
# NON-selected paths, and does exactly one thing with them: records an
# exclusion set for the delta assertion.
check_baseline() {
    local run_id="$1"
    local manifest; manifest="$(manifest_of "$run_id")"
    local excl; excl="$(run_dir "$run_id")/baseline_excluded.txt"
    : > "$excl"

    local dirty blockers=() other_dirty=()
    dirty="$(task_git status --porcelain -- "$TASK_DIR" 2>/dev/null | awk '{print $2}' || true)"
    [[ -z "$dirty" ]] && return 0

    local p row id kind path review_sha
    while IFS= read -r p; do
        [[ -z "$p" ]] && continue
        row="$(awk -F'\t' -v want="$p" '$3==want {print; exit}' "$manifest")"
        if [[ -z "$row" ]]; then
            other_dirty+=("$p")
            continue
        fi
        # A SELECTED path that is dirty is only a blocker when the dirt is not
        # explained by this run. Reconciling (rather than rejecting outright) is
        # what makes --resume usable at all: after a partial apply, every row
        # this run already wrote is by definition dirty and selected, so a
        # blanket rejection would make resume impossible in any git-tracked
        # repo.
        #
        #   LANDED             -> our own write, fine
        #   NOT_STARTED        -> bytes still equal sha256_at_review, i.e. the
        #                         manifest was built from exactly these bytes,
        #                         so the decision is current and the preimage
        #                         will capture the true pre-run state
        #   STARTED_NOT_LANDED -> equals the preimage, fine
        #   FOREIGN_DRIFT / UNRECOVERABLE -> someone else changed it
        IFS=$'\t' read -r id kind path review_sha <<< "$row"
        case "$(reconcile_row "$run_id" "$id" "$kind" "$path" "$review_sha")" in
            FOREIGN_DRIFT|UNRECOVERABLE) blockers+=("$p") ;;
        esac
    done <<< "$dirty"

    if [[ ${#blockers[@]} -gt 0 ]]; then
        warn "Uncommitted changes on task files this run intends to write:"
        printf '    %s\n' "${blockers[@]}" >&2
        die "Refusing to apply. These paths were classified from different bytes than
     they now hold, so the reviewed decision is stale and a preimage taken now
     would capture a foreign edit. Commit or revert them, then re-run the dry
     run. (--allow-dirty-baseline does NOT relax this.)"
    fi

    if [[ ${#other_dirty[@]} -gt 0 ]]; then
        if [[ "$ALLOW_DIRTY_BASELINE" != true ]]; then
            warn "Uncommitted changes on task files NOT selected by this run:"
            printf '    %s\n' "${other_dirty[@]}" >&2
            die "Refusing to apply. Pass --allow-dirty-baseline to proceed with these
     excluded from the delta assertion."
        fi
        printf '%s\n' "${other_dirty[@]}" > "$excl"
        warn "Proceeding with ${#other_dirty[@]} pre-existing dirty task path(s) excluded"
        warn "from the delta assertion (--allow-dirty-baseline)."
    fi
}

apply_rows() {
    local run_id="$1" is_resume="$2"
    local manifest; manifest="$(manifest_of "$run_id")"
    local journal; journal="$(journal_of "$run_id")"

    local id kind path review_sha
    local applied=0 skipped=0

    # Global preflight: fail FAST and with zero writes, so the outcome is
    # "go re-review" rather than "recover a partial run". Only meaningful on a
    # fresh apply -- on resume, landed rows legitimately differ from review.
    if [[ "$is_resume" != true ]]; then
        local drift=()
        while IFS=$'\t' read -r id kind path review_sha; do
            [[ -f "$path" ]] || { drift+=("$path (missing)"); continue; }
            [[ "$(sha "$path")" == "$review_sha" ]] || drift+=("$path")
        done < "$manifest"
        if [[ ${#drift[@]} -gt 0 ]]; then
            warn "Corpus drifted since the manifest was reviewed:"
            printf '    %s\n' "${drift[@]}" >&2
            die "Aborted with ZERO writes. Re-run the dry run and review again."
        fi
    fi

    # Only now create the journal. Doing it before the preflight would leave an
    # artifact behind after a "zero writes" abort, which should leave the run
    # exactly as it was (state=REVIEWED, no journal).
    touch "$journal"
    write_state "$run_id" "APPLYING"

    local n=0
    while IFS=$'\t' read -r id kind path review_sha; do
        if [[ -n "$LIMIT" && "$n" -ge "$LIMIT" ]]; then break; fi

        local state; state="$(reconcile_row "$run_id" "$id" "$kind" "$path" "$review_sha")"
        case "$state" in
            LANDED)
                # Exact field match via awk -- `grep -P` is GNU-only, and a
                # plain grep would need the id escaped against regex metachars.
                awk -F'\t' -v want="$id" '$1=="DONE" && $2==want {found=1} END{exit !found}' \
                    "$journal" \
                    || printf 'DONE\t%s\t%s\t%s\n' "$id" "$path" "$(sha "$path")" >> "$journal"
                skipped=$((skipped+1)); n=$((n+1)); continue ;;
            FOREIGN_DRIFT|UNRECOVERABLE)
                write_state "$run_id" "FAILED"
                die "t$id ($path) is $state -- it was modified outside this run.
     Stopped at row $((n+1)). Rows before it are recoverable:
       $0 --abandon --run $run_id   # undo this run
     Resolve t$id by hand first; this run will not touch it."
                ;;
        esac

        # NOTE ON THE PER-ROW FRESHNESS CHECK.
        # The global preflight hashes every row ONCE, before the first write.
        # This loop then runs one aitask_update.sh per row -- a multi-minute
        # window in which a concurrent session can edit a row not yet reached.
        # That edit must not be copied into the row's preimage and silently
        # adopted as its baseline.
        #
        # The check that prevents it is the reconcile_row call at the TOP OF
        # THIS ITERATION, a few lines above: it re-hashes the file now, and a
        # row whose bytes no longer match `sha256_at_review` has no preimage,
        # so it reports UNRECOVERABLE and the case arm above stops the run with
        # earlier rows intact and recoverable. There is deliberately no second
        # check here -- `NOT_STARTED` is *defined* as `hash == review_sha`, so
        # an additional `state == NOT_STARTED && hash != review_sha` guard is
        # unsatisfiable, and an unreachable guard reads as protection that
        # isn't there.
        #
        # This is also what makes reconcile_row sound: a preimage is only ever
        # captured from bytes that just matched sha256_at_review, so
        # `preimage == review_sha` is an enforced invariant, not an assumption.

        # Write-ahead: preimage, then INTENT, then the write, then DONE.
        cp "$path" "$(preimage_of "$run_id" "$id")"
        printf 'INTENT\t%s\t%s\t%s\n' "$id" "$path" "$review_sha" >> "$journal"

        if ! "$UPDATE_SH" --batch "$id" --followup-kind "$kind" --silent >/dev/null; then
            write_state "$run_id" "FAILED"
            die "aitask_update.sh failed on t$id. Stopped at row $((n+1)).
     Recover with:  $0 --resume --run $run_id
                or: $0 --abandon --run $run_id"
        fi

        printf 'DONE\t%s\t%s\t%s\n' "$id" "$path" "$(sha "$path")" >> "$journal"
        applied=$((applied+1)); n=$((n+1))
    done < "$manifest"

    local total_rows; total_rows=$(wc -l < "$manifest")
    local landed=0
    while IFS=$'\t' read -r id kind path review_sha; do
        [[ "$(reconcile_row "$run_id" "$id" "$kind" "$path" "$review_sha")" == "LANDED" ]] \
            && landed=$((landed+1))
    done < "$manifest"

    echo
    info "Applied $applied row(s) this invocation ($skipped already landed)."
    info "Run $run_id: $landed of $total_rows manifest rows landed."
    if [[ "$landed" -eq "$total_rows" ]]; then
        write_state "$run_id" "COMPLETE"
        info "state=COMPLETE. Next:  $0 --verify-delta --run $run_id"
    else
        write_state "$run_id" "APPLYING"
        info "state=APPLYING (partial). Finish with:  $0 --resume --run $run_id"
    fi
}

do_apply() {
    require_run
    local st; st="$(read_state "$RUN_ID")"
    case "$st" in
        REVIEWED) ;;
        APPLYING|FAILED)
            die "Run $RUN_ID is in state $st -- a previous apply did not finish.
     Refusing a second --apply: it would skip already-marked rows and hide
     that only part of the reviewed corpus landed. Reconcile first:
       $0 --resume --run $RUN_ID     # finish it
       $0 --abandon --run $RUN_ID    # undo it" ;;
        *) die "Run $RUN_ID is in state $st -- nothing to apply." ;;
    esac
    check_baseline "$RUN_ID"
    apply_rows "$RUN_ID" false
}

do_resume() {
    require_run
    local st; st="$(read_state "$RUN_ID")"
    case "$st" in
        APPLYING|FAILED|REVIEWED) ;;
        *) die "Run $RUN_ID is in state $st -- nothing to resume." ;;
    esac
    check_baseline "$RUN_ID"
    apply_rows "$RUN_ID" true
}

do_abandon() {
    require_run
    local manifest; manifest="$(manifest_of "$RUN_ID")"
    local id kind path review_sha
    local to_restore=() blockers=()

    while IFS=$'\t' read -r id kind path review_sha; do
        case "$(reconcile_row "$RUN_ID" "$id" "$kind" "$path" "$review_sha")" in
            LANDED)                        to_restore+=("$id|$path") ;;
            FOREIGN_DRIFT|UNRECOVERABLE)   blockers+=("$path") ;;
        esac
    done < "$manifest"

    if [[ ${#blockers[@]} -gt 0 ]]; then
        warn "Cannot abandon -- these paths were modified outside this run:"
        printf '    %s\n' "${blockers[@]}" >&2
        die "Refusing to restore: doing so would discard someone else's edit.
     Resolve them by hand, then re-run --abandon."
    fi

    local entry
    for entry in "${to_restore[@]:-}"; do
        [[ -z "$entry" ]] && continue
        id="${entry%%|*}"; path="${entry#*|}"
        cp "$(preimage_of "$RUN_ID" "$id")" "$path"
    done
    write_state "$RUN_ID" "ABANDONED"
    info "Restored ${#to_restore[@]} task file(s) byte-exactly from preimage. state=ABANDONED"
}

# --- delta assertion --------------------------------------------------------

do_verify_delta() {
    require_run
    local manifest; manifest="$(manifest_of "$RUN_ID")"
    local excl; excl="$(run_dir "$RUN_ID")/baseline_excluded.txt"
    [[ -f "$excl" ]] || : > "$excl"

    # 1. Task files: SET equality against rows reconciled as landed. Not count
    #    equality -- the canary's rows and the resumed remainder belong to one
    #    run, and a count comparison would also mask an EXTRA file the script
    #    never reported. The expected side is derived by reconciliation, not
    #    from journal rows, so a lost append cannot corrupt the accounting.
    local expected; expected="$(mktemp)"
    local id kind path review_sha
    while IFS=$'\t' read -r id kind path review_sha; do
        [[ "$(reconcile_row "$RUN_ID" "$id" "$kind" "$path" "$review_sha")" == "LANDED" ]] \
            && echo "$path"
    done < "$manifest" | sort > "$expected"

    local actual; actual="$(mktemp)"
    task_git status --porcelain -- "$TASK_DIR" 2>/dev/null | awk '{print $2}' \
        | grep -vxF -f "$excl" 2>/dev/null | sort > "$actual" || true

    if ! diff -q "$expected" "$actual" >/dev/null; then
        warn "Task-file delta does not match the landed set:"
        diff "$expected" "$actual" | sed 's/^/    /' >&2
        rm -f "$expected" "$actual"
        die "Refusing to commit."
    fi
    info "[1/3] task-file set equality: $(wc -l < "$expected") path(s), exact match"

    # 2. Per-file shape.
    local bad=0
    while IFS=$'\t' read -r id kind path review_sha; do
        [[ "$(reconcile_row "$RUN_ID" "$id" "$kind" "$path" "$review_sha")" == "LANDED" ]] || continue
        if ! delta_is_expected_only "$(preimage_of "$RUN_ID" "$id")" "$path" "$kind"; then
            warn "t$id ($path) changed beyond followup_kind + updated_at"
            bad=$((bad+1))
        fi
    done < "$manifest"
    [[ "$bad" -eq 0 ]] || die "Refusing to commit: $bad file(s) carry an unexpected delta."
    info "[2/3] per-file shape: only followup_kind + updated_at changed"

    # 3. Plan file, separately. aitasks/ and aiplans/ share ONE data worktree,
    #    so a single status call mixes them -- and the plan file is exempt from
    #    rule 2 because it carries the classification table.
    #
    #    Other changed plan files are REPORTED, not fatal: concurrent sessions
    #    legitimately edit their own plans, and failing on someone else's work
    #    would make this assertion unusable in a shared tree. Commit 2 is
    #    path-allowlisted, so a foreign plan edit cannot be swept in -- the
    #    warning exists so the operator does not stage it by hand.
    local plan_changed
    plan_changed="$(task_git status --porcelain -- "$PLAN_DIR" 2>/dev/null | awk '{print $2}' || true)"
    if [[ -n "$PLAN_FILE" ]]; then
        printf '%s\n' "$plan_changed" | grep -qxF "$PLAN_FILE" \
            || die "Expected plan file '$PLAN_FILE' to carry the classification table,
     but it shows no changes. Write the table into its Final Implementation
     Notes before committing."
        info "[3/3] plan file $PLAN_FILE carries the table (exempt from the two-line rule)"
        local foreign
        foreign="$(printf '%s\n' "$plan_changed" | grep -vxF "$PLAN_FILE" | grep . || true)"
        if [[ -n "$foreign" ]]; then
            warn "Other plan files are also modified -- almost certainly a concurrent"
            warn "session's work. Do NOT stage these; commit 2 must be path-allowlisted:"
            printf '    %s\n' "$foreign" >&2
        fi
    else
        info "[3/3] plan-file check skipped (pass --plan <path> to enable)"
    fi

    rm -f "$expected" "$actual"
    echo
    info "Delta verified. Safe to commit task data."
}

# --- main -------------------------------------------------------------------

case "$MODE" in
    dry-run)      do_dry_run ;;
    apply)        do_apply ;;
    resume)       do_resume ;;
    abandon)      do_abandon ;;
    verify-delta) do_verify_delta ;;
esac
