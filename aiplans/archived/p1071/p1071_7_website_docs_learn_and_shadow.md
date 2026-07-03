---
Task: t1071_7_website_docs_learn_and_shadow.md
Parent Task: aitasks/t1071_shadow_error_diagnosis_and_learn_skill_command.md
Archived Sibling Plans: aiplans/archived/p1071/p1071_1_*.md ... p1071_6_*.md
Base branch: main
---

# Plan - Website docs for learn skill and shadow capabilities

## Summary

Add current-state website documentation for the landed t1071 capabilities:
`/aitask-learn-skill`, shadow error diagnosis, and shadow learner spawning. Use
the current `.claude/skills/` source as truth, not archived plans. No runtime code
or skill behavior changes.

## Key Changes

- Add `website/content/docs/skills/aitask-learn-skill.md`.
  - Document usage for pane id, local file, URL, repo file, and repo directory
    sources.
  - Explain read-only pane capture, incremental deepening, multi-part selection,
    generalization Q&A, static `SKILL.md` generation, optional wrappers,
    verification, and optional commit.
  - Use skill-reference page frontmatter consistent with nearby advanced skills.
- Update `website/content/docs/skills/_index.md`.
  - Add a `Skill Authoring` section/table containing `/aitask-learn-skill`.
  - Keep agent invocation wording consistent: slash-style agents use
    `/aitask-learn-skill`; Codex wrappers use `$aitask-learn-skill`.
- Update `website/content/docs/workflows/shadow-agent.md`.
  - Add an on-request "Diagnose skill/helper errors" capability: tool-call errors,
    tracebacks, stderr, retry loops; emits concern blocks only when genuine issues
    are found; user chooses concerns; can offer seeded `/aitask-explore` fix-tasks.
  - Add an on-request "Learn a skill from this workflow" capability: shadow
    confirms, spawns a dedicated learner in a new `agent-learn*` tmux window, and
    stays advisory/read-only.
  - Update concern-forwarding prose so it covers both plan review concerns and
    error-diagnosis concerns.
  - State clearly that learner spawning and error diagnosis are on-request only,
    not proactive offers.
- Update `website/content/docs/workflows/_index.md`.
  - Refresh the Shadow Agent bullet to mention diagnosing failures and learning
    reusable skills from followed-agent workflows.
  - Do not add a new workflow page.

## Public Interfaces

- New docs route: `/docs/skills/aitask-learn-skill/`.
- Updated docs route: `/docs/workflows/shadow-agent/`.
- No command, schema, script, or skill API changes.

## Verification

- Run `cd website && hugo build --gc --minify`.
- Check links resolve for:
  - skill overview -> `/aitask-learn-skill`
  - shadow workflow -> `/aitask-learn-skill`, minimonitor, `/aitask-explore`
  - workflows index -> shadow workflow
- Grep the new/updated docs to confirm they do not describe old plan history or
  claim proactive error diagnosis.

## Risk

### Code-health risk: low

Documentation-only changes in existing website content. No runtime code path or
schema changes.

### Goal-achievement risk: low

Main risk is doc drift. Mitigation: read the current `.claude/skills` sources and
state current behavior, including that shadow error diagnosis and learner spawning
are on-request only.

## Final Implementation Notes

- **Actual work done:** Added `website/content/docs/skills/aitask-learn-skill.md`
  documenting source resolution, read-only pane capture, multi-part selection,
  generalization Q&A, generated static skill shape, optional wrappers, optional
  commit, and shadow integration. Updated `website/content/docs/skills/_index.md`
  with a Skill Authoring section linking the new page. Updated
  `website/content/docs/workflows/shadow-agent.md` to cover on-request
  skill/helper error diagnosis, on-request learner spawning, and concern
  forwarding for both plan and error concerns. Updated
  `website/content/docs/workflows/_index.md` to refresh the Shadow Agent entry.
- **Deviations from plan:** None. No new workflow page was added, so no additional
  workflow index entry was needed beyond the existing Shadow Agent bullet.
- **Issues encountered:** `hugo build --gc --minify` passed and printed two
  existing deprecation warnings from Hugo/Docsy template APIs:
  `.Language.LanguageDirection` and `.Site.AllPages`.
- **Key decisions:** Kept docs current-state-only and described current
  `.claude/skills` behavior, including that error diagnosis and learner spawning
  are explicit user requests rather than proactive shadow offers.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:** This is documentation-only and introduces no shared
  implementation patterns for later t1071 children.
