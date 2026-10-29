#!/usr/bin/env bash
# test_projects_lock_released_on_die.sh - a `die` inside a locked section of
# `ait projects` must not leave the registry mutex behind (t2164).
#
# Several verbs die after registry_lock_or_die with no explicit release
# (update / group set / unset / rename on an unknown target, add and group sync
# on an invalid config slug). They rely on the EXIT trap registry_lock_acquire
# installs. Nothing else pins that: dropping the trap, or installing another
# `trap … EXIT` in aitask_projects.sh, would leave projects.yaml.lockd behind on
# every one of these exits. Inside cmd_doctor's `( cmd_update … )` subshell
# the lock records the doctor's own (live) pid, so a leak there is never
# stale-reclaimed: the doctor's next locked verb waits out its acquire timeout
# and dies.
#
# Run: bash tests/test_projects_lock_released_on_die.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"

# --- Setup --------------------------------------------------------------

TMPROOT=$(mktemp -d)
trap 'rm -rf "$TMPROOT"' EXIT

REGISTRY_FILE="$TMPROOT/projects.yaml"
LOCK_DIR="${REGISTRY_FILE}.lockd"
export AITASKS_PROJECTS_INDEX="$REGISTRY_FILE"

PROJECTS_SH="$PROJECT_DIR/.aitask-scripts/aitask_projects.sh"
PRISTINE="$TMPROOT/pristine.yaml"

make_project() {
    local root="$1" name="$2" group="${3:-}"
    mkdir -p "$root/aitasks/metadata"
    printf 'project:\n  name: %s\n' "$name" > "$root/aitasks/metadata/project_config.yaml"
    if [[ -n "$group" ]]; then
        printf '  project_group: %s\n' "$group" >> "$root/aitasks/metadata/project_config.yaml"
    fi
}

ALPHA_ROOT="$TMPROOT/projects/alpha"
BAD_ROOT="$TMPROOT/projects/bad"
make_project "$ALPHA_ROOT" alpha
make_project "$BAD_ROOT" bad 'BAD!'

# Write a registry holding the named entries (no names: an empty registry).
# `bad` is written with no project_group, so `group sync` reads its config.
write_registry() {
    rm -rf "$REGISTRY_FILE" "$LOCK_DIR"
    printf 'projects:\n' > "$REGISTRY_FILE"
    local entry
    for entry in "$@"; do
        case "$entry" in
            alpha)  printf '  - name: alpha\n    path: %s\n' "$ALPHA_ROOT" ;;
            bad)    printf '  - name: bad\n    path: %s\n' "$BAD_ROOT" ;;
            stale1) printf '  - name: stale1\n    path: %s\n' "$TMPROOT/gone/stale1" ;;
            stale2) printf '  - name: stale2\n    path: %s\n' "$TMPROOT/gone/stale2" ;;
        esac
    done >> "$REGISTRY_FILE"
}

# --- 1. Every die under the lock, standalone ------------------------------

# label|registry entries|expected message|verb args (space-separated)
# Paths appear as @ALPHA@ / @BAD@ and are substituted after the split, so a
# TMPDIR containing whitespace still reaches the verb as one argument.
CASES=(
    "update, empty registry||No registered projects.|update alpha @ALPHA@"
    "update, unknown name|alpha|Project 'ghost' is not registered.|update ghost @ALPHA@"
    "group set, unknown name|alpha|Project 'ghost' is not registered.|group set ghost g1"
    "group unset, unknown name|alpha|Project 'ghost' is not registered.|group unset ghost"
    "group rename, no member|alpha|No registered project has group 'nope'.|group rename nope g2"
    "add, invalid config slug|alpha|invalid project.project_group 'BAD!'|add @BAD@"
    "group sync, invalid config slug|alpha bad|invalid project.project_group 'BAD!'|group sync"
)

for spec in "${CASES[@]}"; do
    IFS='|' read -r label entries expected argline <<< "$spec"
    read -r -a entry_list <<< "$entries"
    read -r -a args <<< "$argline"
    for i in "${!args[@]}"; do
        case "${args[i]}" in
            @ALPHA@) args[i]="$ALPHA_ROOT" ;;
            @BAD@)   args[i]="$BAD_ROOT" ;;
        esac
    done
    write_registry "${entry_list[@]}"
    cp "$REGISTRY_FILE" "$PRISTINE"
    rc=0
    err=$("$PROJECTS_SH" "${args[@]}" 2>&1 >/dev/null) || rc=$?
    assert_exit_nonzero_rc "$label: exits non-zero" "$rc"
    # The message proves the run died at this die under the lock, not at an
    # earlier unlocked check.
    assert_contains "$label: dies with its locked-section message" "$expected" "$err"
    if cmp -s "$PRISTINE" "$REGISTRY_FILE"; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: $label: registry bytes changed"
    fi
    assert_dir_not_exists "$label: releases the registry lock" "$LOCK_DIR"
done

# --- 2. doctor: a locked die inside its ( cmd_update … ) subshell -----------

# Doctor reads the registry once, then walks the stale entries. Remove stale1
# from the registry while doctor waits at its "New path:" prompt, so the update
# it then runs dies under the lock with "not registered". The next entry is
# pruned in doctor's own shell: if the subshell leaked the lock (held by the
# live doctor pid), that acquire would time out and doctor would die.
write_registry alpha stale1 stale2
FIFO="$TMPROOT/doctor.fifo"
DOCTOR_OUT="$TMPROOT/doctor.out"
DOCTOR_ERR="$TMPROOT/doctor.err"
mkfifo "$FIFO"
"$PROJECTS_SH" doctor < "$FIFO" > "$DOCTOR_OUT" 2> "$DOCTOR_ERR" &
doctor_pid=$!
exec 3> "$FIFO"
printf 'u\n' >&3
prompt_seen=0
for _ in $(seq 1 100); do
    if grep -q "New path:" "$DOCTOR_ERR" 2>/dev/null; then
        prompt_seen=1
        break
    fi
    sleep 0.1
done
if [[ "$prompt_seen" -eq 1 ]]; then
    assert_record_pass
    write_registry alpha stale2
    printf '%s\np\n' "$ALPHA_ROOT" >&3
    exec 3>&-
    rc=0
    wait "$doctor_pid" || rc=$?
    doctor_err=$(cat "$DOCTOR_ERR")
    assert_eq "doctor: exits 0 after the in-subshell update dies" "0" "$rc"
    assert_contains "doctor: the update died under the lock" \
        "Project 'stale1' is not registered." "$doctor_err"
    assert_contains "doctor: reports the failed update and continues" \
        "Update failed - entry left as-is." "$doctor_err"
    assert_contains "doctor: the next locked verb acquires the lock" \
        "Removed stale2" "$(cat "$DOCTOR_OUT")"
    assert_not_contains "doctor: stale2 is gone from the registry" \
        "name: stale2" "$(cat "$REGISTRY_FILE")"
    assert_dir_not_exists "doctor: registry lock released" "$LOCK_DIR"
else
    assert_record_fail
    echo "FAIL: doctor never showed its New path: prompt within 10s"
    echo "  stderr: $(cat "$DOCTOR_ERR" 2>/dev/null)"
    exec 3>&-
    kill "$doctor_pid" 2>/dev/null || true
    wait "$doctor_pid" 2>/dev/null || true
fi

# --- 3. Positive control ----------------------------------------------------

# The same fixture reaches the locked section and writes on the success path.
write_registry alpha
rc=0
out=$("$PROJECTS_SH" group set alpha g1 2>&1) || rc=$?
assert_exit_zero_rc_out "control: group set on a registered name succeeds" "$rc" "$out"
assert_contains "control: the group is written" "project_group: g1" "$(cat "$REGISTRY_FILE")"
assert_dir_not_exists "control: registry lock released" "$LOCK_DIR"

# --- Summary ------------------------------------------------------------

echo
echo "===================="
echo "Passed: $PASS / $TOTAL"
[[ "$FAIL" -gt 0 ]] && echo "Failed: $FAIL"
echo "===================="
[[ "$FAIL" -eq 0 ]]
