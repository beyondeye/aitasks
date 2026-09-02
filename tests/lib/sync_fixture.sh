#!/usr/bin/env bash
# sync_fixture.sh - shared fixture for the aitask_sync.sh sweep tests (t1599_3).
#
# Source AFTER tests/lib/asserts.sh. Requires PROJECT_DIR to be set.
#
# Builds a bare remote + a BRANCH-MODE clone (real .aitask-data worktree,
# aitasks/ + aiplans/ symlinks), an initialized aitask-locks branch, and a
# bin/hostname shim. The closest pre-existing fixture
# (test_sync_branch_mode_automerge.sh) lacks the last two: plant_lock's
# `git rev-parse origin/aitask-locks` is unguarded and would build a broken
# commit-tree without the branch, and cross-host routing cannot be driven in
# both directions without the shim.

# --- Fixture --------------------------------------------------------------
# Bare remote + BRANCH-MODE local clone (real .aitask-data worktree, aitasks/
# and aiplans/ symlinks), an initialized aitask-locks branch, and a
# bin/hostname shim so cross-host routing can be driven in both directions.
#
# Two gaps in the closest existing fixture (test_sync_branch_mode_automerge.sh)
# are closed here: it never creates the lock branch (plant_lock's
# `git rev-parse origin/aitask-locks` is unguarded and would produce a broken
# commit-tree), and it has no hostname shim.
# One per-run base directory, created HERE in the sourcing shell. setup_repo is
# always called as `TMP="$(setup_repo)"`, i.e. inside a command substitution, so
# anything it appends to a list would be lost with that subshell — every fixture
# therefore nests under this base and one trap removes the lot. Each repo carries
# a full copy of .aitask-scripts, so a leaking suite is measured in gigabytes.
_SYNC_FIXTURE_BASE="$(mktemp -d)"
_sync_fixture_cleanup() { [[ -n "${_SYNC_FIXTURE_BASE:-}" ]] && rm -rf "$_SYNC_FIXTURE_BASE"; }
trap _sync_fixture_cleanup EXIT

setup_repo() {
    local tmpdir
    tmpdir="$(mktemp -d -p "$_SYNC_FIXTURE_BASE")"

    git init -q --bare "$tmpdir/remote.git"
    git clone -q "$tmpdir/remote.git" "$tmpdir/local" 2>/dev/null
    (
        cd "$tmpdir/local"
        git config user.email test@test.com
        git config user.name Test
        git config commit.gpgsign false
        echo "# project" > README.md
        git add -A
        git commit -q -m "init"
        git branch -M main
        git push -q -u origin main 2>/dev/null

        # Orphan aitask-data branch + worktree (mirrors `ait setup`'s layout).
        local empty_tree branch_commit
        empty_tree=$(git mktree < /dev/null)
        branch_commit=$(echo "ait: Initialize aitask-data branch" | git commit-tree "$empty_tree")
        git update-ref refs/heads/aitask-data "$branch_commit"
        git worktree add -q .aitask-data aitask-data
        mkdir -p .aitask-data/aitasks/metadata .aitask-data/aiplans
        ln -s .aitask-data/aitasks aitasks
        ln -s .aitask-data/aiplans aiplans
        git -C .aitask-data config user.email test@test.com
        git -C .aitask-data config user.name Test
        git -C .aitask-data config commit.gpgsign false

        printf -- '---\nstatus: Ready\n---\nA\n' > .aitask-data/aitasks/t10_alpha.md
        printf -- '---\nstatus: Ready\n---\nB\n' > .aitask-data/aitasks/t20_beta.md
        printf -- '---\nstatus: Ready\n---\nC\n' > .aitask-data/aitasks/t30_gamma.md
        printf 'cfg\n' > .aitask-data/aitasks/metadata/stats_config.json
        git -C .aitask-data add -A
        git -C .aitask-data commit -q -m "data init"
        git -C .aitask-data push -q -u origin aitask-data 2>/dev/null

        # hostname shim: get_hostname() in aitask_lock.sh, and the sweep's own
        # cross-host guard, both call `hostname`.
        mkdir -p bin
        cat > bin/hostname <<'HOSTEOF'
#!/usr/bin/env bash
echo "${TEST_HOSTNAME:-testhost}"
HOSTEOF
        chmod +x bin/hostname

        cp "$PROJECT_DIR/ait" ./ait
        chmod +x ./ait
        cp -r "$PROJECT_DIR/.aitask-scripts" ./.aitask-scripts
        git add -A 2>/dev/null; git commit -q -m "framework" 2>/dev/null; git push -q 2>/dev/null

        # The lock branch must exist before plant_lock can extend it.
        PATH="$PWD/bin:$PATH" TEST_HOSTNAME=testhost \
            ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1
    ) >/dev/null 2>&1

    echo "$tmpdir"
}

# plant_lock <tmpdir> <task_id> <yaml> — write a lock blob straight onto
# origin/aitask-locks (mirrors aitask_lock.sh's own plumbing).
plant_lock() {
    local tmpdir="$1" task_id="$2" yaml="$3"
    (
        cd "$tmpdir/local"
        git fetch origin aitask-locks --quiet 2>/dev/null
        local parent_hash current_tree_hash blob_hash new_tree_hash commit_hash
        parent_hash=$(git rev-parse origin/aitask-locks)
        current_tree_hash=$(git rev-parse "origin/aitask-locks^{tree}")
        blob_hash=$(echo "$yaml" | git hash-object -w --stdin)
        new_tree_hash=$( {
            git ls-tree "$current_tree_hash" | grep -v "	t${task_id}_lock\.yaml$" || true
            printf "100644 blob %s\tt%s_lock.yaml\n" "$blob_hash" "$task_id"
        } | git mktree )
        commit_hash=$(echo "test: plant lock for t$task_id" | \
            git commit-tree "$new_tree_hash" -p "$parent_hash")
        git push --quiet origin "$commit_hash:refs/heads/aitask-locks" 2>/dev/null
    )
}

# A lock YAML anchored to a LIVE process on this host (this test's own shell).
lock_yaml_live() {
    local tid="$1" host="${2:-testhost}" pid="${3:-$$}"
    local start kind
    start="$(awk '{print $22}' "/proc/$pid/stat" 2>/dev/null)"
    kind=proc
    if [[ -z "$start" ]]; then start="-"; kind=ps; fi
    printf 'task_id: %s\nlocked_by: other@x.com\nlocked_at: 2026-01-01 00:00\nhostname: %s\npid: %s\npid_starttime: %s\npid_starttime_kind: %s' \
        "$tid" "$host" "$pid" "$start" "$kind"
}

# A lock YAML whose PID is provably gone (starttime cannot match).
lock_yaml_dead() {
    local tid="$1" host="${2:-testhost}"
    printf 'task_id: %s\nlocked_by: other@x.com\nlocked_at: 2026-01-01 00:00\nhostname: %s\npid: 999999\npid_starttime: 12345\npid_starttime_kind: proc' \
        "$tid" "$host"
}

# A pre-PID-anchor lock: no usable pid, so liveness is `unknown`.
lock_yaml_unknown_pid() {
    local tid="$1" host="${2:-testhost}"
    printf 'task_id: %s\nlocked_by: other@x.com\nlocked_at: 2026-01-01 00:00\nhostname: %s\npid: -\npid_starttime: -\npid_starttime_kind: proc' \
        "$tid" "$host"
}

# Run the sweep in <tmpdir>'s clone. Echoes stdout; stderr lands in a
# deterministic file, because callers capture stdout with $( ) and an assignment
# made inside that subshell would never reach this scope.
run_sync() {
    local tmpdir="$1"; shift
    (
        cd "$tmpdir/local"
        export PATH="$PWD/bin:$PATH"
        export TEST_HOSTNAME="${TEST_HOSTNAME:-testhost}"
        export AITASKS_LOCK_DIR="$tmpdir/locks"
        ./.aitask-scripts/aitask_sync.sh --batch "$@" 2>"$tmpdir/sync_stderr"
    )
}
sync_err() { cat "$1/sync_stderr" 2>/dev/null; }

# Data-branch HEAD, so an assertion can be scoped to the commits ONE run made
# rather than to the fixture's own setup commits.
data_head() { git -C "$1/local/.aitask-data" rev-parse HEAD 2>/dev/null; }
files_since() {
    git -C "$1/local/.aitask-data" log --name-only --no-renames --format= "$2..HEAD" 2>/dev/null
}

# Commit subjects on the data branch, newest first.
data_log() { git -C "$1/local/.aitask-data" log --format=%s -20 2>/dev/null; }
# Files touched by the newest commit that mentions <pattern>.
commit_files_for() {
    local tmpdir="$1" pattern="$2" sha
    sha=$(git -C "$tmpdir/local/.aitask-data" log --format='%H %s' -20 2>/dev/null \
          | grep -m1 -- "$pattern" | cut -d' ' -f1)
    [[ -n "$sha" ]] || return 0
    git -C "$tmpdir/local/.aitask-data" show --name-only --format= "$sha" 2>/dev/null
}
data_commit_count() { git -C "$1/local/.aitask-data" rev-list --count HEAD 2>/dev/null; }

