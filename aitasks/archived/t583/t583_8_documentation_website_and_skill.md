---
priority: medium
effort: medium
depends: [t583_1, t583_2, t583_3, t583_4, t583_5, t583_6, t583_7]
issue_type: documentation
status: Done
labels: [framework, skill, task_workflow, verification, docs]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-19 08:30
updated_at: 2026-04-21 16:28
completed_at: 2026-04-21 16:28
---

## Context

Eighth child of t583. Writes user-facing documentation for the manual-verification module and updates project-wide guidance in CLAUDE.md. Depends on all prior implementation children (t583_1 through t583_7) so the docs describe the real, shipping behavior.

Includes the **CLAUDE.md whitelisting-convention note** that the user flagged as a recurring-issue guardrail during plan review.

## Key Files to Modify

- `website/content/docs/workflows/manual-verification.md` — **new page**, main user-facing doc.
- `.claude/skills/aitask-pick/SKILL.md` — short "Manual-Verification Branch" note in Notes section.
- `.claude/skills/aitask-explore/SKILL.md` — cross-reference to the new integration step.
- `CLAUDE.md` — two edits:
  1. Add "Manual verification" subsection under Project-Specific Notes with pointer to website page.
  2. Add "Adding a New Helper Script" subsection (parallel to the existing "Adding a New Frontmatter Field" rule) documenting the 5 whitelist touchpoints.

## Reference Files for Patterns

- `website/content/docs/workflows/` — other workflow pages (if any exist) show Docsy formatting conventions; otherwise use `website/content/docs/` siblings.
- `CLAUDE.md` — "Adding a New Frontmatter Field" subsection as the template for the new "Adding a New Helper Script" subsection.

## Implementation Plan

### 1. Website page (`website/content/docs/workflows/manual-verification.md`)

Sections:
- **Overview** — what the module does (two flows: generation, running).
- **The checklist format** — markdown `## Verification Checklist` H2 with `- [ ]` / `- [x]` / `- [fail]` / `- [skip]` / `- [defer]` items; annotations after ` — `.
- **Generation flow** — screenshots/walkthroughs of the two prompt insertion points in `/aitask-pick` (planning phase) and `/aitask-explore` (create-task phase). Aggregate sibling (parent tasks) vs follow-up task (single tasks).
- **Running flow** — pick a manual-verification task; per-item Pass/Fail/Skip/Defer loop; what each option does.
- **Fail → follow-up bug** — what gets captured (commits, files, failing-item text); back-reference to origin's archived plan.
- **`verifies:` field** — what it is, how to set it via `ait update`, how it drives follow-up origin disambiguation.
- **Defer and carry-over** — deferred items don't archive; `--with-deferred-carryover` creates a new task with just the deferred items.
- **Example end-to-end** — walk through a short session.

Front-matter (Docsy conventions: `title`, `weight`, `description`).

### 2. Skill touch-ups

- `aitask-pick/SKILL.md` Notes: "Manual-verification tasks (`issue_type: manual_verification`) enter a dedicated workflow branch — see `.claude/skills/task-workflow/manual-verification.md`."
- `aitask-explore/SKILL.md`: in the create-task phase description, note the manual-verification prompt that runs before batch-create.

### 3. CLAUDE.md edits

**Edit A — Manual verification subsection (under "Project-Specific Notes"):**
```markdown
## Manual Verification

Tasks with `issue_type: manual_verification` run through a dedicated interactive
loop when picked: Pass/Fail/Skip/Defer per checklist item, with fail-triggered
follow-up bug task creation. See `website/content/docs/workflows/manual-verification.md`
and `.claude/skills/task-workflow/manual-verification.md`.
```

**Edit B — Adding a New Helper Script (parallel to existing "Adding a New Frontmatter Field" block):**
```markdown
### Adding a New Helper Script

Any new script under `.aitask-scripts/` that is invoked by a skill must be
whitelisted for every code agent's permission system — **both runtime configs
(this project) AND seed configs (new projects bootstrapped via `ait setup`)**.
Missing any touchpoint causes users of the corresponding agent to be prompted
on every invocation, which is a recurring friction source.

| Touchpoint | Entry shape |
|-----------|------------|
| `.claude/settings.local.json` | `"Bash(./.aitask-scripts/<name>.sh:*)"` in `permissions.allow` |
| `.gemini/policies/aitasks-whitelist.toml` | `[[rules]]` block with `commandPrefix = "./.aitask-scripts/<name>.sh"` |
| `seed/claude_settings.local.json` | mirror of `.claude/settings.local.json` entry |
| `seed/geminicli_policies/aitasks-whitelist.toml` | mirror of runtime gemini policy |
| `seed/opencode_config.seed.json` | `"./.aitask-scripts/<name>.sh *": "allow"` |

**Codex exception:** `.codex/config.toml` and `seed/codex_config.seed.toml` use
a prompt/forbidden-only permission model — no `allow` decision exists. Codex
does not need a whitelist entry; it prompts by default.

When splitting a plan that introduces one or more new helper scripts, surface
this 5-touchpoint checklist as an explicit deliverable per helper.
```

Per `feedback_doc_forward_only.md` guidance: describe current state only, no "previously…" framing.

## Verification Steps

- `cd website && ./serve.sh` (or `hugo build --gc --minify`) → new page renders without error at `/docs/workflows/manual-verification/`.
- Navigate to the page in a browser; confirm headings, code blocks, tables render.
- `grep -n "Manual Verification" CLAUDE.md` → new subsection present.
- `grep -n "Adding a New Helper Script" CLAUDE.md` → new subsection present.
- `grep -n "Manual-Verification" .claude/skills/aitask-pick/SKILL.md` → cross-reference present.

## Step 9 reminder

Commit: `documentation: Add manual-verification docs and whitelisting convention (t583_8)`.
