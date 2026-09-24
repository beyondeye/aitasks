#!/usr/bin/env bash
# test_shadow_scope.sh - Tests for the shadow's ownership-EVIDENCE helper (t1873).
#
# The failure this guards: the shadow's implementation review treated every
# dirty file in a shared checkout as the followed task's change, so other
# sessions' work came back as actionable concerns round after round.
# aitask_shadow_scope.sh now reports, per changed file PART, the evidence
# bearing on ownership; the shadow judges. These tests pin that each scenario
# the shadow must exercise discretion over gets the evidence it needs:
#
#   - an UNLISTED related file (new tree the plan names; no evidence at all)
#   - a LISTED FOREIGN file (context citation + baseline + another task's claim)
#   - a SHARED file: the task's committed part and a newer dirty part, separate
#   - a MISSING plan (task-description references only)
#   - non-Go / extensionless paths and the section a mention sits under
#   - module-relative claims (a sub-project plan's trailing sub-paths)
#   - a dedicated task worktree vs a worktree on some other branch
#
# and that the helper never emits a verdict (no IN / OUT / blocking tokens).
#
# Run: bash tests/test_shadow_scope.sh
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0; FAIL=0; TOTAL=0
SCOPE="$PROJECT_DIR/.aitask-scripts/aitask_shadow_scope.sh"
CS="$PROJECT_DIR/.aitask-scripts/aitask_change_surface.sh"

# One parent fixture root registered in THIS shell (see test_change_surface.sh
# for why per-fixture registration inside $(...) leaks).
FIXTURE_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/test_shadow_scope_XXXXXX")"
cleanup() { [[ -n "${FIXTURE_ROOT:-}" ]] && rm -rf "$FIXTURE_ROOT"; }
trap cleanup EXIT

# The helper must not see the invoking pane's binding or task-data overrides.
unset TMUX TMUX_PANE TASK_DIR PLAN_DIR ARCHIVED_DIR ARCHIVED_PLAN_DIR AIT_CHANGE_SURFACE_DIR

new_repo() {
    local tmp
    tmp="$(mktemp -d "$FIXTURE_ROOT/repo_XXXXXX")"
    (
        cd "$tmp" || exit 1
        git init -q -b main .
        git config user.email test@example.com
        git config user.name Test
        mkdir -p aitasks aiplans lib shared
        printf '.aitask-gates/\n' > .gitignore
        echo seed > seed.txt
        echo x > lib/x.sh
        echo o > lib/other.sh
        echo a > a.sh
        echo s > shared/s.sh
        printf 'all:\n' > Makefile
        git add -A
        git commit -qm "init"
    ) >/dev/null 2>&1
    echo "$tmp"
}

# task <dir> <id> <status> <body>   — writes aitasks/t<id>_x.md
task() {
    printf -- '---\nstatus: %s\n---\n%s\n' "$3" "$4" > "$1/aitasks/t$2_x.md"
}
# plan <dir> <id> <body>            — writes aiplans/p<id>_x.md
plan() {
    printf -- '---\nTask: t%s_x.md\n---\n%s\n' "$2" "$3" > "$1/aiplans/p$2_x.md"
}
commit_as() {   # commit_as <dir> <tag> <path...>
    local d="$1" tag="$2"; shift 2
    ( cd "$d" && git add -- "$@" && git commit -qm "feature: work ($tag)" -- "$@" ) >/dev/null 2>&1
}
scope() { local d="$1"; shift; ( cd "$d" && "$SCOPE" "$@" 2>/dev/null ); }
# part_line <output> <path> <part> — the one PART line for that path and part.
part_line() {
    printf '%s\n' "$1" | awk -F'|' -v p="$2" -v k="$3" \
        '$1=="PART" && $2==k { path=$0; sub(/^([^|]*\|){4}/, "", path); if (path==p) print }'
}

# ===========================================================================
# Fixture A — a shared checkout. F = t7 (followed), X = t9 (another active task).
# ===========================================================================
A="$(new_repo)"
task "$A" 7 Implementing $'Followed task.\nAlso update docs/guide.md.'
plan "$A" 7 "$(cat <<'EOF'
# Plan
New tree goengines/ is created here.
## Critical files
- goengines/x.go
- src/lib.rs
- Makefile
## Context
lib/x.sh is cited only for its locking pattern.
## Verification
run web/check.ts
EOF
)"
task "$A" 9 Implementing 'Other task body.'
plan "$A" 9 $'## Files\n- lib/x.sh\n- lib/other.sh\n- other/new.py\n- bench/tool.go (module-relative)'
mkdir -p "$A/aitasks/t7"
printf -- '---\nstatus: Ready\n---\nchild\n' > "$A/aitasks/t7/t7_1_c.md"

# Foreign dirt that predates F's claim, then the claim-time baseline.
echo foreign-before-claim >> "$A/lib/x.sh"
( cd "$A" && "$CS" capture 7 >/dev/null 2>&1 )

# F's own commit, then a NEWER foreign edit of the same file.
echo f-work >> "$A/a.sh"; commit_as "$A" t7 a.sh
F_HASH="$(cd "$A" && git rev-parse --short=12 HEAD)"
echo later-edit >> "$A/a.sh"
# X's commit on a file that is dirty again now.
echo x-work >> "$A/shared/s.sh"; commit_as "$A" t9 shared/s.sh
echo x-more >> "$A/shared/s.sh"
# Commits of t70 and of F's child t7_1: never F's own.
echo z > "$A/z70.sh"; commit_as "$A" t70 z70.sh
echo c > "$A/c71.sh"; commit_as "$A" t7_1 c71.sh

mkdir -p "$A/goengines" "$A/src" "$A/web" "$A/tools" "$A/docs" "$A/other"
echo 'package x' > "$A/goengines/x.go"
echo 'module g'  > "$A/goengines/go.mod"
echo 'package x' > "$A/goengines/a b.go"
mkdir -p "$A/goengines/bench"
echo 'package bench' > "$A/goengines/bench/tool.go"
echo 'fn main(){}' > "$A/src/lib.rs"
printf 'all:\n\ttrue\n' > "$A/Makefile"
echo 'check' > "$A/web/check.ts"
echo 'helper' > "$A/tools/helper.py"
echo 'o2' >> "$A/lib/other.sh"
echo 'new' > "$A/other/new.py"
echo 'guide' > "$A/docs/guide.md"
( cd "$A" && git add -- docs/guide.md )
echo 'guide 2' >> "$A/docs/guide.md"
printf 'n' > "$A/bad"$'\n'"name.txt"

outA="$(scope "$A" 7 --checkout "$A")"

echo "=== signals ==="
assert_contains "task line" "TASK:7" "$outA"
assert_contains "explicit checkout reported" "|explicit" "$outA"
assert_contains "not a dedicated worktree" "SIGNAL:dedicated_worktree|no" "$outA"
assert_contains "plan found" "SIGNAL:plan|ok|aiplans/p7_x.md" "$outA"
assert_contains "one F commit" "SIGNAL:commits|1|$F_HASH" "$outA"
assert_contains "baseline available" "SIGNAL:baseline|ok" "$outA"
assert_contains "other active task listed" "SIGNAL:other_tasks|1|9" "$outA"

echo "=== unlisted related file: evidence only, no verdict ==="
assert_eq "go.mod carries the plan's dir reference" \
    "PART|dirty|untracked|f_plan_dir:goengines|goengines/go.mod" \
    "$(part_line "$outA" goengines/go.mod dirty)"
assert_eq "spaced path survives NUL-safe enumeration" \
    "PART|dirty|untracked|f_plan_dir:goengines|goengines/a b.go" \
    "$(part_line "$outA" "goengines/a b.go" dirty)"
assert_eq "an unrelated unlisted file has no evidence" \
    "PART|dirty|untracked|-|tools/helper.py" \
    "$(part_line "$outA" tools/helper.py dirty)"

echo "=== listed files, with the section they are listed under ==="
assert_eq "file-list mention (Go)" \
    "PART|dirty|untracked|f_plan:critical_files|goengines/x.go" \
    "$(part_line "$outA" goengines/x.go dirty)"
assert_eq "file-list mention (Rust)" \
    "PART|dirty|untracked|f_plan:critical_files|src/lib.rs" \
    "$(part_line "$outA" src/lib.rs dirty)"
assert_eq "file-list mention (extensionless, tracked edit)" \
    "PART|dirty|unstaged|f_plan:critical_files|Makefile" \
    "$(part_line "$outA" Makefile dirty)"
assert_eq "verification-section mention (TypeScript)" \
    "PART|dirty|untracked|f_plan:verification|web/check.ts" \
    "$(part_line "$outA" web/check.ts dirty)"
assert_eq "task-description mention, staged + newer unstaged" \
    "PART|dirty|staged,unstaged|f_task:top|docs/guide.md" \
    "$(part_line "$outA" docs/guide.md dirty)"

echo "=== listed FOREIGN file: every source of counter-evidence is kept ==="
assert_eq "context citation + baseline + other task's plan" \
    "PART|dirty|unstaged|f_plan:context,baseline_dirty,other_plan:t9|lib/x.sh" \
    "$(part_line "$outA" lib/x.sh dirty)"
assert_eq "another task's planned file" \
    "PART|dirty|unstaged|other_plan:t9|lib/other.sh" \
    "$(part_line "$outA" lib/other.sh dirty)"
assert_eq "another task's committed file, dirty again" \
    "PART|dirty|unstaged|other_commit:t9|shared/s.sh" \
    "$(part_line "$outA" shared/s.sh dirty)"

assert_eq "module-relative claim by another task is weaker suffix evidence" \
    "PART|dirty|untracked|f_plan_dir:goengines,other_plan_suffix:t9|goengines/bench/tool.go" \
    "$(part_line "$outA" goengines/bench/tool.go dirty)"

echo "=== shared file: committed part and newer dirty part stay separate ==="
assert_eq "F's committed part" \
    "PART|committed|$F_HASH|f_commits:1|a.sh" \
    "$(part_line "$outA" a.sh committed)"
assert_eq "the newer dirty part is its own record" \
    "PART|dirty|unstaged|f_commit_earlier:1|a.sh" \
    "$(part_line "$outA" a.sh dirty)"

echo "=== commit matching is exact ==="
assert_not_contains "(t70) is not (t7)" "z70.sh" "$outA"
assert_not_contains "a child's (t7_1) commit is not the parent's" "c71.sh" "$outA"

echo "=== data paths, bookkeeping, unrepresentable paths ==="
partsA="$(printf '%s\n' "$outA" | grep '^PART|' || true)"
assert_not_contains "task data never reported" "|aitasks/" "$partsA"
assert_not_contains "plan data never reported" "|aiplans/" "$partsA"
assert_not_contains "claim-baseline bookkeeping never reported" ".aitask-gates" "$outA"
assert_contains "newline path counted, not emitted" "WARN:unrepresentable_paths|1" "$outA"

echo "=== the helper reports evidence, never a verdict ==="
assert_not_contains "no IN class" "|IN|" "$outA"
assert_not_contains "no OUT class" "OUT|" "$outA"
assert_not_contains "no TENTATIVE class" "TENTATIVE" "$outA"
assert_not_contains "no blocking eligibility" "blocking" "$outA"

echo "=== argument handling ==="
( cd "$A" && "$SCOPE" 'bad id' --checkout "$A" >/dev/null 2>&1 ); rc=$?
assert_eq "malformed id exits 2" "2" "$rc"
( cd "$A" && "$SCOPE" 7 --checkout "$A/nope" >/dev/null 2>&1 ); rc=$?
assert_eq "missing checkout dir exits 2" "2" "$rc"
outT="$(scope "$A" t7 --checkout "$A")"
assert_contains "a t-prefixed id resolves the same task" "SIGNAL:commits|1|$F_HASH" "$outT"

# ===========================================================================
# Fixture B — missing plan: only task-description evidence exists.
# ===========================================================================
B="$(new_repo)"
task "$B" 5 Implementing $'## Scope\nEdit web/app.ts for the new flow.'
mkdir -p "$B/web"
echo one > "$B/web/app.ts"; commit_as "$B" t5 web/app.ts
B_HASH="$(cd "$B" && git rev-parse --short=12 HEAD)"
echo two >> "$B/web/app.ts"
echo stray > "$B/stray.txt"
outB="$(scope "$B" 5 --checkout "$B")"

echo "=== missing plan ==="
assert_contains "plan reported missing" "SIGNAL:plan|missing" "$outB"
assert_contains "task found" "SIGNAL:task|ok" "$outB"
assert_contains "baseline missing is its own state" "SIGNAL:baseline|missing" "$outB"
assert_eq "committed part still reported" \
    "PART|committed|$B_HASH|f_commits:1,f_task:scope|web/app.ts" \
    "$(part_line "$outB" web/app.ts committed)"
assert_eq "dirty part carries the task mention and the earlier commit" \
    "PART|dirty|unstaged|f_commit_earlier:1,f_task:scope|web/app.ts" \
    "$(part_line "$outB" web/app.ts dirty)"
assert_eq "stray file: no evidence" "PART|dirty|untracked|-|stray.txt" \
    "$(part_line "$outB" stray.txt dirty)"

# ===========================================================================
# Fixture C — a dedicated task worktree vs a worktree on another branch.
# ===========================================================================
C="$(new_repo)"
task "$C" 7 Implementing 'Followed task.'
plan "$C" 7 '## Critical files\n- planned.txt'
( cd "$C" && git worktree add -q -b aitask/t7_x "$FIXTURE_ROOT/wt_ded" \
    && git worktree add -q -b feature "$FIXTURE_ROOT/wt_other" ) >/dev/null 2>&1
echo main-only > "$C/main_only.txt"
echo unplanned > "$FIXTURE_ROOT/wt_ded/unplanned.txt"
echo branch-work >> "$FIXTURE_ROOT/wt_ded/seed.txt"
( cd "$FIXTURE_ROOT/wt_ded" && git add seed.txt && git commit -qm "feature: w (t7)" ) >/dev/null 2>&1
echo other > "$FIXTURE_ROOT/wt_other/o.txt"

outC="$(scope "$C" 7 --checkout "$FIXTURE_ROOT/wt_ded")"
echo "=== dedicated worktree ==="
assert_contains "dedicated by branch" "SIGNAL:dedicated_worktree|yes|branch" "$outC"
assert_contains "unplanned file in the worktree reported" "|unplanned.txt" "$outC"
assert_contains "F's commit on the task branch found" "PART|committed|" "$outC"
assert_not_contains "the main checkout's dirt is absent" "main_only.txt" "$outC"

outR="$(scope "$C" 7)"
assert_contains "worktree record resolves the checkout without --checkout" \
    "|worktree_record" "$outR"
assert_contains "record-resolved checkout is dedicated" \
    "SIGNAL:dedicated_worktree|yes|worktree_record" "$outR"

outO="$(scope "$C" 7 --checkout "$FIXTURE_ROOT/wt_other")"
assert_contains "a worktree on another branch is not dedicated" \
    "SIGNAL:dedicated_worktree|no" "$outO"

echo "=== no binding, no record: the shadow's own checkout, stated as such ==="
D="$(new_repo)"
task "$D" 3 Implementing 'x'
outD="$(scope "$D" 3)"
assert_contains "falls back to shadow_cwd" "|shadow_cwd" "$outD"

echo
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
