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

# --- Summary ---
echo ""
echo "=== Results: $PASS passed, $FAIL failed (of $TOTAL) ==="
[[ $FAIL -eq 0 ]] || exit 1
exit 0
