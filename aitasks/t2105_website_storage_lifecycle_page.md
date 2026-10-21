---
priority: low
effort: low
depends: [2099, 2100, 2101, 2102, 2104]
issue_type: documentation
status: Ready
labels: [task_attachments]
gates: [risk_evaluated]
anchor: 1065
created_at: 2026-10-21 14:52
updated_at: 2026-10-21 14:52
---

## Context

t1890 decided the artifact and attachment storage lifecycle
(`aidocs/artifact_storage_lifecycle.md`). Each implementation task documents its
own verbs and keys on the command pages. This task adds the **overview** a user
needs to pick a setup, and it can only be written once that behaviour exists
(the current-state-only rule in `aidocs/framework/documentation_conventions.md`).

Depends on:
- t2099 (fetch exclusion)
- t2100 (separate remote)
- t2101 (routing)
- t2102 (pin/prune)
- t2104 (compaction)

## Scope

A new `website/content/docs/concepts/` page on the storage lifecycle, following
the concept-page shape (What it is / Why it exists / How to use / See also).
It covers:

- **What a fresh computer downloads**, per backend, including the honest caveat
  that a plain `git clone` downloads a store that lives on `origin`, and that the
  first read fetches the whole store branch.
- The recommended setups: small text on the data branch; a separate artifact
  repository for large recordings.
- Routing (creation only; `move` for an existing artifact).
- Retention (nothing expires automatically; pin; explicit prune with dry-run).
- Cleanup vs. permanent purge, and the purge scope: no erasure of other clones,
  forks or backups; `aitask-data` history is never rewritten.

Link it from `concepts/artifacts.md` and `concepts/attachments.md`, and from
`commands/artifact.md` where useful. Use `{{< relref >}}` links.

## Verification

- `cd website && python3 check_links.py --build` passes.
- `hugo build --gc --minify` passes.
- `bash tests/test_website_doc_lists.sh` passes, if the page joins any
  drift-guarded list.
- Offer `check_link_relevance.py` for the new links.
