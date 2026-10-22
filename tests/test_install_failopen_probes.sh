#!/usr/bin/env bash
# test_install_failopen_probes.sh - install.sh's twin of rows A9 and A9b of the
# fail-open git-probe sweep (t2116): the pre-install dirty baseline must read a
# failed git probe as "unverified", never as "clean".
#
# install.sh cannot source the setup helpers, so it carries its own copy of the
# machinery tests/test_setup_failopen_probes.sh pins for aitask_setup.sh. Rule,
# fix shape and dispositions: aidocs/framework/failopen_git_probes.md.
#
# Every fail-closed case below has:
#   - an argv-keyed git shim that fails exactly ONE probe shape and logs that it
#     fired (a shim that never fires makes a green test vacuous);
#   - an asserted fixture precondition: without the shim the baseline names the
#     foreign work, so the failed probe is the only variable;
#   - a probe-only mutant (an eval'd `declare -f` edit, inside a subshell that
#     only prints observations) under which the defect is observed.
#
# INSTALL_SH points at another installer (e.g. a `git archive` export of the
# pre-fix one) to confirm the fail-closed cases go red.
#
# Run: bash tests/test_install_failopen_probes.sh

TEST_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_SCRIPT_DIR/.." && pwd)"
# Anchor a relative override before the cwd moves.
INSTALL_SH="${INSTALL_SH:-$PROJECT_DIR/install.sh}"
INSTALL_SH="$(cd "$(dirname "$INSTALL_SH")" && pwd)/$(basename "$INSTALL_SH")"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

PASS=0
FAIL=0
TOTAL=0

. "$PROJECT_DIR/tests/lib/asserts.sh"

# shellcheck source=../install.sh
source "$INSTALL_SH" --source-only
# Disable strict mode from sourced script — tests need to handle errors explicitly
set +euo pipefail

echo "=== install.sh fail-open probe tests (t2116) ==="
echo "Installer: $INSTALL_SH"
echo ""

SCRATCH="$(mktemp -d)"
trap 'rm -rf "$SCRATCH"' EXIT

# --- git shim -----------------------------------------------------------------
REAL_GIT="$(command -v git)"
SHIM_BIN="$SCRATCH/shim"
SHIM_LOG="$SCRATCH/shim.log"
export REAL_GIT SHIM_LOG
mkdir -p "$SHIM_BIN"
cat > "$SHIM_BIN/git" <<'SHIMEOF'
#!/usr/bin/env bash
# Fails (exit 128) only when the joined argv matches $SHIM_FAIL; logs each hit.
args="$*"
if [[ -n "${SHIM_FAIL:-}" && "$args" =~ $SHIM_FAIL ]]; then
    printf '%s\n' "$args" >> "$SHIM_LOG"
    echo "fatal: shim-injected failure" >&2
    exit 128
fi
exec "$REAL_GIT" "$@"
SHIMEOF
chmod +x "$SHIM_BIN/git"

# with_shim <ere> <cmd...> — run <cmd> IN-PROCESS (it sets globals) with the shim
# first on PATH. Assigning PATH clears bash's command hash, so `git` re-resolves.
with_shim() {
    local ere="$1"; shift
    local saved_path="$PATH" rc=0
    : > "$SHIM_LOG"
    export SHIM_FAIL="$ere"
    PATH="$SHIM_BIN:$PATH"
    "$@" || rc=$?
    PATH="$saved_path"
    unset SHIM_FAIL
    return "$rc"
}
shim_fired() { [[ -s "$SHIM_LOG" ]] && echo yes || echo no; }

# --- fixtures -----------------------------------------------------------------
# A here-string, not `printf | grep -q`: no writer to SIGPIPE under pipefail (t2056).
has_line() { grep -qxF -- "$2" <<<"$1" && echo yes || echo no; }
commit_count() { git -C "$1" rev-list --count HEAD 2>/dev/null; }
head_files() { git -C "$1" show --name-only --format='' HEAD 2>/dev/null; }
git_ident() { git config user.email t@t.com && git config user.name T && git config commit.gpgsign false; }
rc_of() { local rc=0; "$@" || rc=$?; echo "$rc"; }

# Fake project at <dir>, framework files written but nothing committed.
write_project_files() {
    local d="$1"
    mkdir -p "$d/.aitask-scripts" "$d/aitasks/metadata" "$d/.claude/skills"
    echo "#!/bin/bash" > "$d/ait"
    echo "0.2.0" > "$d/.aitask-scripts/VERSION"
    echo "# placeholder" > "$d/.aitask-scripts/placeholder.sh"
    echo "# staged victim" > "$d/.aitask-scripts/staged.sh"
    echo "# placeholder" > "$d/aitasks/metadata/placeholder.txt"
}

# Committed project, VERSION tracked (an existing install being upgraded).
new_project() {
    local d; d="$(mktemp -d "$SCRATCH/proj.XXXXXX")"
    write_project_files "$d"
    (cd "$d" && git init -q && git_ident && git add -A && git commit -qm init)
    echo "$d"
}

# Repository with only a readme committed: VERSION untracked (the project does
# not track the framework, so install never commits it).
new_untracked_project() {
    local d; d="$(mktemp -d "$SCRATCH/untr.XXXXXX")"
    write_project_files "$d"
    (cd "$d" && git init -q && git_ident && echo init > readme.txt && git add readme.txt \
        && git commit -qm init)
    echo "$d"
}

# Foreign work present before the snapshot: an unstaged edit, a fully STAGED
# edit (visible only to the `diff --cached` term) and a new untracked file.
add_foreign_work() {
    local d="$1"
    echo "concurrent edit" >> "$d/.aitask-scripts/placeholder.sh"
    echo "staged edit" >> "$d/.aitask-scripts/staged.sh"
    git -C "$d" add .aitask-scripts/staged.sh
    echo "# foreign" > "$d/.aitask-scripts/foreign_untracked.sh"
}

# A standalone data worktree stand-in with a foreign unstaged metadata edit.
add_data_repo() {
    local d="$1"
    mkdir -p "$d/.aitask-data/aitasks/metadata" "$d/.aitask-data/aireviewguides"
    (cd "$d/.aitask-data" && git init -q && git_ident \
        && echo "cfg" > aitasks/metadata/tracked.txt && echo "guide" > aireviewguides/g.md \
        && git add -A && git commit -qm init)
    echo "concurrent edit" >> "$d/.aitask-data/aitasks/metadata/tracked.txt"
}

# The sourced install functions read these globals.
# shellcheck disable=SC2034
reset_baseline_globals() {
    AIT_INSTALL_BASELINE_ARMED=0
    AIT_INSTALL_BASELINE_UNVERIFIED=0
    AIT_INSTALL_DATA_BASELINE_UNVERIFIED=0
    AIT_INSTALL_DIRTY_BASELINE=""
    AIT_INSTALL_DATA_DIRTY_BASELINE=""
}

# --- probe-only mutants (call inside a subshell) ------------------------------
# A9: restore `|| true` on the three list probes. Only the probe regresses — the
# rest of the helper must survive, or a control would observe "no helper".
mutate_list_probe() {
    local src; src="$(declare -f _install_list_changes)"
    eval "${src//probe_rc=1/true}"
    local now; now="$(declare -f _install_list_changes)"
    [[ "$now" != *"probe_rc=1"* ]] || return 1
    [[ "$now" == *"--no-renames"* && "$now" == *"diff --cached"* \
        && "$now" == *"grep -Ev"* && "$now" == *"return 2"* ]] || return 1
}
# A9b: conflate "git error" with "untracked", the old `&>/dev/null` shape.
mutate_version_probe() {
    local src; src="$(declare -f _install_version_tracked)"
    eval "${src//return 2/return 1}"
    local now; now="$(declare -f _install_version_tracked)"
    [[ "$now" != *"return 2"* ]] || return 1
    [[ "$now" == *"--error-unmatch"* && "$now" == *"return 0"* ]] || return 1
}

V_PLACE=".aitask-scripts/placeholder.sh"
V_STAGED=".aitask-scripts/staged.sh"
V_UNTR=".aitask-scripts/foreign_untracked.sh"
NEW_FILE=".aitask-scripts/newly_installed.sh"
DATA_EDIT="aitasks/metadata/tracked.txt"
DATA_NEW="aitasks/metadata/new_config.yaml"

# --- P: precondition — without the shim, protection works ---------------------
echo "--- P: unshimmed baseline names all foreign work ---"
d="$(new_project)"; add_foreign_work "$d"
INSTALL_DIR="$d"
snapshot_pre_install_dirty
for v in "$V_PLACE" "$V_STAGED" "$V_UNTR"; do
    assert_eq "P: baseline names $v" "yes" "$(has_line "$AIT_INSTALL_DIRTY_BASELINE" "$v")"
done
assert_eq "P: main baseline verified" "0" "$AIT_INSTALL_BASELINE_UNVERIFIED"
assert_eq "P: data baseline verified" "0" "$AIT_INSTALL_DATA_BASELINE_UNVERIFIED"
echo "# new helper" > "$d/$NEW_FILE"
commit_installed_files </dev/null >/dev/null 2>&1
assert_eq "P: commit is exactly the upgrade's own file" "$NEW_FILE" "$(head_files "$d")"
reset_baseline_globals

# --- 1: a failed snapshot list probe refuses the main commit ------------------
declare -a PROBES=("ls-files --others" "ls-files --modified" "diff --cached")
declare -a VICTIMS=("$V_UNTR" "$V_PLACE" "$V_STAGED")
for i in 0 1 2; do
    probe="${PROBES[$i]}"; victim="${VICTIMS[$i]}"
    echo "--- 1.$i: snapshot shim fails '$probe' -> main commit refused ---"
    d="$(new_project)"; add_foreign_work "$d"
    INSTALL_DIR="$d"
    before="$(commit_count "$d")"
    with_shim "$probe" snapshot_pre_install_dirty
    assert_eq "1.$i: shim fired" "yes" "$(shim_fired)"
    assert_eq "1.$i: main baseline flagged unverified" "1" "$AIT_INSTALL_BASELINE_UNVERIFIED"
    echo "# new helper" > "$d/$NEW_FILE"
    output="$(commit_installed_files 2>&1 </dev/null)"
    assert_contains "1.$i: refusal says nothing was committed" "NOT committed" "$output"
    assert_eq "1.$i: no commit made" "$before" "$(commit_count "$d")"
    status="$(git -C "$d" status --porcelain)"
    assert_eq "1.$i: unstaged edit still unstaged" "yes" "$(has_line "$status" " M $V_PLACE")"
    assert_eq "1.$i: staged edit still staged" "yes" "$(has_line "$status" "M  $V_STAGED")"
    assert_eq "1.$i: untracked file still untracked" "yes" "$(has_line "$status" "?? $V_UNTR")"
    reset_baseline_globals

    # Negative control: the probe-only mutant sweeps the probe's victim.
    d="$(new_project)"; add_foreign_work "$d"
    INSTALL_DIR="$d"
    obs="$(
        mutate_list_probe || { echo "MUTATION_FAILED"; exit 0; }
        with_shim "$probe" snapshot_pre_install_dirty
        echo "fired=$(shim_fired)"
        echo "# new helper" > "$d/$NEW_FILE"
        commit_installed_files </dev/null >/dev/null 2>&1
        head_files "$d"
    )"
    assert_not_contains "1.$i-n: mutant built" "MUTATION_FAILED" "$obs"
    assert_contains "1.$i-n: shim fired under the mutant" "fired=yes" "$obs"
    assert_eq "1.$i-n: mutant sweeps $victim into the upgrade commit" "yes" "$(has_line "$obs" "$victim")"
    reset_baseline_globals
done

# --- 2: a failed list probe at commit time is a refusal, not a false success ---
echo "--- 2: commit-time list probe fails -> refused, no 'already committed' ---"
d="$(new_project)"; add_foreign_work "$d"
INSTALL_DIR="$d"
snapshot_pre_install_dirty
assert_eq "2: snapshot verified" "0" "$AIT_INSTALL_BASELINE_UNVERIFIED"
before="$(commit_count "$d")"
echo "# new helper" > "$d/$NEW_FILE"
output="$(with_shim "ls-files --others" commit_installed_files 2>&1 </dev/null)"
assert_eq "2: shim fired" "yes" "$(shim_fired)"
assert_contains "2: refusal says nothing was committed" "NOT committed" "$output"
assert_not_contains_ci "2: no false 'already committed' success" "already committed" "$output"
assert_contains "2: refusal names a path-scoped commit" "git commit -- <path>" "$output"
assert_eq "2: no commit made" "$before" "$(commit_count "$d")"
assert_eq "2: the upgrade's file left untracked" "?? $NEW_FILE" \
    "$(git -C "$d" status --porcelain -- "$NEW_FILE")"
reset_baseline_globals

# Control: the fail-open list hides the upgrade's file and reports success.
d="$(new_project)"; add_foreign_work "$d"
INSTALL_DIR="$d"
obs="$(
    mutate_list_probe || { echo "MUTATION_FAILED"; exit 0; }
    snapshot_pre_install_dirty
    echo "# new helper" > "$d/$NEW_FILE"
    with_shim "ls-files --others" commit_installed_files 2>&1 </dev/null
    echo "fired=$(shim_fired)"
)"
assert_not_contains "2-n: mutant built" "MUTATION_FAILED" "$obs"
assert_contains "2-n: shim fired under the mutant" "fired=yes" "$obs"
assert_not_contains "2-n: mutant does not refuse" "NOT committed" "$obs"
reset_baseline_globals

# --- 2d: the data committer's own list probe -----------------------------------
# Failing `ls-files --others` hides the upgrade's new untracked metadata file;
# the foreign edit is subtracted by the (verified) baseline, so the fail-open
# shape returns silently with the update uncommitted.
echo "--- 2d: data commit-time list probe fails -> refused, not a silent no-op ---"
d="$(new_project)"; add_data_repo "$d"
INSTALL_DIR="$d"
snapshot_pre_install_dirty
assert_eq "2d: data snapshot verified" "0" "$AIT_INSTALL_DATA_BASELINE_UNVERIFIED"
assert_eq "2d: precondition — data baseline names the edit" "yes" \
    "$(has_line "$AIT_INSTALL_DATA_DIRTY_BASELINE" "$DATA_EDIT")"
data_before="$(commit_count "$d/.aitask-data")"
index_before="$(git -C "$d/.aitask-data" diff --cached --name-status)"
echo "new" > "$d/.aitask-data/$DATA_NEW"
output="$(with_shim '\.aitask-data ls-files --others' commit_installed_data_files 2>&1 </dev/null)"
assert_eq "2d: shim fired" "yes" "$(shim_fired)"
assert_contains "2d: refusal says nothing was committed" "NOT committed" "$output"
assert_eq "2d: no data commit made" "$data_before" "$(commit_count "$d/.aitask-data")"
assert_eq "2d: data index unchanged" "$index_before" "$(git -C "$d/.aitask-data" diff --cached --name-status)"
assert_eq "2d: the upgrade's metadata file left untracked" "?? $DATA_NEW" \
    "$(git -C "$d/.aitask-data" status --porcelain -- "$DATA_NEW")"
reset_baseline_globals

d="$(new_project)"; add_data_repo "$d"
INSTALL_DIR="$d"
obs="$(
    mutate_list_probe || { echo "MUTATION_FAILED"; exit 0; }
    snapshot_pre_install_dirty
    echo "new" > "$d/.aitask-data/$DATA_NEW"
    with_shim '\.aitask-data ls-files --others' commit_installed_data_files 2>&1 </dev/null
    echo "fired=$(shim_fired)"
    echo "data_commits=$(commit_count "$d/.aitask-data")"
)"
assert_not_contains "2d-n: mutant built" "MUTATION_FAILED" "$obs"
assert_contains "2d-n: shim fired under the mutant" "fired=yes" "$obs"
assert_not_contains "2d-n: mutant returns without a refusal" "NOT committed" "$obs"
assert_contains "2d-n: mutant commits nothing (silent no-op)" "data_commits=1" "$obs"
reset_baseline_globals

# --- 3: data twin — the data flag is independent of the main one ---------------
echo "--- 3: data snapshot probe fails -> data commit refused, main unaffected ---"
d="$(new_project)"; add_data_repo "$d"
INSTALL_DIR="$d"
snapshot_pre_install_dirty
assert_eq "3: precondition — unshimmed data baseline names the edit" "yes" \
    "$(has_line "$AIT_INSTALL_DATA_DIRTY_BASELINE" "$DATA_EDIT")"
reset_baseline_globals
data_before="$(commit_count "$d/.aitask-data")"
with_shim '\.aitask-data ls-files --modified' snapshot_pre_install_dirty
assert_eq "3: shim fired" "yes" "$(shim_fired)"
assert_eq "3: data baseline flagged unverified" "1" "$AIT_INSTALL_DATA_BASELINE_UNVERIFIED"
assert_eq "3: main baseline NOT flagged" "0" "$AIT_INSTALL_BASELINE_UNVERIFIED"
echo "new" > "$d/.aitask-data/$DATA_NEW"
output="$(commit_installed_data_files 2>&1 </dev/null)"
assert_contains "3: data refusal says nothing was committed" "NOT committed" "$output"
assert_eq "3: no data commit made" "$data_before" "$(commit_count "$d/.aitask-data")"
assert_eq "3: data edit still modified" " M $DATA_EDIT" \
    "$(git -C "$d/.aitask-data" status --porcelain -- "$DATA_EDIT")"
echo "# new helper" > "$d/$NEW_FILE"
commit_installed_files </dev/null >/dev/null 2>&1
assert_eq "3: main upgrade commit still happens" "$NEW_FILE" "$(head_files "$d")"
reset_baseline_globals

d="$(new_project)"; add_data_repo "$d"
INSTALL_DIR="$d"
obs="$(
    mutate_list_probe || { echo "MUTATION_FAILED"; exit 0; }
    with_shim '\.aitask-data ls-files --modified' snapshot_pre_install_dirty
    echo "fired=$(shim_fired)"
    echo "new" > "$d/.aitask-data/$DATA_NEW"
    commit_installed_data_files </dev/null >/dev/null 2>&1
    head_files "$d/.aitask-data"
)"
assert_not_contains "3-n: mutant built" "MUTATION_FAILED" "$obs"
assert_contains "3-n: shim fired under the mutant" "fired=yes" "$obs"
assert_eq "3-n: mutant sweeps the data edit" "yes" "$(has_line "$obs" "$DATA_EDIT")"
reset_baseline_globals

# --- 4: A9b — a failed VERSION probe during the snapshot -----------------------
# The shim is active during the snapshot only: git has recovered by commit time,
# which is exactly when the old shape swept (skipped baseline, eligible commit).
echo "--- 4: snapshot VERSION probe returns 128 -> main refused, data baseline captured ---"
d="$(new_project)"; add_foreign_work "$d"; add_data_repo "$d"
INSTALL_DIR="$d"
before="$(commit_count "$d")"
with_shim "ls-files --error-unmatch" snapshot_pre_install_dirty
assert_eq "4: shim fired" "yes" "$(shim_fired)"
assert_eq "4: main baseline flagged unverified" "1" "$AIT_INSTALL_BASELINE_UNVERIFIED"
assert_eq "4: data baseline NOT flagged (independence)" "0" "$AIT_INSTALL_DATA_BASELINE_UNVERIFIED"
assert_eq "4: data baseline still captured" "yes" \
    "$(has_line "$AIT_INSTALL_DATA_DIRTY_BASELINE" "$DATA_EDIT")"
echo "# new helper" > "$d/$NEW_FILE"
output="$(commit_installed_files 2>&1 </dev/null)"
assert_contains "4: refusal says nothing was committed" "NOT committed" "$output"
assert_eq "4: no main commit made" "$before" "$(commit_count "$d")"
status="$(git -C "$d" status --porcelain)"
assert_eq "4: unstaged edit intact" "yes" "$(has_line "$status" " M $V_PLACE")"
assert_eq "4: staged edit still staged" "yes" "$(has_line "$status" "M  $V_STAGED")"
echo "new" > "$d/.aitask-data/$DATA_NEW"
commit_installed_data_files </dev/null >/dev/null 2>&1
data_head="$(head_files "$d/.aitask-data")"
assert_eq "4: data commit carries the upgrade's file" "yes" "$(has_line "$data_head" "$DATA_NEW")"
assert_eq "4: data commit leaves the foreign edit" "no" "$(has_line "$data_head" "$DATA_EDIT")"
reset_baseline_globals

d="$(new_project)"; add_foreign_work "$d"
INSTALL_DIR="$d"
obs="$(
    mutate_version_probe || { echo "MUTATION_FAILED"; exit 0; }
    with_shim "ls-files --error-unmatch" snapshot_pre_install_dirty
    echo "fired=$(shim_fired)"
    echo "# new helper" > "$d/$NEW_FILE"
    commit_installed_files </dev/null >/dev/null 2>&1
    head_files "$d"
)"
assert_not_contains "4-n: mutant built" "MUTATION_FAILED" "$obs"
assert_contains "4-n: shim fired under the mutant" "fired=yes" "$obs"
assert_eq "4-n: mutant skips the baseline and sweeps the unstaged edit" "yes" "$(has_line "$obs" "$V_PLACE")"
reset_baseline_globals

# --- 4c: a failed VERSION probe at commit time names the real reason -----------
echo "--- 4c: commit-time VERSION probe returns 128 -> refusal, not 'not git-tracked' ---"
d="$(new_project)"; add_foreign_work "$d"
INSTALL_DIR="$d"
snapshot_pre_install_dirty
assert_eq "4c: snapshot verified" "0" "$AIT_INSTALL_BASELINE_UNVERIFIED"
before="$(commit_count "$d")"
echo "# new helper" > "$d/$NEW_FILE"
output="$(with_shim "ls-files --error-unmatch" commit_installed_files 2>&1 </dev/null)"
assert_eq "4c: shim fired" "yes" "$(shim_fired)"
assert_contains "4c: refusal says nothing was committed" "NOT committed" "$output"
assert_not_contains "4c: does not claim VERSION is untracked" "not git-tracked" "$output"
assert_eq "4c: no commit made" "$before" "$(commit_count "$d")"
reset_baseline_globals

# --- 5: A9b permit — the rc split, and an untracked framework is unchanged ------
echo "--- 5: _install_version_tracked rc split; untracked VERSION still skips ---"
d="$(new_untracked_project)"
assert_eq "5: untracked VERSION -> 1" "1" "$(rc_of _install_version_tracked "$d")"
d2="$(new_project)"
assert_eq "5: tracked VERSION -> 0" "0" "$(rc_of _install_version_tracked "$d2")"
norepo="$(mktemp -d "$SCRATCH/norepo.XXXXXX")"
assert_eq "5: not a repository -> 2" "2" \
    "$(GIT_CEILING_DIRECTORIES="$SCRATCH" rc_of _install_version_tracked "$norepo")"
assert_eq "5: shimmed git error -> 2" "2" \
    "$(with_shim "ls-files --error-unmatch" rc_of _install_version_tracked "$d2")"

# A real (unshimmed) failure: a corrupt index still passes rev-parse, but every
# index read exits 128 — the snapshot must flag it, not call it clean.
d3="$(new_project)"
echo garbage > "$d3/.git/index"
assert_eq "5: corrupt index -> 2" "2" "$(rc_of _install_version_tracked "$d3")"
INSTALL_DIR="$d3"
snapshot_pre_install_dirty
assert_eq "5: corrupt index flags the main baseline" "1" "$AIT_INSTALL_BASELINE_UNVERIFIED"
reset_baseline_globals

INSTALL_DIR="$d"
before="$(commit_count "$d")"
snapshot_pre_install_dirty
assert_eq "5: untracked framework is not unverified" "0" "$AIT_INSTALL_BASELINE_UNVERIFIED"
echo "# new helper" > "$d/$NEW_FILE"
output="$(commit_installed_files 2>&1 </dev/null)"
assert_contains "5: untracked framework still skips the commit" "not git-tracked" "$output"
assert_not_contains "5: no refusal for an untracked framework" "NOT committed" "$output"
assert_eq "5: no commit made" "$before" "$(commit_count "$d")"
reset_baseline_globals

# --- 7a: data rev-parse gate ----------------------------------------------------
echo "--- 7a: data worktree rev-parse fails -> data baseline unverified ---"
d="$(new_project)"; add_data_repo "$d"
INSTALL_DIR="$d"
data_before="$(commit_count "$d/.aitask-data")"
with_shim '\.aitask-data rev-parse --is-inside-work-tree' snapshot_pre_install_dirty
assert_eq "7a: shim fired" "yes" "$(shim_fired)"
assert_eq "7a: data baseline flagged unverified" "1" "$AIT_INSTALL_DATA_BASELINE_UNVERIFIED"
assert_eq "7a: main baseline NOT flagged" "0" "$AIT_INSTALL_BASELINE_UNVERIFIED"
echo "new" > "$d/.aitask-data/$DATA_NEW"
output="$(commit_installed_data_files 2>&1 </dev/null)"
assert_contains "7a: data refusal says nothing was committed" "NOT committed" "$output"
assert_eq "7a: no data commit made" "$data_before" "$(commit_count "$d/.aitask-data")"
assert_eq "7a: data edit still modified" " M $DATA_EDIT" \
    "$(git -C "$d/.aitask-data" status --porcelain -- "$DATA_EDIT")"
reset_baseline_globals

# --- 7b: main rev-parse gate, nested installation -------------------------------
# --dir may name a subdirectory of an ancestor repository: no local .git, so the
# flag must not be keyed on one.
echo "--- 7b: nested install, main rev-parse fails transiently -> refused ---"
nested_fixture() {
    local r; r="$(mktemp -d "$SCRATCH/nested.XXXXXX")"
    write_project_files "$r/sub"
    (cd "$r" && git init -q && git_ident && git add -A && git commit -qm init)
    echo "concurrent edit" >> "$r/sub/$V_PLACE"
    echo "$r"
}
r="$(nested_fixture)"
INSTALL_DIR="$r/sub"
assert_eq "7b: precondition — no local .git in the install dir" "no" \
    "$([[ -e "$r/sub/.git" ]] && echo yes || echo no)"
assert_eq "7b: precondition — git resolves the ancestor repo" "true" \
    "$(git -C "$r/sub" rev-parse --is-inside-work-tree 2>/dev/null)"
assert_eq "7b: precondition — VERSION tracked" "0" "$(rc_of _install_version_tracked "$r/sub")"
snapshot_pre_install_dirty
assert_eq "7b: precondition — unshimmed baseline names the edit" "yes" \
    "$(has_line "$AIT_INSTALL_DIRTY_BASELINE" "$V_PLACE")"
reset_baseline_globals
before="$(commit_count "$r")"
with_shim "rev-parse --is-inside-work-tree" snapshot_pre_install_dirty
assert_eq "7b: shim fired" "yes" "$(shim_fired)"
assert_eq "7b: main baseline flagged unverified" "1" "$AIT_INSTALL_BASELINE_UNVERIFIED"
echo "# new helper" > "$r/sub/$NEW_FILE"
output="$(commit_installed_files 2>&1 </dev/null)"   # git has recovered
assert_contains "7b: refusal says nothing was committed" "NOT committed" "$output"
assert_eq "7b: no commit made" "$before" "$(commit_count "$r")"
assert_eq "7b: foreign edit still unstaged" "yes" \
    "$(has_line "$(git -C "$r" status --porcelain)" " M sub/$V_PLACE")"
reset_baseline_globals

# 7n: control — the same failed snapshot with the flag cleared (the pre-fix
# state) sweeps the edit once git recovers, so the flag is what protects it.
r="$(nested_fixture)"
INSTALL_DIR="$r/sub"
with_shim "rev-parse --is-inside-work-tree" snapshot_pre_install_dirty
assert_eq "7n: shim fired" "yes" "$(shim_fired)"
AIT_INSTALL_BASELINE_UNVERIFIED=0
echo "# new helper" > "$r/sub/$NEW_FILE"
commit_installed_files </dev/null >/dev/null 2>&1
assert_eq "7n: without the flag the foreign edit is swept" "yes" \
    "$(has_line "$(head_files "$r")" "sub/$V_PLACE")"
reset_baseline_globals

# --- E: the refusal paths survive install.sh's own strict mode -----------------
# install.sh runs under `set -euo pipefail` (curl | bash): a refusal branch that
# tripped errexit would abort an upgrade after extraction, before the commit.
#
# Every call here is DIRECT: with_shim runs its command as `"$@" || rc=$?`, and
# bash suspends errexit for the whole function called from a `||` list, so a
# snapshot run through it would never meet effective `set -e`. The shim is
# installed inline instead. Call inside a subshell.
strict_mode_run() {   # strict_mode_run <dir> — prints observations, then REACHED
    set -euo pipefail
    local saved_path="$PATH"
    # shellcheck disable=SC2034  # read by the sourced install functions
    INSTALL_DIR="$1"
    : > "$SHIM_LOG"
    export SHIM_FAIL="ls-files --modified"
    PATH="$SHIM_BIN:$PATH"
    snapshot_pre_install_dirty
    PATH="$saved_path"
    unset SHIM_FAIL
    echo "fired=$(shim_fired)"
    echo "main_flag=$AIT_INSTALL_BASELINE_UNVERIFIED data_flag=$AIT_INSTALL_DATA_BASELINE_UNVERIFIED"
    echo "# new helper" > "$1/$NEW_FILE"
    commit_installed_files </dev/null
    commit_installed_data_files </dev/null
    echo "REACHED"
}
# Control: an unguarded status test on the failure path, which errexit must stop.
mutate_unguarded_main_rc() {
    local src; src="$(declare -f snapshot_pre_install_dirty)"
    eval "${src//"(( main_rc == 0 )) || AIT_INSTALL_BASELINE_UNVERIFIED=1"/"(( main_rc == 0 )); AIT_INSTALL_BASELINE_UNVERIFIED=1"}"
    local now; now="$(declare -f snapshot_pre_install_dirty)"
    [[ "$now" == *"(( main_rc == 0 ));"* ]] || return 1
    [[ "$now" == *"_install_list_changes"* && "$now" == *"_install_version_tracked"* ]] || return 1
}

echo "--- E: snapshot + both refusals under set -euo pipefail ---"
d="$(new_project)"; add_foreign_work "$d"; add_data_repo "$d"
obs="$( strict_mode_run "$d" 2>&1 )"
assert_contains "E: shim fired" "fired=yes" "$obs"
assert_contains "E: both baselines flagged" "main_flag=1 data_flag=1" "$obs"
assert_contains "E: refusals ran" "NOT committed" "$obs"
assert_contains "E: strict mode reaches the end" "REACHED" "$obs"
reset_baseline_globals

d="$(new_project)"; add_foreign_work "$d"; add_data_repo "$d"
obs="$(
    mutate_unguarded_main_rc || { echo "MUTATION_FAILED"; exit 0; }
    strict_mode_run "$d" 2>&1
)"
assert_not_contains "E-n: mutant built" "MUTATION_FAILED" "$obs"
# The run dies before printing fired=; the shim log on disk still records it.
assert_eq "E-n: shim fired under the mutant" "yes" "$(shim_fired)"
assert_not_contains "E-n: errexit stops the unguarded snapshot" "REACHED" "$obs"
reset_baseline_globals

# --- S: every consumer of the changed helpers has a recorded disposition -------
echo "--- S: helper call sites equal the disposition table ---"
# One `file::function::helper<TAB>tagged|untagged` row per CALL site: definition
# lines and comment lines excluded, function spans tracked via `name() {` / `}`.
# A call is "tagged" only when the comment block DIRECTLY above it carries
# `unverified:`, so a second call cannot borrow the first one's tag. Copied from
# tests/test_setup_failopen_probes.sh (S). The tag's TEXT is not checked against
# the code under it — every consumer's unverified branch is driven live above.
CALLSITE_AWK='
BEGIN { n = split(HELPERS, HL, " ") }
{
    s = $0; sub(/^[ \t]+/, "", s)
    if (s ~ /^#/) { cblock = cblock " " s; next }
    if ($0 ~ /^[A-Za-z_][A-Za-z0-9_]*\(\) *\{/) {
        fn = $0; sub(/\(\).*/, "", fn); cblock = ""; next
    }
    if ($0 ~ /^\} *$/) { fn = ""; cblock = ""; next }
    for (i = 1; i <= n; i++)
        if (index($0, HL[i]) > 0)
            printf "%s::%s::%s\t%s\n", REL, (fn == "" ? "<toplevel>" : fn), HL[i], \
                (cblock ~ /unverified:/ ? "tagged" : "untagged")
    cblock = ""
}'
HELPERS="_install_list_changes _install_version_tracked"
callsites() {
    awk -v HELPERS="$HELPERS" -v REL="$(basename "$1")" "$CALLSITE_AWK" "$1" | LC_ALL=C sort
}

# The scanner can fail: a second call borrowing a tag, a top-level call, and a
# comment that merely NAMES a helper must each be classified correctly.
SELFS="$(mktemp -d "$SCRATCH/selfs.XXXXXX")"
cat > "$SELFS/x.sh" <<'SELFEOF'
f_one() {
    # unverified: only the first call carries this
    _install_list_changes
    _install_list_changes
}
# a comment naming _install_version_tracked is not a call
_install_version_tracked
SELFEOF
assert_eq "S: scanner self-test (attribution and per-site tags)" \
    "$(printf 'x.sh::<toplevel>::_install_version_tracked\tuntagged\nx.sh::f_one::_install_list_changes\ttagged\nx.sh::f_one::_install_list_changes\tuntagged\n' | LC_ALL=C sort)" \
    "$(callsites "$SELFS/x.sh")"

rowsS="$(callsites "$INSTALL_SH")"
expectedS="$(printf '%s\n' \
    'install.sh::commit_installed_data_files::_install_list_changes' \
    'install.sh::commit_installed_files::_install_list_changes' \
    'install.sh::commit_installed_files::_install_version_tracked' \
    'install.sh::snapshot_pre_install_dirty::_install_list_changes' \
    'install.sh::snapshot_pre_install_dirty::_install_list_changes' \
    'install.sh::snapshot_pre_install_dirty::_install_version_tracked' \
    | LC_ALL=C sort)"
idsS="$(printf '%s\n' "$rowsS" | cut -f1)"
assert_eq "S: call-site identities equal the disposition table" "$expectedS" "$idsS"
if [[ "$idsS" != "$expectedS" ]]; then
    echo "  -> a consumer of $HELPERS changed in install.sh."
    echo "     Give it an explicit disposition for 'unverified' (see"
    echo "     aidocs/framework/failopen_git_probes.md rows A9/A9b), then update this table."
fi
# A scan that finds nothing must fail, not pass: pin the count and the definitions.
assert_eq "S: exactly six call sites" "6" "$(printf '%s\n' "$rowsS" | grep -c .)"
for defn in '_install_list_changes() {' '_install_version_tracked() {'; do
    assert_eq "S: $defn is defined once in install.sh" "1" "$(grep -cF "$defn" "$INSTALL_SH")"
done
assert_eq "S: every call site carries its own unverified: tag" "" \
    "$(printf '%s\n' "$rowsS" | grep -F "$(printf '\tuntagged')" || true)"
# The boolean wrapper that hid rc 2 behind `&&` must not come back.
assert_eq "S: _install_commit_eligible is gone" "0" "$(grep -c '_install_commit_eligible' "$INSTALL_SH")"
# aitask_setup.sh names the install helpers in comments only (its own twin).
assert_eq "S: no framework script calls the install helpers" "" \
    "$(grep -rnE '_install_list_changes|_install_version_tracked' "$PROJECT_DIR/.aitask-scripts" \
        | grep -vE '^[^:]+:[0-9]+:[[:space:]]*#' || true)"
assert_eq "S: the VERSION probe is spelled once, inside the helper" "1" \
    "$(grep -cF -- '--error-unmatch -- .aitask-scripts/VERSION' "$INSTALL_SH")"

reset_baseline_globals

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
