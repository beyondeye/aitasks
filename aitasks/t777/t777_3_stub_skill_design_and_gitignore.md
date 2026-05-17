---
priority: high
effort: medium
depends: [t777_2]
issue_type: feature
status: Implementing
labels: [aitask_pick]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-17 11:57
updated_at: 2026-05-17 15:43
---

## Context

Depends on t777_2. Designs and documents the canonical stub SKILL.md pattern that lives at the no-suffix slash-command path (`<agent>/skills/<skill>/SKILL.md`). The stub is what allows `/aitask-pick` (typed inside a live agent session) to dispatch to the user's active profile variant.

The stub is per-agent (4 files per skill, because slash-dispatch syntax may differ). Each stub:
1. Runs bash: `ait skill resolve-profile <skill>` → captures `<active_profile>`
2. Runs bash: `ait skill render <skill> --profile <active_profile> --agent <this_agent>`
3. Invokes `/<skill>-<active_profile> <forwarded args>` (slash-dispatch from within a skill)

**Critical risk validated here:** does each of the 4 agents allow a SKILL.md to programmatically invoke another slash command? If any agent doesn't, design a clear fallback (print shell hint and abort).

Also adds the `.gitignore` entries for per-profile rendered directories.

## Key Files to Modify

- 4 reference stub authoring files (one per agent — see notes about the per-skill-and-per-agent stub authoring in t777_6+):
  - This child produces TEMPLATE patterns documented in `.claude/skills/task-workflow/stub-skill-pattern.md` (new) — a reference document that t777_6 (and t777_8..15) follow when writing per-skill stubs.
- Root `.gitignore` — add per-profile dir globs:
  ```
  # Per-profile rendered skill variants (on-demand, not committed)
  .claude/skills/*-*/
  .agents/skills/*-*/
  .gemini/skills/*-*/
  .opencode/skills/*-*/
  ```
- A throwaway test stub for each of the 4 agents to validate slash-dispatch (delete after validation, or commit as `.claude/skills/_dispatch_test/SKILL.md` if useful)

## Reference Files for Patterns

- `.claude/skills/task-workflow/execution-profile-selection.md` — pattern for a procedure file that other skills reference
- `.claude/skills/aitask-pick/SKILL.md` Step 3 ("Hand Off to Shared Workflow") — current pattern for one skill instructing the agent to "Read and follow another file"

## Implementation Plan

### 1. Validate slash-dispatch per agent
- Author a throwaway stub `_dispatch_test/SKILL.md` for each agent that says: "Run `ls /tmp` then invoke `/echo hello`".
- Manually invoke each agent's slash command and observe whether the agent runs the bash AND invokes the second slash command.
- For each of (claude, codex, gemini, opencode): record YES/NO with notes.
- If any agent CAN'T dispatch:
  - Document the limitation in `.claude/skills/task-workflow/stub-skill-pattern.md`
  - Design the fallback: the stub prints "Profile dispatch not supported in <agent>. Run `ait skillrun <skill> --profile <name>` from a shell" and aborts.

### 2. Author the canonical stub pattern document
Create `.claude/skills/task-workflow/stub-skill-pattern.md`:
- Section: "What is a stub SKILL.md"
- Section: "Canonical bash + slash-dispatch body" (paste the actual SKILL.md text, customizable per skill)
- Section: "Per-agent variations" (any syntax differences)
- Section: "Fallback for agents that can't slash-dispatch"
- Subsequent children (t777_6 and t777_8..15) reference this document and reproduce the pattern.

### 3. .gitignore updates
Add the globs noted above. Verify they don't accidentally match authoring directories with hyphenated names (notably `task-workflow/`). Two mitigations:
- (preferred) Use a more specific glob that requires a known profile suffix, e.g. `.claude/skills/*-fast/`, `.claude/skills/*-remote/`, `.claude/skills/*-<future-profile>/`. But this requires updating .gitignore each time a profile is added — not great.
- (alternative) Use a sentinel file: each per-profile directory contains a `.generated` marker file. Use `.gitignore` to exclude directories containing `.generated`. But .gitignore doesn't support content-based exclusion.
- (preferred) Rename `task-workflow/` to `task_workflow/` (underscore) so the hyphen glob doesn't match. This is a small one-off rename across all 4 agent trees; touches all references in SKILL.md and procedure files.
- **Decision:** prefer the rename. Surface the trade-off and execute the rename.

## Verification Steps

1. The 4-agent slash-dispatch matrix is documented (clear pass/fail per agent).
2. `.claude/skills/task-workflow/stub-skill-pattern.md` exists and contains the canonical bash + dispatch body.
3. `.gitignore` matches profile-suffixed directories but does NOT match authoring directories (verify with `git check-ignore -v .claude/skills/aitask-pick-fast/SKILL.md` and `git check-ignore -v .claude/skills/aitask-pick/SKILL.md`).
4. If the rename was executed: all 4 agent trees have `task_workflow/` (or whatever new name); no references to `task-workflow/` remain in skills or procedures.
