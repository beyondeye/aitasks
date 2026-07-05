# Unified Native Artifact Model — Storage, Render & Share

A single **native "artifact" capability** for aitasks that unifies three
strands — HTML plans, durable attachments, and shareable renders — under one
concept model, with three pluggable seams (render / storage / share) that are
kept deliberately separate.

Status: **brainstorm / design (RFC)**. This is a connective design that ties
together work tracked elsewhere; it produces a concept model, the seam
boundaries, the key reconciliations, and a proposed decomposition. It is **not**
an implementation, and it creates no tasks. Open questions are called out
inline.

This doc is a sibling to [`task_attachments_design.md`](task_attachments_design.md)
(t1030) and intentionally generalizes that design. It does **not** supersede or
fold t774 or t1030 — they remain distinct efforts; this is the connective tissue
that unifies their concept and adds the storage-abstraction and sharing
dimensions.

## 1. Goals & non-goals

### Goals

- Give aitasks one **artifact concept** that subsumes HTML plans, attachments,
  and other native renders (mockups, reports), each produced/rendered its own
  way but stored and shared through one substrate.
- Make the **value of "shareable artifacts" native and owned** — not delegated to
  a hosted, login-gated, vendor-shaped feature.
- Keep three concerns **separate and independently pluggable**: what an artifact
  *is* (render), where its bytes live (storage), and how a reference resolves on
  another machine (share).
- Resolve the **HTML-plan storage question** (commit-inline vs. storage-layer)
  and the **artifact ↔ attachment reconciliation** (mutable/versioned vs.
  immutable/hash-keyed) so t774 and t1030 can build on a settled model.

### Non-goals

- **Claude-native artifacts as the substrate.** Rejected (see §13): too much
  complexity, locked to Claude Code + Team/Enterprise + claude.ai login (not
  API-key / Bedrock / Vertex), and shaped around hosted pages we don't control.
  We learn from their UX (versioning, share-scoping, update-in-place) but own the
  implementation.
- **Coupling sharing to AppLink.** AppLink is LAN-only in v1
  ([`applink/protocol.md`](applink/protocol.md) §Roadmap) and is at most a
  *consumer* that reads through the shared abstraction — never the storage/share
  substrate.
- **Detailing team collaboration.** That is the north star (§12), not this design.
- **Building the framework's own hosting.** The storage seam abstracts *existing*
  services (S3-compatible / R2 / GCS / GDrive / GitHub releases / …); the
  framework owns no servers.

## 2. The three concerns — the seam to protect

The whole design rests on keeping three concerns **separate and pluggable**. One
artifact model, pluggable storage, pluggable sharing. **Do not let any two of
these fuse.**

| # | Concern | What it owns | Pluggable along |
|---|---------|--------------|-----------------|
| **A** | **Artifact concept / render** | What an artifact *is* (HTML plan, mockup, report, attached file) and how it is produced/rendered | render type / producer |
| **B** | **Storage sink** | Where the bytes live: pluggable backend + universal local cache + the **artifact manifest** (§4b); `put`/`get`/`head`/write-back | backend (local / S3-compat / GCS / gh-release / gdrive) |
| **C** | **Share handle** | A portable, project-config-resolvable reference that any configured machine resolves back through the storage layer | resolution / config |

The key discipline: a render (A) never knows which backend (B) holds it; a
handle (C) never embeds a raw backend URL; the storage sink (B) never assumes a
single render type. The sections below define each concern and the contracts
between them.

## 3. Artifact data model — the stable-handle / mutable-manifest split

An **artifact** is a stable logical thing with an evolving content body.

- `art:<id>` is a **stable logical handle** — assigned once, **never rewritten**.
- All **mutable** resolution state lives in a separate **artifact manifest**
  (§4b), *not* in task/plan files:
  - `current` — pointer to the content hash of the live version.
  - `versions` — ordered list of immutable `sha256:` content hashes.
  - `backend` — where the canonical copy currently lives.
- Each **version** is an immutable content-addressed blob — the *same* blob
  substrate t1030 uses for attachments (SHA-256 of the bytes).

Operations map cleanly onto this split:

| Operation | Effect | Touches |
|---|---|---|
| Create artifact | mint `art:<id>`, write v1 blob, set `current` | manifest + backend |
| Update in place (e.g. edit HTML plan) | write new blob, append to `versions`, move `current` | manifest + backend |
| Move backend | change `backend`, re-`put` blobs in the new backend | manifest + backend |
| Reference from a task | store the **handle only** | task frontmatter (set once) |

**This is what makes "handle-only, never rewrite task files" actually hold.** The
churny state (current / versions / backend) is quarantined in the manifest; the
stable handle is all a task carries. A backend migration or a cache refresh never
touches a single task file.

**An attachment is the degenerate case:** a single-version artifact that is never
repointed. Its mapping is trivially stable.

### Why this differs from t1030's inline scheme

t1030 stores an attachment's `hash` and `backend` **inline** in task frontmatter
(`task_attachments_design.md` §3) — and that is **correct**, *because attachments
are immutable*: the inline value never changes, so it never rewrites the task
file. Artifacts are **mutable**, so the same inline scheme would rewrite the task
file on every edit or backend move. Hence the manifest indirection. The two are
reconciled, not in conflict (§10): immutable → safe inline; mutable → manifest.

## 4. Frontmatter schema — handle-only + minimal classification

Tasks (and, for HTML plans, the plan record) gain an optional `artifacts:` list.
Every entry carries **only stable, set-once fields**:

```yaml
---
# ... existing task frontmatter ...
artifacts:
  - handle: art:t774-htmlplan        # stable logical handle (set once, never rewritten)
    kind: html_plan                  # html_plan | mockup | report | attachment | ...
    name: "Login flow mockups"       # optional human label
---
```

**Field rules**

- `handle` is canonical and required; it is the *only* link from the task to the
  artifact. It never changes for the life of the artifact.
- `kind` classifies the render type (drives how consumers display/produce it).
- `name` is advisory display metadata.
- **No `current`, `versions`, or `backend` here.** Those are manifest-owned
  (§4b). The entry is immutable for the artifact's life; only the manifest
  changes as the artifact evolves.

Open reconciliation with t1030's inline `attachments:` (see §10 and the t1030
coordination note): either recast immutable attachments as single-version
artifacts under this one schema, or keep `attachments:` as a typed, inline-hash
*view* (safe because immutable) alongside `artifacts:`. **Not decided here** —
flagged for joint t1030/t1065 resolution.

### 4b. The artifact manifest — the mutable resolution layer

The **manifest** is the single home for an artifact's mutable state:

```
art:<id>  →  { current: sha256:…,
               versions: [sha256:…, sha256:…, …],
               backend: <name>,
               resolution hints (optional, advisory) }
```

The manifest is a **new sibling ledger** next to t1030's per-blob attachment
meta files (t1030 shipped per-blob refcount files at `attachments/meta/`, not a
global `index.json`); §9 uses it for version-aware GC.

**Settled (t1076_1): committed per-artifact manifest files.** Each artifact gets
ONE JSON file at `<data-worktree>/artifacts/manifests/<id>.json` (`<id>` = the
handle minus its `art:` prefix; implementation:
`.aitask-scripts/lib/artifact_manifest.{py,sh}`). Rationale and semantics:

- **Travels with the `aitask-data` branch** — any configured PC resolves
  `art:<id>` (verified by a second-clone test); updating a manifest **never
  touches a task file** (both are t1076_1 test-pinned ACs).
- **Per-file granularity** mirrors the per-blob attachment meta ledger — no
  single-file write hotspot; unrelated artifacts never conflict on the shared
  data branch (same rationale that rejected bucketed metadata in t1030_5).
- Manifest mutations run under the same global attach-transaction lock as the
  attachment ledger (shared blob store; gc unions manifest references into its
  blocking set).
- **Malformed manifests fail closed, named:** every reader — including the
  tree-scanning `referenced-hashes` gc input — dies naming the offending file
  and violated invariant rather than silently shrinking the set.
- **Backend-resident manifests (shape 2) are explicitly deferred** to a future
  remote-backend task: resolution already goes handle → manifest → backend, so
  per-artifact backend-resident records can be added later without touching
  task files or the handle scheme. Manifest churn coupling to data-branch
  commits matches the cost model attachments already pay on add/rm.

## 5. Storage sink (seam B) — generalize t1030's adapter

**Done (t1076_1):** t1030's `attachment_backend.sh` contract
(`task_attachments_design.md` §5) is promoted to **`artifact_backend`**
(`.aitask-scripts/lib/artifact_backend.sh` + `lib/artifact_backends/`), serving
*both* attachments and artifacts. No new abstraction was invented — t1030's
adapter seam is the model, widened by one concept.

```sh
artifact_backend_put    <hash> <file>     # upload an immutable blob, idempotent
artifact_backend_get    <hash> <dest>     # download a blob to dest
artifact_backend_head   <hash>            # exit 0 if present
artifact_backend_delete <hash>            # remove a blob
artifact_backend_list                     # enumerate hashes
```

Same content-addressed naming and the same backend table as t1030 (local /
S3-compatible / GCS native / GitHub release assets / GDrive). Dispatch follows
the platform-extensible dispatcher pattern
([`gitremoteproviderintegration.md`](gitremoteproviderintegration.md)).

**Universal local cache + write-back.** Independent of the chosen backend, every
machine keeps a local cache (`~/.cache/ait/artifacts/<hash>`). A **wrapper bash
script reads a blob into the local file cache for local access and writes back to
the backend** (the `put`/`get`/`head` + write-back contract). Resolution order:
cache hit → backend `head`+`get` → loud error (never a silent placeholder).
The resolver (`lib/artifact_cache.sh::artifact_resolve`, t1076_1) **verifies the
resolved bytes' hash itself** — consumers never depend on caller-side re-hashing:
a corrupted cached copy self-heals (single re-fetch), a corrupted canonical blob
dies loudly and is never auto-repaired.

The **zero-config `local` backend** is the default for getting started and for
small immutable attachments — it lives in `.aitask-data/` and is committed, so it
gets archive/query/zip parity for free. **Shareable or large artifacts prefer a
configured remote backend** — see §7 for the HTML-plan policy, where this matters
most.

## 6. Share handle (seam C) — resolvable, not a raw URL

A share handle is `art:<id>`. It is **not** a raw backend URL. It resolves
through the **manifest** (§4b) plus **project config** that names the backend and
its location:

```
art:<id>  ──▶  manifest (current hash + backend)  ──▶  project config (how to reach backend)
          ──▶  backend get  ──▶  verify hash  ──▶  local cache  ──▶  local path
```

- The **task file** holds only the handle.
- The **manifest** holds the current hash + backend.
- The **project config** names how to reach the backend.

Proposed config home: a new `artifacts:` block in
`aitasks/metadata/project_config.yaml` (git-tracked, shared across the team) —
kept separate from execution profiles (workflow behavior) and `userconfig.yaml`
(per-user). Because references are **hash-first underneath**, a backend swap
touches only the manifest, never task files. **Any machine with the project
config resolves the same handle** — this is the "shareable native render whose
handle resolves on any machine with the project configuration" property.

## 7. HTML plans as a "special" artifact

HTML plans (t774) are unlike attachments: an attachment is an auxiliary *input*,
while an HTML plan is an **integral part of the task specification** — but one
that can be **much larger** than a markdown plan. This makes the storage policy
the central design question of this doc, and it changes t774's planned approach.

**Decision.** The markdown plan stays inline on `aitask-data` (small, diffable,
authoritative). The HTML plan becomes an **artifact**, **not** committed inline —
revising t774's "3rd file committed/archived/zipped like markdown plans" framing.
The backend policy, stated crisply:

- **Configured remote backend = the normal/preferred home** for any HTML plan
  meant to be shared across machines or with a team. Whenever a backend is
  configured, that is the default target.
- **Local cache is always active and mandatory.** Every HTML plan, regardless of
  backend, is materialized through the local cache for **open / edit / preview /
  offline** reads. The task/plan carries only the `art:<id>` handle; cache refresh
  or backend migration **never rewrites task files**.
- **`local` backend is bootstrap/dev/offline-only** — *not* the steady-state home
  for shareable plans. Its **cross-machine sharing limits are explicit**: a
  local-backend artifact resolves only on machines that carry the `aitask-data`
  branch holding it, and it bloats that branch for large HTML — which is exactly
  why shareable plans should target a remote backend. It exists so a fresh
  `ait setup` works with zero config and so offline work is possible, not as the
  place shareable HTML plans live.
- **Archive / query / zip parity** is delivered **through the storage layer**, not
  inline — the lifecycle (§9) runs over the artifact, not a committed file.

## 8. Planning-mode-write seam (via t635 gates) — explicit handle lifecycle

The blocker t774 flags: in **planning mode**, code agents cannot write arbitrary
files — only the internal markdown plan. So how does an HTML artifact get
produced?

The **gates framework (t635)** multi-stage processing is the intended mechanism.
Gates Phases 1–3 are shipped (ledger, orchestrator `aitask_run_gates.sh` /
`lib/gate_orchestrator.py`, re-entry, deferred archival, board/monitor views);
Phase 4 is in progress. **But there is no artifact-producing gate type yet** —
the integration roadmap names "artifact-producing follow-ups" as a third gate
family (alongside verifications and approvals) but leaves them as pseudo-gates
([`gates/integration-roadmap.md`](gates/integration-roadmap.md) §"Why integration").
This design proposes filling that gap.

**Proposal: an artifact-producing gate archetype** — a *post-approval* verifier
whose "pass = artifact produced (or explicitly waived)". The third gate family,
made first-class.

**Handle-binding lifecycle (the part that must be explicit).** Because the
markdown plan is approved in read-only plan mode, the chosen approach is: **the
handle is preallocated (derivable by convention) during planning, content is
materialized post-approval, and the approved plan body is never patched.**

1. **Planning (read-only).** The markdown plan references the HTML plan by its
   **derivable handle** `art:<id>` (e.g. `art:t<task>-htmlplan`) — pure text, no
   file write, no content yet. The approved plan is already self-consistent;
   nothing is patched into it afterward.
2. **Approval.** The plan is approved as-is; the handle reference is already
   present in the body.
3. **Post-approval window (the artifact gate / Step 7).** The gate:
   (a) generates the HTML content,
   (b) stores it as an immutable hash blob via the backend (§5),
   (c) creates/updates the **manifest** entry `art:<id> → current/versions/backend`
       (§4b),
   (d) writes the **set-once, handle-only `artifacts:` entry** into task
       frontmatter (§4).
   This is exactly the existing post-approval write pattern: task-workflow Step 7
   already writes risk fields and risk-mitigation tasks *after* approval precisely
   because plan mode is read-only. The plan **body** is never rewritten; only
   frontmatter (handle, set once) and the manifest (mutable) change.
4. **Refinement loop.** Later HTML edits = a new version + repoint **in the
   manifest**; the handle, the plan's reference, and the frontmatter entry all
   stay stable.

This design specifies the **seam only**. It does **not** depend on shipped
artifact-gate code — that gate type does not exist yet and is part of the
proposed decomposition (§11), coordinated with t635.

## 9. Lifecycle

Archive / query / zip and GC all run **through the storage layer + manifest**,
not over inline files:

- **Archive / query / zip parity.** The artifact is archived/queried/zipped via
  its handle and the storage layer, giving HTML plans the same lifecycle t774
  wanted for markdown plans — without committing them inline.
- **GC / refcount.** The manifest (§4b) joins t1030's per-blob refcount ledger as
  a second referrer class: a content hash is GC-able only when **no artifact
  version in any manifest** references it (implemented in t1076_1 —
  `ait attach gc`'s blocking set unions `artifact_manifest referenced-hashes`).
  Version awareness matters — an older version's blob must survive until that
  version is itself pruned, even after `current` moves on.
- **Fold semantics.** On fold, the artifact's manifest entry **re-binds to the
  primary task** (the handle in the folded task's frontmatter moves; manifest
  ownership updates), mirroring t1030's attachment re-bind-on-fold.

## 10. Relationship to t1030 content-addressing

The reconciliation, stated as a table:

| | Identity | Mutability | Where reference lives | Where state lives |
|---|---|---|---|---|
| **Artifact** | `art:<id>` stable handle | mutable (versioned, repointed) | task frontmatter (handle, set once) | manifest (`current`/`versions`/`backend`) |
| **Attachment** | one `sha256:` hash | immutable (single version) | task frontmatter (inline hash — **safe because immutable**) | n/a (the hash *is* the state) |

An attachment is the single-version, never-repointed degenerate case of an
artifact. "Update in place at the same handle" coexists with hash-first storage
because the **repoint happens in the manifest, not the task file** — the crux the
whole model turns on. The two designs are compatible: t1030's immutable inline
hash is correct *for attachments*; artifacts add the manifest indirection *for
mutability*.

## 11. Decomposition (realized as tasks)

The decomposition is realized under the umbrella parent **t1076**
(`unified_artifact_implementation`, anchored to t1065) with four children, plus a
re-scope of the existing **t774**. Sequenced against the building blocks (t1030's
backend seam first, then the artifact concept, then sharing/gate, then HTML-plan
integration).

1. **Storage abstraction generalization** → **t1076_1** — promote t1030's
   `attachment_backend` + universal cache to `artifact_backend` serving both
   attachments and artifacts; define the manifest and settle §4b (where it lives /
   how it travels).
   *Depends on:* t1030.
2. **Artifact pointer/version model + `artifacts:` frontmatter** → **t1076_2** —
   the stable handle, manifest pointer/version layer, and handle-only frontmatter
   schema (§3, §4).
   *Depends on:* t1076_1.
3. **Share-handle resolution + cache wrapper** → **t1076_3** —
   project-config-driven backend resolution (§6) and the put/get/head/write-back
   cache wrapper (§5).
   *Depends on:* t1076_2.
4. **HTML-plan-as-artifact integration** → **re-scoped t774** — route t774 HTML
   plans through the artifact layer per the §7 policy; archive/query/zip parity via
   the storage layer. t774 now `depends: [1076]` (see its coordination note).
   *Depends on:* t1076_2/_3/_4 (via the umbrella), and t774's own scope.
5. **Artifact-producing gate archetype** → **t1076_4** — formalize the §8 seam as a
   t635 gate family (post-approval producer; "pass = produced or waived"; the §8
   handle lifecycle). **Coordinated with t635** (the roadmap's unbuilt third gate
   family; bidirectional note on the t635 parent).
   *Depends on:* t1076_3 (sibling) + t635 Phase 4.

### Coverage against the existing task graph

Not all of this design is mapped to existing tasks. As of this writing:

| Piece | Existing coverage | Verdict |
|---|---|---|
| 1. Storage abstraction generalization (`artifact_backend` + manifest) | t1030 builds the **attachment** backend + cache + per-blob meta ledger only | **Done (t1076_1)** — t1030 was the foundation; the generalization to artifacts + the (net-new) manifest landed in t1076_1 |
| 2. Artifact pointer/version model + `artifacts:` frontmatter | none | **Gap** (net-new) |
| 3. Share-handle resolution + cache wrapper | none | **Gap** (net-new — the sharing dimension this task adds) |
| 4. HTML-plan-as-artifact integration | **t774** exists | **Mapped, needs re-scope** — its "3rd inline-committed file" framing is revised (see the t774 coordination note) |
| 5. Artifact-producing gate archetype | none — t635 children (t635_12…t635_24) have no such child; t635_19 is `docs_updated`, not artifact-producing | **Gap** (net-new t635 child) |

So three pieces were **net-new gaps** (2, 3, 5), one is **partial** on top of t1030
(1), and one is an **existing task to re-scope** (4). These have now been created
as **t1076 + children t1076_1..t1076_4**, with **t774** re-scoped to depend on the
umbrella — see the realized mapping above.

### Dependency-ordered implementation sequence

Building blocks are already tracked; the new work layers on top.

1. **t1030** — attachment backend + universal cache + per-blob meta ledger.
   *Prereq (landed). The storage foundation everything else builds on.*
2. **Storage generalization + artifact pointer/version model + `artifacts:`
   frontmatter** (pieces 1–2). *New; depends on t1030.* Settles the manifest
   (§4b).
3. **Share-handle resolution + cache wrapper** (piece 3). *New; depends on (2).*
   Parallelizable with (4).
4. **Artifact-producing gate archetype** (piece 5). *New; depends on (2) + t635
   Phase 4 — the orchestrator/verifier contract (t635_11) is already done.*
   Parallelizable with (3).
5. **HTML-plan-as-artifact integration = re-scoped t774** (piece 4). *Depends on
   (2), (3), (4) and t774.* Lands **last** — it is the consumer that ties the
   storage, share, and gate seams together for the first real artifact kind.

```
t1030 ──▶ (2) generalize + pointer model + frontmatter ──┬──▶ (3) share handle ──┐
                                                          │                       ├──▶ (5) re-scoped t774
t635 Phase 4 (t635_11 done) ──────────────────────────────┴──▶ (4) artifact gate ─┘
```

## 12. North star (Direction 4 — out of scope to detail)

The eventual destination is **team collaboration**: shareable artifacts + shared
/ observable gates + multi-agent-and-human review + connection to a messaging
platform — with the existing **shadow-agent** as the local precursor, and "work
goes on while your laptop is off the network" as a goal
([`slack/pros_and_cons.md`](slack/pros_and_cons.md)). This is the probable
long-term direction these bricks build toward, but too many building blocks are
not ready (gates not fully complete, no messaging-platform integration,
attachment/artifact support still being designed). **Noted as the horizon; not
scoped here.**

## 13. Rejected alternatives (recorded so they're not re-litigated)

- **Claude-native artifact passthrough** — complexity; locked to Claude Code +
  Team/Enterprise + claude.ai login (not API-key / Bedrock / Vertex); shaped
  around hosted pages we don't control. Learn from the UX, don't build on it.
- **AppLink-coupled sharing** — unwanted coupling; AppLink is LAN-only in v1
  (cross-network relay deferred). AppLink is at most a consumer.
- **Forcing artifacts through pure immutable-hash storage** — loses
  update-in-place / versioning, which HTML plans need.
- **Storing mutable pointer/version/backend state in task frontmatter** — would
  rewrite task files on every artifact edit or backend move, breaking the
  handle-only invariant. Resolved by the manifest indirection (§3, §4b).

## 14. Cross-references

- [`task_attachments_design.md`](task_attachments_design.md) — t1030 attachment
  design (backend adapter §5, universal local cache, hash-first model, per-blob
  meta ledger).
- t774 (`aitasks/t774_support_for_html_plans.md`) — native HTML-plan file type;
  this doc revises its storage approach (see the coordination note there).
- t635 / [`gates/`](gates/) — gate framework
  ([`gates/aitask-gate-framework.md`](gates/aitask-gate-framework.md),
  [`gates/integration-roadmap.md`](gates/integration-roadmap.md)); the
  planning-mode write seam and the artifact-producing gate family.
- [`applink/protocol.md`](applink/protocol.md) — why AppLink is not the share
  substrate (LAN-only v1).
- [`slack/pros_and_cons.md`](slack/pros_and_cons.md) — the team-collaboration
  north-star notes.
- [`gitremoteproviderintegration.md`](gitremoteproviderintegration.md) — the
  platform-extensible dispatcher pattern the storage backend adapter follows.
