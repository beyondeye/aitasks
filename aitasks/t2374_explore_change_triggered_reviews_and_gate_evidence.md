---
priority: medium
effort: medium
depends: [2369]
issue_type: enhancement
status: Ready
labels: [gates, workflow]
anchor: 2258
created_at: 2026-11-27 01:53
updated_at: 2026-11-27 01:53
---

## Context

t2369 adds a documentation-specific review to the attended Step 8 feedback loop. It derives the task's documentation paths from the change surface and proposes per-page evidence tied to the reviewed contents and effective guide. Matching evidence can be reused, including compatible results from `docs_updated`. The existing human commit approval remains part of the workflow.

Other changes may need specialized implementation-review rules or gates. For example, changing a public CLI flag or configuration schema may warrant compatibility review, checks for documented behavior, and targeted tests. Explore whether t2369's approach can support a second real case and fit the existing gate architecture.

## Scope

- Trace the current flow from task-attributed changes (`aitask_change_surface.sh`) to the standard Step 8 review, active gate selection, procedure dispatch, human approval, commit and resume. Check what is already implemented and what remains in the t635 gate roadmap.
- Use documentation and one concrete public CLI or configuration compatibility case from this repository. For each, define how the relevant changes are detected, which rules or verifiers apply, and how multiple applicable reviews compose with the standard review. Decide how the project or task opts in and how uncertain file attribution is handled in shared checkouts.
- Define the minimum inputs that identify valid review evidence. Consider the reviewed paths and contents, policy or procedure version, and related implementation inputs that affect the result. Evaluate whether existing dependency or path signals can identify those inputs. Explain reuse and invalidation for feedback edits, renames, policy changes, and unrelated edits.
- Compare a Step 8 extension backed by the current gate framework with adding scoped freshness to registered procedure gates and their evidence. Specify when findings are advisory, when they block a commit or archival, how stale results are refreshed on resume, and how the commit path validates the evidence against what it commits while keeping human approval.
- Coordinate with t635_29 (procedure-gate dispatch), t635_17 (autonomous-lane enforcement), and t635_28 (default activation of `docs_updated`). Identify work those tasks already own and distinguish actual prerequisites from work that can proceed independently.

## Deliverable and acceptance criteria

- Produce a design comparison and recommendation. A documentation-specific mechanism is a valid conclusion if the two cases do not justify shared machinery. Implementation is outside this task's scope.
- Walk through a feedback round where a CLI flag changes but the page describing it remains byte-identical. State which reviews or gate results become stale and why. Also demonstrate that an unrelated edit leaves the relevant evidence reusable.
- Show how the recommendation works through the actual commit path and on resume. Identify what attended and autonomous profiles can enforce today and which parts need outstanding gate work.
