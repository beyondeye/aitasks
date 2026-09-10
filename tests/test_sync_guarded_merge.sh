#!/usr/bin/env bash
# test_sync_guarded_merge.sh - `ait sync` converges a DIVERGED data branch with a
# guarded merge when protected dirty files block the rebase (t1731).
#
# Run: bash tests/test_sync_guarded_merge.sh
#
# THE PROBLEM. `git pull --rebase` refuses on ANY unstaged tracked change, so a
# live session holding a modified task file blocks every rebase, and on a
# diverged branch (local_ahead > 0 AND remote_ahead > 0) no fast-forward exists:
# sync used to defer forever. A merge refuses only when it would OVERWRITE a
# dirty file. aitask_sync.sh therefore builds the merge without touching the
# worktree (merge-tree -> commit-tree) and advances with
# `merge --ff-only --no-autostash --no-overwrite-ignore` — but only after every
# guard below has said yes.
#
# TWO KINDS OF ASSERTION, KEPT APART ON PURPOSE.
#   (a) guard coverage — the refusal slug on stderr,
#       "Guarded merge not possible (<slug>): ...". Several guards are
#       backstopped by git itself (--ff-only refuses to overwrite a dirty or
#       untracked file), so the end-to-end outcome can stay green with the guard
#       deleted; only the slug proves the guard is the thing that fired.
#   (b) end-to-end preservation — the verdict, HEAD, and the protected bytes.
# Every cell asserts both. A mutant of a backstopped guard is expected to turn
# only (a) red; that is recorded in the t1731 plan, not hidden here.
#
# Local commits are made DIRECTLY in the data worktree (not left for the sweep)
# so a deferral cell can assert HEAD did not move at all. AC1 alone uses the
# sweep, because that is the path a real run takes.

set -uo pipefail

TEST_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/sync_fixture.sh"

# Every slug a cell below drives, collected for the completeness scan at the end.
DRIVEN_SLUGS=()

# --- Helpers --------------------------------------------------------------

dgit() { local t="$1"; shift; git -C "$t/local/.aitask-data" "$@"; }
dhead() { dgit "$1" rev-parse HEAD 2>/dev/null; }
remote_sha() { git -C "$1/remote.git" rev-parse refs/heads/aitask-data 2>/dev/null; }
sha_of() { sha256sum "$1" 2>/dev/null | cut -d' ' -f1; }
sha_of_text() { printf '%s' "$1" | sha256sum | cut -d' ' -f1; }
# Number of parents of the data branch HEAD.
head_parents() { dgit "$1" rev-list --parents -n1 HEAD | awk '{print NF - 1}'; }
first_line() { printf '%s\n' "$1" | head -n1; }
gm_slug() {
    sed -n 's/.*Guarded merge not possible (\([a-z_]*\)).*/\1/p' "$1/sync_stderr" 2>/dev/null | head -n1
}

# local_commit <tmpdir> <snippet> — run <snippet> inside the data worktree (it
# stages what it wants) and commit exactly that. Nothing else is staged, so the
# protected file can never ride along.
local_commit() {
    local t="$1" snippet="$2"
    (
        cd "$t/local/.aitask-data" || exit 1
        eval "$snippet"
        git commit -q -m "local: commit"
    ) >/dev/null 2>&1
}

# pc2 <tmpdir> <label> <snippet> — run <snippet> in a fresh clone of the data
# branch, commit everything, push, and fetch it into the local clone. Asserts
# the remote actually advanced: a helper that fails silently leaves the remote
# where it was, and every assertion after it then tests the wrong fixture.
pc2() {
    local t="$1" label="$2" snippet="$3" before after
    before="$(remote_sha "$t")"
    rm -rf "$t/pc2"
    git clone -q --branch aitask-data "$t/remote.git" "$t/pc2" 2>/dev/null
    (
        cd "$t/pc2" || exit 1
        git config user.email pc2@test.com
        git config user.name PC2
        git config commit.gpgsign false
        # aiplans/ holds no committed file in the fixture, so a clone lacks it.
        mkdir -p aitasks aiplans
        eval "$snippet"
        git add -A && git commit -q -m "pc2: advance" && git push -q origin aitask-data
    ) >/dev/null 2>&1
    dgit "$t" fetch -q origin 2>/dev/null
    after="$(remote_sha "$t")"
    if [[ -n "$after" && "$after" != "$before" ]]; then
        assert_eq "$label: fixture — pc2 advanced the remote" "advanced" "advanced"
    else
        assert_eq "$label: fixture — pc2 advanced the remote" "advanced" "unchanged"
    fi
}

# The protected file: t10 is locked by a LIVE process (this test's own shell), so
# the sweep leaves its modified tracked file dirty. Tracked + local commits is
# exactly what blocks a rebase.
protect_t10() {
    local t="$1"
    plant_lock "$t" 10 "$(lock_yaml_live 10)"
    printf 'edit10\n' >> "$t/local/.aitask-data/aitasks/t10_alpha.md"
}

enable_seams() { mkdir -p "$1/locks" && touch "$1/locks/.ait_sync_test_seams"; }

# Run a sync with one marker-gated seam hook active.
run_sync_with_seam() {
    local t="$1" point="$2" hook="$3"
    enable_seams "$t"
    export "AIT_SYNC_SEAM_${point}=$hook"
    run_sync "$t"
    unset "AIT_SYNC_SEAM_${point}"
}

# expect_deferred <label> <tmpdir> <stdout> <slug> <expected_head>
expect_deferred() {
    local label="$1" t="$2" out="$3" slug="$4" want_head="$5"
    assert_eq "$label: (b) the run defers on protected_dirty" \
        "DEFERRED:protected_dirty" "$(first_line "$out" | cut -d: -f1-2)"
    assert_eq "$label: (a) the refusing guard is $slug" "$slug" "$(gm_slug "$t")"
    assert_eq "$label: (b) HEAD is where it should be" "$want_head" "$(dhead "$t")"
    assert_not_contains "$label: (b) no MERGED verdict" "MERGED" "$out"
    DRIVEN_SLUGS+=("$slug")
}

# expect_preserved <label> <tmpdir> <relpath> <sha> <xy> <pre_head>
# Bytes identical, still in its porcelain state, never committed, never staged.
expect_preserved() {
    local label="$1" t="$2" p="$3" sha="$4" xy="$5" pre="$6"
    assert_eq "$label: bytes unchanged" "$sha" "$(sha_of "$t/local/.aitask-data/$p")"
    assert_eq "$label: still '$xy'" "$xy" \
        "$(dgit "$t" status --porcelain --ignored -- "$p" | head -n1 | cut -c1-2)"
    assert_not_contains "$label: in no commit this run made" "$p" \
        "$(dgit "$t" log --name-only --no-renames --format= "$pre..HEAD" 2>/dev/null)"
    assert_not_contains "$label: not staged" "$p" "$(dgit "$t" diff --cached --name-only 2>/dev/null)"
}

# install_racer <tmpdir> <path> — a pre-push hook that advances the remote with a
# commit touching <path> exactly once, so the first push is rejected and the run
# enters do_push's retry. Mirrors test_sync_deferral_and_quarantine.sh.
install_racer() {
    local tmpdir="$1" path="$2"
    mkdir -p "$tmpdir/local/.git/hooks"
    cat > "$tmpdir/local/.git/hooks/pre-push" <<HOOKEOF
#!/usr/bin/env bash
# git exports GIT_DIR (and friends) into hooks; left set, the clone below lands
# in this repo's own data worktree.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX GIT_COMMON_DIR
marker="$tmpdir/prepush_fired"
[ -e "\$marker" ] && exit 0
touch "\$marker"
rm -rf "$tmpdir/racer"
git clone -q --branch aitask-data "$tmpdir/remote.git" "$tmpdir/racer" >/dev/null 2>&1 || exit 0
(
  cd "$tmpdir/racer" || exit 0
  git config user.email racer@test.com
  git config user.name Racer
  git config commit.gpgsign false
  printf 'racer\n' >> "$path"
  git add -A && git commit -q -m "racer: advance"
  git push -q origin aitask-data
) >/dev/null 2>&1
exit 0
HOOKEOF
    chmod +x "$tmpdir/local/.git/hooks/pre-push"
}

T10=aitasks/t10_alpha.md

echo "=== guarded merge on a diverged data branch (t1731) ==="
echo ""

# --- AC1: diverged + live-locked tracked file + disjoint sides -> MERGED ----
echo "--- AC1: diverged, protected tracked file, disjoint sides -> converges and pushes ---"
T="$(setup_repo)"
printf 'edit20\n' >> "$T/local/.aitask-data/aitasks/t20_beta.md"   # the run's sweep commits this
pc2 "$T" "AC1" 'printf "from pc2\n" >> aitasks/t30_gamma.md'
protect_t10 "$T"
PRE_HEAD="$(dhead "$T")"; PRE10="$(sha_of "$T/local/.aitask-data/$T10")"
# The merge path allocates several scratch files in a script with no trap, so
# each must sit in an exit-free window (_gm_names_into). A private TMPDIR makes a
# leak visible.
mkdir -p "$T/tmpdir_probe"
OUT="$(TMPDIR="$T/tmpdir_probe" run_sync "$T")"
assert_eq "AC1: (b) the verdict is MERGED" "MERGED" "$(first_line "$OUT")"
assert_eq "AC1: the merge path left no temp file behind" "" "$(ls -A "$T/tmpdir_probe" 2>/dev/null)"
assert_eq "AC1: (a) no guard refused" "" "$(gm_slug "$T")"
dgit "$T" fetch -q origin 2>/dev/null
assert_eq "AC1: nothing left to push" "0" "$(dgit "$T" rev-list --count '@{u}..HEAD' 2>/dev/null)"
assert_eq "AC1: nothing left to pull" "0" "$(dgit "$T" rev-list --count 'HEAD..@{u}' 2>/dev/null)"
assert_eq "AC1: the remote holds our HEAD" "$(dhead "$T")" "$(remote_sha "$T")"
assert_eq "AC1: HEAD is a two-parent merge" "2" "$(head_parents "$T")"
assert_contains "AC1: pc2's commit arrived" "from pc2" \
    "$(cat "$T/local/.aitask-data/aitasks/t30_gamma.md")"
assert_contains "AC1: our own commit was published" "edit20" \
    "$(git -C "$T/remote.git" show refs/heads/aitask-data:aitasks/t20_beta.md 2>/dev/null)"
expect_preserved "AC1: the protected file" "$T" "$T10" "$PRE10" " M" "$PRE_HEAD"

# --- AC2: an incoming commit touches the protected file -> defer ----------
echo "--- AC2: the incoming side writes the protected file -> defers ---"
T="$(setup_repo)"
local_commit "$T" 'printf "edit20\n" >> aitasks/t20_beta.md && git add aitasks/t20_beta.md'
pc2 "$T" "AC2" 'printf "theirs\n" >> aitasks/t10_alpha.md'
protect_t10 "$T"
PRE_HEAD="$(dhead "$T")"; PRE10="$(sha_of "$T/local/.aitask-data/$T10")"
OUT="$(run_sync "$T")"
expect_deferred "AC2" "$T" "$OUT" protected_written "$PRE_HEAD"
expect_preserved "AC2: the protected file" "$T" "$T10" "$PRE10" " M" "$PRE_HEAD"

# --- AC3: both sides changed the same file -> defer ------------------------
# The two edits are deliberately NON-conflicting (local rewrites line 2, pc2
# appends after line 4), so a three-way merge WOULD succeed. That is what makes
# the disjointness policy observable end-to-end: without it this cell merges.
echo "--- AC3: local and remote both changed t20_beta.md -> defers ---"
T="$(setup_repo)"
local_commit "$T" "printf -- '---\nstatus: Editing\n---\nB\n' > aitasks/t20_beta.md && git add aitasks/t20_beta.md"
pc2 "$T" "AC3" 'printf "from pc2\n" >> aitasks/t20_beta.md'
protect_t10 "$T"
PRE_HEAD="$(dhead "$T")"; PRE10="$(sha_of "$T/local/.aitask-data/$T10")"
OUT="$(run_sync "$T")"
expect_deferred "AC3" "$T" "$OUT" sides_overlap "$PRE_HEAD"
expect_preserved "AC3: the protected file" "$T" "$T10" "$PRE10" " M" "$PRE_HEAD"

# --- AC4: behind-only keeps t1725_3's fast-forward -> PULLED ---------------
echo "--- AC4: behind-only -> PULLED by fast-forward, never MERGED ---"
T="$(setup_repo)"
pc2 "$T" "AC4" 'printf "from pc2\n" >> aitasks/t30_gamma.md'
protect_t10 "$T"
PRE_HEAD="$(dhead "$T")"; PRE10="$(sha_of "$T/local/.aitask-data/$T10")"
OUT="$(run_sync "$T")"
assert_eq "AC4: the verdict is PULLED" "PULLED" "$(first_line "$OUT")"
assert_eq "AC4: the guarded merge never ran" "" "$(gm_slug "$T")"
assert_eq "AC4: HEAD is a plain commit (fast-forward, no merge)" "1" "$(head_parents "$T")"
expect_preserved "AC4: the protected file" "$T" "$T10" "$PRE10" " M" "$PRE_HEAD"

# --- AC5: a wedged worktree still defers before anything else --------------
echo "--- AC5: mid-rebase worktree -> DEFERRED:worktree_wedged, nothing merged ---"
T="$(setup_repo)"
local_commit "$T" 'printf "edit20\n" >> aitasks/t20_beta.md && git add aitasks/t20_beta.md'
pc2 "$T" "AC5" 'printf "from pc2\n" >> aitasks/t30_gamma.md'
protect_t10 "$T"
mkdir -p "$(dgit "$T" rev-parse --absolute-git-dir)/rebase-merge"
PRE_HEAD="$(dhead "$T")"
OUT="$(run_sync "$T")"
assert_eq "AC5: the run reports the wedge" "DEFERRED:worktree_wedged" "$(first_line "$OUT" | cut -d: -f1-2)"
assert_eq "AC5: HEAD did not move" "$PRE_HEAD" "$(dhead "$T")"
assert_eq "AC5: the guarded merge never ran" "" "$(gm_slug "$T")"

# --- not_diverged: behind-only, but incoming touches the protected file -----
# Rule 4 blocks the fast-forward; with nothing to merge from our side the guarded
# path must decline rather than build a merge.
echo "--- not diverged: behind-only with the protected path incoming -> defers ---"
T="$(setup_repo)"
pc2 "$T" "not_diverged" 'printf "theirs\n" >> aitasks/t10_alpha.md'
protect_t10 "$T"
PRE_HEAD="$(dhead "$T")"; PRE10="$(sha_of "$T/local/.aitask-data/$T10")"
OUT="$(run_sync "$T")"
expect_deferred "not_diverged" "$T" "$OUT" not_diverged "$PRE_HEAD"
expect_preserved "not_diverged: the protected file" "$T" "$T10" "$PRE10" " M" "$PRE_HEAD"

# --- rename: a local rename of a file pc2 modified -> overlap ---------------
# Pins --no-renames on the side sets: with rename detection the local side lists
# only the destination and looks disjoint, and ort then merges the change into
# the renamed file.
echo "--- rename: local renames t30_gamma.md, pc2 modifies it -> defers ---"
T="$(setup_repo)"
local_commit "$T" 'git mv aitasks/t30_gamma.md aitasks/t30_renamed.md'
pc2 "$T" "rename" 'printf "from pc2\n" >> aitasks/t30_gamma.md'
protect_t10 "$T"
PRE_HEAD="$(dhead "$T")"
OUT="$(run_sync "$T")"
expect_deferred "rename" "$T" "$OUT" sides_overlap "$PRE_HEAD"

# --- directory/file, merge direction -> merge-tree refuses ------------------
# Paths disjoint as strings, but one side adds a FILE where the other adds a
# DIRECTORY. Only the merge-tree proof sees it.
echo "--- D/F merge: local adds aitasks/t40/x.md, pc2 adds a file aitasks/t40 -> defers ---"
T="$(setup_repo)"
local_commit "$T" 'mkdir -p aitasks/t40 && printf "x\n" > aitasks/t40/x.md && git add aitasks/t40/x.md'
pc2 "$T" "D/F merge" 'printf "file\n" > aitasks/t40'
protect_t10 "$T"
PRE_HEAD="$(dhead "$T")"
OUT="$(run_sync "$T")"
expect_deferred "D/F merge" "$T" "$OUT" merge_conflict "$PRE_HEAD"

# --- directory/file, protected direction -> prefix rule ----------------------
echo "--- D/F protected: untracked file aiplans/p10_d, pc2 adds aiplans/p10_d/y.md -> defers ---"
T="$(setup_repo)"
local_commit "$T" 'printf "edit20\n" >> aitasks/t20_beta.md && git add aitasks/t20_beta.md'
printf 'mine\n' > "$T/local/.aitask-data/aiplans/p10_d"
pc2 "$T" "D/F protected" 'mkdir -p aiplans/p10_d && printf "y\n" > aiplans/p10_d/y.md'
protect_t10 "$T"
PRE_HEAD="$(dhead "$T")"; PRE_D="$(sha_of "$T/local/.aitask-data/aiplans/p10_d")"
OUT="$(run_sync "$T")"
assert_contains "D/F protected: fixture — the sweep protected aiplans/p10_d" \
    "aiplans/p10_d" "$(sync_err "$T")"
expect_deferred "D/F protected" "$T" "$OUT" protected_written "$PRE_HEAD"
expect_preserved "D/F protected: aiplans/p10_d" "$T" "aiplans/p10_d" "$PRE_D" "??" "$PRE_HEAD"

# --- case fold -> the fold rule (no git backstop on a case-sensitive FS) -----
echo "--- case fold: protected aiplans/p10_Case.md vs incoming aiplans/p10_case.md -> defers ---"
T="$(setup_repo)"
local_commit "$T" 'printf "edit20\n" >> aitasks/t20_beta.md && git add aitasks/t20_beta.md'
printf 'mine\n' > "$T/local/.aitask-data/aiplans/p10_Case.md"
pc2 "$T" "case fold" 'printf "theirs\n" > aiplans/p10_case.md'
protect_t10 "$T"
PRE_HEAD="$(dhead "$T")"; PRE_C="$(sha_of "$T/local/.aitask-data/aiplans/p10_Case.md")"
OUT="$(run_sync "$T")"
assert_contains "case fold: fixture — the sweep protected aiplans/p10_Case.md" \
    "aiplans/p10_Case.md" "$(sync_err "$T")"
expect_deferred "case fold" "$T" "$OUT" protected_written "$PRE_HEAD"
expect_preserved "case fold: aiplans/p10_Case.md" "$T" "aiplans/p10_Case.md" "$PRE_C" "??" "$PRE_HEAD"

# --- ignored file present at prepare -> ignored_written ---------------------
# userconfig.yaml is gitignored on the data branch; the sweep never protects an
# ignored file, and git's default is to overwrite one silently.
echo "--- ignored, present: local userconfig.yaml, pc2 force-adds it -> defers ---"
T="$(setup_repo)"
local_commit "$T" 'printf "edit20\n" >> aitasks/t20_beta.md && git add aitasks/t20_beta.md'
set_userconfig_email "$T" "mine@x.com"
pc2 "$T" "ignored present" 'mkdir -p aitasks/metadata && printf "email: theirs@x.com\n" > aitasks/metadata/userconfig.yaml && git add -f aitasks/metadata/userconfig.yaml'
protect_t10 "$T"
UC=aitasks/metadata/userconfig.yaml
PRE_HEAD="$(dhead "$T")"; PRE_UC="$(sha_of "$T/local/.aitask-data/$UC")"
OUT="$(run_sync "$T")"
expect_deferred "ignored present" "$T" "$OUT" ignored_written "$PRE_HEAD"
expect_preserved "ignored present: userconfig.yaml" "$T" "$UC" "$PRE_UC" "!!" "$PRE_HEAD"

# --- ignored file created AFTER prepare's scan -> the ff itself must refuse ---
# The pre_guarded_ff seam runs between commit-tree and the fast-forward, i.e.
# after the ignored-file scan. Only --no-overwrite-ignore stops this one.
echo "--- ignored, race: userconfig.yaml appears after the scan -> ff refuses, bytes kept ---"
T="$(setup_repo)"
local_commit "$T" 'printf "edit20\n" >> aitasks/t20_beta.md && git add aitasks/t20_beta.md'
pc2 "$T" "ignored race" 'mkdir -p aitasks/metadata && printf "email: theirs@x.com\n" > aitasks/metadata/userconfig.yaml && git add -f aitasks/metadata/userconfig.yaml'
protect_t10 "$T"
PRE_HEAD="$(dhead "$T")"
LATE="email: mine-late@x.com"
OUT="$(run_sync_with_seam "$T" pre_guarded_ff \
    "printf '%s\n' '$LATE' > '$T/local/.aitask-data/$UC'")"
assert_contains "ignored race: fixture — the seam fired" "TEST SEAM ACTIVE - running pre_guarded_ff" "$(sync_err "$T")"
expect_deferred "ignored race" "$T" "$OUT" ff_refused "$PRE_HEAD"
expect_preserved "ignored race: userconfig.yaml" "$T" "$UC" "$(sha_of_text "$LATE"$'\n')" "!!" "$PRE_HEAD"

# --- moving refs: HEAD moves between prepare and the fast-forward ------------
echo "--- moving refs: a commit lands between prepare and ff -> ff refuses, HEAD is that commit ---"
T="$(setup_repo)"
local_commit "$T" 'printf "edit20\n" >> aitasks/t20_beta.md && git add aitasks/t20_beta.md'
pc2 "$T" "moving refs" 'printf "from pc2\n" >> aitasks/t30_gamma.md'
protect_t10 "$T"
OUT="$(run_sync_with_seam "$T" pre_guarded_ff \
    "git -C '$T/local/.aitask-data' commit --allow-empty -q -m 'seam: moved' && git -C '$T/local/.aitask-data' rev-parse HEAD > '$T/seam_sha'")"
assert_contains "moving refs: fixture — the seam fired" "TEST SEAM ACTIVE - running pre_guarded_ff" "$(sync_err "$T")"
expect_deferred "moving refs" "$T" "$OUT" ff_refused "$(cat "$T/seam_sha" 2>/dev/null)"

# --- criss-cross history: two merge bases -> refuse -------------------------
# a1 (local) and b1 (pc2) from the same base; local merges b1 -> a2, pc2 merges a1
# -> b2. merge-base(a2, b2) = {a1, b1}: a single-base side diff is not what the
# merge would actually do.
echo "--- criss-cross: two merge bases -> defers ---"
T="$(setup_repo)"
local_commit "$T" 'printf "a1\n" >> aitasks/t20_beta.md && git add aitasks/t20_beta.md'
dgit "$T" push -q origin HEAD:refs/heads/side 2>/dev/null
pc2 "$T" "criss-cross b1" 'printf "b1\n" >> aitasks/t30_gamma.md'
dgit "$T" merge -q --no-edit origin/aitask-data >/dev/null 2>&1
rm -rf "$T/pc2"
git clone -q --branch aitask-data "$T/remote.git" "$T/pc2" 2>/dev/null
(
    cd "$T/pc2" || exit 1
    git config user.email pc2@test.com; git config user.name PC2
    git config commit.gpgsign false
    git fetch -q origin side && git merge -q --no-edit FETCH_HEAD && git push -q origin aitask-data
) >/dev/null 2>&1
dgit "$T" fetch -q origin 2>/dev/null
assert_eq "criss-cross: fixture — two merge bases" "2" \
    "$(dgit "$T" merge-base --all HEAD '@{u}' 2>/dev/null | wc -l | tr -d ' ')"
protect_t10 "$T"
PRE_HEAD="$(dhead "$T")"
OUT="$(run_sync "$T")"
expect_deferred "criss-cross" "$T" "$OUT" multiple_merge_bases "$PRE_HEAD"

# --- hostile path: a newline in the protected path --------------------------
echo "--- hostile path: protected path with a newline, created by pc2 -> defers ---"
T="$(setup_repo)"
NL_PATH="$(printf 'aiplans/p10_a\nb.md')"
local_commit "$T" 'printf "edit20\n" >> aitasks/t20_beta.md && git add aitasks/t20_beta.md'
printf 'mine\n' > "$T/local/.aitask-data/$NL_PATH"
P="$NL_PATH" pc2 "$T" "hostile path" 'printf "theirs\n" > "$P"'
protect_t10 "$T"
PRE_HEAD="$(dhead "$T")"; PRE_NL="$(sha_of "$T/local/.aitask-data/$NL_PATH")"
OUT="$(run_sync "$T")"
expect_deferred "hostile path" "$T" "$OUT" protected_written "$PRE_HEAD"
assert_eq "hostile path: bytes unchanged" "$PRE_NL" "$(sha_of "$T/local/.aitask-data/$NL_PATH")"

# --- retry path: the push is rejected mid-run -> merge on the retry ----------
# main sees remote_ahead == 0 (nothing blocks), the racer advances the remote
# during the first push, and do_push's re-gate now finds the diverged shape.
echo "--- retry: push rejected mid-run, racer touches t30 -> merges on the retry ---"
T="$(setup_repo)"
local_commit "$T" 'printf "edit20\n" >> aitasks/t20_beta.md && git add aitasks/t20_beta.md'
protect_t10 "$T"
install_racer "$T" aitasks/t30_gamma.md
PRE_HEAD="$(dhead "$T")"; PRE10="$(sha_of "$T/local/.aitask-data/$T10")"
OUT="$(run_sync "$T")"
assert_eq "retry: fixture — the racer fired" "yes" "$([[ -e "$T/prepush_fired" ]] && echo yes || echo no)"
assert_eq "retry: the verdict is MERGED" "MERGED" "$(first_line "$OUT")"
assert_eq "retry: the remote holds our HEAD" "$(dhead "$T")" "$(remote_sha "$T")"
assert_contains "retry: the racer's commit arrived" "racer" \
    "$(cat "$T/local/.aitask-data/aitasks/t30_gamma.md")"
expect_preserved "retry: the protected file" "$T" "$T10" "$PRE10" " M" "$PRE_HEAD"

# --- slug completeness -------------------------------------------------------
# Every `_gm_refuse <slug>` in the script is either driven above or listed here
# with a reason it cannot be; and nothing driven or listed is missing from the
# script. The reverse check is what stops the scan passing vacuously when a
# refactor renames the receiver and the forward scan quietly finds nothing.
echo "--- every refusal slug in the script is driven or justified ---"
declare -A UNREACHABLE=(
    # Set when the incoming set could not be read. Needs `git diff` to fail on a
    # healthy fixture; main() then marks every record unknown and _rebase_blocked
    # already blocks via rule 2, so the guard is a defensive second line.
    [unknown_state]=1
    # HEAD or @{u} unresolvable. Without an upstream remote_ahead reads 0, and
    # rule 1 means the guarded path is never entered at all.
    [rev_unresolved]=1
)
SRC_SLUGS="$(grep -vE '^[[:space:]]*#' "$PROJECT_DIR/.aitask-scripts/aitask_sync.sh" \
    | grep -oE '_gm_refuse[[:space:]]+"?[a-z_]+' | sed -E 's/.*[[:space:]"]//' | sort -u)"
if [[ -n "$SRC_SLUGS" ]]; then
    assert_eq "scan: found refusal slugs in the script" "yes" "yes"
else
    assert_eq "scan: found refusal slugs in the script" "yes" "no"
fi
declare -A DRIVEN=()
for s in "${DRIVEN_SLUGS[@]}"; do DRIVEN["$s"]=1; done
while IFS= read -r s; do
    [[ -z "$s" ]] && continue
    if [[ -n "${DRIVEN[$s]:-}" || -n "${UNREACHABLE[$s]:-}" ]]; then
        assert_eq "scan: slug '$s' is covered" "covered" "covered"
    else
        assert_eq "scan: slug '$s' is covered" "covered" "neither driven nor justified"
    fi
done <<< "$SRC_SLUGS"
for s in "${!DRIVEN[@]}" "${!UNREACHABLE[@]}"; do
    if grep -qxF "$s" <<< "$SRC_SLUGS"; then
        assert_eq "scan: '$s' exists in the script" "present" "present"
    else
        assert_eq "scan: '$s' exists in the script" "present" "missing"
    fi
done

echo ""
echo "==================================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ "$FAIL" -eq 0 ]]; then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "SOME TESTS FAILED"
    exit 1
fi
