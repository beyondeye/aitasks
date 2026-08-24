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
# t1277: the profile's base_branch is now ALSO the recorded base. Both fields in
# one header derive from one resolution -- previously this read `main` while the
# merge target read `dev`, and Re-entry Routing consumed the wrong one.
base_field=$(grep '^Base branch:' "$TMPDIR7H/aiplans/p999_sandbox_task.md" || true)
assert_eq "profile base_branch is also the recorded base" "Base branch: dev" "$base_field"

# The LEGACY flag still reaches the merge target -- and, unlike --base-branch,
# still leaves `Base branch:` alone. That base-neutrality is the whole reason the
# flag is retained (t1277); an interactively chosen base goes through
# --base-branch-file instead (Test 14).
printf 'name: p\n' > "$TMPDIR7H/prof/bare.yaml"
make_fresh_internal "$TMPDIR7H/fakehome/.claude/plans/one-recent.md"
run_externalize "$TMPDIR7H" "$TMPDIR7H/fakehome/.claude/plans" 999 --force \
    --profile "$TMPDIR7H/prof/bare.yaml" --output-branch-default release >/dev/null
out_field=$(grep '^Output branch:' "$TMPDIR7H/aiplans/p999_sandbox_task.md" || true)
assert_eq "legacy default becomes the merge target" "Output branch: release" "$out_field"
base_field=$(grep '^Base branch:' "$TMPDIR7H/aiplans/p999_sandbox_task.md" || true)
assert_eq "legacy default stays base-neutral" "Base branch: main" "$base_field"

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
# ...and the recorded base is suppressed with it: nothing is cut in current-branch
# mode, so `base_branch: dev` must not be presented as the fork point (t1277).
base_field=$(grep '^Base branch:' "$TMPDIR7N/aiplans/p999_sandbox_task.md" || true)
assert_eq "no-worktree suppresses the recorded base too" "Base branch: main" "$base_field"

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

# --- Test 7s: characterization of the whole Output branch resolution matrix ---
# The individual rungs are asserted piecemeal above (7d/7g/7h/7j/7n), which is
# enough to catch a rung that stops working but NOT enough to catch a rung that
# starts outranking another. This table pins every combination in one place so
# any reshuffle of the precedence chain is a named failure rather than a merge
# to the wrong branch discovered at Step 9. Written BEFORE t1277 touched the
# chain, and required to stay green through it.
echo "--- Test 7s: Output branch resolution matrix ---"
TMPDIR7S=$(new_sandbox)
mkdir -p "$TMPDIR7S/prof"
printf 'release\n' > "$TMPDIR7S/release.txt"

# label | profile body ('-' = pass no --profile) | extra flags | expected Output branch
while IFS='|' read -r s_label s_prof s_extra s_expect; do
    [ -n "$s_label" ] || continue
    s_prof_flag=""
    if [ "$s_prof" != "-" ]; then
        { printf 'name: p\n'; printf '%b' "$s_prof"; } > "$TMPDIR7S/prof/case.yaml"
        s_prof_flag="--profile $TMPDIR7S/prof/case.yaml"
    fi
    s_extra=${s_extra//@BRANCHFILE@/$TMPDIR7S/release.txt}
    make_fresh_internal "$TMPDIR7S/fakehome/.claude/plans/one-recent.md"
    # shellcheck disable=SC2086  # deliberate word-splitting of the flag lists
    run_externalize "$TMPDIR7S" "$TMPDIR7S/fakehome/.claude/plans" 999 --force \
        $s_prof_flag $s_extra >/dev/null </dev/null
    out_field=$(grep '^Output branch:' "$TMPDIR7S/aiplans/p999_sandbox_task.md" || true)
    assert_eq "output matrix [$s_label]" "Output branch: $s_expect" "$out_field"
done <<'CASES'
no flags at all|-||main
--output-branch|-|--output-branch dev|dev
profile output_branch|output_branch: dev\n||dev
profile output_branch + --output-branch|output_branch: dev\n|--output-branch staging|staging
--output-branch-default|-|--output-branch-default release|release
--output-branch-default-file|-|--output-branch-default-file @BRANCHFILE@|release
profile base_branch|base_branch: dev\n||dev
profile base_branch + --output-branch-default|base_branch: dev\n|--output-branch-default release|release
profile base_branch + profile output_branch|base_branch: dev\noutput_branch: staging\n||staging
profile base_branch + --output-branch|base_branch: dev\n|--output-branch staging|staging
--no-worktree|-|--no-worktree|main
--output-branch + --no-worktree|-|--output-branch dev --no-worktree|main
profile output_branch + --no-worktree|output_branch: dev\n|--no-worktree|main
profile base_branch + --no-worktree|base_branch: dev\n|--no-worktree|main
--output-branch-default + --no-worktree|-|--output-branch-default release --no-worktree|main
create_worktree false + output_branch|create_worktree: false\noutput_branch: dev\n||main
create_worktree false + base_branch|create_worktree: false\nbase_branch: dev\n||main
CASES
rm -rf "$TMPDIR7S"

# --- Test 7t: --force rebuild replaces a stale external header ---
# The t1578 shape: the stale pair lives in the EXISTING EXTERNAL plan and the
# internal source has NO frontmatter, so the header is rebuilt by build_header()
# rather than spliced. Every other --no-worktree test seeds the stale value in the
# SOURCE frontmatter and therefore only exercises the splice.
#
# Stale values are non-primary on purpose: `main` -> `main` asserts nothing, which
# is exactly why the original report read the overwrite as a no-op (t1578).
#
# The contract is REPLACEMENT with the detected primary, not deletion: only
# `Worktree:` is actually removed. The final block characterizes the asymmetry the
# corrected doc states -- on this path build_header() writes both fields
# unconditionally, so the per-field intent gating never applies and a bare --force
# replaces them just as thoroughly. It is expected to pass with the same values;
# the real negative controls for intent gating live in Test 14c.
echo "--- Test 7t: --force rebuild replaces a stale external header ---"
TMPDIR7T=$(new_sandbox)
mkdir -p "$TMPDIR7T/prof"
printf 'name: fast\ncreate_worktree: false\n' > "$TMPDIR7T/prof/fast.yaml"
write_stale_external_7t() {
    cat > "$TMPDIR7T/aiplans/p999_sandbox_task.md" <<'EOF'
---
Task: t999_sandbox_task.md
Worktree: aiwork/t999_sandbox_task
Base branch: dev
Output branch: dev
---

# old body
EOF
}
write_stale_external_7t
make_fresh_internal "$TMPDIR7T/fakehome/.claude/plans/one-recent.md"
result=$(run_externalize "$TMPDIR7T" "$TMPDIR7T/fakehome/.claude/plans" 999 --force \
    --profile "$TMPDIR7T/prof/fast.yaml" --no-worktree)
plan="$TMPDIR7T/aiplans/p999_sandbox_task.md"
assert_contains "7t: existing external plan is OVERWRITTEN" "OVERWRITTEN:" "$result"
assert_eq "7t: stale base replaced by the primary" "Base branch: main" \
    "$(grep '^Base branch:' "$plan" || true)"
assert_eq "7t: stale output replaced by the primary" "Output branch: main" \
    "$(grep '^Output branch:' "$plan" || true)"
assert_eq "7t: stale Worktree line removed" "0" \
    "$(grep -c '^Worktree:' "$plan" || true)"
assert_eq "7t: exactly one base line" "1" "$(grep -c '^Base branch:' "$plan" || true)"
assert_eq "7t: exactly one output line" "1" "$(grep -c '^Output branch:' "$plan" || true)"
assert_eq "7t: frontmatter block intact" "2" "$(grep -c '^---$' "$plan" || true)"

write_stale_external_7t
run_externalize "$TMPDIR7T" "$TMPDIR7T/fakehome/.claude/plans" 999 --force >/dev/null 2>&1
assert_eq "7t: bare --force rebuild also replaces the stale base" "Base branch: main" \
    "$(grep '^Base branch:' "$plan" || true)"
assert_eq "7t: bare --force rebuild also replaces the stale output" "Output branch: main" \
    "$(grep '^Output branch:' "$plan" || true)"
rm -rf "$TMPDIR7T"

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

# --- Test 14: `Base branch:` records the RESOLVED base branch (t1277) ---
# Before t1277 this field came from detect_primary_branch() regardless of what
# Step 5 resolved, so a `base_branch: develop` profile produced a header reading
# `Base branch: main` while `Output branch:` in the SAME header read `develop`.
# Re-entry Routing resolves both branches from this header alone, so the field is
# what a resumed session cuts its worktree from -- not merely a label.
echo "--- Test 14: Base branch records the resolved base ---"
TMPDIR14=$(new_sandbox)
mkdir -p "$TMPDIR14/prof"

# Reads both header fields of the sandbox plan into base_field / out_field.
read_header_fields_14() {
    base_field=$(grep '^Base branch:' "$TMPDIR14/aiplans/p999_sandbox_task.md" || true)
    out_field=$(grep '^Output branch:' "$TMPDIR14/aiplans/p999_sandbox_task.md" || true)
}

# The headline acceptance: a profile base_branch reaches the header field.
printf 'name: p\nbase_branch: develop\n' > "$TMPDIR14/prof/dev.yaml"
make_fresh_internal "$TMPDIR14/fakehome/.claude/plans/one-recent.md"
run_externalize "$TMPDIR14" "$TMPDIR14/fakehome/.claude/plans" 999 --force \
    --profile "$TMPDIR14/prof/dev.yaml" >/dev/null
read_header_fields_14
assert_eq "profile base_branch: recorded base" "Base branch: develop" "$base_field"
assert_eq "profile base_branch: merge target defaults to it" "Output branch: develop" "$out_field"

# --base-branch with no profile at all (manual / resume invocations).
make_fresh_internal "$TMPDIR14/fakehome/.claude/plans/one-recent.md"
run_externalize "$TMPDIR14" "$TMPDIR14/fakehome/.claude/plans" 999 --force \
    --base-branch develop >/dev/null
read_header_fields_14
assert_eq "--base-branch: recorded base" "Base branch: develop" "$base_field"
assert_eq "--base-branch: merge target defaults to it" "Output branch: develop" "$out_field"

# The file channel, for a base branch the user chose interactively. Passing such a
# value on a command line would let "develop$(id -u)" expand before the helper
# could validate it; a file is never shell-evaluated.
printf 'develop\n' > "$TMPDIR14/base.txt"
make_fresh_internal "$TMPDIR14/fakehome/.claude/plans/one-recent.md"
run_externalize "$TMPDIR14" "$TMPDIR14/fakehome/.claude/plans" 999 --force \
    --base-branch-file "$TMPDIR14/base.txt" >/dev/null
read_header_fields_14
assert_eq "--base-branch-file: recorded base" "Base branch: develop" "$base_field"
assert_eq "--base-branch-file: merge target defaults to it" "Output branch: develop" "$out_field"

printf 'develop$(id -u)\n' > "$TMPDIR14/base.txt"
make_fresh_internal "$TMPDIR14/fakehome/.claude/plans/one-recent.md"
if run_externalize "$TMPDIR14" "$TMPDIR14/fakehome/.claude/plans" 999 --force \
        --base-branch-file "$TMPDIR14/base.txt" >/dev/null 2>&1; then
    assert_eq "--base-branch-file rejects an unsafe value" "rejected" "accepted"
else
    assert_eq "--base-branch-file rejects an unsafe value" "rejected" "rejected"
fi
leaked=$(grep -c "$(id -u)" "$TMPDIR14/aiplans/p999_sandbox_task.md" || true)
assert_eq "--base-branch-file payload did not execute" "0" "$leaked"

# Same fail-closed shape as the output value file: one line, non-empty, present.
printf 'develop\nstaging\n' > "$TMPDIR14/two.txt"
: > "$TMPDIR14/empty.txt"
for bad in two empty missing; do
    make_fresh_internal "$TMPDIR14/fakehome/.claude/plans/one-recent.md"
    if run_externalize "$TMPDIR14" "$TMPDIR14/fakehome/.claude/plans" 999 --force \
            --base-branch-file "$TMPDIR14/$bad.txt" >/dev/null 2>&1; then
        assert_eq "--base-branch-file fails closed: $bad" "died" "succeeded"
    else
        assert_eq "--base-branch-file fails closed: $bad" "died" "died"
    fi
done

# Unsafe direct values are rejected too, and a missing argument is a usage error.
for payload in 'dev$(id -u)' 'dev`id`' "dev'x" 'dev;id' 'dev branch'; do
    make_fresh_internal "$TMPDIR14/fakehome/.claude/plans/one-recent.md"
    if run_externalize "$TMPDIR14" "$TMPDIR14/fakehome/.claude/plans" 999 --force \
            --base-branch "$payload" >/dev/null 2>&1; then
        assert_eq "unsafe --base-branch rejected: $payload" "rejected" "accepted"
    else
        assert_eq "unsafe --base-branch rejected: $payload" "rejected" "rejected"
    fi
done
if run_externalize "$TMPDIR14" "$TMPDIR14/fakehome/.claude/plans" 999 --base-branch >/dev/null 2>&1; then
    assert_eq "missing --base-branch arg exits non-zero" "nonzero" "zero"
else
    assert_eq "missing --base-branch arg exits non-zero" "nonzero" "nonzero"
fi

# No base resolved at all -> the detected primary, i.e. behaviour unchanged. This
# is the clause Tests 1 and 13 also cover, restated beside the new behaviour.
make_fresh_internal "$TMPDIR14/fakehome/.claude/plans/one-recent.md"
run_externalize "$TMPDIR14" "$TMPDIR14/fakehome/.claude/plans" 999 --force \
    --output-branch-default release >/dev/null
read_header_fields_14
assert_eq "legacy default alone: base stays the primary" "Base branch: main" "$base_field"
assert_eq "legacy default alone: it still sets the merge target" "Output branch: release" "$out_field"
rm -rf "$TMPDIR14"

# --- Test 14b: precedence boundaries, one collision per row ---
# Each rung is exercised in isolation above, which cannot catch a rung that starts
# outranking another. An assignment landing in the wrong order would pick the
# wrong fork point or the wrong merge target while every isolated case still
# passed, so every boundary gets a named row asserting BOTH fields.
echo "--- Test 14b: base/output precedence boundaries ---"
TMPDIR14B=$(new_sandbox)
mkdir -p "$TMPDIR14B/prof"
printf 'beta\n'  > "$TMPDIR14B/beta.txt"
printf 'alpha\n' > "$TMPDIR14B/alpha.txt"

# label | profile body ('-' = no --profile) | extra flags | expected base | expected output
while IFS='|' read -r b_label b_prof b_extra b_base b_out; do
    [ -n "$b_label" ] || continue
    b_prof_flag=""
    if [ "$b_prof" != "-" ]; then
        { printf 'name: p\n'; printf '%b' "$b_prof"; } > "$TMPDIR14B/prof/case.yaml"
        b_prof_flag="--profile $TMPDIR14B/prof/case.yaml"
    fi
    b_extra=${b_extra//@BETA@/$TMPDIR14B/beta.txt}
    b_extra=${b_extra//@ALPHA@/$TMPDIR14B/alpha.txt}
    make_fresh_internal "$TMPDIR14B/fakehome/.claude/plans/one-recent.md"
    # shellcheck disable=SC2086  # deliberate word-splitting of the flag lists
    run_externalize "$TMPDIR14B" "$TMPDIR14B/fakehome/.claude/plans" 999 --force \
        $b_prof_flag $b_extra >/dev/null </dev/null
    base_field=$(grep '^Base branch:' "$TMPDIR14B/aiplans/p999_sandbox_task.md" || true)
    out_field=$(grep '^Output branch:' "$TMPDIR14B/aiplans/p999_sandbox_task.md" || true)
    assert_eq "precedence [$b_label] base" "Base branch: $b_base" "$base_field"
    assert_eq "precedence [$b_label] output" "Output branch: $b_out" "$out_field"
done <<'CASES'
base-file beats base-flag|-|--base-branch alpha --base-branch-file @BETA@|beta|beta
base-file beats base-flag (reversed)|-|--base-branch-file @BETA@ --base-branch alpha|beta|beta
base-flag beats profile base_branch|base_branch: dev\n|--base-branch alpha|alpha|alpha
base-file beats profile base_branch|base_branch: dev\n|--base-branch-file @ALPHA@|alpha|alpha
output-flag does not disturb base-flag|-|--output-branch staging --base-branch alpha|alpha|staging
output-flag does not disturb profile base|base_branch: dev\n|--output-branch staging|dev|staging
legacy default outranks the base rung|-|--base-branch alpha --output-branch-default release|alpha|release
profile output_branch outranks the base rung|base_branch: dev\noutput_branch: staging\n||dev|staging
CASES
rm -rf "$TMPDIR14B"

# --- Test 14c: the splice never moves a field its caller said nothing about ---
# Every row starts from a source whose frontmatter ALREADY carries both fields, so
# a spurious rewrite is visible. Tests 7b/7c cannot see this: their sources have no
# `Base branch:` line at all, so an unwanted rewrite there looks like an insert.
echo "--- Test 14c: per-field splice intent on existing frontmatter ---"
TMPDIR14C=$(new_sandbox)
mkdir -p "$TMPDIR14C/prof"
rm -f "$TMPDIR14C/fakehome/.claude/plans/one-recent.md"
printf 'develop\n' > "$TMPDIR14C/base.txt"

make_stale_front_14c() {
    cat > "$TMPDIR14C/fakehome/.claude/plans/with_front.md" <<'EOF'
---
Task: t999_sandbox_task.md
Base branch: stale
Output branch: stale
---

# body
EOF
}

# label | profile body ('-' = no --profile) | extra flags | expected base | expected output
while IFS='|' read -r c_label c_prof c_extra c_base c_out; do
    [ -n "$c_label" ] || continue
    c_prof_flag=""
    if [ "$c_prof" != "-" ]; then
        { printf 'name: p\n'; printf '%b' "$c_prof"; } > "$TMPDIR14C/prof/case.yaml"
        c_prof_flag="--profile $TMPDIR14C/prof/case.yaml"
    fi
    c_extra=${c_extra//@BASEFILE@/$TMPDIR14C/base.txt}
    make_stale_front_14c
    # shellcheck disable=SC2086  # deliberate word-splitting of the flag lists
    run_externalize "$TMPDIR14C" "$TMPDIR14C/fakehome/.claude/plans" 999 --force \
        $c_prof_flag $c_extra >/dev/null </dev/null
    plan="$TMPDIR14C/aiplans/p999_sandbox_task.md"
    base_field=$(grep '^Base branch:' "$plan" || true)
    out_field=$(grep '^Output branch:' "$plan" || true)
    assert_eq "splice intent [$c_label] base" "Base branch: $c_base" "$base_field"
    assert_eq "splice intent [$c_label] output" "Output branch: $c_out" "$out_field"
    # An insert-instead-of-replace bug would duplicate a field or break the block.
    assert_eq "splice intent [$c_label] frontmatter intact" "2" "$(grep -c '^---$' "$plan" || true)"
    assert_eq "splice intent [$c_label] one base line" "1" "$(grep -c '^Base branch:' "$plan" || true)"
    assert_eq "splice intent [$c_label] one output line" "1" "$(grep -c '^Output branch:' "$plan" || true)"
done <<'CASES'
--output-branch claims output only|-|--output-branch dev|stale|dev
legacy default claims output only|-|--output-branch-default release|stale|release
profile with only output_branch|output_branch: dev\n||stale|dev
profile with neither key|description: bare\n||stale|main
--base-branch claims both|-|--base-branch develop|develop|develop
--base-branch-file claims both|-|--base-branch-file @BASEFILE@|develop|develop
profile base_branch claims both|base_branch: dev\n||dev|dev
--no-worktree asserts there is no fork|-|--no-worktree|main|main
create_worktree false asserts the same|create_worktree: false\nbase_branch: dev\n||main|main
CASES
rm -rf "$TMPDIR14C"

# --- Test 14d: --base-branch-file is read AFTER the short-circuit ---
# The base counterpart of Test 7q. Step 8 reuses the same branch flags and the
# scratch file may already be gone, so a no-op call must still short-circuit; a
# call that would actually write the header must still fail closed. The pair is
# what stops a future refactor from hoisting the read (breaking the no-op) or from
# making the writing call silently fall back to the primary.
echo "--- Test 14d: --base-branch-file across the PLAN_EXISTS short-circuit ---"
TMPDIR14D=$(new_sandbox)
printf 'develop\n' > "$TMPDIR14D/base.txt"
make_fresh_internal "$TMPDIR14D/fakehome/.claude/plans/one-recent.md"
result=$(run_externalize "$TMPDIR14D" "$TMPDIR14D/fakehome/.claude/plans" 999 --force \
    --base-branch-file "$TMPDIR14D/base.txt" 2>&1)
assert_contains "step 6 externalizes with a base file" "EXTERNALIZED:" "$result"
base_field=$(grep '^Base branch:' "$TMPDIR14D/aiplans/p999_sandbox_task.md" || true)
assert_eq "step 6 records the interactive base" "Base branch: develop" "$base_field"

rm -f "$TMPDIR14D/base.txt"          # the documented cleanup
# `|| true` so a regression reports FAIL instead of aborting the suite under
# `set -e` -- an aborted run shows zero failures and silently proves nothing.
result=$(run_externalize "$TMPDIR14D" "$TMPDIR14D/fakehome/.claude/plans" 999 \
    --base-branch-file "$TMPDIR14D/base.txt" 2>&1 || true)
assert_contains "step 8 short-circuits despite the removed base file" "PLAN_EXISTS:" "$result"
base_field=$(grep '^Base branch:' "$TMPDIR14D/aiplans/p999_sandbox_task.md" || true)
assert_eq "step 8 leaves the recorded base intact" "Base branch: develop" "$base_field"

if run_externalize "$TMPDIR14D" "$TMPDIR14D/fakehome/.claude/plans" 999 --force \
        --base-branch-file "$TMPDIR14D/base.txt" >/dev/null 2>&1; then
    assert_eq "a writing call still fails closed on a missing base file" "died" "succeeded"
else
    assert_eq "a writing call still fails closed on a missing base file" "died" "died"
fi
rm -rf "$TMPDIR14D"

# --- Test 14e: the shared value-file reader keeps its two consumers apart ---
# read_branch_value_file() returns through a shared global and now has two call
# sites, so both file flags in one invocation is a new path: correctness rests on
# each call copying the result before the next overwrites it. A
# copy-after-both-reads mistake would make one file supply both branches.
echo "--- Test 14e: both value-file flags in one invocation ---"
TMPDIR14E=$(new_sandbox)
printf 'develop\n' > "$TMPDIR14E/base.txt"
printf 'release\n' > "$TMPDIR14E/out.txt"
printf 'staging\n' > "$TMPDIR14E/staging.txt"
printf 'beta\n'    > "$TMPDIR14E/beta.txt"

# label | extra flags | expected base | expected output
while IFS='|' read -r e_label e_extra e_base e_out; do
    [ -n "$e_label" ] || continue
    e_extra=${e_extra//@BASE@/$TMPDIR14E/base.txt}
    e_extra=${e_extra//@OUT@/$TMPDIR14E/out.txt}
    e_extra=${e_extra//@STAGING@/$TMPDIR14E/staging.txt}
    e_extra=${e_extra//@BETA@/$TMPDIR14E/beta.txt}
    make_fresh_internal "$TMPDIR14E/fakehome/.claude/plans/one-recent.md"
    # shellcheck disable=SC2086  # deliberate word-splitting of the flag list
    run_externalize "$TMPDIR14E" "$TMPDIR14E/fakehome/.claude/plans" 999 --force \
        $e_extra >/dev/null </dev/null
    base_field=$(grep '^Base branch:' "$TMPDIR14E/aiplans/p999_sandbox_task.md" || true)
    out_field=$(grep '^Output branch:' "$TMPDIR14E/aiplans/p999_sandbox_task.md" || true)
    assert_eq "value files [$e_label] base" "Base branch: $e_base" "$base_field"
    assert_eq "value files [$e_label] output" "Output branch: $e_out" "$out_field"
done <<'CASES'
both file flags|--base-branch-file @BASE@ --output-branch-default-file @OUT@|develop|release
both file flags reversed|--output-branch-default-file @OUT@ --base-branch-file @BASE@|develop|release
legacy file wins over legacy flag|--output-branch-default release --output-branch-default-file @STAGING@|main|staging
base file wins over base flag|--base-branch alpha --base-branch-file @BETA@|beta|beta
CASES
rm -rf "$TMPDIR14E"

# --- Test 15: `Worktree:` comes from --worktree INTENT, never a disk probe (t1536) ---
# Before t1536 build_header() emitted the field from `[[ -d "aiwork/<task_name>" ]]`.
# The fork is now deferred to Step 7 while externalization still runs in Step 6, so
# that probe would drop `Worktree:` from every worktree-mode plan. The field is now
# emitted iff --worktree is passed; case "probe removed" below is the control that
# distinguishes intent-driven from probe-driven and FAILS on the pre-t1536 helper.
echo "--- Test 15: --worktree intent replaces the aiwork/ directory probe ---"

# 15.1 the flag records the field
TMPDIR15=$(new_sandbox)
make_fresh_internal "$TMPDIR15/fakehome/.claude/plans/one-recent.md"
run_externalize "$TMPDIR15" "$TMPDIR15/fakehome/.claude/plans" 999 \
    --worktree aiwork/t999_sandbox_task >/dev/null
wt_field=$(grep '^Worktree:' "$TMPDIR15/aiplans/p999_sandbox_task.md" || true)
assert_eq "--worktree records the field" "Worktree: aiwork/t999_sandbox_task" "$wt_field"
rm -rf "$TMPDIR15"

# 15.2 NEGATIVE CONTROL: directory present on disk, flag absent -> NO field.
# This is the load-bearing assertion of the whole change.
TMPDIR15B=$(new_sandbox)
mkdir -p "$TMPDIR15B/aiwork/t999_sandbox_task"
make_fresh_internal "$TMPDIR15B/fakehome/.claude/plans/one-recent.md"
run_externalize "$TMPDIR15B" "$TMPDIR15B/fakehome/.claude/plans" 999 >/dev/null 2>&1
n=$(grep -c '^Worktree:' "$TMPDIR15B/aiplans/p999_sandbox_task.md" || true)
assert_eq "probe removed: aiwork/ on disk does not emit Worktree" "0" "$n"
rm -rf "$TMPDIR15B"

# 15.3 no flag, no directory -> no field (unchanged legacy behaviour)
TMPDIR15C=$(new_sandbox)
make_fresh_internal "$TMPDIR15C/fakehome/.claude/plans/one-recent.md"
run_externalize "$TMPDIR15C" "$TMPDIR15C/fakehome/.claude/plans" 999 >/dev/null 2>&1
n=$(grep -c '^Worktree:' "$TMPDIR15C/aiplans/p999_sandbox_task.md" || true)
assert_eq "no claim, no directory: no Worktree field" "0" "$n"
rm -rf "$TMPDIR15C"

# 15.4 --worktree and --no-worktree are mutually exclusive, in BOTH orders
for order in "--no-worktree --worktree aiwork/x" "--worktree aiwork/x --no-worktree"; do
    TMPDIR15D=$(new_sandbox)
    make_fresh_internal "$TMPDIR15D/fakehome/.claude/plans/one-recent.md"
    # shellcheck disable=SC2086  # deliberate word-splitting of the flag list
    if run_externalize "$TMPDIR15D" "$TMPDIR15D/fakehome/.claude/plans" 999 $order \
            >/dev/null 2>&1; then
        assert_eq "conflicting worktree intent rejected [$order]" "died" "succeeded"
    else
        assert_eq "conflicting worktree intent rejected [$order]" "died" "died"
    fi
    rm -rf "$TMPDIR15D"
done

# 15.5 unsafe paths are rejected with the same fail-closed shape as branch names
for payload in 'aiwork/$(id -u)' 'aiwork/`id`' "aiwork/x'y" 'aiwork/x;id' '../escape' \
               'aiwork/../../etc' '/abs/path' 'aiwork/a b'; do
    TMPDIR15E=$(new_sandbox)
    make_fresh_internal "$TMPDIR15E/fakehome/.claude/plans/one-recent.md"
    if run_externalize "$TMPDIR15E" "$TMPDIR15E/fakehome/.claude/plans" 999 \
            --worktree "$payload" >/dev/null 2>&1; then
        assert_eq "unsafe --worktree rejected: $payload" "rejected" "accepted"
    else
        assert_eq "unsafe --worktree rejected: $payload" "rejected" "rejected"
    fi
    # A rejected run never writes the plan, so grep has no file and prints
    # nothing -- normalize the empty capture to 0 rather than comparing "" to "0".
    leaked=$(grep -c "$(id -u)" "$TMPDIR15E/aiplans/p999_sandbox_task.md" 2>/dev/null || true)
    assert_eq "unsafe --worktree payload did not execute: $payload" "0" "${leaked:-0}"
    rm -rf "$TMPDIR15E"
done

# 15.5b boundary: `..` is rejected as a SEGMENT, not as a substring. A name that
# merely contains dots must still be accepted, or the guard would reject valid
# paths -- and Re-entry Routing's documented header check uses the same rule, so
# the two sides have to agree on where the boundary sits.
TMPDIR15E2=$(new_sandbox)
make_fresh_internal "$TMPDIR15E2/fakehome/.claude/plans/one-recent.md"
run_externalize "$TMPDIR15E2" "$TMPDIR15E2/fakehome/.claude/plans" 999 \
    --worktree aiwork/t1..2_sandbox >/dev/null 2>&1
assert_eq "dots in a name are not a '..' segment" "Worktree: aiwork/t1..2_sandbox" \
    "$(grep '^Worktree:' "$TMPDIR15E2/aiplans/p999_sandbox_task.md" || true)"
rm -rf "$TMPDIR15E2"

# 15.6 missing argument is a usage error
TMPDIR15F=$(new_sandbox)
make_fresh_internal "$TMPDIR15F/fakehome/.claude/plans/one-recent.md"
if run_externalize "$TMPDIR15F" "$TMPDIR15F/fakehome/.claude/plans" 999 --worktree \
        >/dev/null 2>&1; then
    assert_eq "--worktree without an argument is an error" "died" "succeeded"
else
    assert_eq "--worktree without an argument is an error" "died" "died"
fi
rm -rf "$TMPDIR15F"

# 15.7 --worktree contradicting a profile's create_worktree: false fails closed
TMPDIR15G=$(new_sandbox)
mkdir -p "$TMPDIR15G/prof"
printf 'name: p\ncreate_worktree: false\n' > "$TMPDIR15G/prof/cur.yaml"
make_fresh_internal "$TMPDIR15G/fakehome/.claude/plans/one-recent.md"
if run_externalize "$TMPDIR15G" "$TMPDIR15G/fakehome/.claude/plans" 999 \
        --profile "$TMPDIR15G/prof/cur.yaml" --worktree aiwork/t999_sandbox_task \
        >/dev/null 2>&1; then
    assert_eq "--worktree vs create_worktree:false rejected" "died" "succeeded"
else
    assert_eq "--worktree vs create_worktree:false rejected" "died" "died"
fi
rm -rf "$TMPDIR15G"

# 15.8 the worktree flag and the branch flags are independent
TMPDIR15H=$(new_sandbox)
make_fresh_internal "$TMPDIR15H/fakehome/.claude/plans/one-recent.md"
run_externalize "$TMPDIR15H" "$TMPDIR15H/fakehome/.claude/plans" 999 \
    --worktree aiwork/t999_sandbox_task --base-branch develop >/dev/null
wt_field=$(grep '^Worktree:' "$TMPDIR15H/aiplans/p999_sandbox_task.md" || true)
base_field=$(grep '^Base branch:' "$TMPDIR15H/aiplans/p999_sandbox_task.md" || true)
assert_eq "worktree + base: Worktree recorded" "Worktree: aiwork/t999_sandbox_task" "$wt_field"
assert_eq "worktree + base: Base branch recorded" "Base branch: develop" "$base_field"
rm -rf "$TMPDIR15H"

# 15.9 an omitted worktree claim warns on STDERR only -- stdout stays the
# single-line status channel every caller parses.
TMPDIR15I=$(new_sandbox)
make_fresh_internal "$TMPDIR15I/fakehome/.claude/plans/one-recent.md"
err15=$(run_externalize "$TMPDIR15I" "$TMPDIR15I/fakehome/.claude/plans" 999 2>&1 >/dev/null)
out15=$(run_externalize "$TMPDIR15I" "$TMPDIR15I/fakehome/.claude/plans" 999 --force 2>/dev/null)
assert_contains "omitted worktree claim warns on stderr" "no worktree claim" "$err15"
assert_contains "omitted claim: stdout still the status line" "OVERWRITTEN:aiplans/p999_sandbox_task.md:" "$out15"
n=$(printf '%s\n' "$out15" | grep -c 'no worktree claim' || true)
assert_eq "omitted claim: warning never reaches stdout" "0" "$n"
rm -rf "$TMPDIR15I"

# 15.10 an explicit claim -- either flag -- emits no warning
for claim in "--worktree aiwork/t999_sandbox_task" "--no-worktree"; do
    TMPDIR15J=$(new_sandbox)
    make_fresh_internal "$TMPDIR15J/fakehome/.claude/plans/one-recent.md"
    # shellcheck disable=SC2086  # deliberate word-splitting of the flag list
    err15=$(run_externalize "$TMPDIR15J" "$TMPDIR15J/fakehome/.claude/plans" 999 $claim 2>&1 >/dev/null)
    n=$(printf '%s\n' "$err15" | grep -c 'no worktree claim' || true)
    assert_eq "explicit claim emits no warning [$claim]" "0" "$n"
    rm -rf "$TMPDIR15J"
done

# --- Test 15b: --worktree reaches a source that ALREADY has frontmatter (t1536).
# build_header() is skipped for such sources, so without a splice the flag would
# be accepted and the field silently dropped -- the exact failure the
# intent-driven contract exists to prevent, and the one build_header alone cannot
# cover. --no-worktree is the tri-state's other arm: it must DELETE a stale line.
echo "--- Test 15b: --worktree spliced into existing frontmatter ---"
write_front_plan_15b() {   # $1=dir  $2..=extra frontmatter lines
    local d="$1"; shift
    { echo "---"; echo "Task: t999_sandbox_task.md"; for l in "$@"; do echo "$l"; done; echo "---";
      echo; echo "# Already has frontmatter"; } > "$d/fakehome/.claude/plans/with_front.md"
}

# insert: no Worktree line present
TMPDIR15K=$(new_sandbox)
write_front_plan_15b "$TMPDIR15K"
run_externalize "$TMPDIR15K" "$TMPDIR15K/fakehome/.claude/plans" 999 \
    --worktree aiwork/t999_sandbox_task >/dev/null 2>&1
plan15k="$TMPDIR15K/aiplans/p999_sandbox_task.md"
assert_eq "worktree splice insert: recorded" "Worktree: aiwork/t999_sandbox_task" \
    "$(grep '^Worktree:' "$plan15k" || true)"
assert_eq "worktree splice insert: exactly once" "1" "$(grep -c '^Worktree:' "$plan15k" || true)"
assert_eq "worktree splice insert: --- count still 2" "2" "$(grep -c '^---$' "$plan15k" || true)"
rm -rf "$TMPDIR15K"

# replace: a stale Worktree line is overwritten, not duplicated
TMPDIR15L=$(new_sandbox)
write_front_plan_15b "$TMPDIR15L" "Worktree: aiwork/stale"
run_externalize "$TMPDIR15L" "$TMPDIR15L/fakehome/.claude/plans" 999 \
    --worktree aiwork/t999_sandbox_task >/dev/null 2>&1
plan15l="$TMPDIR15L/aiplans/p999_sandbox_task.md"
assert_eq "worktree splice replace: value replaced" "Worktree: aiwork/t999_sandbox_task" \
    "$(grep '^Worktree:' "$plan15l" || true)"
assert_eq "worktree splice replace: exactly one line" "1" "$(grep -c '^Worktree:' "$plan15l" || true)"
rm -rf "$TMPDIR15L"

# --no-worktree CLEARS a stale line, so a later session cannot consume it
TMPDIR15M=$(new_sandbox)
write_front_plan_15b "$TMPDIR15M" "Worktree: aiwork/stale"
run_externalize "$TMPDIR15M" "$TMPDIR15M/fakehome/.claude/plans" 999 --no-worktree >/dev/null 2>&1
assert_eq "no-worktree splice: stale Worktree removed" "0" \
    "$(grep -c '^Worktree:' "$TMPDIR15M/aiplans/p999_sandbox_task.md" || true)"
rm -rf "$TMPDIR15M"

# no claim at all leaves an existing line untouched (per-field opt-in)
TMPDIR15N=$(new_sandbox)
write_front_plan_15b "$TMPDIR15N" "Worktree: aiwork/keepme"
run_externalize "$TMPDIR15N" "$TMPDIR15N/fakehome/.claude/plans" 999 --output-branch dev >/dev/null 2>&1
assert_eq "no worktree claim: existing line untouched" "Worktree: aiwork/keepme" \
    "$(grep '^Worktree:' "$TMPDIR15N/aiplans/p999_sandbox_task.md" || true)"
rm -rf "$TMPDIR15N"

# all three fields in one splice keep build_header order and one frontmatter block
TMPDIR15O=$(new_sandbox)
write_front_plan_15b "$TMPDIR15O"
run_externalize "$TMPDIR15O" "$TMPDIR15O/fakehome/.claude/plans" 999 \
    --worktree aiwork/t999_sandbox_task --base-branch develop --output-branch dev >/dev/null 2>&1
plan15o="$TMPDIR15O/aiplans/p999_sandbox_task.md"
order=$(grep -nE '^(Worktree|Base branch|Output branch):' "$plan15o" | cut -d: -f2 | tr '\n' ',')
assert_eq "three-field splice: build_header order" "Worktree,Base branch,Output branch," "$order"
assert_eq "three-field splice: --- count still 2" "2" "$(grep -c '^---$' "$plan15o" || true)"
rm -rf "$TMPDIR15O"

# --- Test 16: `Base branch:` INSERTED into existing frontmatter (t1536).
# Test 7b covers this splice for --output-branch; the base insert path had no
# coverage. It is what upgrades a legacy plan (frontmatter, but no `Base branch:`
# field) the first time a base is actually claimed -- i.e. on a Step 6 call that
# really externalizes. It does NOT fire on the Step 8 fallback, which
# short-circuits with PLAN_EXISTS (Test 14d); that is why the Step-7 fork block's
# legacy-base confirmation is documented as per-session rather than persisted.
echo "--- Test 16: --base-branch-file splices Base branch into existing frontmatter ---"
TMPDIR16=$(new_sandbox)
cat > "$TMPDIR16/fakehome/.claude/plans/legacy.md" <<'EOF'
---
Task: t999_sandbox_task.md
Output branch: main
---

# A legacy plan: no Base branch field
EOF
printf 'develop\n' > "$TMPDIR16/base.txt"
run_externalize "$TMPDIR16" "$TMPDIR16/fakehome/.claude/plans" 999 \
    --base-branch-file "$TMPDIR16/base.txt" >/dev/null 2>&1
plan16="$TMPDIR16/aiplans/p999_sandbox_task.md"
n=$(grep -c '^Base branch: develop$' "$plan16" || true)
assert_eq "legacy splice: Base branch inserted exactly once" "1" "$n"
count=$(grep -c '^---$' "$plan16" || true)
assert_eq "legacy splice: --- count still 2" "2" "$count"
task_line=$(grep '^Task:' "$plan16" || true)
assert_eq "legacy splice: pre-existing fields untouched" "Task: t999_sandbox_task.md" "$task_line"
# --base-branch[-file] deliberately claims the merge target too (rung 4 of the
# output chain: "output defaults to the resolved base"), so the confirmed base
# becomes both fields. That is the documented t1277 contract, not a side effect
# -- pin it so a future change cannot silently decouple them.
out_line=$(grep '^Output branch:' "$plan16" || true)
assert_eq "legacy splice: base also becomes the merge target" "Output branch: develop" "$out_line"

# ...and the merge target can still be pinned independently when the caller says
# so, which is what keeps the base confirmation from relocating a legacy plan's
# merge target against the user's intent.
TMPDIR16B=$(new_sandbox)
cat > "$TMPDIR16B/fakehome/.claude/plans/legacy.md" <<'EOF'
---
Task: t999_sandbox_task.md
Output branch: main
---

# A legacy plan: no Base branch field
EOF
printf 'develop\n' > "$TMPDIR16B/base.txt"
run_externalize "$TMPDIR16B" "$TMPDIR16B/fakehome/.claude/plans" 999 \
    --base-branch-file "$TMPDIR16B/base.txt" --output-branch main >/dev/null 2>&1
plan16b="$TMPDIR16B/aiplans/p999_sandbox_task.md"
assert_eq "explicit output pins the merge target" "Output branch: main" \
    "$(grep '^Output branch:' "$plan16b" || true)"
assert_eq "explicit output leaves the spliced base alone" "Base branch: develop" \
    "$(grep '^Base branch:' "$plan16b" || true)"
rm -rf "$TMPDIR16B"

# Round-trip: Re-entry Routing's documented resolution snippet must now bind the
# spliced value WITH `plan header` provenance -- asserting the value alone cannot
# tell a real header read apart from the legacy `main` fallback.
base_branch=$(sed -n 's/^Base branch: //p' "$plan16" | head -n1)
provenance_base="plan header"
[ -n "$base_branch" ] || { base_branch=main; provenance_base="legacy plan, no Base branch field"; }
assert_eq "round-trip: resolved base is the spliced value" "develop" "$base_branch"
assert_eq "round-trip: provenance is the header, not the fallback" "plan header" "$provenance_base"

# Control: the SAME snippet against a plan with no `Base branch:` line must take
# the fallback -- otherwise the assertion above proves nothing about provenance.
cat > "$TMPDIR16/legacy_plain.md" <<'EOF'
---
Task: t999_sandbox_task.md
---
EOF
base_branch=$(sed -n 's/^Base branch: //p' "$TMPDIR16/legacy_plain.md" | head -n1)
provenance_base="plan header"
[ -n "$base_branch" ] || { base_branch=main; provenance_base="legacy plan, no Base branch field"; }
assert_eq "control: fallback binds main" "main" "$base_branch"
assert_eq "control: fallback provenance is recorded" "legacy plan, no Base branch field" "$provenance_base"
rm -rf "$TMPDIR16"

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
