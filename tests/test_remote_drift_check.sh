#!/usr/bin/env bash
# test_remote_drift_check.sh - Automated tests for aitask_remote_drift_check.sh
# Run: bash tests/test_remote_drift_check.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
HELPER="$PROJECT_DIR/.aitask-scripts/aitask_remote_drift_check.sh"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"

# --- Fixtures ---

# Build a scratch "remote" bare repo + a "local" clone.
# In branch-mode emulation: create a .aitask-data/.git stub so
# _ait_detect_data_worktree returns ".aitask-data" (i.e., the helper does NOT
# short-circuit as legacy mode).
make_branch_mode_pair() {
    local root
    root=$(mktemp -d "${TMPDIR:-/tmp}/aitask_drift_test_XXXXXX")

    git init --bare --quiet "$root/origin.git"

    git clone --quiet "$root/origin.git" "$root/local" 2>/dev/null
    (
        cd "$root/local" || exit 1
        git config user.email "test@example.com"
        git config user.name  "Test"
        echo "v1" > README.md
        git add README.md
        git commit --quiet -m "init"
        git push --quiet origin master 2>/dev/null || git push --quiet origin main
    )

    # Determine which branch the repo defaulted to (master vs main).
    local default_branch
    default_branch=$(git -C "$root/local" rev-parse --abbrev-ref HEAD)
    echo "$root|$default_branch"
}

make_legacy_mode_repo() {
    # No .aitask-data subdir → _ait_detect_data_worktree returns "."
    local root
    root=$(mktemp -d "${TMPDIR:-/tmp}/aitask_drift_legacy_XXXXXX")
    git init --quiet "$root"
    (
        cd "$root" || exit 1
        git config user.email "test@example.com"
        git config user.name  "Test"
        echo "v1" > README.md
        git add README.md
        git commit --quiet -m "init"
    )
    echo "$root"
}

# A fixture's real default branch. `git init` follows init.defaultBranch, which
# differs per machine (master here, main elsewhere), so tests must never hardcode
# a branch name that may not exist locally.
repo_default_branch() {
    git -C "$1" rev-parse --abbrev-ref HEAD
}

# A legacy-mode clone (no .aitask-data stub) that HAS an origin, plus a second
# branch `dev` whose origin side is ahead of the local side. This is the shape
# the --unsynced bypass exists for: legacy task_sync() pulls only the current
# branch, so `dev` is stale and the drift must still be detectable.
# Echoes "<root>|<default_branch>".
make_legacy_mode_pair_with_stale_dev() {
    local root
    root=$(mktemp -d "${TMPDIR:-/tmp}/aitask_drift_legacy_pair_XXXXXX")
    git init --bare --quiet "$root/origin.git"
    git clone --quiet "$root/origin.git" "$root/local" 2>/dev/null
    local default_branch
    (
        cd "$root/local" || exit 1
        git config user.email "test@example.com"
        git config user.name  "Test"
        echo "v1" > README.md
        git add README.md
        git commit --quiet -m "init"
        git push --quiet origin HEAD 2>/dev/null
        git branch dev
        git push --quiet origin dev 2>/dev/null
        # Advance origin/dev beyond local dev, touching a plan-referenced file.
        git checkout --quiet dev
        mkdir -p .aitask-scripts
        echo "changed" > .aitask-scripts/aitask_archive.sh
        git add .aitask-scripts/aitask_archive.sh
        git commit --quiet -m "remote-only change on dev"
        git push --quiet origin dev 2>/dev/null
        git reset --hard --quiet HEAD~1
        git checkout --quiet -
    )
    default_branch=$(git -C "$root/local" rev-parse --abbrev-ref HEAD)
    echo "$root|$default_branch"
}

# Mark a test repo as branch-mode (creates the .aitask-data stub).
mark_branch_mode() {
    local repo_root="$1"
    mkdir -p "$repo_root/.aitask-data"
    # _ait_detect_data_worktree checks for ".aitask-data/.git" file or dir.
    # An empty dir works fine.
    mkdir -p "$repo_root/.aitask-data/.git"
}

write_plan_file() {
    local target="$1"
    cat > "$target" <<'PLAN'
---
Task: t999_test.md
Base branch: main
---

## Plan

We will modify `.aitask-scripts/aitask_archive.sh` and add tests under
`tests/test_archive.sh`. The skill `.claude/skills/task-workflow/SKILL.md`
will reference the new behavior.
PLAN
}

# A plan shaped like a CONSUMER project's: its paths live under top-level
# directories this repository does not have. Before t1275 the helper filtered
# plan paths through a hardcoded allowlist of THIS repo's roots, so none of
# these survived and the overlap signal was unreachable in every installed-into
# project.
#
# `src/app/unreferenced.py` must NOT appear anywhere in this body -- not even in
# a negative sentence ("we do not touch ..."), which would still yield it as a
# token and make the 13c control non-discriminating.
write_consumer_plan_file() {
    local target="$1"
    cat > "$target" <<'PLAN'
---
Task: t999_consumer.md
Base branch: main
---

## Plan

We will modify `src/app/service.py` in the service layer, and update the
framework note at `aidocs/framework/notes.md` to match.
PLAN
}

cleanup_dirs=()
register_cleanup() { cleanup_dirs+=("$1"); }
# shellcheck disable=SC2154  # d is the loop variable in the trap body
trap 'for d in "${cleanup_dirs[@]:-}"; do [[ -n "$d" && -d "$d" ]] && rm -rf "$d"; done' EXIT

# ============================================================
# Test 1: LEGACY_MODE_SKIP
# ============================================================

echo "--- Test 1: legacy mode short-circuit ---"
legacy_repo=$(make_legacy_mode_repo)
register_cleanup "$legacy_repo"
plan_path="$legacy_repo/plan.md"
write_plan_file "$plan_path"

result=$(cd "$legacy_repo" && "$HELPER" main "$plan_path" 2>&1)
assert_eq "legacy mode emits LEGACY_MODE_SKIP" "LEGACY_MODE_SKIP" "$result"

# ============================================================
# Test 2: NO_REMOTE
# ============================================================

echo "--- Test 2: no origin remote ---"
no_remote=$(make_legacy_mode_repo)
register_cleanup "$no_remote"
mark_branch_mode "$no_remote"
plan_path="$no_remote/plan.md"
write_plan_file "$plan_path"

# Confirm: no origin remote configured (make_legacy_mode_repo uses git init).
# The branch must EXIST locally, or LOCAL_BRANCH_MISSING (checked first, since it
# needs no network) would win and this would assert NO_REMOTE for the wrong reason.
no_remote_branch=$(repo_default_branch "$no_remote")
result=$(cd "$no_remote" && "$HELPER" "$no_remote_branch" "$plan_path" 2>&1)
assert_eq "no origin remote emits NO_REMOTE" "NO_REMOTE" "$result"

# ============================================================
# Test 3: UP_TO_DATE
# ============================================================

echo "--- Test 3: up-to-date with origin ---"
pair=$(make_branch_mode_pair)
root="${pair%|*}"
default_branch="${pair##*|}"
register_cleanup "$root"
mark_branch_mode "$root/local"

plan_path="$root/local/plan.md"
write_plan_file "$plan_path"

result=$(cd "$root/local" && "$HELPER" "$default_branch" "$plan_path" 2>&1)
assert_eq "aligned local/remote emits UP_TO_DATE" "UP_TO_DATE" "$result"

# ============================================================
# Test 4: AHEAD + NO_OVERLAP (remote touches a file the plan does not reference)
# ============================================================

echo "--- Test 4: remote ahead, no overlap with plan ---"
pair=$(make_branch_mode_pair)
root="${pair%|*}"
default_branch="${pair##*|}"
register_cleanup "$root"

# Make a "second clone" to push from, simulating another PC
git clone --quiet "$root/origin.git" "$root/other" 2>/dev/null
(
    cd "$root/other" || exit 1
    git config user.email "other@example.com"
    git config user.name  "Other"
    mkdir -p docs
    echo "irrelevant" > docs/unrelated.md
    git add docs/unrelated.md
    git commit --quiet -m "unrelated change"
    git push --quiet origin "$default_branch"
)

mark_branch_mode "$root/local"
plan_path="$root/local/plan.md"
write_plan_file "$plan_path"

result=$(cd "$root/local" && "$HELPER" "$default_branch" "$plan_path" 2>&1)
assert_contains "remote ahead emits AHEAD" "AHEAD:1" "$result"
assert_contains "non-overlapping change emits NO_OVERLAP" "NO_OVERLAP" "$result"
assert_not_contains "no spurious OVERLAP line" "OVERLAP:" "$result"

# ============================================================
# Test 5: AHEAD + OVERLAP (remote touches a file referenced in the plan)
# ============================================================

echo "--- Test 5: remote ahead, overlap with plan-referenced file ---"
pair=$(make_branch_mode_pair)
root="${pair%|*}"
default_branch="${pair##*|}"
register_cleanup "$root"

git clone --quiet "$root/origin.git" "$root/other" 2>/dev/null
(
    cd "$root/other" || exit 1
    git config user.email "other@example.com"
    git config user.name  "Other"
    mkdir -p .aitask-scripts
    echo "patched" > .aitask-scripts/aitask_archive.sh
    git add .aitask-scripts/aitask_archive.sh
    git commit --quiet -m "patch archive script"
    git push --quiet origin "$default_branch"
)

mark_branch_mode "$root/local"
plan_path="$root/local/plan.md"
write_plan_file "$plan_path"

result=$(cd "$root/local" && "$HELPER" "$default_branch" "$plan_path" 2>&1)
assert_contains "remote ahead emits AHEAD" "AHEAD:1" "$result"
assert_contains "overlap on planned file" "OVERLAP:.aitask-scripts/aitask_archive.sh" "$result"
assert_not_contains "no NO_OVERLAP when there is overlap" "NO_OVERLAP" "$result"

# ============================================================
# Test 6: FETCH_FAILED (unreachable origin)
# ============================================================

echo "--- Test 6: fetch failure ---"
broken=$(make_legacy_mode_repo)
register_cleanup "$broken"
mark_branch_mode "$broken"
(
    cd "$broken" || exit 1
    git remote add origin "file:///nonexistent_$$_$RANDOM/origin.git"
)
plan_path="$broken/plan.md"
write_plan_file "$plan_path"

broken_branch=$(repo_default_branch "$broken")
result=$(cd "$broken" && "$HELPER" --timeout 2 "$broken_branch" "$plan_path" 2>&1)
assert_eq "unreachable origin emits FETCH_FAILED" "FETCH_FAILED" "$result"

# Signal separation: an EXISTING local branch behind an unreachable remote must
# stay FETCH_FAILED. Collapsing it into LOCAL_BRANCH_MISSING would fire a false
# "the Step 9 merge will fail" warning on every flaky network.
assert_not_contains "unreachable origin is not reported as a missing branch" \
    "LOCAL_BRANCH_MISSING" "$result"

# ============================================================
# Test 8: --unsynced bypasses the legacy short-circuit
# ============================================================

echo "--- Test 8: --unsynced in legacy mode ---"
unsynced_legacy=$(make_legacy_mode_repo)
register_cleanup "$unsynced_legacy"
plan_path="$unsynced_legacy/plan.md"
write_plan_file "$plan_path"
ul_branch=$(repo_default_branch "$unsynced_legacy")

# Negative control: without the flag, legacy mode still short-circuits.
result=$(cd "$unsynced_legacy" && "$HELPER" "$ul_branch" "$plan_path" 2>&1)
assert_eq "legacy without --unsynced still short-circuits" "LEGACY_MODE_SKIP" "$result"

# With the flag the short-circuit is skipped and evaluation continues.
result=$(cd "$unsynced_legacy" && "$HELPER" --unsynced "$ul_branch" "$plan_path" 2>&1)
assert_not_contains "--unsynced skips LEGACY_MODE_SKIP" "LEGACY_MODE_SKIP" "$result"
assert_eq "--unsynced in legacy mode falls through to NO_REMOTE" "NO_REMOTE" "$result"

# --- Test 8b: the payload case — legacy mode, origin/dev ahead of local dev ---
# Reaching NO_REMOTE only proves the short-circuit was skipped. This proves the
# bypass actually DETECTS drift on a branch legacy task_sync() never refreshes,
# which is the entire reason the flag exists.
echo "--- Test 8b: --unsynced detects drift on a stale legacy branch ---"
lpair=$(make_legacy_mode_pair_with_stale_dev)
lroot="${lpair%|*}"
register_cleanup "$lroot"
plan_path="$lroot/local/plan.md"
write_plan_file "$plan_path"

# Negative control first: without the flag the drift is invisible in legacy mode.
result=$(cd "$lroot/local" && "$HELPER" dev "$plan_path" 2>&1)
assert_eq "legacy mode hides dev drift without --unsynced" "LEGACY_MODE_SKIP" "$result"

result=$(cd "$lroot/local" && "$HELPER" --unsynced dev "$plan_path" 2>&1)
assert_contains "--unsynced reports drift on the stale branch" "AHEAD:1" "$result"
assert_contains "--unsynced still detects plan-file overlap" \
    "OVERLAP:.aitask-scripts/aitask_archive.sh" "$result"

# --- Test 8c: --unsynced is accepted in any position ---
echo "--- Test 8c: --unsynced flag position independence ---"
before=$(cd "$lroot/local" && "$HELPER" --unsynced dev "$plan_path" 2>&1)
after=$(cd "$lroot/local" && "$HELPER" dev "$plan_path" --unsynced 2>&1)
assert_eq "--unsynced after the positionals behaves identically" "$before" "$after"
mixed=$(cd "$lroot/local" && "$HELPER" dev --unsynced "$plan_path" 2>&1)
assert_eq "--unsynced between the positionals behaves identically" "$before" "$mixed"

# ============================================================
# Test 9: LOCAL_BRANCH_MISSING precedes NO_REMOTE
# ============================================================

echo "--- Test 9: missing local branch with no remote ---"
nb=$(make_legacy_mode_repo)
register_cleanup "$nb"
plan_path="$nb/plan.md"
write_plan_file "$plan_path"

# No origin AND no such local branch: the merge target cannot exist, which is
# knowable without any network. NO_REMOTE must not swallow that.
result=$(cd "$nb" && "$HELPER" --unsynced nosuchbranch "$plan_path" 2>&1)
assert_eq "missing local branch wins over NO_REMOTE" "LOCAL_BRANCH_MISSING" "$result"

# ============================================================
# Test 10: LOCAL_BRANCH_MISSING is tag-proof
# ============================================================

echo "--- Test 10: a tag must not satisfy the branch check ---"
tagged=$(make_legacy_mode_repo)
register_cleanup "$tagged"
plan_path="$tagged/plan.md"
write_plan_file "$plan_path"
git -C "$tagged" tag dev

# `git rev-parse --verify dev` resolves the TAG (gitrevisions ranks refs/tags
# above refs/heads), and `git checkout dev` would then detach HEAD so the merge
# lands on no branch. The check must be fully qualified to refs/heads/.
result=$(cd "$tagged" && "$HELPER" --unsynced dev "$plan_path" 2>&1)
assert_eq "a tag does not satisfy the local-branch check" "LOCAL_BRANCH_MISSING" "$result"

# ============================================================
# Test 11: an existing branch in branch mode is evaluated normally
# ============================================================

echo "--- Test 11: --unsynced does not otherwise alter the result ---"
pair=$(make_branch_mode_pair)
root="${pair%|*}"
default_branch="${pair##*|}"
register_cleanup "$root"
mark_branch_mode "$root/local"
plan_path="$root/local/plan.md"
write_plan_file "$plan_path"

result=$(cd "$root/local" && "$HELPER" --unsynced "$default_branch" "$plan_path" 2>&1)
assert_eq "--unsynced on an up-to-date branch still emits UP_TO_DATE" "UP_TO_DATE" "$result"

# ============================================================
# Test 12: merge-target staleness — the gap Step 9 cannot see (t1380)
# ============================================================
#
# Re-entry Routing's POSTIMPL route runs the Merge-Target Sync Pre-flight
# (.claude/skills/task-workflow/merge-target-sync.md) instead of the full drift
# check. That procedure's whole justification is that **Step 9 never fetches**:
# its pre-flight only checks local ref existence and worktree conflicts, and
# `git merge` is purely local. This pins all four legs of that argument against
# real git, so the justification cannot rot into folklore.
#
# Each leg uses its OWN fixture. That is not tidiness: 12b's merge leaves `dev`
# genuinely diverged, so running 12c on the same repo would (correctly) hit the
# refusal path instead of the fast-forward path. The separation mirrors the
# procedure's own ordering — the pre-flight syncs BEFORE Step 9 merges.
#
# `set -e` is active, so every deliberately-failing command is run through an
# if/else rather than `cmd; rc=$?`, which would abort before the capture.

echo "--- Test 12a/b: stale local output branch, origin ahead ---"
mpair=$(make_legacy_mode_pair_with_stale_dev)
mroot="${mpair%|*}"
register_cleanup "$mroot"
plan_path="$mroot/local/plan.md"
write_plan_file "$plan_path"
mlocal="$mroot/local"

# 12a. DETECTION — the helper sees the drift the pre-flight acts on.
result=$(cd "$mlocal" && "$HELPER" --unsynced dev "$plan_path" 2>&1)
assert_contains "12a: stale merge target reports AHEAD" "AHEAD:1" "$result"

# 12b. THE GAP — a purely local merge into the stale branch SUCCEEDS, and the
#      divergence survives it untouched. This is what makes "Step 9's own merge
#      surfaces the divergence" false: nothing fetched, so nothing was seen.
if (
    cd "$mlocal" || exit 1
    git checkout --quiet -b aitask/t_demo dev
    echo "task work" > task_file.txt
    git add task_file.txt
    git commit --quiet -m "task work"
    git checkout --quiet dev
    git merge --quiet --no-edit aitask/t_demo
) >/dev/null 2>&1; then merge_rc=0; else merge_rc=1; fi
assert_exit_zero_rc "12b: local merge into a stale branch succeeds" "$merge_rc"
behind=$(cd "$mlocal" && git rev-list --count dev..origin/dev)
assert_eq "12b: divergence still present after the local merge" "1" "$behind"

# 12c. THE RECOVERY — on a stale-but-unmerged branch (the state the pre-flight
#      actually runs in), the fast-forward-only sync closes the gap.
echo "--- Test 12c: --ff-only syncs a stale merge target ---"
cpair=$(make_legacy_mode_pair_with_stale_dev)
croot="${cpair%|*}"
register_cleanup "$croot"
clocal="$croot/local"
# Run the procedure's documented sequence verbatim, checkout included. The
# checkout is not ceremony: the fixture leaves HEAD on the default branch, and
# a bare `git merge --ff-only origin/dev` would fast-forward THAT branch
# instead — succeeding while leaving `dev` exactly as stale as before. The
# `symbolic-ref` assertion in merge-target-sync.md exists for this.
if (
    cd "$clocal" || exit 1
    git checkout --quiet dev --
    [ "$(git symbolic-ref --short HEAD)" = "dev" ]
    git merge --ff-only origin/dev
) >/dev/null 2>&1; then ff_rc=0; else ff_rc=1; fi
assert_exit_zero_rc "12c: --ff-only fast-forwards the stale branch" "$ff_rc"
behind=$(cd "$clocal" && git rev-list --count dev..origin/dev)
assert_eq "12c: no divergence after the sync" "0" "$behind"

# Negative control for the checkout: without it, the "sync" reports success
# while `dev` stays stale — the failure mode the symbolic-ref assertion pins.
npair=$(make_legacy_mode_pair_with_stale_dev)
nroot="${npair%|*}"
register_cleanup "$nroot"
nlocal="$nroot/local"
if (cd "$nlocal" && git merge --ff-only origin/dev) >/dev/null 2>&1; then nff_rc=0; else nff_rc=1; fi
assert_exit_zero_rc "12c-negctrl: merge without checkout still 'succeeds'" "$nff_rc"
behind=$(cd "$nlocal" && git rev-list --count dev..origin/dev)
assert_eq "12c-negctrl: but dev is still stale" "1" "$behind"

# 12d. THE REFUSAL — once the branches have genuinely diverged (local commits
#      origin lacks), --ff-only must FAIL and leave dev exactly where it was.
#      This pins "never rebase, reset, or force".
echo "--- Test 12d: --ff-only refuses a real divergence ---"
dpair=$(make_legacy_mode_pair_with_stale_dev)
droot="${dpair%|*}"
register_cleanup "$droot"
dlocal="$droot/local"
(
    cd "$dlocal" || exit 1
    git checkout --quiet dev
    echo "local only" > local_only.txt
    git add local_only.txt
    git commit --quiet -m "local-only commit on dev"
) >/dev/null 2>&1
before_sha=$(cd "$dlocal" && git rev-parse dev)
if (cd "$dlocal" && git merge --ff-only origin/dev) >/dev/null 2>&1; then
    diverge_rc=0
else
    diverge_rc=1
fi
assert_exit_nonzero_rc "12d: --ff-only refuses to move a diverged branch" "$diverge_rc"
after_sha=$(cd "$dlocal" && git rev-parse dev)
assert_eq "12d: dev is left exactly where it was" "$before_sha" "$after_sha"

# ============================================================
# Test 13: consumer-project directory layout (t1275)
# ============================================================
#
# The defect: plan paths were filtered through a hardcoded allowlist of this
# repository's own top-level directories, so in a project rooted at src/ (or
# anything else) the intersection was always empty and the helper emitted
# NO_OVERLAP on every run. Since AHEAD+OVERLAP is the *strong* half of the
# signal -- the only half a `remote_drift_check: strong-only` profile acts on --
# the check silently degraded to a no-op rather than failing visibly.
#
# 13b covers the same defect INSIDE this repo: aidocs/ was never in the
# allowlist, so plans referencing aidocs/framework/*.md never overlapped either.
#
# Negative controls (see the plan's mutation table): restoring the allowlist
# grep must break 13a, 13b AND 13d -- with it in place this plan yields an empty
# plan_paths, so the helper short-circuits to NO_OVERLAP. 13c is NOT
# discriminated by that mutation; it is guarded by the exact intersection, and
# breaks only if the intersection itself is removed.

echo "--- Test 13: consumer-project layout produces OVERLAP ---"
pair=$(make_branch_mode_pair)
root="${pair%|*}"
default_branch="${pair##*|}"
register_cleanup "$root"

git clone --quiet "$root/origin.git" "$root/other" 2>/dev/null
(
    cd "$root/other" || exit 1
    git config user.email "other@example.com"
    git config user.name  "Other"
    mkdir -p src/app aidocs/framework
    echo "patched"  > src/app/service.py
    echo "patched"  > aidocs/framework/notes.md
    echo "unrelated" > src/app/unreferenced.py
    git add src aidocs
    git commit --quiet -m "consumer-shaped remote change"
    git push --quiet origin "$default_branch"
)

mark_branch_mode "$root/local"
plan_path="$root/local/plan.md"
write_consumer_plan_file "$plan_path"

result=$(cd "$root/local" && "$HELPER" "$default_branch" "$plan_path" 2>&1)
assert_contains "13: remote ahead emits AHEAD" "AHEAD:1" "$result"
assert_contains "13a: overlap on a non-framework root (src/)" \
    "OVERLAP:src/app/service.py" "$result"
assert_contains "13b: overlap on aidocs/, absent from the old allowlist" \
    "OVERLAP:aidocs/framework/notes.md" "$result"
assert_not_contains "13c: a remote change the plan never mentions is not reported" \
    "OVERLAP:src/app/unreferenced.py" "$result"
assert_not_contains "13d: no NO_OVERLAP when there is overlap" "NO_OVERLAP" "$result"

# ============================================================
# Test 7: missing-arg behavior
# ============================================================

echo "--- Test 7: invalid CLI args ---"
result=$("$HELPER" 2>&1 || true)
assert_contains "missing args produces error" "<base-branch> is required" "$result"

# ============================================================
# Test 14: extraction characterization (t1569_1 pre-phase)
#
# Pins the plan-path extraction's observable output BEFORE it moves out of this
# script into lib/plan_paths.py, so the move is provably behavior-preserving
# rather than assumed. Written as a boundary test: the extraction is observable
# through OVERLAP: lines, which is exactly the surface a verdict depends on.
#
# The fixture is deliberately discriminating on the edges that a naive move
# would silently change:
#   * an all-phantom pair (the p259 shape -- 45 paths, 0 tracked, live)
#   * a leading-hyphen token, produced the way the live corpus produces one:
#     `SKILL-${p}-claude.md` yields `-claude.md`, because `$` and `{` are
#     outside the token charset and split it
#   * a `./`-prefixed path, which must be stripped
#   * a duplicated token, which must be deduped
#   * a collation quartet (ab / aB / a_b / a-b) plus a leading-dot path
#
# NOTE ON ORDER. The intersect below is `grep -Fxf`, which emits in the REMOTE
# list's order, so the plan-side sort order is NOT observable here and this test
# cannot pin it. That is not an oversight: it is why the move may change the
# plan-side collation (ambient `sort -u` -> codepoint) without changing any
# verdict. The canonical order is pinned where it IS observable, against
# lib/plan_paths.py directly, in tests/test_plan_paths.py.
# ============================================================

echo "--- Test 14: plan-path extraction characterization ---"

write_extraction_fixture_plan() {
    local target="$1"
    cat > "$target" <<'PLAN'
---
Task: t999_extraction.md
Base branch: main
---

## Plan

All-phantom (the p259 shape): aiscripts/batch_review.sh and aiscripts/helper.py
Leading hyphen, as the live corpus produces it: SKILL-${p}-claude.md
Dot-slash prefix: ./.aitask-scripts/aitask_archive.sh
Duplicate token: ./.aitask-scripts/aitask_archive.sh again
Collation quartet: ab.md aB.md a_b.md a-b.md
Outside the old extension allowlist: internal/pkg/server.go src/main.rs app/index.ts
PLAN
}

# Every path the extension grammar extracted from that fixture, as a set --
# captured from the pre-move pipeline on 2026-08-27. The reference scan (t1877)
# must still report every one of them when the remote touches them (no lost
# overlap), and additionally the Go/Rust/TS sources the grammar never saw.
EXTRACTION_GOLDEN='-claude.md
.aitask-scripts/aitask_archive.sh
a-b.md
aB.md
a_b.md
ab.md
aiscripts/batch_review.sh
aiscripts/helper.py'
BEYOND_GRAMMAR='app/index.ts
internal/pkg/server.go
src/main.rs'

pair=$(make_branch_mode_pair)
root="${pair%|*}"
default_branch="${pair##*|}"
register_cleanup "$root"

# Make the remote touch EVERY token in the golden, so the OVERLAP set is the
# extracted set and nothing is hidden by a non-matching remote.
git clone --quiet "$root/origin.git" "$root/other" 2>/dev/null
(
    cd "$root/other" || exit 1
    git config user.email "other@example.com"
    git config user.name  "Other"
    while IFS= read -r f; do
        [[ -z "$f" ]] && continue
        mkdir -p "$(dirname -- "$f")" 2>/dev/null || true
        printf 'touched\n' > "$f"
        git add -- "$f"
    done <<< "$EXTRACTION_GOLDEN"$'\n'"$BEYOND_GRAMMAR"
    git commit --quiet -m "touch every extraction-golden path"
    git push --quiet origin "$default_branch"
)

mark_branch_mode "$root/local"
plan_path="$root/local/extraction_plan.md"
write_extraction_fixture_plan "$plan_path"

result=$(cd "$root/local" && "$HELPER" "$default_branch" "$plan_path" 2>&1)
extracted=$(printf '%s\n' "$result" | sed -n 's/^OVERLAP://p' | LC_ALL=C sort)
expected=$(printf '%s\n%s\n' "$EXTRACTION_GOLDEN" "$BEYOND_GRAMMAR" | LC_ALL=C sort)

assert_eq "14a: OVERLAP set = the old golden plus the sources beyond its grammar" \
    "$expected" "$extracted"
assert_contains "14b: a Go source is now referenced" \
    "OVERLAP:internal/pkg/server.go" "$result"
assert_contains "14c: a Rust source is now referenced" \
    "OVERLAP:src/main.rs" "$result"
assert_contains "14d: a TypeScript source is now referenced" \
    "OVERLAP:app/index.ts" "$result"
# Dedupe: the ./-prefixed path appears twice in the fixture and once in the set.
archive_hits=$(printf '%s\n' "$result" | grep -c '^OVERLAP:\.aitask-scripts/aitask_archive\.sh$' || true)
assert_eq "14e: a duplicated token is deduped to one record" "1" "$archive_hits"

# ============================================================
# Test 15: local-only commits must not inflate OVERLAP (t1724)
# ============================================================
#
# The bug: the helper used `git diff BASE..origin/BASE`, which in `git diff` is a
# plain tip-to-tip comparison, so a file the USER changed locally was reported as
# remote drift. The three-dot form diffs from the merge base.
#
# Both plan-referenced files are load-bearing here:
#   - .aitask-scripts/aitask_archive.sh -- changed on the REMOTE only. It is the
#     POSITIVE CONTROL: it must still be reported, so the test cannot pass by the
#     overlap set having gone empty.
#   - tests/test_archive.sh            -- changed LOCALLY only. It must NOT be
#     reported. Without this local-only commit the fixture passes under BOTH diff
#     forms and proves nothing.

echo "--- Test 15: local-only commits do not inflate OVERLAP ---"
pair=$(make_branch_mode_pair)
root="${pair%|*}"
default_branch="${pair##*|}"
register_cleanup "$root"

# Both sides share tests/test_archive.sh at a common base commit.
(
    cd "$root/local" || exit 1
    mkdir -p tests
    echo "baseline" > tests/test_archive.sh
    git add tests/test_archive.sh
    git commit --quiet -m "add shared test file"
    git push --quiet origin "$default_branch"
)

# Another PC pushes a change to a DIFFERENT plan-referenced file.
git clone --quiet "$root/origin.git" "$root/other" 2>/dev/null
(
    cd "$root/other" || exit 1
    git config user.email "other@example.com"
    git config user.name  "Other"
    mkdir -p .aitask-scripts
    echo "patched" > .aitask-scripts/aitask_archive.sh
    git add .aitask-scripts/aitask_archive.sh
    git commit --quiet -m "patch archive script"
    git push --quiet origin "$default_branch"
)

# The user's OWN local commit touches the shared file. Never pushed.
(
    cd "$root/local" || exit 1
    echo "local edit" >> tests/test_archive.sh
    git add tests/test_archive.sh
    git commit --quiet -m "local-only change to the shared test file"
)

mark_branch_mode "$root/local"
plan_path="$root/local/plan.md"
write_plan_file "$plan_path"

result=$(cd "$root/local" && "$HELPER" "$default_branch" "$plan_path" 2>&1)
assert_contains "15a: remote-only commit count is unaffected" "AHEAD:1" "$result"
assert_contains "15b: positive control -- remote-changed planned file still overlaps" \
    "OVERLAP:.aitask-scripts/aitask_archive.sh" "$result"
assert_not_contains "15c: locally-changed planned file is NOT reported as remote drift" \
    "OVERLAP:tests/test_archive.sh" "$result"
assert_not_contains "15d: no NO_OVERLAP when there is overlap" "NO_OVERLAP" "$result"

# ============================================================
# Test 16: reference scan tiers and edge cases (t1877)
#
# The drift check tests each remote-changed path for a reference in the plan
# (plan_paths.reference_kinds). One remote commit touches every path below; each
# sub-case is a different plan against that same drift.
# ============================================================

echo "--- Test 16: reference scan (t1877) ---"

pair=$(make_branch_mode_pair)
root="${pair%|*}"
default_branch="${pair##*|}"
register_cleanup "$root"

NFD_NAME=$(printf 'src/cafe\314\201.py')     # decomposed, as APFS stores it
NFC_NAME=$(printf 'src/caf\303\251.py')      # composed, as an editor writes it
BAD_NAME=$(printf 'src/bad\351.py')          # not valid UTF-8
NL_NAME=$(printf 'src/new\nline.py')         # a newline inside the name

git clone --quiet "$root/origin.git" "$root/other" 2>/dev/null
(
    cd "$root/other" || exit 1
    git config user.email "other@example.com"
    git config user.name  "Other"
    for f in src/Makefile ait goengines/internal/tools/x/main.go x/SKILL.md \
             src/app.py "$NFD_NAME" "$BAD_NAME" "$NL_NAME"; do
        mkdir -p "$(dirname -- "$f")"
        printf 'touched\n' > "$f"
        git add -- "$f"
    done
    git commit --quiet -m "remote-only: every Test 16 path"
    git push --quiet origin "$default_branch"
)
mark_branch_mode "$root/local"

run16() {  # run16 <plan-body>  -> helper output; exit status in rc16
    local plan="$root/local/plan16.md"
    printf -- '---\nTask: t999_refs.md\n---\n\n%s\n' "$1" > "$plan"
    rc16=0
    out16=$(cd "$root/local" && "$HELPER" "$default_branch" "$plan" 2>/dev/null) || rc16=$?
}

run16 'We rewrite `src/Makefile` targets.'
assert_contains "16a: an extensionless file under a directory is a strong OVERLAP" \
    "OVERLAP:src/Makefile" "$out16"

# 16b is the backward-compat contract for a parser that ignores WEAK_OVERLAP:
# the verdict lines are exactly the pre-t1877 shape, with the weak line between.
run16 'First run `ait setup`, then check the board.'
assert_eq "16b: a bare root name is WEAK only; NO_OVERLAP still emitted, in order" \
    "AHEAD:1"$'\n'"WEAK_OVERLAP:ait"$'\n'"NO_OVERLAP" "$out16"
assert_eq "16b: weak-only run exits 0" "0" "$rc16"

run16 'Edit internal/tools/x/main.go in the Go module.'
assert_contains "16c: a module-relative suffix is a WEAK_OVERLAP" \
    "WEAK_OVERLAP:goengines/internal/tools/x/main.go" "$out16"
assert_contains "16c: ...and does not make a strong verdict" "NO_OVERLAP" "$out16"

run16 'Edit the template `x/SKILL.md.j2` and regenerate.'
assert_not_contains "16d: x/SKILL.md.j2 does not reference x/SKILL.md (old false positive)" \
    "OVERLAP:x/SKILL.md" "$out16"
assert_contains "16d: ...so the verdict is NO_OVERLAP" "NO_OVERLAP" "$out16"

run16 'Pin src/app.py@v2 as the baseline.'
assert_not_contains "16e: src/app.py@v2 does not reference src/app.py" \
    "OVERLAP:src/app.py" "$out16"

run16 "Rename \`$NFC_NAME\` (composed form)."
assert_contains "16f: an NFD path cited in NFC overlaps, reported as git named it" \
    "OVERLAP:$NFD_NAME" "$out16"

run16 "Also touches $BAD_NAME and src/Makefile."
assert_eq "16g: a non-UTF-8 remote path does not break the helper (exit 0)" "0" "$rc16"
assert_contains "16g: ...and the verdict is still reached" "OVERLAP:src/Makefile" "$out16"
assert_contains "16g: ...and the undecodable path round-trips byte for byte" \
    "OVERLAP:$BAD_NAME" "$out16"

run16 'Only src/Makefile here; a newline-named remote file exists too.'
assert_eq "16h: a newline in a remote path does not crash the helper" "0" "$rc16"
assert_not_contains "16h: ...and cannot inject a protocol line" "OVERLAP:line.py" "$out16"

# ============================================================
# Test 17: a failed `git diff` keeps its best-effort meaning (t1877)
#
# The remote file list moved from `$(git diff) || x=""` to a redirect into a
# temp file. Under errexit a failure there must still yield NO_OVERLAP / exit 0,
# never a script that dies right after AHEAD, and never EXTRACT_FAILED (which is
# reserved for the plan scan).
# ============================================================

echo "--- Test 17: git diff failure is best-effort ---"

plan17="$root/local/plan17.md"
printf -- '---\nTask: t999_diff.md\n---\n\nWe rewrite `src/Makefile`.\n' > "$plan17"

# Positive control: without the fault the same fixture reaches OVERLAP, so the
# wrapper below provably stands between the helper and the diff call.
ctl=$(cd "$root/local" && "$HELPER" "$default_branch" "$plan17" 2>/dev/null)
assert_contains "17a: positive control reaches the diff and the scan" \
    "OVERLAP:src/Makefile" "$ctl"

REAL_GIT=$(command -v git)
wrap_dir="$root/gitwrap"
mkdir -p "$wrap_dir"
cat > "$wrap_dir/git" <<WRAP
#!/usr/bin/env bash
if [[ "\${1:-}" == "diff" && "\${2:-}" == "--name-only" ]]; then
    exit 128
fi
exec "$REAL_GIT" "\$@"
WRAP
chmod +x "$wrap_dir/git"

rc17=0
out17=$(cd "$root/local" && PATH="$wrap_dir:$PATH" "$HELPER" "$default_branch" "$plan17" 2>/dev/null) || rc17=$?
assert_eq "17b: diff failure yields exactly AHEAD then NO_OVERLAP" \
    "AHEAD:1"$'\n'"NO_OVERLAP" "$out17"
assert_eq "17c: diff failure exits 0" "0" "$rc17"
assert_not_contains "17d: diff failure is not EXTRACT_FAILED" "EXTRACT_FAILED" "$out17"

# ============================================================
# Summary
# ============================================================

echo ""
echo "================================"
echo "Results: $PASS passed, $FAIL failed (of $TOTAL total)"
echo "================================"

if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
