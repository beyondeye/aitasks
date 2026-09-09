#!/usr/bin/env bash
# test_task_data_writer_guard.sh — t1725_2
#
# Two defects, one guard:
#
#   F6  Mid-rebase the checked-out task file is origin's version, not the branch
#       tip, and every writer sed'd it anyway. task_git already refused at COMMIT
#       time — too late, the file was already corrupted. assert_task_data_writable
#       refuses BEFORE the write.
#   F7  `ait create --batch --commit` died when its commit failed, leaving the
#       file on disk under a claimed id; each retry claimed a fresh one
#       (t1722/t1723/t1724 are one follow-up spawned three times).
#
# THE TABLE IS THE AUDIT RECORD. A task-data writer missing from it is the hole.
# One row per physical script, and one row per guarded ENTRY POINT — a script row
# that passes via one entry point must not vouch for another.
#
# Counters: the rows run inside `( … )` subshells (the guard die()s, so it must
# be probed in one), whose in-process PASS/FAIL increments die at subshell exit.
# Hence the file-backed opt-in (CLAUDE.md, t1207).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
export PROJECT_DIR

. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/sync_fixture.sh"

assert_counters_init
# ONE combined EXIT trap. sync_fixture.sh installs its own
# `trap _sync_fixture_cleanup EXIT` at source time; a second `trap ... EXIT` for
# the counter file would REPLACE it and leak a full .aitask-scripts copy per
# fixture (the fixture's own comment measures a leaking suite in gigabytes).
trap 'rm -f "$AIT_ASSERT_COUNTER_FILE"; _sync_fixture_cleanup' EXIT

# The guard's own first sentence. Distinct from assert_data_worktree_clean's
# "is stuck mid-<state>." (pinned by test_task_commit_scoped.sh:269) precisely so
# a row can tell WHICH of the two guards refused.
GUARD_MSG="the checked-out task files are not"

# --- fixture helpers -------------------------------------------------------

# The data worktree's admin git-dir, asked for rather than hardcoded: a linked
# worktree's admin dir is not always .git/worktrees/-aitask-data.
data_gitdir() { (cd "$1/local" && git -C .aitask-data rev-parse --absolute-git-dir); }

plant_wedge()   { mkdir -p "$(data_gitdir "$1")/rebase-merge"; }
clear_wedge()   { local g; g="$(data_gitdir "$1")"; rm -rf "${g:?}/rebase-merge"; }

# Run a command inside the fixture repo, capturing stdout+stderr and the status.
# RUN_OUT / RUN_RC are the results. Not a command substitution around the whole
# thing: these commands die(), and we want the real exit status.
RUN_OUT=""; RUN_RC=0
run_in() {
    local tmpdir="$1"; shift
    RUN_RC=0
    RUN_OUT="$(cd "$tmpdir/local" && PATH="$PWD/bin:$PATH" TEST_HOSTNAME=testhost \
        AITASKS_LOCK_DIR="$tmpdir/locks" "$@" 2>&1)" || RUN_RC=$?
}

md5_of() { md5sum "$1" 2>/dev/null | awk '{print $1}'; }

echo "=== t1725_2: task-data writer guard ==="

TMP="$(setup_repo)"
( cd "$TMP/local" && ./.aitask-scripts/aitask_claim_id.sh --init ) >/dev/null 2>&1

# ===========================================================================
# A. Six-state coverage of the guard ITSELF (function level).
#
# _data_wedge_state reports all six AIT_GIT_INPROGRESS_STATES and the message
# interpolates the state, but every command-level row below plants only
# rebase-merge — so a regression in the lookup or message path for merge,
# cherry-pick, revert or bisect would pass all of them. test_task_git.sh Test 16
# does NOT close this: it proves assert_data_worktree_clean, a different function
# reached through a different git-dir resolver.
# ===========================================================================
echo "--- A: six-state coverage of assert_task_data_writable ---"

GITDIR_A="$(data_gitdir "$TMP")"

# Probes the guard in a subshell, because it die()s (exits the process).
probe_guard() {
    local root="$1"
    ( cd "$root" || exit 99
      # shellcheck source=/dev/null
      SCRIPT_DIR="$PWD/.aitask-scripts" source .aitask-scripts/lib/task_utils.sh >/dev/null 2>&1
      assert_task_data_writable >/dev/null 2>&1
    ) && echo "allowed" || echo "refused"
}
probe_guard_msg() {
    local root="$1"
    ( cd "$root" || exit 99
      # shellcheck source=/dev/null
      SCRIPT_DIR="$PWD/.aitask-scripts" source .aitask-scripts/lib/task_utils.sh >/dev/null 2>&1
      { assert_task_data_writable >/dev/null; } 2>&1
    ) || true
}

for spec_a in "rebase-merge:dir" "rebase-apply:dir" "MERGE_HEAD:file" \
              "CHERRY_PICK_HEAD:file" "REVERT_HEAD:file" "BISECT_LOG:file"; do
    state_a="${spec_a%%:*}"; kind_a="${spec_a##*:}"

    # Negative control BEFORE planting — otherwise "refused" proves nothing
    # about the state we are about to create.
    assert_eq_trim "A[$state_a]: clean worktree is allowed (control)" \
        "allowed" "$(probe_guard "$TMP/local")"

    if [[ "$kind_a" == "dir" ]]; then mkdir -p "$GITDIR_A/$state_a"; else : > "$GITDIR_A/$state_a"; fi

    assert_eq_trim "A[$state_a]: wedged worktree is refused" \
        "refused" "$(probe_guard "$TMP/local")"

    # The message must name THIS state. A merge announced as a rebase would hand
    # the user a recovery command that does not apply.
    assert_contains "A[$state_a]: the message names the actual state" \
        "mid-$state_a" "$(probe_guard_msg "$TMP/local")"
    assert_contains "A[$state_a]: it is OUR guard, not the commit guard" \
        "$GUARD_MSG" "$(probe_guard_msg "$TMP/local")"

    # The documented bypass still works.
    assert_eq_trim "A[$state_a]: AIT_GIT_SKIP_STATE_CHECK=1 bypasses" \
        "allowed" "$(AIT_GIT_SKIP_STATE_CHECK=1 probe_guard "$TMP/local")"

    rm -rf "${GITDIR_A:?}/$state_a"
done

# The one behaviour Test 16 structurally cannot cover, and the whole reason the
# guard calls _data_wedge_state rather than ait_data_inprogress_state: in LEGACY
# mode (no .aitask-data worktree) the old guard is a documented no-op, while this
# one still refuses. That assertion IS the difference between the two functions.
echo "--- A: legacy mode (the new guard's distinguishing behaviour) ---"
LEG="$(mktemp -d)"
(
  cd "$LEG" || exit 1
  git init -q .
  git config user.email t@t; git config user.name t
  mkdir -p aitasks/metadata aiplans .aitask-scripts/lib
  cp -r "$PROJECT_DIR/.aitask-scripts/lib/." .aitask-scripts/lib/
  echo x > f; git add -A; git -c user.email=t@t -c user.name=t commit -qm init
) >/dev/null 2>&1
mkdir -p "$LEG/.git/rebase-merge"

leg_probe() {
    local fn="$1"
    ( cd "$LEG" || exit 99
      # shellcheck source=/dev/null
      SCRIPT_DIR="$PWD/.aitask-scripts" source .aitask-scripts/lib/task_utils.sh >/dev/null 2>&1
      "$fn" >/dev/null 2>&1
    ) && echo "allowed" || echo "refused"
}
assert_eq_trim "A[legacy]: the NEW guard refuses a wedged legacy repo" \
    "refused" "$(leg_probe assert_task_data_writable)"
assert_eq_trim "A[legacy]: the OLD guard does not (documented no-op)" \
    "allowed" "$(leg_probe 'assert_data_worktree_clean')"
rm -rf "$LEG"

# ===========================================================================
# B. Command-level writer table — one row per script, one row per entry point.
# ===========================================================================
echo "--- B: writer table (guarded) ---"

plant_wedge "$TMP"

# Seed a task file whose bytes we can compare before/after. Each row takes its
# own before/after pair, so no file-level snapshot is kept.
SEED="$TMP/local/.aitask-data/aitasks/t10_alpha.md"

# Each row: description | command...
guarded_row() {
    local desc="$1"; shift
    local before after
    before="$(md5_of "$SEED")"
    run_in "$TMP" "$@"
    after="$(md5_of "$SEED")"
    assert_exit_nonzero_rc "$desc: refused (non-zero exit)" "$RUN_RC"
    assert_contains "$desc: it was OUR guard that refused" "$GUARD_MSG" "$RUN_OUT"
    assert_eq "$desc: task file bytes unchanged" "$before" "$after"
}

guarded_row "aitask_update.sh --batch" \
    ./.aitask-scripts/aitask_update.sh --batch 10 --priority low
guarded_row "aitask_note.sh (append)" \
    ./.aitask-scripts/aitask_note.sh 10 --from t20 --text "hello"
guarded_row "aitask_note.sh read (receipt)" \
    ./.aitask-scripts/aitask_note.sh read 10 --by t10 --ids x --mode explicit
guarded_row "aitask_gate.sh append" \
    ./.aitask-scripts/aitask_gate.sh append 10 risk_evaluated pass
guarded_row "aitask_gate.sh begin-procedure" \
    ./.aitask-scripts/aitask_gate.sh begin-procedure 10 risk_evaluated
guarded_row "aitask_archive.sh" \
    ./.aitask-scripts/aitask_archive.sh 10
guarded_row "aitask_plan_externalize.sh" \
    ./.aitask-scripts/aitask_plan_externalize.sh 10 --force --no-worktree
guarded_row "aitask_zip_old.sh" \
    ./.aitask-scripts/aitask_zip_old.sh
guarded_row "aitask_migrate_archives.sh" \
    ./.aitask-scripts/aitask_migrate_archives.sh
guarded_row "aitask_verification_followup.sh" \
    ./.aitask-scripts/aitask_verification_followup.sh --from 10 --item 1

# run_interactive_mode is its OWN entry point: the batch row above cannot vouch
# for it. Reachable headlessly because the guard is the function's first
# statement, ahead of the fzf check.
guarded_row "aitask_update.sh (interactive entry)" \
    ./.aitask-scripts/aitask_update.sh

# finalize_draft is a THIRD create entry point (neither --batch --commit nor the
# draft path): it claims an id and commits, so it is guarded. Drive it with a real
# draft, created while the worktree was still clean.
clear_wedge "$TMP"
run_in "$TMP" ./.aitask-scripts/aitask_create.sh --batch --name fin_probe --desc d
FIN_DRAFT="$(printf '%s\n' "$RUN_OUT" | grep -oE 'aitasks/new/draft_[^ ]*\.md' | tail -1)"
assert_contains "finalize_draft setup: a draft exists" "aitasks/new/" "${FIN_DRAFT:-}"
plant_wedge "$TMP"
run_in "$TMP" ./.aitask-scripts/aitask_create.sh --batch --finalize "$FIN_DRAFT"
assert_exit_nonzero_rc "aitask_create.sh --finalize (finalize_draft): refused" "$RUN_RC"
assert_contains "aitask_create.sh --finalize: our guard" "$GUARD_MSG" "$RUN_OUT"
assert_file_exists "aitask_create.sh --finalize: the draft survives the refusal" \
    "$TMP/local/$FIN_DRAFT"

# zip_old's `unpack` subcommand writes task files back OUT of a bundle and takes a
# different path through main() than the bundling flow, so it needs its own row.
run_in "$TMP" ./.aitask-scripts/aitask_zip_old.sh unpack 10
assert_exit_nonzero_rc "aitask_zip_old.sh unpack: refused" "$RUN_RC"
assert_contains "aitask_zip_old.sh unpack: our guard" "$GUARD_MSG" "$RUN_OUT"

# aitask_create.sh gets its own F7 rows below (the id-claim assertion is the
# point), but the refusal itself belongs in the table too.
run_in "$TMP" ./.aitask-scripts/aitask_create.sh --batch --commit --name wedge_probe --desc d
assert_exit_nonzero_rc "aitask_create.sh --batch --commit: refused" "$RUN_RC"
assert_contains "aitask_create.sh --batch --commit: our guard" "$GUARD_MSG" "$RUN_OUT"

echo "--- B: exempt read-only scripts still run under the wedge ---"
exempt_row() {
    local desc="$1"; shift
    run_in "$TMP" "$@"
    assert_not_contains "$desc: not refused by the write guard" "$GUARD_MSG" "$RUN_OUT"
}
exempt_row "aitask_ls.sh"                    ./.aitask-scripts/aitask_ls.sh 5
exempt_row "aitask_query_files.sh resolve"   ./.aitask-scripts/aitask_query_files.sh resolve 10
exempt_row "aitask_lock.sh --check"          ./.aitask-scripts/aitask_lock.sh --check 10
exempt_row "aitask_archive.sh --dry-run"     ./.aitask-scripts/aitask_archive.sh 10 --dry-run
exempt_row "aitask_zip_old.sh --dry-run"     ./.aitask-scripts/aitask_zip_old.sh --dry-run
# The read-only short-circuit must survive: once a plan EXISTS, a no-force call
# short-circuits to PLAN_EXISTS and writes nothing — and Step 8 makes exactly
# that call on every task. Note the precondition: without an existing plan the
# same command WOULD write one, and being refused then is correct.
clear_wedge "$TMP"
( cd "$TMP/local" && mkdir -p aiplans && printf -- '---\nTask: t10_alpha.md\n---\nplan\n' \
    > aiplans/p10_alpha.md ) >/dev/null 2>&1
plant_wedge "$TMP"
run_in "$TMP" ./.aitask-scripts/aitask_plan_externalize.sh 10
assert_contains "aitask_plan_externalize.sh: existing plan short-circuits" \
    "PLAN_EXISTS" "$RUN_OUT"
assert_not_contains "aitask_plan_externalize.sh (read-only short-circuit) not refused" \
    "$GUARD_MSG" "$RUN_OUT"

echo "--- B: audited, deliberately NOT guarded ---"
# Recorded so the omission is a decision on the record rather than an oversight.
# Metadata-only writers: the corruption class is a lost list entry, not a lost
# task status, and aitask_pick_own.sh runs on EVERY pick — guarding it would make
# a wedged worktree block task selection outright.
for ng in aitask_pick_own aitask_usage_update aitask_verified_update aitask_add_model; do
    # `grep -c` PRINTS 0 and EXITS 1 on no-match, so `|| echo 0` would append a
    # second line. Count the matching lines instead, which is 0 either way.
    ng_hits="$(grep -c 'assert_task_data_writable' "$PROJECT_DIR/.aitask-scripts/$ng.sh" 2>/dev/null || true)"
    assert_eq "audited-not-guarded: $ng.sh (metadata only, by decision)" \
        "0" "${ng_hits:-0}"
done
# Drafts under aitasks/new/ are gitignored and never committed — the one path
# that is SUPPOSED to work while the worktree is broken.
run_in "$TMP" ./.aitask-scripts/aitask_create.sh --batch --name draft_probe --desc d
assert_exit_zero_rc "aitasks/new/ draft creation works under a wedge" "$RUN_RC"

clear_wedge "$TMP"

# ===========================================================================
# F6 reproduction + negative control
# ===========================================================================
echo "--- F6: a frontmatter write against a stale checked-out base ---"

# Commit the real state, then make the CHECKED-OUT file the stale version, which
# is what a stopped rebase leaves behind.
(
  cd "$TMP/local/.aitask-data" || exit 1
  printf -- '---\nstatus: Implementing\nactive_gates: [risk_evaluated]\n---\nA\n' > aitasks/t10_alpha.md
  git add -A && git commit -qm "t10 implementing"
) >/dev/null 2>&1
printf -- '---\nstatus: Ready\n---\nA\n' > "$SEED"   # the stale content
plant_wedge "$TMP"
STALE_MD5="$(md5_of "$SEED")"

run_in "$TMP" ./.aitask-scripts/aitask_update.sh --batch 10 --risk-code-health low
assert_exit_nonzero_rc "F6: the write is refused" "$RUN_RC"
assert_contains "F6: the message offers retry" "retry in a few seconds" "$RUN_OUT"
assert_contains "F6: the message offers abort"  "rebase --abort" "$RUN_OUT"
assert_eq "F6: the stale file was NOT modified" "$STALE_MD5" "$(md5_of "$SEED")"

clear_wedge "$TMP"
# Negative control: the very same update succeeds on a clean worktree. Without
# this, "refused" could mean the command was simply broken.
(cd "$TMP/local/.aitask-data" && git checkout -q -- aitasks/t10_alpha.md) >/dev/null 2>&1
run_in "$TMP" ./.aitask-scripts/aitask_update.sh --batch 10 --risk-code-health low
assert_exit_zero_rc_out "F6 control: the same update succeeds when clean" "$RUN_RC" "$RUN_OUT"

# ===========================================================================
# F7 — the id must not be burned
# ===========================================================================
echo "--- F7: wedge refuses BEFORE the id is claimed ---"
peek() { (cd "$TMP/local" && ./.aitask-scripts/aitask_claim_id.sh --peek 2>/dev/null); }

plant_wedge "$TMP"
PEEK_BEFORE="$(peek)"
run_in "$TMP" ./.aitask-scripts/aitask_create.sh --batch --commit --name burn_probe --desc d
PEEK_AFTER="$(peek)"
assert_exit_nonzero_rc "F7 wedge: create refused" "$RUN_RC"
assert_eq "F7 wedge: the id counter did NOT move" "$PEEK_BEFORE" "$PEEK_AFTER"
clear_wedge "$TMP"

echo "--- F7: commit failure keeps the file, exits 0, burns exactly one id ---"

# Force the commit to fail with an index.lock in the data worktree's admin
# git-dir. No test plants a worktree index.lock today, so ASSERT THE MUTATION
# LANDED before trusting anything downstream — otherwise every assertion below
# passes vacuously against a commit that simply succeeded.
LOCKF="$(data_gitdir "$TMP")/index.lock"
: > "$LOCKF"
assert_file_exists "F7 lock: the index.lock fixture is in place" "$LOCKF"
HEAD_BEFORE="$(data_head "$TMP")"
PEEK_BEFORE="$(peek)"

run_in "$TMP" ./.aitask-scripts/aitask_create.sh --batch --commit --silent --name lockfail_silent --desc d
SILENT_OUT="$RUN_OUT"; SILENT_RC="$RUN_RC"
PEEK_AFTER="$(peek)"

assert_eq "F7 lock: the commit really did fail (HEAD unmoved)" \
    "$HEAD_BEFORE" "$(data_head "$TMP")"
assert_exit_zero_rc "F7 lock: create exits 0 (the caller has no reason to retry)" "$SILENT_RC"
assert_contains "F7 lock: stderr says NOT committed" "NOT committed" "$SILENT_OUT"
# Inspect the WARNING LINE, not the whole capture. The helper re-emits git's
# stderr unconditionally, so asserting "index.lock" anywhere in the output would
# pass even with the AIT_COMMIT_SCOPED_ERR plumbing removed — a vacuous check.
# Only the composed line proves the diagnostic was threaded into the warning.
SILENT_WARN="$(printf '%s\n' "$SILENT_OUT" | grep -m1 'NOT committed')"
assert_contains "F7 lock: the composed warning carries git's own words" \
    "index.lock" "${SILENT_WARN:-}"
assert_not_contains "F7 lock: not the no-diagnostic fallback" \
    "git reported no message" "${SILENT_WARN:-}"
assert_eq "F7 lock: exactly ONE id was consumed" \
    "$((PEEK_BEFORE + 1))" "$PEEK_AFTER"

# stdout shape, both modes, against their successful counterparts.
SILENT_PATH="$(printf '%s\n' "$SILENT_OUT" | grep -E '^aitasks/.*\.md$' | tail -1)"
assert_contains "F7 lock (--silent): stdout carries the bare path" "aitasks/" "${SILENT_PATH:-}"

run_in "$TMP" ./.aitask-scripts/aitask_create.sh --batch --commit --name lockfail_normal --desc d
assert_exit_zero_rc "F7 lock (normal): exits 0" "$RUN_RC"
assert_contains "F7 lock (normal): stdout uses the success shape 'Created:'" "Created:" "$RUN_OUT"
assert_contains "F7 lock (normal): stderr still says NOT committed" "NOT committed" "$RUN_OUT"

rm -f "$LOCKF"

# The sweep: a second create is never needed, which the peek delta already
# pinned. Here we prove the abandoned file is picked up under its OWN task id.
OUT_SYNC="$(run_sync "$TMP")"
assert_contains "F7 sweep: the orphaned file is auto-committed before sync" \
    "Auto-commit" "$(data_log "$TMP")$OUT_SYNC$(sync_err "$TMP")"

# ===========================================================================
# D. The same commit failure on the CHILD branch. Its own rows: the parent
#    branch does not cover it — the child path additionally holds a creation
#    lock, and the removed die used to release it via _child_lock_exit_trap.
# ===========================================================================
echo "--- D: child-branch commit failure releases the lock ---"

# A parent to hang children off.
run_in "$TMP" ./.aitask-scripts/aitask_create.sh --batch --commit --name d_parent --desc d
assert_exit_zero_rc "D setup: parent created" "$RUN_RC"
D_PARENT="$(printf '%s\n' "$RUN_OUT" | grep -oE 't[0-9]+_d_parent' | head -1 | tr -d 't' | cut -d_ -f1)"
assert_contains "D setup: parent id resolved" "$D_PARENT" "${D_PARENT:-}"

: > "$LOCKF"
assert_file_exists "D: index.lock fixture in place" "$LOCKF"
HEAD_BEFORE="$(data_head "$TMP")"

run_in "$TMP" ./.aitask-scripts/aitask_create.sh --batch --commit --silent \
    --parent "$D_PARENT" --name d_child_silent --desc d --no-sibling-dep
assert_eq "D: the child commit really did fail (HEAD unmoved)" \
    "$HEAD_BEFORE" "$(data_head "$TMP")"
assert_exit_zero_rc "D (--silent): exits 0" "$RUN_RC"
assert_contains "D (--silent): stderr says NOT committed" "NOT committed" "$RUN_OUT"
D_WARN="$(printf '%s\n' "$RUN_OUT" | grep -m1 'NOT committed')"
assert_contains "D (--silent): the composed warning carries git's own words" \
    "index.lock" "${D_WARN:-}"
assert_not_contains "D (--silent): not the no-diagnostic fallback" \
    "git reported no message" "${D_WARN:-}"

run_in "$TMP" ./.aitask-scripts/aitask_create.sh --batch --commit \
    --parent "$D_PARENT" --name d_child_normal --desc d --no-sibling-dep
assert_exit_zero_rc "D (normal): exits 0" "$RUN_RC"
assert_contains "D (normal): stdout uses the success shape" "Created:" "$RUN_OUT"
assert_contains "D (normal): stderr still says NOT committed" "NOT committed" "$RUN_OUT"

rm -f "$LOCKF"

# THE load-bearing assertion: the child creation lock was RELEASED.
#
# "The next child creates fine" alone does NOT prove it — a lock leaked by a
# process that has since exited is reclaimed by stale_lock's reaper, so the next
# create succeeds either way. (Verified: mutating the release away leaves that
# assertion green.) The discriminating check is that the lock directory is gone
# the moment the failing create returns.
assert_dir_not_exists "D: the child creation lock was released, not leaked" \
    "$TMP/locks/child_${D_PARENT}"

# Kept as the behavioural companion: it also pins that get_next_child_number
# advanced rather than re-issuing the failed child's number.
run_in "$TMP" ./.aitask-scripts/aitask_create.sh --batch --commit \
    --parent "$D_PARENT" --name d_child_after --desc d --no-sibling-dep
assert_exit_zero_rc_out "D: the NEXT child creates fine" "$RUN_RC" "$RUN_OUT"
assert_not_contains "D: and it really committed this time" "NOT committed" "$RUN_OUT"

# ===========================================================================
# D2. finalize_draft's OWN commit-failure branches. The batch rows above cannot
#     vouch for them: finalize_draft is a separate entry point with its own
#     parent and child branches, and its own trailing output block.
# ===========================================================================
echo "--- D2: finalize_draft commit failure (parent and child branches) ---"

# Parent branch. Draft created clean, then the commit forced to fail.
run_in "$TMP" ./.aitask-scripts/aitask_create.sh --batch --name d2_parent_draft --desc d
D2_DRAFT="$(printf '%s\n' "$RUN_OUT" | grep -oE 'aitasks/new/draft_[^ ]*\.md' | tail -1)"
assert_contains "D2 setup: parent draft exists" "aitasks/new/" "${D2_DRAFT:-}"
: > "$LOCKF"
assert_file_exists "D2: index.lock fixture in place" "$LOCKF"
HEAD_BEFORE="$(data_head "$TMP")"
PEEK_BEFORE="$(peek)"
run_in "$TMP" ./.aitask-scripts/aitask_create.sh --batch --finalize "$D2_DRAFT"
assert_eq "D2 parent: the commit really did fail (HEAD unmoved)" \
    "$HEAD_BEFORE" "$(data_head "$TMP")"
assert_exit_zero_rc "D2 parent: finalize exits 0, not die" "$RUN_RC"
assert_contains "D2 parent: stderr says NOT committed" "NOT committed" "$RUN_OUT"
D2_WARN="$(printf '%s\n' "$RUN_OUT" | grep -m1 'NOT committed')"
assert_contains "D2 parent: the composed warning carries git's own words" \
    "index.lock" "${D2_WARN:-}"
assert_eq "D2 parent: exactly ONE id consumed" "$((PEEK_BEFORE + 1))" "$(peek)"
assert_file_not_exists "D2 parent: the draft was consumed" "$TMP/local/$D2_DRAFT"

# Child branch — additionally holds the creation lock.
rm -f "$LOCKF"
run_in "$TMP" ./.aitask-scripts/aitask_create.sh --batch --commit --name d2_parent --desc d
D2_PARENT="$(printf '%s\n' "$RUN_OUT" | grep -oE 't[0-9]+_d2_parent' | head -1 | tr -d 't' | cut -d_ -f1)"
run_in "$TMP" ./.aitask-scripts/aitask_create.sh --batch --parent "$D2_PARENT" \
    --name d2_child_draft --desc d --no-sibling-dep
D2_CDRAFT="$(printf '%s\n' "$RUN_OUT" | grep -oE 'aitasks/new/draft_[^ ]*\.md' | tail -1)"
assert_contains "D2 setup: child draft exists" "aitasks/new/" "${D2_CDRAFT:-}"
: > "$LOCKF"
HEAD_BEFORE="$(data_head "$TMP")"
run_in "$TMP" ./.aitask-scripts/aitask_create.sh --batch --finalize "$D2_CDRAFT"
assert_eq "D2 child: the commit really did fail (HEAD unmoved)" \
    "$HEAD_BEFORE" "$(data_head "$TMP")"
assert_exit_zero_rc "D2 child: finalize exits 0, not die" "$RUN_RC"
assert_contains "D2 child: stderr says NOT committed" "NOT committed" "$RUN_OUT"
assert_dir_not_exists "D2 child: the creation lock was released, not leaked" \
    "$TMP/locks/child_${D2_PARENT}"
rm -f "$LOCKF"

# ===========================================================================
# D3. mktemp failure must degrade, never abort. An unchecked assignment would
#     exit the process under the callers' set -e AFTER the file was written and
#     the id claimed — recreating the very retry-and-burn-an-id defect (F7).
# ===========================================================================
# Driven at FUNCTION level, deliberately. An end-to-end create cannot isolate
# this: aitask_create.sh has its own unchecked `mktemp` in claim_parent_id_once
# (:1046) whose failure is swallowed by the surrounding command substitution, so
# an unusable TMPDIR makes it emit a task file with an EMPTY id (`t_<name>.md`)
# and exit 0. That is a separate pre-existing defect, recorded as an upstream
# defect; routing this row through create would assert around it instead of
# testing the helper.
echo "--- D3: an unusable TMPDIR must degrade the helper, not abort the caller ---"

# (a) TMPDIR unusable, commit CAN succeed -> helper works, no diagnostic, no abort.
D3_OUT="$(
  cd "$TMP/local" || exit 99
  set -e                                   # the callers' mode, which is the point
  # shellcheck source=/dev/null
  SCRIPT_DIR="$PWD/.aitask-scripts" source .aitask-scripts/lib/task_utils.sh >/dev/null 2>&1
  export TMPDIR="$TMP/no-such-tmpdir-$$"
  printf -- '---\nstatus: Ready\n---\nD3\n' > .aitask-data/aitasks/t20_beta.md
  rc=0
  task_git_commit_scoped "ait: d3 probe" aitasks/t20_beta.md >/dev/null 2>&1 || rc=$?
  printf 'REACHED rc=%s err=[%s]\n' "$rc" "${AIT_COMMIT_SCOPED_ERR:-}"
)" || true
assert_contains "D3a: the helper RETURNED — set -e did not abort the caller" \
    "REACHED" "$D3_OUT"
assert_contains "D3a: and the commit still succeeded" "rc=0" "$D3_OUT"
assert_contains "D3a: with an empty diagnostic (no capture file available)" \
    "err=[]" "$D3_OUT"

# (b) TMPDIR unusable AND the commit fails -> returns 1 with an empty diagnostic,
#     which is the contract warn_task_written_not_committed falls back on.
: > "$LOCKF"
D3_OUT="$(
  cd "$TMP/local" || exit 99
  set -e
  # shellcheck source=/dev/null
  SCRIPT_DIR="$PWD/.aitask-scripts" source .aitask-scripts/lib/task_utils.sh >/dev/null 2>&1
  export TMPDIR="$TMP/no-such-tmpdir-$$"
  printf -- '---\nstatus: Ready\n---\nD3b\n' > .aitask-data/aitasks/t30_gamma.md
  rc=0
  task_git_commit_scoped "ait: d3b probe" aitasks/t30_gamma.md >/dev/null 2>&1 || rc=$?
  printf 'REACHED rc=%s err=[%s]\n' "$rc" "${AIT_COMMIT_SCOPED_ERR:-}"
)" || true
rm -f "$LOCKF"
assert_contains "D3b: the helper RETURNED rather than aborting" "REACHED" "$D3_OUT"
assert_contains "D3b: it reports failure normally" "rc=1" "$D3_OUT"
assert_contains "D3b: with an empty diagnostic, not a crash" "err=[]" "$D3_OUT"

# ===========================================================================
# E. A wedge at commit time is refused, not absorbed.
# ===========================================================================
echo "--- E1: already wedged when the commit helper is entered ---"
plant_wedge "$TMP"
PEEK_BEFORE="$(peek)"
run_in "$TMP" ./.aitask-scripts/aitask_create.sh --batch --commit --name e1_probe --desc d
assert_exit_nonzero_rc "E1: refused" "$RUN_RC"
assert_contains "E1: the guard's message reaches the terminal" "$GUARD_MSG" "$RUN_OUT"
assert_not_contains "E1: NOT absorbed as a recoverable uncommitted create" \
    "NOT committed" "$RUN_OUT"
assert_eq "E1: no id burned" "$PEEK_BEFORE" "$(peek)"
clear_wedge "$TMP"

# E1b — the SHARED helper's own preflight. E1 above exercises aitask_create.sh's
# guard, which fires long before task_git_commit_scoped is reached, so it says
# nothing about the helper. This matters for the helper's other callers
# (aitask_pick_own.sh, aitask_issue_import.sh) which have no guard of their own:
# without the unredirected preflight, task_git's internal die would land in the
# helper's stderr temp file and the process would exit before flushing it —
# a refusal with no explanation.
echo "--- E1b: the shared commit helper surfaces its refusal to the terminal ---"
plant_wedge "$TMP"
HELPER_OUT="$(
  cd "$TMP/local" || exit 99
  # shellcheck source=/dev/null
  SCRIPT_DIR="$PWD/.aitask-scripts" source .aitask-scripts/lib/task_utils.sh >/dev/null 2>&1
  task_git_commit_scoped "probe" aitasks/t10_alpha.md 2>&1 >/dev/null
)" || true
assert_contains "E1b: the wedge message reaches stderr, not the temp file" \
    "stuck mid-rebase-merge" "$HELPER_OUT"
clear_wedge "$TMP"

echo "--- E2: wedge opens AFTER the helper's preflight (injected race) ---"
# The seam lives inside task_git_commit_scoped, after its preflight assert and
# before the guarded git call. A seam ahead of the helper would be caught by the
# preflight and prove nothing about this window.
#
# E2 asserts the REFUSAL SHAPE ONLY and is deliberately silent about the guard's
# message, in both directions. The message is captured into the helper's temp
# file and lost when die exits the process — a documented residual — so requiring
# it would reject the intended implementation, and requiring its ABSENCE would
# pin the residual as a contract and break a later live-forwarding fix.
HEAD_BEFORE="$(data_head "$TMP")"

# The seam has TWO gates (the env var alone must never eval code in a helper four
# production scripts use), so the fixture opts in with the on-disk marker as
# well. Assert the opt-in actually took: without the marker the seam is inert and
# every assertion below would pass for the wrong reason.
SEAM_MARKER="$TMP/locks/.ait_commit_scoped_test_seams"
mkdir -p "$(dirname "$SEAM_MARKER")" && : > "$SEAM_MARKER"
assert_file_exists "E2: the test-seam marker is in place" "$SEAM_MARKER"

RUN_RC=0
RUN_OUT="$(cd "$TMP/local" && PATH="$PWD/bin:$PATH" TEST_HOSTNAME=testhost \
    AITASKS_LOCK_DIR="$TMP/locks" \
    AIT_COMMIT_SCOPED_SEAM_PREGIT="mkdir -p '$(data_gitdir "$TMP")/rebase-merge'" \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name e2_probe --desc d 2>&1)" || RUN_RC=$?
assert_contains "E2: the seam actually fired" "TEST SEAM ACTIVE" "$RUN_OUT"

assert_exit_nonzero_rc "E2: refused (non-zero exit)" "$RUN_RC"
assert_not_contains "E2: no recovery warning — the wedge was not absorbed" \
    "NOT committed" "$RUN_OUT"
assert_not_contains "E2: no path on stdout" "Created:" "$RUN_OUT"
assert_eq "E2: nothing was committed" "$HEAD_BEFORE" "$(data_head "$TMP")"
clear_wedge "$TMP"

# ===========================================================================
echo ""
echo "==============================="
assert_counters_load
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ "$FAIL" -eq 0 ]]; then echo "ALL TESTS PASSED"; else echo "SOME TESTS FAILED ($FAIL)"; fi
[[ "$FAIL" -eq 0 ]]
