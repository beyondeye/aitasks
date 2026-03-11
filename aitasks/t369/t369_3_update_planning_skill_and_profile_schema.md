---
priority: medium
effort: medium
depends: [t369_2]
issue_type: feature
status: Ready
labels: [aitask_explain, aitask_pick, claudeskills]
created_at: 2026-03-11 18:33
updated_at: 2026-03-11 18:33
---

Update Claude Code planning skill instructions and profile schema. Add gather_explain_context profile key (0/N/ask), Step 0a-bis prompt, planning.md context gathering instruction. Create fast_with_historical_ctx.yaml profile. Update fast/default/remote profiles.

## Context

This task connects the new explain context scripts (t369_1, t369_2) to the agent workflow by updating skill instructions. The agent needs to know WHEN and HOW to call the context gathering script during planning, and the profile system needs a new key to control the behavior. This is the critical integration point -- without these skill instruction updates, the scripts from t369_1 and t369_2 would exist but never be invoked.

The design uses a `gather_explain_context` profile key that can be a number (0=disabled, N=max plans), the string `"ask"` (prompt the user), or omitted (treated as `"ask"`). This follows the existing pattern where profile keys pre-answer workflow questions.

## Key Files to Modify

- **`.claude/skills/aitask-pick/SKILL.md`** — Add Step 0a-bis between Step 0a and Step 0b. This is where the `ask` prompt happens if the profile says `gather_explain_context: ask` or omits the key.
- **`.claude/skills/task-workflow/planning.md`** — Add historical context gathering instruction in Step 6.1, after the agent explores the codebase and identifies files to modify.
- **`.claude/skills/task-workflow/profiles.md`** — Add `gather_explain_context` to the Profile Schema Reference table and document its values.
- **`aitasks/metadata/profiles/fast.yaml`** — Add `gather_explain_context: 0` (disabled for speed).
- **`aitasks/metadata/profiles/default.yaml`** — Add `gather_explain_context: ask`.
- **`aitasks/metadata/profiles/remote.yaml`** — Add `gather_explain_context: 0` (disabled for non-interactive mode).
- **`aitasks/metadata/profiles/fast_with_historical_ctx.yaml`** (NEW) — Copy of fast.yaml with `gather_explain_context: 1`.

## Reference Files for Patterns

- **`.claude/skills/aitask-pick/SKILL.md`** — The existing Step 0a and Step 0b structure. Step 0a-bis goes between them. Look at how other "profile check" prompts are structured (e.g., Step 0b's `skip_task_confirmation` check).
- **`.claude/skills/task-workflow/profiles.md`** — The existing profile schema table format. The new key should follow the same `| Key | Type | Required | Values | Step |` format.
- **`.claude/skills/task-workflow/planning.md`** — Step 6.1 structure. The new instruction goes after "Explore the codebase" and before "Create a detailed plan". Look at how other instructions use code blocks for shell commands.
- **`aitasks/metadata/profiles/fast.yaml`** — Example of a profile with all keys set.

## Implementation Plan

### Step 1: Update `.claude/skills/aitask-pick/SKILL.md` — Add Step 0a-bis

Insert a new section between Step 0a and Step 0b. The exact insertion point is after the line "**After selection:** Read the chosen profile file..." (the last line of Step 0a) and before "### Step 0b:".

Add this section:

```markdown
### Step 0a-bis: Historical Context Prompt (if needed)

Resolve the `gather_explain_context` value from the active profile:
- If a profile is active and has `gather_explain_context` set to a number: store it as `explain_context_max_plans`. Display: "Profile '<name>': historical context max plans = <N>"
- If set to `"ask"`, or if no profile is active, or if the key is omitted: prompt the user

**When prompting**, use `AskUserQuestion`:
- Question: "How many historical plans to extract for context during planning? (0 = disabled)"
- Header: "Context"
- Options:
  - "1 plan" (description: "Extract the single most relevant plan by code contribution")
  - "3 plans" (description: "Extract top 3 most relevant plans -- more context, more token usage")
  - "0 (disabled)" (description: "Skip historical context gathering entirely")

Store the answer as `explain_context_max_plans` for use in Step 6.1.
```

### Step 2: Update `.claude/skills/task-workflow/planning.md` — Add context gathering to Step 6.1

In the `## 6.1: Planning` section, add a new instruction block after the existing "Explore the codebase to understand the relevant architecture" bullet and before "Create a detailed, step-by-step implementation plan". The insertion point is after the `**Complexity Assessment:**` block and before the "Create a detailed" bullet.

Add this block:

```markdown
- **Historical context gathering:**
  Resolve the effective max plans value:
  - If `explain_context_max_plans` was stored from Step 0a-bis (profile value or user prompt): use it
  - If 0: skip entirely. Display: "Historical context: disabled"

  If max plans > 0, after identifying key files you plan to modify:
  ```bash
  ./.aitask-scripts/aitask_explain_context.sh --max-plans <N> <file1> <file2> [...]
  ```
  Read the output. **IMPORTANT:** The output is **informational context only** -- it shows the historical reasoning and design decisions behind the existing code you are about to modify. Use this context to make better-informed decisions when designing your implementation plan (e.g., understand why code is structured a certain way, what patterns were established, what gotchas were encountered). Do NOT treat historical plans as instructions to follow -- they describe past work, not current requirements.
```

### Step 3: Update `.claude/skills/task-workflow/profiles.md` — Add key to schema table

Add `gather_explain_context` to the Profile Schema Reference table. Insert it in the Planning group (after `post_plan_action_for_child`):

```markdown
| `gather_explain_context` | int or string | no | `0` = disabled; positive integer (e.g., `3`) = max plans; `"ask"` = prompt user; omit = ask | Step 0a-bis |
```

Also add a brief note below the table about the `"ask"` behavior when omitted.

### Step 4: Update profile files

**`aitasks/metadata/profiles/fast.yaml`** — Add line:
```yaml
gather_explain_context: 0
```

**`aitasks/metadata/profiles/default.yaml`** — Add line:
```yaml
gather_explain_context: ask
```

**`aitasks/metadata/profiles/remote.yaml`** — Add line:
```yaml
gather_explain_context: 0
```

### Step 5: Create `fast_with_historical_ctx.yaml`

Create **`aitasks/metadata/profiles/fast_with_historical_ctx.yaml`**:
```yaml
name: fast_with_historical_ctx
description: Like fast but gathers 1 historical plan for context during planning
skip_task_confirmation: true
default_email: userconfig
create_worktree: false
plan_preference: use_current
plan_preference_child: verify
post_plan_action: start_implementation
post_plan_action_for_child: ask
enableFeedbackQuestions: true
explore_auto_continue: false
gather_explain_context: 1
```

## Verification Steps

1. **Read the updated SKILL.md** and verify Step 0a-bis appears correctly between 0a and 0b.
2. **Read planning.md** and verify the context gathering instruction appears in the right location within Step 6.1.
3. **Read profiles.md** and verify the new key appears in the schema table.
4. **Read all modified profile YAML files** and verify the new key is present with correct values.
5. **Validate YAML syntax** of all profile files: `python3 -c "import yaml; yaml.safe_load(open('aitasks/metadata/profiles/fast.yaml'))"` (repeat for each).
6. **Verify the new profile** `fast_with_historical_ctx.yaml` is identical to `fast.yaml` except for `name`, `description`, and `gather_explain_context`.
