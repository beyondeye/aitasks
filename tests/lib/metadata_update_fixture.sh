#!/usr/bin/env bash
# metadata_update_fixture.sh — shared fixtures for the metadata-update scripts
# (aitask_usage_update.sh / aitask_verified_update.sh) and the convergence seam
# they drive (task_data_converge).
#
# This is a SHARED lib rather than a per-file helper on purpose: t1658_2 reuses
# `setup_branch_mode_metadata_repo` for its non-root-cwd entry-point tests. Do
# not inline either function back into a single test file.
#
# Requires, from the sourcing test file:
#   PROJECT_DIR                  repo root
#   setup_fake_aitask_repo       from tests/lib/test_scaffold.sh
#
# Every setup_* helper echoes the fixture's directory; the caller removes it.

# --- Shared building blocks -------------------------------------------------

# _mdfix_populate <repo_dir> <script_basename>
# Lay down the script under test, the libs it sources, an `ait` shim and a
# seeded models file.
_mdfix_populate() {
    local repo_dir="$1" script="$2"

    mkdir -p "$repo_dir/aitasks/metadata"
    setup_fake_aitask_repo "$repo_dir"

    cp "$PROJECT_DIR/.aitask-scripts/$script" "$repo_dir/.aitask-scripts/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" "$repo_dir/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" "$repo_dir/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/verified_update_lib.sh" "$repo_dir/.aitask-scripts/lib/"
    chmod +x "$repo_dir/.aitask-scripts/$script"

    _mdfix_write_ait_shim "$repo_dir"
    _mdfix_write_models "$repo_dir/aitasks/metadata/models_claudecode.json"
}

# _mdfix_write_ait_shim <repo_dir> [data_worktree]
# In legacy mode `ait git` passes straight through. In branch mode it must
# route to the data worktree, exactly as the real dispatcher does.
_mdfix_write_ait_shim() {
    local repo_dir="$1" data_wt="${2:-}"

    if [[ -z "$data_wt" ]]; then
        cat > "$repo_dir/ait" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
case "${1:-}" in
    git) shift; exec git "$@" ;;
    *)   echo "unsupported test helper command" >&2; exit 1 ;;
esac
EOF
    else
        cat > "$repo_dir/ait" <<EOF
#!/usr/bin/env bash
set -euo pipefail
case "\${1:-}" in
    git) shift; exec git -C "$data_wt" "\$@" ;;
    *)   echo "unsupported test helper command" >&2; exit 1 ;;
esac
EOF
    fi
    chmod +x "$repo_dir/ait"
}

_mdfix_write_models() {
    cat > "$1" <<'EOF'
{
  "models": [
    {
      "name": "opus4_6",
      "cli_id": "claude-opus-4-6",
      "notes": "Test model",
      "verified": {
        "pick": 80,
        "explain": 60,
        "batch-review": 0
      }
    }
  ]
}
EOF
}

# --- Concurrent-writer hooks (t1928) -----------------------------------------
# Scripts for AIT_CAS_BEFORE_SWAP_HOOK (lib/registry_cas.sh). The hook runs
# after the writer rendered its update from a snapshot and before the swap, so
# whatever it writes is a write the updater did NOT see when it read the
# registry — the stale-writer ordering. AIT_CAS_DEST names the registry.

# mdfix_write_refresh_hook <hook_path>
# Attempt 1 only: what an OpenCode-style refresh swapping in looks like —
# regenerated notes on the target row plus a newly discovered row.
mdfix_write_refresh_hook() {
    cat > "$1" <<'EOF'
if [[ "$AIT_CAS_ATTEMPT" == 1 ]]; then
    jq '(.models[] | select(.name == "opus4_6")).notes = "Refreshed by discovery"
        | .models += [{"name": "opus4_7", "cli_id": "claude-opus-4-7", "notes": "New", "verified": {}}]' \
        "$AIT_CAS_DEST" > "$AIT_CAS_DEST.hook" && mv "$AIT_CAS_DEST.hook" "$AIT_CAS_DEST"
fi
EOF
}

# mdfix_write_rename_hook <hook_path> <copy_path>
# Attempt 1 only: a refresh that renamed the target row (it matches rows by
# cli_id, so the name can change under a writer). Saves the registry it left
# behind to <copy_path> for a byte comparison.
mdfix_write_rename_hook() {
    cat > "$1" <<EOF
if [[ "\$AIT_CAS_ATTEMPT" == 1 ]]; then
    jq '(.models[] | select(.name == "opus4_6")).name = "opus4_6_renamed"' \\
        "\$AIT_CAS_DEST" > "\$AIT_CAS_DEST.hook" && mv "\$AIT_CAS_DEST.hook" "\$AIT_CAS_DEST"
    cp "\$AIT_CAS_DEST" "$2"
fi
EOF
}

# --- Legacy mode: no remote ------------------------------------------------

# setup_local_metadata_repo <script_basename>
# Echoes <repo_dir>: a legacy-mode checkout with NO remote, so an update
# commits locally and can never push anywhere. Use it whenever a test only
# needs the script's local behaviour — never run a metadata updater against
# the real repository, which records and pushes a real score (t1937).
setup_local_metadata_repo() {
    local script="$1"
    local repo_dir
    repo_dir="$(mktemp -d)"
    (
        cd "$repo_dir" || exit 1
        git init --quiet
        git config user.email "test@test.com"
        git config user.name "Test"
        _mdfix_populate "$repo_dir" "$script"
        git add .
        git commit -m "Initial setup" --quiet
    )

    echo "$repo_dir"
}

# --- Legacy mode: origin + work clone ---------------------------------------

# setup_remote_metadata_repo <script_basename>
# Echoes <basedir>; the working checkout is <basedir>/work and the bare origin
# is <basedir>/origin.git. Task data lives on the code branch (legacy mode).
setup_remote_metadata_repo() {
    local script="$1"
    local basedir origin_dir seed_dir work_dir
    basedir="$(mktemp -d)"
    origin_dir="$basedir/origin.git"
    seed_dir="$basedir/seed"
    work_dir="$basedir/work"

    git init --bare --quiet "$origin_dir"
    mkdir -p "$seed_dir"
    (
        cd "$seed_dir" || exit 1
        git init --quiet
        git config user.email "test@test.com"
        git config user.name "Test"
        _mdfix_populate "$seed_dir" "$script"
        git add .
        git commit -m "Initial setup" --quiet
        git branch -M main
        git remote add origin "$origin_dir"
        git push --quiet -u origin main
    )

    git --git-dir="$origin_dir" symbolic-ref HEAD refs/heads/main
    git clone --quiet --branch main "$origin_dir" "$work_dir" >/dev/null 2>&1
    (
        cd "$work_dir" || exit 1
        git config user.email "test@test.com"
        git config user.name "Test"
    )

    echo "$basedir"
}

# --- Branch mode: a real .aitask-data worktree ------------------------------

# setup_branch_mode_metadata_repo <script_basename>
# Echoes <basedir>. <basedir>/work is a CODE checkout that carries a real
# `.aitask-data` worktree on an orphan data branch, with `aitasks/` and
# `aiplans/` as symlinks into it — the shape production actually runs in. The
# legacy-mode fixture above cannot surface a mode-specific defect in the
# converge seam, because in legacy mode _ait_data_git is plain `git`.
setup_branch_mode_metadata_repo() {
    local script="$1"
    local basedir data_origin_dir data_seed work_dir
    basedir="$(mktemp -d)"
    data_origin_dir="$basedir/data-origin.git"
    data_seed="$basedir/data-seed"
    work_dir="$basedir/work"

    # 1. A bare origin holding ONLY the data branch, plus a seed that populates
    #    it. The data branch is the one the metadata scripts push to.
    git init --bare --quiet "$data_origin_dir"
    mkdir -p "$data_seed/aitasks/metadata" "$data_seed/aiplans"
    _mdfix_write_models "$data_seed/aitasks/metadata/models_claudecode.json"
    : > "$data_seed/aiplans/.keep"
    (
        cd "$data_seed" || exit 1
        git init --quiet
        git config user.email "test@test.com"
        git config user.name "Test"
        git add .
        git commit -m "Seed task data" --quiet
        git branch -M aitask-data
        git remote add origin "$data_origin_dir"
        git push --quiet -u origin aitask-data
    )

    # 2. The code checkout, carrying the scripts under test.
    mkdir -p "$work_dir"
    (
        cd "$work_dir" || exit 1
        git init --quiet
        git config user.email "test@test.com"
        git config user.name "Test"
    )
    setup_fake_aitask_repo "$work_dir"
    cp "$PROJECT_DIR/.aitask-scripts/$script" "$work_dir/.aitask-scripts/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" "$work_dir/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" "$work_dir/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/verified_update_lib.sh" "$work_dir/.aitask-scripts/lib/"
    chmod +x "$work_dir/.aitask-scripts/$script"
    (
        cd "$work_dir" || exit 1
        echo code > code.txt
        git add code.txt .aitask-scripts
        git commit -m "code branch" --quiet
    )

    # 3. Clone the data branch INTO .aitask-data, then symlink aitasks/ and
    #    aiplans/ at the root — the layout ait_ensure_data_symlinks produces.
    git clone --quiet --branch aitask-data "$data_origin_dir" "$work_dir/.aitask-data" >/dev/null 2>&1
    (
        cd "$work_dir/.aitask-data" || exit 1
        git config user.email "test@test.com"
        git config user.name "Test"
    )
    ln -s .aitask-data/aitasks "$work_dir/aitasks"
    ln -s .aitask-data/aiplans "$work_dir/aiplans"
    printf '.aitask-data/\naitasks\naiplans\n' > "$work_dir/.gitignore"

    # 4. `ait git` must route to the data worktree, as the real dispatcher does.
    _mdfix_write_ait_shim "$work_dir" ".aitask-data"

    echo "$basedir"
}
