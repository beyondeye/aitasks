---
priority: medium
effort: medium
depends: [t2258_5]
issue_type: documentation
status: Ready
labels: [documentation, web_site, doc_quality]
gates: [risk_evaluated]
anchor: 2258
created_at: 2026-11-09 23:09
updated_at: 2026-11-09 23:09
---

## Context

Child 6 of t2258: audit `website/content/docs/skills/` (41 pages) and `website/content/docs/commands/` (15 pages). These are reference pages: check anti-pattern 3 (reference written as narrative), intros that do not say what the skill/command is for in plain words, and how-to steps embedded in reference. Keep literal agent enumerations only where the list is the documentation (`commands/codeagent.md` mapping table). Include the new `skills/aitask-doc-review.md` page from child 2.

## Method (binding; full text in the parent plan's "Common audit method")

Read the parent task `aitasks/t2258_doc_audience_levels_and_readable_prose.md`,
the approved parent plan `aiplans/p2258_doc_audience_levels_and_readable_prose.md`,
and the archived plan of `t2258_3` (concepts pilot) for lessons learned. Rules:
the "Reader levels", "Page types", "How a subject spans levels" and "Prose
rules" sections of `aitasks/metadata/doc_update_guide.md`. Review procedure:
`.claude/skills/aitask-doc-review/SKILL.md`.

1. Inventory every page of the section in the plan: lines, `depth`, page type,
   verdict, violations (Diátaxis anti-patterns 1/2/5 first, then 3/4; the
   guide's level contract; the prose rules).
2. Shared-file gate before each edit: diff the page against HEAD; a page dirty
   from another session is not edited — record it in a **skipped-page ledger**
   (path, reason, dirty state seen). Before closing, re-check each entry: now
   clean → audit it here; still dirty → create a child of t2258 with
   `--no-sibling-dep` named `audit_deferred_pages_<section>` listing pages,
   violations and reason. Final Implementation Notes record each entry's
   outcome (`audited` / `follow-up t2258_<n>`); do not archive otherwise.
3. Restructure: mechanism moves to the page that owns it (reference page,
   workflow page, or `aidocs/` for contributor-only internals); split mixed
   pages; keep a short overview that links out. Record every moved fact
   (source → destination#anchor) in the plan.
4. `aitask-doc-review` on each edited page (fresh-reader on `main-concept`
   pages, within the budget).
5. `cd website && python3 check_links.py --build` (mandatory) and
   `python3 check_link_relevance.py` for retargeted links, opening every
   reported target.
6. Rule refinements go back into the guide's examples, not ad-hoc page fixes.
7. Add `depth:` to every untagged leaf page in the section.

## Verification

- Inventory table, moved-fact table and skipped-page ledger outcomes are in the
  plan.
- `check_links.py --build` exits 0.
- Every leaf page in the section has `depth:`.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2258_2** id=2026-11-10T14:18:13Z.35767bbef376b35d43e645b4 from=t2258_2 from_verified=yes at=2026-11-10T14:18:13Z base=2f816eabe5d2bf807b62aac35edbeaa31f55f9b8 base_branch=main dirty=yes host=omg16
>
> | The review skill that t2258_2 built is named `aitask-docs-review` (renamed at review, to match `aitask-docs-gap`), not `aitask-doc-review` as this task's body and plan say.
> | - Skill: .claude/skills/aitask-docs-review/SKILL.md
> | - Invocation: /aitask-docs-review <page>... [--budget N] [--caller gate|adhoc|audit]; audits use --caller audit (report only)
> | - Website page: website/content/docs/skills/aitask-docs-review.md
> | - Contract test: tests/test_docs_review_contract.sh
> | Read every `aitask-doc-review` reference in this task as `aitask-docs-review`.

> **✉ note:t2258_3** id=2026-11-12T06:51:14Z.57894283cfb7e1884d788970 from=t2258_3 from_verified=yes at=2026-11-12T06:51:14Z base=7f1f4333a3379c4641e0a4b85281072e25ea2240 base_branch=main dirty=yes host=omg16
>
> | Advisory from t2258_3 (concepts pilot), committed in 7f1f4333a. Changes to pages you audit:
> | - commands/lock.md is retagged depth advanced. Its outcome table is at #when-a-pick-meets-a-held-lock, and other pages link to that anchor.
> | - New page commands/skillrun.md (weight 46, advanced): the `ait skillrun` reference moved there from skills/aitask-pick/execution-profiles.md. commands/_index.md links to it.
> | - commands/attach.md, gates.md, task-management.md and setup-install.md received moved facts. task-management's --followup-of row now states the anchorless-child chaining case. The `aitask_create.sh` help still says "never chains"; that is tracked in t2284.
> | - The concepts/artifacts depth and mechanism content were left for you to decide, because commands/artifact points back to the concept page.
> | - The new skill aitask-docs-review Step 4 has the reader sub-agent write its own questions from title, description and persona before it sees the page.

> **✉ note:t2258_4** id=2026-11-12T13:41:14Z.cb0808978210d80ff922735f from=t2258_4 from_verified=yes at=2026-11-12T13:41:14Z base=86d4f4aba660abfb560be589d704b42b20b9a61f base_branch=main dirty=yes host=omg16
>
> | Advisory from t2258_4, committed in 86d4f4aba.
> | 
> | New and changed pages in your section:
> | - NEW commands/chatlink.md (advanced): the full chatlink reference, moved from workflows/bug-report-intake. It has a new row in commands/_index.md.
> | - commands/task-management.md: `--auto-merge` / `--no-auto-merge` rows, the `^` form on `--file-ref`, and a new § "Folding tasks that reference the same files".
> | 
> | Leftovers seen while checking facts:
> | - commands/codeagent.md:179 calls `--headless` a "No-op for other agents/operations", but aitask_codeagent.sh:45-47, 605-607 requires it for explore-relay, relations and obsolescence. t2286 also lists this.
> | - commands/note.md is tagged intermediate but carries status codes and outcome tables, so it probably wants advanced.
> | - skills/aitask-wrap.md has relative links, an em-dash-heavy capability list, and a When-to-Use table that duplicates workflows/retroactive-tracking.
> | - skills/aitask-pick/_index.md:28 lists the premise evidence classes at intermediate; development/premise-staleness#evidence now owns them.
> | - skills/aitask-explore.md does not mention the free-text "Other" goal (feature/medium).
