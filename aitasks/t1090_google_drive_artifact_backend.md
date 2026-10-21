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
boardidx: 154624
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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1231_3** id=2026-10-19T13:26:29Z.cd5aa79338697c06989cc348 from=t1231_3 from_verified=yes at=2026-10-19T13:26:29Z base=a8a32dffcb4d96f53ed22dd6e8897ec2e60309a2 base_branch=main dirty=yes host=omg16
>
> | t1231_3 (commit a8a32dffc) added website docs for `ait artifact` and a drift guard that affects any new artifact backend. Advisory; tree-relative claims are dated by this note's base SHA.
> | 
> | - tests/test_website_doc_lists.sh Test 3 parses the dispatch arms of `_artifact_backend_call` in .aitask-scripts/lib/artifact_backend.sh (both the quoted `name) "artifact_name_${op}" ...` form and the unquoted extension-point form) and asserts:
> |   1. the set of arms equals the set of module files in .aitask-scripts/lib/artifact_backends/*.sh (a module without an arm, or an arm without a module, fails);
> |   2. each backend name appears as a literal table cell `| \`<name>\` |` in website/content/docs/concepts/artifacts.md (the backend table: Backend | Where blobs live | Pick it when).
> |   So landing a new backend without a row in that table makes the test exit 1.
> | - Other doc surfaces a new backend will likely want to extend: website/content/docs/commands/artifact.md (`## Configuration` key table, the `### init-store` section, and a backend section like `### The gitbranch backend`), the commented `artifacts:` block in seed/project_config.yaml, and aidocs/unified_artifact_design.md §5/§6 (which now lists the implemented set as local, dir, gitbranch).
> | - The concept page follows aidocs/framework/documentation_conventions.md "Concept pages": keep the new row and at most a one-sentence rule there; detail goes on the command page.

> **✉ note:t1890** id=2026-10-21T12:33:55Z.84c8642aee4fb3b0eb088dbb from=t1890 from_verified=yes at=2026-10-21T12:33:55Z base=ba4fde3822c67af2fb3aee56c36a16d673b3e1d2 base_branch=main dirty=yes host=omg16
>
> | Advisory from t1890 (aidocs/artifact_storage_lifecycle.md, commit ba4fde382). This backend is recorded as the future per-file external option (D1): one object per read, and a real backend delete is where reclaim actually happens. Unlike gitbranch, no history keeps the bytes. The backend-comparison row in §3 is marked as a design assumption until this lands. Orphan deletion should respect the unsynchronized-reference rule in §7: a blob may be published before its manifest is pushed.
