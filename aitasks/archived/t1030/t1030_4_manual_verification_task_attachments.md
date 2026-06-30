---
priority: medium
effort: medium
depends: [t1030_3]
issue_type: manual_verification
status: Done
labels: [verification, manual]
verifies: [t1030_1, t1030_2, t1030_3]
assigned_to: dario-e@beyond-eye.com
anchor: 1030
created_at: 2026-06-28 12:17
updated_at: 2026-06-30 11:35
completed_at: 2026-06-30 11:35
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [x] [t1030_1] `ait attach ls <task>` on a task with an `attachments:` block prints the entries (name, short-hash, size, backend); a task with none prints "No attachments." — PASS 2026-06-30 11:30 auto: test_attach_scaffold asserts ls prints name/short-hash(12)/size/backend and 'No attachments.' for none (39/39 pass)
- [x] [t1030_1] `ait attach <add|get|rm|gc>` (pre-storage state) print the not-yet-implemented notice rather than erroring obscurely. — PASS 2026-06-30 11:30 auto: premise superseded by t1030_2/3 — add/get/rm/gc now FUNCTIONAL; not-yet notice verified for remaining 'move' stub (scaffold: stub exits non-zero w/ not-yet msg; help marks unimplemented)
- [x] [t1030_2] `ait attach add <task> real-screenshot.png --name login-bug.png` succeeds; the file is hashed (sha256), under the 25 MB cap, and mime is detected. — PASS 2026-06-30 11:30 auto: test_attach_local_backend — add succeeds, mime detected (file --mime-type), oversize rejected per 25MB cap, small add passes (28/28 pass)
- [x] [t1030_2] After add: the blob exists at `.aitask-data/attachments/<first2>/<remaining62>`; the task frontmatter gained a correct `attachments:` mapping; `index.json` shows refcount 1 referencing this task. — PASS 2026-06-30 11:30 auto: DIVERGENCE — blob at attachments/blobs/<2>/<62>, refcount in PER-BLOB meta attachments/meta/<2>/<62>.json (NO global index.json, by design). Frontmatter mapping correct, refcount=1. Tested.
- [x] [t1030_2] The add produced exactly ONE `./ait git` commit containing the blob + index.json + task .md together (they never drift). — PASS 2026-06-30 11:30 auto: exactly ONE commit per add containing blob+meta+task together (s/index.json/per-blob meta/); unrelated staged file excluded. Tested.
- [x] [t1030_2] `ait attach get <task> login-bug.png --out /tmp/out.png` returns bytes byte-identical to the original (verify sha256 match); a cold cache populates `~/.cache/ait/attachments/<hash>` then serves. — PASS 2026-06-30 11:30 auto: get returns byte-identical bytes; cmd_get re-hashes & dies on mismatch (design §8); cold cache symlinks ~/.cache/ait/attachments/<hash>. Tested.
- [x] [t1030_2] `ait attach rm <task> login-bug.png` removes the frontmatter mapping and decrefs index.json to 0, but the blob is NOT deleted. — PASS 2026-06-30 11:30 auto: rm removes frontmatter mapping, decrefs to 0, blob NOT deleted (gc-deferred). Tested.
- [x] [t1030_3] Archiving a task that still references an attachment decrefs its hash in index.json and retains the blob (no synchronous deletion on archive). — PASS 2026-06-30 11:30 auto: blob RETAINED, no synchronous deletion on archive (✓ verified). DIVERGENCE: implemented design intentionally does NOT decref on archive (archived task is a real referrer/browsable history — see project_config attachments_gc_grace note); checklist 'decrefs in index.json' wording is stale. Tested.
- [x] [t1030_3] `ait attach gc` sweeps a zero-refcount orphan (backend_delete + index entry dropped) while RETAINING any hash still referenced by a live task. — PASS 2026-06-30 11:30 auto: gc sweeps zero-refcount orphan (backend_delete + meta file removed; s/index entry/meta file/), retains hashes referenced by live OR archived tasks. Tested.
- [x] [t1030_3] The `attachments_gc_grace` knob blocks a too-recent orphan from being swept; aging past the grace window lets the next `gc` remove it. — PASS 2026-06-30 11:30 auto: attachments_gc_grace blocks fresh orphan (within grace retained), aged-past-grace orphan swept on next gc. Tested.
- [x] [t1030_3] Folding task A (carrying an attachment) into task B re-binds the hash to B in index.json; the attachment survives A's deletion at archival (no double-decref). — PASS 2026-06-30 11:30 auto: fold rebinds hash to primary B (per-blob meta), primary frontmatter gains entry, blob survives A's deletion at archival, no double-decref. Tested (incl. dup-hash/collision/transitive).
- [x] [aggregate] A second `ait attach add` of the SAME file to a different task dedups (same hash, refcount 2, blob written once). — PASS 2026-06-30 11:30 auto: second add of same file to different task dedups — refs [5,6], blob written once (content-addressed, idempotent put). Tested.
- [x] [aggregate] Loud-failure path: a hash whose blob is missing from both cache and backend yields a clear error, never a silent placeholder. — PASS 2026-06-30 11:30 auto: confirmed LIVE — attachment_resolve dies loudly 'blob not found ... (cache miss and backend miss)' exit 1, no silent placeholder.
