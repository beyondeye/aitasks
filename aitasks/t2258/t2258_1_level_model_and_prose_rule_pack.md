---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Implementing
labels: [documentation, web_site, doc_quality]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 2258
created_at: 2026-11-09 23:08
updated_at: 2026-11-10 09:00
---

## Context

Child 1 of t2258 (reader levels and readable prose for the website docs). Read
the parent task `aitasks/t2258_doc_audience_levels_and_readable_prose.md` (the
evidence, prior-art research and the **Integration map** tables) and the
approved parent plan `aiplans/p2258_doc_audience_levels_and_readable_prose.md`
("Design decisions" 1–4 bind this child).

This child writes the **rules**: the reader-level model and the newcomer prose
rule pack, in the configured doc guide `aitasks/metadata/doc_update_guide.md`.
That guide is the only place the rules live. The `docs_updated` gate
(`.claude/skills/aitask-gate-docs-updated/SKILL.md`) already reads it and is
forbidden from reading `aidocs/framework/` convention docs, so rules kept only in
`aidocs/framework/documentation_conventions.md` never reach the agent writing
docs. Child 2 builds the review skill that *reads* these sections, so the
interface below is a contract.

## Decisions already made (do not reopen)

- **Two axes.** `depth` = what the reader already knows (sets vocabulary). Page
  type (Diátaxis: tutorial / how-to / reference / explanation) = what the reader
  needs (sets shape). Type is derived from section and page role, not a new
  field: `concepts/` = explanation; `workflows/` = how-to; `commands/`,
  `skills/` = reference; TUI `_index` / `how-to` / `reference` = overview /
  how-to / reference; `getting-started.md` = tutorial; `overview.md` =
  explanation.
- **Keep the values** `main-concept` / `intermediate` / `advanced`
  (`website/check_links.py:91` uses `depth/advanced/` as its control URL).
  `depth` becomes **required on every leaf page** (child 7 adds the check).
- **Anti-pattern 2 resolution:** a `main-concept` page defines every term it
  uses; `intermediate` / `advanced` pages may assume the knowledge their
  contract names and must link to where it is taught.
- **Interface contract for child 2's skill:** the guide has a section headed
  exactly `## Reader levels` that declares (1) the level field (`depth`), (2)
  the beginner level value (`main-concept`), (3) one persona sentence per level
  (e.g. main-concept: "You know git and a terminal and have never heard of
  aitasks."). Write these three as an easy-to-find list at the top of that
  section. The skill relies only on that heading and those three declarations.

## Key files to modify

- `aitasks/metadata/doc_update_guide.md` — add, after "Doc landscape":
  1. `## Reader levels` — interface declarations, then one contract per depth
     value: who the reader is, what they already know, what the page must
     answer, what is **forbidden** (e.g. at `main-concept`: exit codes, internal
     file paths, status-line vocabularies, edge-case/outcome tables, field
     enumerations not needed for the idea).
  2. `## Page types` — the two-question compass (does the reader *do* or
     *know*; are they *studying* or *working*) in our own words, the
     section→type table above, and which page types assume competence.
  3. `## How a subject spans levels` — separate pages per type (the TUI
     `_index`/`how-to`/`reference` split is the model); a concept page states
     the idea and links to the workflow/reference that owns the detail;
     "every fact must survive" = a fact cut from a beginner page is **moved** to
     its owning page, never deleted.
  4. `## Concept pages` — carried over from
     `aidocs/framework/documentation_conventions.md` § "Concept pages"
     (sections in order, no `###` deep-dives under "What it is", model pages,
     internals belong on the owning page, complementary-to-workflow rule).
  5. `## Prose rules` — a short project-owned list, primary first:
     RULE-01-style tacit-knowledge rule (define terms; purpose before
     mechanics; one-sentence map before a long section; declare the page's level
     before drafting), concrete language (RULE-03; don't copy table values into
     prose), plain words before terms (keep real technical terms), one term per
     thing; then the avoid list: not-X-but-Y / staged contrasts, one-line
     closers, staged run-ups, arguing with no one, forced triads, repeated
     openings, dashes as default connector, inflated significance, shallow -ing
     riders, avoiding is/are/has, decorative bold, heading repeated in the first
     sentence, writing about the document instead of its subject, closing
     summaries. Each avoid entry gets a before/after pair; take "before" text
     from our pages (`workflows/freeze-and-restore-agents.md`: "Parking is a
     signal to *you*… Freezing is a decision about the *agent*", "the obvious one
     is usually not the cheaper one", "What you trade a code agent for is that
     viewer"; `concepts/locks.md` opening; `tuis/minimonitor/how-to.md`
     mechanism). Write "after" text yourself; it must keep every fact.
  6. `## Sources and credits` — credit Diátaxis (Daniele Procida,
     diataxis.fr); yzhao062/agent-style rules are CC BY 4.0 (attribution
     required — name it and link it); blader/humanizer (MIT) and the plain-
     language skills inform the avoid list (ideas adapted, no text copied); the
     keithpatton Diátaxis skill is CC-BY-SA-4.0 — **never copy its text**, write
     our own; anthropics `doc-coauthoring` reader testing is a method only.
- `aidocs/framework/documentation_conventions.md` — replace § "Concept pages"
  with a pointer to the guide's sections (single source of truth; keep the
  other sections).
- `CLAUDE.md` — the "Read documentation_conventions.md when writing user-facing
  doc prose" pointer also names the guide's reader-level model.
- `website/README.md` — one short paragraph: `depth` values have contracts in
  the guide; `depth` is required on leaf pages.

## Reference files

- Model concept pages: `website/content/docs/concepts/{tasks,plans,folded-tasks,execution-profiles}.md`.
- The guide's existing "Writing conventions" section (keep it; the new sections
  sit beside it).

## Constraints

- Write the new sections to the standard they set: plain words, short, a fresh
  reader should understand them. Run the prose rules on your own text.
- The gate guide is read on every docs_updated run — keep the additions
  concise (target ≤ ~150 added lines).
- No website pages are edited in this child (the audits are children 3–7).

## Verification

- `grep -n '^## Reader levels' aitasks/metadata/doc_update_guide.md` finds the
  heading once; the three interface declarations are present.
- `aidocs/framework/documentation_conventions.md` no longer contains the
  concept-page rule text, only the pointer.
- Ask a fresh sub-agent (sees only the new guide sections) to classify three
  pages (`concepts/locks.md`, `concepts/tasks.md`,
  `tuis/minimonitor/how-to.md`) and list their violations; it should flag the
  locks outcome table and the minimonitor mechanism. Record the answer in the
  plan's Final Implementation Notes.
