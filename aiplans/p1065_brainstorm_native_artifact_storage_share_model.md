---
Task: t1065_brainstorm_native_artifact_storage_share_model.md
Base branch: main
plan_verified: []
---

# Plan — t1065: Brainstorm/design the unified native artifact storage & share model

## Context

t1065 is a **brainstorming/design** task (not implementation). It must unify
three existing strands into one coherent "artifact" capability and define the
seams between them:

- **HTML plans** (t774, high-pri) — artifact as a first-class native HTML output.
- **Attachments** (t1030, design-only) — artifact as durable, content-addressed storage.
- **Sharing** (this task) — artifact as a shareable handle that resolves on any
  machine with the project config.

The deliverable is a **design doc** (sibling to `aidocs/task_attachments_design.md`)
plus a **proposed decomposition** and **coordination notes** back into t774 and
t1030. No code, and — per the user's decision — **no live child tasks** are
created; the decomposition lives in the doc as a proposal (like t1030 §11).

The task pre-settles four decisions (honor them): NOT Claude-native artifacts;
do NOT couple sharing to AppLink; storage = a higher-level pluggable abstraction
over existing cloud services; HTML plans are a "special" artifact.

### Grounding established during planning

- **Gates (t635):** Phases 1–3 **shipped**, Phase 4 in progress. Ledger,
  orchestrator (`aitask_run_gates.sh`, `lib/gate_orchestrator.py`,
  `lib/gate_ledger.py`), re-entry, deferred archival, board/monitor views all
  exist. **Gap:** there is *no artifact-producing gate type* — the roadmap names
  "artifact-producing follow-ups" as a third family but leaves them as
  pseudo-gates (`aidocs/gates/integration-roadmap.md:38-46`). This is the seam
  the planning-mode-write design must propose.
- **AppLink:** confirmed **LAN-only v1** (`aidocs/applink/protocol.md:29,40`);
  not a storage/share substrate — at most a consumer. ✓ matches decision 2.
- **Slack north star** (`aidocs/slack/pros_and_cons.md`): team-collaboration
  vision (shareable artifacts + observable gates + multi-agent/human review +
  messaging), with shadow-agent as the local precursor. Vision-only, out of
  scope — document as the horizon.

### User design decisions (collected this session)

1. **Artifact model = a mutable-pointer layer over t1030's immutable hash blobs.**
   One model: `art:<id>` → a `current` pointer to a content hash; each version is
   an immutable t1030 hash blob; "update in place" = repoint the id. An
   **attachment is the degenerate case** (single version, never repointed).
2. **HTML plans live in the artifact storage layer, NOT committed inline.** For
   shareable/project use they **target the configured remote backend**; but every
   HTML plan is **always materialized through the local cache** for open / edit /
   preview / offline reads. The task/plan stores **only a stable artifact handle**;
   backend migration or cache refresh must **never rewrite task files**. (Zero-config
   `local` backend is the fallback when no remote backend is configured.)
3. **Decomposition = proposal inside the design doc only**; create no child tasks.

## Approach

Single deliverable file authored in Step 7, plus two coordination edits. No code.

### 1. New design doc — `aidocs/unified_artifact_design.md`

Sibling to `task_attachments_design.md`, same RFC tone. Sections:

1. **Goals & non-goals** — unify HTML plans / attachments / sharing under one
   artifact model + three pluggable seams; own the value natively. Non-goals:
   Claude-native passthrough, AppLink coupling, team-collab detailing (north star).

2. **The three concerns to keep separate and pluggable** (the seam to protect):
   - **(A) Artifact concept / render** — what an artifact *is* (HTML plan, mockup,
     report, attached file) and how it's produced/rendered.
   - **(B) Storage sink** — pluggable backend (generalized t1030 adapter) +
     universal local cache + the **artifact manifest** (mutable id→current→versions→
     backend index, §4b); project-config-driven resolution; put/get/head/write-back.
   - **(C) Share handle** — portable, project-config-resolvable reference any
     configured machine resolves back through the storage layer.
   *One artifact model, pluggable storage, pluggable sharing — no two fuse.*

3. **Artifact data model (decision 1) — the stable-handle / mutable-manifest split.**
   `art:<id>` is a **stable logical handle**, assigned once and never rewritten.
   All **mutable** resolution state — the `current` version pointer, the ordered
   `versions:` list of immutable `sha256:` hashes, and the `backend` — lives in a
   separate **artifact manifest** (the storage-index layer), **not** in task/plan
   frontmatter. Repoint (HTML-plan update) = new version + moved `current` **in the
   manifest**; backend move = `backend` change **in the manifest**. The task file is
   untouched by any of these. Each version is an immutable t1030 hash blob; history
   is the manifest's version list. Attachment = single-version artifact, never
   repointed (its mapping is trivially stable). This is what actually makes decision
   2's "handle-only, never rewrite task files" hold: the churny state is quarantined
   in the manifest, the stable handle is all the task carries.

   *Why this differs from t1030:* t1030 stores an attachment's `hash`/`backend`
   **inline** in frontmatter and that is fine **because attachments are immutable** —
   the inline value never changes. Artifacts are mutable, so the same inline scheme
   would rewrite the task file on every update; hence the manifest indirection. The
   doc must call this contrast out explicitly.

4. **Frontmatter schema (handle-only + minimal classification).** New optional
   `artifacts:` list whose entries carry **only stable, set-once fields**: the
   `handle` (`art:<id>`), `kind` (`html_plan|mockup|report|attachment|…`), and an
   optional human `name`. **No `current`, `versions`, or `backend` in frontmatter** —
   those are manifest-owned (§3, §5). The entry is immutable for the life of the
   artifact; only the manifest changes as the artifact evolves. Note the open
   reconciliation with t1030's inline `attachments:` (recast immutable attachments as
   single-version artifacts under one schema vs. keep `attachments:` as a typed,
   inline-hash view) → flagged as coordination, not decided here.

4b. **Artifact manifest (the mutable resolution layer).** Define the manifest as the
   single home for `art:<id> → { current: sha256, versions: [sha256…], backend,
   resolution hints }`. It generalizes t1030's `index.json` (§9 reuses it for
   version-aware GC). Open design point to surface (not decide): **where the manifest
   lives and how it travels** — a committed index in the storage layer (zero-config
   `local` backend) vs. a backend-resident manifest resolved via project config for
   shareable/remote artifacts — under the constraint that updating it must **never**
   touch a task file, and any configured PC can resolve `art:<id>` through it.

5. **Storage sink (generalize t1030 §5)** — promote t1030's
   `attachment_backend.sh` (put/get/head/delete/list) + universal cache to an
   **`artifact_backend`** that serves *both* attachments and artifacts. Same
   content-addressed naming; same backend table (local / S3-compat / GCS /
   gh-release / gdrive). A **wrapper bash script reads a blob into the local file
   cache and writes back** (put/get/head/write-back contract). Zero-config `local`
   backend is the default for getting started and small immutable attachments
   (committed to `aitask-data`, archive/query/zip parity for free); shareable or
   large artifacts prefer a configured backend — see §7 for the HTML-plan policy.

6. **Share handle (decision: resolvable, not a raw URL)** — `art:<id>` resolves
   through the **manifest** (§4b) + **project config** that names the backend +
   location (proposed home: `aitasks/metadata/project_config.yaml`, new `artifacts:`
   block — keep separate from execution profiles & userconfig). The task file holds
   only the handle; the manifest holds the current hash + backend; the config names
   how to reach the backend. Hash-first underneath so backend swaps touch only the
   manifest, never task files. Any PC with the project config resolves the same
   handle: handle → manifest → backend → fetch → verify hash → cache → local path.

7. **HTML plans as a "special" artifact (decision 2 — the central question).**
   Markdown plan stays inline on `aitask-data` (small, diffable, authoritative).
   The HTML plan becomes an artifact, **not** committed inline (revises t774's "3rd
   committed file" framing). Crisp backend policy (resolve the earlier ambiguity):
   - **Configured remote backend = the normal/preferred home** for any HTML plan
     meant to be shared across machines or with a team. This is the default target
     whenever a backend is configured.
   - **Local cache is always active and mandatory** — every HTML plan, regardless of
     backend, is materialized through `~/.cache/...` for open / edit / preview /
     offline reads. The task/plan carries only the `art:<id>` handle; cache refresh
     or backend migration never rewrites task files.
   - **`local` backend is bootstrap/dev/offline-only**, not the steady-state home for
     shareable plans. State its **cross-machine sharing limits explicitly**: a
     local-backend artifact only resolves on machines that have the `aitask-data`
     branch carrying it, and it bloats that branch for large HTML — which is exactly
     why shareable plans should target a remote backend. It exists so a fresh
     `ait setup` works with zero config and so offline work is possible, not as the
     place shareable HTML plans live.
   - Archive/query/zip parity is delivered **through the storage layer**, not inline.

8. **Planning-mode-write seam (via t635 gates) — explicit handle lifecycle.** Code
   agents in plan mode can't write arbitrary files (only the internal markdown plan).
   Propose an **artifact-producing gate archetype** (the third gate family the
   roadmap leaves unbuilt): a *post-approval* verifier whose "pass = artifact
   produced (or explicitly waived)". The doc must make the **handle-binding lifecycle
   explicit** — chosen approach: **the handle is preallocated (derivable by
   convention) during planning, content is materialized post-approval, and the
   approved plan body is never patched.** Concretely:
   1. **Planning (read-only):** the markdown plan references the HTML plan by its
      **derivable handle** `art:<id>` (e.g. `art:t<task>-htmlplan`) — pure text, no
      file write, no content yet. The approved plan is therefore already
      self-consistent; nothing is patched into it afterwards.
   2. **Approval:** plan approved as-is, handle reference already present.
   3. **Post-approval window (Step 7 / the artifact gate):** the gate (a) generates
      the HTML content, (b) stores it as an immutable hash blob via the backend,
      (c) creates/updates the **manifest** entry `art:<id> → current/versions/backend`,
      (d) writes the **set-once, handle-only `artifacts:` entry** into task frontmatter
      — exactly the existing post-approval write pattern (Step 7 already writes risk
      fields / mitigations there because plan mode is read-only). The plan **body** is
      never rewritten; only frontmatter (handle, set-once) and the manifest (mutable).
   4. **Refinement loop:** later HTML edits = new version + repoint **in the
      manifest**; the handle, the plan's reference, and the frontmatter entry all stay
      stable.

   Design the seam only; do **not** depend on shipped artifact-gate code (it doesn't
   exist yet — §grounding).

9. **Lifecycle** — archive/query/zip parity through the storage layer; GC/refcount
   reading the **manifest** (§4b, generalizing t1030's `index.json`) to count
   artifact **versions** (a hash is GC-able only when no artifact version in any
   manifest references it); fold semantics = re-bind the artifact's manifest entry to
   the primary task on fold (handle in the folded task's frontmatter moves; manifest
   ownership updates), like attachments.

10. **Relationship to t1030 content-addressing** — explicit reconciliation table:
    artifact = **stable handle in frontmatter** + mutable manifest entry (current +
    versioned hash blobs); attachment = one immutable hash = single-version artifact
    whose mapping never changes (so t1030's inline-hash frontmatter is safe).
    "Update in place at the same handle" coexists with hash-first storage because the
    repoint happens in the manifest, not the task file — the crux the whole model
    turns on.

11. **Proposed decomposition (proposal only, sequenced against building blocks)** —
    e.g.: (a) storage abstraction generalization on top of t1030's local backend;
    (b) artifact pointer/version model + `artifacts:` frontmatter; (c) share-handle
    resolution from project config + cache wrapper; (d) HTML-plan-as-artifact
    integration (coordinate t774); (e) artifact-producing gate archetype (coordinate
    t635). Each with `depends:` notes on t1030 / t774 / t635-Phase4. **No tasks created.**

12. **North star (Direction 4)** — note team-collaboration (shareable artifacts +
    observable gates + multi-agent/human review + messaging; shadow-agent as
    precursor; "work continues while your laptop is offline") as the horizon these
    bricks build toward. Explicitly out of scope to detail.

13. **Rejected alternatives** — Claude-native passthrough; AppLink-coupled sharing;
    forcing artifacts through pure immutable-hash storage (loses update-in-place).

14. **Cross-references** — t774, t1030 (`task_attachments_design.md`), t635
    (`aidocs/gates/`), `aidocs/applink/protocol.md`, `aidocs/slack/pros_and_cons.md`,
    `gitremoteproviderintegration.md` (dispatcher pattern model).

### 2. Coordination notes (bidirectional links)

- **`aitasks/t774_support_for_html_plans.md`** — append a short
  "## Coordination — t1065 unified artifact model" note: HTML plans should route
  through the artifact storage layer (remote backend target + mandatory local-cache
  materialization, handle-only in the task), **revising** the "3rd file committed
  like markdown plans" approach; the planning-mode-write blocker is addressed by the
  artifact-producing gate archetype. Link to `aidocs/unified_artifact_design.md`.
- **`aitasks/t1030*` (attachments design task)** — append a coordination note: the
  backend adapter + universal cache should be designed to serve **both** attachments
  and artifacts (generalized `artifact_backend`); attachments are the single-version
  degenerate case of the artifact pointer model; t1030's **inline-hash frontmatter is
  safe only because attachments are immutable** — mutable artifacts keep current/
  versions/backend in the manifest, not the task file; flag the `attachments:` vs
  `artifacts:` frontmatter reconciliation (and whether `index.json` becomes the shared
  manifest). Link to the new doc. (Resolve the exact t1030 file path at implementation
  time via `aitask_query_files.sh`.)

Both edits committed with `./ait git` (task-data branch).

## Files

- **New:** `aidocs/unified_artifact_design.md` (the deliverable).
- **Edit:** `aitasks/t774_support_for_html_plans.md` (coordination note).
- **Edit:** `aitasks/t1030*.md` (coordination note; path resolved at impl time).
- The plan file in `aiplans/` (externalized record).

## Verification

This is a design/doc task — no build/tests.

- Doc reads coherently end-to-end; every section above is present and the four
  pre-settled decisions + three user decisions are honored verbatim.
- Internal cross-references resolve to real files (`task_attachments_design.md`,
  `aidocs/gates/*`, `aidocs/applink/protocol.md`, `aidocs/slack/pros_and_cons.md`,
  the t774/t1030 task files).
- The three-concern seam (render / storage / share) is explicit and the doc states
  no two may fuse.
- Coordination notes appear in **both** t774 and t1030 with reverse links to the
  new doc, and are committed via `./ait git`.
- No code files changed; no child tasks created.

## Risk

### Code-health risk: low
- None identified. The deliverable is one new markdown design doc plus two
  additive, reversible coordination notes appended to existing task files. No
  code, no build/test path, no executable surface touched.

### Goal-achievement risk: low
- The design's seam decisions (esp. the `attachments:` vs `artifacts:`
  frontmatter reconciliation, and version-aware GC) may need iteration to fully
  satisfy the cleanliness bar. · severity: low · → mitigation: handled inline
  via the plan review/revise loop before any commit — no follow-up task warranted
  (this is a brainstorm doc, fully reviewable and revisable pre-commit).

_No before/after risk-mitigation tasks planned (risk_mitigations_planned = false)._
