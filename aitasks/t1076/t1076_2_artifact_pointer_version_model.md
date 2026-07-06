---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: high
depends: [t1076_1]
issue_type: feature
status: Implementing
labels: [task_attachments, html_plans]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1065
implemented_with: claudecode/fable5
created_at: 2026-06-25 11:04
updated_at: 2026-07-06 19:31
---

**Design spec:** `aidocs/unified_artifact_design.md` §3, §4 (+ §10 reconciliation).

## Context
Second substrate piece (parent t1076). Builds the artifact *concept* on top of the
generalized storage backend + manifest from t1076_1. This is the heart of the
model: the **stable-handle / mutable-manifest split**.

## Key work
- `art:<id>` **stable logical handle**, assigned once, never rewritten.
- Mutable pointer/version state (`current`, `versions[]`, `backend`) lives in the
  **manifest** (from t1076_1), NOT in task frontmatter.
- **Handle-only `artifacts:` frontmatter** (§4): entries carry only stable set-once
  fields — `handle`, `kind` (`html_plan|mockup|report|attachment|...`), optional
  `name`. No current/versions/backend in frontmatter.
- Operations: create (mint id, write v1, set current), update-in-place (new blob,
  append version, move current — manifest only), backend-move (substrate
  `set-backend` landed in t1076_1; the user-facing `ait artifact move` verb is a
  stub until a remote backend exists — a safe move must copy version blobs to a
  registered target first, and only `local` is registered today; scope settled
  at t1076_2 planning).
- Attachment = single-version, never-repointed degenerate case (§10).

## Reference files / patterns
- t1076_1 (sibling) — provides `artifact_backend` + manifest.
- `aidocs/task_attachments_design.md` §2-§3 — content-addressing + frontmatter
  (immutable inline-hash is safe there; contrast in §10 of the unified design).

## Verification
- Update-in-place repoints the manifest and leaves the referencing task file byte-
  identical (no frontmatter rewrite on edit or backend-move).
- `artifacts:` frontmatter parses; handle resolves to current version via manifest.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-06T15:15:15Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-06T21:13:49Z status=pass attempt=1 type=human
