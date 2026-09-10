#!/usr/bin/env bash
# test_sync_branch_mode_automerge.sh - Branch-mode conflict resolution in
# `ait sync` (t1243_8 §0 gate).
#
# Run: bash tests/test_sync_branch_mode_automerge.sh
#
# Why this file exists
# --------------------
# `tests/test_sync.sh` exercises auto-merge only in LEGACY mode (task data on
# the current branch). In BRANCH mode (a real `.aitask-data` worktree) three
# defects in `try_auto_merge` combined so that frontmatter auto-merge could
# never succeed, and the entire suite was blind to it:
#
#   1. AUTHORIZATION — `task_git add` is a mutating verb, so
#      `assert_data_worktree_clean` rejects it while the data worktree is
#      mid-rebase, which is precisely when conflict resolution runs.
#   2. SWALLOWED FAILURE — `|| true` discarded that rejection, the file was
#      counted as resolved and "Auto-merged:" was printed, so the problem only
#      surfaced later as a `rebase --continue` failure with the diagnostic
#      already thrown away.
#   3. CHANNEL POLLUTION — `try_auto_merge`'s STDOUT is the unresolved-file
#      list its caller parses, but the merge driver's own stdout ("RESOLVED" /
#      "PARTIAL:...") was not redirected, so it was reported as a conflicted
#      filename. The observed output was literally `CONFLICT:RESOLVED`.
#
# Test 1 fails against pre-fix code (it reports CONFLICT:RESOLVED, not
# AUTOMERGED). Tests 2 and 3 are the honesty guarantees the `|| true` made
# unassertable.
#
# Tests 6-8 (t1676) cover the SAME class one stage later, in the INTERACTIVE
# resolution loop that handles whatever the driver could not merge. Defects 1
# and 2 above were never fixed there, and a third compounds them:
#
#   4. PIPELINE SUBSHELL — the loop ran as `echo "$remaining" | while … done`,
#      so `assert_data_worktree_clean`'s die() (an `exit 1` that `|| true`
#      cannot catch) ended the LOOP after the first file, and the `else`
#      branch's `all_resolved=false` never escaped the subshell to reach the
#      check that consumes it.
#
# Test 6 pins that every remaining file is offered and staged; Test 7 the
# staging-failure route; Test 8 the editor-failure route, which involves no
# die() and is therefore about the lost assignment alone.

set -uo pipefail

TEST_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

. "$PROJECT_DIR/tests/lib/asserts.sh"

# --- Setup helper ---------------------------------------------------------
# Build a bare remote + a BRANCH-MODE local clone (real .aitask-data worktree,
# aitasks/ symlink) + a pc2 clone that has already pushed a conflicting edit.
# The local clone holds a committed, conflicting edit on an ADJACENT line, so
# the rebase necessarily produces an overlapping hunk rather than a clean
# textual auto-merge. Echoes the tmpdir.
setup_branch_mode_repos() {
    local tmpdir
    tmpdir="$(mktemp -d)"

    git init -q --bare "$tmpdir/remote.git"
    git clone -q "$tmpdir/remote.git" "$tmpdir/local" 2>/dev/null
    (
        cd "$tmpdir/local"
        git config user.email test@test.com
        git config user.name Test
        git config commit.gpgsign false
        echo "# project" > README.md
        git add -A
        git commit -q -m "init"
        git branch -M main
        git push -q -u origin main 2>/dev/null

        # Orphan aitask-data branch + worktree (mirrors `ait setup`'s layout).
        local empty_tree branch_commit
        empty_tree=$(git mktree < /dev/null)
        branch_commit=$(echo "ait: Initialize aitask-data branch" \
            | git commit-tree "$empty_tree")
        git update-ref refs/heads/aitask-data "$branch_commit"
        git worktree add -q .aitask-data aitask-data
        mkdir -p .aitask-data/aitasks .aitask-data/aiplans

        # `status` and `boardcol` are ADJACENT so the two sides' edits land in
        # one overlapping hunk. Non-adjacent edits merge cleanly and would never
        # reach the driver — see Test 4.
        cat > .aitask-data/aitasks/t1_sample.md <<'TASKEOF'
---
priority: high
status: Ready
boardcol: backlog
labels: [ui]
updated_at: 2026-01-01 10:00
---
Task body stays the same
TASKEOF
        ln -s .aitask-data/aitasks aitasks
        ln -s .aitask-data/aiplans aiplans
        git -C .aitask-data add -A
        git -C .aitask-data -c user.email=test@test.com -c user.name=Test \
            commit -q -m "data init"
        git -C .aitask-data push -q -u origin aitask-data 2>/dev/null

        cp "$PROJECT_DIR/ait" ./ait
        chmod +x ./ait
        cp -r "$PROJECT_DIR/.aitask-scripts" ./.aitask-scripts
        git add -A 2>/dev/null
        git commit -q -m "framework" 2>/dev/null
        git push -q 2>/dev/null
    ) >/dev/null 2>&1

    # pc2 pushes a conflicting change to the data branch.
    git clone -q "$tmpdir/remote.git" "$tmpdir/pc2" 2>/dev/null
    (
        cd "$tmpdir/pc2"
        git config user.email test2@test.com
        git config user.name Test2
        git config commit.gpgsign false
        git checkout -q aitask-data
        cat > aitasks/t1_sample.md <<'TASKEOF'
---
priority: high
status: Ready
boardcol: now
labels: [ui]
updated_at: 2026-01-01 10:00
---
Task body stays the same
TASKEOF
        git add -A
        git commit -q -m "pc2: boardcol"
        git push -q 2>/dev/null
    ) >/dev/null 2>&1

    # local commits its own conflicting edit on the adjacent `labels` line.
    (
        cd "$tmpdir/local"
        cat > .aitask-data/aitasks/t1_sample.md <<'TASKEOF'
---
priority: high
status: Ready
boardcol: backlog
labels: [api, ui]
updated_at: 2026-01-01 10:00
---
Task body stays the same
TASKEOF
        git -C .aitask-data add -A
        git -C .aitask-data -c user.email=test@test.com -c user.name=Test \
            commit -q -m "local: labels"
    ) >/dev/null 2>&1

    echo "$tmpdir"
}

# Portable ANSI strip. Single definition, shared by the real call site and its
# portability control below, so the two cannot drift.
#
# NOTE: $'\033[' — NOT 's/\x1b\[...' . GNU sed understands \x1b, but BSD sed
# (macOS) does not: it matches a literal `x`, `1`, `b`, so that form silently
# no-ops and the colour wrapper survives with no error at all. The $'...'
# quoting makes BASH emit the literal ESC byte, so sed never has to interpret
# an escape and the expression behaves identically on both.
# See aidocs/framework/sed_macos_issues.md.
strip_ansi() { sed $'s/\033\[[0-9;]*m//g'; }

# Install a `git` shim that passes everything through EXCEPT `add`, and only
# while a rebase is in progress in the data worktree. That scoping is required:
# `ait sync` runs `git add` during its auto-commit step BEFORE the pull, and a
# blanket-failing shim would abort the run before a conflict ever exists.
install_failing_add_shim() {
    local repo="$1" bindir="$2" real_git
    real_git="$(command -v git)"
    mkdir -p "$bindir"
    cat > "$bindir/git" <<SHIMEOF
#!/usr/bin/env bash
for _a in "\$@"; do
    if [[ "\$_a" == "add" ]]; then
        if [[ -e "$repo/.git/worktrees/-aitask-data/rebase-merge" \
           || -e "$repo/.git/worktrees/-aitask-data/rebase-apply" ]]; then
            echo "fatal: simulated staging failure (test shim)" >&2
            exit 128
        fi
        break
    fi
done
exec "$real_git" "\$@"
SHIMEOF
    chmod +x "$bindir/git"
}

echo "=== ait sync branch-mode auto-merge Tests ==="
echo ""

# --- Test 1: AUTOMERGED in branch mode (the authorization gate) ---
echo "--- Test 1: branch-mode frontmatter conflict auto-resolves ---"

TMP1="$(setup_branch_mode_repos)"

# Positive control: the rebase must genuinely conflict. Without this the test
# could pass on a clean textual auto-merge that never invoked the driver.
(cd "$TMP1/local" && git -C .aitask-data fetch -q origin 2>/dev/null
 git -C .aitask-data rebase origin/aitask-data >/dev/null 2>&1 || true)
unmerged=$(cd "$TMP1/local" && git -C .aitask-data diff --name-only --diff-filter=U 2>/dev/null)
assert_contains "Fixture actually produces an unmerged path" \
    "aitasks/t1_sample.md" "$unmerged"
(cd "$TMP1/local" && git -C .aitask-data rebase --abort >/dev/null 2>&1 || true)

output=$(cd "$TMP1/local" && ./ait sync --batch 2>/dev/null)
assert_eq_trim "Branch-mode conflict returns AUTOMERGED" "AUTOMERGED" "$output"

merged=$(cat "$TMP1/local/.aitask-data/aitasks/t1_sample.md")
assert_contains "Merged file keeps local boardcol" "boardcol: backlog" "$merged"
assert_contains "Merged file has merged labels (api)" "api" "$merged"
assert_contains "Merged file has merged labels (ui)" "ui" "$merged"

# The path must be staged and merged, not left unmerged.
still_unmerged=$(cd "$TMP1/local" && git -C .aitask-data diff --name-only --diff-filter=U 2>/dev/null)
assert_eq "No unmerged paths remain after auto-merge" "" "$still_unmerged"

rm -rf "$TMP1"

# --- Test 2: a failed stage is reported honestly, not as success ---
echo "--- Test 2: unstageable file is reported as CONFLICT, not AUTOMERGED ---"

TMP2="$(setup_branch_mode_repos)"
install_failing_add_shim "$TMP2/local" "$TMP2/shimbin"

output2=$(cd "$TMP2/local" && PATH="$TMP2/shimbin:$PATH" ./ait sync --batch 2>/dev/null)
assert_contains "Unstageable file returns CONFLICT" "CONFLICT:" "$output2"
assert_contains "CONFLICT names the task file" "aitasks/t1_sample.md" "$output2"

rm -rf "$TMP2"

# --- Test 3: diagnostic survives on stderr; stdout stays a clean file list ---
echo "--- Test 3: failure diagnostic on stderr, stdout is exactly the list ---"

TMP3="$(setup_branch_mode_repos)"
install_failing_add_shim "$TMP3/local" "$TMP3/shimbin"

out3=$(cd "$TMP3/local" && PATH="$TMP3/shimbin:$PATH" ./ait sync --batch 2>"$TMP3/err.txt")
err3=$(cat "$TMP3/err.txt")

# STDOUT must be EXACTLY the batch protocol line — no driver output
# ("RESOLVED"/"PARTIAL:"), no prose. A substring assertion would not have
# caught the `CONFLICT:RESOLVED` leak this guards.
assert_eq_trim "stdout is exactly the CONFLICT line for the task file" \
    "CONFLICT:aitasks/t1_sample.md" "$out3"
assert_contains "stderr preserves the staging diagnostic" \
    "could not stage" "$err3"
assert_contains "stderr preserves git's own message" \
    "simulated staging failure" "$err3"

rm -rf "$TMP3"

# --- Test 4: negative control — non-adjacent edits never reach the driver ---
echo "--- Test 4: negative control - far-apart edits merge textually ---"

TMP4="$(setup_branch_mode_repos)"
# Rewrite both sides so the two edits are far apart (priority vs a trailing
# field), with enough context between them that git merges cleanly.
(
    cd "$TMP4/pc2"
    git pull -q 2>/dev/null
    cat > aitasks/t1_sample.md <<'TASKEOF'
---
priority: low
status: Ready
boardcol: backlog
labels: [ui]
effort: low
issue_type: bug
assigned_to: a@b.c
updated_at: 2026-01-01 10:00
---
Task body stays the same
TASKEOF
    git add -A; git commit -q -m "pc2: priority only"; git push -q 2>/dev/null
) >/dev/null 2>&1
(
    cd "$TMP4/local"
    git -C .aitask-data reset -q --hard origin/aitask-data 2>/dev/null
    git -C .aitask-data fetch -q origin 2>/dev/null
    git -C .aitask-data reset -q --hard HEAD~1 2>/dev/null || true
) >/dev/null 2>&1

# This case documents WHY Test 1's fixture uses adjacent lines: it asserts the
# adjacency is load-bearing, so Test 1's positive control discriminates rather
# than always holding.
(
    cd "$TMP4/local"
    cat > .aitask-data/aitasks/t1_sample.md <<'TASKEOF'
---
priority: high
status: Ready
boardcol: backlog
labels: [ui]
effort: low
issue_type: bug
assigned_to: z@z.z
updated_at: 2026-01-01 10:00
---
Task body stays the same
TASKEOF
    git -C .aitask-data add -A
    git -C .aitask-data -c user.email=test@test.com -c user.name=Test \
        commit -q -m "local: assigned_to only" 2>/dev/null
    git -C .aitask-data fetch -q origin 2>/dev/null
    git -C .aitask-data rebase origin/aitask-data >/dev/null 2>&1 || true
) >/dev/null 2>&1
far_unmerged=$(cd "$TMP4/local" && git -C .aitask-data diff --name-only --diff-filter=U 2>/dev/null)
assert_eq "Far-apart edits produce NO unmerged path (control discriminates)" \
    "" "$far_unmerged"

rm -rf "$TMP4"

# --- Test 5: interactive mode - stdout carries ONLY real filenames ---
echo "--- Test 5: interactive conflict list is not polluted with prose ---"

# Mixed outcome (one file auto-resolves, one does not) is what exposes this:
# when everything resolves, `unresolved` is empty and the caller discards
# stdout, so the leak is invisible. With a leftover conflict the caller parses
# stdout as the file list and opens $EDITOR on every line — pre-fix that meant
# the driver's own "RESOLVED"/"PARTIAL:body" output and the "Auto-merged:"
# progress line were each treated as a filename, while the genuinely conflicted
# file was buried among them.
TMP5b="$(setup_branch_mode_repos)"
(
    cd "$TMP5b/local"
    # Add a second task whose BODY diverges, so it cannot auto-merge.
    printf -- '---\npriority: high\nstatus: Ready\n---\nBODY BASE\n' \
        > .aitask-data/aitasks/t2_body.md
    git -C .aitask-data add -A
    git -C .aitask-data -c user.email=test@test.com -c user.name=Test \
        commit -q -m "add second task"
    git -C .aitask-data push -q 2>/dev/null
) >/dev/null 2>&1
(
    cd "$TMP5b/pc2"
    git pull -q 2>/dev/null
    printf -- '---\npriority: high\nstatus: Ready\n---\nBODY FROM PC2\n' \
        > aitasks/t2_body.md
    git add -A; git commit -q -m "pc2: body"; git push -q 2>/dev/null
) >/dev/null 2>&1
(
    cd "$TMP5b/local"
    printf -- '---\npriority: high\nstatus: Ready\n---\nBODY FROM LOCAL\n' \
        > .aitask-data/aitasks/t2_body.md
    git -C .aitask-data add -A
    git -C .aitask-data -c user.email=test@test.com -c user.name=Test \
        commit -q -m "local: body"
) >/dev/null 2>&1

# EDITOR=true makes the interactive resolution loop a no-op we can observe.
int_out=$(cd "$TMP5b/local" && EDITOR=true ./ait sync 2>/dev/null || true)
int_clean=$(printf '%s' "$int_out" | strip_ansi)

# Portability control for strip_ansi, deliberately INDEPENDENT of whether
# `ait sync` colours its output: asserting that $int_out carries a wrapper would
# couple this conflict-resolution test to presentation policy. With the
# non-portable \x1b form this synthetic probe comes back untouched on BSD sed,
# so this assertion is what actually pins the platform behaviour.
assert_eq "strip_ansi removes ESC sequences (BSD/GNU portability control)" \
    "Editing: x" "$(printf '%s' $'\033[0;34mEditing: x\033[0m' | strip_ansi)"
# Cheap integration sanity check on the real output. Vacuous if the output is
# ever uncoloured — harmless, because the probe above carries the guard duty.
assert_eq "No ESC survives into int_clean" \
    "0" "$(printf '%s' "$int_clean" | grep -c $'\033' || true)"

assert_eq "No 'Auto-merged' progress prose reaches stdout" \
    "0" "$(printf '%s' "$int_clean" | grep -c 'Auto-merged' || true)"
assert_eq "No driver output (RESOLVED/PARTIAL) reaches stdout" \
    "0" "$(printf '%s' "$int_clean" | grep -cE 'RESOLVED|PARTIAL:' || true)"
assert_contains "The genuinely conflicted file IS offered for editing" \
    "Editing: aitasks/t2_body.md" "$int_clean"

rm -rf "$TMP5b"

# --- Shared scaffolding for the interactive-loop tests (6-8) --------------

# Fixture: exactly ONE local commit conflicting with exactly ONE remote commit
# over TWO files, so the whole conflict lands in a SINGLE rebase step. A
# multi-step rebase would need a second _rebase_advance round and make "did the
# rebase complete" ambiguous. BODY divergence (not frontmatter) is what makes
# the merge driver return PARTIAL, so both files survive try_auto_merge into
# `remaining` and actually reach the interactive loop — the same mechanism
# Test 5 relies on for its single file. Echoes the tmpdir.
setup_two_body_conflicts() {
    local tmpdir
    tmpdir="$(setup_branch_mode_repos)"
    (
        cd "$tmpdir/local"
        # Drop the base fixture's `local: labels` commit so t1_sample.md does
        # not participate and exactly one local commit is replayed.
        git -C .aitask-data fetch -q origin
        git -C .aitask-data reset -q --hard origin/aitask-data
        printf -- '---\npriority: high\nstatus: Ready\n---\nBODY FROM LOCAL\n' \
            > .aitask-data/aitasks/t2_body.md
        printf -- '---\npriority: high\nstatus: Ready\n---\nBODY FROM LOCAL\n' \
            > .aitask-data/aitasks/t3_body.md
        git -C .aitask-data add -A
        git -C .aitask-data -c user.email=test@test.com -c user.name=Test \
            commit -q -m "local: two bodies"
    ) >/dev/null 2>&1
    (
        cd "$tmpdir/pc2"
        git pull -q
        printf -- '---\npriority: high\nstatus: Ready\n---\nBODY FROM PC2\n' \
            > aitasks/t2_body.md
        printf -- '---\npriority: high\nstatus: Ready\n---\nBODY FROM PC2\n' \
            > aitasks/t3_body.md
        git add -A
        git commit -q -m "pc2: two bodies"
        git push -q
    ) >/dev/null 2>&1
    echo "$tmpdir"
}

# An $EDITOR that genuinely RESOLVES the file (keeps the "ours" side and drops
# the markers) and exits 0, so the loop takes its staging branch rather than its
# editor-failure branch. Path must contain no spaces — `$editor` is expanded
# UNQUOTED at the call site.
make_resolver_editor() {
    local bindir="$1"
    mkdir -p "$bindir"
    cat > "$bindir/resolve-editor" <<'RESOLVEEOF'
#!/usr/bin/env bash
f="$1"
awk '
  /^<<<<<<< / { inconf=1; keep=1; next }
  /^=======$/ { if (inconf) { keep=0; next } }
  /^>>>>>>> / { if (inconf) { inconf=0; keep=1; next } }
  { if (!inconf || keep) print }
' "$f" > "$f.resolved" && mv "$f.resolved" "$f"
RESOLVEEOF
    chmod +x "$bindir/resolve-editor"
}

# Shared failure-path assertion for Tests 7 and 8. Both failure branches call
# `task_git rebase --abort` (on _ait_git_subcmd_is_recovery, so it passes the
# state guard), so a run that reports failure must ALSO leave a clean worktree —
# otherwise the diagnostic is honest but the user is stranded mid-rebase.
#
# The git-dir is RESOLVED, not hardcoded as .git/worktrees/-aitask-data: that
# name is an implementation detail of `git worktree add`. An unresolvable
# git-dir is its own state and FAILS — "could not look" must never read as
# "nothing there".
assert_no_rebase_wedge() {
    local desc="$1" repo="$2" gd state
    gd=$(git -C "$repo/.aitask-data" rev-parse --absolute-git-dir 2>/dev/null || echo "")
    if [[ -z "$gd" ]]; then
        state="GITDIR_UNRESOLVED"
    elif [[ -e "$gd/rebase-merge" || -e "$gd/rebase-apply" ]]; then
        state="WEDGED"
    else
        state="clean"
    fi
    assert_eq "$desc: no rebase sentinel remains" "clean" "$state"
    assert_eq "$desc: no unmerged paths remain" "" \
        "$(git -C "$repo/.aitask-data" diff --name-only --diff-filter=U 2>/dev/null)"
}

# --- Test 6: the loop offers and stages EVERY remaining file ---
echo "--- Test 6: interactive loop does not stop after the first file ---"

TMP6="$(setup_two_body_conflicts)"
make_resolver_editor "$TMP6/bin"

# Positive control: the fixture must genuinely deliver BOTH files unmerged. A
# fixture that only ever produced one conflict would pass pre-fix and prove
# nothing — which is exactly the shape this defect hides in.
(cd "$TMP6/local" && git -C .aitask-data fetch -q origin 2>/dev/null
 git -C .aitask-data rebase origin/aitask-data >/dev/null 2>&1 || true)
ctl6=$(cd "$TMP6/local" && git -C .aitask-data diff --name-only --diff-filter=U 2>/dev/null)
assert_contains "Fixture yields t2_body.md unmerged" "aitasks/t2_body.md" "$ctl6"
assert_contains "Fixture yields t3_body.md unmerged" "aitasks/t3_body.md" "$ctl6"
(cd "$TMP6/local" && git -C .aitask-data rebase --abort >/dev/null 2>&1 || true)

rc6=0
out6=$(cd "$TMP6/local" && EDITOR="$TMP6/bin/resolve-editor" ./ait sync 2>/dev/null) || rc6=$?
clean6=$(printf '%s' "$out6" | strip_ansi)

# THE regression assertion: pre-fix, `task_git add` die()s inside the pipeline
# subshell, ending the loop after the first file — t3 is never offered at all.
assert_contains "First remaining file is offered" \
    "Editing: aitasks/t2_body.md" "$clean6"
assert_contains "SECOND remaining file is offered too" \
    "Editing: aitasks/t3_body.md" "$clean6"

# "Both STAGED" is what the two assertions below actually pin. A wedge check
# alone would not: pre-fix the run ends in `rebase --abort`, which also leaves a
# clean tree and unmarked files. Only a rebase that ADVANCED proves every file
# was staged — and advancing requires the whole loop to have run.
assert_exit_zero_rc "Resolved conflicts complete the sync" "$rc6"
assert_contains "Rebase advanced: the remote commit is in local history" \
    "pc2: two bodies" "$(cd "$TMP6/local" && git -C .aitask-data log --format=%s)"

assert_no_rebase_wedge "Test 6" "$TMP6/local"
assert_not_contains "committed t2_body.md has no leftover conflict markers" \
    "<<<<<<<" "$(cd "$TMP6/local" && git -C .aitask-data show HEAD:aitasks/t2_body.md 2>/dev/null)"
assert_not_contains "committed t3_body.md has no leftover conflict markers" \
    "<<<<<<<" "$(cd "$TMP6/local" && git -C .aitask-data show HEAD:aitasks/t3_body.md 2>/dev/null)"

rm -rf "$TMP6"

# --- Test 7: a failed stage is reported, not swallowed, and leaves no wedge ---
echo "--- Test 7: interactive staging failure is honest and unwedges ---"

TMP7="$(setup_two_body_conflicts)"
make_resolver_editor "$TMP7/bin"
install_failing_add_shim "$TMP7/local" "$TMP7/shimbin"

rc7=0
out7=$(cd "$TMP7/local" && PATH="$TMP7/shimbin:$PATH" \
    EDITOR="$TMP7/bin/resolve-editor" ./ait sync 2>"$TMP7/err.txt") || rc7=$?
clean7=$(printf '%s' "$out7" | strip_ansi)
err7=$(cat "$TMP7/err.txt")

# Pre-fix, `2>/dev/null` discarded the diagnostic and the die() ended the loop,
# so stderr said nothing at all about staging.
assert_contains "Staging failure is reported" "could not stage" "$err7"
assert_contains "Staging failure preserves git's own message" \
    "simulated staging failure" "$err7"
assert_contains "First remaining file offered (shim)" \
    "Editing: aitasks/t2_body.md" "$clean7"
assert_contains "Second remaining file offered (shim)" \
    "Editing: aitasks/t3_body.md" "$clean7"
assert_contains "Unstageable files are treated as unresolved" \
    "Not all conflicts resolved" "$err7"
assert_not_contains "Unstageable files do NOT fall through to rebase --continue" \
    "Rebase continue failed" "$err7"
assert_exit_nonzero_rc "Staging failure exits non-zero" "$rc7"
assert_no_rebase_wedge "Test 7" "$TMP7/local"

rm -rf "$TMP7"

# --- Test 8: a failing editor reaches the all_resolved check ---
echo "--- Test 8: editor failure reaches the all_resolved check ---"

# The branch Tests 6 and 7 do not touch. No die() is involved here, so the ONLY
# pre-fix defect is `all_resolved=false` dying with the pipeline subshell.
TMP8="$(setup_two_body_conflicts)"

rc8=0
out8=$(cd "$TMP8/local" && EDITOR=false ./ait sync 2>"$TMP8/err.txt") || rc8=$?
err8=$(cat "$TMP8/err.txt")

# NOT a discriminator — with no die(), pre-fix code offers both files too. It
# pins that the restructured loop still visits every file.
assert_contains "Editor failure reported for the first file" \
    "Editor exited with error for aitasks/t2_body.md" "$err8"
assert_contains "Editor failure reported for the second file" \
    "Editor exited with error for aitasks/t3_body.md" "$err8"

# THE discriminator: pre-fix the lost assignment sent control into
# _rebase_advance, which failed on the unstaged remainder and printed the other
# message. Both directions are pinned so the branch flip cannot be faked.
assert_contains "Editor failure aborts as unresolved" \
    "Not all conflicts resolved" "$err8"
assert_not_contains "Editor failure does NOT reach rebase --continue" \
    "Rebase continue failed" "$err8"

# CONTRACT, not a discriminator: both branches `return 1`, so pre-fix exits
# non-zero too. It guards a future regression that swallows the failure and
# reports SYNCED.
assert_exit_nonzero_rc "Editor failure exits non-zero" "$rc8"
assert_no_rebase_wedge "Test 8" "$TMP8/local"

rm -rf "$TMP8"

# --- Test 9: the advance-failure path (t1727 loop rc 2) ---------------------
# ait_automerge_rebase_loop's OTHER non-zero result: every conflict merged and
# staged, nothing left unresolved, yet neither `rebase --continue` nor
# `rebase --skip` works. No natural fixture produces it, so it is injected
# through the same argv-keyed PATH shim seam Tests 2/3/7 use.
#
# It is also the regression test for the `set -euo pipefail` absorbing capture:
# aitask_sync.sh calls the loop as `ait_automerge_rebase_loop || loop_rc=$?`,
# and a bare call would exit the shell on this very rc before the
# ERROR:rebase_continue_failed token was ever printed.
echo "--- Test 9: advance failure -> ERROR token, no wedge ---"

install_failing_advance_shim() {
    local bindir="$1" real_git
    real_git="$(command -v git)"
    mkdir -p "$bindir"
    # Fails ONLY the two advance verbs. `--abort` must still work, or the
    # cleanup this test asserts could not run and the assertion would pass for
    # the wrong reason.
    cat > "$bindir/git" <<SHIMEOF
#!/usr/bin/env bash
_saw_rebase=0
for _a in "\$@"; do
    [[ "\$_a" == "rebase" ]] && _saw_rebase=1
    if [[ \$_saw_rebase -eq 1 && ( "\$_a" == "--continue" || "\$_a" == "--skip" ) ]]; then
        echo "fatal: simulated advance failure (test shim)" >&2
        exit 128
    fi
done
exec "$real_git" "\$@"
SHIMEOF
    chmod +x "$bindir/git"
}

TMP9="$(setup_branch_mode_repos)"
install_failing_advance_shim "$TMP9/shimbin"

rc9=0
out9=$(cd "$TMP9/local" && PATH="$TMP9/shimbin:$PATH" ./ait sync --batch 2>"$TMP9/err.txt") || rc9=$?
clean9=$(printf '%s' "$out9" | strip_ansi)

# The token is the whole point: reaching it proves the shell did NOT exit on
# the loop's rc 2.
assert_eq_trim "advance failure reports ERROR:rebase_continue_failed" \
    "ERROR:rebase_continue_failed" "$clean9"
assert_exit_nonzero_rc "advance failure exits non-zero" "$rc9"
# Negative control: it must NOT be mistaken for an unresolvable conflict — the
# files DID merge, so a CONFLICT: token here would name files that are fine.
assert_not_contains "advance failure is not reported as CONFLICT" \
    "CONFLICT:" "$clean9"
assert_no_rebase_wedge "Test 9" "$TMP9/local"

rm -rf "$TMP9"

# =============================================================================
# Tests 10-14 (t1747_2): ait_automerge_advance must never discard a commit on an
# unverified assumption. Rows A1 and A2 of the fail-open probe audit — rule and
# dispositions: aidocs/framework/failopen_git_probes.md
#
# Three ways today's build ran `rebase --skip` (which DISCARDS the replayed
# commit) and still reported AUTOMERGED at rc 0:
#   A1   the advance's own unresolved-file probe could not be read   (Test 11)
#   A1'  the probe was read, but "nothing unresolved" was taken for
#        "empty patch" while `--continue` had failed for another reason (12)
#   A2   the LOOP-ENTRY probe could not be read, so the resolver was
#        skipped and control fell straight into the advance           (Test 14)
# Test 10 is the permit direction all three must leave intact; Test 13 pins the
# helpers' call sites so a new consumer cannot be added without a disposition.
#
# Every half has its own fixture AND its own mutant control: each control
# regresses exactly one half in the FIXTURE's copy of lib/task_automerge.sh
# (never the real one) and must observe that half's defect.
# =============================================================================

# assert_defect_present <desc> <condition-cmd...> — the control INVERTS: the
# defect must be observable against the regressed build. (tests/test_fold_mark.sh)
assert_defect_present() {
    local desc="$1"; shift
    TOTAL=$((TOTAL + 1))
    if "$@"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: negative control — $desc (the regressed build did NOT exhibit the defect; the test above proves nothing)"
    fi
}

_eq() { [[ "$1" == "$2" ]]; }
# <tmpdir> <subject> — is a commit with exactly this subject on local's data branch?
_local_log_has()   { git -C "$1/local/.aitask-data" log --format=%s | grep -qxF -- "$2"; }
_local_log_lacks() { ! _local_log_has "$@"; }
# <shimbin> <needle> — did the shimmed git see this argv fragment?
_git_log_has()     { grep -qF -- "$2" "$1/git.log" 2>/dev/null; }
_yes_no()          { if "$@"; then echo yes; else echo no; fi; }

# Fixture P: a conflict whose auto-merge lands EXACTLY on HEAD — a genuinely
# empty patch. local changes only `updated_at`, to an OLDER value; pc2 changes
# `priority` and a NEWER `updated_at` on the adjacent line. The hunks overlap, so
# the rebase really conflicts, yet the driver resolves to pc2's file verbatim.
# (Fixture R is plain setup_branch_mode_repos: its merge is a real patch.)
# Echoes the tmpdir.
setup_empty_patch_conflict() {
    local tmpdir
    tmpdir="$(setup_branch_mode_repos)"
    (
        cd "$tmpdir/local"
        git -C .aitask-data fetch -q origin
        git -C .aitask-data reset -q --hard origin/aitask-data~1
        printf -- '---\npriority: high\nupdated_at: 2026-01-01 09:00\n---\nBody\n' \
            > .aitask-data/aitasks/t1_sample.md
        git -C .aitask-data add -A
        git -C .aitask-data -c user.email=test@test.com -c user.name=Test \
            commit -q -m "local: older ts only"
    ) >/dev/null 2>&1
    (
        cd "$tmpdir/pc2"
        git fetch -q origin
        git reset -q --hard origin/aitask-data~1
        printf -- '---\npriority: low\nupdated_at: 2026-01-01 12:00\n---\nBody\n' \
            > aitasks/t1_sample.md
        git add -A
        git commit -q -m "pc2: priority and newer ts"
        git push -q -f
    ) >/dev/null 2>&1
    echo "$tmpdir"
}

# install_advance_shim <bindir> <mode> — the argv-keyed PATH shim of
# install_failing_advance_shim, extended to log every invocation to
# <bindir>/git.log (so "was --skip attempted?" is observed, not inferred).
# <mode> selects what fails:
#   continue        `rebase --continue` only. That is the state OLD git (< 2.26)
#                   produces natively for an empty patch — current git's
#                   --continue drops an empty commit itself and never reaches the
#                   --skip fallback — so the case is production-reachable.
#   continue+probe  the above, AND `diff --diff-filter=U` once a `--continue` has
#                   been seen: exactly the probe the --skip fallback consults.
#                   do_pull_rebase's probe and the loop-entry probe run earlier
#                   and must stay readable, or the advance is never reached.
#   late-probe      no rebase verb; every `diff --diff-filter=U` AFTER THE FIRST
#                   fails. do_pull_rebase makes exactly one before the loop, so
#                   the loop-entry probe is the first unreadable one.
# `--skip` and `--abort` always pass through: the fallback must stay reachable,
# and the cleanup these tests assert must be able to run.
install_advance_shim() {
    local bindir="$1" mode="$2" real_git
    real_git="$(command -v git)"
    mkdir -p "$bindir"
    cat > "$bindir/git" <<SHIMEOF
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "$bindir/git.log"
_rebase=0 _cont=0 _diff=0 _u=0
for _a in "\$@"; do
    case "\$_a" in
        rebase) _rebase=1 ;;
        --continue) [[ \$_rebase -eq 1 ]] && _cont=1 ;;
        diff) _diff=1 ;;
        --diff-filter=U) _u=1 ;;
    esac
done
case "$mode" in
    continue|continue+probe)
        if [[ \$_cont -eq 1 ]]; then
            : > "$bindir/.continue-seen"
            echo "fatal: simulated continue failure (test shim)" >&2
            exit 128
        fi
        if [[ "$mode" == "continue+probe" && \$_diff -eq 1 && \$_u -eq 1 \\
              && -e "$bindir/.continue-seen" ]]; then
            echo "fatal: simulated unreadable index (test shim)" >&2
            exit 128
        fi ;;
    late-probe)
        if [[ \$_diff -eq 1 && \$_u -eq 1 ]]; then
            if [[ -e "$bindir/.probe-seen" ]]; then
                echo "fatal: simulated unreadable index (test shim)" >&2
                exit 128
            fi
            : > "$bindir/.probe-seen"
        fi ;;
esac
exec "$real_git" "\$@"
SHIMEOF
    chmod +x "$bindir/git"
}

# wrap_merge_driver <repo> <marker> — replace the fixture's merge driver with a
# wrapper that touches <marker>, then runs the real one. "The resolver never
# ran" becomes an observation; Test 14's marker control proves the wrapper works.
wrap_merge_driver() {
    local drv="$1/.aitask-scripts/board/aitask_merge.py" marker="$2"
    mv "$drv" "$drv.real"
    cat > "$drv" <<PYEOF
import runpy, sys
open("$marker", "w").close()
sys.argv[0] = "$drv.real"
runpy.run_path("$drv.real", run_name="__main__")
PYEOF
}

# run_sync <tmpdir> [shimbin] — `ait sync --batch` in the fixture's local clone.
# Sets SYNC_OUT (ANSI-stripped stdout) and SYNC_RC; stderr -> <tmpdir>/err.txt.
run_sync() {
    local tmp="$1" bin="${2:-}" out rc=0
    if [[ -n "$bin" ]]; then
        out=$(cd "$tmp/local" && PATH="$bin:$PATH" ./ait sync --batch 2>"$tmp/err.txt") || rc=$?
    else
        out=$(cd "$tmp/local" && ./ait sync --batch 2>"$tmp/err.txt") || rc=$?
    fi
    SYNC_OUT=$(printf '%s' "$out" | strip_ansi)
    SYNC_RC=$rc
}

# --- Mutant installers --------------------------------------------------------
# Each regresses ONE half of the fix in the fixture's copy, fails loudly on a
# stale anchor, proves its substitution landed, and proves the rest of the
# advance survived — otherwise a control observes "no guard" rather than
# "fail-open guard". They compose; cross-half survival is checked by the caller.

# _automerge_replace <repo> <old> <new> — exactly-once literal replacement.
_automerge_replace() {
    python3 - "$1/.aitask-scripts/lib/task_automerge.sh" "$2" "$3" <<'PY'
import sys
p, old, new = sys.argv[1:4]
s = open(p).read()
n = s.count(old)
if n != 1:
    sys.stderr.write("FATAL: mutant anchor matched %d times (stale?): %r\n" % (n, old))
    sys.exit(1)
open(p, "w").write(s.replace(old, new, 1))
PY
}

# _require <present|absent> <file> <fixed-string> <what went wrong>
_require() {
    local want="$1" f="$2" needle="$3" msg="$4" found=absent
    grep -qF -- "$needle" "$f" && found=present
    if [[ "$found" != "$want" ]]; then
        echo "FAIL: negative control — $msg"
        FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
        return 1
    fi
}

_control_ok() { TOTAL=$((TOTAL + 1)); PASS=$((PASS + 1)); }

_control_install_failed() {
    echo "FAIL: negative control — could not install the $1 mutant (anchor gone stale?)"
    FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
}

# A1: the advance's probe back to `|| true`.
install_prefix_a1_probe() {
    local f="$1/.aitask-scripts/lib/task_automerge.sh"
    _automerge_replace "$1" \
'    local unresolved="" u_rc=0
    unresolved="$(_ait_data_git diff --name-only --diff-filter=U 2>/dev/null)" || u_rc=$?
    (( u_rc == 0 )) || return 1
' \
'    local unresolved
    unresolved=$(_ait_data_git diff --name-only --diff-filter=U 2>/dev/null || true)
' || { _control_install_failed "A1 probe"; return 1; }
    _require absent  "$f" 'u_rc' "A1: the status capture is still in place" || return 1
    _require present "$f" 'diff-filter=U 2>/dev/null || true)' "A1: the fail-open probe was not installed" || return 1
    _require present "$f" 'ait_automerge_advance() {' "A1: the advance itself was excised" || return 1
    _require present "$f" 'rebase --skip' "A1: the --skip fallback was excised" || return 1
    _control_ok
}

# A1': drop the empty-patch verification.
install_no_emptiness_check() {
    local f="$1/.aitask-scripts/lib/task_automerge.sh"
    _automerge_replace "$1" \
'    local e_rc=0
    _ait_data_git diff --cached --quiet HEAD >/dev/null 2>&1 || e_rc=$?
    (( e_rc == 0 )) || return 1
' \
'' || { _control_install_failed "emptiness check"; return 1; }
    _require absent  "$f" 'diff --cached --quiet HEAD' "A1': the emptiness check is still in place" || return 1
    _require present "$f" '[[ -z "$unresolved" ]] || return 1' "A1': the unresolved gate was excised" || return 1
    _require present "$f" 'ait_automerge_advance() {' "A1': the advance itself was excised" || return 1
    _require present "$f" 'rebase --skip' "A1': the --skip fallback was excised" || return 1
    _control_ok
}

# A2: the loop's probe helper back to `|| true` (its consumers untouched).
install_prefix_a2_probe() {
    local f="$1/.aitask-scripts/lib/task_automerge.sh"
    _automerge_replace "$1" \
'_ait_automerge_conflicted_now() {
    local out="" rc=0
    out="$(_ait_data_git diff --name-only --diff-filter=U 2>/dev/null)" || rc=$?
    (( rc == 0 )) || return 2
    printf '"'"'%s'"'"' "$out"
}' \
'_ait_automerge_conflicted_now() {
    _ait_data_git diff --name-only --diff-filter=U 2>/dev/null || true
}' || { _control_install_failed "A2 probe"; return 1; }
    _require absent  "$f" "printf '%s' \"\$out\"" "A2: the tri-state helper is still in place" || return 1
    _require present "$f" '    _ait_data_git diff --name-only --diff-filter=U 2>/dev/null || true' "A2: the fail-open probe was not installed" || return 1
    _require present "$f" '|| c_rc=$?' "A2: the consumers' absorbing capture was excised" || return 1
    _control_ok
}

# --- Test 10: the permit direction — a VERIFIED empty patch is still skipped --
echo "--- Test 10: a verified-empty patch still takes the --skip fallback ---"

# Precondition: P really is an empty patch. Unshimmed, current git drops an empty
# replayed commit during `--continue` itself; had the patch been real, a commit
# with this subject would survive the replay. (On older git --continue stops
# instead, and the fallback below produces the same end state.)
TMP10c="$(setup_empty_patch_conflict)"
run_sync "$TMP10c"
assert_eq_trim "P control: unshimmed run auto-merges" "AUTOMERGED" "$SYNC_OUT"
assert_exit_zero_rc "P control: unshimmed run succeeds" "$SYNC_RC"
assert_eq "P control: the replayed commit was empty (nothing of it survives)" "no" \
    "$(_yes_no _local_log_has "$TMP10c" "local: older ts only")"
assert_contains "P control: the result is pc2's file verbatim" "priority: low" \
    "$(cat "$TMP10c/local/.aitask-data/aitasks/t1_sample.md")"
rm -rf "$TMP10c"

# The same fixture with `--continue` failing, as old git does: the fallback must
# still fire, because the patch is verifiably empty. This is also precondition (a)
# for Test 11 — same fixture, same --continue failure, probe readable ⇒ --skip
# taken and succeeding, so Test 11's refusal can only come from the probe.
TMP10="$(setup_empty_patch_conflict)"
install_advance_shim "$TMP10/shimbin" continue
run_sync "$TMP10" "$TMP10/shimbin"
assert_eq_trim "verified-empty patch: still AUTOMERGED" "AUTOMERGED" "$SYNC_OUT"
assert_exit_zero_rc "verified-empty patch: sync succeeds" "$SYNC_RC"
assert_eq "verified-empty patch: --continue was failed (the fallback was needed)" "yes" \
    "$(_yes_no _git_log_has "$TMP10/shimbin" "rebase --continue")"
assert_eq "verified-empty patch: the --skip fallback was taken" "yes" \
    "$(_yes_no _git_log_has "$TMP10/shimbin" "rebase --skip")"
assert_no_rebase_wedge "Test 10" "$TMP10/local"
rm -rf "$TMP10"

# --- Test 11: A1 — an unread probe never authorises --skip ---------------------
echo "--- Test 11: an unread unresolved-file probe refuses --skip ---"

TMP11="$(setup_empty_patch_conflict)"
install_advance_shim "$TMP11/shimbin" continue+probe

# Precondition (b): the shim makes the probe unreadable — and ONLY once a
# --continue has been seen, so the earlier probes stay readable.
probe_before=0
"$TMP11/shimbin/git" -C "$TMP11/local/.aitask-data" diff --name-only --diff-filter=U \
    >/dev/null 2>&1 || probe_before=$?
: > "$TMP11/shimbin/.continue-seen"
probe_after=0
"$TMP11/shimbin/git" -C "$TMP11/local/.aitask-data" diff --name-only --diff-filter=U \
    >/dev/null 2>&1 || probe_after=$?
rm -f "$TMP11/shimbin/.continue-seen" "$TMP11/shimbin/git.log"
assert_exit_zero_rc "probe shim: readable before any --continue" "$probe_before"
assert_exit_nonzero_rc "probe shim: UNREADABLE once --continue was seen" "$probe_after"

run_sync "$TMP11" "$TMP11/shimbin"
assert_eq_trim "unread probe: reports ERROR:rebase_continue_failed" \
    "ERROR:rebase_continue_failed" "$SYNC_OUT"
assert_exit_nonzero_rc "unread probe: exits non-zero" "$SYNC_RC"
assert_eq "unread probe: --skip was never attempted" "no" \
    "$(_yes_no _git_log_has "$TMP11/shimbin" "rebase --skip")"
assert_eq "unread probe: the replayed commit is still reachable" "yes" \
    "$(_yes_no _local_log_has "$TMP11" "local: older ts only")"
assert_no_rebase_wedge "Test 11" "$TMP11/local"
rm -rf "$TMP11"

# Negative control: A1 alone regressed. The emptiness check must survive, or the
# --skip below would not be A1's doing.
TMP11m="$(setup_empty_patch_conflict)"
if install_prefix_a1_probe "$TMP11m/local" \
   && _require present "$TMP11m/local/.aitask-scripts/lib/task_automerge.sh" \
        'diff --cached --quiet HEAD' "A1 control: the emptiness check must survive"; then
    install_advance_shim "$TMP11m/shimbin" continue+probe
    run_sync "$TMP11m" "$TMP11m/shimbin"
    assert_defect_present "pre-fix A1: an unread probe authorises --skip" \
        _git_log_has "$TMP11m/shimbin" "rebase --skip"
    assert_defect_present "pre-fix A1: the run reports AUTOMERGED" \
        _eq "$SYNC_OUT" "AUTOMERGED"
    assert_defect_present "pre-fix A1: the replayed commit is gone" \
        _local_log_lacks "$TMP11m" "local: older ts only"
fi
rm -rf "$TMP11m"

# --- Test 12: A1' — "nothing unresolved" is not "empty patch" -----------------
echo "--- Test 12: a real patch is never skipped when --continue fails ---"

TMP12="$(setup_branch_mode_repos)"
# Precondition: R is a REAL patch — local contributes content pc2 does not have.
assert_contains "R: local's commit adds a label" "api" \
    "$(git -C "$TMP12/local/.aitask-data" show HEAD:aitasks/t1_sample.md 2>/dev/null)"
assert_not_contains "R: pc2's side does not have it" "api" \
    "$(git -C "$TMP12/pc2" show HEAD:aitasks/t1_sample.md 2>/dev/null)"

install_advance_shim "$TMP12/shimbin" continue
run_sync "$TMP12" "$TMP12/shimbin"
assert_eq_trim "real patch: reports ERROR:rebase_continue_failed" \
    "ERROR:rebase_continue_failed" "$SYNC_OUT"
assert_exit_nonzero_rc "real patch: exits non-zero" "$SYNC_RC"
assert_eq "real patch: --skip was never attempted" "no" \
    "$(_yes_no _git_log_has "$TMP12/shimbin" "rebase --skip")"
assert_eq "real patch: the local commit is still reachable" "yes" \
    "$(_yes_no _local_log_has "$TMP12" "local: labels")"
assert_no_rebase_wedge "Test 12" "$TMP12/local"
rm -rf "$TMP12"

# Negative control: the emptiness check alone removed (A1's capture survives).
TMP12m="$(setup_branch_mode_repos)"
if install_no_emptiness_check "$TMP12m/local" \
   && _require present "$TMP12m/local/.aitask-scripts/lib/task_automerge.sh" \
        '|| u_rc=$?' "A1' control: A1's status capture must survive"; then
    install_advance_shim "$TMP12m/shimbin" continue
    run_sync "$TMP12m" "$TMP12m/shimbin"
    assert_defect_present "pre-fix A1': a real patch is skipped" \
        _git_log_has "$TMP12m/shimbin" "rebase --skip"
    assert_defect_present "pre-fix A1': the run reports AUTOMERGED" \
        _eq "$SYNC_OUT" "AUTOMERGED"
    assert_defect_present "pre-fix A1': the local commit is gone" \
        _local_log_lacks "$TMP12m" "local: labels"
fi
rm -rf "$TMP12m"

# --- Test 13: every consumer of the two helpers has a recorded disposition ----
echo "--- Test 13: helper call sites equal the disposition table ---"

# One "<path>::<function>::<helper><TAB><tagged|untagged>" row per CALL site.
# Function spans follow this codebase's `name() {` ... `}` (column 0) layout;
# comment lines are not calls. A site is "tagged" when the comment block
# DIRECTLY above it (no blank or code line between) contains `unverified:`, so a
# second call placed after a tagged one cannot borrow its tag.
#
# What this buys: a call site added, moved to another function, or dropped into
# lib/task_automerge.sh without its own disposition turns this test red. What it
# does NOT buy: it never checks that a tag's text is TRUE of the code under it,
# and the tag rule covers lib/task_automerge.sh only — aitask_sync.sh's probes are
# rows A3/A4/A5/A10 (t1747_3), so its consumer is pinned by identity alone.
AUTOMERGE_CALLSITE_AWK='
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

# Files are selected with POSIX `find -name`, not `grep -r --include`: GNU grep
# matches --include against the basename, BSD/macOS grep against the full path
# (grep(1) on both), and no CI job runs this suite on macOS to catch the split.
automerge_callsites() {
    local root="$1" f
    find "$root" -type f -name '*.sh' \
        -exec grep -lE 'ait_automerge_advance|_ait_automerge_conflicted_now' {} + |
    while IFS= read -r f; do
        awk -v HELPERS="ait_automerge_advance _ait_automerge_conflicted_now" \
            -v REL="${f#"$root"/}" "$AUTOMERGE_CALLSITE_AWK" "$f"
    done | LC_ALL=C sort
}

# The scanner can fail: a second call borrowing a tag, a top-level call, and a
# comment that merely NAMES a helper must each be classified correctly.
SELF13="$(mktemp -d)"
cat > "$SELF13/x.sh" <<'SELFEOF'
f_one() {
    # unverified: only the first call carries this
    ait_automerge_advance
    ait_automerge_advance
}
# a comment naming ait_automerge_advance is not a call
_ait_automerge_conflicted_now
SELFEOF
assert_eq "scanner self-test: attribution and per-site tags" \
    "$(printf 'x.sh::<toplevel>::_ait_automerge_conflicted_now\tuntagged\nx.sh::f_one::ait_automerge_advance\ttagged\nx.sh::f_one::ait_automerge_advance\tuntagged\n' | LC_ALL=C sort)" \
    "$(automerge_callsites "$SELF13")"
rm -rf "$SELF13"

rows13="$(automerge_callsites "$PROJECT_DIR/.aitask-scripts")"
expected13="$(printf '%s\n' \
    'aitask_sync.sh::do_pull_rebase::ait_automerge_advance' \
    'lib/task_automerge.sh::ait_automerge_rebase_loop::ait_automerge_advance' \
    'lib/task_automerge.sh::ait_automerge_rebase_loop::_ait_automerge_conflicted_now' \
    'lib/task_automerge.sh::ait_automerge_rebase_loop::_ait_automerge_conflicted_now' \
    | LC_ALL=C sort)"
ids13="$(printf '%s\n' "$rows13" | cut -f1)"
assert_eq "call-site identities equal the disposition table" "$expected13" "$ids13"
if [[ "$ids13" != "$expected13" ]]; then
    echo "  -> a consumer of ait_automerge_advance / _ait_automerge_conflicted_now changed."
    echo "     Give it an explicit disposition for 'unverified' (see"
    echo "     aidocs/framework/failopen_git_probes.md rows A1/A2), then update this table."
fi
# A scan that finds nothing must fail, not pass: pin the count and the definitions.
assert_eq "exactly four call sites" "4" "$(printf '%s\n' "$rows13" | grep -c .)"
assert_eq "ait_automerge_advance is defined once" "1" \
    "$(grep -cF 'ait_automerge_advance() {' "$PROJECT_DIR/.aitask-scripts/lib/task_automerge.sh")"
assert_eq "_ait_automerge_conflicted_now is defined once" "1" \
    "$(grep -cF '_ait_automerge_conflicted_now() {' "$PROJECT_DIR/.aitask-scripts/lib/task_automerge.sh")"
assert_eq "every lib/task_automerge.sh call site carries its own unverified: tag" "" \
    "$(printf '%s\n' "$rows13" | grep -F 'lib/task_automerge.sh::' | grep -F "$(printf '\tuntagged')" || true)"

# --- Test 14: A2 — an unread loop-entry probe refuses before any merge --------
echo "--- Test 14: an unread loop-entry probe refuses before merge or advance ---"

# Marker control: with no shim the wrapped driver runs and the marker appears, so
# its absence below is evidence rather than a broken wrapper.
TMP14c="$(setup_branch_mode_repos)"
wrap_merge_driver "$TMP14c/local" "$TMP14c/resolver_ran"
run_sync "$TMP14c"
assert_eq_trim "marker control: the wrapped driver still auto-merges" "AUTOMERGED" "$SYNC_OUT"
assert_eq "marker control: the wrapper records a resolver run" "yes" \
    "$(_yes_no test -e "$TMP14c/resolver_ran")"
rm -rf "$TMP14c"

TMP14="$(setup_branch_mode_repos)"
wrap_merge_driver "$TMP14/local" "$TMP14/resolver_ran"
install_advance_shim "$TMP14/shimbin" late-probe
run_sync "$TMP14" "$TMP14/shimbin"
# Chosen so a typo in the status capture cannot pass: a shell that died inside
# the command substitution prints no token and leaves a wedge; a capture that
# failed to return 2 lets the resolver run and the advance verbs into the log.
assert_eq_trim "unread loop-entry probe: reports ERROR:rebase_continue_failed" \
    "ERROR:rebase_continue_failed" "$SYNC_OUT"
assert_exit_nonzero_rc "unread loop-entry probe: exits non-zero" "$SYNC_RC"
assert_eq "unread loop-entry probe: the resolver never ran" "no" \
    "$(_yes_no test -e "$TMP14/resolver_ran")"
assert_eq "unread loop-entry probe: no rebase --continue" "no" \
    "$(_yes_no _git_log_has "$TMP14/shimbin" "rebase --continue")"
assert_eq "unread loop-entry probe: no rebase --skip" "no" \
    "$(_yes_no _git_log_has "$TMP14/shimbin" "rebase --skip")"
assert_eq "unread loop-entry probe: the caller aborted the rebase" "yes" \
    "$(_yes_no _git_log_has "$TMP14/shimbin" "rebase --abort")"
assert_eq "unread loop-entry probe: the local commit is still reachable" "yes" \
    "$(_yes_no _local_log_has "$TMP14" "local: labels")"
assert_no_rebase_wedge "Test 14" "$TMP14/local"
rm -rf "$TMP14"

# Negative control: A2 alone regressed (A1 and the emptiness check still fixed).
# Its own defect: an unread loop-entry probe falls through to the advance.
TMP14m="$(setup_branch_mode_repos)"
if install_prefix_a2_probe "$TMP14m/local"; then
    install_advance_shim "$TMP14m/shimbin" late-probe
    run_sync "$TMP14m" "$TMP14m/shimbin"
    assert_defect_present "pre-fix A2: an unread loop-entry probe reaches the advance" \
        _git_log_has "$TMP14m/shimbin" "rebase --continue"
fi
rm -rf "$TMP14m"

# Negative control: the whole pre-fix build — the outcome measured before the fix
# landed. Silent success, resolver never run, commit discarded.
TMP14p="$(setup_branch_mode_repos)"
wrap_merge_driver "$TMP14p/local" "$TMP14p/resolver_ran"
if install_prefix_a2_probe "$TMP14p/local" \
   && install_prefix_a1_probe "$TMP14p/local" \
   && install_no_emptiness_check "$TMP14p/local"; then
    install_advance_shim "$TMP14p/shimbin" late-probe
    run_sync "$TMP14p" "$TMP14p/shimbin"
    assert_defect_present "pre-fix build: reports AUTOMERGED" _eq "$SYNC_OUT" "AUTOMERGED"
    assert_defect_present "pre-fix build: exits zero" _eq "$SYNC_RC" "0"
    assert_defect_present "pre-fix build: the resolver never ran" \
        test ! -e "$TMP14p/resolver_ran"
    assert_defect_present "pre-fix build: the local commit is gone" \
        _local_log_lacks "$TMP14p" "local: labels"
fi
rm -rf "$TMP14p"

# --- Summary ---
echo ""
echo "=== Results: $PASS passed, $FAIL failed (of $TOTAL) ==="
[[ $FAIL -eq 0 ]] || exit 1
exit 0
