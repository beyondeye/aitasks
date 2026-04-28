---
Task: t705_release_pull_before_push_and_changelog_sync.md
Base branch: main
plan_verified: []
---

# Plan: t705 — Sync with remote before release push and changelog gather

## Context

The v0.19.0 release just half-failed: `create_new_release.sh` pushed the
`v0.19.0` tag successfully, then `git push origin main` was rejected because
local `main` was 30 commits ahead but 1 commit behind `origin/main`. The
remote ended up with the tag but a stale branch tip; manual recovery
(`git merge origin/main && git push`) was required.

Two related defects need fixing:

1. **`create_new_release.sh`** does `git push origin main --tags` (line 74)
   without first verifying the local branch is fast-forward to remote. The
   tag-and-push must be atomic — either both go through, or neither does.

2. **`/aitask-changelog`** (`.claude/skills/aitask-changelog/SKILL.md`) calls
   `aitask_changelog.sh --gather` against local refs only. If remote has
   commits the local checkout doesn't, those tasks are silently absent from
   the generated changelog. The skill never fetches before gathering.

## Approach

Two minimal, surgical edits — no new helper scripts, no refactoring.

### 1. `create_new_release.sh`

Insert a "sync with remote" block **after** existing tag-existence check
(line 24) and **before** the changelog check. Steps:

- Verify the current branch is `main` (releases must be cut from `main`).
  Abort with a clear message if not.
- `git fetch origin --quiet`. On fetch failure, prompt user: continue
  without verification or abort (mirrors the existing changelog-confirm
  prompt style).
- Compare `git rev-parse main` vs `git rev-parse origin/main`. If equal,
  proceed. If not equal:
  - `behind=$(git rev-list --count main..origin/main)` /
    `ahead=$(git rev-list --count origin/main..main)`
  - If `behind > 0`, attempt `git pull --rebase origin main`.
    - On success: continue.
    - On failure (conflicts): abort with a message telling the user to
      resolve manually before re-running.

Rationale for `--rebase` (not `--ff-only`): the typical real-world case is
local-ahead-and-behind (linear changes the user pushed elsewhere — e.g.
the t658 macOS-compat audit). `--ff-only` would fail in that case and
force the user to merge manually.

### 2. `.claude/skills/aitask-changelog/SKILL.md`

Add a **Step 0: Sync with Remote** section before "Step 1: Gather Release
Data". Procedure:

- Run `git fetch origin --quiet`. On fetch failure, warn the user and
  proceed (changelog can still be drafted from local data; this is a
  best-effort sync, not a hard gate).
- Compute `behind=$(git rev-list --count main..origin/main 2>/dev/null
  || echo 0)`.
- If `behind == 0`, proceed to Step 1 silently.
- If `behind > 0`, use `AskUserQuestion`:
  - Question: "Local main is N commits behind origin/main. The changelog
    will miss those tasks unless you sync first. How to proceed?"
  - Header: "Sync"
  - Options:
    - "Pull and continue" (description: "Run `git pull --rebase origin
      main` and proceed")
    - "Skip sync (changelog may be incomplete)" (description: "Continue
      with local-only history")
    - "Abort" (description: "Exit without making changes")
- "Pull and continue": run `git pull --rebase origin main`. On failure,
  abort with a clear message.
- "Skip sync": proceed to Step 1.
- "Abort": end workflow.

This goes before Step 1 because the gather output (commit list, archived
plans) depends on what's in the local working tree. Putting the sync
later would mean the user reviews a draft generated from stale data.

## Files to modify

- `create_new_release.sh` — insert sync block between line 24 (tag check)
  and line 27 (changelog check). ~25 lines added.
- `.claude/skills/aitask-changelog/SKILL.md` — insert new "Step 0: Sync
  with Remote" section before the existing "Step 1: Gather Release Data"
  (currently around line 8). Renumber is unnecessary — the new step is
  Step 0, existing Step 1+ unchanged.

## Out of scope

- Mirroring the SKILL.md change in `.gemini/`, `.codex/`, `.opencode/`
  trees. Per CLAUDE.md "WORKING ON SKILLS" section, skill changes land in
  Claude Code first. Suggest a follow-up task at end of implementation.
- Adding sync logic to `aitask_changelog.sh` itself. The script just
  reads git data; the skill is the right layer for interactive decisions.
- Refactoring the sync logic into a shared helper (e.g.,
  `aitask_release_sync.sh`). With only two callers and ~10 lines of
  shell each, a helper is premature abstraction.

## Verification

1. **Manual smoke (release script):**
   - On a scratch checkout, `git reset --hard HEAD~1` to put local
     `main` behind `origin/main` by 1 commit.
   - Run `./create_new_release.sh`, enter a fake new version.
   - Expected: script pulls/rebases cleanly before any tag work, prints
     a "synced" message, then continues to the version-bump prompt.
2. **Manual smoke (release script — abort path):**
   - Force a divergence that won't rebase cleanly (edit a file locally
     that conflicts with origin's HEAD).
   - Run the script.
   - Expected: script aborts with "resolve manually" message before any
     `VERSION` write, no tag created.
3. **Manual smoke (changelog skill):**
   - Reset local `main` behind by 1 commit.
   - Run `/aitask-changelog`.
   - Expected: skill prompts "Local main is 1 commit behind…" with three
     options. Choosing "Pull and continue" pulls then proceeds; "Skip"
     proceeds with local-only data; "Abort" exits cleanly.
4. **Linting:** `shellcheck create_new_release.sh`.

## Reference: existing patterns reused

- `aitask_pick_own.sh:77` and `aitask_lock_diag.sh:74` already use
  `git fetch origin "$BRANCH" --quiet` — same pattern.
- `aitask_crew_addwork.sh:314` uses `git pull --rebase --quiet 2>/dev/null
  || true` — looser variant; we want stricter (abort on conflict) for
  release flow.

## Step 9 (Post-Implementation)

Standard archival flow per `.claude/skills/task-workflow/SKILL.md` Step 9.
No worktree to clean up (working on current branch per profile `fast`).
After commit, suggest follow-up tasks for:
- Mirroring the changelog SKILL.md change to `.gemini/`, `.codex/`,
  `.opencode/` skill trees.

## Final Implementation Notes

- **Actual work done:** Two surgical edits as planned. (1) `create_new_release.sh` gained a sync block between the tag-existence check and the changelog check: branch guard (must be `main`), `git fetch origin --quiet` (with continue-or-abort prompt on fetch failure), then if local `main` differs from `origin/main` and local is behind by ≥1 commit, runs `git pull --rebase origin main` and aborts on rebase failure. (2) `.claude/skills/aitask-changelog/SKILL.md` gained a new Step 0 before Step 1 with a best-effort fetch and an `AskUserQuestion` (Pull / Skip / Abort) when behind.
- **Deviations from plan:** None substantive. Used `git fetch origin --quiet 2>&1 || echo "FETCH_FAILED"` in the SKILL.md doc snippet rather than ad-hoc prose for fetch-failure detection — clearer for the agent to parse.
- **Issues encountered:** None.
- **Key decisions:** Kept the sync logic inline (no shared helper) — only two callers, ~10 lines each; a helper would be premature. Used `--rebase` over `--ff-only` because the realistic recurring case (the v0.19.0 incident itself) is local-ahead-and-behind, where `--ff-only` would force the user to merge manually anyway.
- **Upstream defects identified:** None.
