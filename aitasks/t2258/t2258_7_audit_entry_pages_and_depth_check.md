---
priority: medium
effort: medium
depends: [t2258_6]
issue_type: documentation
status: Ready
labels: [documentation, web_site, doc_quality]
gates: [risk_evaluated]
anchor: 2258
created_at: 2026-11-09 23:09
updated_at: 2026-11-09 23:09
---

## Context

Child 7 of t2258: audit the entry pages — `website/content/docs/overview.md` (explanation, main-concept), `getting-started.md` (tutorial), `installation/` (9 pages), `development/` (task-format, review-guide-format, pypy, skills/), and every section `_index.md`. Then make `depth` required: add a check (a small script under `website/`, or a flag on an existing checker) that fails when a leaf page under `website/content/docs/` (not `_index.md`) lacks `depth:`, wire it into `.github/workflows/hugo.yml` beside `check_links.py`, and document it in `website/README.md` and CLAUDE.md's Website section. Untagged pages at planning time (2026-11-09): `installation/{pypy,linux,updating-model-lists}.md`, `development/pypy.md`, `tuis/applink/{how-to,reference}.md` plus section indexes — earlier audit children tag their own sections; this child tags the rest and runs the check over the whole tree. Include a negative control (a scratch page without `depth:` makes the check fail).

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

> **✉ note:t2258_1** id=2026-11-10T11:32:49Z.1aa3d4d1387a7a71d1cf9729 from=t2258_1 from_verified=yes at=2026-11-10T11:32:49Z base=b93a5f2582ceaeff7401415a25a8936cc7b29e90 base_branch=main dirty=yes host=omg16
>
> | Advisory, from t2258_1. The new "Reader levels" section in aitasks/metadata/doc_update_guide.md says: every leaf page sets depth, and a directory's _index.md sets it too when it has content of its own (such as a TUI overview); an _index.md that only lists and links its pages may leave it out. As of commit c06040c1d the tree already matches this: the content-bearing _index.md pages (all tuis/<name>/_index.md, skills/aitask-pick/_index.md, workflows/screen-recordings/_index.md) carry depth, and the link-list ones (commands/, concepts/, development/, installation/, skills/, tuis/, workflows/, the root) do not. Your depth-required check needs to decide whether it enforces the content-bearing _index.md case or only leaf pages; if only leaf pages, consider softening the guide sentence to match.
