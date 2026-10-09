#!/usr/bin/env bash
# Tests for retired_scripts_manifest.txt and the pruner run against it (t1926).
# Run: bash tests/test_retired_scripts_manifest.sh
#
# The manifest drives deletions in users' projects, AFTER the release tarball
# was extracted over them. So the dangerous mistake is not a missing entry but a
# wrong one: a listed path the release still ships would match its own shipped
# hash and be deleted from every project on upgrade. Part 1 pins the manifest
# against this repository's history in both directions (nothing live listed;
# nothing retired missing, every shipped blob present). Part 2 runs the real
# helper against a temp project the way install.sh / `ait setup` call it.
# The end-to-end upgrade path is covered by tests/test_upgrade_prunes_retired_scripts.sh.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

PRUNER="$PROJECT_DIR/.aitask-scripts/aitask_prune_retired_skills.sh"
MANIFEST="$PROJECT_DIR/.aitask-scripts/retired_scripts_manifest.txt"
TAB="$(printf '\t')"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

manifest_records() {   # manifest_records <TYPE>
    grep "^$1$TAB" "$MANIFEST" | cut -f2 | sort -u
}

echo "=== Part 1: the manifest against repository history ==="

FILES="$(manifest_records FILE)"
SHAS="$(manifest_records SHA)"

assert_eq "manifest has FILE records" "yes" "$([[ -n "$FILES" ]] && echo yes || echo no)"
assert_eq "manifest has SHA records" "yes" "$([[ -n "$SHAS" ]] && echo yes || echo no)"

# No DIR records, deliberately: a DIR is owned per path through DIRSHA records
# (t1932), which this manifest's recipe does not produce — a DIR record here
# would keep any directory that still holds a file (only an empty one is
# removed). FILE records already remove exactly what shipped.
assert_eq "manifest carries no DIR record (FILE records only)" "" \
    "$(manifest_records DIR)"

# THE catastrophic case: a listed path the release still ships.
live_listed="$(comm -12 <(printf '%s\n' "$FILES") \
    <(git -C "$PROJECT_DIR" ls-files .aitask-scripts/ | sort -u))"
assert_eq "no manifest path is shipped by this release (would be deleted after extraction)" \
    "" "$live_listed"

outside="$(printf '%s\n' "$FILES" | grep -v '^\.aitask-scripts/' || true)"
assert_eq "every FILE record is under .aitask-scripts/" "" "$outside"

if [[ "$(git -C "$PROJECT_DIR" rev-parse --is-shallow-repository 2>/dev/null)" == "true" ]]; then
    echo "SKIP: completeness checks need full history (shallow clone)"
else
    # Completeness: every path ever added under .aitask-scripts/ that HEAD no
    # longer has. Fails the moment someone deletes or moves a script without
    # regenerating the manifest (recipe in the manifest header).
    retired="$(comm -23 \
        <(git -C "$PROJECT_DIR" log -m --format= --name-only --diff-filter=A -- .aitask-scripts/ | sort -u) \
        <(git -C "$PROJECT_DIR" ls-files .aitask-scripts/ | sort -u) | grep -v __pycache__ || true)"
    missing="$(comm -23 <(printf '%s\n' "$retired" | sed '/^$/d') <(printf '%s\n' "$FILES"))"
    assert_eq "every deleted/moved .aitask-scripts/ path is listed (regenerate the manifest)" \
        "" "$missing"

    # shellcheck disable=SC2086  # word-split the newline list into pathspecs
    expected_shas="$(cd "$PROJECT_DIR" && git log -m --no-renames --raw --no-abbrev --format= -- $retired \
        | awk '{print $3; print $4}' | grep -v '^0\{40\}$' | sort -u)"
    missing_shas="$(comm -23 <(printf '%s\n' "$expected_shas") <(printf '%s\n' "$SHAS"))"
    assert_eq "every blob ever shipped at a retired path is in the SHA set" "" "$missing_shas"

    # Each SHA must be a real blob of this repository (a hand-typed hash would
    # silently never match — or match something else).
    bad=""
    while IFS= read -r sha; do
        [[ "$(git -C "$PROJECT_DIR" cat-file -t "$sha" 2>/dev/null)" == "blob" ]] || bad+="$sha "
    done <<< "$SHAS"
    assert_eq "every SHA record is a blob in this repository" "" "$bad"
fi

assert_contains "t1217's rename source is listed" ".aitask-scripts/board/task_yaml.py" "$FILES"
assert_contains "t1235's rename source is listed" ".aitask-scripts/stats/stats_data.py" "$FILES"

echo ""
echo "=== Part 2: the helper against a temp project ==="

PROJ="$TMP/proj"

# Content of the last version the framework shipped at <path>.
last_shipped() {   # last_shipped <path> <dest>
    local path="$1" dest="$2" commit
    commit="$(git -C "$PROJECT_DIR" log -1 --format=%H --diff-filter=DR -M -- "$path")"
    mkdir -p "$(dirname "$dest")"
    git -C "$PROJECT_DIR" show "$commit^:$path" > "$dest"
}

build_fixture() {
    rm -rf "$PROJ"
    mkdir -p "$PROJ"
    # pristine leftovers (must be PRUNED)
    last_shipped .aitask-scripts/board/task_yaml.py "$PROJ/.aitask-scripts/board/task_yaml.py"
    last_shipped .aitask-scripts/stats/stats_data.py "$PROJ/.aitask-scripts/stats/stats_data.py"
    last_shipped .aitask-scripts/lib/attachment_backends/local.sh \
        "$PROJ/.aitask-scripts/lib/attachment_backends/local.sh"
    # a user backend copied byte-for-byte from the shipped local.sh: same hash,
    # different name — must survive, and keep the directory alive.
    cp "$PROJ/.aitask-scripts/lib/attachment_backends/local.sh" \
        "$PROJ/.aitask-scripts/lib/attachment_backends/my_backend.sh"
    # modified leftover (must be KEPT)
    last_shipped .aitask-scripts/lib/codex_plan_policy.sh "$PROJ/.aitask-scripts/lib/codex_plan_policy.sh"
    printf '# my local tweak\n' >> "$PROJ/.aitask-scripts/lib/codex_plan_policy.sh"
    # unrelated user file (must be untouched)
    printf '#!/usr/bin/env bash\necho mine\n' > "$PROJ/.aitask-scripts/my_tool.sh"
}

build_fixture
USER_TOOL_SUM="$(git hash-object "$PROJ/.aitask-scripts/my_tool.sh")"
set +e
OUT="$("$PRUNER" --dir "$PROJ" --manifest "$MANIFEST" --label script 2>"$TMP/err")"
RC=$?
set -e
ERR="$(cat "$TMP/err")"

assert_eq "exit 0 even when a path was kept" "0" "$RC"
for p in board/task_yaml.py stats/stats_data.py lib/attachment_backends/local.sh; do
    assert_contains "PRUNED: $p" "PRUNED:.aitask-scripts/$p" "$OUT"
    assert_file_not_exists "removed from disk: $p" "$PROJ/.aitask-scripts/$p"
done
assert_file_exists "user backend with a shipped blob's content survives (FILE, not DIR)" \
    "$PROJ/.aitask-scripts/lib/attachment_backends/my_backend.sh"
assert_contains "modified leftover reported KEPT" \
    "KEPT:.aitask-scripts/lib/codex_plan_policy.sh:unrecognized-content" "$OUT"
assert_file_exists "modified leftover kept on disk" "$PROJ/.aitask-scripts/lib/codex_plan_policy.sh"
assert_contains "warning names the kept path with a cleanup command" \
    "rm -rf .aitask-scripts/lib/codex_plan_policy.sh" "$ERR"
assert_contains "--label script reaches the warning" "retired script path(s) were KEPT" "$ERR"
assert_contains "--label script reaches the explanation" "your own script at" "$ERR"
assert_not_contains "no rendered-closure text without STEM records" "rendered-closure" "$ERR"
assert_eq "unrelated user file untouched" "$USER_TOOL_SUM" \
    "$(git hash-object "$PROJ/.aitask-scripts/my_tool.sh")"

set +e
OUT2="$("$PRUNER" --dir "$PROJ" --manifest "$MANIFEST" --label script 2>/dev/null)"
set -e
assert_not_contains "second run prunes nothing" "PRUNED:" "$OUT2"
assert_contains "second run still reports the kept path" \
    "KEPT:.aitask-scripts/lib/codex_plan_policy.sh" "$OUT2"

echo ""
echo "Tests: $TOTAL, Passed: $PASS, Failed: $FAIL"
[[ "$FAIL" -eq 0 ]] || exit 1
