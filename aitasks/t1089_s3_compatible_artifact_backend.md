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
boardidx: 100
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
