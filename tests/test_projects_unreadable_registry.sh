#!/usr/bin/env bash
# test_projects_unreadable_registry.sh - every `ait projects` verb must refuse
# an unreadable registry instead of rebuilding it from an empty read (t2163).
#
# The mutating verbs rewrite the whole registry from what they read. An
# unreadable registry used to read as empty (non-UTF-8 content made the Python
# reader crash with empty stdout, swallowed by `|| true`; a directory or a
# dangling symlink failed `[[ -f ]]`), so `add` rewrote the file with only the
# new entry and dropped every other one. Each verb must now die, leave the
# registry path exactly as it was, and release the registry mutex.
#
# Run: bash tests/test_projects_unreadable_registry.sh

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
LAUNCH_UTILS="$PROJECT_DIR/.aitask-scripts/lib/agent_launch_utils.py"
PRISTINE="$TMPROOT/pristine.yaml"
SENTINEL="sentinel"
DANGLING_TARGET="$TMPROOT/no_such_registry.yaml"
CANNOT_READ="Cannot read the project registry"

make_project() {
    local root="$1" name="$2"
    mkdir -p "$root/aitasks/metadata"
    printf 'project:\n  name: %s\n' "$name" > "$root/aitasks/metadata/project_config.yaml"
}

ALPHA_ROOT="$TMPROOT/projects/alpha"
BETA_ROOT="$TMPROOT/projects/beta"
make_project "$ALPHA_ROOT" alpha
make_project "$BETA_ROOT" beta

# A two-entry registry. With $1 = bad, beta's git_remote carries one byte that
# is not valid UTF-8 (0xe9, Latin-1 "é").
write_registry() {
    local remote="git@example.test:beta.git"
    [[ "${1:-}" == "bad" ]] && remote=$'caf\xe9'
    {
        printf 'projects:\n'
        printf '  - name: alpha\n    path: %s\n    project_group: suite_a\n' "$ALPHA_ROOT"
        printf '  - name: beta\n    path: %s\n    git_remote: %s\n' "$BETA_ROOT" "$remote"
    } > "$REGISTRY_FILE"
}

# Put an unreadable registry of the given shape at REGISTRY_FILE.
make_shape() {
    rm -rf "$REGISTRY_FILE" "$LOCK_DIR"
    case "$1" in
        non_utf8)
            write_registry bad
            cp "$REGISTRY_FILE" "$PRISTINE"
            ;;
        directory)
            mkdir "$REGISTRY_FILE"
            touch "$REGISTRY_FILE/$SENTINEL"
            ;;
        dangling_symlink)
            ln -s "$DANGLING_TARGET" "$REGISTRY_FILE"
            ;;
    esac
}

# Assert the registry path is exactly what make_shape left there.
assert_shape_unchanged() {
    local desc="$1" shape="$2"
    case "$shape" in
        non_utf8)
            if [[ -f "$REGISTRY_FILE" && ! -L "$REGISTRY_FILE" ]] \
                    && cmp -s "$PRISTINE" "$REGISTRY_FILE"; then
                assert_record_pass
            else
                assert_record_fail
                echo "FAIL: $desc (registry bytes changed)"
            fi
            ;;
        directory)
            if [[ -d "$REGISTRY_FILE" && ! -L "$REGISTRY_FILE" ]] \
                    && [[ "$(ls -A "$REGISTRY_FILE")" == "$SENTINEL" ]]; then
                assert_record_pass
            else
                assert_record_fail
                echo "FAIL: $desc (registry directory changed)"
            fi
            ;;
        dangling_symlink)
            if [[ -L "$REGISTRY_FILE" && ! -e "$REGISTRY_FILE" ]] \
                    && [[ "$(readlink "$REGISTRY_FILE")" == "$DANGLING_TARGET" ]]; then
                assert_record_pass
            else
                assert_record_fail
                echo "FAIL: $desc (registry symlink changed)"
            fi
            ;;
    esac
}

# --- 1. Every verb × every unreadable shape ------------------------------

# label|stdin|verb args (space-separated)
# Paths appear as @ALPHA@ / @BETA@ and are substituted after the split, so a
# TMPDIR containing whitespace still reaches the verb as one argument.
VERBS=(
    "add|-|add @ALPHA@"
    "remove --force|-|remove alpha --force"
    "update|-|update alpha @BETA@"
    "prune --yes|-|prune --yes"
    "doctor|k|doctor"
    "group set|-|group set alpha suite_b"
    "group unset|-|group unset alpha"
    "group rename|-|group rename suite_a suite_b"
    "group sync|-|group sync"
    "list|-|list"
    "group list|-|group list"
)

for shape in non_utf8 directory dangling_symlink; do
    for spec in "${VERBS[@]}"; do
        IFS='|' read -r label stdin_text argline <<< "$spec"
        read -r -a args <<< "$argline"
        for i in "${!args[@]}"; do
            case "${args[i]}" in
                @ALPHA@) args[i]="$ALPHA_ROOT" ;;
                @BETA@)  args[i]="$BETA_ROOT" ;;
            esac
        done
        make_shape "$shape"
        [[ "$stdin_text" == "-" ]] && stdin_text=""
        rc=0
        err=$("$PROJECTS_SH" "${args[@]}" 2>&1 >/dev/null <<< "$stdin_text") || rc=$?
        assert_exit_nonzero_rc "$shape: $label exits non-zero" "$rc"
        assert_contains "$shape: $label names the unreadable registry" "$CANNOT_READ" "$err"
        assert_shape_unchanged "$shape: $label leaves the registry untouched" "$shape"
        assert_dir_not_exists "$shape: $label releases the registry lock" "$LOCK_DIR"
    done
done

# --- 2. remove: the registry turns unreadable after the confirmation prompt --

# A registry that is unreadable from the start dies at remove's first read, so
# section 1 never reaches the second read remove makes under the lock. Corrupt
# the registry while remove waits at its prompt, then confirm.
rm -rf "$REGISTRY_FILE" "$LOCK_DIR"
write_registry good
FIFO="$TMPROOT/confirm.fifo"
REMOVE_ERR="$TMPROOT/remove.err"
mkfifo "$FIFO"
"$PROJECTS_SH" remove alpha < "$FIFO" > /dev/null 2> "$REMOVE_ERR" &
remove_pid=$!
exec 3> "$FIFO"
prompt_seen=0
for _ in $(seq 1 100); do
    if grep -q "Remove 'alpha' from registry?" "$REMOVE_ERR" 2>/dev/null; then
        prompt_seen=1
        break
    fi
    sleep 0.1
done
if [[ "$prompt_seen" -eq 1 ]]; then
    assert_record_pass
    write_registry bad
    cp "$REGISTRY_FILE" "$PRISTINE"
    printf 'y\n' >&3
    exec 3>&-
    rc=0
    wait "$remove_pid" || rc=$?
    assert_exit_nonzero_rc "mid-confirmation corruption: remove exits non-zero" "$rc"
    assert_contains "mid-confirmation corruption: remove names the unreadable registry" \
        "$CANNOT_READ" "$(cat "$REMOVE_ERR")"
    assert_shape_unchanged "mid-confirmation corruption: registry bytes untouched" non_utf8
    assert_dir_not_exists "mid-confirmation corruption: lock released" "$LOCK_DIR"
else
    assert_record_fail
    echo "FAIL: remove never showed its confirmation prompt within 10s"
    echo "  stderr: $(cat "$REMOVE_ERR" 2>/dev/null)"
    exec 3>&-
    kill "$remove_pid" 2>/dev/null || true
    wait "$remove_pid" 2>/dev/null || true
fi

# --- 3. Python CLI contract ----------------------------------------------

make_shape non_utf8
rc=0
out=$(python3 "$LAUNCH_UTILS" --list-registry 2>/dev/null) || rc=$?
assert_eq "--list-registry (tolerant) exits 0 on non-UTF-8" "0" "$rc"
assert_eq "--list-registry (tolerant) prints nothing on non-UTF-8" "" "$out"
rc=0
python3 "$LAUNCH_UTILS" --list-registry-strict > /dev/null 2>&1 || rc=$?
assert_eq "--list-registry-strict exits 3 on non-UTF-8" "3" "$rc"

# --- 4. Positive controls -------------------------------------------------

# The same fixture without the bad byte: add succeeds and keeps both entries,
# so section 1's failures come from the unreadable registry, not the fixture.
rm -rf "$REGISTRY_FILE" "$LOCK_DIR"
write_registry good
rc=0
out=$("$PROJECTS_SH" add "$ALPHA_ROOT" 2>&1) || rc=$?
assert_exit_zero_rc_out "control: add on a readable registry succeeds" "$rc" "$out"
body=$(cat "$REGISTRY_FILE")
assert_contains "control: beta survives the rewrite" "name: beta" "$body"
assert_contains "control: alpha keeps its group" "project_group: suite_a" "$body"

# A genuinely missing registry is still an empty answer, not an error.
rm -rf "$REGISTRY_FILE" "$LOCK_DIR"
rc=0
out=$("$PROJECTS_SH" list 2>&1) || rc=$?
assert_exit_zero_rc_out "control: list with no registry succeeds" "$rc" "$out"
assert_contains "control: list with no registry says so" "No registered projects" "$out"

# --- Summary ------------------------------------------------------------

echo
echo "===================="
echo "Passed: $PASS / $TOTAL"
[[ "$FAIL" -gt 0 ]] && echo "Failed: $FAIL"
echo "===================="
[[ "$FAIL" -eq 0 ]]
