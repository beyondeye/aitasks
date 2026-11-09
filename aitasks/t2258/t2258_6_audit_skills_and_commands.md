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
