---
priority: medium
effort: medium
depends: [t1030_3]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1030_1, 1030_2, 1030_3]
anchor: 1030
created_at: 2026-06-28 12:17
updated_at: 2026-06-28 12:17
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1030_1] `ait attach ls <task>` on a task with an `attachments:` block prints the entries (name, short-hash, size, backend); a task with none prints "No attachments."
- [ ] [t1030_1] `ait attach <add|get|rm|gc>` (pre-storage state) print the not-yet-implemented notice rather than erroring obscurely.
- [ ] [t1030_2] `ait attach add <task> real-screenshot.png --name login-bug.png` succeeds; the file is hashed (sha256), under the 25 MB cap, and mime is detected.
- [ ] [t1030_2] After add: the blob exists at `.aitask-data/attachments/<first2>/<remaining62>`; the task frontmatter gained a correct `attachments:` mapping; `index.json` shows refcount 1 referencing this task.
- [ ] [t1030_2] The add produced exactly ONE `./ait git` commit containing the blob + index.json + task .md together (they never drift).
- [ ] [t1030_2] `ait attach get <task> login-bug.png --out /tmp/out.png` returns bytes byte-identical to the original (verify sha256 match); a cold cache populates `~/.cache/ait/attachments/<hash>` then serves.
- [ ] [t1030_2] `ait attach rm <task> login-bug.png` removes the frontmatter mapping and decrefs index.json to 0, but the blob is NOT deleted.
- [ ] [t1030_3] Archiving a task that still references an attachment decrefs its hash in index.json and retains the blob (no synchronous deletion on archive).
- [ ] [t1030_3] `ait attach gc` sweeps a zero-refcount orphan (backend_delete + index entry dropped) while RETAINING any hash still referenced by a live task.
- [ ] [t1030_3] The `attachments_gc_grace` knob blocks a too-recent orphan from being swept; aging past the grace window lets the next `gc` remove it.
- [ ] [t1030_3] Folding task A (carrying an attachment) into task B re-binds the hash to B in index.json; the attachment survives A's deletion at archival (no double-decref).
- [ ] [aggregate] A second `ait attach add` of the SAME file to a different task dedups (same hash, refcount 2, blob written once).
- [ ] [aggregate] Loud-failure path: a hash whose blob is missing from both cache and backend yields a clear error, never a silent placeholder.
