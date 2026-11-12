---
Task: t2258_4_audit_workflows.md
Parent Task: aitasks/t2258_doc_audience_levels_and_readable_prose.md
Sibling Tasks: aitasks/t2258/t2258_1_*.md, aitasks/t2258/t2258_2_*.md, aitasks/t2258/t2258_3_*.md, aitasks/t2258/t2258_5_*.md, aitasks/t2258/t2258_6_*.md, aitasks/t2258/t2258_7_*.md, aitasks/t2258/t2258_8_*.md
Archived Sibling Plans: aiplans/archived/p2258/p2258_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-12 11:35
---

# t2258_4 — Workflows audit (Tasks, Reporting and Maintenance groups; the rest split into siblings)

## Context

This child audits `website/content/docs/workflows/` against the level model in
`aitasks/metadata/doc_update_guide.md` (from t2258_1). It uses
`aitask-docs-review` (from t2258_2) and the method in the parent plan
`aiplans/p2258_doc_audience_levels_and_readable_prose.md` § "Common audit method
(children 3–7)". The concepts pilot (`aiplans/archived/p2258/p2258_3_audit_concepts_pilot.md`)
covered 25 pages and six restructures, and it took a full session. The task
asks for the section to be split per workflow group when it is too large for
one session, so the section is not shipped half-audited.

## Verification of the existing plan (verify path, 2026-11-12)

Checked against main @ 7f1f4333a. These findings change the plan:

- **The skill is `aitask-docs-review`**, invoked as
  `/aitask-docs-review <page>... --caller audit --budget N`. With
  `--caller audit` it reports only (note from t2258_2, acknowledged).
- **The section is too large for one session, so it is split.** It has 44
  pages and about 5,700 lines. At least eight pages need restructuring, and
  another ten run 100–170 lines. The user chose six parts, with the Parallel
  group split in two, all run **fully sequentially**:
  4 → 9 → 10 → 11 → 12 → 13 → 5 → 6 → 7 → 8. This keeps the original order:
  workflow restructures move facts onto command and skill pages before t2258_6
  audits those pages, and guide lessons accumulate one child at a time.
  t2258_4 keeps the Tasks, Reporting and Maintenance groups.
- **`depth` is already set on every leaf page.** The one gap is
  `contribute-and-manage/_index.md`: it has 149 lines of its own content and
  no `depth`, so the guide requires one. That belongs to the Git child.
  `workflows/_index.md` is a link list and needs none.
- **No workflow page is dirty right now** (`git status` is clean under
  `website/`). `contribution-flow.md`, dirty at planning time, is clean now.
  The shared-file gate still runs before every edit.
- **Coordination with in-flight work:**
  - t2284 (Implementing) owns the `crash-recovery.md:71` re-claim wording.
    The Parallel-local child must not change that sentence while t2284 is open.
  - Another session holds uncommitted shadow-agent changes
    (`aidocs/framework/shadow_agent.md` and `monitor/*`). The Review & Quality
    child re-checks `workflows/shadow-agent.md` against those changes before
    editing.
- **Pages that received facts from t2258_3** (note, acknowledged) are
  `crash-recovery`, `parallel-development`, `freeze-and-restore-agents` and
  `task-notes`. Their audits use the pilot plan's moved-fact table as the
  source record. `task-notes` is in this child.
- **Pilot lessons that apply here:**
  - the detail-placement boundary (behaviour detail → reference or workflow
    page; public architecture → `development/`; contributor-only →
    `aidocs/`);
  - check a fact against the code before moving it;
  - check survival claim by claim with an independent agent, not by token
    grep;
  - `tests/lib/docs_vocabulary_scan.py` reads every table row in
    `development/task-format.md` as a frontmatter field;
  - never pipe a generated file through `tee | head`.
- **No fresh-reader runs in this child.** All 12 of its pages are
  `intermediate`, so the skill reports `not-run(not-beginner)`, and
  `--budget 0` applies. t2258_8 samples restructured pages from children 4+
  for its after-tests.

## Section inventory (sizes, measured at 7f1f4333a) and owner

h2/h3 = `##`/`###` counts; fences = code-fence lines. Verdicts for this child's
pages are written in Step 1. Every other child writes its own.

| Group → owner | Page | Lines | depth | h2/h3 | fences |
|---|---|---|---|---|---|
| Tasks → **t2258_4** | bug-report-intake | 336 | intermediate | 8/2 | 22 |
| | retroactive-tracking | 167 | intermediate | 7/0 | 8 |
| | create-tasks-from-code | 160 | intermediate | 6/0 | 4 |
| | premise-staleness | 119 | intermediate | 9/0 | 4 |
| | task-notes | 107 | intermediate | 6/3 | 4 |
| | follow-up-tasks | 84 | intermediate | 9/0 | 0 |
| | exploration-driven | 77 | intermediate | 5/0 | 2 |
| | task-consolidation | 43 | intermediate | 4/0 | 0 |
| | task-decomposition | 35 | intermediate | 3/0 | 0 |
| | capturing-ideas | 27 | intermediate | 0/0 | 0 |
| Reporting → **t2258_4** | work-report | 90 | intermediate | 5/0 | 6 |
| Maintenance → **t2258_4** | repo-maintenance | 88 | intermediate | 6/0 | 8 |
| Parallel (local) → new child A | freeze-and-restore-agents | 316 | intermediate | 8/0 | 6 |
| | crash-recovery | 188 | intermediate | 8/6 | 4 |
| | implementation-trails | 162 | advanced | 8/1 | 4 |
| | sitrep | 133 | intermediate | 12/0 | 4 |
| | parallel-planning | 76 | advanced | 5/0 | 2 |
| | parallel-development | 75 | advanced | 7/0 | 0 |
| Parallel (cross-project, remote) → new child B | cross_project_dependencies | 236 | advanced | 9/8 | 22 |
| | multi_project | 216 | advanced | 9/2 | 16 |
| | claude-web | 163 | advanced | 6/7 | 16 |
| Review & Quality → new child C | manual-verification | 256 | intermediate | 11/7 | 12 |
| | shadow-agent | 249 | intermediate | 5/13 | 6 |
| | upstream-defect-followup | 133 | intermediate | 11/0 | 10 |
| | qa-testing | 119 | intermediate | 6/2 | 6 |
| | explain | 104 | intermediate | 6/0 | 4 |
| | risk-evaluation | 99 | intermediate | 8/3 | 4 |
| | code-review | 88 | intermediate | 5/0 | 4 |
| Git → new child D | contribute-and-manage/contribution-flow | 235 | advanced | 7/10 | 12 |
| | pr-workflow | 152 | advanced | 6/5 | 14 |
| | contribute-and-manage/_index | 149 | **none** | 5/4 | 10 |
| | releases | 142 | advanced | 6/6 | 10 |
| | revert-changes | 116 | advanced | 7/3 | 0 |
| | issue-tracker | 27 | advanced | 2/0 | 2 |
| Screen Recordings → new child E | animation | 138 | intermediate | 11/0 | 8 |
| | bug-report | 93 | intermediate | 9/0 | 4 |
| | pick-frames | 89 | intermediate | 7/0 | 6 |
| | hand-edited-images | 83 | intermediate | 7/0 | 8 |
| | image-sequences | 81 | intermediate | 6/0 | 10 |
| | exact-frames | 72 | intermediate | 7/0 | 4 |
| | hang-black-silence | 71 | intermediate | 6/0 | 4 |
| | _index | 64 | intermediate | 6/0 | 2 |
| | recording-tips | 64 | intermediate | 5/0 | 2 |
| Section index → each child edits its own group's list | _index | 89 | — (link list) | 7/0 | 0 |

## Steps

### Step 0 — Create the five sibling children and rewire the chain (first, so the split is durable)

1. Create each child with `aitask_create.sh --batch --commit --parent 2258
   --no-sibling-dep --deps <prev>`, type `documentation`, priority `medium`,
   labels `documentation,web_site,doc_quality`. The fast profile adds
   `--gates risk_evaluated`. Use the existing deps format (`t2258_4`); check it
   on the first creation with `grep '^depends:'`.

   | Child | Name | Effort | deps |
   |---|---|---|---|
   | A | `audit_workflows_parallel_local` | high | t2258_4 |
   | B | `audit_workflows_cross_project` | medium | A |
   | C | `audit_workflows_review_quality` | high | B |
   | D | `audit_workflows_git` | medium | C |
   | E | `audit_workflows_screen_recordings` | medium | D |

   Each description is self-contained for a fresh session and includes:
   - **Context:** child of t2258, split from t2258_4 at its planning, with the
     reason.
   - **Pages:** its rows of the inventory table above, with lines and depth.
   - **Method:** the binding seven-step method copied from the t2258_4 task
     body, with `aitask-docs-review` named correctly.
   - **Read first:** the parent task and plan, the archived plans of t2258_3
     and t2258_4 (and any earlier split sibling), and the guide sections.
   - **The `_index.md` rule:** edit only its own group's list in
     `workflows/_index.md`, and add a bullet for any new or split page.
   - **Coordination:** A gets t2284 / `crash-recovery.md:71` and the t2258_3
     moved facts; C gets the in-flight shadow-agent work; D gets
     `contribute-and-manage/_index.md` (needs `depth`) and the shared-file gate
     on `contribution-flow.md`; E runs the section-wide `depth` check as the
     last workflows child.
   - **Ledger:** use the child's own `audit_deferred_pages_workflows_<group>`
     name for any deferred-page follow-up.
   - **Verification:** as in this task.
2. Write a short plan for each at `aiplans/p2258/p2258_<n>_<name>.md`, shaped
   like the existing pending sibling plans, and commit all five plan files by
   name with `./.aitask-scripts/aitask_task_commit.sh`.
3. Rewire t2258_5 so it runs after the last workflows child:
   `aitask_update.sh --batch 2258_5 --deps t2258_<E>`. t2258_8 already waits
   transitively through 7 → 6 → 5.
4. Check the graph:
   - `grep '^depends:'` on every t2258 child;
   - `./.aitask-scripts/aitask_ls.sh -v --children 2258 99` shows only t2258_4
     unblocked;
   - `children_to_implement` on the parent lists the five new ids.
5. Notes, via the `/aitask-note` pieces (`./ait note … --from 2258_4`):
   - **t2258_8:** the workflows audit is now children 4 and 9–13. Its
     ledger reconciliation and its reader-test sample must cover them.
   - **t2258_5:** it now depends on the last workflows child, and why.
6. Update the parent plan's child table with one appended note row listing the
   new children (task-data commit, by path).

### Step 1 — Inventory verdicts for this child's 12 pages

Add a table to this plan with these columns: page, lines, depth before → after,
verdict (ok / minor / restructure), violations. Check in this order:
1. Diátaxis anti-patterns 1, 2 and 5, then 3 and 4.
2. The `intermediate` contract. It allows flags, config keys, files the user
   edits and visible timing. It excludes status lines and vocabularies, exit
   codes, internal paths and outcome tables.
3. The how-to shape: goal, steps, outcome.
4. The prose avoid list.

The signal counts measured at planning:

| Page | table rows | internal paths | status lines | em dashes | bold spans | script names |
|---|---|---|---|---|---|---|
| bug-report-intake | 39 | 14 | 0 | 28 | 59 | 0 |
| retroactive-tracking | 7 | 1 | 0 | 23 | 53 | 5 |
| create-tasks-from-code | 10 | 6 | 2 | 22 | 26 | 16 |
| premise-staleness | 14 | 0 | 0 | 21 | 35 | 0 |
| task-notes | 11 | 0 | 1 | 16 | 18 | 0 |
| follow-up-tasks | 0 | 0 | 0 | 23 | 18 | 0 |
| exploration-driven | 6 | 0 | 0 | 14 | 18 | 4 |
| work-report | 0 | 0 | 0 | 16 | 18 | 0 |
| task-consolidation | 0 | 0 | 0 | 9 | 7 | 0 |
| capturing-ideas | 0 | 0 | 0 | 7 | 7 | 0 |
| task-decomposition | 0 | 1 | 0 | 4 | 2 | 0 |
| repo-maintenance | 0 | 3 | 0 | 4 | 1 | 0 |

Already known restructures: `bug-report-intake` and `create-tasks-from-code`.

### Step 2 — Shared-file gate before every edit

Run `git diff --quiet HEAD -- <page>` and `git status --short -- <page>` on
both the source page and each destination page. A page that is dirty from
another session is not edited. It goes into the **skipped-page ledger** in
this plan with its path, the reason and the dirty state seen. When the dirty
page is a destination, its facts stay on the source page until close-out.

### Step 3 — Restructure, longest first

**Rules for every move:**
- Check the owner page before moving anything.
- Check each moved fact against the code.
- Record every move in the **moved-fact table**:
  source#section → fact → destination#anchor → `moved` / `already-stated` /
  `corrected` / `dropped(reason)`.
- Use `relref` for every new internal link.
- Each page ends as a how-to: goal, numbered steps, outcome, then a short
  "Details" section or links to the reference.

**`bug-report-intake.md` (336 lines).** The page mixes overview, setup,
reference and troubleshooting (AP5). Setup is written twice, in Prerequisites
plus Configure plus Run, and again in the Walkthrough, which includes the
token block twice.
- **New `commands/chatlink.md`** (reference, `advanced`; title, description
  and weight follow its neighbours; add an entry to `commands/_index.md` if
  that list is hand-curated). It gets:
  - `ait chatlink` / `--headless` usage;
  - the full config-key table with defaults and ranges;
  - the authorization precedence and deny-all rules;
  - clamping and the malformed-YAML refusal;
  - the token file's path and modes;
  - the preflight refusal list;
  - the audit-log path;
  - the sandbox ceilings and when they are enforced;
  - the status TUI's keys (`r`, `q`, `j`). No TUI reference page exists for
    these, so they go on the closest reference page, and t2258_5 gets a note;
  - the troubleshooting table;
  - the `aidocs/chat/chatlink_sandbox.md` pointer. It is an internal path,
    excluded at `intermediate`.
- **The workflow page keeps:**
  - what the gateway is for and the flow diagram;
  - one numbered procedure merging Prerequisites, Configure, Run and the
    Walkthrough: tier, image, bot with both intents, a minimal config, token,
    start, file a bug;
  - what the reporter sees, shortened, with the reaction legend kept as a
    short list;
  - limits and safety in short bullets;
  - links to the reference for every key and symptom.
- **Prose:** cut decorative bold and most em-dash connectors.

**`create-tasks-from-code.md` (160 lines).** It mixes field reference,
internals and script chains with the how-to (AP5). It has
status lines (`TASK:<id>:<file>`), internal paths and function names.
- `file_references` syntax rules (regex, order kept, exact-string dedup) go to
  `development/task-format.md` § frontmatter fields. Most are already stated
  there; add only what is missing. Mind the vocabulary-scan trap: do not add a
  table row.
- The codebrowser selection-fallback table goes to the codebrowser TUI
  reference page.
- The board File Refs dispatch table goes to `tuis/board/reference.md`.
  `launch_or_focus_codebrowser` and its file path are contributor-only: move
  them to `aidocs/` if no aidocs page states them, otherwise drop with a
  reason.
- `--auto-merge` behaviour goes to `commands/task-management.md` at the
  `--file-ref` / `--auto-merge` flags: candidate status filter, path-only
  matching, the default warn-and-skip and the exact-string union of refs.
- **`aitask_find_by_file.sh` is public, so it stays on the site.** The
  workflow tells users to call it, and its `--help` documents its output for
  callers. That makes it a script an integrator is meant to call (public
  architecture), not private detail. Its contract has no other site page, and
  `ait` has no dispatcher verb for it. So add a short section to
  `development/task-format.md` (`advanced`, already the owner of
  `file_references`), named "Finding tasks by file reference", placed after
  the frontmatter fields. It covers:
  - `aitask_find_by_file.sh [--project <name>] <path>`;
  - one `TASK:<task_id>:<task_file>` line per match, and no output when
    nothing matches;
  - path-only matching (line ranges and multi-range suffixes are stripped);
  - only `Ready` / `Editing` tasks are returned;
  - exit codes `0` (success), `1` (missing or invalid argument) and `2`
    (`file_references` unreadable: no usable python/PyYAML).

  Write it as prose plus a code block, with **no table row** (the
  vocabulary-scan trap). Verify each item against the script before writing.
  The `file_references` row and the workflow's CLI example both link to this
  section.
- Only the internal fold chain (`aitask_fold_validate.sh` →
  `aitask_fold_content.sh | aitask_update.sh` → `aitask_fold_mark.sh`) is
  contributor-only. It goes to `aidocs/`, or is dropped with a reason where
  aidocs already states it.
- The page keeps:
  - steps for the `n` flow in the codebrowser, with `--auto-merge` as an
    option;
  - the board return trip;
  - CLI examples that use `ait` verbs where a dispatcher verb exists (checked
    in `ait`), otherwise the script names;
  - See also.

**The other ten pages, in size order:** retroactive-tracking,
premise-staleness, task-notes, work-report, repo-maintenance, follow-up-tasks,
exploration-driven, task-consolidation, task-decomposition, capturing-ideas.
Apply the Step 1 violations to each. For `premise-staleness`, check its
answer/limit tables against the `intermediate` outcome-table rule. A table
that is reference material moves to the owning reference page
(`development/task-format.md#…` for `premise_baseline`, or a skill page).
Same gate, same table.

Keep each page's position in `workflows/_index.md` and its `**Next:**` footer.
If a page is split or added, add its bullet to the right group.

### Step 4 — Feed lessons into the guide (last planned guide change)

Make short additions to existing guide sections, only for what this child
showed. Candidates:
- a how-to page that repeats its setup in a walkthrough;
- a troubleshooting table as a reference block inside a how-to.

Keep `## Reader levels` interface lines byte-identical and prose-rule bullets
single-line. Run `bash tests/test_docs_review_contract.sh`. The guide lives on
the task-data branch; commit it by path with `aitask_task_commit.sh`.

### Step 5 — Final level/prose review under the final guide

Run `/aitask-docs-review <every page edited or created> --caller audit
--budget 0`. This covers the 12 workflow pages plus every destination page and
`commands/chatlink.md`. Fix the findings within the skill's invariants: a fix
that cuts a fact gets a moved-fact row. Re-review each page a fix changed.
Record each page's `level=… prose=… reader=…` line and its unresolved findings
in this plan. If the guide changes again, re-run this step on every edited page.

### Step 6 — depth

Check that every leaf page this child edited or created has `depth:`. Also run
the section-wide check and record its result:
`grep -L '^depth:' $(find website/content/docs/workflows -name '*.md' ! -name _index.md)`
plus the two content `_index.md` pages. Today the only gap is
`contribute-and-manage/_index.md`, which is owned by child D.

### Step 7 — Links

- Run `cd website && python3 check_links.py --build`. It must exit 0.
- Run `python3 check_link_relevance.py`. Open every reported target this child
  added or retargeted, and record a verdict for each.
- Run `bash tests/test_website_doc_lists.sh`, because a new commands page may
  touch doc lists.

### Step 8 — Ledger close-out

Re-check every ledger entry against HEAD:
- **Now clean:** audit the page here (Steps 3–7 for that page).
- **Still dirty:** create a child of t2258 with `--no-sibling-dep`, named
  `audit_deferred_pages_workflows_tasks`, listing the pages, their violations
  and the reason they were skipped.

The Final Implementation Notes record each entry's outcome (`audited` /
`follow-up t2258_<n>`), or "ledger empty".

### Post-phase (risk mitigations)

1. [moved_fact_survival_check] The pilot's claim-level survival check, run
   before the commit.
   a. A scratchpad script splits `git show HEAD:<page>` and the working text
      of every page this child cut text from into blocks: paragraph, list
      item, table row, admonition, code block. It lists every HEAD block not
      present byte-for-byte in the working version. Write output files
      directly, never through `tee | head`.
   b. A fresh sub-agent, not the editor, gets for each source page:
      - the removed blocks, verbatim;
      - the full current text of the source page and of every destination
        its moved-fact rows name.

      It lists every claim (rule, condition, exception, consequence, scope,
      default) and classifies each as `preserved` (with a quote and
      page#section), `weakened` or `missing`.
   c. Fix every `weakened` or `missing` claim. If it is not restored, record
      it as `corrected` (with code evidence) or `dropped(reason)`. A token
      grep is supporting evidence only.
   d. Re-run the sub-agent once on the fixed claims. Record per page: claims,
      preserved, fixed, corrected, dropped, and the second-run result.
   e. A page changed in (c) goes back through Step 5 and Step 7.

## Verification

- This plan holds the inventory (sizes for all 44 pages, verdicts for this
  child's 12), the moved-fact table, the survival-check counts and the ledger
  outcomes.
- The five new children exist with the deps chain 4 → A → B → C → D → E → 5,
  checked by `aitask_ls.sh -v --children 2258 99` and `grep '^depends:'`.
- `check_links.py --build` exits 0. `test_docs_review_contract.sh` and
  `test_website_doc_lists.sh` pass.
- Every leaf page in this child's groups has `depth:`. The section-wide
  `depth` result is recorded.

## Risk

### Code-health risk: medium
- A restructure can lose a rule, condition or exception while moving
  bug-report-intake and create-tasks-from-code facts to five other pages ·
  severity: low (residual — addressed by inline post-phase
  moved_fact_survival_check) · → mitigation: inline post-phase
  moved_fact_survival_check
- The new `commands/chatlink.md` and the edits to TUI, command and
  development pages land on pages owned by later siblings (t2258_5/6/7). This
  is bounded by the shared-file gate and by notes to those children ·
  severity: low · → mitigation: none
- Wrong `--deps` on a new child could unblock t2258_5 or a workflows child
  early. Step 0.4's graph check catches this · severity: low · → mitigation:
  none

### Goal-achievement risk: medium
- A split child created here can lack context for a fresh session and audit
  its group differently. Each description carries the full method,
  inventory rows and coordination items · severity: medium · → mitigation:
  none (covered by Step 0.1's description contents)
- A moved fact can be outdated, and copying it would make it look
  authoritative. Each moved fact is checked against the code, and wrong
  facts are recorded `corrected` · severity: low · → mitigation: inline
  post-phase moved_fact_survival_check

### Planned mitigations
- timing: post-phase | name: moved_fact_survival_check | type: test | priority: medium | effort: medium | inline_risk: low | added_complexity: low | addresses: code-health restructure fact loss; goal-achievement stale moved facts | desc: claim-level comparison of every removed block with its destination by an independent sub-agent, before commit

## Post-implementation

Step 9: review; commit website and `aidocs/` files as
`documentation: Audit and restructure the Tasks workflow pages (t2258_4)`;
commit the guide and plan files by path with `aitask_task_commit.sh`; archive.

Step 8e notes, sent when the facts hold at the end:
- t2258_5: the chatlink TUI keys now on `commands/chatlink.md`, and the
  codebrowser and board reference pages that received facts;
- t2258_6: the new `commands/chatlink.md` and the `commands/task-management.md`
  `--auto-merge` facts;
- t2258_7: the new `development/task-format.md` § "Finding tasks by file
  reference" (`aitask_find_by_file.sh` contract) and any other task-format
  additions.
