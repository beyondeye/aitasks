---
priority: medium
effort: medium
depends: [t319_2]
issue_type: documentation
status: Ready
labels: [opencode, codeagent, website]
created_at: 2026-03-06 01:18
updated_at: 2026-03-06 11:33
---

Update website documentation for OpenCode support alongside Codex CLI.

## Context

When Codex CLI support was added (t130_3), the website was updated to document multi-agent skill invocation. Now we need to add OpenCode to those same pages.

## Key Facts About OpenCode Invocation

- OpenCode uses `/skill-name` via its native `skill` tool (same syntax as Claude Code)
- OpenCode has native `ask` tool (no plan mode constraint like Codex)
- OpenCode wrappers live in `.opencode/skills/`
- Permission config lives in `opencode.json` at project root

## Files to Modify

### 1. `website/content/docs/skills/_index.md`
- Update multi-agent callout to include OpenCode
- Document that OpenCode uses `/skill-name` via its native `skill` tool
- Note that OpenCode has native `ask` (no plan mode constraint like Codex)

### 2. `website/content/_index.md`
- Update feature card to include OpenCode
- Add release note for OpenCode support

### 3. Check t130_3 plan for other pages
Read `aiplans/archived/p130/p130_3_codex_docs_update.md` to identify any other pages that were updated for Codex — apply same pattern for OpenCode.

## Reference

- `aiplans/archived/p130/p130_3_codex_docs_update.md` (Codex docs update plan — primary reference)
- `website/content/docs/skills/_index.md` (current skills page)
- `website/content/_index.md` (current home page)

## Verification

- Website builds without errors: `cd website && hugo build --gc --minify`
- OpenCode mentioned on skills page and home page
- All pages that mention Codex CLI also mention OpenCode where appropriate
