---
priority: medium
effort: high
depends: [t2258_10]
issue_type: documentation
status: Ready
labels: [documentation, web_site, doc_quality]
gates: [risk_evaluated]
anchor: 2258
created_at: 2026-11-12 11:39
updated_at: 2026-11-12 11:39
---

## Context

Child of t2258 (reader levels and readable prose for the website docs). It was
split out of t2258_4 (workflows audit) at that task's planning on 2026-11-12.
The workflows section is 44 pages and about 5,700 lines, too much for one
session, so the user chose to split it into six parts run fully sequentially:
t2258_4 (Tasks, Reporting, Maintenance), then the five split children, then
t2258_5 (TUIs), 6, 7 and 8.

This child audits and restructures the **Review & Quality group** of
`website/content/docs/workflows/`:

| Page | Lines | depth |
|---|---|---|
| `manual-verification.md` | 256 | intermediate |
| `shadow-agent.md` | 249 | intermediate |
| `upstream-defect-followup.md` | 133 | intermediate |
| `qa-testing.md` | 119 | intermediate |
| `explain.md` | 104 | intermediate |
| `risk-evaluation.md` | 99 | intermediate |
| `code-review.md` | 88 | intermediate |

`shadow-agent` has 13 `###` subsections under 5 `##`. `manual-verification` has 7 `###`. Both are restructure candidates.

## Read first

- The parent task `aitasks/t2258_doc_audience_levels_and_readable_prose.md` and
  its plan `aiplans/p2258_doc_audience_levels_and_readable_prose.md`
  (§ "Common audit method (children 3–7)", which binds this child too).
- The archived plans of t2258_3 (concepts pilot) and t2258_4, and of every
  earlier workflows split child, under `aiplans/archived/p2258/`. They hold the
  lessons, inventory and moved-fact tables, the survival-check method and the
  guide changes made so far.
- `aitasks/metadata/doc_update_guide.md`: "Reader levels", "Page types", "How
  a subject spans levels" (including the detail-placement boundary: behaviour
  detail → reference or workflow page; public architecture → `development/`
  at `advanced`; contributor-only → `aidocs/`) and "Prose rules".
- The review skill: `.claude/skills/aitask-docs-review/SKILL.md`, invoked as
  `/aitask-docs-review <page>... --caller audit --budget N` (report only).

## Method (binding)

1. Inventory every page of this group in the plan: lines, `depth`, page type,
   verdict, violations (Diátaxis anti-patterns 1/2/5 first, then 3/4; the
   guide's level contract; the prose rules).
2. Shared-file gate before each edit, on source and destination pages alike:
   `git diff --quiet HEAD -- <page>` and `git status --short -- <page>`. A page
   that is dirty from another session is not edited. Record it in a
   **skipped-page ledger** (path, reason, dirty state seen). Before closing,
   re-check each entry: if it is now clean, audit it here; if it is still
   dirty, create a child of t2258 with `--no-sibling-dep` named
   `audit_deferred_pages_workflows_review_quality` listing pages, violations and
   reason. Final Implementation Notes record each entry's outcome (`audited` /
   `follow-up t2258_<n>`, or "ledger empty"). Do not archive otherwise.
3. Restructure: move mechanism to the page that owns it; split mixed pages;
   keep each workflow page a how-to (goal, steps, outcome). Check every moved
   fact against the code, and record each move in the plan (source#section →
   fact → destination#anchor → `moved` / `already-stated` / `corrected` /
   `dropped(reason)`).
   - Before marking any script output, status line or flag contributor-only,
     check whether the site tells readers to call that script and whether its
     `--help` documents the output. If so, it is public architecture and goes
     to an `advanced` reference page, not to `aidocs/` (t2258_4 plan review).
   - Avoid adding table rows to `development/task-format.md`:
     `tests/lib/docs_vocabulary_scan.py` reads every row there as a
     frontmatter field.
4. Run `aitask-docs-review` on each edited or created page, under the final
   guide. Fresh-reader runs only on `main-concept` pages, within the budget.
5. Run `cd website && python3 check_links.py --build` (mandatory) and
   `python3 check_link_relevance.py` for added or retargeted links. Open every
   reported target. Also run `bash tests/test_website_doc_lists.sh` when a page
   is added or moved.
6. Rule refinements go back into the guide's examples, not into ad-hoc page
   fixes. Keep the `## Reader levels` interface lines byte-identical, then run
   `bash tests/test_docs_review_contract.sh`.
7. Every leaf page in this group has `depth:`.
8. Before committing, run the claim-level survival check from the pilot: list
   every removed block (paragraph, list item, table row, admonition, code
   block) per edited page, and have an independent sub-agent classify each
   claim as preserved (quoted), weakened or missing against its destinations.
   Fix or record every gap. Write generated files directly; never pipe them
   through `tee | head`.

**`workflows/_index.md`:** its body is a hand-curated grouped list. Edit only
this group's list, keep each page's position and `**Next:**` footer, and add a
bullet for any new or split page.

## Coordination

- **In-flight shadow-agent work:** at t2258_4's planning (2026-11-12), another session held uncommitted changes to `aidocs/framework/shadow_agent.md` and `.aitask-scripts/monitor/*` (review loop / recheck composer). Before editing `shadow-agent.md`, check `git status` and the in-flight shadow tasks. If that work has landed, re-check the page against it; if still dirty, gate as usual.
- `manual-verification.md` prose follows the guide's "Autonomous, not auto-execution" convention (canonical heading `## Autonomous verification`).
- `concepts/shadow-agent.md` (intermediate) already exists. Keep the concept page and this workflow page in their own roles.

## Verification

- The plan holds the inventory, the moved-fact table, the survival-check counts
  and the ledger outcomes.
- `check_links.py --build` exits 0.
- Every leaf page in this group has `depth:`.
