#!/usr/bin/env bash
# test_sync_fetch_exclusion.sh - `ait sync`'s routine-fetch exclusion guard for
# the gitbranch artifact store (t2099).
#
# Before EACH broad fetch (the initial one and the rejected-push retry), the
# guard fetches the data branch alone, applies the exclusion from the union of
# the local and fetched config + store record, and only then lets the broad fetch
# run; when protection cannot be established it defers WITHOUT the broad fetch.
# After every convergence a no-network reconciliation settles what the union
# kept on the safe side (a dropped retired branch, a disabled dedicated mode).
#
# X is another clone that publishes data-branch changes (config + store record)
# and store branches; Y is the sync fixture's branch-mode clone. Every remote is
# reached through file:// — a plain-path clone hard-links objects and would hide
# whether a fetch downloaded the store. "No store objects" is asserted on the
# exact store commit X pushed.
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/git_config_isolation.sh"
sync_isolate_git_config
. "$PROJECT_DIR/tests/lib/sync_fixture.sh"
PASS=0; FAIL=0; TOTAL=0

SID="0123456789abcdef0123456789abcdef"

# ── Fixture helpers ───────────────────────────────────────────────────────────

# world -- a sync fixture with origin on file://, plus the publishing clone X.
world() {
    T="$(setup_repo)"
    Y="$T/local"
    git -C "$Y" remote set-url origin "file://$T/remote.git"
    git clone -q "file://$T/remote.git" "$T/X" 2>/dev/null
    git -C "$T/X" config user.email x@test.com; git -C "$T/X" config user.name X
    git -C "$T/X" config commit.gpgsign false
}

# xpub <config-branch|-> <record-branch|-> [extra gitbranch yaml lines...] [-- retired...]
# -- publish the data-branch config and store record from X.
xpub() {
    local cb="$1" rb="$2"; shift 2
    local -a extra=() retired=()
    while [[ $# -gt 0 && "$1" != "--" ]]; do extra+=( "$1" ); shift; done
    [[ "${1:-}" == "--" ]] && { shift; retired=( "$@" ); }
    (
        cd "$T/X" || exit 1
        git fetch -q origin aitask-data && git checkout -q -B aitask-data origin/aitask-data || exit 1
        mkdir -p aitasks/metadata artifacts
        if [[ "$cb" != - ]]; then
            {
                printf 'artifacts:\n  backends:\n    gitbranch:\n      branch: %s\n' "$cb"
                local l; for l in "${extra[@]}"; do printf '      %s\n' "$l"; done
            } > aitasks/metadata/project_config.yaml
        fi
        if [[ "$rb" != - ]]; then
            local r="" x
            for x in "${retired[@]}"; do r+="${r:+, }\"$x\""; done
            if [[ -n "$r" ]]; then
                printf '{"store_id": "%s", "branch": "%s", "retired": [%s]}\n' "$SID" "$rb" "$r" > artifacts/gitbranch_store.json
            else
                printf '{"store_id": "%s", "branch": "%s"}\n' "$SID" "$rb" > artifacts/gitbranch_store.json
            fi
        fi
        git add -A && git commit -q -m "x: publish" && git push -q origin aitask-data
    ) >/dev/null 2>&1
}

# xstore <branch> -- push a fresh store commit (a unique 32 KiB blob); print it.
xstore() {
    (
        cd "$T/X" || exit 1
        local blob tree c
        blob="$(head -c 32768 /dev/urandom | git hash-object -w --stdin)" || exit 1
        tree="$(printf '100644 blob %s\tblob\n' "$blob" | git mktree)" || exit 1
        c="$(echo store | git commit-tree "$tree")" || exit 1
        git push -qf origin "$c:refs/heads/$1" 2>/dev/null || exit 1
        echo "$c"
    )
}

has_obj() { git -C "$1" cat-file -e "$2" 2>/dev/null && echo yes || echo no; }
tref() { git -C "$1" rev-parse -q --verify "$2" 2>/dev/null || echo absent; }
fetchvals() { git -C "$1" config --get-all "remote.${2:-origin}.fetch" 2>/dev/null || true; }
first_line() { printf '%s\n' "$1" | head -n1; }
enable_seams() { mkdir -p "$T/locks" && touch "$T/locks/.ait_sync_test_seams"; }
# local_task_commit -- give Y a local data commit (so the push path runs).
local_task_commit() { printf 'local %s\n' "$RANDOM" >> "$Y/.aitask-data/aitasks/t20_beta.md"; }

# ═════════════════════════════════════════════════════════════════════════════
echo "--- 1. First sync after a published migration fetches no new store objects ---"
world
A1="$(xstore store-a)"
xpub store-a store-a
out="$(run_sync "$T")"
assert_contains "1: the first sync pulled the config" "store-a" "$(cat "$Y/aitasks/metadata/project_config.yaml" 2>/dev/null)"
assert_eq "1: even the very first sync did not download the store" "no" "$(has_obj "$Y" "$A1")"
assert_contains "1: store-a is excluded" "^refs/heads/store-a" "$(fetchvals "$Y")"
B1="$(xstore store-b)"
xpub store-b store-b -- store-a
out="$(run_sync "$T")"
assert_eq "1: sync completed" "PULLED" "$(first_line "$out")"
assert_eq "1: no store-b tracking ref" "absent" "$(tref "$Y" refs/remotes/origin/store-b)"
assert_eq "1: the new store branch was not downloaded on the FIRST sync after the record" "no" "$(has_obj "$Y" "$B1")"
assert_contains "1: store-b excluded" "^refs/heads/store-b" "$(fetchvals "$Y")"
assert_contains "1: the retired store-a stays excluded" "^refs/heads/store-a" "$(fetchvals "$Y")"
A2="$(xstore store-a)"; B2="$(xstore store-b)"
run_sync "$T" >/dev/null
git -C "$Y" fetch -q --all --prune 2>/dev/null
assert_eq "1: later syncs and fetch --all skip store-a" "no" "$(has_obj "$Y" "$A2")"
assert_eq "1: later syncs and fetch --all skip store-b" "no" "$(has_obj "$Y" "$B2")"

echo "--- 2. Fresh --single-branch clone + setup + sync ---"
Z="$T/Z"
git clone -q --single-branch -b main "file://$T/remote.git" "$Z" 2>/dev/null
(
    cd "$Z" || exit 1
    git config user.email z@test.com; git config user.name Z; git config commit.gpgsign false
    # setup_data_branch's own sequence (t2127): explicit-refspec fetch, local
    # branch from the tracking ref, worktree, then the upstream reconcile that
    # maps aitask-data so @{u} resolves in a --single-branch clone.
    source .aitask-scripts/lib/data_symlinks.sh
    ait_fetch_data_branch "$PWD"
    ait_ensure_local_data_branch "$PWD"
    git worktree add -q .aitask-data aitask-data
    ait_report_data_branch_upstream "$PWD"
    mkdir -p .aitask-data/aiplans
    # main already carries the aitasks/ and aiplans/ symlinks (the fixture commits them).
    mkdir -p bin; cp "$Y/bin/hostname" bin/
) >/dev/null 2>&1
( source "$Z/.aitask-scripts/aitask_setup.sh" --source-only && setup_artifact_fetch_exclusion ) >/dev/null 2>&1
assert_contains "2: setup excluded the store" "^refs/heads/store-b" "$(fetchvals "$Z")"
assert_contains "2: setup excluded the retired store" "^refs/heads/store-a" "$(fetchvals "$Z")"
B3="$(xstore store-b)"
# A data-branch commit for Z to pull, so the verdict proves @{u} was followed.
(
    cd "$T/X" || exit 1
    git fetch -q origin aitask-data && git checkout -q -B aitask-data origin/aitask-data || exit 1
    printf 'z\n' >> zmark && git add zmark && git commit -qm "zmark" && git push -q origin aitask-data
) >/dev/null 2>&1
out="$( cd "$Z" && export PATH="$PWD/bin:$PATH" TEST_HOSTNAME=testhost AITASKS_LOCK_DIR="$T/zlocks" \
    && ./.aitask-scripts/aitask_sync.sh --batch 2>/dev/null )"
assert_eq "2: aitask-data@{u} resolves" "refs/remotes/origin/aitask-data" \
    "$(git -C "$Z" rev-parse --symbolic-full-name 'aitask-data@{u}' 2>/dev/null)"
assert_eq "2: sync completed" "PULLED" "$(first_line "$out")"
assert_eq "2: the published data commit was pulled" "$(git -C "$T/remote.git" rev-parse aitask-data)" \
    "$(git -C "$Z" rev-parse aitask-data)"
assert_eq "2: no store tracking ref" "absent" "$(tref "$Z" refs/remotes/origin/store-b)"
# Exact, not a count: sync legitimately creates local objects (the lock-branch
# init commit), so assert none of the store commit's own objects arrived.
present=0
while read -r o _; do git -C "$Z" cat-file -e "$o" 2>/dev/null && present=$((present + 1)); done \
    < <(git -C "$T/X" rev-list --objects "$B3")
assert_eq "2: control — the scan saw the store commit's 3 objects" "3" "$(git -C "$T/X" rev-list --objects "$B3" | wc -l | tr -d ' ')"
assert_eq "2: none of the store commit's objects (commit, tree, blob) were downloaded" "0" "$present"

echo "--- 3. Push-retry route: the retry fetch is guarded too ---"
world
xstore store-a >/dev/null; xpub store-a store-a
run_sync "$T" >/dev/null
local_task_commit
cat > "$T/hook.sh" <<EOF
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR
T="$T"; SID="$SID"
$(declare -f xpub xstore)
xstore store-c > "$T/c.sha"
xpub store-c store-c -- store-a
EOF
enable_seams
out="$(AIT_SYNC_SEAM_pre_push="bash $T/hook.sh" run_sync "$T")"
C1="$(cat "$T/c.sha")"
assert_contains "3: the push was retried and completed" "$(first_line "$out")" "PUSHED SYNCED"
assert_eq "3: the retry fetch did not download store-c" "no" "$(has_obj "$Y" "$C1")"
assert_contains "3: store-c excluded before the retry fetch" "^refs/heads/store-c" "$(fetchvals "$Y")"

echo "--- 3b. Push-retry route: a release from another clone settles within the sync ---"
local_task_commit
cat > "$T/hook.sh" <<EOF
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR
T="$T"; SID="$SID"
$(declare -f xpub)
xpub store-c store-c
EOF
out="$(AIT_SYNC_SEAM_pre_push="bash $T/hook.sh" run_sync "$T")"
assert_not_contains "3b: store-a (dropped from retired) released in the same sync" "^refs/heads/store-a" "$(fetchvals "$Y")"
assert_contains "3b: store-c stays excluded" "^refs/heads/store-c" "$(fetchvals "$Y")"

echo "--- 4. Guarded-merge route ---"
world
xstore store-a >/dev/null; xpub store-a store-a -- old-a
run_sync "$T" >/dev/null
assert_contains "4: fixture — old-a excluded" "^refs/heads/old-a" "$(fetchvals "$Y")"
printf 'edit20\n' >> "$Y/.aitask-data/aitasks/t20_beta.md"
B4="$(xstore store-b)"
xpub store-b store-b -- store-a          # drops old-a, retires store-a
plant_lock "$T" 10 "$(lock_yaml_live 10)"
printf 'edit10\n' >> "$Y/.aitask-data/aitasks/t10_alpha.md"
out="$(run_sync "$T")"
assert_eq "4: the verdict is MERGED" "MERGED" "$(first_line "$out")"
assert_eq "4: no store-b objects" "no" "$(has_obj "$Y" "$B4")"
assert_contains "4: store-b excluded" "^refs/heads/store-b" "$(fetchvals "$Y")"
assert_not_contains "4: old-a released within the same sync" "^refs/heads/old-a" "$(fetchvals "$Y")"

echo "--- 5. Fail closed: a config write that cannot happen stops the broad fetch ---"
world
xstore store-a >/dev/null; xpub store-a store-a
run_sync "$T" >/dev/null
B5="$(xstore store-b)"; xpub store-b store-b -- store-a
: > "$Y/.git/config.lock"
out="$(run_sync "$T")"; rc=$?
assert_exit_zero_rc "5: a deferral exits 0" "$rc"
assert_eq "5: deferred" "DEFERRED:fetch_exclusion:apply_failed" "$(first_line "$out")"
assert_eq "5: no store-b ref during the failed attempt" "absent" "$(tref "$Y" refs/remotes/origin/store-b)"
assert_eq "5: no store-b objects during the failed attempt" "no" "$(has_obj "$Y" "$B5")"
assert_contains "5: stderr names the cause" "could not lock config file" "$(sync_err "$T")"
rm -f "$Y/.git/config.lock"
out="$(run_sync "$T")"
assert_eq "5: the next sync converges" "PULLED" "$(first_line "$out")"
assert_eq "5: still no store-b objects" "no" "$(has_obj "$Y" "$B5")"

echo "--- 5b. Fail closed: a data-branch fetch failure ---"
B6="$(xstore store-b)"; xpub store-b store-b -- store-a old-x
enable_seams
# (i) The remote is unreachable: that is the network, and no fetch runs.
out="$(AIT_SYNC_SEAM_pre_exclusion_fetch="git -C '$Y' remote set-url origin 'file://$T/nowhere.git'" run_sync "$T")"
git -C "$Y" remote set-url origin "file://$T/remote.git"
assert_eq "5b(i): an unreachable remote reports the network" "NO_NETWORK" "$(first_line "$out")"
assert_eq "5b(i): no store-b objects" "no" "$(has_obj "$Y" "$B6")"
# (ii) The remote answers, but the data branch cannot be fetched (its tracking
# ref is locked): protection is unknown, so the sync defers.
lockf="$Y/.git/refs/remotes/origin/aitask-data.lock"
out="$(AIT_SYNC_SEAM_pre_exclusion_fetch=": > '$lockf'" run_sync "$T")"
rm -f "$lockf"
assert_eq "5b(ii): deferred" "DEFERRED:fetch_exclusion:data_branch_fetch_failed" "$(first_line "$out")"
assert_eq "5b(ii): no store-b objects" "no" "$(has_obj "$Y" "$B6")"

echo "--- 5c. Fail closed on the push-retry path ---"
run_sync "$T" >/dev/null
local_task_commit
cat > "$T/hook.sh" <<EOF
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR
T="$T"; SID="$SID"
$(declare -f xpub xstore)
xstore store-d > "$T/d.sha"
xpub store-d store-d -- store-b
: > "$Y/.git/config.lock"
EOF
out="$(AIT_SYNC_SEAM_pre_push="bash $T/hook.sh" run_sync "$T")"; rc=$?
D1="$(cat "$T/d.sha")"
rm -f "$Y/.git/config.lock"
assert_exit_zero_rc "5c: a deferral exits 0" "$rc"
assert_contains "5c: deferred on the retry path" "DEFERRED:fetch_exclusion:apply_failed" "$out"
assert_eq "5c: the retry fetch never ran: no store-d objects" "no" "$(has_obj "$Y" "$D1")"

echo "--- 5d. Dedicated drift defers with recovery commands ---"
world
git init -q --bare "$T/st.git"
git -C "$Y" remote add st "file://$T/st.git"
xstore store-a >/dev/null; xpub store-a store-a "remote: st" "remote_dedicated: true"
run_sync "$T" >/dev/null
assert_eq "5d: fixture — st is dedicated" "active" "$(git -C "$Y" config --get remote.st.aitaskDedicatedState)"
git -C "$Y" config --add remote.st.fetch '+refs/heads/hand:refs/remotes/st/hand'
xpub store-a store-a "remote: st"
out="$(run_sync "$T")"
assert_eq "5d: deferred" "DEFERRED:fetch_exclusion:apply_failed" "$(first_line "$out")"
assert_contains "5d: names the recovery commands" "git config --unset-all remote.st.fetch" "$(sync_err "$T")"

echo "--- 6. Dedicated-mode reversal from another clone settles within the sync ---"
world
git init -q --bare "$T/st.git"
git -C "$Y" remote add st "file://$T/st.git"
orig="$(fetchvals "$Y" st)"
xstore store-a >/dev/null; xpub store-a store-a "remote: st" "remote_dedicated: true"
run_sync "$T" >/dev/null
assert_eq "6: fixture — st is dedicated" "true" "$(git -C "$Y" config --get remote.st.skipFetchAll)"
xpub store-a store-a "remote: st"
run_sync "$T" >/dev/null
assert_eq "6: restored within the sync that brought the change" "" "$(git -C "$Y" config --get remote.st.skipFetchAll)"
assert_eq "6: the original mapping is back" "$orig" "$(fetchvals "$Y" st | grep -v '^\^')"
xpub store-a store-a "remote: st" "remote_dedicated: true"
run_sync "$T" >/dev/null
local_task_commit
cat > "$T/hook.sh" <<EOF
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR
T="$T"; SID="$SID"
$(declare -f xpub)
xpub store-a store-a "remote: st"
EOF
enable_seams
AIT_SYNC_SEAM_pre_push="bash $T/hook.sh" run_sync "$T" >/dev/null
assert_eq "6: push-retry route: restored within the sync" "" "$(git -C "$Y" config --get remote.st.skipFetchAll)"

echo "--- 7. Fingerprint: unchanged inputs skip the CLI; a hand-deleted exclusion returns ---"
world
xstore store-a >/dev/null; xpub store-a store-a
run_sync "$T" >/dev/null
mv "$Y/.aitask-scripts/aitask_artifact.sh" "$Y/.aitask-scripts/aitask_artifact.real.sh"
printf '#!/usr/bin/env bash\necho call >> "%s/cli.log"\nexec "$(dirname "$0")/aitask_artifact.real.sh" "$@"\n' "$T" \
    > "$Y/.aitask-scripts/aitask_artifact.sh"
chmod +x "$Y/.aitask-scripts/aitask_artifact.sh"
run_sync "$T" >/dev/null
assert_eq "7: unchanged inputs never invoke the CLI" "0" "$( [[ -f "$T/cli.log" ]] && wc -l < "$T/cli.log" | tr -d ' ' || echo 0)"
git -C "$Y" config --unset-all remote.origin.fetch '^\^refs/heads/store-a$'
run_sync "$T" >/dev/null
assert_contains "7: a hand-deleted exclusion is restored" "^refs/heads/store-a" "$(fetchvals "$Y")"
assert_eq "7: control — a changed input does reach the CLI stub" "yes" \
    "$( [[ -s "$T/cli.log" ]] && echo yes || echo no )"

echo "--- 8. An offline data-branch fetch times out once ---"
world
xstore store-a >/dev/null; xpub store-a store-a
run_sync "$T" >/dev/null
printf '#!/usr/bin/env bash\nsleep 40\n' > "$T/slow.sh"; chmod +x "$T/slow.sh"
git -C "$Y" config remote.origin.uploadpack "$T/slow.sh"
s0=$SECONDS
out="$(run_sync "$T")"
el=$((SECONDS - s0))
git -C "$Y" config --unset remote.origin.uploadpack
assert_eq "8: NO_NETWORK" "NO_NETWORK" "$(first_line "$out")"
assert_eq "8: a single timeout, not two (${el}s)" "yes" "$([[ "$el" -lt 18 ]] && echo yes || echo no)"

echo "--- 9. A remote with no data branch proceeds on local inputs ---"
world
xstore store-a >/dev/null; xpub store-a store-a
run_sync "$T" >/dev/null
git -C "$T/remote.git" update-ref -d refs/heads/aitask-data
out="$(run_sync "$T")"
assert_not_contains "9: no fetch-exclusion deferral" "DEFERRED:fetch_exclusion" "$out"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
