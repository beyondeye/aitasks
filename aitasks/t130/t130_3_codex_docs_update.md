---
priority: low
effort: low
depends: [t130_2]
issue_type: documentation
status: Implementing
labels: [aitasks, codexcli, website]
assigned_to: dario-e@beyond-eye.com
implemented_with: codex/gpt-5
created_at: 2026-03-04 10:46
updated_at: 2026-03-05 22:34
---

## Context

This is child task 3 of t130 (Codex CLI support). It updates the website documentation to mention multi-agent skill invocation — specifically that Codex CLI users invoke skills with `$skill-name` instead of `/skill-name`.

Depends on t130_1 (skill wrappers should exist before documenting them).

## Key Files to Modify

### `website/content/docs/skills/_index.md`

The main skills overview page currently says:
> "aitasks provides Claude Code skills that automate the full task lifecycle. These skills are invoked as slash commands within Claude Code."

Update to acknowledge multi-agent support. Add a callout/note after the intro paragraph (after line 8):

```markdown
> **Multi-agent support:** These skills are also available in Codex CLI via wrapper
> skills in `.agents/skills/`. Invoke with `$aitask-pick`, `$aitask-create`, etc.
> Run `ait setup` to install Codex CLI skill wrappers when Codex is detected.
```

Also consider updating the page title from "Claude Code Skills" to something more inclusive, or add a note that these are primarily Claude Code skills with Codex wrappers available.

### Other pages to review (optional, if time permits)

These pages reference `/skill-name` syntax and could benefit from a brief mention of Codex equivalents:
- `website/content/docs/getting-started.md` (lines 54-75)
- `website/content/_index.md` (lines 25-26, home page)
- Individual skill pages in `website/content/docs/skills/`

For these, a minimal change is sufficient — e.g., adding "(or `$skill-name` in Codex CLI)" after the first mention of a slash command.

## Reference Files

- `website/content/docs/skills/_index.md` — Main file to update
- `.agents/skills/` — Verify skill names match the documentation
- `website/content/docs/getting-started.md` — Optional secondary update

## Implementation Steps

1. Edit `website/content/docs/skills/_index.md` — add multi-agent callout
2. Optionally update `getting-started.md` and home page with brief mentions
3. Verify the website builds: `cd website && hugo build --gc --minify` (if Hugo is available)

## Important Note (from t311)

When documenting Codex CLI skills, mention that interactive skills require
**plan mode** to function correctly. The `request_user_input` function
(Codex equivalent of AskUserQuestion) only works in plan mode. Also note
that post-implementation finalization (commit, archive) must be explicitly
triggered — Codex does not reliably surface finalization prompts
automatically. See `.agents/skills/codex_interactive_prereqs.md` for the
full prerequisites.

## Verification

1. Updated pages render correctly in Hugo
2. All skill names in documentation match actual `.agents/skills/` directory names
3. No broken links introduced
