#!/usr/bin/env bash
# test_staged_entry_ownership.sh - why a wedged cleanup must PRESERVE the paths a
# run staged, and how `ait git-health` reports staged entries whose ownership is
# uncertain (t2277).
#
# Run: bash tests/test_staged_entry_ownership.sh
#
# ait_unstage_staged_by_us (lib/task_utils.sh) leaves the entries a run staged in
# the SHARED .aitask-data index, and names them, when the data worktree is
# wedged. These tests drive REAL git operations to a stop — no fabricated index
# entries, no planted MERGE_HEAD — and show that the entries it leaves cannot be
# proved ours, and that both ways out of the operation act on them.
#
# --- Measured (git 2.56, planning scratch repos; t2277) ---------------------
# A new file of ours staged (absent from HEAD), then the operation is started:
#
#   operation                     | outcome
#   ------------------------------|---------------------------------------------
#   merge / rebase / pull (either)| REFUSES — "index contains uncommitted
#   / cherry-pick / revert        |   changes" / "would be overwritten"; no wedge
#   merge|rebase --autostash      | wedges; our entry is moved INTO the stash, so
#                                 |   a same-path index entry is the operation's
#   am                            | refuses, but leaves rebase-apply/ — a wedge
#                                 |   with our entry still ours
#   bisect start                  | wedges (BISECT_LOG); our entry still ours
#
# And an operation that starts in the gap between the helper's in-loop guard and
# its `add` takes our entry into its own index. C1 below pins the consequence:
# with no autostash, "ours" (R2) and "the merge's" have byte-identical facts —
# ls-files -s, HEAD absence, no unmerged entry, MERGE_HEAD present,
# MERGE_AUTOSTASH absent. No check over the index or the wedge markers can tell
# them apart, so the cleanup leaves both and names them.
#
# Preventing that interleaving among the framework's own writers is
# serialization — t1678's data_index lock adoption — not this file's subject.
#
# --- What each case discriminates ------------------------------------------
#   R1     the counter-example through the real caller: a real
#          `merge --autostash` after our add. The entry passes every check the
#          t2271 review rejected, yet it is the merge's; the merge commit keeps it.
#   R1-NC  NEGATIVE CONTROL: the reset an unconditional cleanup would run drops
#          the incoming file from the merge commit — the harm, asserted directly.
#   R2     a real merge started in the guard→add gap: the entry IS ours, and is
#          still left (the cost of the limitation, pinned so it is not "fixed").
#   R2c/a  why the guidance says "inspect before continuing OR aborting":
#          committing the merge commits the unrelated file, and `merge --abort`
#          deletes it from the index and the worktree.
#   C1     the ours/not-ours pair with identical facts (raw git, no helper).
#   H1-H4  the git-health report: clean, listed, unreadable, capped.
#
# --- Mutations (each MEASURED: a copy of task_utils.sh with the change, loaded
# through TSO_LIB_OVERRIDE, then this file re-run) ---------------------------
#   mutation                                        | assertions that fail
#   ------------------------------------------------|---------------------------
#   M1 cleanup resets on a wedge (unguarded         | R1 (blob, health lists it,
#      _ait_data_git reset — the bypass t2271       |   PRESERVED), R2 (left,
#      rejected)                                    |   health x2), R2c, R2a, C1
#                                                   |   — 10 of 75
#   M2 git-health ignores the diff exit status      | H3 x3
#   M3 git-health listing uncapped                  | H4 (20 listed)
#   M4 git-health drops the in-progress line        | R1 health (op named), R2
#                                                   |   health x5 — 6
#   M5 cleanup warning back to "Once the operation  | R1 + R2 (cleanup wording)
#      is resolved … unstage" (pre-t2277 text)      |
#   R1-NC passes under every mutant: it drives git directly, and is the
#   positive proof that the M1 reset is harmful, not a check of the library.
#
# All assertions run in the main shell, so the in-process counters are enough.

set -uo pipefail

TEST_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

PASS=0
FAIL=0
TOTAL=0

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=lib/sync_fixture.sh
. "$PROJECT_DIR/tests/lib/sync_fixture.sh"

COMMIT_SH="./.aitask-scripts/aitask_task_commit.sh"
OURS="aitasks/t86_first.md"
OURS_CONTENT=$'---\nstatus: Ready\n---\nFirst.\n'
CONFLICTED="aitasks/t10_alpha.md"
BYSTANDER="aitasks/t20_beta.md"
REAL_GIT="$(command -v git)"

data_git() { local t="$1"; shift; "$REAL_GIT" -C "$t/local/.aitask-data" "$@" 2>/dev/null; }
data_gitdir() { data_git "$1" rev-parse --absolute-git-dir; }
in_head() { data_git "$1" cat-file -e "HEAD:$2" && echo present || echo absent; }

# own_fixture — a branch-mode repo whose data branch has three lines of history:
#   incoming        edits t10_alpha.md AND adds t86_first.md with exactly the
#                   content our run will write;
#   incoming_noadd  edits t10_alpha.md only;
#   aitask-data     a conflicting edit of t10_alpha.md (checked out).
# Both merges therefore stop on t10_alpha.md.
own_fixture() {
    local t
    t="$(setup_repo)"
    if [[ -n "${TSO_LIB_OVERRIDE:-}" ]]; then
        cp -- "$TSO_LIB_OVERRIDE" "$t/local/.aitask-scripts/lib/task_utils.sh"
    fi
    mkdir -p "$t/tmp"
    (
        cd "$t/local/.aitask-data" || exit 1
        g() { "$REAL_GIT" "$@"; }
        g checkout -q -b incoming
        printf -- '---\nstatus: Ready\n---\nA from incoming\n' > "$CONFLICTED"
        printf '%s' "$OURS_CONTENT" > "$OURS"
        g add -- "$CONFLICTED" "$OURS"
        g commit -q -m "incoming: edit t10, add t86"
        g checkout -q -b incoming_noadd aitask-data
        printf -- '---\nstatus: Ready\n---\nA from incoming_noadd\n' > "$CONFLICTED"
        g commit -q -am "incoming_noadd: edit t10"
        g checkout -q aitask-data
        printf -- '---\nstatus: Ready\n---\nA local\n' > "$CONFLICTED"
        g commit -q -am "local: edit t10"
    ) >/dev/null 2>&1
    echo "$t"
}

# op_shim <t> <when> <op…> — a PATH `git` that, the FIRST time `add` is invoked
# with $OURS as its last argument, runs the REAL `git -C .aitask-data <op…>`
# either right AFTER the real add (when=after) or right BEFORE it (when=before:
# the guard→add gap). Everything else is the real git.
op_shim() {
    local t="$1" when="$2"; shift 2
    local data op
    data="$t/local/.aitask-data"
    printf -v op '%q ' "$@"
    cat > "$t/local/bin/git" <<SHIM
#!/usr/bin/env bash
args=("\$@"); i=0; sub=""
while (( i < \${#args[@]} )); do
    case "\${args[i]}" in
        -C|-c) i=\$((i + 2)) ;;
        -*) i=\$((i + 1)) ;;
        *) sub="\${args[i]}"; break ;;
    esac
done
last="\${args[\${#args[@]}-1]:-}"
if [[ "\$sub" == add && "\$last" == "$OURS" && ! -e "$t/op_fired" ]]; then
    : > "$t/op_fired"
    if [[ "$when" == before ]]; then
        "$REAL_GIT" -C "$data" $op >/dev/null 2>&1
        exec "$REAL_GIT" "\$@"
    fi
    "$REAL_GIT" "\$@"; rc=\$?
    "$REAL_GIT" -C "$data" $op >/dev/null 2>&1
    exit \$rc
fi
exec "$REAL_GIT" "\$@"
SHIM
    chmod +x "$t/local/bin/git"
}

# run_commit <t> <path>... — the real caller, with its own EXIT trap. Sets
# RUN_OUT (stdout+stderr) / RUN_RC.
run_commit() {
    local t="$1"; shift
    printf '%s' "$OURS_CONTENT" > "$t/local/$OURS"
    RUN_RC=0
    RUN_OUT="$(
        cd "$t/local" || exit 99
        export PATH="$PWD/bin:$PATH" TEST_HOSTNAME=testhost TMPDIR="$t/tmp"
        "$COMMIT_SH" -m "ait: add t86" "$@" 2>&1
    )" || RUN_RC=$?
    rm -f "$t/local/bin/git"
}

# health <t> — `ait git-health` in the fixture; sets HEALTH_OUT (both streams).
health() {
    local t="$1"
    HEALTH_OUT="$(
        cd "$t/local" || exit 99
        export PATH="$PWD/bin:$PATH" TEST_HOSTNAME=testhost TMPDIR="$t/tmp"
        ./ait git-health 2>&1
    )"
}

# facts <t> <path> — the ownership evidence an index/wedge check could read.
facts() {
    local t="$1" p="$2" gd
    gd="$(data_gitdir "$t")"
    printf 'idx=%s|head=%s|unmerged=%s|merge_head=%s|autostash=%s' \
        "$(data_git "$t" ls-files -s -- "$p")" \
        "$(in_head "$t" "$p")" \
        "$(data_git "$t" ls-files -u -- "$p" | wc -l | tr -d ' ')" \
        "$([[ -e "$gd/MERGE_HEAD" ]] && echo yes || echo no)" \
        "$([[ -e "$gd/MERGE_AUTOSTASH" ]] && echo yes || echo no)"
}

# resolve_and_commit <t> — finish the stopped merge the way a user would.
resolve_and_commit() {
    local t="$1"
    printf -- '---\nstatus: Ready\n---\nA resolved\n' > "$t/local/.aitask-data/$CONFLICTED"
    data_git "$t" add -- "$CONFLICTED"
    data_git "$t" commit -q --no-edit
}

assert_no_ownership_claim() {
    local label="$1" out="$2" w
    for w in abandoned ownerless orphan; do
        assert_not_contains_ci "$label: does not call them $w" "$w" "$out"
    done
}

# Capability probe — independent of the code under test.
# The help spells the option `--[no-]autostash`, so a literal `--autostash`
# never matches; match the bare word. `|| true` because `-h` exits non-zero on
# some git versions, and the probe must read the text either way.
HAVE_AUTOSTASH=0
merge_help="$("$REAL_GIT" merge -h 2>&1 || true)"
[[ "$merge_help" == *autostash* ]] && HAVE_AUTOSTASH=1

echo "=== staged entries of uncertain ownership (t2277) ==="
echo ""

if (( HAVE_AUTOSTASH )); then
    # --- R1: real merge --autostash after our add ----------------------------
    echo "--- R1: merge --autostash after our add (the counter-example) ---"
    R1="$(own_fixture)"
    op_shim "$R1" after merge --autostash incoming
    printf 'B\n' > "$R1/local/aitasks/t87_second.md"
    run_commit "$R1" "$OURS" aitasks/t87_second.md
    gd1="$(data_gitdir "$R1")"
    assert_file_exists "R1: the operation ran" "$R1/op_fired"
    assert_exit_nonzero_rc "R1: the run aborted" "$RUN_RC"
    assert_contains "R1: the guard names the wedge" "stuck mid-MERGE_HEAD" "$RUN_OUT"
    assert_contains "R1: the cleanup says it left entries" "were LEFT in the shared index" "$RUN_OUT"
    assert_contains "R1: the cleanup names our path" "$OURS" "$RUN_OUT"
    # Not the bare "./ait git-health": the guard's own message also says that.
    assert_contains "R1: the cleanup points at git-health" \
        "inspect the staged entries (./ait git-health lists them)" "$RUN_OUT"
    assert_file_exists "R1: real merge state (MERGE_HEAD)" "$gd1/MERGE_HEAD"
    assert_file_exists "R1: real autostash (MERGE_AUTOSTASH)" "$gd1/MERGE_AUTOSTASH"

    our_oid="$(cd "$R1/local" && "$REAL_GIT" hash-object -- "$OURS")"
    assert_eq "R1: the entry looks ours — stage 0, our blob" \
        "100644 $our_oid 0	$OURS" "$(data_git "$R1" ls-files -s -- "$OURS")"
    assert_eq "R1: the entry looks ours — absent from HEAD" "absent" "$(in_head "$R1" "$OURS")"
    assert_eq "R1: the entry looks ours — not unmerged" "" "$(data_git "$R1" ls-files -u -- "$OURS")"
    assert_eq "R1: yet it is the incoming side's blob too" \
        "$our_oid" "$(data_git "$R1" rev-parse "incoming:$OURS")"

    health "$R1"
    assert_contains "R1 health: ownership uncertain" "ownership uncertain" "$HEALTH_OUT"
    assert_contains "R1 health: lists our path" "$OURS" "$HEALTH_OUT"
    assert_contains "R1 health: names the in-progress operation" \
        "An operation is in progress (MERGE_HEAD)" "$HEALTH_OUT"
    assert_no_ownership_claim "R1 health" "$HEALTH_OUT"

    resolve_and_commit "$R1"
    assert_eq "R1: the merge commit has two parents" "2" \
        "$(data_git "$R1" rev-list --parents -n1 HEAD | wc -w | awk '{print $1 - 1}')"
    assert_eq "R1: PRESERVED — the incoming addition survives into the merge commit" \
        "present" "$(in_head "$R1" "$OURS")"

    # --- R1-NC: the reset an unconditional cleanup would run ------------------
    echo "--- R1-NC: NEGATIVE CONTROL — reset drops the incoming file ---"
    R1N="$(own_fixture)"
    op_shim "$R1N" after merge --autostash incoming
    printf 'B\n' > "$R1N/local/aitasks/t87_second.md"
    run_commit "$R1N" "$OURS" aitasks/t87_second.md
    assert_file_exists "R1-NC: the operation ran" "$R1N/op_fired"
    assert_file_exists "R1-NC: real merge state" "$(data_gitdir "$R1N")/MERGE_HEAD"
    data_git "$R1N" reset -q -- "$OURS" >/dev/null || true
    resolve_and_commit "$R1N"
    assert_eq "R1-NC: the merge commit LOST the incoming file" "absent" "$(in_head "$R1N" "$OURS")"
else
    echo "SKIP: R1, R1-NC — this git has no 'merge --autostash'"
fi

# --- R2: a real merge started in the guard→add gap; the entry IS ours --------
echo "--- R2: merge started before our add (entry is ours) ---"
R2="$(own_fixture)"
op_shim "$R2" before merge incoming_noadd
run_commit "$R2" "$OURS"
gd2="$(data_gitdir "$R2")"
assert_file_exists "R2: the operation ran" "$R2/op_fired"
assert_exit_nonzero_rc "R2: the run aborted" "$RUN_RC"
assert_contains "R2: the guard names the wedge" "stuck mid-MERGE_HEAD" "$RUN_OUT"
assert_contains "R2: the cleanup says it left entries" "were LEFT in the shared index" "$RUN_OUT"
assert_contains "R2: the cleanup names our path" "$OURS" "$RUN_OUT"
assert_contains "R2: the cleanup qualifies continue/abort" \
    "Before you continue or abort that operation" "$RUN_OUT"
assert_file_exists "R2: real merge state" "$gd2/MERGE_HEAD"
assert_file_not_exists "R2: no autostash" "$gd2/MERGE_AUTOSTASH"
assert_contains "R2: our entry is in the merging index (left, not reset)" \
    "$OURS" "$(data_git "$R2" diff --cached --name-only)"
FACTS_R2="$(facts "$R2" "$OURS")"

health "$R2"
assert_contains "R2 health: ownership uncertain" "ownership uncertain" "$HEALTH_OUT"
assert_contains "R2 health: lists our path" "$OURS" "$HEALTH_OUT"
assert_contains "R2 health: before continue OR abort" "Before you continue OR abort it" "$HEALTH_OUT"
assert_contains "R2 health: the inspect command" "./ait git diff --cached --name-status" "$HEALTH_OUT"
assert_contains "R2 health: continuing commits them" "Continuing (--continue, or committing a resolved merge) commits every staged entry" "$HEALTH_OUT"
assert_contains "R2 health: aborting can discard them" "Aborting can discard them" "$HEALTH_OUT"
assert_contains "R2 health: copy aside" "Copy aside" "$HEALTH_OUT"
assert_not_contains "R2 health: never 'resolve or abort it first'" "resolve or abort it first" "$HEALTH_OUT"
assert_not_contains "R2 health: never suggests the guard bypass" "AIT_GIT_SKIP_STATE_CHECK" "$HEALTH_OUT"
assert_not_contains "R2 health: no all-clear" "Clean —" "$HEALTH_OUT"
assert_no_ownership_claim "R2 health" "$HEALTH_OUT"
assert_contains "R2 health: still nothing was unstaged by the check" \
    "$OURS" "$(data_git "$R2" diff --cached --name-only)"

# --- R2c: continuing commits the unrelated entry ------------------------------
echo "--- R2c: committing the merge commits the unrelated file ---"
resolve_and_commit "$R2"
assert_eq "R2c: the merge commit CONTAINS the unrelated file" "present" "$(in_head "$R2" "$OURS")"

# --- R2a: aborting deletes it from the index AND the worktree -----------------
echo "--- R2a: merge --abort discards the unrelated file ---"
R2A="$(own_fixture)"
op_shim "$R2A" before merge incoming_noadd
run_commit "$R2A" "$OURS"
assert_file_exists "R2a: real merge state" "$(data_gitdir "$R2A")/MERGE_HEAD"
assert_contains "R2a: precondition — our entry is staged" \
    "$OURS" "$(data_git "$R2A" diff --cached --name-only)"
data_git "$R2A" merge --abort >/dev/null || true
assert_eq "R2a: gone from the index" "" "$(data_git "$R2A" ls-files -- "$OURS")"
assert_file_not_exists "R2a: gone from the worktree" "$R2A/local/.aitask-data/$OURS"

# --- C1: the not-ours twin of R2 has identical facts --------------------------
echo "--- C1: ours vs the merge's — identical facts ---"
C1="$(own_fixture)"
data_git "$C1" merge incoming >/dev/null || true
printf '%s' "$OURS_CONTENT" > "$C1/local/.aitask-data/$OURS"
data_git "$C1" add -- "$OURS"
FACTS_C1="$(facts "$C1" "$OURS")"
assert_contains "C1: the merge brought the file (not ours)" \
    "$OURS" "$(data_git "$C1" ls-tree -r --name-only MERGE_HEAD)"
assert_not_contains "C1: R2's merge did not (ours)" \
    "$OURS" "$(data_git "$R2" ls-tree -r --name-only incoming_noadd)"
assert_contains "C1: the facts vector is populated" "idx=100644 " "$FACTS_C1"
assert_eq "C1: ours (R2) and the merge's (C1) are indistinguishable" "$FACTS_R2" "$FACTS_C1"

# --- H1-H4: the git-health report ---------------------------------------------
echo "--- H1: clean ---"
H="$(own_fixture)"
health "$H"
assert_contains "H1: the all-clear covers the index" \
    "Clean — no in-progress rebase/merge/cherry-pick/revert/bisect, and nothing staged." "$HEALTH_OUT"
assert_not_contains "H1: nothing listed" "ownership uncertain" "$HEALTH_OUT"

echo "--- H2: a bystander's entry, no operation ---"
printf '\nMid-edit by another session.\n' >> "$H/local/.aitask-data/$BYSTANDER"
data_git "$H" add -- "$BYSTANDER"
health "$H"
assert_contains "H2: ownership uncertain" "ownership uncertain (1)" "$HEALTH_OUT"
assert_contains_re "H2: lists the entry with its status" "M[[:space:]]+$BYSTANDER" "$HEALTH_OUT"
assert_contains "H2: the inspect command" "./ait git diff --cached -- <path>" "$HEALTH_OUT"
before_reset="${HEALTH_OUT%%./ait git reset*}"
assert_contains "H2: inspect comes before the reset hint" "./ait git diff --cached -- <path>" "$before_reset"
assert_contains "H2: reset only once confirmed" "confirmed is yours and unwanted" "$HEALTH_OUT"
assert_not_contains "H2: no in-progress line" "An operation is in progress" "$HEALTH_OUT"
assert_not_contains "H2: no all-clear" "Clean —" "$HEALTH_OUT"
assert_no_ownership_claim "H2" "$HEALTH_OUT"
assert_contains "H2: the check unstaged nothing" "$BYSTANDER" "$(data_git "$H" diff --cached --name-only)"

echo "--- H4: the listing is capped ---"
for i in $(seq 1 21); do
    printf 'x%s\n' "$i" > "$H/local/.aitask-data/aitasks/t9${i}_cap.md"
    data_git "$H" add -- "aitasks/t9${i}_cap.md"
done
health "$H"
assert_contains "H4: the count is the full count" "ownership uncertain (22)" "$HEALTH_OUT"
assert_eq "H4: 20 entries listed" "20" \
    "$(grep -cE '^    [AMDTU][[:space:]]' <<<"$HEALTH_OUT")"
assert_contains "H4: the remainder is counted" "… and 2 more" "$HEALTH_OUT"

echo "--- H3: an unreadable index is unknown, not none ---"
cat > "$H/local/bin/git" <<SHIM
#!/usr/bin/env bash
for a in "\$@"; do [[ "\$a" == --cached ]] && exit 128; done
exec "$REAL_GIT" "\$@"
SHIM
chmod +x "$H/local/bin/git"
health "$H"
rm -f "$H/local/bin/git"
assert_contains "H3: unknown, not none" "unknown, not none" "$HEALTH_OUT"
assert_contains "H3: names the exit status" "exited 128" "$HEALTH_OUT"
assert_not_contains "H3: no all-clear" "Clean —" "$HEALTH_OUT"
assert_not_contains "H3: nothing listed" "ownership uncertain" "$HEALTH_OUT"

echo ""
echo "========================================="
echo "Results: $PASS passed, $FAIL failed (of $TOTAL)"
echo "========================================="
[[ "$FAIL" -eq 0 ]]
