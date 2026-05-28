---
priority: medium
effort: medium
depends: [t835_5]
issue_type: documentation
status: Ready
labels: [codeagent]
created_at: 2026-05-28 12:19
updated_at: 2026-05-28 12:19
---

## Context

Use the t835 agy implementation as empirical ground truth to audit,
reorganize, and surface `aidocs/adding_a_new_codeagent.md` so the
next code-agent addition has an accurate, well-ordered reference.

The doc today has 23 sections (1339 lines) ordered roughly as
sections were written, NOT in the order an implementer should
follow. The agy implementation produces a known-good ordering:
identity → rendering → setup/install/release → user-facing docs →
cleanup. This child reshapes the doc to match, deduplicates content,
and adds website discoverability.

Runs **last** of all t835 children (depends on t835_1-5) so the
audit reflects what was actually done, not what was originally
planned.

## Key Files to Modify

- `aidocs/adding_a_new_codeagent.md` — main audit + reorganize.
- `website/content/docs/development/adding-a-new-code-agent.md` —
  NEW thin wrapper page linking to the aidocs file.
- `website/content/docs/development/_index.md` (or equivalent
  sidebar index) — link to the new page.
- `CLAUDE.md` — verify the existing `Read aidocs/adding_a_new_codeagent.md`
  pointer is still accurate.
- `aidocs/agent_runtime_guards_audit.md` — if t835_2 introduced new
  `{% if agent == "agy" %}` Jinja gates, surface them here.

## Reference Files for Patterns

- `aiplans/archived/p835/p835_1_*..p835_5_*.md` — actual
  implementation paths taken; primary source of ground truth for
  the audit.
- `aiplans/archived/p812/p812_1_*..p812_5_*.md` — paired
  removal-side plans for context.
- `aidocs/planning_conventions.md` — DRY rule for 3+ duplicated
  content patterns.
- Existing website pages in `website/content/docs/development/` —
  Hugo wrapper conventions, frontmatter format.

## Implementation Plan

1. **Audit pass.** Walk each of `adding_a_new_codeagent.md`'s 23
   sections against the corresponding edits in t835_1-5 (use
   `git log --oneline main..HEAD -- .aitask-scripts/ seed/ install.sh website/`).
   For each section, mark accurate / stale / missing / dead.
   Document findings inline in the plan file's Final Implementation
   Notes.

2. **Reorganize into logical implementation order.** Target
   structure matches the t835 child split:
   - Phase A: Agent identity (current §§ 2-2c, 3, 4, 5, 6, 7, 8, 10)
   - Phase B: Skill rendering (current §§ 1-1g, 9, 12-16)
   - Phase C: Setup, install, release (current §§ 17-22)
   - Phase D: User-facing documentation (current § 23)
   - Phase E: Cleanup & verification (NEW — distill t835_5)
   - Phase F: Tests checklist (current § 11)

   Add an "Implementation order" diagram at the top mapping old
   section numbers → new section numbers so external references in
   archived plan files still resolve.

3. **Deduplicate content.** Known candidates:
   - Helper-doc copy-loop tuple (§§ 17e, 18d, 19b, 21) → keep
     canonical in §21, cross-ref elsewhere.
   - `SUPPORTED_AGENTS` lockstep (§ 2b) → verify no other section
     re-enumerates them.
   - `× N agents` message string (§ 8b) → check § 17/18 for repeats.
   - Any pattern duplicated 3+ times per
     `aidocs/planning_conventions.md`.

4. **Surface in website docs.** Add a thin wrapper page at
   `website/content/docs/development/adding-a-new-code-agent.md`
   that briefly explains the doc's purpose and audience and links
   to the aidocs file. Do NOT duplicate aidocs content. Add a
   sidebar link from the development index.

5. **Verify CLAUDE.md pointer.** Confirm
   `**Read `aidocs/adding_a_new_codeagent.md`**` directive is still
   correctly placed and matches the (possibly renumbered) sections
   it references.

6. **Verify agent_runtime_guards_audit.md.** If t835_2 added new
   `{% if agent == "agy" %}` gates, ensure they are recorded.

## Verification Steps

- Walk the reorganized doc top-to-bottom and mentally execute each
  section against `git log --oneline main..HEAD -- .aitask-scripts/ seed/ install.sh .github/workflows/release.yml website/`.
  Every change in those paths should map cleanly to one section.
- `cd website && ./serve.sh` — the new
  `development/adding-a-new-code-agent` page renders and links
  resolve.
- Fresh-context test: read the reorganized aidocs top-to-bottom as
  if planning a hypothetical new agent addition. Note any remaining
  clarity gaps; fix or log as follow-up.
