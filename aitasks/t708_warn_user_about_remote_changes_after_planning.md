---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [task_workflow, gitremote]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-28 22:19
updated_at: 2026-04-28 22:27
---

## Context

The `aitask-pick` and `task-workflow` skills currently sync only the **task-data branch** before adding new work — never the code branch.

- `aitask-pick` Step 0c (`SKILL.md:89-97`) runs `./.aitask-scripts/aitask_pick_own.sh --sync`, which calls `task_sync()` in `lib/task_utils.sh:177`. That function does `git pull --rebase --quiet` against `_AIT_DATA_WORKTREE` only — i.e. the `aitask-data` branch in branch-mode setups.
- `task-workflow` Step 5 (`SKILL.md:200-225`) creates a worktree from local `<base-branch>` (default `main`) with no `git fetch` first.
- Step 9 merges into local `main` without pulling `origin/main`.
- Planning (`planning.md`) has no fetch/pull at any step.

In branch-mode (where code lives on `main` and task data lives on `aitask-data`), this means: even though task locks prevent double-claiming, code branches can be created from a stale local `main`. If `origin/main` advanced meanwhile — particularly on files the plan intends to change — the user implements against an out-of-date base, then either rediscovers the conflict during the final merge or silently produces a redundant/incompatible change.

## Goal

After the user approves the plan in Step 6 (and before Step 7 starts implementing), the workflow should warn if `origin/<base-branch>` has new commits relative to local `<base-branch>`. The warning should be **stronger when the remote-only commits touch files referenced in the plan**.

## Proposed behavior

Insert a new sub-step between the Step 6 Checkpoint and Step 7 (or as the last action of the checkpoint after "Start implementation" is selected):

1. **Best-effort fetch:** `git fetch origin <base-branch>` — non-blocking; on failure (no network, etc.) skip silently.
2. **Compute remote-ahead commits:**
   ```bash
   git rev-list --count <base-branch>..origin/<base-branch>
   git diff --name-only <base-branch>..origin/<base-branch>
   ```
3. **Compute plan-affected files:** Extract path-like tokens from the plan file. Reasonable patterns: `\.aitask-scripts/[A-Za-z0-9_./-]+`, `\.claude/skills/[A-Za-z0-9_./-]+`, `aiplans/[^ )]+`, `aitasks/[^ )]+`, `website/[^ )]+`, `seed/[^ )]+`, plus any `.sh|.py|.md|.yaml|.json|.toml` file referenced. (Plans don't have a structured "Files Affected" section — see e.g. `aiplans/archived/p632_force_exact_tmux_session_targeting.md` — so regex extraction is the only general approach.)
4. **Decide warning level:**
   - If remote-ahead = 0 → no warning, proceed.
   - If remote-ahead > 0 and intersection with plan-affected files is non-empty → **strong warning** listing the overlapping files.
   - If remote-ahead > 0 with no overlap → soft warning (informational).
5. **AskUserQuestion** with options:
   - "Stop, pull `<base-branch>`, and re-verify plan" (description: "Recommended when overlap exists — abort cleanly, run `git pull` on the base, then re-pick the task")
   - "Continue anyway" (description: "Proceed to implementation; you'll need to handle conflicts at merge time")
   - "Abort task" (description: "Release the lock and revert task status")

## Implementation pointers

- **New helper script:** `./.aitask-scripts/aitask_remote_drift_check.sh <base-branch> <plan_file>` — fetches `origin/<base-branch>`, computes ahead-count, diffs file list, intersects with plan-extracted paths, prints structured output (`AHEAD:<n>`, `OVERLAP:<file>` lines, `NO_OVERLAP`, etc.). Encapsulating the logic in a helper is consistent with the project's "Single source of truth for cross-script constants" memory and makes the SKILL.md change a thin wrapper that just calls the script and parses output.
- **Whitelisting checklist** for the new helper (see CLAUDE.md "Adding a New Helper Script"):
  - `.claude/settings.local.json`
  - `.gemini/policies/aitasks-whitelist.toml`
  - `seed/claude_settings.local.json`
  - `seed/geminicli_policies/aitasks-whitelist.toml`
  - `seed/opencode_config.seed.json`
  - (Codex needs no entry — prompt-only model.)
- **Skill files to update:**
  - `.claude/skills/task-workflow/SKILL.md` — add the new sub-step
  - `.claude/skills/task-workflow/planning.md` — reference the new sub-step in the Checkpoint section so the post-plan-action profile interaction is clearly defined
  - Mirror the same change into `.opencode/skills/task-workflow/`, `.gemini/skills/task-workflow/`, `.agents/skills/task-workflow/` (per CLAUDE.md "WORKING ON SKILLS / CUSTOM COMMANDS"; create separate aitasks for those if not done in the same task).
- **Profile key:** Consider adding `remote_drift_check: warn|skip|strong-only` to execution profiles (default `warn`) so users in single-PC setups can opt out. Document in `profiles.md`.
- **Worktree mode interaction:** In Step 5 with worktree mode, the new branch was already created from local `<base-branch>`. The drift check fires *after* this — pulling at this point means rebasing the worktree's branch onto the updated base. The "Stop and re-verify" option should ideally do this rebase automatically (or at minimum tell the user to run `git rebase origin/<base-branch>` inside the worktree before Step 7).

## Out of scope (defer to follow-up tasks if needed)

- Pulling/fetching the code branch in **Step 0c** (currently data-only). That would require deciding which branch to fetch when the user hasn't picked a task yet — non-trivial and orthogonal to the post-planning warning.
- Adding a similar check at the start of Step 9 (pre-merge) — could be a separate task, but Step 9 already has the merge step that will surface the conflict, so the value-add is smaller.
- Adding a structured `## Files Affected` section requirement to plan files — would make detection precise but is a larger doc/template change.

## Verification

- Manual test 1: with `origin/main` ahead by an unrelated commit, run `/aitask-pick` through to Step 7; expect a soft warning.
- Manual test 2: with `origin/main` ahead by a commit touching a file referenced in the plan, expect a strong warning listing the file.
- Manual test 3: with `origin/main` not ahead, expect no warning.
- Manual test 4: with no network (fetch fails), expect silent skip and proceed.

## References

- `.claude/skills/aitask-pick/SKILL.md` Step 0c
- `.claude/skills/task-workflow/SKILL.md` Steps 5, 6, 7, 9
- `.claude/skills/task-workflow/planning.md` Checkpoint section
- `.aitask-scripts/lib/task_utils.sh:177` (`task_sync` definition)
- `.aitask-scripts/aitask_pick_own.sh` (sync-mode entry point)
