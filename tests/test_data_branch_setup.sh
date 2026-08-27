#!/usr/bin/env bash
# test_data_branch_setup.sh - Automated tests for setup_data_branch and update_claudemd_git_section
# Run: bash tests/test_data_branch_setup.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

# Shared assertion helpers (see tests/lib/asserts.sh)
. "$PROJECT_DIR/tests/lib/asserts.sh"




assert_symlink() {
    local desc="$1" path="$2"
    TOTAL=$((TOTAL + 1))
    if [[ -L "$path" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc ('$path' is not a symlink)"
    fi
}

assert_not_symlink() {
    local desc="$1" path="$2"
    TOTAL=$((TOTAL + 1))
    if [[ ! -L "$path" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc ('$path' should not be a symlink)"
    fi
}

assert_file_contains() {
    local desc="$1" file="$2" pattern="$3"
    TOTAL=$((TOTAL + 1))
    if [[ -f "$file" ]] && grep -qF -- "$pattern" "$file"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (file '$file' does not contain '$pattern')"
    fi
}

# Set up the seed file in a temp directory (simulates post-setup state)
setup_seed_file() {
    local dir="$1"
    mkdir -p "$dir/aitasks/metadata"
    mkdir -p "$dir/seed"
    cp "$PROJECT_DIR/seed/aitasks_agent_instructions.seed.md" "$dir/aitasks/metadata/"
    cp "$PROJECT_DIR/seed/project_config.yaml" "$dir/seed/"
}

# Create a repo with remote for testing
# Drive the real setup_code_agents against <project_dir> (t1612). Only
# _is_agent_installed is stubbed, and only for determinism: it is
# `command -v codex/opencode`, a property of the developer's machine.
# setup_claude_code and prune_retired_skills self-no-op in these fixtures (no
# aitasks/metadata/claude_settings.seed.json, no prune helper in SCRIPT_DIR), so
# update_agentsmd and update_claudemd_git_section run for real.
# stdout is returned unmerged and the real exit status is preserved. Callers that
# assert on the output use  out=""; rc=0; out="$(run_setup_code_agents "$d")" || rc=$?
# others discard it:            rc=0; run_setup_code_agents "$d" >/dev/null || rc=$?
# Assertions stay OUTSIDE the subshell: PASS/FAIL/TOTAL are in-process counters.
run_setup_code_agents() {
    local project_dir="$1"
    (
        SCRIPT_DIR="$project_dir/.aitask-scripts"
        mkdir -p "$SCRIPT_DIR"
        # Overrides the sourced aitask_setup.sh definition that setup_code_agents
        # calls; shellcheck cannot see that indirect invocation.
        # shellcheck disable=SC2329
        _is_agent_installed() { return 1; }
        setup_code_agents </dev/null
    )
}

setup_repo_with_remote() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    # Create bare remote
    git init --bare --quiet "$tmpdir/remote.git"
    # Create local clone
    git clone --quiet "$tmpdir/remote.git" "$tmpdir/local" 2>/dev/null
    (
        cd "$tmpdir/local" || exit 1
        git config user.email "test@test.com"
        git config user.name "Test"
        # Need at least one commit for the repo to be usable
        echo "# Test Project" > README.md
        git add README.md
        git commit -m "init" --quiet
        git push --quiet 2>/dev/null
    )
    echo "$tmpdir"
}

# Create a local-only repo (no remote)
setup_local_repo() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    (
        cd "$tmpdir" || exit 1
        git init --quiet
        git config user.email "test@test.com"
        git config user.name "Test"
        echo "# Test Project" > README.md
        git add README.md
        git commit -m "init" --quiet
    )
    echo "$tmpdir"
}

# --- Command shims (t1631) ---
#
# Several t1631 tests need one specific `git` or `cp` invocation inside
# setup_data_branch to fail while every other call behaves normally. A wrapper
# on PATH is the only mechanism that is deterministic for EVERY EUID: `chmod
# 000` on a source file does nothing when the suite runs as root, which is a
# common CI/container identity, and that is precisely where the no-delete
# guarantee most needs pinning.
#
# shim_install <name>:<matcher> [<name>:<matcher> ...]
#   <matcher> names a case in the generated wrapper (see below). Every wrapper
#   passes through to the real binary — resolved via AIT_TEST_REAL_PATH, saved
#   before PATH is modified — for anything it does not match, so a shimmed
#   `git` still runs `worktree add`, `rm`, `add`, `push` and the rest for real.
SHIM_DIR=""
AIT_TEST_REAL_PATH=""

shim_install() {
    local spec name matcher
    SHIM_DIR="$(mktemp -d)"
    AIT_TEST_REAL_PATH="$PATH"
    export AIT_TEST_REAL_PATH

    for spec in "$@"; do
        name="${spec%%:*}"
        matcher="${spec#*:}"
        {
            echo '#!/usr/bin/env bash'
            echo "real=\"\$(PATH=\"\$AIT_TEST_REAL_PATH\" command -v $name)\""
            case "$matcher" in
                git_fetch)
                    # `git -C <dir> fetch origin aitask-data` -> fail.
                    cat <<'SHIM'
for a in "$@"; do
    if [[ "$a" == "fetch" ]]; then
        echo "fatal: shim: simulated fetch failure" >&2
        exit 1
    fi
done
SHIM
                    ;;
                git_commit)
                    # `git commit` inside the data worktree -> fail. Scoped by
                    # CWD so the main-branch commits still work.
                    cat <<'SHIM'
for a in "$@"; do
    if [[ "$a" == "commit" && "$PWD" == */.aitask-data ]]; then
        echo "fatal: shim: simulated commit failure" >&2
        exit 1
    fi
done
SHIM
                    ;;
                git_worktree_list_fail)
                    # `git worktree list --porcelain` -> fail. Everything else,
                    # including `worktree add` and `worktree remove`, passes
                    # through, so this subverts ONLY the identity guard.
                    cat <<'SHIM'
_wt=0; _list=0
for a in "$@"; do
    [[ "$a" == "worktree" ]] && _wt=1
    [[ "$_wt" == 1 && "$a" == "list" ]] && _list=1
done
if [[ "$_wt" == 1 && "$_list" == 1 ]]; then
    echo "fatal: shim: simulated worktree list failure" >&2
    exit 1
fi
SHIM
                    ;;
                git_worktree_list_omit)
                    # `git worktree list --porcelain` -> real output with the
                    # .aitask-data block filtered out. Exit status 0, so this
                    # pins "parsed, no match" as distinct from "command failed".
                    cat <<'SHIM'
_wt=0; _list=0
for a in "$@"; do
    [[ "$a" == "worktree" ]] && _wt=1
    [[ "$_wt" == 1 && "$a" == "list" ]] && _list=1
done
if [[ "$_wt" == 1 && "$_list" == 1 ]]; then
    "$real" "$@" | awk '
        /^worktree /  { skip = ($0 ~ /\.aitask-data$/) }
        /^$/          { skip = 0 }
        !skip         { print }
    '
    exit 0
fi
SHIM
                    ;;
                cp_ok_then_drop_worktree)
                    # Copy aiplans for real, then make the whole data worktree
                    # vanish, and report success. This is the only fixture that
                    # reaches Step 4 with a missing .aitask-data, which is what
                    # exercises that subshell's `cd ... || exit 1` guard.
                    cat <<'SHIM'
_dst="${!#}"
if [[ "$_dst" == */.aitask-data/aiplans/* || "$_dst" == */.aitask-data/aiplans/ ]]; then
    "$real" "$@" 2>/dev/null
    _wt="${_dst%%/.aitask-data/*}/.aitask-data"
    PATH="$AIT_TEST_REAL_PATH" rm -rf "$_wt"
    exit 0
fi
SHIM
                    ;;
                cp_partial_ok_aitasks)
                    # A partial copy that reports SUCCESS. cp's own exit status
                    # cannot catch this one, so it is the only fixture that
                    # reaches — and therefore pins — the Step-5 pre-delete
                    # verification.
                    cat <<'SHIM'
_dst="${!#}"
if [[ "$_dst" == */.aitask-data/aitasks/* || "$_dst" == */.aitask-data/aitasks/ ]]; then
    _src="${@:$(($#-1)):1}"
    _one="$(PATH="$AIT_TEST_REAL_PATH" find "${_src%/.}" -maxdepth 1 -type f | head -n1)"
    [[ -n "$_one" ]] && "$real" "$_one" "$_dst" 2>/dev/null
    exit 0
fi
SHIM
                    ;;
                cp_into_aitasks|cp_into_aiplans)
                    # `cp -a <src>/. <dst>/` where <dst> is the named directory
                    # in the data worktree -> copy ONE file, then fail. The
                    # partial tree is the point: a complete copy and a part-way
                    # one must be distinguishable at the moment Step 5 deletes
                    # the source. Scoped to ONE destination so a test pins the
                    # call site it names — the aitasks and aiplans copies are
                    # separate statements and each needs its own check.
                    printf '_target="%s"\n' "${matcher#cp_into_}"
                    cat <<'SHIM'
_dst="${!#}"
if [[ "$_dst" == */.aitask-data/"$_target"/* || "$_dst" == */.aitask-data/"$_target"/ ]]; then
    _src="${@:$(($#-1)):1}"
    _one="$(PATH="$AIT_TEST_REAL_PATH" find "${_src%/.}" -maxdepth 1 -type f | head -n1)"
    [[ -n "$_one" ]] && "$real" "$_one" "$_dst" 2>/dev/null
    echo "cp: shim: simulated copy failure" >&2
    exit 1
fi
SHIM
                    ;;
                *)
                    echo "shim_install: unknown matcher '$matcher'" >&2
                    return 1
                    ;;
            esac
            echo 'exec "$real" "$@"'
        } > "$SHIM_DIR/$name"
        chmod +x "$SHIM_DIR/$name"
    done

    PATH="$SHIM_DIR:$PATH"
    export PATH
    hash -r
}

shim_remove() {
    [[ -n "$SHIM_DIR" ]] || return 0
    PATH="${PATH#"$SHIM_DIR":}"
    export PATH
    hash -r
    rm -rf "$SHIM_DIR"
    SHIM_DIR=""
}

# Push a real aitask-data branch to a fixture's remote.
seed_remote_data_branch() {
    local repo="$1"
    (
        cd "$repo" || exit 1
        git push --quiet origin "HEAD:refs/heads/aitask-data" 2>/dev/null
    )
}

# Source the setup script to get access to functions
source "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" --source-only
set +euo pipefail

echo "=== setup_data_branch + update_claudemd_git_section Tests ==="
echo ""

# --- Test 1: Fresh setup with remote ---
echo "--- Test 1: Fresh setup with remote ---"

TMPDIR_1="$(setup_repo_with_remote)"
SCRIPT_DIR="$TMPDIR_1/local/.aitask-scripts"
mkdir -p "$SCRIPT_DIR"
mkdir -p "$TMPDIR_1/local/seed"
cp "$PROJECT_DIR/seed/aitasks_agent_instructions.seed.md" "$TMPDIR_1/local/seed/"
cp "$PROJECT_DIR/seed/project_config.yaml" "$TMPDIR_1/local/seed/"
cp "$PROJECT_DIR/.aitask-scripts/gates_reference.yaml" "$SCRIPT_DIR/"

(cd "$TMPDIR_1/local" && setup_data_branch </dev/null >/dev/null 2>&1)

# Check branch exists on remote
branch_on_remote=$(git -C "$TMPDIR_1/local" ls-remote --heads origin aitask-data 2>/dev/null | grep -c "aitask-data")
assert_eq_trim "aitask-data branch on remote" "1" "$branch_on_remote"

# Check worktree exists
assert_dir_exists "Worktree directory exists" "$TMPDIR_1/local/.aitask-data"
TOTAL=$((TOTAL + 1))
if [[ -f "$TMPDIR_1/local/.aitask-data/.git" || -d "$TMPDIR_1/local/.aitask-data/.git" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Worktree .git marker not found"
fi

# Check symlinks
assert_symlink "aitasks is symlink" "$TMPDIR_1/local/aitasks"
assert_symlink "aiplans is symlink" "$TMPDIR_1/local/aiplans"

# Check .gitignore — symlink-safe (bare) form, not trailing-slash.
# Trailing-slash patterns match directories only and would skip the
# aitasks/aiplans symlinks setup_data_branch just created (t699).
TOTAL=$((TOTAL + 1))
if grep -qxF "aitasks" "$TMPDIR_1/local/.gitignore" 2>/dev/null; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: .gitignore should contain bare 'aitasks' line"
fi
TOTAL=$((TOTAL + 1))
if grep -qxF "aiplans" "$TMPDIR_1/local/.gitignore" 2>/dev/null; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: .gitignore should contain bare 'aiplans' line"
fi
assert_file_contains ".gitignore has .aitask-data/" "$TMPDIR_1/local/.gitignore" ".aitask-data/"

# Rendered-skill-closure ignore block (t939): consumers must receive the
# broad `*-/` patterns plus the headless-prerender negations so on-demand
# rendered closures stay out of `git status` while committed prerenders stay
# tracked. Mirrors this repo's own .gitignore, minus .gemini.
assert_file_contains ".gitignore ignores claude rendered closures" \
    "$TMPDIR_1/local/.gitignore" ".claude/skills/*-/"
assert_file_contains ".gitignore ignores agents rendered closures" \
    "$TMPDIR_1/local/.gitignore" ".agents/skills/*-/"
assert_file_contains ".gitignore ignores opencode rendered closures" \
    "$TMPDIR_1/local/.gitignore" ".opencode/skills/*-/"
assert_file_contains ".gitignore re-includes committed prerender" \
    "$TMPDIR_1/local/.gitignore" "!.claude/skills/task-workflow-remote-/"
# No .gemini lines — .gemini is no longer a required agent root (t939).
TOTAL=$((TOTAL + 1))
if grep -q "\.gemini/skills" "$TMPDIR_1/local/.gitignore" 2>/dev/null; then
    FAIL=$((FAIL + 1))
    echo "FAIL: .gitignore should not contain any .gemini/skills lines"
else
    PASS=$((PASS + 1))
fi

# Regression: aitasks/aiplans symlinks must be ignored. Trailing-slash
# gitignore patterns match directories only and would leave the symlinks
# as untracked entries (t699). Filter porcelain to just those two paths
# so unrelated test-fixture untracked files (e.g. seed/) do not confound.
symlink_porcelain="$(git -C "$TMPDIR_1/local" status --porcelain | grep -E '^\?\? (aitasks|aiplans)$' || true)"
assert_eq_trim "aitasks/aiplans symlinks ignored after setup_data_branch" "" "$symlink_porcelain"

# Check skeleton directories
assert_dir_exists "aitasks/metadata skeleton" "$TMPDIR_1/local/.aitask-data/aitasks/metadata"
assert_dir_exists "aitasks/archived skeleton" "$TMPDIR_1/local/.aitask-data/aitasks/archived"
assert_dir_exists "aiplans/archived skeleton" "$TMPDIR_1/local/.aitask-data/aiplans/archived"
assert_file_exists "project_config.yaml copied" "$TMPDIR_1/local/.aitask-data/aitasks/metadata/project_config.yaml"
assert_file_contains "project_config has coauthor domain" \
    "$TMPDIR_1/local/.aitask-data/aitasks/metadata/project_config.yaml" \
    "codeagent_coauthor_domain: aitasks.io"

# Gate registry seeded from the canonical .aitask-scripts/ reference (t1147) —
# with verifier keys, so a fresh install never defers on "no verifier configured".
assert_file_exists "gates.yaml copied from gates_reference" \
    "$TMPDIR_1/local/.aitask-data/aitasks/metadata/gates.yaml"
assert_file_contains "gates.yaml carries risk_evaluated verifier" \
    "$TMPDIR_1/local/.aitask-data/aitasks/metadata/gates.yaml" \
    "verifier: aitask-gate-risk"

# Check data branch .gitignore has aitasks/new/
assert_file_contains "Data .gitignore has aitasks/new/" "$TMPDIR_1/local/.aitask-data/.gitignore" "aitasks/new/"

# CLAUDE.md is NOT setup_data_branch's job any more (t1612). This is the only
# fixture in this file that ever reached the old Step 8, so it is the
# discriminating production-reachable case for the move -- flipped rather than
# deleted. The absence assertion alone would be vacuous (nothing else here writes
# CLAUDE.md), so the positive control below runs on the SAME fixture: together
# they prove the responsibility MOVED rather than vanished.
assert_file_not_exists "setup_data_branch does not write CLAUDE.md (t1612)" "$TMPDIR_1/local/CLAUDE.md"

# Positive control: the new owner writes it.
rc=0
run_setup_code_agents "$TMPDIR_1/local" >/dev/null || rc=$?
assert_eq_trim "setup_code_agents exited 0" "0" "$rc"
assert_file_contains "CLAUDE.md has git operations section" "$TMPDIR_1/local/CLAUDE.md" "## Git Operations on Task/Plan Files"
assert_file_contains "CLAUDE.md mentions ait git" "$TMPDIR_1/local/CLAUDE.md" "./ait git"
marker_starts_1=$(grep -c '^>>>aitasks$' "$TMPDIR_1/local/CLAUDE.md" || true)
assert_eq_trim "CLAUDE.md has exactly one start marker" "1" "${marker_starts_1:-0}"

# The re-run case t1612 exists for, on a GENUINELY already-configured project:
# .aitask-data/.git now exists, so setup_data_branch early-returns -- and the
# marker-managed block must still be refreshed by setup_code_agents.
sed -i.bak 's/^## Git Operations on Task\/Plan Files$/STALE BLOCK t1612/' "$TMPDIR_1/local/CLAUDE.md"
rm -f "$TMPDIR_1/local/CLAUDE.md.bak"
rerun_out=$(cd "$TMPDIR_1/local" && setup_data_branch </dev/null 2>&1)
assert_contains_ci "Re-run: setup_data_branch says already configured" "already configured" "$rerun_out"
assert_file_contains "Re-run: setup_data_branch left the stale block alone" "$TMPDIR_1/local/CLAUDE.md" "STALE BLOCK t1612"
rc=0
run_setup_code_agents "$TMPDIR_1/local" >/dev/null || rc=$?
assert_eq_trim "Re-run: setup_code_agents exited 0" "0" "$rc"
claudemd_rerun="$(cat "$TMPDIR_1/local/CLAUDE.md")"
assert_not_contains "Re-run: stale block refreshed away" "STALE BLOCK t1612" "$claudemd_rerun"
assert_file_contains "Re-run: regenerated content present" "$TMPDIR_1/local/CLAUDE.md" "## Git Operations on Task/Plan Files"
marker_starts_1b=$(grep -c '^>>>aitasks$' "$TMPDIR_1/local/CLAUDE.md" || true)
assert_eq_trim "Re-run: still exactly one start marker" "1" "${marker_starts_1b:-0}"

rm -rf "$TMPDIR_1"

# --- Test 1b: Seedless fresh setup still seeds the gate registry (t1147) ---
# Installed projects have no seed/ directory (it is deleted after install), but
# they DO have .aitask-scripts/. The gate-registry copy must run independent of
# the `[[ -d seed ]]` metadata block, or seedless fresh inits ship no registry.
echo ""
echo "--- Test 1b: Seedless fresh setup seeds gate registry from reference ---"

TMPDIR_1B="$(setup_repo_with_remote)"
SCRIPT_DIR="$TMPDIR_1B/local/.aitask-scripts"
mkdir -p "$SCRIPT_DIR"
cp "$PROJECT_DIR/.aitask-scripts/gates_reference.yaml" "$SCRIPT_DIR/"
# Deliberately NO seed/ directory.

(cd "$TMPDIR_1B/local" && setup_data_branch </dev/null >/dev/null 2>&1)

assert_file_exists "gates.yaml seeded without seed/ dir" \
    "$TMPDIR_1B/local/.aitask-data/aitasks/metadata/gates.yaml"
assert_file_contains "seedless gates.yaml carries risk_evaluated verifier" \
    "$TMPDIR_1B/local/.aitask-data/aitasks/metadata/gates.yaml" \
    "verifier: aitask-gate-risk"

rm -rf "$TMPDIR_1B"

# --- Test 2: Migration from legacy mode ---
echo "--- Test 2: Migration from legacy mode ---"

TMPDIR_2="$(setup_repo_with_remote)"
SCRIPT_DIR="$TMPDIR_2/local/.aitask-scripts"
mkdir -p "$SCRIPT_DIR"

# Create existing task/plan data on main
(
    cd "$TMPDIR_2/local" || exit 1
    mkdir -p aitasks/metadata aitasks/archived aiplans/archived aitasks/new
    echo "---" > aitasks/t1_test.md
    echo "priority: high" >> aitasks/t1_test.md
    echo "---" >> aitasks/t1_test.md
    echo "Test task content" >> aitasks/t1_test.md
    echo "---" > aiplans/p1_test.md
    echo "Test plan" >> aiplans/p1_test.md
    echo "label1" > aitasks/metadata/labels.txt
    echo "Draft content" > aitasks/new/draft.md
    git add aitasks/ aiplans/
    git commit -m "ait: Add initial tasks" --quiet
    git push --quiet 2>/dev/null
)

(cd "$TMPDIR_2/local" && setup_data_branch </dev/null >/dev/null 2>&1)

# Check task accessible via symlink
assert_symlink "aitasks is symlink after migration" "$TMPDIR_2/local/aitasks"
assert_symlink "aiplans is symlink after migration" "$TMPDIR_2/local/aiplans"

# Check data accessible through symlinks
TOTAL=$((TOTAL + 1))
if [[ -f "$TMPDIR_2/local/aitasks/t1_test.md" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Task file not accessible via symlink"
fi

task_content=$(cat "$TMPDIR_2/local/aitasks/t1_test.md" 2>/dev/null)
assert_contains_ci "Task content preserved" "Test task content" "$task_content"

TOTAL=$((TOTAL + 1))
if [[ -f "$TMPDIR_2/local/aiplans/p1_test.md" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Plan file not accessible via symlink"
fi

# Check draft preserved
TOTAL=$((TOTAL + 1))
if [[ -f "$TMPDIR_2/local/aitasks/new/draft.md" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Draft file not preserved after migration"
fi

# Check metadata preserved
assert_file_exists "Labels.txt preserved" "$TMPDIR_2/local/aitasks/metadata/labels.txt"

# Check data branch has the file
data_branch_has_file=$(git -C "$TMPDIR_2/local/.aitask-data" show HEAD:aitasks/t1_test.md 2>/dev/null | grep -c "Test task content")
assert_eq_trim "Data branch has task file" "1" "$data_branch_has_file"

# Check main no longer tracks aitasks/
main_tracks_aitasks=$(git -C "$TMPDIR_2/local" ls-tree HEAD -- aitasks/ 2>/dev/null | wc -l | tr -d ' ')
assert_eq_trim "Main no longer tracks aitasks/" "0" "$main_tracks_aitasks"

rm -rf "$TMPDIR_2"

# --- Test 3: Idempotent — second run skips ---
echo "--- Test 3: Idempotent — second run skips ---"

TMPDIR_3="$(setup_repo_with_remote)"
SCRIPT_DIR="$TMPDIR_3/local/.aitask-scripts"
mkdir -p "$SCRIPT_DIR"

(cd "$TMPDIR_3/local" && setup_data_branch </dev/null >/dev/null 2>&1)

# Count commits before second run
commits_before=$(git -C "$TMPDIR_3/local" log --oneline 2>/dev/null | wc -l | tr -d ' ')
data_commits_before=$(git -C "$TMPDIR_3/local/.aitask-data" log --oneline 2>/dev/null | wc -l | tr -d ' ')

# Simulate a user-customized coauthor domain before rerun.
cat > "$TMPDIR_3/local/aitasks/metadata/project_config.yaml" << 'YAMLEOF'
codeagent_coauthor_domain: company.example
verify_build:
YAMLEOF

# Second run
output=$(cd "$TMPDIR_3/local" && setup_data_branch </dev/null 2>&1)

commits_after=$(git -C "$TMPDIR_3/local" log --oneline 2>/dev/null | wc -l | tr -d ' ')
data_commits_after=$(git -C "$TMPDIR_3/local/.aitask-data" log --oneline 2>/dev/null | wc -l | tr -d ' ')

assert_contains_ci "Second run says already configured" "already configured" "$output"
assert_eq_trim "No extra commits on main" "$commits_before" "$commits_after"
# t939: the rendered-closure ignore block must be idempotent — exactly one
# occurrence after a second setup run.
closure_block_count=$(grep -cF ".claude/skills/*-/" "$TMPDIR_3/local/.gitignore" 2>/dev/null | tr -d ' ')
assert_eq_trim "Rendered-closure ignore block not duplicated on rerun" "1" "$closure_block_count"
assert_eq_trim "No extra commits on data branch" "$data_commits_before" "$data_commits_after"
assert_file_contains "Customized coauthor domain preserved on rerun" \
    "$TMPDIR_3/local/aitasks/metadata/project_config.yaml" \
    "codeagent_coauthor_domain: company.example"

rm -rf "$TMPDIR_3"

# --- Test 4: Clone on new PC (branch exists, no worktree) ---
echo "--- Test 4: Clone on new PC ---"

TMPDIR_4="$(setup_repo_with_remote)"
SCRIPT_DIR="$TMPDIR_4/local/.aitask-scripts"
mkdir -p "$SCRIPT_DIR"

# First: set up data branch on "PC 1"
(cd "$TMPDIR_4/local" && setup_data_branch </dev/null >/dev/null 2>&1)

# Create some task data
(
    cd "$TMPDIR_4/local/.aitask-data" || exit 1
    mkdir -p aitasks
    echo "---" > aitasks/t5_remote_task.md
    echo "Remote task" >> aitasks/t5_remote_task.md
    git add . && git commit -m "ait: Add remote task" --quiet && git push --quiet 2>/dev/null
)

# Simulate "PC 2": fresh clone, no worktree
git clone --quiet "$TMPDIR_4/remote.git" "$TMPDIR_4/pc2" 2>/dev/null
(cd "$TMPDIR_4/pc2" && git config user.email "test@test.com" && git config user.name "Test")

SCRIPT_DIR="$TMPDIR_4/pc2/.aitask-scripts"
mkdir -p "$SCRIPT_DIR"

(cd "$TMPDIR_4/pc2" && setup_data_branch </dev/null >/dev/null 2>&1)

# Check worktree created
assert_dir_exists "PC2 worktree created" "$TMPDIR_4/pc2/.aitask-data"
assert_symlink "PC2 aitasks symlink" "$TMPDIR_4/pc2/aitasks"
assert_symlink "PC2 aiplans symlink" "$TMPDIR_4/pc2/aiplans"

# Check data is accessible (the task we added on PC1)
TOTAL=$((TOTAL + 1))
if [[ -f "$TMPDIR_4/pc2/aitasks/t5_remote_task.md" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Remote task not accessible on PC2 via symlink"
fi

rm -rf "$TMPDIR_4"

# --- Test 5: No remote (local-only repo) ---
echo "--- Test 5: No remote (local-only) ---"

TMPDIR_5="$(setup_local_repo)"
SCRIPT_DIR="$TMPDIR_5/.aitask-scripts"
mkdir -p "$SCRIPT_DIR"

(cd "$TMPDIR_5" && setup_data_branch </dev/null >/dev/null 2>&1)

# Check local branch exists
TOTAL=$((TOTAL + 1))
if git -C "$TMPDIR_5" show-ref --verify refs/heads/aitask-data &>/dev/null; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: aitask-data branch not created locally"
fi

assert_dir_exists "Local worktree created" "$TMPDIR_5/.aitask-data"
assert_symlink "Local aitasks symlink" "$TMPDIR_5/aitasks"
assert_symlink "Local aiplans symlink" "$TMPDIR_5/aiplans"

# Verify symlinks work (can list directories)
TOTAL=$((TOTAL + 1))
if [[ -d "$TMPDIR_5/aitasks" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: aitasks symlink not functional"
fi

rm -rf "$TMPDIR_5"

# --- Test 6: CLAUDE.md creates file when missing ---
echo "--- Test 6: CLAUDE.md creates when missing ---"

TMPDIR_6="$(mktemp -d)"
setup_seed_file "$TMPDIR_6"

update_claudemd_git_section "$TMPDIR_6"

assert_file_exists "CLAUDE.md created" "$TMPDIR_6/CLAUDE.md"
assert_file_contains "Has section header" "$TMPDIR_6/CLAUDE.md" "## Git Operations on Task/Plan Files"
assert_file_contains "Has ait git reference" "$TMPDIR_6/CLAUDE.md" "./ait git"

rm -rf "$TMPDIR_6"

# --- Test 7: CLAUDE.md appends to existing ---
echo "--- Test 7: CLAUDE.md appends to existing ---"

TMPDIR_7="$(mktemp -d)"
setup_seed_file "$TMPDIR_7"
echo "# My Project" > "$TMPDIR_7/CLAUDE.md"
echo "" >> "$TMPDIR_7/CLAUDE.md"
echo "Some existing content." >> "$TMPDIR_7/CLAUDE.md"

update_claudemd_git_section "$TMPDIR_7" 2>/dev/null

assert_file_contains "Original content preserved" "$TMPDIR_7/CLAUDE.md" "# My Project"
assert_file_contains "Original detail preserved" "$TMPDIR_7/CLAUDE.md" "Some existing content."
assert_file_contains "Section appended" "$TMPDIR_7/CLAUDE.md" "## Git Operations on Task/Plan Files"

rm -rf "$TMPDIR_7"

# --- Test 8: CLAUDE.md idempotent ---
echo "--- Test 8: CLAUDE.md idempotent ---"

TMPDIR_8="$(mktemp -d)"
setup_seed_file "$TMPDIR_8"
echo "# Project" > "$TMPDIR_8/CLAUDE.md"

update_claudemd_git_section "$TMPDIR_8" 2>/dev/null
update_claudemd_git_section "$TMPDIR_8" 2>/dev/null

section_count=$(grep -c "## Git Operations on Task/Plan Files" "$TMPDIR_8/CLAUDE.md" 2>/dev/null || echo "0")
assert_eq_trim "Section appears exactly once" "1" "$section_count"

rm -rf "$TMPDIR_8"

# --- Test 8b: setup_data_branch's Step 9 commit never sweeps a dirty CLAUDE.md ---
echo "--- Test 8b: Step 9 does not sweep a user's CLAUDE.md edits (t1612) ---"

# Before t1612 Step 9 did `git add CLAUDE.md` unconditionally-if-present and then
# committed with NO pathspec, so a user's uncommitted CLAUDE.md edits were swept
# into "ait: Configure task data branch..." -- bypassing the
# snapshot_pre_setup_dirty baseline that commit_framework_files honours. Dropping
# CLAUDE.md from files_to_add is what fixes that, and this is the only assertion
# in the suite that can see it: every other test passes either way.
TMPDIR_8B="$(setup_local_repo)"
SCRIPT_DIR="$TMPDIR_8B/.aitask-scripts"
mkdir -p "$SCRIPT_DIR"
setup_seed_file "$TMPDIR_8B"

# CLAUDE.md tracked in HEAD, then edited in the worktree.
printf '# My Project\n\n## Build\n\nRun make.\n' > "$TMPDIR_8B/CLAUDE.md"
(cd "$TMPDIR_8B" && git add CLAUDE.md && git commit -m "add CLAUDE.md" --quiet)
printf '\nUSER EDIT t1612\n' >> "$TMPDIR_8B/CLAUDE.md"

(cd "$TMPDIR_8B" && setup_data_branch </dev/null >/dev/null 2>&1)

head_claudemd=$(git -C "$TMPDIR_8B" show HEAD:CLAUDE.md 2>/dev/null || true)
assert_not_contains "Step 9 did not commit the user's CLAUDE.md edit" "USER EDIT t1612" "$head_claudemd"
porcelain_8b=$(git -C "$TMPDIR_8B" status --porcelain -- CLAUDE.md 2>/dev/null || true)
assert_contains "User's CLAUDE.md edit still uncommitted in the worktree" "CLAUDE.md" "$porcelain_8b"

rm -rf "$TMPDIR_8B"

# --- Test 9: Syntax check + shellcheck ---
echo "--- Test 9: Syntax check ---"

TOTAL=$((TOTAL + 1))
if bash -n "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" 2>/dev/null; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: bash -n aitask_setup.sh (syntax error)"
fi

# Shellcheck (if available) — only check for actual errors, not info/warning/style
if command -v shellcheck &>/dev/null; then
    TOTAL=$((TOTAL + 1))
    sc_errors=$(shellcheck --severity=error "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" 2>&1 | wc -l | tr -d ' ')
    if [[ "$sc_errors" -eq 0 ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: shellcheck found errors in aitask_setup.sh"
        shellcheck --severity=error "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" 2>&1 | head -20
    fi
fi

# --- Test 10: ensure_project_config_defaults inserts missing key ---
echo "--- Test 10: ensure_project_config_defaults inserts missing key ---"

TMPDIR_10="$(mktemp -d)"
mkdir -p "$TMPDIR_10/.aitask-scripts" "$TMPDIR_10/seed" "$TMPDIR_10/aitasks/metadata"
cp "$PROJECT_DIR/seed/project_config.yaml" "$TMPDIR_10/seed/"
SCRIPT_DIR="$TMPDIR_10/.aitask-scripts"
cat > "$TMPDIR_10/aitasks/metadata/project_config.yaml" << 'YAMLEOF'
verify_build: cargo build
YAMLEOF

ensure_project_config_defaults >/dev/null 2>&1

assert_file_contains "Missing coauthor domain inserted" \
    "$TMPDIR_10/aitasks/metadata/project_config.yaml" \
    "codeagent_coauthor_domain: aitasks.io"
assert_file_contains "Existing verify_build preserved" \
    "$TMPDIR_10/aitasks/metadata/project_config.yaml" \
    "verify_build: cargo build"

rm -rf "$TMPDIR_10"

# --- Test 11: setup_id_counter respects existing tasks on aitask-data (t686) ---
echo "--- Test 11: counter init with pre-existing tasks on aitask-data ---"

TMPDIR_11="$(setup_repo_with_remote)"

# PC1: set up data branch and seed it with tasks t1, t2, t10
SCRIPT_DIR="$TMPDIR_11/local/.aitask-scripts"
mkdir -p "$SCRIPT_DIR" "$TMPDIR_11/local/seed"
cp "$PROJECT_DIR/seed/project_config.yaml" "$TMPDIR_11/local/seed/" 2>/dev/null || true

(cd "$TMPDIR_11/local" && setup_data_branch </dev/null >/dev/null 2>&1)
(
    cd "$TMPDIR_11/local/.aitask-data" || exit 1
    mkdir -p aitasks
    : > aitasks/t1_alpha.md
    : > aitasks/t2_beta.md
    : > aitasks/t10_gamma.md
    git add aitasks/
    git commit -m "ait: seed tasks" --quiet
    git push --quiet 2>/dev/null
)

# PC2: fresh clone — no aitask-ids branch on remote yet, but aitask-data has t1/t2/t10
git clone --quiet "$TMPDIR_11/remote.git" "$TMPDIR_11/pc2" 2>/dev/null
(cd "$TMPDIR_11/pc2" && git config user.email "test@test.com" && git config user.name "Test")
SCRIPT_DIR="$TMPDIR_11/pc2/.aitask-scripts"
mkdir -p "$SCRIPT_DIR"
# aitask_claim_id.sh and lib/ resolve via the script's own SCRIPT_DIR — copy
# them into the test repo so they are reachable when setup_id_counter shells out.
cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" "$SCRIPT_DIR/"
cp -r "$PROJECT_DIR/.aitask-scripts/lib" "$SCRIPT_DIR/"

# Run setup in the post-fix order: data branch first, THEN counter init.
(cd "$TMPDIR_11/pc2" && setup_data_branch </dev/null >/dev/null 2>&1)
(cd "$TMPDIR_11/pc2" && setup_id_counter </dev/null >/dev/null 2>&1)

# Counter must be max(1,2,10) + 1 = 11, not 1.
counter_val=$(git -C "$TMPDIR_11/pc2" fetch origin aitask-ids --quiet 2>/dev/null \
    && git -C "$TMPDIR_11/pc2" show origin/aitask-ids:next_id.txt 2>/dev/null \
    | tr -d '[:space:]')
assert_eq_trim "Counter seeded to max(existing)+1 on fresh clone" "11" "$counter_val"

# Static check: regardless of how the helpers behave in isolation, main() must
# call setup_data_branch BEFORE setup_id_counter or the fresh-clone scenario
# above will silently re-break.
main_body="$(awk '/^main\(\) \{/,/^\}/' "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh")"
data_line=$(echo "$main_body" | grep -n '^[[:space:]]*setup_data_branch$' | head -1 | cut -d: -f1)
counter_line=$(echo "$main_body" | grep -n '^[[:space:]]*setup_id_counter$' | head -1 | cut -d: -f1)
TOTAL=$((TOTAL + 1))
if [[ -n "$data_line" && -n "$counter_line" && "$data_line" -lt "$counter_line" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: main() must call setup_data_branch before setup_id_counter (got data=$data_line counter=$counter_line)"
fi

rm -rf "$TMPDIR_11"

# --- Test 12: gitignore migration from legacy trailing-slash form (t699) ---
echo "--- Test 12: gitignore migration from legacy trailing-slash form ---"

TMPDIR_12="$(setup_repo_with_remote)"
SCRIPT_DIR="$TMPDIR_12/local/.aitask-scripts"
mkdir -p "$SCRIPT_DIR" "$TMPDIR_12/local/seed"
cp "$PROJECT_DIR/seed/aitasks_agent_instructions.seed.md" "$TMPDIR_12/local/seed/"
cp "$PROJECT_DIR/seed/project_config.yaml" "$TMPDIR_12/local/seed/"

# Pre-seed .gitignore with the legacy trailing-slash entries that older
# setup_data_branch versions wrote. The symptom is that these patterns match
# directories only — once setup_data_branch turns aitasks/aiplans into
# symlinks, they appear as untracked in `git status`.
(
    cd "$TMPDIR_12/local" || exit 1
    cat > .gitignore <<'EOF'
.aitask-data/
aitasks/
aiplans/
EOF
    git add .gitignore
    git commit -m "init legacy gitignore" --quiet
    git push --quiet 2>/dev/null
)

(cd "$TMPDIR_12/local" && setup_data_branch </dev/null >/dev/null 2>&1)

# Legacy entries rewritten to bare form
TOTAL=$((TOTAL + 1))
if grep -qxF "aitasks/" "$TMPDIR_12/local/.gitignore" 2>/dev/null; then
    FAIL=$((FAIL + 1))
    echo "FAIL: legacy 'aitasks/' line should have been rewritten"
else
    PASS=$((PASS + 1))
fi
TOTAL=$((TOTAL + 1))
if grep -qxF "aiplans/" "$TMPDIR_12/local/.gitignore" 2>/dev/null; then
    FAIL=$((FAIL + 1))
    echo "FAIL: legacy 'aiplans/' line should have been rewritten"
else
    PASS=$((PASS + 1))
fi
TOTAL=$((TOTAL + 1))
if grep -qxF "aitasks" "$TMPDIR_12/local/.gitignore" 2>/dev/null; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: bare 'aitasks' line should be present after migration"
fi
TOTAL=$((TOTAL + 1))
if grep -qxF "aiplans" "$TMPDIR_12/local/.gitignore" 2>/dev/null; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: bare 'aiplans' line should be present after migration"
fi

# No duplication: exactly one bare 'aitasks' / 'aiplans' line.
aitasks_count=$(grep -cxF "aitasks" "$TMPDIR_12/local/.gitignore" 2>/dev/null | tr -d ' ')
aiplans_count=$(grep -cxF "aiplans" "$TMPDIR_12/local/.gitignore" 2>/dev/null | tr -d ' ')
assert_eq_trim "No duplicate bare 'aitasks' line" "1" "$aitasks_count"
assert_eq_trim "No duplicate bare 'aiplans' line" "1" "$aiplans_count"

# Symlinks must now be ignored: legacy trailing-slash entries no longer
# match them, the migration rewrote them to the bare form. Filter to the
# two paths under test so unrelated fixture untracked files don't confound.
symlink_porcelain="$(git -C "$TMPDIR_12/local" status --porcelain | grep -E '^\?\? (aitasks|aiplans)$' || true)"
assert_eq_trim "aitasks/aiplans symlinks ignored after gitignore migration" "" "$symlink_porcelain"

# Migration commit was created — staged change for .gitignore did not leak
# into a dirty index.
gitignore_status="$(git -C "$TMPDIR_12/local" status --porcelain -- .gitignore)"
assert_eq_trim ".gitignore committed by migration (not left dirty)" "" "$gitignore_status"

rm -rf "$TMPDIR_12"

# --- Test 13: setup_worktree_dirs_gitignore (t1616) ---
#
# The framework creates two worktree trees inside the project — aiwork/<task>
# (task-workflow Step 7) and .aitask-crews/crew-<id> — and `ait setup` seeded
# neither, so every downstream project left both exposed to a broad `git add -A`
# in a concurrent session. The real function is driven here (not a replica): it
# reads SCRIPT_DIR/.. for the project dir, exactly as its siblings do.
echo "--- Test 13: setup_worktree_dirs_gitignore ---"

TMPDIR_13="$(setup_local_repo)"
mkdir -p "$TMPDIR_13/.aitask-scripts"
SCRIPT_DIR="$TMPDIR_13/.aitask-scripts"
rm -f "$TMPDIR_13/.gitignore"

(cd "$TMPDIR_13" && setup_worktree_dirs_gitignore >/dev/null 2>&1)

# Positive: both worktree trees are ignored.
for p in "aiwork/t1_x/" ".aitask-crews/crew-1/"; do
    TOTAL=$((TOTAL + 1))
    if git -C "$TMPDIR_13" check-ignore -q "$p"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: worktree dir not ignored: $p"
    fi
done

# Negative control: neither rule may over-match a sibling path.
for p in "aiwork.md" "aidocs/x.md"; do
    TOTAL=$((TOTAL + 1))
    if git -C "$TMPDIR_13" check-ignore -q "$p"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: over-matched a sibling path: $p"
    else
        PASS=$((PASS + 1))
    fi
done

# Idempotent: a second run must not duplicate either line.
(cd "$TMPDIR_13" && setup_worktree_dirs_gitignore >/dev/null 2>&1)
assert_eq_trim "No duplicate 'aiwork/' line" "1" \
    "$(grep -c '^aiwork/$' "$TMPDIR_13/.gitignore")"
assert_eq_trim "No duplicate '.aitask-crews/' line" "1" \
    "$(grep -c '^\.aitask-crews/$' "$TMPDIR_13/.gitignore")"

rm -rf "$TMPDIR_13"

# --- Test 13b: the two rules are guarded independently ---
# A project that already carries one (this repo carried .aitask-crews/ by hand
# for a long time) must gain only the other — not a duplicate of both.
echo "--- Test 13b: partial pre-existing state ---"

TMPDIR_13B="$(setup_local_repo)"
mkdir -p "$TMPDIR_13B/.aitask-scripts"
SCRIPT_DIR="$TMPDIR_13B/.aitask-scripts"
printf '# AgentCrew worktrees (local, per-crew branches)\n.aitask-crews/\n' \
    > "$TMPDIR_13B/.gitignore"

(cd "$TMPDIR_13B" && setup_worktree_dirs_gitignore >/dev/null 2>&1)

assert_eq_trim "13b: 'aiwork/' added" "1" \
    "$(grep -c '^aiwork/$' "$TMPDIR_13B/.gitignore")"
assert_eq_trim "13b: pre-existing '.aitask-crews/' not duplicated" "1" \
    "$(grep -c '^\.aitask-crews/$' "$TMPDIR_13B/.gitignore")"

rm -rf "$TMPDIR_13B"

# --- Test 14: worktree-add failure surfaces git's own error (t1627) ---
# The old message named `git worktree add .aitask-data aitask-data` as the
# remedy -- the command that had just failed -- and 2>/dev/null discarded git's
# explanation. Fixture: a leftover non-empty .aitask-data/ directory with no
# .git, which is production-reachable (a pruned worktree, a botched migration)
# and does NOT trip the already-configured early return.
echo "--- Test 14: worktree-add failure surfaces git's error ---"

TMPDIR_14="$(setup_local_repo)"
SCRIPT_DIR="$TMPDIR_14/.aitask-scripts"
mkdir -p "$SCRIPT_DIR"
mkdir -p "$TMPDIR_14/.aitask-data"
echo "leftover" > "$TMPDIR_14/.aitask-data/stale.txt"

rc_14=0
out_14="$(cd "$TMPDIR_14" && setup_data_branch </dev/null 2>&1)" || rc_14=$?

assert_eq_trim "14: setup_data_branch still returns 0 (setup continues)" "0" "$rc_14"
assert_contains "14: git's own error is surfaced" "already exists" "$out_14"
assert_contains "14: the message says git said it" "git said:" "$out_14"
# Negative control: the impossible remedy must be gone.
assert_not_contains "14: no longer advises the command that just failed" \
    "You may need to run: git worktree add" "$out_14"
assert_contains "14: names the legacy-layout consequence" \
    "stay on the current branch (legacy layout)" "$out_14"
# `return` skips Steps 3-9 in one jump: nothing is populated, nothing linked.
assert_file_not_exists "14: no worktree was created" "$TMPDIR_14/.aitask-data/.git"
assert_dir_not_exists "14: Step 3 did not populate the leftover directory" \
    "$TMPDIR_14/.aitask-data/aitasks"
assert_not_symlink "14: Step 6 did not create the aitasks symlink" "$TMPDIR_14/aitasks"
assert_not_symlink "14: Step 6 did not create the aiplans symlink" "$TMPDIR_14/aiplans"

rm -rf "$TMPDIR_14"

# --- Test 15: linked worktree, primary already initialized (t1627) ---
echo "--- Test 15: linked worktree refused, primary initialized ---"

TMPDIR_15="$(setup_local_repo)"
SCRIPT_DIR="$TMPDIR_15/.aitask-scripts"
mkdir -p "$SCRIPT_DIR"
cp "$PROJECT_DIR/.aitask-scripts/gates_reference.yaml" "$SCRIPT_DIR/"
(cd "$TMPDIR_15" && setup_data_branch </dev/null >/dev/null 2>&1)
git -C "$TMPDIR_15" worktree add --quiet "$TMPDIR_15/aiwork/t1" -b aitask/t1 2>/dev/null

# ait setup run from inside the worktree resolves project_dir to the worktree.
SCRIPT_DIR="$TMPDIR_15/aiwork/t1/.aitask-scripts"
mkdir -p "$SCRIPT_DIR"
rc_15=0
out_15="$(cd "$TMPDIR_15/aiwork/t1" && setup_data_branch </dev/null 2>&1)" || rc_15=$?

assert_eq_trim "15: returns 0 (rest of setup continues)" "0" "$rc_15"
assert_contains "15: says it is a linked worktree" "is a linked git worktree" "$out_15"
assert_contains "15: names the primary checkout" "$TMPDIR_15" "$out_15"
assert_contains "15: offers the --link-worktree remedy" "--link-worktree" "$out_15"
assert_file_not_exists "15: no second data worktree in the task worktree" \
    "$TMPDIR_15/aiwork/t1/.aitask-data/.git"

rm -rf "$TMPDIR_15"

# --- Test 16: linked worktree, primary NOT initialized (t1627) ---
# The case the guard exists for. Without it Step 1 creates AND pushes the
# aitask-data branch, and Step 2 then succeeds, putting the repo's only task
# data inside a throwaway worktree. Assert there are no side effects at all.
echo "--- Test 16: linked worktree refused, primary uninitialized ---"

TMPDIR_16="$(setup_repo_with_remote)"
SCRIPT_DIR="$TMPDIR_16/local/.aitask-scripts"
mkdir -p "$SCRIPT_DIR"
git -C "$TMPDIR_16/local" worktree add --quiet "$TMPDIR_16/local/aiwork/t1" -b aitask/t1 2>/dev/null

SCRIPT_DIR="$TMPDIR_16/local/aiwork/t1/.aitask-scripts"
mkdir -p "$SCRIPT_DIR"
rc_16=0
out_16="$(cd "$TMPDIR_16/local/aiwork/t1" && setup_data_branch </dev/null 2>&1)" || rc_16=$?

assert_eq_trim "16: returns 0 (rest of setup continues)" "0" "$rc_16"
assert_contains "16: says it is a linked worktree" "is a linked git worktree" "$out_16"
assert_contains "16: tells the user to run setup at the primary first" \
    "Run 'ait setup' in" "$out_16"
assert_contains "16: still offers --link-worktree for afterwards" "--link-worktree" "$out_16"

# Step 1 never ran: no branch locally and none pushed.
rc_branch_16=0
git -C "$TMPDIR_16/local" show-ref --verify --quiet refs/heads/aitask-data || rc_branch_16=$?
assert_exit_nonzero_rc "16: no local aitask-data branch was created" "$rc_branch_16"
assert_eq_trim "16: no aitask-data branch was pushed to the remote" "" \
    "$(git -C "$TMPDIR_16/local" ls-remote --heads origin aitask-data 2>/dev/null)"

# Step 2 never ran: no data checkout anywhere.
assert_file_not_exists "16: no .aitask-data in the worktree" \
    "$TMPDIR_16/local/aiwork/t1/.aitask-data/.git"
assert_file_not_exists "16: no .aitask-data at the primary either" \
    "$TMPDIR_16/local/.aitask-data/.git"

rm -rf "$TMPDIR_16"

# --- Test 17: a git submodule primary is NOT a linked worktree (t1627) ---
# The discriminating case for the `git-dir != git-common-dir` predicate. A
# submodule's common dir is <super>/.git/modules/<name>, so the older
# dirname(git-common-dir) comparison calls its own primary checkout a linked
# worktree -- which under the new early return would silently disable
# data-branch setup for every submodule-hosted project.
echo "--- Test 17: submodule primary classifies as not-linked ---"

TMPDIR_17="$(mktemp -d)"
git init -q --initial-branch=main "$TMPDIR_17/child"
(cd "$TMPDIR_17/child" && git config user.email t@t && git config user.name T \
    && echo hi > a.txt && git add . && git commit -qm init)
git init -q --initial-branch=main "$TMPDIR_17/super"
(cd "$TMPDIR_17/super" && git config user.email t@t && git config user.name T \
    && echo s > s.txt && git add . && git commit -qm init \
    && git -c protocol.file.allow=always submodule add -q ../child sub \
    && git commit -qm "add sub")

rc_17=0
ait_linked_worktree_roots "$TMPDIR_17/super/sub" || rc_17=$?
assert_eq_trim "17: submodule primary is classified not-linked (rc 1)" "1" "$rc_17"

# And it configures fully rather than being refused.
SCRIPT_DIR="$TMPDIR_17/super/sub/.aitask-scripts"
mkdir -p "$SCRIPT_DIR"
cp "$PROJECT_DIR/.aitask-scripts/gates_reference.yaml" "$SCRIPT_DIR/"
(cd "$TMPDIR_17/super/sub" && setup_data_branch </dev/null >/dev/null 2>&1)
assert_file_exists "17: submodule got its data worktree" \
    "$TMPDIR_17/super/sub/.aitask-data/.git"
assert_symlink "17: submodule got the aitasks symlink" "$TMPDIR_17/super/sub/aitasks"

# A linked worktree OF that submodule must still resolve to the submodule
# CHECKOUT, not to <super>/.git/modules/sub -- git's own `worktree list` reports
# the latter, so the resolution needs the extra --show-toplevel hop.
git -C "$TMPDIR_17/super/sub" worktree add --quiet "$TMPDIR_17/subwt" -b wt1 2>/dev/null
AIT_WT_TOPLEVEL=""; AIT_WT_MAIN_ROOT=""
rc_17b=0
ait_linked_worktree_roots "$TMPDIR_17/subwt" || rc_17b=$?
assert_eq_trim "17: linked worktree of a submodule is classified linked (rc 0)" "0" "$rc_17b"
assert_eq_trim "17: its primary root is the submodule checkout, not .git/modules" \
    "$(cd "$TMPDIR_17/super/sub" && pwd -P)" "$AIT_WT_MAIN_ROOT"

rm -rf "$TMPDIR_17"

# --- Test 18: guard placement positive control (t1627) ---
# The new early return sits on the path EVERY primary checkout takes. Pin both
# halves: the classifier says "not linked" for the primary and for a plain
# subdirectory of it, and a primary still configures end to end.
echo "--- Test 18: guard placement positive control ---"

TMPDIR_18="$(setup_local_repo)"
SCRIPT_DIR="$TMPDIR_18/.aitask-scripts"
mkdir -p "$SCRIPT_DIR" "$TMPDIR_18/src/nested"
cp "$PROJECT_DIR/.aitask-scripts/gates_reference.yaml" "$SCRIPT_DIR/"

rc_18a=0
ait_linked_worktree_roots "$TMPDIR_18" || rc_18a=$?
assert_eq_trim "18: primary checkout is not-linked (rc 1)" "1" "$rc_18a"
rc_18b=0
ait_linked_worktree_roots "$TMPDIR_18/src/nested" || rc_18b=$?
assert_eq_trim "18: plain subdirectory of the primary is not-linked (rc 1)" "1" "$rc_18b"

(cd "$TMPDIR_18" && setup_data_branch </dev/null >/dev/null 2>&1)
assert_file_exists "18: primary still gets its data worktree" "$TMPDIR_18/.aitask-data/.git"
assert_symlink "18: primary still gets the aitasks symlink" "$TMPDIR_18/aitasks"
assert_symlink "18: primary still gets the aiplans symlink" "$TMPDIR_18/aiplans"
assert_file_contains "18: primary still gets the .gitignore block" \
    "$TMPDIR_18/.gitignore" ".aitask-data/"

rm -rf "$TMPDIR_18"

# --- Test 19: push failures report git's error (t1627) ---
# Both `warn`s in setup_data_branch discarded stderr. Fixture: an origin that
# points at nothing, so both the branch push (Step 1) and the data push (Step 4)
# fail while the worktree itself is still created.
echo "--- Test 19: push warns carry git's error ---"

TMPDIR_19="$(setup_local_repo)"
SCRIPT_DIR="$TMPDIR_19/.aitask-scripts"
mkdir -p "$SCRIPT_DIR"
cp "$PROJECT_DIR/.aitask-scripts/gates_reference.yaml" "$SCRIPT_DIR/"
git -C "$TMPDIR_19" remote add origin "$TMPDIR_19/does-not-exist.git"

out_19="$(cd "$TMPDIR_19" && setup_data_branch </dev/null 2>&1)" || true

assert_contains "19: branch-push warn fired" "Could not push aitask-data branch" "$out_19"
assert_contains "19: data-push warn fired" "Could not push data branch" "$out_19"
assert_contains "19: git's error is included" "does-not-exist.git" "$out_19"
# The pushes are non-fatal: the worktree and symlinks still land.
assert_file_exists "19: worktree still created despite push failures" \
    "$TMPDIR_19/.aitask-data/.git"
assert_symlink "19: symlinks still created" "$TMPDIR_19/aitasks"

rm -rf "$TMPDIR_19"

# --- Test 20: path handling is separator-free (t1627) ---
# git emits worktree paths raw and unquoted, so any resolution that parses a
# line-oriented listing truncates a path containing a newline. Every value here
# flows through a variable instead. Both halves matter: a newline in the MAIN
# worktree's own path is what a listing parser breaks on, and a newline in a
# LINKED worktree's path must not perturb the primary's resolution either.
echo "--- Test 20: newline-containing paths resolve ---"

TMPDIR_20="$(mktemp -d)"
NL_MAIN="$TMPDIR_20/nl"$'\n'"main"
git init -q --initial-branch=main "$NL_MAIN"
(cd "$NL_MAIN" && git config user.email t@t && git config user.name T \
    && echo x > a && git add . && git commit -qm init)

AIT_WT_MAIN_ROOT=""
rc_20a=0
ait_main_worktree_root "$NL_MAIN" || rc_20a=$?
assert_eq_trim "20: newline-named main worktree resolves" "0" "$rc_20a"
assert_eq_trim "20: and resolves to the full path, not a truncation" \
    "$(cd "$NL_MAIN" && pwd -P)" "$AIT_WT_MAIN_ROOT"

# A linked worktree of it: classified linked, primary still the full path.
git -C "$NL_MAIN" worktree add --quiet "$TMPDIR_20/nlwt" -b w1 2>/dev/null
AIT_WT_MAIN_ROOT=""; AIT_WT_TOPLEVEL=""
rc_20b=0
ait_linked_worktree_roots "$TMPDIR_20/nlwt" || rc_20b=$?
assert_eq_trim "20: worktree of a newline-named primary is linked (rc 0)" "0" "$rc_20b"
assert_eq_trim "20: its primary root is the untruncated path" \
    "$(cd "$NL_MAIN" && pwd -P)" "$AIT_WT_MAIN_ROOT"

# A newline in a LINKED worktree's path must not disturb the primary either.
NL_WT="$TMPDIR_20/nl"$'\n'"wt"
git init -q --initial-branch=main "$TMPDIR_20/plain"
(cd "$TMPDIR_20/plain" && git config user.email t@t && git config user.name T \
    && echo x > a && git add . && git commit -qm init)
git -C "$TMPDIR_20/plain" worktree add --quiet "$NL_WT" -b w2 2>/dev/null
AIT_WT_MAIN_ROOT=""
rc_20c=0
ait_linked_worktree_roots "$NL_WT" || rc_20c=$?
assert_eq_trim "20: newline-named linked worktree is classified linked" "0" "$rc_20c"
assert_eq_trim "20: and its primary resolves normally" \
    "$(cd "$TMPDIR_20/plain" && pwd -P)" "$AIT_WT_MAIN_ROOT"

rm -rf "$TMPDIR_20"

# --- Test 21: --separate-git-dir is the accepted layout boundary (t1627) ---
# That linkage is one-way — the gitdir carries no core.worktree — so nothing,
# git included, can name the checkout from it (`git worktree list` reports the
# gitdir). The helper answers state 2 and callers refuse, rather than the old
# dirname() behaviour of silently returning the gitdir's unrelated PARENT.
echo "--- Test 21: --separate-git-dir refuses rather than guessing ---"

TMPDIR_21="$(mktemp -d)"
git init -q --initial-branch=main --separate-git-dir="$TMPDIR_21/sgd.git" "$TMPDIR_21/sgd"
(cd "$TMPDIR_21/sgd" && git config user.email t@t && git config user.name T \
    && echo x > a && git add . && git commit -qm init)

AIT_WT_MAIN_ROOT=""
rc_21=0
ait_main_worktree_root "$TMPDIR_21/sgd" || rc_21=$?
assert_eq_trim "21: reports indeterminate (state 2), not a wrong root" "2" "$rc_21"
assert_eq_trim "21: and never publishes the gitdir's parent as the root" "" "$AIT_WT_MAIN_ROOT"

# Its PRIMARY checkout is still classified not-linked, so setup is unaffected:
# the git-dir/common-dir predicate settles it before any root is needed.
rc_21b=0
ait_linked_worktree_roots "$TMPDIR_21/sgd" || rc_21b=$?
assert_eq_trim "21: the primary checkout still classifies not-linked (rc 1)" "1" "$rc_21b"

rm -rf "$TMPDIR_21"

# ============================================================================
# t1631 — silent failures in setup_data_branch's probe / fetch / copy / commit
#
# Every fixture below drives a real setup_data_branch through its real entry
# point. The failures are injected with PATH shims (see shim_install) rather
# than with permissions, so each is deterministic for every EUID.
# ============================================================================

# --- Test 22: decoy remote ref is not evidence (exact-ref probe) ---
echo "--- Test 22: decoy remote ref does not count as 'found' (t1631) ---"

# `ls-remote --heads origin aitask-data` matches on the TAIL of a ref, and the
# old caller grepped unanchored — so a remote carrying only
# refs/heads/backup/aitask-data answered "found", the fetch then failed on a ref
# that was never there, and Step 2 died on "invalid reference: aitask-data".
# The correct answer is "absent": create the orphan branch and carry on.
TMPDIR_22="$(setup_repo_with_remote)"
SCRIPT_DIR="$TMPDIR_22/local/.aitask-scripts"
mkdir -p "$SCRIPT_DIR"
(cd "$TMPDIR_22/local" && git push --quiet origin "HEAD:refs/heads/backup/aitask-data" 2>/dev/null)

(cd "$TMPDIR_22/local" && setup_data_branch </dev/null >/dev/null 2>&1)

assert_dir_exists "22: worktree created despite decoy ref" "$TMPDIR_22/local/.aitask-data"
assert_file_exists "22: worktree is a real git worktree" "$TMPDIR_22/local/.aitask-data/.git"
assert_symlink "22: aitasks symlink created" "$TMPDIR_22/local/aitasks"
TOTAL=$((TOTAL + 1))
if git -C "$TMPDIR_22/local" show-ref --verify refs/heads/aitask-data &>/dev/null; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: 22: aitask-data branch not created (decoy ref treated as 'found')"
fi

rm -rf "$TMPDIR_22"

# --- Test 23: a failed fetch is reported and does not claim the branch ---
echo "--- Test 23: failed fetch refuses rather than claiming the branch (t1631) ---"

TMPDIR_23="$(setup_repo_with_remote)"
SCRIPT_DIR="$TMPDIR_23/local/.aitask-scripts"
mkdir -p "$SCRIPT_DIR"
seed_remote_data_branch "$TMPDIR_23/local"
# Drop the local ref the push left behind: this fixture is "the remote has it,
# we have no copy, and the fetch fails".
git -C "$TMPDIR_23/local" update-ref -d refs/remotes/origin/aitask-data 2>/dev/null

shim_install git:git_fetch
out_23=$(cd "$TMPDIR_23/local" && setup_data_branch </dev/null 2>&1)
shim_remove

assert_contains "23: git's fetch error is surfaced" "simulated fetch failure" "$out_23"
assert_contains_ci "23: refusal is explained" "could not be fetched" "$out_23"
assert_dir_not_exists "23: no worktree created" "$TMPDIR_23/local/.aitask-data"
assert_not_symlink "23: aitasks left as a real directory" "$TMPDIR_23/local/aitasks"
TOTAL=$((TOTAL + 1))
if git -C "$TMPDIR_23/local" show-ref --verify refs/heads/aitask-data &>/dev/null; then
    FAIL=$((FAIL + 1))
    echo "FAIL: 23: a second, unrelated aitask-data branch was created locally"
else
    PASS=$((PASS + 1))
fi

rm -rf "$TMPDIR_23"

# --- Test 24: a local branch still wins after a failed fetch ---
echo "--- Test 24: local aitask-data still usable when the fetch fails (t1631) ---"

# Negative control for Test 23: the fall-through must not become a blanket
# refusal. The remote copy is unreachable, but a local branch is a real answer.
TMPDIR_24="$(setup_repo_with_remote)"
SCRIPT_DIR="$TMPDIR_24/local/.aitask-scripts"
mkdir -p "$SCRIPT_DIR"
seed_remote_data_branch "$TMPDIR_24/local"
git -C "$TMPDIR_24/local" branch aitask-data 2>/dev/null

shim_install git:git_fetch
(cd "$TMPDIR_24/local" && setup_data_branch </dev/null >/dev/null 2>&1)
shim_remove

assert_dir_exists "24: worktree created from the local branch" "$TMPDIR_24/local/.aitask-data"
assert_file_exists "24: worktree is a real git worktree" "$TMPDIR_24/local/.aitask-data/.git"
assert_symlink "24: aitasks symlink created" "$TMPDIR_24/local/aitasks"

rm -rf "$TMPDIR_24"

# --- Test 25: an unreachable remote is 'unknown', not a refusal ---
echo "--- Test 25: unreachable remote still creates the branch (t1631 boundary) ---"

# The refusal in Test 23 is scoped to "the remote definitively HAS the branch".
# An unreachable remote is a different state: warn, but keep working, or an
# offline `ait setup` would stop being possible.
TMPDIR_25="$(setup_repo_with_remote)"
SCRIPT_DIR="$TMPDIR_25/local/.aitask-scripts"
mkdir -p "$SCRIPT_DIR"
git -C "$TMPDIR_25/local" remote set-url origin "$TMPDIR_25/does-not-exist.git"

out_25=$(cd "$TMPDIR_25/local" && setup_data_branch </dev/null 2>&1)

assert_contains_ci "25: the probe failure is surfaced" "could not check the remote" "$out_25"
assert_dir_exists "25: worktree still created" "$TMPDIR_25/local/.aitask-data"
assert_file_exists "25: worktree is a real git worktree" "$TMPDIR_25/local/.aitask-data/.git"
assert_symlink "25: aitasks symlink created" "$TMPDIR_25/local/aitasks"

rm -rf "$TMPDIR_25"

# Build a migration-shaped fixture: real task/plan data committed on main.
setup_migration_fixture() {
    local tmpdir
    tmpdir="$(setup_repo_with_remote)"
    (
        cd "$tmpdir/local" || exit 1
        mkdir -p aitasks/metadata aitasks/archived aiplans/archived aitasks/new
        printf -- '---\npriority: high\n---\nTest task content\n' > aitasks/t1_test.md
        printf -- '---\n---\nTest plan\n' > aiplans/p1_test.md
        echo "label1" > aitasks/metadata/labels.txt
        echo "Draft content" > aitasks/new/draft.md
        git add aitasks/ aiplans/
        git commit -m "ait: Add initial tasks" --quiet
        git push --quiet 2>/dev/null
    )
    echo "$tmpdir"
}

# The no-delete guarantee, asserted the same way everywhere it must hold.
assert_migration_originals_intact() {
    local label="$1" root="$2"
    assert_file_exists "$label: task file still on the current branch" "$root/aitasks/t1_test.md"
    assert_file_exists "$label: plan file still on the current branch" "$root/aiplans/p1_test.md"
    assert_not_symlink "$label: aitasks left as a real directory" "$root/aitasks"
    local tracked
    tracked=$(git -C "$root" ls-tree HEAD -- aitasks/ 2>/dev/null | wc -l | tr -d ' ')
    TOTAL=$((TOTAL + 1))
    if [[ "$tracked" != "0" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $label: aitasks/ is no longer tracked on the current branch"
    fi
}

# --- Test 26: a failed copy aborts before anything is deleted ---
echo "--- Test 26: failed cp aborts the migration, deletes nothing (t1631) ---"

# Step 5 removes these very files from the current branch. With cp's status
# discarded, a copy that stopped part-way reached that delete looking exactly
# like a complete one.
TMPDIR_26="$(setup_migration_fixture)"
SCRIPT_DIR="$TMPDIR_26/local/.aitask-scripts"
mkdir -p "$SCRIPT_DIR"

shim_install cp:cp_into_aitasks
out_26=$(cd "$TMPDIR_26/local" && setup_data_branch </dev/null 2>&1)
shim_remove

assert_contains "26: cp's error is surfaced" "simulated copy failure" "$out_26"
assert_contains_ci "26: the failing directory is named" "copy aitasks/" "$out_26"
assert_contains_ci "26: the user is told nothing was removed" "nothing was removed" "$out_26"
assert_migration_originals_intact "26" "$TMPDIR_26/local"
# The teardown is also the identity guard's POSITIVE control: it proves the
# guard authorizes removal in the ordinary case rather than being stuck closed.
assert_dir_not_exists "26: partial worktree torn down so a re-run retries" "$TMPDIR_26/local/.aitask-data"

rm -rf "$TMPDIR_26"

# --- Test 26b: the aiplans copy is checked too ---
echo "--- Test 26b: failed aiplans cp also aborts the migration (t1631) ---"

# The aiplans copy is a separate statement with the same shape; a check on only
# the aitasks copy would leave half the migration silent.
TMPDIR_26B="$(setup_migration_fixture)"
SCRIPT_DIR="$TMPDIR_26B/local/.aitask-scripts"
mkdir -p "$SCRIPT_DIR"

shim_install cp:cp_into_aiplans
out_26b=$(cd "$TMPDIR_26B/local" && setup_data_branch </dev/null 2>&1)
shim_remove

assert_contains "26b: cp's error is surfaced" "simulated copy failure" "$out_26b"
assert_contains_ci "26b: the failing directory is named" "copy aiplans/" "$out_26b"
assert_migration_originals_intact "26b" "$TMPDIR_26B/local"
assert_dir_not_exists "26b: partial worktree torn down" "$TMPDIR_26B/local/.aitask-data"

rm -rf "$TMPDIR_26B"

# --- Test 27: a failed data-branch commit aborts before anything is deleted ---
echo "--- Test 27: failed commit aborts the migration and re-runs cleanly (t1631) ---"

# Copy equality is not durability. If the commit fails, the copied data exists
# only as staged files in a worktree this run created, while Step 5 is about to
# remove the tracked originals.
TMPDIR_27="$(setup_migration_fixture)"
SCRIPT_DIR="$TMPDIR_27/local/.aitask-scripts"
mkdir -p "$SCRIPT_DIR"

shim_install git:git_commit
out_27=$(cd "$TMPDIR_27/local" && setup_data_branch </dev/null 2>&1)
shim_remove

assert_contains_ci "27: the commit failure is surfaced" "could not commit the task data" "$out_27"
assert_migration_originals_intact "27" "$TMPDIR_27/local"
assert_dir_not_exists "27: partial worktree torn down" "$TMPDIR_27/local/.aitask-data"

# Absence of state is only half the claim: the point of tearing the worktree
# down is that `ait setup` can retry, and the "already configured" early return
# is what would silence it.
(cd "$TMPDIR_27/local" && setup_data_branch </dev/null >/dev/null 2>&1)
assert_file_exists "27: re-run creates a real worktree" "$TMPDIR_27/local/.aitask-data/.git"
assert_symlink "27: re-run creates the aitasks symlink" "$TMPDIR_27/local/aitasks"
committed_27=$(git -C "$TMPDIR_27/local/.aitask-data" show HEAD:aitasks/t1_test.md 2>/dev/null | grep -c "Test task content")
assert_eq_trim "27: re-run committed the migrated task" "1" "$committed_27"

rm -rf "$TMPDIR_27"

# --- Test 28: fresh setup, failed commit tears down before the symlinks ---
echo "--- Test 28: fresh-setup commit failure leaves no half-configured layout (t1631) ---"

# Nothing is deleted on this path, but "warn and continue" is still wrong: the
# symlinks would point at a worktree whose seeded contents are uncommitted, and
# the early return at the top of setup_data_branch would report that state as
# "already configured" forever after.
TMPDIR_28="$(setup_repo_with_remote)"
SCRIPT_DIR="$TMPDIR_28/local/.aitask-scripts"
mkdir -p "$SCRIPT_DIR"
setup_seed_file "$TMPDIR_28/local"

shim_install git:git_commit
out_28=$(cd "$TMPDIR_28/local" && setup_data_branch </dev/null 2>&1)
shim_remove

assert_contains_ci "28: the commit failure is surfaced" "could not commit the task data" "$out_28"
assert_dir_not_exists "28: partial worktree torn down" "$TMPDIR_28/local/.aitask-data"
assert_not_symlink "28: no aitasks symlink over an uncommitted worktree" "$TMPDIR_28/local/aitasks"
assert_not_symlink "28: no aiplans symlink over an uncommitted worktree" "$TMPDIR_28/local/aiplans"

(cd "$TMPDIR_28/local" && setup_data_branch </dev/null >/dev/null 2>&1)
assert_file_exists "28: re-run creates a real worktree" "$TMPDIR_28/local/.aitask-data/.git"
assert_symlink "28: re-run creates the aitasks symlink" "$TMPDIR_28/local/aitasks"
TOTAL=$((TOTAL + 1))
if git -C "$TMPDIR_28/local/.aitask-data" ls-tree HEAD -- aitasks/metadata/ 2>/dev/null | grep -q .; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: 28: re-run did not commit the seeded metadata"
fi

rm -rf "$TMPDIR_28"

# --- Tests 29 / 30: the identity guard refuses rather than removing blind ---
#
# The guard is what authorizes `git worktree remove --force` and its `rm -rf`
# fallback, so both of its branches need pinning — Test 26 covers "permits".
# 29 and 30 are deliberately distinct: one makes the command fail, the other
# lets it succeed with no matching entry, so a guard that merely checked for
# non-empty output could not pass both.

run_identity_guard_refusal_case() {
    local label="$1" git_matcher="$2" root
    local tmpdir
    tmpdir="$(setup_migration_fixture)"
    root="$tmpdir/local"
    SCRIPT_DIR="$root/.aitask-scripts"
    mkdir -p "$SCRIPT_DIR"

    shim_install cp:cp_into_aitasks "git:$git_matcher"
    local out
    out=$(cd "$root" && setup_data_branch </dev/null 2>&1)
    shim_remove

    assert_contains_ci "$label: the refusal is stated" "left '.aitask-data' in place" "$out"
    assert_contains_ci "$label: the consequence is stated" "already configured" "$out"
    assert_dir_exists "$label: the worktree is left untouched" "$root/.aitask-data"
    assert_file_exists "$label: its partial copy is left untouched" "$root/.aitask-data/aitasks/t1_test.md"
    # The no-delete guarantee does not depend on the teardown succeeding.
    assert_migration_originals_intact "$label" "$root"

    rm -rf "$tmpdir"
}

# --- Test 31: the pre-delete verification catches a copy that lied ---
echo "--- Test 31: copy verification refuses the delete on a silent partial copy (t1631) ---"

# cp reporting success is the primary guard; this is the last one, and it is the
# only guard that can catch a copy which returned 0 without writing everything.
# Nothing else in the fixture set reaches it, so without this test the check
# could be deleted and the suite would not notice.
TMPDIR_31="$(setup_migration_fixture)"
SCRIPT_DIR="$TMPDIR_31/local/.aitask-scripts"
mkdir -p "$SCRIPT_DIR"

shim_install cp:cp_partial_ok_aitasks
out_31=$(cd "$TMPDIR_31/local" && setup_data_branch </dev/null 2>&1)
shim_remove

assert_contains_ci "31: the verification failure is surfaced" "copy verification failed" "$out_31"
assert_contains_ci "31: diff's own output is quoted" "diff said" "$out_31"
assert_migration_originals_intact "31" "$TMPDIR_31/local"
assert_dir_not_exists "31: partial worktree torn down" "$TMPDIR_31/local/.aitask-data"

rm -rf "$TMPDIR_31"

# --- Test 32: a vanished data worktree never commits against the project root ---
echo "--- Test 32: Step 4 refuses when the data worktree disappeared (t1631) ---"

# Step 4's subshell is the left operand of `|| data_commit_rc=$?`, and bash
# disables errexit inside a compound command whose status is tested. An
# unguarded `cd` there would leave `git add .` and `git commit` running against
# the PROJECT ROOT, and the subshell would still report success — so Step 5
# would delete the originals having committed the wrong repository.
TMPDIR_32="$(setup_migration_fixture)"
SCRIPT_DIR="$TMPDIR_32/local/.aitask-scripts"
mkdir -p "$SCRIPT_DIR"
head_before_32=$(git -C "$TMPDIR_32/local" rev-parse HEAD)
# An unrelated dirty file is what makes the hazard visible rather than
# theoretical: `git add .` run from the wrong directory sweeps whatever the
# developer happens to have in progress into the data-branch commit.
echo "work in progress" > "$TMPDIR_32/local/stray_uncommitted.txt"

shim_install cp:cp_ok_then_drop_worktree
out_32=$(cd "$TMPDIR_32/local" && setup_data_branch </dev/null 2>&1)
shim_remove

assert_contains_ci "32: the commit failure is surfaced" "could not commit the task data" "$out_32"
head_after_32=$(git -C "$TMPDIR_32/local" rev-parse HEAD)
assert_eq_trim "32: nothing was committed to the project repository" "$head_before_32" "$head_after_32"
TOTAL=$((TOTAL + 1))
if git -C "$TMPDIR_32/local" log --oneline -20 2>/dev/null | grep -q "Migrate task data from main branch"; then
    FAIL=$((FAIL + 1))
    echo "FAIL: 32: the data-branch commit landed on the project's own branch"
else
    PASS=$((PASS + 1))
fi
TOTAL=$((TOTAL + 1))
if git -C "$TMPDIR_32/local" ls-files --error-unmatch stray_uncommitted.txt >/dev/null 2>&1; then
    FAIL=$((FAIL + 1))
    echo "FAIL: 32: an unrelated in-progress file was swept into a commit"
else
    PASS=$((PASS + 1))
fi
assert_migration_originals_intact "32" "$TMPDIR_32/local"

rm -rf "$TMPDIR_32"

echo "--- Test 29: identity guard refuses when 'worktree list' fails (t1631) ---"
run_identity_guard_refusal_case "29" "git_worktree_list_fail"

echo "--- Test 30: identity guard refuses when the path is not listed (t1631) ---"
run_identity_guard_refusal_case "30" "git_worktree_list_omit"

# --- Summary ---
echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
