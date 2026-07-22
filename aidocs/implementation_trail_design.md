# Implementation Trails — durable "what lands next, and why" (design RFC)

Status: **proposed design** (t1210 deliverable). Current-state document: describes
the design as decided, plus the shipped seams it builds on. The implementation
decomposition is in §14; nothing in this document is shipped code yet.

Companion artifacts:

- `aidocs/implementation_trail.schema.json` — versioned JSON Schema (v1 contract)
- `aidocs/implementation_trail_examples/` — three representative fixtures
- `tests/test_implementation_trail_design.py` — executable design-contract test

---

## 1. Problem statement

During complex multi-task efforts, the highest-value planning output is not the
task DAG or the board order — it is the *explained sequence*: **which tasks
should land next, in what waves, and why.** Two recent manual analyses showed
the shape of this output:

- A **shadow review-loop** analysis recommended `t1208 → t1187 → t1053 → t1159`,
  distinguishing a true parser blocker, a cheap destructive-verification bug, a
  live foundation check, a coordination-only overlap with a neighboring topic's
  child, and unrelated tasks that should not block.
- A **gate-framework** analysis produced waves — clear dirty/in-flight
  conflicts, fix baseline failures, prove the engine, land procedure gates,
  serialize colliding UI surfaces, then the long tail — and discovered blockers
  *outside* the nominal topic: a red Python suite, stale task premises,
  shared skill-file collision surfaces, and missing model defaults.

That information is expensive to reconstruct and currently ephemeral (it lives
in a terminal scrollback). This RFC designs a durable, machine-readable,
refreshable **Implementation Trail**: a versioned artifact that captures the
recommended landing order *with its reasoning*, plus the skill that generates
and refreshes it and the board view that displays and acts on it.

## 2. Goals, non-goals, terminology

**Goals**

1. Persist the wave-ordered recommendation *and its narrative rationale* as a
   single machine-readable source of truth with deterministic human renderings.
2. Keep trails **dynamic**: detect when reality drifts from the recorded
   analysis (tasks completed, follow-ups created, premises invalidated) and
   support a targeted refresh that produces a new artifact version.
3. First-class board support: a dedicated **By-Trail view** that renders waves
   and lets the user act (open, refresh, move tasks/waves to board columns).
4. Passive manager-report integration: trails feed reports **only** through
   ordinary board columns (see §10) — t1162's contract is untouched.

**Non-goals**

- Changing `anchor` semantics or any task's canonical topic membership.
- Letting the *analysis* mutate `depends`, `priority`, `boardidx`, or `anchor`.
- Implicitly turning work reports into durable artifacts.
- A general project-management Gantt/estimate system: trails record ordering
  rationale and evidence, never invented estimates, progress, or commitments.

**Terminology**

| Term | Meaning |
|---|---|
| Topic | Canonical board grouping keyed by `anchor` resolution (`topic_key()`); each task has exactly one topic. |
| Dependency DAG | Hard `depends:` edges recorded in task frontmatter. |
| Board priority | `boardcol`/`boardidx` layout the user maintains on `ait board`. |
| **Implementation Trail** | A durable, versioned, explained recommendation of landing order across tasks; advisory by construction. |
| Wave | An ordered group of trail entries that lands as a unit before the next wave. |
| Observation | An evidence-backed fact that shapes ordering but is not a trail member (e.g. red baseline suite). |
| Recommendation | Agent judgment recorded in narrative fields; always distinguishable from observations. |
| Evidence | A locator + summary of where a fact was observed; never a copy of task/plan bodies. |

The name **Implementation Trail** was chosen (over roadmap / execution plan /
priority waves) because it is distinct from `aiplan` files, avoids the
umbrella-roadmap-task connotation, and reads naturally as "the trail we follow
to land this effort". The term is unused in the repo today.

## 3. User journeys and invocation matrix

| # | Entry point | Scope | Owner resolution |
|---|---|---|---|
| J1 | `/aitask-trail` (interactive) | User picks task / topic / multi-topic / ad-hoc | Initiating task, or explicit pick for ad-hoc |
| J2 | `/aitask-trail <task_id>` | Single task; skill offers task-only vs the task's canonical topic | The task (or its topic root, user choice) |
| J3 | Board, By-Topic lane focused → trail action | The focused lane's topic root | Topic root task |
| J4 | `/aitask-trail --topics <r1>,<r2>` or interactive expansion | Multi-topic / ad-hoc | **Explicitly user-selected owner task** (substrate requires a task-owned handle) |
| J5 | Board, By-Trail view → `r` on a selected trail | Existing trail handle | Unchanged |
| J6 | `/aitask-trail --refresh <handle>` | Existing trail | Unchanged |
| J7 | Board, By-Trail view → open/inspect/compare versions | Existing trail | n/a (read-only) |

Journey shapes:

- **Create** (J1–J4): resolve scope → read-only analysis → present the proposed
  trail (waves, rationale, observations, exclusions) → user confirms → **one
  write**: `ait artifact create <owner> <trail.json> --kind implementation_trail
  --handle art:<trail-id>` (emits `HANDLE:`).
- **Refresh** (J5–J6): recompute drift (§8) → targeted re-analysis driven by
  the named drift reasons → present a diff-style summary (what changed, which
  waves/entries were added/retired) → user confirms → **one write**:
  `ait artifact update <handle> <trail.json>` (new immutable version; manifest
  `current` repoints; previous versions remain comparable via
  `ait artifact versions` / `get --version`).
- **Inspect** (J7): pure reads (`ait artifact get`), no confirmation needed.

Mid-analysis discoveries outside the initiating scope (J2/J3) do not silently
expand scope: the skill proposes the expansion ("the red suite blocks this
topic — include it as an observation / include topic X?") and the user decides.

## 4. Domain model and invariants

1. **`anchor` stays the one topic-group key.** The board's topic bucketing
   (`topic_key()`, `_build_topic_lanes()` in
   `.aitask-scripts/board/aitask_board.py`) is untouched. A trail records each
   entry's canonical `topic` *as observed*, for projection only. Trail
   documents contain no `anchor` field anywhere (pinned by
   `test_no_anchor_encoding`).
2. **Trail membership is many-to-many and lives only in trail content.** A
   task may be referenced by any number of trails; referencing a task never
   writes anything to that task's file. Only the *owner* task carries the
   handle in its `artifacts:` frontmatter list.
3. **One owner handle.** The artifact substrate supports only task-owned
   artifacts (`ait artifact create` requires a task). Single-task/topic trails
   default ownership to the initiating task or topic root; multi-topic/ad-hoc
   trails require an explicit owner choice at creation (J4). A dedicated
   planning-container task is *not* created implicitly (board clutter; see
   §13-A4).
4. **Facts and recommendations never blur.** Hard `depends` mirrored into a
   trail carry `provenance: fact`; recommended orderings carry
   `provenance: advisory`. Observations require evidence references. The
   analysis records what it did *not* verify (`narrative.method_note`).
5. **Advisory ordering never impersonates the DAG.** Nothing in a trail is
   read by gate enforcement, `depends` resolution, or archival guards.
   Converting advisory order into real `depends`/priority/board changes is a
   separate, per-change, user-confirmed flow — deferred (§13-D4). The one v1
   mutation path is the explicit **move-to-column** board command (§9.4),
   which is a user action on the board, not an analysis output.

## 5. Artifact representation

**Decision: one canonical JSON document per trail, stored as a versioned
artifact (`kind: implementation_trail`), with narrative rationale first-class
in the schema. Markdown and TUI renderings are deterministic projections and
are never persisted as a second source of truth.** (User decision; alternatives
in §13-A2.)

The trail must not degenerate into a bare ranked task list: `narrative.*`,
`waves[].purpose`, `waves[].why_now`, `waves[].consequence_of_delay`,
`entries[].rationale`, `entries[].expected_outcome`,
`entries[].why_order_matters`, `entries[].caveats`, and per-entry
`confidence` carry the prose that made the manual analyses valuable, and
renderers present them as prose, not as tooltip metadata. The design-contract
test pins non-empty narrative at document and wave level.

**Substrate mapping** (all shipped, verified against
`.aitask-scripts/aitask_artifact.sh` and `lib/artifact_manifest.py`):

| Concern | Mechanism |
|---|---|
| Handle | `art:trail-<slug>` (fits `^art:[a-z0-9][a-z0-9._-]{0,127}$`). Always passed explicitly via `--handle` — the default owner+kind derivation would collide when one task owns two trails. `trail_id` in the document mirrors the handle minus `art:`. |
| Kind | `implementation_trail` (valid: `^[a-z][a-z0-9_]{0,31}$`; the kind set is open — no registry change needed). |
| Owner linkage | The owner task's frontmatter `artifacts:` entry (stable fields only: handle/kind/name). |
| Versions | Immutable content-addressed blobs; `update` appends and repoints `current`; identical bytes are an idempotent no-op. Compare versions via `versions` + `get --version sha256:<hash>`. |
| Size | Trails are small JSON (KBs); the 25 MB `artifact_max_size_mb` default is irrelevant headroom. |
| Discovery | "All trails" = scan task frontmatter (active + archived) for `artifacts:` entries with `kind: implementation_trail`. The manifest does not store kind, so discovery is frontmatter-driven; the board loader already parses every task file. |

**Create/update behavior**: create fails if the chosen handle already exists
(collision rule: pick a new slug); refresh always targets an existing handle
and never creates. Missing blobs/corrupt manifests are surfaced as an error
state, never auto-healed (§11, §12).

## 6. Schema walkthrough

`aidocs/implementation_trail.schema.json` (Draft 2020-12, root
`additionalProperties: false`, `schema_version` const `1.0.0`). Field groups,
tied to the fixtures:

- **Identity** — `schema_version`, `trail_id`, `title`, `owner`, `scope`
  (`kind: task|topic|multi_topic|ad_hoc`, canonical `topics`, optional
  `initiating_task`, narrative `selection_note`). All task references use the
  cross-repo notation `<project>#<id>` (`aidocs/framework/cross_repo_references.md`),
  bare-id canonical form — the same shape covers local and registered
  cross-repo tasks (fixtures use `aitasks#1208` etc.).
- **Generation/provenance** — `generated_at`, `generator` (agent string +
  skill), `project_revision`, **`input_digest`**, and presence-tracked
  `inputs` (so a deleted input is itself detectable drift). This follows the
  derived-state-needs-provenance rule: the artifact always records *which
  inputs produced it*.
- **Freshness** — `state: current|stale|unknown`, `checked_at`, structured
  `drift_reasons` (closed enum of codes + per-reason task + detail), and the
  narrative `refresh_recommended_because`. See §8. The `gate_framework.json`
  fixture demonstrates the stale state with `task_completed` and
  `new_related_task` reasons.
- **Narrative** — required `problem_statement` and `recommendation_summary`,
  plus `method_note` (what was and was not verified) and global `caveats`.
- **Waves and entries** — strictly increasing `ordinal`/`position`;
  per-entry `classification` (`hard_prerequisite`, `preferred_predecessor`,
  `core`, `coordination_only`, `optional`), point-in-time `snapshot`
  (status/priority/effort/depends/gates_pending — display convenience and
  drift anchor, never a source of truth), required narrative `rationale`,
  and `confidence` + `caveats` + `evidence_refs`.
- **Relations** — typed edges (`hard_depends`, `advisory_precedes`,
  `coordinates_with`, `verifies`, `informs`) with mandatory
  `provenance: fact|advisory`. `hard_depends` must be facts (pinned by test).
- **Observations** — non-member findings (`baseline_risk`,
  `in_flight_conflict`, `stale_premise`, `shared_surface_collision`,
  `external_dependency`, `environment`), each requiring evidence.
- **Exclusions** — considered-and-rejected work with reason codes; prevents
  re-litigating candidates on every refresh.
- **Evidence** — locator + observed-at + concise summary. Identifiers and
  digests only; task/plan bodies are never copied into the artifact.
- **rendering_hints** — advisory presentation preferences; ignorable.

## 7. Analysis / gathering algorithm

The generating skill is split into a deterministic **gatherer** (a
whitelistable helper script + Python lib, mirroring the t1162 gatherer
pattern) and the agent-side **reasoning** step:

1. **Resolve scope and owner** (J1–J4): normalize task ids, resolve canonical
   topics via the same anchor-resolution rules the board uses, resolve
   cross-repo references through `ait projects resolve` when present.
2. **Gather (deterministic, read-only)**: member/candidate task frontmatter
   (status, depends, gates + pending state, labels, boardcol), plan-file
   existence and identity, in-flight/lock state, archived-sibling landscape,
   and the normalized input snapshot + `input_digest` (§8). Output is a
   line-protocol dump the skill consumes — no agent free-reading of the whole
   board.
3. **Expand with evidence only**: candidates outside the nominal scope
   (baseline suite state, colliding in-flight work, stale premises,
   external/cross-repo dependencies) enter only as evidence-backed
   observations or as user-confirmed scope expansions — never silently.
4. **Classify and order**: hard `depends` edges are respected topologically
   (facts); advisory waves are formed on top and each boundary must carry a
   narrative `purpose`/`why_now`. Every entry gets
   `classification`, `rationale`, `confidence`.
5. **Anti-fabrication rules**: no estimates, progress claims, or commitments;
   every observation cites evidence; `method_note` states what was *not*
   verified; snapshots are labeled as point-in-time copies.
6. **Review, then one write**: the full proposed trail is rendered for the
   user; only after confirmation does the skill perform the single
   create/update call (§3).

Rerun triggers (task completion, new risk-mitigation or follow-up tasks,
design changes, manual-verification outcomes, board moves the user considers
semantic) all route through the refresh journey — the analysis itself never
watches the board.

## 8. Freshness and refresh (dynamic trails)

Trails are **living documents** — this is a core requirement, not an
afterthought. The mechanism has three parts:

**8.1 Input digest.** At generation time the gatherer canonicalizes, per input
task: existence, `status`, sorted `depends`, pending gate set, and the
plan-file content hash; plus the presence-tracked input list. `boardidx` and
timestamps are deliberately excluded — board repaints and cosmetic moves are
not semantic drift. The canonical JSON is hashed (sha256, truncated hex) into
`generation.input_digest`. The normalization procedure is versioned with the
schema so digests are only compared within a schema version.

**8.2 Drift detection.** A cheap `trail-drift` check (same gatherer lib)
recomputes the digest and, when it differs, produces *named* reasons from the
per-input comparison: `task_completed`, `task_archived`, `task_deleted`,
`task_folded`, `status_changed`, `dependency_changed`, `gate_state_changed`,
`plan_changed`, `new_related_task` (a new task anchored into a member topic or
depending on a member), `premise_invalidated`, `input_missing`. Consumers (the
board, the skill) run it on demand — opening the By-Trail view, or explicitly
— and update only the trail's *rendered* badge; polling never rewrites the
artifact (passive observation must not refresh state stamps).

**8.3 Targeted refresh (subskill).** `/aitask-trail --refresh <handle>` (or
`r` in the By-Trail view) loads the current version, consumes the drift
reasons, and re-analyzes **only what changed**: completed entries are moved to
an honored/landed presentation (their wave records the completion via the
refreshed snapshot), newly created follow-up tasks are evaluated for
membership, invalidated premises re-open the affected wave's reasoning.
The result is a new artifact version after user confirmation — never an
in-place mutation — so `ait artifact versions` is the trail's history and
"compare versions" (J7) is a projection diff of two immutable blobs.

**Concurrency.** The artifact CLI has **no public compare-and-swap**: updates
are serialized by the global attach lock, but a stale-base refresh (two
sessions refreshing the same trail from different read states) would
last-write-win. v1 accepts this with a guard: the refresh flow re-reads the
manifest's `current` immediately before writing and warns if it moved since
analysis started (lost-update window shrinks to seconds; all versions remain
recoverable). A real `update --expect-current sha256:<hash>` CLI extension is
scoped as a **conditional follow-up** (§14, D-list): create it when concurrent
refreshers become a practiced workflow, not before.

## 9. Board integration — the By-Trail view

**Decision: a dedicated By-Trail view ships in v1** (user decision; the
overlay-only alternative is recorded in §13-A5). Grounded against the current
board architecture: views are branches of `refresh_board()` keyed off the
`base_filter` radio (`all|locked|free|inflight|bytopic`), with widget models
`TopicColumn`/`InFlightColumn` and footer gating via `check_action()`.

**9.1 Structure.** A new `base_filter` value `bytrail` with its own binding
(concrete key chosen at implementation time via the shortcut manifest — the
board's key surface is crowded and t1162 is concurrently claiming `w`):

- **Trail selection**: entering the view with no active trail (or pressing the
  selection key) opens a modal listing discovered trails — title, owner task,
  scope kind, freshness badge, last updated. Selection is remembered for the
  session; **exactly one trail is active at a time** (a task referenced by
  several trails shows the active trail's wave/order only).
- **Waves as columns**: each wave renders as a column (modeled on
  `TopicColumn`: a non-reorderable `VerticalScroll` + `ColumnHeader`), header
  `W<ordinal> · <title>` with the wave's narrative available in the detail
  modal. Entries render as ordinary `TaskCard`s in `position` order with
  badges: classification glyph, confidence, and completion strike-through when
  the live task is Done/archived (live state read from the loaded task set,
  drift check on entry to the view).
- **Detail modal** (`enter`): full narrative projection — problem statement,
  recommendation summary, wave purpose/why-now/consequence-of-delay, entry
  rationale/expected outcome/caveats, observations, exclusions, evidence.
- **Non-board entries**: archived/missing/cross-repo member tasks render as
  read-only ghost cards (no move actions).

**9.2 State matrix.**

| State | Rendering |
|---|---|
| No trails exist | Empty-state hint: create via task/topic action or `/aitask-trail` |
| Trail current | Normal wave columns |
| Trail stale | Header badge `⚠ stale: <n> reasons`; drift reasons listed in detail modal; `r` offers refresh |
| Owner archived | Trail remains selectable (frontmatter scan includes archived); badge notes archived owner |
| Missing blob / corrupt manifest | Error card in place of waves; read path fails closed, offers `versions` fallback |
| Member task deleted/folded | Ghost card + drift reason; refresh re-evaluates membership |
| Multiple trails referencing focused task | Selection modal indicates "also in: <other trails>" |
| Singleton/Ungrouped topics | Irrelevant to trails (membership is explicit, not lane-derived) |

**9.3 Launch seams.** Trail creation/refresh from the board reuses the
existing agent-launch pattern (`resolve_dry_run_command(Path("."), "trail",
<args>)` → `AgentCommandScreen(..., operation="trail", operation_args=[...],
skill_name="trail", default_window_name="agent-trail-<id>")`), exactly as
Pick/Work-Report do. Contextual entry points:

- Task card → "Create/refresh trail" → `/aitask-trail <task_id>` (J2).
- By-Topic lane header → same action with the lane's root (J3).
- By-Trail view → `r` → `/aitask-trail --refresh <handle>` (J5).

Read-only parts of the flow (view, detail, compare, drift check) run inside
the board process; **every artifact write happens in the launched agent skill
after its own confirmation** — the board itself never writes trail content.

**9.4 Move-to-column commands (the passive report bridge).** In the By-Trail
view (user decision):

- `m` — move the focused entry's task to a chosen board column.
- `M` — move the focused wave's tasks (in `position` order) to a chosen column.

Both reuse the existing mutators (`TaskManager.move_task_col` appends at
bottom with `board_idx = max+10`, then `normalize_indices`), so a wave moved
into an empty column lands in wave order. This is an explicit, user-invoked
board mutation with the same semantics as a hand move — the trail artifact is
not consulted by anything downstream and records nothing about the move.
Cross-repo/archived entries are excluded (ghost cards).

## 10. Manager-report integration (t1162) — passive contract

**Decision: passive integration only** (user decision). The bridge is the
board column, not an API:

1. The user moves selected tasks or whole waves into a column from the
   By-Trail view (§9.4).
2. The t1162 Work Report flow reads that column exactly as designed — its
   gatherer's exact-membership + `boardidx`-ordering guarantee, ephemeral
   output, `--columns/--tasks` launch contract, and its `check_action`
   visibility rules are all untouched. No shared code, no new flags, no
   coupling to its in-flight children.

Consequences, stated explicitly:

- A report never gains or reorders tasks because a trail exists; trail
  influence reaches a report only through user-performed column moves the
  user can see on the board before launching the report.
- Trails remain durable artifacts; reports remain ephemeral drafts. Neither
  implies the other.
- A future explicit "report from trail" mode (`--trail <handle>`) is
  **documented-only** (§14 D-list): if ever built, it must be a separate
  user-selected mode that names the trail as its membership/order source and
  leaves column mode byte-identical. The passive bridge covers the practiced
  workflow without it.
- Coordination note: t1162's children are in flight; the only shared surface
  is the board binding/action region (both add bindings + `check_action`
  gates), so the By-Trail child is sequenced after t1162's board child
  (§14 coordination).

## 11. Lifecycle and concurrency analysis

| Event | Behavior (grounded in shipped substrate) |
|---|---|
| Create | `ait artifact create <owner> trail.json --kind implementation_trail --handle art:trail-<slug>` under the attach lock; frontmatter gains the stable `artifacts:` entry; `HANDLE:` line parsed by the skill. Handle collision → error, pick a new slug. |
| Refresh | `ait artifact update <handle> trail.json`; append-only version, `current` repoints; same-bytes no-op. Stale-base guard per §8.3. |
| Inspect / compare | `get` (current) / `get --version` / `versions`; read-only, lock-free safe (writes are atomic). |
| Owner folded | The `artifacts:` entry (handle) transfers to the fold primary automatically — the trail survives with a new owner. |
| Owner archived | Archival never decrefs artifacts; the trail stays resolvable and the board's frontmatter scan includes archived tasks. Expect staleness. |
| Owner hard delete | The delete guard refuses while the task still lists the artifact — the user must `ait artifact rm` (or the flow must transfer the handle) first. The board delete flow surfaces this instead of failing opaquely. |
| `ait artifact rm` | Manifest deleted, orphan blobs swept unless referenced elsewhere; recoverable from data-branch git history. |
| Member task archived/deleted/folded | Nothing happens to the artifact (membership is content, not reference). The change surfaces as drift (§8.2) and is resolved by refresh. |
| Missing blob / corrupt manifest | Manifest schema is validated on every load; reads fail closed. Board shows the error state (§9.2); older versions may still resolve via `get --version`. |
| Concurrent create (same slug) | Second create fails on handle collision (attach-lock serialized). |
| Concurrent refresh | Serialized by the attach lock; stale-base last-write-wins bounded by the §8.3 pre-write re-read guard; all versions retained. CAS extension deferred (conditional). |
| Cross-repo members | Task *references* work (notation + resolver); the artifact itself is not cross-repo addressable (no project-qualified handles in the substrate) — a trail is owned and stored in one project. Documented limit. |

## 12. Security and failure model

- **Bounded reads**: the gatherer reads task/plan frontmatter and named files
  under the repo's task directories only; it never shells out per candidate.
- **Validation**: trail JSON is validated against the schema before every
  write and after every read; unknown root keys, bad refs, or ordinal
  violations fail closed (no partial render, no partial write).
- **Path/handle validation**: handles must match the substrate regex; task
  refs must match the cross-repo notation; file paths in evidence are
  locators, never opened by renderers.
- **No secrets**: evidence records are identifiers + summaries; command
  outputs are summarized, not embedded.
- **Atomicity**: all writes go through the artifact CLI's transactional path
  (temp file + rename, path-scoped commit, rollback on failure); the skill
  never edits manifests or blobs directly.
- **Confirmation**: every artifact write and every task-metadata mutation
  (column moves) is explicit and user-visible before it happens; analysis and
  rendering are read-only.

## 13. Alternatives considered and decisions

**A. Decided (D = user decision in the t1210 design session):**

| # | Decision | Alternatives rejected — why |
|---|---|---|
| A1 (D) | Name: **Implementation Trail** | "Roadmap" (umbrella-task/product connotations), "Execution plan" (collides with aiplan), "Priority waves" (names the structure, not the capability) |
| A2 (D) | **JSON canonical + narrative-first schema**, deterministic renderings | Structured Markdown + parser (validation fragility, prose/structure drift); paired JSON+MD artifacts (two sources of truth) |
| A3 (D) | Explicit owner task for cross-topic/ad-hoc | Auto-picked owner (surprising lifecycle coupling); unowned artifacts (unsupported by substrate) |
| A4 | No implicit planning-container tasks | Container-per-trail adds board clutter without lifecycle benefit; revisit only if ownerless trails become a real need |
| A5 (D) | **Dedicated By-Trail view in v1** | Overlay-badges-in-By-Topic first (weaker wave visibility; the wave structure *is* the product); detail-modal-only (no in-context ordering at all) |
| A6 (D) | Many trails per task; **one active trail** in the UI | Unique membership (forbids legitimate overlap — see the release-hardening fixture); showing all trails' badges at once (unreadable, ambiguous ordering) |
| A7 (D) | Read-only analysis; single confirmed write; column moves are explicit user commands | Analysis auto-writing artifacts (removes review); analysis mutating depends/priority (advisory would impersonate the DAG) |
| A8 (D) | **Passive t1162 bridge via column moves** | Report enrichment mode (couples to in-flight t1162 internals); trail-driven report membership (violates exact-membership contract) |
| A9 (D) | Input digest + named drift reasons + targeted refresh subskill | TTL staleness (noisy both directions); manual-only (defeats the dynamic-trail requirement); every-board-change invalidation (repaints are not drift) |
| A10 | Duplicating cards across topic lanes — rejected outright | Reintroduces the ambiguity `anchor` exists to prevent; trails project ordering in their own view instead |

**B. Explicitly rejected for v1, with disposition** (every exclusion carries
one): see §14's D-list — each is either *conditional* (create when a named
trigger occurs) or *documented-only*.

## 14. Implementation decomposition (copy-ready)

Sequenced child tasks (create under t1210 after design approval; each child
owns its tests). Coordination constraint: **T4/T5 touch the board
bindings/`check_action` surface that t1162_4 also edits — land them after
t1162_4 merges** (serialize, don't parallelize, shared-surface collisions).

- **T1 — Trail schema library and validator** (`lib/trail_schema.py`,
  `tests/test_trail_schema.py`). Load/validate/canonicalize trail JSON
  (structural validation equivalent to the design-contract checks, plus the
  schema patterns); adopt the fixtures as test data; export the canonical
  normalization used by the digest (versioned with the schema). Pure Python,
  stdlib only. *No dependencies.*
- **T2 — Gatherer + digest/drift helper**
  (`.aitask-scripts/aitask_trail_gather.sh` → `lib/trail_gather.py`,
  `tests/test_trail_gather.py`). Scope/owner resolution, input snapshot,
  `input_digest`, and the `trail-drift` verb producing named drift reasons
  from a stored trail vs live state. Line-protocol output; helper
  whitelisted. This is the riskiest spike (digest normalization + drift
  fidelity) — it lands **first among the behavioral pieces** and before any
  UI. *Depends: T1.*
- **T3 — `/aitask-trail` skill** (create + refresh flows). Claude Code
  source-of-truth skill + stub/`.md.j2` per conventions; agent wrappers
  suggested as separate follow-ups per the cross-agent porting rule.
  Registers the `trail` codeagent operation **including `.defaults` entries in
  both seed and live `codeagent_config.json`** (omitting them silently gets
  the heavy fallback model). Read-only analysis → review → single confirmed
  `ait artifact create/update`. *Depends: T2.*
- **T4 — Board By-Trail view** (`bytrail` base filter, trail discovery scan,
  selection modal, wave columns, badges, detail modal, drift check on entry,
  `r` refresh launch via `AgentCommandScreen`). Binding registered in the
  shortcut manifest; `check_action` gates move/sort actions per view.
  Render-level tests (assert `widget.render().plain`) + Pilot tests.
  *Depends: T3; land after t1162_4 (shared board surface).*
- **T5 — Move-to-column commands** (`m`/`M` in By-Trail view) using
  `move_task_col` + `normalize_indices`; wave moves preserve `position`
  order; ghost cards excluded. Unit tests over the manager mutators plus a
  Pilot test. *Depends: T4.*
- **T6 — Documentation.** Website workflow page (plus the hand-curated
  bullet in workflows `_index.md`), board docs update (document the new view
  alongside board/monitor/minimonitor/codebrowser/settings/brainstorm), and
  aidocs current-state sync of this RFC. *Depends: T4/T5.*
- **T7 — Manual verification (aggregate sibling).** Human-only checks: live
  trail creation from a task/topic/By-Trail view, refresh after archiving a
  member, stale badge appearance, wave move-to-column then a t1162 work
  report from that column, error states (deleted blob). *Depends: all.*

**D-list — deferred items with dispositions:**

| Item | Disposition |
|---|---|
| CAS (`update --expect-current`) on the artifact CLI | **Conditional**: create the task when concurrent refreshes of one trail become a practiced workflow; v1 guard per §8.3 |
| By-Topic overlay/badges | **Documented-only**: superseded by the dedicated view; revisit on user demand |
| Explicit `--trail` report mode in t1162's skill | **Documented-only**: passive column bridge covers the need; any future mode per §10 rules |
| Confirmed advisory→`depends`/priority conversion flow | **Conditional**: create when a trail consumer actually wants recorded ordering; must be per-change confirmed |
| Cross-repo artifact resolution (project-qualified handles) | **Documented-only**: substrate limitation recorded in §11 |
| Trail-aware auto-creation of follow-up tasks during refresh | **Documented-only**: refresh may *propose* candidates; task creation stays a user-confirmed action in the skill session |

## 15. Wireframes (compact)

By-Trail view (waves as columns; active trail in header):

```
┌ ait board — By-Trail: "Gate framework landing order" (⚠ stale: 2) ─────────┐
│ W1 · Clear conflicts   W2 · Fix baseline   W3 · Prove engine   W4 · Gates  │
│ ┌───────────────────┐ ┌────────────────┐ ┌────────────────┐ ┌───────────┐ │
│ │ ✔ t1147 (landed)  │ │ ◆ t1183       │ │ ● t635_29      │ │ ● t635_33 │ │
│ │   hard prereq     │ │   hard prereq │ │   core · med   │ │   core    │ │
│ └───────────────────┘ │   conf: high  │ │   ⚑ premise    │ │ ● t1181   │ │
│                       └────────────────┘ │     re-checked │ └───────────┘ │
│                                          └────────────────┘               │
│ [enter] details  [r] refresh  [m] move task  [M] move wave  [s] select    │
└────────────────────────────────────────────────────────────────────────────┘
```

Trail selection modal:

```
┌ Select trail ───────────────────────────────────────────────┐
│ ▸ Gate framework landing order   owner t635    ⚠ stale (2)  │
│   Shadow review-loop order       owner t1208   ✓ current    │
│   Release hardening (x-topic)    owner t1187   ✓ current    │
│     └ also references: t1187 (Shadow review-loop order)     │
└─────────────────────────────────────────────────────────────┘
```

Detail modal (entry focus):

```
┌ t635_29 — W3 · Prove the orchestrator engine ──────────────┐
│ classification: core · confidence: medium                   │
│ Why here: verdict semantics are the contract every wave-4   │
│ gate implements against. …                                  │
│ Expected: demonstrated engine run with recorded ledger …    │
│ Caveat: premise re-verified against current source.         │
│ Evidence: ev-premise-check (task_file aitasks#635_29)       │
└─────────────────────────────────────────────────────────────┘
```

Stale banner + refresh confirmation (in the launched skill):

```
Trail "gate-framework-landing" is stale (2 reasons):
  • task_completed: t1147 archived 2026-07-11 — wave 1 partially satisfied
  • new_related_task: t1181 created after generation
Refresh will re-evaluate waves 1 and 4 only. Proceed? [review diff / write v3 / cancel]
```

## 16. Verification traceability (performed for this RFC)

- Artifact claims (§5, §11) walked against `aitask_artifact.sh` verb surface,
  `artifact_manifest.py` schema/locking, and the CLI pinning tests — including
  the no-CAS finding, fold handle transfer, hard-delete guard, and orphan
  sweep behavior.
- Board claims (§9) walked against `refresh_board()`'s per-`base_filter`
  branches, `TopicColumn`/`InFlightColumn` widget models, `check_action`
  gating, `move_task_col`/`normalize_indices`, and the
  Pick/Work-Report launch patterns.
- t1162 claims (§10) walked against its approved plan: gatherer protocol,
  exact-membership/ordering guarantee, ephemeral output, `w` binding and
  By-Topic visibility rules, and child-task status (t1162_1 Implementing).
- Schema and fixtures validated by `tests/test_implementation_trail_design.py`
  (23 checks, including the cross-topic/multiple-trail and no-anchor pins),
  with a verified failing negative control.
