---
Task: t2258_doc_audience_levels_and_readable_prose.md
Base branch: main
Output branch: main
---

### Pre-phase (risk mitigations)

These steps are carried verbatim into the named child's plan and task
description at creation time; the parent itself runs nothing.

1. [gate_review_cost_bound] (child 2) Write the `aitask-doc-review` procedure so
   one gate run stays bounded: the level/prose check is one in-context pass per
   edited page (no sub-agent); fresh-reader runs (sub-agent, or self-review where
   no sub-agent exists) happen only for edited pages at the guide's declared
   beginner level, with a **budget of 3 per gate run, cumulative across every
   review and re-review** (decision 6). The gate passes the remaining budget into
   each review call, and the skill returns how much it used. Within a pass, pages
   are chosen by most changed body lines; pages left over are logged
   `reader=not-run(cap)` and listed at the confirm step. Extra tests run only on
   the user's explicit "Run more fresh-reader tests" choice there, and never
   under an autonomous profile. In the no-level-model case no fresh-reader test
   runs and no budget is used. Verify: the skill and gate text state the
   cumulative budget, the selection order, the explicit-authorization rule and
   the log value, and the contract test (post-phase step 1) asserts them.
2. [reader_test_baseline_and_control] (child 3) Before restructuring any concept
   page, run the fresh-reader test (child 2's procedure, `main-concept` persona)
   on the six long concept pages **and** on `concepts/tasks.md` and
   `concepts/plans.md` as controls. Record every report verbatim in the child's
   plan. If the reports do not separate the long pages from the controls (more
   guessed terms / unneeded details on the long pages), stop and tune the
   persona and question set in `aitask-doc-review` before restructuring. After
   restructuring, re-run on the same pages and record the after-reports
   (child 8 compares them).

# t2258 — Reader levels and readable prose for the website docs (decomposition plan)

## Context

Pages under `website/content/docs/` that agents write often mismatch audience and
detail: orienting pages (concepts, how-tos, workflows) carry mechanism, exit codes
and edge-case tables; beginners meet field names before ideas; and the prose has
AI tells (staged contrasts, "not X but Y", dash rhythm). A `depth` taxonomy exists
(`main-concept` 13, `intermediate` 88, `advanced` 58, 16 untagged) but nothing says
what each level may contain, and the `docs_updated` gate checks no readability.
Goal: a written level model the doc-writing path reads, a review pass in that
path, and the existing site audited and restructured against the model.

The task is too large for one session (≈175 pages plus a gate/skill change), so
this plan decomposes it into 8 sequential children. The parent itself makes no
edits.

## Design decisions (confirmed with the user)

1. **Two axes, existing values kept.** `depth` = what the reader already knows
   (sets vocabulary); **page type** = what the reader needs (sets shape), using
   Diátaxis types (tutorial / how-to / reference / explanation). Type comes from
   the section and page role, not a new frontmatter field:
   `concepts/` = explanation, `workflows/` = how-to, `commands/` + `skills/` =
   reference, TUI `_index` / `how-to` / `reference` = overview / how-to /
   reference, `getting-started.md` = tutorial, `overview.md` = explanation.
   Values stay `main-concept` / `intermediate` / `advanced` (no URL churn;
   `website/check_links.py:91` uses `depth/advanced/` as its control). Each value
   gets a written contract, and `depth` becomes **required on every leaf page**.
   The Diátaxis "how-to must not teach" rule is resolved by depth: a
   `main-concept` page defines every term; `intermediate` / `advanced` pages may
   assume the knowledge their contract names, and link to where it is taught.
2. **Rules live only in the configured guide; procedure lives in a reusable
   skill.** Level model + prose rule pack go into
   `aitasks/metadata/doc_update_guide.md`. A new skill `aitask-doc-review` holds
   the review *procedure* only and reads each project's configured guide through
   `aitask_resolve_config_path.sh doc_update.guide …` — it duplicates no rule
   text. The skill owns only procedure invariants (what a rewrite must not touch;
   no invented facts; a cut fact is moved to its owning page, not deleted).
   **Interface to the guide:** a guide has a level model when it has a
   `## Reader levels` section that declares the level field (here `depth`), the
   beginner level value (here `main-concept`) and one persona sentence per level.
   That heading name and those three declarations are the only things the skill
   relies on; everything else it reads as rule text.
   **No level model** (a guide without that section, which is today's seed guide):
   the prose check runs against whatever writing conventions the guide does have;
   the level check and the fresh-reader test do **not** run, because without a
   declared beginner level there is no basis to choose pages or a persona. Both
   are logged `not-run(no-level-model)` and the confirm step tells the user the
   project's guide has no level model. Whether the seed guide gains one is child
   8's decision.
3. **Review coverage.** The level/prose check runs on **every edited page**; the
   fresh-reader sub-agent test runs on **edited `main-concept` pages**, and as
   spot checks during the audit. Agents without sub-agents fall back to a
   self-review checklist, **recorded explicitly** as such. Unresolved reader
   problems are **reported** to the user at the gate's confirm step and in the
   gate log (they inform the user's decision; they do not auto-fail the gate).
   Per page, the log's `reader=` field takes exactly one of: `subagent`,
   `self-review`, `not-run(not-beginner)`, `not-run(untagged)` (also a level
   finding: `depth` is required), `not-run(cap)`, `not-run(no-level-model)`.
4. **Eight children, sequential** (default sibling dependencies). Sequential
   avoids concurrent edits to the shared guide file and cross-section links,
   and lets the concepts pilot shape the later audits.
5. **The review reads the text that will be applied, and applying never
   overwrites newer content.** Step 3 of the gate writes, per proposed page, two
   files under `.aitask-gates/<task-id>/docs_updated_<run-id>_drafts/`
   (gitignored): `<page path>.draft`, the **complete** proposed page, and
   `<page path>.base`, a copy of the page as it was when drafting began (no
   `.base` for a new page). The review consumes the `.draft` files, never the
   existing page or an outline.
   - **Changed after review → reviewed again.** Any change to a draft after its
     last review (the user's "Adjust", or a reconciliation below) puts that page
     back through the review before the gate asks for confirmation again
     (level/prose check always; fresh-reader only within the run's remaining
     budget, decision 6).
   - **Destination check at apply.** Step 5 classifies each page by whether
     `.base` exists (the page existed when drafting began) and whether the
     destination exists now, and acts on exactly one row:

     | `.base` | destination now | state | action |
     |---|---|---|---|
     | yes | exists, `cmp -s` equal to `.base` | unchanged | copy `.draft` over it |
     | no | absent | unchanged (new page) | copy `.draft` into place |
     | yes | exists, differs | modified by another session | three-way merge (below) |
     | no | exists | **created** by another session | do not apply; back to proposal |
     | yes | absent | **deleted** by another session | do not apply; back to proposal |

     **Three-way merge, only when all three inputs exist:**
     `git merge-file -p <current> <.base> <.draft> > <reconciled>`, branching on
     its exit status: `0` → clean reconciled draft; `1`–`127` → that many
     conflicts, resolved by hand, and the result must contain no conflict
     markers before it counts as a draft; any other status (git reports errors
     as a negative value, seen as `255`) → **error, not reconciliation**: discard
     the output, apply nothing for that page, and report it. A reconciled draft
     replaces the `.draft`, the current page becomes the new `.base`, and the
     page goes through review and the confirm step again.

     **Created or deleted by another session:** stop applying that page and
     return it to step 3. For a created page, draft again against the page that
     now exists (it becomes the `.base`). For a deleted page, ask the user
     whether to recreate it, move the change to another page, or drop it. Either
     way the page is reviewed and confirmed again before anything is written.
     Other pages in the run that are unchanged still apply normally.

     Never apply a draft over a destination that is not in an "unchanged" row.
   - Content hashes and a reviewed/applied digest audit trail are **not** part of
     this child; whether to add them is recorded as an open item for child 8.
6. **Fresh-reader budget is per gate run.** At most **3** fresh-reader tests
   (sub-agent or self-review) in one gate run, counted **cumulatively** across
   the first review and every re-review after "Adjust" or reconciliation. Within
   a pass, beginner pages are chosen by most changed body lines. Once the budget
   is spent, further beginner pages are logged `reader=not-run(cap)` and listed
   at the confirm step. More tests in the same run need the user's **explicit**
   authorization there ("Run more fresh-reader tests", naming the pages);
   autonomous profiles never extend the budget.

## Child tasks (created post-approval)

Labels for all: `documentation,web_site,doc_quality` (child 2 adds
`aitask_gate_docs_updated`). Type `documentation` except child 2 (`enhancement`).

| # | Name | Effort | Delivers |
|---|---|---|---|
| 1 | `level_model_and_prose_rule_pack` | medium | Guide sections: reader levels, page types, how a subject spans levels, concept-page rules (moved from `aidocs/framework/documentation_conventions.md`, which keeps a pointer), prose rules with before/after examples from our pages, sources and credits. CLAUDE.md + `website/README.md` pointers. |
| 2 | `doc_review_skill_and_gate_wiring` | high | `.claude/skills/aitask-doc-review/SKILL.md` (procedure only; reads the configured guide; no-level-model path per decision 2); `docs_updated` gate: step 3 writes complete `.draft` + `.base` files, new step 3b reviews the drafts, step 4 shows the reader report and the remaining fresh-reader budget, "Adjust" re-reviews changed drafts, step 5 applies only over an unchanged destination and otherwise reconciles + re-reviews, step 6 logs `reader=` per page (decisions 5–6); `aitask-docs-gap` Step 6 "Target level" line; website skill page; static contract test. |
| 3 | `audit_concepts_pilot` | high | All 25 concept pages classified; the six long ones (`gates`, `framework-session`, `skill-templating`, `attachments`, `topic-anchoring`, `locks`) restructured; before/after fresh-reader reports recorded; lessons fed back into the guide. |
| 4 | `audit_workflows` | high | 44 workflow pages; longest first (`bug-report-intake`, `freeze-and-restore-agents`, `manual-verification`, `shadow-agent`, …). May add sibling children at its own planning if too large. |
| 5 | `audit_tuis` | medium | 32 TUI pages; mechanism out of `how-to` pages (e.g. `tuis/minimonitor/how-to.md` refresh cycle / `exit()` / startup grace). |
| 6 | `audit_skills_and_commands` | medium | 41 skill + 15 command pages (reference type): narrative-in-reference, intros, depth tags. |
| 7 | `audit_entry_pages_and_depth_check` | medium | `overview`, `getting-started`, `installation/`, `development/`, section `_index` pages; tag remaining untagged pages; add a depth-required check to the website checks + CI. |
| 8 | `retrospective_doc_levels` | medium | Before/after reader-report comparison; **skipped-page reconciliation** (every page in the skipped-page ledgers of children 3–7 is either audited or has an open follow-up child; outstanding ones are listed in the parent's completion report); decide seed-guide level model, Vale advisory step, t2186 eval follow-up, and whether the gate's drafts need a content-hash audit trail (deferred from child 2); create port tasks for `aitask-doc-review` (Codex / OpenCode wrappers). |
| 9–13 | `audit_workflows_{parallel_local,cross_project,review_quality,git,screen_recordings}` | high / medium / high / medium / medium | Split from child 4 at its planning (2026-11-12, user decision): the 44 workflow pages are too many for one session. Child 4 keeps the Tasks, Reporting and Maintenance groups; 9–13 take the other `workflows/_index.md` groups, with Parallel split in two. Fully sequential chain: 4 → 9 → 10 → 11 → 12 → 13 → 5 → 6 → 7 → 8. The common audit method below binds them too. |

### Common audit method (children 3–7)

1. **Inventory first, in the child's plan:** every page → lines, `depth`, page
   type, verdict, violations (Diátaxis anti-patterns 1/2/5 first, then 3/4; the
   guide's level contract; the prose rules).
2. **Shared-file gate before each edit:** diff the page against HEAD; a page
   dirty from another session (today: `tuis/applink/reference.md`,
   `tuis/monitor/reference.md`, `workflows/contribute-and-manage/contribution-flow.md`)
   is not edited over. It goes into a **skipped-page ledger** in the child's plan
   (path, reason, the dirty state seen) and stays pending.
   **Before the child closes** it re-checks every ledger entry against HEAD: a
   page that is now clean (the other session committed) is audited in this child
   like any other. A page still dirty gets a tracked follow-up: a new child of
   t2258, created with `--no-sibling-dep`, named
   `audit_deferred_pages_<section>`, listing each page, its violations and the
   reason it was skipped. The child's Final Implementation Notes record each
   ledger entry's outcome (`audited` or `follow-up t2258_<n>`). A child may not
   archive with a ledger entry that has neither outcome. Because the follow-up is
   a child of t2258, the parent cannot archive while that work is open.
3. **Restructure:** move mechanism to the page that owns the behaviour (reference
   page, workflow page, or `aidocs/` for contributor-only internals); split mixed
   pages; keep a short overview that links out. Every cut fact is moved, and the
   move is recorded.
4. Run `aitask-doc-review` on each edited page (fresh-reader on `main-concept`).
5. `cd website && python3 check_links.py --build` (mandatory) and
   `check_link_relevance.py` for retargeted links, opening every reported target.
6. Rule refinements discovered go back into the guide's examples, not into ad-hoc
   page fixes.

## Post-approval steps (this session)

1. Create the 8 children with the Batch Task Creation Procedure (sequential
   sibling deps), each carrying the full context above for a fresh session.
2. Write and commit child plans `aiplans/p2258/p2258_<n>_<name>.md`.
3. Revert t2258 to `Ready`, release its lock; manual-verification sibling
   question; child checkpoint.
4. Step 9 (Post-Implementation) applies per child; the parent archives when all
   children are done.

### Post-phase (risk mitigations)

1. [doc_review_gate_contract_test] (child 2) Add `tests/test_doc_review_contract.sh`
   (self-contained, `assert_*` helpers from `tests/lib/asserts.sh`) asserting:
   - the gate's `SKILL.md` has the review step after step 3 and before step 4;
     step 3 writes complete `.draft` and `.base` files; "Adjust" and
     reconciliation route back through the review; step 5 names all five
     destination states of decision 5, calls `git merge-file` only in the
     "modified" state, treats exit statuses outside `0`–`127` as an error that
     applies nothing, and sends "created" and "deleted" pages back to proposal;
   - the review skill resolves the guide via `aitask_resolve_config_path.sh
     doc_update.guide` and names `## Reader levels` as its only interface heading;
   - no duplicated rules: none of the bullet lines under the guide's prose-rules
     section appear in the review skill;
   - the step-6 log instructions name the `reader=` field with all six values
     from decision 3;
   - the budget is stated as 3 per gate run, cumulative across re-reviews, with
     most-changed-first selection and extra tests only on explicit user
     authorization (decision 6); the no-level-model path skips both the level
     check and the fresh-reader test.

   Include a pre-fix control: run against the current (unwired) gate text and
   confirm it fails.

## Verification

- Each child's own verification (named in its plan); for every child touching
  `website/content/`, `check_links.py --build` passes.
- Child 2: the static contract test passes (and its pre-fix control fails), plus
  three recorded dry runs of the gate, in a scratch copy of the docs tree:
  - **reviewed-draft run** on a sample `main-concept` page: propose → `.draft` +
    `.base` → review (`reader=subagent`) → "Adjust" with a body change →
    re-review of that page → apply. The applied page is byte-identical to the
    last reviewed draft (`cmp`), and the run used no more than 3 fresh-reader
    tests in total;
  - **destination-change runs**, one per non-unchanged row of the decision-5
    table, each changing the destination after drafting and before confirming
    (standing in for another session):
    - *modified, clean merge*: an edit in a different region. Apply refuses the
      plain copy, the merge exits 0, the reconciled draft is re-reviewed and
      confirmed, and the final page has both the other edit and the reviewed
      changes;
    - *modified, conflicting*: an edit to the same lines. The merge exits 1, the
      conflict is resolved by hand, no conflict markers remain, re-review and
      re-confirm follow;
    - *created*: a proposed new page appears before confirming. Nothing is
      applied for it, it returns to proposal and is drafted against the page that
      now exists;
    - *deleted*: an existing page is removed before confirming. Nothing is
      applied for it, `git merge-file` is never called, and the user is asked how
      to proceed;
    - in each case, other unchanged pages in the same run still apply;
  - **no-level-model run** with a scratch config pointing `doc_update.guide` at a
    copy of `seed/doc_update_guide.md`: the log shows `level=` and `reader=` as
    `not-run(no-level-model)`, and the confirm step says the guide has no level
    model.
- Children 3–7: each skipped-page ledger entry has an outcome (`audited` or
  `follow-up t2258_<n>`) in the child's Final Implementation Notes before it
  archives; child 8 verifies the union and lists outstanding follow-ups.
- Parent done when the "Done when" list in the task holds: the guide carries the
  level model and the gate reads it; the gate runs the review incl. fresh-reader
  for beginner pages; all sections audited (children 3–7 archived), and every
  skipped page either audited or carried by an open `audit_deferred_pages_*`
  child (which itself keeps the parent from archiving).

## Risk

### Code-health risk: medium
- The `docs_updated` gate gets a heavier step that runs for every gated task; a malformed or ambiguous step degrades every doc update, and a per-page sub-agent run adds time and tokens · severity: medium · → mitigation: inline pre-phase gate_review_cost_bound; inline post-phase doc_review_gate_contract_test
- Restructuring ≈175 pages moves content between pages; links and anchors break silently and facts can be lost in a move · severity: medium · → mitigation: none separate; covered by audit method steps 3 (moved-fact record) and 5 (mandatory `check_links.py`)
- Other sessions edit website pages concurrently (three are dirty now); a skipped page could leave restructuring work untracked · severity: low · → mitigation: the audit method's shared-file gate and skipped-page ledger (step 2), reconciled in child 8

### Goal-achievement risk: medium
- A model as "fresh reader" is in effect an expert; even with a depth persona it may not find what a real newcomer misses, so the test can pass pages that still read badly · severity: medium · → mitigation: inline pre-phase reader_test_baseline_and_control
- Level contracts written in the abstract may be too vague to shape real pages · severity: medium · → mitigation: the concepts pilot (child 3) feeds back into the guide before the larger audits
- The site-wide audit is large and may stall partway · severity: low · → mitigation: one child per section, sequential, each independently shippable

Reassessed after inlining the three phases: levels unchanged (link/fact loss in
moves and the persona's limits are reduced, not removed).

### Planned mitigations
- timing: pre-phase | name: gate_review_cost_bound | type: enhancement | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: heavier docs_updated gate step (time/tokens) | desc: cap fresh-reader sub-agents at 3 edited main-concept pages per gate run; log not-run(cap)
- timing: pre-phase | name: reader_test_baseline_and_control | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: fresh reader is in effect an expert | desc: before/after reader reports on the six long concept pages with tasks.md/plans.md as controls; stop and tune if no separation
- timing: post-phase | name: doc_review_gate_contract_test | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: malformed or ambiguous gate review step | desc: static contract test of gate wiring, guide resolution, no duplicated rules, reader= log field, with pre-fix control
