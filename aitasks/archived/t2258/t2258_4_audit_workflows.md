---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: high
depends: [t2258_3]
issue_type: documentation
status: Done
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
updated_at: 2026-11-12 15:41
completed_at: 2026-11-12 15:41
---

## Context

Child 4 of t2258: audit and restructure `website/content/docs/workflows/` (44 pages, incl. `contribute-and-manage/` and `screen-recordings/`). Workflow pages are how-tos that blend overview, steps and internals. Longest first (2026-11-09): `bug-report-intake.md` 336, `freeze-and-restore-agents.md` 316 (also the AI-tell prose sample), `manual-verification.md` 256, `shadow-agent.md` 249, `cross_project_dependencies.md` 236, `contribute-and-manage/contribution-flow.md` 235, `multi_project.md` 216, `crash-recovery.md` 188. Remember the hand-curated body list in `workflows/_index.md` when splitting or adding pages. `contribute-and-manage/contribution-flow.md` was dirty from another session at planning time — apply the shared-file gate. If the inventory shows this is too large for one session, create additional children of t2258 at planning (one per workflow group) rather than shipping a partial audit.

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

> **✉ note:t2258_2** id=2026-11-10T14:18:09Z.ce4b2042150a2b416728cf15 from=t2258_2 from_verified=yes at=2026-11-10T14:18:09Z base=2f816eabe5d2bf807b62aac35edbeaa31f55f9b8 base_branch=main dirty=yes host=omg16
>
> | The review skill that t2258_2 built is named `aitask-docs-review` (renamed at review, to match `aitask-docs-gap`), not `aitask-doc-review` as this task's body and plan say.
> | - Skill: .claude/skills/aitask-docs-review/SKILL.md
> | - Invocation: /aitask-docs-review <page>... [--budget N] [--caller gate|adhoc|audit]; audits use --caller audit (report only)
> | - Website page: website/content/docs/skills/aitask-docs-review.md
> | - Contract test: tests/test_docs_review_contract.sh
> | Read every `aitask-doc-review` reference in this task as `aitask-docs-review`.

> **✉ note:t2258_3** id=2026-11-12T06:51:10Z.5f4acf693ab7120a7a441386 from=t2258_3 from_verified=yes at=2026-11-12T06:51:10Z base=7f1f4333a3379c4641e0a4b85281072e25ea2240 base_branch=main dirty=yes host=omg16
>
> | Advisory from t2258_3 (concepts pilot), committed in 7f1f4333a. Your workflows pages received moved facts and link changes:
> | - crash-recovery.md: lock-outcome and session-liveness facts moved in from concepts/locks. Its See also now points to development/gates#the-ledger for the Gate Runs ledger.
> | - parallel-development.md: § Serialized Merge-Back is now the intermediate summary. The full mutex reference is the new development/merge-mutex.md.
> | - freeze-and-restore-agents.md: framework-session prose was edited when the concept page was cut.
> | - task-notes.md: See also now points to commands/lock#how-it-works for the lock record live delivery reads.
> | Open item: crash-recovery.md:71 says a same-session re-claim refreshes silently. aitask_pick_own.sh:782-806 still emits RECLAIM_STATUS for an Implementing task, so the re-pick is not silent. This is tracked in t2284, which you may want to coordinate with.
> | The guide now has a detail-placement boundary: behaviour detail on reference/workflow pages, public architecture in development/ at advanced, contributor-only detail in aidocs/. See aiplans/archived/p2258/p2258_3_*.md.

> **👁 note:read** id=2026-11-12T08:05:12Z.3dcad23042908634b265340a by=t2258_4 at=2026-11-12T08:05:12Z mode=explicit ids=2026-11-10T14:18:09Z.ce4b2042150a2b416728cf15,2026-11-12T06:51:10Z.5f4acf693ab7120a7a441386

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-12T09:38:00Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-12T11:04:57Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-12T13:41:36Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:4c8da47069e45c35

> **✅ gate:risk_evaluated** run=2026-11-12T13:41:36Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2258_4/risk_evaluated_2026-11-12T13:41:36Z-risk_evaluated-a1.log`
