---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: high
depends: [t2258_4]
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
created_at: 2026-11-12 11:39
updated_at: 2026-11-12 23:21
completed_at: 2026-11-12 23:21
---

## Context

Child of t2258 (reader levels and readable prose for the website docs). It was
split out of t2258_4 (workflows audit) at that task's planning on 2026-11-12.
The workflows section is 44 pages and about 5,700 lines, too much for one
session, so the user chose to split it into six parts run fully sequentially:
t2258_4 (Tasks, Reporting, Maintenance), then the five split children, then
t2258_5 (TUIs), 6, 7 and 8.

This child audits and restructures the **Parallel group, local part** of
`website/content/docs/workflows/`:

| Page | Lines | depth |
|---|---|---|
| `freeze-and-restore-agents.md` | 316 | intermediate |
| `crash-recovery.md` | 188 | intermediate |
| `implementation-trails.md` | 162 | advanced |
| `sitrep.md` | 133 | intermediate |
| `parallel-planning.md` | 76 | advanced |
| `parallel-development.md` | 75 | advanced |

`freeze-and-restore-agents` (316 lines) is also the guide's AI-tell prose sample: several of the guide's avoid-list examples are quoted from it. `crash-recovery` has 6 `###` subsections.

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
   `audit_deferred_pages_workflows_parallel_local` listing pages, violations and
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

- **t2284 owns the `crash-recovery.md:71` re-claim wording.** The page says a session re-claiming its own lock refreshes it silently, but `aitask_pick_own.sh` still emits `RECLAIM_STATUS` for an `Implementing` task. While t2284 is open, do not change that sentence. Check t2284's status first; if it has landed, audit its new wording like any other text.
- **Facts moved in by t2258_3** (concepts pilot): `crash-recovery` received the lock-outcome and session-liveness facts from `concepts/locks`, and its See also points to `development/gates#the-ledger`. `parallel-development` § Serialized Merge-Back is now the intermediate summary of `development/merge-mutex.md`. `freeze-and-restore-agents` had framework-session prose edited. The source record is the moved-fact table in `aiplans/archived/p2258/p2258_3_audit_concepts_pilot.md`. Do not move these facts back onto concept pages.
- `sitrep` and `implementation-trails` have TUI pages (`tuis/sitrep/`, `tuis/trails/`) owned by t2258_5. Moving behaviour detail there is fine; t2258_5 audits them later.

## Verification

- The plan holds the inventory, the moved-fact table, the survival-check counts
  and the ledger outcomes.
- `check_links.py --build` exits 0.
- Every leaf page in this group has `depth:`.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2258_4** id=2026-11-12T13:41:21Z.6c718059468ffe31d070baae from=t2258_4 from_verified=yes at=2026-11-12T13:41:21Z base=86d4f4aba660abfb560be589d704b42b20b9a61f base_branch=main dirty=yes host=omg16
>
> | Advisory from t2258_4 for your group. check_link_relevance flags workflows/crash-recovery.md:30 (`aitask_lock.sh` -> commands/lock) and workflows/parallel-development.md:46 (`/aitask-pick` -> skills/aitask-pick/parallel-admission); triage them in your audit. crash-recovery.md:71 still belongs to t2284.

> **👁 note:read** id=2026-11-12T13:49:31Z.38ab69bf4419594c78d72a61 by=t2258_9 at=2026-11-12T13:49:31Z mode=explicit ids=2026-11-12T13:41:21Z.6c718059468ffe31d070baae

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-12T17:40:38Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-12T21:09:44Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-12T21:21:06Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:179f5113aaa3a69a

> **✅ gate:risk_evaluated** run=2026-11-12T21:21:06Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2258_9/risk_evaluated_2026-11-12T21:21:06Z-risk_evaluated-a1.log`
