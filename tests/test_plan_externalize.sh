#!/usr/bin/env bash
# test_plan_externalize.sh - Tests for aitask_plan_externalize.sh
# Run: bash tests/test_plan_externalize.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"
EXTERNALIZE="$PROJECT_DIR/.aitask-scripts/aitask_plan_externalize.sh"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

# --- Setup helpers ---

new_sandbox() {
    local tmpdir
    tmpdir=$(mktemp -d)
    mkdir -p "$tmpdir/aitasks"
    mkdir -p "$tmpdir/aiplans"
    mkdir -p "$tmpdir/fakehome/.claude/plans"
    cat > "$tmpdir/aitasks/t999_sandbox_task.md" <<'EOF'
---
priority: medium
effort: medium
status: Ready
---

Sandbox task body.
EOF
    echo "$tmpdir"
}

make_fresh_internal() {
    local path="$1"
    cat > "$path" <<'EOF'
# Sandbox plan

- Step 1
- Step 2
EOF
}

# Portable "set file mtime to N hours ago". Uses touch -t YYYYMMDDhhmm.
make_old() {
    local path="$1" hours_ago="$2"
    local stamp
    if stamp=$(date -d "${hours_ago} hours ago" +%Y%m%d%H%M 2>/dev/null); then
        :
    else
        stamp=$(date -v-"${hours_ago}"H +%Y%m%d%H%M)
    fi
    touch -t "$stamp" "$path"
}

run_externalize() {
    local sandbox="$1"; shift
    local plans_dir="$1"; shift
    ( cd "$sandbox" && \
      AIT_PLAN_EXTERNALIZE_INTERNAL_DIR="$plans_dir" \
      "$EXTERNALIZE" "$@" )
}

echo "=== test_plan_externalize.sh ==="
echo ""

# --- Test 1: Fresh internal plan → EXTERNALIZED ---
echo "--- Test 1: fresh internal plan ---"
TMPDIR1=$(new_sandbox)
make_fresh_internal "$TMPDIR1/fakehome/.claude/plans/one-recent.md"
result=$(run_externalize "$TMPDIR1" "$TMPDIR1/fakehome/.claude/plans" 999)
assert_contains "fresh: EXTERNALIZED prefix" "EXTERNALIZED:aiplans/p999_sandbox_task.md:" "$result"
assert_file_exists "fresh: external plan created" "$TMPDIR1/aiplans/p999_sandbox_task.md"
first_line=$(head -n 1 "$TMPDIR1/aiplans/p999_sandbox_task.md")
assert_eq "fresh: frontmatter opener prepended" "---" "$first_line"
task_field=$(grep '^Task:' "$TMPDIR1/aiplans/p999_sandbox_task.md" || true)
assert_contains "fresh: Task field present" "t999_sandbox_task.md" "$task_field"
base_field=$(grep '^Base branch:' "$TMPDIR1/aiplans/p999_sandbox_task.md" || true)
assert_contains "fresh: Base branch field present" "main" "$base_field"
out_field=$(grep '^Output branch:' "$TMPDIR1/aiplans/p999_sandbox_task.md" || true)
assert_eq "fresh: Output branch defaults to Base branch" "Output branch: ${base_field#Base branch: }" "$out_field"
rm -rf "$TMPDIR1"

# --- Test 2: Second invocation → PLAN_EXISTS ---
echo "--- Test 2: idempotent no-op ---"
TMPDIR2=$(new_sandbox)
make_fresh_internal "$TMPDIR2/fakehome/.claude/plans/one-recent.md"
run_externalize "$TMPDIR2" "$TMPDIR2/fakehome/.claude/plans" 999 >/dev/null
result=$(run_externalize "$TMPDIR2" "$TMPDIR2/fakehome/.claude/plans" 999)
assert_contains "no-op: PLAN_EXISTS" "PLAN_EXISTS:aiplans/p999_sandbox_task.md" "$result"
rm -rf "$TMPDIR2"

# --- Test 3: Only stale files → NOT_FOUND:no_internal_files ---
echo "--- Test 3: stale file ignored ---"
TMPDIR3=$(new_sandbox)
make_fresh_internal "$TMPDIR3/fakehome/.claude/plans/stale-old.md"
make_old "$TMPDIR3/fakehome/.claude/plans/stale-old.md" 2
result=$(run_externalize "$TMPDIR3" "$TMPDIR3/fakehome/.claude/plans" 999)
assert_contains "stale: NOT_FOUND:no_internal_files" "NOT_FOUND:no_internal_files" "$result"
rm -rf "$TMPDIR3"

# --- Test 4: Multiple fresh files → MULTIPLE_CANDIDATES ---
echo "--- Test 4: multiple candidates ---"
TMPDIR4=$(new_sandbox)
make_fresh_internal "$TMPDIR4/fakehome/.claude/plans/first.md"
make_fresh_internal "$TMPDIR4/fakehome/.claude/plans/second.md"
result=$(run_externalize "$TMPDIR4" "$TMPDIR4/fakehome/.claude/plans" 999)
assert_contains "multiple: MULTIPLE_CANDIDATES prefix" "MULTIPLE_CANDIDATES:" "$result"
assert_contains "multiple: first.md listed" "first.md" "$result"
assert_contains "multiple: second.md listed" "second.md" "$result"
rm -rf "$TMPDIR4"

# --- Test 5a: --internal explicit path → EXTERNALIZED ---
echo "--- Test 5a: --internal path ---"
TMPDIR5=$(new_sandbox)
explicit_path="$TMPDIR5/fakehome/.claude/plans/fresh.md"
make_fresh_internal "$explicit_path"
result=$(run_externalize "$TMPDIR5" "$TMPDIR5/fakehome/.claude/plans" 999 --internal "$explicit_path")
assert_contains "--internal ok: EXTERNALIZED" "EXTERNALIZED:aiplans/p999_sandbox_task.md:" "$result"
rm -rf "$TMPDIR5"

# --- Test 5b: --internal with nonexistent path → NOT_FOUND:source_not_file ---
echo "--- Test 5b: --internal nonexistent ---"
TMPDIR5b=$(new_sandbox)
result=$(run_externalize "$TMPDIR5b" "$TMPDIR5b/fakehome/.claude/plans" 999 --internal /nonexistent/plan.md)
assert_contains "--internal nonexistent: NOT_FOUND:source_not_file" "NOT_FOUND:source_not_file" "$result"
rm -rf "$TMPDIR5b"

# --- Test 6: Child task form → aiplans/p<parent>/p<parent>_<child>_*.md ---
echo "--- Test 6: child task ---"
TMPDIR6=$(new_sandbox)
mkdir -p "$TMPDIR6/aitasks/t999"
cat > "$TMPDIR6/aitasks/t999/t999_2_sub.md" <<'EOF'
---
priority: medium
status: Ready
---

Child task body.
EOF
make_fresh_internal "$TMPDIR6/fakehome/.claude/plans/child.md"
result=$(run_externalize "$TMPDIR6" "$TMPDIR6/fakehome/.claude/plans" 999_2)
assert_contains "child: EXTERNALIZED path" "EXTERNALIZED:aiplans/p999/p999_2_sub.md:" "$result"
assert_file_exists "child: external plan created in subdir" "$TMPDIR6/aiplans/p999/p999_2_sub.md"
parent_field=$(grep '^Parent Task:' "$TMPDIR6/aiplans/p999/p999_2_sub.md" || true)
assert_contains "child: Parent Task field present" "t999_sandbox_task.md" "$parent_field"
rm -rf "$TMPDIR6"

# --- Test 7: Internal plan already has frontmatter → no duplicate header ---
echo "--- Test 7: existing frontmatter not duplicated ---"
TMPDIR7=$(new_sandbox)
cat > "$TMPDIR7/fakehome/.claude/plans/with_front.md" <<'EOF'
---
Task: t999_sandbox_task.md
---

# Already has frontmatter
EOF
result=$(run_externalize "$TMPDIR7" "$TMPDIR7/fakehome/.claude/plans" 999)
assert_contains "existing front: EXTERNALIZED" "EXTERNALIZED:" "$result"
count=$(grep -c '^---$' "$TMPDIR7/aiplans/p999_sandbox_task.md" || true)
assert_eq "existing front: frontmatter not duplicated (--- count == 2)" "2" "$count"
# Negative control: without --output-branch the file is copied verbatim.
if diff -q "$TMPDIR7/fakehome/.claude/plans/with_front.md" \
           "$TMPDIR7/aiplans/p999_sandbox_task.md" >/dev/null; then
    assert_eq "existing front: no --output-branch leaves file unchanged" "same" "same"
else
    assert_eq "existing front: no --output-branch leaves file unchanged" "same" "differs"
fi
rm -rf "$TMPDIR7"

# --- Test 7b: --output-branch is spliced into pre-existing frontmatter ---
# build_header() is skipped for such sources, so without the splice the flag
# would be silently dropped and Step 9 would merge to the wrong branch.
echo "--- Test 7b: --output-branch spliced into existing frontmatter ---"
TMPDIR7B=$(new_sandbox)
cat > "$TMPDIR7B/fakehome/.claude/plans/with_front.md" <<'EOF'
---
Task: t999_sandbox_task.md
---

# Already has frontmatter
EOF
run_externalize "$TMPDIR7B" "$TMPDIR7B/fakehome/.claude/plans" 999 --output-branch dev >/dev/null
count=$(grep -c '^---$' "$TMPDIR7B/aiplans/p999_sandbox_task.md" || true)
assert_eq "splice insert: --- count still 2" "2" "$count"
n=$(grep -c '^Output branch: dev$' "$TMPDIR7B/aiplans/p999_sandbox_task.md" || true)
assert_eq "splice insert: Output branch recorded exactly once" "1" "$n"
rm -rf "$TMPDIR7B"

# --- Test 7c: existing Output branch in frontmatter is replaced, not duplicated ---
echo "--- Test 7c: --output-branch replaces an existing field ---"
TMPDIR7C=$(new_sandbox)
cat > "$TMPDIR7C/fakehome/.claude/plans/with_front.md" <<'EOF'
---
Task: t999_sandbox_task.md
Output branch: stale
---

# Already has frontmatter
EOF
run_externalize "$TMPDIR7C" "$TMPDIR7C/fakehome/.claude/plans" 999 --output-branch dev >/dev/null
n=$(grep -c '^Output branch:' "$TMPDIR7C/aiplans/p999_sandbox_task.md" || true)
assert_eq "splice replace: exactly one Output branch line" "1" "$n"
out_field=$(grep '^Output branch:' "$TMPDIR7C/aiplans/p999_sandbox_task.md" || true)
assert_eq "splice replace: value replaced" "Output branch: dev" "$out_field"
count=$(grep -c '^---$' "$TMPDIR7C/aiplans/p999_sandbox_task.md" || true)
assert_eq "splice replace: --- count still 2" "2" "$count"
rm -rf "$TMPDIR7C"

# --- Test 7d: --output-branch on the built-header path ---
echo "--- Test 7d: --output-branch on a header-built plan ---"
TMPDIR7D=$(new_sandbox)
make_fresh_internal "$TMPDIR7D/fakehome/.claude/plans/one-recent.md"
run_externalize "$TMPDIR7D" "$TMPDIR7D/fakehome/.claude/plans" 999 --output-branch dev >/dev/null
out_field=$(grep '^Output branch:' "$TMPDIR7D/aiplans/p999_sandbox_task.md" || true)
assert_eq "built header: Output branch honoured" "Output branch: dev" "$out_field"
base_field=$(grep '^Base branch:' "$TMPDIR7D/aiplans/p999_sandbox_task.md" || true)
assert_eq "built header: Base branch unaffected by --output-branch" "Base branch: main" "$base_field"
rm -rf "$TMPDIR7D"

# --- Test 7e: --output-branch without an argument is a usage error ---
echo "--- Test 7e: --output-branch missing argument ---"
TMPDIR7E=$(new_sandbox)
make_fresh_internal "$TMPDIR7E/fakehome/.claude/plans/one-recent.md"
if run_externalize "$TMPDIR7E" "$TMPDIR7E/fakehome/.claude/plans" 999 --output-branch >/dev/null 2>&1; then
    assert_eq "missing --output-branch arg exits non-zero" "nonzero" "zero"
else
    assert_eq "missing --output-branch arg exits non-zero" "nonzero" "nonzero"
fi
rm -rf "$TMPDIR7E"

# --- Test 7f: unsafe --output-branch values are rejected at the write site ---
# Git accepts refs containing shell metacharacters, and the recorded value is
# later substituted by an agent into shell commands, where quoting does NOT
# help ("dev$(id)" executes inside double quotes). Reject them here so the
# payload can never reach the plan header.
echo "--- Test 7f: --output-branch rejects unsafe branch names ---"
TMPDIR7F=$(new_sandbox)
make_fresh_internal "$TMPDIR7F/fakehome/.claude/plans/one-recent.md"
for payload in 'dev$(id -u)' 'dev`id -u`' "dev'x" 'dev;id' 'dev|x' 'dev&&x' 'dev"x'; do
    if run_externalize "$TMPDIR7F" "$TMPDIR7F/fakehome/.claude/plans" 999 --force \
            --output-branch "$payload" >/dev/null 2>&1; then
        assert_eq "unsafe --output-branch rejected: $payload" "rejected" "accepted"
    else
        assert_eq "unsafe --output-branch rejected: $payload" "rejected" "rejected"
    fi
done
# Non-execution proof: nothing ran, so no uid can appear in any produced plan.
leaked=$(grep -rl "$(id -u)" "$TMPDIR7F/aiplans" 2>/dev/null | wc -l | tr -d ' ')
assert_eq "no command substitution executed while validating" "0" "$leaked"
# A legitimate branch name with the allowed charset still works.
run_externalize "$TMPDIR7F" "$TMPDIR7F/fakehome/.claude/plans" 999 --force \
    --output-branch "feature/ok-1.2_x" >/dev/null
out_field=$(grep '^Output branch:' "$TMPDIR7F/aiplans/p999_sandbox_task.md" || true)
assert_eq "safe branch name accepted" "Output branch: feature/ok-1.2_x" "$out_field"
rm -rf "$TMPDIR7F"

# --- Test 7g: --profile resolves output_branch through a real YAML parser ---
# A sed on the right-hand side would carry YAML syntax into the value, so the
# equally valid quoted / commented forms would fail validation even though the
# renderer parses them all as `dev`.
echo "--- Test 7g: --profile YAML scalar forms ---"
TMPDIR7G=$(new_sandbox)
mkdir -p "$TMPDIR7G/prof"
for form in 'output_branch: dev' 'output_branch: "dev"' "output_branch: 'dev'" 'output_branch: dev # integration'; do
    printf 'name: p\n%s\n' "$form" > "$TMPDIR7G/prof/p.yaml"
    make_fresh_internal "$TMPDIR7G/fakehome/.claude/plans/one-recent.md"
    run_externalize "$TMPDIR7G" "$TMPDIR7G/fakehome/.claude/plans" 999 --force \
        --profile "$TMPDIR7G/prof/p.yaml" >/dev/null
    out_field=$(grep '^Output branch:' "$TMPDIR7G/aiplans/p999_sandbox_task.md" || true)
    assert_eq "profile form resolves to dev: $form" "Output branch: dev" "$out_field"
done

# Absent key: the common case for every shipped profile. This MUST succeed and
# fall back to the detected primary -- not stall or produce an empty value.
printf 'name: p\ndescription: no output_branch here\n' > "$TMPDIR7G/prof/p.yaml"
make_fresh_internal "$TMPDIR7G/fakehome/.claude/plans/one-recent.md"
result=$(run_externalize "$TMPDIR7G" "$TMPDIR7G/fakehome/.claude/plans" 999 --force \
    --profile "$TMPDIR7G/prof/p.yaml" 2>&1)
assert_contains "absent output_branch still externalizes" "OVERWRITTEN:" "$result"
out_field=$(grep '^Output branch:' "$TMPDIR7G/aiplans/p999_sandbox_task.md" || true)
assert_eq "absent output_branch falls back to the primary branch" "Output branch: main" "$out_field"
base_field=$(grep '^Base branch:' "$TMPDIR7G/aiplans/p999_sandbox_task.md" || true)
assert_eq "absent output_branch matches Base branch" "Base branch: main" "$base_field"

# An injected payload in the profile is rejected, and nothing executes.
printf 'name: p\noutput_branch: "dev$(id -u)"\n' > "$TMPDIR7G/prof/bad.yaml"
make_fresh_internal "$TMPDIR7G/fakehome/.claude/plans/one-recent.md"
if run_externalize "$TMPDIR7G" "$TMPDIR7G/fakehome/.claude/plans" 999 --force \
        --profile "$TMPDIR7G/prof/bad.yaml" >/dev/null 2>&1; then
    assert_eq "profile injection payload rejected" "rejected" "accepted"
else
    assert_eq "profile injection payload rejected" "rejected" "rejected"
fi
leaked=$(grep -c "$(id -u)" "$TMPDIR7G/aiplans/p999_sandbox_task.md" || true)
assert_eq "profile injection did not execute" "0" "$leaked"
rm -rf "$TMPDIR7G"

# --- Test 7h: unset output_branch falls back to the RESOLVED base branch ---
# The headline contract is "output_branch defaults to base_branch". Falling back
# to the repository primary instead would merge to the wrong branch for any
# project that bases worktrees on an integration branch.
echo "--- Test 7h: output_branch defaults to base_branch ---"
TMPDIR7H=$(new_sandbox)
mkdir -p "$TMPDIR7H/prof"

printf 'name: p\nbase_branch: dev\n' > "$TMPDIR7H/prof/p.yaml"
make_fresh_internal "$TMPDIR7H/fakehome/.claude/plans/one-recent.md"
run_externalize "$TMPDIR7H" "$TMPDIR7H/fakehome/.claude/plans" 999 --force \
    --profile "$TMPDIR7H/prof/p.yaml" >/dev/null
out_field=$(grep '^Output branch:' "$TMPDIR7H/aiplans/p999_sandbox_task.md" || true)
assert_eq "profile base_branch becomes the merge target" "Output branch: dev" "$out_field"
base_field=$(grep '^Base branch:' "$TMPDIR7H/aiplans/p999_sandbox_task.md" || true)
assert_eq "Base branch field is untouched by the fallback" "Base branch: main" "$base_field"

# Interactively chosen base branch (not in the profile) reaches the same place.
printf 'name: p\n' > "$TMPDIR7H/prof/bare.yaml"
make_fresh_internal "$TMPDIR7H/fakehome/.claude/plans/one-recent.md"
run_externalize "$TMPDIR7H" "$TMPDIR7H/fakehome/.claude/plans" 999 --force \
    --profile "$TMPDIR7H/prof/bare.yaml" --output-branch-default release >/dev/null
out_field=$(grep '^Output branch:' "$TMPDIR7H/aiplans/p999_sandbox_task.md" || true)
assert_eq "interactive base branch becomes the merge target" "Output branch: release" "$out_field"

# An explicit output_branch still wins over the base-branch fallback.
printf 'name: p\nbase_branch: dev\noutput_branch: staging\n' > "$TMPDIR7H/prof/both.yaml"
make_fresh_internal "$TMPDIR7H/fakehome/.claude/plans/one-recent.md"
run_externalize "$TMPDIR7H" "$TMPDIR7H/fakehome/.claude/plans" 999 --force \
    --profile "$TMPDIR7H/prof/both.yaml" >/dev/null
out_field=$(grep '^Output branch:' "$TMPDIR7H/aiplans/p999_sandbox_task.md" || true)
assert_eq "explicit output_branch wins over base_branch" "Output branch: staging" "$out_field"
rm -rf "$TMPDIR7H"

# --- Test 7i: unreadable profiles fail closed ---
# Silently recording the primary branch would discard a configured merge target
# and only surface as a wrong merge, long after the mistake.
echo "--- Test 7i: profile read failures fail closed ---"
TMPDIR7I=$(new_sandbox)
mkdir -p "$TMPDIR7I/prof"
printf 'name: p\n  bad: [unclosed\n' > "$TMPDIR7I/prof/malformed.yaml"
printf -- '- a\n- b\n' > "$TMPDIR7I/prof/list.yaml"
for bad in "$TMPDIR7I/prof/missing.yaml" "$TMPDIR7I/prof/malformed.yaml" "$TMPDIR7I/prof/list.yaml"; do
    make_fresh_internal "$TMPDIR7I/fakehome/.claude/plans/one-recent.md"
    if run_externalize "$TMPDIR7I" "$TMPDIR7I/fakehome/.claude/plans" 999 --force \
            --profile "$bad" >/dev/null 2>&1; then
        assert_eq "unreadable profile fails closed: $(basename "$bad")" "died" "succeeded"
    else
        assert_eq "unreadable profile fails closed: $(basename "$bad")" "died" "died"
    fi
done
rm -rf "$TMPDIR7I"

# --- Test 7j: output_branch is ignored outside worktree mode ---
# The schema documents it as worktree-only. Recording it anyway leaves a stale
# merge target a later session could consume.
echo "--- Test 7j: output_branch ignored without a worktree ---"
TMPDIR7J=$(new_sandbox)
mkdir -p "$TMPDIR7J/prof"
printf 'name: p\ncreate_worktree: false\noutput_branch: dev\n' > "$TMPDIR7J/prof/nw.yaml"
make_fresh_internal "$TMPDIR7J/fakehome/.claude/plans/one-recent.md"
run_externalize "$TMPDIR7J" "$TMPDIR7J/fakehome/.claude/plans" 999 --force \
    --profile "$TMPDIR7J/prof/nw.yaml" >/dev/null
out_field=$(grep '^Output branch:' "$TMPDIR7J/aiplans/p999_sandbox_task.md" || true)
assert_eq "create_worktree:false ignores output_branch" "Output branch: main" "$out_field"

# The --no-worktree flag has the same effect for an interactive resolution.
printf 'name: p\noutput_branch: dev\n' > "$TMPDIR7J/prof/wt.yaml"
make_fresh_internal "$TMPDIR7J/fakehome/.claude/plans/one-recent.md"
run_externalize "$TMPDIR7J" "$TMPDIR7J/fakehome/.claude/plans" 999 --force \
    --profile "$TMPDIR7J/prof/wt.yaml" --no-worktree >/dev/null
out_field=$(grep '^Output branch:' "$TMPDIR7J/aiplans/p999_sandbox_task.md" || true)
assert_eq "--no-worktree ignores output_branch" "Output branch: main" "$out_field"

# Positive control: the SAME profile in worktree mode does record it.
make_fresh_internal "$TMPDIR7J/fakehome/.claude/plans/one-recent.md"
run_externalize "$TMPDIR7J" "$TMPDIR7J/fakehome/.claude/plans" 999 --force \
    --profile "$TMPDIR7J/prof/wt.yaml" >/dev/null
out_field=$(grep '^Output branch:' "$TMPDIR7J/aiplans/p999_sandbox_task.md" || true)
assert_eq "worktree mode records output_branch" "Output branch: dev" "$out_field"
rm -rf "$TMPDIR7J"

# --- Test 7k: YAML scalars are validated INSIDE the parser ---
# The profile reader speaks a newline-delimited key=value protocol, so a scalar
# containing a newline (valid YAML via "dev\\nbase_branch=release") injects a
# second record. The record split happens before any downstream charset check
# could see it, so validation must happen before serialisation.
echo "--- Test 7k: profile scalar record-injection ---"
TMPDIR7K=$(new_sandbox)
mkdir -p "$TMPDIR7K/prof"
cat > "$TMPDIR7K/prof/inj.yaml" <<'YAML'
name: p
output_branch: "dev\nbase_branch=release"
YAML
make_fresh_internal "$TMPDIR7K/fakehome/.claude/plans/one-recent.md"
if run_externalize "$TMPDIR7K" "$TMPDIR7K/fakehome/.claude/plans" 999 --force \
        --profile "$TMPDIR7K/prof/inj.yaml" >/dev/null 2>&1; then
    assert_eq "newline-injected profile scalar rejected" "rejected" "accepted"
else
    assert_eq "newline-injected profile scalar rejected" "rejected" "rejected"
fi
# A non-scalar type must be rejected too, not coerced.
printf 'name: p\noutput_branch:\n  - a\n  - b\n' > "$TMPDIR7K/prof/list.yaml"
make_fresh_internal "$TMPDIR7K/fakehome/.claude/plans/one-recent.md"
if run_externalize "$TMPDIR7K" "$TMPDIR7K/fakehome/.claude/plans" 999 --force \
        --profile "$TMPDIR7K/prof/list.yaml" >/dev/null 2>&1; then
    assert_eq "non-scalar output_branch rejected" "rejected" "accepted"
else
    assert_eq "non-scalar output_branch rejected" "rejected" "rejected"
fi
rm -rf "$TMPDIR7K"

# --- Test 7l: the file channel for interactively supplied branches ---
# Passing such a value on the command line would let "release$(id -u)" expand
# before the helper could validate it; a file is never shell-evaluated.
echo "--- Test 7l: --output-branch-default-file ---"
TMPDIR7L=$(new_sandbox)
printf 'release\n' > "$TMPDIR7L/branch.txt"
make_fresh_internal "$TMPDIR7L/fakehome/.claude/plans/one-recent.md"
run_externalize "$TMPDIR7L" "$TMPDIR7L/fakehome/.claude/plans" 999 --force \
    --output-branch-default-file "$TMPDIR7L/branch.txt" >/dev/null
out_field=$(grep '^Output branch:' "$TMPDIR7L/aiplans/p999_sandbox_task.md" || true)
assert_eq "file channel supplies the fallback target" "Output branch: release" "$out_field"

printf 'release$(id -u)\n' > "$TMPDIR7L/branch.txt"
make_fresh_internal "$TMPDIR7L/fakehome/.claude/plans/one-recent.md"
if run_externalize "$TMPDIR7L" "$TMPDIR7L/fakehome/.claude/plans" 999 --force \
        --output-branch-default-file "$TMPDIR7L/branch.txt" >/dev/null 2>&1; then
    assert_eq "file channel rejects an unsafe value" "rejected" "accepted"
else
    assert_eq "file channel rejects an unsafe value" "rejected" "rejected"
fi
leaked=$(grep -c "$(id -u)" "$TMPDIR7L/aiplans/p999_sandbox_task.md" || true)
assert_eq "file channel payload did not execute" "0" "$leaked"

for bad_case in missing empty; do
    if [ "$bad_case" = empty ]; then : > "$TMPDIR7L/bad.txt"; fi
    make_fresh_internal "$TMPDIR7L/fakehome/.claude/plans/one-recent.md"
    if run_externalize "$TMPDIR7L" "$TMPDIR7L/fakehome/.claude/plans" 999 --force \
            --output-branch-default-file "$TMPDIR7L/bad.txt" >/dev/null 2>&1; then
        assert_eq "file channel fails closed: $bad_case" "died" "succeeded"
    else
        assert_eq "file channel fails closed: $bad_case" "died" "died"
    fi
done
rm -rf "$TMPDIR7L"

# --- Test 7m: the no-profile path (manual / resume invocations) ---
# active_profile_filename is null there, so --profile is omitted entirely. This
# must still externalize and honour an interactively resolved base branch.
echo "--- Test 7m: no --profile supplied ---"
TMPDIR7M=$(new_sandbox)
make_fresh_internal "$TMPDIR7M/fakehome/.claude/plans/one-recent.md"
result=$(run_externalize "$TMPDIR7M" "$TMPDIR7M/fakehome/.claude/plans" 999 --force 2>&1)
assert_contains "no profile: still externalizes" "EXTERNALIZED:" "$result"
out_field=$(grep '^Output branch:' "$TMPDIR7M/aiplans/p999_sandbox_task.md" || true)
assert_eq "no profile: falls back to the primary branch" "Output branch: main" "$out_field"

printf 'release\n' > "$TMPDIR7M/branch.txt"
make_fresh_internal "$TMPDIR7M/fakehome/.claude/plans/one-recent.md"
run_externalize "$TMPDIR7M" "$TMPDIR7M/fakehome/.claude/plans" 999 --force \
    --output-branch-default-file "$TMPDIR7M/branch.txt" --no-worktree >/dev/null
out_field=$(grep '^Output branch:' "$TMPDIR7M/aiplans/p999_sandbox_task.md" || true)
assert_eq "no profile + --no-worktree ignores the fallback" "Output branch: main" "$out_field"
rm -rf "$TMPDIR7M"

# --- Test 7n: no-worktree mode is authoritative over every derived target ---
echo "--- Test 7n: no-worktree clears derived targets and stale headers ---"
TMPDIR7N=$(new_sandbox)
mkdir -p "$TMPDIR7N/prof"
printf 'name: p\ncreate_worktree: false\nbase_branch: dev\n' > "$TMPDIR7N/prof/nw.yaml"
make_fresh_internal "$TMPDIR7N/fakehome/.claude/plans/one-recent.md"
run_externalize "$TMPDIR7N" "$TMPDIR7N/fakehome/.claude/plans" 999 --force \
    --profile "$TMPDIR7N/prof/nw.yaml" >/dev/null
out_field=$(grep '^Output branch:' "$TMPDIR7N/aiplans/p999_sandbox_task.md" || true)
assert_eq "no-worktree suppresses the base_branch fallback too" "Output branch: main" "$out_field"

# A stale value already in the source frontmatter must be overwritten, not kept.
cat > "$TMPDIR7N/fakehome/.claude/plans/with_front.md" <<'EOF'
---
Task: t999_sandbox_task.md
Output branch: stale
---

# body
EOF
rm -f "$TMPDIR7N/fakehome/.claude/plans/one-recent.md"
run_externalize "$TMPDIR7N" "$TMPDIR7N/fakehome/.claude/plans" 999 --force \
    --profile "$TMPDIR7N/prof/nw.yaml" >/dev/null
out_field=$(grep '^Output branch:' "$TMPDIR7N/aiplans/p999_sandbox_task.md" || true)
assert_eq "no-worktree overwrites a stale frontmatter target" "Output branch: main" "$out_field"
rm -rf "$TMPDIR7N"

# --- Test 7o: the MULTIPLE_CANDIDATES retry must keep the resolution flags ---
# The retry is the call that actually writes the header, so dropping --profile
# there silently replaces a configured merge target with the primary branch.
echo "--- Test 7o: two-candidate retry preserves the merge target ---"
TMPDIR7O=$(new_sandbox)
mkdir -p "$TMPDIR7O/prof"
printf 'name: p\noutput_branch: dev\n' > "$TMPDIR7O/prof/p.yaml"
make_fresh_internal "$TMPDIR7O/fakehome/.claude/plans/cand_a.md"
make_fresh_internal "$TMPDIR7O/fakehome/.claude/plans/cand_b.md"
result=$(run_externalize "$TMPDIR7O" "$TMPDIR7O/fakehome/.claude/plans" 999 --force \
    --profile "$TMPDIR7O/prof/p.yaml" 2>&1)
assert_contains "two candidates produce MULTIPLE_CANDIDATES" "MULTIPLE_CANDIDATES:" "$result"
# The documented retry: --internal <chosen> plus the FULL original flag set.
run_externalize "$TMPDIR7O" "$TMPDIR7O/fakehome/.claude/plans" 999 \
    --internal "$TMPDIR7O/fakehome/.claude/plans/cand_a.md" --force \
    --profile "$TMPDIR7O/prof/p.yaml" >/dev/null
out_field=$(grep '^Output branch:' "$TMPDIR7O/aiplans/p999_sandbox_task.md" || true)
assert_eq "retry with the branch flags keeps the merge target" "Output branch: dev" "$out_field"
rm -rf "$TMPDIR7O"

# --- Test 7p: the value file must hold exactly one branch name ---
# head -n1 would silently turn an invalid multi-line file into a DIFFERENT
# branch rather than rejecting it.
echo "--- Test 7p: --output-branch-default-file multiline rejection ---"
TMPDIR7P=$(new_sandbox)
printf 'release\nstaging\n' > "$TMPDIR7P/two.txt"
printf 'release\n\n'        > "$TMPDIR7P/blank.txt"
printf 'release\r\n'        > "$TMPDIR7P/crlf.txt"
for f in two blank crlf; do
    make_fresh_internal "$TMPDIR7P/fakehome/.claude/plans/one-recent.md"
    if run_externalize "$TMPDIR7P" "$TMPDIR7P/fakehome/.claude/plans" 999 --force \
            --output-branch-default-file "$TMPDIR7P/$f.txt" >/dev/null 2>&1; then
        assert_eq "value file rejected: $f" "died" "succeeded"
    else
        assert_eq "value file rejected: $f" "died" "died"
    fi
done
# Positive controls: one line, with and without a terminating newline.
for f in lf nolf; do
    if [ "$f" = lf ]; then printf 'release\n' > "$TMPDIR7P/$f.txt"; else printf 'release' > "$TMPDIR7P/$f.txt"; fi
    make_fresh_internal "$TMPDIR7P/fakehome/.claude/plans/one-recent.md"
    run_externalize "$TMPDIR7P" "$TMPDIR7P/fakehome/.claude/plans" 999 --force \
        --output-branch-default-file "$TMPDIR7P/$f.txt" >/dev/null
    out_field=$(grep '^Output branch:' "$TMPDIR7P/aiplans/p999_sandbox_task.md" || true)
    assert_eq "single-line value file accepted: $f" "Output branch: release" "$out_field"
done
rm -rf "$TMPDIR7P"

# --- Test 7q: full Step 6 -> cleanup -> Step 8 sequence ---
# Step 8 reuses the same branch flags, and the scratch value file may already be
# gone. A no-op Step 8 must still short-circuit to PLAN_EXISTS rather than
# failing on a resolution input it would never have used.
echo "--- Test 7q: Step 6 / cleanup / Step 8 lifecycle ---"
TMPDIR7Q=$(new_sandbox)
printf 'release\n' > "$TMPDIR7Q/branch.txt"
make_fresh_internal "$TMPDIR7Q/fakehome/.claude/plans/one-recent.md"
result=$(run_externalize "$TMPDIR7Q" "$TMPDIR7Q/fakehome/.claude/plans" 999 --force \
    --output-branch-default-file "$TMPDIR7Q/branch.txt" 2>&1)
assert_contains "step 6 externalizes" "EXTERNALIZED:" "$result"
out_field=$(grep '^Output branch:' "$TMPDIR7Q/aiplans/p999_sandbox_task.md" || true)
assert_eq "step 6 records the interactive target" "Output branch: release" "$out_field"

rm -f "$TMPDIR7Q/branch.txt"          # the documented cleanup
# `|| true` so a regression reports FAIL instead of aborting the suite under
# `set -e` -- an aborted run shows zero failures and silently proves nothing.
result=$(run_externalize "$TMPDIR7Q" "$TMPDIR7Q/fakehome/.claude/plans" 999 \
    --output-branch-default-file "$TMPDIR7Q/branch.txt" 2>&1 || true)
assert_contains "step 8 short-circuits despite the removed value file" \
    "PLAN_EXISTS:" "$result"
out_field=$(grep '^Output branch:' "$TMPDIR7Q/aiplans/p999_sandbox_task.md" || true)
assert_eq "step 8 leaves the recorded target intact" "Output branch: release" "$out_field"

# A call that WOULD write the header must still fail closed on the missing file.
if run_externalize "$TMPDIR7Q" "$TMPDIR7Q/fakehome/.claude/plans" 999 --force \
        --output-branch-default-file "$TMPDIR7Q/branch.txt" >/dev/null 2>&1; then
    assert_eq "a writing call still fails closed on a missing value file" "died" "succeeded"
else
    assert_eq "a writing call still fails closed on a missing value file" "died" "died"
fi
rm -rf "$TMPDIR7Q"

# --- Test 7r: no-profile current-branch mode clears a stale target ---
# The documented minimal flag set for current-branch mode is --no-worktree, not
# an empty one: without it OUTPUT_INTENT stays false and a stale header survives.
echo "--- Test 7r: no-profile current-branch vs stale frontmatter ---"
TMPDIR7R=$(new_sandbox)
cat > "$TMPDIR7R/fakehome/.claude/plans/with_front.md" <<'EOF'
---
Task: t999_sandbox_task.md
Output branch: stale
---

# body
EOF
run_externalize "$TMPDIR7R" "$TMPDIR7R/fakehome/.claude/plans" 999 --force --no-worktree >/dev/null
out_field=$(grep '^Output branch:' "$TMPDIR7R/aiplans/p999_sandbox_task.md" || true)
assert_eq "no-profile --no-worktree clears the stale target" "Output branch: main" "$out_field"
rm -rf "$TMPDIR7R"

# --- Test 8: AIT_PLAN_EXTERNALIZE_MAX_AGE_SECS widens window ---
echo "--- Test 8: age-window env var ---"
TMPDIR8=$(new_sandbox)
make_fresh_internal "$TMPDIR8/fakehome/.claude/plans/twohours.md"
make_old "$TMPDIR8/fakehome/.claude/plans/twohours.md" 2
result=$(
    cd "$TMPDIR8" && \
    AIT_PLAN_EXTERNALIZE_INTERNAL_DIR="$TMPDIR8/fakehome/.claude/plans" \
    AIT_PLAN_EXTERNALIZE_MAX_AGE_SECS=14400 \
    "$EXTERNALIZE" 999
)
assert_contains "widened window: EXTERNALIZED (includes 2h-old file)" "EXTERNALIZED:" "$result"
rm -rf "$TMPDIR8"

# --- Test 9: Unknown task id → NOT_FOUND:no_task_file ---
echo "--- Test 9: unknown task id ---"
TMPDIR9=$(new_sandbox)
make_fresh_internal "$TMPDIR9/fakehome/.claude/plans/whatever.md"
result=$(run_externalize "$TMPDIR9" "$TMPDIR9/fakehome/.claude/plans" 12345)
assert_contains "unknown task: NOT_FOUND:no_task_file" "NOT_FOUND:no_task_file" "$result"
rm -rf "$TMPDIR9"

# --- Test 10: --force overwrites existing external plan → OVERWRITTEN ---
echo "--- Test 10: --force overwrites existing plan ---"
TMPDIR10=$(new_sandbox)
make_fresh_internal "$TMPDIR10/fakehome/.claude/plans/first.md"
run_externalize "$TMPDIR10" "$TMPDIR10/fakehome/.claude/plans" 999 >/dev/null
# Replace the internal plan with new content that carries a unique marker
cat > "$TMPDIR10/fakehome/.claude/plans/first.md" <<'EOF'
# Sandbox plan v2

UNIQUE_MARKER_FORCE_OVERWRITE_LINE
- Revised step 1
- Revised step 2
EOF
result=$(run_externalize "$TMPDIR10" "$TMPDIR10/fakehome/.claude/plans" 999 --force)
assert_contains "force: OVERWRITTEN prefix" "OVERWRITTEN:aiplans/p999_sandbox_task.md:" "$result"
marker=$(grep 'UNIQUE_MARKER_FORCE_OVERWRITE_LINE' "$TMPDIR10/aiplans/p999_sandbox_task.md" || true)
assert_contains "force: overwritten file contains new content" "UNIQUE_MARKER_FORCE_OVERWRITE_LINE" "$marker"
rm -rf "$TMPDIR10"

# --- Test 11: --force with no existing external plan → EXTERNALIZED ---
echo "--- Test 11: --force with no existing plan ---"
TMPDIR11=$(new_sandbox)
make_fresh_internal "$TMPDIR11/fakehome/.claude/plans/fresh.md"
result=$(run_externalize "$TMPDIR11" "$TMPDIR11/fakehome/.claude/plans" 999 --force)
assert_contains "force fresh: EXTERNALIZED prefix" "EXTERNALIZED:aiplans/p999_sandbox_task.md:" "$result"
assert_file_exists "force fresh: external plan created" "$TMPDIR11/aiplans/p999_sandbox_task.md"
# Ensure OVERWRITTEN is NOT emitted for a fresh externalize (backward compat)
if echo "$result" | grep -q 'OVERWRITTEN:'; then
    FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
    echo "FAIL: force fresh: did not expect OVERWRITTEN token"
    echo "  actual: $result"
else
    PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1))
fi
rm -rf "$TMPDIR11"

# --- Test 12: --force with no internal source preserves existing external plan ---
echo "--- Test 12: --force with empty internal dir preserves existing plan ---"
TMPDIR12=$(new_sandbox)
make_fresh_internal "$TMPDIR12/fakehome/.claude/plans/original.md"
run_externalize "$TMPDIR12" "$TMPDIR12/fakehome/.claude/plans" 999 >/dev/null
# Capture the externalized plan's checksum before the force attempt
before_hash=$(md5sum "$TMPDIR12/aiplans/p999_sandbox_task.md" | awk '{print $1}')
# Empty the internal plans dir so nothing is eligible
rm -f "$TMPDIR12/fakehome/.claude/plans/original.md"
result=$(run_externalize "$TMPDIR12" "$TMPDIR12/fakehome/.claude/plans" 999 --force)
assert_contains "force empty src: NOT_FOUND:no_internal_files" "NOT_FOUND:no_internal_files" "$result"
assert_file_exists "force empty src: external plan still exists" "$TMPDIR12/aiplans/p999_sandbox_task.md"
after_hash=$(md5sum "$TMPDIR12/aiplans/p999_sandbox_task.md" | awk '{print $1}')
assert_eq "force empty src: external plan unchanged" "$before_hash" "$after_hash"
rm -rf "$TMPDIR12"

# --- Test 13: master-default repo records Base branch: master (t1031) ---
echo "--- Test 13: master-default repo Base branch ---"
TMPDIR13=$(new_sandbox)
make_fresh_internal "$TMPDIR13/fakehome/.claude/plans/master-repo.md"
(
    cd "$TMPDIR13"
    git init --quiet
    git config user.email "test@test.com"
    git config user.name "Test"
    git add -A
    git commit -m "initial" --quiet
    # master is the primary branch; main does not exist
    git branch -M master
)
run_externalize "$TMPDIR13" "$TMPDIR13/fakehome/.claude/plans" 999 >/dev/null
base_field=$(grep '^Base branch:' "$TMPDIR13/aiplans/p999_sandbox_task.md" || true)
assert_eq "master-default: Base branch is master" "Base branch: master" "$base_field"
out_field=$(grep '^Output branch:' "$TMPDIR13/aiplans/p999_sandbox_task.md" || true)
assert_eq "master-default: Output branch defaults to master" "Output branch: master" "$out_field"
# current branch == primary (master) → no stray Branch: line
branch_field=$(grep -c '^Branch:' "$TMPDIR13/aiplans/p999_sandbox_task.md" || true)
assert_eq "master-default: no Branch line when on primary" "0" "$branch_field"
rm -rf "$TMPDIR13"

# --- Results ---

echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
