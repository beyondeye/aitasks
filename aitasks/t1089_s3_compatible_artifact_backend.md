---
priority: medium
effort: high
depends: [t1076_1]
issue_type: feature
status: Ready
labels: [task_attachments, html_plans]
anchor: 1065
created_at: 2026-06-28 12:10
updated_at: 2026-06-28 12:10
boardidx: 153600
---

Implement the **S3-compatible artifact backend** — one adapter covering Cloudflare R2 / AWS S3 / Backblaze B2 / MinIO / GCS-via-HMAC — against the **generalized `artifact_backend`** contract (so it serves both attachments and artifacts, not attachments alone).

Design spec: `aidocs/task_attachments_design.md` §5 (adapter contract), §7 (backend comparison — S3-compat is the recommended first remote, "one adapter, five providers; R2's zero egress is the standout"). `aidocs/unified_artifact_design.md` §5 (storage sink seam B; universal cache + write-back).

## Why this depends on t1076_1 (not t1030)
t1030 ships the local-only attachment backend behind a generalizable `attachment_backend` seam. **t1076_1** promotes that seam to `artifact_backend` (serving attachments AND artifacts) and defines the manifest. Building S3 against the *generalized* contract means it is implemented **once** and works for both concepts — avoiding a build-twice (once on `attachment_backend`, again after generalization). Hence `depends: [t1076_1]` (transitively gated on t1030).

## Key work
- New `.aitask-scripts/lib/artifact_backends/s3.sh` implementing the contract: `put/get/head/delete/list`, mapping the content-addressed `<2>/<62>` naming to `s3://<bucket>/aitasks/attachments/<2>/<62>` (design §4 table).
- Register via the dispatcher `case` arm + `# BACKEND-EXTENSION-POINT` marker established by t1030_2 / generalized by t1076_1.
- Provider-agnostic S3 API access (endpoint override for R2/B2/MinIO; HMAC/SigV4 auth). Decide the client: `aws` CLI vs `s3cmd`/`mc` vs a small Python (boto3) helper — pick the most portable + lowest-dep option and encapsulate the choice in one place (shell_conventions: platform CLI encapsulation).
- Config: an `artifacts:`/backend block in `aitasks/metadata/project_config.yaml` (git-tracked) naming endpoint / bucket / region; **credentials via env vars or a gitignored file — never committed** (coordinate with `aidocs/applink/security.md` posture on secrets).
- Bucket-setup docs (user-facing) following `aidocs/framework/documentation_conventions.md` (genericize provider names; current-state-only).

## Verification
- Round-trip a blob (`put → head → get → verify hash`) against a real or MinIO-local S3 endpoint; cache hit/miss + write-back per §5.
- Backend swap (local → s3) does not rewrite any task file (hash-first invariant).

## Reference files / patterns
- `aidocs/gitremoteproviderintegration.md` — platform-extensible dispatcher.
- t1030_2's `attachment_backend.sh` + `attachment_backends/local.sh` (the contract to mirror); t1076_1's generalized `artifact_backend`.
- `.aitask-scripts/lib/python_resolve.sh` if a Python client is chosen.

Coordination: gated on t1076_1 (generalized seam + manifest). Sibling follow-up: Google Drive backend (separate task).

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1231_3** id=2026-10-19T13:26:27Z.af04b0280f22e3ef4f92f3e7 from=t1231_3 from_verified=yes at=2026-10-19T13:26:27Z base=a8a32dffcb4d96f53ed22dd6e8897ec2e60309a2 base_branch=main dirty=yes host=omg16
>
> | t1231_3 (commit a8a32dffc) added website docs for `ait artifact` and a drift guard that affects any new artifact backend. Advisory; tree-relative claims are dated by this note's base SHA.
> | 
> | - tests/test_website_doc_lists.sh Test 3 parses the dispatch arms of `_artifact_backend_call` in .aitask-scripts/lib/artifact_backend.sh (both the quoted `name) "artifact_name_${op}" ...` form and the unquoted extension-point form) and asserts:
> |   1. the set of arms equals the set of module files in .aitask-scripts/lib/artifact_backends/*.sh (a module without an arm, or an arm without a module, fails);
> |   2. each backend name appears as a literal table cell `| \`<name>\` |` in website/content/docs/concepts/artifacts.md (the backend table: Backend | Where blobs live | Pick it when).
> |   So landing a new backend without a row in that table makes the test exit 1.
> | - Other doc surfaces a new backend will likely want to extend: website/content/docs/commands/artifact.md (`## Configuration` key table, the `### init-store` section, and a backend section like `### The gitbranch backend`), the commented `artifacts:` block in seed/project_config.yaml, and aidocs/unified_artifact_design.md §5/§6 (which now lists the implemented set as local, dir, gitbranch).
> | - The concept page follows aidocs/framework/documentation_conventions.md "Concept pages": keep the new row and at most a one-sentence rule there; detail goes on the command page.

> **✉ note:t1890** id=2026-10-21T12:33:51Z.970ad960be297d5fe1f41579 from=t1890 from_verified=yes at=2026-10-21T12:33:51Z base=ba4fde3822c67af2fb3aee56c36a16d673b3e1d2 base_branch=main dirty=yes host=omg16
>
> | Advisory from t1890 (aidocs/artifact_storage_lifecycle.md, commit ba4fde382). This backend is recorded as the future per-file external option (D1): one object per read, and a real backend delete is where reclaim actually happens. Unlike gitbranch, no history keeps the bytes. The backend-comparison row in §3 is marked as a design assumption until this lands. Orphan deletion should respect the unsynchronized-reference rule in §7: a blob may be published before its manifest is pushed.
