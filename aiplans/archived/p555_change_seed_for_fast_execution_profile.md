---
Task: t555_change_seed_for_fast_execution_profile.md
Base branch: main
plan_verified: []
---

# Task t555 — Change fast execution profile to stop after plan approval

## Context

The `fast` execution profile currently has `post_plan_action: start_implementation`, which means Claude Code jumps directly from plan approval into implementation. In practice, plan creation now produces very comprehensive plans that consume most of the LLM context window — so implementation typically starts with an almost-full context, which degrades quality.

Recent workflow changes already added a "stop after plan approval" escape hatch (the "Approve and stop here" checkpoint option) so users can manually commit the plan and re-pick the task in a fresh context. This task extends that mitigation to the `fast` profile by default, so fast-profile users get the same benefit without having to override the profile.

The task also asks to ensure the post-plan-approval question exposes an option to run the Task Abort Procedure while keeping the plan. That option already exists — selecting "Abort task" at the checkpoint routes to `task-abort.md`, which asks "keep or delete the plan file" as its first sub-question. **Confirmed with the user: no new checkpoint option is needed** — unlocking the existing checkpoint by changing `fast.yaml` is sufficient.

## Scope — files to change

### 1. `aitasks/metadata/profiles/fast.yaml` (live profile)

Current line 2 and line 11:
```yaml
description: Minimal prompts - skip confirmations, jump to implementation
...
post_plan_action: start_implementation
```

Change to:
```yaml
description: Minimal prompts - skip confirmations, stop after plan approval
...
post_plan_action: ask
```

Rationale: explicit `ask` is clearer than deleting the key (which defaults to asking per `profiles.md` schema). Description updated to reflect new behavior.

### 2. `seed/profiles/fast.yaml` (template for `ait setup` in fresh projects)

Same two edits as above (description + `post_plan_action`). The seed and live versions have drifted (seed is simpler), but the relevant lines match.

### 3. `website/content/docs/skills/aitask-pick/execution-profiles.md`

Three edits:

- **Line 15** — update the fast profile one-liner:
  ```
  - **fast** -- Skip confirmations, use userconfig email, stay on the current branch, stop after plan approval, and keep feedback questions enabled
  ```
- **Line 29** — the `post_plan_action` row description is generic; no change needed (it already explains what `start_implementation` does, which is still valid for custom profiles).
- **Line 50** — the example `worktree` profile uses `post_plan_action: start_implementation` as an illustration. Leave unchanged: this is a hypothetical example profile, not the shipped fast profile, and the docs page describes it as "Like fast but creates a worktree" — which was accurate of the pre-change fast. Since the user's stated motivation is about LLM-context exhaustion during planning, that concern applies to worktree profiles too, but this is a docs example, not a shipped profile, so it's out of scope. *Decision: leave line 50 alone.*

**Revised edit list for this file:** only line 15.

### Not changing

- **`.claude/skills/task-workflow/planning.md`** — checkpoint options stay as-is per user confirmation. The "Abort task" option already routes through `task-abort.md` which asks about keeping the plan.
- **`.claude/skills/task-workflow/task-abort.md`** — plan-keep question already exists (lines 7–18).
- **`aitasks/metadata/profiles/remote.yaml`** and **`seed/profiles/remote.yaml`** — the remote profile must remain autonomous (no interactive checkpoint). It explicitly sets `post_plan_action: start_implementation` and `abort_plan_action: keep` for the `aitask-pickrem` / `aitask-pickweb` flows, which is correct. Do NOT change.
- **`.claude/skills/aitask-pickrem/SKILL.md`**, **`.claude/skills/aitask-pickweb/SKILL.md`** — these remote skills are driven by the `remote` profile and their own profile-handling logic; unaffected.
- **`.aitask-scripts/settings/settings_app.py`** — Settings TUI renders generic key editors and doesn't hardcode "fast = start_implementation".
- **`website/static/imgs/aitasks_settings_execution_profiles_tab.svg`** — a screenshot asset. If it visually labels fast as "jump to implementation" it's now slightly stale, but regenerating screenshots is out of scope for this task. Note it in the Final Implementation Notes.
- **Mirror skill dirs** (`.gemini/`, `.agents/`, `.codex/`, `.opencode/`) — they don't ship fast.yaml. Per `CLAUDE.md`, Claude Code is the source of truth; no mirror changes needed.
- **Tests** — no tests assert fast-profile `post_plan_action` value.

## Implementation Steps

1. Edit `aitasks/metadata/profiles/fast.yaml` — update `description` (line 2) and `post_plan_action` (line 11).
2. Edit `seed/profiles/fast.yaml` — update `description` (line 2) and `post_plan_action` (line 8).
3. Edit `website/content/docs/skills/aitask-pick/execution-profiles.md` line 15 — append "stop after plan approval" to the fast profile bullet.
4. Hand off to Step 7 → Step 8 review/commit per task-workflow.

## Verification

**Behavioral check — no automated test exists, so this is manual:**

1. After the change, running `/aitask-pick` with the fast profile default should:
   - Select a task, claim it, enter planning.
   - Approve plan → **show the checkpoint question** (previously it auto-proceeded to implementation).
   - The checkpoint must show four options: Start implementation / Revise plan / Approve and stop here / Abort task.
   - Selecting "Abort task" must route to `task-abort.md` which asks "A plan file was created. What should happen to it?" with "Keep for future reference" / "Delete the plan file".

2. Re-reading `aitasks/metadata/profiles/fast.yaml` with `cat` should show `post_plan_action: ask` and the new description.

3. Optional sanity: `grep -rn "Minimal prompts - skip confirmations, jump" aitasks/ seed/` should return no matches after the change.

## Post-implementation (Step 9)

Per `task-workflow/SKILL.md` Step 9: commit code changes and plan file separately, then archive via `./.aitask-scripts/aitask_archive.sh 555`. No worktree cleanup (current branch). Issue field is not set on this task, so no issue update.

**Suggested follow-up task (per CLAUDE.md mirror rule):** none required — the mirror skill dirs do not ship fast.yaml, so no mirror updates are needed.

## Files modified

- `aitasks/metadata/profiles/fast.yaml` (2 lines)
- `seed/profiles/fast.yaml` (2 lines)
- `website/content/docs/skills/aitask-pick/execution-profiles.md` (1 line)

## Final Implementation Notes

- **Actual work done:** Applied the plan exactly. Changed `post_plan_action: start_implementation` → `post_plan_action: ask` and updated `description` in both `aitasks/metadata/profiles/fast.yaml` (live) and `seed/profiles/fast.yaml` (template). Updated the fast profile bullet on `website/content/docs/skills/aitask-pick/execution-profiles.md` line 15 to mention "stop after plan approval".
- **Deviations from plan:** None.
- **Issues encountered:** None.
- **Key decisions:**
  - Used explicit `post_plan_action: ask` instead of deleting the key. Both work (the schema in `profiles.md` says omission defaults to asking), but `ask` is clearer for readers scanning the profile file.
  - Left the example `worktree` profile on line 50 of `execution-profiles.md` unchanged — it's a hypothetical template, not the shipped fast profile, and the docs page presents it as a custom example where the author may have chosen `start_implementation` deliberately.
  - Did not touch `.claude/skills/task-workflow/planning.md` or `task-abort.md`. Confirmed with the user via AskUserQuestion during planning that the existing four checkpoint options are sufficient — `Abort task` already routes to `task-abort.md` which asks keep/delete for the plan file, satisfying the task's second requirement.
  - Did not touch `aitasks/metadata/profiles/remote.yaml` or the `aitask-pickrem` / `aitask-pickweb` skills — those remain autonomous by design and must keep `post_plan_action: start_implementation`.
- **Stale asset note:** `website/static/imgs/aitasks_settings_execution_profiles_tab.svg` (a Settings TUI screenshot) may show the old fast-profile description. Regenerating it is out of scope for this task; flagging for a future follow-up if someone refreshes docs screenshots.
- **Mirror dirs:** `.gemini/`, `.agents/`, `.codex/`, `.opencode/` do not ship `fast.yaml`, so no mirror task is needed per `CLAUDE.md`'s rule.
