#!/usr/bin/env bash
# test_framework_copy.sh - fixtures copy the framework without bytecode caches
# (t2226): copy_framework_tree's contract, sync_fixture.sh's setup_repo on a
# source tree that HAS caches, and a guard that no tracked bash test copies
# .aitask-scripts recursively with cp.
# Run: bash tests/test_framework_copy.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

PASS=0
FAIL=0
TOTAL=0
. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/framework_copy.sh"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# caches_under <dir>: every bytecode-cache path below <dir>, one per line.
caches_under() {
    find "$1" \( -name __pycache__ -o -name '*.pyc' \) -print | sort
}

# --- 1. copy_framework_tree --------------------------------------------------
echo "--- 1. copy_framework_tree"
SRC="$TMP/src"
mkdir -p "$SRC/__pycache__" "$SRC/pkg/__pycache__" "$SRC/pkg/deep/__pycache__"
printf 'x\n' > "$SRC/__pycache__/top.cpython-313.pyc"
printf 'x\n' > "$SRC/pkg/__pycache__/mod.cpython-313.pyc"
printf 'x\n' > "$SRC/pkg/deep/__pycache__/d.cpython-313.pyc"
printf 'x\n' > "$SRC/stray.pyc"
printf 'print(1)\n' > "$SRC/pkg/mod.py"
printf 'print(2)\n' > "$SRC/pkg/deep/d.py"
printf '#!/usr/bin/env bash\necho a\n' > "$SRC/a.sh"
chmod +x "$SRC/a.sh"
printf 'cfg\n' > "$SRC/.dotfile"
# Precondition: the source really carries what the copy must drop.
assert_eq "precondition: the source holds 7 cache paths" "7" "$(caches_under "$SRC" | wc -l | tr -d ' ')"

DST="$TMP/fresh/nested/dst"
rc=0
copy_framework_tree "$SRC" "$DST" || rc=$?
assert_eq "copy into a missing destination succeeds" "0" "$rc"
assert_eq "no __pycache__ or *.pyc is copied" "" "$(caches_under "$DST")"
assert_eq "every non-cache file is copied" \
    "$(cd "$SRC" && find . -type f ! -path '*/__pycache__/*' ! -name '*.pyc' | sort)" \
    "$(cd "$DST" && find . -type f | sort)"
assert_eq "file contents survive" "print(2)" "$(cat "$DST/pkg/deep/d.py")"
if [[ -x "$DST/a.sh" ]]; then assert_record_pass; else assert_record_fail; echo "FAIL: the executable bit is kept"; fi
assert_file_exists "dotfiles are copied" "$DST/.dotfile"

# An existing destination receives the contents -- never a nested src/ dir.
EXIST="$TMP/existing"
mkdir -p "$EXIST"
printf 'mine\n' > "$EXIST/keep.txt"
rc=0
copy_framework_tree "$SRC" "$EXIST" || rc=$?
assert_eq "copy into an existing destination succeeds" "0" "$rc"
assert_file_exists "existing destination: contents land at its top level" "$EXIST/pkg/mod.py"
assert_eq "existing destination: no nested copy of the source dir" "" "$(find "$EXIST" -maxdepth 1 -name src)"
assert_eq "existing destination: its own files are untouched" "mine" "$(cat "$EXIST/keep.txt")"
assert_eq "existing destination: no caches either" "" "$(caches_under "$EXIST")"

rc=0
err="$(copy_framework_tree "$TMP/no_such_dir" "$TMP/never" 2>&1)" || rc=$?
assert_eq "a missing source fails" "1" "$rc"
assert_contains "a missing source names itself" "not a directory: $TMP/no_such_dir" "$err"
assert_eq "a missing source creates no destination" "" "$(find "$TMP" -maxdepth 1 -name never)"

# --- 2. sync_fixture.sh setup_repo -------------------------------------------
# Run against a synthetic project that DOES carry caches, so the check means
# something on a clean checkout too (which has none to copy).
echo "--- 2. sync_fixture.sh setup_repo"
FAKE="$TMP/project"
mkdir -p "$FAKE/tests"
cp "$PROJECT_DIR/ait" "$FAKE/ait"
ln -s "$PROJECT_DIR/tests/lib" "$FAKE/tests/lib"
copy_framework_tree "$PROJECT_DIR/.aitask-scripts" "$FAKE/.aitask-scripts"
for d in "$FAKE/.aitask-scripts" "$FAKE/.aitask-scripts/lib" "$FAKE/.aitask-scripts/board"; do
    mkdir -p "$d/__pycache__"
    printf 'x\n' > "$d/__pycache__/planted.cpython-313.pyc"
done
assert_eq "precondition: the synthetic project holds 3 planted caches" "3" \
    "$(find "$FAKE/.aitask-scripts" -name __pycache__ | wc -l | tr -d ' ')"

# sync_fixture.sh reads PROJECT_DIR, so it is re-pointed -- deliberately only
# inside this subshell; the guard below must still scan the real checkout.
# shellcheck disable=SC2030,SC2031
fx_out="$(
    PROJECT_DIR="$FAKE"
    . "$PROJECT_DIR/tests/lib/sync_fixture.sh"
    fx="$(setup_repo)"
    printf 'DISK:%s\n' "$(find "$fx/local/.aitask-scripts" \( -name __pycache__ -o -name '*.pyc' \) | wc -l | tr -d ' ')"
    printf 'SCRIPTS:%s\n' "$( [[ -f "$fx/local/.aitask-scripts/aitask_lock.sh" ]] && echo yes || echo no)"
    printf 'TREE:%s\n' "$(git -C "$fx/local" ls-tree -r --name-only HEAD | grep -cE '(^|/)__pycache__/|\.pyc$')"
    printf 'LOCKS:%s\n' "$(git -C "$fx/local" rev-parse --verify --quiet origin/aitask-locks >/dev/null && echo yes || echo no)"
)"
assert_contains "setup_repo copies the framework" "SCRIPTS:yes" "$fx_out"
assert_contains "setup_repo copies no bytecode cache to disk" "DISK:0" "$fx_out"
assert_contains "setup_repo commits no bytecode cache" "TREE:0" "$fx_out"
assert_contains "setup_repo still initializes the lock branch" "LOCKS:yes" "$fx_out"

# --- 3. no tracked bash test copies .aitask-scripts with a recursive cp -------
# Tracked files only: an untracked test belongs to the session writing it and
# is outside this contract until it is committed. The pattern is assembled from
# fragments so this file never matches itself.
echo "--- 3. guard: tracked tests use copy_framework_tree"
cp_flags='cp[[:space:]]+-[A-Za-z]*[rRa][A-Za-z]*[[:space:]]'
src_path='.*\$\{?PROJECT_DIR\}?/\.aitask-'"scripts"
pattern="${cp_flags}${src_path}"

# guard_hits <repo_root>: print one `<path>:<line>:<text>` per forbidden copy in
# a tracked tests/*.sh or tests/lib/*.sh file; return 2 when the tracked files
# cannot be enumerated, there are none, or a file cannot be scanned (never a
# vacuous pass). Filenames are data end to end: enumeration is NUL-delimited
# (without -z git C-quotes unusual names, "tests/test_caf\303\251.sh", and the
# quoted form is not a path on disk), and the hit prefix is printed literally --
# never spliced into a sed expression, where `|` or a newline breaks it.
guard_hits() {
    local root="$1" list f m line n=0 ls_rc=0 g_rc
    list="$(mktemp -p "$TMP")"
    git -C "$root" ls-files -z -- ':(glob)tests/*.sh' ':(glob)tests/lib/*.sh' > "$list" || ls_rc=$?
    if [[ "$ls_rc" -ne 0 ]]; then
        echo "guard: git ls-files failed (exit $ls_rc) in $root" >&2
        return 2
    fi
    while IFS= read -r -d '' f; do
        n=$((n + 1))
        [[ -f "$root/$f" ]] || continue   # tracked but deleted in the worktree
        g_rc=0
        m="$(grep -nE -- "$pattern" "$root/$f")" || g_rc=$?
        if [[ "$g_rc" -ge 2 ]]; then
            printf 'guard: grep could not scan %s (exit %s)\n' "$f" "$g_rc" >&2
            return 2
        fi
        [[ -n "$m" ]] || continue
        while IFS= read -r line; do
            printf '%s:%s\n' "$f" "$line"
        done <<< "$m"
    done < "$list"
    if [[ "$n" -eq 0 ]]; then
        echo "guard: no tracked test scripts in $root" >&2
        return 2
    fi
}

g_rc=0
# shellcheck disable=SC2031  # the subshell above re-pointed only its own copy
hits="$(guard_hits "$PROJECT_DIR")" || g_rc=$?
assert_eq "guard: the tracked test scripts are enumerated" "0" "$g_rc"
if [[ -z "$hits" ]]; then
    assert_record_pass
else
    assert_record_fail
    echo "FAIL: guard: recursive cp of PROJECT_DIR/.aitask-scripts -- use copy_framework_tree (tests/lib/framework_copy.sh):"
    printf '%s\n' "$hits" | sed 's/^/    /'
fi

# The guard itself, on a synthetic repository: a forbidden copy in a tracked
# file with a non-ASCII name is found, an untracked one is not, and a repository
# with no tracked test scripts refuses rather than passing.
G="$TMP/guardrepo"
mkdir -p "$G/tests/lib"
git -C "$G" init -q
# shellcheck disable=SC2016  # literal source text, nothing may expand
bad_line='    cp -R "$PROJECT_DIR/@FW@" "$t/"'
bad_line="${bad_line//@FW@/.aitask-scripts}"
printf '#!/usr/bin/env bash\n%s\n' "$bad_line" > "$G/tests/test_café.sh"
printf '#!/usr/bin/env bash\n%s\n' "$bad_line" > "$G/tests/lib/untracked_helper.sh"
printf '#!/usr/bin/env bash\necho ok\n' > "$G/tests/test_clean.sh"
g_rc=0
empty_out="$(guard_hits "$G" 2>/dev/null)" || g_rc=$?
assert_eq "guard: a repository with no tracked test scripts refuses" "2" "$g_rc"
assert_eq "guard: ...and reports no hits" "" "$empty_out"
git -C "$G" add -- "tests/test_café.sh" tests/test_clean.sh
g_rc=0
g_hits="$(guard_hits "$G")" || g_rc=$?
assert_eq "guard: the synthetic repository is enumerated" "0" "$g_rc"
assert_contains "guard: a tracked non-ASCII filename is scanned, line named" "tests/test_café.sh:2:" "$g_hits"
assert_not_contains "guard: an untracked file is outside the contract" "untracked_helper" "$g_hits"
assert_not_contains "guard: a clean tracked file is not flagged" "test_clean" "$g_hits"

# Names that are syntax elsewhere: `|` (a sed delimiter) and an embedded newline.
nl_name="$G/tests/test_nl"$'\n'"name.sh"
printf '#!/usr/bin/env bash\n%s\n' "$bad_line" > "$G/tests/test_pipe|name.sh"
printf '#!/usr/bin/env bash\n%s\n' "$bad_line" > "$nl_name"
git -C "$G" add -- "tests/test_pipe|name.sh" "tests/test_nl"$'\n'"name.sh"
g_rc=0
g_hits="$(guard_hits "$G")" || g_rc=$?
assert_eq "guard: odd filenames are enumerated" "0" "$g_rc"
assert_contains "guard: a tracked name holding '|' is flagged, line named" "tests/test_pipe|name.sh:2:" "$g_hits"
assert_contains "guard: a tracked name holding a newline is flagged, line named" "name.sh:2:" "$g_hits"
assert_eq "guard: every forbidden copy is reported once" "3" "$(grep -c ':2:' <<< "$g_hits")"

# A file the scanner cannot read is a guard failure, never a clean scan.
if [[ "$(id -u)" -ne 0 ]]; then
    chmod 000 "$G/tests/test_clean.sh"
    g_rc=0
    g_err="$(guard_hits "$G" 2>&1 >/dev/null)" || g_rc=$?
    chmod 644 "$G/tests/test_clean.sh"
    assert_eq "guard: an unreadable tracked file fails the scan" "2" "$g_rc"
    assert_contains "guard: ...naming the file" "could not scan tests/test_clean.sh" "$g_err"
fi

# The guard's own pattern must recognise every shape it forbids. @FW@ stands
# for the framework dir, substituted at run time so these lines never match.
# The shapes are literal source text, so nothing in them may expand.
# shellcheck disable=SC2016
for shape in 'cp -r "$PROJECT_DIR/@FW@" x' 'cp -R "$PROJECT_DIR/@FW@/lib" x' \
             'cp -a "${PROJECT_DIR}/@FW@" x' '    cp -rf "$PROJECT_DIR/@FW@/lib/." x/'; do
    shape="${shape//@FW@/.aitask-scripts}"
    if printf '%s\n' "$shape" | grep -qE "$pattern"; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: guard pattern misses: $shape"
    fi
done
# shellcheck disable=SC2016
for ok in 'cp "$PROJECT_DIR/@FW@/VERSION" x' 'copy_framework_tree "$PROJECT_DIR/@FW@" x'; do
    ok="${ok//@FW@/.aitask-scripts}"
    if printf '%s\n' "$ok" | grep -qE "$pattern"; then
        assert_record_fail
        echo "FAIL: guard pattern flags an allowed shape: $ok"
    else
        assert_record_pass
    fi
done

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]] || exit 1
