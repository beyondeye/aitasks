#!/usr/bin/env bash
# test_install_upgrade_dirty_baseline.sh - install.sh / `ait upgrade` commits
# only what the upgrade changed, and repairs symlink-unsafe data entries (t1964).
#
# install.sh takes a dirty framework-path baseline before extraction
# (snapshot_pre_install_dirty) and its two commits subtract it, so a user's
# uncommitted work under a framework path is reported and left alone. An
# existing install also gets setup_data_gitignore_symlink_safe (t1711), whose
# .gitignore rewrite lands in the upgrade commit only when .gitignore was clean.
#
# Each case runs the real installer against a scratch project built from a
# release-style tarball of this checkout. INSTALL_SH points at another
# installer (e.g. the pre-fix one) to confirm the negative controls go red.
#
# Run: bash tests/test_install_upgrade_dirty_baseline.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Anchor a relative override before the cwd moves.
INSTALL_SH="${INSTALL_SH:-$PROJECT_DIR/install.sh}"
INSTALL_SH="$(cd "$(dirname "$INSTALL_SH")" && pwd)/$(basename "$INSTALL_SH")"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

PASS=0
FAIL=0
TOTAL=0

# Shared assertion helpers (see tests/lib/asserts.sh)
. "$PROJECT_DIR/tests/lib/asserts.sh"
# sed_inplace (BSD/GNU portable in-place sed)
. "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
FAKE_HOME="$TMP/home"
TAB="$(printf '\t')"
mkdir -p "$FAKE_HOME"

echo "=== install.sh upgrade: dirty baseline + symlink-safe .gitignore (t1964) ==="
echo "Installer: $INSTALL_SH"

# --- Release-style tarballs ---------------------------------------------------
# Same top-level layout as release.yml: ait, CHANGELOG.md, .aitask-scripts/,
# packaging/, seed/, and skills/ built from .claude/skills (tracked + untracked
# not-ignored files of this checkout). The "new" tarball bumps VERSION and
# changes `ait`, so the upgrade has real changes to commit.
NEW_VERSION="99.0.0-t1964test"
build_tarball() {   # build_tarball <out.tar.gz> <bump:1|0>
    local out="$1" bump="$2" stage="$TMP/stage_$2" list="$TMP/list_$2"
    rm -rf "$stage"; mkdir -p "$stage"
    git -C "$PROJECT_DIR" ls-files -co --exclude-standard -- \
        ait CHANGELOG.md .aitask-scripts packaging seed .claude/skills \
        | while IFS= read -r f; do [[ -f "$PROJECT_DIR/$f" ]] && printf '%s\n' "$f"; done > "$list"
    tar -C "$PROJECT_DIR" -cf - -T "$list" | tar -xf - -C "$stage"
    mv "$stage/.claude/skills" "$stage/skills"
    rmdir "$stage/.claude"
    if [[ "$bump" != 0 ]]; then
        printf '%s\n' "$NEW_VERSION" > "$stage/.aitask-scripts/VERSION"
        printf '# t1964 upgrade marker\n' >> "$stage/ait"
    fi
    if [[ "$bump" == predates ]]; then   # an aitask_setup.sh older than t1711's repair
        sed_inplace 's/^setup_data_gitignore_symlink_safe() {/_t1964_absent_repair() {/' \
            "$stage/.aitask-scripts/aitask_setup.sh"
        # Fail closed: a fixture edit that silently did nothing would make case H
        # assert against a setup that still has the repair.
        if grep -q '^setup_data_gitignore_symlink_safe() {' "$stage/.aitask-scripts/aitask_setup.sh"; then
            echo "FATAL: could not strip the repair from the predates fixture"; exit 1
        fi
    fi
    tar -C "$stage" -czf "$out" ait CHANGELOG.md .aitask-scripts packaging seed skills
}
TARBALL_OLD="$TMP/aitasks-old.tar.gz"
TARBALL_NEW="$TMP/aitasks-new.tar.gz"
build_tarball "$TARBALL_OLD" 0
build_tarball "$TARBALL_NEW" 1
TARBALL_PREDATES="$TMP/aitasks-predates.tar.gz"
build_tarball "$TARBALL_PREDATES" predates

# run_install <dir> <tarball> [--force] -> sets OUT and RC
# diff.renames=true is pinned through GIT_CONFIG_COUNT (above every config
# file): case R's negative control needs rename detection ON, and an inherited
# diff.renames=false would hide the source-omission it guards against.
run_install() {
    local dir="$1" tarball="$2"
    shift 2
    RC=0
    OUT="$(HOME="$FAKE_HOME" AITASKS_HOME="$TMP/aitasks_home" AIT_TESTMAP_FETCH=0 \
        GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=diff.renames GIT_CONFIG_VALUE_0=true \
        bash "$INSTALL_SH" "$@" --dir "$dir" --local-tarball "$tarball" </dev/null 2>&1)" || RC=$?
}

g() { git -C "$PROJECT_UNDER_TEST" "$@"; }
gcommit() { git -C "$1" -c user.email=t@t -c user.name=t -c commit.gpgsign=false commit -q "${@:2}"; }

new_repo() {   # new_repo <dir> -> git repo with one commit (README.md)
    rm -rf "$1"; mkdir -p "$1"
    git -C "$1" init -q -b main
    git -C "$1" config user.email t@t
    git -C "$1" config user.name t
    git -C "$1" config commit.gpgsign false
    echo "# project" > "$1/README.md"
    git -C "$1" add README.md
    gcommit "$1" -m "Initial commit"
}

# make_project <dir>: an existing install whose framework files are committed.
make_project() {
    new_repo "$1"
    run_install "$1" "$TARBALL_OLD"
    [[ "$RC" -eq 0 ]] || { echo "FATAL: first install failed in $1"; printf '%s\n' "$OUT"; exit 1; }
    git -C "$1" add -A
    gcommit "$1" -m "fixture: framework install"
    PROJECT_UNDER_TEST="$1"
}

upgrade() {   # upgrade the current PROJECT_UNDER_TEST to the new tarball
    HEAD_BEFORE="$(g rev-parse -q --verify HEAD || true)"
    run_install "$PROJECT_UNDER_TEST" "$TARBALL_NEW" --force
}

# Files in the commits the upgrade made (empty when it made none).
upgrade_commit_files() {
    if [[ -n "$HEAD_BEFORE" ]]; then
        g log --name-only --format= "$HEAD_BEFORE..HEAD" | sed '/^$/d' | sort -u
    else
        g log --all --name-only --format= 2>/dev/null | sed '/^$/d' | sort -u
    fi
}

has_line() { grep -qxF -- "$2" <<<"$1" && echo yes || echo no; }

LEGACY_GITIGNORE=$'node_modules/\n.aitask-data/\naitasks/\naiplans/'

# ==============================================================================
echo ""
echo "=== A: clean .gitignore with legacy lines is repaired and committed ==="
make_project "$TMP/A"
printf '%s\n' "$LEGACY_GITIGNORE" > "$TMP/A/.gitignore"
g add .gitignore; gcommit "$TMP/A" -m "legacy gitignore"
upgrade
assert_eq "A upgrade exits 0" "0" "$RC"
assert_eq "A disk has bare .aitask-data" "yes" "$(has_line "$(cat "$TMP/A/.gitignore")" ".aitask-data")"
assert_eq "A disk has bare aitasks" "yes" "$(has_line "$(cat "$TMP/A/.gitignore")" "aitasks")"
assert_eq "A HEAD .gitignore has bare .aitask-data" "yes" "$(has_line "$(g show HEAD:.gitignore)" ".aitask-data")"
assert_eq "A HEAD .gitignore lost .aitask-data/" "no" "$(has_line "$(g show HEAD:.gitignore)" ".aitask-data/")"
assert_eq "A .gitignore clean after upgrade" "" "$(g status --porcelain -- .gitignore)"
assert_eq "A upgrade commit carries .gitignore" "yes" "$(has_line "$(upgrade_commit_files)" ".gitignore")"
assert_eq "A upgrade commit carries VERSION" "yes" "$(has_line "$(upgrade_commit_files)" ".aitask-scripts/VERSION")"

# ==============================================================================
echo ""
echo "=== B: dirty .gitignore is repaired on disk but never committed ==="
make_project "$TMP/B"
printf '%s\n' "$LEGACY_GITIGNORE" > "$TMP/B/.gitignore"
g add .gitignore; gcommit "$TMP/B" -m "legacy gitignore"
echo "user-rule.log" >> "$TMP/B/.gitignore"
upgrade
assert_eq "B upgrade exits 0" "0" "$RC"
assert_eq "B disk has bare .aitask-data" "yes" "$(has_line "$(cat "$TMP/B/.gitignore")" ".aitask-data")"
assert_eq "B disk keeps the user rule" "yes" "$(has_line "$(cat "$TMP/B/.gitignore")" "user-rule.log")"
assert_eq "B HEAD .gitignore still legacy" "yes" "$(has_line "$(g show HEAD:.gitignore)" ".aitask-data/")"
assert_eq "B HEAD .gitignore lacks the user rule" "no" "$(has_line "$(g show HEAD:.gitignore)" "user-rule.log")"
assert_eq "B .gitignore still modified" " M .gitignore" "$(g status --porcelain -- .gitignore)"
assert_eq "B upgrade commit lacks .gitignore" "no" "$(has_line "$(upgrade_commit_files)" ".gitignore")"
assert_eq "B upgrade commit still carries VERSION" "yes" "$(has_line "$(upgrade_commit_files)" ".aitask-scripts/VERSION")"
assert_contains "B output reports the left-alone file" "left alone" "$OUT"
assert_contains "B ... naming .gitignore" "    .gitignore" "$OUT"

# ==============================================================================
# Regression control: the pre-fix installer listed only untracked + modified
# files, so staged-only work was already safe. This pins the new staged term.
echo ""
echo "=== C: staged foreign and staged framework-path files are never swept ==="
make_project "$TMP/C"
echo "staged readme edit" >> "$TMP/C/README.md"
mkdir -p "$TMP/C/.claude/skills/my_skill"
echo "# my skill" > "$TMP/C/.claude/skills/my_skill/SKILL.md"
g add README.md .claude/skills/my_skill/SKILL.md
upgrade
assert_eq "C upgrade exits 0" "0" "$RC"
assert_eq "C upgrade commit lacks README.md" "no" "$(has_line "$(upgrade_commit_files)" "README.md")"
assert_eq "C upgrade commit lacks the staged skill" "no" \
    "$(has_line "$(upgrade_commit_files)" ".claude/skills/my_skill/SKILL.md")"
assert_eq "C README.md still staged" "yes" "$(has_line "$(g diff --cached --name-only)" "README.md")"
assert_eq "C staged skill still staged" "yes" \
    "$(has_line "$(g diff --cached --name-only)" ".claude/skills/my_skill/SKILL.md")"
assert_eq "C upgrade commit carries VERSION" "yes" "$(has_line "$(upgrade_commit_files)" ".aitask-scripts/VERSION")"

# ==============================================================================
echo ""
echo "=== C2: an untracked custom skill is left alone ==="
make_project "$TMP/C2"
mkdir -p "$TMP/C2/.claude/skills/my_untracked_skill"
echo "# wip skill" > "$TMP/C2/.claude/skills/my_untracked_skill/SKILL.md"
upgrade
assert_eq "C2 upgrade exits 0" "0" "$RC"
assert_eq "C2 upgrade commit lacks the untracked skill" "no" \
    "$(has_line "$(upgrade_commit_files)" ".claude/skills/my_untracked_skill/SKILL.md")"
assert_eq "C2 skill still untracked" "?? .claude/skills/my_untracked_skill/" \
    "$(g status --porcelain -- .claude/skills/my_untracked_skill)"
assert_contains "C2 output names the left-alone skill" \
    ".claude/skills/my_untracked_skill/SKILL.md" "$OUT"

# ==============================================================================
# The include-absent case: `ait` does not exist when the snapshot runs, so an
# existence-filtered baseline would drop it and the recreated file would ride
# into the commit over the user's deletion.
echo ""
echo "=== D: an unstaged deletion of a top-level framework file is left alone ==="
make_project "$TMP/D"
rm "$TMP/D/ait"
upgrade
assert_eq "D upgrade exits 0" "0" "$RC"
assert_eq "D upgrade commit lacks ait" "no" "$(has_line "$(upgrade_commit_files)" "ait")"
assert_eq "D HEAD ait is the pre-upgrade one" "no" \
    "$(g show HEAD:ait | grep -qxF '# t1964 upgrade marker' && echo yes || echo no)"
assert_contains "D output names ait as left alone" "    ait" "$OUT"

# ==============================================================================
# A staged rename inside the framework paths: with rename detection the staged
# inventory lists only the destination, extraction recreates the source, and
# committing it would turn the pending rename into an addition.
echo ""
echo "=== R: a staged rename between framework paths is left alone ==="
make_project "$TMP/R"
RENAME_SRC=".aitask-scripts/aitask_ls.sh"
RENAME_DST=".aitask-scripts/aitask_ls_renamed_t1964.sh"
g mv "$RENAME_SRC" "$RENAME_DST"
upgrade
assert_eq "R upgrade exits 0" "0" "$RC"
assert_eq "R upgrade commit lacks the rename source" "no" "$(has_line "$(upgrade_commit_files)" "$RENAME_SRC")"
assert_eq "R upgrade commit lacks the rename destination" "no" "$(has_line "$(upgrade_commit_files)" "$RENAME_DST")"
R_STAGED="$(g diff --cached --name-status --no-renames)"
assert_eq "R source deletion still staged" "yes" "$(has_line "$R_STAGED" "D${TAB}$RENAME_SRC")"
assert_eq "R destination addition still staged" "yes" "$(has_line "$R_STAGED" "A${TAB}$RENAME_DST")"
assert_eq "R upgrade commit carries VERSION" "yes" "$(has_line "$(upgrade_commit_files)" ".aitask-scripts/VERSION")"

# ==============================================================================
# Installer behaviour only — no fixture commit between install and asserts.
echo ""
echo "=== E: fresh install does not auto-commit and runs no .gitignore repair ==="
new_repo "$TMP/E"
PROJECT_UNDER_TEST="$TMP/E"
run_install "$TMP/E" "$TARBALL_OLD"
assert_eq "E install exits 0" "0" "$RC"
assert_file_exists "E VERSION extracted" "$TMP/E/.aitask-scripts/VERSION"
assert_eq "E VERSION untracked" "no" \
    "$(g ls-files --error-unmatch -- .aitask-scripts/VERSION >/dev/null 2>&1 && echo yes || echo no)"
assert_eq "E no installer commit" "1" "$(g rev-list --count HEAD)"
assert_not_contains "E no .gitignore repair on a fresh install" "Checking .gitignore data entries" "$OUT"

# ==============================================================================
# Branch mode: aitasks/ and aiplans/ are symlinks into an .aitask-data worktree
# on an orphan aitask-data branch (same layout as test_t644_branch_mode_upgrade).
to_branch_mode() {   # to_branch_mode <dir>
    local d="$1" empty_tree branch_commit
    empty_tree="$(git -C "$d" mktree </dev/null)"
    branch_commit="$(echo "ait: Initialize aitask-data branch" \
        | git -C "$d" -c user.email=t@t -c user.name=t commit-tree "$empty_tree")"
    git -C "$d" update-ref refs/heads/aitask-data "$branch_commit"
    mv "$d/aitasks" "$TMP/staging_aitasks"
    git -C "$d" worktree add -q "$d/.aitask-data" aitask-data
    mkdir -p "$d/.aitask-data/aitasks" "$d/.aitask-data/aiplans"
    cp -a "$TMP/staging_aitasks/." "$d/.aitask-data/aitasks/"
    rm -rf "$TMP/staging_aitasks" "$d/aiplans"
    ln -s .aitask-data/aitasks "$d/aitasks"
    ln -s .aitask-data/aiplans "$d/aiplans"
    git -C "$d/.aitask-data" add aitasks
    gcommit "$d/.aitask-data" -m "ait: Migrate task data"
    git -C "$d" rm -r -q --cached aitasks aiplans 2>/dev/null || true
    printf '.aitask-data\n' >> "$d/.gitignore"
    git -C "$d" add -A
    gcommit "$d" -m "fixture: branch mode"
}

TYPE_EDIT="t1964_uncommitted_type"
branch_case() {   # branch_case <label> <untrack_version:1|0>
    local label="$1" untrack="$2" d="$TMP/$1" data_head_before
    echo ""
    if [[ "$untrack" == 1 ]]; then
        echo "=== $label: data baseline holds with VERSION untracked in the main repo ==="
    else
        echo "=== $label: branch-mode upgrade leaves dirty data-branch metadata alone ==="
    fi
    make_project "$d"
    to_branch_mode "$d"
    if [[ "$untrack" == 1 ]]; then
        git -C "$d" rm -q --cached .aitask-scripts/VERSION
        gcommit "$d" -m "fixture: stop tracking the framework"
    fi
    echo "$TYPE_EDIT" >> "$d/.aitask-data/aitasks/metadata/task_types.txt"
    data_head_before="$(git -C "$d/.aitask-data" rev-parse HEAD)"
    upgrade
    assert_eq "$label upgrade exits 0" "0" "$RC"
    assert_not_contains "$label no symlink pathspec error" "beyond a symbolic link" "$OUT"
    assert_eq "$label data commits lack task_types.txt" "no" \
        "$(has_line "$(git -C "$d/.aitask-data" log --name-only --format= "$data_head_before..HEAD")" \
            "aitasks/metadata/task_types.txt")"
    assert_eq "$label data HEAD task_types.txt lacks the edit" "no" \
        "$(git -C "$d/.aitask-data" show HEAD:aitasks/metadata/task_types.txt | grep -qxF "$TYPE_EDIT" && echo yes || echo no)"
    assert_eq "$label task_types.txt still modified" " M aitasks/metadata/task_types.txt" \
        "$(git -C "$d/.aitask-data" status --porcelain -- aitasks/metadata/task_types.txt)"
    if [[ "$untrack" == 1 ]]; then
        assert_contains "$label main commit skipped on the sentinel" "skipping auto-commit" "$OUT"
    else
        assert_eq "$label main upgrade commit carries VERSION" "yes" \
            "$(has_line "$(upgrade_commit_files)" ".aitask-scripts/VERSION")"
    fi
}
branch_case F 0
branch_case F2 1

# ==============================================================================
# install_errexit_edges: the snapshot's skip branches must not abort an
# installer that runs under `set -euo pipefail`.
echo ""
echo "=== G1: install into a non-git directory ==="
mkdir -p "$TMP/G1"
run_install "$TMP/G1" "$TARBALL_OLD"
assert_eq "G1 install exits 0" "0" "$RC"
assert_contains "G1 install completes" "aitasks installed successfully" "$OUT"

echo ""
echo "=== G2a: fresh install into a repository with no commit ==="
rm -rf "$TMP/G2a"; mkdir -p "$TMP/G2a"; git -C "$TMP/G2a" init -q -b main
run_install "$TMP/G2a" "$TARBALL_OLD"
assert_eq "G2a install exits 0" "0" "$RC"
assert_contains "G2a install completes" "aitasks installed successfully" "$OUT"

# Commit-eligible with no HEAD (VERSION staged): the snapshot must run under the
# committer's own predicate, or the repair rides in with the staged .gitignore.
echo ""
echo "=== G2b: no HEAD, VERSION staged, staged .gitignore with a legacy line ==="
D2="$TMP/G2b"
rm -rf "$D2"; mkdir -p "$D2"; git -C "$D2" init -q -b main
git -C "$D2" config user.email t@t; git -C "$D2" config user.name t
git -C "$D2" config commit.gpgsign false
PROJECT_UNDER_TEST="$D2"
run_install "$D2" "$TARBALL_OLD"
g add .aitask-scripts/VERSION
printf '.aitask-data/\nuser-rule.log\n' > "$D2/.gitignore"
g add .gitignore
upgrade
assert_eq "G2b upgrade exits 0" "0" "$RC"
assert_contains "G2b upgrade completes" "aitasks installed successfully" "$OUT"
assert_eq "G2b no installer commit carries .gitignore" "no" "$(has_line "$(upgrade_commit_files)" ".gitignore")"
assert_eq "G2b index .gitignore keeps the user rule" "yes" "$(has_line "$(g show :.gitignore)" "user-rule.log")"
assert_eq "G2b index .gitignore keeps the legacy line" "yes" "$(has_line "$(g show :.gitignore)" ".aitask-data/")"
assert_eq "G2b disk .gitignore repaired" "yes" "$(has_line "$(cat "$D2/.gitignore")" ".aitask-data")"
# Everything was untracked before this upgrade, so the left-alone list runs to
# hundreds of entries and .gitignore sits past its 20-line display cut.
assert_contains "G2b output reports left-alone files" "left alone" "$OUT"

# ==============================================================================
# `install.sh --version <older>` pairs this installer with a tarball whose
# aitask_setup.sh predates the repair; an unknown command under errexit would
# abort after extraction, before the commit.
echo ""
echo "=== H: a tarball whose setup predates the repair still upgrades and commits ==="
make_project "$TMP/H"
printf '%s\n' "$LEGACY_GITIGNORE" > "$TMP/H/.gitignore"
g add .gitignore; gcommit "$TMP/H" -m "legacy gitignore"
HEAD_BEFORE="$(g rev-parse HEAD)"
run_install "$TMP/H" "$TARBALL_PREDATES" --force
assert_eq "H upgrade exits 0" "0" "$RC"
assert_contains "H upgrade completes" "aitasks installed successfully" "$OUT"
assert_eq "H upgrade commit carries VERSION" "yes" "$(has_line "$(upgrade_commit_files)" ".aitask-scripts/VERSION")"
assert_eq "H .gitignore untouched" "yes" "$(has_line "$(cat "$TMP/H/.gitignore")" ".aitask-data/")"

# ==============================================================================
# framework_path_list_parity: install.sh's copy of the framework path list
# must match setup's, minus the entries only setup commits.
echo ""
echo "=== P: install.sh and setup framework path lists agree ==="
PARITY="$(
    # shellcheck source=/dev/null
    source "$INSTALL_SH" --source-only
    install_list="$(_install_framework_paths "$TMP" 1 | sort)"
    # shellcheck source=/dev/null
    source "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" --source-only
    setup_list="$(_ait_framework_paths "$TMP" 1 \
        | grep -vxF -e install.sh -e .gitlab-ci.yml -e bitbucket-pipelines.yml | sort)"
    if [[ -n "$install_list" && "$install_list" == "$setup_list" ]]; then
        echo same
    else
        echo different
        diff <(printf '%s\n' "$install_list") <(printf '%s\n' "$setup_list")
    fi
)"
assert_eq "P path lists agree" "same" "$PARITY"

echo ""
echo "Tests: $TOTAL, Passed: $PASS, Failed: $FAIL"
[[ "$FAIL" -eq 0 ]] || exit 1
