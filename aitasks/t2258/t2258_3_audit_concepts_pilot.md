---
priority: medium
effort: high
depends: [t2258_2]
issue_type: documentation
status: Implementing
labels: [documentation, web_site, doc_quality]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2258
implemented_with: claudecode/opus5_5
created_at: 2026-11-09 23:09
updated_at: 2026-11-10 22:35
---

## Context

Child 3 of t2258 — the **pilot audit**. Read the parent task
`aitasks/t2258_doc_audience_levels_and_readable_prose.md` (evidence section:
concept-page violations) and the approved parent plan
`aiplans/p2258_doc_audience_levels_and_readable_prose.md`, in particular the
**Common audit method (children 3–7)** and the Pre-phase step
`reader_test_baseline_and_control`, both binding here. Child 1 put the level
model and prose rules in `aitasks/metadata/doc_update_guide.md`; child 2 built
`.claude/skills/aitask-doc-review/SKILL.md`. This child applies them to
`website/content/docs/concepts/` (25 pages) first, so lessons reach the guide
before the larger audits.

Known violations (measured 2026-11-09): `concepts/locks.md` (main-concept, 127
lines, opens with a 7-row lock-outcome table), `gates.md` (237 lines, 8 `###`),
`framework-session.md` (198), `skill-templating.md` (190), `attachments.md`
(164), `topic-anchoring.md` (main-concept, 141). Models: `tasks.md`, `plans.md`,
`folded-tasks.md`, `execution-profiles.md` (28–80 lines). Even `tasks.md`
enumerates frontmatter fields under "What it is" — check the models too.

## Pre-phase (risk mitigation) — reader_test_baseline_and_control

1. Before restructuring any page, run the fresh-reader test (via
   `aitask-doc-review`, `main-concept` persona) on the six long pages above
   **and** on `tasks.md` and `plans.md` as controls. Record every report
   verbatim in this child's plan.
2. If the reports do not separate the long pages from the controls (more
   guessed terms / unneeded details on the long pages), stop and tune the
   persona and question set in `aitask-doc-review` before restructuring.
3. After restructuring, re-run on the same eight pages and record the
   after-reports (child 8 compares them).

## Method (from the parent plan; summary)

1. Inventory all 25 pages in the plan: lines, `depth`, page type, verdict,
   violations (Diátaxis anti-patterns 1/2/5 first, then 3/4; the guide's level
   contract; the prose rules).
2. Shared-file gate before each edit: diff against HEAD; a page dirty from
   another session is not edited — record it in a **skipped-page ledger**
   (path, reason, dirty state seen). Before closing, re-check each entry; now
   clean → audit it here; still dirty → create a child of t2258 with
   `--no-sibling-dep` named `audit_deferred_pages_concepts` listing pages,
   violations and reason. Final Implementation Notes record each entry's
   outcome (`audited` / `follow-up t2258_<n>`); do not archive otherwise.
3. Restructure: mechanism moves to the page that owns it (workflow, command,
   skill, reference page, or `aidocs/` for contributor-only internals); keep the
   concept page to what / why / how-to-use / see-also. Record every moved fact
   (source → destination#anchor) in the plan.
4. `aitask-doc-review` on each edited page.
5. `cd website && python3 check_links.py --build` (mandatory);
   `python3 check_link_relevance.py` for retargeted links, opening every
   reported target.
6. Rule refinements go back into the guide's examples.

## Verification

- Inventory table, moved-fact table, before/after reader reports and the
  skipped-page ledger outcomes are in the plan.
- `check_links.py --build` exits 0.
- Every concept page has `depth:`; every `main-concept` concept page passes the
  guide's forbidden-content list.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2258_1** id=2026-11-10T11:32:44Z.d949c61ec58ca16bdda35a9d from=t2258_1 from_verified=yes at=2026-11-10T11:32:44Z base=b93a5f2582ceaeff7401415a25a8936cc7b29e90 base_branch=main dirty=yes host=omg16
>
> | Advisory, from t2258_1 (level model + prose rules, committed c06040c1d; guide on the task-data branch).
> | 
> | concepts/tasks.md is a weak reader-test control for your reader_test_baseline_and_control step. Against the new main-concept contract in aitasks/metadata/doc_update_guide.md it breaks two rules: its opening (line 11) lists eight frontmatter field names (priority, effort, status, depends, boardcol, issue_type, labels, assigned_to) on a page about tasks, and it never explains "YAML frontmatter". A fresh-reader classification run in t2258_1 (sub-agent given only the guide + page) flagged exactly that, plus CLI/TUI/LLM/Kanban undefined, verdict "minor issues". So expect findings on tasks.md rather than a clean report, or add a compliant control (t2258_1 used a ~28-line scratch "Labels" concept page, which came back nearly clean).
> | 
> | The same run gives a ready "before" baseline: locks.md flagged for outcome tables (l.19-27, 43-48), status lines, internal paths, ### under "What it is", ~128 lines; gates.md (held out, not quoted in the guide) flagged for eight ### under "What it is", resolution/digest rules belonging on reference pages, ~238 lines. Details in the archived plan p2258_1, Final Implementation Notes.

> **✉ note:t2258_2** id=2026-11-10T14:18:07Z.f7b923ac1b0eb28cd7108144 from=t2258_2 from_verified=yes at=2026-11-10T14:18:07Z base=2f816eabe5d2bf807b62aac35edbeaa31f55f9b8 base_branch=main dirty=yes host=omg16
>
> | The review skill that t2258_2 built is named `aitask-docs-review` (renamed at review, to match `aitask-docs-gap`), not `aitask-doc-review` as this task's body and plan say.
> | - Skill: .claude/skills/aitask-docs-review/SKILL.md
> | - Invocation: /aitask-docs-review <page>... [--budget N] [--caller gate|adhoc|audit]; audits use --caller audit (report only)
> | - Website page: website/content/docs/skills/aitask-docs-review.md
> | - Contract test: tests/test_docs_review_contract.sh
> | Read every `aitask-doc-review` reference in this task as `aitask-docs-review`.

> **👁 note:read** id=2026-11-10T16:24:08Z.5d2d5875084ec3077c7d29a1 by=t2258_3 at=2026-11-10T16:24:08Z mode=explicit ids=2026-11-10T11:32:44Z.d949c61ec58ca16bdda35a9d,2026-11-10T14:18:07Z.f7b923ac1b0eb28cd7108144

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-10T20:35:16Z status=pass attempt=1 type=human
