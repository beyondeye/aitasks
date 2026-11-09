---
Task: t2258_1_level_model_and_prose_rule_pack.md
Parent Task: aitasks/t2258_doc_audience_levels_and_readable_prose.md
Sibling Tasks: aitasks/t2258/t2258_2_*.md, aitasks/t2258/t2258_3_*.md, aitasks/t2258/t2258_4_*.md, aitasks/t2258/t2258_5_*.md, aitasks/t2258/t2258_6_*.md, aitasks/t2258/t2258_7_*.md, aitasks/t2258/t2258_8_*.md
Archived Sibling Plans: aiplans/archived/p2258/p2258_*_*.md
Base branch: main
Output branch: main
---

# t2258_1 — Level model and prose rule pack (in the configured doc guide)

## Context

The rules half of t2258. The `docs_updated` gate reads only the configured guide
(`aitasks/metadata/doc_update_guide.md`), so the level model and prose rules must
live there. Child 2's `aitask-doc-review` skill reads them through a fixed
interface (`## Reader levels` + three declarations). Binding decisions: parent
plan `aiplans/p2258_doc_audience_levels_and_readable_prose.md` § Design
decisions 1–2.

## Steps

1. **Read inputs.** `aitasks/metadata/doc_update_guide.md` (90 lines),
   `aidocs/framework/documentation_conventions.md` § "Concept pages", the
   parent task's Integration map tables, model pages
   `website/content/docs/concepts/{tasks,plans,folded-tasks,execution-profiles}.md`,
   and the prose samples named in the task description.
2. **Draft `## Reader levels`** (after "Doc landscape"). Open with the interface
   list:
   - `Level field: depth`
   - `Beginner level: main-concept`
   - `Personas:` one sentence each for `main-concept`, `intermediate`,
     `advanced` (e.g. main-concept: knows git and a terminal, has never heard of
     aitasks; intermediate: has run a task through pick → archive and knows
     the board; advanced: maintains a project setup, edits profiles/gates, reads
     framework internals).
   Then one contract per level: reader, already knows, page must answer,
   forbidden content. State that `depth` is required on every leaf page.
3. **Draft `## Page types`.** The two-question compass in our own words; the
   section → type table; which types assume competence and how depth resolves
   the "how-to must not teach" conflict (main-concept defines every term;
   intermediate/advanced assume the contract's knowledge and link to where it
   is taught).
4. **Draft `## How a subject spans levels`.** Separate pages per type (TUI split
   as the model); concept page → links to the workflow/reference owner; the
   "every fact survives" rule (moved, never deleted); when layered sections in
   one page are acceptable (short pages only).
5. **Move `## Concept pages`** from `documentation_conventions.md` into the guide
   (text adapted to sit under the level model), and replace the aidocs section
   with a two-line pointer.
6. **Draft `## Prose rules`.** Primary rules first (tacit knowledge, concrete
   language, plain words before terms, one term per thing), then the avoid list,
   each with a before/after pair from our pages. "After" text keeps every fact.
7. **Draft `## Sources and credits`.** Diátaxis credit; agent-style CC BY 4.0
   attribution with link; humanizer (MIT) and plain-language skills as idea
   sources; note that the CC-BY-SA keithpatton skill text was not copied;
   doc-coauthoring reader testing as method.
8. **Pointers.** CLAUDE.md doc-prose pointer names the guide's reader-level
   model; `website/README.md` gets a short `depth` paragraph.
9. **Self-check** the new sections against their own prose rules; keep additions
   ≤ ~150 lines.

## Verification

- `grep -c '^## Reader levels' aitasks/metadata/doc_update_guide.md` → `1`, and
  the three interface lines are present.
- The concept-page rule text is gone from `documentation_conventions.md` (only a
  pointer remains).
- Fresh sub-agent given only the new guide sections classifies
  `concepts/locks.md`, `concepts/tasks.md`, `tuis/minimonitor/how-to.md` and
  flags the locks outcome table and the minimonitor mechanism; record its answer
  in Final Implementation Notes.
- No `website/content/` page edited (so `check_links.py` is not required; run it
  anyway if `website/README.md` changed links).

## Post-implementation

Step 9 of the task workflow (review, commit `documentation: … (t2258_1)`,
archival).
