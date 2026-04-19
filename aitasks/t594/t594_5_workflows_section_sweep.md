---
priority: medium
effort: high
depends: []
issue_type: documentation
status: Ready
labels: []
created_at: 2026-04-19 17:11
updated_at: 2026-04-19 17:11
---

Child of t594. Sweep the 21 pages under `website/content/docs/workflows/`. Depends on t594_2 for canonical wording.

## Context

Parent plan: `aiplans/p594_website_documentation_coherence.md`. Workflows pages often duplicate content with Skill pages (e.g., `workflows/qa-testing.md` ↔ `skills/aitask-qa.md`). Per user's conservative dedup stance, keep both — but add cross-links and canonicalize wording.

## Key Files to Modify

- All 21 pages under `website/content/docs/workflows/`.
- `website/content/docs/workflows/_index.md` — category intro (no weight changes).
- `website/content/docs/workflows/tmux-ide.md`, `parallel-development.md`, `capture-ideas.md` — canonicalize "how to launch `ait ide`" wording.

## Reference Files for Patterns (Authoritative Sources)

- `.aitask-scripts/aitask_ide.sh` (if present) or the relevant tmux-orchestration scripts — truth for `ait ide` command behavior.
- `.claude/skills/<name>/SKILL.md` for skills whose workflows overlap (aitask-qa, aitask-review, aitask-pr-import, aitask-contribute, etc.).

## Implementation Plan

1. **Identify workflow↔skill page pairs** that duplicate content:
   - `workflows/qa-testing.md` ↔ `skills/aitask-qa.md`
   - `workflows/code-review.md` ↔ `skills/aitask-review.md`
   - `workflows/pr-import.md` ↔ `skills/aitask-pr-import.md`
   - `workflows/contribution.md` ↔ `skills/aitask-contribute.md`
   - `workflows/revert-changes.md` ↔ `skills/aitask-revert.md`
   - `workflows/explain.md` ↔ `skills/aitask-explain.md`
   For each pair, add bi-directional links; unify step names.
2. **Category intro for `workflows/_index.md`:** group the 21 workflows into Daily / Decomposition / Patterns / Integrations / Advanced — without changing weight values.
3. **Canonicalize `ait ide` launch sequence** across `tmux-ide.md`, `parallel-development.md`, `capture-ideas.md`. Keep self-contained wording but use the same command and flags.
4. **"Next:" footers** within the suggested reading path.
5. **Source verification:** verify command sequences (e.g., `ait ide` flow) against the actual shell scripts.

## Verification Steps

- `grep -rn "ait ide" website/content/docs/workflows/` — all instances show the same canonical command.
- Open the 5 top workflow pages by weight; the flow from one to the next feels coherent.
- `cd website && hugo build --gc --minify` succeeds.
