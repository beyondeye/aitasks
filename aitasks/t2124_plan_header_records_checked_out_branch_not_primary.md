---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [task-workflow, worktree, git]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-22 11:18
updated_at: 2026-10-23 11:22
---

## Origin

Handoff from thinking_backend#t65 (a downstream project vendoring this framework
at v0.39.0). Not a task in this repository. The fix below is already applied to
that project's vendored copy (commit a2e872d) and pinned there by a regression
suite, so the next `ait upgrade` would revert it unless this lands upstream.

## Defects (both in `.aitask-scripts/aitask_plan_externalize.sh`)

1. **Current-branch mode records the primary, not the branch the work is on.**
   With `--no-worktree` (or `create_worktree: false`) the resolution block clears
   every derived value and writes `detect_primary_branch` (e.g. `main`) into BOTH
   `Base branch:` and `Output branch:`. In a project whose work branch is `dev`,
   a resumed session (Re-entry Routing) then drift-checks `origin/main`, and if
   the user picks "Create the worktree now" it cuts from `main` with provenance
   "plan header" (no legacy confirmation) and Step 9 merges into `main`.
   Recurred on 6+ downstream tasks, every one hand-corrected.
2. **`Branch:` is the repo root's branch in worktree mode.** Since t1536 deferred
   the fork to Step 7, `build_header()` runs while HEAD is still the root's
   branch, so a `--worktree` plan gets `Branch: dev` instead of the documented
   `aitask/<task_name>`. Invisible here because this repo's root is on `main` =
   primary, where the line is omitted.
3. (found in review of the fix) `git symbolic-ref --short HEAD` answers
   `heads/dev` when a tag `dev` exists beside branch `dev`; the fix reads the
   full ref and strips `refs/heads/`. Sibling defect in `detect_primary_branch`
   is tracked separately as t2123.

## Behaviour change to note

On a repo checked out on its primary, current-branch and no-claim runs stay
byte-identical, but a `--worktree` run now gains one line,
`Branch: aitask/<task_name>` (intended — defect 2). The existing
`tests/test_plan_externalize.sh` passes unchanged (264/264): its sandboxes are
not git repos, Test 13 sits on the primary with no worktree claim, and the
splice-order assertion greps only Worktree/Base/Output.

## Patch (downstream commit a2e872d; helper + canonical task-workflow docs)

The downstream also carries the same two doc edits in
`.claude/skills/task-workflow-remote-/`; apply them to every agent tree that
ships `planning.md` / `plan-externalization.md`, and refresh the goldens under
`tests/golden/procs/task-workflow/` if they embed those passages.

```diff
diff --git a/.aitask-scripts/aitask_plan_externalize.sh b/.aitask-scripts/aitask_plan_externalize.sh
index cdc4a71..e10118a 100755
--- a/.aitask-scripts/aitask_plan_externalize.sh
+++ b/.aitask-scripts/aitask_plan_externalize.sh
@@ -56,8 +56,9 @@
 #                        --no-worktree, and with a profile whose create_worktree
 #                        is false.
 #   --no-worktree        Step 5 created no worktree, so neither `base_branch` nor
-#                        `output_branch` applies; both fall back to the detected
-#                        primary branch.
+#                        `output_branch` applies; both record the checked-out
+#                        branch -- the one the work lands on -- and fall back to
+#                        the detected primary only on a detached HEAD (t65).
 #
 # `Worktree:` is emitted IFF --worktree is passed. There is deliberately no
 # fallback: this field used to come from a `[[ -d aiwork/<task_name> ]]` probe,
@@ -66,6 +67,12 @@
 # plan. A caller that makes NO worktree claim at all (neither flag) gets a
 # one-line stderr warning, so the omission is loud rather than silent.
 #
+# `Branch:` names the branch the work is committed on. With --worktree that is
+# the task branch Step 7 cuts, `aitask/<task_name>` -- NOT the branch checked out
+# while this runs, which is still the repo root's because the fork is deferred
+# (t1536). Otherwise it is the checked-out branch, omitted when that is the
+# primary (t65).
+#
 # Resolution precedence (t1233 for output, t1277 for base):
 #
 #   Base branch:    --base-branch[-file] > profile base_branch > detected primary
@@ -75,7 +82,8 @@
 #                 > detected primary
 #
 # Outside worktree mode (--no-worktree / `create_worktree: false`) every derived
-# value on BOTH chains is discarded and the detected primary is recorded.
+# value on BOTH chains is discarded and the checked-out branch is recorded in
+# both fields; the detected primary only when HEAD is detached (t65).
 #
 # Both header fields are consumed by task-workflow -- `Output branch:` by Step 9's
 # merge, `Base branch:` by Re-entry Routing (which resolves the branch context
@@ -172,16 +180,20 @@ Arguments:
                        is deferred to Step 7 (t1536), so this is Step-5 intent,
                        not a disk probe. Mutually exclusive with --no-worktree.
   --no-worktree        No worktree was created, so base_branch and output_branch
-                       are both ignored.
+                       are both ignored; both fields record the checked-out
+                       branch (the detected primary only on a detached HEAD).
 
 `Worktree:` is emitted only when --worktree is given; supplying neither flag
-warns on stderr and omits the field.
+warns on stderr and omits the field. `Branch:` is aitask/<task_name> with
+--worktree, else the checked-out branch (omitted when it is the primary).
 
 Precedence:
   Base branch:   --base-branch[-file] > profile base_branch > detected primary
   Output branch: --output-branch > profile output_branch
                > --output-branch-default[-file]
                > resolved base > detected primary
+  --no-worktree: both fields = the checked-out branch (detected primary on a
+                 detached HEAD)
 
 Output (exit 0):
   PLAN_EXISTS:<path>                  Already externalized (no-op)
@@ -557,21 +569,50 @@ if [[ "$WORKTREE_FLAG_SEEN" == false && "$NO_WORKTREE_FLAG_SEEN" == false ]]; th
     warn "no worktree claim (--worktree/--no-worktree) -- 'Worktree:' omitted from the plan header"
 fi
 
+PRIMARY_BRANCH="$(detect_primary_branch)"
+# The checked-out branch; empty on a detached HEAD or outside a repository. Read
+# the full ref and strip `refs/heads/` rather than using `--short`, which
+# abbreviates by ambiguity: with a tag `dev` beside branch `dev` it answers
+# `heads/dev`, a name nothing downstream can resolve as a branch (t65).
+CURRENT_BRANCH="$(git symbolic-ref --quiet HEAD 2>/dev/null || true)"
+case "$CURRENT_BRANCH" in
+    refs/heads/*) CURRENT_BRANCH="${CURRENT_BRANCH#refs/heads/}" ;;
+    *)            CURRENT_BRANCH="" ;;
+esac
+
 # Outside worktree mode nothing is cut and nothing is merged, so no derived value
-# on either chain applies.
-[[ "$WORKTREE_MODE" == true ]] \
-    || { OUTPUT_BRANCH_OVERRIDE=""; OUTPUT_BRANCH_DEFAULT=""; BASE_BRANCH_OVERRIDE=""; }
+# on either chain applies: the work lands on the checked-out branch, and that is
+# what both fields record. The detected primary is only the fallback when there is
+# no branch to name (detached HEAD) -- recording it otherwise points a resumed
+# session at a branch the work never touched (t65).
+if [[ "$WORKTREE_MODE" != true ]]; then
+    [[ -z "$CURRENT_BRANCH" ]] \
+        || validate_branch_name "$CURRENT_BRANCH" "current branch (HEAD)"
+    OUTPUT_BRANCH_DEFAULT=""
+    BASE_BRANCH_OVERRIDE="${CURRENT_BRANCH:-$PRIMARY_BRANCH}"
+    OUTPUT_BRANCH_OVERRIDE="$BASE_BRANCH_OVERRIDE"
+fi
 [[ -n "$OUTPUT_BRANCH_OVERRIDE" ]] || OUTPUT_BRANCH_OVERRIDE="$OUTPUT_BRANCH_DEFAULT"
 [[ -n "$OUTPUT_BRANCH_OVERRIDE" ]] || OUTPUT_BRANCH_OVERRIDE="$BASE_BRANCH_OVERRIDE"
-
-PRIMARY_BRANCH="$(detect_primary_branch)"
 BASE_BRANCH_RESOLVED="${BASE_BRANCH_OVERRIDE:-$PRIMARY_BRANCH}"
 
+# `Branch:` names the branch the work is committed on. In worktree mode that is the
+# task branch Step 7 cuts (`aitask/<task_name>`), not the branch checked out now:
+# the fork is deferred (t1536), so at Step 6 HEAD is still the repo root's branch.
+# Otherwise it is the checked-out branch, omitted when that is the primary (t65).
+BRANCH_FIELD=""
+if [[ "$WORKTREE_FLAG_SEEN" == true ]]; then
+    BRANCH_FIELD="aitask/${TASK_BASENAME%.md}"
+elif [[ -n "$CURRENT_BRANCH" && "$CURRENT_BRANCH" != "$PRIMARY_BRANCH" ]]; then
+    BRANCH_FIELD="$CURRENT_BRANCH"
+fi
+
 # BASE_INTENT gates the `Base branch:` splice into a plan that ALREADY carries
 # frontmatter. It is DERIVED, not flag-enumerated: true iff a base was actually
 # supplied (--base-branch[-file] or a profile that really sets base_branch), or the
 # caller positively asserted there is no fork (--no-worktree / create_worktree:
-# false, where the primary is the right answer and a stale value must go).
+# false, where the checked-out branch is the right answer and a stale value must
+# go).
 #
 # The asymmetry with OUTPUT_INTENT is deliberate. A profile with no output_branch
 # still DETERMINES the merge target (it falls back to base/primary), so --profile
@@ -665,9 +706,6 @@ if [[ "$first_line" == "---" ]]; then
 fi
 
 build_header() {
-    local current_branch=""
-    current_branch=$(git symbolic-ref --short HEAD 2>/dev/null || echo "")
-
     echo "---"
     echo "Task: $TASK_BASENAME"
 
@@ -723,8 +761,8 @@ build_header() {
     # a missing claim is warned about at parse time instead.
     [[ -n "$WORKTREE_PATH" ]] && echo "Worktree: $WORKTREE_PATH"
 
-    if [[ -n "$current_branch" && "$current_branch" != "$PRIMARY_BRANCH" ]]; then
-        echo "Branch: $current_branch"
+    if [[ -n "$BRANCH_FIELD" ]]; then
+        echo "Branch: $BRANCH_FIELD"
     fi
 
     echo "Base branch: $BASE_BRANCH_RESOLVED"
@@ -734,7 +772,7 @@ build_header() {
     echo ""
 }
 
-# Record `Worktree:` / `Base branch:` / `Output branch:` inside a plan file that
+# Record `Worktree:` / `Branch:` / `Base branch:` / `Output branch:` inside a plan file that
 # ALREADY carries frontmatter. build_header() is skipped for such sources, so
 # without this the flags would be accepted and silently dropped -- Step 9 would
 # merge somewhere else, Re-entry Routing would resolve the wrong fork point, and
@@ -751,11 +789,16 @@ build_header() {
 #   "set"  + <wt>  -> --worktree; record that path
 #   "none"         -> --no-worktree; remove any existing `Worktree:` line
 #
+# `Branch:` rides the worktree claim, because the claim is what decides it (see
+# BRANCH_FIELD): with any claim an existing line becomes `br`, or is dropped when
+# `br` is empty -- exactly what build_header() would emit; with no claim it is
+# left alone (t65).
+#
 # Replaces an existing field, else inserts before the closing `---` in
-# build_header order (Worktree, Base, Output), keeping the `---` count at 2. No-op
-# when the file does not open with `---` or when no field was claimed.
+# build_header order (Worktree, Branch, Base, Output), keeping the `---` count at
+# 2. No-op when the file does not open with `---` or when no field was claimed.
 splice_header_branches() {
-    local file="$1" base="$2" out="$3" wt_claim="${4:-}" wt="${5:-}"
+    local file="$1" base="$2" out="$3" wt_claim="${4:-}" wt="${5:-}" br="${6:-}"
     [[ -n "$base" || -n "$out" || -n "$wt_claim" ]] || return 0
     [[ "$(head -n 1 "$file" 2>/dev/null || true)" == "---" ]] || return 0
     # Renderer contract (lib/atomic_write.sh): a single `awk`, so the renderer's
@@ -764,17 +807,22 @@ splice_header_branches() {
     # ait_atomic_render also fixes the old `awk … > "$tmp" && mv …` form, which
     # left the temp behind whenever awk failed.
     _ait_splice_header_branches_body() {
-        awk -v base="$base" -v out="$out" -v wtc="$wt_claim" -v wt="$wt" '
+        awk -v base="$base" -v out="$out" -v wtc="$wt_claim" -v wt="$wt" -v br="$br" '
             NR == 1                 { print; next }
             done_fm                 { print; next }
             /^Worktree:/            { if (wtc != "") {
                                           if (wtc == "set") { print "Worktree: " wt; seen_wt = 1 }
                                           next   # wtc == "none" -> drop the line
                                       } }
+            /^Branch:/              { if (wtc != "") {
+                                          if (br != "") { print "Branch: " br; seen_br = 1 }
+                                          next   # empty br -> drop the line
+                                      } }
             /^Base branch:/         { if (base != "") { print "Base branch: " base; seen_base = 1; next } }
             /^Output branch:/       { if (out  != "") { print "Output branch: " out; seen_out  = 1; next } }
             $0 == "---" {
                 if (wtc == "set" && !seen_wt) print "Worktree: " wt
+                if (wtc != "" && br != "" && !seen_br) print "Branch: " br
                 if (base != "" && !seen_base) print "Base branch: " base
                 if (out  != "" && !seen_out)  print "Output branch: " out
                 done_fm = 1; print; next
@@ -830,14 +878,15 @@ if [[ "$has_frontmatter" == true ]]; then
         _splice_wt="$WORKTREE_PATH"
     elif [[ "$NO_WORKTREE_FLAG_SEEN" == true ]]; then
         # Positively "there is no worktree" -- clear any stale line, so a later
-        # session cannot consume it. `Worktree:` is the ONLY field --no-worktree
-        # deletes: the two branch fields are OVERWRITTEN with the detected primary
-        # instead, because an absent `Base branch:` is what Re-entry Routing reads
-        # as a legacy plan (and then confirms the guessed base with the user).
+        # session cannot consume it. `Worktree:` is the field --no-worktree
+        # deletes: the two branch fields are OVERWRITTEN with the checked-out
+        # branch instead, because an absent `Base branch:` is what Re-entry
+        # Routing reads as a legacy plan (and then confirms the guessed base with
+        # the user). `Branch:` follows build_header() -- see BRANCH_FIELD.
         _splice_wt_claim="none"
     fi
     splice_header_branches "$EXTERNAL_PLAN" "$_splice_base" "$_splice_out" \
-        "$_splice_wt_claim" "$_splice_wt"
+        "$_splice_wt_claim" "$_splice_wt" "$BRANCH_FIELD"
 fi
 
 if [[ "$EXISTED_BEFORE" == true ]]; then
diff --git a/.claude/skills/task-workflow/plan-externalization.md b/.claude/skills/task-workflow/plan-externalization.md
index 0968378..e778cba 100644
--- a/.claude/skills/task-workflow/plan-externalization.md
+++ b/.claude/skills/task-workflow/plan-externalization.md
@@ -24,7 +24,7 @@ Run the externalize helper. **Step 6 (proactive, from `planning.md`) must pass `
 - `--profile "aitasks/metadata/profiles/<active_profile_filename>"` — **only when `active_profile_filename` is set.** It is null on manual / resume invocations that carry no profile; passing a constructed path then would point at a file that does not exist, and the helper fails closed and aborts externalization. Omit the flag entirely in that case. When present, the helper reads `output_branch`, `base_branch` and `create_worktree` from it with a real YAML parser (so `output_branch: "dev"`, `'dev'` and `dev # comment` all resolve to `dev`), validates every scalar **inside the parser** before it is serialized, and fails closed on a missing, malformed or non-mapping file. Passing a *path* rather than a value keeps a user-authored branch name out of your command line. A profile `base_branch` is used for **both** header fields — it is recorded as `Base branch:` and it is the last-resort merge target.
 - `--base-branch-file <path>` — when the base branch was chosen **interactively** rather than taken from the profile. Write the selected name to a scratch file with a **non-shell tool** (the Write tool), then pass the path. Do **not** use `--base-branch "<value>"` for an interactive answer: substituting it into a command line re-creates the injection sink, because git accepts refs like `release$(id -u)` and that expands *before* the helper can validate anything — even inside double quotes. Keep the scratch file until **Step 8** has run — Step 8 reuses the same `<branch-flags>`. Delete it only after Step 8 reaches a terminal result. (A no-op Step 8 tolerates a missing file and still returns `PLAN_EXISTS`, but any call that actually writes the header needs it.) This one flag covers both fields: it is recorded as `Base branch:` **and** becomes the merge target when the profile sets no `output_branch`.
 - `--worktree aiwork/<task_name>` — when Step 5 resolved **worktree** mode. **Pass it even though the directory does not exist yet.** The fork is deferred to Step 7 while this call runs in Step 6, so the flag carries Step-5 *intent*; the helper records `Worktree:` from it and never probes the filesystem. Omitting it silently drops the field from the header (the helper warns on stderr when a call makes no worktree claim at all).
-- `--no-worktree` — when Step 5 worked on the current branch. Neither `base_branch` nor `output_branch` applies outside worktree mode, since nothing is cut and nothing is merged; both fields are therefore **overwritten with the detected primary branch**, so a stale value from an earlier worktree-mode run cannot survive for a later session to consume. The lines are **not removed** — an absent `Base branch:` is what Re-entry Routing reads as a legacy plan, and Step 7 then confirms the guessed base with the user before cutting. `Worktree:` is the one field this flag genuinely deletes.
+- `--no-worktree` — when Step 5 worked on the current branch. Neither `base_branch` nor `output_branch` applies outside worktree mode, since nothing is cut and nothing is merged; both fields are therefore **overwritten with the checked-out branch** — the one the work lands on (the detected primary only on a detached HEAD, where there is no branch to name) — so a stale value from an earlier worktree-mode run cannot survive for a later session to consume, and a resumed session is never pointed at a branch the work never touched. The lines are **not removed** — an absent `Base branch:` is what Re-entry Routing reads as a legacy plan, and Step 7 then confirms the guessed base with the user before cutting. `Worktree:` is the one field this flag genuinely deletes. (`Branch:` follows the same rule as a fresh header: the checked-out branch, omitted when it is the primary; with `--worktree` it is `aitask/<task_name>`.)
 
 `--worktree` and `--no-worktree` are **mutually exclusive**, and the helper fails closed on both a conflicting pair and on `--worktree` against a profile whose `create_worktree` is `false`.
 
@@ -44,7 +44,7 @@ Below, `<branch-flags>` stands for the resolution flags established above. Build
 - Add `--no-worktree` when Step 5 worked on the current branch.
 - Add `--worktree aiwork/<task_name>` when Step 5 resolved worktree mode.
 
-Current-branch mode **always** includes `--no-worktree` — it is what tells the helper there is no merge target, and it is also what **resets** a stale `Output branch:` left in a plan's frontmatter by an earlier run **to the detected primary branch**. So the minimal set for a no-profile, current-branch invocation is `--no-worktree`, not an empty one. Symmetrically, **worktree mode always includes `--worktree aiwork/<task_name>`**: it is the only thing that puts `Worktree:` in the header, because the deferred fork means the directory is not on disk yet when this call runs. An empty `<branch-flags>` is only correct for a bare backward-compatible helper call that makes no claim about the merge target at all.
+Current-branch mode **always** includes `--no-worktree` — it is what tells the helper there is no merge target, and it is also what **resets** a stale `Output branch:` left in a plan's frontmatter by an earlier run **to the checked-out branch**. So the minimal set for a no-profile, current-branch invocation is `--no-worktree`, not an empty one. Symmetrically, **worktree mode always includes `--worktree aiwork/<task_name>`**: it is the only thing that puts `Worktree:` in the header, because the deferred fork means the directory is not on disk yet when this call runs. An empty `<branch-flags>` is only correct for a bare backward-compatible helper call that makes no claim about the merge target at all.
 
 Step 6 form (proactive, after `ExitPlanMode`):
 
diff --git a/.claude/skills/task-workflow/planning.md b/.claude/skills/task-workflow/planning.md
index 7271128..f916751 100644
--- a/.claude/skills/task-workflow/planning.md
+++ b/.claude/skills/task-workflow/planning.md
@@ -458,7 +458,12 @@ they must come from that one resolution rather than from two different sources:
   to the wrong branch.
 
 In **current-branch mode** neither branch is resolved (nothing is cut, nothing is
-merged): record the detected primary branch in both fields, and omit `Worktree:`.
+merged): record the checked-out branch — the one the work lands on — in both
+fields (the detected primary only on a detached HEAD), and omit `Worktree:`.
+
+`Branch:` is the branch the work is committed on: `aitask/<task_name>` in worktree
+mode (cut later by Step 7 — not the branch checked out while planning), else the
+checked-out branch, omitted when that is the primary.
 
 `Worktree:` records the **intent** Step 5 resolved, not a directory that exists.
 Externalization runs here in Step 6 while the fork is deferred to Step 7, so the
```

## Tests to port into `tests/test_plan_externalize.sh`

The downstream pins the behaviour with the self-contained suite below (bash +
git only; never passes `--profile`, so it needs no Python). Port its cases
C1-C10 into the upstream suite — they are the first upstream cases that check
out a non-primary branch:

```bash
#!/usr/bin/env bash
# Behavioural tests for the vendored .aitask-scripts/aitask_plan_externalize.sh
# (t65): the plan header's Base/Output/Branch fields name the branch the work
# lands on -- never the repository primary while HEAD is on another branch, and
# `aitask/<task_name>` for a worktree task. Upstream's own suite never checks out
# a non-primary branch, so an `ait upgrade` that restored the old behaviour would
# pass it; this suite is what notices.
#
# Offline and Python-free: no case passes --profile (its YAML parser is the
# helper's only Python use), and stub interpreters prove none is invoked, so the
# CI runner's Python environment is irrelevant. Git runs with an empty HOME.
#
# Every assertion is input -> header output, never source text, so an upstream
# fix or refactor that keeps the behaviour keeps this green. To prove the suite
# still detects the defect, point it at a pre-t65 helper (it must fail):
#   EXTERNALIZE=<old>/.aitask-scripts/aitask_plan_externalize.sh bash <this file>
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HELPER="${EXTERNALIZE:-$REPO_ROOT/.aitask-scripts/aitask_plan_externalize.sh}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

mkdir -p "$WORK/home" "$WORK/nopy"
export HOME="$WORK/home" GIT_CONFIG_NOSYSTEM=1
unset XDG_CONFIG_HOME

t_pass=0; t_fail=0
ok()  { t_pass=$((t_pass+1)); printf '    ok   %s\n' "$1"; }
bad() { t_fail=$((t_fail+1)); printf '    FAIL %s\n' "$1"; }
pass_if() { local d="$1"; shift; if "$@"; then ok "$d"; else bad "$d"; fi; }

# Any Python use leaves a marker and fails the run (C9).
for p in python3 python; do
    printf '#!/bin/sh\ntouch "%s/python_called"\nexit 97\n' "$WORK" > "$WORK/nopy/$p"
    chmod +x "$WORK/nopy/$p"
done

# sandbox [frontmatter-plan]: a repo on `main` with a `dev` branch and
# origin/HEAD -> origin/main, task t999 and an internal plan. Prints its path.
sandbox() {
    local d
    d="$(mktemp -d "$WORK/sb.XXXXXX")"
    (
        cd "$d" || exit 1
        git init --quiet -b main
        git config user.email t65@test.invalid
        git config user.name t65
        git config commit.gpgsign false
        mkdir -p aitasks aiplans plans
        printf -- '---\npriority: medium\nstatus: Ready\n---\n\nSandbox task body.\n' \
            > aitasks/t999_sandbox_task.md
        git add -A && git commit --quiet -m init
        git branch dev
        git update-ref refs/remotes/origin/main HEAD
        git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main
        printf '# Sandbox plan\n\n- Step 1\n' > plans/internal.md
    ) || return 1
    [ -z "${1:-}" ] || printf '%s' "$1" > "$d/plans/internal.md"
    echo "$d"
}

# run <sandbox> <args...>: externalize t999 there. Sets RC, ERR and PLAN.
run() {
    local d="$1"; shift
    PLAN="$d/aiplans/p999_sandbox_task.md"
    ERR="$(cd "$d" && env AIT_PYTHON="$WORK/nopy/python3" PATH="$WORK/nopy:$PATH" \
        AIT_PLAN_EXTERNALIZE_INTERNAL_DIR="$d/plans" \
        "$HELPER" 999 --internal "$d/plans/internal.md" --force "$@" 2>&1 >/dev/null)"
    RC=$?
}

has_line() { grep -qxF -- "$2" "$1" 2>/dev/null; }
no_field() { [ -f "$1" ] && ! grep -q -- "^$2:" "$1"; }
once()     { [ "$(grep -cxF -- "$2" "$1" 2>/dev/null)" = 1 ]; }
fences()   { [ "$(grep -cx -- '---' "$1" 2>/dev/null)" = 2 ]; }
body()     { awk 'n >= 2 { print } /^---$/ { n++ }' "$1"; }
rc_is()    { [ "$RC" -eq "$1" ]; }

WT=(--worktree aiwork/t999_sandbox_task --base-branch dev --output-branch dev)

echo "  -- aitask_plan_externalize.sh branch fields (t65) --"

sb="$(sandbox)"; git -C "$sb" checkout --quiet dev
run "$sb" --no-worktree
pass_if "C1 current-branch on dev: exit 0" rc_is 0
pass_if "C1 Base branch is the checked-out dev" has_line "$PLAN" "Base branch: dev"
pass_if "C1 Output branch is the checked-out dev" has_line "$PLAN" "Output branch: dev"
pass_if "C1 Branch is dev" has_line "$PLAN" "Branch: dev"
pass_if "C1 no Worktree line" no_field "$PLAN" Worktree

sb="$(sandbox)"; git -C "$sb" checkout --quiet dev
run "$sb" "${WT[@]}"
pass_if "C2 worktree on dev: exit 0" rc_is 0
pass_if "C2 Branch is the task branch, not the checked-out dev" \
    once "$PLAN" "Branch: aitask/t999_sandbox_task"
pass_if "C2 Base branch dev" has_line "$PLAN" "Base branch: dev"
pass_if "C2 Output branch dev" has_line "$PLAN" "Output branch: dev"
pass_if "C2 Worktree recorded" has_line "$PLAN" "Worktree: aiwork/t999_sandbox_task"

sb="$(sandbox)"; git -C "$sb" checkout --quiet --detach main
run "$sb" --no-worktree
pass_if "C3 detached HEAD: exit 0" rc_is 0
pass_if "C3 Base branch falls back to the primary" has_line "$PLAN" "Base branch: main"
pass_if "C3 Output branch falls back to the primary" has_line "$PLAN" "Output branch: main"
pass_if "C3 no Branch line" no_field "$PLAN" Branch

sb="$(sandbox)"
run "$sb" --no-worktree
pass_if "C4 current-branch on main: exit 0" rc_is 0
pass_if "C4 Base branch main" has_line "$PLAN" "Base branch: main"
pass_if "C4 Output branch main" has_line "$PLAN" "Output branch: main"
pass_if "C4 no Branch line on the primary" no_field "$PLAN" Branch

sb="$(sandbox)"
run "$sb" "${WT[@]}"
pass_if "C5 worktree on main: exit 0" rc_is 0
pass_if "C5 Branch is the task branch (the intended on-primary change)" \
    once "$PLAN" "Branch: aitask/t999_sandbox_task"
pass_if "C5 Base branch dev" has_line "$PLAN" "Base branch: dev"
pass_if "C5 Output branch dev" has_line "$PLAN" "Output branch: dev"

sb="$(sandbox)"; git -C "$sb" checkout --quiet dev
run "$sb" --base-branch dev --output-branch dev
pass_if "C6 no worktree claim: exit 0" rc_is 0
pass_if "C6 Branch stays the checked-out dev" has_line "$PLAN" "Branch: dev"
pass_if "C6 Base branch dev" has_line "$PLAN" "Base branch: dev"
pass_if "C6 Output branch dev" has_line "$PLAN" "Output branch: dev"
pass_if "C6 no Worktree line" no_field "$PLAN" Worktree

# C7: sources that already carry frontmatter go through the splice, which
# replaces present fields in place and appends missing ones before the closing
# fence -- so assert value, uniqueness and fence integrity, not global order.
front='---
Task: t999_sandbox_task.md
Branch: dev
Base branch: main
Output branch: main
---

# Sandbox plan

- Step 1
'
sb="$(sandbox "$front")"; git -C "$sb" checkout --quiet dev
run "$sb" "${WT[@]}"
pass_if "C7i splice with --worktree: exit 0" rc_is 0
pass_if "C7i one Branch, the task branch" once "$PLAN" "Branch: aitask/t999_sandbox_task"
pass_if "C7i one Base branch, dev" once "$PLAN" "Base branch: dev"
pass_if "C7i one Output branch, dev" once "$PLAN" "Output branch: dev"
pass_if "C7i one Worktree line" once "$PLAN" "Worktree: aiwork/t999_sandbox_task"
pass_if "C7i exactly two fences" fences "$PLAN"
pass_if "C7i body unchanged" \
    test "$(body "$PLAN")" = "$(body "$sb/plans/internal.md")"

stale_front="${front/Task: t999_sandbox_task.md/Task: t999_sandbox_task.md
Worktree: aiwork/stale}"
sb="$(sandbox "$stale_front")"; git -C "$sb" checkout --quiet dev
run "$sb" --no-worktree
pass_if "C7ii splice with --no-worktree: exit 0" rc_is 0
pass_if "C7ii one Branch, dev" once "$PLAN" "Branch: dev"
pass_if "C7ii one Base branch, dev" once "$PLAN" "Base branch: dev"
pass_if "C7ii one Output branch, dev" once "$PLAN" "Output branch: dev"
pass_if "C7ii stale Worktree removed" no_field "$PLAN" Worktree
pass_if "C7ii exactly two fences" fences "$PLAN"

# C8: git accepts this ref; the header must not. It is recorded only in
# current-branch mode, so that is where it has to fail closed.
bad_ref="dev\$(id)"
sb="$(sandbox)"; git -C "$sb" checkout --quiet -b "$bad_ref"
run "$sb" --no-worktree
pass_if "C8 unsafe checked-out branch: non-zero exit" test "$RC" -ne 0
pass_if "C8 stderr names the unsafe branch" grep -q "unsafe branch name" <<<"$ERR"
pass_if "C8 no plan written" test ! -e "$PLAN"
git -C "$sb" checkout --quiet dev
run "$sb" --no-worktree
pass_if "C8 control: the same sandbox on dev exits 0" rc_is 0

# C10: a tag named like the branch makes `git symbolic-ref --short` answer
# `heads/dev`, which the drift check would look up as refs/heads/heads/dev.
sb="$(sandbox)"; git -C "$sb" tag dev
# Same commit, so pointing HEAD at the branch is a checkout -- without the
# ambiguity warning `checkout`/`switch` print for a name that is also a tag.
git -C "$sb" symbolic-ref HEAD refs/heads/dev
run "$sb" --no-worktree
pass_if "C10 tag beside the branch, current-branch: exit 0" rc_is 0
pass_if "C10 Base branch is dev, not heads/dev" has_line "$PLAN" "Base branch: dev"
pass_if "C10 Output branch is dev, not heads/dev" has_line "$PLAN" "Output branch: dev"
pass_if "C10 Branch is dev, not heads/dev" has_line "$PLAN" "Branch: dev"
run "$sb" --base-branch dev --output-branch dev
pass_if "C10 tag beside the branch, no claim: Branch is dev" has_line "$PLAN" "Branch: dev"

pass_if "C9 no Python interpreter was invoked by any case" test ! -e "$WORK/python_called"
sb="$(sandbox)"
printf 'create_worktree: false\n' > "$sb/prof.yaml"
run "$sb" --profile prof.yaml --no-worktree
pass_if "C9 control: a --profile run does reach the stub (marker created)" \
    test -e "$WORK/python_called"
pass_if "C9 control: and fails without a real interpreter" test "$RC" -ne 0

printf '    %d/%d plan_externalize branch-field assertions passed\n' "$t_pass" "$((t_pass+t_fail))"
[ "$t_fail" -eq 0 ]
```

Dev-time negative control used downstream: the suite run against the pre-fix
helper (`EXTERNALIZE=<old helper>`) fails C1, C2, C5, C7i, C7ii, C8 and C10.

## Verification

- `tests/test_plan_externalize.sh` stays green; the ported C1-C10 cases pass and
  fail against the pre-fix helper.
- Docs in every agent tree say: current-branch mode records the checked-out
  branch (primary only on a detached HEAD); `Branch:` is `aitask/<task_name>`
  with `--worktree`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-23T08:22:20Z status=pass attempt=1 type=human
