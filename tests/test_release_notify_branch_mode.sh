#!/usr/bin/env bash
# test_release_notify_branch_mode.sh - the release-notify posting gate against
# a REAL separate task-data worktree (t2261_2): tests/lib/sync_fixture.sh's
# bare remote + branch-mode clone with .aitask-data, aitasks/ symlinks, a
# copied framework tree and a hostname shim.
#
# Traced before reuse: setup_repo builds remote.git, local/ (main + the
# aitask-data worktree, both pushed), copies ./ait and .aitask-scripts into
# local/, writes local/bin/hostname (TEST_HOSTNAME, default testhost) and
# initializes the lock branch. It creates no tags and no project_config.yaml,
# and its origin is a bare local path, so this test adds tags, a config, and a
# github.com origin URL rewritten (url.<path>.insteadOf) to that bare repo.
#
# Coverage:
#   (1) fresh -> posts once, the move committed on the data branch
#   (2) failed fetch -> INCOMPLETE:freshness:unknown:fetch_error
#   (3) behind -> INCOMPLETE:freshness:behind:1
#   (4) rev-list failing -> unknown:count_failed (no 0 fallback)
#   (5) the wrapper's RECONCILE_FAILED on CONFLICT and on a dead network
#   (6) an after_remove interruption, then a retry -> RESUMED, no new comment
#
# All assertions run in the main shell, so the in-process counters are enough.
#
# Run: bash tests/test_release_notify_branch_mode.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/git_config_isolation.sh"
sync_isolate_git_config
. "$PROJECT_DIR/tests/lib/sync_fixture.sh"

PASS=0
FAIL=0
TOTAL=0

command -v jq >/dev/null 2>&1 || { echo "SKIP: jq is required by the gh stub"; exit 0; }

TMP="$(mktemp -d -p "$_SYNC_FIXTURE_BASE")"
. "$PROJECT_DIR/tests/lib/release_notify_fixture.sh"
rnf_write_stubs
REAL_GIT="$(command -v git)"

# bm_repo — a branch-mode fixture in BM, ready for release-notify.
bm_repo() {
    BM="$(setup_repo)"
    L="$BM/local"
    export AITASKS_LOCK_DIR="$BM/locks"
    mkdir -p "$AITASKS_LOCK_DIR"
    git -C "$L" remote set-url origin https://github.com/o/r.git
    git -C "$L" config url."$BM/remote.git".insteadOf https://github.com/o/r.git
    rnf_commit "$L" "feature: a (t10)"
    git -C "$L" tag v1.0.0
    rnf_commit "$L" "feature: b (t50)"
    git -C "$L" tag v1.1.0
    git -C "$L" push -q origin main --tags 2>/dev/null
    printf 'release_notify_host: testhost\n' > "$L/.aitask-data/aitasks/metadata/project_config.yaml"
    git -C "$L/.aitask-data" add -A
    git -C "$L/.aitask-data" commit -qm "ait: config"
    PENDING="$(rnf_record "$L" 50 https://github.com/o/r/issues/50)"
    git -C "$L/.aitask-data" push -q origin aitask-data 2>/dev/null
    rnf_reset_state
    rnf_release v1.1.0 1 false
}

# bm_run <args…> — the copied consumer, cwd = the clone, stubs + shim first.
bm_run() {
    RNF_RC=0
    ( cd "$L" && PATH="$RNF_BIN:$L/bin:$PATH" ./.aitask-scripts/aitask_release_notify.sh "$@" ) \
        > "$TMP/bm.out" 2> "$TMP/bm.err" || RNF_RC=$?
    RNF_OUT="$(cat "$TMP/bm.out")"
    RNF_ERR="$(cat "$TMP/bm.err")"
}
posts() { rnf_log_count '^gh issue comment'; }

# ---------------------------------------------------------------------------
# (1) fresh -> posts once
bm_repo
bm_run --tag v1.1.0 --no-push
assert_eq "(1) exit 0" "0" "$RNF_RC"
assert_contains "(1) fresh" "FRESHNESS:fresh" "$RNF_OUT"
assert_contains "(1) posted" "POSTED:50|https://github.com/o/r/issues/50" "$RNF_OUT"
assert_eq "(1) one post" "1" "$(posts)"
assert_contains "(1) the move is a data-branch commit" "ait: Record release notice for t50 (v1.1.0)" \
    "$(git -C "$L/.aitask-data" log -1 --format=%s)"
assert_eq "(1) the data worktree is clean" "" \
    "$(git -C "$L/.aitask-data" status --porcelain -- aitasks/metadata/release_issues)"
assert_eq "(1) main got no ledger commit" "" \
    "$(git -C "$L" log --format=%s -3 | grep 'release notice' || true)"
bm_run --tag v1.1.0
assert_contains "(1) push reported" "PUSH:" "$RNF_OUT"
assert_eq "(1) re-run: still one post" "1" "$(posts)"

# ---------------------------------------------------------------------------
# (2) failed fetch
bm_repo
git -C "$L" config --unset url."$BM/remote.git".insteadOf
git -C "$L" config url."$BM/gone.git".insteadOf https://github.com/o/r.git
bm_run --tag v1.1.0 --no-push
assert_eq "(2) exit 3" "3" "$RNF_RC"
assert_contains "(2) fetch error" "INCOMPLETE:freshness:unknown:fetch_error" "$RNF_OUT"
assert_contains "(2) recovery line" "HINT:run ./ait sync (resolve any conflict), then re-run: ait release-notify --tag v1.1.0" "$RNF_OUT"
assert_eq "(2) no post" "0" "$(posts)"
assert_file_exists "(2) stays pending" "$L/$PENDING"

# ---------------------------------------------------------------------------
# (3) behind: another clone pushed a new record
bm_repo
git clone -q "$BM/remote.git" "$BM/second" 2>/dev/null
git -C "$BM/second" checkout -q aitask-data 2>/dev/null
git -C "$BM/second" config user.email s@example.com
git -C "$BM/second" config user.name Second
mkdir -p "$BM/second/aitasks/metadata/release_issues/pending"
printf 'x\n' > "$BM/second/aitasks/metadata/release_issues/pending/10--0000000000000000.rec"
git -C "$BM/second" add -A
git -C "$BM/second" commit -qm "ait: another record"
git -C "$BM/second" push -q origin aitask-data 2>/dev/null
bm_run --tag v1.1.0 --no-push
assert_eq "(3) exit 3" "3" "$RNF_RC"
assert_contains "(3) behind" "INCOMPLETE:freshness:behind:1" "$RNF_OUT"
assert_eq "(3) no post" "0" "$(posts)"

# ---------------------------------------------------------------------------
# (4) rev-list fails: never read as a count of 0
bm_repo
mkdir -p "$TMP/gitshim"
cat > "$TMP/gitshim/git" <<EOF
#!/usr/bin/env bash
for a in "\$@"; do
    if [[ "\$a" == rev-list ]]; then echo "fatal: simulated rev-list failure" >&2; exit 128; fi
done
exec "$REAL_GIT" "\$@"
EOF
chmod +x "$TMP/gitshim/git"
RNF_RC=0
( cd "$L" && PATH="$TMP/gitshim:$RNF_BIN:$L/bin:$PATH" ./.aitask-scripts/aitask_release_notify.sh --tag v1.1.0 --no-push ) \
    > "$TMP/bm.out" 2>&1 || RNF_RC=$?
RNF_OUT="$(cat "$TMP/bm.out")"
assert_eq "(4) exit 3" "3" "$RNF_RC"
assert_contains "(4) count failed" "INCOMPLETE:freshness:unknown:count_failed" "$RNF_OUT"
assert_eq "(4) no post" "0" "$(posts)"

# ---------------------------------------------------------------------------
# (5) the wrapper requires a successful reconciliation
WPOLICY=$'release_notify_host: testhost\nrelease_publication_workflow: release.yml\nrelease_publication_assets:\n  - app-{tag}.tar.gz\n'
wrapper_ready() {
    bm_repo
    cp "$PROJECT_DIR/wait_release_and_notify.sh" "$L/"
    printf '%s' "$WPOLICY" > "$L/.aitask-data/aitasks/metadata/project_config.yaml"
    git -C "$L/.aitask-data" commit -qam "ait: policy"
    git -C "$L/.aitask-data" push -q origin aitask-data 2>/dev/null
    rnf_release v1.1.0 1 false "app-v1.1.0.tar.gz:uploaded:5"
    rnf_runs v1.1.0 1 "5 $(git -C "$L" rev-parse 'v1.1.0^{commit}') v1.1.0 completed success"
}
w_run() {
    RNF_RC=0
    ( cd "$L" && PATH="${W_PATH_PREFIX:-}$RNF_BIN:$L/bin:$PATH" ./wait_release_and_notify.sh v1.1.0 --timeout 5 --interval 0 ) \
        > "$TMP/w.out" 2> "$TMP/w.err" || RNF_RC=$?
    RNF_OUT="$(cat "$TMP/w.out")"
}
wrapper_ready
# Both clones change the same shared file differently: a rebase conflict.
git clone -q "$BM/remote.git" "$BM/second" 2>/dev/null
git -C "$BM/second" checkout -q aitask-data 2>/dev/null
git -C "$BM/second" config user.email s@example.com
git -C "$BM/second" config user.name Second
printf 'remote side\n' > "$BM/second/aitasks/metadata/stats_config.json"
git -C "$BM/second" commit -qam "ait: remote edit"
git -C "$BM/second" push -q origin aitask-data 2>/dev/null
printf 'local side\n' > "$L/.aitask-data/aitasks/metadata/stats_config.json"
git -C "$L/.aitask-data" commit -qam "ait: local edit"
w_run
assert_eq "(5) conflict: exit 5" "5" "$RNF_RC"
assert_contains "(5) conflict: reconcile failed" "RECONCILE_FAILED:CONFLICT" "$RNF_OUT"
assert_contains "(5) conflict: retry printed" "RETRY: ./wait_release_and_notify.sh v1.1.0" "$RNF_OUT"
assert_eq "(5) conflict: no post" "0" "$(posts)"
assert_file_exists "(5) conflict: stays pending" "$L/$PENDING"

wrapper_ready
cat > "$TMP/gitshim/git" <<EOF
#!/usr/bin/env bash
for a in "\$@"; do
    if [[ "\$a" == fetch || "\$a" == pull || "\$a" == push ]]; then
        echo "fatal: unable to access 'https://github.com/o/r.git/': Could not resolve host: github.com" >&2
        exit 128
    fi
done
exec "$REAL_GIT" "\$@"
EOF
chmod +x "$TMP/gitshim/git"
# Every fetch fails as on a dead network. `ait sync --batch` reports that as
# DEFERRED:fetch_exclusion:data_branch_fetch_failed in this tree (NO_NETWORK is
# its token for a timed-out cycle); either way the token is not one of the six
# the wrapper proceeds on, which is the property under test.
W_PATH_PREFIX="$TMP/gitshim:" w_run
assert_eq "(5) no network: exit 5" "5" "$RNF_RC"
assert_contains "(5) no network: reconcile failed" "RECONCILE_FAILED:DEFERRED:fetch_exclusion" "$RNF_OUT"
assert_contains "(5) no network: retry printed" "RETRY: ./wait_release_and_notify.sh v1.1.0" "$RNF_OUT"
assert_eq "(5) no network: no post" "0" "$(posts)"
assert_file_exists "(5) no network: stays pending" "$L/$PENDING"

# ---------------------------------------------------------------------------
# (6) an interrupted move in the real data worktree, then a retry
bm_repo
RELEASED="aitasks/metadata/release_issues/released/v1.1.0/$(basename "$PENDING")"
: > "$AITASKS_LOCK_DIR/.ril_move_test_seams"
_RIL_MOVE_TEST_SEAM=after_remove bm_run --tag v1.1.0 --no-push
rm -f "$AITASKS_LOCK_DIR/.ril_move_test_seams"
assert_contains "(6) the seam fired" "TEST SEAM ACTIVE" "$RNF_ERR"
assert_eq "(6) killed run: exit 4" "4" "$RNF_RC"
assert_eq "(6) one comment" "1" "$(rnf_comment_count o_r_50)"
assert_contains "(6) residue: a tracked deletion" " D $PENDING" \
    "$(git -C "$L/.aitask-data" status --porcelain -- aitasks/metadata/release_issues)"
before="$(git -C "$L/.aitask-data" rev-parse HEAD)"
bm_run --tag v1.1.0 --no-push
assert_eq "(6) retry exit 0" "0" "$RNF_RC"
assert_contains "(6) resumed" "RESUMED:50|https://github.com/o/r/issues/50|$RELEASED" "$RNF_OUT"
assert_eq "(6) no new comment" "1" "$(rnf_comment_count o_r_50)"
assert_eq "(6) one data-branch commit with both paths" \
    "$(printf '%s\n%s' "$PENDING" "$RELEASED" | sort)" \
    "$(git -C "$L/.aitask-data" log --no-renames --format= --name-only "$before..HEAD" | sort)"
assert_eq "(6) the data worktree is clean" "" \
    "$(git -C "$L/.aitask-data" status --porcelain -- aitasks/metadata/release_issues)"

# --- summary -----------------------------------------------------------------
echo
echo "Results: $PASS passed, $FAIL failed (of $TOTAL)"
[[ "$FAIL" -eq 0 ]]
