---
priority: high
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: [t1687_4]
issue_type: documentation
status: Done
labels: [documentation, website, concepts]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1687
implemented_with: claudecode/opus5_5
created_at: 2026-09-20 12:02
updated_at: 2026-09-24 22:19
completed_at: 2026-09-24 22:19
---

## Context

Final child of t1687 (Concepts docs gap sweep). Siblings t1687_1..t1687_4 each
write their concept pages **and their own back-links**, but none of them touches
`website/content/docs/concepts/_index.md`. This task reconciles that index,
repairs the reading chain, and runs the whole verification block.

It runs last by sibling auto-dependency, which is deliberate:
`concepts/_index.md` is **contended** — t1231_3 and t635_18 both plan to edit it
(t1705_10's edit already landed). Landing one consolidated regroup spares both a
rebase, and editing it once rather than five times avoids self-conflict.

## Key files to modify

- `website/content/docs/concepts/_index.md` — the only file this task owns
  outright.
- Whichever sibling pages need a `**Next:**` footer adjustment (see below).

## Six new pages to index

| Page | Weight | Group |
|---|---|---|
| `concepts/task-notes.md` | 45 | Data model |
| `concepts/attachments.md` | 55 | Data model |
| `concepts/gates.md` | 85 | Workflow primitives |
| `concepts/implementation-trails.md` | 105 | Lifecycle and infrastructure |
| `concepts/cross-repo-references.md` | 115 | Lifecycle and infrastructure |
| `concepts/shadow-agent.md` | 125 | Workflow primitives |

All six sit on free `+5`-grid slots; **no existing page is renumbered** (that
was a deliberate choice to keep the rebase surface small for t1231_3/t635_18).

`shadow-agent` (125) is the one page whose weight falls outside its group's
band. This is fine and has precedent: `_index.md` grouping is hand-ordered and
already independent of weight — agentcrews (75) is listed after agent-attribution
(80), and framework-session (95) after The IDE model (120). Note it rather than
"fixing" it by renumbering.

## Bullet shape (copy exactly)

```
- **[Tasks]({{< relref "/docs/concepts/tasks" >}})** — Markdown files with YAML frontmatter, one per unit of work.
```

Link text = the page's `linkTitle`. Blurb = a lightly reworded `description`,
capitalized, ending in a period. Em dash with spaces. No `.md`, no trailing
slash, always the full `/docs/...` path.

## The `**Next:**` reading chain

14 of the 17 existing pages form a linear chain via a `**Next:**` footer;
`topic-anchoring.md`, `agentcrews.md` and `framework-session.md` sit outside it.
Adding six more orphans would leave 9 of 23 pages off the chain and make it
actively misleading.

- Splice the six new pages into the chain in weight order.
- Close the two pre-existing skips: `parent-child.md` currently points past
  `topic-anchoring.md`, and `ide-model.md` past `framework-session.md`.

**This item is the one piece beyond a literal reading of t1687's scope.** It was
approved at planning as serving "the section still reads in a sensible
progression", and it is easy to drop: if it looks like scope creep when you get
here, skip it and note the decision — the rest of this task stands alone.

## Orphan check — both directions

- Every `.md` in `website/content/docs/concepts/` (except `_index.md`) appears
  exactly once in `_index.md`.
- Every bullet in `_index.md` resolves to a file that exists.

Both directions were clean before this sweep (17 files ↔ 17 bullets); they must
be clean after (23 ↔ 23).

## Verification (the full block for the whole t1687 sweep)

```bash
cd website && hugo build --gc --minify
cd website && python3 check_links.py --build
cd website && python3 check_link_relevance.py
```

- `hugo build` fails a dead **or ambiguous** relref. Ambiguity matters here:
  three new slugs (`task-notes`, `implementation-trails`, `shadow-agent`)
  collide with same-named workflow pages, so any bare relref must be caught.
- `check_links.py` catches dead `#fragment` targets and hand-written relative
  paths that the build lets through.
- `check_link_relevance.py` is a **report, not a gate** — reported links never
  change its exit status, and false positives are expected (t1759's first sweep
  reported 4, all four triaged as false positives). Only a failed self-control
  makes it exit non-zero.

**Piping discards the exit status** — use `set -o pipefail` or check
`${PIPESTATUS[0]}`.

Also confirm:
- `website/content/docs/concepts/` still contains **zero** hand-written relative
  links (it had none before this sweep);
- every anchor named in t1687's reciprocal link map still exists;
- no mermaid fence was introduced anywhere (the site has no mermaid support, so
  one would build green and render as a plain code block).

## Post-phase risk mitigation — link_relevance_triage

Run `check_link_relevance.py` and walk **every link added by t1687_1..t1687_5**,
not just the reported ones. The failure class it targets — a link resolving to a
real page that never discusses the subject — passes both `hugo build` and
`check_links.py`, and is exactly the defect t1707 found by hand in two
`ait artifact` links. Record the triage outcome.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1687_1** id=2026-09-22T13:59:29Z.319e38c07adff5789520d9e5 from=t1687_1 at=2026-09-22T13:59:29Z base=15a1f9f66a3def24e2c541692e71a5d313174b98 base_branch=main dirty=no host=omg16
>
> | t1687_1 wrote website/content/docs/concepts/gates.md (weight 85, "Workflow
> | primitives", depth [advanced]). Two things your task body does not yet reflect:
> | 
> | 1. FOURTH SLUG COLLISION. Your verification section lists three new slugs that
> |    collide with same-named pages (task-notes, implementation-trails,
> |    shadow-agent). concepts/gates.md adds a fourth: it shares the `gates` slug
> |    with commands/gates.md (a commands page, not a workflow page). As of the
> |    commit below, no bare `relref "gates"` exists anywhere under
> |    website/content/ — every relref uses the full /docs/... path — and
> |    hugo build + check_links.py pass. Any bullet you add to _index.md needs the
> |    full "/docs/concepts/gates" path.
> | 
> | 2. NEXT-CHAIN SPLICE POINT. The page deliberately ends at `## See also` with no
> |    `---` / `**Next:**` footer, because your task owns the reading chain. By
> |    weight it sits between agent-attribution (80, currently -> locks) and
> |    locks (90).
> | 
> | Tree-relative claims are dated by this note's base SHA. The page itself is in
> | commit 15a1f9f66 on main, which, as of this moment, is committed locally but
> | not yet pushed; t1687_1's Step 9 is expected to push it. Advisory only —
> | verify before acting.

> **✉ note:t1687_3** id=2026-09-23T14:01:44Z.7411418da602481782982311 from=t1687_3 from_verified=yes at=2026-09-23T14:01:44Z base=a9b93ff989075f7e493b749bf0b76044f701c588 base_branch=main dirty=yes host=omg16
>
> | t1687_3 landed two Concepts pages that your `_index.md` regroup must place, and
> | hit one build trap worth knowing before you write a single relref.
> | 
> | Tree-relative (dated by this note's base SHA):
> | 
> | - NEW `website/content/docs/concepts/task-notes.md` — weight **45**. Sits in
> |   *Data model*, between topic-anchoring (40) and review-guides (50).
> | - NEW `website/content/docs/concepts/cross-repo-references.md` — weight **115**.
> |   Sits in *Lifecycle and infrastructure*, between git-branching-model (110) and
> |   ide-model (120).
> | - Neither page is listed in `concepts/_index.md` — t1687_3 deliberately did not
> |   touch that file, since it is yours. Both are therefore orphans in the
> |   "_index.md lists every page" check until you add them.
> | - Neither page carries a `**Next:**` footer. Both end at `## See also`, the same
> |   shape t1687_2 left `attachments.md` in for the same reason.
> | 
> | The trap: `/docs/concepts/task-notes` collides with the pre-existing
> | `/docs/workflows/task-notes`. A bare `{{< relref "task-notes" >}}` is ambiguous
> | and FAILS `hugo build` outright. Always write the full `/docs/...` path. This is
> | the one class of dead link that the build catches and `check_links.py` alone
> | would not.
> | 
> | Two smaller things, as of this commit:
> | 
> | - `check_link_relevance.py` reports `concepts/task-notes.md:44` (`ait note` ->
> |   /docs/commands/note/ [#provenance]). It is a false positive — the extractor
> |   takes the leading code span as the label and matches it against the anchor
> |   subject. Four pre-existing links on the site report the same way
> |   (gates.md:229, tuis/monitor/how-to.md:236, workflows/risk-evaluation.md:38).
> |   Re-ordering the label does not clear it; that was tried and measured.
> | - t1687_3 also corrected `workflows/multi_project.md` line ~143, which claimed
> |   `--project` cannot be combined with `--parent`. It can; the parent resolves in
> |   the target project. If your ordering pass moves or rewrites that section, keep
> |   the corrected wording.
> | 
> | Advisory only — verify anything you depend on against the tree you actually
> | have.

> **👁 note:read** id=2026-09-24T06:52:49Z.96b2c361be0942909cee4525 by=t1687_5 at=2026-09-24T06:52:49Z mode=explicit ids=2026-09-22T13:59:29Z.319e38c07adff5789520d9e5,2026-09-23T14:01:44Z.7411418da602481782982311

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-24T12:29:16Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-24T18:59:09Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-09-24T19:19:33Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:a9598418eafe0f6b

> **✅ gate:risk_evaluated** run=2026-09-24T19:19:33Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1687_5/risk_evaluated_2026-09-24T19:19:33Z-risk_evaluated-a1.log`
