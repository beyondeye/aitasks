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

Method: fresh-reader method of `aitask-docs-review` Step 4, run directly with
the `main-concept` persona ("You know git and a terminal and have never heard of
aitasks.") on every page whatever its `depth`. Sub-agent (general-purpose),
page text inline with frontmatter and shortcodes, no tools; answers first, then
the five follow-up questions in the same conversation (SendMessage). Reports
were extracted verbatim from the sub-agent transcripts by a script (no
retyping). Score = guessed terms + unneeded details, as counted by the reader.

### Run 1 (untuned procedure) — separation test FAILED

| Page | depth | guessed | unneeded | score |
|---|---|---|---|---|
| locks | main-concept | 28 | 13 | 41 |
| topic-anchoring | main-concept | 14 | 8 | **22** |
| gates | advanced | 18 | 21 | 39 |
| framework-session | advanced | 17 | 14 | 31 |
| skill-templating | intermediate | 21 | 21 | 42 |
| attachments | intermediate | 12 | 19 | 31 |
| tasks (control) | main-concept | 17 | 12 | 29 |
| plans (control) | main-concept | 15 | 10 | 25 |
| scratch Labels (compliant control) | main-concept | 4 | 5 | 9 |

`topic-anchoring` (22) scored below both controls (29, 25). Diagnosis:

1. The readers counted page chrome (frontmatter `weight` / `linkTitle` /
   `depth`, the See also list, the Next footer) as unneeded detail. That was
   8 of 12 items on `tasks` and 9 of 10 on `plans`, so short pages were
   inflated most.
2. The questions mirrored the pages' own sections. For topic-anchoring,
   "how do I make a task belong to a topic / a follow-up / change it" made the
   flag-level mechanism count as needed, which hid the signal.

**Tuning** (procedure only, `.claude/skills/aitask-docs-review/SKILL.md`
Step 4; contract test 71/71):
- questions are written from the page's title, `description` and the persona,
  before reading the body, and are reused for the re-test;
- the "details not needed" follow-up leaves out frontmatter and navigation.

### Run 2 (tuned procedure) — separation test PASSED

| Page | depth | guessed | unneeded | score |
|---|---|---|---|---|
| locks | main-concept | 27 | 26 | 53 |
| topic-anchoring | main-concept | 15 | 15 | 30 |
| gates | advanced | 17 | 24 | 41 |
| framework-session | advanced | 16 | 22 | 38 |
| skill-templating | intermediate | 21 | 20 | 41 |
| attachments | intermediate | 12 | 17 | 29 |
| tasks (control) | main-concept | 14 | 6 | 20 |
| plans (control) | main-concept | 14 | 5 | 19 |
| scratch Labels (compliant control) | main-concept | 4 | 5 | 9 |

- `locks` (53) and `topic-anchoring` (30) are each above both `tasks` (20) and
  `plans` (19). The scratch control (9) is the lowest.
- The four non-beginner long pages (29–41) are also above the controls.
- The separation comes mainly from unneeded details: 15–26 on the long pages,
  5–6 on the controls and the scratch page. Guessed terms separate less
  (12–27 against 14), because the controls also leave
  skill / TUI / archive / worktree undefined. That is a real `main-concept`
  violation on the controls, not noise.

**Questions used in run 2** (reused verbatim for the after-reports):
- locks: What is a lock in aitasks? / Why do agents need locks? / Do I have to do anything myself to lock a task? / What happens if two agents try to work on the same task? / What happens if an agent crashes while it holds a task? / How do I see or release a lock?
- topic-anchoring: What is a topic in aitasks? / Why group follow-up work this way instead of making child tasks? / How do I put a task in a topic? / Where do I see the tasks of a topic together? / Can I move a task to another topic later? / When should I not use a topic?
- gates: What is a gate? / What does it mean for a task to archive? / How does a task get its gates? / Can a task archive while one of its gates has not passed? / What decides which gates are enforced on a task? / Why is the enforced set fixed when the task is picked? / What do I do when a gate fails?
- framework-session: What is a framework session? / What does freezing an agent mean? / What does restoring an agent mean, and what do I get back? / Do I need to manage these records myself? / What happens to the records if my machine or tmux restarts? / How do I restore a frozen agent?
- skill-templating: What is a profile-aware skill? / What is a profile? / Why does a skill need different variants? / How do I run a skill with a given profile? / Do I need to do anything with the generated variants? / Does any of this matter to me if I only use skills and never write them?
- attachments: What is an attachment? / Why would I attach a file to a task? / How do I attach a file and get it back later? / What does "identified by their hash" mean for me as a user? / What happens to the attachment if I delete the original file? / When are attached files actually deleted?
- tasks: What is a task in aitasks? / What is YAML frontmatter, and what does it hold here? / Where do tasks live? / How do I create a task? / Why keep tasks as files in git? / Who reads and changes task files?
- plans: What is a plan? / Who writes a plan, and when? / How do I approve a plan? / Where are plans kept? / What happens to a plan after the work is done? / Do I ever write a plan myself?
- scratch Labels: What is a label? / Why would I use labels? / How do I add a label to a task? / How do I find the tasks that carry a label? / Can a task have several labels?

The scratch control page (written for this test, not on the site):
`control_labels.md`, 37 lines. Its text is repeated in full in the run-2
answers prompt, and its findings (no command named for adding or filtering
labels, "the project's list" unexplained) are real slips in the control.

### Verbatim reports

#### Run 1 (untuned): `locks.md` — guessed terms 28, unneeded details 13, score 41

**Answers** (verbatim):

> 1. A task lock is an atomic claim on one task ID, recorded on a dedicated `aitask-locks` git branch, with the owner's email, hostname, a timestamp and the agent session's process. It stops two sessions from picking the same task at the same time and producing conflicting branches, commits or archival records.
>
> 2. No. If a different owner holds the lock, from any host, their pick is refused with `LOCK_FAILED`, which names you as the owner. The lock stays held until the task is archived, aborted or explicitly unlocked.
>
> 3. No, not while both are running. A pick from a second, still-running session on the same host is refused before anything changes, and you are asked whether to leave the task alone or force-claim it. The same email does not count as the same worker, because the lock excludes sessions rather than people.
>
> 4. Yes. If the crashed session is "provably gone", picking the task again (with `/aitask-pick`, I assume) claims it and shows a crash-recovery prompt. If the framework cannot tell whether that session is still alive, the pick is refused; you can then choose the force option or run `ait lock --unlock <task_id>`. The page only links to a crash-recovery workflow for the details, so what the prompt asks is my guess.
>
> 5. The merge mutex is one global lock per repository. It lets only one task at a time run its end-of-task merge (merging the finished task branch into its output branch), because that merge runs in the shared repository root. It matters when several tasks finish around the same time, since a second merge waits in a queue. It also matters if a session dies mid-merge: the lock is never released automatically, so no other task can merge until you clear it.
>
> 6. No. `/aitask-pick` and the board TUI take and release task locks automatically, and the task workflow takes and releases the merge mutex around the merge. One exception: outside tmux you must set `AIT_AGENT_PID` correctly, or the merge is refused with `NO_SESSION_ANCHOR`.
>
> 7. Run `./.aitask-scripts/aitask_merge_task.sh status` to see who holds it; `ait lock` does not cover the merge mutex. If status reports a leaked guard, remove it with `rmdir` (never `rm -rf`). Then run `force-release` with no flags as a dry run, and run the armed command it prints exactly as printed. It refuses to break a holder whose session is still alive, and it tells you whether `--abort-merge` or `--reset-hard` is needed.
>
> 8. For task locks, `ait lock` can list the current locks, and the lock data lives on the `aitask-locks` git branch. For the merge mutex, use `./.aitask-scripts/aitask_merge_task.sh status`. The page does not give the exact `ait lock` subcommand for listing (my guess: `ait lock --list`).
>
> Where I stumbled as a newcomer:
> - "Skill", "`/aitask-pick`", "agent session/pane", "output branch" and "worktree" are used without explanation. I could not tell whether `/aitask-pick` is something I type, or what a "session" is apart from a tmux pane.
> - The phrases "pre-anchor lock", "ownership guard" and "anomaly prompt" are opaque.
> - Detail on `AIT_AGENT_PID` and the residue flags is heavy for a concept page.

**Follow-up report** (verbatim):

> Follow-up answers about the Locks page, from the page text alone, as before:
>
> **1. What was ambiguous**
> - **What "session" means.** I could not tell whether it is a tmux pane, one agent process, or something wider. The whole outcome table depends on it.
> - **Who runs `ait lock --unlock <task_id>`, and where.** The page says to run it "in the session that is holding it", but that session may belong to another window, or may be the one that crashed.
> - **How "provably gone" differs from "liveness cannot be established".** I could not predict which one a crash produces.
> - **What "Stale locks can be force-unlocked, optionally with a confirmation prompt" means.** I could not tell what makes a lock stale, who sets the "optionally", or whether this is the same thing as "force-claim" in the table.
> - **How a refused merge relates to "keep waiting".** When the wait budget runs out, "the merge is refused, and you choose whether to keep waiting or stop". I could not tell whether it is refused or paused.
> - **When the task lock is released.** It says "only releases it on archival, abort, or explicit unlock", but several table rows let a new session claim a held lock. I could not tell whether that claim counts as a release.
> - **Which `ait lock` subcommands exist.** "List current locks" and "clean up stuck locks" are named as operations without the syntax.
> - **What `force-release` is called on each side.** The same word is used for `ait lock` ("force-release a stale lock") and for the merge broker's `force-release`, so the two are easy to mix up.
> - **What `status` reports as a "leaked guard".** The page never says what it looks like or where it lives, so the `rmdir` step has no target.
>
> **2. What the page assumed I already knew**
> - That aitasks runs AI coding agents, which it calls skills, launched with slash commands such as `/aitask-pick`.
> - That each task gets its own branch and worktree, and is later merged into an "output branch".
> - That agents run in tmux panes, and that this is the normal setup.
> - What a task is, and what archiving one does.
> - That a "board TUI" exists, and what "the task workflow" is.
> - That the repo has a separate `aitask-locks` branch that gets pushed and fetched. The git branching model is only linked.
> - That I know what Claude Web and `/aitask-web-merge` are.
> - That I can read git-internals vocabulary (`MERGE_HEAD`, an unmerged index, a dirty tree) and know what `--reset-hard` costs.
> - That "multi-PC" use, with one person on several machines, is a normal setup.
>
> **3. Terms whose meaning I had to guess**
> 1. skill
> 2. `/aitask-pick`
> 3. agent session
> 4. agent pane
> 5. session anchor / anchor process
> 6. pre-anchor lock
> 7. ownership guard
> 8. resume / re-pick
> 9. crash-recovery prompt
> 10. multi-PC reclaim prompt
> 11. anomaly prompt
> 12. archival
> 13. abort (of a task)
> 14. task branch / output branch
> 15. worktree (as aitasks uses it)
> 16. end-of-task merge
> 17. merge-approval prompt
> 18. wait budget
> 19. merge broker
> 20. leaked guard
> 21. residue (working-tree residue)
> 22. armed command / token pinning the holder
> 23. post-merge verification run
> 24. conflict-parked merge
> 25. board TUI
> 26. task workflow
> 27. Claude Web merge path
> 28. liveness verdict
>
> **4. Details I did not need to answer the questions**
> 1. The exact fields a lock records (hostname, timestamp, session process).
> 2. The "idempotent" note about resume, re-pick and the ownership guard.
> 3. The pre-anchor / outside-tmux row and the "boundary of the guarantee" paragraph.
> 4. The reasoning that the mutex is global rather than per-branch.
> 5. "The reservation outlives the command" (anchoring to the session rather than the process; holding across conflict resolution and verification).
> 6. The two `AIT_AGENT_PID` failure directions (a PID that outlives the session, a PID that dies early).
> 7. Why `rmdir` and not `rm -rf` (emptiness as proof).
> 8. The "three properties make this ladder terminate" block.
> 9. The `--abort-merge` versus `--reset-hard` residue details.
> 10. The note that `/aitask-web-merge` and hand-run `git merge` do not take the mutex, plus its closing warning.
> 11. The "backend-free, routed through git" rationale.
> 12. The paragraph on why the merge mutex exists (index races, half-resolved work absorbed into the next commit).
> 13. The See-also list, including the `ait note` live-delivery link, and the "Next: Shadow agent" link.
>
> **5. Contradictions within the page**
> - **Automatic release.** "Nothing releases this lock automatically" and "a session that dies mid-merge leaves it held" clash with the table row where a provably gone holder is "Reclaimed, and the merge proceeds", with no human involved. That is an automatic takeover. It is probably a distinction between releasing and reclaiming, but it reads as a contradiction.
> - **When the task lock is released.** "Only releases it on archival, abort, or explicit unlock" sits awkwardly with the rows where a provably gone, other-host or pre-anchor holder is simply "Claimed" by the next pick.
> - **A refused merge that keeps waiting.** "The merge is refused, and you choose whether to keep waiting" describes a refusal that can carry on waiting.
> - **Unequal "cannot tell" handling.** "The last two rows apply the same rule as the task lock" is not quite true. For the task lock, "cannot tell" can be overridden at the prompt. For the mutex, it is left alone, and clearing it needs the manual ladder.
> - **Force vocabulary.** "Force-unlock", "force-claim", "force option" and two different "force-release" commands (`ait lock` and the merge broker) are used without saying whether they are the same action. This is a naming inconsistency rather than a contradiction of fact.
>
> GUESSED_TERMS=28 UNNEEDED_DETAILS=13

#### Run 1 (untuned): `topic-anchoring.md` — guessed terms 14, unneeded details 8, score 22

**Answers** (verbatim):

> Answers, using only the page text:
>
> 1. Topic anchoring groups related tasks that share a subject, such as follow-ups found while working on a feature, so they sit together for triage and review. You get this without building a parent-child tree. On the board, those tasks are clustered together in the By-Topic view.
>
> 2. A parent with children is a strict decomposition: one larger piece of work is split into ordered child tasks that share the parent's lifecycle. Anchored tasks only share a grouping key. Each one can be planned, picked, implemented and archived on its own. The two also overlap: a child automatically joins its parent's topic.
>
> 3. Pass `--anchor <id>` when you create the task, for example `./.aitask-scripts/aitask_create.sh --batch --commit --name ... --anchor 130 --desc "..."`. The id can be written `130` or `t130`; both are stored as `anchor: 130`. The target task must exist, but it may already be completed or archived.
>
> 4. With `--followup-of <source_id>`, the new task always joins the source's root topic, never the source itself, so chains never form. If the source has an `anchor`, the new task gets the same value. If the source is a child without an anchor (e.g. `130_2`), the new task gets the parent (`130`). If the source is a parent without an anchor, the new task gets that parent. The page doesn't cover a source that is a plain standalone task, neither parent nor child. My guess is that the source becomes the root.
>
> 5. Yes. Run `./.aitask-scripts/aitask_update.sh --batch 180 --anchor 130` to move task 180 to another topic. Run `--anchor ""` to make it its own root again. You can also edit the anchor field on the task detail screen in the board.
>
> 6. In the board TUI, press `y` to switch to the By-Topic view. A topic with two or more visible tasks gets its own lane, named after its root task. Topics with only one task go into a trailing `Ungrouped` lane. The page doesn't say how to open the board or what "visible" means. My guess: something like `ait board`, and "visible" means not hidden by a filter.
>
> 7. Use a topic when tasks should sit near each other but stay independent. Use a label for broad filtering across many unrelated topics, such as `ui` or `docs`. Use `depends` when one task cannot be implemented until another lands. They can be combined: a follow-up can be anchored to a feature topic and also depend on a bug fix.
>
> 8. Nothing breaks. Archived tasks remain valid roots, so new follow-ups can still anchor to the root. The root's id stays the lane key, and the lane label falls back to that id, so the remaining tasks keep clustering. One gap: the page talks about the "root", not the "first task". I'm assuming the first task is the root; the page never says whether a root has to be the first task in its topic.
>
> Things a newcomer would stumble on:
> - The page never explains how "topic root" relates to the first task in a topic.
> - Every example calls `./.aitask-scripts/aitask_*.sh` directly. A newcomer won't know whether an `ait` command does the same thing.
> - It never says how to open the board.
> - "Visible tasks" is never defined.
> - It never explains what happens to tasks anchored to a root that later gets anchored somewhere else itself.

**Follow-up report** (verbatim):

> Follow-up answers, from the page text alone:
>
> 1. What was ambiguous
> - "Topic root" versus "first task". The page never says whether the root has to be the first task in a topic, or how a task becomes a root other than by having no `anchor`.
> - "Anchorless child like `130_2`". The page also says a child created with `--parent` gets `anchor = P` stored, so it is unclear how a child ends up with no anchor at all.
> - Re-anchoring a root. If task 180 is a root with follow-ups and I set its anchor to 130, the page doesn't say whether its follow-ups move with it or form the chain that "never" happens.
> - "Two or more visible tasks". "Visible" is not defined: it could mean filtered, loaded or unarchived.
> - "Labelled by the root task when available". The page doesn't say what the label shows: the id, the name or the title.
> - A follow-up whose source is a plain standalone task, neither parent nor child, is not covered.
> - "Base view" suggests there are other kinds of view, but none are named.
>
> 2. What the page assumed I already knew
> - What an aitasks task is and how a task id is assigned.
> - That tasks are markdown files with YAML frontmatter.
> - How to open the board TUI.
> - What the task detail screen is and how to reach it.
> - What `--batch` and `--commit` do on the create script.
> - That `./.aitask-scripts/` is the place to run commands from, and whether an `ait` command does the same thing.
> - What implementation trails are.
> - The child id convention (`130_2`).
> - What "archived" means for a task.
>
> 3. Terms I had to guess the meaning of
> 1. topic root
> 2. topic key
> 3. lane
> 4. base view
> 5. visible task
> 6. implementation trail
> 7. "projection of recommended ordering"
> 8. parent lifecycle / "decomposed parent task"
> 9. "loaded in the current task set"
> 10. task detail screen
> 11. `--batch`
> 12. `--commit`
> 13. frontmatter, as aitasks uses it
> 14. the child id form `130_2`
>
> 4. Details I did not need to answer the questions
> 1. The whole paragraph comparing topics with implementation-trail membership.
> 2. The page frontmatter: `weight`, `linkTitle`, `depth`.
> 3. The YAML example's `priority`, `effort` and `status` fields.
> 4. The `--name`, `--issue-type` and `--desc` flags in the create examples.
> 5. That `--anchor` and `--followup-of` are mutually exclusive and that both are rejected together with `--parent`.
> 6. The "See also" list.
> 7. The "Next: Folded tasks" link.
> 8. The normalization of child ids to bare form (`130_2`).
>
> 5. Contradictions
> - Probably one, a mild one. "Children derive their topic from the parent", and a child created with `--parent P` stores `anchor = P` or `P.anchor`. Yet the follow-up section and the board section both speak of an "anchorless child" whose topic falls back to its parent. Either children don't always store an anchor, or that fallback never happens. The page doesn't say which.
> - One gap borders on a contradiction. "Follow-ups never form anchor chains" is guaranteed only at creation. The page itself shows `aitask_update.sh --anchor`, which looks able to create a chain by re-anchoring a root, and the page doesn't address this.
> - I found nothing else that conflicts.
>
> GUESSED_TERMS=14 UNNEEDED_DETAILS=8

#### Run 1 (untuned): `gates.md` — guessed terms 18, unneeded details 21, score 39

**Answers** (verbatim):

> 1. A gate is a named check that a task has to pass before it can be archived. Examples are a build that must pass, a green test suite, a completed risk evaluation, or a person's review sign-off. Gates sit next to the task's `status` and only matter while the task is `Implementing`.
>
> 2. A gate stops a task from archiving until each of these separate facts is true. One `status` field can't hold "build passed, review pending, docs not done". Some gates, the ones marked `blocks_dependents` such as build, tests and review/merge approval, also keep tasks that depend on this one blocked until they pass.
>
> 3. You declare them when you create the task with the batch `--gates` flag, or you let the execution profile's `default_gates` fill them in when the task has no `gates:` key. The page doesn't show the flag's exact syntax and sends me to the `/aitask-create` page. My guess is something like `--gates risk_evaluated,docs_updated`, or writing `gates: [...]` in the task's frontmatter by hand.
>
> 4. Normally no. A task with gates archives only when every enforced gate is satisfied, and the archive command refuses otherwise unless you explicitly override it. Gates the profile filtered out never block archival, and an approval whose code has changed since signing counts as not satisfied.
>
> 5. `gates:` is what the task asks for, written by you or by the profile. `active_gates` is what the framework actually enforces: the overlap between the requested gates and the profile's "ceiling". It is computed when you pick the task and you never edit it by hand. Gates you asked for that aren't enforced are listed in `active_gates_filtered`.
>
> 6. It depends on the kind of gate. For machine gates, a verifier program runs and its exit status is the verdict. Human gates need a real person, and an agent never approves them itself. Procedure gates like `docs_updated` are run as a skill by an attended agent.
>
> 7. In the task file itself, in an append-only `## Gate Runs` section. The latest entry for each gate gives its current state, and `pass` or `skip` both count as satisfied. The board also shows each in-flight task's gates against its enforced set, and `ait gates` can list their state. The page doesn't give the exact list command, so the exact command is a guess.
>
> 8. A failed machine gate is re-run up to `max_retries` more times. After that it reports itself "exhausted" and waits for a person. Human gates don't retry. The page doesn't say what that person should do next. My guess is fix the problem and re-run the gate with `ait gate` or `/aitask-run-gates`, or override at archive time.

**Follow-up report** (verbatim):

> **1. What was ambiguous**
> - The page never says what "archive" means: deleted, moved, or marked done.
> - "Pick" and "claim" are used for the same moment, but neither is defined, and I could not tell whether either is a command I run.
> - Gates are declared when the task is created, yet they "only come into play while the task is `Implementing`". I couldn't tell whether a gate can pass or fail before that.
> - The exact syntax of the `--gates` flag is not shown.
> - "Unless it is explicitly overridden": the page does not say how to override, or who may.
> - After a gate is "exhausted" it "waits for a person", but the page does not say what that person does: fix and re-run, reset the budget, or override.
> - "Each enforced gate unlocks the next one in the task's list": I couldn't tell which list that is, `gates:` or `active_gates`.
> - The page doesn't say who or what records `skip`, or who decides a gate is "not applicable".
> - Under a profile that records gates, the ledger also records workflow checkpoints the task did not declare. I couldn't tell whether those undeclared checkpoints can block archival.
> - "Anything that reads the enforced set checks parts 1 and 3" doesn't say which tools do this.
> - Procedure-backed gates are called "machine gates", but the headless engine can't run them, so it is unclear whether "ready machine gates run in parallel" includes them.
> - The page mentions both `ait gates` and `ait gate` without saying which subcommands belong to which.
>
> **2. What the page assumed I already knew**
> - What an execution profile is, and that you choose one per session.
> - The pick/claim workflow and what happens at archival.
> - That a task is a file with frontmatter fields plus markdown sections.
> - What "the board" is.
> - What a skill is, and the difference between an attended agent and a headless one.
> - What task dependents are, and what "unblocking" means.
> - That task data syncs across machines.
> - The task lifecycle statuses (`Implementing` and the others).
> - What risk evaluation is, and what a manual-verification task and its checklist are.
> - That "approval" and "sign" mean a recorded human action of some specific kind.
>
> **3. Terms I had to guess the meaning of**
> 1. archive
> 2. pick / claim
> 3. execution profile
> 4. ceiling
> 5. `rendered_gates`
> 6. attended / attended session / attended-only
> 7. headless gate engine
> 8. skill
> 9. verifier
> 10. `signal` / `signal_target`
> 11. re-materializes
> 12. dependents / unblock
> 13. board
> 14. in-flight
> 15. "a profile that records gates"
> 16. signature / sign (and how it is "bound to the code")
> 17. manual-verification task / its checklist
> 18. risk evaluation (`risk_evaluated`)
>
> **4. Details I did not need to answer the questions**
> 1. The digest format (three 12-character hashes joined by dots).
> 2. Which digest parts are checked, and the fallback to raw `gates:`.
> 3. The reasoning behind the direction of the fallback (over-block rather than under-block).
> 4. The `active_gates_profile` and `active_gates_digest` fields.
> 5. That the four `active_gates*` fields are always written together as one tuple.
> 6. That an empty enforced set is written as `[]` rather than left out.
> 7. That `gates: []` is an opt-out that is never backfilled.
> 8. Manual-verification tasks dropping gates they can't reach.
> 9. The stored tuple being cleared when the profile is missing or unreadable.
> 10. Re-picking an in-flight task derives the set afresh.
> 11. `plan_approved` being refused by `ait gate pass`.
> 12. The headless engine deferring procedure-backed gates.
> 13. The ledger's first-line format and attempt number.
> 14. The ledger witnessing workflow checkpoints for resume.
> 15. The full registry key table (`type`, `kind`, `timeout_seconds`, and the rest).
> 16. `ait gates sync-registry` and how it reconciles.
> 17. Unlock ordering (linear vs registry-driven, fan-out).
> 18. `max_parallel_gates`.
> 19. Only `fail` and `error` spending the retry budget.
> 20. `also_blocks_dependents`.
> 21. A dependent unblocking while the upstream task is still active.
>
> **5. Contradictions within the page**
> - **Main one:** the Archival section says "A gate the profile filtered out can never block archival." The digest section says the fallback to raw `gates:` "can enforce a gate the profile would have filtered — over-blocking until the next pick". Taken together, a filtered gate *can* block archival during a fallback. The second passage presents this as intended, but it contradicts the word "never" in the first.
> - **Tension:** procedure-backed gates are called "machine gates ... verified programmatically" and "ready machine gates run in parallel", yet the headless engine cannot run them and an attended agent has to.
> - **Tension:** "gates only come into play while the task is `Implementing`" against gates being declared at creation and `active_gates` being written at pick time. This is probably consistent (declaring vs enforcing), but it reads oddly.
> - **Tension:** Human gates "wait for a person", but `plan_approved` is "recorded from the interactive plan approval", and the page doesn't make clear that this approval is itself the person acting.
>
> GUESSED_TERMS=18 UNNEEDED_DETAILS=21

#### Run 1 (untuned): `framework-session.md` — guessed terms 17, unneeded details 14, score 31

**Answers** (verbatim):

> 1. A framework session is aitasks' own record of one code agent: which project and tmux window it belongs to, which task it is working on, which agent and model it is, the CLI session id it could be resumed from, and where it is in the freeze/restore lifecycle. There is one record per agent, covering every agent on the machine across all projects.
>
> 2. A tmux pane does not last. It dies when tmux restarts, and it gets recycled, renamed or split. So aitasks keeps "which agent is this" somewhere outside tmux. Because of that, you can end an agent's process and still bring it back later, including after a crash or a reboot.
>
> 3. No. The page says you rarely touch the store directly, and only `aitask_agent_sessions.sh` writes to it. The records are filled in by the freeze/restore workflow and by a SessionStart hook that `ait setup` installs. The page never says you must or may edit the file by hand. My guess is that you shouldn't.
>
> 4. The page never defines "freezing" outright, so this is partly inferred (a guess). Freezing seems to mean ending an agent's running process while keeping its record and a capture of its terminal output. A "Frozen Agent" viewer then sits in the pane in its place, and the agent can be restored later. The record is what makes this possible: it holds the agent's state (live → freezing → frozen) and the session id that a restore resumes from.
>
> 5. No. A record is identified by project root, window name and slot. The pane id and process id only count as its "location". After a tmux restart, the new pane id and process id are written onto the same record, so no duplicate record is created.
>
> 6. The records are in `~/.config/aitasks/agent_sessions.json` (mode 0600). A frozen agent's captured output is in `~/.config/aitasks/frozen/<id>/`, as `capture.ansi` (with colour) and `capture.txt` (plain text). You can move these with the `AITASKS_AGENT_SESSIONS_FILE` and `AITASKS_FROZEN_DIR` environment variables.
>
> 7. "Unverified" means nothing confirmed, within the `frozen.restore_ack_grace` time limit, that the resumed session is the one that was asked for. The restore is accepted only because the launched process is running in the pane. In that case the capture files are deliberately kept, whereas a verified restore deletes them. A matching hook report that arrives later can still upgrade it to verified.
>
> 8. The page doesn't give the steps. It points to the "Freeze and Restore Agents" workflow page and says `ait frozenagent` lists frozen agents and acts on them. My guess is that you run `ait frozenagent`, or use the frozen rows in `ait monitor` / `ait minimonitor`, and pick restore. The page also says that if a restore is refused, you can "re-pick its task" instead.

**Follow-up report** (verbatim):

> Answers to the follow-up questions, from the page text alone (persona: knows git and a terminal, has never heard of aitasks).
>
> **1. What was ambiguous**
> - **"Session" has several meanings.** The page talks about a "framework session", a CLI session id, a tmux session (implied) and "raw sessions". On top of that, one thing is called a "framework session", a "record" and "the store". I couldn't tell at first whether these are one thing or three.
> - **"Freezing" is never defined.** It is the central action the record exists for, yet the page only describes it through state names and storage locations.
> - **"The viewer" / "stand-in viewer".** It is unclear what this is, what it shows, or whether I interact with it. It is only named in See also ("Frozen Agent").
> - **"Re-pick its task".** This is offered as the fallback when a restore fails. I can't tell how it differs from a restore, or whether it loses the agent's conversation.
> - **Who triggers "drop" and "reconcile".** It is unclear whether they are commands I run or internal steps.
> - **`frozen.restore_ack_grace`.** I don't know where it is configured or what its default is.
> - **`capture_missing` cleanup.** If I delete a capture file, is my frozen agent gone for good? It reads that way, but it isn't stated as a warning.
> - **After a tmux restart.** Pane options "die with the pane", but the page doesn't say what puts `@aitask_record` back on the new pane.
> - **The diagram's two arrows back to `live`.** "hook acknowledgement, or liveness confirmation" is easy to misread until the verified/unverified section much further down.
> - **The depth label.** `depth: [advanced]` suggests it wasn't meant for me, but nothing on the page points a beginner elsewhere first.
>
> **2. What the page assumed I already knew**
> - tmux concepts: server, window, pane, pane id, pane options, splitting, respawning, reattaching.
> - What a "code agent" is, and the specific CLIs it mentions (Claude Code, Codex): their session ids, resuming, transcripts, TUI vs `codex exec`.
> - What a SessionStart hook is.
> - The Codex app-server daemon.
> - What "project" and "task" mean in aitasks, and what an agent "working a task" looks like.
> - The `ait` commands: `ait setup`, `ait monitor`, `ait minimonitor`, `ait frozenagent`.
> - Systems concepts: atomic replace, read-modify-write locking, nonce, lease, file modes 0600/0700, `/proc`, `lsof`.
> - The "IDE model" tmux layout and the "Locks" concept (linked, not explained).
>
> **3. Terms I had to guess the meaning of**
> 1. freeze / freezing
> 2. stand-in viewer / "the viewer"
> 3. slot
> 4. coordinator
> 5. lease
> 6. reconcile
> 7. drop
> 8. re-pick its task
> 9. raw sessions ("default agent for raw sessions")
> 10. launch overrides
> 11. Codex app-server daemon
> 12. maintenance tick
> 13. "fully enumerated" (project)
> 14. `frozen.restore_ack_grace`
> 15. generation ("one complete generation")
> 16. liveness confirmation
> 17. transcript / transcript path
>
> **4. Details I did not need to answer the questions**
> 1. The writer's lock around read-modify-write, the atomic replace, and the fact that readers take no lock.
> 2. The `@aitask_record` pane option and the two other pane options (frozen pane, booted viewer).
> 3. That `freezing`, `restoring` and `aborting` are transitional, and that `aborting` is owned by the failed restore attempt.
> 4. Operation leases: the nonce plus process id, and the 60-second rule.
> 5. Reconcile's rules for leaving leased records alone.
> 6. The hook's ancestor-pane check and the rule about Codex app-server reports being ignored.
> 7. Detecting which CLI owns a session from the shape of the transcript path (`projects/`, `rollout-…`).
> 8. Restore rules for hand-started agents (agent/model recovery, project default agent, refusal).
> 9. Nested agents inheriting identity, and the hook recording nothing on disagreement.
> 10. That the hook writes nothing into the agent's session and always exits successfully.
> 11. Codex verification via `/proc` / `lsof`, and the version numbers 0.163.0 and 0.153.4.
> 12. The cleanup-reasons table (`dead_window`, `dead_pane`, `capture_missing`).
> 13. Who runs cleanup (the monitor/minimonitor maintenance tick and the coordinator).
> 14. The See also and Next links (IDE model, Locks, Agent memory).
>
> **5. Contradictions within the page**
> I found no hard contradictions, but there are some tensions:
> - **Who writes the records.** "`aitask_agent_sessions.sh` is the only writer" sits awkwardly next to "the hook records the agent's session id into the record". This is consistent only if the hook calls that script, which the page doesn't say.
> - **Whether restore needs the hook.** "The hook … is what makes a later restore possible at all" conflicts with a hand-started Codex agent whose hook reports are ignored but which is still "restored by re-picking its task". "Restore" seems to be used in two senses.
> - **Removal rules.** "Transitional records are exempt entirely" from cleanup, yet "drop, from any state" removes a record. This is probably fine if drop is explicit rather than cleanup, but the page doesn't say so.
> - **Scope wording.** The description says "every running and frozen code agent", while the body says "every agent on the machine". These are probably equivalent, since every record is either live or frozen, but the wording differs.
>
> GUESSED_TERMS=17 UNNEEDED_DETAILS=14

#### Run 1 (untuned): `skill-templating.md` — guessed terms 21, unneeded details 21, score 42

**Answers** (verbatim):

> Answers, using only the page text and reading as someone who knows git and a terminal but has never heard of aitasks:
>
> 1. **What is a profile-aware skill?** It is a slash command, such as `/aitask-pick`, that has no single `SKILL.md`. It comes as two pieces: a Jinja template at `.claude/skills/<skill>/SKILL.md.j2`, and a small "stub" in each agent's discovery location. When you run the command, the stub works out the active execution profile, builds a variant of the skill for that skill, profile and agent, and then follows it. The page never says what a "skill" or an "execution profile" is in general; it only links to another page for profiles.
>
> 2. **Why render variants instead of one skill file?** The agent keeps re-reading `SKILL.md` while the skill runs, so rewriting that file per profile in the middle of a session would give torn, inconsistent reads. Each run therefore gets its own frozen copy. The template also lets one source produce different flows for the `default`, `fast` and `remote` profiles, instead of one file full of "if your profile sets X, skip this" prose. The page never says what `fast` or `remote` actually change.
>
> 3. **How do I run a skill with a specific profile?** Inside an agent session, type `/aitask-pick --profile fast 42`. From the shell, run `ait skillrun pick --profile fast 42`. In the `ait board` or `ait codeagent` launch dialog, use the Profile row and its `(E)dit` button. I was unsure why the shell form uses `pick` and not `aitask-pick`. My guess is that `skillrun` takes a short name with the `aitask-` prefix dropped, but the page doesn't say so.
>
> 4. **If I don't choose a profile, which one is used?** The stub checks `default_profiles.<short_name>` in `userconfig.yaml` (your personal setting) first, then the same key in `project_config.yaml` (the team setting), and asks you to pick one interactively if neither is set. The page doesn't say where these files live or what `<short_name>` is. My guess is a metadata directory such as `aitasks/metadata/` and a name like `pick`. It also doesn't say whether the profile named `default` is ever chosen automatically.
>
> 5. **Can I make a one-time change to a profile for a single run?** Yes, in two ways. `ait skillrun ... --profile-override <yaml|->` merges ad-hoc YAML on top of the chosen profile, writes it to a temporary gitignored `_skillrun_<unique>.yaml` and deletes it when the run ends. In the TUI, "Save as one-shot" does the same thing. The page doesn't show what the override YAML looks like; I guess `-` means read it from stdin. It also mentions no one-shot option for a slash command typed inside a session; my guess is there isn't one.
>
> 6. **Do I need to commit or edit the rendered files?** No. They are generated on demand, matched by gitignore globs (directory names ending in `-`), and should not be hand-edited or committed. The exception is "two skills" that ship committed pre-rendered `remote` variants for headless runs, but the page doesn't name them.
>
> 7. **Does it work the same with other code agents?** Yes. The page says the same flow runs for Codex, Gemini and OpenCode, and only the stub location and the rendered-output location differ (there is a table). Codex output gets an extra `-codex-` segment because its folder is shared with a future agent, `agy`. The step-by-step dispatch example only shows the Claude paths and `--agent claude`, so I had to work out the other agents' equivalents from the table.
>
> 8. **Where do I start writing my own profile-aware skill?** Write `.claude/skills/<skill>/SKILL.md.j2`, branching with `{% if profile.<key> %}` and `{% if agent == "..." %}`, add stubs for the other agents, and run `./.aitask-scripts/aitask_skill_verify.sh` before committing. Then read `aidocs/framework/stub-skill-pattern.md` and `skill_authoring_conventions.md`. The page itself doesn't show what a stub contains. It says to add stubs at "the other three agent surfaces", yet the dispatch section shows a committed Claude stub, so it's unclear whether I write the Claude stub too (I guess yes). "Goldens" and "dep closure" are never defined, so the rule to "regenerate goldens in the same commit" meant nothing to me.
>
> **Where I stumbled most:**
> - Terms used without being defined: execution profile, `<short_name>`, goldens, dep closure.
> - The `pick` / `aitask-pick` naming difference in question 3.
> - No sample stub or sample override YAML anywhere on the page.
> - The "two skills" with committed variants are not named.

**Follow-up report** (verbatim):

> Follow-up answers, from the page text only.
>
> **1. What was ambiguous**
> - `ait skillrun pick` versus `/aitask-pick`: the page never explains why the shell form drops the `aitask-` prefix, so the naming rule is unstated.
> - `default_profiles.<short_name>` does not say what `<short_name>` is (`pick`? `aitask-pick`?).
> - It never says where `userconfig.yaml` and `project_config.yaml` live. Only `aitasks/metadata/profiles/local/` is given as a path.
> - It doesn't say whether the profile called `default` is ever picked automatically, or whether you always end up at "Interactive selection".
> - `--profile-override <yaml|->`: the YAML format isn't shown, and `-` is unexplained (my guess is stdin).
> - "Live mode" is contrasted only with `--dry-run`. It is never defined.
> - "No-op when the rendered variant is already fresh": what makes a variant fresh, or stale, is never stated.
> - "Two skills currently ship pre-rendered remote variants": the two skills aren't named.
> - Authoring says "add profile-agnostic stubs at the other three agent surfaces", yet dispatch describes a committed Claude stub. It's unclear whether the author also writes the Claude stub.
> - The dispatch steps show only Claude paths and `--agent claude`. The commands for the other agents have to be inferred from the table.
> - The Gemini stub is a `.toml` under `.gemini/commands/` while the rendered output goes under `.gemini/skills/`. The page doesn't say whether Gemini really reads skills from there.
> - The meaning of `42` in the examples is never given.
>
> **2. What the page assumed I already knew**
> - What a "skill" and a slash command are, and that agents discover them through `SKILL.md` files in fixed folders.
> - What an execution profile is, and what `default`, `fast` and `remote` do. This is only linked, never summarized.
> - Jinja / minijinja template syntax (`{% if %}`, `{% raw %}`, macros, `{% from %}`).
> - The four agents named on the page: Claude Code, Codex, Gemini and OpenCode.
> - The other `ait` tools (`ait board`, `ait codeagent`, `ait settings`) and their screens.
> - The agent-string format and the `AIT_AGENT_STRING` / `DEFAULT_AGENT_STRING` environment variables.
> - That the arguments are task IDs.
> - Testing jargon: "goldens", "dep closure".
> - What "headless agent runs" are.
> - gitignore negation patterns.
>
> **3. Terms I had to guess the meaning of**
> 1. execution profile
> 2. what the `default` / `fast` / `remote` profiles actually change
> 3. stub
> 4. discovery surface
> 5. `<short_name>`
> 6. dep closure / "closure-`.md` file"
> 7. goldens
> 8. "fresh" (for a rendered variant)
> 9. live mode
> 10. headless agent runs
> 11. agent string (`<agent>/<model>`, `$AIT_AGENT_STRING`, `$DEFAULT_AGENT_STRING`)
> 12. `AgentCommandScreen`
> 13. `ProfileEditScreen`
> 14. user-layer override
> 15. `agent_shared_skills_root` predicate
> 16. NON-SKIPPABLE banner rule
> 17. stub-pattern markers
> 18. `agy`
> 19. `ait codeagent`
> 20. the argument `42`
> 21. profile keys (`default_email`, `create_worktree`, `plan_preference`, `post_plan_action`)
>
> **4. Details I did not need to answer the eight questions**
> 1. The engine's name (minijinja)
> 2. The per-agent argument variables (`ARGUMENTS`, `{{args}}`, `$ARGUMENTS`)
> 3. `$AIT_AGENT_STRING` / `$DEFAULT_AGENT_STRING` and `--agent-string`
> 4. `--dry-run`
> 5. The class names `AgentCommandScreen` / `ProfileEditScreen`
> 6. The "Save persistently" path and its shadowing of project profiles
> 7. One-shot files being pruned when at least 1 hour old at TUI startup
> 8. The script names and arguments `aitask_skill_resolve_profile.sh` / `aitask_skill_render.sh ... --agent claude`
> 9. Rendering the dep closure and rewriting cross-references
> 10. The render being a no-op when the variant is fresh
> 11. The reason for the `-codex-` segment, `agy`, and the `agent_shared_skills_root` predicate
> 12. The four literal `.gitignore` glob lines
> 13. The rule that authoring directory names must not end in `-`
> 14. The list of profile key names
> 15. The `aitask-wrap` Step 1b example
> 16. `{% raw %} … {% endraw %}`
> 17. What the verify script checks internally (every `.j2` × profile × agent, markers)
> 18. The `agent_runtime_guards_audit.md` reference
> 19. The GitHub URLs for the aidocs
> 20. The "See also" and "Next" links
> 21. The frontmatter (weight, depth, linkTitle)
>
> **5. Contradictions within the page**
> I found no hard contradictions, but there are three tensions:
> - "Add profile-agnostic stubs at the other three agent surfaces" reads as if Claude needs no stub. The dispatch section says the agent reads a committed stub at `.claude/skills/aitask-pick/SKILL.md`.
> - "Materializes a stable ... snapshot once per invocation" suggests a fresh render every run. Dispatch step 4 says the step is a no-op when the variant is already fresh.
> - "Do not ... commit them" sits next to two skills whose rendered variants are committed. The page states this as an exception, so it is not a real contradiction, but the skills aren't named.
>
> The naming difference (`pick` versus `aitask-pick`) is an inconsistency rather than a contradiction.
>
> GUESSED_TERMS=21 UNNEEDED_DETAILS=21

#### Run 1 (untuned): `attachments.md` — guessed terms 12, unneeded details 19, score 31

**Answers** (verbatim):

> Answers (based only on the page text):
>
> 1. An attachment is a file, such as a screenshot, log or PDF, stored with a task. Its identity is the SHA-256 hash of its bytes, and its name is only a label. The task file lists each one in an `attachments:` block in its YAML frontmatter, with hash, name, mime, size, added_at and backend.
>
> 2. Files that explain a task usually sit somewhere temporary, like a downloads folder, a scratch directory or a chat upload, so a task that only points at them loses them. Attaching copies the bytes into the "task data branch", so the file travels with the task and can be fetched for as long as the task exists.
>
> 3. Attach with `ait attach add 42 screenshot.png`, list with `ait attach ls 42`, and get it back with `ait attach get 42 screenshot.png --out /tmp/shot.png`. Here `42` means task t42. `get` checks the bytes against the recorded hash and refuses a corrupted copy.
>
> 4. No. `ait attach add` copies the bytes, so the attachment can still be fetched after the original is moved, edited or deleted.
>
> 5. No. Identical bytes are stored once: one blob with two references. Each task can give it its own name, because the name lives in the task file and not with the blob.
>
> 6. Nothing changes. An archived task still counts as a referrer, so its attachments are kept indefinitely and can still be listed and fetched. You just can't add new ones, because `ait attach add` refuses an archived task.
>
> 7. No. `ait attach rm` only removes the task's reference and the task-file entry; the blob stays. Blobs are deleted only by an explicit `ait attach gc`, and only when nothing references them. A blob that has a recorded orphan time is also kept until a grace window has passed (`attachments_gc_grace`, 30 days by default).
>
> 8. No. The block is written only by `ait attach add` and `ait attach rm`, which commit the blob, its ledger and the task file together. An entry edited by hand no longer matches them. The page doesn't say what actually happens if you do it anyway. My guess (it is a guess): later attach commands or fetches error out or behave inconsistently.
>
> Where I stumbled as a newcomer:
> - "Task data branch" and "task data worktree" (`.aitask-data/`) are used but never explained. I can't tell if this is a separate git branch, or whether I have to push it myself.
> - The page says a task never refers to an attachment by path, only by hash. But the `get` example uses the name `screenshot.png`, and it isn't clear whether `get` also takes a hash.
> - "Ledger", "artifact version" (in the gc rules) and "folding" are used with little or no explanation. They only get links.
> - The `42` argument presumably means task t42, but the page never says what form task IDs take.

**Follow-up report** (verbatim):

> Follow-up answers (from the page text only, no tools used):
>
> **1. What was ambiguous**
> - **How you name an attachment in commands.** The page stresses that a task never refers to an attachment by path, only by hash. But `ait attach get 42 screenshot.png` uses the name, and it isn't clear whether `get` or `rm` also take a hash.
> - **Task ID form.** The example passes `42`, while the prose says "t42". Does the command take `42`, `t42`, or both?
> - **Duplicate names.** `name` is "unique per task", but the page doesn't say what happens if you attach two different files with the same basename to one task: a refusal, a rename, or a name flag.
> - **The grace window.** It isn't clear whether the 30 days count from the recorded orphan time, or what "also kept" adds when the blob is already unreferenced.
> - **Other backends.** `backend` is a field, yet `local` is the only one `add` accepts. That suggests other backends exist (maybe via artifacts), but the page doesn't say.
> - **Deleting from the board.** "Hands them to any folded task the delete revives" is unclear: which task gets revived, and why?
> - **The cache entry.** "A link to the stored blob": a symlink, a hard link, something else?
> - **"Refuses to start".** Is that an error message with an exit code, or a prompt?
>
> **2. What the page assumed I already knew**
> - What a task is in aitasks, and that tasks are markdown files with YAML frontmatter.
> - That there is a separate "task data branch" and a "task data worktree" (`.aitask-data/`), and how they relate to my normal git branch (do I push it, and how?).
> - The `aitasks/` and `aiplans/` directories.
> - What archiving, folding and deleting a task from `ait board` mean.
> - What an "artifact" or "artifact version" is.
> - The `ait:` commit-message convention.
> - That the `ait` CLI is installed, and how its commands are invoked.
> - Content-addressed storage in general: blobs and sharding by hash prefix, which I knew from git.
>
> **3. Terms I had to guess the meaning of**
> 1. task data branch
> 2. task data worktree
> 3. reference ledger / ledger entry
> 4. backend
> 5. artifact version
> 6. folding / folded task / primary task
> 7. "the delete revives" (reviving a folded task)
> 8. archiving / archived task
> 9. `ait:` commit
> 10. attach lock
> 11. orphaned / orphan time
> 12. `aitasks/` and `aiplans/` (what lives there)
>
> **4. Details I did not need to answer the questions**
> 1. The example values in the YAML block.
> 2. "The `sha256:` prefix names the digest algorithm."
> 3. The "hash is the address" bullet: storage path and cache key derived from the hash, no lookup table.
> 4. "An edit to an attachment is a different attachment."
> 5. The field table's meanings for `mime`, `size`, `added_at` and `backend`, and its "belongs to" column.
> 6. `name` defaulting to the basename and being unique per task.
> 7. The `blobs/` and `meta/` directory layout and sharding by the first two hex digits.
> 8. `.attach.lock`.
> 9. `local` being the only backend, with no command to move between backends.
> 10. The per-machine cache path `~/.cache/ait/artifacts/<hash>` and its link behaviour.
> 11. The "One commit per change" section on the three paths committed together. Question 8 was answered from the block section's own sentence.
> 12. Refusing to start on uncommitted changes, and blobs being exempt from that check.
> 13. Partial-failure rollback and reporting.
> 14. The per-blob ledger avoiding contention, stated in two places.
> 15. Folding moving references to the primary task.
> 16. Deleting from `ait board` releasing or handing over references.
> 17. The detailed gc conditions: no artifact version pointing at the blob, no archived task listing its hash.
> 18. The "keying by content is what keeps it cheap" paragraph.
> 19. The See also and Next links.
>
> **5. Contradictions within the page**
> I found no hard contradictions, but two places read like tensions:
> - **Name vs hash.** "A task never refers to an attachment by path or URL. It refers to it by hash", and the name is "only a label". Yet every CLI example identifies the attachment by its name (`get 42 screenshot.png`). This probably means the name is looked up to find the hash within one task, but the page doesn't say so.
> - **"Archiving changes nothing".** The same bullet then says an archived task cannot gain attachments, because `ait attach add` refuses it. So archiving does change what you can do; it just doesn't change the references.
>
> The six-field count matches the table (two task fields, four blob fields). "Kept indefinitely" for archived tasks is consistent with the gc rule, since an archived task still counts as a referrer.
>
> GUESSED_TERMS=12 UNNEEDED_DETAILS=19

#### Run 1 (untuned): `tasks.md (control)` — guessed terms 17, unneeded details 12, score 29

**Answers** (verbatim):

> 1. A task is the basic unit of work in aitasks. It is a markdown file with a YAML frontmatter block at the top. The frontmatter holds structured metadata about the task, and the markdown body describes the work in free form.
>
> 2. Tasks live in the `aitasks/` directory and are committed to git like source code. Each file is named `t<N>_<short_name>.md`, for example `aitasks/t130_add_login.md`. The page never shows an actual file, so this is a guess: a `---`-delimited YAML block with keys like `priority: high` and `status: ...`, followed by a markdown description.
>
> 3. In git, every task's full history shows up in `git log`. Branches and worktrees can also carry their own task state. A code agent can read, write and reason about tasks with the same tools it uses for source code. The page also says the schema is kept small enough for an LLM to hold in context.
>
> 4. The most common way is `ait create`, usually launched from inside a TUI such as Board or Brainstorm. The page also names `/aitask-explore` and `/aitask-wrap` (create tasks from code) and `/aitask-pr-import` (import from a pull request). It says all of these just write a file into `aitasks/`, but it never gives an actual command line. My guess is that running `ait create` in the repo prompts for the details.
>
> 5. A task holds:
>    - prioritization: `priority`, `effort`
>    - scheduling and dependencies: `status`, `depends`, `boardcol`
>    - classification: `issue_type`, `labels`
>    - ownership: `assigned_to`
>    - "a long tail of fields the workflow writes for itself"
>    - the free-form markdown body describing the work
>
>    The page does not say what values these fields take. For example, I can't tell what `boardcol` holds, or whether `depends` is a list of task numbers (that part is a guess).
>
> 6. Yes. The page says every code agent skill works on the task files directly, and that agents can read, write and reason about tasks with their normal file tools. It also mentions that only one agent works on a task at a time (see Locks), but it doesn't explain how that is enforced.
>
> 7. In the Task File Format reference (`/docs/development/task-format`), which "documents every field" and includes worked examples.
>
> Reader notes (stumbles):
> - There is no example file on the page, so I had to guess what a task looks like.
> - "Code agent skill", "TUI" and the `/aitask-...` slash syntax are never explained. As a newcomer I can't tell what runs these or where I would type them.
> - I can't tell how `N` in `t<N>` is chosen (automatic? sequential?).
> - Field names like `boardcol` are listed without saying what they mean.
> - "Code-aware capture" is unclear.
>
> This reply ends my run, so I can't answer the follow-up questions in this conversation. Send them to a new reader with this page and my answers above.

**Follow-up report** (verbatim):

> Follow-up answers for the Tasks concept page. I used only the page text and no tools.
>
> **1. What was ambiguous**
> - How the `N` in `t<N>_<short_name>.md` is chosen. Is it automatic, sequential, or picked by hand?
> - "A long tail of fields the workflow writes for itself": which workflow, which fields, and may I edit them?
> - "Every CLI command, TUI, and code agent skill operates on those files directly." Does that mean I can also create or edit a task file by hand, or should I always go through `ait`?
> - "Branches and worktrees can carry their own task state." What happens when those branches merge? Do task files conflict?
> - "`ait create` (typically launched from inside a TUI like Board or Brainstorm)." Can I run it straight from the shell, and is the TUI route preferred?
> - "Code-aware capture" and "import flows": what exactly they do, and whether PRs are the only import source.
> - Brainstorm is named alongside Board, but only Board has a link, so I can't tell whether Brainstorm is a TUI or something else.
> - The fields are listed by name only. The page gives no values for `status`, `issue_type`, `effort`, `boardcol` or `assigned_to`, and doesn't say what format `depends` uses.
> - The "How to use" section opens with a pointer to the schema rather than a usage step.
> - "An approved task" (in the Plans see-also line): approved by whom, and how?
>
> **2. What the page assumed I already knew**
> - What aitasks / `ait` is, that it is installed, and that the repo is already set up for it.
> - What a TUI is, and what the Board and Brainstorm TUIs are.
> - What a "code agent" is, what a "skill" is, and where you type the `/aitask-...` slash commands.
> - What YAML frontmatter is and how it sits at the top of a markdown file.
> - What an LLM's "context" is.
> - What Kanban-style triage means.
> - How the task workflow runs overall: approval, plans, statuses, locks.
>
> **3. Terms I had to guess the meaning of**
> 1. TUI
> 2. code agent
> 3. code agent skill
> 4. the slash-prefixed names (`/aitask-explore`, `/aitask-wrap`, `/aitask-pr-import`)
> 5. Board
> 6. Brainstorm
> 7. code-aware capture
> 8. import flows
> 9. `boardcol`
> 10. `effort`
> 11. `depends` (its value format)
> 12. `issue_type` (its allowed values)
> 13. `status` (its allowed values)
> 14. "the workflow" (in "fields the workflow writes for itself")
> 15. Kanban-style triage
> 16. dependency resolution
> 17. "approved task" (in the Plans see-also line)
>
> **4. Details I did not need to answer the questions**
> 1. `weight: 10` in the frontmatter
> 2. `depth: [main-concept]` in the frontmatter
> 3. `linkTitle: "Tasks"` (repeats the title)
> 4. "expressive enough to drive prioritization, dependency resolution, and Kanban-style triage"
> 5. the Capturing ideas workflow link
> 6. the Create tasks from code workflow link
> 7. See also: Plans
> 8. See also: Parent and child tasks
> 9. See also: Task lifecycle
> 10. See also: Locks (I mentioned it in my answer to question 6, but the answer didn't need it)
> 11. the "Next: Plans" footer
> 12. the second mention of the Task File Format reference (it appears in both "What it is" and "How to use")
>
> **5. Contradictions on the page**
> - I found no direct contradictions.
> - There is one mild tension. The schema is called "intentionally small enough for an LLM to keep in context", but the same page also mentions "a long tail of fields the workflow writes for itself". A reader can't tell whether the schema is small or not.
> - There is also a gap that reads a little like a contradiction. The page says every creation route "just write[s] a file into `aitasks/`", which suggests writing the file by hand is fine, but it never says so.
>
> GUESSED_TERMS=17 UNNEEDED_DETAILS=12

#### Run 1 (untuned): `plans.md (control)` — guessed terms 15, unneeded details 10, score 25

**Answers** (verbatim):

> 1. A plan is a markdown file that serves as the implementation contract for one task. It describes what will be done and how, and it is written and approved before any code for that task is written.
>
> 2. The agent writes it during the "planning phase" of a skill such as `/aitask-pick`, and it comes before any coding. The user (the human running the agent, as I read it) approves it before any code is written. The page doesn't say how approval happens, whether that's a prompt, a command or an edit to the file. My guess is the agent asks in the conversation and waits for a yes.
>
> 3. No. Plans are produced as a side effect of running `/aitask-pick` or `/aitask-explore`, and the page says you "do not normally write the file by hand." The word "normally" suggests hand-writing is possible but unusual.
>
> 4. Plans are stored in the `aiplans/` directory. The filename mirrors the task's: task `aitasks/t130_add_login.md` has plan `aiplans/p130_add_login.md`, so you swap `t` for `p` and `aitasks/` for `aiplans/`. A child task's plan sits in a subfolder named after its parent, at `aiplans/p<parent>/p<parent>_<child>_<name>.md`.
>
> 5. It is archived and becomes the main long-term record of how that task was actually built. Later sibling tasks read it as their main source of context, and the Code Browser shows it when explaining changed code. The page doesn't say where archived plans go or what archiving does to the file. My guess is they move to something like `aiplans/archived/`.
>
> 6. A plan that lives only in the agent's session memory is lost when the session ends. Saving it as a file in `aiplans/` (and, I assume, in git) is what makes it a long-term record that later tasks and tools can read. It also gives the agent a fixed contract to follow and update.
>
> 7. A plan contains:
>    - a metadata header naming the task it implements, the worktree, the branch and the base branch
>    - a context summary
>    - a step-by-step implementation outline
>    - the critical files to be touched
>    - verification steps
>
>    While the work goes on, the plan is also updated with deviations, post-review changes and final implementation notes.
>
> Where I stumbled as a reader new to aitasks:
> - The page never says what a "skill" is, or where you type `/aitask-pick`. I guessed it's a command inside an AI coding agent, but that's not stated.
> - "Worktree" in the metadata header suggests each task may get its own git worktree, but the page doesn't explain this.
> - "Sibling tasks" only makes sense once you know about parent and child tasks.
> - "The user approves" says nothing about how approval happens.
> - "Verification protocol" is pointed to an external file without a one-line summary.

**Follow-up report** (verbatim):

> Follow-up answers (from the page text alone):
>
> 1. What was ambiguous
> - **Who "the user" is and how approval happens.** I assumed it means the human running the agent, but the page never says how they approve: a prompt, a command, or an edit to the file.
> - **"Approved once" against "update with deviations, post-review changes".** It's unclear whether a plan updated after approval needs approving again, and whether those updates still count as the contract.
> - **"A skill like `/aitask-pick`."** "Like" suggests other skills write plans too, but only `/aitask-explore` is named, and that only in the How-to-use section.
> - **Plans from `/aitask-explore`.** It's unclear whether these also go through the approve-before-code step.
> - **"Archived."** The page doesn't say where archived plans go, when archiving happens, or whether the file changes.
> - **Three kinds of "verification".** "Verification steps" (plan contents), "verification protocol" (defined elsewhere) and "plan verification" (feeds verified scores) may or may not be the same thing.
> - **The metadata header.** The page doesn't give its format (YAML frontmatter like tasks?), and doesn't say whether worktree and branch are always filled in.
> - **Who reads archived plans.** "Subsequent sibling tasks" could mean only siblings or any later task.
> - **Whether plans are committed to git.** The page implies it but doesn't say so.
> - **"Do not normally write the file by hand."** The page doesn't say when you would.
>
> 2. What the page assumed I already knew
> - What aitasks is, and that it pairs with an AI coding agent.
> - What a task is, the `aitasks/` directory, and the `t<N>_<name>.md` numbering.
> - What a "skill" is, and where you type `/aitask-pick` (inside a coding agent, I assume).
> - Parent/child task structure and the meaning of "sibling".
> - What the Code Browser is (a tool or UI, I assume).
> - Why a plan would record a worktree and a base branch, which suggests per-task worktrees or branches.
> - That agents have "session memory" that gets lost.
> - What "archiving" means in this system.
>
> 3. Every term whose meaning I had to guess
> 1. task (as an aitasks file)
> 2. skill
> 3. `/aitask-pick`
> 4. `/aitask-explore`
> 5. planning phase
> 6. worktree (in this context: per task?)
> 7. base branch (in this context)
> 8. child task / parent
> 9. sibling tasks
> 10. archived / archived plans
> 11. Code Browser
> 12. shared task-workflow skill
> 13. verification protocol
> 14. agent session memory
> 15. per-model reliability tracking / verified scores
>
> 4. Every detail I did not need to answer the questions
> 1. Frontmatter `weight: 20`
> 2. Frontmatter `linkTitle`
> 3. Frontmatter `depth: [main-concept]`
> 4. Frontmatter `description`, which repeats the body
> 5. The GitHub link to `task-workflow/planning.md`
> 6. See also: Tasks
> 7. See also: Agent memory
> 8. See also: Parent and child tasks
> 9. See also: Verified scores and "per-model reliability tracking"
> 10. The "Next: Parent and child tasks" link
>
> 5. Contradictions
> There are no outright contradictions, but there are some tensions:
> - **Fixed vs changing.** The plan is "approved before any code is written" and is "a concrete contract", yet it gets updated with deviations and post-review changes. It reads as both fixed and evolving.
> - **Who produces plans.** "What it is" names only `/aitask-pick` (with "like"), while "How to use" names `/aitask-pick` and `/aitask-explore`. That's not contradictory, but the two lists don't match.
> - **Verification.** "Verification steps" and "verification protocol" sit next to "plan verification" in See also without being linked to each other.
>
> GUESSED_TERMS=15 UNNEEDED_DETAILS=10

#### Run 1 (untuned): `scratch Labels page (compliant control)` — guessed terms 4, unneeded details 5, score 9

**Answers** (verbatim):

> 1. A label is a short tag, such as `ui` or `docs`, that you attach to a task. A task is one piece of work that aitasks tracks, kept as a small text file in your repository.
>
> 2. Labels let you pick out the tasks that touch the same area, for example every task about the user interface, even when they are spread across a project full of unrelated work. Adding a label does not change how those tasks are planned or ordered.
>
> 3. You can choose labels when you create a task, or add them later from the board, which is the aitasks screen that shows tasks as cards in columns. The page does not give the actual command, flag or key to press. My guess: an option on whatever command creates a task, or a key or menu on the board.
>
> 4. You filter the board by that label. The page does not say how to apply the filter, or whether you can filter from the terminal outside the board. My guess: a key or search box on the board.
>
> 5. Yes. The page says a task can carry several labels, and many tasks can share the same label.
>
> 6. No. The page points to a separate concept, "Topic anchoring", for grouping a few closely related tasks around one subject, while labels are tags that cut across the whole project. The page does not explain the difference beyond that. My guess: a topic group is a small, deliberate group of tasks, while a label is a loose tag that can cover any number of tasks.

**Follow-up report** (verbatim):

> 1. What was ambiguous
> - "add them later from the board": the page does not say how. It could be a key, a menu or an edit dialog.
> - "filter the board by that label": the page does not say how to apply or clear the filter, or whether you can filter by several labels at once.
> - "New labels are added to the project's list the first time you use them": the page does not say what or where this list is, whether it limits which labels you may use, or whether you can edit or remove entries.
> - How a label differs from topic anchoring: both are described as grouping "related" tasks, and the only stated difference is "across the whole project" versus "a few closely related tasks around one subject".
> - The page does not say whether you can remove or rename a label on a task.
> - The page does not say how labels are written: the allowed characters, case, or whether spaces are allowed.
>
> 2. What the page assumed I already knew
> - How to open the board and how to create a task. Neither is shown or linked from the "How to use" section.
> - That aitasks has a "project's list" of labels.
> - That tasks are "planned" and "ordered" in some specific way, which labels do not affect.
> - What topic anchoring is. It is only named in See also.
>
> 3. Terms I had to guess the meaning of
> - "the project's list" (of labels)
> - "planned" (as a step in aitasks)
> - "ordered" (how tasks are ordered, and by what)
> - "Topic anchoring"
>
> 4. Details I did not need to answer the questions
> - That a task is "kept as a small text file in your repository"
> - That the board shows tasks "as cards in columns"
> - "New labels are added to the project's list the first time you use them"
> - The See also link to Tasks
> - The "Next: Tasks" link
>
> 5. Contradictions
> - None. The closest thing is that the description ("find related tasks across the whole project") and the Topic anchoring entry ("grouping a few closely related tasks") use the same "related" wording without explaining the difference. That makes the two concepts unclear, but they do not contradict each other.
>
> GUESSED_TERMS=4 UNNEEDED_DETAILS=5

#### Run 2 (tuned): `locks.md` — guessed terms 27, unneeded details 26, score 53

**Answers** (verbatim):

> Fresh-reader answers (persona: knows git and a terminal, has never heard of aitasks). I used only the page text and no tools.
>
> 1. **What is a lock?** There are two. A "task lock" is a claim on a single task ID, stored on a git branch called `aitask-locks`. It records who owns the task (email, hostname, timestamp, agent session process). The "merge mutex" is one repo-wide lock that lets only one task at a time run its end-of-task merge. (Stumble: the page never says what a "task" or a "skill" is. I had to infer that a task is a unit of work an AI agent picks up.)
>
> 2. **Why do agents need locks?** Several PCs, developers or parallel agent sessions can share one repository. Without a lock, two sessions could pick the same task and produce conflicting branches, commits or archival records. The merge mutex is needed because the final merge runs in the shared repo root, not in a private worktree, so two merges at once would fight over the same index and working tree.
>
> 3. **Do I have to lock a task myself?** No. The "How to use" section says locks are normally invisible: `/aitask-pick` and the board TUI take and release them for you. (Stumble: this answer is at the very bottom. I read the whole dense first half believing I might have to manage locks by hand. And `/aitask-pick` is never explained. The slash suggests an agent command, but that is a guess.)
>
> 4. **What if two agents try the same task?** The second one is refused if the holder is a different owner, or is your own session that is still running or whose liveness can't be determined. A refused pick changes nothing, and you can force-claim at a prompt. It is only claimed if the holder is the same session, a session that is provably gone, a session on another host, or a lock that never recorded a process. (Stumble: the table distinguishes "owner" from "session", but I had to work that out. "Owner" seems to mean email, and "session" seems to mean one agent process or tmux pane.)
>
> 5. **What if an agent crashes while holding a task?** On the next pick, the dead session's task lock is detected as provably gone and is reclaimed, with a crash-recovery prompt. If it crashed mid-merge, the merge mutex stays held, because nothing releases it automatically. You have to clear it by hand with `./.aitask-scripts/aitask_merge_task.sh status`, then `force-release` (dry run first), then the armed command it prints. (Stumble: I can't tell how the framework decides a session is "provably gone" versus "cannot tell". My guess is it checks whether the recorded PID still exists.)
>
> 6. **How do I see or release a lock?** For task locks, use `ait lock`: list locks, check one task, force-release a stale lock, or clean up stuck ones. `ait lock --unlock <task_id>` is the one exact syntax given. For the merge mutex, `ait lock` does not apply. Use `aitask_merge_task.sh status` and `force-release` instead. (Stumble: the only exact `ait lock` syntax is `--unlock`. Listing and checking locks are deferred to the linked command page. Having two separate tools for two locks is confusing at first.)
>
> **Overall, as this reader:** the page puts expert material first: edge-case tables, PID anchoring, `AIT_AGENT_PID` failure modes, `rmdir` guards. The beginner takeaway ("it's automatic; use `ait lock` if stuck") comes at the end. Several terms are used without being defined: skill, `/aitask-pick`, board TUI, archival, worktree, output branch, session anchor, tmux pane as agent process.
>
> I'm ready for follow-up questions. This run ends with this report, though, so follow-ups would need to go to a new or continued agent.

**Follow-up report** (verbatim):

> Follow-up answers. I am still reading as someone who knows git and a terminal but has never heard of aitasks, and I used only the page text.
>
> **1. What was ambiguous**
> - How "owner", "you" and "session" relate. I took "owner" to mean the email address and "session" to mean one agent process, but the page never defines either.
> - What decides "provably gone" versus "liveness cannot be established". The page never says.
> - "Refreshed silently": I can't tell what gets refreshed (timestamp? the commit?).
> - "You, from another host → Claimed": it is unclear whether the agent on the other PC could still be running, and what happens to it if it is.
> - "run `ait lock --unlock <task_id>` in the session that is holding it": I can't tell how I would type a command into another agent's session.
> - How "stale" locks differ from "stuck" ones, and how "force-release a stale lock" differs from "clean up stuck locks".
> - Who "you" is in the merge-queue row ("you choose whether to keep waiting or stop"): the agent or the human.
> - Where the merge mutex lives: on a git branch like the task lock, or only locally. That decides whether "one global lock per repository" means per clone or across PCs.
> - How a lock recorded via git push/fetch can be "atomic" across hosts.
> - "Stale locks can be force-unlocked, optionally with a confirmation prompt": it doesn't say who chooses whether the prompt appears, or how.
> - What a "leaked guard" is, where it lives, and when `status` would report one.
> - How long the "wait budget" is, and whether it can be configured.
>
> **2. What the page assumed I already knew**
> - What aitasks is, and what a task and a task ID are.
> - What a "skill" is, and that `/aitask-pick` is a command you give to an AI agent.
> - What the board TUI is.
> - The task lifecycle: picking, the status change, archival, abort, resume, re-pick.
> - That each task runs in its own worktree on a task branch that gets merged into an "output branch".
> - That agents are normally started as tmux panes, one agent per pane.
> - What the "task workflow" and its end-of-task merge and post-merge verification steps are.
> - The `ait` CLI, and the `.aitask-scripts/` directory sitting in the repo.
> - What Claude Web and `/aitask-web-merge` are.
> - What the crash-recovery and multi-PC reclaim flows are.
> - Git internals like `MERGE_HEAD` and the difference between an unmerged index and a dirty tree. These are fine for my persona, but they are assumed.
>
> **3. Terms I had to guess** (27)
> 1. skill
> 2. `/aitask-pick`
> 3. board TUI
> 4. archival
> 5. abort (as a task operation)
> 6. owner
> 7. session / agent session
> 8. ownership guard
> 9. resume
> 10. re-pick
> 11. pre-anchor lock
> 12. session anchor / anchor process
> 13. anomaly prompt
> 14. multi-PC reclaim prompt
> 15. crash-recovery prompt
> 16. output branch
> 17. task branch
> 18. task workflow
> 19. liveness verdict
> 20. wait budget
> 21. merge-approval prompt
> 22. leaked guard
> 23. armed command
> 24. residue (working-tree residue)
> 25. post-merge verification run
> 26. merge broker
> 27. Claude Web merge path
>
> **4. Details I did not need to answer the six questions** (26)
> 1. The table row "You, from this same session → refreshed silently", plus its idempotency explanation.
> 2. The row "You, from another host → multi-PC reclaim prompt".
> 3. The row about a lock that never recorded a session process (the anomaly prompt).
> 4. "The last row is the boundary of the guarantee…"
> 5. The Note that `/aitask-web-merge` and hand-run `git checkout`/`git merge` don't take the mutex.
> 6. Why the mutex is global rather than per-branch.
> 7. In the queued row: that you are told which task you are waiting on, in the prompt and in progress output.
> 8. The wait budget running out, and the keep-waiting-or-stop choice.
> 9. "The last two rows apply the same rule…", the difference during recovery.
> 10. That taking, merging and releasing are three short-lived commands, so the reservation is anchored to the session.
> 11. That the reservation is held through conflict resolution, verification and cleanup, and why.
> 12. The `NO_SESSION_ANCHOR` refusal before anything is acquired.
> 13. The tmux-pane route for supplying the anchor.
> 14. `AIT_AGENT_PID`, and the requirement that it name the outliving session process.
> 15. That only "positive integer and exists now" is checked.
> 16. The failure mode where the PID outlives the session (stranded reservation).
> 17. The failure mode where the PID dies early (reclaim mid-merge).
> 18. The list of what `status` reports (anchor process, output branch, time taken).
> 19. Recovery step 2: clear a leaked guard with `rmdir`, not `rm -rf`, and why.
> 20. What the `force-release` dry run prints.
> 21. The token that pins the holder in the armed command.
> 22. `REFUSED_LIVE_HOLDER`: a live holder is never broken.
> 23. The two residue remedies, `--abort-merge` versus `--reset-hard`, and the mismatched-flag refusal.
> 24. "Failure is reported, not silent": the lock is kept and the reason named.
> 25. The warning not to run `/aitask-web-merge` while a task is at its merge step.
> 26. Why the lock goes through git and not a backend service (push/fetch distributes the state; force-unlock is just a commit).
>
> **5. Contradictions**
> - The merge mutex section says "**nothing releases this lock automatically**". The table and the next paragraph say a holder whose session is provably gone is "Reclaimed, and the merge proceeds", and that "the automatic path displaces" such a holder. That is an automatic release by takeover. Both may be meant (no release, but a takeover), but as written they clash.
> - The task lock "only releases it on archival, abort, or explicit unlock". The table, though, lets a new pick claim a lock whose session is provably gone, came from another host, or never recorded a process. That is a fourth way a lock stops being held, and the "only" list leaves it out.
> - "Locks are normally invisible" sits oddly next to the table's several prompts: force-claim, crash-recovery, multi-PC reclaim, anomaly, and the merge-wait choice. This is a mild tension rather than a strict contradiction.
> - No factual contradiction otherwise. One naming collision: "force-release" is both an `ait lock` operation and a merge-broker subcommand, even though the page insists `ait lock` doesn't cover the mutex.
>
> GUESSED_TERMS=27 UNNEEDED_DETAILS=26

#### Run 2 (tuned): `topic-anchoring.md` — guessed terms 15, unneeded details 15, score 30

**Answers** (verbatim):

> 1. A topic is a loose group of related tasks about the same subject. It is keyed by the id of one "root" task. Each member task stores that root id in an `anchor` frontmatter field, and the root task itself has no `anchor` line, so its own id is the key. It is not a dependency, a label or a parent-child relationship.
>
> 2. Child tasks share their parent's lifecycle: they are ordered pieces of one larger job that has been broken down. Tasks in a topic sit near each other for triage and review, but each can be planned, picked, implemented and archived on its own. A topic can also keep collecting follow-ups after its root task is archived.
>
> 3. When creating a task, pass `--anchor <root-id>` to `aitask_create.sh` if you know the root. Pass `--followup-of <source-id>` instead to take the topic of the task the work came from. You can't use both flags together, and neither works with `--parent`. You can also set the `anchor` field on an existing task with `aitask_update.sh --batch <id> --anchor <root-id>`, or from the task detail screen.
>
> 4. In the board TUI, press `y` to switch to the By-Topic view. Each topic with two or more visible tasks gets its own lane. Topics with only one task go into a trailing `Ungrouped` lane.
>
> 5. Yes. Run `aitask_update.sh --batch 180 --anchor 130` to move task 180 to topic 130, or edit the anchor field on the task detail screen. Running `--anchor ""` makes the task its own topic root again.
>
> 6. Don't use a topic when the work is one larger job that needs ordered subtasks sharing a lifecycle (use parent-child tasks), when one task can't start until another lands (use `depends`), or when you want broad filtering across unrelated subjects such as `ui` or `docs` (use labels). These can be combined, for example a follow-up that is anchored to a topic and also depends on a bug fix.
>
> Points I stumbled on as a fresh reader:
> - The page never shows a short `ait` command for this. All examples use `./.aitask-scripts/aitask_create.sh` and `aitask_update.sh`, so I couldn't tell whether that is the normal way to run them.
> - On the board, "a child's parent topic" falls back for a child with no `anchor`. But earlier the page says children always get an anchor when they are created, so it is unclear when that fallback applies. My guess is it covers older or hand-edited files.
> - I didn't know what the board TUI is or how to open it. The page assumes I already do.
> - The section on implementation trails assumes I know what a trail is. It is a distraction this early on the page.

**Follow-up report** (verbatim):

> **1. What was ambiguous**
> - **Children without an `anchor`.** The board view falls back to "a child's parent topic" when a child has no `anchor`. But "Children and re-anchoring" says every child gets an anchor when it is created. I can't tell when a child would lack one.
> - **"Two or more visible tasks."** The page doesn't say what makes a task visible: filters, status, or being loaded.
> - **Lane labels.** "Labelled by the root task when available" could mean the root's title, its name, or its id.
> - **Failed validation.** "Anchor targets are validated to exist" doesn't say what happens when the target is missing: an error, a warning, or a refused write.
> - **Moving a parent.** The page doesn't say whether re-anchoring a parent also moves its children.
> - **Anchor chains.** "Follow-ups never form anchor chains" is stated for `--followup-of`. It is unclear whether `--anchor` or `aitask_update.sh --anchor` also flattens to the root, or whether pointing at an anchored task creates a chain.
> - **Re-anchoring a child.** Children "derive their topic from the parent", yet the update command seems to work on any task. I can't tell whether a child can be moved to a different topic than its parent.
> - **"Anchorless parent".** I couldn't tell whether this means a task that has children, or any task without an `anchor`.
> - **How to run commands.** The page only shows `./.aitask-scripts/aitask_*.sh` scripts, not whether a shorter `ait` command exists.
>
> **2. What the page assumed I already knew**
> - What aitasks is: tasks as markdown files with YAML frontmatter.
> - The task id format: `t130` versus `130`, and child ids like `130_2`.
> - What the board TUI is and how to open it.
> - What a "base view" is, and that the board has other views.
> - What "archived" means for a task, and that a task can be "not loaded".
> - What the parent-child model is and what a "parent lifecycle" involves.
> - What the `depends` field and labels are.
> - What implementation trails are.
> - What the `--batch` and `--commit` flags do.
> - That a task detail screen exists and how to reach it.
> - The task workflow verbs "planned, picked, implemented, archived".
>
> **3. Terms whose meaning I had to guess**
> 1. board TUI
> 2. base view
> 3. lane
> 4. implementation trail
> 5. projection of recommended ordering
> 6. archived
> 7. parent lifecycle (and decomposed parent task)
> 8. `--batch`
> 9. `--commit`
> 10. the child id form `130_2`
> 11. picked
> 12. loaded in the current task set
> 13. visible task
> 14. task detail screen
> 15. anchor chain
>
> **4. Details I did not need to answer the questions**
> 1. The paragraph on topics versus trails: one topic per task, many trails per task, and a trail can span several topics.
> 2. "A trail is a projection of recommended ordering … never changes its anchor."
> 3. The example YAML frontmatter block.
> 4. Id normalization: `--anchor t130` and `--anchor 130` both store `130`.
> 5. Child ids use the same bare form, such as `130_2`.
> 6. Anchor targets are validated to exist.
> 7. The `--followup-of` flattening rules: source has an anchor, source is an anchorless child, source is an anchorless parent.
> 8. "Follow-ups never form anchor chains."
> 9. Child inheritance: `anchor = P.anchor`, otherwise `P`.
> 10. "A topic lane spans the parent, its children, and loose follow-up work."
> 11. The board's key order: `anchor`, then a child's parent topic, then the task's own id.
> 12. Lanes are labelled by the root task when it is available.
> 13. An archived or unloaded root keeps its lane key, and the label falls back to the id.
> 14. The extra flags in the example commands (`--name`, `--issue-type`, `--desc`, `--commit`).
> 15. `--anchor` and `--followup-of` are rejected together with `--parent`.
>
> **5. Contradictions within the page**
> - **Children without an anchor.** The board rule for anchorless children conflicts with the statement that every child gets `anchor = P.anchor` or `P` at creation. Either such children don't exist and the rule is dead, or the creation rule has exceptions that the page doesn't mention.
> - **Children versus re-anchoring.** "Children derive their topic from the parent" sits uneasily next to "edit the anchor directly" for any existing task. If a child can be re-anchored, it no longer derives its topic from its parent.
> - **"Not a parent-child relationship" versus inheritance.** The page says an anchor is not a parent-child relationship, but children get their anchor from the parent automatically. This is not a strict contradiction, but it can confuse a first-time reader.
>
> GUESSED_TERMS=15 UNNEEDED_DETAILS=15

#### Run 2 (tuned): `gates.md` — guessed terms 17, unneeded details 24, score 41

**Answers** (verbatim):

> Answers, using only the page text:
>
> 1. **What is a gate?** A gate is a named check a task must pass before it can archive. Examples are a build that must pass, green tests, a completed risk evaluation, or a person's sign-off. It is tracked separately from the task's `status` and only matters while the task is `Implementing`.
>
> 2. **What does it mean for a task to archive?** The page never defines "archive". It only implies it, through phrases like "archival reads the enforced gates to decide whether it is finished" and "the archive command". *Guess:* archiving means marking the task as finished and moving it out of the active task list, probably once the work is committed.
>
> 3. **How does a task get its gates?** You declare them in the task's `gates:` field when you create it, for example with the batch `--gates` flag. If the task has no `gates:` key at all, the execution profile's `default_gates` fill it in. An explicit `gates: []` means "no gates" and is never filled in. Then, when the task is picked, the framework works out the enforced set (`active_gates`) from those declared gates.
>
> 4. **Can a task archive while one of its gates has not passed?** Yes in three cases: the gate was filtered out by the profile (listed in `active_gates_filtered`), its latest result is `skip` (which counts as satisfied), or someone explicitly overrides the archive command. Otherwise the archive command refuses while any enforced gate is unmet, including a human approval whose signature no longer matches the code. The page does not say how to override. *Guess:* a flag on the archive command.
>
> 5. **What decides which gates are enforced on a task?** The enforced set is the overlap between the task's declared `gates:` and the profile's "ceiling" (`rendered_gates`, which defaults to `default_gates`). It is computed when the task is picked. A manual-verification task also drops gates its checklist cannot reach. If the stored digest shows that `gates:` or `active_gates` was edited after the pick, enforcement falls back to the raw `gates:` field until the next pick.
>
> 6. **Why is the enforced set fixed when the task is picked?** The profile is chosen per session, so the same task could be picked under different profiles on different days. Fixing the set at pick time means everything that enforces gates sees the same answer for the whole session. A profile change then takes effect at the next pick instead of halfway through.
>
> 7. **What do I do when a gate fails?** The page only partly says. A failed machine gate is re-run up to `max_retries` times. Once that budget is spent, it reports itself exhausted and "waits for a person", but the page does not say what that person should do. *Guess:* read the run's log with `ait gate`, fix the problem, and re-run with `ait gates` or `/aitask-run-gates`. For a human approval that went stale because the code changed, re-sign it with `ait gate pass`.
>
> Where this reader got stuck:
> - "Archive" is never defined.
> - "Pick" and "claim" are used as if they mean the same thing, and neither is explained.
> - "Execution profile" appears in the first section, but it is only defined through a See-also link.
> - The page says an archive override exists but never names it.
> - There is no concrete recovery step for a failed or exhausted gate.
> - The "Declared intent versus the enforced set" section, with its four `active_gates*` fields and the digest, is heavy reading before the basic "How to use" section.

**Follow-up report** (verbatim):

> Follow-up answers, using only the page text:
>
> **1. What was ambiguous?**
> - **"Archive":** the page never says whether this means finishing the task, moving the file, committing, or something else.
> - **"Picked" and "claimed":** both words are used ("computed when the task is claimed — when you pick it"). They seem to mean the same thing, but neither is defined.
> - **The archive override:** the page says the archive command can be "explicitly overridden" but gives no flag, command or rule for who may do it.
> - **"Waits for a person":** after a gate's retries are used up, the page does not say what that person does. Fix and re-run? Reset the budget? Override?
> - **The ceiling:** `rendered_gates` "defaults to `default_gates`", so a task with no `gates:` key gets exactly the ceiling. It is unclear whether `rendered_gates` is usually wider than `default_gates`, and so whether declared gates outside the defaults get filtered.
> - **Linear order:** "each enforced gate unlocks the next one in the task's list" could mean the `gates:` list or the `active_gates` list.
> - **Re-picking an in-flight task:** the page says this re-derives the enforced set, but not whether the ledger or the retry budgets are affected.
> - **"Under a profile that records gates":** the page does not say which profiles do this or how you can tell.
> - **Manual-verification tasks:** "the gates its checklist can reach" has no rule for what "reach" means.
> - **Who records a `skip`:** the page does not say who or what decides a gate is "not applicable".
> - **"Gates only come into play while the task is `Implementing`":** it is unclear whether `gates:` can be edited, or has any effect, in other statuses.
>
> **2. What did the page assume you already knew?**
> - What aitasks is, and that tasks are markdown files with YAML frontmatter.
> - The task `status` values and the lifecycle they describe.
> - What an execution profile is, and that one is chosen per session.
> - What "picking" or "claiming" a task means, and what a "session" is.
> - The difference between an attended agent or session and a headless engine.
> - What a "skill" is and how an agent runs one.
> - What "the pick workflow" and "resuming an in-flight task" are.
> - That tasks can depend on each other (what "dependents" are, and what "unblock" means).
> - What "the board" is.
> - That a task file has body sections (such as `## Gate Runs`) the framework appends to.
> - Who signs human gates, and how a signature is tied to code.
>
> **3. Every term I had to guess the meaning of**
> 1. archive / archival
> 2. pick
> 3. claim
> 4. execution profile
> 5. session
> 6. attended (session / agent)
> 7. headless gate engine
> 8. skill
> 9. procedure (as in `kind: procedure`)
> 10. verifier
> 11. `rendered_gates`
> 12. dependents / unblock
> 13. pick workflow
> 14. in-flight
> 15. `signal` / `signal_target`
> 16. manual-verification task
> 17. the board
>
> **4. Every detail I did not need to answer the questions**
> 1. The `active_gates_profile` and `active_gates_digest` rows in the diagram.
> 2. The four `active_gates*` fields form one tuple and are always written together.
> 3. An empty enforced set is written as `[]` rather than left out.
> 4. The stored tuple is cleared when the profile is missing or unreadable.
> 5. The digest's format: three 12-character hashes joined by dots.
> 6. The three inputs the digest hashes.
> 7. The fallback's direction (over-blocking rather than under-enforcing), and that a profile change is caught by part 2 at the next pick.
> 8. The machine / human / procedure-backed classification of gates.
> 9. `plan_approved` is attended-only, and `ait gate pass` refuses it.
> 10. `docs_updated` is a skill, which the headless engine defers to an attended agent.
> 11. The ledger's format: an append-only `## Gate Runs` section, with each block's first line carrying gate, time, status and attempt number.
> 12. A gate's state comes from its latest ledger block, and no summary field exists.
> 13. The ledger also records workflow checkpoints, and resume and archival ask separate questions of it.
> 14. The registry's file path, `aitasks/metadata/gates.yaml`.
> 15. The registry key table, apart from `max_retries`.
> 16. `ait gates sync-registry` and how it reconciles the registry.
> 17. Only `fail` and `error` use up the retry budget, so re-running a gate that passed costs nothing.
> 18. Human gates do not retry.
> 19. The unlock ordering: linear versus registry-driven `unlocks`, and fan-out.
> 20. When a gate counts as ready to run, and `max_parallel_gates`.
> 21. The whole dependents-unblocking section: `blocks_dependents` and `also_blocks_dependents`.
> 22. "Why it exists": a single status field cannot hold several facts, and gates survive crashes and sync across machines.
> 23. "Why it exists": the rationale for separating declared gates from enforced ones.
> 24. The board shows each task's gates against its enforced set.
>
> **5. Does anything on the page contradict something else on the page?**
> - No direct contradictions. There are some tensions:
>   - Machine gates are "verified programmatically… its exit status is the verdict", yet procedure-backed gates are also called machine gates even though a skill run by an attended agent does the work.
>   - "The rest is the framework's job… archival waits for them" sounds fully automatic, but human gates need a person and procedure gates need an attended agent.
>   - `active_gates` is something "nobody edits by hand", yet the digest exists to catch hand edits. This is a rule plus a safeguard, so it is not really a contradiction.
>   - "Gates only come into play while the task is `Implementing`", yet the enforced set is written at pick time and the gates can release dependents while the task is "still active". This is probably consistent, but the boundaries of the `Implementing` status are not explained.
>
> GUESSED_TERMS=17 UNNEEDED_DETAILS=24

#### Run 2 (tuned): `framework-session.md` — guessed terms 16, unneeded details 22, score 38

**Answers** (verbatim):

> Fresh-reader answers (persona: knows git and a terminal, has never heard of aitasks). I used only the page text.
>
> 1. **What is a framework session?** It is the framework's own record of one code agent. The record holds the agent's project, tmux window, the task it is working, which agent and model it is, the CLI session id it could be resumed from, and its freeze/restore state. There is one record per agent, for every agent on the machine across all projects, and they are all kept in `~/.config/aitasks/agent_sessions.json`.
>
> 2. **What does freezing mean?** The page never defines it in one sentence; I pieced it together. Freezing seems to end the agent's process. Its terminal output is saved to `~/.config/aitasks/frozen/<id>/` (as `capture.ansi` and `capture.txt`), and a "stand-in viewer" takes over its pane. The page never says *why* I would freeze an agent. My guess, marked as a guess: to free resources or survive a shutdown without losing the agent.
>
> 3. **What does restoring mean, and what do I get back?** Restoring launches a replacement agent in the pane, which resumes the recorded CLI session with the same CLI. So I believe I get the agent's previous conversation back, though the page only says "resumes the session". If the restore is verified, the saved capture files are deleted; if it is unverified, they are kept. If the framework cannot tell which CLI the agent used, the restore is refused and the agent stays frozen. I could then "re-pick its task", but the page does not explain what that means.
>
> 4. **Do I need to manage these records myself?** No. The page says "You rarely address the store directly": one script writes it, and cleanup runs on its own from the `ait monitor` / `ait minimonitor` maintenance tick and after each freeze/restore. The one setup step I can see is `ait setup`, which installs the session hook that makes restore possible.
>
> 5. **What happens to the records on a machine or tmux restart?** The records are a file on disk, outside tmux, so they survive a tmux restart. The new pane id and process id are written onto the existing record rather than creating a duplicate. For a reboot, the page implies recovery works ("after the crash or the reboot you most want to recover from") but never says exactly what happens. One thing confused me: the cleanup table removes a *live* agent's record when its window is gone (`dead_window`). After a tmux restart the windows are gone, so I could not tell whether a live, non-frozen agent's record survives or is retired. Only frozen records clearly survive.
>
> 6. **How do I restore a frozen agent?** The page does not give the steps. It only points to the "Freeze and Restore Agents" workflow page, to `ait frozenagent` (which "lists and acts on" the records), and to the frozen rows in `ait monitor` / `ait minimonitor`. My guess, marked as a guess: run `ait frozenagent` and pick the agent, or select its frozen row in `ait monitor`.
>
> **Where this reader stumbled:**
> - Terms used without definition: "the framework" itself, "slot", "stand-in viewer", "coordinator", "re-pick its task", and `frozen.restore_ack_grace` (no hint where that setting lives).
> - Freeze is never defined in one plain sentence, and nothing says why I would want it.
> - The "How to use" section has no actual steps.
> - Most of the page is internal detail (leases, Codex hook timing, `/proc`/`lsof` checks) that does not help a first-time user.
> - It is unclear whether the `dead_window` cleanup applies after a tmux restart.

**Follow-up report** (verbatim):

> Follow-up answers, from the page text alone.
>
> **1. What was ambiguous**
> - What freezing does to the agent: whether the process is killed or paused. The page implies it is ended but never says so plainly.
> - Who starts a freeze or restore, and how. No command or key is given.
> - Whether a live, non-frozen agent's record survives a tmux restart. One passage says identity survives the restart, but the `dead_window` cleanup retires a live agent's record when its window is gone.
> - Whether a machine reboot behaves like a tmux restart.
> - What "re-pick its task" means as a fallback when a restore is refused.
> - What "verified" versus "unverified" means for me in practice, for example whether I have to delete a kept capture myself.
> - "the project's default agent for raw sessions": what a raw session is, and where that default is set.
> - "An agent started inside another agent inherits that agent's identity": in what situation this happens.
> - "Two more options mark a frozen pane and a stand-in viewer": these options are never named.
>
> **2. What the page assumed I already knew**
> - What aitasks ("the framework") is, and what a "task" is and what it means for an agent to be "working" one.
> - What a code agent is (Claude Code, Codex), and that its CLI sessions can be resumed by id.
> - tmux internals: pane options, slots and splits, respawn, reattach.
> - What a SessionStart hook is.
> - What Codex's app-server daemon is and when an agent runs through it.
> - The `ait` commands (`ait setup`, `ait monitor`, `ait minimonitor`, `ait frozenagent`) and what they show.
> - Where config keys such as `frozen.restore_ack_grace` live.
> - Lock, lease and nonce concepts, and atomic file replacement.
>
> **3. Terms I had to guess**
> 1. freeze / frozen agent (never defined in one sentence)
> 2. framework
> 3. code agent
> 4. task (as in "which task it is working")
> 5. slot
> 6. stand-in viewer
> 7. coordinator
> 8. reconcile
> 9. re-pick its task
> 10. raw sessions
> 11. `frozen.restore_ack_grace`
> 12. launch overrides
> 13. Codex app-server daemon
> 14. maintenance tick
> 15. drop
> 16. generation ("one complete generation")
>
> **4. Details I did not need to answer the six questions**
> 1. File modes `0600` and `0700`.
> 2. `aitask_agent_sessions.sh` being the only writer, with its lock and atomic replace.
> 3. Readers taking no lock and always seeing one complete generation.
> 4. The difference between `capture.ansi` (colour kept) and `capture.txt` (plain text).
> 5. The `@aitask_record` pane-option join, and pane options dying with the pane.
> 6. The two further pane options for a frozen pane and a booted stand-in.
> 7. The five-state diagram and the names of its transitions.
> 8. `aborting` being owned by the failed restore attempt.
> 9. Operation leases (nonce plus process id), and a coordinator that lost the race writing nothing.
> 10. The `reconcile` rules: leave a record alone while the owner is alive or the lease is under 60 seconds old, and the takeover rule.
> 11. The hook's ancestor-process check and the Codex app-server exclusion.
> 12. Identifying the CLI from transcript path shapes (`projects/`, `rollout-…`).
> 13. The rules for recovering agent and model, and the fallback to the default agent.
> 14. Identity inheritance for an agent inside an agent, and the hook recording nothing when identity and transcript disagree.
> 15. The restore acknowledgement through record id and nonce in the environment.
> 16. Codex verification through `/proc` or `lsof`, and the Codex version numbers 0.163.0 and 0.153.4.
> 17. The details of the liveness-confirmation fallback, including the case of a Codex resume routed through the app-server daemon.
> 18. A late hook report upgrading an unverified restore to verified.
> 19. The cleanup rules: retire only on positive evidence, never on a partial view, and exempt transitional records.
> 20. The `dead_pane` and `capture_missing` cleanup reasons.
> 21. The override environment variables table.
> 22. The hook writing nothing into the agent's session and always exiting successfully.
>
> **5. Contradictions within the page**
> I found no outright contradictions, only three tensions:
> - Identity "survives" a tmux restart, yet `dead_window` cleanup retires a live agent's record once its window is gone. A tmux restart removes the windows, so it is unclear which rule wins.
> - The page says the hook "is what makes a later restore possible at all", but the TUI of a resumed Codex agent fires the hook only at its first turn. It is unclear whether a hand-started Codex agent frozen before its first turn can be restored. (Codex timing is described only for resumed agents, so this is my inference.)
> - "A hook that reports in after the restore has settled is never refused" sits uneasily with "when the inherited identity and the transcript disagree, the hook records nothing". These are probably different stages, but the page does not say so.
>
> GUESSED_TERMS=16 UNNEEDED_DETAILS=22

#### Run 2 (tuned): `skill-templating.md` — guessed terms 21, unneeded details 20, score 41

**Answers** (verbatim):

> 1. **What is a profile-aware skill?** It's a slash command, such as `/aitask-pick`, that isn't stored as one fixed `SKILL.md`. It ships as a template (`SKILL.md.j2`) plus a small "stub". When you run the command, the stub works out which profile is active, builds a version of the skill for that profile and agent, and the agent then follows that version. The page never says what a "skill" is in the first place. My guess is that it's a markdown instruction file an AI coding agent reads when you type a slash command.
>
> 2. **What is a profile?** The page doesn't define it. It only links to "execution profile". From the clues (profiles named `default`, `fast` and `remote`, keys like `default_email`, `create_worktree`, `plan_preference` and `post_plan_action`, and YAML files under `aitasks/metadata/profiles/`), my guess is that a profile is a named set of settings. Those settings decide ahead of time how a skill's workflow behaves, such as which steps to skip and what to do after planning.
>
> 3. **Why does a skill need different variants?** Each profile needs a slightly different flow. Writing all of them into one file would mean lots of "if your profile sets X, skip this step" text. The file also can't be rewritten in place for each profile, because the agent re-reads it while the skill runs, and changing it mid-session gives inconsistent behaviour. So a separate fixed copy is built for each skill, profile and agent combination.
>
> 4. **How do I run a skill with a given profile?**
>    - Inside an agent session, add the flag: `/aitask-pick --profile fast 42`.
>    - From a terminal: `ait skillrun pick --profile fast 42`.
>    - From the `ait board` or `ait codeagent` launch dialog, use the Profile row.
>
>    If you don't pass `--profile`, it uses your personal default from `userconfig.yaml`, then the team default from `project_config.yaml`, and otherwise asks you to pick one.
>
> 5. **Do I need to do anything with the generated variants?** No. They're created automatically when needed and are already gitignored (folders whose names end in `-`). The page says not to edit them by hand or commit them.
>
> 6. **Does any of this matter if I only use skills and never write them?** Only the "how to run with a profile" part matters to me: the `--profile` flag, `ait skillrun`, the default-profile settings, and knowing to leave the `*-/` folders alone. The page never says plainly which sections are for users and which are for authors. My guess is that everything from "How dispatch works" onward is internals or authoring material I can skip.
>
> **Where a newcomer like me got stuck:**
> - "Skill" and "profile" are never defined on the page itself.
> - Several terms are used without explanation: "discovery surface", "dep closure", "goldens", "NON-SKIPPABLE banner".
> - `<short_name>` is never explained. `ait skillrun pick` uses `pick` where the slash command is `aitask-pick`, and I had to infer that this is the short name.
> - The page starts with internals (stubs, `.j2` templates, minijinja) before saying what a user actually does. I couldn't tell at first whether I needed to care about any of it.

**Follow-up report** (verbatim):

> **1. What was ambiguous?**
> - **What a profile controls.** The page links to "execution profile" but never says what one is. A few key names are its only hints.
> - **Which skills are profile-aware.** Only `/aitask-pick` is named. I can't tell whether every skill works this way or only some.
> - **`<short_name>` in `default_profiles.<short_name>`.** It isn't explained. `ait skillrun pick` vs `/aitask-pick` suggests the short name is `pick`, but I'm inferring that.
> - **What "Interactive selection" looks like.** The page doesn't say who asks or how.
> - **When a variant gets rebuilt.** One sentence says a snapshot is made "once per invocation". Another says rendering is "a no-op when the rendered variant is already fresh". "Fresh" isn't defined, so I don't know what triggers a rebuild.
> - **What `--profile-override <yaml|->` takes.** It could be a YAML string or a file path, and `-` presumably means stdin.
> - **Which default-agent variable wins.** The page names `$AIT_AGENT_STRING` and `$DEFAULT_AGENT_STRING` but not which takes precedence, or what an "agent string" looks like apart from `<agent>/<model>`.
> - **Where project profiles live.** "Save persistently" shadows "any same-name project profile", but the page only gives the path of the local layer.
> - **Which skills ship committed pre-rendered remote variants.** It says two skills do, but doesn't name them.
> - **What `42` means** in the example commands. I guessed a task number.
>
> **2. What did the page assume I already knew?**
> - What a "skill" or slash command is, and how coding agents find and read `SKILL.md` files.
> - The four agents (Claude, Codex, Gemini, OpenCode) and how each one handles commands and arguments, plus what "agy" is.
> - What execution profiles are and what they contain.
> - Jinja or minijinja template syntax.
> - The aitasks layout (`aitasks/metadata/...`) and where `userconfig.yaml` and `project_config.yaml` live.
> - The `ait` CLI and its parts: `ait board`, `ait codeagent`, `ait settings`, and what a TUI is in this context.
> - The task model, i.e. that "42" is a task ID.
> - The project's test and commit conventions: "goldens", stub-pattern markers, the NON-SKIPPABLE banner rule.
>
> **3. Terms whose meaning I had to guess**
> 1. skill
> 2. profile / execution profile
> 3. stub
> 4. discovery surface
> 5. dep closure / closure-`.md`
> 6. goldens
> 7. `<short_name>`
> 8. agent string
> 9. user-layer override
> 10. one-shot (override)
> 11. "fresh" (rendered variant)
> 12. headless agent runs
> 13. `AgentCommandScreen`
> 14. `ProfileEditScreen`
> 15. `agent_shared_skills_root` predicate
> 16. agy
> 17. stub-pattern markers
> 18. NON-SKIPPABLE banner rule
> 19. torn reads
> 20. template-completeness checks
> 21. `ait codeagent`
>
> **4. Details I didn't need for the questions** (frontmatter, See also, Next and the "Authoring references" link list are left out)
> 1. The name of the template engine (minijinja).
> 2. The argument variable for each agent (`ARGUMENTS`, `{{args}}`, `$ARGUMENTS`), and the fact that `--profile` is stripped before the rest is passed on.
> 3. The default-agent variables `$AIT_AGENT_STRING` / `$DEFAULT_AGENT_STRING` and the `--agent-string` override.
> 4. How `--profile-override` works: the `_skillrun_<unique>.yaml` temp file and its deletion on exit.
> 5. `--dry-run`.
> 6. The TUI screen class names (`AgentCommandScreen`, `ProfileEditScreen`) and the reuse from `ait settings`.
> 7. Where "Save persistently" and "Save as one-shot" write, and the cleanup of one-shot files older than an hour at startup.
> 8. The dispatch script names (`aitask_skill_resolve_profile.sh`, `aitask_skill_render.sh ... --agent claude`).
> 9. How rendering walks the dependency closure and rewrites cross-references.
> 10. That rendering is skipped when the variant is fresh.
> 11. The per-agent stub and variant location table.
> 12. The extra `-codex-` segment, why it exists (the shared root with agy), and the `agent_shared_skills_root` predicate.
> 13. The literal `.gitignore` glob lines.
> 14. The rule that authoring folder names must not end with `-`.
> 15. The two skills with pre-rendered remote variants that are exempted in `.gitignore`.
> 16. The two Jinja conditional patterns, including the `aitask-wrap` Step 1b example.
> 17. `{% raw %} … {% endraw %}`.
> 18. `aitask_skill_verify.sh` and what it checks.
> 19. The rule to regenerate goldens in the same commit.
> 20. That authors write the template against the Claude surface and then add stubs for the other three agents.
>
> **5. Does anything on the page contradict something else on the page?**
> - Nothing is a hard contradiction.
> - There is one tension. "Materializes a stable ... snapshot once per invocation" reads as if a variant is built on every run. "The whole step is a no-op when the rendered variant is already fresh" says it is often skipped.
> - There is also a near-contradiction. "Rendered files are autogenerated on demand; do not ... commit them" sits next to "two skills currently ship pre-rendered remote variants". The page does flag that as an intentional exception.
>
> GUESSED_TERMS=21 UNNEEDED_DETAILS=20

#### Run 2 (tuned): `attachments.md` — guessed terms 12, unneeded details 17, score 29

**Answers** (verbatim):

> 1. An attachment is a file, such as a screenshot, a log or a PDF, that is stored with a task. The SHA-256 hash of its bytes identifies it, and its name is only a label. The task file lists each attachment in an `attachments:` block in its frontmatter.
>
> 2. The files that explain a task, like a bug screenshot or a log, usually sit somewhere temporary (a downloads folder, a scratch directory, a chat upload). A task that only points at them loses them. Attaching copies the bytes into the task's storage, so they travel with the task and can be fetched for as long as it exists, active or archived.
>
> 3. You attach with `ait attach add 42 screenshot.png`, list with `ait attach ls 42`, and get it back with `ait attach get 42 screenshot.png --out /tmp/shot.png`. The page doesn't say whether `--out` is required or what happens without it. My guess is that without it the file goes to stdout or the current directory.
>
> 4. You never refer to the file by its path, so moving or deleting the original can't break anything. If you attach the same bytes twice, only one copy is stored. A fetch is checked against the hash, so a corrupted copy gives an error instead of a wrong file. You can't edit an attachment in place: changed bytes mean a new attachment. In practice you still use the name (e.g. `screenshot.png`) on the command line. The hash is the identity behind the scenes. That is my reading of the example commands; the page never says it outright.
>
> 5. Nothing happens to it. `ait attach` already copied the bytes, so the attachment can still be retrieved after the original is moved, edited or deleted.
>
> 6. Only when you run `ait attach gc` explicitly, and only for a blob nothing references any more: no ledger reference, no active or archived task listing its hash, and no "artifact version" pointing at it. A blob that became orphaned is also kept until a grace window has passed (`attachments_gc_grace`, 30 days by default). `ait attach rm` only removes the reference and never deletes the file. Archiving a task keeps its attachments forever.
>
> Where I stumbled as this reader:
> - "Task data branch" / "task data worktree" / `.aitask-data/` are never explained. I can't tell if attachments end up in my repo's history, on a separate branch, or get pushed to my remote.
> - "Artifact version" comes up in the gc rules with no explanation. I'm only guessing it's the subject of the "Next: Artifacts" page.
> - "Blob" and "ledger" are used without being defined, though I could work them out from context.
> - In `ait attach add 42`, it's not obvious that `42` means task t42. The comment explains it.
> - The page doesn't say whether `ait attach gc` asks for confirmation or has a dry-run mode, which matters because it permanently deletes files.
> - The "uncommitted changes" refusal confused me: which "task file or ledger file" would I have edited?

**Follow-up report** (verbatim):

> Answers to the follow-up questions, from the page text alone:
>
> **1. What was ambiguous**
> - **Where attachments end up in git.** The page never says whether the "task data branch" is a separate branch, whether it gets pushed with my normal `git push`, or whether it adds to my code repo's history.
> - **How `ait attach get` picks the file.** It takes a name (`screenshot.png`), yet the page insists a task never refers to an attachment by anything but its hash. It doesn't say whether I can pass a hash instead.
> - **Whether `--out` is optional.** The page doesn't say what happens without it.
> - **Which command copies the file.** The intro says "`ait attach` copies the file's bytes", with no verb. Later it's `ait attach add`.
> - **Re-adding a changed file under the same name.** Names are "unique per task", and an edit makes a new attachment. It's unclear whether re-adding is refused, replaces the old entry, or renames.
> - **The gc rules.**
>   - It's unclear whether a blob with no recorded orphan time can be deleted right away or is kept anyway.
>   - "Artifact version" is undefined.
>   - The page doesn't say why gc checks both the ledger and the task files.
>   - The page says "the command reference has the exact rules", so this summary may be incomplete.
> - **The uncommitted-changes refusal.** It's unclear when I would ever have uncommitted edits to a ledger file, given the block is "never hand-edited".
> - **Deleting a task.** The page only says what happens when a task is deleted "from `ait board`". It's unclear whether other ways to delete a task behave the same.
> - **Archived tasks.** It's unclear whether I fetch an archived task's attachment with the same task number.
>
> **2. What the page assumed I already knew**
> - That aitasks has numbered tasks, and that `42` means t42 (only the code comment hints at this).
> - That tasks are markdown files with YAML frontmatter.
> - That a separate "task data branch" or worktree (`.aitask-data/`) exists.
> - What archiving and folding a task mean.
> - What `ait board` is.
> - What "artifacts" are.
> - The `ait:` commit-message convention.
> - Content addressing, SHA-256 and git worktrees (I happen to know these).
>
> **3. Terms I had to guess**
> 1. task data branch
> 2. task data worktree
> 3. blob
> 4. reference ledger / ledger
> 5. backend
> 6. artifact version
> 7. folding / folded task
> 8. archiving / archived task
> 9. `ait:` commit
> 10. `ait board`
> 11. sharded
> 12. orphan time / grace window
>
> **4. Details I didn't need for the questions**
> 1. The exact field values in the YAML example.
> 2. The six-field table and which fields belong to the blob versus the task.
> 3. The `sha256:` prefix naming the digest algorithm.
> 4. The storage path and cache key being derived from the hash, so there is no lookup table.
> 5. The directory layout, sharded by the first two hex digits.
> 6. The `.attach.lock` file.
> 7. The per-machine cache at `~/.cache/ait/artifacts/<hash>`, and its being a link for the local backend.
> 8. `local` being the only backend, with no command to move an attachment to another.
> 9. The block never being hand-edited.
> 10. One commit per change, with blob, ledger and task file committed together.
> 11. The refusal when there are uncommitted changes, and blobs being exempt from that check.
> 12. Failed transactions restoring paths or reporting which ones they couldn't restore.
> 13. One ledger file per blob to avoid contention on the shared branch.
> 14. Archived tasks refusing new attachments.
> 15. Folding moving references to the primary task.
> 16. Deleting from `ait board` releasing references or handing them to a revived folded task.
> 17. The name defaulting to the file's basename and being unique per task.
>
> **5. Contradictions**
> Nothing on the page outright contradicts anything else. There are some mild tensions:
> - **"No lookup table maps names to files" vs. the task file.** The task file's `name` → `hash` entries work as exactly that kind of map, and `ait attach get` looks things up by name.
> - **The `backend` field vs. "only `local`".** The field reads "where the stored copy lives", as if there were a choice, yet `local` is the only backend accepted.
> - **Retrieving attachments by name.** "A task never refers to an attachment by path" sits a little awkwardly next to commands that use the name. That isn't strictly a contradiction, since a name is not a path.
>
> GUESSED_TERMS=12 UNNEEDED_DETAILS=17

#### Run 2 (tuned): `tasks.md (control)` — guessed terms 14, unneeded details 6, score 20

**Answers** (verbatim):

> 1. A task is the basic unit of work in aitasks. It is a markdown file with YAML frontmatter, stored in the `aitasks/` directory and named `t<N>_<short_name>.md`, for example `aitasks/t130_add_login.md`. The frontmatter holds structured metadata, and the markdown body below it describes the work in free form.
>
> 2. The page never says what YAML frontmatter is. My guess, based on the `---`-delimited block at the top of this page's own source, is that it's a block of YAML key/value pairs at the top of the file between `---` lines. Here it holds the task's metadata: `priority` and `effort`, `status`, `depends` and `boardcol`, `issue_type` and `labels`, `assigned_to`, plus "a long tail of fields the workflow writes for itself". The page points to the Task File Format reference for the full list of fields.
>
> 3. Tasks live as files in the `aitasks/` directory, committed to git like source code. The page doesn't say whose repository that directory is in. My guess is that it sits at the root of your own project's repo.
>
> 4. The page lists several ways, which all write a file into `aitasks/`. The most common is `ait create`, usually started from inside a TUI such as Board or Brainstorm; others are `/aitask-explore`, `/aitask-wrap` and `/aitask-pr-import`. The page never explains what `ait` is, gives no actual command line, and doesn't say what the `/aitask-...` names are. My guess is that `ait` is the aitasks CLI and the slash names are commands you type to a coding agent. Its "they all just write a file" also hints that you could write the file by hand, but it doesn't say so.
>
> 5. Because then version control does the tracking. Every task's full history shows up in `git log`, branches and worktrees can carry their own task state, and a code agent can read, write and reason about tasks with the same tools it uses for source code. The page also says the frontmatter is kept small enough for an LLM (a large language model) to hold in context, but rich enough to drive prioritization, dependency resolution and Kanban-style triage.
>
> 6. The page says that every CLI command, TUI and code-agent skill works on the task files directly, and that "the workflow" writes some fields itself. It never says outright that people edit them, though my guess is that you can, since they are plain files in git. It also leaves "TUI", "code agent", "skill" and "the workflow" undefined, so a new reader can't tell which tool owns which fields.
>
> Places a reader new to aitasks would stumble:
> - `ait` is used without ever being introduced.
> - The first concrete creation step is buried in a list of links.
> - The `/aitask-...` names are never explained.
> - "Board" and "Brainstorm" are named without saying what they are.
> - Nothing says whether hand-editing a task file is safe or how that interacts with the fields the workflow writes.
>
> Ready for follow-up questions.

**Follow-up report** (verbatim):

> These answers come from the page text alone.
>
> **1. What was ambiguous**
> - Where the `aitasks/` directory lives: in my own project's repo root, or somewhere aitasks creates.
> - Whether writing a task file by hand is a supported way to create a task. "They all just write a file into `aitasks/`" suggests it is, but the page never says so.
> - "A long tail of fields the workflow writes for itself": I can't tell what "the workflow" is, which fields those are, or whether I may edit them.
> - How the `<N>` in `t<N>_<short_name>.md` is assigned (by hand or automatically), and what happens when two branches pick the same number.
> - "Branches and worktrees can carry their own task state": the page doesn't say how that state merges back, or whether conflicts are a concern.
> - Whether `ait create` can run on its own in a terminal, since it is "typically launched from inside a TUI".
> - What "code-aware capture" and "import flows" actually do.
> - `boardcol` is grouped under "scheduling and dependencies", which reads like a board-column setting rather than scheduling.
>
> **2. What the page assumed I already knew**
> - That `ait` exists, what it is (the aitasks CLI, I assume), and that it is installed.
> - What a TUI is, and what the Board and Brainstorm TUIs are.
> - What a "code agent" and a code-agent "skill" are, and that the `/aitask-...` names are commands typed to an agent.
> - What YAML frontmatter is.
> - What "the workflow" refers to.
> - Kanban-style triage and the idea of an LLM's "context". These are probably familiar but are not explained.
>
> **3. Terms whose meaning I had to guess**
> 1. YAML frontmatter
> 2. `ait`
> 3. TUI
> 4. code agent
> 5. skill (code-agent skill)
> 6. the slash-prefixed names (`/aitask-explore`, `/aitask-wrap`, `/aitask-pr-import`)
> 7. Board
> 8. Brainstorm
> 9. "the workflow"
> 10. `boardcol`
> 11. `effort`
> 12. "code-aware capture"
> 13. "import flows"
> 14. `<N>` (I took it to be the task number, but how it is assigned is unclear)
>
> **4. Details I did not need to answer the questions**
> 1. The inline pointer "The Task File Format reference documents every field" in "What it is".
> 2. The repeated pointer "The complete frontmatter schema and worked examples live in the Task File Format reference" in "How to use".
> 3. The sentence saying the schema is small enough for an LLM to keep in context but expressive enough for prioritization, dependency resolution and Kanban-style triage. That is a design rationale for the schema, not a reason for keeping tasks in git.
> 4. The pointer to the "Capturing ideas" and "Create tasks from code" workflows.
> 5. The other ways to create a task besides `ait create` (`/aitask-explore`, `/aitask-wrap`, `/aitask-pr-import`). One way was enough to answer "how do I create a task", though I did mention them.
> 6. The aside "(typically launched from inside a TUI like Board or Brainstorm)".
>
> **5. Contradictions**
> - I found no outright contradictions.
> - There are minor tensions:
>   - `boardcol` is filed under "scheduling and dependencies".
>   - `ait create` is listed among the CLI entry points but described as "typically launched from inside a TUI". That leaves it unclear whether it is meant to be run directly.
>   - "They all just write a file" sits awkwardly next to "fields the workflow writes for itself". The page never says whether a hand-written file is complete without those fields.
>
> GUESSED_TERMS=14 UNNEEDED_DETAILS=6

#### Run 2 (tuned): `plans.md (control)` — guessed terms 14, unneeded details 5, score 19

**Answers** (verbatim):

> Fresh-reader answers (persona: knows git and a terminal, has never heard of aitasks). I used only the page text and no tools.
>
> 1. **What is a plan?** It is a markdown file in `aiplans/` that describes how a task will be built. It mirrors its task file, so `p130_add_login.md` goes with `t130_add_login.md`. It has a metadata header (the task, worktree, branch and base branch), a context summary, step-by-step implementation steps, the critical files to be touched and verification steps. The description calls it "the implementation contract".
>
> 2. **Who writes a plan, and when?** It is written during the "planning phase" of a skill like `/aitask-pick` (or `/aitask-explore`), before any code is written. The page never says outright who writes it. From "produced as a side effect" and "the agent then has a concrete contract to follow", I infer the AI agent writes it. That is an inference, not something the page states. I also don't know what a "skill" is or where I would type `/aitask-pick`; the page assumes I do.
>
> 3. **How do I approve a plan?** The page does not say. It only says plans are "approved by the user before any code is written" and that "the user approves the approach once, in plain English." **Guess:** while the skill is running, the agent shows me the plan in its session and asks me to approve it, and I answer there. I can't tell whether "in plain English" describes the plan or my approval.
>
> 4. **Where are plans kept?** In the `aiplans/` directory, named `p<N>_<short_name>.md`. Child task plans go under `aiplans/p<parent>/p<parent>_<child>_<name>.md`. The page also mentions "archived plans" but never says where they are stored. **Guess:** an archive subfolder such as `aiplans/archived/`. I also assume they are committed to git, but the page doesn't say so.
>
> 5. **What happens to a plan after the work is done?** While the work is happening, the agent updates the plan with deviations, post-review changes and final implementation notes. After that it becomes an "archived plan": the long-term record of how the task was built. Later sibling tasks read it as context, and the Code Browser shows it when explaining changed code. The page never explains when or how archiving happens, or who does it.
>
> 6. **Do I ever write a plan myself?** Normally not: "you do not normally write the file by hand." The word "normally" suggests you sometimes might, but the page gives no case for it and no instructions beyond a GitHub link to `task-workflow/planning.md`.
>
> **Where I got stuck as a reader:** "skill", "worktree" and "archived" are never defined. How approval works is missing entirely. Who writes the plan is only implied. And the plan's contents are listed before I'm told what a task is.

**Follow-up report** (verbatim):

> Follow-up answers (fresh-reader persona, page text only, no tools).
>
> **1. What was ambiguous?**
> - Who writes the plan. The page says a plan is "written during the planning phase of a skill" and "produced as a side effect", but never names the writer. I inferred it is the AI agent.
> - How approval works. "Approved by the user" gives no mechanism: no command, no prompt, no file edit.
> - "The user approves the approach once, in plain English." I can't tell whether the plan is in plain English or my approval is.
> - Who updates the plan with "deviations, post-review changes, and final implementation notes", and whether those later edits need approval again.
> - "You do not *normally* write the file by hand." The page doesn't say when you would.
> - Where archived plans live, and when or how a plan becomes "archived".
> - Whether every task gets its own worktree and branch. The header lists both, but the page never says whether they are always created.
>
> **2. What did the page assume you already knew?**
> - What aitasks is, and what a "task" is: its file, its number, where it lives.
> - What a "skill" is, and where you type `/aitask-pick` (in which program or agent).
> - That an AI coding agent is part of this workflow.
> - The parent/child task model, and what "sibling tasks" are.
> - What "archiving" a task or plan means in this system.
> - What the Code Browser is.
> - Why a task would have its own worktree and base branch. I know git worktrees in general, but not how they are used here.
> - What an agent's "session memory" is and why it gets lost.
>
> **3. Terms I had to guess the meaning of**
> 1. task
> 2. skill
> 3. `/aitask-pick`
> 4. `/aitask-explore`
> 5. planning phase
> 6. agent
> 7. archived / archived plan
> 8. child task (and parent)
> 9. sibling tasks
> 10. Code Browser
> 11. worktree (as a field in the plan's header)
> 12. verification protocol
> 13. shared task-workflow skill
> 14. session memory
>
> **4. Details I did not need to answer the questions**
> 1. The list of metadata header fields (task, worktree, branch, base branch).
> 2. The child-plan path pattern `aiplans/p<parent>/p<parent>_<child>_<name>.md`. I mentioned it, but Q4 only needed `aiplans/`.
> 3. "A plan separates the what and how from the doing."
> 4. "Externalizing the plan to `aiplans/` (rather than leaving it inside an agent's session memory) is what makes that long-term record possible."
> 5. The pointer saying the file naming, metadata header and verification protocol are defined in `task-workflow/planning.md` on GitHub.
>
> **5. Does anything contradict something else on the page?**
> - Nothing contradicts outright.
> - There is a mild tension. The description and "What it is" frame the plan as written and approved *before* coding, but "Why it exists" says it is updated afterwards with deviations, post-review changes and final notes. A reader can't tell whether the approved contract can change without re-approval.
> - Smaller tension: "you do not normally write the file by hand" sits next to "the user approves the approach". My role is approving, yet the page never says how I approve.
>
> GUESSED_TERMS=14 UNNEEDED_DETAILS=5

#### Run 2 (tuned): `scratch Labels page (compliant control)` — guessed terms 4, unneeded details 5, score 9

**Answers** (verbatim):

> 1. A label is a short tag, such as `ui` or `docs`, that you attach to a task. A task is one piece of work that aitasks tracks, kept as a small text file in your repository.
>
> 2. A project builds up many tasks about unrelated things. Labels let you pick out the tasks that touch the same area, for example everything about the user interface, without changing how those tasks are planned or ordered.
>
> 3. You pick labels when you create a task, or add them later from the board, which is the aitasks screen that shows tasks as cards in columns. The page doesn't say how to do either one: no command, flag, key or menu is named. My guess is that a create command takes a label option and the board has a key for editing labels. I also can't tell whether I could just edit the task's text file myself.
>
> 4. Filter the board by that label. The page doesn't say how to set the filter, or whether there is a command-line way to list labelled tasks. My guess is a filter key or menu on the board.
>
> 5. Yes. A task can carry several labels, and many tasks can share the same label.
>
> Where I stumbled as a reader:
> - How do I open the board? It's described but never named as a command.
> - "New labels are added to the project's list the first time you use them." What list is that, where does it live, and can I see or edit it? Does it mean a typo creates a new label without any warning?
> - I don't know what "planned or ordered" means in aitasks. It hints at other ideas, maybe priority or columns, that I haven't met yet.
> - "Topic anchoring" in See also sounds like it overlaps with labels. One sentence on when to use which would help.

**Follow-up report** (verbatim):

> 1. What was ambiguous
> - How to add a label. The page says "when you create a task" or "from the board" but never names a command, option, key or menu.
> - How to filter the board by a label. The page gives no mechanism for it.
> - Whether I can filter by more than one label at a time, or only one.
> - What "the project's list" of labels is: where it lives, whether I can see or edit it, and whether a mistyped label silently becomes a new one.
> - Whether labels are free text or have to come from a fixed set. "Added the first time you use them" suggests free text, but the page never says so.
> - Whether labels can be removed or renamed later.
> - Whether labelled tasks can be found outside the board, for example from the terminal.
>
> 2. What the page assumed I already knew
> - How to create a task in aitasks.
> - How to open the board and move around in it.
> - What "planned" and "ordered" mean for an aitasks task, such as whether there is a priority or position.
> - That aitasks is already installed and set up in my repository.
> - What a "project" is in aitasks terms (I assume it is the repository).
>
> 3. Terms I had to guess the meaning of
> - "project's list" (of labels): guessed it is a stored list of known labels somewhere in the repository.
> - "planned" / "ordered" (as aitasks concepts): guessed they mean priority or position on the board.
> - "columns" (on the board): guessed they are status or workflow stages, but the page doesn't say what they represent.
> - "project": guessed it is the same as the git repository.
>
> 4. Details I did not need to answer the questions
> - "A task is one piece of work that aitasks tracks"
> - "kept as a small text file in your repository"
> - "without changing how those tasks are planned or ordered"
> - "the aitasks screen that shows your tasks as cards in columns" (the explanation of what the board is)
> - "New labels are added to the project's list the first time you use them."
>
> 5. Contradictions
> - None found. Every statement is consistent with the others.
>
> GUESSED_TERMS=4 UNNEEDED_DETAILS=5


## Reader reports — after

Same method as the run-2 baseline: `main-concept` persona on every page, the
run-2 questions verbatim, page text inline (final working-tree text), follow-up
questions in the same conversation with frontmatter and navigation excluded
from "details not needed". Reports extracted verbatim from the transcripts.

| Page | depth (after) | before (run 2) | after | change |
|---|---|---|---|---|
| locks | main-concept | 27 + 26 = 53 | 7 + 6 = 13 | −40 |
| topic-anchoring | main-concept | 15 + 15 = 30 | 7 + 7 = 14 | −16 |
| gates | intermediate | 17 + 24 = 41 | 16 + 12 = 28 | −13 |
| framework-session | intermediate | 16 + 22 = 38 | 10 + 4 = 14 | −24 |
| skill-templating | intermediate | 21 + 20 = 41 | 6 + 4 = 10 | −31 |
| attachments | intermediate | 12 + 17 = 29 | 7 + 5 = 12 | −17 |
| tasks (control, edited in Step 4) | main-concept | 14 + 6 = 20 | 7 + 6 = 13 | −7 |
| plans (control, edited in Step 4) | main-concept | 14 + 5 = 19 | 8 + 5 = 13 | −6 |

The gates row is the final text, re-run at the Step 8 review after the user's
findings changed its failure paragraph. The first after-report for gates (18 + 9 = 27)
and the run on the intermediate wording (19 + 14 = 33) are kept below as historical
reports of superseded text.

Reading notes for child 8:
- Unneeded details fell most (long pages 15–26 → 4–12), which is the signal the
  restructure targeted. Guessed terms fell least on gates (17 → 16), where a
  `main-concept` reader still guesses the terms an `intermediate` page links
  instead of defining (archive, pick, profile, registry) — expected under the
  level contract, not a defect.
- The three gates runs (27, 33 and 28) also show run-to-run variance of a few
  points, partly from the wording change in between. A difference of that size
  between two runs is not a signal on its own.
- The two controls also improved because Step 4 edited them (field list,
  undefined skill/TUI/frontmatter), so they are no longer unedited controls in
  the after run; the scratch Labels page (9) remains the floor.
- Remaining reader stumbles worth a later pass: how a plan is approved (plans),
  whether `ait lock` covers the merge mutex (locks), the task-number format
  (tasks, attachments), and the after-reboot restore path (framework-session).

### Verbatim reports

#### After (tuned procedure): `locks.md` — guessed terms 7, unneeded details 6, score 13

**Answers** (verbatim):

> 1. A lock marks something as in use by one agent so other agents leave it alone. There are two kinds. The **task lock** is taken when an agent starts work on a task (a markdown file describing one piece of work). The **merge mutex** lets only one finished task at a time merge its branch back into the branch the work started from.
>
> 2. Several agents can work in one repository at the same time, on one machine or several. Without the task lock, two agents could start the same task and produce conflicting branches, commits and archive records. Without the merge mutex, two merges running at once in the shared main copy of the repository would mix their changes.
>
> 3. No. aitasks takes and releases both locks itself. Starting a task with `/aitask-pick` or from the board (`ait board`) takes the task lock automatically.
>
> 4. The page says the task lock means "no other agent can take the same task," so the second agent is refused. It doesn't say what the second agent actually sees or does. It points to `ait lock` for "what happens when a pick meets a held lock." Guess: the second agent's pick fails or warns that the task is already locked, and it moves on to another task.
>
> 5. The crashed agent's locks stay behind. The next agent can take over the task lock through a crash-recovery procedure, and a stuck merge mutex has its own clearing steps. Both are on linked pages, and this page doesn't give the steps.
>
> 6. `ait lock` shows the task locks, and you can release a task lock yourself with it. The page doesn't give the exact subcommands or flags. For a stuck merge mutex it points to the Merge mutex page instead, which suggests `ait lock` does not handle that one. Guess: something like `ait lock list` and `ait lock release <task>`.
>
> Points where I, as a new reader, got stuck:
> - The page says locks are "kept in git" and shared by push and fetch. So if two machines grab the same task before either pushes, can both get it? The page doesn't say.
> - I can't tell if `ait lock` can show or clear the merge mutex, or only task locks.
> - I can't tell how a crash is detected, or if a lock left by a crashed agent ever expires on its own.

**Follow-up report** (verbatim):

> **1. What was ambiguous**
> - **What the second agent sees.** "No other agent can take the same task" says the second agent is refused. It doesn't say whether it gets an error, a warning, a wait, or an offer to take over.
> - **Locks across machines.** "Task locks are kept in git" and shared by push and fetch. If two machines take the same task before either one pushes, can both get it?
> - **What `ait lock` covers.** It "shows the task locks", but stuck merge mutexes are sent to a different page. Can `ait lock` see or clear the merge mutex at all?
> - **Who releases the lock.** "aitasks takes and releases both locks on its own", but also "The agent releases it". Is it the framework or the agent?
> - **"The task is given up".** How do you give up a task, and is it an action I take or something the agent decides?
> - **"Once the merge and its checks are done".** What checks?
> - **"A task that has its own branch" / "can have its own worktree".** When does a task get its own branch or worktree? Is it optional, and who decides?
> - **Where the merge happens.** Is "the branch the work started from" the same as "the main copy of the repository"? Is the merge target always main?
> - **How a crash is detected.** It isn't explained, and the page doesn't say whether a left-over lock ever expires on its own.
>
> **2. What the page assumed I already knew**
> - What a "coding agent" is and that you type commands into one. "Skill" is defined, the agent itself is not.
> - That `ait` is installed and is the aitasks CLI.
> - That agent identity involves an email ("under the same email"). Nothing earlier says tasks or agents are tied to an email.
> - What "mutex" means.
> - That tasks produce "archive records".
> - That "pick" means claiming a task (implied by `/aitask-pick`).
> - Git worktrees and checkouts. It defines worktree briefly, but "checkout" relies on git knowledge, which my persona has.
>
> **3. Terms I had to guess**
> 1. mutex (in "merge mutex"): guessed as a lock that only one holder can have at a time.
> 2. archive records: guessed as some log or archive entry written when a task is finished.
> 3. "same email": guessed as the git user email that identifies who owns a lock.
> 4. "checks" (in "the merge and its checks"): guessed as tests or verifications run after merging.
> 5. "given up" task: guessed as a task that is abandoned or un-claimed.
> 6. "main copy of the repository": guessed as the original checkout, as opposed to the worktrees.
> 7. coding agent: guessed as an AI coding assistant running in a terminal.
>
> **4. Details I did not need for the questions**
> 1. "so several agents in one checkout under the same email still exclude each other" (the agent session definition).
> 2. "Task locks are kept in git, so the same push and fetch ... share them, with no server to run."
> 3. The worktree definition and "so agents running at the same time never edit each other's files."
> 4. "archived (moved out of the list of open tasks)".
> 5. "The merge mutex is taken just before a finished task merges and released once the merge and its checks are done."
> 6. The list of automatic release events: "when the task is finished and archived ... when the task is given up".
>
> **5. Contradictions within the page**
> - **Who releases the lock.** "aitasks takes and releases both locks on its own" against "The agent releases it ... or when you release it yourself". Is the releaser aitasks, the agent, or you? It reads as a mild inconsistency, not a hard contradiction.
> - **Whether I need to act.** "You do not need to do anything with them" is in tension with releasing a lock yourself with `ait lock`, and with crash recovery or clearing a stuck merge mutex, which both seem to need a person.
> - **"Never" for an optional feature.** A task "can have" its own worktree, which sounds optional, "so agents ... never edit each other's files". That "never" only holds if every concurrent task actually has a worktree.
> - Nothing is directly self-contradictory beyond these.
>
> GUESSED_TERMS=7 UNNEEDED_DETAILS=6

#### After (tuned procedure): `topic-anchoring.md` — guessed terms 7, unneeded details 7, score 14

**Answers** (verbatim):

> 1. A topic is a group of loosely related tasks about one subject. It is named after one of its tasks, the "topic root", which is usually the task the others came from. Other tasks join by storing the root's task number in a field called "anchor". A child task belongs to its parent's topic without needing an anchor.
>
> 2. Child tasks are ordered parts of one larger task that are finished as a set, and the parent is done only when all of them are. Topic tasks just sit near each other when you sort and review your backlog. Each one is still planned, picked up and archived on its own, and none has to wait for the others.
>
> 3. Most of the time you don't do anything: follow-ups that aitasks creates join their source task's topic, and child tasks join their parent's topic. To add one yourself, run `ait create` in batch mode and give it either the root's task number or the task it follows up (aitasks then finds the root for you). You can also edit the anchor on the task detail screen in `ait board`. The page doesn't give the actual flag names. My guess is something like `ait create --batch --anchor <N>`.
>
> 4. Open `ait board` and press `y` for the By-Topic view. Each topic with at least two tasks gets its own column, headed by its root task. Tasks that are alone in their topic share one last column.
>
> 5. Yes. `ait update` moves an existing task to another topic or makes it a root of its own, and you can also edit the anchor on the board's task detail screen. The page doesn't say which `ait update` option does this. I'd guess an `--anchor` option, but that is a guess.
>
> 6. The page doesn't say directly when not to use a topic, so this is inferred from its comparison list. Use child tasks instead when the work is ordered parts of one task that finish together. Use a dependency when one task can't start until another is done. Use a label to filter across many unrelated subjects. The page also says these can be combined, so a topic doesn't rule out the others.

**Follow-up report** (verbatim):

> **1. What was ambiguous**
> - How to call `ait create` in batch mode. The page says to "give it either the root's task number or the task it follows up", but it names no flag or argument for either.
> - Which `ait update` option moves a task to another topic, or makes it "a root of its own". I also can't tell whether "a root of its own" just means clearing the anchor.
> - "A follow-up task that aitasks itself creates": the page never says when or how aitasks creates tasks by itself.
> - What a "task number" looks like (for example `130` or `t130`).
> - Whether a root task has an anchor field itself, or leaves it empty.
> - Whether a child task can be moved to a different topic from its parent. "A parent and its children share one topic" suggests it can't, but `ait update` "moves an existing task to another topic" has no exception for children.
> - What happens to the tasks anchored to a root when that root is moved into another topic.
> - "The subject is named after one of them": I can't tell whether the topic's displayed name is the root's title or just its number.
> - "Sorting" the backlog: the page doesn't say whether that means only the By-Topic view or something more.
>
> **2. What the page assumed I already knew**
> - What `ait` is, and how to install and run it.
> - What "batch mode" is, as opposed to some other mode of `ait create`.
> - That task files have named fields (the page says "a field called its anchor" without explaining where fields live in a markdown file).
> - What "planned" and "picked up" mean in the aitasks workflow.
> - That aitasks (or some agent) creates follow-up tasks automatically.
> - How to open a task's detail screen in the board.
> - How to set dependencies and labels (they are named but not shown).
>
> **3. Every term I had to guess the meaning of**
> - batch mode
> - task number (its format)
> - field (where it lives in the task file)
> - planned (as a workflow step)
> - picked up (as a workflow step)
> - "follow-up task that aitasks itself creates"
> - task detail screen
>
> **4. Every detail I did not need to answer the questions**
> - The definition of a task as a markdown file kept in the repository and committed to git.
> - "That number is how aitasks keeps the group together." (This repeats what the sentences before it already say.)
> - What archiving does, that an archived task stays a valid topic root, and that a topic keeps collecting tasks after its root is done.
> - "Work on one task often turns up more: a follow-up fix, a related cleanup, an idea for later."
> - "Without a topic they scatter across your task list, and the link back to their origin lives only in your memory."
> - The board described as "the terminal view ... which shows your tasks as cards in columns".
> - The example labels `ui` and `docs`.
>
> **5. Contradictions**
> - There is no outright contradiction.
> - There is one small tension. A topic is defined as "a group of loosely related tasks", but the By-Topic view mentions tasks "alone in their topic", so a topic can hold just one task.
> - There is also a possible conflict between "a parent and its children share one topic" and `ait update` being able to move "an existing task" to another topic. The page doesn't say what happens if you move a child.
>
> GUESSED_TERMS=7 UNNEEDED_DETAILS=7

#### After (final text, re-run at the Step 8 review): `gates.md` — guessed terms 16, unneeded details 12, score 28

Same persona and the same seven run-2 questions; page text inline (the committed text).

**Answers** (verbatim):

> Answers from a fresh reader (knows git and a terminal, has never heard of aitasks), using only the page text:
>
> 1. **What is a gate?** A gate is a named check that a task has to pass before it can be archived. The page's examples are a build that must pass, a test suite that must be green, a risk evaluation that must have been done, and a review a person must sign off. Gates are stored in the task file, separately from the task's `status` field.
>
> 2. **What does it mean for a task to archive?** The page never defines it. It only sets "archived" against the task that "stays active" when a gate fails. Guess: archiving means the finished task is marked complete and moved out of the active task list, probably into some archive storage in git.
>
> 3. **How does a task get its gates?** You declare them when you create the task, using the `--gates` flag of `/aitask-create` (batch mode). Or an execution profile's `default_gates` declares them for you.
>
> 4. **Can a task archive while one of its gates has not passed?** Normally no: archival waits until every enforced gate is satisfied. You can do it only with an explicit override, and the page sends you to the Gate rules page for how. It is not clear whether a declared gate that is *not* enforced also blocks archival. I read the page as saying it does not.
>
> 5. **What decides which gates are enforced on a task?** The execution profile you pick the task under. It enforces only those of the task's declared gates that its workflow can check. The page does not explain what an execution profile is or what "picking" a task involves; it only links to other pages.
>
> 6. **Why is the enforced set fixed when the task is picked?** The page does not say. It only states that the set is fixed at pick time and stays the same until the task is picked again. Guess: so the requirements don't change partway through the work, and every machine and session sees the same set.
>
> 7. **What do I do when a gate fails?** Run `ait gate log <task> <gate>` to see why, fix the cause, then re-run it in the way that matches the kind of gate:
>    - **A gate a script checks:** `ait gates run <task> --gate <gate>`.
>    - **A gate that is coding-agent work** (such as `docs_updated`): carry on with the task in your agent, or run `/aitask-pick <id>`.
>    - **A gate the "registry" doesn't know how to check:** `ait gates sync-registry`.
>    - **A human gate** (such as `review_approved`): approve the review in an "attended session", or the reviewer runs `ait gate pass <task> <gate>`.
>
> Places I stumbled as this reader:
> - **Undefined terms:** "archive", "pick", "execution profile", "registry", "attended session", "retries are spent", "machine gates" and "the ledger" (that last one appears only in See also).
> - **Q7 "human gate" case:** the page lists it among failure cases, but it sounds like waiting rather than failing.
> - **"Coding agent":** the page assumes I already have one running.
>
> I'm handing this back through SubagentHandback, which ends my run. Follow-up questions will need a new agent or a resumed one, and it should get the same "page text only" instructions.

**Follow-up report** (verbatim):

> Follow-up answers on the Gates page, from the page text alone:
>
> **1. What was ambiguous?**
> 1. Whether a gate that is declared but not enforced still blocks archival. "Every gate its workflow enforces" suggests it does not, but the page never says so outright.
> 2. "Checked as the work proceeds": who checks, and when? An automatic process, the agent, or me?
> 3. "Some gates also hold back the tasks that depend on this one": the page doesn't say which gates do this, or how a task comes to depend on another.
> 4. "Even when its retries are spent": I can't tell whether gates retry automatically, or how many times.
> 5. "When the task next reaches review or archival": I can't tell whether "review" is a defined stage or the human review gate.
> 6. Whether a human gate can "fail" at all, or only wait. It appears in the "when a gate fails" paragraph but is described as waiting.
> 7. Gates "come into play only while the task is `Implementing`", yet they are declared at creation and fixed at pick time. I'm not sure what being "in play" means beyond those two points.
> 8. Picking the task again (one of the remedies after a failure) re-fixes the enforced set. The page doesn't say whether that can quietly change which gates are enforced.
> 9. The archival override: the page doesn't say what it is or who may use it, only that it lives on another page.
>
> **2. What did I assume the reader already knew?**
> 1. What aitasks is: tasks as files kept in git, plus an `ait` command-line tool.
> 2. The task lifecycle: what `status` values exist, what "pick" and "archive" mean.
> 3. What an execution profile and a "workflow" are.
> 4. That a coding agent is involved and that I'm running one, with slash commands like `/aitask-create` and `/aitask-pick`.
> 5. That task data is synced between machines, and how.
> 6. That there is a "board" and what it shows.
> 7. That tasks can depend on other tasks.
>
> **3. Terms whose meaning I had to guess:**
> 1. archive / archival
> 2. pick (a task)
> 3. execution profile
> 4. workflow
> 5. `Implementing` (as a status value)
> 6. `default_gates`
> 7. machine gate
> 8. registry
> 9. retries (of a gate)
> 10. attended session
> 11. the board
> 12. syncs the task data
> 13. in-flight task
> 14. review (as a stage the task "reaches")
> 15. override (of the archival check)
> 16. dependent tasks / tasks that depend on this one
>
> **4. Details I did not need to answer the seven questions:**
> 1. Gates come into play only while the task is `Implementing`.
> 2. Gates are checked as the work proceeds.
> 3. A single `status` field cannot express independent facts that finish at different times.
> 4. Gates survive a crashed session.
> 5. Gates are visible from every machine that syncs the task data.
> 6. Some gates hold back dependent tasks until they pass.
> 7. Each gate's result is recorded as the workflow reaches it.
> 8. `ait gates` / `ait gate` can run gates, list their state, sign a human gate and read a run's log.
> 9. `/aitask-run-gates` runs the ready machine gates and explains the result.
> 10. The board shows each in-flight task's gates against its enforced set.
> 11. A gate a script checks can be re-run even when its retries are spent.
> 12. An agent never approves a human gate on its own.
>
> **5. Does anything contradict something else on the page?**
> There is no direct contradiction. Archival needing every enforced gate fits with the explicit override, because the first sentence already says "unless you explicitly override that check". There are two tensions:
> - The human gate sits under "when a gate fails" but is described only as waiting for a person.
> - "Fixed when you pick the task and stays the same until it is picked again" sits uneasily with "pick it again" offered as a routine way to re-run a failed gate. The page doesn't say whether re-picking can change the enforced set.
>
> guessed terms: 16
> unneeded details: 12

#### Historical — intermediate wording (superseded text): `gates.md` — guessed terms 19, unneeded details 14, score 33

Run on the first wording of the Step 8 fix ("attended workflow", "agent session"), which was then rewritten.

**Answers** (verbatim):

> Answers (from the page text only, no tools used):
>
> 1. **What is a gate?** A gate is a named check a task has to pass before it can be archived. Examples are a build that must pass, a green test suite, a finished risk evaluation, or a sign-off from a person. Gates are stored apart from the task's `status` field, and they only matter while the task is `Implementing`.
>
> 2. **What does it mean for a task to archive?** The page never says. My guess: the task is marked finished and moved out of the active task list into some archive location, as the last step of its life. The page points to "Task lifecycle" for this.
>
> 3. **How does a task get its gates?** You declare them when you create the task, with the batch `--gates` flag on `/aitask-create`. Or an execution profile's `default_gates` declares them for you.
>
> 4. **Can a task archive while one of its gates has not passed?** Only with an explicit override; the details are behind the "Gate rules" link. One caveat from the wording: archival waits for "every gate its workflow *enforces*". So a gate that was declared but is not enforced under the current profile apparently does not block. The page does not say that outright.
>
> 5. **What decides which gates are enforced?** The execution profile you pick the task under. Out of the gates the task declares, it enforces only the ones its workflow can check. This confused me a little: the same page also says a profile's `default_gates` can *declare* gates. So a profile seems to play two roles, declaring and filtering, and the page does not separate them.
>
> 6. **Why is the enforced set fixed at pick time?** The page says that it happens (fixed at pick, unchanged until the task is picked again) but not why. My guess: so the target does not move in the middle of the work, and progress (for example the board's "satisfied vs enforced" count) stays consistent.
>
> 7. **What do I do when a gate fails?**
>    - Run `ait gate log <task> <gate>` to see why it failed, then fix the cause.
>    - A script-checked gate: rerun it with `ait gates run <task> --gate <gate>`. This works even if its retries are spent.
>    - An agent-run gate such as `docs_updated`: continue the task in an agent session, or run `/aitask-pick <id>`. The workflow reruns it at review or archival.
>    - If the registry has no instructions for how to check the gate: run `ait gates sync-registry`.
>    - A human gate such as `review_approved`: it is recorded when you approve the review in an attended session, or the reviewer later runs `ait gate pass <task> <gate>`.
>    - Otherwise, archive with an explicit override.
>
> Where I stumbled as a newcomer:
> - **"Archive" and "archival"** are central to the page but never defined.
> - **"Workflow"** ("gates its workflow enforces") is used as if I already know it. I can't tell whether it means the profile, the agent session, or something else.
> - **"Attended" vs. agent session:** "attended session" and "attended workflow" are not explained, and neither is how they differ from an "agent session".
> - **"Registry"** appears in "the registry never says how to check it" with no introduction. I don't know what it is or where it lives.
> - **"Machine gates that are ready":** "ready" hints at an ordering or unlock rule the page doesn't explain.
> - **"Picking" a task** is assumed knowledge.
> - **The `Implementing` status** is assumed knowledge.
> - **Blocking dependents:** "Some gates also hold back the tasks that depend on this one". It doesn't say which gates, or how a gate gets that behaviour. The field name `also_blocks_dependents` only shows up in the See-also list.
>
> I can take follow-up questions, but this hand-back ends my run, so they would need to go to a resumed or new agent.

**Follow-up report** (verbatim):

> Follow-up answers on the Gates page. I used only the page text and no tools.
>
> **1. What was ambiguous?**
> 1. **What "workflow" means.** "Every gate its workflow enforces" never says whether the workflow is the execution profile, the agent session, or something else.
> 2. **The profile's two roles.** A profile's `default_gates` *declare* gates, and the profile also *decides which are enforced*. The page never says whether a profile always enforces the gates it declared itself.
> 3. **Declared but not enforced.** Archival waits only for *enforced* gates, so it is unclear whether a declared gate that isn't enforced blocks anything, shows anywhere, or is simply ignored.
> 4. **"Only while Implementing."** Gates are declared at create time but "come into play only while `Implementing`". Archival seems to happen from that status, but the page doesn't say so.
> 5. **Re-picking a task.** "Pick it again with `/aitask-pick <id>`" is offered as a way to rerun `docs_updated`. But picking again also re-derives the enforced set, and the page doesn't say whether that can change which gates apply.
> 6. **Which gates block dependents.** "Some gates also hold back the tasks that depend on this one" doesn't say which gates do this or how.
> 7. **"Ready."** "Machine gates that are ready" suggests an ordering or unlock rule that isn't explained.
> 8. **"Attended session" vs "agent session".** Both names are used and the page doesn't say whether they are the same thing.
> 9. **The override.** "Unless you explicitly override that check" never says what the override is: a flag, a command, or a prompt.
>
> **2. What did you assume the reader already knew?**
> 1. What a task is in this framework (a file with a `status` field).
> 2. What archiving a task means.
> 3. What "picking" a task means.
> 4. The `Implementing` status and the other statuses.
> 5. What an execution profile is.
> 6. What an agent session is, and what "attended" means.
> 7. That task data is synced between machines, and how.
> 8. That there is a "board" and what it shows.
> 9. That task dependencies exist.
> 10. That there is a gate "registry".
> 11. That gates have retry budgets.
>
> **3. Terms I had to guess the meaning of, one per line**
> 1. archive / archival
> 2. workflow
> 3. execution profile
> 4. pick / picking
> 5. `Implementing` (as a status)
> 6. attended session / attended workflow
> 7. agent session
> 8. machine gate
> 9. human gate
> 10. agent-run gate (a gate "an agent carries out")
> 11. registry
> 12. retries (for a gate)
> 13. ready (for a gate)
> 14. enforced set / enforced gates
> 15. in-flight task
> 16. the board
> 17. batch (`--gates` flag)
> 18. override (for archival)
> 19. syncs the task data
>
> **4. Details I did not need to answer the seven questions, one per line**
> 1. Gates "are checked as the work proceeds".
> 2. "A single `status` field cannot say 'the build passed, the review is pending and the docs still need updating'".
> 3. "Those are independent facts that finish at different times."
> 4. Gates survive a crashed session.
> 5. Gates are visible from every machine that syncs the task data.
> 6. Some gates hold back dependent tasks until they pass.
> 7. "The rest is the framework's job".
> 8. Each gate's result is recorded as the workflow reaches it.
> 9. `ait gates` / `ait gate` can list gate state.
> 10. `ait gates` / `ait gate` can sign a human gate (stated generically; Q7 used the specific `ait gate pass` command instead).
> 11. `/aitask-run-gates` runs the machine gates that are ready and explains the result.
> 12. The board shows each in-flight task's gates against its enforced set.
> 13. "An agent never approves it on its own" (about human gates).
> 14. A failure is recorded in the task file (I used "the task stays active" only loosely).
>
> **5. Does anything on the page contradict something else?**
> There are no outright contradictions. There are four tensions:
> 1. "The rest is the framework's job" sits next to a long list of commands the reader runs by hand when a gate fails.
> 2. The enforced set is "fixed when you pick the task", yet re-picking is offered as a remedy. That silently re-derives the set, and the page doesn't acknowledge it.
> 3. Gates "come into play only while the task is `Implementing`", but they are declared at create time and can be set by a profile's defaults. That fits if "come into play" means "are checked", but a reader could trip on it.
> 4. A human gate "is recorded when you approve the review in an attended session" sits beside "an agent never approves it on its own". It's consistent if the agent records your approval, but the wording makes the agent's role in recording it unclear.
>
> guessed terms: 19
> unneeded details: 14

#### Historical — first after-report (superseded text): `gates.md` — guessed terms 18, unneeded details 9, score 27

**Answers** (verbatim):

> 1. A gate is a named check a task must pass before it can be archived. Examples are a build that must pass, a test suite that must be green, a risk evaluation that must have been done, or a review a person must sign off. Gates are recorded in the task file separately from the task's `status` field.
>
> 2. The page never defines "archive". **Guess:** archiving means closing a finished task and moving it out of the active set, like marking it done. The page only implies this: the task "stays active" after a gate fails, and the See also list names "picking, implementing and archiving" as lifecycle steps.
>
> 3. A task gets its gates in one of two ways. You declare them when you create the task with the batch `--gates` flag, or an execution profile's `default_gates` declares them for you. Separately, when you pick the task, the framework works out which of those declared gates are enforced.
>
> 4. Not normally. A task archives only once every enforced gate is satisfied. Archiving with an unmet gate needs an explicit override, and the page sends me to "Gate rules" for how to do that.
>
> 5. Two things decide it together. The task declares the gates it asks for, and the execution profile you pick it under enforces only the ones its workflow can check. So the same task can have a different enforced set under a different profile.
>
> 6. The page says the enforced set is fixed at pick time and stays the same until the task is picked again, but it never says why. **Guess:** it keeps the rules stable while work is in progress, so the gates can't change partway through or differ between sessions and machines.
>
> 7. First run `ait gate log <task> <gate>` to see why it failed. Fix the cause, then run `ait gates run <task> --gate <gate>`, which works even if its retries are used up. Two special cases:
>    - If the gate can't pass because "the registry never says how to check it", run `ait gates sync-registry`. I don't know what "the registry" is; the page never explains it.
>    - If it's a human gate like `review_approved`, a person has to approve it, either in an attended session or with `ait gate pass <task> <gate>`.
>
> Where I stumbled as a newcomer:
> - "Archive", "pick", "attended session", "registry", "retries", "machine gate" and "workflow" are all used without being defined.
> - The page says some gates "hold back the tasks that depend on this one", but never says which gates do or how.

**Follow-up report** (verbatim):

> Follow-up answers, from the page text only.
>
> **1. What was ambiguous**
> - **When gates apply:** they "come into play only while the task is `Implementing`", yet they are also checked "when the task archives". It's unclear whether a task is still `Implementing` at the moment it archives.
> - **"Workflow" vs. "profile":** "every gate its workflow enforces" and "the execution profile … decides which of them its workflow enforces" use workflow and profile almost interchangeably. Their relationship is never stated.
> - **Declared but not enforced:** what happens to a declared gate that the profile doesn't enforce? Is it ignored, shown, or run anyway?
> - **Gates that hold back dependents:** "Some gates also hold back the tasks that depend on this one". It doesn't say which gates or how.
> - **"Picked again":** the enforced set lasts "until it is picked again", but nothing says when or why a task would be picked a second time.
> - **"Retries are spent":** it doesn't say who retries, how many times, or automatically on what.
> - **The registry:** "the registry never says how to check it" never says what the registry is, or why it would be missing an entry.
> - **Ready machine gates:** "machine gates that are ready" doesn't explain what makes a gate ready.
> - **The override:** it's named twice but never described on this page.
> - **Two kinds of command:** `/aitask-create` and `/aitask-run-gates` are slash-style names, while `ait gates` is a shell command. The page doesn't say where each one is typed.
>
> **2. What the page assumed I already knew**
> - Tasks are files with frontmatter-like fields, such as `status`, and `Implementing` is one of the status values.
> - What "picking" a task means, and that it starts the work.
> - What "archiving" means.
> - What an execution profile and a "workflow" are.
> - That AI agents do the work, and what an "attended session" is as opposed to an unattended one.
> - That task data is synced across machines.
> - That there is a "board" UI.
> - That tasks can depend on other tasks.
> - The `ait` CLI and the slash-command (skill) interface, including "batch" mode for create.
>
> **3. Every term I had to guess the meaning of**
> 1. archive / archival
> 2. pick (a task)
> 3. `Implementing` (as a status)
> 4. execution profile
> 5. workflow
> 6. registry
> 7. retries
> 8. machine gate
> 9. attended session
> 10. agent
> 11. board
> 12. in-flight
> 13. ready (gate)
> 14. depend / dependents
> 15. batch (`--gates` flag)
> 16. override
> 17. `default_gates`
> 18. sync (task data)
>
> **4. Details I didn't need to answer the questions**
> 1. Why one `status` field can't express several independent facts.
> 2. Gates survive a crashed session and are visible on every machine that syncs task data.
> 3. Some gates hold back dependent tasks.
> 4. Gates are checked "as the work proceeds" and only matter while the task is `Implementing`.
> 5. What `ait gates` / `ait gate` can do: run, list state, sign a human gate, read a run's log.
> 6. `/aitask-run-gates` runs ready machine gates and explains the result.
> 7. The board shows each in-flight task's gates against its enforced set.
> 8. Each gate's result is recorded as the workflow reaches it.
> 9. "An agent never approves it on its own."
>
> **5. Contradictions**
> - I found no outright contradiction.
> - The closest is a tension between "come into play only while the task is `Implementing`" and "checked … when the task archives". The two sentences conflict unless archiving happens while the task is still `Implementing`, and the page doesn't say whether it does.
>
> GUESSED_TERMS=18 UNNEEDED_DETAILS=9

#### After (tuned procedure): `framework-session.md` — guessed terms 10, unneeded details 4, score 14

**Answers** (verbatim):

> Answers (from the page text only):
>
> 1. **What is a framework session?** It is the record aitasks keeps for each coding agent. The record holds the agent's project, its tmux window, the task it is working on, which agent and model it is, and the id its CLI uses to resume the conversation. There is one record per agent, covering every agent on the machine in every project. It is stored apart from the terminal pane, so it lasts longer than the pane.
>
> 2. **What does freezing an agent mean?** Freezing ends the agent's process but keeps its terminal output readable in its pane. This frees the memory and machine share a finished agent still holds. You freeze one agent with **f** in `ait monitor` or `ait minimonitor`, and **Z** freezes every agent.
>
> 3. **What does restoring an agent mean, and what do I get back?** Restoring starts the coding agent again on the same conversation, using the resume id stored in the record. The page does not say whether it comes back in the same tmux window or pane. My guess is that it reopens in its original window or pane, because the record stores that window.
>
> 4. **Do I need to manage these records myself?** No. aitasks writes the record and you never edit it. The one thing you need to do is install the session hook that `ait setup` offers, because a restore needs the session id that the hook records when the agent starts.
>
> 5. **What happens to the records if my machine or tmux restarts?** The records survive. They are kept apart from the pane, which dies on a tmux restart or shutdown, so you can bring agents back "even after a reboot." The page does not say where the records are stored; it links to "Framework Session Store" for that. My guess is a file on disk somewhere under the user's home directory.
>
> 6. **How do I restore a frozen agent?** Press **R** in the frozen-agent viewer, which takes over the frozen agent's pane. This only works if the session hook recorded the agent's session id. Without it, the page says to "re-pick the task instead." The page does not explain how to reach the viewer after a reboot, when the pane is gone; it points to the Freeze and Restore Agents workflow page for that.
>
> **Where I stumbled as this reader:**
> - "Coding agent" is never defined. I assume it means something like an AI CLI running in a tmux pane.
> - "Re-pick the task" is used as a fallback but never explained.
> - "The frozen-agent viewer that takes its pane" is unclear: does it replace the pane automatically, or do I open it?
> - It is unclear whether **Z** freezes every agent on the machine or only in the current project or monitor.
> - "Share of the machine" is vague. I read it as CPU.
> - The page gives no restore steps for the after-reboot case.

**Follow-up report** (verbatim):

> Follow-up answers, from the page text alone:
>
> **1. What was ambiguous?**
> - The phrase "the frozen-agent viewer that takes its pane". I could not tell whether the viewer replaces the pane automatically when the agent is frozen, or whether I open it myself.
> - What **Z** covers: "freezes every agent" could mean every agent on the machine, in this project, or in this monitor.
> - Whether "session id" and "the id its CLI can resume the conversation from" are the same thing. The page uses both names without linking them.
> - Where a restored agent comes back: the same window or pane, or a new one.
> - After a reboot the pane is gone, so it is unclear where the "readable terminal output" and the viewer's **R** key live then.
> - "The share of the machine" is too vague to pin down: CPU, or something else?
> - What "re-pick the task instead" gets me compared with a restore. Is the conversation lost?
>
> **2. What did the page assume I already knew?**
> - What aitasks is, and what a "task" and a "project" are in it.
> - What a "coding agent" is, and that it has a CLI that can resume conversations by id.
> - That I run agents inside tmux, and how tmux servers, windows and panes relate. This part I did know.
> - What `ait monitor` and `ait minimonitor` are and how to open them.
> - What "picking" a task means, which "re-pick" depends on.
> - What a "session hook" is and when `ait setup` offers it.
>
> **3. Every term I had to guess the meaning of**
> 1. coding agent
> 2. task (in the aitasks sense)
> 3. project
> 4. re-pick (the task)
> 5. frozen-agent viewer
> 6. "takes its pane"
> 7. session hook
> 8. session id (guessed to be the same as the resume id)
> 9. share of the machine
> 10. `ait monitor` / `ait minimonitor`
>
> **4. Details I did not need for the six questions** (frontmatter, See also and Next left out)
> 1. A pane "can be recycled, renamed or split".
> 2. "An agent known only by its pane is lost with the pane." This restates the point without adding anything.
> 3. The freeze keys: **f** in `ait monitor` / `ait minimonitor`, and **Z** to freeze every agent. Question 2 asked what freezing means, not how to do it. I mentioned them anyway.
> 4. The inline sentence saying the Freeze and Restore Agents page walks through both, including re-picking and recovery after a reboot.
>
> **5. Does anything contradict something else on the page?**
> - Nothing contradicts outright.
> - There is one tension. Freezing "keep[s] its terminal output readable in its pane", and the page also says panes die on a tmux restart or reboot. Yet restore works "even after a reboot" using **R** in a viewer that lives in that pane. The page never says how the pane and its output survive a reboot.
> - One naming inconsistency: "the id its CLI can resume the conversation from" in the first section and "session id" in the third, with nothing saying they are the same.
>
> GUESSED_TERMS=10 UNNEEDED_DETAILS=4

#### After (tuned procedure): `skill-templating.md` — guessed terms 6, unneeded details 4, score 10

**Answers** (verbatim):

> 1. A profile-aware skill is a skill, such as `/aitask-pick`, that is written once and comes in several ready-made variants: one for each execution profile and coding agent you run it with. aitasks creates a variant the first time you need it, and the agent follows that variant as the skill.
>
> 2. The page does not define it. It only links to an "Execution profiles" page for "what a profile is and which ones ship." It does name `fast` and `default` as profiles and says a variant holds only its own profile's flow. My guess: a profile is a named preset of choices that changes how a skill runs, for example a `fast` profile that skips some steps or prompts.
>
> 3. There are two reasons. First, the agent re-reads the skill's file while it runs, so if the file changed mid-run the agent would mix two versions of its instructions; each run therefore follows a fixed variant. Second, separate variants keep each one plain, so no variant needs branches like "if your profile sets X, skip this step."
>
> 4. Pass `--profile <name>` when you invoke the skill, for example `/aitask-pick --profile fast 42`, or from a shell run `ait skillrun pick --profile fast 42`. You can also set a default per skill under `default_profiles` in `userconfig.yaml` (just you) or `project_config.yaml` (your team), or in `ait settings`. In `ait board` and other TUIs, use **(E)dit** on the **Profile** row of the launch dialog.
>
> 5. No. They are created automatically next to the skill, in folders whose names end in `-` (such as `aitask-pick-fast-`), and you must never edit or commit them. Something the page leaves open: since I must not commit them, should I add them to `.gitignore` myself, or are they ignored already? It doesn't say.
>
> 6. Partly. The "How to use" part matters, because it covers choosing a profile and not touching the variant folders. The details of how variants are produced are only for skill authors, and the page sends them to another page. Two terms the page uses without explaining: "coding agent", which I guess means a tool like an AI coding CLI, and "stub", which appears only in a See-also blurb.
>
> Stumbles for this reader:
> - "Execution profile" is the key concept and is never defined here; the page only links to it.
> - "TUIs" and `ait board` appear without explanation.
> - It is unclear whether I need to do anything about the auto-created `-` folders showing up in `git status`.

**Follow-up report** (verbatim):

> Follow-up answers about the same page (page text only, no tools):
>
> 1. What was ambiguous?
> - Where "next to the skill" actually is. The page never says which directory skills live in.
> - Whether I should add the `-` variant folders to `.gitignore` myself or whether they are already ignored. "Never ... commit them" leaves this open.
> - When a variant gets rebuilt. It is created "the first time you need it", but the page doesn't say what happens later, for example after the skill or the profile changes.
> - Why a skill's file would change during a run at all. The "Why it exists" reasoning assumes this can happen but never says what changes it.
> - Skill naming. It is `/aitask-pick` in the agent but `pick` with `ait skillrun`. I can't tell whether the `aitask-` prefix is always dropped for `ait skillrun`.
> - What "saves it for later runs" saves to in the launch dialog: `userconfig.yaml`, `project_config.yaml`, or something else.
>
> 2. What did the page assume I already knew?
> - What an aitasks "skill" is and how you invoke it (a slash command inside a coding agent).
> - What an execution profile is, and which profiles exist (only `fast` and `default` are named).
> - Which coding agents are supported.
> - That `ait` is the CLI and that `ait board`, `ait settings` and the other TUIs exist.
> - Where `userconfig.yaml` and `project_config.yaml` live, and what format `default_profiles` takes.
> - That the `42` in the examples is a task number.
>
> 3. Terms I had to guess the meaning of:
> - skill
> - execution profile / profile
> - coding agent
> - TUI
> - launch dialog
> - `ait settings`
>
> 4. Details I did not need to answer the questions:
> - "Without a default, the skill uses the `default` profile."
> - The "(yours alone)" / "(your team's)" distinction between `userconfig.yaml` and `project_config.yaml`.
> - In the launch dialog, the choice between changing the profile "for one run" and saving it "for later runs".
> - "and other TUIs" (beyond `ait board`).
>
> 5. Does anything contradict something else?
> - Nothing outright contradicts. There is one tension: variants are created once ("the first time you need it"), yet the rationale worries about the file changing mid-run. The page doesn't explain how a file that was made once could change.
>
> GUESSED_TERMS=6 UNNEEDED_DETAILS=4

#### After (tuned procedure): `attachments.md` — guessed terms 7, unneeded details 5, score 12

**Answers** (verbatim):

> 1. An attachment is a file, such as a screenshot, a log or a PDF, that `ait attach` copies into the task's own storage. The copy lives with the task data and is committed to git like the task files.
>
> 2. Files that explain a task usually sit somewhere temporary, like a downloads folder, a scratch directory or a chat upload, so a task that only points at them loses them. Attaching keeps a copy with the task for as long as the task exists, whether it is active or archived.
>
> 3. To attach, run `ait attach add 42 screenshot.png`. To list a task's attachments, run `ait attach ls 42`. To get one back, run `ait attach get 42 screenshot.png --out /tmp/shot.png`. You refer to it by its name on the task, which is the file's name by default. I'm inferring that "42" means task t42 from the comment. The page doesn't say what `get` does without `--out`; my guess is that it writes to the current directory or to stdout.
>
> 4. You mostly don't deal with the hash, because you type the attachment's name in commands. In practice it means:
>    - the same file attached to two tasks is stored only once;
>    - a file whose contents change becomes a different attachment;
>    - every fetch is checked against the recorded hash, so a damaged copy gives you an error instead of bad data.
>    The page doesn't say what happens if I re-attach an edited file under the same name. My guess is that it errors or needs a different name.
>
> 5. Nothing happens to it. After the copy, the original can be moved, edited or deleted and the attachment stays.
>
> 6. Stored copies are deleted only when you run `ait attach gc` yourself, and it only removes copies that no task uses any more. `ait attach rm` takes the attachment off the task but keeps the stored copy, and archived tasks keep theirs. The page doesn't say whether deleting a task frees its copies for gc, or whether gc also removes them from git history. My guess is that they stay in history because they were committed.
>
> Points that confused me as a newcomer:
> - The page never says what "42" is or how tasks get numbers.
> - It's unclear whether "committed to git" happens automatically or whether I have to commit myself.
> - It doesn't explain what "stored copy" means compared with the attachment on a task.
> - The rule for when a stored copy counts as "used" by a task is left to the command reference.

**Follow-up report** (verbatim):

> **1. What was ambiguous**
> - In `ait attach add 42 …` the comment says "t42" but the command takes "42". It isn't clear whether a task's ID is "42" or "t42", or where the number comes from.
> - "committed to git like the task files": I can't tell whether `ait attach add` commits by itself or I have to commit.
> - The page has two layers, the attachment on a task (with a name) and the "stored copy" (keyed by hash), but never lays out how they relate.
> - "copies that no task uses any more": it doesn't say whether an archived task, or a task that was deleted, still counts as using a copy.
> - What `ait attach get` does without `--out`.
> - What happens if I re-attach an edited file under the same name. The page says it is "a different attachment" but not whether the name clashes or gets replaced.
> - Where "the task's own storage" actually is.
> - Whether `gc` also removes the copy from git history, since the copy was committed.
> - When attachments move during a fold, what happens if two attachments have the same name.
>
> **2. What the page assumed I already knew**
> - What an aitasks "task" is, and how tasks are numbered.
> - What the `ait` command is and how it gets installed.
> - What "archived" and "active" mean for a task.
> - That task data lives in git, and where it lives.
> - What folding is, beyond the short "merged into another task" in parentheses.
> - What a content hash is. I know this from git, but the page doesn't explain it.
> - What "gc" (garbage collection) means.
>
> **3. Terms I had to guess the meaning of**
> - t42 / task ID
> - task data
> - task's own storage
> - stored copy
> - archived (task)
> - active (task)
> - gc
>
> **4. Details I didn't need to answer the questions**
> - Two tasks can give the same file different names.
> - `ait attach ls 42`, the list command.
> - An archived task can still have its attachments listed and fetched.
> - You can't add new attachments to an archived task.
> - When a task is folded, its attachments move to the task it was merged into.
>
> **5. Contradictions**
> - I found no real contradictions.
> - One phrase could look like a contradiction at first: "changing a file's contents makes a different attachment" next to "the original can be … edited … and the attachment stays". On a careful read they agree: editing the original doesn't touch the stored copy.
> - "keeps a copy … for as long as the task exists" reads like the copy's lifetime ends with the task. In fact the copy can outlive the task until `gc` runs. That is loose wording, not a contradiction.
>
> GUESSED_TERMS=7 UNNEEDED_DETAILS=5

#### After (tuned procedure): `tasks.md (control)` — guessed terms 7, unneeded details 6, score 13

**Answers** (verbatim):

> 1. A task is one piece of work, written as a markdown file in the repository's `aitasks/` directory (for example `aitasks/t130_add_login.md`). The top of the file holds frontmatter with facts about the task, and the markdown below it describes the work.
>
> 2. The page says frontmatter is a block of `name: value` lines in YAML, placed between two `---` lines at the top of the file. Here it records facts about the task, such as its priority, its status and the tasks it waits for. The page doesn't define YAML itself; I'm assuming it's a common plain-text data format. The full list of fields is in the Task File Format reference, which the page links to but does not include.
>
> 3. Tasks live in the `aitasks/` directory of your own repository, and they are committed to git like source code.
>
> 4. The usual way is `ait create`, typically started from the board, which is a full-screen terminal app. A coding agent can also create tasks: `/aitask-explore` and `/aitask-wrap` make them from the code you're working on, and `/aitask-pr-import` turns a pull request into one. The page doesn't say what `ait create` asks for or what flags it takes, so I'd have to follow the link.
>
> 5. Every change to a task is recorded in git history. A coding agent can also read and edit tasks with the same tools it uses for code. The page adds that the frontmatter is small enough for an agent to keep in mind, yet still enough to sort tasks by priority, order them by what they wait for, and show them as cards on a board.
>
> 6. All parts of aitasks read and write the files directly: the `ait` command line, its terminal apps (TUIs) such as the board, and the skills. Skills are the instructions a coding agent such as Claude Code follows when you type a command like `/aitask-pick`. The page doesn't say outright whether I can edit a task file by hand. My guess is yes, since it's a plain file in git, but the page doesn't say whether that's supported.
>
> Things that tripped me up as a newcomer:
> - "Skills" is defined well enough to follow.
> - It's unclear whether the `t130` prefix is a number I choose or one the tool assigns.
> - I couldn't tell how to start the board.
> - I don't know what an "approved task" is (the Plans link mentions it).

**Follow-up report** (verbatim):

> Follow-up answers about the "Tasks" page, from the page text alone.
>
> **1. What was ambiguous**
> - Whether I pick the `t130` in `t130_add_login.md` or the tool assigns it, and what the `t` stands for.
> - "typically started from the board": I couldn't tell whether `ait create` is a shell command I type, an action inside the board, or both. I also don't know how to open the board.
> - "the ones the workflow writes for itself": I don't know what "the workflow" is, or whether some fields are off-limits for me to edit.
> - "Every part of aitasks reads and writes these files directly": the page never says whether I may hand-edit a task file in my editor.
> - "All of them just write a file into `aitasks/`": I couldn't tell whether that includes a git commit, or whether I have to commit it myself.
> - "the tasks it waits for": dependencies, presumably, but the page doesn't say how they are written (ids? filenames?).
> - "small enough for an agent to keep in mind" is a vague size claim.
> - "cards in the columns of a board": the page doesn't say what the columns stand for (status? something else?).
>
> **2. What the page assumed I already knew**
> - What markdown is.
> - What YAML is. The page explains frontmatter but not YAML itself.
> - What a coding agent is, what Claude Code is, and that typing `/something` to an agent runs a command.
> - That `ait` is installed and the repository is already set up for aitasks.
> - What the possible status and priority values are.
> - That I know what to do with a task once it exists (how work actually starts on it).
>
> **3. Terms I had to guess the meaning of**
> - YAML
> - coding agent
> - "the workflow" (as in "fields the workflow writes for itself")
> - board, including what its columns and cards are
> - status (what values it takes)
> - "waits for" (I guessed it means dependencies)
> - the `t130` id prefix (task numbering)
>
> **4. Details I did not need to answer the questions**
> - The `/aitask-pick` example command.
> - The sentence that the frontmatter is "small enough for an agent to keep in mind, and still enough to sort tasks by priority, order them by what they wait for, and lay them out as cards in the columns of a board."
> - The specific skill names and what each one does (`/aitask-explore`, `/aitask-wrap`, and `/aitask-pr-import` turning a pull request into a task). "An agent can also write tasks" was enough.
> - "All of them just write a file into `aitasks/`."
> - The pointer to the "Capturing ideas" and "Create tasks from code" workflows.
> - The pointer to the Task File Format reference, including "the ones the workflow writes for itself".
>
> **5. Contradictions**
> - I found no outright contradiction.
> - One mild tension: the first section calls frontmatter "facts about the task" such as priority and status. The reference pointer then says some fields are written by "the workflow for itself". That hints at fields the user doesn't own, which the first section never mentions. It's a gap rather than a contradiction.
>
> GUESSED_TERMS=7 UNNEEDED_DETAILS=6

#### After (tuned procedure): `plans.md (control)` — guessed terms 8, unneeded details 5, score 13

**Answers** (verbatim):

> 1. A plan is a step-by-step description of how a task will be done, written and approved before any code changes. It is a markdown file that gives a summary of the context, the implementation steps, the files that will change and how to check the result.
>
> 2. A coding agent writes it while it plans the task. That happens when you run a skill (a command you type to the agent), such as `/aitask-pick` or `/aitask-explore`.
>
> 3. The page says I approve the plan "before any code changes" and "once, in plain words", but it never says how. Guess: the agent shows me the plan in the chat and asks me to confirm before it starts coding, and I either say yes or ask for changes.
>
> 4. Plans are kept in my repository's `aiplans/` directory and named after their task. For example, the plan for `aitasks/t130_add_login.md` is `aiplans/p130_add_login.md`. Child tasks' plans are stored somewhere else, but the page only links to the Task File Format reference for that and doesn't say where.
>
> 5. As the agent works, it adds to the plan what it did differently, what I asked it to change at review, and its final notes. When the task is finished and archived, the plan stays as the long-term record of how the task was built. For a child task, agents working on sibling tasks read it first, and the Code Browser shows it beside the code it explains. The page doesn't say whether the plan file moves anywhere when it is archived. Guess: it might go to something like an archive subfolder of `aiplans/`, the same way the task moves out of the open list.
>
> 6. Normally no, because the skills produce the plan and "you do not normally write the file by hand." The word "normally" suggests I could, but the page never says when or why I would. Guess: hand-editing is possible but unusual, maybe for fixing up a plan before approving it.
>
> Points where I stumbled as a fresh reader:
> - How to approve a plan (Q3) is the main thing missing, even though the description and first paragraph present approval as central.
> - "Archived" is defined only as "moved out of the list of open tasks," so it is unclear whether the plan file moves too.
> - The child-task sentence in "Why it exists" is long and hard to follow on a first read.
> - The "Verified scores" link in See also has no clear connection to plans.

**Follow-up report** (verbatim):

> Follow-up answers (from the page text alone):
>
> 1. What was ambiguous
> - How I approve a plan. Approval is presented as central, but the page never says how it is given (in the chat, a command, editing the file).
> - "Fixed plan to follow" doesn't fit with the agent later adding "what it did differently". I couldn't tell whether the plan is fixed or a living document.
> - "what you asked it to change at review": I couldn't tell which review is meant (the plan review before coding, or a code review after it).
> - "archived (moved out of the list of open tasks)": I couldn't tell whether the plan file itself moves or stays in `aiplans/`.
> - "the agents that work on its sibling tasks ... read its plan first": I couldn't tell what "first" means (before planning their own task? only once this child is finished?).
> - "you do not normally write the file by hand": the page never says when I would.
> - "The file's header": I couldn't tell what header a markdown plan has.
> - Where child tasks' plans are stored is mentioned but only deferred to another page.
>
> 2. What the page assumed I already knew
> - What a "task" is in this tool, and the task file naming (`aitasks/t130_add_login.md`, task numbers).
> - What a "coding agent" is and how to run one.
> - That typing a `/name` command to the agent is how you run things (slash-command convention).
> - That the tool is set up in my repo with an `aitasks/` and `aiplans/` layout.
> - That there is a review step in the workflow.
> - What parent and child tasks are, and how a task gets split.
> - That I can read markdown files.
>
> 3. Terms I had to guess the meaning of
> - coding agent
> - task (in this tool's specific sense)
> - child task / parent task / sibling tasks (what "splitting" a task means)
> - review ("at review")
> - the file's header
> - `/aitask-pick` (what "pick" does)
> - `/aitask-explore` (how it differs from pick)
> - implementation contract (description line)
>
> 4. Details I did not need to answer the questions
> - "A plan keeps deciding what to do apart from doing it" (the rationale)
> - "the agent then has a fixed plan to follow"
> - The gloss of the Code Browser as "a terminal app for reading the project's code"
> - "The file's header ... are in the Task File Format reference" (the header part)
> - The gloss of sibling tasks as "split from the same parent"
>
> 5. Contradictions
> - No hard contradiction. One tension: the description and "a fixed plan to follow" present the plan as settled before coding, but the same section says the agent keeps adding deviations, review changes and final notes as it works. The page doesn't reconcile "fixed" with "updated".
>
> GUESSED_TERMS=8 UNNEEDED_DETAILS=5


## Inventory

Measured at HEAD 9b54f33d8 before any edit. Type: every leaf page is an
explanation page; `_index.md` is an overview (link list, no `depth` needed).
Anti-pattern numbers are Diátaxis (1 tutorial that explains, 2 how-to that
teaches, 3 reference as narrative, 4 explanation with procedures, 5 mixed page,
e.g. reference tables in an overview). "Level" = the guide's level contract for
the page's `depth`; "prose" = the guide's avoid list.

| Page | Lines | depth (before → after) | Verdict | Violations |
|---|---|---|---|---|
| `_index.md` | 47 | — (link list) | ok | none |
| `agent-attribution.md` | 34 | advanced | ok | none material at `advanced` |
| `agent-memory.md` | 32 | advanced | ok | last page in the index list, correctly has no Next footer |
| `agentcrews.md` | 79 | advanced | ok | internal path and status lifecycle under "What it is" are allowed at `advanced`; decorative bold (prose) left for a later pass |
| `artifacts.md` | 56 | advanced | minor → fixed | rules under "What it is" (three `gitbranch` rules, already stated on `commands/artifact.md`) |
| `attachments.md` | 164 | intermediate | **restructure** | AP5 (field table, storage layout, gc rules); 5 `###` under "What it is"; internal paths; config key + timing value |
| `cross-repo-references.md` | 64 | intermediate | ok | one em-dash connector |
| `execution-profiles.md` | 39 | intermediate | ok | key list is allowed at `intermediate` |
| `folded-tasks.md` | 29 | intermediate | minor → fixed | writer convention ("This wording matters…") aimed at contributors; staged contrast "merged, not superseded"; decorative bold |
| `framework-session.md` | 198 | advanced → intermediate | **restructure** | AP5; 6 `###` under "What it is"; internal paths, modes, state diagram, leases, version-specific measurements; "freeze" never defined |
| `gates.md` | 237 | advanced → intermediate | **restructure** | AP5; 8 `###` under "What it is"; resolution/digest/registry rules; field tuple; contradiction "filtered gate never blocks" vs fallback |
| `git-branching-model.md` | 40 | advanced | ok | branch table allowed at `advanced` |
| `ide-model.md` | 34 | advanced | ok | none material |
| `implementation-trails.md` | 65 | advanced | ok | reads at a lower level than its tag; left as is |
| `locks.md` | 127 | main-concept | **restructure** | AP5 (two outcome tables); 5 `###`; status lines (`LOCK_FAILED`, `NO_SESSION_ANCHOR`, `REFUSED_LIVE_HOLDER`); internal paths; env var; prose (staged contrast, closing line, decorative bold); contradictions on release vs reclaim |
| `parent-child.md` | 30 | main-concept | minor → fixed | path patterns and `children_to_implement` field name; "agent session" / "context" undefined; em dashes |
| `plans.md` | 30 | main-concept | minor → fixed | child-plan path pattern; "skill" undefined; approval left implicit |
| `review-guides.md` | 28 | intermediate | ok | frontmatter field names allowed at `intermediate` |
| `shadow-agent.md` | 66 | intermediate | ok | none |
| `skill-templating.md` | 190 | intermediate | **restructure** | AP5 (per-agent table, dispatch steps, gitignore globs); authoring material for contributors; "skill"/"profile" undefined; 3 `###` |
| `task-lifecycle.md` | 40 | main-concept | minor → fixed | internal path `aitasks/archived/`; links to implementation scripts; em dashes |
| `task-notes.md` | 62 | intermediate | ok | none |
| `tasks.md` | 32 | main-concept | minor → fixed | eight frontmatter field names under "What it is"; "YAML frontmatter", TUI, skill, LLM, Kanban undefined |
| `topic-anchoring.md` | 141 | main-concept | **restructure** | non-standard sections (no "Why it exists" / "How to use"); storage, normalization and flag rules; script paths; key order |
| `verified-scores.md` | 37 | advanced | ok | bucket table allowed at `advanced` |

All 24 leaf pages carry `depth` (list form). Retags: `gates` and
`framework-session` `advanced → intermediate` (their concept pages now hold
only what a user who picks tasks and freezes agents needs; the rules moved to
`development/`).

## Moved-fact table

Steps 3–4. Steps 3 were drafted by four restructure agents working in parallel on
disjoint file sets (brief: `restructure_brief.md`, reproduced in their
prompts), then reviewed in this session. Each agent's report, including its
moved-fact table, its code-verified corrections and its open points, is
reproduced verbatim below. Step 4 rows (edited directly) follow.

### Restructure report: `locks.md` (verbatim)

## Report: `concepts/locks.md` restructure

The concept page is now 74 lines and has the five sections. Everything I cut from it moved to `commands/lock.md` or to the new `development/merge-mutex.md`, or is linked where `workflows/crash-recovery.md` already says it. `python3 check_links.py --build` ran clean (`SWEEP: PASSED`, 0 broken). Nothing is committed or staged, and the shared-file gate was clean for all five files.

### 1. Files changed or created (all under /home/ddt/Work/aitasks/website/content/docs/)

| file | lines old → new | depth old → new |
|---|---|---|
| `concepts/locks.md` | 127 → 74 | main-concept → main-concept |
| `commands/lock.md` | 145 → 165 | intermediate → **advanced** (it now has the 7-row outcome table, and it already had exit codes, status tokens and the internal branch and file paths) |
| `development/merge-mutex.md` (NEW, weight 55) | — → 82 | — → advanced |
| `workflows/crash-recovery.md` | 188 → 188 | intermediate (unchanged). Only two See-also descriptions changed, because the concept page no longer holds the branch or the lock metadata. |
| `workflows/parallel-development.md` | 75 → 75 | advanced (unchanged). The two inbound anchors now point to `development/merge-mutex` (`#recovering-a-stuck-merge-mutex` and the page itself). |

- **Link form:** in the four files I edited for content, relref anchors now sit outside the shortcode, as `documentation_conventions.md` asks. In `parallel-development.md` that changed the form of one existing link, not where it goes.
- **Internal links to the removed concept section:** `commands/lock.md` linked to that section twice (the exit-code row and the "How It Works" paragraph). Both now point to its own new `#when-a-pick-meets-a-held-lock` section.

### 2. Moved-fact table

| source page#section | fact (short) | destination page#anchor | status |
|---|---|---|---|
| locks#what-it-is ¶1 | two locks; task lock = who owns the task; merge mutex = one merge at a time, because it runs in the shared root | concepts/locks#what-it-is and #why-it-exists, in plain words | moved (rewritten) |
| locks#what-it-is ¶2 | task lock recorded on the `aitask-locks` branch; holds email, hostname, timestamp, session process | commands/lock#how-it-works (YAML plus the pid paragraph) | already-stated |
| locks#what-it-is ¶2 | released on archival, abort or explicit unlock | commands/lock#how-it-works (new paragraph) and concepts/locks#how-to-use (plain words) | moved |
| locks#what-it-is ¶2 | stale locks force-unlockable, optionally with a confirmation prompt | commands/lock#when-a-pick-meets-a-held-lock (prompt in the interactive pick; `/aitask-pickrem` without a prompt only when `force_unlock_stale` is set) | corrected (made precise, see 4) |
| locks#what-the-lock-actually-excludes | lock belongs to the session, not the person; same email does not mean same worker | commands/lock#when-a-pick-meets-a-held-lock (one sentence) and concepts/locks#why-it-exists; crash-recovery#when-the-holder-is-still-running also states it | moved / already-stated |
| same | 7-row competing-pick outcome table, including "different owner → `LOCK_FAILED`, naming the owner" | commands/lock#when-a-pick-meets-a-held-lock | moved |
| same | refusals happen before lock, status and commit; task left as it was | crash-recovery#when-the-holder-is-still-running (linked from lock.md) | already-stated |
| same | overrides: force option at the prompt, or `ait lock --unlock` in the holding session | crash-recovery#when-the-holder-is-still-running (linked) | already-stated |
| same | a lock that never named a process stays reclaimable, never stuck | crash-recovery#when-the-holder-is-still-running (third bullet) and the lock.md table row | already-stated |
| locks#the-merge-mutex | serializes the end-of-task merge (task branch → output branch); runs in the shared root, so one HEAD, index and tree | development/merge-mutex#what-it-serializes | moved |
| same (note) | `/aitask-web-merge` and hand-run git do not take it | merge-mutex#what-it-serializes | moved; the closing line "does not police the repository" was dropped because it only restates the note (the guide's own example) |
| locks#what-the-merge-mutex-excludes | one global lock per repo, not per branch, and why | merge-mutex#what-it-serializes | moved |
| same | 4-row holder/outcome table (queueing, which task you wait on, wait budget, provably gone, cannot tell) | merge-mutex#what-the-next-task-does | moved |
| same | same rule as the task lock; automatic path only takes a provably-gone holder, manual recovery can also clear an unverifiable one | merge-mutex#what-the-next-task-does | moved |
| locks#the-reservation-outlives-the-command | three short-lived commands; anchored to the session, not the process | merge-mutex#the-reservation-lasts-the-whole-merge | moved |
| same | held through conflict resolution, verification and cleanup, and why | same | moved |
| same | "nothing releases this lock automatically"; a dead session leaves it held | same, restated precisely: only the holder releases it, no timeout or background job does, the next task reclaims only a provably-gone holder | moved (contradiction resolved) |
| locks#before-a-merge-can-start | `NO_SESSION_ANCHOR` refusal before anything is acquired; tmux pane; `AIT_AGENT_PID` requirement; not enforced; the two failure directions | merge-mutex#the-session-anchor | moved |
| locks#recovering-a-stuck-merge-mutex | `ait lock` does not cover it; status, rmdir guard, dry-run `force-release`, armed command | merge-mutex#recovering-a-stuck-merge-mutex | moved (code blocks verbatim) |
| same | the three properties (`REFUSED_LIVE_HOLDER`, `--abort-merge`/`--reset-hard`, failure reported) | same | moved. "Either the mutex is released, or the tool tells you why" was dropped as a closing restatement of the sentence before it. |
| same | do not run `/aitask-web-merge` during a task's merge step | same | moved |
| locks#why-it-exists ¶1 | multiple PCs, devs and sessions; conflicting branches and commits; shared email; git instead of a backend; force-unlock is a commit | concepts/locks#why-it-exists | kept (plain words). "archival records" was folded into "branches and commits". |
| locks#why-it-exists ¶2 | merge is the one step in the shared root; index race; conflict work taken into the next commit | concepts/locks#why-it-exists | kept (plain words) |
| locks#how-to-use | invisible; `/aitask-pick` and the board take and release locks; `ait lock` operations | concepts/locks#how-to-use, plus commands/lock | kept / already-stated |
| locks#how-to-use ¶2 | merge mutex taken before the merge and released after cleanup; not covered by `ait lock`; `aitask_merge_task.sh status`/`force-release` | concepts/locks#how-to-use (plain words, link) and merge-mutex#recovering-a-stuck-merge-mutex | kept / moved (the script path left the concept page) |
| locks#see-also | all entries | concepts/locks#see-also, plus a new entry for the merge-mutex page | kept |

The concept page now says the two things that looked contradictory in a way that keeps both:
- **A crashed agent cannot release its lock.** The next agent can take it over once aitasks can tell the old one is gone. For a task lock it asks you first; for the merge mutex it does so on its own.
- **You can also clear a left-over lock by hand.** The release-versus-reclaim distinction is stated exactly on both reference pages.

### 3. Skipped files
None.

### 4. Facts found wrong or made precise
- **"Stale locks can be force-unlocked, optionally with a confirmation prompt."** I made this precise from the code:
  - `.claude/skills/task-workflow/SKILL.md:245-251`: on `LOCK_FAILED`, the interactive pick asks "Force unlock and claim" / "Pick a different task".
  - `.claude/skills/aitask-pickrem/SKILL.md.j2:190-198`: `/aitask-pickrem` forces only when `force_unlock_stale` is set and otherwise stops. `skills/aitask-pickrem.md` already documents that key.
- **Wrong fact outside my file set:** `development/_index.md` "Atomic Task Locking" says "Locks are idempotent: the same email can refresh its own lock". `aitask_lock.sh:221-273` refuses the same email from another live or unverifiable session on the same host (exit 13/14). Only the same session refreshes silently. Its owner should fix this.
- **Verified in code, no change needed:** the merge-mutex facts (`NO_SESSION_ANCHOR`, `REFUSED_LIVE_HOLDER`, the `--abort-merge`/`--reset-hard` residue remedies, the guard `rmdir` hint) match `.aitask-scripts/aitask_merge_task.sh`. The task-lock outcome rows match `aitask_lock.sh` and `aitask_pick_own.sh`.

### 5. Guide rules unclear or ill-fitting
- **"Do not add facts the source pages do not state":** making the force-unlock sentence precise needed a fact from another site page (`force_unlock_stale`, on `skills/aitask-pickrem.md`) plus a code check. It is unclear whether a fact stated on a non-source site page counts as "added". I treated it as a correction and reported it above.
- **Weight collisions:** the new-page weight range (40–75) has no coordination between parallel agents. I used 55; `development/gates.md` took 50.
- **Defining "merge mutex":** the guide's main-concept example keeps the name "merge mutex" without defining "mutex". I followed it and introduced it only as "a second lock, the merge mutex".

### Restructure report: `gates.md` (verbatim)

## Report: restructuring `concepts/gates.md`

The shared-file gate was clean for every file I touched. `check_links.py --build` passed: `SWEEP: PASSED`, 0 broken links. Nothing was committed or staged.

### 1. Files changed or created
| file | lines old → new | depth old → new |
|---|---|---|
| /home/ddt/Work/aitasks/website/content/docs/concepts/gates.md | 237 → 90 | `[advanced]` → `[intermediate]` (retag as assigned: with the rules gone, its reader is someone who picks and archives tasks) |
| /home/ddt/Work/aitasks/website/content/docs/development/gates.md (NEW, title/linkTitle "Gate rules", weight 50) | 0 → 221 | `[advanced]` |
| /home/ddt/Work/aitasks/website/content/docs/commands/gates.md | 244 → 245 | `[advanced]`, unchanged |
| /home/ddt/Work/aitasks/aidocs/gates/gate-guarded-archival.md | 249 → 256 | n/a |

- **Concept page:** I also tightened its description, which promised "why the enforced set is fixed" mechanism.
- **Body length:** about 80 lines, above the 30–60 target. The extra comes from the failed-gate steps and the term definitions that fresh readers asked for.
- **commands/gates.md:**
  - The intro now links to the new Gate rules page as well as the concept page.
  - The `--gate` row now says it runs even if the gate already passed or its retry budget is spent. That fact was already on `skills/aitask-run-gates.md#arguments`, and I checked it in `_force_one` in `.aitask-scripts/lib/gate_orchestrator.py`, whose docstring says "overriding skip-already-passed + budget".
- **aidocs:** added a "Digest encoding" paragraph. It records the three 12-hex sha256 prefixes joined by dots, in the order `<gates>.<profile>.<outputs>`, built by `_hash12`/`build_active_digest` in `lib/gate_ledger.py` with the bash twin `_gate_hash12`. This was not in aidocs before.

### 2. Moved-fact table
| source page#section | fact (short) | destination page#anchor | status |
|---|---|---|---|
| What it is | gate definition and examples | concepts/gates#what-it-is | kept (plain) |
| What it is | gates sit beside `status`; they come into play while Implementing | concepts/gates#what-it-is | kept (rephrased: "while the task is being implemented") |
| What it is | two sets: `gates:` is intent (you or a profile writes it), `active_gates` is derived and never hand-edited | development/gates#declared-gates-and-the-enforced-set | moved; one plain sentence kept on the concept page |
| Declared vs enforced | profile ceiling (`rendered_gates`, defaults to `default_gates`), intersection, diagram | development/gates#declared-gates-and-the-enforced-set | moved (diagram code block unchanged) |
| Declared vs enforced | four fields form one tuple written together; `_filtered` blocks nothing and is kept | same | moved |
| Declared vs enforced | empty set written as `[]` | same | moved; the vague "means something different" is now stated concretely (a missing tuple means the task is enforced from raw `gates:`), as the digest section says |
| Declared vs enforced | `gates: []` is an opt-out and never backfilled | same | moved (task-format row already states it in part) |
| Declared vs enforced | manual-verification tasks keep only reachable gates | same | moved |
| Snapshot | computed at pick and stored, not on read; re-pick re-derives | development/gates#when-the-enforced-set-is-computed | moved; a plain version kept on the concept page |
| Snapshot | why: profile is per-session, so one answer per session | same | moved |
| Snapshot | profile unreadable means the tuple is cleared | same | moved |
| Digest | three 12-character hashes joined by dots | aidocs/gates/gate-guarded-archival.md "Digest encoding" | moved (contributor-only) |
| Digest | the three inputs; parts 1 and 3 checkable from the task file; the two failure modes; fallback to raw `gates:`; part 2 caught at next pick | development/gates#the-digest | moved |
| Digest | the fallback errs toward over-blocking, and why | same | moved, plus a paragraph reconciling it with "filtered never blocks" (see section 4) |
| Kinds of gate | machine / human (the three human gates and how they differ) / procedure-backed | development/gates#kinds-of-gate | moved; "attended" and "headless engine" are now defined in place |
| Kinds of gate | `ait gate pass` refuses `plan_approved`; signature bound to the code | commands/gates#ait-gate-pass | already-stated (also kept on the development page) |
| Ledger | append-only `## Gate Runs`, block first line, never rewritten | development/gates#the-ledger | moved |
| Ledger | derived state, latest wins, `pass`/`skip` satisfied | same | moved (board reference also states the `skip` rule) |
| Ledger | checkpoints for resume vs archival | same | moved |
| Registry | the key table | development/gates#the-registry | moved |
| Registry | `sync-registry` fills missing keys, reports differing values | commands/gates#ait-gates-sync-registry | already-stated; linked |
| Retry/unlock | budget, only `fail`/`error` spend it, exhausted waits, humans don't retry | development/gates#retry-budgets | moved; plain version on the concept page |
| Retry/unlock | linear vs registry-driven order, fan-out, readiness, `max_parallel_gates` | development/gates#the-unlock-order | moved |
| Archival | every enforced gate satisfied, stale signature, filtered never blocks, archive command refuses unless overridden | development/gates#archival | moved; the override is now named (see section 4); a plain version is on the concept page |
| Archival | dependents unblocking: `blocks_dependents`, `also_blocks_dependents`, filtered additions dropped, ordinary release | development/gates#unblocking-dependents | moved; one plain sentence on the concept page |
| Why it exists | status can't hold independent facts; survives crashes; syncs | concepts/gates#why-it-exists | kept |
| Why it exists | intent vs enforced lets a task move between workflows; fixed at pick | concepts/gates#why-it-exists | kept |
| Why it exists | "the digest stops a stored decision from outliving its inputs" | development/gates#the-digest (first sentence) | moved |
| How to use / See also | `--gates`, `default_gates`, commands, skill, board, all See also links | concepts/gates | kept; added links to Gate rules and Task lifecycle |

New on the concept page, addressing what fresh readers stumbled on:
- "archive", "pick" and "execution profile" are defined at first use.
- "ceiling", "attended" and "headless" no longer appear there.
- A three-step "when a gate fails or has used up its retries" list: `ait gate log`, then `ait gates run --gate`, then `ait gates sync-registry`.

### 3. Skipped files
None.

### 4. Facts checked in code, and an owner left undecided
- **Archive override (newly named on the site):** the brief only said the archive refusal can be overridden. I verified the override as the `--ignore-gates` flag of `.aitask-scripts/aitask_archive.sh` (help lines 81–83 and 106–110, handled by `gate_guard` at line 1109). Before this, no site page named it. The development page shows `./.aitask-scripts/aitask_archive.sh --ignore-gates <id>`, following the precedent of `--with-deferred-carryover` on `workflows/manual-verification.md`.
- **The contradiction, reconciled:** I verified it in `read_active_tuple_from_text` in `lib/gate_ledger.py`. When the digest fails, `active_gates` and `active_gates_filtered` are both set aside together. The development page now says the filter applies while the stored tuple is valid, and that the fallback is the case where the stored tuple, its filter list included, is no longer trusted. Both facts are kept.
- **Possible pre-existing doc drift (not fixed):** the help text of `aitask_archive.sh` says "not all `pass`", but archival treats `skip` as satisfied too.
- **Owner undecided:** the code also has a stopping rule: two identical failures with no code change count as exhausted (`blocked: exhausted (stopping heuristic…)` in gate_orchestrator.py). No source page stated it, so I added it nowhere. It is a candidate for `commands/gates.md`'s line table.
- **Inbound links others may want to retarget:** `tuis/board/reference.md#gate-progress` and `development/task-format.md` (the `gates` row) link to `concepts/gates` for the declared-vs-enforced distinction. The concept page still states it in one sentence, but the details now live in `development/gates`. Both files are outside my set, so I left them.

### 5. Guide rules that did not fit
- **Weight collisions:** the 40–75 range for new `development/` pages gives parallel agents no way to avoid picking the same weight. I picked 50.
- **Body length vs. fresh-reader fixes:** the 30–60 line target conflicts with the requirement to define every stumbled-on term and give concrete failure steps on an `intermediate` concept page. That pushed this page to about 80 body lines.

### Restructure report: `framework-session.md + skill-templating.md` (verbatim)

## Report: `concepts/framework-session.md` and `concepts/skill-templating.md` restructured

Both concept pages now have the five-section shape, and every cut fact has a new home. `check_links.py --build` passes: 0 broken links and every control check true. Nothing was committed or staged.

### 1. Files changed or created
| File | Lines old → new | depth old → new |
|---|---|---|
| website/content/docs/concepts/framework-session.md | 198 → 62 | advanced → **intermediate** (retag as the assignment asked: its reader uses freeze and restore) |
| website/content/docs/development/framework-session.md (NEW, weight 62) | – → 113 | – → advanced |
| aidocs/framework/agent_session_store.md (NEW) | – → 58 | n/a |
| website/content/docs/commands/setup-install.md (session-hooks paragraph only) | 156 → 156 | unchanged (none set) |
| website/content/docs/workflows/freeze-and-restore-agents.md (link retargets only) | 316 → 317 | intermediate (unchanged) |
| website/content/docs/tuis/frozenagent/reference.md (one-word correction) | 124 → 124 | advanced (unchanged) |
| website/content/docs/concepts/skill-templating.md | 190 → 57 | intermediate (unchanged) |
| website/content/docs/development/skill-templating.md (NEW, weight 67) | – → 62 | – → advanced |
| website/content/docs/skills/aitask-pick/execution-profiles.md | 120 → 139 | advanced (unchanged) |
| website/content/docs/commands/_index.md (one link) | 149 → 149 | unchanged |

`development/skills/_index.md` lists framework-development skills, so skill templating did not fit there and got its own new page. Another agent has already used development weights 50 (`gates.md`) and 55 (`merge-mutex.md`); I took 62 and 67.

Inbound anchors I retargeted:
- `workflows/freeze-and-restore-agents.md`: the two links to `concepts/framework-session#the-session-hook` now point to `development/framework-session#which-cli-owns-the-session` and `#when-it-records`. Its See-also line now also links the development page.
- `commands/_index.md:83`: `../concepts/skill-templating/#invocation-paths` now points to `{{< relref "/docs/skills/aitask-pick/execution-profiles" >}}#ait-skillrun`.

### 2. Moved-fact table
Abbreviations: FS = concepts/framework-session.md, ST = concepts/skill-templating.md, dev/FS = development/framework-session.md, dev/ST = development/skill-templating.md, aid = aidocs/framework/agent_session_store.md, WF = workflows/freeze-and-restore-agents.md, EP = skills/aitask-pick/execution-profiles.md.

| source page#section | fact (short) | destination page#anchor | status |
|---|---|---|---|
| FS#what-it-is | what a record holds: project, window, task, agent/model, session id, lifecycle; one per agent machine-wide | FS#what-it-is (plain form) + dev/FS#where-the-state-lives | moved |
| FS#what-it-is | records file `~/.config/aitasks/agent_sessions.json`, mode 0600 | dev/FS#where-the-state-lives | moved |
| FS#what-it-is | `aitask_agent_sessions.sh` is the only writer; readers take no lock and see one whole generation | dev/FS#who-writes-it | moved (public half) |
| FS#what-it-is | the lock around each read-modify-write and the atomic replace | aid "How the single-writer guarantee is implemented" | moved (contributor half) |
| FS#what-it-is | capture dir `frozen/<id>/` (0700), `capture.ansi` / `capture.txt` | dev/FS#where-the-state-lives (WF#limits already gives the path) | moved |
| FS#identity-versus-location | identity = root + window + slot (slot defined) | dev/FS#identity-and-location | moved |
| FS#identity-versus-location | pane id / pid are location; restart, reattach or respawn replaces them; no second record | dev/FS#identity-and-location | moved, plus a code-verified rule on taking over a record (see 4) |
| FS#identity-versus-location | `@aitask_record` join, stamped after the write, dies with the pane; two more options; not trusting a process name | dev/FS#identity-and-location | moved (option names already in aidocs tmux_gateway.md, which aid links) |
| FS#states | five-state diagram, guarded transitions, the transitional states, who owns `aborting` | dev/FS#states | moved (code block unchanged) |
| FS#operation-leases | coordinator, lease = nonce + pid, matching nonce, a race loser writes nothing | dev/FS#operation-leases | moved |
| FS#operation-leases | reconcile leaves a record alone while the owner is alive or the lease is under 60 s | dev/FS#operation-leases (links WF#when-something-goes-wrong for when it runs) | moved |
| FS#the-session-hook | `ait setup` installs the hook; it records the session id, writes nothing into the session, always exits successfully | commands/setup-install#session-hooks | already-stated (linked from FS and dev/FS) |
| FS#the-session-hook | records only in the agent's own pane; the Codex app-server daemon case | dev/FS#when-it-records | moved |
| FS#the-session-hook | how the CLI is identified (names itself, transcript path shape, path must match, inheritance, disagreement records nothing) | dev/FS#which-cli-owns-the-session | moved |
| FS#the-session-hook | a restore resumes only with the same CLI; recovered agent/model; refused otherwise; re-pick remains | WF (lines 75–84) + dev/FS#which-cli-owns-the-session | already-stated in WF; kept on dev/FS. "raw sessions" is now spelled out as the default agent for the `raw` operation, linked to `commands/codeagent#operations` |
| FS#the-session-hook | restore acknowledgement: record id and nonce in the environment, store compares sessions, only a verified restore deletes the capture | dev/FS#restore-verification (outcome table already in WF#what-unverified-means) | moved |
| FS#the-session-hook | a resumed Codex agent is verified by the transcript it holds open; a match deletes the capture, a mismatch aborts | dev/FS#restore-verification | moved |
| FS#the-session-hook | Codex 0.163.0 / 0.153.4 timing measurements | aid "Codex hook timing (measured)" | moved (contributor-only) |
| FS#the-session-hook | read from `/proc` on Linux, from `lsof` on macOS | aid "How the open transcript is read" | moved (contributor-only) |
| FS#the-session-hook | unverified outcome after `frozen.restore_ack_grace`; keeps the capture; when it happens | dev/FS#restore-verification (grace links tuis/frozenagent/reference#configuration) | moved |
| FS#the-session-hook | a late hook report is never refused; the upgrade-to-verified rule; other late reports update the record | dev/FS#restore-verification | moved (WF already states the Codex upgrade) |
| FS#cleanup-rules | positive evidence only; a partial view suppresses removal; transitional records exempt | dev/FS#cleanup-rules | moved |
| FS#cleanup-rules | `dead_window` / `dead_pane` / `capture_missing` table | dev/FS#cleanup-rules | moved; `dead_window` stated precisely from code (see 4) |
| FS#cleanup-rules | run by the monitor/minimonitor maintenance tick and by the coordinator after each operation | dev/FS#cleanup-rules (also WF#when-something-goes-wrong) | moved |
| FS#overrides | `AITASKS_AGENT_SESSIONS_FILE`, `AITASKS_FROZEN_DIR` table; unusual home layout | dev/FS#overrides | moved |
| FS#overrides | the test suite uses them | aid "Overrides and the test suite" | moved (test strategy) |
| FS#why-it-exists | panes die, get recycled, renamed, split; the record lives outside tmux, machine-wide | FS#why-it-exists | kept (rewritten, adds one-sentence definitions of freeze and restore) |
| FS#how-to-use / see-also | entry points and links | FS#how-to-use (numbered steps), FS#see-also (+ dev/FS, setup-install#session-hooks) | kept / expanded |
| setup-install#session-hooks | "(measured on Codex 0.163.0; Codex 0.153.4 …)" | aid "Codex hook timing (measured)" | moved (contributor-only) |
| ST#what-it-is | template `SKILL.md.j2` + stub on each agent's surface; stub resolves, renders, reads | dev/ST#the-two-pieces, #how-dispatch-works | moved ("discovery surface" defined) |
| ST#why-it-exists | the agent re-reads the skill file mid-run, so the variant stays fixed; one template instead of "if your profile…" prose | ST#why-it-exists | kept (plain form) |
| ST#why-it-exists | minijinja, the default/fast/remote flows | dev/ST#the-two-pieces | moved |
| ST#invocation-paths | in-session `--profile`, stripped and the rest forwarded; argument variable names per agent | EP#profile-override-argument (already stated) + dev/ST#how-dispatch-works | already-stated + moved, Gemini dropped (see 4) |
| ST#invocation-paths | fallback userconfig → project_config → interactive; `<short_name>` | EP#resolution-order (already stated); short name defined in EP and dev/ST | already-stated |
| ST#invocation-paths | `ait skillrun`, agent from `$AIT_AGENT_STRING` / `$DEFAULT_AGENT_STRING`, `--agent-string`, `--profile-override`, `_skillrun_<unique>.yaml` deleted on exit, `--dry-run` | EP#ait-skillrun | moved |
| ST#invocation-paths | launch dialog Profile row with (E)dit, persistent vs one-shot save, pruning of old one-shot files | EP#editing-the-profile-in-a-launch-dialog | moved; corrected (see 4). Class names `AgentCommandScreen` / `ProfileEditScreen` dropped (code structure, not public) |
| ST#how-dispatch-works | the 5 steps, closure walk, link rewriting, no work when the variant is fresh, the same flow on every agent | dev/ST#how-dispatch-works | moved ("dep closure" defined) |
| ST#per-agent-surfaces | the surface table and the `-codex-` segment (shared root with `agy`) | dev/ST#per-agent-surfaces | moved; Gemini row removed (see 4) |
| ST#per-agent-surfaces | the `agent_shared_skills_root` predicate | aidocs stub-skill-pattern.md §3a/§3g | already-stated (contributor-only), not repeated |
| ST#rendered-dirs | trailing hyphen, single glob, authoring dirs never end in `-`, never edit or commit | dev/ST#rendered-directories-and-gitignore; user form in ST#how-to-use | moved; glob list corrected to three |
| ST#rendered-dirs | pre-rendered remote variants negated in `.gitignore` | dev/ST#rendered-directories-and-gitignore | corrected (see 4) |
| ST#authoring | write the `.md.j2` once, add stubs; `{% if profile.<key> %}`, `{% if agent == … %}` (aitask-wrap Step 1b), `{% raw %}` | dev/ST#authoring (short) + aidocs skill_authoring_conventions.md / agent_runtime_guards_audit.md | already-stated in aidocs; short pointer on dev/ST |
| ST#authoring | run `aitask_skill_verify.sh`; what it checks; regenerate goldens in the same commit | dev/ST#authoring (pointer, "goldens" defined) + aidocs skill_authoring_conventions.md §Verifying / §Regenerate goldens | already-stated; the concept page's description of the check was wrong and is not carried over (see 4) |
| ST#authoring | the three aidocs GitHub links and their summaries | dev/ST#authoring | moved |
| ST#see-also | links | ST#see-also (+ EP, dev/ST) | kept / expanded |

### 3. Skipped files (shared-file gate)
None. Every target file returned an empty `git status --short` before I edited it.

### 4. Corrections and additions, each checked against the code
1. **Gemini is not a supported agent.** `aitask_skill_render.sh` accepts `--agent claude | codex | opencode`, `.gitignore` lines 67–69 have only three `*-/` globs, and there is no `.gemini/` directory. I removed the Gemini table row, its argument-variable mention and its glob. Not edited: aidocs `skill_authoring_conventions.md` (lines 3–4, 12–21, 174–176, 231–235) and `agent_runtime_guards_audit.md` still say four agents including Gemini, and `.gemini/…` paths.
2. **The verify script description was wrong.** The concept page said it "renders every .j2 against every profile for all four agents". `aitask_skill_verify.sh` (header and lines 116–117) renders against the default profile only, for 3 agents, and checks 4 stub surfaces. I did not carry the claim to the site.
3. **There are three pre-rendered remote variants, not "two skills".** `.gitignore` lines 80–88 negate `aitask-pickrem-remote-`, `aitask-pickweb-remote-` and `task-workflow-remote-` for each of the three agents.
4. **One-shot profile pruning runs when a launch dialog opens, not at TUI startup.** The call is in the dialog's constructor, `lib/agent_command_screen.py:485`.
5. **`ait codeagent` has no launch dialog.** It is a shell command, and no `AgentCommandScreen` caller exists there; the callers are board, codebrowser, brainstorm, monitor, minimonitor, syncer and the switcher. The text now says "`ait board` and other TUIs".
6. **Codex transcript verification works on macOS too.** setup-install said "On Linux … Elsewhere unverified", and the frozenagent reference said "on Linux". `lib/agent_sessions.py` sets `_PS_PROBE_PLATFORM = sys.platform == "darwin"`, and the `codex_observe_pid` docstring says macOS reads the same facts through `ps` / `lsof`. Both pages now say "Linux and macOS"; other platforms still report unverified.
7. **When `dead_window` applies.** This is from `lib/agent_sessions.py` `purge()`, `monitor/monitor_shared.py` `_collect_marks_observation`, and `lib/agent_freeze.py` `reconcile()` / `_write_observation`. Three facts on dev/FS go beyond the old page:
   - It applies only to `live` records.
   - A project counts as fully enumerated only when every one of its tmux sessions was listed successfully. A project with no session on the server is never swept.
   - The monitors count a window as seen only if they found an agent in it; reconcile counts any window.

   This resolves the stumble without a contradiction. A frozen record is never retired for a missing window or pane, so it always survives a tmux restart. A `live` record survives only until a full enumeration of its project finds its window or pane gone. An agent started again in that window before then takes over the record (the upsert selects the single `live` record in that window whose process is dead).
8. **Records with unharvested text are kept.** Every cleanup reason keeps a record whose capture text sitrep has not harvested (`capture_harvested` in `purge()`). This is new on dev/FS, linked to `workflows/sitrep`.

### 5. Guide rules that were unclear or did not fit, and leftovers
- **Facts the code needs but the source never stated.** "Do not add facts the source pages do not state" conflicts with the caller's request to state precisely when `dead_window` applies. I added only the code-verified scope conditions from items 7 and 8 and flagged them here.
- **Workflow page I was only allowed to retarget.** `workflows/freeze-and-restore-agents.md` lines 228–229 still carry the Codex 0.163.0 / 0.153.4 measurements, which the brief classes as contributor-only. Its opening and "When to freeze" prose also contain avoid-list patterns: a staged contrast, the "a small terminal app that reads a file" line, and em-dash connectors. They are left for that page's owner.
- **No site page owns `ait skillrun`.** There is no `commands/` page for it, so its behaviour went to the profiles reference page (`skills/aitask-pick/execution-profiles.md`), the page my assignment named.

### Restructure report: `topic-anchoring.md + attachments.md` (verbatim)

## Report: `concepts/topic-anchoring.md` and `concepts/attachments.md`

Both concept pages now follow the five-section shape. Every cut fact went to a destination page, or a link points to where it was already stated. `python3 check_links.py --build` passed: 0 broken links, `SWEEP: PASSED`, every fragment resolved. Nothing was committed or staged.

### 1. Files changed (all under /home/ddt/Work/aitasks/website/content/docs/)

| File | Lines old → new | depth old → new |
|---|---|---|
| concepts/topic-anchoring.md | 141 → 78 | main-concept → main-concept |
| concepts/attachments.md | 164 → 62 | intermediate → intermediate. `description` was tightened, because the old one promised mechanism the page no longer has. |
| development/task-format.md | 220 → 312 | advanced → advanced. Changed only § Nested fields (two new `####` blocks) and § Topic Anchoring. |
| commands/attach.md | 164 → 181 | intermediate → intermediate. The intro pointer was retargeted and a new `### References over a task's life` section added. |
| commands/task-management.md | 226 → 229 | intermediate → intermediate. Added rows for `--anchor` and `--followup-of` (create) and `--anchor` (update). |
| tuis/board/reference.md | 765 → 774 | advanced → advanced. Rewrote the "By-Topic lanes" paragraph and the `anchor` field row. |

No retags were needed. No new `development/attachments.md` was created: the storage layout fits task-format.md, which already holds a storage layout (Archive Storage). workflows/implementation-trails.md was not edited, because it already states the topic-vs-trail fact (lines 144 and 150).

### 2. Moved-fact table

| source page#section | fact (short) | destination page#anchor | status |
|---|---|---|---|
| topic-anchoring#what-it-is | `anchor` holds the root id; same key clusters in By-Topic | concept page (plain words); task-format#topic-anchoring | moved |
| topic-anchoring#what-it-is | not a dependency, label or parent-child relation | concept page, Why it exists | moved |
| topic-anchoring#what-it-is | topic vs trail membership; a trail never changes the anchor | workflows/implementation-trails (lines 144, 150) | already-stated; one plain sentence kept on the concept page |
| topic-anchoring#how-the-key-is-stored | root omits `anchor:`, bare id form, YAML example | task-format#topic-anchoring | moved (example block carried over verbatim) |
| topic-anchoring#how-the-key-is-stored | `t130` normalizes to `130`, child ids bare (`130_2`), target validated, archived roots valid | task-format#topic-anchoring; task-management#ait-create (`--anchor` row) | moved |
| topic-anchoring#creating-anchored-tasks | two `aitask_create.sh` examples | task-format#topic-anchoring | corrected (`--issue-type` → `--type`, see §4) |
| topic-anchoring#creating-anchored-tasks | `--followup-of` flattens to the root (three cases) | task-management#ait-create (`--followup-of` row) | corrected (the "never chains" scope, see §4) |
| topic-anchoring#creating-anchored-tasks | the two flags are mutually exclusive; both rejected with `--parent` | task-management#ait-create | moved |
| topic-anchoring#children-and-re-anchoring | a child inherits `P.anchor`, else `P` | task-format#topic-anchoring | moved; now scoped to batch mode |
| topic-anchoring#children-and-re-anchoring | `aitask_update.sh --anchor` / `--anchor ""` | task-format#topic-anchoring (already stated inline); task-management#ait-update (`--anchor` row) | already-stated plus completed; the claim that clearing makes a task its own root is corrected |
| topic-anchoring#when-to-use-it | topic vs child vs `depends` vs labels; they combine | concept page, Why it exists (shortened) | kept |
| topic-anchoring#board-view | `y`, topic key order, two-or-more rule, Ungrouped | tuis/board/reference#base-filters-radio and the "By-Topic lanes" paragraph | already-stated; the concept page keeps a plain version |
| topic-anchoring#board-view | archived root stays the lane key; label fallback | board reference, By-Topic lanes | moved and corrected (label) |
| topic-anchoring#board-view | detail screen edits the anchor; useful for a task that started standalone | board reference, `anchor` field row (Editable: Yes) | already-stated plus completed |
| topic-anchoring#see-also | links | concept page See also, retargeted to the new homes | moved |
| attachments#what-it-is | YAML block example | task-format#nested-fields-artifacts-and-attachments | already-stated |
| attachments#what-it-is | `ait attach` copies the bytes so the attachment survives the original | concept page (plain) | kept |
| attachments#identity-is-the-hash | never referred to by path or URL; `sha256:` prefix | task-format, new `#### attachments: entry fields` | moved |
| attachments#identity-is-the-hash | the source can go away; identical bytes stored once; per-task names | concept page (plain); task-format entry fields | moved |
| attachments#identity-is-the-hash | fetches are verified; a mismatch is an error | commands/attach#get | already-stated; plain sentence on the concept page |
| attachments#identity-is-the-hash | storage path and cache key derived from the hash, no lookup table | task-format, new `#### Where attachment blobs live` | moved |
| attachments#identity-is-the-hash | an edit makes a different attachment | concept page | kept |
| attachments#the-attachments-block | six-field table | task-format entry fields | moved |
| attachments#the-attachments-block | written only by add/rm, never by hand, would desynchronise | task-format nested fields (existing text) | already-stated |
| attachments#where-blobs-live | `.aitask-data/attachments/` tree, sharding, `.attach.lock` | task-format "Where attachment blobs live" | moved (block verbatim) |
| attachments#where-blobs-live | `local` is the only backend; no move command; per-machine cache | task-format "Where attachment blobs live"; attach.md (`--backend` row, "Not available") | moved / already-stated |
| attachments#one-commit-per-change | add commits three paths as one `ait:` commit under the lock; rm commits two | task-format "Where attachment blobs live"; attach#add and #rm | moved (the lock part) / already-stated |
| attachments#one-commit-per-change | refusal on uncommitted changes; blobs exempt; partial-failure restore | commands/attach#uncommitted-changes | already-stated |
| attachments#reference-counting-and-gc | ledger `refs`, orphan time; one file per blob so nothing contends | task-format "Where attachment blobs live" | moved |
| attachments#reference-counting-and-gc | how add / rm / archive / fold / board delete change refs | commands/attach, new `#references-over-a-tasks-life` | moved (add and rm already stated) |
| attachments#reference-counting-and-gc | gc only on explicit run; its conditions; `attachments_gc_grace` 30 days | commands/attach#gc and #configuration | already-stated |
| attachments#why-it-exists | temporary locations; the copy travels with the task; content keying is cheap and checkable | concept page | kept |
| attachments#why-it-exists | the per-blob ledger avoids concurrent collisions | task-format "Where attachment blobs live" | moved |
| attachments#how-to-use | three examples; link to the verb reference | concept page | kept |

### 3. Skipped files

None. All my target files were clean at the gate. commands/gates.md and commands/lock.md were dirty from other sessions; I did not touch them.

### 4. Corrections (checked against the code)

- **`--issue-type` does not exist.** Both create examples from the old concept page would fail with `die "Unknown option: $1"`. The real flag is `--type|-t` (`aitask_create.sh` parse_args, around line 205). I changed it to `--type` in the carried-over blocks.
- **"Follow-ups never form anchor chains" is not always true.** In `resolve_anchor()` (aitask_create.sh:260-274), when the source of `--followup-of` is an anchorless child, the new task gets the parent id (`BASH_REMATCH[1]`) even when that parent has an anchor of its own. The task-management row now says so.
- **Clearing the anchor does not always make a task its own root.** That holds for a standalone task only. `topic_key()` (lib/topic_semantics.py:68-86) puts a child without an anchor in its parent's topic. This is fixed on task-format, on the task-management `--anchor` row, and on the board reference `anchor` row ("Empty means the task is its own topic root" was wrong for children).
- **When an anchorless child exists:** `RESOLVED_ANCHOR` is computed only in batch mode (aitask_create.sh:73-77, :2407), so interactive `ait create` writes no anchor for any task. A child's anchor can also be cleared with `ait update --anchor ""`. A child created in batch mode with `--parent` always gets one. task-format now says this. The old concept page's "children always get an anchor at creation" is scoped to batch mode.
- **The lane label fallback was wrong.** When the root is not loaded, `_topic_lane_label()` (board/board_task_manager.py:98) labels the lane `t<key>` plus the name of the lane's first task, not the bare id. Corrected on the board reference.
- **"Visible tasks" was wrong.** Lanes are built from every loaded task (`task_datas` plus `child_task_datas`, aitask_board.py around line 2962) before any search filter, and archived tasks are not loaded. Corrected on the board reference.
- **Checked and true:** `ait create`, `ait update`, `ait attach` and `ait board` dispatch to `aitask_create.sh`, `aitask_update.sh`, `aitask_attach.sh` and `aitask_board.sh`. Follow-ups that aitasks creates itself pass `--followup-of` (aitask_archive.sh:966, aitask_verification_followup.sh:221, aitask_create_manual_verification.sh:157, monitor_shared.py:2116).
- **No undecided owners.**

### 5. Guide rules that did not fit cleanly

- **Flags on a `main-concept` page:** the assignment asks for "how to put a task in a topic (with the command name)", but flags are an `intermediate` addition. I named only `ait create` and `ait update` and described what they take in words.
- **Moved code blocks:** "never change code blocks you carry over" conflicts with correcting a block that cannot run. I applied the correction rule and report it in §4.
- **Length:** the topic-anchoring body is about 70 lines, just above the 30–60 target. The "When to use it" comparison and the define-every-term rule for task, child task, label and archived account for most of it.

#### Step 4 pages (edited in this session)

| source page#section | fact (short) | destination page#anchor | outcome |
|---|---|---|---|
| tasks#what-it-is | eight frontmatter field names, grouped by purpose | development/task-format#frontmatter-fields | already-stated; the page now names three in plain words (priority, status, what it waits for) |
| tasks#what-it-is | "a long tail of fields the workflow writes for itself" | development/task-format#fields-the-workflow-writes-for-you | already-stated; one sentence kept in tasks#how-to-use |
| tasks#what-it-is / #how-to-use | Task File Format reference documents every field (stated twice) | tasks#how-to-use | kept once |
| tasks#why-it-exists | "small enough for an LLM … prioritization, dependency resolution, Kanban-style triage" | tasks#why-it-exists | kept, reworded in plain words |
| plans#what-it-is | child plan path `aiplans/p<parent>/p<parent>_<child>_<name>.md` | development/task-format#parent-child-hierarchies | already-stated; linked from plans#how-to-use |
| plans#what-it-is | header fields (task, worktree, branch, base branch) | plans#what-it-is | kept, reworded |
| plans#how-to-use | "verification protocol" defined in planning.md | plans#how-to-use | kept, reworded ("how an existing plan is checked again before it is reused") |
| parent-child#what-it-is | path pattern `aitasks/t<N>/t<N>_<M>_<name>.md` | development/task-format#parent-child-hierarchies | already-stated; one example kept |
| parent-child#what-it-is | `children_to_implement` field lists pending children | development/task-format#parent-child-hierarchies | already-stated; page keeps "the parent keeps track of which children still need work" and links |
| task-lifecycle#what-it-is | `Done → Archived` moves the file into `aitasks/archived/` | development/task-format#status-workflow, #archive-storage | already-stated |
| folded-tasks#why-it-exists | "merged, not superseded or replaced"; code, commit messages and procedures use "merged"/"incorporated" | CLAUDE.md § Folded Task Semantics (contributor docs) | already-stated; the user-facing part (original wording stays visible) kept |
| artifacts#what-it-is | three `gitbranch` rules (write counts once pushed; branch belongs to the store, reserved names refused; rename = `gitbranch-migrate`) | commands/artifact (§ the `gitbranch` write and branch rules, #gitbranch-migrate) | already-stated; linked |
| parent-child#what-it-is | parent counts as completed when any child completed; superseded/obsolete only when none was | development/task-format#parent-child-hierarchies | moved |
| task-lifecycle#how-to-use | transition logic lives in `aitask_pick_own.sh`, `aitask_archive.sh`, the task abort procedure (GitHub links) | development/task-format#status-workflow | moved |
| task-lifecycle#what-it-is | Ready → Implementing takes a lock; abort reverts and releases; Folded is terminal and deleted not archived | task-lifecycle#what-it-is | kept, reworded |
| development/_index.md#atomic-task-locking | "the same email can refresh its own lock" | development/_index.md (same bullet) | corrected: only the holding session refreshes; another live/unverifiable session on the host is refused (`aitask_lock.sh` same-host branch, exit 13/14) |
| tasks#why-it-exists | "branches and worktrees can carry their own task state" | — | dropped(true only in legacy mode; in branch mode task data lives on the separate `aitask-data` branch, see concepts/git-branching-model; flagged by the concept review and the survival check) |
| tasks#how-to-use | `ait create` typically launched from a TUI like Board or Brainstorm | commands/task-management#ait-create (intro) | moved (Brainstorm is undefined at `main-concept`) |
| folded-tasks#why-it-exists | code, commit messages and procedures say "merged"/"incorporated" | CLAUDE.md § Folded Task Semantics | moved (commit messages added there; it named only code, procedures and docs) |

## Final review (Step 6) — round 1

`/aitask-docs-review --caller audit` on every page this child edited or created,
split across three reviewer agents that did not write the edits. Concept pages
were reviewed in full (fresh-reader budget 2, spent on `parent-child` and
`task-lifecycle`; the other `main-concept` pages get the Step 7 after-reports);
new `development/` pages in full; pages changed only in part were reviewed on
their changed hunks, with pre-existing findings listed separately for their
owning audit child. Reports verbatim below, then the fixes.

### Decisions on the findings

- Applied: every prose fix; the level fixes on all concept pages; the
  development-page level fixes except as below; the four wrong facts the
  concept review found, each verified in code before fixing ("Has children"
  is `ait ls` output, not a board label; archiving sets `Done`; abort offers
  `Ready` or `Editing`; an ad-hoc fold is triggered by the task description or
  the user, not by the plan); the merge-mutex guard-removal step and the
  `AIT_AGENT_PID` check (both wrong, verified in code).
- Applied as a placement fix: the `ait skillrun` reference had landed on a
  skill page; it moved to a new `commands/skillrun.md` (the guide's page-type
  table makes `commands/` the CLI reference), with `commands/_index.md` and the
  profiles page pointing to it.
- Rephrased instead of cut: the merge-mutex "rejected alternative" sentences
  became positive reasons on the same page, so no fact needed a new owner.
- Declined in part: the gate digest's three inputs stay on
  `development/gates.md` (which edits invalidate the stored set is behaviour an
  integrator relies on; only the dot-joined encoding hint in the diagram went);
  the script links in task-format § Status Workflow stay ("which component
  writes what" is public architecture), with only the staged contrast fixed.
- Deferred to the owning child (noted, not fixed here): `concepts/artifacts.md`
  depth/mechanism (moving it needs `commands/artifact.md`, which points back to
  the concept page — t2258_6); pre-existing findings on `crash-recovery.md`,
  `freeze-and-restore-agents.md` prose, `commands/lock.md` relative links,
  `development/_index.md` depth/type (t2258_4, t2258_6, t2258_7).

### Concept pages (verbatim)

## /aitask-docs-review report: 12 concept pages, `--caller audit --budget 2`

This was an audit run, so I edited nothing. I read the guide at `aitasks/metadata/doc_update_guide.md`. It has a level model: level field `depth`, beginner level `main-concept`, and the persona "You know git and a terminal and have never heard of aitasks."

The six `main-concept` pages are locks, topic-anchoring, tasks, plans, parent-child and task-lifecycle. As you asked, I spent the budget on parent-child and task-lifecycle.

**Deviation from the skill's ordering rule.** Ordered by changed lines (from `git diff --numstat`), the two tests would have gone to topic-anchoring (about 155 lines) and locks (about 141). parent-child and task-lifecycle changed about 6 lines each.

**Fresh-reader method.**
- I wrote the questions from each page's title, description and the persona before reading the body. They are saved in `/tmp/claude-1000/-home-ddt-Work-aitasks/57ffb334-9dbe-4f0f-81e5-ee1f5a3ac601/scratchpad/questions.txt`, so a re-test can reuse them.
- Each test ran in a general-purpose sub-agent with the page text inline. The five follow-up questions went to the same agent by SendMessage.

**Other checks.**
- All `Next:` footers match the order of the list on `concepts/_index.md`.
- Every relref anchor these pages use exists.
- I did not run `check_links.py`.

---

PAGE: website/content/docs/concepts/locks.md
level=findings:4  prose=findings:1  reader=not-run(cap)  (tested separately, after-report run)

Level findings:
1. **Sentences:** "Each task lock belongs to one **agent session**, a single running coding agent in its own terminal. Several agents on one machine usually run under the same email, so a lock that belonged to the email would let all of them take the same task."
   - **Problem:** this is the reason for an internal design choice, and it argues with no one.
   - **Fix:** replace both sentences with the guide's own After: "Each task lock belongs to one **agent session**, a single running coding agent in its own terminal, so several agents in one checkout under the same email still exclude each other."
2. **Clause:** "and a merge stopped at a conflict could have its half-resolved files taken into the next task's merge commit".
   - **Problem:** this is an edge case, which `main-concept` leaves out.
   - **Fix:** cut it, so the sentence ends "Two merges at once would mix their changes in that one copy." Nothing needs to move: `development/merge-mutex.md` ("The reservation lasts the whole merge") already says the mutex is held through conflict resolution.
3. **Clause:** ", and clearing a lock by hand is one more commit".
   - **Problem:** it describes how something is implemented.
   - **Fix:** cut it and end the sentence at "with no server to run."
4. **Paragraph** under How to use: "An agent that crashes cannot release a lock it holds … a task lock after asking you (…), and a merge mutex on its own. You can also clear a left-over lock by hand: …"
   - **Problem:** this is takeover and recovery behaviour detail on a beginner page, and it is the main reason the page runs to 74 lines against the guide's 30–40.
   - **Fix:** shorten it to "An agent that crashes leaves its locks behind. [Crash recovery](…) shows how the next agent takes over a task lock, and [Merge mutex](…#recovering-a-stuck-merge-mutex) shows how to clear a stuck merge mutex." The facts are already on those two pages.

Prose findings:
1. **See also entry:** "[`ait note`] — live delivery reads the lock record to find the agent session holding a task".
   - **Problem:** it describes a mechanism and uses an undefined term ("live delivery").
   - **Fix:** drop the entry, or reword it as "— sends a note to a task, and to the agent working on it".

Changes made: none (audit).
Reader report: not run (cap); tested separately (after-report run).
Unresolved: 5 — all findings above (audit, nothing edited).

---

PAGE: website/content/docs/concepts/gates.md
level=findings:4  prose=findings:2  reader=not-run(not-beginner)

Level findings:
1. **Section:** "What it is" holds mechanism in paragraphs 2–4: declared vs enforced gates, the profile, "fixed at that pick", retry budgets, and the override. The concept-page rule allows only a plain definition there.
   - **Fix:** keep paragraph 1, plus the sentence "a task archives only once every enforced gate is satisfied."
   - Move paragraph 2 ("A task declares the gates it asks for … until the task is picked again.") into Why it exists, in place of its paragraph 2 (see finding 2).
   - Delete paragraph 4 ("When a gate fails, the failure is recorded … described in [Gate rules]…#archival"). How to use already carries the failure handling, and `development/gates.md` (#the-ledger, #retry-budgets, #archival) owns the ledger, the retry budget and the `--ignore-gates` override.
   - Add one link in How to use: "Archiving with an unmet gate needs an explicit override; see [Gate rules](…#archival)."
2. **Paragraph:** Why it exists, paragraph 2: "Keeping the declared gates apart from the enforced ones lets one task move between workflows. … the gap between the two is recorded rather than lost. Fixing the enforced gates at pick time keeps that decision stable for a whole session."
   - **Problem:** this is design rationale. `development/gates.md#when-the-enforced-set-is-computed` already states it.
   - **Fix:** cut it to one user-facing sentence, for example "The same task can be picked under different profiles, and each enforces only the gates its workflow can check."
3. **List:** How to use has a numbered list: "When a gate fails or has used up its retries: 1. Read why … 2. Fix the cause … 3. If the gate can never pass because the project's gate registry …".
   - **Problem:** steps belong on the command or workflow page, and the concept-page rule says "Short; link out for steps". "gate registry" is also used without a definition or link.
   - **Fix:** replace the list with "When a gate fails, `ait gate log <task> <gate>` shows why; after fixing the cause, `ait gates run <task> --gate <gate>` runs it again even when its retries are spent. [`ait gates`](…#when-to-run-sync-registry) covers a gate that has no way to run."
   - Every fact here is on `commands/gates.md`, lines 52–58 and 150–240.
4. **Clauses:** ", that is, closed as finished and moved out of the active task list" and "(start work on it with `/aitask-pick` or another pick skill)". The execution-profile definition is also given in place even though a page for it exists.
   - **Problem:** at `intermediate`, terms that have a defining page are linked, not defined.
   - **Fix:** cut the two clauses and keep the links (Task lifecycle, Execution profiles).

Prose findings:
1. **Sentence:** "Gates sit beside the task's `status` field, which keeps tracking the task's lifecycle, and they come into play while the task is being implemented."
   - **Problem:** vague.
   - **Fix:** "A task's gates are recorded apart from its `status` field and are checked while the task is implemented and when it archives."
2. **Phrase:** "the gap between the two is recorded rather than lost".
   - **Problem:** staged contrast.
   - **Fix:** removed by Level finding 2.

Changes made: none.
Reader report: n/a.
Unresolved: 6 — all findings above.

---

PAGE: website/content/docs/concepts/framework-session.md
level=findings:1  prose=findings:3  reader=not-run(not-beginner)

Level findings:
1. **List:** How to use is a four-step procedure covering f, Z, R, P, k, `ait ide` after a reboot and `ait frozenagent`.
   - **Problem:** those are steps and key reference. `workflows/freeze-and-restore-agents.md` (lines 113–147) and `tuis/frozenagent/reference.md` (lines 26–28) already hold all of them.
   - **Fix:** replace the list with "You meet it when you freeze an agent, with **f** in `ait monitor` or `ait minimonitor` (**Z** freezes every agent), and when you restore one with **R** in the [frozen-agent viewer](…) that takes its pane. [Freeze and Restore Agents](…) walks through both, including bringing agents back after a reboot."

Prose findings:
1. **Sentence:** "A restore needs the agent's session id, which the session hook that `ait setup` offers records when the agent starts."
   - **Problem:** it reads as a garden path.
   - **Fix:** "A restore needs the agent's session id. The session hook, which `ait setup` offers to install, records it when the agent starts."
2. **Sentence:** "An agent known only by its pane is lost at exactly the moment you most want it back."
   - **Problem:** a saying that sounds deep.
   - **Fix:** "An agent known only by its pane is lost with the pane."
3. **See also entry:** "[Locks] — the other claim an agent holds, on its task rather than its pane."
   - **Problem:** "claim" is a second term for what `locks.md` calls the task lock, and the framework session is a record, not a claim.
   - **Fix:** "[Locks] — the task lock an agent holds on its task."

Note: the frontmatter title "Framework Session" uses a capital S. linkTitle and the sibling pages use sentence case. That is frontmatter, so I report it only.

Changes made: none.
Reader report: n/a.
Unresolved: 4.

---

PAGE: website/content/docs/concepts/skill-templating.md
level=findings:1  prose=findings:1  reader=not-run(not-beginner)

Level findings:
1. **Sentences:** "A [skill] is a set of instructions a coding agent follows when you type its slash command, such as `/aitask-pick`." and "An execution profile is a saved set of answers to the workflow's routine questions."
   - **Problem:** at `intermediate` you link to a defining page rather than define in place, and both terms have linked pages.
   - **Fix:** cut the second sentence. Merge the first into "A profile-aware [skill], such as `/aitask-pick`, is written once and comes in several ready-made variants, …"

Prose findings:
1. **Sentences:** "Everything above is what you need to run skills. How the variants are produced, and how to write a profile-aware skill of your own, is for skill authors and is on the development page below."
   - **Problem:** this writes about the page instead of the subject.
   - **Fix:** "Skill authors will find how the variants are produced, and how to write a profile-aware skill, on [Skill Templating and Dispatch]({{< relref "/docs/development/skill-templating" >}})."

Notes:
- The title "Skill templating and per-profile dispatch" uses "dispatch", which the body never mentions. That is frontmatter, so I report it only.
- The `_index.md` blurb "materialize per-(skill, profile, agent) variants on demand via templated dispatch" is jargon. `_index.md` was not in scope.

Changes made: none.
Reader report: n/a.
Unresolved: 2.

---

PAGE: website/content/docs/concepts/attachments.md
level=findings:1  prose=findings:1  reader=not-run(not-beginner)

Level findings:
1. **Paragraph:** What it is, paragraph 2 ("aitasks identifies an attachment by its content, the SHA-256 hash of its bytes, and the task file records that hash, never a path … Changing a file's contents makes a different attachment, with a different hash.").
   - **Problem:** this is mechanism and public architecture inside "What it is".
   - **Fix:** shorten it to "aitasks identifies an attachment by its content, so the same file attached to two tasks is stored once. On its task an attachment also has a name, by default the file's name, which is what you type in commands."
   - Where the cut facts go:
     - SHA-256 and the task file recording the hash: `commands/attach.md` (the `sha256:` form) and `development/task-format.md#nested-fields-artifacts-and-attachments` (the `hash`/`name` fields) already state these.
     - "two tasks can give the same file different names": add to the task-format nested-field section if it is not already there.

Prose findings:
1. **Sentence:** "The full verb reference, with flags, refusals and the gc rules, is on the [`ait attach` command page]."
   - **Problem:** it repeats the first See also entry.
   - **Fix:** cut it.

Changes made: none.
Reader report: n/a.
Unresolved: 2.

---

PAGE: website/content/docs/concepts/topic-anchoring.md
level=findings:2  prose=findings:1  reader=not-run(cap)  (tested separately, after-report run)

Level findings:
1. **Paragraph:** "A task belongs to exactly one topic, but it can appear in any number of implementation trails, recorded recommendations of the order in which a set of tasks should land. Adding a task to a trail never changes its topic."
   - **Problem:** it brings in a term the idea does not need at `main-concept`.
   - **Fix:** cut the paragraph. Trails are already linked twice in See also.
2. **Ordering:** "The task detail screen of the board can edit the anchor too." (line 59) uses "board" before it is defined at lines 61–62.
   - **Fix:** define it at line 59: "…the task detail screen of the board, the terminal view that shows your tasks as cards in columns, which `ait board` opens, can edit the anchor too." Then line 61 becomes "To see your topics, press `y` in the board for the By-Topic view."

Prose findings:
1. **See also separators:** the entries use " - " (hyphen) while every other concept page uses " — ".
   - **Fix:** make them consistent.

Fact: see the "Facts that may be wrong" list (anchor sentence).

Changes made: none.
Reader report: not run (cap); tested separately.
Unresolved: 3, plus 1 fact.

---

PAGE: website/content/docs/concepts/tasks.md
level=findings:2  prose=ok  reader=not-run(cap)  (tested separately, after-report run)

Level findings:
1. **Phrase:** "typically started from a TUI such as the [board] or Brainstorm".
   - **Problem:** "Brainstorm" is undefined and not needed.
   - **Fix:** drop "or Brainstorm".
2. **Sentence:** "Keeping tasks in git means every change to a task shows up in `git log`, a branch or worktree can carry its own task changes, and …"
   - **Problem:** "worktree" is undefined at `main-concept`, and the clause is doubtful (see the facts list).
   - **Fix:** cut ", a branch or worktree can carry its own task changes".

Changes made: none.
Reader report: not run (cap).
Unresolved: 2, plus 1 fact.

---

PAGE: website/content/docs/concepts/plans.md
level=findings:4  prose=findings:1  reader=not-run(cap)  (tested separately, after-report run)

Level findings:
1. **Sentence:** "It opens with a short header naming the task, the branch the work uses and the branch it starts from, and the git worktree when the task has one."
   - **Problem:** file-format detail in "What it is" on a beginner page.
   - **Fix:** cut it. No site page documents the plan header (I grepped for "Base branch"), so move it to a new "Plan files" section in `development/task-format.md` (the source is `task-workflow/planning.md`, lines 449–470).
2. **Sentence:** "The file naming, the header and how an existing plan is checked again before it is reused are defined in the shared task-workflow skill: see [`task-workflow/planning.md`](github…) on GitHub."
   - **Problem:** it points a beginner at a contributor skill source and mentions an edge case (plan re-check).
   - **Fix:** cut it, and point to the new task-format section from finding 1, which can carry the GitHub link.
3. **Sentence:** "Later tasks split from the same parent read it first".
   - **Problem:** it assumes the parent/child idea.
   - **Fix:** "Child tasks split from the same parent task (see [Parent and child tasks](…)) read it first".
4. **Link:** "[Code Browser]" has no definition at first use.
   - **Fix:** "the [Code Browser], a terminal app for reading the project's code, shows it …". The wording comes from the codebrowser page description ("TUI code viewer").

Prose findings:
1. **Sentence:** "Keeping the plan as a file, rather than only in the agent's conversation, is what makes that record possible."
   - **Problem:** a closing line that restates the point, and it dodges "is" with "is what makes".
   - **Fix:** cut it.

Changes made: none.
Reader report: not run (cap).
Unresolved: 5.

---

PAGE: website/content/docs/concepts/parent-child.md
level=findings:3  prose=findings:2  reader=subagent

Level findings:
1. **Terms undefined at `main-concept`** (the reader guessed every one):
   - **"planning agent":** in "Splitting the work lets the planning agent describe the whole problem once", change "the planning agent" to "the agent that plans the parent".
   - **"plan":** "its plan becomes the first thing the next children read" → "its **plan**, the step-by-step description of the work that the agent wrote and you approved before coding (see [Plans]), becomes the first thing the agents working on the next children read".
   - **"pick":** "You pick a child the same way as any other task, by its number: `/aitask-pick 130_2`." → "You start work on a child the same way as on any other task, by typing `/aitask-pick 130_2` (the parent's number, then the child's) into your coding agent."
   - **"board":** "The [board] …" → "The [board], the task board that `ait board` opens in your terminal, …". This wording is from locks.md, and that sentence also needs the fact fix below.
2. **How to use names no way to create children.**
   - The reader could not answer "how do I split a task?": the page only links the workflow.
   - **Fix:** add "When you pick a large task with `/aitask-pick`, the agent can offer to split it into children while it plans; you can also ask for a split in the task's description."
   - Verified in `workflows/task-decomposition.md` lines 15–16 and 26, and in planning.md (the Complexity Assessment and the "Children" checkpoint).
3. **Sentence:** "Children depend on each other in order, so they are done one after another".
   - **Problem:** the reader could not tell whether the order is enforced or which order it is. It also reads as contradicting "lets you pick a specific child", and it overstates the rule: `aitask_create.sh --no-sibling-dep` exists, so the dependency is only the default.
   - **Fix:** "By default each child depends on the one before it, so the children are done in number order."

Prose findings:
1. **Phrase:** "kept in a folder named after its parent".
   - **Problem:** the example folder `aitasks/t130/` uses the parent's number, not its name. The reader flagged this as a mismatch.
   - **Fix:** "kept in a folder named after the parent's number".
2. **Definition:** "agent session, a single conversation with a coding agent".
   - **Problem:** `locks.md` defines the same term as "a single running coding agent in its own terminal", so one term has two meanings across beginner pages.
   - **Fix:** drop the term here: "Many real tasks are too large for one conversation with a coding agent: …"

Changes made: none.

Reader report (fresh reader, 8 questions):
- **Answered from the page:** Q1 (what parent and child are), Q2 (why split), Q5 (the parent archives with the last child), Q6 (the archived plan is read next), Q8 (folder and filename).
- **Not answered:** Q3 (how to create children) and Q7 (adding a child later, or working on the parent).
- **Guessed:** Q4. It guessed what happens when a child is picked out of order, and where `/aitask-pick` is typed.
- **Guessed terms:** task, plan, planning agent, pick, board, "Has children" (a column, a label or a status?), archived (only partly defined), "open tasks", fresh session, background, review, "depend on", the `130_2` id format.
- **Details not needed:** almost none; at most, Q2 needed only one of the three ways a big task goes wrong.
- **Ambiguities:**
  - is "parent keeps track" a field I must update?
  - is the order enforced?
  - does archived mean the same as done, and who archives?
  - who hands each child to a session, and who decides what background it gets?
  - does "next children" mean all of them or one?
  - is "Has children" a column, a label or a status?
- **Contradictions:**
  - "done one after another" vs "pick a specific child";
  - "folder named after its parent" vs `t130/`.

Unresolved: 5, plus 1 fact ("Has children").

---

PAGE: website/content/docs/concepts/task-lifecycle.md
level=findings:3  prose=findings:2  reader=subagent

Level findings:
1. **Terms undefined at `main-concept`**, and a second field named (the reader guessed: triaged, picked, TUI, skill, agent, claimed, lock, archival, fold/merged, "normal selection", `folded_into`). Fixes, table row by row:
   - **Ready:** "Created and triaged. Available to be picked." → "Ready to start work on; new tasks start here." (`ait create` defaults to Ready, per `commands/task-management.md` line 59.)
   - **Editing:** "Being authored or revised in a TUI; not yet ready for implementation." → "Still being written or revised; not ready to start yet."
   - **Implementing:** "A skill has claimed the task; an agent is actively working on it." → "A coding agent has started work on it and holds its task lock." This also removes "claimed" as a second word for the lock.
   - **Postponed:** "Deferred — left visible but skipped during normal selection." → "Put aside for later. It stays listed, but task selection skips it." This also removes the em-dash connector.
   - **Folded:** "The task has been merged into another (the `folded_into` task)." → "Merged into another task (see [Folded tasks])." The page's subject is `status`, so it should not name a second field.
   - **Following paragraph:** "Picking a task, which starts work on it," → "Picking a task, which you do with `/aitask-pick` in your coding agent or from the board, starts work on it and".
2. **Sentence:** "A small, fixed set of statuses keeps simple everything that decides what comes next, such as sorting by priority, the board and task selection: each only has to reason about a handful of states."
   - **Problem:** it gives an internal design reason, not the user's problem. The reader also asked "next what?"
   - **Fix:** "The status tells you, the board and task selection which tasks can be started, which are being worked on and which are finished; a `Postponed` task stays listed without being offered."
3. **How to use** never says how to set the statuses you do set by hand. The reader could not answer "how do I put a task aside and bring it back?".
   - **Fix:** append "To put a task aside, set it to `Postponed` on the board's task detail screen or with `ait update --status`, and back to `Ready` when it should be picked again."
   - Verified: `ait update -s` accepts Postponed (`commands/task-management.md`, around line 194), and the board detail screen cycles `status` (`tuis/board/reference.md` line 636).
   - Optional: add [Crash recovery] to See also. The reader had nothing for "what if the agent crashes?"

Prose findings:
1. **Sentence:** "Each status change is a commit rather than a silent edit, so `git log` for a task file is also its history."
   - **Problem:** staged contrast.
   - **Fix:** "Each status change the workflow makes is committed to git, so the task file's git history is also its history." (See the `git log` fact below.)
2. **Contradiction the reader found:** "A finished run moves it to `Done`, and archiving then moves the file …" vs "picking, archiving, aborting and folding set it".
   - **Fix:** correct the fact (see the facts list); the two sentences then agree.

Changes made: none.

Reader report (fresh reader, 8 questions):
- **Answered:** Q1 (from the table), Q3 and Q4.
- **Partly answered:** Q2 (written from the tool's point of view), Q5 (archive location sent elsewhere; is archiving automatic?), Q6 (`Postponed` exists, but how to set it is not said), Q7 (abort yes, crash no).
- **Not answered:** Q8 (reopening).
- **Guessed terms:** skill, agent, TUI, the board, lock, pick, triaged, workflow, run, archive, abort, fold, merged, "normal selection", `folded_into`, "authored".
- **Details not needed:** the `Folded` deletion sentence, the `folded_into` name, "sorting by priority", and the How-to-use link text.
- **Ambiguities:**
  - who picks, and what action picking is;
  - "a finished run" of what;
  - is archiving automatic, and where is the archive;
  - does a new task start as Ready or Editing, and who triages;
  - which TUI;
  - are the skill and the agent the same thing;
  - when to set status by hand;
  - who commits a status change;
  - "what comes next".
- **Contradictions:**
  - "workflow changes it for you" vs "rarely by hand";
  - the finished run sets `Done` but is missing from the list of actions that set status;
  - nothing on the page moves a task into or out of `Editing` or `Postponed`.

Unresolved: 5, plus 2 facts.

---

PAGE: website/content/docs/concepts/folded-tasks.md
level=findings:1  prose=ok  reader=not-run(not-beginner)

Level findings:
1. **Paragraph:** What it is: "Folding sets the folded task's `status` to `Folded` and writes a `folded_into` field … lists every task folded into it in its `folded_tasks` frontmatter field. At fold time the folded task's body is copied into the primary's description under a `## Merged from t<N>` header."
   - **Problem:** mechanism in "What it is".
   - **Fix:** "A **folded task** is a task whose content has been merged into another task, the *primary* task. Its wording is copied into the primary's description, and the folded file stays on disk only as a reference until the primary is archived, when it is deleted."
   - Nothing needs to move: the three fields are in `development/task-format.md` (lines 54–55 and Status Workflow), and the `## Merged from t<N>` header is in `skills/aitask-fold.md` and `workflows/task-consolidation.md`.
   - Low priority: the guide names this page as a structure and length exemplar.

Fact: see the facts list ("a plan … names additional tasks to fold").

Changes made: none.
Reader report: n/a.
Unresolved: 1, plus 1 fact.

---

PAGE: website/content/docs/concepts/artifacts.md
level=findings:2  prose=findings:2  reader=not-run(not-beginner)

Level findings:
1. **Depth set by mechanism, not by audience.** The page itself says "/aitask-trail … stores implementation trails as artifacts, so you may already have some", so the people who meet artifacts are trail users, not maintainers. The `advanced` tag comes from the mechanism the page carries: manifest, per-version SHA-256, the `~/.cache/ait/artifacts/` cache path, and the resolution chain.
   - **Fix:** move that mechanism to an advanced reference (a `development/artifacts.md`, or `commands/artifact.md`), then retag the page `intermediate`.
   - **Needs a decision:** `commands/artifact.md` lines 11–12 point back to this concept page for "the model (handle, manifest, backends) and when to pick each backend". That cross-reference must be redirected in the same change.
2. **"What it is" has a cases table** (Backend / Where blobs live / Pick it when) and the line "Resolving a handle therefore goes handle → manifest → backend → local cache." The guide names both as signs of a reference page.
   - **Fix:** move them with finding 1. Keep in "What it is" only the handle sentence and "new versions and backend moves never rewrite the task file".

Prose findings:
1. **Sentence:** "Some outputs are too large, or change too often, to live inside a task file — and a task file that is rewritten on every revision makes a noisy history."
   - **Problem:** the em dash is the default connector.
   - **Fix:** "…to live inside a task file, and a task file rewritten on every revision has a noisy history."
2. **Sentence:** "The backend choice is what lets large blobs stay off the task data branch: start on `local`, then move…"
   - **Problem:** it dodges "is" with "is what lets".
   - **Fix:** "Choosing a backend keeps large blobs off the task data branch: start on `local`, then move…"

Changes made: none. The gitbranch rules cut from this page are on `commands/artifact.md` (lines 223–227, 266–269 and 153).
Reader report: n/a.
Unresolved: 4 (Level 1 needs a decision).

---

BUDGET_USED:2 BUDGET_LEFT:0 NOT_RUN_CAP: website/content/docs/concepts/locks.md, website/content/docs/concepts/topic-anchoring.md, website/content/docs/concepts/tasks.md, website/content/docs/concepts/plans.md (tested separately, after-report run)

---

## Facts that may be wrong

1. **parent-child.md:** "The [board] shows a parent with children still to do as **Has children**". Likely wrong.
   - "Has children" is the status that `ait ls` prints (`aitask_ls.sh` line 820; `commands/task-management.md` line 134).
   - `grep` finds no "Has children" anywhere in `.aitask-scripts/board/`. The board's parent card shows "👶 N children" or "👶 N more children" (`board_widgets.py` lines 468–470; `tuis/board/reference.md` line 108), and the Child Picker (reference line 707) is how you open a specific child.
   - **Fix:** "In the [board], a parent's card shows how many children it has, and opening it lets you pick a specific child."
2. **task-lifecycle.md:** "A finished run moves it to `Done`, and archiving then moves the file into the archive of finished tasks", together with the `Done` row "Awaiting archival". The sequence is likely wrong.
   - `aitask_archive.sh` sets `status: Done` itself (lines 179 and 197) in the same step that moves the file. A `Done` task that is not archived is only an interrupted archive (task-workflow SKILL.md line 41: "status 'Done' but hasn't been archived yet").
   - **Fix:** "When the work is finished and committed, archiving sets the status to `Done` and moves the file into the archive of finished tasks." Done row: "Finished; archived tasks keep this status."
   - `development/task-format.md` Status Workflow ("Done — Implementation complete, pending archival") has the same framing and should be checked too.
3. **task-lifecycle.md:** "Aborting puts it back to `Ready` and releases the lock." This is incomplete: `task-abort.md` (lines 26–32) asks whether to revert to `Ready` or `Editing`.
   - **Fix:** "Aborting puts it back to `Ready` (or `Editing`, if you choose) and releases the lock."
4. **folded-tasks.md:** "if a plan in [`/aitask-pick`] names additional tasks to fold in". The trigger is not a plan. `task-workflow/planning.md` line 253 runs the Ad-Hoc Fold when the task description asks to fold other tasks, or when the user asks during planning.
   - **Fix:** "if the task's description, or you during planning, asks for other tasks to be folded in, the workflow folds them before planning continues."
5. **topic-anchoring.md:** "Every other task in the topic records the root's task number in a field called its **anchor**". This overstates it.
   - A child task with no `anchor` is in its parent's topic (`tuis/board/reference.md` line 224: "`anchor`, else a child's parent topic"; the board `anchor` row at line 651; `ait create --anchor` is rejected together with `--parent`).
   - **Fix:** "Other tasks join the topic by recording the root's task number in a field called its **anchor**; a child task is in its parent's topic without one."
6. **tasks.md:** "a branch or worktree can carry its own task changes". This is doubtful in branch mode. There, task files live on the separate `aitask-data` branch, and `aitasks/` is a symlink into that worktree (`concepts/git-branching-model.md` lines 16–21). A code branch or worktree therefore does not carry its own task changes.
   - **Fix:** cut the clause (also Level finding 2 on tasks.md).
7. **tasks.md** ("every change to a task shows up in `git log`") and **task-lifecycle.md** ("`git log` for a task file is also its history"). Possibly misleading in branch mode, where task history is read with `./ait git log` (CLAUDE.md and git-branching-model). I did not check which mode `ait setup` makes the default.
   - **Fix:** say "git history" without naming the plain `git log` command, or mention `./ait git log`.

All other facts I spot-checked against code and owner pages were consistent:
- locks/merge-mutex takeover and recovery;
- the gates commands, retries, `--ignore-gates` and blocks_dependents;
- the frozen-agent keys and the session hook;
- skill-variant rendering and the trailing `-` folders;
- attachment rm/gc, archived and fold behaviour;
- artifact commands, the `k` settings key and the cache path;
- the plan header fields.

### Development pages (verbatim)

## Docs review: 6 development pages (`--caller audit`, `--budget 0`)

I edited nothing. The guide is `aitasks/metadata/doc_update_guide.md` and it has a level model (`depth`, beginner level `main-concept`). All six pages are reference pages: `development/_index.md` is an overview by the guide's location table. All four new pages open with a plain sentence saying what they cover.

```
PAGE: website/content/docs/development/gates.md
level=findings:1  prose=findings:9  reader=not-run(not-beginner)
```
**Level findings**
1. **Contributor-only digest encoding (L82–95, and diagram L42).** These lines give the digest's encoding and how it is checked: "It has one part for each input to the computation: 1. … 2. … 3. …" and "Anything that reads the enforced set checks parts 1 and 3 first. Both can be checked from the task file alone…".
   - **Fix:** replace L82–95 with:
     > "`active_gates_digest` records what the enforced set was computed from. Anything that reads the enforced set first checks it against the task file. If `gates:` was edited after the pick, or `active_gates` or `active_gates_filtered` was edited by hand, the stored set is treated as absent, and enforcement falls back to the raw `gates:` field until the next pick computes it again. A change to the profile itself takes effect at the next pick."
   - In the code block, L42 `<gates>.<profile>.<outputs>` → `<digest>`.
   - The part layout already lives in `aidocs/gates/gate-guarded-archival.md` L51–56. Those lines currently say "The site's `development/gates.md` page describes which inputs each part covers", so update them too.
   - This is borderline: that aidocs note shows the split was chosen on purpose. Your call.

**Prose findings**
1. **L17–18** "…and most of what is surprising about gates comes from confusing them:" is inflated. → "Each task carries two sets of gates:"
2. **L50** "Three cases read oddly until you know them:" is a run-up. → "Three cases follow from these rules:"
3. **L76–78** The closing line restates the point, and the reader is not told what governs afterwards. "…any previously stored tuple is cleared rather than left in charge. An old profile's enforcement never quietly governs a new session." → "…any previously stored tuple is cleared, and the raw `gates:` field governs until a pick computes the set again." (Code: `aitask_gate.sh` L1012 "stale tuple cleared; raw gates: fallback governs".)
4. **L97** "The fallback errs in one direction on purpose." is a run-up. Cut it, so the paragraph starts "Falling back to declared intent can enforce…".
5. **L102–106** "This fallback and the rule that a filtered gate never blocks archival … hold together. …" repeats L97–100. Cut the paragraph. In Archival, change L199–200 "a gate the profile filtered out can never block archival" → "a gate the profile filtered out never blocks archival while the stored enforced set is valid (see [The digest](#the-digest))".
6. **L151–152** "Both read the same ledger, and the two questions are kept separate." is a closing restatement. Cut it.
7. **L147** "Under a profile that records gates" uses an undefined term. → "Under a profile with `record_gates: true`" (the key is in `lib/profile_editor.py` L63/198).
8. **L201–202** "so the rule holds for every caller, not just the pick workflow" is a staged contrast. → "so the rule holds for every caller, the pick workflow included."
9. **L99** "a hand-edited active set" uses a second term; the page calls it the "enforced set" everywhere else. → "a hand-edited enforced set".

**Unresolved:** 10 (all of the above; nothing applied).

```
PAGE: website/content/docs/development/merge-mutex.md
level=findings:3  prose=findings:5  reader=not-run(not-beginner)
```
**Level findings**
1. **L34 is a rejected alternative.** "A reservation anchored to that process would vanish as soon as the first command returned." Cut it. No aidocs page covers merge-mutex internals, so the owner is unresolved: a new aidocs note, or the header of `aitask_merge_task.sh`.
2. **L64 is mechanism, and the fact is wrong (see "Facts that may be wrong" 1).** "Remove it with `rmdir`, never `rm -rf`: the guard is a directory whose emptiness is the proof that no reclaim is in progress." Replace with:
   > "2. **Clear a leaked guard, if `status` reports one.** `status` prints the `rmdir` command that removes it. Run that command only when no reclaim is in progress, and never use `rm -rf`."
   This also removes the undefined term "guard".
3. **L17 is a rejected alternative.** "…so a per-branch lock would not exclude them." → "There is one lock per repository, so two tasks merging into different output branches still wait for each other: they drive the same HEAD, index and working tree."

**Prose findings**
1. **L28** "\"Cannot tell\" is its own answer and is never rounded up to \"go ahead\"." sounds deep but adds nothing. Cut it; the next sentence already says the next task never clears it.
2. **L49–50** "**outlives the session**" and "**dies early**" are bold for emphasis. Unbold both.
3. **L76** "Three properties keep this procedure from looping:" is a run-up and "looping" is unclear. → "Three rules make `force-release` safe to run:"
4. **L47** "The framework does not enforce that second requirement." is vague. → "The framework cannot check that the PID represents the whole session."
5. **L38** "The next task takes it over only when that session is provably gone, as the table above shows; a holder whose liveness cannot be established stays in place until you clear it." repeats the table and L30. Cut it, and end the paragraph: "A session that dies mid-merge therefore leaves it held until the next task finds it provably gone or you [clear it](#recovering-a-stuck-merge-mutex)."

**Unresolved:** 8.

```
PAGE: website/content/docs/development/framework-session.md
level=findings:4  prose=findings:4  reader=not-run(not-beginner)
```
**Level findings**
1. **L34: implementation detail about unnamed private pane options, plus a rejected alternative.** The sentences are "It is stamped on the pane after the record is written." and "Two more pane options mark a frozen pane and a frozen-agent viewer that has finished starting up in it. Together they let the framework tell … without trusting a process name." Cut them. `aidocs/framework/agent_session_store.md` L52 already names `@aitask_frozen` and `@aitask_standin_ready`.
2. **L60: how the lease guarantee is implemented.** "a one-time nonce together with the coordinator's own process id. Every command that changes a leased record must present the matching nonce, so…" → "Each operation takes a lease on the record, owned by its coordinator. While the lease is held only that coordinator can change the record, so a coordinator that lost a race writes nothing instead of acting twice." Move the nonce detail to `aidocs/framework/agent_session_store.md`.
3. **L70: how the check is implemented (borderline).** "the pane's process must be one of its ancestors, and no Codex app-server daemon may sit between them." → "The hook records only when it runs inside the agent's own pane, never on another agent's behalf." Keep the Codex explanation that follows.
4. **L74: detection internals.** "the hook reads the CLI from the shape of the transcript path the agent reports: a Claude Code transcript lives under `projects/`, a Codex one is a `rollout-…` file. The path counts only when it names the very session being reported." → "For an agent you start by hand, the hook works out the CLI from the transcript path the agent reports, and only from a path that belongs to the session being reported." Move the path shapes to aidocs.
- **Not counted, for you to decide:** the state diagram (L40–54) labels its transitions with the sole writer's subcommand verbs (`freeze-begin`, `restore-abort`, …), which integrators do not call. Plain event labels would avoid this, but it is a code block.

**Prose findings**
1. **L30** "These three values are what survive the things that happen to a running agent." is vague. → "These three values survive a tmux server restart, a reattach or a respawn, which change the pane id and process id."
2. **L13** "It holds one record per agent, for every agent on the machine, across every project." repeats L9. → "It covers every project on the machine."
3. **L104 contradicts itself.** "Two things run this cleanup, so it does not depend on a TUI being open: the maintenance tick of `ait monitor` and `ait minimonitor`, and the freeze/restore coordinator…" But monitor and minimonitor are TUIs. → "Two things run this cleanup: the maintenance tick of `ait monitor` and `ait minimonitor`, and the freeze/restore coordinator, which reconciles after every operation, so a freeze or restore cleans up even when no monitor is open."
4. **L62** "The lease is what makes repair safe." is a run-up. Cut it. Also, at its first use, name the owner of `reconcile` as `aitask_frozen.sh reconcile`, which is the form `workflows/freeze-and-restore-agents.md` L266 shows.

**Unresolved:** 8.

```
PAGE: website/content/docs/development/skill-templating.md
level=findings:1  prose=findings:4  reader=not-run(not-beginner)
```
**Level findings**
1. **L56: test strategy and authoring syntax are contributor-only.** The paragraph runs "Skill authors write the `.md.j2` once … `{% if profile.<key> %}` … run `./.aitask-scripts/aitask_skill_verify.sh`; … regenerate the affected goldens, the expected render outputs the tests compare against, in the same commit."
   - **Fix:** replace L56 with "Profile-aware skills are authored in the framework repository; the authoring rules live in the engineering docs on [GitHub](…):" and merge it with L58.
   - `aidocs/framework/skill_authoring_conventions.md` (already linked) holds the verify and golden rules.

**Prose findings**
1. **L9** "renders one variant of a template per execution profile and coding agent, then follows it" reads as if it renders every variant. → "renders the variant of its template for the chosen execution profile and the running coding agent, then follows it".
2. **L40** "is shared with a future agent (`agy`)" breaks the current-state-only rule. → "because its skills root (`.agents/skills/`) can be read by more than one agent."
3. **One term per thing:** "coding agent" (L9) becomes "code agent" (L28) and "agent". Use "coding agent" throughout.
4. **L18** "different flows for the `default`, `fast` and `remote` profiles" names only the shipped profiles. → "different flows for each execution profile, such as the shipped `default`, `fast` and `remote`".

**Unresolved:** 5.

```
PAGE: website/content/docs/development/task-format.md   (changed hunks only)
level=findings:3  prose=findings:4  reader=not-run(not-beginner)
```
**Level findings**
1. **Design rationale (new "Where attachment blobs live").** "The ledger is one small file per blob rather than one shared index, so two unrelated attachments never contend for the same file on the shared task data branch." Cut it; `aidocs/attachment_metadata_bucketing.md` owns this.
2. **Lock mechanism of a guarantee.** "…commits all three together as one `ait:` commit while it holds the attach lock, so they cannot drift apart." → "…commits all three together as one `ait:` commit, so they cannot drift apart. Only one `ait attach add` or `rm` runs at a time in a repository; one started meanwhile stops with \"another attach operation is in progress — retry\"." (Source: `lib/attachment_lock.sh` L112.) Whether to keep the tree's `.attach.lock … serializes every change` line is your call; the busy error does name that path.
3. **New Status Workflow line points readers at code.** "The transitions are made by the workflow, not by hand: picking a task ([`aitask_pick_own.sh`](github…)), archiving it ([`aitask_archive.sh`](…)) and the [task abort procedure](…) hold the full transition logic." It links to source files as the documentation, `aitask_pick_own.sh` is not something integrators call, and "not by hand" is a staged contrast. → "The workflow makes these transitions when it picks, archives or aborts a task." Link to `concepts/task-lifecycle` instead of source, if it covers this.

**Prose findings**
1. **The prose repeats the table's "Belongs to" column.** "Of the six fields in an entry, two describe the attachment on this task and the other four describe the stored copy of the bytes, the blob, which every task attaching the same bytes shares:" → "Each entry's fields belong either to this task or to the blob, the stored copy of the bytes that every task attaching the same bytes shares:"
2. **One term per thing, plus a duplicated fact.** The new text says "reference ledger" / "ledger file", but the unchanged sentence just above says "both commands manage the blob, the manifest and the task file as one commit". The new `ait attach add … commits all three together` paragraph restates that sentence. Use "ledger file" in both places and keep the one-commit fact in one place only.
3. **Em dash as connector** in the table cell "`sha256:<64 hex digits>` — the identity". → "`sha256:<64 hex digits>`; the identity".
4. **New parent sentence** "it is marked superseded or obsolete only when none was" uses undefined terms and duplicates the `archived_reason` row (L47). → "…it takes the child's `archived_reason` only when none was (see [`archived_reason`](#frontmatter-fields))."

The Topic Anchoring hunk checks out against the code: normalization, the existence check, archived roots, batch `--parent` inheritance, interactive create writing no anchor, and the By-Topic fallback (`lib/topic_semantics.py` L68–86). The removed "`--followup-of` resolves to the root" fact now lives on `commands/task-management.md` L68, which the page links.

**Unresolved:** 7.

```
PAGE: website/content/docs/development/_index.md   (changed hunk only: lock idempotence bullet)
level=ok  prose=findings:1  reader=not-run(untagged)
```
**Prose findings**
1. **"Arguing with no one", the guide's own example on this subject.** "The same email alone is not enough: a lock held by another running (or unverifiable) session on the same host is refused, as described in…" → "Each lock belongs to one agent session, so a lock held by another running (or unverifiable) session on the same host is refused even under the same email, as described in [`ait lock`](…)."

**Unresolved:** 1.

```
BUDGET_USED:0 BUDGET_LEFT:0 NOT_RUN_CAP:none
```
**Changes made:** none (audit mode).

### Pre-existing (not in scope, not counted)

**`_index.md`**
- **No `depth` set**, although the page has its own content; that is why `reader=not-run(untagged)`. The guide requires it.
- **Wrong page type for its content.** By location it is an overview, but it holds long architecture reference.
- **Contributor-only detail:**
  - "git plumbing commands (`hash-object`, `mktree`, `commit-tree`)"
  - "random backoff up to 5 retries/attempts"
  - "Child tasks do not use the atomic counter — they use local file scan instead…"
  - the "internal script … not exposed via the `ait` dispatcher" framing
- **Lock-file bullet is out of date.** It says "(… task ID, email, timestamp, and hostname)" but omits `pid`/`pid_starttime`/`pid_starttime_kind`, which `commands/lock.md` documents and which the changed bullet now depends on.
- **Em dash:** "The pick itself is never blocked — a failed sweep…".

**`task-format.md`**
- **L47 `archived_reason` row:** "Written only by `ait archive --superseded` or `--obsolete`". There is no `ait archive` command (see "Facts that may be wrong" 6).
- **Unchanged nested-fields paragraph:** "blob" is used before it is defined.
- **"Fields the workflow writes for you":** bold for emphasis on "**not documented**".
- **No opening sentence:** the page starts directly with `## File Structure`.

### Facts that may be wrong

1. **merge-mutex.md L64 (guard removal).** The guard is not empty: it holds a holder record `h.<pid>.<nonce>/`, so a plain `rmdir` on it fails with ENOTEMPTY. The real cure is `rmdir '<dir>.gc'/h.* '<dir>.gc'`, which `status` prints, and only "if no reclaim is running". Sources: `aitask_merge_task.sh` L387 and L517, `lib/stale_lock.sh` L222–246.
2. **merge-mutex.md L47.** "checks only that `AIT_AGENT_PID` is a positive integer naming a process that exists": the code requires a value greater than 1. An invalid value is not refused; it is ignored with a warning, and the anchor falls back to the tmux pane (`lib/pid_anchor.sh` L459–466). Minor.
3. **task-format.md, new blob layout.** The `.aitask-data/attachments/…` tree and "committed on the task data branch" are true in branch mode only. In legacy mode, which is still supported, the data worktree is the repository root (`lib/task_utils.sh` L146), so `attachments/` sits at the repo root. The cache path also follows `$XDG_CACHE_HOME` (`lib/artifact_utils.sh` L88), not always `~/.cache`.
4. **task-format.md** "there is no command to move an attachment to another backend": `ait attach move` exists in the usage text as a "not yet implemented" stub. Low risk.
5. **framework-session.md L104** says cleanup does not depend on a TUI being open, but two of its three runners are TUIs (prose finding 3 above).
6. **task-format.md L47 (pre-existing):** `ait archive` does not exist. The `ait` dispatcher has no top-level `archive` case; the writer is `aitask_archive.sh`.
7. **gates.md, possible gap rather than an error.** The `default_gates` help text in `lib/profile_editor.py` L224–225 says declaring a human gate (`plan_approved`/`review_approved`/`merge_approved`) requires `record_gates: true`, "or archival deadlocks". gates.md does not say this.

**Checked against the code and found correct:**
- **Gates:** set resolution, ceiling and default, the empty set, the `gates: []` opt-out, the manual-verification allowlist dropping gates from both lists, the cleared tuple when a profile is missing, the registry keys and the `blocks_dependents` set, `--ignore-gates`, and that only fail/error spend the retry budget.
- **Merge mutex:** the verdict tokens, flags and subcommands.
- **Session store:** paths, modes, env vars, capture file names, the 60 s lease grace, `frozen.restore_ack_grace`, `@aitask_record`, and the sole writer.
- **Skill templating:** the `.gitignore` globs and remote-variant negations, the per-agent surfaces, and `ARGUMENTS` vs `$ARGUMENTS`.
- **Task format:** the parent archive-reason decision.
- **Links:** every relref anchor on these pages resolves.

### Destination pages (changed hunks) (verbatim)

/aitask-docs-review audit report. Run as `--caller audit --budget 0`, so nothing was edited. Guide: aitasks/metadata/doc_update_guide.md. It has a level model: field `depth`, beginner level `main-concept`.

Scope: only the regions shown by `git diff HEAD -- <page>`. Problems in unchanged text are listed under "Pre-existing (not in scope)" and are not counted.

Links: `python3 check_links.py --build` passed (broken: 0, SWEEP: PASSED). Every new relref and anchor resolves.

How to read "Unresolved": this is an audit, so nothing was fixed. "Unresolved" lists only findings that need a decision or a code check before anyone can edit. Every other finding comes with a ready replacement.

---

PAGE: website/content/docs/commands/lock.md
level=ok  prose=findings:5  reader=not-run(not-beginner)
Level findings: none.
- Retag `intermediate` → `advanced` is justified. Even before this change the page had exit codes (0/1/13/14 in the command table, 11/12 in the cleanup exit table), an internal branch (`aitask-locks`) and the lock-file YAML fields. The `intermediate` contract excludes all of these. The new section adds an outcome table and the `LOCK_FAILED` status token, which only `advanced` allows.
Prose findings:
1. Table row "You, from another session on this host, whose liveness cannot be established | Refused: "cannot tell" is its own answer and is never rounded up to "go ahead"". This is a saying that sounds deep and argues with no one, and it never says what the user sees.
   - Fix: "Refused the same way: nothing is claimed, and you are asked whether to leave it alone or reclaim it anyway".
   - Verified: task-workflow SKILL.md lines 269-275 use the same prompt shape, with the options "Pick a different task" / "Reclaim anyway".
2. Table row "You, via a lock that never recorded a session process (a lock that predates the session anchor, or a claim made outside tmux)". Two problems:
   - "session anchor" is undefined here. On the site it names the merge mutex's anchor (development/merge-mutex.md "## The session anchor"), and crash-recovery calls this one the "PID anchor", so this is one term for two things.
   - The row is also incomplete: a claim outside tmux records a process when `AIT_AGENT_PID` is set.
   - Fix: "(an older lock with no `pid` fields, or a claim made outside tmux without `AIT_AGENT_PID`)".
3. Table row "You, from this same session | Refreshed silently, so resume, re-pick and the ownership guard can run again on your own task". The term "the ownership guard" is not defined or linked anywhere on the page.
   - Fix: "...and the pick's ownership check can run again..." (or link to where it is defined).
   - There is also a possible fact problem; see "Facts that may be wrong" #4.
4. Rows "Claimed, with a multi-PC reclaim prompt" and "Claimed, with the anomaly prompt". Both terms are used before they are linked; the link only comes two paragraphs later ("The three claim prompts are on…"). At `advanced`, link at first use.
   - Fix: make them `[multi-PC reclaim prompt]({{< relref "/docs/workflows/crash-recovery" >}}#multi-pc-reclaim)` and `[anomaly prompt]({{< relref "/docs/workflows/crash-recovery" >}}#lock-anomaly-fallback)`.
5. "A lock is released when its task is archived or aborted, or when you run `ait lock --unlock`, and [Stale Lock Cleanup](#stale-lock-cleanup) removes locks left behind by tasks that are already archived." This is a run-on with two ", and" joins.
   - Fix: end the first sentence after "`ait lock --unlock`." and start a new one: "[Stale Lock Cleanup](#stale-lock-cleanup) removes locks left behind by tasks that are already archived."
Changes made: none (audit).
Reader report: not run (not beginner).
Unresolved: 1. Prose #3 (fact part, #4 below) needs confirmation against the pick flow before the row is reworded.
Pre-existing (not in scope):
- Line 124 "This matters because the failure is self-perpetuating if unreported…": inflated importance.
- Lines 68 and 145 use hand-written relative links (`../../tuis/board/`, `../../skills/aitask-pickweb/`). The guide prefers relref.
- The `--unlock` row says "Idempotent (succeeds even if not locked)" but lists no exit codes. `unlock_task` can `die_code 12` after retries (aitask_lock.sh:399).

PAGE: website/content/docs/commands/gates.md
level=ok  prose=ok  reader=not-run(not-beginner)
Level findings: none
Prose findings: none
- The `--gate` row was checked against `_force_one` in lib/gate_orchestrator.py:467. It overrides skip-already-passed and the retry budget, and refuses when predecessors are unmet. The row is correct.
Changes made: none
Reader report: not run
Unresolved: 0 (none)

PAGE: website/content/docs/commands/attach.md
level=ok  prose=findings:4  reader=not-run(not-beginner)
Level findings: none
Prose findings:
1. "they stay listable and fetchable, and only `add` refuses it." This contradicts the page's own rm section ("`rm` … does not work on one already packed into a numbered archive … `rm` refuses it"). The code agrees with the rm section (aitask_attach.sh:397-401).
   - Fix: "they stay listable and fetchable; `add` refuses an archived task, and `rm` refuses one already packed into a numbered archive."
2. "An archived task is still a real referrer, because its history stays browsable, so its attachments are kept indefinitely". "Real referrer" is a new word for something the page otherwise calls "reference(s)" (one term per thing), and "real" is filler.
   - Fix: "An archived task still references its attachments, because its history stays browsable, so they are kept indefinitely".
3. The section opens with "These operations change that list:", but one bullet is "Archiving a task changes nothing."
   - Fix: "This is how each operation on a task affects that list:".
4. "Folding a task into another moves its references to the primary task (see [Folded tasks](…))." The parenthetical reads like the source of the fact, but concepts/folded-tasks.md never mentions attachments.
   - Fix: link the verb instead: "[Folding]({{< relref "/docs/concepts/folded-tasks" >}}) a task into another moves its references to the primary task."
Changes made: none
Reader report: not run
Unresolved: 0 (none)
Pre-existing (not in scope): the intro sentence uses an em dash as a connector ("file attachments — content-addressed blobs").

PAGE: website/content/docs/commands/task-management.md
level=ok  prose=findings:1  reader=not-run(not-beginner)
Level findings: none
- Both rows were checked against `resolve_anchor` / `normalize_anchor_id` (aitask_create.sh:246-287, 2975) and aitask_update.sh:2547-2551: the flags, the exclusions, the child-source fallback that ignores the parent's own anchor, and `""` clears. All are correct.
Prose findings:
1. `--anchor` row: "stored in bare form". The term "bare form" is not defined.
   - Fix: "stored without the `t` prefix".
Changes made: none
Reader report: not run
Unresolved: 0 (none)

PAGE: website/content/docs/commands/setup-install.md
level=ok  prose=findings:1  reader=not-run(not-beginner)
Level findings: none
- The removed Codex version numbers (0.163.0 / 0.153.4) now live in aidocs/framework/agent_session_store.md "Codex hook timing (measured)". That move is correct.
- "Linux and macOS" is correct: macOS reads the open transcript through `lsof` (lib/agent_sessions.py:2015-2046).
Prose findings:
1. "On Linux and macOS, an older Codex agent has its session captured when it is frozen instead, from the transcript its process holds open". With the version parenthetical gone, "older" no longer refers to anything. In the code it means an older Codex release whose TUI never fires the hook (agent_freeze.py:388-389).
   - Fix: "On Linux and macOS, a Codex agent whose release never fires the hook in its interactive TUI has its session captured when it is frozen instead, …".
   - Optional: the next sentence repeats the "On Linux and macOS" opening; fold it in as "On those platforms a resumed Codex agent is verified…".
Changes made: none
Reader report: not run
Unresolved: 1. Prose #1: confirm the intended meaning of "older" before rewording.
Pre-existing (not in scope): heavy em-dash use across the session-hooks paragraphs.

PAGE: website/content/docs/commands/_index.md
level=ok  prose=ok  reader=not-run(untagged)
Level findings: none
- The page sets no `depth`. The guide lets an `_index.md` that is only a list of links leave it out, and this page is a link table.
- The changed row (the `ait skillrun` link retargeted with relref) is fine.
- Related type concern: the command index now sends a CLI subcommand to a skill page. See execution-profiles Level #1.
Prose findings: none
Changes made: none
Reader report: not run
Unresolved: 0 (none)

PAGE: website/content/docs/workflows/crash-recovery.md
level=ok  prose=ok  reader=not-run(not-beginner)
Level findings: none
- In scope: only the two See-also bullets. Both are fine. `ait lock --unlock` does not check the owner, so "force-release" is accurate.
Prose findings: none
Changes made: none
Reader report: not run
Unresolved: 0 (none)
Pre-existing (not in scope):
- The page is `intermediate` but carries content only `advanced` allows: status signals (`RECLAIM_CRASH:`, `LOCK_RECLAIM:`, `RECLAIM_STATUS:`, `LOCK_LIVE_HOLDER:`, `LOCK_UNVERIFIABLE_HOLDER:`), a signal table, a PID resolution order and `/proc`/`ps`/`kill` internals.
- Internal contradiction: "Lock anomaly fallback" lists "the lock is this session's own, being refreshed" as a RECLAIM_STATUS (anomaly prompt) case, while "When the Holder Is Still Running" says such a session "refreshes it silently".
- The term "ownership guard" is undefined.
- "this feature was built for" / "This case predates the PID-anchor work" are history wording, which the current-state-only rule forbids.

PAGE: website/content/docs/workflows/parallel-development.md
level=ok  prose=ok  reader=not-run(not-beginner)
Level findings: none
- Both links were retargeted to development/merge-mutex; the anchors resolve.
Prose findings: none
Changes made: none
Reader report: not run
Unresolved: 0 (none)

PAGE: website/content/docs/workflows/freeze-and-restore-agents.md
level=ok  prose=ok  reader=not-run(not-beginner)
Level findings: none
Prose findings: none
- The two relinked "see" targets and the reworded See-also bullet are fine.
Changes made: none
Reader report: not run
Unresolved: 0 (none)
Pre-existing (not in scope): line 229 still says "(measured on Codex 0.163.0; Codex 0.153.4 fires it only under `codex exec`)".
- aidocs/framework/agent_session_store.md now says "The public pages state only the rule… Keep version numbers here", so this move is incomplete.
- Fix: drop the parenthetical from line 229.

PAGE: website/content/docs/tuis/board/reference.md
level=ok  prose=findings:4  reader=not-run(not-beginner)
Level findings: none
- Checked against `topic_key` (lib/topic_semantics.py:68), `_build_topic_lanes` / `_topic_lane_label` (board/board_task_manager.py:98-188) and aitask_board.py:2962-2967 (`task_datas` plus `child_task_datas`, with `apply_filter` after mount). The rules are correct.
Prose findings:
1. "Lanes are built from every task the board has loaded, the task files under `aitasks/` and their children, before any search filter; archived tasks are not loaded." The appositive is hard to parse.
   - Fix: "Lanes are built from every task the board loads (the task files under `aitasks/` and their child tasks; archived tasks are not loaded), before any search filter applies."
2. "A topic with two or more of them gets its own lane". It is unclear what "them" refers to.
   - Fix: "A topic with two or more loaded tasks gets its own lane".
3. "…the inheritance rules under [Topic Anchoring](…/development/task-format#topic-anchoring), and when to use an anchor … on [Topic anchoring](…/concepts/topic-anchoring)." These are two adjacent links with near-identical text pointing at different pages.
   - Fix: change the first link's text to "the task file format's Topic Anchoring section".
4. Field table, `anchor` row: "Editing it moves a task that started standalone into a broader topic." This is vague ("broader") and too narrow, since editing can also move a child or re-anchor any task.
   - Fix: "Setting it moves the task into the topic rooted at that task id."
Changes made: none
Reader report: not run
Unresolved: 0 (none)

PAGE: website/content/docs/tuis/frozenagent/reference.md
level=ok  prose=ok  reader=not-run(not-beginner)
Level findings: none
Prose findings: none
- "Linux and macOS" was verified, as for setup-install.
Changes made: none
Reader report: not run
Unresolved: 0 (none)

PAGE: website/content/docs/skills/aitask-pick/execution-profiles.md
level=findings:2  prose=findings:3  reader=not-run(not-beginner)
Level findings:
1. Page type: the new `## ait skillrun` section is the reference for an `ait` CLI subcommand, placed on a skill page. The guide's doc landscape says `commands/` is "the `ait` CLI subcommand reference", and commands/_index.md now links its `ait skillrun` row into this skill page.
   - Fix: move the section to a commands/ page (a new commands/skillrun.md, or a section of commands/codeagent.md). Leave a one-line pointer here and point the `_index` row there.
2. At `advanced` the page should give every flag, but the skillrun section uses `--profile fast` and a trailing `42` in its example without explaining either.
   - Fix: add "`--profile <name>` selects the profile. Any further arguments, or everything after `--`, are passed to the skill."
   - Verified in aitask_skillrun.sh:86-111. The script's help also accepts `-h/--help`.
Prose findings:
1. "The resolver key is the skill's short name from the list above (`pick` for `/aitask-pick`)." The term "resolver key" is undefined, and the sentence partly repeats the "Valid skill names" line.
   - Fix: "In `default_profiles.<skill>`, `<skill>` is one of the valid skill names above (`pick` for `/aitask-pick`)."
2. "In live mode the merged YAML is written to …". The term "live mode" is undefined.
   - Fix: "Without `--dry-run`, the merged YAML is written to …".
3. "**Save persistently** writes …" / "**Save as one-shot** writes …". Bold marks on-screen labels, but the real button labels are "(S)ave" and "Save as (O)ne-shot" (lib/profile_editor.py:908-909; agent_command_screen.py:998-1003 passes no label override).
   - Fix: "**(S)ave** writes …" and "**Save as (O)ne-shot** writes …".
Changes made: none
Reader report: not run
Unresolved: 1. Level #1: where the `ait skillrun` reference should live is a placement decision for the user.
Pre-existing (not in scope): "Shipped Profiles" lists only `default` and `fast`, but `remote.yaml` ships in seed/profiles/ and the page's own Notes mention the shipped `remote` profile.

BUDGET_USED:0 BUDGET_LEFT:0 NOT_RUN_CAP:none

---

Facts that may be wrong:
1. execution-profiles.md: the button labels "Save persistently" / "Save as one-shot" do not match the UI ("(S)ave" / "Save as (O)ne-shot"). Confirmed in code.
2. attach.md: "only `add` refuses it" is wrong. `rm` also refuses an archived task that is packed into a bundle (aitask_attach.sh:397-401, and the page's own rm section). Confirmed.
3. lock.md, table row "…or a claim made outside tmux": incomplete. A claim made outside tmux with `AIT_AGENT_PID` set does record a process (crash-recovery.md PID resolution order). Confirmed.
4. lock.md, row "You, from this same session | Refreshed silently". This is true of the lock itself. However, aitask_pick_own.sh:783-806 still emits `RECLAIM_STATUS` (the anomaly prompt) after the refresh when the task was already `Implementing` and assigned to you, and task-workflow SKILL.md:240 lists "is this session's own" as an anomaly-fallback case. So a re-pick may not be silent. Not run end-to-end; confirm before rewording. crash-recovery.md carries the same contradiction (pre-existing).
5. setup-install.md: "an older Codex agent" no longer says older than what. The code means an older Codex release that never fires the hook interactively. Wording, not a wrong fact, but it now misleads.
6. freeze-and-restore-agents.md:229 (pre-existing): it still states the Codex version measurements, which aidocs now says belong only in aidocs.

### Fixer report for the development pages (verbatim)

I applied every listed fix across the seven files. The code contradicted one wording you supplied (the attach-lock busy behaviour), and I followed the code; it is the first item under code checks. `check_links.py --build` ends with **SWEEP: PASSED**. Nothing was committed, staged, stashed or restored. All seven files were present at the start (` M` or `??`).

**Code checks**
- **Attach lock busy behaviour.** Your wording said a second `ait attach add`/`rm` "stops with an error". In `lib/attachment_lock.sh` it first waits for `ATTACH_LOCK_TIMEOUT`, which defaults to 30 seconds, and only then dies with "ait attach: another attach operation is in progress — retry". So the page says it "waits up to 30 seconds, then stops with an error asking you to retry". I did not quote the message.
- **`AIT_AGENT_PID`** (`lib/pid_anchor.sh`): the value must be an integer greater than 1 naming a live process. Anything else is ignored with a warning, and the anchor falls back to the tmux pane. This matches your correction, and the old "positive integer" wording was wrong.
- **Leaked guard**: `status` (`aitask_merge_task.sh` ~L387) and the `force-release` dry run (~L517) both print `rmdir '<dir>.gc'/h.* '<dir>.gc'`, and `stale_lock.sh` confirms the `h.<pid>.<nonce>/` holder record. The reviewer was right that a plain `rmdir` fails. The holder-record layout is already in `aidocs/framework/shell_conventions.md` (~L207), so I added nothing to aidocs for it.
- **Also confirmed**:
  - the "stale tuple cleared; raw gates: fallback governs" message in `aitask_gate.sh` ~L1012
  - the `record_gates` key in `profile_editor.py`
  - `aitask_frozen.sh` has a `reconcile` verb
  - the attachments root is `.` in legacy mode (`task_utils.sh`)
  - the cache path uses `${XDG_CACHE_HOME:-$HOME/.cache}` (`artifact_utils.sh`)
  - `move` is an unimplemented stub in `aitask_attach.sh`
  - lease takeover needs both the 60-second grace to have elapsed and the owner pid to be dead (`_lease_stale` in `lib/agent_sessions.py`)

**development/gates.md**: fixes 1–10 applied as written. For fix 5, the cut paragraph had one clause not covered elsewhere: the tuple is distrusted "its list of filtered gates included". I kept it by adding that phrase to the digest paragraph ("Either way the tuple, its list of filtered gates included, is treated as absent…"). The Archival wording is now as you specified, with a link to `#the-digest`. The digest's three inputs, and which of them are checked from the task file, are unchanged.

**development/merge-mutex.md**: fixes 1–8 applied. Fix 5 now reads: "The framework cannot check that the PID represents the whole session. It checks only that `AIT_AGENT_PID` is an integer greater than 1 naming a process that is alive right now. A value that fails that check is ignored with a warning, and the anchor falls back to the tmux pane." The two failure directions are kept. Fix 6 uses your suggested wording. For fix 8, the cut fact that a holder of unknown liveness stays until a person clears it is still in the table row ("Left alone. Clearing it is a deliberate human act…").

**development/framework-session.md**: fixes 1–8 applied. For fix 6, the opening already says "one record per coding agent on the machine", so the sentence became "It covers every project on the machine." For fix 5, the next paragraph now reads "The pane id and the process id are the record's location, so when they change they are replaced on the same record", so the list of events is not repeated.

**development/skill-templating.md**: fixes 1–5 applied; one "code agent" was replaced. For fix 1, I checked that every cut fact is already in aidocs, so `skill_authoring_conventions.md` was not edited:
- the Claude Code version is written first, then the stubs on the other agents' surfaces (L231–234, L265)
- `{% if profile.… %}` (stub-skill-pattern.md L241, skill_authoring L318)
- `{% if agent == "claude" %}` (stub-skill-pattern.md L248)
- the verify script (skill_authoring L9–30)
- goldens regenerated in the same commit (skill_authoring L468–476)

The cut paragraph had no aitask-wrap example; `{% raw %}` is still named in the kept GitHub link list.

**development/task-format.md**: fixes 1–9 applied.
- For fix 1, `aidocs/attachment_metadata_bucketing.md` L39–43 already gives the per-blob rationale (no global write hotspot, no conflicts between unrelated attachments on the shared `.aitask-data` branch), so it was a cut only.
- For fix 3, I also changed "`local`, this layout committed on the task data branch" to "committed with the task data", because in legacy mode there is no separate branch.
- For fix 6, `aitask_attach.sh` shows that the attachment ledger file and the artifact manifest are different files. The old Nested-fields sentence ("both commands manage the blob, the manifest and the task file as one commit") was therefore wrong for attachments. It now says `ait artifact` commits the blob, the artifact's manifest and the task file as one commit, and that `ait attach` commits "as described under [Where attachment blobs live](#where-attachment-blobs-live)". The attach one-commit fact now lives only in that section.
- Prose now says "ledger file(s)" throughout. The tree comment inside the code block was not touched.

**development/_index.md**: fix 1 applied; the link target is unchanged.

**Facts moved to `aidocs/framework/agent_session_store.md`** (four new sections, inserted before "Codex hook timing"):
- framework-session.md "Identity and location" → "Pane options and the order they are stamped":
  - `@aitask_record` is stamped after the record is written
  - `@aitask_frozen` and `@aitask_standin_ready` mark a frozen pane and a viewer that has finished starting up
  - together they tell "the agent is still here" from "the viewer has taken over" without trusting a process name
- framework-session.md "Operation leases" → "What an operation lease holds": a one-time nonce plus the coordinator's process id, and every change must present the matching nonce. I added one sentence that the lease's process id is what reconcile checks for owner liveness, verified in `_lease_stale`.
- framework-session.md "When it records" → "How the session hook decides it is in the agent's own pane": the pane's process must be an ancestor of the hook, with no Codex app-server daemon in between.
- framework-session.md "Which CLI owns the session" → "How the session hook reads the CLI from a transcript path": a Claude Code transcript lives under `projects/`, a Codex one is a `rollout-…` file, and the path counts only when it names the session being reported.

Edited files:
- /home/ddt/Work/aitasks/website/content/docs/development/gates.md
- /home/ddt/Work/aitasks/website/content/docs/development/merge-mutex.md
- /home/ddt/Work/aitasks/website/content/docs/development/framework-session.md
- /home/ddt/Work/aitasks/website/content/docs/development/skill-templating.md
- /home/ddt/Work/aitasks/website/content/docs/development/task-format.md
- /home/ddt/Work/aitasks/website/content/docs/development/_index.md
- /home/ddt/Work/aitasks/aidocs/framework/agent_session_store.md

## Final review (Step 6) — round 2 and close

Round 2 reviewed every page changed since round 1 (concept pages in full; new
`development/` pages and `commands/skillrun.md` in full; the other destination
pages on their changed hunks), after the survival-check fixes. 24 findings on
the concept pages and 22 on the rest; every finding came with its exact
replacement text, and every fact finding with code evidence.

Decisions:
- Applied: all 24 concept-page findings, including six wrong
  facts verified in code before fixing — the merge mutex is a local lock
  directory, not a git branch (`lib/stale_lock.sh` `ait_lock_dir`; the storage
  fact was then added to `development/merge-mutex.md`); worktrees are optional
  and the merge mutex only applies in worktree mode; a profile-aware skill
  without a default uses the `default` profile (`aitask_skill_resolve_profile.sh`);
  only batch-mode `ait create` writes an anchor; a parent with pending children
  cannot be folded (`aitask_fold_validate.sh` `has_children`); `review_approved`
  is recorded from an attended approval or signed later with `ait gate pass`.
  Two facts the survival check had restored were found wrong and were dropped
  with this reason: `Editing` is not set by a TUI (chosen by hand), and status
  does not drive the priority sort (`aitask_ls.sh` sorts by blocked state,
  priority, effort).
- Applied: the 22 non-concept findings via a fixer agent, each fact re-verified
  in code; none contradicted.
- Kept (twice-raised, declined): the Status Workflow script links in
  `development/task-format.md` ("which component writes what").
- Brainstorm stays as a place `ait create` starts from (survival requirement),
  as "the brainstorm TUI".

**Close:** the round-2 fixes are the reviewers' own replacement sentences or
code-verified facts; the one sentence written afresh after round 2 (the merge
mutex storage location) was verified against `lib/stale_lock.sh` directly.
No further review round was run; `check_links.py --build` SWEEP PASSED,
`test_docs_vocabulary_coverage.sh` 32/32, `test_website_doc_lists.sh` pass,
`test_docs_review_contract.sh` 71/71 after the last edit.

### Link relevance (Step 8)

`check_link_relevance.py --report`: 8 records site-wide, 6 on pages this child
touched. Every target was opened:
- concepts/gates.md:62 and development/gates.md:124 → skills/aitask-gate-docs-updated#why-it-runs-where-it-runs: relevant (the link text promises exactly that section).
- development/_index.md:117 → commands/lock#when-a-pick-meets-a-held-lock: relevant (the bullet is about the same-host refusal that section tabulates).
- development/gates.md:177 → skills/aitask-run-gates#arguments: relevant (the `--gate` row states the forced-run rule).
- workflows/crash-recovery.md:30 and workflows/parallel-development.md:46: lines not changed by this child; targets relevant (lock record; parallel-admission page).
- tuis/monitor/how-to.md:242, workflows/risk-evaluation.md:38: pages not touched by this child.

### Round-2 reports (verbatim)

#### Concept pages

Guide: aitasks/metadata/doc_update_guide.md. It has a level model (field `depth`, beginner level `main-concept`). Caller is `audit`, so this run reports only and no page was edited. Budget is 0. `check_links.py --build` returned SWEEP: PASSED with 0 broken links. Every `**Next:**` footer matches the order in concepts/_index.md.

Facts were checked against the code. Each finding marked [fact] cites its evidence. Because this is an audit, every finding is also unresolved.

PAGE: website/content/docs/concepts/locks.md
level=findings:1  prose=findings:2  reader=not-run(cap)
Level findings:
- L1 (main-concept allows no flags). Line 48: "or when you run `ait lock --unlock`." Replace with: "or when you release it yourself with `ait lock`." The flag is already on commands/lock.md.
Prose findings:
- F1 [fact]. Lines 31–33: "The locks are kept in git, so the same push and fetch that share tasks between machines also share the locks, with no server to run."
  - Only task locks are in git, on the `aitask-locks` branch (aitask_lock.sh header).
  - The merge mutex is a local directory, `${TMPDIR:-/tmp}/aitask-locks-<uid>-<cksum>`. Evidence: lib/merge_lock.sh `merge_lock_dir` → lib/stale_lock.sh `ait_lock_dir`, lines 144–154.
  - Replace with: "Task locks are kept in git, so the same push and fetch that share tasks between machines also share them, with no server to run."
- F2 [fact]. Two sentences assume every task has its own branch:
  - Lines 18–19: "When a task is finished, its branch is merged back into the branch the work started from."
  - Line 35: "a task usually has its own **worktree**".
  - Evidence: a worktree is optional. The shipped `fast` profile sets `create_worktree: false` (seed/profiles/fast.yaml). The merge, and so the merge mutex, runs only in worktree mode (task-workflow/merge-broker.md, "Worktree mode only").
  - Replace lines 18–19 with: "When a task that has its own branch is finished, that branch is merged back into the branch the work started from."
  - Replace line 35's clause with: "a task can have its own **worktree**".
Changes made: none (audit)
Reader report: not run (budget 0)
Unresolved: 3 — L1, F1, F2

PAGE: website/content/docs/concepts/gates.md
level=ok  prose=findings:3  reader=not-run(not-beginner)
Level findings: none
Prose findings:
- G1 [fact]. Lines 55–56: "A human gate such as `review_approved` is signed by the reviewer with `ait gate pass <task> <gate>`, never by an agent."
  - Evidence: in an attended session the workflow records `review_approved` from your interactive approval. See task-workflow/SKILL.md line 817 (Gate Recording Procedure) and gates_reference.yaml lines 107–111 ("DUAL transport"). `ait gate pass` is the route for the headless lane, or for signing later (development/gates.md "Kinds of gate").
  - Replace with: "A human gate such as `review_approved` waits for a person: it is recorded when you approve the review in an attended session, or the reviewer signs it later with `ait gate pass <task> <gate>`. An agent never approves it on its own."
- G2 [contradiction]. Lines 16–17, "a task archives only once every gate its workflow enforces is satisfied", conflicts with line 57, "Archiving with an unmet gate needs an explicit override". Replace the first with: "a task archives only once every gate its workflow enforces is satisfied, unless you explicitly override that check."
- G3 [vague claim; link text does not match its target]. Lines 54–55: "[`ait gates`](…#when-to-run-sync-registry) covers a gate that has no way to run."
  - Replace with: "When a gate cannot pass because the registry never says how to check it, run [`ait gates sync-registry`]({{< relref "/docs/commands/gates" >}}#when-to-run-sync-registry)."
  - The concrete fact comes from commands/gates.md "When to run sync-registry".
Changes made: none (audit)
Reader report: not run (budget 0)
Unresolved: 3 — G1, G2, G3

PAGE: website/content/docs/concepts/framework-session.md
level=ok  prose=ok  reader=not-run(not-beginner)
Level findings: none
Prose findings: none
- Checked against the code: the record's fields (lib/agent_sessions.py: window, slot, task_id, agent_string, codeagent_session_id), the `f`/`Z` keys in monitor and minimonitor, the `R` key in frozenagent, and the setup hook prompt.
Changes made: none
Reader report: not run (budget 0)
Unresolved: 0 — none

PAGE: website/content/docs/concepts/skill-templating.md
level=ok  prose=findings:1  reader=not-run(not-beginner)
Level findings: none
Prose findings:
- S1 [fact]. Line 33: "Without a default, the skill asks you to choose."
  - Evidence: the stub (e.g. .claude/skills/aitask-pick/SKILL.md, step 1) runs aitask_skill_resolve_profile.sh. That script falls back to `default` (line 72: `[[ -z "$value" ]] && value="default"`), and the variant has the profile baked in at render time. No selection prompt runs.
  - Replace with: "Without a default, the skill uses the `default` profile."
Changes made: none
Reader report: not run (budget 0)
Unresolved: 1 — S1

PAGE: website/content/docs/concepts/attachments.md
level=ok  prose=findings:2  reader=not-run(not-beginner)
Level findings: none
Prose findings:
- A1 [one term per thing / term not introduced]. Line 16 says "aitasks identifies an attachment by its content". Lines 30–31 then rely on "the hash the task recorded", and "hash" is never introduced. Replace line 16's clause with: "aitasks identifies an attachment by a hash of its content".
- A2 [clarity]. Lines 45–46: "When a task is folded, that is merged into another task, its attachments move to that task." Replace with: "When a task is folded (merged into another task), its attachments move to that task."
Changes made: none
Reader report: not run (budget 0)
Unresolved: 2 — A1, A2

PAGE: website/content/docs/concepts/topic-anchoring.md
level=ok  prose=findings:2  reader=not-run(cap)
Level findings: none
Prose findings:
- T1 [fact]. Lines 53–55: "To put a task in a topic yourself, tell `ait create` either the root's task number or the task the new one follows up; for a follow-up it finds the root for you."
  - Evidence: only batch mode takes an anchor. `--anchor` and `--followup-of` are batch flags (aitask_create.sh lines 102–109 and 220–221). development/task-format.md lines 222–223 say: "Interactive `ait create` (without `--batch`) writes no anchor for any task".
  - Replace with: "To put a new task in a topic yourself, create it with `ait create` in batch mode and give it either the root's task number or the task it follows up; for a follow-up it finds the root for you."
- T2 [one long sentence with definitions nested inside it]. Lines 56–57: "The task detail screen of the board, the terminal view that shows your tasks as cards in columns and that `ait board` opens, can edit the anchor too."
  - Replace with: "You can also edit the anchor on the task detail screen of the board, the terminal view that `ait board` opens, which shows your tasks as cards in columns."
Changes made: none
Reader report: not run (budget 0)
Unresolved: 2 — T1, T2

PAGE: website/content/docs/concepts/tasks.md
level=ok  prose=ok  reader=not-run(cap)
Level findings: none
Prose findings: none
Changes made: none
Reader report: not run (budget 0)
Unresolved: 0 — none

PAGE: website/content/docs/concepts/plans.md
level=ok  prose=findings:2  reader=not-run(cap)
Level findings: none
Prose findings:
- P1 [ambiguity]. Lines 30–32: "Child tasks split from the same parent task (see [Parent and child tasks]) read it first". The sentence never says which task shares that parent.
  - Replace with: "When the task is a child task, the agents that work on its sibling tasks, split from the same parent (see [Parent and child tasks]({{< relref "/docs/concepts/parent-child" >}})), read its plan first".
- P2 [fact]. Line 50, See also: "[Verified scores] — plan verification feeds into per-model reliability tracking".
  - Evidence: verified scores come only from the satisfaction rating at the end of a skill (task-workflow/satisfaction-feedback.md → `aitask_verified_update.sh --score`). Plan verification (aitask_plan_verified.sh) writes `plan_verified` entries in the plan file and never updates scores.
  - Replace with: "[Verified scores]({{< relref "/docs/concepts/verified-scores" >}}) — how your rating at the end of a skill run becomes a per-model reliability score".
Changes made: none
Reader report: not run (budget 0)
Unresolved: 2 — P1, P2

PAGE: website/content/docs/concepts/parent-child.md
level=ok  prose=ok  reader=not-run(cap)
Level findings: none
Prose findings: none
- Checked against the code: the sibling auto-dependency (`--no-sibling-dep` is the opt-out in aitask_create.sh), parent auto-archive (`PARENT_ARCHIVED` in aitask_archive.sh), and the board's child count and child picker.
Changes made: none
Reader report: not run (budget 0)
Unresolved: 0 — none

PAGE: website/content/docs/concepts/task-lifecycle.md
level=findings:2  prose=findings:3  reader=not-run(cap)
Level findings:
- TL1 (main-concept: define or link a term at first use). Line 17: "A coding agent has started work on it and holds its task lock." This is the first use of "task lock", and its link only comes on line 22. Replace with: "A coding agent has started work on it and holds its [task lock]({{< relref "/docs/concepts/locks" >}})."
- TL2 (main-concept allows no flags). Line 30: "or with `ait update --status`". Replace with: "or with `ait update`".
Prose findings:
- TL3 [fact]. Line 16, the `Editing` row: "Still being written or revised in a TUI, one of the full-screen terminal apps such as the board; not ready to start yet."
  - Evidence: nothing sets `Editing` when a TUI edits a task. It is chosen by hand: the board detail status options (board_detail_screen.py line 1816), `ait update`, or the abort option "Task needs modifications before ready" (task-workflow/task-abort.md line 32).
  - Replace with: "Still being written or revised; not ready to start yet." This also removes the only use of "TUI" on the page.
- TL4 [repeats a table value]. Line 26: "; a `Postponed` task stays listed without being offered". This restates the `Postponed` table row (line 18). Cut it and end the sentence at "which are finished."
- TL5 [unsupported or vague claim]. Line 26: "so the board, task selection and the sort by priority each handle only a handful of states."
  - Evidence: the task-listing sort (aitask_ls.sh lines 936–946) orders by blocked state, priority and effort. Status only filters the list (`STATUS_FILTER="Ready"`).
  - Replace with: "so the board and task selection each handle only a handful of states." The dropped clause is wrong, so it moves nowhere.
Changes made: none
Reader report: not run (budget 0)
Unresolved: 5 — TL1, TL2, TL3, TL4, TL5

PAGE: website/content/docs/concepts/folded-tasks.md
level=ok  prose=findings:2  reader=not-run(not-beginner)
Level findings: none
Prose findings:
- FT1 [fact]. Lines 30–31: "Both parent and child tasks can be folded."
  - Evidence: aitask_fold_validate.sh refuses a parent with pending children (`INVALID:<id>:has_children`, lines 101–107). task-workflow/planning.md line 253 says "standalone parent tasks".
  - Replace with: "Both standalone tasks and child tasks can be folded; a parent task that still has children cannot."
- FT2 [clarity; "during planning" appears twice]. Lines 27–30: "Folding can also happen during planning in [`/aitask-pick`]: if the task's description, or you during planning, asks for other tasks to be folded in, the workflow folds them before planning continues."
  - Replace with: "Folding can also happen while [`/aitask-pick`]({{< relref "/docs/skills/aitask-pick" >}}) plans a task: when the task's description or you ask for other tasks to be folded in, the workflow folds them before planning continues."
Changes made: none
Reader report: not run (budget 0)
Unresolved: 2 — FT1, FT2

PAGE: website/content/docs/concepts/artifacts.md
level=findings:1  prose=findings:3  reader=not-run(not-beginner)
(Not re-reported, as agreed: the backend table and the `advanced` depth.)
Level findings:
- AR1 (concept page rule: "What it is" carries no mechanism). Line 13: "Resolving a handle therefore goes handle → manifest → backend → local cache."
  - This is mechanism, and "therefore" claims a link that isn't there. Cut it and keep "The backend is where the blobs actually live:" as the table's lead-in.
  - The chain moves to commands/artifact.md, whose `get` section already describes the local cache (lines 122–124).
  - It sits next to the deferred table, so the commands audit may take it.
Prose findings:
- AR2 [false "so"]. Line 11: "…identified by the SHA-256 of its bytes, so every fetch is checked against its hash and each machine keeps a local cache under `~/.cache/ait/artifacts/`." Content hashing does not cause the cache.
  - Replace with: "…identified by the SHA-256 of its bytes, so every fetch is checked against its hash. Each machine keeps a local cache of fetched versions under `~/.cache/ait/artifacts/`."
  - The path is confirmed in lib/artifact_cache.sh line 5.
- AR3 [em dash as connector]. Line 11: "a versioned output that belongs to a task — an HTML plan, an implementation trail, a report, a mockup." Replace with: "a versioned output that belongs to a task, such as an HTML plan, an implementation trail, a report or a mockup."
- AR4 [fact/precision]. Line 29: "Choosing a backend keeps large blobs off the task data branch: start on `local`, then move artifacts to `dir` or `gitbranch` when the data branch should stay small."
  - `local` stores blobs on the task data branch (the page's own table row, line 17). So choosing a backend does not by itself keep blobs off that branch.
  - Replace with: "Choosing `dir` or `gitbranch` keeps large blobs off the task data branch: start on `local`, then move artifacts to one of them when the data branch should stay small."
Changes made: none
Reader report: not run (budget 0)
Unresolved: 4 — AR1, AR2, AR3, AR4

Out of scope, not counted: the wrong fact in S1 also appears on website/content/docs/skills/aitask-pick/execution-profiles.md, under "Resolution Order" item 4: "Interactive selection / auto-select (fallback)". For a profile-aware skill, the fallback is the `default` profile (same evidence as S1).

BUDGET_USED:0 BUDGET_LEFT:0 NOT_RUN_CAP:website/content/docs/concepts/locks.md, website/content/docs/concepts/topic-anchoring.md, website/content/docs/concepts/tasks.md, website/content/docs/concepts/plans.md, website/content/docs/concepts/parent-child.md, website/content/docs/concepts/task-lifecycle.md

FINDINGS_TOTAL:24

#### Other pages

Docs review, round 2: `/aitask-docs-review --caller audit --budget 0`. Report only; nothing was edited.

The guide is `aitasks/metadata/doc_update_guide.md` and it has a level model (`depth`, beginner level `main-concept`). None of the pages in scope is at `main-concept`, so the fresh-reader test did not apply. `check_links.py --build` passes (0 broken links). Findings marked [fact] were checked against `.aitask-scripts/`, with evidence given.

PAGE: website/content/docs/development/gates.md
level=findings:2  prose=findings:1  reader=not-run(not-beginner)
Level findings:
1. [fact] Retry budgets: "Once the budget is spent the gate reports itself exhausted and waits for a person." This leaves out the stopping rule (`is_stuck` in `lib/gate_orchestrator.py`). After two failures in a row on the same code, the gate is not run again, even with budget left. Add after that sentence: "A gate also stops early, with budget left, once its last two failures ran on unchanged code; a code change makes it eligible again."
2. [fact] "To run an exhausted gate again after fixing its cause, force it with `ait gates run <task> --gate <name>`: …" This does not hold for a procedure-backed gate. `_force_one` hands any gate with a `verifier` to `_run_machine_gate`. For `docs_updated` that resolves to `aitask_gate_docs_updated.sh`, which does not exist, so the run is recorded as `error` (`_spawn_verifier` turns the OSError into 3). Add: "This applies to command gates only: forcing a procedure-backed gate such as `docs_updated` does not run its skill and records an `error`." (This is also a code bug. `_force_one` should defer `kind: procedure` gates the way `run()` does.)
Prose findings:
1. A closing line that repeats an earlier point: "An addition the profile filtered out is dropped, so a filtered gate holds back neither archival nor dependents while the stored enforced set is valid." The Archival section already says this. Replace with: "An addition the profile filtered out is dropped while the stored enforced set is valid."
Changes made: none
Reader report: not run
Unresolved: 3 — all of the above

PAGE: website/content/docs/development/merge-mutex.md
level=ok  prose=findings:3  reader=not-run(not-beginner)
Level findings: none. Facts checked: NO_SESSION_ANCHOR, the `AIT_AGENT_PID` check (integer >1 and alive, otherwise a warning and fallback), REFUSED_LIVE_HOLDER, the `--abort-merge` / `--reset-hard` remedies, the `--expect` token, the fields `status` prints, and that an `unknown` holder is never reclaimed automatically.
Prose findings:
1. Staged contrast: "Taking the mutex, merging and releasing it are three separate short-lived commands, so the reservation is anchored to the **agent session** (the running agent that owns the task), which lasts through all three, and not to the process of the command that took it, which exits as soon as that command returns." Replace with: "Taking the mutex, merging and releasing it are three separate short-lived commands, and each one's process exits as soon as it returns, so the reservation is anchored to the **agent session** (the running agent that owns the task), which lasts through all three."
2. A closing line that repeats the three rules above it: "So every run ends one of two ways: the mutex is released, or the tool names the reason it will not act on it." Cut it.
3. "Guard" is never defined: "**Clear a leaked guard, if `status` reports one.** `status` prints the `rmdir` command that removes it." Replace with: "**Clear a leaked guard, if `status` reports one.** The guard is a directory a reclaim holds while it runs; one left behind blocks recovery. `status` prints the `rmdir` command that removes it."
Changes made: none
Reader report: not run
Unresolved: 3 — all of the above

PAGE: website/content/docs/development/framework-session.md
level=findings:4  prose=ok  reader=not-run(not-beginner)
Level findings:
1. [fact] Takeover is claimed without a condition: "An agent that starts in a window whose `live` record has lost its process takes over that record, so a restarted tmux does not produce a second record for an agent the store already knows." In `upsert`, takeover happens only when exactly one such dead `live` record is in that window. With two or more, it creates a new record (`ambiguous_relocation`). Replace with: "An agent that starts in a window where exactly one `live` record has lost its process takes over that record, so a restarted tmux does not produce a second record for an agent the store already knows. When two or more such records share the window, nothing tells them apart: the agent gets a new record and the old ones are left to the [cleanup rules](#cleanup-rules)." The same condition applies to "An agent started again in that window before then takes over the record; …"
2. [fact] The record id is never introduced, yet `frozen/<id>/` uses it, and a renamed window keeps its record (`_follow_window`; the id is the primary key). After "A record is identified by its project root, its tmux window name and its slot.", add: "It also has a generated id, which names its capture directory and is what `@aitask_record` stores; when its window is renamed, the record keeps its id and takes the new name."
3. [fact] Claims too much: "…records the agent's session id into its record, which is what makes a later restore possible at all." A re-pick restore needs no session id. A Codex session can also be captured at freeze time from the transcript its process holds open (`_observe_codex_session`). Replace with: "…records the agent's session id into its record, which is what lets a later restore resume that session."
4. [fact] The diagram footer "drop, from any state: the record and its capture files are removed" leaves out the harvest check in `drop()`. Keep the diagram as it is and add below it: "A drop is refused while the record holds captured text that [sitrep]({{< relref "/docs/workflows/sitrep" >}}) has not harvested; `aitask_frozen.sh drop` runs that harvest first."
Prose findings: none. Facts checked: the 0600/0700 modes, the five states and their transitions, the 60 s lease grace (fixed outside test mode), `dead_window` / `dead_pane` / `capture_missing`, the `raw`-default resume rule, the late-ack upgrade and both override variables.
Changes made: none
Reader report: not run
Unresolved: 4 — all of the above

PAGE: website/content/docs/development/skill-templating.md
level=findings:1  prose=ok  reader=not-run(not-beginner)
Level findings:
1. [fact] "The same flow runs on every supported coding agent; only the stub's discovery surface and the rendered-variant directory differ." The stub also passes a different `--agent` value (`codex` in `.agents/skills/aitask-pick/SKILL.md`, `opencode` in `.opencode/commands/aitask-pick.md`). Replace with: "…only the stub's discovery surface, the `--agent` value it passes and the rendered-variant directory differ."
Prose findings: none
Changes made: none
Reader report: not run
Unresolved: 1

PAGE: website/content/docs/commands/skillrun.md
level=findings:2  prose=ok  reader=not-run(not-beginner)
Level findings:
1. [fact] "`ait skillrun` starts a code agent with an aitask skill's slash command already typed in…" The command is passed as the agent's initial prompt and runs at once (`claude --model … "/aitask-… --profile …"`). It does not wait in the input box. Replace with: "`ait skillrun` starts a code agent that runs an aitask skill's slash command as its first prompt, under the execution profile you choose."
2. [fact] What happens with `--dry-run` is missing. After "With `--profile-override`, and without `--dry-run`, the merged YAML is written to …", add: "With `--dry-run`, the merged YAML is printed to standard error instead, and no file is written."
Prose findings: none
Changes made: none
Reader report: not run
Unresolved: 2

PAGE: website/content/docs/development/task-format.md (changed regions)
level=findings:1  prose=findings:2  reader=not-run(not-beginner)
Level findings:
1. This is contributor-only detail (code structure, not scripts an integrator calls): "…the logic is in [`aitask_pick_own.sh`](…), [`aitask_archive.sh`](…) and the [task abort procedure](…)." Replace the sentence with "The workflow makes these transitions when it picks, archives or aborts a task." The file pointers belong in `aidocs/`.
Prose findings:
1. Ambiguous, because the header has four fields with "branch" in the name: "A task worked on the current branch, with no worktree, records the checked-out branch in both branch fields." Replace with: "…records the checked-out branch in both `Base branch` and `Output branch`." (`planning.md` means these two.)
2. This hints at a future change, against the current-state-only rule: "…and `ait attach` cannot move an attachment to another backend yet." Replace with: "…and `ait attach move` is not implemented."
Facts checked: the blob/meta layout, the 30 s lock timeout, local-only `add`, the `XDG_CACHE_HOME` cache and the symlink, the `ait:` commits, anchor normalization and parent inheritance, Done set at archival, a parent's `archived_reason` only when no child landed, and the plan-header fields.
Changes made: none
Reader report: not run
Unresolved: 3

PAGE: website/content/docs/commands/lock.md (changed regions)
level=findings:1  prose=ok  reader=not-run(not-beginner)
Level findings:
1. [fact] "Releasing a lock, including a forced unlock, is likewise one commit on that branch, so no server is involved." `unlock_task` pushes to `origin` (`git push origin …:refs/heads/aitask-locks`), and the branch exists only on the remote. Replace with: "Releasing a lock, including a forced unlock, is likewise one commit pushed to that branch."
Prose findings: none. The held-lock table matches `lock_task` and `aitask_pick_own.sh`.
Changes made: none
Reader report: not run
Unresolved: 1

PAGE: website/content/docs/commands/attach.md (changed regions)
level=ok  prose=findings:2  reader=not-run(not-beginner)
Level findings: none. Facts checked: archived owners are refused by `add`, and by `rm` only once bundled; fold rebinding; board-delete decref with rebinding to revived tasks.
Prose findings:
1. A term this intermediate page does not link: "…`rm` refuses one already packed into a numbered archive." Replace with: "…`rm` refuses one already packed into a [numbered archive]({{< relref "/docs/development/task-format" >}}#archive-storage)."
2. An unclear term: "Deleting a task from `ait board` releases its references, or hands them to any folded task the delete revives." Replace with: "Deleting a task from `ait board` releases its references. When other tasks had been folded into it, the delete restores them, and each takes back the references it still lists."
Changes made: none
Reader report: not run
Unresolved: 2

PAGE: website/content/docs/commands/task-management.md (changed regions)
level=ok  prose=findings:1  reader=not-run(not-beginner)
Level findings: none. The `--anchor` / `--followup-of` rows match `resolve_anchor` and `normalize_anchor_id`.
Prose findings:
1. One term per thing (elsewhere it is the brainstorm TUI, lowercase), and brainstorm only calls `aitask_create.sh --batch` for module tasks: "It is typically started from inside a TUI such as the [board](…) or Brainstorm." Replace with: "It is typically started from inside a TUI such as the [board](…)."
Changes made: none
Reader report: not run
Unresolved: 1

PAGE: website/content/docs/commands/gates.md (changed regions)
level=ok  prose=ok  reader=not-run(not-beginner)
Level findings: none. The `--gate` row matches `_force_one`; the procedure-gate caveat is development/gates.md finding 2.
Prose findings: none. Changes made: none. Reader report: not run. Unresolved: 0

PAGE: website/content/docs/commands/setup-install.md (changed regions)
level=ok  prose=ok  reader=not-run(not-beginner)
Level findings: none. Prose findings: none. Changes made: none. Reader report: not run. Unresolved: 0

PAGE: website/content/docs/commands/_index.md (changed regions)
level=ok  prose=ok  reader=not-run(untagged)
Level findings: none in the changed region. Prose findings: none. Changes made: none. Reader report: not run. Unresolved: 0

PAGE: website/content/docs/development/_index.md (changed regions)
level=ok  prose=ok  reader=not-run(untagged)
Level findings: none in the changed region. Prose findings: none. Changes made: none. Reader report: not run. Unresolved: 0

PAGE: website/content/docs/workflows/crash-recovery.md (changed regions)
level=ok  prose=ok  reader=not-run(not-beginner)
Level findings: none. Prose findings: none. Changes made: none. Reader report: not run. Unresolved: 0

PAGE: website/content/docs/workflows/parallel-development.md (changed regions)
level=ok  prose=ok  reader=not-run(not-beginner)
Level findings: none. Prose findings: none. Changes made: none. Reader report: not run. Unresolved: 0

PAGE: website/content/docs/workflows/freeze-and-restore-agents.md (changed regions)
level=ok  prose=ok  reader=not-run(not-beginner)
Level findings: none. Prose findings: none. Changes made: none. Reader report: not run. Unresolved: 0

PAGE: website/content/docs/tuis/board/reference.md (changed regions)
level=ok  prose=ok  reader=not-run(not-beginner)
Level findings: none. The lane rules match `_build_topic_lanes`, `_topic_lane_label` and `topic_key`. Prose findings: none. Changes made: none. Reader report: not run. Unresolved: 0

PAGE: website/content/docs/tuis/frozenagent/reference.md (changed regions)
level=ok  prose=ok  reader=not-run(not-beginner)
Level findings: none. Prose findings: none. Changes made: none. Reader report: not run. Unresolved: 0

PAGE: website/content/docs/skills/aitask-pick/execution-profiles.md (changed regions)
level=ok  prose=ok  reader=not-run(not-beginner)
Level findings: none. The one-shot save and the 1 h prune match `agent_command_screen.py`. Prose findings: none. Changes made: none. Reader report: not run. Unresolved: 0

PAGE: aidocs/framework/agent_session_store.md (accuracy only)
level=n/a  prose=n/a  reader=not-run(not-beginner)
Accuracy findings:
1. [fact] "A lease is a one-time nonce together with the coordinator's own process id." The lease also stores when it was taken (`_mint_lease` sets `op_nonce`, `op_owner_pid` and `op_started_at`), and that time is half of the takeover rule. Replace it and the paragraph's last sentence with: "A lease is a one-time nonce, the coordinator's own process id and the time it was taken (`op_nonce`, `op_owner_pid`, `op_started_at`). Every command that changes a leased record must present the matching nonce; that is how a coordinator that lost a race is made to write nothing. `reconcile` takes a lease over only when 60 seconds have passed since it was taken and that process id is no longer alive (`_lease_stale`)."
2. [fact] "The hook records only when the pane's process is one of its ancestors and no Codex app-server daemon sits between them." The hook also refuses when its process ancestry cannot be established, or when a process between it and the pane cannot be identified (`aitask_session_hook.sh` §5b, `_codex_daemon_hop` return 2). Replace with: "The hook records only when the pane's process is one of its ancestors and every process between them can be identified and none is the Codex app-server daemon."
Everything else checked out: the `registry_lock` / `os.replace` description, the stamp order, the pane options, the transcript-path shapes, the `/proc` / `lsof` / `KERN_PROCARGS2` probes, the Codex version notes, and every referenced section and fixture file.
Unresolved: 2

Pre-existing (not in scope, not counted):
- `development/_index.md` and `commands/_index.md` set no `depth`, though both have content of their own. The guide requires it.
- `workflows/freeze-and-restore-agents.md`, unchanged context line: "nothing can yet tell which conversation belongs to its pane". "yet" breaks the current-state-only rule.

BUDGET_USED:0 BUDGET_LEFT:0 NOT_RUN_CAP:none

FINDINGS_TOTAL:22

#### Fixer report (non-concept pages)

I applied all 22 fixes and checked every "[fact]" against the code; no code contradicted any of them. Both checks pass: `check_links.py --build` ends with `SWEEP: PASSED`, and `test_docs_vocabulary_coverage.sh` reports `Results: 32/32 passed, 0 failed`. Nothing was committed, staged, stashed or restored.

**website/content/docs/development/gates.md**
1. Applied, reworded to what `is_stuck` checks: "A machine gate also stops early, with budget left, once its two most recent runs both failed on the code as it is now; a change to the code makes it eligible again." `is_stuck` only drops machine gates from automatic dispatch, so I said "machine gate". "The code" here is the commit plus staged, unstaged and untracked changes, with task and plan data left out (`code_digest`).
2. Applied, with the opening reworded because the page never defines "command gates": "This applies only to gates whose verifier is a command: forcing a procedure-backed gate such as `docs_updated` does not run its skill and records an `error`." The code confirms it: `_force_one` calls `_run_machine_gate` for any gate with a verifier and does not check `kind: procedure`. `resolve_verifier` turns `aitask-gate-docs-updated` into `.aitask-scripts/aitask_gate_docs_updated.sh`, which does not exist. The launch then fails, which maps to exit code 3 and so to `error`.
3. Applied, using the dependents variant: "…is dropped, so it holds back no dependents while the stored enforced set is valid." The Archival section still says a filtered gate never blocks archival, and dependents are not stated anywhere else.

**website/content/docs/development/merge-mutex.md**
4. Applied verbatim.
5. Applied verbatim.
6. Applied verbatim. The code confirms both points:
   - **The guard is held during a reclaim.** `stale_lock.sh` runs every lock-directory change (acquire, release, reclaim) under the `.gc` guard, and `force-release` runs inside it too.
   - **A leftover guard blocks recovery.** The merge lock never automatically reclaims a guard that has no holder record (`merge_lock.sh` around line 259, and the "If a leaked .gc guard blocks recovery" hint in `aitask_merge_task.sh`).
   - **One nuance:** the guard is also held during acquire and release, not only during a reclaim. The new sentence is incomplete on that point but not wrong.

**website/content/docs/development/framework-session.md**
7. Applied, including the `ambiguous_relocation` sentence; the code confirms it. In the Cleanup paragraph the later sentence now reads "…takes over the record when it is the only `live` record in that window to have lost its process;" because "exactly one" did not read naturally there.
8. Applied, with two changes:
   - **Moved:** the sentence goes at the end of the paragraph, after "These three values survive…", so that "three values" still clearly means root, window and slot.
   - **Reworded:** it starts "Each record also has a generated id…".
   The code confirms it: the id is the primary key, it names the capture directory (`capture_dir(record_id)`), `@aitask_record` holds it, and `_follow_window` gives the record the window's new name.
9. Applied verbatim.
10. Applied below the state diagram. The `/docs/workflows/sitrep` page exists and is linked without an anchor. The code confirms it: `drop()` raises `HarvestRequired` unless the text has been harvested, and `aitask_frozen.sh drop` runs the harvest first. The code also has a `--skip-harvest` discard, which I did not add.

**website/content/docs/development/skill-templating.md**
11. Applied. The stubs pass `--agent claude`, `codex` or `opencode` respectively.

**website/content/docs/commands/skillrun.md**
12. Applied. The code confirms it: the command is passed as the agent's first prompt (a positional argument for claude and codex, `--prompt` for opencode).
13. Applied with one word added: "…and no profile file is written." In dry-run the merged YAML does go to standard error and no profile file is created. But `--profile-override -` still copies standard input into a temporary file in both modes, so "no file is written" would not be strictly true.

**website/content/docs/development/task-format.md**
14. Applied.
15. Applied; the rest of the sentence is kept.

**website/content/docs/commands/lock.md**
16. Applied. `unlock_task` pushes to origin (`aitask_lock.sh` line 386).

**website/content/docs/commands/attach.md**
17. Applied; the `#archive-storage` anchor exists in task-format.md.
18. Applied. The code confirms it: `_unfold_deleted_primary_children` sets each folded task back to Ready and clears `folded_into`. `_decref_doomed_attachments --protect-task` moves each reference a restored task still lists from the deleted task to that task.

**website/content/docs/commands/task-management.md**
19. Applied; the board link is kept.

**website/content/docs/skills/aitask-pick/execution-profiles.md**
20. Applied: item 4 is now "The `default` profile (fallback)". `aitask_skill_resolve_profile.sh` checks userconfig, then project_config, then returns `"default"`. All ten profile-aware stubs call this resolver (pick, fold, review, pr-import, revert, explore, pickrem, pickweb, qa, shadow). The interactive `execution-profile-selection.md` procedure is now referenced only from task-workflow's list of procedures, not from any skill stub.

**aidocs/framework/agent_session_store.md**
21. Applied. The old paragraph's last fact (`reconcile` checks the process id) is covered by the new sentence. 60 seconds is `STALE_OP_GRACE_DEFAULT`; it can only be overridden under `AITASKS_TEST_MODE=1`, so it holds in real use.
22. Applied verbatim. The code confirms it: in hook section 5b, a process on the chain that cannot be identified (`_codex_daemon_hop` returns 2) also means nothing is recorded.

## Fact-survival check (post-phase `moved_fact_survival_check`)

Run after the round-1 review fixes (deviation from the step order: before the
final re-review instead of after it, so one re-review covers the fixes of both;
every recorded Step 6 / Step 7 report is of the final text). Removed blocks per
page were computed by `removed_blocks.py` (HEAD vs working tree, paragraph /
list item / table row / heading / code-block granularity). Four independent
checker agents (none wrote the edits) classified every claim of every removed
block. Note: the first block files were truncated at 8192 bytes by a
`tee | head` pipe; only `concepts/gates.md` was affected, and its checker
rebuilt R45–R62 from git itself (reported below); the files were regenerated
without the pipe afterwards.

| Group | claims | preserved | weakened | missing | changed |
|---|---|---|---|---|---|
| locks (5 source pages) | 74 | 68 | 3 | 0 | 4 (code-verified corrections) |
| gates (2) | 87 | 85 | 1 | 0 | 1 (deliberate condition) |
| sessions + skill templating (6) | 145 | 134 | 1 | 0 | 10 (code-verified corrections: Gemini removed, macOS, labels, prune timing) |
| tasks, topics, attachments, small concepts (11) | 199 | 176 | 3 | 3 | 17 (corrections) |

**Reconciliation** (every weakened / missing claim):

- locks R29 anchor-not-the-taking-process → restored on development/merge-mutex.md as a positive clause.
- locks R49/R52 termination guarantee → restored on development/merge-mutex.md ("every run ends one of two ways").
- locks R54 "archival records" → restored on concepts/locks.md.
- locks R31 (changed, precise) left `workflows/parallel-development.md` saying "cleared deliberately, not automatically" → reworded there to match.
- gates R1 "only while `Implementing`" → restored on concepts/gates.md.
- gates R50 (changed: "while the stored enforced set is valid") → same condition added to development/gates.md § Unblocking dependents for consistency.
- skill-templating R39 `{% raw %}` rule → added to aidocs/framework/skill_authoring_conventions.md § minijinja caveats.
- tasks R4 Brainstorm → moved to commands/task-management.md § ait create.
- tasks R2 "branches and worktrees carry their own task state" → dropped(true only in legacy mode).
- task-lifecycle R2 "in a TUI" and R8 small-fixed-set rationale → restored on concepts/task-lifecycle.md.
- folded-tasks R2 commit messages → added to CLAUDE.md § Folded Task Semantics.
- attachments R31/R40 per-blob ledger rationale → contributor-only, stated in aidocs/attachment_metadata_bucketing.md §1 (kept off the site).
- All "changed" rows were checked against the checkers' code citations; they are the corrections listed in the restructure and review reports.

**Second run (step d)**, an independent checker on the 10 fixed claims: all 10 `preserved` (`ALL_PRESERVED`), including that development/gates.md's "never blocks while the stored enforced set is valid" and its over-blocking fallback do not contradict each other.

Upstream defects surfaced (not fixed here; see Final Implementation Notes): `aitask_create.sh` help says follow-ups are "Flattened — never chains" while `resolve_anchor()` chains for an anchorless-child source; `aidocs/framework/skill_authoring_conventions.md` and `agent_runtime_guards_audit.md` still describe four agents incl. Gemini and a verify script that renders "every profile"; the `ait archive` command named in the task-format `archived_reason` row does not exist.

### Checker report: locks group (verbatim)

Fact-survival check is done for all five source pages, and I edited nothing. Most claims survive: 68 of 74 are preserved. 3 are weakened and 4 are changed, all of them in `concepts/locks.md` except one in `development/_index.md`. I checked two of the changed claims against the code, and the new wording is the accurate one.

Where a claim survives, it is now mostly in `development/merge-mutex.md`, `commands/lock.md` ("When a Pick Meets a Held Lock") or `workflows/crash-recovery.md` ("When the Holder Is Still Running").

SOURCE: website/content/docs/concepts/locks.md
claims: 60  preserved: 54  weakened: 3  missing: 0  changed: 3
(R3, R5, R6, R16, R19, R21, R22, R28, R32, R39 and R41 are headings or table scaffolding and carry no claims.)
| R# | claim (short) | verdict | where / quote / what was lost |
|---|---|---|---|
| R1 | two locks; the task lock decides who owns a task ID | preserved | concepts/locks.md#what-it-is "aitasks takes a **task lock** on it, so no other agent can take the same task" |
| R1 | the merge mutex lets one task at a time merge, because the merge runs in the shared root, unlike the rest of the work | preserved | concepts/locks.md#what-it-is lines 18-20; #why-it-exists "The final merge runs in the main copy of the repository, which every agent shares" |
| R2 | atomic claim on one task ID, kept on the `aitask-locks` branch | preserved | commands/lock.md#ait-lock "Uses atomic git operations on a separate `aitask-locks` branch" |
| R2 | taken on pick; records email, host, timestamp and the session's process | preserved | concepts/locks.md#how-to-use; commands/lock.md#how-it-works (YAML example plus the pid paragraph) |
| R2 | released only on archival, abort or explicit unlock | preserved | commands/lock.md#how-it-works "A lock is released when its task is archived or aborted, or when you run `ait lock --unlock`" |
| R2 | stale locks can be force-unlocked, optionally with a confirmation prompt | preserved | commands/lock.md#when-a-pick-meets-a-held-lock "the interactive pick asks whether to force-unlock it… `/aitask-pickrem` asks nothing: it force-unlocks only when its profile sets `force_unlock_stale`" |
| R4 | the lock excludes sessions, not just people; several panes under one email exclude each other | preserved | commands/lock.md#when-a-pick-meets-a-held-lock "Each lock belongs to one agent session, so several agents in one checkout under the same email still exclude each other"; concepts/locks.md#why-it-exists |
| R7 | a different owner on any host: refused with `LOCK_FAILED`, naming the owner | preserved | commands/lock.md table row 1 |
| R8 | the same session: refreshed silently, which makes resume, re-pick and the ownership guard idempotent | preserved | crash-recovery.md#when-the-holder-is-still-running "a session recognises its own lock and refreshes it silently. Without that, the ownership guard, an in-pane re-pick, and every resume… would lock you out"; commands/lock.md row 2 adds that the anomaly prompt follows when the task is already Implementing and assigned to you (a clarification that agrees with crash-recovery#lock-anomaly-fallback) |
| R9 | another live session on this host: refused, nothing claimed, asked to leave it or force-claim | preserved | commands/lock.md row 3 |
| R10 | a session on this host whose liveness is unknown: refused; "cannot tell" is never rounded up | preserved | commands/lock.md row 4 "Refused the same way"; crash-recovery.md "**unknown** … **The claim is refused**" and "'We cannot tell' is never rounded up" |
| R11 | a provably gone session: claimed, with the crash-recovery prompt | preserved | commands/lock.md row 5 |
| R12 | another host: claimed, with the multi-PC reclaim prompt | preserved | commands/lock.md row 6 |
| R13 | a lock with no recorded process (pre-anchor, or made outside tmux): claimed with the anomaly prompt, because there is no holder to verify | preserved | commands/lock.md row 7 (adds "without `AIT_AGENT_PID`") |
| R14 | refusals happen before the lock, the status change and the commit, so the task is left as it was | preserved | crash-recovery.md#when-the-holder-is-still-running "Both refusals happen **before** the lock is written, before `status` becomes `Implementing`, and before anything is committed" |
| R14 | both refusals can be overridden: the force option at the prompt, or `ait lock --unlock` in the holding session | preserved | crash-recovery.md "The prompt offers… a force option second"; "release the lock from the session that holds it (`ait lock --unlock <task_id>`)" |
| R15 | a lock that never named a process stays reclaimable rather than stuck | preserved | crash-recovery.md "There is nothing to verify, so refusing would strand it forever. It stays reclaimable through the anomaly prompt." |
| R17 | the mutex serializes the end-of-task merge, which runs in the shared root, so every merging task drives one HEAD, index and working tree | preserved | merge-mutex.md#what-it-serializes |
| R18 | only the task workflow's merge takes it; `/aitask-web-merge` and hand-run git checkout or merge do not | preserved | merge-mutex.md#what-it-serializes "Only the task workflow's end-of-task merge takes the mutex…" |
| R20 | one global lock per repository, not one per branch, and why | preserved | merge-mutex.md "There is one lock per repository, so two tasks merging into different output branches still wait for each other" |
| R23 | no holder: claimed, and the merge proceeds | preserved | merge-mutex.md#what-the-next-task-does row 1 |
| R24 | live holder: queued and told which task it waits on (prompt and progress); wait budget expires, then refused, then keep waiting or stop | preserved | merge-mutex.md row 2 (the same text) |
| R25 | provably gone holder: reclaimed, and the merge proceeds | preserved | merge-mutex.md row 3 |
| R26 | holder whose liveness is unknown: left alone; clearing it is a deliberate human act | preserved | merge-mutex.md row 4 |
| R27 | same rule as the task lock, except manual recovery can also clear an unverifiable holder | preserved | merge-mutex.md line 30 |
| R29 | three separate commands, so the reservation is anchored to the session, not the process that took it (which would evaporate) | **weakened** | merge-mutex.md#the-reservation-lasts-the-whole-merge says it is anchored to the agent session "which lasts through all three". It no longer says it is not anchored to the taking process, or that such an anchor would vanish when the first command returns |
| R30 | held through conflict resolution, post-merge verification and cleanup | preserved | merge-mutex.md line 36 |
| R30 | so a conflict-parked merge is safe and a verification result is attributable | preserved | merge-mutex.md line 36; parallel-development.md#serialized-merge-back |
| R31 | nothing releases the lock automatically; each merge releases it at the end; a session that dies leaves it held | **changed** | see the list below |
| R33 | a merge needs an identifiable session, or it is refused before anything is acquired (`NO_SESSION_ANCHOR`) and no lock is left | preserved | merge-mutex.md#the-session-anchor |
| R34 | tmux pane is the standard route; the anchor lives and dies with the agent | preserved | merge-mutex.md line 44 |
| R35 | `AIT_AGENT_PID` must name a process that represents and outlives the whole session | preserved | merge-mutex.md line 45 |
| R36 | not enforced; the check is "positive integer naming an existing process"; a wrong but live PID is accepted silently | **changed** | see the list below |
| R37 | a PID that outlives the session strands the reservation | preserved | merge-mutex.md line 49 |
| R38 | a PID that dies early lets another task reclaim mid-merge | preserved | merge-mutex.md line 50 |
| R40 | if a session died mid-merge, no other task can merge until the reservation is cleared | preserved | merge-mutex.md#recovering-a-stuck-merge-mutex (same sentence) |
| R40 | `ait lock` does not manage it (task locks only); use the merge broker | preserved | merge-mutex.md line 54 |
| R42/43 | `status` reports the holder task, anchor process, liveness, output branch and time taken | preserved | merge-mutex.md step 1 |
| R44 | clear a leaked guard with `rmdir`, never `rm -rf`; the guard's emptiness proves no reclaim is in progress | **changed** | see the list below |
| R45-47 | `force-release` with no flags is a dry run that changes nothing; it prints holder, liveness, residue, remedy and a pinned armed command | preserved | merge-mutex.md step 3 |
| R48 | run the armed command verbatim; a token pins the holder; refused if the holder changed | preserved | merge-mutex.md step 4 |
| R49/R52 | the ladder terminates rather than loops: either the mutex is released or you are told why | **weakened** | merge-mutex.md: "Three rules make `force-release` safe to run". The individual rules survive, but the termination guarantee ("either released or the tool tells you precisely why") is no longer stated |
| R50 | a live holder is never broken (`REFUSED_LIVE_HOLDER`, names the process); let it finish or stop it | preserved | merge-mutex.md "The only remedy is to let that session finish or to stop it" |
| R51 | two residue states, two remedies, a mismatched flag is refused, `--reset-hard` discards and prints first, take the flag from the dry run | preserved | merge-mutex.md line 79 |
| R52 | if the tree cannot be made verified-clean, the lock is kept and the reason named | preserved | merge-mutex.md line 80 |
| R53 | do not run `/aitask-web-merge` while a task is at its merge step | preserved | merge-mutex.md line 82 |
| R54 | designed for multiple PCs, developers and parallel sessions | preserved | parallel-development.md line 9 "multiple developers (or multiple AI agent instances)"; concepts/locks.md line 11 |
| R54 | without locks: conflicting branches, commits or archival records | **weakened** | concepts/locks.md#why-it-exists says "conflicting branches and commits". "Archival records" is gone |
| R54 | sessions share one email, so matching on owner alone would not catch it | preserved | concepts/locks.md#why-it-exists "so several agents in one checkout under the same email still exclude each other" |
| R54 | locks kept in git, not a backend; push and fetch distribute them; force-unlock is just a commit | preserved | concepts/locks.md "with no server to run"; commands/lock.md#how-it-works "Releasing a lock, including a forced unlock, is likewise one commit on that branch, so no server is involved" |
| R55 | the merge is the one mutating step in the shared root, where worktree isolation stops | preserved | concepts/locks.md#why-it-exists lines 35-40 |
| R55 | concurrent merges race on one index; half-resolved conflict work is absorbed into the next merge commit | preserved | concepts/locks.md "Two merges at once would mix their changes"; parallel-development.md "the next task's merge would absorb the half-resolved conflict work into its own merge commit" |
| R55 | serializing carries isolation across the last step | preserved | concepts/locks.md "The merge mutex keeps that last step to one task at a time" |
| R56 | locks are normally invisible; pick and board acquire and release them | preserved | concepts/locks.md#what-it-is and #how-to-use |
| R56 | `ait lock` lists, checks, force-releases and cleans up | preserved | commands/lock.md command table (`--list`, `--check`, `--unlock`, `--cleanup`) |
| R57 | the mutex is invisible; taken before the merge and released after cleanup; not covered by `ait lock`; clear with `status` and `force-release` | preserved | concepts/locks.md#how-to-use; merge-mutex.md lines 36, 54-74 |
| R58 | tasks are the unit a lock applies to | preserved | concepts/locks.md See also |
| R59 | locks live on the `aitask-locks` branch | preserved | concepts/locks.md See also; git-branching-model.md table |
| R60 | `ait lock` is the CLI for inspecting and managing locks | preserved | concepts/locks.md See also |
| R61 | `ait note` live delivery reads the lock record to find the session | preserved | commands/lock.md#how-it-works "it is also what `ait note --with-live` reads to find the live agent session implementing a task" |

SOURCE: website/content/docs/commands/lock.md
claims: 8  preserved: 8  weakened: 0  missing: 0  changed: 0
| R# | claim (short) | verdict | where / quote / what was lost |
|---|---|---|---|
| R1 | email auto-detected from `userconfig.yaml`, falling back to `emails.txt` | preserved | commands/lock.md command table line 23 (only the link target changed) |
| R1 | exit codes 0, 1, 13 and 14 with their meanings | preserved | the same line, identical |
| R2 | `t<N>_lock.yaml` files on an orphan `aitask-locks` branch that exists only on the remote | preserved | commands/lock.md#how-it-works line 72, identical |
| R2 | atomicity through push rejection; the loser retries up to 5 times | preserved | the same line (a sentence was added after it) |
| R3 | records `pid` plus a start-time token that guards against PID recycling | preserved | line 86, identical |
| R3 | older or session-less locks have no `pid` fields | preserved | line 86 |
| R3 | that record lets a later pick tell a live holder from a crashed one | preserved | line 86 (link retargeted) |
| R3 | `ait note --with-live` reads it | preserved | line 86 |

SOURCE: website/content/docs/workflows/crash-recovery.md
claims: 2  preserved: 2  weakened: 0  missing: 0  changed: 0
| R# | claim (short) | verdict | where / quote / what was lost |
|---|---|---|---|
| R1 | the `aitask-locks` branch and the lock metadata the recovery reads | preserved | crash-recovery.md See also: "`ait lock` — the lock record the recovery reads"; commands/lock.md#how-it-works |
| R2 | `ait lock` gives manual inspection and force-release | preserved | crash-recovery.md See also line 188 "manual inspection and force-release" |

SOURCE: website/content/docs/workflows/parallel-development.md
claims: 2  preserved: 2  weakened: 0  missing: 0  changed: 0
| R# | claim (short) | verdict | where / quote / what was lost |
|---|---|---|---|
| R1 | a session that dies mid-merge leaves the reservation held, and it is cleared deliberately, not automatically | preserved | parallel-development.md line 35, same text, link retargeted to merge-mutex. This now conflicts with merge-mutex.md (see R31 below) |
| R2 | where to read what the mutex covers | preserved | line 39, now pointing to merge-mutex |

SOURCE: website/content/docs/development/_index.md
claims: 2  preserved: 1  weakened: 0  missing: 0  changed: 1
| R# | claim (short) | verdict | where / quote / what was lost |
|---|---|---|---|
| R1 | the same email can refresh its own lock | **changed** | see the list below |
| R1 | unlocking a lock that does not exist succeeds silently | preserved | development/_index.md#atomic-task-locking, same text; also commands/lock.md "Idempotent (succeeds even if not locked)" |

---

**Weakened, changed and missing claims only (with the exact source wording)**

1. **concepts/locks.md R29, weakened.** Source: "Taking the mutex, merging, and releasing it are three separate short-lived commands. The reservation is therefore anchored to the **agent session** rather than to the process that took it — anchored to the process, it would evaporate the moment the first command returned."
   - Current (merge-mutex.md#the-reservation-lasts-the-whole-merge): "…so the reservation is anchored to the **agent session** (the running agent that owns the task), which lasts through all three."
   - Lost: that the reservation is *not* anchored to the process that took it, and that such an anchor would vanish when the first command returned.

2. **concepts/locks.md R31, changed.** Source: "The consequence is that **nothing releases this lock automatically**. Every merge that takes it ends by releasing it, and a session that dies mid-merge leaves it held. That is what the recovery ladder below is for."
   - Current (merge-mutex.md line 38): "Only the holder releases the mutex: every merge that takes it ends by releasing it, and no timeout or background job releases it on the holder's behalf. A session that dies mid-merge therefore leaves it held until the next task finds it provably gone or you clear it."
   - This is a narrower, more accurate claim and matches the source's own R25 row ("provably gone → Reclaimed").
   - Inconsistency to fix: parallel-development.md line 35 still says "It is cleared deliberately, not automatically", which now contradicts merge-mutex.md.

3. **concepts/locks.md R36, changed (the new wording matches the code).** Source: "the framework checks only that `AIT_AGENT_PID` is a positive integer naming a process that exists right now. A wrong-but-live PID is accepted silently…"
   - Current (merge-mutex.md line 47): "It checks only that `AIT_AGENT_PID` is an integer greater than 1 naming a process that is alive right now. A value that fails that check is ignored with a warning, and the anchor falls back to the tmux pane."
   - `.aitask-scripts/lib/pid_anchor.sh:460-466` checks `(( AIT_AGENT_PID > 1 ))`, then warns and ignores the value. The new wording is correct.

4. **concepts/locks.md R44, changed (the rationale was dropped).** Source: "**Clear a leaked guard, if `status` reports one.** Remove it with `rmdir`, never `rm -rf`: the guard is a directory whose *emptiness* is the proof that no reclaim is in progress."
   - Current (merge-mutex.md step 2): "`status` prints the `rmdir` command that removes it. Run that command only when no reclaim is in progress, and never use `rm -rf`."
   - Lost: why `rmdir` is safe (the guard is a directory, and its emptiness proves no reclaim is running). The responsibility moves to the user as a precondition instead.
   - The code (`.aitask-scripts/aitask_merge_task.sh:387,517`) prints `rmdir '<dir>.gc'/h.* '<dir>.gc'` with "if no reclaim is running" / "(never rm -rf)". That matches the current wording better than the source's "emptiness" framing.

5. **concepts/locks.md R49 and the last sentence of R52, weakened.** Source: "Three properties make this ladder terminate rather than loop:" … "Either the mutex is released, or the tool tells you precisely why it will not act on it."
   - Current (merge-mutex.md): "Three rules make `force-release` safe to run:" … "the lock is kept and the reason is named."
   - Lost: the termination guarantee, i.e. that the procedure always ends in release or in a stated reason.

6. **concepts/locks.md R54, weakened.** Source: "Without locks, two sessions could pick the same task at the same time and produce conflicting branches, commits, or archival records".
   - Current (concepts/locks.md#why-it-exists): "two agents could start the same task at once and produce conflicting branches and commits."
   - Lost: "archival records".

7. **development/_index.md R1, changed (this is a correction).** Source: "Locks are idempotent: the same email can refresh its own lock, and unlocking a non-existent lock succeeds silently"
   - Current (development/_index.md#atomic-task-locking): "Locks are idempotent: the agent session that holds a lock can refresh it, and unlocking a non-existent lock succeeds silently. Each lock belongs to one agent session, so a lock held by another running (or unverifiable) session on the same host is refused even under the same email…"
   - The new wording matches the session-exclusion table that was in the HEAD version of locks.md.

### Checker report: gates group (verbatim)

Fact-survival check: concepts/gates.md and commands/gates.md. Read-only; nothing was edited, staged or committed.

**Problem with the input file.** `/tmp/claude-1000/-home-ddt-Work-aitasks/57ffb334-9dbe-4f0f-81e5-ee1f5a3ac601/scratchpad/survival/website_content_docs_concepts_gates.md.md` is cut off at exactly 8192 bytes. Its header says 62 blocks, but it holds only R1–R44 and ends in the middle of a heading (`##`). I rebuilt R45–R62 by comparing `git show HEAD:website/content/docs/concepts/gates.md` against the working tree, paragraph by paragraph and byte for byte. Exactly 62 blocks came out, which matches the header count:
- R45 sync-registry paragraph
- R46 "### Retry budgets and the unlock order"
- R47 retry paragraph
- R48 unlock-order paragraph
- R49 "### Archival and unblocking"
- R50 archival paragraph
- R51 unblocking paragraph
- R52 and R53 the two "Why it exists" paragraphs
- R54 and R55 the two "How to use" paragraphs
- R56–R62 the seven See-also bullets (each one was rewritten)

The other survival files may be cut off the same way. Check that each file's `^### R` count matches its header.

Short names used below:
- **dev** = `website/content/docs/development/gates.md`
- **concepts** = `website/content/docs/concepts/gates.md` (working tree)
- **cmd** = `website/content/docs/commands/gates.md`
- **aidocs** = `/home/ddt/Work/aitasks/aidocs/gates/gate-guarded-archival.md`

Headings, table header and separator rows, and pure rhetoric are not counted as claims: R5, R9, R13, R17, R22, R29, R33, R35, R36, R46 and R49.

```
SOURCE: website/content/docs/concepts/gates.md
claims: 83  preserved: 81  weakened: 1  missing: 0  changed: 1
```

| R# | claim (short) | verdict | where / quote / what was lost |
|---|---|---|---|
| R1 | A gate is a named check a task must satisfy before it can archive | preserved | concepts#what-it-is: "a named check a task must satisfy before it can be archived" |
| R1 | Examples: build, tests, risk evaluation, a person's review sign-off | preserved | concepts#what-it-is, same four examples |
| R1 | Gates sit beside `status`, not inside it; status stays the coarse lifecycle | preserved | concepts#what-it-is: "recorded apart from its `status` field"; aidocs#criterion-d5--d6: "no new coarse `status` value" |
| R1 | Gates come into play **only** while the task is `Implementing` | weakened | concepts#what-it-is: "they are checked while the task is implemented and when it archives". Lost: the word "only" (no gate role in other statuses) and the tie to the `Implementing` status value |
| R2 | Each task carries two sets of gates | preserved | dev#declared-gates-and-the-enforced-set: "Each task carries two sets of gates:" |
| R3 | `gates:` = what the task asks for; declared intent; written by you or injected from a profile at creation | preserved | dev#declared-gates…: "declared intent, written by you or injected from an execution profile when the task is created" |
| R4 | `active_gates` = enforced; derived; written by the framework; never hand-edited | preserved | dev#declared-gates…: "It is derived: the framework writes it, and nobody edits it by hand." |
| R6 | The profile's ceiling limits the machinery; only the intersection is enforced | preserved | dev#declared-gates…: "resolved against the ceiling, and only the intersection is enforced" |
| R7 | No `gates:` key at all → the profile's `default_gates` | preserved | dev diagram: "no gates: key at all → the profile's default_gates" |
| R7 | `rendered_gates` is the ceiling and defaults to `default_gates` | preserved | dev: "set by its `rendered_gates` key, which defaults to the profile's `default_gates`" |
| R7 | `active_gates_profile` records which profile decided | preserved | dev diagram: "which profile decided"; task-format row "Provenance stamp" |
| R7 | Digest form is `<gates>.<profile>.<outputs>` | preserved | aidocs#criterion: "in the order `<gates>.<profile>.<outputs>`"; task-format `<g>.<p>.<o>`. The dev diagram now shows only `<digest of the three inputs>` |
| R7 | Worked example: [risk_evaluated, docs_updated] → active [risk_evaluated], filtered [docs_updated], profile fast | preserved | dev diagram, identical |
| R8 | The four `active_gates*` fields form one tuple and are always written together | preserved | dev: verbatim |
| R8 | A filtered gate was asked for, deliberately not enforced, blocks nothing, and is not forgotten | preserved | dev: "It blocks nothing, and it stays on record." |
| R10 | An empty enforced set is written as `[]`, not omitted, because a missing tuple means something else | preserved | dev: "rather than leaving the field out, because a missing tuple means the task is enforced from its raw `gates:` field" |
| R11 | `gates: []` is an opt-out, never backfilled; only a missing key takes the defaults | preserved | dev: verbatim |
| R12 | A manual-verification task keeps only reachable gates; the rest are dropped from both lists | preserved | dev: "The rest are dropped from both lists, because they could never be satisfied." |
| R14 | Computed at claim/pick and stored, not per read; a re-pick (in-flight included) derives it afresh under that pick's profile | preserved | dev#when-the-enforced-set-is-computed, same conditions |
| R15 | The profile is a per-session choice; the set is fixed for the session; a change applies at the next pick | preserved | dev#when…: "a change of profile takes effect at the next pick instead of half-way through one" |
| R16 | If the profile is missing or unreadable, the stored tuple is cleared; an old profile never governs a new session | preserved | dev#when…: "any previously stored tuple is cleared, and the raw `gates:` field governs until a pick computes the set again" |
| R18 | Digest = three 12-character hashes joined by dots, one per input | preserved | aidocs#criterion: "three 12-character hashes (the first 12 hex characters of a sha256 …) joined by dots". dev keeps only "one part for each input"; aidocs says the width is deliberately contributor-only |
| R19 | The three inputs: raw `gates:` including whether the key exists; the profile's default/rendered gates; stored active/filtered | preserved | dev#the-digest: verbatim list |
| R20 | Readers check parts 1 and 3 first, from the task file alone | preserved | dev#the-digest: verbatim |
| R20 | These catch a `gates:` edit after the pick, or a hand edit of `active_gates` | preserved | dev#the-digest: verbatim |
| R20 | The tuple is then treated as absent and enforcement falls back to raw `gates:` until the next pick | preserved | dev#the-digest: "the tuple, its list of filtered gates included, is treated as absent, and enforcement falls back to the raw `gates:` field until the next pick" |
| R21 | The fallback can over-block a filtered gate until the next pick, but never enforces less than asked | preserved | dev#the-digest: "over-blocks until the next pick, but a hand-edited enforced set can never quietly enforce less" |
| R21 | Part 2 needs a profile, so a profile change is caught at the next pick | preserved | dev#the-digest: verbatim |
| R23 | The registry classifies gates by what can satisfy them | preserved | dev#kinds-of-gate |
| R24 | Machine gates: build, tests, linter, risk check; a verifier runs; its exit status is the verdict | preserved | dev#kinds-of-gate |
| R25 | Human gates wait for a person; an agent never supplies the approval; the three shipped human gates differ | preserved | dev#kinds-of-gate: verbatim |
| R26 | `plan_approved` is attended-only, recorded from interactive plan approval; `ait gate pass` refuses it | preserved | dev#kinds-of-gate: "recorded only in an attended session … `ait gate pass` refuses it" |
| R27 | review/merge_approved are recorded in an attended session or signed asynchronously with `ait gate pass`; the signature is code-bound; a code change means re-sign | preserved | dev#kinds-of-gate: "can also be signed later with `ait gate pass` … if the code changes after signing, the gate counts as outstanding again" |
| R28 | Procedure-backed (`kind: procedure`): `docs_updated`'s verifier is a skill; the headless engine defers it and an attended agent runs it | preserved | dev#kinds-of-gate: same, plus a definition of the headless engine |
| R30 | Append-only `## Gate Runs` in the task file; one block per run (gate, time, status, attempt once finished); re-runs append; never rewritten | preserved | dev#the-ledger: verbatim |
| R31 | State is derived from the ledger, latest block wins, never copied to another field | preserved | dev#the-ledger |
| R31 | `pass` and `skip` both satisfy; skip = "evaluated, not applicable", distinct in history, never blocks | preserved | dev#the-ledger: "It stays distinct from `pass` in the history and never blocks." |
| R32 | Under a recording profile, the ledger also records workflow checkpoints whether declared or not | preserved | dev#the-ledger: "Under a profile with `record_gates: true` …" (now more precise) |
| R32 | Resume reads checkpoints; archival reads enforced gates; the two questions stay separate | preserved | dev#the-ledger: "Resuming … reads those checkpoints …; archival reads the enforced gates". The sentence "kept separate" was dropped, but the separation is still stated |
| R34 | The registry says how a gate runs; the task says which gates apply | preserved | dev#the-registry |
| R37 | `type`: machine or human | preserved | dev#the-registry table |
| R38 | `kind`: procedure = verifier is a skill | preserved | dev table |
| R39 | `verifier`: empty for a recorded-only gate | preserved | dev table |
| R40 | `max_retries` | preserved | dev table |
| R41 | `unlocks` | preserved | dev table |
| R42 | `timeout_seconds`: wall-clock limit per machine run | preserved | dev table |
| R43 | `signal`, `signal_target`: how a human signature is detected | preserved | dev table |
| R44 | `blocks_dependents` | preserved | dev table |
| R45 | `sync-registry` fills missing keys and reports, never overwrites, differing values | preserved | cmd#what-it-changes--and-what-it-refuses-to-change: "only fills in keys that are absent. A key that is present with a different value is reported and left alone". dev keeps only "reconciles" |
| R47 | Re-run up to `max_retries` more times | preserved | dev#retry-budgets |
| R47 | Only fail/error spend the budget; re-running a passed gate costs nothing | preserved | dev#retry-budgets: verbatim |
| R47 | When the budget is spent: exhausted, waits for a person | preserved | dev#retry-budgets: verbatim |
| R47 | Human gates do not retry | preserved | dev#retry-budgets |
| R48 | Default order is linear: each enforced gate unlocks the next in the task's list | preserved | dev#the-unlock-order |
| R48 | Any enforced `unlocks:` → the registry drives; a gate without `unlocks:` unlocks nothing; gates can fan out | preserved | dev#the-unlock-order |
| R48 | Ready = all unlockers satisfied, not yet satisfied itself, budget left | preserved | dev#the-unlock-order: verbatim |
| R48 | Ready machine gates run in parallel up to `max_parallel_gates` | preserved | dev#the-unlock-order |
| R50 | Archives only when every enforced gate is satisfied | preserved | dev#archival |
| R50 | A stale approval signature counts as unsatisfied | preserved | dev#archival |
| R50 | A filtered gate can **never** block archival | changed | dev#archival: "a gate the profile filtered out never blocks archival while the stored enforced set is valid (see The digest)" — a condition was added |
| R50 | The archive command refuses an unmet gate unless overridden; this holds for every caller | preserved | dev#archival: "so the rule holds for every caller, the pick workflow included", plus `--ignore-gates` |
| R51 | `blocks_dependents` gates (build, tests, review/merge approval) decide usability; the rest can finish later | preserved | dev#unblocking-dependents |
| R51 | A dependent unblocks once the upstream's enforced `blocks_dependents` gates are satisfied, even while others pend and the task is active | preserved | dev#unblocking-dependents: verbatim |
| R51 | `also_blocks_dependents` adds gates per task; a filtered addition is dropped; a filtered gate holds back neither | preserved | dev#unblocking-dependents: verbatim |
| R51 | With none of these enforced, dependents release at archive | preserved | dev#unblocking-dependents |
| R52 | A single status cannot express independent facts that finish at different times | preserved | concepts#why-it-exists: verbatim |
| R52 | Gates in the task file survive a crash and are visible on every syncing machine | preserved | concepts#why-it-exists: verbatim |
| R53 | One task can move between workflows; each profile decides what it can check | preserved | concepts#why-it-exists: "The same task can be picked under different profiles, and each enforces only the gates its workflow can check." |
| R53 | The intent/enforced gap is recorded, not silently lost | preserved | dev#declared-gates…: "It blocks nothing, and it stays on record." |
| R53 | Fixing the set at claim keeps it stable for the session | preserved | concepts#why-it-exists: "fixed when you pick the task … and stay the same until it is picked again" |
| R53 | The digest stops a stored decision from outliving its inputs | preserved | dev#the-digest: "stops a stored enforced set from outliving the inputs it was computed from" |
| R54 | Declare gates with the batch `--gates` flag (aitask-create) or a profile's `default_gates` | preserved | concepts#how-to-use; skills/aitask-create.md `--gates GATES` bullet |
| R54 | The enforced set is written at pick; gates recorded as reached; archival waits | preserved | concepts#how-to-use: "the enforced gates are worked out when you pick the task, each gate's result is recorded … archival waits" |
| R55 | `ait gates`/`ait gate`: run, list state, sign a human gate, read a log | preserved | concepts#how-to-use |
| R55 | `/aitask-run-gates` runs the ready machine gates | preserved | concepts#how-to-use |
| R55 | The board shows in-flight gates against the enforced set | preserved | concepts#how-to-use; board reference#gate-progress |
| R56 | Command reference covers run, list, sign off, reconcile | preserved | concepts#see-also |
| R57 | `/aitask-run-gates` is the conversational front of the gate engine | preserved | concepts#see-also; skills/aitask-run-gates.md |
| R58 | Procedure-backed gate; only an attended agent can run it | preserved | concepts#see-also |
| R59 | Task format has the gates, also_blocks_dependents and active_gates* rows | preserved | concepts#see-also; rows confirmed at task-format.md lines 72–77 |
| R60 | The board counts satisfied gates against the enforced set | preserved | concepts#see-also; board reference#gate-progress: "The denominator is the enforced active set" |
| R61 | The `risk_evaluated` gate verifies the risk-evaluation planning step | preserved | concepts#see-also: verbatim |
| R62 | Each profile sets its workflow's gate ceiling | preserved | concepts#see-also: "each one also limits which gates its workflow enforces" |

```
SOURCE: website/content/docs/commands/gates.md
claims: 4  preserved: 4  weakened: 0  missing: 0  changed: 0
```

| R# | claim (short) | verdict | where / quote / what was lost |
|---|---|---|---|
| R1 | `ait gates`/`ait gate` operate on a task's verification gates, the named checks it must satisfy before it can archive | preserved | cmd intro: verbatim |
| R1 | The task-format page documents the `gates`/`active_gates` fields | preserved | cmd intro: verbatim (the concept-model topics now link to Gate rules) |
| R2 | `--gate <name>` runs only this gate | preserved | cmd#ait-gates-run: "Run only this gate, even if it already passed and even if its retry budget is spent." Something was added; nothing was lost |
| R2 | `--gate` reports instead of running if the gate is not in the active set or its predecessors are unsatisfied | preserved | cmd#ait-gates-run: verbatim |

**Only the weakened and changed claims, ready to fix:**

1. **WEAKENED — concepts/gates.md R1.** Source wording: "Gates sit beside the task's `status` rather than inside it — `status` stays the coarse lifecycle, and gates only come into play while the task is `Implementing`." The current text in concepts#what-it-is is "they are checked while the task is implemented and when it archives". It drops "only" (gates have no role in other statuses) and the tie to the `Implementing` status value. Nothing else under `website/content/docs/` or `aidocs/` restates it.

2. **CHANGED — concepts/gates.md R50.** Source wording: "A gate the profile filtered out can never block archival." The current text in dev#archival is "a gate the profile filtered out never blocks archival while the stored enforced set is valid (see [The digest](#the-digest))". This looks like a deliberate correction: it agrees with R21's own fallback rule, which says a stale or absent tuple falls back to raw `gates:` and can over-block. The same page is now inconsistent with itself, though. dev#unblocking-dependents still says, without the condition, "so a filtered gate holds back neither archival nor dependents". aidocs#criterion also says "a declared gate that the profile filtered out **never blocks archival**", though its next clause ("the fallback can only over-block") hedges it.

Nothing is missing on either page.

### Checker report: sessions + skills group (verbatim)

Fact-survival check: concepts/framework-session, concepts/skill-templating, commands/setup-install, workflows/freeze-and-restore-agents, tuis/frozenagent/reference, commands/_index

I read every destination page in full. I left the repository untouched: no edits, staging, commits or restores.

Headings, table header rows, and see-also or "see X" navigation blocks are not counted as claims. These are R4/8/12/15/23/25/26/31/33/34/40-42 of framework-session, R7/8/12/16/20/23/24/25/31/35/43/47/48 of skill-templating, and R3 of freeze-and-restore. Abbreviations below: DEV-FS = development/framework-session.md, DEV-ST = development/skill-templating.md, ASS = aidocs/framework/agent_session_store.md, SAC = aidocs/framework/skill_authoring_conventions.md, SSP = aidocs/framework/stub-skill-pattern.md, EP = skills/aitask-pick/execution-profiles.md.

```
SOURCE: website/content/docs/concepts/framework-session.md
claims: 68  preserved: 68  weakened: 0  missing: 0  changed: 0
```
| R# | claim (short) | verdict | where / quote |
|---|---|---|---|
| R1 | record holds project, window, task, agent+model, CLI session id | preserved | concepts/framework-session#What it is "which project and tmux window ... the id its CLI can resume the conversation from" |
| R1 | record tracks freeze/restore lifecycle position | preserved | DEV-FS#States "A record moves through five states" |
| R1 | one record per agent, every agent on the machine, every project | preserved | concept#What it is "one record per agent, for every agent on the machine, in every project" |
| R2 | `~/.config/aitasks/agent_sessions.json`, mode 0600 | preserved | DEV-FS#Where the state lives |
| R2 | `aitask_agent_sessions.sh` is the only writer | preserved | DEV-FS#Who writes it |
| R2 | lock held around each read-modify-write | preserved | ASS#How the single-writer guarantee is implemented "holds a lock (`registry_lock.sh`) around each read-modify-write" |
| R2 | file replaced atomically | preserved | DEV-FS "Every write replaces the file whole"; ASS "os.replace" |
| R2 | readers (viewer, monitor, minimonitor) take no lock and see one complete generation | preserved | DEV-FS#Who writes it |
| R3 | captures in `frozen/<id>/`, mode 0700 | preserved | DEV-FS#Where the state lives |
| R3 | `capture.ansi` raw with colour; `capture.txt` plain | preserved | DEV-FS table |
| R5 | identity = project root + window name + slot | preserved | DEV-FS#Identity and location |
| R5 | slot tells apart a second agent split into the same window | preserved | DEV-FS "tells apart a second agent split into the same window" |
| R6 | pane id / pid are location; restart, reattach or respawn replaces them on the same record | preserved | DEV-FS "when they change they are replaced on the same record" |
| R6 | restarted tmux makes no second record for a known agent | preserved (refined) | DEV-FS "a restarted tmux does not produce a second record". New text adds that take-over happens only before cleanup retires the record. |
| R7 | `@aitask_record` joins a pane to its record | preserved | DEV-FS#Identity and location |
| R7 | it is stamped after the record is written | preserved | ASS#Pane options "stamped on the pane only after the record has been written" |
| R7 | pane options die with the pane, so no stale id | preserved | DEV-FS |
| R7 | two more options (frozen pane, booted stand-in) distinguish states without trusting a process name | preserved | ASS#Pane options |
| R9 | five states; guarded transitions; an illegal one is refused and writes nothing | preserved | DEV-FS#States |
| R10 | state diagram | preserved | DEV-FS#States (identical) |
| R11 | freezing/restoring/aborting are transitional | preserved | DEV-FS#States |
| R11 | aborting is owned by the failed restore and blocks a second restore before the viewer is back | preserved | DEV-FS#States |
| R13 | multi-step coordinator must outlive the pane it respawns | preserved | DEV-FS#Operation leases |
| R13 | lease = one-time nonce + coordinator pid | preserved | ASS#What an operation lease holds |
| R13 | every changing verb must present the matching nonce | preserved | ASS "Every command that changes a leased record must present the matching nonce" |
| R13 | a coordinator that lost the race writes nothing | preserved | DEV-FS#Operation leases |
| R14 | reconcile settles transitional records from what tmux can be seen to hold | preserved | DEV-FS#Operation leases |
| R14 | reconcile leaves a record alone while the owner is alive or the lease is under 60 s; only an owner-gone lease is taken over | preserved | DEV-FS#Operation leases (verbatim) |
| R16 | `ait setup` installs a SessionStart hook that runs at agent start | preserved | setup-install#Session Hooks |
| R16 | hook records the session id, which makes restore possible | preserved | DEV-FS#The session hook |
| R16 | hook writes nothing into the session and always exits successfully | preserved | setup-install#Session Hooks |
| R17 | own-pane test: pane process is an ancestor, no Codex app-server daemon between | preserved | ASS#How the session hook decides; DEV-FS#When it records gives the rule |
| R17 | hand-started Codex via the daemon reports the starter pane; ignored; re-pick | preserved | DEV-FS#When it records |
| R18 | hook records the owning CLI; a framework-launched agent names itself | preserved | DEV-FS#Which CLI owns the session |
| R18 | CLI read from transcript path shape (`projects/` vs `rollout-…`) | preserved | ASS#How the session hook reads the CLI |
| R18 | path counts only if it names the very session being reported | preserved | DEV-FS; ASS |
| R18 | restore resumes only with the same CLI | preserved | DEV-FS |
| R18 | hand-started: uses the recorded agent/model when freezing recovered them (known model) | preserved | DEV-FS |
| R18 | otherwise the project default for raw sessions, resumed only if it is the same CLI | preserved | DEV-FS "default agent for the `raw` operation" |
| R18 | unknown or different CLI: refused, stays frozen, re-pick available | preserved | DEV-FS |
| R18 | nested agent inherits identity; on disagreement records nothing | preserved | DEV-FS |
| R19 | ack via record id + nonce in env; hook hands them back; store checks the session | preserved | DEV-FS#Restore verification |
| R19 | only a verified restore deletes the capture | preserved | DEV-FS#Restore verification |
| R20 | Codex TUI fires the hook only at first turn | preserved | DEV-FS#Restore verification |
| R20 | measured on Codex 0.163.0; 0.153.4 only under `codex exec` | preserved | ASS#Codex hook timing |
| R20 | coordinator doesn't wait for the hook; reads the held-open transcript | preserved | DEV-FS |
| R20 | `/proc` on Linux, `lsof` on macOS | preserved | ASS#How the open transcript is read |
| R20 | match → verified and capture deleted; mismatch → abort | preserved | DEV-FS |
| R21 | no verification within `restore_ack_grace` → liveness, unverified, capture kept | preserved | DEV-FS |
| R21 | applies to CLIs reporting no session and to unreadable Codex (daemon example) | preserved | DEV-FS |
| R22 | late hook never refused; Codex reports at first turn | preserved | DEV-FS |
| R22 | upgrade to verified when liveness-confirmed, from the launched process, with the asked-for session | preserved | DEV-FS |
| R22 | any other late report updates the record | preserved | DEV-FS |
| R24 | retire only on positive evidence; a partial view suppresses every removal | preserved | DEV-FS#Cleanup rules |
| R24 | transitional records exempt; reconcile owns them | preserved | DEV-FS#Cleanup rules |
| R27 | `dead_window` | preserved | DEV-FS table |
| R28 | `dead_pane` (pane gone or dead AND process provably gone) | preserved | DEV-FS table |
| R29 | `capture_missing` | preserved | DEV-FS table |
| R30 | runs on the monitor/minimonitor tick and the coordinator after every operation; no TUI needed | preserved | DEV-FS "cleans up even when no monitor is open" |
| R32 | two env vars relocate state, for unusual home layouts | preserved | DEV-FS#Overrides |
| R32 | the test suite uses them | preserved | ASS#Overrides and the test suite |
| R35/36 | variable → path mapping | preserved | DEV-FS#Overrides |
| R37 | panes aren't durable (tmux restart, recycled, renamed, split) | preserved | concept#Why it exists |
| R37 | pane-tied identity loses agents after a crash or reboot | preserved | concept "An agent known only by its pane is lost with the pane"; "even after a reboot" |
| R38 | record kept outside tmux, machine-wide | preserved | concept "kept apart from the agent's terminal pane"; "every project" |
| R38 | enables ending the process and bringing it back | preserved | concept#Why it exists |
| R39 | you rarely address the store directly | preserved | concept#How to use "You never edit the record; aitasks writes it" |
| R39 | underlies freeze/restore, frozenagent, monitor frozen rows | preserved | DEV-FS#Who writes it (readers); concept#How to use |

```
SOURCE: website/content/docs/concepts/skill-templating.md
claims: 51  preserved: 43  weakened: 1  missing: 0  changed: 7
```
| R# | claim (short) | verdict | where / quote / what was lost |
|---|---|---|---|
| R2 | template at `.claude/skills/<skill>/SKILL.md.j2` | preserved | DEV-ST#The two pieces |
| R3 | profile-agnostic stub at each agent's discovery surface | preserved | DEV-ST#The two pieces |
| R4 | stub resolves profile, renders per-(skill, profile, agent) variant on demand, reads and follows it | preserved | DEV-ST intro + #How dispatch works |
| R5 | SKILL.md re-read throughout execution | preserved | concept#Why it exists "re-reads a skill's file while it runs, not only when the skill starts" |
| R5 | mid-session mutation → torn reads, so no in-place per-profile rewrite | preserved | concept "would mix two versions of its instructions" |
| R5 | stable snapshot per invocation | preserved | concept "a variant that stays fixed for the whole run"; SAC "materialises a stable ... snapshot once per invocation" |
| R6 | minijinja; one `.j2` → default/fast/remote flows | preserved | DEV-ST#The two pieces |
| R6 | avoids "if your profile sets X" prose | preserved | concept#Why it exists |
| R9 | `/aitask-pick --profile fast 42` | preserved | concept#How to use |
| R10 | stub strips `--profile`, forwards remaining args (`ARGUMENTS` Claude/Codex, `$ARGUMENTS` OpenCode) | preserved | DEV-ST#How dispatch works |
| R10 | `{{args}}` in Gemini | changed | Gemini dropped everywhere. DEV-ST lists only "`ARGUMENTS` in Claude Code and Codex, `$ARGUMENTS` in OpenCode". Consistent with code: no `.gemini/` dir, verify `agents=(claude codex opencode)`. |
| R11 | fallback: `--profile` → userconfig → project_config → interactive | preserved | EP#Resolution Order |
| R13 | `ait skillrun pick --profile fast 42` | preserved | commands/skillrun |
| R14 | launches agent with slash command preloaded | preserved | skillrun |
| R14 | default from `$AIT_AGENT_STRING` / `$DEFAULT_AGENT_STRING`; `--agent-string` override | preserved | skillrun argument table |
| R15 | `--profile-override` merges ad-hoc YAML | preserved | skillrun |
| R15 | live mode: gitignored `local/_skillrun_<unique>.yaml`, agent gets `--profile`, file deleted on exit | preserved | skillrun "the file is deleted when the agent exits" |
| R15 | `--dry-run` previews | preserved | skillrun |
| R17 | dialog is in `ait board` or `ait codeagent` (AgentCommandScreen) | changed | EP#Editing the profile "The launch dialog that `ait board` and other TUIs open". `ait codeagent` dropped; it is a shell script that does not use AgentCommandScreen, which codebrowser, brainstorm and others use. |
| R17 | Profile row (E)dit opens the same editor as `ait settings`, plus a second save mode | preserved | EP "opens the same profile editor as `ait settings`, with two ways to save" |
| R18 | persistent save → `local/<name>.yaml`, user layer, gitignored, shadows same-name project profile | preserved | EP |
| R18/R19 | button names "Save persistently" / "Save as one-shot" | changed | EP "**(S)ave**" / "**Save as (O)ne-shot**"; matches `profile_editor.py` labels |
| R19 | one-shot writes `_skillrun_` file, rewrites launch command; same mechanism as `--profile-override` | preserved | EP |
| R19 | pruned best-effort (≥1 h old) "at TUI startup" | changed | EP "One-shot files at least an hour old are removed, best-effort, whenever a launch dialog opens". Code: `_prune_stale_skillrun_overrides()` runs in AgentCommandScreen init. |
| R21 | steps 1–3: stub read, resolve script or `--profile` | preserved | DEV-ST#How dispatch works |
| R21 | step 4: render command, dep-closure walk, ref rewriting, no-op when fresh | preserved | DEV-ST step 4 |
| R21 | step 5: read `aitask-pick-<p>-/SKILL.md` and follow it | preserved | DEV-ST step 5 |
| R22 | same flow on every agent; only surface and dir differ | preserved | DEV-ST |
| R26 | Claude row | preserved | DEV-ST#Per-agent surfaces |
| R27 | Codex row | preserved | DEV-ST |
| R28 | Gemini row (`.gemini/commands/<skill>.toml`, `.gemini/skills/<skill>-<profile>-/`) | changed | Row removed; Gemini no longer supported |
| R29 | OpenCode row | preserved | DEV-ST |
| R30 | `-codex-` segment: root shared with future `agy`; prevents collisions | preserved | DEV-ST "can be read by more than one agent ... prevents collisions"; SSP#3a "today: codex + future agy" |
| R30 | others keep the short `<skill>-<profile>-/` form | preserved | DEV-ST "Claude and OpenCode keep the shorter" |
| R30 | decided by the `agent_shared_skills_root` predicate | preserved | SSP#3a / #3g |
| R32 | trailing hyphen = generated marker, one glob per root | preserved | DEV-ST#Rendered directories |
| R33 | claude/agents/opencode globs | preserved | DEV-ST |
| R33 | `.gemini/skills/*-/` glob | changed | Removed; `.gitignore` has no gemini glob |
| R34 | authoring dir names must not end with `-` | preserved | DEV-ST |
| R34 | rendered on demand; never edit or commit | preserved | DEV-ST |
| R34 | two skills ship pre-rendered remote variants, negated in `.gitignore` | preserved | DEV-ST, now names `aitask-pickrem`, `aitask-pickweb` + task-workflow procedures |
| R36 | author `.md.j2` once against the Claude surface, then add stubs on the other surfaces | preserved | SAC#Profile-aware skills require a stub + `.md.j2` pair |
| R37 | `{% if profile.<key> %}` with key examples | preserved | SAC#Jinja comment conventions (default_email, create_worktree, plan_preference labels) |
| R38 | `{% if agent == "<name>" %}`; today used by aitask-wrap Step 1b (`~/.claude/plans`, claude-only) | preserved | agent_runtime_guards_audit.md lines 5, 39 |
| R39 | `{% raw %}…{% endraw %}` wraps literal `{{`/`{%` that must not be evaluated | weakened | SAC#minijinja caveats lists `{% raw %} ... {% endraw %}` among supported constructs; DEV-ST says "minijinja caveats including `{% raw %}`". Neither says literal `{{` / `{%` markers must be wrapped in it. |
| R40/41 | run `aitask_skill_verify.sh` before committing any `.md.j2` / stub change | preserved | SAC#Verifying `.j2` templates before commit |
| R42 | verify renders every `.j2` "against every profile for all four agents", walks closure, asserts stub markers | changed | SAC: "renders every `.j2` against `default.yaml` for all 4 supported agents (claude, codex, gemini, opencode)". Closure walk and markers are preserved. Code: `agents=(claude codex opencode)`, default.yaml render plus walk-verify of headless profiles, so both the old page and SAC are inaccurate. |
| R42 | regenerate goldens in the same commit | preserved | SAC#Regenerate goldens "Commit rule" |
| R44 | stub-skill-pattern contents | preserved | DEV-ST#Authoring |
| R45 | skill_authoring_conventions contents | preserved | DEV-ST#Authoring |
| R46 | runtime guards audit contents | preserved | DEV-ST#Authoring |

```
SOURCE: website/content/docs/commands/setup-install.md
claims: 9  preserved: 7  weakened: 0  missing: 0  changed: 2
```
| R# | claim | verdict | where / quote |
|---|---|---|---|
| R1 | Codex hook is part of the "Install Codex CLI skills and config?" prompt, shown only if Codex is installed | preserved | same page#Session Hooks |
| R1 | merged by parse and rewrite; comments in `.codex/config.toml` lost | preserved | same |
| R1 | trust_level "trusted" required; setup never writes it | preserved | same |
| R1 | TUI fires the hook at first turn, not launch | preserved | same |
| R1 | measured 0.163.0 / 0.153.4 `codex exec` | preserved | ASS#Codex hook timing |
| R1 | "On Linux, an older Codex agent has its session captured when it is frozen" | changed | now "On Linux and macOS, a Codex agent whose release never fires the hook in its interactive TUI has its session captured…". Matches ASS (`lsof` on macOS) and the code. |
| R1 | transcript exists only after a turn; frozen before first turn → re-pick | preserved | same |
| R1 | "On Linux a resumed Codex agent is verified from the transcript…" | changed | now "On those platforms" (Linux and macOS) |
| R1 | elsewhere → unverified | preserved | same; "elsewhere" now means outside Linux and macOS |

```
SOURCE: website/content/docs/workflows/freeze-and-restore-agents.md
claims: 13  preserved: 13  weakened: 0  missing: 0  changed: 0
```
| R# | claim | verdict | where |
|---|---|---|---|
| R1 | re-pick needs a task id; restore needs a session id | preserved | same page#The daily loop (only link targets changed) |
| R1 | OpenCode can only be re-picked | preserved | same |
| R1 | restore needs the CLI and relaunches only that CLI | preserved | same |
| R1 | hand-started agent uses the recorded agent/model when recoverable | preserved | same |
| R1 | else default for raw sessions; resumes only if same CLI | preserved | same |
| R1 | unknown or different → refused, frozen; re-pick available | preserved | same |
| R1 | hand-started Codex via daemon: no session id recorded | preserved | same |
| R1 | shell-prompt Codex (`-c tui.alternate_screen=never`) read only while foreground; suspended or background never taken | preserved | same |
| R1 | restorable only if model nameable (known `-m`, or Codex model on record), else re-pick | preserved | same |
| R2 | hook fires only at first turn | preserved | same page#What "unverified" means |
| R2 | measured 0.163.0 / 0.153.4 | preserved | ASS#Codex hook timing |
| R2 | resumed Codex never self-confirms via hook within the grace → transcript check | preserved | same page#What "unverified" means |
| R2 | later hook at first message upgrades to `restored`, deletes capture | preserved | same |

```
SOURCE: website/content/docs/tuis/frozenagent/reference.md
claims: 3  preserved: 2  weakened: 0  missing: 0  changed: 1
```
| R# | claim | verdict | where / quote |
|---|---|---|---|
| R1 | `restore_ack_grace` default 20 s | preserved | same page#Configuration |
| R1 | waits for hook / transcript verification, then falls back to liveness | preserved | same |
| R1 | transcript verification "for a Codex resume on Linux" | changed | now "on Linux and macOS" |

```
SOURCE: website/content/docs/commands/_index.md
claims: 1  preserved: 1  weakened: 0  missing: 0  changed: 0
```
| R# | claim | verdict | where |
|---|---|---|---|
| R1 | `ait skillrun`: "Launch a code agent with a profile-aware aitask skill" | preserved | same row, unchanged. Only the link target moved, from `concepts/skill-templating/#invocation-paths` to the relref `/docs/commands/skillrun` (navigation). |

---

**Only weakened / missing / changed claims**

Weakened:
1. **skill-templating R39.** Source wording: "`{% raw %} … {% endraw %}` wraps literal `{{` / `{%` markers that must not be evaluated." SAC#minijinja caveats lists `{% raw %} ... {% endraw %}` only as a supported construct, and DEV-ST only names it. No current page states the rule that literal `{{` / `{%` in a template must be wrapped in `{% raw %}`.

Changed (all appear to be deliberate corrections, checked against the code):
2. **skill-templating R10.** Source: "(`ARGUMENTS` in Claude / Codex, `{{args}}` in Gemini, `$ARGUMENTS` in OpenCode)". DEV-ST drops Gemini. No `.gemini/` dir exists and `aitask_skill_verify.sh` has `agents=(claude codex opencode)`.
3. **skill-templating R28.** Source row: "| Gemini | `.gemini/commands/<skill>.toml` (`prompt` field) | `.gemini/skills/<skill>-<profile>-/SKILL.md` |". Removed from DEV-ST.
4. **skill-templating R33.** Source glob "`.gemini/skills/*-/`". Removed from DEV-ST; `.gitignore` has no gemini line either.
5. **skill-templating R17.** Source: "In `ait board` or `ait codeagent`, the `AgentCommandScreen` carries a **Profile** row". EP now says "The launch dialog that `ait board` and other TUIs open". `ait codeagent` (`aitask_codeagent.sh`) does not use AgentCommandScreen.
6. **skill-templating R18/R19.** Source button names: "**Save persistently**" / "**Save as one-shot**". EP now has "**(S)ave**" / "**Save as (O)ne-shot**", matching the `profile_editor.py` labels.
7. **skill-templating R19.** Source: "the file is best-effort pruned (≥1 hour old) at TUI startup." EP: "removed, best-effort, whenever a launch dialog opens". The prune runs in the AgentCommandScreen constructor, so the new wording is the accurate one.
8. **skill-templating R42.** Source: "It renders every committed `.j2` against every profile for all four agents, walks the dep closure, and asserts the stub-pattern markers." SAC#Verifying says "against `default.yaml` for all 4 supported agents (claude, codex, gemini, opencode)". The code renders default.yaml for 3 agents and walk-verifies headless profiles, so neither the old page nor SAC is accurate. The SAC text needs updating; it lies outside this assignment and pre-dates these edits.
9. **setup-install R1.** Source: "On Linux, an older Codex agent has its session captured when it is frozen instead, from the transcript its process holds open". Now: "On Linux and macOS, a Codex agent whose release never fires the hook in its interactive TUI has its session captured…". This matches ASS and `lib/agent_sessions.py` (`lsof` on macOS).
10. **setup-install R1.** Source: "On Linux a resumed Codex agent is verified from the transcript its process holds open, so its restores do not wait for the hook. Elsewhere they report as unverified." Now: "On those platforms…" (Linux and macOS).
11. **frozenagent/reference R1.** Source: "or for a Codex resume on Linux by the transcript its process holds open". Now: "on Linux and macOS".

Nothing is missing. Every framework-session fact survives in DEV-FS or ASS. Version numbers, the lock, the nonce + pid lease, the transcript-path shapes and the `/proc` / `lsof` detail moved to ASS by design.

### Checker report: tasks + attachments group (verbatim)

Fact-survival check: 11 source pages, read-only (nothing was edited, staged or committed).

Totals: 199 claims. 176 preserved, 3 weakened, 3 missing, 17 changed. Most of the "changed" rows are refinements that look like deliberate corrections; for the `--issue-type` to `--type` change I checked the code and the current text is correct.

## SOURCE: website/content/docs/concepts/topic-anchoring.md
claims: 38  preserved: 31  weakened: 0  missing: 0  changed: 7
| R# | claim | verdict | where / quote |
|---|---|---|---|
| R1 | the anchor's value is the topic root's task id | preserved | concepts/topic-anchoring#What it is: "recording the root's task number in a field called its anchor"; task-format#Frontmatter Fields `anchor` row |
| R1 | the By-Topic view clusters tasks with the same key | preserved | board/reference#Base filters: "Tasks clustered into per-anchor swimlanes by their topic key" |
| R2 | an anchor is not a dependency, label or parent-child link; it groups tasks without the parent lifecycle | preserved | topic-anchoring#What it is: "A topic does not tie its tasks together in any other way. Each one is still planned, picked up, implemented and archived on its own"; #Why it exists list |
| R3 | a task has exactly one topic but can be in any number of trails; one trail can span several topics | preserved | workflows/implementation-trails (line 150): "a task belongs to exactly one topic, but it may appear in several trails, and one trail may span several topics" |
| R3 | a trail is a projection, not a regrouping; putting a task in a trail never changes its anchor | preserved | implementation-trails#Where a Trail Is Stored (line 144): "It never rewrites `depends`, priority, board position, or a task's topic"; line 131 |
| R5 | a root omits `anchor`; its own id is the topic key | preserved | task-format#Topic Anchoring: "A root task omits the field; its own task id is its topic key" |
| R5 | a related task stores the root id in bare form | preserved | task-format#Topic Anchoring |
| R6 | YAML example `anchor: 130` | preserved | task-format#Topic Anchoring (same block) |
| R7 | `--anchor t130` and `--anchor 130` both store `130`; child ids use the bare form `130_2` | preserved | task-format#Topic Anchoring: "Task ids are normalized when they are written…" |
| R7 | anchor targets are validated to exist | preserved | task-format#Topic Anchoring: "The target must exist"; task-management `--anchor` row |
| R7 | completed or archived tasks are valid roots, so a topic keeps collecting follow-ups | preserved | task-format#Topic Anchoring: "a completed or archived task is a valid root, so a long-running topic keeps collecting follow-ups" |
| R9 | use `--anchor` when the root is already known | preserved | task-management#ait-create `--anchor` row; concept#How to use |
| R10 | example command uses `--issue-type enhancement` | changed | task-format#Topic Anchoring now uses `--type enhancement`. Correction: `aitask_create.sh` has no `--issue-type` flag, only `--type/-t` |
| R11 | use `--followup-of` to inherit the source task's topic | preserved | task-management `--followup-of` row; concept: "for a follow-up it finds the root for you" |
| R12 | example command uses `--issue-type` | changed | task-format#Topic Anchoring now uses `--type` (same correction) |
| R13 | source has `anchor: 130`, so the new task gets `anchor: 130` | preserved | task-management `--followup-of`: "if the source has an anchor, the new task gets the same anchor" |
| R13 | an anchorless child `130_2` gives anchor `130` | preserved | task-management `--followup-of`: "anchors to its parent id, 130, even when that parent has an anchor of its own" |
| R13 | an anchorless parent gives an anchor to that parent | preserved | task-management: "otherwise it anchors to the source itself" |
| R13 | "Follow-ups never form anchor chains" | changed | task-management keeps only "A follow-up of an anchored follow-up therefore points at the same root", and now says an anchorless child's source anchors to the parent id "even when that parent has an anchor of its own". That case is a chain, so the universal statement is gone |
| R14 | `--anchor` and `--followup-of` are mutually exclusive | preserved | task-management, both rows |
| R14 | both are rejected with `--parent`, because children derive their topic from the parent | preserved | task-management `--anchor`: "rejected with --parent, because a child derives its topic from its parent" |
| R16 | a child created with `--parent P` inherits `P.anchor`, else `P` | changed | task-format#Topic Anchoring: "A child created **in batch mode** with --parent P inherits…"; "Interactive `ait create` (without `--batch`) writes no anchor for any task" |
| R16 | one topic lane can hold the parent, its children and loose follow-ups | preserved | task-format: "a topic can include a parent, its child tasks and loose follow-ups in one board lane" |
| R18 | `aitask_update.sh --batch 180 --anchor 130` moves a task to another topic | preserved | task-format: "Use aitask_update.sh --batch <id> --anchor <root> to move a task"; task-management `--anchor` row |
| R20 | `--anchor ""` makes the task its own root again | changed | task-format: "Clearing the field therefore makes a standalone task its own root again, while an anchorless child stays in its parent's topic"; task-management update `--anchor` row says the same |
| R22 | use a topic when tasks belong together but have independent lifecycles | preserved | concept#Why it exists, first bullet |
| R23 | use parent-child for ordered decomposition that shares the parent's lifecycle | preserved | concept: "split into ordered parts that are finished as a set" |
| R24 | use `depends` when a task can't be implemented until another lands | preserved | concept: "Use a dependency when a task cannot start until another one is done" |
| R25 | use labels for broad filtering (`ui`, `docs`, `performance`) | preserved | concept: "a tag such as ui or docs, to filter across many unrelated subjects" (the `performance` example was dropped) |
| R26 | these relationships combine (anchored follow-up plus a dependency on a fix) | preserved | concept: "These combine: a follow-up can belong to a feature's topic and also depend on a bug fix" |
| R28 | `y` switches to By-Topic | preserved | concept#How to use; board/reference shortcut table |
| R28 | topic key is `anchor`, else the child's parent topic, else the task's own id | preserved | board/reference#Base filters: "By-Topic lanes" paragraph |
| R28 | topics with two or more **visible** tasks get a lane | changed | board/reference: "Lanes are built from every task the board loads (… archived tasks are not loaded), before any search filter applies. A topic with two or more loaded tasks gets its own lane" |
| R28 | a lane is labelled by its root task when available | preserved | board/reference: "labelled `t<id>` and the root task's name" |
| R28 | single-task topics go to the trailing Ungrouped lane | preserved | board/reference: "Topics with only one task are collected in the trailing **Ungrouped** lane" |
| R29 | if the root is archived or not loaded, its id stays the lane key and follow-ups keep clustering | preserved | board/reference: "the anchor id still remains the stable lane key, so follow-ups anchored to an archived root keep clustering together" |
| R29 | the lane label falls back to the id | changed | board/reference: "the label takes the name of the lane's first task instead" |
| R30 | the board's task detail screen can edit the anchor | preserved | concept: "The task detail screen of the board … can edit the anchor too"; board/reference field table: anchor "Yes" |

## SOURCE: website/content/docs/concepts/attachments.md
claims: 44  preserved: 44  weakened: 0  missing: 0  changed: 0
| R# | claim | verdict | where / quote |
|---|---|---|---|
| R1 | an attachment is a file (screenshot, log, PDF) stored with a task | preserved | attachments#What it is |
| R1 | its identity is the SHA-256 of its bytes; the name is only a label | preserved | task-format#attachments: entry fields: "`hash` … `sha256:<64 hex digits>`; the identity", "`name` … Display label" |
| R1 | the task file records attachments in a nested `attachments:` block | preserved | task-format#Nested fields |
| R2 | example `attachments:` block | preserved | task-format#Nested fields (identical) |
| R3/R6 | bytes are copied into task data, so the attachment survives the original being moved, edited or deleted | preserved | attachments#What it is: "the original can be moved, edited or deleted and the attachment stays" |
| R5 | a task refers to an attachment by `hash`, never by path or URL; the `sha256:` prefix names the algorithm | preserved | task-format#attachments: entry fields (same sentence) |
| R7 | identical bytes are stored once: one blob, two references | preserved | attachments#What it is; attach.md#add: "stores nothing new: the existing blob gains a second reference" |
| R7 | each task can give the blob its own name, because the name lives in the task file | preserved | task-format: "Because the name lives in the task file and not with the blob, two tasks … can each give them their own name" |
| R8 | `get` verifies the hash and refuses a mismatch | preserved | attach.md#get: "A hash mismatch on fetch is an error; the bytes are not written" |
| R9 | storage path and cache key both come from the hash; no lookup table | preserved | task-format#Where attachment blobs live |
| R10 | an edit is a different attachment | preserved | attachments: "changing a file's contents makes a different attachment" |
| R12 | six fields: two belong to the task, the rest to the blob | preserved | task-format#attachments: entry fields table |
| R15 | `hash` is `sha256:<64 hex>`, the identity | preserved | same table |
| R16 | `name` defaults to the basename and is unique per task | preserved | same table |
| R17 | `added_at` format `YYYY-MM-DD HH:MM` | preserved | same table |
| R18 | `mime` is the detected content type | preserved | same table |
| R19 | `size` in bytes | preserved | same table |
| R20 | `backend` says where the copy lives | preserved | same table |
| R21 | written by `add`/`rm`, never by hand | preserved | task-format `attachments` row: "Written by ait attach add / rm, never by hand" |
| R21 | blob and ledger are updated in the same commit; a hand edit no longer matches | preserved | task-format#Nested fields: "Editing the block by hand desynchronises it from the store"; #Where attachment blobs live |
| R23/R24 | blobs and ledger sit in the task data worktree, sharded by 2 hex digits; `.attach.lock` serializes changes | preserved | task-format#Where attachment blobs live (same tree). Now scoped to branch mode, with a new legacy-mode line |
| R25 | `local` is the only backend `add` accepts | preserved | attach.md `--backend` row; task-format |
| R25 | there is no command to move an attachment to another backend | preserved | task-format: "ait attach cannot move an attachment to another backend yet"; attach.md#Not available |
| R25 | each machine has a cache at `~/.cache/ait/artifacts/<hash>` | preserved | task-format (now also documents `$XDG_CACHE_HOME`) |
| R25 | for `local`, a cache entry is a link to the blob | preserved | task-format |
| R27 | `add` commits blob, ledger and task file together as one `ait:` commit under the lock | preserved | task-format: "commits all three together as one ait: commit, so they cannot drift apart"; attach.md#add |
| R27 | `rm` commits ledger and task file the same way | preserved | task-format; attach.md#rm |
| R28 | a verb refuses to start when the task file or a ledger file is dirty; commit or revert first | preserved | attach.md#Uncommitted changes |
| R28 | blobs are exempt, because a blob's path is its hash | preserved | attach.md#Uncommitted changes |
| R29 | a partial failure restores the files or reports which it could not | preserved | attach.md#Uncommitted changes |
| R31 | each blob's ledger lists the referencing tasks (`refs`) | preserved | task-format; attach.md#References |
| R31/R40 | one ledger file per blob, not a shared index, so unrelated or concurrent attaches never contend on the data branch | preserved | aidocs/attachment_metadata_bucketing.md §1: "Per-blob was chosen … to avoid a global write-hotspot". No website page states this rationale any more |
| R33 | `add` adds the task to `refs` | preserved | attach.md#References over a task's life |
| R34 | `rm` removes the ref and the entry and does not delete the blob | preserved | attach.md#rm |
| R34 | when the last ref goes, the ledger records the orphan time | preserved | attach.md#rm |
| R35 | archiving changes nothing; an archived task is a real referrer, kept indefinitely | preserved | attach.md#References |
| R35 | archived attachments stay listable and fetchable; `add` refuses an archived task | preserved | attach.md#References and #add |
| R36 | folding moves refs to the primary | preserved | attach.md#References; attachments concept |
| R37 | deleting a task from the board releases its refs, or hands them to a revived folded task | preserved | attach.md#References |
| R38 | blobs are reclaimed only by an explicit `gc` | preserved | attach.md#gc: "nothing runs it automatically" |
| R38 | gc requires no ledger ref, no active or archived task listing the hash, and no artifact version | preserved | attach.md#gc conditions 1–3 |
| R38 | an orphaned blob is kept for the grace period, `attachments_gc_grace`, 30 days by default | preserved | attach.md#gc condition 4; #Configuration |
| R39 | why: explanatory files live in temporary places; an attachment travels with the task, active or archived | preserved | attachments#Why it exists |
| R40 | re-attaching costs nothing; a copy is always checked against the record | preserved | attachments#Why it exists: "adds no second copy … every fetch is checked against the hash" |

## SOURCE: website/content/docs/concepts/tasks.md
claims: 16  preserved: 14  weakened: 1  missing: 1  changed: 0
| R# | claim | verdict | where / quote |
|---|---|---|---|
| R1 | a task is a markdown file with YAML frontmatter in `aitasks/` | preserved | tasks#What it is |
| R1 | named `t<N>_<short_name>.md`, e.g. `t130_add_login.md` | preserved | tasks (example); task-format#File Structure: "`t<number>_<name>.md`" |
| R1 | the frontmatter groups (priority/effort, status/depends/boardcol, issue_type/labels, assigned_to, workflow fields) | preserved | task-format#Frontmatter Fields; tasks: "including the ones the workflow writes for itself" |
| R1 | the body describes the work | preserved | tasks |
| R1 | Task File Format documents every field | preserved | tasks#How to use |
| R1 | tasks are committed to git like code | preserved | tasks |
| R1 | every CLI command, TUI and skill works on the files directly | preserved | tasks: "Every part of aitasks reads and writes these files directly" |
| R2 | full history is in `git log` | preserved | tasks#Why: "every change to a task is in its git history" |
| R2 | branches and worktrees can carry their own task state | missing | — |
| R2 | an agent edits tasks with the same tools it uses for code | preserved | tasks#Why |
| R2 | the schema is small enough for an LLM to keep in context | preserved | tasks#Why |
| R2 | the schema can drive prioritization, dependency resolution and Kanban triage | preserved | tasks#Why |
| R4 | every way of making a task just writes a file into `aitasks/` | preserved | tasks#How to use |
| R4 | `ait create` is typically launched from a TUI like Board **or Brainstorm** | weakened | tasks: "typically started from the board". Brainstorm was dropped, and no page says Brainstorm launches `ait create` |
| R4 | `/aitask-explore` and `/aitask-wrap` capture tasks from code | preserved | tasks#How to use |
| R4 | `/aitask-pr-import` is an import flow | preserved | tasks#How to use |

## SOURCE: website/content/docs/concepts/plans.md
claims: 14  preserved: 14  weakened: 0  missing: 0  changed: 0
| R# | claim | verdict | where / quote |
|---|---|---|---|
| R1 | a plan is `aiplans/p<N>_<name>.md`, mirroring its task | preserved | plans#What it is; task-format#Plan Files |
| R1 | child plans live at `aiplans/p<parent>/p<parent>_<child>_<name>.md` | preserved | task-format#Parent-Child Hierarchies: "Child plans live in aiplans/p<parent>/ (e.g., aiplans/p10/p10_1_add_login.md)" |
| R1 | the header records task, worktree, branch and base branch | preserved | task-format#Plan Files header table |
| R1 | the body has context, steps, critical files and verification | preserved | plans#What it is; task-format#Plan Files |
| R1 | the plan is written in the planning phase of a skill like `/aitask-pick` | preserved | plans#What it is |
| R1 | the user approves it before any code | preserved | plans: "you approve it before any code changes" |
| R2 | planning is kept apart from doing; approval happens once, in plain words | preserved | plans#Why |
| R2 | the agent records deviations, review changes and final notes | preserved | plans#Why |
| R2 | archived plans are the long-term record | preserved | plans#Why |
| R2 | later sibling tasks read them as primary context | preserved | plans#Why: "Child tasks … read it first" |
| R2 | the Code Browser surfaces them | preserved | plans#Why |
| R2 | keeping plans in `aiplans/` rather than session memory is what makes the record possible | preserved | concepts/agent-memory#What it is: "a structured, version-controlled record … that subsequent agent sessions read" (the explicit session-memory contrast is gone) |
| R3 | plans are produced by pick/explore, not written by hand | preserved | plans#How to use |
| R3 | naming, header and verification protocol are defined in `task-workflow/planning.md` | preserved | task-format#Plan Files: "The full rules … are in task-workflow/planning.md" |

## SOURCE: website/content/docs/concepts/parent-child.md
claims: 12  preserved: 11  weakened: 0  missing: 0  changed: 1
| R# | claim | verdict | where / quote |
|---|---|---|---|
| R1 | a parent is a regular task split into children | preserved | parent-child#What it is |
| R1 | file layout `aitasks/t<N>/t<N>_<M>_<name>.md`, with example | preserved | parent-child; task-format#Parent-Child Hierarchies |
| R1 | `children_to_implement` lists the children still pending | preserved | task-format#Parent-Child: "Parent tasks track remaining children via the children_to_implement" |
| R1 | children automatically depend on each other in order | preserved | parent-child: "By default each child depends on the one before it" |
| R1 | the parent is archived when the last child is | preserved | parent-child; task-format |
| R1 | the parent counts as completed if any child was completed; superseded/obsolete only if none was | preserved | task-format#Parent-Child: "gets a superseded or obsolete archived_reason … only when none was" |
| R2 | large tasks clutter context, the plan drifts, review gets unwieldy | preserved | parent-child#Why |
| R2 | the problem is planned once and each child gets a fresh context with its slice | preserved | parent-child#Why |
| R2 | archived child plans become primary context for later siblings | preserved | parent-child#Why |
| R3 | a child is picked like any task: `/aitask-pick 130_2` | preserved | parent-child#How to use |
| R3 | the board shows parents with pending children as **"Has children"** | changed | parent-child: "a parent's card shows how many children it has" (matches board/reference card anatomy "👶 3 children"; "Has children" is the `ait ls` label) |
| R3 | drilling into a parent lets you pick a specific child | preserved | parent-child: "opening it lets you pick a specific child" |

## SOURCE: website/content/docs/concepts/task-lifecycle.md
claims: 14  preserved: 9  weakened: 1  missing: 1  changed: 3
| R# | claim | verdict | where / quote |
|---|---|---|---|
| R1 | Ready means available to be picked | preserved | task-lifecycle table: "Ready to start work on; new tasks start here." ("triaged" dropped) |
| R2 | Editing means being authored or revised **in a TUI**; not yet ready | weakened | table: "Still being written or revised; not ready to start yet." The "in a TUI" scope is gone |
| R3 | Implementing means a skill claimed the task and an agent is working | preserved | table: "A coding agent has started work on it and holds its task lock" |
| R4 | Postponed tasks stay visible but normal selection skips them | preserved | table |
| R5 | Done means finished and committed, **awaiting archival** | changed | table: "Finished; archived tasks keep this status"; body: "archiving sets the status to Done and moves the file" |
| R6 | Folded means merged into the `folded_into` task | preserved | table; task-format `folded_into` row |
| R7 | picking moves Ready to Implementing and takes the lock | preserved | task-lifecycle#What it is |
| R7 | a successful run moves Implementing to Done, then Done to Archived when the file moves to `aitasks/archived/` | changed | task-lifecycle: "When the work is finished and committed, archiving sets the status to Done and moves the file into the archive". task-format#Status Workflow: "Archiving sets this status in the same step that moves the task file". The location is preserved in task-format#File Structure |
| R7 | aborting reverts to Ready and releases the lock | changed | task-lifecycle: "Aborting puts it back to Ready (or Editing, if you choose) and releases the lock" |
| R7 | Folded is terminal; folded files are deleted, not archived, with the primary | preserved | task-lifecycle |
| R8 | a small fixed set of statuses keeps prioritization, board and selection logic simple | missing | — (the Why section now explains what the status tells you, not why the set is small) |
| R8 | transitions are commits, so `git log` is the audit trail | preserved | task-lifecycle#Why |
| R9 | you rarely set status by hand; pick, archive, abort and fold set it | preserved | task-lifecycle#How to use |
| R9 | the logic is in `aitask_pick_own.sh`, `aitask_archive.sh` and `task-abort.md` | preserved | task-format#Status Workflow (same three links) |

## SOURCE: website/content/docs/concepts/folded-tasks.md
claims: 15  preserved: 13  weakened: 1  missing: 0  changed: 1
| R# | claim | verdict | where / quote |
|---|---|---|---|
| R1 | the folded task's content is merged into the primary | preserved | folded-tasks#What it is |
| R1 | folding sets `status: Folded` | preserved | task-lifecycle table; skills/aitask-fold step 3; workflows/task-consolidation#How It Works |
| R1 | `folded_into` points at the primary | preserved | task-format `folded_into` row; aitask-fold step 3 |
| R1 | the primary lists folded tasks in `folded_tasks` | preserved | task-format `folded_tasks` row; aitask-fold step 4 |
| R1 | the body goes under a `## Merged from t<N>` header | preserved | task-consolidation; aitask-fold step 4; CLAUDE.md |
| R1 | the folded file stays only as a reference and is deleted, not archived, with the primary | preserved | folded-tasks#What it is |
| R2 | duplicate work across separate plans wastes context and produces redundant commits | preserved | folded-tasks#Why |
| R2 | folding preserves each original's framing | preserved | folded-tasks#Why |
| R2 | folded tasks are merged, not superseded or replaced | preserved | task-format `archived_reason` row: "a folded task is **merged** into its primary … not superseded"; CLAUDE.md "Folded Task Semantics" |
| R2 | the original wording stays visible for reviewers | preserved | folded-tasks#Why |
| R2 | code, **commit messages** and procedures say "merged"/"incorporated" | weakened | CLAUDE.md lists "code, procedures, and docs" only. Commit messages are not named, and no website page states the rule now |
| R3 | `/aitask-fold` merges two or more tasks | preserved | folded-tasks#How to use |
| R3 | inline fold trigger: "if a plan in /aitask-pick names additional tasks to fold in" | changed | folded-tasks: "if the task's description, or you during planning, asks for other tasks to be folded in" |
| R3 | the workflow folds inline before continuing | preserved | folded-tasks: "the workflow folds them before planning continues" |
| R3 | both parent-level and child-level tasks can be folded | preserved | folded-tasks: "Both parent and child tasks can be folded." (see the note at the end) |

## SOURCE: website/content/docs/concepts/artifacts.md
claims: 9  preserved: 9  weakened: 0  missing: 0  changed: 0
| R# | claim | verdict | where / quote |
|---|---|---|---|
| R2 | with an `origin`, a write counts only once `origin` accepts it, so `origin` must be reachable | preserved | commands/artifact#The gitbranch backend: "A write succeeds only once the push is accepted; if origin cannot be reached the write fails" |
| R2 | with no `origin`, the local branch is the store and nothing is pushed | preserved | same section |
| R3 | an existing ordinary branch is refused | preserved | artifact.md: "An existing branch without the store marker is refused" |
| R3 | reserved names such as `main` and `aitask-data` are refused | preserved | artifact.md branch rules list |
| R4 | renaming the branch needs `gitbranch-migrate`, not `move` | preserved | artifact.md#move: "`move --to gitbranch` cannot change which branch … that is gitbranch-migrate"; Configuration row |
| R6 | outputs too large or too frequent for a task file; noisy history | preserved | artifacts#Why it exists |
| R6 | the handle is recorded once; versions and moves touch only the manifest | preserved | artifacts#Why it exists |
| R6 | a stable handle keeps links valid and fetchable on any machine | preserved | artifacts#Why it exists |
| R7 | the backend choice keeps large blobs off the data branch: start `local`, move to `dir`/`gitbranch` | preserved | artifacts#Why it exists |

## SOURCE: website/content/docs/development/task-format.md
claims: 17  preserved: 13  weakened: 0  missing: 0  changed: 4
| R# | claim | verdict | where / quote |
|---|---|---|---|
| R1 | neither nested block is hand-edited | preserved | task-format#Nested fields |
| R1 | entries are written by `ait artifact` / `ait attach` | preserved | same |
| R1 | each writes store and task file as one commit | preserved | same (artifact: blob + manifest + task file; attach: via "Where attachment blobs live") |
| R1 | a hand edit desynchronises the block | preserved | same |
| R2 | an anchor groups tasks without making them children | preserved | task-format#Topic Anchoring |
| R2 | a root omits the field; its id is the key | preserved | same |
| R2 | related tasks store the bare root id | preserved | same |
| R3 | `anchor: 130` example | preserved | same |
| R4 | written by `--anchor`, or derived with `--followup-of` | preserved | same |
| R4 | `--followup-of` "always resolves to the source task's root rather than chaining" | changed | task-format now defers to `ait create`; task-management: an anchorless child source "anchors to its parent id, 130, even when that parent has an anchor of its own" |
| R4 | children created with `--parent` inherit the parent's root | changed | now "A child created **in batch mode** with --parent P…"; interactive create writes no anchor |
| R4 | parent, children and follow-ups share one lane | preserved | same |
| R5 | `--anchor <root>` moves a task | preserved | same |
| R5 | `--anchor ""` makes the task its own root again | changed | now: "Clearing the field therefore makes a standalone task its own root again, while an anchorless child stays in its parent's topic" |
| R6 | Done means "Implementation complete, pending archival" | changed | now: "Done — Finished. Archiving sets this status in the same step that moves the task file, so archived tasks keep it" |
| R7 | the parent tracks children via `children_to_implement` | preserved | task-format#Parent-Child (verbatim; block only extended) |
| R7 | the parent is auto-archived when all children are complete | preserved | same |

## SOURCE: website/content/docs/tuis/board/reference.md
claims: 9  preserved: 7  weakened: 0  missing: 0  changed: 2
| R# | claim | verdict | where / quote |
|---|---|---|---|
| R1 | the key uses `anchor` when set | preserved | board/reference "By-Topic lanes" |
| R1 | a child falls back to its parent's topic | preserved | same (now spelled out: "the parent's anchor, else the parent's id") |
| R1 | a standalone task falls back to its own id | preserved | same |
| R1 | if the root is archived or not loaded, the anchor id stays the lane key | preserved | same |
| R1 | topics with only one **visible** task go to Ungrouped | changed | now counted over loaded tasks: "built from every task the board loads … before any search filter applies"; "Topics with only one task are collected…" |
| R2 | `anchor` is a string field | preserved | field table |
| R2 | editable from the board | preserved | field table "Yes" |
| R2 | it is the topic root used by By-Topic | preserved | field table |
| R2 | "Empty means the task is its own topic root" | changed | now: "…except a child task, which stays in its parent's topic" |

## SOURCE: website/content/docs/commands/attach.md
claims: 1  preserved: 1  weakened: 0  missing: 0  changed: 0
| R# | claim | verdict | where / quote |
|---|---|---|---|
| R1 | `ait attach` manages a task's attachments: content-addressed blobs stored beside the task, not inside it | preserved | attach.md intro (verbatim) |

## Weakened, missing and changed claims, with exact source wording

**Weakened**
1. tasks.md R4: "typically launched from inside a TUI like [Board](...) or Brainstorm". The current text says only "typically started from the board". Brainstorm as a launcher of `ait create` appears on no page.
2. task-lifecycle.md R2: "| `Editing` | Being authored or revised in a TUI; not yet ready for implementation. |". Current: "Still being written or revised; not ready to start yet." The "in a TUI" scope is lost.
3. folded-tasks.md R2: "This wording matters: code, commit messages, and procedures all use "merged" / "incorporated" rather than "superseded" / "replaced"." This rule now survives only in CLAUDE.md, which says "code, procedures, and docs". Commit messages are not named.

**Missing**
1. tasks.md R2: "branches and worktrees can carry their own task state".
2. task-lifecycle.md R8: "A small, fixed set of statuses lets the prioritization, board, and selection logic stay simple: every script that asks "what's next?" only has to reason about a handful of states."
3. Website only, kept in aidocs: attachments.md R31 "The ledger is one small file per blob rather than one shared index, so two unrelated attachments never contend for the same file on the shared data branch." and R40 "a per-blob ledger keeps concurrent attach operations from colliding on the shared data branch." Both are stated only in aidocs/attachment_metadata_bucketing.md §1, so I counted them as preserved. They are listed here because no website page has them any more.

**Changed** (most look like deliberate corrections)
1. topic-anchoring.md R10 and R12: example commands use `--issue-type enhancement`. task-format now uses `--type enhancement`. `aitask_create.sh` only accepts `--type/-t`, so this is a correct fix.
2. topic-anchoring.md R13: "Follow-ups never form anchor chains." Also task-format.md R4: "which always resolves to the source task's root rather than chaining follow-ups together". task-management.md now says "if the source is an anchorless child such as 130_2, the new task anchors to its parent id, 130, even when that parent has an anchor of its own … A follow-up of an anchored follow-up therefore points at the same root." That edge case is a chain, so the universal "never chains" claim is gone. The `aitask_create.sh` help still says "Flattened — never chains". Worth reconciling one way or the other.
3. topic-anchoring.md R16: "A child created with `--parent P` inherits `anchor = P.anchor` when the parent has one; otherwise it inherits `anchor = P`." Also task-format.md R4: "Children created with `--parent` inherit the parent's root". Now: "A child created in batch mode with --parent P inherits…" plus "Interactive ait create (without --batch) writes no anchor for any task".
4. topic-anchoring.md R20: "To make a task its own topic root again, clear the field". Also task-format.md R5: "or `--anchor ""` to clear the field and make the task its own root again", and board/reference.md R2: "Empty means the task is its own topic root." Now: "makes a standalone task its own root again, while an anchorless child stays in its parent's topic".
5. topic-anchoring.md R28: "Topics with two or more visible tasks get their own lane". Also board/reference.md R1: "Topics with only one visible task are collected in the trailing **Ungrouped** lane." Now: lanes are built from loaded tasks "before any search filter applies".
6. topic-anchoring.md R29: "The lane label falls back to that id". Now: "the label takes the name of the lane's first task instead" (the label is `t<id>` plus a name).
7. parent-child.md R3: "The board TUI shows parents with pending children as **Has children**". Now: "a parent's card shows how many children it has" (board card shows "👶 3 children").
8. task-lifecycle.md R5: "| `Done` | Implementation finished and committed. Awaiting archival. |". Also task-format.md R6: "**Done** — Implementation complete, pending archival". Now: "Finished; archived tasks keep this status" and "Archiving sets this status in the same step that moves the task file".
9. task-lifecycle.md R7: "a successful run moves `Implementing → Done` (then `Done → Archived` as the file moves into `aitasks/archived/`)". Now: "When the work is finished and committed, archiving sets the status to `Done` and moves the file into the archive of finished tasks."
10. task-lifecycle.md R7: "aborting reverts to `Ready` and releases the lock". Now: "Aborting puts it back to `Ready` (or `Editing`, if you choose) and releases the lock."
11. folded-tasks.md R3: "if a plan in [`/aitask-pick`] names additional tasks to fold in, the workflow runs the fold inline before continuing". Now: "if the task's description, or you during planning, asks for other tasks to be folded in, the workflow folds them before planning continues".

**Note (an older inconsistency, not a fact lost in these rewrites):** concepts/folded-tasks.md says "Both parent and child tasks can be folded", but skills/aitask-fold.md step 2 says interactive discovery only lists tasks that are "not a child task, no children of their own".

## Step 8 user review — round 1 (four findings, all verified and fixed)

1. **[medium] `concepts/gates.md` recovery advice ignored procedure gates.**
   Verified: `gate_orchestrator.resolve_verifier("aitask-gate-docs-updated")`
   yields `.aitask-scripts/aitask_gate_docs_updated.sh`, which does not exist, so
   a forced `ait gates run --gate docs_updated` records `error`. Fixed: the
   paragraph now limits `ait gates run --gate` to script-checked gates. For a
   gate whose check is coding-agent work it says the agent re-runs it at review
   or archival (task-workflow SKILL.md: Step 8 `procedure-gates` dispatch, and
   the Step 9 "Resolve now" branch, which re-dispatches a gate that is not
   `pass`/`skip`), so carry on in the agent or re-pick with `/aitask-pick <id>`.
   A first wording ("attended workflow", "agent session") added two unexplained
   terms in the re-run reader test and was rewritten in plain words.
2. **[medium] `aitask-docs-review` Step 4 wrote questions after Step 3 had read
   the body.** Fixed in `.claude/skills/aitask-docs-review/SKILL.md`: the reader
   sub-agent's first prompt carries only the title, `description` and persona,
   and it writes the questions itself. The page text is sent afterwards, in the
   same conversation. A re-test reuses the first questions. Without sub-agents,
   the questions are written in Step 3 item 1, before the body is read, and a
   reviewer who saw the body earlier (for example its drafter) says so in the
   reader report. Contract test 71/71 (one rewrap kept the pinned phrase
   `not to open files` on one line). No other agent tree carries this skill, so
   there is nothing to port.
   **Limitation for child 8:** this pilot's own reader questions were written by
   the orchestrating agent, who had read the pages during planning. Before and
   after used the same questions, so the comparison holds. But the absolute
   "unneeded details" counts may be lower than a body-blind question set would
   give.
3. **[medium] `development/merge-mutex.md` named the lock base as the mutex.**
   Verified: `merge_lock.sh` uses `ait_lock_dir merge`, and `stale_lock.sh`
   prints `<base>/merge`. The default base is
   `${TMPDIR:-/tmp}/aitask-locks-$(id -u)-<cksum of root>`, and stale_lock.sh's
   documented limitations say different users sharing a checkout do not
   serialize unless `AITASKS_LOCK_DIR` names a shared, admin-created base.
   Fixed: the storage paragraph names `merge/` under the base (and
   `$AITASKS_LOCK_DIR/merge`), and a new paragraph states the per-user
   coordination boundary. "One lock per repository" now reads "one mutex per
   repository, not one per output branch".
4. **[low] Two incoming links promised moved detail.** Retargeted:
   `workflows/crash-recovery.md` See also → `development/gates#the-ledger`;
   `workflows/task-notes.md` See also → `commands/lock#how-it-works`.
   `task-notes.md` was clean before the edit (shared-file gate).

Checks after the fixes: `check_links.py --build` SWEEP PASSED,
`test_docs_review_contract.sh` 71/71, `test_website_doc_lists.sh` passed,
`test_docs_vocabulary_coverage.sh` 32/32.

**Gates after-report re-run** (it is one of the eight reader-test pages and its
text changed). Same persona, the same seven run-2 questions, the page text
inline, follow-ups in the same conversation:
- the text with the first wording: guessed 19 + unneeded 14 = 33;
- the final text: **guessed 16 + unneeded 12 = 28**. The first after-report
  scored 27, and before scored 41.

The terms still guessed on the final text are the ones the `intermediate` page
links to instead of defining: archive, pick, execution profile, workflow,
registry, attended session and board. Readers also raised two open points:
whether a declared but unenforced gate blocks archival, and whether re-picking
re-derives the enforced set. Both are stated on `development/gates`, which the
concept page links to. They are left for child 6/8 to weigh, and are not fixed
here. Both re-runs are recorded verbatim under "Reader reports — after": the final
text first, then the two historical gates reports. The main after table
shows the final 28.

## Skipped-page ledger

Empty. The shared-file gate (`git status --short -- <page>` before each edit,
run by this session and by every restructure and fixer agent) found no page with
another session's uncommitted changes. At the start of implementation the
website, `aidocs/` and the guide were clean (`git status` at 9b54f33d8); the
sitrep pages dirty at session start had been committed in 9b54f33d8. The agents'
reports each state "Skipped files: none".

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

## Post-Review Changes

### Change Request 1 (2026-11-12)
- **Requested by user:** four review findings. (1) The gates concept page told
  readers to force any failed gate with `ait gates run --gate`, which records
  `error` for a procedure gate. (2) `aitask-docs-review` Step 4 wrote its
  questions after Step 3 had read the body. (3) merge-mutex.md named the lock
  base as the mutex and left out the per-user default boundary. (4) Two
  incoming links promised detail their targets no longer hold.
- **Changes made:** all four verified against the code and fixed. Details,
  checks and the gates reader re-runs are in "Step 8 user review — round 1"
  above.
- **Files affected:** `website/content/docs/concepts/gates.md`,
  `.claude/skills/aitask-docs-review/SKILL.md`,
  `website/content/docs/development/merge-mutex.md`,
  `website/content/docs/workflows/crash-recovery.md`,
  `website/content/docs/workflows/task-notes.md`, this plan.

### Change Request 2 (2026-11-12)
- **Requested by user:** record the final gates reader report verbatim, update
  the main after-table to the final score, and mark the older gates reports
  historical.
- **Changes made:** the final-text answers and follow-up are now quoted
  verbatim under "Reader reports — after". The run on the intermediate wording
  is quoted too, marked historical. The first after-report is relabelled
  historical. The table row reads 41 → 28 (−13), and the child-8 reading notes
  are corrected.
- **Files affected:** this plan.

## Final Implementation Notes
- **Actual work done:**
  - **Pre-phase:**
    - reader baseline on eight pages plus a scratch control. Run 1 failed
      separation; the skill's Step 4 was tuned and run 2 passed.
    - the detail-placement boundary went into the guide (behaviour detail /
      public architecture in `development/` / contributor-only in `aidocs/`),
      checked by two boundary self-review runs (below).
  - **Restructures:** six long concept pages, with four new `advanced`
    reference pages: `development/{gates,framework-session,merge-mutex,skill-templating}.md`.
  - **Other new pages:** `commands/skillrun.md` (the `ait skillrun` reference
    moved off `execution-profiles.md`) and
    `aidocs/framework/agent_session_store.md`.
  - **Step 4 fixes:** tasks, plans, parent-child, task-lifecycle, folded-tasks
    and artifacts.
  - **Guide lessons (Step 5):** signs that a concept page has grown into
    reference material; choosing `depth` by who meets the idea; moving a fact
    is the time to check it against the code.
  - **Reviews and checks:** two Step 6 review rounds and the claim-level
    fact-survival check, ending ALL_PRESERVED.
  - **After-reports:** scores fell on every page, as the after table shows
    (gates final 41 → 28).
  - **Step 8 review:** two rounds of user findings, all fixed (Post-Review
    Changes above).
- **Deviations from plan:**
  - Most page work was delegated: four restructure agents, fixer agents and
    independent reviewer and checker agents. This session gave each one a
    written brief, then reconciled and recorded their verbatim reports.
  - The skill's Step 4 was changed twice:
    - pre-phase tuning, which is allowed by the plan;
    - a Step 8 fix: the reader sub-agent now writes its own questions before
      it sees the page.
  - This pilot's own questions were written by the orchestrator after reading
    the pages. See the limitation recorded in the Step 8 round-1 section.
  - The survival check ran before the round-2 close and the Step 8 fixes. Pages
    changed afterwards got link checks and, for gates, a reader re-run, but no
    second full survival run. The Step 8 fixes added facts and cut none.
  - The attachment entry-fields table in task-format became a list.
    `tests/lib/docs_vocabulary_scan.py` reads every table row there as a
    frontmatter field.
- **Issues encountered:**
  - A `tee | head` pipe truncated the gates block file for the survival check.
    The file was rebuilt, and only gates was affected.
  - The first separation test failed: questions mirrored the page sections,
    and navigation was counted as unneeded detail.
  - The contract test pins the phrase `not to open files` on one line, so the
    line was rewrapped.
- **Key decisions:**
  - The user's placement boundary: public architecture stays on the site in
    `development/`, and `aidocs/` is only for contributor-only detail.
  - `depth` retags: gates and framework-session advanced → intermediate;
    `commands/lock.md` → advanced.
  - Gemini mentions were dropped from the site pages, because the agent is not
    supported.
  - The artifacts concept page's depth and mechanism content were left for
    t2258_6, because `commands/artifact` points back to it.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_create.sh:108` — the `--followup-of` help says
    "Flattened — never chains", but `resolve_anchor()` (line 246) anchors a
    follow-up of an anchorless child to the parent id even when that parent
    has an anchor of its own.
  - `.aitask-scripts/lib/gate_orchestrator.py:467` — `_force_one` dispatches a
    `kind: procedure` gate's verifier as a command, so `resolve_verifier` gives
    the nonexistent `aitask_gate_docs_updated.sh` and an `error` is recorded.
    The unforced path defers the gate instead.
  - `aidocs/framework/skill_authoring_conventions.md:4` — it still describes
    `.gemini/` trees and four agents. `agent_runtime_guards_audit.md:27` does
    the same. The conventions doc also says the verify script renders every
    profile, but `aitask_skill_verify.sh` renders the default profile for
    three agents.
  - `website/content/docs/development/task-format.md:47` — the `archived_reason`
    row names `ait archive --superseded/--obsolete`. There is no `ait archive`
    dispatcher verb; the flags belong to `.aitask-scripts/aitask_archive.sh`.
  - `website/content/docs/workflows/crash-recovery.md:71` — it says a session
    re-claiming its own lock refreshes it silently. But
    `aitask_pick_own.sh:782-806` still emits `RECLAIM_STATUS` for this
    session's own refreshed lock when the task is already `Implementing`, so a
    same-session re-pick is not silent. Not run end to end.
- **Notes for sibling tasks:**
  - **The guide boundary:**
    - behaviour detail goes on the feature's reference or workflow page;
    - public architecture goes in `development/`, at `advanced`;
    - contributor-only detail goes in `aidocs/`, never on the site;
    - split a mixed fact before placing it.
  - **The reader-test method:**
    - the persona sentence comes from the guide;
    - questions come from the title, description and persona only (now the
      skill's rule);
    - frontmatter and navigation are excluded from "unneeded";
    - a scratch compliant page is a better control than `tasks.md`;
    - expect a few points of run-to-run variance (gates: 27, 33, 28).
  - **The survival check:** split HEAD and working text into blocks, then have
    an independent agent compare every removed block claim by claim. Token
    greps alone miss conditions.
  - **Two traps:**
    - `docs_vocabulary_scan.py` treats every table row on task-format as a
      field;
    - do not pipe a generated file through `tee | head`.
  - **Pages that received moved facts:**
    - workflows: crash-recovery, parallel-development, freeze-and-restore
      (t2258_4);
    - board and frozenagent reference (t2258_5);
    - commands: lock, attach, gates, task-management, setup-install and the new
      skillrun (t2258_6);
    - the new `development/` pages (t2258_7).
  - **Ledger:** empty, so no `audit_deferred_pages_concepts` child is needed.

### Guide boundary self-review — run 1 (verbatim)

> I worked from the quoted passages only and used no tools.
>
> ## Classification
>
> **A. Public architecture (`development/`).** The file path, its 0600 mode and the variables that move it are "the data layout", "where state lives", and what a user needs to "configure" the framework. The two variables could also count as behaviour detail, because a user relies on them; see Q1.
>
> **B. Public architecture (`development/`).** This is "which component writes what" plus "the concurrency and atomicity guarantees a reader of that state relies on". The single writer, and the promise that readers need no lock and always see a complete file, are what an integrator relies on. The exact way it locks around each read-modify-write is close to "how the code achieves all of that". I would keep the guarantee and leave out any lock-implementation detail beyond it.
>
> **C. Contributor-only (`aidocs/`).** A named constant and a method are "internal loops and counters, private helpers, code structure". The guide's own example puts "the counter" in `aidocs/`. The rule a user can observe ("auto-close needs two consecutive refreshes that see only its own pane") is behaviour detail. It should be split out and kept on the minimonitor reference page, since "every fact survives a cut".
>
> **D. Public architecture (`development/`), with low confidence.** On its face this is "file formats": a frontmatter field's layout. But the field is framework-derived and must never be hand-edited. Which inputs go into each hash is arguably "how the code achieves" enforcement, which would make it contributor-only. It belongs in `development/` only if an integrator is expected to read or check the digest.
>
> **E. Behaviour detail (the reference page).** It is one of "the exact rules a user can observe or rely on": the refusal, that nothing changes first, and the two choices offered.
>
> **F. Public architecture (`development/`).** The block's six fields are "task and plan file formats" / "the data layout and file formats".
>
> **G. Contributor-only (`aidocs/`).** Reading `/proc` or using `lsof` is "how the code achieves" the verification. One caveat: if macOS needs `lsof` installed, that dependency is something a user must act on. It would then belong on an installation or known-issues page, and none of the three kinds covers that (Q2).
>
> **H. Behaviour detail (the reference page).** It is an "exact rule a user can observe or rely on": the restore is refused, the agent stays frozen, and the task can still be re-picked.
>
> ## 1. Ambiguous wording, and the facts it made hard
>
> - **"as far as a user or an integrator needs it"**: how much someone "needs" is subjective, and this is the only test separating public architecture from contributor-only. It made D (does anyone outside need the hash inputs?) and G (does the macOS lookup matter to a user?) hard to place.
> - **"the concurrency and atomicity guarantees"** (public) next to **"how the code achieves all of that"** (contributor-only): a fact that states both a guarantee and its mechanism, like B, has no clear dividing line.
> - **"the library scripts and functions meant to be called"** next to **"private helpers"**: nothing says how to tell which is which. In B, it is unclear whether `aitask_agent_sessions.sh` is a public entry point or an internal one.
> - **"exact rules a user can observe or rely on"** overlaps with public architecture for file formats and configuration knobs. A user "relies on" the env vars in A and the frontmatter fields in F too.
> - **"at every level"** for `aidocs/`: the levels describe site pages, so it is unclear whether this means "contributor-only detail is never allowed at any site level" or "`aidocs/` pages may be written at any depth". C is still easy to place despite this.
> - **"Each level allows everything the level before it allows"** refers to levels the excerpt never lists, apart from `advanced`.
>
> ## 2. Facts with no home
>
> - **Workflow steps.** The "spans levels" section names steps as a fourth thing a page owns ("the feature's workflow page for steps"), but the "three kinds of detail" leave them out.
> - **Conceptual / mental-model explanation** (the `concepts/` section), with no kind of its own.
> - **Installation, platform requirements and known issues** (the `installation/` section). G's `lsof` dependency is an example.
> - **Command, skill and configuration reference** (`commands/`, `skills/`). These can be treated as behaviour detail, but the guide only says "its reference page" without matching these sections to it.
> - **Design rationale meant for users.** "Rejected alternatives and design history" are contributor-only, which leaves no site home for a "why it works this way" note a user needs.
> - **Mixed facts** like C need to be split before they can be placed. The cut rule implies this, but the categories do not say so.
>
> ## 3. Contradictions
>
> - **The "no such page" rule conflicts with the kind-to-location rules.** "If the feature has no such page, put a single fact on the closest reference page" covers any kind. For a contributor-only fact that would put it on a site reference page, but "Contributor-only detail goes to `aidocs/` … at every level". It would also send a public-architecture fact to a reference page rather than `development/`.
> - **Behaviour detail ends up in `development/`.** One rule says "create a focused `advanced` reference page for it in `development/`" for a block of behaviour detail. But the landscape defines `development/` as "the framework's public architecture", and "Reader levels" sends behaviour detail to the feature's reference page.
> - **Lesser tension:** "Public architecture goes to the site's `development/` section, at `advanced`" sets a level, while `aidocs/` gets "at every level". Since `aidocs/` is not on the site, the phrase is either redundant or a category mismatch rather than a strict contradiction.

### Guide boundary self-review — run 2 (verbatim, after the guide wording fixes)

> I worked only from the quoted passages and used no files or tools.
>
> ## Classification
>
> **A. Public architecture (`development/`).** The file path and its 0600 mode come under "the data layout and file formats, where state lives", and the two environment variables fall under the same entry's "as far as a user or an integrator needs it to understand, configure or extend". One caveat: the env vars are equally "exact rules a user can … rely on" (behaviour detail), so they could also sit on a `commands/` or installation reference page. If they are really test seams rather than user settings, they are contributor-only.
>
> **B. Mixed; split it the way the guide's own example does.**
> - Public architecture: `aitask_agent_sessions.sh` is the only writer, and readers such as the monitor take no lock and always see a complete file. That is "which component writes what" plus "the concurrency and atomicity guarantees a reader of that state relies on".
> - Contributor-only: the lock around each read-modify-write and the atomic replace. That is "how a guarantee is implemented", which matches "the lock and rename that do it are contributor-only".
>
> **C. Mixed.**
> - Contributor-only: the constant `AUTO_CLOSE_CONFIRMATIONS`, the method `_check_auto_close` and the refresh counter. These are "internal loops and counters" and "private helpers", and the example names "the counter" directly.
> - Behaviour detail, for the minimonitor's TUI reference page and written without code names: the minimonitor closes itself after two consecutive refreshes that find only its own pane. This is an "exact rule a user can observe".
>
> **D. Mixed, leaning contributor-only.**
> - Public architecture: the field exists, the framework writes it (it is not hand-edited), and it records which inputs the enforced gate set came from (the raw `gates:` field, the profile defaults, the stored active sets), so changing any of them is detectable. That is the "file formats" and "which component writes what" part.
> - Contributor-only: the exact encoding (three 12-character hashes joined by dots). That is "how a guarantee is implemented", unless an integrator is meant to compute or compare the digest. The passage gives no test for deciding that.
>
> **E. Behaviour detail (the pick skill's reference page).** It is an "exact rule a user can observe or rely on": the refusal, the fact that nothing changes before it, and the leave-alone-or-force-claim question.
>
> **F. Public architecture (the task-file-format page in `development/`).** It is frontmatter layout, so "the data layout and file formats".
>
> **G. Mixed.**
> - Contributor-only: reading `/proc` on Linux and `lsof` on macOS. That is "how a guarantee is implemented".
> - Behaviour detail: a resumed Codex agent is checked to be holding the right session transcript before the restore counts as verified.
> - If macOS needs `lsof` installed, that requirement belongs on an `installation/` page. No rule in the passages sends it there (see question 2).
>
> **H. Behaviour detail (the restore/monitor reference page).** It is an "exact rule a user can observe or rely on": the restore is refused, the agent stays frozen, and you can still re-pick the task.
>
> ## 1. Ambiguous wording, and the facts it made hard to place
>
> - **"needs it to understand, configure or extend"** (public architecture) overlaps with "exact rules a user can … rely on" (behaviour detail). A user-facing setting fits both, which affected A.
> - **"the concurrency and atomicity guarantees a reader of that state relies on"** versus behaviour detail's "rely on". The guide never says whether "reader" means a program reading the state or a person using the tool. E's "refused before anything changes" is an atomicity guarantee that a user can see. B's write-side lock prevents lost updates between concurrent callers of the writer, so it could be a guarantee rather than an implementation detail.
> - **"file formats"** gives no depth: it could mean field names and meanings, or every byte of the encoding. This affected D, and to a smaller degree F.
> - **"every function no integrator is meant to call"** depends on intent that the guide gives no way to determine. It affected B (is `aitask_agent_sessions.sh` an "integrator-callable library script" or a private helper?), C and D.
> - **"integrator"** is never defined, and the split between public architecture and contributor-only depends on it.
> - **"the closest reference page"** has no definition of what "closest" means.
> - **Levels:** the excerpt says public architecture goes "at `advanced`" but never gives behaviour detail a level.
>
> ## 2. Kinds of fact the three categories leave without a home
>
> - **Steps and user-facing motivation.** The passage says "Three kinds of detail are kept apart", but the owner rule also places "steps" (workflow page) and "why a feature exists, as its user sees it" (concept page). The three categories alone don't cover these two. The other sentences give them a home, but the "three kinds" framing is incomplete.
> - **Prerequisites, platform requirements and known issues** (for example G's `lsof`). The landscape lists `installation/` for these, but no ownership rule maps any kind of fact to it.
> - **Rationale aimed at integrators**, such as why readers take no lock. It falls between "why a feature exists, as its user sees it" (concept page) and "rejected alternatives and design history" (`aidocs/`).
> - **User-facing change or migration notes.** "Design history" is contributor-only, and the passage gives no home to history a user needs.
> - **A contributor-only block whose subject has no `aidocs/` page.** The create-a-page rule covers only behaviour detail and public architecture in `development/`. Nothing says to create an `aidocs/` page.
>
> ## 3. Contradictions
>
> I found no outright contradiction, but there are three tensions:
>
> - "Reader levels" calls `development/` the home of public architecture. "How a subject spans levels" also sends "a substantial block of behaviour detail" there, which goes against "its reference page for behaviour detail". The landscape's mention of a focused `advanced` reference page reconciles the two, but the "Reader levels" sentence on its own reads as exclusive.
> - "Each level allows everything the level before it allows" could suggest `advanced` allows everything. It is held in check by "never onto the site, whatever a page's level". That works because contributor-only detail sits outside the level scale altogether, which the passage implies but never says.
> - "Three kinds of detail" conflicts with the five owners the later rule names (concept, workflow, reference, `development/`, `aidocs/`). That is a counting mismatch, not a contradiction in substance.
