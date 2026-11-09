---
priority: medium
effort: high
depends: []
issue_type: documentation
status: Implementing
labels: [documentation, web_site, doc_quality, aitask_gate_docs_updated]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
children_to_implement: [t2258_1, t2258_2, t2258_3, t2258_4, t2258_5, t2258_6]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-11-09 14:07
updated_at: 2026-11-09 23:09
---

## Problem

Pages under `website/content/docs/` that a code agent writes, and nobody reviews,
often don't read as documentation for a person. The main failure is a mismatch
between the audience and the level of detail, more than bad grammar:

- **Too much mechanism on pages meant to orient.** Overviews, concept pages, how-to
  guides and workflow pages explain internals a newcomer has no use for.
- **Technical language where plain words would do.** Someone trying to learn what
  aitasks is, with no prior knowledge, gets field names, exit codes and edge-case
  tables before they get the idea.
- **AI-tell phrasing on top of that:** staged contrasts, run-up sentences,
  dash-heavy rhythm, "not X but Y" framing.

The current structure may also need revising so each subject is split across
levels, from beginner to technical. Use existing skills and frameworks to guide
both the prose and the levels each page or subject is split into, rather than
inventing a style guide from scratch.

## What exists today (evidence, measured 2026-11-09)

- **A level tag exists but has no contract.** `website/hugo.toml` declares a
  `depth` taxonomy shown in the page header (`taxonomyPageHeader`). Counts:
  `main-concept` 13, `intermediate` 88, `advanced` 58, and 16 of 175 pages
  untagged. Nothing in `aidocs/`, `website/README.md` or
  `aitasks/metadata/doc_update_guide.md` says what may or may not appear at each
  level, so the tag labels a page without shaping what goes on it.
  (`maturity` is a separate taxonomy: experimental / stabilizing / stable.)
- **Concept-page rules exist but nothing enforces them.**
  `aidocs/framework/documentation_conventions.md` § "Concept pages" says a concept
  page "states the idea, not the rules that enforce it" and allows no `###`
  deep-dives under "What it is". The model pages are 28–80 lines. Violations:
  - `concepts/locks.md`, tagged `main-concept`, 127 lines: opens with a 7-row
    lock-outcome table about session liveness, `LOCK_FAILED` and pre-anchor locks.
  - `concepts/gates.md`: 237 lines, 8 `###` sections.
  - `concepts/framework-session.md`: 198 lines.
  - `concepts/skill-templating.md`: 190 lines.
  - `concepts/attachments.md`: 164 lines.
- **Mechanism in how-to pages.** `tuis/minimonitor/how-to.md` explains the refresh
  cycle, `exit()` and a 5-second startup grace period to end users.
- **Workflow pages mix every level.** 44 pages, up to 336 lines
  (`bug-report-intake.md`, `freeze-and-restore-agents.md`,
  `manual-verification.md`). Each one blends overview, steps and internals.
- **The split already works in one place.** Each TUI has
  `_index` / `how-to` / `reference` pages, which is roughly the Diátaxis split.
  That proves the shape works here, but mechanism still leaks into the how-to
  pages.
- **AI-tell prose sample:** `workflows/freeze-and-restore-agents.md`. For example,
  "Parking is a signal to *you*… Freezing is a decision about the *agent*", "the
  obvious one is usually not the cheaper one", and "What you trade a code agent
  for is that viewer".
- **The pipeline checks no readability.** `aitasks/metadata/doc_update_guide.md`
  (read by the `docs_updated` gate, `.claude/skills/aitask-gate-docs-updated/`)
  carries content rules only: current-state-only, genericized agent names,
  generic example project names, links. `aitask-docs-gap` finds missing docs,
  not hard-to-read ones.

## Prior art to adopt or adapt (researched 2026-11-09)

Check each license before copying text. Adapting ideas is always fine.

- **Diátaxis** (Daniele Procida, https://diataxis.fr/) sorts pages into tutorial,
  how-to, reference and explanation. Agent skill:
  https://github.com/keithpatton/diataxis-agent-skill (**CC-BY-SA-4.0**, a
  share-alike license, so adapt it rather than vendoring its text). It has
  classify / audit / generate / **restructure** modes, a classification decision
  tree (`references/compass.md`) and an anti-pattern list
  (`references/anti-patterns.md`). Other Diátaxis skills:
  sammcj/agentic-coding `writing-documentation-with-diataxis`, and an
  oxidecomputer `eng` plugin skill.
- **Progressive disclosure:** simplest and most common path first, then link to
  depth. Layer by what the reader is trying to do, not by raw technical
  complexity, and make each level stand on its own.
- **blader/humanizer** (https://github.com/blader/humanizer, MIT, about 67k stars):
  26 AI-writing patterns in six groups, built from Wikipedia's "Signs of AI
  writing". It edits only prose and leaves code, frontmatter and link targets
  alone. Group F, "writing for the wrong reader", is directly relevant here.
- **anthropics/skills `doc-coauthoring`**
  (https://github.com/anthropics/skills/tree/main/skills/doc-coauthoring):
  *reader testing*. A sub-agent gets only the page plus 5–10 questions a real
  reader would ask, then reports wrong answers, ambiguity and unstated
  assumptions. The page is done when that fresh reader stops finding new gaps.
  This maps well onto a "newcomer can understand this page" check.
- **yzhao062/agent-style** (https://github.com/yzhao062/agent-style, rules
  CC BY 4.0, tooling MIT): 21 rules. RULE-01 says not to assume the reader shares
  your tacit knowledge, plus jargon, concreteness and the field-observed LLM
  patterns. It ships a `style-review` second pass. Its benchmark is only
  directional.
- **Plain-language skills** (for example mdskills `plain-language` and skills.sh
  `shihyuho/skills/plain`): every fact must survive a rewrite, because clear is not
  the same as vague. Pair the rules with before/after examples.
- **Optional deterministic lint:** Vale (`pacman` extra, v3.26.0; not installed
  here) with `tbhb/vale-ai-tells` (MIT, about 137 rules aimed at technical docs,
  all at `error` by default, false positives need per-rule tuning) and the
  errata-ai Google style port. Vale publishes https://vale.sh/AGENTS.md. Use it
  only as an advisory feedback sensor for the agent. It judges style, never
  content.

## Integration map (source files read 2026-11-09)

Which parts of the existing skills to take, where each goes, and on what terms.
Ordered by the task's main goal: **matching detail to the reader comes first**;
prose cleanup supports it. "Adopt" means use the rule as written (with
attribution where the license asks for it). "Adapt" means rewrite the idea in our
own words for our pages. "Skip" means deliberately left out.

### Primary: matching detail to the reader

| Part | Source | Verdict | Where it goes | Terms |
|---|---|---|---|---|
| **The compass**: two questions per page. Does the reader *do* something or *know* something? Are they *studying* or *working*? The answers pick tutorial / how-to / reference / explanation (`diataxis/references/compass.md`). | keithpatton/diataxis-agent-skill | **Adapt** | Level model in the doc guide: the "what kind of page is this" test that every new or edited page passes before drafting. | CC-BY-SA-4.0: write our own text and credit Diátaxis. Never copy the files, or the share-alike terms spread to our guide. |
| **Anti-patterns 1, 2, 5**: tutorial with too much explanation; how-to that teaches; mixed-mode page, including "reference tables embedded in an overview" (`references/anti-patterns.md`). Each has detection signals and a fix ("move the detail to a reference page and link to it"). | same | **Adapt** | Audit checklist (scope 4) and the gate review pass (scope 3). Anti-pattern 5 is exactly the `concepts/locks.md` case. | same |
| Anti-patterns 3, 4: reference written as narrative; explanation containing procedures. | same | **Adapt**, lower priority | Audit checklist | same |
| **Restructure method**: split a mixed page into one page per type, or keep a short overview and link out. "Getting Started" splits into a tutorial plus reference; a README keeps an overview and links out. | same | **Adapt** | Method for restructuring the workflow pages and the long concept pages (scope 4). It matches our existing rule that "internals belong on the page that owns the behaviour". | same |
| **RULE-01, "Don't assume the reader shares your tacit knowledge"**: define terms the intended reader may not know; state the purpose before the mechanics; give a one-sentence map before a long section; *name the intended reader before drafting*. | yzhao062/agent-style `RULES.md` | **Adopt** (core rule) | First rule of the newcomer rule pack. "Name the reader before drafting" becomes "declare the page's level before drafting". The source says no mechanical check exists, so the fresh-reader test below checks it. | CC BY 4.0: attribution required |
| **RULE-03, concrete language**: name the specific items instead of "factors / aspects / considerations"; *don't copy every table value into prose*; keep intros light on numbers. | same | **Adopt** | Rule pack | CC BY 4.0 |
| **Reader testing**: predict 5–10 reader questions; give each to a sub-agent that sees *only the page*; then ask it what is ambiguous, what it assumes the reader already knows, and what contradicts itself; fix and repeat until no new gaps appear. | anthropics/skills `doc-coauthoring` (Stage 3) | **Adapt** | Gate review pass for beginner-level pages, and spot checks during the audit. **Our change:** their fresh reader is a generic model that is in effect an expert. Ours gets a *persona from the page's level*, for example "you know git and a terminal and have never heard of aitasks". It also reports two extra lists: every term it had to guess, and every detail it didn't need to answer its questions. The second list is the "too much mechanism" signal. | No license field in the SKILL.md and none found for the folder: reuse the method only and write our own procedure |
| **"Every fact must survive a rewrite"** | plain-language skills (mdskills, shihyuho/skills `plain`) | **Adopt** as a principle | Rule pack. Interpretation: a fact cut from a beginner page must be *moved* to the page that owns it, not deleted. | Idea only, no text copied |

### Secondary: prose cleanup

| Part | Source | Verdict | Where it goes | Terms |
|---|---|---|---|---|
| **What not to touch, and no invented facts**: rewrite only prose; leave code blocks, inline code, commands, paths, URLs and frontmatter unchanged; add no facts, names or numbers; ask, or write a simpler sentence. | blader/humanizer `SKILL.md` | **Adopt** | Hard rules for any rewrite pass (gate review and audit) | MIT: may quote with the notice |
| **Group A, staging**: not-X-but-Y, one-line closers, deep-sounding sayings, staged run-ups, arguing with no one. These are the patterns found in `freeze-and-restore-agents.md`. | humanizer | **Adapt** | Rule pack, short "avoid" list with before/after examples from our pages | MIT |
| Picks from B–E: forced triads (6), repeated openings (7), dashes as the default connector (8), inflated significance (13), shallow -ing riders (15), avoiding is/are/has (18), decorative bold (19), heading repeated in the first sentence (24), writing about the document instead of its subject (25). | humanizer | **Adapt** | Same list; merge duplicates with agent-style into one entry each | MIT |
| RULE-06 jargon → everyday word (keep real technical terms), RULE-07 X-not-Y, RULE-B dashes, RULE-E closing summaries, RULE-F one term per thing, no synonym rotation. | agent-style | **Adopt**, merged with the humanizer entries | Rule pack | CC BY 4.0 |
| Humanizer **group F** ("re-explaining what the reader knows") | humanizer | **Skip** | Not applicable: it targets replies in a thread, where the reader has the context. Our problem is the opposite. | — |
| Humanizer voice matching / writing sample, curly quotes, chat residue, knowledge-limit disclaimers | humanizer | **Skip** | Low value for site pages | — |
| agent-style RULE-G (title-case headings), RULE-I (no contractions), RULE-H (citations) | agent-style | **Skip** | House-style choices or not about product docs; check our heading case before deciding anything | — |
| **Vale + `vale-ai-tells`** (137 rules, all at `error`, needs per-rule tuning) | tbhb/vale-ai-tells | **Defer** | Possible later follow-up, advisory only. It checks wording and cannot see a level mismatch, which is the main problem. Not installed here. | MIT |
| Other Diátaxis skills (sammcj, oxidecomputer), Beagle docs-style, dhruvbaldawa writing-documentation | — | **Not read** | Only if planning finds a gap the sources above leave | — |

### Local pieces and how they change

- **`aitasks/metadata/doc_update_guide.md` is the home for the level model and the
  rule pack.** The docs gate skill is forbidden from reading framework convention
  docs ("MUST NOT reference framework-internal convention docs — read the
  project's configured guide instead"). Anything that lives only in
  `aidocs/framework/documentation_conventions.md` never reaches the agent writing
  the docs. The concept-page rules there must be carried into the guide, or the
  guide must restate them.
- **`docs_updated` gate** (`.claude/skills/aitask-gate-docs-updated/SKILL.md`):
  add the review pass between step 3 (infer + propose) and step 4 (confirm with
  the user), so the user sees the reader report alongside the proposed edits. Its
  Codex and OpenCode surfaces are generated wrappers; refresh them with
  `aitask_audit_wrappers.sh`.
- **`aitask-docs-gap`** (Step 6, "What to write"): add the target level for each
  gap, so the documentation task it creates knows its reader.
- **`seed/doc_update_guide.md`** (68 lines, generic default for other projects):
  candidate for a project-agnostic version of the level model.

### Uncertain choices, recorded for planning

1. **One axis or two.** Our `depth` values describe how much the reader already
   knows; Diátaxis types describe what the reader needs. Combine them (for example
   "depth sets the vocabulary, type sets the shape"), or replace `depth`?
2. **Anti-pattern 2 conflicts with our goal.** Diátaxis treats "defining terms
   before using them" as a fault in a how-to (it assumes a competent reader).
   Beginner pages *must* define terms. The level model has to say which pages
   assume competence.
3. **Where the rule pack lives.** Inside `doc_update_guide.md`, or a separate file
   listed in `doc_update.extra_guides`. The gate reads `extra_guides` today, but
   it is a list value outside the config resolver.
4. **Fresh-reader cost and portability.** Sub-agent runs for every edited
   beginner page, or only during the audit? Codex and OpenCode may lack sub-agents,
   so they need a fallback: a self-review checklist, or a deferral recorded in
   the gate log.
5. **Personas.** How many, and their exact wording. One per `depth` value is the
   simplest start.
6. **Seed guide.** Ship the level model to other projects now, or after it has
   proved itself on this site?

## Scope (to be refined and likely split into children during planning)

1. **Level model.** Write the contract for each audience level and page type.
   Decide whether to keep the existing `depth` values (`main-concept` /
   `intermediate` / `advanced`), rename them, or map them onto Diátaxis types.
   For each level, say who the reader is, what they already know, what the page
   must answer, and what is forbidden on it (for example, no exit codes, internal
   file paths or edge-case tables at the beginner level). The current
   concept-page rules in `documentation_conventions.md` become one instance of
   this model. Decide how a subject spans levels: separate pages per level (as
   the TUIs do now), layered sections within one page, or both. Also decide
   whether `depth` becomes a required frontmatter field.
2. **Newcomer prose rule pack.** A concise, project-owned rule list adapted from
   the sources above. Cover: plain words before terms, define a term before using
   it, idea before mechanism, and the AI-tell patterns to avoid. Include
   before/after examples taken from our own pages.
3. **Wire it into the doc-writing path.** Add the level model and rule pack to
   `aitasks/metadata/doc_update_guide.md`, and decide whether the generic
   `seed/doc_update_guide.md` gets a project-agnostic version. Extend the
   `docs_updated` gate procedure with a review pass after drafting:
   - a pattern/level check against the page's declared depth;
   - a **fresh-reader sub-agent test** (doc-coauthoring style) for beginner-level
     pages.

   Decide whether to package this as a reusable skill (for example
   `aitask-doc-review`), so `aitask-docs-gap` and ad-hoc doc edits can call it too.
   Evaluate Vale + ai-tells as an optional advisory step. Don't make it a hard
   gate.
4. **Audit and restructure the existing site.** Classify every page by level/type
   and list the violations, starting with the concept pages above and the
   longest workflow pages. Then restructure: move mechanism to reference pages or
   `aidocs/`, and split mixed workflow pages. Follow the
   "internals belong on the page that owns the behaviour" rule. This is large;
   expect one child per section (concepts, workflows, tuis, skills, commands,
   overview/getting-started).

## Constraints

- Follow `aidocs/framework/documentation_conventions.md`: current-state-only,
  genericize the agent set in blurb prose, and use `relref` for internal links.
- Run `cd website && python3 check_links.py --build` after editing any page under
  `website/content/`. Offer `check_link_relevance.py` when links are retargeted.
  Moving content between pages is exactly the case where links break silently.
- Skill changes go to the Claude Code version (`.claude/skills/`) first. Suggest
  separate tasks to port them to the Codex (`.agents/skills/`) and OpenCode
  (`.opencode/`) versions. Run `aitask_skill_verify.sh` and regenerate goldens if
  any `.md.j2` changes.
- The rule pack and level contract must be written to the same standard they set.
  A fresh reader should understand them.

## Related

- **t2186** (generic agent-prompt eval harness, `aidocs/benchmarks/prompt_eval/`)
  can later measure whether this task's doc-review instructions (the rule pack
  and the fresh-reader pass in the docs gate) work reliably across agents,
  including open choice 4 (agents without sub-agents). It is **not** a
  prerequisite: this task's work does not need the harness. Testing the review
  pass with it would be a separate follow-up once both exist, and it fits only
  after t2186 supports judge-scored prompts (its second spec is meant to be
  deterministic, with no LLM judge).

## Done when

- A written level model exists, with a contract for each depth/page type, and the
  doc-writing path reads it.
- The `docs_updated` path runs a readability/level review, including a
  fresh-reader test for beginner-level pages.
- The existing site has been audited against the model, and restructuring work is
  done or tracked as child tasks.
