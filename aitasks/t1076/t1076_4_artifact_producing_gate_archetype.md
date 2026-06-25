---
priority: medium
effort: high
depends: [t1076_3]
issue_type: feature
status: Ready
labels: [task_attachments, html_plans, gates]
anchor: 1065
created_at: 2026-06-25 11:04
updated_at: 2026-06-25 11:04
---

**Design spec:** `aidocs/unified_artifact_design.md` §8 (planning-mode-write seam).

## Context
Fourth substrate piece (parent t1076). Formalizes the **artifact-producing gate
archetype** — the gates framework's unbuilt "third gate family" (verifications /
approvals / **artifact-producing follow-ups**) named in
`aidocs/gates/integration-roadmap.md`. Solves t774's planning-mode-write blocker:
code agents in plan mode can only write the internal markdown plan, so the HTML
artifact is produced *post-approval*.

## Key work
- A post-approval verifier whose "pass = artifact produced (or explicitly waived)".
- **Handle-binding lifecycle (§8):** handle is preallocated (derivable, e.g.
  `art:t<task>-htmlplan`) and referenced in the markdown plan *during planning*
  (text only); content is materialized post-approval; the approved plan body is
  never patched. The gate (a) generates content, (b) stores immutable hash blob,
  (c) updates the manifest, (d) writes the set-once handle-only `artifacts:` entry
  — mirroring how task-workflow Step 7 writes risk fields post-approval.

## Coordinate with t635
This is a gates-framework gate family driven by the artifact model. Add a
bidirectional coordination note to/from t635 (gates parent). Depends on the
artifact model (t1076_2) AND t635 Phase 4 (orchestrator/verifier contract,
t635_11 — done). Decide at planning whether it ultimately lands as a t635 child or
stays here; for now it lives under t1076 with the t635 coordination link.

## Reference files / patterns
- `aidocs/gates/aitask-gate-framework.md` (verifier contract), `integration-roadmap.md`
  ("Why integration" — the three gate families).
- task-workflow Step 7 post-approval write pattern (risk fields / mitigations).
- t1076_2 (sibling) — the artifact model the gate produces into.

## Verification
- Plan references a derivable handle; after approval the gate produces content +
  manifest entry + frontmatter handle, with the approved plan body unchanged.
- Re-running is idempotent; a second edit creates a new version (manifest repoint).
