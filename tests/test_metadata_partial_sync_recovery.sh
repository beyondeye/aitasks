#!/usr/bin/env bash
# test_metadata_partial_sync_recovery.sh - the './ait sync' hint printed on a
# PARTIAL metadata update actually recovers while a live session holds a dirty
# task file (t1696).
#
# Run: bash tests/test_metadata_partial_sync_recovery.sh
#
# THE CLAIM UNDER TEST. aitask_usage_update.sh / aitask_verified_update.sh end
# UPDATED_REMOTE_ONLY (exit 3) when their metadata commit reached origin but not
# the local data branch, and every message on that path says "recover with
# './ait sync'". t1658_3 item #7 found that hint unreachable on a multi-agent
# box: sync deferred on the live-locked files (protected_dirty), and on a
# DIVERGED branch task_data_converge and sync each handed recovery to the other.
# t1725_3 (fast-forward when behind-only) and t1731 (guarded merge when
# diverged) fixed sync; this file pins that the hint and the recovery AGREE.
#
# WHY THE EXISTING TESTS DO NOT. test_task_push.sh Tests 37/38 execute the hint
# but hold no live-locked file. test_sync_guarded_merge.sh AC1/AC4 hold one but
# hand-build the divergence with a second clone, so no real metadata updater
# produced the state and no hint is ever read. Here the real producer makes the
# partial outcome, its stderr is checked for the hint, and the hint is run.

set -uo pipefail

TEST_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

PASS=0
FAIL=0
TOTAL=0

. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/sync_fixture.sh"

# --- Helpers --------------------------------------------------------------

dgit() { local t="$1"; shift; git -C "$t/local/.aitask-data" "$@"; }
dhead() { dgit "$1" rev-parse HEAD 2>/dev/null; }
remote_sha() { git -C "$1/remote.git" rev-parse refs/heads/aitask-data 2>/dev/null; }
sha_of() { sha256sum "$1" 2>/dev/null | cut -d' ' -f1; }
first_line() { printf '%s\n' "$1" | head -n1; }
ahead_of() { dgit "$1" rev-list --count '@{u}..HEAD' 2>/dev/null; }
behind_of() { dgit "$1" rev-list --count 'HEAD..@{u}' 2>/dev/null; }
is_ancestor() {
    if dgit "$1" merge-base --is-ancestor "$2" HEAD 2>/dev/null; then echo yes; else echo no; fi
}

MODELS=aitasks/metadata/models_claudecode.json
T10=aitasks/t10_alpha.md

# seed_models <tmpdir> — the registry the updater bumps, committed and pushed on
# the data branch (same shape as metadata_update_fixture.sh's _mdfix_write_models).
seed_models() {
    local t="$1"
    cat > "$t/local/.aitask-data/$MODELS" <<'EOF'
{
  "models": [
    {
      "name": "opus4_6",
      "cli_id": "claude-opus-4-6",
      "notes": "Test model",
      "verified": {
        "pick": 80
      }
    }
  ]
}
EOF
    dgit "$t" add "$MODELS"
    dgit "$t" commit -q -m "seed models"
    dgit "$t" push -q 2>/dev/null
}

# The protected file: t10 is locked by a LIVE process (this test's own shell), so
# sync's sweep leaves its modified tracked file dirty — the multi-agent condition.
protect_t10() {
    local t="$1"
    plant_lock "$t" 10 "$(lock_yaml_live 10)"
    printf 'edit10\n' >> "$t/local/.aitask-data/$T10"
}

# run_usage <tmpdir> — the real producer of the partial outcome. Stdout is
# echoed; stderr lands in <tmpdir>/usage_stderr; the exit status goes to
# <tmpdir>/usage_rc (callers capture stdout with $( ), so no assignment made in
# here would survive).
run_usage() {
    local t="$1" rc=0
    (
        cd "$t/local" || exit 1
        # The fixture's run_sync exports these inside its own subshell; reading
        # the untouched parent values here is exactly what is wanted.
        # shellcheck disable=SC2031
        PATH="$PWD/bin:$PATH" TEST_HOSTNAME="${TEST_HOSTNAME:-testhost}" \
            ./.aitask-scripts/aitask_usage_update.sh \
            --agent-string claudecode/opus4_6 --skill pick --silent 2>"$t/usage_stderr"
    ) || rc=$?
    echo "$rc" > "$t/usage_rc"
}
usage_rc() { cat "$1/usage_rc" 2>/dev/null; }
usage_err() { cat "$1/usage_stderr" 2>/dev/null; }

# pick_runs <tmpdir> <rev> — the all-time pick run count recorded at <rev>.
pick_runs() {
    dgit "$1" show "$2:$MODELS" 2>/dev/null \
        | jq -r '.models[] | select(.name == "opus4_6") | .usagestats.pick.all_time.runs'
}

# make_ff_partial <tmpdir> <label> — item #6's forcing move, then item #7's
# starting state: a local edit to the registry blocks the fast-forward, so the
# update lands on origin only; the probe edit is then reverted, leaving the
# branch behind 1 with only the live-held t10 dirty.
make_ff_partial() {
    local t="$1" label="$2" out
    printf '\n' >> "$t/local/.aitask-data/$MODELS"
    out="$(run_usage "$t")"
    assert_eq "$label: the update is a partial result" \
        "UPDATED_REMOTE_ONLY:claudecode/opus4_6:pick:1" "$out"
    assert_eq "$label: partial exit status is exactly 3" "3" "$(usage_rc "$t")"
    assert_contains "$label: the partial result names './ait sync' as the recovery" \
        "./ait sync" "$(usage_err "$t")"
    dgit "$t" checkout -q -- "$MODELS"
}

echo "=== the partial-outcome './ait sync' hint recovers with live-held files (t1696) ==="
echo ""

# --- Cell A: behind-only partial -> './ait sync' -> PULLED ------------------
echo "--- Cell A: fast-forwardable partial, protected t10 -> './ait sync' fast-forwards ---"
T="$(setup_repo)"
seed_models "$T"
protect_t10 "$T"
make_ff_partial "$T" "A"
P1="$(remote_sha "$T")"
dgit "$T" fetch -q origin 2>/dev/null

assert_eq "A: precondition — the metadata commit is not local" "no" "$(is_ancestor "$T" "$P1")"
assert_eq "A: precondition — behind 1" "1" "$(behind_of "$T")"
assert_eq "A: precondition — ahead 0" "0" "$(ahead_of "$T")"
assert_eq "A: precondition — only the protected t10 is dirty" " M $T10" \
    "$(dgit "$T" status --porcelain)"
PRE_HEAD="$(dhead "$T")"; PRE10="$(sha_of "$T/local/.aitask-data/$T10")"

# No pipeline: $? is the command substitution's own status, so a recovery that
# converges but still exits non-zero cannot pass on its output alone.
OUT="$(run_sync "$T")"
SYNC_RC=$?
assert_eq "A: the hinted recovery exits 0" "0" "$SYNC_RC"
assert_eq "A: the hinted recovery reports PULLED" "PULLED" "$(first_line "$OUT")"
assert_eq "A: the metadata commit is now local" "yes" "$(is_ancestor "$T" "$P1")"
dgit "$T" fetch -q origin 2>/dev/null
assert_eq "A: nothing left to pull" "0" "$(behind_of "$T")"
assert_eq "A: nothing left to push" "0" "$(ahead_of "$T")"
assert_eq "A: the protected t10 bytes are unchanged" "$PRE10" "$(sha_of "$T/local/.aitask-data/$T10")"
assert_eq "A: the protected t10 is still dirty" " M" \
    "$(dgit "$T" status --porcelain -- "$T10" | cut -c1-2)"
assert_not_contains "A: t10 rode along in no commit" "$T10" \
    "$(dgit "$T" log --name-only --format= "$PRE_HEAD..HEAD" 2>/dev/null)"

# --- Cell B: diverged partial (the absorbing state) -> './ait sync' -> MERGED --
echo "--- Cell B: diverged partial, protected t10 -> './ait sync' merges ---"
T="$(setup_repo)"
seed_models "$T"
protect_t10 "$T"
make_ff_partial "$T" "B"
P1="$(remote_sha "$T")"

# A local commit lands while origin is ahead: the branch is now diverged.
(
    cd "$T/local/.aitask-data" || exit 1
    printf 'local20\n' >> aitasks/t20_beta.md
    git add aitasks/t20_beta.md
    git commit -q -m "local: t20"
) >/dev/null 2>&1

# The next update in that state — the scope correction's "every subsequent pick":
# the converge seam declines (diverged), and one more commit lands on origin only.
OUT="$(run_usage "$T")"
assert_eq "B: the second update is also partial" \
    "UPDATED_REMOTE_ONLY:claudecode/opus4_6:pick:2" "$OUT"
assert_eq "B: partial exit status is exactly 3" "3" "$(usage_rc "$T")"
# The negative control: the seam reports diverged instead of healing it, so the
# state below is the one the task describes, not an already-converged branch.
assert_contains "B: the converge seam reports diverged" "[diverged]" "$(usage_err "$T")"
assert_contains "B: and names './ait sync' as the recovery" "./ait sync" "$(usage_err "$T")"
P2="$(remote_sha "$T")"
dgit "$T" fetch -q origin 2>/dev/null

assert_eq "B: precondition — the first metadata commit is not local" "no" "$(is_ancestor "$T" "$P1")"
assert_eq "B: precondition — the second metadata commit is not local" "no" "$(is_ancestor "$T" "$P2")"
assert_eq "B: precondition — ahead 1" "1" "$(ahead_of "$T")"
assert_eq "B: precondition — behind 2" "2" "$(behind_of "$T")"
PRE_HEAD="$(dhead "$T")"; PRE10="$(sha_of "$T/local/.aitask-data/$T10")"

OUT="$(run_sync "$T")"
SYNC_RC=$?
assert_eq "B: the hinted recovery exits 0" "0" "$SYNC_RC"
assert_eq "B: the hinted recovery reports MERGED" "MERGED" "$(first_line "$OUT")"
assert_eq "B: the first metadata commit is now local" "yes" "$(is_ancestor "$T" "$P1")"
assert_eq "B: the second metadata commit is now local" "yes" "$(is_ancestor "$T" "$P2")"
assert_contains "B: the local t20 commit survived" "local20" \
    "$(dgit "$T" show HEAD:aitasks/t20_beta.md 2>/dev/null)"
assert_eq "B: the merged registry carries both runs" "2" "$(pick_runs "$T" HEAD)"
dgit "$T" fetch -q origin 2>/dev/null
assert_eq "B: nothing left to pull" "0" "$(behind_of "$T")"
assert_eq "B: nothing left to push" "0" "$(ahead_of "$T")"
assert_eq "B: the remote holds our HEAD" "$(dhead "$T")" "$(remote_sha "$T")"
assert_eq "B: the protected t10 bytes are unchanged" "$PRE10" "$(sha_of "$T/local/.aitask-data/$T10")"
assert_eq "B: the protected t10 is still dirty" " M" \
    "$(dgit "$T" status --porcelain -- "$T10" | cut -c1-2)"
assert_not_contains "B: t10 rode along in no commit" "$T10" \
    "$(dgit "$T" log --name-only --format= "$PRE_HEAD..HEAD" 2>/dev/null)"

echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ "$FAIL" -eq 0 ]]; then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "SOME TESTS FAILED"
    exit 1
fi
