---
Task: t1210_brainstorm_durable_implementation_trail_skill_and_board_repo.md
Worktree: /home/ddt/Work/aitasks (current checkout; fast profile)
Branch: main
Base branch: main
plan_verified: []
---

# Plan: t1210 — Durable implementation-trail skill and board/report integration

## Context

t1210 is a design/brainstorm task, not the full feature implementation. It must
turn the useful but ephemeral “what should land next, in which waves, and why?”
analyses into an architecture that can later be implemented consistently across
the artifact engine, a profile-aware skill, `ait board`, and manager reporting.

The user chose to keep this as one integrated design task. The implementation
decomposition will therefore be a copy-ready deliverable in the design document;
this task will not create live child tasks before the architecture is approved.

## Re-entry requirement

This initial planning session was explicitly aborted after saving the plan. The
plan is **not approved** and must be verified again on the next pick before any
implementation starts. Because the `fast` profile normally uses an existing
parent plan as-is, re-pick t1210 with `--profile default` (or another profile
whose `plan_preference` is `verify`) and take the verify-plan path. Do not treat
the existence of this file as approval; no `plan_approved` checkpoint was
recorded in this session.

### Grounding established during exploration

- The two tmux examples share a stable semantic shape: ordered waves, ordered
  task entries, per-task rationale, hard prerequisites, strongly preferred
  predecessors, coordination-only conflicts, explicitly non-blocking work, and
  live baseline risks discovered outside the nominal topic.
- `anchor` is a scalar canonical topic-group key. `topic_key()`,
  `_build_topic_lanes()`, and `TopicColumn` in
  `.aitask-scripts/board/aitask_board.py` intentionally place each task in one
  topic lane; singleton topics collapse into `Ungrouped`.
- The shipped artifact substrate already supports task-owned stable handles,
  open `kind` values, immutable blob versions, mutable manifests, and
  `create/update/get/versions`. `ait artifact create` requires an owning task;
  unowned artifacts are not a supported public lifecycle.
- t1162's approved plan is deliberately different: Work Report selects exact
  board-column membership, preserves `boardidx` order, launches with explicit
  `--columns/--tasks`, and writes no report file. Its board action is hidden in
  By-Topic. Trail integration must not silently alter that contract or modify
  t1162 while its children are being created/implemented.
- The board already has the reusable launch seams: `KanbanApp.BINDINGS`,
  `check_action()`, `_get_focused_col_id()`, `AgentCommandScreen`, and the
  focused-task launch patterns used by Pick/Brainstorm.

## Recommended architecture to test in the design

These are planning hypotheses, not pre-approved product decisions. The RFC must
compare alternatives and either substantiate or revise them.

1. Public term: **Implementation Trail**, deliberately distinct from an
   `aiplan`, an umbrella “roadmap” task, hard `depends`, and board priority.
2. Canonical source: one versioned JSON artifact with
   `kind: implementation_trail`, validated by a versioned JSON Schema. Human
   Markdown/TUI views are deterministic projections rather than a second
   persisted source of truth.
3. Ownership: the initiating task or resolved topic root owns the artifact. An
   ad-hoc/multi-topic trail requires an explicitly selected owner because the
   current artifact lifecycle is task-owned. Referenced tasks do not gain the
   handle and their anchors do not change.
4. Board: By-Topic remains the canonical projection. A selected-trail overlay
   dims nonmembers and badges members in their existing lanes with wave/order;
   a detail modal renders the full ordered waves. A dedicated By-Trail/Waves
   view is evaluated as a later enhancement, not required for the first slice.
5. Multiple membership: a task may occur in several trail artifacts, but the
   board displays wave/order for one explicitly selected trail at a time.
6. Staleness: each artifact stores a normalized input snapshot/digest and
   evidence records. Consumers compare current task/plan/dependency/gate inputs
   and report named drift reasons; they do not treat every timestamp or board
   repaint as semantic invalidation.
7. Mutations: v1 analysis only creates/updates the artifact after review and
   confirmation. It does not rewrite `depends`, priority, `boardidx`, or
   `anchor`; recommended mutations, if later supported, are a separate explicit
   confirmation flow.
8. t1162: ordinary column reports keep exact membership and board order. A
   chosen trail may enrich only already-selected task entries. A future explicit
   “report from trail” mode may use trail membership/wave order only when the
   user selects that mode.

## Implementation

### 1. Author the decision-oriented RFC

Create `aidocs/implementation_trail_design.md` in the same current-state/RFC
style as `aidocs/unified_artifact_design.md`. Make it self-contained and include:

1. Problem statement using the two distilled manual examples.
2. Goals/non-goals and terminology: topic, dependency DAG, board priority,
   implementation trail, wave, observation, recommendation, evidence.
3. User journeys and invocation matrix:
   - direct interactive skill;
   - single task, with an explicit choice between task-only and canonical topic;
   - focused By-Topic lane/root;
   - ad-hoc/multi-topic scope with an explicit owner;
   - create, inspect, refresh, compare versions, and select among multiple trails.
4. Domain model and invariants:
   - `anchor` remains the one-topic group key;
   - trail membership is many-to-many and stored only in trail content;
   - one owner handle, stable task references, facts separated from recommendations;
   - advisory ordering never impersonates hard `depends`.
5. Artifact representation decision, handle naming, `kind`, create/update lookup,
   content/manifest split, and deterministic Markdown/TUI rendering.
6. Schema walkthrough tied field-by-field to
   `aidocs/implementation_trail.schema.json` and the fixtures.
7. Analysis/gathering algorithm:
   - resolve owner/scope and canonical topics;
   - read tasks, children, active plans, dependencies, gates, board state, labels,
     locks/in-flight work, and cross-repo references;
   - expand beyond the nominal topic only with evidence;
   - classify hard prerequisite / preferred predecessor / coordination-only /
     optional / excluded / baseline risk;
   - topologically respect hard dependencies, then form advisory waves;
   - record confidence and evidence without inventing progress or blockers;
   - review before the single artifact create/update write.
8. Freshness model with a canonical normalization/input digest, named drift
   reasons, status-transition policy, plan/task deletion behavior, and refresh
   compare-and-swap needs. Explicitly identify that the current artifact CLI has
   no public optimistic-concurrency/CAS update and scope the required extension
   if concurrent refresh safety needs one.
9. Board UX state matrix/wireframes:
   - task card and `TopicColumn` invocation;
   - singleton/Ungrouped behavior;
   - no trail / current / stale / missing blob / corrupt content;
   - cross-topic overlay without card duplication;
   - multiple trails and explicit active-overlay selection;
   - archived owner and missing referenced tasks;
   - exact code-agent launch arguments and read-only analysis vs confirmed write.
10. Manager-report contract with t1162:
    - column mode remains exact-membership and `boardidx` ordered;
    - optional enrichment is an intersection with selected tasks and cannot add or
      reorder them;
    - explicit trail-report mode is separate and names its membership/order source;
    - ordinary reports remain ephemeral while trails are durable;
    - coordinate after t1162's gatherer/skill child interfaces land rather than
      coupling to its in-flight internals.
11. Lifecycle table for create, refresh, fold, archive, hard delete, artifact rm,
    missing/corrupt manifest/blob, cross-repo references, and concurrent updates.
12. Security/failure model: bounded reads, path/handle validation, no credential
    material in artifacts, fail-closed parsing, atomic write/rollback, and user
    confirmation before persistence or task-metadata mutations.
13. Alternatives and decisions: structured Markdown vs JSON; paired artifacts;
    unowned artifacts; dedicated planning-container tasks; duplicating cards;
    changing anchors; making advisory edges hard dependencies; eager By-Trail view.
14. Sequenced implementation decomposition with copy-ready task scopes,
    dependencies, coordination notes, automated verification, and a separate
    human manual-verification task for live TUI/agent/artifact flows. At minimum
    separate schema/gathering, skill/artifact writes, board projection, t1162
    integration, and docs/manual verification so collision-heavy surfaces land
    in a deliberate order.

Do not edit t1162 task/plan files in this task; reference the approved
`aiplans/p1162_add_manager_facing_work_report_skill_and_board_flow.md` contract.

### 2. Define the machine-readable v1 contract

Create `aidocs/implementation_trail.schema.json` as a Draft 2020-12 JSON Schema.
Keep the root contract strict (`additionalProperties: false`) and versioned.
Model at least:

- identity: `schema_version`, `trail_id`, `artifact_handle`, `owner`, `scope`;
- generation: timestamp, generator/agent, project revision, normalized
  `input_digest`, and explicit evidence sources;
- freshness: state, checked-at time, and structured drift reasons;
- waves: stable wave id, ordinal, title, motivation, and ordered entries;
- entries: project/task id, topic id, snapshot metadata, expected outcome,
  recommendation rationale/confidence, classification, and evidence refs;
- relations: typed directed edges with fact/advisory provenance;
- observations: external baseline risks and coordination findings that may not be
  task members;
- exclusions: considered tasks/work with the reason it does not block;
- rendering hints that are advisory and never duplicate canonical content.

Use project-qualified task references so the same shape can represent local and
registered cross-repo tasks. Keep mutable task descriptions and plan bodies out
of the artifact; store identifiers, snapshots, digests, and concise analysis.

### 3. Add representative fixtures and wireframes

Create `aidocs/implementation_trail_examples/` with:

- `shadow_review_loop.json` — waves/order for t1208, t1187, t1053, t1159;
  parser blocker vs preferred live verification, `t1118_4` coordination-only,
  and non-blocking shadow tasks.
- `gate_framework.json` — multi-wave t635 sequence, explicit dependencies,
  dirty/in-flight coordination, red-suite baseline risk, stale premise, and
  serialized shared-file surfaces.
- `cross_topic_multiple_trails.json` — a compact synthetic case proving one
  task can be referenced by two trail identities while retaining one canonical
  topic; use it to show active-overlay selection and no card duplication.

Use stable illustrative timestamps/digests and label the synthetic values. Do
not claim the examples are live board state. Include compact text wireframes in
the RFC for By-Topic normal mode, a selected trail overlay, the detail modal,
the stale state, and trail selection.

### 4. Add an executable design-contract test

Create `tests/test_implementation_trail_design.py` using only the Python standard
library. It is not the future production parser. It protects the design
deliverables by checking:

- schema and every fixture parse as JSON;
- fixture `schema_version` matches the schema constant;
- required root keys and unique wave/entry/evidence ids;
- wave ordinals and entry positions are strictly ordered;
- every relation/evidence reference resolves;
- task entries include project-qualified ids and a canonical topic id;
- the cross-topic fixture demonstrates two trail identities referencing the
  same task/topic without encoding alternate anchors;
- the two manual fixtures contain the key blocker/coordination/exclusion classes
  that motivated the feature.

This intentionally avoids adding a runtime JSON-Schema dependency. The future
schema/parser implementation task may adopt a validator and replace or extend
these contract checks.

### 5. Verify the RFC against shipped seams

Before review, perform and record a traceability pass:

- Walk owner/create/update/fold/archive/delete claims against
  `.aitask-scripts/aitask_artifact.sh`,
  `.aitask-scripts/lib/artifact_manifest.py`, `tests/test_artifact_cli.sh`, and
  `aidocs/unified_artifact_design.md`; label substrate gaps rather than assuming
  APIs exist.
- Walk board states against `topic_key()`, `_build_topic_lanes()`,
  `group_tasks_by_topic()`, `TopicColumn`, `check_action()`, and focused launch
  patterns in `.aitask-scripts/board/aitask_board.py`.
- Walk reporting examples against t1162's approved plan, especially exact
  membership, `boardidx` ordering, fail-closed stale selection, ephemeral output,
  and the current decision to hide Work Report in By-Topic.
- Check the decomposition for shared-file collisions with t1162 and require
  sequencing/coordination rather than parallel edits to the same skill/board
  surfaces.

### 6. Verification commands

Run:

```bash
python3 -m unittest tests.test_implementation_trail_design -v
python3 -m json.tool aidocs/implementation_trail.schema.json >/dev/null
for f in aidocs/implementation_trail_examples/*.json; do
  python3 -m json.tool "$f" >/dev/null
done
git diff --check
```

Also use focused `rg` checks to confirm the RFC names `anchor`, t1162's exact
membership/order contract, artifact ownership/lifecycle, staleness, multiple
trails, and the implementation decomposition.

### 7. Review, commit, and post-implementation

- Present the RFC, schema/fixture summary, wireframes, and proposed decomposition
  for the non-skippable Step 8 user review.
- After approval, commit code/docs/fixtures/tests with
  `feature: Design durable implementation trails (t1210)` and update this plan's
  Final Implementation Notes separately through `./ait git`.
- Run Step 9 gate verification and archival. This current-branch profile has no
  feature branch to merge.

## Risk

### Code-health risk: low

- A premature schema could become a duplicated task/plan data model rather than
  a compact analysis snapshot · severity: low · → mitigation: strict v1 scope,
  identifiers/digests instead of copied descriptions, and executable fixture
  checks in Steps 2–4.
- A design-only validator could be mistaken for the future production parser ·
  severity: low · → mitigation: explicit non-production boundary in Step 4 and
  a separate schema/gatherer implementation task in the decomposition.

### Goal-achievement risk: medium

- Cross-topic ownership may not fit the shipped task-owned artifact lifecycle,
  especially fold/delete and concurrent refresh behavior · severity: medium ·
  → mitigation: command-by-command lifecycle trace and explicit substrate-gap
  decisions in Steps 1 and 5.
- Trail visualization could reintroduce the duplicate-card/topic ambiguity the
  feature is meant to solve · severity: medium · → mitigation: canonical-lane
  invariant, multiple-trail fixture, and board state/wireframe matrix in Steps
  1 and 3.
- t1162 is concurrently decomposing/implementing, so coupling to an unstable
  helper could invalidate the report integration design · severity: medium · →
  mitigation: preserve its approved external contract, make enrichment/mode
  boundaries explicit, and sequence implementation after its interfaces land.

All identified risks are mitigated inside this design/validation task and its
sequenced implementation decomposition; no separate before/after risk-mitigation
task is proposed.
