---
priority: low
effort: high
depends: [t1076_1]
issue_type: feature
status: Ready
labels: [task_attachments, html_plans]
anchor: 1065
created_at: 2026-06-28 12:10
updated_at: 2026-06-28 12:10
boardidx: 80
---

Implement the **Google Drive artifact backend** against the **generalized `artifact_backend`** contract (serves both attachments and artifacts).

Design spec: `aidocs/task_attachments_design.md` §5 (adapter contract), §7 (backend comparison — GDrive: "free with a Google account, share-link friendly, heaviest auth (OAuth + token refresh, browser flow), weakest IAM"). `aidocs/unified_artifact_design.md` §5 (storage sink seam B).

## Why this depends on t1076_1 (not t1030)
Same rationale as the S3 backend: t1030 ships the local-only seam; **t1076_1** generalizes it to `artifact_backend`. Building GDrive against the generalized contract means it serves attachments and artifacts in one implementation. `depends: [t1076_1]` (transitively gated on t1030).

## Key work
- New `.aitask-scripts/lib/artifact_backends/gdrive.sh` implementing `put/get/head/delete/list`. Map content-addressed `<hash>` to `<hash>`-named files inside a dedicated Drive folder (Drive has no native content-addressed paths, so maintain a name→fileId lookup; `head` = name lookup, `get` = download by fileId, `delete` = trash/delete by fileId, `list` = folder enumeration).
- Register via the dispatcher `case` arm + extension-point marker (from t1030_2 / t1076_1).
- **Auth is the hard part** (call out in the plan): OAuth 2.0 with a one-time browser consent flow + refresh-token storage. Store the refresh token in a gitignored, per-user location (NOT in project_config.yaml, NOT committed); coordinate with `aidocs/applink/security.md` secret-handling posture. Decide client: Google's `gdrive` CLI vs a Python helper using `google-api-python-client` (likely the cleaner path given `python_resolve.sh`).
- Config: Drive folder id / app credentials home in `project_config.yaml` (non-secret) + per-user token in the gitignored secret store.
- User-facing setup docs (OAuth app + consent) per `aidocs/framework/documentation_conventions.md`.

## Caveats (record in plan)
- Heaviest auth UX of all backends; token-refresh lifecycle and revocation handling needed. Weakest IAM (folder-level sharing, not per-object). Best suited where a Google account is already the user's hub and share-links are wanted.

## Verification
- Round-trip a blob (`put → head → get → verify hash`) against a real Drive folder (test account); cache hit/miss + write-back per §5.
- Token-refresh path exercised (expired access token → silent refresh → success).
- Backend swap to/from gdrive does not rewrite any task file (hash-first invariant).

## Reference files / patterns
- `aidocs/gitremoteproviderintegration.md` — dispatcher pattern.
- t1030_2's `attachment_backend.sh` + `local.sh`; t1076_1's generalized `artifact_backend`; t1089 (S3 backend) as a sibling remote-backend reference once it lands.
- `.aitask-scripts/lib/python_resolve.sh`.

Coordination: gated on t1076_1. Sibling follow-up of the S3 backend task (t1089).
