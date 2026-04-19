---
Task: t594_6_concepts_commands_development_sweep.md
Parent Task: aitasks/t594_website_documentation_coherence.md
Parent Plan: aiplans/p594_website_documentation_coherence.md
Sibling Tasks: aitasks/t594/t594_{1,2,3,4,5}_*.md
Depends on: t594_2 (canonical wording)
Worktree: (none — work on current branch)
Branch: main
Base branch: main
---

# t594_6 — Concepts + Commands + Development coherence sweep

## Context

Bundled child covering three smaller sections (14 + 10 + 3 = 27 pages). All three drift the same way: missing flags, missing frontmatter fields, stale schemas. Per-page changes are small, so they are bundled. Depends on t594_2 for canonical wording.

## Scope

**In-bounds:**
- Add missing flags to command reference pages (from authoritative script sources).
- Add missing frontmatter fields to `development/task-format.md`.
- Tighten `commands/codeagent.md` by defining "agent string" once.
- Align `concepts/tasks.md` overview vs `development/task-format.md` schema.
- Verify concept pages against the relevant source.
- Add "Next:" footers within each section.

**Out-of-bounds:**
- Reorganizing section structure or weights.
- Splitting or merging pages.

## Concrete factual drift to fix

### A. `development/task-format.md` — missing `verifies` field

Lines 29-49 list ~13 frontmatter fields. Add:

- `verifies` — list of task IDs this task verifies (added with t583_2, commit `b17f8c54`; source: `.aitask-scripts/aitask_create.sh:25` `--verifies`).

Also cross-check the 13+ existing fields against `CLAUDE.md` §"Task File Format" and the create/update scripts — fix any other missing fields found.

### B. `commands/task-management.md` — missing `ait update` flags

Current page documents ~13 flags. Missing flags (source `.aitask-scripts/aitask_update.sh:52-82`):

- `--verifies`, `--add-verifies`, `--remove-verifies`
- `--file-ref`, `--remove-file-ref`
- `--pull-request`
- `--contributor`, `--contributor-email`
- `--folded-tasks`, `--folded-into`
- `--implemented-with`
- `--boardcol`, `--boardidx`

### C. `commands/task-management.md` — `ait create` missing `--verifies` flag

Source: `.aitask-scripts/aitask_create.sh:25`.

### D. `commands/codeagent.md` — tighten "agent string" repetition

Currently re-introduces "agent string" 4 times across ~280 lines. Define it once upfront (lines ~23-32 area), then reference that definition. Do NOT split the page.

Verify default model ("pick: claudecode/opus4_7_1m") against:
- `.aitask-scripts/aitask_codeagent.sh:27` (`DEFAULT_AGENT_STRING`).
- `aitasks/metadata/codeagent_config.json`.

### E. `concepts/tasks.md` ↔ `development/task-format.md`

Align overview sentences (done in part by t594_2). Add explicit cross-link: "See `development/task-format.md` for the full frontmatter schema."

### F. Per-concept page verification

For each of the 14 concept pages, identify the relevant source (script, SKILL.md, procedure file) and diff claims vs source. Priority pages:

- `concepts/locks.md` vs `.aitask-scripts/aitask_lock.sh`, `aitask_lock_diag.sh`.
- `concepts/agent-attribution.md` vs `.claude/skills/task-workflow/agent-attribution.md` and `.aitask-scripts/aitask_resolve_detected_agent.sh`.
- `concepts/execution-profiles.md` (if present) vs `.claude/skills/task-workflow/profiles.md` and shipped YAMLs.
- `concepts/git-branching-model.md` vs `./ait git` dispatcher and `aitask_sync.sh`.
- `concepts/task-lifecycle.md` vs the Status enum used across scripts.

### G. `development/review-guide-format.md`

Verify against actual files in `aireviewguides/`.

### H. "Next:" footers

Add within each section (concepts internal, commands internal, development internal).

## Authoritative sources

| Topic | Source |
|---|---|
| `ait create` flags | `.aitask-scripts/aitask_create.sh` |
| `ait update` flags | `.aitask-scripts/aitask_update.sh:52-82` |
| Task frontmatter schema | `CLAUDE.md` §"Task File Format" + create/update scripts |
| Review guide format | `aireviewguides/` directory |
| Default code-agent model | `.aitask-scripts/aitask_codeagent.sh:27`, `aitasks/metadata/codeagent_config.json` |
| Concept details | corresponding `.aitask-scripts/`, `.claude/skills/task-workflow/` files |

## Implementation plan

1. **`development/task-format.md` frontmatter update** — add `verifies` and any other missing fields found.
2. **`commands/task-management.md` flag additions** — for `ait update` and `ait create`.
3. **`commands/codeagent.md` tightening** — single "agent string" definition upfront.
4. **`concepts/tasks.md` cross-link + alignment.**
5. **Concept page verification pass** — priority pages first.
6. **`development/review-guide-format.md` verification** against `aireviewguides/`.
7. **"Next:" footers within each section.**
8. **Hugo build check.**

## Verification

- `diff <(./.aitask-scripts/aitask_update.sh --help 2>&1 | grep -oE '^\s*--[a-z-]+' | sort -u) <(grep -oE '\-\-[a-z-]+' website/content/docs/commands/task-management.md | sort -u)` — every script flag has a doc mention (or documented exclusion).
- `grep -i "verifies" website/content/docs/development/task-format.md` — at least one match.
- `grep -c "agent string" website/content/docs/commands/codeagent.md` — reduced from 4+ to 1 (definition) + follow-on references that don't re-define.
- `cd website && hugo build --gc --minify` succeeds.

## Step 9 reference

Archive via `./.aitask-scripts/aitask_archive.sh 594_6`.
