---
Task: t528_add_contribution_review_mirrors.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

## Context

The `aitask-contribution-review` skill was added in commit ab3c60b5 (t355_6) but
wrapper/mirror files were never created for the alt-agent frontends (Codex CLI,
Gemini CLI, OpenCode). The skill's `user-invocable` flag is true (confirmed in
`.claude/skills/aitask-contribution-review/SKILL.md:4`), so users of those
frontends should be able to invoke `/aitask-contribution-review` too. This is
the same thin-delegator pattern used by `aitask-fold`, `aitask-explore`, and
`aitask-pr-import`.

The task is pure wrapper creation — no procedural logic is inlined anywhere.
All wrappers point at `.claude/skills/aitask-contribution-review/SKILL.md` as
the source of truth so future edits flow through automatically.

## Authoritative Description

From `.claude/skills/aitask-contribution-review/SKILL.md:3`:

> Analyze a contribution issue, find related issues, and import as grouped or single task.

Argument interface: optional `<issue_number>`. Without it, the skill lists open
contribution issues interactively.

## Files to Create (4 new files)

### 1. `.agents/skills/aitask-contribution-review/SKILL.md`

Copy the structure from `.agents/skills/aitask-fold/SKILL.md` (27 lines).

### 2. `.opencode/skills/aitask-contribution-review/SKILL.md`

Copy the structure from `.opencode/skills/aitask-fold/SKILL.md` (23 lines).

### 3. `.gemini/commands/aitask-contribution-review.toml`

Copy the structure from `.gemini/commands/aitask-fold.toml` (13 lines).

### 4. `.opencode/commands/aitask-contribution-review.md`

Copy the structure from `.opencode/commands/aitask-fold.md` (13 lines).

## Implementation Steps

1. Write the 4 files using `Write` (one call each).
2. Verify file count: `grep -l "aitask-contribution-review" .agents/skills/*/SKILL.md .opencode/skills/*/SKILL.md .gemini/commands/*.toml .opencode/commands/*.md` should hit exactly 4 files.
3. Stage and commit code changes:
   ```bash
   git add .agents/skills/aitask-contribution-review/SKILL.md \
           .opencode/skills/aitask-contribution-review/SKILL.md \
           .gemini/commands/aitask-contribution-review.toml \
           .opencode/commands/aitask-contribution-review.md
   git commit -m "chore: Add aitask-contribution-review wrappers for alt-agent frontends (t528)"
   ```
4. Proceed to Step 9 (post-implementation/archival) per task-workflow.

## Verification

- Each of the 4 new files must exist.
- The grep verification from step 2 must return exactly 4 files.
- No build/test run needed — pure doc/wrapper change.

## Reference Files (pattern sources)

- `.agents/skills/aitask-fold/SKILL.md` — `.agents/` mirror pattern
- `.opencode/skills/aitask-fold/SKILL.md` — `.opencode/skills/` mirror pattern
- `.gemini/commands/aitask-fold.toml` — Gemini command pattern
- `.opencode/commands/aitask-fold.md` — OpenCode command pattern
- `.claude/skills/aitask-contribution-review/SKILL.md` — authoritative description
