---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [html_plans, task_attachments]
children_to_implement: [t1076_1, t1076_2, t1076_3]
anchor: 1065
created_at: 2026-06-25 11:01
updated_at: 2026-06-25 11:04
---

Implement the **unified native artifact storage/share model** designed in
`aidocs/unified_artifact_design.md` (brainstorm task t1065).

This is the implementation umbrella for the net-new pieces of that design. The
design doc is the authoritative spec — read it (esp. the three-concern seam §2,
the stable-handle/mutable-manifest split §3–§4b, storage sink §5, share handle
§6, HTML-plan policy §7, planning-mode-write gate §8, lifecycle §9, and the
decomposition + dependency sequence §11).

## Children (sequenced per design §11)

1. **Storage abstraction generalization** — promote t1030's `attachment_backend`
   + universal cache to a shared `artifact_backend`; define the artifact manifest
   (§4b). *Depends on t1030 landing its attachment backend.*
2. **Artifact pointer/version model + `artifacts:` frontmatter** — stable handle,
   manifest pointer/version layer, handle-only frontmatter (§3, §4).
3. **Share-handle resolution + cache wrapper** — project-config-driven backend
   resolution (§6) + put/get/head/write-back cache wrapper (§5).
4. **Artifact-producing gate archetype** — formalize the §8 planning-mode-write
   seam as a t635 gate family (post-approval producer; the §8 handle lifecycle).
   **Coordinate with t635** (the roadmap's unbuilt "third gate family").

## Building-block dependencies (already tracked)

- **t1030** (task attachments) — the storage foundation child 1 generalizes.
- **t635 Phase 4** (gates orchestrator/verifier contract, t635_11 done) — the
  substrate child 4's gate archetype plugs into.
- **t774** (HTML plans) — the external consumer; re-scoped to route HTML plans
  through this artifact layer (design §7). t774 depends on this umbrella.

## Scope note

Per t1065's framing the decomposition was a proposal; these tasks were created as
a follow-up when the user elected to map the design to real tasks. No code in this
parent — children own the implementation.
