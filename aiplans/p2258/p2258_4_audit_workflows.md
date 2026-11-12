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

#### Step 1 result — inventory verdicts (measured at 7f1f4333a, before any edit)

Type: every page is a how-to (it sits under `workflows/`). AP = Diátaxis
anti-pattern (1 tutorial that explains, 2 how-to that teaches, 3 reference as
narrative, 4 explanation with procedures, 5 mixed page). "Level" means the
`intermediate` contract.

| Page | Lines | depth (before → after) | Verdict | Violations |
|---|---|---|---|---|
| `bug-report-intake` | 336 | intermediate → intermediate | **restructure** | AP5: overview, setup, a config-key reference table (15 rows), authorization rules, the token file, preflight refusals and a 14-row troubleshooting table on one page. Setup is written twice (Prerequisites/Configure/Run, then the Walkthrough, with the token block repeated). Level: internal paths (`aitasks/metadata/chatlink_sessions/…`, `aidocs/chat/chatlink_sandbox.md`, the audit log path), an outcome table (troubleshooting). Prose: 59 bold spans, 28 em dashes. |
| `create-tasks-from-code` | 160 | intermediate → intermediate | **restructure** | AP5: the `file_references` syntax reference (validation regex), fold-chain internals (`aitask_fold_*` calls) and the board launcher's function name and file path inside a how-to. Level: status lines (`TASK:<id>:<file>`), internal paths, two outcome tables (selection fallback, File Refs dispatch). Prose: decorative bold, 22 em dashes, "The real leverage". |
| `premise-staleness` | 119 | intermediate → intermediate | **restructure** | AP3/AP5: it reads as reference, not a how-to. It has two outcome tables (six evidence classes; four answers → effect → baseline), baseline-advance edge rules, and internal detail at `intermediate` (`AIT_AGENT_PID`, `aitasks/new/`, lock-proof requirement). No page owns this behaviour detail, so it gets a focused `development/` reference page. |
| `retroactive-tracking` | 167 | intermediate → intermediate | **restructure** (condense) | AP2: four walkthroughs repeat the same three steps (launch, review, execute) and teach rather than direct. Examples use the framework's own scripts (`aitask_ls.sh`, `aitask_lock.sh`); one gives a wrong path, `.aitask-scripts/lib/aitask_lock.sh`. Prose: "The philosophy" bold line, 53 bold spans, 23 em dashes, the closing restatement "Both workflows produce the same artifacts…". |
| `task-notes` | 107 | intermediate → intermediate | minor | Level: status lines (`LIVE_NONE:remote_host`, `LIVE_NONE:holder_dead`); "Where notes surface" is an outcome table. Prose: decorative bold ("That is a success."). |
| `work-report` | 90 | intermediate → intermediate | minor | Prose: a bold "key insight" paragraph (inflated importance, "correct by construction"), em-dash connectors. Steps and level are fine. |
| `repo-maintenance` | 88 | intermediate → intermediate | minor | Prose: "This page gathers the recurring maintenance commands in one place" (writing about the page). Level: internal cache path `.aitask-explain/`. |
| `follow-up-tasks` | 84 | intermediate → intermediate | minor | Level: internal workflow step numbers ("Step 8b", "Step 8c"). Prose: "simply", "far more effective", the inflated advantages list, bold emphasis. |
| `exploration-driven` | 77 | intermediate → intermediate | minor | The walkthrough uses the framework's own `aitask_ls.sh` as the user's project; the guide wants generic examples. Prose: "The philosophy" bold line, em dashes. |
| `task-consolidation` | 43 | intermediate → intermediate | minor | Prose: a staged contrast ("conceptually the opposite … but serves a different purpose: decomposition splits … while consolidation merges …"), bold emphasis. |
| `task-decomposition` | 35 | intermediate → intermediate | minor | Level: internal path `aiplans/archived/p<parent>/`. Prose: "controlled, disciplined execution". |
| `capturing-ideas` | 27 | intermediate → intermediate | minor | Prose: "The most important thing", "The philosophy" bold line, the closing line "The framework handles progressive refinement at each stage". Level: internal path `aitasks/new/`. |

All 12 pages keep `intermediate`: the reader of each is someone who has
already taken a task from pick to archive. No retags.

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

## Moved-fact table

Step 3 was drafted by four restructure agents working in parallel on disjoint
file sets, each with a shared written brief (scratchpad `restructure_brief.md`;
its rules are the guide's, summarised), and then reviewed in this session. Each
agent's report is reproduced below: files changed, moved-fact table,
code-verified corrections and open points.

### Restructure report: `premise-staleness.md` + `retroactive-tracking.md`

**Files.**
- `workflows/premise-staleness.md` was rewritten as an `intermediate` how-to:
  a short opening; "When you see the prompt"; "Answering the prompt" (the four
  answers as a list); opting in and out (command blocks unchanged); a one-line
  "Unattended runs"; the `verification_baseline` note; and Related. The
  `#opting-a-task-in` and `#unattended-runs` anchors are kept. No page links to
  a `premise-staleness#` anchor.
- NEW `development/premise-staleness.md`, "Premise Staleness Rules",
  `advanced`, weight 15. Sections: Which tasks it evaluates, Evidence (table),
  Answers and the baseline (table), Rules that shape the answers, Unattended
  runs, Limits.
- `workflows/retroactive-tracking.md` was condensed: a goal, one five-step
  procedure, four one-line cases with generic files, the Wrap-vs-Create table,
  and four tips. Touched links use relref.
- `development/_index.md` is not a page list, so it was not edited.
  `skills/aitask-wrap.md` was not needed.

**Moved facts — premise-staleness** (source → destination → outcome):
- The intro facts (premise definition, advisory nature, a clean result only
  means the watched files did not change) stay in the workflow intro: moved.
- When it runs:
  - the entry routes and conditions → workflow "When you see the prompt"
    (short) and dev "Which tasks it evaluates" (full): moved;
  - the silent skips → dev: **corrected**. It skips when the baseline is not an
    *ancestor* of the checked commit (`aitask_premise_stale.sh:432`,
    `history_rewritten`). Also added: invalid baseline, invalid YAML,
    unresolvable scope, all files retired;
  - silent when nothing changed → dev: moved;
  - pickrem/pickweb do not run the check → both pages: moved.
- What it compares:
  - committed history only → both pages: moved;
  - the six evidence rows → dev "Evidence": moved. The Deleted row is
    **corrected**: it names the culprit task and the commit subject
    (`aitask_premise_stale.sh:35`);
  - "never an all-clear" → dev: moved.
- The prompt:
  - the 10-row cap and the summarised rest → dev "Evidence": moved;
  - always asked under an interactive profile → dev "Answers and the
    baseline": moved;
  - the four answer rows → the workflow list (plain words) plus the dev table:
    moved. The replan advance also needs the plan's review of every row
    (added).
- The detail rules:
  - re-check under the lock, the baseline moves only to the commit shown,
    never-existed refs get a keep/remove question, unverifiable evidence
    blocks the advance, invalid refs cannot be cleared from the prompt → dev
    "Rules that shape the answers" (the workflow states two of them briefly):
    moved.
- Opting in and out: kept on the workflow page (the field link now carries
  `#frontmatter-fields`).
- Unattended runs → a workflow line plus dev in full (with the `headless: true`
  key): moved.
- Limits:
  - the no-backfill, no-time-verdict, change-not-behaviour and
    invalid/never-existed ref rules → dev "Limits": moved;
  - session identity / `AIT_AGENT_PID` → dev "Limits": moved. Added: the lock
    must name this email, host and session; a lock with no session anchor also
    blocks;
  - draft stamping → the workflow (first half) and dev (the `aitasks/new/`
    path): moved.
- Added on dev, each verified:
  - an answer is void if the scope or baseline changed between the prompt and
    the write;
  - removal is impossible when the list holds an invalid entry, though the
    baseline still advances;
  - line ranges are ignored, and `file_references` wins over `verifies`.

**Moved facts — retroactive-tracking:**
- The four situations → "When you need it", one line each with its tip: moved.
- "The philosophy: never lose traceability": dropped (a saying; the goal
  states the outcome).
- The quick-fix walkthrough:
  - detection summary, file choice, analysis fields, then task, plan, commit,
    archive and push → procedure steps 1–5: moved;
  - "appears in changelogs, searchable" → goal: moved;
  - "can be linked to issues": dropped (a wrap creates no issue link;
    SKILL.md 4d);
  - the `aitask_ls.sh` example: dropped (a framework script used as the user's
    project; a generic example replaces it).
- The debugging walkthrough:
  - a fix plus its test → choose all changes (debugging case): moved;
  - the `.aitask-scripts/lib/aitask_lock.sh` path: dropped (wrong path, and a
    framework example);
  - "priority high inferred": dropped (example colour; the skill defaults to
    medium);
  - the plan documents the problem, fix and test → Tips and the case: moved.
- Config and pair-programming walkthroughs:
  - version numbers, file counts and example metadata: dropped (example
    colour);
  - record versions and migrations; wrap unrelated changes separately, main
    change first; review the name and labels on large diffs: moved.
- Option labels **corrected**: "All changes", not "Include all changes"
  (`aitask-wrap/SKILL.md.j2:45`); "Adjust task name or metadata", not "Adjust
  metadata" (`:150`).
- Wrap vs Create:
  - table kept;
  - the decision guide is already stated by the table rows;
  - explore-first → one line;
  - "Both workflows produce the same artifacts…": dropped (a closing
    restatement, and inaccurate: create outputs only a task file).
- Tips kept; "one concern per wrap" → the pair-programming case.
- Added, verified (SKILL.md.j2:18–20, 149, 198–200): run from the project
  root; it stops if there is nothing to wrap; the confirmation labels.

**Checked against the code:**
- 10-row cap: `task-workflow/premise-staleness.md:73–75`.
- Six classes, all `ASK_STALE`; retired files are not evidence:
  `lib/task_premise.py:128–135, 602–647`.
- No advance on unverifiable rows: `aitask_premise_stale.sh:784–786, 866`.
- `AIT_AGENT_PID`: `:729–736`.
- Headless display-and-continue: task-workflow SKILL.md:149, and
  `remote.yaml:3`.
- Stamping only at create/finalize: `aitask_create.sh:166, 868–935` and
  `aitask_update.sh:2239–2245`.
- Carry-over inheritance: `aitask_archive.sh:971–1003`.

**Leftovers for other children:**
- `skills/aitask-wrap.md`: relative links, an em-dash-heavy capability list, a
  duplicated When-to-Use table (t2258_6).
- `skills/aitask-pick/_index.md:28` lists the premise evidence classes at
  `intermediate`; it could link to `development/premise-staleness#evidence`
  (t2258_6).
- The `task-format` `premise_baseline` row could point at the new dev page.

**Links:** no broken link in its files.

### Restructure report: the eight minor pages

**Files.** Each page got a prose pass against the avoid list: decorative bold,
em-dash connectors and puffery removed, and body links moved to relref.
`**Next:**` footers are unchanged.
- `task-notes`: the `LIVE_NONE:` tokens are now plain words (the `#output` link
  is kept); the "Where notes surface" table is now a prose list.
- `work-report`: the bold "key insight" paragraph is now one plain sentence.
- `repo-maintenance`: the "This page gathers…" paragraph is cut; the internal
  paths are now plain words.
- `follow-up-tasks`: "Step 8b/8c" are now plain words; the `codebrowser.py`
  example is now a generic `FileViewer.tsx`.
- `exploration-driven`: the `aitask_ls.sh` walkthrough is now a generic
  `list_orders` endpoint; the mode labels are unchanged.
- `task-consolidation`: the staged contrast is now a pointer.
- `task-decomposition`: the internal path is now "the archived plans of the
  finished siblings".
- `capturing-ideas`: the sayings and closing lines are cut; `aitasks/new/` is
  now "a local draft that is not committed".
- `skills/aitask-note.md` and `commands/note.md` did not need edits.

**Moved facts:**
- task-notes:
  - `LIVE_NONE:remote_host` / `holder_dead` → `commands/note#output`:
    already-stated (note.md:158–159), plain words kept;
  - "a success, don't resend": already-stated (note.md:136), kept in prose;
  - "optimisation, not the product": dropped (rhetoric; the inbox fact is
    kept);
  - the four surface-table rows (pick named, other routes, pickrem auto,
    pickweb never; every route shows): kept in place as prose;
  - "context, not a payload": already-stated (note.md:50), the 8192-byte limit
    is kept.
- work-report:
  - "board encodes priorities": already-stated (§ Why report from the board);
  - "correct by construction…": dropped (a saying);
  - "Two guardrails keep it honest" and the guardrail labels: dropped
    (rhetoric; both facts kept).
- repo-maintenance:
  - "This page gathers…": dropped (writes about the page);
  - the archive, `.aitask-explain/`, `aitask-data` and `.aitask-data` paths:
    already-stated (`commands/issue-integration#ait-zip-old`,
    `commands/explain#ait-explain-runs`, `commands/sync#ait-git-health`);
  - "git-health reports the symlinks": **corrected**.
- follow-up-tasks:
  - "far more effective": dropped;
  - "Step 8b": already-stated (upstream-defect-followup.md:11);
  - "Step 8c": already-stated (the `manual-verification#post-implementation-follow-up-step-8c`
    link is kept);
  - the `codebrowser.py` example: dropped (framework code as the user's
    project; now a generic example);
  - the advantages labels: dropped (puffery; every fact kept).
- exploration-driven:
  - the philosophy line: merged into the intro;
  - the `aitask_ls.sh` internals: dropped (framework example);
  - "cleaned up after implementation": **corrected** to "removed when the new
    task is archived".
- task-consolidation: the decomposition/consolidation staged contrast:
  dropped, now a pointer.
- task-decomposition:
  - "controlled, disciplined execution": already-stated (sibling context);
  - `aiplans/archived/p<parent>/`: already-stated (development/task-format,
    "Archived Sibling Plans").
- capturing-ideas:
  - the philosophy line: already-stated;
  - drafts under `aitasks/new/`, gitignored: already-stated
    (task-management.md:15, 31, 82);
  - "saved as a local draft": **corrected**;
  - "drag tasks": **corrected**;
  - "never need perfect descriptions": already-stated;
  - "framework handles progressive refinement": dropped (closing
    restatement).

**Corrections, checked against the code:**
- git-health does not inspect symlinks. It prints the mode, worktree, git-dir,
  branch and HEAD, and warns on a detached HEAD or an in-progress operation
  (`lib/task_utils.sh:513-558`).
- Folded originals are deleted at archival (`aitask_archive.sh:45-52, 94`).
- Saving a draft is optional: the prompt offers "Finalize now" or "Save as
  draft" (task-management.md:26; `aitask_create.sh:161-172`).
- The board moves cards with Shift+Left/Right; there is no drag
  (`tuis/board/how-to.md:15`; a grep of `aitask_board.py` finds none).

**Verified, no change needed:**
- the explore mode labels and defaults (`aitask-explore/SKILL.md.j2:26-72`);
- `explore_auto_continue` (`SKILL.md.j2:347`, `fast.yaml:15`);
- parent auto-archival (`aitask_archive.sh:770-833`);
- drafts are gitignored (`.aitask-data/.gitignore:2`; `aitask_create.sh:70`);
- note acknowledgement per route (the pick, pickrem and pickweb skill
  templates and task-workflow Step 3);
- live delivery is Claude Code only (`live_delivery/claudecode.md`);
- fold discovery (`related-task-discovery.md:55-56`);
- archived sibling plans are the primary reference (`planning.md:242`).

**Leftovers for other children:**
- `upstream-defect-followup.md` uses "Step 8b/8c" and relative links (t2258_11).
- `manual-verification.md` has the heading "Post-Implementation Follow-up
  (Step 8c)". Renaming it changes the anchor follow-up-tasks links to
  (t2258_11).
- `/aitask-explore`'s free-text "Other" goal (defaults feature/medium) belongs
  on `skills/aitask-explore.md` (t2258_6).
- `commands/note.md` is tagged `intermediate` but carries status codes and
  outcome tables, so it probably wants `advanced` (t2258_6).
- "sibling project" wording: left, because the multi_project anchor depends on
  it (t2258_10).

**Unclear guide rules:**
- bold lead-ins on list items;
- walkthrough labels ("You ask:");
- whether the "You learned… / Use" routing table counts as an outcome table.

**Links:** `check_links.py --build` passed (0 broken).

### Restructure report: `create-tasks-from-code.md`

**Files.**
- `workflows/create-tasks-from-code.md` is now an intermediate how-to: a goal,
  six steps for the codebrowser `n` flow (with `--auto-merge` as an option),
  an outcome paragraph, the board return trip, CLI examples using
  `ait create` / `ait update`, and a link to the find-by-file contract. It has
  0 em dashes.
- `development/task-format.md`:
  - the `file_references` row gains the `^` form, a dedup example, "order
    kept", the regex, and the control-char / UTF-8 refusal;
  - NEW `## Finding tasks by file reference` section (prose plus a code
    block, no table row): usage, `TASK:` output, Ready/Editing, path-only
    matching, `--project`, exit codes 0/1/2.
- `tuis/codebrowser/reference.md`:
  - the `n` row is corrected;
  - NEW "Creating a task from the viewer" (viewer state → `--file-ref` →
    dialog title table, pre-filled command, tabs, banner);
  - NEW "Opening a file at a line range".
- `tuis/board/reference.md`: NEW "Opening file references" (row display, a
  0/1/2+ table, tmux window reuse, the no-session warning, "last request
  wins"), and a "File Reference Picker" row in Modal Dialogs.
- `commands/task-management.md`: `--auto-merge` / `--no-auto-merge` rows; the
  `^` form on the `--file-ref` rows; NEW `### Folding tasks that reference the
  same files`.
- NEW `aidocs/framework/file_references_flow.md` (contributor-only):
  `run_auto_merge_if_needed` and the fold chain; the board → codebrowser focus
  handoff; how `n` builds the ref.

**Moved facts** (source → destination → outcome):
- "This workflow ties together" list: dropped (writes about the page).
- The field syntax:
  - forms, 1-indexed, dedup → task-format: already-stated (example and `^`
    meaning moved);
  - order kept, regex → task-format: moved (`lib/task_utils.sh:3854`; added
    the control-char / UTF-8 checks at :3844-3852).
- The codebrowser flow:
  - "a single cursor line is used as fallback" → **corrected**: no
    multi-line selection means the whole file;
  - dialog title → codebrowser reference: moved;
  - the pre-filled command → **corrected**: the path is absolute and
    shell-quoted (`codebrowser_app.py:1619, 1646`);
  - the run buttons → **corrected**: "Run in terminal" (Direct tab) and "Run
    in tmux" (Tmux tab, chosen window, default current;
    `agent_command_screen.py:524-526, 569, 671`);
  - the banner → codebrowser reference: moved;
  - the interactive create steps: already-stated (task-management
    `#ait-create`);
  - `file_references` committed and `premise_baseline` stamped: kept and
    verified (`aitask_create.sh:165-166`).
- The selection fallback table:
  - multi-line → codebrowser reference: moved;
  - one-line and cursor-only → **corrected** to `path:1-<last line>`; rows for
    an empty file and for no file open were added.
- Auto-merge:
  - "real leverage": dropped;
  - after-commit candidates, distinct stripped paths, path-only, Ready/Editing,
    children excluded, explicit opt-in, default warn-and-skip, Yes/No → fold,
    `Folded` + `folded_into`, exact-string union of refs (primary first) →
    task-management `#folding-tasks-that-reference-the-same-files`: moved;
  - `TASK:` output → task-format `#finding-tasks-by-file-reference`: moved;
  - the validator call and the fold chain → aidocs (the generic sequence is
    already in `task_relations.md`): moved;
  - the fzf prompt → **corrected**: it appears for any non-`--batch` run with
    a terminal and without `--auto-merge`, and the header has no "?"
    (`aitask_create.sh:2096-2106`).
- The board:
  - the steps: kept;
  - `(none)` dimmed, 0 → no-op, 2+ → picker → board reference: moved;
  - 1 entry → **corrected**: the cursor goes on the range's *last* line, and a
    multi-range collapses to min..max (`codebrowser_app.py:546, 647-655`);
  - the function path → **corrected** to `.aitask-scripts/lib/agent_launch_utils.py:2938`
    (moved to aidocs);
  - "else a fresh process" → **corrected**: with no project tmux session it
    warns and opens nothing (`board_detail_screen.py:888-893`); otherwise a
    new `codebrowser` tmux window (`agent_launch_utils.py:2966-2980`).
- The CLI:
  - "For power users": dropped;
  - examples: kept, converted to `ait` verbs (`ait:210, 212`);
  - the find_by_file example → a link: moved;
  - "safer in CI": dropped (advice);
  - repeatable `--file-ref` / `--remove-file-ref`: already-stated.
- See also tutorial wording: dropped (the link is kept).

**Verified:**
- the regex, shared by create:227 and update:395-396;
- the filter (`aitask_find_by_file.sh:98-107`);
- the validator reasons (`aitask_fold_validate.sh:73-107`);
- the union (`aitask_fold_mark.sh:237-251`);
- `find_by_file` help and exit codes (`:18-22, 124-131`);
- `test_docs_vocabulary_coverage.sh` passes 32/32.

**Leftovers for other children:**
- `tuis/codebrowser/how-to.md:113, 115, 119` and `tuis/codebrowser/_index.md:111`
  repeat the stale fallback (t2258_5).
- `tuis/board/how-to.md:365` has the 0/1/2+ cell and an inaccurate tmux claim
  (t2258_5).
- The `aitask_find_by_file.sh --help` says "sibling aitasks project".
- A stale comment at `aitask_create.sh:2030` says auto-merge runs only on
  `--batch --commit`, but `finalize_draft` also calls it (lines 1022, 1087).

**Links:** `check_links.py --build` passed (0 broken).

### Restructure report: `bug-report-intake.md`

**Files.**
- `workflows/bug-report-intake.md` is now a how-to:
  - a short purpose paragraph and the flow diagram;
  - ONE numbered procedure: chat tier, Docker + image, bot with both intents
    and the invite, a minimal config, commit the config, token, start, file a
    bug;
  - "What the reporter sees", shortened, with the reaction list;
  - short limits and safety bullets;
  - relref links to the reference.

  Bold went from 59 to 21 (step titles and on-screen labels). No prose em
  dashes remain.
- NEW `commands/chatlink.md` (`advanced`, weight 43). Sections: usage, Files,
  config keys, invalid values / clamping, authorization and posture warnings,
  ordered startup refusals with exit status, sessions, reporter refusals,
  sandbox ceilings, the status TUI and wizard, troubleshooting, and Internals
  pointers to `aidocs/chat/*`.
- `commands/_index.md`: an `ait chatlink` row in the Integration table.
- `aidocs/chat/*` was not edited: `chatlink_runtime.md` and
  `chatlink_sandbox.md` already state the internals.

**Moved facts** (source → destination → outcome):
- Intro, reporter never touches a terminal, diagram: kept in the workflow
  intro.
- Sandbox limits (no repo writes, no credentials, no token; proposal
  validated) → the workflow's limits section plus chatlink `#sandbox` and
  `#sessions`: moved.
- Prerequisites:
  - the tier, image build, no-Docker behaviour, image/mount pointer →
    workflow steps 1–2 plus chatlink `#startup-checks-and-refusals`,
    `#sandbox` and `#internals`: moved;
  - bot setup 3.1–3.5 (application, intents, token, invite scopes and
    permissions — checked against `live_check.py:43-68` — channel overwrites,
    Developer Mode IDs) → workflow step 3: moved;
  - "without Message Content messages arrive empty" → **corrected**: the
    gateway never starts with an intent off.
- Configure:
  - location, seeding, checked in → step 4 plus chatlink `#files`: moved;
  - every config-table row → chatlink `#configuration-keys`: moved, defaults
    and ranges verified (`config.py:28-48`); `sandbox_memory` gains its format
    `<n>[kmg]`;
  - `deny_message_mode` ephemeral → **corrected**: it arrives as a DM;
  - `repo_name` "used in audit and display output" → **corrected**: only the
    wizard summary uses it;
  - **`sandbox_env_passthrough` was missing → corrected (added)**. It is the
    only route a credential reaches the sandbox by, so the walkthrough as
    written could not work;
  - authorization rules and precedence → chatlink `#authorization`: moved
    (`policy.py:73-95`);
  - "preflight warns loudly" → **corrected**: the warning appears only in the
    TUI panel and wizard;
  - clamping and malformed YAML → chatlink `#invalid-values`: moved.
- Token: one block (the duplicate in the walkthrough was merged) → step 5 plus
  chatlink `#files`: moved; token modes verified (`paths.py:93-115`).
- Run it: the command and success line, the refusal list, the Docker warning,
  the status TUI keys → step 6 plus chatlink: moved. Added the `w` and `?`
  keys.
- Reporter sees:
  - the thread name (48 chars), questions (≤3 plus a confirmation), the
    `Answer…` dialog, pagination (>25 options, 24 per page), reporter-only
    answers, `*(answered)*`, the ~9-minute timeout (540 s), the success post →
    chatlink `#sessions` plus the workflow list: moved;
  - reactions → the workflow list plus chatlink: moved.
- Walkthrough 1–7: merged into steps 1–7, duplicates removed. The example
  question now matches the `render.py` format; "ephemeral while testing":
  moved.
- Limits:
  - deny-by-default, committed-HEAD copy, re-validation, secrets: moved;
  - "killed at deadline even if the gateway restarts" → **corrected**: if the
    gateway was down at the deadline, the kill happens at its next start
    (`lib/sandbox_launch.py:365-373, 413-421`);
  - audit path → chatlink `#files`: moved.
- Troubleshooting:
  - wizard live check and the 14 rows → chatlink `#status-tui` /
    `#troubleshooting` / `#startup-checks-and-refusals`: moved (exact strings
    and exit status 2 added);
  - rows 8–9 (intents) → **corrected**: the gateway exits at connect
    (`chat/discord_adapter.py:690-692, 756-767`; `daemon.py:750`);
  - rows 12–13 → **corrected**: shown only in `ephemeral` mode
    (`intake.py:192-206, 469-473`).
- New facts from the code:
  - the wizard `w` key and what it writes;
  - commit a hand-edited config;
  - the `chatlink.config` fallback;
  - thread messages never start a session;
  - channel membership is required, and bots are ignored;
  - a restart fails unfinished sessions;
  - the hourly rate counts finished sessions;
  - "This question has expired.";
  - the confirmation free-text rule;
  - Claude Code only, plus headless billing.

**Verified:**
- refusal strings and order (`preflight.py:245-356`, `daemon.py:696-727`);
- launcher exit 1 (`aitask_chatlink.sh:31-36`);
- the question cap and timeout (`aitask-explorechat/SKILL.md:67-79`);
- `render.py:57-120`;
- `intake.py:81-84, 219, 543`;
- `payload_guard.py:90-101`;
- `flow.py:220`;
- `audit.py:17, 38`;
- Discord-only (`daemon.py:730, 750`);
- explore-relay is Claude Code only (`aitask_codeagent.sh:497-498`).

Not verified: that `ANTHROPIC_API_KEY` is the variable the pinned CLI reads.
It is used only as "for example".

**Leftovers and open points:**
- The workflow names `./.aitask-scripts/aitask_metadata_commit.sh` for
  committing a hand-edited config. It is a script the user calls, as on
  `commands/sync.md`, but strictly it is a script path on an `intermediate`
  page.
- `commands/codeagent.md:179` says `--headless` is a "No-op for other
  agents/operations", but explore-relay and relations require it (t2258_6).
- `tuis/_index.md:29` omits the chatlink check panel and the `w` wizard
  (t2258_5 / t2258_7).
- Code messages point at the workflow page for per-key docs
  (`config_write.py:42-44`, `preflight.py:369`, `live_check.py:63`,
  `daemon.py:744`, `sandbox_launch.py:332-334`). The chain still works.
- `seed/chatlink_config.yaml` does not document `sandbox_env_passthrough`.
- `aidocs/chat/chatlink_runtime.md:23-30` has a stale TUI description.

**Links:** `check_links.py --build` passed (0 broken).

## Step 4 result — guide lessons

Three short additions to `aitasks/metadata/doc_update_guide.md`, committed on
the task-data branch. `test_docs_review_contract.sh` passes 71/71.
- **Page types:** signs that a how-to has grown into a lesson or a reference
  page. A walkthrough that repeats steps the page already listed; several
  walkthroughs that differ only in their example; a table of config keys,
  error messages or symptoms with fixes. Write the steps once, with the example
  inside them, and move the tables to the command's reference page. Seen on
  bug-report-intake and retroactive-tracking.
- **How a subject spans levels:** before calling a script's output, status line
  or flag contributor-only, check whether a site page tells readers to run it
  and whether its `--help` documents it for callers. Either makes it public
  architecture (the user's plan-review finding on `aitask_find_by_file.sh`).
- **Writing conventions / generic example names:** never use the framework's
  own scripts or modules as the reader's code (exploration-driven,
  retroactive-tracking, follow-up-tasks).

## Step 5 result — review round 1 (`/aitask-docs-review … --caller audit --budget 0`, independent agent)

All 19 pages were reviewed, plus the changed regions of the five long
destination pages. Every page reports `reader=not-run(not-beginner)`, except
`commands/_index.md`, which is untagged: a link list, out of scope. The link
check passed.

| Page | level | prose | unresolved |
|---|---|---|---|
| workflows/bug-report-intake | ok | 2 | 0 |
| workflows/create-tasks-from-code | ok | 2 | 1 (tmux fact) |
| workflows/premise-staleness | 2 | 2 | 1 (carry-over contradiction) |
| workflows/retroactive-tracking | ok | 2 | 0 |
| workflows/task-notes | 1 | 3 | 0 |
| workflows/work-report | ok | 4 | 0 |
| workflows/repo-maintenance | ok | 2 | 0 |
| workflows/follow-up-tasks | 1 | 3 | 0 |
| workflows/exploration-driven | ok | 2 | 0 |
| workflows/task-consolidation | ok | 2 | 0 |
| workflows/task-decomposition | ok | 1 | 0 |
| workflows/capturing-ideas | ok | 3 | 0 |
| commands/chatlink | 1 | 1 | 1 (label mechanism → aidocs) |
| commands/_index (row) | n/a (link list) | ok | 0 |
| commands/task-management (changed regions) | 1 | 1 | 1 (internal loop) |
| development/task-format (changed regions) | ok | 2 | 0 |
| development/premise-staleness | ok | 2 | 0 |
| tuis/board/reference (changed regions) | 1 | ok | 1 (tmux fact) |
| tuis/codebrowser/reference (changed regions) | ok | ok | 0 |

**Facts that may be wrong (reviewer):**
1. Carry-over tasks are `manual_verification`, so the premise check never reads
   their inherited baseline.
2. The board falls back to the project's `default_session` outside tmux.
3. `depends: [t108]` format.
4. "Force decomposition" overstates the mechanism.
5. A chatlink TUI missing-packages exit is undocumented.

Seen outside the pages: the `chatlink/daemon.py:8-9` docstring gives a stale
startup order.

All findings were sent to one fix agent (scratchpad `fix_brief.md`), with each
fact correction verified in the code first.

## Post-phase result — moved_fact_survival_check, run 1

Four independent checker agents, one per source group. Each read the
removed-blocks files from `removed_blocks.py` and the full source and
destination pages, and classified every claim with a quote. Full tables are
in scratchpad `survival_*.md`.

| Source | claims | preserved | weakened | missing | intentionally-changed |
|---|---|---|---|---|---|
| bug-report-intake | 237 | 223 | 6 | 0 | 8 |
| create-tasks-from-code (+4 rewritten destination rows) | 115 | 99 | 2 | 2 | 12 |
| premise-staleness | 61 | 57 | 0 | 1 | 3 |
| retroactive-tracking | 57 | 36 | 1 | 3 | 17 |
| 8 minor pages | 233 | 217 | 0 | 0 | 16 |

**Intentionally changed claims:**
- the code-verified corrections recorded in the restructure reports;
- example colour replaced by generic examples;
- the button-label, create-order and helper-path corrections;
- the `guild` → "server" wording.

Each one matches the code as checked.

**Weakened or missing → fixed in the fix pass (B list of `fix_brief.md`):**
- bug-report-intake:
  - Discord shows the token once;
  - the minimum permission set;
  - the most common no-op cause;
  - the most conservative default;
  - what the confirmation shows;
  - a session can also report missing channel access.
- create-tasks-from-code:
  - paths are relative to the project root;
  - the fold prompt header;
  - the codebrowser tutorial pointer.
- premise-staleness:
  - dependencies and status do not reveal drift;
  - **defect D1**: the trigger list omitted never-existed and invalid
    references, contradicting the dev page.
- retroactive-tracking: "one concern per wrap" as a general tip.

**Accepted as dropped:**
- create-tasks-from-code "safer in CI" (advice; the fact survives);
- retroactive "can be linked to issues" (wrap creates no issue link);
- "the analysis is more detailed on larger diffs" (no fact);
- "both workflows produce the same artifacts" (inaccurate: create makes only a
  task file).

**Stale sibling pages found** (they contradict the corrected facts): the
codebrowser how-to and `_index`, and the board how-to. Fact-only fixes are
included in the fix pass; their full audit stays with t2258_5.

## Step 7 result — links

- `check_links.py --build` passed (before the fix pass; re-run after it).
- `check_link_relevance.py` reported 8 links. None is in a file this child
  added or retargeted:
  - concepts/gates:66;
  - development/_index:117;
  - development/gates:124 and :177;
  - tuis/monitor/how-to:242;
  - workflows/risk-evaluation:38;
  - workflows/crash-recovery:30;
  - workflows/parallel-development:46.

  They are all pre-existing and belong to other sections (risk-evaluation →
  t2258_11, crash-recovery and parallel-development → t2258_9), so no verdict
  was owed here.
- `test_website_doc_lists.sh` passes 63/63, and
  `test_docs_vocabulary_coverage.sh` 32/32.

## Step 6 result — depth

Every leaf page under `workflows/` has `depth:`. Of the two content
`_index.md` pages, `screen-recordings/_index.md` is tagged and
`contribute-and-manage/_index.md` is not; t2258_12 owns that page, and its
task body says so. The new pages `commands/chatlink.md` and
`development/premise-staleness.md` are `advanced`.

## Fix pass (review round 1 + survival run 1) — report summary

One fix agent applied the findings from scratchpad `fix_brief.md`. It verified
each fact correction in the code first.

**Fact corrections:**
- **A1, carry-over: corrected.** Every carry-over is created as
  `manual_verification` (`aitask_archive.sh:960-966`), and the premise check
  skips that type (task-workflow SKILL.md:148). The opt-in bullet was dropped
  from the workflow page. The dev page now says the inherited baseline is never
  read by this check. The task-format row ("inherited, not reset") is
  accurate.
- **A2, board outside tmux: corrected.** `owned_lookup_session`
  (`lib/agent_launch_utils.py:597-613`) uses the caller's session, then the
  project's `tmux.default_session`. Either one must be owned by the project
  and running. Fixed in `tuis/board/reference#opening-file-references` and in
  the create-tasks-from-code board step. Added the `Codebrowser launch failed:
  <err>` notice (`board_detail_screen.py:893-899`).
- **A3, `depends: [t108]`: not a defect** (`lib/dep_resolution.py:75` accepts
  the `t` prefix).
- **A4:** decomposition is "ask for it in the description".
- **A5:** the chatlink status-TUI missing-packages refusal (exit 1) was added
  (`aitask_chatlink.sh:49-55`).

**Restored claims:** all 12 weakened or missing claims from run 1 (B list).
- `file_references` paths are relative to the project root
  (`codebrowser_app.py:1622`).
- The fold picker header is now named (`aitask_create.sh:2098-2099`).

**Facts that had to move:**
- the chatlink container-label clause → already stated in
  `aidocs/chat/chatlink_sandbox.md:47-57`;
- the task-management "each path looked up once" clause → already stated in
  `aidocs/framework/file_references_flow.md:23-24`;
- the task-format validation sentence → moved from the table cell to a
  paragraph below the table (no new row).

**Level and prose:**
- task-notes: the routing table is now bullets; "linked project" is the body
  term. Its heading is kept, because three pages link the anchor (a rename
  broke 3 links and was reverted).
- follow-up-tasks: the example is folded once into "Updating existing tasks";
  the Advantages and Result restatements are cut. The `depends` and
  batch-follow-up facts moved to "During implementation".
- work-report: the walkthrough is one numbered procedure; the flat-average
  flags are named (`--velocity-model flat`, `--velocity-window <days>`);
  "membership review" is now used as one term.
- exploration-driven: the free-text goal is added; "Exploration Modes"
  (no incoming links).
- Prose fixes on all twelve pages and both dev pages, as listed in the brief.
- Next footers are now relref with a colon, targets unchanged.

**Stale sibling pages, fact-only fixes:** the fallback, title and button names
on `tuis/codebrowser/how-to.md#how-to-create-a-task-from-a-selection` and
`tuis/codebrowser/_index.md#creating-tasks-from-code`; the tmux rule on
`tuis/board/how-to.md` (the File Refs row). All three were clean at the gate.
Their full audit stays with t2258_5.

**Checks:** `check_links.py --build` passed; `test_docs_vocabulary_coverage.sh`
passed 32/32.

**Leftovers:**
- the bug-report-intake Next footer points backwards (unchanged);
- "blast radius" in task-notes L15;
- bold list lead-ins.

## Survival check run 2 (on the fixes and the fix-pass cuts, independent agent)

- **Part 1:** all 12 restored claims are preserved: 12/12.
- **Part 2:** the fix-pass cuts hold 150 claims: 138 preserved, 3 weakened, 0
  missing and 9 intentionally changed. The 9 are the codebrowser and board
  corrections, re-verified against the code.
- **The 3 weakened claims were restored in this session:**
  - follow-up-tasks: "detailed and accurate";
  - follow-up-tasks: the agent cross-references batched follow-ups;
  - board reference: the `file_references` row links the workflow again.
- **Final: 0 missing, 0 weakened.**

## Step 5 — review round 2 (independent agent, after the fix pass)

All round-1 items were fixed or still held. New findings:

**Facts, verified and fixed here:**
- `ait update` without `--batch` opens the interactive editor and ignores its
  flags (`aitask_update.sh:371, 2598-2602`). This was already wrong at HEAD.
  `--batch` was added to all four commands on `workflows/premise-staleness.md`
  and to the one on `development/premise-staleness.md`.
- `ait create` has no `--remove-file-ref`. The `development/task-format.md`
  sentence was corrected.
- The invite URL's `permissions=397552863296` is wrong. It lacks
  `view_channel` and `attach_files`, which `live_check.py` requires, and adds
  voice and moderation permissions; the listed ten sum to `395137109056`. The
  integer lives in `.aitask-scripts/chatlink/live_check.py:68`,
  `aidocs/chat/discord_bot_setup.md:50` and `tests/test_chatlink_wizard.sh:510`,
  so the docs keep matching the code until those three change together. This
  is recorded as an upstream defect.

**Level and precision fixes:**
- `AgentCommandScreen` became "a command dialog" on the codebrowser how-to and
  `_index`;
- "bare id" is now spelled out;
- "persistent kanban views" is now plain words;
- the board's "switches to it" became "makes it that session's current
  window";
- the codebrowser `create-task` window name (verified at
  `codebrowser_app.py:1620`);
- transitive refs in the fold union (verified in `aitask_fold_mark.sh:237`);
- "shows the file at the referenced lines".

**Prose fixes:** the duplicate token "copy"; "watched files" is now "files in
its scope"; "exploration type" is now "mode"; the doubled "unproven"; a
repeated board sentence and the duplicate exit-0 sentence are cut; the
codebrowser how-to's repeated fallback sentence is cut.

**Left as minor and noted for the later children:**
- the bug-report-intake diagram's "payload" and the example `repo_name`, both
  in code blocks;
- em-dash separators in Related lists;
- the retroactive "When you need it" / "Wrap vs. Create" overlap;
- the task-notes route wording;
- "force re-verification" on follow-up-tasks;
- "thousands of orders" on exploration-driven;
- "preserving all original context" on task-consolidation.

These are wording-level items with no fact and no level breach. Re-running
review rounds on them would not converge, so they are listed here for t2258_8
to weigh in its retrospective.

**Final checks after round 2:**
- `check_links.py --build` passed;
- `test_website_doc_lists.sh` passed;
- `test_docs_vocabulary_coverage.sh` 32/32;
- `test_docs_review_contract.sh` 71/71.

## Step 8 — ledger close-out

**Ledger empty.** Every source and destination page passed the shared-file
gate when it was edited. That includes the three TUI pages added in the fix
pass. No `audit_deferred_pages_workflows_tasks` child is needed.

## Post-Review Changes

### Change Request 1 (2026-11-12)
- **Requested by user:** two review findings.
  1. `commands/chatlink.md` said every non-integer ceiling value falls back to
     its default with a warning. `_clamped_int` calls `int(raw)` first, so a
     decimal is truncated silently and a numeric string is accepted.
  2. `tuis/codebrowser/reference.md` described a multi-range focus as running
     from the "first start to the last end". `_parse_focus_value` uses
     `min(starts)..max(ends)` and accepts unordered or overlapping segments.
- **Verified by a direct probe of `chatlink/config.py::_clamped_int`:**
  - `1.9→1`, `2.5→2` and `-1.2→-1→clamped 1`, with no warning;
  - `'3'→3` and `' 4 '→4`;
  - `'3.5'`, `'abc'` and `True`: the default, with a warning;
  - `None`: the default, silently;
  - out of range: clamped, with a warning.

  The focus rule was read in `codebrowser_app.py:522` (`min(starts)..max(ends)`).
- **Changes made:**
  - chatlink "invalid values" now states the conversion order and each
    fallback (truncation without a warning, quoted whole numbers accepted,
    other text and booleans → default with a warning, empty → default
    silently, then the range clamp).
  - The codebrowser reference now says "lowest start to highest end, whatever
    their order and even when they overlap", with the three examples.
  - No other page states either rule (grep). The link check passes.
- **Files affected:** `website/content/docs/commands/chatlink.md`,
  `website/content/docs/tuis/codebrowser/reference.md`.

## Final Implementation Notes
- **Actual work done:**
  - **Step 0, split** (user decision: six parts, fully sequential). Created
    t2258_9 `audit_workflows_parallel_local`, t2258_10 `audit_workflows_cross_project`,
    t2258_11 `audit_workflows_review_quality`, t2258_12 `audit_workflows_git` and
    t2258_13 `audit_workflows_screen_recordings`, each with a self-contained
    description and a plan. Chain: 4 → 9 → 10 → 11 → 12 → 13 → 5 → 6 → 7 → 8;
    t2258_5 was rewired to depend on t2258_13. Notes went to t2258_8 (ledger
    and reader-sample scope) and t2258_5 (new dependency). The parent plan's
    child table gained a row.
  - **Steps 1–3:** inventory verdicts for the 12 pages of the Tasks, Reporting
    and Maintenance groups.
    - Four restructures:
      - `bug-report-intake`: one procedure, plus a new `commands/chatlink.md`
        reference;
      - `create-tasks-from-code`: facts moved to task-format,
        task-management, the board and codebrowser references, and a new
        `aidocs/framework/file_references_flow.md`;
      - `premise-staleness`: a how-to, plus a new
        `development/premise-staleness.md`;
      - `retroactive-tracking`: condensed to one procedure.
    - Eight pages got minor level and prose fixes.
    - Fact-only fixes went onto three stale TUI pages (codebrowser how-to and
      `_index`, board how-to) that contradicted the corrected facts.
  - **Step 4:** three guide lessons (how-to growth signs; documented script
    output is public; no framework scripts as example code).
  - **Steps 5–7:** two review rounds and two claim-level survival runs, ending
    at 0 missing and 0 weakened. Checks pass: links, doc lists, vocabulary
    coverage and the docs-review contract. All leaf pages carry `depth`.
- **Deviations from plan:**
  - `premise-staleness` was planned as a minor table check, but became a
    restructure with a new `development/premise-staleness.md`. Its two outcome
    tables and edge rules had no owner page, and the guide calls for a focused
    `advanced` dev page in that case.
  - `retroactive-tracking` was upgraded to a restructure (anti-pattern 2: four
    repeated walkthroughs).
  - The fix pass edited three TUI pages outside the planned set (fact
    corrections only, gated clean). Their full audit stays with t2258_5.
  - Page work was delegated to parallel agents on disjoint file sets with a
    shared brief, as in the pilot; reviews and survival checks went to
    independent agents. Every report is recorded above.
  - The guide commit's message carries a `(t2258_4)` suffix. Administrative
    `ait:` commits should omit it. It is harmless, since that commit is on the
    task-data branch.
- **Issues encountered:**
  - One fix-pass heading rename broke three incoming anchors. It was caught by
    the link check and reverted.
  - The first transcript-extraction attempt for an agent report returned the
    handback stub, so reports were recorded from the handback messages
    instead.
- **Key decisions:**
  - `aitask_find_by_file.sh` is public architecture (user plan review): its
    contract is on `development/task-format.md`, and only the fold helper chain
    went to aidocs.
  - `commands/chatlink.md` is the chatlink reference, including the status TUI
    keys, because there is no chatlink TUI page.
  - The wrong invite integer was left matching the code until code, aidocs
    and test change together.
  - Minor wording findings from review round 2 are listed above, not chased in
    further rounds.
- **Ledger outcomes:** the ledger is empty. No page was dirty from another
  session at its edit time, so no follow-up child is needed.
- **Upstream defects identified:**
  - `.aitask-scripts/chatlink/live_check.py:68` — the invite URL's
    `permissions=397552863296` lacks View Channels and Attach Files (both in
    `REQUIRED_BOT_PERMISSIONS`) and grants unrelated voice and moderation
    rights. The listed ten sum to `395137109056` (`395137117248` with Manage
    Messages). The same integer is copied in `aidocs/chat/discord_bot_setup.md:50`,
    `tests/test_chatlink_wizard.sh:510` and the bug-report-intake page.
  - `seed/chatlink_config.yaml` — it does not document `sandbox_env_passthrough`,
    the only route the agent's API key reaches the sandbox by, so a config
    built from the seed template cannot run a session.
  - `.aitask-scripts/aitask_create.sh:2029-2030` — the comment says
    `run_auto_merge_if_needed` is "only invoked from the --batch --commit
    paths", but `finalize_draft` (lines 1022, 1087) also calls it.
  - `.aitask-scripts/chatlink/daemon.py:8-9` — the docstring gives the startup
    order as "config → token → intake"; the code runs config → yaml → intake →
    token.
  - `website/content/docs/commands/codeagent.md:179` — it says `--headless` is
    a "No-op for other agents/operations", but `aitask_codeagent.sh:45-47, 605-607`
    makes it required for `explore-relay`, `relations` and `obsolescence`.
- **Notes for sibling tasks:**
  - **Method that worked:**
    - parallel restructure agents on disjoint file sets with one written
      brief;
    - then an independent `/aitask-docs-review --caller audit` round;
    - then claim-level survival agents per source group;
    - then one fix agent;
    - then round 2 of both.

    `scratchpad/removed_blocks.py` (the block splitter) is described in the
    post-phase. Re-create it from that description.
  - **Expect real fact errors on old pages.** About 25 were corrected here,
    for example `ait update` without `--batch`, wrong option labels and
    impossible flows. Check every moved fact in the code.
  - Before calling script output contributor-only, check `--help` and whether
    the site tells users to run the script (now a guide rule).
  - Avoid table rows in `development/task-format.md` (the vocabulary scan).
  - Renaming a heading breaks incoming anchors: grep `website/content` for
    `<page>#` first.
  - **Leftovers by owner:**
    - **t2258_5:** the full audit of the three TUI pages fact-fixed here;
      `tuis/_index.md:29` (the chatlink check panel and `w` wizard are
      missing).
    - **t2258_6:** `commands/codeagent.md:179`; `commands/note.md` probably
      wants `advanced`; `skills/aitask-wrap.md` (relative links, a duplicated
      table); `skills/aitask-pick/_index.md:28` (the premise classes at
      intermediate); `skills/aitask-explore.md` (the free-text goal).
    - **t2258_9:** `crash-recovery.md:71` is t2284's. The relevance report
      flags `crash-recovery:30` and `parallel-development:46`.
    - **t2258_11:** `upstream-defect-followup.md` ("Step 8b/8c", relative
      links); the `manual-verification` heading "(Step 8c)", whose anchor
      `follow-up-tasks` links to; `risk-evaluation:38` (relevance).
    - **t2258_10:** "sibling project" wording and the
      `#creating-a-task-in-a-sibling-project` anchor.
    - **t2258_7:** the new `development/premise-staleness.md` and the
      task-format "Finding tasks by file reference" section.
