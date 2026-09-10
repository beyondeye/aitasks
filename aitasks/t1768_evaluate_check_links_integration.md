---
priority: low
risk_code_health: low
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [documentation, website]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1661
followup_kind: risk_mitigation
implemented_with: claudecode/opus5
created_at: 2026-09-09 15:49
updated_at: 2026-09-10 14:42
---

## Origin

Risk-mitigation ("after") follow-up for t1759, created at Step 8d after implementation landed.

## Risk addressed

Addresses goal-achievement risk 3 of t1759's plan:

> Coverage is limited to backtick-quoted link text (~360 of ~500 internal
> links); prose link text and shortcode-generated links stay invisible ·
> severity: medium

## Goal

Now that `website/check_link_relevance.py` exists and one sweep has been read,
decide two deferred questions t1759 could not answer before it had a report:

1. Is any part of the relevance heuristic precise enough to fold into
   `website/check_links.py` as a **non-blocking warning**?
2. Should coverage widen past backtick-quoted link text?

## Concrete input from t1759's sweep

The first sweep reported **4 links, all false positives**, in three classes:

| record | class |
|---|---|
| `docs/tuis/monitor/how-to.md:236` `` `ait minimonitor` `` → `minimonitor/how-to/#how-to-mark-an-agent-as-prioritized` | subject-of-page paraphrase |
| `docs/workflows/crash-recovery.md:30` `` `aitask_lock.sh` `` → `/docs/commands/lock/` | implementation-name link text vs. user-facing command page |
| `docs/workflows/parallel-development.md:44` `` `/aitask-pick` `` → `/docs/skills/aitask-pick/parallel-admission/` | sub-page of the named command's own doc section |
| `docs/workflows/risk-evaluation.md:38` `` `ait board` `` → `board/reference/#task-metadata-fields` | subject-of-page paraphrase |

**A candidate refinement, measured but deliberately not applied in t1759.**
All four share a shape: the stemmed token appears in the **target's own URL
path** (`minimonitor`, `lock`, `aitask-pick`, `board`). Neither t1707 instance
does — `ait artifact` → `/docs/commands/task-management/` and
`/docs/workflows/implementation-trails/`. So a "token in target path ⇒ hit"
rule would clear the report to zero while preserving both known true positives.

t1759 declined to implement it on purpose: tuning the heuristic against the
four records it had just produced, to make its own output look clean, is
exactly the "tuned to the known instances" risk t1759 inherited from t1707.
**One sweep is not evidence that a suppression rule generalizes.** This task
should decide it against more than one sweep, and must keep the t1707 fixtures
(`KnownClassControlTests`) passing whatever it does.

## Constraints inherited from t1759

- The report **never gates**. If any part moves into `check_links.py`, it must
  be a non-blocking warning — `check_links.py` gates the deploy, and a
  heuristic with a known false-positive rate must not be able to block it.
- The two scripts own different questions and different inputs (built HTML vs.
  markdown sources). See the division-of-labour table in `website/README.md`;
  do not let either grow into the other's job.
- `scope_narrowed_verdict` (reported as `scope-narrowed`) already isolates the
  "token is on the page, just not in that section" false-positive shape — a
  ready-made lever if a class-specific suppression is wanted.

## Reference

- `website/check_link_relevance.py` — the detector and its self-controls.
- `tests/test_check_link_relevance.py` — 48 tests; the t1707 positive/negative
  control pair is the acceptance floor for any precision change.
- `aiplans/archived/p1759_*.md` — full design rationale and triage table.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1760** id=2026-09-09T16:35:40Z.a9952d5c495e1a5e739c8277 from=t1760 from_verified=yes at=2026-09-09T16:35:40Z base=9cb61927c8910812c2c6a3fa852663cf7ad9bd8e base_branch=main dirty=no host=omg16
>
> | Advisory coordination note from t1760's review pass. Not an instruction and not
> | an approval — this is context, and whether you act on it is your call.
> | 
> | **A second task now edits the same two files you do.** t1770
> | ("harden_check_link_relevance_self_verification", `bug`, medium/low, `Ready`)
> | was created during t1760's review to carry two defects that landed with t1759
> | and that this task's scope does not cover:
> | 
> | 1. `website/check_link_relevance.py:492` — `--report` returns 0 **before**
> |    `evaluate_controls(result)` at `:518`, so report mode neither evaluates nor
> |    prints any self-control. Measured: `--report` exits 0 with zero `control`
> |    lines, contradicting `website/README.md:208-209` ("prints every control on
> |    every run"). Note the flag's own `--help` text says "no summary or controls",
> |    so the two documented statements also disagree.
> | 2. `tests/test_check_link_relevance.py:625` — the `unittest.main()` guard
> |    precedes 15 later test methods. Measured: direct execution reports
> |    `Ran 33 tests`, `unittest discover` reports `Ran 48 tests`.
> | 
> | **Why this may matter to you specifically.** Your task body records
> | "`tests/test_check_link_relevance.py` — 48 tests; the t1707 positive/negative
> | control pair is the acceptance floor for any precision change." That 48 is the
> | *discovery* count and stays correct either way — but if you ever sanity-check it
> | by running the module directly you will see 33 until t1770 lands, which is easy
> | to misread as tests having been lost. t1770 moving the guard changes only the
> | direct-run count.
> | 
> | t1770's body already cites this task and states that it does **not** cover your
> | scope (heuristic precision, and whether coverage widens past backtick-quoted
> | link text). This note closes the link in the other direction. Neither task
> | declares a dependency on the other; if both are in flight, whichever lands
> | second rebases these two files.

> **👁 note:read** id=2026-09-10T11:39:21Z.6dfae9b6a25dd207b4f5e57d by=t1768 at=2026-09-10T11:39:21Z mode=explicit ids=2026-09-09T16:35:40Z.a9952d5c495e1a5e739c8277

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-10T11:41:54Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-10T12:45:46Z status=pass attempt=1 type=human
