---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [skills, ui, reporting, artifacts, planning, brainstorming]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
children_to_implement: [t1210_1, t1210_2, t1210_3]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/fable5
created_at: 2026-07-22 10:14
updated_at: 2026-07-22 16:16
boardidx: 10
---

## Context

During complex feature work, the implementation plan and preferred route evolve as implementation uncovers risks, alternative designs, manual-verification needs, coordination conflicts, and tasks outside the original topic. The task DAG and board priority are necessary but do not preserve the higher-level answer to: **which tasks should land next, in what waves, and why?**

Two recent manual analyses showed the desired output shape:

- A shadow-review-loop analysis recommended `t1208 → t1187 → t1053 → t1159`, distinguishing a true parser blocker, a cheap destructive verification bug, a live foundation check, a coordination-only overlap with `t1118_4`, and unrelated tasks that should not block.
- A gate-framework analysis produced waves from clearing dirty/in-flight conflicts, through fixing baseline failures, proving the engine, landing procedure gates, serializing conflicting UI surfaces, and handling the long tail. It also discovered blockers outside the gate topic (a red Python suite, stale task premises, shared skill-file collision surfaces, and missing model defaults).

This information is valuable, expensive to reconstruct, and currently ephemeral. Create a brainstorm/design task for a durable **implementation trail** capability that can be invoked directly or from an `ait board` task/topic and can feed manager-facing reporting.

## Goal

Design a profile-aware aitask skill and persistent machine-readable artifact that derives, explains, versions, and refreshes the preferred implementation trail for a selected task, topic, or explicitly chosen scope. Define how the trail integrates with the board's By-Topic view and with the manager-facing work-report flow in t1162, then decompose the approved design into implementable tasks.

This task is for design, decisions, and decomposition. Do not implement the complete skill, board UI, or report integration in this task.

## Re-entry requirement

The initial planning session was aborted after saving
`aiplans/p1210_brainstorm_durable_implementation_trail_skill_and_board_repo.md`.
The plan is not approved and must be verified again before implementation. On
the next pick, use `--profile default` or another profile with
`plan_preference: verify`; the `fast` profile's normal `use_current` behavior is
not sufficient for this re-entry.

## Core design requirements

### Preserve topic semantics

- Treat task metadata `anchor` as the single canonical topic-group key. Do not redefine it as roadmap/trail membership and do not mutate anchors merely because a trail references a task.
- Model trail membership as a separate many-to-many relationship: one trail may reference tasks from several topics, and a task may be relevant to more than one trail.
- Avoid rendering the same card in multiple topic lanes. Explore an overlay, badge, focused trail/filter, dedicated wave view, or another UX that keeps canonical topic membership unambiguous.

### Invocation and scope

Design entry points for:

- Direct skill invocation with interactive selection.
- Invocation for a single task, resolving its canonical topic when appropriate.
- Invocation from a focused By-Topic lane/root in `ait board`.
- An ad-hoc or multi-topic scope when the analysis finds prerequisite or coordination work outside the initiating topic.

Specify how an initiating/owning task is selected when a trail spans topics or begins without an obvious topic root. Compare attaching the artifact to a designated root/task with introducing a dedicated planning container; avoid task-board clutter unless it has a clear lifecycle benefit.

### Machine-readable trail artifact

Use the unified artifact substrate (`ait artifact`) unless the brainstorm finds a concrete incompatibility. The existing model provides a stable task-owned handle, an open `kind`, immutable content versions, and a mutable current-version manifest.

Define and validate a versioned schema (JSON, YAML, or another justified format) with enough information to reproduce the useful manual output, including at least:

- Schema version, stable trail identity, owner/scope, generation time, and source/evidence snapshot.
- Ordered waves and ordered entries within each wave.
- Task IDs, canonical topic IDs, current status/priority/effort snapshot, and dependency/blocker relationships.
- Per-entry motivation, expected outcome, why the order matters, and confidence or evidence.
- Distinction among hard prerequisites, strongly preferred predecessors, coordination-only conflicts, optional work, excluded/non-blocking work, and discovered baseline risks.
- Cross-topic and, if supported, cross-repository references without copying task descriptions as a second source of truth.
- Freshness/staleness signals and the reason a refresh is recommended.

Choose whether the canonical artifact is structured data with a rendered Markdown/TUI view, a structured Markdown document, or paired artifacts. Prefer one source of truth and deterministic rendering.

Define create/update behavior using stable handles and artifact versions, including lookup of an existing trail, collision rules, task folding/archival implications, missing tasks, and concurrent refreshes.

### Analysis behavior

Specify how the skill gathers and reasons over:

- The selected task/topic, child tasks, active plans, dependencies, gates, statuses, board order, labels, and related tasks.
- Potential blockers outside the nominal topic, including broken test baselines, in-flight dirty/conflicting work, stale task premises, shared-file collision surfaces, and external/cross-repo dependencies.
- Existing explicit DAG constraints versus advisory preferred ordering. The artifact must not silently rewrite `depends`, priority, `boardidx`, or anchors; offer separate confirmed mutations if the final product supports them.
- Reruns after task completion, new risk-mitigation tasks, design changes, manual-verification outcomes, or board moves.

The design should prevent fabricated blockers, progress, estimates, or commitments. Record evidence and clearly separate observed facts from agent recommendations.

### Board integration

Study `.aitask-scripts/board/aitask_board.py` topic grouping and design the board flow in concrete terms:

- Contextual action(s) from a task card and a By-Topic column/root.
- Create, open, refresh, compare-version, and select-trail behavior.
- How wave/order and stale/current state are surfaced without duplicating cards across topic lanes.
- How cross-topic members are revealed (for example, an overlay that badges/dims cards in their existing lanes, or a selected-trail wave view).
- Behavior for singleton/Ungrouped topics, archived owners, missing artifact blobs, and multiple trails referencing the same task.
- Exact launch arguments passed to the code-agent skill and the read-only versus mutating parts of the flow.

Keep topic bucketing derived from `anchor`; trail visualization is a separate projection.

### Manager report integration (t1162)

Coordinate explicitly with `t1162_add_manager_facing_work_report_skill_and_board_flow.md`, which is already Implementing.

- Preserve t1162's deterministic contract: its report contains exactly the board-selected tasks and retains selected-column/`boardidx` order unless the user explicitly chooses a trail-based mode.
- A trail may provide motivation, wave, dependency, risk, and manager-ask context only for tasks already selected; it must not silently expand report membership.
- Evaluate a later explicit `--trail <handle>` or board "report from trail" path, including how it interacts with horizon, column grouping, exact membership, and report ordering.
- Decide whether the implementation-trail feature consumes t1162's gatherer, extends it through a stable interface, or remains a separate gatherer with shared primitives. Avoid coupling to t1162's in-flight implementation details.
- Define whether manager reports remain ephemeral drafts, as required by t1162, while implementation trails are durable artifacts. Do not turn every work report into an artifact implicitly.

### Skill and lifecycle design

- Define the canonical skill name, arguments, supported-agent wrappers, model class, read/write policy, and board dispatcher registration.
- Decide whether generating/updating the artifact is one confirmed write after a read-only analysis/review step.
- Define artifact ownership and cleanup across task fold, archive, hard delete, and cross-repo scope.
- Include permission, conflict, failure-recovery, and partial-update behavior.
- Identify documentation and manual-verification needs.

## Deliverables

1. A decision-oriented design document with user journeys and alternatives considered.
2. A concrete machine-readable schema with representative fixtures for both manual examples above.
3. Board UX flows/wireframes for task, topic, cross-topic, multiple-trail, and stale-trail cases.
4. A precise integration contract with t1162 that preserves its exact-membership guarantees.
5. A lifecycle and concurrency analysis for artifact creation, update, fold, archive, delete, and missing/corrupt content.
6. An implementation decomposition into child or follow-up tasks with dependencies, coordination notes, verification scope, and a recommended landing order.

## Decision questions to resolve

- What should the public capability be called: implementation trail, roadmap, execution plan, priority waves, or another term distinct from `aiplan`?
- Is the canonical artifact structured JSON/YAML with deterministic Markdown rendering, or structured Markdown with a parser?
- Which task owns a cross-topic or ad-hoc trail, and is an unowned artifact supported by the current substrate?
- Does By-Topic gain an overlay/action only, or should there also be a dedicated By-Trail/Waves view?
- How are stale recommendations detected without treating every board/status change as invalidation?
- Can one task appear in several trails, and how does the UI select which trail's wave/order to show?
- When may the user confirm converting advisory order into actual `depends`, priority, or board ordering changes?
- How does an explicit trail-based work report coexist with t1162's column-based exact ordering?

## Related work and boundaries

- **t1162** — manager-facing work report and board flow; integrate through an explicit contract, do not fold or duplicate it.
- **t571** — structured brainstorming-plan sections and DAG UI; reuse conventions where useful, but this trail is task sequencing across the board rather than internal section structure within one brainstorm plan.
- **t1076 / `aidocs/unified_artifact_design.md`** — artifact handle/version/backend substrate and `artifacts:` frontmatter.
- **Board topic implementation** — `_build_topic_lanes`, `topic_key`, `TopicColumn`, and By-Topic actions in `.aitask-scripts/board/aitask_board.py`.

Non-goals for the brainstorm task: changing existing anchors, making report membership implicit, implementing all proposed surfaces, or treating advisory trail ordering as a hard dependency graph without user confirmation.

## Verification for the design task

- Validate the proposed schema against both example analyses and at least one cross-topic/multiple-trail case.
- Trace every board flow against current topic grouping, Ungrouped behavior, and artifact resolution APIs.
- Review the t1162 contract against its requirement to include exactly selected tasks in board order.
- Confirm proposed artifact operations are supported by `ait artifact create/update/get/versions` or explicitly scope substrate changes.
- Ensure the decomposition identifies automated tests and human-only manual verification separately.
