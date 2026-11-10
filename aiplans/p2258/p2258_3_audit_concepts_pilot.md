---
Task: t2258_3_audit_concepts_pilot.md
Parent Task: aitasks/t2258_doc_audience_levels_and_readable_prose.md
Sibling Tasks: aitasks/t2258/t2258_1_*.md, aitasks/t2258/t2258_2_*.md, aitasks/t2258/t2258_4_*.md, aitasks/t2258/t2258_5_*.md, aitasks/t2258/t2258_6_*.md, aitasks/t2258/t2258_7_*.md, aitasks/t2258/t2258_8_*.md
Archived Sibling Plans: aiplans/archived/p2258/p2258_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-10 22:29
---

# t2258_3 — Concepts audit (pilot)

## Context

This is the first time the level model (t2258_1, now in
`aitasks/metadata/doc_update_guide.md`) and the review skill (t2258_2) are
applied to real pages. The target is `website/content/docs/concepts/`: 24 leaf
pages plus `_index.md`. The reader reports and lessons from this pilot go back
into the guide before children 4–7 start. Method: parent plan
`aiplans/p2258_doc_audience_levels_and_readable_prose.md` § "Common audit method
(children 3–7)".

## Verification of the existing plan (verify path, 2026-11-10)

Checked against main @ 9b54f33d8. The approach still holds. These findings
change the plan:

- **The skill was renamed.** It is `aitask-docs-review`
  (`.claude/skills/aitask-docs-review/SKILL.md`), invoked as
  `/aitask-docs-review <page>... [--budget N] [--caller audit]`. With
  `--caller audit` it only reports, so this child makes the edits itself. Every
  `aitask-doc-review` in the task body means this skill (note from t2258_2,
  acknowledged).
- **The skill's fresh-reader test only takes beginner-level pages.** Four of the
  six long pages are not `main-concept`: `gates` and `framework-session` are
  `advanced`, and `skill-templating` and `attachments` are `intermediate`. The
  skill would mark them `not-run(not-beginner)`. The pre-phase asks for the
  `main-concept` persona on all eight pages, so for the baseline and the
  after-reports I run the skill's Step 4 method directly (questions, sub-agent,
  the five follow-up questions) and do not go through its candidate filter.
  These reports are recorded as "fresh-reader method, main-concept persona".
  Ordinary reviews of edited pages still go through the skill.
- **`tasks.md` is a weak control** (note from t2258_1, acknowledged). Line 11
  lists eight frontmatter fields, and the page never explains "YAML
  frontmatter". So I add a third control: a ~28-line compliant scratch concept
  page, unlabelled. The separation test is made concrete (Pre-phase step 2).
- **Concept-page inventory today** (lines / `depth` / `###` count):
  - The six long pages:
    - `gates` 237 / advanced / 8
    - `framework-session` 198 / advanced / 6
    - `skill-templating` 190 / intermediate / 3
    - `attachments` 164 / intermediate / 5
    - `topic-anchoring` 141 / main-concept / 0. It has non-standard sections (`How the key is stored`, `Creating anchored tasks`, `Children and re-anchoring`, `Board view`) and no `Why it exists` / `How to use`.
    - `locks` 127 / main-concept / 5
  - The rest run 28–79 lines and have no `###`. Every leaf page has `depth`; `_index.md` is a link list and needs none.
  - `depth` uses the list form `[value]`, which the skill accepts.
- **Nothing is dirty right now.** `git status` shows no changes under `website/`,
  `aidocs/` or the guide. The sitrep pages that were dirty at session start were
  committed in 9b54f33d8. The shared-file gate still runs before each edit.
- **Owner pages exist for most detail.** `commands/lock.md`,
  `workflows/crash-recovery.md`, `workflows/parallel-development.md`
  (§ Serialized Merge-Back), `commands/gates.md`, `commands/attach.md`,
  `development/task-format.md` (§ Topic Anchoring, § Nested fields),
  `commands/setup-install.md#session-hooks`,
  `skills/aitask-pick/execution-profiles.md` (§ Profile Override Argument) and
  `tuis/board/reference.md`. Some detail has no owner: framework-session's
  record file, states, leases, cleanup reasons and overrides; skill-templating's
  dispatch, per-agent surfaces and rendered dirs; much of the gates
  enforced-set, digest, ledger and registry rules.
- **User decision (planning, 2026-11-10):** where an existing website page
  fits, use it. That includes the **Development** section for architecture that
  helps users and integrators understand the framework. When a substantial block
  of detail has no suitable home, create a focused `advanced` reference page in
  `development/` and link it from the concept page. Keep `aidocs/` for
  contributor-only implementation detail. Add this boundary to the guide so
  useful public architecture documentation is kept. `development/_index.md`
  already documents library functions and the directory layout. That is the
  integrator-facing architecture this decision keeps public. The guide's
  current text ("code mechanism … function names … goes to `aidocs/` at every
  level") is narrower than this decision, so the guide is changed **first**
  (Pre-phase step 3), before any inventory verdict, move or review relies on it.
- **Review findings (user, plan round 1), both verified:**
  - The first survival check selected only lines with inline code, table rows
    or numbers. `locks.md` lines 56–58 state rules in plain prose: the
    reservation holds through conflict resolution, post-merge verification and
    cleanup, and nothing releases it automatically. Those lines would have
    escaped the check. A matching token can also survive while its condition is
    lost. The post-phase check now compares every removed block, claim by claim,
    with its destination, using an independent sub-agent. Token greps are only
    supporting evidence.
  - Page reviews ran before the guide changed. Now the boundary goes into the
    guide in the pre-phase, before any page work. Pilot lessons are the last
    guide change (Step 5). The recorded level/prose review of every edited page
    runs after that (Step 6), and any later guide change re-runs it.

### Pre-phase (risk mitigations)

1. [reader_test_baseline_and_control] Before editing any page, run the
   fresh-reader method with the `main-concept` persona ("You know git and a
   terminal and have never heard of aitasks.", from the guide) on these pages:
   - the six long pages: `locks`, `topic-anchoring`, `gates`,
     `framework-session`, `skill-templating`, `attachments`;
   - controls `tasks.md` and `plans.md`;
   - a compliant scratch control: a ~28-line `main-concept` concept page in the
     scratchpad, with the four concept sections, no field lists, and every term
     defined. Write it before running, and give it to the reader unlabelled like
     the rest.

   For each page:
   - the sub-agent gets the full page text inline, frontmatter and shortcodes
     included, plus the persona and 5–10 reader questions;
   - it is told to answer from the page text alone and not to open files,
     search or browse;
   - then I ask the five follow-up questions in the same conversation
     (SendMessage): what was ambiguous, what it assumed the reader knew,
     guessed terms, unneeded details, contradictions.

   Run the nine readers in parallel. Record each report verbatim under "Reader
   reports — before", with counts of guessed terms and unneeded details.
2. [reader_test_baseline_and_control] **Separation test.** It passes when:
   - `locks` and `topic-anchoring` (the two `main-concept` long pages) each
     score higher than both `tasks` and `plans`, where score = guessed terms
     + unneeded details;
   - the scratch control scores lowest of all nine;
   - the four non-beginner long pages also score above the controls. They are
     reported separately, because a `main-concept` reader on an `advanced` page
     is expected to guess more.

   If the test fails: stop, tune the persona or question guidance in
   `.claude/skills/aitask-docs-review/SKILL.md` Step 4 (procedure only, no rule
   text), re-run the failing pages, record both runs, and only then continue.
   Run `bash tests/test_docs_review_contract.sh` after any skill edit.
3. [guide_boundary_self_review] **Set the detail-placement boundary in the
   guide before any page work** (`aitasks/metadata/doc_update_guide.md`, on the
   task-data branch; user decision). In "Reader levels" (the
   two-kinds-of-detail paragraph) and in "How a subject spans levels" (the
   owning-page sentence), split today's "code mechanism → `aidocs/`" into three:
   - behaviour detail → the feature's reference or workflow page;
   - public architecture → `development/` (reference type). This is what helps
     users and integrators understand or extend the framework: data layout and
     file formats, where state lives, which component writes what, the
     concurrency and atomicity guarantees a reader relies on, extension points,
     and library functions meant to be called. `development/` is also where a
     focused `advanced` reference page goes when substantial detail has no other
     home;
   - contributor-only implementation detail → `aidocs/`: internal loops and
     counters, private helpers, code structure for maintainers, rejected
     alternatives and design history, test strategy.

   Update the minimonitor example only if its wording now conflicts. Its tmux
   query, counter and `exit()` stay contributor-only. Keep the
   `## Reader levels` interface lines byte-identical, then run
   `bash tests/test_docs_review_contract.sh`.

   **Check it:**
   - give a fresh sub-agent only the changed guide passages and eight sample
     facts from the six long pages, at least two of each kind. For example:
     framework-session's record-file location and override env vars; its
     single-writer, lock-free-reader guarantee; minimonitor's confirmation
     counter; the gate digest construction; a lock outcome a user sees; the
     `attachments:` block format;
   - ask it to place each fact as behaviour detail, public architecture
     (`development/`) or contributor-only (`aidocs/`), and to name any wording
     it found ambiguous;
   - where its placement differs from the intended one, fix the guide wording
     and re-run once.

   Record both reports in Final Implementation Notes. Restructuring starts only
   after this step.

## Steps

1. **Inventory.** Add a table to this plan covering all 25 pages: lines,
   `depth`, type (explanation; `_index` = overview), verdict (ok / minor /
   restructure), and violations. Check in this order: Diátaxis anti-patterns 1,
   2 and 5, then 3 and 4, then the guide's level contract for the page's
   `depth`, then the concept-page section rules, then the prose rules. Decide
   each page's `depth`, keeping the declared value unless the subject's reader
   is clearly different. Record any retag with its reason. Most concept pages
   should end up `main-concept`; `intermediate` or `advanced` only for subjects
   only experienced users meet.
2. **Shared-file gate before every edit**, for both concept pages and
   destination pages: `git diff --quiet HEAD -- <page>` and
   `git status --short <page>`. A page dirty from another session is not edited.
   It goes into the **skipped-page ledger** in this plan with its path, reason
   and the dirty state seen. If the dirty page is a destination, its facts stay
   on the source page until close-out.
3. **Restructure the six long pages**, in this order: `locks`,
   `topic-anchoring`, `gates`, `framework-session`, `skill-templating`,
   `attachments`. Each ends with the concept sections (What it is / Why it
   exists / How to use / See also / `**Next:**`), no `###` under "What it is",
   and only what its `depth` allows. Every cut fact is moved, or linked when the
   owner already states it. Check the owner before moving anything. Each move is
   recorded as one row in the **moved-fact table** (source page#section → fact
   → destination#anchor → `moved` / `already-stated` / `corrected` /
   `dropped(reason)`). Planned destinations, confirmed by reading each owner
   first:
   - `locks`: the task-lock outcome table and session-liveness rules go to
     `commands/lock.md` (§ How It Works / Locking vs Ownership) and
     `workflows/crash-recovery.md` (§ When the Holder Is Still Running, Lock
     anomaly fallback). The merge-mutex scope, the reservation that outlives the
     command, the session anchor and the recovery ladder go to the `ait lock` /
     merge-mutex reference if `ait lock` owns those verbs. Otherwise they get a
     new `development/` reference section. The intermediate how-to summary goes
     to `workflows/parallel-development.md#serialized-merge-back`. The
     `aitask-locks` branch stays a link to `concepts/git-branching-model`.
   - `topic-anchoring`: key storage and re-anchoring rules go to
     `development/task-format.md#topic-anchoring`. Creation flags go to the
     owning command or skill page (`commands/task-management.md` /
     `skills/aitask-create`). The By-Topic view goes to `tuis/board/reference.md`.
     The rewrite adds the missing `Why it exists` / `How to use` sections.
   - `gates`: the user-visible verbs and exit statuses go to
     `commands/gates.md`. The enforced set, snapshot, digest, ledger, registry,
     retry budgets and unlock order become a new `development/gates.md`
     (`advanced` reference) unless `commands/gates.md` already states them.
     Contributor-only detail goes to `aidocs/gates/` only where it is not
     already there.
   - `framework-session`: a new `development/framework-session.md`
     (`advanced`). It covers the records file and its permissions, the single
     writer and lock-free readers, identity versus location, states, operation
     leases, cleanup reasons and the override env vars. The session hook goes
     to `commands/setup-install.md#session-hooks`, linked where it is already
     stated.
   - `skill-templating`: invocation paths go to
     `skills/aitask-pick/execution-profiles.md#profile-override-argument`.
     Dispatch, per-agent surfaces, rendered dirs and `.gitignore` go to a new
     `development/skill-templating.md` (`advanced`), or into
     `development/skills/_index.md` if that page fits. The authoring pointer
     stays a short link to the authoring docs.
   - `attachments`: verbs, gc and configuration go to `commands/attach.md`. The
     `attachments:` block goes to
     `development/task-format.md#nested-fields-artifacts-and-attachments`.
     Hash identity, blob location and one-commit-per-change go to a
     `development/` page only if neither of those owners fits.

   A new `development/` page gets `depth: [advanced]`, a title, a description
   and a weight that follow its neighbours, plus a link from its concept page's
   "See also". If `development/_index.md` carries a hand-curated list, it gets
   an entry there too. Use `relref` for every internal link. Keep each concept
   page's position in `concepts/_index.md` and its `**Next:**` footer
   unchanged.
4. **Fix the remaining pages.** Apply the inventory's violations to the other
   18 leaf pages and `_index.md`. That includes field enumerations under "What
   it is" (`tasks.md`: move the eight-field list to a link to
   `development/task-format.md#frontmatter-fields`, and define "frontmatter" in
   plain words), undefined terms on `main-concept` pages, and avoid-list prose.
   Same gate, same moved-fact table.
5. **Feed pilot lessons into the guide. This is the last planned guide
   change.** Make short additions to existing sections of
   `aitasks/metadata/doc_update_guide.md`, not new rule lists: for example, a
   concept page's mechanism-heavy section headings as a detection signal, or
   how to choose a concept page's `depth`. Add only what the pilot actually
   showed, and put each lesson into the guide's examples or contracts, not into
   ad-hoc page fixes. Keep the `## Reader levels` interface lines
   byte-identical, and keep prose-rule bullets as single-line bullets. Then run
   `bash tests/test_docs_review_contract.sh`, which also checks that no
   prose-rule bullet appears in the skill. Before this step, findings during
   editing are only working notes. The recorded review is Step 6.
6. **Final level/prose review, under the final guide.** Run
   `/aitask-docs-review <pages> --caller audit --budget <n>` on **every page
   this child edited or created**: the concept pages, the destination pages and
   the new `development/` pages.
   - Size `<n>` to cover the edited `main-concept` pages that are not among the
     eight after-report pages, such as `parent-child` and `task-lifecycle` if
     they are edited.
   - Fix the findings within the skill's invariants. A fix that cuts a fact
     follows the move rule and gets a moved-fact row.
   - Re-review each page a fix changed.
   - Record each page's final report line (`level=… prose=… reader=…`) and its
     unresolved findings in the plan.

   **The review runs only on final pages under the final policy:** if the guide
   changes again after this step starts (a review finding that turns out to be a
   guide gap), re-run Step 6 on every edited page, not only the one that
   prompted the change.
7. **After-reports.** Re-run Pre-phase step 1 (same persona, the same questions
   for each page) on the same eight pages, now in their final form. Record them
   under "Reader reports — after" with the counts, next to the before counts.
   Child 8 compares them.
8. **Links.** Run `cd website && python3 check_links.py --build`, which must
   pass, and `python3 check_link_relevance.py`. Open every reported target that
   this child added or retargeted, and record its verdict. Also run
   `bash tests/test_website_doc_lists.sh`, because new `development/` pages may
   touch doc lists.
9. **Ledger close-out.** Re-check every ledger entry against HEAD. Now clean →
   audit it in this child (Steps 3–8 for that page). Still dirty → create the
   child `audit_deferred_pages_concepts` of t2258 with `--no-sibling-dep`,
   listing pages, violations and reasons. Final Implementation Notes record each
   entry's outcome (`audited` / `follow-up t2258_<n>`). An empty ledger is
   recorded as "ledger empty".

### Post-phase (risk mitigations)

1. [moved_fact_survival_check] An independent, claim-level check that no rule,
   condition or exception was lost, run before the commit.
   a. **Removed blocks.** For each edited concept page (and any other page this
      child cut text from), a scratch script in the scratchpad splits
      `git show HEAD:<page>` and the working version into blocks. A block is a
      paragraph, list item, table row, admonition or code block. The script
      lists every HEAD block that is not present byte-for-byte in the working
      version: removed or rewritten. **Every** such block is in scope, plain
      prose included. Example: `locks.md`'s "held across the whole critical
      section: through conflict resolution, through the post-merge verification
      run, and through cleanup" and "nothing releases this lock automatically".
   b. **Independent comparison.** A fresh sub-agent, which did not write the
      edits, gets for each source page the removed blocks verbatim plus the full
      current text of the source page and of every destination page that page's
      moved-fact rows name. It:
      - lists every claim in the removed blocks: each rule, condition,
        exception, consequence, scope limit and default;
      - classifies each claim as `preserved` (quote the sentence and give
        page#section, with every condition and exception intact), `weakened`
        (say which condition, exception or scope was lost) or `missing`.
   c. **Reconcile.** Every `weakened` or `missing` claim is fixed: restore it on
      the destination with its conditions, or on the source page if the level
      allows it. Otherwise record it `corrected` (wrong fact, with evidence from
      the code) or `dropped(reason)`. A `grep -F` of a claim's key tokens on the
      destination is supporting evidence only; a token match never counts as
      `preserved` without the sub-agent's quote.
   d. Re-run the sub-agent once on the fixed claims. Record per page: claims /
      preserved / fixed / corrected / dropped, plus the second-run result.
   e. A page changed in (c) goes back through Step 6 (level/prose review) and
      Step 8 (links). If it is one of the eight reader-test pages, its Step 7
      after-report is re-run, so every recorded report describes the committed
      text.

## Reader reports — before

(filled during implementation)

## Reader reports — after

(filled during implementation)

## Inventory

(filled during implementation, Step 1)

## Moved-fact table

(filled during implementation, Steps 3–4 and 6)

## Skipped-page ledger

(filled during implementation, Step 2)

## Verification

- The inventory, moved-fact table, before/after reports with counts, separation
  test result, review report lines and ledger outcomes are all in this plan.
- The boundary self-review reports (both runs) and the survival check's
  per-page claim counts (with no `weakened` / `missing` left) are recorded.
- Every recorded Step 6 report line and every after-report is for the committed
  text: no page changed after its last review.
- `cd website && python3 check_links.py --build` exits 0.
- `tests/test_docs_review_contract.sh` and `tests/test_website_doc_lists.sh`
  pass.
- Every concept leaf page has `depth:`. No `main-concept` concept page contains
  anything on the guide's `main-concept` exclusion list: exit codes, status
  lines, status vocabularies, internal paths, edge cases, outcome tables,
  config keys, timing values. No concept page has `###` under "What it is".
  Check with `grep -n '^### '` per page, plus review.
- The guide's `## Reader levels` interface lines are unchanged:
  `grep -c` of the three label lines and three persona lines.

## Risk

### Code-health risk: medium
- Facts move across about 15 pages (concept, command, workflow, new `development/` pages). A fact can be lost or land on the wrong page, and an anchor can break without anyone noticing · severity: medium · → mitigation: inline post-phase moved_fact_survival_check
- The guide's new detail-placement boundary is read on every `docs_updated` run and by children 4–7. Ambiguous wording would shift every later audit, and pages reviewed before the boundary lands would be judged under the old policy · severity: medium · → mitigation: inline pre-phase guide_boundary_self_review
- New `development/` pages could repeat what `commands/` reference pages already say · severity: low · → mitigation: none separate; Step 3 checks the owner before moving and links where it already states the fact

### Goal-achievement risk: medium
- A model acting as fresh reader is in effect an expert. The baseline may not tell long pages from controls, and then the before/after comparison proves nothing · severity: medium · → mitigation: inline pre-phase reader_test_baseline_and_control
- The scope may run out of session: six restructures, 18 page fixes, the guide and 17+ reader runs · severity: low · → mitigation: none separate; each restructured page ships on its own, and Step 4's fixes can be deferred to a tracked child if needed

### Planned mitigations
- timing: pre-phase | name: reader_test_baseline_and_control | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: fresh reader is in effect an expert | desc: carried from the parent plan; before/after reader reports on the six long pages with tasks/plans plus a compliant scratch control; stop and tune if no separation
- timing: post-phase | name: moved_fact_survival_check | type: documentation | priority: medium | effort: medium | inline_risk: low | added_complexity: low | addresses: facts lost or misplaced in moves | desc: every removed or rewritten block (prose included) of each edited page is compared claim by claim with its destinations by an independent sub-agent (preserved with quote / weakened / missing); fix, re-run once; token greps are supporting evidence only; changed pages are re-reviewed
- timing: pre-phase | name: guide_boundary_self_review | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: ambiguous detail-placement boundary in the guide; reviews under a superseded policy | desc: write the user's boundary into the guide before any page work; fresh sub-agent places 8 sample facts using only the changed passages; fix mismatches, re-run once, record both

Reassessed after inlining (one pre-phase added, one post-phase), and again after
the plan-review changes (boundary moved to the pre-phase, claim-level survival
check, final review after the last guide change): levels unchanged
(medium/medium).
Fact loss and boundary ambiguity are reduced, not removed, and the reader
persona's limits remain.

## Post-implementation

Step 9:
- review;
- commit the website and `aidocs/` files as
  `documentation: Audit and restructure the concept pages (t2258_3)`;
- commit the guide with `./.aitask-scripts/aitask_task_commit.sh`, naming its
  path;
- archive.

Step 8e notes, sent when the facts hold at the end of the work:
- t2258_7 (entry pages and `development/`): list the new `development/` pages
  and the guide's new boundary;
- t2258_4 and t2258_6: list the workflow, command and skill pages that received
  moved facts, so their audits know where those facts came from.
