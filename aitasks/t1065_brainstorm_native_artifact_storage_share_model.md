---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [html_plans, task_attachments]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-24 21:56
updated_at: 2026-06-25 10:38
---

## Brainstorm / design (not implementation)

Design a **unified, native "artifact" capability** for aitasks that ties
together three existing strands into one coherent model, and defines the seams
between them. This is a brainstorming/design task — produce a design doc and a
decomposition, not code. (t774 itself says HTML-plan support "needs to be
explored in brainstorming mode before implementation".)

The trigger: t1030 (durable attachment storage) and Claude Code's hosted
"artifacts" feature (https://code.claude.com/docs/en/artifacts) are
complementary — how do we get the *value* of shareable artifacts natively?

### The three strands are one feature seen from three angles

| Strand | Task | Angle |
|---|---|---|
| **HTML plans** | t774 (high pri) | Artifact as a first-class native HTML output — mockups, prototypes, option-comparisons — living alongside the markdown plan |
| **Attachments** | t1030 (design-only) | Artifact as durable, content-addressed storage with pluggable backends |
| **Sharing** | *this task* | Artifact as a shareable native render whose handle resolves on any machine with the project config |

Reference (do **not** fold) t774 and t1030 — they remain distinct efforts; this
task is the connective design that unifies their concept and adds the
sharing/storage-abstraction dimension.

### Decisions already taken in brainstorming (honor these)

1. **NOT Claude-native artifacts.** Rejected as the implementation substrate:
   too much complexity, locked to Claude Code + Team/Enterprise + claude.ai
   login (not API-key/Bedrock/Vertex), and shaped around hosted pages we don't
   control. We want a **native implementation** whose value we own. (Still fine
   to *learn from* their UX — versioning, share-scoping, "update in place".)

2. **Do NOT couple artifact sharing to AppLink.** Earlier idea was to serve a
   `task_artifact` verb over the AppLink WebSocket server
   (`.aitask-scripts/applink/`). Rejected: unwanted coupling, and AppLink is
   LAN-only in v1 (cross-network relay is explicitly deferred — see
   `aidocs/applink/protocol.md` §Roadmap). AppLink is at most a *consumer* that
   reads through the shared abstraction; it is not the share/storage substrate.

3. **Storage/sharing = a higher-level API that abstracts the storage layer**,
   the way task-management tools (Monday, Asana, etc.) attach files via existing
   cloud storage/file services. Concretely this is t1030's backend-adapter seam
   (`aidocs/task_attachments_design.md` §5 + §"Universal local cache"),
   **generalized to serve both attachments and artifacts**:
   - Pluggable backends over existing services (S3-compatible / R2 / GCS /
     GDrive / GitHub-release / …) — the framework owns no hosting.
   - The shared **"link" is a project-config-resolvable handle**, not a raw URL:
     it can be retrieved on *any* PC that has the project configuration.
   - A **wrapper bash script reads the blob into a LOCAL FILE CACHE** for local
     access and **writes back** to the storage layer (put/get/head contract).
   - Hash-first references (per t1030) so backend migration never rewrites task
     files.

4. **HTML task plans are a "special" artifact.** Unlike attachments (auxiliary
   *inputs*), an HTML plan is an **integral part of the task specification**.
   But it can be **much larger** than a markdown plan, so committing it inline
   on the `aitask-data` branch alongside markdown plans (t774's current "3rd
   file, committed/archived/zipped like markdown plans" framing) may be **too
   heavy**. A unified artifact data layer with a **local file cache** is likely
   the better home for HTML plans too — they flow through the storage
   abstraction (backend + cache) rather than being committed inline. **This is a
   key design question for the brainstorm to settle** (commit-inline vs.
   artifact-in-storage-layer-with-cache), and it has a coordination impact on
   t774's planned approach.

### The seam to protect

Keep three concerns **separate and pluggable**:

1. **Artifact concept / render** — what the artifact *is* (HTML plan, mockup,
   report, attached file) and how it's produced/rendered.
2. **Storage sink** — the pluggable backend (t1030 adapter) + universal local
   cache; project-config-driven resolution; put/get/head/write-back.
3. **Share handle** — the portable, project-config-resolvable reference that
   any configured machine can resolve back through the storage layer.

One artifact model, pluggable storage, pluggable sharing. Do not let any two of
these fuse.

### Cross-cutting concerns to work through

- **Writing artifacts during "planning" mode.** Code agents in planning mode
  can't write arbitrary files (only the internal markdown plan). t774 flags this
  as the blocker. The **gates framework (t635)** multi-stage processing is the
  intended mechanism (plan → HTML artifact with mocks/choices → user refinement
  → actionable markdown plan). Gates are not fully implemented yet — design the
  seam, don't depend on shipped gate code.
- **Relationship to t1030's content-addressing.** Artifacts are *versioned /
  mutable* (HTML plan edited in place); t1030 attachments are *immutable blobs
  keyed by content hash*. Reconcile: does an artifact get a stable logical id
  with versioned blobs underneath, vs. attachment = one hash? Settle how
  "update in place at the same handle" coexists with hash-first storage.
- **Lifecycle.** Archive/query/zip parity with markdown plans (t774's ask) but
  via the storage layer; GC / refcount (t1030 `index.json`); fold semantics
  (artifacts re-bind on fold).
- **Backend resolution from project config.** Where the per-project backend
  config lives (`aitasks/metadata/project_config.yaml`?), and how a teammate's
  machine resolves the same handle.

### North star (Direction 4 — out of scope to detail now)

The eventual destination is **team collaboration**: shareable artifacts +
shared/observable gates + multi-agent-and-human review + connection to a
messaging platform — with the existing **shadow-agent** as the local precursor
("like I now try to do with shadow agent"), and "work goes on while your laptop
is off the network" as a goal. This is the probable long-term direction, but
**too many building blocks are not ready** (gates not fully implemented,
messaging-platform integration does not exist, attachment/artifact support still
to be designed). Note it as the horizon these bricks build toward; do **not**
attempt to scope its details in this task.

### Deliverables

- A design doc (sibling to `aidocs/task_attachments_design.md`) covering the
  unified artifact model, the render/storage/share seam, the HTML-plan
  commit-inline-vs-storage-layer decision, the planning-mode-write seam (via
  t635 gates), and the t774/t1030 coordination impact.
- A proposed decomposition into implementable child tasks, sequenced against the
  building blocks (t1030 backend seam first, then artifact concept, then
  sharing).
- Explicit coordination notes back into t774 and t1030 where this design changes
  or constrains their planned approach.

### Rejected alternatives (record so they're not re-litigated)

- Claude-native artifact passthrough (complexity, agent/plan/login-locked).
- AppLink-coupled sharing (unwanted coupling; LAN-only).
- Forcing artifacts through pure immutable-hash storage (loses
  update-in-place / versioning).

### References

- `aidocs/task_attachments_design.md` — t1030 attachment design (backend
  adapter §5, universal local cache, hash-first model).
- t774 (`aitasks/t774_support_for_html_plans.md`) — native HTML-plan file type.
- t635 — gates / multi-stage framework (planning-mode write seam).
- `aidocs/applink/protocol.md` — why AppLink is not the share substrate
  (LAN-only v1).
- `aidocs/slack/pros_and_cons.md` — the team-collaboration ("claude tag")
  north-star notes.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-25T07:38:23Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-25T07:38:25Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-25T08:08:20Z status=pass attempt=1 type=human
