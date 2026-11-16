#!/usr/bin/env bash
# metadata_update_fixture.sh — shared fixtures for the counter writers
# (aitask_usage_update.sh / aitask_verified_update.sh).
#
# The writers record into the `aitask-stats` plumbing branch through
# aitask_model_stats.py (lib/model_stats_store.py) and only READ the model
# registry, to check that the model exists (t1912_4). A fixture therefore lays
# down the writer, its shell libs, the stats CLI and its Python closure, plus a
# seeded registry. Assertions read the counters back through `mdfix_export` (the
# CLI's effective view: registry counters + branch, the way every reader sees
# them), never from the registry file.
#
# Requires, from the sourcing test file:
#   PROJECT_DIR                  repo root
#   setup_fake_aitask_repo       from tests/lib/test_scaffold.sh
#   copy_lib_py_closure          from tests/lib/test_scaffold.sh
#
# Every setup_* helper echoes the fixture's directory; the caller removes it.
# Never run a counter writer against the real repository: it records and pushes
# a real count (t1937).

# --- Shared building blocks -------------------------------------------------

# _mdfix_populate <repo_dir> <script_basename>
# Lay down the script under test, the libs it sources, the stats CLI with its
# Python closure, an `ait` shim and a seeded models file.
_mdfix_populate() {
    local repo_dir="$1" script="$2"

    mkdir -p "$repo_dir/aitasks/metadata"
    setup_fake_aitask_repo "$repo_dir"

    cp "$PROJECT_DIR/.aitask-scripts/$script" "$repo_dir/.aitask-scripts/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" "$repo_dir/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" "$repo_dir/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/verified_update_lib.sh" "$repo_dir/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_model_stats.py" "$repo_dir/.aitask-scripts/"
    copy_lib_py_closure "$repo_dir" model_stats_store
    chmod +x "$repo_dir/.aitask-scripts/$script"

    cat > "$repo_dir/ait" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
case "${1:-}" in
    git) shift; exec git "$@" ;;
    *)   echo "unsupported test helper command" >&2; exit 1 ;;
esac
EOF
    chmod +x "$repo_dir/ait"
    _mdfix_write_models "$repo_dir/aitasks/metadata/models_claudecode.json"
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

# --- Reading the result -------------------------------------------------------

# mdfix_export <repo_dir> [agent] — the effective counters as JSON
# ({"schema":1,"models":{...}}), read through the stats CLI. Never fetches.
mdfix_export() {
    local repo_dir="$1" agent="${2:-claudecode}"
    python3 "$repo_dir/.aitask-scripts/aitask_model_stats.py" export \
        --root "$repo_dir" --agent "$agent"
}

# mdfix_stat <repo_dir> <jq path under .models.opus4_6> — one counter value.
mdfix_stat() {
    mdfix_export "$1" | jq -r ".models.opus4_6$2"
}

# mdfix_registry_sha <repo_dir> — the registry file's bytes, hashed; a writer
# run must leave it unchanged.
mdfix_registry_sha() {
    sha256sum "$1/aitasks/metadata/models_claudecode.json" | cut -d' ' -f1
}

# --- No remote ----------------------------------------------------------------

# setup_local_metadata_repo <script_basename>
# Echoes <repo_dir>: a checkout with NO remote, so the store commits to the
# local refs/heads/aitask-stats only and can never push anywhere.
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

# --- origin + work clone --------------------------------------------------------

# setup_remote_stats_repo <script_basename>
# Echoes <basedir>; the working checkout is <basedir>/work and the bare origin
# is <basedir>/origin.git, so the store takes its leased-push path and the
# write lands on origin's refs/heads/aitask-stats.
setup_remote_stats_repo() {
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
