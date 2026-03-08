---
priority: medium
effort: low
depends: [t131_3]
issue_type: documentation
status: Done
labels: [geminicli]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-07 23:21
updated_at: 2026-03-08 15:19
completed_at: 2026-03-08 15:19
---

Update website documentation to include Gemini CLI as a supported agent.

## Context

The Hugo/Docsy website documents all aitasks features. The installation page (`website/content/docs/installation/_index.md`) lists "Optional: Codex CLI support" and "Optional: OpenCode support" sections. A matching "Optional: Gemini CLI support" section needs to be added. Other pages that list supported agents should also be updated.

Depends on t131_3 (setup/install must be implemented first so docs match reality).

## Key Files to Modify

- `website/content/docs/installation/_index.md` — Add "Optional: Gemini CLI support" section (after OpenCode section at line 79)
- `website/content/docs/overview.md` — Update agent listing if present
- `website/content/about/_index.md` — Update agent listing if present

## Files Already Covering Gemini CLI (no changes needed)

- `website/content/docs/commands/codeagent.md` — Already lists `geminicli` as supported agent
- `website/content/docs/tuis/settings/` — Already supports all 4 agents

## Implementation Plan

### Step 1: Update installation page

Add after the "Optional: OpenCode support" section:

```markdown
**Optional: Gemini CLI support** (when `ait setup` detects Gemini CLI):

- `.gemini/skills/` — Gemini CLI skill wrappers
- `.gemini/commands/` — Gemini CLI command wrappers
- `GEMINI.md` — aitasks instructions for Gemini CLI
```

### Step 2: Review and update other pages

Check `overview.md` and `about/_index.md` for any agent listings that need Gemini CLI added. Add it where Codex/OpenCode are already listed.

## Verification Steps

```bash
cd website && hugo build --gc --minify
```
