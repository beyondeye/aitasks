---
Task: t583_8_documentation_website_and_skill.md
Parent Task: aitasks/t583/t583_8_documentation_website_and_skill.md
Sibling Tasks: aitasks/t583/t583_9_*.md
Archived Sibling Plans: aiplans/archived/p583/p583_1_*.md .. p583_7_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-21 16:19
---

# Plan: t583_8 — Documentation + CLAUDE.md Whitelisting Convention (verified)

## Context

The manual-verification module (t583_1…t583_7) has shipped. User-facing docs are missing: there is no workflow page describing the two generation paths and the Pass/Fail/Skip/Defer running flow end-to-end, and CLAUDE.md has no pointer to it. Separately, the user flagged the 5-file whitelist touchpoint list as a recurring-issue guardrail that deserves its own CLAUDE.md subsection parallel to "Adding a New Frontmatter Field".

## Verify-path drift from the originally-scheduled plan

The scheduled plan predates the **t602** refactor. Codebase re-verification surfaced the following divergences:

1. **Explore-path cross-reference no longer applies.** `t602` moved the manual-verification follow-up prompt out of `.claude/skills/aitask-explore/SKILL.md` and out of the planning-Checkpoint "Start implementation" branch, into task-workflow **Step 8c** (driven by `.claude/skills/task-workflow/manual-verification-followup.md`). A grep of `aitask-explore/SKILL.md` for `manual`, `verifies`, or `verification` returns zero matches. → **Drop the `aitask-explore/SKILL.md` edit entirely.** The Step 8c follow-up automatically covers explore-created tasks when the user later runs `/aitask-pick`, so no explore-specific documentation is needed.

2. **Current generation surfaces are two, not three:**
   - **Aggregate-sibling path** — `planning.md` lines 170–197, fires when a parent task is split into ≥2 children; user is offered to add a sibling manual-verification task covering all or a subset of the children.
   - **Step 8c single-task follow-up** — SKILL.md Step 8c → `manual-verification-followup.md`, fires after the "Commit changes" branch of Step 8; assembles candidate checklist bullets from `## Verification Steps`, plan `## Verification`, plan "Deviations/Issues" notes, and diff scans of interactive-surface files.

3. **All other plan assumptions verified:**
   - `aitask_create_manual_verification.sh` CLI: `--parent` XOR `--related`, `--name`, `--verifies`, `--items`; structured output `MANUAL_VERIFICATION_CREATED:<new_id>:<path>`.
   - `aitask_verification_followup.sh` CLI: `--from`, `--item`, `[--origin]`; structured output `FOLLOWUP_CREATED:<id>:<path>` / `ORIGIN_AMBIGUOUS:<csv>` / `ERROR:<msg>`.
   - `aitask_verification_parse.sh` subcommands: `parse`, `set <idx> {pass,fail,skip,defer,pending} [--note]`, `summary`, `terminal_only`, `seed --items`.
   - `aitask_archive.sh --with-deferred-carryover` is live; gate blocks archival when non-terminal items remain.
   - `manual_verification` registered at `aitasks/metadata/task_types.txt:9`.
   - `verifies:` and `manual_verification_followup_mode` are already partially documented in `website/content/docs/development/task-format.md`, `commands/task-management.md`, `tuis/settings/reference.md`, and `skills/aitask-pick/execution-profiles.md` — the new workflow page should link to those rather than duplicate them.

## Files to create / modify

**New:**
- `website/content/docs/workflows/manual-verification.md` — workflow guide.

**Modify:**
- `.claude/skills/aitask-pick/SKILL.md` — short Notes entry pointing at the procedure file.
- `CLAUDE.md` — two new subsections (A: Manual Verification pointer under Project-Specific Notes; B: Adding a New Helper Script under Architecture, parallel to "Adding a New Frontmatter Field").

**Dropped vs original task file:**
- `.claude/skills/aitask-explore/SKILL.md` — no edit needed (see drift note 1).

## 1. Website page — `website/content/docs/workflows/manual-verification.md`

Docsy front-matter (mirror existing "Review & Quality" pages — `qa-testing.md` weight 75, `code-review.md` weight 70):

```yaml
---
title: "Manual Verification Workflow"
linkTitle: "Manual Verification"
weight: 80
description: "Human-checked verification items (TUI flows, live agent launches, artifact inspection) as first-class gated tasks"
depth: [intermediate]
---
```

Sections (in order):

### Overview
Lead paragraph: explains that some behavior — TUI flows, tmux-driven agents, multi-screen navigation, on-disk artifact inspection — cannot be covered by `/aitask-qa` because it is not script-testable. `issue_type: manual_verification` marks a task as a human-checklist runner; `/aitask-pick` dispatches it through a dedicated Pass/Fail/Skip/Defer loop instead of the normal plan+implement flow.

Cross-link out to [`/aitask-qa`](../../skills/aitask-qa/) for the automated-test side; state the division of labor (automated = unit/integration, manual = TUI/live-agent/artifact).

### The checklist format
One H2 `## Verification Checklist` section in the task body, one bullet per item:

- `- [ ] text` — pending
- `- [x] text — PASS YYYY-MM-DD HH:MM` — passed
- `- [fail] text — FAIL YYYY-MM-DD HH:MM follow-up t<new_id>` — failed (follow-up bug task linked)
- `- [skip] text — SKIP YYYY-MM-DD HH:MM <reason>` — skipped with reason
- `- [defer] text — DEFER YYYY-MM-DD HH:MM` — deferred

Item text may carry trailing annotations after ` — ` (em dash + spaces); the parser strips and rewrites this suffix on each `set`. Link to the parser CLI help output snippet (`aitask_verification_parse.sh --help`).

### Where checklists come from — two generation paths

**Aggregate-sibling (parent → children planning):**
When `/aitask-pick` on a parent task splits it into ≥2 children during planning, after the child plans are committed the skill offers to add a **sibling** manual-verification task that verifies some or all of the children. Choose **"Yes, aggregate sibling"** (covers every child) or **"Yes, but let me choose"** (multi-select subset). The seeder extracts each selected child's plan `## Verification` bullets, prefixes each with `[t<parent>_<child>] ` for at-a-glance origin, and seeds the new sibling. Skipped when only one child is created (a single-task follow-up covers that case).

**Post-implementation follow-up (Step 8c):**
After the "Commit changes" branch of `/aitask-pick`'s review step, Step 8c offers a standalone manual-verification follow-up — a new task that will be picked after the current one archives. Skipped for child tasks (aggregate covers them), for tasks that are themselves `manual_verification`, and when an aggregate sibling was already created during the same session. Candidate bullets are discovered from four sources (de-duplicated): the task's `## Verification Steps` H2, the plan's `## Verification` H2, the plan's Final Implementation Notes "Deviations"/"Issues" fields, and a diff scan of the task's commits that flags interactive-surface files (TUI code, `textual` imports, `fzf`/`gum` scripts). If all four sources are empty, a single `TODO: define verification for t<id>` stub is written — the user fills it in when they later pick the follow-up.

Both paths shell out to the same seeder: `./.aitask-scripts/aitask_create_manual_verification.sh` — `--parent <N>` (aggregate) XOR `--related <id>` (follow-up).

Profile controls:
- `manual_verification_followup_mode: "never"` in the active profile skips Step 8c entirely. See [Execution Profiles](../../skills/aitask-pick/execution-profiles/).

### Running a manual-verification task
When `/aitask-pick` picks a task whose `issue_type` is `manual_verification`, Step 3 (Check 3) dispatches to the **Manual Verification Procedure** instead of Steps 6–8. Steps 4 (ownership lock) and 5 (worktree) still run before dispatch.

For each pending or deferred item, the procedure renders the item text and prompts:

| Choice | Effect |
|---|---|
| **Pass** | Marks the item `pass` with timestamp. |
| **Fail** | Runs `aitask_verification_followup.sh` — creates a pre-populated bug task with commit hashes, touched files, verbatim failing text, and `depends: [<origin>]`. Item annotated with `follow-up t<new_id>`. |
| **Skip (with reason)** | Prompts for free-text reason; marks the item `skip <reason>`. |
| **Defer** | Marks the item `defer` — the task will not archive cleanly while any item is deferred. |
| **Other (free text)** | Treated as a normal chat message — answer questions or handle requests, then re-prompt the *same* item. The "abort/pause/stop" intent (judged from the free text, not a keyword list) ends the loop without mutating state; the task stays `Implementing` and the lock is held so only the original picker can resume. |

### Fail → follow-up bug task
On Fail, `aitask_verification_followup.sh` does five things:

1. Resolves the origin task — user-supplied `--origin`, or the single entry in `verifies:`, or `ORIGIN_AMBIGUOUS:<csv>` (exit 2) forcing the user to disambiguate. Empty `verifies:` falls back to the `--from` task itself.
2. Collects commits via `git log --oneline --all --grep="(t<origin>)"`.
3. Collects files touched by those commits via `git show --name-only`.
4. Creates a `bug`-type task with `depends: [<origin>]`, `labels: verification,bug`, and a description containing the verbatim failing-item text, commit list, touched-file list, and a **Source** block (MV task path, origin ID, origin archived-plan path).
5. Best-effort appends a back-reference bullet under the origin's archived plan `## Final Implementation Notes` section.

### The `verifies:` field
Optional list of task IDs that a manual-verification task validates — populated by the aggregate-sibling seeder. Used by the Fail → follow-up helper to attribute failures to the right origin when the checklist spans multiple feature tasks. A single entry auto-resolves; multiple entries trigger `ORIGIN_AMBIGUOUS` so the picker chooses at verification time.

Edit via `ait update`:
```bash
./.aitask-scripts/aitask_update.sh --batch <id> --verifies 571_4,571_5
./.aitask-scripts/aitask_update.sh --batch <id> --add-verifies 571_6
./.aitask-scripts/aitask_update.sh --batch <id> --remove-verifies 571_4
```

See also the field reference in [Task Format](../../development/task-format/#frontmatter-fields).

### Defer and carry-over
Deferred items block clean archival — `aitask_archive.sh <id>` errors out while any item is non-terminal. Two resolutions:

- **Archive with carry-over** — run `aitask_archive.sh --with-deferred-carryover <id>`. The script archives the current task and creates a new `manual_verification` task seeded with just the deferred items (original `verifies:` copied forward). The procedure offers this at the post-loop checkpoint when `DEFER > 0`.
- **Stop without archiving** — leave the task `Implementing` with the lock held. The user can re-pick it later with `/aitask-pick <id>` (same PC, same owner) to continue the remaining items.

### Example end-to-end
Walk through a short hypothetical session:

1. `/aitask-pick 571` on a parent that splits into three children (`571_4`, `571_5`, `571_6`). At the aggregate prompt, answer "Yes, aggregate sibling covering all children". A new `t571_7_manual_verification_structured_brainstorming.md` is created with `verifies: [571_4, 571_5, 571_6]` and a pre-seeded checklist.
2. Children are implemented and archived normally.
3. `/aitask-pick 571_7`. Step 3 Check 3 routes to the Manual Verification Procedure. Items render one at a time.
4. Item 1 passes → Pass. Item 2 fails → Fail → `ORIGIN_AMBIGUOUS:t571_4,t571_5,t571_6` → pick `571_5` → `FOLLOWUP_CREATED:612:aitasks/t612_fix_failed_verification_t571_7_item2.md`. The failing item is now `[fail] ... follow-up t612`. Item 3 defers — waiting on downstream work.
5. Post-loop: `DEFER=1` → "Archive with carry-over" → primary archives as Done, a new `t613_manual_verification_structured_brainstorming_deferred.md` is created with only item 3.

### Tips
- Seed aggregate siblings from child plans' `## Verification` bullets so the checklist reflects the actual shipped behavior, not an a-priori wishlist.
- Use "Other" (free-text) inside the loop for conversational adjustments — "please also check <x>", "explain the failing behavior" — without leaving the picker.
- Set `manual_verification_followup_mode: never` in a profile when you are batching small commits and don't want the Step 8c prompt on every archive.
- Child tasks don't get Step 8c prompts — add an aggregate sibling during parent planning instead.

## 2. `.claude/skills/aitask-pick/SKILL.md` edit

In the **Notes** section at the end of the file (after line 224), append one bullet keeping the existing list style:

```markdown
- Manual-verification tasks (`issue_type: manual_verification`) dispatch to a dedicated checklist loop instead of the plan+implement flow — see `.claude/skills/task-workflow/manual-verification.md`. Post-implementation follow-up creation is handled by Step 8c (`manual-verification-followup.md`).
```

## 3. `CLAUDE.md` edits

### Edit A — "Manual Verification" subsection
Insert at the end of the "Project-Specific Notes" section (currently line 186–188), as a new bullet after the `diffviewer` bullet:

```markdown
- **Manual verification.** Tasks with `issue_type: manual_verification` dispatch through a dedicated Pass/Fail/Skip/Defer loop in `/aitask-pick` (Step 3 Check 3 → `.claude/skills/task-workflow/manual-verification.md`). Aggregate-sibling tasks are offered during parent-task planning when ≥2 children are created; single-task follow-ups are offered at Step 8c after "Commit changes". See `website/content/docs/workflows/manual-verification.md` for the end-to-end workflow.
```

Rationale for list-bullet (vs new H2/H3 heading): the existing "Project-Specific Notes" section uses a bullet list; mirror that style.

### Edit B — "Adding a New Helper Script" subsection
Insert after the "Adding a New Frontmatter Field" block (line 80) and before "### Script Modes" (line 82), as a new H3 parallel to the existing one:

```markdown
### Adding a New Helper Script

Any new script under `.aitask-scripts/` invoked by a skill must be whitelisted for every code agent's permission system — **both runtime configs (this project) AND seed configs (new projects bootstrapped via `ait setup`)**. Missing any touchpoint causes users of the corresponding agent to be prompted on every invocation, which is a recurring friction source.

| Touchpoint | Entry shape |
|-----------|------------|
| `.claude/settings.local.json` | `"Bash(./.aitask-scripts/<name>.sh:*)"` in `permissions.allow` |
| `.gemini/policies/aitasks-whitelist.toml` | `[[rules]]` block with `commandPrefix = "./.aitask-scripts/<name>.sh"` |
| `seed/claude_settings.local.json` | mirror of `.claude/settings.local.json` entry |
| `seed/geminicli_policies/aitasks-whitelist.toml` | mirror of runtime Gemini policy |
| `seed/opencode_config.seed.json` | `"./.aitask-scripts/<name>.sh *": "allow"` |

**Codex exception:** `.codex/config.toml` and `seed/codex_config.seed.toml` use a prompt/forbidden-only permission model — no `allow` decision exists. Codex does not need a whitelist entry; it prompts by default.

When splitting a plan that introduces one or more new helper scripts, surface this 5-touchpoint checklist as an explicit deliverable per helper.
```

Both edits state current behavior positively per the `Documentation Writing` rule — no "previously…" framing.

## Reference patterns

- `website/content/docs/workflows/qa-testing.md` — Docsy frontmatter + H2 structure + profile-key call-outs. Closest analogue for weight (75 vs new 80), tier table style, "When to Run" / "Tips" trailing sections.
- `website/content/docs/workflows/follow-up-tasks.md` — example-driven walkthrough style.
- `website/content/docs/development/task-format.md:51` — existing `verifies:` field entry; cross-link rather than duplicate.
- `website/content/docs/skills/aitask-pick/execution-profiles.md:39` — existing `manual_verification_followup_mode` entry; cross-link rather than duplicate.
- `.claude/skills/task-workflow/manual-verification.md` — source of truth for the Pass/Fail/Skip/Defer semantics documented on the workflow page.
- `.claude/skills/task-workflow/manual-verification-followup.md` — source of truth for the Step 8c candidate-discovery logic.
- `.claude/skills/task-workflow/planning.md` (lines 170–197) — source of truth for the aggregate-sibling flow.
- `CLAUDE.md` "Adding a New Frontmatter Field" (lines 73–80) — structural template for Edit B.

## Verification

- `cd website && hugo build --gc --minify` — new page builds without error; no broken relrefs.
- Browser render of `/docs/workflows/manual-verification/` — headings, tables, code blocks render; the Pass/Fail/Skip/Defer table is readable.
- `grep -n "Manual verification" CLAUDE.md` — new bullet present.
- `grep -n "Adding a New Helper Script" CLAUDE.md` — new H3 present.
- `grep -n "Manual-verification tasks" .claude/skills/aitask-pick/SKILL.md` — new Notes bullet present.
- Visual sanity: open the rendered workflow page in a browser, click the `task-format.md#frontmatter-fields` and `execution-profiles.md` cross-links — both resolve.

## Out of scope / follow-ups

- Gemini / Codex / OpenCode mirror edits for `aitask-pick` SKILL.md and the new CLAUDE.md subsections — per `CLAUDE.md` "WORKING ON SKILLS / CUSTOM COMMANDS", Claude Code is the source of truth; mirror tasks should be filed separately after this task archives.
- `t583_9` (meta-dogfood aggregate verification) — will exercise this page end-to-end.

## Step 9 reminder

Commit message: `documentation: Add manual-verification docs and whitelisting convention (t583_8)`. Plan file commits use `ait:` prefix. Standard post-implementation flow per `.claude/skills/task-workflow/SKILL.md` Step 9.

## Final Implementation Notes

_To be filled in during implementation._
