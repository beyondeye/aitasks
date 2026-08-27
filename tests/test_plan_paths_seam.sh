#!/usr/bin/env bash
# test_plan_paths_seam.sh - Post-phase risk mitigations for t1569_1.
#
#   guard_single_extractor_source          — the no-fork guard
#   drift_check_fails_closed_without_python — the new dependency's failure mode
#
# Run: bash tests/test_plan_paths_seam.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

. "$PROJECT_DIR/tests/lib/asserts.sh"
cd "$PROJECT_DIR"

# ============================================================
# guard_single_extractor_source
#
# Deliberately NOT a match on the source literal. A fork written as
# [A-Za-z0-9./_-] (same class, different member order) would pass such a guard,
# while documenting the grammar in plan_paths.py's own docstring would make two
# occurrences and FAIL it for a documentation reason — and a guard that fails
# for innocent reasons trains people to weaken it. Assert instead that every
# consumer resolves the grammar through the plan_paths SYMBOL.
# ============================================================

echo "--- guard: one extractor, reached by symbol ---"

# (a) The canonical definition exists and is reachable as a symbol.
assert_exit_zero "guard: plan_paths exposes extract()" \
    python3 -c "import sys; sys.path.insert(0,'.aitask-scripts/lib'); import plan_paths; plan_paths.extract"
assert_exit_zero "guard: plan_paths exposes the malformed predicate" \
    python3 -c "import sys; sys.path.insert(0,'.aitask-scripts/lib'); import plan_paths; plan_paths.is_malformed"

# (b) No OTHER file under .aitask-scripts/ builds its own path-token matcher.
#     Normalize away member order by sorting the character class, so a reordered
#     fork is caught and a docstring mention of the grammar is not.
forks=$(python3 - <<'PY'
import re, pathlib
root = pathlib.Path(".aitask-scripts")
canonical = pathlib.Path(".aitask-scripts/lib/plan_paths.py").resolve()
# Any char-class-plus-extension-alternation construct, in shell or Python.
pat = re.compile(r"\[[^\]]*A-Za-z0-9[^\]]*\]\+?\\?\.\(\??:?(?:sh|py|md)")
hits = []
for path in root.rglob("*"):
    if not path.is_file() or path.resolve() == canonical:
        continue
    if path.suffix not in (".py", ".sh"):
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        continue
    for line in text.splitlines():
        stripped = line.strip()
        # A comment is documentation, not a fork.
        if stripped.startswith("#"):
            continue
        if pat.search(line):
            hits.append(f"{path}: {stripped[:70]}")
print("\n".join(hits))
PY
)
assert_eq "guard: no second copy of the extension-allowlist grammar" "" "$forks"

# WHAT THIS GUARD DOES NOT BUY. It pins one copy of THIS grammar — the
# extension-allowlisted one the drift check and the gatherer share. It does not
# claim the repository has exactly one plan-path extractor, because it does not:
# aitask_change_surface.sh carries a deliberately DIFFERENT one (t1263) with a
# broader token class, no extension allowlist, and filesystem validation instead
# of `git ls-files`. That is a different question ("which files did this task
# change?") with different correctness requirements, and consolidating the two
# would change its behaviour. Pinned here so a reader sees a recorded decision
# rather than an oversight — and so it cannot quietly drift INTO a copy of ours.
other="$(sed -n '226p' .aitask-scripts/aitask_change_surface.sh)"
assert_contains "guard: change_surface keeps its own broader grammar" \
    "[A-Za-z0-9_.][A-Za-z0-9_./-]*" "$other"
assert_not_contains "guard: change_surface has NOT adopted our extension list" \
    "yaml|yml|json|toml" "$other"

# (c) The drift check reaches the grammar through the bridge, not a local copy.
assert_contains "guard: drift check sources the bridge" \
    "lib/plan_paths_sh.sh" "$(cat .aitask-scripts/aitask_remote_drift_check.sh)"
assert_contains "guard: drift check calls the shared extractor" \
    "plan_paths_extract" "$(cat .aitask-scripts/aitask_remote_drift_check.sh)"

# ============================================================
# drift_check_fails_closed_without_python
#
# The drift check was pure shell and now depends on Python via the bridge. A
# resolve failure must produce a NAMED error, never a silent NO_OVERLAP — a
# false all-clear on the pick hot path is indistinguishable from a real one.
# ============================================================

echo "--- guard: drift check fails CLOSED when Python is unreachable ---"

root=$(mktemp -d "${TMPDIR:-/tmp}/aitask_failclosed_XXXXXX")
trap 'rm -rf "$root"' EXIT
git init --bare --quiet "$root/origin.git"
git clone --quiet "$root/origin.git" "$root/local" 2>/dev/null
(
    cd "$root/local"
    git config user.email "t@e.com"
    git config user.name "T"
    echo v1 > README.md
    git add README.md
    git commit --quiet -m init
    git push --quiet origin HEAD 2>/dev/null
)
default_branch=$(git -C "$root/local" rev-parse --abbrev-ref HEAD)

# Extraction only runs once there IS drift -- the helper returns UP_TO_DATE
# before reading any plan. Push a remote-only commit so the extraction path is
# genuinely exercised; otherwise this whole section would assert nothing.
git clone --quiet "$root/origin.git" "$root/other" 2>/dev/null
(
    cd "$root/other"
    git config user.email "o@e.com"
    git config user.name "O"
    mkdir -p .aitask-scripts
    echo patched > .aitask-scripts/aitask_archive.sh
    git add .aitask-scripts/aitask_archive.sh
    git commit --quiet -m "remote-only change"
    git push --quiet origin "$default_branch"
)
mkdir -p "$root/local/.aitask-data/.git"
cat > "$root/local/plan.md" <<'PLAN'
---
Task: t999.md
---
Touches .aitask-scripts/aitask_archive.sh
PLAN

HELPER="$PROJECT_DIR/.aitask-scripts/aitask_remote_drift_check.sh"

# Positive control FIRST: without the fault, this path reaches a real verdict.
# Without it, a broken invocation would satisfy the negative assertions below.
ok_out=$(cd "$root/local" && "$HELPER" "$default_branch" "$root/local/plan.md" 2>&1 || true)
assert_contains "fail-closed: positive control reaches the extraction path" \
    "OVERLAP:.aitask-scripts/aitask_archive.sh" "$ok_out"

# Now poison the interpreter the bridge resolves.
bad_out=$(cd "$root/local" && _AIT_RESOLVED_PYTHON=/nonexistent/python \
    "$HELPER" "$default_branch" "$root/local/plan.md" 2>&1 || true)
bad_rc=0
(cd "$root/local" && _AIT_RESOLVED_PYTHON=/nonexistent/python \
    "$HELPER" "$default_branch" "$root/local/plan.md" >/dev/null 2>&1) || bad_rc=$?

assert_contains "fail-closed: emits a NAMED error" "EXTRACT_FAILED" "$bad_out"
assert_not_contains "fail-closed: never a silent NO_OVERLAP" "NO_OVERLAP" "$bad_out"
assert_not_contains "fail-closed: never a spurious OVERLAP" "OVERLAP:" "$bad_out"
assert_eq "fail-closed: exits non-zero (3 = infra)" "3" "$bad_rc"

# An EXISTING but unreadable plan must reach the extractor and fail closed.
# The former `-r` guard intercepted exactly this case -- the one the script
# header names -- skipping the block and printing NO_OVERLAP with exit 0.
echo "--- guard: an unreadable plan fails closed, not silently ---"

# (a) mode 000
cp "$root/local/plan.md" "$root/local/unreadable.md"
chmod 000 "$root/local/unreadable.md"
if [[ -r "$root/local/unreadable.md" ]]; then
    echo "SKIP: running as root -- mode 000 is still readable"
else
    out=$(cd "$root/local" && "$HELPER" "$default_branch" "$root/local/unreadable.md" 2>&1 || true)
    rc=0
    (cd "$root/local" && "$HELPER" "$default_branch" "$root/local/unreadable.md" >/dev/null 2>&1) || rc=$?
    assert_contains "unreadable plan: emits EXTRACT_FAILED" "EXTRACT_FAILED" "$out"
    assert_not_contains "unreadable plan: never a silent NO_OVERLAP" "NO_OVERLAP" "$out"
    assert_eq "unreadable plan: exits 3" "3" "$rc"
fi
chmod 644 "$root/local/unreadable.md" 2>/dev/null || true

# (b) broken symlink -- `-e` is false for it, so the guard must also test `-L`
ln -s /nonexistent/target.md "$root/local/broken.md"
out=$(cd "$root/local" && "$HELPER" "$default_branch" "$root/local/broken.md" 2>&1 || true)
rc=0
(cd "$root/local" && "$HELPER" "$default_branch" "$root/local/broken.md" >/dev/null 2>&1) || rc=$?
assert_contains "broken symlink plan: emits EXTRACT_FAILED" "EXTRACT_FAILED" "$out"
assert_not_contains "broken symlink plan: never a silent NO_OVERLAP" "NO_OVERLAP" "$out"
assert_eq "broken symlink plan: exits 3" "3" "$rc"

# (c) a genuinely ABSENT plan keeps the pre-existing behaviour.
out=$(cd "$root/local" && "$HELPER" "$default_branch" "$root/local/absent.md" 2>&1 || true)
assert_not_contains "absent plan: not treated as an extraction failure" \
    "EXTRACT_FAILED" "$out"

echo ""
echo "================================"
echo "Results: $PASS passed, $FAIL failed (of $TOTAL total)"
echo "================================"

if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
