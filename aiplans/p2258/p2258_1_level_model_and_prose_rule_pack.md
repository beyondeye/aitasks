---
Task: t2258_1_level_model_and_prose_rule_pack.md
Parent Task: aitasks/t2258_doc_audience_levels_and_readable_prose.md
Sibling Tasks: aitasks/t2258/t2258_2_*.md, aitasks/t2258/t2258_3_*.md, aitasks/t2258/t2258_4_*.md, aitasks/t2258/t2258_5_*.md, aitasks/t2258/t2258_6_*.md, aitasks/t2258/t2258_7_*.md, aitasks/t2258/t2258_8_*.md
Archived Sibling Plans: aiplans/archived/p2258/p2258_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-10 10:39
---

# t2258_1 — Level model and prose rule pack (in the configured doc guide)

## Context

The rules half of t2258. The `docs_updated` gate reads only the configured guide
(`aitasks/metadata/doc_update_guide.md`) and must not read `aidocs/framework/`,
so the reader-level model and the prose rules have to live in that guide. Child 2's
`aitask-doc-review` skill reads them through a fixed interface (`## Reader levels`
plus three declarations). Binding decisions: parent plan
`aiplans/p2258_doc_audience_levels_and_readable_prose.md` § Design decisions 1–2.

## Verification of the existing plan (verify path, 2026-11-10)

Checked against the current tree; the plan still holds. Findings that refine it:

- `doc_update_guide.md` is still 90 lines; "Doc landscape" ends at line 22, and
  "Writing conventions" (line 44) stays as is. The guide lives on the task-data
  branch (`aitasks/` → `.aitask-data/`), so it is committed with `./ait git`,
  separately from the code-repo files.
- `documentation_conventions.md` § "Concept pages" is lines 25–58. Nothing else in
  `aidocs/`, `.claude/skills/`, `tests/`, `seed/` or `CLAUDE.md` references that
  section, so replacing it with a pointer breaks no reference.
- `website/README.md` § "Adding Content" (line 114) lists the required
  frontmatter; the `depth` paragraph goes there. README is not under
  `website/content/`, so `check_links.py` is not required.
- CLAUDE.md pointer is at line 289.
- All target files are clean in git (no other session's edits to gate against).
- Child 2's contract test asserts "no bullet line from the guide's prose-rules
  section appears in the review skill", so the prose rules are written as bullets
  (not a table) and the rewrite invariants that child 2's skill owns (what a
  rewrite must not touch, no invented facts) stay **out** of the guide.
- **Test contamination found:** the planned fresh-reader check classifies
  `concepts/locks.md` and `tuis/minimonitor/how-to.md`, and the guide quotes text
  from those same pages as "before" examples. A sub-agent could then flag them by
  matching the quote instead of by applying the rules. Mitigations: the guide's
  examples do not name their source pages, and the check adds a held-out page with
  known violations that the guide does not quote (`concepts/gates.md`, 237 lines,
  8 `###` sections). The Final Implementation Notes report the held-out result
  separately.
- **Review findings (user, plan round 1), both verified:** `concepts/tasks.md`
  line 11 lists eight frontmatter fields and leaves "YAML frontmatter"
  unexplained, so it is a structural example, not a clean model or control
  (Steps 4 and Verification changed). The minimonitor example now separates
  user-visible timing (reference page) from code-level detail (`aidocs/`). Neither
  `tuis/minimonitor/reference.md` nor `aidocs/` states the auto-despawn mechanism
  today (Step 1 changed).
- **Review finding (user, plan round 2), verified:** the auto-close needs two
  consecutive verified self-only observations (`AUTO_CLOSE_CONFIRMATIONS = 2`), a
  failed or non-empty observation resets the streak, and checks start only after
  the 5 s grace, so no one-refresh bound holds. Step 1's example now carries
  only those conditions. The live how-to text ("the first refresh after the
  agent pane has gone triggers an `exit()`") is itself stale; that is child 5's
  page, so it goes to t2258_5 as a note (Step 8e).

## Steps

1. **Draft `## Reader levels`** directly after "Doc landscape" (before the
   change-kind map). It opens with the interface, written exactly so:

   ```markdown
   ## Reader levels

   Other tools read the three lines below. Keep the labels as written.

   - Level field: `depth`
   - Beginner level: `main-concept`
   - Personas:
     - `main-concept`: You know git and a terminal and have never heard of aitasks.
     - `intermediate`: You have taken a task from pick to archive and know the board.
     - `advanced`: You maintain a project's aitasks setup, edit its profiles and gates, and read framework scripts.
   ```

   Then: every leaf page (any page except `_index.md`) sets `depth` to exactly one
   value. Then one short contract per value (reader / already knows / the page
   answers / forbidden):
   - `main-concept`: answers what the thing is, why you would want it, where to
     start. Defines every term it uses. Forbidden: exit codes and status lines,
     internal file paths and branch names, status vocabularies, edge-case and
     outcome tables, config keys, timing values, field lists the idea does not need.
   - `intermediate`: answers how to do one job, or what a screen, command or key
     does. May assume the `main-concept` knowledge and links to where a term is
     taught instead of re-teaching it. Forbidden: implementation mechanism (refresh
     loops, process lifecycle, internal function names) and the rationale for
     internal design choices.
   - `advanced`: answers the exact rules (validation, resolution order, failure
     cases, every field and exit status). Outcome tables and internal paths belong
     here. Forbidden: contributor-only internals (code structure, function names),
     which belong in `aidocs/`.
   One example pair at the intermediate contract: the minimonitor auto-despawn
   paragraph (refresh cycle, `exit()`, 5-second grace) → "minimonitor closes
   itself when the agent beside it exits; a new one opens with the next agent you
   launch". The example names **two destinations by kind of detail**, matching the
   `advanced` contract:
   - observable behaviour and timing a user can see or rely on → the TUI's user
     reference page. Stated with the verified conditions only, never a time bound
     (`.aitask-scripts/monitor/minimonitor_app.py`, `AUTO_CLOSE_CONFIRMATIONS = 2`
     and `_check_auto_close`): it closes only after two refreshes in a row each
     confirm it is alone in its window; a check that fails or still sees another
     pane starts the count over, and repeated failures never close it; no check
     runs in its first 5 seconds. The example must not promise "within one
     refresh" or any other deadline;
   - code-level mechanism (the per-refresh pane check, the `exit()` call) → the
     engineering docs in `aidocs/`, because function and call names are forbidden
     even at `advanced`.
   No source path is named. (Neither destination states this today; moving it is
   child 5's job, not this child's.)

2. **Draft `## Page types`.** The compass in our own words: does the reader want
   to *do* something or *understand* something; are they *learning* (away from the
   work) or *working* (in the middle of it)? do+learn = tutorial, do+work = how-to,
   understand+work = reference, understand+learn = explanation. Then the
   section → type table: `concepts/` explanation; `workflows/` how-to; `commands/`,
   `skills/` reference; TUI `_index` / `how-to` / `reference` = overview / how-to /
   reference; `getting-started.md` tutorial; `overview.md` explanation;
   `installation/` how-to; `development/` reference. A page whose role differs from
   its section (a section `_index.md` overview) takes the type of its role. Then
   the competence rule: how-to and reference pages assume the reader knows what
   they want; `depth` decides how much they may assume (a `main-concept` page of any
   type defines its terms; `intermediate` / `advanced` pages link to where a term
   is taught).

3. **Draft `## How a subject spans levels`.** One page per type; the TUI
   `_index` / `how-to` / `reference` split is the model. A concept page states the
   idea and links to the workflow or reference page that owns the detail. Every
   fact survives: a fact cut from a page because it is above the page's level is
   moved to the page that owns it (check first whether that page already states it,
   then link), never deleted. A short page may stay one page with a plain opening
   and one clearly headed details section; split it when the details outgrow the
   opening.

4. **Move `## Concept pages`** into the guide, after "How a subject spans levels":
   the five sections in order, no `###` under "What it is", "states the idea,
   not the rules", internals on the owning page, the complementary-to-workflow
   rule. The model pages (`concepts/{tasks,plans,folded-tasks,execution-profiles}.md`)
   are named as **structural examples only** (section order and length), with a
   sentence saying their content is not a model: `tasks.md` opens with a list of
   eight frontmatter fields and leaves "YAML frontmatter" unexplained, which the
   `main-concept` contract forbids. No website page is edited here; child 3 audits
   these pages. Reworded to sit under the level model (a concept page is an explanation
   page, usually `main-concept`). In `aidocs/framework/documentation_conventions.md`,
   replace lines 25–58 with a heading plus a two-line pointer to the guide's
   "Concept pages", "Reader levels", "Page types" and "How a subject spans levels"
   sections, saying the gate reads only the guide so the guide is the single
   source.

5. **Draft `## Prose rules`**, all bullets. Primary rules first:
   - Don't assume the reader knows what you know: declare the page's `depth` and
     type before drafting; define each term the reader may not know at first use;
     say what a thing is for before how it works; open a long section with one
     sentence that says what it covers. Example pair: the locks concept opening
     ("two locks… end-of-task merge… shared repository root") → a plain
     main-concept opening, with the cut facts moved.
   - Be concrete: name the actual items, not "factors / aspects / considerations";
     don't repeat table values in the prose around the table; keep numbers out of
     opening paragraphs.
   - Plain words before terms: use the everyday word when it says the same thing;
     keep a real technical term when it names the thing, and define it.
   - One term per thing: no synonym rotation.

   Then "Avoid", one bullet each with a before/after pair. The "before" is quoted
   from our pages (no path named); the "after" is written fresh and keeps every
   fact:
   - staged contrast / not-X-but-Y — "Parking is a signal to *you*… Freezing is a
     decision about the *agent*…"
   - one-line closers — "The mutex serializes the merges that take it; it does not
     police the repository." (after: cut; the sentence before says which merges
     take it)
   - staged run-ups — "Two ways back, and the obvious one is usually not the
     cheaper one:"
   - deep-sounding sayings — "What you trade a code agent for is that viewer"
   - arguing with no one — "…so "same user" is not treated as "same worker"."
   - forced triads — sample found by grep during implementation
   - repeated openings — "…still running, still holding its context, still
     costing you memory…"
   - dashes as the default connector — "Ten or twenty panes, each holding a code
     agent that has finished its task — and what you actually want…"
   - inflated significance — "This is particularly powerful for parent tasks…" /
     "creating a seamless round-trip"
   - shallow -ing riders — "…with the correct agent string, ensuring accurate
     `implemented_with` metadata."
   - avoiding is/are/has — "The subdirectory name serves as a strong hint…"
   - decorative bold — "The lock excludes **sessions**, not just people."
   - heading repeated in the first sentence — sample found by grep
   - writing about the document — "This page tracks current workflow issues by
     code agent. Issues are grouped by agent below."
   - closing summaries — sample found by grep
   For the three "found by grep" entries, search `website/content/docs/` first;
   only if the site has no instance, write a short example and label it
   "(constructed)". Pattern names are plain run-in labels, not bold, so the list
   does not break its own decorative-bold rule.

6. **Draft `## Sources and credits`.** Diátaxis (Daniele Procida,
   https://diataxis.fr/): page types and the compass, in our words.
   yzhao062/agent-style (https://github.com/yzhao062/agent-style), rules under
   CC BY 4.0 (link the license): RULE-01, -03, -06, -07, -B, -E, -F adapted and
   reworded. blader/humanizer (https://github.com/blader/humanizer, MIT) and the
   plain-language skills (mdskills `plain-language`, shihyuho/skills `plain`):
   ideas for the avoid list and "every fact survives", no text copied.
   keithpatton/diataxis-agent-skill (CC BY-SA 4.0): read for its compass and
   anti-patterns; none of its text is copied, and later edits must not copy it.
   anthropics/skills `doc-coauthoring`: the reader-testing method the review
   skill uses.

7. **Pointers.** CLAUDE.md line 289: the documentation_conventions pointer also
   says the reader-level model, page types and prose rules live in
   `aitasks/metadata/doc_update_guide.md`. `website/README.md` § "Adding Content":
   one bullet saying every leaf page also sets `depth` (`main-concept`,
   `intermediate` or `advanced`), each value has a contract in the guide's
   "Reader levels" section, and `depth` is required.

8. **Size check.** Added guide lines ≤ ~150 (`git diff --stat` on the task-data
   branch). If over, shorten the contracts before the examples.

### Post-phase (risk mitigations)

1. [guide_self_review] Give a fresh sub-agent only the new guide sections (no
   repo access) with the `main-concept` persona plus the note "you will write docs
   using these rules". Ask it to list every term it had to guess, every rule it
   found ambiguous, and every place where the new text itself breaks a rule in
   its avoid list. Fix what it finds, re-run once, and record both reports
   (summarised) in Final Implementation Notes.

## Verification

- `grep -c '^## Reader levels' aitasks/metadata/doc_update_guide.md` → `1`; the
  lines `- Level field: \`depth\``, `- Beginner level: \`main-concept\`` and the
  three persona lines are present.
- `grep -n 'What it is' aidocs/framework/documentation_conventions.md` finds no
  concept-page rule text; only the pointer remains under its heading.
- Fresh sub-agent, given only the new guide sections plus the page files,
  classifies `concepts/locks.md`, `concepts/tasks.md`,
  `tuis/minimonitor/how-to.md` and the held-out `concepts/gates.md` (type, whether
  the declared `depth` fits, violations). Expected: locks outcome table flagged,
  minimonitor mechanism flagged, gates.md `###`
  deep-dives / mechanism flagged, and tasks.md flagged for its field list and the
  unexplained "YAML frontmatter" (it is a structural example, not a clean page; a
  reviewer that passes it has missed exactly what the guide targets).
  **Clean control:** a short compliant `main-concept` page written to the
  scratchpad (≈25 lines, the four concept sections, no field lists, every term
  defined), given to the same sub-agent unlabelled; expected: no level violations.
  Record the answers in Final Implementation Notes, the held-out and control
  results separately.
- No `website/content/` page edited (`git status website/content` clean).

## Risk

### Code-health risk: low
- The guide is read on every `docs_updated` run; long or ambiguous additions degrade every doc update · severity: low · → mitigation: inline post-phase guide_self_review
- A misformatted interface line breaks child 2's level-model detection · severity: low · → mitigation: none separate; covered by the Verification grep of the exact lines

### Goal-achievement risk: medium
- Contracts and rules written in the abstract, or whose own wording breaks them, may not change how real pages read · severity: medium · → mitigation: inline post-phase guide_self_review
- The fresh-reader classification check is partly contaminated because the guide quotes two of the checked pages · severity: low · → mitigation: none separate; held-out `concepts/gates.md` in Verification, reported separately

Reassessed after inlining guide_self_review: levels unchanged (the post-phase
reduces the clarity risk, it does not prove the rules shape real pages; child 3's
pilot does that).

### Planned mitigations
- timing: post-phase | name: guide_self_review | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: abstract or self-violating rule text; guide length/clarity | desc: fresh sub-agent with main-concept persona reviews only the new guide sections for guessed terms, ambiguous rules and avoid-list violations; fix, re-run once, record both reports

## Post-implementation

Step 9 of the task workflow: review; commit code-repo files
(`aidocs/framework/documentation_conventions.md`, `CLAUDE.md`, `website/README.md`)
with `documentation: Add reader-level model and prose rules to the doc guide (t2258_1)`,
and the guide with `./ait git` naming its path; archive.

Step 8e note: send `./ait note 2258_3 --from 2258_1` saying that `concepts/tasks.md`
(one of its two reader-test controls) fails the `main-concept` contract (field
list, unexplained "YAML frontmatter"), so it is a weak control. Its
reader_test_baseline_and_control step should expect findings on it, or add a
compliant control.

Step 8e note: send `./ait note 2258_5 --from 2258_1` saying that
`tuis/minimonitor/how-to.md`'s auto-despawn note is factually stale: closing
needs two consecutive verified self-only refreshes, a failed or non-empty check
resets the count, repeated failures never close it, and checks start after 5 s
(`minimonitor_app.py` `AUTO_CLOSE_CONFIRMATIONS`, `_check_auto_close`). When it
moves the mechanism out, the reference page should carry these conditions and
no time bound, and `aidocs/` should get the code-level detail.
