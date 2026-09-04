---
priority: medium
effort: medium
depends: [1698]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1698]
anchor: 1661
followup_kind: manual_verification
created_at: 2026-09-04 15:52
updated_at: 2026-09-04 15:52
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1698

## Verification Checklist

- [ ] In a REAL branch-mode repo (this one: `.aitask-data/` is the data worktree and, unlike `aitasks/` and `aiplans/`, `attachments/` and `artifacts/` are NOT symlinked into the checkout), verify each of the following. Every automated verb-level pin for t1698 runs in a LEGACY-mode fixture, so this is the only end-to-end branch-mode coverage.
- [ ] Preflight, task file: with an uncommitted edit in flight on a task's `.md`, run `ait attach add <task> <file>` and confirm it REFUSES, names that path, names the `./ait git commit --` remedy, adds no commit, and leaves the edit byte-identical.
- [ ] Preflight, ledger path: attach a file, commit, then hand-edit its `attachments/meta/<shard>.json` (a trailing newline keeps the JSON valid) and confirm `ait attach rm` refuses naming THAT path rather than the task file.
- [ ] Narrowing still holds: with the owner task file dirty, `ait artifact update <handle> <file>` must still SUCCEED (it stages only the manifest — the stable-handle split), and the dirty task file must be untouched afterwards.
- [ ] Rollback restores real bytes: with everything clean, force an abort mid-transaction (`AIT_PYTHON` shim failing `frontmatter_patch.py append` on `ait attach add`) and confirm the blob under `.aitask-data/attachments/blobs/` and the meta JSON are BOTH gone, the task file is unchanged, and `./ait git status --porcelain` is clean. This is the case the CWD-vs-data-root path bug would have broken: a wrong resolution records "absent" and the restore DELETES the real file.
- [ ] Rollback preserves a dirty bystander: repeat the forced abort while an unrelated task file is dirty, and confirm that edit still exists afterwards (the old restore-from-HEAD destroyed it).
- [ ] Lock hygiene: after each forced abort, confirm `.aitask-data/attachments/.attach.lock` is absent and a following `ait attach add` still acquires it.
- [ ] Message quality: read the refusal text as a user would — does it make the next action obvious without opening the source?
