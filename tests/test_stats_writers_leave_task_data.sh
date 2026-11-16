#!/usr/bin/env bash
# test_stats_writers_leave_task_data.sh - the counter writers never touch the
# shared task-data worktree (t1912_4 acceptance).
#
# Run: bash tests/test_stats_writers_leave_task_data.sh
#
# THE CLAIM. aitask_usage_update.sh / aitask_verified_update.sh record into the
# aitask-stats plumbing branch. A run must leave `.aitask-data` exactly as it
# found it, even in the state that used to open a rebase window: the worktree
# dirty (a modified tracked file plus an untracked file) and origin's aitask-data
# ahead. Five facts are compared byte for byte before and after both writers:
# the data worktree's HEAD, its index (hash of `git ls-files -s`), its
# `status --porcelain`, the clone's refs/remotes/origin/aitask-data, and origin's
# own aitask-data tip.
#
# A `git` wrapper first on PATH logs every git argv the writers and the store
# CLI run (PWD + argv). The log must hold no merge / rebase / pull at all, no
# fetch / push / ls-remote that names aitask-data, and no mutating git command
# run against the data worktree. A positive control requires a push of
# aitask-stats in the same log, so the remote path really ran (an empty or
# no-remote log cannot pass vacuously).
#
# The real branch-mode layout comes from tests/lib/sync_fixture.sh (bare remote,
# clone with a .aitask-data worktree of the same repository, full framework copy).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

PASS=0
FAIL=0
TOTAL=0

. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/sync_fixture.sh"
. "$PROJECT_DIR/tests/lib/git_config_isolation.sh"

set +e

REAL_GIT="$(command -v git)"
MODELS=aitasks/metadata/models_claudecode.json

# snapshot <tmpdir> <outdir> — the five facts, one file each, read with the
# real git (never through the logging wrapper).
SNAP_FACTS=(head index status tracking origin)
snapshot() {
    local t="$1" o="$2" d="$1/local/.aitask-data"
    mkdir -p "$o"
    "$REAL_GIT" -C "$d" rev-parse HEAD > "$o/head"
    "$REAL_GIT" -C "$d" ls-files -s | sha256sum | cut -d' ' -f1 > "$o/index"
    "$REAL_GIT" -C "$d" status --porcelain --untracked-files=all > "$o/status"
    "$REAL_GIT" -C "$t/local" rev-parse -q --verify refs/remotes/origin/aitask-data > "$o/tracking"
    "$REAL_GIT" -C "$t/remote.git" rev-parse refs/heads/aitask-data > "$o/origin"
}

# install_git_wrapper <dir> <log> — a `git` that appends PWD<TAB>arg<TAB>arg…
install_git_wrapper() {
    local dir="$1" log="$2"
    mkdir -p "$dir"
    cat > "$dir/git" <<EOF
#!/usr/bin/env bash
{ printf '%s' "\$PWD"; printf '\t%s' "\$@"; printf '\n'; } >> "$log"
exec "$REAL_GIT" "\$@"
EOF
    chmod +x "$dir/git"
}

# Every logged command that "involves aitask-data", printed one per line:
#   - any merge / rebase / pull, wherever it runs;
#   - a fetch / push / ls-remote naming aitask-data;
#   - a mutating subcommand whose cwd or -C target is the data worktree.
forbidden_git() {
    awk -F'\t' '
        function involves_data(   i) {
            if (index($1, ".aitask-data")) return 1
            for (i = 2; i <= NF; i++) if (index($i, ".aitask-data")) return 1
            return 0
        }
        {
            sub_ = ""; mentions = 0
            for (i = 2; i <= NF; i++) {
                if (sub_ == "" && $i !~ /^-/ && $(i - 1) != "-C" && $(i - 1) != "-c") sub_ = $i
                if (index($i, "aitask-data")) mentions = 1
            }
            if (sub_ ~ /^(merge|rebase|pull)$/) { print; next }
            if (sub_ ~ /^(fetch|push|ls-remote)$/ && (mentions || index($1, "aitask-data"))) { print; next }
            if (sub_ ~ /^(add|commit|reset|checkout|switch|stash|rm|mv|restore|update-index|update-ref|worktree|cherry-pick|revert|am|apply)$/ && involves_data()) { print; next }
        }' "$1"
}

seed_state() {
    local t="$1" d="$1/local/.aitask-data"
    cat > "$d/$MODELS" <<'EOF'
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
    "$REAL_GIT" -C "$d" add "$MODELS"
    "$REAL_GIT" -C "$d" commit -q -m "seed models"
    "$REAL_GIT" -C "$d" push -q 2>/dev/null

    # origin's aitask-data moves ahead of the local data branch.
    "$REAL_GIT" clone -q --branch aitask-data "$t/remote.git" "$t/other" 2>/dev/null
    "$REAL_GIT" -C "$t/other" -c user.email=o@test.com -c user.name=O \
        commit -q --allow-empty -m "elsewhere"
    "$REAL_GIT" -C "$t/other" push -q origin aitask-data 2>/dev/null

    # The data worktree is dirty: a modified tracked file and an untracked one.
    printf 'local edit\n' >> "$d/aitasks/t10_alpha.md"
    printf 'scratch\n' > "$d/aitasks/untracked_note.md"
}

# run_writer <tmpdir> <script> <args...> — stdout echoed, exit status in
# <tmpdir>/rc, stderr in <tmpdir>/err.
# RUN_CWD (default <tmpdir>/local) is where the writer is launched from.
run_writer() {
    local t="$1" script="$2"; shift 2
    local rc=0
    (
        cd "${RUN_CWD:-$t/local}" || exit 1
        sync_isolate_git_config
        PATH="$t/gitwrap:$t/local/bin:$PATH" TEST_HOSTNAME=testhost \
            "$t/local/.aitask-scripts/$script" "$@" 2>>"$t/err"
    ) || rc=$?
    echo "$rc" > "$t/rc"
}

echo "=== the stats writers leave the task-data worktree untouched (t1912_4) ==="

T="$(setup_repo)"
seed_state "$T"
LOG="$T/git.log"
: > "$LOG"
install_git_wrapper "$T/gitwrap" "$LOG"

assert_eq "fixture: origin's aitask-data is ahead of the local data branch" "1" \
    "$("$REAL_GIT" -C "$T/remote.git" rev-list --count \
        "$("$REAL_GIT" -C "$T/local/.aitask-data" rev-parse HEAD)..refs/heads/aitask-data")"
assert_eq "fixture: the data worktree is dirty (modified + untracked)" "2" \
    "$("$REAL_GIT" -C "$T/local/.aitask-data" status --porcelain --untracked-files=all | wc -l | tr -d ' ')"

snapshot "$T" "$T/before"

out_usage="$(run_writer "$T" aitask_usage_update.sh \
    --agent-string claudecode/opus4_6 --skill pick --silent)"
rc_usage="$(cat "$T/rc")"
out_verified="$(run_writer "$T" aitask_verified_update.sh \
    --agent-string claudecode/opus4_6 --skill pick --score 4 --silent)"
rc_verified="$(cat "$T/rc")"
# Launched from INSIDE the data worktree (aitasks/ is a symlink into
# .aitask-data): the writer must anchor to the repo root before anything runs,
# and still leave the worktree alone (t1658_2's non-root cwd, sharpest case).
out_inside="$(RUN_CWD="$T/local/aitasks/metadata" run_writer "$T" aitask_usage_update.sh \
    --agent-string claudecode/opus4_6 --skill pick --silent)"
rc_inside="$(cat "$T/rc")"

snapshot "$T" "$T/after"

assert_eq "usage writer: UPDATED, exit 0" "UPDATED:claudecode/opus4_6:pick:1|0" \
    "$out_usage|$rc_usage"
assert_eq "verified writer: UPDATED, exit 0" "UPDATED:claudecode/opus4_6:pick:80|0" \
    "$out_verified|$rc_verified"
assert_eq "usage writer launched inside the data worktree: UPDATED, exit 0" \
    "UPDATED:claudecode/opus4_6:pick:2|0" "$out_inside|$rc_inside"

for fact in "${SNAP_FACTS[@]}"; do
    assert_eq "fact recorded before the run: $fact" "yes" \
        "$([[ -s "$T/before/$fact" || "$fact" == status ]] && echo yes || echo no)"
    assert_eq "unchanged by all three runs: $fact" "$(cat "$T/before/$fact")" "$(cat "$T/after/$fact")"
done
assert_eq "status snapshot is the dirty state (2 entries)" "2" "$(wc -l < "$T/before/status" | tr -d ' ')"

forbidden="$(forbidden_git "$LOG")"
assert_eq "no git command involved aitask-data" "" "$forbidden"
[[ -z "$forbidden" ]] || printf '  offending: %s\n' "$forbidden"

assert_contains "positive control: the store pushed aitask-stats to origin" \
    "aitask-stats" "$(awk -F'\t' '{ for (i = 2; i <= NF; i++) if ($i == "push") { print; next } }' "$LOG")"
assert_eq "origin now carries refs/heads/aitask-stats" "yes" \
    "$("$REAL_GIT" -C "$T/remote.git" rev-parse -q --verify refs/heads/aitask-stats >/dev/null && echo yes || echo no)"

show="$(cd "$T/local" && sync_isolate_git_config && python3 "$T/local/.aitask-scripts/aitask_model_stats.py" show --root "$T/local")"
assert_contains "store: both usage runs recorded" "claudecode/opus4_6 usagestats pick all_time=2" "$show"
assert_contains "store: rating recorded" "claudecode/opus4_6 verifiedstats pick all_time=1 avg=80" "$show"
assert_eq "registry file untouched (no counters, no verified write)" \
    '{"pick":80}|null|null' \
    "$(jq -c '.models[0] | "\(.verified|tojson)|\(.usagestats|tojson)|\(.verifiedstats|tojson)"' -r \
        "$T/local/.aitask-data/$MODELS")"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
