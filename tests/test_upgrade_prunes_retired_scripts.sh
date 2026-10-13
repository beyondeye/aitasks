#!/usr/bin/env bash
# test_upgrade_prunes_retired_scripts.sh - Acceptance: a real upgrade of an old
# project removes the .aitask-scripts/ files the framework retired (t1926).
#
# Run: bash tests/test_upgrade_prunes_retired_scripts.sh
#
# `ait upgrade` downloads the TARGET release's install.sh and runs it with
# `--force --dir <project>` — so the prune executes from the new release's code
# even inside a project whose installed scripts predate it. This test drives that
# exact entry point, offline: this checkout's install.sh against a tarball built
# from this checkout the way release.yml builds one.
#
# Fixtures are throwaway git projects at a fixed old version — the v0.31.0 and
# v0.36.1 framework trees from `git archive <tag>`, plus every leftover the
# registry scan found in projects on that version, byte-exact from the last
# release that shipped each file. Each also carries one locally MODIFIED
# leftover and one USER-AUTHORED file under .aitask-scripts/.
#
# Sections:
#   W   setup main() wiring — prune runs after the dirty baseline, before commit
#   U   upgrade of each fixture: pruned + committed, modified kept, user file
#       untouched, board imports; a re-run is a no-op
#   S   `ait setup` on an already-current project that still carries leftovers
#   N   negative control: the same upgrade from a release WITHOUT the manifest
#       keeps board/task_yaml.py and the board fails — so U is not vacuous

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

PASS=0
FAIL=0
TOTAL=0

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# The framework venv carries textual; capture it BEFORE HOME is redirected.
VENV_PY="$HOME/.aitask/venv/bin/python"
if [[ ! -x "$VENV_PY" ]] || ! "$VENV_PY" -c 'import textual, yaml' 2>/dev/null; then
    VENV_PY=""
    echo "SKIP (board-import sub-asserts only): no framework venv with textual at ~/.aitask/venv"
fi

for tag in v0.31.0 v0.36.1; do
    if ! git -C "$PROJECT_DIR" rev-parse -q --verify "refs/tags/$tag" >/dev/null; then
        echo "SKIP: release tag $tag not available (shallow clone?)"
        exit 0
    fi
done

FAKE_HOME="$TMP/home"
mkdir -p "$FAKE_HOME"
TAB="$(printf '\t')"

# --- Release-style tarballs -------------------------------------------------
# Same top-level layout as release.yml's `tar -czf`: ait, CHANGELOG.md,
# .aitask-scripts/, packaging/, seed/, and skills/ built from .claude/skills.
# Tracked + untracked-not-ignored files, so this checkout's work is included and
# gitignored caches/renders are not.
build_tarball() {   # build_tarball <out.tar.gz> <with-manifest:1|0>
    local out="$1" with_manifest="$2" stage list
    stage="$TMP/stage_$with_manifest"
    list="$TMP/list_$with_manifest"
    rm -rf "$stage"; mkdir -p "$stage"
    (cd "$PROJECT_DIR" || exit 1; git ls-files -co --exclude-standard -- \
        ait CHANGELOG.md .aitask-scripts packaging seed .claude/skills \
        | while IFS= read -r f; do [[ -f "$f" ]] && printf '%s\n' "$f"; done) > "$list"
    (cd "$PROJECT_DIR" && tar -cf - -T "$list") | tar -xf - -C "$stage"
    mv "$stage/.claude/skills" "$stage/skills"
    rmdir "$stage/.claude"
    if [[ "$with_manifest" == 0 ]]; then
        rm -f "$stage/.aitask-scripts/retired_scripts_manifest.txt"
    fi
    (cd "$stage" && tar -czf "$out" ait CHANGELOG.md .aitask-scripts packaging seed skills)
}

TARBALL="$TMP/aitasks-test.tar.gz"
TARBALL_NOPRUNE="$TMP/aitasks-test-noprune.tar.gz"
build_tarball "$TARBALL" 1
build_tarball "$TARBALL_NOPRUNE" 0

# --- Fixtures -----------------------------------------------------------------
LEFTOVERS_036=(
    .aitask-scripts/aitask_codex_plan_invoke.py
    .aitask-scripts/board/task_yaml.py
    .aitask-scripts/lib/attachment_backend.sh
    .aitask-scripts/lib/attachment_backends/local.sh
    .aitask-scripts/lib/attachment_cache.sh
    .aitask-scripts/lib/attachment_utils.sh
    .aitask-scripts/lib/codex_plan_policy.sh
    .aitask-scripts/stats/stats_data.py
)
LEFTOVERS_031=(
    "${LEFTOVERS_036[@]}"
    .aitask-scripts/aitask_brainstorm_apply_detailer.sh
    .aitask-scripts/aitask_brainstorm_apply_patcher.sh
    .aitask-scripts/brainstorm/templates/detailer.md
    .aitask-scripts/brainstorm/templates/patcher.md
    .aitask-scripts/skill_templates/_detailer_rules.md
)
MODIFIED=.aitask-scripts/lib/codex_plan_policy.sh
USER_FILE=.aitask-scripts/my_tool.sh

# The last release tag whose tree ships <path>.
last_shipping_tag() {
    local path="$1" t last=""
    for t in $(git -C "$PROJECT_DIR" tag -l 'v*' | sort -V); do
        git -C "$PROJECT_DIR" cat-file -e "$t:$path" 2>/dev/null && last="$t"
    done
    printf '%s' "$last"
}

make_fixture() {   # make_fixture <dir> <tag> <leftover>...
    local dir="$1" tag="$2" p src
    shift 2
    rm -rf "$dir"; mkdir -p "$dir"
    git -C "$dir" init -q -b main
    git -C "$dir" config user.email test@example.com
    git -C "$dir" config user.name test
    git -C "$dir" config commit.gpgsign false
    local paths=(.aitask-scripts ait)
    git -C "$PROJECT_DIR" cat-file -e "$tag:.claude/skills" 2>/dev/null && paths+=(.claude/skills)
    git -C "$PROJECT_DIR" archive "$tag" -- "${paths[@]}" | tar -xf - -C "$dir"
    for p in "$@"; do
        src="$(last_shipping_tag "$p")"
        [[ -n "$src" ]] || { echo "FATAL: no release ships $p"; exit 1; }
        mkdir -p "$dir/$(dirname "$p")"
        git -C "$PROJECT_DIR" show "$src:$p" > "$dir/$p"
    done
    printf '# local tweak kept by the project\n' >> "$dir/$MODIFIED"
    printf '#!/usr/bin/env bash\necho "my own tool"\n' > "$dir/$USER_FILE"
    git -C "$dir" add -A
    git -C "$dir" commit -qm "fixture: aitasks $tag install with leftovers"
}

run_install() {   # run_install <fixture> <tarball>  -> combined output
    HOME="$FAKE_HOME" AITASKS_HOME="$TMP/aitasks_home" AIT_TESTMAP_FETCH=0 \
        bash "$PROJECT_DIR/install.sh" --force --dir "$1" --local-tarball "$2" </dev/null 2>&1
}

# board_import <fixture> -> "rc|stderr" ; imports aitask_board with board/ first.
board_import() {
    local err rc=0
    err="$(cd "$1" && "$VENV_PY" -c 'import sys; sys.path.insert(0, ".aitask-scripts/board"); import aitask_board' 2>&1 >/dev/null)" || rc=$?
    printf '%s|%s' "$rc" "$err"
}

tracked() { git -C "$1" ls-files --error-unmatch -- "$2" >/dev/null 2>&1 && echo yes || echo no; }

# ==============================================================================
echo "=== W: setup main() calls the prune after the baseline, before the commit ==="
# Every setup function stubbed (offline, prompt-free) except main and the
# loggers; the three under test echo their call. `set -u` stays ON so an unbound
# variable in main aborts the run instead of passing silently.
W_OUT="$(HOME="$FAKE_HOME" AITASKS_HOME="$TMP/w_home" T="$PROJECT_DIR" bash -c '
    source "$T/.aitask-scripts/aitask_setup.sh" --source-only
    set +e
    for fn in $(compgen -A function); do
        case "$fn" in main|info|success|warn|die) continue ;; esac
        eval "$fn() { return 0; }"
    done
    detect_os() { OS=linux; }   # the one stubbed step main reads a result from
    snapshot_pre_setup_dirty() { echo "CALL:snapshot"; }
    prune_retired_scripts()    { echo "CALL:prune:$(cd "$1" && pwd)"; }
    commit_framework_files()   { echo "CALL:commit"; }
    main
    echo "MAIN_RC:$?"' 2>&1)"
assert_contains "W main ran to completion under set -u" "MAIN_RC:0" "$W_OUT"
assert_contains "W prune_retired_scripts gets the project root" \
    "CALL:prune:$PROJECT_DIR" "$W_OUT"
n_snap="$(printf '%s\n' "$W_OUT" | grep -n '^CALL:snapshot' | head -1 | cut -d: -f1)"
n_prune="$(printf '%s\n' "$W_OUT" | grep -n '^CALL:prune' | head -1 | cut -d: -f1)"
n_commit="$(printf '%s\n' "$W_OUT" | grep -n '^CALL:commit' | head -1 | cut -d: -f1)"
assert_eq "W order: snapshot < prune < commit" "yes" \
    "$([[ -n "$n_snap" && -n "$n_prune" && -n "$n_commit" \
          && "$n_snap" -lt "$n_prune" && "$n_prune" -lt "$n_commit" ]] && echo yes || echo no)"

# ==============================================================================
upgrade_fixture() {   # upgrade_fixture <label> <tag> <leftover>...
    local label="$1" tag="$2" fx head0 head1 out log p rc err res
    shift 2
    fx="$TMP/fx_$label"
    echo ""
    echo "=== U[$label]: upgrade a $tag project carrying $# leftover(s) ==="
    make_fixture "$fx" "$tag" "$@"
    head0="$(git -C "$fx" rev-parse HEAD)"
    local user_sum mod_sum
    user_sum="$(git hash-object "$fx/$USER_FILE")"
    mod_sum="$(git hash-object "$fx/$MODIFIED")"

    out="$(run_install "$fx" "$TARBALL")"
    head1="$(git -C "$fx" rev-parse HEAD)"
    assert_eq "U[$label] install created a commit" "yes" "$([[ "$head0" != "$head1" ]] && echo yes || echo no)"
    log="$(git -C "$fx" log --name-status --format= "$head0..$head1")"

    for p in "$@"; do
        [[ "$p" == "$MODIFIED" ]] && continue
        assert_file_not_exists "U[$label] pruned from tree: $p" "$fx/$p"
        assert_eq "U[$label] no longer tracked: $p" "no" "$(tracked "$fx" "$p")"
        assert_contains "U[$label] deletion committed by install.sh: $p" "D${TAB}$p" "$log"
    done
    assert_eq "U[$label] .aitask-scripts/ clean after the upgrade commit" "" \
        "$(git -C "$fx" status --porcelain -- .aitask-scripts/)"

    assert_file_exists "U[$label] modified leftover kept" "$fx/$MODIFIED"
    assert_eq "U[$label] modified leftover byte-identical" "$mod_sum" "$(git hash-object "$fx/$MODIFIED")"
    assert_contains "U[$label] output names the kept file with a cleanup hint" \
        "rm -rf $MODIFIED" "$out"
    assert_eq "U[$label] user-authored file untouched" "$user_sum" "$(git hash-object "$fx/$USER_FILE")"
    assert_eq "U[$label] user-authored file still tracked" "yes" "$(tracked "$fx" "$USER_FILE")"

    if [[ -n "$VENV_PY" ]]; then
        res="$(board_import "$fx")"; rc="${res%%|*}"; err="${res#*|}"
        assert_eq "U[$label] board imports with board/ first (no ImportError)" "0" "$rc"
        [[ "$rc" == 0 ]] || printf '%s\n' "$err" | tail -5
    fi

    # Re-running the upgrade is a no-op: nothing pruned, no new commit.
    out="$(run_install "$fx" "$TARBALL")"
    assert_not_contains "U[$label] re-run prunes nothing" "retired script path(s):" "$out"
    assert_eq "U[$label] re-run makes no commit" "$head1" "$(git -C "$fx" rev-parse HEAD)"
    assert_contains "U[$label] re-run still reports the kept file" "rm -rf $MODIFIED" "$out"
}

upgrade_fixture v031 v0.31.0 "${LEFTOVERS_031[@]}"
upgrade_fixture v036 v0.36.1 "${LEFTOVERS_036[@]}"

# ==============================================================================
echo ""
echo "=== S: ait setup prunes an already-current project that still carries leftovers ==="
# `ait upgrade` stops with "Already up to date" on such a project, so setup's
# prune is what reaches it. Put the v0.36.1 leftovers back on the upgraded
# fixture, then run the real setup functions in main()'s order (W pins that
# main makes exactly this call sequence).
FX="$TMP/fx_v036"
PRE_UPGRADE="$(git -C "$FX" rev-list --max-parents=0 HEAD)"
PRISTINE=()
for p in "${LEFTOVERS_036[@]}"; do
    [[ "$p" == "$MODIFIED" ]] && continue
    PRISTINE+=("$p")
done
git -C "$FX" checkout -q "$PRE_UPGRADE" -- "${PRISTINE[@]}"
git -C "$FX" commit -qm "leftovers back on a current project" -- "${PRISTINE[@]}"
HEAD_S0="$(git -C "$FX" rev-parse HEAD)"

run_setup_prune() {
    (cd "$FX" && HOME="$FAKE_HOME" AITASKS_HOME="$TMP/aitasks_home" bash -c '
        source .aitask-scripts/aitask_setup.sh --source-only
        set +e
        snapshot_pre_setup_dirty
        prune_retired_scripts "$SCRIPT_DIR/.."
        commit_framework_files' </dev/null 2>&1)
}
S_OUT="$(run_setup_prune)"
HEAD_S1="$(git -C "$FX" rev-parse HEAD)"
assert_eq "S setup committed the prune" "yes" "$([[ "$HEAD_S0" != "$HEAD_S1" ]] && echo yes || echo no)"
S_LOG="$(git -C "$FX" log --name-status --format= "$HEAD_S0..$HEAD_S1")"
for p in "${PRISTINE[@]}"; do
    assert_file_not_exists "S pruned: $p" "$FX/$p"
    assert_contains "S deletion committed: $p" "D${TAB}$p" "$S_LOG"
done
assert_file_exists "S modified leftover still kept" "$FX/$MODIFIED"
assert_eq "S .aitask-scripts/ clean after setup" "" "$(git -C "$FX" status --porcelain -- .aitask-scripts/)"

S_OUT2="$(run_setup_prune)"
assert_not_contains "S re-run prunes nothing" "retired script path(s):" "$S_OUT2"
assert_eq "S re-run makes no commit" "$HEAD_S1" "$(git -C "$FX" rev-parse HEAD)"
: "$S_OUT"

# ==============================================================================
echo ""
echo "=== N: negative control — the same upgrade from a release without the manifest ==="
NFX="$TMP/fx_noprune"
make_fixture "$NFX" v0.36.1 "${LEFTOVERS_036[@]}"
run_install "$NFX" "$TARBALL_NOPRUNE" >/dev/null
assert_file_exists "N board/task_yaml.py survives without the prune" "$NFX/.aitask-scripts/board/task_yaml.py"
assert_eq "N ... and stays tracked" "yes" "$(tracked "$NFX" .aitask-scripts/board/task_yaml.py)"
if [[ -n "$VENV_PY" ]]; then
    # The fixture reproduces the defect: board/-first resolution finds the stale
    # copy, which lacks the name the current board imports.
    raw="$(cd "$NFX" && "$VENV_PY" -c 'import sys; sys.path[:0] = [".aitask-scripts/board", ".aitask-scripts/lib"]; from task_yaml import normalize_board_idx' 2>&1)"
    assert_contains "N stale copy reproduces the t1926 ImportError" \
        "cannot import name 'normalize_board_idx'" "$raw"
    res="$(board_import "$NFX")"; rc="${res%%|*}"; err="${res#*|}"
    assert_eq "N board fails to start" "1" "$rc"
    assert_contains "N ... with the guard naming the stale file" \
        ".aitask-scripts/board/task_yaml.py  shadows" "$err"
    assert_not_contains "N ... never an opaque ImportError" "ImportError" "$err"
fi

echo ""
echo "Tests: $TOTAL, Passed: $PASS, Failed: $FAIL"
[[ "$FAIL" -eq 0 ]] || exit 1
