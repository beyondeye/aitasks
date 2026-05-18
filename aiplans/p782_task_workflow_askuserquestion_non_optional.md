---
Task: t782_task_workflow_askuserquestion_non_optional.md
Base branch: main
plan_verified: []
---

## Context

During t777_22 implementation a system-reminder told Claude to "work without stopping for clarifying questions" — Claude over-applied this and silently skipped the Step 8c manual-verification followup prompt AND the Step 9b satisfaction-feedback prompt. Those are NOT clarifying questions; they are workflow contractual checkpoints. Skipping them either drops data (verified-model scores, follow-up tasks) or lets unreviewed work land in git.

Step 8 already carries an explicit `⚠️ NON-SKIPPABLE` banner that names execution profiles and auto mode as invalid bypasses. Steps 8b / 8c / 9 (merge-approval) / 9b do not, leaving them vulnerable to over-broad interpretation of system-injected directives. This task adds parallel banners at the remaining 4 sites and codifies the convention in CLAUDE.md.

Per [[feedback_system_injected_directives_scope]] memory and the task description's explicit decision, the banners and convention are the deliverables — no factoring to a shared partial, since (a) each site has site-specific valid-opt-out keys, and (b) include-mechanism for plain `.md` files in the skills tree is not the dep-walker (which is .j2-only).

## Files to modify

1. `.claude/skills/task-workflow/SKILL.md` — Step 9 merge-approval prompt (around line 410, the "Proceed with merge of code changes to main branch?" AskUserQuestion).
2. `.claude/skills/task-workflow/upstream-followup.md` — top of `## Procedure` body, before `### 1. Resolve…`.
3. `.claude/skills/task-workflow/manual-verification-followup.md` — top of `## Procedure` body, before `### 1. Profile check`.
4. `.claude/skills/task-workflow/satisfaction-feedback.md` — top of `**Procedure:**` body, before `## Step 0 — Record usage`.
5. `CLAUDE.md` — new bullet under "Skill / Workflow Authoring Conventions" section.

## Banner template

Each banner mirrors the existing Step 8 banner (SKILL.md lines 277–296) for tone and structure, but enumerates **site-specific valid opt-outs** (which differ per site — see step-by-step below). All four banners share these three "DO NOT cover" lines:

- Execution profiles (unless a key in this SKILL.md/procedure is explicitly named as covering this prompt).
- Auto mode / `work without stopping` system-injected directives.
- Generic user instructions like `be brief` or `don't ask`.

And each enumerates the valid-skip set with the site-specific profile key (or `currently: none`).

## Step-by-step implementation

### 1. `.claude/skills/task-workflow/SKILL.md` Step 9 — merge approval

Locate the line:

```
**IMPORTANT:** Use `AskUserQuestion` to ask: "Proceed with merge of code changes to main branch?" with options "Yes, proceed with merge" / "No, not yet". Do NOT proceed until the user approves.
```

Insert this banner **immediately before** that line:

```
**⚠️ NON-SKIPPABLE — Auto mode and execution profiles do NOT bypass this merge approval.**

The AskUserQuestion below is a workflow gate, not a routine confirmation. The
following do NOT cover this prompt:
- Execution profiles (no profile key currently bypasses Step 9 merge approval).
- Auto mode / 'work without stopping' system-injected directives.
- Generic user instructions to 'be brief' or 'don't ask'.

The only valid skips are profile keys explicitly named in this SKILL.md as
covering Step 9 merge approval (currently: none) or the user explicitly
authorizing the merge in chat before the prompt fires.
```

### 2. `.claude/skills/task-workflow/upstream-followup.md` Step 8b

Insert this banner **immediately after** the `## Procedure` line (and before `### 1. Resolve the plan file…`):

```
**⚠️ NON-SKIPPABLE — Auto mode and execution profiles do NOT bypass the Step 8b prompt.**

The AskUserQuestion in step 2 below is the workflow gate where an upstream
defect either becomes its own follow-up task or stays buried in this task's
archived plan. The following do NOT cover this prompt:
- Execution profiles (no profile key currently bypasses Step 8b).
- Auto mode / 'work without stopping' system-injected directives.
- Generic user instructions to 'be brief' or 'don't ask'.

The only valid skips are profile keys explicitly named in this procedure as
covering Step 8b (currently: none) or the user explicitly typing a decision
(e.g. "skip the upstream followup" or "create the followup task") in chat
before the prompt fires.
```

### 3. `.claude/skills/task-workflow/manual-verification-followup.md` Step 8c

Insert this banner **immediately after** the `## Procedure` line (and before `### 1. Profile check`):

```
**⚠️ NON-SKIPPABLE — Auto mode and 'work without stopping' directives do NOT bypass the Step 8c prompt.**

The AskUserQuestion in step 4 below is the workflow gate that decides whether
a standalone manual-verification follow-up task is created. The following do
NOT cover this prompt:
- Auto mode / 'work without stopping' system-injected directives.
- Generic user instructions to 'be brief' or 'don't ask'.
- Profile keys other than the one named below.

The only valid skips are:
- The profile key `manual_verification_followup_mode: never` (handled by
  step 1 below before the prompt is reached), or
- The user explicitly typing a decision in chat before the prompt fires.
```

### 4. `.claude/skills/task-workflow/satisfaction-feedback.md` Step 9b

Insert this banner **immediately after** the `**Procedure:**` line (and before `## Step 0 — Record usage (unconditional)`):

```
**⚠️ NON-SKIPPABLE — Auto mode and 'work without stopping' directives do NOT bypass the Step 9b satisfaction prompt.**

The AskUserQuestion in Step 1 substep 3 below is the only data path that
updates verified-model scores from interactive workflows. Skipping it silently
drops the user's rating for the run. The following do NOT cover this prompt:
- Auto mode / 'work without stopping' system-injected directives.
- Generic user instructions to 'be brief' or 'don't ask'.
- Profile keys other than the one named below.

The only valid skips are:
- The profile key `enableFeedbackQuestions: false` (handled by Step 1
  substep 1 below before the prompt is reached), or
- The user explicitly typing a rating in chat before the prompt fires.
```

(Step 0 has no AskUserQuestion of its own — the usage bump is unconditional — so the banner placed at the top of the procedure correctly scopes to Step 1's prompt and is harmless above Step 0.)

### 5. `CLAUDE.md` — Skill / Workflow Authoring Conventions

Append a new bullet to the "Skill / Workflow Authoring Conventions" section (under the existing bullets), capturing the convention:

```
- **Mark workflow-defined AskUserQuestion prompts as NON-SKIPPABLE when they record data, close a gate, or surface a decision the user must own.** When you add an AskUserQuestion to a SKILL.md or referenced procedure file (`task-workflow/*.md`) whose purpose is (a) recording load-bearing data (e.g. verified-model scores), (b) gating workflow progression (e.g. merge approval, plan approval), or (c) surfacing a user-owned decision (e.g. create vs. skip a follow-up task), prefix it with a `⚠️ NON-SKIPPABLE` banner that mirrors Step 8's wording in `task-workflow/SKILL.md`. The banner MUST explicitly enumerate what does NOT cover the prompt — execution profiles (unless a specific key is named), auto mode / 'work without stopping' system-injected directives, and generic user instructions to 'be brief' or 'don't ask'. The banner MUST also enumerate the only valid opt-outs: site-specific profile keys (or `currently: none`) and explicit user pre-decision in chat.

  **Why:** During t777_22, a Claude Code harness injected a "work without stopping" directive that was meant to suppress clarifying questions. The agent over-applied it and silently skipped the Step 8c manual-verification follow-up AND the Step 9b satisfaction-feedback prompt — losing a follow-up task and a verified-model rating. The explicit banner at Step 8 was correctly NOT over-applied; its absence at the other gates was the gap.

  **How to apply:** When adding a new AskUserQuestion to a workflow procedure, classify it as either (i) a clarifying question (no banner needed; existing auto-mode/profile shortcuts may legitimately bypass it) or (ii) a workflow gate / data-recording prompt (banner required). When in doubt, default to (ii). Existing banners live at `task-workflow/SKILL.md` Step 8, Step 9 merge-approval; and at the top of `task-workflow/upstream-followup.md`, `manual-verification-followup.md`, `satisfaction-feedback.md`.
```

## Verification

1. Grep for the new banner phrase across the skills tree:
   ```bash
   grep -rn "NON-SKIPPABLE" .claude/skills/task-workflow/
   ```
   Confirm 5 hits total: existing Step 8 banner in SKILL.md, new Step 9 banner in SKILL.md, and one each in `upstream-followup.md`, `manual-verification-followup.md`, `satisfaction-feedback.md`.

2. Re-read Step 8's existing banner (`task-workflow/SKILL.md` lines 277–296) and compare wording / structure to the four new banners for consistency.

3. Run `./ait skill verify`. With no .j2 templates yet under task-workflow, this is a no-op exit-0 path — it exercises the verify entrypoint without touching the new content. Confirm clean exit.

4. Grep CLAUDE.md to confirm the new bullet landed cleanly:
   ```bash
   grep -n "NON-SKIPPABLE" CLAUDE.md
   ```
   Should show one hit (the new bullet's reference) plus any existing references (none expected).

## Out of scope

- Factoring the banner into a shared `_non_skippable_banner.md` partial. Reasons: (a) site-specific valid-opt-out keys differ per site, so factoring would require a parameterized include; (b) plain `.md` files in the skills tree are not rendered by the t777_22 dep-walker (that path is .j2 only); (c) the task description explicitly marks this as "Optional".
- Backporting the banner to other agent trees (`.agents/`, `.gemini/`, `.opencode/`). Per CLAUDE.md "WORKING ON SKILLS / CUSTOM COMMANDS" section, Claude Code is the source of truth; suggest sibling aitasks for the other agents at the end of implementation if the user wants to mirror.

## Step 9 reference

After implementation, follow task-workflow Step 9 (Post-Implementation) — no separate branch was created (`create_worktree: false` profile), so the workflow goes: review → commit → 8b (no upstream defect expected — this is a pure-docs change) → 8c (manual-verification follow-up offer) → 9 archival → 9b feedback.

## Final Implementation Notes
- **Actual work done:** Added 4 `⚠️ NON-SKIPPABLE` banner blocks (Step 9 merge approval in `task-workflow/SKILL.md`; top of `upstream-followup.md` / `manual-verification-followup.md` / `satisfaction-feedback.md`) plus a new convention bullet in CLAUDE.md's "Skill / Workflow Authoring Conventions" section. Each banner enumerates the three "DO NOT cover" categories (execution profiles, auto-mode/work-without-stopping directives, generic 'be brief' instructions) and the site-specific valid opt-outs (`currently: none` for Step 9 / Step 8b; `manual_verification_followup_mode: never` for Step 8c; `enableFeedbackQuestions: false` for Step 9b).
- **Deviations from plan:** None. Plan executed as approved.
- **Issues encountered:** None.
- **Key decisions:** Skipped the optional shared-partial factoring (already documented in "Out of scope") — each site has distinct valid-opt-out keys, and plain `.md` files in the skills tree are read directly by the agent (no t777_22 dep-walker on this path).
- **Upstream defects identified:** None
- **Cross-agent porting:** `.agents/`, `.gemini/`, `.opencode/` mirrors of `task-workflow/` and CLAUDE.md (where present) should receive the same banners. Per CLAUDE.md "WORKING ON SKILLS / CUSTOM COMMANDS" the user should create sibling aitasks for those agents if mirroring is wanted. Listed for the user as a follow-up at task close, not a Step 8b upstream-defect bullet.
